# SPDX-License-Identifier: LGPL-2.1-or-later
"""CONSTRUCT planes with real clicks: Plane at Angle, Tangent Plane, Midplane (parallel and
meeting), Plane Through Two Edges (and lines that do not share a plane: refused in the
dialog), Plane Through Three Points, Plane Tangent to Face at Point, Plane Along Path.

Part (real input): box 40 x 30 x 10 from the origin with a round boss r = 5 on top,
centre (10, 10), 10 high (z = 10 .. 20). Hand-derived expectations:
  Plane at Angle about the front top edge (y = 0, z = 10, along X): it starts at 0 degrees,
    in the front face (normal -Y); at a degrees its normal is (0, -cos a, +-sin a).
  Tangent Plane clicked on the boss at (15, 10, 15): normal +X through x = 15; turned 90
    degrees about the boss axis: normal +-Y through y = 10 +- 5.
  Midplane of the top face (z = 10) and the XY origin plane: z = 5. Of the top face and
    the right face (x = 40): normal (-1, 0, 1) / sqrt 2 through the edge x = 40, z = 10.
  Plane Through Two Edges (front top + right top edges): the top plane z = 10.
  Plane Through Three Points (40,0,10), (40,30,10), (0,0,10): z = 10.
  Plane Tangent to Face at Point (boss face, corner (40, 0, 10)): normal (3, -1, 0)/sqrt 10
    through (10, 10, 10) + 5 * that normal.
  Plane Along Path (front top edge, 40 long): proportional 0.5 -> x = 20; physical 10 ->
    10 from the edge's start (x = 10 or 30)."""
import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import inspect_steps as s

V = App.Vector
st = {}
R2 = 1.0 / math.sqrt(2.0)


def new_datum():
    """The construction the open dialog shows."""
    p = s.construct_panel()
    return p.datum if p is not None else None


def gp():
    d = new_datum()
    return d.getGlobalPlacement() if d is not None else None


# -- Plane at Angle --------------------------------------------------------------------------
def angle_start():
    h.click_empty()
    s.menu("CONSTRUCT", "Plane at Angle")


def angle_waits():
    p = s.construct_panel()
    h.check("Plane at Angle open", p is not None and p.title == "Plane at Angle")
    if p is None:
        return
    h.check("waits for a line", p.datum is None and "straight edge" in p.message.text())
    h.check("origin axes drawn to click", "axes" in p.overlays, list(p.overlays))
    s.no_popups("Plane at Angle")


def angle_click_edge():
    h.fit()
    h.click_edge(V(25, 0, 10))


def angle_preview():
    p = s.construct_panel()
    d = new_datum()
    h.check("plane shown after the edge click", d is not None, p and p.message.text())
    if d is None:
        return
    n = s.normal_of(d)
    h.check("at 0 degrees it lies in the front face", s.near(n, V(0, -1, 0), 1e-9), n)
    h.check("through the edge", s.close(gp().Base.z, 10.0) and abs(gp().Base.y) < 1e-6, gp())
    h.check("angle handle shown", p.handle is not None and p.handle_key == "angle")
    st["angle_before"] = p.values["angle"]
    h.shot("1-plane-at-angle")


def angle_drag():
    p = s.construct_panel()
    if p is None or p.handle is None:
        return
    handle = p.handle
    ball = handle.point_at(handle.angle())
    start = s.screen(ball)
    end = s.screen(handle.point_at(handle.angle() + 30))
    h.drag(start, end, steps=16)


def angle_dragged():
    p = s.construct_panel()
    if p is None:
        return
    value = p.values["angle"]
    h.check("dragging the ball turned the plane", abs(value - st["angle_before"]) > 5, value)
    h.check("the Angle field follows", s.close(p.angle.value(), value, 1e-2), p.angle.value())


def angle_type_90():
    p = s.construct_panel()
    if p is not None:
        s.type_into(p.angle.widget, "90")


def angle_typed():
    d = new_datum()
    if d is None:
        return
    n = s.normal_of(d)
    h.check("at 90 degrees: horizontal", abs(abs(n.z) - 1) < 1e-6, n)
    h.task_button("OK")


def angle_made():
    planes = s.datums("PartDesign::Plane")
    h.check("Plane1 made", [o.Label for o in planes] == ["Plane1"], [o.Label for o in planes])
    st["angle_plane"] = planes[0].Name if planes else None


def angle_edit():
    s.double_click_timeline(App.ActiveDocument.getObject(st["angle_plane"]))


def angle_edit_30():
    p = s.construct_panel()
    h.check("Plane at Angle opens again", p is not None and p.editing and p.key == "PlaneAtAngle")
    if p is None:
        return
    h.check("with its edge", "edge" in s.box_value(p, 0), s.box_value(p, 0))
    h.check("and its angle", s.close(p.angle.value(), 90.0), p.angle.value())
    s.type_into(p.angle.widget, "30")


def angle_edit_ok():
    h.task_button("OK")


