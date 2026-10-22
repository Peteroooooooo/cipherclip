from __future__ import annotations

import base64
import ctypes
import io
from collections.abc import Callable
from pathlib import Path

if hasattr(ctypes, "windll"):
    from ctypes import wintypes
else:  # pragma: no cover - non-Windows guard
    wintypes = None

DWMWA_NCRENDERING_POLICY = 2
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_BORDER_COLOR = 34
DWMWA_SYSTEMBACKDROP_TYPE = 38
DWMNCRP_DISABLED = 1
DWMWCP_DONOTROUND = 1
DWMWA_COLOR_NONE = 0xFFFFFFFE
DWMSBT_NONE = 1
DWM_BB_ENABLE = 0x1
WDA_NONE = 0x0
WDA_EXCLUDEFROMCAPTURE = 0x11

# The desktop snapshot behind the glass is shrunk, blurred and saturated before it reaches the
# page. Heavy blur hides the low resolution, and a small JPEG crosses into WebView2 quickly.
BACKDROP_DOWNSCALE = 4
BACKDROP_DEFAULT_BLUR_DIP = 10
BACKDROP_DEFAULT_SATURATION = 100
BACKDROP_JPEG_QUALITY = 72

MONITOR_DEFAULTTONEAREST = 2
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SM_SWAPBUTTON = 23
VK_LBUTTON = 0x01
VK_RBUTTON = 0x02
CURSOR_GAP = 12


GLASS_LIVE = "live"
GLASS_SNAPSHOT = "snapshot"


class GlassBackdrop:
    """Handle to the installed glass: which mode is active and how to reshape it."""

    def __init__(self, form, mode: str, live_dll=None, *, filtered: bool = False) -> None:
        self._form = form
        self.mode = mode
        self._live_dll = live_dll
        self._filtered = filtered

    @property
    def live_available(self) -> bool:
        return self._live_dll is not None

    @property
    def filtered(self) -> bool:
        """True when live glass is the captured desktop with real blur and colour filters (all
        backdrop settings apply live), False when it is Windows' fixed host blur."""
        if not self._filtered:
            return False
        return self._live_dll.cc_live_filter_status() == 1

    def set_filter(self, *, blur_dip: float, saturation: float) -> None:
        """Backdrop filters for the filtered live glass, as CSS factors (1 = unchanged)."""
        if not self._filtered:
            return
        sigma = blur_dip * _dpi_scale(self._form.Handle.ToInt64())

        def apply() -> None:
            self._live_dll.cc_live_filter_set(ctypes.c_float(sigma), ctypes.c_float(saturation))

        _invoke(self._form, apply)

    def use_live(self, enabled: bool) -> str:
        """Switch between the live compositor blur and the page-painted snapshot."""
        if self._live_dll is None:
            self.mode = GLASS_SNAPSHOT
            return self.mode

        def apply() -> None:
            self._live_dll.cc_live_backdrop_set_visible(1 if enabled else 0)

        _invoke(self._form, apply)
        self.mode = GLASS_LIVE if enabled else GLASS_SNAPSHOT
        return self.mode

    def set_live_strength(self, strength: float) -> None:
        """Fade the live blur between none (0, the desktop shows through sharp) and Windows' full,
        fixed-strength blur (1)."""
        if self._live_dll is None or not hasattr(self._live_dll, "cc_live_backdrop_set_opacity"):
            return

        def apply() -> None:
            self._live_dll.cc_live_backdrop_set_opacity(ctypes.c_float(strength))

        _invoke(self._form, apply)

    def set_corner_radius(self, radius_dip: float) -> None:
        if self._live_dll is None:
            return
        scale = _dpi_scale(self._form.Handle.ToInt64())

        def apply() -> None:
            self._live_dll.cc_live_backdrop_set_radius(ctypes.c_float(radius_dip * scale))

        _invoke(self._form, apply)


