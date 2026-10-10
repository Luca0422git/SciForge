# SPDX-License-Identifier: LGPL-2.1-or-later
"""Revolve: editing, several profiles, changing the axis, only real input.

1. A part from an older file: a revolve made by FreeCAD's own command (ring section
   x 10..20, z 0..5 on XZ, about the sketch's vertical axis, 90 degrees). Double-click it
   in the timeline: SciForge's Revolve dialog shows it (not FreeCAD's). Two Sides (90 and
   90), drag the side-two arrow round to about 150, OK. Edit again, type 10, Esc: nothing
   changes.
2. A sketch on XZ with a 20 x 20 square (x 30..50, z 0..20) and a circle r5 inside it
   (centre x 40, z 10): two profiles, so Revolve waits for clicks. Click the ring, then
   the disc, then the Z axis: the whole square turns round Z. Click the disc again: it is
   dropped (the hole turns into a torus-shaped hollow). Clear the axis with its x: the
   preview goes. Click the X axis: the ring turns round X. New Body, OK. Undo / redo.

Hand-derived (Pappus): ring section 1500 pi * angle / 360. Square about Z:
pi (50^2 - 30^2) 20 = 32000 pi; minus the disc's torus (R 40, r 5): 2 pi^2 40 25 =
2000 pi^2. Ring about X: area (400 - 25 pi), centroid 10 from X: 2 pi 10 (400 - 25 pi).
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
RING = 1500.0 * PI
s = {}


def near(a, b, tol=1e-6):
    return ri.near(a, b, tol)


def bodies():
    return [o for o in App.ActiveDocument.Objects if o.TypeId == "PartDesign::Body"]


def first_body():
    return s["body"]


# -- 1. a FreeCAD-made revolve ------------------------------------------------------------------
def old_file():
    """The part as an older file has it (made before SciForge had its Revolve dialog)."""
    import Part

    Gui.activateWorkbench("SciForgeWorkbench")
    doc = App.newDocument("RevolveEdit")
    body = doc.addObject("PartDesign::Body", "Body")
    Gui.ActiveDocument.ActiveView.setActiveObject("pdbody", body)
    xz = [f for f in body.Origin.OriginFeatures if f.Role == "XZ_Plane"][0]
    sk = body.newObject("Sketcher::SketchObject", "Sketch")
    sk.AttachmentSupport = [(xz, "")]
    sk.MapMode = "FlatFace"
    pts = [V(10, 0, 0), V(20, 0, 0), V(20, 5, 0), V(10, 5, 0)]
    for i in range(4):
        sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))
    rev = body.newObject("PartDesign::Revolution", "Revolution")
    rev.Profile = sk
    rev.ReferenceAxis = (sk, ["V_Axis"])
    rev.Angle = 90
    doc.recompute()
    sk.ViewObject.Visibility = False
    s["body"] = body
    s["rev"] = rev
    h.fit()


def edit_old():
    h.check("90 degrees of the ring", near(first_body().Shape.Volume, RING / 4))
    h.check(
        "double-click it in the timeline",
        ui.double_click_timeline("Revolve 1"),
        ui.timeline_titles(),
    )


def old_in_dialog():
    p = ri.panel()
    h.check("SciForge's Revolve dialog opened", p is not None and p.editing)
    h.check("no FreeCAD pop-up", not h.popups(), h.popups())
    if p is None:
        return
    h.check("angle 90", near(p.angle.value(), 90.0), p.angle.value())
    h.check("the sketch's vertical axis", p.fields["axis"].button.text() == "V axis of Sketch")
    h.check("one profile", len(p.profiles) == 1, p.profiles)
    h.check("Join (not New Body: editing keeps it)", p.operation.currentText() == "Join")
    h.check("the sketch is shown while editing", s["rev"].Profile[0].ViewObject.Visibility)
    h.check("choose Two Sides", ui.choose(p.direction, "Two Sides"))


def two_sides():
    p = ri.panel()
    h.check("side two 90 by default", near(p.angle2.value(), 90.0), p.angle2.value())
    h.check("90 + 90: half the ring", near(first_body().Shape.Volume, RING / 2))
    h.fit()


def drag_side_two():
    p = ri.panel()
    handle = p.handles.get("angle2")
    h.check("side-two arrow shown", handle is not None, list(p.handles))
    if handle is not None:
        h.check("it sits at -90 (the other way)", near(handle.angle(), -90.0), handle.angle())
        ri.drag_handle(handle, -150.0)


drag_side_two.wait_ms = 1200


def side_two_dragged():
    p = ri.panel()
    a2 = p.angle2.value()
    h.check("dragging the side-two arrow sets its angle", 130.0 < a2 < 170.0, a2)
    h.check("side one unchanged", near(p.angle.value(), 90.0), p.angle.value())
    want = RING * (90.0 + a2) / 360.0
    h.check(
        "volume follows",
        near(first_body().Shape.Volume, want, 1e-5),
        (first_body().Shape.Volume, want),
    )
    s["a2"] = a2
    h.shot("1-two-sides")
    h.task_button("OK")


def edited_ok():
    h.check("dialog closed", not Gui.Control.activeDialog())
    rev = ri.revolves()
    h.check("still one Revolution", len(rev) == 1 and rev[0].TypeId == "PartDesign::Revolution")
    s["volume"] = first_body().Shape.Volume
    h.check("kept", near(s["volume"], RING * (90.0 + s["a2"]) / 360.0, 1e-5), s["volume"])
    h.check("the sketch is hidden again", not rev[0].Profile[0].ViewObject.Visibility)
    h.check("edit again", ui.double_click_timeline("Revolve 1"), ui.timeline_titles())


def type_10():
    p = ri.panel()
    h.check("editing shows Two Sides", p is not None and p.direction.currentText() == "Two Sides")
    ui.type_into(p.angle.widget, "10")


def esc_edit():
    h.check("the preview changed", not near(first_body().Shape.Volume, s["volume"]))
    h.press(QtCore.Qt.Key_Escape)


def esc_done():
    h.check("Esc closes the dialog", not Gui.Control.activeDialog())
    h.check("Esc keeps the revolve as it was", near(first_body().Shape.Volume, s["volume"]))
    h.check("Esc: the part is shown", ri.shown(first_body()))
    h.check("Esc: the sketch is hidden again", not s["rev"].Profile[0].ViewObject.Visibility)
    h.fit()


# -- 2. two profiles, axis changes ---------------------------------------------------------------
def create_sketch():
    h.click_empty()
    h.ribbon("Create Sketch")


def pick_xz():
    h.fit()
    h.click(V(5, 0, 24))


def draw():
    sk = h.in_sketch()
    h.check("sketch on XZ", sk is not None and sk.AttachmentSupport[0][0].Role == "XZ_Plane")
    if sk:
        h.draw_rectangle(sk, 30, 0, 50, 20)
        h.draw_circle(sk, 40, 10, 5)
        s["sk"] = sk


def finish():
    h.ribbon("Finish Sketch")


def revolve():
    h.fit()
    h.ribbon("Revolve")


def waits():
    p = ri.panel()
    h.check("two profiles: nothing taken by itself", p is not None and not p.profiles)
    h.check("Profile box waits", p is not None and p.active == "profiles")
    h.fit()
    h.click(V(33, 0, 3))  # inside the ring, away from the circle


def ring_picked():
    p = ri.panel()
    h.check("the ring is picked", len(p.profiles) == 1, p.profiles)
    h.check("then the Axis box waits", p.active == "axis")
    h.click(V(40, 0, 10))  # the disc


def disc_picked():
    p = ri.panel()
    h.check("the disc is added", len(p.profiles) == 2, p.profiles)
    h.click(V(0, 0, 32))  # the Z axis, above the part


def square_about_z():
    p = ri.panel()
    h.check("Z axis", p.axis is not None and p.axis[0].Role == "Z_Axis", p.axis)
    h.check("choose New Body", ui.choose(p.operation, "New Body"))


def square_new_body():
    h.check("the first body is still shown", ri.shown(first_body()))
    other = [b for b in bodies() if b is not first_body()]
    h.check(
        "the whole square turned round Z",
        other and near(other[0].Shape.Volume, 32000 * PI),
        other and other[0].Shape.Volume,
    )
    h.fit()
    h.shot("2-two-profiles")
    h.click(V(40, 0, 10))  # the disc again: drop it


def disc_dropped():
    p = ri.panel()
    h.check("the disc is dropped", len(p.profiles) == 1, p.profiles)
    other = [b for b in bodies() if b is not first_body()]
    want = 32000 * PI - 2000 * PI**2
    h.check(
        "the ring alone: a torus-shaped hollow",
        other and near(other[0].Shape.Volume, want),
        other and (other[0].Shape.Volume, want),
    )
    ui.click(p.fields["axis"].clear)


def axis_cleared():
    p = ri.panel()
    h.check("axis cleared", p.axis is None)
    h.check("the preview is gone", len(bodies()) == 1 and not p.target, [b.Label for b in bodies()])
    h.check("Axis box waits", p.active == "axis")
    h.check("the first body is shown", ri.shown(first_body()))
    h.fit()
    h.click(V(62, 0, 0))  # the X axis, past the sketch


def ring_about_x():
    p = ri.panel()
    h.check("X axis", p.axis is not None and p.axis[0].Role == "X_Axis", p.axis)
    h.check("New Body kept (picked by hand)", p.operation.currentText() == "New Body")
    other = [b for b in bodies() if b is not first_body()]
    want = 2 * PI * 10 * (400 - 25 * PI)
    h.check(
        "the ring turned round X",
        other and near(other[0].Shape.Volume, want),
        other and (other[0].Shape.Volume, want),
    )
    h.shot("3-about-x")
    h.task_button("OK")


def done():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("two bodies", len(bodies()) == 2)
    h.check("the first body is unchanged", near(first_body().Shape.Volume, s["volume"]))
    h.check("both bodies shown", all(ri.shown(b) for b in bodies()))
    h.check("Undo button", ui.quick_access("Undo"))


def undone():
    h.check("Undo removes the new body", len(bodies()) == 1, [b.Label for b in bodies()])
    h.check("Redo button", ui.quick_access("Redo"))


def redone():
    h.check("Redo brings it back", len(bodies()) == 2, [b.Label for b in bodies()])
    other = [b for b in bodies() if b is not first_body()]
    h.check(
        "with its ring",
        other and near(other[0].Shape.Volume, 2 * PI * 10 * (400 - 25 * PI)),
    )


h.run(
    "revolve_edit",
    [
        old_file,
        edit_old,
        old_in_dialog,
        two_sides,
        drag_side_two,
        side_two_dragged,
        edited_ok,
        type_10,
        esc_edit,
        esc_done,
        create_sketch,
        pick_xz,
        draw,
        finish,
        revolve,
        waits,
        ring_picked,
        disc_picked,
        square_about_z,
        square_new_body,
        disc_dropped,
        axis_cleared,
        ring_about_x,
        done,
        undone,
        redone,
    ],
)
