# SPDX-License-Identifier: LGPL-2.1-or-later
"""Thread the way Fusion users really use it, trying to break it (QA, only real input), on a
40 x 30 x 10 box with a boss d10 x 12:

Path T1, beginner: Thread with nothing selected, OK, a click on the flat top (does not light
         up), Enter over the view, Esc. Nothing is made, nothing in the undo history.
Path T2, wrong order and values while the preview runs: Full Length off and a length longer
         than the boss typed before any pick, then the boss side; the length arrow dragged
         far past the end and far back; Modeled; length 8 and offset 2 typed; Enter over the
         3D view finishes it.
Path T3, edit from the timeline twice with a person's double-click (Modeled off + Left hand;
         another size and Cancel), then undo / redo.
Path T4, a hole made with Hole, its wall clicked, then CREATE > Thread: an inside thread at
         once; Modeled.
Path T5, another command's key while the dialog is open: H keeps a good thread and opens
         Hole; E drops a thread that cannot be made and opens Extrude.
Path T6, a parameter typed in Thread Length; the thread follows it; a typo is explained.
Path T7, Ctrl+S with the dialog open; close, reopen: cosmetic threads drawn again, edit one.

Hand-derived volumes: thread_core.removed_volume (the ISO 68-1 groove per mm of thread).
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
from SciForgeTests.gui import hole_steps as hs
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import timeline_input as ti
from SciForgeTests.gui import versions_input as vi

V = App.Vector
s = {}
R, HEIGHT = 5.0, 12.0
BOSS = hs.BOX + math.pi * R * R * HEIGHT
# On the boss's side facing the viewer, nearer its top end (z 22) than its foot (z 10).
SIDE = V(20 + R * math.cos(math.radians(-50)), 15 + R * math.sin(math.radians(-50)), 19)
TOP = V(5, 25, 10)


def doc():
    return App.ActiveDocument


def dialog_open():
    return bool(Gui.Control.activeDialog())


def panel():
    return hs.thread_panel()


def msg():
    return hs.message(panel())


def near(a, c, tol=1e-6):
    return abs(a - c) <= tol * max(1.0, abs(c))


def removed(length, pitch=1.5):
    from sciforge import thread_core

    return thread_core.removed_volume(R, pitch, False, R, length)


def drawn():
    from sciforge import thread_ui

    return thread_ui.CosmeticThreads.count(doc().Name)


def part_ok(where):
    broken = [o.Label for o in doc().Objects if "Invalid" in o.State or "Error" in o.State]
    h.check("%s: nothing in error" % where, not broken, broken)
    h.check("%s: valid solid" % where, h.body().Shape.isValid())
    tip = h.body().Tip
    h.check("%s: the part is shown" % where, tip is not None and tip.ViewObject.isVisible())


def open_thread():
    Gui.Selection.clearSelection()
    si.menu_item("CREATE", "Thread")


def slow(fn, ms=2500):
    fn.wait_ms = ms  # a modeled thread takes a moment (FreeCAD is busy meanwhile)
    return fn


# -- T1: beginner -------------------------------------------------------------------------------
def t1_open():
    h.check("boss d10 x 12 on the box", hs.close(h.solid_volume(), BOSS), h.solid_volume())
    s["undo"] = doc().UndoCount
    s["objects"] = len(doc().Objects)
    open_thread()


def t1_ok():
    p = panel()
    h.check("T1 Thread opens with nothing selected", p is not None and dialog_open())
    hs.no_popups("Thread with nothing selected")
    h.task_button("OK")


def t1_refused():
    h.check("T1 OK with nothing picked keeps the dialog", dialog_open() and panel() is not None)
    h.check("T1 it says to click a round face", "cylindrical" in msg().lower(), msg())
    h.fit()
    h.click(TOP)


def t1_flat():
    p = panel()
    h.check("T1 a flat face is not taken", p is not None and not p.faces and p.target is None)
    h.check("T1 nothing selected", not Gui.Selection.getSelectionEx())
    h.press(QtCore.Qt.Key_Return)


def t1_enter():
    h.check("T1 Enter with nothing picked keeps the dialog", dialog_open())
    h.press(QtCore.Qt.Key_Escape)


def t1_esc():
    h.check("T1 Esc closes", not dialog_open())
    h.check("T1 nothing new", len(doc().Objects) == s["objects"], len(doc().Objects))
    h.check("T1 undo history unchanged", doc().UndoCount == s["undo"], doc().UndoCount)
    h.check("T1 no undo step left open", not doc().HasPendingTransaction)


# -- T2: values first, arrow dragged far, Enter --------------------------------------------------
def t2_open():
    open_thread()


def t2_values_first():
    p = panel()
    if p is None:
        h.check("T2 Thread open", False)
        return
    hs.click_checkbox(p.full_length)
    ui.type_into(p.length.widget, "30")


def t2_click():
    p = panel()
    h.check("T2 a length alone builds nothing", p is not None and p.target is None)
    h.check("T2 and says nothing wrong", "⚠" not in msg(), msg())
    h.fit()
    h.click(SIDE)


def t2_picked():
    p = panel()
    h.check("T2 the boss side is picked", p is not None and p.target is not None, msg())
    if p is None:
        return
    h.check("T2 M10x1.5 from the d10 boss", p.designation.currentText() == "M10x1.5")
    h.check("T2 Full Length stays off", not p.full_length.isChecked())
    h.check(
        "T2 a length longer than the boss is cut to the boss",
        near(p.length.value(), HEIGHT),
        p.length.value(),
    )
    h.check("T2 no warning", "⚠" not in msg(), msg())


def t2_drag_far():
    p = panel()
    arrow = p.draggers.get("length") if p else None
    if arrow is None:
        h.check("T2 length arrow to drag", False)
        return
    hs.type_into(p.length.widget, "6")
    s["drag"] = True


def t2_drag_far2():
    p = panel()
    arrow = p.draggers.get("length") if p else None
    if arrow is None:
        h.check("T2 length arrow shown again", False)
        return
    hs.drag_arrow(p.length_origin, p.length_direction, arrow.distance(), 30.0)


def t2_dragged_far():
    p = panel()
    length = p.length.value() if p else 0
    h.check(
        "T2 dragged past the end: the length stops at the boss's end", near(length, HEIGHT), length
    )
    arrow = p.draggers.get("length") if p else None
    h.check(
        "T2 the arrow sits at the end of the thread",
        arrow is not None and near(arrow.distance(), HEIGHT, 1e-3),
        arrow and arrow.distance(),
    )
    if arrow is not None:
        hs.drag_arrow(p.length_origin, p.length_direction, arrow.distance(), -40.0)


def t2_dragged_back():
    p = panel()
    length = p.length.value() if p else -1
    h.check("T2 dragged far back: the length stops above 0", 0 < length < 1, length)
    h.check("T2 no warning", "⚠" not in msg(), msg())
    if p:
        hs.click_checkbox(p.modeled)


def t2_values():
    p = panel()
    if p:
        ui.type_into(p.length.widget, "8")
        ui.type_into(p.offset.widget, "2")


def t2_modeled():
    v = h.solid_volume()
    expect = BOSS - removed(8)
    h.check("T2 modeled M10x1.5, 8 long", hs.close(v, expect, 1e-5), (v, expect))
    h.check("T2 valid", h.body().Shape.isValid())
    h.shot("t2-modeled")
    h.click_empty()
    h.press(QtCore.Qt.Key_Return)


def t2_done():
    h.check("T2 Enter over the view finishes the thread", not dialog_open())
    h.check("T2 one thread", len(hs.threads()) == 1, hs.threads())
    v = h.solid_volume()
    h.check("T2 kept", hs.close(v, BOSS - removed(8), 1e-5), v)
    part_ok("T2")
    s["v"] = v


# -- T3: edits from the timeline ----------------------------------------------------------------
def t3_edit():
    b.timeline_double_click("Thread 1", click_first=True)


def t3_open():
    p = panel()
    h.check("T3 editing Thread 1", p is not None and p.editing)
    if p is None:
        return
    h.check("T3 nothing left selected", not Gui.Selection.getSelectionEx())
    h.check("T3 Modeled shown", p.modeled.isChecked())
    h.check("T3 length 8 / offset 2 shown", near(p.length.value(), 8) and near(p.offset.value(), 2))
    hs.click_checkbox(p.modeled)


def t3_left():
    p = panel()
    if p:
        b.choose(p.direction, "Left hand")


def t3_ok():
    h.check("T3 cosmetic: the part is the plain boss", hs.close(h.solid_volume(), BOSS))
    h.task_button("OK")


def t3_cosmetic():
    h.check("T3 closed", not dialog_open())
    t = hs.threads()
    h.check("T3 left hand, cosmetic", t and t[0].LeftHanded and not t[0].Modeled)
    h.check("T3 a dashed helix is drawn", drawn() == 1, drawn())
    b.timeline_double_click("Thread 1", click_first=True)


def t3_second():
    p = panel()
    h.check("T3 second edit", p is not None and p.editing)
    if p:
        b.choose(p.designation, "M10x1.25")


def t3_cancel():
    h.task_button("Cancel")


def t3_cancelled():
    t = hs.threads()
    h.check("T3 Cancel kept M10x1.5", t and t[0].Designation == "M10x1.5", t and t[0].Designation)
    h.check("T3 still drawn", drawn() == 1, drawn())
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


t3_cancelled.wait_ms = 2500


def t3_undone():
    h.check("T3 Ctrl+Z: modeled again", hs.close(h.solid_volume(), s["v"], 1e-5), h.solid_volume())
    h.check("T3 nothing drawn for a modeled thread", drawn() == 0, drawn())
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def t3_redone():
    h.check("T3 Ctrl+Y: cosmetic again", hs.close(h.solid_volume(), BOSS), h.solid_volume())
    h.check("T3 drawn again", drawn() == 1, drawn())
    part_ok("T3")


# -- T4: an inside thread on a hole made with Hole ------------------------------------------------
HOLE = V(7, 7, 10)


def t4_h():
    h.press("h")


def t4_click():
    h.fit()
    h.click(HOLE)


def t4_hole():
    p = hs.hole_panel()
    h.check("T4 a hole", p is not None and p.target is not None, hs.message(p))
    if p:
        hs.type_into(p.pos_x.widget, "7")
        hs.type_into(p.pos_y.widget, "7")
        b.choose(p.extent, "All")
        b.choose(p.hole_type, "Simple")
        b.choose(p.tap_type, "Simple")
        hs.type_into(p.diameter.widget, "8.5")


def t4_hole_ok():
    h.task_button("OK")


def t4_wall():
    v = h.solid_volume()
    h.check("T4 d8.5 through hole", hs.close(v, BOSS - hs.cylinder(8.5, 10)), v)
    s["v"] = v
    h.fit()


def t4_click_wall():
    # The far wall of the hole (away from the iso camera) is in view through its opening.
    a = math.radians(135)
    h.click(V(7 + 4.25 * math.cos(a), 7 + 4.25 * math.sin(a), 8))


def t4_thread():
    sel = Gui.Selection.getSelectionEx()
    h.check(
        "T4 the hole's wall is selected",
        bool(sel),
        [(x.ObjectName, x.SubElementNames) for x in sel],
    )
    open_thread_keep()


def open_thread_keep():
    si.menu_item("CREATE", "Thread")


def t4_inside():
    p = panel()
    h.check("T4 the wall is taken at once", p is not None and p.target is not None, msg())
    if p is None:
        return
    h.check("T4 inside thread", "Inside" in p.info.text(), p.info.text())
    h.check("T4 M10x1.5 from the tap drill", p.designation.currentText() == "M10x1.5")
    h.check("T4 class 6H", p.thread_class.currentText() == "6H", p.thread_class.currentText())
    if not p.modeled.isChecked():
        hs.click_checkbox(p.modeled)


def t4_ok():
    h.task_button("OK")


def t4_done():
    from sciforge import thread_core

    v = h.solid_volume()
    expect = s["v"] - thread_core.removed_volume(5.0, 1.5, True, 4.25, 10.0)
    h.check("T4 modeled inside thread through the plate", hs.close(v, expect, 1e-5), (v, expect))
    part_ok("T4")
    s["v"] = v
    h.fit()


# -- T5: another command's key while the dialog is open -----------------------------------------
def t5_open():
    open_thread()


def t5_click():
    h.fit()
    h.click(SIDE)


def t5_h():
    p = panel()
    h.check("T5 a thread previewed", p is not None and p.target is not None, msg())
    s["threads"] = len(hs.threads())
    h.press("h")


def t5_hole_open():
    from sciforge import taskui

    current = taskui.current()
    h.check("T5 H opened Hole", current is not None and current.title == "Hole", current)
    h.check("T5 the thread was kept", len(hs.threads()) == s["threads"], hs.threads())
    h.press(QtCore.Qt.Key_Escape)


def t5_undo_kept():
    h.check("T5 Esc closed Hole", not dialog_open())
    # A second thread on the same boss was not meant: Ctrl+Z takes it away again.
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def t5_open2():
    h.check("T5 Ctrl+Z took the kept thread away", len(hs.threads()) == s["threads"] - 1)
    h.check("T5 the part is as before", hs.close(h.solid_volume(), s["v"], 1e-5))
    s["threads"] = len(hs.threads())
    open_thread()


def t5_click2():
    h.fit()
    h.click(SIDE)


def t5_bad():
    p = panel()
    h.check("T5 a second preview", p is not None and p.target is not None, msg())
    if p:
        if p.full_length.isChecked():
            hs.click_checkbox(p.full_length)
        ui.type_into(p.length.widget, "0")


def t5_e():
    h.check("T5 a 0 length is explained", "⚠" in msg(), msg())
    h.press("e")


def t5_extrude_open():
    from sciforge import taskui

    current = taskui.current()
    h.check("T5 E opened Extrude", current is not None and current.title == "Extrude", current)
    h.check("T5 the bad thread was dropped", len(hs.threads()) == s["threads"], hs.threads())
    h.check("T5 the part is as it was", hs.close(h.solid_volume(), s["v"], 1e-5))
    h.press(QtCore.Qt.Key_Escape)


def t5_done():
    h.check("T5 closed", not dialog_open())
    part_ok("T5")


# -- T6: a parameter in Thread Length --------------------------------------------------------------
def t6_edit():
    from sciforge import parameters

    parameters.add_user(doc(), "tlen", "mm", "6")  # Change Parameters made it
    doc().recompute()
    b.timeline_double_click("Thread 1", click_first=True)


def t6_type():
    p = panel()
    h.check("T6 editing Thread 1", p is not None and p.editing)
    if p:
        if not p.modeled.isChecked():
            hs.click_checkbox(p.modeled)


t6_type = slow(t6_type)


def t6_formula():
    p = panel()
    if p:
        ui.type_into(p.length.widget, "tlen")


t6_formula = slow(t6_formula)


def t6_typed():
    p = panel()
    h.check(
        "T6 'tlen' is 6 mm", p is not None and near(p.length.value(), 6), p and p.length.value()
    )
    h.check("T6 the formula is shown", p is not None and "tlen" in p.formulas.text())
    v = h.solid_volume()
    expect = s["v"] - removed(6)
    h.check("T6 the thread is 6 long", hs.close(v, expect, 1e-5), (v, expect))
    if p:
        ui.type_into(p.length.widget, "tlenn")


def t6_typo():
    h.check("T6 a typo is explained", "⚠" in msg(), msg())
    p = panel()
    if p:
        b.press_enter(p.length.widget)


def t6_enter():
    h.check("T6 Enter right after the typo keeps the dialog", dialog_open())
    p = panel()
    if p:
        ui.type_into(p.length.widget, "tlen")


t6_enter = slow(t6_enter)


def t6_ok():
    h.task_button("OK")


t6_ok = slow(t6_ok)


def t6_change():
    from sciforge import parameters

    h.check("T6 closed", not dialog_open())
    parameters.set_user(doc(), "tlen", "9")  # in Change Parameters
    doc().recompute()


t6_change = slow(t6_change)


def t6_followed():
    v = h.solid_volume()
    expect = s["v"] - removed(9)
    h.check("T6 the thread follows tlen = 9", hs.close(v, expect, 1e-5), (v, expect))
    part_ok("T6")
    s["v"] = v


# -- T7: Ctrl+S with the dialog open; reopen ------------------------------------------------------
def t7_save():
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-thread-qa-"), "thread_qa.FCStd")
    s["path"] = path
    doc().saveAs(path)
    b.timeline_double_click("Thread 1", click_first=True)


def t7_cosmetic():
    p = panel()
    h.check("T7 editing Thread 1", p is not None and p.editing, msg())
    if p and p.modeled.isChecked():
        hs.click_checkbox(p.modeled)
    s["threads"] = len(hs.threads())


t7_cosmetic = slow(t7_cosmetic)


def t7_press():
    h.check("T7 cosmetic preview: the boss is whole again", drawn() == 1, drawn())
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


def t7_describe():
    """Fusion's Save asks for a version description on a saved design; Enter skips it."""
    h.check("T7 the Save dialog asks for a version description", vi.version_dialog() is not None)
    vi.accept_save()


