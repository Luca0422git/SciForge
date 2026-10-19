# SPDX-License-Identifier: LGPL-2.1-or-later
"""Trying to break the pattern dialogs, the way an impatient user would (real input):

1. A 40 x 30 x 10 box with a through hole r 2 at (8, 8).
2. Wrong picks: the hole's sketch in the timeline (Pattern Type Features) and the hole's
   round wall (or rim) as a direction: the dialog says why, nothing in the Report view. Esc.
3. Ctrl+Z while the preview is shown: the dialog ends and the model is as before.
4. Pattern Type changed after a preview: the objects are cleared and the preview goes;
   the hole's wall picked as a face instead previews a copy. Cancel.
5. A Rectangular Pattern made by clicking the hole's wall (the feature that made it is
   taken, Pattern Type Features), then a pattern of the body (two new bodies), then that
   step deleted from the timeline's right-click menu: its bodies go with it.
6. Saved, closed and opened again: the patterns rebuild without an error and open in
   their dialog from the timeline.

Hand-derived: box 12000; a through hole r 2 removes pi 2^2 10.
"""
import os

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
ONE = ps.BOX - HOLE


def start_rect():
    Gui.Selection.clearSelection()
    h.ribbon("Rectangular Pattern")


# -- 2. wrong picks ----------------------------------------------------------------------------
def click_sketch_step():
    titles = ps.timeline_titles()
    sketches = [t for t in titles if t.startswith("Sketch")]
    h.check("the timeline shows the hole's sketch", len(sketches) >= 2, titles)
    if len(sketches) >= 2:
        ps.timeline_click(sketches[1])


def sketch_refused():
    p = ps.panel()
    text = p.message.text() if p else ""
    h.check("a sketch is refused, with the reason", "sketch" in text.lower(), text)
    h.check("nothing picked", p and p.options["objects"] == [])
    ps.timeline_click("Extrude 2")


def direction_box():
    ps.click_box("direction")


def click_round_wall():
    h.fit()
    h.click(V(8 - R * 0.7071, 8 + R * 0.7071, 9))


def wall_refused():
    p = ps.panel()
    text = p.message.text() if p else ""
    # The click lands on the round wall or on the hole's round rim: neither is a direction.
    h.check(
        "a round face or edge is no direction, said in the dialog",
        "flat face" in text or "straight edge" in text,
        text,
    )
    h.check("no direction taken", p and p.options["direction"] is None)
    h.check("no preview", p and p.target is None and ps.close(h.solid_volume(), ONE))
    h.press(QtCore.Qt.Key_Escape)


def after_esc():
    h.check("Esc closed it", not Gui.Control.activeDialog())


# -- 3. Ctrl+Z in the dialog ----------------------------------------------------------------------
def undo_start():
    start_rect()


def undo_pick():
    ps.timeline_click("Extrude 2")


def undo_box():
    ps.click_box("direction")


def undo_axis():
    h.fit()
    pl.click_on_plane(V(-12, 0, 0))


def undo_press():
    p = ps.panel()
    h.check(
        "preview shown",
        p is not None and p.target is not None and not ps.close(h.solid_volume(), ONE),
    )
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def after_undo_inside():
    h.check("Ctrl+Z ended the dialog", not Gui.Control.activeDialog() and ps.panel() is None)
    h.check("the model is as before", ps.close(h.solid_volume(), ONE) and not ps.patterns())
    h.check(
        "the hole is still there",
        App.ActiveDocument.getObject("Pocket") is not None or ps.close(h.solid_volume(), ONE),
    )


# -- 4. pattern type changed after a preview ----------------------------------------------------------
def switch_start():
    start_rect()


def switch_pick():
    ps.timeline_click("Extrude 2")


def switch_box():
    ps.click_box("direction")


def switch_axis():
    h.fit()
    pl.click_on_plane(V(-12, 0, 0))


def switch_type():
    p = ps.panel()
    h.check("preview shown", p is not None and p.target is not None)
    b.choose(p.pattern_type, "Faces")


def switched():
    p = ps.panel()
    h.check("objects cleared", p and p.options["objects"] == [], p and p.options["objects"])
    h.check(
        "preview removed",
        p and p.target is None and ps.close(h.solid_volume(), ONE),
        h.solid_volume(),
    )
    h.check("the direction is kept", p and p.options["direction"] is not None)
    h.check("the hint asks for faces", p and "faces" in p.info.text().lower(), p and p.info.text())
    h.fit()
    h.click(V(8 - R * 0.7071, 8 + R * 0.7071, 9))


def face_preview():
    p = ps.panel()
    h.check(
        "the wall is picked",
        p and len(p.options["objects"]) == 1 and p.options["objects"][0][1].startswith("Face"),
    )
    v = h.solid_volume()
    h.check("a copy of the hole", ps.close(v, ps.BOX - 2 * HOLE), v)
    h.task_button("Cancel")


def after_switch_cancel():
    h.check("Cancel: one hole, no pattern", ps.close(h.solid_volume(), ONE) and not ps.patterns())


