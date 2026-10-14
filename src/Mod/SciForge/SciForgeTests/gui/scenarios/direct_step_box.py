# SPDX-License-Identifier: LGPL-2.1-or-later
"""Press Pull, Offset Face and Delete on solids without history: STEP files opened with
FreeCAD's own import (Luca's downloaded parts), only real input after the import.

Input: two STEP files made with FreeCAD's Part module in the setup: a 20 mm cube at the
origin, and a plate 40 x 30 x 10 at x = 60 with a through hole r 5 in its middle
(12000 - 250 pi). FreeCAD's import gives plain solids: no body, no history.

  A  Q, the cube's top face, 5, OK: the cube becomes a body whose Base Feature holds the
     imported solid, and the Press Pull is a step after it (Fusion's parametric design:
     a timeline step on the imported body): 20 x 20 x 25; the imported solid is hidden.
  B  Undo: the cube is a plain solid again and shows; Redo: the body is back.
  C  Q on the plate's top, 3, Cancel: no body is left, the plate shows again.
  D  The plate's hole wall, Del: the hole closes (neighbours extended): a body with a
     Delete Face step, 12000.
  E  The plate's top face, Del: refused with the reason next to the pointer; no change.
  F  MODIFY > Offset Face, the cube's +X side, 2, OK: an "Offset Face 1" step (22 wide);
     double-click it: the Offset Face dialog edits it, 4, OK: 24 wide. Undo, Redo.
  G  Without history (the design's menu): Q on the plate's top, 2, OK: baked into the
     body, no step; Undo.
"""

import math

import FreeCAD as App
import Part
from PySide import QtCore

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import direct_steps as d
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import timeline_input as t

V = App.Vector
HOLE = 250 * math.pi
state = {}


def cube():
    return state.get("cube_body")


def plate():
    return state.get("plate_body")


def body_of_import(name):
    for body in d.bodies():
        if body.BaseFeature is not None and body.BaseFeature.Name == name:
            return body
    return None


# -- setup: the STEP files and FreeCAD's import ---------------------------------------------
def setup_files():
    cube_shape = Part.makeBox(20, 20, 20)
    plate_shape = Part.makeBox(40, 30, 10, V(60, 0, 0)).cut(Part.makeCylinder(5, 10, V(80, 15, 0)))
    state["cube_file"] = d.step_file("cube", cube_shape)
    state["plate_file"] = d.step_file("plate", plate_shape)


def import_files():
    cube_objs = d.import_step(state["cube_file"])
    plate_objs = d.import_step(state["plate_file"])
    h.check("one cube solid imported", len(cube_objs) == 1, [o.Name for o in cube_objs])
    h.check("one plate solid imported", len(plate_objs) == 1, [o.Name for o in plate_objs])
    if cube_objs and plate_objs:
        state["cube"], state["plate"] = cube_objs[0], plate_objs[0]
    h.check("no bodies yet", not d.bodies(), [b.Label for b in d.bodies()])
    h.check("both are plain solids", len(d.plain_solids()) == 2, d.plain_solids())
    h.fit()


# -- A ------------------------------------------------------------------------------------------
def a_press_pull():
    h.click_empty()
    h.press("q")


def a_click_top():
    h.click(V(6, 6, 20))


def a_type():
    p = d.press_pull_panel()
    h.check("the cube's top picked", p is not None and len(p.names) == 1, p and p.names)
    d.type_distance("5")


def a_ok():
    h.task_button("OK")


def a_done():
    body = body_of_import(state["cube"].Name)
    state["cube_body"] = body
    if not h.check("the cube is a body built on the import", body is not None):
        return
    h.check("20 x 20 x 25", d.near(d.volume(body), 10000), d.volume(body))
    titles = [x for x in t.titles() if x in ("Base Feature 1", "Press Pull 1")]
    h.check(
        "Base Feature then Press Pull", titles == ["Base Feature 1", "Press Pull 1"], t.titles()
    )
    h.check("the imported solid is hidden", not d.shown(state["cube"]))
    h.check("the body shows", d.shown(body))
    h.check("the body is in the browser", body.Label in t.labels(), t.labels())
    h.fit()


# -- B ------------------------------------------------------------------------------------------
def b_undo():
    t.undo()


def b_undone():
    h.check("undo: no body", not d.bodies(), [b.Label for b in d.bodies()])
    h.check("undo: the cube is a plain solid again", state["cube"] in d.plain_solids())
    h.check("undo: the cube shows", d.shown(state["cube"]))


def b_redo():
    t.redo()


def b_redone():
    body = body_of_import(state["cube"].Name)
    state["cube_body"] = body
    h.check("redo: the body is back", body is not None and d.near(d.volume(body), 10000))


# -- C ------------------------------------------------------------------------------------------
def c_press_pull():
    h.click_empty()
    h.press("q")


def c_click_plate():
    h.click(V(64, 4, 10))


def c_type():
    d.type_distance("3")


def c_cancel():
    h.check("a body is previewed", len(d.bodies()) == 2, [b.Label for b in d.bodies()])
    h.task_button("Cancel")


