# SPDX-License-Identifier: LGPL-2.1-or-later
"""Hole and Thread on a part made of several features, mixed with Create Sketch, Extrude and
Press Pull before and after (QA, only real input).

Path 9,  a box and a boss (Create Sketch on the top face, E): H on the boss's top, X / Y
         typed, Extents All: a hole through boss and box.
Path 10, Press Pull the box's end face after the hole (Q): the hole is untouched.
Path 11, double-click the first Extrude in the timeline and make the box taller: the boss,
         the hole on it and the Press Pull all follow; nothing breaks.
Path 12, a sketch with two points on the top face, selected in the browser, then H: holes at
         both points at once (From Sketch); the sketch is hidden on OK.
Path 13, edit that sketch and move a point: its hole moves along.
Path 14, the timeline marker dragged back before the Press Pull, a hole added there, the
         marker back to the end: the new hole sits in the timeline where it was made and the
         later steps still work.
Path 15, Thread the boss (CREATE > Thread), Modeled; then make the boss taller (edit its
         Extrude): the full-length thread follows the longer boss.

Volumes by hand: box 40 x 30 x h, boss d12 x 8 (pi 36 * 8), a through hole d removes
pi d^2/4 * (its length in material); hole_steps / thread_core have the formulas.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui
import Part

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import hole_steps as hs
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import timeline_input as ti

V = App.Vector
s = {}
BOSS_R, BOSS_H = 6.0, 8.0


def doc():
    return App.ActiveDocument


def dialog_open():
    return bool(Gui.Control.activeDialog())


def panel():
    return hs.hole_panel()


def msg():
    return hs.message(panel())


def boss(height=BOSS_H):
    return math.pi * BOSS_R * BOSS_R * height


def broken():
    return [o.Label for o in doc().Objects if "Invalid" in o.State or "Error" in o.State]


def part_ok(where):
    h.check("%s: nothing in error" % where, not broken(), broken())
    h.check("%s: valid solid" % where, h.body().Shape.isValid())
    tip = h.body().Tip
    h.check("%s: the part is shown" % where, tip is not None and tip.ViewObject.isVisible())


# -- Path 9: a hole through the boss and the box -----------------------------------------------
def p9_h():
    s["v"] = h.solid_volume()
    h.check("box with boss", hs.close(s["v"], hs.BOX + boss()), s["v"])
    h.press("h")


def p9_click_boss():
    h.fit()
    h.click(V(23, 17, 10 + BOSS_H))


def p9_place():
    p = panel()
    h.check("P9 the boss's top takes the hole", p is not None and p.target is not None, msg())
    if p is None:
        return
    hs.type_into(p.pos_x.widget, "20")
    hs.type_into(p.pos_y.widget, "15")
    b.choose(p.extent, "All")
    hs.type_into(p.diameter.widget, "5")


def p9_preview():
    p = panel()
    c = hs.centre_of(p.target) if p and p.target else None
    h.check("P9 centred on the boss", hs.vnear(c, V(20, 15, 10 + BOSS_H), 1e-6), c)
    v = h.solid_volume()
    expect = s["v"] - hs.cylinder(5, 10 + BOSS_H)
    h.check("P9 through boss and box", hs.close(v, expect), (v, expect))
    h.check("P9 no depth arrow for All", p is not None and "depth" not in p.draggers)
    h.shot("p9-through")
    h.task_button("OK")


def p9_done():
    h.check("P9 closed", not dialog_open())
    s["v"] = h.solid_volume()
    part_ok("P9")


# -- Path 10: Press Pull after the hole ---------------------------------------------------------
def p10_q():
    h.click_empty()
    h.press("q")


def p10_face():
    h.fit()
    h.click(V(40, 8, 4))


def p10_distance():
    from sciforge import presspull_ui

    p = presspull_ui.PressPullPanel.last
    h.check("P10 Press Pull took the end face", p is not None and p.target is not None)
    if p:
        hs.type_into(p.field.widget, "5")


def p10_ok():
    h.task_button("OK")


def p10_done():
    v = h.solid_volume()
    expect = s["v"] + 5 * 30 * 10
    h.check("P10 the box is 5 longer, the hole untouched", hs.close(v, expect), (v, expect))
    part_ok("P10")
    s["v"] = v


# -- Path 11: an earlier step edited ------------------------------------------------------------
def p11_edit():
    h.fit()
    b.timeline_double_click("Extrude 1", click_first=True)


def p11_taller():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    h.check("P11 editing Extrude 1", p is not None and p.editing and not p._closed)
    if p:
        hs.type_into(p.distance.widget, "14")


def p11_ok():
    h.task_button("OK")


def p11_done():
    v = h.solid_volume()
    expect = 45 * 30 * 14 + boss() - hs.cylinder(5, 14 + BOSS_H)
    h.check(
        "P11 box 14 high: the boss, its hole and the Press Pull follow",
        hs.close(v, expect),
        (v, expect),
    )
    hl = hs.holes()
    c = hs.centre_of(hl[0]) if hl else None
    h.check("P11 the hole is on the boss's new top", hs.vnear(c, V(20, 15, 14 + BOSS_H), 1e-6), c)
    part_ok("P11")
    s["v"] = v
    h.shot("p11-taller")


# -- Path 12: From Sketch, the sketch picked in the browser before H ----------------------------
Q1 = V(6, 6, 14)
Q2 = V(38, 24, 14)


def p12_sketch():
    h.fit()
    h.ribbon("Create Sketch")


def p12_top():
    h.click(V(4, 26, 14))


def p12_points():
    sk = h.in_sketch()
    h.check("P12 sketch open on the top face", sk is not None)
    if sk is None:
        return
    s["sketch"] = sk.Name
    for q in (Q1, Q2):
        x, y = h.to_sketch(sk, q)
        sk.addGeometry(Part.Point(V(x, y, 0)))
    doc().recompute()


def p12_finish():
    h.ribbon("Finish Sketch")


def p12_select():
    sk = doc().getObject(s.get("sketch", ""))
    if sk is not None:
        ti.click_row(sk.Label)


def p12_h():
    sel = Gui.Selection.getSelectionEx()
    h.check(
        "P12 the sketch is selected in the browser",
        [x.ObjectName for x in sel] == [s.get("sketch")],
        [(x.ObjectName, x.SubElementNames) for x in sel],
    )
    h.press("h")


def p12_both():
    p = panel()
    h.check("P12 From Sketch at once", p is not None and p.placement.currentData() == "sketch")
    spots = hs.centres_all(p.target) if p and p.target else []
    h.check("P12 a hole at each point", len(spots) == 2, spots)
    if p:
        b.choose(p.extent, "Distance")
        hs.type_into(p.diameter.widget, "3")
        hs.type_into(p.depth.widget, "4")
        b.choose(p.drill_point, "Flat")


def p12_ok():
    v = h.solid_volume()
    expect = s["v"] - 2 * hs.cylinder(3, 4)
    h.check("P12 two holes d3 x 4", hs.close(v, expect), (v, expect))
    h.task_button("OK")


def p12_done():
    h.check("P12 closed", not dialog_open())
    sk = doc().getObject(s.get("sketch", ""))
    h.check("P12 the used sketch is hidden", sk is not None and not hs.visible(sk))
    part_ok("P12")
    s["v"] = h.solid_volume()


# -- Path 13: the sketch edited, its hole follows -----------------------------------------------
def p13_edit_sketch():
    sk = doc().getObject(s.get("sketch", ""))
    if sk is not None:
        ti.double_click_row(sk.Label)


def p13_move_point():
    sk = h.in_sketch()
    h.check("P13 the sketch is open", sk is not None and sk.Name == s.get("sketch"))
    if sk is None:
        return
    # The person drags the second point 4 mm to the left.
    x, y = h.to_sketch(sk, Q2 - V(4, 0, 0))
    for i, geo in enumerate(sk.Geometry):
        if geo.TypeId == "Part::GeomPoint":
            p = V(geo.X, geo.Y, 0)
            if (sk.getGlobalPlacement().multVec(p) - Q2).Length < 1e-6:
                sk.moveGeometry(i, 1, V(x, y, 0))
    doc().recompute()


def p13_finish():
    h.ribbon("Finish Sketch")


def p13_done():
    hl = [x for x in hs.holes() if x.Profile and x.Profile[0].Name == s.get("sketch")]
    spots = hs.centres_all(hl[0]) if hl else []
    moved = any(hs.vnear(c, Q2 - V(4, 0, 0), 1e-6) for c in spots)
    h.check("P13 the hole followed the point", moved and len(spots) == 2, spots)
    h.check("P13 same volume", hs.close(h.solid_volume(), s["v"]), h.solid_volume())
    sk = doc().getObject(s.get("sketch", ""))
    h.check("P13 the sketch is hidden again", sk is not None and not hs.visible(sk))
    part_ok("P13")


# -- Path 14: a hole inserted with the marker rolled back ---------------------------------------
def p14_roll():
    s["titles"] = hs.timeline_titles()
    ti.drag_marker(before_title="Press Pull 1")


def p14_rolled():
    v = h.solid_volume()
    expect = 40 * 30 * 14 + boss() - hs.cylinder(5, 14 + BOSS_H)
    h.check("P14 rolled back before the Press Pull", hs.close(v, expect), (v, expect))
    h.press("h")


def p14_click():
    h.fit()
    h.click(V(34, 6, 14))


def p14_place():
    p = panel()
    h.check("P14 a hole in the rolled-back part", p is not None and p.target is not None, msg())
    if p:
        b.choose(p.extent, "Distance")
        hs.type_into(p.pos_x.widget, "34")
        hs.type_into(p.pos_y.widget, "6")
        hs.type_into(p.diameter.widget, "4")
        hs.type_into(p.depth.widget, "5")
        b.choose(p.drill_point, "Flat")


def p14_ok():
    h.task_button("OK")


def p14_inserted():
    titles = hs.timeline_titles()
    h.check(
        "P14 the new hole sits before the Press Pull",
        "Hole 3" in titles
        and "Press Pull 1" in titles
        and titles.index("Hole 3") < titles.index("Press Pull 1"),
        titles,
    )
    ti.drag_marker(to_end=True)


def p14_end():
    v = h.solid_volume()
    expect = s["v"] - hs.cylinder(4, 5)
    h.check("P14 at the end: everything plus the new hole", hs.close(v, expect), (v, expect))
    part_ok("P14")
    s["v"] = v
    h.shot("p14-inserted")


# -- Path 15: a modeled thread on the boss, then the boss made taller ---------------------------
SIDE = V(20 + BOSS_R * math.cos(math.radians(-60)), 15 + BOSS_R * math.sin(math.radians(-60)), 18)


def p15_thread():
    Gui.Selection.clearSelection()
    si.menu_item("CREATE", "Thread")


def p15_click():
    h.fit()
    h.click(SIDE)


def p15_modeled():
    p = hs.thread_panel()
    h.check("P15 the boss side is picked", p is not None and len(p.faces) == 1, msg())
    h.check(
        "P15 M12x1.75 from the d12 boss",
        p is not None and p.designation.currentText() == "M12x1.75",
        p and p.designation.currentText(),
    )
    if p:
        hs.click_checkbox(p.modeled)


p15_modeled.wait_ms = 2500


def p15_ok():
    h.task_button("OK")


p15_ok.wait_ms = 2500


def removed(length):
    from sciforge import thread_core

    from sciforge import thread_tables

    # a modeled thread lies in the middle of its class's zone (6g on a shaft)
    d = thread_tables.find("iso", "M12x1.75")
    return thread_core.class_removed_volume(d, "6g", False, BOSS_R, length)


def p15_done():
    h.check("P15 closed", not dialog_open())
    v = h.solid_volume()
    expect = s["v"] - removed(BOSS_H)
    h.check("P15 the modeled thread runs the boss's length", hs.close(v, expect, 1e-5), (v, expect))
    part_ok("P15")
    s["v"] = v
    b.timeline_double_click("Extrude 2", click_first=True)


def p15_taller():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    h.check("P15 editing the boss's Extrude", p is not None and p.editing and not p._closed)
    if p:
        hs.type_into(p.distance.widget, "10")


# The preview rebuilds the modeled thread (a second or two): a person waits for the busy
# cursor before clicking OK (FreeCAD swallows clicks meanwhile, a test's timer does not).
p15_taller.wait_ms = 4000


def p15_taller_ok():
    h.task_button("OK")


p15_taller_ok.wait_ms = 3000


def p15_followed():
    v = h.solid_volume()
    # Boss 2 higher: 2 more of the boss, 2 more of the through hole, 2 more of thread.
    expect = s["v"] + boss(2.0) - hs.cylinder(5, 2.0) - removed(2.0)
    h.check(
        "P15 the thread and the hole follow the taller boss", hs.close(v, expect, 1e-5), (v, expect)
    )
    part_ok("P15 after the edit")
    h.check("P15 no kernel errors in the Report view", not b.report_has_kernel_errors())
    hs.no_popups("a part of many steps")
    h.shot("p15-end")


h.run(
    "hole_qa_part",
    ti.watched(
        b.box_steps("HoleQAPart")
        + hs.make_boss("boss", radius=BOSS_R, height=BOSS_H, at=(20.0, 15.0))
        + [
            p9_h,
            p9_click_boss,
            p9_place,
            p9_preview,
            p9_done,
            p10_q,
            p10_face,
            p10_distance,
            p10_ok,
            p10_done,
            p11_edit,
            p11_taller,
            p11_ok,
            p11_done,
            p12_sketch,
            p12_top,
            p12_points,
            p12_finish,
            p12_select,
            p12_h,
            p12_both,
            p12_ok,
            p12_done,
            p13_edit_sketch,
            p13_move_point,
            p13_finish,
            p13_done,
            p14_roll,
            p14_rolled,
            p14_click,
            p14_place,
            p14_ok,
            p14_inserted,
            p14_end,
            p15_thread,
            p15_click,
            p15_modeled,
            p15_ok,
            p15_done,
            p15_taller,
            p15_taller_ok,
            p15_followed,
        ]
    ),
)
