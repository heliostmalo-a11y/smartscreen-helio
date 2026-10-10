"""Cadres photo AX206 « hackés » (USB 1908:0102), protocole dpf-ax / lcd4linux.

L'écran reçoit des rectangles d'image en RGB565 big-endian, encapsulés dans des commandes
SCSI (transport USB mass-storage « bulk-only »). Sous Windows il faut le pilote libusb-win32
(celui livré par AIDA64 pour l'AX206) et le module Python pyusb.
"""
from __future__ import annotations

import struct

from PIL import Image

from . import ImageScreen

VID, PID = 0x1908, 0x0102
EP_OUT, EP_IN = 0x01, 0x81
CMD_PROBE, CMD_SETPROP, CMD_BLIT = 0x00, 0x01, 0x12


class AX206Screen(ImageScreen):
    name = "AX206"
    max_fps = 8.0

    def __init__(self):
        self.dev = None
        self._size = (320, 240)
        self._tag = 0

    # ------------------------------------------------------------ usb / scsi
    def _scsi(self, cdb: bytes, data_out: bytes = b"", read_len: int = 0) -> bytes:
        self._tag = (self._tag + 1) & 0xFFFFFFFF
        length = len(data_out) if data_out else read_len
        flags = 0x80 if read_len else 0x00
        cbw = struct.pack("<4sIIBBB", b"USBC", self._tag, length, flags, 0, len(cdb)) + cdb.ljust(16, b"\x00")
        self.dev.write(EP_OUT, cbw, timeout=2000)
        result = b""
        if data_out:
            self.dev.write(EP_OUT, data_out, timeout=5000)
        elif read_len:
            result = bytes(self.dev.read(EP_IN, read_len, timeout=2000))
        self.dev.read(EP_IN, 13, timeout=2000)          # CSW
        return result

    @staticmethod
    def _cdb(cmd: int, args: bytes = b"") -> bytes:
        return bytes([0xCD, 0, 0, 0, 0, 6 if cmd != CMD_PROBE else 2, cmd]) + args

    def open(self):
        import usb.core
        dev = usb.core.find(idVendor=VID, idProduct=PID)
        if dev is None:
            raise OSError("AX206 non détecté (pilote libusb-win32 installé ?)")
        try:
            dev.set_configuration()
        except Exception:
            pass
        self.dev = dev
        try:
            info = self._scsi(bytes([0xCD, 0, 0, 0, 0, 2]), read_len=5)
            w, h = info[0] | info[1] << 8, info[2] | info[3] << 8
            if 32 <= w <= 2048 and 32 <= h <= 2048:
                self._size = (w, h)
        except Exception:
            pass
        self.set_backlight(7)

    def close(self):
        if self.dev is not None:
            try:
                import usb.util
                usb.util.dispose_resources(self.dev)
            except Exception:
                pass
        self.dev = None

    @property
    def size(self) -> tuple[int, int]:
        return self._size

    def set_backlight(self, level: int):
        level = max(0, min(7, level))
        try:
            self._scsi(self._cdb(CMD_SETPROP, bytes([0x01, 0x00, level, 0x00])))
        except Exception:
            pass

    def show(self, image: Image.Image):
        if self.dev is None:
            self.open()
        img = image.convert("RGB")
        if img.size != self._size:
            from . import fit
            img = fit(img, self._size)
        w, h = img.size
        import numpy as np
        a = np.asarray(img, dtype=np.uint16)
        rgb565 = ((a[..., 0] >> 3) << 11) | ((a[..., 1] >> 2) << 5) | (a[..., 2] >> 3)
        data = rgb565.astype(">u2").tobytes()
        args = struct.pack("<HHHH", 0, 0, w - 1, h - 1)
        self._scsi(self._cdb(CMD_BLIT, args), data_out=data)
