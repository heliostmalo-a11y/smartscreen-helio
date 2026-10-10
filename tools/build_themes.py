"""Generate the built-in themes shipped with SmartScreen Hélio (run once at build time)."""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.model import (T_BAR, T_DATETIME, T_TEXT, T_VALUE, W, H, new_theme, new_widget,  # noqa: E402
                        save_bundle, set_background)

THEMES = ROOT / "themes"

CPU_T, CPU_U = "TCPUDIO", "SCPUUTI"
GPU_T, GPU_U = "TGPU1", "SGPU1UTI"
RAM_U, RAM_MB = "SMEMUTI", "SUSEDMEM"
NET_D, NET_U = "SNIC1DLRATE", "SNIC1ULRATE"


def gradient(top: str, bottom: str) -> Image.Image:
    a, b = Image.new("RGB", (W, H), top), Image.new("RGB", (W, H), bottom)
    mask = Image.linear_gradient("L").resize((W, H))
    return Image.composite(b, a, mask)


def panels(img: Image.Image, boxes, fill=(255, 255, 255, 18), outline=(120, 200, 255, 90), accent=None):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i, box in enumerate(boxes):
        d.rounded_rectangle(box, radius=12, fill=fill, outline=outline, width=1)
        if accent:
            x0, y0, x1, _ = box
            d.rounded_rectangle((x0 + 12, y0 + 6, x0 + 52, y0 + 9), radius=2, fill=accent[i % len(accent)])
    out = img.convert("RGBA")
    out.alpha_composite(layer)
    return out.convert("RGB")


def theme_sombre():
    d = THEMES / "Helio Sombre"
    bg = gradient("#0b1220", "#05070d")
    boxes = [(8, 8, 236, 152), (244, 8, 472, 152), (8, 160, 236, 312), (244, 160, 472, 312)]
    bg = panels(bg, boxes, accent=[(0, 200, 255, 255), (120, 255, 120, 255), (255, 170, 0, 255), (200, 120, 255, 255)])
    b = new_theme(d, "Helio Sombre")
    b.theme.widget_parents[0].background_image_path = set_background(d, bg)
    ws = b.theme.widgets
    # CPU
    ws += [new_widget(T_TEXT, 20, 16, 80, 22, text="CPU", size=14, color="#7fd8ff"),
           new_widget(T_VALUE, 16, 44, 92, 50, sensor=CPU_T, size=30, color="#ffffff", sample="54"),
           new_widget(T_TEXT, 106, 50, 40, 26, text="°C", size=16, color="#7fd8ff"),
           new_widget(T_VALUE, 160, 48, 52, 34, sensor=CPU_U, size=18, color="#ffffff", sample="12"),
           new_widget(T_TEXT, 212, 52, 20, 26, text="%", size=12, color="#7fd8ff"),
           new_widget(T_BAR, 20, 110, 204, 12, sensor=CPU_U, fg="#00c8ff")]
    # GPU
    ws += [new_widget(T_TEXT, 256, 16, 80, 22, text="GPU", size=14, color="#8dff8d"),
           new_widget(T_VALUE, 252, 44, 92, 50, sensor=GPU_T, size=30, color="#ffffff", sample="48"),
           new_widget(T_TEXT, 342, 50, 40, 26, text="°C", size=16, color="#8dff8d"),
           new_widget(T_VALUE, 396, 48, 52, 34, sensor=GPU_U, size=18, color="#ffffff", sample="5"),
           new_widget(T_TEXT, 448, 52, 20, 26, text="%", size=12, color="#8dff8d"),
           new_widget(T_BAR, 256, 110, 204, 12, sensor=GPU_U, fg="#58e858")]
    # RAM
    ws += [new_widget(T_TEXT, 20, 168, 80, 22, text="RAM", size=14, color="#ffc04d"),
           new_widget(T_VALUE, 16, 196, 76, 50, sensor=RAM_U, size=30, color="#ffffff", sample="47"),
           new_widget(T_TEXT, 92, 202, 30, 26, text="%", size=16, color="#ffc04d"),
           new_widget(T_VALUE, 132, 204, 70, 30, sensor=RAM_MB, size=14, color="#cccccc", sample="11313"),
           new_widget(T_TEXT, 202, 206, 30, 22, text="Mo", size=10, color="#ffc04d"),
           new_widget(T_BAR, 20, 262, 204, 12, sensor=RAM_U, fg="#ffaa00")]
    # Time / network
    ws += [new_widget(T_DATETIME, 256, 170, 204, 44, format="hh:nn:ss", size=26, color="#ffffff"),
           new_widget(T_DATETIME, 256, 214, 204, 30, format="yyyy-mm-dd", size=14, color="#c8a0ff"),
           new_widget(T_TEXT, 258, 258, 30, 20, text="↓", size=12, color="#c8a0ff"),
           new_widget(T_VALUE, 274, 256, 60, 24, sensor=NET_D, size=12, color="#ffffff", sample="80"),
           new_widget(T_TEXT, 258, 282, 30, 20, text="↑", size=12, color="#c8a0ff"),
           new_widget(T_VALUE, 274, 280, 60, 24, sensor=NET_U, size=12, color="#ffffff", sample="12"),
           new_widget(T_TEXT, 338, 270, 60, 20, text="Ko/s", size=10, color="#c8a0ff")]
    return save_bundle(b, d / "Helio Sombre.ui")


