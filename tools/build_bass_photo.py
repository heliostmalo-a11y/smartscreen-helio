"""Animated theme from the user's own bass photo (cut-out PNG with transparency)."""
from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import build_manga as bm  # noqa: E402
from build_backgrounds import vgrad  # noqa: E402
from core.model import W, H, new_theme, save_bundle, set_background_frames  # noqa: E402

FRAMES, DELAY = 8, 120


TINTS = {
    "normal": ((28, 14, 42), (4, 4, 10), (255, 175, 90, 85)),
    "orange": ((120, 50, 0), (20, 8, 0), (255, 150, 30, 150)),
    "rouge": ((140, 0, 0), (25, 0, 0), (255, 40, 30, 170)),
}


def frame(bass: Image.Image, t: float, moving_light: bool = True, tint: str = "normal", notes: bool = True) -> Image.Image:
    top, bottom, light_col = TINTS[tint]
    img = vgrad(top, bottom).convert("RGBA")
    # moving stage spotlight
    cx = 140 + 200 * (0.5 - 0.5 * math.cos(t * 2 * math.pi)) if moving_light else W / 2
    light = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(light).ellipse((cx - 170, -140, cx + 170, 230), fill=light_col)
    img.alpha_composite(light.filter(ImageFilter.GaussianBlur(45)))
    ox, oy = (W - bass.width) // 2, 40
    # floor reflection
    refl = bass.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    fade = Image.linear_gradient("L").resize(refl.size).point(lambda v: int(max(0, 90 - v * 0.9)))
    a = refl.getchannel("A").point(lambda v: v)
    refl.putalpha(Image.composite(fade, Image.new("L", refl.size, 0), a))
    img.alpha_composite(refl.filter(ImageFilter.GaussianBlur(1.5)), (ox, oy + bass.height - 6))
    # soft shadow + the bass, brightness follows the spotlight
    shadow = Image.new("RGBA", bass.size, (0, 0, 0, 0))
    shadow.putalpha(bass.getchannel("A").point(lambda v: int(v * 0.5)))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(7)), (ox + 5, oy + 7))
    lit = ImageEnhance.Brightness(bass).enhance(0.95 + 0.12 * math.sin(t * 2 * math.pi)) if moving_light else bass
    img.alpha_composite(lit, (ox, oy))
    if notes:
        draw_notes(img, t)
    return img.convert("RGB")


NOTES_BOX = (290, 150, 180, 76)   # x, y, w, h of the animated notes widget


def draw_notes(img: Image.Image, t: float, dx: int = 0, dy: int = 0):
    d = ImageDraw.Draw(img)
    f = bm.jfont(24)
    for i, (x0, y0) in enumerate(((300, 212), (360, 204), (420, 214))):
        p = (t + i / 3) % 1
        d.text((x0 + 6 * math.sin(p * 6) + dx, y0 - 34 * p + dy), "♫" if i % 2 else "♪", font=f,
               fill=(255, 210, 130, int(230 * (1 - p))))


def notes_frames(n: int) -> list[Image.Image]:
    x, y, w, h = NOTES_BOX
    out = []
    for i in range(n):
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw_notes(im, i / n, -x, -y)
        out.append(im)
    return out


def with_bands(img: Image.Image) -> Image.Image:
    """Bottom strip (values) + small top band (clock / date)."""
    img = bm.with_strip(img)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle((6, 4, W - 6, 34), radius=10, fill=(0, 0, 0, 175),
                                            outline=(255, 255, 255, 80))
    out = img.convert("RGBA")
    out.alpha_composite(layer)
    return out.convert("RGB")


