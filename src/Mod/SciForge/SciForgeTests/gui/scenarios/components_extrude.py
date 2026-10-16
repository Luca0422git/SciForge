# SPDX-License-Identifier: LGPL-2.1-or-later
"""Extrude's New Component operation and timeline edits inside a component (real input).

Path A, box at the root, a second sketch beside it, E, Operation New Component, 8, OK: a
        component (Component1) with Body1 holding the new solid; the sketch stays in the
        root body (Fusion keeps the sketch where it was); the new component is active and
        the timeline shows its step and the extrude.
Path B, edit Extrude 2 from the timeline: Operation reads New Component, the distance is
        changed to 12; OK keeps the same component and body (no second one).
Path C, Undo twice takes the edit and the extrude (and its component) away; Redo twice
        brings them back.
Path D, the history marker dragged before Extrude 2 (component active) empties its body;
        dragged to the end the solid is back.
Path E, Revolve > New Component is on the same core path: the operation is offered.
Numbers: box 40 x 30 x 10 = 12000; the second rectangle 20 x 20 extruded 8 = 3200, 12 = 4800.
"""

import FreeCAD as App

from SciForgeTests.gui import arrow_input as ai
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import component_steps as cs
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import timeline_input as t

V = App.Vector
state = {}
BOX = 12000.0


def xpanel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return p if p is not None and not p._closed else None


def new_design():
    s.new_design("ComponentsExtrude")()
    state["doc"] = App.ActiveDocument.Label


# -- Path A ----------------------------------------------------------------------------------------
def a_sketch():
    h.fit()
    h.ribbon("Create Sketch")


def a_plane():
    pl.click_square("XY_Plane")  # where the square shows (was 12, -8, 0)


def a_draw():
    sk = h.in_sketch()
    h.check("sketch open", sk is not None)
    if sk is not None:
        h.draw_rectangle(sk, 60, 0, 80, 20)
        state["sketch"] = sk.Name


def a_finish():
    h.ribbon("Finish Sketch")


def a_extrude():
    h.fit()
    h.press("e")


def a_operation():
    p = xpanel()
    if h.check("extrude dialog", p is not None):
        labels = [p.operation.itemText(i) for i in range(p.operation.count())]
        h.check("Operation offers New Component", "New Component" in labels, labels)
        ui.choose(p.operation, "New Component")


def a_distance():
    h.check("distance typed", ai.give_distance("8"))


def a_preview():
    p = xpanel()
    h.check("still New Component", p is not None and p.operation.currentText() == "New Component")
    h.check("a component appears in the preview", cs.component("Component1") is not None)


def a_ok():
    h.task_button("OK")


def a_made():
    part = cs.component("Component1")
    h.check("Component1 made", part is not None, [p.Label for p in cs.components()])
    if part is None:
        return
    body = h.body()
    h.check("new body in Component1", body is not None and cs.container_label(body) == "Component1")
    h.check("named Body1", body is not None and body.Label == "Body1", body and body.Label)
    h.check("volume 3200", cs.near(cs.volume(body), 3200.0), cs.volume(body))
    state["b2"] = body.Name
    sketch = App.ActiveDocument.getObject(state["sketch"])
    h.check("the sketch stays in the root body", cs.container_label(sketch) is None)
    h.check("the box keeps its volume", cs.near(cs.volume(s.bodies()[0]), BOX))
    h.check("Component1 active", cs.active_label() == "Component1", cs.active_label())
    h.check(
        "timeline (component active): its step and extrude",
        t.titles() == ["Component1", "Extrude 2"],
        t.titles(),
    )
    h.check(
        "every step in order",
        cs.all_timeline_titles()
        == ["Sketch 1", "Extrude 1", "Sketch 2", "Component1", "Extrude 2"],
        cs.all_timeline_titles(),
    )
    h.shot("a-new-component")


# -- Path B: edit ----------------------------------------------------------------------------------
def b_edit():
    t.double_click("Extrude 2")


def b_dialog():
    p = xpanel()
    h.check("edit dialog open", p is not None)
    if p is None:
        return
    h.check("Operation reads New Component", p.operation.currentText() == "New Component")
    ui.type_into(p.distance.widget, "12")


