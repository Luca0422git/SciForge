# SPDX-License-Identifier: LGPL-2.1-or-later
"""A plain number typed in a value box is in mm, whatever the box shows (Fusion).

FreeCAD's number box reads a number without a unit in the unit it *shows*. After an arrow
drag to a tiny distance it shows micrometres ("20.00 µm"), and the next "4" typed became
4 µm instead of 4 mm (found by the fillet QA in its own boxes; every other dialog uses the
shared taskui.DistanceField). Also: Enter after a sum (2*0.25) finishes the command at
once (FreeCAD's box swallowed that Enter to rewrite the text).

Block 40 x 30 x 10, click the top, Q. The arrow leaves 0.02 mm in the box (as a drag
does), type 4: 40 x 30 x 14. Then type 2*0.25 and Enter: the dialog closes, the top is
0.5 mm higher.

Hand-derived: 40*30*10 = 12000; 40*30*14 = 16800; 40*30*10.5 = 12600."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h

V = App.Vector
s = {}


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def panel():
    from sciforge import presspull_ui

    p = presspull_ui.PressPullPanel.last
    return p if p is not None and not p._closed else None


def edit_of(field):
    return field.widget.findChild(QtWidgets.QLineEdit)


def type_keys(field, text, enter=False):
    """Click into the box, select all, type like a keyboard (Tab or Enter at the end)."""
    widget = field.widget
    QtTest.QTest.mouseClick(
        widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, QtCore.QPoint(10, widget.height() // 2)
    )
    QtWidgets.QApplication.processEvents()
    widget.setFocus()
    QtTest.QTest.keyClick(widget, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
    QtTest.QTest.keyClicks(widget, text)
    QtWidgets.QApplication.processEvents()
    QtTest.QTest.keyClick(widget, QtCore.Qt.Key_Return if enter else QtCore.Qt.Key_Tab)
    QtWidgets.QApplication.processEvents()


def setup():
    from sciforge import commands, extrude, sketch_ui

    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("ValueBoxUnits")
    body = commands.ensure_body()
    sk = sketch_ui.create_sketch(body, (sketch_ui.origin_planes(body)["XY_Plane"], ""))
    h.draw_rectangle(sk, 0, 0, 40, 30)
    extrude.make(body, sk, {"distance": 10.0})
    App.ActiveDocument.recompute()
    h.fit()


def pick_top():
    h.click(V(20, 15, 10))


def press_pull():
    h.press("q")


def tiny_value():
    p = panel()
    h.check("Press Pull on the top face", p is not None and p.target is not None)
    if p is None:
        return
    p.field.set_value(0.02)  # what the arrow callback does at the end of a drag near 0
    text = edit_of(p.field).text() if edit_of(p.field) else ""
    h.check("the box shows micrometres (the trap is set)", "µm" in text or "um" in text, text)


def type_4():
    p = panel()
    if p is not None:
        type_keys(p.field, "4")


def four_mm():
    p = panel()
    v = h.solid_volume()
    h.check("typing 4 means 4 mm: 40 x 30 x 14", near(v, 16800.0), v)
    h.check(
        "the box holds 4 mm", p is not None and near(p.field.value(), 4.0), p and p.field.value()
    )


def type_sum_enter():
    p = panel()
    if p is not None:
        type_keys(p.field, "2*0.25", enter=True)


def finished():
    h.check("Enter after a sum finished Press Pull", not Gui.Control.activeDialog())
    v = h.solid_volume()
    h.check("the top is 0.5 mm higher: 40 x 30 x 10.5", near(v, 12600.0), v)


h.run(
    "value_box_units",
    [setup, pick_top, press_pull, tiny_value, type_4, four_mm, type_sum_enter, finished],
)
