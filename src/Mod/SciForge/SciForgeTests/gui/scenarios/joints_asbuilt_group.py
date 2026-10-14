# SPDX-License-Identifier: LGPL-2.1-or-later
"""Ground, Joint Origin, As-Built Joint, Rigid Group, joint limits and a joint the solver cannot
satisfy, only real input (docs/sciforge/parity/joints.md).

Plate = 0..40 x 0..30 x 10, Block = 50..70 x 0..10 x 20, Pin = 0..10 x 40..50 x 10 (three
bodies, Extrude New Body).

  A  Ground: right-click the plate's row > Ground: it is grounded (the row's menu now says
     Unground). Ctrl+Z ungrounds, Ctrl+Y grounds again; Unground frees it.
  B  Joint Origin: ASSEMBLE > Joint Origin, hover the pin's top (its snap points light up),
     click near a corner, Offset Z 5, OK: "Joint Origin 1" in the timeline and in the
     browser's Joint Origins folder, 5 above the corner. J, click that row in the browser
     (component 1 = the pin, at its joint origin), click near the plate's top corner: the pin
     comes so that its joint origin sits on that corner. OK, then Ctrl+Z.
  C  As-Built Joint: ASSEMBLE > As-built Joint, click the block and the plate (nothing moves),
     Type Revolute (the Position box waits), click the block's top centre: the axis stands
     there, still nothing moved. OK. Right-click the joint > Animate Joint: the block turns
     about that axis until Esc, then stands where it was. Right-click > Edit Joint Limits:
     Maximum 45, OK.
  D  Rigid Group: ASSEMBLE > Rigid Group, click the block and the pin, OK: "Rigid Group 1".
     Right-click the as-built joint > Drive Joints, Rotation 90: it stops at 45 (the limit) and
     the pin turns with the block; Cancel puts both back. Suppress the group from the
     timeline: its hidden links are off; Unsuppress: on again.
  E  A joint the solver cannot satisfy: J, the pin's joint origin (browser), the plate's
     corner: the dialog says the joints fight each other and OK is refused; Cancel puts
     everything back.
  F  Delete the pin (its row's menu): its rigid group (one member left) and its joint origin go
     with it, in one undo step; Ctrl+Z brings all of it back.
"""

from PySide import QtCore

import FreeCAD as App

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import joints_steps as j
from SciForgeTests.gui import timeline_input as t

V = App.Vector
state = {}
PIN = (0, 40, 10, 50)
PIN_HOME = [0, 40, 0, 10, 50, 10]


def jm():
    return j.joints_module()


def pin():
    return s.bodies()[2]


def doc():
    return App.ActiveDocument


def same_plc(a, c, tol=1e-6):
    return a.isSame(c, tol)


# -- A ground ----------------------------------------------------------------------------------
def a_ground():
    j.browser_menu(j.plate().Label, "Ground")


def a_grounded():
    h.check("plate grounded", jm().is_grounded(j.plate()))
    entries = [e[0] for e in t.row_menu_entries(j.plate().Label)]
    h.check(
        "its menu now offers Unground", "Unground" in entries and "Ground" not in entries, entries
    )
    h.check("the block is not", not jm().is_grounded(j.block()))


def a_undo():
    s.undo()


def a_undone():
    h.check("undo ungrounded the plate", not jm().is_grounded(j.plate()))


def a_redo():
    s.redo()


def a_redone():
    h.check("redo grounded it again", jm().is_grounded(j.plate()))


def a_unground():
    j.browser_menu(j.plate().Label, "Unground")


def a_free():
    h.check("Unground freed the plate", not jm().is_grounded(j.plate()))


# -- B joint origin ------------------------------------------------------------------------------
def b_command():
    # Looking straight down: in the isometric view the pin's top is squeezed along one
    # diagonal, so a point near its corner is either within a pick radius of an edge (CI
    # picked the edge: its midpoint and ends only) or nearer a midpoint on the screen.
    h.view().viewTop()
    h.fit(iso=False)
    j.menu("Joint Origin")


def b_hover():
    p = j.panel()
    h.check("Joint Origin dialog open", p is not None and p.title == "Joint Origin", p and p.title)
    j.hover(V(1.5, 41.5, 10))  # well inside the top, the corner the nearest snap point


def b_snaps():
    p = j.panel()
    h.check(
        "the pin's top lights up its snap points",
        j.snap_kinds(p) == ["centre", "midpoint", "vertex"],
        j.snap_kinds(p),
    )
    h.check("the corner is the nearest", j.hot_kind(p) == "vertex", j.hot_kind(p))


def b_click():
    h.click(V(1.5, 41.5, 10))


