# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sketching on faces Offset Face and Press Pull changed, then saving and opening the design
again (Luca, 2026-10-16: "sketching on an edited object will revert it to a previous state,
making it impossible to sketch on edited faces"). Only real input; fixsketch_steps has the
shared steps and why.

Block 40 x 30 x 10 (Create Sketch, XY, rectangle, Finish, E, 10, OK).
  A  MODIFY > Offset Face, the top, 2, OK: 40 x 30 x 12. Create Sketch on the top: the
     sketch hangs on the Offset Face step (the face moved there); a circle r 5, E, 5, OK.
  B  Q, the right side face, 10, OK: the part is 50 long. Create Sketch on the top where
     Press Pull made it longer (x 45): the sketch hangs on the Offset Face's top (the same
     face), the part stays drawn 50 long with A's boss (before: it went back to the Offset
     Face step, 40 long and without the boss, so the clicked spot was not even on the part
     any more). A circle r 2 there, E, 4, OK.
  C  Ctrl+Z: B's boss goes, the part is drawn with every edit; Ctrl+Y: back.
  D  Save, close, open again: the same part. Create Sketch on the top again: drawn with
     every edit; a circle r 2, E, 3, OK.
  E  Double-click B's sketch in the timeline (after reopening): the design is drawn as it is
     at the sketch: the Press Pull, without B's boss and what came after; Finish Sketch.

Hand-derived: 40*30*12 = 14400; Press Pull adds 10*30*12 = 3600; a boss r x d adds
pi r^2 d (r as drawn).
"""

import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import direct_steps as d
from SciForgeTests.gui import fixsketch_steps as fs
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}


def grid():
    fs.one_mm_grid()
    s["block"] = h.body().Tip.Name


# -- A --------------------------------------------------------------------------------------
def offset_face():
    Gui.Selection.clearSelection()
    h.click_empty()
    h.fit()
    d.ribbon_menu("MODIFY", "Offset Face")


def offset_pick():
    p = d.panel()
    h.check("A: Offset Face dialog", p is not None and p.title == "Offset Face", p)
    h.click(V(20, 15, 10))


def offset_type():
    d.type_distance("2")


def offset_ok():
    h.task_button("OK")


def offset_done():
    v = h.solid_volume()
    h.check("A: 40 x 30 x 12", fs.close(v, 14400.0), v)
    s["offset"] = h.body().Tip.Name
    h.check(
        "A: an Offset Face step",
        getattr(h.body().Tip, "SciForgeType", "") == "OffsetFace",
        h.body().Tip.Name,
    )


# -- B --------------------------------------------------------------------------------------
def press_pull():
    s["before_pp"] = h.solid_volume()
    Gui.Selection.clearSelection()
    h.click_empty()
    h.fit()
    h.press("q")


def pp_pick():
    h.click(V(40, 15, 5))


def pp_type():
    p = d.press_pull_panel()
    h.check("B: the side face picked", p is not None and len(p.names) == 1, p and p.names)
    d.type_distance("10")


def pp_ok():
    h.task_button("OK")


def pp_done():
    v = h.solid_volume()
    expect = s["before_pp"] + 3600.0
    h.check("B: Press Pull made it 50 long", fs.close(v, expect), (v, expect))
    s["presspull"] = h.body().Tip.Name
    h.check("B: 50 long", abs(h.body().Shape.BoundBox.XLength - 50) < 1e-6)


# -- D --------------------------------------------------------------------------------------
def save():
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-fixsketch-"), "edited.FCStd")
    s["path"] = path
    s["saved_volume"] = h.solid_volume()
    App.ActiveDocument.saveAs(path)
    h.check("D: saved", os.path.isfile(path), path)


def close():
    App.closeDocument(App.ActiveDocument.Name)


def reopen():
    App.openDocument(s["path"])
    h.fit()


def reopened():
    v = h.solid_volume()
    h.check("D: the same part after reopening", fs.close(v, s["saved_volume"]), v)
    body = h.body()
    h.check(
        "D: drawn as it is (the last step)",
        fs.shown_steps(body) == [body.Tip.Name],
        fs.shown_steps(body),
    )
    fs.no_errors_in_design("D, reopened")


steps = b.box_steps("FixSketchPressPull") + [grid]
steps += [offset_face, offset_pick, offset_type, offset_ok, offset_done]
steps += fs.sketch_on("A", V(25, 15, 12), s, support=(lambda st: s["offset"], "the face moved"))
steps += fs.circle("A", V(25, 15, 12), 5, s)
steps += fs.finish_and_extrude("A", 5, s)
steps += [press_pull, pp_pick, pp_type, pp_ok, pp_done]
steps += fs.sketch_on("B", V(45, 15, 12), s, support=(lambda st: s["offset"], "the same face"))
steps += fs.circle("B", V(45, 15, 12), 2, s)
steps += fs.finish_and_extrude("B", 4, s)
steps += fs.undo_redo("C", "B", s)
steps += [save, close, reopen, h.idle_step("wait_reopen"), reopened]
steps += fs.sketch_on("D", V(35, 25, 12), s)
steps += fs.circle("D", V(35, 25, 12), 2, s)
steps += fs.finish_and_extrude("D", 3, s)
steps += fs.edit_later("E", "B", s)

h.run("fixsketch_presspull", steps)
