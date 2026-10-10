"""Passe toutes les dates des thèmes au format français jour-mois-année (dd-mm-yyyy)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.smartmonitor.ui import decode_ui_file, encode_ui_file

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "themes"
n = 0
for ui in root.rglob("*.ui"):
    if "_old" in ui.parts:
        continue
    xml = decode_ui_file(ui).decode("utf-8")
    new = xml.replace(">yyyy-mm-dd<", ">dd-mm-yyyy<").replace(">2026-01-01<", ">01-01-2026<").replace(">2022-01-01<", ">01-01-2022<")
    if new != xml:
        encode_ui_file(ui, new)
        n += 1
        print("date FR :", ui.parent.name)
print(n, "thème(s) modifié(s)")
