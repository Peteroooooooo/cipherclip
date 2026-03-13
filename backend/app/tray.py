from __future__ import annotations

from collections.abc import Callable
import ctypes
import math

import pystray
from PIL import Image, ImageDraw

from .state import AppState

APP_NAME = "CipherClip"
TRAY_TITLE = "CipherClip 剪贴板历史"


def menu_labels(*, is_recording_paused: bool) -> list[str]:
    return [
        "显示主面板",
        "继续记录" if is_recording_paused else "暂停记录",
        "打开设置",
        "清空全部历史",
        f"退出 {APP_NAME}",
    ]


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
        image = Image.new("RGBA", (64, 64), (10, 10, 12, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((10, 6, 50, 58), radius=12, fill=(22, 22, 26, 235), outline=(255, 255, 255, 38), width=1)
        draw.polygon([(36, 6), (50, 20), (36, 20)], fill=(32, 32, 38, 240), outline=(255, 255, 255, 28))
        draw.line((18, 24, 34, 24), fill=(0, 240, 255, 220), width=4)
        draw.line((18, 31, 30, 31), fill=(0, 240, 255, 150), width=4)
        draw.line((18, 38, 26, 38), fill=(0, 240, 255, 96), width=4)
        _draw_rotated_pen(draw, center=(43, 32), angle_deg=25)
        return image

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


def _draw_rotated_pen(draw: ImageDraw.ImageDraw, *, center: tuple[float, float], angle_deg: float) -> None:
    body = [(0, -12), (4, -12), (4, 8), (0, 8)]
    cap = [(0, -12), (4, -12), (4, -8), (0, -8)]
    tip = [(0, 8), (2, 14), (4, 8)]

    draw.polygon(_rotate_polygon(body, center=center, angle_deg=angle_deg), fill=(168, 85, 247, 235))
    draw.polygon(_rotate_polygon(cap, center=center, angle_deg=angle_deg), fill=(192, 132, 252, 200))
    draw.polygon(_rotate_polygon(tip, center=center, angle_deg=angle_deg), fill=(168, 85, 247, 180))


def _rotate_polygon(
    points: list[tuple[float, float]],
    *,
    center: tuple[float, float],
    angle_deg: float,
) -> list[tuple[float, float]]:
    angle = math.radians(angle_deg)
    cos_value = math.cos(angle)
    sin_value = math.sin(angle)
    center_x, center_y = center
    rotated: list[tuple[float, float]] = []
    for point_x, point_y in points:
        rotated_x = center_x + (point_x * cos_value) - (point_y * sin_value)
        rotated_y = center_y + (point_x * sin_value) + (point_y * cos_value)
        rotated.append((rotated_x, rotated_y))
    return rotated
