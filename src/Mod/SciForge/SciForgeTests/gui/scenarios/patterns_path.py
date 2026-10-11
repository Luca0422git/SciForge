# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pattern on Path and patterns of bodies, only real input:

1. A 40 x 30 x 10 box, a boss r 2 x 4 at (6, 6) on top, and a sketch on the top face with
   one line from (6, 6) to (34, 24) (the path).
2. CREATE > Pattern > Pattern on Path with nothing selected: waits. Click the boss's step in
   the timeline, the Path box, the sketch line: a copy 20 mm along the line (Extent, 2).
3. Quantity 4, Distance 30: bosses every 10 mm along the line. Symmetric: the copies would
   run off the start of the line: the dialog says so, OK waits, nothing is printed in the
   Report view. Back to One Direction; OK. Ctrl+Z / Ctrl+Y. Edit from the timeline:
   Quantity 3. OK.
4. Rectangular Pattern, Pattern Type Bodies: click the part, the Direction box, the X axis:
   Spacing 50, Quantity 3: two new bodies 50 and 100 mm along X. OK. Ctrl+Z removes them,
   Ctrl+Y brings them back. Edit: Quantity 2: one new body is left.

Hand-derived: box 12000; a boss pi 2^2 4 = 16 pi. Along the line (28, 18) / |(28, 18)| a copy
at s mm is at (6, 6) + s (28, 18) / 33.2866.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
import Part
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import pattern_steps as ps

V = App.Vector
s = {}
BOSS = math.pi * 4.0 * 4.0
LINE = (28.0, 18.0)
LENGTH = math.hypot(*LINE)


def at(dist):
    return (round(6 + dist * LINE[0] / LENGTH, 4), round(6 + dist * LINE[1] / LENGTH, 4))


def boss_centres():
    return ps.circle_centres(h.body().Shape, 2.0, z=14)


def same(a, b, tol=2e-3):
    return len(a) == len(b) and all(
        abs(p[0] - q[0]) < tol and abs(p[1] - q[1]) < tol for p, q in zip(sorted(a), sorted(b))
    )


# -- the path sketch ------------------------------------------------------------------------------
def path_sketch():
    h.fit()
    h.ribbon("Create Sketch")


def path_click_top():
    h.click(V(30, 8, 10))


def path_draw():
    sk = h.in_sketch()
    h.check("sketch open on the top face", sk is not None)
    if sk is None:
        return
    s["sketch"] = sk.Name
    a = h.to_sketch(sk, V(6, 6, 10))
    c = h.to_sketch(sk, V(6 + LINE[0], 6 + LINE[1], 10))
    sk.addGeometry(Part.LineSegment(V(a[0], a[1], 0), V(c[0], c[1], 0)))
    App.ActiveDocument.recompute()


def path_finish():
    h.ribbon("Finish Sketch")


# -- pattern on path --------------------------------------------------------------------------------
def open_path_pattern():
    Gui.Selection.clearSelection()
    s["v0"] = h.solid_volume()
    ps.menu("Pattern on Path")


def waiting():
    p = ps.panel()
    h.check("Pattern on Path dialog open", p is not None and p.kind == "path")
    if p is None:
        return
    h.check("nothing picked", p.options["objects"] == [] and p.target is None)
    h.check("model unchanged", ps.close(h.solid_volume(), s["v0"]))
    ps.no_popups("Pattern on Path with nothing selected")


def click_boss_step():
    ps.timeline_click("Extrude 2")


def click_path_box():
    ps.click_box("path")


def click_line():
    h.fit()
    h.click_edge(V(6 + LINE[0] * 0.75, 6 + LINE[1] * 0.75, 10))


def path_preview():
    p = ps.panel()
    path = p.options["path"] if p else None
    h.check("the sketch line is the path", path is not None and path[0].Name == s["sketch"], path)
    v = h.solid_volume()
    h.check("one copy (Extent 20, Quantity 2)", ps.close(v, ps.BOX + 2 * BOSS), v)
    h.check(
        "the copy is 20 mm along the line", same(boss_centres(), [at(0), at(20)]), boss_centres()
    )
    h.check("a blue arrow along the path", "distance" in p.handles, list(p.handles))
    h.shot("1-path")


def four():
    p = ps.panel()
    ps.type_quantity(p.quantity, 4)


def distance_30():
    ps.type_value(ps.panel().distance_field.widget, "30")


def four_bosses():
    v = h.solid_volume()
    h.check("4 bosses", ps.close(v, ps.BOX + 4 * BOSS), v)
    h.check("every 10 mm", same(boss_centres(), [at(0), at(10), at(20), at(30)]), boss_centres())
    b.choose(ps.panel().direction_type, "Symmetric")


def symmetric_runs_off():
    p = ps.panel()
    text = p.message.text() if p else ""
    h.check("the dialog says the copies run off the path", "off the end of the path" in text, text)
    # The values are valid but the copies do not fit on the path: a compute failure. Like
    # Fusion, the failed step adds nothing (timeline_ops.settle), the dialog says why and OK
    # waits. (A value the dialog refuses outright keeps the last good preview instead.)
    v = h.solid_volume()
    h.check("the failed pattern adds nothing: the one boss", ps.close(v, ps.BOX + BOSS), v)
    h.shot("2-off-path")
    h.task_button("OK")


def ok_refused():
    h.check("OK waits while the pattern cannot be made", ps.panel() is not None)
    b.choose(ps.panel().direction_type, "One Direction")


def path_ok():
    p = ps.panel()
    h.check("error gone", p and p.message.text() == "", p and p.message.text())
    h.task_button("OK")


