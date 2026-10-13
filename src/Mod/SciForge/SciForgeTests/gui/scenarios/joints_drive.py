# SPDX-License-Identifier: LGPL-2.1-or-later
"""Drive Joints, Capture / Revert Position, limits, Animate Joint, Suppress, save / reopen and
deleting a jointed body, only real input (docs/sciforge/parity/joints.md).

Plate = 0..40 x 0..30 x 10, Block = 50..70 x 0..10 x 20; J joins the block's top to the
plate's top as a Revolute (the block stands upside down on the plate, turning about the
upright axis through (20, 15)).

  D1 ASSEMBLE > Drive Joints, click the joint's row in the browser: a Rotation box and a
     slider. Type 90: the block turns a quarter; PageUp on the slider adds a degree (91). OK.
  D2 Ctrl+Z undoes the drive in one step; Ctrl+Y drives again.
  D3 ASSEMBLE > Capture Position: "Position 1" in the timeline. Drive to 30 (right-click the
     joint > Drive Joints), OK; ASSEMBLE > Revert Position: back at 91.
  D4 Right-click > Edit Joint Limits: the Motion tab; Maximum switched on starts at 91 (nothing
     moves); type 45: the block goes to 45. OK.
  D5 Drive Joints: 120 stops at 45; -60 is fine; Cancel puts it back at 45.
  D6 Right-click > Animate Joint: it swings, never past 45; Esc: it stands at 45 again.
  D7 Timeline right-click > Suppress Features: the joint is off; Unsuppress: on again, nothing
     jumped.
  D8 Save, close, reopen: the joint, the captured position, the ground and the limit are all
     there; Drive Joints still works (10, OK), Ctrl+Z.
  D9 Delete the block (its row's menu): its joint goes with it, one undo step; Ctrl+Z brings
     both back and the solver is happy.
"""

import os
import tempfile

from PySide import QtCore
from PySide6 import QtTest

import FreeCAD as App

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import joints_steps as j
from SciForgeTests.gui import timeline_input as t

V = App.Vector
state = {}


def jm():
    return j.joints_module()


def joint():
    found = j.joint_list()
    return found[0] if found else None


def angle_now():
    jt = joint()
    return jm().value(jt)[0] if jt is not None else None


def angle_is(name, expect, tol=1e-4):
    got = angle_now()
    return h.check(name, got is not None and abs(got - expect) < tol, got)


def doc():
    return App.ActiveDocument


# -- the joint ------------------------------------------------------------------------------------
def make_motion():
    p = j.panel()
    j.click_tab(p, "Motion")
    j.choose_type(p, "Revolute")


make_motion.wait_ms = 2600


def make_ok():
    j.ok()


def made():
    j.no_dialog("Joint OK")
    h.check("Revolute 1 made", joint() is not None and joint().Label == "Revolute 1")
    j.block_box("block on the plate", j.ON_PLATE)


# -- D1 -------------------------------------------------------------------------------------------
def d1_command():
    h.fit()
    j.menu("Drive Joints")


def d1_waits():
    p = j.panel()
    h.check("Drive Joints open", p is not None and p.title == "Drive Joints", p and p.title)
    h.check("it waits for a joint", p is not None and p.active == "joint" and p.joint is None)


def d1_pick_row():
    t.click_row("Revolute 1")


def d1_taken():
    p = j.panel()
    h.check("the joint is taken", p is not None and p.joint is joint(), p and p.joint)
    h.check("a Rotation box and slider", p.angle.widget.isVisible() and p.angle_slider.isVisible())
    h.check("no Distance box for a Revolute", not p.slide.widget.isVisible())


def d1_type_90():
    s.type_value(j.panel().angle.widget, "90")


def d1_turned():
    angle_is("the joint is at 90", 90)
    j.block_box("the block turned a quarter", [15, 5, 10, 25, 25, 30])
    h.check(
        "the slider follows", j.panel().angle_slider.value() == 900, j.panel().angle_slider.value()
    )


def d1_slider_key():
    slider = j.panel().angle_slider
    slider.setFocus()  # as Tab would: a click on the groove would jump a page first
    QtTest.QTest.keyClick(slider, QtCore.Qt.Key_PageUp)


def d1_slid():
    p = j.panel()
    h.check("PageUp: one more degree in the box", abs(p.angle.value() - 91) < 1e-6, p.angle.value())
    angle_is("the joint is at 91", 91)


def d1_ok():
    j.ok()


def d1_done():
    j.no_dialog("Drive OK")
    angle_is("OK kept 91", 91)


