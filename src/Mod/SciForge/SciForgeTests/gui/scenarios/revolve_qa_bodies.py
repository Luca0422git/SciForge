# SPDX-License-Identifier: LGPL-2.1-or-later
"""Revolve: new bodies, Intersect after reopening, formulas through undo, an edge-on drag
(QA, only real input).

The part: Create Sketch on XY, R, a 40 x 30 rectangle from the origin, E, OK (10 high).

Path 18, New Body, then edited to Join: Create Sketch on the front face, a 6 x 4
         rectangle hanging from the top front edge; Revolve about that edge, New Body: a
         second body. Double-click it in the timeline, Join, OK: one body again (the new
         body goes). Ctrl+Z: two bodies; Ctrl+Y: one.
Path 19, the angle handle dragged in a view that looks along the circle it moves on
         (front view of a turn about an X-direction edge): the drag still turns it.
Path 20, Intersect: the front face turned a full turn about the bottom front edge keeps
         the quarter round inside the block. Save, close, reopen, edit it (Intersect is
         shown), 45, OK.
Path 21, a parameter in the angle of the first revolve: Ctrl+Z / Ctrl+Y, then the
         parameter changes: the revolve still follows it.
Path 22, a number typed with the mouse over the 3D view (Fusion types it into the value
         box next to the handle): 4, 5, Enter gives 45 and OK; the view does not jump
         (FreeCAD's 4 and 5 are view keys).
"""

import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import arrow_input as arrows
from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import revolve_input as ri
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import timeline_input as ti

V = App.Vector
PI = math.pi
BLOCK = 12000.0
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


def bodies():
    return doc().findObjects("PartDesign::Body")


def total():
    return sum(x.Shape.Volume for x in bodies() if not x.Shape.isNull())


def first():
    return doc().getObject(s["body"])


def first_vol():
    return first().Shape.Volume


def invalid():
    return [o.Label for o in doc().Objects if "Invalid" in o.State]


def revolve_titles():
    return [t for t in b.timeline_titles() if t.startswith("Revolve")]


# == the block =====================================================================================
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("RevolveQABodies")
    h.fit()
    h.ribbon("Create Sketch")


def block_plane():
    pl.click_on_plane(V(12, -8, 0))


def block_rect():
    h.press("r")


def block_corner():
    si.click(V(0, 0, 0))


def block_size():
    si.move_towards(V(12, 9, 0), V(0.8, 0.6, 0))
    si.type_text("40", enter=False)
    si.tab()
    si.type_text("30")


def block_finish():
    esc()
    h.ribbon("Finish Sketch")


def block_extrude():
    h.fit()
    h.press("e")


def block_ok():
    arrows.type_distance("10")  # Extrude starts at 0 (Fusion): type the distance
    h.task_button("OK")


# == Path 18: New Body, edited to Join =============================================================
def p18_sketch():
    h.check("block 40 x 30 x 10", near(h.solid_volume(), BLOCK), h.solid_volume())
    s["body"] = h.body().Name
    h.fit()
    h.click_empty()
    h.ribbon("Create Sketch")


def p18_face():
    h.click(V(30, 0, 5))  # the front face


def p18_rect():
    s["sk"] = h.in_sketch()
    h.check("P18 sketch on the front face", s["sk"] is not None)
    h.press("r")


def p18_corner():
    si.click(V(5, 0, 10), approach=V(1.0, 0, -0.6))


def p18_size():
    si.move_towards(V(9, 0, 7), V(0.8, 0, -0.6))
    si.type_text("6", enter=False)
    si.tab()
    si.type_text("4")


def p18_finish():
    esc()
    h.ribbon("Finish Sketch")


def p18_revolve():
    # (the face's edges are projected (Auto project): the rest of the front face is an
    # area too; Revolve takes the drawn rectangle by itself)
    areas = ri.taken(s["sk"])
    h.check("P18 one area", len(areas) == 1, areas)
    if areas:
        s["ring"] = ri.pappus(areas[0][1], V(0, 0, 10), V(1, 0, 0))
    h.fit()
    h.ribbon("Revolve")


