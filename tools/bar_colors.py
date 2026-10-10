"""Barres de charge plus visibles : fond = couleur de la barre assombrie, cadre = couleur de la barre,
remplissage plus vif, barre un peu plus haute. Les anciens .ui sont copiés dans old/<date>/ avant modification.

Usage : python tools/bar_colors.py
"""
from __future__ import annotations

import colorsys
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.model import T_BAR, load_bundle, save_bundle  # noqa: E402


def _rgb(v: int):
    return (v >> 16) & 255, (v >> 8) & 255, v & 255


def _int(rgb, alpha=0xFF) -> int:
    r, g, b = (max(0, min(255, int(c))) for c in rgb)
    return (alpha << 24) | (r << 16) | (g << 8) | b


def _vivid(rgb):
    h, l, s = colorsys.rgb_to_hls(*(c / 255 for c in rgb))
    if s < 0.15:                       # barre grise -> bleu vif
        h, s = 0.55, 1.0
    r, g, b = colorsys.hls_to_rgb(h, 0.55, max(s, 0.9))
    return r * 255, g * 255, b * 255


def main():
    backup = ROOT / "old" / f"{time.strftime('%Y%m%d_%H%M%S')}_barres"
    n = 0
    for ui in sorted((ROOT / "themes").rglob("*.ui")):
        if "_old" in ui.parts or "_fichiers_mal_ranges" in ui.parts:
            continue
        b = load_bundle(ui)
        bars = [w for w in b.theme.widgets if w.widget_type == T_BAR and w.style]
        if not bars:
            continue
        dest = backup / ui.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ui, dest)
        for w in bars:
            st = w.style
            fg = _vivid(_rgb(st.fg_color))
            st.fg_color = _int(fg)
            st.bg_color = _int((8, 8, 8))     # fond noir, mais pas 000000 pur (barres disparues sur l'écran avec 000000 + 12 px)
            st.frame_color = _int([min(255, c * 1.15 + 30) for c in fg])
            st.fg_color_raw = f"{st.fg_color:08x}"
            st.bg_color_raw = f"{st.bg_color:08x}"
            st.frame_color_raw = f"{st.frame_color:08x}"
            if w.geometry.height == 12:      # retour à la hauteur d'origine qui s'affichait bien
                w.geometry.height = 9
        save_bundle(b, ui)
        n += 1
        print("barres :", ui.parent.name)
    print(n, "thème(s) modifié(s) — anciens fichiers dans", backup.relative_to(ROOT))


if __name__ == "__main__":
    main()