def install_glass_backdrop(
    window,
    *,
    on_deactivate: Callable[[], None] | None = None,
    shadow_margin_dip: int = 16,
    corner_radius_dip: float = 24,
    prefer_live: bool = True,
) -> GlassBackdrop | None:
    """Turn the native WinForms host into a fully transparent, frameless surface with glass.

    The page inside WebView2 cannot read the desktop behind the window, so live blur has to come
    from the Windows compositor. When the native helper (backend/native, built by
    scripts/build-native.ps1) is available, a live host-backdrop visual is hung under the page,
    clipped to the panel's rounded rectangle. Otherwise the page paints a blurred desktop
    snapshot itself (see `capture_desktop_backdrop`). DWM's own corners, border and shadow are
    switched off in both modes; the page draws the outline. Returns None when the window has no
    WinForms host (tests, non-Windows).
    """
    form = getattr(window, "native", None)
    if form is None or wintypes is None:
        return None

    try:
        from System import Action
        from System import EventHandler
        from System.Drawing import Color
        from Microsoft.Win32 import SystemEvents
    except ImportError:  # pragma: no cover - pythonnet missing
        return None

    # The live visual is attached whenever the helper exists, so the user can switch modes later
    # without restarting; `prefer_live` only decides whether it starts visible.
    live_dll = _load_live_backdrop()
    result: dict[str, object] = {"mode": GLASS_SNAPSHOT, "attached": False}

    def resize_live(_sender=None, _args=None) -> None:
        if result["attached"]:
            live_dll.cc_live_backdrop_resize(ctypes.c_float(form.Width), ctypes.c_float(form.Height))

    def apply() -> None:
        form.BackColor = Color.Black
        browser = getattr(form, "browser", None)
        webview_control = getattr(browser, "webview", None)
        if webview_control is not None:
            webview_control.DefaultBackgroundColor = Color.Transparent
        hwnd = form.Handle.ToInt64()
        _make_transparent(hwnd)
        if live_dll is not None:
            scale = _dpi_scale(hwnd)
            status = live_dll.cc_live_backdrop_attach(
                wintypes.HWND(hwnd),
                ctypes.c_float(shadow_margin_dip * scale),
                ctypes.c_float(corner_radius_dip * scale),
            )
            if status == 0:
                result["attached"] = True
                resize_live()
                live_dll.cc_live_backdrop_set_visible(1 if prefer_live else 0)
                result["mode"] = GLASS_LIVE if prefer_live else GLASS_SNAPSHOT
                # Real, adjustable blur from a capture that leaves this window out. Falls back to
                # the fixed host blur when the system cannot deliver it.
                if hasattr(live_dll, "cc_live_filter_start"):
                    result["filtered"] = live_dll.cc_live_filter_start(wintypes.HWND(hwnd)) == 0

    def reapply(_sender=None, _args=None) -> None:
        # pywebview resets the backdrop to Mica on theme changes; restore transparency afterwards.
        _make_transparent(form.Handle.ToInt64())

    form.Invoke(Action(apply))
    form.SizeChanged += EventHandler(resize_live)
    SystemEvents.UserPreferenceChanged += reapply
    if on_deactivate is not None:
        form.Deactivate += EventHandler(lambda _sender, _args: on_deactivate())
    return GlassBackdrop(
        form,
        str(result["mode"]),
        live_dll if result["attached"] else None,
        filtered=bool(result.get("filtered")),
    )


def live_backdrop_dll_path() -> Path:
    import sys

    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root is not None:
        return Path(bundle_root) / "native" / "cipherclip_backdrop.dll"
    return Path(__file__).resolve().parents[1] / "native" / "bin" / "cipherclip_backdrop.dll"


