# SPDX-License-Identifier: LGPL-2.1-or-later
"""A nested component moves on its own (Fusion: a component inside another one is its own
part of the assembly), with real input (docs/sciforge/parity/joints.md).

Plate = 0..40 x 0..30 x 10, Block = 50..70 x 0..10 x 20. The plate becomes component "Base"
(New Component, From Bodies), the block component "Arm" inside Base (New Component, Parent
Base, From Bodies).

  N1 J: the block's top onto the plate's top, Revolute, OK: Arm moves (its own Placement,
     written in Base's frame); Base stays.
  N2 Top view: dragging the block turns Arm 90 degrees about the joint; Base stays.
  N3 Dragging the plate moves Base and Arm comes along inside it (Arm's own placement does
     not change); Ctrl+Z.
  N4 Drive Joints: 45 turns Arm; Ctrl+Z.
"""

from PySide import QtWidgets

import FreeCAD as App

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import component_steps as cs
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import joints_steps as j
from SciForgeTests.gui import timeline_input as t

V = App.Vector
state = {}


def jm():
    return j.joints_module()


def doc():
    return App.ActiveDocument


def joint():
    found = j.joint_list()
    return found[0] if found else None


def angle_now():
    jt = joint()
    return jm().value(jt)[0] if jt is not None else None


def base():
    return cs.component("Base")


def arm():
    return cs.component("Arm")


def global_box(body):
    shape = body.Shape.copy()
    parent = body.getParentGeoFeatureGroup()
    if parent is not None:
        shape.Placement = parent.getGlobalPlacement().multiply(shape.Placement)
    return shape.BoundBox


def top_view():
    h.view().viewTop()
    h.view().fitAll()
    QtWidgets.QApplication.processEvents()


# -- the components -----------------------------------------------------------------------------
def base_select():
    t.click_row(j.plate().Label)


def base_command():
    j.menu("New Component")


def base_name():
    p = cs.new_component_panel()
    h.check("From Bodies took the selected body", p is not None and p.from_bodies.isChecked())
    cs.type_name("Base")
    if p.activate.isChecked():
        cs.toggle(p.activate)  # the root stays the active component


def base_ok():
    h.task_button("OK")


def arm_select():
    h.check("Base made", base() is not None, [c.Label for c in cs.components()])
    t.click_row(j.block().Label)


def arm_command():
    j.menu("New Component")


def arm_name():
    p = cs.new_component_panel()
    h.check("From Bodies took the block", p is not None and p.from_bodies.isChecked())
    cs.type_name("Arm")
    b.choose(p.parent_box, "Base")
    if p.activate.isChecked():
        cs.toggle(p.activate)


def arm_ok():
    h.task_button("OK")


def nested():
    h.check("Arm made", arm() is not None, [c.Label for c in cs.components()])
    h.check("Arm sits in Base", arm().getParentGeoFeatureGroup() is base())
    h.check("the block is in Arm", j.block().getParentGeoFeatureGroup() is arm())
    h.check("Arm is a part of its own", jm().part_of(j.block()) is arm())
    h.check("Base is the plate's part", jm().part_of(j.plate()) is base())
    state["base"] = App.Placement(base().Placement)


# -- N1 the joint ---------------------------------------------------------------------------------
def n1_type():
    p = j.panel()
    h.check(
        "component 1 is Arm, component 2 Base",
        p.picks["comp1"].part is arm() and p.picks["comp2"].part is base(),
        (p.picks["comp1"].part.Label, p.picks["comp2"].part.Label),
    )
    j.click_tab(p, "Motion")
    j.choose_type(p, "Revolute")


n1_type.wait_ms = 2600


def n1_ok():
    j.ok()


def n1_done():
    j.no_dialog("Joint OK")
    jt = joint()
    h.check("Revolute 1 made", jt is not None and jt.Label == "Revolute 1")
    h.check("Base did not move", base().Placement.isSame(state["base"], 1e-9))
    j.box_is("the block landed on the plate", global_box(j.block()), j.ON_PLATE, 1e-4)
    h.check("the block's own placement is untouched", j.block().Placement.isIdentity())
    h.check("the joint is satisfied", jm().satisfied(jt))


# -- N2 drag -------------------------------------------------------------------------------------
def n2_drag():
    top_view()
    state["arm"] = App.Placement(arm().Placement)
    h.drag(h.screen_point(V(27, 15, 30)), h.screen_point(V(20, 22, 30)), steps=16)
    j.wait(200)


def n2_turned():
    a = angle_now()
    h.check("Arm turned 90 on its joint", a is not None and abs(a - 90) < 1.5, a)
    j.box_is("the block's footprint turned", global_box(j.block()), [15, 5, 10, 25, 25, 30], 0.5)
    h.check("Base stayed", base().Placement.isSame(state["base"], 1e-9))
    h.check("the joint is satisfied", jm().satisfied(joint()))


# -- N3 Base carries Arm --------------------------------------------------------------------------
def n3_drag_base():
    state["arm"] = App.Placement(arm().Placement)
    state["block_box"] = global_box(j.block())
    a = h.screen_point(V(4, 27, 10))
    h.drag(a, a.__class__(a.x() + 60, a.y()), steps=12)
    j.wait(200)


def n3_moved():
    moved = base().Placement.Base - state["base"].Base
    h.check("Base moved in the view plane", moved.x > 1 and abs(moved.z) < 1e-9, moved)
    h.check("Arm's own placement did not change", arm().Placement.isSame(state["arm"], 1e-9))
    box = global_box(j.block())
    h.check(
        "the block came along with Base",
        abs(box.XMin - state["block_box"].XMin - moved.x) < 1e-6,
        (box, state["block_box"], moved),
    )
    h.check("the angle is kept", abs(angle_now() - 90) < 1.5, angle_now())


def n3_undo():
    s.undo()


def n3_undone():
    h.check("Ctrl+Z: Base back", base().Placement.isSame(state["base"], 1e-9))


# -- N4 Drive Joints -------------------------------------------------------------------------------
def n4_drive():
    j.browser_menu("Revolute 1", "Drive Joints")


def n4_type():
    s.type_value(j.panel().angle.widget, "45")


n4_type.wait_ms = 1500


def n4_driven():
    h.check("at 45", abs(angle_now() - 45) < 1e-6, angle_now())
    h.check("Base stayed", base().Placement.isSame(state["base"], 1e-9))
    h.check("the joint is satisfied", jm().satisfied(joint()))


def n4_ok():
    j.ok()


def n4_undo():
    j.no_dialog("Drive OK")
    s.undo()


def n4_undone():
    h.check("Ctrl+Z: back near 90", abs(angle_now() - 90) < 1.5, angle_now())


steps = [s.new_design("JointsNested")] + j.two_boxes()
steps += [base_select, base_command, base_name, base_ok]
steps += [arm_select, arm_command, arm_name, arm_ok, nested]
steps += j.pick_pair("n1") + [n1_type, n1_ok, n1_done]
steps += [n2_drag, n2_turned]
steps += [n3_drag_base, n3_moved, n3_undo, n3_undone]
steps += [n4_drive, n4_type, n4_driven, n4_ok, n4_undo, n4_undone]

h.run("joints2_nested", steps)
