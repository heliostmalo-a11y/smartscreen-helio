"""Drag & drop theme editor (480 x 320 canvas)."""
from __future__ import annotations

import copy
from pathlib import Path

from PIL.ImageQt import ImageQt
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QFont, QKeySequence, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QFileDialog, QFontComboBox, QFormLayout,
                               QGraphicsItem, QGraphicsObject, QGraphicsScene, QGraphicsView, QGroupBox,
                               QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton,
                               QSpinBox, QToolBar, QVBoxLayout, QWidget)

from core import aida64
from core.model import (H, T_BAR, T_DATETIME, T_IMAGE, T_TEXT, T_VALUE, TYPE_LABELS, W, argb, import_image,
                        load_bundle, new_theme, new_widget, rgb_hex, save_bundle, set_background)
from core.preview import background_image
from core.sensors import AIDA_TYPE, PRESETS
from core.settings import THEMES_DIR
from core.smartmonitor.ui import resolve_theme_path

HANDLE = 7
DATE_FORMATS = ["hh:nn:ss", "hh:nn", "dd-mm-yyyy", "yyyy-mm-dd"]
ALIGNS = [("Gauche", 0), ("Centre", 1), ("Droite", 2)]


def _qcolor(value: int) -> QColor:
    return QColor(f"#{value & 0xFFFFFF:06x}")


