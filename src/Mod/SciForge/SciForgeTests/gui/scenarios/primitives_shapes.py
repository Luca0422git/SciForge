# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cylinder, Sphere and Torus like a Fusion user, only real input.

Cylinder with nothing selected: click the XY square, the centre on the origin (it snaps
there), a point at (10, 0): diameter 20, first height 20, New Body. Drag the blue
diameter arrow (the cylinder follows); type Diameter 20 and Height 12; OK. Undo / redo.
Double-click Cylinder 1 in the timeline: Height 15, OK.
A second Cylinder from the selected top face: centre in the middle, a point 3 mm out,
type Height -8: going into the part, Fusion switches to Cut: a hole 6 x 8.
Sphere from the selected top face, centre 6 mm out, Diameter 4: half sticks out, Join;
Intersect keeps the half inside; Cut takes it away; OK. Double-click Sphere 1, Diameter
3, OK. Torus with nothing selected: XY square, centre on the origin, a point at (20, 0):
inner diameter 40, torus diameter 10, away from the part: a New Body. Position Outside;
Inside with Torus Diameter 25 is too thick (said in the dialog, OK refused); back to
10 and Outside, OK. Undo / redo. Cancel and Esc leave the part as it was.

Hand-derived volumes (pi = PI):
  cylinder r10 h20 = 2000 pi, h12 = 1200 pi, h15 = 1500 pi
  hole r3 h8 = 72 pi                  -> 1428 pi
  half sphere r2 = 16 pi / 3          (join adds it, intersect keeps it, cut removes it)
  half sphere r1.5 = 2.25 pi
  torus R25 r5 = 2 pi^2 25 25 = 1250 pi^2; R20 r5 = 1000 pi^2
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import primitive_input as pi

V = App.Vector
PI = math.pi
CUP = 1428.0 * PI
HALF2 = 16.0 * PI / 3.0
HALF15 = 2.25 * PI
s = {}


def near(a, b, tol=1e-6):
    return pi.near(a, b, tol)


def vol():
    return pi.total_volume()


def cyl_panel():
    return pi.panel("CylinderPanel")


def sphere_panel():
    return pi.panel("SpherePanel")


def torus_panel():
    return pi.panel("TorusPanel")


# -- Cylinder, nothing selected ------------------------------------------------------------------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Shapes")
    h.fit()


def cylinder_start():
    h.check("nothing selected", not Gui.Selection.getSelectionEx())
    pi.menu("Cylinder")


def cylinder_waits():
    p = cyl_panel()
    h.check("Cylinder dialog open", p is not None and p.state == "plane")
    if p is None:
        return
    h.check("no pop-up", not h.popups(), h.popups())
    h.check(
        "Fusion's fields",
        p.diameter.widget.isVisible()
        and p.height.widget.isVisible()
        and p.operation.currentText() in ("Join", "New Body"),
    )


def cylinder_xy():
    h.click(V(15, -15, 0))


def cylinder_centre():
    p = cyl_panel()
    h.check("XY picked, placing", p is not None and p.state == "place", p and p.state)
    h.click(V(0, 0, 0))


def cylinder_hover():
    p = cyl_panel()
    h.check("asks for the circle", p is not None and "circle" in p.info.text())
    pi.hover(V(5, 0, 0))


def cylinder_live():
    p = cyl_panel()
    h.check(
        "the diameter follows the mouse", near(p.diameter.value(), 10.0, 1e-3), p.diameter.value()
    )
    h.shot("1-cylinder-circle")
    h.click(V(10, 0, 0))


cylinder_live.wait_ms = 1200


def cylinder_first():
    p = cyl_panel()
    if p is None:
        return
    h.check("diameter 20, height 20", (p.diameter.value(), p.height.value()) == (20.0, 20.0))
    h.check("first solid: New Body", p.operation.currentText() == "New Body")
    h.check("cylinder 2000 pi", near(vol(), 2000.0 * PI), vol())
    h.check("handles", set(p.handles) == {"height", "diameter"}, list(p.handles))
    h.fit()
    h.shot("2-cylinder")


def drag_diameter():
    p = cyl_panel()
    handle = p.handles.get("diameter")
    h.check("diameter handle at 20", handle is not None and near(handle.value(), 20.0), handle)
    if handle is not None:
        pi.drag_handle(handle, 26.0)


