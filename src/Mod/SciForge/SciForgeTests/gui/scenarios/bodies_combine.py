# SPDX-License-Identifier: LGPL-2.1-or-later
"""Combine (Modify > Combine), only real input.

Two bodies made like Luca makes them: Body1 = rectangle 0..40 x 0..30, extruded 10 (12000);
Body2 = rectangle 30..70 x 0..30, extruded 10 as a New Body (12000). They overlap in
30..40 x 0..30 x 0..10 = 3000.

  A  nothing selected: the Combine button opens the dialog waiting for the target body;
     click Body1 (target), click Body2 (tool): the preview joins them (21000, a single
     70 x 30 x 10 block, 6 faces); OK. Body2 is used up (hidden). Ctrl+Z / Ctrl+Y.
  B  double-click the Combine in the timeline: Cut: 12000 - 3000 = 9000. OK.
  C  edit again: Keep Tools on: Body2 comes back. Cancel path: Intersect previews 3000,
     Cancel leaves 9000.
  D  Body2 selected first, then Combine: it is the target; click Body1 as the tool, Join:
     Body2 = 70 x 30 x 10 = 21000; Body1 used up.
  E  New Body: undo D, Combine with New Body: Body3 = 21000, Body1 and Body2 hidden; undo.
  F  Intersect of bodies that only touch: the reason is shown in the dialog and OK keeps it
     open; Esc cancels.
"""
import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h

V = App.Vector
state = {}


def body1():
    return s.body_named("Body1") or s.bodies()[0]


def body2():
    return s.bodies()[1]


def combines():
    return s.steps_of_kind("Combine")


# -- A ----------------------------------------------------------------------------------------
def a_open_nothing_selected():
    h.click_empty()
    h.fit()
    h.ribbon("Combine")


def a_dialog_waits():
    p = s.panel()
    h.check("Combine dialog open", p is not None and p.title == "Combine", p)
    s.no_popups("Combine")
    if p is not None:
        h.check("target box takes the first click", p.active == "target", p.active)
        h.check("hint says what to click", "target" in p.info.text().lower(), p.info.text())


def a_click_target():
    h.click(V(10, 15, 10))


def a_click_tool():
    p = s.panel()
    if p is not None:
        h.check("Body1 is the target", p.options["target"] is body1(), p.options["target"])
        h.check("tool box active now", p.active == "tools", p.active)
    h.click(V(60, 15, 10))


def a_preview():
    p = s.panel()
    h.check("Body2 is a tool", p is not None and p.options["tools"] == [body2()], p and p.options)
    h.check("preview joins: 21000", s.close(s.volume(body1()), 21000), s.volume(body1()))
    h.check("tool still shown while the dialog is open", s.shown(body2()))
    h.shot("A-preview")


def a_ok():
    h.task_button("OK")


def a_joined():
    h.check("dialog closed", s.panel() is None)
    h.check("Body1 = 21000", s.close(s.volume(body1()), 21000), s.volume(body1()))
    h.check("one block: 6 faces", len(body1().Shape.Faces) == 6, len(body1().Shape.Faces))
    h.check("Body2 used up (hidden)", not s.shown(body2()))
    tree = s.browser()
    h.check(
        "Body2 is out of the browser, like Fusion",
        tree.row(body2().Label) is None,
        tree.labels(),
    )
    h.check("one Combine step", len(combines()) == 1, combines())
    h.check("timeline shows the Combine", s.timeline_title_of(combines()[0]) is not None)
    h.shot("A-joined")


def a_undo():
    s.undo()


def a_undone():
    h.check("undo: Body1 = 12000", s.close(s.volume(body1()), 12000), s.volume(body1()))
    h.check("undo: no Combine", not combines(), combines())


def a_undone_view():
    h.check("undo: Body2 shown again", s.shown(body2()))
    tree = s.browser()
    h.check("undo: Body2 back in the browser", tree.row(body2().Label) is not None, tree.labels())


