# SPDX-License-Identifier: LGPL-2.1-or-later
"""SURFACE > Loft, part 2: two rails with a Tangent end, a centerline with a Direction end,
New Component, save and reopen, only real input.

Create Sketch on XY: the line (0, 20) - (5, 0); SURFACE > Extrude it with Start Offset 20,
10 high: a wall z 20 .. 30 (the plane 4 x + y = 20, turned to the camera). Sketches: on XY the
line (0, 40) - (10, 0) (the second profile, z 0); on YZ the rail (y 20, z 20) - (y 40, z 0); on
XZ the rail (x 5, z 20) - (x 10, z 0); on XY a circle r 5 at (-30, 0); on YZ a circle r 5 at
(y 0, z 30); on XZ the quarter arc r 30 about the origin from (-30, 0) to (0, 30) (the
centerline).
Path L1 (two rails, a Tangent end, a refusal, New Component): SURFACE > Loft; click the wall's
        lower edge (one edge: Chain Selection takes the edges joined smoothly), then the line;
        click the Rails box, then both rails: one face from z 20 down to 0; First Profile
        offers Connected / Tangent / Curvature (an edge of a body): Tangent (G1): the loft
        leaves the wall smoothly (the normals match along the edge); Closed: the dialog says
        a closed loft cannot follow rails; Closed off again; Operation New Component: the loft
        body goes into a new component. OK: "Loft 1".
Path L2 (undo / redo).
Path L3 (a centerline and a Direction end): Loft, click the two circles, Guide Type
        Centerline, click the arc: a quarter torus R 30, r 5 (area 1480.4); First Profile
        Direction: the same tube (it leaves the circle along the arc). OK: "Loft 2".
Path L4 (save, reopen, edit): Ctrl+S (version prompt), close, reopen: both lofts are back as
        surface bodies with the same areas; double-click Loft 2: Centerline, the arc and
        Direction read back; Esc. Double-click Loft 1: rails and Tangent read back; Tangent
        Edges Merge on: still one face; OK."""

import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import surface_steps as st
from SciForgeTests.gui import versions_input as vi

V = App.Vector
TORUS = (2 * math.pi * 5) * (2 * math.pi * 30) / 4.0
s = {}


def doc():
    return App.ActiveDocument


def by_label(label):
    found = doc().getObjectsByLabel(label)
    return found[0] if found else None


def g1_error(loft_body, wall_body, point):
    """Degrees between the loft's and the wall's normals at a point of their shared edge."""
    import Part

    worst = 0.0
    try:
        loft_face = loft_body.Shape.Faces[0]
        wall_face = min(wall_body.Shape.Faces, key=lambda f: f.distToShape(Part.Vertex(point))[0])
        for k in range(1, 6):
            p = point + V(2.5, -10, 0) * ((k - 3) / 3.0)
            nu = loft_face.normalAt(*loft_face.Surface.parameter(p))
            nw = wall_face.normalAt(*wall_face.Surface.parameter(p))
            worst = max(worst, math.degrees(math.acos(min(1.0, abs(nu.dot(nw))))))
    except Exception as exc:
        return "%s" % exc
    return worst


# -- the wall and the curves -----------------------------------------------------------------------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Surface2Loft")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xy():
    st.open_sketch_clicked(V(12, -8, 0))


def draw_wall_line():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None)
    if sk:
        st.add_lines(sk, [(0, 20), (5, 0)])


def finish_wall_line():
    h.ribbon("Finish Sketch")


def wall_extrude():
    h.check("left the sketch", h.in_sketch() is None)
    h.fit()
    h.click_empty()
    st.tab("SURFACE")
    st.menu("CREATE", "Extrude")


def wall_click():
    h.check("Extrude dialog", st.panel() is not None)
    h.fit()
    h.check("clicked the wall line", h.click_edge(V(2.5, 10, 0)))


def wall_offset():
    st.settle()
    st.choose("start", "Offset")


def wall_values():
    st.type_field("start_offset", "20")
    st.type_field("distance", "10")


def wall_ok():
    st.settle()
    s["wall"] = st.step_body()
    b = s["wall"].Shape.BoundBox if s.get("wall") else None
    h.check(
        "a wall z 20 .. 30",
        b is not None and abs(b.ZMin - 20) < 1e-6 and abs(b.ZMax - 30) < 1e-6,
        b,
    )
    st.ok()


def sketch(plane_point):
    def create():
        h.check("left the dialog / sketch", st.panel() is None and h.in_sketch() is None)
        h.fit()
        h.click_empty()
        st.tab("SOLID")
        h.ribbon("Create Sketch")

    def pick():
        st.open_sketch_clicked(plane_point)

    return create, pick