def p18_axis():
    h.fit()
    h.click_edge(V(30, 0, 10))  # the top front edge


def p18_new_body():
    p = panel()
    h.check("P18 the top front edge is the axis", p is not None and p.axis is not None)
    if p is not None:
        b.choose(p.operation, "New Body")


def p18_ok():
    h.check("P18 New Body: the whole ring", near(total(), BLOCK + s["ring"]), total())
    h.check("P18 no warning", "⚠" not in msg(), msg())
    h.task_button("OK")


def p18_made():
    h.check("P18 two bodies", len(bodies()) == 2, bodies())
    h.check("P18 the block is unchanged", near(first_vol(), BLOCK), first_vol())
    h.check("P18 the ring is a body of its own", near(total(), BLOCK + s["ring"]), total())
    s["title"] = revolve_titles()[-1] if revolve_titles() else "Revolve 1"
    b.timeline_double_click(s["title"], click_first=True)


def p18_editing():
    p = panel()
    h.check("P18 editing the new-body revolve", p is not None and p.editing)
    if p is None:
        return
    h.check("P18 New Body is shown", p.operation.currentText() == "New Body")
    h.check("P18 the profile and the axis are shown", len(p.profiles) == 1 and p.axis is not None)
    b.choose(p.operation, "Join")


def p18_join_ok():
    want = BLOCK + s["ring"] * 0.75
    h.check("P18 Join: three quarters stick out of the block", near(total(), want), total())
    h.check("P18 no warning", "⚠" not in msg(), msg())
    h.task_button("OK")


def p18_joined():
    want = BLOCK + s["ring"] * 0.75
    h.check("P18 one body again", len(bodies()) == 1, bodies())
    h.check("P18 joined to the block", near(first_vol(), want), (first_vol(), want))
    h.check("P18 nothing broken", not invalid(), invalid())
    ti.ctrl("z")


def p18_undone():
    h.check("P18 Ctrl+Z: two bodies again", len(bodies()) == 2, bodies())
    h.check("P18 the block alone again", near(first_vol(), BLOCK), first_vol())
    ti.ctrl("y")


def p18_redone():
    want = BLOCK + s["ring"] * 0.75
    h.check("P18 Ctrl+Y: one body", len(bodies()) == 1, bodies())
    h.check("P18 joined again", near(first_vol(), want), first_vol())
    h.check("P18 nothing broken", not invalid(), invalid())
    s["v18"] = first_vol()


# == Path 19: an edge-on drag =========================================================================
def p19_edit():
    b.timeline_double_click(s["title"], click_first=True)


def p19_angle():
    p = panel()
    h.check("P19 editing", p is not None and p.editing)
    if p is not None:
        ui.type_into(p.angle.widget, "-90")


def p19_front():
    p = panel()
    out, into = BLOCK + s["ring"] / 4.0, BLOCK
    v = first_vol()
    h.check("P19 -90: a quarter turn (out of or into the block)", near(v, out) or near(v, into), v)
    # The user turns the view to Front (the ViewCube): the circle the handle moves on is
    # then seen edge-on.
    h.view().viewFront()
    h.view().fitAll()
    QtWidgets.QApplication.processEvents()
    handle = p.handles.get("angle") if p else None
    h.check("P19 the handle is there", handle is not None)
    if handle is None:
        return
    s["a19"] = p.angle.value()
    start = ri.handle_screen(handle)
    tip = h.screen_point(handle.point_at(handle.angle()) + handle._tangent(handle.angle()) * 5)
    dx, dy = tip.x() - start.x(), tip.y() - start.y()
    length = max(1.0, math.hypot(dx, dy))
    end = QtCore.QPoint(int(start.x() + dx / length * 60), int(start.y() + dy / length * 60))
    s["drag19"] = (start, end)
    h.drag(start, end, steps=12)


p19_front.wait_ms = 1500


def p19_dragged():
    p = panel()
    if p is None:
        h.check("P19 dialog open", False)
        return
    a = p.angle.value()
    h.check("P19 the edge-on drag turned the handle", abs(a - s["a19"]) > 5.0, (a, s["a19"]))
    h.check("P19 no warning", "⚠" not in msg(), msg())
    h.shot("p19-edge-on")
    esc()


