# SPDX-License-Identifier: LGPL-2.1-or-later
"""Loft with rails and with a centerline. Only real input.

A 10 x 10 plate 2 thick (sketch on XY, Extrude 2). CONSTRUCT > Offset Plane 40 above its
top face, a 10 x 10 square sketched on it, the plane hidden with its eye in the browser. A
sketch on XZ with two rails, arcs from (5, 2) through (8, 22) to (5, 42) and the same on the
other side, and a straight centerline at x = 12. CREATE > Loft: click the plate's top face
and inside the top square: a straight block. Click the Rails box, click the first rail: the
loft leans over to touch it (every section the same square, moved: the volume stays).
Click the second rail: the sections grow to touch both (a barrel). Guide Type Centerline,
click the line at x 12: the profiles stay square to it, a straight block again. OK. Edit it
from the timeline, Cancel.

Hand-derived: a block 10 x 10 x 40 on the 10 x 10 x 2 plate: 4000 + 200. One rail moves
each section without changing it: the same volume (Cavalieri). Two rails at x(z) and -x(z)
scale the square to 2 x(z) wide: V = 200 + integral of 4 x(z)^2 dz from 2 to 42, with x(z)
on the arc's circle (centre x -60.17 at z 22, radius 68.17); the loft goes through sections
fitted every 40/9 mm, so it matches to about 0.1 %.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import sweep_loft_steps as st

V = App.Vector
PLATE = 200.0
BLOCK = PLATE + 4000.0
CX = -361.0 / 6.0
R = 8.0 - CX


def rail_x(z):
    return CX + math.sqrt(R * R - (z - 22.0) ** 2)


BARREL = PLATE + st.simpson(lambda z: 4.0 * rail_x(z) ** 2, 2.0, 42.0)
s = {}


def panel():
    return st.panel("loft")


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("LoftGuides")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xy():
    pl.click_square("XY_Plane")  # where the square shows (was 12, -8, 0)


def draw_plate():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None)
    if sk:
        h.draw_rectangle(sk, -5, -5, 5, 5)


def finish_plate():
    h.ribbon("Finish Sketch")


def extrude():
    h.fit()
    h.press("e")


def extrude_distance():
    from sciforge import taskui

    p = taskui.current()
    field = getattr(getattr(p, "distance", None), "widget", None)
    h.check("extrude dialog", field is not None)
    if field is not None:
        ui.type_into(field, "2")


def extrude_ok():
    h.task_button("OK")


def plate_made():
    h.check("plate 10 x 10 x 2", st.near(h.solid_volume(), PLATE), h.solid_volume())
    h.fit()
    h.click_empty()
    h.ribbon("Offset Plane")


def pick_top():
    h.click(V(2, -2, 2))


def plane_distance():
    from sciforge import construct_ui

    p = construct_ui.ConstructPanel.last
    if p is not None and p.field is not None:
        ui.type_into(p.field.widget, "40")


def plane_ok():
    h.task_button("OK")


def top_sketch():
    planes = [o for o in App.ActiveDocument.Objects if o.TypeId == "PartDesign::Plane"]
    h.check("a plane at z 42", len(planes) == 1 and st.near(planes[0].Placement.Base.z, 42.0))
    s["plane"] = planes[0] if planes else None
    h.fit()
    h.ribbon("Create Sketch")


def pick_plane():
    h.click(V(-3, 3, 42))


def draw_top():
    sk = h.in_sketch()
    h.check("sketch on the plane", sk is not None and sk.AttachmentSupport[0][0] is s.get("plane"))
    if sk:
        h.draw_rectangle(sk, -5, -5, 5, 5)


def finish_top():
    h.ribbon("Finish Sketch")


def hide_plane():
    h.check("plane eye clicked", st.hide_in_browser(s["plane"]))


def rails_sketch():
    h.check("plane hidden", not s["plane"].ViewObject.Visibility)
    h.fit()
    h.ribbon("Create Sketch")


def pick_xz():
    pl.click_square("XZ_Plane")  # where the square shows (was -8, 0, 7)


def draw_rails():
    sk = h.in_sketch()
    h.check("sketch open on XZ", sk is not None and sk.AttachmentSupport[0][0].Role == "XZ_Plane")
    if sk:
        st.add_arc3(sk, (5, 2), (8, 22), (5, 42))
        st.add_arc3(sk, (-5, 2), (-8, 22), (-5, 42))
        st.add_lines(sk, [(12, 2), (12, 42)])
        s["guides"] = sk


def finish_rails():
    h.ribbon("Finish Sketch")


def loft_start():
    h.fit()
    h.click_empty()
    st.menu("Loft")


def click_plate():
    h.fit()
    h.click(V(2, -2, 2))


def click_top():
    p = panel()
    h.check("plate face is profile 1", p is not None and len(p.profiles) == 1, p and p.profiles)
    h.click(V(-2, 2, 42))


def block():
    p = panel()
    h.check("two profiles", p is not None and len(p.profiles) == 2, p and p.profiles)
    h.check("a straight block", st.near(h.solid_volume(), BLOCK, 1e-6), h.solid_volume())
    h.check("Rails by default", p.guide.currentText() == "Rails")
    ui.click(p.fields["rails"].button)


def rails_box():
    p = panel()
    h.check("the Rails box waits", p.active == "rails", p.active)
    h.fit()
    h.check("clicked rail 1", h.click_edge(V(8, 0, 22)))


rails_box.wait_ms = 2500  # fitting sections to the rail takes a moment (under load > 1 s)


def one_rail():
    p = panel()
    h.check("one rail picked", len(p.rails) == 1, p.rails)
    h.check(
        "SciForge's loft for rails",
        p.target is not None and p.target.SciForgeType == "Loft",
        p.target and p.target.TypeId,
    )
    h.check(
        "the sections only move: same volume",
        st.near(h.solid_volume(), BLOCK, 1e-4),
        h.solid_volume(),
    )
    bb = st.bbox(h.body().Shape)
    h.check("it leans out to the rail", abs(bb[3] - 8.0) < 0.05 and abs(bb[0] + 5.0) < 0.05, bb)
    h.shot("1-one-rail")
    h.check("clicked rail 2", h.click_edge(V(-8, 0, 22)))


one_rail.wait_ms = 3000  # fitting sections to two rails takes a moment


def two_rails():
    p = panel()
    h.check("two rails", len(p.rails) == 2, p.rails)
    h.check(
        "a barrel between the rails",
        st.near(h.solid_volume(), BARREL, 2e-3),
        (h.solid_volume(), BARREL),
    )
    bb = st.bbox(h.body().Shape)
    h.check(
        "8 out each way in x and y",
        all(abs(abs(v) - 8.0) < 0.05 for v in (bb[0], bb[1], bb[3], bb[4])),
        bb,
    )
    h.fit()
    h.shot("2-two-rails")
    h.check("choose Centerline", ui.choose(p.guide, "Centerline"))


def centerline_box():
    p = panel()
    h.check(
        "the Centerline box is shown and waits",
        p.fields["centerline"].widget.isVisible() and p.active == "centerline",
        p.active,
    )
    h.check(
        "without a centerline: the plain block",
        st.near(h.solid_volume(), BLOCK, 1e-6),
        h.solid_volume(),
    )
    h.fit()
    h.check("clicked the centerline", h.click_edge(V(12, 0, 22)))


def along_line():
    p = panel()
    h.check("centerline picked", len(p.centerline) == 1, p.centerline)
    h.check(
        "square to the line: the block", st.near(h.solid_volume(), BLOCK, 1e-6), h.solid_volume()
    )
    h.task_button("OK")


def kept():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("kept", st.near(h.solid_volume(), BLOCK, 1e-6), h.solid_volume())
    h.check("the guides sketch is hidden", not s["guides"].ViewObject.Visibility)
    h.check("Loft 1 in the timeline", "Loft 1" in st.timeline_titles(), st.timeline_titles())


def edit():
    h.check("double-click Loft 1", st.edit_in_timeline("Loft 1"))


def editing():
    p = panel()
    h.check("editing", p is not None and p.editing)
    if p is None:
        return
    h.check("edit shows Centerline", p.guide.currentText() == "Centerline", p.guide.currentText())
    h.check("edit shows the line", len(p.centerline) == 1, p.centerline)
    h.check("the guides sketch is shown while editing", s["guides"].ViewObject.Visibility)
    h.check("choose Rails", ui.choose(p.guide, "Rails"))


def edit_cancel():
    h.task_button("Cancel")


def cancelled():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("Cancel keeps the block", st.near(h.solid_volume(), BLOCK, 1e-6), h.solid_volume())
    h.check("the sketch hides again", not s["guides"].ViewObject.Visibility)


h.run(
    "sweep_loft_loft_guides",
    [
        new_design,
        pick_xy,
        draw_plate,
        finish_plate,
        extrude,
        extrude_distance,
        extrude_ok,
        plate_made,
        pick_top,
        plane_distance,
        plane_ok,
        top_sketch,
        pick_plane,
        draw_top,
        finish_top,
        hide_plane,
        rails_sketch,
        pick_xz,
        draw_rails,
        finish_rails,
        loft_start,
        click_plate,
        click_top,
        block,
        rails_box,
        one_rail,
        two_rails,
        centerline_box,
        along_line,
        kept,
        edit,
        editing,
        edit_cancel,
        cancelled,
    ],
)
