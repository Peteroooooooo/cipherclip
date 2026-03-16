from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from backend.app.clipboard import ClipboardCapture
from backend.app.models import HistoryRecord
from backend.app.state import AppState
from backend.app.storage import AppStorage


class DummyClipboardService:
    def __init__(self) -> None:
        self.writes: list[tuple[str, bool]] = []
        self.paste_shortcuts = 0
        self.captured_targets = 0
        self.restored_targets = 0
        self.target_available = False

    def write_record(self, record, *, as_plain_text: bool) -> None:
        self.writes.append((record.id, as_plain_text))

    def send_paste_shortcut(self) -> None:
        self.paste_shortcuts += 1

    def capture_paste_target(self) -> None:
        self.captured_targets += 1
        self.target_available = True

    def has_paste_target(self) -> bool:
        return self.target_available

    def restore_paste_target(self) -> bool:
        if not self.target_available:
            return False
        self.restored_targets += 1
        self.target_available = False
        return True


def build_state(tmp_path: Path, *, clipboard_service: DummyClipboardService | None = None) -> AppState:
    storage = AppStorage(base_path=tmp_path / "data")
    return AppState(storage=storage, clipboard_service=clipboard_service)


def image_uri_to_path(image_uri: str) -> Path:
    parsed = urlparse(image_uri)
    assert parsed.scheme == "file"
    return Path(url2pathname(unquote(parsed.path)))


def sample_record_for_summary(summary: str, *, captured_at: str) -> HistoryRecord:
    return HistoryRecord(
        id=f"record-{summary.replace(' ', '-')}",
        type="text",
        summary=summary,
        detail=summary,
        meta="Text",
        source_app="VS Code",
        source_glyph="VS",
        pinned=False,
        created_at=captured_at,
        updated_at=captured_at,
        content_hash=f"hash-{summary}",
        plain_text=summary,
    )


def test_snapshot_loads_empty_persistent_state_by_default(tmp_path: Path) -> None:
    state = build_state(tmp_path)

    snapshot = state.snapshot()

    assert snapshot["view"] == "panel"
    assert snapshot["isRecordingPaused"] is False
    assert snapshot["pinnedRecords"] == []
    assert snapshot["recentRecords"] == []


def test_ingest_capture_keeps_pinned_records_and_latest_unpinned_limit(tmp_path: Path) -> None:
    state = build_state(tmp_path)
    state.settings.history_limit = 3

    first = state.ingest_capture(
        ClipboardCapture(text="alpha", source_app="VS Code"),
        captured_at="2026-03-11T10:00:00",
    )
    record_id = first["recentRecords"][0]["id"]

    state.toggle_pin(record_id)
    state.ingest_capture(
        ClipboardCapture(text="beta", source_app="VS Code"),
        captured_at="2026-03-11T10:01:00",
    )
    state.ingest_capture(
        ClipboardCapture(rich_text="<b>gamma</b>", text="gamma", source_app="Word"),
        captured_at="2026-03-11T10:02:00",
    )
    state.ingest_capture(
        ClipboardCapture(file_paths=["D:\\Docs\\spec.docx"], source_app="Explorer"),
        captured_at="2026-03-11T10:03:00",
    )
    state.ingest_capture(
        ClipboardCapture(image_bytes=b"image-1", image_width=640, image_height=480, source_app="Snipping Tool"),
        captured_at="2026-03-11T10:04:00",
    )
    latest = state.ingest_capture(
        ClipboardCapture(image_bytes=b"image-2", image_width=800, image_height=600, source_app="Snipping Tool"),
        captured_at="2026-03-11T10:05:00",
    )

    assert [record["type"] for record in latest["pinnedRecords"]] == ["text"]
    assert [record["summary"] for record in latest["recentRecords"]] == [
        "Image 800 x 600",
        "Image 640 x 480",
        "spec.docx",
    ]


def test_delete_undo_and_restart_restore_persisted_history(tmp_path: Path) -> None:
    state = build_state(tmp_path)

    created = state.ingest_capture(
        ClipboardCapture(text="persist me", source_app="PowerShell"),
        captured_at="2026-03-11T10:10:00",
    )
    record_id = created["recentRecords"][0]["id"]

    deleted = state.delete_record(record_id)
    restored = state.undo_delete()
    restarted = AppState(storage=AppStorage(base_path=tmp_path / "data"))

    assert deleted["recentRecords"] == []
    assert restored["recentRecords"][0]["summary"] == "persist me"
    assert restarted.snapshot()["recentRecords"][0]["summary"] == "persist me"


