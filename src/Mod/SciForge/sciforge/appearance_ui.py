# SPDX-License-Identifier: LGPL-2.1-or-later
"""Appearance (Modify > Appearance) with a Fusion-like dialog:

  Apply To       Bodies / Faces
  In This Design the looks the design already uses (click one to pick it again)
  Library        metals, glossy and matte plastics in several colours, rubber, glass, wood
  Custom         any colour: type #RRGGBB or move the R / G / B sliders

Pick a look (a swatch), then click bodies (or faces) in the 3D view: each click gives it
that look at once. Bodies or faces selected before the command get the first look picked.
OK keeps all of it as one undo step, Cancel / Esc puts every look back. A face keeps its
look through later steps while it is still there. The document side is appearance.py.
"""
import FreeCAD as App

from . import appearance, bodies, bodies_gui, ui_icon_path, warn
from .bodies_panel import BodyPanel, start as _start
from .compat import QtCore, QtGui, QtWidgets

APPLY_TO = [("Bodies", "bodies"), ("Faces", "faces")]
SWATCH = 28


def swatch_icon(look):
    pixmap = QtGui.QPixmap(SWATCH, SWATCH)
    r, g, b = [int(round(c * 255)) for c in look["color"]]
    pixmap.fill(QtGui.QColor(r, g, b))
    painter = QtGui.QPainter(pixmap)
    try:
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        shine = float(look.get("shininess", 0.5))
        if shine > 0.3:  # a highlight, brighter for shinier looks
            light = QtGui.QColor(255, 255, 255, int(60 + 120 * shine))
            painter.setBrush(light)
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawEllipse(SWATCH // 5, SWATCH // 6, SWATCH // 3, SWATCH // 4)
        if look.get("transparency", 0.0) > 0.2:
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 160), 1))
            painter.drawLine(0, SWATCH, SWATCH, 0)
        painter.setPen(QtGui.QPen(QtGui.QColor("#1b1f24"), 1))
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawRect(0, 0, SWATCH - 1, SWATCH - 1)
    finally:
        painter.end()
    return QtGui.QIcon(pixmap)


class _EnterTakes(QtCore.QObject):
    """Event filter: Enter / Return in a field runs `action` and goes no further."""

    def __init__(self, action):
        super().__init__()
        self.action = action

    def eventFilter(self, obj, event):
        try:
            if event.type() == QtCore.QEvent.KeyPress and event.key() in (
                QtCore.Qt.Key_Return,
                QtCore.Qt.Key_Enter,
            ):
                self.action()
                return True
        except Exception as exc:
            warn("colour field: %s" % exc)
        return False


MIME = "application/x-sciforge-look"


def look_of(mime):
    """The look carried by a drag (a swatch of the Appearance dialog), or None."""
    import json

    try:
        if mime is None or not mime.hasFormat(MIME):
            return None
        return json.loads(bytes(mime.data(MIME)).decode("utf-8"))
    except Exception:
        return None


def mime_of(look):
    import json

    mime = QtCore.QMimeData()
    mime.setData(MIME, QtCore.QByteArray(json.dumps(look).encode("utf-8")))
    return mime


class _SwatchList(QtWidgets.QListWidget):
    """Swatches; dragging one carries its look (drop it on a body or a face)."""

    def mimeTypes(self):
        return [MIME]

    def mimeData(self, items):
        look = items[0].data(QtCore.Qt.UserRole) if items else None
        return mime_of(dict(look)) if look else QtCore.QMimeData()


class _DropTaker(QtCore.QObject):
    """Event filter on the 3D view's drawing widget: accepts a swatch dragged from the
    Appearance dialog and hands the drop to the dialog."""

    def __init__(self, panel):
        super().__init__()
        self.panel = panel

    def eventFilter(self, obj, event):
        try:
            kind = event.type()
            if kind not in (QtCore.QEvent.DragEnter, QtCore.QEvent.DragMove, QtCore.QEvent.Drop):
                return False
            panel = self.panel
            if panel is None or panel._closed:
                return False
            look = look_of(event.mimeData())
            if look is None:
                return False
            if kind == QtCore.QEvent.Drop:
                position = event.position().toPoint()
                QtCore.QTimer.singleShot(
                    0, lambda: panel._guarded(lambda: panel.dropped(look, position))
                )
            event.setDropAction(QtCore.Qt.CopyAction)
            event.accept()
            return True
        except Exception as exc:
            warn("appearance drop: %s" % exc)
            return False


def _gl_widget():
    import FreeCADGui as Gui

    area = Gui.getMainWindow().findChild(QtWidgets.QMdiArea)
    if area is None:
        return None
    sub = area.activeSubWindow() or (area.subWindowList() or [None])[-1]
    if sub is None:
        return None
    for widget in sub.findChildren(QtWidgets.QWidget):
        if widget.metaObject().className() == "QOpenGLWidget":
            return widget
    return None


