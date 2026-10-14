# SPDX-License-Identifier: LGPL-2.1-or-later
"""Ordinate, Baseline, Chain and Arc Length dimensions (DIMENSIONS group), with real
clicks.

The plate (drawing_fixtures.plate), ISO A3, base view Top at 1:1: its sharp corner at
(-40, -25) of the view, hole 1's centre at (-20, -10), hole 2's at (20, 10), the R8
corner arc centred at (32, 17).

A  DIMENSIONS > Ordinate Dimension: the corner as the origin, hole 1 then a place above
   (x): 0 at the origin and 20; hole 2 above near the same line (lined up): 60; hole 1
   to the left (y): a 0 for y and 15. Esc drops a picked point, Esc again ends. Five
   ordinate dimensions; Undo takes back the last placing (15 and its 0), Redo.
B  A dimension from the corner to hole 1 (20, made with D), then DIMENSIONS > Baseline
   Dimension: click it near the corner's end, then hole 2: 60 from the corner, stacked
   below the first; Esc.
C  DIMENSIONS > Chain Dimension: the first dimension near hole 1's end, hole 2, the
   bottom right corner: 40 and 20 on the same line as the first; Esc.
D  DIMENSIONS > Arc Length Dimension: a click on a hole (a whole circle) is refused;
   the R8 corner arc then a place: its length 12.57; Esc.
E  The ordinates follow the design: hole 2 moved 5 mm right (by script: the subject is
   the drawing): its ordinate reads 65.
"""

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import drawing2_steps as w
from SciForgeTests.gui import drawing_input as d
from SciForgeTests.gui import harness as h

state = {}
CORNER = (-40.0, -25.0)


def ordinates():
    return w.annotations("ordinate")


def values():
    from sciforge import drawing_annot

    return sorted(
        (drawing_annot.annotation_data(o)["axis"], round(drawing_annot.ordinate_value(o), 3))
        for o in ordinates()
    )


def linear():
    return [x for x in w.dims() if x.Type in ("DistanceX", "DistanceY", "Distance")]


def value(dim):
    from sciforge import drawing

    return round(drawing.dimension_value(dim), 3)


# -- A ------------------------------------------------------------------------------------------
def a_command():
    w.menu("DIMENSIONS", "Ordinate Dimension")


a_command.wait_ms = 1200


def a_origin():
    p = d.panel_of("OrdinatePanel")
    if h.check("the Ordinate dialog", p is not None, d.panel()):
        w.click(*CORNER)


def a_hole1():
    p = d.panel_of("OrdinatePanel")
    h.check("origin taken", p is not None and p.origin is not None, p and p.message.text())
    w.click(*w.hole_top(w.HOLE1))
    w.move(-20.0, 33.0)


def a_place1():
    w.click(-20.0, 35.0)


a_place1.wait_ms = 1200


def a_first():
    h.check("0 and 20 across", values() == [("x", 0.0), ("x", 20.0)], values())
    w.click(*w.hole_top(w.HOLE2))
    w.move(20.0, 33.0)


def a_place2():
    w.click(20.0, 37.5)  # near the first one's line: lined up with it


a_place2.wait_ms = 1200


def a_second():
    from sciforge import drawing_annot

    h.check("60 across", ("x", 60.0) in values(), values())
    lines = {round(drawing_annot.annotation_data(o)["off"][1], 4) for o in ordinates()}
    h.check("all on one line", len(lines) == 1, lines)
    w.click(*w.hole_top(w.HOLE1))
    w.move(-50.0, -10.0)


def a_place3():
    w.click(-55.0, -10.0)


a_place3.wait_ms = 1200


def a_third():
    h.check("0 and 15 up", ("y", 0.0) in values() and ("y", 15.0) in values(), values())
    h.check("five ordinates", len(ordinates()) == 5, values())
    w.click(*w.hole_top(w.HOLE2))  # a point picked...


def a_escape():
    d.key(QtCore.Qt.Key_Escape)  # ...dropped


def a_still():
    h.check("Esc: the command stays", d.panel_of("OrdinatePanel") is not None)
    h.check("nothing placed", len(ordinates()) == 5)
    d.key(QtCore.Qt.Key_Escape)


def a_ended():
    h.check("Esc again ends", d.panel() is None, d.panel())
    d.undo()


a_ended.wait_ms = 1500


def a_undone():
    h.check("undo: the 15 and its 0 go", len(ordinates()) == 3, values())
    d.redo()


a_undone.wait_ms = 1500


def a_redone():
    h.check("redo: five", len(ordinates()) == 5, values())
    h.shot("a-ordinates")


# -- B ------------------------------------------------------------------------------------------
def b_command():
    w.menu("DIMENSIONS", "Baseline Dimension")


b_command.wait_ms = 1200


