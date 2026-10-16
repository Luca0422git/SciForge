# SPDX-License-Identifier: LGPL-2.1-or-later
"""Value boxes beside the handles that had none: Move's triad, Scale's arrow, Draft's angle
disc (Fusion shows the value beside every manipulator; docs/sciforge/parity/
extrude-presspull.md). Only real input.

Box 40 x 30 x 10 from the origin (12000).

A  M, click the body: the triad, no box yet. The mouse over the X arrow: a box beside it
   with X Distance's text (0 mm), not over the arrow, no keyboard taken. Drag the X arrow:
   the box follows it and shows the dragged distance. Click the box, type 25, Enter: X
   Distance 25, the body at x 25..65.
B  The mouse over the Z arrow: the box moves beside it and shows Z Distance. Digits typed
   over the view (1, 2, Enter) go into it: the body at z 12..22.
C  The mouse over the Z turn handle: the box shows Z Angle; 90 typed in it and Enter (the
   value and OK, as in Fusion): one Move step, the body turned (30 across in X, 40 in Y).
   Ctrl+Z puts the body back, Ctrl+Y moves it again. (A, B, D, E leave the box with Tab.)
D  Scale, click the body: the box beside the arrow shows the factor (1); 2 typed in it:
   the part is 8 times the volume. Esc: the part as it was, no box left.
E  Draft (MODIFY), click the XY square, click the front face: the angle disc with its box
   (1 deg); 5 typed in it: the front face drafted 5 deg. Cancel: as it was.
F  INSERT > Insert Mesh (a 20 x 10 x 5 STL): its manipulator is Move's triad; the mouse over
   the Z arrow: a box beside it with Z Distance's text; 7 typed in it: the mesh at z 7 and
   the field says so. Cancel: no mesh body, no box left.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import arrow_input as a
from SciForgeTests.gui import bodies_steps as bs
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as ins
from SciForgeTests.gui import shell_draft_steps as sd

V = App.Vector
s = {}
BOX = 12000.0
TOP = V(20, 15, 10)
FRONT = V(20, 0, 5)
XY_SQUARE = V(12, -8, 0)


def panel():
    from sciforge import taskui

    return taskui.current()


def body():
    return bs.bodies()[0]


def bbox():
    return body().Shape.BoundBox


def close(a_, b_, tol=1e-3):
    return abs(a_ - b_) <= tol * max(1.0, abs(b_))


def shown_boxes():
    return a.value_boxes()


def hover(point):
    h.uncover(point)  # the dialog floats over the right of the view: pan, as a person does
    pos = h.screen_point(point)
    h.move(pos)
    QtTest.QTest.qWait(60)
    h.move(QtCore.QPoint(pos.x() + 1, pos.y()))


def box_beside(box, handle):
    """(ok, detail): shown, beside the handle's grabbable part, not over it."""
    anchor, tail, tip, _r = handle.box_geometry()
    over = []
    for name, point in (("tail", tail), ("middle", anchor), ("tip", tip)):
        pos = h.screen_point(point)
        if a.top_name(pos) == a.BOX_NAME:
            over.append(name)
    centre = box.geometry().center()
    mid = h.screen_point(anchor)
    gap = (centre - mid).manhattanLength()
    return box.isVisible() and not over and gap < 260, (over, gap)


def type_and_leave(box, text):
    """Type into a box and leave it with Tab: the value is taken (Enter would also finish the
    command, as Fusion's Enter in the box does)."""
    a.type_in_box(box, text, enter=False)
    QtTest.QTest.keyClick(box, QtCore.Qt.Key_Tab)
    QtWidgets.QApplication.processEvents()


def wait_preview():
    QtTest.QTest.qWait(400)
    while getattr(App.ActiveDocument, "Recomputing", False):
        QtTest.QTest.qWait(50)


# -- A: Move's X arrow ----
def a_m():
    h.click_empty()
    h.fit()
    h.press("m")


def a_click_body():
    h.click(TOP)