def b_offset():
    p = j.panel()
    h.check("snap taken", p.pick is not None and p.snap["kind"] == "vertex", p.snap)
    s.type_value(p.offset_fields["z"].widget, "5")


def b_placed():
    origins = jm().joint_origins(doc())
    h.check("one joint origin", len(origins) == 1, origins)
    if origins:
        g = origins[0].getGlobalPlacement()
        h.check("5 above the pin's corner", (g.Base - V(0, 40, 15)).Length < 1e-6, g)


def b_ok():
    j.ok()


def b_done():
    j.no_dialog("Joint Origin OK")
    h.check("timeline shows Joint Origin 1", "Joint Origin 1" in t.titles(), t.titles())
    h.check(
        "browser's Joint Origins folder lists it",
        (t.children("Joint Origins") or []) == ["Joint Origin 1"],
        t.children("Joint Origins"),
    )
    h.fit()  # back to the isometric view the next steps click in


def b_press_j():
    j.press_j()


def b_pick_origin_row():
    t.click_row("Joint Origin 1")


def b_origin_taken():
    p = j.panel()
    pick = p.picks["comp1"] if p is not None else None
    h.check(
        "component 1 = the pin, at its joint origin",
        pick is not None and pick.part is pin() and pick.is_datum(),
        pick,
    )
    h.check(
        "the snap is the joint origin itself",
        p is not None and p.snaps["comp1"] and p.snaps["comp1"]["kind"] == "origin",
        p and p.snaps["comp1"],
    )
    h.check("component 2 waits", p is not None and p.active == "comp2", p and p.active)


def b_pick_corner():
    h.click(V(39, 29, 10))


b_pick_corner.wait_ms = 900


def b_joined():
    joints = j.joint_list()
    h.check("one joint", len(joints) == 1, joints)
    origin = jm().joint_origins(doc())[0]
    g = origin.getGlobalPlacement()
    h.check(
        "the pin's joint origin sits on the plate's corner",
        (g.Base - V(40, 30, 10)).Length < 1e-5,
        g,
    )
    h.check("the block did not move", j.block().Shape.BoundBox.XMin == 50, j.block().Shape.BoundBox)


def b_ok2():
    j.ok()


def b_done2():
    j.no_dialog("Joint OK")
    h.check("Rigid 1 in the timeline", "Rigid 1" in t.titles(), t.titles())


def b_undo():
    s.undo()


def b_undone():
    h.check("undo removed the joint", not j.joint_list())
    j.box_is("the pin is back", pin().Shape.BoundBox, PIN_HOME, 1e-4)
    h.check("the joint origin stays", len(jm().joint_origins(doc())) == 1)


# -- C as-built joint -------------------------------------------------------------------------------
def c_command():
    h.fit()
    j.menu("As-built Joint")


def c_pick_block():
    p = j.panel()
    h.check(
        "As-Built Joint dialog open", p is not None and p.title == "As-Built Joint", p and p.title
    )
    h.click(V(60, 0, 10))  # the block's front face


def c_pick_plate():
    h.click(V(5, 5, 10))  # the plate's top


def c_two():
    p = j.panel()
    h.check(
        "both components taken", p is not None and p.parts == [j.block(), j.plate()], p and p.parts
    )
    j.block_box("nothing moved (block)", j.HOME)
    j.box_is("nothing moved (plate)", j.plate().Shape.BoundBox, [0, 0, 0, 40, 30, 10], 1e-4)


def c_revolute():
    p = j.panel()
    j.choose_type(p, "Revolute")


def c_waits():
    p = j.panel()
    h.check("the Position box waits", p.active == "position", p.active)
    h.check("...and says so", "position" in p.info.text().lower(), p.info.text())


def c_pick_position():
    h.click(V(58, 6, 20))  # the block's top, near its centre


def c_axis():
    joints = j.joint_list()
    h.check(
        "one as-built joint",
        len(joints) == 1 and getattr(joints[0], "SciForgeType", "") == "AsBuiltJoint",
        joints,
    )
    if not joints:
        return
    j1, j2 = j.frames(joints[0])
    h.check(
        "its axis stands at the block's top centre",
        (j1.Base - V(60, 5, 20)).Length < 1e-6 and (j2.Base - V(60, 5, 20)).Length < 1e-6,
        (j1.Base, j2.Base),
    )
    h.check(
        "its axis is upright", j.tilt(j.z_of(j2), j.Z) < 1e-6 and j.tilt(j.z_of(j1), j.Z) < 1e-6
    )
    j.block_box("still nothing moved", j.HOME)
    h.check("FreeCAD Revolute", joints[0].JointType == "Revolute", joints[0].JointType)


def c_ok():
    j.ok()


