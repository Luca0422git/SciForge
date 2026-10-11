# SPDX-License-Identifier: LGPL-2.1-or-later
"""Circular Pattern the way a Fusion user does it, only real input:

1. A disc r 20 x 10 (sketch on XY, circle, E 10, OK) with a through hole r 2 at (14, 0).
2. Circular Pattern from the ribbon with nothing selected: waits. Click the hole's step in
   the timeline, click the Axis box, click the origin Z axis drawn over the view: Full,
   Quantity 3 (holes at 0, 120, 240 degrees).
3. Quantity 6. Type Angle (Total Angle starts at 180): 6 holes from 0 to 180 degrees.
   Total Angle 90, Quantity 3: 0, 45, 90. Drag the blue curved handle to about 120, then
   on round past half a turn to about 200 (holes at 0, 100, 200).
4. Type Symmetric, Quantity 2, Total Angle 60: holes at 0 and +-60. OK (FreeCAD's
   PolarPattern). Ctrl+Z / Ctrl+Y.
5. Double-click in the timeline: Symmetric / 2 / 60 shown; Full, Quantity 4; OK.
6. A new Circular Pattern with the hole step clicked in the timeline first: Objects are
   taken at once and the Axis box waits. The disc's round side face is clicked as the
   axis (its centre line); the preview is checked, then Cancel: nothing changed.
7. Esc in a new dialog changes nothing.

Hand-derived: disc pi 20^2 10; each through hole r 2 removes pi 2^2 10; a hole at angle a
has its centre at (14 cos a, 14 sin a).
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import pattern_steps as ps

V = App.Vector
s = {}
R = 2.0
HOLE = ps.hole(R)
DISC = math.pi * 400.0 * 10.0


def holes_at(*angles):
    return sorted(
        (
            round(14 * math.cos(math.radians(a)), 4) + 0.0,
            round(14 * math.sin(math.radians(a)), 4) + 0.0,
        )
        for a in angles
    )


def centres():
    found = ps.circle_centres(h.body().Shape, R, z=10)
    return sorted((x + 0.0, y + 0.0) for x, y in found)


def same_points(a, b, tol=1e-3):
    return len(a) == len(b) and all(
        abs(p[0] - q[0]) < tol and abs(p[1] - q[1]) < tol for p, q in zip(sorted(a), sorted(b))
    )


def disc(sk):
    h.draw_circle(sk, 0, 0, 20)


def ribbon_pattern():
    Gui.Selection.clearSelection()
    s["v0"] = h.solid_volume()
    ps.menu("Circular Pattern")


def waiting():
    p = ps.panel()
    h.check("Circular Pattern dialog open", p is not None and p.kind == "circular")
    if p is None:
        return
    h.check("nothing picked", p.options["objects"] == [] and p.target is None)
    h.check(
        "Type Full, Quantity 3", p.circular_type.currentText() == "Full" and p.quantity.value() == 3
    )
    h.check("Total Angle hidden for Full", not p.angle_field.widget.isVisible())
    h.check("model unchanged", ps.close(h.solid_volume(), s["v0"]))
    ps.no_popups("Circular Pattern with nothing selected")
    h.shot("1-waiting")


def click_hole_step():
    ps.timeline_click("Extrude 2")


def click_axis_box():
    p = ps.panel()
    h.check("hole picked", p and len(p.options["objects"]) == 1, p and p.options["objects"])
    ps.click_box("axis")


def click_z_axis():
    p = ps.panel()
    h.check("origin axes drawn", p and p.axis_picker is not None)
    h.fit()
    h.click(V(0, 0, 22))


def full_three():
    p = ps.panel()
    axis = p.options["axis"] if p else None
    h.check("the Z axis is the axis", axis is not None and axis[0].Role == "Z_Axis", axis)
    h.check("Axis box shows Z Axis", p and p.fields["axis"].button.text() == "Z Axis")
    v = h.solid_volume()
    h.check("3 holes", ps.close(v, DISC - 3 * HOLE), v)
    h.check("at 0, 120, 240 degrees", same_points(centres(), holes_at(0, 120, 240)), centres())
    h.shot("2-full")


def quantity_6():
    ps.type_quantity(ps.panel().quantity, 6)


def six():
    v = h.solid_volume()
    h.check("6 holes", ps.close(v, DISC - 6 * HOLE), v)
    h.check("every 60 degrees", same_points(centres(), holes_at(0, 60, 120, 180, 240, 300)))


def choose_angle():
    b.choose(ps.panel().circular_type, "Angle")


def angle_180():
    p = ps.panel()
    h.check(
        "Total Angle shown, 180",
        p.angle_field.widget.isVisible() and abs(p.angle_field.value() - 180) < 1e-9,
    )
    h.check(
        "6 holes from 0 to 180",
        same_points(centres(), holes_at(0, 36, 72, 108, 144, 180)),
        centres(),
    )
    h.check("curved handle shown", "angle" in p.handles, list(p.handles))
    ps.type_quantity(p.quantity, 3)


def angle_90():
    ps.type_value(ps.panel().angle_field.widget, "90")


def three_in_90():
    h.check("0, 45, 90", same_points(centres(), holes_at(0, 45, 90)), centres())
    handle = ps.panel().handles.get("angle")
    h.check(
        "handle follows the typed angle",
        handle is not None and abs(handle.angle() - 90) < 1e-3,
        handle and handle.angle(),
    )
    h.shot("3-angle")


def drag_handle():
    p = ps.panel()
    handle = p.handles.get("angle")
    if not h.check("curved handle to drag", handle is not None):
        return
    now, later = handle.screen_points(120.0)
    h.drag(h.screen_point(now), h.screen_point(later), steps=16)


def dragged():
    p = ps.panel()
    angle = p.angle_field.value()
    h.check("dragging the handle opens the angle", 105 < angle < 135, angle)
    h.check(
        "the last hole follows",
        same_points(centres(), holes_at(0, angle / 2.0, angle), tol=0.05),
        (centres(), angle),
    )


def drag_past_half():
    p = ps.panel()
    handle = p.handles.get("angle")
    if not h.check("curved handle still there", handle is not None):
        return
    ps.drag_turn(handle, handle.angle(), 200.0)


def past_half():
    p = ps.panel()
    angle = p.angle_field.value()
    h.check("the handle turns on past 180", 185 < angle < 215, angle)
    h.check(
        "the holes follow past half a turn",
        same_points(centres(), holes_at(0, angle / 2.0, angle), tol=0.05),
        (centres(), angle),
    )
    h.check("no complaint", not p.message.text().startswith("⚠"), p.message.text())
    h.shot("3b-past-half")


def choose_symmetric():
    b.choose(ps.panel().circular_type, "Symmetric")


def symmetric_values():
    p = ps.panel()
    ps.type_quantity(p.quantity, 2)


def symmetric_angle():
    ps.type_value(ps.panel().angle_field.widget, "60")


def symmetric_preview():
    v = h.solid_volume()
    h.check("3 holes: 0 and +-60", ps.close(v, DISC - 3 * HOLE), v)
    h.check("at -60, 0, 60", same_points(centres(), holes_at(-60, 0, 60)), centres())
    h.shot("4-symmetric")
    h.task_button("OK")


def after_ok():
    h.check("dialog closed", not Gui.Control.activeDialog())
    found = ps.patterns("circular")
    h.check(
        "one Circular Pattern (FreeCAD's PolarPattern), the end of the timeline",
        len(found) == 1
        and found[0].TypeId == "PartDesign::PolarPattern"
        and h.body().Tip is found[0],
        found,
    )
    h.check("timeline shows Circular Pattern 1", "Circular Pattern 1" in ps.timeline_titles())
    shape = h.body().Shape
    h.check("valid solid", shape.isValid())
    s["v"] = shape.Volume


def undo():
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def after_undo():
    h.check(
        "Ctrl+Z removes the pattern",
        ps.close(h.solid_volume(), DISC - HOLE) and not ps.patterns(),
        h.solid_volume(),
    )
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def after_redo():
    h.check("Ctrl+Y brings it back", ps.close(h.solid_volume(), s["v"]) and len(ps.patterns()) == 1)
    h.fit()


def edit():
    ps.timeline_double_click("Circular Pattern 1")


def edit_open():
    p = ps.panel()
    h.check("the dialog opens on the pattern", p is not None and p.editing)
    if p is None:
        return
    h.check(
        "Symmetric, 2, 60 shown",
        p.circular_type.currentText() == "Symmetric"
        and p.quantity.value() == 2
        and abs(p.angle_field.value() - 60) < 1e-9,
        (p.circular_type.currentText(), p.quantity.value(), p.angle_field.value()),
    )
    h.check("the axis is shown", p.fields["axis"].button.text() == "Z Axis")
    b.choose(p.circular_type, "Full")


def edit_quantity():
    ps.type_quantity(ps.panel().quantity, 4)


def edit_ok():
    h.check("4 holes every 90", same_points(centres(), holes_at(0, 90, 180, 270)), centres())
    h.task_button("OK")


def after_edit():
    h.check("4 holes", ps.close(h.solid_volume(), DISC - 4 * HOLE), h.solid_volume())
    h.check("still one pattern", len(ps.patterns()) == 1)
    s["v"] = h.solid_volume()


def preselect_step():
    ps.timeline_click("Extrude 2")


def preselected_start():
    sel = ps.selection()
    h.check("the hole step is selected", bool(sel), sel)
    ps.menu("Circular Pattern")


def preselected():
    p = ps.panel()
    if not h.check("dialog open", p is not None):
        return
    h.check("the selected step is the object", len(p.options["objects"]) == 1)
    h.check("the Axis box waits", p.fields["axis"].button.isChecked())


def click_round_face():
    h.fit()
    # The disc's side, facing the camera (front-right of the iso view), half way up.
    h.click(V(20 * math.cos(math.radians(-45)), 20 * math.sin(math.radians(-45)), 5))


def round_face_axis():
    p = ps.panel()
    axis = p.options["axis"] if p else None
    h.check("the round face is the axis", axis is not None and axis[1].startswith("Face"), axis)
    v = h.solid_volume()
    # 3 more holes at 0/120/240 of which the one at 0 is the original: 2 new ones, plus the
    # 4 of the first pattern, two of them at 0 and 180... 0 and 120/240 overlap nothing.
    h.check("a preview is shown", p is not None and p.target is not None)
    h.check("the preview changes the part", not ps.close(v, s["v"]), v)
    h.task_button("Cancel")


def after_cancel():
    h.check("Cancel: unchanged", ps.close(h.solid_volume(), s["v"]) and len(ps.patterns()) == 1)
    h.check("dialog closed", not Gui.Control.activeDialog())


def esc_start():
    ps.menu("Circular Pattern")


def esc():
    h.press(QtCore.Qt.Key_Escape)


def after_esc():
    h.check(
        "Esc: closed, unchanged",
        not Gui.Control.activeDialog() and ps.close(h.solid_volume(), s["v"]),
    )


h.run(
    "patterns_circ",
    b.box_steps("PatternCirc", profile=disc)
    + ps.make_cut("hole", (14, 0), R, click=V(8, 6, 10))
    + [
        ribbon_pattern,
        waiting,
        click_hole_step,
        click_axis_box,
        click_z_axis,
        full_three,
        quantity_6,
        six,
        choose_angle,
        angle_180,
        angle_90,
        three_in_90,
        drag_handle,
        dragged,
        drag_past_half,
        past_half,
        choose_symmetric,
        symmetric_values,
        symmetric_angle,
        symmetric_preview,
        after_ok,
        undo,
        after_undo,
        after_redo,
        edit,
        edit_open,
        edit_quantity,
        edit_ok,
        after_edit,
        preselect_step,
        preselected_start,
        preselected,
        click_round_face,
        round_face_axis,
        after_cancel,
        esc_start,
        esc,
        after_esc,
    ],
)