def c_cancelled():
    h.check("cancel: no plate body", len(d.bodies()) == 1, [b.Label for b in d.bodies()])
    h.check("cancel: the plate is a plain solid", state["plate"] in d.plain_solids())
    h.check("cancel: the plate shows again", d.shown(state["plate"]))


# -- D ------------------------------------------------------------------------------------------
def d_click_wall():
    h.click_empty()
    h.fit()
    a = math.radians(135)
    h.click(V(80 + 5 * math.cos(a), 15 + 5 * math.sin(a), 8))


def d_delete():
    h.press(QtCore.Qt.Key_Delete)


def d_healed():
    body = body_of_import(state["plate"].Name)
    state["plate_body"] = body
    if not h.check("the plate is a body", body is not None):
        return
    h.check("the hole closed: 12000", d.near(d.volume(body), 12000), d.volume(body))
    kinds = [getattr(o, "SciForgeType", "") or o.TypeId for o in d.solid_steps(body)]
    h.check("Base Feature then Delete Face", kinds == ["BaseFeature", "DeleteFace"], kinds)
    h.shot("D-healed")


# -- E ------------------------------------------------------------------------------------------
def e_click_top():
    h.click_empty()
    h.click(V(64, 4, 10))


def e_delete():
    h.press(QtCore.Qt.Key_Delete)


def e_refused():
    h.check("refused: still 12000", d.near(d.volume(plate()), 12000), d.volume(plate()))
    msg = d.told()
    h.check("the reason is said", "cannot be deleted" in msg, msg)
    h.check("no pop-up", not h.popups(), h.popups())


# -- F ------------------------------------------------------------------------------------------
def f_offset_face():
    h.click_empty()
    h.fit()
    d.ribbon_menu("MODIFY", "Offset Face")


def f_click_side():
    p = d.panel()
    h.check("Offset Face dialog", p is not None and p.title == "Offset Face", p)
    h.click(V(20, 5, 5))


def f_type():
    d.type_distance("2")


def f_ok():
    h.task_button("OK")


def f_done():
    h.check("22 x 20 x 25", d.near(d.volume(cube()), 22 * 20 * 25), d.volume(cube()))
    titles = t.titles()
    h.check("an Offset Face step", "Offset Face 1" in titles, titles)


def f_edit():
    h.check("double-click Offset Face 1", ui.double_click_timeline("Offset Face 1"))


def f_edit_dialog():
    p = d.press_pull_panel()
    h.check(
        "the Offset Face dialog edits it",
        p is not None and p.title == "Offset Face" and p.editing,
        p,
    )
    d.type_distance("4")


def f_edit_ok():
    h.task_button("OK")


def f_edited():
    h.check("24 x 20 x 25", d.near(d.volume(cube()), 24 * 20 * 25), d.volume(cube()))


def f_undo():
    t.undo()


def f_undone():
    h.check("undo: 22 wide again", d.near(d.volume(cube()), 22 * 20 * 25), d.volume(cube()))


def f_redo():
    t.redo()


def f_redone():
    h.check("redo: 24 wide", d.near(d.volume(cube()), 24 * 20 * 25), d.volume(cube()))


# -- G ------------------------------------------------------------------------------------------
def g_history_off():
    d.design_menu("Do Not Capture Design History")


def g_remove():
    d.answer_history(remove=True)


def g_press_pull():
    h.check("without history", d.is_direct())
    h.click_empty()
    h.fit()
    h.press("q")


def g_click_top():
    h.click(V(64, 4, 10))


def g_type():
    d.type_distance("2")


def g_ok():
    h.task_button("OK")


def g_baked():
    body = plate()
    h.check("plate 12 high: 14400", d.near(d.volume(body), 14400), d.volume(body))
    kinds = [o.TypeId for o in d.solid_steps(body)]
    h.check("one frozen step", kinds == ["PartDesign::FeatureBase"], kinds)


def g_undo():
    t.undo()


def g_undone():
    h.check("undo: 12000", d.near(d.volume(plate()), 12000), d.volume(plate()))


h.run(
    "direct_step_box",
    t.watched(
        [s.new_design("StepBox"), setup_files, import_files]
        + [
            a_press_pull,
            a_click_top,
            a_type,
            a_ok,
            a_done,
            b_undo,
            b_undone,
            b_redo,
            b_redone,
            c_press_pull,
            c_click_plate,
            c_type,
            c_cancel,
            c_cancelled,
            d_click_wall,
            d_delete,
            d_healed,
            e_click_top,
            e_delete,
            e_refused,
            f_offset_face,
            f_click_side,
            f_type,
            f_ok,
            f_done,
            f_edit,
            f_edit_dialog,
            f_edit_ok,
            f_edited,
            f_undo,
            f_undone,
            f_redo,
            f_redone,
            g_history_off,
            g_remove,
            g_press_pull,
            g_click_top,
            g_type,
            g_ok,
            g_baked,
            g_undo,
            g_undone,
        ]
    ),
)
