from __future__ import annotations

import ctypes
import hashlib
import io
import re
import threading
import time
import uuid
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path

from PIL import Image
from PIL import ImageGrab

if hasattr(ctypes, "windll"):
    from ctypes import wintypes
else:  # pragma: no cover - non-Windows guard
    wintypes = None

from .models import HistoryRecord
from .models import SettingsState


@dataclass(slots=True)
class ClipboardCapture:
    text: str | None = None
    rich_text: str | None = None
    image_bytes: bytes | None = None
    image_width: int | None = None
    image_height: int | None = None
    file_paths: list[str] = field(default_factory=list)
    source_app: str | None = None
    source_glyph: str | None = None


class ClipboardMonitor:
    def __init__(
        self,
        *,
        reader,
        on_capture,
        is_paused,
        poll_interval: float = 0.35,
        sleep_fn=time.sleep,
    ) -> None:
        self.reader = reader
        self.on_capture = on_capture
        self.is_paused = is_paused
        self.poll_interval = poll_interval
        self.sleep_fn = sleep_fn
        self._last_sequence = 0
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._last_sequence = self.reader.get_sequence_number()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="clipboard-monitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    def poll_once(self) -> bool:
        sequence_number = self.reader.get_sequence_number()
        if sequence_number == 0 or sequence_number == self._last_sequence:
            return False

        self._last_sequence = sequence_number
        if self.is_paused():
            return False

        capture = self.reader.read_capture()
        if capture is None:
            return False

        self.on_capture(capture)
        return True

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.poll_once()
            except Exception:
                pass
            self.sleep_fn(self.poll_interval)


class WindowsClipboardReader:
    CF_UNICODETEXT = 13
    CF_HDROP = 15

    def __init__(self) -> None:
        self._is_windows = hasattr(ctypes, "windll")
        if not self._is_windows:
            return

        self.user32 = ctypes.windll.user32
        self.kernel32 = ctypes.windll.kernel32
        self.shell32 = ctypes.windll.shell32
        _configure_clipboard_api(self.user32, self.kernel32, self.shell32)
        _configure_process_api(self.user32, self.kernel32)
        self._html_format = self.user32.RegisterClipboardFormatW("HTML Format")
        self._rtf_format = self.user32.RegisterClipboardFormatW("Rich Text Format")

    def get_sequence_number(self) -> int:
        if not self._is_windows:
            return 0
        return int(self.user32.GetClipboardSequenceNumber())

    def read_capture(self) -> ClipboardCapture | None:
        if not self._is_windows:
            return None

        text: str | None = None
        rich_text: str | None = None
        file_paths: list[str] = []

        if not self._open_clipboard():
            return None

        try:
            if self.user32.IsClipboardFormatAvailable(self.CF_HDROP):
                file_paths = self._read_file_paths()

            if self.user32.IsClipboardFormatAvailable(self.CF_UNICODETEXT):
                text = self._read_unicode_text()

            if self._rtf_format and self.user32.IsClipboardFormatAvailable(self._rtf_format):
                rich_text = self._read_registered_text(self._rtf_format)
            elif self._html_format and self.user32.IsClipboardFormatAvailable(self._html_format):
                rich_text = self._read_registered_text(self._html_format)
        finally:
            self.user32.CloseClipboard()

        image_bytes: bytes | None = None
        image_width: int | None = None
        image_height: int | None = None

        if not file_paths:
            clipboard_image = ImageGrab.grabclipboard()
            if isinstance(clipboard_image, Image.Image):
                with io.BytesIO() as buffer:
                    clipboard_image.save(buffer, format="PNG")
                    image_bytes = buffer.getvalue()
                image_width, image_height = clipboard_image.size
            elif isinstance(clipboard_image, list):
                file_paths = [str(item) for item in clipboard_image]

        source_app = _foreground_app_name()
        return ClipboardCapture(
            text=text,
            rich_text=rich_text,
            image_bytes=image_bytes,
            image_width=image_width,
            image_height=image_height,
            file_paths=file_paths,
            source_app=source_app,
            source_glyph=_glyph_for_app(source_app),
        )

    def _open_clipboard(self) -> bool:
        for _ in range(10):
            if self.user32.OpenClipboard(None):
                return True
            time.sleep(0.02)
        return False

    def _read_file_paths(self) -> list[str]:
        handle = self.user32.GetClipboardData(self.CF_HDROP)
        if not handle:
            return []

        file_count = self.shell32.DragQueryFileW(handle, 0xFFFFFFFF, None, 0)
        file_paths: list[str] = []
        for index in range(file_count):
            length = self.shell32.DragQueryFileW(handle, index, None, 0)
            buffer = ctypes.create_unicode_buffer(length + 1)
            self.shell32.DragQueryFileW(handle, index, buffer, length + 1)
            file_paths.append(buffer.value)
        return file_paths

    def _read_unicode_text(self) -> str | None:
        handle = self.user32.GetClipboardData(self.CF_UNICODETEXT)
        if not handle:
            return None

        pointer = self.kernel32.GlobalLock(handle)
        if not pointer:
            return None

        try:
            return ctypes.wstring_at(pointer)
        finally:
            self.kernel32.GlobalUnlock(handle)

    def _read_registered_text(self, format_id: int) -> str | None:
        handle = self.user32.GetClipboardData(format_id)
        if not handle:
            return None

        pointer = self.kernel32.GlobalLock(handle)
        if not pointer:
            return None

        try:
            size = int(self.kernel32.GlobalSize(handle))
            raw_value = ctypes.string_at(pointer, size)
            raw_value = raw_value.split(b"\x00\x00", 1)[0].split(b"\x00", 1)[0]
            for encoding in ("utf-8", "utf-16le", "latin1"):
                try:
                    decoded = raw_value.decode(encoding).strip()
                except UnicodeDecodeError:
                    continue
                if decoded:
                    return decoded
            return None
        finally:
            self.kernel32.GlobalUnlock(handle)