def p19_esc():
    h.check("P19 Esc keeps the revolve as it was", near(first_vol(), s["v18"]), first_vol())
    h.fit()


# == Path 20: Intersect, save, reopen, edit ===========================================================
def p20_revolve():
    s["v20"] = first_vol()
    h.fit()
    h.click_empty()
    h.ribbon("Revolve")


def p20_face():
    h.fit()
    h.click(V(30, 0, 4))  # the front face, away from the round


def p20_edge():
    p = panel()
    h.check(
        "P20 the front face is the profile",
        p is not None and len(p.profiles) == 1 and p.profiles[0][1].startswith("Face"),
        p and p.profiles,
    )
    h.click_edge(V(35, 0, 0))  # its bottom edge


def p20_intersect():
    p = panel()
    h.check("P20 the bottom front edge is the axis", p is not None and p.axis is not None)
    if p is not None:
        b.choose(p.operation, "Intersect")


def p20_ok():
    # the front face turned a full turn about its bottom edge: the block keeps what lies
    # inside that round bar
    h.check("P20 no warning", "⚠" not in msg(), msg())
    h.check("P20 Intersect keeps a part of the block", 0 < first_vol() < s["v20"], first_vol())
    s["v20i"] = first_vol()
    h.shot("p20-intersect")
    h.task_button("OK")


def p20_saved():
    h.check("P20 kept", not dialog_open() and near(first_vol(), s["v20i"]), first_vol())
    from sciforge import revolve

    h.check("P20 an Intersect revolve", any(revolve.is_intersect(o) for o in ri.revolves()))
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-revolve-qa-"), "bodies.FCStd")
    s["path"] = path
    doc().saveAs(path)
    App.closeDocument(doc().Name)


def p20_open():
    App.openDocument(s["path"])
    h.fit()


def p20_reopened():
    h.check("P20 reopened: the same part", near(first_vol(), s["v20i"]), first_vol())
    h.check("P20 nothing broken", not invalid(), invalid())
    titles = revolve_titles()
    h.check("P20 two revolves in the timeline", len(titles) == 2, b.timeline_titles())
    s["t20"] = titles[-1] if titles else "Revolve 2"
    b.timeline_double_click(s["t20"], click_first=True)


def p20_editing():
    p = panel()
    h.check("P20 editing the Intersect after reopening", p is not None and p.editing)
    if p is None:
        return
    h.check("P20 Intersect is shown", p.operation.currentText() == "Intersect")
    h.check("P20 360 is shown", near(p.angle.value(), 360.0), p.angle.value())
    h.check("P20 no warning", "⚠" not in msg(), msg())
    ui.type_into(p.angle.widget, "45")


def p20_45():
    p = panel()
    if "overlap" in msg():
        # 45 turned away from the block: Intersect would keep nothing, which the dialog
        # says (Fusion too); the other way round then
        h.check("P20 the dialog says why", "Intersect would leave nothing" in msg(), msg())
        ui.type_into(p.angle.widget, "-45")


def p20_45_ok():
    v = first_vol()
    h.check("P20 45 keeps less of the block", 0 < v < s["v20i"], (v, s["v20i"]))
    h.check("P20 no warning", "⚠" not in msg(), msg())
    s["v20e"] = v
    h.task_button("OK")


def p20_done():
    h.check("P20 kept", not dialog_open() and near(first_vol(), s["v20e"]), first_vol())
    h.check("P20 nothing broken", not invalid(), invalid())


# == Path 21: a parameter, undo / redo, the parameter changes ======================================
def p21_parameter():
    from sciforge import parameters

    # Change Parameters (its own dialog) made this user parameter:
    parameters.add_user(doc(), "turn", "deg", "360")
    doc().recompute()
    titles = revolve_titles()
    s["t21"] = titles[0] if titles else "Revolve 1"
    b.timeline_double_click(s["t21"], click_first=True)


def p21_type():
    p = panel()
    h.check("P21 editing the first revolve", p is not None and p.editing)
    if p is not None:
        ui.type_into(p.angle.widget, "turn / 4")


