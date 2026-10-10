"""Crée un thème à partir d'une photo (bandeau noir horloge/date en haut, CPU/GPU/RAM/SSD/carte mère en bas).

Usage : python tools/build_photo_theme.py photo.jpg "Photo - Coucher de soleil" [x y largeur]
        x, y, largeur : zone à garder, en fraction de la photo (0 à 1), format 3:2 conservé.
La photo d'origine n'est pas modifiée.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from PIL import Image, ImageEnhance  # noqa: E402

from build_bass_photo import bass_widgets, with_bands  # noqa: E402
from core.model import H, W, new_theme, save_bundle, set_background  # noqa: E402


def horizon_glow(d: Path, bg: Image.Image, y0: int, y1: int, frames: int = 6, delay: int = 180):
    """Petite bande animée : la lueur rouge de l'horizon « respire » et une lumière glisse de gauche à droite.
    Seule cette bande est animée (envoi rapide)."""
    import numpy as np
    from core.model import T_IMAGE, new_widget
    band = np.asarray(bg.crop((0, y0, W, y1))).astype(float)
    red = np.clip((band[..., 0] - band[..., 2]) / 80.0, 0, 1)            # où il y a du rouge
    h = y1 - y0
    vy = np.clip(np.minimum(np.arange(h), h - 1 - np.arange(h)) / 6.0, 0, 1)[:, None]   # bords fondus
    xs = np.arange(W)[None, :] / W
    for i in range(frames):
        ph = i / frames
        sweep = 0.5 + 0.5 * np.cos(2 * np.pi * (xs - ph))
        breath = 0.6 + 0.4 * np.sin(2 * np.pi * ph)
        f = 1 + 0.55 * red * sweep * breath * vy
        out = band * f[..., None]
        out[..., 1] += 18 * red * sweep * breath * vy                        # un peu plus doré
        Image.fromarray(np.clip(out, 0, 255).astype("uint8")).save(d / "images" / f"bg_glow_{i:02d}.png")
    w = new_widget(T_IMAGE, 0, y0, W, h)
    w.raw_fields.update(imagePath="./images/bg_glow_00.png", imageDelay=str(delay))
    return [w]


def build(photo: str, name: str, x: float = 0.0, y: float = 0.0, width: float = 1.0,
          glow: tuple[int, int] | None = (186, 224)) -> Path:
    src = Image.open(photo).convert("RGB")
    cw = int(src.width * width)
    ch = int(cw * H / W)
    x0, y0 = int(src.width * x), int(src.height * y)
    x0, y0 = max(0, min(x0, src.width - cw)), max(0, min(y0, src.height - ch))
    img = src.crop((x0, y0, x0 + cw, y0 + ch)).resize((W, H), Image.Resampling.LANCZOS)
    img = ImageEnhance.Brightness(img).enhance(1.12)
    img = ImageEnhance.Color(img).enhance(1.15)
    d = ROOT / "themes" / name
    b = new_theme(d, name)
    b.theme.widget_parents[0].background_image_path = set_background(d, with_bands(img))
    if glow:
        b.theme.widgets += horizon_glow(d, with_bands(img), *glow)
    b.theme.widgets += bass_widgets()
    ui = save_bundle(b, d / f"{name}.ui")
    from core import preview
    prev = [preview.render(b, t_ms=i * 180) for i in range(6)]
    prev[0].save(d / "apercu.gif", save_all=True, append_images=prev[1:], duration=180, loop=0)
    return ui


if __name__ == "__main__":
    args = sys.argv[1:]
    nums = [float(a) for a in args[2:5]]
    print(build(args[0], args[1], *nums))
