# SPDX-License-Identifier: LGPL-2.1-or-later
"""Dragging a slider to its limit, contact sets stopping a drag and a drive, and a component
held by nothing dragged on the view plane; only real input (docs/sciforge/parity/joints.md).

Plate = 0..40 x 0..30 x 10, Block = 50..70 x 0..10 x 20, Wall = 45..48 x 0..30 x 40 made a
component (Create Components from Bodies). J puts the block upside down on the plate's top
(10..30 x 10..20 x 10..30) as a Slider along X with limits -10 .. 10 mm.

  S1 Top view: drag the block 20 mm along +X: it stops at the limit (10 mm), one undo step.
     Ctrl+Z.
  S2 ASSEMBLE > New Contact Set: click the block and the wall, OK ("Contact Set 1" in the
     browser's Contacts folder). Limits widened to -25 .. 25 (Edit Joint Limits). Contact is
     off: a drag of 40 mm goes to the limit (25), through the wall. Ctrl+Z.
  S3 ASSEMBLE > Enable Contact Sets: the same drag stops where the block touches the wall
     (block's right face at x = 45). Ctrl+Z.
  S4 Drive Joints: 25 mm towards the wall stops at the touch (15) and says so; Cancel.
  S5 The wall component is held by nothing (no joint): dragged in the top view it moves in
     the view plane (its height stays); Ctrl+Z. ASSEMBLE > Disable Contact.
"""

from PySide import QtCore, QtWidgets

import FreeCAD as App

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import joints_steps as j
from SciForgeTests.gui import timeline_input as t

V = App.Vector
state = {}
WALL = (45, 0, 48, 30)
WALL_HEIGHT = 40


def jm():
    return j.joints_module()


def drag_module():
    from sciforge import joints_drag

    return joints_drag


def doc():
    return App.ActiveDocument


def joint():
    found = j.joint_list()
    return found[0] if found else None


def slide_now():
    jt = joint()
    return jm().value(jt)[1] if jt is not None else None


def top_view():
    h.view().viewTop()
    h.view().fitAll()
    QtWidgets.QApplication.processEvents()


def drag3d(a, bb, steps=16):
    h.drag(h.screen_point(a), h.screen_point(bb), steps=steps)
    j.wait(200)


def wall_part():
    for obj in doc().Objects:
        if obj.TypeId == "App::Part":
            return obj
    return None


def block_x():
    box = j.block().Shape.BoundBox
    return box.XMin, box.XMax


# -- the design --------------------------------------------------------------------------------
def wall_component():
    h.check("three bodies", len(s.bodies()) == 3, len(s.bodies()))
    t.row_menu(s.bodies()[2].Label, "Create Components from Bodies")


def wall_made():
    part = wall_part()
    h.check("the wall is a component", part is not None)
    state["wall_place"] = App.Placement(part.Placement) if part is not None else None


def make_motion():
    p = j.panel()
    j.click_tab(p, "Motion")
    j.choose_type(p, "Slider")


make_motion.wait_ms = 2600


def make_axis():
    p = j.panel()
    b.choose(p.axis_boxes["Slide"][0], "X Axis")


make_axis.wait_ms = 1500


def make_limits():
    p = j.panel()
    lim = p.slide_limits.rows
    s.toggle(lim["min"][0])
    s.type_value(lim["min"][1].widget, "-10")
    s.toggle(lim["max"][0])
    s.type_value(lim["max"][1].widget, "10")


def make_ok():
    j.ok()


def made():
    j.no_dialog("Joint OK")
    jt = joint()
    h.check("Slider 1 made", jt is not None and jt.Label == "Slider 1", jt and jt.Label)
    j.block_box("block on the plate", j.ON_PLATE, 1e-3)
    lim = jm().limits(jt)["slide"]
    h.check("limits -10 .. 10", lim["min"] == -10 and lim["max"] == 10, lim)


# -- S1 the limit -------------------------------------------------------------------------------
def s1_drag():
    top_view()
    state["undos"] = doc().UndoCount
    drag3d(V(24, 13, 30), V(44, 13, 30))


def s1_limited():
    x0, x1 = block_x()
    h.check("the block went 10 mm along +X and stopped (limit)", abs(x0 - 20) < 1e-3, (x0, x1))
    got = slide_now()
    h.check("the slider reads its limit", got is not None and abs(abs(got) - 10) < 1e-3, got)
    state["sign"] = 1.0 if (got or 0) > 0 else -1.0
    j.box_is(
        "it only slid (no turn, no lift)", j.block().Shape.BoundBox, [20, 10, 10, 40, 20, 30], 1e-3
    )
    h.check("one undo step", doc().UndoCount == state["undos"] + 1, doc().UndoCount)


def s1_undo():
    s.undo()


def s1_undone():
    j.block_box("Ctrl+Z: back in the middle", j.ON_PLATE, 1e-3)


# -- S2 a contact set, contact off --------------------------------------------------------------
def s2_menu():
    h.fit()
    j.menu("New Contact Set")


def s2_pick_block():
    p = j.panel()
    h.check("New Contact Set open", p is not None and p.title == "New Contact Set", p and p.title)
    h.click(V(24, 13, 30))


def s2_pick_wall():
    h.click(V(46.5, 15, 40))


def s2_ok():
    p = j.panel()
    names = [m.Name for m in getattr(p, "members", [])]
    h.check("both picked", len(names) == 2, names)
    j.ok()