def c_done():
    j.no_dialog("As-Built OK")
    h.check("Revolute 1 in the timeline", "Revolute 1" in t.titles(), t.titles())
    h.check(
        "and in the Joints folder",
        "Revolute 1" in (t.children("Joints") or []),
        t.children("Joints"),
    )
    h.check("nothing was grounded for it (none is needed)", not jm().is_grounded(j.plate()))
    j.block_box("block where it was built", j.HOME)


def c_animate():
    j.browser_menu("Revolute 1", "Animate Joint")
    joint = j.joint_list()[0]
    state["c_samples"] = j.sample(joint, j.block(), 2.0)


def c_watched():
    samples = state.get("c_samples") or []
    h.check("watched the animation", len(samples) >= 5, len(samples))
    bad = [i for i, r in enumerate(samples) if (r["j1"].Base - V(60, 5, 20)).Length > 1e-5]
    h.check("it turns about the axis at the block's top centre", not bad, bad[:5])
    h.check(
        "it turns",
        j.spread(r["angle"] for r in samples) > 60,
        j.spread(r["angle"] for r in samples),
    )


def c_escape():
    b.press_guarded(QtCore.Qt.Key_Escape)


def c_stopped():
    from sciforge import joints_ui

    h.check("Esc stopped the animation", joints_ui._STANDALONE["animator"] is None)
    j.block_box("the block stands where it was", j.HOME)


def c_limits():
    j.browser_menu("Revolute 1", "Edit Joint Limits")


def c_limit_max():
    p = j.panel()
    h.check(
        "the as-built joint's dialog opened",
        p is not None and p.title == "As-Built Joint" and p.editing,
        p and p.title,
    )
    if p is None:
        return
    s.toggle(p.angle_limits.rows["max"][0])
    s.type_value(p.angle_limits.rows["max"][1].widget, "45")


def c_limit_ok():
    j.ok()


def c_limited():
    j.no_dialog("Edit Joint Limits OK")
    joint = j.joint_list()[0]
    lim = jm().limits(joint)["angle"]
    h.check("maximum 45 stored", lim["max"] == 45 and lim["min"] is None, lim)
    h.check("still one joint", len(j.joint_list()) == 1)
    j.block_box("nothing moved", j.HOME)


# -- D rigid group ---------------------------------------------------------------------------------
def d_command():
    h.fit()
    j.menu("Rigid Group")


def d_pick_block():
    p = j.panel()
    h.check("Rigid Group dialog open", p is not None and p.title == "Rigid Group", p and p.title)
    h.click(V(60, 0, 10))


def d_pick_pin():
    h.click(V(5, 45, 10))


def d_members():
    p = j.panel()
    h.check(
        "block and pin taken", p is not None and p.members == [j.block(), pin()], p and p.members
    )


def d_ok():
    j.ok()


def d_done():
    j.no_dialog("Rigid Group OK")
    groups = jm().rigid_groups(doc())
    h.check("one rigid group", len(groups) == 1, groups)
    h.check("Rigid Group 1 in the timeline", "Rigid Group 1" in t.titles(), t.titles())
    h.check(
        "and in the Joints folder",
        "Rigid Group 1" in (t.children("Joints") or []),
        t.children("Joints"),
    )
    if groups:
        h.check("one hidden link", len(jm().helpers_of(groups[0])) == 1)
    state["pin_plc"] = App.Placement(pin().Placement)


def d_drive():
    j.browser_menu("Revolute 1", "Drive Joints")


def d_type_90():
    p = j.panel()
    h.check(
        "Drive Joints open on the joint",
        p is not None and p.title == "Drive Joints" and p.joint is not None,
        p and p.title,
    )
    if p is None:
        return
    h.check(
        "a Rotation box, no Distance box",
        p.angle.widget.isVisible() and not p.slide.widget.isVisible(),
    )
    s.type_value(p.angle.widget, "90")


def d_driven():
    p = j.panel()
    joint = j.joint_list()[0]
    angle, _ = jm().value(joint)
    h.check("stopped at the 45 limit", abs(angle - 45) < 1e-4, angle)
    h.check("the box shows 45", abs(p.angle.value() - 45) < 1e-6, p.angle.value())
    turn = App.Placement(V(0, 0, 0), App.Rotation(V(0, 0, 1), 45), V(60, 5, 0))
    expect = turn.multiply(state["pin_plc"])
    h.check(
        "the pin turned with the block (rigid group)",
        same_plc(pin().Placement, expect, 1e-5),
        (pin().Placement, expect),
    )


def d_cancel():
    j.cancel()


