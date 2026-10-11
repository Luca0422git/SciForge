# SPDX-License-Identifier: LGPL-2.1-or-later
"""Loft like a Fusion user, only real input.

Box: a 20 x 20 square on XY, Extrude 10. CONSTRUCT > Offset Plane: click the top face, type
20: a plane at z 30. Create Sketch on it: a circle r10. CREATE > Loft with nothing selected:
click the box's top face, then inside the circle: the square blends into the circle (Join).
Move the first profile down the list (same shape, the order swapped), take one out with the
list's x (no loft until two are picked again), click it again. Closed with only two profiles
says why in the dialog; clear it; OK. Undo / redo. Double-click it in the timeline, choose
Cut: the dialog says the cut does not touch the box and stays open; Cancel leaves the part.

Second use: a sketch on XZ with a point at (0, 45). Loft: click the round top face of the
first loft, then the point: a cone on top. OK. Esc cancels a third Loft.

Hand-derived: a loft between a square of half-side s and a circle of radius r (both centred,
h apart) blends matching points in a straight line (OpenCASCADE puts the circle's points
across from the square's corners), so a section at t is (1-t) P + t Q and
V = h (A_P / 3 + A_Q / 3 + M / 6) with M = 16 sqrt(2) s r / pi; here s = r = 10, h = 20.
Cone on a circle r10, 15 high: pi 100 15 / 3.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sweep_loft_steps as st

V = App.Vector
PI = math.pi
BOX = 20.0 * 20.0 * 10.0
LOFT = 20.0 * (400.0 / 3 + PI * 100 / 3 + 16 * math.sqrt(2) * 100 / PI / 6)
CONE = PI * 100.0 * 15.0 / 3.0
s = {}


def panel():
    return st.panel("loft")


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Loft")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xy():
    h.click(V(12, -8, 0))


def draw_square():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None)
    if sk:
        h.draw_rectangle(sk, -10, -10, 10, 10)


def finish_square():
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
        ui.type_into(field, "10")


def extrude_ok():
    h.task_button("OK")


def box_made():
    h.check("box 20 x 20 x 10", st.near(h.solid_volume(), BOX), h.solid_volume())
    h.fit()
    h.click_empty()
    h.ribbon("Offset Plane")


def pick_top_face():
    h.click(V(5, -5, 10))


def plane_distance():
    from sciforge import construct_ui

    p = construct_ui.ConstructPanel.last
    h.check("offset plane dialog", p is not None and p.field is not None)
    if p is not None and p.field is not None:
        ui.type_into(p.field.widget, "20")


def plane_ok():
    h.task_button("OK")


def plane_made():
    planes = [o for o in App.ActiveDocument.Objects if o.TypeId == "PartDesign::Plane"]
    h.check("a plane", len(planes) == 1, planes)
    if planes:
        s["plane"] = planes[0]
        h.check("at z 30", st.near(planes[0].Placement.Base.z, 30.0), planes[0].Placement)
    h.fit()
    h.ribbon("Create Sketch")


def pick_plane():
    h.click(V(-6, 6, 30))


def draw_circle():
    sk = h.in_sketch()
    h.check(
        "sketch open on the plane", sk is not None and sk.AttachmentSupport[0][0] is s.get("plane")
    )
    if sk:
        h.draw_circle(sk, 0, 0, 10)
        s["circle"] = sk


def finish_circle():
    h.ribbon("Finish Sketch")


def hide_plane():
    """The plane is in front of the box's top face: hide it with its eye in the browser."""
    from SciForgeTests.gui import timeline_input as ti

    h.check("plane eye clicked", ti.click_eye(s["plane"].Label))


def plane_hidden():
    h.check("the plane is hidden", not s["plane"].ViewObject.Visibility)


# -- the loft ----------------------------------------------------------------------------------------
def loft_start():
    h.fit()
    h.click_empty()
    st.menu("Loft")


