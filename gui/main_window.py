"""Main window: Écran (status) / Thèmes (gallery) / Éditeur + tray icon."""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

from PIL.ImageQt import ImageQt
from PySide6.QtCore import QObject, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFormLayout, QGroupBox, QSpinBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel,
                               QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox, QProgressBar,
                               QPushButton, QSystemTrayIcon, QTableWidget, QTableWidgetItem, QTabWidget,
                               QVBoxLayout, QWidget)

from core import settings
from core.device import SmartScreenDevice
from core.model import find_ui
from core.preview import thumbnail
from core.runtime import Engine
from gui.editor import EditorTab

ICON = settings.APP_DIR / "res" / "icons" / "app.png"


class Bridge(QObject):
    status = Signal(str)
    theme_changed = Signal(str)
    progress = Signal(int, int)


class UploadWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, engine: Engine, ui_path: str, bridge: Bridge):
        super().__init__()
        self.engine, self.ui_path, self.bridge = engine, ui_path, bridge

    def run(self):
        try:
            self.engine.upload(self.ui_path, progress=lambda i, n: self.bridge.progress.emit(i, n))
            self.done.emit(True, self.ui_path)
        except Exception as exc:  # noqa: BLE001
            self.done.emit(False, str(exc))


# ======================================================================= Écran
class ScreenTab(QWidget):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        self.lbl_dev = QLabel()
        self.lbl_aida = QLabel()
        self.lbl_theme = QLabel()
        self.lbl_status = QLabel()
        self.lbl_status.setWordWrap(True)
        for l in (self.lbl_dev, self.lbl_aida, self.lbl_theme):
            l.setStyleSheet("font-size:14px")
        self.btn_toggle = QPushButton("Arrêter l'envoi des valeurs")
        self.btn_toggle.clicked.connect(self.toggle)
        self.btn_resend = QPushButton("Renvoyer le thème actif à l'écran")
        self.btn_resend.clicked.connect(self.resend)
        from core import drivers as _drv
        self.cb_screen = QComboBox()
        self.cb_screen.addItem("Automatique (détecte l'écran branché)", "auto")
        for st in _drv.SCREENS:
            self.cb_screen.addItem(st.label, st.key)
        self.cb_screen.setCurrentIndex(max(0, self.cb_screen.findData(self.win.cfg.get("screen_type", "auto"))))
        self.cb_screen.activated.connect(self.set_screen_type)
        self.ck_auto = QCheckBox("Lancer avec Windows (discret, icône près de l'horloge)")
        self.ck_auto.setChecked(settings.autostart_enabled())
        self.ck_auto.toggled.connect(self.set_autostart)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["N°", "Capteur", "Valeur envoyée"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        help_ = QLabel(
            "<b>Si les températures restent vides :</b> LibreHardwareMonitor doit être lancé "
            "(en administrateur), avec <i>Options → Remote Web Server → Run</i> coché. "
            "Le logiciel d'origine « 3.5 Inch SmartMonitor » doit être fermé.")
        help_.setWordWrap(True)
        help_.setStyleSheet("color:#999")

        btns = QHBoxLayout()
        btns.addWidget(self.btn_toggle)
        btns.addWidget(self.btn_resend)
        self.btn_lhm = QPushButton("Relancer les températures")
        self.btn_lhm.setToolTip("Ferme et relance LibreHardwareMonitor (si les températures ne sont plus reçues)")
        self.btn_lhm.clicked.connect(self.restart_lhm)
        btns.addWidget(self.btn_lhm)
        btns.addStretch()
        lay = QVBoxLayout(self)
        self.lbl_preview = QLabel()              # aperçu du thème affiché sur l'écran
        self.lbl_preview.setFixedSize(360, 240)
        self.lbl_preview.setStyleSheet("border:1px solid #444; background:#000")
        self._preview_key = None
        top = QHBoxLayout()
        infos = QVBoxLayout()
        for w in (self.lbl_dev, self.lbl_aida, self.lbl_theme):
            infos.addWidget(w)
        infos.addStretch()
        top.addLayout(infos, 1)
        top.addWidget(self.lbl_preview)
        lay.addLayout(top)
        row_scr = QHBoxLayout()
        row_scr.addWidget(QLabel("Type d'écran :"))
        row_scr.addWidget(self.cb_screen, 1)
        btn_drv = QPushButton("Pilotes…")
        btn_drv.setToolTip("Liens pour télécharger les pilotes des écrans")
        btn_drv.clicked.connect(self.show_drivers)
        row_scr.addWidget(btn_drv)
        lay.addLayout(row_scr)
        lay.addLayout(btns)
        lay.addWidget(self.progress)
        lay.addWidget(self.lbl_status)
        lay.addWidget(self.ck_auto)
        lay.addWidget(self._alert_box())
        lay.addWidget(QLabel("Valeurs envoyées à l'écran :"))
        lay.addWidget(self.table, 1)
        lay.addWidget(help_)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(2000)
        self.refresh()

    # ------------------------------------------------------- temperature alert
    def _alert_box(self) -> QGroupBox:
        a = self.win.cfg.setdefault("alert", {"enabled": False, "sensor": "max", "warn": 60, "crit": 80,
                                              "hyst": 5, "delay": 8})
        box = QGroupBox("Fond selon la température (change de thème automatiquement)")
        box.setCheckable(True)
        box.setChecked(bool(a.get("enabled")))
        form = QFormLayout(box)
        self.cb_alert_sensor = QComboBox()
        for label, key in (("Le plus chaud (CPU ou GPU)", "max"), ("Processeur (CPU)", "cpu"),
                           ("Carte graphique (GPU)", "gpu")):
            self.cb_alert_sensor.addItem(label, key)
        self.cb_alert_sensor.setCurrentIndex(max(0, self.cb_alert_sensor.findData(a.get("sensor", "max"))))
        self.sp_warn, self.sp_crit = QSpinBox(), QSpinBox()
        for sp, v in ((self.sp_warn, a.get("warn", 60)), (self.sp_crit, a.get("crit", 80))):
            sp.setRange(30, 110)
            sp.setSuffix(" °C")
            sp.setValue(int(v))
        self.cb_th = [QComboBox() for _ in range(3)]
        themes = [str(u) for u in sorted(settings.THEMES_DIR.glob("*/*.ui"))
                  if not u.parent.name.startswith("_")]
        themes += [str(u) for u in sorted((settings.THEMES_DIR / "_variantes").glob("*/*.ui"))]
        for cb, key in zip(self.cb_th, ("normal", "warn_theme", "crit_theme")):
            cb.addItem("— aucun —", "")
            for t in themes:
                cb.addItem(Path(t).stem, t)
            cb.setCurrentIndex(max(0, cb.findData(a.get(key, ""))))
        form.addRow("Température surveillée", self.cb_alert_sensor)
        form.addRow("Thème normal", self.cb_th[0])
        form.addRow("Seuil orange", self.sp_warn)
        form.addRow("Thème orange", self.cb_th[1])
        form.addRow("Seuil rouge", self.sp_crit)
        form.addRow("Thème rouge", self.cb_th[2])
        note = QLabel("Le changement se fait après 10 s au-dessus du seuil, et le retour 5 °C en dessous. "
                      "L'écran recharge alors le thème (quelques secondes à 1-2 min pour un thème animé).")
        note.setWordWrap(True)
        note.setStyleSheet("color:#999")
        form.addRow(note)
        self.box_alert = box
        for w in (box,):
            w.toggled.connect(self._save_alert)
        self.cb_alert_sensor.activated.connect(self._save_alert)
        self.sp_warn.valueChanged.connect(self._save_alert)
        self.sp_crit.valueChanged.connect(self._save_alert)
        for cb in self.cb_th:
            cb.activated.connect(self._save_alert)
        self.cb_th[0].activated.connect(lambda *_: self._autofill_variants(force=True))
        self._autofill_variants(force=False)
        self.win.engine.alert = dict(self.win.cfg.get("alert", a))
        return box

    @staticmethod
    def _find_variants(normal_ui: str) -> tuple[str, str]:
        """'Anime - Ma basse (notes)' -> ('…Ma basse ORANGE.ui', '…Ma basse ROUGE.ui') if they exist."""
        import re as _re
        if not normal_ui:
            return "", ""
        stem = Path(normal_ui).stem
        base = _re.sub(r"\s*\(.*?\)\s*$", "", stem).strip()
        found = []
        for color in ("ORANGE", "ROUGE"):
            hit = ""
            for root in (settings.THEMES_DIR / "_variantes", settings.THEMES_DIR):
                for name in (f"{stem} {color}", f"{base} {color}"):
                    ui = root / name / f"{name}.ui"
                    if ui.is_file():
                        hit = str(ui)
                        break
                if hit:
                    break
            found.append(hit)
        return found[0], found[1]

    def _autofill_variants(self, force: bool):
        normal = self.cb_th[0].currentData() or ""
        if not normal:
            active = self.win.cfg.get("active_theme", "")
            idx = self.cb_th[0].findData(active)
            if idx > 0:
                self.cb_th[0].setCurrentIndex(idx)
                normal = active
        orange, rouge = self._find_variants(normal)
        changed = False
        for cb, path in ((self.cb_th[1], orange), (self.cb_th[2], rouge)):
            if force and not path:
                cb.setCurrentIndex(0)          # pas de variante pour ce thème : on n'en garde pas une autre
                changed = True
                continue
            if path and (force or not cb.currentData()):
                i = cb.findData(path)
                if i < 0:
                    cb.addItem(Path(path).stem, path)
                    i = cb.findData(path)
                cb.setCurrentIndex(i)
                changed = True
        if changed or normal:
            self._save_alert()

    def use_as_normal(self, ui_path: str):
        """Le thème choisi dans la galerie devient le « thème normal », avec ses variantes orange/rouge.
        Sans ça, l'alerte renvoyait aussitôt l'ancien thème normal et l'écran se déconnectait en boucle."""
        a = self.win.cfg.get("alert", {})
        if Path(ui_path).parent.parent.name == "_variantes" or \
                ui_path in (a.get("normal"), a.get("warn_theme"), a.get("crit_theme")):
            return
        cb = self.cb_th[0]
        i = cb.findData(ui_path)
        if i < 0:
            cb.addItem(Path(ui_path).stem, ui_path)
            i = cb.findData(ui_path)
        cb.setCurrentIndex(i)
        self._autofill_variants(force=True)
        self._save_alert()

    def _refresh_alert_sensors(self):
        """Add every live temperature sensor (CPU Tctl, CCD1, GPU, SSD…) to the 'Température surveillée' list."""
        if not hasattr(self, "cb_alert_sensor"):
            return
        try:
            from core import aida64 as _a
            live = self.win.engine.source.last_data
        except Exception:
            return
        cb = self.cb_alert_sensor
        known = {cb.itemData(i) for i in range(cb.count())}
        wanted = self.win.cfg.get("alert", {}).get("sensor", "max")
        for sid, sen in sorted(live.items(), key=lambda kv: kv[1].label):
            if sen.kind == "temp" and sen.number is not None and \
                    (sid.startswith("LHM:") or _a.LAST_SOURCE == "AIDA64"):
                key = "id:" + sid
                if key not in known:
                    cb.addItem(f"{sen.label}", key)
                    known.add(key)
        i = cb.findData(wanted)
        if i >= 0 and cb.currentIndex() != i:
            cb.blockSignals(True)
            cb.setCurrentIndex(i)
            cb.blockSignals(False)

    def _save_alert(self, *_):
        a = self.win.cfg.setdefault("alert", {})
        a.update(enabled=self.box_alert.isChecked(), sensor=self.cb_alert_sensor.currentData(),
                 warn=self.sp_warn.value(), crit=max(self.sp_crit.value(), self.sp_warn.value() + 1),
                 normal=self.cb_th[0].currentData(), warn_theme=self.cb_th[1].currentData(),
                 crit_theme=self.cb_th[2].currentData())
        a.setdefault("hyst", 5)
        a["delay"] = 8
        settings.save(self.win.cfg)
        self.win.engine.alert = dict(a)

    def show_drivers(self):
        from core import drivers as _drv
        items = "".join(f"<li>{txt}<br><a href='{url}'>{url}</a></li>" for txt, url in _drv.DRIVER_HELP)
        box = QMessageBox(self)
        box.setWindowTitle("Pilotes des écrans")
        box.setTextFormat(Qt.RichText)
        box.setTextInteractionFlags(Qt.TextBrowserInteraction)
        box.setText("<b>SmartMonitor 3,5\" :</b> aucun pilote à installer.<ul>" + items + "</ul>"
                    "Après l'installation d'un pilote, débranche et rebranche l'écran.")
        for lbl in box.findChildren(QLabel):
            lbl.setOpenExternalLinks(True)
        box.exec()

    def _update_preview(self, ui: str):
        try:
            key = (ui, Path(ui).stat().st_mtime) if ui and Path(ui).is_file() else None
        except OSError:
            key = None
        if key == self._preview_key:
            return
        self._preview_key = key
        if key is None:
            self.lbl_preview.clear()
            return
        try:
            from core import preview
            from core.smartmonitor.ui import parse_theme_bundle
            img = preview.render(parse_theme_bundle(ui), dict(self.win.engine.last_values))
            img = img.resize((360, 240))
            self.lbl_preview.setPixmap(QPixmap.fromImage(ImageQt(img.convert("RGBA"))))
        except Exception:
            self.lbl_preview.clear()

    def set_screen_type(self, *_):
        key = self.cb_screen.currentData() or "auto"
        self.win.cfg["screen_type"] = key
        settings.save(self.win.cfg)
        eng = self.win.engine
        eng.preferred_screen = key
        eng.screen_type = None          # la boucle refait la détection
        st = __import__("core.drivers", fromlist=["BY_KEY"]).BY_KEY.get(key)
        if st and st.note:
            msg = QMessageBox(self)
            msg.setWindowTitle("Écran")
            msg.setTextFormat(Qt.RichText)
            msg.setText(st.note + (f"<br><br><a href='{st.driver}'>Télécharger le pilote</a>" if st.driver else ""))
            for lbl in msg.findChildren(QLabel):
                lbl.setOpenExternalLinks(True)
            msg.exec()

    def refresh(self):
        # fenêtre rangée près de l'horloge ou autre onglet : rien à redessiner (économise le processeur)
        if not self.isVisible() or self.win.isMinimized():
            return
        eng = self.win.engine
        st = eng.screen_type
        if st is not None:
            self.lbl_dev.setText(f"🟢 Écran détecté : {st.label}")
        elif SmartScreenDevice.is_present():
            self.lbl_dev.setText("🟢 Écran détecté : SmartMonitor 3,5\"")
        else:
            self.lbl_dev.setText("🔴 Aucun écran compatible détecté — vérifier le câble USB")
        aida_ok = eng.source.aida_ok
        from core import aida64 as _a
        self.lbl_aida.setText("🟢 Températures reçues" if aida_ok else
                              "🟠 Températures non reçues : lancer LibreHardwareMonitor")
        self._refresh_alert_sensors()
        t = getattr(eng, "last_alert_temp", None)
        if hasattr(self, "box_alert"):
            self.box_alert.setTitle("Fond selon la température" + (f"  —  mesurée : {t:.0f} °C" if t is not None else ""))
        active = self.win.cfg.get("active_theme") or "aucun"
        self.lbl_theme.setText(f"Thème actif : <b>{Path(active).stem if active != 'aucun' else active}</b>")
        self._update_preview(active)
        running = bool(eng._thread and eng._thread.is_alive())
        self.btn_toggle.setText("Arrêter l'envoi des valeurs" if running else "Démarrer l'envoi des valeurs")
        names = {}
        for b in eng.bindings:
            names[b.tag] = b.aida_id or b.metric or "?"
        try:
            live = self.win.engine.source.last_data
        except Exception:
            live = {}
        rows = [(b.tag, names.get(b.tag, "?"), eng.last_values.get(b.tag)) for b in sorted(eng.bindings, key=lambda b: b.tag)]
        if self.table.rowCount() != len(rows):
            self.table.setRowCount(len(rows))
        for r, (tag, sid, val) in enumerate(rows):
            label = f"{live[sid].label}  [{sid}]" if sid in live else f"{sid}"
            text = str(val) if val is not None else "— non reçu"
            for c, t in enumerate((str(tag), label, text)):
                it = self.table.item(r, c)
                if it is None:
                    self.table.setItem(r, c, QTableWidgetItem(t))
                elif it.text() != t:            # ne redessine que ce qui change
                    it.setText(t)

    def restart_lhm(self):
        msg = settings.restart_lhm()
        self.win.statusBar().showMessage(msg, 10000)
        try:
            from core import lhm
            lhm._LAST = None
        except Exception:
            pass

    def toggle(self):
        eng = self.win.engine
        if eng._thread and eng._thread.is_alive():
            eng.stop()
        else:
            eng.start()
        self.refresh()

    def resend(self):
        active = self.win.cfg.get("active_theme")
        if not active or not Path(active).is_file():
            QMessageBox.information(self, "Écran", "Choisis d'abord un thème dans l'onglet Thèmes.")
            return
        self.win.send_theme(active)

    def set_autostart(self, on: bool):
        try:
            settings.set_autostart(on)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Démarrage automatique", str(exc))


# ===================================================================== Thèmes
class GalleryTab(QWidget):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        self.list = QListWidget()
        self.list.setViewMode(QListWidget.IconMode)
        self.list.setIconSize(QSize(240, 160))
        self.list.setGridSize(QSize(262, 200))
        self.list.setResizeMode(QListWidget.Adjust)
        self.list.setMovement(QListWidget.Static)
        self.list.setSpacing(6)
        self.list.itemDoubleClicked.connect(lambda *_: self.edit())

        actions = [("▶ Utiliser sur l'écran", self.use), ("✏ Modifier", self.edit), ("Dupliquer", self.duplicate),
                   ("Supprimer", self.remove), ("Importer les thèmes du logiciel d'origine…", self.import_vendor),
                   ("Ouvrir le dossier", self.open_folder)]
        btns = QHBoxLayout()
        for text, slot in actions:
            b = QPushButton(text)
            b.clicked.connect(slot)
            btns.addWidget(b)
        btns.addStretch()
        lay = QVBoxLayout(self)
        lay.addLayout(btns)
        lay.addWidget(self.list)
        self.reload()

    def reload(self, select: str | None = None):
        self.list.clear()
        settings.THEMES_DIR.mkdir(exist_ok=True)
        for d in sorted(p for p in settings.THEMES_DIR.iterdir() if p.is_dir() and not p.name.startswith("_")):
            ui = find_ui(d)
            if not ui:
                continue
            img = self._cached_thumb(ui)
            item = QListWidgetItem(QIcon(QPixmap.fromImage(ImageQt(img.convert("RGBA")))), d.name)
            item.setData(Qt.UserRole, str(ui))
            if str(ui) == self.win.cfg.get("active_theme"):
                item.setText(f"★ {d.name}")
            self.list.addItem(item)
            if select and str(ui) == select:
                self.list.setCurrentItem(item)

    @staticmethod
    def _cached_thumb(ui):
        """Vignette mise en cache dans le dossier du thème (recalculée si le thème change)."""
        from PIL import Image
        cache = Path(ui).parent / ".vignette.png"
        try:
            if cache.is_file() and cache.stat().st_mtime >= Path(ui).stat().st_mtime:
                return Image.open(cache)
        except Exception:
            pass
        img = thumbnail(ui)
        try:
            img.save(cache)
        except Exception:
            pass
        return img

    def _current(self) -> str | None:
        it = self.list.currentItem()
        if not it:
            QMessageBox.information(self, "Thèmes", "Sélectionne d'abord un thème.")
            return None
        return it.data(Qt.UserRole)

    def use(self):
        ui = self._current()
        if ui:
            self.win.send_theme(ui)

    def edit(self):
        ui = self._current()
        if ui:
            self.win.editor.load(ui)
            self.win.tabs.setCurrentWidget(self.win.editor)

    def duplicate(self):
        ui = self._current()
        if not ui:
            return
        src = Path(ui).parent
        n = 2
        while (settings.THEMES_DIR / f"{src.name} ({n})").exists():
            n += 1
        dest = settings.THEMES_DIR / f"{src.name} ({n})"
        shutil.copytree(src, dest)
        old = dest / Path(ui).name
        old.rename(dest / f"{dest.name}.ui")
        self.reload(select=str(dest / f"{dest.name}.ui"))

    def remove(self):
        ui = self._current()
        if not ui:
            return
        src = Path(ui).parent
        if QMessageBox.question(self, "Supprimer", f"Mettre « {src.name} » à la corbeille des thèmes ?\n"
                                f"(dossier {settings.TRASH_DIR.name}, récupérable)") != QMessageBox.Yes:
            return
        settings.TRASH_DIR.mkdir(exist_ok=True)
        dest = settings.TRASH_DIR / f"{src.name}_{time.strftime('%Y%m%d-%H%M%S')}"
        shutil.move(str(src), str(dest))
        self.reload()

    def import_vendor(self):
        start = r"C:\SmartMonitor" if os.path.isdir(r"C:\SmartMonitor") else str(Path.home())
        folder = QFileDialog.getExistingDirectory(
            self, "Dossier « themefor3.5 » du logiciel d'origine (ou un dossier de thème)", start)
        if not folder:
            return
        root = Path(folder)
        candidates = [root] if find_ui(root) else [d for d in root.rglob("*") if d.is_dir() and find_ui(d)]
        count = 0
        for d in candidates:
            name = d.name.removeprefix("theme_")
            dest = settings.THEMES_DIR / name
            if dest.exists():
                continue
            shutil.copytree(d, dest, ignore=shutil.ignore_patterns("backup"))
            count += 1
        QMessageBox.information(self, "Import", f"{count} thème(s) importé(s)."
                                if count else "Aucun nouveau thème trouvé (fichiers .ui) dans ce dossier.")
        self.reload()

    def open_folder(self):
        if hasattr(os, "startfile"):
            os.startfile(settings.THEMES_DIR)  # noqa: S606


def migrate_variants(win):
    """Alert variants (… ORANGE / … ROUGE) live in themes/_variantes, hidden from the gallery."""
    var = settings.THEMES_DIR / "_variantes"
    moved = {}
    if not settings.THEMES_DIR.is_dir():
        return
    for d in list(settings.THEMES_DIR.iterdir()):
        if d.is_dir() and not d.name.startswith("_") and d.name.endswith((" ORANGE", " ROUGE")):
            var.mkdir(exist_ok=True)
            dest = var / d.name
            if not dest.exists():
                shutil.move(str(d), str(dest))
                for ui in dest.glob("*.ui"):
                    moved[str(d / ui.name)] = str(ui)
    if moved:
        a = win.cfg.get("alert", {})
        for k in ("normal", "warn_theme", "crit_theme"):
            if a.get(k) in moved:
                a[k] = moved[a[k]]
        settings.save(win.cfg)


# ================================================================ main window
class MainWindow(QMainWindow):
    def __init__(self, tray_mode: bool = False):
        super().__init__()
        self.setWindowTitle("SmartScreen Hélio — écran 3,5\"")
        self.setWindowIcon(QIcon(str(ICON)))
        self.resize(1320, 820)
        self.cfg = settings.load()
        self.bridge = Bridge()
        self.engine = Engine(on_status=self.bridge.status.emit)
        self.engine.interval = float(self.cfg.get("interval", 1.0))
        self.engine.preferred_screen = self.cfg.get("screen_type", "auto")
        self.worker: UploadWorker | None = None
        self._quitting = False

        # l'écran est servi tout de suite, avant de construire l'interface
        active = self.cfg.get("active_theme")
        if active and Path(active).is_file():
            try:
                self.engine.set_theme(active)
            except Exception:
                pass
        self.engine.alert = dict(self.cfg.get("alert", {}))
        self.engine.start()

        self.tabs = QTabWidget()
        migrate_variants(self)
        self.screen_tab = ScreenTab(self)
        self.gallery = GalleryTab(self)
        self.editor = EditorTab()
        self.editor.send_requested.connect(self.send_theme)
        self.editor.saved.connect(lambda p: self.gallery.reload(select=p))
        self.tabs.addTab(self.screen_tab, "Écran")
        self.tabs.addTab(self.gallery, "Thèmes")
        self.tabs.addTab(self.editor, "Éditeur")
        self.setCentralWidget(self.tabs)
        self.tabs.currentChanged.connect(self._on_tab)
        self.statusBar().showMessage("Prêt")
        self.bridge.status.connect(self._on_status)
        self.bridge.theme_changed.connect(self._on_theme_changed)
        self.engine.on_theme_changed = self.bridge.theme_changed.emit
        self.bridge.progress.connect(self._on_progress)

        self._make_tray()


        if settings.vendor_app_running():
            QTimer.singleShot(800, lambda: QMessageBox.warning(
                self, "Logiciel d'origine ouvert",
                "Le logiciel « 3.5 Inch SmartMonitor » est encore lancé.\n"
                "Ferme-le (icône près de l'horloge → Quitter), sinon les deux logiciels se disputent l'écran."))

    # ------------------------------------------------------------------ tray
    def _make_tray(self):
        self.tray = QSystemTrayIcon(QIcon(str(ICON)), self)
        menu = QMenu()
        a_open = QAction("Ouvrir SmartScreen", self)
        a_open.triggered.connect(self.show_normal)
        a_resend = QAction("Renvoyer le thème actif", self)
        a_resend.triggered.connect(self.screen_tab.resend)
        a_quit = QAction("Quitter", self)
        a_quit.triggered.connect(self.quit)
        for a in (a_open, a_resend):
            menu.addAction(a)
        menu.addSeparator()
        menu.addAction(a_quit)
        self.tray.setContextMenu(menu)
        self.tray.setToolTip("SmartScreen Hélio")
        self.tray.activated.connect(lambda r: self.show_normal() if r == QSystemTrayIcon.Trigger else None)
        self.tray.show()

    def show_normal(self):
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        """Croix = fermeture complète du logiciel."""
        if self._quitting:
            event.accept()
            return
        if self.editor.dirty and not self.editor._confirm_discard():
            event.ignore()
            return
        self._quitting = True
        self.engine.stop()
        self.tray.hide()
        event.accept()
        QApplication.quit()

    def changeEvent(self, event):
        """Réduire = la fenêtre se range près de l'horloge."""
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.WindowStateChange and self.isMinimized() \
                and QSystemTrayIcon.isSystemTrayAvailable():
            QTimer.singleShot(0, self.hide)
            self.tray.showMessage("SmartScreen Hélio", "Toujours actif près de l'horloge.",
                                  QSystemTrayIcon.Information, 2000)
        super().changeEvent(event)

    def quit(self):
        if self.editor.dirty and not self.editor._confirm_discard():
            return
        self._quitting = True
        self.engine.stop()
        self.tray.hide()
        QApplication.quit()

    # --------------------------------------------------------------- upload
    def send_theme(self, ui_path: str):
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "Envoi", "Un envoi est déjà en cours.")
            return
        if settings.vendor_app_running():
            QMessageBox.warning(self, "Envoi", "Ferme d'abord le logiciel « 3.5 Inch SmartMonitor ».")
            return
        self.screen_tab.progress.setVisible(True)
        self.screen_tab.progress.setValue(0)
        self.tabs.setCurrentWidget(self.screen_tab)
        self.statusBar().showMessage(f"Envoi de « {Path(ui_path).stem} »… (ne pas débrancher l'écran)")
        self.screen_tab.use_as_normal(str(ui_path))
        eng = self.engine
        a = self.cfg.get("alert", {})
        t = eng.last_alert_temp
        if a.get("enabled") and t is not None and str(ui_path) == a.get("normal"):
            # déjà chaud : on envoie directement la bonne couleur (un seul envoi, pas deux)
            level = eng.alert_level_for(t, eng._alert_level)
            pick = [a.get("normal"), a.get("warn_theme"), a.get("crit_theme")][level]
            if pick and Path(pick).is_file():
                ui_path = pick
                eng._alert_level = level
        eng._alert_candidate = (eng._alert_level, time.monotonic())
        self.worker = UploadWorker(self.engine, ui_path, self.bridge)
        self.worker.done.connect(self._upload_done)
        self.worker.start()

    def _on_tab(self, _i: int):
        """Éditeur vide : on ouvre directement le thème affiché sur l'écran (version normale, pas orange/rouge)."""
        if self.tabs.currentWidget() is not self.editor or self.editor.bundle is not None:
            return
        a = self.cfg.get("alert", {})
        for ui in (a.get("normal") if a.get("enabled") else None, self.cfg.get("active_theme")):
            if ui and Path(ui).is_file():
                try:
                    self.editor.load(ui)
                except Exception:
                    continue
                break

    def _upload_done(self, ok: bool, info: str):
        self.screen_tab.progress.setVisible(False)
        if ok:
            self.cfg["active_theme"] = info
            settings.save(self.cfg)
            self.engine.start()
            self.statusBar().showMessage(f"Thème « {Path(info).stem} » envoyé.", 8000)
            self.gallery.reload(select=info)
        else:
            self.statusBar().showMessage("Échec de l'envoi.", 8000)
            QMessageBox.warning(self, "Envoi du thème", f"L'envoi a échoué :\n{info}\n\n"
                                "Débranche/rebranche l'écran puis réessaie.")
        self.screen_tab.refresh()

    def _on_theme_changed(self, path: str):
        self.cfg["active_theme"] = path
        settings.save(self.cfg)
        self.gallery.reload(select=path)
        self.screen_tab.refresh()

    def _on_progress(self, i: int, n: int):
        self.screen_tab.progress.setMaximum(n)
        self.screen_tab.progress.setValue(i)

    def _on_status(self, msg: str):
        try:
            self.statusBar().showMessage(msg, 10000)
            if hasattr(self, "screen_tab"):
                self.screen_tab.lbl_status.setText(msg)
        except RuntimeError:  # fenêtre déjà détruite (fermeture)
            pass
