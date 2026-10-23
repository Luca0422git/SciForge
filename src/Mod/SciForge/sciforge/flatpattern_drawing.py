# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Bend Table and the Bend Notes of a flat pattern drawing (FreeCAD, no Qt).

Fusion: Tables > Bend Table, then a flat pattern view: a table of the bends (identifier,
direction, angle, radius) is placed and every bend gets its identifier on the view. Here the
identifiers are balloons on the bend centre lines (B1, B2 ... left to right), the table is
drawn like the parts list (drawing_core.table_layout with its own columns).

    flat_views(page)                   the views of the page that show a flat pattern
    bend_rows(fp)                      the table's rows, in identifier order
    add_bend_table(page, view, top_left)   -> (table, balloons)
    bend_at(view, local, reach)        the bend whose centre line passes a view point
    add_bend_note(page, view, index)   Fusion's Bend Note: the bend's direction, angle and
                                       radius written along its centre line

Both follow later edits of the design (refresh, called by drawing.refresh_page).
"""

import json
import math

import FreeCAD as App

from . import drawing, flatpattern
from . import drawing_core as core

TYPE = "BendTable"
NOTE_TYPE = "BendNote"
NOTE_SIZE = 3.5  # mm on the paper, like the drawing's other text
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


def note_text(bend):
    """What a bend note says: direction, angle and inside radius ("UP 90° R 1.00")."""
    angle = ("%.2f" % bend["angle"]).rstrip("0").rstrip(".")
    return "%s %s\u00b0 R %.2f" % ("UP" if bend.get("up") else "DOWN", angle, bend["radius"])


def _centre_local(view, fp, bend):
    """The bend's centre line in the view's own (unscaled) coordinates: two (u, v)."""
    axes = drawing.axes_of(view)
    centre = drawing.centre_of(view)
    place = fp.getGlobalPlacement()
    out = []
    for x, y in bend["centre"]:
        p = place.multVec(App.Vector(x, y, 0.0))
        out.append(core.to_view(axes, centre, (p.x, p.y, p.z)))
    return out


def _to_segment(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = dx * dx + dy * dy
    t = 0.0 if n < 1e-18 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / n))
    return math.hypot(p[0] - a[0] - dx * t, p[1] - a[1] - dy * t)


def bend_at(view, local, reach):
    """Index (identifier order) of the bend whose centre line passes within `reach` of the
    view point `local` (unscaled view coordinates), or None."""
    fp = flat_of(view)
    if fp is None:
        return None
    best = None
    for i, bend in enumerate(_ordered(fp)):
        a, b = _centre_local(view, fp, bend)
        d = _to_segment(local, a, b)
        if d <= reach and (best is None or d < best[0]):
            best = (d, i)
    return None if best is None else best[1]


def note_place(view, fp, bend):
    """(x, y, rotation) of a bend's note on the paper: along its centre line, beside it, the
    text reading left to right or upwards."""
    a, b = [drawing.local_to_page(view, p) for p in _centre_local(view, fp, bend)]
    angle = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
    if angle <= -90.0 + 1e-6:
        angle += 180.0
    elif angle > 90.0 + 1e-6:
        angle -= 180.0
    rad = math.radians(angle)
    side = NOTE_SIZE * 0.9  # beside the line (to its left as the text reads), not on it
    x = (a[0] + b[0]) / 2.0 - math.sin(rad) * side
    y = (a[1] + b[1]) / 2.0 + math.cos(rad) * side
    return x, y, angle


def bend_notes_of(page, view=None):
    out = []
    for obj in drawing.annotations(page):
        if drawing.kind(obj) != NOTE_TYPE:
            continue
        if view is None or drawing.same(getattr(obj, "SciForgeView", None), view):
            out.append(obj)
    return out


def add_bend_note(page, view, index):
    """Fusion's Bend Note on the bend `index` (identifier order) of the flat pattern view.
    Raises drawing.DrawingError."""
    fp = flat_of(view)
    if fp is None:
        raise drawing.DrawingError("Click a bend centre line of a flat pattern view.")
    bends = _ordered(fp)
    if not 0 <= index < len(bends):
        raise drawing.DrawingError("That flat pattern has no such bend.")
    for note in bend_notes_of(page, view):
        if int(getattr(note, "SciForgeBend", -1)) == index:
            raise drawing.DrawingError("That bend has its note already.")
    bend = bends[index]
    x, y, angle = note_place(view, fp, bend)
    note = drawing.add_text(page, [note_text(bend)], (x, y), size=NOTE_SIZE)
    drawing._mark(note, NOTE_TYPE)
    note.Label = "Bend Note"
    drawing._add(note, "App::PropertyLink", "SciForgeView", view)
    drawing._add(note, "App::PropertyInteger", "SciForgeBend", index)
    note.Rotation = angle
    return note


def _refresh_notes(page):
    changed = False
    for note in bend_notes_of(page):
        view = getattr(note, "SciForgeView", None)
        fp = flat_of(view) if drawing.alive(view) else None
        if fp is None:
            continue
        bends = _ordered(fp)
        index = int(getattr(note, "SciForgeBend", -1))
        if not 0 <= index < len(bends):
            continue
        bend = bends[index]
        text = [note_text(bend)]
        if list(note.Text) != text:
            note.Text = text
            changed = True
        x, y, angle = note_place(view, fp, bend)
        old = (note.X.Value, note.Y.Value, note.Rotation.Value)
        if max(abs(old[0] - x), abs(old[1] - y), abs(old[2] - angle)) > 1e-6:
            note.X, note.Y, note.Rotation = x, y, angle
            changed = True
    return changed


def refresh(page):
    """After the design changed: the bend table's rows, its identifiers and the bend notes
    follow the flat pattern (another K-factor, a bend moved). True when anything changed."""
    changed = _refresh_notes(page)
    return _refresh_table(page) or changed


def _refresh_table(page):
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
