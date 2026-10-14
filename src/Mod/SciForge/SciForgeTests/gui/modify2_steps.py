# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shared helpers of the Modify part 2 scenarios (scenarios/modify2_*.py): only real input
(ribbon, keys, clicks in the view and the browser, typing in the dialogs' fields)."""

import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import shell_draft_steps as sd
from SciForgeTests.gui import widget_input as w

V = App.Vector


def tan(a):
    return math.tan(math.radians(a))


def close(x, y, tol=1e-6):
    return abs(x - y) <= tol * max(1.0, abs(y))


def doc():
    return App.ActiveDocument


def objects(kind=None, type_id=None):
    found = []
    for o in doc().Objects:
        if kind and getattr(o, "SciForgeType", "") == kind:
            found.append(o)
        elif type_id and o.TypeId == type_id:
            found.append(o)
    return found


def followers():
    from sciforge import modify_bodies

    return [o for o in doc().Objects if modify_bodies.is_follower(o)]


def bodies_list():
    from sciforge import bodies

    return bodies.list_bodies(doc())


def body_volume(body):
    tip = body.Tip
    return tip.Shape.Volume if tip is not None and not tip.Shape.isNull() else 0.0


def total_volume():
    return sum(body_volume(b) for b in bodies_list())


def click_row(label):
    """Click a browser row as a person does, opening the folders above it first."""
    t = sd.browser()
    item = t.row(label)
    if not h.check("browser row %r" % label, item is not None, t.labels()):
        return False
    parent = item.parent()
    while parent is not None:
        parent.setExpanded(True)
        parent = parent.parent()
    t.scrollToItem(item)
    QtWidgets.QApplication.processEvents()
    w.click(t.viewport(), t.label_point(item))
    return True


def press(key, modifiers=QtCore.Qt.NoModifier):
    h.press(key, modifiers)


def undo():
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def redo():
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def no_dialog():
    return not Gui.Control.activeDialog()


def panel_of(module, cls):
    mod = __import__("sciforge." + module, fromlist=[cls])
    p = getattr(mod, cls).last
    if p is None or p._closed:
        return None
    return p


def message(p):
    return p.message.text() if p is not None else ""


def item_enabled(combo, label):
    """(present, enabled, tooltip) of a drop-down entry."""
    for i in range(combo.count()):
        if combo.itemText(i) == label:
            item = combo.model().item(i)
            tip = combo.itemData(i, QtCore.Qt.ToolTipRole) or ""
            return True, bool(item.isEnabled()) if item is not None else True, tip
    return False, False, ""


def selected_names():
    return [(x.ObjectName, list(x.SubElementNames)) for x in Gui.Selection.getSelectionEx()]
