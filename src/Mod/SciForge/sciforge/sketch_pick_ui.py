# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sketch commands that work on curves you pick first: Mirror, Circular Pattern,
Rectangular Pattern, Sketch Scale, Move/Copy.

FreeCAD's versions do nothing when nothing is selected, and its Rectangular Pattern
opens a pop-up asking for rows and columns. Like in Fusion, the command now starts
anyway: click the curves (each click adds one), press Enter (or click the command
again), then the tool continues: FreeCAD's tool for the next pick (mirror line,
centre, base point), or, for Rectangular Pattern, a panel at the top of the sketch
panel with the quantity and spacing in both directions and a live preview.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, log, sketch_mode, ui_icon_path, warn
from .compat import QtCore, QtWidgets

_state = {"waiter": None, "box": None}


def selected_curves(sketch):
    from .sketch_tools_ui import selected_curves as picked

    return picked(sketch)


class _Waiter:
    """Waits for curves to be clicked; Enter (or the command again) continues."""

    def __init__(self, sketch, title, run):
        stop_waiting()
        _state["waiter"] = self
        self.sketch = sketch
        self.title = title
        self.run = run
        self._timer = QtCore.QTimer()
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._check)
        self._timer.start()
        commands.tell("%s: click the curves, then press Enter." % title)
        log("%s: click the curves, then press Enter" % title)

    def _check(self):
        if sketch_mode.editing_sketch() is not self.sketch:
            self.stop()

    def confirm(self):
        ids = selected_curves(self.sketch)
        if not ids:
            commands.tell("%s: click at least one curve first." % self.title)
            return
        self.stop()
        self.run(self.sketch, ids)

    def stop(self):
        try:
            self._timer.stop()
        except Exception:
            pass
        if _state["waiter"] is self:
            _state["waiter"] = None


def stop_waiting():
    waiter = _state["waiter"]
    if waiter is not None:
        waiter.stop()


def on_enter():
    """Enter pressed on the 3D view while sketching: continue a waiting command."""
    waiter = _state["waiter"]
    if waiter is None:
        return False
    try:
        waiter.confirm()
    except Exception as exc:
        warn("%s failed: %s" % (waiter.title, exc))
    return True


class _PickCommand:
    title = ""
    tip = ""
    icon = ""
    freecad = ""  # FreeCAD's command that continues with the picked curves

    def GetResources(self):
        res = {"MenuText": self.title, "ToolTip": self.tip}
        if self.icon:
            res["Pixmap"] = ui_icon_path(self.icon)
        return res

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            sketch = sketch_mode.editing_sketch()
            if sketch is None:
                commands.tell(
                    "%s works inside a sketch: click Create Sketch (or edit a sketch) first."
                    % self.title
                )
                return
            waiter = _state["waiter"]
            if waiter is not None and waiter.title == self.title:
                waiter.confirm()  # the command clicked again: go on
                return
            if not sketch.Geometry:
                commands.tell("%s: draw some curves first." % self.title)
                return
            ids = selected_curves(sketch)
            if ids:
                self.go(sketch, ids)
            else:
                _Waiter(sketch, self.title, self.go)
        except Exception as exc:
            warn("%s failed: %s" % (self.title, exc))

    def go(self, sketch, ids):
        _select(sketch, ids)
        Gui.runCommand(self.freecad)


def _select(sketch, ids):
    Gui.Selection.clearSelection()
    for index in ids:
        Gui.Selection.addSelection(sketch.Document.Name, sketch.Name, "Edge%d" % (index + 1))


class SketchMirror(_PickCommand):
    title = "Mirror"
    tip = "Mirror curves: click them, Enter, then click the mirror line"
    icon = "sk_mirror"
    freecad = "Sketcher_Symmetry"


class SketchCircularPattern(_PickCommand):
    title = "Circular Pattern"
    tip = "Copy curves around a centre: click them, Enter, then click the centre"
    icon = "sk_pattern_circ"
    freecad = "Sketcher_Rotate"


class SketchScale(_PickCommand):
    title = "Sketch Scale"
    tip = "Scale curves: click them, Enter, then the base point and the size"
    icon = "sk_scale"
    freecad = "Sketcher_Scale"


class SketchMove(_PickCommand):
    title = "Move/Copy"
    tip = "Move or copy curves: click them, Enter, then the base point and where to"
    icon = "sk_move"
    freecad = "Sketcher_Translate"


class SketchRectangularPattern(_PickCommand):
    title = "Rectangular Pattern"
    tip = "Copy curves in rows and columns: click them, Enter, then set quantity and spacing"
    icon = "sk_pattern_rect"

    def go(self, sketch, ids):
        session = sketch_mode.current()
        if session is None:
            return
        RectangularPatternBox(session, ids)


def _size(sketch, ids):
    """(width, height) of the picked curves' bounding box (for the default spacing)."""
    box = None
    for index in ids:
        try:
            b = sketch.Geometry[index].toShape().BoundBox
        except Exception:
            continue
        if box is None:
            box = b
        else:
            box.add(b)
    if box is None:
        return 10.0, 10.0
    return max(box.XLength, 1.0), max(box.YLength, 1.0)


