# SPDX-License-Identifier: LGPL-2.1-or-later
"""The dimension box never stays behind on the screen.

Luca saw two boxes "Invalid constraint index: 19 / 23" stay over the part after the
sketch was finished. Closing a box by clicking elsewhere (or finishing the sketch, or
starting the next dimension) first tries to set the typed value; when that failed, the box
stayed open with the reason but the sketch had already forgotten it, so nothing closed it
again. The index failed because the dimension was gone (Undo) while its box was open.

A  Circle, Sketch Dimension on it: the box opens. Type "abc" + Enter: the box stays open
   and says why (like Fusion). Click empty space: the box closes, the radius is unchanged
   and a note says why. No box is left on the view.
B  Line, Sketch Dimension on it: the box opens. Undo on the application bar (twice:
   FreeCAD records an extra "Dimension" step) removes that dimension while the box is open. Click empty space: the box closes quietly (nothing
   left to set), no "Invalid constraint index", no box left.
C  Dimension the line again, type 30 (no Enter), Finish Sketch from the ribbon: the value
   is kept, the box is gone, and none is left on the view after the sketch closed.
D  Three lines 10, 15, 20 with their dimensions. Delete the middle line (its dimension
   goes, the 20 line takes its numbers), double-click the 20 dimension, type 30, Undo: the
   box closes and no length changes (it used to set the 15 line to 30: review finding).
E  Double-click the 10 dimension, type 25 (no Enter), Extrude on the ribbon: 25 is set
   before the sketch closes, and the finished sketch shows it (not left to recompute).
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

from SciForgeTests.gui import dialog_input
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si

V = App.Vector
EMPTY = V(40, 35, 0)  # empty space of the sketch
s = {}


def session():
    from sciforge import sketch_mode

    return sketch_mode.current()


def editor():
    sess = session()
    return sess.editor if sess is not None else None


def boxes_on_view():
    """Dimension boxes shown on the 3D view (also ones the sketch forgot)."""
    gl = h.gl_widget()
    return [
        b.findChild(QtWidgets.QLabel).text() if b.findChild(QtWidgets.QLabel) else ""
        for b in gl.findChildren(QtWidgets.QFrame, "SciForgeDimensionEditor")
        if b.isVisible()
    ]


def esc():
    h.press(QtCore.Qt.Key_Escape)


# == A: a value that cannot be set, then a click elsewhere ==========================
def a_new():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("DimBoxCloses")
    h.fit()
    h.ribbon("Create Sketch")


def a_pick():
    h.click(V(12, -8, 0))


def a_circle():
    s["sk"] = h.in_sketch()
    h.check("A: sketch open", s["sk"] is not None)
    h.press("c")


def a_centre():
    si.click(V(10, 10, 0))


def a_radius():
    si.click(V(15, 10, 0))


def a_dim():
    esc()
    h.press("d")


def a_pick_circle():
    c = si.circles(s["sk"], construction=False)[0][1]
    s["c"] = c
    s["r0"] = c.Radius
    si.click(c.Center + V(c.Radius * math.cos(1.0), c.Radius * math.sin(1.0), 0))


def a_place():
    si.click(s["c"].Center + V(9, -2, 0))


def a_type():
    h.check("A: the dimension box is open", editor() is not None)
    si.type_text("abc")


def a_stays():
    ed = editor()
    h.check("A: after Enter the box stays open", ed is not None)
    h.check("A: and says why", ed is not None and "Not a value" in ed.message.text())
    h.click(EMPTY)


def a_closed():
    h.check("A: a click elsewhere closes the box", editor() is None)
    h.check("A: no box left on the view", not boxes_on_view(), boxes_on_view())
    c = si.circles(s["sk"], construction=False)[0][1]
    h.check("A: the radius did not change", si.near(c.Radius, s["r0"], 1e-6), c)
    h.shot("A-closed")


# == B: the box's dimension is undone while the box is open ==========================
def b_line():
    esc()
    h.press("l")


def b_first():
    si.click(V(30, 0, 0))


def b_second():
    si.click(V(30, 20, 0))


def b_dim():
    esc()
    esc()
    s["count"] = len(s["sk"].Constraints)
    h.press("d")


def b_pick_line():
    si.click(V(30, 10, 0))


def b_place():
    si.click(V(36, 10, 0))


def b_undo():
    h.check("B: the dimension box is open", editor() is not None)
    h.check("B: a dimension was added", len(s["sk"].Constraints) > s["count"], s["sk"].Constraints)
    s["index"] = editor().index if editor() is not None else None
    # Undo on the application bar until the dimension is gone (FreeCAD's dimension tool
    # records an extra "Dimension" step first).
    for _ in range(3):
        if len(s["sk"].Constraints) <= s["count"]:
            break
        h.check("Undo button", dialog_input.quick_access("Undo"))


def b_after_undo():
    h.check(
        "B: Undo removed the dimension the box is for",
        len(s["sk"].Constraints) <= s["count"],
        s["sk"].Constraints,
    )
    h.click(EMPTY)


def b_closed():
    h.check("B: a click elsewhere closes the box", editor() is None)
    left = boxes_on_view()
    h.check("B: no box left on the view", not left, left)
    h.check("B: no 'Invalid constraint index' anywhere", not any("Invalid" in t for t in left), left)
    h.shot("B-closed")


# == C: a typed value is kept by Finish Sketch, and no box is left ===================
def c_dim():
    esc()
    h.press("d")


def c_pick_line():
    si.click(V(30, 10, 0))


def c_place():
    si.click(V(36, 10, 0))


def c_type():
    h.check("C: the dimension box is open", editor() is not None)
    ed = editor()
    if ed is not None:
        ed.edit.setFocus()
        ed.edit.selectAll()
    from PySide6 import QtTest

    QtTest.QTest.keyClicks(QtWidgets.QApplication.focusWidget(), "30")
    QtWidgets.QApplication.processEvents()


def c_finish():
    h.ribbon("Finish Sketch")


def c_done():
    h.check("C: the sketch closed", h.in_sketch() is None)
    lines = [g for g in s["sk"].Geometry if g.TypeId == "Part::GeomLineSegment"]
    h.check("C: the typed 30 was kept", any(si.near(l.length(), 30.0, 1e-6) for l in lines), lines)
    left = boxes_on_view()
    h.check("C: no box left on the view after Finish Sketch", not left, left)
    h.shot("C-finished")


# == D: Undo while the box is open on a dimension whose curve numbers moved =============
def d_new():
    App.newDocument("DimBoxUndo")
    h.fit()
    h.ribbon("Create Sketch")


def d_pick():
    h.click(V(12, -8, 0))


def d_lines():
    """Three upright lines 10, 15 and 20 long, each with its length dimension (one undo
    step of their own)."""
    import Part
    import Sketcher

    sk = s["dsk"] = h.in_sketch()
    if not h.check("D: sketch open", sk is not None):
        return
    doc = sk.Document
    doc.openTransaction("Three lines")
    for x, length in ((0, 10), (15, 15), (30, 20)):
        i = sk.addGeometry(Part.LineSegment(V(x, 0, 0), V(x, length, 0)), False)
        sk.addConstraint(Sketcher.Constraint("Distance", i, float(length)))
    doc.commitTransaction()
    sk.recompute()
    h.fit()


def d_delete_middle():
    if editor() is not None:  # (a box opened by itself on the new dimensions: not this test)
        esc()
    si.click(V(15, 7, 0))


def d_deleted():
    h.press(QtCore.Qt.Key_Delete)


def d_open_box():
    sk = s["dsk"]
    h.check("D: the middle line and its dimension went", len(sk.Geometry) == 2, len(sk.Geometry))
    # The 20 line is curve 1 now, and its dimension is the second one.
    index = [i for i, c in enumerate(sk.Constraints) if c.Type == "Distance" and abs(c.Value - 20) < 1e-6]
    if not h.check("D: the 20 dimension is there", len(index) == 1, sk.Constraints):
        return
    point = si.dimension_label(sk, index[0])
    h.move(h.screen_point(point + V(2, 1, 0)))
    h.move(h.screen_point(point))
    h.double_click(point)


def d_type():
    ed = editor()
    h.check("D: double-click opens the box on the 20 dimension", ed is not None)
    if ed is not None:
        ed.edit.setFocus()
        ed.edit.selectAll()
        from PySide6 import QtTest

        QtTest.QTest.keyClicks(QtWidgets.QApplication.focusWidget(), "30")
        QtWidgets.QApplication.processEvents()
    h.check("Undo button", dialog_input.quick_access("Undo"))


def d_after_undo():
    sk = s["dsk"]
    h.check("D: Undo brought the middle line back", len(sk.Geometry) == 3, len(sk.Geometry))
    h.check("D: Undo closed the box (its dimension's numbers moved)", editor() is None)
    h.check("D: no box left on the view", not boxes_on_view(), boxes_on_view())
    h.click(EMPTY)


def d_nothing_set():
    sk = s["dsk"]
    lengths = sorted(round(g.length(), 6) for g in sk.Geometry)
    h.check("D: no length changed (30 went nowhere)", lengths == [10.0, 15.0, 20.0], lengths)
    h.shot("D-undo")


# == E: a value typed in the box, then a command from the ribbon =========================
def e_open_box():
    sk = s["dsk"]
    index = [i for i, c in enumerate(sk.Constraints) if c.Type == "Distance" and abs(c.Value - 10) < 1e-6]
    if not h.check("E: the 10 dimension is there", len(index) == 1, sk.Constraints):
        return
    point = si.dimension_label(sk, index[0])
    h.move(h.screen_point(point + V(2, 1, 0)))
    h.move(h.screen_point(point))
    h.double_click(point)


def e_type():
    ed = editor()
    h.check("E: the box is open on the 10 dimension", ed is not None)
    if ed is not None:
        ed.edit.setFocus()
        ed.edit.selectAll()
        from PySide6 import QtTest

        QtTest.QTest.keyClicks(QtWidgets.QApplication.focusWidget(), "25")
        QtWidgets.QApplication.processEvents()
    h.ribbon("Extrude")


def e_done():
    sk = s["dsk"]
    h.check("E: the ribbon command closed the sketch", h.in_sketch() is None)
    lengths = sorted(round(e.Length, 6) for e in sk.Shape.Edges)
    h.check("E: the typed 25 was set, and the finished sketch shows it", 25.0 in lengths, lengths)
    h.check("E: the sketch is up to date (not left to recompute)", "Touched" not in sk.State, sk.State)
    h.check("E: no box left on the view", not boxes_on_view(), boxes_on_view())
    if Gui.Control.activeDialog():
        h.task_button("Cancel")


h.run(
    "sketch_dim_box_closes",
    [
        a_new,
        a_pick,
        a_circle,
        a_centre,
        a_radius,
        a_dim,
        a_pick_circle,
        a_place,
        a_type,
        a_stays,
        a_closed,
        b_line,
        b_first,
        b_second,
        b_dim,
        b_pick_line,
        b_place,
        b_undo,
        b_after_undo,
        b_closed,
        c_dim,
        c_pick_line,
        c_place,
        c_type,
        c_finish,
        c_done,
        d_new,
        d_pick,
        d_lines,
        d_delete_middle,
        d_deleted,
        d_open_box,
        d_type,
        d_after_undo,
        d_nothing_set,
        e_open_box,
        e_type,
        e_done,
    ],
)
