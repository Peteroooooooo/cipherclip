"""The ClipDeck icon for the tray. Every icon file (this PNG, the exe/window .ico and the favicon)
is rendered from assets/clipdeck-icon.svg by scripts/make-icon.py, so they always match. The tray
uses the small-size cut, whose board is drawn larger so it reads at 16-24 px."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image


def brand_icon_path() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    root = Path(bundle_root) if bundle_root is not None else Path(__file__).resolve().parents[2]
    return root / "assets" / "clipdeck-icon-small.png"


def load_icon(size: int = 256) -> Image.Image:
    with Image.open(brand_icon_path()) as image:
        return image.convert("RGBA").resize((size, size), Image.LANCZOS)
