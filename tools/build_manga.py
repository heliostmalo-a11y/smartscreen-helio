"""10 original manga / Japan-style backgrounds (drawn in code, no copied artwork) + one theme each."""
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

from build_backgrounds import OUT, vgrad, with_panels  # noqa: E402
from core.model import W, H, load_bundle, save_bundle, set_background  # noqa: E402

FONT_CANDIDATES = ["NotoSansCJK-Bold.ttc", "NotoSansCJKjp-Bold.otf", "msgothic.ttc", "YuGothB.ttc",
                   "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "C:/Windows/Fonts/YuGothB.ttc",
                   "C:/Windows/Fonts/msgothic.ttc", "DejaVuSans-Bold.ttf"]


def jfont(size: int):
    for f in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(f, size)
        except Exception:
            continue
    return ImageFont.load_default()


def speed_lines():
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    cx, cy = 300, 160
    rnd = random.Random(1)
    for i in range(220):
        a = rnd.random() * 2 * math.pi
        r0 = rnd.randint(70, 130)
        w = rnd.uniform(0.6, 2.4) * math.pi / 180
        p = [(cx + math.cos(a) * r0, cy + math.sin(a) * r0),
             (cx + math.cos(a - w) * 600, cy + math.sin(a - w) * 600),
             (cx + math.cos(a + w) * 600, cy + math.sin(a + w) * 600)]
        d.polygon(p, fill=(0, 0, 0))
    d.ellipse((cx - 60, cy - 60, cx + 60, cy + 60), fill=(230, 30, 40))
    d.text((cx, cy), "ドン!", font=jfont(46), fill=(255, 255, 255), anchor="mm", stroke_width=3,
           stroke_fill=(0, 0, 0))
    return img