def s2_made():
    j.no_dialog("Contact Set OK")
    sets = jm().contact_sets(doc())
    h.check("Contact Set 1 made", len(sets) == 1 and sets[0].Label == "Contact Set 1", sets)
    h.check(
        "the browser's Contacts folder lists it",
        "Contact Set 1" in (t.children("Contacts") or []),
        t.children("Contacts"),
    )
    h.check("contact is off by default", jm().contact_mode(doc()) == "off")


def s2_limits():
    j.browser_menu("Slider 1", "Edit Joint Limits")


def s2_widen():
    p = j.panel()
    lim = p.slide_limits.rows
    s.type_value(lim["min"][1].widget, "-25")
    s.type_value(lim["max"][1].widget, "25")


def s2_widened():
    j.ok()


def s2_drag():
    j.no_dialog("limits OK")
    lim = jm().limits(joint())["slide"]
    h.check("limits -25 .. 25", lim["min"] == -25 and lim["max"] == 25, lim)
    top_view()
    drag3d(V(24, 13, 30), V(64, 13, 30))


def s2_through():
    x0, x1 = block_x()
    h.check(
        "contact off: the block went through the wall to the limit", abs(x0 - 35) < 1e-3, (x0, x1)
    )


def s2_undo():
    s.undo()


# -- S3 contact sets on --------------------------------------------------------------------------
def s3_enable():
    j.block_box("back in the middle", j.ON_PLATE, 1e-3)
    j.menu("Enable Contact Sets")


def s3_drag():
    h.check("contact sets are on", jm().contact_mode(doc()) == "sets")
    top_view()
    drag3d(V(24, 13, 30), V(64, 13, 30))


def s3_stopped():
    x0, x1 = block_x()
    h.check("the block stopped against the wall (x = 45)", abs(x1 - 45) < 0.05, (x0, x1))
    last = drag_module().last() or {}
    h.check("the drag says what stopped it", bool(last.get("contact")), last)
    got = slide_now()
    h.check("the slider reads 15", got is not None and abs(abs(got) - 15) < 0.05, got)
    h.shot("S3-contact")


def s3_undo():
    s.undo()


# -- S4 Drive Joints stops at the touch ----------------------------------------------------------
def s4_drive():
    j.block_box("back in the middle", j.ON_PLATE, 1e-3)
    j.browser_menu("Slider 1", "Drive Joints")


def s4_type():
    p = j.panel()
    h.check("Drive Joints open", p is not None and p.title == "Drive Joints")
    s.type_value(p.slide.widget, "%g" % (25 * state.get("sign", 1.0)))


s4_type.wait_ms = 2500


def s4_stopped():
    p = j.panel()
    x0, x1 = block_x()
    h.check("the drive stopped against the wall", abs(x1 - 45) < 0.05, (x0, x1))
    h.check(
        "the box shows where it stopped", abs(abs(p.slide.value()) - 15) < 0.05, p.slide.value()
    )
    h.check("the dialog says they touch", "touch" in p.note.text(), p.note.text())


def s4_cancel():
    j.cancel()


def s4_back():
    j.no_dialog("Cancel")
    j.block_box("Cancel: back in the middle", j.ON_PLATE, 1e-3)


# -- S5 a component held by nothing --------------------------------------------------------------
def s5_drag_wall():
    part = wall_part()
    state["wall"] = App.Placement(part.Placement)
    top_view()
    a = h.screen_point(V(46.5, 25, 40))
    h.drag(a, QtCore.QPoint(a.x() + 50, a.y() + 30), steps=12)
    j.wait(200)


def s5_moved():
    part = wall_part()
    moved = part.Placement.Base - state["wall"].Base
    h.check("the wall moved in the view plane (+X, -Y)", moved.x > 1 and moved.y < -0.5, moved)
    h.check("its height did not change", abs(moved.z) < 1e-6, moved)
    h.check("it did not turn", part.Placement.Rotation.isSame(state["wall"].Rotation, 1e-9))
    last = drag_module().last() or {}
    h.check("a free drag", last.get("kind") == "free" and last.get("moved"), last)
    j.block_box("the block stayed", j.ON_PLATE, 1e-3)


def s5_undo():
    s.undo()


def s5_undone():
    h.check("Ctrl+Z: the wall is back", wall_part().Placement.isSame(state["wall"], 1e-9))


def s5_disable():
    j.menu("Disable Contact")


def s5_off():
    h.check("contact is off again", jm().contact_mode(doc()) == "off")


steps = [s.new_design("JointsSlider")] + j.two_boxes()
steps += s.box_steps("wall", WALL, WALL_HEIGHT, V(6, -6, 0), new_body=True)
steps += [wall_component, wall_made]
steps += j.pick_pair("make") + [make_motion, make_axis, make_limits, make_ok, made]
steps += [s1_drag, s1_limited, s1_undo, s1_undone]
steps += [s2_menu, s2_pick_block, s2_pick_wall, s2_ok, s2_made]
steps += [s2_limits, s2_widen, s2_widened, s2_drag, s2_through, s2_undo]
steps += [s3_enable, s3_drag, s3_stopped, s3_undo]
steps += [s4_drive, s4_type, s4_stopped, s4_cancel, s4_back]
steps += [s5_drag_wall, s5_moved, s5_undo, s5_undone, s5_disable, s5_off]

h.run("joints2_slider", steps)