def angle_edited():
    d = App.ActiveDocument.getObject(st["angle_plane"])
    n = s.normal_of(d)
    h.check(
        "edited to 30 degrees",
        abs(n.y + math.cos(math.radians(30))) < 1e-6 and abs(abs(n.z) - 0.5) < 1e-6,
        n,
    )
    s.eye("Plane1")  # out of the way of the next clicks


# -- Tangent Plane -----------------------------------------------------------------------------
def tangent_start():
    h.click_empty()
    s.menu("CONSTRUCT", "Tangent Plane")


def tangent_click_boss():
    h.fit()
    h.click(V(15, 10, 15))


def tangent_preview():
    d = new_datum()
    h.check("tangent plane shown", d is not None)
    if d is None:
        return
    n = s.normal_of(d)
    h.check("touches the boss where clicked: normal +X", s.near(n, V(1, 0, 0), 1e-6), n)
    h.check("at x = 15", s.close(gp().Base.x, 15.0), gp())
    p = s.construct_panel()
    s.type_into(p.angle.widget, "90")


def tangent_turned():
    d = new_datum()
    n = s.normal_of(d)
    h.check("turned 90 about the boss axis", abs(abs(n.y) - 1) < 1e-6, n)
    h.check("still touching it", s.close(abs(gp().Base.y - 10), 5.0) and s.close(gp().Base.x, 10.0))
    h.shot("2-tangent-plane")
    h.task_button("OK")


def tangent_made():
    h.check("Plane2 made", len(s.datums("PartDesign::Plane")) == 2)
    s.eye("Plane2")


# -- Midplane ----------------------------------------------------------------------------------
def mid_start():
    h.click_empty()
    s.menu("CONSTRUCT", "Midplane")


def mid_click_top():
    h.fit()
    h.click(V(30, 20, 10))


def mid_click_xy():
    p = s.construct_panel()
    h.check("first plane taken, second box blue", p is not None and p.boxes[1].button.isChecked())
    h.click(V(6, -6, 0))


def mid_preview():
    d = new_datum()
    p = s.construct_panel()
    h.check("midplane shown", d is not None, p and (s.box_value(p, 0), s.box_value(p, 1)))
    if d is None:
        return
    h.check("halfway: z = 5", s.close(gp().Base.z, 5.0), gp())
    h.check("parallel", abs(abs(s.normal_of(d).z) - 1) < 1e-9, s.normal_of(d))
    h.task_button("OK")


def mid2_start():
    s.eye("Plane3")
    h.click_empty()
    s.menu("CONSTRUCT", "Midplane")


def mid2_top():
    h.fit()
    h.click(V(30, 20, 10))


def mid2_right():
    h.click(V(40, 15, 5))


def mid2_preview():
    d = new_datum()
    h.check("midplane of two meeting faces", d is not None)
    if d is None:
        return
    n = s.normal_of(d)
    h.check(
        "bisects the corner", s.near(n, V(-R2, 0, R2), 1e-6) or s.near(n, V(R2, 0, -R2), 1e-6), n
    )
    base = gp().Base
    h.check("through the edge x = 40, z = 10", abs((base.x - 40) - (10 - base.z)) < 1e-6, base)
    h.task_button("OK")


def mid2_made():
    h.check("Plane4 made", len(s.datums("PartDesign::Plane")) == 4)
    s.eye("Plane4")


# -- Plane Through Two Edges ---------------------------------------------------------------------
def two_start():
    h.click_empty()
    s.menu("CONSTRUCT", "Plane Through Two Edges")


def two_click_1():
    h.fit()
    h.click_edge(V(30, 0, 10))


def two_click_skew():
    """The back right upright edge (x = 40, y = 30) never meets the front top edge."""
    h.click_edge(V(40, 30, 5))


def two_click_2_skew():
    p = s.construct_panel()
    h.check("two lines picked", p is not None and all(p.picks), p and p.picks)
    h.check(
        "lines not in one plane: said in the dialog",
        p and "not in one plane" in p.message.text(),
        p and p.message.text(),
    )
    h.check("nothing made for them", p is not None and p.datum is None)
    s.no_popups("lines in no plane")
    h.task_button("OK")


def two_ok_refused():
    p = s.construct_panel()
    h.check("OK waits while the lines do not fit", p is not None)
    if p is not None:
        s.click_box(p, 1)


def two_click_2():
    h.click_edge(V(40, 20, 10))


def two_preview():
    d = new_datum()
    h.check("plane through the two top edges", d is not None)
    if d is None:
        return
    h.check(
        "is the top plane z = 10",
        s.close(gp().Base.z, 10.0) and abs(abs(s.normal_of(d).z) - 1) < 1e-9,
    )
    h.task_button("OK")


def two_made():
    h.check("Plane5 made", len(s.datums("PartDesign::Plane")) == 5)
    s.eye("Plane5")


# -- Plane Through Three Points --------------------------------------------------------------------
def three_start():
    h.click_empty()
    s.menu("CONSTRUCT", "Plane Through Three Points")


def three_p1():
    h.fit()
    s.click_vertex(V(40, 0, 10))