def a_no_box_yet():
    p = panel()
    triad = getattr(p, "triad", None)
    h.check("A the triad is shown", triad is not None)
    h.check("A no value box before a handle is used", not shown_boxes(), shown_boxes())
    if triad is not None:
        s["size"] = triad.size
        hover(triad.center + V(1, 0, 0) * (0.6 * triad.size))


a_no_box_yet.wait_ms = 500


def a_x_box():
    p = panel()
    triad = p.triad
    box = a.value_box("move0", p)
    h.check(
        "A the mouse over the X arrow: its box",
        box is not None and box.isVisible(),
        p and sorted(p.value_boxes.boxes),
    )
    if box is None:
        return
    h.check(
        "A it shows X Distance",
        box.text() == p.distance_fields[0].widget.text(),
        (box.text(), p.distance_fields[0].widget.text()),
    )
    ok, detail = box_beside(box, triad)
    h.check("A beside the X arrow, not over it", ok, detail)
    h.check("A the box does not take the keyboard", not box.hasFocus(), a.focus_name())
    h.shot("A-x-box")
    start = triad.center + V(1, 0, 0) * (0.75 * triad.size)
    h.drag(h.screen_point(start), h.screen_point(start + V(10, 0, 0)))


def a_dragged():
    p = panel()
    box = a.value_box("move0", p)
    dx = p.options["dx"]
    h.check("A the drag moved the body along X", dx > 3.0, dx)
    h.check(
        "A the box shows the dragged distance",
        box is not None and box.text() == p.distance_fields[0].widget.text(),
        box and box.text(),
    )
    ok, detail = box_beside(box, p.triad)
    h.check("A the box followed the arrow", ok, detail)
    type_and_leave(box, "25")


def a_typed():
    wait_preview()
    p = panel()
    h.check("A X Distance 25", close(p.options["dx"], 25.0), p.options["dx"])
    bb = bbox()
    h.check(
        "A the body at x 25..65", close(bb.XMin, 25.0) and close(bb.XMax, 65.0), (bb.XMin, bb.XMax)
    )
    hover(p.triad.center + V(0, 0, 1) * (0.6 * p.triad.size))


a_typed.wait_ms = 500


# -- B: the Z arrow, digits typed over the view ----
def b_z_box():
    p = panel()
    box = a.value_box("move2", p)
    h.check(
        "B the mouse over the Z arrow: its box",
        box is not None and box.isVisible(),
        sorted(p.value_boxes.boxes),
    )
    x_box = a.value_box("move0", p)
    h.check("B the X box stepped aside (one box at a time)", x_box is None or not x_box.isVisible())
    if box is None:
        return
    h.check(
        "B it shows Z Distance",
        box.text() == p.distance_fields[2].widget.text(),
        (box.text(), p.distance_fields[2].widget.text()),
    )
    ok, detail = box_beside(box, p.triad)
    h.check("B beside the Z arrow", ok, detail)
    # The first digit arrives at the 3D view and goes into the box, which takes the
    # keyboard; a person's next keys then reach the box itself.
    QtTest.QTest.keyClick(h.gl_widget(), QtCore.Qt.Key_1)
    QtTest.QTest.qWait(80)
    focus = QtWidgets.QApplication.focusWidget() or h.gl_widget()
    QtTest.QTest.keyClick(focus, QtCore.Qt.Key_2)
    QtWidgets.QApplication.processEvents()


def b_enter():
    box = a.value_box("move2", panel())
    h.check(
        "B the digits went into the Z box",
        box is not None and box.text().startswith("12"),
        box and box.text(),
    )
    h.check(
        "B the box took the keyboard for them", box is not None and box.hasFocus(), a.focus_name()
    )
    if box is not None:
        QtTest.QTest.keyClick(box, QtCore.Qt.Key_Tab)
        QtWidgets.QApplication.processEvents()


