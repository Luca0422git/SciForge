# SPDX-License-Identifier: LGPL-2.1-or-later
"""Editing patterns the way Fusion users do it, over and over (QA, only real input).

Path 5, edit from the timeline three times with a person's double-click: the first edit is
        undone with Ctrl+Z inside the dialog (the dialog closes, the pattern is as it was, no
        undo step is left); then Quantity 4 / Distance 30; then Spacing 8. Undo / redo walk
        back and forth through the two edits.
Path 6, later steps survive an edit that rebuilds the pattern: a sketch on the pattern's top
        face and a boss extruded from it, then the pattern edited with Suppression (one copy
        left out). FreeCAD cannot leave a copy out, so SciForge rebuilds the step as its own
        feature: the boss's sketch stays on the top face (before, a sketch hung on the
        pattern lost its face silently), and when the box is made taller from the timeline the
        boss rides up with the face.
Path 7, the design saved (Ctrl+S with the edit dialog open: the edit is finished first),
        closed and opened again; the pattern edited again (Suppression off: FreeCAD's pattern
        again, the boss still on its face); Ctrl+Z / Ctrl+Y.

Hand-derived: box 40 x 30 x 10 = 12000; a through hole r 2 removes pi 2^2 10; a boss r 3 x 4
adds pi 3^2 4.
"""
import math
import os

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import pattern_steps as ps
from SciForgeTests.gui import widget_input as w

V = App.Vector
s = {}
R = 2.0
HOLE = ps.hole(R)
BOSS = math.pi * 9.0 * 4.0


def doc():
    return App.ActiveDocument


def centres():
    return ps.circle_centres(h.body().Shape, R, z=10)


def xs():
    return [x for x, _y in centres()]