def d_cancelled():
    j.no_dialog("Drive Cancel")
    j.block_box("Cancel put the block back", j.HOME)
    h.check("and the pin", same_plc(pin().Placement, state["pin_plc"]), pin().Placement)


def d_suppress():
    j.timeline_menu("Rigid Group 1", "Suppress Features")


def d_suppressed():
    group = jm().rigid_groups(doc())[0]
    h.check("group suppressed", bool(group.Suppressed))
    h.check("its links are off", all(x.Suppressed for x in jm().helpers_of(group)))


def d_unsuppress():
    j.timeline_menu("Rigid Group 1", "Unsuppress Features")


def d_unsuppressed():
    group = jm().rigid_groups(doc())[0]
    h.check("group on again", not group.Suppressed)
    h.check("its links are on", not any(x.Suppressed for x in jm().helpers_of(group)))
    h.check("the solver is happy", jm().solve(doc()) == 0)


# -- E the solver cannot ------------------------------------------------------------------------------
def e_press_j():
    j.press_j()


def e_pick_origin():
    t.click_row("Joint Origin 1")


def e_pick_corner():
    h.click(V(39, 29, 10))


e_pick_corner.wait_ms = 900


def e_refused():
    p = j.panel()
    h.check(
        "the dialog says the joints fight",
        p is not None and "cannot all be satisfied" in p.message.text(),
        p and p.message.text(),
    )


def e_ok():
    j.ok()


def e_still_open():
    p = j.panel()
    h.check("OK is refused while they fight", p is not None and not p._closed, p)


def e_cancel():
    j.cancel()


def e_back():
    j.no_dialog("Cancel")
    h.check(
        "no new joint",
        [x.Label for x in j.joint_list()] == ["Revolute 1"],
        [x.Label for x in j.joint_list()],
    )
    j.block_box("the block is back", j.HOME)
    h.check("the pin is back", same_plc(pin().Placement, state["pin_plc"]), pin().Placement)
    h.check("the solver is happy again", jm().solve(doc()) == 0)


# -- F delete the pin -------------------------------------------------------------------------------
def f_delete():
    state["undo_count"] = doc().UndoCount
    j.browser_menu(pin().Label, "Delete")


def f_deleted():
    h.check("the pin is gone", len(s.bodies()) == 2, len(s.bodies()))
    h.check("its rigid group went with it", not jm().rigid_groups(doc()))
    helpers = [o.Name for o in doc().Objects if jm().is_helper(o)]
    h.check("and the group's link", not helpers, helpers)
    h.check("its joint origin too", not jm().joint_origins(doc()))
    h.check("the as-built joint stays", [x.Label for x in j.joint_list()] == ["Revolute 1"])
    h.check(
        "one undo step",
        doc().UndoCount == state["undo_count"] + 1,
        (state["undo_count"], doc().UndoCount),
    )


def f_undo():
    s.undo()


def f_back():
    h.check("undo: the pin is back", len(s.bodies()) == 3)
    groups = jm().rigid_groups(doc())
    h.check(
        "its rigid group is back with both members",
        len(groups) == 1 and len(groups[0].Members) == 2,
        groups,
    )
    h.check("its joint origin is back", len(jm().joint_origins(doc())) == 1)
    h.check("the solver is happy", jm().solve(doc()) == 0)


steps = [s.new_design("JointGroups")] + j.two_boxes()
steps += s.box_steps("pin", PIN, 10, V(12, -8, 0), new_body=True)
steps += [a_ground, a_grounded, a_undo, a_undone, a_redo, a_redone, a_unground, a_free]
steps += [b_command, b_hover, b_snaps, b_click, b_offset, b_placed, b_ok, b_done]
steps += [
    b_press_j,
    b_pick_origin_row,
    b_origin_taken,
    b_pick_corner,
    b_joined,
    b_ok2,
    b_done2,
    b_undo,
    b_undone,
]
steps += [
    c_command,
    c_pick_block,
    c_pick_plate,
    c_two,
    c_revolute,
    c_waits,
    c_pick_position,
    c_axis,
    c_ok,
    c_done,
]
steps += [c_animate, c_watched, c_escape, c_stopped, c_limits, c_limit_max, c_limit_ok, c_limited]
steps += [
    d_command,
    d_pick_block,
    d_pick_pin,
    d_members,
    d_ok,
    d_done,
    d_drive,
    d_type_90,
    d_driven,
    d_cancel,
    d_cancelled,
]
steps += [d_suppress, d_suppressed, d_unsuppress, d_unsuppressed]
steps += [e_press_j, e_pick_origin, e_pick_corner, e_refused, e_ok, e_still_open, e_cancel, e_back]
steps += [f_delete, f_deleted, f_undo, f_back]

h.run("joints_asbuilt_group", steps)
