from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Callable

from .clipboard import ClipboardCapture
from .clipboard import WindowsClipboardService
from .clipboard import build_record_from_capture
from .models import HistoryRecord
from .models import SettingsState
from .models import ShortcutBindings
from .models import ToastMessage
from .models import default_settings
from .runtime import resolve_default_storage_path
from .storage import AppStorage


SnapshotListener = Callable[[dict[str, object]], None]


class AppState:
    def __init__(self, *, storage: AppStorage | None = None, clipboard_service=None) -> None:
        project_root = Path(__file__).resolve().parents[2]
        default_storage_path = resolve_default_storage_path(project_root=project_root)
        self.storage = storage or AppStorage(base_path=default_storage_path)
        self.clipboard_service = clipboard_service or WindowsClipboardService()
        self.view = "panel"
        self.is_recording_paused = False
        self.settings = self.storage.load_settings()
        self.records = self.storage.load_records()
        self.toast: ToastMessage | None = None
        self.deleted_record: HistoryRecord | None = None
        self.deleted_record_image_bytes: bytes | None = None
        self._listeners: list[SnapshotListener] = []
        self._normalize_storage_path()
        self._persist_all()

    def subscribe(self, listener: SnapshotListener) -> None:
        self._listeners.append(listener)

    def snapshot(self) -> dict[str, object]:
        pinned = [record for record in self._sorted_records() if record.pinned]
        recent = [record for record in self._sorted_records() if not record.pinned]
        return {
            "view": self.view,
            "isRecordingPaused": self.is_recording_paused,
            "pinnedRecords": [record.to_dict() for record in pinned],
            "recentRecords": [record.to_dict() for record in recent],
            "settings": self.settings.to_dict(),
            "toast": None if self.toast is None else self.toast.to_dict(),
        }

    def set_view(self, view: str) -> dict[str, object]:
        self.view = view
        return self._commit()

    def toggle_pause(self) -> dict[str, object]:
        self.is_recording_paused = not self.is_recording_paused
        self.toast = self._make_toast(
            title="记录已暂停" if self.is_recording_paused else "已恢复记录",
            message="新的剪贴板内容暂时不会进入历史。"
            if self.is_recording_paused
            else "新的剪贴板内容会继续进入历史。",
            tone="danger" if self.is_recording_paused else "success",
        )
        return self._commit()

    def ingest_capture(self, capture: ClipboardCapture, *, captured_at: str | None = None) -> dict[str, object]:
        if self.is_recording_paused:
            return self.snapshot()

        timestamp = captured_at or self._timestamp()
        record = build_record_from_capture(capture, self.settings, captured_at=timestamp)
        if record is None:
            return self.snapshot()

        if record.type == "image" and capture.image_bytes:
            record.image_path = self.storage.save_image_bytes(record_id=record.id, image_bytes=capture.image_bytes)

        newest_record = next(iter(self._sorted_records()), None)
        if newest_record and newest_record.content_hash == record.content_hash:
            return self.snapshot()

        self.records.append(record)
        self._apply_retention()
        self._persist_all()
        return self._commit()

    def toggle_pin(self, record_id: str) -> dict[str, object]:
        record = self._find_record(record_id)
        if record is None:
            return self.snapshot()

        record.pinned = not record.pinned
        record.updated_at = self._timestamp()
        self._apply_retention()
        self._persist_all()
        self.toast = self._make_toast(
            title="已固定记录" if record.pinned else "已取消固定",
            message=record.summary,
            tone="success",
        )
        return self._commit()

    def delete_record(self, record_id: str) -> dict[str, object]:
        record = self._find_record(record_id)
        if record is None:
            return self.snapshot()

        self.deleted_record_image_bytes = self.storage.read_image_bytes(record.image_path)
        self.deleted_record = deepcopy(record)
        self.records = [item for item in self.records if item.id != record_id]
        self._persist_all()
        self.toast = self._make_toast(
            title="记录已删除",
            message=record.summary,
            tone="danger",
            action_kind="undo_delete",
            action_label="撤销",
        )
        return self._commit()

    def capture_paste_target(self) -> None:
        capture_target = getattr(self.clipboard_service, "capture_paste_target", None)
        if callable(capture_target):
            capture_target()

    def has_paste_target(self) -> bool:
        has_target = getattr(self.clipboard_service, "has_paste_target", None)
        if callable(has_target):
            return bool(has_target())
        return False

    def clear_paste_target(self) -> None:
        clear_target = getattr(self.clipboard_service, "clear_paste_target", None)
        if callable(clear_target):
            clear_target()

    def undo_delete(self) -> dict[str, object]:
        if self.deleted_record is None:
            return self.snapshot()

        restored_record = deepcopy(self.deleted_record)
        if restored_record.type == "image" and self.deleted_record_image_bytes is not None:
            restored_record.image_path = self.storage.save_image_bytes(
                record_id=restored_record.id,
                image_bytes=self.deleted_record_image_bytes,
            )

        self.records.append(restored_record)
        self._apply_retention()
        self._persist_all()
        self.toast = self._make_toast(
            title="已恢复删除的记录",
            message=restored_record.summary,
            tone="success",
        )
        self.deleted_record = None
        self.deleted_record_image_bytes = None
        return self._commit()

    def clear_all_history(self) -> dict[str, object]:
        self.records = []
        self._persist_all()
        self.toast = self._make_toast(
            title="已清空全部历史",
            message="固定和最近记录都已移除。",
            tone="danger",
        )
        return self._commit()

    def clear_unpinned_history(self) -> dict[str, object]:
        self.records = [record for record in self.records if record.pinned]
        self._persist_all()
        self.toast = self._make_toast(
            title="已清除未固定记录",
            message="仅保留固定记录。",
            tone="danger",
        )
        return self._commit()

    def trigger_primary_action(self, record_id: str) -> dict[str, object]:
        record = self._find_record(record_id)
        if record is None:
            return self.snapshot()

        self.clipboard_service.write_record(record, as_plain_text=False)
        if self.has_paste_target():
            restore_target = getattr(self.clipboard_service, "restore_paste_target", None)
            if callable(restore_target):
                restore_target()
            self.clipboard_service.send_paste_shortcut()
        return self._commit()

    def paste_plain_text(self, record_id: str) -> dict[str, object]:
        record = self._find_record(record_id)
        if record is None:
            return self.snapshot()

        self.clipboard_service.write_record(record, as_plain_text=True)
        if self.has_paste_target():
            restore_target = getattr(self.clipboard_service, "restore_paste_target", None)
            if callable(restore_target):
                restore_target()
            self.clipboard_service.send_paste_shortcut()
        return self._commit()

    def copy_record(self, record_id: str) -> dict[str, object]:
        record = self._find_record(record_id)
        if record is None:
            return self.snapshot()

        self.clipboard_service.write_record(record, as_plain_text=False)
        return self._commit()

    def save_settings(self, settings: dict[str, object], pause_recording: bool) -> dict[str, object]:
        self.settings = SettingsState(
            launch_on_startup=bool(settings["launchOnStartup"]),
            close_to_tray=bool(settings["closeToTray"]),
            follow_system_theme=bool(settings["followSystemTheme"]),
            record_text=bool(settings.get("recordText", True)),
            record_rich_text=bool(settings.get("recordRichText", True)),
            text_history_limit=int(settings["textHistoryLimit"]),
            image_history_limit=int(settings["imageHistoryLimit"]),
            record_images=bool(settings["recordImages"]),
            record_files=bool(settings.get("recordFiles", True)),
            storage_path=str(settings["storagePath"]),
            shortcuts=ShortcutBindings(
                toggle_panel=str(settings["shortcuts"]["togglePanel"]),
                primary_action=str(settings["shortcuts"]["primaryAction"]),
                paste_plain_text=str(settings["shortcuts"]["pastePlainText"]),
                toggle_pin=str(settings["shortcuts"]["togglePin"]),
                delete_record=str(settings["shortcuts"]["deleteRecord"]),
            ),
        )
        self.is_recording_paused = pause_recording
        self.view = "panel"
        self._normalize_storage_path()
        self._apply_retention()
        self._persist_all()
        self.toast = self._make_toast(
            title="设置已保存",
            message="新的应用配置已经生效。",
            tone="success",
        )
        return self._commit()

    def restore_default_shortcuts(self) -> dict[str, object]:
        self.settings.shortcuts = self._default_settings().shortcuts
        self.toast = self._make_toast(
            title="快捷键已恢复默认",
            message="可以继续编辑后再保存。",
            tone="neutral",
        )
        return self._commit()

    def dismiss_toast(self) -> dict[str, object]:
        self.toast = None
        self.deleted_record = None
        self.deleted_record_image_bytes = None
        return self._commit()

    def _commit(self) -> dict[str, object]:
        snapshot = self.snapshot()
        for listener in self._listeners:
            listener(snapshot)
        return snapshot

    def _persist_all(self) -> None:
        self.storage.save_settings(self.settings)
        self.storage.save_records(self.records)
        self.storage.prune_unreferenced_images(record.image_path for record in self.records)

    def _normalize_storage_path(self) -> None:
        storage_path = Path(self.settings.storage_path)
        if storage_path != self.storage.base_path:
            target_storage = AppStorage(base_path=storage_path)
            self.records = self._merge_records(self.records, target_storage.load_records())
            self.records = self._migrate_record_images(self.records, target_storage)
            self.storage = target_storage
        self.settings.storage_path = str(self.storage.base_path)

    def _apply_retention(self) -> None:
        sorted_records = self._sorted_records()
        retained_ids: set[str] = {record.id for record in sorted_records if record.pinned}

        unpinned_text_records = [
            record for record in sorted_records if not record.pinned and record.type in {"text", "rich_text", "file"}
        ]
        unpinned_image_records = [
            record for record in sorted_records if not record.pinned and record.type == "image"
        ]

        retained_ids.update(record.id for record in unpinned_text_records[: self.settings.text_history_limit])
        retained_ids.update(record.id for record in unpinned_image_records[: self.settings.image_history_limit])
        self.records = [record for record in self.records if record.id in retained_ids]

    def _sorted_records(self) -> list[HistoryRecord]:
        return sorted(self.records, key=lambda record: record.updated_at, reverse=True)

    def _find_record(self, record_id: str) -> HistoryRecord | None:
        return next((record for record in self.records if record.id == record_id), None)

    @staticmethod
    def _merge_records(
        current_records: list[HistoryRecord],
        target_records: list[HistoryRecord],
    ) -> list[HistoryRecord]:
        merged_records = {record.id: deepcopy(record) for record in target_records}
        for record in current_records:
            merged_records[record.id] = deepcopy(record)
        return list(merged_records.values())

    @staticmethod
    def _migrate_record_images(records: list[HistoryRecord], storage: AppStorage) -> list[HistoryRecord]:
        migrated_records: list[HistoryRecord] = []
        for record in records:
            migrated_record = deepcopy(record)
            if migrated_record.type == "image" and migrated_record.image_path:
                migrated_record.image_path = storage.import_image_path(
                    record_id=migrated_record.id,
                    image_path=migrated_record.image_path,
                )
            migrated_records.append(migrated_record)
        return migrated_records

    def _make_toast(
        self,
        *,
        title: str,
        message: str,
        tone: str,
        action_kind: str | None = None,
        action_label: str | None = None,
    ) -> ToastMessage:
        return ToastMessage(
            id=f"{title}-{int(datetime.now().timestamp() * 1000)}",
            title=title,
            message=message,
            tone=tone,
            action_kind=action_kind,
            action_label=action_label,
        )

    @staticmethod
    def _timestamp() -> str:
        return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    @staticmethod
    def _default_settings() -> SettingsState:
        default_storage_path = resolve_default_storage_path(project_root=Path(__file__).resolve().parents[2])
        return default_settings(storage_path=str(default_storage_path))
