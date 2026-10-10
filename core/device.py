# SPDX-License-Identifier: GPL-3.0-or-later
"""Windows/Linux HID transport for the 3.5" SmartMonitor (USB 0483:0065).

Protocol (reverse-engineered by the turing-smart-screen-python HIDdev2 fork):
  * 64-byte HID reports, report id 0.
  * Theme upload: "\\x01reset" -> wait -> "ymodem" -> ACK (0x06) -> YMODEM of img.dat.
  * Runtime values: cmd 0x02, count, then (tag, value_be16) pairs (max 20).
  * Clock: cmd 0x03 01 15 yy mm dd HH MM SS weekday 64.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Callable, Optional

try:
    import hid  # package "hidapi"
except Exception:  # pragma: no cover - handled at runtime
    hid = None

log = logging.getLogger("smartscreen")

VID = 0x0483
PID = 0x0065
REPORT = 64
SOH, STX, EOT, ACK, NAK = 0x01, 0x02, 0x04, 0x06, 0x15


class DeviceError(RuntimeError):
    pass


def _crc16_xmodem(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def _frame(block_type: int, number: int, payload: bytes) -> bytes:
    head = bytes([block_type, number & 0xFF, 0xFF - (number & 0xFF)])
    return head + payload + _crc16_xmodem(payload).to_bytes(2, "big")


class SmartScreenDevice:
    """Thread-safe access to the screen. All public methods may raise DeviceError."""

    def __init__(self):
        self._dev = None
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ basics
    @staticmethod
    def is_present() -> bool:
        if hid is None:
            return False
        try:
            return bool(hid.enumerate(VID, PID))
        except Exception:
            return False

    @property
    def is_open(self) -> bool:
        return self._dev is not None

    def open(self, attempts: int = 1, delay: float = 0.5):
        if hid is None:
            raise DeviceError("Le module 'hidapi' n'est pas installé (relancer install.bat).")
        with self._lock:
            if self._dev is not None:
                return
            last = None
            for _ in range(max(1, attempts)):
                try:
                    infos = hid.enumerate(VID, PID)
                    if not infos:
                        raise DeviceError("Écran non détecté (USB 0483:0065).")
                    dev = hid.device()
                    dev.open_path(infos[0]["path"])
                    dev.set_nonblocking(False)
                    self._dev = dev
                    return
                except Exception as exc:  # noqa: BLE001
                    last = exc
                    time.sleep(delay)
            raise DeviceError(f"Impossible d'ouvrir l'écran : {last}")

    def close(self):
        with self._lock:
            if self._dev is not None:
                try:
                    self._dev.close()
                except Exception:
                    pass
            self._dev = None

    def reopen(self, attempts: int = 10, delay: float = 0.5):
        self.close()
        time.sleep(delay)
        self.open(attempts=attempts, delay=delay)

    def _write_raw(self, data: bytes):
        """Split arbitrary data in 64-byte reports."""
        if self._dev is None:
            self.open(attempts=3)
        for off in range(0, len(data), REPORT):
            chunk = data[off:off + REPORT].ljust(REPORT, b"\x00")
            written = self._dev.write(b"\x00" + chunk)
            if written is None or written < 0:
                raise DeviceError("Écriture USB refusée par l'écran.")

    def write_report(self, payload: bytes):
        if len(payload) > REPORT:
            raise ValueError("payload > 64 octets")
        with self._lock:
            try:
                self._write_raw(payload)
            except Exception:
                # one recovery attempt (unplug/replug, sleep...)
                self.reopen(attempts=6)
                self._write_raw(payload)

    def _read(self, timeout: float) -> bytes:
        if self._dev is None:
            return b""
        data = self._dev.read(REPORT + 1, int(timeout * 1000))
        if not data:
            return b""
        data = bytes(data)
        if len(data) == REPORT + 1 and data[0] == 0:
            data = data[1:]
        return data

    def _drain(self):
        try:
            while self._read(0.02):
                pass
        except Exception:
            pass

    def _expect_ack(self, timeout: float = 2.0) -> int:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            rep = self._read(max(0.05, deadline - time.monotonic()))
            if rep and rep[0] in (ACK, NAK):
                return rep[0]
        raise DeviceError("Pas de réponse (ACK) de l'écran.")

    def _send_frame(self, frame: bytes, retries: int = 8, timeout: float = 2.0):
        for _ in range(retries):
            self._write_raw(frame)
            if self._expect_ack(timeout) == ACK:
                return
        raise DeviceError("L'écran refuse un bloc du thème (NAK répétés).")

    # ----------------------------------------------------------------- runtime
    def send_values(self, pairs: list[tuple[int, int]], command: int = 0x02):
        """Send (tag, value) pairs; split in packets of 20."""
        for start in range(0, len(pairs), 20):
            chunk = pairs[start:start + 20]
            payload = bytearray(REPORT)
            payload[0] = command
            payload[1] = len(chunk)
            off = 2
            for tag, value in chunk:
                payload[off] = int(tag) & 0xFF
                payload[off + 1:off + 3] = (max(0, min(0xFFFF, int(value)))).to_bytes(2, "big")
                off += 3
            self.write_report(bytes(payload))

    def send_clock(self, when: Optional[datetime] = None):
        when = when or datetime.now()
        payload = bytearray(REPORT)
        payload[0:3] = b"\x03\x01\x15"
        payload[3:10] = bytes([when.year - 2000, when.month, when.day, when.hour,
                               when.minute, when.second, when.isoweekday()])
        payload[10] = 0x64
        self.write_report(bytes(payload))

    # ------------------------------------------------------------------ upload
    def upload_theme(self, data: bytes, progress: Callable[[int, int], None] | None = None,
                     remote_name: str = "img.dat"):
        """Upload a compiled img.dat. Takes ~10-60 s depending on size."""
        with self._lock:
            ready = False
            last = None
            for reset_delay in (1.5, 3.0, 4.5):
                try:
                    self.open(attempts=5)
                    try:
                        self._write_raw(b"\x01reset")
                    except Exception:
                        pass
                    time.sleep(reset_delay)
                    self.reopen(attempts=12, delay=0.5)
                    for _ in range(3):
                        self._drain()
                        self._write_raw(b"ymodem")
                        try:
                            if self._expect_ack(1.5) == ACK:
                                ready = True
                                break
                        except DeviceError as exc:
                            last = exc
                            time.sleep(0.3)
                    if ready:
                        break
                except Exception as exc:  # noqa: BLE001
                    last = exc
            if not ready:
                raise DeviceError(f"L'écran n'entre pas en mode transfert : {last}")

            header = bytearray(128)
            meta = f"{remote_name}\0{len(data)}\0".encode("ascii")
            header[:len(meta)] = meta
            self._send_frame(_frame(SOH, 0, bytes(header)))

            total = max(1, (len(data) + 1023) // 1024)
            for i in range(total):
                block = data[i * 1024:(i + 1) * 1024].ljust(1024, b"\x1A")
                self._send_frame(_frame(STX, i + 1, block))
                if progress:
                    progress(i + 1, total)

            self._write_raw(bytes([EOT]))
            self._expect_ack(3.0)
            self._send_frame(_frame(SOH, 0, bytes(128)))
            # the screen restarts with the new theme
            time.sleep(0.5)
            try:
                self.reopen(attempts=16, delay=0.5)
            except DeviceError:
                pass
