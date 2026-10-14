# SPDX-License-Identifier: LGPL-2.1-or-later
"""Direct modeling with a body inside a component that is turned and moved, only real input.

Bodies made with Create Sketch + Extrude: a box 0..40 x 0..30 x 10 and a plate 60..100 x
0..30 x 10 (New Body). Create Components from Bodies on the box; then MODIFY > Align with
Objects: Components puts the box's top face onto the plate's top: the component is turned
upside down and sits on the plate (x 60..100, y 0..30, z 10..20 in the design).

  A  Do Not Capture Design History: the box keeps its place; its base shape lives in its
     component (FreeCAD refuses links out of a component); the Report view stays clean.
  B  Q on the box's top (z 20 in the design), 5, OK: baked into the body, the top goes up
     in the design (z 10..25); Undo / Redo.
  C  The box's top face, Del: refused with the reason (its neighbours cannot close the gap);
     nothing changes.
  D  Capture Design History: the timeline comes back with the bodies' Base Features; double
     -click the box's: rolled back to it; Q on its top, 2, OK: baked into the base feature
     (z 10..27), no new step; Finish Base Feature.
  E  Save, close, open: the box is where it was, nothing in error; its base shape is still
     in its component.
"""

import os

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import direct_steps as d
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import timeline_input as t

V = App.Vector
state = {}


def box():
    return d.doc().getObject(state["box"]) if state.get("box") else None


def where():
    from sciforge import bodies

    return bodies.global_shape(box().Tip).BoundBox


def at(bb, *want):
    got = (bb.XMin, bb.YMin, bb.ZMin, bb.XMax, bb.YMax, bb.ZMax)
    return all(abs(w - g) < 1e-6 for w, g in zip(want, got))


def part():
    from sciforge import components

    return components.component_of(box())


def holder_home():
    from sciforge import direct

    holder = direct._base_shape(box())
    if holder is None:
        return None, None
    return holder, holder.getParentGeoFeatureGroup()


def errors():
    return {k: v for k, v in t.states().items() if v[1] not in ("ok", "")}


# -- setup: the component, turned onto the plate ----------------------------------------------
def names():
    found = d.bodies()
    h.check("two bodies", len(found) == 2, [b.Label for b in found])
    state["box"], state["plate"] = found[0].Name, found[1].Name


def to_component():
    h.click_empty()
    t.row_menu(box().Label, "Create Components from Bodies")


def align_start():
    h.check("the box is in a component", part() is not None)
    h.click_empty()
    h.fit()
    d.ribbon_menu("MODIFY", "Align")


def align_components():
    d.choose("objects", "Components")


def align_from():
    h.click(V(30, 22, 10))


def align_to():
    h.click(V(90, 22, 10))


def align_ok():
    h.task_button("OK")


def aligned():
    bb = where()
    h.check("the box sits upside down on the plate", at(bb, 60, 0, 10, 100, 30, 20), bb)
    rot = part().Placement.Rotation
    h.check("its component is turned", abs(rot.Angle - 3.141592653589793) < 1e-6, part().Placement)
    h.fit()


# -- A ------------------------------------------------------------------------------------------
def a_history_off():
    d.design_menu("Do Not Capture Design History")


def a_remove():
    d.answer_history(remove=True)


def a_direct():
    d.wait_timeline()
    h.check("without history", d.is_direct())
    bb = where()
    h.check("the box keeps its place", at(bb, 60, 0, 10, 100, 30, 20), bb)
    holder, home = holder_home()
    h.check("the box has a base shape", holder is not None)
    h.check("its base shape lives in the component", home is part(), home and home.Label)
    h.check(
        "one frozen step",
        [o.TypeId for o in d.solid_steps(box())] == ["PartDesign::FeatureBase"],
        [o.TypeId for o in d.solid_steps(box())],
    )


# -- B ------------------------------------------------------------------------------------------
def b_press_pull():
    h.click_empty()
    h.press("q")


def b_click_top():
    h.click(V(66, 4, 20))


def b_type():
    p = d.press_pull_panel()
    h.check("the box's top picked", p is not None and len(p.names) == 1, p and p.names)
    d.type_distance("5")


def b_ok():
    h.task_button("OK")


