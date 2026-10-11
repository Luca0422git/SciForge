# SPDX-License-Identifier: LGPL-2.1-or-later
"""Value boxes and keys for the Fillet / Chamfer dialogs (fillet_ui.py).

ValueField: Fusion's value box. It takes
  * a number: "1.5" is 1.5 mm (or degrees), always. FreeCAD's number field reads a number
    without a unit in the unit it *shows*: after a drag down to 0.01 mm it showed
    "10.00 µm" and the next "1.5" typed became 1.5 µm (found by the fillet QA);
  * a number with a unit: "0.1 in", "2 cm", "30 deg";
  * a parameter or a formula: "r", "r * 2", "=width/4" (Fusion's way; FreeCAD's field
    silently dropped names, and its "=" opened a FreeCAD formula pop-up). The formula is
    put on the feature as an expression, so the value follows the parameter later.

SaveFinishes: Ctrl+S / Ctrl+N / Ctrl+O while the dialog is open finish it first (OK if
  possible, else Cancel), like starting any other command: a saved file never holds a
  half-made fillet.
"""
import re

import FreeCAD as App

from . import warn
from .compat import QtCore, QtWidgets
from .taskui import DistanceField

_NUMBER = re.compile(r"^[+-]?(\d+([.,]\d*)?|[.,]\d+)([eE][+-]?\d+)?$")
UNITS = {"mm": ("a length", "mm"), "deg": ("an angle", "deg")}


def _in_unit(quantity, unit, text):
    """A FreeCAD quantity as a float in mm (or degrees). A bare number is taken in the box's
    unit; a value of another kind ("30 deg" in a length box) raises ValueError."""
    what, target = UNITS.get(unit, UNITS["mm"])
    if not hasattr(quantity, "Unit"):
        return float(quantity)
    if quantity.Unit == App.Units.Unit():
        return float(quantity.Value)
    try:
        return float(quantity.getValueAs(target))
    except Exception:
        raise ValueError("'%s' is not %s." % (text, what))


def _plain(text):
    try:
        from . import parameters

        return parameters.is_plain_number(text)
    except Exception:
        return False


def parse_number(text, unit="mm"):
    """The value of a plain number typed in a box, in mm (or degrees for unit "deg"), or
    None if `text` is not a usable plain number (a formula, a name, half-typed, empty, a
    value of another kind)."""
    text = (text or "").strip()
    if not text:
        return None
    if _NUMBER.match(text):
        return float(text.replace(",", "."))
    if not _plain(text):
        return None
    try:
        return _in_unit(App.Units.Quantity(text), unit, text)
    except Exception:
        return None


def evaluate(doc, text, unit="mm"):
    """The value of what was typed in a box: a number ("2", "0.1 in"), a parameter or a
    formula ("r", "r * 2 + 1 mm"). Raises ValueError with a plain-language reason."""
    text = (text or "").strip().lstrip("=").strip()
    if not text:
        raise ValueError("Type a value.")
    if _NUMBER.match(text):
        return float(text.replace(",", "."))
    if _plain(text):
        return _in_unit(App.Units.Quantity(text), unit, text)
    from . import parameters, parameters_core

    expr = parameters_core.to_freecad(text, parameters.user_names(doc))
    host = parameters.container(doc)
    if host is None:
        if not doc.Objects:
            raise ValueError("'%s' is not a value." % text)
        host = doc.Objects[0]
    try:
        value = host.evalExpression(expr)
    except Exception as exc:
        raise ValueError("'%s' is not a value here: %s" % (text, exc))
    return _in_unit(value, unit, text)


