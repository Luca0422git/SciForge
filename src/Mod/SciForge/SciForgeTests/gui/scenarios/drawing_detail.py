# SPDX-License-Identifier: LGPL-2.1-or-later
"""Detail View and Break View (CREATE > Detail View / Break View), with real clicks.

The filleted block (drawing_fixtures.block) on an ISO A3 drawing, base view Top at 1:1 at
(130, 190): 60 x 40 mm with R5 corners and the 12 mm hole in the middle.

A  Detail View: click the base view, the centre of a filleted corner (it snaps to the
   fillet's centre), the circle's size (10 mm), then place the detail: DETAIL A at twice
   the base view's scale (2:1), showing the corner. The label typed C: DETAIL C (2:1).
   OK. Undo removes it; Redo brings it back.
B  Detail View, centre clicked, Esc: nothing new.
C  Break View: click the base view, then two points 30 mm apart along it: a broken view
   stands in for it (the original hidden), 30 mm shorter plus the 10 mm gap; the gap
   typed 5; OK.
D  Select the broken view and press Del: the break is gone and the original view is back.
"""

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import drawing_fixtures as fx
from SciForgeTests.gui import drawing_input as d
from SciForgeTests.gui import harness as h

BASE = (130.0, 190.0)
state = {}


def new_design():
    s.new_design("Corner")()
    fx.block(App.ActiveDocument)
    h.fit()


def of_type(type_name):
    from sciforge import drawing

    page = d.page()
    return [v for v in drawing.all_views(page) if v.TypeId == type_name] if page else []


def details():
    from sciforge import drawing

    return of_type(drawing.DETAIL)


def base():
    return d.bases()[0]


def base_pos():
    from sciforge import drawing

    return drawing.view_position(base())


# -- A ------------------------------------------------------------------------------------------
def a_command():
    h.ribbon("Detail View")


def a_view():
    h.check("Detail View dialog", d.panel_of("DetailPanel") is not None, d.panel())
    x, y = base_pos()
    d.click_at(x + 10, y + 5)


def a_centre():
    x, y = base_pos()
    d.click_at(x + 25.6, y + 14.6)  # near the fillet's centre (25, 15)


def a_size():
    x, y = base_pos()
    d.move_to(x + 30, y + 15)
    d.click_at(x + 35, y + 15)


def a_place():
    d.move_to(300, 200)
    d.move_to(310, 210)


a_place.wait_ms = 1500


def a_click():
    h.check("a detail follows the mouse", len(details()) == 1, details())
    d.click_at(310, 210)


a_click.wait_ms = 1500


def a_placed():
    from sciforge import drawing

    found = details()
    if not h.check("one detail view", len(found) == 1, found):
        return
    det = found[0]
    h.check("label A", det.Reference == "A", det.Reference)
    h.check("twice the base scale", abs(det.Scale - 2.0) < 1e-9, det.Scale)
    h.check("caption DETAIL A (2:1)", det.Label == "DETAIL A (2:1)", det.Label)
    anchor = det.AnchorPoint
    h.check(
        "centre snapped to the fillet's centre",
        abs(anchor.x - 25) < 1e-6 and abs(anchor.y - 15) < 1e-6,
        anchor,
    )
    h.check("radius 10", abs(float(det.Radius) - 10.0) < 0.25, det.Radius)
    h.check("placed where clicked", abs(det.X.Value - 310) < 0.5 and abs(det.Y.Value - 210) < 0.5)
    h.check("the detail has geometry", d.visible_edge_count(det) > 0)
    arcs = [
        e
        for e in det.getVisibleEdges(True)
        if e.Curve.__class__.__name__ == "Circle" and abs(e.Curve.Radius - 10.0) < 1e-3
    ]
    h.check(
        "the R5 fillet drawn at 2:1 (R10)",
        len(arcs) >= 1,
        [
            round(e.Curve.Radius, 3)
            for e in det.getVisibleEdges(True)
            if e.Curve.__class__.__name__ == "Circle"
        ],
    )
    p = d.panel_of("DetailPanel")
    if h.check("dialog still open", p is not None):
        d.type_into(p.label, "C")
    del drawing


a_placed.wait_ms = 1200


