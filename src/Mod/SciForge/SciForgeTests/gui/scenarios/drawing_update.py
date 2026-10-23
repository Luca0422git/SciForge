# SPDX-License-Identifier: LGPL-2.1-or-later
"""The drawing follows the design (Fusion: a drawing is linked to its design and updates
when the design changes), with real clicks.

The filleted block (drawing_fixtures.block: 60 x 40, R5 corners, the 12 mm hole in the
middle), ISO A3, base view Top at 1:1 at (130, 190). On it, with real clicks: the bottom
edge's dimension (50: the straight part between the fillets), the radius of a corner
fillet (R5), the hole's diameter (12) and a centre mark on the hole.

A  Workspace > Design; the timeline's Fillet 1 double-clicked; radius 8; OK.
B  Workspace > Drawing > the drawing: the corners are R8 arcs on the view; the radius
   dimension reads 8, the bottom edge's 44 (60 - 2 x 8); the hole's is still 12; the
   centre mark is still on the hole; the title block is unchanged.
C  Back in the design, Ctrl+Z (the fillet edit undone): on the drawing R5 and 50 again.
   The Undo rebuilt nothing (undo_fast: FreeCAD put the shapes back), only the drawing's
   views were recomputed (review fix F1, 2026-10-22: the view kept the edited part).
   Ctrl+Y: R8 and 44 again, the same way.
D  The hole moved 10 mm to the right (by script: the subject is the drawing): the centre
   mark goes with it, the diameter dimension still reads 12.
"""

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import drawing_fixtures as fx
from SciForgeTests.gui import drawing_input as d
from SciForgeTests.gui import harness as h

BASE = (130.0, 190.0)
ARC_MID = (25 + 5 * 0.7071067811865476, 15 + 5 * 0.7071067811865476)
state = {}


def new_design():
    s.new_design("Upd")()
    fx.block(App.ActiveDocument)
    h.fit()


def base():
    return d.bases()[0]


def at(u, v):
    from sciforge import drawing

    return drawing.local_to_page(base(), (u, v))


def dims():
    from sciforge import drawing

    page = d.page()
    return [o for o in drawing.annotations(page) if o.TypeId == drawing.DIMENSION] if page else []


def by_type():
    from sciforge import drawing

    return {dim.Type: round(drawing.dimension_value(dim), 6) for dim in dims()}


def arcs(radius):
    found = []
    for edge in base().getVisibleEdges(False):
        curve = edge.Curve
        if curve.__class__.__name__ == "Circle" and abs(curve.Radius - radius) < 1e-6:
            found.append(edge)
    return found


def marks():
    from sciforge import drawing

    return drawing.center_marks(base())


# -- the dimensions and the centre mark (real clicks) -------------------------------------------
def dimension(name, pick, place):
    def start():
        h.ribbon("Dimension")

    def picked():
        d.click_at(*at(*pick))
        d.move_to(*at(place[0] + 2, place[1] + 2))

    def placed():
        d.click_at(*at(*place))

    def end():
        d.key(QtCore.Qt.Key_Escape)

    picked.wait_ms = 1000
    placed.wait_ms = 1000
    steps = [start, picked, placed, end]
    for step in steps:
        step.__name__ = "%s_%s" % (name, step.__name__)
    return steps


def mark_start():
    h.ribbon("Center Mark")


def mark_pick():
    d.click_at(*at(0, 6))


mark_pick.wait_ms = 1000


def mark_end():
    d.key(QtCore.Qt.Key_Return)


def set_up():
    found = by_type()
    h.check(
        "three dimensions", found == {"DistanceX": 50.0, "Radius": 5.0, "Diameter": 12.0}, found
    )
    h.check("a centre mark on the hole", len(marks()) == 1, marks())
    h.check("R5 corners on the view", len(arcs(5.0)) == 4, len(arcs(5.0)))
    from sciforge import drawing

    state["title"] = dict(drawing.title(d.page()))
    state["page"] = d.page().Name
    state["label"] = d.page().Label


# -- A ------------------------------------------------------------------------------------------
def a_design():
    d.workspace("Design")


a_design.wait_ms = 1200


def a_edit():
    h.check("the design's tab", d.page() is None)
    h.fit()
    b.timeline_double_click("Fillet 1")


a_edit.wait_ms = 1500


def a_radius():
    p = b.blend_panel()
    if h.check("editing Fillet 1", p is not None and p.target is not None and not p.created):
        b.type_into(p.radius.widget, "8")


a_radius.wait_ms = 1500


def a_ok():
    h.task_button("OK")


a_ok.wait_ms = 1500


def a_done():
    import math

    body = App.ActiveDocument.getObject("Body")
    # each corner loses (r^2 - pi r^2 / 4) x height more with R8 than with R5
    extra = 4 * ((64 - math.pi * 64 / 4) - (25 - math.pi * 25 / 4)) * fx.HEIGHT
    expect = fx.VOLUME - extra
    h.check("the fillets are R8", abs(body.Shape.Volume - expect) < 1e-3, body.Shape.Volume)


