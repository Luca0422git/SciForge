# SPDX-License-Identifier: LGPL-2.1-or-later
"""Patterns of several features, of faces, and of bodies on a real part (QA, only real input).

Path 14, a boss with a hole in it (two steps), picked in the "wrong" order: the hole first (a
         click on its wall), then the boss in the timeline. Patterned together along -X, the
         copy has its hole too (before, the steps were repeated in the order they were picked,
         so the copied boss filled its own hole).
Path 15, a Faces pattern of a hole's wall, then the hole made shallower from the timeline:
         the copies follow (they are faces of the step before the pattern).
Path 16, a fillet's round face alone as Faces: the dialog says why it cannot be repeated in
         plain words (before: "<unknown exception data>", OpenCASCADE's own text). Cancel.
Path 17, a pattern of the body (new bodies), then the copied body deleted in the browser:
         the copies stay and the pattern step says in plain words why it keeps them, as a
         warning, not red (before 2026-10-16 it failed; earlier still: a Python
         AttributeError from the copies); Ctrl+Z brings the body back and the step is fine.

Hand-derived: box 40 x 30 x 10 = 12000; boss r 4 x 4 = 64 pi; hole r 1.5 through the boss
(4 deep) = 9 pi; a through hole r 2 in the box = 40 pi, 5 deep = 20 pi.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import pattern_steps as ps
from SciForgeTests.gui import widget_input as w

V = App.Vector
s = {}
R = 2.0
HOLE = ps.hole(R)
BOSS = math.pi * 16.0 * 4.0
BOSS_HOLE = math.pi * 2.25 * 4.0


def doc():
    return App.ActiveDocument


def message():
    p = ps.panel()
    return p.message.text() if p is not None else ""


def broken():
    return [o.Label for o in doc().Objects if set(o.State) & {"Invalid", "Error"}]


# -- the boss with its hole --------------------------------------------------------------------------
def boss_hole_sketch():
    h.fit()
    h.ribbon("Create Sketch")


def boss_hole_top():
    h.click(V(31.5, 14, 14))  # the boss's top face, beside where the hole goes


def boss_hole_circle():
    sk = h.in_sketch()
    h.check("sketch on the boss's top", sk is not None)
    if sk is not None:
        x, y = h.to_sketch(sk, V(30, 15, 14))
        h.draw_circle(sk, x, y, 1.5)


def boss_hole_finish():
    h.ribbon("Finish Sketch")


def boss_hole_extrude():
    s["v"] = h.solid_volume()
    h.fit()
    h.press("e")


def boss_hole_depth():
    b.type_into(b.active_panel().distance.widget, "-4")


def boss_hole_ok():
    h.task_button("OK")


def boss_hole_made():
    h.check("hole in the boss", ps.close(h.solid_volume(), s["v"] - BOSS_HOLE), h.solid_volume())
    s["v"] = h.solid_volume()


# -- Path 14: two steps patterned together --------------------------------------------------------------
def p14_start():
    Gui.Selection.clearSelection()
    h.ribbon("Rectangular Pattern")


def p14_boss_in_timeline():
    ps.timeline_click("Extrude 3")


def p14_hole_face():
    h.fit()
    # the far wall of the small hole in the boss (seen from the iso view)
    h.click(V(30 - 1.5 * 0.7071, 15 + 1.5 * 0.7071, 13.5))


def p14_both():
    p = ps.panel()
    names = [o.Label for o, _sub in p.options["objects"]] if p else []
    h.check("the boss and its hole are the objects", len(names) == 2, (names, message()))
    h.check(
        "the list names both steps",
        p and "Extrude 3" in p.objects_label.text() and "Extrude 4" in p.objects_label.text(),
        p and p.objects_label.text(),
    )
    ps.click_box("direction")


def p14_axis():
    h.fit()
    pl.click_on_plane(V(-12, 0, 0))


def p14_values():
    p = ps.panel()
    b.choose(p.distribution, "Spacing")


def p14_distance():
    ps.type_value(ps.panel().distance_field.widget, "-12")


def p14_preview():
    v = h.solid_volume()
    h.check("a copy of the boss with its hole", ps.close(v, s["v"] + BOSS - BOSS_HOLE), v)
    tops = ps.circle_centres(h.body().Shape, 4.0, z=14)
    h.check("bosses at x = 30 and 18", tops == [(18, 15), (30, 15)], tops)
    holes = ps.circle_centres(h.body().Shape, 1.5, z=14)
    h.check("each with its hole", holes == [(18, 15), (30, 15)], holes)
    h.shot("14-two-features")
    h.task_button("OK")


def p14_done():
    found = ps.patterns()
    h.check("one pattern step", len(found) == 1)
    h.check(
        "FreeCAD's pattern with both steps",
        found and found[0].TypeId == "PartDesign::LinearPattern" and len(found[0].Originals) == 2,
        found and (found[0].TypeId, found[0].Originals),
    )
    s["v"] = h.solid_volume()


# -- Path 15: a Faces pattern follows the hole it copies ------------------------------------------------
def p15_wall():
    Gui.Selection.clearSelection()
    h.fit()
    h.click(V(8 - R * 0.7071, 8 + R * 0.7071, 9))


def p15_start():
    sel = ps.selection()
    h.check(
        "the hole's wall is selected", sel and sel[0][1] and sel[0][1][0].startswith("Face"), sel
    )
    h.ribbon("Rectangular Pattern")


def p15_axis():
    p = ps.panel()
    h.check("Pattern Type Faces", p and p.pattern_type.currentText() == "Faces")
    h.fit()
    pl.click_on_plane(V(0, -12, 0))


def p15_distance():
    ps.type_value(ps.panel().distance_field.widget, "14")


def p15_ok():
    h.check("a copy of the hole", ps.close(h.solid_volume(), s["v"] - HOLE), h.solid_volume())
    h.task_button("OK")


def p15_edit_hole():
    s["v"] = h.solid_volume()
    ps.timeline_double_click("Extrude 2")


def p15_shallower():
    p = b.active_panel()
    field = getattr(getattr(p, "distance", None), "widget", None)
    if h.check("the hole opens to edit", field is not None):
        b.type_into(field, "-5")


def p15_shallower_ok():
    h.task_button("OK")


p15_shallower_ok.wait_ms = 1500


def p15_followed():
    # The hole and its copy are 5 deep now: each removes 20 pi instead of 40 pi.
    want = s["v"] + 2 * (HOLE - ps.hole(R, 5.0))
    h.check(
        "the copy follows the shallower hole", ps.close(h.solid_volume(), want), h.solid_volume()
    )
    h.check("nothing broken", not broken(), broken())
    s["v"] = h.solid_volume()


# -- Path 16: a fillet's round face as Faces ------------------------------------------------------------
def p16_fillet():
    Gui.Selection.clearSelection()
    h.ribbon("Fillet")


def p16_edge():
    h.fit()
    h.click_edge(V(20, 0, 10))


def p16_radius():
    p = b.blend_panel()
    if h.check("Fillet dialog", p is not None):
        b.type_into(p.radius.widget, "2")


def p16_fillet_ok():
    h.task_button("OK")


def p16_pattern():
    s["v"] = h.solid_volume()
    Gui.Selection.clearSelection()
    h.ribbon("Rectangular Pattern")


def p16_faces_type():
    b.choose(ps.panel().pattern_type, "Faces")


def p16_round_face():
    h.fit()
    a = math.radians(45)
    h.click(V(20, 2 - 2 * math.cos(a), 8 + 2 * math.sin(a)))


def p16_box():
    p = ps.panel()
    objs = p.options["objects"] if p else []
    h.check("the round face is picked", len(objs) == 1 and objs[0][1].startswith("Face"), objs)
    ps.click_box("direction")


def p16_axis():
    h.fit()
    pl.click_on_plane(V(0, -12, 0))


def p16_said():
    text = message()
    h.check("the reason in plain words", "do not close up" in text, text)
    h.check("no kernel jargon", "unknown exception" not in text, text)
    h.check("the part is as it was", ps.close(h.solid_volume(), s["v"]), h.solid_volume())
    h.task_button("OK")


def p16_ok_waits():
    h.check("OK waits", ps.panel() is not None)
    h.task_button("Cancel")


def p16_cancelled():
    h.check(
        "Cancel: unchanged", ps.close(h.solid_volume(), s["v"]) and not Gui.Control.activeDialog()
    )


# -- Path 17: a pattern of the body, the body deleted -----------------------------------------------------
def p17_start():
    Gui.Selection.clearSelection()
    h.ribbon("Rectangular Pattern")


def p17_bodies():
    b.choose(ps.panel().pattern_type, "Bodies")


def p17_part():
    h.fit()
    h.click(V(30, 25, 10))


def p17_box():
    ps.click_box("direction")


def p17_axis():
    h.fit()
    pl.click_on_plane(V(-12, 0, 0))


def p17_spacing():
    b.choose(ps.panel().distribution, "Spacing")


def p17_distance():
    ps.type_value(ps.panel().distance_field.widget, "50")


def p17_ok():
    h.task_button("OK")


p17_ok.wait_ms = 1500


def p17_delete_body():
    h.check("two bodies", len(ps.bodies()) == 2, [x.Label for x in ps.bodies()])
    from sciforge import browser_ui

    t = browser_ui.widget()
    t.refresh()
    item = t.row("Body")
    if h.check("the body in the browser", item is not None, t.labels()):
        h.check("Delete in its menu", w.right_click(t.viewport(), t.label_point(item), "Delete"))


p17_delete_body.wait_ms = 2000


def p17_said():
    from sciforge import timeline_ops

    steps = [o for o in doc().Objects if getattr(o, "SciForgeType", "") == "RectangularPattern"]
    h.check("the pattern step is still there", len(steps) == 1, steps)
    if steps:
        kind, why = timeline_ops.problem(steps[0])
        h.check(
            "it says why, as a warning (the copies stay)",
            kind == "warning" and "was deleted" in why,
            (kind, why),
        )
        h.check("no Python jargon", "Error" not in why and "NoneType" not in why, why)
        h.check("the copy body stays", len(ps.bodies()) == 1, [x.Label for x in ps.bodies()])
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


p17_said.wait_ms = 1500


def p17_back():
    h.check("Ctrl+Z: the body is back", len(ps.bodies()) == 2, [x.Label for x in ps.bodies()])
    h.check("nothing broken", not broken(), broken())


h.run(
    "patterns_qa_features",
    b.box_steps("PatternQAFeatures")
    + ps.make_cut("hole", (8, 8), R)
    + ps.make_boss("boss", (30, 15), 4, 4, V(36, 4, 10))
    + [
        boss_hole_sketch,
        boss_hole_top,
        boss_hole_circle,
        boss_hole_finish,
        boss_hole_extrude,
        boss_hole_depth,
        boss_hole_ok,
        boss_hole_made,
        p14_start,
        p14_hole_face,
        p14_boss_in_timeline,
        p14_both,
        p14_axis,
        p14_values,
        p14_distance,
        p14_preview,
        p14_done,
        p15_wall,
        p15_start,
        p15_axis,
        p15_distance,
        p15_ok,
        p15_edit_hole,
        p15_shallower,
        p15_shallower_ok,
        p15_followed,
        p16_fillet,
        p16_edge,
        p16_radius,
        p16_fillet_ok,
        p16_pattern,
        p16_faces_type,
        p16_round_face,
        p16_box,
        p16_axis,
        p16_said,
        p16_ok_waits,
        p16_cancelled,
        p17_start,
        p17_bodies,
        p17_part,
        p17_box,
        p17_axis,
        p17_spacing,
        p17_distance,
        p17_ok,
        p17_delete_body,
        p17_said,
        p17_back,
    ],
)
