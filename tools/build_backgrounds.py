"""Generate 10 decorative 480x320 backgrounds (procedural, free of rights) + one theme per background."""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from core.model import W, H, new_theme, save_bundle, set_background  # noqa: E402
import build_themes as bt  # noqa: E402

OUT = ROOT / "res" / "backgrounds"


# ----------------------------------------------------------------- helpers
def noise(seed: int, octaves: int = 5, base: int = 4) -> np.ndarray:
    rng = np.random.default_rng(seed)
    acc = np.zeros((H, W))
    amp, total = 1.0, 0.0
    for o in range(octaves):
        n = base * 2 ** o
        grid = rng.random((n + 1, int(n * 1.5) + 1))
        img = Image.fromarray((grid * 255).astype(np.uint8)).resize((W, H), Image.Resampling.BICUBIC)
        acc += np.asarray(img, dtype=float) / 255 * amp
        total += amp
        amp *= 0.5
    acc /= total
    return (acc - acc.min()) / (acc.max() - acc.min() + 1e-9)


def colorize(v: np.ndarray, stops: list[tuple[float, tuple[int, int, int]]]) -> Image.Image:
    xs = [s for s, _ in stops]
    out = np.zeros((H, W, 3))
    for c in range(3):
        out[..., c] = np.interp(v, xs, [col[c] for _, col in stops])
    return Image.fromarray(out.astype(np.uint8))


def vgrad(top, bottom) -> Image.Image:
    t = np.linspace(0, 1, H)[:, None, None]
    arr = np.array(top)[None, None, :] * (1 - t) + np.array(bottom)[None, None, :] * t
    return Image.fromarray(np.repeat(arr, W, axis=1).astype(np.uint8))


# ------------------------------------------------------------- backgrounds
def nebula():
    v = noise(7, 6, 3) ** 1.6
    img = colorize(v, [(0, (5, 3, 20)), (.35, (40, 10, 70)), (.6, (150, 40, 140)), (.8, (255, 120, 90)),
                       (1, (255, 230, 200))])
    d = ImageDraw.Draw(img)
    rnd = random.Random(1)
    for _ in range(260):
        x, y, b = rnd.randrange(W), rnd.randrange(H), rnd.randrange(120, 255)
        d.point((x, y), fill=(b, b, b))
    return img


def aurora():
    img = vgrad((2, 8, 25), (5, 25, 30))
    arr = np.asarray(img, dtype=float)
    xs = np.arange(W)
    yy = np.arange(H)[:, None]
    for k, (col, off) in enumerate((((40, 255, 140), 90), ((120, 80, 255), 130), ((30, 200, 255), 60))):
        center = off + 25 * np.sin(xs / 60 + k) + 12 * np.sin(xs / 23 + k * 2)
        band = np.exp(-((yy - center[None, :]) ** 2) / (2 * 22 ** 2))
        streak = 0.6 + 0.4 * np.sin(xs / 4 + k)[None, :]
        arr += band[..., None] * streak[..., None] * np.array(col) * 0.55
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    pts = [(0, H)] + [(x, 250 + 20 * math.sin(x / 40) + 10 * math.sin(x / 13)) for x in range(0, W + 1, 8)] + [(W, H)]
    d.polygon(pts, fill=(3, 8, 10))
    return img


def synthwave():
    img = vgrad((20, 0, 40), (255, 60, 120))
    d = ImageDraw.Draw(img)
    cx, cy, r = W // 2, 175, 70
    for y in range(cy - r, cy + 1):
        t = (y - (cy - r)) / r
        if y > cy - r * 0.6 and int((y - cy) / 7) % 2 == 0 and y > cy - 40:
            continue
        half = int(math.sqrt(max(0, r * r - (y - cy) ** 2)))
        col = (255, int(220 - 140 * t), int(80 + 60 * t))
        d.line((cx - half, y, cx + half, y), fill=col)
    d.rectangle((0, 180, W, H), fill=(15, 0, 35))
    for i in range(-12, 13):
        d.line((cx + i * 12, 180, cx + i * 70, H), fill=(255, 40, 200), width=1)
    y = 180
    gap = 4
    while y < H:
        d.line((0, y, W, y), fill=(255, 40, 200))
        y += gap
        gap = int(gap * 1.35) + 1
    return img.filter(ImageFilter.GaussianBlur(0.4))


