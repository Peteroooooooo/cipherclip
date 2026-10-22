import threading
from pathlib import Path
from types import SimpleNamespace
from types import FunctionType

from backend.app.tray import menu_labels
from backend.app.window import AppWindowController
from backend.app.window import resolve_runtime_mode
from backend.app.window import resolve_frontend_entry
from backend.app.window import set_window_on_top

TEST_PROJECT_ROOT = Path("C:/workspace/ClipDeck")


def test_resolve_frontend_entry_prefers_dev_server_and_falls_back_to_dist():
    project_root = TEST_PROJECT_ROOT

    dev_entry = resolve_frontend_entry(project_root=project_root, dev_mode=True)
    prod_entry = resolve_frontend_entry(project_root=project_root, dev_mode=False)

    assert dev_entry == "http://127.0.0.1:5173"
    assert str(prod_entry).endswith("frontend/dist/index.html")


def test_menu_labels_reflect_recording_state():
    active_labels = menu_labels(is_recording_paused=False)
    paused_labels = menu_labels(is_recording_paused=True)

    assert active_labels[1] == "暂停记录"
    assert paused_labels[1] == "继续记录"


def test_runtime_mode_defaults_to_static_build_when_dist_exists(tmp_path: Path):
    project_root = tmp_path
    dist_index = project_root / "frontend" / "dist" / "index.html"
    dist_index.parent.mkdir(parents=True)
    dist_index.write_text("<!doctype html>", encoding="utf-8")

    dev_mode, debug_mode = resolve_runtime_mode(project_root=project_root, env={})

    assert dev_mode is False
    assert debug_mode is False


def test_runtime_mode_can_be_forced_to_dev_and_debug():
    project_root = TEST_PROJECT_ROOT

    dev_mode, debug_mode = resolve_runtime_mode(
        project_root=project_root,
        env={"CLIPBOARD_DEV": "1", "CLIPBOARD_DEBUG": "1"},
    )

    assert dev_mode is True
    assert debug_mode is True


def test_window_controller_hides_instead_of_closing_when_close_to_tray_is_enabled():
    bridge = SimpleNamespace(bind_hide_window=lambda _callback: None)
    hidden = {"value": False}
    controller = AppWindowController(
        project_root=TEST_PROJECT_ROOT,
        bridge=bridge,
        snapshot_provider=lambda: {},
        dev_mode=False,
        close_to_tray_provider=lambda: True,
    )
    controller.window = SimpleNamespace(hide=lambda: hidden.__setitem__("value", True))

    should_cancel = controller._handle_closing()

    assert should_cancel is False
    assert hidden["value"] is True


def test_window_controller_can_start_hidden_and_toggle_visibility():
    bridge = SimpleNamespace(bind_hide_window=lambda _callback: None)
    calls = {
        "show": 0,
        "hide": 0,
        "restore": 0,
    }
    controller = AppWindowController(
        project_root=TEST_PROJECT_ROOT,
        bridge=bridge,
        snapshot_provider=lambda: {},
        dev_mode=False,
        start_hidden=True,
        close_to_tray_provider=lambda: True,
    )
    controller.window = SimpleNamespace(
        show=lambda: calls.__setitem__("show", calls["show"] + 1),
        hide=lambda: calls.__setitem__("hide", calls["hide"] + 1),
        restore=lambda: calls.__setitem__("restore", calls["restore"] + 1),
    )

    assert controller.is_hidden is True

    controller.toggle_visibility()
    controller.toggle_visibility()

    assert calls["show"] == 1
    assert calls["restore"] == 1
    assert calls["hide"] == 1


def test_hiding_puts_the_page_to_sleep_and_showing_wakes_it_in_order(monkeypatch):
    import backend.app.window as window_module

    monkeypatch.setattr(window_module, "move_window_near_pointer", lambda _window: None)
    scripts: list[str] = []
    controller = AppWindowController(
        project_root=TEST_PROJECT_ROOT,
        bridge=SimpleNamespace(),
        snapshot_provider=lambda: {},
        dev_mode=False,
        start_hidden=True,
        set_on_top_callback=lambda _window, _enabled: None,
        backdrop_capture=lambda _window, _appearance: None,
    )
    controller.window = SimpleNamespace(
        show=lambda: None,
        hide=lambda: None,
        restore=lambda: None,
        evaluate_js=scripts.append,
    )
    controller._is_loaded = True
    started: list[threading.Thread] = []
    original_start = threading.Thread.start

    def start_and_track(thread):
        started.append(thread)
        original_start(thread)

    monkeypatch.setattr(threading.Thread, "start", start_and_track)

    controller.show()
    controller.hide()
    controller.hide()  # already hidden: nothing more to send
    for thread in started:
        thread.join(timeout=2)

    assert len(scripts) == 2
    assert "'clipdeck:reveal'" in scripts[0] and '"seq": 1' in scripts[0]
    assert "'clipdeck:sleep'" in scripts[1] and '"seq": 2' in scripts[1]


