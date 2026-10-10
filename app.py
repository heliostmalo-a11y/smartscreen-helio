"""SmartScreen Hélio — pilote libre pour l'écran 3,5" USB (SmartMonitor 0483:0065).

Lancement :  pythonw app.py          (fenêtre)
             pythonw app.py --tray   (démarrage discret, icône près de l'horloge)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtCore import QLockFile  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from core import settings  # noqa: E402


def main() -> int:
    import time as _t
    _t0 = _t.monotonic()
    log = settings.setup_logging()
    app = QApplication(sys.argv)
    app.setApplicationName(settings.APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    # barres bien visibles (progression d'envoi, défilement de la galerie)
    app.setStyleSheet("""
        QProgressBar { border: 1px solid #00b4ff; border-radius: 5px; background: #000000;
                       color: white; text-align: center; min-height: 18px; font-weight: bold; }
        QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                              stop:0 #00b4ff, stop:1 #3ce03c); border-radius: 4px; }
        QScrollBar:vertical { background: #1e1e1e; width: 14px; margin: 0; }
        QScrollBar::handle:vertical { background: #00b4ff; border-radius: 6px; min-height: 30px; }
        QScrollBar::handle:vertical:hover { background: #3cc8ff; }
        QScrollBar:horizontal { background: #1e1e1e; height: 14px; margin: 0; }
        QScrollBar::handle:horizontal { background: #00b4ff; border-radius: 6px; min-width: 30px; }
        QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
    """)

    lock = QLockFile(str(settings.DATA_DIR / "smartscreen.lock"))
    if not lock.tryLock(100):
        QMessageBox.information(None, settings.APP_NAME,
                                "SmartScreen est déjà lancé (icône près de l'horloge).")
        return 0

    from gui.main_window import MainWindow
    tray = "--tray" in sys.argv
    win = MainWindow(tray_mode=tray)
    if not tray:
        win.show()
    log.info("SmartScreen démarré (tray=%s) en %.1f s", tray, _t.monotonic() - _t0)
    code = app.exec()
    lock.unlock()
    return code


if __name__ == "__main__":
    sys.exit(main())
