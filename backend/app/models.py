from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field

DEFAULT_HISTORY_LIMIT = 25
MIN_HISTORY_LIMIT = 1
MAX_HISTORY_LIMIT = 5000


@dataclass(slots=True)
class HistoryRecord:
    id: str
    type: str
    summary: str
    detail: str
    meta: str
    source_app: str
    source_glyph: str
    pinned: bool
    created_at: str
    updated_at: str
    content_hash: str
    plain_text: str | None = None
    rich_text: str | None = None
    image_path: str | None = None
    image_width: int | None = None
    image_height: int | None = None
    file_paths: list[str] = field(default_factory=list)
    # The source app's icon (a cached PNG), when it could be read from its exe.
    source_icon: str | None = None

    def _normalize_image_path(self) -> str | None:
        return _as_uri(self.image_path)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "type": self.type,
            "summary": self.summary,
            "detail": self.detail,
            "meta": self.meta,
            "sourceApp": self.source_app,
            "sourceGlyph": self.source_glyph,
            "pinned": self.pinned,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "contentHash": self.content_hash,
            "plainText": self.plain_text,
            "richText": self.rich_text,
            "imagePath": self._normalize_image_path(),
            "imageWidth": self.image_width,
            "imageHeight": self.image_height,
            "filePaths": list(self.file_paths),
            "sourceIcon": _as_uri(self.source_icon),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "HistoryRecord":
        return cls(
            id=str(payload["id"]),
            type=str(payload["type"]),
            summary=str(payload["summary"]),
            detail=str(payload["detail"]),
            meta=str(payload["meta"]),
            source_app=str(payload["sourceApp"]),
            source_glyph=str(payload.get("sourceGlyph", "")),
            pinned=bool(payload["pinned"]),
            created_at=str(payload.get("createdAt", payload["updatedAt"])),
            updated_at=str(payload["updatedAt"]),
            content_hash=str(payload.get("contentHash", payload["id"])),
            plain_text=_optional_string(payload.get("plainText")),
            rich_text=_optional_string(payload.get("richText")),
            image_path=_optional_string(payload.get("imagePath")),
            image_width=_optional_int(payload.get("imageWidth")),
            image_height=_optional_int(payload.get("imageHeight")),
            file_paths=[str(item) for item in payload.get("filePaths", [])],
            source_icon=_optional_string(payload.get("sourceIcon")),
        )


def _as_uri(path: str | None) -> str | None:
    if path is None:
        return None
    if path.startswith(("file://", "http://", "https://")):
        return path
    from pathlib import Path
    return Path(path).as_uri()


