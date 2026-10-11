# SPDX-License-Identifier: LGPL-2.1-or-later
"""Chamfer the way Fusion users really use it, trying to break it (QA, only real input).

Path 12, beginner and wrong values: Chamfer with nothing picked, OK (refused, says why),
         Esc; a 0 distance and impossible angles (0, 90 degrees: said in the dialog, OK
         refused, nothing in the Report view); Flip in Distance and Angle; Two Distances
         with the second arrow dragged back through the edge (it stops at its smallest and
         comes back to the value shown).
Path 13, edit twice from the timeline (type changed, an edge added), undo / redo, save,
         close, reopen, the chamfer opens as it was saved; Esc keeps it.
Path 14, a chamfer round a hole (a curved edge) after Create Sketch + Extrude cut, and F
         pressed while the Chamfer dialog is open (the chamfer is kept, Fillet starts empty).

Numbers by hand: 40 x 30 x 10 box; a chamfer with legs a, b along a straight edge of length
L removes L a b / 2; round a hole of radius R with legs d it removes d^2/2 * 2 pi (R + d/3).
"""
import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}
FRONT_TOP = V(20, 0, 10)
BACK_TOP = V(20, 30, 10)
HOLE_R = 4.0
HOLE_C = (20.0, 15.0)


def step(fn, name):
    fn.__name__ = name
    return fn


def doc():
    return App.ActiveDocument


def dialog_open():
    return bool(Gui.Control.activeDialog())


def picks():
    p = b.blend_panel()
    return list(p.refs) if p else None


def legs(a, c, length=40.0):
    return b.BOX - length * a * c / 2.0


def message():
    p = b.blend_panel()
    return p.message.text() if p else ""


def broken():
    return [o.Name for o in doc().Objects if "Invalid" in o.State or "Error" in o.State]


# -- Path 12: beginner, wrong values ---------------------------------------------------------
def p12_chamfer():
    h.click_empty()
    h.ribbon("Chamfer")


def p12_ok_empty():
    p = b.blend_panel()
    h.check("P12 Chamfer opens with nothing picked", p is not None and p.title == "Chamfer")
    h.task_button("OK")


def p12_refused():
    h.check("P12 OK with nothing picked keeps the dialog", dialog_open())
    h.check("P12 it says to pick edges", "select the edges" in message().lower(), message())
    h.press(QtCore.Qt.Key_Escape)


def p12_again():
    h.check("P12 Esc closed it", not dialog_open())
    h.check("P12 nothing made", not b.blends())
    h.ribbon("Chamfer")


def p12_pick():
    h.fit()
    h.click_edge(FRONT_TOP)


def p12_zero():
    p = b.blend_panel()
    h.check("P12 front edge picked", p is not None and len(p.refs) == 1, picks())
    if p:
        ui.type_into(p.distance.widget, "0")


def p12_zero_said():
    h.check("P12 a 0 distance is explained", "more than 0" in message(), message())
    h.task_button("OK")


def p12_zero_refused():
    h.check("P12 OK refused with a 0 distance", dialog_open())
    p = b.blend_panel()
    if p:
        ui.type_into(p.distance.widget, "2")
        b.choose(p.ctype, "Distance and Angle")


def p12_angle_zero():
    p = b.blend_panel()
    if p:
        ui.type_into(p.angle.widget, "0")


def p12_angle_zero_said():
    h.check("P12 a 0 degree angle is explained", "angle" in message().lower(), message())
    p = b.blend_panel()
    if p:
        ui.type_into(p.angle.widget, "90")


def p12_angle_90():
    text = message()
    h.check(
        "P12 90 degrees (the bevel never meets the face) is explained", "below 90" in text, text
    )
    h.check(
        "P12 nothing about it in the Report view",
        not b.report_has_kernel_errors(),
        b.report_has_kernel_errors(),
    )
    b.no_popups("an impossible chamfer angle")
    h.shot("p12-angle-90")
    h.task_button("OK")


def p12_angle_refused():
    h.check("P12 OK refused at 90 degrees", dialog_open())
    p = b.blend_panel()
    if p:
        ui.type_into(p.angle.widget, "60")


def p12_angle_60():
    v = legs(2, 2 * math.tan(math.radians(60)))
    h.check("P12 distance 2 at 60 degrees", b.close(h.solid_volume(), v), (h.solid_volume(), v))
    h.check("P12 no message", "⚠" not in message(), message())
    s["cut"] = b.top_cut()
    p = b.blend_panel()
    if p:
        b.click_widget(p.flip)