def t7_saved():
    h.check("T7 Ctrl+S finished the dialog first", not dialog_open())
    h.check("T7 the edit was kept", hs.threads() and not hs.threads()[0].Modeled)
    h.check("T7 no thread added or lost", len(hs.threads()) == s["threads"], hs.threads())
    h.check("T7 the design is saved", not doc().isTouched() and not b.modified())
    s["v"] = h.solid_volume()
    s["drawn"] = drawn()
    App.closeDocument(doc().Name)


def t7_open():
    App.openDocument(s["path"])
    h.fit()


t7_open = slow(t7_open, 4000)


def t7_reopened():
    h.check("T7 same part", hs.close(h.solid_volume(), s["v"], 1e-5), h.solid_volume())
    h.check("T7 the threads are in the file", len(hs.threads()) == s["threads"], hs.threads())
    h.check("T7 cosmetic threads drawn again", drawn() == s["drawn"], (drawn(), s["drawn"]))
    part_ok("T7")
    b.timeline_double_click("Thread 1", click_first=True)


def t7_edit():
    p = panel()
    h.check("T7 editing after reopening", p is not None and p.editing)
    h.check("T7 the formula is back", p is not None and "tlen" in p.formulas.text())
    h.task_button("OK")


t7_edit = slow(t7_edit)


