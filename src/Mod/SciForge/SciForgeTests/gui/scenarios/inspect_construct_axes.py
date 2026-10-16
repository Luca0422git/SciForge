# SPDX-License-Identifier: LGPL-2.1-or-later
"""CONSTRUCT axes and points with real clicks: Axis Through Cylinder/Cone/Torus, Axis
Perpendicular to Face at Point (where clicked, and through a picked corner), Axis Through Two
Planes (faces, and the XY / XZ origin squares), Axis Through Two Points, Axis Through Edge
(an edge, and the origin Z axis drawn to click), Point at Vertex, Point Through Two Edges,
Point Through Three Planes, Point at Center of a circle, Point at Edge and Plane, Point Along
Path (edited again from the timeline), plus Cancel, Esc and undo / redo.

Part (real input): box 40 x 30 x 10 from the origin with a round boss r = 5 on top, centre
(10, 10), 10 high. Hand-derived expectations are written next to each check: axes are
lines through the stated point along the stated direction, points sit at the stated spot."""
import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import inspect_steps as s

V = App.Vector
st = {}


def datum():
    p = s.construct_panel()
    return p.datum if p is not None else None


def on_line(obj, point, direction, tol=1e-6):
    """Is construction axis `obj` the line through `point` along `direction`?"""
    if obj is None:
        return False
    gp = obj.getGlobalPlacement()
    d = gp.Rotation.multVec(V(0, 0, 1))
    if d.cross(V(direction).normalize()).Length > 1e-6:
        return False
    return (gp.Base - V(point)).cross(d).Length < tol


def at(obj, point):
    return obj is not None and s.near(obj.getGlobalPlacement().Base, point, 1e-6)


def start(label):
    def step():
        h.click_empty()
        s.menu("CONSTRUCT", label)

    step.__name__ = "start " + label
    return step


def ok():
    h.task_button("OK")


def count(type_id, n, label):
    def step():
        found = s.datums(type_id)
        h.check("%s made" % label, len(found) == n, [o.Label for o in found])
        h.check("dialog closed", s.construct_panel() is None)

    step.__name__ = "check " + label
    return step


# -- axes ------------------------------------------------------------------------------------------
def cyl_click():
    h.fit()
    h.click(V(15, 10, 15))  # on the boss, right on the line where its surface closes


def cyl_check():
    d = datum()
    h.check("axis through the boss", on_line(d, V(10, 10, 0), V(0, 0, 1)), d and d.Placement)
    h.shot("1-axis-cylinder")
    ok()


def normal_click():
    h.fit()
    h.click(V(30, 20, 10))


def normal_check():
    d = datum()
    p = s.construct_panel()
    h.check(
        "axis square to the top where clicked (a pixel off at most)",
        on_line(d, V(30, 20, 0), V(0, 0, 1), tol=0.5),
        d and d.Placement,
    )
    h.check("the Point box waits (optional)", p is not None and p.boxes[1].button.isChecked())
    s.click_vertex(V(40, 0, 10))


def normal_through_vertex():
    d = datum()
    h.check("through the picked corner", on_line(d, V(40, 0, 0), V(0, 0, 1)), d and d.Placement)
    ok()


def planes_top():
    h.fit()
    h.click(V(30, 20, 10))


def planes_front():
    h.click(V(30, 0, 5))


def planes_check():
    d = datum()
    h.check("axis where top and front meet", on_line(d, V(0, 0, 10), V(1, 0, 0)), d and d.Placement)
    ok()


def origin_xy():
    h.fit()
    h.click(V(6, -6, 0))


def origin_xz():
    p = s.construct_panel()
    h.check("XY square taken", p is not None and "XY" in s.box_value(p, 0), p and s.box_value(p, 0))
    h.click(V(8, 0, -8))


def origin_check():
    d = datum()
    h.check("XY and XZ meet in the X axis", on_line(d, V(0, 0, 0), V(1, 0, 0)), d and d.Placement)
    ok()


def points_1():
    h.fit()
    s.click_vertex(V(40, 0, 10))


def points_2():
    s.click_vertex(V(40, 30, 10))


def points_check():
    d = datum()
    h.check("axis through the two corners", on_line(d, V(40, 0, 10), V(0, 1, 0)), d and d.Placement)
    ok()


def edge_click():
    h.fit()
    h.click_edge(V(40, 15, 10))


def edge_check():
    d = datum()
    h.check("axis along the edge", on_line(d, V(40, 0, 10), V(0, 1, 0)), d and d.Placement)
    ok()


def z_axis_click():
    p = s.construct_panel()
    h.check("origin axes drawn", p is not None and "axes" in p.overlays)
    h.fit()
    h.click(V(0, 0, -15))


def z_axis_check():
    d = datum()
    p = s.construct_panel()
    h.check(
        "the Z axis line was taken",
        p is not None and "Z axis" in s.box_value(p, 0),
        p and s.box_value(p, 0),
    )
    h.check("axis along Z", on_line(d, V(0, 0, 0), V(0, 0, 1)), d and d.Placement)
    ok()


def undo_axis():
    st["axes"] = len(s.datums("PartDesign::Line"))
    s.undo()


def axis_undone():
    h.check("Undo removes the last axis", len(s.datums("PartDesign::Line")) == st["axes"] - 1)
    s.redo()


def axis_redone():
    h.check("Redo brings it back", len(s.datums("PartDesign::Line")) == st["axes"])
    h.check("all axes valid", all("Invalid" not in o.State for o in s.datums()))


def hide_construction():
    """The axes lie on edges the points pick next: hide them all (the folder's eye)."""
    h.click_empty()
    s.eye("Construction")


