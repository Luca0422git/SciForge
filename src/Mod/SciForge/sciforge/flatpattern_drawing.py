# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Bend Table of a flat pattern drawing (FreeCAD, no Qt).

Fusion: Tables > Bend Table, then a flat pattern view: a table of the bends (identifier,
direction, angle, radius) is placed and every bend gets its identifier on the view. Here the
identifiers are balloons on the bend centre lines (B1, B2 ... left to right), the table is
drawn like the parts list (drawing_core.table_layout with its own columns).

    flat_views(page)                   the views of the page that show a flat pattern
    bend_rows(fp)                      the table's rows, in identifier order
    add_bend_table(page, view, top_left)   -> (table, balloons)
"""

import json

import FreeCAD as App

from . import drawing, flatpattern
from . import drawing_core as core

TYPE = "BendTable"
COLUMNS = (
    ("Item", "BEND ID", 16.0),
    ("Direction", "DIRECTION", 22.0),
    ("Angle", "ANGLE", 18.0),
    ("Radius", "RADIUS", 18.0),
    ("KFactor", "K-FACTOR", 18.0),
)


def flat_of(view):
    """The flat pattern a view shows (its only source), or None."""
    sources = [s for s in getattr(view, "Source", []) or [] if drawing.alive(s)]
    if len(sources) == 1 and flatpattern.is_flat_pattern(sources[0]):
        return sources[0]
    return None


def flat_views(page):
    return [v for v in drawing.all_views(page) if flat_of(v) is not None]


def _ordered(fp):
    bends = flatpattern.bends(fp)

    def mid(bend):
        (x1, y1), (x2, y2) = bend["centre"]
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    return sorted(bends, key=lambda b: (round(mid(b)[0], 6), round(mid(b)[1], 6)))


def bend_rows(fp):
    rows = []
    for i, bend in enumerate(_ordered(fp), start=1):
        rows.append(
            {
                "Item": "B%d" % i,
                "Direction": "UP" if bend.get("up") else "DOWN",
                "Angle": ("%.2f" % bend["angle"]).rstrip("0").rstrip(".") + "°",
                "Radius": "%.2f" % bend["radius"],
                "KFactor": "%.2f" % float(fp.KFactor),
            }
        )
    return rows


def bend_table_of(page):
    for obj in drawing.annotations(page):
        if drawing.kind(obj) == TYPE:
            return obj
    return None


def _page_point(view, point):
    """A model point as add_balloon takes it: the view's position + the point's offset in
    the view's own (unscaled) coordinates, as TechDraw keeps a balloon's origin."""
    axes = drawing.axes_of(view)
    centre = drawing.centre_of(view)
    u, v = core.to_view(axes, centre, (point.x, point.y, point.z))
    x, y = drawing.view_position(view)
    return x + u, y + v


def bend_anchors(view, fp):
    """Page points at the middle of each bend centre line (identifier order)."""
    place = fp.getGlobalPlacement()
    out = []
    for bend in _ordered(fp):
        (x1, y1), (x2, y2) = bend["centre"]
        point = place.multVec(App.Vector((x1 + x2) / 2.0, (y1 + y2) / 2.0, 0.0))
        out.append(_page_point(view, point))
    return out


def add_bend_table(page, view, top_left):
    """The bend table of the flat pattern `view` shows, its top left corner at `top_left`,
    and the bend identifiers on the view. Raises drawing.DrawingError."""
    fp = flat_of(view)
    if fp is None:
        raise drawing.DrawingError("Pick a view of a flat pattern (it shows its bends).")
    if bend_table_of(page) is not None:
        raise drawing.DrawingError("This drawing already has a bend table.")
    rows = bend_rows(fp)
    if not rows:
        raise drawing.DrawingError("That flat pattern has no bends.")
    doc = page.Document
    table = doc.addObject(drawing.SYMBOL, "BendTable")
    drawing._mark(table, TYPE)
    drawing._add(table, "App::PropertyLink", "SciForgeView", view)
    table.Label = "Bend Table"
    drawing._add_to_page(page, table)
    layout = core.table_layout(rows, columns=COLUMNS)
    table.Symbol = core.table_svg(layout)
    table.X = top_left[0] + layout["width"] / 2.0
    table.Y = top_left[1] - layout["height"] / 2.0
    drawing._add(table, "App::PropertyString", "SciForgeRows", json.dumps(rows))
    balloons = []
    # each identifier just above the flat, over its bend (offsets in the view's own units)
    top = _half_height(view, fp) + 12.0 / (drawing.scale_of(view) or 1.0)
    _x, y = drawing.view_position(view)
    for row, anchor in zip(rows, bend_anchors(view, fp)):
        spot = (anchor[0], y + top)
        balloons.append(drawing.add_balloon(view, anchor, spot, row["Item"]))
    return table, balloons


def refresh(page):
    """After the design changed: the bend table's rows and its identifiers follow the flat
    pattern (another K-factor, a bend moved). True when anything changed."""
    table = bend_table_of(page)
    if table is None:
        return False
    view = getattr(table, "SciForgeView", None)
    fp = flat_of(view) if drawing.alive(view) else None
    if fp is None:
        return False
    rows = bend_rows(fp)
    changed = False
    if json.dumps(rows) != getattr(table, "SciForgeRows", ""):
        layout = core.table_layout(rows, columns=COLUMNS)
        x = table.X.Value - _old_width(table) / 2.0
        y = table.Y.Value + _old_height(table) / 2.0
        table.Symbol = core.table_svg(layout)
        table.X = x + layout["width"] / 2.0
        table.Y = y - layout["height"] / 2.0
        table.SciForgeRows = json.dumps(rows)
        changed = True
    by_text = {}
    for obj in getattr(view, "InList", []):
        if obj.TypeId == drawing.BALLOON and getattr(obj, "SourceView", None) is view:
            by_text[obj.Text] = obj
    x, y = drawing.view_position(view)
    for row, anchor in zip(rows, bend_anchors(view, fp)):
        balloon = by_text.get(row["Item"])
        if balloon is None:
            continue
        ox, oy = anchor[0] - x, anchor[1] - y
        if abs(balloon.OriginX.Value - ox) > 1e-6 or abs(balloon.OriginY.Value - oy) > 1e-6:
            balloon.OriginX = ox
            balloon.OriginY = oy
            balloon.X = ox
            changed = True
    return changed


def _old_width(table):
    try:
        return core.table_layout(json.loads(table.SciForgeRows), columns=COLUMNS)["width"]
    except Exception:
        return 0.0


def _old_height(table):
    try:
        return core.table_layout(json.loads(table.SciForgeRows), columns=COLUMNS)["height"]
    except Exception:
        return 0.0


def _half_height(view, fp):
    """How far the flat reaches up the view from its centre (the view's own units)."""
    axes = drawing.axes_of(view)
    centre = drawing.centre_of(view)
    bb = fp.Shape.BoundBox
    place = fp.getGlobalPlacement()
    reach = 0.0
    for x in (bb.XMin, bb.XMax):
        for yy in (bb.YMin, bb.YMax):
            p = place.multVec(App.Vector(x, yy, 0.0))
            reach = max(reach, abs(core.to_view(axes, centre, (p.x, p.y, p.z))[1]))
    return reach
