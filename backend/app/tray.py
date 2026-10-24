from __future__ import annotations

from collections.abc import Callable
import ctypes

import pystray
from PIL import Image

from .brand_icon import load_icon
from .state import AppState

APP_NAME = "ClipDeck"
TRAY_TITLE = "ClipDeck 剪贴板历史"


def menu_labels(*, is_recording_paused: bool) -> list[str]:
    return [
        "显示主面板",
        "继续记录" if is_recording_paused else "暂停记录",
        "打开设置",
        "清空全部历史",
        f"退出 {APP_NAME}",
    ]


# uxtheme.dll exports these by ordinal only (Windows 10 1903 and later; Explorer and Office use
# them for their dark menus): SetPreferredAppMode(mode) and FlushMenuThemes().
_SET_PREFERRED_APP_MODE = 135
_FLUSH_MENU_THEMES = 136
_FORCE_DARK = 2


def use_dark_menus() -> bool:
    """Draw this process's native menus (the tray menu) in Windows' dark style instead of the old
    white one. Undocumented, so any failure just leaves the light menu."""
    if not hasattr(ctypes, "windll"):
        return False
    try:
        uxtheme = ctypes.WinDLL("uxtheme")
        set_preferred_app_mode = uxtheme[_SET_PREFERRED_APP_MODE]
        set_preferred_app_mode.argtypes = [ctypes.c_int]
        set_preferred_app_mode.restype = ctypes.c_int
        flush_menu_themes = uxtheme[_FLUSH_MENU_THEMES]
        flush_menu_themes.argtypes = []
        flush_menu_themes.restype = None
        set_preferred_app_mode(_FORCE_DARK)
        flush_menu_themes()
        return True
    except (AttributeError, OSError):
        return False


def confirm_clear_all_history() -> bool:
    if not hasattr(ctypes, "windll"):
        return True

    result = ctypes.windll.user32.MessageBoxW(
        None,
        "确定要清空全部历史记录吗？固定和最近记录都会被删除。",
        APP_NAME,
        0x00000001 | 0x00000030,
    )
    return result == 1


class TrayController:
    def __init__(
        self,
        *,
        state: AppState,
        show_history: Callable[[], None],
        show_settings: Callable[[], None],
        exit_app: Callable[[], None],
        confirm_clear: Callable[[], bool] = confirm_clear_all_history,
    ) -> None:
        self.state = state
        self.show_history = show_history
        self.show_settings = show_settings
        self.exit_app = exit_app
        self.confirm_clear = confirm_clear
        self.icon = pystray.Icon(
            "clipboard-history",
            icon=self._create_icon(),
            title=TRAY_TITLE,
            menu=self._create_menu(),
        )

    def run(self) -> None:
        use_dark_menus()
        self.icon.run_detached()

    def stop(self) -> None:
        self.icon.stop()

    def _create_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem(menu_labels(is_recording_paused=False)[0], self._handle_open_history),
            pystray.MenuItem(
                lambda _item: menu_labels(is_recording_paused=self.state.is_recording_paused)[1],
                self._handle_toggle_pause,
            ),
            pystray.MenuItem(menu_labels(is_recording_paused=False)[2], self._handle_open_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(menu_labels(is_recording_paused=False)[3], self._handle_clear_all_history),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(menu_labels(is_recording_paused=False)[4], self._handle_exit),
        )

    @staticmethod
    def _create_icon() -> Image.Image:
        return load_icon(64)

    def _handle_open_history(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self.state.set_view("panel")
        self.show_history()

    def _handle_toggle_pause(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self.state.toggle_pause()
        self.icon.update_menu()

    def _handle_open_settings(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self.state.set_view("settings")
        self.show_settings()

    def _handle_clear_all_history(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        if self.confirm_clear():
            self.state.clear_all_history()

    def _handle_exit(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self.exit_app()


