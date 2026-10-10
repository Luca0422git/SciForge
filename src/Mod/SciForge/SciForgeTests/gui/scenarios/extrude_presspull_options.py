# SPDX-License-Identifier: LGPL-2.1-or-later
"""Extrude's Fusion options on one feature, only real input: Start (Offset / Profile
Plane), Direction (Symmetric with Half and Whole Length, Two Sides with a tapered side
two), the taper handle dragged in the 3D view, OK, edit again from the timeline, and
Esc to cancel a second extrude.

Profile: the 40 x 30 rectangle of a sketch on XY, picked by itself (one profile).
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}


def panel():
    from sciforge import extrude_ui

    return extrude_ui.ExtrudePanel.last


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def box():
    shape = h.body().Shape
    b = shape.BoundBox
    return (round(b.ZMin, 6), round(b.ZMax, 6))


def simpson_frustum(a, b, h_, d):
    """Rectangle a x b shrinking by d on every side over the height h_ (exact: the
    area is quadratic in the height)."""
    mid = (a - d) * (b - d)
    top = (a - 2 * d) * (b - 2 * d)
    return h_ / 6.0 * (a * b + 4 * mid + top)


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Options")
    h.fit()


def create_sketch():
    h.ribbon("Create Sketch")


def pick_xy():
    h.click(V(12, -8, 0))


def draw():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None)
    if sk:
        h.draw_rectangle(sk, 0, 0, 40, 30)


def finish_sketch():
    h.ribbon("Finish Sketch")


def extrude_it():
    h.fit()
    h.press("e")


def started():
    p = panel()
    h.check("the single profile is picked by itself", p is not None and p.target is not None)
    h.check(
        "first solid: operation New Body",
        p.operation.currentText() == "New Body",
        p.operation.currentText(),
    )
    h.check("10 mm: 12000", near(h.solid_volume(), 12000.0), h.solid_volume())
    h.check(
        "Start offers Profile Plane, Offset, Object",
        [p.start.itemText(i) for i in range(p.start.count())]
        == ["Profile Plane", "Offset", "Object"],
    )
    h.check("choose Start: Offset", ui.choose(p.start, "Offset"))


def offset_shown():
    p = panel()
    h.check("Offset field shown", p.start_offset.widget.isVisible())
    ui.type_into(p.start_offset.widget, "5")


def offset_5():
    p = panel()
    h.check("start offset 5: z 5 to 15", box() == (5.0, 15.0), box())
    h.check("still 12000", near(h.solid_volume(), 12000.0), h.solid_volume())
    h.check("offset handle shown", "offset" in p.draggers, list(p.draggers))
    h.shot("1-offset")
    h.check("choose Start: Profile Plane", ui.choose(p.start, "Profile Plane"))


def back_to_plane():
    p = panel()
    h.check("back on the profile plane: z 0 to 10", box() == (0.0, 10.0), box())
    h.check("choose Direction: Symmetric", ui.choose(p.direction, "Symmetric"))


def symmetric_half():
    p = panel()
    h.check("Measurement shown", p.measurement.isVisible())
    h.check("Half Length by default", p.measurement.currentText() == "Half Length")
    h.check("symmetric half 10: z -10 to 10", box() == (-10.0, 10.0), box())
    h.check("24000", near(h.solid_volume(), 24000.0), h.solid_volume())
    h.check("choose Whole Length", ui.choose(p.measurement, "Whole Length"))


def symmetric_whole():
    p = panel()
    h.check("symmetric whole 10: z -5 to 5", box() == (-5.0, 5.0), box())
    h.check("choose Direction: Two Sides", ui.choose(p.direction, "Two Sides"))


def two_sides():
    p = panel()
    h.check("side two fields shown", p.distance2.widget.isVisible() and p.taper2.widget.isVisible())
    h.check("second arrow shown", "distance2" in p.draggers, list(p.draggers))
    ui.type_into(p.distance2.widget, "4")


def two_sides_4():
    p = panel()
    h.check("two sides 10 and 4: z -4 to 10", box() == (-4.0, 10.0), box())
    ui.type_into(p.taper2.widget, "-10")


def two_sides_taper():
    d = 4 * math.tan(math.radians(10))
    want = 12000.0 + simpson_frustum(40.0, 30.0, 4.0, d)
    h.check(
        "side two tapered -10 deg (narrows)",
        near(h.solid_volume(), want, 1e-5),
        (h.solid_volume(), want),
    )
    h.shot("2-two-sides")
    h.check("choose Direction: One Side", ui.choose(panel().direction, "One Side"))


def one_side_again():
    h.check("one side again: 12000", near(h.solid_volume(), 12000.0), h.solid_volume())
    h.fit()


def drag_taper():
    p = panel()
    handle = p.draggers.get("taper")
    h.check("taper handle shown", handle is not None, list(p.draggers))
    if handle is None:
        return
    now, later = handle.screen_points(12.0)
    h.drag(h.screen_point(now), h.screen_point(later), steps=16)


def taper_dragged():
    p = panel()
    angle = p.taper.value()
    h.check("dragging the taper handle outward gives a positive angle", angle > 3.0, angle)
    h.check("a positive taper widens the extrusion", h.solid_volume() > 12000.5, h.solid_volume())
    h.shot("3-taper")
    ui.type_into(p.taper.widget, "0")


def ok_options():
    h.check("taper back to 0: 12000", near(h.solid_volume(), 12000.0), h.solid_volume())
    h.task_button("OK")


def after_ok():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("40 x 30 x 10", near(h.solid_volume(), 12000.0) and box() == (0.0, 10.0), box())
    h.fit()


def edit_again():
    h.check(
        "double-click Extrude 1 in the timeline",
        ui.double_click_timeline("Extrude 1"),
        ui.timeline_titles(),
    )


def edit_symmetric():
    p = panel()
    h.check("editing", p is not None and p.editing and not p._closed)
    if p is None or not p.editing:
        return
    h.check(
        "operation still the first body's",
        p.operation.currentText() == "New Body",
        p.operation.currentText(),
    )
    ui.choose(p.direction, "Symmetric")


def edit_ok():
    # Whole Length was chosen in the first dialog: the edit remembers it (Fusion does).
    h.check("edit remembers Whole Length", panel().measurement.currentText() == "Whole Length")
    h.check("edit preview symmetric whole 10: z -5 to 5", box() == (-5.0, 5.0), box())
    h.task_button("OK")


def after_edit():
    h.check(
        "edit kept: 40 x 30 x 10 centred",
        near(h.solid_volume(), 12000.0) and box() == (-5.0, 5.0),
        box(),
    )
    s["volume"] = h.solid_volume()
    h.fit()


def esc_case():
    h.press("e")


def esc_pick():
    h.fit()
    top = h.body().Shape.BoundBox.ZMax
    h.click(V(30, 25, top))


def esc_now():
    p = panel()
    h.check("a face extrude started", p.target is not None, p.message.text())
    h.check("preview changes the part", not near(h.solid_volume(), s["volume"]))
    h.press(QtCore.Qt.Key_Escape)


def after_esc():
    h.check("Esc closes the dialog", not Gui.Control.activeDialog())
    h.check("Esc leaves the part as it was", near(h.solid_volume(), s["volume"]), h.solid_volume())
    h.shot("4-end")


h.run(
    "extrude_options",
    [
        new_design,
        create_sketch,
        pick_xy,
        draw,
        finish_sketch,
        extrude_it,
        started,
        offset_shown,
        offset_5,
        back_to_plane,
        symmetric_half,
        symmetric_whole,
        two_sides,
        two_sides_4,
        two_sides_taper,
        one_side_again,
        drag_taper,
        taper_dragged,
        ok_options,
        after_ok,
        edit_again,
        edit_symmetric,
        edit_ok,
        after_edit,
        esc_case,
        esc_pick,
        esc_now,
        after_esc,
    ],
)
