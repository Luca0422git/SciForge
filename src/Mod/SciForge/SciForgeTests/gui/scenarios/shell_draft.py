# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shell the way a Fusion user does it, only real input: the ribbon's Shell with nothing
selected (the dialog waits, no error), click the top face (again to drop it), type a
thickness, take away a second face and drop it again, drag the blue arrow, Direction
Both / Outside, Shell Type Rounded, a wall too thick (explained in the dialog, OK waits,
nothing in the Report view), OK, Ctrl+Z / Ctrl+Y, edit by double-clicking the timeline,
Cancel and Esc leave the part as it was. Volumes are worked out by hand
(shell_draft_steps)."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import shell_draft_steps as sd

V = App.Vector
s = {}
TOP = V(20, 15, 10)
FRONT = V(20, 0, 5)
RIGHT = V(40, 15, 5)


def ribbon_shell():
    Gui.Selection.clearSelection()
    h.ribbon("Shell")


def waiting():
    p = sd.shell_panel()
    h.check("Shell dialog open", p is not None and Gui.Control.activeDialog())
    if p is None:
        return
    h.check("nothing picked yet", p.picked == [] and not p.whole and p.target is None)
    h.check("selection box says Select", p.selection.button.text() == "Select")
    h.check("no error shown while waiting", p.message.text() == "", p.message.text())
    h.check("model unchanged while waiting", sd.close(h.solid_volume(), sd.BOX))
    h.check("Inside Thickness shown, 1 mm", p.inside.widget.isVisible() and p.inside.value() == 1)
    h.check("Outside Thickness hidden (Direction Inside)", not p.outside.widget.isVisible())
    h.check("Tangent Chain on", p.tangent.isChecked())
    sd.no_popups("Shell with nothing selected")
    h.shot("1-waiting")


def click_top():
    h.fit()
    h.click(TOP)


def top_picked():
    p = sd.shell_panel()
    h.check("top face picked", p is not None and len(p.names()) == 1, p and p.names())
    h.check("selection box says 1 face", p and p.selection.button.text() == "1 face")
    v = h.solid_volume()
    h.check("preview: open box, 1 mm wall (12000 - 38*28*9)", sd.close(v, sd.open_top(1)), v)
    h.check("the picked face is highlighted", len(sd.selected()) == 1, sd.selected())
    h.check("a blue arrow on the rim", p is not None and len(p.arrows) == 1)
    h.check(
        "FreeCAD's own shell feature", [o.TypeId for o in sd.shells()] == ["PartDesign::Thickness"]
    )
    h.shot("2-top")


def type_2():
    p = sd.shell_panel()
    if p:
        sd.type_into(p.inside.widget, "2")


def two_mm():
    p = sd.shell_panel()
    v = h.solid_volume()
    h.check("typed 2 mm previews (12000 - 36*26*8)", sd.close(v, sd.open_top(2)), v)
    h.check(
        "arrow follows the typed value",
        p and abs(p.arrows[0][0].distance() - 2.0) < 1e-6,
        p and p.arrows[0][0].distance(),
    )


def click_top_again():
    h.click(TOP)


def top_dropped():
    p = sd.shell_panel()
    h.check("clicking the picked face drops it", p is not None and p.picked == [], p and p.picked)
    h.check("preview gone: the part is whole again", sd.close(h.solid_volume(), sd.BOX))
    h.check("no shell step left behind", sd.shells() == [], sd.shells())
    h.check("no arrow without a pick", p is not None and not p.arrows)
    h.check("no message", p is not None and p.message.text() == "", p and p.message.text())


def click_top_third():
    h.click(TOP)


def click_front():
    p = sd.shell_panel()
    h.check("top picked again", p is not None and len(p.picked) == 1)
    h.click(FRONT)


def two_faces():
    p = sd.shell_panel()
    h.check("two faces picked", p is not None and len(p.names()) == 2, p and p.names())
    v = h.solid_volume()
    h.check("top and front open (12000 - 36*28*8)", sd.close(v, sd.BOX - 36 * 28 * 8), v)
    h.check("selection box says 2 faces", p and p.selection.button.text() == "2 faces")
    h.shot("3-two-faces")


def click_front_again():
    h.click(FRONT)


def front_dropped():
    p = sd.shell_panel()
    h.check("front face dropped again", p is not None and len(p.names()) == 1, p and p.names())
    h.check("back to the open box", sd.close(h.solid_volume(), sd.open_top(2)), h.solid_volume())


def drag_arrow():
    p = sd.shell_panel()
    if p is None or not p.arrows:
        h.check("arrow to drag", False)
        return
    h.fit()
    start, end = sd.arrow_screen(p, along=1.5)
    s["before"] = p.inside.value()
    h.drag(start, end)


def dragged():
    p = sd.shell_panel()
    t = p.inside.value() if p else 0
    h.check("dragging the arrow into the wall thickens it", t > s["before"] + 0.4, (s["before"], t))
    v = h.solid_volume()
    h.check("preview matches the dragged thickness", sd.close(v, sd.open_top(t)), (v, t))
    h.shot("4-dragged")
    if p:
        sd.type_into(p.inside.widget, "2")


