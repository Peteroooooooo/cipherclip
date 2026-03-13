from __future__ import annotations

from pathlib import Path

from backend.app.bridge import AppBridge
from backend.app.clipboard import ClipboardCapture
from backend.app.state import AppState
from backend.app.storage import AppStorage


def build_bridge(tmp_path: Path) -> AppBridge:
    state = AppState(storage=AppStorage(base_path=tmp_path / "data"))
    return AppBridge(state)


def test_bridge_returns_frontend_friendly_snapshot_shape(tmp_path: Path) -> None:
    bridge = build_bridge(tmp_path)

    snapshot = bridge.get_app_state()

    assert set(snapshot) == {
        "view",
        "isRecordingPaused",
        "pinnedRecords",
        "recentRecords",
        "settings",
        "toast",
    }
    assert snapshot["settings"]["shortcuts"]["togglePanel"] == "Alt + Space"


def test_bridge_does_not_expose_internal_state_as_public_js_api_attribute(tmp_path: Path) -> None:
    bridge = build_bridge(tmp_path)

    public_attributes = [name for name in dir(bridge) if not name.startswith("_")]

    assert "state" not in public_attributes


def test_bridge_methods_proxy_real_record_updates(tmp_path: Path) -> None:
    bridge = build_bridge(tmp_path)

    created = bridge.ingest_clipboard_capture(
        {
            "text": "bridge text",
            "sourceApp": "VS Code",
        },
        "2026-03-11T11:00:00",
    )
    record_id = created["recentRecords"][0]["id"]
    settings_snapshot = bridge.set_view("settings")
    updated_snapshot = bridge.toggle_pin(record_id)
    cleared_recent_snapshot = bridge.clear_unpinned_history()
    cleared_snapshot = bridge.clear_all_history()

    assert settings_snapshot["view"] == "settings"
    assert updated_snapshot["pinnedRecords"][0]["summary"] == "bridge text"
    assert cleared_recent_snapshot["pinnedRecords"][0]["summary"] == "bridge text"
    assert cleared_recent_snapshot["recentRecords"] == []
    assert cleared_snapshot["pinnedRecords"] == []
    assert cleared_snapshot["recentRecords"] == []


def test_bridge_copy_record_proxies_without_hiding_window(tmp_path: Path) -> None:
    state = AppState(storage=AppStorage(base_path=tmp_path / "data"))
    bridge = AppBridge(state)
    hide_calls = {"count": 0}
    bridge._bind_hide_window(lambda: hide_calls.__setitem__("count", hide_calls["count"] + 1))

    created = state.ingest_capture(
        ClipboardCapture(text="copy bridge", source_app="VS Code"),
        captured_at="2026-03-11T11:05:00",
    )
    record_id = created["recentRecords"][0]["id"]

    bridge.copy_record(record_id)

    assert hide_calls["count"] == 0


def test_bridge_can_undo_deleted_records(tmp_path: Path) -> None:
    state = AppState(storage=AppStorage(base_path=tmp_path / "data"))
    bridge = AppBridge(state)
    created = state.ingest_capture(
        ClipboardCapture(text="delete me", source_app="Word"),
        captured_at="2026-03-11T11:10:00",
    )

    record_id = created["recentRecords"][0]["id"]
    deleted = bridge.delete_record(record_id)
    restored = bridge.undo_delete()

    assert deleted["toast"]["actionKind"] == "undo_delete"
    assert restored["recentRecords"][0]["summary"] == "delete me"


def test_bridge_can_delegate_storage_path_picking(tmp_path: Path) -> None:
    bridge = build_bridge(tmp_path)
    bridge._bind_pick_storage_path(lambda current_path: f"{current_path}\\next")

    selected_path = bridge.pick_storage_path("D:\\Desktop\\clipboard\\data")

    assert selected_path == "D:\\Desktop\\clipboard\\data\\next"


def test_bridge_can_delegate_clear_all_history_confirmation(tmp_path: Path) -> None:
    bridge = build_bridge(tmp_path)
    bridge._bind_confirm_clear_all_history(lambda: False)

    assert bridge.confirm_clear_all_history() is False