profile2_create, profile2_pick = sketch(V(12, -8, 0))


def profile2_draw():
    sk = h.in_sketch()
    h.check(
        "profile sketch on XY", sk is not None and sk.AttachmentSupport[0][0].Role == "XY_Plane"
    )
    if sk:
        st.add_lines(sk, [(0, 40), (10, 0)])


def finish_sketch():
    h.ribbon("Finish Sketch")


rail1_create, rail1_pick = sketch(V(0, -12, 8))


def rail1_draw():
    sk = h.in_sketch()
    h.check("rail sketch on YZ", sk is not None and sk.AttachmentSupport[0][0].Role == "YZ_Plane")
    if sk:
        st.add_lines(sk, [(20, 20), (40, 0)])


rail2_create, rail2_pick = sketch(V(12, 0, 8))


def rail2_draw():
    sk = h.in_sketch()
    h.check("rail sketch on XZ", sk is not None and sk.AttachmentSupport[0][0].Role == "XZ_Plane")
    if sk:
        st.add_lines(sk, [(5, 20), (10, 0)])


circle1_create, circle1_pick = sketch(V(12, -8, 0))


def circle1_draw():
    sk = h.in_sketch()
    h.check("circle sketch on XY", sk is not None and sk.AttachmentSupport[0][0].Role == "XY_Plane")
    if sk:
        st.add_circle(sk, -30, 0, 5)


circle2_create, circle2_pick = sketch(V(0, -12, 8))


def circle2_draw():
    sk = h.in_sketch()
    h.check("circle sketch on YZ", sk is not None and sk.AttachmentSupport[0][0].Role == "YZ_Plane")
    if sk:
        st.add_circle(sk, 0, 30, 5)


arc_create, arc_pick = sketch(V(12, 0, 8))


def arc_draw():
    from SciForgeTests.gui import sweep_loft_steps as sls

    sk = h.in_sketch()
    h.check("arc sketch on XZ", sk is not None and sk.AttachmentSupport[0][0].Role == "XZ_Plane")
    if sk:
        sls.add_arc(sk, (0, 0), 30, 90, 180)


# -- L1: two rails, Tangent, a refusal, New Component ------------------------------------------
def l1_loft():
    h.check("left the last sketch", h.in_sketch() is None)
    h.fit()
    h.click_empty()
    st.tab("SURFACE")
    st.menu("CREATE", "Loft")


def l1_click_edge():
    p = st.panel()
    h.check("Loft dialog open", p is not None and p.kind == "loft")
    if p is None:
        return
    guides = [p.rows["guide"][0].itemText(i) for i in range(p.rows["guide"][0].count())]
    h.check("Guide Type Rails / Centerline", guides == ["Rails", "Centerline"], guides)
    h.check(
        "Tangent Edges Merge offered, off",
        p.rows["merge"][0].isVisible() and not p.options["merge"],
    )
    h.fit()
    h.check("clicked the wall's lower edge", h.click_edge(V(2.5, 10, 20)))


def l1_click_line():
    st.settle()
    p = st.panel()
    h.check(
        "the edge alone is profile 1",
        p is not None and len(p.groups) == 1 and len(p.groups[0]) == 1,
        p and p.groups,
    )
    h.check("clicked the second profile", h.click_edge(V(5, 20, 0)))


def l1_rails_box():
    st.settle()
    p = st.panel()
    h.check("two profiles", p is not None and len(p.groups) == 2, p and p.groups)
    st.click_box("rails")


def l1_rail1():
    p = st.panel()
    h.check("the Rails box takes the clicks", p is not None and p.active == "rails", p and p.active)
    h.check("clicked rail 1", h.click_edge(V(0, 30, 10)))


def l1_rail2():
    st.settle()
    h.check("clicked rail 2", h.click_edge(V(7.5, 0, 10)))


def l1_lofted():
    st.settle()
    p = st.panel()
    h.check("two rails", p is not None and len(p.picks["rails"]) == 2, p and p.picks)
    s["loft1"] = st.step_body()
    body = s["loft1"]
    h.check("one face", body is not None and len(body.Shape.Faces) == 1)
    b = body.Shape.BoundBox if body is not None else None
    h.check(
        "from the wall's edge (z 20) to the line (z 0), x 0 .. 10, y 0 .. 40",
        b is not None
        and abs(b.ZMin) < 1e-3
        and abs(b.ZMax - 20) < 1e-3
        and abs(b.XMax - 10) < 1e-2
        and abs(b.YMax - 40) < 1e-2,
        b,
    )
    combo = p.rows["start_condition"][0] if p else None
    items = [combo.itemText(i) for i in range(combo.count())] if combo else []
    h.check(
        "First Profile: an edge of a body's choices",
        items == ["Connected (G0)", "Tangent (G1)", "Curvature (G2)"],
        items,
    )
    st.choose("start_condition", "Tangent (G1)")


