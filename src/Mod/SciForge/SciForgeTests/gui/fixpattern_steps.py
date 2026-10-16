# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shared steps for the scenarios of Luca's report on patterns and mirrors of bodies
(scenarios/fixpattern_*.py, 2026-10-16): "using rectangular/circular pattern completely
breaks all bodies. the original object in the pattern can not be edited and if deleted, it
breaks everything else. it cant even be moved without breaking everything. any movements or
edits to the original will also happen to the other bodies." / "mirror has the same issues".

Fusion copies the body as it stands at the pattern's place in the timeline: steps of the
original made after the pattern (a Move, a hole) do not reach the copies, edits of steps
before it do; each copy is a body of its own; deleting the original leaves the copies.

`main_steps(kind)` is one person's session, only real input (ribbon, clicks on the part and
the axes, the dialogs' fields, the timeline, the browser, the Undo / Redo buttons):

  1. A 40 x 30 x 10 box from the origin (12000).
  2. The pattern of the body (Pattern Type Bodies), see KINDS: the copies are new bodies.
  3. The original is moved 20 up with Move/Copy (M): only the original moves. Undo / Redo.
  4. A hole r 5, 10 deep, is cut in the original's top after the pattern: only the original
     gets it (12000 - 250 pi).
  5. The original's Extrude 1 (before the pattern) is edited from the timeline to 15: every
     copy follows (18000, z 0..15), the original too (18000 - 250 pi, z 20..35). Undo / Redo.
  6. The original is deleted (its browser row, MODIFY > Delete): the copies stay as they
     are, the pattern step is not red, the Report view stays clean. Undo / Redo / Undo.
  7. Saved, closed and opened again: the same bodies; editing Extrude 1 back to 10 still
     reaches the copies (12000, z 0..10).
  8. (Rectangular) A copy is a body of its own: Body2 moved 5 up moves alone, and still
     follows an edit of Extrude 1 (to 12, then undone).

