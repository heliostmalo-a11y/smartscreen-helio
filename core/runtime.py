"""Background engine: compiles/uploads themes and pushes live values every second."""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Callable

from .device import DeviceError, SmartScreenDevice
from .sensors import Binding, ValueSource, bindings_for_theme
from .smartmonitor.compile import compile_theme_bundle
from .smartmonitor.ui import parse_theme_bundle

log = logging.getLogger("smartscreen")


_COMPILED: dict = {}


def compile_ui(ui_path: str | Path) -> tuple[bytes, list[Binding]]:
    """Compile un thème ; le résultat est gardé en mémoire (recompilé seulement si un fichier du thème a changé)."""
    p = Path(ui_path)
    try:
        stamp = max(f.stat().st_mtime_ns for f in p.parent.rglob("*") if f.is_file())
    except OSError:
        stamp = 0
    key = str(p)
    hit = _COMPILED.get(key)
    if hit and hit[0] == stamp:
        return hit[1], hit[2]
    bundle = parse_theme_bundle(ui_path)
    data = compile_theme_bundle(bundle)
    binds = bindings_for_theme(bundle.theme)
    if len(_COMPILED) > 8:
        _COMPILED.clear()
    _COMPILED[key] = (stamp, data, binds)
    return data, binds


class Engine:
    def __init__(self, on_status: Callable[[str], None] | None = None):
        self.device = SmartScreenDevice()
        self.source = ValueSource()
        self.bindings: list[Binding] = []
        self.interval = 1.0
        self._on_status = on_status or (lambda msg: None)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._busy = threading.Lock()   # held during uploads
        self.last_values: dict[int, int] = {}
        self.status = "Arrêté"
        # temperature alert: switch between 3 themes (normal / warn / crit)
        self.alert: dict = {}
        self.active_theme: str = ""
        self.on_theme_changed: Callable[[str], None] = lambda path: None
        self._alert_level = 0
        self._switch_level = 0
        self.last_alert_temp: float | None = None
        self._alert_candidate = (0, 0.0)
        # type d'écran : "theme" (SmartMonitor) ou "image" (AX206, Turing, XuanFang…)
        self.preferred_screen = "auto"
        self.screen_type = None
        self.image_screen = None
        self.bundle = None
        self._last_read = 0.0
        self._t0 = time.monotonic()

    # ------------------------------------------------------------ alert
    def _alert_temp(self, data) -> float | None:
        """Hottest reading among all CPU (and/or GPU) temperature sensors shared by AIDA64."""
        which = self.alert.get("sensor", "max")
        if which.startswith("id:"):
            s = data.get(which[3:])
            self.last_alert_temp = s.number if s else None
            return self.last_alert_temp
        temps = []
        for sid, s in data.items():
            if s.kind != "temp" or s.number is None:
                continue
            is_cpu = sid.startswith(("TCPU", "TCC")) or "CPU" in s.label.upper() or "CCD" in s.label.upper()
            is_gpu = sid.startswith("TGPU") or "GPU" in s.label.upper()
            if (which in ("max", "cpu") and is_cpu) or (which in ("max", "gpu") and is_gpu):
                temps.append(s.number)
        self.last_alert_temp = max(temps) if temps else None
        return self.last_alert_temp

    def alert_level_for(self, t: float, current: int) -> int:
        a = self.alert
        warn, crit, hyst = float(a.get("warn", 60)), float(a.get("crit", 80)), float(a.get("hyst", 5))
        if t >= crit or (current == 2 and t > crit - hyst):
            return 2
        if t >= warn or (current >= 1 and t > warn - hyst):
            return 1
        return 0

    def _check_alert(self, data):
        a = self.alert
        if not a.get("enabled"):
            return
        if not getattr(self, "_precompiled", False):      # prépare les fonds orange / rouge pour un changement plus rapide
            self._precompiled = True
            paths = [a.get(k) for k in ("warn_theme", "crit_theme", "normal")]

            def _pre():
                for q in paths:
                    try:
                        if q and Path(q).is_file():
                            compile_ui(q)
                    except Exception:  # noqa: BLE001
                        pass
            threading.Thread(target=_pre, daemon=True).start()
        t = self._alert_temp(data)
        if t is None:
            return
        level = self.alert_level_for(t, self._alert_level)
        themes = [a.get("normal"), a.get("warn_theme"), a.get("crit_theme")]
        wanted = themes[level]
        now = time.monotonic()
        if level != self._alert_candidate[0]:
            self._alert_candidate = (level, now)
        self._alert_level = level
        if not wanted or not Path(wanted).is_file() or wanted == self.active_theme:
            return
        if now - self._alert_candidate[1] < float(a.get("delay", 10)):
            return
        # anti-rebond : pas plus d'un changement de fond par minute (chaque changement = rechargement + déconnexion)
        if now - getattr(self, "_last_switch", -1e9) < 60:
            return
        if level < self._switch_level and now - self._alert_candidate[1] < 30:    # retour au calme : on attend 30 s
            return
        label = ["normal", "ORANGE", "ROUGE"][level]
        self._set_status(f"Température {t:.0f} °C : passage au fond {label}…")
        t0 = time.monotonic()
        self._apply_theme(wanted)
        self._last_switch = time.monotonic()
        log.info("changement de fond en %.1f s", self._last_switch - t0)
        self._switch_level = level
        self._alert_candidate = (level, self._last_switch)
        try:
            self.on_theme_changed(wanted)
        except Exception:
            pass
        self._set_status(f"Fond {label} affiché ({t:.0f} °C)")

    # ------------------------------------------------------------- screens
    @property
    def image_mode(self) -> bool:
        return self.screen_type is not None and self.screen_type.family == "image"

    def detect_screen(self):
        from . import drivers
        st = drivers.detect(self.preferred_screen)
        if st is None:
            return None
        if self.screen_type is None or st.key != self.screen_type.key:
            if self.image_screen is not None:
                self.image_screen.close()
            self.screen_type = st
            self.image_screen = st.factory() if st.family == "image" and st.factory else None
            self._set_status(f"Écran : {st.label}")
            if self.active_theme and Path(self.active_theme).is_file():
                self.bundle = parse_theme_bundle(self.active_theme)
        return st

    def _apply_theme(self, ui_path, progress=None):
        """Met un thème sur l'écran (envoi complet pour SmartMonitor, simple changement en mode image)."""
        if self.image_mode:
            self.bundle = parse_theme_bundle(ui_path)
            self.bindings = bindings_for_theme(self.bundle.theme)
            if progress:
                progress(1, 1)
        else:
            data, bindings = compile_ui(ui_path)
            self.device.upload_theme(data, progress=progress)
            self.bindings = bindings
        self.active_theme = str(ui_path)

    # ---------------------------------------------------------------- status
    def _set_status(self, msg: str):
        self.status = msg
        log.info(msg)
        try:
            self._on_status(msg)
        except Exception:
            pass

    # ------------------------------------------------------------- lifecycle
    def set_theme(self, ui_path: str | Path):
        """Use the bindings of a theme already present on the screen (no upload)."""
        bundle = parse_theme_bundle(ui_path)
        self.bundle = bundle
        self.bindings = bindings_for_theme(bundle.theme)
        self.active_theme = str(ui_path)

    def upload(self, ui_path: str | Path, progress: Callable[[int, int], None] | None = None):
        if self.screen_type is None:
            self.detect_screen()
        with self._busy:
            self._set_status("Envoi du thème à l'écran…")
            self._apply_theme(ui_path, progress)
            if not self.image_mode:
                time.sleep(1.0)
        self._set_status("Thème envoyé")

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="smartscreen-runtime", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        self.device.close()
        if self.image_screen is not None:
            self.image_screen.close()
        self._set_status("Arrêté")

    # ----------------------------------------------------------------- loop
    def tick(self):
        now = time.monotonic()
        if now - self._last_read >= 0.5 or not self.source.last_data:
            data = self.source.snapshot()
            self._last_read = now
            self._check_alert(data)
            pairs: list[tuple[int, int]] = []
            for b in self.bindings:
                v = self.source.value(b, data)
                if v is None:
                    v = self.last_values.get(b.tag)
                    if v is None:
                        continue
                iv = int(round(v * b.scale))
                self.last_values[b.tag] = iv
                pairs.append((b.tag, iv))
            if not self.image_mode:
                self.device.send_clock()
                if pairs:
                    self.device.send_values(pairs)
        if self.image_mode and self.bundle is not None and self.image_screen is not None:
            from .drivers import fit
            from .preview import render
            img = render(self.bundle, dict(self.last_values), t_ms=int((now - self._t0) * 1000))
            self.image_screen.show(fit(img, self.image_screen.size))

    def _loop(self):
        was_ok = None
        while not self._stop.is_set():
            if self._busy.locked():
                time.sleep(0.2)
                continue
            try:
                if self.screen_type is None and not self.detect_screen():
                    raise OSError("aucun écran compatible détecté")
                with self._busy:
                    self.tick()
                if was_ok is not True:
                    note = "" if self.source.aida_ok else " (températures non reçues)"
                    self._set_status("Écran connecté" + note)
                was_ok = True
            except (DeviceError, OSError, ValueError) as exc:
                if was_ok is not False:
                    self._set_status(f"Écran non connecté – nouvel essai… ({exc})")
                was_ok = False
                self.device.close()
                if self.image_screen is not None:
                    self.image_screen.close()
                self.screen_type = None
                self._stop.wait(3.0)
                continue
            if self.image_mode and self.image_screen is not None:
                self._stop.wait(1.0 / max(0.5, self.image_screen.max_fps))
            else:
                self._stop.wait(min(self.interval, 0.5))
