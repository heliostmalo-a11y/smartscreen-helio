"""Resolve theme sensor fields into live values (AIDA64 first, psutil as fallback)."""
from __future__ import annotations

import re
import shutil
import time
from dataclasses import dataclass

from . import aida64

try:
    import psutil
except Exception:  # pragma: no cover
    psutil = None

AIDA_TYPE = "AIDA64"   # value stored in <sensorTypeName> for our own themes

# Friendly presets shown in the editor (id -> label). Real list comes from AIDA64.
PRESETS: list[tuple[str, str]] = [
    ("TCPUPKG", "Température CPU (package)"),
    ("TCPUDIO", "Température CPU (diode)"),
    ("TCPU", "Température CPU"),
    ("SCPUUTI", "Utilisation CPU %"),
    ("SCPUCLK", "Fréquence CPU MHz"),
    ("FCPU", "Ventilateur CPU tr/min"),
    ("TGPU1", "Température GPU"),
    ("TGPU1HOT", "Point chaud GPU"),
    ("SGPU1UTI", "Utilisation GPU %"),
    ("SGPU1CLK", "Fréquence GPU MHz"),
    ("SGPU1USEDDEMEM", "Mémoire GPU utilisée Mo"),
    ("SMEMUTI", "Utilisation RAM %"),
    ("SUSEDMEM", "RAM utilisée Mo"),
    ("SFREEMEM", "RAM libre Mo"),
    ("TMOBO", "Température carte mère"),
    ("SNIC1DLRATE", "Réseau réception Ko/s"),
    ("SNIC1ULRATE", "Réseau envoi Ko/s"),
    ("SDSK1ACT", "Activité disque 1 %"),
    ("PSU:C", "Disque C: utilisé %"),
]

# Metric names used by vendor themes -> AIDA64 candidates (first available wins)
METRIC_TO_AIDA: dict[str, list[str]] = {
    "CPU_TEMP": ["TCPUPKG", "TCPUDIO", "TCPU", "TCC-1-1"],
    "CPU_PERCENT": ["SCPUUTI"],
    "CPU_FREQ_MHZ": ["SCPUCLK", "SCC-1-1"],
    "CPU_FAN": ["FCPU"],
    "GPU_TEMP": ["TGPU1", "TGPU1HOT"],
    "GPU_PERCENT": ["SGPU1UTI"],
    "GPU_MEM_PERCENT": ["SVMEMUSAGE", "SGPU1MEMUTI"],
    "GPU_MEM_USED_MB": ["SGPU1USEDDEMEM", "SUSEDVMEM"],
    "GPU_FREQ_MHZ": ["SGPU1CLK"],
    "RAM_PERCENT": ["SMEMUTI"],
    "RAM_USED_GB": ["SUSEDMEM"],
    "RAM_FREE_GB": ["SFREEMEM"],
    "DISK_PERCENT": ["SDSK1ACT"],
    "NET_UP_KBPS": ["SNIC1ULRATE"],
    "NET_DOWN_KBPS": ["SNIC1DLRATE"],
}

# AIDA64 id -> metric (used for the Windows fallback when AIDA64 does not share the id)
AIDA_TO_METRIC: dict[str, str] = {aid: metric for metric, ids in METRIC_TO_AIDA.items() for aid in ids}

# label regex fallbacks when the id is not shared by AIDA64
METRIC_LABEL_RE: dict[str, str] = {
    "CPU_TEMP": r"^(CPU|Processeur)",
    "GPU_TEMP": r"^GPU",
    "CPU_PERCENT": r"CPU.*(Utili|Usage)",
    "GPU_PERCENT": r"GPU.*(Utili|Usage)",
    "RAM_PERCENT": r"(Mémoire|Memory).*(Utili|Usage)",
}


def derive_metric(type_name: str, sensor_name: str, reading: str) -> str | None:
    """Same heuristics as the vendor-theme mapping of the HIDdev2 fork."""
    t, s, r = (type_name or "").lower(), (sensor_name or "").lower(), (reading or "").lower()
    if t == "temperature" and "cpu" in r:
        return "CPU_TEMP"
    if t == "temperature" and ("gpu" in r or "graphics" in r):
        return "GPU_TEMP"
    if t == "usage" and "cpu" in r:
        return "CPU_PERCENT"
    if t == "usage" and "gpu memory" in r:
        return "GPU_MEM_PERCENT"
    if t == "usage" and "gpu" in r:
        return "GPU_PERCENT"
    if t == "other" and "physical memory load" in r:
        return "RAM_PERCENT"
    if t == "other" and "physical memory used" in r:
        return "RAM_USED_GB"
    if t == "other" and "physical memory free" in r:
        return "RAM_FREE_GB"
    if t == "other" and "disk load" in r:
        return "DISK_PERCENT"
    if t == "other" and "disk used" in r:
        return "DISK_USED_GB"
    if t == "other" and "disk free" in r:
        return "DISK_FREE_GB"
    if t == "other" and "disk total" in r:
        return "DISK_TOTAL_GB"
    if t == "other" and "gpu memory used" in r:
        return "GPU_MEM_USED_MB"
    if t == "fan" and "cpu" in r:
        return "CPU_FAN"
    if t == "frequency" and "core clock" in r and "gpu" in s:
        return "GPU_FREQ_MHZ"
    if t == "frequency" and "core clock" in r:
        return "CPU_FREQ_MHZ"
    if "network:" in s and "up rate" in r:
        return "NET_UP_KBPS"
    if "network:" in s and "dl rate" in r:
        return "NET_DOWN_KBPS"
    return None


