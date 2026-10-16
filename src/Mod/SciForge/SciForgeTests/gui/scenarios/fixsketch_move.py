# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sketching on a part after Move/Copy (Luca, 2026-10-16: "sketching on an edited object
will revert it to a previous state, making it impossible to sketch on edited faces"). Only
real input; fixsketch_steps has the shared steps and why.

Block 40 x 30 x 10 (Create Sketch, XY, rectangle, Finish, E, 10, OK).
  A  M, click the part, X Distance 10, OK: the part at x 10..50. Create Sketch on its top:
     the part stays drawn where it is now (before: drawn back at x 0..40 while sketching,
     the step before the move). The sketch hangs on the Move step: the top moved with the
     part, though it is still in the plane z 10. A circle r 2 at x 43, E, 5, OK.
  B  Double-click the Move in the timeline, Z Distance 5, OK: the part is lifted to z 5..15
     and the boss came along (its top at z 20): one solid (before: the sketch hung on the
     top before the move and stayed at z 10, the boss sank into the part).
  C  Ctrl+Z: the part at z 0..10, the boss top at 15; Ctrl+Y: lifted again.
  D  M, click the part, Create Copy, X Distance 60, OK: a copy at x 70..110. Create Sketch
     on the copy's top: the sketch goes in the copy's body (it hangs on the copy's own first
     step), both parts stay drawn as they are; a circle r 2, E, 3, OK: the copy gets a boss,
     the original is unchanged.

Hand-derived: block 12000; a boss r x d adds pi r^2 d (r as drawn).
"""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import bodies_steps as bst
from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import fixsketch_steps as fs
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}


def grid():
    fs.one_mm_grid()
    s["block"] = h.body().Tip.Name
    s["original"] = h.body().Name


def original():
    return App.ActiveDocument.getObject(s["original"])


def moves():
    return bst.steps_of_kind("MoveCopy")


def dx_field(p):
    return p.distance_fields[0].widget


def boss_top():
    """(x, z) of the centre of the round edge at the top of A's boss (the highest one)."""
    found = [
        edge.Curve.Center
        for edge in original().Shape.Edges
        if edge.Curve.TypeId == "Part::GeomCircle"
    ]
    if not found:
        return None
    top = max(found, key=lambda c: c.z)
    return top.x, top.z


def boss_at(where, z):
    top = boss_top()
    h.check(
        "%s: the boss on the part, its top at x 43, z %g" % (where, z),
        top is not None and abs(top[0] - 43) < 1e-6 and abs(top[1] - z) < 1e-6,
        top,
    )
    h.check(
        "%s: one solid with the boss" % where,
        fs.solids(original()) == 1 and fs.close(fs.volume(original()), s["with_boss"]),
        (fs.solids(original()), fs.volume(original()), s["with_boss"]),
    )


# -- A --------------------------------------------------------------------------------------
def move():
    Gui.Selection.clearSelection()
    h.click_empty()
    h.fit()
    h.press("m")


def move_pick():
    h.click(V(20, 15, 10))


def move_type():
    p = bst.panel()
    if h.check("A: Move/Copy picked the part", p is not None and p.options["bodies"]):
        bst.type_value(dx_field(p), "10")


def move_ok():
    h.task_button("OK")


def moved():
    box = original().Shape.BoundBox
    h.check("A: the part at x 10..50", abs(box.XMin - 10) < 1e-6 and abs(box.XMax - 50) < 1e-6)
    h.check("A: one Move step", len(moves()) == 1, moves())
    s["move"] = moves()[0].Name if moves() else None


# -- B --------------------------------------------------------------------------------------
def edit_move():
    s["with_boss"] = fs.volume(original())
    h.click_empty()
    bst.timeline_double_click(App.ActiveDocument.getObject(s["move"]))


def edit_type():
    p = bst.panel()
    if h.check("B: the Move opens for editing", p is not None and p.editing, p):
        bst.type_value(p.distance_fields[2].widget, "5")


def edit_ok():
    h.task_button("OK")


def edited():
    box = original().Shape.BoundBox
    h.check("B: the part lifted to z 5", abs(box.ZMin - 5) < 1e-6, (box.ZMin, box.ZMax))
    boss_at("B", 20)
    fs.no_errors_in_design("B")
    h.shot("B-lifted")


# -- C --------------------------------------------------------------------------------------
def undo():
    bst.undo()


def undone():
    h.check("C: Ctrl+Z: the part at z 0", abs(original().Shape.BoundBox.ZMin) < 1e-6)
    boss_at("C, Ctrl+Z", 15)


def redo():
    bst.redo()


def redone():
    boss_at("C, Ctrl+Y", 20)
    fs.no_errors_in_design("C")


# -- D --------------------------------------------------------------------------------------
def copy():
    s["original_volume"] = fs.volume(original())
    Gui.Selection.clearSelection()
    h.click_empty()
    h.fit()
    h.press("m")


def copy_pick():
    h.click(V(20, 10, 15))


def copy_options():
    p = bst.panel()
    if h.check("D: Move/Copy picked the part", p is not None and p.options["bodies"]):
        bst.toggle(p.copy)
        bst.type_value(dx_field(p), "60")


def copy_ok():
    h.task_button("OK")


def copied():
    found = bst.bodies()
    h.check("D: two bodies", len(found) == 2, [x.Label for x in found])
    others = [x for x in found if x.Name != s["original"]]
    if others:
        s["copy"] = others[0].Name
        box = others[0].Shape.BoundBox
        h.check("D: the copy at x 70..110", abs(box.XMin - 70) < 1e-6, (box.XMin, box.XMax))
    h.fit()


def copy_body():
    return App.ActiveDocument.getObject(s["copy"])


def original_kept():
    body = original()
    h.check(
        "D: the original is drawn as it is",
        fs.shown_steps(body) == [body.Tip.Name],
        fs.shown_steps(body),
    )
    h.check(
        "D: the original is unchanged",
        fs.close(fs.volume(body), s["original_volume"]),
        (fs.volume(body), s["original_volume"]),
    )
    h.check(
        "D: the sketch hangs on a step of the copy's body",
        fs.body_of(fs.obj(s["support"])) is copy_body(),
        s.get("support"),
    )


steps = b.box_steps("FixSketchMove") + [grid, move, move_pick, move_type, move_ok, moved]
steps += fs.sketch_on("A", V(35, 15, 10), s, support=(lambda st: s["move"], "the face moved"))
steps += fs.circle("A", V(43, 15, 10), 2, s)
steps += fs.finish_and_extrude("A", 5, s)
steps += [edit_move, edit_type, edit_ok, h.idle_step("wait_edit"), edited]
steps += [undo, h.idle_step("wait_undo"), undone, redo, h.idle_step("wait_redo"), redone]
steps += [copy, copy_pick, copy_options, copy_ok, h.idle_step("wait_copy"), copied]
steps += fs.sketch_on("D", V(85, 15, 15), s, body_after=copy_body)
steps += [original_kept]
steps += fs.circle("D", V(85, 15, 15), 2, s)
steps += fs.finish_and_extrude("D", 3, s)
steps += [original_kept]

h.run("fixsketch_move", steps)
