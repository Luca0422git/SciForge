# SPDX-License-Identifier: LGPL-2.1-or-later
"""Primitives QA: what a Fusion user does besides the plain path, only real input.

A. A parameter in a field: user parameter w = 30 (Change Parameters made it); Box on XY
   10 x 10 x 10, type "w" as Length: 30 long; Enter (mouse over the 3D view) is OK;
   w = 40 in Change Parameters: the box follows.
B. Ctrl+Z inside a dialog cancels it (the preview goes, nothing else).
C. A Cylinder d6 h10 on the top face; editing the Box under it (height 20) carries the
   cylinder up; Sphere with a curved face clicked: said next to the dialog, still waiting;
   Esc. Editing the Cylinder, the Plane box clicked: the planes show again, XY clicked:
   the cylinder moves down onto XY (inside the box: nothing sticks out).
D. Pipe along the box's top front edge, Intersect (SciForge's own step); a Coil on XZ far
   away (a new body). Save, close, reopen: same volumes, no errors; edit the coil (3
   revolutions) and the pipe (section 4) after reopening. Delete the pipe and the coil in
   the timeline: their hidden helpers go too (a later dialog tidies what is left).
E. Parameters in the Torus and Coil fields (d = 20): torus inner 20, torus d "d / 4";
   edited to Outside; a coil (Height and Pitch) with height "d / 2", pitch 4. d = 60 in
   Change Parameters: both follow.
F. A parameter in the coil's Revolutions: edit the coil, type Revolution and Height (the
   same coil: 7.5 revolutions), Revolutions "n" (n = 3, no unit); OK; n = 5: the coil
   follows; editing again shows the formula; Esc keeps it.

Hand-derived volumes: box 30*10*10 = 3000, 40*10*10 = 4000, 40*10*20 = 8000;
cylinder d6 h10 = 90 pi; pipe d2 along a 40 mm edge, Intersect: a quarter tube 10 pi,
d4: 40 pi; coil d20 (section 2 inside, r9), 5 turns: 90 pi^2, 3 turns: 54 pi^2.
"""
import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import primitive_input as pi
from SciForgeTests.gui import timeline_input as ti

V = App.Vector
PI = math.pi
s = {}


def near(a, b, tol=1e-6):
    return pi.near(a, b, tol)


def vol():
    return pi.total_volume()


def doc():
    return App.ActiveDocument


# -- A: a parameter in a field, Enter ---------------------------------------------------------------
def new_design():
    from sciforge import parameters

    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("PrimQA")
    # Change Parameters (its own dialog) made this user parameter:
    parameters.add_user(doc(), "w", "mm", "30")
    doc().recompute()
    h.fit()
    pi.menu("Box")


def a_plane():
    pl.click_square("XY_Plane")  # where the XY square shows


def a_corner():
    pl.click_on_plane(V(0, 0, 0))


def a_corner2():
    pl.click_on_plane(V(10, 10, 0))


a_corner2.wait_ms = 1200


def a_formula():
    p = pi.panel("BoxPanel")
    h.check("10 x 10 x 10", near(vol(), 1000.0), vol())
    ui.type_into(p.length.widget, "w")


a_formula.wait_ms = 1200


def a_follows():
    p = pi.panel("BoxPanel")
    h.check("Length = w: 30", near(p.length.value(), 30.0) and near(vol(), 3000.0), vol())
    h.check("the formula is listed", "w" in p.formulas.text(), p.formulas.text())
    h.check("no error text", p.message.text() == "", p.message.text())
    h.press(QtCore.Qt.Key_Return)


def a_enter():
    h.check("Enter is OK", pi.no_dialog())
    h.check("kept", near(vol(), 3000.0), vol())
    box = pi.steps_of("AdditiveBox")[0]
    s["box"] = box
    h.check("the length follows w", "Length" in dict(box.ExpressionEngine), box.ExpressionEngine)
    from sciforge import parameters

    parameters.set_user(doc(), "w", "40")  # in Change Parameters
    doc().recompute()