def sakura():
    img = vgrad((255, 180, 200), (120, 60, 140))
    d = ImageDraw.Draw(img)
    d.ellipse((330, 40, 420, 130), fill=(255, 240, 230))
    d.polygon([(40, 250), (200, 90), (230, 110), (260, 95), (420, 250)], fill=(90, 70, 140))
    d.polygon([(175, 115), (200, 90), (230, 110), (260, 95), (285, 120), (250, 118), (230, 128), (205, 118)],
              fill=(250, 250, 255))
    d.rectangle((0, 250, W, H), fill=(60, 30, 80))
    branch = [(W, 30), (380, 60), (330, 50), (290, 80)]
    d.line(branch, fill=(60, 30, 30), width=7)
    rnd = random.Random(5)
    for _ in range(90):
        x, y = rnd.randint(270, W), rnd.randint(10, 110)
        r = rnd.randint(3, 7)
        d.ellipse((x - r, y - r, x + r, y + r), fill=rnd.choice([(255, 190, 210), (255, 220, 235), (250, 160, 190)]))
    for _ in range(60):
        x, y, r = rnd.randint(0, W), rnd.randint(0, H), rnd.randint(2, 4)
        d.ellipse((x - r, y - r // 2, x + r, y + r // 2), fill=(255, 200, 220))
    return img


def torii():
    img = vgrad((255, 120, 60), (90, 20, 60))
    d = ImageDraw.Draw(img)
    d.ellipse((190, 90, 290, 190), fill=(255, 220, 140))
    d.rectangle((0, 230, W, H), fill=(30, 10, 30))
    for y in range(236, H, 7):
        d.line((200, y, 280, y), fill=(255, 150, 90), width=1)
    red = (200, 30, 30)
    d.rectangle((120, 70, 360, 84), fill=red)
    d.polygon([(105, 66), (375, 66), (360, 74), (120, 74)], fill=(30, 10, 10))
    d.rectangle((140, 100, 340, 110), fill=red)
    d.rectangle((160, 84, 176, 230), fill=red)
    d.rectangle((304, 84, 320, 230), fill=red)
    d.rectangle((232, 84, 248, 100), fill=red)
    return img


def tokyo_night():
    img = vgrad((10, 5, 40), (60, 10, 80))
    d = ImageDraw.Draw(img)
    rnd = random.Random(9)
    x = 0
    while x < W:
        w = rnd.randint(25, 60)
        h = rnd.randint(80, 240)
        d.rectangle((x, H - h, x + w, H), fill=(15, 10, 30))
        for wy in range(H - h + 8, H - 6, 10):
            for wx in range(x + 4, x + w - 4, 8):
                if rnd.random() < 0.35:
                    d.rectangle((wx, wy, wx + 3, wy + 4), fill=rnd.choice([(255, 220, 120), (120, 220, 255)]))
        x += w + 2
    f = jfont(22)
    for text, pos, col in (("東京", (60, 120), (255, 60, 160)), ("ラーメン", (200, 170), (60, 230, 255)),
                           ("夜", (400, 100), (255, 200, 60))):
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gd.text(pos, text, font=f, fill=col + (255,))
        img = Image.alpha_composite(img.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(4))).convert("RGB")
        ImageDraw.Draw(img).text(pos, text, font=f, fill=(255, 255, 255))
    return img


def katana_moon():
    img = vgrad((10, 10, 30), (60, 20, 30))
    d = ImageDraw.Draw(img)
    d.ellipse((260, 30, 420, 190), fill=(240, 230, 200))
    d.ellipse((290, 40, 440, 190), fill=None)
    d.rectangle((0, 260, W, H), fill=(5, 5, 10))
    s = (5, 5, 10)
    d.polygon([(170, 260), (185, 180), (205, 175), (220, 260)], fill=s)          # body + coat
    d.ellipse((186, 152, 206, 174), fill=s)                                       # head
    d.polygon([(178, 156), (214, 156), (196, 146)], fill=s)                       # hat
    d.line((205, 190, 330, 120), fill=(200, 200, 210), width=3)                   # blade
    d.line((200, 193, 212, 186), fill=s, width=6)
    rnd = random.Random(2)
    for _ in range(40):
        x, y = rnd.randint(0, W), rnd.randint(0, 250)
        d.line((x, y, x + 6, y + 2), fill=(200, 60, 80), width=2)
    return img


def wave():
    img = Image.new("RGB", (W, H), (240, 228, 200))
    d = ImageDraw.Draw(img)
    d.ellipse((330, 40, 400, 110), fill=(220, 70, 50))
    layers = ((150, 34, (110, 150, 200)), (190, 30, (60, 100, 165)), (230, 26, (30, 65, 130)),
              (270, 20, (15, 40, 95)))
    for k, (base, amp, col) in enumerate(layers):
        pts = [(0, H)]
        crests = []
        for x in range(0, W + 1, 3):
            y = base + amp * math.sin(x / 38 + k * 1.7) + amp * 0.35 * math.sin(x / 13 + k)
            pts.append((x, y))
            if (x // 3) % 9 == 0:
                crests.append((x, y))
        pts.append((W, H))
        d.polygon(pts, fill=col)
        for x, y in crests:
            d.arc((x - 10, y - 8, x + 10, y + 8), 180, 330, fill=(250, 250, 245), width=3)
    return img


def halftone():
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for y in range(0, H, 8):
        for x in range(0, W, 8):
            r = 3.6 * (x / W) * (1 - y / H) + 0.4
            d.ellipse((x - r, y - r, x + r, y + r), fill=(30, 30, 30))
    for box in ((6, 6, 300, 150), (306, 6, 474, 150), (6, 156, 180, 314), (186, 156, 474, 314)):
        d.rectangle(box, outline=(0, 0, 0), width=4)
    d.text((390, 70), "バン", font=jfont(40), fill=(230, 40, 40), anchor="mm", stroke_width=3, stroke_fill=(0, 0, 0))
    d.text((90, 235), "!?", font=jfont(52), fill=(0, 0, 0), anchor="mm")
    return img


def lanterns():
    img = vgrad((5, 5, 25), (30, 5, 20))
    rnd = random.Random(7)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    lanterns = []
    d0 = ImageDraw.Draw(img)
    d0.line((0, 40, W, 70), fill=(40, 30, 30), width=2)
    d0.line((0, 150, W, 120), fill=(40, 30, 30), width=2)
    for i in range(9):
        x = 25 + i * 55
        y = int(45 + i * 3) + 10 if i % 2 == 0 else int(140 - i * 3) + 10
        s = rnd.randint(16, 22)
        lanterns.append((x, y, s))
        gd.ellipse((x - s * 2, y - s * 2, x + s * 2, y + s * 2.4), fill=(255, 90, 30, 120))
    img = Image.alpha_composite(img.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(12))).convert("RGB")
    d = ImageDraw.Draw(img)
    f = jfont(14)
    for x, y, s in lanterns:
        d.ellipse((x - s, y - s * 0.8, x + s, y + s * 1.4), fill=(225, 40, 30))
        d.rectangle((x - s * 0.6, y - s * 0.95, x + s * 0.6, y - s * 0.75), fill=(30, 20, 10))
        d.rectangle((x - s * 0.6, y + s * 1.3, x + s * 0.6, y + s * 1.5), fill=(30, 20, 10))
        d.text((x, y + s * 0.3), "祭", font=f, fill=(255, 230, 180), anchor="mm")
    d.rectangle((0, 280, W, H), fill=(10, 5, 10))
    return img


def cyber_alley():
    img = vgrad((15, 5, 35), (5, 20, 40))
    d = ImageDraw.Draw(img)
    d.polygon([(0, 0), (150, 60), (150, 300), (0, H)], fill=(20, 15, 40))
    d.polygon([(W, 0), (330, 60), (330, 300), (W, H)], fill=(20, 15, 40))
    d.polygon([(150, 300), (330, 300), (W, H), (0, H)], fill=(25, 20, 45))
    f = jfont(18)
    for text, x, y, col in (("バー", 40, 80, (255, 60, 200)), ("24H", 360, 70, (60, 255, 220)),
                            ("ホテル", 20, 170, (255, 200, 60)), ("寿司", 380, 160, (255, 80, 80))):
        d.rectangle((x - 6, y - 6, x + 70, y + 28), outline=col, width=2)
        d.text((x, y), text, font=f, fill=col)
    img = Image.blend(img, img.filter(ImageFilter.GaussianBlur(5)), 0.35)
    d = ImageDraw.Draw(img)
    rnd = random.Random(3)
    for _ in range(160):
        x, y = rnd.randint(0, W), rnd.randint(0, H)
        d.line((x, y, x - 3, y + 12), fill=(140, 160, 220), width=1)
    return img


def comet_sky():
    img = vgrad((10, 20, 70), (230, 120, 160))
    d = ImageDraw.Draw(img)
    rnd = random.Random(4)
    for _ in range(200):
        x, y = rnd.randint(0, W), rnd.randint(0, 200)
        b = rnd.randint(150, 255)
        d.point((x, y), fill=(b, b, 255))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for i in range(30):
        t = i / 30
        gd.line((60 + 300 * t, 20 + 120 * t, 72 + 300 * t, 25 + 120 * t), fill=(200, 240, 255, 255), width=int(2 + 10 * t))
    img = Image.alpha_composite(img.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(3))).convert("RGB")
    img = Image.alpha_composite(img.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(10))).convert("RGB")
    d = ImageDraw.Draw(img)
    d.ellipse((355, 136, 371, 152), fill=(255, 255, 255))
    pts = [(0, H)] + [(x, 250 + 15 * math.sin(x / 50) + 8 * math.sin(x / 17)) for x in range(0, W + 1, 6)] + [(W, H)]
    d.polygon(pts, fill=(20, 15, 40))
    for x in range(30, W, 70):
        d.rectangle((x, 230, x + 3, 262), fill=(20, 15, 40))
    return img