class WidgetItem(QGraphicsObject):
    changed = Signal()

    def __init__(self, widget, base_dir: str):
        super().__init__()
        self.w = widget
        self.base_dir = base_dir
        self._resizing = False
        self._pix: QPixmap | None = None
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable
                      | QGraphicsItem.ItemSendsGeometryChanges)
        self.setPos(widget.geometry.x, widget.geometry.y)
        self._load_image()

    def _load_image(self):
        self._pix = None
        if self.w.widget_type == T_IMAGE:
            p = resolve_theme_path(self.base_dir, str(self.w.raw_fields.get("imagePath", "")))
            if p.is_file():
                self._pix = QPixmap(str(p))

    # geometry ---------------------------------------------------------------
    def boundingRect(self) -> QRectF:
        g = self.w.geometry
        return QRectF(0, 0, max(4, g.width), max(4, g.height))

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            g = self.w.geometry
            x = int(round(max(0, min(W - 4, value.x()))))
            y = int(round(max(0, min(H - 4, value.y()))))
            return QPointF(x, y)
        if change == QGraphicsItem.ItemPositionHasChanged:
            self.w.geometry.x, self.w.geometry.y = int(self.pos().x()), int(self.pos().y())
            self.changed.emit()
        return super().itemChange(change, value)

    def _in_handle(self, pos) -> bool:
        r = self.boundingRect()
        return pos.x() >= r.width() - HANDLE and pos.y() >= r.height() - HANDLE

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.isSelected() and self._in_handle(event.pos()):
            self._resizing = True
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing:
            self.prepareGeometryChange()
            g = self.w.geometry
            g.width = int(max(6, min(W - g.x, event.pos().x())))
            g.height = int(max(6, min(H - g.y, event.pos().y())))
            self.update()
            self.changed.emit()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._resizing = False
        super().mouseReleaseEvent(event)

    def hoverMoveEvent(self, event):
        self.setCursor(Qt.SizeFDiagCursor if self._in_handle(event.pos()) else Qt.SizeAllCursor)

    # painting ---------------------------------------------------------------
    def _font(self) -> QFont:
        f = self.w.font
        qf = QFont(f.name or "Arial")
        qf.setPixelSize(max(6, round((f.size or 12) * 96 / 72)))
        qf.setBold(bool(f.bold))
        qf.setItalic(bool(f.italic))
        return qf

    def paint(self, painter: QPainter, option, widget=None):
        r = self.boundingRect()
        w = self.w
        if w.widget_type == T_BAR:
            st = w.style
            painter.setPen(QPen(_qcolor(st.frame_color if st else 0x606060), 1))
            painter.setBrush(QBrush(_qcolor(st.bg_color if st else 0x303030)))
            painter.drawRect(r.adjusted(0, 0, -1, -1))
            painter.fillRect(QRectF(1, 1, (r.width() - 2) * 0.6, r.height() - 2),
                             _qcolor(st.fg_color if st else 0x00c8ff))
        elif w.widget_type == T_IMAGE:
            if self._pix:
                painter.drawPixmap(r.toRect(), self._pix)
            else:
                painter.fillRect(r, QColor(80, 80, 80, 120))
                painter.drawText(r, Qt.AlignCenter, "Image")
        elif w.font is not None:
            painter.setFont(self._font())
            painter.setPen(_qcolor(w.font.color))
            if w.widget_type == T_VALUE:
                text = w.font.text or "42"
            elif w.widget_type == T_DATETIME:
                fmt = (w.datetime_format or "hh:nn:ss").strip()
                text = "12:34:56" if fmt == "hh:nn:ss" else "12:34" if fmt == "hh:nn" else ("09-10-2026" if fmt.startswith("dd") else "2026-10-09")
            else:
                text = w.font.text
            align = int(w.raw_fields.get("hAlign", 0) or 0)
            flags = Qt.AlignTop | ([Qt.AlignLeft, Qt.AlignHCenter, Qt.AlignRight][align] if align in (0, 1, 2)
                                   and w.widget_type != T_TEXT else Qt.AlignLeft)
            painter.drawText(r, flags, text)
        if self.isSelected():
            painter.setPen(QPen(QColor("#ffcc00"), 0, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(r.adjusted(0, 0, -1, -1))
            painter.fillRect(QRectF(r.width() - HANDLE, r.height() - HANDLE, HANDLE, HANDLE), QColor("#ffcc00"))
        else:
            painter.setPen(QPen(QColor(255, 255, 255, 40), 0, Qt.DotLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(r.adjusted(0, 0, -1, -1))


class Canvas(QGraphicsView):
    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setBackgroundBrush(QColor("#1e1e1e"))
        self.zoom = 2.0
        self.scale(self.zoom, self.zoom)
        self.setFixedSize(int(W * self.zoom) + 4, int(H * self.zoom) + 4)

    def keyPressEvent(self, event):
        step = 10 if event.modifiers() & Qt.ShiftModifier else 1
        dx = {Qt.Key_Left: -step, Qt.Key_Right: step}.get(event.key(), 0)
        dy = {Qt.Key_Up: -step, Qt.Key_Down: step}.get(event.key(), 0)
        if dx or dy:
            for it in self.scene().selectedItems():
                it.moveBy(dx, dy)
            event.accept()
            return
        super().keyPressEvent(event)


class EditorTab(QWidget):
    send_requested = Signal(str)      # ui path
    saved = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.bundle = None
        self.items: list[WidgetItem] = []
        self.dirty = False
        self._loading = False

        self.scene = QGraphicsScene(0, 0, W, H)
        self.scene.selectionChanged.connect(self._on_selection)
        self.bg_item = self.scene.addPixmap(QPixmap())
        self.bg_item.setZValue(-10)
        self.view = Canvas(self.scene)

        self.title = QLabel("Aucun thème ouvert")
        self.title.setStyleSheet("font-size:15px;font-weight:600")
        tb = QToolBar()
        self._act(tb, "Nouveau", self.new_theme)
        self._act(tb, "Enregistrer", self.save, QKeySequence.Save)
        self._act(tb, "Enregistrer sous…", self.save_as)
        tb.addSeparator()
        self._act(tb, "Fond : image…", self.pick_background)
        self._act(tb, "Fond : animation (GIF)…", self.pick_background_gif)
        self._act(tb, "Fond : couleur…", self.pick_background_color)
        tb.addSeparator()
        for label, kind in (("+ Valeur", T_VALUE), ("+ Texte", T_TEXT), ("+ Heure", "time"), ("+ Date", "date"),
                            ("+ Barre", T_BAR), ("+ Image", T_IMAGE)):
            self._act(tb, label, lambda _=False, k=kind: self.add(k))
        tb.addSeparator()
        self._act(tb, "Dupliquer", self.duplicate, QKeySequence("Ctrl+D"))
        self._act(tb, "Supprimer", self.delete_selected, QKeySequence.Delete)
        tb.addSeparator()
        send = self._act(tb, "▶ Envoyer à l'écran", self.send)
        send.setToolTip("Enregistre puis envoie ce thème au petit écran")

        # properties panel
        self.props = QGroupBox("Propriétés")
        self.form = QFormLayout(self.props)
        self.lbl_type = QLabel("-")
        self.sp = {k: QSpinBox() for k in ("x", "y", "w", "h")}
        for k, s in self.sp.items():
            s.setRange(0, W if k in ("x", "w") else H)
            s.valueChanged.connect(self._apply_geom)
        self.ed_text = QLineEdit()
        self.ed_text.textEdited.connect(self._apply_text)
        self.cb_sensor = QComboBox()
        self.cb_sensor.setEditable(True)
        self.cb_sensor.setMinimumWidth(260)
        self.cb_sensor.activated.connect(self._apply_sensor)
        self.cb_sensor.lineEdit().editingFinished.connect(self._apply_sensor)
        btn_refresh = QPushButton("↻ Rafraîchir les capteurs")
        btn_refresh.clicked.connect(self.refresh_sensors)
        self.cb_format = QComboBox()
        self.cb_format.addItems(DATE_FORMATS)
        self.cb_format.activated.connect(self._apply_format)
        self.cb_font = QFontComboBox()
        self.cb_font.currentFontChanged.connect(self._apply_font)
        self.sp_size = QSpinBox()
        self.sp_size.setRange(5, 96)
        self.sp_size.valueChanged.connect(self._apply_font)
        self.ck_bold = QCheckBox("Gras")
        self.ck_bold.toggled.connect(self._apply_font)
        self.btn_color = QPushButton("Couleur…")
        self.btn_color.clicked.connect(lambda: self._pick_color("font"))
        self.cb_align = QComboBox()
        for label, _ in ALIGNS:
            self.cb_align.addItem(label)
        self.cb_align.activated.connect(self._apply_align)
        self.btn_fg = QPushButton("Couleur barre…")
        self.btn_fg.clicked.connect(lambda: self._pick_color("fg"))
        self.btn_bg = QPushButton("Couleur fond…")
        self.btn_bg.clicked.connect(lambda: self._pick_color("bg"))
        self.btn_frame = QPushButton("Couleur cadre…")
        self.btn_frame.clicked.connect(lambda: self._pick_color("frame"))
        self.btn_img = QPushButton("Choisir l'image…")
        self.btn_img.clicked.connect(self._pick_widget_image)

        self.rows = {}
        for key, label, widget in (
                ("type", "Élément", self.lbl_type), ("x", "X", self.sp["x"]), ("y", "Y", self.sp["y"]),
                ("w", "Largeur", self.sp["w"]), ("h", "Hauteur", self.sp["h"]), ("text", "Texte", self.ed_text),
                ("sensor", "Capteur", self.cb_sensor), ("refresh", "", btn_refresh),
                ("format", "Format", self.cb_format), ("font", "Police", self.cb_font),
                ("size", "Taille (pt)", self.sp_size), ("bold", "", self.ck_bold), ("color", "", self.btn_color),
                ("align", "Alignement", self.cb_align), ("fg", "", self.btn_fg), ("bg", "", self.btn_bg),
                ("frame", "", self.btn_frame), ("img", "", self.btn_img)):
            self.form.addRow(label, widget)
            self.rows[key] = widget
        hint = QLabel("Astuces : glisser pour déplacer, carré jaune pour redimensionner, "
                      "flèches pour ajuster au pixel (Maj = 10 px).")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#888")
        self.form.addRow(hint)
        self._show_rows(None)
        self.refresh_sensors()

        right = QVBoxLayout()
        right.addWidget(self.props)
        right.addStretch()
        center = QHBoxLayout()
        left = QVBoxLayout()
        left.addWidget(self.view)
        left.addStretch()
        center.addLayout(left)
        center.addLayout(right)
        lay = QVBoxLayout(self)
        lay.addWidget(self.title)
        lay.addWidget(tb)
        lay.addLayout(center)

    def _act(self, tb, text, slot, shortcut=None):
        a = QAction(text, self)
        a.triggered.connect(slot)
        if shortcut:
            a.setShortcut(shortcut)
            a.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        tb.addAction(a)
        return a

    # ------------------------------------------------------------- sensors
    def refresh_sensors(self):
        current = self.cb_sensor.currentText()
        self.cb_sensor.blockSignals(True)
        self.cb_sensor.clear()
        seen = set()
        try:
            live = aida64.read_sensors()
        except Exception:
            live = {}
        for sid, s in live.items():
            if s.number is None:
                continue
            self.cb_sensor.addItem(f"{s.label} = {s.raw}   [{sid}]", sid)
            seen.add(sid)
        for sid, label in PRESETS:
            if sid not in seen:
                self.cb_sensor.addItem(f"{label}   [{sid}]", sid)
        self.cb_sensor.setEditText(current)
        self.cb_sensor.blockSignals(False)

    def _sensor_id_from_combo(self) -> str:
        idx = self.cb_sensor.currentIndex()
        text = self.cb_sensor.currentText().strip()
        if idx >= 0 and self.cb_sensor.itemText(idx) == text:
            return self.cb_sensor.itemData(idx)
        if "[" in text and text.endswith("]"):
            return text[text.rindex("[") + 1:-1]
        return text

    # -------------------------------------------------------------- loading
    def load(self, ui_path: str | Path):
        if not self._confirm_discard():
            return
        self.bundle = load_bundle(ui_path)
        self._rebuild()
        self.dirty = False
        self._update_title()

    def _rebuild(self):
        self._loading = True
        for it in self.items:
            self.scene.removeItem(it)
        self.items = []
        self._refresh_background()
        for w in self.bundle.theme.widgets:
            self._add_item(w)
        self._loading = False
        self._show_rows(None)

    def _refresh_background(self):
        img = background_image(self.bundle)
        self.bg_item.setPixmap(QPixmap.fromImage(ImageQt(img.convert("RGBA"))))

    def _add_item(self, w) -> WidgetItem:
        it = WidgetItem(w, self.bundle.base_dir)
        it.setAcceptHoverEvents(True)
        it.changed.connect(self._item_changed)
        self.scene.addItem(it)
        self.items.append(it)
        return it

    def _update_title(self):
        if not self.bundle:
            self.title.setText("Aucun thème ouvert")
            return
        name = Path(self.bundle.ui_path).stem
        self.title.setText(f"Thème : {name}{' *' if self.dirty else ''}")

    def _mark(self):
        if not self._loading:
            self.dirty = True
            self._update_title()

    def _confirm_discard(self) -> bool:
        if not self.dirty:
            return True
        r = QMessageBox.question(self, "Thème modifié", "Enregistrer les modifications du thème en cours ?",
                                 QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if r == QMessageBox.Cancel:
            return False
        if r == QMessageBox.Save:
            self.save()
        return True

    # --------------------------------------------------------------- actions
    def new_theme(self):
        if not self._confirm_discard():
            return
        name, ok = QInputDialog.getText(self, "Nouveau thème", "Nom du thème :")
        name = (name or "").strip()
        if not ok or not name:
            return
        safe = "".join(c for c in name if c not in '\\/:*?"<>|')
        d = THEMES_DIR / safe
        if d.exists():
            QMessageBox.warning(self, "Nouveau thème", "Un thème porte déjà ce nom.")
            return
        self.bundle = new_theme(d, safe, color="#101418")
        save_bundle(self.bundle, d / f"{safe}.ui")
        self._rebuild()
        self.dirty = False
        self._update_title()
        self.saved.emit(self.bundle.ui_path)

    def _need_bundle(self) -> bool:
        if self.bundle is None:
            QMessageBox.information(self, "Éditeur", "Ouvre un thème depuis la galerie, ou crée-en un nouveau.")
            return False
        return True

    def save(self):
        if not self._need_bundle():
            return
        save_bundle(self.bundle)
        self.dirty = False
        self._update_title()
        self.saved.emit(self.bundle.ui_path)

    def save_as(self):
        if not self._need_bundle():
            return
        name, ok = QInputDialog.getText(self, "Enregistrer sous", "Nom du nouveau thème :")
        name = "".join(c for c in (name or "").strip() if c not in '\\/:*?"<>|')
        if not ok or not name:
            return
        import shutil
        dest = THEMES_DIR / name
        if dest.exists():
            QMessageBox.warning(self, "Enregistrer sous", "Un thème porte déjà ce nom.")
            return
        shutil.copytree(self.bundle.base_dir, dest, ignore=shutil.ignore_patterns("*.ui", "backup"))
        save_bundle(self.bundle, dest / f"{name}.ui")
        self.bundle = load_bundle(dest / f"{name}.ui")
        self._rebuild()
        self.dirty = False
        self._update_title()
        self.saved.emit(self.bundle.ui_path)

    def send(self):
        if not self._need_bundle():
            return
        self.save()
        self.send_requested.emit(self.bundle.ui_path)

    def pick_background(self):
        if not self._need_bundle():
            return
        from core.settings import APP_DIR
        path, _ = QFileDialog.getOpenFileName(self, "Image de fond (recadrée en 480 × 320)",
                                              str(APP_DIR / "res" / "backgrounds"),
                                              "Images (*.png *.jpg *.jpeg *.bmp *.webp *.gif)")
        if not path:
            return
        parent = self.bundle.theme.widget_parents[0]
        parent.background_image_path = set_background(self.bundle.base_dir, path)
        parent.background_type = 1
        self._refresh_background()
        self._mark()

    def pick_background_gif(self):
        if not self._need_bundle():
            return
        from core.model import read_gif, set_background_frames
        path, _ = QFileDialog.getOpenFileName(self, "Animation de fond (GIF, 12 images max)", "",
                                              "Animations (*.gif *.webp *.png)")
        if not path:
            return
        frames, delay = read_gif(path)
        parent = self.bundle.theme.widget_parents[0]
        parent.background_image_path = set_background_frames(self.bundle.base_dir, frames)
        parent.background_type = 1
        parent.image_delay = delay
        self._refresh_background()
        self._mark()
        QMessageBox.information(self, "Animation", f"{len(frames)} images, {delay} ms entre chaque image.\n"
                                "L'envoi à l'écran sera plus long (environ 1 à 2 minutes).")

    def pick_background_color(self):
        if not self._need_bundle():
            return
        c = QColorDialog.getColor(QColor("#101418"), self, "Couleur de fond")
        if not c.isValid():
            return
        parent = self.bundle.theme.widget_parents[0]
        parent.background_image_path = set_background(self.bundle.base_dir, None, c.name())
        self._refresh_background()
        self._mark()

    def add(self, kind):
        if not self._need_bundle():
            return
        if kind == "time":
            w = new_widget(T_DATETIME, 160, 140, 160, 40, format="hh:nn:ss", size=22)
        elif kind == "date":
            w = new_widget(T_DATETIME, 160, 140, 160, 30, format="yyyy-mm-dd", size=14)
        elif kind == T_VALUE:
            w = new_widget(T_VALUE, 200, 140, 80, 40, sensor="SCPUUTI", size=22)
        elif kind == T_TEXT:
            w = new_widget(T_TEXT, 200, 140, 100, 30, text="Texte", size=14)
        elif kind == T_BAR:
            w = new_widget(T_BAR, 140, 150, 200, 14, sensor="SCPUUTI")
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Image ou GIF animé", "",
                                                  "Images (*.png *.jpg *.jpeg *.bmp *.gif)")
            if not path:
                return
            from PIL import Image
            with Image.open(path) as im:
                iw, ih = im.size
                animated = getattr(im, "n_frames", 1) > 1
            ratio = min(1.0, 160 / max(iw, ih))
            w = new_widget(T_IMAGE, 20, 20, max(8, int(iw * ratio)), max(8, int(ih * ratio)))
            if animated:
                from core.model import import_animated_image
                p0, _n, delay = import_animated_image(self.bundle.base_dir, path, w.geometry.width,
                                                      w.geometry.height)
                w.raw_fields["imagePath"] = p0
                w.raw_fields["imageDelay"] = str(delay)
            else:
                w.raw_fields["imagePath"] = import_image(self.bundle.base_dir, path, w.geometry.width,
                                                         w.geometry.height)
        self.bundle.theme.widgets.append(w)
        it = self._add_item(w)
        self.scene.clearSelection()
        it.setSelected(True)
        self._mark()

    def duplicate(self):
        for it in list(self.scene.selectedItems()):
            if isinstance(it, WidgetItem):
                w = copy.deepcopy(it.w)
                w.geometry.x = min(W - 10, w.geometry.x + 10)
                w.geometry.y = min(H - 10, w.geometry.y + 10)
                self.bundle.theme.widgets.append(w)
                self._add_item(w)
        self._mark()

    def delete_selected(self):
        for it in list(self.scene.selectedItems()):
            if isinstance(it, WidgetItem):
                self.bundle.theme.widgets.remove(it.w)
                self.items.remove(it)
                self.scene.removeItem(it)
        self._mark()

    # ----------------------------------------------------------- properties
    def _selected(self) -> WidgetItem | None:
        try:
            sel = [i for i in self.scene.selectedItems() if isinstance(i, WidgetItem)]
        except RuntimeError:  # scene already destroyed (application closing)
            return None
        return sel[0] if len(sel) == 1 else None

    def _show_rows(self, w):
        keys = set()
        if w is not None:
            keys = {"type", "x", "y", "w", "h"}
            t = w.widget_type
            if t in (T_TEXT, T_VALUE, T_DATETIME):
                keys |= {"font", "size", "bold", "color"}
            if t == T_TEXT:
                keys.add("text")
            if t in (T_VALUE, T_BAR):
                keys |= {"sensor", "refresh"}
            if t in (T_VALUE, T_DATETIME):
                keys.add("align")
            if t == T_DATETIME:
                keys.add("format")
            if t == T_BAR:
                keys |= {"fg", "bg", "frame"}
            if t == T_IMAGE:
                keys.add("img")
        for k, widget in self.rows.items():
            visible = k in keys
            widget.setVisible(visible)
            label = self.form.labelForField(widget)
            if label:
                label.setVisible(visible)

    def _on_selection(self):
        it = self._selected()
        self._show_rows(it.w if it else None)
        if not it:
            return
        w = it.w
        self._loading = True
        self.lbl_type.setText(TYPE_LABELS.get(w.widget_type, str(w.widget_type)))
        for k, v in zip(("x", "y", "w", "h"), (w.geometry.x, w.geometry.y, w.geometry.width, w.geometry.height)):
            self.sp[k].setValue(v)
        if w.font:
            self.ed_text.setText(w.font.text)
            self.cb_font.setCurrentFont(QFont(w.font.name or "Arial"))
            self.sp_size.setValue(w.font.size or 12)
            self.ck_bold.setChecked(bool(w.font.bold))
            self.btn_color.setStyleSheet(f"background:{rgb_hex(w.font.color)}")
        if w.sensor:
            sid = w.sensor.reading_name if w.sensor.sensor_type_name == AIDA_TYPE else \
                f"{w.sensor.sensor_type_name}/{w.sensor.reading_name} (thème d'origine)"
            i = self.cb_sensor.findData(sid)
            if i >= 0:
                self.cb_sensor.setCurrentIndex(i)
            else:
                self.cb_sensor.setEditText(sid)
        if w.widget_type == T_DATETIME:
            fmt = (w.datetime_format or "").strip()
            self.cb_format.setCurrentIndex(DATE_FORMATS.index(fmt) if fmt in DATE_FORMATS else 0)
        align = int(w.raw_fields.get("hAlign", 1) or 0)
        self.cb_align.setCurrentIndex(align if align in (0, 1, 2) else 1)
        if w.style:
            self.btn_fg.setStyleSheet(f"background:{rgb_hex(w.style.fg_color)}")
            self.btn_bg.setStyleSheet(f"background:{rgb_hex(w.style.bg_color)}")
            self.btn_frame.setStyleSheet(f"background:{rgb_hex(w.style.frame_color)}")
        self._loading = False

    def _item_changed(self):
        it = self._selected()
        if it and not self._loading:
            self._loading = True
            g = it.w.geometry
            for k, v in zip(("x", "y", "w", "h"), (g.x, g.y, g.width, g.height)):
                self.sp[k].setValue(v)
            self._loading = False
        self._mark()

    def _apply_geom(self):
        it = self._selected()
        if not it or self._loading:
            return
        it.prepareGeometryChange()
        g = it.w.geometry
        g.width, g.height = self.sp["w"].value(), self.sp["h"].value()
        it.setPos(self.sp["x"].value(), self.sp["y"].value())
        it.update()
        self._mark()

    def _apply_text(self, text):
        it = self._selected()
        if it and it.w.font and not self._loading:
            it.w.font.text = text
            it.update()
            self._mark()

    def _apply_sensor(self, *_):
        it = self._selected()
        if not it or not it.w.sensor or self._loading:
            return
        sid = self._sensor_id_from_combo()
        if not sid or "(thème d'origine)" in sid:
            return
        s = it.w.sensor
        s.sensor_type_name = AIDA_TYPE
        s.sensor_name = AIDA_TYPE
        s.reading_name = sid
        self._mark()

    def _apply_format(self, *_):
        it = self._selected()
        if it and it.w.widget_type == T_DATETIME and not self._loading:
            fmt = self.cb_format.currentText()
            it.w.datetime_format = fmt
            it.w.font.text = "12:00:00" if "h" in fmt else "2026-01-01"
            it.update()
            self._mark()

    def _apply_font(self, *_):
        it = self._selected()
        if not it or not it.w.font or self._loading:
            return
        it.w.font.name = self.cb_font.currentFont().family()
        it.w.font.size = self.sp_size.value()
        it.w.font.bold = self.ck_bold.isChecked()
        it.w.font.bold_value = int(it.w.font.bold)
        it.update()
        self._mark()

    def _apply_align(self, *_):
        it = self._selected()
        if it and not self._loading:
            it.w.raw_fields["hAlign"] = str(ALIGNS[self.cb_align.currentIndex()][1])
            it.update()
            self._mark()

    def _pick_color(self, which: str):
        it = self._selected()
        if not it:
            return
        w = it.w
        cur = {"font": w.font.color if w.font else 0xffffff}.get(which)
        if which != "font" and w.style:
            cur = getattr(w.style, f"{which}_color")
        c = QColorDialog.getColor(_qcolor(cur or 0xffffff), self, "Couleur")
        if not c.isValid():
            return
        raw, val = argb(c.name())
        if which == "font":
            w.font.color_raw, w.font.color = raw, val
            if w.widget_type == T_DATETIME:
                w.raw_fields["fontColor"] = raw
        else:
            setattr(w.style, f"{which}_color_raw", raw)
            setattr(w.style, f"{which}_color", val)
        it.update()
        self._on_selection()
        self._mark()

    def _pick_widget_image(self):
        it = self._selected()
        if not it or it.w.widget_type != T_IMAGE:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Image", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if not path:
            return
        it.w.raw_fields["imagePath"] = import_image(self.bundle.base_dir, path, it.w.geometry.width,
                                                    it.w.geometry.height)
        it._load_image()
        it.update()
        self._mark()
