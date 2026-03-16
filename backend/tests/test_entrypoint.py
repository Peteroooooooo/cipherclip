from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import backend.main as backend_main
from backend.main import _toggle_window_from_shortcut


class DummySingleInstanceManager:
    def __init__(self, *, primary: bool) -> None:
        self.primary = primary
        self.calls: list[str] = []

    def acquire_primary(self) -> bool:
        self.calls.append("acquire_primary")
        return self.primary

    def signal_primary(self) -> bool:
        self.calls.append("signal_primary")
        return True

    def start_activation_listener(self, _callback) -> None:
        self.calls.append("start_activation_listener")

    def stop(self) -> None:
        self.calls.append("stop")


def test_backend_main_script_can_be_loaded_from_project_root() -> None:
    project_root = Path(__file__).resolve().parents[2]

    result = subprocess.run(
        [
            sys.executable,
            "backend/main.py",
        ],
        cwd=project_root,
        env={"CLIPBOARD_TEST_MODE": "1"},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_resolve_project_root_prefers_meipass_in_frozen_runtime(tmp_path: Path) -> None:
    bundle_root = tmp_path / "_internal"
    frontend_dist = bundle_root / "frontend" / "dist"
    frontend_dist.mkdir(parents=True)
    (frontend_dist / "index.html").write_text("<!doctype html>", encoding="utf-8")

    project_root = backend_main.resolve_project_root(
        current_file=tmp_path / "main.py",
        frozen=True,
        meipass=bundle_root,
    )

    assert project_root == bundle_root


def test_toggle_window_from_shortcut_captures_only_when_showing() -> None:
    state = SimpleNamespace(
        captured=0,
        cleared=0,
        capture_paste_target=lambda: state.__setattr__("captured", state.captured + 1),
        clear_paste_target=lambda: state.__setattr__("cleared", state.cleared + 1),
    )
    window_controller = SimpleNamespace(
        is_hidden=True,
        toggle_visibility=lambda: None,
    )

    _toggle_window_from_shortcut(state=state, window_controller=window_controller)
    window_controller.is_hidden = False
    _toggle_window_from_shortcut(state=state, window_controller=window_controller)

    assert state.captured == 1
    assert state.cleared == 1


def test_main_signals_existing_instance_and_skips_bootstrap(monkeypatch) -> None:
    manager = DummySingleInstanceManager(primary=False)

    monkeypatch.delenv("CLIPBOARD_TEST_MODE", raising=False)
    monkeypatch.setattr(backend_main, "create_single_instance_manager", lambda: manager, raising=False)

    def fail_app_state():
        raise AssertionError("AppState should not be created for a secondary launch")

    monkeypatch.setattr(backend_main, "AppState", fail_app_state)

    backend_main.main([])

    assert manager.calls == [
        "acquire_primary",
        "signal_primary",
        "stop",
    ]


def test_main_hidden_secondary_launch_exits_without_signaling(monkeypatch) -> None:
    manager = DummySingleInstanceManager(primary=False)

    monkeypatch.delenv("CLIPBOARD_TEST_MODE", raising=False)
    monkeypatch.setattr(backend_main, "create_single_instance_manager", lambda: manager, raising=False)

    def fail_app_state():
        raise AssertionError("AppState should not be created for a secondary launch")

    monkeypatch.setattr(backend_main, "AppState", fail_app_state)

    backend_main.main([backend_main.START_HIDDEN_FLAG])

    assert manager.calls == [
        "acquire_primary",
        "stop",
    ]
