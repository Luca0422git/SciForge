# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sketching on a face with a hole in it (Luca, 2026-10-16: "sketching on an edited object
will revert it to a previous state, making it impossible to sketch on edited faces"), and
the hole QA's rule kept: a sketch on a face the first extrude made does not depend on a
later, unrelated step. Only real input; fixsketch_steps has the shared steps and why.

Block 40 x 30 x 10 (Create Sketch, XY, rectangle, Finish, E, 10, OK).
  A  Hole, click the top at (10, 10), OK (5 mm through). Create Sketch on the top: the
     sketch hangs on the block's top (the first extrude), and the part stays drawn with its
     hole (before: drawn without it, so its edge could not be used). P, click the hole's
     edge: it is projected into the sketch (from the step that has it). Finish Sketch.
  B  Create Sketch on the top again, a circle r 5, E, 5, OK: a boss on the drilled block.
  C  Ctrl+Z: the boss goes, drawn with the hole; Ctrl+Y: back.
  D  Suppress the hole in the timeline: B's sketch and boss stay (they hang on the block's
     top); A's sketch goes with the hole (it uses the hole's edge, and SciForge's suppress
     takes what uses a step along). Unsuppress: as before.
  E  Double-click B's sketch in the timeline: drawn as it is at the sketch: with the hole,
     without the boss; Finish Sketch.

Hand-derived: a hole d 5 through 10 removes pi 6.25 10; a boss r x d adds pi r^2 d (r as
drawn).
"""

import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import fixsketch_steps as fs
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import hole_steps as hs
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import widget_input as w

V = App.Vector
s = {}
HOLE = math.pi * 2.5**2 * 10


def grid():
    fs.one_mm_grid()
    s["block"] = h.body().Tip.Name


# -- A --------------------------------------------------------------------------------------
def hole():
    Gui.Selection.clearSelection()
    h.click_empty()
    h.fit()
    h.ribbon("Hole")


def hole_pick():
    h.click(V(10, 10, 10))


def hole_ok():
    p = hs.hole_panel()
    h.check("A: a hole is placed", p is not None and p.target is not None)
    h.task_button("OK")


def drilled():
    v = h.solid_volume()
    h.check("A: the hole d 5 through", fs.close(v, 12000.0 - HOLE), (v, 12000.0 - HOLE))
    s["hole"] = h.body().Tip.Name
    s["hole_centre"] = hs.centre_of(h.body().Tip)


def project():
    sk = fs.obj(s["sketch"])
    s["external"] = len(sk.ExternalGeo)
    h.press("p")


def project_edge():
    c = s["hole_centre"]
    si.click(V(c.x + 2.5, c.y, 10), V(1.0, 0.0, 0))


def projected():
    h.press(QtCore.Qt.Key_Escape)
    sk = fs.obj(s["sketch"])
    added = len(sk.ExternalGeo) - s["external"]
    h.check("A: the hole's edge is projected", added == 1, added)
    used = [o.Name for o, _subs in sk.ExternalGeometry]
    h.check("A: from the step that has the hole", s["hole"] in used, used)
    fs.design_kept("A, projected", s)
    h.shot("A-projected")
    s["sketch_projected"] = sk.Name


def finish_a():
    h.ribbon("Finish Sketch")


def finished_a():
    h.check("A: the sketch is closed", h.in_sketch() is None)
    fs.design_kept("A, finished", s)


# -- D --------------------------------------------------------------------------------------
def timeline_button(name):
    from sciforge import timeline_ui

    tl = timeline_ui.widget()
    tl.refresh(force=True)
    QtWidgets.QApplication.processEvents()
    for button in tl._buttons:
        if button.item.name == name:
            return button
    h.check("timeline shows %s" % name, False, tl.titles())
    return None


def suppress_hole():
    s["full"] = h.solid_volume()
    button = timeline_button(s["hole"])
    if button is not None:
        w.right_click(button, w.center(button), "Suppress Features")


def suppressed():
    from sciforge import timeline_ops

    doc = App.ActiveDocument
    v = h.solid_volume()
    h.check("D: hole suppressed: block + boss", fs.close(v, s["full"] + HOLE), (v, s["full"]))
    for key in ("sketch_B", "boss_B"):
        o = doc.getObject(s[key])
        h.check("D: %s stays" % key, o is not None and not timeline_ops.is_suppressed(o))
    o = doc.getObject(s["sketch_projected"])
    h.check("D: the sketch using the hole's edge goes with it", timeline_ops.is_suppressed(o))
    fs.no_errors_in_design("D")
    h.shot("D-suppressed")
    button = timeline_button(s["hole"])
    if button is not None:
        w.right_click(button, w.center(button), "Unsuppress Features")


def unsuppressed():
    from sciforge import timeline_ops

    v = h.solid_volume()
    h.check("D: unsuppressed: as before", fs.close(v, s["full"]), (v, s["full"]))
    o = fs.obj(s["sketch_projected"])
    h.check("D: the projecting sketch is back", not timeline_ops.is_suppressed(o))
    fs.no_errors_in_design("D, unsuppressed")
    body = h.body()
    h.check("D: drawn as it is", fs.shown_steps(body) == [body.Tip.Name], fs.shown_steps(body))


steps = b.box_steps("FixSketchHole") + [grid, hole, hole_pick, hole_ok, drilled]
steps += fs.sketch_on("A", V(25, 15, 10), s, support=(lambda st: s["block"], "the first extrude"))
steps += [project, project_edge, projected, finish_a, finished_a]
steps += fs.sketch_on("B", V(25, 15, 10), s, support=(lambda st: s["block"], "the first extrude"))
steps += fs.circle("B", V(25, 15, 10), 5, s)
steps += fs.finish_and_extrude("B", 5, s)
steps += fs.undo_redo("C", "B", s)
steps += [suppress_hole, h.idle_step(), suppressed, h.idle_step("wait_unsuppress"), unsuppressed]
steps += fs.edit_later("E", "B", s)

h.run("fixsketch_hole", steps)