def _load_live_backdrop():
    path = live_backdrop_dll_path()
    if not path.exists():
        return None
    try:
        dll = ctypes.WinDLL(str(path))
    except OSError:
        return None
    dll.cc_live_backdrop_attach.argtypes = [wintypes.HWND, ctypes.c_float, ctypes.c_float]
    dll.cc_live_backdrop_attach.restype = ctypes.c_int
    dll.cc_live_backdrop_resize.argtypes = [ctypes.c_float, ctypes.c_float]
    dll.cc_live_backdrop_set_radius.argtypes = [ctypes.c_float]
    dll.cc_live_backdrop_set_visible.argtypes = [ctypes.c_int]
    if hasattr(dll, "cc_live_backdrop_set_opacity"):
        dll.cc_live_backdrop_set_opacity.argtypes = [ctypes.c_float]
    if hasattr(dll, "cc_live_filter_start"):
        dll.cc_live_filter_start.argtypes = [wintypes.HWND]
        dll.cc_live_filter_start.restype = ctypes.c_int
        dll.cc_live_filter_set.argtypes = [ctypes.c_float] * 2
        dll.cc_live_filter_status.restype = ctypes.c_int
    if hasattr(dll, "cc_window_drag_begin"):
        dll.cc_window_drag_begin.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int]
        dll.cc_window_drag_begin.restype = ctypes.c_int
    return dll


_drag_dll: object = None


def begin_window_drag(window, grab: tuple[int, int], *, elastic: bool) -> None:
    """Drag the window with the pointer until the button is released.

    `grab` is the pressed point inside the window (physical pixels). The native helper follows
    the pointer once per display frame, on a spring when `elastic`; without it the window just
    tracks the pointer from this (bridge) thread.
    """
    form = getattr(window, "native", None)
    if form is None or wintypes is None:
        return
    global _drag_dll
    if _drag_dll is None:
        _drag_dll = _load_live_backdrop() or False
    hwnd = wintypes.HWND(form.Handle.ToInt64())
    if _drag_dll and hasattr(_drag_dll, "cc_window_drag_begin"):
        _drag_dll.cc_window_drag_begin(hwnd, int(grab[0]), int(grab[1]), 1 if elastic else 0)
        return

    user32 = ctypes.windll.user32
    button = VK_RBUTTON if user32.GetSystemMetrics(SM_SWAPBUTTON) else VK_LBUTTON
    while user32.GetAsyncKeyState(button) & 0x8000:
        point = _cursor_point()
        if point is not None:
            user32.SetWindowPos(
                hwnd, None, point[0] - int(grab[0]), point[1] - int(grab[1]), 0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE
            )
        ctypes.windll.dwmapi.DwmFlush()


# Windows' host backdrop has one blur strength (about this many DIPs). In live mode the Backdrop
# Blur setting fades it in up to that point instead of changing its radius.
LIVE_FULL_BLUR_DIP = 12


def live_blur_strength(backdrop_blur_dip: float) -> float:
    return max(0.0, min(1.0, float(backdrop_blur_dip) / LIVE_FULL_BLUR_DIP))


def _dpi_scale(hwnd: int) -> float:
    user32 = ctypes.windll.user32
    user32.GetDpiForWindow.argtypes = [wintypes.HWND]
    user32.GetDpiForWindow.restype = wintypes.UINT
    return (user32.GetDpiForWindow(hwnd) or 96) / 96


def _invoke(form, action: Callable[[], None]) -> None:
    from System import Action

    if getattr(form, "InvokeRequired", False):
        form.Invoke(Action(action))
    else:
        action()


def backdrop_payload(
    *,
    jpeg_bytes: bytes,
    monitor: tuple[int, int, int, int],
    window_origin: tuple[int, int],
) -> dict[str, object]:
    """What the page needs to align the snapshot: the image, the monitor rect it covers and
    where the window sits, all in physical pixels."""
    left, top, right, bottom = monitor
    return {
        "url": "data:image/jpeg;base64," + base64.b64encode(jpeg_bytes).decode("ascii"),
        "left": left,
        "top": top,
        "width": right - left,
        "height": bottom - top,
        **window_position_payload(window_origin),
    }


def window_position_payload(window_origin: tuple[int, int]) -> dict[str, int]:
    return {"windowLeft": window_origin[0], "windowTop": window_origin[1]}


def window_origin(window) -> tuple[int, int] | None:
    form = getattr(window, "native", None)
    if form is None or wintypes is None:
        return None
    rect = wintypes.RECT()
    if not ctypes.windll.user32.GetWindowRect(wintypes.HWND(form.Handle.ToInt64()), ctypes.byref(rect)):
        return None
    return rect.left, rect.top