class ValueField:
    """A value box of a blend dialog. `panel` gets:
    panel._typed(key, value)            a new value (typed, formula, arrows of the box)
    panel._formula_changed(key)         the formula behind the box changed (or was dropped)
    panel._formula_failed(key, text)    what was typed is no value (a typo, wrong unit)"""

    def __init__(self, panel, key, value, unit="mm", minimum=0.0):
        self.panel = panel
        self.key = key
        self.unit = unit
        self.formula = ""  # bare-name formula driving the value ('' = a plain number)
        self.raw = None  # text typed since the box was last settled
        self.field = DistanceField(value, unit=unit, on_change=self._spun)
        self.widget = self.field.widget
        if minimum is not None:
            self.widget.setProperty("minimum", float(minimum))
        # FreeCAD's box swallows the first Enter after a sum ("2*0.25") to rewrite it as
        # "0.50 mm"; Fusion's Enter finishes the command at once (the text is settled in
        # _finished, which runs on that same Enter).
        self.widget.setProperty("autoNormalize", False)
        self.widget.setToolTip(
            "Type a value (%s), a parameter name or a formula such as  r * 2" % unit
        )
        self.edit = self.widget.findChild(QtWidgets.QLineEdit)
        if self.edit is not None:
            self.edit.textEdited.connect(self._edited)
        self.widget.editingFinished.connect(self._finished)
        field = self

        class Steps(QtCore.QObject):
            """Up/Down, Page Up/Down and the wheel step the box's own value: what was typed
            before no longer counts (else leaving the box put the typed value back)."""

            KEYS = (
                QtCore.Qt.Key_Up,
                QtCore.Qt.Key_Down,
                QtCore.Qt.Key_PageUp,
                QtCore.Qt.Key_PageDown,
            )

            def eventFilter(self, obj, event):
                try:
                    kind = event.type()
                    if kind == QtCore.QEvent.Wheel or (
                        kind == QtCore.QEvent.KeyPress and event.key() in self.KEYS
                    ):
                        field.raw = None
                except Exception:
                    pass
                return False

        self._steps = Steps(self.widget)
        self.widget.installEventFilter(self._steps)

    # -- the value ---------------------------------------------------------------------------
    def value(self):
        return self.field.value()

    def set_value(self, value):
        self.field.set_value(value)

    def set_formula(self, text):
        """Show that the box follows a formula (an existing feature's expression)."""
        self.formula = text or ""

    # -- what the person does ------------------------------------------------------------------
    def _alive(self):
        return not getattr(self.panel, "_closed", True)

    def _spun(self, value):
        """FreeCAD's box changed its value: arrows, wheel, or its own reading of the text."""
        try:
            if not self._alive():
                return
            if self.raw is not None:
                # typing: read the text ourselves (a bare number is mm, never µm)
                number = parse_number(self.raw, self.unit)
                if number is None:
                    return  # a formula or half-typed: settled when the box is left
                value = number
            elif self.formula:
                self.formula = ""  # stepped with the arrows: a plain number again
                self.panel._formula_changed(self.key)
            self.panel._typed(self.key, value)
        except Exception as exc:
            warn("%s value: %s" % (self.key, exc))

    def _edited(self, text):
        try:
            self.raw = text
            number = parse_number(text, self.unit)
            if number is not None and self._alive():
                self.panel._typed(self.key, number)
        except Exception as exc:
            warn("%s value: %s" % (self.key, exc))

    def _finished(self):
        """Enter, Tab or a click elsewhere: settle what was typed."""
        raw, self.raw = self.raw, None
        if raw is None or not self._alive():
            return
        try:
            text = raw.strip().lstrip("=").strip()
            if not text:
                self.set_value(self.panel.options.get(self.key, self.value()))
                return
            try:
                value = evaluate(self.panel.doc, text, self.unit)
            except Exception as exc:
                self.set_value(self.panel.options.get(self.key, self.value()))
                self.panel._formula_failed(self.key, str(exc))
                return
            self.set_value(value)  # shown in mm again ("1.50 mm")
            formula = "" if _NUMBER.match(text) or _plain(text) else text
            if formula != self.formula:
                self.formula = formula
                self.panel._formula_changed(self.key)
            self.panel._typed(self.key, value)
        except Exception as exc:
            warn("%s value: %s" % (self.key, exc))


class SaveFinishes:
    """Ctrl+S / Ctrl+N / Ctrl+O while a blend dialog is open: the dialog is finished first
    (OK if the blend can be made, else Cancel), then the command runs. remove() at the end."""

    COMMANDS = {
        QtCore.Qt.Key_S: "Std_Save",
        QtCore.Qt.Key_N: "Std_New",
        QtCore.Qt.Key_O: "Std_Open",
    }

    def __init__(self, panel):
        self.panel = panel
        guard = self

        class KeyFilter(QtCore.QObject):
            def eventFilter(self, obj, event):
                return guard._filter(event)

        self.filter = KeyFilter()
        QtWidgets.QApplication.instance().installEventFilter(self.filter)

    def _filter(self, event):
        try:
            from .compat import QtGui

            kind = event.type()
            if kind not in (QtCore.QEvent.ShortcutOverride, QtCore.QEvent.KeyPress):
                return False
            if self.panel is None or not isinstance(event, QtGui.QKeyEvent):
                return False
            mods = event.modifiers()
            if not (mods & QtCore.Qt.ControlModifier) or (
                mods & (QtCore.Qt.ShiftModifier | QtCore.Qt.AltModifier)
            ):
                return False
            command = self.COMMANDS.get(event.key())
            if command is None:
                return False
            event.accept()  # the main window's own shortcut must not run under the dialog
            if kind == QtCore.QEvent.KeyPress and not event.isAutoRepeat():
                panel = self.panel
                QtCore.QTimer.singleShot(0, lambda: _finish_then(panel, command))
            return True
        except Exception:
            return False

    def remove(self):
        try:
            QtWidgets.QApplication.instance().removeEventFilter(self.filter)
        except Exception:
            pass
        self.panel = None


def _finish_then(panel, command):
    """A plain function (rule 11: a timer aimed at a deleted Qt object never fires)."""
    import FreeCADGui as Gui

    try:
        if panel is not None and not getattr(panel, "_closed", True):
            panel.finish()
        Gui.runCommand(command)
    except Exception as exc:
        warn("%s with the dialog open: %s" % (command, exc))
