# SPDX-License-Identifier: LGPL-2.1-or-later
"""Capture Design History on and off (Fusion: right-click the design's top row), only real
input.

Part: box 0..40 x 0..30 x 10 made with Create Sketch + Extrude, a through hole r 5 at
(20, 15) cut with Extrude: 12000 - 250 pi.

  A  the design's menu offers "Do Not Capture Design History"; the question comes up and
     Cancel keeps everything (steps, timeline).
  B  Remove History: the timeline goes away, the body is one frozen step (its base
     feature), same volume, the sketches stay; the Report view stays clean.
  C  Undo brings the history back (steps, timeline); Redo takes it away again.
  D  Without history: Q on the top face, 5, OK: the body grows (18000 - 375 pi) and is
     still one step (no Press Pull step); Undo / Redo.
  E  Without history: the hole's wall, Del: the hole closes (the neighbours grow), still
     one step; the top face, Del: refused with the reason, nothing changes.
  F  Save, close, open again: still without history, no timeline, same body.
  G  The design's menu now offers "Capture Design History": the timeline comes back with
     the body's Base Feature; a Press Pull after it is a step of its own again.
"""

import math
import os

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import direct_steps as d
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import pattern_steps as ps
from SciForgeTests.gui import timeline_input as t

V = App.Vector
HOLE = 250 * math.pi
state = {}


def body():
    return d.bodies()[0]


def vol():
    return d.volume(body())


def steps():
    return d.solid_steps(body())


# -- A ------------------------------------------------------------------------------------------
def a_part_made():
    h.check("part volume", d.near(vol(), 12000 - HOLE), vol())
    state["steps"] = [o.Name for o in steps()]
    h.check("two extrudes", len(state["steps"]) == 2, state["steps"])
    h.check("timeline shown", d.timeline_shown())
    entries = d.design_menu_entries()
    h.check(
        "the design's menu offers Do Not Capture Design History",
        "Do Not Capture Design History" in entries,
        entries,
    )


def a_menu():
    d.design_menu("Do Not Capture Design History")


def a_cancel():
    d.answer_history(remove=False)


def a_kept():
    h.check("question closed", d.history_dialog() is None)
    h.check("still captures history", not d.is_direct())
    h.check("steps kept", [o.Name for o in steps()] == state["steps"], [o.Name for o in steps()])
    h.check("timeline still shown", d.timeline_shown())


# -- B ------------------------------------------------------------------------------------------
def b_menu():
    d.design_menu("Do Not Capture Design History")


def b_remove():
    d.answer_history(remove=True)


def b_direct():
    d.wait_timeline()
    h.check("design without history", d.is_direct())
    h.check("the timeline is gone", not d.timeline_shown())
    names = [o.TypeId for o in steps()]
    h.check("one frozen step", names == ["PartDesign::FeatureBase"], names)
    h.check("same volume", d.near(vol(), 12000 - HOLE), vol())
    sketches = [o for o in body().Group if o.TypeId == "Sketcher::SketchObject"]
    h.check("the sketches stay", len(sketches) == 2, [o.Label for o in sketches])
    h.check("the body shows", d.shown(body()) and d.shown(body().Tip))
    h.shot("B-without-history")


# -- C ------------------------------------------------------------------------------------------
def c_undo():
    t.undo()


def c_undone():
    d.wait_timeline()
    h.check("undo: history captured again", not d.is_direct())
    h.check(
        "undo: the steps are back",
        [o.Name for o in steps()] == state["steps"],
        [o.Name for o in steps()],
    )
    h.check("undo: timeline shown", d.timeline_shown())
    h.check("undo: same volume", d.near(vol(), 12000 - HOLE), vol())


def c_redo():
    t.redo()


def c_redone():
    d.wait_timeline()
    h.check("redo: without history", d.is_direct())
    h.check("redo: one step", len(steps()) == 1, [o.Name for o in steps()])
    h.check("redo: timeline gone", not d.timeline_shown())


# -- D ------------------------------------------------------------------------------------------
def d_press_pull():
    h.click_empty()
    h.fit()
    h.press("q")


def d_click_top():
    h.click(V(34, 25, 10))


def d_type():
    p = d.press_pull_panel()
    h.check("top face picked", p is not None and len(p.names) == 1, p and p.names)
    d.type_distance("5")


def d_ok():
    h.task_button("OK")


