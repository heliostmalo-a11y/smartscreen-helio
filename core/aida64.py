"""Read AIDA64 sensor values from its shared memory.

AIDA64 > Préférences > Surveillance matérielle > Applications externes >
« Activer la mémoire partagée » must be checked (and the wanted sensors ticked).
The block is a sequence of <sys|temp|fan|volt|curr|pwr|duty><id/><label/><value/></...>.
"""
from __future__ import annotations

import ctypes
import re
import sys
from dataclasses import dataclass

SHM_NAME = "AIDA64_SensorValues"
_ENTRY = re.compile(
    r"<(?P<kind>[a-z]+)><id>(?P<id>.*?)</id><label>(?P<label>.*?)</label>"
    r"<value>(?P<value>.*?)</value></(?P=kind)>",
    re.S,
)

KIND_LABELS = {
    "sys": "Système",
    "temp": "Température",
    "fan": "Ventilateur",
    "duty": "Ventilateur %",
    "volt": "Tension",
    "curr": "Courant",
    "pwr": "Puissance",
}


@dataclass
class Sensor:
    id: str
    label: str
    kind: str
    raw: str

    @property
    def number(self) -> float | None:
        text = self.raw.strip().replace(",", ".")
        m = re.match(r"-?\d+(\.\d+)?", text)
        return float(m.group(0)) if m else None


def _read_windows() -> str:
    kernel32 = ctypes.windll.kernel32
    FILE_MAP_READ = 0x0004
    kernel32.OpenFileMappingW.restype = ctypes.c_void_p
    kernel32.MapViewOfFile.restype = ctypes.c_void_p
    kernel32.MapViewOfFile.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                                       ctypes.c_uint32, ctypes.c_size_t]
    kernel32.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = None
    for name in (SHM_NAME, "Global\\" + SHM_NAME, "Local\\" + SHM_NAME):
        handle = kernel32.OpenFileMappingW(FILE_MAP_READ, False, name)
        if handle:
            break
    if not handle:
        raise FileNotFoundError("AIDA64 n'est pas lancé ou la mémoire partagée est désactivée.")
    try:
        view = kernel32.MapViewOfFile(handle, FILE_MAP_READ, 0, 0, 0)
        if not view:
            raise OSError("Lecture de la mémoire partagée AIDA64 impossible.")
        try:
            raw = ctypes.string_at(view)  # null-terminated
        finally:
            kernel32.UnmapViewOfFile(view)
    finally:
        kernel32.CloseHandle(handle)
    return raw.decode("utf-8", errors="replace")


# For tests / non-Windows development
_FAKE_TEXT: str | None = None


def set_fake_data(text: str | None):
    global _FAKE_TEXT
    _FAKE_TEXT = text


def parse(text: str) -> dict[str, Sensor]:
    out: dict[str, Sensor] = {}
    for m in _ENTRY.finditer(text):
        out[m.group("id")] = Sensor(m.group("id"), m.group("label"), m.group("kind"), m.group("value"))
    return out


LAST_SOURCE = ""   # "AIDA64", "LibreHardwareMonitor" or ""


def read_sensors() -> dict[str, Sensor]:
    """Merge LibreHardwareMonitor (web server) and AIDA64 (shared memory); AIDA64 wins on equal ids.
    Raises FileNotFoundError if neither is available."""
    global LAST_SOURCE
    if _FAKE_TEXT is not None:
        LAST_SOURCE = "AIDA64"
        return parse(_FAKE_TEXT)
    data: dict[str, Sensor] = {}
    sources = []
    try:
        from . import lhm
        got = lhm.read_sensors()
        if got:
            data.update(got)
            sources.append("LibreHardwareMonitor")
    except Exception:
        pass
    if sys.platform == "win32":
        try:
            got = parse(_read_windows())
            if got:
                data.update(got)
                sources.append("AIDA64")
        except Exception:
            pass
    LAST_SOURCE = " + ".join(sources)
    if not data:
        raise FileNotFoundError("Ni AIDA64 (mémoire partagée) ni LibreHardwareMonitor (serveur web) ne répondent.")
    return data


def is_available() -> bool:
    try:
        return bool(read_sensors())
    except Exception:
        return False
