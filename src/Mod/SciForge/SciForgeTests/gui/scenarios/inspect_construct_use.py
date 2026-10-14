# SPDX-License-Identifier: LGPL-2.1-or-later
"""Construction geometry used by other commands, like in Fusion, only real input.

Part: box 40 x 30 x 10 from the origin (real input).
  1. A circle r3 sketched on the right face (x = 40) at y = 15, z = 5.
  2. Offset Plane on the right face, 10: Plane1 at x = 50.
  3. Extrude the circle with Extent "To Object", clicking Plane1: a boss from x = 40 to
     x = 50: + 9 pi * 10 = 90 pi.
  4. Axis Through Two Planes: Plane1 and the origin's XY square: Axis1 along Y at
     x = 50, z = 0.
  5. A 3 x 10 rectangle sketched on XY (x 55..58, y 0..10), revolved a full turn about
     Axis1 (clicked in the 3D view): a ring with radii 5 and 8, 10 long:
     pi (64 - 25) * 10 = 390 pi. It does not touch the box (x >= 42), so the Join makes it a
     body of its own (Fusion: a Join that touches nothing is a New Body).
  6. Plane1 edited from the timeline to 20 (x = 60): the boss now ends at x = 60 (180 pi)
     and Axis1 moves with the plane, so the ring has radii 2 and 5: pi (25 - 4) * 10 =
     210 pi. Undo / redo.

Hand-derived volumes: 12000 + 90 pi; 12000 + 480 pi; after the edit 12000 + 390 pi."""
import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import inspect_steps as s

V = App.Vector
PI = math.pi
BOX = 12000.0
st = {}


def obj(key):
    name = st.get(key)
    return App.ActiveDocument.getObject(name) if name else None


def extrude_panel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return p if p is not None and Gui.Control.activeDialog() else None


def revolve_panel():
    from sciforge import revolve_ui

    p = revolve_ui.RevolvePanel.last
    return p if p is not None and not p._closed else None


def on_line(datum, point, direction, tol=1e-6):
    if datum is None:
        return False
    gp = datum.getGlobalPlacement()
    d = gp.Rotation.multVec(V(0, 0, 1))
    if d.cross(V(direction).normalize()).Length > 1e-6:
        return False
    return (gp.Base - V(point)).cross(d).Length < tol


def plane_x(datum):
    return datum.getGlobalPlacement().Base.x if datum is not None else None


def total():
    """Every shown body together: the ring touches nothing, so it is a body of its own."""
    found = 0.0
    for body in App.ActiveDocument.findObjects("PartDesign::Body"):
        if body.ViewObject.Visibility and not body.Shape.isNull():
            found += body.Shape.Volume
    return found


# -- 1. the circle on the right face -------------------------------------------------------
def sketch_right():
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def click_right_face():
    h.click(V(40, 15, 5))


def draw_circle():
    sk = h.in_sketch()
    h.check("sketch open on the right face", sk is not None)
    if sk:
        x, y = h.to_sketch(sk, V(40, 15, 5))
        h.draw_circle(sk, x, y, 3)
        st["circle"] = sk.Name


def finish_circle():
    h.ribbon("Finish Sketch")


# -- 2. Offset Plane on the right face ------------------------------------------------------
def offset_start():
    h.click_empty()
    h.ribbon("Offset Plane")


def offset_click():
    h.fit()
    h.click(V(40, 4, 8))


def offset_preview():
    p = s.construct_panel()
    h.check("Offset Plane previews a plane", p is not None and p.datum is not None)
    if p is None or p.datum is None:
        return
    h.check("10 to the right of the face: x = 50", s.close(plane_x(p.datum), 50.0), p.datum)
    h.check("normal along X", abs(s.normal_of(p.datum).x) > 1 - 1e-9, s.normal_of(p.datum))
    h.task_button("OK")


def plane_made():
    planes = s.datums("PartDesign::Plane")
    h.check("Plane1 made", len(planes) == 1 and planes[0].Label == "Plane1", planes)
    if planes:
        st["plane"] = planes[0].Name
    h.check("part unchanged", s.close(h.solid_volume(), BOX), h.solid_volume())


# -- 3. Extrude To Object: Plane1 --------------------------------------------------------------
def extrude_start():
    h.click_empty()
    h.fit()
    h.press("e")


def to_object():
    p = extrude_panel()
    h.check("Extrude open", p is not None)
    if p is None:
        return
    h.check("the circle is taken by itself", len(p.profiles) == 1, p.message.text())
    h.check("choose Extent: To Object", ui.choose(p.extent, "To Object"))
    h.check("the Object box takes the next click", p.active == "extent_object", p.active)


def click_plane1():
    h.fit()
    h.click(V(50, 25, 8))


def boss_to_plane():
    p = extrude_panel()
    if p is None:
        return
    target = p.options.get("extent_object")
    h.check(
        "To Object is Plane1",
        target is not None and target[0] is obj("plane"),
        (target, p.message.text()),
    )
    h.check(
        "the boss stops at Plane1: + 90 pi",
        s.close(h.solid_volume(), BOX + 90 * PI),
        (h.solid_volume(), p.message.text()),
    )
    h.check("no error shown", p.message.text() == "", p.message.text())
    h.shot("1-extrude-to-plane")
    h.task_button("OK")


def boss_made():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("boss kept", s.close(h.solid_volume(), BOX + 90 * PI), h.solid_volume())
    s.no_popups("Extrude To Object")


