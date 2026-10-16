# SPDX-License-Identifier: LGPL-2.1-or-later
"""A decal goes with its body when a joint moves it: made, driven, dragged, undone; only real
input. docs/sciforge/parity/misc.md, Decal (Luca: "decals dont follow their faces when
moved"). A joint moves a body at the root by its own placement, without recomputing it: the
decal must follow at once.

Plate = 0..40 x 0..30 x 10, Block = 50..70 x 0..10 x 20 (joints_steps.two_boxes).

J1 INSERT > Decal, click the block's front (y 0): a decal on it.
J2 J, the block's top, the plate's top, Revolute, OK: the joint puts the block upside down
   on the plate; the decal goes with the block.
J3 ASSEMBLE > Drive Joints, the joint's row, Rotation 90: the decal turns with the block while
   the dialog is open; OK: the same.
J4 Ctrl+Z: the block and its decal back at 0; Ctrl+Y: at 90 again.
J5 Component Drag (top view): a drag on the block round its axis turns it further; the decal
   is where the drag left the block. Ctrl+Z: back with it.
"""

import FreeCAD as App
from PySide import QtWidgets

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import fixdecal_steps as f
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import joints_steps as j
from SciForgeTests.gui import timeline_input as t

V = App.Vector
FRONT = V(60, 0, 10)  # the block's front face (normal -Y) where it was made
st = {}


def jm():
    return j.joints_module()


def joint():
    found = j.joint_list()
    return found[0] if found else None


def angle_now():
    jt = joint()
    return jm().value(jt)[0] if jt is not None else None


def moved_since(key):
    """How the block moved (design coordinates) since `key` was stored."""
    return j.block().getGlobalPlacement().multiply(st[key].inverse())


def keep(key):
    st[key] = App.Placement(j.block().getGlobalPlacement())
    st[key + "_decal"] = f.snapshot(f.flat())


def new_design():
    s.new_design("DecalJoints")()
    f.use_picture()


# -- J1 ----------------------------------------------------------------------------------------
def j1_check():
    obj = f.flat()
    h.check("J1 a decal on the block", obj is not None and obj.Body is j.block(), obj)
    if obj is None:
        return
    keep("j1")
    f.drawn_on_face("J1", obj)


# -- J2 ----------------------------------------------------------------------------------------
def j2_motion():
    p = j.panel()
    j.click_tab(p, "Motion")
    j.choose_type(p, "Revolute")


j2_motion.wait_ms = 2600


def j2_ok():
    j.ok()


j2_ok.wait_ms = 1500


def j2_check():
    j.no_dialog("Joint OK")
    h.check("J2 the joint is made", joint() is not None, j.joint_list())
    j.block_box("J2 the block is on the plate", j.ON_PLATE)
    f.follows("J2 the decal went with the block", f.flat(), st["j1_decal"], moved_since("j1"))
    h.shot("J2-joint")


# -- J3 ----------------------------------------------------------------------------------------
def j3_command():
    keep("j3")
    h.fit()
    j.menu("Drive Joints")


j3_command.wait_ms = 1200


def j3_row():
    t.click_row(joint().Label)


j3_row.wait_ms = 1200


def j3_type():
    p = j.panel()
    if h.check("J3 Drive Joints on the joint", p is not None and p.joint is joint(), p):
        s.type_value(p.angle.widget, "90")


j3_type.wait_ms = 1500


def j3_live():
    h.check("J3 the joint is at 90", abs((angle_now() or 0) - 90) < 1e-4, angle_now())
    f.follows("J3 while driving", f.flat(), st["j3_decal"], moved_since("j3"))
    h.shot("J3-driven")
    j.ok()


j3_live.wait_ms = 1500


def j3_check():
    j.no_dialog("Drive OK")
    f.follows("J3 after OK", f.flat(), st["j3_decal"], moved_since("j3"))


# -- J4 ----------------------------------------------------------------------------------------
def j4_undo():
    s.undo()


j4_undo.wait_ms = 1500


def j4_undone():
    h.check("J4 Ctrl+Z: back at 0", abs(angle_now() or 0) < 1e-4, angle_now())
    f.follows("J4 Ctrl+Z", f.flat(), st["j3_decal"], moved_since("j3"))
    h.check("J4 the block is where it was", moved_since("j3").isSame(App.Placement(), 1e-7))
    s.redo()


j4_undone.wait_ms = 1500


def j4_redone():
    h.check("J4 Ctrl+Y: at 90", abs((angle_now() or 0) - 90) < 1e-4, angle_now())
    f.follows("J4 Ctrl+Y", f.flat(), st["j3_decal"], moved_since("j3"))


# -- J5 ----------------------------------------------------------------------------------------
def j5_drag():
    keep("j5")
    h.view().viewTop()
    h.view().fitAll()
    QtWidgets.QApplication.processEvents()
    # at 90 the block's top (z 30) covers x 15..25, y 5..25 round the axis (20, 15): press 7 mm
    # along +Y from the axis and drag round to 7 mm along -X (a further quarter turn)
    h.drag(h.screen_point(V(20, 22, 30)), h.screen_point(V(13, 15, 30)), steps=16)
    j.wait(150)


j5_drag.wait_ms = 1500


def j5_check():
    from sciforge import joints_drag

    last = joints_drag.last() or {}
    h.check("J5 it was a drag along the joint", last.get("kind") == "joint", last)
    h.check("J5 the drag turned the block", abs((angle_now() or 90) - 90) > 20, angle_now())
    # the place the drag actually produced (CI's window differs by a pixel)
    f.follows(
        "J5 the decal is where the drag left the block", f.flat(), st["j5_decal"], moved_since("j5")
    )
    h.shot("J5-dragged")
    s.undo()


j5_check.wait_ms = 1500


def j5_undone():
    h.check("J5 Ctrl+Z: at 90 again", abs((angle_now() or 0) - 90) < 1e-3, angle_now())
    f.follows("J5 Ctrl+Z", f.flat(), st["j5_decal"], moved_since("j5"))


def cleanup():
    f.forget_picture()
    for name in list(App.listDocuments()):
        App.closeDocument(name)
    h.new_errors()


h.run(
    "fixdecal_joints",
    [new_design]
    + j.two_boxes()
    + f.decal_steps("j1_decal", FRONT)
    + [j1_check]
    + j.pick_pair("j2_pick")
    + [
        j2_motion,
        j2_ok,
        j2_check,
        j3_command,
        j3_row,
        j3_type,
        j3_live,
        j3_check,
        j4_undo,
        j4_undone,
        j4_redone,
        j5_drag,
        j5_check,
        j5_undone,
        cleanup,
    ],
)
