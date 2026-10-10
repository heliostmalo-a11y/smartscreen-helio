"""Thèmes animés « légers » : fond fixe + UNE zone animée (comme la basse) → environ 2 fois plus rapide à charger.

* la zone est placée là où ça bouge le plus, sans toucher aux textes / valeurs (sinon ils clignotent) ;
* ses bords sont fondus dans le fond fixe (pas de coupure visible) ;
* même nombre d'images et même vitesse qu'avant.

Usage : python tools/make_zone.py                 (tous les thèmes « Anime - » animés plein écran)
        python tools/make_zone.py "Anime - Vague"
L'ancienne version de chaque thème est rangée dans old/themes/ (rien n'est supprimé).
"""
from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from core.model import T_IMAGE, find_ui, load_bundle, new_widget, save_bundle  # noqa: E402
from core.preview import _frames  # noqa: E402

THEMES = ROOT / "themes"
W, H = 480, 320
ANIM_BYTES = 280_000     # poids de la zone animée (toutes images), ≈ comme les notes de la basse
FEATHER = 10
MIN_SHARE = 0.7        # part minimale du mouvement qui doit tenir dans la zone
ASPECTS = [1.83, 2.6, 3.33, 1.29, 1.0, 5.1, 0.55]          # largeur / hauteur des zones essayées


def _sizes(nframes: int):
    area = ANIM_BYTES / (2 * nframes)
    out = []
    for a in ASPECTS:
        h = int((area / a) ** 0.5) // 4 * 4
        w = min(W, int(area / max(h, 1)) // 4 * 4)
        if h >= 24 and w >= 24:
            out.append((w, min(h, H)))
    return out


def _free_mask(b) -> np.ndarray:
    """True là où il n'y a ni texte ni valeur ni barre."""
    m = np.ones((H, W), bool)
    for w in b.theme.widgets:
        g = w.geometry
        m[max(0, g.y - 2):g.y + g.height + 2, max(0, g.x - 2):g.x + g.width + 2] = False
    return m


def _best_window(motion: np.ndarray, free: np.ndarray, sizes):
    ii = np.pad(motion.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    bad = np.pad((~free).astype(np.int32).cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    best = None
    for bw, bh in sizes:
        for y in range(0, H - bh + 1, 4):
            for x in range(0, W - bw + 1, 4):
                if bad[y + bh, x + bw] - bad[y, x + bw] - bad[y + bh, x] + bad[y, x]:
                    continue
                e = ii[y + bh, x + bw] - ii[y, x + bw] - ii[y + bh, x] + ii[y, x]
                if best is None or e > best[0]:
                    best = (e, x, y, bw, bh)
    return best


def _expand(frames: list[np.ndarray], n: int) -> list[np.ndarray]:
    """Ramène à n images (fondu entre images voisines si besoin), boucle sans à-coup."""
    k = len(frames)
    out = []
    for i in range(n):
        p = i * k / n
        a, t = int(p) % k, p - int(p)
        out.append(frames[a] * (1 - t) + frames[(a + 1) % k] * t)
    return out


def make_zone(theme_dir: Path) -> str:
    ui = find_ui(theme_dir)
    if ui is None:
        return "pas de .ui"
    b = load_bundle(ui)
    p = b.theme.widget_parents[0] if b.theme.widget_parents else None
    if not p or not p.background_image_path:
        return "pas animé"
    files = _frames(theme_dir, p.background_image_path)
    if len(files) < 2:
        return "déjà léger"
    src = [np.asarray(Image.open(f).convert("RGB").resize((W, H))).astype(np.float32) for f in files]
    motion = sum(np.abs(f - src[0]).max(axis=2) for f in src[1:])
    nframes = len(src)
    best = _best_window(motion, _free_mask(b), _sizes(nframes))
    if best is None:
        return "aucune place libre pour une zone animée"
    e, x, y, bw, bh = best
    share = e / max(1.0, float(motion.sum()))
    if share < MIN_SHARE:                 # le mouvement est partout : une zone serait coupée, on laisse tel quel
        return f"laissé plein écran (la zone ne couvrirait que {share:.0%} du mouvement)"
    total_delay = int(getattr(p, "image_delay", 100) or 100) * len(src)
    delay = max(60, total_delay // nframes)

    stamp = int(time.time())
    work = theme_dir.parent / (theme_dir.name + ".__zone")
    if work.exists():
        shutil.move(str(work), str(ROOT / "old" / "themes" / f"{work.name}_{stamp}"))
    skip = {f.name for f in files} | {".vignette.png"}
    shutil.copytree(theme_dir, work, ignore=lambda _d, names: [n for n in names if n in skip])
    imgs = work / "images"

    static = src[0]
    Image.fromarray(static.astype("uint8")).save(imgs / f"bg_{stamp}.jpg", quality=92)
    # bords fondus : au bord de la zone on montre le fond fixe, au centre l'animation
    yy = np.minimum(np.arange(bh), bh - 1 - np.arange(bh))[:, None]
    xx = np.minimum(np.arange(bw), bw - 1 - np.arange(bw))[None, :]
    alpha = np.clip(np.minimum(yy, xx) / FEATHER, 0, 1)[..., None]
    base = static[y:y + bh, x:x + bw]
    for i, fr in enumerate(f[y:y + bh, x:x + bw] for f in src):
        out = base * (1 - alpha) + fr * alpha
        Image.fromarray(np.clip(out, 0, 255).astype("uint8")).save(imgs / f"bg_zone_{stamp}_{i:02d}.jpg", quality=95)

    b2 = load_bundle(work / ui.name)
    p2 = b2.theme.widget_parents[0]
    p2.background_image_path = f"./images/bg_{stamp}.jpg"
    p2.image_delay = 0
    wz = new_widget(T_IMAGE, x, y, bw, bh)
    wz.raw_fields.update(imagePath=f"./images/bg_zone_{stamp}_00.jpg", imageDelay=str(delay))
    b2.theme.widgets = [wz] + list(b2.theme.widgets)
    save_bundle(b2, work / ui.name)
    try:
        from core import preview
        b3 = load_bundle(work / ui.name)
        prev = [preview.render(b3, t_ms=i * delay) for i in range(nframes)]
        prev[0].save(work / "apercu.gif", save_all=True, append_images=prev[1:], duration=delay, loop=0)
    except Exception as exc:  # noqa: BLE001
        print("   aperçu non créé :", exc)

    old = ROOT / "old" / "themes" / f"{theme_dir.name}_{time.strftime('%Y%m%d_%H%M%S')}"
    old.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(theme_dir), str(old))
    shutil.move(str(work), str(theme_dir))
    return f"zone {bw}×{bh} en ({x},{y}), {nframes} images"


def main():
    names = [a for a in sys.argv[1:] if not a.startswith("-")]
    dirs = [THEMES / n for n in names] if names else \
        [d for d in sorted(THEMES.iterdir()) if d.is_dir() and d.name.startswith("Anime - ") and "Ma basse" not in d.name]
    for d in dirs:
        print(f"{d.name} : {make_zone(d)}", flush=True)


if __name__ == "__main__":
    main()