class RectangularPatternBox(QtWidgets.QFrame):
    """Fusion's sketch Rectangular Pattern panel, shown at the top of the sketch panel:
    Quantity and Distance (spacing) for both directions, live preview, OK / Cancel."""

    def __init__(self, session, ids):
        from . import sketch_palette
        from .taskui import DistanceField

        panel = sketch_palette.sketch_panel()
        super().__init__(panel)
        close_box()
        _state["box"] = self
        self.session = session
        self.sketch = session.sketch
        self.doc = self.sketch.Document
        self.ids = list(ids)
        self.setObjectName("SciForgeRectangularPattern")
        self.setStyleSheet(sketch_palette.STYLE.replace("SciForgeSketchPalette", self.objectName()))
        width, height = _size(self.sketch, self.ids)
        layout = QtWidgets.QFormLayout(self)
        title = QtWidgets.QLabel("RECTANGULAR PATTERN")
        title.setProperty("role", "title")
        layout.addRow(title)
        layout.addRow(QtWidgets.QLabel("Objects: %d curve(s)" % len(self.ids)))
        self.count1 = self._spin(3)
        self.distance1 = DistanceField(round(width * 1.5, 2), on_change=self._changed)
        self.count2 = self._spin(1)
        self.distance2 = DistanceField(round(height * 1.5, 2), on_change=self._changed)
        layout.addRow("Quantity (X)", self.count1)
        layout.addRow("Distance (X)", self.distance1.widget)
        layout.addRow("Quantity (Y)", self.count2)
        layout.addRow("Distance (Y)", self.distance2.widget)
        self.message = QtWidgets.QLabel("")
        self.message.setStyleSheet("color: #ff8a80;")
        self.message.setWordWrap(True)
        layout.addRow(self.message)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(lambda: QtCore.QTimer.singleShot(0, self.accept))
        buttons.rejected.connect(lambda: QtCore.QTimer.singleShot(0, self.reject))
        layout.addRow(buttons)
        if panel is not None and panel.layout() is not None:
            panel.layout().insertWidget(0, self)
        self.show()
        self._open = False
        self._timer = QtCore.QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self._preview)
        Gui.Selection.clearSelection()
        self._preview()
        log("rectangular pattern: set quantity and spacing, then OK")

    def keyPressEvent(self, event):
        # Enter in a field updates the preview; it must not reach FreeCAD's sketch panel
        if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            self._timer.start()
            event.accept()
            return
        super().keyPressEvent(event)

    def _spin(self, value):
        box = QtWidgets.QSpinBox()
        box.setRange(1, 999)
        box.setValue(value)
        box.valueChanged.connect(self._changed)
        return box

    def _changed(self, *_):
        self._timer.start()

    def _preview(self):
        """Take the previous preview back and make the pattern again."""
        try:
            if self._open:
                self.doc.abortTransaction()
            self.doc.openTransaction("Rectangular Pattern")
            self._open = True
            nx, ny = self.count1.value(), self.count2.value()
            dx, dy = self.distance1.value(), self.distance2.value()
            if (nx > 1 or ny > 1) and abs(dx) < 1e-9:
                raise ValueError("Distance (X) must not be 0")
            if nx > 1 or ny > 1:
                # FreeCAD: "rows" go along the vector, "columns" along the vector turned
                # -90 degrees and scaled; so X copies are rows and +Y needs a minus sign
                self.sketch.addRectangularArray(
                    self.ids, App.Vector(dx, 0, 0), False, nx, ny, False, -dy / dx
                )
            self.sketch.solve()
            self.message.setText("")
        except Exception as exc:
            self.message.setText(str(exc))

    def accept(self):
        self._timer.stop()
        self._preview()
        if self.message.text():
            return  # stay open with the reason, like Fusion
        if self._open:
            self.doc.commitTransaction()
            self._open = False
        log("rectangular pattern done")
        self._close()

    def reject(self):
        self._timer.stop()
        if self._open:
            self.doc.abortTransaction()
            self._open = False
        self._close()

    def _close(self):
        if _state["box"] is self:
            _state["box"] = None
        try:
            self.hide()
            self.setParent(None)
            self.deleteLater()
        except Exception:
            pass


def settle_box():
    """The sketch closed under the panel (E, another command): keep what it shows,
    without touching its widgets (they went with FreeCAD's sketch panel)."""
    box = _state["box"]
    _state["box"] = None
    stop_waiting()
    if box is not None and box._open:
        try:
            box._timer.stop()
        except Exception:
            pass
        try:
            box.doc.commitTransaction()
        except Exception as exc:
            warn("rectangular pattern: %s" % exc)
        box._open = False


def close_box(accept=False):
    box = _state["box"]
    if box is not None:
        try:
            box.accept() if accept else box.reject()
        except Exception as exc:
            warn("rectangular pattern: %s" % exc)


COMMANDS = {
    "SciForge_SketchMirror": SketchMirror,
    "SciForge_SketchCircularPattern": SketchCircularPattern,
    "SciForge_SketchRectangularPattern": SketchRectangularPattern,
    "SciForge_SketchScale": SketchScale,
    "SciForge_SketchMove": SketchMove,
}