def a_parameter_changed():
    h.check("w = 40: the box is 40 long", near(vol(), 4000.0), vol())
    h.fit()


# -- B: Ctrl+Z inside a dialog --------------------------------------------------------------------
def b_select_top():
    h.click(V(20, 5, 10))


def b_cylinder():
    pi.menu("Cylinder")


def b_centre():
    h.click(V(20, 5, 10))


def b_circle():
    h.click(V(23, 5, 10))


b_circle.wait_ms = 1200


def b_ctrl_z():
    p = pi.panel("CylinderPanel")
    h.check("a cylinder preview", p is not None and p.target is not None)
    s["count"] = len(doc().Objects)
    h.press("z", QtCore.Qt.ControlModifier)


b_ctrl_z.wait_ms = 1200


def b_undone():
    h.check("Ctrl+Z cancelled the dialog", pi.no_dialog())
    h.check("the box is as it was", near(vol(), 4000.0), vol())
    h.check("no cylinder left", not pi.steps_of("Cylinder"))
    h.check("the box is still there", s["box"].Document.getObject(s["box"].Name) is not None)


# -- C: a cylinder on the box, edits ------------------------------------------------------------------
def c_select_top():
    h.click(V(20, 5, 10))


def c_cylinder():
    pi.menu("Cylinder")


def c_centre():
    h.click(V(20, 5, 10))


def c_circle():
    h.click(V(23, 5, 10))


c_circle.wait_ms = 1200


def c_ok():
    p = pi.panel("CylinderPanel")
    h.check("d6 on top, Join", p is not None and p.operation.currentText() == "Join")
    h.check("cylinder d6 h10", near(vol(), 4000.0 + 90.0 * PI), vol())
    h.task_button("OK")


def c_edit_box():
    h.check("double-click Box 1", ui.double_click_timeline("Box 1"), ui.timeline_titles())


def c_box_taller():
    p = pi.panel("BoxPanel")
    h.check("editing the box", p is not None and p.editing)
    if p is None:
        return
    h.check("the length shows its formula", "w" in p.formulas.text(), p.formulas.text())
    ui.type_into(p.height.widget, "20")


def c_box_ok():
    h.task_button("OK")


def c_carried():
    h.check("box 20 high, the cylinder carried up", near(vol(), 8000.0 + 90.0 * PI), vol())
    zmax = pi.bbox(h.body().Shape)[5]
    h.check("the cylinder sits on the new top", near(zmax, 30.0), zmax)
    h.fit()


def c_sphere():
    h.click_empty()
    pi.menu("Sphere")


def c_curved():
    p = pi.panel("SpherePanel")
    h.check("Sphere waits for a plane", p is not None and p.state == "plane")
    h.click(V(20, 2, 25))  # the cylinder's round side


def c_refused():
    p = pi.panel("SpherePanel")
    h.check(
        "a curved face is refused in the dialog", "flat face" in p.message.text(), p.message.text()
    )
    h.check("still waiting for a plane", p.state == "plane")
    h.check("no pop-up", not h.popups(), h.popups())
    h.press(QtCore.Qt.Key_Escape)


def c_edit_cylinder():
    h.check("Esc closed it", pi.no_dialog())
    h.check("double-click Cylinder 1", ui.double_click_timeline("Cylinder 1"))


def c_replane():
    p = pi.panel("CylinderPanel")
    h.check("editing the cylinder", p is not None and p.editing)
    if p is None:
        return
    h.check("on the box's face", p.plane_field.button.text().startswith("Face of"))
    ui.click(p.plane_field.button)


def c_planes_shown():
    p = pi.panel("CylinderPanel")
    h.check("the planes show again", p.state == "replane" and p.planes is not None, p.state)
    # Where XY is in front: the squares are as big as the design, and from the iso view
    # (-15, -15, 0) lies behind the YZ square (the front square takes the click, as in
    # Fusion).
    pl.click_square("XY_Plane")  # where the XY square shows


c_planes_shown.wait_ms = 1500


