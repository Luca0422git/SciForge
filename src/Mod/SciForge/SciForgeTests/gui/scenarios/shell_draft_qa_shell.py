# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shell the way Fusion users use it, trying to break it (QA, only real input).
A 40 x 30 x 10 box made with Create Sketch / E.

Path 1, a beginner: Shell, OK with nothing picked (the dialog says what to pick and
        stays), Enter over the view (same), Esc: nothing made, no undo step added.
Path 2, picks in the "wrong" order: the body row in the browser first (hollow), then a
        face of the part (the face is taken away instead), the body again (hollow again),
        the selection box's x (nothing picked: the part is whole again), Esc.
Path 3, Esc while the blue arrow is being dragged (the mouse button still down), then
        the button let go: the dialog is closed, the part is as it was, no crash.
Path 4, values while the preview runs: 3 mm and Both and 1.5 mm out typed in a row;
        "abc" (explained, OK waits); 0 (explained); Delete does nothing; the arrow
        dragged far through the surface (a thin wall, never below zero) and far into the
        part (it stops at the thickest wall that fits and says so: Luca's decision of
        2026-10-21); Esc.
Path 5, another command's key while the dialog is open: E keeps the shell (like any
        command start) and opens Extrude; Esc. Shell with nothing picked, then F: no
        shell is made, Fillet opens; Esc.
Path 6, editing from the timeline twice (3 mm, then Outside), Ctrl+Z twice, Ctrl+Y
        twice, then back to Inside 2 mm.
Path 7, Create Sketch on the shell's floor, a circle, E 5 mm (a boss on the floor); the
        shell edited to 3 mm: the boss follows the floor; Press Pull on the outside wall.
