# SPDX-License-Identifier: LGPL-2.1-or-later
"""Motion Link (a pinion and its rack) and Motion Study, with real input
(docs/sciforge/parity/joints.md, "Motion Link", "Motion Study").

Plate = 0..40 x 0..30 x 10, Pinion = 50..60 x 0..10 x 10 (a 10 mm "gear"), Rack = 50..90 x
20..25 x 5. J: the pinion's top onto the plate's top centre, Revolute (upright axis through
(20, 15)); J: the rack's top onto the midpoint of the plate's top front edge, Slider along X.
Nothing is grounded.

  L1 ASSEMBLE > Motion Link: click the Revolute's row, then the Slider's: Angle 360 for the
     first, Distance 62.832 (2 pi x 10 mm) for the second; OK: "Motion Link 1" in the
     timeline and the Joints folder.
  L2 Drive Joints on the Revolute: one turn (360) slides the rack 2 pi r = 62.83 mm; the
     Revolute reads 360 (not 0). OK, then Ctrl+Z puts both back.
  L3 Dragging the pinion a quarter turn in the canvas slides the rack 15.71 mm.
  L4 Edit Motion Link 1 (timeline double-click), Reverse: a quarter turn now slides the rack
     the other way. Ctrl+Z.
  L5 Driving the Slider moves the pinion back (a link drives both ways).
  L6 ASSEMBLE > Motion Study: click the Revolute's row (a point at step 0 where it stands),
     Step 100, Angle 360, Set Point; the playhead at 50 shows half a turn (rack 31.4 mm);
     Play Once runs to step 100 (one turn, rack 62.8 mm); OK: "Motion Study 1" in the
     browser's Motion Studies folder and everything back where it was.
  L7 Save, close, reopen: the link still ties the joints (Drive 90 -> rack 15.71 mm).
"""

import math
import os
import tempfile

from PySide import QtCore, QtWidgets
from PySide6 import QtTest

import FreeCAD as App

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import joints_steps as j
from SciForgeTests.gui import timeline_input as t

V = App.Vector
state = {}
PINION = (50, 0, 60, 10)
RACK = (50, 20, 90, 25)
TURN = 2 * math.pi * 10.0  # one turn of the 10 mm pinion
TOL = 1e-3
LINK_TOL = 0.01  # the link's distance box keeps two decimals (62.83 mm)


def jm():
    return j.joints_module()


def doc():
    return App.ActiveDocument


def pinion():
    return s.bodies()[1]


def rack():
    return s.bodies()[2]


def by_label(label):
    for jt in j.joint_list():
        if jt.Label == label:
            return jt
    return None


def revolute():
    return by_label("Revolute 1")


def slider():
    return by_label("Slider 1")


def rack_x():
    return rack().Shape.BoundBox.XMin


def angle_now():
    jt = revolute()
    return jm().value(jt)[0] if jt is not None else None


def top_view():
    h.view().viewTop()
    h.view().fitAll()
    QtWidgets.QApplication.processEvents()


# -- the design --------------------------------------------------------------------------------
def pinion_steps():
    return s.box_steps("pinion", PINION, 10, V(5, -3, 0), new_body=True)


def rack_steps():
    return s.box_steps("rack", RACK, 5, V(5, -3, 0), new_body=True)


def rev_press():
    j.press_j()


def rev_first():
    h.click(V(56, 4, 10))  # the pinion's top near its centre


def rev_second():
    h.click(V(21, 16, 10))  # the plate's top near its centre


rev_second.wait_ms = 900


def rev_type():
    p = j.panel()
    j.click_tab(p, "Motion")
    j.choose_type(p, "Revolute")


rev_type.wait_ms = 2600


def rev_ok():
    j.ok()


def rev_made():
    j.no_dialog("Joint OK")
    h.check("Revolute 1 made", revolute() is not None)
    box = pinion().Shape.BoundBox
    h.check(
        "the pinion stands on the plate's centre",
        abs(box.Center.x - 20) < TOL and abs(box.Center.y - 15) < TOL,
        box,
    )
    j.box_is("the rack is where it was made", rack().Shape.BoundBox, [50, 20, 0, 90, 25, 5])
    h.shot("rev-made")