def c_moved():
    p = pi.panel("CylinderPanel")
    h.check("now on XY", p.plane_field.button.text() == "XY Plane", p.plane_field.button.text())
    h.check("inside the box: nothing sticks out", near(vol(), 8000.0), vol())
    h.task_button("OK")


c_moved.wait_ms = 1500


def c_kept():
    h.check("kept", near(vol(), 8000.0), vol())
    cyl = pi.steps_of("AdditiveCylinder")[0]
    h.check(
        "the cylinder is attached to XY",
        cyl.AttachmentSupport[0][0].Role == "XY_Plane",
        cyl.AttachmentSupport,
    )
    h.fit()


# -- D: intersect pipe, coil in a new body, save / reopen, delete ------------------------------------
def d_edge():
    h.click_edge(V(20, 0, 20))


def d_pipe():
    h.check("the edge is selected", bool(Gui.Selection.getSelectionEx()), h.state.get("last_click"))
    pi.menu("Pipe")


d_pipe.wait_ms = 1500


def d_intersect():
    p = pi.pipe_panel()
    h.check("the edge taken", p is not None and len(p.path) == 1)
    if p is None:
        return
    ui.type_into(p.size.widget, "2")


d_intersect.wait_ms = 1500


def d_choose():
    h.check("Intersect", ui.choose(pi.pipe_panel().operation, "Intersect"))


d_choose.wait_ms = 1500


def d_pipe_ok():
    h.check("Intersect: a quarter tube", near(vol(), 10.0 * PI, 1e-5), vol())
    h.task_button("OK")


d_pipe_ok.wait_ms = 1500


def d_coil():
    h.check("SciForge's intersect step", len(pi.steps_of("FeaturePython")) == 1)
    s["pipe"] = vol()
    h.click_empty()
    pi.menu("Coil")


def d_coil_plane():
    p = pi.panel("CoilPanel")
    h.check("Coil waits", p is not None and p.state == "plane")
    # The XZ square above the part: nothing is in front of it there (left of the part, at
    # (-20, 0, 10), the YZ square is in front from the iso view since the squares are as big
    # as the design).
    pl.click_square("XZ_Plane")  # where the square shows (was 20, 0, 30)


def d_coil_centre():
    p = pi.panel("CoilPanel")
    h.check("XZ picked", p is not None and p.plane_field.button.text() == "XZ Plane", p and p.state)
    pl.click_on_plane(V(-80, 0, 0))


def d_coil_circle():
    pl.click_on_plane(V(-70, 0, 0))


d_coil_circle.wait_ms = 2500


def d_coil_ok():
    p = pi.panel("CoilPanel")
    h.check(
        "away from the part: New Body", p is not None and p.operation.currentText() == "New Body"
    )
    h.check("coil 90 pi^2", near(vol() - s["pipe"], 90.0 * PI * PI, 1e-5), vol())
    h.task_button("OK")


d_coil_ok.wait_ms = 2500


def d_save():
    s["volume"] = vol()
    s["bodies"] = len(pi.bodies())
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-prim-"), "primitives_qa.FCStd")
    s["path"] = path
    doc().saveAs(path)
    h.check("saved", os.path.isfile(path), path)


def d_close():
    App.closeDocument(doc().Name)


def d_open():
    App.openDocument(s["path"])
    h.fit()


d_open.wait_ms = 2500


def d_reopened():
    h.check("reopened: same volume", near(vol(), s["volume"], 1e-6), (vol(), s["volume"]))
    h.check("same bodies", len(pi.bodies()) == s["bodies"])
    doc().recompute()
    h.check("a recompute after reopening keeps it", near(vol(), s["volume"], 1e-6), vol())
    titles = ui.timeline_titles()
    h.check(
        "steps listed",
        all(t in titles for t in ("Box 1", "Cylinder 1", "Pipe 1", "Coil 1")),
        titles,
    )
    h.check("double-click Coil 1", ui.double_click_timeline("Coil 1"))


d_reopened.wait_ms = 2500


def d_coil_editing():
    p = pi.panel("CoilPanel")
    h.check("editing the coil after reopening", p is not None and p.editing)
    if p is None:
        return
    h.check("5 revolutions remembered", near(p.revolutions.value(), 5.0))
    ui.type_into(p.revolutions.widget, "3")