def build_record_from_capture(
    capture: ClipboardCapture,
    settings: SettingsState,
    *,
    captured_at: str,
) -> HistoryRecord | None:
    source_app = (capture.source_app or "Clipboard").strip() or "Clipboard"
    source_glyph = capture.source_glyph or _glyph_for_app(source_app)

    if capture.file_paths and settings.record_files:
        first_path = Path(capture.file_paths[0])
        summary = first_path.name
        if len(capture.file_paths) > 1:
            summary = f"{summary} and {len(capture.file_paths) - 1} more files"

        detail = "\n".join(capture.file_paths)
        return HistoryRecord(
            id=f"record-{uuid.uuid4().hex}",
            type="file",
            summary=summary,
            detail=detail,
            meta=f"Files · {len(capture.file_paths)} items",
            source_app=source_app,
            source_glyph=source_glyph,
            pinned=False,
            created_at=captured_at,
            updated_at=captured_at,
            content_hash=_hash_for_payload("file", detail.encode("utf-8")),
            plain_text=detail,
            file_paths=list(capture.file_paths),
        )

    if capture.image_bytes and settings.record_images:
        width = capture.image_width or 0
        height = capture.image_height or 0
        return HistoryRecord(
            id=f"record-{uuid.uuid4().hex}",
            type="image",
            summary=f"Image {width} x {height}".strip(),
            detail=f"Image {width} x {height}".strip(),
            meta=f"Image · {width} x {height}".strip(),
            source_app=source_app,
            source_glyph=source_glyph,
            pinned=False,
            created_at=captured_at,
            updated_at=captured_at,
            content_hash=_hash_for_payload("image", capture.image_bytes),
            image_width=width or None,
            image_height=height or None,
        )

    if capture.rich_text and settings.record_rich_text:
        plain_text = (capture.text or _strip_markup(capture.rich_text)).strip()
        if not plain_text:
            plain_text = "Rich text"
        return HistoryRecord(
            id=f"record-{uuid.uuid4().hex}",
            type="rich_text",
            summary=_trim_summary(plain_text),
            detail=plain_text,
            meta="Rich text",
            source_app=source_app,
            source_glyph=source_glyph,
            pinned=False,
            created_at=captured_at,
            updated_at=captured_at,
            content_hash=_hash_for_payload("rich_text", capture.rich_text.encode("utf-8")),
            plain_text=plain_text,
            rich_text=capture.rich_text,
        )

    if capture.text and settings.record_text:
        plain_text = capture.text.strip()
        if not plain_text:
            return None

        return HistoryRecord(
            id=f"record-{uuid.uuid4().hex}",
            type="text",
            summary=_trim_summary(plain_text),
            detail=plain_text,
            meta="Text",
            source_app=source_app,
            source_glyph=source_glyph,
            pinned=False,
            created_at=captured_at,
            updated_at=captured_at,
            content_hash=_hash_for_payload("text", plain_text.encode("utf-8")),
            plain_text=plain_text,
        )

    return None


