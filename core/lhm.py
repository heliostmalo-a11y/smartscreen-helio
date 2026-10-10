"""Read sensors from LibreHardwareMonitor's built-in web server (Options > Remote Web Server > Run).

Values are exposed with AIDA64-style ids (TCPUDIO, SCPUUTI, TGPU1, SGPU1UTI, SMEMUTI…)
so every existing theme keeps working, plus one "LHM:<path>" entry per sensor.
"""
from __future__ import annotations

import json
import re
import urllib.request

from .aida64 import Sensor

URL = "http://127.0.0.1:{port}/data.json"

_KIND = {"temperatures": "temp", "load": "sys", "clocks": "sys", "fans": "fan", "voltages": "volt",
         "powers": "pwr", "data": "sys", "smalldata": "sys", "controls": "duty", "throughput": "sys"}


def _num(text: str) -> float | None:
    text = re.sub(r"(?<=\d)[\s\u00a0\u202f](?=\d)", "", text or "")
    m = re.search(r"-?\d+(?:[.,]\d+)?", text)
    return float(m.group(0).replace(",", ".")) if m else None


def _hw_type(node: dict) -> str:
    img = (node.get("ImageURL") or "").lower()
    sid = (node.get("SensorId") or "").lower()
    text = (node.get("Text") or "").lower()
    if "virtual" in text or sid.startswith("/vram"):
        return "other"              # mémoire virtuelle (fichier d'échange) : pas la RAM réelle
    if "cpu" in img or sid.startswith(("/amdcpu", "/intelcpu")):
        return "cpu"
    if any(k in img for k in ("nvidia", "ati", "amd", "intel", "gpu")) or sid.startswith("/gpu"):
        return "gpu"
    if "ram" in img or sid.startswith(("/ram", "/memory")) or text in ("generic memory", "total memory"):
        return "ram"
    if "mainboard" in img or "board" in img:
        return "mobo"
    if any(k in text for k in ("ssd", "nvme", "crucial", "samsung", "t705", "wd ", "kingston", "sabrent")):
        return "disk"
    if "hdd" in img or "ssd" in img or "nvme" in img or sid.startswith(("/nvme", "/hdd", "/ssd", "/ata", "/storage")):
        return "disk"
    return "other"


def _app_dir():
    from .settings import APP_DIR
    return APP_DIR


def _preferred_disk() -> str:
    """Disk to show as 'SSD C:' : text of SmartScreen/ssd.txt (e.g. T705), else the first disk."""
    try:
        from pathlib import Path
        return (_app_dir() / "ssd.txt").read_text(encoding="utf-8").strip().lower()
    except Exception:
        return ""


def parse(tree: dict) -> dict[str, Sensor]:
    out: dict[str, Sensor] = {}
    best: dict[str, tuple[int, float, str]] = {}

    def offer(alias: str, prio: int, value: float, label: str):
        if alias not in best or prio < best[alias][0]:
            best[alias] = (prio, value, label)

    def walk(node: dict, hw: str, hw_name: str, cat: str, path: str):
        children = node.get("Children") or []
        text = node.get("Text") or ""
        if node.get("ImageURL") and children and _hw_type(node) != "other":
            hw, hw_name = _hw_type(node), text
        if children:
            low = text.lower()
            new_cat = low if low in _KIND else cat
            for i, ch in enumerate(children):
                walk(ch, hw, hw_name, new_cat, f"{path}/{i}")
            return
        value = _num(node.get("Value", ""))
        if value is None or not cat:
            return
        kind = _KIND.get(cat, "sys")
        prefix = {"cpu": "CPU ", "gpu": "GPU ", "ram": "RAM ", "disk": "SSD "}.get(hw, "")
        label = f"{prefix}{text}".strip()
        sid = "LHM:" + (node.get("SensorId") or path)
        out[sid] = Sensor(sid, label, kind, node.get("Value", ""))
        t = text.lower()
        if hw == "cpu" and cat == "temperatures" and "ccd" in t and ("1" in t.split("ccd", 1)[1][:3]):
            offer("TCCD1", 0 if "tdie" in t else 1, value, label)
        if hw == "cpu" and cat == "temperatures":
            prio = 0 if any(k in t for k in ("tctl", "tdie", "package")) else 1 if "core" in t or "ccd" in t else 2
            offer("TCPUDIO", prio, value, label)
            offer("TCPUPKG", prio, value, label)
        elif hw == "cpu" and cat == "load" and "total" in t:
            offer("SCPUUTI", 0, value, label)
        elif hw == "cpu" and cat == "clocks" and "core" in t:
            offer("SCPUCLK", 0 if "#1" in t else 1, value, label)
        elif hw == "gpu" and cat == "temperatures":
            if "hot" in t:
                offer("TGPU1HOT", 0, value, label)
            else:
                offer("TGPU1", 0 if "core" in t else 1, value, label)
        elif hw == "gpu" and cat == "load":
            if "core" in t or t in ("gpu", "d3d 3d"):
                offer("SGPU1UTI", 0 if "core" in t else 1, value, label)
            elif "memory" in t:
                offer("SGPU1MEMUTI", 0, value, label)
        elif hw == "gpu" and cat == "clocks" and "core" in t:
            offer("SGPU1CLK", 0, value, label)
        elif hw == "ram" and cat == "load" and t in ("memory", "physical memory"):
            offer("SMEMUTI", 0, value, label)
        elif hw == "ram" and cat == "data" and "used" in t and "virtual" not in t:
            offer("SUSEDMEM", 0, value * 1024, label)
        elif hw == "ram" and cat == "data" and "available" in t and "virtual" not in t:
            offer("SFREEMEM", 0, value * 1024, label)
        elif hw == "disk" and cat == "temperatures" and "warning" not in t and "critical" not in t:
            main = t in ("temperature", "composite temperature", "temperature 1", "temperature #1")
            pref = _preferred_disk()
            prio = (0 if pref and pref in hw_name.lower() else 10) + (0 if main else 1)
            offer("THDD1", prio, value, f"SSD {hw_name}")
        elif hw == "mobo" and cat == "temperatures" and 5 < value < 110:
            offer("TMOBO", 0 if any(k in t for k in ("motherboard", "system", "mainboard")) else
                  2 if "cpu" in t else 1, value, label)

    walk(tree, "other", "", "", "")
    for alias, (_p, value, label) in best.items():
        kind = "temp" if alias.startswith("T") else "sys"
        out[alias] = Sensor(alias, label, kind, f"{value:.1f}")
    return out


_LAST: tuple[float, dict] | None = None


def read_sensors(port: int = 8085, timeout: float = 2.5) -> dict[str, Sensor]:
    """Lit LibreHardwareMonitor. Sous forte charge (OCCT, Prime95…) son serveur web répond lentement :
    délai plus long, et en cas d'échec on garde la dernière lecture pendant 20 s."""
    global _LAST
    import time
    try:
        req = urllib.request.Request(URL.format(port=port), headers={"User-Agent": "SmartScreenHelio"})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # never use a proxy for localhost
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        _dump_once(raw)
        data = parse(json.loads(raw))
        if data:
            _LAST = (time.monotonic(), data)
        return data
    except Exception:
        if _LAST and time.monotonic() - _LAST[0] < 20:
            return _LAST[1]
        raise


_DUMPED = False


def _dump_once(raw: str):
    """Keep a copy of the sensor tree next to the app (diagnostics)."""
    global _DUMPED
    if _DUMPED:
        return
    _DUMPED = True
    try:
        from pathlib import Path
        (_app_dir() / "lhm_capteurs.json").write_text(raw, encoding="utf-8")
    except Exception:
        pass