def sli_press():
    j.press_j()


def sli_first():
    from sciforge import joints_ui

    p = j.panel()
    h.check(
        "the Joint dialog is open (no prompt: nothing moved)",
        p is not None and p.title == "Joint" and joints_ui.prompt() is None,
        (p and p.title, joints_ui.prompt()),
    )
    h.click(V(70, 22, 5))  # the rack's top


def sli_second():
    p = j.panel()
    h.check(
        "the rack is component 1",
        p is not None and p.picks["comp1"] is not None and p.picks["comp1"].part is rack(),
        p and p.picks,
    )
    h.click(V(20, 2.5, 10))  # the plate's top, by the middle of its front edge


sli_second.wait_ms = 900


def sli_type():
    p = j.panel()
    h.check(
        "component 2 snapped to the front edge's middle",
        p.snaps["comp2"] is not None and p.snaps["comp2"]["kind"] == "midpoint",
        p.snaps["comp2"],
    )
    j.click_tab(p, "Motion")
    j.choose_type(p, "Slider")


sli_type.wait_ms = 2600


def sli_axis():
    p = j.panel()
    b.choose(p.axis_boxes["Slide"][0], "X Axis")


sli_axis.wait_ms = 1500


def sli_ok():
    j.ok()


def sli_made():
    j.no_dialog("Joint OK")
    h.check("Slider 1 made", slider() is not None)
    box = rack().Shape.BoundBox
    h.check("the rack lies along X on the plate's front edge", abs(box.XLength - 40) < TOL, box)
    state["rack_x"] = rack_x()
    state["pinion"] = App.Placement(pinion().Placement)


# -- L1 the link -------------------------------------------------------------------------------
def l1_menu():
    h.fit()
    j.menu("Motion Link")


def l1_first():
    p = j.panel()
    h.check("Motion Link open", p is not None and p.title == "Motion Link", p and p.title)
    h.check("it waits for joints", "two joints" in p.info.text(), p.info.text())
    t.click_row("Revolute 1")


def l1_second():
    t.click_row("Slider 1")


def l1_values():
    p = j.panel()
    h.check("both joints taken", [x.Label for x in p.picked] == ["Revolute 1", "Slider 1"])
    h.check("joint 1 is an angle, 360 to start", abs(p.rows[0]["field"].value() - 360) < 1e-9)
    h.check("Reverse shows with two joints", p.reverse.isVisible())
    s.type_value(p.rows[1]["field"].widget, "%.4f" % TURN)


def l1_ok():
    j.ok()


def l1_made():
    j.no_dialog("Motion Link OK")
    links = jm().motion_links(doc())
    h.check("Motion Link 1 made", len(links) == 1 and links[0].Label == "Motion Link 1", links)
    h.check("in the timeline", "Motion Link 1" in t.titles(), t.titles())
    h.check(
        "in the browser's Joints folder",
        "Motion Link 1" in (t.children("Joints") or []),
        t.children("Joints"),
    )
    h.check("nothing moved", abs(rack_x() - state["rack_x"]) < TOL)


# -- L2 one turn -------------------------------------------------------------------------------
def l2_drive():
    state["undos"] = doc().UndoCount
    j.browser_menu("Revolute 1", "Drive Joints")


def l2_type():
    p = j.panel()
    h.check("Drive Joints on Revolute 1", p is not None and p.joint is revolute())
    s.type_value(p.angle.widget, "360")


l2_type.wait_ms = 1500


def l2_turned():
    p = j.panel()
    moved = rack_x() - state["rack_x"]
    h.check("one turn slides the rack 2 pi r", abs(abs(moved) - TURN) < LINK_TOL, moved)
    state["sign"] = 1.0 if moved > 0 else -1.0
    h.check("the Revolute reads one whole turn", abs(angle_now() - 360) < 1e-6, angle_now())
    h.check("the box keeps 360", abs(p.angle.value() - 360) < 1e-6, p.angle.value())
    h.check(
        "the pinion looks the same after a turn", pinion().Placement.isSame(state["pinion"], 1e-6)
    )