def b_ok():
    h.task_button("OK")


def b_edited():
    body = App.ActiveDocument.getObject(state["b2"])
    h.check("volume 4800", cs.near(cs.volume(body), 4800.0), cs.volume(body))
    h.check("still one component", len(cs.components()) == 1, [p.Label for p in cs.components()])
    h.check("same body in Component1", cs.container_label(body) == "Component1")
    h.check("still 2 bodies", len(cs.bodies()) == 2, len(cs.bodies()))


# -- Path C: undo / redo ---------------------------------------------------------------------------
def c_undo():
    t.undo()


def c_undone_edit():
    body = App.ActiveDocument.getObject(state["b2"])
    h.check("Undo: 3200 again", cs.near(cs.volume(body), 3200.0), cs.volume(body))


def c_undo_2():
    t.undo()


def c_undone_extrude():
    h.check("Undo: the component is gone", cs.component("Component1") is None)
    h.check("Undo: one body", len(cs.bodies()) == 1, len(cs.bodies()))
    h.check("root active", cs.active_label() is None, cs.active_label())


def c_redo():
    t.redo()


def c_redo_2():
    t.redo()


def c_redone():
    body = App.ActiveDocument.getObject(state["b2"])
    h.check(
        "Redo: component and body back", cs.component("Component1") is not None and body is not None
    )
    h.check("Redo: 4800", cs.near(cs.volume(body), 4800.0), cs.volume(body))


# -- Path D: rollback inside the component ---------------------------------------------------------
def d_activate():
    cs.click_radio("Component1")


def d_active():
    h.check("Component1 active", cs.active_label() == "Component1", cs.active_label())
    h.check("timeline filtered", t.titles() == ["Component1", "Extrude 2"], t.titles())


def d_roll_back():
    t.drag_marker("Extrude 2")


def d_rolled():
    body = App.ActiveDocument.getObject(state["b2"])
    h.check("Extrude 2 rolled back", t.item("Extrude 2").state == "rolled_back", t.states())
    h.check("its body is empty", cs.volume(body) == 0.0, cs.volume(body))
    h.check("the box is untouched", cs.near(cs.volume(s.bodies()[0]), BOX))


def d_roll_end():
    t.drag_marker(to_end=True)


def d_end():
    body = App.ActiveDocument.getObject(state["b2"])
    h.check("solid back", cs.near(cs.volume(body), 4800.0), cs.volume(body))
    h.shot("d-rolled-back-forth")


# -- Path E: Revolve offers it too -----------------------------------------------------------------
def e_revolve():
    h.click_empty()
    h.fit()
    s.menu("CREATE", "Revolve")


def e_offered():
    from sciforge import revolve_ui

    p = revolve_ui.RevolvePanel.last if hasattr(revolve_ui, "RevolvePanel") else None
    p = p if p is not None and not getattr(p, "_closed", True) else None
    if h.check("Revolve dialog open", p is not None):
        labels = [p.operation.itemText(i) for i in range(p.operation.count())]
        h.check("Revolve offers New Component", "New Component" in labels, labels)


def e_cancel():
    h.task_button("Cancel")


def e_unchanged():
    h.check("nothing changed", len(cs.components()) == 1 and len(cs.bodies()) == 2)


h.run(
    "components_extrude",
    t.watched(
        [new_design]
        + s.box_steps("box", (0, 0, 40, 30), 10, V(6, -6, 0))
        + [
            a_sketch,
            a_plane,
            a_draw,
            a_finish,
            a_extrude,
            a_operation,
            a_distance,
            a_preview,
            a_ok,
            a_made,
            b_edit,
            b_dialog,
            b_ok,
            b_edited,
            c_undo,
            c_undone_edit,
            c_undo_2,
            c_undone_extrude,
            c_redo,
            c_redo_2,
            c_redone,
            d_activate,
            d_active,
            d_roll_back,
            d_rolled,
            d_roll_end,
            d_end,
            e_revolve,
            e_offered,
            e_cancel,
            e_unchanged,
        ]
    ),
)
