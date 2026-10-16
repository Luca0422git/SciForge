# SPDX-License-Identifier: LGPL-2.1-or-later
"""Align: choose which point of a face or an edge (Luca: "the align tool should have the
option to select what part of the face you should align to. there should be a middle
point, edge point, etc."). Fusion offers snap points on the face or edge under the mouse
(face centres, edge midpoints, corners, circle centres); Align shows them as dots and a
click takes the dot next to the mouse; the face's normal still sets the direction. Only
real input.

Bodies made with Create Sketch + Extrude: a table 0..60 x 0..40 x 10 (Body) and a block
80..100 x 0..10 x 5 (New Body, 1000).

  A  MODIFY > Align. The mouse over the block's top face near its corner (100, 10, 5): the
     face's dots are shown (centre, 4 corners, 4 edge middles), the corner is lit. Click
     there: From = that corner, facing up.
  B  The mouse over the table's top face near the middle of its front edge (30, 0, 10): that
     dot is lit; click: To = (30, 0, 10). The two faces face each other (the block upside
     down on the table) and the corner lands on the edge's middle. Hand-derived: a half
     turn about Y, then the corner (100, 10, 5) onto (30, 0, 10): x 30..50, y -10..0,
     z 10..15.
  C  OK: an Align step, same volume. Undo: back at 80..100; Redo.
  D  Double-click the Align in the timeline: the snapped points are kept (same place); the To
     box waits: clear it, click the table's top face far from every dot: To = its centre
     (30, 20, 10) as before: x 30..50, y 10..20, z 10..15. OK.
  E  An edge: Align again, From = the block's top face near its corner (50, 20, 15), To =
     the table's right edge (x 60, y 0..40, z 10) near its end (60, 40, 10): the corner goes
     to that end of the edge. Esc: nothing moved.
  F  Ctrl keeps the face: Align, the mouse over the block's top face, Ctrl held, the mouse
     right on the block's corner (an edge / corner is under it): the dots stay the face's;
     the click takes the face at that corner (facing up), not the bare corner.
  G  Esc cancels: nothing moved.
"""

import FreeCAD as App
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import direct_steps as d
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import timeline_input as t
from SciForgeTests.gui import widget_input as wi

V = App.Vector
state = {}


def block():
    return d.bodies()[1]


def box():
    from sciforge import bodies

    return bodies.global_shape(block().Tip).BoundBox


def at(bb, xmin=None, xmax=None, ymin=None, ymax=None, zmin=None, zmax=None):
    want = (xmin, xmax, ymin, ymax, zmin, zmax)
    got = (bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax)
    return all(w is None or abs(w - g) < 1e-6 for w, g in zip(want, got))


def aligns():
    return [o for o in d.doc().Objects if getattr(o, "SciForgeType", "") == "Align"]


def snaps():
    p = d.panel()
    return getattr(p, "snaps", None) if p is not None else None


def near(dot, toward, pixels=6.0):
    """A point of the face `pixels` on the screen from `dot`, towards `toward` (inside it)."""
    a = h.screen_point(dot)
    step = toward - dot
    step.normalize()
    for i in range(1, 400):
        p = dot + step * (0.05 * i)
        b = h.screen_point(p)
        if ((a.x() - b.x()) ** 2 + (a.y() - b.y()) ** 2) ** 0.5 >= pixels:
            return p
    return dot + step * 0.5


def hover(point, modifiers=QtCore.Qt.NoModifier):
    """The mouse to `point`, with `modifiers` held (a move carries the keys held, as a real
    one does)."""
    from PySide import QtGui

    h.uncover(point)
    widget = h.gl_widget()
    pixel = h.screen_point(point)
    if modifiers == QtCore.Qt.NoModifier:
        h.move(pixel)
    else:
        event = QtGui.QMouseEvent(
            QtCore.QEvent.MouseMove,
            QtCore.QPointF(pixel),
            QtCore.QPointF(widget.mapToGlobal(pixel)),
            QtCore.Qt.NoButton,
            QtCore.Qt.NoButton,
            modifiers,
        )
        QtWidgets.QApplication.sendEvent(widget, event)
        QtWidgets.QApplication.processEvents()
    state["hover"] = point


def lit(where, kind, point):
    sn = snaps()
    if not h.check("%s: snap dots shown" % where, sn is not None and sn.candidates, sn):
        return
    hot = sn.hot
    h.check(
        "%s: the %s at %s is lit" % (where, kind, tuple(point)),
        hot is not None and hot["kind"] == kind and (hot["point"] - point).Length < 1e-6,
        hot and (hot["kind"], hot["point"]),
    )
    return sn