def theme_minimal():
    d = THEMES / "Helio Minimal"
    bg = Image.new("RGB", (W, H), "#000000")
    dr = ImageDraw.Draw(bg)
    dr.line((240, 30, 240, 210), fill="#222222", width=2)
    dr.line((30, 230, 450, 230), fill="#222222", width=2)
    b = new_theme(d, "Helio Minimal")
    b.theme.widget_parents[0].background_image_path = set_background(d, bg)
    b.theme.widgets += [
        new_widget(T_TEXT, 30, 30, 120, 26, text="CPU °C", size=14, color="#888888"),
        new_widget(T_VALUE, 20, 70, 200, 110, sensor=CPU_T, size=60, color="#ffffff", align=1, sample="54"),
        new_widget(T_TEXT, 270, 30, 120, 26, text="GPU °C", size=14, color="#888888"),
        new_widget(T_VALUE, 260, 70, 200, 110, sensor=GPU_T, size=60, color="#ffffff", align=1, sample="48"),
        new_widget(T_DATETIME, 20, 248, 220, 50, format="hh:nn:ss", size=28, color="#ffffff"),
        new_widget(T_TEXT, 270, 252, 60, 24, text="CPU", size=12, color="#888888"),
        new_widget(T_VALUE, 330, 248, 60, 30, sensor=CPU_U, size=16, color="#ffffff", sample="12"),
        new_widget(T_TEXT, 392, 252, 20, 24, text="%", size=12, color="#888888"),
        new_widget(T_TEXT, 270, 280, 60, 24, text="RAM", size=12, color="#888888"),
        new_widget(T_VALUE, 330, 276, 60, 30, sensor=RAM_U, size=16, color="#ffffff", sample="47"),
        new_widget(T_TEXT, 392, 280, 20, 24, text="%", size=12, color="#888888"),
    ]
    return save_bundle(b, d / "Helio Minimal.ui")


def theme_ocean():
    d = THEMES / "Helio Ocean"
    bg = gradient("#00334d", "#001018").filter(ImageFilter.GaussianBlur(1))
    dr = ImageDraw.Draw(bg)
    for i in range(0, W, 24):
        dr.line((i, 300, i + 12, 300), fill="#0a5a7a", width=2)
    b = new_theme(d, "Helio Ocean")
    b.theme.widget_parents[0].background_image_path = set_background(d, bg)
    rows = [("CPU", CPU_T, "°C", CPU_U, "#4fd1ff"), ("GPU", GPU_T, "°C", GPU_U, "#7cffb2"),
            ("RAM", None, "", RAM_U, "#ffd36b")]
    y = 20
    for label, temp, unit, usage, col in rows:
        b.theme.widgets += [new_widget(T_TEXT, 20, y + 6, 70, 26, text=label, size=16, color=col)]
        if temp:
            b.theme.widgets += [new_widget(T_VALUE, 90, y, 70, 40, sensor=temp, size=24, color="#ffffff",
                                           sample="50"),
                                new_widget(T_TEXT, 162, y + 6, 30, 26, text=unit, size=12, color=col)]
        b.theme.widgets += [new_widget(T_BAR, 200, y + 12, 200, 16, sensor=usage, fg=col, bg="#0d2633",
                                       frame="#1d4a5e"),
                            new_widget(T_VALUE, 404, y + 4, 50, 30, sensor=usage, size=16, color="#ffffff",
                                       sample="25"),
                            new_widget(T_TEXT, 456, y + 8, 20, 24, text="%", size=11, color=col)]
        y += 70
    b.theme.widgets += [new_widget(T_DATETIME, 20, 236, 200, 50, format="hh:nn:ss", size=28, color="#ffffff"),
                        new_widget(T_DATETIME, 260, 248, 200, 30, format="yyyy-mm-dd", size=16, color="#4fd1ff")]
    return save_bundle(b, d / "Helio Ocean.ui")


if __name__ == "__main__":
    for fn in (theme_sombre, theme_minimal, theme_ocean):
        print("built", fn())