def a_redo():
    s.redo()


def a_redone():
    h.check("redo: Body1 = 21000", s.close(s.volume(body1()), 21000), s.volume(body1()))


def a_redone_view():
    h.check("redo: Body2 hidden again", not s.shown(body2()))


# -- B ----------------------------------------------------------------------------------------
def b_edit():
    s.timeline_double_click(combines()[0])


def b_choose_cut():
    p = s.panel()
    h.check("edit dialog open", p is not None and p.editing, p)
    if p is not None:
        h.check("edit shows the target", p.options["target"] is body1())
        h.check("edit shows the tool", p.options["tools"] == [body2()])
        b.choose(p.operation, "Cut")


def b_preview():
    h.check("cut preview: 9000", s.close(s.volume(body1()), 9000), s.volume(body1()))
    h.shot("B-cut")


def b_ok():
    h.task_button("OK")


def b_done():
    h.check("cut: 9000", s.close(s.volume(body1()), 9000), s.volume(body1()))
    h.check("still one Combine step", len(combines()) == 1, combines())


def b_done_view():
    h.check("Body2 still used up", not s.shown(body2()))


# -- C ----------------------------------------------------------------------------------------
def c_edit():
    s.timeline_double_click(combines()[0])


def c_keep_tools():
    p = s.panel()
    if h.check("edit dialog open", p is not None):
        s.toggle(p.keep_tools)
        h.check("Keep Tools ticked", p.keep_tools.isChecked())


def c_ok():
    h.task_button("OK")


def c_kept():
    h.check("kept tools: Body1 = 9000", s.close(s.volume(body1()), 9000), s.volume(body1()))


def c_kept_view():
    h.check("kept tools: Body2 shown", s.shown(body2()))
    h.check("Body2 intact (12000)", s.close(s.volume(body2()), 12000), s.volume(body2()))


def c_edit_again():
    s.timeline_double_click(combines()[0])


def c_intersect():
    p = s.panel()
    if h.check("edit dialog open", p is not None):
        b.choose(p.operation, "Intersect")


def c_intersect_preview():
    h.check("intersect preview: 3000", s.close(s.volume(body1()), 3000), s.volume(body1()))


def c_cancel():
    h.task_button("Cancel")


def c_cancelled():
    h.check("Cancel: dialog closed", s.panel() is None)
    h.check("Cancel: Body1 back to 9000", s.close(s.volume(body1()), 9000), s.volume(body1()))
    h.check("Cancel: still Cut", combines()[0].Operation == "Cut", combines()[0].Operation)


def c_cancelled_view():
    h.check("Cancel: Body2 still shown (kept)", s.shown(body2()))


# -- D ----------------------------------------------------------------------------------------
def d_select_body2():
    h.fit()
    h.click(V(60, 15, 10))


def d_open():
    h.ribbon("Combine")


def d_target_taken():
    p = s.panel()
    h.check("dialog open", p is not None)
    if p is not None:
        h.check("preselected Body2 is the target", p.options["target"] is body2(), p.options)
        h.check("tool box waits", p.active == "tools", p.active)


def d_click_body1():
    h.click(V(10, 15, 10))


def d_ok():
    p = s.panel()
    if p is not None:
        h.check("Body1 is the tool", p.options["tools"] == [body1()], p.options)
    h.task_button("OK")


def d_done():
    h.check("second Combine: Body2 = 21000", s.close(s.volume(body2()), 21000), s.volume(body2()))
    h.check("two Combine steps", len(combines()) == 2, combines())
    h.check("one block: 6 faces", len(body2().Shape.Faces) == 6, len(body2().Shape.Faces))


def d_done_view():
    h.check("Body1 used up", not s.shown(body1()))
    h.shot("D-second-combine")


# -- E ----------------------------------------------------------------------------------------
def e_undo():
    s.undo()


