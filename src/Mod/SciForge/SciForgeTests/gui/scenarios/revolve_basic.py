# SPDX-License-Identifier: LGPL-2.1-or-later
"""Revolve like a Fusion user, only real input.

Create Sketch on XZ, a 10 x 20 rectangle against the Z axis (x 0..10, z 0..20), Finish
Sketch. Revolve with nothing selected: the sketch's one profile is taken by itself, the
origin axes appear as long lines; click the Z axis: a cylinder r10 h20 (Fusion's
default 360 degrees), operation New Body (the first solid). Type Full; Type Angle, type
90; drag the blue arrow round to about 200 degrees; Symmetric 45 each way; Two Sides 90
and 30; One Side 270; OK. Undo / redo. Double-click it in the timeline, Type Full, OK.

Second use: a sketch on XZ with a 3 x 4 rectangle inside the shaft's material (x 7..10,
z 8..12). Revolve, click the Z axis: Fusion switches to Cut by itself (a groove).
Cancel leaves the shaft as it was; Revolve again, OK: the groove is cut. Esc cancels a
third Revolve.

Hand-derived volumes: cylinder r10 h20 = 2000 pi; an angle a of it = 2000 pi a / 360;
groove = pi (10^2 - 7^2) 4 = 204 pi.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import revolve_input as ri

V = App.Vector
PI = math.pi
CYL = 2000.0 * PI
GROOVE = PI * (100.0 - 49.0) * 4.0
s = {}


def panel():
    return ri.panel()


def near(a, b, tol=1e-6):
    return ri.near(a, b, tol)


def bbox():
    return ri.bbox(h.body().Shape)


drag_handle = ri.drag_handle


# -- the sketch ---------------------------------------------------------------------------------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Revolve")
    h.fit()


def create_sketch():
    h.ribbon("Create Sketch")


def pick_xz():
    h.check("no pop-up", not h.popups(), h.popups())
    h.click(V(12, 0, 8))


def draw():
    sk = h.in_sketch()
    h.check("sketch open on XZ", sk is not None and sk.AttachmentSupport[0][0].Role == "XZ_Plane")
    if sk:
        h.draw_rectangle(sk, 0, 0, 10, 20)
        s["sk1"] = sk


def finish_sketch():
    h.ribbon("Finish Sketch")


def after_finish():
    h.check("left the sketch", h.in_sketch() is None)
    h.fit()


# -- revolve with nothing selected --------------------------------------------------------------
def revolve_nothing_selected():
    h.check("nothing selected", not Gui.Selection.getSelectionEx())
    h.ribbon("Revolve")


def dialog_open():
    p = panel()
    h.check("Revolve dialog open", p is not None and Gui.Control.activeDialog())
    if p is None:
        return
    h.check("no pop-up", not h.popups(), h.popups())
    h.check("the sketch's one profile is taken", len(p.profiles) == 1, p.profiles)
    h.check("Axis box waits for a click", p.active == "axis" and p.axis is None, p.active)
    h.check(
        "origin axes drawn to click",
        p.axes is not None
        and sorted(l[1] for l in p.axes.lines if l[1] != "construction") == ["X", "Y", "Z"],
    )
    h.check("no solid before the axis is picked", h.solid_volume() == 0.0, h.solid_volume())
    h.check(
        "Fusion's fields",
        [p.type.itemText(i) for i in range(p.type.count())] == ["Angle", "Full"]
        and [p.direction.itemText(i) for i in range(p.direction.count())]
        == ["One Side", "Two Sides", "Symmetric"]
        and [p.operation.itemText(i) for i in range(p.operation.count())]
        == ["Join", "Cut", "Intersect", "New Body"],
    )
    h.fit()
    h.shot("1-waiting-for-axis")


def click_z_axis():
    p = panel()
    if p is None:
        return
    h.fit()
    h.click(V(0, 0, 32))


def cylinder():
    p = panel()
    if p is None:
        return
    h.check("Z axis picked", p.axis is not None and p.axis[0].Role == "Z_Axis", p.axis)
    h.check("axis box shows it", p.fields["axis"].button.text() == "Z Axis")
    h.check("default 360 degrees: cylinder 2000 pi", near(h.solid_volume(), CYL), h.solid_volume())
    h.check("bbox r10 h20", bbox() == [-10, -10, 0, 10, 10, 20], bbox())
    h.check("first solid: New Body", p.operation.currentText() == "New Body")
    h.check("angle handle shown", "angle" in p.handles, list(p.handles))
    h.check("no error text", p.message.text() == "", p.message.text())
    h.fit()
    h.shot("2-cylinder")
    h.check("choose Type Full", ui.choose(p.type, "Full"))


def full():
    p = panel()
    h.check("Full: same cylinder", near(h.solid_volume(), CYL), h.solid_volume())
    h.check(
        "Full hides Direction and Angle",
        not p.direction.isVisible() and not p.angle.widget.isVisible(),
    )
    h.check("no handle for Full", not p.handles, list(p.handles))
    h.check("choose Type Angle", ui.choose(p.type, "Angle"))


def type_90():
    p = panel()
    h.check("Angle shows the field again", p.angle.widget.isVisible())
    ui.type_into(p.angle.widget, "90")


def angle_90():
    h.check("90 degrees: a quarter", near(h.solid_volume(), CYL / 4), h.solid_volume())
    h.check("turns right-handed about +Z (towards +Y)", bbox() == [0, 0, 0, 10, 10, 20], bbox())
    h.fit()


def drag_arrow():
    p = panel()
    handle = p.handles.get("angle")
    h.check(
        "handle at 90", handle is not None and near(handle.angle(), 90.0), handle and handle.angle()
    )
    if handle is not None:
        drag_handle(handle, 200.0)


drag_arrow.wait_ms = 1200


def dragged():
    p = panel()
    angle = p.angle.value()
    h.check("dragging the arrow round changed the angle", 170.0 < angle < 230.0, angle)
    h.check(
        "volume follows the angle field",
        near(h.solid_volume(), CYL * angle / 360.0, 1e-5),
        (h.solid_volume(), angle),
    )
    h.shot("3-dragged")
    h.check("choose Direction Symmetric", ui.choose(p.direction, "Symmetric"))


def symmetric():
    p = panel()
    h.check("symmetric angle at most 180", abs(p.angle.value()) <= 180.0, p.angle.value())
    ui.type_into(p.angle.widget, "45")


def symmetric_45():
    b = bbox()
    y = round(10 * math.sin(math.radians(45)), 4)
    h.check("symmetric 45 each way: a quarter", near(h.solid_volume(), CYL / 4), h.solid_volume())
    h.check("symmetric about the sketch plane", b[1] == -y and b[4] == y, b)
    h.check("choose Direction Two Sides", ui.choose(panel().direction, "Two Sides"))


def two_sides():
    p = panel()
    h.check("side two field shown", p.angle2.widget.isVisible())
    h.check("two handles", set(p.handles) == {"angle", "angle2"}, list(p.handles))
    ui.type_into(p.angle.widget, "90")


def two_sides_a2():
    ui.type_into(panel().angle2.widget, "30")


def two_sides_check():
    b = bbox()
    h.check("90 + 30 = a third", near(h.solid_volume(), CYL / 3), h.solid_volume())
    h.check("side two turns the other way", b[1] == -5.0 and b[4] == 10.0, b)
    h.shot("4-two-sides")
    h.check("choose One Side", ui.choose(panel().direction, "One Side"))


def one_side_270():
    ui.type_into(panel().angle.widget, "270")


def ok_first():
    h.check("270: three quarters", near(h.solid_volume(), CYL * 0.75), h.solid_volume())
    h.task_button("OK")


def after_ok():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("kept: 270 degrees", near(h.solid_volume(), CYL * 0.75), h.solid_volume())
    h.check("the sketch is hidden (Fusion)", not s["sk1"].ViewObject.Visibility)
    rev = [o for o in h.body().Group if o.TypeId == "PartDesign::Revolution"]
    h.check("one Revolution in the body", len(rev) == 1, [o.Name for o in h.body().Group])
    s["rev"] = rev[0] if rev else None
    h.check("Revolve 1 in the timeline", "Revolve 1" in ui.timeline_titles(), ui.timeline_titles())
    h.check("nothing selected after OK", not Gui.Selection.getSelectionEx())
    h.shot("5-ok")


def undo():
    h.check("Undo button", ui.quick_access("Undo"))


def undone():
    h.check("Undo removes the revolve (one step)", h.solid_volume() == 0.0, h.solid_volume())


def redo():
    h.check("Redo button", ui.quick_access("Redo"))


def redone():
    h.check("Redo brings it back", near(h.solid_volume(), CYL * 0.75), h.solid_volume())


def edit_again():
    h.check(
        "double-click Revolve 1 in the timeline",
        ui.double_click_timeline("Revolve 1"),
        ui.timeline_titles(),
    )


def editing():
    p = panel()
    h.check("Revolve dialog edits it", p is not None and p.editing)
    if p is None:
        return
    h.check("edit shows 270", near(p.angle.value(), 270.0), p.angle.value())
    h.check("edit shows the Z axis", p.axis is not None and p.axis[0].Role == "Z_Axis", p.axis)
    h.check("edit shows the profile", len(p.profiles) == 1, p.profiles)
    h.check("choose Full", ui.choose(p.type, "Full"))


def edit_ok():
    h.check("edit preview: full", near(h.solid_volume(), CYL), h.solid_volume())
    h.task_button("OK")


def after_edit():
    h.check("edit kept: full cylinder", near(h.solid_volume(), CYL), h.solid_volume())
    h.check(
        "still one revolve",
        len([o for o in h.body().Group if o.TypeId == "PartDesign::Revolution"]) == 1,
    )
    h.fit()


# -- second use: a groove (auto Cut), Cancel first --------------------------------------------
def create_sketch_2():
    h.click_empty()
    h.ribbon("Create Sketch")


def pick_xz_2():
    h.fit()
    h.click(V(12, 0, -10))


def draw_2():
    sk = h.in_sketch()
    h.check(
        "second sketch open on XZ",
        sk is not None and sk is not s.get("sk1") and sk.AttachmentSupport[0][0].Role == "XZ_Plane",
    )
    if sk:
        h.draw_rectangle(sk, 7, 8, 10, 12)
        s["sk2"] = sk


def finish_sketch_2():
    h.ribbon("Finish Sketch")


def revolve_2():
    h.fit()
    h.ribbon("Revolve")


def click_z_2():
    h.fit()
    p = panel()
    h.check("the new sketch's profile is taken", p is not None and len(p.profiles) == 1)
    h.click(V(0, 0, 32))


def groove_preview():
    p = panel()
    if p is None:
        return
    h.check(
        "revolving into the shaft: Cut chosen by itself",
        p.operation.currentText() == "Cut",
        p.operation.currentText(),
    )
    h.check(
        "preview is a Groove",
        p.target is not None and p.target.TypeId == "PartDesign::Groove",
        p.target and p.target.TypeId,
    )
    h.check("groove cut", near(h.solid_volume(), CYL - GROOVE), h.solid_volume())
    h.shot("6-groove")
    h.task_button("Cancel")


def cancelled():
    h.check("Cancel closes the dialog", not Gui.Control.activeDialog())
    h.check("Cancel leaves the shaft unchanged", near(h.solid_volume(), CYL), h.solid_volume())
    h.check("the shaft is shown", ri.shown(h.body()))
    h.check(
        "no Groove left",
        not [o for o in App.ActiveDocument.Objects if o.TypeId == "PartDesign::Groove"],
    )
    h.fit()


def revolve_3():
    h.ribbon("Revolve")


def click_z_3():
    h.fit()
    h.click(V(0, 0, 32))


def ok_groove():
    p = panel()
    h.check("Cut again", p is not None and p.operation.currentText() == "Cut")
    h.task_button("OK")


def grooved():
    h.check("groove kept", near(h.solid_volume(), CYL - GROOVE), h.solid_volume())
    h.check("Revolve 2 in the timeline", "Revolve 2" in ui.timeline_titles(), ui.timeline_titles())
    s["volume"] = h.solid_volume()
    h.shot("7-grooved")
    h.fit()


def esc_case():
    h.ribbon("Revolve")


def esc_now():
    h.check("dialog open", panel() is not None)
    h.press(QtCore.Qt.Key_Escape)


def after_esc():
    h.check("Esc closes the dialog", not Gui.Control.activeDialog())
    h.check("Esc changes nothing", near(h.solid_volume(), s["volume"]), h.solid_volume())


h.run(
    "revolve_basic",
    [
        new_design,
        create_sketch,
        pick_xz,
        draw,
        finish_sketch,
        after_finish,
        revolve_nothing_selected,
        dialog_open,
        click_z_axis,
        cylinder,
        full,
        type_90,
        angle_90,
        drag_arrow,
        dragged,
        symmetric,
        symmetric_45,
        two_sides,
        two_sides_a2,
        two_sides_check,
        one_side_270,
        ok_first,
        after_ok,
        undo,
        undone,
        redo,
        redone,
        edit_again,
        editing,
        edit_ok,
        after_edit,
        create_sketch_2,
        pick_xz_2,
        draw_2,
        finish_sketch_2,
        revolve_2,
        click_z_2,
        groove_preview,
        cancelled,
        revolve_3,
        click_z_3,
        ok_groove,
        grooved,
        esc_case,
        esc_now,
        after_esc,
    ],
)
