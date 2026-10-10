"""Crée les variantes ORANGE et ROUGE de tous les thèmes (pour le fond selon la température).

Usage : python tools/build_color_variants.py            (crée les variantes manquantes)
        python tools/build_color_variants.py --force    (recrée tout, l'ancien va dans old/themes)

Les variantes vont dans themes/_variantes/<nom> ORANGE et <nom> ROUGE.
Les thèmes d'origine ne sont jamais modifiés.
"""
from __future__ import annotations

import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageOps  # noqa: E402

THEMES = ROOT / "themes"
VARIANTS = THEMES / "_variantes"
COLORS = {"ORANGE": ("#ff8a00", 0.55), "ROUGE": ("#e00000", 0.60)}
BG_RE = re.compile(r"^(bg|background)_", re.I)


def tint(img: Image.Image, color: str, strength: float) -> Image.Image:
    rgb = img.convert("RGB")
    lum = ImageOps.autocontrast(rgb.convert("L"), cutoff=1)
    col = ImageOps.colorize(lum, black="#000000", mid=color, white="#fff2e0", midpoint=110)
    out = Image.blend(rgb, col, strength)
    out = Image.blend(out, Image.new("RGB", rgb.size, color), 0.22)   # même un fond noir prend la couleur
    if img.mode == "RGBA":
        out = out.convert("RGBA")
        out.putalpha(img.getchannel("A"))
    return out


def tint_hex(value: int, color: str, strength: float) -> int:
    px = Image.new("RGB", (1, 1), f"#{value & 0xFFFFFF:06x}")
    r, g, b = tint(px, color, strength).getpixel((0, 0))
    r, g, b = (max(r, 40) if color == "#e00000" else r), g, b
    return (value & 0xFF000000) | (r << 16) | (g << 8) | b


def make_variant(src: Path, color_name: str, force: bool) -> str:
    name = f"{src.name} {color_name}"
    dest = VARIANTS / name
    if dest.exists():
        if not force:
            return "déjà là"
        old = ROOT / "old" / "themes" / f"{name}_{time.strftime('%Y%m%d_%H%M%S')}"
        old.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(dest), str(old))
    ui_src = next(iter(sorted(src.glob("*.ui"))), None)
    if ui_src is None:
        return "pas de .ui"
    color, strength = COLORS[color_name]
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns(".vignette.png", "apercu.gif"))
    (dest / ui_src.name).rename(dest / f"{name}.ui")
    ui = dest / f"{name}.ui"
    imgs = dest / "images"
    tinted = 0
    if imgs.is_dir():
        for f in sorted(imgs.iterdir()):
            if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp") and BG_RE.match(f.name):
                im = Image.open(f)
                im.load()
                out = tint(im, color, strength)
                if f.suffix.lower() in (".jpg", ".jpeg"):
                    out.convert("RGB").save(f, quality=92)
                else:
                    out.save(f)
                tinted += 1
    from core.model import load_bundle, save_bundle
    b = load_bundle(ui)
    if not tinted and b.theme.widget_parents:          # fond uni : on change sa couleur
        p = b.theme.widget_parents[0]
        p.background_color = tint_hex(p.background_color, color, 0.75)
        save_bundle(b, ui)
        b = load_bundle(ui)
    try:                                                # aperçu animé pour la galerie
        from core import preview
        frames = [preview.render(b, t_ms=i * 100) for i in range(8)]
        frames[0].save(dest / "apercu.gif", save_all=True, append_images=frames[1:], duration=100, loop=0)
    except Exception as exc:  # noqa: BLE001
        print("   aperçu non créé :", exc)
    return f"ok ({tinted} image(s) teintée(s))"


def main():
    force = "--force" in sys.argv
    VARIANTS.mkdir(parents=True, exist_ok=True)
    for src in sorted(THEMES.iterdir()):
        if not src.is_dir() or src.name.startswith("_") or "Ma basse" in src.name:   # basse : variantes faites à la main
            continue
        base = re.sub(r"\s*\(.*?\)\s*$", "", src.name).strip()
        for c in COLORS:
            if base != src.name and (VARIANTS / f"{base} {c}").exists():
                print(f"{src.name} {c} : variante « {base} {c} » déjà utilisée")
                continue
            print(f"{src.name} {c} : {make_variant(src, c, force)}", flush=True)


if __name__ == "__main__":
    main()
