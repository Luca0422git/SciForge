# SPDX-License-Identifier: LGPL-2.1-or-later
"""Changing sketch curves with the mouse and Fusion's keys: T trim, O offset,
X construction, Esc, Ctrl+Z / Ctrl+Y inside the sketch.

C: circle around (0, 20), L: a line across it, T: click the line inside the circle
(that piece goes, two pieces stay). Undo / redo. R: a 30 x 20 rectangle, D: 30;
O with nothing selected waits; click the rectangle: its whole chain is offset, type 3.
X on a line makes it construction. Esc stops a tool without drawing; a second Esc
clears the selection; the sketch stays open. Every step: no error, no pop-up.
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si

V = App.Vector
s = {}


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("SketchModify")
    h.fit()


def create_sketch():
    h.ribbon("Create Sketch")


def pick_xy_plane():
    h.click(V(12, -8, 0))


def circle_key():
    s["sk"] = h.in_sketch()
    h.check("sketch open", s["sk"] is not None)
    h.press("c")


def circle_centre():
    si.click(V(0, 20, 0))


def circle_radius():
    si.click(V(10, 20, 0))


def line_key():
    h.press(QtCore.Qt.Key_Escape)
    h.press("l")


def line_a():
    si.click(V(-20, 25, 0))


def line_b():
    si.click(V(20, 25, 0))


def line_end():
    h.press(QtCore.Qt.Key_Escape)


def drawn():
    sk = s["sk"]
    h.check("circle drawn", len(si.circles(sk, construction=False)) == 1, sk.Geometry)
    h.check("line drawn", len(si.lines(sk)) == 1, sk.Geometry)
    r = si.circles(sk, construction=False)[0][1].Radius
    s["r"] = r
    h.check("circle radius 10 (snapped to the grid)", si.near(r, 10.0, 1e-6), r)


def trim_key():
    h.press("t")


def trim_click():
    si.click(V(2, 25, 0))


def trimmed():
    h.press(QtCore.Qt.Key_Escape)
    sk = s["sk"]
    y = si.lines(sk)[0][1].StartPoint.y if si.lines(sk) else 25.0
    pieces = sorted(
        (min(g.StartPoint.x, g.EndPoint.x), max(g.StartPoint.x, g.EndPoint.x))
        for _, g in si.lines(sk)
    )
    h.check("trim removed the piece inside the circle: 2 lines", len(pieces) == 2, pieces)
    if len(pieces) == 2:
        # the line y (clicked at 25) meets the circle (0, 20) r 10 at
        # x = +-sqrt(10^2 - (y - 20)^2)
        cut = (10.0**2 - (y - 20.0) ** 2) ** 0.5
        ok = (
            si.near(pieces[0][0], -20, 1e-6)
            and si.near(pieces[0][1], -cut, 1e-6)
            and si.near(pieces[1][0], cut, 1e-6)
            and si.near(pieces[1][1], 20, 1e-6)
        )
        h.check("pieces -20..-cut and cut..20", ok, (pieces, cut))
        h.check(
            "sketch still valid", not s["sk"].MalformedConstraints, s["sk"].MalformedConstraints
        )
    h.shot("1-trim")


def undo_trim():
    h.press("z", QtCore.Qt.ControlModifier)


def trim_undone():
    h.check("Ctrl+Z in the sketch undoes the trim", len(si.lines(s["sk"])) == 1)
    h.check("still in the sketch", h.in_sketch() is s["sk"])


def redo_trim():
    h.press("y", QtCore.Qt.ControlModifier)


def trim_redone():
    h.check("Ctrl+Y trims again", len(si.lines(s["sk"])) == 2)
    s["count"] = len(s["sk"].Geometry)


def rect_key():
    h.press("r")


def rect_a():
    si.click(V(-40, -30, 0))


def rect_b():
    si.click(V(-10, -10, 0))


def rect_done():
    h.press(QtCore.Qt.Key_Escape)
    sk = s["sk"]
    new = [i for i in range(s["count"], len(sk.Geometry))]
    h.check("2-point rectangle: 4 lines", len(new) == 4, new)
    s["rect"] = new
    xs = [p.x for i in new for p in (sk.Geometry[i].StartPoint, sk.Geometry[i].EndPoint)]
    ys = [p.y for i in new for p in (sk.Geometry[i].StartPoint, sk.Geometry[i].EndPoint)]
    s["rect_box"] = (min(xs), min(ys), max(xs), max(ys))
    h.check(
        "rectangle 30 x 20 from the two clicks",
        si.near(max(xs) - min(xs), 30, 1e-6) and si.near(max(ys) - min(ys), 20, 1e-6),
        s["rect_box"],
    )
    hv = [c.Type for c in sk.Constraints if c.First in new and c.Type in ("Horizontal", "Vertical")]
    h.check("rectangle sides horizontal / vertical", len(hv) == 4, hv)
    s["count"] = len(sk.Geometry)


def offset_key():
    h.press("o")


def offset_waits():
    h.check("no pop-up when nothing is selected", not h.popups(), h.popups())
    h.check("still in the sketch", h.in_sketch() is s["sk"])
    x0, y0, x1, y1 = s["rect_box"]
    si.click(V((x0 + x1) / 2, y0, 0))  # the bottom edge


def offset_started():
    from sciforge import sketch_tools_ui

    h.check("the offset tool runs", h.gl_widget().cursor().shape() != QtCore.Qt.ArrowCursor)
    h.check(
        "the whole rectangle chain is offset",
        sketch_tools_ui.last_offset() == s["rect"],
        (sketch_tools_ui.last_offset(), s["rect"]),
    )
    h.shot("2-offset")


def offset_move():
    """Move the pointer away from the rectangle, outside it: the offset follows."""
    x0, y0, x1, y1 = s["rect_box"]
    for d in (1.0, 2.0, 3.0, 4.0):
        h.move(h.screen_point(V((x0 + x1) / 2, y0 - d, 0)))


def offset_type():
    h.shot("2b-offset-preview")
    si.type_text("3")


def offset_done():
    h.press(QtCore.Qt.Key_Escape)
    sk = s["sk"]
    new = [
        i
        for i in range(s["count"], len(sk.Geometry))
        if sk.Geometry[i].TypeId == "Part::GeomLineSegment" and not sk.getConstruction(i)
    ]
    h.check("offset made a second rectangle", len(new) == 4, [sk.Geometry[i] for i in new])
    if len(new) == 4:
        xs = [p.x for i in new for p in (sk.Geometry[i].StartPoint, sk.Geometry[i].EndPoint)]
        ys = [p.y for i in new for p in (sk.Geometry[i].StartPoint, sk.Geometry[i].EndPoint)]
        w, hh = max(xs) - min(xs), max(ys) - min(ys)
        ok = (si.near(w, 36, 1e-6) and si.near(hh, 26, 1e-6)) or (
            si.near(w, 24, 1e-6) and si.near(hh, 14, 1e-6)
        )
        h.check("offset by exactly 3 on every side", ok, (w, hh))
    arcs = [
        i
        for i in range(s["count"], len(sk.Geometry))
        if sk.Geometry[i].TypeId == "Part::GeomArcOfCircle"
    ]
    h.check("sharp corners like Fusion (no arcs)", not arcs, arcs)
    h.shot("3-offset-done")


def select_line():
    si.click(V(-15, 25, 0))


def x_key():
    h.check("line selected", bool(Gui.Selection.getSelectionEx()))
    h.press("x")


def construction_done():
    sk = s["sk"]
    left = [
        i
        for i, g in enumerate(sk.Geometry)
        if g.TypeId == "Part::GeomLineSegment"
        and si.near(g.StartPoint.y, 25, 0.5)
        and min(g.StartPoint.x, g.EndPoint.x) < -12
    ]
    h.check("X made the line construction", left and sk.getConstruction(left[0]), left)
    s["count"] = len(sk.Geometry)


def esc_tool_start():
    h.press(QtCore.Qt.Key_Escape)
    h.press("l")


def esc_tool_click():
    si.click(V(30, -20, 0))


def esc_tool():
    h.press(QtCore.Qt.Key_Escape)


def esc_tool_check():
    h.check("Esc stops the line tool, nothing drawn", len(s["sk"].Geometry) == s["count"])
    h.check("Esc does not close the sketch", h.in_sketch() is s["sk"])
    cursor = h.gl_widget().cursor().shape()
    h.check("no tool running after one Esc", cursor == QtCore.Qt.ArrowCursor, cursor)


def select_again():
    si.click(V(15, 25, 0))


def esc_selection():
    h.check("a line is selected", bool(Gui.Selection.getSelectionEx()))
    h.press(QtCore.Qt.Key_Escape)


def esc_selection_check():
    h.check("Esc clears the selection", not Gui.Selection.getSelectionEx())
    h.check("the sketch is still open", h.in_sketch() is s["sk"])


def finish():
    h.task_button("Finish Sketch")  # the palette's button


def finished():
    h.check("Finish Sketch in the palette closes the sketch", h.in_sketch() is None)
    h.check("no pop-up", not h.popups(), h.popups())


h.run(
    "sketch_modify",
    si.watched(
        [
            new_design,
            create_sketch,
            pick_xy_plane,
            circle_key,
            circle_centre,
            circle_radius,
            line_key,
            line_a,
            line_b,
            line_end,
            drawn,
            trim_key,
            trim_click,
            trimmed,
            undo_trim,
            trim_undone,
            redo_trim,
            trim_redone,
            rect_key,
            rect_a,
            rect_b,
            rect_done,
            offset_key,
            offset_waits,
            offset_started,
            offset_move,
            offset_type,
            offset_done,
            select_line,
            x_key,
            construction_done,
            esc_tool_start,
            esc_tool_click,
            esc_tool,
            esc_tool_check,
            select_again,
            esc_selection,
            esc_selection_check,
            finish,
            finished,
        ]
    ),
)