@dataclass(slots=True)
class ShortcutBindings:
    toggle_panel: str
    primary_action: str
    paste_plain_text: str
    toggle_pin: str
    delete_record: str

    def to_dict(self) -> dict[str, str]:
        return {
            "togglePanel": self.toggle_panel,
            "primaryAction": self.primary_action,
            "pastePlainText": self.paste_plain_text,
            "togglePin": self.toggle_pin,
            "deleteRecord": self.delete_record,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "ShortcutBindings":
        return cls(
            toggle_panel=str(payload["togglePanel"]),
            primary_action=str(payload["primaryAction"]),
            paste_plain_text=str(payload["pastePlainText"]),
            toggle_pin=str(payload["togglePin"]),
            delete_record=str(payload["deleteRecord"]),
        )


TEXT_TONES = ("auto", "light", "dark")
BACKDROP_BLUR_MAX = 20
GLASS_SOURCES = ("live", "snapshot")
LIQUID_MODES = ("standard", "polar", "prominent", "shader")

# Glass looks the backend needs. SMOKE_GLASS and CLEAR_LIGHT_GLASS are the two templates of
# frontend/src/app/appearance.ts (GLASS_PRESETS: Dark Glass, Light Glass); CLEAR_DARK_GLASS is no
# longer a template, only what settings from before the single parameter set map onto.
SMOKE_GLASS: dict[str, object] = {
    "white_point": 164, "black_point": 13, "backdrop_blur": 10, "backdrop_saturation": 100,
    "rim_light": 0, "edge_highlight": 0, "text_tone": "auto", "text_halo": 0, "secondary_text_opacity": 56,
}
CLEAR_DARK_GLASS: dict[str, object] = {
    **SMOKE_GLASS, "white_point": 161, "black_point": 8, "backdrop_blur": 16, "backdrop_saturation": 160,
    "rim_light": 45, "secondary_text_opacity": 42,
}
CLEAR_LIGHT_GLASS: dict[str, object] = {
    **CLEAR_DARK_GLASS, "white_point": 255, "black_point": 82, "rim_light": 100, "secondary_text_opacity": 46,
}
# The white point never comes closer to the black point than this, so the desktop always shows.
MIN_POINT_GAP = 4
# Tint and brightness defaults from before the white/black points, for converting old settings.
LEGACY_TINT_GRAY, LEGACY_TINT_OPACITY, LEGACY_BRIGHTNESS = 130, 10, 66
LEGACY_THEME_TINT_GRAY = {"dark": 20, "light": 255}


@dataclass(slots=True)
class AppearanceSettings:
    """Look of the glass: one full parameter set (templates are just saved values of it).
    Liquid parameters mirror rdev/liquid-glass-react's props."""

    glass_source: str = "live"
    corner_radius: int = 24
    # Grey levels (0-255) that white and black on the desktop come out at through the glass.
    white_point: int = 164
    black_point: int = 13
    backdrop_blur: int = 10
    backdrop_saturation: int = 100
    rim_light: int = 0
    edge_highlight: int = 0
    text_tone: str = "auto"
    text_halo: int = 0
    secondary_text_opacity: int = 56
    liquid_enabled: bool = True
    liquid_mode: str = "standard"
    displacement_scale: int = 70
    aberration_intensity: float = 2.0
    elasticity: float = 0.15
    frost: float = 0.25
    liquid_saturation: int = 140
    liquid_shade: int = 0
    animations: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "glassSource": self.glass_source,
            "cornerRadius": self.corner_radius,
            "whitePoint": self.white_point,
            "blackPoint": self.black_point,
            "backdropBlur": self.backdrop_blur,
            "backdropSaturation": self.backdrop_saturation,
            "rimLight": self.rim_light,
            "edgeHighlight": self.edge_highlight,
            "textTone": self.text_tone,
            "textHalo": self.text_halo,
            "secondaryTextOpacity": self.secondary_text_opacity,
            "liquidEnabled": self.liquid_enabled,
            "liquidMode": self.liquid_mode,
            "displacementScale": self.displacement_scale,
            "aberrationIntensity": self.aberration_intensity,
            "elasticity": self.elasticity,
            "frost": self.frost,
            "liquidSaturation": self.liquid_saturation,
            "liquidShade": self.liquid_shade,
            "animations": self.animations,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object] | None) -> "AppearanceSettings":
        """Builds from a (possibly partial or hand-edited) payload, clamping every value."""
        data = _migrate_legacy_appearance(dict(payload or {}))
        d = cls()

        def number(key: str, low: float, high: float, default: float) -> int:
            return int(round(_clamp(data.get(key), low, high, default)))

        white = number("whitePoint", MIN_POINT_GAP, 255, d.white_point)
        return cls(
            glass_source=_choice(data.get("glassSource"), GLASS_SOURCES, d.glass_source),
            corner_radius=number("cornerRadius", 8, 40, d.corner_radius),
            white_point=white,
            black_point=number("blackPoint", 0, white - MIN_POINT_GAP, min(d.black_point, white - MIN_POINT_GAP)),
            backdrop_blur=number("backdropBlur", 0, BACKDROP_BLUR_MAX, d.backdrop_blur),
            backdrop_saturation=number("backdropSaturation", 50, 250, d.backdrop_saturation),
            rim_light=number("rimLight", 0, 100, d.rim_light),
            edge_highlight=number("edgeHighlight", 0, 100, d.edge_highlight),
            text_tone=_choice(data.get("textTone"), TEXT_TONES, d.text_tone),
            text_halo=number("textHalo", 0, 100, d.text_halo),
            secondary_text_opacity=number("secondaryTextOpacity", 30, 100, d.secondary_text_opacity),
            liquid_enabled=_flag(data.get("liquidEnabled"), d.liquid_enabled),
            liquid_mode=_choice(data.get("liquidMode"), LIQUID_MODES, d.liquid_mode),
            displacement_scale=number("displacementScale", 0, 150, d.displacement_scale),
            aberration_intensity=round(_clamp(data.get("aberrationIntensity"), 0, 10, d.aberration_intensity), 1),
            elasticity=round(_clamp(data.get("elasticity"), 0, 0.5, d.elasticity), 2),
            frost=round(_clamp(data.get("frost"), 0, 1, d.frost), 2),
            liquid_saturation=number("liquidSaturation", 50, 250, d.liquid_saturation),
            liquid_shade=number("liquidShade", 0, 50, d.liquid_shade),
            animations=_flag(data.get("animations"), d.animations),
        )


