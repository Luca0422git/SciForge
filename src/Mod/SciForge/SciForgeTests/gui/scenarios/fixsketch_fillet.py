# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sketching on faces a fillet and a chamfer changed (Luca, 2026-10-16: "sketching on an
edited object will revert it to a previous state, making it impossible to sketch on edited
faces"). Only real input; fixsketch_steps has the shared steps and why.

Block 40 x 30 x 10 (Create Sketch, XY, rectangle, Finish, E, 10, OK).
  A  F, the top front edge, OK (r 1). Create Sketch, click the top (which the fillet
     changed): the sketch hangs on the top the first extrude made (so a later step can be
     suppressed without taking it along), but the part stays drawn with its fillet, the
     marker stays at the end. C, a circle r 5, Finish Sketch, E, 5, OK: the boss joins the
     filleted part (before: the part showed without its fillet while sketching).
  B  Chamfer, the right bottom edge, OK (1 mm). Create Sketch on the front face (a face of
     the first extrude, its outline changed by the fillet and the chamfer): the part stays
     drawn with the boss, fillet and chamfer. A circle r 2, E, 3, OK: a boss out of the
     front.
  C  Ctrl+Z: B's boss goes, the part is drawn with every edit; Ctrl+Y: back.
  D  Double-click A's sketch in the timeline: the design is drawn as it is at the sketch
     (Fusion rolls back to it): the fillet is there, A's boss and what came after are not;
     Finish Sketch: everything is drawn again, nothing changed.
  E  Suppress the fillet (an earlier step the sketches do not hang on): both sketches and
     bosses stay (the hole QA's rule); Unsuppress: as before.

Hand-derived: a round r on a 40 mm edge removes 40 r^2 (1 - pi/4); a 1 mm chamfer on the
30 mm edge removes 15; a boss r x d adds pi r^2 d (r as drawn).
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtWidgets

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import fixsketch_steps as fs
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import widget_input as w

V = App.Vector
s = {}
FILLET = 40 * b.spandrel(1)
CHAMFER = 30 * 1 * 1 / 2.0


def grid():
    fs.one_mm_grid()
    s["block"] = h.body().Tip.Name


# -- A --------------------------------------------------------------------------------------
def fillet():
    Gui.Selection.clearSelection()
    h.click_empty()
    h.fit()
    h.press("f")


def fillet_pick():
    h.click_edge(V(20, 0, 10))


def fillet_ok():
    p = b.blend_panel()
    h.check("A: one edge picked", p is not None and len(p.refs) == 1)
    h.task_button("OK")


def filleted():
    v = h.solid_volume()
    h.check("A: the filleted block", fs.close(v, b.BOX - FILLET), (v, b.BOX - FILLET))
    s["fillet"] = h.body().Tip.Name


# -- B --------------------------------------------------------------------------------------
def chamfer():
    Gui.Selection.clearSelection()
    h.click_empty()
    h.fit()
    h.ribbon("Chamfer")


def chamfer_pick():
    h.click_edge(V(40, 15, 0))


def chamfer_ok():
    h.task_button("OK")


def chamfered():
    v = h.solid_volume()
    expect = s["after_a"] - CHAMFER
    h.check("B: the chamfer", fs.close(v, expect), (v, expect))
    s["chamfer"] = h.body().Tip.Name


def after_a():
    s["after_a"] = h.solid_volume()


# -- E --------------------------------------------------------------------------------------
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


def suppress_fillet():
    s["full"] = h.solid_volume()
    button = timeline_button(s["fillet"])
    if button is not None:
        w.right_click(button, w.center(button), "Suppress Features")


def suppressed():
    from sciforge import timeline_ops

    doc = App.ActiveDocument
    v = h.solid_volume()
    expect = s["full"] + FILLET
    h.check("E: fillet suppressed: everything else stays", fs.close(v, expect, 1e-5), (v, expect))
    for key in ("sketch_A", "sketch_B", "boss_A", "boss_B"):
        o = doc.getObject(s[key])
        h.check(
            "E: %s is not suppressed" % key, o is not None and not timeline_ops.is_suppressed(o)
        )
    fs.no_errors_in_design("E")
    h.check("E: the part is drawn as it is now", fs.shown_steps(h.body()) == [h.body().Tip.Name])
    button = timeline_button(s["fillet"])
    if button is not None:
        w.right_click(button, w.center(button), "Unsuppress Features")


def unsuppressed():
    v = h.solid_volume()
    h.check("E: unsuppressed: as before", fs.close(v, s["full"], 1e-6), (v, s["full"]))
    fs.no_errors_in_design("E, unsuppressed")
    h.shot("E-unsuppressed")


steps = b.box_steps("FixSketchFillet") + [grid, fillet, fillet_pick, fillet_ok, filleted]
steps += fs.sketch_on("A", V(25, 15, 10), s, support=(lambda st: s["block"], "the first extrude"))
steps += fs.circle("A", V(25, 15, 10), 5, s)
steps += fs.finish_and_extrude("A", 5, s)
steps += [after_a, chamfer, chamfer_pick, chamfer_ok, chamfered]
steps += fs.sketch_on("B", V(15, 0, 5), s, support=(lambda st: s["block"], "the first extrude"))
steps += fs.circle("B", V(15, 0, 5), 2, s, rim=V(17, 0, 5))
steps += fs.finish_and_extrude("B", 3, s)
steps += fs.undo_redo("C", "B", s)
steps += fs.edit_later("D", "A", s)
steps += [suppress_fillet, h.idle_step(), suppressed, h.idle_step("wait_unsuppress"), unsuppressed]

h.run("fixsketch_fillet", steps)