Kinds: rectangular, circular, mirror, path (Pattern on Path along a sketch line; the
sketch is drawn first, path_sketch_steps). Hand-derived: box 12000 = 40 x 30 x 10; a hole
r 5, 10 deep removes 250 pi.
"""

import math
import os

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import pattern_steps as ps

V = App.Vector
HOLE = 250 * math.pi  # r 5, 10 deep
TOL = 1e-4


def _rot(box, degrees):
    """(x0, y0, x1, y1) of the box (x0, y0, x1, y1) turned about the Z axis."""
    a = math.radians(degrees)
    pts = [(x, y) for x in (box[0], box[2]) for y in (box[1], box[3])]
    xs = [x * math.cos(a) - y * math.sin(a) for x, y in pts]
    ys = [x * math.sin(a) + y * math.cos(a) for x, y in pts]
    return (round(min(xs), 6), round(min(ys), 6), round(max(xs), 6), round(max(ys), 6))


BOX = (0.0, 0.0, 40.0, 30.0)
# Per kind: the dialog, and where its copies land (x0, y0, x1, y1 in the floor plane).
KINDS = {
    "rectangular": {
        "title": "Rectangular Pattern 1",
        "copies": [(50.0, 0.0, 90.0, 30.0), (100.0, 0.0, 140.0, 30.0)],
    },
    "circular": {
        "title": "Circular Pattern 1",
        "copies": [_rot(BOX, 90), _rot(BOX, 180), _rot(BOX, 270)],
    },
    "mirror": {
        "title": "Mirror 1",
        "copies": [(40.0, 0.0, 80.0, 30.0)],  # across the box's right face (x = 40)
    },
    # along a sketch line y = -10 (path_sketch_steps), Quantity 3, Distance 100 (Extent): the
    # copies 50 and 100 mm along it from the point of the line nearest the part
    "path": {
        "title": "Pattern on Path 1",
        "copies": [(50.0, 0.0, 90.0, 30.0), (100.0, 0.0, 140.0, 30.0)],
    },
}
state = {}


def close(a, c, tol=1e-6):
    return abs(a - c) <= tol * max(1.0, abs(c))


def doc():
    return App.ActiveDocument


def original():
    return doc().getObject("Body") if doc() is not None else None


def copies():
    """The copy bodies (every body but the original), in the order they were made."""
    return [x for x in s.bodies() if x.Name != "Body"]


def flat(box):
    bb = box
    return (round(bb.XMin, 4), round(bb.YMin, 4), round(bb.XMax, 4), round(bb.YMax, 4))


def same_rects(got, want, tol=TOL):
    got, want = sorted(got), sorted(want)
    return len(got) == len(want) and all(
        all(abs(a - c) <= tol for a, c in zip(g, w)) for g, w in zip(got, want)
    )


def check_copies(kind, height, volume, where):
    """The copies: one body per copy, each `volume`, from z 0 to `height`, where KINDS says."""
    found = copies()
    want = KINDS[kind]["copies"]
    h.check(
        "%s: %d copy bodies" % (where, len(want)), len(found) == len(want), [x.Label for x in found]
    )
    vols = [s.volume(x) for x in found]
    h.check("%s: each copy %g" % (where, volume), all(close(v, volume) for v in vols), vols)
    rects = [flat(x.Shape.BoundBox) for x in found if not x.Shape.isNull()]
    h.check("%s: the copies where the pattern put them" % where, same_rects(rects, want), rects)
    zs = [(round(x.Shape.BoundBox.ZMin, 4), round(x.Shape.BoundBox.ZMax, 4)) for x in found]
    h.check(
        "%s: the copies from z 0 to %g" % (where, height),
        all(abs(a) < TOL and abs(c - height) < TOL for a, c in zs),
        zs,
    )
    h.check(
        "%s: the copies are shown" % where,
        all(s.shown(x) for x in found),
        [s.shown(x) for x in found],
    )


def check_original(volume, z0, z1, where):
    body = original()
    if not h.check("%s: the original is there" % where, body is not None):
        return
    h.check("%s: the original %g" % (where, volume), close(s.volume(body), volume), s.volume(body))
    bb = body.Shape.BoundBox
    h.check(
        "%s: the original from z %g to %g, x 0..40" % (where, z0, z1),
        abs(bb.ZMin - z0) < TOL
        and abs(bb.ZMax - z1) < TOL
        and abs(bb.XMin) < TOL
        and abs(bb.XMax - 40) < TOL,
        (bb.XMin, bb.XMax, bb.ZMin, bb.ZMax),
    )


def no_red(where):
    """Nothing red in the timeline (Fusion shows no failed step here)."""
    from sciforge import timeline_ops

    tl = timeline_ops.timeline(doc())
    red = [(i.display, i.message) for i in tl.items if i.status == "error"]
    h.check("%s: nothing red in the timeline" % where, not red, red)
    broken = [o.Label for o in doc().Objects if "Invalid" in list(getattr(o, "State", []))]
    h.check("%s: nothing broken" % where, not broken, broken)


def named(fn, name):
    fn.__name__ = name
    return fn


# -- 2. the pattern ------------------------------------------------------------------------
def pattern_steps(kind):
    def start():
        Gui.Selection.clearSelection()
        h.click_empty()
        if kind == "rectangular":
            h.ribbon("Rectangular Pattern")
        elif kind == "circular":
            ps.menu("Circular Pattern")
        elif kind == "path":
            ps.menu("Pattern on Path")
        else:
            h.ribbon("Mirror")

    def bodies_type():
        p = ps.panel()
        if h.check("the %s dialog is open" % kind, p is not None):
            b.choose(p.pattern_type, "Bodies")

    def click_part():
        h.fit()
        h.click(V(20, 15, 10))

    def reference_box():
        p = ps.panel()
        objs = p.options["objects"] if p else []
        h.check(
            "the body is the object",
            len(objs) == 1 and objs[0][0].TypeId == "PartDesign::Body",
            objs,
        )
        name = {"rectangular": "direction", "circular": "axis", "mirror": "plane", "path": "path"}
        ps.click_box(name[kind])

    def reference():
        h.fit()
        if kind == "rectangular":
            h.click(V(-12, 0, 0))  # the X axis, left of the part
        elif kind == "circular":
            h.click(V(0, 0, 22))  # the Z axis, above the part
        elif kind == "path":
            h.click(V(160, -10, 0))  # the sketch line
        else:
            h.click(V(40, 15, 5))  # the box's right face

    def values():
        p = ps.panel()
        if p is None:
            return
        if kind == "rectangular":
            b.choose(p.distribution, "Spacing")
            ps.type_quantity(p.quantity, 3)
            ps.type_value(p.distance_field.widget, "50")
        elif kind == "circular":
            ps.type_quantity(p.quantity, 4)
        elif kind == "path":
            h.check("the line is the path", p.options["path"] is not None, p.options["path"])
            ps.type_quantity(p.quantity, 3)
            ps.type_value(p.distance_field.widget, "100")

    def preview():
        check_copies(kind, 10, 12000, "preview")
        h.task_button("OK")

    def made():
        h.check("the dialog closed", not Gui.Control.activeDialog())
        title = KINDS[kind]["title"]
        h.check("%s in the timeline" % title, title in ps.timeline_titles(), ps.timeline_titles())
        check_copies(kind, 10, 12000, "made")
        check_original(12000, 0, 10, "made")
        no_red("made")
        h.shot("pattern")

    found = [start, bodies_type, click_part, reference_box, reference, values, preview, made]
    return [named(f, "pattern_" + f.__name__) for f in found]


# -- 3. Move the original ------------------------------------------------------------------
def move_steps(kind):
    def select():
        h.click_empty()
        h.fit()
        h.click(V(20, 15, 10))

    def press_m():
        h.press("m")

    def dz():
        p = s.panel()
        h.check("Move/Copy open", p is not None and getattr(p, "title", "") == "Move/Copy", p)
        if p is None or not hasattr(p, "distance_fields"):
            return
        h.check(
            "the original is what moves",
            [x.Name for x in p.options["bodies"]] == ["Body"],
            [x.Label for x in p.options["bodies"]],
        )
        s.type_value(p.distance_fields[2].widget, "20")

    def ok():
        h.task_button("OK")

    def moved():
        h.check("Move/Copy closed", not Gui.Control.activeDialog())
        check_original(12000, 20, 30, "moved")
        check_copies(kind, 10, 12000, "after the Move of the original")
        no_red("moved")
        h.shot("moved")
        s.undo()

    def undone():
        check_original(12000, 0, 10, "undo of the Move")
        check_copies(kind, 10, 12000, "undo of the Move")
        s.redo()

    def redone():
        check_original(12000, 20, 30, "redo of the Move")
        check_copies(kind, 10, 12000, "redo of the Move")

    found = [select, press_m, dz, ok, moved, undone, redone]
    return [named(f, "move_" + f.__name__) for f in found]


# -- 4. a hole in the original after the pattern -------------------------------------------
def hole_steps(kind):
    def sketch():
        h.click_empty()
        h.fit()
        h.ribbon("Create Sketch")

    def click_top():
        h.click(V(35, 25, 30))  # the moved original's top face

    def circle():
        sk = h.in_sketch()
        h.check("sketch open on the original's top", sk is not None)
        if sk is not None:
            x, y = h.to_sketch(sk, V(20, 15, 30))
            h.draw_circle(sk, x, y, 5)

    def finish():
        h.ribbon("Finish Sketch")

    def extrude():
        h.fit()
        h.press("e")

    def depth():
        p = b.active_panel()
        field = getattr(getattr(p, "distance", None), "widget", None)
        if h.check("extrude dialog open", field is not None):
            s.type_value(field, "-10")

    def ok():
        h.task_button("OK")

    def cut():
        check_original(12000 - HOLE, 20, 30, "the hole")
        check_copies(kind, 10, 12000, "after a hole in the original")
        no_red("the hole")

    found = [sketch, click_top, circle, finish, extrude, depth, ok, cut]
    return [named(f, "hole_" + f.__name__) for f in found]


# -- 5. the original's extrude (before the pattern) edited from the timeline -----------------
def edit_steps(kind, height, prefix, then_undo=True):
    def open_edit():
        h.click_empty()
        ps.timeline_double_click("Extrude 1")

    def distance():
        p = b.active_panel()
        field = getattr(getattr(p, "distance", None), "widget", None)
        if h.check("the extrude's dialog opened from the timeline", field is not None, p):
            s.type_value(field, "%g" % height)

    def ok():
        h.task_button("OK")

    def edited():
        h.check("extrude dialog closed", not Gui.Control.activeDialog())
        check_original(1200 * height - HOLE, 20, 20 + height, "edit %g" % height)
        check_copies(kind, height, 1200 * height, "edit of Extrude 1 to %g" % height)
        no_red("edit %g" % height)
        if then_undo:
            s.undo()

    def undone():
        check_original(12000 - HOLE, 20, 30, "undo of the edit")
        check_copies(kind, 10, 12000, "undo of the edit")
        s.redo()

    def redone():
        check_original(1200 * height - HOLE, 20, 20 + height, "redo of the edit")
        check_copies(kind, height, 1200 * height, "redo of the edit")

    found = [open_edit, distance, ok, edited] + ([undone, redone] if then_undo else [])
    return [named(f, "%s_%s" % (prefix, f.__name__)) for f in found]


# -- 6. delete the original ------------------------------------------------------------------
def delete_steps(kind, height):
    def select():
        h.click_empty()
        s.click_browser_row("Body")

    def delete():
        h.check("the original is selected", "Body" in s.selected_names(), s.selected_names())
        s.menu("MODIFY", "Delete")

    def deleted():
        h.check("the original is gone", original() is None, [x.Label for x in s.bodies()])
        check_copies(kind, height, 1200 * height, "after deleting the original")
        no_red("delete")
        s.no_popups("delete of the original")
        h.shot("deleted")
        s.undo()

    def undone():
        check_original(1200 * height - HOLE, 20, 20 + height, "undo of the delete")
        check_copies(kind, height, 1200 * height, "undo of the delete")
        no_red("undo of the delete")
        from sciforge import timeline_ops

        step = doc().getObject(_pattern_name())
        status = timeline_ops.problem(step) if step is not None else ("", "")
        h.check("the pattern step is fine again", status == ("", ""), status)
        s.redo()

    def redone():
        h.check("redo: the original is gone again", original() is None)
        check_copies(kind, height, 1200 * height, "redo of the delete")
        no_red("redo of the delete")
        s.undo()

    def back():
        check_original(1200 * height - HOLE, 20, 20 + height, "the delete undone again")

    found = [select, delete, deleted, undone, redone, back]
    return [named(f, "delete_" + f.__name__) for f in found]


def _pattern_name():
    from sciforge import pattern

    for obj in doc().Objects:
        if pattern.is_body_pattern(obj):
            return obj.Name
    return ""


# -- 7. save, close, open ----------------------------------------------------------------------
def reopen_steps(kind, height, name):
    def save_and_reopen():
        path = os.path.join(h.OUT_DIR, "%s.FCStd" % name)
        d = doc()
        d.saveAs(path)
        App.closeDocument(d.Name)
        App.openDocument(path)
        h.fit()

    save_and_reopen.wait_ms = 2000

    def reopened():
        check_original(1200 * height - HOLE, 20, 20 + height, "reopened")
        check_copies(kind, height, 1200 * height, "reopened")
        no_red("reopened")

    found = [save_and_reopen, reopened]
    return [named(f, "reopen_" + f.__name__) for f in found]


# -- 8. a copy is a body of its own --------------------------------------------------------
def copy_steps():
    """Rectangular only (after main_steps): Body2 is moved 5 up with Move/Copy: only Body2
    moves; Extrude 1 edited to 12: every copy follows (Body2 still 5 higher), undo."""

    def body2():
        found = copies()
        return found[0] if found else None

    def select():
        h.click_empty()
        h.fit()
        h.click(V(70, 15, 10))  # Body2's top

    def press_m():
        h.press("m")

    def dz():
        p = s.panel()
        if not h.check("Move/Copy open", p is not None and hasattr(p, "distance_fields"), p):
            return
        h.check(
            "Body2 is what moves",
            [x.Label for x in p.options["bodies"]] == ["Body2"],
            [x.Label for x in p.options["bodies"]],
        )
        s.type_value(p.distance_fields[2].widget, "5")

    def ok():
        h.task_button("OK")

    def moved():
        bb = body2().Shape.BoundBox if body2() is not None else None
        h.check(
            "Body2 moved: z 5..15",
            bb is not None and abs(bb.ZMin - 5) < TOL and abs(bb.ZMax - 15) < TOL,
            bb,
        )
        other = copies()[1].Shape.BoundBox
        h.check("Body3 stays: z 0..10", abs(other.ZMin) < TOL and abs(other.ZMax - 10) < TOL)
        check_original(12000 - HOLE, 20, 30, "a copy moved")
        no_red("a copy moved")

    def edit():
        h.click_empty()
        ps.timeline_double_click("Extrude 1")

    def distance():
        p = b.active_panel()
        field = getattr(getattr(p, "distance", None), "widget", None)
        if h.check("the extrude's dialog", field is not None, p):
            s.type_value(field, "12")

    def edit_ok():
        h.task_button("OK")

    def edited():
        bb = body2().Shape.BoundBox
        h.check(
            "the moved copy follows the edit: z 5..17",
            abs(bb.ZMin - 5) < TOL and abs(bb.ZMax - 17) < TOL,
            bb,
        )
        h.check("the moved copy 14400", close(s.volume(body2()), 14400), s.volume(body2()))
        other = copies()[1].Shape.BoundBox
        h.check("Body3 follows: z 0..12", abs(other.ZMin) < TOL and abs(other.ZMax - 12) < TOL)
        check_original(14400 - HOLE, 20, 32, "edit 12")
        no_red("edit 12")
        s.undo()

    def undone():
        bb = body2().Shape.BoundBox
        h.check("undo: Body2 z 5..15", abs(bb.ZMin - 5) < TOL and abs(bb.ZMax - 15) < TOL, bb)
        check_original(12000 - HOLE, 20, 30, "undo of edit 12")

    found = [select, press_m, dz, ok, moved, edit, distance, edit_ok, edited, undone]
    return [named(f, "copy_" + f.__name__) for f in found]


def path_sketch_steps():
    """A sketch on XY with one line from (0, -10) to (200, -10): the path."""

    def sketch():
        h.click_empty()
        h.fit()
        h.ribbon("Create Sketch")

    def click_xy():
        pl.click_square("XY_Plane")  # where the XY square shows

    def line():
        import Part

        sk = h.in_sketch()
        h.check("sketch open on XY", sk is not None)
        if sk is None:
            return
        a = h.to_sketch(sk, V(0, -10, 0))
        c = h.to_sketch(sk, V(200, -10, 0))
        sk.addGeometry(Part.LineSegment(V(a[0], a[1], 0), V(c[0], c[1], 0)))
        doc().recompute()

    def finish():
        h.ribbon("Finish Sketch")

    found = [sketch, click_xy, line, finish]
    return [named(f, "path_" + f.__name__) for f in found]


def main_steps(kind, name):
    return (
        b.box_steps(name)
        + (path_sketch_steps() if kind == "path" else [])
        + pattern_steps(kind)
        + move_steps(kind)
        + hole_steps(kind)
        + edit_steps(kind, 15, "edit15")
        + delete_steps(kind, 15)
        + reopen_steps(kind, 15, name)
        + edit_steps(kind, 10, "edit10", then_undo=False)
        + (copy_steps() if kind == "rectangular" else [])
    )