def three_p2():
    s.click_vertex(V(40, 30, 10))


def three_p3():
    s.click_vertex(V(0, 0, 10))


def three_preview():
    d = new_datum()
    p = s.construct_panel()
    h.check(
        "plane through the three corners",
        d is not None,
        p and [s.box_value(p, i) for i in range(3)],
    )
    if d is None:
        return
    h.check("z = 10", s.close(gp().Base.z, 10.0) and abs(abs(s.normal_of(d).z) - 1) < 1e-9, gp())
    h.task_button("OK")


def three_made():
    h.check("Plane6 made", len(s.datums("PartDesign::Plane")) == 6)
    s.eye("Plane6")


# -- Plane Tangent to Face at Point --------------------------------------------------------------
def tat_start():
    h.click_empty()
    s.menu("CONSTRUCT", "Plane Tangent to Face at Point")


def tat_face():
    h.fit()
    h.click(V(15, 10, 15))


def tat_point():
    s.click_vertex(V(40, 0, 10))


def tat_preview():
    d = new_datum()
    h.check("tangent plane at the point", d is not None)
    if d is None:
        return
    n0 = V(3, -1, 0)
    n0.normalize()
    h.check("normal toward the corner", s.near(s.normal_of(d), n0, 1e-6), s.normal_of(d))
    h.check("touches the boss", s.near(gp().Base, V(10, 10, 10) + n0 * 5, 1e-6), gp())
    h.task_button("OK")


def tat_made():
    h.check("Plane7 made", len(s.datums("PartDesign::Plane")) == 7)
    s.eye("Plane7")


# -- Plane Along Path --------------------------------------------------------------------------------
def path_start():
    h.click_empty()
    s.menu("CONSTRUCT", "Plane Along Path")


def path_click():
    h.fit()
    h.click_edge(V(30, 0, 10))


def path_preview():
    d = new_datum()
    p = s.construct_panel()
    h.check("plane along the edge", d is not None, p and p.message.text())
    if d is None:
        return
    h.check("halfway: x = 20", s.close(gp().Base.x, 20.0), gp())
    h.check("square to the edge", abs(abs(s.normal_of(d).x) - 1) < 1e-9, s.normal_of(d))
    h.check("a ball to slide", p.handle is not None and p.handle_key == "path")
    h.shot("3-along-path")


def path_drag():
    p = s.construct_panel()
    if p is None or p.handle is None:
        return
    start = s.screen(p.handle.point())
    end = s.screen(V(30, 0, 10))
    h.drag(start, end, steps=16)


def path_dragged():
    p = s.construct_panel()
    if p is None:
        return
    x = gp().Base.x
    h.check("sliding the ball moved the plane", abs(x - 20.0) > 3.0, x)
    h.check("the Distance follows", abs(p.fraction.value() - 0.5) > 0.05, p.fraction.value())


def path_physical():
    from SciForgeTests.gui import dialog_input as di

    p = s.construct_panel()
    if p is not None:
        h.check("Distance Type offered", di.choose(p.path_type, "Physical"))


def path_type_10():
    p = s.construct_panel()
    if p is None:
        return
    h.check("the field is a length now", p.distance_stack.currentIndex() == 1)
    s.type_into(p.distance.widget, "10")


def path_physical_10():
    x = gp().Base.x
    h.check("10 along the edge from its start", s.close(x, 10.0) or s.close(x, 30.0), x)
    h.task_button("OK")


def path_made():
    planes = s.datums("PartDesign::Plane")
    h.check("Plane8 made", len(planes) == 8, [o.Label for o in planes])
    h.check("part never changed", s.close(h.solid_volume(), 12000 + math.pi * 250))
    h.check("no pop-ups", not h.popups(), h.popups())
    h.shot("4-end")


h.run(
    "inspect_construct_planes",
    b.box_steps("InspectPlanes")
    + s.boss_steps()
    + [
        angle_start,
        angle_waits,
        angle_click_edge,
        angle_preview,
        angle_drag,
        angle_dragged,
        angle_type_90,
        angle_typed,
        angle_made,
        angle_edit,
        angle_edit_30,
        angle_edit_ok,
        angle_edited,
        tangent_start,
        tangent_click_boss,
        tangent_preview,
        tangent_turned,
        tangent_made,
        mid_start,
        mid_click_top,
        mid_click_xy,
        mid_preview,
        mid2_start,
        mid2_top,
        mid2_right,
        mid2_preview,
        mid2_made,
        two_start,
        two_click_1,
        two_click_skew,
        two_click_2_skew,
        two_ok_refused,
        two_click_2,
        two_preview,
        two_made,
        three_start,
        three_p1,
        three_p2,
        three_p3,
        three_preview,
        three_made,
        tat_start,
        tat_face,
        tat_point,
        tat_preview,
        tat_made,
        path_start,
        path_click,
        path_preview,
        path_drag,
        path_dragged,
        path_physical,
        path_type_10,
        path_physical_10,
        path_made,
    ],
)