def capture_desktop_backdrop(window, appearance: dict[str, object] | None = None) -> dict[str, object] | None:
    """Snapshot the monitor under the window, pre-blurred, for the page's glass background.

    The window is excluded from capture for the duration of the grab, so this works whether it
    is shown or hidden. The image stays in memory and is only handed to the page; nothing is
    written to disk.
    """
    form = getattr(window, "native", None)
    if form is None or wintypes is None:
        return None

    try:
        from PIL import Image
        from PIL import ImageEnhance
        from PIL import ImageFilter
        from PIL import ImageGrab
    except ImportError:  # pragma: no cover - Pillow is a runtime dependency
        return None

    hwnd = form.Handle.ToInt64()
    monitor = _monitor_rect_for_window(hwnd)
    origin = window_origin(window)
    if monitor is None or origin is None:
        return None

    user32 = ctypes.windll.user32
    user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
    excluded = bool(user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE))
    try:
        if excluded:
            ctypes.windll.dwmapi.DwmFlush()  # let DWM drop the window from the next frame
        shot = ImageGrab.grab(bbox=monitor, all_screens=True)
    except OSError:
        return None
    finally:
        if excluded:
            # Restore normal capture so the panel still shows up in the user's screenshots.
            user32.SetWindowDisplayAffinity(hwnd, WDA_NONE)

    width, height = shot.size
    small = shot.convert("RGB").resize(
        (max(1, width // BACKDROP_DOWNSCALE), max(1, height // BACKDROP_DOWNSCALE)),
        Image.Resampling.BILINEAR,
    )
    settings = appearance or {}
    # Blur is chosen in CSS px; convert to pixels of the downscaled image.
    blur_px = float(settings.get("backdropBlur", BACKDROP_DEFAULT_BLUR_DIP)) * _dpi_scale(hwnd) / BACKDROP_DOWNSCALE
    if blur_px > 0:
        small = small.filter(ImageFilter.GaussianBlur(blur_px))
    small = ImageEnhance.Color(small).enhance(float(settings.get("backdropSaturation", BACKDROP_DEFAULT_SATURATION)) / 100)

    buffer = io.BytesIO()
    small.save(buffer, "JPEG", quality=BACKDROP_JPEG_QUALITY)
    return backdrop_payload(jpeg_bytes=buffer.getvalue(), monitor=monitor, window_origin=origin)


def move_window_near_pointer(window) -> None:
    """Place the window next to the text caret (or mouse pointer), clamped to the work area."""
    form = getattr(window, "native", None)
    if form is None or wintypes is None:
        return

    user32 = ctypes.windll.user32
    hwnd = wintypes.HWND(form.Handle.ToInt64())
    anchor = _caret_screen_point() or _cursor_point()
    if anchor is None:
        return

    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    work_area = _work_area_for_point(anchor)
    if work_area is None:
        return

    x, y = place_rect_near_anchor(
        anchor=anchor,
        size=(width, height),
        work_area=work_area,
    )
    user32.SetWindowPos(hwnd, None, x, y, 0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)


def place_rect_near_anchor(
    *,
    anchor: tuple[int, int],
    size: tuple[int, int],
    work_area: tuple[int, int, int, int],
) -> tuple[int, int]:
    anchor_x, anchor_y = anchor
    width, height = size
    left, top, right, bottom = work_area

    x = anchor_x - width // 2
    y = anchor_y + CURSOR_GAP
    if y + height > bottom:
        y = anchor_y - CURSOR_GAP - height

    x = max(left, min(x, right - width))
    y = max(top, min(y, bottom - height))
    return x, y


class _DWM_BLURBEHIND(ctypes.Structure):
    _fields_ = (
        [
            ("dwFlags", wintypes.DWORD),
            ("fEnable", wintypes.BOOL),
            ("hRgnBlur", wintypes.HRGN),
            ("fTransitionOnMaximized", wintypes.BOOL),
        ]
        if wintypes is not None
        else []
    )


def _set_dwm_attribute(hwnd: int, attribute: int, payload: ctypes._SimpleCData) -> None:
    dwmapi = ctypes.windll.dwmapi
    dwmapi.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    dwmapi.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(payload), ctypes.sizeof(payload))


def _make_transparent(hwnd: int) -> None:
    dwmapi = ctypes.windll.dwmapi
    dwmapi.DwmExtendFrameIntoClientArea.argtypes = [wintypes.HWND, ctypes.c_void_p]
    dwmapi.DwmEnableBlurBehindWindow.argtypes = [wintypes.HWND, ctypes.POINTER(_DWM_BLURBEHIND)]

    margins = (ctypes.c_int * 4)(-1, -1, -1, -1)
    dwmapi.DwmExtendFrameIntoClientArea(hwnd, margins)
    _set_dwm_attribute(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, ctypes.c_int(DWMSBT_NONE))
    # Since Windows 8 "blur behind" no longer blurs: it only makes DWM honour per-pixel alpha.
    blur_behind = _DWM_BLURBEHIND(DWM_BB_ENABLE, True, None, False)
    dwmapi.DwmEnableBlurBehindWindow(hwnd, ctypes.byref(blur_behind))
    # The page draws its own rounded outline, so DWM's corners, border and shadow all go.
    _set_dwm_attribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.c_int(DWMWCP_DONOTROUND))
    _set_dwm_attribute(hwnd, DWMWA_BORDER_COLOR, ctypes.c_uint(DWMWA_COLOR_NONE))
    _set_dwm_attribute(hwnd, DWMWA_NCRENDERING_POLICY, ctypes.c_int(DWMNCRP_DISABLED))


