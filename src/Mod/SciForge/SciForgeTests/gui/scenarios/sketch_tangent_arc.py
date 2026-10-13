# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's tangent arc in the Line tool (sciforge/sketch_infer.py, TangentArc), with
real mouse presses, drags and releases.

L, a level line A -> B. The chain goes on from B. Press on B and drag (without letting
go) to a point P: an arc tangent to the line follows the pointer (SciForge's own
preview and tangent mark); release: the arc is in the sketch, tangent to the line at B
(FreeCAD's end-to-end Tangent, which also joins the points), its centre on the
normal through B, its end at P. The chain goes on from P: a drag from P makes an arc
tangent to the first arc, dragged onto the end of another line it snaps there
(Coincident). One Ctrl+Z takes an arc back (its own step), Ctrl+Y brings it back. A
plain click on the chain's point (no drag) adds nothing, as before; a plain click
elsewhere still makes a straight line; a typed length still works.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si

V = App.Vector
s = {}
CTRL = QtCore.Qt.ControlModifier


def session():
    from sciforge import sketch_mode

    return sketch_mode.current()


def infer_state():
    sess = session()
    return sess.infer.state() if sess is not None and sess.infer is not None else {}


def g(point):
    return s["sk"].getGlobalPlacement().multVec(point)


def cons():
    return [(c.Type, c.First, c.FirstPos, c.Second, c.SecondPos) for c in s["sk"].Constraints]


def esc():
    h.press(QtCore.Qt.Key_Escape)


def move(point):
    pos = h.screen_point(point)
    QtGui.QCursor.setPos(h.gl_widget().mapToGlobal(pos))
    h.move(pos)


def approach(raw, towards=V(-1.0, 1.5, 0)):
    for f in (3.0, 2.0, 1.0, 0.0):
        move(g(raw + towards * f))


def shot(name):
    QtTest.QTest.qWait(300)
    h.shot(name)


def arcs():
    return [
        (i, geo) for i, geo in enumerate(s["sk"].Geometry) if geo.TypeId == "Part::GeomArcOfCircle"
    ]


def press_at(point):
    """Press the left button on the 3D point (the real pointer rests there first)."""
    pos = h.screen_point(point)
    move(point)
    QtTest.QTest.qWait(80)
    QtTest.QTest.mousePress(h.gl_widget(), QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, pos)
    QtWidgets.QApplication.processEvents()
    return pos


def drag_to(point, steps=8, modifiers=QtCore.Qt.NoModifier):
    """Move the pointer to the 3D point with the left button held, in steps."""
    widget = h.gl_widget()
    start = widget.mapFromGlobal(QtGui.QCursor.pos())
    end = h.screen_point(point)
    for i in range(1, steps + 1):
        pos = QtCore.QPointF(
            start.x() + (end.x() - start.x()) * i / steps,
            start.y() + (end.y() - start.y()) * i / steps,
        )
        event = QtGui.QMouseEvent(
            QtCore.QEvent.MouseMove,
            pos,
            QtCore.QPointF(widget.mapToGlobal(pos.toPoint())),
            QtCore.Qt.NoButton,
            QtCore.Qt.LeftButton,
            modifiers,
        )
        QtWidgets.QApplication.sendEvent(widget, event)
        QtWidgets.QApplication.processEvents()
    # the screen's own pointer stays where the button went down: moving it would make
    # the virtual screen send a move with no button held, which ends the gesture (as a
    # real release elsewhere would)
    return end


def release_at(pos, modifiers=QtCore.Qt.NoModifier):
    QtTest.QTest.mouseRelease(h.gl_widget(), QtCore.Qt.LeftButton, modifiers, pos)
    QtWidgets.QApplication.processEvents()


def tangent_at(arc, point):
    """The counterclockwise tangent of the arc at one of its ends."""
    radial = point - arc.Center
    return V(-radial.y, radial.x, 0).normalize()


def degrees_between(a, b):
    c = a.dot(b) / (a.Length * b.Length)
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


# -- setup ------------------------------------------------------------------------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("SketchTangentArc")
    h.fit()


def create_sketch():
    h.ribbon("Create Sketch")


def pick_xy():
    h.click(V(12, -8, 0))


def reference():
    import Part

    sk = h.in_sketch()
    s["sk"] = sk
    h.check("sketch open", sk is not None)
    s["ref"] = sk.addGeometry(Part.LineSegment(V(70, 45, 0), V(90, 60, 0)))
    App.ActiveDocument.recompute()
    s["px"] = si.mm_per_pixel(sk)


def line_key():
    h.press("l")


def line_a():
    si.click(g(V(0, 0, 0)))


def line_b():
    s["count"] = len(s["sk"].Geometry)
    si.click(g(V(30, 0, 0)))


def press_without_moving():
    """Straight after the chain click, with no mouse move at all (FreeCAD previews
    nothing then), a press on B arms the gesture; a release with no drag adds nothing."""
    pos = h.screen_point(g(V(30, 0, 0)))
    QtTest.QTest.mousePress(h.gl_widget(), QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, pos)
    QtWidgets.QApplication.processEvents()
    h.check(
        "a press on the chain's point before any move arms the tangent arc",
        infer_state().get("arc") == "armed",
        infer_state().get("arc"),
    )
    release_at(pos)
    h.check("...and a release without a drag adds nothing", len(s["sk"].Geometry) == s["count"] + 1)


def chained():
    lines = si.lines(s["sk"])
    h.check("the line A-B was drawn", len(s["sk"].Geometry) == s["count"] + 1, len(lines))
    s["line"] = lines[-1][0]
    # the chain goes on from B: move a little and the preview starts there
    approach(V(38, 6, 0), V(1.0, 1.0, 0))
    from sciforge import sketch_mode

    coords, _ = sketch_mode.find_node(h.view().getSceneGraph(), "EditCurvesCoordinate")
    points = coords.point.getValues(0) if coords is not None else []
    start = points[0].getValue() if len(points) == 2 else None
    h.check(
        "the next line starts at B",
        start is not None and abs(start[0] - 30) < 1e-3 and abs(start[1]) < 1e-3,
        start,
    )


# == the first arc: press on B, drag, release ============================================
def a_press():
    s["a_count"] = len(s["sk"].Geometry)
    s["a_cons"] = len(s["sk"].Constraints)
    press_at(g(V(30, 0, 0)))
    h.check(
        "pressing on the chain's point arms the tangent arc",
        infer_state().get("arc") == "armed",
        infer_state().get("arc"),
    )


def a_drag():
    s["a_pos"] = drag_to(g(V(50, 15, 0)))
    state = infer_state()
    preview = state.get("overlay", {}).get("preview", [])
    marks = state.get("overlay", {}).get("marks", [])
    h.check(
        "dragging shows the arc preview",
        state.get("arc") == "dragging" and len(preview) == 1 and len(preview[0]) > 10,
        (state.get("arc"), len(preview)),
    )
    h.check(
        "...and SciForge's tangent mark at the joint", len(marks) == 1 and len(marks[0]) == 2, marks
    )
    if preview:
        pts = preview[0]
        h.check(
            "the preview arc starts at B",
            abs(pts[0][0] - 30) < 1e-6
            and abs(pts[0][1]) < 1e-6
            or abs(pts[-1][0] - 30) < 1e-6
            and abs(pts[-1][1]) < 1e-6,
            (pts[0], pts[-1]),
        )
    h.check(
        "FreeCAD's own line preview did not follow the drag", len(s["sk"].Geometry) == s["a_count"]
    )
    shot("1-arc-drag")


def a_release():
    release_at(s["a_pos"])


a_release.wait_ms = 1200


def a_check():
    sk = s["sk"]
    found = arcs()
    h.check(
        "releasing adds the arc",
        len(sk.Geometry) == s["a_count"] + 1 and len(found) == 1,
        (len(sk.Geometry), len(found)),
    )
    if not found:
        return
    index, arc = found[0]
    s["arc1"] = index
    if (arc.StartPoint - V(30, 0, 0)).Length < 1e-6:
        joint, free = arc.StartPoint, arc.EndPoint
    else:
        joint, free = arc.EndPoint, arc.StartPoint
    h.check(
        "the arc starts at B (joined to the line)",
        (joint - V(30, 0, 0)).Length < 1e-6,
        (arc.StartPoint, arc.EndPoint),
    )
    h.check(
        "its centre is on the normal through B (tangent to the level line)",
        abs(arc.Center.x - 30) < 1e-6,
        arc.Center,
    )
    expected = (20.0**2 + 15.0**2) / (2 * 15.0)  # the circle through B and P tangent at B
    h.check(
        "its radius fits the dragged point",
        abs(arc.Radius - expected) < 1.5 * s["px"],
        (arc.Radius, expected),
    )
    pointer = si.sketch_at(sk, s["a_pos"])
    # the grid snap is on: x lands on the 50 grid line, y (14.8) is left alone
    h.check(
        "its end is where the mouse was let go (x snapped to the grid)",
        abs(free.x - 50.0) < 1e-9 and abs(free.y - pointer.y) < 1e-6,
        (free, pointer),
    )
    added = cons()[s["a_cons"] :]
    tangent = [c for c in added if c[0] == "Tangent" and c[1] == s["line"] and c[3] == index]
    h.check(
        "Tangent between the line's end and the arc's end (joins them too)",
        len(tangent) == 1 and tangent[0][2] == 2 and tangent[0][4] in (1, 2),
        added,
    )
    h.check(
        "the arc is its own undo step",
        App.ActiveDocument.UndoNames[0] == "Tangent arc",
        App.ActiveDocument.UndoNames[:3],
    )
    h.check(
        "sketch solves cleanly",
        not sk.ConflictingConstraints
        and not sk.RedundantConstraints
        and not sk.MalformedConstraints,
    )
    s["free1"] = free


def a_chain_goes_on():
    approach(V(58, 20, 0), V(1.0, 1.0, 0))
    from sciforge import sketch_mode

    coords, _ = sketch_mode.find_node(h.view().getSceneGraph(), "EditCurvesCoordinate")
    points = coords.point.getValues(0) if coords is not None else []
    start = points[0].getValue() if len(points) == 2 else None
    free = s.get("free1", V(0, 0, 0))
    h.check(
        "the next line starts at the arc's end",
        start is not None and abs(start[0] - free.x) < 1e-3 and abs(start[1] - free.y) < 1e-3,
        (start, free),
    )
    h.check("the line tool is still running", si.drawing())


# == undo / redo ========================================================================
def a_undo():
    h.press("z", CTRL)


a_undo.wait_ms = 1200


def a_undone():
    sk = s["sk"]
    h.check(
        "one Ctrl+Z takes the arc back",
        len(sk.Geometry) == s["a_count"] and not arcs(),
        (len(sk.Geometry), App.ActiveDocument.RedoNames[:3]),
    )
    h.check("...and the line stays", len(si.lines(sk)) == 2)
    h.press("y", CTRL)


a_undone.wait_ms = 1200


def a_redone():
    sk = s["sk"]
    tangent = [c for c in cons() if c[0] == "Tangent"]
    h.check(
        "Ctrl+Y brings the arc and its tangency back",
        len(arcs()) == 1 and len(tangent) == 1,
        (len(arcs()), tangent),
    )


# == a plain click on the chain's point adds nothing =====================================
def b_plain_click():
    s["b_count"] = len(s["sk"].Geometry)
    free = s.get("free1", V(50, 15, 0))
    pos = press_at(g(free))
    release_at(pos)


b_plain_click.wait_ms = 900


def b_check():
    h.check(
        "a plain click on the chain's point adds nothing (no drag)",
        len(s["sk"].Geometry) == s["b_count"],
        len(s["sk"].Geometry),
    )
    h.check(
        "...and the tool still waits for the line's end",
        si.drawing() and infer_state().get("arc") is None,
    )


# == an arc from the arc's end, snapped onto another line's end ============================
def c_press():
    s["c_count"] = len(s["sk"].Geometry)
    s["c_cons"] = len(s["sk"].Constraints)
    press_at(g(s.get("free1", V(50, 15, 0))))


def c_drag():
    # the end of the reference line, a little off: the arc's end snaps onto it
    s["c_pos"] = drag_to(g(V(70 + 0.3, 45 - 0.3, 0)))
    state = infer_state()
    h.check(
        "dragging from the arc's end shows another arc",
        state.get("arc") == "dragging" and bool(state.get("overlay", {}).get("preview")),
        state.get("arc"),
    )
    shot("2-arc-from-arc")


def c_release():
    release_at(s["c_pos"])


c_release.wait_ms = 1200


def c_check():
    sk = s["sk"]
    found = arcs()
    h.check(
        "the second arc was added",
        len(found) == 2 and len(sk.Geometry) == s["c_count"] + 1,
        (len(found), len(sk.Geometry)),
    )
    if len(found) != 2:
        return
    first = sk.Geometry[s["arc1"]]
    index, arc = found[-1]
    s["arc2"] = index
    joint = s["free1"]
    # tangent to the first arc at the joint: both centres on the normal through it
    a = (first.Center - joint).normalize()
    b = (arc.Center - joint).normalize()
    h.check(
        "the second arc is tangent to the first (centres in line through the joint)",
        abs(abs(a.dot(b)) - 1.0) < 1e-6,
        (first.Center, arc.Center, joint),
    )
    ends = [arc.StartPoint, arc.EndPoint]
    h.check("it starts at the first arc's end", any((p - joint).Length < 1e-6 for p in ends), ends)
    h.check(
        "its end snapped onto the reference line's end",
        any((p - V(70, 45, 0)).Length < 1e-6 for p in ends),
        ends,
    )
    added = cons()[s["c_cons"] :]
    h.check(
        "Tangent between the two arcs",
        any(c[0] == "Tangent" and c[1] == s["arc1"] and c[3] == index for c in added),
        added,
    )
    h.check(
        "Coincident with the reference line's end",
        any(
            c[0] == "Coincident" and c[1] == index and c[3] == s["ref"] and c[4] == 1 for c in added
        ),
        added,
    )
    h.check(
        "sketch solves cleanly",
        not sk.ConflictingConstraints
        and not sk.RedundantConstraints
        and not sk.MalformedConstraints,
    )
    esc()


# == a plain line and a typed length still work ============================================
def d_line():
    line_key()


def d_start():
    si.click(g(V(-40, 30, 0)))


def d_end():
    s["d_count"] = len(s["sk"].Geometry)
    si.click(g(V(-10, 30, 0)))


def d_check():
    sk = s["sk"]
    h.check(
        "a plain click still makes a straight line",
        len(sk.Geometry) == s["d_count"] + 1 and sk.Geometry[-1].TypeId == "Part::GeomLineSegment",
        sk.Geometry[-1].TypeId,
    )


def d_type():
    s["d2_count"] = len(s["sk"].Geometry)
    si.type_text("25", enter=False)
    si.move_towards(g(V(10, 30, 0)), V(1, 0, 0))


def d_enter():
    si.key(QtCore.Qt.Key_Return)


d_enter.wait_ms = 1000


def d_typed_check():
    sk = s["sk"]
    line = sk.Geometry[-1]
    h.check(
        "a typed length still draws the line",
        len(sk.Geometry) == s["d2_count"] + 1 and line.TypeId == "Part::GeomLineSegment",
    )
    if line.TypeId == "Part::GeomLineSegment":
        h.check(
            "25 mm long, as typed",
            abs((line.EndPoint - line.StartPoint).Length - 25.0) < 1e-6,
            line,
        )


def finish():
    esc()
    sk = s["sk"]
    h.check("sketch has no errors", not sk.MalformedConstraints and not sk.ConflictingConstraints)
    shot("3-end")
    h.ribbon("Finish Sketch")


h.run(
    "sketch_tangent_arc",
    si.watched(
        [
            new_design,
            create_sketch,
            pick_xy,
            reference,
            line_key,
            line_a,
            line_b,
            press_without_moving,
            chained,
            a_press,
            a_drag,
            a_release,
            a_check,
            a_chain_goes_on,
            a_undo,
            a_undone,
            a_redone,
            b_plain_click,
            b_check,
            c_press,
            c_drag,
            c_release,
            c_check,
            d_line,
            d_start,
            d_end,
            d_check,
            d_type,
            d_enter,
            d_typed_check,
            finish,
        ]
    ),
)
