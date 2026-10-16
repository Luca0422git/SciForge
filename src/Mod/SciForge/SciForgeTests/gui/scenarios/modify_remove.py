# SPDX-License-Identifier: LGPL-2.1-or-later
"""Remove (MODIFY > Remove, and Remove in a body's right-click menu) like Fusion: a timeline
step from which on the body is gone; only real input.

Bodies made with Create Sketch + Extrude: a box 0..40 x 0..30 x 10 (12000) and two blocks
50..60 and 70..80 x 0..10 x 10 (New Body, 1000 each).

  A  Right-click the first block in the browser, Remove: a "Remove 1" step; the block is
     hidden and leaves the browser, nothing else changes. Undo: it is back; Redo.
  B  The history marker dragged before Remove 1: the block is back; to the end: gone again.
  C  MODIFY > Remove with nothing selected: the dialog waits; click the second block: it
     goes (previewed); OK: "Remove 2". Double-click Remove 2: clear the box, click the box:
     now the box is removed and the second block is back; OK. Edit again, clear: the box
     shows; Cancel: removed again.
  D  Delete Remove 1 in the timeline: the first block is back for good. Undo / Redo.
  E  Create Components from Bodies on the second block, Remove on the component's row: its
     body goes with a step named after the component. Undo.
  F  Without history (the design's menu): the removed box does not come back, the blocks
     stay. Remove on a block now deletes it (there is no timeline to hold a Remove), said
     next to the pointer; Undo brings it back.
"""

import FreeCAD as App

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import direct_steps as d
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import timeline_input as t
from SciForgeTests.gui import widget_input as wi

V = App.Vector
state = {}


def named(key):
    return d.doc().getObject(state[key]) if state.get(key) else None


def in_browser(body):
    rows = [x.replace("●", "").strip() for x in t.labels()]
    return body is not None and body.Label in rows


def removes():
    return [o for o in d.doc().Objects if getattr(o, "SciForgeType", "") == "Remove"]


def gone(body):
    return body is not None and not d.shown(body) and not in_browser(body)


def back(body):
    return body is not None and d.shown(body) and in_browser(body)


# -- A ------------------------------------------------------------------------------------------
def a_names():
    found = d.bodies()
    h.check("three bodies", len(found) == 3, [b.Label for b in found])
    h.check(
        "the second block on XY (y 0..10)",
        len(found) == 3 and abs(found[2].Shape.BoundBox.YMin) < 1e-6,
        found[-1].Shape.BoundBox,
    )
    state["box"], state["b1"], state["b2"] = [b.Name for b in found]


def a_menu():
    h.click_empty()
    entries = [e for e, _ok in t.row_menu_entries(named("b1").Label)]
    h.check(
        "the body's menu has Remove (before Delete)",
        "Remove" in entries and entries.index("Remove") < entries.index("Delete"),
        entries,
    )
    t.row_menu(named("b1").Label, "Remove")


def a_removed():
    h.check("Remove 1 in the timeline", "Remove 1" in t.titles(), t.titles())
    h.check("the block is gone", gone(named("b1")), t.labels())
    h.check("the others stay", back(named("box")) and back(named("b2")), t.labels())
    h.check("no pop-up", not h.popups(), h.popups())


def a_undo():
    t.undo()


def a_undone():
    h.check("undo: the block is back", back(named("b1")), t.labels())
    h.check("undo: no Remove step", not removes(), removes())


def a_redo():
    t.redo()


def a_redone():
    h.check("redo: gone again", gone(named("b1")), t.labels())


# -- B ------------------------------------------------------------------------------------------
def b_roll_back():
    t.drag_marker(before_title="Remove 1")


def b_rolled():
    h.check("rolled back: the block is back", back(named("b1")), t.labels())


def b_to_end():
    t.drag_marker(to_end=True)


def b_end():
    h.check("at the end: gone again", gone(named("b1")), t.labels())


# -- C ------------------------------------------------------------------------------------------
def c_start():
    h.click_empty()
    h.fit()
    d.ribbon_menu("MODIFY", "Remove")


def c_waits():
    p = d.panel()
    h.check("Remove dialog", p is not None and p.title == "Remove", p)
    h.check("it waits for bodies", p is not None and p.active == "objects", p and p.active)
    h.check("the second block shows", d.shown(named("b2")))
    h.shot("C-waits")


def c_click_b2():
    h.click(V(75, 5, 10))


def c_preview():
    h.check("preview: the second block is hidden", not d.shown(named("b2")))


def c_ok():
    h.task_button("OK")


def c_done():
    h.check("Remove 2", "Remove 2" in t.titles(), t.titles())
    h.check("the second block is gone", gone(named("b2")), t.labels())


def c_edit():
    h.check("double-click Remove 2", ui.double_click_timeline("Remove 2"), t.titles())


def c_clear():
    p = d.panel()
    if h.check("the edit dialog", p is not None and p.editing, p):
        wi.click(p.fields["objects"].clear)


def c_click_box():
    h.click(V(30, 20, 10))


def c_edit_preview():
    h.check("preview: the box hidden", not d.shown(named("box")))
    h.check("preview: the second block shows again", d.shown(named("b2")))


