from __future__ import annotations

import json
import os
import threading
from pathlib import Path

import webview

from .backdrop import GLASS_LIVE
from .backdrop import begin_window_drag
from .backdrop import capture_desktop_backdrop
from .backdrop import install_glass_backdrop
from .backdrop import live_blur_strength
from .backdrop import move_window_near_pointer
from .backdrop import window_origin
from .backdrop import window_position_payload
from .bridge import AppBridge


# Must match --shell-pad in frontend/src/index.css.
WINDOW_SHADOW_MARGIN = 16


def resolve_frontend_entry(*, project_root: Path, dev_mode: bool) -> str | Path:
    if dev_mode:
        return "http://127.0.0.1:5173"
    return (project_root / "frontend" / "dist" / "index.html").as_posix()


def resolve_runtime_mode(*, project_root: Path, env: dict[str, str] | None = None) -> tuple[bool, bool]:
    runtime_env = os.environ if env is None else env
    dist_exists = (project_root / "frontend" / "dist" / "index.html").exists()

    dev_mode = runtime_env.get("CLIPBOARD_DEV")
    if dev_mode is None:
        dev_enabled = not dist_exists
    else:
        dev_enabled = dev_mode != "0"

    debug_mode = runtime_env.get("CLIPBOARD_DEBUG", "0") != "0"
    return dev_enabled, debug_mode