def b_baked():
    bb = where()
    h.check("the top went up in the design (z 10..25)", at(bb, 60, 0, 10, 100, 30, 25), bb)
    h.check(
        "still one frozen step",
        len(d.solid_steps(box())) == 1,
        [o.Name for o in d.solid_steps(box())],
    )
    h.fit()


def b_undo():
    t.undo()


def b_undone():
    h.check("undo: z 10..20", at(where(), 60, 0, 10, 100, 30, 20), where())


def b_redo():
    t.redo()


def b_redone():
    h.check("redo: z 10..25", at(where(), 60, 0, 10, 100, 30, 25), where())


# -- C ------------------------------------------------------------------------------------------
def c_click_top():
    h.click_empty()
    h.click(V(66, 4, 25))


def c_delete():
    h.press(QtCore.Qt.Key_Delete)


def c_refused():
    h.check("refused: nothing changed", at(where(), 60, 0, 10, 100, 30, 25), where())
    msg = d.told()
    h.check("the reason is said", "cannot be deleted" in msg, msg)


# -- D ------------------------------------------------------------------------------------------
def d_history_on():
    d.design_menu("Capture Design History")


def d_captured():
    d.wait_timeline()
    h.check("history captured", not d.is_direct())
    titles = t.titles()
    h.check("Base Features in the timeline", "Base Feature 1" in titles, titles)
    base = box().Group[0]
    state["base_title"] = None
    for title in titles:
        if t.obj(title) is base:
            state["base_title"] = title
    h.check("the box's base feature is listed", state["base_title"] is not None, titles)
    h.fit()


def d_edit():
    title = state.get("base_title") or "Base Feature 1"
    h.check("double-click the box's base feature", ui.double_click_timeline(title), t.titles())


def d_press_pull():
    h.check("editing the base feature", d.session() is not None)
    h.click_empty()
    h.fit()
    h.press("q")


def d_click_top():
    h.click(V(66, 4, 25))


def d_type():
    d.type_distance("2")


def d_ok():
    h.task_button("OK")


def d_baked():
    bb = where()
    h.check("z 10..27", at(bb, 60, 0, 10, 100, 30, 27), bb)
    h.check("no Press Pull step", "Press Pull 1" not in t.titles(), t.titles())
    h.check(
        "still one solid step",
        len(d.solid_steps(box())) == 1,
        [o.Name for o in d.solid_steps(box())],
    )


def d_finish():
    d.finish_bar()


def d_finished():
    h.check("closed", d.session() is None)
    h.check("still z 10..27", at(where(), 60, 0, 10, 100, 30, 27), where())
    h.check("nothing in error", not errors(), errors())


# -- E ------------------------------------------------------------------------------------------
def e_save_close_open():
    path = os.path.join(h.OUT_DIR, "direct_components.FCStd")
    if os.path.exists(path):
        os.remove(path)
    App.ActiveDocument.saveAs(path)
    App.closeDocument(App.ActiveDocument.Name)
    App.openDocument(path)


def e_reopened():
    d.doc().recompute()
    h.check("reopened: the box where it was", at(where(), 60, 0, 10, 100, 30, 27), where())
    holder, home = holder_home()
    h.check(
        "reopened: its base shape in the component",
        holder is not None and home is part(),
        home and home.Label,
    )
    h.check("reopened: nothing in error", not errors(), errors())


h.run(
    "direct_components",
    t.watched(
        [s.new_design("DirectComponents")]
        + s.box_steps("box", (0, 0, 40, 30), 10, V(12, -8, 0))
        + s.box_steps("plate", (60, 0, 100, 30), 10, V(12, -8, 0), new_body=True)
        + [
            names,
            to_component,
            align_start,
            align_components,
            align_from,
            align_to,
            align_ok,
            aligned,
            a_history_off,
            a_remove,
            a_direct,
            b_press_pull,
            b_click_top,
            b_type,
            b_ok,
            b_baked,
            b_undo,
            b_undone,
            b_redo,
            b_redone,
            c_click_top,
            c_delete,
            c_refused,
            d_history_on,
            d_captured,
            d_edit,
            d_press_pull,
            d_click_top,
            d_type,
            d_ok,
            d_baked,
            d_finish,
            d_finished,
            e_save_close_open,
            e_reopened,
        ]
    ),
)
