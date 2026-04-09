from __future__ import annotations

import os
import sys
from pathlib import Path


def resolve_project_root(
    *,
    current_file: str | Path | None = None,
    frozen: bool | None = None,
    meipass: str | Path | None = None,
) -> Path:
    frozen_runtime = bool(getattr(sys, "frozen", False)) if frozen is None else frozen

    if frozen_runtime:
        runtime_bundle_root = meipass if meipass is not None else getattr(sys, "_MEIPASS", None)
        if runtime_bundle_root is not None:
            return Path(runtime_bundle_root).resolve()

    return Path(current_file or __file__).resolve().parents[1]


PROJECT_ROOT = resolve_project_root(current_file=__file__)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import webview

from backend.app.bridge import AppBridge
from backend.app.clipboard import ClipboardMonitor
from backend.app.clipboard import WindowsClipboardReader
from backend.app.hotkeys import NoopGlobalHotkeyManager
from backend.app.hotkeys import WindowsGlobalHotkeyManager
from backend.app.runtime import resolve_startup_command
from backend.app.runtime import START_HIDDEN_FLAG
from backend.app.runtime_integration import NoopStartupManager
from backend.app.runtime_integration import RuntimeIntegrationController
from backend.app.runtime_integration import WindowsStartupManager
from backend.app.single_instance import NoopSingleInstanceManager
from backend.app.single_instance import WindowsSingleInstanceManager
from backend.app.state import AppState
from backend.app.tray import TrayController
from backend.app.tray import confirm_clear_all_history
from backend.app.window import AppWindowController
from backend.app.window import resolve_runtime_mode


def main(argv: list[str] | None = None) -> None:
    project_root = PROJECT_ROOT
    dev_mode, debug_mode = resolve_runtime_mode(project_root=project_root)
    launch_args = sys.argv[1:] if argv is None else argv
    start_hidden = START_HIDDEN_FLAG in launch_args

    if os.getenv("CLIPBOARD_TEST_MODE") == "1":
        return

    single_instance_manager = create_single_instance_manager()
    if not single_instance_manager.acquire_primary():
        if not start_hidden:
            single_instance_manager.signal_primary()
        single_instance_manager.stop()
        return

    state = AppState()
    bridge = AppBridge(state)
    monitor = ClipboardMonitor(
        reader=WindowsClipboardReader(),
        on_capture=state.ingest_capture,
        is_paused=lambda: state.is_recording_paused,
    )
    window_controller = AppWindowController(
        project_root=project_root,
        bridge=bridge,
        snapshot_provider=bridge.get_app_state,
        dev_mode=dev_mode,
        start_hidden=start_hidden,
        close_to_tray_provider=lambda: state.settings.close_to_tray,
    )
    window_controller.create()
    single_instance_manager.start_activation_listener(window_controller.show)
    bridge._bind_confirm_clear_all_history(confirm_clear_all_history)
    startup_manager = WindowsStartupManager() if os.name == "nt" else NoopStartupManager()
    hotkey_manager = WindowsGlobalHotkeyManager() if os.name == "nt" else NoopGlobalHotkeyManager()
    runtime_integration = RuntimeIntegrationController(
        startup_manager=startup_manager,
        hotkey_manager=hotkey_manager,
        startup_command=resolve_startup_command(project_root=project_root),
        toggle_window=lambda: _toggle_window_from_shortcut(state=state, window_controller=window_controller),
    )
    state.subscribe(lambda _snapshot: window_controller.dispatch_snapshot(bridge.get_app_state()))
    state.subscribe(runtime_integration.sync)
    runtime_integration.sync(state.snapshot())

    tray = TrayController(
        state=state,
        show_history=window_controller.show,
        show_settings=window_controller.show,
        exit_app=lambda: _shutdown(
            tray=None,
            window_controller=window_controller,
            monitor=monitor,
            runtime_integration=runtime_integration,
            single_instance_manager=single_instance_manager,
        ),
    )
    tray.exit_app = lambda: _shutdown(
        tray=tray,
        window_controller=window_controller,
        monitor=monitor,
        runtime_integration=runtime_integration,
        single_instance_manager=single_instance_manager,
    )
    tray.run()
    monitor.start()

    webview.start(debug=debug_mode)


def _shutdown(
    *,
    tray: TrayController | None,
    window_controller: AppWindowController,
    monitor: ClipboardMonitor | None,
    runtime_integration: RuntimeIntegrationController | None,
    single_instance_manager: NoopSingleInstanceManager | WindowsSingleInstanceManager | None,
) -> None:
    if tray is not None:
        tray.stop()
    if monitor is not None:
        monitor.stop()
    if runtime_integration is not None:
        runtime_integration.stop()
    if single_instance_manager is not None:
        single_instance_manager.stop()
    window_controller.destroy()


def _toggle_window_from_shortcut(*, state: AppState, window_controller: AppWindowController) -> None:
    if window_controller.is_hidden:
        state.capture_paste_target()
    else:
        state.clear_paste_target()
    window_controller.toggle_visibility()


def create_single_instance_manager() -> NoopSingleInstanceManager | WindowsSingleInstanceManager:
    if os.name == "nt":
        return WindowsSingleInstanceManager()
    return NoopSingleInstanceManager()


if __name__ == "__main__":
    main()
