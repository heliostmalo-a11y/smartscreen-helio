"""Animated theme: generic 4-string electric bass (original drawing, no brand), vibrating strings."""
from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import build_manga as bm  # noqa: E402
from build_backgrounds import vgrad  # noqa: E402
from core.model import W, H, new_theme, save_bundle, set_background_frames  # noqa: E402

FRAMES, DELAY = 8, 100


def body_mask(scale=1.0) -> Image.Image:
    """Original offset double-cutaway body, drawn in a 260x170 box."""
    m = Image.new("L", (260, 170), 0)
    d = ImageDraw.Draw(m)
    d.ellipse((0, 40, 150, 170), fill=255)            # lower bout
    d.ellipse((40, 10, 170, 120), fill=255)           # upper bout
    d.ellipse((120, 55, 230, 150), fill=255)          # waist / lower horn area
    d.polygon([(150, 20), (250, 0), (255, 15), (190, 60)], fill=255)    # upper horn
    d.polygon([(200, 100), (258, 115), (250, 130), (190, 135)], fill=255)  # lower horn
    d.ellipse((140, 60, 205, 100), fill=0)            # cutaway
    return m.filter(ImageFilter.GaussianBlur(1.5)).point(lambda v: 255 if v > 128 else 0)


def frame(t: float) -> Image.Image:
    img = vgrad((25, 12, 40), (5, 5, 12))
    # stage light
    light = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(light).ellipse((60, -120, 420, 260), fill=(255, 170, 80, 70))
    img = Image.alpha_composite(img.convert("RGBA"), light.filter(ImageFilter.GaussianBlur(40)))

    bass = Image.new("RGBA", (520, 200), (0, 0, 0, 0))
    mask = body_mask()
    # sunburst body
    yy, xx = [v for v in __import__("numpy").mgrid[0:170, 0:260]]
    import numpy as np
    r = np.sqrt(((xx - 110) / 130) ** 2 + ((yy - 90) / 85) ** 2)
    col = np.stack([np.interp(r, [0, .45, .8, 1.1], [250, 230, 120, 25]),
                    np.interp(r, [0, .45, .8, 1.1], [190, 120, 30, 10]),
                    np.interp(r, [0, .45, .8, 1.1], [60, 20, 10, 5]),
                    np.full_like(r, 255)], -1).astype(np.uint8)
    body = Image.fromarray(col, "RGBA")
    bass.paste(body, (10, 15), mask)
    d = ImageDraw.Draw(bass)
    # pickguard (tortoise-ish) and pickups
    d.polygon([(60, 70), (150, 45), (190, 70), (150, 130), (80, 140)], fill=(60, 25, 15, 255), outline=(20, 10, 5))
    d.rounded_rectangle((95, 78, 113, 120), radius=4, fill=(15, 15, 15, 255))
    d.rounded_rectangle((128, 72, 146, 114), radius=4, fill=(15, 15, 15, 255))
    for k in (40, 52, 64):
        d.ellipse((k, 125 + (k - 40) // 3, k + 10, 135 + (k - 40) // 3), fill=(200, 200, 200, 255))  # knobs
    d.rectangle((40, 80, 58, 112), fill=(170, 170, 175, 255))   # bridge
    # neck + frets + headstock (generic paddle shape, no logo)
    d.polygon([(190, 82), (470, 86), (470, 104), (190, 110)], fill=(200, 150, 90, 255))
    d.polygon([(200, 84), (470, 87), (470, 103), (200, 108)], fill=(90, 50, 25, 255))
    for i in range(20):
        x = 200 + 270 * (1 - 0.94 ** i) / (1 - 0.94 ** 20)
        d.line((x, 84, x, 108), fill=(200, 200, 200, 255), width=1)
    d.polygon([(470, 82), (515, 74), (518, 112), (470, 108)], fill=(40, 30, 25, 255))
    for k in range(4):
        d.ellipse((480 + k * 9, 70 - (k % 2) * 4, 488 + k * 9, 78 - (k % 2) * 4), fill=(210, 210, 210, 255))
    # strings: vibrating (amplitude decays from the middle)
    for s in range(4):
        y0 = 89 + s * 5
        amp = 2.2 * math.sin(t * 2 * math.pi * (1 + s * 0.5))
        pts = []
        for x in range(50, 476, 6):
            u = (x - 50) / 426
            pts.append((x, y0 + amp * math.sin(math.pi * u)))
        d.line(pts, fill=(235, 235, 235, 255), width=1 + (s < 2))
    bass = bass.rotate(12, resample=Image.Resampling.BICUBIC, expand=True)
    bass = bass.crop(bass.getbbox())
    k = min(470 / bass.width, 205 / bass.height)
    bass = bass.resize((int(bass.width * k), int(bass.height * k)), Image.Resampling.LANCZOS)
    ox, oy = (W - bass.width) // 2, 14
    shadow = Image.new("RGBA", bass.size, (0, 0, 0, 0))
    shadow.putalpha(bass.getchannel("A").point(lambda v: int(v * 0.35)))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(8)), (ox + 6, oy + 8))
    img.alpha_composite(bass, (ox, oy))
    # floating notes
    f = bm.jfont(26)
    dn = ImageDraw.Draw(img)
    for i, (x0, y0) in enumerate(((380, 160), (420, 110), (350, 70))):
        y = y0 - 30 * ((t + i / 3) % 1)
        a = int(255 * (1 - (t + i / 3) % 1))
        dn.text((x0, y), "♪" if i % 2 else "♫", font=f, fill=(255, 210, 120, a))
    return img.convert("RGB")


def build():
    name = "Anime - Basse"
    d = ROOT / "themes" / name
    b = new_theme(d, name)
    frames = [bm.with_strip(frame(i / FRAMES)) for i in range(FRAMES)]
    p = b.theme.widget_parents[0]
    p.background_image_path = set_background_frames(d, frames)
    p.image_delay = DELAY
    b.theme.widgets += bm.strip_widgets()
    save_bundle(b, d / f"{name}.ui")
    frames[0].save(d / "apercu.gif", save_all=True, append_images=frames[1:], duration=DELAY, loop=0)
    return frames


if __name__ == "__main__":
    build()