class AppWindowController:
    def __init__(
        self,
        *,
        project_root: Path,
        bridge: AppBridge,
        snapshot_provider,
        dev_mode: bool,
        start_hidden: bool = False,
        close_to_tray_provider=lambda: True,
        set_on_top_callback=None,
        hide_on_blur_provider=lambda: False,
        on_blur_hide=None,
        backdrop_capture=None,
        appearance_provider=lambda: {},
        warm_webview=None,
    ) -> None:
        self.project_root = project_root
        self.bridge = bridge
        self.snapshot_provider = snapshot_provider
        self.dev_mode = dev_mode
        self.start_hidden = start_hidden
        self.close_to_tray_provider = close_to_tray_provider
        self.set_on_top_callback = set_window_on_top if set_on_top_callback is None else set_on_top_callback
        self.hide_on_blur_provider = hide_on_blur_provider
        self.on_blur_hide = on_blur_hide
        self.backdrop_capture = capture_desktop_backdrop if backdrop_capture is None else backdrop_capture
        self.warm_webview = warm_hidden_webview if warm_webview is None else warm_webview
        self.appearance_provider = appearance_provider
        self._corner_radius: float | None = None
        self._live_strength: float | None = None
        self._appearance: dict[str, object] = {}
        self.window: webview.Window | None = None
        self._move_lock = threading.Lock()
        self._move_in_flight = False
        self._move_dirty = False
        self._has_glass = False
        self._glass = None
        self._dialog_depth = 0
        self._is_loaded = False
        self._allow_close = False
        self._is_hidden = start_hidden
        self._visibility_seq = 0
        self._is_always_on_top = False

    def create(self) -> webview.Window:
        entry = resolve_frontend_entry(project_root=self.project_root, dev_mode=self.dev_mode)
        url = entry if isinstance(entry, str) and entry.startswith("http") else Path(str(entry)).resolve().as_uri()

        self.window = webview.create_window(
            title="CipherClip",
            url=url,
            js_api=self.bridge,
            # The page panel is 440x640; the extra WINDOW_SHADOW_MARGIN on each side is transparent
            # room for its floating shadow.
            width=440 + 2 * WINDOW_SHADOW_MARGIN,
            height=640 + 2 * WINDOW_SHADOW_MARGIN,
            min_size=(380, 480),
            hidden=self.start_hidden,
            on_top=self._is_always_on_top,
            frameless=True,
            easy_drag=False,
            background_color="#000000",
            text_select=True,
        )
        self.window.events.before_show += self._handle_before_show
        self.window.events.loaded += self._handle_loaded
        self.window.events.closing += self._handle_closing
        self.window.events.moved += self._handle_moved
        self.bridge._bind_hide_window(self.hide)
        self.bridge._bind_pick_storage_path(self.pick_storage_path)
        self.bridge._bind_toggle_always_on_top(self.toggle_always_on_top)
        self.bridge._bind_is_always_on_top(lambda: self.is_always_on_top)
        self.bridge._bind_preview_appearance(self.apply_appearance)
        self.bridge._bind_begin_window_drag(self.begin_drag)
        return self.window

    def show(self) -> None:
        if self.window is None:
            return
        was_hidden = self._is_hidden
        if was_hidden:
            move_window_near_pointer(self.window)
        self.window.show()
        self.window.restore()
        self._apply_always_on_top()
        self._is_hidden = False
        if was_hidden and self._is_loaded:
            # Lets the page play its "materialise" animation each time the panel is summoned, and
            # wakes its animations (see hide).
            self._visibility_seq += 1
            self._dispatch_event("cipherclip:reveal", {"seq": self._visibility_seq})
            # The desktop grab (~0.1s) runs after showing so summoning never waits on it; the
            # panel excludes itself from the capture and the fresh glass lands during the fade-in.
            self._send_backdrop()

    @property
    def glass_mode(self) -> str | None:
        return None if self._glass is None else self._glass.mode

    def apply_appearance(self, appearance: dict[str, object]) -> None:
        """Follow the saved glass settings: live vs snapshot source and the corner radius."""
        if self._glass is None:
            return
        snapshot_look_changed = any(
            appearance.get(key) != self._appearance.get(key) for key in ("backdropBlur", "backdropSaturation")
        )
        self._appearance = dict(appearance)
        previous = self._glass.mode
        want_live = appearance.get("glassSource", "live") == "live"
        mode = self._glass.use_live(want_live) if want_live != (previous == GLASS_LIVE) else previous

        radius = float(appearance.get("cornerRadius", 24))
        if radius != self._corner_radius:
            self._corner_radius = radius
            self._glass.set_corner_radius(radius)

        self._apply_live_backdrop(appearance)

        if mode != previous:
            self._announce_glass()
        if (mode != previous or snapshot_look_changed) and not self._is_hidden:
            self._send_backdrop()

    def _apply_live_backdrop(self, appearance: dict[str, object]) -> None:
        blur = float(appearance.get("backdropBlur", 10))
        if getattr(self._glass, "filtered", False):
            # Real filters on the captured desktop: every backdrop setting applies live.
            self._glass.set_filter(
                blur_dip=blur,
                saturation=float(appearance.get("backdropSaturation", 100)) / 100,
            )
            return
        strength = live_blur_strength(blur)
        if strength != self._live_strength:
            self._live_strength = strength
            self._glass.set_live_strength(strength)

    def _announce_glass(self) -> None:
        if not self._is_loaded or self._glass is None:
            return
        self._dispatch_event(
            "cipherclip:glass",
            {
                "mode": self._glass.mode,
                "liveAvailable": self._glass.live_available,
                "filtered": bool(getattr(self._glass, "filtered", False)),
            },
        )

    def _send_backdrop(self) -> None:
        if not self._is_loaded or self.window is None:
            return
        if self.glass_mode == GLASS_LIVE:
            # The compositor blurs the desktop live; no snapshot needed.
            return
        payload = self.backdrop_capture(self.window, self._appearance)
        if payload is not None:
            self._dispatch_event("cipherclip:backdrop", payload)

    def begin_drag(self, grab_x: float, grab_y: float) -> None:
        """Drag the window from the page's title area; elastic unless animations are off."""
        if self.window is None:
            return
        elastic = bool(self._appearance.get("animations", True))
        begin_window_drag(self.window, (int(grab_x), int(grab_y)), elastic=elastic)

    def _handle_moved(self) -> None:
        if self.glass_mode == GLASS_LIVE:
            # Only the snapshot is lined up by the page; the live glass follows by itself.
            return
        # Move events arrive in bursts while dragging; keep at most one update in flight and
        # always finish with the latest position.
        with self._move_lock:
            if self._move_in_flight:
                self._move_dirty = True
                return
            self._move_in_flight = True
        try:
            while True:
                origin = window_origin(self.window)
                if origin is not None and self._is_loaded:
                    self._dispatch_event("cipherclip:moved", window_position_payload(origin))
                with self._move_lock:
                    if not self._move_dirty:
                        self._move_in_flight = False
                        return
                    self._move_dirty = False
        except Exception:
            with self._move_lock:
                self._move_in_flight = False
            raise

    def _dispatch_event(self, name: str, detail: dict[str, object]) -> None:
        payload = json.dumps(detail, ensure_ascii=False)
        self.window.evaluate_js(f"window.dispatchEvent(new CustomEvent('{name}', {{ detail: {payload} }}));")

    def hide(self) -> None:
        if self.window is None:
            return
        # Mark hidden first so the Deactivate event raised by hiding is not treated as a blur.
        was_hidden = self._is_hidden
        self._is_hidden = True
        self.window.hide()
        if not was_hidden and self._is_loaded:
            # A hidden WebView2 still reports its page as visible and keeps drawing every animation
            # frame (measured: over a core of CPU and GPU, and a renderer growing past 2 GB): the
            # page pauses them until the next reveal. Sent from a worker thread, because
            # evaluate_js waits on the UI thread, which hide can be called from (Deactivate).
            self._visibility_seq += 1
            seq = self._visibility_seq
            threading.Thread(
                target=self._dispatch_event, args=("cipherclip:sleep", {"seq": seq}), daemon=True
            ).start()

    def toggle_visibility(self) -> None:
        if self._is_hidden:
            self.show()
            return
        self.hide()

    def destroy(self) -> None:
        if self.window is None:
            return
        self._allow_close = True
        self.window.destroy()

    @property
    def is_hidden(self) -> bool:
        return self._is_hidden

    @property
    def is_always_on_top(self) -> bool:
        return self._is_always_on_top

    def toggle_always_on_top(self) -> None:
        self._is_always_on_top = not self._is_always_on_top
        self._apply_always_on_top()

    def dispatch_snapshot(self, snapshot: dict[str, object]) -> None:
        if not self._is_loaded or self.window is None:
            return

        payload = json.dumps(snapshot, ensure_ascii=False)
        self.window.evaluate_js(
            f"window.dispatchEvent(new CustomEvent('clipboard:snapshot', {{ detail: {payload} }}));"
        )

    def _handle_before_show(self) -> None:
        if self.window is None or self._has_glass:
            return
        appearance = self.appearance_provider()
        self._appearance = dict(appearance)
        self._corner_radius = float(appearance.get("cornerRadius", 24))
        self._glass = install_glass_backdrop(
            self.window,
            on_deactivate=self._handle_deactivate,
            shadow_margin_dip=WINDOW_SHADOW_MARGIN,
            corner_radius_dip=self._corner_radius,
            prefer_live=appearance.get("glassSource", "live") == "live",
        )
        self._has_glass = self._glass is not None
        if self._glass is not None:
            self._apply_live_backdrop(appearance)
        self._announce_glass()

    def _handle_deactivate(self) -> None:
        if self._is_hidden or self._dialog_depth or self._is_always_on_top:
            return
        if not self.hide_on_blur_provider():
            return
        self.hide()
        if self.on_blur_hide is not None:
            self.on_blur_hide()

    def run_modal(self, action):
        """Run a dialog-showing callable without the panel auto-hiding underneath it."""
        self._dialog_depth += 1
        try:
            return action()
        finally:
            self._dialog_depth -= 1

    def _handle_loaded(self) -> None:
        self._is_loaded = True
        self.dispatch_snapshot(self.snapshot_provider())
        self._announce_glass()
        if not self._is_hidden:
            self._send_backdrop()
            return
        # Started in the tray: the page sleeps (animations paused), then renders once in the
        # background, so the first summon is as quick as every later one.
        self._visibility_seq += 1
        self._dispatch_event("cipherclip:sleep", {"seq": self._visibility_seq})
        self.warm_webview(self.window)

    def _handle_closing(self) -> bool | None:
        if self._allow_close:
            return None

        if self.close_to_tray_provider():
            self.hide()
            return False

        return None

    def pick_storage_path(self, current_path: str) -> str | None:
        if self.window is None:
            return None

        dialog_type = getattr(getattr(webview, "FileDialog", None), "FOLDER", getattr(webview, "FOLDER_DIALOG", 20))
        selection = self.run_modal(
            lambda: self.window.create_file_dialog(dialog_type=dialog_type, directory=current_path or "")
        )
        if not selection:
            return None
        return str(Path(selection[0]))

    def _apply_always_on_top(self) -> None:
        if self.window is None:
            return
        self.set_on_top_callback(self.window, self._is_always_on_top)


