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
        self._toggle_always_on_top: Callable[[], None] | None = None
        self._is_always_on_top: Callable[[], bool] | None = None

    def _bind_hide_window(self, hide_window: Callable[[], None]) -> None:
        self._hide_window = hide_window

    def _bind_pick_storage_path(self, pick_storage_path: Callable[[str], str | None]) -> None:
        self._pick_storage_path = pick_storage_path

    def _bind_confirm_clear_all_history(self, confirm_clear_all_history: Callable[[], bool]) -> None:
        self._confirm_clear_all_history = confirm_clear_all_history

    def _bind_toggle_always_on_top(self, toggle_always_on_top: Callable[[], None]) -> None:
        self._toggle_always_on_top = toggle_always_on_top

    def _bind_is_always_on_top(self, is_always_on_top: Callable[[], bool]) -> None:
        self._is_always_on_top = is_always_on_top

    def get_app_state(self) -> dict[str, object]:
        return self._snapshot()

    def set_view(self, view: str) -> dict[str, object]:
        if view != "panel":
            self._state.clear_paste_target()
        self._state.set_view(view)
        return self._snapshot()

    def toggle_pause(self) -> dict[str, object]:
        self._state.toggle_pause()
        return self._snapshot()

    def toggle_pin(self, record_id: str) -> dict[str, object]:
        self._state.toggle_pin(record_id)
        return self._snapshot()

    def delete_record(self, record_id: str) -> dict[str, object]:
        self._state.delete_record(record_id)
        return self._snapshot()

    def undo_delete(self) -> dict[str, object]:
        self._state.undo_delete()
        return self._snapshot()

    def clear_all_history(self) -> dict[str, object]:
        self._state.clear_all_history()
        return self._snapshot()

    def clear_unpinned_history(self) -> dict[str, object]:
        self._state.clear_unpinned_history()
        return self._snapshot()

    def trigger_primary_action(self, record_id: str) -> dict[str, object]:
        if self._should_hide_window_for_action():
            self._hide_window()
        self._state.trigger_primary_action(record_id)
        return self._snapshot()

    def paste_plain_text(self, record_id: str) -> dict[str, object]:
        if self._should_hide_window_for_action() and self._state.has_paste_target():
            self._hide_window()
        self._state.paste_plain_text(record_id)
        return self._snapshot()

    def copy_record(self, record_id: str) -> dict[str, object]:
        if self._should_hide_window_for_action():
            self.hide_window()
        self._state.copy_record(record_id)
        return self._snapshot()

    def save_settings(self, settings: dict[str, object], pause_recording: bool) -> dict[str, object]:
        self._state.save_settings(settings, pause_recording)
        return self._snapshot()

    def restore_default_shortcuts(self) -> dict[str, object]:
        self._state.restore_default_shortcuts()
        return self._snapshot()

    def dismiss_toast(self) -> dict[str, object]:
        self._state.dismiss_toast()
        return self._snapshot()

    def ingest_clipboard_capture(
        self,
        payload: dict[str, object],
        captured_at: str | None = None,
    ) -> dict[str, object]:
        self._state.ingest_capture(
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
        return self._snapshot()

    def toggle_always_on_top(self) -> dict[str, object]:
        if self._toggle_always_on_top is not None:
            self._toggle_always_on_top()
        return self._snapshot()

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

    def _snapshot(self) -> dict[str, object]:
        snapshot = self._state.snapshot()
        snapshot["isAlwaysOnTop"] = False if self._is_always_on_top is None else self._is_always_on_top()
        return snapshot

    def _should_hide_window_for_action(self) -> bool:
        if self._hide_window is None:
            return False
        if self._is_always_on_top is None:
            return True
        return not self._is_always_on_top()


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