def test_page_loaded_in_the_tray_sleeps_then_renders_in_the_background():
    order: list[str] = []
    controller = AppWindowController(
        project_root=TEST_PROJECT_ROOT,
        bridge=SimpleNamespace(),
        snapshot_provider=lambda: {},
        dev_mode=False,
        start_hidden=True,
        warm_webview=lambda _window: order.append("warm") or True,
    )
    controller.window = SimpleNamespace(evaluate_js=lambda script: order.append(script))

    controller._handle_loaded()

    assert "'clipdeck:sleep'" in order[-2] and '"seq": 1' in order[-2]
    assert order[-1] == "warm"


def test_page_loaded_on_screen_is_not_put_to_sleep():
    warmed: list[object] = []
    controller = AppWindowController(
        project_root=TEST_PROJECT_ROOT,
        bridge=SimpleNamespace(),
        snapshot_provider=lambda: {},
        dev_mode=False,
        start_hidden=False,
        backdrop_capture=lambda _window, _appearance: None,
        warm_webview=warmed.append,
    )
    scripts: list[str] = []
    controller.window = SimpleNamespace(evaluate_js=scripts.append)

    controller._handle_loaded()

    assert warmed == []
    assert not any("clipdeck:sleep" in script for script in scripts)


def test_window_controller_can_toggle_always_on_top_for_current_run():
    bridge = SimpleNamespace(
        _bind_hide_window=lambda _callback: None,
        _bind_pick_storage_path=lambda _callback: None,
    )
    topmost = {"value": False}
    set_on_top_calls: list[bool] = []
    controller = AppWindowController(
        project_root=TEST_PROJECT_ROOT,
        bridge=bridge,
        snapshot_provider=lambda: {},
        dev_mode=False,
        set_on_top_callback=lambda _window, enabled: (set_on_top_calls.append(enabled), topmost.__setitem__("value", enabled)),
    )
    controller.window = SimpleNamespace()

    assert controller.is_always_on_top is False

    controller.toggle_always_on_top()

    assert controller.is_always_on_top is True
    assert topmost["value"] is True
    assert set_on_top_calls == [True]


def test_window_controller_reapplies_always_on_top_when_showing_window():
    bridge = SimpleNamespace(
        _bind_hide_window=lambda _callback: None,
        _bind_pick_storage_path=lambda _callback: None,
    )
    set_on_top_calls: list[bool] = []
    calls = {
        "show": 0,
        "restore": 0,
    }
    controller = AppWindowController(
        project_root=TEST_PROJECT_ROOT,
        bridge=bridge,
        snapshot_provider=lambda: {},
        dev_mode=False,
        set_on_top_callback=lambda _window, enabled: set_on_top_calls.append(enabled),
    )
    controller.window = SimpleNamespace(
        show=lambda: calls.__setitem__("show", calls["show"] + 1),
        restore=lambda: calls.__setitem__("restore", calls["restore"] + 1),
    )

    controller.toggle_always_on_top()
    controller.show()

    assert calls["show"] == 1
    assert calls["restore"] == 1
    assert set_on_top_calls == [True, True]


def test_set_window_on_top_updates_native_topmost_on_ui_thread():
    invoke_calls = {"count": 0}

    class NativeWindow:
        def __init__(self) -> None:
            self.TopMost = False
            self.InvokeRequired = True

        def Invoke(self, callback):
            if isinstance(callback, FunctionType):
                raise TypeError("Invoke must receive a .NET delegate, not a raw Python function")
            invoke_calls["count"] += 1
            callback()

    window = SimpleNamespace(native=NativeWindow())

    set_window_on_top(window, True)

    assert window.native.TopMost is True
    assert invoke_calls["count"] == 1


