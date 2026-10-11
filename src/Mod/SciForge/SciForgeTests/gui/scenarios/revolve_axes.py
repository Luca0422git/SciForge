# SPDX-License-Identifier: LGPL-2.1-or-later
"""Revolve about every kind of axis, with every operation, only real input.

A 40 x 30 x 10 box (Create Sketch on XY, Extrude, OK).

1. A sketch on XZ: a 20 x 20 square (x 0..20, z 0..20). Revolve: the square is taken by
   itself; click the square's right line (x = 20) as the axis: a cylinder r20 h20 about
   it. Join adds it; Intersect keeps the box inside it (a half disc r20 h10, the box
   holds y >= 0); New Body makes a second body; back to Join; Cancel: the box is as it was.
2. Select the box's right face (x = 40) and, with Ctrl, its top edge on that side, then
   Revolve: the face turns about the edge at once (Fusion takes the selection). A full
   turn adds the outer three quarters of a cylinder r10; -90 turns it away from the box
   (a quarter round added); 90 turns it into the box: Cut by itself (a quarter round
   removed). OK. Double-click it in the timeline, 45, OK. Undo / redo.
3. A sketch on XZ with a 10 x 5 rectangle (x 50..60, z 0..5) and a construction line at
   x = 70. Revolve: the construction line is drawn as a dashed line to click; click it:
   a ring that does not touch the box: Join makes it a second lump of the box's body (a
   Fusion body can hold several). Two Sides with 270 + 120 degrees: the dialog says the
   angles add up to more than a turn and OK keeps it open. One Side 360, New Body, OK:
   a second body.

Hand-derived: box 12000. 1: cylinder 8000 pi, inside the box 2000 pi -> join
12000 + 6000 pi, intersect 2000 pi, new body 8000 pi. 2: cylinder r10 along the edge,
length 30: 3000 pi; full turn adds 3/4 of it, a quarter turn 750 pi, 45 degrees 375 pi.
3: ring pi (20^2 - 10^2) 5 = 1500 pi.
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
BOX = 12000.0
s = {}


def panel():
    from sciforge import revolve_ui

    p = revolve_ui.RevolvePanel.last
    return p if p is not None and not p._closed else None


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def bodies():
    return [o for o in App.ActiveDocument.Objects if o.TypeId == "PartDesign::Body"]


def box_body():
    return s.get("box_body") or bodies()[0]


def volume():
    return box_body().Shape.Volume


# -- the box ----------------------------------------------------------------------------------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("RevolveAxes")
    h.fit()


def create_sketch():
    h.ribbon("Create Sketch")


def pick_xy():
    h.click(V(12, -8, 0))


def draw_box():
    sk = h.in_sketch()
    h.check("sketch on XY", sk is not None)
    if sk:
        h.draw_rectangle(sk, 0, 0, 40, 30)


def finish_box_sketch():
    h.ribbon("Finish Sketch")


def extrude_box():
    h.fit()
    h.press("e")


def extrude_ok():
    h.task_button("OK")


def box_made():
    h.check("box 40 x 30 x 10", near(h.solid_volume(), BOX), h.solid_volume())
    s["box_body"] = h.body()
    h.fit()


# -- 1. a sketch line as the axis, every operation ------------------------------------------------
def sketch_square():
    h.click_empty()
    h.ribbon("Create Sketch")


def pick_xz():
    h.fit()
    h.click(V(5, 0, 24))


def draw_square():
    sk = h.in_sketch()
    h.check("sketch on XZ", sk is not None and sk.AttachmentSupport[0][0].Role == "XZ_Plane")
    if sk:
        h.draw_rectangle(sk, 0, 0, 20, 20)
        s["square"] = sk


def finish_square():
    h.ribbon("Finish Sketch")


def revolve_square():
    h.fit()
    h.ribbon("Revolve")


def click_sketch_line():
    p = panel()
    h.check("the square is taken by itself", p is not None and len(p.profiles) == 1)
    h.fit()
    h.check("an edge is under the mouse", h.click_edge(V(20, 0, 16)))


def sketch_line_axis():
    p = panel()
    if p is None:
        return
    h.check(
        "the sketch's line is the axis",
        p.axis is not None and p.axis[0] is s["square"] and p.axis[1].startswith("Edge"),
        p.axis,
    )
    h.check("axis box says so", p.fields["axis"].button.text().startswith("Line of"))
    h.check("mostly outside the box: Join", p.operation.currentText() == "Join")
    h.check(
        "join: box + cylinder r20 h20 - overlap",
        near(volume(), BOX + 6000 * PI),
        volume(),
    )
    h.shot("1-sketch-line-axis")
    h.check("choose Intersect", ui.choose(p.operation, "Intersect"))


def intersect():
    p = panel()
    h.check(
        "Intersect is SciForge's revolve feature",
        p.target is not None and getattr(p.target, "SciForgeType", "") == "Revolve",
        p.target and p.target.TypeId,
    )
    h.check("intersect: half disc r20 h10", near(volume(), 2000 * PI), volume())
    h.check("no error text", p.message.text() == "", p.message.text())
    h.check("choose New Body", ui.choose(p.operation, "New Body"))


def new_body():
    p = panel()
    h.check("a second body", len(bodies()) == 2, [b.Label for b in bodies()])
    other = [b for b in bodies() if b is not box_body()]
    h.check(
        "new body holds the cylinder",
        other and near(other[0].Shape.Volume, 8000 * PI),
        other and other[0].Shape.Volume,
    )
    h.check("the box is untouched", near(volume(), BOX), volume())
    h.check("the box is still shown", ri.shown(box_body()))
    h.check("the new body is shown", other and ri.shown(other[0]))
    h.shot("2-new-body")
    h.check("choose Join", ui.choose(p.operation, "Join"))


def back_to_join():
    h.check("back to one body", len(bodies()) == 1, [b.Label for b in bodies()])
    h.check("join again", near(volume(), BOX + 6000 * PI), volume())
    h.check("join shown", ri.shown(box_body()))
    h.task_button("Cancel")


def cancelled():
    h.check("Cancel closes the dialog", not Gui.Control.activeDialog())
    h.check("Cancel: the box as it was", near(volume(), BOX), volume())
    h.check("Cancel: one body", len(bodies()) == 1)
    h.check("Cancel: the box is shown", ri.shown(box_body()))
    h.check(
        "Cancel: no revolve left",
        not [o for o in App.ActiveDocument.Objects if o.TypeId.startswith("PartDesign::Revol")],
    )
    h.fit()


# -- 2. a face and an edge selected first ------------------------------------------------------
def select_face():
    h.click_empty()
    h.fit()
    h.click(V(40, 15, 4))


def select_edge():
    h.click_edge(V(40, 22, 10), QtCore.Qt.ControlModifier)
    h.ensure_also_selected(V(40, 22, 10))


def revolve_selection():
    sel = [(x.ObjectName, list(x.SubElementNames)) for x in Gui.Selection.getSelectionEx()]
    h.check("a face and an edge selected", sum(len(x[1]) for x in sel) == 2, sel)
    h.ribbon("Revolve")


def from_selection():
    p = panel()
    h.check("dialog open", p is not None)
    if p is None:
        return
    h.check(
        "the face is the profile",
        len(p.profiles) == 1 and p.profiles[0][1].startswith("Face"),
        p.profiles,
    )
    h.check(
        "the edge is the axis",
        p.axis is not None and p.axis[1].startswith("Edge"),
        p.axis,
    )
    h.check("preview at once", p.target is not None)
    want = BOX + 3000 * PI * 0.75
    h.check(
        "full turn about the edge adds 3/4 of the round", near(volume(), want), (volume(), want)
    )
    h.check("Join", p.operation.currentText() == "Join", p.operation.currentText())
    ui.type_into(p.angle.widget, "-90")


def turned_out():
    p = panel()
    h.check("-90 turns away from the box: Join", p.operation.currentText() == "Join")
    h.check("a quarter round added", near(volume(), BOX + 750 * PI), volume())
    ui.type_into(p.angle.widget, "90")


def turned_in():
    p = panel()
    h.check("90 turns into the box: Cut by itself", p.operation.currentText() == "Cut")
    h.check(
        "the preview is a Groove",
        p.target is not None and p.target.TypeId == "PartDesign::Groove",
        p.target and p.target.TypeId,
    )
    h.check("a quarter round removed", near(volume(), BOX - 750 * PI), volume())
    h.shot("3-face-cut")
    h.task_button("OK")


def face_ok():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("kept", near(volume(), BOX - 750 * PI), volume())
    h.check("Revolve 1 in the timeline", "Revolve 1" in ui.timeline_titles(), ui.timeline_titles())


def edit_face_revolve():
    h.check("double-click Revolve 1", ui.double_click_timeline("Revolve 1"), ui.timeline_titles())


def edit_45():
    p = panel()
    h.check("editing", p is not None and p.editing)
    if p is None:
        return
    h.check(
        "edit shows 90 and Cut", near(p.angle.value(), 90.0) and p.operation.currentText() == "Cut"
    )
    h.check("edit shows the face and the edge", p.profiles and p.axis is not None)
    ui.type_into(p.angle.widget, "45")


def edit_ok():
    h.check("edit preview 45", near(volume(), BOX - 375 * PI), volume())
    h.task_button("OK")


def edited():
    h.check("edit kept", near(volume(), BOX - 375 * PI), volume())


def undo():
    h.check("Undo button", ui.quick_access("Undo"))


def undone():
    h.check("Undo the edit: back to 90", near(volume(), BOX - 750 * PI), volume())


def redo():
    h.check("Redo button", ui.quick_access("Redo"))


def redone():
    h.check("Redo: 45 again", near(volume(), BOX - 375 * PI), volume())
    s["volume"] = volume()
    h.fit()


# -- 3. a construction line, Join impossible, New Body ------------------------------------------------
def sketch_ring():
    h.click_empty()
    h.ribbon("Create Sketch")


def pick_xz_2():
    h.fit()
    h.click(V(5, 0, 24))


def draw_ring():
    import Part

    sk = h.in_sketch()
    h.check("sketch on XZ", sk is not None and sk.AttachmentSupport[0][0].Role == "XZ_Plane")
    if sk:
        h.draw_rectangle(sk, 50, 0, 60, 5)
        sk.addGeometry(Part.LineSegment(V(70, -5, 0), V(70, 15, 0)), True)  # construction
        App.ActiveDocument.recompute()
        s["ring"] = sk


def finish_ring():
    h.ribbon("Finish Sketch")


def revolve_ring():
    h.fit()
    h.ribbon("Revolve")


def construction_drawn():
    p = panel()
    h.check("the ring profile is taken", p is not None and len(p.profiles) == 1)
    if p is None:
        return
    lines = [l for l in p.axes.lines if l[1] == "construction"]
    h.check(
        "the construction line is drawn to click",
        any(l[0][0] is s["ring"] for l in lines),
        [(l[0][0].Label, l[0][1]) for l in lines],
    )
    h.fit()
    h.shot("4-construction-line")
    h.click(V(70, 0, 11))


def ring_axis():
    p = panel()
    if p is None:
        return
    h.check(
        "the construction line is the axis",
        p.axis is not None and p.axis[0] is s["ring"] and p.axis[1] == "Axis0",
        p.axis,
    )
    h.check("Join (a solid is there)", p.operation.currentText() == "Join")
    h.check(
        "Join: the ring becomes a second lump of the body (Fusion's bodies can have several)",
        near(volume(), s["volume"] + 1500 * PI),
        volume(),
    )
    h.check("no error text", p.message.text() == "", p.message.text())
    h.check("choose Two Sides", ui.choose(p.direction, "Two Sides"))


def two_sides_too_much():
    p = panel()
    h.check(
        "Two Sides from a full turn: side one made room for side two (270 + 90)",
        near(p.angle.value(), 270.0) and near(p.angle2.value(), 90.0),
        (p.angle.value(), p.angle2.value()),
    )
    ui.type_into(p.angle2.widget, "120")


def angles_refused():
    p = panel()
    text = p.message.text()
    h.check("the dialog says the angles add up to more than a turn", "360" in text, text)
    h.task_button("OK")


def still_open():
    p = panel()
    h.check("OK refused: the dialog stays open", p is not None and Gui.Control.activeDialog())
    if p is None:
        return
    h.check("choose One Side", ui.choose(p.direction, "One Side"))


def one_side_full():
    p = panel()
    ui.type_into(p.angle.widget, "360")


def choose_new_body():
    p = panel()
    h.check("error gone", p.message.text() == "", p.message.text())
    h.check("choose New Body", ui.choose(p.operation, "New Body"))


def ring_ok():
    p = panel()
    h.check(
        "no error with New Body", p is not None and p.message.text() == "", p and p.message.text()
    )
    h.task_button("OK")


def ring_made():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("two bodies", len(bodies()) == 2, [b.Label for b in bodies()])
    other = [b for b in bodies() if b is not box_body()]
    h.check(
        "the ring body",
        other and near(other[0].Shape.Volume, 1500 * PI),
        other and other[0].Shape.Volume,
    )
    h.check("the box body unchanged", near(volume(), s["volume"]), volume())
    h.fit()
    h.shot("5-end")


h.run(
    "revolve_axes",
    [
        new_design,
        create_sketch,
        pick_xy,
        draw_box,
        finish_box_sketch,
        extrude_box,
        extrude_ok,
        box_made,
        sketch_square,
        pick_xz,
        draw_square,
        finish_square,
        revolve_square,
        click_sketch_line,
        sketch_line_axis,
        intersect,
        new_body,
        back_to_join,
        cancelled,
        select_face,
        select_edge,
        revolve_selection,
        from_selection,
        turned_out,
        turned_in,
        face_ok,
        edit_face_revolve,
        edit_45,
        edit_ok,
        edited,
        undo,
        undone,
        redo,
        redone,
        sketch_ring,
        pick_xz_2,
        draw_ring,
        finish_ring,
        revolve_ring,
        construction_drawn,
        ring_axis,
        two_sides_too_much,
        angles_refused,
        still_open,
        one_side_full,
        choose_new_body,
        ring_ok,
        ring_made,
    ],
)