def l2_ok():
    j.ok()


def l2_undo():
    j.no_dialog("Drive OK")
    s.undo()


def l2_undone():
    h.check("Ctrl+Z: the rack is back", abs(rack_x() - state["rack_x"]) < TOL, rack_x())
    h.check("and the Revolute at 0", abs(angle_now()) < 1e-6, angle_now())


# -- L3 the canvas drag carries the rack ---------------------------------------------------------
def l3_drag():
    top_view()
    # the pinion stands at 15..25 x 10..20 (upside down, heading kept); grab it off its axis
    h.drag(h.screen_point(V(24, 15, 20)), h.screen_point(V(20, 19, 20)), steps=16)
    j.wait(200)


def l3_dragged():
    turned = angle_now()
    h.check("the pinion turned about a quarter", abs(turned - 90) < 1.5, turned)
    moved = rack_x() - state["rack_x"]
    expect = state.get("sign", 1.0) * TURN * turned / 360.0
    h.check("the rack followed the link", abs(moved - expect) < LINK_TOL, (moved, expect))


def l3_undo():
    s.undo()


# -- L4 Reverse --------------------------------------------------------------------------------
def l4_edit():
    h.check("back at 0", abs(angle_now()) < 1e-6, angle_now())
    t.double_click("Motion Link 1")


def l4_reverse():
    p = j.panel()
    h.check("Edit Motion Link open", p is not None and p.title == "Motion Link", p and p.title)
    h.check("both joints shown", len(p.picked) == 2)
    s.toggle(p.reverse)


def l4_ok():
    p = j.panel()
    h.check("Reverse ticked", p.reverse.isChecked())
    j.ok()


def l4_drive():
    j.no_dialog("edit OK")
    j.browser_menu("Revolute 1", "Drive Joints")


def l4_type():
    s.type_value(j.panel().angle.widget, "90")


l4_type.wait_ms = 1500


def l4_reversed():
    moved = rack_x() - state["rack_x"]
    expect = -state.get("sign", 1.0) * TURN / 4
    h.check(
        "a quarter turn slides the rack the other way",
        abs(moved - expect) < LINK_TOL,
        (moved, expect),
    )


def l4_cancel():
    j.cancel()


# -- L5 the slider drives the pinion -------------------------------------------------------------
def l5_drive():
    j.no_dialog("Cancel")
    h.check("Cancel: rack back", abs(rack_x() - state["rack_x"]) < TOL)
    j.browser_menu("Slider 1", "Drive Joints")


def l5_type():
    p = j.panel()
    s.type_value(p.slide.widget, "%.4f" % (TURN / 2))


l5_type.wait_ms = 1500


def l5_turned():
    a = angle_now()
    h.check(
        "half a turn of the rack's travel turns the pinion half a turn", abs(abs(a) - 180) < 0.05, a
    )


def l5_cancel():
    j.cancel()


# -- L6 Motion Study -----------------------------------------------------------------------------
def l6_menu():
    j.no_dialog("Cancel")
    h.fit()
    j.menu("Motion Study")


def l6_pick():
    p = j.panel()
    h.check("Motion Study open", p is not None and p.title == "Motion Study", p and p.title)
    t.click_row("Revolute 1")


def l6_point():
    p = j.panel()
    h.check("the joint is in the study", p.data["joints"] == [revolute().Name], p.data["joints"])
    h.check(
        "a point at step 0 where it stands",
        p.data["keys"].get(revolute().Name) == [[0.0, 0.0]],
        p.data["keys"],
    )
    p.step.setFocus()
    p.step.selectAll()
    QtTest.QTest.keyClicks(p.step, "100")
    QtTest.QTest.keyClick(p.step, QtCore.Qt.Key_Tab)
    s.type_value(p.value_field.widget, "360")
    QtTest.QTest.mouseClick(p.set_point, QtCore.Qt.LeftButton)
    QtWidgets.QApplication.processEvents()


