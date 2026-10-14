# SPDX-License-Identifier: LGPL-2.1-or-later
"""One Dimension command that picks the right kind (DIMENSIONS > Dimension, D), with
real clicks on the sheet.

The filleted block (drawing_fixtures.block), ISO A3, base view Top at 1:1 at (150, 180),
visible edges only: 60 x 40 with R5 corners (straight edges 50 and 30 long) and the 12 mm
hole in the middle.

A  D on the sheet starts Dimension; a click on empty paper says what to pick.
B  The bottom edge: a horizontal dimension 50, placed below. The left edge: vertical 30.
   The hole: a diameter 12. A corner fillet: a radius 5. The bottom edge then the top
   edge: their distance 40. The bottom edge then the left edge: an angle of 90 degrees.
   Esc ends the command. Six dimensions, each its own undo step.
C  Undo removes the last one (the angle); Redo brings it back.
D  DIMENSIONS > Diameter Dimension on a fillet: a diameter 10 (the forced kind).
E  Dimension, an edge picked, Esc: no dimension left behind.
F  An isometric view (added by script at the lower right): Dimension, a click on one of
   its edges: it says an isometric view cannot be dimensioned (Fusion's rule); nothing
   made; Esc.
"""

import math

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import drawing_fixtures as fx
from SciForgeTests.gui import drawing_input as d
from SciForgeTests.gui import harness as h

BASE = (150.0, 180.0)
state = {}


def new_design():
    s.new_design("Dims")()
    fx.block(App.ActiveDocument)
    h.fit()


def base():
    return d.bases()[0]


def at(u, v):
    """A page point of the base view (its own coordinates, from its centre)."""
    from sciforge import drawing

    return drawing.local_to_page(base(), (u, v))


def dims():
    from sciforge import drawing

    page = d.page()
    return [o for o in drawing.annotations(page) if o.TypeId == drawing.DIMENSION] if page else []


def last():
    found = dims()
    return found[-1] if found else None


def value(dim):
    from sciforge import drawing

    return drawing.dimension_value(dim)


# -- A ------------------------------------------------------------------------------------------
def a_key():
    d.click_at(380, 250)  # the sheet gets the keyboard
    d.key("d")


def a_paper():
    p = d.panel_of("DimensionPanel")
    if h.check("D starts the Dimension command", p is not None, d.panel()):
        d.click_at(380, 240)


def a_message():
    p = d.panel_of("DimensionPanel")
    h.check(
        "says what to pick",
        p is not None and "click on an edge" in p.message.text().lower(),
        p and p.message.text(),
    )


# -- B ------------------------------------------------------------------------------------------
def pick_and_place(name, picks, place, kind, expect, tol=1e-6):
    def pick():
        state["count"] = len(dims())
        for u, v in picks:
            d.click_at(*at(u, v))
        d.move_to(*at(place[0] + 2, place[1] + 2))

    def placed():
        d.click_at(*at(*place))

    def check():
        found = dims()
        h.check("%s: one more dimension" % name, len(found) == state["count"] + 1, len(found))
        dim = last()
        if dim is None:
            return
        h.check("%s: %s" % (name, kind), dim.Type == kind, dim.Type)
        h.check("%s: %g" % (name, expect), abs(value(dim) - expect) < tol, value(dim))
        from sciforge import drawing

        x, y = drawing.view_position(base())
        px, py = at(*place)
        h.check(
            "%s: text where clicked" % name,
            abs(dim.X.Value + x - px) < 0.5 and abs(dim.Y.Value + y - py) < 0.5,
            (dim.X, dim.Y),
        )

    pick.__name__ = "b_%s_pick" % name
    placed.__name__ = "b_%s_place" % name
    check.__name__ = "b_%s_check" % name
    pick.wait_ms = 1000
    placed.wait_ms = 1000
    return [pick, placed, check]


ARC_MID = (25 + 5 * math.cos(math.radians(45)), 15 + 5 * math.sin(math.radians(45)))


def b_escape():
    d.key(QtCore.Qt.Key_Escape)


def b_done():
    h.check("Esc ends the command", d.panel() is None, d.panel())
    h.check("six dimensions", len(dims()) == 6, [x.Type for x in dims()])
    h.shot("b-dimensions")


# -- C ------------------------------------------------------------------------------------------
def c_undo():
    d.undo()


def c_undone():
    h.check("undo: five", len(dims()) == 5, len(dims()))
    h.check("the angle went", all(x.Type != "Angle" for x in dims()))
    d.redo()


