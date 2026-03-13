from __future__ import annotations

import ctypes
import queue
import threading
import time

if hasattr(ctypes, "windll"):
    from ctypes import wintypes
else:  # pragma: no cover - non-Windows guard
    wintypes = None


MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
PM_REMOVE = 0x0001
WM_HOTKEY = 0x0312

MODIFIER_MAP = {
    "alt": MOD_ALT,
    "ctrl": MOD_CONTROL,
    "control": MOD_CONTROL,
    "shift": MOD_SHIFT,
    "win": MOD_WIN,
    "meta": MOD_WIN,
}

SPECIAL_KEY_MAP = {
    "space": 0x20,
    "enter": 0x0D,
    "return": 0x0D,
    "delete": 0x2E,
    "backspace": 0x08,
    "tab": 0x09,
    "escape": 0x1B,
    "esc": 0x1B,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
}


def parse_shortcut_binding(binding: str) -> tuple[int, int] | None:
    tokens = [token.strip().lower() for token in binding.split("+") if token.strip()]
    if not tokens:
        return None

    modifiers = 0
    key_code: int | None = None
    for token in tokens:
        if token in MODIFIER_MAP:
            modifiers |= MODIFIER_MAP[token]
            continue

        if token in SPECIAL_KEY_MAP:
            if key_code is not None:
                return None
            key_code = SPECIAL_KEY_MAP[token]
            continue

        if len(token) == 1 and token.isalpha():
            if key_code is not None:
                return None
            key_code = ord(token.upper())
            continue

        if len(token) == 1 and token.isdigit():
            if key_code is not None:
                return None
            key_code = ord(token)
            continue

        if token.startswith("f") and token[1:].isdigit():
            function_number = int(token[1:])
            if 1 <= function_number <= 24 and key_code is None:
                key_code = 0x6F + function_number
                continue

        return None

    if key_code is None:
        return None

    return modifiers, key_code


class NoopGlobalHotkeyManager:
    def update_toggle_panel(self, shortcut: str, callback) -> None:
        return None

    def stop(self) -> None:
        return None


class WindowsGlobalHotkeyManager:
    HOTKEY_ID = 1

    def __init__(self) -> None:
        self._is_windows = hasattr(ctypes, "windll") and wintypes is not None
        if not self._is_windows:
            return

        self.user32 = ctypes.windll.user32
        self._configure_api()
        self._commands: queue.Queue[tuple[str, str | None, object | None]] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def update_toggle_panel(self, shortcut: str, callback) -> None:
        if not self._is_windows:
            return

        self._ensure_thread()
        self._commands.put(("set", shortcut, callback))

    def stop(self) -> None:
        if not self._is_windows or self._thread is None:
            return

        self._stop_event.set()
        self._commands.put(("stop", None, None))
        self._thread.join(timeout=1.0)
        self._thread = None

    def _ensure_thread(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="global-hotkey-manager", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        registered = False
        callback = None

        while not self._stop_event.is_set():
            while True:
                try:
                    command, shortcut, next_callback = self._commands.get_nowait()
                except queue.Empty:
                    break

                if command == "stop":
                    self._stop_event.set()
                    break

                if registered:
                    self.user32.UnregisterHotKey(None, self.HOTKEY_ID)
                    registered = False

                callback = next_callback
                binding = parse_shortcut_binding(shortcut or "")
                if binding is None:
                    continue

                modifiers, key_code = binding
                registered = bool(self.user32.RegisterHotKey(None, self.HOTKEY_ID, modifiers, key_code))

            message = wintypes.MSG()
            while self.user32.PeekMessageW(ctypes.byref(message), None, 0, 0, PM_REMOVE):
                if message.message == WM_HOTKEY and message.wParam == self.HOTKEY_ID and callable(callback):
                    try:
                        callback()
                    except Exception:
                        pass

            time.sleep(0.05)

        if registered:
            self.user32.UnregisterHotKey(None, self.HOTKEY_ID)

    def _configure_api(self) -> None:
        self.user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_uint, ctypes.c_uint]
        self.user32.RegisterHotKey.restype = wintypes.BOOL
        self.user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        self.user32.UnregisterHotKey.restype = wintypes.BOOL
        self.user32.PeekMessageW.argtypes = [
            ctypes.POINTER(wintypes.MSG),
            wintypes.HWND,
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.c_uint,
        ]
        self.user32.PeekMessageW.restype = wintypes.BOOL