def c_edit_ok():
    h.task_button("OK")


def c_edited():
    h.check("the box is gone", gone(named("box")), t.labels())
    h.check("the second block is back", back(named("b2")), t.labels())
    h.check("still two Remove steps", len(removes()) == 2, removes())


def c_edit_again():
    h.check("double-click Remove 2 again", ui.double_click_timeline("Remove 2"), t.titles())


def c_clear_again():
    p = d.panel()
    if h.check("the edit dialog", p is not None and p.editing, p):
        wi.click(p.fields["objects"].clear)


def c_cleared():
    h.check("cleared: the box shows (previewed)", d.shown(named("box")))
    h.task_button("Cancel")


def c_cancelled():
    h.check("cancel: the box is removed again", gone(named("box")), t.labels())
    h.check("cancel: two Remove steps", len(removes()) == 2, removes())


# -- D ------------------------------------------------------------------------------------------
def d_delete():
    h.click_empty()
    t.menu("Remove 1", "Delete")


def d_deleted():
    h.check(
        "one Remove step left (the timeline numbers it Remove 1 now)",
        len(removes()) == 1 and t.titles().count("Remove 1") == 1,
        t.titles(),
    )
    h.check("the first block is back", back(named("b1")), t.labels())


def d_undo():
    t.undo()


def d_undone():
    h.check("undo: removed again", gone(named("b1")), t.labels())


def d_redo():
    t.redo()


def d_redone():
    h.check("redo: back", back(named("b1")), t.labels())


# -- E ------------------------------------------------------------------------------------------
def e_component():
    h.click_empty()
    t.row_menu(named("b2").Label, "Create Components from Bodies")


def e_remove_component():
    from sciforge import components

    part = components.component_of(named("b2"))
    if not h.check("the block is in a component", part is not None):
        return
    state["part"] = part.Name
    state["steps"] = len(removes())
    t.row_menu(part.Label, "Remove")


def e_removed():
    part = named("part")
    made = removes()[state["steps"] :] if state.get("steps") is not None else []
    h.check(
        "one more Remove step, named after the component",
        len(made) == 1 and part is not None and made[0].Label == "Remove %s" % part.Label,
        [o.Label for o in made],
    )
    h.check("the component's body is gone", not d.shown(named("b2")))


def e_undo():
    t.undo()


def e_undone():
    h.check("undo: the component's body is back", d.shown(named("b2")))


# -- F ------------------------------------------------------------------------------------------
def f_history_off():
    d.design_menu("Do Not Capture Design History")


def f_remove_history():
    d.answer_history(remove=True)


def f_direct():
    d.wait_timeline()
    h.check("without history", d.is_direct())
    h.check(
        "the removed box does not come back",
        named("box") is None or not d.shown(named("box")),
        [b.Label for b in d.bodies()],
    )
    h.check(
        "two blocks left",
        sorted(b.Name for b in d.bodies()) == sorted([state["b1"], state["b2"]]),
        [b.Label for b in d.bodies()],
    )
    h.check("both shown", d.shown(named("b1")) and d.shown(named("b2")))


def f_remove():
    h.click_empty()
    h.fit()
    entries = [e for e, _ok in t.row_menu_entries(named("b1").Label)]
    h.check(
        "no Remove in a body's menu without history (Delete is there)",
        "Remove" not in entries and "Delete" in entries,
        entries,
    )
    h.click(V(55, 5, 10))


def f_modify_remove():
    h.check("the block selected", bool(d.selected()), d.selected())
    d.ribbon_menu("MODIFY", "Remove")


def f_deleted():
    h.check("the block is deleted", named("b1") is None, [b.Label for b in d.bodies()])
    msg = d.told()
    h.check("said why", "does not capture history" in msg, msg)


def f_undo():
    t.undo()


def f_undone():
    h.check("undo: the block is back", named("b1") is not None and d.shown(named("b1")))


h.run(
    "modify_remove",
    t.watched(
        [s.new_design("Remove")]
        + s.box_steps("box", (0, 0, 40, 30), 10, V(6, -6, 0))
        + s.box_steps("b1", (50, 0, 60, 10), 10, V(6, -6, 0), new_body=True)
        + s.box_steps("b2", (70, 0, 80, 10), 10, V(5, -5, 0), new_body=True)
        + [
            a_names,
            a_menu,
            a_removed,
            a_undo,
            a_undone,
            a_redo,
            a_redone,
            b_roll_back,
            b_rolled,
            b_to_end,
            b_end,
            c_start,
            c_waits,
            c_click_b2,
            c_preview,
            c_ok,
            c_done,
            c_edit,
            c_clear,
            c_click_box,
            c_edit_preview,
            c_edit_ok,
            c_edited,
            c_edit_again,
            c_clear_again,
            c_cleared,
            c_cancelled,
            d_delete,
            d_deleted,
            d_undo,
            d_undone,
            d_redo,
            d_redone,
            e_component,
            e_remove_component,
            e_removed,
            e_undo,
            e_undone,
            f_history_off,
            f_remove_history,
            f_direct,
            f_remove,
            f_modify_remove,
            f_deleted,
            f_undo,
            f_undone,
        ]
    ),
)