def b_pick():
    from sciforge import drawing_annot

    first = w.STORE["first"]
    p = d.panel_of("BaselinePanel")
    if not h.check("the Baseline dialog", p is not None, d.panel()):
        return
    # its extension line at the corner's end
    (ax, ay), (bx, by) = drawing_annot.dimension_points(first)
    corner = min(((ax, ay), (bx, by)), key=lambda q: q[0])
    tx, ty = drawing_annot.dimension_line_offset(first)
    d.click_at(corner[0], (corner[1] + ty) / 2.0)


def b_next():
    p = d.panel_of("BaselinePanel")
    h.check("the dimension taken", p is not None and p.base is not None, p and p.message.text())
    state["before"] = [x.Name for x in linear()]
    w.click(*w.hole_top(w.HOLE2))


b_next.wait_ms = 1500


def b_made():
    new = [x for x in linear() if x.Name not in state["before"]]
    if not h.check("one more", len(new) == 1, [x.Name for x in new]):
        return
    dim = new[0]
    h.check("60 from the corner", value(dim) == 60.0, value(dim))
    first = w.STORE["first"]
    h.check("stacked below the first", dim.Y.Value < first.Y.Value - 5.0, (dim.Y, first.Y))
    d.key(QtCore.Qt.Key_Escape)


def b_done():
    h.check("Esc ends", d.panel() is None, d.panel())


# -- C ------------------------------------------------------------------------------------------
def c_command():
    w.menu("DIMENSIONS", "Chain Dimension")


c_command.wait_ms = 1200


def c_pick():
    from sciforge import drawing_annot

    first = w.STORE["first"]
    (ax, ay), (bx, by) = drawing_annot.dimension_points(first)
    end = max(((ax, ay), (bx, by)), key=lambda q: q[0])  # hole 1's end
    tx, ty = drawing_annot.dimension_line_offset(first)
    d.click_at(end[0], (end[1] + ty) / 2.0)
    state["before"] = [x.Name for x in linear()]


def c_hole2():
    w.click(*w.hole_top(w.HOLE2))


c_hole2.wait_ms = 1500


def c_corner():
    w.click(40.0, -25.0)


c_corner.wait_ms = 1500


def c_made():
    new = [x for x in linear() if x.Name not in state["before"]]
    h.check("two more", len(new) == 2, [x.Name for x in new])
    h.check("40 and 20", sorted(value(x) for x in new) == [20.0, 40.0], [value(x) for x in new])
    first = w.STORE["first"]
    h.check(
        "on the first one's line",
        all(abs(x.Y.Value - first.Y.Value) < 1e-6 for x in new),
        [(x.Y.Value, first.Y.Value) for x in new],
    )
    d.key(QtCore.Qt.Key_Escape)


# -- D ------------------------------------------------------------------------------------------
def d_command():
    w.menu("DIMENSIONS", "Arc Length Dimension")


d_command.wait_ms = 1200


def d_circle():
    p = d.panel_of("ArcLengthPanel")
    if h.check("the Arc Length dialog", p is not None, d.panel()):
        w.click(*w.hole_top(w.HOLE1))


def d_refused():
    p = d.panel_of("ArcLengthPanel")
    h.check(
        "a whole circle is refused",
        p is not None and "diameter" in p.message.text(),
        p and p.message.text(),
    )
    w.click(*w.ARC_MID)
    w.move(45.0, 30.0)


def d_place():
    w.click(46.0, 31.0)


d_place.wait_ms = 1200


def d_made():
    found = w.annotations("arc")
    if h.check("an arc length", len(found) == 1, found):
        text = w.describe(found[0])
        h.check("12.57 with the arc sign", text == "⌒12.57", text)
    d.key(QtCore.Qt.Key_Escape)


def d_done():
    h.check("ended", d.panel() is None)
    h.shot("d-all")


# -- E ------------------------------------------------------------------------------------------
def e_move():
    doc = App.ActiveDocument
    hole = doc.getObject("Hole2")
    hole.Placement.Base = App.Vector(65.0, 35.0, 0)
    doc.recompute()


e_move.wait_ms = 3500


def e_followed():
    h.check("hole 2's ordinate reads 65", ("x", 65.0) in values(), values())
    h.check("hole 1's still 20", ("x", 20.0) in values(), values())


h.run(
    "drawing2_ordinate",
    [w.new_design("Ord")]
    + w.sheet_steps()
    + [d.wait_geometry(1500)]
    + [a_command, a_origin, a_hole1, a_place1, a_first, a_place2, a_second, a_place3]
    + [a_third, a_escape, a_still, a_ended, a_undone, a_redone]
    + w.dimension_steps("first", [CORNER, w.hole_top(w.HOLE1)], (-30.0, -40.0), "DistanceX")
    + [b_command, b_pick, b_next, b_made, b_done]
    + [c_command, c_pick, c_hole2, c_corner, c_made]
    + [d_command, d_circle, d_refused, d_place, d_made, d_done]
    + [e_move, e_followed],
)
