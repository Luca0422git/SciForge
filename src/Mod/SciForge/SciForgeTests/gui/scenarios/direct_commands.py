# SPDX-License-Identifier: LGPL-2.1-or-later
"""Every command still works without history (Fusion: they change the bodies directly), only
real input.

Part: a box 0..40 x 0..30 x 10 (Create Sketch + Extrude), then Do Not Capture Design
History (the design's menu, Remove History).

  A  Fillet (F) on the box's front right upright edge, r 3, OK: the fillet is in the box,
     which is still one frozen step (12000 - 90 (1 - pi/4)); Undo / Redo.
  B  Create Sketch + Extrude, New Body: a plate 60..100 x 0..30 x 15: a new body that is one
     frozen step (no Extrude step anywhere).
  C  MODIFY > Replace Face: the box's top onto the plate's top: the box is 15 high
     (18000 - 135 (1 - pi/4)), still one step.
  D  MODIFY > Combine, Join, the box then the plate: one body (the plate is gone: it is
     part of the box now), one step; Undo: two bodies again; Redo.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import direct_steps as d
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import timeline_input as t

V = App.Vector
SPANDREL = 9 * (1 - math.pi / 4)  # r 3
state = {}


def box():
    return d.doc().getObject(state["box"]) if state.get("box") else None


def plate():
    return d.doc().getObject(state["plate"]) if state.get("plate") else None


def frozen(body):
    return body is not None and [o.TypeId for o in d.solid_steps(body)] == [
        "PartDesign::FeatureBase"
    ]


def kinds_left():
    """SciForge / FreeCAD feature steps left in the design (none without history)."""
    wanted = ("PartDesign::Fillet", "PartDesign::Pad", "PartDesign::FeaturePython")
    return [o.Name for o in d.doc().Objects if o.TypeId in wanted]


# -- setup ----------------------------------------------------------------------------------------
def history_off():
    state["box"] = d.bodies()[0].Name
    d.design_menu("Do Not Capture Design History")


def remove_history():
    d.answer_history(remove=True)


def direct_now():
    d.wait_timeline()
    h.check("without history", d.is_direct())
    h.check("the box is one frozen step", frozen(box()))


# -- A ------------------------------------------------------------------------------------------
def a_fillet():
    Gui.Selection.clearSelection()
    h.click_empty()
    h.fit()
    h.ribbon("Fillet")


def a_click_edge():
    h.click_edge(V(40, 0, 5))


def a_radius():
    p = b.blend_panel()
    if h.check("one edge picked", p is not None and len(p.refs) == 1, p and p.refs):
        b.type_into(p.radius.widget, "3")


def a_ok():
    h.task_button("OK")


def a_baked():
    v = d.volume(box())
    h.check("the fillet is in the box", d.near(v, 12000 - 10 * SPANDREL), v)
    h.check("still one frozen step", frozen(box()), [o.Name for o in box().Group])
    h.check("no Fillet step left", not kinds_left(), kinds_left())


def a_undo():
    t.undo()


def a_undone():
    h.check("undo: no fillet", d.near(d.volume(box()), 12000), d.volume(box()))
    h.check("undo: one step", frozen(box()))


def a_redo():
    t.redo()


def a_redone():
    h.check("redo: the fillet", d.near(d.volume(box()), 12000 - 10 * SPANDREL), d.volume(box()))


# -- B (box_steps below) ------------------------------------------------------------------------
def b_plate():
    found = [x for x in d.bodies() if x is not box()]
    if not h.check("a new body", len(found) == 1, [x.Label for x in d.bodies()]):
        return
    state["plate"] = found[0].Name
    h.check("the plate: 18000", d.near(d.volume(plate()), 18000), d.volume(plate()))
    h.check("the plate is one frozen step", frozen(plate()), [o.Name for o in plate().Group])
    h.check("no Extrude step left", not kinds_left(), kinds_left())
    h.check("still no timeline", not d.timeline_shown())


# -- C ------------------------------------------------------------------------------------------
def c_start():
    h.click_empty()
    h.fit()
    d.ribbon_menu("MODIFY", "Replace Face")


def c_click_top():
    h.click(V(12, 22, 10))


def c_target_box():
    d.click_box("target")


def c_click_plate():
    h.click(V(80, 22, 15))


def c_ok():
    h.task_button("OK")


def c_baked():
    v = d.volume(box())
    h.check("the box is 15 high", d.near(v, 18000 - 15 * SPANDREL), v)
    h.check("still one frozen step", frozen(box()), [o.Name for o in box().Group])
    h.check("no Replace Face step left", not kinds_left(), kinds_left())


# -- D ------------------------------------------------------------------------------------------
def d_start():
    h.click_empty()
    h.fit()
    h.ribbon("Combine")


def d_click_target():
    h.click(V(12, 22, 15))


def d_click_tool():
    p = s.panel()
    h.check(
        "the box is the target", p is not None and p.options["target"] is box(), p and p.options
    )
    h.click(V(80, 22, 15))


def d_ok():
    h.task_button("OK")


def d_combined():
    h.check(
        "one body left",
        [x.Name for x in d.bodies()] == [state["box"]],
        [x.Label for x in d.bodies()],
    )
    v = d.volume(box())
    h.check("the box holds both", d.near(v, 36000 - 15 * SPANDREL), v)
    h.check("one frozen step", frozen(box()), [o.Name for o in box().Group])
    h.check("no Combine step left", not kinds_left(), kinds_left())


def d_undo():
    t.undo()


def d_undone():
    h.check("undo: two bodies", len(d.bodies()) == 2, [x.Label for x in d.bodies()])
    h.check("undo: the plate shows", plate() is not None and d.shown(plate()))
    h.check("undo: the box alone", d.near(d.volume(box()), 18000 - 15 * SPANDREL), d.volume(box()))


def d_redo():
    t.redo()


def d_redone():
    h.check("redo: one body", len(d.bodies()) == 1, [x.Label for x in d.bodies()])
    h.check("redo: both in it", d.near(d.volume(box()), 36000 - 15 * SPANDREL), d.volume(box()))


h.run(
    "direct_commands",
    t.watched(
        [s.new_design("DirectCommands")]
        + s.box_steps("box", (0, 0, 40, 30), 10, V(6, -6, 0))
        + [
            history_off,
            remove_history,
            direct_now,
            a_fillet,
            a_click_edge,
            a_radius,
            a_ok,
            a_baked,
            a_undo,
            a_undone,
            a_redo,
            a_redone,
        ]
        + s.box_steps("plate", (60, 0, 100, 30), 15, V(6, -6, 0), new_body=True)
        + [
            b_plate,
            c_start,
            c_click_top,
            c_target_box,
            c_click_plate,
            c_ok,
            c_baked,
            d_start,
            d_click_target,
            d_click_tool,
            d_ok,
            d_combined,
            d_undo,
            d_undone,
            d_redo,
            d_redone,
        ]
    ),
)
