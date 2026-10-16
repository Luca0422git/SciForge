# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's sketch inference while drawing lines (sciforge/sketch_infer.py), with real
mouse moves and clicks. The reference lines are put in the sketch first; every line
under test is drawn with L and the mouse.

A  Ctrl (Fusion: no snapping, no automatic constraints while held). L, click a start,
   then with Ctrl held move to and click just beside the end of a line, 0.6 degrees off
   level: the point is exactly where the mouse was (FreeCAD alone snaps to 5-degree
   steps with Ctrl), no coincident, no horizontal constraint. The same without Ctrl:
   coincident and horizontal. With Ctrl only on the second click of a line that starts
   on a point, the start keeps its coincident.
B  Guides: hover the end of a line, move to where the new end is straight below it,
   3 pixels off: a dashed guide shows from that point to the pointer; click: the new
   end's x is the hovered end's x and a Vertical (point to point) constraint holds it.
   The free coordinate keeps the grid snap.
C  Perpendicular: from the end of a slanted line, a line at 87 degrees to it: the
   right-angle mark shows; click: exactly 90 degrees, Perpendicular constraint. One
   Ctrl+Z takes the inferred constraint back with FreeCAD's automatic ones, Ctrl+Y
   brings them back. A line from a free point ending on the slanted line at about 88
   degrees: it ends on that line at exactly 90 degrees.
D  Level within 4 degrees (FreeCAD alone: 2): 3.5 degrees off level becomes Horizontal;
   6.8 degrees stays free.
E  Parallel to a hovered line: off by default (nothing added); switched on, a line 1.5
   degrees off a hovered line becomes Parallel.
G  A typed length wins over a guide: L, click, type 25, then point near a hovered
   point's guide: no guide shows (the line would not end on it), Enter: a 25 mm line,
   no alignment constraint.