drag_diameter.wait_ms = 1200


def diameter_dragged():
    p = cyl_panel()
    d = p.diameter.value()
    h.check("dragging changed the diameter", 23.0 < d < 29.0, d)
    h.check("the cylinder follows", near(vol(), PI * d * d / 4.0 * 20.0, 1e-4), (vol(), d))
    ui.type_into(p.diameter.widget, "20")


def type_height():
    ui.type_into(cyl_panel().height.widget, "12")


def cylinder_ok():
    h.check("1200 pi", near(vol(), 1200.0 * PI), vol())
    h.task_button("OK")


def cylinder_kept():
    h.check("dialog closed", pi.no_dialog())
    h.check("kept", near(vol(), 1200.0 * PI), vol())
    h.check("an AdditiveCylinder", len(pi.steps_of("AdditiveCylinder")) == 1)
    h.check(
        "Cylinder 1 in the timeline", "Cylinder 1" in ui.timeline_titles(), ui.timeline_titles()
    )


def cylinder_undo():
    h.check("Undo button", ui.quick_access("Undo"))


def cylinder_undone():
    h.check("Undo removes it", vol() == 0.0, vol())
    h.check("Redo button", ui.quick_access("Redo"))


def cylinder_redone():
    h.check("Redo brings it back", near(vol(), 1200.0 * PI), vol())
    h.fit()


def cylinder_edit():
    h.check("double-click Cylinder 1", ui.double_click_timeline("Cylinder 1"), ui.timeline_titles())


def cylinder_editing():
    p = cyl_panel()
    h.check("editing", p is not None and p.editing)
    if p is None:
        return
    h.check("shows 20 / 12", (p.diameter.value(), p.height.value()) == (20.0, 12.0))
    ui.type_into(p.height.widget, "15")


def cylinder_edit_ok():
    h.check("1500 pi", near(vol(), 1500.0 * PI), vol())
    h.task_button("OK")


def cylinder_edited():
    h.check("edit kept", near(vol(), 1500.0 * PI), vol())
    h.check("still one cylinder", len(pi.steps_of("AdditiveCylinder")) == 1)
    h.fit()


# -- a second Cylinder from the selected top face: a hole ---------------------------------------------
def select_top():
    h.click(V(0, -5, 15))


def cylinder2_start():
    h.check("top face selected", bool(Gui.Selection.getSelectionEx()), h.state.get("last_click"))
    pi.menu("Cylinder")


def cylinder2_centre():
    p = cyl_panel()
    h.check("the face is taken at once", p is not None and p.state == "place", p and p.state)
    h.click(V(0, 0, 15))


def cylinder2_circle():
    h.click(V(3, 0, 15))


cylinder2_circle.wait_ms = 1200


def cylinder2_built():
    p = cyl_panel()
    if p is None:
        return
    h.check("diameter 6", near(p.diameter.value(), 6.0), p.diameter.value())
    h.check("upwards: Join", p.operation.currentText() == "Join", p.operation.currentText())
    ui.type_into(p.height.widget, "-8")


cylinder2_built.wait_ms = 1200


def cylinder2_cut():
    p = cyl_panel()
    h.check("into the part: Cut by itself", p.operation.currentText() == "Cut")
    h.check("hole 6 x 8", near(vol(), CUP), vol())
    h.shot("3-hole")
    h.task_button("OK")


def cylinder2_kept():
    h.check("kept", near(vol(), CUP), vol())
    h.check("a SubtractiveCylinder", len(pi.steps_of("SubtractiveCylinder")) == 1)
    h.check(
        "Cylinder 2 in the timeline", "Cylinder 2" in ui.timeline_titles(), ui.timeline_titles()
    )
    h.fit()


# -- Sphere from the selected top face -----------------------------------------------------------------
def select_top_2():
    h.click(V(6, 0, 15))


def sphere_start():
    pi.menu("Sphere")


def sphere_centre():
    p = sphere_panel()
    h.check("Sphere: the face is taken at once", p is not None and p.state == "place")
    h.click(V(6, 0, 15))


sphere_centre.wait_ms = 1200