def d_coil_edit_ok():
    h.check("3 turns: 54 pi^2", near(vol() - s["pipe"], 54.0 * PI * PI, 1e-5), vol())
    h.task_button("OK")


d_coil_edit_ok.wait_ms = 2500


def d_pipe_edit():
    h.check("double-click Pipe 1", ui.double_click_timeline("Pipe 1"))


def d_pipe_editing():
    p = pi.pipe_panel()
    h.check("editing the pipe after reopening", p is not None and p.editing)
    if p is None:
        return
    h.check("Intersect remembered", p.operation.currentText() == "Intersect")
    ui.type_into(p.size.widget, "4")


d_pipe_editing.wait_ms = 1500


def d_pipe_edit_ok():
    # the coil (made after the pipe) waits while the pipe is edited (Fusion)
    h.check("d4: 40 pi", near(vol(), 40.0 * PI, 1e-5), vol())
    h.task_button("OK")


d_pipe_edit_ok.wait_ms = 1500


def d_delete_pipe():
    h.check("d4 kept: 40 pi + the coil", near(vol(), 40.0 * PI + 54.0 * PI * PI, 1e-5), vol())
    ti.menu("Pipe 1", "Delete")


d_delete_pipe.wait_ms = 1500


def d_pipe_deleted():
    h.check(
        "the pipe is gone: the box with its cylinder",
        near(vol(), 8000.0 + 54.0 * PI * PI, 1e-5),
        vol(),
    )
    h.check(
        "no pipe step", not [o for o in doc().Objects if getattr(o, "SciForgeType", "") == "Pipe"]
    )
    ti.menu("Coil 1", "Delete")


d_pipe_deleted.wait_ms = 1500


def d_coil_deleted():
    h.check("the coil is gone", near(vol(), 8000.0, 1e-6), vol())
    roles = [getattr(o, "SciForgeRole", "") for o in doc().Objects]
    h.check("the coil's section went with it", "CoilSection" not in roles, roles)
    h.check("the pipe's section went with it", "PipeSection" not in roles, roles)
    s["orphans"] = roles.count("PipePath")
    pi.menu("Box")


d_coil_deleted.wait_ms = 1500


def d_tidied():
    roles = [getattr(o, "SciForgeRole", "") for o in doc().Objects]
    h.check(
        "a new dialog tidies the pipe's left-over path",
        "PipePath" not in roles,
        (s["orphans"], roles),
    )
    h.press(QtCore.Qt.Key_Escape)


def d_end():
    h.check("Esc closed it", pi.no_dialog())
    h.check("still 8000", near(vol(), 8000.0), vol())
    h.shot("end")


# -- E: parameters in the Torus and Coil fields ----------------------------------------------------
def e_new():
    from sciforge import parameters

    App.newDocument("PrimQA2")
    parameters.add_user(doc(), "d", "mm", "20")
    doc().recompute()
    h.fit()
    pi.menu("Torus")


def e_plane():
    pl.click_square("XY_Plane")  # where the XY square shows


def e_centre():
    pl.click_on_plane(V(0, 0, 0))


def e_circle():
    pl.click_on_plane(V(10, 0, 0))


e_circle.wait_ms = 1500


def e_inner():
    p = pi.panel("TorusPanel")
    h.check("torus placed", p is not None and p.target is not None)
    ui.type_into(p.inner.widget, "d")


e_inner.wait_ms = 1500


def e_tube():
    ui.type_into(pi.panel("TorusPanel").tube.widget, "d / 4")


e_tube.wait_ms = 1500


def e_torus_ok():
    p = pi.panel("TorusPanel")
    h.check(
        "inner d = 20, torus d/4 = 5", near(p.inner.value(), 20.0) and near(p.tube.value(), 5.0)
    )
    h.check("R10 r2.5: 125 pi^2", near(vol(), 125.0 * PI * PI), vol())
    h.check("both formulas listed", p.formulas.text().count("= d") == 2, p.formulas.text())
    h.task_button("OK")