# -- 4. Axis Through Two Planes ------------------------------------------------------------
def axis_start():
    h.click_empty()
    s.menu("CONSTRUCT", "Axis Through Two Planes")


def axis_click_plane1():
    h.fit()
    h.click(V(50, 25, 8))


def axis_click_xy():
    p = s.construct_panel()
    h.check(
        "Plane1 taken first",
        p is not None and "Plane1" in s.box_value(p, 0),
        p and s.box_value(p, 0),
    )
    h.click(V(20, -10, 0))


def axis_preview():
    p = s.construct_panel()
    d = p.datum if p is not None else None
    h.check("axis where Plane1 meets XY: along Y at x = 50", on_line(d, V(50, 0, 0), V(0, 1, 0)))
    h.task_button("OK")


def axis_made():
    lines = s.datums("PartDesign::Line")
    h.check("Axis1 made", len(lines) == 1 and lines[0].Label == "Axis1", lines)
    if lines:
        st["axis"] = lines[0].Name


# -- 5. Revolve about Axis1 ---------------------------------------------------------------------
def ring_sketch():
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def ring_pick_xy():
    h.click(V(12, -8, 0))


def ring_draw():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None)
    if sk:
        h.check("the sketch lies on XY", s.close(sk.getGlobalPlacement().Base.z, 0.0))
        h.draw_rectangle(sk, 55, 0, 58, 10)
        st["ring"] = sk.Name


def ring_finish():
    h.ribbon("Finish Sketch")


def hide_plane1():
    """Axis1 lies in Plane1: hide the plane so the click takes the axis (eye in the browser)."""
    h.click_empty()
    s.eye("Plane1")


def revolve_start():
    h.check("Plane1 hidden", not obj("plane").ViewObject.Visibility)
    h.fit()
    h.ribbon("Revolve")


def revolve_axis_click():
    p = revolve_panel()
    h.check("Revolve open", p is not None)
    if p is None:
        return
    h.check("the rectangle is taken by itself", len(p.profiles) == 1, p.profiles)
    h.click(V(50, 25, 0))


def ring_made_preview():
    p = revolve_panel()
    if p is None:
        return
    h.check(
        "Axis1 is the axis",
        p.axis is not None and p.axis[0] is obj("axis"),
        (p.axis, p.message.text()),
    )
    h.check(
        "a full turn about Axis1: + 390 pi (a body of its own: it touches nothing)",
        s.close(total(), BOX + 480 * PI),
        (total(), p.message.text()),
    )
    h.check("no error shown", p.message.text() == "", p.message.text())
    h.shot("2-revolve-about-axis1")
    h.task_button("OK")


def ring_kept():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("ring kept", s.close(total(), BOX + 480 * PI), total())
    s.no_popups("Revolve about Axis1")


# -- 6. editing Plane1 moves everything built on it ---------------------------------------------
def edit_plane1():
    h.click_empty()
    s.double_click_timeline(obj("plane"))


def edit_20():
    p = s.construct_panel()
    h.check("Offset Plane opens for Plane1", p is not None and p.editing)
    if p is None:
        return
    h.check("with 10", s.close(p.distance.value(), 10.0), p.distance.value())
    s.type_into(p.distance.widget, "20")


def edit_ok():
    h.task_button("OK")


def followed():
    plane = obj("plane")
    h.check("Plane1 at x = 60", s.close(plane_x(plane), 60.0), plane and plane.Placement)
    h.check(
        "Axis1 moved with it: x = 60",
        on_line(obj("axis"), V(60, 0, 0), V(0, 1, 0)),
        obj("axis") and obj("axis").Placement,
    )
    h.check(
        "boss to x = 60 (180 pi), ring radii 2 and 5 (210 pi)",
        s.close(total(), BOX + 390 * PI),
        total(),
    )
    bad = [o.Label for o in App.ActiveDocument.Objects if "Invalid" in o.State]
    h.check("nothing broken", not bad, bad)
    h.shot("3-plane1-moved")


def undo_edit():
    s.undo()


def edit_undone():
    h.check("Undo: Plane1 at x = 50", s.close(plane_x(obj("plane")), 50.0))
    h.check("Undo: volumes back", s.close(total(), BOX + 480 * PI), total())
    s.redo()


def edit_redone():
    h.check("Redo: Plane1 at x = 60", s.close(plane_x(obj("plane")), 60.0))
    h.check("Redo: volumes again", s.close(total(), BOX + 390 * PI), total())


def the_end():
    s.no_popups("the end")
    h.shot("4-end")


h.run(
    "inspect_construct_use",
    b.box_steps("InspectConstructUse")
    + [
        sketch_right,
        click_right_face,
        draw_circle,
        finish_circle,
        offset_start,
        offset_click,
        offset_preview,
        plane_made,
        extrude_start,
        to_object,
        click_plane1,
        boss_to_plane,
        boss_made,
        axis_start,
        axis_click_plane1,
        axis_click_xy,
        axis_preview,
        axis_made,
        ring_sketch,
        ring_pick_xy,
        ring_draw,
        ring_finish,
        hide_plane1,
        revolve_start,
        revolve_axis_click,
        ring_made_preview,
        ring_kept,
        edit_plane1,
        edit_20,
        edit_ok,
        followed,
        undo_edit,
        edit_undone,
        edit_redone,
        the_end,
    ],
)
