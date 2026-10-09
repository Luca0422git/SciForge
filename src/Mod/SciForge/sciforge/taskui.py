# SPDX-License-Identifier: LGPL-2.1-or-later
"""Building blocks for SciForge's Fusion-style command dialogs.

- DistanceField: unit-aware number field (types "5", "5 mm", "0.2 in", "=width*2"),
  optionally bound to a property so expressions/parameters work like in FreeCAD.
- ArrowDragger: the arrow you drag in the 3D view to set a distance (Coin3D).
- Panel: a task-dialog base that wraps the edit in one undo step: OK keeps it,
  Cancel/Esc removes it again, like Fusion.
"""
import FreeCAD as App
import FreeCADGui as Gui

from . import log, warn
from .compat import QtCore, QtWidgets


class DistanceField:
    def __init__(self, value=0.0, unit="mm", on_change=None):
        self.widget = Gui.UiLoader().createWidget("Gui::QuantitySpinBox")
        self.widget.setProperty("unit", unit)
        self.widget.setProperty("minimum", -1e9)
        self.widget.setProperty("maximum", 1e9)
        self.widget.setProperty("rawValue", float(value))
        self._on_change = on_change
        self._quiet = False
        self.widget.valueChanged.connect(self._changed)

    def bind(self, obj, prop):
        """Bind to obj.prop so typed expressions (=Parameters.width) are stored on it."""
        try:
            self._binding = Gui.ExpressionBinding(self.widget).bind(obj, prop)
        except Exception as exc:
            warn("expression binding unavailable: %s" % exc)

    def value(self):
        return float(self.widget.property("rawValue"))

    def set_value(self, value):
        self._quiet = True
        try:
            self.widget.setProperty("rawValue", float(value))
        finally:
            self._quiet = False

    def _changed(self, *_):
        if not self._quiet and self._on_change:
            self._on_change(self.value())


class ArrowDragger:
    """A 1D drag handle at `origin` pointing along `direction` (both App.Vector).

    on_drag(distance) is called while dragging, on_release(distance) at the end."""

    def __init__(self, origin, direction, distance=0.0, size=8.0, on_drag=None, on_release=None):
        from pivy import coin

        self.coin = coin
        self.view = Gui.ActiveDocument.ActiveView
        self.root = coin.SoSeparator()
        place = coin.SoTransform()
        place.translation.setValue(origin.x, origin.y, origin.z)
        # SoTranslate1Dragger moves along its local X axis; turn X onto `direction`.
        rot = App.Rotation(App.Vector(1, 0, 0), direction)
        place.rotation.setValue(*rot.Q)
        scale = coin.SoScale()
        scale.scaleFactor.setValue(size, size, size)
        self.dragger = coin.SoTranslate1Dragger()
        self.size = size
        self.dragger.translation.setValue(distance / size, 0, 0)
        self.root.addChild(place)
        self.root.addChild(scale)
        self.root.addChild(self.dragger)
        self.on_drag = on_drag
        self.on_release = on_release
        self.dragger.addMotionCallback(self._motion)
        self.dragger.addFinishCallback(self._finish)
        self.view.getSceneGraph().addChild(self.root)

    def distance(self):
        return self.dragger.translation.getValue()[0] * self.size

    def set_distance(self, distance):
        self.dragger.translation.setValue(distance / self.size, 0, 0)

    def _motion(self, *_):
        if self.on_drag:
            try:
                self.on_drag(self.distance())
            except Exception as exc:
                warn("drag: %s" % exc)

    def _finish(self, *_):
        if self.on_release:
            try:
                self.on_release(self.distance())
            except Exception as exc:
                warn("drag: %s" % exc)

    def remove(self):
        try:
            self.view.getSceneGraph().removeChild(self.root)
        except Exception:
            pass


class Panel:
    """Base for SciForge task dialogs. Subclasses fill self.layout and implement apply()."""

    title = "SciForge"
    icon = None

    def __init__(self, doc, transaction):
        from . import ui_icon

        self.doc = doc
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle(self.title)
        if self.icon:
            self.form.setWindowIcon(ui_icon(self.icon))
        self.layout = QtWidgets.QFormLayout(self.form)
        self.message = QtWidgets.QLabel("")
        self.message.setWordWrap(True)
        self.message.setStyleSheet("color: #ff8a80;")
        self._timer = QtCore.QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(60)  # coalesce rapid changes (dragging) into one recompute
        self._timer.timeout.connect(self._recompute)
        doc.openTransaction(transaction)
        self._closed = False

    def finish_layout(self):
        self.layout.addRow(self.message)

    # -- live preview ---------------------------------------------------------
    def schedule(self):
        self._timer.start()

    def _recompute(self):
        try:
            self.doc.recompute()
            self.show_status()
        except Exception as exc:
            self.message.setText(str(exc))

    def feature(self):
        """The feature whose state the dialog reports (override)."""
        return None

    def show_status(self):
        obj = self.feature()
        if obj is None:
            return
        state = list(getattr(obj, "State", []))
        if "Invalid" in state or "Error" in state:
            text = obj.getStatusString() if hasattr(obj, "getStatusString") else "Invalid result"
            self.message.setText("⚠ " + text)
        else:
            self.message.setText("")

    # -- task dialog API --------------------------------------------------------
    def getStandardButtons(self):
        buttons = QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        return getattr(buttons, "value", buttons)  # PySide6 enums need .value

    def accept(self):
        self._timer.stop()
        self.doc.recompute()
        obj = self.feature()
        if obj is not None and "Invalid" in list(obj.State):
            self.show_status()
            return False  # stay open, like Fusion's dialog with an error
        self.cleanup()
        self.doc.commitTransaction()
        self._close()
        log("%s done" % self.title)
        return True

    def reject(self):
        self._timer.stop()
        self.cleanup()
        self.doc.abortTransaction()
        self.doc.recompute()
        self._close()
        return True

    def _close(self):
        Gui.Control.closeDialog()
        try:
            if Gui.ActiveDocument is not None and Gui.ActiveDocument.getInEdit() is not None:
                Gui.ActiveDocument.resetEdit()
        except Exception:
            pass

    def cleanup(self):
        """Remove draggers/observers (override, call super)."""
        self._closed = True
