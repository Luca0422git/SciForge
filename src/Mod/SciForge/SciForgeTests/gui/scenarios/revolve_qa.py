# SPDX-License-Identifier: LGPL-2.1-or-later
"""Revolve the way Fusion users really use it, trying to break it (QA, only real input).

Every sketch is drawn with the mouse and typed sizes (R, a click on the origin, the sizes,
Enter), like a person does; expected volumes are worked out by hand from the drawn areas
(Pappus: area x the path of its centre).

Path 1, beginner: Revolve in an empty design says what is missing (no dialog, no pop-up).
        Sketch a 10 x 20 rectangle on XZ, Revolve: its one area is taken by itself. OK with no
        axis keeps the dialog open and says to pick the axis; Enter over the 3D view and a
        click on the background change nothing. Click the Z axis: a cylinder (New Body).
        Enter over the 3D view finishes it (Fusion: Enter is OK). One undo step.
Path 2, wrong order: a sketch with two areas (nothing is taken by itself). Click the axis
        first, then the far area (a New Body: it does not touch the shaft), then the near one
        (both join), then the far one again (it is dropped), OK.
Path 3, Esc in the middle of picking: Ctrl+Z, Revolve, click an area, Esc: nothing changes,
        nothing stays selected, no undo step is left open; Ctrl+Y still brings the undone
        revolve back (the Redo list survives a dialog closed without a change).
Path 4, values while the preview runs: 30 then 60 typed back to back, 0 (said in the
        dialog, OK waits), -90 (the other way), 400 (said), a formula, a parameter, the
        handle dragged far round and back past zero to a negative angle; OK. The revolve
        follows when the parameter changes.
Path 5, edit from the timeline three times with a person's double-click (Two Sides, a
        Cancel, Symmetric), then Ctrl+Z / Ctrl+Y through the edits.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import revolve_input as ri
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import timeline_input as ti

V = App.Vector
PI = math.pi
Z_AXIS = (V(0, 0, 0), V(0, 0, 1))
s = {}


def doc():
    return App.ActiveDocument


def panel():
    return ri.panel()


def msg():
    p = panel()
    return p.message.text() if p is not None else ""


def dialog_open():
    return bool(Gui.Control.activeDialog())


def near(a, c, tol=1e-6):
    return ri.near(a, c, tol)


def esc():
    h.press(QtCore.Qt.Key_Escape)


def formula(p, key):
    """The formula the dialog keeps for a value field ("" when it holds a plain number)."""
    try:
        return p.formula_of(key)
    except AttributeError:
        return "<the dialog keeps no formulas>"


def vol():
    return h.solid_volume()


def total():
    """Volume of every body (a revolve away from the part is a body of its own)."""
    return sum(
        o.Shape.Volume
        for o in doc().Objects
        if o.TypeId == "PartDesign::Body" and not o.Shape.isNull() and o.Shape.Solids
    )


def body_shown():
    return ri.shown(h.body())


def sketch_click(point):
    """Click in a sketch on the XZ plane, the pointer coming in along the plane."""
    si.click(point, approach=V(1.0, 0, 0.6))


def toward(point, direction):
    si.move_towards(point, direction)


def region_click(sketch, which):
    """Click inside the area `which` (a function of the area's face) of a sketch, where
    nothing of the part is in front of it."""
    faces = [f for _sub, f in ri.regions(sketch)]
    face = which(faces)
    p = panel()
    # The part before the revolve can hide an area; the preview does not (it is not a pick).
    shape = p._occluder() if p is not None else ri.body_shape()
    point = ri.visible_point(face, shape)
    h.check("a visible spot inside the area", point is not None)
    if point is not None:
        pl.click_on_plane(point)


# == Path 1: beginner ============================================================================
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("RevolveQA")
    h.fit()
    h.click_empty()
    h.ribbon("Revolve")


def p1_empty():
    h.check("P1 Revolve in an empty design opens no dialog", not dialog_open())
    h.check("P1 no pop-up", not h.popups(), h.popups())
    h.check("P1 says a sketch is needed", "sketch" in si.tooltip().lower(), si.tooltip())
    h.ribbon("Create Sketch")


def p1_plane():
    pl.click_square("XZ_Plane")  # where the square shows (was 12, 0, 8)


def p1_rect_key():
    s["sk1"] = h.in_sketch()
    h.check("P1 sketch open on XZ", s["sk1"] is not None)
    h.press("r")


def p1_corner():
    sketch_click(V(0, 0, 0))


def p1_size():
    toward(V(8, 0, 16), V(0.45, 0, 0.9))
    si.type_text("10", enter=False)
    si.tab()
    si.type_text("20")


def p1_finish():
    esc()
    h.ribbon("Finish Sketch")


def p1_revolve():
    sk = s["sk1"]
    areas = ri.regions(sk)
    h.check("P1 the sketch has one area", len(areas) == 1, areas)
    if areas:
        box = areas[0][1].BoundBox
        s["r1"] = (box.XMin, box.XMax, box.ZMin, box.ZMax)
        h.check(
            "P1 the drawn rectangle is 10 x 20 from the origin",
            [round(v, 6) for v in s["r1"]] == [0, 10, 0, 20],
            s["r1"],
        )
    h.fit()
    s["undo"] = doc().UndoCount
    h.ribbon("Revolve")


def p1_open():
    p = panel()
    h.check("P1 Revolve opens", p is not None and dialog_open())
    if p is None:
        return
    h.check("P1 the one area is taken by itself", len(p.profiles) == 1, p.profiles)
    h.check("P1 the Axis box waits", p.active == "axis" and p.axis is None, p.active)
    h.check("P1 New Body is offered for the first solid", p.operation.currentText() == "New Body")
    h.task_button("OK")


def p1_ok_refused():
    h.check("P1 OK without an axis keeps the dialog open", dialog_open() and panel() is not None)
    h.check("P1 the dialog says to pick the axis", "axis" in msg().lower(), msg())
    h.check("P1 nothing was built", not ri.revolves(), ri.revolves())
    h.check("P1 no pop-up", not h.popups(), h.popups())
    h.shot("p1-ok-refused")
    h.click_empty()


def p1_background():
    p = panel()
    h.check("P1 a background click keeps the profile", p is not None and len(p.profiles) == 1)
    h.press(QtCore.Qt.Key_Return)


def p1_enter_refused():
    h.check("P1 Enter without an axis keeps the dialog", dialog_open() and panel() is not None)
    h.fit()
    pl.click_on_plane(V(0, 0, 32))


def p1_axis():
    p = panel()
    if p is None:
        h.check("P1 dialog still open", False)
        return
    h.check("P1 the Z axis is picked", p.axis is not None and p.axis[0].Role == "Z_Axis", p.axis)
    want = PI * 100.0 * 20.0
    h.check("P1 cylinder r10 h20", near(vol(), want), (vol(), want))
    h.check("P1 no warning", "⚠" not in msg(), msg())
    h.shot("p1-cylinder")
    h.click_empty()  # the mouse over the 3D view
    h.press(QtCore.Qt.Key_Return)


def p1_done():
    h.check("P1 Enter over the 3D view finishes the revolve (Fusion)", not dialog_open())
    want = PI * 100.0 * 20.0
    h.check("P1 kept: cylinder r10 h20", near(vol(), want), (vol(), want))
    h.check("P1 one undo step", doc().UndoCount == s["undo"] + 1, (doc().UndoCount, s["undo"]))
    h.check("P1 no undo step left open", not doc().HasPendingTransaction)
    h.check("P1 the sketch is hidden", not s["sk1"].ViewObject.Visibility)
    h.check("P1 nothing selected", not Gui.Selection.getSelectionEx())
    h.check("P1 the part is shown", body_shown())
    s["v1"] = vol()


# == Path 2: the axis first, then the areas, one dropped again ===================================
def p2_sketch():
    h.fit()
    h.click_empty()
    h.ribbon("Create Sketch")


def p2_plane():
    pl.click_square("XZ_Plane")  # where the square shows (was 11, 0, -9)


def p2_rect1_key():
    s["sk2"] = h.in_sketch()
    h.check("P2 second sketch open", s["sk2"] is not None and s["sk2"] is not s["sk1"])
    h.press("r")


def p2_rect1_corner():
    sketch_click(V(0, 0, 0))


def p2_rect1_size():
    toward(V(-4, 0, -8), V(-0.45, 0, -0.9))
    si.type_text("6", enter=False)
    si.tab()
    si.type_text("12")


def p2_rect2_corner():
    sketch_click(V(-20, 0, -12))


def p2_rect2_size():
    toward(V(-23, 0, -6), V(-0.45, 0, 0.9))
    si.type_text("4", enter=False)
    si.tab()
    si.type_text("8")


def p2_finish():
    esc()
    h.ribbon("Finish Sketch")


def p2_revolve():
    areas = ri.regions(s["sk2"])
    h.check("P2 two separate areas", len(areas) == 2, areas)
    h.fit()
    h.ribbon("Revolve")


def p2_open():
    p = panel()
    h.check("P2 Revolve opens", p is not None)
    if p is None:
        return
    h.check("P2 two areas: nothing is taken by itself", not p.profiles, p.profiles)
    h.check("P2 the Profile box waits", p.active == "profiles", p.active)
    h.fit()
    pl.click_on_plane(V(0, 0, 32))  # the axis first, while the Profile box waits


def _near_area(faces):  # the area touching the Z axis
    return min(faces, key=lambda f: abs(f.BoundBox.XMax))


def _far_area(faces):
    return max(faces, key=lambda f: abs(f.BoundBox.XMax))


def p2_axis_first():
    p = panel()
    if p is None:
        return
    h.check("P2 a click on the axis sets the axis", p.axis is not None, p.axis)
    h.check("P2 no profile yet, nothing built", not p.profiles and p.target is None)
    h.check("P2 no warning", "⚠" not in msg(), msg())
    region_click(s["sk2"], _far_area)


def p2_far():
    p = panel()
    if p is None:
        return
    far = _far_area([f for _s, f in ri.regions(s["sk2"])])
    s["far"] = ri.pappus(far, *Z_AXIS)
    h.check("P2 the far area is picked", len(p.profiles) == 1, p.profiles)
    want = s["v1"] + s["far"]
    # Fusion: a revolve that does not touch the part is a New Body (the ring is not joined).
    h.check("P2 a ring away from the shaft", near(total(), want), (total(), want))
    h.check(
        "P2 it is a New Body", p.operation.currentText() == "New Body", p.operation.currentText()
    )
    region_click(s["sk2"], _near_area)


def p2_both():
    p = panel()
    if p is None:
        return
    near_face = _near_area([f for _s, f in ri.regions(s["sk2"])])
    s["near"] = ri.pappus(near_face, *Z_AXIS)
    h.check("P2 both areas picked", len(p.profiles) == 2, p.profiles)
    want = s["v1"] + s["far"] + s["near"]
    h.check("P2 both revolved", near(vol(), want), (vol(), want))
    region_click(s["sk2"], _far_area)


def p2_dropped():
    p = panel()
    if p is None:
        return
    h.check("P2 a second click on an area drops it", len(p.profiles) == 1, p.profiles)
    want = s["v1"] + s["near"]
    h.check("P2 only the near area is revolved", near(vol(), want), (vol(), want))
    h.shot("p2-dropped")
    h.task_button("OK")


def p2_done():
    h.check("P2 OK closes the dialog", not dialog_open())
    want = s["v1"] + s["near"]
    h.check("P2 kept", near(vol(), want), (vol(), want))
    h.check("P2 valid solid", h.body().Shape.isValid())
    h.check("P2 two revolves", len(ri.revolves()) == 2, ri.revolves())
    s["v2"] = vol()


# == Path 3: Esc in the middle of picking; the Redo list survives =================================
def p3_undo():
    s["undo"] = doc().UndoCount
    ti.ctrl("z")


def p3_undone():
    h.check("P3 Ctrl+Z undid the revolve", near(vol(), s["v1"]), vol())
    s["redo"] = doc().RedoCount
    h.check("P3 something to redo", s["redo"] >= 1, s["redo"])
    h.fit()
    h.ribbon("Revolve")


def p3_pick():
    p = panel()
    h.check("P3 Revolve opens", p is not None)
    region_click(s["sk2"], _near_area)


def p3_esc():
    p = panel()
    h.check("P3 the area is picked", p is not None and len(p.profiles) == 1, p and p.profiles)
    esc()


def p3_closed():
    h.check("P3 Esc closes the dialog", not dialog_open())
    h.check("P3 nothing changed", near(vol(), s["v1"]), vol())
    h.check("P3 nothing selected", not Gui.Selection.getSelectionEx())
    h.check("P3 no undo step left open", not doc().HasPendingTransaction)
    h.check("P3 the Redo list is kept", doc().RedoCount == s["redo"], doc().RedoCount)
    h.check("P3 the part is shown", body_shown())
    ti.ctrl("y")


def p3_redone():
    h.check("P3 Ctrl+Y brings the revolve back", near(vol(), s["v2"]), vol())
    h.check("P3 two revolves", len(ri.revolves()) == 2, ri.revolves())


# == Path 4: values while the preview runs ===============================================================
def p4_sketch():
    h.fit()
    h.click_empty()
    h.ribbon("Create Sketch")


def p4_plane():
    h.fit()  # the plane squares too
    pl.click_square("XZ_Plane")  # where the XZ square shows


def p4_rect_key():
    s["sk3"] = h.in_sketch()
    h.check("P4 third sketch open", s["sk3"] is not None)
    h.press("r")


def p4_corner():
    sketch_click(V(0, 0, 0))


def p4_size():
    toward(V(12, 0, -6), V(0.9, 0, -0.45))
    si.type_text("15", enter=False)
    si.tab()
    si.type_text("8")


def p4_finish():
    esc()
    h.ribbon("Finish Sketch")


def p4_revolve():
    areas = ri.regions(s["sk3"])
    h.check("P4 one area", len(areas) == 1, areas)
    if areas:
        face = areas[0][1]
        bb = face.BoundBox
        h.check(
            "P4 the rectangle is 15 x 8",
            [round(v, 6) for v in (bb.XMin, bb.XMax, bb.ZMin, bb.ZMax)] == [0, 15, -8, 0],
            (bb.XMin, bb.XMax, bb.ZMin, bb.ZMax),
        )
        # what a full turn adds: the disc r15 h8 minus the part of it the r6 boss already fills
        s["add360"] = PI * (225.0 - 36.0) * 8.0
    h.fit()
    h.ribbon("Revolve")


def p4_axis():
    p = panel()
    h.check("P4 the new sketch's area is taken", p is not None and len(p.profiles) == 1)
    h.fit()
    pl.click_on_plane(V(0, 0, 32))


def added(angle):
    return s["v2"] + s["add360"] * abs(angle) / 360.0


def p4_full():
    p = panel()
    if p is None:
        return
    h.check("P4 360: a disc added", near(vol(), added(360)), (vol(), added(360)))
    h.check("P4 Join", p.operation.currentText() == "Join", p.operation.currentText())
    ui.type_into(p.angle.widget, "30")
    ui.type_into(p.angle.widget, "60")


def p4_sixty():
    p = panel()
    h.check("P4 the last value wins: 60", near(p.angle.value(), 60.0), p.angle.value())
    h.check("P4 preview at 60", near(vol(), added(60)), (vol(), added(60)))
    bb = ri.bbox(h.body().Shape)
    y60 = round(15.0 * math.sin(math.radians(60.0)), 4)
    h.check("P4 a positive angle turns towards +Y", bb[4] == y60 and bb[1] == -10.0, bb)
    ui.type_into(p.angle.widget, "0")


def p4_zero():
    p = panel()
    h.check("P4 0 is explained in the dialog", "⚠" in msg() and "zero" in msg().lower(), msg())
    h.check("P4 no pop-up", not h.popups(), h.popups())
    h.task_button("OK")


def p4_zero_ok():
    h.check("P4 OK waits while the angle is 0", dialog_open() and panel() is not None)
    p = panel()
    if p:
        ui.type_into(p.angle.widget, "-90")


def p4_minus90():
    p = panel()
    h.check("P4 -90 is fine", "⚠" not in msg(), msg())
    h.check("P4 a quarter", near(vol(), added(90)), (vol(), added(90)))
    bb = ri.bbox(h.body().Shape)  # the shaft reaches y = +-10, the new disc r15
    h.check("P4 -90 turns the other way (towards -Y)", bb[1] == -15.0 and bb[4] == 10.0, bb)
    ui.type_into(p.angle.widget, "400")


def p4_400():
    h.check("P4 400 is explained", "⚠" in msg() and "360" in msg(), msg())
    p = panel()
    ui.type_into(p.angle.widget, "45*2")


def p4_formula():
    p = panel()
    h.check(
        "P4 a formula: 45*2 = 90", p is not None and near(p.angle.value(), 90.0), p.angle.value()
    )
    h.check("P4 a quarter again", near(vol(), added(90)), (vol(), added(90)))
    h.check("P4 no warning", "⚠" not in msg(), msg())
    from sciforge import parameters

    # Change Parameters (its own dialog) made this user parameter:
    parameters.add_user(doc(), "turn", "deg", "120")


def p4_parameter():
    p = panel()
    ui.type_into(p.angle.widget, "turn")


def p4_param_typed():
    p = panel()
    h.check("P4 'turn' is 120", p is not None and near(p.angle.value(), 120.0), p.angle.value())
    h.check("P4 preview at 120", near(vol(), added(120)), (vol(), added(120)))
    h.check("P4 no warning", "⚠" not in msg(), msg())
    h.fit()


def p4_drag_far():
    p = panel()
    handle = p.handles.get("angle") if p else None
    h.check("P4 the handle is there", handle is not None, p and list(p.handles))
    if handle is not None:
        h.check("P4 the handle sits at 120", near(handle.angle(), 120.0), handle.angle())
        ri.drag_handle(handle, 340.0, steps=36)


p4_drag_far.wait_ms = 1500


def p4_dragged_far():
    p = panel()
    a = p.angle.value()
    h.check("P4 dragged far round: 300..360", 300.0 <= a <= 360.0, a)
    h.check("P4 volume follows", near(vol(), added(a), 1e-5), (vol(), added(a)))
    h.check("P4 a drag drops the formula", not formula(p, "angle"), formula(p, "angle"))
    h.shot("p4-dragged-far")
    handle = p.handles.get("angle")
    if handle is not None:
        ri.drag_handle(handle, -100.0, steps=60)


p4_dragged_far.wait_ms = 1800


def p4_dragged_back():
    p = panel()
    a = p.angle.value()
    h.check("P4 dragged back past zero: negative", -130.0 <= a <= -70.0, a)
    h.check("P4 volume follows", near(vol(), added(a), 1e-5), (vol(), added(a)))
    h.check("P4 no warning", "⚠" not in msg(), msg())
    h.shot("p4-dragged-negative")
    ui.type_into(p.angle.widget, "turn")


def p4_ok():
    h.task_button("OK")


def p4_done():
    h.check("P4 OK closes", not dialog_open())
    h.check("P4 kept at 120", near(vol(), added(120)), (vol(), added(120)))
    rev = [o for o in ri.revolves() if "Invalid" not in o.State]
    h.check("P4 three revolves", len(ri.revolves()) == 3 and len(rev) == 3, ri.revolves())
    from sciforge import parameters

    parameters.set_user(doc(), "turn", "150")  # in Change Parameters
    doc().recompute()


def p4_follows():
    h.check("P4 the revolve follows turn = 150", near(vol(), added(150)), (vol(), added(150)))
    h.check("P4 valid", h.body().Shape.isValid())
    s["v4"] = vol()


# == Path 5: edit three times from the timeline, undo / redo ===========================================
def p5_edit1():
    titles = b.timeline_titles()
    s["title"] = [t for t in titles if t.startswith("Revolve")][-1] if titles else "Revolve 3"
    b.timeline_double_click(s["title"], click_first=True)


def p5_editing1():
    p = panel()
    h.check("P5 editing the third revolve", p is not None and p.editing)
    if p is None:
        return
    h.check("P5 the angle shows 150", near(p.angle.value(), 150.0), p.angle.value())
    h.check("P5 the formula is shown", formula(p, "angle") == "turn", formula(p, "angle"))
    h.check("P5 one profile and the Z axis", len(p.profiles) == 1 and p.axis is not None)
    b.choose(p.direction, "Two Sides")
    ui.type_into(p.angle.widget, "90")
    ui.type_into(p.angle2.widget, "45")


def p5_ok1():
    p = panel()
    h.check("P5 two sides: 135 in all", near(vol(), added(135)), (vol(), added(135)))
    h.task_button("OK")


def p5_edit2():
    h.check("P5 kept", not dialog_open() and near(vol(), added(135)), vol())
    s["v5a"] = vol()
    b.timeline_double_click(s["title"], click_first=True)


def p5_cancel():
    p = panel()
    h.check(
        "P5 second edit shows Two Sides", p is not None and p.direction.currentText() == "Two Sides"
    )
    if p is None:
        return
    h.check("P5 and 90 / 45", near(p.angle.value(), 90.0) and near(p.angle2.value(), 45.0))
    b.choose(p.type, "Full")
    h.task_button("Cancel")


def p5_cancelled():
    h.check("P5 Cancel keeps the revolve as it was", near(vol(), s["v5a"]), vol())
    h.check("P5 the part is shown", body_shown())
    b.timeline_double_click(s["title"], click_first=True)


def p5_edit3():
    p = panel()
    h.check("P5 third edit opens", p is not None and p.editing)
    if p is None:
        return
    b.choose(p.direction, "Symmetric")
    ui.type_into(p.angle.widget, "30")


def p5_ok3():
    h.check("P5 symmetric 30 each way: 60", near(vol(), added(60)), (vol(), added(60)))
    h.task_button("OK")


def p5_undo1():
    h.check("P5 kept: 60", not dialog_open() and near(vol(), added(60)), vol())
    ti.ctrl("z")


def p5_undo2():
    h.check("P5 Ctrl+Z: back to two sides", near(vol(), s["v5a"]), vol())
    ti.ctrl("z")


def p5_redo1():
    h.check("P5 Ctrl+Z again: back to 150", near(vol(), s["v4"]), vol())
    h.check("P5 the part is shown", body_shown())
    ti.ctrl("y")


def p5_redo2():
    h.check("P5 Ctrl+Y: two sides", near(vol(), s["v5a"]), vol())
    ti.ctrl("y")


def p5_end():
    h.check("P5 Ctrl+Y: symmetric 60", near(vol(), added(60)), vol())
    h.check("P5 valid", h.body().Shape.isValid())
    invalid = [o.Label for o in doc().Objects if "Invalid" in o.State]
    h.check("P5 nothing broken", not invalid, invalid)
    h.shot("p5-end")


STEPS = [
    new_design,
    p1_empty,
    p1_plane,
    p1_rect_key,
    p1_corner,
    p1_size,
    p1_finish,
    p1_revolve,
    p1_open,
    p1_ok_refused,
    p1_background,
    p1_enter_refused,
    p1_axis,
    p1_done,
    p2_sketch,
    p2_plane,
    p2_rect1_key,
    p2_rect1_corner,
    p2_rect1_size,
    p2_rect2_corner,
    p2_rect2_size,
    p2_finish,
    p2_revolve,
    p2_open,
    p2_axis_first,
    p2_far,
    p2_both,
    p2_dropped,
    p2_done,
    p3_undo,
    p3_undone,
    p3_pick,
    p3_esc,
    p3_closed,
    p3_redone,
    p4_sketch,
    p4_plane,
    p4_rect_key,
    p4_corner,
    p4_size,
    p4_finish,
    p4_revolve,
    p4_axis,
    p4_full,
    p4_sixty,
    p4_zero,
    p4_zero_ok,
    p4_minus90,
    p4_400,
    p4_formula,
    p4_parameter,
    p4_param_typed,
    p4_drag_far,
    p4_dragged_far,
    p4_dragged_back,
    p4_ok,
    p4_done,
    p4_follows,
    p5_edit1,
    p5_editing1,
    p5_ok1,
    p5_edit2,
    p5_cancel,
    p5_cancelled,
    p5_edit3,
    p5_ok3,
    p5_undo1,
    p5_undo2,
    p5_redo1,
    p5_redo2,
    p5_end,
]

h.run("revolve_qa", ti.watched(STEPS))