def p12_flipped():
    v = legs(2, 2 * math.tan(math.radians(60)))
    h.check("P12 Flip keeps the volume", b.close(h.solid_volume(), v), h.solid_volume())
    cut = b.top_cut()
    h.check("P12 Flip puts the distance on the other face", cut != s["cut"], (s["cut"], cut))
    p = b.blend_panel()
    if p:
        b.choose(p.ctype, "Two Distances")


def p12_two():
    p = b.blend_panel()
    if p:
        ui.type_into(p.distance2.widget, "3")


def p12_two_drag():
    v = legs(2, 3)
    h.check("P12 two distances 2 and 3", b.close(h.solid_volume(), v), (h.solid_volume(), v))
    p = b.blend_panel()
    if p is None or len(p.arrows) < 2:
        h.check("P12 two arrows", False)
        return
    start, end = b.arrow_screen(p, 1, along=-(p.distance2.value() + 12.0))
    h.drag(start, end)


def p12_dragged_back():
    p = b.blend_panel()
    if p is None:
        return
    d2 = p.distance2.value()
    h.check("P12 dragged through the edge: Distance 2 stops at its smallest", 0 < d2 < 0.5, d2)
    dragger, spot = p.arrows[1][0], p.arrows[1][1]
    h.check(
        "P12 the arrow comes back to the distance shown",
        abs(dragger.distance() - d2 * spot["per_unit"]) < 1e-6,
        (dragger.distance(), d2),
    )
    h.check(
        "P12 the box shows mm (not µm)",
        "mm" in p.distance2.widget.text(),
        p.distance2.widget.text(),
    )
    v = legs(2, d2)
    h.check("P12 preview follows", b.close(h.solid_volume(), v), (h.solid_volume(), v))
    h.shot("p12-dragged-back")
    ui.type_into(p.distance2.widget, "1")


def p12_ok():
    v = legs(2, 1)
    h.check(
        "P12 typed 1 after the drag is 1 mm", b.close(h.solid_volume(), v), (h.solid_volume(), v)
    )
    h.task_button("OK")


def p12_done():
    h.check("P12 closed", not dialog_open())
    h.check("P12 one chamfer", len(b.blends()) == 1, b.blends())
    h.fit()


# -- Path 13: edit twice, undo / redo, save / reopen --------------------------------------------
def p13_edit():
    b.timeline_double_click("Chamfer 1")


def p13_editing():
    p = b.blend_panel()
    h.check("P13 editing Chamfer 1", p is not None and not p.created)
    if p is None:
        return
    h.check(
        "P13 Two Distances 2 and 1 shown",
        p.ctype.currentText() == "Two Distances"
        and abs(p.distance.value() - 2) < 1e-9
        and abs(p.distance2.value() - 1) < 1e-9,
        (p.ctype.currentText(), p.distance.value(), p.distance2.value()),
    )
    b.choose(p.ctype, "Equal Distance")


def p13_equal():
    p = b.blend_panel()
    if p:
        ui.type_into(p.distance.widget, "1.5")


def p13_ok():
    v = legs(1.5, 1.5)
    h.check("P13 equal 1.5", b.close(h.solid_volume(), v), (h.solid_volume(), v))
    h.task_button("OK")


def p13_edit2():
    h.check("P13 edit kept", not dialog_open())
    h.fit()
    b.timeline_double_click("Chamfer 1")


def p13_add():
    p = b.blend_panel()
    h.check(
        "P13 Equal Distance remembered", p is not None and p.ctype.currentText() == "Equal Distance"
    )
    h.click_edge(BACK_TOP)


def p13_ok2():
    p = b.blend_panel()
    h.check("P13 back edge added", p is not None and len(p.refs) == 2, picks())
    h.task_button("OK")


def p13_two_edges():
    v = b.BOX - 80 * 1.5 * 1.5 / 2
    h.check("P13 both edges 1.5", b.close(h.solid_volume(), v), (h.solid_volume(), v))
    s["v"] = v
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def p13_undone():
    h.check(
        "P13 Ctrl+Z: one edge again", b.close(h.solid_volume(), legs(1.5, 1.5)), h.solid_volume()
    )
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def p13_redone():
    h.check("P13 Ctrl+Y: two edges", b.close(h.solid_volume(), s["v"]), h.solid_volume())
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-chamfer-qa-"), "chamfer_qa.FCStd")
    s["path"] = path
    doc().saveAs(path)
    App.closeDocument(doc().Name)


def p13_open():
    App.openDocument(s["path"])
    h.fit()


def p13_reopened():
    h.check("P13 reopened", b.close(h.solid_volume(), s["v"]), h.solid_volume())
    b.timeline_double_click("Chamfer 1")


