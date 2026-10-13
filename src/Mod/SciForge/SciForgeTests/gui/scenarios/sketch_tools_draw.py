# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Midpoint Line, 2-Point Circle, Tangent Arc and Edge Polygon (SciForge's own
sketch tools, sketch_draw_tools.py), drawn with real clicks, moves and keys.

Midpoint Line (CREATE menu): click the middle (-35, 25), click (-15, 26): the end snaps
level (within 4 degrees), the line runs (-55, 25) -> (-15, 25), a point sits at its
middle held by Symmetric, Horizontal is added. Typed values: click the middle, type
30 Tab 45 Enter: the line is 30 long at 45 degrees, both become dimensions. The tool
repeats until Esc; Esc halfway adds nothing.
2-Point Circle: two clicks are the ends of a diameter (centre (35, 15), r 10); a click on
the Midpoint Line's end puts the circle through it (PointOnObject); a typed diameter
becomes a Diameter dimension.
Tangent Arc: click the end of the first line, then (5, 45): the arc leaves the line's end
along the line (Tangent end to end) and ends at the click.
Edge Polygon: the edge (55, -25) -> (75, -25), type 4 for the sides, click above: a
square on that edge, equal sides, the edge Horizontal.
Undo takes back one shape, Redo brings it again; OK in the right-click menu ends a tool.
"""

import math

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import sketch_tools_steps as st

V = App.Vector
s = st.s
CLICK = 0.6  # a click lands within a pixel or two of the point aimed at (mm)


# == Midpoint Line ===========================================================================
def ml_open():
    si.menu_item("CREATE", "Midpoint Line")


def ml_open_check():
    h.check("Midpoint Line runs", st.tool_title() == "Midpoint Line", st.tool_title())
    h.check("the cursor is a cross while it runs", st.cross_cursor())
    h.check("no pop-up", not h.popups(), h.popups())
    s["count"] = len(st.sketch().Geometry)


def ml_middle():
    st.click(V(-35, 25, 0))


def ml_move():
    st.hover(V(-15, 26, 0))
    drawn = st.preview()
    curves = drawn.get("curves", [])
    ok = len(curves) == 1 and len(curves[0]) == 2
    h.check("the preview is the line through the middle", ok, curves)
    if ok:
        a, b = curves[0]
        h.check(
            "it runs from (-55, 25) to (-15, 25)",
            st.vnear(V(a[0], a[1], 0), V(-55, 25, 0), CLICK)
            and st.vnear(V(b[0], b[1], 0), V(-15, 25, 0), CLICK),
            (a, b),
        )
        h.check("...exactly level (the 1 mm off is snapped)", a[1] == b[1], (a, b))
    f = st.field("length")
    h.check(
        "the length box shows about 40",
        f is not None and st.near(f.value or 0, 40.0, 2 * CLICK),
        f and f.value,
    )
    h.check(
        "the length and angle boxes are on the view",
        any(t.startswith("L ") and t.endswith("mm") for t in st.box_texts())
        and "A 0 deg" in st.box_texts(),
        st.box_texts(),
    )
    h.check("a level mark shows", len(drawn.get("marks", [])) >= 1, drawn.get("marks"))
    h.shot("1-midpoint-preview")


def ml_click():
    st.click(V(-15, 26, 0), towards=V(0, 0, 0))


def ml_check():
    sk = st.sketch()
    new = st.new_geometry(s["count"])
    lines = st.of_type(new, "Part::GeomLineSegment")
    points = st.of_type(new, "Part::GeomPoint")
    h.check(
        "one line and its middle point",
        len(lines) == 1 and len(points) == 1,
        [g.TypeId for _, g in new],
    )
    if lines:
        i, line = lines[0]
        s["ml_line"] = i
        ends = sorted([(line.StartPoint.x, line.StartPoint.y), (line.EndPoint.x, line.EndPoint.y)])
        h.check(
            "the line runs from (-55, 25) to (-15, 25)",
            st.vnear(V(*ends[0], 0), V(-55, 25, 0), CLICK)
            and st.vnear(V(*ends[1], 0), V(-15, 25, 0), CLICK),
            ends,
        )
        s["ml_end"] = V(*ends[1], 0)  # the line's right end, exactly
        cons = st.constraints_of(i)
        h.check(
            "Horizontal was added",
            ("Horizontal", i, 0, -2000, 0) in cons or "Horizontal" in st.types(cons),
            cons,
        )
        if points:
            p = points[0][0]
            where = V(sk.Geometry[p].X, sk.Geometry[p].Y, 0)
            middle = (line.StartPoint + line.EndPoint) * 0.5
            h.check("the point is exactly at the line's middle", st.vnear(where, middle), where)
            h.check("...where the first click was", st.vnear(where, V(-35, 25, 0), CLICK), where)
            h.check(
                "Symmetric holds it at the middle",
                any(c[0] == "Symmetric" for c in st.constraints_of(p)),
                st.constraints_of(p),
            )
    h.check(
        "the tool goes on (Fusion repeats)", st.tool_title() == "Midpoint Line", st.tool_title()
    )
    st.sketch_ok("midpoint line")
    s["count"] = len(sk.Geometry)


def ml_typed_middle():
    st.click(V(-35, -15, 0))


def ml_typed_values():
    st.hover(V(-25, -5, 0))
    st.keys("30\t45\n")


def ml_typed_check():
    sk = st.sketch()
    new = st.new_geometry(s["count"])
    lines = st.of_type(new, "Part::GeomLineSegment")
    h.check("typed: one line", len(lines) == 1, [g.TypeId for _, g in new])
    if lines:
        i, line = lines[0]
        h.check("typed: 30 long", st.near(line.length(), 30.0, 1e-6), line.length())
        d = line.EndPoint - line.StartPoint
        angle = math.degrees(math.atan2(d.y, d.x)) % 180.0
        h.check("typed: at 45 degrees", st.near(angle, 45.0, 1e-6), angle)
        middle = (line.StartPoint + line.EndPoint) * 0.5
        h.check("typed: its middle is the click", st.vnear(middle, V(-35, -15, 0), CLICK), middle)
        cons = st.types(st.constraints_of(i))
        h.check("typed: the length is a dimension", "Distance" in cons, cons)
        h.check("typed: the angle is a dimension", "Angle" in cons, cons)
    st.sketch_ok("typed midpoint line")
    s["count"] = len(sk.Geometry)


def ml_esc_halfway():
    st.click(V(5, -35, 0))
    st.hover(V(15, -35, 0))
    st.esc()


def ml_esc_check():
    h.check(
        "Esc halfway adds nothing",
        len(st.sketch().Geometry) == s["count"],
        len(st.sketch().Geometry),
    )
    h.check("Esc ends the tool", st.tool() is None, st.tool_title())
    h.check("the cursor is back to the arrow", not st.cross_cursor())


# == 2-Point Circle =============================================================================
def c2_open():
    si.menu_item("CREATE", "2-Point Circle")


def c2_first():
    h.check("2-Point Circle runs", st.tool_title() == "2-Point Circle", st.tool_title())
    st.click(V(25, 15, 0))


def c2_second():
    st.hover(V(45, 15, 0))
    curves = st.preview().get("curves", [])
    h.check("a circle previews", len(curves) == 1 and len(curves[0]) > 20, len(curves))
    st.click(V(45, 15, 0), towards=V(0, 0, 0))


def c2_check():
    new = st.new_geometry(s["count"])
    circles = st.of_type(new, "Part::GeomCircle")
    h.check("one circle", len(circles) == 1, [g.TypeId for _, g in new])
    if circles:
        c = circles[0][1]
        h.check("centre (35, 15)", st.vnear(c.Center, V(35, 15, 0), CLICK), c.Center)
        h.check("radius 10", st.near(c.Radius, 10.0, CLICK), c.Radius)
    s["count"] = len(st.sketch().Geometry)


def c2_through_point():
    # the first click on the Midpoint Line's end (-15, 25): the circle passes through it
    st.click(V(-15, 25, 0))
    st.click(V(-15, 5, 0), towards=V(0.3, 1, 0))


def c2_through_check():
    new = st.new_geometry(s["count"])
    circles = st.of_type(new, "Part::GeomCircle")
    h.check("the second circle", len(circles) == 1, [g.TypeId for _, g in new])
    if circles:
        i, c = circles[0]
        cons = st.constraints_of(i)
        h.check(
            "it passes through the line's end (PointOnObject)",
            any(t[0] == "PointOnObject" and t[1] == s["ml_line"] for t in cons),
            cons,
        )
        end = st.sketch().Geometry[s["ml_line"]].EndPoint
        start = st.sketch().Geometry[s["ml_line"]].StartPoint
        right = end if end.x > start.x else start
        h.check(
            "...and does, exactly",
            st.near((right - c.Center).Length, c.Radius, 1e-6),
            ((right - c.Center).Length, c.Radius),
        )
    st.sketch_ok("2-point circle")
    s["count"] = len(st.sketch().Geometry)


def c2_typed():
    st.click(V(25, -25, 0))
    st.hover(V(35, -25, 0))
    st.keys("16\n")


def c2_typed_check():
    new = st.new_geometry(s["count"])
    circles = st.of_type(new, "Part::GeomCircle")
    h.check("typed: a circle", len(circles) == 1, [g.TypeId for _, g in new])
    if circles:
        i, c = circles[0]
        h.check("typed: diameter 16", st.near(c.Radius, 8.0, 1e-6), c.Radius)
        h.check("typed: towards the pointer", st.vnear(c.Center, V(33, -25, 0), CLICK), c.Center)
        h.check("typed: a Diameter dimension", "Diameter" in st.types(st.constraints_of(i)))
    s["count"] = len(st.sketch().Geometry)
    st.esc()


# == Tangent Arc ===============================================================================
def ta_open():
    si.menu_item("CREATE", "Tangent Arc")


def ta_start_wrong():
    h.check("Tangent Arc runs", st.tool_title() == "Tangent Arc", st.tool_title())
    st.click(V(5, 5, 0))  # empty space: refused
    h.check("a click in empty space does not start an arc", st.tool().step == 0, st.tool().step)


def ta_start():
    st.click(V(-15, 25, 0))


def ta_end():
    st.hover(V(5, 45, 0))
    curves = st.preview().get("curves", [])
    h.check("an arc previews", len(curves) == 1 and len(curves[0]) > 10, len(curves))
    st.click(V(5, 45, 0), towards=V(0, 0, 0))


def ta_check():
    new = st.new_geometry(s["count"])
    arcs = st.of_type(new, "Part::GeomArcOfCircle")
    h.check("one arc", len(arcs) == 1, [g.TypeId for _, g in new])
    if arcs:
        i, arc = arcs[0]
        s["ta_arc"] = i
        ends = [arc.StartPoint, arc.EndPoint]
        line = st.sketch().Geometry[s["ml_line"]]
        joint = line.EndPoint if line.EndPoint.x > line.StartPoint.x else line.StartPoint
        h.check("it starts at the line's end", any(st.vnear(e, joint, 1e-6) for e in ends), ends)
        h.check("it ends at the click", any(st.vnear(e, V(5, 45, 0), CLICK) for e in ends), ends)
        cons = st.constraints_of(i)
        h.check(
            "tangent to the line end to end",
            any(c[0] == "Tangent" and s["ml_line"] in (c[1], c[3]) for c in cons),
            cons,
        )
        # the centre lies on the normal to the (level) line at its end
        h.check(
            "its centre is straight above the line's end",
            st.near(arc.Center.x, joint.x, 1e-6) and arc.Center.y > joint.y,
            (arc.Center, joint),
        )
    st.sketch_ok("tangent arc")
    s["count"] = len(st.sketch().Geometry)


def ta_ok_menu():
    """OK in the right-click menu ends the tool (3 o'clock)."""
    h.click(st.g(V(65, 45, 0)), button=QtCore.Qt.RightButton)
    QtCore.QTimer.singleShot(200, lambda: si.marking_slot("OK"))


def ta_ok_check():
    h.check("OK in the right-click menu ended the tool", st.tool() is None, st.tool_title())


# == Edge Polygon ===================================================================
def ep_open():
    si.menu_item("CREATE", "Edge Polygon")


def ep_first():
    h.check("Edge Polygon runs", st.tool_title() == "Edge Polygon", st.tool_title())
    st.click(V(55, -25, 0))


def ep_second():
    st.click(V(75, -25, 0), towards=V(0, 0, 0))


def ep_sides():
    st.hover(V(65, -15, 0))
    st.keys("4")
    h.check("the sides box takes 4", "Sides 4" in " ".join(st.box_texts()), st.box_texts())


def ep_place():
    st.enter()


def ep_check():
    new = st.new_geometry(s["count"])
    lines = st.of_type(new, "Part::GeomLineSegment", construction=False)
    h.check("a square: 4 sides", len(lines) == 4, [g.TypeId for _, g in new])
    corners = sorted({(round(g.StartPoint.x, 6), round(g.StartPoint.y, 6)) for _, g in lines})
    want = [(55.0, -25.0), (55.0, -5.0), (75.0, -25.0), (75.0, -5.0)]
    h.check(
        "on the clicked edge, above it",
        len(corners) == 4
        and all(st.vnear(V(*c, 0), V(*w, 0), 2 * CLICK) for c, w in zip(corners, want)),
        corners,
    )
    sides = [g.length() for _, g in lines]
    h.check("exactly square: equal sides", max(sides) - min(sides) < 1e-6, sides)
    h.check(
        "...with the clicked edge exactly level",
        any(abs(g.StartPoint.y - g.EndPoint.y) < 1e-9 and g.StartPoint.y < -20 for _, g in lines),
        [(g.StartPoint, g.EndPoint) for _, g in lines],
    )
    all_cons = [c.Type for c in st.sketch().Constraints]
    h.check("equal sides", all_cons.count("Equal") >= 3, all_cons)
    st.sketch_ok("edge polygon")
    s["count"] = len(st.sketch().Geometry)
    h.shot("2-shapes")


# == undo / redo ========================================================================
def undo_square():
    st.esc()
    st.undo()


def undo_check():
    h.check(
        "one Ctrl+Z takes the square back",
        len(st.sketch().Geometry) < s["count"],
        len(st.sketch().Geometry),
    )
    s["after_undo"] = len(st.sketch().Geometry)


def redo_square():
    st.redo()


def redo_check():
    h.check(
        "Ctrl+Y brings it back", len(st.sketch().Geometry) == s["count"], len(st.sketch().Geometry)
    )
    st.sketch_ok("after redo")


def finish():
    h.ribbon("Finish Sketch")


h.run(
    "sketch_tools_draw",
    si.watched(
        st.start_steps("SketchToolsDraw")
        + [
            ml_open,
            ml_open_check,
            ml_middle,
            ml_move,
            ml_click,
            ml_check,
            ml_typed_middle,
            ml_typed_values,
            ml_typed_check,
            ml_esc_halfway,
            ml_esc_check,
            c2_open,
            c2_first,
            c2_second,
            c2_check,
            c2_through_point,
            c2_through_check,
            c2_typed,
            c2_typed_check,
            ta_open,
            ta_start_wrong,
            ta_start,
            ta_end,
            ta_check,
            ta_ok_menu,
            ta_ok_check,
            ep_open,
            ep_first,
            ep_second,
            ep_sides,
            ep_place,
            ep_check,
            undo_square,
            undo_check,
            redo_square,
            redo_check,
            finish,
        ]
    ),
)
