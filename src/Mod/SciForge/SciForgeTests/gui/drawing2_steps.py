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


def _near_circle(c, r):
    def test(info):
        return (
            abs(info["center"][0] - c[0]) < 1e-3
            and abs(info["center"][1] - c[1]) < 1e-3
            and abs(info["radius"] - r) < 1e-3
        )

    return test


def furnish():
    """By script, with the same functions the commands use (for the scenarios whose
    subject is what follows: design edits, save and reopen): on the base view a
    diameter dimension of hole 1 toleranced H7 shown as limits, an ordinate dimension
    from the sharp corner to hole 1, a leader on hole 1, a feature control frame on
    hole 2, datum A on the bottom edge, a surface texture on the top edge, automated
    centre marks on the holes, an edge extension at the rounded corner, the arc length
    of the rounded corner, a Slice section through hole 1 (placed right) and an offset
    section through both holes (placed below). Returns {name: object name}."""
    from sciforge import drawing, drawing_annot

    page = d.page()
    view = base()
    doc = page.Document
    made = {}
    elems = drawing_annot.elements(view)

    def edge(kind, test):
        for name, info in elems:
            if info["kind"] == kind and test(info):
                return name
        return None

    def level(y):
        return lambda i: abs(i["p1"][1] - y) < 1e-6 and abs(i["p2"][1] - y) < 1e-6

    hole1 = edge("circle", _near_circle(HOLE1, HOLE_R))
    hole2 = edge("circle", _near_circle(HOLE2, HOLE_R))
    bottom = edge("line", level(-25.0))
    top = edge("line", level(25.0))
    right = edge("line", lambda i: abs(i["p1"][0] - 40) < 1e-6 and abs(i["p2"][0] - 40) < 1e-6)
    arc = edge("arc", lambda i: abs(i["radius"] - ARC_R) < 1e-3)
    corner = drawing_annot.vertex_at(view, (-40.0, -25.0))
    base_pos = drawing.view_position(view)

    def off(u, v):
        p = at(u, v)
        return [p[0] - base_pos[0], p[1] - base_pos[1]]

    def anchor(name, point):
        return drawing_annot.make_anchor(view, name, point)

    doc.openTransaction("Set up")
    dim = drawing.add_dimension(view, [hole1], "Diameter", at(-50.0, 18.0))
    doc.recompute()
    drawing_annot.set_dimension_settings(
        dim, {"tolerance": "Fit", "fit": "H7/g6", "fit_display": "Limits"}
    )
    made["dim"] = dim.Name
    origin = anchor(corner, (-40.0, -25.0))
    drawing_annot.add_ordinate(view, origin, origin, "x", at(-40.0, 34.0))
    made["ordinate"] = drawing_annot.add_ordinate(
        view, origin, anchor(hole1, hole_top(HOLE1)), "x", at(-20.0, 34.0)
    ).Name
    annotations_made = (
        ("leader", {"anchor": anchor(hole1, (-23.0, -14.0)), "off": off(-60.0, -38.0)}),
        ("fcf", {"anchor": anchor(hole2, (25.0, 10.0)), "off": off(50.0, 38.0)}),
        ("datum", {"anchor": anchor(bottom, (10.0, -25.0)), "off": off(10.0, -36.0)}),
        ("texture", {"anchor": anchor(top, (-25.0, 25.0)), "off": off(-25.0, 25.0)}),
        ("arc", {"anchor": anchor(arc, ARC_MID), "off": off(48.0, 32.0)}),
    )
    extra = {
        "leader": {"lines": ["2 HOLES"]},
        "fcf": {
            "fcf": {
                "row1": {
                    "char": "position",
                    "dia": True,
                    "tol": "0.05",
                    "mod": "M",
                    "datums": [["A", ""], ["B", ""]],
                }
            }
        },
        "datum": {"letter": "A"},
        "texture": {"texture": {"kind": "removal", "value": "Ra 3.2"}},
        "arc": {},
    }
    for kind, data in annotations_made:
        data = dict(data, kind=kind, **extra[kind])
        made[kind] = drawing_annot.add_annotation(page, data, view).Name
    drawing.set_auto_marks(view, {"holes": True})
    drawing.add_edge_extension(view, top, right)
    x, y = base_pos
    made["slice"] = drawing.add_section(
        view, (-20.0, 35.0), (-20.0, -35.0), (10.0, 0.0), (x + 85.0, y), depth=("Slice", 0.0)
    ).Name
    made["offset"] = drawing.add_section(
        view,
        (-48.0, -10.0),
        (0.0, -10.0),
        (0.0, -60.0),
        (x, y - 75.0),
        points=[(-48.0, -10.0), (0.0, -10.0), (0.0, 10.0), (48.0, 10.0)],
    ).Name
    doc.recompute()
    doc.commitTransaction()
    return made