def _hash_for_payload(kind: str, payload: bytes) -> str:
    digest = hashlib.sha256()
    digest.update(kind.encode("utf-8"))
    digest.update(b":")
    digest.update(payload)
    return digest.hexdigest()


def _glyph_for_app(source_app: str) -> str:
    tokens = [token[0] for token in re.findall(r"[A-Za-z0-9]+", source_app)]
    glyph = "".join(tokens[:2]).upper()
    return glyph or source_app[:2].upper()


def _strip_markup(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value)


def _trim_summary(value: str, limit: int = 120) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def _foreground_app_name() -> str:
    if not hasattr(ctypes, "windll") or wintypes is None:  # pragma: no cover - non-Windows guard
        return "Clipboard"

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return "Clipboard"

    process_id = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
    if not process_id.value:
        return "Clipboard"

    process = kernel32.OpenProcess(0x1000, False, process_id.value)
    if not process:
        return "Clipboard"

    try:
        size = wintypes.DWORD(260)
        buffer = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(process, 0, buffer, ctypes.byref(size)):
            app_name = Path(buffer.value).stem.replace("_", " ").strip()
            return app_name or "Clipboard"
    finally:
        kernel32.CloseHandle(process)

    return "Clipboard"


class WindowsClipboardService:
    CF_UNICODETEXT = 13
    CF_HDROP = 15
    CF_DIB = 8
    GMEM_MOVEABLE = 0x0002
    KEYEVENTF_KEYUP = 0x0002
    SW_RESTORE = 9
    VK_CONTROL = 0x11
    VK_V = 0x56

    def __init__(self) -> None:
        self._is_windows = hasattr(ctypes, "windll")
        self._paste_target_hwnd = None
        if not self._is_windows:
            return

        self.user32 = ctypes.windll.user32
        self.kernel32 = ctypes.windll.kernel32
        _configure_clipboard_api(self.user32, self.kernel32)
        _configure_window_activation_api(self.user32)

    def capture_paste_target(self) -> None:
        if not self._is_windows:
            return
        self._paste_target_hwnd = self.user32.GetForegroundWindow()

    def has_paste_target(self) -> bool:
        if not self._is_windows or self._paste_target_hwnd is None:
            return False
        return bool(self.user32.IsWindow(self._paste_target_hwnd))

    def clear_paste_target(self) -> None:
        self._paste_target_hwnd = None

    def restore_paste_target(self) -> bool:
        if not self.has_paste_target():
            self._paste_target_hwnd = None
            return False

        hwnd = self._paste_target_hwnd
        self._paste_target_hwnd = None
        if self.user32.IsIconic(hwnd):
            self.user32.ShowWindow(hwnd, self.SW_RESTORE)
        self.user32.SetForegroundWindow(hwnd)
        return True

    def write_record(self, record: HistoryRecord, *, as_plain_text: bool) -> None:
        if not self._is_windows:
            return

        if not self._open_clipboard():
            return

        try:
            self.user32.EmptyClipboard()

            if record.type == "file" and record.file_paths and not as_plain_text:
                self._set_file_drop(record.file_paths)
                return

            if record.type == "image" and record.image_path and not as_plain_text:
                self._set_image(record.image_path)
                return

            plain_text = record.plain_text or record.detail or record.summary
            self._set_unicode_text(plain_text)

            if record.rich_text and not as_plain_text:
                self._set_rich_payload(record.rich_text)
        finally:
            self.user32.CloseClipboard()

    def send_paste_shortcut(self) -> None:
        if not self._is_windows:
            return

        self.user32.keybd_event(self.VK_CONTROL, 0, 0, 0)
        self.user32.keybd_event(self.VK_V, 0, 0, 0)
        self.user32.keybd_event(self.VK_V, 0, self.KEYEVENTF_KEYUP, 0)
        self.user32.keybd_event(self.VK_CONTROL, 0, self.KEYEVENTF_KEYUP, 0)

    def _open_clipboard(self) -> bool:
        for _ in range(10):
            if self.user32.OpenClipboard(None):
                return True
            time.sleep(0.02)
        return False

    def _set_unicode_text(self, value: str) -> None:
        payload = value.encode("utf-16le") + b"\x00\x00"
        self._set_memory_payload(self.CF_UNICODETEXT, payload)

    def _set_rich_payload(self, value: str) -> None:
        format_name = "Rich Text Format" if value.lstrip().startswith("{\\rtf") else "HTML Format"
        format_id = self.user32.RegisterClipboardFormatW(format_name)
        payload = value.encode("utf-8") + b"\x00"
        self._set_memory_payload(format_id, payload)

    def _set_file_drop(self, file_paths: list[str]) -> None:
        if wintypes is None:  # pragma: no cover - non-Windows guard
            return

        class DROPFILES(ctypes.Structure):
            _fields_ = [
                ("pFiles", wintypes.DWORD),
                ("pt_x", ctypes.c_long),
                ("pt_y", ctypes.c_long),
                ("fNC", wintypes.BOOL),
                ("fWide", wintypes.BOOL),
            ]

        drop_files = DROPFILES()
        drop_files.pFiles = ctypes.sizeof(DROPFILES)
        drop_files.pt_x = 0
        drop_files.pt_y = 0
        drop_files.fNC = False
        drop_files.fWide = True
        encoded_paths = ("\0".join(file_paths) + "\0\0").encode("utf-16le")
        header = ctypes.string_at(ctypes.byref(drop_files), ctypes.sizeof(DROPFILES))
        self._set_memory_payload(self.CF_HDROP, header + encoded_paths)

    def _set_image(self, image_path: str) -> None:
        with Image.open(image_path) as image:
            with io.BytesIO() as buffer:
                image.convert("RGB").save(buffer, format="BMP")
                payload = buffer.getvalue()[14:]
        self._set_memory_payload(self.CF_DIB, payload)

    def _set_memory_payload(self, format_id: int, payload: bytes) -> None:
        handle = self.kernel32.GlobalAlloc(self.GMEM_MOVEABLE, len(payload))
        pointer = self.kernel32.GlobalLock(handle)
        ctypes.memmove(pointer, payload, len(payload))
        self.kernel32.GlobalUnlock(handle)
        self.user32.SetClipboardData(format_id, handle)