def test_save_settings_changes_capture_behavior_immediately(tmp_path: Path) -> None:
    state = build_state(tmp_path)
    settings = state.settings.to_dict()
    settings["recordImages"] = False
    settings["historyLimit"] = 1

    state.save_settings(settings, pause_recording=False)
    skipped = state.ingest_capture(
        ClipboardCapture(image_bytes=b"image", image_width=100, image_height=100, source_app="Snipping Tool"),
        captured_at="2026-03-11T10:11:00",
    )
    latest = state.ingest_capture(
        ClipboardCapture(text="keep latest", source_app="VS Code"),
        captured_at="2026-03-11T10:12:00",
    )
    state.ingest_capture(
        ClipboardCapture(text="drop older", source_app="VS Code"),
        captured_at="2026-03-11T10:13:00",
    )

    assert skipped["recentRecords"] == []
    assert latest["recentRecords"][0]["summary"] == "keep latest"
    assert [record["summary"] for record in state.snapshot()["recentRecords"]] == ["drop older"]


def test_primary_action_and_plain_text_paste_restore_hotkey_target(tmp_path: Path) -> None:
    clipboard_service = DummyClipboardService()
    state = build_state(tmp_path, clipboard_service=clipboard_service)
    created = state.ingest_capture(
        ClipboardCapture(
            text="hello world",
            rich_text="<p>hello world</p>",
            source_app="Word",
        ),
        captured_at="2026-03-11T10:14:00",
    )
    record_id = created["recentRecords"][0]["id"]

    state.capture_paste_target()
    state.trigger_primary_action(record_id)
    state.capture_paste_target()
    state.paste_plain_text(record_id)

    assert clipboard_service.writes == [
        (record_id, False),
        (record_id, True),
    ]
    assert clipboard_service.captured_targets == 2
    assert clipboard_service.restored_targets == 2
    assert clipboard_service.paste_shortcuts == 2


def test_copy_record_keeps_copy_only_behavior_without_pasting(tmp_path: Path) -> None:
    clipboard_service = DummyClipboardService()
    state = build_state(tmp_path, clipboard_service=clipboard_service)
    created = state.ingest_capture(
        ClipboardCapture(text="copy me", source_app="VS Code"),
        captured_at="2026-03-11T10:14:30",
    )
    record_id = created["recentRecords"][0]["id"]

    state.capture_paste_target()
    state.copy_record(record_id)

    assert clipboard_service.writes == [(record_id, False)]
    assert clipboard_service.captured_targets == 1
    assert clipboard_service.restored_targets == 0
    assert clipboard_service.paste_shortcuts == 0


def test_clear_all_history_removes_pinned_and_recent_records(tmp_path: Path) -> None:
    state = build_state(tmp_path)

    created = state.ingest_capture(
        ClipboardCapture(text="keep me?", source_app="VS Code"),
        captured_at="2026-03-11T10:15:00",
    )
    record_id = created["recentRecords"][0]["id"]
    state.toggle_pin(record_id)
    state.ingest_capture(
        ClipboardCapture(text="drop me", source_app="Word"),
        captured_at="2026-03-11T10:16:00",
    )

    cleared = state.clear_all_history()

    assert cleared["pinnedRecords"] == []
    assert cleared["recentRecords"] == []
    assert cleared["toast"]["title"] == "已清空全部历史"


def test_clear_unpinned_history_keeps_pinned_records(tmp_path: Path) -> None:
    state = build_state(tmp_path)

    created = state.ingest_capture(
        ClipboardCapture(text="keep pinned", source_app="VS Code"),
        captured_at="2026-03-11T10:17:00",
    )
    pinned_id = created["recentRecords"][0]["id"]
    state.toggle_pin(pinned_id)
    state.ingest_capture(
        ClipboardCapture(text="drop recent", source_app="Word"),
        captured_at="2026-03-11T10:18:00",
    )

    cleared = state.clear_unpinned_history()

    assert [record["summary"] for record in cleared["pinnedRecords"]] == ["keep pinned"]
    assert cleared["recentRecords"] == []
    assert cleared["toast"]["title"] == "已清除未固定记录"


def test_switching_storage_path_merges_existing_target_history_and_migrates_images(tmp_path: Path) -> None:
    state = build_state(tmp_path)
    current = state.ingest_capture(
        ClipboardCapture(
            image_bytes=b"source-image",
            image_width=320,
            image_height=180,
            source_app="Snipping Tool",
        ),
        captured_at="2026-03-11T10:19:00",
    )
    current_image = current["recentRecords"][0]
    source_image_path = image_uri_to_path(str(current_image["imagePath"]))
    assert source_image_path.exists()

    target_storage = AppStorage(base_path=tmp_path / "external-data")
    target_state = AppState(storage=target_storage)
    target_state.ingest_capture(
        ClipboardCapture(text="target history", source_app="Word"),
        captured_at="2026-03-11T10:20:00",
    )

    settings = state.settings.to_dict()
    settings["storagePath"] = str(target_storage.base_path)

    switched = state.save_settings(settings, pause_recording=False)

    assert {record["summary"] for record in switched["recentRecords"]} == {"Image 320 x 180", "target history"}
    persisted_records = target_storage.load_records()
    assert {record.summary for record in persisted_records} == {"Image 320 x 180", "target history"}

    migrated_image = next(record for record in persisted_records if record.type == "image")
    assert migrated_image.image_path is not None
    migrated_image_path = image_uri_to_path(migrated_image.image_path)
    assert migrated_image_path.exists()
    assert migrated_image_path.parent == target_storage.images_path
    assert migrated_image_path.read_bytes() == b"source-image"