def dialog_open():
    p = panel()
    h.check("Loft dialog open", p is not None and Gui.Control.activeDialog())
    if p is None:
        return
    h.check("no pop-up", not h.popups(), h.popups())
    h.check("nothing picked yet", not p.profiles, p.profiles)
    h.check(
        "Fusion's fields",
        [p.guide.itemText(i) for i in range(p.guide.count())] == ["Rails", "Centerline"]
        and [p.operation.itemText(i) for i in range(p.operation.count())]
        == ["Join", "Cut", "Intersect", "New Body"]
        and p.closed.isVisible()
        and p.merge.isVisible(),
    )
    h.check(
        "Tangent Edges Merge is greyed and says why",
        not p.merge.isEnabled() and "SciForge" in p.merge.toolTip(),
    )
    h.fit()
    h.click(V(5, -5, 10))


def first_profile():
    p = panel()
    h.check(
        "the top face is profile 1",
        len(p.profiles) == 1 and p.profiles[0][1].startswith("Face"),
        p.profiles,
    )
    h.check("one row in the list", p.list.count() == 1, p.list.count())
    h.check("no loft with one profile", st.near(h.solid_volume(), BOX), h.solid_volume())
    h.click(V(-4, 4, 30))


def lofted():
    p = panel()
    h.check("the circle is profile 2", len(p.profiles) == 2, p.profiles)
    h.check(
        "two rows",
        p.list.count() == 2 and p.list.item(1).text().startswith("2"),
        [p.list.item(i).text() for i in range(p.list.count())],
    )
    h.check("Join", p.operation.currentText() == "Join", p.operation.currentText())
    h.check(
        "FreeCAD's own loft",
        p.target is not None and p.target.TypeId == "PartDesign::AdditiveLoft",
        p.target and p.target.TypeId,
    )
    h.check(
        "box + square-to-circle loft",
        st.near(h.solid_volume(), BOX + LOFT, 1e-6),
        (h.solid_volume(), BOX + LOFT),
    )
    h.check("bbox", st.bbox(h.body().Shape) == [-10, -10, 0, 10, 10, 30], st.bbox(h.body().Shape))
    h.fit()
    h.shot("1-loft")
    rect = p.list.visualItemRect(p.list.item(0))
    from SciForgeTests.gui import widget_input as wi

    wi.click(p.list.viewport(), rect.center())


def move_down():
    p = panel()
    h.check("row 1 selected", p.list.currentRow() == 0, p.list.currentRow())
    s["first"] = p.profiles[0]
    ui.click(p.down)


def moved():
    p = panel()
    h.check("the face moved to second place", p.profiles[1] == s["first"], p.profiles)
    h.check(
        "the list follows",
        p.list.item(1).text().startswith("2") and "face" in p.list.item(1).text(),
        p.list.item(1).text(),
    )
    h.check(
        "same shape the other way round",
        st.near(h.solid_volume(), BOX + LOFT, 1e-6),
        h.solid_volume(),
    )
    ui.click(p.remove)


def removed():
    p = panel()
    h.check("one profile left", len(p.profiles) == 1, p.profiles)
    h.check(
        "the loft is gone until two are picked", st.near(h.solid_volume(), BOX), h.solid_volume()
    )
    h.fit()
    h.click(V(5, -5, 10))


def picked_again():
    p = panel()
    h.check("two profiles again", len(p.profiles) == 2, p.profiles)
    h.check("loft back", st.near(h.solid_volume(), BOX + LOFT, 1e-6), h.solid_volume())
    from SciForgeTests.gui import hole_steps

    hole_steps.click_checkbox(p.closed)


def closed_two():
    p = panel()
    h.check("Closed checked", p.closed.isChecked())
    h.check(
        "the dialog says a closed loft needs three", "three" in p.message.text(), p.message.text()
    )
    from SciForgeTests.gui import hole_steps

    hole_steps.click_checkbox(p.closed)


def open_again():
    p = panel()
    h.check("Closed cleared", not p.closed.isChecked())
    h.check("no message", p.message.text() == "", p.message.text())
    h.check("loft back", st.near(h.solid_volume(), BOX + LOFT, 1e-6), h.solid_volume())
    h.task_button("OK")


def kept():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("kept", st.near(h.solid_volume(), BOX + LOFT, 1e-6), h.solid_volume())
    h.check("Loft 1 in the timeline", "Loft 1" in st.timeline_titles(), st.timeline_titles())
    h.check("the circle sketch is hidden", not s["circle"].ViewObject.Visibility)
    h.check("the part is shown", st.shown(h.body()))