def test_place_rect_near_anchor_prefers_below_and_clamps_to_work_area():
    from backend.app.backdrop import place_rect_near_anchor

    assert place_rect_near_anchor(anchor=(500, 100), size=(200, 300), work_area=(0, 0, 1920, 1040)) == (400, 112)
    # Not enough room below -> flips above the anchor.
    assert place_rect_near_anchor(anchor=(500, 900), size=(200, 300), work_area=(0, 0, 1920, 1040)) == (400, 588)
    # Near the left edge -> clamped inside the work area.
    assert place_rect_near_anchor(anchor=(10, 100), size=(200, 300), work_area=(0, 0, 1920, 1040)) == (0, 112)


def _blur_controller(hide_on_blur=True):
    hidden = {"count": 0}
    blurred = {"count": 0}
    controller = AppWindowController(
        project_root=TEST_PROJECT_ROOT,
        bridge=SimpleNamespace(),
        snapshot_provider=lambda: {},
        dev_mode=False,
        hide_on_blur_provider=lambda: hide_on_blur,
        on_blur_hide=lambda: blurred.__setitem__("count", blurred["count"] + 1),
    )
    controller.window = SimpleNamespace(hide=lambda: hidden.__setitem__("count", hidden["count"] + 1))
    controller._is_hidden = False
    return controller, hidden, blurred


def test_window_hides_on_blur_when_enabled():
    controller, hidden, blurred = _blur_controller()

    controller._handle_deactivate()

    assert hidden["count"] == 1
    assert blurred["count"] == 1
    assert controller.is_hidden is True


def test_window_does_not_hide_on_blur_while_dialog_open_or_pinned_or_disabled():
    controller, hidden, _ = _blur_controller()
    controller.run_modal(controller._handle_deactivate)
    assert hidden["count"] == 0

    controller._is_always_on_top = True
    controller._handle_deactivate()
    assert hidden["count"] == 0

    disabled, disabled_hidden, _ = _blur_controller(hide_on_blur=False)
    disabled._handle_deactivate()
    assert disabled_hidden["count"] == 0


def test_showing_a_hidden_loaded_window_asks_the_page_to_play_its_reveal(monkeypatch):
    import backend.app.window as window_module

    monkeypatch.setattr(window_module, "move_window_near_pointer", lambda _window: None)
    scripts: list[str] = []
    controller = AppWindowController(
        project_root=TEST_PROJECT_ROOT,
        bridge=SimpleNamespace(),
        snapshot_provider=lambda: {},
        dev_mode=False,
        start_hidden=True,
        set_on_top_callback=lambda _window, _enabled: None,
    )
    controller.window = SimpleNamespace(
        show=lambda: None,
        restore=lambda: None,
        evaluate_js=scripts.append,
    )
    controller._is_loaded = True

    controller.show()
    controller.show()

    assert len(scripts) == 1
    assert "clipdeck:reveal" in scripts[0]


def test_backdrop_payload_carries_image_and_alignment_in_physical_pixels():
    from backend.app.backdrop import backdrop_payload

    payload = backdrop_payload(jpeg_bytes=b"\xff\xd8jpeg", monitor=(-1920, 0, 0, 1080), window_origin=(-1500, 200))

    assert payload["url"].startswith("data:image/jpeg;base64,")
    assert (payload["left"], payload["top"], payload["width"], payload["height"]) == (-1920, 0, 1920, 1080)
    assert (payload["windowLeft"], payload["windowTop"]) == (-1500, 200)


def test_showing_a_hidden_window_reveals_it_first_then_sends_the_desktop_backdrop(monkeypatch):
    import backend.app.window as window_module

    monkeypatch.setattr(window_module, "move_window_near_pointer", lambda _window: None)
    events: list[str] = []
    controller = AppWindowController(
        project_root=TEST_PROJECT_ROOT,
        bridge=SimpleNamespace(),
        snapshot_provider=lambda: {},
        dev_mode=False,
        start_hidden=True,
        set_on_top_callback=lambda _window, _enabled: None,
        backdrop_capture=lambda _window, _appearance=None: {"url": "data:image/jpeg;base64,AA==", "windowLeft": 0, "windowTop": 0},
    )
    controller.window = SimpleNamespace(
        show=lambda: events.append("show"),
        restore=lambda: None,
        evaluate_js=lambda script: events.append(script.split("'")[1]),
    )
    controller._is_loaded = True

    controller.show()

    assert events == ["show", "clipdeck:reveal", "clipdeck:backdrop"]


