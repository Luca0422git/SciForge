# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's alignment guides in the other drawing tools (sciforge/sketch_infer.py),
with real mouse moves and clicks: rectangle, circle, centre-point arc, polygon and
slot. Reference lines are put in the sketch first; a point of one is hovered
("acquired"), then the shape's point is placed 3 pixels off the dashed guide from it.

R  Rectangle: the first corner straight below a hovered end (guide shown; after the
   click the corner's x is exactly that point's x, a Vertical point-to-point
   constraint holds it); the second corner level with another hovered point
   (Horizontal). One Ctrl+Z takes the inferred constraints back with FreeCAD's own.
C  Circle: the centre level with a hovered point (Horizontal on the centre); the rim
   point straight below another hovered point: snapped (the radius follows), no
   constraint (the rim point is no sketch vertex).
A  Centre point arc: the centre on a vertical guide, the start on a horizontal one;
   the end gets no guide (it lies on the circle at the pointer's angle).
P  Inscribed polygon: the centre level with a hovered point, a corner straight below
   another.
S  Slot (SciForge's own centre-to-centre slot, sketch_draw_tools.py): the first centre
   on the end of a slanted line, the second at about 87 degrees to it: the right-angle
   mark shows, the slot is exactly perpendicular to that line (Perpendicular constraint
   on the slot's construction centre line).
T  Speed: about 2 ms of SciForge's own work per mouse move on a 400-curve sketch.
"""

import math
import time

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

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
    """Come to the sketch point `raw` in a few steps (as a hand does)."""
    for f in (3.0, 2.0, 1.0, 0.0):
        move(g(raw + towards * f))


def acquired_point(point):
    """True when the inference's newest acquired vertex is `point` (sketch coordinates)."""
    try:
        sess = session()
        keys = sess.infer.acquired
        keyed = sess.infer._geometry()[3]
        if not keys or keys[-1] not in keyed:
            return False
        x, y = keyed[keys[-1]][0], keyed[keys[-1]][1]
        return si.near(x, point.x, 1e-6) and si.near(y, point.y, 1e-6)
    except Exception:
        return False


def hover(point):
    """Rest the mouse on a sketch point, coming from the side (acquires it). A hand sends
    many moves while it comes to rest; a few are sent here, and the acquire is checked:
    GitHub's slower machine once dropped a single move onto the point (CI #104) while the
    tool was still starting, and no guide followed."""
    from PySide6 import QtTest

    for f in (2.0, 1.0, 0.5, 0.2, 0.0):
        move(g(point + V(1.0, 0.6, 0) * f))
    QtTest.QTest.qWait(80)
    for _ in range(4):
        if acquired_point(point):
            return
        QtTest.QTest.qWait(150)
        for f in (0.3, 0.1, 0.0):
            move(g(point + V(1.0, 0.6, 0) * f))
        QtTest.QTest.qWait(80)


def shot(name):
    from PySide6 import QtTest

    QtTest.QTest.qWait(300)
    h.shot(name)


def guides():
    return infer_state().get("overlay", {}).get("guides", [])


def guide_check(label, anchor, axis, others=()):
    """One guide from `anchor` (or one of `others`, points on the same guide line)
    to the pointer, along `axis`."""
    found = guides()
    anchors = [anchor] + list(others)
    ok = len(found) == 1 and any(
        si.near(found[0][0][0], a.x, 1e-6) and si.near(found[0][0][1], a.y, 1e-6) for a in anchors
    )
    if ok and axis == "x":
        ok = si.near(found[0][1][0], anchor.x, 1e-6)
    elif ok:
        ok = si.near(found[0][1][1], anchor.y, 1e-6)
    state = infer_state()
    h.check(
        label,
        ok,
        (
            found,
            state.get("kind"),
            state.get("step"),
            state.get("last"),
            state.get("acquired"),
            state.get("placed"),
        ),
    )


def new_geometry(before):
    sk = s["sk"]
    return list(range(before, len(sk.Geometry)))


# -- setup ------------------------------------------------------------------------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("SketchInferTools")
    h.fit()


def create_sketch():
    h.ribbon("Create Sketch")


def pick_xy():
    h.click(V(12, -8, 0))


def reference_lines():
    import Part

    sk = h.in_sketch()
    s["sk"] = sk
    h.check("sketch open", sk is not None)
    refs = {
        "P1": (V(40, 20, 0), V(40, 35, 0)),
        "P2": (V(-60, 70, 0), V(-45, 70, 0)),
        "P3": (V(70, -20, 0), V(85, -20, 0)),
        "P4": (V(-30, -60, 0), V(-30, -45, 0)),
        "C": (V(35.3, -45.2, 0), V(55.3, -33.2, 0)),
    }
    s["ref"] = {}
    for name, (a, b) in refs.items():
        s["ref"][name] = sk.addGeometry(Part.LineSegment(a, b))
    App.ActiveDocument.recompute()
    s["px"] = si.mm_per_pixel(sk)
    h.check("about 0.1-0.5 mm per pixel", 0.05 < s["px"] < 1.0, s["px"])


# == R: rectangle =====================================================================
def r_key():
    h.press("r")


def r_hover():
    hover(V(40, 35, 0))


def r_near():
    s["r_raw"] = V(40 + 3 * s["px"], 55.6, 0)
    approach(s["r_raw"])
    h.check("R: the rectangle tool is known to the guides", infer_state().get("kind") == "rect")
    guide_check("R: a guide from the hovered end down to the first corner", V(40, 35, 0), "x")
    shot("1-rect-guide")


def r_click1():
    s["r_before"] = len(s["sk"].Geometry)
    s["r_cons"] = len(s["sk"].Constraints)
    h.click(g(s["r_raw"]))


def r_hover2():
    hover(V(-45, 70, 0))


def r_near2():
    s["r_raw2"] = V(75.3, 70 + 3 * s["px"], 0)
    approach(s["r_raw2"], V(1.0, 1.5, 0))
    guide_check("R: a guide from the second hovered end to the second corner", V(-45, 70, 0), "y")


def r_click2():
    h.click(g(s["r_raw2"]))


def r_check():
    sk = s["sk"]
    new = new_geometry(s["r_before"])
    h.check("R: the rectangle's 4 lines were added", len(new) == 4, new)
    if len(new) != 4:
        return
    lines = [sk.Geometry[i] for i in new]
    corner1 = lines[0].StartPoint
    corner3 = lines[1].EndPoint
    h.check(
        "R: the first corner's x is exactly the hovered end's", abs(corner1.x - 40) < 1e-9, corner1
    )
    h.check(
        "R: the second corner's y is exactly the other end's", abs(corner3.y - 70) < 1e-9, corner3
    )
    added = cons()[s["r_cons"] :]
    h.check(
        "R: Vertical between the first corner and the hovered end",
        ("Vertical", new[0], 1, s["ref"]["P1"], 2) in added,
        added,
    )
    h.check(
        "R: Horizontal between the second corner and the other end",
        ("Horizontal", new[1], 2, s["ref"]["P2"], 2) in added,
        added,
    )
    h.check(
        "R: the sketch solves cleanly",
        not sk.ConflictingConstraints and not sk.RedundantConstraints,
    )
    s["r_new"] = new


def r_undo():
    esc()
    s["r_count"] = len(s["sk"].Geometry)
    h.press("z", CTRL)


r_undo.wait_ms = 1200


def r_undone():
    sk = s["sk"]
    left = [
        c for c in cons() if c[0] in ("Vertical", "Horizontal") and c[3] >= 0 and c[1] in s["r_new"]
    ]
    h.check(
        "R: one Ctrl+Z takes the inferred alignments back",
        not left,
        (left, App.ActiveDocument.UndoNames[:4]),
    )
    # FreeCAD's rectangle is one step with its own constraints (this one had none of
    # FreeCAD's automatic ones): the glued step takes the rectangle with it, like
    # Fusion's one Ctrl+Z per shape
    h.check(
        "R: ...and the rectangle is gone with it (one Ctrl+Z per shape, like Fusion)",
        len(sk.Geometry) == s["r_count"] - 4,
        (len(sk.Geometry), App.ActiveDocument.RedoNames[:4]),
    )
    h.press("y", CTRL)


r_undone.wait_ms = 1200


def r_redone():
    back = [
        c for c in cons() if c[0] in ("Vertical", "Horizontal") and c[3] >= 0 and c[1] in s["r_new"]
    ]
    h.check("R: Ctrl+Y brings the rectangle and its alignments back", len(back) == 2, back)
    h.check("R: ...all 4 lines", len(s["sk"].Geometry) == s["r_count"], len(s["sk"].Geometry))


# == C: circle ========================================================================
def c_key():
    h.press("c")


def c_hover():
    hover(V(85, -20, 0))


def c_near():
    s["c_raw"] = V(60.4, -20 + 3 * s["px"], 0)
    approach(s["c_raw"], V(-1.0, 1.5, 0))
    h.check("C: the circle tool is known to the guides", infer_state().get("kind") == "circle")
    guide_check("C: a guide from the hovered end to the centre (level)", V(85, -20, 0), "y")


def c_click1():
    s["c_before"] = len(s["sk"].Geometry)
    s["c_cons"] = len(s["sk"].Constraints)
    h.click(g(s["c_raw"]))


def c_hover2():
    hover(V(70, -20, 0))


def c_near2():
    s["c_raw2"] = V(70 + 3 * s["px"], -45.3, 0)
    approach(s["c_raw2"])
    guide_check("C: a guide from the hovered start down to the rim point", V(70, -20, 0), "x")
    shot("2-circle-guide")


def c_click2():
    h.click(g(s["c_raw2"]))


def c_check():
    sk = s["sk"]
    new = new_geometry(s["c_before"])
    circles = [i for i in new if sk.Geometry[i].TypeId == "Part::GeomCircle"]
    h.check("C: the circle was added", len(new) == 1 and len(circles) == 1, new)
    if not circles:
        return
    circle = sk.Geometry[circles[0]]
    h.check(
        "C: the centre's y is exactly the hovered end's",
        abs(circle.Center.y + 20) < 1e-9,
        circle.Center,
    )
    added = cons()[s["c_cons"] :]
    h.check(
        "C: Horizontal between the centre and the hovered end",
        ("Horizontal", circles[0], 3, s["ref"]["P3"], 2) in added,
        added,
    )
    expected = (V(70, -45.3, 0) - circle.Center).Length
    h.check(
        "C: the rim point went onto the guide (the radius follows, within a pixel)",
        abs(circle.Radius - expected) < 1.5 * s["px"],
        (circle.Radius, expected),
    )
    h.check(
        "C: no constraint for the rim point (it is no vertex)",
        not [c for c in added if c[0] == "Vertical"],
        added,
    )


# == A: centre point arc ================================================================
def a_menu():
    esc()
    si.menu_item("CREATE", "Center Point Arc")


def a_hover():
    hover(V(40, 20, 0))


def a_near():
    s["a_raw"] = V(40 + 3 * s["px"], 5.5, 0)
    approach(s["a_raw"], V(1.0, -1.5, 0))
    h.check("A: the arc tool is known to the guides", infer_state().get("kind") == "arc")
    guide_check("A: a guide from the hovered start down to the centre", V(40, 20, 0), "x")


def a_click1():
    s["a_before"] = len(s["sk"].Geometry)
    s["a_cons"] = len(s["sk"].Constraints)
    h.click(g(s["a_raw"]))


def a_hover2():
    hover(V(40, 35, 0))


def a_near2():
    s["a_raw2"] = V(62.1, 35 + 3 * s["px"], 0)
    approach(s["a_raw2"], V(1.0, 1.5, 0))
    guide_check("A: a guide from the hovered end to the arc's start (level)", V(40, 35, 0), "y")
    shot("3-arc-guide")


def a_click2():
    h.click(g(s["a_raw2"]))


def a_end():
    approach(V(12.0, 40.0, 0), V(-1.0, 1.0, 0))
    state = infer_state()
    h.check(
        "A: the arc's end gets no guide (it rides on the circle)",
        state.get("step") is None and not guides(),
        (state.get("step"), guides()),
    )
    h.click(g(V(12.0, 40.0, 0)))


def a_check():
    sk = s["sk"]
    new = new_geometry(s["a_before"])
    arcs = [i for i in new if sk.Geometry[i].TypeId == "Part::GeomArcOfCircle"]
    h.check("A: the arc was added", len(new) == 1 and len(arcs) == 1, new)
    if not arcs:
        return
    arc = sk.Geometry[arcs[0]]
    h.check(
        "A: the centre's x is exactly the hovered start's",
        abs(arc.Center.x - 40) < 1e-9,
        arc.Center,
    )
    ends = [p for p in (arc.StartPoint, arc.EndPoint) if abs(p.y - 35) < 1e-9]
    h.check(
        "A: the arc's start is exactly level with the hovered end",
        len(ends) == 1,
        (arc.StartPoint, arc.EndPoint),
    )
    added = cons()[s["a_cons"] :]
    h.check(
        "A: Vertical between the centre and the hovered start",
        ("Vertical", arcs[0], 3, s["ref"]["P1"], 1) in added,
        added,
    )
    h.check(
        "A: Horizontal between the start and the hovered end",
        any(c == ("Horizontal", arcs[0], pos, s["ref"]["P1"], 2) for c in added for pos in (1, 2)),
        added,
    )


# == P: polygon ========================================================================
def p_menu():
    esc()
    si.menu_item("CREATE", "Inscribed Polygon")


def p_hover():
    hover(V(-30, -60, 0))


def p_near():
    s["p_raw"] = V(-5.4, -60 + 3 * s["px"], 0)
    approach(s["p_raw"], V(1.0, 1.5, 0))
    h.check("P: the polygon tool is known to the guides", infer_state().get("kind") == "polygon")
    guide_check("P: a guide from the hovered start to the centre (level)", V(-30, -60, 0), "y")


def p_click1():
    s["p_before"] = len(s["sk"].Geometry)
    s["p_cons"] = len(s["sk"].Constraints)
    h.click(g(s["p_raw"]))


def p_hover2():
    hover(V(-30, -45, 0))


def p_near2():
    s["p_raw2"] = V(-30 + 3 * s["px"], -75.3, 0)
    approach(s["p_raw2"], V(1.0, -1.5, 0))
    # both ends of P4 were hovered and both are at x = -30: the nearer one gives the guide
    guide_check(
        "P: a guide from a hovered point of P4 down to the corner",
        V(-30, -45, 0),
        "x",
        [V(-30, -60, 0)],
    )
    shot("4-polygon-guide")


def p_click2():
    h.click(g(s["p_raw2"]))


def p_check():
    sk = s["sk"]
    new = new_geometry(s["p_before"])
    circles = [i for i in new if sk.Geometry[i].TypeId == "Part::GeomCircle"]
    lines = [i for i in new if sk.Geometry[i].TypeId == "Part::GeomLineSegment"]
    h.check(
        "P: six sides and the construction circle were added",
        len(lines) == 6 and len(circles) == 1,
        new,
    )
    if not circles or len(lines) != 6:
        return
    circle = sk.Geometry[circles[0]]
    # the polygon's own constraints (equal sides, corners on the circle) make the solver
    # spread the half-pixel correction: within a millionth of a millimetre
    h.check(
        "P: the centre's y is the hovered start's", abs(circle.Center.y + 60) < 1e-6, circle.Center
    )
    corner = sk.Geometry[lines[0]].StartPoint
    h.check("P: the corner's x is the hovered end's", abs(corner.x + 30) < 1e-6, corner)
    added = cons()[s["p_cons"] :]
    h.check(
        "P: Horizontal between the centre and the hovered start",
        ("Horizontal", circles[0], 3, s["ref"]["P4"], 1) in added,
        added,
    )
    # both ends of P4 are at x = -30: the guide takes the one nearer to the pointer
    h.check(
        "P: Vertical between the corner and a hovered point of P4",
        any(
            ("Vertical", line, pos, s["ref"]["P4"], ref_pos) in added
            for line, pos in ((lines[0], 1), (lines[5], 2))
            for ref_pos in (1, 2)
        ),
        added,
    )
    h.check(
        "P: the sketch solves cleanly",
        not sk.ConflictingConstraints and not sk.RedundantConstraints,
    )


# == S: slot ============================================================================
def slot_tool():
    from sciforge import sketch_draw

    return sketch_draw.current_tool()


def s_menu():
    esc()
    si.menu_item("CREATE", "Center to Center Slot")


def s_first():
    t = slot_tool()
    h.check(
        "S: SciForge's slot tool runs (Fusion's width box)",
        t is not None and t.title == "Center to Center Slot",
        t and t.title,
    )
    s["s_before"] = len(s["sk"].Geometry)
    s["s_cons"] = len(s["sk"].Constraints)
    approach(V(55.3, -33.2, 0), V(1.0, 0.6, 0))
    h.click(g(V(55.3, -33.2, 0)))  # the end of the slanted line C


def s_near():
    u = V(20, 12, 0)
    u.normalize()
    n = V(-u.y, u.x, 0)
    r = math.radians(-3.0)
    turned = V(n.x * math.cos(r) - n.y * math.sin(r), n.x * math.sin(r) + n.y * math.cos(r), 0)
    s["s_raw"] = V(55.3, -33.2, 0) + turned * 25.0
    approach(s["s_raw"], V(1.0, 0.6, 0))
    t = slot_tool()
    state = t.state() if t is not None else {}
    last = state.get("last")
    result = last.result if last is not None else None
    marks = state.get("preview", {}).get("marks", [])
    h.check(
        "S: the first centre sits on the end of line C",
        bool(state.get("snaps")) and state["snaps"][0].key is not None,
        state.get("snaps"),
    )
    h.check(
        "S: the slot's centre line at 87 degrees is made perpendicular",
        result is not None and result.kind == "perp",
        result and result.kind,
    )
    h.check(
        "S: the right-angle mark shows at the corner", len(marks) == 1 and len(marks[0]) == 3, marks
    )
    shot("5-slot-perpendicular")


def s_second():
    h.click(g(s["s_raw"]))


def s_width():
    u = V(20, 12, 0)
    u.normalize()
    n = V(-u.y, u.x, 0)
    point = V(55.3, -33.2, 0) + n * 12.0 + u * 6.0
    approach(point, V(0.5, 0.5, 0))
    t = slot_tool()
    drawn = t.state().get("preview", {}) if t is not None else {}
    h.check("S: the width click gets no guide", not drawn.get("guides"), drawn.get("guides"))
    h.click(g(point))


def s_check():
    sk = s["sk"]
    new = new_geometry(s["s_before"])
    lines = [
        i
        for i in new
        if sk.Geometry[i].TypeId == "Part::GeomLineSegment" and not sk.getConstruction(i)
    ]
    centre = [
        i for i in new if sk.Geometry[i].TypeId == "Part::GeomLineSegment" and sk.getConstruction(i)
    ]
    arcs = [i for i in new if sk.Geometry[i].TypeId == "Part::GeomArcOfCircle"]
    h.check(
        "S: the slot (2 arcs, 2 lines, a construction centre line) was added",
        len(lines) == 2 and len(arcs) == 2 and len(centre) == 1,
        new,
    )
    if len(lines) != 2 or len(centre) != 1:
        return
    added = cons()[s["s_cons"] :]
    perp = [c for c in added if c[0] == "Perpendicular" and s["ref"]["C"] in (c[1], c[3])]
    h.check(
        "S: Perpendicular between the slot's centre line and the slanted line",
        len(perp) == 1 and centre[0] in (perp[0][1], perp[0][3]),
        added,
    )
    side = sk.Geometry[lines[0]]
    other = sk.Geometry[s["ref"]["C"]]
    a = side.EndPoint - side.StartPoint
    b = other.EndPoint - other.StartPoint
    deg = math.degrees(math.acos(max(-1.0, min(1.0, a.dot(b) / (a.Length * b.Length)))))
    h.check("S: the sides exactly at 90 degrees", abs(deg - 90.0) < 1e-5, deg)
    h.check(
        "S: the slanted line did not move (within 10 nanometres)",
        si.vnear(other.EndPoint, V(55.3, -33.2, 0), 1e-5)
        and si.vnear(other.StartPoint, V(35.3, -45.2, 0), 1e-5),
        (other.StartPoint, other.EndPoint),
    )
    h.check(
        "S: the sketch solves cleanly",
        not sk.ConflictingConstraints and not sk.RedundantConstraints,
    )
    s["s_lines"] = lines + centre


def s_undo():
    esc()
    s["s_count"] = len(s["sk"].Geometry)
    h.press("z", CTRL)


s_undo.wait_ms = 1200


def s_undone():
    # SciForge's slot and the constraints it adds are one undo step (Fusion)
    left = [c for c in cons() if c[0] == "Perpendicular" and c[1] in s["s_lines"]]
    h.check(
        "S: one Ctrl+Z takes the slot back with its Perpendicular",
        not left and len(s["sk"].Geometry) == s["s_before"],
        (left, len(s["sk"].Geometry), s["s_before"], App.ActiveDocument.UndoNames[:4]),
    )


# == T: speed ========================================================================
def t_many_curves():
    import Part

    sk = s["sk"]
    geos = []
    for k in range(400):
        x = -150 + (k % 40) * 7.3
        y = -120 + (k // 40) * 6.1
        geos.append(Part.LineSegment(V(x, y, 0), V(x + 4.1, y + 2.3, 0)))
    sk.addGeometry(geos)
    App.ActiveDocument.recompute()
    h.press("l")


def t_measure():
    si.click(g(V(-100.5, 100.3, 0)))
    infer = session().infer
    widget = h.gl_widget()
    pts = [V(-100.5 + 30 + (k % 7) * 3.3, 100.3 + 10 + (k % 5) * 2.7, 0) for k in range(60)]
    total = 0.0
    for p in pts:
        pos = h.screen_point(g(p))
        event = QtGui.QMouseEvent(
            QtCore.QEvent.MouseMove,
            QtCore.QPointF(pos),
            QtCore.QPointF(widget.mapToGlobal(pos)),
            QtCore.Qt.NoButton,
            QtCore.Qt.NoButton,
            QtCore.Qt.NoModifier,
        )
        t0 = time.perf_counter()
        infer._plan(widget, event)
        total += time.perf_counter() - t0
    ms = total / len(pts) * 1000.0
    print(
        "[SciForge] sketch_infer_tools: %.2f ms per mouse move (inference) on a 400-curve sketch"
        % ms,
        flush=True,
    )
    h.check("T: under 10 ms of inference per mouse move on a 400-curve sketch", ms < 10.0, ms)
    esc()


def finish():
    sk = s["sk"]
    h.check("sketch has no errors", not sk.MalformedConstraints and not sk.ConflictingConstraints)
    h.ribbon("Finish Sketch")


h.run(
    "sketch_infer_tools",
    si.watched(
        [
            new_design,
            create_sketch,
            pick_xy,
            reference_lines,
            r_key,
            r_hover,
            r_near,
            r_click1,
            r_hover2,
            r_near2,
            r_click2,
            r_check,
            r_undo,
            r_undone,
            r_redone,
            c_key,
            c_hover,
            c_near,
            c_click1,
            c_hover2,
            c_near2,
            c_click2,
            c_check,
            a_menu,
            a_hover,
            a_near,
            a_click1,
            a_hover2,
            a_near2,
            a_click2,
            a_end,
            a_check,
            p_menu,
            p_hover,
            p_near,
            p_click1,
            p_hover2,
            p_near2,
            p_click2,
            p_check,
            s_menu,
            s_first,
            s_near,
            s_second,
            s_width,
            s_check,
            s_undo,
            s_undone,
            t_many_curves,
            t_measure,
            finish,
        ]
    ),
)
