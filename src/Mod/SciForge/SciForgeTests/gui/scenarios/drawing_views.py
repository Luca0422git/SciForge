# SPDX-License-Identifier: LGPL-2.1-or-later
"""Base view and projected views (CREATE > Projected View), with real clicks.

The filleted block with a hole (drawing_fixtures.block) on an ISO A3 drawing (first angle
projection), base view Front at 1:1 at (120, 200).

A  Projected View: the base view is the parent (the only one); moving below it shows the
   Top view (first angle: the view from above goes below); a click places it; moving
   right shows the Left view, a click; moving to the lower right an isometric view, a
   click; back over the base view the preview goes; Enter ends. Three views, lined up.
B  Undo removes the three (one step); Redo brings them back.
C  Dragging the base view: the projected views move with it and stay lined up.
D  Double-click the base view: its dialog; Orientation Top turns it and its projected
   views; Cancel puts everything back.
E  A second drawing, ASME (third angle), Automatic views: base, Top above, Right to the
   right and an isometric view, all at the automatic scale.
"""

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import drawing_fixtures as fx
from SciForgeTests.gui import drawing_input as d
from SciForgeTests.gui import harness as h

state = {}
BASE = (120.0, 200.0)


def close(a, b, tol=1e-6):
    return abs(a - b) <= tol


def vclose(v, t, tol=1e-6):
    return all(abs(a - b) <= tol for a, b in zip((v.x, v.y, v.z), t))


def new_design():
    s.new_design("Plate")()
    fx.block(App.ActiveDocument)
    h.fit()


def base():
    found = d.bases()
    return found[0] if found else None


def projected():
    from sciforge import drawing

    b = base()
    return drawing.children_of(b) if b is not None else []


def kinds():
    return sorted(getattr(v, "SciForgeKind", "") for v in projected())


# -- A ------------------------------------------------------------------------------------------
def a_command():
    h.ribbon("Projected View")


def a_below():
    h.check("Projected View dialog", d.panel_of("ProjectedPanel") is not None, d.panel())
    d.move_to(BASE[0] + 3, BASE[1] - 60)


a_below.wait_ms = 1200


def a_top_preview():
    h.check("preview: the Top view (first angle: below)", kinds() == ["Top"], kinds())
    d.click_at(BASE[0] + 3, BASE[1] - 60)


def a_right():
    d.move_to(BASE[0] + 90, BASE[1] - 4)


a_right.wait_ms = 1200


def a_left_preview():
    h.check("preview: the Left view on the right", kinds() == ["Left", "Top"], kinds())
    d.click_at(BASE[0] + 90, BASE[1] - 4)


def a_corner():
    d.move_to(BASE[0] + 90, BASE[1] - 60)


a_corner.wait_ms = 1200


def a_corner_click():
    h.check("preview: an isometric view", len(kinds()) == 3, kinds())
    d.click_at(BASE[0] + 90, BASE[1] - 60)


def a_over_base():
    d.move_to(*BASE)


def a_still_three():
    h.check("over the base view: no preview", len(kinds()) == 3, kinds())
    d.key(QtCore.Qt.Key_Return)


a_still_three.wait_ms = 1500


def a_done():
    h.check("dialog closed", d.panel() is None, d.panel())
    views = {getattr(v, "SciForgeKind", ""): v for v in projected()}
    h.check("Top, Left, isometric", kinds() == ["FrontTopLeft", "Left", "Top"], kinds())
    b = base()
    top, left = views.get("Top"), views.get("Left")
    if top is None or left is None or b is None:
        return
    h.check("Top view lined up below", close(top.X.Value, b.X.Value) and top.Y.Value < b.Y.Value)
    h.check(
        "Left view lined up on the right",
        close(left.Y.Value, b.Y.Value) and left.X.Value > b.X.Value,
    )
    h.check("Top looks down", vclose(top.Direction, (0, 0, 1)), top.Direction)
    h.check("Left looks from the left", vclose(left.Direction, (-1, 0, 0)), left.Direction)
    for v in projected():
        h.check("%s has geometry" % v.Label, d.visible_edge_count(v) > 0)
    h.check("same scale as the base", all(close(v.Scale, b.Scale) for v in projected()))
    h.shot("a-projected")


# -- B ------------------------------------------------------------------------------------------
def b_undo():
    d.undo()


def b_undone():
    h.check("undo: no projected views", kinds() == [], kinds())


def b_redo():
    d.redo()


b_redo.wait_ms = 1500


def b_redone():
    h.check("redo: three again", len(kinds()) == 3, kinds())