# -- 5. a pattern, a pattern of the body, deleted from the timeline --------------------------------------
def make_start():
    start_rect()


def make_pick():
    # Pattern Type Features, a click on the hole's wall in the view: Fusion takes the
    # feature that made the face.
    h.fit()
    h.click(V(8 - R * 0.7071, 8 + R * 0.7071, 8.5))


def make_box():
    p = ps.panel()
    objs = p.options["objects"] if p else []
    h.check(
        "a face click picks the feature that made it",
        len(objs) == 1 and objs[0][1] == "" and objs[0][0].TypeId == "PartDesign::Pocket",
        objs,
    )
    h.check("the objects list says Extrude 2", p and "Extrude 2" in p.objects_label.text())
    ps.click_box("direction")


def make_axis():
    h.fit()
    pl.click_on_plane(V(-12, 0, 0))


def make_values():
    p = ps.panel()
    ps.type_quantity(p.quantity, 3)


def make_distance():
    ps.type_value(ps.panel().distance_field.widget, "24")


def make_ok():
    h.task_button("OK")


def made():
    h.check("3 holes", ps.close(h.solid_volume(), ps.BOX - 3 * HOLE), h.solid_volume())
    s["v"] = h.solid_volume()


def bodies_start():
    start_rect()


def bodies_type():
    b.choose(ps.panel().pattern_type, "Bodies")


def bodies_part():
    h.fit()
    h.click(V(30, 20, 10))


def bodies_box():
    ps.click_box("direction")


def bodies_axis():
    h.fit()
    pl.click_on_plane(V(-12, 0, 0))


def bodies_spacing():
    b.choose(ps.panel().distribution, "Spacing")


def bodies_distance():
    ps.type_value(ps.panel().distance_field.widget, "50")


def bodies_ok():
    h.check("two bodies while previewing", len(ps.bodies()) == 2, [x.Label for x in ps.bodies()])
    h.task_button("OK")


def delete_from_timeline():
    titles = ps.timeline_titles()
    h.check("Rectangular Pattern 2 in the timeline", "Rectangular Pattern 2" in titles, titles)
    button = ps.timeline_button("Rectangular Pattern 2")
    if button is not None:
        h.check("Delete in the right-click menu", w.right_click(button, w.center(button), "Delete"))


delete_from_timeline.wait_ms = 1500


def deleted():
    found = ps.bodies()
    h.check("the copy body went with its pattern", len(found) == 1, [x.Label for x in found])
    h.check(
        "the first pattern is untouched",
        ps.close(h.solid_volume(), s["v"]) and len(ps.patterns()) == 1,
    )
    h.check(
        "timeline: no Rectangular Pattern 2", "Rectangular Pattern 2" not in ps.timeline_titles()
    )


# -- 6. save, close, open -------------------------------------------------------------------------
def save_and_reopen():
    doc = App.ActiveDocument
    path = os.path.join(h.OUT_DIR, "patterns_qa.FCStd")
    doc.saveAs(path)
    name = doc.Name
    App.closeDocument(name)
    App.openDocument(path)
    App.ActiveDocument.recompute()
    h.fit()


save_and_reopen.wait_ms = 2000


def reopened():
    doc = App.ActiveDocument
    body = doc.getObject("Body")
    h.check(
        "reopened: the holes are there",
        body is not None and ps.close(body.Shape.Volume, s["v"]),
        body and body.Shape.Volume,
    )
    broken = [o.Label for o in doc.Objects if "Invalid" in list(getattr(o, "State", []))]
    h.check("nothing broken", not broken, broken)
    ps.timeline_double_click("Rectangular Pattern 1")


def reopened_edit():
    p = ps.panel()
    h.check("the dialog opens after reopening", p is not None and p.editing)
    h.check(
        "its values", p and p.quantity.value() == 3 and abs(p.distance_field.value() - 24) < 1e-6
    )
    h.task_button("Cancel")


def end():
    h.check(
        "closed, unchanged", not Gui.Control.activeDialog() and ps.close(h.solid_volume(), s["v"])
    )


h.run(
    "patterns_qa",
    b.box_steps("PatternQA")
    + ps.make_cut("hole", (8, 8), R)
    + [
        start_rect,
        click_sketch_step,
        sketch_refused,
        direction_box,
        click_round_wall,
        wall_refused,
        after_esc,
        undo_start,
        undo_pick,
        undo_box,
        undo_axis,
        undo_press,
        after_undo_inside,
        switch_start,
        switch_pick,
        switch_box,
        switch_axis,
        switch_type,
        switched,
        face_preview,
        after_switch_cancel,
        make_start,
        make_pick,
        make_box,
        make_axis,
        make_values,
        make_distance,
        make_ok,
        made,
        bodies_start,
        bodies_type,
        bodies_part,
        bodies_box,
        bodies_axis,
        bodies_spacing,
        bodies_distance,
        bodies_ok,
        delete_from_timeline,
        deleted,
        save_and_reopen,
        reopened,
        reopened_edit,
        end,
    ],
)