def tick(box):
    w.click(box, QtCore.QPoint(8, box.height() // 2))


def the_pattern():
    found = ps.patterns()
    return found[0] if len(found) == 1 else None


def boss_sketch():
    return doc().getObject(s["boss_sketch"]) if s.get("boss_sketch") else None


# -- the pattern ------------------------------------------------------------------------------------
def make_start():
    Gui.Selection.clearSelection()
    h.ribbon("Rectangular Pattern")


def make_pick():
    ps.timeline_click("Extrude 2")


def make_box():
    ps.click_box("direction")


def make_axis():
    h.fit()
    h.click(V(-12, 0, 0))


def make_quantity():
    ps.type_quantity(ps.panel().quantity, 3)


def make_distance():
    ps.type_value(ps.panel().distance_field.widget, "24")


def make_ok():
    h.task_button("OK")


def made():
    h.check("3 holes at 8, 20, 32", xs() == [8, 20, 32], centres())
    s["undo"] = doc().UndoCount


# -- Path 5: three edits, Ctrl+Z in the first ---------------------------------------------------------
def p5_edit1():
    ps.timeline_double_click("Rectangular Pattern 1")


def p5_edit1_open():
    p = ps.panel()
    h.check("the edit dialog opens", p is not None and p.editing)
    if p is not None:
        ps.type_quantity(p.quantity, 2)


def p5_edit1_preview():
    h.check("preview: 2 holes", xs() == [8, 32], centres())
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def p5_edit1_undone():
    h.check("Ctrl+Z in the edit closes it", ps.panel() is None and not Gui.Control.activeDialog())
    h.check("the pattern is as it was", xs() == [8, 20, 32], centres())
    h.check("no undo step left", doc().UndoCount == s["undo"], (doc().UndoCount, s["undo"]))
    ps.timeline_double_click("Rectangular Pattern 1")


def p5_edit2():
    p = ps.panel()
    h.check("the second edit opens with the old values", p and p.quantity.value() == 3)
    if p is not None:
        ps.type_quantity(p.quantity, 4)
        ps.type_value(p.distance_field.widget, "30")


def p5_edit2_ok():
    h.check("4 holes over 30", xs() == [8, 18, 28, 38], centres())
    h.task_button("OK")


def p5_edit3():
    ps.timeline_double_click("Rectangular Pattern 1")


def p5_edit3_open():
    p = ps.panel()
    h.check("third edit: 4 / 30 shown", p and p.quantity.value() == 4)
    if p is not None:
        b.choose(p.distribution, "Spacing")


def p5_spacing():
    ps.type_value(ps.panel().distance_field.widget, "8")


def p5_edit3_ok():
    h.check("Spacing 8: 8, 16, 24, 32", xs() == [8, 16, 24, 32], centres())
    h.task_button("OK")


def p5_undo1():
    h.check("dialog closed", ps.panel() is None)
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def p5_undone1():
    h.check("undo: back to Extent 30", xs() == [8, 18, 28, 38], centres())
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def p5_undone2():
    h.check("undo again: back to 3 over 24", xs() == [8, 20, 32], centres())
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def p5_redone1():
    h.check("redo: Extent 30", xs() == [8, 18, 28, 38], centres())
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def p5_redone2():
    h.check("redo: Spacing 8", xs() == [8, 16, 24, 32], centres())
    h.check("one pattern", the_pattern() is not None)
    s["v"] = h.solid_volume()


# -- Path 6: a boss on the pattern's top face, the pattern rebuilt ---------------------------------------
def on_top_face(top=10.0):
    """(ok, detail): the boss's sketch still hangs on a top face of the part. Clicked on the
    patterned part, it hangs on the pattern, or (when Create Sketch picks the step that made
    the face) on the step before it; if it hung on the pattern, it must hang on the pattern
    now (the rebuilt one), not on nothing."""
    sketch = boss_sketch()
    support = list(sketch.AttachmentSupport) if sketch else []
    if not support or not support[0][1]:
        return False, support
    obj, subs = support[0]
    if s.get("on_pattern") and obj is not the_pattern():
        return False, ("not on the pattern any more", support)
    try:
        face = obj.Shape.getElement(subs[0])
    except Exception as exc:
        return False, (support, exc)
    ok = abs(face.CenterOfMass.z - top) < 1e-6 and face.Surface.TypeId == "Part::GeomPlane"
    return ok, (obj.Label, subs, face.CenterOfMass)


def p6_boss_made():
    sketches = [o for o in doc().Objects if o.TypeId == "Sketcher::SketchObject"]
    s["boss_sketch"] = sketches[-1].Name
    support = sketches[-1].AttachmentSupport
    s["on_pattern"] = bool(support) and support[0][0] is the_pattern()
    ok, detail = on_top_face()
    h.check("the boss's sketch sits on the top face", ok, detail)
    s["v"] = h.solid_volume()
    ps.timeline_double_click("Rectangular Pattern 1")


def p6_tick():
    p = ps.panel()
    h.check("edit open", p is not None and p.editing)
    if p is not None:
        tick(p.suppression)


def p6_dot():
    p = ps.panel()
    h.check("a dot on each of the 3 copies", p.dots is not None and len(p.dots.points) == 3)
    if p.dots is not None:
        h.fit()
        h.click(p.dots.points[0])  # the copy at x = 16


def p6_left_out():
    p = ps.panel()
    h.check("copy at 16 left out", p.options["suppressed"] == [0], p.options["suppressed"])
    h.check("holes at 8, 24, 32", xs() == [8, 24, 32], centres())
    h.task_button("OK")


p6_left_out.wait_ms = 1200


def p6_after():
    pat = the_pattern()
    h.check(
        "one pattern, now SciForge's own feature", pat and pat.TypeId == "PartDesign::FeaturePython"
    )
    ok, detail = on_top_face()
    h.check("the boss's sketch is still on the top face (not lost)", ok, detail)
    h.check("boss still there", ps.close(h.solid_volume(), s["v"] + HOLE), h.solid_volume())
    h.check("timeline title kept", "Rectangular Pattern 1" in ps.timeline_titles())
    broken = [o.Label for o in doc().Objects if set(o.State) & {"Invalid", "Error"}]
    h.check("nothing broken", not broken, broken)
    s["v"] = h.solid_volume()
    ps.timeline_double_click("Extrude 1")


def p6_taller():
    p = b.active_panel()
    field = getattr(getattr(p, "distance", None), "widget", None)
    h.check("Extrude 1 opens to edit", field is not None)
    if field is not None:
        b.type_into(field, "14")


def p6_taller_ok():
    h.task_button("OK")


p6_taller_ok.wait_ms = 1500


def p6_boss_rides_up():
    tops = ps.circle_centres(h.body().Shape, 3.0, z=18)
    h.check("the boss rides up with the top face (top at z = 18)", tops == [(30, 22)], tops)
    broken = [o.Label for o in doc().Objects if set(o.State) & {"Invalid", "Error"}]
    h.check("nothing broken", not broken, broken)
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def p6_back():
    tops = ps.circle_centres(h.body().Shape, 3.0, z=14)
    h.check("Ctrl+Z: box 10 high again, boss top at 14", tops == [(30, 22)], tops)
    h.check("volume as before", ps.close(h.solid_volume(), s["v"]), h.solid_volume())


# -- Path 7: Ctrl+S with the dialog open, reopen, edit again ---------------------------------------------
def p7_save_as():
    s["path"] = os.path.join(h.OUT_DIR, "patterns_qa_edit.FCStd")
    if os.path.exists(s["path"]):
        os.remove(s["path"])
    doc().saveAs(s["path"])  # the design was saved before (File > Save As)
    ps.timeline_double_click("Rectangular Pattern 1")


def p7_edit():
    p = ps.panel()
    h.check("edit open", p is not None)
    if p is not None:
        ps.type_quantity(p.quantity, 3)


def p7_ctrl_s():
    h.check("preview: 3 holes, the first copy left out", xs() == [8, 24], centres())
    s["mtime"] = os.path.getmtime(s["path"])
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


p7_ctrl_s.wait_ms = 2500


def p7_saved():
    h.check("Ctrl+S finished the edit first", ps.panel() is None and not Gui.Control.activeDialog())
    h.check("the file was saved", os.path.getmtime(s["path"]) > s["mtime"])
    h.check("not modified after the save", not doc().isTouched())
    s["v"] = h.solid_volume()
    name = doc().Name
    App.closeDocument(name)
    App.openDocument(s["path"])
    doc().recompute()
    h.fit()


p7_saved.wait_ms = 2500


def p7_reopened():
    h.check("reopened: same part", ps.close(h.solid_volume(), s["v"]), h.solid_volume())
    broken = [o.Label for o in doc().Objects if set(o.State) & {"Invalid", "Error"}]
    h.check("nothing broken after reopening", not broken, broken)
    ps.timeline_double_click("Rectangular Pattern 1")


def p7_edit_again():
    p = ps.panel()
    h.check("the pattern opens in its dialog", p is not None and p.editing)
    if p is None:
        return
    h.check("Suppression ticked, the left-out copy known", p.options["suppressed"] == [0])
    h.check("quantity 3", p.quantity.value() == 3)
    tick(p.suppression)


def p7_untick_ok():
    h.check("every copy back: 8, 16, 24", xs() == [8, 16, 24], centres())
    h.task_button("OK")


p7_untick_ok.wait_ms = 1200


def p7_native_again():
    pat = the_pattern()
    h.check("FreeCAD's LinearPattern again", pat and pat.TypeId == "PartDesign::LinearPattern")
    ok, detail = on_top_face()
    h.check("the boss's sketch followed again", ok, detail)
    tops = ps.circle_centres(h.body().Shape, 3.0, z=14)
    h.check("the boss is there", tops == [(30, 22)], tops)
    s["v"] = h.solid_volume()
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def p7_undone():
    pat = the_pattern()
    h.check("Ctrl+Z: SciForge's feature with the copy left out", xs() == [8, 24], centres())
    h.check("one pattern", pat is not None)
    ok, detail = on_top_face()
    h.check("the sketch is on the top face", ok, detail)
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def p7_redone():
    h.check("Ctrl+Y: 8, 16, 24", xs() == [8, 16, 24], centres())
    h.check("volume", ps.close(h.solid_volume(), s["v"]), h.solid_volume())
    h.check("valid", h.body().Shape.isValid())
    h.shot("7-end")


h.run(
    "patterns_qa_edit",
    b.box_steps("PatternQAEdit")
    + ps.make_cut("hole", (8, 8), R)
    + [
        make_start,
        make_pick,
        make_box,
        make_axis,
        make_quantity,
        make_distance,
        make_ok,
        made,
        p5_edit1,
        p5_edit1_open,
        p5_edit1_preview,
        p5_edit1_undone,
        p5_edit2,
        p5_edit2_ok,
        p5_edit3,
        p5_edit3_open,
        p5_spacing,
        p5_edit3_ok,
        p5_undo1,
        p5_undone1,
        p5_undone2,
        p5_redone1,
        p5_redone2,
    ]
    + ps.make_boss("boss", (30, 22), 3, 4, V(36, 27, 10))
    + [
        p6_boss_made,
        p6_tick,
        p6_dot,
        p6_left_out,
        p6_after,
        p6_taller,
        p6_taller_ok,
        p6_boss_rides_up,
        p6_back,
        p7_save_as,
        p7_edit,
        p7_ctrl_s,
        p7_saved,
        p7_reopened,
        p7_edit_again,
        p7_untick_ok,
        p7_native_again,
        p7_undone,
        p7_redone,
    ],
)
