# SPDX-License-Identifier: LGPL-2.1-or-later
"""Create Base Feature (SOLID > CREATE), Finish Base Feature, editing a base feature from
the timeline, only real input.

Part: Body "Body" 0..40 x 0..30 x 10 made with Create Sketch + Extrude (12000).

  A  CREATE > Create Base Feature: the Finish Base Feature bar shows over the view.
  B  Inside it: a plate 60..100 x 0..30 x 10 (sketch + Extrude, New Body), a hole r 4 cut
     through it (sketch on its top + Extrude), its top pulled up 2 (Q): the plate's body
     is one "Base Feature 1" step in the timeline, never Extrude / Press Pull steps, and
     its sketches are not in the timeline (they are in the browser). 36000 - 192 pi.
  C  A Press Pull on the other body while the base feature is open stays a step of its own.
  D  Finish Base Feature (the bar): the bar goes; a Press Pull on the plate afterwards is
     a step after the base feature ("Press Pull 2").
  E  Double-click "Base Feature 1": the design is rolled back to it (Press Pull 2 waits),
     the bar says what is edited; Q, the plate's +X side, 5, OK: baked into the base
     feature (no new step); Undo / Redo; Finish: the marker goes back to the end and
     Press Pull 2 builds on the edited plate.
  F  Edit it again: the hole's wall, Del: the hole closes inside the base feature; Finish.
  G  Save, close, open: the base feature is still one step and can be edited again.
"""

import math
import os

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import direct_steps as d
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import pattern_steps as ps
from SciForgeTests.gui import timeline_input as t

V = App.Vector
state = {}
HOLE = 16 * math.pi * 12  # r 4 through 12 mm


def first():
    return d.bodies()[0]


def plate():
    found = [b for b in d.bodies() if b is not first()]
    return found[0] if found else None


def plate_volume():
    return d.volume(plate())


# -- A ------------------------------------------------------------------------------------------
def a_create():
    h.check("box made: 12000", d.near(d.volume(first()), 12000), d.volume(first()))
    h.click_empty()
    d.ribbon_menu("CREATE", "Create Base Feature")


def a_open():
    h.check("a base feature is open", d.session() is not None)
    h.check("the Finish Base Feature bar shows", d.bar() is not None)
    h.shot("A-bar")


# -- B (inside the base feature) -----------------------------------------------------------------
def b_plate_made():
    body = plate()
    if not h.check("the plate is a new body", body is not None, [b.Label for b in d.bodies()]):
        return
    h.check("plate 40 x 30 x 10", d.near(d.volume(body), 12000), d.volume(body))
    kinds = [o.TypeId for o in d.solid_steps(body)]
    h.check("the plate is one frozen step", kinds == ["PartDesign::FeatureBase"], kinds)
    titles = t.titles()
    h.check("Base Feature 1 in the timeline", "Base Feature 1" in titles, titles)
    h.check("no Extrude 2 step", "Extrude 2" not in titles, titles)


def b_hole_cut():
    body = plate()
    h.check(
        "the hole is cut: 12000 - 160 pi",
        d.near(d.volume(body), 12000 - 160 * math.pi),
        d.volume(body),
    )
    kinds = [o.TypeId for o in d.solid_steps(body)]
    h.check("still one frozen step", kinds == ["PartDesign::FeatureBase"], kinds)
    titles = t.titles()
    h.check(
        "no sketch of the base feature in the timeline",
        [x for x in titles if x.startswith("Sketch")] == ["Sketch 1"],
        titles,
    )


def b_press_pull():
    h.click_empty()
    h.fit()
    h.press("q")


def b_click_top():
    h.click(V(94, 26, 10))


def b_type():
    d.type_distance("2")


def b_ok():
    h.task_button("OK")


def b_pulled():
    h.check(
        "the plate is 12 high: 14400 - 192 pi", d.near(plate_volume(), 14400 - HOLE), plate_volume()
    )
    titles = t.titles()
    h.check("still only the Base Feature", "Press Pull 1" not in titles, titles)
    h.check("the base feature is still open", d.session() is not None)


# -- C ------------------------------------------------------------------------------------------
def c_press_pull_other():
    h.click_empty()
    h.press("q")


def c_click_box_top():
    h.click(V(30, 22, 10))


def c_type():
    d.type_distance("3")


def c_ok():
    h.task_button("OK")


def c_step():
    titles = t.titles()
    h.check("a Press Pull on the other body is a step", "Press Pull 1" in titles, titles)
    h.check("the other body 13 high", d.near(d.volume(first()), 15600), d.volume(first()))


# -- D ------------------------------------------------------------------------------------------
def d_finish():
    d.finish_bar()


def d_finished():
    h.check("the base feature is closed", d.session() is None)
    h.check("the bar is gone", d.bar() is None)


def d_press_pull():
    h.click_empty()
    h.press("q")


def d_click_top():
    h.click(V(94, 26, 12))


def d_type():
    d.type_distance("3")


def d_ok():
    h.task_button("OK")


def d_step():
    titles = t.titles()
    h.check("Press Pull 2 after the base feature", "Press Pull 2" in titles, titles)
    h.check(
        "the plate 15 high: 18000 - 240 pi",
        d.near(plate_volume(), 18000 - 240 * math.pi),
        plate_volume(),
    )
    state["pp2"] = t.obj("Press Pull 2")


# -- E ------------------------------------------------------------------------------------------
def e_edit():
    h.check("double-click Base Feature 1", ui.double_click_timeline("Base Feature 1"))