def _camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(part.title() for part in rest)


LEGACY_GLASS_KEYS = {"theme", "material", "overLight", "backdropContrast", "tintGray", "tintOpacity", "backdropBrightness"}


def _migrate_legacy_appearance(data: dict[str, object]) -> dict[str, object]:
    """Same as migrateLegacy in frontend/src/app/appearance.ts: settings saved with a "material"
    and a light/dark "theme" (which swapped hidden values) become the parameters they stood for,
    and the old contrast, brightness and tint become the white and black points they produce."""
    if not LEGACY_GLASS_KEYS & data.keys():
        return data
    migrated = dict(data)
    if data.get("material") != "smoke" and "theme" in data:
        light = data.get("theme") == "light"
        base = CLEAR_LIGHT_GLASS if light else CLEAR_DARK_GLASS
        saved_tint = data.get("tintOpacity")
        # Dark clear glass used to add 8 points of tint on top of the saved value.
        tint = saved_tint + (0 if light else 8) if _is_number(saved_tint) else (32 if light else 40)
        migrated.update({_camel(key): value for key, value in base.items()})
        for key in ("backdropBlur", "backdropSaturation"):
            if _is_number(data.get(key)):
                migrated[key] = data[key]
        migrated.pop("whitePoint")
        migrated.pop("blackPoint")
        migrated.update(
            {"tintGray": LEGACY_THEME_TINT_GRAY["light" if light else "dark"], "tintOpacity": tint, "backdropBrightness": 100}
        )
    if data.get("overLight") is True:
        # "Over light" used to add a 20% shade, 8px of extra frost and halve the displacement.
        frost = data.get("frost") if _is_number(data.get("frost")) else 0.25
        displacement = data.get("displacementScale") if _is_number(data.get("displacementScale")) else 70
        migrated.update({"liquidShade": 20, "frost": min(1.0, frost + 0.25), "displacementScale": round(displacement / 2)})
    _fold_contrast_into_tint(migrated)
    _tint_to_points(migrated)
    for key in ("theme", "material", "overLight"):
        migrated.pop(key, None)
    return migrated


def _legacy_tint(data: dict[str, object]) -> tuple[float, float, float]:
    """Old tint opacity (0-1), tint grey and brightness (0-1), with their old bounds and defaults."""
    return (
        _clamp(data.get("tintOpacity"), 0, 95, LEGACY_TINT_OPACITY) / 100,
        _clamp(data.get("tintGray"), 0, 255, LEGACY_TINT_GRAY),
        _clamp(data.get("backdropBrightness"), 30, 100, LEGACY_BRIGHTNESS) / 100,
    )


def _fold_contrast_into_tint(data: dict[str, object]) -> None:
    """Contrast c pulled the backdrop towards mid-grey (128) by 1 - c before brightness b; with
    the tint (grey g at opacity a) on top that is exactly one stronger tint:
    a' = 1 - (1 - a)c and a'g' = (1 - a)·b·(1 - c)·128 + a·g."""
    contrast = data.pop("backdropContrast", None)
    if not _is_number(contrast) or contrast >= 100:
        return
    c = max(0.3, float(contrast) / 100)
    a, g, b = _legacy_tint(data)
    folded = 1 - (1 - a) * c
    data["tintOpacity"] = round(folded * 100)
    data["tintGray"] = round(((1 - a) * b * (1 - c) * 128 + a * g) / folded)


