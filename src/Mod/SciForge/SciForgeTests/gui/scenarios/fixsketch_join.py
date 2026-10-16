# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sketching on faces after the first extrude was edited and a later extrude joined the part
(Luca, 2026-10-16: "sketching on an edited object will revert it to a previous state, making
it impossible to sketch on edited faces"). Only real input; fixsketch_steps has the shared
steps and why.

Block 40 x 30 x 10 (Create Sketch, XY, rectangle, Finish, E, 10, OK).
  A  Double-click Extrude 1 in the timeline, 15, OK: 40 x 30 x 15. Create Sketch on the top,
     a circle r 5, E, 5, OK: a boss.
  B  Create Sketch on XY, a rectangle x 40..60, Finish, E, 15, OK: it joins the part, the top
     is one face 60 long. Create Sketch on the top where the join made it (x 55): the
     sketch hangs on the first extrude's top (the same face), the part stays drawn 60 long
     with A's boss (before: it went back to the first extrude, 40 long, without the boss,
     and the clicked spot was off the part). A circle r 2 there, E, 5, OK.
  C  Create Sketch on the front face where the join made it (x 55): drawn as it is; a
     circle r 2, E, 3, OK: a boss out of the front.
  D  Ctrl+Z: C's boss goes, the part is drawn with every edit; Ctrl+Y: back.
  E  Double-click B's sketch in the timeline: the design is drawn as it is at the sketch:
     with the join, without B's boss and what came after; Finish Sketch.

Hand-derived: 40*30*15 = 18000; the join adds 20*30*15 = 9000; a boss r x d adds pi r^2 d
(r as drawn).
"""

import FreeCAD as App

from SciForgeTests.gui import bodies_steps as bst
from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import fixsketch_steps as fs
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl

V = App.Vector
s = {}


def grid():
    fs.one_mm_grid()
    s["block"] = h.body().Tip.Name


# -- A --------------------------------------------------------------------------------------
def edit_first():
    h.click_empty()
    bst.timeline_double_click(App.ActiveDocument.getObject(s["block"]))


def edit_distance():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    if h.check("A: Extrude 1 opens for editing", p is not None and not p._closed, p):
        ui.type_into(p.distance.widget, "15")


def edit_ok():
    h.task_button("OK")


def edited():
    v = h.solid_volume()
    h.check("A: the first extrude is 15 now", fs.close(v, 18000.0), v)
    h.check("A: still one step", h.body().Tip.Name == s["block"], h.body().Tip.Name)


# -- B --------------------------------------------------------------------------------------
def join_sketch():
    s["before_join"] = h.solid_volume()
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def join_plane():
    pl.click_square("XY_Plane")  # where the square shows (was 12, -8, 0)


def join_draw():
    sk = h.in_sketch()
    if h.check("B: sketch open on XY", sk is not None):
        h.draw_rectangle(sk, 40, 0, 60, 30)


def join_finish():
    h.ribbon("Finish Sketch")


def join_extrude():
    h.fit()
    h.press("e")


def join_distance():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    if h.check("B: Extrude open", p is not None):
        ui.type_into(p.distance.widget, "15")


def join_ok():
    h.task_button("OK")


def joined():
    v = h.solid_volume()
    expect = s["before_join"] + 9000.0
    h.check("B: the join made the part 60 long", fs.close(v, expect), (v, expect))
    h.check("B: one solid", fs.solids(h.body()) == 1)
    s["join"] = h.body().Tip.Name
    h.fit()


steps = b.box_steps("FixSketchJoin") + [grid, edit_first, edit_distance, edit_ok, edited]
steps += fs.sketch_on("A", V(25, 15, 15), s, support=(lambda st: s["block"], "the first extrude"))
steps += fs.circle("A", V(25, 15, 15), 5, s)
steps += fs.finish_and_extrude("A", 5, s)
steps += [join_sketch, join_plane, join_draw, join_finish, join_extrude, join_distance]
steps += [join_ok, joined]
steps += fs.sketch_on("B", V(55, 15, 15), s, support=(lambda st: s["block"], "the same face"))
steps += fs.circle("B", V(55, 15, 15), 2, s)
steps += fs.finish_and_extrude("B", 5, s)
steps += fs.sketch_on("C", V(55, 0, 7), s)
steps += fs.circle("C", V(55, 0, 7), 2, s)
steps += fs.finish_and_extrude("C", 3, s)
steps += fs.undo_redo("D", "C", s)
steps += fs.edit_later("E", "B", s)

h.run("fixsketch_join", steps)
