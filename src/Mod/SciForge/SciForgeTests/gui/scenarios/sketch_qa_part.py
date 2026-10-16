# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sketches inside a part made of several features, with Press Pull before and after.
Only real input.

R: click the origin, type 40, Tab, 30, Enter; Finish, E, OK: block 40 x 30 x 10.
Q: click the top face, type 5, OK: 40 x 30 x 15. Create Sketch on the pulled top face,
C: centre, type 10 (diameter), E while the circle tool runs, OK: a boss on top.
Double-click the first sketch in the browser, double-click its 40 dimension, type 50,
Finish: the block, the pulled top and the boss all follow (no error anywhere); Ctrl+Z /
Ctrl+Y once each. Q on the right face, type 5: 55 wide. Edit the boss sketch from the
browser: its diameter 10 -> 12. Every feature stays valid.

Hand-derived: block 40*30*10 = 12000; pulled 40*30*15 = 18000; boss pi*5^2*10;
edited 50*30*15 = 22500 (+ boss); right face +5: 55*30*15 = 24750 (+ boss);
boss 12 wide: pi*6^2*10.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import arrow_input as arrows
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import sketch_input as si

V = App.Vector
X = V(1, 0, 0)
s = {}
BOSS10 = math.pi * 5.0**2 * 10.0
BOSS12 = math.pi * 6.0**2 * 10.0


def esc():
    h.press(QtCore.Qt.Key_Escape)


def invalid_objects():
    return [o.Label for o in App.ActiveDocument.Objects if "Invalid" in o.State]


def presspull():
    from sciforge import presspull_ui

    return presspull_ui.PressPullPanel.last


def volume_is(name, expected):
    v = h.solid_volume()
    h.check(name, si.near(v, expected, 1e-6), (v, expected))
    h.check("%s: every feature valid" % name, not invalid_objects(), invalid_objects())


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("SketchQAPart")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xy():
    pl.click_square("XY_Plane")  # where the square shows (was 12, -8, 0)


def rect_key():
    s["base"] = h.in_sketch()
    h.check("base sketch open", s["base"] is not None)
    h.press("r")


def rect_corner():
    si.click(V(0, 0, 0))


def rect_size():
    si.move_towards(V(12, 9, 0), V(0.8, 0.6, 0))
    si.type_text("40", enter=False)
    si.tab()
    si.type_text("30")


def rect_done():
    esc()
    h.ribbon("Finish Sketch")


def extrude_block():
    h.fit()
    h.press("e")


def block_ok():
    arrows.type_distance("10")  # Extrude starts at 0 (Fusion): type the distance
    h.task_button("OK")


def block():
    volume_is("block 40 x 30 x 10", 12000.0)
    h.fit()
    h.click_empty()
    h.press("q")


def pull_top():
    p = presspull()
    h.check("Q waits for a face", p is not None and not p._closed and p.target is None)
    h.click(V(10, 8, 10))


def pull_type():
    p = presspull()
    h.check("top face picked", p is not None and p.target is not None, p and p.message.text())
    ui.type_into(p.field.widget, "5")


def pull_ok():
    h.task_button("OK")


def pulled():
    volume_is("pulled up: 40 x 30 x 15", 18000.0)
    h.fit()
    h.ribbon("Create Sketch")


def pick_top():
    h.click(V(10, 8, 15))


def circle_key():
    s["boss"] = h.in_sketch()
    h.check("sketch on the pulled top face", s["boss"] is not None)
    if s["boss"] is not None:
        top = s["boss"].getGlobalPlacement().Base.z
        h.check("the sketch sits at z = 15", si.near(top, 15.0, 1e-6), top)
    h.press("c")


def circle_centre():
    si.click(V(20, 15, 15))


def circle_diameter():
    si.move_towards(V(26, 15.3, 15), X)
    si.type_text("10")


def boss_e():
    circles = si.circles(s["boss"], construction=False)
    h.check("circle 10 wide", circles and si.near(circles[0][1].Radius, 5.0), circles)
    h.press("e")  # the circle tool still runs


def boss_ok():
    arrows.type_distance("10")  # Extrude starts at 0 (Fusion): type the distance
    h.check("E finished the sketch", h.in_sketch() is None)
    h.task_button("OK")


def boss():
    volume_is("boss on top", 18000.0 + BOSS10)
    si.browser_double_click(s["base"].Label)


def _double_click_dim(sketch, value):
    index = None
    for i, c in enumerate(sketch.Constraints):
        if c.Type in ("Distance", "DistanceX", "Diameter") and c.Driving:
            if si.near(c.Value, value, 1e-6):
                index = i
    h.check("dimension %g in %s" % (value, sketch.Label), index is not None, sketch.Constraints)
    if index is None:
        return
    point = si.dimension_label(sketch, index)
    h.move(h.screen_point(point + V(2, 1, 0)))
    h.move(h.screen_point(point))
    h.double_click(point)


def base_dimension():
    h.check("editing the first sketch from the browser", h.in_sketch() is s["base"])
    _double_click_dim(s["base"], 40.0)


def base_type():
    from sciforge import sketch_mode

    sess = sketch_mode.current()
    h.check("dimension box", sess is not None and sess.editor is not None)
    si.type_text("50")


def base_finish():
    h.ribbon("Finish Sketch")


def base_edited():
    h.check("sketch closed", h.in_sketch() is None)
    volume_is("block 50 wide, pulled top and boss follow", 22500.0 + BOSS10)
    h.shot("1-edited")
    h.press("z", QtCore.Qt.ControlModifier)


def undone():
    volume_is("one Ctrl+Z: 40 wide again", 18000.0 + BOSS10)
    h.press("y", QtCore.Qt.ControlModifier)


def redone():
    volume_is("one Ctrl+Y: 50 wide again", 22500.0 + BOSS10)
    h.fit()
    h.click_empty()
    h.press("q")


def pull_right():
    h.click(V(50, 15, 4))  # the right face, low (away from the arrow in its middle)


def pull_right_type():
    p = presspull()
    h.check("right face picked", p is not None and p.target is not None, p and p.message.text())
    ui.type_into(p.field.widget, "5")


def pull_right_ok():
    h.task_button("OK")


def pulled_right():
    volume_is("right face +5: 55 wide", 24750.0 + BOSS10)
    si.browser_double_click(s["boss"].Label)


def boss_dimension():
    h.check("editing the boss sketch", h.in_sketch() is s["boss"])
    _double_click_dim(s["boss"], 10.0)


def boss_type():
    from sciforge import sketch_mode

    sess = sketch_mode.current()
    h.check("boss dimension box", sess is not None and sess.editor is not None)
    si.type_text("12")


def boss_finish():
    h.ribbon("Finish Sketch")


def boss_edited():
    h.check("sketch closed", h.in_sketch() is None)
    volume_is("boss 12 wide", 24750.0 + BOSS12)
    h.check("no pop-up", not h.popups(), h.popups())
    h.shot("2-final")


h.run(
    "sketch_qa_part",
    si.watched(
        [
            new_design,
            pick_xy,
            rect_key,
            rect_corner,
            rect_size,
            rect_done,
            extrude_block,
            block_ok,
            block,
            pull_top,
            pull_type,
            pull_ok,
            pulled,
            pick_top,
            circle_key,
            circle_centre,
            circle_diameter,
            boss_e,
            boss_ok,
            boss,
            base_dimension,
            base_type,
            base_finish,
            base_edited,
            undone,
            redone,
            pull_right,
            pull_right_type,
            pull_right_ok,
            pulled_right,
            boss_dimension,
            boss_type,
            boss_finish,
            boss_edited,
        ]
    ),
)
