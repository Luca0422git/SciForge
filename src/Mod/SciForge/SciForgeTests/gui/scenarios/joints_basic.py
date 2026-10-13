# SPDX-License-Identifier: LGPL-2.1-or-later
"""Joint (J) on two plain bodies, only real input (docs/sciforge/parity/joints.md).

Plate = 0..40 x 0..30 x 10, Block = 50..70 x 0..10 x 20 (Extrude New Body).

  A  J: the dialog waits for component 1 (blue box). Hovering the block's top face lights up
     its snap points (centre, corners, edge midpoints), the centre nearest the mouse. Click
     near the centre: component 1 taken, the triad stays, the box for component 2 waits.
     Click the plate's top face near its centre: the block flies onto the plate, faces mating
     (top against top: the block stands upside down on the plate, 10..30 high, centred on
     (20, 15)), keeping its heading; the motion is previewed and comes back. Type Revolute;
     the plate was grounded (nothing held it), the note says so. OK: one "Revolute 1" in the
     timeline and in the browser's Joints folder; the plate's row shows the anchor. Ctrl+Z
     puts the block back where it was and removes the joint; Ctrl+Y brings both back.
  B  Edit from the timeline (double-click "Revolute 1"): Angle 90 turns the block about the
     joint axis (its 20 x 10 footprint turns); Offset Z 5 lifts it; Flip turns it over (right
     way up, hanging from the joint origin). OK, then Ctrl+Z undoes the edit in one step.
  C  Cancel: J, pick, pick, Cancel: the block is back where it was, no joint. Esc the same.
     The same component twice is refused with a message. J with only one body in another
     design says why.
"""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import joints_steps as j
from SciForgeTests.gui import timeline_input as t

V = App.Vector
state = {}
ON_PLATE = [10, 10, 10, 30, 20, 30]  # the block, upside down, centred on the plate's top


# -- A ---------------------------------------------------------------------------------------------
def a_press_j():
    j.press_j()


def a_waits():
    p = j.panel()
    h.check("Joint dialog open", p is not None and p.title == "Joint", p and p.title)
    s.no_popups("J")
    if p is None:
        return
    h.check("component 1 box waits", p.active == "comp1", p.active)
    h.check("hint asks for a snap point", "snap" in p.info.text().lower(), p.info.text())
    h.check("type starts Rigid", p.type_box.currentData() == "rigid", p.type_box.currentData())
    h.check("two tabs: Position, Motion", p.tabs.count() == 2 and p.tabs.tabText(1) == "Motion")


def a_hover_block():
    j.hover(V(58, 6, 20))  # the block's top face, near its centre


def a_snaps_shown():
    p = j.panel()
    kinds = j.snap_kinds(p)
    h.check("snap points on the top face: centre, corners, midpoints", kinds == ["centre", "midpoint", "vertex"], kinds)
    h.check("the centre is the nearest", j.hot_kind(p) == "centre", j.hot_kind(p))
    hov = p.hover
    if hov is not None and hov.hot is not None:
        h.check("the triad stands at the face centre", (hov.hot["point"] - V(60, 5, 20)).Length < 1e-6, hov.hot["point"])
    h.shot("A-snaps")


def a_click_block():
    h.click(V(58, 6, 20))


def a_block_taken():
    p = j.panel()
    h.check("component 1 = the block", p.picks["comp1"] is not None and p.picks["comp1"].part is j.block(), p.picks["comp1"])
    h.check("component 2 box waits now", p.active == "comp2", p.active)
    h.check("a triad marker stays", len(p.markers) == 1, len(p.markers))
    h.check("nothing moved yet", j.block().Shape.BoundBox.XMin == 50, j.block().Shape.BoundBox)


def a_click_plate():
    h.click(V(19, 14, 10))  # the plate's top face near its centre


def a_joined():
    p = j.panel()
    joints = j.joint_list()
    h.check("one joint made", len(joints) == 1, len(joints))
    j.box_is("block on the plate: 10..30 x 10..20 x 10..30", j.block().Shape.BoundBox, ON_PLATE, 1e-4)
    h.check("the plate was grounded by itself", j.joints_module().is_grounded(j.plate()))
    h.check("the note says so", "grounded" in p.note.text().lower(), p.note.text())
    h.check("the markers are gone", not p.markers, len(p.markers))
    state["anim"] = p.animator is not None
    h.shot("A-joined")


