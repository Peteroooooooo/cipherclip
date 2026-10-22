"""The ClipDeck icon: a small deck of cards on a graphite tile. Drawn here so the tray icon and
the exe icon (scripts/make-icon.py writes assets/clipdeck.ico from this) are always the same."""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFilter

# Drawn this many times larger, then scaled down: smooth edges at every size.
SUPERSAMPLE = 4


def draw_icon(size: int = 256) -> Image.Image:
    n = size * SUPERSAMPLE
    px = lambda fraction: round(fraction * n)  # noqa: E731

    # The tile: graphite, a little lighter at the top, with a faint top light line.
    tile = Image.new("RGBA", (n, n))
    gradient = ImageDraw.Draw(tile)
    top, bottom = (74, 74, 82), (30, 30, 35)
    for y in range(n):
        t = y / (n - 1)
        gradient.line((0, y, n, y), fill=tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)) + (255,))
    inset, radius = px(0.04), px(0.23)
    shape = Image.new("L", (n, n), 0)
    ImageDraw.Draw(shape).rounded_rectangle((inset, inset, n - inset, n - inset), radius=radius, fill=255)
    icon = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    icon.paste(tile, mask=shape)
    rim = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    ImageDraw.Draw(rim).rounded_rectangle(
        (inset, inset, n - inset, n - inset), radius=radius, outline=(255, 255, 255, 46), width=max(1, px(0.008))
    )
    icon.alpha_composite(rim)

    # The deck: two cards peeking out behind the front one, each smaller and fainter.
    def card(box: tuple[float, float, float, float], fill: tuple[int, int, int, int]) -> None:
        layer = Image.new("RGBA", (n, n), (0, 0, 0, 0))
        ImageDraw.Draw(layer).rounded_rectangle(tuple(px(v) for v in box), radius=px(0.075), fill=fill)
        icon.alpha_composite(layer)

    card((0.33, 0.19, 0.67, 0.62), (255, 255, 255, 70))
    card((0.27, 0.265, 0.73, 0.70), (255, 255, 255, 140))

    front = (0.21, 0.35, 0.79, 0.80)
    shadow = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        tuple(px(v) for v in (front[0], front[1] + 0.02, front[2], front[3] + 0.02)), radius=px(0.085), fill=(0, 0, 0, 90)
    )
    icon.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(px(0.02))))
    card(front, (246, 246, 248, 255))

    # Two lines of "text" on the front card.
    lines = ImageDraw.Draw(icon)
    weight = px(0.045)
    for x0, x1, y in ((0.30, 0.66, 0.50), (0.30, 0.52, 0.625)):
        lines.rounded_rectangle((px(x0), px(y) - weight // 2, px(x1), px(y) + weight // 2), radius=weight // 2, fill=(150, 150, 158, 255))

    # Nothing outside the tile (the card shadow must not spill over its corners).
    icon.putalpha(Image.composite(icon.getchannel("A"), Image.new("L", (n, n), 0), shape))
    return icon.resize((size, size), Image.LANCZOS)
