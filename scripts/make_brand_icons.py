"""Generate ESPTimeCast brand images (LED dot-matrix "ESP").

Renders a green dot-matrix display showing "ESP" — modelled on the device's
MAX7219 8x32 matrix (a decorative top row of dots above the letters) — into
custom_components/esptimecast/brand/ as the icon/logo PNGs Home Assistant's
brands proxy serves directly from a custom integration.

Run:  python scripts/make_brand_icons.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

_ROOT = Path(__file__).resolve().parent.parent
BRAND_DIR = _ROOT / "custom_components" / "esptimecast" / "brand"

# 5x7 dot-matrix glyphs.
GLYPHS = {
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "S": ["01110", "10001", "10000", "01110", "00001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "C": ["01110", "10001", "10000", "10000", "10000", "10001", "01110"],
}

ICON_TEXT = "ESP"
LOGO_TEXT = "ETC"  # ESP Time Cast

# Colours
TILE = (20, 23, 28, 255)  # device charcoal
SCREEN = (5, 7, 6, 255)  # near-black display
OFF_DOT = (16, 26, 16, 255)  # unlit LED
DOT = (147, 224, 36, 255)  # lit LED (yellow-green, like the photo)
CORE = (216, 255, 143, 255)  # bright LED core
GLOW = (120, 210, 30)  # glow tint

SS = 4  # supersample factor


def build_grid(text: str) -> list[list[bool]]:
    """9 rows x 17 cols: decorative dot row, blank row, then 3 glyphs."""
    cols = 17
    grid = [[False] * cols for _ in range(9)]
    grid[0] = [True] * cols  # decorative top row
    x = 0
    for letter in text:
        rows = GLYPHS[letter]
        for r, line in enumerate(rows):
            for c, bit in enumerate(line):
                if bit == "1":
                    grid[2 + r][x + c] = True
        x += 6  # 5 wide + 1 gap
    return grid


def render(grid: list[list[bool]], *, square: bool) -> Image.Image:
    rows, cols = len(grid), len(grid[0])
    cell = 18 * SS
    dot_r = 7 * SS
    margin = cell  # gap between matrix and screen edge
    bezel = cell  # device border around the screen

    screen_w = cols * cell + 2 * margin
    screen_h = rows * cell + 2 * margin

    if square:
        size = max(screen_w, screen_h) + 2 * bezel
        w = h = size
    else:
        w = screen_w + 2 * bezel
        h = screen_h + 2 * bezel

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Device tile (rounded).
    draw.rounded_rectangle(
        [0, 0, w - 1, h - 1], radius=int(0.16 * min(w, h)), fill=TILE
    )

    # Display panel (rounded), centred.
    sx = (w - screen_w) // 2
    sy = (h - screen_h) // 2
    draw.rounded_rectangle(
        [sx, sy, sx + screen_w, sy + screen_h], radius=int(0.10 * screen_h), fill=SCREEN
    )

    ox = sx + margin + cell // 2
    oy = sy + margin + cell // 2

    # Unlit LEDs (faint grid).
    for r in range(rows):
        for c in range(cols):
            cx, cy = ox + c * cell, oy + r * cell
            draw.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r], fill=OFF_DOT)

    # Lit LEDs on their own layer so we can build a glow.
    lit = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lit)
    for r in range(rows):
        for c in range(cols):
            if not grid[r][c]:
                continue
            cx, cy = ox + c * cell, oy + r * cell
            ld.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r], fill=DOT)
            cr = dot_r // 2
            ld.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=CORE)

    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for r in range(rows):
        for c in range(cols):
            if not grid[r][c]:
                continue
            cx, cy = ox + c * cell, oy + r * cell
            gr = dot_r * 2
            gd.ellipse([cx - gr, cy - gr, cx + gr, cy + gr], fill=(*GLOW, 130))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=dot_r))

    img.alpha_composite(glow)
    img.alpha_composite(lit)
    return img


def save(img: Image.Image, name: str, target_long_edge: int) -> None:
    w, h = img.size
    scale = target_long_edge / max(w, h)
    out = img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
    BRAND_DIR.mkdir(parents=True, exist_ok=True)
    out.save(BRAND_DIR / name)
    print(f"  {name}: {out.size[0]}x{out.size[1]}")


def main() -> None:
    icon = render(build_grid(ICON_TEXT), square=True)
    logo = render(build_grid(LOGO_TEXT), square=False)
    print("Writing brand assets:")
    save(icon, "icon.png", 256)
    save(icon, "icon@2x.png", 512)
    save(logo, "logo.png", 256)
    save(logo, "logo@2x.png", 512)


if __name__ == "__main__":
    main()