a_joined.wait_ms = 2600  # let the motion preview play out (1.8 s) and come back


def a_preview_done():
    p = j.panel()
    h.check("the preview animation ran (rigid: none)", not state["anim"], state["anim"])
    j.box_is("the block is back after the preview", j.block().Shape.BoundBox, ON_PLATE, 1e-4)
    h.check("no animation left running", p.animator is None)


def a_revolute():
    p = j.panel()
    p.tabs.setCurrentIndex(1)
    j.choose_type(p, "Revolute")


def a_revolute_set():
    p = j.panel()
    joint = j.joint_list()[0]
    h.check("FreeCAD joint type Revolute", joint.JointType == "Revolute", joint.JointType)
    h.check("label Revolute 1", joint.Label == "Revolute 1", joint.Label)
    h.check("Rotate axis box shown", p.axis_boxes["Rotate"][0].isVisible())
    h.check("Animate button shown", p.animate.isVisible())
    h.check("angle limits shown", p.angle_limits.rows["min"][0].isVisible())
    j.box_is("block still on the plate", j.block().Shape.BoundBox, ON_PLATE, 1e-4)


a_revolute_set.wait_ms = 2600


def a_ok():
    j.ok()


def a_done():
    j.no_dialog("OK")
    joints = j.joint_list()
    h.check("one joint after OK", len(joints) == 1, len(joints))
    h.check("timeline shows Revolute 1", "Revolute 1" in t.titles(), t.titles())
    labels = j.row_labels()
    h.check("browser has a Joints folder", "Joints" in labels, labels)
    h.check("browser lists Revolute 1", "Revolute 1" in labels, labels)
    j.box_is("block stays on the plate", j.block().Shape.BoundBox, ON_PLATE, 1e-4)
    state["block_plc"] = j.body_placement(j.block())
    h.shot("A-done")


def a_undo():
    s.undo()


def a_undone():
    h.check("undo removed the joint", not j.joint_list(), [x.Label for x in j.joint_list()])
    j.box_is("undo put the block back", j.block().Shape.BoundBox, [50, 0, 0, 70, 10, 20], 1e-4)
    h.check("undo removed the ground", not j.joints_module().is_grounded(j.plate()))


def a_redo():
    s.redo()


def a_redone():
    h.check("redo brought the joint back", len(j.joint_list()) == 1)
    j.box_is("redo put the block on the plate", j.block().Shape.BoundBox, ON_PLATE, 1e-4)


# -- B ---------------------------------------------------------------------------------------------
def b_edit():
    h.fit()
    t.double_click("Revolute 1")


def b_dialog():
    p = j.panel()
    h.check("Edit Joint dialog", p is not None and p.title == "Joint" and p.editing, p)
    if p is None:
        return
    h.check("type shows Revolute", p.type_box.currentData() == "revolute", p.type_box.currentData())
    h.check("component boxes filled", bool(p.fields["comp1"].button.text()) and "Select" not in p.fields["comp1"].button.text(), p.fields["comp1"].button.text())


def b_angle():
    p = j.panel()
    s.type_value(p.angle.widget, "90")


def b_turned():
    j.box_is("Angle 90 turned the block (10 x 20 footprint)", j.block().Shape.BoundBox, [15, 5, 10, 25, 25, 30], 1e-4)


def b_offset_z():
    p = j.panel()
    s.type_value(p.offset_fields["z"].widget, "5")


def b_lifted():
    j.box_is("Offset Z 5 lifts the block", j.block().Shape.BoundBox, [15, 5, 15, 25, 25, 35], 1e-4)


def b_flip():
    p = j.panel()
    b.click_widget(p.flip)


def b_flipped():
    p = j.panel()
    h.check("Flip pressed", p.flip.isChecked())
    # turned over: right way up, its top face at the (lifted) joint origin, hanging down from it
    j.box_is("Flip turns the block over", j.block().Shape.BoundBox, [15, 5, -5, 25, 25, 15], 1e-4)
    joint = j.joint_list()[0]
    h.check("flip stored", j.joints_module().offsets(joint)["flip"] is True)