def set_window_on_top(window: webview.Window, enabled: bool) -> None:
    native_window = getattr(window, "native", None)

    def apply_topmost() -> None:
        if hasattr(type(window), "on_top"):
            window.on_top = enabled
            return
        if hasattr(window, "on_top"):
            setattr(window, "on_top", enabled)
            return
        if native_window is not None:
            native_window.TopMost = enabled

    if native_window is None:
        apply_topmost()
        return

    if getattr(native_window, "InvokeRequired", False):
        try:
            from System import Action
        except ModuleNotFoundError:
            import clr

            clr.AddReference("System.Windows.Forms")
            from System import Action

        native_window.Invoke(Action(apply_topmost))
        return

    apply_topmost()


def warm_hidden_webview(window: webview.Window) -> bool:
    """Let the page render while the app still sits hidden in the tray.

    Started hidden, WebView2 renders nothing until the window is first shown, so the first summon
    had to do all of it at once (measured: about half a second before the first frame, then a
    stuttering reveal); every later summon is smooth, because after one show/hide WebView2 keeps
    the page "visible" behind the hidden window. This puts the page in that same state from the
    start, by marking the WebView2 controller visible without showing the window. The page keeps
    its animations paused meanwhile (cipherclip:sleep), so it costs nothing while it waits.
    """
    form = getattr(window, "native", None)
    control = getattr(getattr(form, "browser", None), "webview", None)
    if form is None or control is None:
        return False
    try:
        from System import Action
        from System.Reflection import BindingFlags

        flags = BindingFlags.NonPublic | BindingFlags.Instance
        controller = None
        for field in control.GetType().GetFields(flags):
            if field.FieldType.Name == "CoreWebView2Controller":
                controller = field.GetValue(control)
                break
        if controller is None:
            return False

        def wake() -> None:
            controller.IsVisible = True

        form.Invoke(Action(wake))
        return True
    except Exception:
        return False