def sphere_built():
    p = sphere_panel()
    if p is None:
        return
    h.check("one click places it", p.state == "ready" and p.target is not None, p.state)
    h.check("a diameter handle", set(p.handles) == {"diameter"}, list(p.handles))
    ui.type_into(p.diameter.widget, "4")


def sphere_join():
    p = sphere_panel()
    h.check(
        "half out of the part: Join", p.operation.currentText() == "Join", p.operation.currentText()
    )
    h.check("adds the upper half", near(vol(), CUP + HALF2), vol())
    h.check("choose Intersect", ui.choose(p.operation, "Intersect"))


def sphere_intersect():
    p = sphere_panel()
    h.check("Intersect keeps the half inside", near(vol(), HALF2), vol())
    h.check(
        "the intersect step",
        p.target is not None and p.target.TypeId == "PartDesign::FeaturePython",
    )
    h.shot("4-intersect")
    h.check("choose Cut", ui.choose(p.operation, "Cut"))


def sphere_cut():
    h.check("Cut takes the half away", near(vol(), CUP - HALF2), vol())
    h.task_button("OK")


def sphere_kept():
    h.check("kept", near(vol(), CUP - HALF2), vol())
    h.check("a SubtractiveSphere", len(pi.steps_of("SubtractiveSphere")) == 1)
    h.check("no intersect step left", not pi.steps_of("FeaturePython"))
    h.check("Sphere 1 in the timeline", "Sphere 1" in ui.timeline_titles(), ui.timeline_titles())


def sphere_edit():
    h.check("double-click Sphere 1", ui.double_click_timeline("Sphere 1"))


def sphere_editing():
    p = sphere_panel()
    h.check("editing the sphere", p is not None and p.editing)
    if p is None:
        return
    h.check("shows Cut, 4", p.operation.currentText() == "Cut" and near(p.diameter.value(), 4.0))
    ui.type_into(p.diameter.widget, "3")


def sphere_edit_ok():
    h.check("diameter 3", near(vol(), CUP - HALF15), vol())
    h.task_button("OK")


def sphere_edited():
    h.check("edit kept", near(vol(), CUP - HALF15), vol())
    s["volume"] = vol()
    h.fit()


# -- Torus, nothing selected: a new body ------------------------------------------------------------------
def torus_start():
    h.click_empty()
    pi.menu("Torus")


def torus_xy():
    p = torus_panel()
    h.check("Torus waits for a plane", p is not None and p.state == "plane")
    h.click(V(12, -12, 0))


def torus_centre():
    p = torus_panel()
    h.check("placing the torus", p is not None and p.state == "place", p and p.state)
    h.click(V(0, 0, 0))


def torus_circle():
    h.click(V(20, 0, 0))


torus_circle.wait_ms = 1500


def torus_built():
    p = torus_panel()
    if p is None:
        return
    h.check(
        "inner 40, torus 10, On Center",
        (p.inner.value(), p.tube.value(), p.position.currentText()) == (40.0, 10.0, "On Center"),
        (p.inner.value(), p.tube.value(), p.position.currentText()),
    )
    h.check("away from the part: New Body", p.operation.currentText() == "New Body")
    h.check("a second body", len(pi.bodies()) == 2, pi.bodies())
    h.check("torus R20 r5", near(vol() - s["volume"], 1000.0 * PI * PI), vol() - s["volume"])
    h.check(
        "Fusion's positions",
        [p.position.itemText(i) for i in range(3)] == ["Inside", "On Center", "Outside"],
    )
    h.fit()
    h.shot("5-torus")
    h.check("choose Outside", ui.choose(p.position, "Outside"))


torus_built.wait_ms = 1500


def torus_outside():
    h.check("torus R25 r5", near(vol() - s["volume"], 1250.0 * PI * PI), vol() - s["volume"])
    h.check("choose Inside", ui.choose(torus_panel().position, "Inside"))


def torus_too_thick():
    ui.type_into(torus_panel().tube.widget, "25")


torus_too_thick.wait_ms = 1200


def torus_refused():
    p = torus_panel()
    h.check("too thick: said in the dialog", "too thick" in p.message.text(), p.message.text())
    h.check("no pop-up", not h.popups(), h.popups())
    h.task_button("OK")


def torus_still_open():
    p = torus_panel()
    h.check("OK refused while it cannot be built", p is not None and not pi.no_dialog())
    if p is None:
        return
    ui.type_into(p.tube.widget, "10")


