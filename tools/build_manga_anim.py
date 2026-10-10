"""10 animated manga themes (8 frames each, drawn in code) — background frames + bottom strip of values."""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import build_manga as bm  # noqa: E402
from build_backgrounds import vgrad  # noqa: E402
from core.model import W, H, new_theme, save_bundle, set_background_frames  # noqa: E402

FRAMES = 8
DELAY_MS = 120
TAU = 2 * math.pi


def glow_text(img, pos, text, font, col, blur=4, alpha=255):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text(pos, text, font=font, fill=col + (alpha,))
    img = Image.alpha_composite(img.convert("RGBA"), layer.filter(ImageFilter.GaussianBlur(blur)))
    ImageDraw.Draw(img).text(pos, text, font=font, fill=(255, 255, 255, alpha))
    return img.convert("RGB")


# 1 ------------------------------------------------------------ speed lines
def a_speed(t):
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    cx, cy = 300, 130
    rnd = random.Random(int(t * FRAMES) + 1)
    for _ in range(200):
        a = rnd.random() * TAU
        r0 = rnd.randint(70, 130)
        w = rnd.uniform(0.6, 2.4) * math.pi / 180
        d.polygon([(cx + math.cos(a) * r0, cy + math.sin(a) * r0),
                   (cx + math.cos(a - w) * 600, cy + math.sin(a - w) * 600),
                   (cx + math.cos(a + w) * 600, cy + math.sin(a + w) * 600)], fill=(0, 0, 0))
    r = 58 + 8 * math.sin(t * TAU)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(230, 30, 40))
    d.text((cx, cy), "ドン!", font=bm.jfont(int(42 + 8 * math.sin(t * TAU))), fill=(255, 255, 255), anchor="mm",
           stroke_width=3, stroke_fill=(0, 0, 0))
    return img


# 2 ---------------------------------------------------------------- sakura
def a_sakura(t):
    img = vgrad((255, 180, 200), (120, 60, 140))
    d = ImageDraw.Draw(img)
    d.ellipse((330, 30, 420, 120), fill=(255, 240, 230))
    d.polygon([(40, 230), (200, 80), (230, 100), (260, 85), (420, 230)], fill=(90, 70, 140))
    d.polygon([(175, 105), (200, 80), (230, 100), (260, 85), (285, 110), (250, 108), (230, 118), (205, 108)],
              fill=(250, 250, 255))
    d.rectangle((0, 230, W, H), fill=(60, 30, 80))
    d.line([(W, 25), (380, 55), (330, 45), (290, 75)], fill=(60, 30, 30), width=7)
    rnd = random.Random(5)
    for _ in range(90):
        x, y, r = rnd.randint(270, W), rnd.randint(5, 100), rnd.randint(3, 7)
        d.ellipse((x - r, y - r, x + r, y + r), fill=rnd.choice([(255, 190, 210), (255, 220, 235), (250, 160, 190)]))
    rnd = random.Random(11)
    for _ in range(45):
        x0, y0, sp = rnd.randint(0, W), rnd.randint(0, H), rnd.uniform(0.6, 1.4)
        y = (y0 + t * H * sp) % H
        x = (x0 - t * 120 * sp + 10 * math.sin((y / 30) + x0)) % W
        r = rnd.randint(2, 4)
        d.ellipse((x - r, y - r / 2, x + r, y + r / 2), fill=(255, 205, 225))
    return img


# 3 ----------------------------------------------------------------- torii
def a_torii(t):
    img = bm.torii()
    d = ImageDraw.Draw(img)
    d.rectangle((150, 232, 330, 300), fill=(30, 10, 30))
    rnd = random.Random(int(t * FRAMES))
    for y in range(236, 300, 6):
        w = 40 + rnd.randint(-15, 15) + int(10 * math.sin(t * TAU + y / 9))
        off = int(6 * math.sin(t * TAU + y / 13))
        d.line((240 - w + off, y, 240 + w + off, y), fill=(255, 160, 90), width=2)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse((175, 75, 305, 205), fill=(255, 230, 150, int(60 + 50 * math.sin(t * TAU))))
    return Image.alpha_composite(img.convert("RGBA"), layer.filter(ImageFilter.GaussianBlur(14))).convert("RGB")


# 4 ----------------------------------------------------------- tokyo night
def a_tokyo(t):
    img = vgrad((10, 5, 40), (60, 10, 80))
    d = ImageDraw.Draw(img)
    rnd = random.Random(9)
    tw = random.Random(int(t * FRAMES) + 50)
    x = 0
    while x < W:
        w, h = rnd.randint(25, 60), rnd.randint(80, 220)
        d.rectangle((x, H - h, x + w, H), fill=(15, 10, 30))
        for wy in range(H - h + 8, H - 6, 10):
            for wx in range(x + 4, x + w - 4, 8):
                lit = rnd.random() < 0.35
                if lit and tw.random() < 0.9:
                    d.rectangle((wx, wy, wx + 3, wy + 4), fill=rnd.choice([(255, 220, 120), (120, 220, 255)]))
                else:
                    rnd.random()
        x += w + 2
    f = bm.jfont(22)
    for i, (text, pos, col) in enumerate((("東京", (60, 90), (255, 60, 160)), ("ラーメン", (200, 130), (60, 230, 255)),
                                         ("夜", (400, 70), (255, 200, 60)))):
        on = not (i == int(t * FRAMES) % 3 and int(t * FRAMES) % 2 == 0)
        img = glow_text(img, pos, text, f, col, alpha=255 if on else 90)
    return img


