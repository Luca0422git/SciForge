# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sketching on faces a Shell and a Draft changed (Luca, 2026-10-16: "sketching on an edited
object will revert it to a previous state, making it impossible to sketch on edited
faces"). Only real input; fixsketch_steps has the shared steps and why.

Block 40 x 30 x 10 (Create Sketch, XY, rectangle, Finish, E, 10, OK).
  A  Shell, the front face, OK (1 mm inside): an open box. Create Sketch on the top (the top
     wall): the part stays drawn hollow (before: drawn as the solid block while sketching).
     A circle r 5, E, 5, OK: a boss on the top wall.
  B  Ctrl+Z: the boss goes, the part is drawn hollow; Ctrl+Y: back.
  C  Double-click A's sketch in the timeline: the design as it is at the sketch: the shell,
     without the boss; Finish Sketch.
  D  A second design, the same block. MODIFY > Draft, the XY square, the front face, 5, OK:
     the front leans in, the top is narrower. Create Sketch on the top: drawn drafted; a
     circle r 5, E, 4, OK.

Hand-derived: a boss r x d adds pi r^2 d (r as drawn); the shell and the draft are measured
before the sketch (their volumes are checked by their own scenarios).
"""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import fixsketch_steps as fs
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import shell_draft_steps as sd

V = App.Vector
s = {}
s2 = {}


def grid():
    fs.one_mm_grid()
    s["block"] = h.body().Tip.Name


# -- A --------------------------------------------------------------------------------------
def shell():
    Gui.Selection.clearSelection()
    h.click_empty()
    h.fit()
    h.ribbon("Shell")


def shell_pick():
    h.click(V(20, 0, 5))


def shell_ok():
    h.task_button("OK")


def shelled():
    v = h.solid_volume()
    expect = 12000.0 - 38 * 29 * 8
    h.check("A: an open box, 1 mm walls", fs.close(v, expect), (v, expect))
    s["shell"] = h.body().Tip.Name


# -- D --------------------------------------------------------------------------------------
def draft():
    s2["extrude"] = h.body().Tip.Name
    Gui.Selection.clearSelection()
    h.click_empty()
    h.fit()
    sd.modify_menu("Draft")


def draft_plane():
    h.click(V(12, -8, 0))


def draft_face():
    h.fit()
    h.click(V(20, 0, 5))


def draft_angle():
    p = sd.draft_panel()
    if h.check("D: the front face picked", p is not None and len(p.names()) == 1):
        sd.type_into(p.angle.widget, "5")


def draft_ok():
    h.task_button("OK")


def drafted():
    v = h.solid_volume()
    h.check("D: the front leans in", v < 12000.0 - 10.0, v)
    s2["draft"] = h.body().Tip.Name
    h.fit()


steps = b.box_steps("FixSketchShell") + [grid, shell, shell_pick, shell_ok, shelled]
steps += fs.sketch_on("A", V(25, 15, 10), s, support=(lambda st: s["block"], "the first extrude"))
steps += fs.circle("A", V(25, 15, 10), 5, s)
steps += fs.finish_and_extrude("A", 5, s)
steps += fs.undo_redo("B", "A", s)
steps += fs.edit_later("C", "A", s)
steps += b.box_steps("FixSketchDraft") + [draft, draft_plane, draft_face, draft_angle]
steps += [draft_ok, drafted]
steps += fs.sketch_on(
    "D", V(25, 15, 10), s2, support=(lambda st: s2["extrude"], "the first extrude")
)
steps += fs.circle("D", V(25, 15, 10), 5, s2)
steps += fs.finish_and_extrude("D", 4, s2)

h.run("fixsketch_shell_draft", steps)
