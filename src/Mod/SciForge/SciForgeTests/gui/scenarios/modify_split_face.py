# SPDX-License-Identifier: LGPL-2.1-or-later
"""Split Face (MODIFY > Split Face) like Fusion, only real input.

Body: rectangle -20..20 x -15..15 extruded 10 (12000), so the origin planes cross it. A tool
block 25..35 x -5..5 x 20 beside it (New Body).

  A  MODIFY > Split Face with nothing selected: the dialog waits for the faces; Split Type is
     Split with Surface and Extend Splitting Tool is off (Fusion's defaults).
  B  Body's top face, then the Splitting Tool box: the origin squares show; the YZ square:
     the top is split at x = 0 (one more face, same volume), previewed; OK: a "Split Face 1"
     step. Undo / Redo.
  C  What a split face is for: Q on the top's +X half, 3, OK: only that half goes up
     (12000 + 20 x 30 x 3 = 13800).
  D  Split Face again: Body's +X side, then the tool block's front face (it lies beside
     Body): the reason is said in the dialog and OK keeps it open; tick Extend Splitting
     Tool: its plane y = -5 splits the side (one more face); OK: "Split Face 2".
  E  Double-click Split Face 2: Split Type Closest Point (the Extend box goes), clear the
     tool, click the tool block in the browser: its edges nearest the side split it at
     y = -5 and y = 5 (two more faces than before Split Face 2); OK; the volume never changed.
  F  Save, close, open: both splits are still there and nothing is in error.
"""

import os

import FreeCAD as App

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import direct_steps as d
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import timeline_input as t
from SciForgeTests.gui import widget_input as wi

V = App.Vector
state = {}


def body():
    return d.bodies()[0]


def tool_body():
    return d.bodies()[1]


def vol():
    return d.volume(body())


def faces():
    return len(body().Shape.Faces)


def splits():
    return [o for o in d.doc().Objects if getattr(o, "SciForgeType", "") == "SplitFace"]


def errors():
    return {k: v for k, v in t.states().items() if v[1] not in ("ok", "")}


# -- A ------------------------------------------------------------------------------------------
def a_start():
    state["faces0"] = faces()
    h.click_empty()
    h.fit()
    d.ribbon_menu("MODIFY", "Split Face")


def a_waits():
    p = d.panel()
    if not h.check("Split Face dialog", p is not None and p.title == "Split Face", p):
        return
    h.check("the faces box takes the clicks", p.active == "faces", p.active)
    h.check(
        "Split with Surface by default",
        p.split_type.currentData() == "surface",
        p.split_type.currentText(),
    )
    h.check("Extend Splitting Tool off by default", not p.extend.isChecked())
    h.check("no pop-up", not h.popups(), h.popups())


# -- B ------------------------------------------------------------------------------------------
def b_click_top():
    h.click(V(-10, -8, 10))


def b_tool_box():
    p = d.panel()
    picked = p is not None and p.options["faces"] is not None and len(p.options["faces"][1]) == 1
    h.check("one face picked", picked, p and p.options)
    d.click_box("tool")


def b_click_yz():
    p = d.panel()
    h.check("the tool box waits", p is not None and p.active == "tool", p and p.active)
    h.check("the origin squares show", p is not None and p.squares.picker is not None)
    pl.click_square("YZ_Plane")  # where the square shows (was 0, -24, 20)


def b_preview():
    p = d.panel()
    h.check("YZ plane picked", p is not None and p.options["tool"] is not None, p and p.options)
    h.check("preview: one more face", faces() == state["faces0"] + 1, faces())
    h.check("same volume", d.near(vol(), 12000), vol())
    h.check(
        "the dialog says so", p is not None and "1 more face" in p.note.text(), p and p.note.text()
    )
    h.shot("B-preview")


def b_ok():
    h.task_button("OK")


def b_done():
    h.check("dialog closed", d.panel() is None)
    titles = t.titles()
    h.check("a Split Face step", "Split Face 1" in titles, titles)
    h.check("split", faces() == state["faces0"] + 1, faces())


def b_undo():
    t.undo()


def b_undone():
    h.check("undo: no split", faces() == state["faces0"], faces())
    h.check("undo: no step", not splits(), splits())


def b_redo():
    t.redo()


def b_redone():
    h.check("redo: split again", faces() == state["faces0"] + 1, faces())


# -- C ------------------------------------------------------------------------------------------
def c_press_pull():
    h.click_empty()
    h.fit()
    h.press("q")


def c_click_half():
    h.click(V(10, -8, 10))


def c_type():
    p = d.press_pull_panel()
    h.check("one face (the half)", p is not None and len(p.names) == 1, p and p.names)
    d.type_distance("3")


def c_ok():
    h.task_button("OK")