e_torus_ok.wait_ms = 1500


def e_d40():
    from sciforge import parameters

    parameters.set_user(doc(), "d", "40")  # in Change Parameters
    doc().recompute()


def e_torus_follows():
    h.check("d = 40: R20 r5, 1000 pi^2", near(vol(), 1000.0 * PI * PI), vol())
    h.check("double-click Torus 1", ui.double_click_timeline("Torus 1"))


def e_torus_editing():
    p = pi.panel("TorusPanel")
    h.check("editing the torus", p is not None and p.editing)
    if p is None:
        return
    h.check("shows the values d gives", near(p.inner.value(), 40.0) and near(p.tube.value(), 10.0))
    h.check("and the formulas", p.formulas.text().count("= d") == 2, p.formulas.text())
    h.check("Outside", ui.choose(p.position, "Outside"))


def e_torus_outside():
    h.check("Outside keeps the formulas: R25 r5", near(vol(), 1250.0 * PI * PI), vol())
    h.task_button("OK")


e_torus_outside.wait_ms = 1500


def e_torus_kept():
    s["torus"] = vol()
    h.click_empty()
    pi.menu("Coil")


def e_coil_plane():
    pl.click_square("XY_Plane")  # where the XY square shows


def e_coil_centre():
    p = pi.panel("CoilPanel")
    h.check("placing the coil", p is not None and p.state == "place", p and p.state)
    pl.click_on_plane(V(0, 0, 0))  # in the middle of the torus' hole


def e_coil_circle():
    pl.click_on_plane(V(10, 0, 0))


e_coil_circle.wait_ms = 2500


def e_coil_type():
    h.check("Height and Pitch", ui.choose(pi.panel("CoilPanel").type, "Height and Pitch"))


e_coil_type.wait_ms = 2000


def e_coil_height():
    p = pi.panel("CoilPanel")
    ui.type_into(p.pitch.widget, "4")


e_coil_height.wait_ms = 2000


def e_coil_formula():
    ui.type_into(pi.panel("CoilPanel").height.widget, "d / 2")


e_coil_formula.wait_ms = 2000


def e_coil_ok():
    p = pi.panel("CoilPanel")
    h.check(
        "height d/2 = 20, pitch 4: 5 turns, 90 pi^2", near(vol() - s["torus"], 90.0 * PI * PI, 1e-5)
    )
    h.task_button("OK")


e_coil_ok.wait_ms = 2500


def e_d60():
    from sciforge import parameters

    parameters.set_user(doc(), "d", "60")
    doc().recompute()


e_d60.wait_ms = 2500


def e_coil_follows():
    # torus: inner 60, section 15, Outside: R 37.5, r 7.5; coil: height 30, pitch 4: 7.5 turns
    torus = [
        b for b in pi.bodies() if b.Tip is not None and b.Tip.TypeId == "PartDesign::AdditiveTorus"
    ]
    h.check("the torus and the coil are two bodies", len(torus) == 1 and len(pi.bodies()) == 2)
    if not torus:
        return
    expected = 2.0 * PI * PI * 37.5 * 7.5 * 7.5
    h.check(
        "the torus follows d", near(torus[0].Shape.Volume, expected, 1e-6), torus[0].Shape.Volume
    )
    coil = vol() - torus[0].Shape.Volume
    h.check("the coil follows d: 7.5 turns", near(coil, 135.0 * PI * PI, 1e-5), coil)
    h.shot("formulas")


# -- F: a parameter in the coil's Revolutions ----------------------------------------------------
def coil_volume():
    torus = [
        b for b in pi.bodies() if b.Tip is not None and b.Tip.TypeId == "PartDesign::AdditiveTorus"
    ]
    return vol() - sum(b.Shape.Volume for b in torus)


def f_edit():
    from sciforge import parameters

    parameters.add_user(doc(), "n", "", "3")
    doc().recompute()
    h.check("double-click Coil 1", ui.double_click_timeline("Coil 1"))


f_edit.wait_ms = 2500