def l1_tangent():
    st.settle()
    p = st.panel()
    h.check("Tangency Weight shown", p is not None and p.rows["start_weight"][0].isVisible())
    error = g1_error(s["loft1"], s["wall"], V(2.5, 10, 20))
    h.check(
        "the loft leaves the wall smoothly (within 1 degree)",
        isinstance(error, float) and error < 1.0,
        error,
    )
    h.check("still one face", len(s["loft1"].Shape.Faces) == 1)
    h.shot("1-rails-tangent")
    st.toggle_check("closed")


def l1_closed_refused():
    st.settle()
    text = st.message()
    h.check("Closed: the dialog says why", "closed loft cannot follow rails" in text, text)
    st.toggle_check("closed")


def l1_component():
    st.settle()
    h.check("no problem again", "closed loft" not in st.message(), st.message())
    st.choose("operation", "New Component")


def l1_ok():
    st.settle()
    st.ok()


def l1_done():
    from sciforge import components

    h.check("dialog closed", st.panel() is None)
    titles = st.timeline_titles()
    h.check("Loft 1 in the timeline", "Loft 1" in titles, titles)
    found = [b for b in st.surface_bodies() if b is not s["wall"]]
    h.check("the loft is a surface body", len(found) == 1, found)
    if found:
        s["loft1"] = found[0]
        part = components.container_of(found[0])
        h.check("in a new component", components.is_component(part), part)
    s["loft1_area"] = st.area(s.get("loft1"))


# -- L2: undo / redo -------------------------------------------------------------------------------
def l2_undo():
    st.undo()


def l2_undone():
    found = [b for b in st.surface_bodies() if b is not s["wall"]]
    h.check("undo takes the loft away", not found, found)


def l2_redo():
    st.redo()


def l2_redone():
    found = [b for b in st.surface_bodies() if b is not s["wall"]]
    h.check("redo brings it back", len(found) == 1, found)
    if found:
        s["loft1"] = found[0]
        h.check("the same area", st.near(st.area(found[0]), s["loft1_area"], 1e-6))


# -- L3: centerline + Direction ----------------------------------------------------------------
def l3_loft():
    h.fit()
    h.click_empty()
    st.menu("CREATE", "Loft")


def l3_circle1():
    h.check("Loft dialog open", st.panel() is not None)
    h.fit()
    h.check("clicked circle 1", h.click_edge(V(-35, 0, 0)))


def l3_circle2():
    st.settle()
    h.check("clicked circle 2", h.click_edge(V(0, -5, 30)))


def l3_centerline():
    st.settle()
    p = st.panel()
    h.check("two profiles", p is not None and len(p.groups) == 2, p and p.groups)
    st.choose("guide", "Centerline")


def l3_click_arc():
    p = st.panel()
    h.check("the Centerline box is shown", p is not None and p.is_shown("centerline"))
    h.check("and takes the clicks", p is not None and p.active == "centerline", p and p.active)
    h.check(
        "clicked the arc",
        h.click_edge(V(-30 * math.cos(math.radians(45)), 0, 30 * math.sin(math.radians(45)))),
    )


def l3_torus():
    st.settle()
    p = st.panel()
    h.check(
        "the arc is the centerline",
        p is not None and len(p.picks["centerline"]) == 1,
        p and p.picks,
    )
    s["loft2"] = st.step_body()
    h.check(
        "a quarter torus",
        st.near(st.area(s["loft2"]), TORUS, 2e-4),
        (st.area(s["loft2"]), TORUS),
    )
    st.choose("start_condition", "Direction")


def l3_direction():
    st.settle()
    p = st.panel()
    h.check(
        "Takeoff Weight and Angle shown", p is not None and p.rows["start_angle"][0].isVisible()
    )
    h.check(
        "still the tube along the arc",
        st.near(st.area(s["loft2"]), TORUS, 2e-3),
        (st.area(s["loft2"]), TORUS),
    )
    h.shot("2-centerline")
    st.ok()


def l3_done():
    h.check("dialog closed", st.panel() is None)
    titles = st.timeline_titles()
    h.check("Loft 2 in the timeline", "Loft 2" in titles, titles)
    s["loft2_area"] = st.area(s["loft2"])


# -- L4: save, reopen, edit --------------------------------------------------------------------
def l4_save_as():
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-surface2-"), "surface2_loft.FCStd")
    s["path"] = path
    doc().saveAs(path)
    h.check("saved", os.path.isfile(path), path)