def test_appearance_settings_fill_defaults_and_clamp_hand_edited_values():
    from backend.app.models import AppearanceSettings

    defaults = AppearanceSettings.from_dict(None)
    assert defaults.glass_source == "live"
    assert defaults.corner_radius == 24

    edited = AppearanceSettings.from_dict(
        {"textTone": "neon", "cornerRadius": 400, "displacementScale": -5, "elasticity": "bouncy", "glassSource": "snapshot"}
    )
    assert edited.text_tone == "auto"
    assert edited.corner_radius == 40
    assert edited.displacement_scale == 0
    assert edited.elasticity == defaults.elasticity
    assert edited.glass_source == "snapshot"
    assert AppearanceSettings.from_dict(edited.to_dict()) == edited

    clamped = AppearanceSettings.from_dict({"whitePoint": 999, "backdropBlur": 80, "blackPoint": -3})
    assert (clamped.white_point, clamped.backdrop_blur, clamped.black_point) == (255, 20, 0)

    # Black can never reach white: the desktop always shows through.
    crossed = AppearanceSettings.from_dict({"whitePoint": 50, "blackPoint": 200})
    assert (crossed.white_point, crossed.black_point) == (50, 46)


def test_old_tint_and_brightness_become_the_same_white_and_black_points():
    from backend.app.models import AppearanceSettings

    # brightness .66 under a 10% grey-130 tint: white 255·.66·.9 + 13 = 164, black 13.
    smoke = AppearanceSettings.from_dict({"tintGray": 130, "tintOpacity": 10, "backdropBrightness": 66})
    assert (smoke.white_point, smoke.black_point) == (164, 13)
    assert {"tintGray", "tintOpacity", "backdropBrightness"}.isdisjoint(smoke.to_dict())

    # A saved contrast is folded into the tint first: Mist's 22% grey 110, brightness .72, contrast .7.
    mist = AppearanceSettings.from_dict({"tintGray": 110, "tintOpacity": 22, "backdropBrightness": 72, "backdropContrast": 70})
    assert (mist.white_point, mist.black_point) == (146, 45)
    assert "backdropContrast" not in mist.to_dict()

    # Already converted settings are left alone.
    assert AppearanceSettings.from_dict(smoke.to_dict()) == smoke


def test_appearance_defaults_to_the_smoke_template():
    from backend.app.models import AppearanceSettings

    fresh = AppearanceSettings.from_dict(None)
    # white_text_gray_glass_tuner.html's export: rgba(130,130,130,.10) over brightness .66 (white
    # 164, black 13), blur 10, saturate 100%, no sheen, rim or halo, meta at .56.
    assert (fresh.white_point, fresh.black_point, fresh.backdrop_blur, fresh.backdrop_saturation) == (164, 13, 10, 100)
    assert (fresh.rim_light, fresh.edge_highlight, fresh.text_halo, fresh.secondary_text_opacity) == (0, 0, 0, 56)
    assert fresh.text_tone == "auto"


def test_old_material_and_theme_settings_become_full_parameters():
    from backend.app.models import AppearanceSettings

    # Smoke saved before: its values are kept as they were (no tint over brightness .66).
    smoke = AppearanceSettings.from_dict({"material": "smoke", "theme": "system", "tintGray": 90, "tintOpacity": 0})
    assert (smoke.white_point, smoke.black_point) == (168, 0)

    # Clear + dark theme: 40% grey-20 tint (8 points over the saved 32), same as Clear Dark.
    dark = AppearanceSettings.from_dict({"material": "clear", "theme": "dark", "tintOpacity": 32, "backdropBlur": 20})
    assert (dark.white_point, dark.black_point, dark.backdrop_blur, dark.rim_light) == (161, 8, 20, 45)

    light = AppearanceSettings.from_dict({"theme": "light", "tintOpacity": 32})
    assert (light.white_point, light.black_point, light.rim_light) == (255, 82, 100)

    # "Over light" turns into the explicit values it used to apply behind the scenes.
    calm = AppearanceSettings.from_dict({"overLight": True, "frost": 0.25, "displacementScale": 70})
    assert (calm.liquid_shade, calm.frost, calm.displacement_scale) == (20, 0.5, 35)
    assert "theme" not in calm.to_dict() and "overLight" not in calm.to_dict()


