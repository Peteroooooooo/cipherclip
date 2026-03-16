from __future__ import annotations

import ctypes
import threading

if hasattr(ctypes, "windll"):
    from ctypes import wintypes
else:  # pragma: no cover - non-Windows guard
    wintypes = None


ERROR_ALREADY_EXISTS = 183
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 258
EVENT_MODIFY_STATE = 0x0002


class NoopSingleInstanceManager:
    def acquire_primary(self) -> bool:
        return True

    def signal_primary(self) -> bool:
        return False

    def start_activation_listener(self, on_activate) -> None:
        return None

    def stop(self) -> None:
        return None


class WindowsSingleInstanceManager:
    def __init__(
        self,
        *,
        mutex_name: str = "Local\\CipherClip.SingleInstance",
        event_name: str = "Local\\CipherClip.Activate",
        kernel32=None,
        is_windows: bool | None = None,
        wait_timeout_ms: int = 100,
    ) -> None:
        self._is_windows = hasattr(ctypes, "windll") and wintypes is not None if is_windows is None else is_windows
        self.mutex_name = mutex_name
        self.event_name = event_name
        self.wait_timeout_ms = wait_timeout_ms
        self._mutex_handle = None
        self._event_handle = None
        self._listener_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        if not self._is_windows:
            self.kernel32 = None
            return

        self.kernel32 = kernel32 or ctypes.windll.kernel32
        if kernel32 is None:
            self._configure_api()

    def acquire_primary(self) -> bool:
        if not self._is_windows or self.kernel32 is None:
            return True

        if self._mutex_handle is not None:
            return True

        self._mutex_handle = self.kernel32.CreateMutexW(None, False, self.mutex_name)
        if not self._mutex_handle:
            raise OSError("Failed to create single-instance mutex.")
        already_exists = self.kernel32.GetLastError() == ERROR_ALREADY_EXISTS

        self._event_handle = self.kernel32.CreateEventW(None, True, False, self.event_name)
        if not self._event_handle:
            self._close_handles()
            raise OSError("Failed to create single-instance activation event.")

        return not already_exists

    def signal_primary(self) -> bool:
        if not self._is_windows or self.kernel32 is None:
            return False

        event_handle = self._event_handle
        close_after_signal = False
        if event_handle is None:
            event_handle = self.kernel32.OpenEventW(EVENT_MODIFY_STATE, False, self.event_name)
            close_after_signal = bool(event_handle)

        if not event_handle:
            return False

        try:
            return bool(self.kernel32.SetEvent(event_handle))
        finally:
            if close_after_signal:
                self.kernel32.CloseHandle(event_handle)

    def start_activation_listener(self, on_activate) -> None:
        if not self._is_windows or self.kernel32 is None or self._event_handle is None:
            return

        if self._listener_thread is not None and self._listener_thread.is_alive():
            return

        self._stop_event.clear()
        self._listener_thread = threading.Thread(
            target=self._listen_for_activation,
            args=(on_activate,),
            name="single-instance-activation",
            daemon=True,
        )
        self._listener_thread.start()

    def stop(self) -> None:
        if not self._is_windows or self.kernel32 is None:
            return

        should_wake_listener = self._listener_thread is not None
        self._stop_event.set()
        if should_wake_listener and self._event_handle is not None:
            self.kernel32.SetEvent(self._event_handle)
        if self._listener_thread is not None:
            self._listener_thread.join(timeout=1.0)
            self._listener_thread = None

        self._close_handles()

    def _listen_for_activation(self, on_activate) -> None:
        while not self._stop_event.is_set():
            wait_result = self.kernel32.WaitForSingleObject(self._event_handle, self.wait_timeout_ms)
            if wait_result == WAIT_TIMEOUT:
                continue
            if wait_result != WAIT_OBJECT_0:
                break

            self.kernel32.ResetEvent(self._event_handle)
            if self._stop_event.is_set():
                break

            try:
                on_activate()
            except Exception:
                pass

    def _close_handles(self) -> None:
        if self._event_handle is not None:
            self.kernel32.CloseHandle(self._event_handle)
            self._event_handle = None
        if self._mutex_handle is not None:
            self.kernel32.CloseHandle(self._mutex_handle)
            self._mutex_handle = None

    def _configure_api(self) -> None:
        if wintypes is None:
            return

        self.kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        self.kernel32.CreateMutexW.restype = wintypes.HANDLE
        self.kernel32.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
        self.kernel32.CreateEventW.restype = wintypes.HANDLE
        self.kernel32.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
        self.kernel32.OpenEventW.restype = wintypes.HANDLE
        self.kernel32.SetEvent.argtypes = [wintypes.HANDLE]
        self.kernel32.SetEvent.restype = wintypes.BOOL
        self.kernel32.ResetEvent.argtypes = [wintypes.HANDLE]
        self.kernel32.ResetEvent.restype = wintypes.BOOL
        self.kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.kernel32.WaitForSingleObject.restype = wintypes.DWORD
        self.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel32.CloseHandle.restype = wintypes.BOOL
        self.kernel32.GetLastError.argtypes = []
        self.kernel32.GetLastError.restype = wintypes.DWORD
