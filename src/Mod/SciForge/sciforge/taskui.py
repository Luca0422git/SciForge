# SPDX-License-Identifier: LGPL-2.1-or-later
"""Building blocks for SciForge's Fusion-style command dialogs.

- DistanceField: unit-aware number field (types "5", "5 mm", "0.2 in", "=width*2"),
  optionally bound to a property so expressions/parameters work like in FreeCAD.
- ArrowDragger: the arrow you drag in the 3D view to set a distance (Coin3D).
- Panel: a task-dialog base that wraps the edit in one undo step: OK keeps it,
  Cancel/Esc removes it again, like Fusion.
"""
import re

import FreeCAD as App
import FreeCADGui as Gui

from . import drag_guard, log, warn
from .compat import QtCore, QtWidgets


_OPEN = {"dialog": None}


def current():
    """The SciForge task dialog that is open now (it has finish()), or None."""
    dialog = _OPEN["dialog"]
    if dialog is None or getattr(dialog, "_closed", False) or not Gui.Control.activeDialog():
        _OPEN["dialog"] = None
        return None
    return dialog


def set_current(dialog):
    _OPEN["dialog"] = dialog


# Editors for existing features: {type key: function(obj)}. The type key is the
# FreeCAD TypeId ("PartDesign::Fillet") or "SciForge::<SciForgeType>" for SciForge's
# own Python features. Feature modules declare EDITORS = {...}; commands.py collects
# them. The timeline and the browser open features with edit_object().
EDITORS = {}


def dialog_button(role):
    """The enabled OK ("accept") or Cancel/Close ("reject") button of the open task
    dialog, or None. FreeCAD keeps them in the TaskEditControl's button box."""
    want = (
        QtWidgets.QDialogButtonBox.AcceptRole
        if role == "accept"
        else QtWidgets.QDialogButtonBox.RejectRole
    )
    if not Gui.Control.activeDialog():
        return None
    found = None
    for box in Gui.getMainWindow().findChildren(QtWidgets.QDialogButtonBox):
        parent = box.parentWidget()
        if parent is None or parent.metaObject().className() != "Gui::TaskView::TaskEditControl":
            continue
        for button in box.buttons():
            if box.buttonRole(button) == want and button.isEnabled():
                if button.isVisible():
                    return button
                found = found or button  # the Tasks tab may be hidden behind the Model tab
    return found


def press_dialog_button(role):
    """Click the open dialog's OK or Cancel, exactly as a mouse click on it does (the
    marking menu offers them, as Fusion's does while a command is open)."""
    try:
        button = dialog_button(role)
        if button is None:
            return False
        button.click()
        return True
    except Exception as exc:
        warn("could not press %s: %s" % ("OK" if role == "accept" else "Cancel", exc))
        return False


def type_key(obj):
    kind = getattr(obj, "SciForgeType", "")
    return "SciForge::" + kind if kind else obj.TypeId


def edit_object(obj):
    """Open the right dialog for an existing feature (Fusion: double-click in the
    timeline). Finishes whatever is open first."""
    from . import commands

    if obj is None or not commands.finish_open_dialog():
        return
    try:
        editor = EDITORS.get(type_key(obj))
    except ReferenceError:
        return  # it was the unfinished step of the dialog that was just cancelled
    try:
        if editor is not None:
            editor(obj)
        else:
            Gui.ActiveDocument.setEdit(obj.Name)
    except Exception as exc:
        warn("could not edit %s: %s" % (obj.Label, exc))


_BARE_NUMBER = re.compile(r"^\s*[+-]?(\d+([.,]\d*)?|[.,]\d+)([eE][+-]?\d+)?\s*$")


class DistanceField:
    """A plain number typed in the box is in the box's own unit (mm, or degrees), like
    Fusion. FreeCAD's box reads it in the unit it *shows*: after a value below 0.1 mm it
    showed "50.00 µm", and the next "4" typed became 4 µm (found by the fillet QA)."""

    def __init__(self, value=0.0, unit="mm", on_change=None):
        self.widget = Gui.UiLoader().createWidget("Gui::QuantitySpinBox")
        self.widget.setProperty("unit", unit)
        self.widget.setProperty("minimum", -1e9)
        self.widget.setProperty("maximum", 1e9)
        self.widget.setProperty("rawValue", float(value))
        # autoNormalize stays on: switched off, the box re-read its own rounded text when
        # it lost the focus ("12.57 mm" for 4*pi), a silent loss of precision. The cost: the
        # first Enter after a sum ("2*0.25") only evaluates it, a second Enter is OK.
        self._on_change = on_change
        self._quiet = False
        self._typed = None  # text typed since the box was last settled
        edit = self.widget.findChild(QtWidgets.QLineEdit)
        if edit is not None:
            edit.textEdited.connect(self._edited)
        self.widget.editingFinished.connect(self._settle)
        self.widget.valueChanged.connect(self._changed)

    def bind(self, obj, prop):
        """Bind to obj.prop so typed expressions (=Parameters.width) are stored on it."""
        try:
            self._binding = Gui.ExpressionBinding(self.widget).bind(obj, prop)
        except Exception as exc:
            warn("expression binding unavailable: %s" % exc)

    def value(self):
        typed = self._bare()
        return typed if typed is not None else float(self.widget.property("rawValue"))

    def set_value(self, value):
        self._typed = None
        self._quiet = True
        try:
            self.widget.setProperty("rawValue", float(value))
        finally:
            self._quiet = False

    def _bare(self):
        if self._typed is None or not _BARE_NUMBER.match(self._typed):
            return None
        return float(self._typed.strip().replace(",", "."))

    def _edited(self, text):
        self._typed = text

    def _settle(self):
        """Editing finished: a plain number typed counts in the box's unit. Only a value
        FreeCAD read in another unit is corrected; nothing is done while the dialog closes
        (leaving the box then also "finishes" it, after the value was taken)."""
        typed, self._typed = self._bare(), None
        if typed is None:
            return
        try:
            if not self.widget.isVisible():
                return
            if abs(float(self.widget.property("rawValue")) - typed) <= 1e-12:
                return
        except RuntimeError:
            return  # the box went with its dialog
        try:
            self.set_value(typed)
            owner = getattr(self._on_change, "__self__", None)
            if self._on_change is not None and not getattr(owner, "_closed", False):
                self._on_change(typed)
        except Exception as exc:
            warn("value box: %s" % exc)

    def _changed(self, *_):
        if not self._quiet and self._on_change:
            self._on_change(self.value())