# 5 ---------------------------------------------------------- samurai moon
def a_samurai(t):
    img = vgrad((10, 10, 30), (60, 20, 30))
    d = ImageDraw.Draw(img)
    d.ellipse((260, 20, 420, 180), fill=(240, 230, 200))
    d.rectangle((0, 240, W, H), fill=(5, 5, 10))
    s = (5, 5, 10)
    d.polygon([(170, 240), (185, 160), (205, 155), (220, 240)], fill=s)
    d.ellipse((186, 132, 206, 154), fill=s)
    d.polygon([(178, 136), (214, 136), (196, 126)], fill=s)
    blade = 0.15 * math.sin(t * TAU)
    d.line((205, 170, 205 + 125 * math.cos(-0.5 + blade), 170 + 125 * math.sin(-0.5 + blade)),
           fill=(220, 220, 230), width=3)
    sway = 4 * math.sin(t * TAU)
    d.polygon([(185, 165), (150 - sway, 230), (172, 236)], fill=s)
    rnd = random.Random(2)
    for _ in range(50):
        x0, y0, sp = rnd.randint(0, W), rnd.randint(0, 240), rnd.uniform(0.7, 1.3)
        x = (x0 + t * 200 * sp) % W
        y = (y0 + t * 120 * sp) % 240
        d.line((x, y, x + 6, y + 2), fill=(200, 60, 80), width=2)
    return img


# 6 ------------------------------------------------------------------ wave
def a_wave(t):
    img = Image.new("RGB", (W, H), (240, 228, 200))
    d = ImageDraw.Draw(img)
    d.ellipse((330, 30, 400, 100), fill=(220, 70, 50))
    layers = ((150, 34, (110, 150, 200)), (180, 30, (60, 100, 165)), (210, 26, (30, 65, 130)),
              (240, 20, (15, 40, 95)))
    for k, (base, amp, col) in enumerate(layers):
        ph = t * TAU * (1 if k % 2 else -1)
        pts, crests = [(0, H)], []
        for x in range(0, W + 1, 3):
            y = base + amp * math.sin(x / 38 + k * 1.7 + ph) + amp * 0.35 * math.sin(x / 13 + k + ph * 2)
            pts.append((x, y))
            if (x // 3) % 9 == 0:
                crests.append((x, y))
        pts.append((W, H))
        d.polygon(pts, fill=col)
        for x, y in crests:
            d.arc((x - 10, y - 8, x + 10, y + 8), 180, 330, fill=(250, 250, 245), width=3)
    return img


# 7 ------------------------------------------------------------ comic page
def a_comic(t):
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for y in range(0, H, 8):
        for x in range(0, W, 8):
            k = 0.5 + 0.5 * math.sin(x / 60 - t * TAU) * math.cos(y / 50)
            r = 3.4 * k * (1 - y / H) + 0.4
            d.ellipse((x - r, y - r, x + r, y + r), fill=(30, 30, 30))
    for box in ((6, 6, 300, 140), (306, 6, 474, 140), (6, 146, 180, 222), (186, 146, 474, 222)):
        d.rectangle(box, outline=(0, 0, 0), width=4)
    size = int(36 + 10 * abs(math.sin(t * TAU)))
    d.text((390, 70), "バン", font=bm.jfont(size), fill=(230, 40, 40), anchor="mm", stroke_width=3,
           stroke_fill=(0, 0, 0))
    d.text((90, 184), "!?" if int(t * FRAMES) % 2 == 0 else "!!", font=bm.jfont(44), fill=(0, 0, 0), anchor="mm")
    return img


# 8 -------------------------------------------------------------- lanterns
def a_lanterns(t):
    img = vgrad((5, 5, 25), (30, 5, 20))
    rnd = random.Random(7)
    d0 = ImageDraw.Draw(img)
    d0.line((0, 40, W, 70), fill=(40, 30, 30), width=2)
    d0.line((0, 150, W, 120), fill=(40, 30, 30), width=2)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    lan = []
    for i in range(9):
        x = 25 + i * 55
        y = (55 + i * 3) if i % 2 == 0 else (150 - i * 3)
        s = rnd.randint(16, 22)
        swing = 3 * math.sin(t * TAU + i)
        a = int(90 + 60 * (0.5 + 0.5 * math.sin(t * TAU * 2 + i * 1.7)))
        lan.append((x + swing, y, s))
        gd.ellipse((x + swing - s * 2, y - s * 2, x + swing + s * 2, y + s * 2.4), fill=(255, 90, 30, a))
    img = Image.alpha_composite(img.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(12))).convert("RGB")
    d = ImageDraw.Draw(img)
    f = bm.jfont(14)
    for x, y, s in lan:
        d.ellipse((x - s, y - s * 0.8, x + s, y + s * 1.4), fill=(225, 40, 30))
        d.rectangle((x - s * 0.6, y - s * 0.95, x + s * 0.6, y - s * 0.75), fill=(30, 20, 10))
        d.rectangle((x - s * 0.6, y + s * 1.3, x + s * 0.6, y + s * 1.5), fill=(30, 20, 10))
        d.text((x, y + s * 0.3), "祭", font=f, fill=(255, 230, 180), anchor="mm")
    return img