# -- D2 -------------------------------------------------------------------------------------------
def d2_undo():
    s.undo()


def d2_undone():
    angle_is("Ctrl+Z: back at 0", 0)
    j.block_box("the block is back", j.ON_PLATE)


def d2_redo():
    s.redo()


def d2_redone():
    angle_is("Ctrl+Y: at 91 again", 91)


# -- D3 -------------------------------------------------------------------------------------------
def d3_capture():
    j.menu("Capture Position")


def d3_captured():
    h.check("Position 1 in the timeline", "Position 1" in t.titles(), t.titles())
    h.check("nothing left to capture", not jm().positions_dirty(doc()))


def d3_drive():
    j.browser_menu("Revolute 1", "Drive Joints")


def d3_type_30():
    p = j.panel()
    h.check("Drive Joints open on Revolute 1", p is not None and p.joint is joint())
    s.type_value(p.angle.widget, "30")


def d3_ok():
    j.ok()


def d3_at_30():
    j.no_dialog("Drive OK")
    angle_is("at 30", 30)
    h.check("the position is not the captured one now", jm().positions_dirty(doc()))


def d3_revert():
    j.menu("Revert Position")


def d3_reverted():
    angle_is("Revert: back at 91 (the captured position)", 91)
    h.check("nothing to revert any more", not jm().positions_dirty(doc()))


# -- D4 -------------------------------------------------------------------------------------------
def d4_limits():
    j.browser_menu("Revolute 1", "Edit Joint Limits")


def d4_max_on():
    p = j.panel()
    h.check(
        "the Joint dialog on its Motion tab",
        p is not None and p.title == "Joint" and p.tabs.currentIndex() == 1,
        p and p.title,
    )
    if p is None:
        return
    s.toggle(p.angle_limits.rows["max"][0])


def d4_prefilled():
    p = j.panel()
    h.check(
        "Maximum starts at the joint's value (91)",
        abs(p.angle_limits.rows["max"][1].value() - 91) < 1e-4,
        p.angle_limits.rows["max"][1].value(),
    )
    angle_is("nothing moved", 91)


def d4_type_45():
    s.type_value(j.panel().angle_limits.rows["max"][1].widget, "45")


def d4_clamped():
    angle_is("the block went to the 45 limit", 45)


def d4_ok():
    j.ok()


def d4_done():
    j.no_dialog("Edit Joint Limits OK")
    lim = jm().limits(joint())["angle"]
    h.check("maximum 45 stored", lim["max"] == 45 and lim["min"] is None, lim)
    angle_is("still at 45", 45)


# -- D5 -------------------------------------------------------------------------------------------
def d5_drive():
    j.browser_menu("Revolute 1", "Drive Joints")


def d5_type_120():
    s.type_value(j.panel().angle.widget, "120")


def d5_stopped():
    p = j.panel()
    angle_is("120 stops at the limit", 45)
    h.check("the box shows 45", abs(p.angle.value() - 45) < 1e-6, p.angle.value())


def d5_type_minus_60():
    s.type_value(j.panel().angle.widget, "-60")


def d5_minus_60():
    angle_is("-60 is inside", -60)


def d5_cancel():
    j.cancel()


def d5_back():
    j.no_dialog("Drive Cancel")
    angle_is("Cancel: back at 45", 45)


# -- D6 -------------------------------------------------------------------------------------------
def d6_animate():
    j.browser_menu("Revolute 1", "Animate Joint")
    state["d6"] = j.sample(joint(), j.block(), 2.0)


def d6_watched():
    samples = state.get("d6") or []
    h.check("watched the animation", len(samples) >= 5, len(samples))
    angles = [r["angle"] for r in samples]
    h.check("never past the 45 limit", max(angles) <= 45 + 1e-6, max(angles))
    h.check("it swings", j.spread(angles) > 40, j.spread(angles))


def d6_escape():
    b.press_guarded(QtCore.Qt.Key_Escape)


def d6_stopped():
    from sciforge import joints_ui

    h.check("Esc stopped it", joints_ui._STANDALONE["animator"] is None)
    angle_is("back at 45", 45)
    h.check("no pop-ups", not b.POPUPS, b.POPUPS)


# -- D7 -------------------------------------------------------------------------------------------
def d7_suppress():
    state["plc"] = App.Placement(j.block().Placement)
    j.timeline_menu("Revolute 1", "Suppress Features")