# -- C ------------------------------------------------------------------------------------------
def c_drag():
    from sciforge import drawing

    b = base()
    state["start"] = drawing.view_position(b)
    views = {getattr(v, "SciForgeKind", ""): v for v in projected()}
    state["top_dy"] = views["Top"].Y.Value - b.Y.Value
    # grab the base view by its frame, just outside its outline (inside, its faces take
    # the click, as in TechDraw)
    x, y = state["start"]
    half_w, half_h = drawing.view_extent(b)
    point = (x + half_w + 1.5, y + half_h + 1.5)
    state["grab"] = point
    d.drag_page(point, (point[0] + 15, point[1] + 10))


c_drag.wait_ms = 1500


def c_moved():
    from sciforge import drawing

    b = base()
    x, y = drawing.view_position(b)
    sx, sy = state["start"]
    h.check("the base view moved", abs(x - sx) > 5 or abs(y - sy) > 5, ((sx, sy), (x, y)))
    views = {getattr(v, "SciForgeKind", ""): v for v in projected()}
    top, left = views["Top"], views["Left"]
    h.check(
        "Top view followed (lined up)",
        close(top.X.Value, b.X.Value, 1e-4),
        (top.X.Value, b.X.Value),
    )
    h.check("Top view kept its distance", close(top.Y.Value - b.Y.Value, state["top_dy"], 1e-4))
    h.check(
        "Left view followed (lined up)",
        close(left.Y.Value, b.Y.Value, 1e-4),
        (left.Y.Value, b.Y.Value),
    )
    h.shot("c-dragged")


# -- D ------------------------------------------------------------------------------------------
def d_double_click():
    from sciforge import drawing

    b = base()
    x, y = drawing.view_position(b)
    d.double_click_at(x, y)


d_double_click.wait_ms = 1200


def d_dialog():
    p = d.panel_of("BaseViewPanel")
    if not h.check("the base view's dialog", p is not None, d.panel()):
        return
    h.check("editing, not a new view", p.editing)
    d.choose(p.orientation, "Top")


d_dialog.wait_ms = 1500


def d_turned():
    b = base()
    h.check("base view turned to Top", vclose(b.Direction, (0, 0, 1)), b.Direction)
    views = {getattr(v, "SciForgeKind", ""): v for v in projected()}
    h.check(
        "its Top view turned too",
        not vclose(views["Top"].Direction, (0, 0, 1)),
        views["Top"].Direction,
    )
    d.cancel()


d_turned.wait_ms = 1500


def d_restored():
    b = base()
    h.check("Cancel: Front again", vclose(b.Direction, (0, -1, 0)), b.Direction)
    views = {getattr(v, "SciForgeKind", ""): v for v in projected()}
    h.check("Cancel: Top view as before", vclose(views["Top"].Direction, (0, 0, 1)))
    h.check("dialog closed", d.panel() is None)


# -- E ------------------------------------------------------------------------------------------
def e_design_tab():
    d.workspace("Design")


e_design_tab.wait_ms = 800


def e_automatic():
    from sciforge import drawing

    page = d.page()
    h.check("the new drawing is ASME", page is not None and page.ProjectionType == "Third angle")
    views = drawing.all_views(page)
    h.check("four views", len(views) == 4, [v.Label for v in views])
    bases = drawing.base_views(page)
    if not h.check("one base view", len(bases) == 1):
        return
    b = bases[0]
    kids = {getattr(v, "SciForgeKind", ""): v for v in drawing.children_of(b)}
    h.check(
        "Top, Right and an isometric view",
        sorted(kids) == ["FrontTopRight", "Right", "Top"],
        sorted(kids),
    )
    if "Top" in kids and "Right" in kids:
        h.check("third angle: Top above", kids["Top"].Y.Value > b.Y.Value)
        h.check("third angle: Right on the right", kids["Right"].X.Value > b.X.Value)
    title = drawing.title(page)
    h.check("title block scale filled", bool(title.get("Scale")), title)
    h.check("sheet B", title.get("Size") == "B", title)
    h.shot("e-automatic")


e_automatic.wait_ms = 1500


h.run(
    "drawing_views",
    [new_design]
    + d.drawing_steps("first", base_at=BASE, scale="1:1")
    + [
        a_command,
        a_below,
        a_top_preview,
        a_right,
        a_left_preview,
        a_corner,
        a_corner_click,
        a_over_base,
        a_still_three,
        a_done,
        b_undo,
        b_undone,
        b_redo,
        b_redone,
        c_drag,
        c_moved,
        d_double_click,
        d_dialog,
        d_turned,
        d_restored,
        e_design_tab,
    ]
    + d.drawing_steps("auto", standard="ASME", views="Automatic (base, projected, iso)")
    + [e_automatic],
)