# 9 ------------------------------------------------------------ neon alley
def a_alley(t):
    img = vgrad((15, 5, 35), (5, 20, 40))
    d = ImageDraw.Draw(img)
    d.polygon([(0, 0), (150, 60), (150, 300), (0, H)], fill=(20, 15, 40))
    d.polygon([(W, 0), (330, 60), (330, 300), (W, H)], fill=(20, 15, 40))
    d.polygon([(150, 300), (330, 300), (W, H), (0, H)], fill=(25, 20, 45))
    f = bm.jfont(18)
    frame = int(t * FRAMES)
    for i, (text, x, y, col) in enumerate((("バー", 40, 60, (255, 60, 200)), ("24H", 360, 50, (60, 255, 220)),
                                          ("ホテル", 20, 140, (255, 200, 60)), ("寿司", 380, 130, (255, 80, 80)))):
        on = not (i == frame % 4 and frame % 3 == 1)
        c = col if on else tuple(v // 4 for v in col)
        d.rectangle((x - 6, y - 6, x + 70, y + 28), outline=c, width=2)
        d.text((x, y), text, font=f, fill=c)
    img = Image.blend(img, img.filter(ImageFilter.GaussianBlur(5)), 0.35)
    d = ImageDraw.Draw(img)
    rnd = random.Random(3)
    for _ in range(170):
        x0, y0 = rnd.randint(0, W), rnd.randint(0, H)
        y = (y0 + t * H * 2) % H
        x = (x0 - (y - y0) * 0.25) % W
        d.line((x, y, x - 3, y + 12), fill=(140, 160, 220), width=1)
    return img


# 10 --------------------------------------------------------------- comet
def a_comet(t):
    img = vgrad((10, 20, 70), (230, 120, 160))
    d = ImageDraw.Draw(img)
    rnd = random.Random(4)
    for i in range(200):
        x, y = rnd.randint(0, W), rnd.randint(0, 200)
        b = rnd.randint(150, 255)
        if (i + int(t * FRAMES)) % 7:
            d.point((x, y), fill=(b, b, 255))
    hx, hy = 80 + 340 * t, 20 + 110 * t
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for i in range(30):
        k = i / 30
        x, y = hx - 160 * (1 - k), hy - 52 * (1 - k)
        gd.line((x, y, x + 8, y + 3), fill=(200, 240, 255, 255), width=int(2 + 8 * k))
    img = Image.alpha_composite(img.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(3)))
    img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(10))).convert("RGB")
    d = ImageDraw.Draw(img)
    d.ellipse((hx - 7, hy - 7, hx + 7, hy + 7), fill=(255, 255, 255))
    pts = [(0, H)] + [(x, 230 + 15 * math.sin(x / 50) + 8 * math.sin(x / 17)) for x in range(0, W + 1, 6)] + [(W, H)]
    d.polygon(pts, fill=(20, 15, 40))
    return img


ANIMATED = {
    "Anime - Lignes de vitesse": a_speed, "Anime - Sakura": a_sakura, "Anime - Torii": a_torii,
    "Anime - Tokyo la nuit": a_tokyo, "Anime - Samourai": a_samurai, "Anime - Vague": a_wave,
    "Anime - Planche BD": a_comic, "Anime - Lanternes": a_lanterns, "Anime - Ruelle neon": a_alley,
    "Anime - Comete": a_comet,
}


def frames_for(fn) -> list[Image.Image]:
    return [bm.with_strip(fn(i / FRAMES).convert("RGB").resize((W, H))) for i in range(FRAMES)]


def build(names=None):
    for name, fn in ANIMATED.items():
        if names and name not in names:
            continue
        d = ROOT / "themes" / name
        b = new_theme(d, name)
        frames = frames_for(fn)
        parent = b.theme.widget_parents[0]
        parent.background_image_path = set_background_frames(d, frames)
        parent.image_delay = DELAY_MS
        b.theme.widgets += bm.strip_widgets()
        save_bundle(b, d / f"{name}.ui")
        # animated preview for the user
        frames[0].save(d / "apercu.gif", save_all=True, append_images=frames[1:], duration=DELAY_MS, loop=0)
        print("built", name)


if __name__ == "__main__":
    build()
