from __future__ import annotations

from collections import deque
import ctypes

from backend.app.clipboard import ClipboardCapture
from backend.app.clipboard import ClipboardMonitor
from backend.app.clipboard import WindowsClipboardReader
from backend.app.clipboard import WindowsClipboardService
from backend.app.clipboard import build_record_from_capture
from backend.app.models import SettingsState, ShortcutBindings


def settings(
    *,
    record_text: bool = True,
    record_rich_text: bool = True,
    record_images: bool = True,
    record_files: bool = True,
) -> SettingsState:
    return SettingsState(
        launch_on_startup=True,
        close_to_tray=True,
        follow_system_theme=True,
        record_text=record_text,
        record_rich_text=record_rich_text,
        history_limit=25,
        record_images=record_images,
        record_files=record_files,
        storage_path="D:\\Desktop\\clipboard\\data",
        shortcuts=ShortcutBindings(
            toggle_panel="Alt + Space",
            primary_action="Enter",
            paste_plain_text="Ctrl + Shift + V",
            toggle_pin="Ctrl + P",
            delete_record="Delete",
        ),
    )


def test_build_record_from_capture_prioritizes_file_then_image_then_rich_text_then_text() -> None:
    record = build_record_from_capture(
        ClipboardCapture(
            text="plain",
            rich_text="<b>plain</b>",
            image_bytes=b"image",
            image_width=400,
            image_height=300,
            file_paths=["D:\\Docs\\file.txt"],
            source_app="Explorer",
        ),
        settings(),
        captured_at="2026-03-11T12:30:00",
    )

    assert record is not None
    assert record.type == "file"
    assert record.summary == "file.txt"


def test_build_record_from_capture_skips_files_when_disabled() -> None:
    record = build_record_from_capture(
        ClipboardCapture(
            file_paths=["D:\\Docs\\file.txt"],
            source_app="Explorer",
        ),
        settings(record_files=False),
        captured_at="2026-03-11T12:30:30",
    )

    assert record is None


def test_build_record_from_capture_skips_images_when_disabled() -> None:
    record = build_record_from_capture(
        ClipboardCapture(
            image_bytes=b"image",
            image_width=320,
            image_height=240,
            source_app="Snipping Tool",
        ),
        settings(record_images=False),
        captured_at="2026-03-11T12:31:00",
    )

    assert record is None


def test_build_record_from_capture_skips_rich_text_when_disabled_and_uses_plain_text() -> None:
    record = build_record_from_capture(
        ClipboardCapture(
            text="hello",
            rich_text="<p>hello</p>",
            source_app="Word",
        ),
        settings(record_rich_text=False),
        captured_at="2026-03-11T12:31:30",
    )

    assert record is not None
    assert record.type == "text"
    assert record.plain_text == "hello"


def test_build_record_from_capture_uses_rich_text_before_plain_text() -> None:
    record = build_record_from_capture(
        ClipboardCapture(
            text="hello",
            rich_text="<p>hello</p>",
            source_app="Word",
        ),
        settings(),
        captured_at="2026-03-11T12:32:00",
    )

    assert record is not None
    assert record.type == "rich_text"
    assert record.plain_text == "hello"


def test_build_record_from_capture_skips_text_when_disabled() -> None:
    record = build_record_from_capture(
        ClipboardCapture(
            text="hello",
            source_app="VS Code",
        ),
        settings(record_text=False),
        captured_at="2026-03-11T12:32:30",
    )

    assert record is None


class FakeClipboardReader:
    def __init__(self, sequence_numbers: list[int], captures: list[ClipboardCapture | None]) -> None:
        self.sequence_numbers = deque(sequence_numbers)
        self.captures = deque(captures)

    def get_sequence_number(self) -> int:
        if self.sequence_numbers:
            return self.sequence_numbers.popleft()
        return 0

    def read_capture(self) -> ClipboardCapture | None:
        if self.captures:
            return self.captures.popleft()
        return None


def test_clipboard_monitor_emits_only_when_sequence_changes() -> None:
    emitted: list[ClipboardCapture] = []
    monitor = ClipboardMonitor(
        reader=FakeClipboardReader(
            sequence_numbers=[1, 1, 2, 2],
            captures=[
                ClipboardCapture(text="first"),
                ClipboardCapture(text="second"),
            ],
        ),
        on_capture=emitted.append,
        is_paused=lambda: False,
    )

    monitor.poll_once()
    monitor.poll_once()
    monitor.poll_once()
    monitor.poll_once()

    assert [capture.text for capture in emitted] == ["first", "second"]


def test_clipboard_monitor_skips_capture_while_paused() -> None:
    emitted: list[ClipboardCapture] = []
    paused = True
    monitor = ClipboardMonitor(
        reader=FakeClipboardReader(
            sequence_numbers=[1, 2],
            captures=[
                ClipboardCapture(text="second"),
            ],
        ),
        on_capture=emitted.append,
        is_paused=lambda: paused,
    )

    monitor.poll_once()
    paused = False
    monitor.poll_once()

    assert [capture.text for capture in emitted] == ["second"]


def test_windows_clipboard_reader_configures_pointer_sized_winapi_signatures() -> None:
    if not hasattr(ctypes, "windll"):
        return

    reader = WindowsClipboardReader()

    assert reader.user32.GetClipboardData.restype is ctypes.c_void_p
    assert reader.kernel32.GlobalLock.restype is ctypes.c_void_p


def test_restore_paste_target_does_not_restore_non_minimized_window() -> None:
    calls: list[tuple[str, int, int] | tuple[str, int]] = []

    class FakeUser32:
        def IsWindow(self, hwnd):
            return True

        def IsIconic(self, hwnd):
            return False

        def ShowWindow(self, hwnd, command):
            calls.append(("show", hwnd, command))
            return True

        def SetForegroundWindow(self, hwnd):
            calls.append(("foreground", hwnd))
            return True

    clipboard_service = object.__new__(WindowsClipboardService)
    clipboard_service._is_windows = True
    clipboard_service.user32 = FakeUser32()
    clipboard_service._paste_target_hwnd = 99
    clipboard_service.SW_RESTORE = 9

    restored = clipboard_service.restore_paste_target()

    assert restored is True
    assert calls == [("foreground", 99)]


def test_restore_paste_target_restores_minimized_window_before_foregrounding() -> None:
    calls: list[tuple[str, int, int] | tuple[str, int]] = []

    class FakeUser32:
        def IsWindow(self, hwnd):
            return True

        def IsIconic(self, hwnd):
            return True

        def ShowWindow(self, hwnd, command):
            calls.append(("show", hwnd, command))
            return True

        def SetForegroundWindow(self, hwnd):
            calls.append(("foreground", hwnd))
            return True

    clipboard_service = object.__new__(WindowsClipboardService)
    clipboard_service._is_windows = True
    clipboard_service.user32 = FakeUser32()
    clipboard_service._paste_target_hwnd = 42
    clipboard_service.SW_RESTORE = 9

    restored = clipboard_service.restore_paste_target()

    assert restored is True
    assert calls == [("show", 42, 9), ("foreground", 42)]
