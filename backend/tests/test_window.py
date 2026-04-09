from pathlib import Path
from types import SimpleNamespace
from types import FunctionType

from backend.app.tray import menu_labels
from backend.app.window import AppWindowController
from backend.app.window import resolve_runtime_mode
from backend.app.window import resolve_frontend_entry
from backend.app.window import set_window_on_top

TEST_PROJECT_ROOT = Path("C:/workspace/CipherClip")


def test_resolve_frontend_entry_prefers_dev_server_and_falls_back_to_dist():
    project_root = TEST_PROJECT_ROOT

    dev_entry = resolve_frontend_entry(project_root=project_root, dev_mode=True)
    prod_entry = resolve_frontend_entry(project_root=project_root, dev_mode=False)

    assert dev_entry == "http://127.0.0.1:5173"
    assert str(prod_entry).endswith("frontend/dist/index.html")


def test_menu_labels_reflect_recording_state():
    active_labels = menu_labels(is_recording_paused=False)
    paused_labels = menu_labels(is_recording_paused=True)

    assert active_labels[1] == "暂停记录"
    assert paused_labels[1] == "继续记录"


def test_runtime_mode_defaults_to_static_build_when_dist_exists(tmp_path: Path):
    project_root = tmp_path
    dist_index = project_root / "frontend" / "dist" / "index.html"
    dist_index.parent.mkdir(parents=True)
    dist_index.write_text("<!doctype html>", encoding="utf-8")

    dev_mode, debug_mode = resolve_runtime_mode(project_root=project_root, env={})

    assert dev_mode is False
    assert debug_mode is False


def test_runtime_mode_can_be_forced_to_dev_and_debug():
    project_root = TEST_PROJECT_ROOT

    dev_mode, debug_mode = resolve_runtime_mode(
        project_root=project_root,
        env={"CLIPBOARD_DEV": "1", "CLIPBOARD_DEBUG": "1"},
    )

    assert dev_mode is True
    assert debug_mode is True


def test_window_controller_hides_instead_of_closing_when_close_to_tray_is_enabled():
    bridge = SimpleNamespace(bind_hide_window=lambda _callback: None)
    hidden = {"value": False}
    controller = AppWindowController(
        project_root=TEST_PROJECT_ROOT,
        bridge=bridge,
        snapshot_provider=lambda: {},
        dev_mode=False,
        close_to_tray_provider=lambda: True,
    )
    controller.window = SimpleNamespace(hide=lambda: hidden.__setitem__("value", True))

    should_cancel = controller._handle_closing()

    assert should_cancel is False
    assert hidden["value"] is True


def test_window_controller_can_start_hidden_and_toggle_visibility():
    bridge = SimpleNamespace(bind_hide_window=lambda _callback: None)
    calls = {
        "show": 0,
        "hide": 0,
        "restore": 0,
    }
    controller = AppWindowController(
        project_root=TEST_PROJECT_ROOT,
        bridge=bridge,
        snapshot_provider=lambda: {},
        dev_mode=False,
        start_hidden=True,
        close_to_tray_provider=lambda: True,
    )
    controller.window = SimpleNamespace(
        show=lambda: calls.__setitem__("show", calls["show"] + 1),
        hide=lambda: calls.__setitem__("hide", calls["hide"] + 1),
        restore=lambda: calls.__setitem__("restore", calls["restore"] + 1),
    )

    assert controller.is_hidden is True

    controller.toggle_visibility()
    controller.toggle_visibility()

    assert calls["show"] == 1
    assert calls["restore"] == 1
    assert calls["hide"] == 1


def test_window_controller_can_toggle_always_on_top_for_current_run():
    bridge = SimpleNamespace(
        _bind_hide_window=lambda _callback: None,
        _bind_pick_storage_path=lambda _callback: None,
    )
    topmost = {"value": False}
    set_on_top_calls: list[bool] = []
    controller = AppWindowController(
        project_root=TEST_PROJECT_ROOT,
        bridge=bridge,
        snapshot_provider=lambda: {},
        dev_mode=False,
        set_on_top_callback=lambda _window, enabled: (set_on_top_calls.append(enabled), topmost.__setitem__("value", enabled)),
    )
    controller.window = SimpleNamespace()

    assert controller.is_always_on_top is False

    controller.toggle_always_on_top()

    assert controller.is_always_on_top is True
    assert topmost["value"] is True
    assert set_on_top_calls == [True]


def test_window_controller_reapplies_always_on_top_when_showing_window():
    bridge = SimpleNamespace(
        _bind_hide_window=lambda _callback: None,
        _bind_pick_storage_path=lambda _callback: None,
    )
    set_on_top_calls: list[bool] = []
    calls = {
        "show": 0,
        "restore": 0,
    }
    controller = AppWindowController(
        project_root=TEST_PROJECT_ROOT,
        bridge=bridge,
        snapshot_provider=lambda: {},
        dev_mode=False,
        set_on_top_callback=lambda _window, enabled: set_on_top_calls.append(enabled),
    )
    controller.window = SimpleNamespace(
        show=lambda: calls.__setitem__("show", calls["show"] + 1),
        restore=lambda: calls.__setitem__("restore", calls["restore"] + 1),
    )

    controller.toggle_always_on_top()
    controller.show()

    assert calls["show"] == 1
    assert calls["restore"] == 1
    assert set_on_top_calls == [True, True]


def test_set_window_on_top_updates_native_topmost_on_ui_thread():
    invoke_calls = {"count": 0}

    class NativeWindow:
        def __init__(self) -> None:
            self.TopMost = False
            self.InvokeRequired = True

        def Invoke(self, callback):
            if isinstance(callback, FunctionType):
                raise TypeError("Invoke must receive a .NET delegate, not a raw Python function")
            invoke_calls["count"] += 1
            callback()

    window = SimpleNamespace(native=NativeWindow())

    set_window_on_top(window, True)

    assert window.native.TopMost is True
    assert invoke_calls["count"] == 1