def circuit():
    img = vgrad((2, 30, 25), (0, 12, 12))
    d = ImageDraw.Draw(img)
    rnd = random.Random(4)
    for _ in range(90):
        x, y = rnd.randrange(0, W, 8), rnd.randrange(0, H, 8)
        col = rnd.choice([(0, 200, 140), (0, 160, 120), (200, 170, 60)])
        for _ in range(rnd.randint(2, 5)):
            dx, dy = rnd.choice([(1, 0), (0, 1), (1, 1), (-1, 1), (-1, 0), (0, -1)])
            L = rnd.randint(2, 8) * 8
            nx, ny = x + dx * L, y + dy * L
            d.line((x, y, nx, ny), fill=col, width=2)
            x, y = nx, ny
        d.ellipse((x - 3, y - 3, x + 3, y + 3), outline=col, width=2)
    for _ in range(6):
        x, y = rnd.randrange(40, W - 80), rnd.randrange(40, H - 60)
        d.rectangle((x, y, x + 46, y + 30), fill=(10, 10, 10), outline=(80, 80, 80))
        for i in range(5):
            d.line((x + 6 + i * 8, y - 5, x + 6 + i * 8, y), fill=(200, 170, 60), width=2)
            d.line((x + 6 + i * 8, y + 30, x + 6 + i * 8, y + 35), fill=(200, 170, 60), width=2)
    return img


def carbon():
    tile = Image.new("RGB", (16, 16))
    d = ImageDraw.Draw(tile)
    for i in range(8):
        g = 25 + i * 5
        d.line((i, 0, i, 7), fill=(g, g, g + 3))
        d.line((8, i, 15, i), fill=(g, g, g + 3))
        d.line((i + 8, 8, i + 8, 15), fill=(g, g, g + 3))
        d.line((0, i + 8, 7, i + 8), fill=(g, g, g + 3))
    img = Image.new("RGB", (W, H))
    for x in range(0, W, 16):
        for y in range(0, H, 16):
            img.paste(tile, (x, y))
    shade = vgrad((60, 60, 60), (0, 0, 0))
    img = Image.blend(img, shade, 0.25)
    d = ImageDraw.Draw(img)
    d.line((0, 300, W, 140), fill=(220, 30, 30), width=6)
    d.line((0, 312, W, 152), fill=(140, 20, 20), width=2)
    return img


