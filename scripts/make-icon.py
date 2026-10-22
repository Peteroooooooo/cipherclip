"""Writes the ClipDeck icon files from backend/app/brand_icon.py:
assets/clipdeck.ico (exe), assets/clipdeck-icon.png (preview) and frontend/public/favicon.png."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.brand_icon import draw_icon  # noqa: E402

SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)

frames = [draw_icon(size) for size in SIZES]
frames[-1].save(ROOT / "assets" / "clipdeck.ico", sizes=[(s, s) for s in SIZES], append_images=frames[:-1])
frames[-1].save(ROOT / "assets" / "clipdeck-icon.png")
public = ROOT / "frontend" / "public"
public.mkdir(exist_ok=True)
draw_icon(64).save(public / "favicon.png")
print("wrote", ", ".join(str(p.relative_to(ROOT)) for p in (ROOT / "assets" / "clipdeck.ico", ROOT / "assets" / "clipdeck-icon.png", public / "favicon.png")))