def _tint_to_points(data: dict[str, object]) -> None:
    """Brightness b, then a tint of grey g at opacity a, turned desktop level x into
    x·b(1 - a) + g·a: white (255) and black (0) land exactly on these two points."""
    if not {"tintGray", "tintOpacity", "backdropBrightness"} & data.keys():
        return
    a, g, b = _legacy_tint(data)
    for key in ("tintGray", "tintOpacity", "backdropBrightness"):
        data.pop(key, None)
    if "whitePoint" in data or "blackPoint" in data:
        return
    data["whitePoint"] = round(255 * b * (1 - a) + g * a)
    data["blackPoint"] = round(g * a)


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


@dataclass(slots=True)
class SettingsState:
    launch_on_startup: bool
    close_to_tray: bool
    follow_system_theme: bool
    record_text: bool
    record_rich_text: bool
    history_limit: int
    record_images: bool
    record_files: bool
    storage_path: str
    shortcuts: ShortcutBindings
    appearance: AppearanceSettings = field(default_factory=AppearanceSettings)

    def to_dict(self) -> dict[str, object]:
        return {
            "launchOnStartup": self.launch_on_startup,
            "closeToTray": self.close_to_tray,
            "followSystemTheme": self.follow_system_theme,
            "recordText": self.record_text,
            "recordRichText": self.record_rich_text,
            "historyLimit": self.history_limit,
            "recordImages": self.record_images,
            "recordFiles": self.record_files,
            "storagePath": self.storage_path,
            "shortcuts": self.shortcuts.to_dict(),
            "appearance": self.appearance.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "SettingsState":
        return cls(
            launch_on_startup=bool(payload["launchOnStartup"]),
            close_to_tray=bool(payload["closeToTray"]),
            follow_system_theme=bool(payload["followSystemTheme"]),
            record_text=bool(payload.get("recordText", True)),
            record_rich_text=bool(payload.get("recordRichText", True)),
            history_limit=_history_limit_from_payload(payload.get("historyLimit")),
            record_images=bool(payload["recordImages"]),
            record_files=bool(payload.get("recordFiles", True)),
            storage_path=str(payload["storagePath"]),
            shortcuts=ShortcutBindings.from_dict(dict(payload["shortcuts"])),
            appearance=AppearanceSettings.from_dict(_optional_dict(payload.get("appearance"))),
        )


@dataclass(slots=True)
class ToastMessage:
    title: str
    message: str
    tone: str
    action_kind: str | None = None
    action_label: str | None = None
    id: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "message": self.message,
            "tone": self.tone,
            "actionKind": self.action_kind,
            "actionLabel": self.action_label,
        }


def default_settings(*, storage_path: str) -> SettingsState:
    return SettingsState(
        launch_on_startup=True,
        close_to_tray=True,
        follow_system_theme=True,
        record_text=True,
        record_rich_text=True,
        history_limit=DEFAULT_HISTORY_LIMIT,
        record_images=True,
        record_files=True,
        storage_path=storage_path,
        shortcuts=ShortcutBindings(
            toggle_panel="Alt + Space",
            primary_action="Enter",
            paste_plain_text="Ctrl + Shift + V",
            toggle_pin="Ctrl + P",
            delete_record="Delete",
        ),
    )


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_dict(value: object) -> dict[str, object] | None:
    return dict(value) if isinstance(value, dict) else None


def _choice(value: object, options: tuple[str, ...], default: str) -> str:
    return value if isinstance(value, str) and value in options else default


def _flag(value: object, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _clamp(value: object, low: float, high: float, default: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return max(low, min(high, float(value)))


def _history_limit_from_payload(value: object) -> int:
    if value is None:
        return DEFAULT_HISTORY_LIMIT

    return max(MIN_HISTORY_LIMIT, min(MAX_HISTORY_LIMIT, int(value)))
