# SPDX-License-Identifier: LGPL-2.1-or-later
"""A plain fillet with a chamfer after it is edited from the timeline to hold a second radius
set: the fillet step becomes SciForge's own in the same place of the timeline, and the
chamfer after it keeps its edge. Ctrl+Z gives the plain fillet back (one undo step), Ctrl+Y
the two sets again. Then Press Pull (Q) on set 2's round edits set 2's radius, as Press
Pull edits a fillet in Fusion. Only real input.

Volumes: a round of radius r on a 40 mm box edge removes 40 r^2 (1 - pi/4); a 1 mm chamfer
on a 30 mm edge removes 30 / 2."""

import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import fillet2_steps as f2
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}
FRONT_TOP = V(20, 0, 10)
BACK_TOP = V(20, 30, 10)
RIGHT_BOTTOM = V(40, 15, 0)
CHAMFER = 30 * 1 * 1 / 2.0


def fillet():
    Gui.Selection.clearSelection()
    h.fit()
    h.press("f")


def pick():
    h.click_edge(FRONT_TOP)


def fillet_ok():
    p = b.blend_panel()
    h.check("one edge", p is not None and len(p.refs) == 1)
    h.task_button("OK")


def chamfer():
    h.check(
        "FreeCAD's fillet for one set", f2.steps() and f2.steps()[0].TypeId == "PartDesign::Fillet"
    )
    Gui.Selection.clearSelection()
    h.ribbon("Chamfer")


def chamfer_pick():
    h.click_edge(RIGHT_BOTTOM)


def chamfer_ok():
    h.task_button("OK")


def made():
    v = h.solid_volume()
    expect = b.BOX - 40 * b.spandrel(1) - CHAMFER
    h.check("fillet then chamfer", b.close(v, expect), (v, expect))
    s["chamfer"] = f2.steps()[1].Name if len(f2.steps()) == 2 else None
    h.fit()
    b.timeline_double_click("Fillet 1", click_first=True)


def edit_plus():
    p = b.blend_panel()
    h.check("editing Fillet 1", p is not None and not p.created)
    if p:
        f2.press_plus(p)


def edit_pick():
    h.click_edge(BACK_TOP)


def edit_radius():
    p = b.blend_panel()
    h.check("set 2 has the back edge", p is not None and len(p.refs) == 1, p and p.refs)
    if p:
        b.type_into(p.radius.widget, "2")


def edit_preview():
    p = b.blend_panel()
    h.check("the edited step is SciForge's now", p is not None and f2.is_sets(p.target))
    h.check(
        "no later step is broken",
        p is not None and "no longer work" not in p.message.text(),
        p and p.message.text(),
    )
    h.task_button("OK")


def after_ok():
    steps = f2.steps()
    h.check(
        "the timeline order is kept: the fillet, then the chamfer",
        len(steps) == 2 and f2.is_sets(steps[0]) and steps[1].Name == s["chamfer"],
        [(o.Name, o.TypeId) for o in steps],
    )
    h.check("the chamfer still computes", len(steps) == 2 and "Invalid" not in steps[1].State)
    v = h.solid_volume()
    expect = b.BOX - 40 * b.spandrel(1) - 40 * b.spandrel(2) - CHAMFER
    h.check("two sets and the chamfer", b.close(v, expect), (v, expect))
    h.check("the chamfer is the last step shown", h.body().Tip.Name == s["chamfer"])
    h.check("titles", b.timeline_titles()[-2:] == ["Fillet 1", "Chamfer 1"], b.timeline_titles())
    s["v"] = v
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def undone():
    steps = f2.steps()
    h.check(
        "Ctrl+Z gives the plain fillet back",
        len(steps) == 2 and steps[0].TypeId == "PartDesign::Fillet",
        [(o.Name, o.TypeId) for o in steps],
    )
    v = h.solid_volume()
    h.check("and the chamfer", b.close(v, b.BOX - 40 * b.spandrel(1) - CHAMFER), v)
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def redone():
    h.check("Ctrl+Y: the two sets again", b.close(h.solid_volume(), s["v"]), h.solid_volume())
    h.click_empty()
    h.press("q")


def round_face():
    h.fit()
    r = 2.0  # set 2's round on the back top edge, half way round
    c = math.cos(math.radians(45))
    h.click(V(20, 30 - r + r * c, 10 - r + r * c))


def press_pull_edit():
    from sciforge import presspull_ui

    p = presspull_ui.PressPullPanel.last
    ok = p is not None and not p._closed and p.mode == "edit_blend"
    h.check("Press Pull on set 2's round edits it", ok, p and (p.mode, p.message.text()))
    if ok:
        h.check("the box says which size", "set 2" in p.field_label.text(), p.field_label.text())
        b.type_into(p.field.widget, "3")


def press_pull_ok():
    v = h.solid_volume()
    expect = b.BOX - 40 * b.spandrel(1) - 40 * b.spandrel(3) - CHAMFER
    h.check("set 2 is now r 3 (preview)", b.close(v, expect), (v, expect))
    h.task_button("OK")


def end():
    v = h.solid_volume()
    expect = b.BOX - 40 * b.spandrel(1) - 40 * b.spandrel(3) - CHAMFER
    h.check("kept", b.close(v, expect), (v, expect))
    steps = f2.steps()
    h.check(
        "still one fillet step and the chamfer, nothing added",
        len(steps) == 2 and abs(f2.spec_of(steps[0])["sets"][1]["radius"] - 3) < 1e-9,
        steps and f2.spec_of(steps[0])["sets"],
    )
    h.check("no kernel errors", not f2.report_errors(), f2.report_errors())
    h.check("dialog closed", not Gui.Control.activeDialog())


h.run(
    "fillet2_edit_later",
    b.box_steps("EditLater")
    + [
        fillet,
        pick,
        fillet_ok,
        chamfer,
        chamfer_pick,
        chamfer_ok,
        made,
        edit_plus,
        edit_pick,
        edit_radius,
        edit_preview,
        after_ok,
        undone,
        redone,
        round_face,
        press_pull_edit,
        press_pull_ok,
        end,
    ],
)