def planet():
    img = Image.new("RGB", (W, H), (2, 2, 10))
    d = ImageDraw.Draw(img)
    rnd = random.Random(8)
    for _ in range(400):
        x, y, b = rnd.randrange(W), rnd.randrange(H), rnd.randrange(80, 255)
        d.point((x, y), fill=(b, b, min(255, b + 20)))
    arr = np.asarray(img, dtype=float)
    yy, xx = np.mgrid[0:H, 0:W]
    cx, cy, r = 400, 330, 210
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    inside = dist < r
    shade = np.clip(1 - ((xx - cx + 80) ** 2 + (yy - cy + 120) ** 2) ** 0.5 / (r * 1.6), 0.05, 1)
    tex = noise(11, 5, 4)
    bands = 0.5 + 0.5 * np.sin(yy / 9 + tex * 6)
    col = np.stack([40 + 120 * bands, 90 + 100 * bands, 180 + 60 * bands], -1) * shade[..., None]
    arr[inside] = col[inside]
    glow = np.exp(-((dist - r) ** 2) / (2 * 6 ** 2)) * (dist >= r)
    arr += glow[..., None] * np.array([80, 160, 255])
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def hexneon():
    img = vgrad((8, 6, 24), (2, 2, 8))
    d = ImageDraw.Draw(img)
    s = 22
    hw = s * math.sqrt(3)
    rnd = random.Random(3)
    row = 0
    y = 0.0
    while y < H + s:
        x = (hw / 2 if row % 2 else 0)
        while x < W + hw:
            pts = [(x + s * math.cos(math.radians(a + 30)), y + s * math.sin(math.radians(a + 30))) for a in range(0, 360, 60)]
            lit = rnd.random() < 0.12
            col = rnd.choice([(0, 220, 255), (255, 0, 200), (120, 255, 80)]) if lit else (30, 30, 70)
            d.polygon(pts, outline=col, fill=(col[0] // 6, col[1] // 6, col[2] // 6) if lit else None)
            x += hw
        y += s * 1.5
        row += 1
    glow = img.filter(ImageFilter.GaussianBlur(3))
    return Image.blend(glow, img, 0.6)


def matrix():
    img = Image.new("RGB", (W, H), (0, 6, 0))
    d = ImageDraw.Draw(img)
    from build_manga import jfont
    font = jfont(12)
    rnd = random.Random(6)
    chars = "01アイウエオカキクケコサシスセソ<>{}=+*"
    for x in range(0, W, 12):
        head = rnd.randrange(-H, H)
        length = rnd.randrange(80, 260)
        for y in range(0, H, 14):
            dist = head - y
            if 0 <= dist <= length:
                k = 1 - dist / length
                col = (180, 255, 180) if dist < 14 else (0, int(60 + 180 * k), int(30 * k))
                d.text((x, y), rnd.choice(chars), font=font, fill=col)
    return img


def magma():
    v = noise(21, 6, 3)
    v = np.abs(v - 0.5) * 2
    v = 1 - v ** 0.35
    return colorize(v, [(0, (10, 0, 0)), (.4, (60, 5, 0)), (.65, (200, 40, 0)), (.85, (255, 150, 20)),
                        (1, (255, 240, 160))])


def cote_emeraude():
    """Coucher de soleil sur la mer avec un phare."""
    img = vgrad((25, 20, 70), (255, 140, 60))
    arr = np.asarray(img, dtype=float).copy()
    horizon = 200
    sea = vgrad((10, 70, 90), (2, 20, 35))
    arr[horizon:] = np.asarray(sea, dtype=float)[horizon:]
    img = Image.fromarray(arr.astype(np.uint8))
    d = ImageDraw.Draw(img)
    d.ellipse((300, 150, 380, 230), fill=(255, 200, 110))
    d.rectangle((0, horizon, W, H), fill=None)
    sea_img = Image.fromarray(arr.astype(np.uint8)).crop((0, horizon, W, H))
    img.paste(sea_img, (0, horizon))
    d = ImageDraw.Draw(img)
    rnd = random.Random(2)
    for y in range(horizon + 4, H, 6):
        for _ in range(6):
            x = rnd.randrange(260, 420)
            wl = rnd.randrange(8, 30)
            d.line((x, y, x + wl, y), fill=(255, 190, 110), width=1)
    d.polygon([(0, 215), (60, 185), (140, 200), (170, 215), (0, 230)], fill=(10, 10, 20))
    d.polygon([(78, 188), (98, 188), (95, 120), (81, 120)], fill=(235, 235, 235))
    for y in (135, 155, 175):
        d.rectangle((80, y, 96, y + 6), fill=(200, 30, 40))
    d.rectangle((78, 110, 98, 120), fill=(30, 30, 30))
    d.polygon([(76, 110), (100, 110), (88, 98)], fill=(200, 30, 40))
    d.polygon([(88, 114), (0, 90), (0, 130)], fill=(255, 240, 180, 60))
    return img.filter(ImageFilter.GaussianBlur(0.5))


BACKGROUNDS = {
    "Nebuleuse": nebula, "Aurore boreale": aurora, "Synthwave": synthwave, "Circuit imprime": circuit,
    "Fibre de carbone": carbon, "Planete": planet, "Hexagones neon": hexneon, "Matrix": matrix,
    "Magma": magma, "Cote d'Emeraude": cote_emeraude,
}


def with_panels(img: Image.Image) -> Image.Image:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for box in [(8, 8, 236, 152), (244, 8, 472, 152), (8, 160, 236, 312), (244, 160, 472, 312)]:
        d.rounded_rectangle(box, radius=12, fill=(0, 0, 0, 125), outline=(255, 255, 255, 70), width=1)
    out = img.convert("RGBA")
    out.alpha_composite(layer)
    return out.convert("RGB")


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in BACKGROUNDS.items():
        art = fn().convert("RGB").resize((W, H))
        art.save(OUT / f"{name}.jpg", quality=95)
        # one ready-to-use theme per background (layout "Helio Sombre")
        d = ROOT / "themes" / f"Fond {name}"
        if d.exists():
            continue
        src = bt.THEMES / "Helio Sombre" / "Helio Sombre.ui"
        from core.model import load_bundle
        b = load_bundle(src)
        d.mkdir(parents=True, exist_ok=True)
        b.base_dir = str(d)
        b.theme.widget_parents[0].background_image_path = set_background(d, with_panels(art))
        save_bundle(b, d / f"Fond {name}.ui")
        print("theme", d.name)


if __name__ == "__main__":
    build()
