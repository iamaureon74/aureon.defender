"""Draws the aureon.defender icon: a shield outline holding a rising-sun horizon, on a dark rounded square.

Rendered at 4x and downsampled for clean edges; the small sizes drop the inner detail so they stay legible.
  python windows/assets/make_icon.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).parent
VOID, EMBER, GLOW, RIM = (13, 12, 14), (201, 128, 63), (255, 217, 176), (42, 36, 33)


def shield_points(cx, top, w, h):
    """Shield silhouette: flat shoulders, straight sides, pointed base. Smooth enough at 4x."""
    import math
    pts = [(cx - w / 2, top + h * 0.08), (cx, top), (cx + w / 2, top + h * 0.08), (cx + w / 2, top + h * 0.45)]
    steps = 24
    for i in range(1, steps + 1):          # right curve down to the point
        t = i / steps
        x = cx + w / 2 * math.cos(t * math.pi / 2) ** 1.4
        y = top + h * 0.45 + (h * 0.55) * math.sin(t * math.pi / 2)
        pts.append((x, y))
    for i in range(steps, -1, -1):         # mirror up the left side
        t = i / steps
        x = cx - w / 2 * math.cos(t * math.pi / 2) ** 1.4
        y = top + h * 0.45 + (h * 0.55) * math.sin(t * math.pi / 2)
        pts.append((x, y))
    return pts


def draw(size, detail=True):
    S = size * 4
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = S * 0.04
    d.rounded_rectangle((pad, pad, S - pad, S - pad), radius=S * 0.22, fill=VOID + (255,), outline=RIM + (255,), width=max(2, S // 96))
    # warm horizon glow behind the mark
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((S * 0.18, S * 0.52, S * 0.82, S * 1.02), fill=EMBER + (110,))
    glow = glow.filter(ImageFilter.GaussianBlur(S * 0.08))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((pad, pad, S - pad, S - pad), radius=S * 0.22, fill=255)
    img.paste(glow, (0, 0), Image.composite(glow, Image.new("RGBA", (S, S)), mask).split()[3])
    # shield outline = outer shield minus an inset inner shield (clean joins at every corner)
    stroke = S * (0.06 if size <= 32 else 0.042)
    ring = Image.new("L", (S, S), 0)
    rd = ImageDraw.Draw(ring)
    rd.polygon(shield_points(S / 2, S * 0.2, S * 0.5, S * 0.62), fill=255)
    rd.polygon(shield_points(S / 2, S * 0.2 + stroke * 1.15, S * 0.5 - stroke * 2, S * 0.62 - stroke * 2.3), fill=0)
    img.paste(Image.new("RGBA", (S, S), GLOW + (255,)), (0, 0), ring)
    d = ImageDraw.Draw(img)
    if detail:
        # rising sun: a half disc on the horizon line, inside the shield
        cx, hy, r = S / 2, S * 0.56, S * 0.1
        d.pieslice((cx - r, hy - r, cx + r, hy + r), 180, 360, fill=EMBER + (255,))
        d.line((S / 2 - S * 0.17, hy, S / 2 + S * 0.17, hy), fill=GLOW + (255,), width=max(3, int(S * 0.022)))
    return img.resize((size, size), Image.LANCZOS)


def main():
    big = draw(256)
    big.save(HERE / "aureon.png")
    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    frames = [draw(s, detail=s >= 32) for s in sizes]
    frames[-1].save(HERE / "aureon.ico", sizes=[(s, s) for s in sizes], append_images=frames[:-1])
    ui = HERE.parent / "aureon_defender" / "ui"
    draw(128).save(ui / "icon.png")
    preview = Image.new("RGBA", (sum(sizes) + 12 * len(sizes), 270), (30, 28, 30, 255))
    x = 8
    for s, f in zip(sizes, frames):
        preview.paste(f, (x, 260 - s), f)
        x += s + 12
    preview.save(HERE / "icon-preview.png")


if __name__ == "__main__":
    main()
