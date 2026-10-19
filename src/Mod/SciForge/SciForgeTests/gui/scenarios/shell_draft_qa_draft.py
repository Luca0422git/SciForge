# SPDX-License-Identifier: LGPL-2.1-or-later
"""Draft the way Fusion users use it, trying to break it (QA, only real input).
A 40 x 30 x 10 box made with Create Sketch / E.

Path 1, picks in the "wrong" order: the front face clicked first becomes the Pull
        Direction (Fusion takes a flat face there too); its x clears it, the XY square
        is clicked, then the front face is the face to draft; 3 degrees; Enter over the
        view finishes.
Path 2, OK with the plane but no face (the dialog says what is missing and stays); a
        face; Esc in the middle: nothing made, the part as it was.
Path 3, Q (Press Pull) while a second Draft is open with a good preview: the draft is
        kept, Press Pull opens; Esc.
Path 4, the first draft edited from the timeline: the curved handle dragged far (past
        what can be drafted: explained, OK waits), then the other way (a negative angle:
        the face leans out); 3 typed; OK.
Path 5, a third Draft on the front face: the pull arrow in the 3D view clicked flips the
        pull direction (Fusion), like the flip button next to Pull Direction; clicked
        again, back; Cancel.
Path 6, save, close, reopen; the first draft edited again (4 degrees); Ctrl+Z, Ctrl+Y.
Path 7, a new design for a moulded part: the four sides drafted 3 degrees about XY, then
        Shell taking the top away (1 mm); the draft edited to 5 degrees afterwards: the
        shell follows. Ctrl+Z.

Volumes by hand (h = 10, a, b in degrees):
  front face drafted by a:            12000 - 40 h^2 tan(a) / 2
  then the right face by b:           - tan(b) (30 h^2 / 2 - h^3 tan(a) / 3)
  four sides by a, shelled with t:    prismatoid h/6 (A(0) + 4 A(h/2) + A(h)),
                                      A(z) = (40 - 2 z tan a)(30 - 2 z tan a), minus the
                                      cavity from z = t to h with each side moved in by
                                      t / cos a.
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
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import shell_draft_steps as sd
from SciForgeTests.gui import timeline_input as tl
from SciForgeTests.gui import widget_input as w

V = App.Vector
s = {}
FRONT = V(20, 0, 5)
RIGHT = V(40, 15, 5)
TOP = V(20, 15, 10)


def tan(a):
    return math.tan(math.radians(a))


def front(a):
    return sd.BOX - 40 * 100.0 * tan(a) / 2.0


def front_right(a, b_):
    return front(a) - tan(b_) * (30 * 100.0 / 2.0 - 1000.0 * tan(a) / 3.0)


def moulded(a, t):
    k = tan(a)
    c = math.cos(math.radians(a))

    def area(z, d=0.0):
        return (40 - 2 * z * k - 2 * d) * (30 - 2 * z * k - 2 * d)

    outer = 10 / 6.0 * (area(0) + 4 * area(5) + area(10))
    hh = 10 - t
    inner = hh / 6.0 * (area(t, t / c) + 4 * area(t + hh / 2, t / c) + area(10, t / c))
    return outer - inner


def doc():
    return App.ActiveDocument


def dialog_open():
    return bool(Gui.Control.activeDialog())


def msg(p):
    return p.message.text() if p is not None else ""


def part_ok(where):
    bad = [o.Label for o in doc().Objects if "Invalid" in o.State or "Error" in o.State]
    h.check("%s: nothing in error" % where, not bad, bad)
    h.check("%s: valid solid" % where, h.body().Shape.isValid())
    tip = h.body().Tip
    h.check("%s: the part is shown" % where, tip is not None and tip.ViewObject.isVisible())
    h.check("%s: nothing left see-through" % where, not b.see_through(), b.see_through())


def made():
    s["undo"] = list(doc().UndoNames)


# -- Path 1: a face first --------------------------------------------------------------------
def p1_draft():
    Gui.Selection.clearSelection()
    sd.modify_menu("Draft")


def p1_front_first():
    p = sd.draft_panel()
    h.check("P1 the dialog waits for the pull direction", p is not None and p.active == "plane")
    h.check(
        "P1 the box is called Pull Direction",
        p is not None
        and p.layout.labelForField(p.plane_box.widget.parentWidget()) is not None
        and p.layout.labelForField(p.plane_box.widget.parentWidget()).text() == "Pull Direction",
    )
    h.fit()
    h.click(FRONT)


def p1_front_is_plane():
    p = sd.draft_panel()
    h.check(
        "P1 the flat face clicked first is the pull direction",
        p is not None and p.plane_ref is not None and p.plane_ref[1].startswith("Face"),
        p and p.plane_ref,
    )
    h.check("P1 the Faces box takes the clicks now", p is not None and p.active == "faces")
    h.check("P1 nothing drafted yet", not sd.drafts() and sd.close(h.solid_volume(), sd.BOX))
    if p:
        w.click(p.plane_box.clear)


def p1_cleared():
    p = sd.draft_panel()
    h.check("P1 x clears the pull direction", p is not None and p.plane_ref is None)
    h.check("P1 the Pull Direction box takes the clicks", p is not None and p.active == "plane")
    h.check("P1 the origin squares are back", p is not None and p.planes is not None)
    h.fit()
    pl.click_square("XY_Plane")  # where the XY square shows


def p1_xy():
    p = sd.draft_panel()
    h.check(
        "P1 XY is the pull direction",
        p is not None and p.plane_ref is not None and p.plane_ref[0].TypeId == "App::Plane",
        p and p.plane_ref,
    )
    h.fit()
    h.click(FRONT)


def p1_face():
    p = sd.draft_panel()
    h.check("P1 now the front face is drafted", p is not None and len(p.names()) == 1)
    if p:
        ui.type_into(p.angle.widget, "3")


def p1_enter():
    v = h.solid_volume()
    h.check("P1 3 degrees previewed", sd.close(v, front(3)), (v, front(3)))
    h.press(QtCore.Qt.Key_Return)


def p1_done():
    h.check("P1 Enter over the view finished", not dialog_open())
    h.check("P1 one draft", len(sd.drafts()) == 1, sd.drafts())
    h.check("P1 kept", sd.close(h.solid_volume(), front(3)), h.solid_volume())
    h.check("P1 called Draft 1", "Draft 1" in sd.timeline_titles(), sd.timeline_titles())
    part_ok("P1")
    s["undo"] = list(doc().UndoNames)


# -- Path 2: OK with no face, Esc in the middle -------------------------------------------------
def p2_draft():
    sd.modify_menu("Draft")


def p2_xy():
    h.fit()
    pl.click_square("XY_Plane")  # where the XY square shows


def p2_ok():
    h.task_button("OK")


def p2_refused():
    p = sd.draft_panel()
    h.check("P2 OK without a face keeps the dialog", p is not None and dialog_open())
    h.check("P2 and says to pick the faces", "faces" in msg(p), msg(p))
    sd.no_popups("OK without a face")
    h.fit()
    h.click(RIGHT)


def p2_esc():
    p = sd.draft_panel()
    h.check("P2 a preview", p is not None and p.target is not None, msg(p))
    h.check("P2 two drafts while previewing", len(sd.drafts()) == 2, sd.drafts())
    h.press(QtCore.Qt.Key_Escape)


def p2_closed():
    h.check("P2 Esc closed it", not dialog_open())
    h.check("P2 one draft", len(sd.drafts()) == 1, sd.drafts())
    h.check("P2 the part as it was", sd.close(h.solid_volume(), front(3)), h.solid_volume())
    h.check("P2 no undo step added", list(doc().UndoNames) == s["undo"], doc().UndoNames)
    part_ok("P2")


# -- Path 3: Q while the Draft dialog is open ---------------------------------------------------
def p3_draft():
    sd.modify_menu("Draft")


def p3_xy():
    h.fit()
    pl.click_square("XY_Plane")  # where the XY square shows


def p3_right():
    h.fit()
    h.click(RIGHT)


def p3_type():
    p = sd.draft_panel()
    if p:
        ui.type_into(p.angle.widget, "2")


def p3_q():
    v = h.solid_volume()
    h.check("P3 right face 2 degrees previewed", sd.close(v, front_right(3, 2)), v)
    h.press("q")


def p3_after():
    from sciforge import taskui

    h.check("P3 Q kept the draft", len(sd.drafts()) == 2 and sd.draft_panel() is None)
    h.check("P3 kept as previewed", sd.close(h.solid_volume(), front_right(3, 2)))
    current = taskui.current()
    h.check(
        "P3 Press Pull is open",
        current is not None and current.title == "Press Pull",
        current and current.title,
    )
    sd.no_popups("Q with Draft open")
    h.press(QtCore.Qt.Key_Escape)


def p3_closed():
    h.check("P3 closed", not dialog_open())
    h.check("P3 Draft 2 in the timeline", "Draft 2" in sd.timeline_titles(), sd.timeline_titles())
    part_ok("P3")
    s["v3"] = h.solid_volume()


# -- Path 4: the handle dragged far, then negative ------------------------------------------------
def p4_edit():
    h.fit()
    b.timeline_double_click("Draft 1", click_first=True)


def p4_open():
    p = sd.draft_panel()
    h.check("P4 editing Draft 1", p is not None and p.editing)
    h.check("P4 3 degrees shown", p is not None and abs(p.angle.value() - 3) < 1e-9)
    h.check("P4 the curved handle", p is not None and p.handle is not None)
    if p is None or p.handle is None:
        return
    h.fit()
    here, there = p.handle.screen_points(150.0)
    h.drag(h.screen_point(here), h.screen_point(there))


def p4_far():
    p = sd.draft_panel()
    a = p.angle.value() if p else 0
    h.check("P4 dragged far: the angle stops at 89.9", abs(a - 89.9) < 1e-6 or a > 60, a)
    h.check("P4 explained in the dialog", msg(p).startswith("⚠"), msg(p))
    h.check("P4 nothing in the Report view", not sd.report_errors(), sd.report_errors())
    h.task_button("OK")


p4_far.wait_ms = 1200


def p4_ok_waits():
    p = sd.draft_panel()
    h.check("P4 OK waits", p is not None and dialog_open())
    if p is None or p.handle is None:
        return
    h.fit()
    here, there = p.handle.screen_points(-8.0)
    h.drag(h.screen_point(here), h.screen_point(there))


def p4_negative():
    p = sd.draft_panel()
    a = p.angle.value() if p else 0
    h.check("P4 dragged the other way: a negative angle", -30 < a < 0, a)
    v = h.solid_volume()
    expect = front_right(a, 2)
    h.check("P4 the face leans out (wider at the top)", sd.close(v, expect), (v, expect, a))
    h.check("P4 no message", msg(p) == "", msg(p))
    h.shot("p4-negative")
    if p:
        ui.type_into(p.angle.widget, "3")


def p4_ok():
    h.task_button("OK")


def p4_done():
    h.check("P4 closed", not dialog_open())
    h.check("P4 3 degrees again", sd.close(h.solid_volume(), s["v3"]), h.solid_volume())
    part_ok("P4")


# -- Path 5: click the pull arrow ---------------------------------------------------------------
def p5_draft():
    sd.modify_menu("Draft")


def p5_xy():
    h.fit()
    pl.click_square("XY_Plane")  # where the XY square shows


def p5_front():
    h.fit()
    h.click(FRONT)


def p5_arrow():
    p = sd.draft_panel()
    h.check("P5 the front face previewed", p is not None and p.target is not None, msg(p))
    h.check("P5 no message", msg(p) == "", msg(p))
    s["p5_unflipped"] = h.solid_volume()
    if p is None or p.arrow is None:
        h.check("P5 a pull arrow", False)
        return
    h.fit()
    h.click(p.arrow.tip())


def p5_flipped():
    p = sd.draft_panel()
    h.check("P5 clicking the arrow flips the pull direction", p is not None and p.flip.isChecked())
    v = h.solid_volume()
    h.check("P5 the front face now leans out", v > s["p5_unflipped"], (v, s["p5_unflipped"]))
    h.check("P5 the click picked no face", p is not None and len(p.names()) == 1, p and p.names())
    h.shot("p5-flipped")
    if p and p.arrow is not None:
        h.fit()
        h.click(p.arrow.tip())


def p5_unflipped():
    p = sd.draft_panel()
    h.check("P5 again: back", p is not None and not p.flip.isChecked())
    h.check(
        "P5 the preview too",
        sd.close(h.solid_volume(), s["p5_unflipped"]),
        (h.solid_volume(), s["p5_unflipped"], msg(p)),
    )
    h.task_button("Cancel")


def p5_cancelled():
    h.check("P5 Cancel: as before", sd.close(h.solid_volume(), s["v3"]), h.solid_volume())
    h.check("P5 two drafts", len(sd.drafts()) == 2, sd.drafts())
    part_ok("P5")


# -- Path 6: save, close, reopen, edit ----------------------------------------------------------
def p6_save():
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-draft-qa-"), "draft_qa.FCStd")
    s["path"] = path
    doc().saveAs(path)
    h.check("P6 saved", os.path.isfile(path), path)
    App.closeDocument(doc().Name)


def p6_open():
    App.openDocument(s["path"])
    h.fit()


def p6_reopened():
    h.check("P6 same part", sd.close(h.solid_volume(), s["v3"]), h.solid_volume())
    part_ok("P6 reopened")
    b.timeline_double_click("Draft 1", click_first=True)


def p6_edit():
    p = sd.draft_panel()
    h.check("P6 Draft 1 opens after reopening", p is not None and p.editing)
    h.check("P6 3 degrees", p is not None and abs(p.angle.value() - 3) < 1e-9)
    h.check(
        "P6 XY shown",
        p is not None and p.plane_box.button.text() == "XY-plane",
        p and p.plane_box.button.text(),
    )
    h.check("P6 its face shown", p is not None and len(p.names()) == 1)
    h.check("P6 not flipped", p is not None and not p.flip.isChecked())
    if p:
        ui.type_into(p.angle.widget, "4")


def p6_ok():
    h.task_button("OK")


def p6_four():
    v = h.solid_volume()
    expect = front_right(4, 2)
    h.check("P6 4 degrees; Draft 2 follows", sd.close(v, expect), (v, expect))
    part_ok("P6 edited")
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def p6_undo():
    h.check("P6 Ctrl+Z: 3 again", sd.close(h.solid_volume(), s["v3"]), h.solid_volume())
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def p6_redo():
    h.check("P6 Ctrl+Y: 4", sd.close(h.solid_volume(), front_right(4, 2)), h.solid_volume())
    part_ok("P6 redo")


# -- Path 7: a moulded part: draft the sides, then shell -----------------------------------------
def p7_draft():
    h.check("P7 a new box", sd.close(h.solid_volume(), sd.BOX), h.solid_volume())
    Gui.Selection.clearSelection()
    sd.modify_menu("Draft")


def p7_xy():
    h.fit()
    pl.click_square("XY_Plane")  # where the XY square shows


def p7_front():
    h.fit()
    h.click(FRONT)


def p7_right():
    h.click(RIGHT)


def p7_back():
    p = sd.draft_panel()
    h.check("P7 front and right picked", p is not None and len(p.names()) == 2, p and p.names())
    h.view().viewRear()  # the person turns the part round to reach the back and the left
    h.view().fitAll()
    h.click(V(20, 30, 5))


def p7_left():
    p = sd.draft_panel()
    h.check("P7 the back picked", p is not None and len(p.names()) == 3, p and p.names())
    h.view().viewLeft()
    h.view().fitAll()
    pl.click_on_plane(V(0, 15, 5))


def p7_type():
    h.fit()
    p = sd.draft_panel()
    h.check("P7 four sides picked", p is not None and len(p.names()) == 4, p and p.names())
    if p:
        ui.type_into(p.angle.widget, "3")


def p7_ok():
    h.task_button("OK")


def p7_shell():
    k = tan(3)
    outer = 10 / 6.0 * (1200 + 4 * (40 - 10 * k) * (30 - 10 * k) + (40 - 20 * k) * (30 - 20 * k))
    h.check("P7 four sides drafted", sd.close(h.solid_volume(), outer), h.solid_volume())
    h.ribbon("Shell")


def p7_top():
    h.fit()
    h.click(TOP)


def p7_shell_ok():
    p = sd.shell_panel()
    h.check("P7 the drafted top picked", p is not None and len(p.names()) == 1, p and p.names())
    h.task_button("OK")


def p7_shelled():
    v = h.solid_volume()
    h.check("P7 a drafted open box, 1 mm", sd.close(v, moulded(3, 1)), (v, moulded(3, 1)))
    part_ok("P7 shell")
    h.fit()
    b.timeline_double_click("Draft 1", click_first=True)


def p7_edit():
    p = sd.draft_panel()
    h.check("P7 editing the draft under the shell", p is not None and p.editing)
    if p:
        ui.type_into(p.angle.widget, "5")


def p7_edit_ok():
    v = h.solid_volume()
    h.check("P7 the preview shells the new draft", sd.close(v, moulded(5, 1)), (v, moulded(5, 1)))
    h.task_button("OK")


def p7_followed():
    v = h.solid_volume()
    h.check("P7 the shell follows 5 degrees", sd.close(v, moulded(5, 1)), (v, moulded(5, 1)))
    part_ok("P7 edited")
    h.shot("p7-moulded")
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def p7_undo():
    h.check("P7 Ctrl+Z: 3 degrees", sd.close(h.solid_volume(), moulded(3, 1)), h.solid_volume())
    part_ok("P7 undo")
    h.check("P7 nothing in the Report view", not sd.report_errors(), sd.report_errors())


h.run(
    "shell_draft_qa_draft",
    tl.watched(
        sd.box_steps("DraftQA")
        + [
            made,
            p1_draft,
            p1_front_first,
            p1_front_is_plane,
            p1_cleared,
            p1_xy,
            p1_face,
            p1_enter,
            p1_done,
            p2_draft,
            p2_xy,
            p2_ok,
            p2_refused,
            p2_esc,
            p2_closed,
            p3_draft,
            p3_xy,
            p3_right,
            p3_type,
            p3_q,
            p3_after,
            p3_closed,
            p4_edit,
            p4_open,
            p4_far,
            p4_ok_waits,
            p4_negative,
            p4_ok,
            p4_done,
            p5_draft,
            p5_xy,
            p5_front,
            p5_arrow,
            p5_flipped,
            p5_unflipped,
            p5_cancelled,
            p6_save,
            p6_open,
            p6_reopened,
            p6_edit,
            p6_ok,
            p6_four,
            p6_undo,
            p6_redo,
        ]
        + sd.box_steps("DraftQA2")
        + [
            p7_draft,
            p7_xy,
            p7_front,
            p7_right,
            p7_back,
            p7_left,
            p7_type,
            p7_ok,
            p7_shell,
            p7_top,
            p7_shell_ok,
            p7_shelled,
            p7_edit,
            p7_edit_ok,
            p7_followed,
            p7_undo,
        ]
    ),
)