def bass_widgets():
    from core.model import T_BAR, T_DATETIME, T_TEXT, T_VALUE, new_widget
    ws = [new_widget(T_DATETIME, 20, 7, 150, 26, format="hh:nn:ss", size=16, color="#ffffff"),
          new_widget(T_DATETIME, 300, 10, 160, 22, format="yyyy-mm-dd", size=12, color="#dddddd")]
    cols = [("CPU", "TCPUDIO", "SCPUUTI", "#7fd8ff", "#00b4ff"),
            ("GPU", "TGPU1", "SGPU1UTI", "#8dff8d", "#3ce03c"),
            ("RAM", None, "SMEMUTI", "#ffc04d", "#ffaa00")]
    x = 14
    for label, temp, load, col, bar in cols:
        ws.append(new_widget(T_TEXT, x, 233, 40, 18, text=label, size=10, color=col))
        if temp:
            ws += [new_widget(T_VALUE, x - 6, 249, 52, 30, sensor=temp, size=19, color="#ffffff", sample="50"),
                   new_widget(T_TEXT, x + 44, 255, 24, 18, text="°C", size=10, color=col),
                   new_widget(T_VALUE, x + 56, 253, 30, 22, sensor=load, size=11, color="#ffffff", sample="12"),
                   new_widget(T_TEXT, x + 90, 256, 12, 16, text="%", size=8, color=col)]
        else:
            ws += [new_widget(T_VALUE, x - 6, 249, 52, 30, sensor=load, size=19, color="#ffffff", sample="47"),
                   new_widget(T_TEXT, x + 44, 255, 24, 18, text="%", size=10, color=col)]
        ws += [new_widget(T_TEXT, x, 282, 60, 14, text="charge", size=7, color="#aaaaaa"),
               new_widget(T_BAR, x, 296, 86, 9, sensor=load, fg=bar, bg="#202020", frame="#505050")]
        x += 100
    for label, sensor, col, xx in (("SSD C:", "THDD1", "#c8a0ff", 318), ("Carte m.", "TMOBO", "#ff9e6b", 396)):
        ws += [new_widget(T_TEXT, xx, 233, 70, 18, text=label, size=10, color=col),
               new_widget(T_VALUE, xx - 6, 252, 52, 34, sensor=sensor, size=21, color="#ffffff", sample="38"),
               new_widget(T_TEXT, xx + 46, 260, 24, 18, text="°C", size=10, color=col)]
    return ws


def build(cutout: str | Path, name: str = "Anime - Ma basse", moving_light: bool = True,
          tint: str = "normal", frames_count: int = FRAMES):
    bass = Image.open(cutout).convert("RGBA")
    bass = bass.crop(bass.getbbox())
    k = min(464 / bass.width, 170 / bass.height)
    bass = bass.resize((int(bass.width * k), int(bass.height * k)), Image.Resampling.LANCZOS)
    d = ROOT / "themes" / name
    b = new_theme(d, name)
    p = b.theme.widget_parents[0]
    if moving_light:
        frames = [with_bands(frame(bass, i / frames_count, moving_light, tint)) for i in range(frames_count)]
        p.background_image_path = set_background_frames(d, frames)
        p.image_delay = DELAY
        b.theme.widgets += bass_widgets()
    else:
        # léger : fond fixe + petite zone animée pour les notes (≈4x moins de données à envoyer)
        from core.model import T_IMAGE, new_widget, set_background
        static = with_bands(frame(bass, 0, False, tint, notes=False))
        p.background_image_path = set_background(d, static)
        nf = notes_frames(FRAMES)
        for i, im in enumerate(nf):
            im.save(d / "images" / f"notes_{i:02d}.png")
        x, y, w, h = NOTES_BOX
        wid = new_widget(T_IMAGE, x, y, w, h)
        wid.raw_fields.update(imagePath="./images/notes_00.png", imageDelay=str(DELAY))
        b.theme.widgets += [wid] + bass_widgets()
        frames = []
        for im in nf:
            fr = static.convert("RGBA")
            fr.alpha_composite(im, (x, y))
            frames.append(fr.convert("RGB"))
    save_bundle(b, d / f"{name}.ui")
    bass.save(d / "images" / "basse_detouree.png")
    frames[0].save(d / "apercu.gif", save_all=True, append_images=frames[1:], duration=DELAY, loop=0)
    return d


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[2] == "--all":
        build(sys.argv[1])
        build(sys.argv[1], "Anime - Ma basse (notes)", moving_light=False)
        for c in ("ORANGE", "ROUGE"):
            d = build(sys.argv[1], f"Anime - Ma basse {c}", False, c.lower(), 4)
            dest = ROOT / "themes" / "_variantes" / d.name
            import shutil
            shutil.rmtree(dest, ignore_errors=True)
            shutil.move(str(d), str(dest))
            ui = dest / f"{d.name}.ui"
        print("ok")
    elif len(sys.argv) > 2 and sys.argv[2] == "--alert":
        print(build(sys.argv[1], "Anime - Ma basse ORANGE", False, "orange", 4))
        print(build(sys.argv[1], "Anime - Ma basse ROUGE", False, "rouge", 4))
    elif len(sys.argv) > 2 and sys.argv[2] == "--notes-only":
        print(build(sys.argv[1], "Anime - Ma basse (notes)", moving_light=False))
    else:
        print(build(sys.argv[1]))
