# SPDX-License-Identifier: LGPL-2.1-or-later
"""The sketch inference and the Line chain around undo, tool restarts and odd views
(fixes of the 2026-10-13 review of sf/sketch-feel), with real mouse input.

U1 Tangent arc, Ctrl+Z, then two clicks: FreeCAD's line tool used to keep the point
   it was started on (the arc's end, gone with the undo) and joined the next line to
   itself ("Both points are equal", every solve failed after that). Now the tool is
   started again from the end of the last line; the two clicks make two lines, no
   constraint joins a curve to itself, the sketch solves, Finish Sketch is clean.
U2 The plain chain: a line, Ctrl+Z twice (its constraints, then the line), two clicks:
   a new line, nothing joined to itself.
U3 L again halfway through a line: the first click of the restarted tool is where it
   was clicked, not pulled level with the forgotten old start.
U4 The pointer leaving the 3D view takes the guides and marks with it.
U5 A sketch on a turned plane (attachment offset rotated 30 degrees) seen from a tilted
   view: the chain still goes on from the line's end point (Coincident, not a point
   somewhere on the line), and a press there arms the tangent arc.
U6 A tool started outside SciForge (FreeCAD's own command after the circle tool): the
   guides know the rectangle from its preview.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
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


def self_joins():
    return [c for c in cons() if c[0] == "Coincident" and c[1] == c[3]]


def esc():
    h.press(QtCore.Qt.Key_Escape)


def move(point):
    pos = h.screen_point(point)
    QtGui.QCursor.setPos(h.gl_widget().mapToGlobal(pos))
    h.move(pos)


def approach(raw, towards=V(-1.0, 1.5, 0)):
    for f in (3.0, 2.0, 1.0, 0.0):
        move(g(raw + towards * f))


def press_at(point):
    pos = h.screen_point(point)
    move(point)
    QtTest.QTest.qWait(80)
    QtTest.QTest.mousePress(h.gl_widget(), QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, pos)
    QtWidgets.QApplication.processEvents()
    return pos


def drag_to(point, steps=8):
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
            QtCore.Qt.NoModifier,
        )
        QtWidgets.QApplication.sendEvent(widget, event)
        QtWidgets.QApplication.processEvents()
    return end


def release_at(pos):
    QtTest.QTest.mouseRelease(h.gl_widget(), QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, pos)
    QtWidgets.QApplication.processEvents()


def lines():
    return si.lines(s["sk"])


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("SketchInferUndo")
    h.fit()


def create_sketch():
    h.ribbon("Create Sketch")


def pick_xy():
    pl.click_square("XY_Plane")  # where the square shows (was 12, -8, 0)


def ready():
    sk = h.in_sketch()
    s["sk"] = sk
    h.check("sketch open", sk is not None)
    s["px"] = si.mm_per_pixel(sk)


# == U1: tangent arc, undo, click, click ==================================================
def u1_line():
    h.press("l")


def u1_a():
    si.click(g(V(0, 0, 0)))


def u1_b():
    si.click(g(V(30, 0, 0)))


def u1_arc():
    approach(V(38, 6, 0), V(1.0, 1.0, 0))
    press_at(g(V(30, 0, 0)))
    pos = drag_to(g(V(50, 15, 0)))
    release_at(pos)


u1_arc.wait_ms = 1200


def u1_undo():
    arcs = [i for i, geo in enumerate(s["sk"].Geometry) if geo.TypeId == "Part::GeomArcOfCircle"]
    h.check(
        "U1: the arc was added",
        len(arcs) == 1 and App.ActiveDocument.UndoNames[0] == "Tangent arc",
        (arcs, App.ActiveDocument.UndoNames[:2]),
    )
    h.press("z", CTRL)


u1_undo.wait_ms = 1200


def u1_click1():
    arcs = [i for i, geo in enumerate(s["sk"].Geometry) if geo.TypeId == "Part::GeomArcOfCircle"]
    h.check("U1: Ctrl+Z took the arc back", not arcs)
    s["u1_count"] = len(s["sk"].Geometry)
    si.click(g(V(50, 40, 0)))


def u1_click2():
    si.click(g(V(70, 40, 0)))


def u1_check():
    sk = s["sk"]
    added = [sk.Geometry[i] for i in range(s["u1_count"], len(sk.Geometry))]
    h.check(
        "U1: the two clicks after the undo made two lines",
        len(added) == 2 and all(geo.TypeId == "Part::GeomLineSegment" for geo in added),
        [geo.TypeId for geo in added],
    )
    h.check("U1: no constraint joins a curve to itself", not self_joins(), self_joins())
    if added:
        h.check(
            "U1: the chain went on from the line's end",
            si.vnear(added[0].StartPoint, V(30, 0, 0), 1e-6),
            added[0].StartPoint,
        )
    h.check(
        "U1: the sketch solves",
        sk.solve() == 0 and not sk.ConflictingConstraints and not sk.MalformedConstraints,
    )
    esc()


# == U2: the plain chain, undone twice =======================================================
def u2_line():
    h.press("l")


def u2_c():
    si.click(g(V(0, -40, 0)))


def u2_d():
    si.click(g(V(30, -40, 0)))


def u2_undo1():
    h.press("z", CTRL)


u2_undo1.wait_ms = 1200


def u2_undo2():
    h.press("z", CTRL)


u2_undo2.wait_ms = 1200


def u2_click1():
    s["u2_count"] = len(s["sk"].Geometry)
    h.check(
        "U2: the line is gone after two Ctrl+Z",
        not [i for i, geo in lines() if abs(geo.StartPoint.y + 40) < 1e-6],
        [geo.StartPoint for _, geo in lines()],
    )
    si.click(g(V(40, -40, 0)))


def u2_click2():
    si.click(g(V(60, -40, 0)))


def u2_check():
    sk = s["sk"]
    added = [sk.Geometry[i] for i in range(s["u2_count"], len(sk.Geometry))]
    h.check(
        "U2: a new line after the undos",
        len(added) == 1 and added[0].TypeId == "Part::GeomLineSegment",
        [geo.TypeId for geo in added],
    )
    h.check("U2: nothing joined to itself", not self_joins(), self_joins())
    h.check("U2: the sketch solves", sk.solve() == 0 and not sk.ConflictingConstraints)
    esc()


# == U3: L again halfway through a line ====================================================
def u3_line():
    h.press("l")


def u3_start():
    si.click(g(V(20, -80, 0)))


def u3_move():
    approach(V(40, -70, 0), V(-1.0, -1.0, 0))


def u3_line_again():
    h.press("l")


def u3_click():
    # 3 degrees up from the old start (within the level snap if the old start were kept),
    # clear of the grid lines (the grid snaps within 2 mm of them)
    s["u3_raw"] = V(90.5, -76.3, 0)
    approach(s["u3_raw"], V(1.0, 1.0, 0))
    state = infer_state()
    h.check(
        "U3: the restarted tool waits for its first click (no direction)",
        state.get("step") in (0, None)
        and (state.get("last") is None or state.get("last").kind is None),
        (state.get("step"), state.get("last")),
    )
    si.click(g(s["u3_raw"]))


def u3_end():
    si.click(g(V(80, -60, 0)))


def u3_check():
    index, line = lines()[-1]
    h.check(
        "U3: the new line starts where it was clicked, not level with the old start",
        line is not None and abs(line.StartPoint.y + 76.3) < 1.5 * s["px"],
        line and line.StartPoint,
    )
    esc()


# == U4: the pointer leaves the view ======================================================
def u4_line():
    h.press("l")


def u4_start():
    si.click(g(V(-60, -20, 0)))


def u4_near_level():
    approach(V(-20, -20 + 40 * math.tan(math.radians(3.0)), 0), V(1.0, 1.0, 0))
    marks = infer_state().get("overlay", {}).get("marks", [])
    h.check("U4: the level mark shows", len(marks) == 1, marks)
    gl = h.gl_widget()
    QtWidgets.QApplication.sendEvent(gl, QtCore.QEvent(QtCore.QEvent.Type.Leave))
    QtWidgets.QApplication.processEvents()
    state = infer_state()
    h.check(
        "U4: leaving the view takes the mark and guides away",
        not state.get("overlay", {}).get("marks") and not state.get("overlay", {}).get("guides"),
        state.get("overlay"),
    )
    h.check("U4: ...and forgets the inference", state.get("last") is None, state.get("last"))
    esc()


# == U5: a turned sketch plane seen from a tilted view =====================================
def u5_turn():
    sk = s["sk"]
    sk.AttachmentOffset = App.Placement(V(0, 0, 0), App.Rotation(V(0, 0, 1), 30))
    App.ActiveDocument.recompute()
    view = h.view()
    q = view.getCameraOrientation()
    view.setCameraOrientation(q.multiply(App.Rotation(V(1, 0, 0), 14)))
    QtWidgets.QApplication.processEvents()
    normal = sk.getGlobalPlacement().Rotation.multVec(V(0, 0, 1))
    direction = view.getViewDirection()
    deg = math.degrees(math.acos(max(-1.0, min(1.0, abs(normal.dot(direction))))))
    h.check("U5: the view is tilted against the sketch plane", 8 < deg < 20, deg)
    s["px"] = si.mm_per_pixel(sk)


def u5_line():
    h.press("l")


def u5_a():
    si.click(g(V(-40, 40, 0)))


def u5_b():
    s["u5_count"] = len(s["sk"].Geometry)
    si.click(g(V(-10, 52, 0)))


def u5_c():
    si.click(g(V(10, 70, 0)))


def u5_check():
    sk = s["sk"]
    new = [
        i
        for i in range(s["u5_count"], len(sk.Geometry))
        if sk.Geometry[i].TypeId == "Part::GeomLineSegment"
    ]
    h.check("U5: two lines were chained on the turned plane", len(new) == 2, new)
    if len(new) != 2:
        return
    first, second = sk.Geometry[new[0]], sk.Geometry[new[1]]
    h.check(
        "U5: the second line starts exactly at the first one's end",
        (second.StartPoint - first.EndPoint).Length < 1e-9,
        (first.EndPoint, second.StartPoint),
    )
    h.check(
        "U5: ...joined by a Coincident, not put somewhere on the line",
        ("Coincident", new[1], 1, new[0], 2) in cons()
        or ("Coincident", new[0], 2, new[1], 1) in cons(),
        [c for c in cons() if new[1] in (c[1], c[3])],
    )
    s["u5_end"] = second.EndPoint


def u5_press():
    end = s.get("u5_end", V(10, 70, 0))
    approach(V(end.x + 8, end.y + 4, 0), V(1.0, 1.0, 0))
    pos = press_at(g(end))
    h.check(
        "U5: a press on the chain's point arms the tangent arc on the tilted view",
        infer_state().get("arc") == "armed",
        infer_state().get("arc"),
    )
    release_at(pos)
    esc()


# == U6: a tool started outside SciForge ===================================================
def u6_circle_then_rect():
    h.press("c")
    Gui.runCommand("Sketcher_CreateRectangle")  # FreeCAD's own command, not SciForge's


def u6_corner():
    si.click(g(V(-60, 60, 0)))


def u6_move():
    approach(V(-30, 80, 0), V(1.0, 1.0, 0))
    h.check(
        "U6: the preview tells the guides it is a rectangle",
        infer_state().get("kind") == "rect",
        infer_state().get("kind"),
    )
    esc()


def finish():
    sk = s["sk"]
    h.check("sketch has no errors", not sk.MalformedConstraints and not sk.ConflictingConstraints)
    h.ribbon("Finish Sketch")


def finished():
    sk = s["sk"]
    h.check(
        "Finish Sketch left a valid sketch",
        h.in_sketch() is None and "Invalid" not in sk.State,
        sk.State,
    )


h.run(
    "sketch_infer_undo",
    si.watched(
        [
            new_design,
            create_sketch,
            pick_xy,
            ready,
            u1_line,
            u1_a,
            u1_b,
            u1_arc,
            u1_undo,
            u1_click1,
            u1_click2,
            u1_check,
            u2_line,
            u2_c,
            u2_d,
            u2_undo1,
            u2_undo2,
            u2_click1,
            u2_click2,
            u2_check,
            u3_line,
            u3_start,
            u3_move,
            u3_line_again,
            u3_click,
            u3_end,
            u3_check,
            u4_line,
            u4_start,
            u4_near_level,
            u5_turn,
            u5_line,
            u5_a,
            u5_b,
            u5_c,
            u5_check,
            u5_press,
            u6_circle_then_rect,
            u6_corner,
            u6_move,
            finish,
            finished,
        ]
    ),
)
