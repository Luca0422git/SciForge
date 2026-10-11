# SPDX-License-Identifier: LGPL-2.1-or-later
"""Draft the way a Fusion user does it, only real input: the ribbon's Draft with nothing
selected (the dialog waits for the fixed plane, the origin squares appear), click the XY
square, click the front face (again to drop it, a second face), type the angle, turn the
blue angle handle, Flip the pull direction, a face that cannot be drafted does not light
up, an angle too steep (explained in the dialog, OK waits, nothing in the Report view),
OK, Ctrl+Z / Ctrl+Y, edit from the timeline, Cancel and Esc leave the part as it was, and
a second Draft started with a face selected beforehand.

Box 40 x 30 x 10, fixed plane XY (pull +Z), h = 10, hand-derived volumes:
  front face drafted by a:          12000 - 40 * h^2 tan(a) / 2
  front and right faces:            12000 - (40 + 30) h^2 tan(a) / 2 + h^3 tan(a)^2 / 3
  flipped (the face leans out):     12000 + 40 * h^2 tan(a) / 2
  then the right face by b:         V1 - tan(b) (30 h^2 / 2 - h^3 tan(a) / 3)
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import shell_draft_steps as sd
from SciForgeTests.gui import widget_input as w

V = App.Vector
s = {}
XY_SQUARE = V(12, -8, 0)
FRONT = V(20, 0, 5)
RIGHT = V(40, 15, 5)
TOP = V(20, 15, 10)


def tan(a):
    return math.tan(math.radians(a))


def one_face(a, length=40.0):
    return sd.BOX - length * 100.0 * tan(a) / 2.0


def two_faces(a):
    return sd.BOX - 70 * 100.0 * tan(a) / 2.0 + 1000.0 * tan(a) ** 2 / 3.0


def ribbon_draft():
    Gui.Selection.clearSelection()
    sd.modify_menu("Draft")


def waiting():
    p = sd.draft_panel()
    h.check("Draft dialog open", p is not None and Gui.Control.activeDialog())
    if p is None:
        return
    h.check("waits for the fixed plane", p.plane_ref is None and p.active == "plane")
    h.check("Plane box is the blue one", p.plane_box.button.isChecked())
    h.check("the origin squares are shown to click", p.planes is not None)
    h.check("no step made yet", p.target is None and not sd.drafts())
    h.check("no error while waiting", p.message.text() == "", p.message.text())
    h.check("Type Fixed Plane; Parting Line greyed", p.type.currentText() == "Fixed Plane")
    h.check("angle 1 deg to start", abs(p.angle.value() - 1.0) < 1e-9, p.angle.value())
    sd.no_popups("Draft with nothing selected")
    h.shot("1-waiting")


def click_xy():
    h.fit()
    h.click(XY_SQUARE)


def plane_picked():
    p = sd.draft_panel()
    h.check("XY plane picked", p is not None and p.plane_ref is not None, p and p.plane_ref)
    h.check(
        "it is the origin XY plane",
        p and p.plane_ref and p.plane_ref[0].TypeId == "App::Plane",
        p and p.plane_ref,
    )
    h.check("Faces box takes the clicks now", p is not None and p.active == "faces")
    h.check("the squares are gone", p is not None and p.planes is None)
    h.check("pull direction arrow shown", p is not None and p.arrow is not None)
    h.check("model unchanged (no faces yet)", sd.close(h.solid_volume(), sd.BOX))


def click_front():
    h.fit()
    h.click(FRONT)


def front_picked():
    p = sd.draft_panel()
    h.check("front face picked", p is not None and p.names() and len(p.names()) == 1)
    v = h.solid_volume()
    h.check("preview: front face drafted 1 deg", sd.close(v, one_face(1)), v)
    h.check("FreeCAD's Draft feature", len(sd.drafts()) == 1, sd.drafts())
    h.check("the angle handle is shown", p is not None and p.handle is not None)
    h.shot("2-front")
    if p:
        sd.type_into(p.angle.widget, "5")


def five_degrees():
    v = h.solid_volume()
    h.check("typed 5 deg previews", sd.close(v, one_face(5)), (v, one_face(5)))


def click_right():
    h.click(RIGHT)


def two_picked():
    p = sd.draft_panel()
    h.check("two faces picked", p is not None and len(p.names()) == 2, p and p.names())
    v = h.solid_volume()
    h.check("front and right drafted 5 deg", sd.close(v, two_faces(5)), (v, two_faces(5)))
    h.shot("3-two")


def click_right_again():
    h.click(RIGHT)


def right_dropped():
    p = sd.draft_panel()
    h.check("right face dropped", p is not None and len(p.names()) == 1, p and p.names())
    h.check("back to one face", sd.close(h.solid_volume(), one_face(5)), h.solid_volume())


def click_top_refused():
    h.click(TOP)


def top_refused():
    p = sd.draft_panel()
    h.check(
        "the top face (parallel to the plane) is not taken",
        p is not None and len(p.names()) == 1,
        p and p.names(),
    )
    h.check("the part is unchanged by that click", sd.close(h.solid_volume(), one_face(5)))


def turn_handle():
    p = sd.draft_panel()
    if p is None or p.handle is None:
        h.check("angle handle to turn", False)
        return
    h.fit()
    here, there = p.handle.screen_points(12.0)
    s["before"] = p.angle.value()
    h.drag(h.screen_point(here), h.screen_point(there))


def turned():
    p = sd.draft_panel()
    a = p.angle.value() if p else 0
    h.check("turning the handle changes the angle", abs(a - s["before"]) > 1.0, (s["before"], a))
    v = h.solid_volume()
    h.check("preview follows the turned angle", sd.close(v, one_face(a)), (v, a))
    h.shot("4-turned")
    if p:
        sd.type_into(p.angle.widget, "5")


def flip():
    p = sd.draft_panel()
    if p:
        w.click(p.flip)


def flipped():
    p = sd.draft_panel()
    h.check("Flip is on", p is not None and p.flip.isChecked())
    v = h.solid_volume()
    h.check("flipped: the face leans out", sd.close(v, sd.BOX + 2000 * tan(5)), v)
    h.shot("5-flipped")
    if p:
        w.click(p.flip)


def type_too_steep():
    p = sd.draft_panel()
    s["good"] = h.solid_volume()
    h.check("unflipped again", sd.close(s["good"], one_face(5)), s["good"])
    if p:
        sd.type_into(p.angle.widget, "80")


def too_steep_reported():
    p = sd.draft_panel()
    text = p.message.text() if p else ""
    h.check("too steep explained in the dialog", "cannot be tilted this far" in text, text)
    h.check("nothing about it in the Report view", not sd.report_errors(), sd.report_errors())
    sd.no_popups("an angle too steep")
    h.shot("6-too-steep")
    h.task_button("OK")


def ok_refused():
    h.check("OK waits while the draft fails", sd.draft_panel() is not None)
    p = sd.draft_panel()
    if p:
        sd.type_into(p.angle.widget, "5")


def ok():
    p = sd.draft_panel()
    h.check("message gone", p is not None and p.message.text() == "", p and p.message.text())
    h.task_button("OK")


def after_ok():
    h.check("dialog closed", not Gui.Control.activeDialog())
    shape = h.body().Shape
    h.check("draft: 12000 - 2000 tan 5", sd.close(shape.Volume, one_face(5)), shape.Volume)
    h.check("still 6 faces", len(shape.Faces) == 6, len(shape.Faces))
    h.check("valid solid", shape.isValid())
    d = sd.drafts()
    h.check("one Draft, the end of the timeline", len(d) == 1 and h.body().Tip is d[0], d)
    h.check("timeline shows Draft 1", "Draft 1" in sd.timeline_titles(), sd.timeline_titles())
    h.check("no leftover selection", not Gui.Selection.getSelectionEx())
    h.check("only the draft is shown", sd.shown_features() == [d[0].Name], sd.shown_features())
    h.shot("7-draft")


def undo():
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def after_undo():
    h.check(
        "Ctrl+Z takes the draft away in one step",
        sd.close(h.solid_volume(), sd.BOX) and not sd.drafts(),
        h.solid_volume(),
    )


def redo():
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def after_redo():
    h.check("Ctrl+Y brings it back", sd.close(h.solid_volume(), one_face(5)) and sd.drafts())
    h.fit()


def edit_from_timeline():
    sd.timeline_double_click("Draft 1")


def edit_open():
    p = sd.draft_panel()
    h.check("double-click opens the Draft dialog on the step", p is not None and p.editing)
    h.check("its plane is shown", p is not None and p.plane_ref is not None)
    h.check("its face is shown picked", p is not None and len(p.names()) == 1)
    h.check("the angle is shown", p is not None and abs(p.angle.value() - 5) < 1e-9)
    h.check("Faces box takes the clicks", p is not None and p.active == "faces")
    h.shot("8-edit")
    if p:
        sd.type_into(p.angle.widget, "3")


def edit_ok():
    h.task_button("OK")


def after_edit():
    v = h.solid_volume()
    h.check("edited to 3 deg", sd.close(v, one_face(3)), v)
    h.check("still one draft", len(sd.drafts()) == 1)
    s["v"] = v


def cancel_start():
    sd.modify_menu("Draft")


def cancel_plane():
    h.fit()
    h.click(XY_SQUARE)


def cancel_face():
    h.click(RIGHT)


def cancel_preview():
    p = sd.draft_panel()
    h.check("a second draft previewed", p is not None and p.target is not None)
    h.check("preview changes the part", not sd.close(h.solid_volume(), s["v"]))
    h.task_button("Cancel")


def after_cancel():
    h.check("Cancel leaves the model as it was", sd.close(h.solid_volume(), s["v"]))
    h.check("no new step", len(sd.drafts()) == 1, sd.drafts())
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("the part is shown", sd.shown_features() == [h.body().Tip.Name], sd.shown_features())


def esc_start():
    sd.modify_menu("Draft")


def esc_plane():
    h.fit()
    h.click(XY_SQUARE)


def esc_face():
    h.click(RIGHT)


def esc_press():
    p = sd.draft_panel()
    h.check("previewed before Esc", p is not None and p.target is not None)
    h.press(QtCore.Qt.Key_Escape)


def after_esc():
    h.check("Esc closes the dialog", not Gui.Control.activeDialog())
    h.check("Esc leaves the model as it was", sd.close(h.solid_volume(), s["v"]))
    h.check("no new step", len(sd.drafts()) == 1, sd.drafts())


def preselect_right():
    h.fit()
    h.click(RIGHT)


def second_draft():
    h.check("right face selected before Draft", len(sd.selected()) == 1, sd.selected())
    sd.modify_menu("Draft")


def second_started():
    p = sd.draft_panel()
    h.check("Draft started with the right face", p is not None and len(p.names()) == 1)
    h.check("it still waits for the plane", p is not None and p.active == "plane")
    h.check("the part unchanged meanwhile", sd.close(h.solid_volume(), s["v"]))
    h.fit()
    h.click(XY_SQUARE)


def second_plane():
    p = sd.draft_panel()
    h.check("plane picked", p is not None and p.plane_ref is not None)
    if p:
        sd.type_into(p.angle.widget, "4")


def second_enter():
    p = sd.draft_panel()
    if p:
        sd.press_enter(p.angle.widget)


def after_second():
    h.check("Enter finished the dialog", not Gui.Control.activeDialog())
    v = h.solid_volume()
    expect = s["v"] - tan(4) * (1500.0 - 1000.0 * tan(3) / 3.0)
    h.check("second draft on the right face, 4 deg", sd.close(v, expect), (v, expect))
    h.check("two drafts in the timeline", "Draft 2" in sd.timeline_titles(), sd.timeline_titles())
    h.check("valid at the end", h.body().Shape.isValid())
    h.check("no errors in the Report view", not sd.report_errors(), sd.report_errors())
    h.shot("9-end")


h.run(
    "shell_draft_draft",
    sd.box_steps("Draft")
    + [
        ribbon_draft,
        waiting,
        click_xy,
        plane_picked,
        click_front,
        front_picked,
        five_degrees,
        click_right,
        two_picked,
        click_right_again,
        right_dropped,
        click_top_refused,
        top_refused,
        turn_handle,
        turned,
        flip,
        flipped,
        type_too_steep,
        too_steep_reported,
        ok_refused,
        ok,
        after_ok,
        undo,
        after_undo,
        redo,
        after_redo,
        edit_from_timeline,
        edit_open,
        edit_ok,
        after_edit,
        cancel_start,
        cancel_plane,
        cancel_face,
        cancel_preview,
        after_cancel,
        esc_start,
        esc_plane,
        esc_face,
        esc_press,
        after_esc,
        preselect_right,
        second_draft,
        second_started,
        second_plane,
        second_enter,
        after_second,
    ],
)
