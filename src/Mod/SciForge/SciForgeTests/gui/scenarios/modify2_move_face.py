# SPDX-License-Identifier: LGPL-2.1-or-later
"""Move/Copy with Move Object Faces (Fusion moves faces the way it moves bodies: the faces
next to them stretch along), only real input.

Part: the 40 x 30 x 10 box (blend_steps.box_steps).

Path F1, M with nothing selected: Move Object lists Bodies and Faces; choose Faces (Create Copy
        goes away: it makes bodies). Click the top face: the Objects box says 1 face, the
        manipulator sits on the face. Type Z Distance 5: the box is 15 high. OK: one Move step
        in the timeline, the part still one valid solid.
Path F2, Ctrl+Z: 10 high again; Ctrl+Y: 15 high.
Path F3, the Move edited from the timeline: it reads Faces and Z 5; Z -3 typed: 7 high. OK.
Path F4, M again, Faces, click the right face, X Distance 5: the box is 45 long. OK: a second
        Move step.
Path F5, M, Faces, the top face, Z 10, Esc: nothing changes.

Volumes: 40 x 30 x 15 = 18000, 40 x 30 x 7 = 8400, 45 x 30 x 7 = 9450.
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as bs
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import modify2_steps as m
from SciForgeTests.gui import shell_draft_steps as sd

V = App.Vector
s = {}


def panel():
    from sciforge import move_ui

    p = bs.panel()
    return p if isinstance(p, move_ui.MovePanel) and not p._closed else None


def moves():
    return m.objects(kind="MoveFace")


def box():
    bb = h.body().Shape.BoundBox
    return [round(x, 6) for x in (bb.XMin, bb.YMin, bb.ZMin, bb.XMax, bb.YMax, bb.ZMax)]


def dz_field(p):
    return p.distance_fields[2].widget


def dx_field(p):
    return p.distance_fields[0].widget


# -- F1 -------------------------------------------------------------------------------------------
def press_m():
    Gui.Selection.clearSelection()
    h.click_empty()
    h.fit()
    h.press("m")


def faces_listed():
    p = panel()
    if not h.check("Move/Copy dialog open", p is not None):
        return
    labels = [p.move_object.itemText(i) for i in range(p.move_object.count())]
    h.check("Move Object: Bodies, Faces", labels == ["Bodies", "Faces"], labels)
    h.check("Create Copy shows for bodies", p.copy.isVisible())
    h.check("choose Faces", b.choose(p.move_object, "Faces"))


def faces_chosen():
    p = panel()
    if p is None:
        return
    h.check("Create Copy hidden for faces", not p.copy.isVisible())
    h.check("the Objects box waits", p.active == "objects", p.active)
    h.click(V(20, 15, 10))


def top_picked():
    p = panel()
    if p is None:
        return
    text = p.fields["objects"].button.text()
    h.check("the Objects box says 1 face", text == "1 face", text)
    triad = getattr(p, "triad", None)
    if h.check("manipulator shown", triad is not None):
        h.check("on the face", (triad.center - V(20, 15, 10)).Length < 1e-6, triad.center)
    h.check("nothing moved yet", m.close(h.solid_volume(), 12000.0), h.solid_volume())
    bs.type_value(dz_field(p), "5")


def raised():
    v = h.solid_volume()
    h.check("Z 5: the box is 15 high", m.close(v, 18000.0), v)
    h.check("bounding box", box() == [0, 0, 0, 40, 30, 15], box())
    h.shot("1-top-up")
    h.task_button("OK")


def after_ok():
    h.check("dialog closed", m.no_dialog())
    h.check("one Move step", len(moves()) == 1, moves())
    shape = h.body().Shape
    h.check("kept", m.close(shape.Volume, 18000.0), shape.Volume)
    h.check("one valid solid with 6 faces", shape.isValid() and len(shape.Solids) == 1)
    h.check("6 faces", len(shape.Faces) == 6, len(shape.Faces))
    s["title"] = bs.timeline_title_of(moves()[0]) if moves() else None
    h.check("the timeline shows the Move", bool(s["title"]), sd.timeline_titles())
    h.check("no errors in the Report view", not sd.report_errors(), sd.report_errors())


# -- F2 -------------------------------------------------------------------------------------------
def undo():
    m.undo()


def after_undo():
    h.check("Ctrl+Z: 10 high", m.close(h.solid_volume(), 12000.0), h.solid_volume())
    h.check("no Move step", not moves(), moves())


def redo():
    m.redo()


def after_redo():
    h.check("Ctrl+Y: 15 high", m.close(h.solid_volume(), 18000.0), h.solid_volume())
    h.fit()


# -- F3 -------------------------------------------------------------------------------------------
def edit():
    sd.timeline_double_click(s["title"] or "Move 1")


def edit_open():
    p = panel()
    if not h.check("the Move dialog opens on the step", p is not None and p.editing):
        return
    h.check("it reads Faces", p.move_object.currentText() == "Faces", p.move_object.currentText())
    h.check("1 face", p.fields["objects"].button.text() == "1 face")
    h.check("Z 5", abs(p.options["dz"] - 5.0) < 1e-9, p.options["dz"])
    bs.type_value(dz_field(p), "-3")


def lowered():
    v = h.solid_volume()
    h.check("Z -3: 7 high", m.close(v, 8400.0), v)
    h.check("bounding box", box() == [0, 0, 0, 40, 30, 7], box())
    h.task_button("OK")


def after_edit():
    h.check("dialog closed", m.no_dialog())
    h.check("still one Move step", len(moves()) == 1, moves())
    h.check("kept", m.close(h.solid_volume(), 8400.0), h.solid_volume())


# -- F4 -------------------------------------------------------------------------------------------
def press_m2():
    Gui.Selection.clearSelection()
    h.click_empty()
    h.fit()
    h.press("m")


def faces2():
    p = panel()
    if h.check("Move/Copy open", p is not None):
        h.check("choose Faces", b.choose(p.move_object, "Faces"))


def click_right():
    h.click(V(40, 15, 4))


def right_picked():
    p = panel()
    if p is None:
        return
    h.check("1 face", p.fields["objects"].button.text() == "1 face")
    bs.type_value(dx_field(p), "5")


def stretched():
    v = h.solid_volume()
    h.check("X 5: 45 long", m.close(v, 9450.0), v)
    h.check("bounding box", box() == [0, 0, 0, 45, 30, 7], box())
    h.task_button("OK")


def after_second():
    h.check("dialog closed", m.no_dialog())
    h.check("two Move steps", len(moves()) == 2, moves())
    h.check("valid", h.body().Shape.isValid())


# -- F5 -------------------------------------------------------------------------------------------
def press_m3():
    Gui.Selection.clearSelection()
    h.click_empty()
    h.fit()
    h.press("m")


def faces3():
    p = panel()
    if h.check("Move/Copy open", p is not None):
        h.check("choose Faces", b.choose(p.move_object, "Faces"))


def click_top3():
    h.click(V(20, 15, 7))


def ten():
    p = panel()
    if p is not None:
        bs.type_value(dz_field(p), "10")


def esc():
    h.check("the preview moved it", m.close(h.solid_volume(), 45 * 30 * 17.0), h.solid_volume())
    h.press(QtCore.Qt.Key_Escape)


def after_esc():
    h.check("Esc closes it", m.no_dialog())
    h.check("nothing changed", m.close(h.solid_volume(), 9450.0), h.solid_volume())
    h.check("two Move steps", len(moves()) == 2, moves())
    h.check("no errors in the Report view", not sd.report_errors(), sd.report_errors())
    h.shot("2-end")


h.run(
    "modify2_move_face",
    sd.box_steps("Modify2MoveFace")
    + [
        press_m,
        faces_listed,
        faces_chosen,
        top_picked,
        raised,
        after_ok,
        undo,
        after_undo,
        redo,
        after_redo,
        edit,
        edit_open,
        lowered,
        after_edit,
        press_m2,
        faces2,
        click_right,
        right_picked,
        stretched,
        after_second,
        press_m3,
        faces3,
        click_top3,
        ten,
        esc,
        after_esc,
    ],
)
