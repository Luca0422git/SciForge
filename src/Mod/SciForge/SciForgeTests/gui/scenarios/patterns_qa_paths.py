# SPDX-License-Identifier: LGPL-2.1-or-later
"""Patterns and Mirror the way real Fusion users try them (QA, only real input).

Path 1, beginner: Rectangular Pattern with nothing selected, OK, Enter over the view, a click on
        the empty background, Esc. Nothing is made, nothing is added to the undo history, no
        overlay is left in the view.
Path 2, wrong order: Quantity and Distance typed first, then the Direction box and the X axis,
        and only then the hole in the timeline. The preview uses the typed values (the default
        distance does not overwrite them), the picked hole lights up blue in the view (Fusion
        shades what is picked). OK.
Path 3, Esc in the middle of a pick: Mirror, the hole, the Mirror Plane box (the origin squares
        are drawn), Esc. The squares go, the part is as before, nothing is selected, the next
        Mirror starts empty.
Path 4, values while the preview runs: a pattern along Y; "abc" in Quantity is explained in
        plain words and OK waits; Distance 0 is refused in the dialog; a negative distance puts
        the copy off the part (it cuts nothing, no error); the blue arrow dragged far out and far
        back past the start; a formula typed (4 * pi) stays when the arrow is only clicked (it
        was thrown away); Enter in the Quantity field finishes the command.
        Ctrl+Z removes exactly that pattern, Ctrl+Y brings it back.

Hand-derived: box 40 x 30 x 10 = 12000; a through hole r 2 removes pi 2^2 10.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import pattern_steps as ps

V = App.Vector
s = {}
R = 2.0
HOLE = ps.hole(R)


def doc():
    return App.ActiveDocument


def nodes():
    return h.view().getSceneGraph().getNumChildren()


def centres():
    return ps.circle_centres(h.body().Shape, R, z=10)


def message():
    p = ps.panel()
    return p.message.text() if p is not None else ""


# -- Path 1: beginner, nothing picked -----------------------------------------------------------
def p1_start():
    Gui.Selection.clearSelection()
    s["undo"] = doc().UndoCount
    s["nodes"] = nodes()
    s["v"] = h.solid_volume()
    h.ribbon("Rectangular Pattern")


def p1_ok_with_nothing():
    p = ps.panel()
    h.check("dialog open, nothing picked", p is not None and p.options["objects"] == [])
    h.task_button("OK")


def p1_ok_waits():
    p = ps.panel()
    h.check("OK with nothing picked keeps the dialog open", p is not None)
    h.check("the dialog says what to pick", "select the features" in message().lower(), message())
    h.check("model unchanged", ps.close(h.solid_volume(), s["v"]))
    ps.no_popups("OK with nothing picked")
    h.fit()
    h.press(QtCore.Qt.Key_Return)


def p1_enter_waits():
    h.check("Enter over the view with nothing picked keeps it open", ps.panel() is not None)
    h.click_empty()


def p1_background():
    p = ps.panel()
    h.check("a click on the background picks nothing", p is not None and not p.options["objects"])
    h.press(QtCore.Qt.Key_Escape)


def p1_after_esc():
    h.check("Esc closes it", ps.panel() is None and not Gui.Control.activeDialog())
    h.check("nothing was made", ps.close(h.solid_volume(), s["v"]) and not ps.patterns())
    h.check("no undo step left behind", doc().UndoCount == s["undo"], (doc().UndoCount, s["undo"]))
    h.check("no overlay left in the view", nodes() == s["nodes"], (nodes(), s["nodes"]))
    h.check("nothing selected", not Gui.Selection.getSelectionEx())


# -- Path 2: values and direction first, the feature last -------------------------------------------
def p2_start():
    Gui.Selection.clearSelection()
    h.ribbon("Rectangular Pattern")


def p2_values_first():
    p = ps.panel()
    ps.type_quantity(p.quantity, 3)
    ps.type_value(p.distance_field.widget, "24")


def p2_values_kept_waiting():
    p = ps.panel()
    h.check(
        "typed values shown", p.quantity.value() == 3 and ps.close(p.distance_field.value(), 24)
    )
    h.check("still nothing built", p.target is None and ps.close(h.solid_volume(), s["v"]))
    h.check("no warning while waiting", message() == "", message())
    ps.click_box("direction")


def p2_axis():
    h.fit()
    pl.click_on_plane(V(-12, 0, 0))


def p2_axis_taken():
    p = ps.panel()
    d1 = p.options["direction"]
    h.check("X axis taken before any object", d1 is not None and d1[0].Role == "X_Axis", d1)
    h.check("the dialog asks for the features", "features" in p.info.text().lower(), p.info.text())
    h.check("the typed distance is kept", ps.close(p.distance_field.value(), 24))
    ps.timeline_click("Extrude 2")


def p2_preview():
    p = ps.panel()
    h.check("the hole is the object", len(p.options["objects"]) == 1, p.options["objects"])
    h.check("3 holes at 8, 20, 32", centres() == [(8, 8), (20, 8), (32, 8)], centres())
    h.check("the typed distance was not replaced", ps.close(p.distance_field.value(), 24))
    lit = p.marks.content.getNumChildren() if p.marks is not None else 0
    h.check("the picked hole is shaded in the view", lit >= 1, lit)
    h.check("blue arrows shown", "distance" in p.handles, list(p.handles))
    h.shot("2-wrong-order")
    h.task_button("OK")


def p2_after_ok():
    h.check("one pattern, 3 holes", len(ps.patterns()) == 1, ps.patterns())
    h.check("volume", ps.close(h.solid_volume(), ps.BOX - 3 * HOLE), h.solid_volume())
    s["v"] = h.solid_volume()


# -- Path 3: Esc in the middle of a pick ------------------------------------------------------------
def p3_start():
    Gui.Selection.clearSelection()
    s["nodes"] = nodes()
    s["undo"] = doc().UndoCount
    h.ribbon("Mirror")


def p3_pick():
    ps.timeline_click("Extrude 2")


def p3_plane_box():
    ps.click_box("plane")


def p3_planes_up():
    p = ps.panel()
    h.check("the origin planes are drawn to click", p is not None and p.plane_picker is not None)
    h.check("waiting for the plane: no preview yet", p is not None and p.target is None)
    h.press(QtCore.Qt.Key_Escape)


def p3_after_esc():
    h.check("Esc in the middle of a pick closes Mirror", ps.panel() is None)
    # Not more nodes than before (other overlays, such as the timeline's hover highlight,
    # may have gone away meanwhile).
    h.check("the plane squares are gone", nodes() <= s["nodes"], (nodes(), s["nodes"]))
    h.check("model unchanged", ps.close(h.solid_volume(), s["v"]) and len(ps.patterns()) == 1)
    h.check("nothing selected", not Gui.Selection.getSelectionEx())
    h.check("no undo step left behind", doc().UndoCount == s["undo"])
    h.ribbon("Mirror")


def p3_starts_empty():
    p = ps.panel()
    h.check("the next Mirror starts empty", p is not None and p.options["objects"] == [])
    h.press(QtCore.Qt.Key_Escape)


# -- Path 4: values while the preview runs ----------------------------------------------------------
def p4_start():
    Gui.Selection.clearSelection()
    h.ribbon("Rectangular Pattern")


def p4_pick():
    ps.timeline_click("Extrude 2")


def p4_box():
    ps.click_box("direction")


def p4_y_axis():
    h.fit()
    pl.click_on_plane(V(0, -12, 0))


def p4_y_taken():
    p = ps.panel()
    d1 = p.options["direction"] if p else None
    h.check("Y axis is Direction 1", d1 is not None and d1[0].Role == "Y_Axis", d1)
    ps.type_quantity(p.quantity, "abc")


def p4_abc():
    text = message()
    h.check("'abc' explained in plain words", "not a number or a parameter" in text, text)
    h.check("no FreeCAD jargon", "Property" not in text, text)
    h.task_button("OK")


def p4_abc_ok_waits():
    h.check("OK waits while Quantity is wrong", ps.panel() is not None)
    ps.type_quantity(ps.panel().quantity, 2)


def p4_two():
    h.check("the message goes once a number is typed", message() == "", message())
    ps.type_value(ps.panel().distance_field.widget, "0")


def p4_zero():
    h.check("distance 0 is refused in the dialog", "must not be 0" in message(), message())
    h.task_button("OK")


def p4_zero_ok_waits():
    h.check("OK waits while the distance is 0", ps.panel() is not None)
    ps.type_value(ps.panel().distance_field.widget, "-12")


def p4_negative():
    # The copy goes 12 mm the other way: y = -4, off the part. It cuts nothing; no error.
    h.check("negative distance: no message", message() == "", message())
    h.check("the copy off the part cuts nothing", ps.close(h.solid_volume(), s["v"]))
    s["arrow"] = ps.drag_arrow("distance", 150.0)


p4_negative.wait_ms = 1200


def p4_dragged_far():
    p = ps.panel()
    value = p.distance_field.value()
    h.check("dragged far out", value > 100.0, value)
    h.check("no message", message() == "", message())
    ps.drag_arrow("distance", -400.0)


p4_dragged_far.wait_ms = 1200


def p4_dragged_back():
    p = ps.panel()
    value = p.distance_field.value()
    h.check("dragged back past the start", value < -100.0, value)
    ps.type_value(p.distance_field.widget, "4 * pi")  # a formula, like "gap * 2"


def p4_fourteen():
    p = ps.panel()
    h.check("copy at (8, 8 + 4 pi)", (8, round(8 + 4 * math.pi, 4)) in centres(), centres())
    h.check("4 holes", ps.close(h.solid_volume(), ps.BOX - 4 * HOLE), h.solid_volume())
    h.check("the formula is kept", "4 * pi" in p.formulas.text(), p.formulas.text())
    handle = p.handles.get("distance")
    if h.check("the arrow is there", handle is not None):
        h.fit()
        h.click(handle.origin + handle.direction * handle.distance())  # a click, no drag


def p4_clicked_arrow():
    p = ps.panel()
    h.check(
        "a click on the arrow without moving it keeps the formula",
        "4 * pi" in p.formulas.text(),
        p.formulas.text(),
    )
    h.check(
        "and the value", ps.close(p.distance_field.value(), 4 * math.pi), p.distance_field.value()
    )
    spin = p.quantity
    spin.setFocus()
    QtTest.QTest.mouseClick(spin, QtCore.Qt.LeftButton)
    QtTest.QTest.keyClick(spin, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
    QtTest.QTest.keyClicks(spin, "2")
    QtTest.QTest.keyClick(spin, QtCore.Qt.Key_Return)
    QtWidgets.QApplication.processEvents()


p4_clicked_arrow.wait_ms = 1200


def p4_enter_finished():
    h.check("Enter in Quantity finishes the pattern", ps.panel() is None)
    h.check("two patterns now", len(ps.patterns()) == 2, ps.patterns())
    h.check("4 holes", ps.close(h.solid_volume(), ps.BOX - 4 * HOLE), h.solid_volume())
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def p4_undone():
    h.check("one Ctrl+Z removes that pattern", len(ps.patterns()) == 1)
    h.check("3 holes again", ps.close(h.solid_volume(), ps.BOX - 3 * HOLE), h.solid_volume())
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def p4_redone():
    h.check("Ctrl+Y brings it back", len(ps.patterns()) == 2)
    h.check("4 holes", ps.close(h.solid_volume(), ps.BOX - 4 * HOLE), h.solid_volume())
    h.check("valid", h.body().Shape.isValid())
    h.shot("4-end")


h.run(
    "patterns_qa_paths",
    b.box_steps("PatternQAPaths")
    + ps.make_cut("hole", (8, 8), R)
    + [
        p1_start,
        p1_ok_with_nothing,
        p1_ok_waits,
        p1_enter_waits,
        p1_background,
        p1_after_esc,
        p2_start,
        p2_values_first,
        p2_values_kept_waiting,
        p2_axis,
        p2_axis_taken,
        p2_preview,
        p2_after_ok,
        p3_start,
        p3_pick,
        p3_plane_box,
        p3_planes_up,
        p3_after_esc,
        p3_starts_empty,
        p4_start,
        p4_pick,
        p4_box,
        p4_y_axis,
        p4_y_taken,
        p4_abc,
        p4_abc_ok_waits,
        p4_two,
        p4_zero,
        p4_zero_ok_waits,
        p4_negative,
        p4_dragged_far,
        p4_dragged_back,
        p4_fourteen,
        p4_clicked_arrow,
        p4_enter_finished,
        p4_undone,
        p4_redone,
    ],
)
