from __future__ import annotations

from pathlib import Path

from backend.app.models import HistoryRecord, SettingsState, ShortcutBindings
from backend.app.storage import AppStorage


def sample_record() -> HistoryRecord:
    return HistoryRecord(
        id="record-1",
        type="text",
        summary="stored text",
        detail="stored text",
        meta="Text",
        source_app="VS Code",
        source_glyph="VS",
        pinned=False,
        created_at="2026-03-11T12:00:00",
        updated_at="2026-03-11T12:00:00",
        content_hash="abc123",
        plain_text="stored text",
    )


def sample_settings(storage_path: Path) -> SettingsState:
    return SettingsState(
        launch_on_startup=False,
        close_to_tray=True,
        follow_system_theme=True,
        record_text=True,
        record_rich_text=True,
        text_history_limit=123,
        image_history_limit=45,
        record_images=True,
        record_files=True,
        storage_path=str(storage_path),
        shortcuts=ShortcutBindings(
            toggle_panel="Alt + Space",
            primary_action="Enter",
            paste_plain_text="Ctrl + Shift + V",
            toggle_pin="Ctrl + P",
            delete_record="Delete",
        ),
    )


def test_storage_round_trips_settings_and_records(tmp_path: Path) -> None:
    storage = AppStorage(base_path=tmp_path / "data")
    settings = sample_settings(storage.base_path)
    records = [sample_record()]

    storage.save_settings(settings)
    storage.save_records(records)

    loaded_settings = storage.load_settings()
    loaded_records = storage.load_records()

    assert loaded_settings.record_text is True
    assert loaded_settings.record_rich_text is True
    assert loaded_settings.text_history_limit == 123
    assert loaded_settings.record_files is True
    assert loaded_records[0].summary == "stored text"
    assert loaded_records[0].plain_text == "stored text"