def b_moved():
    wait_preview()
    p = panel()
    h.check("B Z Distance 12", close(p.options["dz"], 12.0), p.options["dz"])
    bb = bbox()
    h.check(
        "B the body at z 12..22", close(bb.ZMin, 12.0) and close(bb.ZMax, 22.0), (bb.ZMin, bb.ZMax)
    )
    hover(p.triad.ball_point(2))


b_moved.wait_ms = 500


# -- C: the Z turn handle ----
def c_turn_box():
    p = panel()
    box = a.value_box("turn2", p)
    t = p.triad
    pos = h.screen_point(t.ball_point(2))
    h.check(
        "C the mouse over the Z turn handle: its box",
        box is not None and box.isVisible(),
        (sorted(p.value_boxes.boxes), "in use", t.in_use, "on top", a.top_name(pos)),
    )
    if box is None:
        return
    h.check(
        "C it shows Z Angle",
        box.text() == p.angle_fields[2].widget.text(),
        (box.text(), p.angle_fields[2].widget.text()),
    )
    h.check("C in degrees", box.text().strip().endswith("°"), box.text())
    h.shot("C-turn-box")
    a.type_in_box(box, "90")  # Enter in the box: the value, and OK (as in Fusion)


def c_turned():
    wait_preview()
    h.check("C Enter in the box finished the Move", panel() is None)
    bb = bbox()
    h.check(
        "C the body turned: 30 across in X, 40 in Y",
        close(bb.XLength, 30.0) and close(bb.YLength, 40.0),
        (bb.XLength, bb.YLength),
    )
    h.check("C still at z 12..22", close(bb.ZMin, 12.0), bb.ZMin)


def c_ok():
    h.check("C one Move step", len(bs.steps_of_kind("MoveCopy")) == 1, bs.steps_of_kind("MoveCopy"))
    h.check("C no value box left", not shown_boxes(), shown_boxes())
    bs.undo()


def c_undone():
    bb = bbox()
    h.check(
        "C Ctrl+Z: the body back at the origin",
        close(bb.XMin, 0.0) and close(bb.ZMin, 0.0),
        (bb.XMin, bb.ZMin),
    )
    bs.redo()


def c_redone():
    bb = bbox()
    h.check(
        "C Ctrl+Y: moved and turned again",
        close(bb.ZMin, 12.0) and close(bb.XLength, 30.0),
        (bb.ZMin, bb.XLength),
    )
    bs.undo()  # the Scale and the Draft below work on the box at the origin


# -- D: Scale's arrow ----
def d_scale():
    Gui.Selection.clearSelection()
    h.fit()
    h.ribbon("Scale")


def d_click():
    h.click(TOP)


def d_box():
    p = sd.scale_panel()
    h.check("D the Scale arrow", p is not None and len(p.arrows) == 1)
    if p is None or not p.arrows:
        return
    box = a.value_box("factor", p)
    h.check(
        "D a box beside the arrow", box is not None and box.isVisible(), sorted(p.value_boxes.boxes)
    )
    if box is None:
        return
    h.check(
        "D it shows the Scale Factor",
        box.text() == p.factor.widget.text(),
        (box.text(), p.factor.widget.text()),
    )
    dragger = p.arrows[0][0]
    ok, detail = box_beside(box, dragger)
    h.check("D not over the arrow", ok, detail)
    h.shot("D-scale-box")
    type_and_leave(box, "2")


def d_scaled():
    wait_preview()
    p = sd.scale_panel()
    h.check(
        "D Scale Factor 2", p is not None and close(p.factor.value(), 2.0), p and p.factor.value()
    )
    v = h.solid_volume()
    h.check("D the part is 8 times the volume", close(v, BOX * 8), v)
    h.press(QtCore.Qt.Key_Escape)


def d_cancelled():
    h.check("D Esc closed the dialog", sd.scale_panel() is None or sd.scale_panel()._closed)
    h.check("D the part as it was", close(h.solid_volume(), BOX), h.solid_volume())
    h.check("D no value box left", not shown_boxes(), shown_boxes())


# -- E: Draft's angle disc ----
def e_draft():
    Gui.Selection.clearSelection()
    sd.modify_menu("Draft")


