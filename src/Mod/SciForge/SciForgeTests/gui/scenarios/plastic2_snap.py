# SPDX-License-Identifier: LGPL-2.1-or-later
"""PLASTIC > Snap Fit on an enclosure wall and its groove, like a Fusion user, real input.

A base (60 x 40 x 20, 2 mm walls, open top) with a 2 mm lid on it; a sketch of one point on
the parting plane (z = 20) against the inside of the right wall (58, 20). PLASTIC tab >
Snap Fit: the dialog asks for a sketch; a click on the sketch's row in the browser takes
its point (Automatic). The hook hangs from the lid (the body behind the sketch plane) and
its groove is cut in the base's wall: 1.1 x 6.2 x 3.2 = 21.824 (the default rule: clearance
0.1). The dialog shows the rule and the strain at the beam's root. Beam Length typed 14:
the hook grows, the groove moves down (same size). The catch depth arrow dragged deeper:
the groove deepens. OK: one "Snap Fit 1" in the timeline (the groove step in the base is
not listed). Undo: both bodies as before; Redo: back. Double-click "Snap Fit 1": the values
read back (14); Retention Angle 60: the lid changes, Esc: back as it was. Save, close,
reopen: the same volumes, every step computed.
"""

import os
import tempfile

import FreeCAD as App
import Part
from PySide import QtCore

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plastic2_steps as ps
from SciForgeTests.gui import versions_input as vi

V = App.Vector
s = {}


def setup():
    base, lid = ps.enclosure("SnapFit", lid="plate")
    ps.points_sketch(base, [(58, 20)])
    s["base"], s["lid"] = base, lid
    h.fit()
    h.check("the enclosure", ps.near(ps.volume(base), ps.BASE) and ps.near(ps.volume(lid), 4800))


def open_snap_fit():
    ps.plastic_tab()
    h.ribbon("Snap Fit")


def dialog_asks_for_sketch():
    p = ps.snap_panel()
    h.check("the Snap Fit dialog is open", p is not None)
    if p is None:
        return
    h.check("it asks for a sketch", "sketch" in ps.message(p).lower(), ps.message(p))
    h.check("it shows the plastic rule", "Default (mm)" in p.rule_label.text(), p.rule_label.text())
    h.check("Parallel Hook and Groove first", p.type.currentText() == "Parallel Hook and Groove")
    ps.click_row("SnapPoints")


def hook_and_groove():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    h.check("still open", p is not None)
    if p is None:
        return
    h.check("1 point picked", p.field.button.text().startswith("1 point"), p.field.button.text())
    added = ps.volume(s["lid"]) - 4800.0
    s["lid1"] = ps.volume(s["lid"])
    h.check("a hook on the lid (beam ~144 + catch ~12 + base fillet)", 150 < added < 165, added)
    cut = ps.BASE - ps.volume(s["base"])
    h.check("the groove in the base wall: 21.824", ps.near(cut, ps.GROOVE, 1e-6), cut)
    h.check("the other body is the base", p.other_label.text() == "Base", p.other_label.text())
    box = s["lid"].Shape.BoundBox
    h.check("the hook hangs 12 below the lid", ps.near(box.ZMin, 8.0, 1e-6), box)
    window = Part.makeBox(1.0, 6.0, 3.0, V(58.05, 17.05, 7.95))
    left = window.common(s["base"].Shape).Volume
    h.check("the groove is in the right wall, beside the catch", left < 1e-6, left)
    h.shot("plastic2_snap_hook")
    h.check("the strain is shown", "Strain" in p.strain.text(), p.strain.text())
    h.check("no error", not p.error and "⚠" not in ps.message(p), ps.message(p))
    h.check("two arrows (length, catch depth)", set(p.arrows) == {"length", "catch_depth"})
    ps.type_field(p, "length", "14")


def longer_beam():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    lid = ps.volume(s["lid"])
    h.check("Beam Length 14: the hook grows", lid > s["lid1"] + 20, (lid, s["lid1"]))
    cut = ps.BASE - ps.volume(s["base"])
    h.check("the groove keeps its size", ps.near(cut, ps.GROOVE, 1e-6), cut)
    groove = ps.followers(p.target)
    h.check("one groove step in the base", len(groove) == 1, groove)
    if groove:
        z = groove[0].Shape.BoundBox
        h.check("the base keeps its box", ps.near(z.ZLength, 20.0), z)
    s["lid14"] = lid
    s["drag"] = ps.drag_arrow(p, "catch_depth", 1.5)


def deeper_catch():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    depth = p.options["catch_depth"]
    h.check("the catch depth arrow dragged deeper", depth > 1.05, depth)
    cut = ps.BASE - ps.volume(s["base"])
    h.check("the groove deepens with the catch", cut > ps.GROOVE + 0.5, cut)
    ps.type_field(p, "catch_depth", "1")


def ok_snap():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    h.check("catch depth back to 1", ps.near(p.options["catch_depth"], 1.0), p.options)
    ps.ok()