# -- B ------------------------------------------------------------------------------------------
def b_open():
    d.workspace("Drawing", state["label"])


b_open.wait_ms = 2500


def b_followed():
    h.check("the drawing's tab", d.page() is not None and d.page().Name == state["page"])
    h.check("R8 corners on the view", len(arcs(8.0)) == 4, len(arcs(8.0)))
    h.check("no R5 corners left", not arcs(5.0), len(arcs(5.0)))
    found = by_type()
    h.check("the radius reads 8", found.get("Radius") == 8.0, found)
    h.check("the bottom edge reads 44", found.get("DistanceX") == 44.0, found)
    h.check("the hole still 12", found.get("Diameter") == 12.0, found)
    m = marks()
    h.check(
        "the centre mark still on the hole",
        len(m) == 1 and abs(m[0]["c"][0]) < 1e-6 and abs(m[0]["c"][1]) < 1e-6,
        m,
    )
    from sciforge import drawing

    h.check("the title block unchanged", dict(drawing.title(d.page())) == state["title"])
    h.shot("b-followed")


# -- C ------------------------------------------------------------------------------------------
def c_design():
    d.workspace("Design")


c_design.wait_ms = 1200


def undo_stats():
    from sciforge import undo_fast

    return dict(undo_fast.stats)


def c_undo():
    state["stats"] = undo_stats()
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


c_undo.wait_ms = 1500


def c_undone():
    body = App.ActiveDocument.getObject("Body")
    h.check(
        "the fillets are R5 again", abs(body.Shape.Volume - fx.VOLUME) < 1e-3, body.Shape.Volume
    )
    d.workspace("Drawing", state["label"])


c_undone.wait_ms = 2500


def fast(what):
    before, after = state["stats"], undo_stats()
    h.check(
        "%s rebuilt nothing (the shapes were put back)" % what,
        after["skipped"] > before["skipped"] and after["rebuilt"] == before["rebuilt"],
        (before, after),
    )


def c_followed():
    found = by_type()
    h.check("R5 corners on the view again", len(arcs(5.0)) == 4, len(arcs(5.0)))
    h.check("the radius reads 5 again", found.get("Radius") == 5.0, found)
    h.check("the bottom edge reads 50 again", found.get("DistanceX") == 50.0, found)
    fast("the Undo")


def c_redo():
    state["stats"] = undo_stats()
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


c_redo.wait_ms = 1500


def c_redone():
    import math

    body = App.ActiveDocument.getObject("Body")
    extra = 4 * ((64 - math.pi * 64 / 4) - (25 - math.pi * 25 / 4)) * fx.HEIGHT
    h.check(
        "the fillets are R8 again", abs(body.Shape.Volume - (fx.VOLUME - extra)) < 1e-3, body.Shape.Volume
    )
    d.workspace("Drawing", state["label"])


c_redone.wait_ms = 2500


def c_followed_redo():
    found = by_type()
    h.check("after Ctrl+Y, R8 corners on the view", len(arcs(8.0)) == 4, len(arcs(8.0)))
    h.check("after Ctrl+Y, the radius reads 8", found.get("Radius") == 8.0, found)
    h.check("after Ctrl+Y, the bottom edge reads 44", found.get("DistanceX") == 44.0, found)
    fast("the Redo")


# -- D ------------------------------------------------------------------------------------------
def d_move():
    doc = App.ActiveDocument
    hole = doc.getObject("Hole")
    hole.Placement.Base = App.Vector(fx.LENGTH / 2.0 + 10.0, fx.WIDTH / 2.0, 0)
    doc.recompute()


d_move.wait_ms = 2500


def d_followed():
    m = marks()
    h.check(
        "the centre mark went with the hole",
        len(m) == 1 and abs(m[0]["c"][0] - 10.0) < 1e-6 and abs(m[0]["c"][1]) < 1e-6,
        m,
    )
    h.check("its circle is the hole's (R6)", len(m) == 1 and abs(m[0]["r"] - 6.0) < 1e-6, m)
    h.check("two lines", len(m) == 1 and len(base().CosmeticEdges) == 2, len(base().CosmeticEdges))
    found = by_type()
    h.check("the diameter still reads 12", found.get("Diameter") == 12.0, found)
    h.shot("d-hole-moved")


h.run(
    "drawing_update",
    [new_design]
    + d.drawing_steps("sheet", base_at=BASE, scale="1:1", orientation="Top", style="Visible Edges")
    + dimension("length", (0, -20), (0, -32))
    + dimension("radius", ARC_MID, (40, 32))
    + dimension("hole", (0, 6), (22, 28))
    + [mark_start, mark_pick, mark_end, set_up]
    + [a_design, a_edit, a_radius, a_ok, a_done]
    + [b_open, b_followed]
    + [c_design, c_undo, c_undone, c_followed]
    + [c_design, c_redo, c_redone, c_followed_redo]
    + [d_move, d_followed],
)
