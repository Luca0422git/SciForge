# SPDX-License-Identifier: LGPL-2.1-or-later
"""Compute All (MODIFY > Compute All, Ctrl+B), only real input (docs/sciforge/parity/misc.md).

A body: a 40 x 30 sketch extruded by the user parameter depth (10 mm), then a fillet on an edge
that does not exist (Edge99): red in the timeline.

P1 MODIFY > Compute All: the summary window: "Compute All: N steps ...: 1 could not be computed.", the Fillet
   listed with the reason; nothing in the Report view (failures show in the timeline).
P2 Find in Timeline: the Fillet is selected in the timeline.
P3 The fillet given a real edge and depth set to 20 without recomputing: Ctrl+B computes
   everything again: the body is 40 x 30 x 20 (less the fillet), no window (a note says all
   were computed).
P4 Compute All adds nothing to undo (the Undo list is the same).
P5 With no design open the command is greyed (it computes the open design).
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import misc_steps as m
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import widget_input as w

s = {}


def doc():
    return App.ActiveDocument


def summary():
    from sciforge import compute_ui

    d = compute_ui.SummaryDialog.last
    try:
        return d if d is not None and d.isVisible() else None
    except RuntimeError:
        return None


def setup():
    from sciforge import commands, parameters, sketch_ui, timeline_ops

    Gui.activateWorkbench("SciForgeWorkbench")
    d = App.newDocument("Compute")
    parameters.add_user(d, "depth", "mm", "10")
    body = commands.ensure_body()
    planes = sketch_ui.origin_planes(body)
    sk = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    h.draw_rectangle(sk, 0, 0, 40, 30)
    pad = body.newObject("PartDesign::Pad", "Pad")
    pad.Profile = sk
    pad.setExpression("Length", "Parameters.depth")
    body.Tip = pad
    d.recompute()
    fillet = body.newObject("PartDesign::Fillet", "Fillet")
    fillet.Base = (pad, ["Edge99"])
    fillet.Radius = 2
    body.Tip = fillet
    timeline_ops.recompute(d)
    s["body"], s["pad"], s["fillet"] = body.Name, pad.Name, fillet.Name
    h.fit()
    h.check(
        "the fillet is red in the timeline",
        "Invalid" in fillet.State or "Error" in fillet.State,
        fillet.State,
    )


# -- P1 ----------------------------------------------------------------------------------------
def p1_compute():
    s["undo"] = list(doc().UndoNames)
    si.menu_item("MODIFY", "Compute All")


p1_compute.wait_ms = 1500


def p1_summary():
    d = summary()
    h.check("P1 the summary window", d is not None, h.popups())
    if d is None:
        return
    text = d.words.text()
    h.check(
        "P1 it counts one step that could not be computed",
        text.startswith("Compute All:") and "1 could not be computed" in text,
        text,
    )
    rows = [
        (d.list.topLevelItem(r).text(0), d.list.topLevelItem(r).text(1))
        for r in range(d.list.topLevelItemCount())
    ]
    h.check("P1 the Fillet listed as an error", rows == [("Fillet", "Error")], rows)
    reason = d.list.topLevelItem(0).text(2) if rows else ""
    h.check("P1 with the reason", len(reason) > 5, reason)
    h.shot("1-summary")


# -- P2 ----------------------------------------------------------------------------------------
def p2_find():
    d = summary()
    if d is not None:
        w.click(d.find_button)


def p2_check():
    from sciforge import timeline_ui

    selected = timeline_ui.widget().selected()
    h.check("P2 the Fillet is selected in the timeline", s["fillet"] in selected, selected)
    d = summary()
    if d is not None:
        w.click(m.find_child(d, "SciForgeComputeAllClose"))


# -- P3 ----------------------------------------------------------------------------------------
def p3_fix():
    d = doc()
    fillet = d.getObject(s["fillet"])
    fillet.Base = (d.getObject(s["pad"]), ["Edge1"])
    d.getObject("Parameters").depth = 20  # changed, not recomputed yet
    s["before"] = d.getObject(s["body"]).Shape.Volume
    h.press(QtCore.Qt.Key_B, QtCore.Qt.ControlModifier)


p3_fix.wait_ms = 1500


def p3_check():
    d = doc()
    vol = d.getObject(s["body"]).Shape.Volume
    h.check(
        "P3 Ctrl+B computed everything: about 40 x 30 x 20", 23900 < vol < 24000, (s["before"], vol)
    )
    h.check("P3 no window without errors", summary() is None)
    h.check("P3 a note says all were computed", "all computed" in m.told(), m.told())
    h.check("P3 the fillet is fine now", "Invalid" not in d.getObject(s["fillet"]).State)


# -- P4 ----------------------------------------------------------------------------------------
def p4_undo_list():
    h.check(
        "P4 Compute All adds nothing to undo",
        list(doc().UndoNames) == s["undo"],
        (s["undo"], list(doc().UndoNames)),
    )


# -- P5 ----------------------------------------------------------------------------------------
def p5_no_design():
    from sciforge import compute_ui

    m.close_all()
    h.check("P5 greyed without a design", not compute_ui.ComputeAllCommand().IsActive())


def cleanup():
    m.close_all()
    h.new_errors()


h.run(
    "misc_compute",
    [
        setup,
        p1_compute,
        p1_summary,
        p2_find,
        p2_check,
        p3_fix,
        p3_check,
        p4_undo_list,
        p5_no_design,
        cleanup,
    ],
)
