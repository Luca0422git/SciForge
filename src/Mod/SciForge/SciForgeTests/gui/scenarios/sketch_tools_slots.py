# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's slots on SciForge's slot tool (sketch_draw_tools.LinearSlot / ThreePointArcSlot),
with real clicks and keys. The width is what is typed (Fusion: "specify the diameter of
the slot arcs"); FreeCAD's own slot tool asked for the end radius, so typing 10 made a
20 mm wide slot.

Center to Center Slot (CREATE > Slot): click (-55, 25) and (-15, 26) (snaps level), type
10, Enter: end arcs centred on the clicks, radius exactly 5, a Diameter dimension of 10,
the sides tangent to the ends, a construction centre line made Horizontal.
Overall Slot: click (5, 25) and (45, 25), type 8: the clicks are the slot's far ends (the
construction line from end to end touches both arcs at their tips), radius 4.
Center Point Slot: click the middle (-35, -25), then an end centre (-15, -25), type 6:
the other end centre mirrors it, a point at the middle held by Symmetric.
Three Point Arc Slot: end centres (5, -25), (45, -25), a point (25, -15) on the centre
arc (the circle through them: centre (25, -40), radius 25), type 6: outer arc radius 28,
inner 22, end caps radius 3, concentric outer and inner arcs.
Esc halfway adds nothing; Ctrl+Z takes one slot back.
"""

import FreeCAD as App

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import sketch_tools_steps as st

V = App.Vector
s = st.s
CLICK = 0.6


def parts(new):
    arcs = st.of_type(new, "Part::GeomArcOfCircle", construction=False)
    sides = st.of_type(new, "Part::GeomLineSegment", construction=False)
    centre_lines = st.of_type(new, "Part::GeomLineSegment", construction=True)
    return arcs, sides, centre_lines


def slot_shape_ok(name, arcs, sides, radius):
    h.check(
        "%s: two end arcs and two sides" % name,
        len(arcs) == 2 and len(sides) == 2,
        (len(arcs), len(sides)),
    )
    if len(arcs) != 2 or len(sides) != 2:
        return
    h.check(
        "%s: end radius %g" % (name, radius),
        all(st.near(a.Radius, radius, 1e-6) for _, a in arcs),
        [a.Radius for _, a in arcs],
    )
    c1, c2 = arcs[0][1].Center, arcs[1][1].Center
    span = (c2 - c1).Length
    h.check(
        "%s: the sides run from end to end" % name,
        all(st.near(g.length(), span, 1e-6) for _, g in sides),
        ([g.length() for _, g in sides], span),
    )
    cons = []
    for i, _g in arcs + sides:
        cons += st.constraints_of(i)
    h.check(
        "%s: tangent joins (4) and equal ends" % name,
        st.types(cons).count("Tangent") >= 8 and "Equal" in st.types(cons),
        st.types(cons),
    )


# == Center to Center ==================================================================
def cc_open():
    si.menu_item("CREATE", "Center to Center Slot")
    h.check(
        "SciForge's slot tool runs", st.tool_title() == "Center to Center Slot", st.tool_title()
    )
    s["count"] = len(st.sketch().Geometry)


def cc_points():
    st.click(V(-55, 25, 0))
    st.click(V(-15, 26, 0), towards=V(0, 0, 0))
    st.hover(V(-35, 31, 0))
    h.check("the width box shows", any(t.startswith("W ") for t in st.box_texts()), st.box_texts())


def cc_width():
    st.keys("10\n")


def cc_check():
    new = st.new_geometry(s["count"])
    arcs, sides, lines = parts(new)
    slot_shape_ok("centre to centre", arcs, sides, 5.0)
    if len(arcs) == 2:
        centres = sorted([(a.Center.x, a.Center.y) for _, a in arcs])
        h.check(
            "the end centres are the clicks",
            st.vnear(V(*centres[0], 0), V(-55, 25, 0), CLICK)
            and st.vnear(V(*centres[1], 0), V(-15, 25, 0), CLICK),
            centres,
        )
        h.check("...exactly level", st.near(centres[0][1], centres[1][1], 1e-9), centres)
        h.check(
            "the typed width is a Diameter dimension of 10",
            any(
                c.Type == "Diameter" and st.near(c.Value, 10.0, 1e-9)
                for c in st.sketch().Constraints
            ),
        )
    h.check("a construction centre line", len(lines) == 1, len(lines))
    if lines:
        h.check("...made Horizontal", "Horizontal" in st.types(st.constraints_of(lines[0][0])))
    st.sketch_ok("centre to centre slot")
    s["count"] = len(st.sketch().Geometry)
    h.shot("1-centre-slot")


def cc_esc_halfway():
    st.click(V(-55, -35, 0))
    st.hover(V(-25, -35, 0))
    st.esc()
    h.check("Esc halfway adds nothing", len(st.sketch().Geometry) == s["count"])
    h.check("Esc ends the tool", st.tool() is None)


# == Overall ==================================================================================
def ov_open():
    si.menu_item("CREATE", "Overall Slot")


def ov_points():
    h.check("Overall Slot runs", st.tool_title() == "Overall Slot", st.tool_title())
    st.click(V(5, 25, 0))
    st.click(V(45, 25, 0), towards=V(0, 0, 0))
    st.hover(V(25, 33, 0))
    st.keys("8\n")


def ov_check():
    new = st.new_geometry(s["count"])
    arcs, sides, lines = parts(new)
    slot_shape_ok("overall", arcs, sides, 4.0)
    h.check("a construction line from end to end", len(lines) == 1, len(lines))
    if lines and len(arcs) == 2:
        line = lines[0][1]
        ends = sorted([line.StartPoint, line.EndPoint], key=lambda p: p.x)
        h.check(
            "its ends are the clicks",
            st.vnear(ends[0], V(5, 25, 0), CLICK) and st.vnear(ends[1], V(45, 25, 0), CLICK),
            ends,
        )
        arc_list = sorted([a for _, a in arcs], key=lambda a: a.Center.x)
        h.check(
            "...at the tips of the end arcs (overall length = the line)",
            st.near((ends[0] - arc_list[0].Center).Length, 4.0, 1e-6)
            and st.near((ends[1] - arc_list[1].Center).Length, 4.0, 1e-6),
        )
    st.sketch_ok("overall slot")
    s["count"] = len(st.sketch().Geometry)
    st.esc()


# == Center Point ==============================================================================
def cp_open():
    si.menu_item("CREATE", "Center Point Slot")


def cp_points():
    h.check("Center Point Slot runs", st.tool_title() == "Center Point Slot", st.tool_title())
    st.click(V(-35, -25, 0))
    st.click(V(-15, -25, 0), towards=V(0, 0, 0))
    st.hover(V(-35, -21, 0))
    st.keys("6\n")


def cp_check():
    new = st.new_geometry(s["count"])
    arcs, sides, lines = parts(new)
    slot_shape_ok("centre point", arcs, sides, 3.0)
    points = st.of_type(new, "Part::GeomPoint")
    h.check("a point at the middle", len(points) == 1, len(points))
    if points and len(arcs) == 2:
        p = points[0][1]
        middle = (arcs[0][1].Center + arcs[1][1].Center) * 0.5
        h.check("exactly between the end centres", st.vnear(V(p.X, p.Y, 0), middle, 1e-6))
        h.check("where the first click was", st.vnear(V(p.X, p.Y, 0), V(-35, -25, 0), CLICK))
        h.check(
            "held there by Symmetric",
            "Symmetric" in st.types(st.constraints_of(points[0][0])),
            st.constraints_of(points[0][0]),
        )
    st.sketch_ok("centre point slot")
    s["count"] = len(st.sketch().Geometry)
    st.esc()


# == Three Point Arc Slot ====================================================================
def as_open():
    si.menu_item("CREATE", "Three Point Arc Slot")


def as_points():
    h.check("Three Point Arc Slot runs", st.tool_title() == "Three Point Arc Slot", st.tool_title())
    st.click(V(5, -25, 0))
    st.click(V(45, -25, 0))
    st.click(V(25, -15, 0))
    st.hover(V(25, -12, 0))
    curves = st.preview().get("curves", [])
    h.check("the slot previews (four arcs)", len(curves) == 4, len(curves))
    st.keys("6\n")


def as_check():
    new = st.new_geometry(s["count"])
    arcs = st.of_type(new, "Part::GeomArcOfCircle", construction=False)
    h.check("four arcs (outer, inner, two end caps)", len(arcs) == len(new) == 4, len(new))
    if len(arcs) == 4:
        radii = sorted(round(a.Radius, 6) for _, a in arcs)
        big = [a for _, a in arcs if a.Radius > 10]
        caps = [a for _, a in arcs if a.Radius < 10]
        h.check("end caps radius 3", radii[0] == 3.0 and radii[1] == 3.0, radii)
        h.check(
            "inner and outer arcs 6 apart",
            len(big) == 2 and st.near(abs(big[0].Radius - big[1].Radius), 6.0, 1e-6),
            radii,
        )
        h.check(
            "the centre arc goes through the three clicks: radius about 25",
            len(big) == 2 and st.near((big[0].Radius + big[1].Radius) / 2.0, 25.0, 2 * CLICK),
            radii,
        )
        h.check(
            "the end caps are centred on the clicked end centres",
            len(caps) == 2
            and sorted(
                [
                    st.vnear(c.Center, V(5, -25, 0), CLICK)
                    or st.vnear(c.Center, V(45, -25, 0), CLICK)
                    for c in caps
                ]
            )
            == [True, True],
            [c.Center for c in caps],
        )
        if len(big) == 2:
            h.check(
                "outer and inner arcs are concentric", st.vnear(big[0].Center, big[1].Center, 1e-6)
            )
    st.sketch_ok("arc slot")
    s["count"] = len(st.sketch().Geometry)
    h.shot("2-slots")


def undo_arc_slot():
    st.esc()
    st.undo()


def undo_check():
    h.check(
        "one Ctrl+Z takes the arc slot back",
        len(st.sketch().Geometry) == s["count"] - 4,
        len(st.sketch().Geometry),
    )
    st.redo()


def redo_check():
    h.check(
        "Ctrl+Y brings it back", len(st.sketch().Geometry) == s["count"], len(st.sketch().Geometry)
    )
    st.sketch_ok("after redo")


def finish():
    h.ribbon("Finish Sketch")


h.run(
    "sketch_tools_slots",
    si.watched(
        st.start_steps("SketchToolsSlots")
        + [
            cc_open,
            cc_points,
            cc_width,
            cc_check,
            cc_esc_halfway,
            ov_open,
            ov_points,
            ov_check,
            cp_open,
            cp_points,
            cp_check,
            as_open,
            as_points,
            as_check,
            undo_arc_slot,
            undo_check,
            redo_check,
            finish,
        ]
    ),
)