def e_open():
    h.check("undo D: Body2 = 12000", s.close(s.volume(body2()), 12000), s.volume(body2()))
    h.click_empty()
    h.fit()
    h.ribbon("Combine")


def e_target():
    h.click(V(60, 15, 10))  # Body2


def e_tool():
    h.click(V(10, 15, 10))  # Body1


def e_new_body():
    p = s.panel()
    if h.check("dialog open", p is not None):
        s.toggle(p.new_body)


def e_ok():
    h.task_button("OK")


def e_done():
    found = s.bodies()
    h.check("a third body", len(found) == 3, [x.Label for x in found])
    if len(found) == 3:
        h.check("new body = 21000", s.close(s.volume(found[2]), 21000), s.volume(found[2]))
    h.check("Body2 untouched", s.close(s.volume(body2()), 12000), s.volume(body2()))


def e_done_view():
    found = s.bodies()
    h.check("Body1 and Body2 used up", not s.shown(body1()) and not s.shown(body2()))
    if len(found) == 3:
        h.check("new body shown", s.shown(found[2]))
    h.shot("E-new-body")


def e_undo_new_body():
    s.undo()


def e_undone():
    h.check("undo: two bodies", len(s.bodies()) == 2, [x.Label for x in s.bodies()])


def e_undone_view():
    h.check("undo: both shown", s.shown(body1()) and s.shown(body2()))


# -- F ----------------------------------------------------------------------------------------
def f_open():
    h.click_empty()
    h.fit()
    h.ribbon("Combine")


def f_target():
    h.click(V(10, 15, 10))


def f_tool():
    h.click(V(60, 15, 10))


def f_intersect():
    p = s.panel()
    if h.check("dialog open", p is not None):
        b.choose(p.operation, "Intersect")


def f_reason_shown():
    p = s.panel()
    if h.check("dialog open", p is not None):
        text = p.message.text()
        h.check("the reason is in the dialog", "overlap" in text.lower(), text)
    h.shot("F-intersect-error")


def f_ok_refused():
    h.task_button("OK")


def f_still_open():
    h.check("OK refused: dialog still open", s.panel() is not None)
    s.no_popups("OK on a failing Combine")


def f_escape():
    h.press(QtCore.Qt.Key_Escape)


def f_cancelled():
    h.check("Esc closed the dialog", s.panel() is None)
    h.check("Esc: Body1 = 9000", s.close(s.volume(body1()), 9000), s.volume(body1()))
    h.check("Esc: one Combine", len(combines()) == 1, combines())


h.run(
    "bodies_combine",
    [s.new_design("Combine")]
    + s.box_steps("body1", (0, 0, 40, 30), 10, V(12, -8, 0))
    + s.box_steps("body2", (30, 0, 70, 30), 10, V(12, -8, 0), new_body=True)
    + [
        a_open_nothing_selected,
        a_dialog_waits,
        a_click_target,
        a_click_tool,
        a_preview,
        a_ok,
        a_joined,
        a_undo,
        a_undone,
        a_undone_view,
        a_redo,
        a_redone,
        a_redone_view,
        b_edit,
        b_choose_cut,
        b_preview,
        b_ok,
        b_done,
        b_done_view,
        c_edit,
        c_keep_tools,
        c_ok,
        c_kept,
        c_kept_view,
        c_edit_again,
        c_intersect,
        c_intersect_preview,
        c_cancel,
        c_cancelled,
        c_cancelled_view,
        d_select_body2,
        d_open,
        d_target_taken,
        d_click_body1,
        d_ok,
        d_done,
        d_done_view,
        e_undo,
        e_open,
        e_target,
        e_tool,
        e_new_body,
        e_ok,
        e_done,
        e_done_view,
        e_undo_new_body,
        e_undone,
        e_undone_view,
        f_open,
        f_target,
        f_tool,
        f_intersect,
        f_reason_shown,
        f_ok_refused,
        f_still_open,
        f_escape,
        f_cancelled,
    ],
)