F  The same guide on a sketch on the XZ plane (turned and placed in 3D).
"""

import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import sketch_input as si

V = App.Vector
s = {}
SNAP = "User parameter:BaseApp/Preferences/Mod/Sketcher/Snap"
INFER = "User parameter:BaseApp/Preferences/Mod/SciForge/SketchInference"
CTRL = QtCore.Qt.ControlModifier


def session():
    from sciforge import sketch_mode

    return sketch_mode.current()


def infer_state():
    sess = session()
    return sess.infer.state() if sess is not None and sess.infer is not None else {}


def g(point):
    """Sketch point -> global 3D point (the sketch is on XY, but be exact)."""
    return s["sk"].getGlobalPlacement().multVec(point)


def cons(sk=None):
    sk = sk or s["sk"]
    return [(c.Type, c.First, c.FirstPos, c.Second, c.SecondPos) for c in sk.Constraints]


def on(index):
    """Constraints that involve geometry `index`."""
    return [c for c in cons() if index in (c[1], c[3])]


def newest_line():
    lines = si.lines(s["sk"])
    return lines[-1] if lines else (None, None)


def esc():
    h.press(QtCore.Qt.Key_Escape)


def line_key():
    h.press("l")


def degrees_between(a, b):
    c = a.dot(b) / (a.Length * b.Length)
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def rotated(v, deg):
    r = math.radians(deg)
    return V(v.x * math.cos(r) - v.y * math.sin(r), v.x * math.sin(r) + v.y * math.cos(r), 0)


def move(point):
    """Move the mouse to a 3D point. The screen's own pointer goes there too: under the
    test's virtual screen it otherwise stays elsewhere, and hover events from it (or a
    tool putting the pointer "back where the hand is") would land at that other spot."""
    from PySide import QtGui

    pos = h.screen_point(point)
    QtGui.QCursor.setPos(h.gl_widget().mapToGlobal(pos))
    h.move(pos)


def shot(name):
    """A screenshot once the 3D view has redrawn the guides."""
    from PySide6 import QtTest

    QtTest.QTest.qWait(300)
    h.shot(name)


def hover(point):
    """Rest the mouse on a sketch point, coming from the side (acquires it)."""
    for f in (2.0, 1.0, 0.0):
        move(g(point + V(1.0, 0.6, 0) * f))
    from PySide6 import QtTest

    QtTest.QTest.qWait(80)


# -- setup ------------------------------------------------------------------------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("SketchInfer")
    h.fit()


def create_sketch():
    h.ribbon("Create Sketch")


def pick_xy():
    pl.click_square("XY_Plane")  # where the square shows (was 12, -8, 0)


def reference_lines():
    import Part

    sk = h.in_sketch()
    s["sk"] = sk
    h.check("sketch open", sk is not None)
    h.check("Fusion sketch mode with inference", session() is not None and session().infer)
    refs = {
        "A1": (V(40, 20, 0), V(40, 35, 0)),
        "A2": (V(40, -20, 0), V(40, -35, 0)),
        "A3": (V(-40, -50, 0), V(-25, -50, 0)),
        "B": (V(52.3, 3.1, 0), V(61.7, 8.6, 0)),
        "C": (V(35.3, -45.2, 0), V(55.3, -33.2, 0)),
        "E": (V(95.3, 2.1, 0), V(115.3, 14.1, 0)),
    }
    s["ref"] = {}
    for name, (a, b) in refs.items():
        s["ref"][name] = sk.addGeometry(Part.LineSegment(a, b))
    App.ActiveDocument.recompute()
    s["px"] = si.mm_per_pixel(sk)
    h.check("about 0.1-0.5 mm per pixel", 0.05 < s["px"] < 1.0, s["px"])
    shot("0-start")


# == A: Ctrl =========================================================================
def a_line():
    line_key()


def a_start():
    # Ctrl from the first click: the start stays where it is clicked too (without Ctrl
    # FreeCAD's grid snap, 1/5 of the 10 mm grid, put it on y = 20 and the line came out
    # level or nearly so, depending on the screen's pixel scale).
    s["a_start_pos"] = si.click_held(g(V(5.5, 21.3, 0)), CTRL)


def a_ctrl_end():
    # beside the end (40, 20) of line A1 (FreeCAD would snap to it), 0.6 degrees off level
    s["a_count"] = len(s["sk"].Constraints)
    s["a_pos"] = si.click_held(g(V(40.5, 20.35, 0)), CTRL)


def a_ctrl_check():
    sk = s["sk"]
    index, line = newest_line()
    expected = si.sketch_at(sk, s["a_pos"])
    h.check("A: the Ctrl line was drawn", index is not None and index > s["ref"]["E"])
    h.check(
        "A: with Ctrl the end is exactly where the mouse was (no snap, no 5-degree step)",
        line is not None and si.vnear(line.EndPoint, expected, 1e-6),
        (line and line.EndPoint, expected),
    )
    angle = math.degrees(
        math.atan2(line.EndPoint.y - line.StartPoint.y, line.EndPoint.x - line.StartPoint.x)
    )
    start = si.sketch_at(sk, s["a_start_pos"])
    h.check(
        "A: with Ctrl the start is exactly where the mouse was",
        line is not None and si.vnear(line.StartPoint, start, 1e-6),
        (line and line.StartPoint, start),
    )
    h.check(
        "A: the Ctrl line keeps its small angle (not leveled, not a 5-degree step)",
        0.5 < abs(angle) < 4.0,
        (angle, line.StartPoint, line.EndPoint, s["px"]),
    )
    added = cons()[s["a_count"] :]
    h.check(
        "A: with Ctrl no coincident and no horizontal constraint",
        not [c for c in added if c[0] in ("Coincident", "Horizontal", "PointOnObject")],
        added,
    )
    h.check("A: FreeCAD's snapping is back on", App.ParamGet(SNAP).GetBool("Snap", True))
    h.check("A: automatic constraints are back on", bool(sk.ViewObject.Autoconstraints))
    s["a_line"] = index
    shot("1-ctrl")


def a2_restart():
    esc()


def a2_line():
    line_key()


def a2_start():
    si.click(g(V(5.5, -21.3, 0)))


def a2_end():
    s["a2_count"] = len(s["sk"].Constraints)
    si.click(g(V(40.5, -19.65, 0)))


def a2_check():
    index, line = newest_line()
    ref = s["ref"]["A2"]
    added = cons()[s["a2_count"] :]
    h.check(
        "A: without Ctrl the end is coincident with the line's end",
        ("Coincident", index, 2, ref, 1) in added or ("Coincident", ref, 1, index, 2) in added,
        added,
    )
    h.check(
        "A: without Ctrl the line is horizontal", ("Horizontal", index, 0, -2000, 0) in added, added
    )


def a3_restart():
    esc()


def a3_line():
    line_key()


def a3_start_on_point():
    # starts on the end of line A3 (coincident), then Ctrl on the second click only
    s["a3_count"] = len(s["sk"].Constraints)
    si.click(g(V(-25, -50, 0)))


def a3_ctrl_end():
    si.click_held(g(V(-10.3, -49.6, 0)), CTRL)


def a3_check():
    index, line = newest_line()
    ref = s["ref"]["A3"]
    added = cons()[s["a3_count"] :]
    h.check(
        "A: Ctrl on the second click keeps the start's coincident",
        ("Coincident", index, 1, ref, 2) in added or ("Coincident", ref, 2, index, 1) in added,
        added,
    )
    h.check(
        "A: ...and adds nothing for the Ctrl point (no horizontal)",
        not [c for c in added if c[0] == "Horizontal"],
        added,
    )


# == B: guides =======================================================================
def b_restart():
    esc()


def b_line():
    line_key()


def b_start():
    si.click(g(V(45.5, 27.7, 0)))


def b_hover_end():
    hover(V(61.7, 8.6, 0))
    state = infer_state()
    h.check(
        "B: hovering the end of line B acquires it",
        (s["ref"]["B"], 2) in state.get("acquired", []),
        state.get("acquired"),
    )


def b_near_guide():
    # straight below the hovered end, 3 pixels off to the right
    s["b_raw"] = V(61.7 + 3 * s["px"], 20.6, 0)
    for f in (3.0, 2.0, 1.0, 0.0):
        move(g(s["b_raw"] + V(-1.0, 1.5, 0) * f))
    state = infer_state()
    guides = state.get("overlay", {}).get("guides", [])
    ok = len(guides) == 1 and si.near(guides[0][0][0], 61.7, 1e-6)
    ok = ok and si.near(guides[0][1][0], 61.7, 1e-6) and si.near(guides[0][0][1], 8.6, 1e-6)
    h.check("B: a dashed guide runs from the hovered end down to the pointer", ok, guides)
    shot("2-guide")


def b_click():
    s["b_count"] = len(s["sk"].Constraints)
    h.click(g(s["b_raw"]))


def b_check():
    sk = s["sk"]
    index, line = newest_line()
    ref = s["ref"]["B"]
    h.check(
        "B: the new end's x equals the hovered end's x",
        line is not None and abs(line.EndPoint.x - 61.7) < 1e-9,
        line and line.EndPoint,
    )
    h.check(
        "B: line B did not move",
        si.vnear(sk.Geometry[ref].EndPoint, V(61.7, 8.6, 0), 1e-9),
        sk.Geometry[ref].EndPoint,
    )
    added = cons()[s["b_count"] :]
    h.check(
        "B: a Vertical constraint keeps the two points aligned",
        ("Vertical", index, 2, ref, 2) in added,
        added,
    )
    h.check(
        "B: the free coordinate kept the grid snap (y = 20)",
        abs(line.EndPoint.y - 20.0) < 1e-6,
        line.EndPoint,
    )
    h.check(
        "B: sketch solves cleanly", not sk.MalformedConstraints and not sk.ConflictingConstraints
    )


# == C: perpendicular ===============================================================
def c_restart():
    esc()


def c_line():
    line_key()


def c_start_on_end():
    si.click(g(V(55.3, -33.2, 0)))  # the end of the slanted line C


def c_near_90():
    u = V(20, 12, 0)
    u.normalize()
    n = V(-u.y, u.x, 0)
    s["c_raw"] = V(55.3, -33.2, 0) + rotated(n, -3.0) * 25.0
    for f in (3.0, 2.0, 1.0, 0.0):
        move(g(s["c_raw"] + V(1.0, 0.6, 0) * f))
    state = infer_state()
    last = state.get("last")
    marks = state.get("overlay", {}).get("marks", [])
    h.check("C: perpendicular inferred", last is not None and last.kind == "perp", last)
    h.check(
        "C: the right-angle mark shows at the corner", len(marks) == 1 and len(marks[0]) == 3, marks
    )
    shot("3-perpendicular")


def c_click():
    s["c_count"] = len(s["sk"].Constraints)
    h.click(g(s["c_raw"]))


def c_check():
    sk = s["sk"]
    index, line = newest_line()
    ref = s["ref"]["C"]
    s["c_line"] = index
    added = cons()[s["c_count"] :]
    h.check(
        "C: Perpendicular constraint added",
        ("Perpendicular", index, 0, ref, 0) in added,
        (added, App.ActiveDocument.UndoNames[:4]),
    )
    other = sk.Geometry[ref]
    a = line.EndPoint - line.StartPoint
    b = other.EndPoint - other.StartPoint
    h.check(
        "C: exactly 90 degrees", abs(degrees_between(a, b) - 90.0) < 1e-5, degrees_between(a, b)
    )
    h.check(
        "C: starts on the slanted line's end (coincident)",
        ("Coincident", index, 1, ref, 2) in added or ("Coincident", ref, 2, index, 1) in added,
        added,
    )
    h.check(
        "C: line C did not move",
        si.vnear(other.StartPoint, V(35.3, -45.2, 0), 1e-9)
        and si.vnear(other.EndPoint, V(55.3, -33.2, 0), 1e-9),
        (other.StartPoint, other.EndPoint),
    )


def c_stop():
    esc()


def c_undo():
    s["c_lines"] = len(si.lines(s["sk"]))
    h.press("z", CTRL)


c_undo.wait_ms = 1200


def c_undone():
    left = [c for c in on(s["c_line"]) if c[0] in ("Perpendicular", "Coincident")]
    h.check(
        "C: one Ctrl+Z takes back the inferred and the automatic constraints",
        not left,
        (left, App.ActiveDocument.UndoNames[:4], App.ActiveDocument.RedoNames[:4]),
    )
    h.check(
        "C: ...and keeps the line (FreeCAD's own step)",
        len(si.lines(s["sk"])) == s["c_lines"],
        len(si.lines(s["sk"])),
    )
    h.press("y", CTRL)


c_undone.wait_ms = 1200


def c_redone():
    found = [c for c in on(s["c_line"]) if c[0] in ("Perpendicular", "Coincident")]
    h.check(
        "C: one Ctrl+Y brings both back",
        len(found) == 2,
        (found, App.ActiveDocument.UndoNames[:4], App.ActiveDocument.RedoNames[:4]),
    )


def c2_line():
    line_key()


def c2_start():
    u = V(20, 12, 0)
    u.normalize()
    n = V(-u.y, u.x, 0)
    s["c2_foot"] = V(41.3, -41.6, 0)  # 30% along line C (its middle snaps elsewhere)
    s["c2_start"] = s["c2_foot"] + n * 18.0
    si.click(g(s["c2_start"]))


def c2_near_line():
    u = V(20, 12, 0)
    u.normalize()
    n = V(-u.y, u.x, 0)
    start = preview_start(s["c2_start"] - n * 5.0)
    s["c2_start"] = start
    foot = V(35.3, -45.2, 0) + u * (start - V(35.3, -45.2, 0)).dot(u)
    s["c2_foot"] = foot
    # 2 degrees off 90, a little above the line (within FreeCAD's pick radius)
    gap = (start - foot).Length
    s["c2_raw"] = foot + u * (gap * math.tan(math.radians(2.0))) + n * (1.5 * s["px"])
    for f in (3.0, 2.0, 1.0, 0.0):
        move(g(s["c2_raw"] + n * (f * 1.5)))
    last = infer_state().get("last")
    h.check(
        "C: ending on the line at about 90 degrees: perpendicular onto it",
        last is not None and last.kind == "perp" and last.on_line,
        last,
    )


def preview_start(towards):
    """Move the mouse a little (FreeCAD then draws the line from its first point) and
    read that first point."""
    from sciforge import sketch_mode

    from PySide6 import QtTest

    for attempt in range(5):
        move(g(towards + V(0.3 * attempt, 0, 0)))
        coords, _ = sketch_mode.find_node(h.view().getSceneGraph(), "EditCurvesCoordinate")
        points = coords.point.getValues(0) if coords is not None else []
        if len(points) == 2:
            p = points[0].getValue()
            return V(p[0], p[1], 0)
        QtTest.QTest.qWait(150)
    h.check("the line tool shows the line from its first point", False, len(points))
    return V(0, 0, 0)


def c2_click():
    s["c2_count"] = len(s["sk"].Constraints)
    h.click(g(s["c2_raw"]))


def c2_check():
    sk = s["sk"]
    index, line = newest_line()
    ref = s["ref"]["C"]
    added = cons()[s["c2_count"] :]
    h.check(
        "C2: Perpendicular constraint added", ("Perpendicular", index, 0, ref, 0) in added, added
    )
    h.check(
        "C2: the end lies on the slanted line",
        ("PointOnObject", index, 2, ref, 0) in added,
        added,
    )
    other = sk.Geometry[ref]
    a = line.EndPoint - line.StartPoint
    b = other.EndPoint - other.StartPoint
    h.check(
        "C2: exactly 90 degrees", abs(degrees_between(a, b) - 90.0) < 1e-5, degrees_between(a, b)
    )


# == D: level within 4 degrees =====================================================
def d_restart():
    esc()


def d_line():
    line_key()


def d_start():
    si.click(g(V(5.5, 51.7, 0)))  # the grid takes it to (5.5, 50)


def d_end():
    s["d_count"] = len(s["sk"].Constraints)
    si.click(g(V(45.5, 50.0 + 40.0 * math.tan(math.radians(3.5)), 0)))


def d_check():
    index, line = newest_line()
    added = cons()[s["d_count"] :]
    h.check(
        "D: 3.5 degrees off level becomes Horizontal",
        ("Horizontal", index, 0, -2000, 0) in added,
        added,
    )
    h.check("D: ...and is level", abs(line.EndPoint.y - line.StartPoint.y) < 1e-9, line)


def d2_restart():
    esc()


def d2_line():
    line_key()


def d2_start():
    si.click(g(V(5.5, 61.7, 0)))


def d2_end():
    s["d2_count"] = len(s["sk"].Constraints)
    si.click(g(V(45.5, 60.0 + 40.0 * math.tan(math.radians(6.8)), 0)))


def d2_check():
    index, line = newest_line()
    added = cons()[s["d2_count"] :]
    h.check(
        "D: 6.8 degrees stays free",
        not [c for c in added if c[0] in ("Horizontal", "Vertical")],
        added,
    )


# == E: parallel ======================================================================
def _e_draw_end(start_y):
    u = rotated(V(20, 12, 0), 1.5)
    u.normalize()
    start = preview_start(V(92.7, start_y, 0) + u * 5.0)
    return start + u * 22.0


def e_restart():
    esc()


def e_line():
    line_key()


def e_hover():
    hover(V(105.3, 8.1, 0))  # the middle of line E


def e_start():
    si.click(g(V(92.7, 23.3, 0)))


def e_move():
    s["e_raw"] = _e_draw_end(23.3)
    for f in (3.0, 2.0, 1.0, 0.0):
        move(g(s["e_raw"] + V(0.6, -1.0, 0) * f))


def e_click():
    s["e_count"] = len(s["sk"].Constraints)
    h.click(g(s["e_raw"]))


def e_check_off():
    added = cons()[s["e_count"] :]
    h.check(
        "E: parallel is off by default: nothing added",
        not [c for c in added if c[0] == "Parallel"],
        added,
    )


def e_switch_on():
    esc()
    App.ParamGet(INFER).SetBool("Parallel", True)


def e2_line():
    line_key()


def e2_hover():
    hover(V(105.3, 8.1, 0))


def e2_start():
    si.click(g(V(92.7, 33.3, 0)))


def e2_move():
    s["e2_raw"] = _e_draw_end(33.3)
    for f in (3.0, 2.0, 1.0, 0.0):
        move(g(s["e2_raw"] + V(0.6, -1.0, 0) * f))
    last = infer_state().get("last")
    h.check(
        "E: switched on, parallel is inferred", last is not None and last.kind == "parallel", last
    )


def e2_click():
    s["e2_count"] = len(s["sk"].Constraints)
    h.click(g(s["e2_raw"]))


def e2_check():
    sk = s["sk"]
    index, line = newest_line()
    ref = s["ref"]["E"]
    added = cons()[s["e2_count"] :]
    App.ParamGet(INFER).RemBool("Parallel")
    h.check("E: Parallel constraint added", ("Parallel", index, 0, ref, 0) in added, added)
    other = sk.Geometry[ref]
    a = line.EndPoint - line.StartPoint
    b = other.EndPoint - other.StartPoint
    h.check("E: exactly parallel", degrees_between(a, b) < 1e-5, degrees_between(a, b))


def finish():
    esc()
    sk = s["sk"]
    h.check("sketch has no errors", not sk.MalformedConstraints and not sk.ConflictingConstraints)
    h.check(
        "sketch has no redundant constraints", not sk.RedundantConstraints, sk.RedundantConstraints
    )
    h.check("snapping still on", App.ParamGet(SNAP).GetBool("Snap", True))
    shot("4-end")


# == G: a typed length wins over a guide ===========================================
def g_restart():
    esc()


def g_line():
    line_key()


def g_hover():
    hover(V(-40, -50, 0))  # the start of line A3


def g_start():
    si.click(g(V(-55.5, -21.7, 0)))


def g_type_25():
    s["g_count"] = len(s["sk"].Constraints)
    s["g_lines"] = len(si.lines(s["sk"]))
    si.type_text("25", enter=False)


def g_near_guide():
    # straight above the start of line A3, 3 pixels off, about 30 mm from the start
    raw = V(-40 + 3 * s["px"], -45.0, 0)
    for f in (3.0, 2.0, 1.0, 0.0):
        move(g(raw + V(-1.0, 1.5, 0) * f))
    guides = infer_state().get("overlay", {}).get("guides", [])
    h.check(
        "G: with a typed length no guide shows (the end would not be on it)", not guides, guides
    )


def g_enter():
    si.key(QtCore.Qt.Key_Return)


g_enter.wait_ms = 1000


def g_check():
    index, line = newest_line()
    added = cons()[s["g_count"] :]
    h.check("G: Enter drew the line", len(si.lines(s["sk"])) == s["g_lines"] + 1)
    h.check(
        "G: 25 mm long, as typed",
        line is not None and abs((line.EndPoint - line.StartPoint).Length - 25.0) < 1e-6,
        line,
    )
    h.check(
        "G: no alignment constraint",
        not [c for c in added if c[0] in ("Vertical", "Horizontal") and c[3] >= 0],
        added,
    )


# == F: a sketch on the XZ plane (turned and placed in 3D) ==============================
def f_finish():
    h.ribbon("Finish Sketch")


def f_create():
    h.check("the XY sketch closed", h.in_sketch() is None, h.in_sketch())
    h.ribbon("Create Sketch")


def f_pick_xz():
    pl.click_square("XZ_Plane")  # where the square shows (was 10, 0, 18)


def f_reference():
    import Part

    sk = h.in_sketch()
    h.check("a second sketch is open", sk is not None and sk is not s["sk"], sk)
    if sk is None:
        return
    s["sk"] = sk
    normal = sk.getGlobalPlacement().Rotation.multVec(V(0, 0, 1))
    h.check("it is on the XZ plane", abs(abs(normal.y) - 1.0) < 1e-9, normal)
    s["ref"]["F"] = sk.addGeometry(Part.LineSegment(V(12.3, 3.1, 0), V(21.7, 8.6, 0)))
    App.ActiveDocument.recompute()
    s["px"] = si.mm_per_pixel(sk)


def f_line():
    line_key()


def f_start():
    si.click(g(V(5.5, 27.7, 0)))


def f_hover():
    hover(V(21.7, 8.6, 0))


def f_near_guide():
    s["f_raw"] = V(21.7 + 3 * s["px"], 20.6, 0)
    for f in (3.0, 2.0, 1.0, 0.0):
        move(g(s["f_raw"] + V(-1.0, 1.5, 0) * f))
    guides = infer_state().get("overlay", {}).get("guides", [])
    h.check(
        "F: on the XZ sketch the guide shows too",
        len(guides) == 1 and si.near(guides[0][1][0], 21.7, 1e-6),
        guides,
    )
    shot("5-xz-guide")


def f_click():
    s["f_count"] = len(s["sk"].Constraints)
    h.click(g(s["f_raw"]))


def f_check():
    index, line = newest_line()
    added = cons()[s["f_count"] :]
    h.check(
        "F: the new end's x equals the hovered end's x",
        line is not None and abs(line.EndPoint.x - 21.7) < 1e-9,
        line and line.EndPoint,
    )
    h.check("F: Vertical constraint", ("Vertical", index, 2, s["ref"]["F"], 2) in added, added)
    esc()


h.run(
    "sketch_infer",
    si.watched(
        [
            new_design,
            create_sketch,
            pick_xy,
            reference_lines,
            a_line,
            a_start,
            a_ctrl_end,
            a_ctrl_check,
            a2_restart,
            a2_line,
            a2_start,
            a2_end,
            a2_check,
            a3_restart,
            a3_line,
            a3_start_on_point,
            a3_ctrl_end,
            a3_check,
            b_restart,
            b_line,
            b_start,
            b_hover_end,
            b_near_guide,
            b_click,
            b_check,
            c_restart,
            c_line,
            c_start_on_end,
            c_near_90,
            c_click,
            c_check,
            c_stop,
            c_undo,
            c_undone,
            c_redone,
            c2_line,
            c2_start,
            c2_near_line,
            c2_click,
            c2_check,
            d_restart,
            d_line,
            d_start,
            d_end,
            d_check,
            d2_restart,
            d2_line,
            d2_start,
            d2_end,
            d2_check,
            e_restart,
            e_line,
            e_hover,
            e_start,
            e_move,
            e_click,
            e_check_off,
            e_switch_on,
            e2_line,
            e2_hover,
            e2_start,
            e2_move,
            e2_click,
            e2_check,
            g_restart,
            g_line,
            g_hover,
            g_start,
            g_type_25,
            g_near_guide,
            g_enter,
            g_check,
            finish,
            f_finish,
            f_create,
            f_pick_xz,
            f_reference,
            f_line,
            f_start,
            f_hover,
            f_near_guide,
            f_click,
            f_check,
        ]
    ),
)
