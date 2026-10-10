# SPDX-License-Identifier: LGPL-2.1-or-later
"""Drawing a sketch with the mouse, like in Fusion, and turning it into a part.

Create Sketch > click the XY plane (camera turns to look at it). L: click four
corners and the start point again (one chained line, closed). D: click the bottom
line, place the dimension, type 50, Enter; the same for the right line, 20. C: click
a centre and a point (circle), D on it, type 8 (diameter). Finish Sketch while the
line tool is still running (the camera goes back). E extrudes the plate with its hole.
Undo / redo, then double-click the sketch in the timeline, double-click the 50
dimension, type 60, Finish: the part follows. No pop-up, no error anywhere.

Hand-derived: plate 50 x 20 x 10 with a 8 mm hole: V = 50*20*10 - pi*4^2*10;
after the edit 60 x 20: V = 60*20*10 - pi*4^2*10.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si

V = App.Vector
s = {}
HOLE = math.pi * 4.0**2 * 10.0


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("SketchDraw")
    h.fit()
    s["camera"] = h.view().getCameraOrientation()


def create_sketch():
    h.ribbon("Create Sketch")


def pick_xy_plane():
    h.check("no pop-up after Create Sketch", not h.popups(), h.popups())
    h.click(V(12, -8, 0))


def sketch_is_open():
    from sciforge import shell, sketch_mode

    sk = h.in_sketch()
    s["sk"] = sk
    h.check("sketch open on the XY plane", sk is not None)
    h.check("no pop-up", not h.popups(), h.popups())
    direction = h.view().getViewDirection()
    h.check(
        "camera looks straight at the sketch (Look At)",
        si.vnear(direction, V(0, 0, -1), 1e-6),
        direction,
    )
    h.check("SKETCH tab shown", shell.ribbon().current_tab() == "sketch")
    h.check("sketch palette shown", si.palette() is not None and si.palette().isVisible())
    h.check("Fusion sketch mode on", sketch_mode.current() is not None)
    h.shot("1-open")


def line_key():
    h.press("l")


def line_p1():
    si.click(V(0, 0, 0))


def line_p2():
    si.click(V(40, 0, 0))


def line_p3():
    si.click(V(40, 30, 0))


def line_p4():
    si.click(V(0, 30, 0))


def line_close():
    si.click(V(0, 0, 0))  # back on the start point closes the chain


def chain_checks():
    sk = s["sk"]
    lines = si.lines(sk)
    h.check("one chained line made 4 lines", len(lines) == 4, [g for _, g in lines])
    # each line starts where the previous ends (coincident constraints)
    coincident = [c for c in sk.Constraints if c.Type == "Coincident"]
    h.check("the lines are joined (coincident)", len(coincident) >= 4, si.constraint_types(sk))
    hv = [c for c in sk.Constraints if c.Type in ("Horizontal", "Vertical", "PointOnObject")]
    h.check("lines snapped horizontal/vertical", len(hv) >= 3, si.constraint_types(sk))
    from sciforge import sketch_mode

    h.check("closed shape shaded as a profile", sketch_mode.current().shading.count == 1)
    h.shot("2-chain")


def esc_once():
    h.press(QtCore.Qt.Key_Escape)


def esc_twice():
    h.check("Esc keeps the sketch open", h.in_sketch() is s["sk"])
    h.press(QtCore.Qt.Key_Escape)


def after_esc():
    h.check("second Esc keeps the sketch open too", h.in_sketch() is s["sk"])
    h.check("nothing selected after Esc", not Gui.Selection.getSelectionEx())


def dim_key():
    h.press("d")


def dim_bottom_line():
    si.click(V(20, 0, 0))


def dim_bottom_place():
    si.click(V(20, -8, 0))


def dim_bottom_box():
    from sciforge import sketch_mode

    h.check("no pop-up for the dimension", not h.popups(), h.popups())
    editor = sketch_mode.current().editor
    h.check("dimension box next to the dimension", editor is not None and editor.isVisible())
    h.shot("3-dimension-box")
    si.type_text("50")


def _right_x():
    return max(max(g.StartPoint.x, g.EndPoint.x) for _, g in si.lines(s["sk"]))


def dim_right_line():
    s["right"] = _right_x()
    si.click(V(s["right"], 15, 0))


def dim_right_place():
    si.click(V(s["right"] + 8, 15, 0))


def dim_right_type():
    si.type_text("20")


def dims_check():
    sk = s["sk"]
    xs, ys = [], []
    for _, g in si.lines(sk):
        xs += [g.StartPoint.x, g.EndPoint.x]
        ys += [g.StartPoint.y, g.EndPoint.y]
    width, height = max(xs) - min(xs), max(ys) - min(ys)
    h.check("width typed: 50", si.near(width, 50.0, 1e-6), width)
    h.check("height typed: 20", si.near(height, 20.0, 1e-6), height)
    dims = [c for c in sk.Constraints if c.Type in ("Distance", "DistanceX", "DistanceY")]
    h.check("two dimensions", len(dims) == 2, [(c.Type, c.Value) for c in dims])
    s["box"] = (min(xs), min(ys), max(xs), max(ys))


def circle_key():
    h.press(QtCore.Qt.Key_Escape)
    h.press("c")


def circle_centre():
    x0, y0, x1, y1 = s["box"]
    s["centre"] = V((x0 + x1) / 2, (y0 + y1) / 2, 0)
    si.click(s["centre"])


def circle_radius():
    si.click(s["centre"] + V(5, 0, 0))


def circle_dim_key():
    h.press(QtCore.Qt.Key_Escape)
    h.press("d")


def circle_dim_pick():
    # a point on the circle, away from the centre's horizontal line
    circle = si.circles(s["sk"], construction=False)[0][1]
    r = circle.Radius
    s["centre"] = circle.Center
    si.click(circle.Center + V(r * math.cos(1.0), r * math.sin(1.0), 0))


def circle_dim_place():
    si.click(s["centre"] + V(9, 9, 0))


def circle_dim_type():
    si.type_text("8")


def circle_check():
    h.press(QtCore.Qt.Key_Escape)
    sk = s["sk"]
    circles = si.circles(sk, construction=False)
    h.check("one circle", len(circles) == 1, circles)
    if circles:
        h.check("circle diameter typed: 8", si.near(circles[0][1].Radius, 4.0, 1e-6), circles)
    from sciforge import sketch_mode

    h.check("plate and hole: 2 profiles", sketch_mode.current().shading.count == 2)
    h.shot("4-sketch")


def line_tool_again():
    h.press("l")  # Finish Sketch must work with a tool running


def finish_sketch():
    h.ribbon("Finish Sketch")


def finished():
    h.check("left the sketch", h.in_sketch() is None)
    h.check("no pop-up", not h.popups(), h.popups())
    h.check(
        "camera back where it was before the sketch",
        h.view().getCameraOrientation().isSame(s["camera"], 1e-6),
        (h.view().getCameraOrientation(), s["camera"]),
    )
    h.check(
        "SKETCH tab gone",
        not __import__("sciforge.shell").shell.ribbon().tab_buttons["sketch"].isVisible(),
    )
    h.fit()


def extrude_key():
    h.press("e")


def extrude_pick_plate():
    # Plate + hole are two profiles: like Fusion, Extrude waits for a pick. Click the
    # plate (the ring), away from the hole.
    h.fit()
    x0, y0, x1, y1 = s["box"]
    h.click(s["sk"].getGlobalPlacement().multVec(V(x0 + 3, y0 + 3, 0)))


def extrude_ok():
    from sciforge import extrude_ui

    panel = extrude_ui.ExtrudePanel.last
    h.check("Extrude took the sketch", panel is not None and panel.target is not None)
    h.task_button("OK")


def extruded():
    v = h.solid_volume()
    s["v1"] = v
    expected = 50 * 20 * 10 - HOLE
    h.check("plate with hole: V = 50*20*10 - pi*16*10", si.near(v, expected, 1e-6), (v, expected))
    h.shot("5-part")


def undo():
    h.press("z", QtCore.Qt.ControlModifier)


def undone():
    h.check("undo removes the extrude", h.solid_volume() < 1e-9, h.solid_volume())


def redo():
    h.press("y", QtCore.Qt.ControlModifier)


def redone():
    h.check("redo brings it back", si.near(h.solid_volume(), s["v1"], 1e-6), h.solid_volume())


def edit_from_timeline():
    si.timeline_double_click("Sketch 1")


def editing_again():
    sk = h.in_sketch()
    h.check("double-click in the timeline edits the sketch", sk is s["sk"], sk)
    h.check("no pop-up", not h.popups(), h.popups())
    h.shot("6-edit")


def double_click_dimension():
    sk = s["sk"]
    index = [
        i
        for i, c in enumerate(sk.Constraints)
        if c.Type in ("Distance", "DistanceX") and si.near(c.Value, 50.0, 1e-6)
    ][0]
    point = si.dimension_label(sk, index)
    h.move(h.screen_point(point + V(2, 1, 0)))
    h.move(h.screen_point(point))
    h.double_click(point)


def dimension_box_again():
    from sciforge import sketch_mode

    session = sketch_mode.current()
    h.check("no FreeCAD pop-up on double-click", not h.popups(), h.popups())
    h.close_popups()
    h.check(
        "double-click on a dimension opens the box",
        session is not None and session.editor is not None,
    )
    si.type_text("60")


def finish_again():
    h.ribbon("Finish Sketch")


def part_followed():
    h.check("left the sketch", h.in_sketch() is None)
    v = h.solid_volume()
    expected = 60 * 20 * 10 - HOLE
    h.check("part follows the edited sketch: 60*20*10 - pi*16*10", si.near(v, expected, 1e-6), v)
    h.check("part visible", h.body_visible())
    h.shot("7-edited")


h.run(
    "sketch_draw",
    si.watched(
        [
            new_design,
            create_sketch,
            pick_xy_plane,
            sketch_is_open,
            line_key,
            line_p1,
            line_p2,
            line_p3,
            line_p4,
            line_close,
            chain_checks,
            esc_once,
            esc_twice,
            after_esc,
            dim_key,
            dim_bottom_line,
            dim_bottom_place,
            dim_bottom_box,
            dim_right_line,
            dim_right_place,
            dim_right_type,
            dims_check,
            circle_key,
            circle_centre,
            circle_radius,
            circle_dim_key,
            circle_dim_pick,
            circle_dim_place,
            circle_dim_type,
            circle_check,
            line_tool_again,
            finish_sketch,
            finished,
            extrude_key,
            extrude_pick_plate,
            extrude_ok,
            extruded,
            undo,
            undone,
            redo,
            redone,
            edit_from_timeline,
            editing_again,
            double_click_dimension,
            dimension_box_again,
            finish_again,
            part_followed,
        ]
    ),
)
