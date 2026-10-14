# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shared steps of the drawing2_* scenarios (annotations, sheets, more views): the plate
(drawing_fixtures.plate) on an ISO A3 sheet, its base view Top at 1:1, and real input on
it given in the base view's own coordinates (millimetres from its centre, y up).

The plate's Top view at 1:1 (centre = the plate's middle (40, 25)):
    outline x -40..40, y -25..25; the corner at (40, 25) is an R8 arc (centre (32, 17));
    hole 1 centre (-20, -10), hole 2 centre (20, 10), both radius 5.
Kept outside scenarios/ because every file there is a scenario."""

import math

import FreeCAD as App
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import drawing_fixtures as fx
from SciForgeTests.gui import drawing_input as d
from SciForgeTests.gui import harness as h

BASE = (130.0, 200.0)
HOLE1 = (-20.0, -10.0)
HOLE2 = (20.0, 10.0)
HOLE_R = fx.PLATE_HOLE_R
ARC_CENTRE = (32.0, 17.0)
ARC_R = fx.PLATE_FILLET
ARC_MID = (32.0 + 8.0 * math.cos(math.radians(45)), 17.0 + 8.0 * math.sin(math.radians(45)))
DIA = "⌀"


def new_design(name):
    def new_design():
        s.new_design(name)()
        fx.plate(App.ActiveDocument)
        h.fit()

    new_design.__name__ = "new_design_" + name
    return new_design


def sheet_steps(prefix="sheet", orientation="Top"):
    return d.drawing_steps(
        prefix, base_at=BASE, scale="1:1", orientation=orientation, style="Visible Edges"
    )


def base():
    found = d.bases()
    return found[0] if found else None


def at(u, v, view=None):
    """A page point of a view (the base view by default) from its own coordinates."""
    from sciforge import drawing

    return drawing.local_to_page(view or base(), (u, v))


def hole_top(centre):
    """The top point of a hole's circle in view coordinates (a click there picks the
    circle; its rightmost point is a vertex where TechDraw starts the circle)."""
    return (centre[0], centre[1] + HOLE_R)


def click(u, v, view=None):
    d.click_at(*at(u, v, view))


def move(u, v, view=None):
    d.move_to(*at(u, v, view))


def dims():
    from sciforge import drawing

    page = d.page()
    return [o for o in drawing.annotations(page) if o.TypeId == drawing.DIMENSION] if page else []


def annotations(kind=None):
    from sciforge import drawing_annot

    page = d.page()
    if page is None:
        return []
    found = drawing_annot.annotations_of(page)
    if kind is not None:
        found = [o for o in found if drawing_annot.annotation_kind(o) == kind]
    return found


def label_point(dim):
    from sciforge import drawing

    view = dim.References2D[0][0]
    x, y = drawing.view_position(view)
    return x + dim.X.Value, y + dim.Y.Value


def annotation_point(obj):
    """A page point on an annotation's text or frame (where a person double-clicks)."""
    from sciforge import drawing, drawing_annot

    data = drawing_annot.annotation_data(obj)
    view = drawing_annot.annotation_view(obj, data)
    x, y = drawing.view_position(view) if view is not None else (0.0, 0.0)
    off = data.get("off") or [0.0, 0.0]
    kind = data.get("kind")
    if kind == "fcf":
        return x + off[0] + 2.5, y + off[1]
    if kind == "leader":
        return x + off[0] + 6.0, y + off[1] - 1.0
    return x + off[0], y + off[1]


def dimension_steps(name, picks, place, expect_type=None):
    """Dimension (D): click the picks (base view coordinates), move, click the place,
    Esc. Leaves state[name] = the new dimension."""
    state = {}

    def start():
        state["before"] = [x.Name for x in dims()]
        d.click_at(380, 250)  # the sheet takes the keyboard (empty paper)
        d.key("d")

    def pick():
        for u, v in picks:
            click(u, v)
        move(place[0] + 2.0, place[1] + 2.0)

    pick.wait_ms = 1200

    def put():
        click(*place)

    put.wait_ms = 1200

    def end():
        d.key(QtCore.Qt.Key_Escape)

    def made():
        new = [x for x in dims() if x.Name not in state["before"]]
        if h.check("%s: one dimension made" % name, len(new) == 1, [x.Name for x in new]):
            STORE[name] = new[0]
            if expect_type:
                h.check("%s: %s" % (name, expect_type), new[0].Type == expect_type, new[0].Type)
        h.check("%s: the command ended" % name, d.panel() is None, d.panel())

    steps = [start, pick, put, end, made]
    for step in steps:
        step.__name__ = "%s_%s" % (name, step.__name__)
    return steps


STORE = {}


def menu(group, label):
    """GROUP > label in the DRAWING ribbon, clicked with the mouse."""
    return d.group_menu(group, label)


def panel():
    return d.panel()


def ok():
    return d.ok()


def cancel():
    return d.cancel()


def toggle(box):
    s.toggle(box)


def type_into(widget, text):
    d.type_into(widget, text)


def choose(combo, label):
    d.choose(combo, label)


def describe(obj):
    from sciforge import drawing_annot

    return drawing_annot.describe(obj)


def process():
    QtWidgets.QApplication.processEvents()


def wait(ms):
    QtTest.QTest.qWait(ms)