def a_label():
    det = details()[0]
    h.check(
        "caption DETAIL C (2:1)", det.Reference == "C" and det.Label == "DETAIL C (2:1)", det.Label
    )
    d.ok()


a_label.wait_ms = 1200


def a_undo():
    h.shot("a-detail")
    d.undo()


def a_undone():
    h.check("undo: no detail", not details(), details())
    d.redo()


a_undone.wait_ms = 1500


def a_redone():
    h.check("redo: the detail is back", len(details()) == 1)


# -- B ------------------------------------------------------------------------------------------
def b_command():
    h.ribbon("Detail View")


def b_clicks():
    x, y = base_pos()
    d.click_at(x + 10, y + 5)
    d.click_at(x - 20, y - 10)


def b_escape():
    d.key(QtCore.Qt.Key_Escape)


def b_nothing():
    h.check("Esc: still one detail", len(details()) == 1, details())
    h.check("dialog closed", d.panel() is None)
    h.check("no preview left on the sheet", d.previews_left() == 0, d.previews_left())


# -- C ------------------------------------------------------------------------------------------
def c_command():
    d.group_menu("CREATE", "Break View")


def c_clicks():
    from sciforge import drawing

    h.check("Break View dialog", d.panel_of("BreakPanel") is not None, d.panel())
    x, y = base_pos()
    state["extent"] = drawing.view_extent(base())
    d.click_at(x + 10, y + 5)
    d.click_at(x - 15, y + 2)
    d.move_to(x + 5, y + 2)
    d.click_at(x + 15, y + 2)


c_clicks.wait_ms = 2000


def c_broken():
    from sciforge import drawing

    broken = of_type(drawing.BROKEN)
    if not h.check("a broken view", len(broken) == 1, broken):
        return
    view = broken[0]
    h.check("the original is hidden", not base().Visibility)
    half_w, half_h = drawing.view_extent(view)
    h.check("30 mm shorter plus the 10 mm gap (40 mm long)", abs(2 * half_w - 40.0) < 0.6, half_w)
    h.check("same height", abs(2 * half_h - 40.0) < 0.1, half_h)
    p = d.panel_of("BreakPanel")
    if h.check("dialog open", p is not None):
        d.type_into(p.gap, "5")
        QtCore.QTimer.singleShot(0, lambda: None)


c_broken.wait_ms = 1500


def c_ok():
    d.ok()


c_ok.wait_ms = 2000


def c_gap():
    from sciforge import drawing

    view = of_type(drawing.BROKEN)[0]
    h.check("gap 5", abs(view.Gap.Value - 5.0) < 1e-6, view.Gap)
    half_w, _ = drawing.view_extent(view)
    h.check("35 mm long now", abs(2 * half_w - 35.0) < 0.6, half_w)
    h.shot("c-broken")


# -- D ------------------------------------------------------------------------------------------
def d_select():
    from sciforge import drawing

    view = of_type(drawing.BROKEN)[0]
    x, y = drawing.view_position(view)
    half_w, half_h = drawing.view_extent(view)
    d.click_at(x + half_w + 1.5, y + half_h + 1.5)  # the view's frame


def d_delete():
    from sciforge import drawing

    selected = [o.Name for o in __import__("FreeCADGui").Selection.getSelection()]
    h.check("the broken view is selected", of_type(drawing.BROKEN)[0].Name in selected, selected)
    d.key(QtCore.Qt.Key_Delete)


d_delete.wait_ms = 1500


def d_back():
    from sciforge import drawing

    h.check("no broken view", not of_type(drawing.BROKEN))
    h.check("the original view is back", base().Visibility)
    h.check("the detail stays", len(details()) == 1)


h.run(
    "drawing_detail",
    [new_design]
    + d.drawing_steps("sheet", base_at=BASE, scale="1:1", orientation="Top", style="Visible Edges")
    + [
        a_command,
        a_view,
        a_centre,
        a_size,
        a_place,
        a_click,
        a_placed,
        a_label,
        a_undo,
        a_undone,
        a_redone,
        b_command,
        b_clicks,
        b_escape,
        b_nothing,
        c_command,
        c_clicks,
        c_broken,
        c_ok,
        c_gap,
        d_select,
        d_delete,
        d_back,
    ],
)