def l6_scrub():
    p = j.panel()
    h.check(
        "the point is listed",
        p.table.rowCount() == 2 and p.table.item(1, 0).text() == "100",
        p.table.rowCount(),
    )
    p.slider.setFocus()
    p.slider.setValue(50)  # as a drag of the playhead to the middle
    QtWidgets.QApplication.processEvents()


def l6_half():
    moved = rack_x() - state["rack_x"]
    h.check("step 50: half a turn", abs(angle_now() - 180) < 1e-6, angle_now())
    h.check("the rack followed (pi r)", abs(abs(moved) - TURN / 2) < LINK_TOL, moved)


def l6_play():
    p = j.panel()
    QtTest.QTest.mouseClick(p.play, QtCore.Qt.LeftButton)
    QtWidgets.QApplication.processEvents()
    state["played"] = []


def l6_watch():
    p = j.panel()
    end = 0
    while end < 80 and p.playing:
        j.wait(100)
        state["played"].append(angle_now())
        end += 1
    h.check("Play Once stopped by itself", not p.playing)
    h.check("it went through the turn", len(state["played"]) > 5, len(state["played"]))
    h.check("it ended at step 100 (one turn)", abs(angle_now() - 360) < 1e-6, angle_now())
    h.check("the playhead at the end", p.slider.value() == 100, p.slider.value())


l6_watch.wait_ms = 300


def l6_ok():
    j.ok()


def l6_done():
    j.no_dialog("Motion Study OK")
    studies = jm().motion_studies(doc())
    h.check("Motion Study 1 kept", len(studies) == 1 and studies[0].Label == "Motion Study 1")
    h.check(
        "in the browser's Motion Studies folder",
        "Motion Study 1" in (t.children("Motion Studies") or []),
        t.children("Motion Studies"),
    )
    h.check("everything back where it was", abs(rack_x() - state["rack_x"]) < TOL, rack_x())
    h.check("not in the timeline", "Motion Study 1" not in t.titles())


# -- L7 save / reopen ----------------------------------------------------------------------------
def l7_save_close():
    state["path"] = os.path.join(tempfile.mkdtemp(), "joints2_motion.FCStd")
    doc().saveAs(state["path"])
    App.closeDocument(doc().Name)


def l7_open():
    App.openDocument(state["path"])
    h.fit()


def l7_drive():
    h.check("the link is back", len(jm().motion_links(doc())) == 1)
    h.check("the study is back", len(jm().motion_studies(doc())) == 1)
    state["rack_x"] = rack_x()
    j.browser_menu("Revolute 1", "Drive Joints")


def l7_type():
    s.type_value(j.panel().angle.widget, "90")


l7_type.wait_ms = 1500


def l7_followed():
    moved = rack_x() - state["rack_x"]
    h.check("after reopening the rack still follows", abs(abs(moved) - TURN / 4) < LINK_TOL, moved)


def l7_cancel():
    j.cancel()


steps = [s.new_design("JointsMotion")]
steps += s.box_steps("plate", j.PLATE, j.PLATE_HEIGHT, V(6, -6, 0))
steps += pinion_steps() + rack_steps()
steps += [rev_press, rev_first, rev_second, rev_type, rev_ok, rev_made]
steps += [sli_press, sli_first, sli_second, sli_type, sli_axis, sli_ok, sli_made]
steps += [l1_menu, l1_first, l1_second, l1_values, l1_ok, l1_made]
steps += [l2_drive, l2_type, l2_turned, l2_ok, l2_undo, l2_undone]
steps += [l3_drag, l3_dragged, l3_undo]
steps += [l4_edit, l4_reverse, l4_ok, l4_drive, l4_type, l4_reversed, l4_cancel]
steps += [l5_drive, l5_type, l5_turned, l5_cancel]
steps += [l6_menu, l6_pick, l6_point, l6_scrub, l6_half, l6_play, l6_watch, l6_ok, l6_done]
steps += [l7_save_close, l7_open, l7_drive, l7_type, l7_followed, l7_cancel]

h.run("joints2_motion", steps)
