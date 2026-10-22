"""Which app a clip came from, its proper name and its icon.

The source is the process that owns the clipboard (the app that put the content there); the
foreground window is only the fallback, since a screenshot tool or a background app can copy
while another window is in front. The proper name is the exe's FileDescription ("Visual Studio
Code" rather than "Code"); the icon is pulled straight out of the exe at 64 px, alpha included
(this works for Store apps too, whose exe also embeds its icon).
"""

from __future__ import annotations

import ctypes
import io
import os
from dataclasses import dataclass
from pathlib import Path

if hasattr(ctypes, "windll"):
    from ctypes import wintypes
else:  # pragma: no cover - non-Windows guard
    wintypes = None

ICON_SIZE = 64
# Longer descriptions are usually a sentence ("Microsoft Office component ..."), not a name.
MAX_NAME_LENGTH = 32
SELF_NAME = "ClipDeck"
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


@dataclass(slots=True)
class SourceApp:
    name: str
    exe_path: str | None = None


def exe_stem_name(exe_path: str) -> str:
    """The name records were labelled with before proper names: the exe's stem."""
    return Path(exe_path).stem.replace("_", " ").strip()


def identify_source_app() -> SourceApp:
    if wintypes is None:  # pragma: no cover - non-Windows guard
        return SourceApp("Clipboard")
    user32, kernel32 = _apis()
    for hwnd in (user32.GetClipboardOwner(), user32.GetForegroundWindow()):
        if not hwnd:
            continue
        process_id = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        if not process_id.value:
            continue
        if process_id.value == os.getpid():
            return SourceApp(SELF_NAME)
        exe_path = _process_path(kernel32, process_id.value)
        if exe_path:
            return SourceApp(display_name(exe_path), exe_path)
    return SourceApp("Clipboard")


def display_name(exe_path: str) -> str:
    description = (file_description(exe_path) or "").strip()
    if description and len(description) <= MAX_NAME_LENGTH:
        return description
    return exe_stem_name(exe_path) or "Clipboard"


def file_description(exe_path: str) -> str | None:
    if wintypes is None:  # pragma: no cover - non-Windows guard
        return None
    version = _version_api()
    size = version.GetFileVersionInfoSizeW(exe_path, None)
    if not size:
        return None
    data = ctypes.create_string_buffer(size)
    if not version.GetFileVersionInfoW(exe_path, 0, size, data):
        return None
    pointer = ctypes.c_void_p()
    length = wintypes.UINT()
    languages: list[str] = []
    if version.VerQueryValueW(data, "\\VarFileInfo\\Translation", ctypes.byref(pointer), ctypes.byref(length)) and length.value >= 4:
        pairs = ctypes.cast(pointer, ctypes.POINTER(wintypes.WORD * (length.value // 2))).contents
        languages = [f"{pairs[i]:04x}{pairs[i + 1]:04x}" for i in range(0, len(pairs) - 1, 2)]
    # Some exes list no translation table; these two are what they use in practice.
    for language in [*languages, "040904b0", "040904e4"]:
        query = f"\\StringFileInfo\\{language}\\FileDescription"
        if version.VerQueryValueW(data, query, ctypes.byref(pointer), ctypes.byref(length)) and length.value > 1:
            return ctypes.wstring_at(pointer, length.value - 1)
    return None


def extract_icon_png(exe_path: str, size: int = ICON_SIZE) -> bytes | None:
    """The exe's main icon as a PNG, or None if it has none."""
    if wintypes is None:  # pragma: no cover - non-Windows guard
        return None
    from PIL import Image

    user32, _ = _apis()
    gdi32 = _gdi_api()
    hicon = wintypes.HICON()
    if not user32.PrivateExtractIconsW(exe_path, 0, size, size, ctypes.byref(hicon), None, 1, 0) or not hicon:
        return None
    info = _IconInfo()
    try:
        if not user32.GetIconInfo(hicon, ctypes.byref(info)) or not info.hbmColor:
            return None
        header = _BitmapInfoHeader(biSize=ctypes.sizeof(_BitmapInfoHeader), biWidth=size, biHeight=-size, biPlanes=1, biBitCount=32)
        pixels = ctypes.create_string_buffer(size * size * 4)
        dc = user32.GetDC(None)
        try:
            rows = gdi32.GetDIBits(dc, info.hbmColor, 0, size, pixels, ctypes.byref(header), 0)
        finally:
            user32.ReleaseDC(None, dc)
        if rows != size:
            return None
        image = Image.frombuffer("RGBA", (size, size), pixels.raw, "raw", "BGRA", 0, 1)
        if image.getchannel("A").getextrema()[1] == 0:
            # An icon without an alpha channel: take its mask instead.
            image = _apply_mask(image, info.hbmMask, size, user32, gdi32)
        if image is None or image.getbbox() is None:
            return None
        with io.BytesIO() as buffer:
            image.save(buffer, format="PNG")
            return buffer.getvalue()
    finally:
        if info.hbmColor:
            gdi32.DeleteObject(info.hbmColor)
        if info.hbmMask:
            gdi32.DeleteObject(info.hbmMask)
        user32.DestroyIcon(hicon)


def _apply_mask(image, hbm_mask, size: int, user32, gdi32):
    from PIL import Image

    if not hbm_mask:
        return None
    header = _BitmapInfoHeader(biSize=ctypes.sizeof(_BitmapInfoHeader), biWidth=size, biHeight=-size, biPlanes=1, biBitCount=32)
    bits = ctypes.create_string_buffer(size * size * 4)
    dc = user32.GetDC(None)
    try:
        if gdi32.GetDIBits(dc, hbm_mask, 0, size, bits, ctypes.byref(header), 0) != size:
            return None
    finally:
        user32.ReleaseDC(None, dc)
    mask = Image.frombuffer("RGBA", (size, size), bits.raw, "raw", "BGRA", 0, 1).convert("L")
    # Mask bits: black = opaque icon pixel, white = transparent.
    image.putalpha(mask.point(lambda value: 0 if value > 127 else 255))
    return image


def _process_path(kernel32, process_id: int) -> str | None:
    process = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, process_id)
    if not process:
        return None
    try:
        size = wintypes.DWORD(1024)
        buffer = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(process, 0, buffer, ctypes.byref(size)):
            return buffer.value or None
        return None
    finally:
        kernel32.CloseHandle(process)


if wintypes is not None:

    class _IconInfo(ctypes.Structure):
        _fields_ = [
            ("fIcon", wintypes.BOOL),
            ("xHotspot", wintypes.DWORD),
            ("yHotspot", wintypes.DWORD),
            ("hbmMask", wintypes.HBITMAP),
            ("hbmColor", wintypes.HBITMAP),
        ]

    class _BitmapInfoHeader(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD),
            ("biWidth", wintypes.LONG),
            ("biHeight", wintypes.LONG),
            ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD),
            ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD),
            ("biXPelsPerMeter", wintypes.LONG),
            ("biYPelsPerMeter", wintypes.LONG),
            ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]


