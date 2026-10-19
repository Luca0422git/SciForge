# SPDX-License-Identifier: LGPL-2.1-or-later
"""Primitives QA, a beginner's and a power user's paths (only real input).

P1. A new design, Box from SOLID > CREATE with nothing selected. OK before anything is
    picked: the dialog stays and says what to do. The XY square, the first corner, Esc in
    the middle of the pick: nothing is left (no box, no body, no outline in the view).
    Box again: the first corner, then Length 30 typed in the dialog while placing (Fusion:
    "place the opposite corner, or specify exact Length and Width values"): the typed
    length stays while the mouse moves; the second click only gives the width (15).
    A typo in Width and a zero Height are said in the dialog and OK waits; Width 12,
    Height 10, OK. Ctrl+Z: the design is empty again (the body went with the box); Ctrl+Y.
P2. Values changed while the preview runs, on the box's top face (selected first: taken at
    once). Cylinder d6; Height -5 typed (the field is not left): the preview follows at
    once and turns into a Cut by itself. An unknown parameter in Diameter: said, OK waits;
    8. Intersect picked and Height -8 typed right after it: both count. OK.
P3. Handles dragged far and negative: a 20 x 10 box; the Length arrow dragged through the
    first corner to -15 (the box flips over to that side, the arrow and the box agree);
    the Width arrow out to 50; the Height arrow down to -25 (below the plane); OK.
P4. Editing from the timeline twice, then undo / redo: a Sphere d10 on the box's top
    (Join: half of it sticks out); Sphere 1 edited to Cut, then to Intersect; Ctrl+Z twice,
    Ctrl+Y twice. An edit closed with OK and no change adds no undo step (Ctrl+Z still
    goes back to the Cut).

Volumes by hand (pi = PI): box 30 x 12 x 10 = 3600; cylinder d6 h5 = 45 pi; d8 h5 = 80 pi;
d8 h8 = 128 pi; box 15 x 50 x 25 = 18750; half sphere r5 = 250 pi / 3.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import primitive_input as pi

V = App.Vector
PI = math.pi
HALF = 250.0 * PI / 3.0
s = {}


def doc():
    return App.ActiveDocument


def near(a, b, tol=1e-6):
    return pi.near(a, b, tol)


def vol():
    return pi.total_volume()


def msg(p):
    return p.message.text() if p is not None else ""


def scene_children():
    from pivy import coin  # noqa: F401  (getSceneGraph needs pivy loaded)

    return h.view().getSceneGraph().getNumChildren()


def type_live(widget, text):
    """Click into a number field, select its text and type `text`, without leaving the
    field (no Tab, no Enter): a person who types and looks at the preview."""
    QtTest.QTest.mouseClick(
        widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, QtCore.QPoint(10, widget.height() // 2)
    )
    widget.setFocus()
    QtTest.QTest.keyClick(widget, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
    QtTest.QTest.keyClicks(widget, text)
    QtWidgets.QApplication.processEvents()


def boxes():
    return [o for o in doc().Objects if "Box" in o.TypeId]


# == P1: a beginner's first box =====================================================================
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("PrimQAPaths")
    h.fit()
    s["sg"] = scene_children()
    pi.menu("Box")


def p1_ok_first():
    p = pi.panel("BoxPanel")
    h.check("P1 Box waits for a plane", p is not None and p.state == "plane", p and p.state)
    h.task_button("OK")


def p1_ok_refused():
    p = pi.panel("BoxPanel")
    h.check("P1 OK with nothing picked keeps the dialog", p is not None)
    h.check("P1 it says what to pick", "plane" in msg(p).lower(), msg(p))
    h.check("P1 no pop-up", not h.popups(), h.popups())
    pl.click_on_plane(V(15, -15, 0))  # the XY square


def p1_corner():
    p = pi.panel("BoxPanel")
    h.check("P1 placing", p is not None and p.state == "place", p and p.state)
    pl.click_on_plane(V(0, 0, 0))


def p1_rubber():
    pi.hover(V(10, 6, 0))
    pi.hover(V(12, 8, 0))


def p1_esc():
    p = pi.panel("BoxPanel")
    h.check("P1 asks for the opposite corner", p is not None and "opposite" in p.info.text())
    h.press(QtCore.Qt.Key_Escape)


p1_esc.wait_ms = 1200


def p1_nothing_left():
    h.check("P1 Esc closed the Box", pi.no_dialog())
    h.check("P1 no box", not boxes(), [o.Name for o in doc().Objects])
    h.check("P1 no body made", not pi.bodies(), [b.Name for b in pi.bodies()])
    h.check(
        "P1 no outline or square left in the view",
        scene_children() == s["sg"],
        (scene_children(), s["sg"]),
    )
    pi.menu("Box")


def p1_plane():
    pl.click_square("XY_Plane")  # where the square shows (was 15, -15, 0)


def p1_corner_again():
    pl.click_on_plane(V(0, 0, 0))


def p1_type_length():
    p = pi.panel("BoxPanel")
    h.check("P1 placing again", p is not None and p.state == "place", p and p.state)
    if p is not None:
        ui.type_into(p.length.widget, "30")


def p1_mouse_moves():
    pi.hover(V(14, 12, 0))
    pi.hover(V(20, 15, 0))


def p1_length_kept():
    p = pi.panel("BoxPanel")
    if p is None:
        return
    h.check(
        "P1 the typed length stays while the mouse moves",
        near(p.length.value(), 30.0),
        p.length.value(),
    )
    h.check("P1 the width follows the mouse", near(p.width.value(), 15.0, 1e-3), p.width.value())
    pl.click_on_plane(V(20, 15, 0))


p1_length_kept.wait_ms = 1500


def p1_placed():
    p = pi.panel("BoxPanel")
    box = p.target if p is not None else None
    h.check("P1 a box", box is not None and p.state == "ready")
    if box is None:
        return
    h.check("P1 30 long (typed)", near(box.Length.Value, 30.0), box.Length.Value)
    h.check("P1 15 wide (clicked)", near(box.Width.Value, 15.0), box.Width.Value)
    h.check("P1 New Body (the first solid)", p.operation.currentText() == "New Body")
    ui.type_into(p.width.widget, "wdth")


p1_placed.wait_ms = 1500


def p1_typo():
    p = pi.panel("BoxPanel")
    h.check("P1 the typo is said", "wdth" in msg(p), msg(p))
    h.task_button("OK")


def p1_typo_ok():
    p = pi.panel("BoxPanel")
    h.check("P1 OK waits for a value", p is not None)
    if p is not None:
        ui.type_into(p.width.widget, "12")


p1_typo_ok.wait_ms = 1200


def p1_zero():
    p = pi.panel("BoxPanel")
    h.check("P1 the message went with the typo", msg(p) == "", msg(p))
    ui.type_into(p.height.widget, "0")


p1_zero.wait_ms = 1200


def p1_zero_said():
    p = pi.panel("BoxPanel")
    h.check("P1 a zero height is said", "0" in msg(p) and "height" in msg(p).lower(), msg(p))
    h.task_button("OK")


def p1_zero_ok():
    p = pi.panel("BoxPanel")
    h.check("P1 OK waits for a height", p is not None)
    if p is not None:
        ui.type_into(p.height.widget, "10")


p1_zero_ok.wait_ms = 1200


def p1_ok():
    p = pi.panel("BoxPanel")
    h.check("P1 no message", msg(p) == "", msg(p))
    h.check("P1 30 x 12 x 10", near(vol(), 3600.0), vol())
    h.task_button("OK")


def p1_kept():
    h.check("P1 OK closed it", pi.no_dialog())
    h.check("P1 kept", near(vol(), 3600.0), vol())
    h.check("P1 one Box step", ui.timeline_titles() == ["Box 1"], ui.timeline_titles())
    h.press("z", QtCore.Qt.ControlModifier)


p1_kept.wait_ms = 1200


def p1_undone():
    h.check("P1 Ctrl+Z: no box", not boxes())
    h.check("P1 Ctrl+Z: no body either", not pi.bodies(), [b.Name for b in pi.bodies()])
    h.press("y", QtCore.Qt.ControlModifier)


p1_undone.wait_ms = 1200


def p1_redone():
    h.check("P1 Ctrl+Y: the box is back", near(vol(), 3600.0), vol())
    body = pi.bodies()[0] if pi.bodies() else None
    h.check("P1 shown", body is not None and pi.shown(body))
    h.fit()


# == P2: values changed while the preview runs ======================================================
def p2_select_top():
    h.click(V(15, 6, 10))


def p2_cylinder():
    h.check("P2 the top face is selected", bool(Gui.Selection.getSelectionEx()))
    pi.menu("Cylinder")


def p2_centre():
    p = pi.panel("CylinderPanel")
    h.check("P2 the selected face is taken", p is not None and p.state == "place", p and p.state)
    if p is not None:
        h.check(
            "P2 on the box's face",
            p.plane_field.button.text() == "Face of Box 1",
            p.plane_field.button.text(),
        )
    h.click(V(15, 6, 10))


def p2_circle():
    h.click(V(18, 6, 10))


p2_circle.wait_ms = 1500


def p2_height_live():
    p = pi.panel("CylinderPanel")
    h.check("P2 d6", p is not None and near(p.diameter.value(), 6.0), p and p.diameter.value())
    if p is not None:
        type_live(p.height.widget, "-5")


p2_height_live.wait_ms = 1500


def p2_follows():
    p = pi.panel("CylinderPanel")
    if p is None:
        return
    h.check(
        "P2 into the part: Cut by itself",
        p.operation.currentText() == "Cut",
        p.operation.currentText(),
    )
    h.check("P2 the preview follows the typing", near(vol(), 3600.0 - 45.0 * PI), vol())
    ui.type_into(p.diameter.widget, "w2")


p2_follows.wait_ms = 1200


def p2_unknown():
    p = pi.panel("CylinderPanel")
    h.check("P2 the unknown name is said", "w2" in msg(p), msg(p))
    h.task_button("OK")


def p2_waits():
    p = pi.panel("CylinderPanel")
    h.check("P2 OK waits", p is not None)
    if p is not None:
        ui.type_into(p.diameter.widget, "8")


p2_waits.wait_ms = 1200


def p2_d8():
    p = pi.panel("CylinderPanel")
    h.check("P2 message gone", msg(p) == "", msg(p))
    h.check("P2 d8 h5 cut", near(vol(), 3600.0 - 80.0 * PI), vol())
    ui.choose(p.operation, "Intersect")
    type_live(p.height.widget, "-8")


p2_d8.wait_ms = 1500


def p2_both():
    p = pi.panel("CylinderPanel")
    if p is None:
        return
    h.check(
        "P2 Intersect stays picked",
        p.operation.currentText() == "Intersect",
        p.operation.currentText(),
    )
    h.check("P2 d8 h8 kept inside", near(vol(), 128.0 * PI), vol())
    h.task_button("OK")


p2_both.wait_ms = 1500


def p2_done():
    h.check("P2 closed", pi.no_dialog())
    h.check("P2 kept", near(vol(), 128.0 * PI), vol())
    h.check("P2 timeline", ui.timeline_titles() == ["Box 1", "Cylinder 1"], ui.timeline_titles())
    h.shot("p2")


# == P3: handles dragged far and negative =========================================================
def p3_new():
    App.newDocument("PrimQAHandles")
    h.fit()
    pi.menu("Box")


def p3_plane():
    pl.click_square("XY_Plane")  # where the square shows (was 15, -15, 0)


def p3_c1():
    pl.click_on_plane(V(0, 0, 0))


def p3_c2():
    pl.click_on_plane(V(20, 10, 0))


p3_c2.wait_ms = 1500


def p3_length_negative():
    p = pi.panel("BoxPanel")
    h.check("P3 a 20 x 10 box", p is not None and p.target is not None)
    if p is None or "length" not in p.handles:
        h.check("P3 a length arrow", False)
        return
    h.fit()
    pi.drag_handle(p.handles["length"], -15.0)


p3_length_negative.wait_ms = 1500


def p3_flipped():
    p = pi.panel("BoxPanel")
    if p is None:
        return
    bb = pi.bbox(p.target.Shape)
    h.check(
        "P3 the box flipped over the first corner",
        near(bb[0], -15.0, 1e-3) and near(bb[3], 0.0, 1e-3),
        bb,
    )
    h.check("P3 Length shows 15", near(p.length.value(), 15.0, 1e-3), p.length.value())
    handle = p.handles.get("length")
    h.check(
        "P3 the arrow sits on the box's end",
        handle is not None and near(handle.position().x, -15.0, 1e-3),
        handle and handle.position(),
    )
    pi.drag_handle(p.handles["width"], 50.0)


p3_flipped.wait_ms = 1500


def p3_width():
    p = pi.panel("BoxPanel")
    if p is None:
        return
    bb = pi.bbox(p.target.Shape)
    h.check("P3 50 wide", near(bb[4] - bb[1], 50.0, 1e-3), bb)
    pi.drag_handle(p.handles["height"], -25.0)


p3_width.wait_ms = 1500


def p3_height():
    p = pi.panel("BoxPanel")
    if p is None:
        return
    bb = pi.bbox(p.target.Shape)
    h.check("P3 below the plane", near(bb[2], -25.0, 1e-3) and near(bb[5], 0.0, 1e-3), bb)
    h.check("P3 still New Body", p.operation.currentText() == "New Body")
    h.check("P3 no message", msg(p) == "", msg(p))
    h.task_button("OK")


p3_height.wait_ms = 1500


def p3_kept():
    h.check("P3 kept: 15 x 50 x 25", near(vol(), 18750.0, 1e-5), vol())
    h.fit()


# == P4: edit twice from the timeline, undo / redo =================================================
def p4_sphere():
    h.click_empty()
    pi.menu("Sphere")


def p4_plane():
    pl.click_square("XY_Plane")  # where the square shows (was 30, -30, 0)


def p4_centre():
    p = pi.panel("SpherePanel")
    h.check("P4 placing the sphere", p is not None and p.state == "place", p and p.state)
    pl.click_on_plane(V(-7.5, 25, 0))


p4_centre.wait_ms = 1500


def p4_size():
    p = pi.panel("SpherePanel")
    h.check("P4 a sphere", p is not None and p.target is not None)
    if p is not None:
        ui.type_into(p.diameter.widget, "10")


p4_size.wait_ms = 1500


def p4_ok():
    p = pi.panel("SpherePanel")
    h.check(
        "P4 half sticks out: Join",
        p is not None and p.operation.currentText() == "Join",
        p and p.operation.currentText(),
    )
    h.check("P4 box + half sphere", near(vol(), 18750.0 + HALF, 1e-5), vol())
    h.task_button("OK")


def p4_edit_cut():
    h.check("P4 double-click Sphere 1", ui.double_click_timeline("Sphere 1"), ui.timeline_titles())


def p4_cut():
    p = pi.panel("SpherePanel")
    h.check("P4 editing", p is not None and p.editing)
    if p is not None:
        ui.choose(p.operation, "Cut")


p4_cut.wait_ms = 1500


def p4_cut_ok():
    h.check("P4 Cut: box - half sphere", near(vol(), 18750.0 - HALF, 1e-5), vol())
    h.task_button("OK")


def p4_edit_intersect():
    h.check(
        "P4 still one step 'Sphere 1'",
        ui.timeline_titles() == ["Box 1", "Sphere 1"],
        ui.timeline_titles(),
    )
    h.check("P4 double-click Sphere 1 again", ui.double_click_timeline("Sphere 1"))


def p4_intersect():
    p = pi.panel("SpherePanel")
    h.check("P4 editing a Cut", p is not None and p.operation.currentText() == "Cut")
    if p is not None:
        ui.choose(p.operation, "Intersect")


p4_intersect.wait_ms = 1500


def p4_intersect_ok():
    h.check("P4 Intersect: the half sphere", near(vol(), HALF, 1e-5), vol())
    h.task_button("OK")


def p4_undo1():
    h.press("z", QtCore.Qt.ControlModifier)


p4_undo1.wait_ms = 1200


def p4_undo2():
    h.check("P4 Ctrl+Z: the Cut again", near(vol(), 18750.0 - HALF, 1e-5), vol())
    h.press("z", QtCore.Qt.ControlModifier)


p4_undo2.wait_ms = 1200


def p4_redo1():
    h.check("P4 Ctrl+Z: the Join again", near(vol(), 18750.0 + HALF, 1e-5), vol())
    h.press("y", QtCore.Qt.ControlModifier)


p4_redo1.wait_ms = 1200


def p4_redo2():
    h.check("P4 Ctrl+Y: Cut", near(vol(), 18750.0 - HALF, 1e-5), vol())
    h.press("y", QtCore.Qt.ControlModifier)


p4_redo2.wait_ms = 1200


def p4_noop_edit():
    h.check("P4 Ctrl+Y: Intersect", near(vol(), HALF, 1e-5), vol())
    h.check("P4 double-click Sphere 1", ui.double_click_timeline("Sphere 1"))


def p4_noop_ok():
    p = pi.panel("SpherePanel")
    h.check("P4 editing the Intersect", p is not None and p.operation.currentText() == "Intersect")
    h.task_button("OK")


def p4_noop_undo():
    h.check("P4 unchanged", near(vol(), HALF, 1e-5), vol())
    h.press("z", QtCore.Qt.ControlModifier)


p4_noop_undo.wait_ms = 1200


def p4_end():
    h.check(
        "P4 an unchanged edit added no undo step: Ctrl+Z gives the Cut",
        near(vol(), 18750.0 - HALF, 1e-5),
        vol(),
    )
    h.press("y", QtCore.Qt.ControlModifier)


p4_end.wait_ms = 1200


def p4_redo_kept():
    h.check("P4 the redo list survived", near(vol(), HALF, 1e-5), vol())
    h.shot("p4")


h.run(
    "primitives_qa_paths",
    [
        new_design,
        p1_ok_first,
        p1_ok_refused,
        p1_corner,
        p1_rubber,
        p1_esc,
        p1_nothing_left,
        p1_plane,
        p1_corner_again,
        p1_type_length,
        p1_mouse_moves,
        p1_length_kept,
        p1_placed,
        p1_typo,
        p1_typo_ok,
        p1_zero,
        p1_zero_said,
        p1_zero_ok,
        p1_ok,
        p1_kept,
        p1_undone,
        p1_redone,
        p2_select_top,
        p2_cylinder,
        p2_centre,
        p2_circle,
        p2_height_live,
        p2_follows,
        p2_unknown,
        p2_waits,
        p2_d8,
        p2_both,
        p2_done,
        p3_new,
        p3_plane,
        p3_c1,
        p3_c2,
        p3_length_negative,
        p3_flipped,
        p3_width,
        p3_height,
        p3_kept,
        p4_sphere,
        p4_plane,
        p4_centre,
        p4_size,
        p4_ok,
        p4_edit_cut,
        p4_cut,
        p4_cut_ok,
        p4_edit_intersect,
        p4_intersect,
        p4_intersect_ok,
        p4_undo1,
        p4_undo2,
        p4_redo1,
        p4_redo2,
        p4_noop_edit,
        p4_noop_ok,
        p4_noop_undo,
        p4_end,
        p4_redo_kept,
    ],
)