def f_type():
    p = pi.panel("CoilPanel")
    h.check("editing the coil", p is not None and p.editing)
    if p is None:
        return
    h.check("Revolution and Height", ui.choose(p.type, "Revolution and Height"))


f_type.wait_ms = 2000


def f_turns():
    p = pi.panel("CoilPanel")
    if p is None:
        return
    shown = p.revolutions.value()
    h.check("the same coil: 7.5 revolutions", near(shown, 7.5, 1e-3), shown)
    ui.type_into(p.revolutions.widget, "n")


f_turns.wait_ms = 2000


def f_ok():
    p = pi.panel("CoilPanel")
    if p is None:
        return
    h.check("Revolutions = n listed", "Revolutions = n" in p.formulas.text(), p.formulas.text())
    h.check("n = 3 revolutions", near(p.revolutions.value(), 3.0), p.revolutions.value())
    h.check("3 turns: 54 pi^2", near(coil_volume(), 54.0 * PI * PI, 1e-5), coil_volume())
    h.task_button("OK")


f_ok.wait_ms = 2500


def f_n5():
    from sciforge import parameters

    h.check("dialog closed", pi.no_dialog())
    parameters.set_user(doc(), "n", "5")
    doc().recompute()


f_n5.wait_ms = 2500


def f_follows():
    h.check("the coil follows n: 5 turns", near(coil_volume(), 90.0 * PI * PI, 1e-5), coil_volume())
    h.check("double-click Coil 1 again", ui.double_click_timeline("Coil 1"))


f_follows.wait_ms = 2500


def f_shown_again():
    p = pi.panel("CoilPanel")
    h.check("editing again", p is not None and p.editing)
    if p is None:
        return
    h.check("still Revolutions = n", "Revolutions = n" in p.formulas.text(), p.formulas.text())
    h.check("5 revolutions shown", near(p.revolutions.value(), 5.0), p.revolutions.value())
    h.press(QtCore.Qt.Key_Escape)


f_shown_again.wait_ms = 2000


def f_closed():
    h.check("Esc closed the dialog", pi.no_dialog())
    h.check("Esc kept the coil", near(coil_volume(), 90.0 * PI * PI, 1e-5), coil_volume())
    h.shot("revolutions")


h.run(
    "primitives_qa",
    [
        new_design,
        a_plane,
        a_corner,
        a_corner2,
        a_formula,
        a_follows,
        a_enter,
        a_parameter_changed,
        b_select_top,
        b_cylinder,
        b_centre,
        b_circle,
        b_ctrl_z,
        b_undone,
        c_select_top,
        c_cylinder,
        c_centre,
        c_circle,
        c_ok,
        c_edit_box,
        c_box_taller,
        c_box_ok,
        c_carried,
        c_sphere,
        c_curved,
        c_refused,
        c_edit_cylinder,
        c_replane,
        c_planes_shown,
        c_moved,
        c_kept,
        d_edge,
        d_pipe,
        d_intersect,
        d_choose,
        d_pipe_ok,
        d_coil,
        d_coil_plane,
        d_coil_centre,
        d_coil_circle,
        d_coil_ok,
        d_save,
        d_close,
        d_open,
        d_reopened,
        d_coil_editing,
        d_coil_edit_ok,
        d_pipe_edit,
        d_pipe_editing,
        d_pipe_edit_ok,
        d_delete_pipe,
        d_pipe_deleted,
        d_coil_deleted,
        d_tidied,
        d_end,
        e_new,
        e_plane,
        e_centre,
        e_circle,
        e_inner,
        e_tube,
        e_torus_ok,
        e_d40,
        e_torus_follows,
        e_torus_editing,
        e_torus_outside,
        e_torus_kept,
        e_coil_plane,
        e_coil_centre,
        e_coil_circle,
        e_coil_type,
        e_coil_height,
        e_coil_formula,
        e_coil_ok,
        e_d60,
        e_coil_follows,
        f_edit,
        f_type,
        f_turns,
        f_ok,
        f_n5,
        f_follows,
        f_shown_again,
        f_closed,
    ],
)
