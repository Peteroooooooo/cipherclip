from __future__ import annotations

import os

try:  # pragma: no cover - import guard for non-Windows environments
    import winreg
except ImportError:  # pragma: no cover - non-Windows guard
    winreg = None


class NoopStartupManager:
    def set_enabled(self, enabled: bool, command: str) -> None:
        return None


class WindowsStartupManager:
    RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"

    def __init__(self, *, app_name: str = "CipherClip") -> None:
        self.app_name = app_name
        self._is_windows = os.name == "nt" and winreg is not None

    def set_enabled(self, enabled: bool, command: str) -> None:
        if not self._is_windows or winreg is None:
            return

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            self.RUN_KEY_PATH,
            0,
            winreg.KEY_SET_VALUE,
        ) as run_key:
            if enabled:
                winreg.SetValueEx(run_key, self.app_name, 0, winreg.REG_SZ, command)
                return

            try:
                winreg.DeleteValue(run_key, self.app_name)
            except FileNotFoundError:
                pass


class RuntimeIntegrationController:
    def __init__(
        self,
        *,
        startup_manager,
        hotkey_manager,
        startup_command: str,
        toggle_window,
    ) -> None:
        self.startup_manager = startup_manager
        self.hotkey_manager = hotkey_manager
        self.startup_command = startup_command
        self.toggle_window = toggle_window
        self._launch_on_startup: bool | None = None
        self._toggle_panel_shortcut: str | None = None

    def sync(self, snapshot: dict[str, object]) -> None:
        settings = dict(snapshot.get("settings", {}))
        launch_on_startup = bool(settings.get("launchOnStartup", False))
        shortcuts = dict(settings.get("shortcuts", {}))
        toggle_panel_shortcut = str(shortcuts.get("togglePanel", ""))

        if launch_on_startup != self._launch_on_startup:
            self.startup_manager.set_enabled(launch_on_startup, self.startup_command)
            self._launch_on_startup = launch_on_startup

        if toggle_panel_shortcut != self._toggle_panel_shortcut:
            self.hotkey_manager.update_toggle_panel(toggle_panel_shortcut, self.toggle_window)
            self._toggle_panel_shortcut = toggle_panel_shortcut

    def stop(self) -> None:
        stop = getattr(self.hotkey_manager, "stop", None)
        if callable(stop):
            stop()