def choose_both():
    p = sd.shell_panel()
    if p:
        sd.choose(p.direction, "Both")


def both_shown():
    p = sd.shell_panel()
    h.check(
        "Both shows the two thickness fields",
        p and p.inside.widget.isVisible() and p.outside.widget.isVisible(),
    )
    h.check("two arrows (inside and outside)", p is not None and len(p.arrows) == 2)
    if p:
        sd.type_into(p.outside.widget, "1")


def both_preview():
    v = h.solid_volume()
    expect = 42 * 32 * 11 - 36 * 26 * 8
    h.check("Both: 2 mm in, 1 mm out (42*32*11 - 36*26*8)", sd.close(v, expect), (v, expect))
    h.check(
        "SciForge's shell feature does Both",
        [getattr(o, "SciForgeType", "") for o in sd.shells()] == ["Shell"],
        [o.TypeId for o in sd.shells()],
    )
    h.shot("5-both")


def choose_outside():
    p = sd.shell_panel()
    if p:
        sd.choose(p.direction, "Outside")


def outside_preview():
    p = sd.shell_panel()
    v = h.solid_volume()
    h.check("Outside 1 mm, sharp ((42*32*11) - 12000)", sd.close(v, sd.outside_sharp(1)), v)
    h.check(
        "only Outside Thickness shown",
        p and not p.inside.widget.isVisible() and p.outside.widget.isVisible(),
    )
    h.check("back on FreeCAD's shell", [o.TypeId for o in sd.shells()] == ["PartDesign::Thickness"])
    h.check("still one step", len(sd.shells()) == 1, sd.shells())
    if p:
        sd.choose(p.shell_type, "Rounded")


def rounded_preview():
    v = h.solid_volume()
    h.check(
        "Rounded: the outside corners are rounds (slabs + quarter rounds + ball corners)",
        sd.close(v, sd.outside_rounded(1)),
        (v, sd.outside_rounded(1)),
    )
    h.shot("6-rounded")


def back_to_inside():
    p = sd.shell_panel()
    if p:
        sd.choose(p.shell_type, "Sharp")
        sd.choose(p.direction, "Inside")


def type_too_thick():
    p = sd.shell_panel()
    s["good"] = h.solid_volume()
    h.check("inside 2 again", sd.close(s["good"], sd.open_top(2)), s["good"])
    if p:
        sd.type_into(p.inside.widget, "20")


def too_thick_reported():
    p = sd.shell_panel()
    text = p.message.text() if p else ""
    h.check("too-thick wall explained in the dialog", "too thick" in text, text)
    h.check("preview keeps the last good result", sd.close(h.solid_volume(), s["good"]))
    h.check("nothing about it in the Report view", not sd.report_errors(), sd.report_errors())
    sd.no_popups("a wall too thick")
    h.shot("7-too-thick")


too_thick_reported.wait_ms = 1500  # the thickest wall that fits is worked out


def hint_shown():
    p = sd.shell_panel()
    text = p.message.text() if p else ""
    h.check("dialog says the thickest wall that fits", "thickest inside wall" in text, text)
    h.task_button("OK")


def ok_refused():
    h.check(
        "OK waits while the wall does not fit",
        sd.shell_panel() is not None and Gui.Control.activeDialog(),
    )
    p = sd.shell_panel()
    if p:
        sd.type_into(p.inside.widget, "2")


def ok():
    p = sd.shell_panel()
    h.check(
        "message gone after a good value",
        p is not None and p.message.text() == "",
        p and p.message.text(),
    )
    h.task_button("OK")


def after_ok():
    h.check("dialog closed", sd.shell_panel() is None and not Gui.Control.activeDialog())
    shape = h.body().Shape
    h.check("shell: 12000 - 36*26*8", sd.close(shape.Volume, sd.open_top(2)), shape.Volume)
    h.check("11 faces (5 outside, 5 inside, the rim)", len(shape.Faces) == 11, len(shape.Faces))
    h.check("valid solid", shape.isValid())
    bb = shape.BoundBox
    h.check("bounding box unchanged", sd.close(bb.XLength, 40) and sd.close(bb.ZLength, 10), bb)
    sh = sd.shells()
    h.check("one shell, the end of the timeline", len(sh) == 1 and h.body().Tip is sh[0], sh)
    h.check("timeline shows Shell 1", "Shell 1" in sd.timeline_titles(), sd.timeline_titles())
    h.check("no leftover selection", not Gui.Selection.getSelectionEx())
    h.check("only the shell is shown", sd.shown_features() == [sh[0].Name], sd.shown_features())
    h.shot("8-shell")


def undo():
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def after_undo():
    h.check(
        "Ctrl+Z takes the whole shell away in one step",
        sd.close(h.solid_volume(), sd.BOX) and not sd.shells(),
        h.solid_volume(),
    )


def redo():
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def after_redo():
    h.check(
        "Ctrl+Y brings it back",
        sd.close(h.solid_volume(), sd.open_top(2)) and len(sd.shells()) == 1,
        h.solid_volume(),
    )
    h.fit()