def e_editing():
    h.check("editing the base feature", d.session() is not None and d.session().editing)
    bar = d.bar()
    h.check(
        "the bar says what is edited",
        bar is not None and "Editing" in bar.label.text(),
        bar and bar.label.text(),
    )
    states = t.states()
    h.check(
        "Press Pull 2 waits (rolled back)",
        states.get("Press Pull 2", ("",))[0] == "rolled_back",
        states,
    )
    h.check("the plate is back to 12 high", d.near(plate_volume(), 14400 - HOLE), plate_volume())


def e_press_pull():
    h.click_empty()
    h.fit()
    h.press("q")


def e_click_side():
    h.click(V(100, 26, 6))


def e_type():
    d.type_distance("5")


def e_ok():
    h.task_button("OK")


def e_baked():
    h.check(
        "the plate 45 long: 45 x 30 x 12 - hole",
        d.near(plate_volume(), 16200 - HOLE),
        plate_volume(),
    )
    kinds = [o.TypeId for o in d.solid_steps(plate())]
    h.check(
        "the edit is in the base feature",
        kinds[0] == "PartDesign::FeatureBase"
        and len([k for k in kinds if k == "PartDesign::FeatureBase"]) == 1,
        kinds,
    )
    h.check("no Press Pull 3", "Press Pull 3" not in t.titles(), t.titles())


def e_undo():
    t.undo()


def e_undone():
    h.check("undo: 40 long again", d.near(plate_volume(), 14400 - HOLE), plate_volume())
    h.check("undo: still editing", d.session() is not None)


def e_redo():
    t.redo()


def e_redone():
    h.check("redo: 45 long", d.near(plate_volume(), 16200 - HOLE), plate_volume())


def e_finish():
    d.finish_bar()


def e_finished():
    h.check("closed", d.session() is None)
    states = t.states()
    h.check("Press Pull 2 is done again", states.get("Press Pull 2", ("",))[0] == "done", states)
    h.check(
        "Press Pull 2 builds on the edited plate: 45 x 30 x 15 - hole",
        d.near(plate_volume(), 20250 - 240 * math.pi),
        plate_volume(),
    )
    h.check(
        "Press Pull 2 has no error", t.states().get("Press Pull 2", ("", "?"))[1] == "ok", states
    )


# -- F ------------------------------------------------------------------------------------------
def f_edit():
    h.check("double-click Base Feature 1 again", ui.double_click_timeline("Base Feature 1"))


def f_click_wall():
    h.check("editing again", d.session() is not None)
    h.click_empty()
    h.fit()
    a = math.radians(135)
    h.click(V(80 + 4 * math.cos(a), 15 + 4 * math.sin(a), 8))


def f_delete():
    h.press(QtCore.Qt.Key_Delete)


def f_healed():
    h.check(
        "the hole closed in the base feature: 45 x 30 x 12",
        d.near(plate_volume(), 16200),
        plate_volume(),
    )
    kinds = [o.TypeId for o in d.solid_steps(plate())]
    h.check("no Delete Face step", "PartDesign::FeaturePython" not in kinds[:1], kinds)


def f_finish():
    d.finish_bar()


def f_finished():
    h.check("45 x 30 x 15 without the hole", d.near(plate_volume(), 20250), plate_volume())
    h.check("closed", d.session() is None)


# -- G ------------------------------------------------------------------------------------------
def g_save_close_open():
    path = os.path.join(h.OUT_DIR, "direct_base_feature.FCStd")
    if os.path.exists(path):
        os.remove(path)
    App.ActiveDocument.saveAs(path)
    App.closeDocument(App.ActiveDocument.Name)
    App.openDocument(path)


def g_reopened():
    titles = t.titles()
    h.check("reopened: Base Feature 1 in the timeline", "Base Feature 1" in titles, titles)
    h.check("reopened: same plate", d.near(plate_volume(), 20250), plate_volume())
    h.fit()


def g_edit():
    h.check(
        "double-click Base Feature 1 after reopening", ui.double_click_timeline("Base Feature 1")
    )


def g_editing():
    h.check("editing after reopening", d.session() is not None)


def g_finish():
    d.finish_bar()


def g_done():
    h.check("closed", d.session() is None)
    h.check("still the same plate", d.near(plate_volume(), 20250), plate_volume())


h.run(
    "direct_base_feature",
    t.watched(
        [s.new_design("BaseFeature")]
        + s.box_steps("box", (0, 0, 40, 30), 10, V(6, -6, 0))
        + [a_create, a_open]
        + s.box_steps("plate", (60, 0, 100, 30), 10, V(6, -6, 0), new_body=True)
        + [b_plate_made]
        + ps.make_cut("hole", (80, 15), 4, 10)
        + [
            b_hole_cut,
            b_press_pull,
            b_click_top,
            b_type,
            b_ok,
            b_pulled,
            c_press_pull_other,
            c_click_box_top,
            c_type,
            c_ok,
            c_step,
            d_finish,
            d_finished,
            d_press_pull,
            d_click_top,
            d_type,
            d_ok,
            d_step,
            e_edit,
            e_editing,
            e_press_pull,
            e_click_side,
            e_type,
            e_ok,
            e_baked,
            e_undo,
            e_undone,
            e_redo,
            e_redone,
            e_finish,
            e_finished,
            f_edit,
            f_click_wall,
            f_delete,
            f_healed,
            f_finish,
            f_finished,
            g_save_close_open,
            g_reopened,
            g_edit,
            g_editing,
            g_finish,
            g_done,
        ]
    ),
)
