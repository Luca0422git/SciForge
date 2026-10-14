# SPDX-License-Identifier: LGPL-2.1-or-later
"""Chamfer sets: two rows in one Chamfer step, each with its own type and sizes (Fusion's "+"
in the selection box). Set 1: Equal Distance 1 on the front top edge; set 2: Distance and
Angle, 2 mm at 30 degrees, Flip, on the back top edge (measured: Flip moves the 2 mm to the
other face). Corner Type Miter / Blend shown greyed with the reason. OK, Ctrl+Z / Ctrl+Y,
edit from the timeline (set 1 to Two Distances), Cancel. Only real input.

A chamfer with legs a and b along a 40 mm edge removes 40 a b / 2; Distance and Angle on a
90 degree edge has legs d and d tan(angle)."""

import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import fillet2_steps as f2
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}
FRONT_TOP = V(20, 0, 10)
BACK_TOP = V(20, 30, 10)
T30 = math.tan(math.radians(30))


def legs(*pairs):
    return b.BOX - sum(40 * a * c / 2.0 for a, c in pairs)


def top_span():
    """(where the top face starts in y, where it ends): the chamfers' cuts into it."""
    shape = h.body().Shape
    top = [
        f
        for f in shape.Faces
        if type(f.Surface).__name__ == "Plane"
        and abs(f.BoundBox.ZMin - 10) < 1e-6
        and abs(f.BoundBox.ZMax - 10) < 1e-6
    ]
    if len(top) != 1:
        return None
    return round(top[0].BoundBox.YMin, 4), round(top[0].BoundBox.YMax, 4)


def start():
    Gui.Selection.clearSelection()
    h.fit()
    h.ribbon("Chamfer")


def pick_first():
    p = b.blend_panel()
    h.check("Chamfer dialog with one set", p is not None and p.rows.count() == 1)
    if p:
        disabled = [
            p.corner.itemText(i)
            for i in range(p.corner.count())
            if not p.corner.model().item(i).isEnabled()
        ]
        h.check("Corner Type: Miter and Blend greyed", disabled == ["Miter", "Blend"], disabled)
    h.click_edge(FRONT_TOP)


def plus():
    v = h.solid_volume()
    h.check("set 1: equal distance 1", b.close(v, legs((1, 1))), v)
    f2.press_plus(b.blend_panel())


def pick_second():
    p = b.blend_panel()
    h.check("set 2 current", p is not None and p.active == 1 and p.rows.count() == 2)
    h.click_edge(BACK_TOP)


def angle_type():
    p = b.blend_panel()
    h.check("set 2 has the back edge", p is not None and len(p.refs) == 1, p and p.refs)
    if p:
        b.choose(p.ctype, "Distance and Angle")


def distance():
    p = b.blend_panel()
    if p:
        b.type_into(p.distance.widget, "2")


def angle():
    p = b.blend_panel()
    if p:
        b.type_into(p.angle.widget, "30")


def no_flip():
    p = b.blend_panel()
    v = h.solid_volume()
    h.check("set 2: 2 mm at 30 degrees", b.close(v, legs((1, 1), (2, 2 * T30))), v)
    span = top_span()
    s["span"] = span
    h.check("set 1 cuts 1 mm into the top", span and abs(span[0] - 1) < 1e-4, span)
    h.check("two sets: SciForge's chamfer step", p is not None and f2.is_sets(p.target))
    h.check("an arrow per set", p is not None and len(p.arrows) == 2, p and len(p.arrows))
    if p:
        b.click_widget(p.flip)


def flipped():
    p = b.blend_panel()
    v = h.solid_volume()
    h.check("Flip keeps the volume", b.close(v, legs((1, 1), (2, 2 * T30))), v)
    span = top_span()
    before = s["span"]
    h.check(
        "Flip moves the 2 mm onto the other face",
        span
        and before
        and {round(30 - span[1], 3), round(30 - before[1], 3)} == {2.0, round(2 * T30, 3)},
        (before, span),
    )
    h.check("set 1 untouched by set 2's Flip", span and abs(span[0] - 1) < 1e-4, span)
    s["span2"] = span
    h.shot("1-chamfer-sets")
    h.task_button("OK")


def after_ok():
    v = h.solid_volume()
    h.check("kept", b.close(v, legs((1, 1), (2, 2 * T30))), v)
    steps = f2.steps()
    h.check("one Chamfer step", len(steps) == 1 and f2.is_sets(steps[0]), steps)
    h.check("timeline: Chamfer 1", "Chamfer 1" in b.timeline_titles(), b.timeline_titles())
    s["v"] = v
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def undone():
    h.check("Ctrl+Z", b.close(h.solid_volume(), b.BOX) and not f2.steps())
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def redone():
    h.check("Ctrl+Y", b.close(h.solid_volume(), s["v"]))
    h.fit()
    b.timeline_double_click("Chamfer 1", click_first=True)


def edit_open():
    p = b.blend_panel()
    h.check("editing the chamfer", p is not None and not p.created and p.rows.count() == 2)
    if p is None:
        return
    h.check(
        "set 1 shows Equal Distance (the current row)",
        p.active == 0 and p.ctype.currentText() == "Equal Distance",
        (p.active, p.ctype.currentText()),
    )
    f2.click_row(p, 1)


def edit_second():
    p = b.blend_panel()
    if p is None:
        return
    h.check(
        "set 2's row shows its own type, sizes and Flip",
        p.ctype.currentText() == "Distance and Angle"
        and abs(p.distance.value() - 2) < 1e-9
        and abs(p.angle.value() - 30) < 1e-9
        and p.flip.isChecked(),
        (p.ctype.currentText(), p.distance.value(), p.angle.value(), p.flip.isChecked()),
    )
    f2.click_row(p, 0)


def edit_first():
    p = b.blend_panel()
    if p:
        b.choose(p.ctype, "Two Distances")


def edit_first_size():
    p = b.blend_panel()
    if p:
        b.type_into(p.distance2.widget, "3")


def edit_ok():
    h.task_button("OK")


def edited():
    v = h.solid_volume()
    h.check("set 1 is now 1 / 3", b.close(v, legs((1, 3), (2, 2 * T30))), v)
    h.check("set 2 unchanged", top_span() and abs(top_span()[1] - s["span2"][1]) < 1e-4)
    s["v"] = v


def cancel_start():
    b.timeline_double_click("Chamfer 1", click_first=True)


def cancel_change():
    p = b.blend_panel()
    if p:
        b.type_into(p.distance.widget, "4")


def cancel():
    h.task_button("Cancel")


def end():
    h.check("Cancel keeps it", b.close(h.solid_volume(), s["v"]))
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("no kernel errors", not f2.report_errors(), f2.report_errors())
    h.shot("2-end")


h.run(
    "fillet2_chamfer",
    b.box_steps("ChamferSets")
    + [
        start,
        pick_first,
        plus,
        pick_second,
        angle_type,
        distance,
        angle,
        no_flip,
        flipped,
        after_ok,
        undone,
        redone,
        edit_open,
        edit_second,
        edit_first,
        edit_first_size,
        edit_ok,
        edited,
        cancel_start,
        cancel_change,
        cancel,
        end,
    ],
)
