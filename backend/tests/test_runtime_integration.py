from __future__ import annotations

from pathlib import Path

from backend.app.hotkeys import parse_shortcut_binding
from backend.app.runtime import resolve_default_storage_path
from backend.app.runtime import resolve_webview_data_path
from backend.app.runtime import resolve_startup_command
from backend.app.runtime_integration import RuntimeIntegrationController

TEST_PROJECT_ROOT = Path("C:/workspace/ClipDeck")
TEST_LOCAL_APP_DATA = Path("C:/Users/TestUser/AppData/Local")


class DummyStartupManager:
    def __init__(self) -> None:
        self.calls: list[tuple[bool, str]] = []

    def set_enabled(self, enabled: bool, command: str) -> None:
        self.calls.append((enabled, command))


class DummyHotkeyManager:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def update_toggle_panel(self, shortcut: str, callback) -> None:
        self.calls.append((shortcut, callback))


def test_parse_shortcut_binding_maps_supported_modifier_shortcuts() -> None:
    assert parse_shortcut_binding("Alt + Space") == (0x0001, 0x20)
    assert parse_shortcut_binding("Ctrl + Shift + V") == (0x0002 | 0x0004, 0x56)
    assert parse_shortcut_binding("not a shortcut") is None


def test_resolve_startup_command_uses_pythonw_for_source_runtime() -> None:
    command = resolve_startup_command(
        project_root=TEST_PROJECT_ROOT,
        executable=Path("C:/Python312/python.exe"),
        frozen=False,
    )

    assert "pythonw.exe" in command.lower()
    assert "backend\\main.py" in command
    assert "--start-hidden" in command


def test_resolve_startup_command_uses_executable_for_frozen_runtime() -> None:
    command = resolve_startup_command(
        project_root=TEST_PROJECT_ROOT,
        executable=Path("C:/Program Files/ClipDeck/ClipDeck.exe"),
        frozen=True,
    )

    assert command == '"C:\\Program Files\\ClipDeck\\ClipDeck.exe" --start-hidden'


def test_webview_data_lives_in_a_fixed_folder_under_local_app_data() -> None:
    first = resolve_webview_data_path(env={"LOCALAPPDATA": str(TEST_LOCAL_APP_DATA)})
    second = resolve_webview_data_path(env={"LOCALAPPDATA": str(TEST_LOCAL_APP_DATA)})

    assert first == second == TEST_LOCAL_APP_DATA / "ClipDeck" / "WebView2"


def test_webview_data_from_before_the_rename_is_moved_over_once(tmp_path: Path) -> None:
    (tmp_path / "CipherClip" / "WebView2").mkdir(parents=True)
    (tmp_path / "CipherClip" / "WebView2" / "cache").write_text("kept")

    path = resolve_webview_data_path(env={"LOCALAPPDATA": str(tmp_path)})

    assert path == tmp_path / "ClipDeck" / "WebView2"
    assert (path / "cache").read_text() == "kept"
    assert not (tmp_path / "CipherClip").exists()

    # A folder that comes back later (an old copy still running) is left alone.
    (tmp_path / "CipherClip").mkdir()
    resolve_webview_data_path(env={"LOCALAPPDATA": str(tmp_path)})
    assert (tmp_path / "CipherClip").exists() and (path / "cache").exists()


def test_resolve_default_storage_path_uses_project_data_for_source_runtime() -> None:
    storage_path = resolve_default_storage_path(
        project_root=TEST_PROJECT_ROOT,
        frozen=False,
        env={"LOCALAPPDATA": str(TEST_LOCAL_APP_DATA)},
    )

    assert storage_path == TEST_PROJECT_ROOT / "data"


def test_resolve_default_storage_path_uses_executable_directory_for_frozen_runtime() -> None:
    storage_path = resolve_default_storage_path(
        project_root=TEST_PROJECT_ROOT,
        executable=Path("C:/Program Files/ClipDeck/ClipDeck.exe"),
        frozen=True,
        env={"LOCALAPPDATA": str(TEST_LOCAL_APP_DATA)},
    )

    assert storage_path == Path("C:/Program Files/ClipDeck/data")


def test_runtime_integration_syncs_startup_and_global_toggle_shortcut_without_repeating() -> None:
    startup_manager = DummyStartupManager()
    hotkey_manager = DummyHotkeyManager()
    toggles = {"count": 0}
    controller = RuntimeIntegrationController(
        startup_manager=startup_manager,
        hotkey_manager=hotkey_manager,
        startup_command='"C:\\Program Files\\ClipDeck\\ClipDeck.exe" --start-hidden',
        toggle_window=lambda: toggles.__setitem__("count", toggles["count"] + 1),
    )
    snapshot = {
        "settings": {
            "launchOnStartup": True,
            "shortcuts": {
                "togglePanel": "Alt + Space",
            },
        }
    }

    controller.sync(snapshot)
    controller.sync(snapshot)

    assert startup_manager.calls == [(
        True,
        '"C:\\Program Files\\ClipDeck\\ClipDeck.exe" --start-hidden',
    )]
    assert len(hotkey_manager.calls) == 1
    hotkey_manager.calls[0][1]()
    assert toggles["count"] == 1
