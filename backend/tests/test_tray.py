from __future__ import annotations

from backend.app.tray import APP_NAME
from backend.app.tray import TRAY_TITLE
from backend.app.tray import TrayController
from backend.app.tray import menu_labels


class DummyState:
    def __init__(self) -> None:
        self.is_recording_paused = False
        self.cleared = False
        self.view = "panel"

    def set_view(self, view: str) -> dict[str, object]:
        self.view = view
        return {"view": view}

    def toggle_pause(self) -> dict[str, object]:
        self.is_recording_paused = not self.is_recording_paused
        return {"isRecordingPaused": self.is_recording_paused}

    def clear_all_history(self) -> dict[str, object]:
        self.cleared = True
        return {"pinnedRecords": [], "recentRecords": []}


def test_tray_menu_labels_are_localized_and_grouped_for_release() -> None:
    assert menu_labels(is_recording_paused=False) == [
        "显示主面板",
        "暂停记录",
        "打开设置",
        "清空全部历史",
        f"退出 {APP_NAME}",
    ]
    assert menu_labels(is_recording_paused=True)[1] == "继续记录"


def test_tray_controller_uses_localized_title_and_brand_icon() -> None:
    tray = TrayController(
        state=DummyState(),
        show_history=lambda: None,
        show_settings=lambda: None,
        exit_app=lambda: None,
    )

    assert tray.icon.title == TRAY_TITLE

    image = tray._create_icon()
    pixels = list(image.getchannel("R").tobytes())
    greens = list(image.getchannel("G").tobytes())
    blues = list(image.getchannel("B").tobytes())
    color_triplets = list(zip(pixels, greens, blues))
    has_cyan = any(red < 40 and green > 200 and blue > 220 for red, green, blue in color_triplets)
    has_purple = any(red > 120 and blue > 180 for red, green, blue in color_triplets)

    assert has_cyan is True
    assert has_purple is True


def test_tray_clear_all_history_requires_confirmation() -> None:
    state = DummyState()
    tray = TrayController(
        state=state,
        show_history=lambda: None,
        show_settings=lambda: None,
        exit_app=lambda: None,
        confirm_clear=lambda: False,
    )

    tray._handle_clear_all_history(tray.icon, None)

    assert state.cleared is False


def test_tray_clear_all_history_runs_after_confirmation() -> None:
    state = DummyState()
    tray = TrayController(
        state=state,
        show_history=lambda: None,
        show_settings=lambda: None,
        exit_app=lambda: None,
        confirm_clear=lambda: True,
    )

    tray._handle_clear_all_history(tray.icon, None)

    assert state.cleared is True