class ArrowDragger:
    """A 1D drag handle at `origin` pointing along `direction` (both App.Vector).

    on_drag(distance) is called while dragging, on_release(distance) at the end.

    The arrow is watched with a Qt timer instead of Coin dragger callbacks: Coin
    calls those in the middle of its mouse handling, where rebuilding the part
    (or swapping Extrude for Cut) changes the scene under its feet, and pivy runs
    them without taking Python's lock. Both crashed FreeCAD on a drag."""

    POLL_MS = 30

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
        color = coin.SoMaterial()  # Fusion's manipulator blue instead of Coin's white
        color.diffuseColor.setValue(0.30, 0.62, 0.95)
        color.emissiveColor.setValue(0.10, 0.25, 0.45)
        color.setOverride(True)
        self.root.addChild(place)
        self.root.addChild(scale)
        self.root.addChild(color)
        self.root.addChild(self.dragger)
        self.on_drag = on_drag
        self.on_release = on_release
        self._last = self.distance()
        self._was_active = False
        self.view.getSceneGraph().addChild(self.root)
        self._timer = QtCore.QTimer()
        self._timer.setInterval(self.POLL_MS)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    def distance(self):
        return self.dragger.translation.getValue()[0] * self.size

    def set_distance(self, distance):
        self.dragger.translation.setValue(distance / self.size, 0, 0)
        self._last = self.distance()

    def _poll(self):
        try:
            # a release FreeCAD never passed on ends the drag here (drag_guard)
            active = drag_guard.guard_coin_dragger(self.dragger, self.root, self.view)
            value = self.distance()
            if abs(value - self._last) > 1e-9:
                self._last = value
                if self.on_drag:
                    self.on_drag(value)
            if self._was_active and not active and self.on_release:
                self.on_release(value)
            self._was_active = active
        except Exception as exc:
            warn("drag: %s" % exc)

    def remove(self):
        try:
            self._timer.stop()
        except Exception:
            pass
        drag_guard.before_remove(self.dragger, self.root, self.view)
        try:
            self.view.getSceneGraph().removeChild(self.root)
        except Exception:
            pass


def _end_transaction(doc, abort=False):
    """Close a dialog's undo step. doc.commitTransaction()/abortTransaction() only close a
    step that holds changes: a dialog OK'd or cancelled without a change left its step name
    pending, and the next change anywhere opened a step under that name and threw away the
    Redo list. The pending name is closed too (same as preview.end_transaction)."""
    if abort:
        doc.abortTransaction()
    else:
        doc.commitTransaction()
    try:
        App.closeActiveTransaction(abort)
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
        set_current(self)

    def finish_layout(self):
        self.layout.addRow(self.message)

    # -- live preview ---------------------------------------------------------
    def schedule(self):
        self._timer.start()

    def _recompute(self):
        if self._closed:
            return  # a change that arrived as the dialog closed
        try:
            self.doc.recompute()
            self.show_status()
        except Exception as exc:
            try:
                self.message.setText(str(exc))
            except RuntimeError:
                pass

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
        _end_transaction(self.doc)
        self._close()
        log("%s done" % self.title)
        return True

    def reject(self):
        self._timer.stop()
        self.cleanup()
        _end_transaction(self.doc, abort=True)
        self.doc.recompute()
        self._close()
        return True

    def finish(self):
        """Another command is starting: keep this edit if it is valid, else drop it."""
        if not self.accept():
            self.reject()

    def _close(self):
        if _OPEN["dialog"] is self:
            _OPEN["dialog"] = None
        Gui.Control.closeDialog()
        # Fusion clears the selection when a command ends. A selection left behind
        # was picked up by the next command (a second Extrude re-used the first
        # sketch, cut into the part and made it disappear).
        try:
            Gui.Selection.clearSelection()
        except Exception:
            pass
        try:
            from . import commands

            commands.leave_edit()
        except Exception as exc:
            warn("could not finish editing: %s" % exc)

    def cleanup(self):
        """Remove draggers/observers (override, call super)."""
        self._closed = True
