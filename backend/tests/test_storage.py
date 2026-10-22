from __future__ import annotations

import json
from pathlib import Path

from backend.app.models import HistoryRecord, SettingsState, ShortcutBindings
from backend.app import storage as storage_module
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


def test_image_uris_resolve_back_to_unc_and_percent_named_folders() -> None:
    for original in (r"\\server\share\cc\images\x.png", r"D:\100%41 dir\images\a b.png"):
        assert storage_module.resolve_local_path(Path(original).as_uri()) == Path(original)


def test_prune_keeps_images_in_a_folder_whose_name_contains_percent(tmp_path: Path) -> None:
    storage = AppStorage(base_path=tmp_path / "100%41 data")
    kept = storage.save_image_bytes(record_id="record-1", image_bytes=b"png")

    storage.prune_unreferenced_images([kept])

    assert (storage.images_path / "record-1.png").exists()


def sample_settings(storage_path: Path) -> SettingsState:
    return SettingsState(
        launch_on_startup=False,
        close_to_tray=True,
        follow_system_theme=True,
        record_text=True,
        record_rich_text=True,
        history_limit=123,
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
    assert loaded_settings.history_limit == 123
    assert loaded_settings.record_files is True
    assert "historyLimit" in loaded_settings.to_dict()
    assert "textHistoryLimit" not in loaded_settings.to_dict()
    assert "imageHistoryLimit" not in loaded_settings.to_dict()
    assert loaded_records[0].summary == "stored text"
    assert loaded_records[0].plain_text == "stored text"


def test_storage_loads_legacy_settings_with_default_history_limit(tmp_path: Path) -> None:
    storage = AppStorage(base_path=tmp_path / "data")
    storage.settings_path.write_text(
        json.dumps(
            {
                "launchOnStartup": True,
                "closeToTray": True,
                "followSystemTheme": True,
                "recordText": True,
                "recordRichText": True,
                "textHistoryLimit": 1000,
                "imageHistoryLimit": 100,
                "recordImages": True,
                "recordFiles": True,
                "storagePath": str(storage.base_path),
                "shortcuts": {
                    "togglePanel": "Alt + Space",
                    "primaryAction": "Enter",
                    "pastePlainText": "Ctrl + Shift + V",
                    "togglePin": "Ctrl + P",
                    "deleteRecord": "Delete",
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    loaded_settings = storage.load_settings()

    assert loaded_settings.history_limit == 25


def test_corrupt_history_is_quarantined_and_loads_empty(tmp_path: Path) -> None:
    storage = AppStorage(base_path=tmp_path / "data")
    storage.history_path.write_text("[{\"id\": \"record-1\", ", encoding="utf-8")

    assert storage.load_records() == []
    assert not storage.history_path.exists()
    quarantined = list(storage.base_path.glob("history.corrupt-*.json"))
    assert len(quarantined) == 1
    assert quarantined[0].read_text(encoding="utf-8") == "[{\"id\": \"record-1\", "


def test_malformed_history_shape_is_quarantined(tmp_path: Path) -> None:
    storage = AppStorage(base_path=tmp_path / "data")
    storage.history_path.write_text(json.dumps({"not": "a list"}), encoding="utf-8")

    assert storage.load_records() == []
    assert len(list(storage.base_path.glob("history.corrupt-*.json"))) == 1


def test_corrupt_settings_are_quarantined_and_fall_back_to_defaults(tmp_path: Path) -> None:
    storage = AppStorage(base_path=tmp_path / "data")
    storage.settings_path.write_text("{not json", encoding="utf-8")

    loaded = storage.load_settings()

    assert loaded.history_limit == 25
    assert loaded.storage_path == str(storage.base_path)
    assert not storage.settings_path.exists()
    assert len(list(storage.base_path.glob("settings.corrupt-*.json"))) == 1


def test_settings_missing_required_keys_fall_back_to_defaults(tmp_path: Path) -> None:
    storage = AppStorage(base_path=tmp_path / "data")
    storage.settings_path.write_text(json.dumps({"launchOnStartup": False}), encoding="utf-8")

    loaded = storage.load_settings()

    assert loaded.launch_on_startup is True
    assert len(list(storage.base_path.glob("settings.corrupt-*.json"))) == 1


def test_repeated_corruption_keeps_each_quarantined_copy(tmp_path: Path) -> None:
    storage = AppStorage(base_path=tmp_path / "data")
    for _ in range(2):
        storage.history_path.write_text("broken", encoding="utf-8")
        storage.load_records()

    assert len(list(storage.base_path.glob("history.corrupt-*.json"))) == 2


def test_failed_atomic_write_keeps_previous_file_intact(tmp_path: Path, monkeypatch) -> None:
    storage = AppStorage(base_path=tmp_path / "data")
    storage.save_records([sample_record()])

    def failing_replace(source, target):
        raise OSError("simulated crash before replace")

    monkeypatch.setattr(storage_module.os, "replace", failing_replace)
    try:
        storage.save_records([])
    except OSError:
        pass
    else:  # pragma: no cover - guard
        raise AssertionError("expected simulated failure")
    monkeypatch.undo()

    assert [record.summary for record in storage.load_records()] == ["stored text"]
    assert [path.name for path in storage.base_path.iterdir() if path.suffix == ".tmp"] == []


def test_atomic_writes_leave_no_temp_files(tmp_path: Path) -> None:
    storage = AppStorage(base_path=tmp_path / "data")
    storage.save_settings(sample_settings(storage.base_path))
    storage.save_records([sample_record()])

    assert sorted(path.name for path in storage.base_path.iterdir() if path.is_file()) == [
        "history.json",
        "settings.json",
    ]