def click_hovered():
    h.click(state["hover"])


def frame_point(name):
    p = d.panel()
    frame = p.options.get(name + "_frame") if p is not None else None
    return V(*frame["point"]) if frame else None, frame


# -- A ------------------------------------------------------------------------------------------
def a_open():
    h.click_empty()
    h.fit()
    d.ribbon_menu("MODIFY", "Align")


def a_hover_corner():
    p = d.panel()
    if not h.check("Align dialog", p is not None and p.title == "Align", p):
        return
    hover(near(V(100, 10, 5), V(90, 5, 5), pixels=11.0))  # on the face, not its edges


def a_lit():
    sn = lit("block top", "vertex", V(100, 10, 5))
    if sn is not None:
        h.check("9 dots: centre, 4 corners, 4 middles", len(sn.candidates) == 9, sn.candidates)
    h.shot("A-dots")


a_lit.wait_ms = 400


def a_click():
    click_hovered()


def a_taken():
    point, frame = frame_point("from")
    h.check(
        "From = the corner (100, 10, 5)",
        point is not None and (point - V(100, 10, 5)).Length < 1e-6,
        frame,
    )
    h.check(
        "facing up (the face's normal)",
        frame is not None and frame["oriented"] and abs(frame["axis"][2] - 1.0) < 1e-9,
        frame,
    )


# -- B ------------------------------------------------------------------------------------------
def b_hover_middle():
    hover(near(V(30, 0, 10), V(30, 20, 10), pixels=9.0))


def b_lit():
    lit("table top", "midpoint", V(30, 0, 10))


b_lit.wait_ms = 400


def b_click():
    click_hovered()


def b_preview():
    point, frame = frame_point("to")
    h.check(
        "To = the edge's middle (30, 0, 10)",
        point is not None and (point - V(30, 0, 10)).Length < 1e-6,
        frame,
    )
    bb = box()
    h.check(
        "corner on the edge's middle: x 30..50, y -10..0, z 10..15",
        at(bb, 30, 50, -10, 0, 10, 15),
        bb,
    )
    h.check("same volume", d.near(d.volume(block()), 1000), d.volume(block()))
    h.shot("B-preview")


# -- C ------------------------------------------------------------------------------------------
def c_ok():
    h.task_button("OK")


def c_done():
    h.check("dialog closed", d.panel() is None)
    h.check("an Align step", len(aligns()) == 1, aligns())
    h.check("kept", at(box(), 30, 50, -10, 0, 10, 15), box())
    t.undo()


def c_undone():
    h.check("undo: back where it was", at(box(), 80, 100, 0, 10, 0, 5), box())
    t.redo()


def c_redone():
    h.check("redo: on the edge again", at(box(), 30, 50, -10, 0, 10, 15), box())


# -- D ------------------------------------------------------------------------------------------
def d_edit():
    h.click_empty()
    h.fit()
    h.check("double-click Align 1", ui.double_click_timeline("Align 1"), t.titles())


def d_kept():
    p = d.panel()
    if not h.check("the edit dialog", p is not None and p.editing, p):
        return
    h.check("the snapped points are kept", at(box(), 30, 50, -10, 0, 10, 15), box())
    wi.click(p.fields["to"].clear)


def d_hover_far():
    # far from every dot of the table's top face: the centre (30, 20, 10) is taken
    hover(V(12, 28, 10))


def d_centre_lit():
    lit("table top, far from the dots", "centre", V(30, 20, 10))


d_centre_lit.wait_ms = 400


def d_click():
    click_hovered()


def d_preview():
    point, frame = frame_point("to")
    h.check("To = the centre", point is not None and (point - V(30, 20, 10)).Length < 1e-6, frame)
    h.check(
        "the corner on the centre: x 30..50, y 10..20", at(box(), 30, 50, 10, 20, 10, 15), box()
    )
    h.task_button("OK")


def d_done():
    h.check("dialog closed", d.panel() is None)
    h.check("still one Align step", len(aligns()) == 1, aligns())
    h.check("on the centre", at(box(), 30, 50, 10, 20, 10, 15), box())


# -- E ------------------------------------------------------------------------------------------
def e_open():
    h.click_empty()
    h.fit()
    d.ribbon_menu("MODIFY", "Align")


def e_hover_corner():
    # the block's top (upside down now: its old bottom, z 15) near the corner (50, 20, 15)
    hover(near(V(50, 20, 15), V(40, 15, 15), pixels=11.0))


def e_lit():
    lit("block top", "vertex", V(50, 20, 15))


e_lit.wait_ms = 400


def e_click():
    click_hovered()


