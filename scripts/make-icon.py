"""Writes every ClipDeck icon file from the master assets/clipdeck-icon.svg (and its small-size
cut, assets/clipdeck-icon-small.svg): assets/clipdeck.ico (exe and window),
assets/clipdeck-icon.png (previews), assets/clipdeck-icon-small.png (tray),
frontend/public/favicon.png and frontend/public/clipdeck-icon.svg (the panel's empty-state logo).

The SVG uses gradients and blur filters, so it is rendered by a headless Edge or Chrome (always
present on Windows) rather than a Python SVG library.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SVG = ROOT / "assets" / "clipdeck-icon.svg"
# The same icon with the board 1.5x larger, for the tray and the taskbar: on a dark taskbar the
# dark tile disappears and the board alone read far smaller than the icons next to it.
SMALL_SVG = ROOT / "assets" / "clipdeck-icon-small.svg"
SMALL_UP_TO = 64
MASTER = 1024
ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)
BROWSERS = (
    Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
    Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
    Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Google" / "Chrome" / "Application" / "chrome.exe",
)


def render_svg(size: int, svg: Path = SVG) -> Image.Image:
    browser = next((path for path in BROWSERS if path.is_file()), None)
    if browser is None:
        raise SystemExit("Needs Microsoft Edge or Google Chrome to render the SVG.")
    with tempfile.TemporaryDirectory() as work:
        page = Path(work) / "icon.html"
        shot = Path(work) / "icon.png"
        page.write_text(
            "<!doctype html><html><head><style>html,body{margin:0;background:transparent;overflow:hidden}"
            f"svg{{display:block;width:{size}px;height:{size}px}}</style></head><body>"
            + svg.read_text(encoding="utf-8").split("?>", 1)[-1]
            + "</body></html>",
            encoding="utf-8",
        )
        subprocess.run(
            [
                str(browser),
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                "--force-device-scale-factor=1",
                "--default-background-color=00000000",
                f"--window-size={size},{size}",
                f"--user-data-dir={Path(work) / 'profile'}",
                f"--screenshot={shot}",
                page.as_uri(),
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )
        image = Image.open(shot).convert("RGBA")
        image.load()
    if image.size != (size, size):
        image = image.crop((0, 0, size, size))
    return image


def main() -> None:
    master = render_svg(MASTER)
    small = render_svg(MASTER, SMALL_SVG)
    frames = [(small if size <= SMALL_UP_TO else master).resize((size, size), Image.LANCZOS) for size in ICO_SIZES]
    ico = ROOT / "assets" / "clipdeck.ico"
    frames[-1].save(ico, sizes=[(s, s) for s in ICO_SIZES], append_images=frames[:-1])
    png = ROOT / "assets" / "clipdeck-icon.png"
    master.resize((512, 512), Image.LANCZOS).save(png)
    tray = ROOT / "assets" / "clipdeck-icon-small.png"
    small.resize((256, 256), Image.LANCZOS).save(tray)
    public = ROOT / "frontend" / "public"
    public.mkdir(exist_ok=True)
    favicon = public / "favicon.png"
    small.resize((64, 64), Image.LANCZOS).save(favicon)
    page_logo = public / "clipdeck-icon.svg"
    page_logo.write_bytes(SVG.read_bytes())
    print("wrote", ", ".join(str(p.relative_to(ROOT)) for p in (ico, png, tray, favicon, page_logo)))


if __name__ == "__main__":
    sys.exit(main())
