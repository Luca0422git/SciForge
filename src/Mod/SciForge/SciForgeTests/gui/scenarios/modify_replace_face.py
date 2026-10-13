# SPDX-License-Identifier: LGPL-2.1-or-later
"""Replace Face (MODIFY > Replace Face) like Fusion, only real input.

Bodies made with Create Sketch + Extrude: Body 0..40 x 0..30 x 10 (12000), a taller block
50..70 x 0..30 x 15 (New Body) and a low block 80..100 x 0..30 x 6 (New Body).

  A  MODIFY > Replace Face with nothing selected: the dialog waits for the source faces;
     Tangent Chain is on (Fusion's default).
  B  Click Body's top face, then the Target Faces box, then the tall block's top face: the
     top goes up to 15 (18000), previewed; OK: a "Replace Face 1" step. Undo / Redo.
  C  Double-click Replace Face 1: clear the target (its x), click the low block's top:
     the top comes down to 6 (7200); OK.
  D  Edit again: the tall block's side face as the target (it does not lie in front of the
     top face): the reason is said in the dialog and OK keeps the dialog open; Cancel: still
     7200.
  E  A step sees the design as it is at its place in the timeline: a Press Pull on the low
     block after Replace Face 1 leaves Body at 7200; editing the low block's Extrude (before
     Replace Face 1) to 8 moves Body's top with it: 9600, no error.
"""

import FreeCAD as App

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import direct_steps as d
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import timeline_input as t

V = App.Vector


def body():
    return d.bodies()[0]


def vol():
    return d.volume(body())


def replace_steps():
    return [o for o in d.doc().Objects if getattr(o, "SciForgeType", "") == "ReplaceFace"]


# -- A ------------------------------------------------------------------------------------------
def a_start():
    h.click_empty()
    h.fit()
    d.ribbon_menu("MODIFY", "Replace Face")


def a_waits():
    p = d.panel()
    h.check("Replace Face dialog", p is not None and p.title == "Replace Face", p)
    if p is None:
        return
    h.check("the source box takes the clicks", p.active == "faces", p.active)
    h.check("Tangent Chain on by default", p.tangent.isChecked())
    h.check("the hint asks for faces", "faces" in p.info.text().lower(), p.info.text())
    h.check("no pop-up", not h.popups(), h.popups())


# -- B ------------------------------------------------------------------------------------------
def b_click_top():
    h.click(V(30, 22, 10))


def b_target_box():
    p = d.panel()
    h.check(
        "one source face",
        p is not None and p.options["faces"] is not None and len(p.options["faces"][1]) == 1,
        p and p.options,
    )
    d.click_box("target")


def b_click_target():
    h.click(V(60, 22, 15))


def b_preview():
    h.check("preview: up to 15 (18000)", d.near(vol(), 18000), (vol(), d.message()))
    h.shot("B-preview")


def b_ok():
    h.task_button("OK")


def b_done():
    h.check("dialog closed", d.panel() is None)
    h.check("18000", d.near(vol(), 18000), vol())
    titles = t.titles()
    h.check("a Replace Face step", "Replace Face 1" in titles, titles)


def b_undo():
    t.undo()


def b_undone():
    h.check("undo: 12000", d.near(vol(), 12000), vol())
    h.check("undo: no step", not replace_steps())


def b_redo():
    t.redo()


def b_redone():
    h.check("redo: 18000", d.near(vol(), 18000), vol())


# -- C ------------------------------------------------------------------------------------------
def c_edit():
    h.fit()
    h.check("double-click Replace Face 1", ui.double_click_timeline("Replace Face 1"))


def c_clear_target():
    p = d.panel()
    if not h.check("the edit dialog", p is not None and p.editing, p):
        return
    h.check("the target box is active", p.active == "target", p.active)
    w = p.fields["target"].clear
    from SciForgeTests.gui import widget_input as wi

    wi.click(w)


def c_click_low():
    h.click(V(90, 22, 6))


def c_preview():
    h.check("preview: down to 6 (7200)", d.near(vol(), 7200), (vol(), d.message()))


def c_ok():
    h.task_button("OK")


def c_done():
    h.check("7200", d.near(vol(), 7200), vol())
    h.check("still one step", len(replace_steps()) == 1, replace_steps())


# -- D ------------------------------------------------------------------------------------------
def d_edit():
    h.check("double-click Replace Face 1 again", ui.double_click_timeline("Replace Face 1"))


def d_clear():
    p = d.panel()
    if not h.check("the edit dialog", p is not None, p):
        return
    from SciForgeTests.gui import widget_input as wi

    wi.click(p.fields["target"].clear)


def d_click_side():
    h.click(V(70, 15, 8))


def d_refused():
    msg = d.message()
    h.check("the reason is said", "does not lie in front" in msg, msg)


def d_ok():
    h.task_button("OK")


def d_still_open():
    p = d.panel()
    h.check("OK keeps the dialog open", p is not None and not p._closed, p)


def d_cancel():
    h.task_button("Cancel")


def d_cancelled():
    h.check("cancel: still 7200", d.near(vol(), 7200), vol())
    h.check("dialog closed", d.panel() is None)


# -- E ------------------------------------------------------------------------------------------
def e_press_pull_low():
    h.click_empty()
    h.press("q")


def e_click_low():
    h.click(V(95, 26, 6))


def e_type():
    d.type_distance("2")


def e_ok():
    h.task_button("OK")


def e_after():
    h.check("a later Press Pull on the target does not move Body", d.near(vol(), 7200), vol())


def e_edit_extrude():
    h.click_empty()
    h.fit()
    h.check("double-click Extrude 3", ui.double_click_timeline("Extrude 3"), t.titles())


def e_type_8():
    p = d.panel()
    field = getattr(getattr(p, "distance", None), "widget", None)
    if h.check("the Extrude dialog edits it", field is not None and p.editing, p):
        ui.type_into(field, "8")


def e_extrude_ok():
    h.task_button("OK")


def e_followed():
    h.check("Body follows its target: 9600", d.near(vol(), 9600), vol())
    state = t.states().get("Replace Face 1", ("", "?"))
    h.check("Replace Face 1 has no error", state[1] == "ok", t.states())


h.run(
    "modify_replace_face",
    t.watched(
        [s.new_design("ReplaceFace")]
        + s.box_steps("box", (0, 0, 40, 30), 10, V(12, -8, 0))
        + s.box_steps("tall", (50, 0, 70, 30), 15, V(12, -8, 0), new_body=True)
        + s.box_steps("low", (80, 0, 100, 30), 6, V(12, -8, 0), new_body=True)
        + [
            a_start,
            a_waits,
            b_click_top,
            b_target_box,
            b_click_target,
            b_preview,
            b_ok,
            b_done,
            b_undo,
            b_undone,
            b_redo,
            b_redone,
            c_edit,
            c_clear_target,
            c_click_low,
            c_preview,
            c_ok,
            c_done,
            d_edit,
            d_clear,
            d_click_side,
            d_refused,
            d_ok,
            d_still_open,
            d_cancel,
            d_cancelled,
            e_press_pull_low,
            e_click_low,
            e_type,
            e_ok,
            e_after,
            e_edit_extrude,
            e_type_8,
            e_extrude_ok,
            e_followed,
        ]
    ),
)
