from __future__ import annotations

from collections.abc import Callable

from .clipboard import ClipboardCapture
from .state import AppState


class AppBridge:
    def __init__(self, state: AppState) -> None:
        self._state = state
        self._hide_window: Callable[[], None] | None = None
        self._pick_storage_path: Callable[[str], str | None] | None = None
        self._confirm_clear_all_history: Callable[[], bool] | None = None

    def _bind_hide_window(self, hide_window: Callable[[], None]) -> None:
        self._hide_window = hide_window

    def _bind_pick_storage_path(self, pick_storage_path: Callable[[str], str | None]) -> None:
        self._pick_storage_path = pick_storage_path

    def _bind_confirm_clear_all_history(self, confirm_clear_all_history: Callable[[], bool]) -> None:
        self._confirm_clear_all_history = confirm_clear_all_history

    def get_app_state(self) -> dict[str, object]:
        return self._state.snapshot()

    def set_view(self, view: str) -> dict[str, object]:
        if view != "panel":
            self._state.clear_paste_target()
        return self._state.set_view(view)

    def toggle_pause(self) -> dict[str, object]:
        return self._state.toggle_pause()

    def toggle_pin(self, record_id: str) -> dict[str, object]:
        return self._state.toggle_pin(record_id)

    def delete_record(self, record_id: str) -> dict[str, object]:
        return self._state.delete_record(record_id)

    def undo_delete(self) -> dict[str, object]:
        return self._state.undo_delete()

    def clear_all_history(self) -> dict[str, object]:
        return self._state.clear_all_history()

    def clear_unpinned_history(self) -> dict[str, object]:
        return self._state.clear_unpinned_history()

    def trigger_primary_action(self, record_id: str) -> dict[str, object]:
        if self._hide_window is not None and self._state.has_paste_target():
            self._hide_window()
        return self._state.trigger_primary_action(record_id)

    def paste_plain_text(self, record_id: str) -> dict[str, object]:
        if self._hide_window is not None and self._state.has_paste_target():
            self._hide_window()
        return self._state.paste_plain_text(record_id)

    def copy_record(self, record_id: str) -> dict[str, object]:
        return self._state.copy_record(record_id)

    def save_settings(self, settings: dict[str, object], pause_recording: bool) -> dict[str, object]:
        return self._state.save_settings(settings, pause_recording)

    def restore_default_shortcuts(self) -> dict[str, object]:
        return self._state.restore_default_shortcuts()

    def dismiss_toast(self) -> dict[str, object]:
        return self._state.dismiss_toast()

    def ingest_clipboard_capture(
        self,
        payload: dict[str, object],
        captured_at: str | None = None,
    ) -> dict[str, object]:
        return self._state.ingest_capture(
            ClipboardCapture(
                text=_optional_string(payload.get("text")),
                rich_text=_optional_string(payload.get("richText")),
                image_bytes=_optional_bytes(payload.get("imageBytes")),
                image_width=_optional_int(payload.get("imageWidth")),
                image_height=_optional_int(payload.get("imageHeight")),
                file_paths=[str(item) for item in payload.get("filePaths", [])],
                source_app=_optional_string(payload.get("sourceApp")),
                source_glyph=_optional_string(payload.get("sourceGlyph")),
            ),
            captured_at=captured_at,
        )

    def hide_window(self) -> None:
        self._state.clear_paste_target()
        if self._hide_window is not None:
            self._hide_window()

    def pick_storage_path(self, current_path: str) -> str | None:
        if self._pick_storage_path is None:
            return None
        return self._pick_storage_path(current_path)

    def confirm_clear_all_history(self) -> bool:
        if self._confirm_clear_all_history is None:
            return True
        return self._confirm_clear_all_history()


def _optional_bytes(value: object) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value
    return str(value).encode("utf-8")


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