MANGA = {
    "Manga - Lignes de vitesse": speed_lines, "Manga - Sakura": sakura, "Manga - Torii": torii,
    "Manga - Tokyo la nuit": tokyo_night, "Manga - Samourai lune": katana_moon, "Manga - Vague": wave,
    "Manga - Planche BD": halftone, "Manga - Lanternes": lanterns, "Manga - Ruelle neon": cyber_alley,
    "Manga - Comete": comet_sky,
}


def with_strip(img: Image.Image) -> Image.Image:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((6, 228, W - 6, H - 6), radius=12, fill=(0, 0, 0, 175), outline=(255, 255, 255, 80))
    out = img.convert("RGBA")
    out.alpha_composite(layer)
    return out.convert("RGB")


def strip_widgets():
    """Bottom strip: per column label, temperature, load % and a small load bar; clock on the right."""
    from core.model import T_BAR, T_DATETIME, T_TEXT, T_VALUE, new_widget
    cols = [("CPU", "TCPUDIO", "°C", "SCPUUTI", "#7fd8ff", "#00b4ff"),
            ("GPU", "TGPU1", "°C", "SGPU1UTI", "#8dff8d", "#3ce03c"),
            ("RAM", None, "", "SMEMUTI", "#ffc04d", "#ffaa00")]
    ws = []
    x = 14
    for label, temp, unit, load, col, bar in cols:
        ws.append(new_widget(T_TEXT, x, 233, 40, 18, text=label, size=10, color=col))
        if temp:
            ws += [new_widget(T_VALUE, x - 6, 249, 52, 30, sensor=temp, size=19, color="#ffffff", sample="50"),
                   new_widget(T_TEXT, x + 44, 255, 24, 18, text=unit, size=10, color=col),
                   new_widget(T_VALUE, x + 56, 253, 30, 22, sensor=load, size=11, color="#ffffff", sample="12"),
                   new_widget(T_TEXT, x + 90, 256, 12, 16, text="%", size=8, color=col)]
        else:
            ws += [new_widget(T_VALUE, x - 6, 249, 52, 30, sensor=load, size=19, color="#ffffff", sample="47"),
                   new_widget(T_TEXT, x + 44, 255, 24, 18, text="%", size=10, color=col)]
        ws += [new_widget(T_TEXT, x, 282, 60, 14, text="charge", size=7, color="#aaaaaa"),
               new_widget(T_BAR, x, 296, 86, 9, sensor=load, fg=bar, bg="#202020", frame="#505050")]
        x += 100
    ws += [new_widget(T_DATETIME, 312, 240, 156, 40, format="hh:nn:ss", size=22, color="#ffffff"),
           new_widget(T_DATETIME, 312, 282, 156, 26, format="yyyy-mm-dd", size=12, color="#dddddd")]
    return ws


def build():
    from core.model import new_theme
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in MANGA.items():
        art = fn().convert("RGB").resize((W, H))
        art.save(OUT / f"{name}.jpg", quality=95)
        d = ROOT / "themes" / name
        b = new_theme(d, name)
        b.theme.widget_parents[0].background_image_path = set_background(d, with_strip(art))
        b.theme.widgets += strip_widgets()
        save_bundle(b, d / f"{name}.ui")


if __name__ == "__main__":
    build()
