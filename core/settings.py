"""Small JSON settings store + Windows autostart + logging setup."""
from __future__ import annotations

import json
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

APP_NAME = "SmartScreen Helio"
# Folder that holds themes/, res/ … : next to the .exe when packaged, else the source folder
APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
THEMES_DIR = APP_DIR / "themes"
TRASH_DIR = APP_DIR / "themes_corbeille"
DATA_DIR = Path(os.environ.get("APPDATA", Path.home() / ".config")) / "SmartScreenHelio"
CONFIG_FILE = DATA_DIR / "config.json"
LOG_FILE = DATA_DIR / "smartscreen.log"

DEFAULTS = {"active_theme": "", "interval": 1.0, "start_minimized": True}


def setup_logging():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger("smartscreen")
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    fh = RotatingFileHandler(LOG_FILE, maxBytes=500_000, backupCount=2, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(fh)
    return log


def load() -> dict:
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    return {**DEFAULTS, **data}


def save(cfg: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(CONFIG_FILE)


# ------------------------------------------------------------------ autostart
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_RUN_NAME = "SmartScreenHelio"


def _launch_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable)}" --tray'
    exe = Path(sys.executable)
    pythonw = exe.with_name("pythonw.exe")
    if pythonw.is_file():
        exe = pythonw
    return f'"{exe}" "{APP_DIR / "app.py"}" --tray'


_TASK = "SmartScreenHelio"


def _schtasks(*args) -> bool:
    import subprocess
    try:
        r = subprocess.run(["schtasks", *args], capture_output=True, text=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=15)
        return r.returncode == 0
    except Exception:
        return False


def _run_key(enabled: bool | None):
    import winreg
    if enabled is None:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
                winreg.QueryValueEx(key, _RUN_NAME)
                return True
        except OSError:
            return False
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, _RUN_NAME, 0, winreg.REG_SZ, _launch_command())
        else:
            try:
                winreg.DeleteValue(key, _RUN_NAME)
            except OSError:
                pass


def autostart_enabled() -> bool:
    if sys.platform != "win32":
        return False
    return _schtasks("/Query", "/TN", _TASK) or bool(_run_key(None))


def set_autostart(enabled: bool):
    """Tâche planifiée « à l'ouverture de session » (démarre ~5 s après, sans la file d'attente
    lente des programmes de démarrage de Windows) ; clé Run en secours."""
    if sys.platform != "win32":
        return
    if enabled:
        if _schtasks("/Create", "/F", "/SC", "ONLOGON", "/TN", _TASK, "/TR", _launch_command(),
                     "/DELAY", "0000:05", "/IT"):
            _run_key(False)
            return
        _run_key(True)
    else:
        _schtasks("/Delete", "/F", "/TN", _TASK)
        _run_key(False)


def vendor_app_running() -> bool:
    try:
        import psutil
        for p in psutil.process_iter(["name"]):
            name = (p.info.get("name") or "").lower()
            if "smartmonitor" in name and "python" not in name:
                return True
    except Exception:
        pass
    return False


# ------------------------------------------------------------ LibreHardwareMonitor
def find_lhm() -> Path | None:
    """LibreHardwareMonitor.exe : à côté du logiciel (installateur) ou dans le dossier parent (version de travail)."""
    for base in (APP_DIR, APP_DIR.parent, Path("C:/SmartScreen Helio")):
        exe = base / "LibreHardwareMonitor" / "LibreHardwareMonitor.exe"
        if exe.is_file():
            return exe
    return None


def restart_lhm() -> str:
    """Ferme puis relance LibreHardwareMonitor en administrateur (une fenêtre de confirmation Windows)."""
    exe = find_lhm()
    if exe is None:
        return "LibreHardwareMonitor.exe introuvable."
    if sys.platform != "win32":
        return "Seulement sous Windows."
    import ctypes
    ps = ("Stop-Process -Name LibreHardwareMonitor -Force -ErrorAction SilentlyContinue; "
          "Start-Sleep -Seconds 1; "
          f"Start-Process -FilePath '{exe}' -WorkingDirectory '{exe.parent}'")
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", "powershell.exe",
                                             f'-NoProfile -WindowStyle Hidden -Command "{ps}"', None, 0)
    if rc <= 32:
        return "Relance annulée."
    return "LibreHardwareMonitor relancé (les températures reviennent dans quelques secondes)."


# ------------------------------------------------------------ sauvegarde / restauration
def backup_config(zip_path) -> str:
    """Zip : réglages (config.json) + thèmes. Retourne un court message."""
    import time
    import zipfile
    zip_path = Path(zip_path)
    n = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        if CONFIG_FILE.is_file():
            z.write(CONFIG_FILE, "config.json")
        z.writestr("LISEZMOI.txt", f"Sauvegarde SmartScreen Helio du {time.strftime('%d/%m/%Y %H:%M')}\n"
                                   "config.json = réglages ; themes/ = tous les thèmes.\n")
        if THEMES_DIR.is_dir():
            for f in THEMES_DIR.rglob("*"):
                if f.is_file() and "_old" not in f.parts:
                    z.write(f, ("themes/" + f.relative_to(THEMES_DIR).as_posix()))
                    n += 1
    return f"Sauvegarde créée : {zip_path.name} (réglages + {n} fichiers de thèmes)"


def restore_config(zip_path) -> str:
    """Restaure les réglages (l'ancien config.json est gardé à côté) et ajoute les thèmes manquants."""
    import shutil
    import time
    import zipfile
    added = 0
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        if "config.json" in names:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            if CONFIG_FILE.is_file():
                shutil.copy2(CONFIG_FILE, CONFIG_FILE.with_name(f"config_avant_restauration_{time.strftime('%Y%m%d_%H%M%S')}.json"))
            CONFIG_FILE.write_bytes(z.read("config.json"))
        for name in names:
            if not name.startswith("themes/") or name.endswith("/") or ".." in name:
                continue
            dest = THEMES_DIR / name[len("themes/"):]
            if dest.exists():
                continue                        # on n'écrase jamais un thème existant
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(z.read(name))
            added += 1
    return f"Sauvegarde restaurée ({added} fichiers de thèmes ajoutés). Relance le logiciel pour appliquer les réglages."