def e_hover_edge():
    p = d.panel()
    h.check("To waits", p is not None and p.active == "to", p and p.active)
    # on the table's right edge (x 60, z 10), near its far end (60, 40, 10)
    edge_point = near(V(60, 40, 10), V(60, 0, 10), pixels=5.0)
    state["edge"] = edge_point
    hover(edge_point)


def e_end_lit():
    lit("the table's right edge", "vertex", V(60, 40, 10))


e_end_lit.wait_ms = 400


def e_click_edge():
    h.click_edge(state["edge"])


def e_preview():
    point, frame = frame_point("to")
    h.check(
        "To = the edge's end (60, 40, 10)",
        point is not None and (point - V(60, 40, 10)).Length < 1e-6,
        frame,
    )
    bb = box()
    corner = V(bb.XMax, bb.YMax, bb.ZMax)
    h.check(
        "a corner of the block is on (60, 40, 10)",
        any(
            (V(x, y, z) - V(60, 40, 10)).Length < 1e-6
            for x in (bb.XMin, bb.XMax)
            for y in (bb.YMin, bb.YMax)
            for z in (bb.ZMin, bb.ZMax)
        ),
        (bb, corner),
    )
    h.press(QtCore.Qt.Key_Escape)


def e_cancelled():
    h.check("Esc: nothing moved", at(box(), 30, 50, 10, 20, 10, 15), box())
    h.check("still one Align step", len(aligns()) == 1, aligns())


# -- F ------------------------------------------------------------------------------------------
def f_open():
    h.click_empty()
    h.fit()
    d.ribbon_menu("MODIFY", "Align")


def f_hover_face():
    hover(near(V(30, 10, 15), V(40, 15, 15), pixels=20.0))


def f_ctrl():
    sn = snaps()
    h.check(
        "the face's dots",
        sn is not None and sn.pick is not None and sn.pick[1].startswith("Face"),
        sn and sn.pick,
    )
    QtTest.QTest.keyPress(h.gl_widget(), QtCore.Qt.Key_Control, QtCore.Qt.ControlModifier)
    QtWidgets.QApplication.processEvents()
    # right on the corner (an edge or the corner is under the mouse), Ctrl still held
    hover(V(30, 10, 15), QtCore.Qt.ControlModifier)


def f_locked():
    sn = snaps()
    h.check(
        "Ctrl keeps the face",
        sn is not None and sn.locked and sn.pick[1].startswith("Face"),
        sn and (sn.locked, sn.pick),
    )
    lit("the kept face", "vertex", V(30, 10, 15))
    h.click(V(30, 10, 15), modifiers=QtCore.Qt.ControlModifier)


f_locked.wait_ms = 400


def f_taken():
    QtTest.QTest.keyRelease(h.gl_widget(), QtCore.Qt.Key_Control, QtCore.Qt.NoModifier)
    QtWidgets.QApplication.processEvents()
    point, frame = frame_point("from")
    p = d.panel()
    h.check(
        "From = the face (not the bare corner)",
        p is not None and p.options["from_pick"] and p.options["from_pick"][1].startswith("Face"),
        p and p.options["from_pick"],
    )
    h.check(
        "at the corner, facing the face's way",
        point is not None and (point - V(30, 10, 15)).Length < 1e-6 and frame["oriented"],
        frame,
    )
    h.press(QtCore.Qt.Key_Escape)


# -- G ------------------------------------------------------------------------------------------
def g_cancelled():
    h.check("Esc: no dialog", d.panel() is None)
    h.check("Esc: nothing moved", at(box(), 30, 50, 10, 20, 10, 15), box())
    h.check("Esc: still one Align step", len(aligns()) == 1, aligns())


h.run(
    "modify_align_points",
    t.watched(
        [s.new_design("AlignPoints")]
        + s.box_steps("table", (0, 0, 60, 40), 10, V(6, -6, 0))
        + s.box_steps("block", (80, 0, 100, 10), 5, V(6, -6, 0), new_body=True)
        + [
            a_open,
            a_hover_corner,
            a_lit,
            a_click,
            a_taken,
            b_hover_middle,
            b_lit,
            b_click,
            b_preview,
            c_ok,
            c_done,
            c_undone,
            c_redone,
            d_edit,
            d_kept,
            d_hover_far,
            d_centre_lit,
            d_click,
            d_preview,
            d_done,
            e_open,
            e_hover_corner,
            e_lit,
            e_click,
            e_hover_edge,
            e_end_lit,
            e_click_edge,
            e_preview,
            e_cancelled,
            f_open,
            f_hover_face,
            f_ctrl,
            f_locked,
            f_taken,
            g_cancelled,
        ]
    ),
)
