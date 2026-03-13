from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field


@dataclass(slots=True)
class HistoryRecord:
    id: str
    type: str
    summary: str
    detail: str
    meta: str
    source_app: str
    source_glyph: str
    pinned: bool
    created_at: str
    updated_at: str
    content_hash: str
    plain_text: str | None = None
    rich_text: str | None = None
    image_path: str | None = None
    image_width: int | None = None
    image_height: int | None = None
    file_paths: list[str] = field(default_factory=list)

    def _normalize_image_path(self) -> str | None:
        if self.image_path is None:
            return None
        if self.image_path.startswith(("file://", "http://", "https://")):
            return self.image_path
        from pathlib import Path
        return Path(self.image_path).as_uri()

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "type": self.type,
            "summary": self.summary,
            "detail": self.detail,
            "meta": self.meta,
            "sourceApp": self.source_app,
            "sourceGlyph": self.source_glyph,
            "pinned": self.pinned,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "contentHash": self.content_hash,
            "plainText": self.plain_text,
            "richText": self.rich_text,
            "imagePath": self._normalize_image_path(),
            "imageWidth": self.image_width,
            "imageHeight": self.image_height,
            "filePaths": list(self.file_paths),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "HistoryRecord":
        return cls(
            id=str(payload["id"]),
            type=str(payload["type"]),
            summary=str(payload["summary"]),
            detail=str(payload["detail"]),
            meta=str(payload["meta"]),
            source_app=str(payload["sourceApp"]),
            source_glyph=str(payload.get("sourceGlyph", "")),
            pinned=bool(payload["pinned"]),
            created_at=str(payload.get("createdAt", payload["updatedAt"])),
            updated_at=str(payload["updatedAt"]),
            content_hash=str(payload.get("contentHash", payload["id"])),
            plain_text=_optional_string(payload.get("plainText")),
            rich_text=_optional_string(payload.get("richText")),
            image_path=_optional_string(payload.get("imagePath")),
            image_width=_optional_int(payload.get("imageWidth")),
            image_height=_optional_int(payload.get("imageHeight")),
            file_paths=[str(item) for item in payload.get("filePaths", [])],
        )


@dataclass(slots=True)
class ShortcutBindings:
    toggle_panel: str
    primary_action: str
    paste_plain_text: str
    toggle_pin: str
    delete_record: str

    def to_dict(self) -> dict[str, str]:
        return {
            "togglePanel": self.toggle_panel,
            "primaryAction": self.primary_action,
            "pastePlainText": self.paste_plain_text,
            "togglePin": self.toggle_pin,
            "deleteRecord": self.delete_record,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "ShortcutBindings":
        return cls(
            toggle_panel=str(payload["togglePanel"]),
            primary_action=str(payload["primaryAction"]),
            paste_plain_text=str(payload["pastePlainText"]),
            toggle_pin=str(payload["togglePin"]),
            delete_record=str(payload["deleteRecord"]),
        )


@dataclass(slots=True)
class SettingsState:
    launch_on_startup: bool
    close_to_tray: bool
    follow_system_theme: bool
    record_text: bool
    record_rich_text: bool
    text_history_limit: int
    image_history_limit: int
    record_images: bool
    record_files: bool
    storage_path: str
    shortcuts: ShortcutBindings

    def to_dict(self) -> dict[str, object]:
        return {
            "launchOnStartup": self.launch_on_startup,
            "closeToTray": self.close_to_tray,
            "followSystemTheme": self.follow_system_theme,
            "recordText": self.record_text,
            "recordRichText": self.record_rich_text,
            "textHistoryLimit": self.text_history_limit,
            "imageHistoryLimit": self.image_history_limit,
            "recordImages": self.record_images,
            "recordFiles": self.record_files,
            "storagePath": self.storage_path,
            "shortcuts": self.shortcuts.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "SettingsState":
        return cls(
            launch_on_startup=bool(payload["launchOnStartup"]),
            close_to_tray=bool(payload["closeToTray"]),
            follow_system_theme=bool(payload["followSystemTheme"]),
            record_text=bool(payload.get("recordText", True)),
            record_rich_text=bool(payload.get("recordRichText", True)),
            text_history_limit=int(payload["textHistoryLimit"]),
            image_history_limit=int(payload["imageHistoryLimit"]),
            record_images=bool(payload["recordImages"]),
            record_files=bool(payload.get("recordFiles", True)),
            storage_path=str(payload["storagePath"]),
            shortcuts=ShortcutBindings.from_dict(dict(payload["shortcuts"])),
        )


@dataclass(slots=True)
class ToastMessage:
    title: str
    message: str
    tone: str
    action_kind: str | None = None
    action_label: str | None = None
    id: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "message": self.message,
            "tone": self.tone,
            "actionKind": self.action_kind,
            "actionLabel": self.action_label,
        }


def default_settings(*, storage_path: str) -> SettingsState:
    return SettingsState(
        launch_on_startup=True,
        close_to_tray=True,
        follow_system_theme=True,
        record_text=True,
        record_rich_text=True,
        text_history_limit=1000,
        image_history_limit=100,
        record_images=True,
        record_files=True,
        storage_path=storage_path,
        shortcuts=ShortcutBindings(
            toggle_panel="Alt + Space",
            primary_action="Enter",
            paste_plain_text="Ctrl + Shift + V",
            toggle_pin="Ctrl + P",
            delete_record="Delete",
        ),
    )


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