def one_step():
    h.check("the dialog closed", ps.snap_panel() is None)
    titles = ps.titles()
    h.check("one Snap Fit in the timeline", titles.count("Snap Fit 1") == 1, titles)
    h.check("the groove step is not listed", not any("Groove" in t for t in titles), titles)
    s["lidOK"] = ps.volume(s["lid"])
    s["baseOK"] = ps.volume(s["base"])
    h.check("still the groove", ps.near(ps.BASE - s["baseOK"], ps.GROOVE, 1e-6), s["baseOK"])
    sketch = ps.by_label("SnapPoints")
    h.check("the sketch is hidden after OK", not sketch.ViewObject.Visibility)
    ps.undo()


def undone():
    h.check("Undo: the lid as before", ps.near(ps.volume(s["lid"]), 4800.0), ps.volume(s["lid"]))
    h.check("Undo: the base as before", ps.near(ps.volume(s["base"]), ps.BASE))
    h.check("Undo: no snap fit", not ps.snap_steps())
    ps.redo()


def redone():
    h.check("Redo: the hook", ps.near(ps.volume(s["lid"]), s["lidOK"], 1e-9))
    h.check("Redo: the groove", ps.near(ps.volume(s["base"]), s["baseOK"], 1e-9))
    h.check("double-click opens the edit", ps.double_click_timeline("Snap Fit 1"))


def edit_reads_back():
    p = ps.snap_panel()
    h.check("the edit dialog", p is not None and p.editing)
    if p is None:
        return
    h.check("Beam Length read back: 14", ps.near(p.options["length"], 14.0), p.options["length"])
    h.check("1 point", p.field.button.text().startswith("1 point"), p.field.button.text())
    ps.type_field(p, "retention_angle", "60")


def edit_changes():
    ps.settle(ps.snap_panel)
    lid = ps.volume(s["lid"])
    h.check("Retention Angle 60: the catch changes", not ps.near(lid, s["lidOK"], 1e-9), lid)
    ps.esc()


def esc_keeps():
    h.check("Esc closed the dialog", ps.snap_panel() is None)
    h.check("Esc: the lid as before the edit", ps.near(ps.volume(s["lid"]), s["lidOK"], 1e-9))
    h.check("Esc: the base as before", ps.near(ps.volume(s["base"]), s["baseOK"], 1e-9))
    h.check("Esc: still one Snap Fit", ps.titles().count("Snap Fit 1") == 1, ps.titles())
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-snap-"), "snap.FCStd")
    s["path"] = path
    ps.doc().saveAs(path)
    h.check("saved", os.path.isfile(path), path)


def ctrl_s():
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


def describe():
    vi.accept_save()


def close_reopen():
    App.closeDocument(ps.doc().Name)
    App.openDocument(s["path"])
    h.fit()


def reopened():
    base, lid = ps.by_label("Base"), ps.by_label("Lid")
    h.check("both bodies are back", base is not None and lid is not None)
    if base is None or lid is None:
        return
    ps.doc().recompute()
    h.check("the lid with its hook", ps.near(ps.volume(lid), s["lidOK"], 1e-7), ps.volume(lid))
    h.check("the base with its groove", ps.near(ps.volume(base), s["baseOK"], 1e-7))
    steps = ps.snap_steps()
    h.check("the Snap Fit step is back", len(steps) == 1)
    if steps:
        h.check("its groove step is back", len(ps.followers(steps[0])) == 1)
        bad = [o.Name for o in ps.doc().Objects if "Invalid" in o.State or "Error" in o.State]
        h.check("every step computed", not bad, bad)
    h.check("Snap Fit 1 in the timeline", "Snap Fit 1" in ps.titles(), ps.titles())
    rule_changes()


def rule_changes():
    """The design's rule becomes "ABS 1.5 mm" (plastic-1's Assign Plastic Rule dialog does
    this; its contract call here): the values still linked to the rule follow it, the typed
    Beam Length stays."""
    from sciforge import plastic

    step = ps.snap_steps()[0]
    lid = ps.by_label("Lid")
    before = ps.volume(lid)
    plastic.assign_rule(ps.doc(), "ABS 1.5 mm", None)
    ps.doc().recompute()
    h.check("the rule's thickness reaches the beam", ps.near(step.RootThickness.Value, 1.5))
    h.check("and the catch end", ps.near(step.TipThickness.Value, 1.5))
    h.check("the typed Beam Length stays 14", ps.near(step.BeamLength.Value, 14.0))
    h.check("the hook is thinner now", ps.volume(lid) < before - 10, (ps.volume(lid), before))
    h.check("still computed", "Invalid" not in step.State, step.State)


h.run(
    "plastic2_snap",
    [
        setup,
        open_snap_fit,
        dialog_asks_for_sketch,
        hook_and_groove,
        longer_beam,
        deeper_catch,
        ok_snap,
        one_step,
        undone,
        redone,
        edit_reads_back,
        edit_changes,
        esc_keeps,
        ctrl_s,
        describe,
        close_reopen,
        reopened,
    ],
)