def c_done():
    h.check("only the half went up: 13800", d.near(vol(), 13800), vol())
    h.check("Press Pull 1", "Press Pull 1" in t.titles(), t.titles())
    state["faces1"] = faces()


# -- D ------------------------------------------------------------------------------------------
def d_start():
    h.click_empty()
    h.fit()
    d.ribbon_menu("MODIFY", "Split Face")


def d_click_side():
    h.click(V(20, -10, 4))


def d_tool_box():
    d.click_box("tool")


def d_click_tool_face():
    h.click(V(30, -5, 12))


def d_refused():
    msg = d.message()
    h.check("the reason is said", "does not cross" in msg, msg)
    h.check("nothing split", faces() == state["faces1"], faces())


def d_ok_refused():
    h.task_button("OK")


def d_still_open():
    p = d.panel()
    h.check("OK keeps the dialog open", p is not None and not p._closed, p)


def d_extend():
    p = d.panel()
    if h.check("the Extend box shows", p is not None and p.extend.isVisible()):
        s.toggle(p.extend)


def d_extended():
    p = d.panel()
    h.check("Extend ticked", p is not None and p.extend.isChecked())
    h.check("the side is split", faces() == state["faces1"] + 1, (faces(), d.message()))
    h.check("no reason shown any more", "does not cross" not in d.message(), d.message())


def d_ok():
    h.task_button("OK")


def d_done():
    h.check("dialog closed", d.panel() is None)
    h.check("Split Face 2", "Split Face 2" in t.titles(), t.titles())
    h.check("volume kept", d.near(vol(), 13800), vol())


# -- E ------------------------------------------------------------------------------------------
def e_edit():
    h.check("double-click Split Face 2", ui.double_click_timeline("Split Face 2"), t.titles())


def e_closest():
    p = d.panel()
    if not h.check("the edit dialog", p is not None and p.editing, p):
        return
    h.check("it shows Extend ticked", p.extend.isChecked())
    d.choose("split_type", "Closest Point")


def e_clear_tool():
    p = d.panel()
    h.check("the Extend box goes", not p.extend.isVisible())
    wi.click(p.fields["tool"].clear)


def e_tool_body():
    p = d.panel()
    h.check("the tool box waits", p.active == "tool", p.active)
    s.click_browser_row(tool_body().Label)


def e_preview():
    p = d.panel()
    h.check(
        "the tool block picked",
        p.options["tool"] is not None and p.options["tool"][0] is tool_body(),
        p.options["tool"],
    )
    h.check("split at y = -5 and y = 5", faces() == state["faces1"] + 2, (faces(), d.message()))


def e_ok():
    h.task_button("OK")


def e_done():
    h.check("dialog closed", d.panel() is None)
    h.check("still two more faces", faces() == state["faces1"] + 2, faces())
    h.check("volume never changed", d.near(vol(), 13800), vol())
    h.check("no step in error", not errors(), errors())
    h.check("still two Split Face steps", len(splits()) == 2, splits())


# -- F ------------------------------------------------------------------------------------------
def f_save_close_open():
    state["faces2"] = faces()
    path = os.path.join(h.OUT_DIR, "modify_split_face.FCStd")
    if os.path.exists(path):
        os.remove(path)
    App.ActiveDocument.saveAs(path)
    App.closeDocument(App.ActiveDocument.Name)
    App.openDocument(path)


def f_reopened():
    d.doc().recompute()
    h.check("reopened: same faces", faces() == state["faces2"], faces())
    h.check("reopened: same volume", d.near(vol(), 13800), vol())
    titles = t.titles()
    h.check("reopened: both steps", "Split Face 1" in titles and "Split Face 2" in titles, titles)
    h.check("reopened: no step in error", not errors(), errors())


h.run(
    "modify_split_face",
    t.watched(
        [s.new_design("SplitFace")]
        + s.box_steps("box", (-20, -15, 20, 15), 10, V(12, -22, 0))
        + s.box_steps("tool", (25, -5, 35, 5), 20, V(5, -24, 0), new_body=True)
        + [
            a_start,
            a_waits,
            b_click_top,
            b_tool_box,
            b_click_yz,
            b_preview,
            b_ok,
            b_done,
            b_undo,
            b_undone,
            b_redo,
            b_redone,
            c_press_pull,
            c_click_half,
            c_type,
            c_ok,
            c_done,
            d_start,
            d_click_side,
            d_tool_box,
            d_click_tool_face,
            d_refused,
            d_ok_refused,
            d_still_open,
            d_extend,
            d_extended,
            d_ok,
            d_done,
            e_edit,
            e_closest,
            e_clear_tool,
            e_tool_body,
            e_preview,
            e_ok,
            e_done,
            f_save_close_open,
            f_reopened,
        ]
    ),
)
