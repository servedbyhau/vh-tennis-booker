"""Draw the app's icon, a ticket in the UI's colours, into the Windows ``.ico`` of the shell.

Needs Pillow. The icon is committed, so run this only to change it.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ICON = Path(__file__).resolve().parents[1] / "desktop" / "src-tauri" / "icons" / "icon.ico"
SIZES = (16, 24, 32, 48, 64, 128, 256)
SIZE = 1024
INK = "#1c1b19"
PAPER = "#f8f7f3"
HIGHLIGHT = "#ecd78f"


def draw_icon() -> Image.Image:
    """Return the icon: a paper ticket with notches and a stub on an ink square."""
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, SIZE - 1, SIZE - 1), radius=200, fill=INK)
    left, top, right, bottom = 150, 270, 874, 754
    draw.rounded_rectangle((left, top, right, bottom), radius=64, fill=PAPER)
    stub = 650
    draw.rectangle((stub, top, right - 64, bottom), fill=HIGHLIGHT)
    draw.rounded_rectangle((stub + 60, top, right, bottom), radius=64, fill=HIGHLIGHT)
    notch = 48
    for y in (top, bottom):
        draw.ellipse((stub - notch, y - notch, stub + notch, y + notch), fill=INK)
    for y in range(top + 80, bottom - 60, 80):
        draw.rectangle((stub - 8, y, stub + 8, y + 40), fill=INK)
    return image


def main() -> int:
    ICON.parent.mkdir(parents=True, exist_ok=True)
    draw_icon().save(ICON, sizes=[(size, size) for size in SIZES])
    print(f"Wrote {ICON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