def d_baked():
    h.check("grown by 5: 18000 - 375 pi", d.near(vol(), 18000 - 1.5 * HOLE), vol())
    h.check("still one step (no Press Pull step)", len(steps()) == 1, [o.Name for o in steps()])
    h.check(
        "no Press Pull in the design",
        not [o for o in d.doc().Objects if getattr(o, "SciForgeType", "") == "PressPull"],
    )
    h.fit()


def d_undo():
    t.undo()


def d_undone():
    h.check("undo: back to 10 high", d.near(vol(), 12000 - HOLE), vol())
    h.check("undo: still one step", len(steps()) == 1, [o.Name for o in steps()])
    h.check("undo: still without history", d.is_direct())


def d_redo():
    t.redo()


def d_redone():
    h.check("redo: 15 high again", d.near(vol(), 18000 - 1.5 * HOLE), vol())


# -- E ------------------------------------------------------------------------------------------
def e_click_wall():
    h.click_empty()
    h.fit()
    a = math.radians(135)
    h.click(V(20 + 5 * math.cos(a), 15 + 5 * math.sin(a), 12))


def e_delete():
    h.press(QtCore.Qt.Key_Delete)


def e_closed():
    h.check("the hole closed: 18000", d.near(vol(), 18000), vol())
    h.check("still one step", len(steps()) == 1, [o.Name for o in steps()])
    h.shot("E-hole-closed")


def e_click_top():
    h.click_empty()
    h.click(V(30, 20, 15))


def e_delete_top():
    h.press(QtCore.Qt.Key_Delete)


def e_refused():
    h.check("top face refused: nothing changed", d.near(vol(), 18000), vol())
    msg = d.told()
    h.check("the reason is said", "cannot be deleted" in msg and "extended" in msg, msg)
    h.check("no pop-up", not h.popups(), h.popups())


# -- F ------------------------------------------------------------------------------------------
def f_save_close_open():
    path = os.path.join(h.OUT_DIR, "direct_history.FCStd")
    if os.path.exists(path):
        os.remove(path)
    state["path"] = path
    App.ActiveDocument.saveAs(path)
    App.closeDocument(App.ActiveDocument.Name)
    App.openDocument(path)


def f_reopened():
    d.wait_timeline()
    h.check("reopened: without history", d.is_direct())
    h.check("reopened: no timeline", not d.timeline_shown())
    h.check("reopened: one step", len(steps()) == 1, [o.Name for o in steps()])
    h.check("reopened: same volume", d.near(vol(), 18000), vol())
    h.fit()


# -- G ------------------------------------------------------------------------------------------
def g_menu():
    entries = d.design_menu_entries()
    h.check(
        "the design's menu offers Capture Design History",
        "Capture Design History" in entries,
        entries,
    )
    d.design_menu("Capture Design History")


def g_captured():
    d.wait_timeline()
    h.check("history captured", not d.is_direct())
    h.check("the timeline is back", d.timeline_shown())
    titles = t.titles()
    h.check("the timeline starts with the Base Feature", titles[:1] == ["Base Feature 1"], titles)
    base = body().Group[0]
    h.check("the base feature has an id", getattr(base, "SciForgeBaseId", ""), base.Name)


def g_press_pull():
    h.click_empty()
    h.fit()
    h.press("q")


def g_click_top():
    h.click(V(30, 20, 15))


def g_type():
    d.type_distance("2")


def g_ok():
    h.task_button("OK")


def g_step():
    titles = t.titles()
    h.check("Press Pull is a step again", "Press Pull 1" in titles, titles)
    h.check("two solid steps", len(steps()) == 2, [o.Name for o in steps()])
    h.check("17 high", d.near(vol(), 40 * 30 * 17), vol())


h.run(
    "direct_history",
    t.watched(
        [s.new_design("History")]
        + s.box_steps("box", (0, 0, 40, 30), 10, V(12, -8, 0))
        + ps.make_cut("hole", (20, 15), 5, 10)
        + [
            a_part_made,
            a_menu,
            a_cancel,
            a_kept,
            b_menu,
            b_remove,
            b_direct,
            c_undo,
            c_undone,
            c_redo,
            c_redone,
            d_press_pull,
            d_click_top,
            d_type,
            d_ok,
            d_baked,
            d_undo,
            d_undone,
            d_redo,
            d_redone,
            e_click_wall,
            e_delete,
            e_closed,
            e_click_top,
            e_delete_top,
            e_refused,
            f_save_close_open,
            f_reopened,
            g_menu,
            g_captured,
            g_press_pull,
            g_click_top,
            g_type,
            g_ok,
            g_step,
        ]
    ),
)
