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
    h.click(V(15, -15, 0))


def a_corner():
    h.click(V(0, 0, 0))


def a_corner2():
    h.click(V(10, 10, 0))


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
    h.click(V(-15, -15, 0))


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
    # the XZ square, left of the part (nothing in front of it there)
    h.click(V(-20, 0, 10))


def d_coil_centre():
    p = pi.panel("CoilPanel")
    h.check("XZ picked", p is not None and p.plane_field.button.text() == "XZ Plane", p and p.state)
    h.click(V(-80, 0, 0))


def d_coil_circle():
    h.click(V(-70, 0, 0))


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
    ui.type_into(p.revolutions, "3")


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
    h.check("d4: 40 pi + the coil", near(vol(), 40.0 * PI + 54.0 * PI * PI, 1e-5), vol())
    h.task_button("OK")


d_pipe_edit_ok.wait_ms = 1500


def d_delete_pipe():
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
    ],
)
