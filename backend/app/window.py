from __future__ import annotations

import json
import os
from pathlib import Path

import webview

from .bridge import AppBridge


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
    ) -> None:
        self.project_root = project_root
        self.bridge = bridge
        self.snapshot_provider = snapshot_provider
        self.dev_mode = dev_mode
        self.start_hidden = start_hidden
        self.close_to_tray_provider = close_to_tray_provider
        self.set_on_top_callback = set_window_on_top if set_on_top_callback is None else set_on_top_callback
        self.window: webview.Window | None = None
        self._is_loaded = False
        self._allow_close = False
        self._is_hidden = start_hidden
        self._is_always_on_top = False

    def create(self) -> webview.Window:
        entry = resolve_frontend_entry(project_root=self.project_root, dev_mode=self.dev_mode)
        url = entry if isinstance(entry, str) and entry.startswith("http") else Path(str(entry)).resolve().as_uri()

        self.window = webview.create_window(
            title="Clipboard History",
            url=url,
            js_api=self.bridge,
            width=540,
            height=760,
            min_size=(420, 560),
            hidden=self.start_hidden,
            on_top=self._is_always_on_top,
            text_select=True,
        )
        self.window.events.loaded += self._handle_loaded
        self.window.events.closing += self._handle_closing
        self.bridge._bind_hide_window(self.hide)
        self.bridge._bind_pick_storage_path(self.pick_storage_path)
        self.bridge._bind_toggle_always_on_top(self.toggle_always_on_top)
        self.bridge._bind_is_always_on_top(lambda: self.is_always_on_top)
        return self.window

    def show(self) -> None:
        if self.window is None:
            return
        self.window.show()
        self.window.restore()
        self._apply_always_on_top()
        self._is_hidden = False

    def hide(self) -> None:
        if self.window is None:
            return
        self.window.hide()
        self._is_hidden = True

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

    def _handle_loaded(self) -> None:
        self._is_loaded = True
        self.dispatch_snapshot(self.snapshot_provider())

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
        selection = self.window.create_file_dialog(dialog_type=dialog_type, directory=current_path or "")
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
