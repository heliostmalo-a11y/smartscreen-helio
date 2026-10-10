"""Allège les thèmes : les petites zones animées sans transparence passent de PNG à JPG.
Sur l'écran, un PNG coûte 3 octets par pixel (transparence + couleur), un JPG 2 : un tiers de moins à envoyer,
image identique à l'écran. Les PNG transparents (ex. notes de la basse) sont d'abord posés sur le fond fixe.
Les anciens .ui sont copiés dans old/<date>_zones/ ; les PNG restent en place.

Usage : python tools/zones_jpg.py
"""
from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from core.model import T_IMAGE, load_bundle, save_bundle  # noqa: E402
from core.preview import _frames  # noqa: E402


def opaque(path: Path) -> bool:
    im = Image.open(path)
    if im.mode not in ("RGBA", "LA", "P"):
        return True
    a = im.convert("RGBA").getchannel("A")
    return a.getextrema()[0] == 255


def static_background(b, base: Path):
    p = b.theme.widget_parents[0] if b.theme.widget_parents else None
    if not p or not p.background_image_path:
        return None
    files = _frames(base, p.background_image_path)
    if len(files) != 1:
        return None
    return Image.open(files[0]).convert("RGB").resize((480, 320))


def main():
    backup = ROOT / "old" / f"{time.strftime('%Y%m%d_%H%M%S')}_zones"
    n = 0
    for ui in sorted((ROOT / "themes").rglob("*.ui")):
        if "_old" in ui.parts or "_fichiers_mal_ranges" in ui.parts:
            continue
        b = load_bundle(ui)
        changed = False
        for w in b.theme.widgets:
            raw = str(w.raw_fields.get("imagePath", ""))
            if w.widget_type != T_IMAGE or not raw.lower().endswith(".png"):
                continue
            files = _frames(ui.parent, raw)
            if not files:
                continue
            g = w.geometry
            if not all(opaque(f) for f in files):
                bg = static_background(b, ui.parent)
                if bg is None:                      # fond animé : on ne peut pas aplatir
                    continue
                under = bg.crop((g.x, g.y, g.x + g.width, g.y + g.height)).convert("RGBA")
            else:
                under = None
            for f in files:
                im = Image.open(f).convert("RGBA")
                if im.size != (g.width, g.height):
                    im = im.resize((g.width, g.height))
                if under is not None:
                    im = Image.alpha_composite(under, im)
                im.convert("RGB").save(f.with_suffix(".jpg"), quality=95)
            w.raw_fields["imagePath"] = raw[:-4] + ".jpg"
            changed = True
        if changed:
            dest = backup / ui.relative_to(ROOT)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ui, dest)
            save_bundle(b, ui)
            n += 1
            print("allégé :", ui.parent.name)
    print(n, "thème(s) allégé(s)")


if __name__ == "__main__":
    main()