def d7_suppressed():
    h.check("the joint is suppressed", bool(joint().Suppressed))
    h.check("the timeline shows it off", t.button("Revolute 1") is not None)
    h.check("the block did not jump", j.block().Placement.isSame(state["plc"], 1e-6))


def d7_unsuppress():
    j.timeline_menu("Revolute 1", "Unsuppress Features")


def d7_unsuppressed():
    h.check("the joint is on again", not joint().Suppressed)
    angle_is("and still at 45", 45)
    h.check("the solver is happy", jm().solve(doc()) == 0)


# -- D8 -------------------------------------------------------------------------------------------
def d8_save_close():
    state["path"] = os.path.join(tempfile.mkdtemp(), "joints_drive.FCStd")
    doc().saveAs(state["path"])
    App.closeDocument(doc().Name)


def d8_open():
    App.openDocument(state["path"])
    h.fit()


def d8_reopened():
    jt = joint()
    h.check("the joint is back", jt is not None and jt.Label == "Revolute 1", jt)
    if jt is None:
        return
    h.check("still SciForge's joint", type(jt.Proxy).__name__ == "JointProxy", type(jt.Proxy))
    h.check("still a Revolute", jt.JointType == "Revolute" and jm().fusion_type(jt) == "revolute")
    h.check(
        "the timeline shows it and the captured position",
        "Revolute 1" in t.titles() and "Position 1" in t.titles(),
        t.titles(),
    )
    h.check(
        "the browser's Joints folder lists it",
        "Revolute 1" in (t.children("Joints") or []),
        t.children("Joints"),
    )
    h.check("the plate is still grounded", jm().is_grounded(j.plate()))
    h.check("the limit is kept", jm().limits(jt)["angle"]["max"] == 45)
    angle_is("still at 45", 45)
    h.check("the solver is happy", jm().solve(doc()) == 0)


def d8_drive():
    j.browser_menu("Revolute 1", "Drive Joints")


def d8_type_10():
    p = j.panel()
    h.check("Drive Joints works after reopening", p is not None and p.joint is joint())
    if p is not None:
        s.type_value(p.angle.widget, "10")


def d8_ok():
    j.ok()


def d8_driven():
    j.no_dialog("Drive OK")
    angle_is("at 10", 10)


def d8_undo():
    s.undo()


def d8_undone():
    angle_is("Ctrl+Z: back at 45", 45)


# -- D9 -------------------------------------------------------------------------------------------
def d9_delete():
    state["undos"] = doc().UndoCount
    j.browser_menu(j.block().Label, "Delete")


def d9_deleted():
    h.check("the block is gone", len(s.bodies()) == 1, len(s.bodies()))
    h.check("its joint went with it", not j.joint_list(), [x.Label for x in j.joint_list()])
    h.check("the timeline has no joint", "Revolute 1" not in t.titles(), t.titles())
    h.check(
        "one undo step", doc().UndoCount == state["undos"] + 1, (state["undos"], doc().UndoCount)
    )


def d9_undo():
    s.undo()


def d9_back():
    h.check("the block is back", len(s.bodies()) == 2)
    h.check("its joint is back", joint() is not None and joint().Label == "Revolute 1")
    angle_is("at 45", 45)
    h.check("the solver is happy", jm().solve(doc()) == 0)


steps = [s.new_design("JointDrive")] + j.two_boxes() + j.pick_pair("make")
steps += [make_motion, make_ok, made]
steps += [
    d1_command,
    d1_waits,
    d1_pick_row,
    d1_taken,
    d1_type_90,
    d1_turned,
    d1_slider_key,
    d1_slid,
    d1_ok,
    d1_done,
]
steps += [d2_undo, d2_undone, d2_redo, d2_redone]
steps += [d3_capture, d3_captured, d3_drive, d3_type_30, d3_ok, d3_at_30, d3_revert, d3_reverted]
steps += [d4_limits, d4_max_on, d4_prefilled, d4_type_45, d4_clamped, d4_ok, d4_done]
steps += [d5_drive, d5_type_120, d5_stopped, d5_type_minus_60, d5_minus_60, d5_cancel, d5_back]
steps += [d6_animate, d6_watched, d6_escape, d6_stopped]
steps += [d7_suppress, d7_suppressed, d7_unsuppress, d7_unsuppressed]
steps += [
    d8_save_close,
    d8_open,
    d8_reopened,
    d8_drive,
    d8_type_10,
    d8_ok,
    d8_driven,
    d8_undo,
    d8_undone,
]
steps += [d9_delete, d9_deleted, d9_undo, d9_back]

h.run("joints_drive", steps)
