from __future__ import annotations

import threading
import time

from backend.app.single_instance import ERROR_ALREADY_EXISTS
from backend.app.single_instance import WAIT_OBJECT_0
from backend.app.single_instance import WAIT_TIMEOUT
from backend.app.single_instance import WindowsSingleInstanceManager


class FakeKernel32:
    def __init__(self) -> None:
        self._next_handle = 1
        self._last_error = 0
        self._handles: dict[int, tuple[str, object]] = {}
        self._mutexes: dict[str, int] = {}
        self._events: dict[str, int] = {}

    def CreateMutexW(self, _security_attributes, _initial_owner, name: str) -> int:
        existing_handle = self._mutexes.get(name)
        if existing_handle is not None:
            self._last_error = ERROR_ALREADY_EXISTS
            return existing_handle

        handle = self._allocate_handle("mutex", name)
        self._mutexes[name] = handle
        self._last_error = 0
        return handle

    def CreateEventW(self, _security_attributes, _manual_reset, initial_state, name: str) -> int:
        existing_handle = self._events.get(name)
        if existing_handle is not None:
            return existing_handle

        event = threading.Event()
        if initial_state:
            event.set()

        handle = self._allocate_handle("event", event)
        self._events[name] = handle
        return handle

    def OpenEventW(self, _desired_access, _inherit_handle, name: str) -> int:
        return self._events.get(name, 0)

    def WaitForSingleObject(self, handle: int, timeout_ms: int) -> int:
        kind, target = self._handles[handle]
        assert kind == "event"

        if target.wait(timeout_ms / 1000):
            return WAIT_OBJECT_0
        return WAIT_TIMEOUT

    def SetEvent(self, handle: int) -> int:
        kind, target = self._handles[handle]
        assert kind == "event"
        target.set()
        return 1

    def ResetEvent(self, handle: int) -> int:
        kind, target = self._handles[handle]
        assert kind == "event"
        target.clear()
        return 1

    def CloseHandle(self, handle: int) -> int:
        return 1 if handle in self._handles else 0

    def GetLastError(self) -> int:
        return self._last_error

    def _allocate_handle(self, kind: str, target: object) -> int:
        handle = self._next_handle
        self._next_handle += 1
        self._handles[handle] = (kind, target)
        return handle


def test_windows_single_instance_manager_detects_existing_primary_instance() -> None:
    kernel32 = FakeKernel32()
    first_manager = WindowsSingleInstanceManager(kernel32=kernel32, is_windows=True, wait_timeout_ms=10)
    second_manager = WindowsSingleInstanceManager(kernel32=kernel32, is_windows=True, wait_timeout_ms=10)

    assert first_manager.acquire_primary() is True
    assert second_manager.acquire_primary() is False

    second_manager.stop()
    first_manager.stop()


def test_windows_single_instance_manager_signals_activation_callback() -> None:
    kernel32 = FakeKernel32()
    manager = WindowsSingleInstanceManager(kernel32=kernel32, is_windows=True, wait_timeout_ms=10)
    activations = {"count": 0}

    assert manager.acquire_primary() is True
    manager.start_activation_listener(lambda: activations.__setitem__("count", activations["count"] + 1))
    assert manager.signal_primary() is True

    deadline = time.time() + 1.0
    while activations["count"] == 0 and time.time() < deadline:
        time.sleep(0.01)

    manager.stop()

    assert activations["count"] == 1


def test_secondary_manager_stop_does_not_trigger_activation() -> None:
    kernel32 = FakeKernel32()
    primary_manager = WindowsSingleInstanceManager(kernel32=kernel32, is_windows=True, wait_timeout_ms=10)
    secondary_manager = WindowsSingleInstanceManager(kernel32=kernel32, is_windows=True, wait_timeout_ms=10)
    activations = {"count": 0}

    assert primary_manager.acquire_primary() is True
    primary_manager.start_activation_listener(lambda: activations.__setitem__("count", activations["count"] + 1))
    assert secondary_manager.acquire_primary() is False

    secondary_manager.stop()
    time.sleep(0.05)
    primary_manager.stop()

    assert activations["count"] == 0