def l4_ctrl_s():
    s["titles"] = st.timeline_titles()
    s["labels"] = [s[k].Label for k in ("wall", "loft1", "loft2")]
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


def l4_describe():
    h.check("the Save dialog asks for a version description", vi.version_dialog() is not None)
    vi.accept_save()


def l4_close():
    h.check("saved (nothing unsaved)", not doc().isTouched())
    App.closeDocument(doc().Name)


def l4_reopen():
    App.openDocument(s["path"])
    h.fit()


def l4_reopened():
    from sciforge import surface

    wall, loft1, loft2 = (by_label(x) for x in s["labels"])
    h.check("the bodies are back", None not in (wall, loft1, loft2), s["labels"])
    if None in (wall, loft1, loft2):
        return
    s["wall"], s["loft1"], s["loft2"] = wall, loft1, loft2
    h.check(
        "both lofts are surface bodies",
        surface.is_surface_body(loft1) and surface.is_surface_body(loft2),
    )
    h.check("loft 1 the same", st.near(st.area(loft1), s["loft1_area"], 1e-6), st.area(loft1))
    h.check("loft 2 the same", st.near(st.area(loft2), s["loft2_area"], 1e-6), st.area(loft2))
    titles = st.timeline_titles()
    h.check("the same timeline", titles == s["titles"], (titles, s["titles"]))
    steps = [x for x in doc().Objects if surface.kind_of(x)]
    h.check(
        "every surface step computed",
        steps and all("Invalid" not in x.State for x in steps),
        [(x.Name, x.State) for x in steps],
    )
    st.tab("SURFACE")


def l4_edit_loft2():
    h.check("double-clicked Loft 2", st.double_click_timeline("Loft 2"))


def l4_loft2_read():
    p = st.panel()
    h.check("edit dialog open", p is not None and p.editing)
    if p is None:
        return
    h.check("Centerline read back", p.options["guide"] == "centerline", p.options)
    h.check("the arc read back", len(p.picks["centerline"]) == 1, p.picks)
    h.check("Direction read back", p.options["start_condition"] == "direction", p.options)
    h.check("two profiles read back", len(p.groups) == 2, p.groups)
    st.esc()


def l4_edit_loft1():
    h.check("Esc closed it", st.panel() is None)
    h.check("double-clicked Loft 1", st.double_click_timeline("Loft 1"))


def l4_loft1_read():
    p = st.panel()
    h.check("edit dialog open", p is not None and p.editing)
    if p is None:
        return
    h.check("two rails read back", len(p.picks["rails"]) == 2, p.picks)
    h.check("Tangent read back", p.options["start_condition"] == "tangent", p.options)
    st.toggle_check("merge")


def l4_merged():
    st.settle()
    p = st.panel()
    h.check("Tangent Edges Merge on", p is not None and p.options["merge"])
    h.check("still one face", len(s["loft1"].Shape.Faces) == 1)
    st.ok()


def l4_done():
    h.check("dialog closed", st.panel() is None)
    error = g1_error(s["loft1"], s["wall"], V(2.5, 10, 20))
    h.check("still smooth with the wall", isinstance(error, float) and error < 1.0, error)


h.run(
    "surface2_loft",
    [
        new_design,
        pick_xy,
        draw_wall_line,
        finish_wall_line,
        wall_extrude,
        wall_click,
        wall_offset,
        wall_values,
        wall_ok,
        profile2_create,
        profile2_pick,
        profile2_draw,
        finish_sketch,
        rail1_create,
        rail1_pick,
        rail1_draw,
        finish_sketch,
        rail2_create,
        rail2_pick,
        rail2_draw,
        finish_sketch,
        circle1_create,
        circle1_pick,
        circle1_draw,
        finish_sketch,
        circle2_create,
        circle2_pick,
        circle2_draw,
        finish_sketch,
        arc_create,
        arc_pick,
        arc_draw,
        finish_sketch,
        l1_loft,
        l1_click_edge,
        l1_click_line,
        l1_rails_box,
        l1_rail1,
        l1_rail2,
        l1_lofted,
        l1_tangent,
        l1_closed_refused,
        l1_component,
        l1_ok,
        l1_done,
        l2_undo,
        l2_undone,
        l2_redo,
        l2_redone,
        l3_loft,
        l3_circle1,
        l3_circle2,
        l3_centerline,
        l3_click_arc,
        l3_torus,
        l3_direction,
        l3_done,
        l4_save_as,
        l4_ctrl_s,
        l4_describe,
        l4_close,
        l4_reopen,
        l4_reopened,
        l4_edit_loft2,
        l4_loft2_read,
        l4_edit_loft1,
        l4_loft1_read,
        l4_merged,
        l4_done,
    ],
)
