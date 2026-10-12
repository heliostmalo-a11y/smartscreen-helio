"""Surveillance de LibreHardwareMonitor.

Au démarrage de Windows, LibreHardwareMonitor est parfois lancé avant que le matériel soit prêt :
son serveur web ne répond pas, ou répond sans aucun capteur. Le logiciel le détecte et le relance
tout seul (une seule fenêtre de confirmation Windows), au lieu de demander de cliquer plusieurs fois.
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
import threading
import time
import urllib.request

log = logging.getLogger("smartscreen")

PORT = 8085
WAIT_BEFORE_RESTART = 30      # secondes sans températures avant la première relance
MAX_ATTEMPTS = 2              # relances automatiques par période sans températures
MIN_GAP = 150                 # secondes entre deux relances (le script de relance dure jusqu'à ~100 s)


def process_running() -> bool:
    """LibreHardwareMonitor.exe tourne-t-il ?"""
    if sys.platform != "win32":
        return False
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq LibreHardwareMonitor.exe", "/NH"],
                             capture_output=True, text=True, timeout=10,
                             creationflags=0x08000000).stdout          # CREATE_NO_WINDOW
        return "LibreHardwareMonitor.exe" in out
    except Exception:
        return False


def web_state(port: int = PORT) -> str:
    """'ok' (capteurs servis), 'empty' (serveur web sans capteur) ou 'down' (ne répond pas)."""
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/data.json", headers={"User-Agent": "SmartScreenHelio"})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=2.5) as resp:
            tree = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        return "down"
    from . import lhm
    return "ok" if lhm.parse(tree) else "empty"


def diagnose() -> str:
    """Phrase courte pour le journal."""
    if not process_running():
        return "LibreHardwareMonitor n'est pas lancé"
    st = web_state()
    return {"down": "LibreHardwareMonitor tourne mais son serveur web ne répond pas",
            "empty": "serveur web actif mais aucun capteur lu",
            "ok": "capteurs disponibles"}[st]


class Guard:
    """Relance LibreHardwareMonitor si les températures manquent trop longtemps.

    ok_fn() -> True (températures reçues), False (non reçues) ou None (envoi à l'écran arrêté : on ne fait rien).
    enabled_fn() -> réglage « relance automatique » coché ou non.
    """

    def __init__(self, ok_fn, enabled_fn):
        self.ok_fn = ok_fn
        self.enabled_fn = enabled_fn
        self._thread: threading.Thread | None = None

    def start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="lhm-guard", daemon=True)
            self._thread.start()

    def _run(self):
        from . import settings
        bad_since: float | None = None
        attempts = 0
        last_try = -1e9
        while True:
            time.sleep(5)
            try:
                if not self.enabled_fn():
                    bad_since = None
                    continue
                ok = self.ok_fn()
                if ok is None:
                    bad_since = None
                    continue
                now = time.monotonic()
                if ok:
                    if bad_since is not None:
                        log.info("Températures reçues")
                    bad_since, attempts = None, 0
                    continue
                if bad_since is None:
                    bad_since = now
                if (now - bad_since >= WAIT_BEFORE_RESTART and attempts < MAX_ATTEMPTS
                        and now - last_try >= MIN_GAP and settings.find_lhm() is not None):
                    attempts += 1
                    last_try = now
                    log.info("Températures absentes depuis %d s (%s) : relance automatique de LibreHardwareMonitor (%d/%d)",
                             now - bad_since, diagnose(), attempts, MAX_ATTEMPTS)
                    log.info(settings.restart_lhm())
            except Exception as exc:  # noqa: BLE001 — la surveillance ne doit jamais planter le logiciel
                log.info("Surveillance LibreHardwareMonitor : %s", exc)