_configured: dict[str, object] = {}


def _apis():
    """user32 / kernel32 with their own prototypes (WinDLL, so other modules' ones don't clash)."""
    if "user32" not in _configured:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        user32.GetClipboardOwner.argtypes = []
        user32.GetClipboardOwner.restype = wintypes.HWND
        user32.GetForegroundWindow.argtypes = []
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        user32.PrivateExtractIconsW.argtypes = [
            wintypes.LPCWSTR, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ctypes.POINTER(wintypes.HICON), ctypes.POINTER(wintypes.UINT), wintypes.UINT, wintypes.UINT,
        ]
        user32.PrivateExtractIconsW.restype = wintypes.UINT
        user32.GetIconInfo.argtypes = [wintypes.HICON, ctypes.c_void_p]
        user32.GetIconInfo.restype = wintypes.BOOL
        user32.DestroyIcon.argtypes = [wintypes.HICON]
        user32.DestroyIcon.restype = wintypes.BOOL
        user32.GetDC.argtypes = [wintypes.HWND]
        user32.GetDC.restype = wintypes.HDC
        user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
        user32.ReleaseDC.restype = ctypes.c_int
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_wchar_p, ctypes.POINTER(wintypes.DWORD)]
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        _configured["user32"] = user32
        _configured["kernel32"] = kernel32
    return _configured["user32"], _configured["kernel32"]


def _gdi_api():
    if "gdi32" not in _configured:
        gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
        gdi32.GetDIBits.argtypes = [
            wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT,
        ]
        gdi32.GetDIBits.restype = ctypes.c_int
        gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
        gdi32.DeleteObject.restype = wintypes.BOOL
        _configured["gdi32"] = gdi32
    return _configured["gdi32"]


def _version_api():
    if "version" not in _configured:
        version = ctypes.WinDLL("version", use_last_error=True)
        version.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
        version.GetFileVersionInfoSizeW.restype = wintypes.DWORD
        version.GetFileVersionInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
        version.GetFileVersionInfoW.restype = wintypes.BOOL
        version.VerQueryValueW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.UINT)]
        version.VerQueryValueW.restype = wintypes.BOOL
        _configured["version"] = version
    return _configured["version"]
