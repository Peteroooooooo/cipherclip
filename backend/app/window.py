from __future__ import annotations

import json
import os
import threading
from pathlib import Path

import webview

from .backdrop import CONCEAL_MS
from .backdrop import CONCEAL_SCALE
from .backdrop import GLASS_LIVE
from .backdrop import REVEAL_MS
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

# A normal launch waits for the page to settle after it has loaded, but never longer than this.
PAGE_READY_TIMEOUT_S = 5.0
# ...and shows the window anyway if the page has not even loaded by then (a cold start after a
# long idle can take several seconds just to start WebView2).
PAGE_LOAD_TIMEOUT_S = 20.0
# pywebview's evaluate_js waits for the page without a timeout: if the page's renderer has died,
# a summon would wait forever and take the shortcut and the tray down with it.
JS_CALL_TIMEOUT_S = 1.0


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
        watch_page=None,
        window_icon: str | None = None,
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
        self.watch_page = watch_page_crashes if watch_page is None else watch_page
        self._watching_page = False
        self.window_icon = window_icon
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
        # The window is always created hidden: a normal launch shows it once the page has drawn
        # its first frame (page_ready), so no black box or loading text ever appears.
        self._is_hidden = True
        self._show_when_ready = not start_hidden
        self._page_ready = False
        self._conceal_token: int | None = None
        # On screen before the page could play its reveal (load fallback, reload after a crash):
        # the reveal runs once the page reports ready.
        self._reveal_pending = False
        self._visibility_seq = 0
        self._is_always_on_top = False

    def create(self) -> webview.Window:
        entry = resolve_frontend_entry(project_root=self.project_root, dev_mode=self.dev_mode)
        url = entry if isinstance(entry, str) and entry.startswith("http") else Path(str(entry)).resolve().as_uri()

        self.window = webview.create_window(
            title="ClipDeck",
            url=url,
            js_api=self.bridge,
            # The page panel is 440x640; the extra WINDOW_SHADOW_MARGIN on each side is transparent
            # room for its floating shadow.
            width=440 + 2 * WINDOW_SHADOW_MARGIN,
            height=640 + 2 * WINDOW_SHADOW_MARGIN,
            min_size=(380, 480),
            hidden=True,
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
        if hasattr(self.bridge, "_bind_conceal_window"):
            self.bridge._bind_conceal_window(lambda: self.hide(animated=True))
        if hasattr(self.bridge, "_bind_page_ready"):
            self.bridge._bind_page_ready(self.page_ready)
        if self._show_when_ready:
            self._start_show_fallback(PAGE_LOAD_TIMEOUT_S)
        return self.window

    def _start_show_fallback(self, seconds: float) -> None:
        fallback = threading.Timer(seconds, self._show_after_timeout)
        fallback.daemon = True
        fallback.start()

    def show(self) -> None:
        if self.window is None:
            return
        self._show_when_ready = False
        was_hidden = self._is_hidden
        # Summoned again while the conceal animation is still running: the window never left the
        # screen, so it reverses in place instead of jumping to the pointer.
        mid_conceal = self._conceal_token is not None
        self._conceal_token = None
        if was_hidden and not mid_conceal:
            move_window_near_pointer(self.window)
        if was_hidden and not self._is_loaded:
            self._reveal_pending = True
        if was_hidden and self._is_loaded:
            self._reveal_pending = False
            # The page has sat concealed (transparent, slightly small, blurred) since it was
            # hidden, so the frame WebView2 shows first is already the reveal's starting point;
            # the page and the native glass then grow in together.
            self._animate_glass(opacity=1.0, scale=1.0, ms=REVEAL_MS, from_concealed=not mid_conceal)
            self._visibility_seq += 1
            self._dispatch_event("clipdeck:reveal", {"seq": self._visibility_seq})
        self.window.show()
        self.window.restore()
        self._apply_always_on_top()
        self._is_hidden = False
        if was_hidden and self._is_loaded:
            # The desktop grab (~0.1s) runs after showing so summoning never waits on it; the
            # panel excludes itself from the capture and blends in the fresh glass.
            self._send_backdrop()

    def page_ready(self) -> None:
        """The page has drawn its first real frame (data loaded): a normal launch shows now."""
        self._page_ready = True
        self._show_if_pending()
        self._reveal_if_pending()

    def _reveal_if_pending(self) -> None:
        if not (self._reveal_pending and self._is_loaded and not self._is_hidden):
            return
        self._reveal_pending = False
        self._animate_glass(opacity=1.0, scale=1.0, ms=REVEAL_MS, from_concealed=True)
        self._visibility_seq += 1
        self._dispatch_event("clipdeck:reveal", {"seq": self._visibility_seq})
        self._send_backdrop()

    def _show_if_pending(self) -> None:
        if self._show_when_ready and self._is_loaded and self._page_ready:
            self.show()

    def _show_after_timeout(self) -> None:
        # Safety net: never leave a normal launch invisible because the page went quiet.
        if self._show_when_ready:
            self.show()
        self._reveal_if_pending()

    @property
    def _motion_enabled(self) -> bool:
        return bool(self._appearance.get("animations", True))

    def _animate_glass(self, *, opacity: float, scale: float, ms: int, from_concealed: bool = False) -> None:
        animate = getattr(self._glass, "animate", None)
        if animate is None:
            return
        try:
            animate(
                opacity=opacity,
                scale=scale,
                ms=ms if self._motion_enabled else 0,
                from_concealed=from_concealed and self._motion_enabled,
            )
        except Exception:
            pass

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
            "clipdeck:glass",
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
            self._dispatch_event("clipdeck:backdrop", payload)

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
                    self._dispatch_event("clipdeck:moved", window_position_payload(origin))
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
        self._evaluate(f"window.dispatchEvent(new CustomEvent('{name}', {{ detail: {payload} }}));")

    def _evaluate(self, script: str) -> None:
        """Run a script in the page, waiting for it at most JS_CALL_TIMEOUT_S."""
        window = self.window
        done = threading.Event()

        def run() -> None:
            try:
                window.evaluate_js(script)
            except Exception:
                pass
            finally:
                done.set()

        threading.Thread(target=run, name="page-script", daemon=True).start()
        done.wait(JS_CALL_TIMEOUT_S)

    def _handle_page_crashed(self) -> None:
        # The page's renderer died and is being reloaded (watch_page_crashes). Until `loaded` is
        # raised again nothing is sent to it; that handler then puts the fresh page in the state
        # the window is in.
        self._is_loaded = False
        self._page_ready = False
        if not self._is_hidden:
            # The page is blank until the reload lands: take the empty glass away meanwhile.
            self._reveal_pending = True
            self._animate_glass(opacity=0.0, scale=CONCEAL_SCALE, ms=CONCEAL_MS)

    def hide(self, *, animated: bool = False) -> None:
        """Hide the panel. `animated` plays a short conceal first (shortcut, Esc, click-away);
        paste and focus-loss hides stay instant so nothing waits on the animation."""
        if self.window is None:
            return
        # Mark hidden first so the Deactivate event raised by hiding is not treated as a blur.
        was_hidden = self._is_hidden
        self._is_hidden = True
        if was_hidden:
            pending = self._conceal_token
            if pending is not None and not animated:
                self._finish_conceal(pending)
            return
        if animated and self._is_loaded and self._motion_enabled:
            self._visibility_seq += 1
            token = self._visibility_seq
            self._conceal_token = token
            self._animate_glass(opacity=0.0, scale=CONCEAL_SCALE, ms=CONCEAL_MS)
            threading.Thread(
                target=self._dispatch_event, args=("clipdeck:conceal", {"seq": token}), daemon=True
            ).start()
            timer = threading.Timer(CONCEAL_MS / 1000, self._finish_conceal, args=(token,))
            timer.daemon = True
            timer.start()
            return
        self._hide_now()

    def _finish_conceal(self, token: int) -> None:
        if self._conceal_token != token or not self._is_hidden:
            return
        self._conceal_token = None
        self._hide_now()

    def _hide_now(self) -> None:
        self.window.hide()
        # Leave the native glass at the reveal's starting point for the next summon.
        self._animate_glass(opacity=0.0, scale=CONCEAL_SCALE, ms=0)
        if self._is_loaded:
            # A hidden WebView2 still reports its page as visible and keeps drawing every animation
            # frame (measured: over a core of CPU and GPU, and a renderer growing past 2 GB): the
            # page pauses them until the next reveal. Sent from a worker thread, because
            # evaluate_js waits on the UI thread, which hide can be called from (Deactivate).
            self._visibility_seq += 1
            seq = self._visibility_seq
            threading.Thread(
                target=self._dispatch_event, args=("clipdeck:sleep", {"seq": seq}), daemon=True
            ).start()

    def toggle_visibility(self) -> None:
        if self._is_hidden:
            self.show()
            return
        self.hide(animated=True)

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
        self._evaluate(f"window.dispatchEvent(new CustomEvent('clipboard:snapshot', {{ detail: {payload} }}));")

    def _handle_before_show(self) -> None:
        if self.window is None or self._has_glass:
            return
        if self.window_icon:
            set_window_icon(self.window, self.window_icon)
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
            # Start out where every reveal starts, so the glass never shows up ahead of the page.
            self._animate_glass(opacity=0.0, scale=CONCEAL_SCALE, ms=0)
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
        if not self._watching_page:
            self._watching_page = self.watch_page(self.window, self._handle_page_crashed)
        self.dispatch_snapshot(self.snapshot_provider())
        self._announce_glass()
        if not self._is_hidden:
            if not self._reveal_pending:
                self._send_backdrop()
                return
            # On screen before the page was there (load fallback, reload after a crash): the page
            # and the glass wait concealed, then reveal together once the page has settled.
            self._visibility_seq += 1
            self._dispatch_event("clipdeck:sleep", {"seq": self._visibility_seq})
            self._start_show_fallback(PAGE_READY_TIMEOUT_S)
            if self._page_ready:
                self._reveal_if_pending()
            return
        # Hidden in the tray (always, at first): the page sleeps (animations paused) and sits
        # concealed, then renders once in the background, so the first summon is as quick as
        # every later one. A normal launch then shows as soon as the page reports ready.
        self._visibility_seq += 1
        self._dispatch_event("clipdeck:sleep", {"seq": self._visibility_seq})
        self.warm_webview(self.window)
        if self._show_when_ready:
            self._start_show_fallback(PAGE_READY_TIMEOUT_S)
        self._show_if_pending()

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


def set_window_icon(window: webview.Window, icon_path: str) -> bool:
    """Put the ClipDeck icon on the window and its taskbar button (pywebview's WinForms host
    always takes the running exe's icon, which from source is python.exe's)."""
    form = getattr(window, "native", None)
    if form is None:
        return False
    try:
        from System import Action
        from System.Drawing import Icon

        def apply() -> None:
            form.Icon = Icon(icon_path)

        form.Invoke(Action(apply))
        return True
    except Exception:
        return False


PAGE_CRASH_KINDS = {"RenderProcessExited", "RenderProcessUnresponsive"}


def watch_page_crashes(window: webview.Window, on_crash) -> bool:
    """Reload the page whenever its renderer process dies or hangs.

    WebView2 restarts its GPU process by itself, but a dead renderer leaves an empty page that
    never answers scripts again. Returns False when there is no WebView2 to watch.
    """
    form = getattr(window, "native", None)
    control = getattr(getattr(form, "browser", None), "webview", None)
    if form is None or control is None:
        return False
    try:
        from System import Action

        def failed(_sender, args) -> None:
            if str(args.ProcessFailedKind) not in PAGE_CRASH_KINDS:
                return
            on_crash()
            try:
                control.CoreWebView2.Reload()
            except Exception:
                pass

        def attach() -> None:
            control.CoreWebView2.ProcessFailed += failed

        form.Invoke(Action(attach))
        return True
    except Exception:
        return False


def warm_hidden_webview(window: webview.Window) -> bool:
    """Let the page render while the app still sits hidden in the tray.

    Started hidden, WebView2 renders nothing until the window is first shown, so the first summon
    had to do all of it at once (measured: about half a second before the first frame, then a
    stuttering reveal); every later summon is smooth, because after one show/hide WebView2 keeps
    the page "visible" behind the hidden window. This puts the page in that same state from the
    start, by marking the WebView2 controller visible without showing the window. The page keeps
    its animations paused meanwhile (clipdeck:sleep), so it costs nothing while it waits.
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
