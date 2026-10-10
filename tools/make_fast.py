"""Rend les thèmes animés plus rapides à charger sur le SmartMonitor.

Au lieu d'envoyer 8 fonds complets (≈2,4 Mo, plus d'une minute), on garde UN fond fixe
et seules les zones qui bougent sont animées (petites images). Si presque tout l'écran
bouge (ex. Lignes de vitesse), on garde l'animation plein écran mais avec 4 images au lieu de 8.

Usage : python tools/make_fast.py               (tous les thèmes animés de themes/)
        python tools/make_fast.py "Anime - Vague"
L'ancienne version de chaque thème est déplacée dans old/themes/ (rien n'est supprimé).
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
TILE = 16
MAX_BOXES = 12
BYTES_PX = 3.3                          # coût mesuré d'un pixel d'image animée dans img.dat
FULL_FRAMES = 4


def _boxes(mask: np.ndarray) -> list[list[int]]:
    """Rectangles (x0, y0, x1, y1) couvrant les tuiles qui bougent, fusionnés jusqu'à MAX_BOXES."""
    th, tw = mask.shape[0] // TILE, mask.shape[1] // TILE
    tiles = mask[:th * TILE, :tw * TILE].reshape(th, TILE, tw, TILE).mean(axis=(1, 3)) > 0.01
    boxes = [[x * TILE, y * TILE, (x + 1) * TILE, (y + 1) * TILE] for y, x in zip(*np.where(tiles))]

    def area(b):
        return (b[2] - b[0]) * (b[3] - b[1])

    def union(a, b):
        return [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]

    def touch(a, b, gap=TILE):
        return not (a[2] + gap <= b[0] or b[2] + gap <= a[0] or a[3] + gap <= b[1] or b[3] + gap <= a[1])

    merged = True
    while merged:                                   # fusionne les rectangles voisins
        merged = False
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                if touch(boxes[i], boxes[j]):
                    boxes[i] = union(boxes[i], boxes[j])
                    del boxes[j]
                    merged = True
                    break
            if merged:
                break
    while len(boxes) > MAX_BOXES:                   # trop de zones : fusionne celles qui coûtent le moins
        best = None
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                cost = area(union(boxes[i], boxes[j])) - area(boxes[i]) - area(boxes[j])
                if best is None or cost < best[0]:
                    best = (cost, i, j)
        _, i, j = best
        boxes[i] = union(boxes[i], boxes[j])
        del boxes[j]
    return boxes


def make_fast(theme_dir: Path, dest_root: Path | None = None) -> str:
    ui = find_ui(theme_dir)
    if ui is None:
        return "pas de .ui"
    b = load_bundle(ui)
    p = b.theme.widget_parents[0] if b.theme.widget_parents else None
    if not p or not p.background_image_path:
        return "pas animé"
    files = _frames(theme_dir, p.background_image_path)
    if len(files) < 2:
        return "pas animé"
    frames = [Image.open(f).convert("RGB").resize((480, 320)) for f in files]
    arr = [np.asarray(f).astype(np.int16) for f in frames]
    mask = np.zeros(arr[0].shape[:2], bool)
    for a in arr[1:]:
        mask |= np.abs(a - arr[0]).max(axis=2) > 24
    delay = int(getattr(p, "image_delay", 100) or 100)

    # nouvelle version écrite à côté, puis échange avec l'ancienne (qui part dans old/themes)
    work = (dest_root or theme_dir.parent) / (theme_dir.name + ".__rapide")
    if work.exists():                               # reste d'un essai précédent -> old/themes (pas de suppression)
        trash = ROOT / "old" / "themes" / f"{work.name}_{time.strftime('%Y%m%d_%H%M%S')}"
        trash.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(work), str(trash))
    skip = {f.name for f in files} | {".vignette.png"}
    shutil.copytree(theme_dir, work, ignore=lambda _d, names: [n for n in names if n in skip])
    imgs = work / "images"
    stamp = int(time.time())

    boxes = _boxes(mask)
    anim_px = sum((x1 - x0) * (y1 - y0) for x0, y0, x1, y1 in boxes)
    b2 = load_bundle(work / ui.name)
    p2 = b2.theme.widget_parents[0]
    zones_cost = 480 * 320 * 2 + anim_px * len(frames) * BYTES_PX
    full_cost = 480 * 320 * 2 * FULL_FRAMES
    if zones_cost < full_cost * 0.85:
        frames[0].save(imgs / f"bg_{stamp}.jpg", quality=92)
        p2.background_image_path = f"./images/bg_{stamp}.jpg"
        p2.image_delay = 0
        new = []
        for k, (x0, y0, x1, y1) in enumerate(boxes):
            for i, fr in enumerate(frames):
                fr.crop((x0, y0, x1, y1)).save(imgs / f"bg_zone{k}_{stamp}_{i:02d}.png")
            w = new_widget(T_IMAGE, x0, y0, x1 - x0, y1 - y0)
            w.raw_fields.update(imagePath=f"./images/bg_zone{k}_{stamp}_00.png", imageDelay=str(delay))
            new.append(w)
        b2.theme.widgets = new + list(b2.theme.widgets)      # sous les textes et valeurs
        how = f"{len(boxes)} zone(s) animée(s), {anim_px * 100 // (480 * 320)} % de l'écran"
    else:
        step = max(1, len(frames) // FULL_FRAMES)
        keep = frames[::step][:FULL_FRAMES]
        for i, fr in enumerate(keep):
            fr.save(imgs / f"bg_{stamp}_{i:02d}.jpg", quality=92)
        p2.background_image_path = f"./images/bg_{stamp}_00.jpg"
        p2.image_delay = delay * step
        how = f"plein écran, {len(keep)} images au lieu de {len(frames)}"
    save_bundle(b2, work / ui.name)

    try:                                            # aperçu galerie
        from core import preview
        b3 = load_bundle(work / ui.name)
        prev = [preview.render(b3, t_ms=i * delay) for i in range(8)]
        prev[0].save(work / "apercu.gif", save_all=True, append_images=prev[1:], duration=delay, loop=0)
    except Exception as exc:  # noqa: BLE001
        print("   aperçu non créé :", exc)

    old = ROOT / "old" / "themes" / f"{theme_dir.name}_{time.strftime('%Y%m%d_%H%M%S')}"
    old.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(theme_dir), str(old))
    shutil.move(str(work), str(theme_dir))
    return how


def main():
    names = [a for a in sys.argv[1:] if not a.startswith("-")]
    dirs = [THEMES / n for n in names] if names else \
        [d for d in sorted(THEMES.iterdir()) if d.is_dir() and not d.name.startswith("_")]
    for d in dirs:
        if "Ma basse" in d.name:          # déjà optimisée à la main
            continue
        print(f"{d.name} : {make_fast(d)}", flush=True)


if __name__ == "__main__":
    main()