@dataclass
class Binding:
    tag: int
    aida_id: str | None = None      # explicit AIDA64 id
    metric: str | None = None       # vendor-theme metric name
    scale: float = 1.0


class ValueSource:
    """Collects values once per tick from AIDA64 (+ psutil fallback)."""

    def __init__(self):
        self._net_prev: tuple[float, int, int] | None = None
        self.last_error: str = ""
        self.aida_ok = False

    def snapshot(self) -> dict[str, aida64.Sensor]:
        try:
            data = aida64.read_sensors()
            self.aida_ok = bool(data)
            self.last_error = "" if data else "AIDA64 ne partage aucun capteur."
            return data
        except Exception as exc:  # noqa: BLE001
            self.aida_ok = False
            self.last_error = str(exc)
            return {}

    # ---------------------------------------------------------------- psutil
    def _net_rates(self) -> tuple[float, float]:
        if psutil is None:
            return 0.0, 0.0
        c = psutil.net_io_counters()
        now = time.monotonic()
        prev, self._net_prev = self._net_prev, (now, c.bytes_sent, c.bytes_recv)
        if not prev:
            return 0.0, 0.0
        dt = max(0.1, now - prev[0])
        return (c.bytes_sent - prev[1]) / 1024 / dt, (c.bytes_recv - prev[2]) / 1024 / dt

    def _fallback(self, metric: str | None) -> float | None:
        if psutil is None or not metric:
            return None
        if metric == "CPU_PERCENT":
            return psutil.cpu_percent()
        if metric == "RAM_PERCENT":
            return psutil.virtual_memory().percent
        if metric == "RAM_USED_GB":
            return psutil.virtual_memory().used / 1024 ** 2
        if metric == "RAM_FREE_GB":
            return psutil.virtual_memory().available / 1024 ** 2
        if metric in ("NET_UP_KBPS", "NET_DOWN_KBPS"):
            up, down = self._net_rates()
            return up if metric == "NET_UP_KBPS" else down
        if metric in ("DISK_USED_GB", "DISK_FREE_GB", "DISK_TOTAL_GB"):
            u = shutil.disk_usage("C:\\" if psutil.WINDOWS else "/")
            return {"DISK_USED_GB": u.used, "DISK_FREE_GB": u.free, "DISK_TOTAL_GB": u.total}[metric] / 1024 ** 3
        if metric == "CPU_FREQ_MHZ":
            f = psutil.cpu_freq()
            return f.current if f else None
        return None

    def value(self, binding: Binding, data: dict[str, aida64.Sensor]) -> float | None:
        aida_id = binding.aida_id
        if aida_id and aida_id.startswith("PSU:"):
            drive = aida_id[4:] + "\\"
            try:
                u = shutil.disk_usage(drive)
                return u.used * 100 / u.total
            except Exception:
                return None
        if aida_id:
            s = data.get(aida_id)
            if s and s.number is not None:
                return s.number
            # AIDA64 does not share this id: use the Windows value instead
            return self._fallback(AIDA_TO_METRIC.get(aida_id))
        if binding.metric:
            for cand in METRIC_TO_AIDA.get(binding.metric, []):
                s = data.get(cand)
                if s and s.number is not None:
                    return s.number
            pattern = METRIC_LABEL_RE.get(binding.metric)
            if pattern:
                kind = "temp" if binding.metric.endswith("_TEMP") else "sys"
                for s in data.values():
                    if s.kind == kind and re.search(pattern, s.label, re.I) and s.number is not None:
                        return s.number
            return self._fallback(binding.metric)
        return None


def bindings_for_theme(theme) -> list[Binding]:
    """Build one binding per distinct sensor tag of a parsed SmartMonitorTheme."""
    out: dict[int, Binding] = {}
    for w in theme.widgets:
        sp = w.sensor
        if sp is None or sp.fast_sensor is None or sp.fast_sensor < 0 or sp.fast_sensor in out:
            continue
        if (sp.sensor_type_name or "") == AIDA_TYPE:
            out[sp.fast_sensor] = Binding(sp.fast_sensor, aida_id=sp.reading_name or None)
        else:
            out[sp.fast_sensor] = Binding(sp.fast_sensor,
                                          metric=derive_metric(sp.sensor_type_name, sp.sensor_name,
                                                               sp.reading_name))
    return list(out.values())