def after_ok():
    h.check("dialog closed", not Gui.Control.activeDialog())
    found = ps.patterns("path")
    h.check(
        "one pattern on path, the end of the timeline", len(found) == 1 and h.body().Tip is found[0]
    )
    shape = h.body().Shape
    h.check("4 bosses, valid", ps.close(shape.Volume, ps.BOX + 4 * BOSS) and shape.isValid())
    s["title"] = [t for t in ps.timeline_titles() if "Path" in t]
    h.check("in the timeline", len(s["title"]) == 1, ps.timeline_titles())
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def after_undo():
    h.check("Ctrl+Z: one boss", ps.close(h.solid_volume(), ps.BOX + BOSS) and not ps.patterns())
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def after_redo():
    h.check("Ctrl+Y: 4 bosses", ps.close(h.solid_volume(), ps.BOX + 4 * BOSS))
    h.fit()


def edit():
    if s.get("title"):
        ps.timeline_double_click(s["title"][0])


def edit_open():
    p = ps.panel()
    h.check("the dialog opens on it", p is not None and p.editing)
    if p is None:
        return
    h.check("values shown", p.quantity.value() == 4 and abs(p.distance_field.value() - 30) < 1e-9)
    ps.type_quantity(p.quantity, 3)


def edit_ok():
    h.check("3 bosses: 0, 15, 30", same(boss_centres(), [at(0), at(15), at(30)]), boss_centres())
    h.task_button("OK")


def after_edit():
    h.check("3 bosses", ps.close(h.solid_volume(), ps.BOX + 3 * BOSS), h.solid_volume())
    s["v"] = h.solid_volume()


# -- a pattern of bodies --------------------------------------------------------------------------------
def bodies_start():
    Gui.Selection.clearSelection()
    h.ribbon("Rectangular Pattern")


def choose_bodies():
    b.choose(ps.panel().pattern_type, "Bodies")


def click_part():
    h.fit()
    h.click(V(30, 8, 10))


def click_direction_box():
    p = ps.panel()
    objs = p.options["objects"] if p else []
    h.check(
        "the body is the object", len(objs) == 1 and objs[0][0].TypeId == "PartDesign::Body", objs
    )
    ps.click_box("direction")


def click_x_axis():
    h.fit()
    h.click(V(-15, 0, 0))


def spacing():
    p = ps.panel()
    h.check(
        "X axis picked", p and p.options["direction"] and p.options["direction"][0].Role == "X_Axis"
    )
    b.choose(p.distribution, "Spacing")


def quantity3():
    ps.type_quantity(ps.panel().quantity, 3)


def spacing50():
    ps.type_value(ps.panel().distance_field.widget, "50")


def bodies_preview():
    found = ps.bodies()
    h.check("3 bodies: the original and 2 new ones", len(found) == 3, [x.Label for x in found])
    xs = sorted(round(x.Shape.BoundBox.XMin, 6) for x in found)
    h.check("copies 50 and 100 mm along X", xs == [0.0, 50.0, 100.0], xs)
    h.check(
        "each a copy of the part",
        all(ps.close(x.Shape.Volume, s["v"]) for x in found),
        [x.Shape.Volume for x in found],
    )
    h.shot("3-bodies")
    h.task_button("OK")


def bodies_ok():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("3 bodies", len(ps.bodies()) == 3)
    h.check(
        "Rectangular Pattern 1 in the timeline", "Rectangular Pattern 1" in ps.timeline_titles()
    )
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def bodies_undo():
    h.check("Ctrl+Z: one body", len(ps.bodies()) == 1, [x.Label for x in ps.bodies()])
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def bodies_redo():
    h.check("Ctrl+Y: 3 bodies", len(ps.bodies()) == 3)
    h.fit()


def bodies_edit():
    ps.timeline_double_click("Rectangular Pattern 1")


def bodies_edit_open():
    p = ps.panel()
    h.check(
        "the dialog shows Bodies, 3",
        p and p.pattern_type.currentText() == "Bodies" and p.quantity.value() == 3,
    )
    ps.type_quantity(p.quantity, 2)


def bodies_edit_ok():
    h.check("2 bodies now", len(ps.bodies()) == 2, [x.Label for x in ps.bodies()])
    h.task_button("OK")


def bodies_end():
    found = ps.bodies()
    xs = sorted(round(x.Shape.BoundBox.XMin, 6) for x in found)
    h.check("the copy 50 mm along X", xs == [0.0, 50.0], xs)
    h.check(
        "the original body unchanged",
        ps.close(App.ActiveDocument.getObject("Body").Shape.Volume, s["v"]),
    )
    h.shot("4-end")


h.run(
    "patterns_path",
    b.box_steps("PatternPath")
    + ps.make_boss("boss", (6, 6), 2.0, 4.0, click=V(30, 20, 10))
    + [
        path_sketch,
        path_click_top,
        path_draw,
        path_finish,
        open_path_pattern,
        waiting,
        click_boss_step,
        click_path_box,
        click_line,
        path_preview,
        four,
        distance_30,
        four_bosses,
        symmetric_runs_off,
        ok_refused,
        path_ok,
        after_ok,
        after_undo,
        after_redo,
        edit,
        edit_open,
        edit_ok,
        after_edit,
        bodies_start,
        choose_bodies,
        click_part,
        click_direction_box,
        click_x_axis,
        spacing,
        quantity3,
        spacing50,
        bodies_preview,
        bodies_ok,
        bodies_undo,
        bodies_redo,
        bodies_edit,
        bodies_edit_open,
        bodies_edit_ok,
        bodies_end,
    ],
)