def _monitor_rect_for_window(hwnd: int) -> tuple[int, int, int, int] | None:
    user32 = ctypes.windll.user32
    user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.MonitorFromWindow.restype = wintypes.HMONITOR
    monitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    info = _MONITORINFO(cbSize=ctypes.sizeof(_MONITORINFO))
    if not monitor or not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        return None
    rect = info.rcMonitor
    return rect.left, rect.top, rect.right, rect.bottom


class _GUITHREADINFO(ctypes.Structure):
    _fields_ = (
        [
            ("cbSize", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("hwndActive", wintypes.HWND),
            ("hwndFocus", wintypes.HWND),
            ("hwndCapture", wintypes.HWND),
            ("hwndMenuOwner", wintypes.HWND),
            ("hwndMoveSize", wintypes.HWND),
            ("hwndCaret", wintypes.HWND),
            ("rcCaret", wintypes.RECT),
        ]
        if wintypes is not None
        else []
    )


class _MONITORINFO(ctypes.Structure):
    _fields_ = (
        [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", wintypes.RECT),
            ("rcWork", wintypes.RECT),
            ("dwFlags", wintypes.DWORD),
        ]
        if wintypes is not None
        else []
    )


def _caret_screen_point() -> tuple[int, int] | None:
    user32 = ctypes.windll.user32
    foreground = user32.GetForegroundWindow()
    if not foreground:
        return None

    thread_id = user32.GetWindowThreadProcessId(foreground, None)
    info = _GUITHREADINFO(cbSize=ctypes.sizeof(_GUITHREADINFO))
    if not user32.GetGUIThreadInfo(thread_id, ctypes.byref(info)) or not info.hwndCaret:
        return None

    point = wintypes.POINT(info.rcCaret.left, info.rcCaret.bottom)
    if not user32.ClientToScreen(info.hwndCaret, ctypes.byref(point)):
        return None
    return point.x, point.y


def _cursor_point() -> tuple[int, int] | None:
    point = wintypes.POINT()
    if not ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
        return None
    return point.x, point.y


def _work_area_for_point(point: tuple[int, int]) -> tuple[int, int, int, int] | None:
    user32 = ctypes.windll.user32
    user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
    user32.MonitorFromPoint.restype = wintypes.HMONITOR
    monitor = user32.MonitorFromPoint(wintypes.POINT(*point), MONITOR_DEFAULTTONEAREST)
    info = _MONITORINFO(cbSize=ctypes.sizeof(_MONITORINFO))
    if not monitor or not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        return None
    work = info.rcWork
    return work.left, work.top, work.right, work.bottom
