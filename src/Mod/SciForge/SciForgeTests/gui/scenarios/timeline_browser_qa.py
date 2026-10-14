# SPDX-License-Identifier: LGPL-2.1-or-later
"""The timeline the way Fusion users really use it (QA, only real input).

Path 1, an early edit breaks a later step: box, fillet r3 on the front top edge,
        double-click Extrude 1 and make the box 2 high. Fusion: the fillet turns red
        in the timeline with the reason on hover, nothing in the Report view, no
        pop-up; the box is still there. Back to 10: the fillet works again. Ctrl+Z /
        Ctrl+Y walk through both edits.
Path 2, editing a rolled-back step: the marker before the fillet, double-click the
        fillet. Fusion rolls to it while its dialog is open and puts the marker back
        after OK.
Path 3, a new step while rolled back goes in at the marker (Create Sketch on the top
        face, circle, E = a boss), the later fillet stays rolled back until the marker
        is dragged to the end, and still rounds the same edge on the new base.
Path 4, Play, then E straight away: the command starts and playback stops (it must
        not roll the design under the open dialog); Cancel leaves the design where
        playback stopped.
Path 5, undo of a marker drag: Ctrl+Z puts the marker back and the 3D view shows the
        last step again.

Numbers by hand: box 40 x 30 x 10 = 12000; a radius r round along a 40 mm edge
removes 40 r^2 (1 - pi/4); the boss r5, 5 high adds 125 pi.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import timeline_input as t

V = App.Vector
s = {}
BOX = 12000.0
BOSS = 25.0 * math.pi * 5.0
FRONT_TOP = V(20, 0, 10)


def round_off(r):
    return 40.0 * b.spandrel(r)


def xpanel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return p if p is not None and not p._closed else None


def fpanel():
    return b.blend_panel()


# -- the part: box, fillet --------------------------------------------------------------
def fillet_start():
    h.click_empty()
    h.ribbon("Fillet")


def fillet_edge():
    h.fit()
    h.click_edge(FRONT_TOP)


def fillet_radius():
    p = fpanel()
    h.check("fillet dialog has the edge", p is not None and len(p.refs) == 1, p and p.refs)
    if p is not None:
        ui.type_into(p.radius.widget, "3")


def fillet_ok():
    h.task_button("OK")


def part_made():
    v = t.volume()
    h.check("box with an r3 round", t.near(v, BOX - round_off(3)), v)
    h.check(
        "timeline: Sketch 1, Extrude 1, Fillet 1",
        t.titles() == ["Sketch 1", "Extrude 1", "Fillet 1"],
        t.titles(),
    )
    h.shot("1-part")


# -- Path 1: an early edit breaks a later step ---------------------------------------------
def p1_edit_box():
    t.double_click("Extrude 1")


def p1_type_2():
    p = xpanel()
    h.check("double-click opens Extrude on Extrude 1", p is not None)
    if p is not None:
        ui.type_into(p.distance.widget, "2")


def p1_ok():
    h.task_button("OK")


def p1_fillet_red():
    h.check("extrude dialog closed", not t.dialog_open())
    i = t.item("Fillet 1")
    h.check("Fillet 1 red", i is not None and i.status == "error", i and (i.status, i.message))
    tip = t.button("Fillet 1").toolTip() if i else ""
    h.check("the reason is on hover", "Error" in tip and len(tip.splitlines()) >= 2, tip)
    h.check("the box is still there, 2 high", t.near(t.volume(), 2400.0), t.volume())
    h.check("Extrude 1 itself is fine", t.item("Extrude 1").status == "ok", t.states())
    t.no_popups("an edit that breaks a later step")
    h.shot("2-fillet-red")


def p1_edit_again():
    t.double_click("Extrude 1")


def p1_type_10():
    p = xpanel()
    h.check("Extrude dialog opens again", p is not None)
    if p is not None:
        ui.type_into(p.distance.widget, "10")


def p1_ok_2():
    h.task_button("OK")


def p1_fillet_back():
    i = t.item("Fillet 1")
    h.check("Fillet 1 works again", i is not None and i.status == "ok", i and i.message)
    h.check("box and round back", t.near(t.volume(), BOX - round_off(3)), t.volume())


def p1_undo():
    t.ctrl("z")


def p1_after_undo():
    h.check("Ctrl+Z: 2 high again", t.near(t.volume(), 2400.0), t.volume())
    i = t.item("Fillet 1")
    h.check("and the fillet red again", i is not None and i.status == "error", t.states())


def p1_redo():
    t.ctrl("y")


def p1_after_redo():
    h.check("Ctrl+Y: back to 10 with the round", t.near(t.volume(), BOX - round_off(3)), t.volume())
    h.check("nothing red", all(i.status == "ok" for i in t.tl().items()), t.states())


# -- Path 2: editing a rolled-back step ------------------------------------------------------
def p2_roll_back():
    t.drag_marker(before_title="Fillet 1")


def p2_rolled():
    h.check("rolled back before the fillet", t.near(t.volume(), BOX), t.volume())
    h.check("Fillet 1 after the marker", t.item("Fillet 1").state == "rolled_back", t.states())


def p2_edit_fillet():
    t.double_click("Fillet 1")


def p2_editing():
    p = fpanel()
    h.check("double-click opens the fillet", p is not None)
    h.check(
        "Fusion rolls to the step while it is edited",
        t.near(t.volume(), BOX - round_off(3)),
        t.volume(),
    )
    h.check("the fillet is drawn", t.shown(t.obj("Fillet 1")))
    if p is not None:
        ui.type_into(p.radius.widget, "2")
    h.shot("3-edit-rolled-back")


def p2_preview():
    h.check("the preview shows the new radius", t.near(t.volume(), BOX - round_off(2)), t.volume())
    h.task_button("OK")


def p2_marker_back():
    h.check("dialog closed", not t.dialog_open())
    h.check(
        "the marker goes back where it was",
        t.item("Fillet 1").state == "rolled_back",
        t.states(),
    )
    h.check("so the part is the box again", t.near(t.volume(), BOX), t.volume())
    h.check("the box is drawn", t.shown(t.obj("Extrude 1")))
    h.check("the fillet is not", not t.shown(t.obj("Fillet 1")))
    h.check("the edit is kept", abs(t.obj("Fillet 1").Radius.Value - 2.0) < 1e-9)


# -- Path 3: a new step while rolled back goes in at the marker ---------------------------------
def p3_sketch():
    h.click_empty()
    h.ribbon("Create Sketch")


def p3_pick_top():
    h.fit()
    h.click(V(20, 15, 10))


def p3_circle():
    sk = h.in_sketch()
    h.check("sketch on the top face", sk is not None)
    if sk:
        x, y = h.to_sketch(sk, V(20, 15, 10))
        h.draw_circle(sk, x, y, 5)


def p3_finish():
    h.ribbon("Finish Sketch")


def p3_extrude():
    h.fit()
    h.press("e")


def p3_boss():
    p = xpanel()
    h.check("Extrude picked the circle", p is not None and len(p.profiles) == 1)
    if p is not None:
        ui.type_into(p.distance.widget, "5")


def p3_ok():
    p = xpanel()
    h.check("out of the part: Join", p is not None and p.operation.currentText() == "Join")
    h.task_button("OK")


def p3_inserted():
    titles = t.titles()
    h.check(
        "the new steps went in at the marker",
        titles == ["Sketch 1", "Extrude 1", "Sketch 2", "Extrude 2", "Fillet 1"],
        titles,
    )
    st = t.states()
    h.check(
        "the marker is after them, the fillet still rolled back",
        st.get("Extrude 2", ("",))[0] == "done" and st.get("Fillet 1", ("",))[0] == "rolled_back",
        st,
    )
    h.check("box with a boss", t.near(t.volume(), BOX + BOSS), t.volume())
    h.shot("4-inserted")


def p3_marker_end():
    t.drag_marker(to_end=True)


def p3_all():
    s["full"] = BOX + BOSS - round_off(2)
    h.check("marker at the end: boss and round", t.near(t.volume(), s["full"]), t.volume())
    i = t.item("Fillet 1")
    h.check("the round still works on its new base", i.status == "ok", (i.status, i.message))
    h.check("marker at the end", t.tl()._timeline.at_end)


# -- Path 4: Play, then E straight away -------------------------------------------------------
def p4_play():
    t.playback("play")
    s["play_volume"] = t.volume()  # Play starts from the beginning (an empty design)
    h.press("e")


def p4_after():
    h.check("E opened Extrude during playback", xpanel() is not None)
    s["play_tip"] = getattr(h.body().Tip, "Name", None)  # None: Play starts empty


p4_after.wait_ms = 1500  # playback would have moved on by now


def p4_still():
    h.check(
        "playback stopped: the design does not change under the dialog",
        getattr(h.body().Tip, "Name", None) == s.get("play_tip"),
        (getattr(h.body().Tip, "Name", None), s.get("play_tip")),
    )
    h.task_button("Cancel")


p4_still.wait_ms = 1500


def p4_cancelled():
    h.check("dialog closed", not t.dialog_open())
    h.check(
        "Cancel leaves the design where playback stopped",
        t.near(t.volume(), s["play_volume"]),
        (t.volume(), s["play_volume"]),
    )
    h.check("nothing added", len(t.titles()) == 5, t.titles())
    t.drag_marker(to_end=True)


def p4_end():
    h.check("marker at the end", t.tl()._timeline.at_end, t.states())
    h.check("whole design", t.near(t.volume(), s["full"]), t.volume())
    h.check("the last step is drawn", t.shown(t.obj("Fillet 1")))


# -- Path 5: undo of a marker drag -----------------------------------------------------------------
def p5_drag():
    t.drag_marker(before_title="Extrude 2")


def p5_rolled():
    h.check("rolled back to the box", t.near(t.volume(), BOX), t.volume())
    h.check("the box is drawn", t.shown(t.obj("Extrude 1")))
    t.ctrl("z")


def p5_undone():
    h.check("Ctrl+Z puts the marker back at the end", t.tl()._timeline.at_end, t.states())
    h.check("whole design again", t.near(t.volume(), s["full"]), t.volume())
    h.check("the 3D view shows the last step", t.shown(t.obj("Fillet 1")))
    h.check("and not an earlier one", not t.shown(t.obj("Extrude 1")))
    t.ctrl("y")


def p5_redone():
    h.check("Ctrl+Y rolls back again", t.near(t.volume(), BOX), t.volume())
    h.check("the box is drawn", t.shown(t.obj("Extrude 1")))
    h.check("the fillet is not", not t.shown(t.obj("Fillet 1")))
    t.drag_marker(to_end=True)


def end():
    h.check("final part", t.near(t.volume(), s["full"]), t.volume())
    t.no_popups("the end")
    h.shot("5-end")


STEPS = b.box_steps("TimelineQA") + [
    fillet_start,
    fillet_edge,
    fillet_radius,
    fillet_ok,
    part_made,
    p1_edit_box,
    p1_type_2,
    p1_ok,
    p1_fillet_red,
    p1_edit_again,
    p1_type_10,
    p1_ok_2,
    p1_fillet_back,
    p1_undo,
    p1_after_undo,
    p1_redo,
    p1_after_redo,
    p2_roll_back,
    p2_rolled,
    p2_edit_fillet,
    p2_editing,
    p2_preview,
    p2_marker_back,
    p3_sketch,
    p3_pick_top,
    p3_circle,
    p3_finish,
    p3_extrude,
    p3_boss,
    p3_ok,
    p3_inserted,
    p3_marker_end,
    p3_all,
    p4_play,
    p4_after,
    p4_still,
    p4_cancelled,
    p4_end,
    p5_drag,
    p5_rolled,
    p5_undone,
    p5_redone,
    end,
]

h.run("timeline_browser_qa", t.watched(STEPS))