def torus_fixed():
    p = torus_panel()
    h.check("choose Outside again", ui.choose(p.position, "Outside"))


def torus_ok():
    p = torus_panel()
    h.check("the message is gone", p.message.text() == "", p.message.text())
    h.check("torus R25 r5 again", near(vol() - s["volume"], 1250.0 * PI * PI), vol() - s["volume"])
    h.task_button("OK")


def torus_kept():
    h.check("dialog closed", pi.no_dialog())
    h.check("an AdditiveTorus", len(pi.steps_of("AdditiveTorus")) == 1)
    h.check("Torus 1 in the timeline", "Torus 1" in ui.timeline_titles(), ui.timeline_titles())
    h.check("two bodies", len(pi.bodies()) == 2)
    h.shot("6-torus-ok")
    h.check("Undo button", ui.quick_access("Undo"))


def torus_undone():
    h.check("Undo removes the torus and its body", len(pi.bodies()) == 1, pi.bodies())
    h.check("the part is as before", near(vol(), s["volume"]), vol())
    h.check("Redo button", ui.quick_access("Redo"))


def torus_redone():
    h.check("Redo brings the torus body back", len(pi.bodies()) == 2)
    h.check("torus again", near(vol() - s["volume"], 1250.0 * PI * PI), vol() - s["volume"])
    s["volume"] = vol()
    s["count"] = len(App.ActiveDocument.Objects)
    h.fit()


# -- Cancel and Esc ------------------------------------------------------------------------------------------
def sphere_cancel_start():
    h.click_empty()
    pi.menu("Sphere")


def sphere_cancel_plane():
    p = sphere_panel()
    h.check("Sphere waits for a plane", p is not None and p.state == "plane")
    h.click(V(0, -5, 15))


def sphere_cancel_centre():
    h.click(V(0, -6, 15))


sphere_cancel_centre.wait_ms = 1200


def sphere_cancel():
    p = sphere_panel()
    h.check("a sphere preview", p is not None and p.target is not None)
    h.task_button("Cancel")


def sphere_cancelled():
    h.check("Cancel closes", pi.no_dialog())
    h.check("Cancel changes nothing", near(vol(), s["volume"]), vol())
    h.check("no new objects", len(App.ActiveDocument.Objects) == s["count"])
    pi.menu("Cylinder")


def esc_now():
    h.check("Cylinder dialog open", cyl_panel() is not None)
    h.press(QtCore.Qt.Key_Escape)


def after_esc():
    h.check("Esc closes", pi.no_dialog())
    h.check("Esc changes nothing", near(vol(), s["volume"]), vol())
    h.check("no new objects", len(App.ActiveDocument.Objects) == s["count"])
    h.shot("7-end")


h.run(
    "primitives_shapes",
    [
        new_design,
        cylinder_start,
        cylinder_waits,
        cylinder_xy,
        cylinder_centre,
        cylinder_hover,
        cylinder_live,
        cylinder_first,
        drag_diameter,
        diameter_dragged,
        type_height,
        cylinder_ok,
        cylinder_kept,
        cylinder_undo,
        cylinder_undone,
        cylinder_redone,
        cylinder_edit,
        cylinder_editing,
        cylinder_edit_ok,
        cylinder_edited,
        select_top,
        cylinder2_start,
        cylinder2_centre,
        cylinder2_circle,
        cylinder2_built,
        cylinder2_cut,
        cylinder2_kept,
        select_top_2,
        sphere_start,
        sphere_centre,
        sphere_built,
        sphere_join,
        sphere_intersect,
        sphere_cut,
        sphere_kept,
        sphere_edit,
        sphere_editing,
        sphere_edit_ok,
        sphere_edited,
        torus_start,
        torus_xy,
        torus_centre,
        torus_circle,
        torus_built,
        torus_outside,
        torus_too_thick,
        torus_refused,
        torus_still_open,
        torus_fixed,
        torus_ok,
        torus_kept,
        torus_undone,
        torus_redone,
        sphere_cancel_start,
        sphere_cancel_plane,
        sphere_cancel_centre,
        sphere_cancel,
        sphere_cancelled,
        esc_now,
        after_esc,
    ],
)