def p13_editing_reopened():
    p = b.blend_panel()
    h.check("P13 editing after reopening", p is not None and not p.created)
    if p is None:
        return
    h.check(
        "P13 as saved: Equal Distance 1.5, two edges",
        p.ctype.currentText() == "Equal Distance"
        and abs(p.distance.value() - 1.5) < 1e-9
        and len(p.refs) == 2,
        (p.ctype.currentText(), p.distance.value(), p.refs),
    )
    h.press(QtCore.Qt.Key_Escape)


def p13_esc():
    h.check("P13 Esc closed the edit", not dialog_open())
    h.check("P13 unchanged", b.close(h.solid_volume(), s["v"]), h.solid_volume())
    h.check("P13 the chamfer is shown", h.body().Tip.ViewObject.isVisible())


# -- Path 14: a chamfer round a hole; F in the Chamfer dialog --------------------------------------
def p14_sketch():
    h.click_empty()
    h.ribbon("Create Sketch")


def p14_face():
    h.fit()
    h.click(V(30, 22, 10))


def p14_draw():
    sk = h.in_sketch()
    h.check("P14 sketch on the top face", sk is not None)
    if sk:
        x, y = h.to_sketch(sk, V(HOLE_C[0], HOLE_C[1], 10))
        h.draw_circle(sk, x, y, HOLE_R)


def p14_finish():
    h.ribbon("Finish Sketch")


def p14_e():
    h.fit()
    h.press("e")


def p14_depth():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    if p is not None:
        ui.type_into(p.distance.widget, "-10")


def p14_cut_ok():
    h.task_button("OK")


def p14_hole():
    s["v"] -= math.pi * HOLE_R**2 * 10
    h.check("P14 a hole through the part", b.close(h.solid_volume(), s["v"]), h.solid_volume())
    h.fit()
    h.click_empty()
    h.ribbon("Chamfer")


def p14_rim():
    a = math.radians(-60)
    h.fit()
    h.click_edge(V(HOLE_C[0] + HOLE_R * math.cos(a), HOLE_C[1] + HOLE_R * math.sin(a), 10))


def p14_rim_size():
    p = b.blend_panel()
    h.check("P14 the hole's rim picked", p is not None and len(p.refs) == 1, picks())
    if p:
        ui.type_into(p.distance.widget, "1")


def p14_press_f():
    v = s["v"] - 0.5 * 2 * math.pi * (HOLE_R + 1.0 / 3.0)
    h.check(
        "P14 chamfer round the hole (Pappus)", b.close(h.solid_volume(), v), (h.solid_volume(), v)
    )
    s["v"] = v
    s["chamfer_panel"] = b.blend_panel()
    h.press("f")


def p14_fillet_open():
    p = b.blend_panel()
    h.check("P14 F kept the chamfer", len(b.blends()) == 2 and b.close(h.solid_volume(), s["v"]))
    h.check(
        "P14 Fillet is open now, with nothing picked",
        p is not None and p is not s["chamfer_panel"] and p.title == "Fillet" and p.refs == [],
        picks(),
    )
    h.check("P14 no message", "⚠" not in message(), message())
    h.press(QtCore.Qt.Key_Escape)


def p14_done():
    h.check("P14 Esc closed the Fillet", not dialog_open())
    h.check("P14 nothing broken", not broken(), broken())
    h.check("P14 valid", h.body().Shape.isValid())
    h.shot("p14-end")


h.run(
    "fillet_qa_chamfer",
    b.box_steps("ChamferQA")
    + [
        p12_chamfer,
        p12_ok_empty,
        p12_refused,
        p12_again,
        p12_pick,
        p12_zero,
        p12_zero_said,
        p12_zero_refused,
        p12_angle_zero,
        p12_angle_zero_said,
        p12_angle_90,
        p12_angle_refused,
        p12_angle_60,
        p12_flipped,
        p12_two,
        p12_two_drag,
        p12_dragged_back,
        p12_ok,
        p12_done,
        p13_edit,
        p13_editing,
        p13_equal,
        p13_ok,
        p13_edit2,
        p13_add,
        p13_ok2,
        p13_two_edges,
        p13_undone,
        p13_redone,
        p13_open,
        p13_reopened,
        p13_editing_reopened,
        p13_esc,
        p14_sketch,
        p14_face,
        p14_draw,
        p14_finish,
        p14_e,
        p14_depth,
        p14_cut_ok,
        p14_hole,
        p14_rim,
        p14_rim_size,
        p14_press_f,
        p14_fillet_open,
        p14_done,
    ],
)