def edit_from_timeline():
    sd.timeline_double_click("Shell 1")


def edit_open():
    p = sd.shell_panel()
    h.check("double-click opens the Shell dialog on the step", p is not None and p.editing)
    h.check("its face is shown picked", p is not None and p.names() and len(p.names()) == 1)
    h.check("and highlighted", len(sd.selected()) == 1, sd.selected())
    h.check("thickness shown", p is not None and abs(p.inside.value() - 2.0) < 1e-9)
    h.shot("9-edit")
    if p:
        sd.choose(p.direction, "Both")


def edit_both():
    p = sd.shell_panel()
    if p:
        sd.type_into(p.outside.widget, "1")


def edit_ok():
    h.task_button("OK")


def after_edit():
    v = h.solid_volume()
    h.check("edited to Both 2/1", sd.close(v, 42 * 32 * 11 - 36 * 26 * 8), v)
    sh = sd.shells()
    h.check(
        "still one shell step (now SciForge's)",
        len(sh) == 1 and getattr(sh[0], "SciForgeType", "") == "Shell",
        sh,
    )
    h.check(
        "still called Shell 1 in the timeline",
        "Shell 1" in sd.timeline_titles(),
        sd.timeline_titles(),
    )
    h.check("it is the end of the timeline", h.body().Tip is (sh[0] if sh else None))
    s["v"] = v


def edit_again():
    sd.timeline_double_click("Shell 1")


def edit_again_open():
    p = sd.shell_panel()
    h.check("the edited step opens again", p is not None and p.editing)
    h.check("Direction Both shown", p is not None and p.direction.currentText() == "Both")
    h.check(
        "both values shown",
        p is not None and abs(p.inside.value() - 2) < 1e-9 and abs(p.outside.value() - 1) < 1e-9,
    )
    if p:
        sd.choose(p.direction, "Inside")


def edit_cancel():
    v = h.solid_volume()
    h.check("preview of Inside while editing", sd.close(v, sd.open_top(2)), v)
    h.task_button("Cancel")


def after_edit_cancel():
    h.check("Cancel keeps the step as it was", sd.close(h.solid_volume(), s["v"]), h.solid_volume())
    sh = sd.shells()
    h.check(
        "one shell, unchanged kind",
        len(sh) == 1 and getattr(sh[0], "SciForgeType", "") == "Shell",
        sh,
    )
    h.check("shown again", sd.shown_features() == [h.body().Tip.Name], sd.shown_features())


def cancel_start():
    h.ribbon("Shell")


def cancel_pick():
    h.fit()
    h.click(RIGHT)


def cancel_preview():
    p = sd.shell_panel()
    h.check(
        "a second shell previewed", p is not None and p.target is not None, p and p.message.text()
    )
    h.check("preview changes the part", not sd.close(h.solid_volume(), s["v"]), h.solid_volume())
    h.task_button("Cancel")


def after_cancel():
    h.check(
        "Cancel leaves the model as it was", sd.close(h.solid_volume(), s["v"]), h.solid_volume()
    )
    h.check("no new step", len(sd.shells()) == 1, sd.shells())
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("the part is shown", sd.shown_features() == [h.body().Tip.Name], sd.shown_features())


def esc_start():
    h.ribbon("Shell")


def esc_pick():
    h.fit()
    h.click(RIGHT)


def esc_press():
    p = sd.shell_panel()
    h.check("previewed before Esc", p is not None and p.target is not None)
    h.press(QtCore.Qt.Key_Escape)


def after_esc():
    h.check("Esc closes the dialog", not Gui.Control.activeDialog() and sd.shell_panel() is None)
    h.check("Esc leaves the model as it was", sd.close(h.solid_volume(), s["v"]), h.solid_volume())
    h.check("no new step", len(sd.shells()) == 1, sd.shells())
    h.check("no errors in the Report view", not sd.report_errors(), sd.report_errors())
    h.shot("10-end")


h.run(
    "shell_draft",
    sd.box_steps("Shell")
    + [
        ribbon_shell,
        waiting,
        click_top,
        top_picked,
        type_2,
        two_mm,
        click_top_again,
        top_dropped,
        click_top_third,
        click_front,
        two_faces,
        click_front_again,
        front_dropped,
        drag_arrow,
        dragged,
        choose_both,
        both_shown,
        both_preview,
        choose_outside,
        outside_preview,
        rounded_preview,
        back_to_inside,
        type_too_thick,
        too_thick_reported,
        hint_shown,
        ok_refused,
        ok,
        after_ok,
        undo,
        after_undo,
        redo,
        after_redo,
        edit_from_timeline,
        edit_open,
        edit_both,
        edit_ok,
        after_edit,
        edit_again,
        edit_again_open,
        edit_cancel,
        after_edit_cancel,
        cancel_start,
        cancel_pick,
        cancel_preview,
        after_cancel,
        esc_start,
        esc_pick,
        esc_press,
        after_esc,
    ],
)
