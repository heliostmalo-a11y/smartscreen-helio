"""Écrans pris en charge et détection automatique.

Deux familles :
* « theme »  : l'écran garde un thème en mémoire et reçoit seulement les valeurs (SmartMonitor 0483:0065).
* « image »  : SmartScreen dessine l'image complète et l'envoie (AX206, Turing, XuanFang, WeAct, Kipye…).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

from PIL import Image

log = logging.getLogger("smartscreen")


@dataclass
class ScreenType:
    key: str
    label: str
    family: str                       # "theme" or "image"
    detect: Callable[[], bool]
    factory: Callable[[], "ImageScreen"] | None = None
    note: str = ""
    driver: str = ""                  # lien de téléchargement du pilote (vide = aucun pilote à installer)


class ImageScreen:
    """Écran qui affiche une image envoyée par l'ordinateur."""
    name = "écran"
    max_fps = 4.0

    def open(self):  # pragma: no cover - hardware
        raise NotImplementedError

    def close(self):
        pass

    @property
    def size(self) -> tuple[int, int]:  # largeur, hauteur en paysage
        raise NotImplementedError

    def show(self, image: Image.Image):  # pragma: no cover - hardware
        raise NotImplementedError


def fit(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Adapte l'image 480×320 du thème à la taille de l'écran (sans déformer, bandes noires si besoin)."""
    if image.size == size:
        return image
    w, h = size
    scale = min(w / image.width, h / image.height)
    resized = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))),
                           Image.Resampling.LANCZOS)
    out = Image.new("RGB", size, "black")
    out.paste(resized, ((w - resized.width) // 2, (h - resized.height) // 2))
    return out


# Liens des pilotes (Windows 10/11)
ZADIG = "https://zadig.akeo.ie/"
WCH = "https://www.wch-ic.com/downloads/CH341SER_EXE.html"
TURING_WIKI = "https://github.com/mathoudebine/turing-smart-screen-python/wiki/Hardware-revisions"
LHM = "https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases"

DRIVER_HELP = [
    ("Températures : LibreHardwareMonitor (obligatoire, déjà dans l'installateur)", LHM),
    ("AX206 : Zadig → choisir l'écran (1908:0102) → pilote « libusb-win32 » → Installer", ZADIG),
    ("Turing / XuanFang / Kipye / WeAct : normalement aucun pilote sous Windows 10/11. "
     "Si l'écran n'apparaît pas dans les ports COM : pilote série CH340/CH341", WCH),
    ("Identifier son modèle d'écran série (photos des révisions)", TURING_WIKI),
]


# ---------------------------------------------------------------- détection
def _hid_present(vid: int, pid: int) -> bool:
    try:
        import hid
        return bool(hid.enumerate(vid, pid))
    except Exception:
        return False


def _usb_present(vid: int, pid: int) -> bool:
    try:
        import usb.core
        return usb.core.find(idVendor=vid, idProduct=pid) is not None
    except Exception:
        return False


def _ports():
    try:
        from serial.tools.list_ports import comports
        return list(comports())
    except Exception:
        return []


def _port(serials=(), vidpid=()) -> bool:
    for p in _ports():
        if p.serial_number in serials:
            return True
        if (p.vid, p.pid) in vidpid and not serials:
            return True
    return False


def _turing(cls_name: str, w: int, h: int):
    def make():
        from .turing_screen import TuringScreen
        return TuringScreen(cls_name, w, h)
    return make


def _ax206():
    from .ax206 import AX206Screen
    return AX206Screen()


SCREENS: list[ScreenType] = [
    ScreenType("smartmonitor", "SmartMonitor 3,5\" (USB 0483:0065)", "theme",
               lambda: _hid_present(0x0483, 0x0065)),
    ScreenType("ax206", "Cadre photo AX206 (USB 1908:0102)", "image",
               lambda: _usb_present(0x1908, 0x0102), _ax206,
               note="Nécessite le pilote libusb-win32 : lancer Zadig, choisir l'écran (1908:0102), "
                    "pilote « libusb-win32 », puis Installer.", driver=ZADIG),
    ScreenType("turing_a", "Turing Smart Screen 3,5\"", "image",
               lambda: _port(serials=("USB35INCHIPSV2",)), _turing("A", 320, 480)),
    ScreenType("xuanfang", "XuanFang 3,5\" (révision B / flagship)", "image",
               lambda: _port(serials=("2017-2-25",)), _turing("B", 320, 480)),
    ScreenType("turing_a_generic", "Écran 3,5\" série CH340 (Turing ou XuanFang)", "image",
               lambda: _port(vidpid=((0x1a86, 0x5722),)), _turing("A", 320, 480)),
    ScreenType("turing_c5", "Turing 5\" (révision C)", "image",
               lambda: _port(serials=("USB7INCH",)), _turing("C", 480, 800)),
    ScreenType("turing_c21", "Turing 2,1\" rond (révision C)", "image",
               lambda: _port(serials=("CT21INCH",)), _turing("C", 480, 480)),
    ScreenType("turing_c88", "Turing 8,8\" (révision C)", "image",
               lambda: _port(serials=("CT88INCH",)), _turing("C", 480, 1920)),
    ScreenType("kipye", "Kipye Qiye 3,5\" (révision D)", "image",
               lambda: _port(vidpid=((0x454d, 0x4e41),)), _turing("D", 320, 480)),
    ScreenType("weact_a", "WeAct Studio 3,5\"", "image",
               lambda: any(isinstance(p.serial_number, str) and p.serial_number.startswith("AB") for p in _ports()),
               _turing("WEACT_A", 320, 480)),
    ScreenType("weact_b", "WeAct Studio 0,96\"", "image",
               lambda: any(isinstance(p.serial_number, str) and p.serial_number.startswith("AD") for p in _ports()),
               _turing("WEACT_B", 80, 160)),
]

BY_KEY = {s.key: s for s in SCREENS}


def detect(preferred: str = "auto") -> ScreenType | None:
    if preferred and preferred != "auto":
        s = BY_KEY.get(preferred)
        return s
    for s in SCREENS:
        try:
            if s.detect():
                return s
        except Exception as exc:  # noqa: BLE001
            log.debug("détection %s : %s", s.key, exc)
    return None