def test_switching_glass_source_toggles_the_live_visual_and_tells_the_page():
    calls: list[object] = []

    class FakeGlass:
        mode = "live"
        live_available = True

        def use_live(self, enabled):
            calls.append(("live", enabled))
            self.mode = "live" if enabled else "snapshot"
            return self.mode

        def set_corner_radius(self, radius):
            calls.append(("radius", radius))

        def set_live_strength(self, strength):
            calls.append(("strength", strength))

    scripts: list[str] = []
    controller = AppWindowController(
        project_root=TEST_PROJECT_ROOT,
        bridge=SimpleNamespace(),
        snapshot_provider=lambda: {},
        dev_mode=False,
        backdrop_capture=lambda _window, _appearance=None: {"url": "data:image/jpeg;base64,AA==", "windowLeft": 0, "windowTop": 0},
    )
    controller.window = SimpleNamespace(evaluate_js=scripts.append)
    controller._glass = FakeGlass()
    controller._is_loaded = True
    controller._is_hidden = False

    controller.apply_appearance({"glassSource": "snapshot", "cornerRadius": 30})

    assert ("live", False) in calls
    assert ("radius", 30.0) in calls
    assert any("clipdeck:glass" in script and '"snapshot"' in script for script in scripts)
    assert any("clipdeck:backdrop" in script for script in scripts)


def test_title_drag_is_elastic_unless_animations_are_off(monkeypatch):
    from backend.app import window as window_module
    from backend.app.bridge import AppBridge

    drags: list[tuple[object, tuple[int, int], bool]] = []
    monkeypatch.setattr(
        window_module, "begin_window_drag", lambda win, grab, *, elastic: drags.append((win, grab, elastic))
    )
    bridge = AppBridge(SimpleNamespace())
    controller = AppWindowController(project_root=TEST_PROJECT_ROOT, bridge=bridge, snapshot_provider=lambda: {}, dev_mode=False)
    controller.window = SimpleNamespace()
    bridge._bind_begin_window_drag(controller.begin_drag)

    bridge.begin_window_drag(60, 32.4)
    controller._appearance = {"animations": False}
    bridge.begin_window_drag(10, 12)

    assert drags == [(controller.window, (60, 32), True), (controller.window, (10, 12), False)]


def test_moves_are_only_sent_to_the_page_for_snapshot_glass(monkeypatch):
    from backend.app import window as window_module

    monkeypatch.setattr(window_module, "window_origin", lambda _window: (100, 200))
    scripts: list[str] = []
    controller = AppWindowController(project_root=TEST_PROJECT_ROOT, bridge=SimpleNamespace(), snapshot_provider=lambda: {}, dev_mode=False)
    controller.window = SimpleNamespace(evaluate_js=scripts.append)
    controller._is_loaded = True

    controller._glass = SimpleNamespace(mode="live")
    controller._handle_moved()
    assert scripts == []

    controller._glass = SimpleNamespace(mode="snapshot")
    controller._handle_moved()
    assert len(scripts) == 1 and "clipdeck:moved" in scripts[0]


def test_backdrop_blur_fades_the_live_glass_down_to_a_clear_window():
    from backend.app.backdrop import live_blur_strength

    # Windows' live blur has one strength: 0 px hides it (sharp desktop), 12 px and up is all of it.
    assert live_blur_strength(0) == 0
    assert live_blur_strength(6) == 0.5
    assert live_blur_strength(28) == 1

    strengths: list[float] = []
    controller = AppWindowController(project_root=TEST_PROJECT_ROOT, bridge=SimpleNamespace(), snapshot_provider=lambda: {}, dev_mode=False)
    controller._glass = SimpleNamespace(
        mode="live",
        use_live=lambda enabled: "live",
        set_corner_radius=lambda _radius: None,
        set_live_strength=strengths.append,
    )
    controller.apply_appearance({"glassSource": "live", "backdropBlur": 0})
    controller.apply_appearance({"glassSource": "live", "backdropBlur": 0, "blackPoint": 20})

    assert strengths == [0.0]
