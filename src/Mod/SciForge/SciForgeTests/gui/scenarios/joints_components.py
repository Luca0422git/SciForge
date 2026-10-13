# SPDX-License-Identifier: LGPL-2.1-or-later
"""Joints on components (an App::Part holding a body, the components work's model, see
docs/sciforge/parity/components.md), with real clicks in the 3D view.

The Components commands live on another branch: this scenario makes the component the way
they do (components.from_bodies: a tagged App::Part at the root with the body inside) and
deletes it the way components.remove does (bodies, then the part, one undo step). Everything
about the joint itself is real input.

  K1 The block becomes component "Component1". J, click the block's top (the click lands in
     the component), click the plate's top: the component moves (its own Placement), the
     body inside keeps its placement; Revolute; OK.
  K2 Drive Joints from the browser: 90 turns the component.
  K3 The body goes back to the root (out of its component): the joint now moves the body
     (it does not keep its place: the components work moves bodies without compensating the
     component's placement); Ctrl+Z puts it back in the component.
  K4 Deleting the component deletes its joint, one undo step; Ctrl+Z brings both back.
"""

import FreeCAD as App

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import joints_steps as j
from SciForgeTests.gui import timeline_input as t

V = App.Vector
state = {}


def jm():
    return j.joints_module()


def doc():
    return App.ActiveDocument


def comp():
    return doc().getObject(state.get("comp", "")) if state.get("comp") else None


def joint():
    found = j.joint_list()
    return found[0] if found else None


def global_box(name, expect):
    """The block's box in the design (its body's shape is in the component's frame)."""
    shape = j.block().Shape.copy()
    parent = j.block().getParentGeoFeatureGroup()
    if parent is not None:
        shape.Placement = parent.getGlobalPlacement().multiply(shape.Placement)
    return j.box_is(name, shape.BoundBox, expect, 1e-4)


def k1_wrap():
    d = doc()
    d.openTransaction("Create Components from Bodies")
    part = d.addObject("App::Part", "Component")
    part.Label = "Component1"
    part.addProperty("App::PropertyString", "SciForgeType", "SciForge", "SciForge object kind", 0)
    part.SciForgeType = "Component"
    part.addObject(j.block())
    d.commitTransaction()
    d.recompute()
    state["comp"] = part.Name
    h.fit()


def k1_wrapped():
    h.check("the block is in the component", j.block().getParentGeoFeatureGroup() is comp())
    h.check(
        "the component is a part joints move", jm().is_part(comp()) and not jm().is_part(j.block())
    )


def k1_joined():
    p = j.panel()
    jt = joint()
    h.check("one joint", jt is not None)
    if jt is None:
        return
    h.check(
        "component 1 is the component",
        jm().part1(jt) is comp(),
        jm().part1(jt) and jm().part1(jt).Label,
    )
    h.check(
        "its reference goes through the body",
        jt.Reference1[1][0] == "%s.Face6" % j.block().Name,
        jt.Reference1[1],
    )
    h.check("the component moved", not comp().Placement.isIdentity(), comp().Placement)
    h.check(
        "the body inside kept its placement", j.block().Placement.isIdentity(), j.block().Placement
    )
    global_box("the block (in its component) sits on the plate", j.ON_PLATE)
    h.check("dialog open", p is not None)


def k1_type():
    p = j.panel()
    j.click_tab(p, "Motion")
    j.choose_type(p, "Revolute")


k1_type.wait_ms = 2600


def k1_ok():
    j.ok()


def k1_done():
    j.no_dialog("Joint OK")
    h.check("Revolute 1", joint() is not None and joint().Label == "Revolute 1")
    global_box("still on the plate", j.ON_PLATE)


def k2_drive():
    j.browser_menu("Revolute 1", "Drive Joints")


def k2_type():
    p = j.panel()
    h.check("Drive Joints open", p is not None and p.title == "Drive Joints")
    if p is not None:
        s.type_value(p.angle.widget, "90")


def k2_turned():
    a, _s = jm().value(joint())
    h.check("the joint is at 90", abs(a - 90) < 1e-4, a)
    global_box("the component turned a quarter", [15, 5, 10, 25, 25, 30])
    h.check("the body inside still has its own placement", j.block().Placement.isIdentity())


def k2_ok():
    j.ok()


def k3_out():
    d = doc()
    state["undos"] = d.UndoCount
    d.openTransaction("Move to the root")
    comp().removeObject(j.block())
    d.commitTransaction()
    d.recompute()


def k3_rerooted():
    jt = joint()
    h.check(
        "the joint now moves the body",
        jm().part1(jt) is j.block(),
        jm().part1(jt) and jm().part1(jt).Label,
    )
    h.check("...through its face", list(jt.Reference1[1]) == ["Face6", "Face6"], jt.Reference1[1])


def k3_undo():
    s.undo()


def k3_back():
    jt = joint()
    h.check("undo: in the component again", j.block().getParentGeoFeatureGroup() is comp())
    h.check("undo: the joint moves the component again", jm().part1(jt) is comp())
    a, _s = jm().value(jt)
    h.check("still at 90", abs(a - 90) < 1e-4, a)


def k4_delete():
    d = doc()
    state["undos"] = d.UndoCount
    d.openTransaction("Delete Component1")
    body = j.block()
    for obj in reversed(list(body.Group)):
        if d.getObject(obj.Name) is not None:
            body.removeObject(obj)
            d.removeObject(obj.Name)
    d.removeObject(body.Name)
    d.removeObject(state["comp"])
    d.commitTransaction()
    d.recompute()


def k4_deleted():
    h.check("the component is gone", doc().getObject(state["comp"]) is None)
    h.check("its joint went with it", joint() is None, [x.Label for x in j.joint_list()])
    h.check("the timeline has no joint", "Revolute 1" not in t.titles(), t.titles())
    h.check(
        "one undo step", doc().UndoCount == state["undos"] + 1, (state["undos"], doc().UndoCount)
    )


def k4_undo():
    s.undo()


def k4_back():
    h.check("undo: the component is back", comp() is not None)
    h.check("undo: its joint is back", joint() is not None and jm().part1(joint()) is comp())
    h.check("the solver is happy", jm().solve(doc()) == 0)


steps = [s.new_design("JointComponents")] + j.two_boxes()
steps += [k1_wrap, k1_wrapped] + j.pick_pair("k1") + [k1_joined, k1_type, k1_ok, k1_done]
steps += [k2_drive, k2_type, k2_turned, k2_ok]
steps += [k3_out, k3_rerooted, k3_undo, k3_back]
steps += [k4_delete, k4_deleted, k4_undo, k4_back]

h.run("joints_components", steps)
