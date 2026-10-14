# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pattern on Path with a Start Point (Fusion: where along the path the pattern starts), only
real input.

Part: the 40 x 30 x 10 box, a boss r 2 x 4 at (10, 8) on top, and a sketch on the top face
with an L of two lines (10, 8) - (34, 8) - (34, 26), 42 mm long: the path.

Path P1, CREATE > Pattern > Pattern on Path with nothing selected: the boss's step clicked in
        the timeline, the Path box, the sketch's row in the browser (the whole L). Quantity 2,
        Distance 21: Start Point shows 0 (the boss sits at the path's start), the copy is 21 mm
        along the L: at (31, 8).
Path P2, Start Point 0.25 typed: the distance is counted from 10.5 mm along the L, (20.5, 8);
        the point 21 mm further is (34, 15.5), so the copy is the boss moved by (13.5, 7.5):
        at (23.5, 15.5). Start Point 1: the copies would run off the end: the dialog says so,
        OK waits. Back to 0.25, OK.
Path P3, Ctrl+Z / Ctrl+Y; the pattern edited from the timeline reads 0.25; Cancel.

Hand-derived: box 12000; a boss pi 2^2 4 = 16 pi.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui
import Part
import Sketcher
from PySide6 import QtTest
from PySide import QtCore, QtWidgets

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import modify2_steps as m
from SciForgeTests.gui import pattern_steps as ps
from SciForgeTests.gui import shell_draft_steps as sd

V = App.Vector
s = {}
BOSS = math.pi * 16.0
BOX = 12000.0


def panel():
    return ps.panel()


def bosses():
    return ps.circle_centres(h.body().Shape, 2.0, z=14)


def same(a, want, tol=2e-3):
    return len(a) == len(want) and all(
        abs(p[0] - q[0]) < tol and abs(p[1] - q[1]) < tol for p, q in zip(sorted(a), sorted(want))
    )


def type_start(text):
    p = panel()
    if p is None:
        return
    spin = p.start_point
    spin.setFocus()
    QtTest.QTest.mouseClick(spin, QtCore.Qt.LeftButton)
    QtTest.QTest.keyClick(spin, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
    QtTest.QTest.keyClicks(spin, text)
    QtTest.QTest.keyClick(spin, QtCore.Qt.Key_Tab)
    QtWidgets.QApplication.processEvents()


# -- the boss and the path ------------------------------------------------------------------------
def boss_sketch():
    h.fit()
    h.ribbon("Create Sketch")


def boss_top():
    h.click(V(30, 22, 10))


def boss_circle():
    sk = h.in_sketch()
    h.check("sketch on the top face", sk is not None)
    if sk is not None:
        x, y = h.to_sketch(sk, V(10, 8, 10))
        h.draw_circle(sk, x, y, 2)


def boss_finish():
    h.ribbon("Finish Sketch")


def boss_extrude():
    h.fit()
    h.press("e")


def boss_height():
    p = b.active_panel()
    field = getattr(getattr(p, "distance", None), "widget", None) if p else None
    if h.check("Extrude open", field is not None):
        b.type_into(field, "4")


def boss_ok():
    h.task_button("OK")


def boss_made():
    v = h.solid_volume()
    h.check("the boss", m.close(v, BOX + BOSS), v)


def path_sketch():
    Gui.Selection.clearSelection()
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def path_top():
    h.click(V(30, 22, 10))


def path_draw():
    sk = h.in_sketch()
    h.check("sketch on the top face", sk is not None)
    if sk is None:
        return
    s["sketch"] = sk.Label
    pts = [V(*h.to_sketch(sk, c), 0) for c in (V(10, 8, 10), V(34, 8, 10), V(34, 26, 10))]
    first = sk.GeometryCount
    sk.addGeometry(Part.LineSegment(pts[0], pts[1]))
    sk.addGeometry(Part.LineSegment(pts[1], pts[2]))
    sk.addConstraint(Sketcher.Constraint("Coincident", first, 2, first + 1, 1))
    App.ActiveDocument.recompute()


def path_finish():
    h.ribbon("Finish Sketch")


# -- P1 -------------------------------------------------------------------------------------------
def pattern_start():
    Gui.Selection.clearSelection()
    h.click_empty()
    s["v0"] = h.solid_volume()
    ps.menu("Pattern on Path")


def click_boss_step():
    p = panel()
    h.check("Pattern on Path waits", p is not None and p.kind == "path")
    ps.timeline_click("Extrude 2")


def click_path_box():
    ps.click_box("path")


def click_sketch_row():
    m.click_row(s.get("sketch", "Sketch"))


def two():
    p = panel()
    if p is None:
        return
    path = p.options.get("path")
    h.check("the whole L is the path", path is not None and path[1] == "", path)
    row = sd.browser().row(s.get("sketch", "Sketch"))
    shown = row.text(1) if row is not None else "?"
    text = p.fields["path"].button.text()
    h.check("the Path box names the sketch as the browser does", text == shown, (text, shown))
    ps.type_quantity(p.quantity, 2)


def distance():
    ps.type_value(panel().distance_field.widget, "21")


def from_start():
    p = panel()
    if p is None:
        return
    h.check("Start Point shows", p.start_point.isVisible())
    h.check("Start Point 0: the boss sits at the start", abs(p.start_point.value()) < 1e-9)
    h.check("the copy 21 mm along the L", same(bosses(), [(10, 8), (31, 8)]), bosses())
    h.check("one copy", m.close(h.solid_volume(), BOX + 2 * BOSS), h.solid_volume())
    h.shot("1-from-start")
    type_start("0.25")


# -- P2 -------------------------------------------------------------------------------------------
def quarter():
    p = panel()
    if p is None:
        return
    h.check("Start Point 0.25 kept", abs(p.start_point.value() - 0.25) < 1e-9)
    h.check("the copy moved by (13.5, 7.5)", same(bosses(), [(10, 8), (23.5, 15.5)]), bosses())
    h.check("no message", not p.message.text(), p.message.text())
    h.shot("2-quarter")
    type_start("1")


def at_end():
    p = panel()
    if p is None:
        return
    text = p.message.text()
    h.check("Start Point 1: the dialog says the copies run off", "path" in text.lower(), text)
    h.task_button("OK")


def ok_waits():
    p = panel()
    h.check("OK waits", p is not None)
    type_start("0.25")


def quarter_again():
    h.check("back to 0.25", same(bosses(), [(10, 8), (23.5, 15.5)]), bosses())
    h.task_button("OK")


def after_ok():
    h.check("dialog closed", m.no_dialog())
    found = ps.patterns()
    h.check("one pattern step", len(found) == 1, found)
    h.check("kept", same(bosses(), [(10, 8), (23.5, 15.5)]), bosses())
    titles = ps.timeline_titles()
    s["title"] = [t for t in titles if "Pattern" in t][-1:] or ["?"]
    h.check("the timeline shows the pattern", s["title"][0] != "?", titles)


# -- P3 -------------------------------------------------------------------------------------------
def undo():
    m.undo()


def after_undo():
    h.check("Ctrl+Z: no copy", same(bosses(), [(10, 8)]), bosses())


def redo():
    m.redo()


def after_redo():
    h.check("Ctrl+Y: the copy is back", same(bosses(), [(10, 8), (23.5, 15.5)]), bosses())
    h.fit()


def edit():
    ps.timeline_double_click(s["title"][0])


def edit_open():
    p = panel()
    h.check("the pattern opens for editing", p is not None and p.editing)
    if p is None:
        return
    h.check("it reads 0.25", abs(p.start_point.value() - 0.25) < 1e-9, p.start_point.value())
    h.task_button("Cancel")


def end():
    h.check("dialog closed", m.no_dialog())
    h.check("unchanged", same(bosses(), [(10, 8), (23.5, 15.5)]), bosses())
    h.check("no errors in the Report view", not sd.report_errors(), sd.report_errors())
    h.shot("3-end")


h.run(
    "modify2_pattern_path",
    sd.box_steps("Modify2Path")
    + [
        boss_sketch,
        boss_top,
        boss_circle,
        boss_finish,
        boss_extrude,
        boss_height,
        boss_ok,
        boss_made,
        path_sketch,
        path_top,
        path_draw,
        path_finish,
        pattern_start,
        click_boss_step,
        click_path_box,
        click_sketch_row,
        two,
        distance,
        from_start,
        quarter,
        at_end,
        ok_waits,
        quarter_again,
        after_ok,
        undo,
        after_undo,
        redo,
        after_redo,
        edit,
        edit_open,
        end,
    ],
)
