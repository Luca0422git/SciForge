# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shell, second scenario, only real input: the body picked in the browser before
pressing Shell makes it hollow (Fusion allows picking the body), Cancel; the top face
clicked before pressing Shell starts with it and Enter finishes; a second Shell on the
result with nothing selected waits, then the body clicked in the browser hollows the
open box (a wall too thick for its 2 mm walls is explained first); Ctrl+Z inside the
dialog; the first shell edited to Both while the second one depends on it (the second
follows); undo/redo of that edit. Volumes worked out by hand:
  hollow box, inside t:          12000 - (40-2t)(30-2t)(10-2t)
  open box (2 mm walls) hollowed with 0.5 mm:  4512 - (39*29*9 - 37*27*8) = 2325
  after the first shell is Both 2 in / 1 out:  7296 - (41*31*10 - 37*27*8) = 2578
"""
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import shell_draft_steps as sd

V = App.Vector
s = {}
TOP = V(20, 15, 10)
RIGHT = V(40, 15, 5)


def pick_body_in_browser():
    Gui.Selection.clearSelection()
    sd.click_browser_row("Body")


def body_selected_then_shell():
    sel = [x.ObjectName for x in Gui.Selection.getSelectionEx()]
    h.check("the body is selected", sel == ["Body"], sel)
    h.ribbon("Shell")


def hollow_preview():
    p = sd.shell_panel()
    h.check("Shell started with the body", p is not None and p.whole, p and p.picked)
    h.check("selection box says Body", p and p.selection.button.text() == "Body")
    v = h.solid_volume()
    h.check("hollow, 1 mm wall (12000 - 38*28*8)", sd.close(v, sd.hollow(1)), v)
    h.check(
        "SciForge's shell feature makes it hollow",
        [getattr(o, "SciForgeType", "") for o in sd.shells()] == ["Shell"],
        sd.shells(),
    )
    h.check("an arrow to drag", p is not None and len(p.arrows) == 1)
    h.shot("1-hollow")
    if p:
        sd.type_into(p.inside.widget, "2")


def hollow_2():
    v = h.solid_volume()
    h.check("hollow, 2 mm (12000 - 36*26*6)", sd.close(v, sd.hollow(2)), v)
    shape = h.body().Shape
    h.check(
        "a closed wall: two shells (outside and inside)", len(shape.Shells) == 2, len(shape.Shells)
    )
    p = sd.shell_panel()
    if p:
        sd.choose(p.direction, "Outside")


def hollow_outside():
    v = h.solid_volume()
    h.check("hollow, 1 mm outside (42*32*12 - 12000)", sd.close(v, 42 * 32 * 12 - sd.BOX), v)
    h.task_button("Cancel")


def after_cancel():
    h.check("Cancel: the box is whole again", sd.close(h.solid_volume(), sd.BOX), h.solid_volume())
    h.check("no shell step", sd.shells() == [], sd.shells())
    h.check("dialog closed", not Gui.Control.activeDialog())


def preselect_top():
    h.fit()
    h.click(TOP)


def shell_with_top():
    h.check("top face selected", len(sd.selected()) == 1, sd.selected())
    h.ribbon("Shell")


def started_with_top():
    p = sd.shell_panel()
    h.check(
        "Shell started with the top face", p is not None and len(p.names()) == 1, p and p.names()
    )
    v = h.solid_volume()
    h.check("open box preview at once", sd.close(v, sd.open_top(1)), v)
    if p:
        sd.type_into(p.inside.widget, "2")


def enter_finishes():
    p = sd.shell_panel()
    if p:
        sd.press_enter(p.inside.widget)


def first_shell():
    h.check("Enter finished the dialog", not Gui.Control.activeDialog())
    v = h.solid_volume()
    h.check("first shell: open box, 2 mm", sd.close(v, sd.open_top(2)), v)
    h.check("FreeCAD's own shell", [o.TypeId for o in sd.shells()] == ["PartDesign::Thickness"])
    s["v1"] = v


def second_shell():
    Gui.Selection.clearSelection()
    h.ribbon("Shell")


def second_waits():
    p = sd.shell_panel()
    h.check(
        "second Shell waits for a pick", p is not None and not p.has_picks() and p.target is None
    )
    h.check(
        "no error while waiting", p is not None and p.message.text() == "", p and p.message.text()
    )
    sd.no_popups("a second Shell")
    sd.click_browser_row("Body")


def second_too_thick():
    p = sd.shell_panel()
    h.check("the body (open box) picked: hollow", p is not None and p.whole)
    text = p.message.text() if p else ""
    h.check("1 mm is too thick for the 2 mm walls: said in the dialog", "too thick" in text, text)
    h.check("the part is unchanged meanwhile", sd.close(h.solid_volume(), sd.open_top(2)))
    h.check("nothing in the Report view", not sd.report_errors(), sd.report_errors())
    h.shot("2-too-thick")
    if p:
        sd.type_into(p.inside.widget, "0.5")


def second_preview():
    p = sd.shell_panel()
    v = h.solid_volume()
    h.check(
        "open box hollowed with 0.5 mm (2325)", sd.close(v, 2325.0), (v, p and p.message.text())
    )
    h.check("message gone", p is not None and p.message.text() == "", p and p.message.text())
    h.shot("3-second")
    h.task_button("OK")


def after_second():
    sh = sd.shells()
    h.check("two shells in the timeline", len(sh) == 2, sh)
    h.check("Shell 2 in the timeline", "Shell 2" in sd.timeline_titles(), sd.timeline_titles())
    h.check("valid solid", h.body().Shape.isValid())
    s["v2"] = h.solid_volume()


def undo_inside_start():
    h.ribbon("Shell")


def undo_inside_pick():
    h.fit()
    h.click(RIGHT)


def undo_inside_type():
    p = sd.shell_panel()
    text = p.message.text() if p else ""
    h.check("1 mm is too much for a 2 mm wall taken from both sides: said", "1 mm" in text, text)
    if p:
        sd.type_into(p.inside.widget, "0.5")


def undo_inside_press():
    p = sd.shell_panel()
    h.check("third shell previewed", p is not None and p.target is not None, p and p.message.text())
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def undo_inside_after():
    h.check("Ctrl+Z inside the dialog ends it", not Gui.Control.activeDialog())
    h.check(
        "and takes the unfinished shell away",
        sd.close(h.solid_volume(), s["v1"]) and len(sd.shells()) == 1,
        (h.solid_volume(), sd.shells()),
    )
    h.fit()


def edit_first():
    sd.timeline_double_click("Shell 1")


def edit_first_open():
    p = sd.shell_panel()
    h.check("Shell 1 opens for editing", p is not None and p.editing and len(p.names()) == 1)
    shown = sd.shown_features()
    h.check(
        "while editing, the timeline is rolled back to Shell 1 (Shell 2 not shown)",
        p is not None and p.target.Name in shown and sd.shells()[1].Name not in shown,
        shown,
    )
    if p:
        sd.choose(p.direction, "Both")


def edit_first_outside():
    p = sd.shell_panel()
    if p:
        sd.type_into(p.outside.widget, "1")


def edit_first_ok():
    h.task_button("OK")


def after_edit_first():
    v = h.solid_volume()
    h.check("Shell 2 follows the edited Shell 1 (2578)", sd.close(v, 2578.0), v)
    sh = sd.shells()
    h.check("still two shells", len(sh) == 2, sh)
    h.check("Shell 2 is the end of the timeline", h.body().Tip is (sh[1] if len(sh) == 2 else None))
    h.check("both steps compute", all("Invalid" not in o.State for o in sh), [o.State for o in sh])
    h.check(
        "timeline still Shell 1, Shell 2",
        "Shell 1" in sd.timeline_titles() and "Shell 2" in sd.timeline_titles(),
        sd.timeline_titles(),
    )
    h.shot("4-edited")


def undo_edit():
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def after_undo_edit():
    v = h.solid_volume()
    h.check("Ctrl+Z undoes the whole edit", sd.close(v, s["v2"]), v)
    sh = sd.shells()
    h.check("two shells again", len(sh) == 2, sh)
    h.check("Shell 1 is FreeCAD's shell again", sh and sh[0].TypeId == "PartDesign::Thickness", sh)


def redo_edit():
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def after_redo_edit():
    v = h.solid_volume()
    h.check("Ctrl+Y redoes it", sd.close(v, 2578.0), v)
    h.check("valid at the end", h.body().Shape.isValid())
    from sciforge import parameters

    parameters.add_user(App.ActiveDocument, "wall", "mm", "1.5")  # as in Change Parameters


def formula_edit():
    sd.timeline_double_click("Shell 1")


def type_formula():
    p = sd.shell_panel()
    h.check("Shell 1 opens again", p is not None and p.editing)
    if p:
        ui.type_into(p.inside.widget, "wall")


def formula_preview():
    p = sd.shell_panel()
    h.check("the parameter's value is used", p is not None and abs(p.inside.value() - 1.5) < 1e-9)
    h.check(
        "the formula is shown",
        p is not None and "Inside Thickness = wall" in p.formula_label.text(),
        p and p.formula_label.text(),
    )
    h.task_button("OK")


def formula_kept():
    v = h.solid_volume()
    # Shell 1: Both 1.5 in / 1 out = 42*32*11 - 37*27*8.5; Shell 2 hollows it with 0.5 mm:
    # minus (41*31*10 - 38*28*8.5)
    expect = (42 * 32 * 11 - 37 * 27 * 8.5) - (41 * 31 * 10 - 38 * 28 * 8.5)
    h.check("inside wall = wall (1.5 mm)", sd.close(v, expect), (v, expect))
    sh = sd.shells()[0]
    h.check(
        "the step keeps the formula",
        "Parameters.wall" in dict(sh.ExpressionEngine).get("InsideThickness", ""),
        sh.ExpressionEngine,
    )
    from sciforge import parameters

    parameters.set_user(App.ActiveDocument, "wall", "2")  # as in Change Parameters
    App.ActiveDocument.recompute()


def follows_parameter():
    v = h.solid_volume()
    h.check("changing the parameter to 2 changes the shell (2578)", sd.close(v, 2578.0), v)


def save():
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-shell-"), "hollow.FCStd")
    s["path"] = path
    App.ActiveDocument.saveAs(path)
    h.check("saved", os.path.isfile(path), path)


def close():
    App.closeDocument(App.ActiveDocument.Name)


def reopen():
    App.openDocument(s["path"])
    h.fit()


def reopened():
    h.check("reopened: same part", sd.close(h.solid_volume(), 2578.0), h.solid_volume())
    h.check(
        "both shells in the timeline",
        "Shell 1" in sd.timeline_titles() and "Shell 2" in sd.timeline_titles(),
        sd.timeline_titles(),
    )
    sd.timeline_double_click("Shell 2")


def reopened_edit():
    p = sd.shell_panel()
    h.check("SciForge's shell opens for editing after reopening", p is not None and p.editing)
    h.check("the hollow body is shown", p is not None and p.whole)
    h.check("0.5 mm remembered", p is not None and abs(p.inside.value() - 0.5) < 1e-9)
    h.task_button("Cancel")


def reopened_cancel():
    h.check("Cancel changes nothing", sd.close(h.solid_volume(), 2578.0), h.solid_volume())
    h.check("no errors in the Report view", not sd.report_errors(), sd.report_errors())


h.run(
    "shell_draft_hollow",
    sd.box_steps("Hollow")
    + [
        pick_body_in_browser,
        body_selected_then_shell,
        hollow_preview,
        hollow_2,
        hollow_outside,
        after_cancel,
        preselect_top,
        shell_with_top,
        started_with_top,
        enter_finishes,
        first_shell,
        undo_inside_start,
        undo_inside_pick,
        undo_inside_type,
        undo_inside_press,
        undo_inside_after,
        second_shell,
        second_waits,
        second_too_thick,
        second_preview,
        after_second,
        edit_first,
        edit_first_open,
        edit_first_outside,
        edit_first_ok,
        after_edit_first,
        undo_edit,
        after_undo_edit,
        redo_edit,
        after_redo_edit,
        formula_edit,
        type_formula,
        formula_preview,
        formula_kept,
        follows_parameter,
        save,
        close,
        reopen,
        reopened,
        reopened_edit,
        reopened_cancel,
    ],
)