def undo():
    h.check("Undo button", ui.quick_access("Undo"))


def undone():
    h.check("Undo removes the loft (one step)", st.near(h.solid_volume(), BOX), h.solid_volume())


def redo():
    h.check("Redo button", ui.quick_access("Redo"))


def redone():
    h.check("Redo brings it back", st.near(h.solid_volume(), BOX + LOFT, 1e-6), h.solid_volume())
    s["volume"] = h.solid_volume()


def edit():
    h.check("double-click Loft 1", st.edit_in_timeline("Loft 1"))


def editing():
    p = panel()
    h.check("editing", p is not None and p.editing)
    if p is None:
        return
    h.check("edit lists both profiles in order", p.list.count() == 2, p.list.count())
    h.check("choose Cut", ui.choose(p.operation, "Cut"))


def cut_refused():
    p = panel()
    h.check("dialog stays open", p is not None)
    if p is None:
        return
    text = p.message.text()
    h.check("the dialog says why", text.startswith("⚠") and len(text) > 5, text)
    h.task_button("Cancel")


def cancelled():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("Cancel keeps the loft", st.near(h.solid_volume(), s["volume"], 1e-6), h.solid_volume())
    h.check("still one loft", len(st.features("loft")) == 1, st.features("loft"))
    h.fit()
    h.ribbon("Create Sketch")


# -- second use: a cone to a point ----------------------------------------------------------------
def pick_xz():
    h.click(V(-17, 0, 12))


def draw_point():
    sk = h.in_sketch()
    h.check("sketch open on XZ", sk is not None)
    if sk:
        st.add_point(sk, 0, 45)
        s["point"] = sk


def finish_point():
    h.ribbon("Finish Sketch")


def loft_point():
    h.fit()
    h.click_empty()
    st.menu("Loft")


def click_round_face():
    h.fit()
    h.click(V(-4, 4, 30))


def click_point():
    p = panel()
    h.check(
        "the round top face is profile 1", p is not None and len(p.profiles) == 1, p and p.profiles
    )
    h.click(V(0, 0, 45))


def cone():
    p = panel()
    h.check(
        "the point is profile 2",
        p is not None and len(p.profiles) == 2 and p.profiles[1][1].startswith("Vertex"),
        p and p.profiles,
    )
    h.check(
        "a cone on top",
        st.near(h.solid_volume(), s["volume"] + CONE, 1e-6),
        (h.solid_volume(), s["volume"] + CONE),
    )
    h.shot("2-cone")
    h.task_button("OK")


def cone_kept():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("kept", st.near(h.solid_volume(), s["volume"] + CONE, 1e-6), h.solid_volume())
    h.check("Loft 2 in the timeline", "Loft 2" in st.timeline_titles(), st.timeline_titles())
    s["volume2"] = h.solid_volume()
    st.menu("Loft")


def esc_now():
    h.check("dialog open", panel() is not None)
    h.press(QtCore.Qt.Key_Escape)


def after_esc():
    h.check("Esc closes the dialog", not Gui.Control.activeDialog())
    h.check("Esc changes nothing", st.near(h.solid_volume(), s["volume2"]), h.solid_volume())


h.run(
    "sweep_loft_loft",
    [
        new_design,
        pick_xy,
        draw_square,
        finish_square,
        extrude,
        extrude_distance,
        extrude_ok,
        box_made,
        pick_top_face,
        plane_distance,
        plane_ok,
        plane_made,
        pick_plane,
        draw_circle,
        finish_circle,
        hide_plane,
        plane_hidden,
        loft_start,
        dialog_open,
        first_profile,
        lofted,
        move_down,
        moved,
        removed,
        picked_again,
        closed_two,
        open_again,
        kept,
        undo,
        undone,
        redo,
        redone,
        edit,
        editing,
        cut_refused,
        cancelled,
        pick_xz,
        draw_point,
        finish_point,
        loft_point,
        click_round_face,
        click_point,
        cone,
        cone_kept,
        esc_now,
        after_esc,
    ],
)