class AppearancePanel(BodyPanel):
    title = "Appearance"
    icon = "appearance"
    needs_pick = ()

    def __init__(self, doc):
        self.look = None
        self.pending = []  # selection made before the command, waiting for the first look
        super().__init__(doc, "Appearance")
        self.pending = [(o, s) for o, s, _p in bodies_gui.selection_entries() if o.Document is doc]
        bodies_gui.clear_selection()
        if self.pending and any(s.startswith("Face") for _o, s in self.pending):
            from . import hole_common

            hole_common.set_combo(self.apply_to, "faces")
        self._fill_design()
        self._drop_widget = None
        self._install_drop()
        self.info.setText(
            "Pick a look, then click bodies (or faces) to give them that look (or drag it "
            "onto them)."
            if not self.pending
            else "Pick a look for the selection."
        )

    # -- form --------------------------------------------------------------------------------------
    def build_form(self):
        self.apply_to, _ = self.combo("Apply To", APPLY_TO, "bodies", self._apply_to_changed)
        self.layout.addRow(QtWidgets.QLabel("<b>In This Design</b>"))
        self.design = self._list(rows=1)
        self.layout.addRow(self.design)
        self.layout.addRow(QtWidgets.QLabel("<b>Library</b>"))
        self.library = self._list(rows=4)
        for look in appearance.library():
            self._add(self.library, look)
        self.layout.addRow(self.library)
        self.layout.addRow(QtWidgets.QLabel("<b>Custom</b>"))
        row = QtWidgets.QWidget()
        line = QtWidgets.QHBoxLayout(row)
        line.setContentsMargins(0, 0, 0, 0)
        self.hex = QtWidgets.QLineEdit("#808080")
        self.hex.setMaxLength(7)
        self.hex.setToolTip("Type a colour as #RRGGBB, then Enter")
        self.hex.editingFinished.connect(lambda: self._guarded(self._hex_typed))
        # Enter in the colour field takes the colour; it must not reach the task panel,
        # which would take it as OK and close the dialog.
        self._enter_filter = _EnterTakes(lambda: self._guarded(self._hex_typed))
        self.hex.installEventFilter(self._enter_filter)
        self.preview_swatch = QtWidgets.QLabel()
        self.preview_swatch.setFixedSize(SWATCH, SWATCH)
        self.use_custom = QtWidgets.QPushButton("Use")
        self.use_custom.setToolTip("Pick this colour as the look")
        self.use_custom.clicked.connect(lambda *_: self._guarded(self._custom_picked))
        line.addWidget(self.preview_swatch)
        line.addWidget(self.hex, 1)
        line.addWidget(self.use_custom)
        self.layout.addRow("Colour", row)
        self.sliders = []
        for name in ("R", "G", "B"):
            slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            slider.setRange(0, 255)
            slider.setValue(128)
            slider.valueChanged.connect(lambda *_: self._guarded(self._slid))
            self.layout.addRow(name, slider)
            self.sliders.append(slider)
        self._paint_custom()
        self.chosen = QtWidgets.QLabel("")
        self.chosen.setStyleSheet("color: #b8c7d9;")
        self.layout.addRow("Look", self.chosen)

    def _list(self, rows):
        view = _SwatchList()
        view.setViewMode(QtWidgets.QListView.IconMode)
        view.setIconSize(QtCore.QSize(SWATCH, SWATCH))
        view.setGridSize(QtCore.QSize(SWATCH + 14, SWATCH + 14))
        view.setResizeMode(QtWidgets.QListView.Adjust)
        view.setMovement(QtWidgets.QListView.Static)
        view.setFixedHeight(rows * (SWATCH + 14) + 8)
        view.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        view.itemClicked.connect(lambda item: self._guarded(lambda: self._swatch_clicked(item)))
        view.setDragEnabled(True)  # Fusion: drag a look onto a body or a face
        view.setDragDropMode(QtWidgets.QAbstractItemView.DragOnly)
        return view

    def _add(self, view, look):
        item = QtWidgets.QListWidgetItem(swatch_icon(look), "")
        item.setToolTip(look["label"])
        item.setData(QtCore.Qt.UserRole, look)
        view.addItem(item)
        return item

    def _fill_design(self):
        self.design.clear()
        for look, used in appearance.looks_in_design(self.doc):
            item = self._add(self.design, look)
            item.setToolTip("%s (%s)" % (look["label"], bodies_gui.body_text(used)))

    def items(self, view=None):
        view = view or self.library
        return [view.item(i) for i in range(view.count())]

    def item_for(self, label):
        """The library swatch with this name (tests)."""
        for item in self.items():
            if item.data(QtCore.Qt.UserRole)["label"] == label:
                return item
        return None

    # -- picking a look --------------------------------------------------------------------------
    def _swatch_clicked(self, item):
        look = item.data(QtCore.Qt.UserRole)
        if look:
            self._choose(dict(look))

    def _choose(self, look):
        self.look = look
        self.chosen.setText(look["label"])
        self.info.setText("Click bodies (or faces) to give them this look.")
        if self.pending:
            pending, self.pending = self.pending, []
            for obj, short in pending:
                self._give(obj, short)

    def _rgb(self):
        return [s.value() / 255.0 for s in self.sliders]

    def _paint_custom(self):
        r, g, b = [int(round(c * 255)) for c in self._rgb()]
        pixmap = QtGui.QPixmap(SWATCH, SWATCH)
        pixmap.fill(QtGui.QColor(r, g, b))
        self.preview_swatch.setPixmap(pixmap)

    def _slid(self):
        r, g, b = [int(round(c * 255)) for c in self._rgb()]
        self.hex.blockSignals(True)
        self.hex.setText("#%02X%02X%02X" % (r, g, b))
        self.hex.blockSignals(False)
        self._paint_custom()

    def _hex_typed(self):
        text = self.hex.text().strip().lstrip("#")
        try:
            if len(text) != 6:
                raise ValueError
            values = [int(text[i : i + 2], 16) for i in (0, 2, 4)]
        except ValueError:
            self.message.setText("⚠ Type a colour as #RRGGBB (for example #3366CC).")
            return
        self.message.setText("")
        self._quiet = True
        try:
            for slider, value in zip(self.sliders, values):
                slider.setValue(value)
        finally:
            self._quiet = False
        self._paint_custom()

    def _custom_picked(self):
        self._choose(appearance.custom(self._rgb()))

    def _apply_to_changed(self):
        pass

    # -- clicks ------------------------------------------------------------------------------------
    def picked(self, obj, short, point):
        if self.look is None:
            self.pending.append((obj, short))
            self.message.setText("Pick a look first (a swatch), then click.")
            return
        self.message.setText("")
        self._give(obj, short)

    def _give(self, obj, short):
        body = bodies.body_of(obj)
        if body is None:
            return
        faces_mode = self.apply_to.currentData() == "faces"
        if faces_mode and short.startswith("Face"):
            feature = obj if not bodies.is_body(obj) else body.Tip
            if feature is not body.Tip:  # a face of an earlier step: the body as it is now
                from . import profile_pick

                face = profile_pick.global_face(obj, short)
                name = profile_pick.face_name_in(body.Tip, face) if face is not None else None
                if not name:
                    return
                feature, short = body.Tip, name
            appearance.set_faces(body, feature, [short], self.look)
        else:
            appearance.set_body(body, self.look)
        appearance.apply(body)
        self._fill_design()
        self.note.setText("%s: %s" % (body.Label, self.look["label"]))

    def can_finish(self):
        return ""

    # -- drag and drop -------------------------------------------------------------------------------
    def _install_drop(self):
        """The 3D view takes a swatch dropped on it (Fusion drags looks onto the part)."""
        try:
            widget = _gl_widget()
            if widget is None:
                return
            self._drop_widget = widget
            self._drop_filter = _DropTaker(self)
            self._drop_accepted = widget.acceptDrops()
            widget.setAcceptDrops(True)
            widget.installEventFilter(self._drop_filter)
        except Exception as exc:
            warn("appearance drag and drop unavailable: %s" % exc)

    def remove_handles(self):
        widget = getattr(self, "_drop_widget", None)
        if widget is not None:
            try:
                widget.removeEventFilter(self._drop_filter)
                widget.setAcceptDrops(self._drop_accepted)
            except Exception:
                pass
            self._drop_widget = None

    def dropped(self, look, position):
        """A swatch dropped at widget pixel `position`: the body or face there takes it."""
        widget = self._drop_widget
        if widget is None:
            return False
        ratio = widget.devicePixelRatioF()
        info = self.view.getObjectInfo(
            (position.x() * ratio, (widget.height() - position.y()) * ratio)
        )
        if not info or not info.get("Object"):
            self.message.setText("Drop the look on a body or a face.")
            return False
        obj = self.doc.getObject(info["Object"])
        if obj is None:
            return False
        from . import hole_common

        obj, short = hole_common.resolve(obj, info.get("Component", "") or "")
        self._choose(look)
        self._give(obj, short)
        return True

    def after_close(self, ok):
        super().after_close(ok)
        try:
            appearance.sync(self.doc)
        except Exception as exc:
            warn("appearance: %s" % exc)


class AppearanceCommand:
    def GetResources(self):
        return {
            "MenuText": "Appearance",
            "ToolTip": "Give bodies or faces a look: metals, plastics, rubber, glass or any "
            "colour",
            "Pixmap": ui_icon_path("appearance"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            _start(AppearancePanel)
        except Exception as exc:
            warn("Appearance could not start: %s" % exc)


COMMANDS = {"SciForge_Appearance": AppearanceCommand}