def construction_hidden():
    h.check("axes hidden", not any(o.ViewObject.Visibility for o in s.datums()))


# -- points ----------------------------------------------------------------------------------------
def vertex_click():
    h.fit()
    s.click_vertex(V(40, 30, 10))


def vertex_check():
    h.check("point at the corner", at(datum(), V(40, 30, 10)), datum() and datum().Placement)
    ok()


def two_edges_1():
    h.fit()
    h.click_edge(V(25, 0, 10))


def two_edges_2():
    h.click_edge(V(40, 20, 10))


def two_edges_check():
    h.check("point where the edges meet", at(datum(), V(40, 0, 10)), datum() and datum().Placement)
    ok()


def three_1():
    h.fit()
    h.click(V(30, 20, 10))


def three_2():
    h.click(V(30, 0, 5))


def three_3():
    h.click(V(40, 20, 5))


def three_check():
    p = s.construct_panel()
    h.check(
        "point where three faces meet",
        at(datum(), V(40, 0, 10)),
        p and ([s.box_value(p, i) for i in range(3)], p.message.text()),
    )
    ok()


def center_click():
    h.fit()
    h.click_edge(V(13.5355339, 6.4644661, 20))


def center_check():
    h.check(
        "point at the circle's centre", at(datum(), V(10, 10, 20)), datum() and datum().Placement
    )
    ok()


def edge_plane_edge():
    h.fit()
    h.click_edge(V(40, 0, 5))


def edge_plane_xy():
    h.click(V(6, -6, 0))


def edge_plane_check():
    p = s.construct_panel()
    h.check(
        "point where the edge meets XY",
        at(datum(), V(40, 0, 0)),
        p and [s.box_value(p, i) for i in range(2)],
    )
    ok()


def path_click():
    h.fit()
    h.click_edge(V(25, 0, 10))


def path_check():
    h.check(
        "point halfway along the edge", at(datum(), V(20, 0, 10)), datum() and datum().Placement
    )
    ok()


def path_made():
    points = s.datums("PartDesign::Point")
    st["path_point"] = points[-1].Name if points else None
    h.check("six points", len(points) == 6, [o.Label for o in points])


def path_edit():
    s.double_click_timeline(App.ActiveDocument.getObject(st["path_point"]))


def path_edit_quarter():
    p = s.construct_panel()
    h.check(
        "Point Along Path opens again", p is not None and p.editing and p.key == "PointAlongPath"
    )
    if p is not None:
        s.type_into(p.fraction, "0.25")


def path_edit_ok():
    ok()


def path_edited():
    d = App.ActiveDocument.getObject(st["path_point"])
    gp = d.getGlobalPlacement().Base
    h.check("a quarter along: x = 10 or 30", s.close(gp.x, 10.0) or s.close(gp.x, 30.0), gp)
    h.check("still on the edge", abs(gp.y) < 1e-6 and s.close(gp.z, 10.0), gp)


def cancel_click():
    h.fit()
    s.click_vertex(V(0, 0, 10))


def cancel_press():
    h.check("a point is previewed", datum() is not None)
    h.task_button("Cancel")


def cancelled():
    h.check("Cancel: still six points", len(s.datums("PartDesign::Point")) == 6)


def esc_click():
    h.fit()
    s.click_vertex(V(0, 0, 10))


def esc_press():
    s.press_escape()


def escaped():
    h.check("Esc closes", not Gui.Control.activeDialog())
    h.check("Esc: still six points", len(s.datums("PartDesign::Point")) == 6)
    h.check("part unchanged", s.close(h.solid_volume(), 12000 + 3.141592653589793 * 250))
    h.check("no pop-ups", not h.popups(), h.popups())
    h.shot("2-end")


h.run(
    "inspect_construct_axes",
    b.box_steps("InspectAxes")
    + s.boss_steps()
    + [
        start("Axis Through Cylinder/Cone/Torus"),
        cyl_click,
        cyl_check,
        count("PartDesign::Line", 1, "Axis1"),
        start("Axis Perpendicular to Face at Point"),
        normal_click,
        normal_check,
        normal_through_vertex,
        count("PartDesign::Line", 2, "Axis2"),
        start("Axis Through Two Planes"),
        planes_top,
        planes_front,
        planes_check,
        start("Axis Through Two Planes"),
        origin_xy,
        origin_xz,
        origin_check,
        start("Axis Through Two Points"),
        points_1,
        points_2,
        points_check,
        start("Axis Through Edge"),
        edge_click,
        edge_check,
        start("Axis Through Edge"),
        z_axis_click,
        z_axis_check,
        count("PartDesign::Line", 7, "Axis7"),
        undo_axis,
        axis_undone,
        axis_redone,
        hide_construction,
        construction_hidden,
        start("Point at Vertex"),
        vertex_click,
        vertex_check,
        start("Point Through Two Edges"),
        two_edges_1,
        two_edges_2,
        two_edges_check,
        start("Point Through Three Planes"),
        three_1,
        three_2,
        three_3,
        three_check,
        start("Point at Center of Circle/Sphere/Torus"),
        center_click,
        center_check,
        start("Point at Edge and Plane"),
        edge_plane_edge,
        edge_plane_xy,
        edge_plane_check,
        start("Point Along Path"),
        path_click,
        path_check,
        path_made,
        path_edit,
        path_edit_quarter,
        path_edit_ok,
        path_edited,
        start("Point at Vertex"),
        cancel_click,
        cancel_press,
        cancelled,
        start("Point at Vertex"),
        esc_click,
        esc_press,
        escaped,
    ],
)