Path 8, save, close, reopen; the shell edited to Both (FreeCAD's shell swapped for
        SciForge's under the boss and the Press Pull); Ctrl+Z; Ctrl+Y.

Volumes by hand (shell_draft_steps): open box 12000 - (40-2t)(30-2t)(10-t); Both with
the top taken away (40+2o)(30+2o)(10+o) - (40-2i)(30-2i)(10-i); a boss pi r^2 h.
"""

import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import shell_draft_steps as sd
from SciForgeTests.gui import timeline_input as tl
from SciForgeTests.gui import widget_input as w

V = App.Vector
s = {}
TOP = V(20, 15, 10)
FRONT = V(20, 0, 5)
RIGHT = V(40, 15, 5)
BOSS_R = 4.0
BOSS_H = 5.0


def doc():
    return App.ActiveDocument


def dialog_open():
    return bool(Gui.Control.activeDialog())


def msg(p):
    return p.message.text() if p is not None else ""


def boss():
    return math.pi * BOSS_R * BOSS_R * BOSS_H


def both_open(i, o):
    return (40 + 2 * o) * (30 + 2 * o) * (10 + o) - (40 - 2 * i) * (30 - 2 * i) * (10 - i)


def part_ok(where):
    bad = [o.Label for o in doc().Objects if "Invalid" in o.State or "Error" in o.State]
    h.check("%s: nothing in error" % where, not bad, bad)
    h.check("%s: valid solid" % where, h.body().Shape.isValid())
    tip = h.body().Tip
    h.check("%s: the part is shown" % where, tip is not None and tip.ViewObject.isVisible())
    h.check("%s: nothing left see-through" % where, not b.see_through(), b.see_through())


def made():
    s["undo"] = list(doc().UndoNames)
    h.check("the box is a solid of 12000", sd.close(h.solid_volume(), sd.BOX))


# -- Path 1: OK with nothing picked -----------------------------------------------------------
def p1_shell():
    Gui.Selection.clearSelection()
    h.ribbon("Shell")


def p1_ok():
    h.check("P1 the dialog waits", sd.shell_panel() is not None and dialog_open())
    h.task_button("OK")


def p1_ok_refused():
    p = sd.shell_panel()
    h.check("P1 OK with nothing picked keeps the dialog open", p is not None and dialog_open())
    h.check("P1 and says what to pick", "Select the faces" in msg(p), msg(p))
    sd.no_popups("OK with nothing picked")
    h.check("P1 nothing made", not sd.shells() and sd.close(h.solid_volume(), sd.BOX))
    h.press(QtCore.Qt.Key_Return)


def p1_enter_refused():
    p = sd.shell_panel()
    h.check("P1 Enter over the view: still open", p is not None and dialog_open())
    h.shot("p1-ok-nothing")
    h.press(QtCore.Qt.Key_Escape)


def p1_closed():
    h.check("P1 Esc closes", not dialog_open() and sd.shell_panel() is None)
    h.check("P1 nothing made", not sd.shells() and sd.close(h.solid_volume(), sd.BOX))
    h.check("P1 no undo step added", list(doc().UndoNames) == s["undo"], doc().UndoNames)
    part_ok("P1")


# -- Path 2: the body first, then a face, the body again, x ------------------------------
def p2_shell():
    h.ribbon("Shell")


def p2_body_row():
    sd.click_browser_row("Body")


def p2_hollow():
    p = sd.shell_panel()
    h.check("P2 the body row picks the body", p is not None and p.whole, p and p.picked)
    h.check("P2 box says Body", p is not None and p.selection.button.text() == "Body")
    v = h.solid_volume()
    h.check("P2 hollow 1 mm: 12000 - 38*28*8", sd.close(v, sd.hollow(1)), v)
    h.shot("p2-hollow")
    h.fit()
    h.click(TOP)


def p2_face():
    p = sd.shell_panel()
    h.check("P2 a face click takes the face away instead", p is not None and not p.whole)
    h.check("P2 one face", p is not None and len(p.names()) == 1, p and p.names())
    v = h.solid_volume()
    h.check("P2 open box 1 mm", sd.close(v, sd.open_top(1)), v)
    h.check("P2 still one shell step", len(sd.shells()) == 1, sd.shells())
    sd.click_browser_row("Body")


def p2_hollow_again():
    p = sd.shell_panel()
    h.check("P2 the body row again: hollow again", p is not None and p.whole)
    v = h.solid_volume()
    h.check("P2 hollow 1 mm again", sd.close(v, sd.hollow(1)), v)
    if p:
        w.click(p.selection.clear)


def p2_cleared():
    p = sd.shell_panel()
    h.check("P2 x: nothing picked", p is not None and not p.has_picks())
    h.check("P2 box says Select", p is not None and p.selection.button.text() == "Select")
    h.check("P2 the part is whole again", sd.close(h.solid_volume(), sd.BOX), h.solid_volume())
    h.check("P2 no shell step left", not sd.shells(), sd.shells())
    h.check("P2 no message", msg(p) == "", msg(p))
    h.press(QtCore.Qt.Key_Escape)


def p2_closed():
    h.check("P2 closed", not dialog_open())
    h.check("P2 nothing made", not sd.shells() and sd.close(h.solid_volume(), sd.BOX))
    part_ok("P2")


# -- Path 3: Esc while dragging the arrow ---------------------------------------------------
def p3_shell():
    h.ribbon("Shell")


def p3_pick():
    h.fit()
    h.click(TOP)


def p3_press_arrow():
    p = sd.shell_panel()
    if not h.check("P3 an arrow to drag", p is not None and len(p.arrows) == 1):
        return
    start, end = sd.arrow_screen(p, along=2.0)
    s["p3_end"] = end
    widget = h.gl_widget()
    h.move(start)
    QtTest.QTest.mousePress(widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, start)
    for i in range(1, 9):
        pos = QtCore.QPointF(
            start.x() + (end.x() - start.x()) * i / 8.0, start.y() + (end.y() - start.y()) * i / 8.0
        )
        event = QtGui_mouse_move(widget, pos)
        QtWidgets.QApplication.sendEvent(widget, event)
        QtWidgets.QApplication.processEvents()


def QtGui_mouse_move(widget, pos):
    from PySide import QtGui

    return QtGui.QMouseEvent(
        QtCore.QEvent.MouseMove,
        pos,
        QtCore.QPointF(widget.mapToGlobal(pos.toPoint())),
        QtCore.Qt.NoButton,
        QtCore.Qt.LeftButton,
        QtCore.Qt.NoModifier,
    )


def p3_esc():
    p = sd.shell_panel()
    h.check(
        "P3 the wall follows the drag",
        p is not None and p.inside.value() > 1.2,
        p and p.inside.value(),
    )
    h.press(QtCore.Qt.Key_Escape)


def p3_release():
    widget = h.gl_widget()
    end = s.get("p3_end") or QtCore.QPoint(200, 200)
    QtTest.QTest.mouseRelease(widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, end)
    QtWidgets.QApplication.processEvents()


def p3_after():
    h.check("P3 Esc during the drag closed the dialog", not dialog_open())
    h.check("P3 nothing made", not sd.shells() and sd.close(h.solid_volume(), sd.BOX))
    part_ok("P3")
    h.fit()
    h.click(TOP)


def p3_view_still_works():
    picked = sd.selected()
    h.check("P3 the view still picks faces after that", len(picked) == 1, picked)
    Gui.Selection.clearSelection()


# -- Path 4: values while the preview runs ----------------------------------------------------
def p4_shell():
    h.ribbon("Shell")


def p4_pick():
    h.fit()
    h.click(TOP)


def p4_fast():
    p = sd.shell_panel()
    if not h.check("P4 a preview", p is not None and p.target is not None, msg(p)):
        return
    ui.type_into(p.inside.widget, "3")
    ui.choose(p.direction, "Both")
    ui.type_into(p.outside.widget, "1.5")


def p4_fast_result():
    v = h.solid_volume()
    h.check("P4 3 in / 1.5 out typed fast: 43*33*11.5 - 34*24*7", sd.close(v, both_open(3, 1.5)), v)
    p = sd.shell_panel()
    h.check("P4 no message", msg(p) == "", msg(p))
    if p:
        ui.type_into(p.inside.widget, "abc")


def p4_garbage():
    p = sd.shell_panel()
    h.check("P4 'abc' is explained in the dialog", msg(p).startswith("⚠"), msg(p))
    h.check("P4 the preview stays", sd.close(h.solid_volume(), both_open(3, 1.5)))
    h.task_button("OK")


def p4_garbage_ok():
    p = sd.shell_panel()
    h.check("P4 OK waits while the value is wrong", p is not None and dialog_open())
    sd.no_popups("a wrong value")
    if p:
        ui.type_into(p.inside.widget, "0")


def p4_zero():
    p = sd.shell_panel()
    h.check("P4 0 mm is explained", "more than 0" in msg(p), msg(p))
    h.check("P4 the last good preview stays", sd.close(h.solid_volume(), both_open(3, 1.5)))
    if p:
        ui.choose(p.direction, "Inside")
        ui.type_into(p.inside.widget, "2")


def p4_two():
    v = h.solid_volume()
    h.check("P4 back to Inside 2", sd.close(v, sd.open_top(2)), v)
    h.press(QtCore.Qt.Key_Delete)


def p4_delete():
    h.check("P4 Delete does nothing to the part", dialog_open() and len(sd.shells()) == 1)
    sd.no_popups("Delete in the dialog")
    p = sd.shell_panel()
    if p is None or not p.arrows:
        h.check("P4 arrow to drag", False)
        return
    h.fit()
    start, end = sd.arrow_screen(p, along=-12.0)
    h.drag(start, end)


def p4_dragged_out():
    p = sd.shell_panel()
    t = p.inside.value() if p else -1
    h.check("P4 dragged through the surface: a thin wall, not below 0", 0 < t < 1, t)
    v = h.solid_volume()
    h.check("P4 the preview is that thin wall", sd.close(v, sd.open_top(t)), (v, t))
    h.check("P4 no message", msg(p) == "", msg(p))
    s["thin"] = v
    if p is None or not p.arrows:
        return
    h.fit()
    start, end = sd.arrow_screen(p, along=25.0)
    h.drag(start, end)


def p4_dragged_in():
    """Luca, 2026-10-21: dragged far into the part, the wall stops at the thickest that fits
    (about 9.99 mm here; it was refused, with the thickest wall in the message)."""
    p = sd.shell_panel()
    t = p.inside.value() if p else 0
    note = p.limit_label.text() if p is not None and p.limit_label.isVisible() else ""
    h.check("P4 dragged far into the part: the wall stops just under 10 mm", 9.0 < t < 10.0, t)
    h.check("P4 the note says so", note == "Largest that fits here: %.2f mm" % t, note)
    h.check("P4 no error", msg(p) == "", msg(p))
    v = h.solid_volume()
    h.check("P4 the preview is that wall", sd.close(v, sd.open_top(t)), (v, t))
    h.check("P4 nothing in the Report view", not sd.report_errors(), sd.report_errors())


p4_dragged_in.wait_ms = 1500


def p4_esc():
    h.shot("p4-too-thick")
    h.press(QtCore.Qt.Key_Escape)


def p4_closed():
    h.check("P4 Esc: nothing made", not dialog_open() and not sd.shells())
    h.check("P4 the part is whole", sd.close(h.solid_volume(), sd.BOX))
    part_ok("P4")


# -- Path 5: another command's key while the dialog is open ---------------------------------
def p5_shell():
    h.ribbon("Shell")


def p5_pick():
    h.fit()
    h.click(TOP)


def p5_type():
    p = sd.shell_panel()
    if p:
        ui.type_into(p.inside.widget, "2")


def p5_e():
    h.check("P5 previewed", sd.close(h.solid_volume(), sd.open_top(2)), h.solid_volume())
    h.press("e")


def p5_after_e():
    from sciforge import taskui

    h.check("P5 E kept the shell", len(sd.shells()) == 1 and sd.shell_panel() is None)
    h.check("P5 the shell: open box 2 mm", sd.close(h.solid_volume(), sd.open_top(2)))
    current = taskui.current()
    h.check(
        "P5 Extrude's dialog is open",
        current is not None and current.title == "Extrude",
        current and current.title,
    )
    sd.no_popups("E with Shell open")
    h.press(QtCore.Qt.Key_Escape)


def p5_extrude_closed():
    h.check("P5 Esc closes Extrude", not dialog_open())
    h.check("P5 the shell stays", sd.close(h.solid_volume(), sd.open_top(2)))
    h.check("P5 timeline shows Shell 1", "Shell 1" in sd.timeline_titles(), sd.timeline_titles())
    part_ok("P5")
    s["v"] = h.solid_volume()
    s["undo"] = list(doc().UndoNames)
    Gui.Selection.clearSelection()
    h.ribbon("Shell")


def p5_f():
    h.check("P5 a second Shell waits", sd.shell_panel() is not None)
    h.press("f")


def p5_after_f():
    from sciforge import taskui

    current = taskui.current()
    h.check("P5 F: Fillet's dialog", current is not None and current.title in ("Fillet",))
    h.check("P5 no second shell", len(sd.shells()) == 1, sd.shells())
    h.press(QtCore.Qt.Key_Escape)


def p5_fillet_closed():
    h.check("P5 closed", not dialog_open())
    h.check("P5 the part as it was", sd.close(h.solid_volume(), s["v"]), h.solid_volume())
    h.check("P5 no undo step from the empty dialogs", list(doc().UndoNames) == s["undo"])
    part_ok("P5 end")


# -- Path 6: two timeline edits, undo/redo ----------------------------------------------------
def p6_edit():
    h.fit()
    b.timeline_double_click("Shell 1", click_first=True)


def p6_open():
    p = sd.shell_panel()
    h.check("P6 the shell opens to edit", p is not None and p.editing)
    h.check("P6 2 mm shown", p is not None and abs(p.inside.value() - 2) < 1e-9)
    h.check("P6 its face shown picked", p is not None and len(p.names()) == 1)
    if p:
        ui.type_into(p.inside.widget, "3")


def p6_ok():
    h.task_button("OK")


def p6_three():
    h.check("P6 3 mm", sd.close(h.solid_volume(), sd.open_top(3)), h.solid_volume())
    b.timeline_double_click("Shell 1", click_first=True)


def p6_open2():
    p = sd.shell_panel()
    h.check("P6 the second edit shows 3 mm", p is not None and abs(p.inside.value() - 3) < 1e-9)
    if p:
        ui.choose(p.direction, "Outside")


def p6_ok2():
    h.check("P6 Outside previews", sd.close(h.solid_volume(), sd.outside_sharp(1)))
    h.task_button("OK")


def p6_outside():
    h.check("P6 Outside 1 kept", sd.close(h.solid_volume(), sd.outside_sharp(1)))
    h.check("P6 still one step", len(sd.shells()) == 1, sd.shells())
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def p6_undo1():
    h.check("P6 Ctrl+Z: 3 mm inside", sd.close(h.solid_volume(), sd.open_top(3)), h.solid_volume())
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def p6_undo2():
    h.check("P6 Ctrl+Z: 2 mm inside", sd.close(h.solid_volume(), sd.open_top(2)), h.solid_volume())
    part_ok("P6 undo")
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def p6_redo1():
    h.check("P6 Ctrl+Y: 3 mm", sd.close(h.solid_volume(), sd.open_top(3)), h.solid_volume())
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def p6_redo2():
    h.check("P6 Ctrl+Y: Outside", sd.close(h.solid_volume(), sd.outside_sharp(1)))
    part_ok("P6 redo")
    b.timeline_double_click("Shell 1", click_first=True)


def p6_back():
    p = sd.shell_panel()
    h.check(
        "P6 the redone edit opens as Outside",
        p is not None and p.direction.currentText() == "Outside",
    )
    if p:
        ui.choose(p.direction, "Inside")
        ui.type_into(p.inside.widget, "2")


def p6_back_ok():
    h.task_button("OK")


def p6_done():
    h.check("P6 Inside 2 again", sd.close(h.solid_volume(), sd.open_top(2)), h.solid_volume())
    part_ok("P6 end")


# -- Path 7: a boss on the floor, the shell edited, Press Pull -----------------------------------
FLOOR = V(20, 15, 2)


def p7_sketch():
    Gui.Selection.clearSelection()
    h.ribbon("Create Sketch")


def p7_floor():
    h.fit()
    h.click(FLOOR)


def p7_draw():
    sk = h.in_sketch()
    if not h.check("P7 a sketch on the floor", sk is not None):
        return
    z = sk.getGlobalPlacement().Base.z
    h.check("P7 the sketch lies on the floor (z = 2)", abs(z - 2.0) < 1e-6, z)
    x, y = h.to_sketch(sk, V(20, 15, 2))
    h.draw_circle(sk, x, y, BOSS_R)


def p7_finish():
    h.ribbon("Finish Sketch")


def p7_e():
    h.fit()
    h.press("e")


def p7_distance():
    p = b.active_panel()
    if p is not None and getattr(p, "distance", None) is not None:
        ui.type_into(p.distance.widget, "%g" % BOSS_H)


def p7_extrude_ok():
    h.task_button("OK")


def p7_boss():
    v = h.solid_volume()
    h.check(
        "P7 a boss on the floor", sd.close(v, sd.open_top(2) + boss()), (v, sd.open_top(2) + boss())
    )
    part_ok("P7 boss")
    b.timeline_double_click("Shell 1", click_first=True)


def p7_edit():
    p = sd.shell_panel()
    h.check("P7 editing the shell under the boss", p is not None and p.editing)
    if p:
        ui.type_into(p.inside.widget, "3")


def p7_edit_preview():
    v = h.solid_volume()
    # the shell is edited with the timeline rolled to it (Fusion): the boss after it waits
    # until OK (edit_rollback / preview.hold), then follows the floor (p7_followed)
    h.check("P7 the preview: the shell alone, the boss waits", sd.close(v, sd.open_top(3)), v)
    p = sd.shell_panel()
    h.check("P7 no message", msg(p) == "", msg(p))
    h.task_button("OK")


def p7_followed():
    v = h.solid_volume()
    h.check("P7 the boss follows the floor (3 mm)", sd.close(v, sd.open_top(3) + boss()), v)
    top = max(
        f.BoundBox.ZMax for f in h.body().Shape.Faces if f.Surface.TypeId == "Part::GeomCylinder"
    )
    h.check("P7 the boss now ends at z = 8", abs(top - 8.0) < 1e-6, top)
    part_ok("P7 shell edited")
    h.press("q")


def p7_pp_face():
    h.fit()
    h.click(FRONT)


def p7_pp_type():
    from sciforge import presspull_ui

    p = presspull_ui.PressPullPanel.last
    if h.check("P7 Press Pull took the outside wall", p is not None and not p._closed):
        ui.type_into(p.field.widget, "2")


def p7_pp_ok():
    h.task_button("OK")


def p7_pp_done():
    v = h.solid_volume()
    expect = sd.open_top(3) + boss() + 40 * 10 * 2
    h.check("P7 the wall pulled out 2 mm (+800)", sd.close(v, expect), (v, expect))
    part_ok("P7 Press Pull")
    s["v7"] = v
    h.shot("p7-boss-pressed")


# -- Path 8: save, close, reopen, edit to Both -------------------------------------------------
def p8_save():
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-shell-qa-"), "shell_qa.FCStd")
    s["path"] = path
    doc().saveAs(path)
    h.check("P8 saved", os.path.isfile(path), path)
    App.closeDocument(doc().Name)


def p8_open():
    App.openDocument(s["path"])
    h.fit()


def p8_reopened():
    h.check("P8 reopened: same part", sd.close(h.solid_volume(), s["v7"]), h.solid_volume())
    part_ok("P8 reopened")
    b.timeline_double_click("Shell 1", click_first=True)


def p8_edit():
    p = sd.shell_panel()
    h.check("P8 the shell opens after reopening", p is not None and p.editing)
    h.check("P8 3 mm, Inside", p is not None and abs(p.inside.value() - 3) < 1e-9)
    h.check("P8 Tangent Chain remembered", p is not None and p.tangent.isChecked())
    if p:
        ui.choose(p.direction, "Both")


def p8_both():
    v = h.solid_volume()
    expect = both_open(3, 1)  # the boss and the Press Pull wait until OK (rolled back)
    h.check("P8 Both previews, the later steps wait", sd.close(v, expect), (v, expect))
    p = sd.shell_panel()
    h.check("P8 no message", msg(p) == "", msg(p))
    h.task_button("OK")


def p8_after():
    v = h.solid_volume()
    expect = both_open(3, 1) + boss() + 42 * 11 * 2
    h.check("P8 Both kept: the later steps follow", sd.close(v, expect), (v, expect))
    sh = sd.shells()
    h.check(
        "P8 one shell (SciForge's now)", len(sh) == 1 and sh[0].TypeId != "PartDesign::Thickness"
    )
    h.check("P8 still Shell 1", "Shell 1" in sd.timeline_titles(), sd.timeline_titles())
    part_ok("P8 Both")
    s["v8"] = v
    h.shot("p8-both")
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def p8_undo():
    h.check("P8 Ctrl+Z: back to Inside", sd.close(h.solid_volume(), s["v7"]), h.solid_volume())
    sh = sd.shells()
    h.check("P8 FreeCAD's shell is back", len(sh) == 1 and sh[0].TypeId == "PartDesign::Thickness")
    part_ok("P8 undo")
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def p8_redo():
    h.check("P8 Ctrl+Y: Both again", sd.close(h.solid_volume(), s["v8"]), h.solid_volume())
    part_ok("P8 redo")
    h.check("P8 nothing in the Report view", not sd.report_errors(), sd.report_errors())


h.run(
    "shell_draft_qa_shell",
    tl.watched(
        sd.box_steps("ShellQA")
        + [
            made,
            p1_shell,
            p1_ok,
            p1_ok_refused,
            p1_enter_refused,
            p1_closed,
            p2_shell,
            p2_body_row,
            p2_hollow,
            p2_face,
            p2_hollow_again,
            p2_cleared,
            p2_closed,
            p3_shell,
            p3_pick,
            p3_press_arrow,
            p3_esc,
            p3_release,
            p3_after,
            p3_view_still_works,
            p4_shell,
            p4_pick,
            p4_fast,
            p4_fast_result,
            p4_garbage,
            p4_garbage_ok,
            p4_zero,
            p4_two,
            p4_delete,
            p4_dragged_out,
            p4_dragged_in,
            p4_esc,
            p4_closed,
            p5_shell,
            p5_pick,
            p5_type,
            p5_e,
            p5_after_e,
            p5_extrude_closed,
            p5_f,
            p5_after_f,
            p5_fillet_closed,
            p6_edit,
            p6_open,
            p6_ok,
            p6_three,
            p6_open2,
            p6_ok2,
            p6_outside,
            p6_undo1,
            p6_undo2,
            p6_redo1,
            p6_redo2,
            p6_back,
            p6_back_ok,
            p6_done,
            p7_sketch,
            p7_floor,
            p7_draw,
            p7_finish,
            p7_e,
            p7_distance,
            p7_extrude_ok,
            p7_boss,
            p7_edit,
            p7_edit_preview,
            p7_followed,
            p7_pp_face,
            p7_pp_type,
            p7_pp_ok,
            p7_pp_done,
            p8_save,
            p8_open,
            p8_reopened,
            p8_edit,
            p8_both,
            p8_after,
            p8_undo,
            p8_redo,
        ]
    ),
)