def e_xy():
    h.fit()
    h.click(XY_SQUARE)


def e_front():
    h.fit()
    h.click(FRONT)


def e_box():
    p = sd.draft_panel()
    h.check("E the angle disc", p is not None and p.handle is not None)
    if p is None or p.handle is None:
        return
    box = a.value_box("angle", p)
    h.check(
        "E a box beside the disc", box is not None and box.isVisible(), sorted(p.value_boxes.boxes)
    )
    if box is None:
        return
    h.check(
        "E it shows the draft Angle",
        box.text() == p.angle.widget.text(),
        (box.text(), p.angle.widget.text()),
    )
    ok, detail = box_beside(box, p.handle)
    h.check("E not over the disc", ok, detail)
    h.shot("E-draft-box")
    type_and_leave(box, "5")


def e_drafted():
    wait_preview()
    p = sd.draft_panel()
    h.check("E Angle 5", p is not None and close(p.angle.value(), 5.0), p and p.angle.value())
    expect = BOX - 40 * 100.0 * math.tan(math.radians(5)) / 2.0
    v = h.solid_volume()
    h.check("E the front face drafted 5 deg", close(v, expect), (v, expect))
    h.task_button("Cancel")


def e_cancelled():
    h.check("E Cancel: the part as it was", close(h.solid_volume(), BOX), h.solid_volume())
    h.check("E no Draft step", not sd.drafts(), sd.drafts())
    h.check("E no value box left", not shown_boxes(), shown_boxes())


# -- F: Insert Mesh's triad ----
def f_insert():
    Gui.Selection.clearSelection()
    ins.use_file(ins.fixture("box_20x10x5.stl"))
    h.fit()
    h.ribbon("Insert Mesh")


f_insert.wait_ms = 800


def f_hover():
    p = ins.panel()
    triad = getattr(p, "triad", None)
    h.check("F Insert Mesh with its manipulator", triad is not None, p)
    if triad is not None:
        hover(triad.center + V(0, 0, 1) * (0.6 * triad.size))


f_hover.wait_ms = 500


def f_box():
    p = ins.panel()
    triad = getattr(p, "triad", None)
    box = a.value_box("move2", p)
    h.check(
        "F the mouse over the Z arrow: its box",
        box is not None and box.isVisible(),
        p is not None and sorted(getattr(p, "value_boxes", None).boxes),
    )
    if box is None or triad is None:
        return
    h.check(
        "F it shows Z Distance", box.text() == p.z.widget.text(), (box.text(), p.z.widget.text())
    )
    ok, detail = box_beside(box, triad)
    h.check("F not over the arrow", ok, detail)
    h.shot("F-insert-mesh-box")
    type_and_leave(box, "7")


def f_moved():
    wait_preview()
    p = ins.panel()
    meshes = ins.mesh_bodies()
    z = meshes[0].Placement.Base.z if meshes else None
    h.check("F the mesh at z 7", z is not None and close(z, 7.0), z)
    h.check("F the Z Distance field says 7", p is not None and close(p.z.value(), 7.0))
    h.task_button("Cancel")


def f_cancelled():
    h.check("F Cancel: no mesh body", not ins.mesh_bodies(), ins.mesh_bodies())
    h.check("F no value box left", not shown_boxes(), shown_boxes())


STEPS = sd.box_steps("Polish2Boxes") + [
    a_m,
    a_click_body,
    a_no_box_yet,
    a_x_box,
    a_dragged,
    a_typed,
    b_z_box,
    b_enter,
    b_moved,
    c_turn_box,
    c_turned,
    c_ok,
    c_undone,
    c_redone,
    d_scale,
    d_click,
    d_box,
    d_scaled,
    d_cancelled,
    e_draft,
    e_xy,
    e_front,
    e_box,
    e_drafted,
    e_cancelled,
    f_insert,
    f_hover,
    f_box,
    f_moved,
    f_cancelled,
]

h.run("polish2_value_boxes", STEPS)
