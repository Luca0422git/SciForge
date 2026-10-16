# SPDX-License-Identifier: LGPL-2.1-or-later
"""Gear like a Fusion user, only real input: the main use, the timeline edit, Undo / Redo,
Cancel and Esc.

New design, nothing selected, SOLID > CREATE > Gear: click the XY square; the gear's
outline follows the mouse; click the centre on the origin. First values (Fusion's sample
fields): Spur, Metric, 20 deg, module 2, 24 teeth, backlash 0, root fillet 0.5, thickness
10, hole 10, Pitch Diameter 48 read-only, New Body. Type 30 teeth: the preview redraws
(Pitch Diameter 60). Drag the thickness arrow, type 12 in its box. OK: one timeline step
"Gear 1" with no sketch of its own. Undo / Redo with the application bar's buttons.
Double-click Gear 1: the dialog shows it as left; Pressure Angle 25, Hole Diameter 0,
OK. Then Cancel and Esc on a second gear change nothing.

Expected volumes come from gear_core.area() (Green's theorem on the exact outline the
profile is made of; FreeCAD's Pad agrees to 1e-11, see the golden models) x thickness.
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import primitive_input as pi

V = App.Vector
s = {}


def area(**options):
    from sciforge import gear_core

    return gear_core.area(options)


def near(a, b, tol=1e-6):
    return pi.near(a, b, tol)


def vol():
    return pi.total_volume()


def panel():
    return pi.panel("GearPanel")


def gears():
    return [o for o in App.ActiveDocument.Objects if getattr(o, "SciForgeType", "") == "Gear"]


# -- the first gear -------------------------------------------------------------------------------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Gears")
    h.fit()


def gear_start():
    h.check("nothing selected", not Gui.Selection.getSelectionEx())
    h.check("Gear in SOLID > CREATE", pi.menu("Gear") is not False)


def gear_waits():
    p = panel()
    h.check("Gear dialog open, waiting for a plane", p is not None and p.state == "plane")
    if p is None:
        return
    h.check("no pop-up", not h.popups(), h.popups())
    h.check(
        "types",
        [p.type.itemText(i) for i in range(p.type.count())] == ["Spur", "Internal", "Rack"],
    )
    h.check(
        "standards",
        [p.standard.itemText(i) for i in range(p.standard.count())] == ["Metric", "English"],
    )
    h.check(
        "Fusion's pressure angles",
        [p.angle.itemText(i) for i in range(p.angle.count())] == ["14.5 deg", "20 deg", "25 deg"],
    )
    ops = [p.operation.itemText(i) for i in range(p.operation.count())]
    h.check("operations (no Intersect)", ops == ["Join", "Cut", "New Body", "New Component"], ops)
    h.check("Pitch Diameter is read-only", p.pitch_value.isReadOnly())


def gear_xy():
    h.click(V(15, -15, 0))


def gear_hover():
    p = panel()
    h.check("placing", p is not None and p.state == "place", p and p.state)
    pi.hover(V(20, 10, 0))


def gear_outline():
    p = panel()
    if p is None or p.placer is None:
        h.check("placing tool", False)
        return
    count = p.placer.coords.point.getNum()
    h.check("the gear's outline follows the mouse", count > 24 * 10, count)
    h.check("still no gear", p.target is None)
    h.click(V(0, 0, 0))


gear_outline.wait_ms = 800


def gear_first():
    p = panel()
    if p is None:
        h.check("Gear dialog still open", False)
        return
    values = (
        p.type.currentText(),
        p.standard.currentText(),
        p.angle.currentText(),
        p.module.value(),
        p.teeth.value(),
        p.backlash.value(),
        p.fillet.value(),
        p.thickness.value(),
        p.hole.value(),
    )
    h.check(
        "first values",
        values == ("Spur", "Metric", "20 deg", 2.0, 24.0, 0.0, 0.5, 10.0, 10.0),
        values,
    )
    h.check("Pitch Diameter 48", p.pitch_value.text().startswith("48"), p.pitch_value.text())
    h.check("New Body", p.operation.currentText() == "New Body")
    h.check("preview", near(vol(), area() * 10.0), (vol(), area() * 10.0))
    h.check("one gear step, no sketch", len(gears()) == 1 and not pi.steps_of("Sketcher"))
    h.check("thickness arrow", set(p.handles) == {"thickness"}, list(p.handles))
    h.check("hole and pitch diameter shown", p.hole.widget.isVisible())
    h.check("rim and rack fields hidden", not p.rim.widget.isVisible())
    h.check("module shown, diametral pitch hidden", not p.dp.widget.isVisible())
    h.fit()
    h.shot("1-gear-24")
    s["first"] = vol()
    ui.type_into(p.teeth.widget, "30")


gear_first.wait_ms = 2000


def thirty_teeth():
    p = panel()
    h.check("30 teeth: the preview redraws", near(vol(), area(teeth=30) * 10.0), vol())
    h.check("bigger than before", vol() > s["first"] * 1.3, (vol(), s["first"]))
    h.check("Pitch Diameter 60", p.pitch_value.text().startswith("60"), p.pitch_value.text())
    h.fit()
    h.shot("2-gear-30")


thirty_teeth.wait_ms = 2000


def drag_thickness():
    p = panel()
    handle = p.handles.get("thickness")
    h.check("thickness handle", handle is not None, list(p.handles))
    if handle is not None:
        pi.drag_handle(handle, 16.0)


drag_thickness.wait_ms = 2500


def dragged():
    p = panel()
    t = p.thickness.value()
    h.check("dragging changed the thickness", 12.0 < t < 22.0, t)
    h.check("the gear follows", near(vol(), area(teeth=30) * t, 1e-4), (vol(), t))
    box = p.value_boxes
    h.check("a value box beside the arrow", box is not None)
    ui.type_into(p.thickness.widget, "12")


dragged.wait_ms = 2000


def gear_ok():
    h.check("12 thick", near(vol(), area(teeth=30) * 12.0), vol())
    h.task_button("OK")


gear_ok.wait_ms = 2000


def gear_kept():
    h.check("dialog closed", pi.no_dialog())
    h.check("kept", near(vol(), area(teeth=30) * 12.0), vol())
    h.check("Gear 1 in the timeline", "Gear 1" in ui.timeline_titles(), ui.timeline_titles())
    h.check(
        "its profile is hidden and no step",
        all(
            not o.ViewObject.Visibility
            for o in App.ActiveDocument.Objects
            if getattr(o, "SciForgeRole", "") == "GearProfile"
        )
        and not any("profile" in t.lower() for t in ui.timeline_titles()),
        ui.timeline_titles(),
    )
    h.check("Undo button", ui.quick_access("Undo"))


def gear_undone():
    h.check("Undo removes it", vol() == 0.0, vol())
    h.check("Redo button", ui.quick_access("Redo"))


gear_undone.wait_ms = 1500


def gear_redone():
    h.check("Redo brings it back", near(vol(), area(teeth=30) * 12.0), vol())
    h.fit()
    h.check("double-click Gear 1", ui.double_click_timeline("Gear 1"), ui.timeline_titles())


gear_redone.wait_ms = 1500


def gear_editing():
    p = panel()
    h.check("editing the gear", p is not None and p.editing)
    if p is None:
        return
    shown = (p.teeth.value(), p.thickness.value(), p.angle.currentText(), p.hole.value())
    h.check("edit shows it as left", shown == (30.0, 12.0, "20 deg", 10.0), shown)
    h.check("Pressure Angle 25", ui.choose(p.angle, "25 deg"))


def edit_angle():
    p = panel()
    h.check("25 deg", near(vol(), area(teeth=30, pressure_angle=25) * 12.0), vol())
    ui.type_into(p.hole.widget, "0")


edit_angle.wait_ms = 2000


def edit_hole():
    expected = area(teeth=30, pressure_angle=25, hole=0) * 12.0
    h.check("no hole", near(vol(), expected), (vol(), expected))
    h.task_button("OK")


edit_hole.wait_ms = 2000


def gear_edited():
    expected = area(teeth=30, pressure_angle=25, hole=0) * 12.0
    h.check("edit kept", near(vol(), expected), vol())
    h.check("still one gear", len(gears()) == 1)
    h.check("still Gear 1", "Gear 1" in ui.timeline_titles(), ui.timeline_titles())
    s["volume"] = vol()
    s["count"] = len(App.ActiveDocument.Objects)
    h.fit()
    h.shot("3-edited")


# -- Cancel and Esc -------------------------------------------------------------------------------
def cancel_start():
    h.click_empty()
    pi.menu("Gear")


def cancel_plane():
    h.click(V(34, -34, 0))  # a corner of the XY square the parts leave free


def cancel_centre():
    h.click(V(80, 0, 0))


cancel_centre.wait_ms = 2000


def cancel_now():
    p = panel()
    h.check("a second gear's preview", p is not None and p.target is not None)
    h.check("a second body", len(pi.bodies()) == 2, len(pi.bodies()))
    h.task_button("Cancel")


cancel_now.wait_ms = 1500


def cancelled():
    h.check("Cancel closes", pi.no_dialog())
    h.check("Cancel changes nothing", near(vol(), s["volume"]), vol())
    h.check("no new objects", len(App.ActiveDocument.Objects) == s["count"])
    pi.menu("Gear")


def esc_now():
    h.check("Gear dialog open", panel() is not None)
    h.press(QtCore.Qt.Key_Escape)


def after_esc():
    h.check("Esc closes", pi.no_dialog())
    h.check("Esc changes nothing", near(vol(), s["volume"]), vol())
    h.check("no new objects", len(App.ActiveDocument.Objects) == s["count"])
    h.shot("4-end")


h.run(
    "gear_spur",
    [
        new_design,
        gear_start,
        gear_waits,
        gear_xy,
        gear_hover,
        gear_outline,
        gear_first,
        thirty_teeth,
        drag_thickness,
        dragged,
        gear_ok,
        gear_kept,
        gear_undone,
        gear_redone,
        gear_editing,
        edit_angle,
        edit_hole,
        gear_edited,
        cancel_start,
        cancel_plane,
        cancel_centre,
        cancel_now,
        cancelled,
        esc_now,
        after_esc,
    ],
)