def t7_done():
    h.check("T7 closed", not dialog_open())
    h.check("T7 unchanged", hs.close(h.solid_volume(), s["v"], 1e-5), h.solid_volume())
    h.check("T7 no kernel errors in the Report view", not b.report_has_kernel_errors())
    hs.no_popups("threads")
    h.shot("t7-end")


h.run(
    "hole_qa_thread",
    ti.watched(
        b.box_steps("ThreadQA")
        + hs.make_boss("boss", radius=R, height=HEIGHT, at=(20.0, 15.0))
        + [
            t1_open,
            t1_ok,
            t1_refused,
            t1_flat,
            t1_enter,
            t1_esc,
            t2_open,
            t2_values_first,
            t2_click,
            t2_picked,
            t2_drag_far,
            t2_drag_far2,
            t2_dragged_far,
            t2_dragged_back,
            slow(t2_values),
            slow(t2_modeled),
            t2_done,
            t3_edit,
            slow(t3_open),
            t3_left,
            t3_ok,
            t3_cosmetic,
            t3_second,
            t3_cancel,
            t3_cancelled,
            slow(t3_undone),
            t3_redone,
            t4_h,
            t4_click,
            t4_hole,
            t4_hole_ok,
            t4_wall,
            t4_click_wall,
            t4_thread,
            slow(t4_inside),
            slow(t4_ok),
            t4_done,
            t5_open,
            slow(t5_click),
            t5_h,
            t5_hole_open,
            t5_undo_kept,
            t5_open2,
            slow(t5_click2),
            slow(t5_bad),
            t5_e,
            t5_extrude_open,
            t5_done,
            t6_edit,
            t6_type,
            t6_formula,
            t6_typed,
            t6_typo,
            t6_enter,
            t6_ok,
            t6_change,
            t6_followed,
            t7_save,
            t7_cosmetic,
            t7_press,
            t7_describe,
            t7_saved,
            t7_open,
            t7_reopened,
            t7_edit,
            t7_done,
        ]
    ),
)