c_undone.wait_ms = 1200


def c_redone():
    h.check("redo: six", len(dims()) == 6, len(dims()))


# -- D ------------------------------------------------------------------------------------------
def d_forced():
    d.group_menu("DIMENSIONS", "Diameter Dimension")


def d_pick():
    p = d.panel_of("DimensionPanel")
    h.check("Diameter Dimension command", p is not None and p.forced == "diameter", d.panel())
    arc = (-25 - 5 * math.cos(math.radians(45)), -15 - 5 * math.sin(math.radians(45)))
    d.click_at(*at(*arc))
    d.move_to(*at(-45, -32))


d_pick.wait_ms = 1000


def d_place():
    d.click_at(*at(-46, -33))


d_place.wait_ms = 1000


def d_check():
    dim = last()
    h.check(
        "a diameter on the fillet", dim is not None and dim.Type == "Diameter", dim and dim.Type
    )
    h.check("diameter 10", dim is not None and abs(value(dim) - 10.0) < 1e-6, dim and value(dim))
    d.key(QtCore.Qt.Key_Escape)


# -- E ------------------------------------------------------------------------------------------
def e_start():
    state["count"] = len(dims())
    h.ribbon("Dimension")


def e_pick():
    d.click_at(*at(0, 20))
    d.move_to(*at(0, 35))


def e_escape():
    h.check("a preview while picking", len(dims()) == state["count"] + 1, len(dims()))
    d.key(QtCore.Qt.Key_Escape)


def e_second_escape():
    h.check("Esc drops the unplaced one", len(dims()) == state["count"], len(dims()))
    h.check("the command still waits", d.panel_of("DimensionPanel") is not None)
    d.key(QtCore.Qt.Key_Escape)


def e_done():
    h.check("Esc again ends it", d.panel() is None)
    h.check("no dimension left behind", len(dims()) == state["count"], len(dims()))


# -- F ------------------------------------------------------------------------------------------
def f_iso():
    from sciforge import drawing
    from sciforge import drawing_core as core

    state["count"] = len(dims())
    kind = core.projected_kind(1.0, -1.0, d.page().ProjectionType)
    state["iso"] = drawing.add_projected(base(), kind, BASE[0] + 100.0, BASE[1] - 80.0)
    App.ActiveDocument.recompute()


f_iso.wait_ms = 3000


def f_start():
    from sciforge import drawing

    h.check("an isometric view", drawing.is_isometric(state["iso"]), state["iso"].Direction)
    h.check("the base view is not", not drawing.is_isometric(base()))
    h.ribbon("Dimension")


def f_click():
    point = d.edge_point(state["iso"], lambda info: info["kind"] == "line")
    if h.check("an edge of the isometric view", point is not None):
        d.click_at(*point)


f_click.wait_ms = 1000


def f_refused():
    p = d.panel_of("DimensionPanel")
    h.check(
        "says it cannot be dimensioned",
        p is not None and "isometric view cannot be dimensioned" in p.message.text(),
        p and p.message.text(),
    )
    h.check("nothing made", len(dims()) == state["count"], len(dims()))
    d.key(QtCore.Qt.Key_Escape)


def f_done():
    h.check("Esc ends it", d.panel() is None)


h.run(
    "drawing_dimensions",
    [new_design]
    + d.drawing_steps("sheet", base_at=BASE, scale="1:1", orientation="Top", style="Visible Edges")
    + [a_key, a_paper, a_message]
    + pick_and_place("length", [(0, -20)], (0, -32), "DistanceX", 50.0)
    + pick_and_place("height", [(-30, 0)], (-42, 0), "DistanceY", 30.0)
    + pick_and_place("hole", [(0, 6)], (22, 28), "Diameter", 12.0)
    + pick_and_place("fillet", [ARC_MID], (40, 32), "Radius", 5.0)
    + pick_and_place("width", [(10, -20), (10, 20)], (45, 0), "DistanceY", 40.0)
    + pick_and_place("angle", [(-10, -20), (-30, -5)], (-40, -30), "Angle", 90.0, 1e-4)
    + [
        b_escape,
        b_done,
        c_undo,
        c_undone,
        c_redone,
        d_forced,
        d_pick,
        d_place,
        d_check,
        e_start,
        e_pick,
        e_escape,
        e_second_escape,
        e_done,
        f_iso,
        f_start,
        f_click,
        f_refused,
        f_done,
    ],
)