def test_delete_record_prunes_image_file_and_undo_restores_it(tmp_path: Path) -> None:
    state = build_state(tmp_path)
    created = state.ingest_capture(
        ClipboardCapture(
            image_bytes=b"delete-me",
            image_width=100,
            image_height=100,
            source_app="Snipping Tool",
        ),
        captured_at="2026-03-11T10:21:00",
    )
    record = created["recentRecords"][0]
    image_path = image_uri_to_path(str(record["imagePath"]))

    deleted = state.delete_record(str(record["id"]))

    assert deleted["recentRecords"] == []
    assert not image_path.exists()

    restored = state.undo_delete()

    assert restored["recentRecords"][0]["summary"] == "Image 100 x 100"
    assert image_path.exists()


def test_clear_all_history_prunes_image_files(tmp_path: Path) -> None:
    state = build_state(tmp_path)
    created = state.ingest_capture(
        ClipboardCapture(
            image_bytes=b"clear-all",
            image_width=120,
            image_height=90,
            source_app="Snipping Tool",
        ),
        captured_at="2026-03-11T10:22:00",
    )
    record = created["recentRecords"][0]
    image_path = image_uri_to_path(str(record["imagePath"]))
    assert image_path.exists()

    state.clear_all_history()

    assert not image_path.exists()


def test_clear_unpinned_history_prunes_image_files(tmp_path: Path) -> None:
    state = build_state(tmp_path)
    pinned = state.ingest_capture(
        ClipboardCapture(text="keep pinned", source_app="VS Code"),
        captured_at="2026-03-11T10:22:30",
    )
    state.toggle_pin(str(pinned["recentRecords"][0]["id"]))
    created = state.ingest_capture(
        ClipboardCapture(
            image_bytes=b"clear-unpinned",
            image_width=150,
            image_height=100,
            source_app="Snipping Tool",
        ),
        captured_at="2026-03-11T10:23:00",
    )
    image_record = created["recentRecords"][0]
    image_path = image_uri_to_path(str(image_record["imagePath"]))
    assert image_path.exists()

    cleared = state.clear_unpinned_history()

    assert [record["summary"] for record in cleared["pinnedRecords"]] == ["keep pinned"]
    assert cleared["recentRecords"] == []
    assert not image_path.exists()


def test_retention_prunes_replaced_image_files(tmp_path: Path) -> None:
    state = build_state(tmp_path)
    state.settings.history_limit = 1

    first = state.ingest_capture(
        ClipboardCapture(
            image_bytes=b"first-image",
            image_width=64,
            image_height=64,
            source_app="Snipping Tool",
        ),
        captured_at="2026-03-11T10:23:00",
    )
    first_image_path = image_uri_to_path(str(first["recentRecords"][0]["imagePath"]))
    assert first_image_path.exists()

    second = state.ingest_capture(
        ClipboardCapture(
            image_bytes=b"second-image",
            image_width=96,
            image_height=96,
            source_app="Snipping Tool",
        ),
        captured_at="2026-03-11T10:24:00",
    )
    second_image_path = image_uri_to_path(str(second["recentRecords"][0]["imagePath"]))

    assert not first_image_path.exists()
    assert second_image_path.exists()


def test_restart_uses_persisted_custom_storage_path(tmp_path: Path) -> None:
    state = build_state(tmp_path)
    custom_storage_path = tmp_path / "custom-data"

    settings = state.settings.to_dict()
    settings["storagePath"] = str(custom_storage_path)
    state.save_settings(settings, pause_recording=False)
    state.ingest_capture(
        ClipboardCapture(text="persist custom storage", source_app="VS Code"),
        captured_at="2026-03-11T10:25:00",
    )

    restarted = AppState(storage=AppStorage(base_path=tmp_path / "data"))

    assert restarted.storage.base_path == custom_storage_path
    assert restarted.settings.storage_path == str(custom_storage_path)
    assert [record["summary"] for record in restarted.snapshot()["recentRecords"]] == ["persist custom storage"]


def test_restart_prefers_custom_storage_history_over_default_storage_history(tmp_path: Path) -> None:
    state = build_state(tmp_path)
    default_storage = AppStorage(base_path=tmp_path / "data")
    custom_storage_path = tmp_path / "custom-data"

    settings = state.settings.to_dict()
    settings["storagePath"] = str(custom_storage_path)
    state.save_settings(settings, pause_recording=False)
    state.ingest_capture(
        ClipboardCapture(text="custom history", source_app="VS Code"),
        captured_at="2026-03-11T10:26:00",
    )

    default_storage.save_records([
        sample_record_for_summary("stale default history", captured_at="2026-03-11T10:27:00")
    ])

    restarted = AppState(storage=default_storage)

    assert [record["summary"] for record in restarted.snapshot()["recentRecords"]] == ["custom history"]