def b_ok():
    j.ok()


def b_done():
    j.no_dialog("OK")
    h.check("still one joint", len(j.joint_list()) == 1)


def b_undo():
    s.undo()


def b_undone():
    h.check("one undo takes the whole edit", len(j.joint_list()) == 1)
    j.box_is("block as before the edit", j.block().Shape.BoundBox, ON_PLATE, 1e-4)
    joint = j.joint_list()[0]
    h.check("flip undone", j.joints_module().offsets(joint)["flip"] is False)


# -- C ---------------------------------------------------------------------------------------------
def c_delete_joint():
    t.menu("Revolute 1", "Delete")


def c_deleted():
    h.check("joint deleted from the timeline", not j.joint_list())
    j.box_is("the block stays where it was", j.block().Shape.BoundBox, ON_PLATE, 1e-4)
    helpers = [o for o in App.ActiveDocument.Objects if getattr(o, "SciForgeRole", "") in ("JointHelper",)]
    h.check("no helper left", not helpers)


def c_press_j():
    j.press_j()


def c_pick_block():
    h.click(V(28, 14, 30))  # the block's (now) top face


def c_same_again():
    p = j.panel()
    h.check("component 1 picked", p.picks["comp1"] is not None)
    h.click(V(12, 17, 30))  # the same block again


def c_refused():
    p = j.panel()
    h.check("second pick on the same component refused", p.picks["comp2"] is None)
    h.check("...with a message", "another component" in p.message.text().lower(), p.message.text())


def c_pick_plate():
    h.click(V(36, 27, 10))  # the plate's top face, near a corner


def c_moved():
    p = j.panel()
    h.check("corner snap taken", p.snaps["comp2"] is not None and p.snaps["comp2"]["kind"] == "vertex", p.snaps["comp2"])
    h.check("the block moved", j.block().Shape.BoundBox.XMin != 10, j.block().Shape.BoundBox)


c_moved.wait_ms = 2600


def c_cancel():
    j.cancel()


def c_cancelled():
    j.no_dialog("Cancel")
    h.check("no joint after Cancel", not j.joint_list())
    j.box_is("Cancel put the block back", j.block().Shape.BoundBox, ON_PLATE, 1e-4)


def c_press_j_again():
    j.press_j()


def c_pick_block_again():
    h.click(V(28, 14, 30))


def c_pick_plate_again():
    h.click(V(4, 3, 10))  # the plate's top face, clear of the block


def c_escape():
    b.press_guarded(QtCore.Qt.Key_Escape)


def c_escaped():
    j.no_dialog("Esc")
    h.check("no joint after Esc", not j.joint_list())
    j.box_is("Esc put the block back", j.block().Shape.BoundBox, ON_PLATE, 1e-4)
    h.check("no pop-ups", not b.POPUPS, b.POPUPS)


def c_one_body_design():
    App.newDocument("OneBody")
    h.fit()


def c_j_refused():
    j.press_j()
    h.check("J with no second body: no dialog", not Gui.Control.activeDialog())


def c_close_second():
    App.closeDocument("OneBody")


h.run(
    "joints_basic",
    [s.new_design("Joints")]
    + j.two_boxes()
    + [
        a_press_j,
        a_waits,
        a_hover_block,
        a_snaps_shown,
        a_click_block,
        a_block_taken,
        a_click_plate,
        a_joined,
        a_preview_done,
        a_revolute,
        a_revolute_set,
        a_ok,
        a_done,
        a_undo,
        a_undone,
        a_redo,
        a_redone,
        b_edit,
        b_dialog,
        b_angle,
        b_turned,
        b_offset_z,
        b_lifted,
        b_flip,
        b_flipped,
        b_ok,
        b_done,
        b_undo,
        b_undone,
        c_delete_joint,
        c_deleted,
        c_press_j,
        c_pick_block,
        c_same_again,
        c_refused,
        c_pick_plate,
        c_moved,
        c_cancel,
        c_cancelled,
        c_press_j_again,
        c_pick_block_again,
        c_pick_plate_again,
        c_escape,
        c_escaped,
        c_one_body_design,
        c_j_refused,
        c_close_second,
    ],
)
