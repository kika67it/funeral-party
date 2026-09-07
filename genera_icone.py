"""Script una tantum per generare le icone PWA (candela stilizzata su sfondo scuro)."""
from pathlib import Path

from PIL import Image, ImageDraw

OUT_DIR = Path(__file__).resolve().parent / "static" / "icons"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BG = (30, 33, 41, 255)
CANDELA = (236, 233, 225, 255)
FIAMMA = (230, 168, 87, 255)


def disegna_icona(size):
    img = Image.new("RGBA", (size, size), BG)
    d = ImageDraw.Draw(img)

    cx = size / 2
    corpo_w = size * 0.16
    corpo_h = size * 0.34
    corpo_top = size * 0.46
    corpo_bottom = corpo_top + corpo_h

    d.rounded_rectangle(
        [cx - corpo_w / 2, corpo_top, cx + corpo_w / 2, corpo_bottom],
        radius=size * 0.02,
        fill=CANDELA,
    )

    base_w = size * 0.34
    base_h = size * 0.05
    d.rounded_rectangle(
        [cx - base_w / 2, corpo_bottom - size * 0.01, cx + base_w / 2, corpo_bottom + base_h],
        radius=size * 0.02,
        fill=CANDELA,
    )

    flame_w = size * 0.11
    flame_h = size * 0.20
    flame_bottom = corpo_top + size * 0.02
    flame_top = flame_bottom - flame_h
    d.ellipse(
        [cx - flame_w / 2, flame_top, cx + flame_w / 2, flame_bottom],
        fill=FIAMMA,
    )

    return img


for dim in (192, 512):
    disegna_icona(dim).save(OUT_DIR / f"icon-{dim}.png")

print("Icone generate in", OUT_DIR)
