# SPDX-License-Identifier: LGPL-2.1-or-later
"""SURFACE > Thicken, Offset and Reverse Normal like a Fusion user, only real input.

An L of two walls: sketch lines (0, 0) - (30, 0) - (30, 20) on XY, surface-extruded 10 up
(area 500). Thicken: click both walls; OK waits for a thickness; drag the arrow (about 3),
then type 2 and -2: one way the walls thicken into the L's inside, 10 (30 2 + 20 2 - 2 2)
= 960, the other way outside with a sharp corner, 10 (60 + 40 + 2 2) = 1040. Outside,
Thicken Type Rounded: the corner is a quarter circle of radius 2, 10 (100 + pi 4 / 4)
= 1031.42. Symmetric (1 each way): rounded 10 (100 - 1 + pi / 4) = 997.85; Sharp
10 (100 - 1 + 1) = 1000. OK: a new solid body, "Thicken 1". Undo / Redo. Edit it from
the timeline: thickness 4 (2 each way, sharp): 10 (32 22 - 28 18) = 2000.
The SOLID tab's Thicken opens the same dialog (Esc).
A 40 x 30 x 10 box (12000). SURFACE > Offset, click the top face, drag the arrow up
(about 5), type 5: a new surface 40 x 30 at z 15. Thicken it -5 (down to the box) with
Operation Join: the box grows to 40 x 30 x 15 = 18000, no new body. Reverse Normal: a click
on the surface now finds the box under it (the two lie on each other): refused, a solid;
click the surface's row in the browser: its face turns to look down; Undo / Redo.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import surface_steps as st
from SciForgeTests.gui import timeline_input as tl

V = App.Vector
s = {}
INSIDE = 960.0
OUTSIDE = 1040.0
OUTSIDE_ROUND = 1000.0 + 10 * math.pi
SYM_ROUND = 10 * (99 + math.pi / 4)
SYM_SHARP = 1000.0


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("SurfaceThicken")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xy():
    st.open_sketch_clicked(V(12, -8, 0))


def draw_l():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None)
    if sk:
        st.add_lines(sk, [(0, 0), (30, 0), (30, 20)])


def finish():
    h.ribbon("Finish Sketch")


def extrude_walls():
    h.fit()
    h.click_empty()
    st.tab("SURFACE")
    st.menu("CREATE", "Extrude")


def click_l():
    h.check("clicked the L", h.click_edge(V(15, 0, 0)))


def walls_distance():
    st.type_field("distance", "10")


def walls_ok():
    st.settle()
    body = st.step_body()
    h.check(
        "an L of walls (area 500)",
        body is not None and st.near(st.area(body), 500.0),
        st.area(body),
    )
    s["walls"] = body
    st.ok()


def thicken_menu():
    h.check("walls made", st.panel() is None)
    h.fit()
    st.menu("CREATE", "Thicken")


def click_wall_a():
    p = st.panel()
    h.check("Thicken dialog open", p is not None and p.kind == "thicken")
    pl.click_on_plane(V(15, 0, 5))


def click_wall_b():
    h.click(V(30, 10, 5))


def waits_for_thickness():
    st.settle()
    p = st.panel()
    if p is None:
        return
    h.check("two faces", len(p.picks["faces"]) == 2, p.picks["faces"])
    h.check("OK waits for a thickness", "thickness" in st.message().lower(), st.message())
    h.check("New Body", p.options["operation"] == "new_body", p.options["operation"])
    st.type_field("thickness", "1")


def drag_thickness():
    s["drag"] = st.drag_arrow("thickness", 3.0)


drag_thickness.wait_ms = 2200


def dragged():
    st.settle()
    d = s.get("drag")
    h.check("the drag finished", d is not None and d.done, getattr(d, "error", None))
    p = st.panel()
    value = p.options["thickness"] if p else 0
    h.check("the drag set the thickness (about 3)", 2.2 < abs(value) < 4.0, value)
    st.type_field("thickness", "2")


def plus_two():
    st.settle()
    s["plus"] = st.volume(st.step_body())
    h.check(
        "2: inside or outside", st.near(s["plus"], INSIDE) or st.near(s["plus"], OUTSIDE), s["plus"]
    )
    st.type_field("thickness", "-2")


def minus_two():
    st.settle()
    v = st.volume(st.step_body())
    other = OUTSIDE if st.near(s["plus"], INSIDE) else INSIDE
    h.check("-2: the other side", st.near(v, other), (v, other))
    s["out"] = "-2" if st.near(v, OUTSIDE) else "2"
    st.type_field("thickness", s["out"])


def outside_sharp():
    st.settle()
    v = st.volume(st.step_body())
    h.check("outside, sharp corner: 1040", st.near(v, OUTSIDE), v)
    h.shot("1-sharp")
    st.choose("thicken_type", "Rounded")


def outside_rounded():
    st.settle()
    v = st.volume(st.step_body())
    h.check("outside, rounded corner: 1031.42", st.near(v, OUTSIDE_ROUND, 1e-5), v)
    h.shot("2-rounded")
    st.choose("direction", "Symmetric")


def symmetric_rounded():
    st.settle()
    v = st.volume(st.step_body())
    h.check("symmetric, rounded: 997.85", st.near(v, SYM_ROUND, 1e-5), v)
    st.choose("thicken_type", "Sharp")


def symmetric_sharp():
    st.settle()
    body = st.step_body()
    v = st.volume(body)
    h.check("symmetric, sharp: 1000", st.near(v, SYM_SHARP, 1e-5), v)
    bb = body.Shape.BoundBox if body is not None else None
    h.check(
        "1 each side of the walls",
        bb is not None and st.near(bb.XMax, 31.0) and st.near(bb.YMin, -1.0),
        bb,
    )
    s["thick"] = body
    st.ok()


def thickened():
    h.check("dialog closed", st.panel() is None)
    titles = st.timeline_titles()
    h.check("Thicken 1 in the timeline", "Thicken 1" in titles, titles)
    h.check("a solid body", st.browser_icon_of(s["thick"]) == "box", st.browser_icon_of(s["thick"]))
    h.check("the walls stay a surface", st.browser_icon_of(s["walls"]) == "surface_body")
    st.undo()


def undone():
    from sciforge import bodies

    h.check(
        "undo: the solid is gone",
        not any(bodies.has_solid(x) for x in st.bodies()),
        [x.Label for x in st.bodies()],
    )
    st.redo()


def redone():
    h.check(
        "redo: 1000 again", st.near(st.volume(s["thick"]), SYM_SHARP, 1e-5), st.volume(s["thick"])
    )


def edit_thicken():
    h.check("double-clicked Thicken 1", st.double_click_timeline("Thicken 1"))


def edit_open():
    st.settle()
    p = st.panel()
    h.check("edit dialog open", p is not None and p.editing and p.kind == "thicken")
    if p is None:
        return
    h.check(
        "read back: symmetric, sharp, 2 faces",
        p.options["direction"] == "symmetric"
        and p.options["thicken_type"] == "sharp"
        and len(p.picks["faces"]) == 2,
        (p.options, p.picks["faces"]),
    )
    st.type_field("thickness", s["out"].replace("2", "4"))


def edit_ok():
    st.settle()
    v = st.volume(s["thick"])
    h.check("thickness 4: 2000", st.near(v, 2000.0, 1e-5), v)
    st.ok()


def edited():
    h.check("dialog closed", st.panel() is None)
    h.check("2000 kept", st.near(st.volume(s["thick"]), 2000.0, 1e-5), st.volume(s["thick"]))


def solid_tab_thicken():
    st.tab("SOLID")
    st.menu("CREATE", "Thicken")


def solid_tab_dialog():
    p = st.panel()
    h.check("SOLID > Thicken opens the Thicken dialog", p is not None and p.kind == "thicken")
    st.esc()


def solid_tab_closed():
    h.check("Esc closed it", st.panel() is None)
    h.check("nothing changed", st.near(st.volume(s["thick"]), 2000.0, 1e-5))


# -- Offset and Thicken Join on a box --------------------------------------------------------------
def offset_menu():
    s["box"] = h.body()
    h.check("box 12000", s["box"] is not None and st.near(st.volume(s["box"]), 12000.0))
    st.tab("SURFACE")
    st.menu("CREATE", "Offset")


def click_top():
    p = st.panel()
    h.check("Offset dialog open", p is not None and p.kind == "offset")
    h.click(V(20, 15, 10))


def drag_offset():
    st.settle()
    p = st.panel()
    h.check("the top face", p is not None and len(p.picks["faces"]) == 1, p and p.picks)
    st.type_field("distance", "1")
    st.settle()
    s["drag"] = st.drag_arrow("distance", 5.0)


drag_offset.wait_ms = 2200


def offset_dragged():
    st.settle()
    d = s.get("drag")
    h.check("the drag finished", d is not None and d.done, getattr(d, "error", None))
    p = st.panel()
    value = p.options["distance"] if p else 0
    h.check("the drag set the distance (about 5)", 3.5 < value < 6.5, value)
    st.type_field("distance", "5")


def offset_ok():
    st.settle()
    body = st.step_body()
    h.check("a 40 x 30 surface", body is not None and st.near(st.area(body), 1200.0), st.area(body))
    h.check("at z 15", body is not None and st.near(body.Shape.BoundBox.ZMin, 15.0))
    s["offset"] = body
    st.ok()


def offset_done():
    h.check("dialog closed", st.panel() is None)
    titles = st.timeline_titles()
    h.check("Offset 1 in the timeline", "Offset 1" in titles, titles)
    h.check("a surface body", st.browser_icon_of(s["offset"]) == "surface_body")
    h.check("the box unchanged", st.near(st.volume(s["box"]), 12000.0))
    st.menu("CREATE", "Thicken")


def click_offset():
    h.click(V(20, 15, 15))


def thicken_down():
    st.settle()
    p = st.panel()
    h.check(
        "the offset surface picked", p is not None and len(p.picks["faces"]) == 1, p and p.picks
    )
    st.type_field("thickness", "-5")
    st.choose("operation", "Join")


def joined():
    st.settle()
    v = st.volume(s["box"])
    h.check("Join: the box grows to 18000", st.near(v, 18000.0, 1e-5), v)
    st.ok()


def join_done():
    h.check("dialog closed", st.panel() is None)
    h.check(
        "the box 40 x 30 x 15", st.near(st.volume(s["box"]), 18000.0, 1e-5), st.volume(s["box"])
    )
    from sciforge import bodies

    solids = [x for x in st.bodies() if bodies.has_solid(x)]
    h.check("no new body", solids == [s["box"]], [x.Label for x in solids])
    s["normal"] = s["offset"].Shape.Faces[0].normalAt(0.5, 0.5)
    st.menu("MODIFY", "Reverse Normal")


def click_offset_again():
    h.click(V(20, 15, 15))  # it lies on the box's top now: the click finds the box


def solid_refused():
    st.settle()
    p = st.panel()
    if p is None:
        return
    h.check("the box is not taken", p.picks["bodies"] == [], p.picks["bodies"])
    h.check("the dialog says it is a solid", "is a solid" in p.message.text(), p.message.text())
    tl.click_row(s["offset"].Label)


def reverse_ok():
    st.settle()
    p = st.panel()
    h.check(
        "the browser click took the surface",
        p is not None and [x[0] for x in p.picks["bodies"]] == [s["offset"]],
        p and p.picks,
    )
    n = s["offset"].Shape.Faces[0].normalAt(0.5, 0.5)
    h.check("the face turned over", n.dot(s["normal"]) < -0.99, (n, s["normal"]))
    h.shot("3-reversed")
    st.ok()


def reversed_done():
    h.check("dialog closed", st.panel() is None)
    titles = st.timeline_titles()
    h.check("Reverse Normal 1 in the timeline", "Reverse Normal 1" in titles, titles)
    st.undo()


def reverse_undone():
    n = s["offset"].Shape.Faces[0].normalAt(0.5, 0.5)
    h.check("undo: facing up again", n.dot(s["normal"]) > 0.99, n)
    st.redo()


def reverse_redone():
    n = s["offset"].Shape.Faces[0].normalAt(0.5, 0.5)
    h.check("redo: facing down", n.dot(s["normal"]) < -0.99, n)


h.run(
    "surface_thicken",
    [
        new_design,
        pick_xy,
        draw_l,
        finish,
        extrude_walls,
        click_l,
        walls_distance,
        walls_ok,
        thicken_menu,
        click_wall_a,
        click_wall_b,
        waits_for_thickness,
        drag_thickness,
        dragged,
        plus_two,
        minus_two,
        outside_sharp,
        outside_rounded,
        symmetric_rounded,
        symmetric_sharp,
        thickened,
        undone,
        redone,
        edit_thicken,
        edit_open,
        edit_ok,
        edited,
        solid_tab_thicken,
        solid_tab_dialog,
        solid_tab_closed,
    ]
    + b.box_steps("SurfaceOffset", 10)
    + [
        offset_menu,
        click_top,
        drag_offset,
        offset_dragged,
        offset_ok,
        offset_done,
        click_offset,
        thicken_down,
        joined,
        join_done,
        click_offset_again,
        solid_refused,
        reverse_ok,
        reversed_done,
        reverse_undone,
        reverse_redone,
    ],
)