def p21_ok():
    p = panel()
    h.check("P21 'turn / 4' is 90", p is not None and near(p.angle.value(), 90.0), p.angle.value())
    h.check("P21 the formula is listed", p is not None and "turn / 4" in p.formulas.text())
    s["v21"] = first_vol()
    rev = ti.obj(s["t21"])
    s["r21"] = rev.Shape.Volume if rev is not None else None
    h.task_button("OK")


def p21_undo():
    h.check("P21 kept", not dialog_open() and near(first_vol(), s["v21"]), first_vol())
    ti.ctrl("z")


def p21_redo():
    ti.ctrl("y")


def p21_change():
    h.check("P21 Ctrl+Y: the formula is back", near(first_vol(), s["v21"]), first_vol())
    from sciforge import parameters

    # in Change Parameters (an angle parameter stays within one turn in FreeCAD)
    parameters.set_user(doc(), "turn", "200")
    doc().recompute()


def p21_followed():
    rev = ti.obj(s["t21"])
    h.check(
        "P21 the revolve was rebuilt after the parameter changed",
        rev is not None and "Up-to-date" in rev.State,
        rev and rev.State,
    )
    angle = rev.Angle.Value if rev is not None else None
    h.check("P21 its angle is turn / 4 = 50", angle is not None and near(angle, 50.0), angle)
    h.check("P21 nothing broken", not invalid(), invalid())
    h.shot("p21-end")


# == Path 22: a number typed over the 3D view ===============================================
def p22_edit():
    s["v22"] = first_vol()
    b.timeline_double_click(s["t21"], click_first=True)


def p22_type():
    p = panel()
    h.check("P22 editing", p is not None and p.editing)
    h.fit()
    h.click_empty()  # the mouse is over the 3D view
    s["camera"] = h.view().getCameraOrientation()
    h.press("4")  # the first key, with the keyboard on the 3D view
    si.key("5")  # the next ones go where the keyboard now is
    p = panel()
    # The digits go into the angle handle's value box (Fusion's box next to the handle);
    # the dialog's field takes the value on Enter, which is OK as well.
    box = p.value_boxes.current() if p is not None else None
    typed = box.text().strip() if box is not None and box.hasFocus() else None
    h.check(
        "P22 the typed number is in the angle handle's box",
        box is not None and box is p.value_boxes.boxes.get("angle") and typed == "45",
        (typed, p and sorted(p.value_boxes.shown())),
    )
    si.key(QtCore.Qt.Key_Return)


def p22_done():
    h.check("P22 Enter finished the edit", not dialog_open())
    rev = ti.obj(s["t21"])
    angle = rev.Angle.Value if rev is not None else None
    h.check("P22 the angle is 45", angle is not None and near(angle, 45.0), angle)
    same = h.view().getCameraOrientation().isSame(s["camera"], 1e-9)
    h.check("P22 the view did not jump (no view key fired)", same)
    h.check("P22 nothing broken", not invalid(), invalid())


STEPS = [
    new_design,
    block_plane,
    block_rect,
    block_corner,
    block_size,
    block_finish,
    block_extrude,
    block_ok,
    p18_sketch,
    p18_face,
    p18_rect,
    p18_corner,
    p18_size,
    p18_finish,
    p18_revolve,
    p18_axis,
    p18_new_body,
    p18_ok,
    p18_made,
    p18_editing,
    p18_join_ok,
    p18_joined,
    p18_undone,
    p18_redone,
    p19_edit,
    p19_angle,
    p19_front,
    p19_dragged,
    p19_esc,
    p20_revolve,
    p20_face,
    p20_edge,
    p20_intersect,
    p20_ok,
    p20_saved,
    p20_open,
    p20_reopened,
    p20_editing,
    p20_45,
    p20_45_ok,
    p20_done,
    p21_parameter,
    p21_type,
    p21_ok,
    p21_undo,
    p21_redo,
    p21_change,
    p21_followed,
    p22_edit,
    p22_type,
    p22_done,
]

h.run("revolve_qa_bodies", ti.watched(STEPS))