def _configure_clipboard_api(user32, kernel32, shell32=None) -> None:
    user32.OpenClipboard.argtypes = [ctypes.c_void_p]
    user32.OpenClipboard.restype = ctypes.c_int
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = ctypes.c_int
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = ctypes.c_int
    user32.IsClipboardFormatAvailable.argtypes = [ctypes.c_uint]
    user32.IsClipboardFormatAvailable.restype = ctypes.c_int
    user32.GetClipboardData.argtypes = [ctypes.c_uint]
    user32.GetClipboardData.restype = ctypes.c_void_p
    user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p
    user32.GetClipboardSequenceNumber.argtypes = []
    user32.GetClipboardSequenceNumber.restype = ctypes.c_uint
    user32.RegisterClipboardFormatW.argtypes = [ctypes.c_wchar_p]
    user32.RegisterClipboardFormatW.restype = ctypes.c_uint

    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.restype = ctypes.c_int
    kernel32.GlobalSize.argtypes = [ctypes.c_void_p]
    kernel32.GlobalSize.restype = ctypes.c_size_t
    kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p

    if shell32 is not None:
        shell32.DragQueryFileW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_uint]
        shell32.DragQueryFileW.restype = ctypes.c_uint


def _configure_process_api(user32, kernel32) -> None:
    if wintypes is None:  # pragma: no cover - non-Windows guard
        return

    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD

    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.c_wchar_p,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL


def _configure_window_activation_api(user32) -> None:
    if wintypes is None:  # pragma: no cover - non-Windows guard
        return

    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsIconic.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
