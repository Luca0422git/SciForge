# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's DRAWING workspace as data and maths. Pure Python (no FreeCAD, no Qt), unit tested.

What Fusion does (sources in docs/sciforge/parity/drawings.md):
  * File > New Drawing > From Design: Contents (the components / bodies), Template,
    Standard (ASME / ISO), Units (mm / in), Sheet Size (ISO A4..A0, ASME A..E).
  * ISO drawings use first angle projection, ASME drawings third angle.
  * Base View (orientation, style, scale), Projected Views placed by moving the mouse round
    the parent view (8 directions: 4 orthographic, 4 isometric corners), Section View (a cut
    line, a label A-A), Detail View (a circle, a label, a larger scale), Break View.
  * One Dimension command that picks the right kind from what is clicked.
  * A title block filled from the design; a parts list and balloons for assemblies.
  * Export PDF / DXF.

Here: sheets and scales, the original SciForge title block (an SVG template with
TechDraw's editable fields), where projected and section views go, dimension inference,
parts-list rows and their table, and a small DXF (R12) writer.

Page coordinates are millimetres with the origin at the sheet's bottom left corner and y
up (TechDraw's App side); SVG coordinates have y down and are converted here.
"""

import math
import re
from xml.sax.saxutils import escape

STANDARDS = ("ASME", "ISO")
UNITS = ("mm", "in")
MM_PER_IN = 25.4

# Fusion's sheet sizes (Autodesk "Create Drawing reference"): landscape, millimetres.
SHEETS = {
    "ISO": (
        ("A4", 297.0, 210.0),
        ("A3", 420.0, 297.0),
        ("A2", 594.0, 420.0),
        ("A1", 841.0, 594.0),
        ("A0", 1189.0, 841.0),
    ),
    "ASME": (
        ("A", 279.4, 215.9),
        ("B", 431.8, 279.4),
        ("C", 558.8, 431.8),
        ("D", 863.6, 558.8),
        ("E", 1117.6, 863.6),
    ),
}
DEFAULT_SHEET = {"ISO": "A3", "ASME": "B"}
PROJECTION = {"ISO": "First angle", "ASME": "Third angle"}

# Orientations of a base view (Fusion: the standard views and Home, an isometric view).
# name -> (direction towards the viewer, x direction on the paper), as in TechDraw.
ORIENTATIONS = (
    ("Front", (0.0, -1.0, 0.0), (1.0, 0.0, 0.0)),
    ("Back", (0.0, 1.0, 0.0), (-1.0, 0.0, 0.0)),
    ("Top", (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)),
    ("Bottom", (0.0, 0.0, -1.0), (1.0, 0.0, 0.0)),
    ("Left", (-1.0, 0.0, 0.0), (0.0, -1.0, 0.0)),
    ("Right", (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    (
        "Home",
        (1.0 / math.sqrt(3), -1.0 / math.sqrt(3), 1.0 / math.sqrt(3)),
        (1.0 / math.sqrt(2), 1.0 / math.sqrt(2), 0.0),
    ),
)
ORIENTATION_NAMES = tuple(o[0] for o in ORIENTATIONS)

# Fusion's view styles. Shaded is drawn by TechDraw as faces filled with one colour.
STYLES = (
    "Visible Edges",
    "Visible and Hidden Edges",
    "Shaded",
    "Shaded with Hidden Edges",
)
TANGENT_EDGES = ("Full Length", "Off")

# Standard drawing scales, largest first (ISO 5455 and the inch scales 1:4, 1:8).
SCALES = (
    (50, 1),
    (20, 1),
    (10, 1),
    (5, 1),
    (4, 1),
    (2, 1),
    (1, 1),
    (1, 2),
    (1, 4),
    (1, 5),
    (1, 8),
    (1, 10),
    (1, 20),
    (1, 50),
    (1, 100),
    (1, 200),
)
AUTOMATIC = "Automatic"

# Section and detail labels: letters that are not confused with digits or other marks
# (ASME Y14.3 leaves out I, O and Q; S, X and Z are often left out too).
LABEL_LETTERS = [c for c in "ABCDEFGHJKLMNPRTUVWY"]

DEFAULT_DETAIL_FACTOR = 2.0  # a detail view is drawn twice its parent's scale


# ------------------------------------------------------------------ sheets and scales
def sheet_names(standard):
    return [s[0] for s in SHEETS.get(standard, SHEETS["ISO"])]


def sheet_size(standard, name):
    """(width, height) in mm of a sheet (landscape); the standard's default sheet when the
    name is not one of its sizes."""
    sheets = SHEETS.get(standard, SHEETS["ISO"])
    for sheet, width, height in sheets:
        if sheet == name:
            return width, height
    default = DEFAULT_SHEET.get(standard, "A3")
    for sheet, width, height in sheets:
        if sheet == default:
            return width, height
    return sheets[0][1], sheets[0][2]


def default_standard(units):
    """Inch designs are usually drawn to ASME, millimetre designs to ISO."""
    return "ASME" if units == "in" else "ISO"


def projection_of(standard):
    return PROJECTION.get(standard, "First angle")


def format_scale(value):
    """0.5 -> "1:2", 2 -> "2:1", 1 -> "1:1", 0.4 -> "1:2.5"."""
    if value is None or value <= 0:
        return ""
    for a, b in SCALES:
        if abs(value - float(a) / b) < 1e-9:
            return "%d:%d" % (a, b)
    if value >= 1:
        return "%s:1" % _short(value)
    return "1:%s" % _short(1.0 / value)


def _short(x):
    text = ("%.4f" % x).rstrip("0").rstrip(".")
    return text or "0"


def parse_scale(text):
    """A scale typed by a person: "1:2", "2:1", "1/2", "0.5", "2" -> a number > 0, or None."""
    if text is None:
        return None
    s = str(text).strip().replace(",", ".")
    if not s:
        return None
    try:
        match = re.match(r"^([0-9.]+)\s*[:/]\s*([0-9.]+)$", s)
        if match:
            a, b = float(match.group(1)), float(match.group(2))
            value = a / b if b > 0 else None
        else:
            value = float(s)
    except (ValueError, ZeroDivisionError):
        return None
    if value is None or not (1e-6 < value < 1e6) or math.isnan(value):
        return None
    return value


def scale_choices():
    return [format_scale(float(a) / b) for a, b in SCALES]


def fit_scale(content_w, content_h, area_w, area_h):
    """The largest standard scale at which content_w x content_h (mm at 1:1) fits into
    area_w x area_h; the smallest one when even that does not fit."""
    values = [float(a) / b for a, b in SCALES]
    if content_w <= 0 or content_h <= 0:
        return 1.0
    for value in values:
        if content_w * value <= area_w and content_h * value <= area_h:
            return value
    return values[-1]


# ------------------------------------------------------------------ the title block
# (key, caption, x, y, width, height, value size); x, y = bottom left of the cell, inside
# the title block (its bottom left is 0, 0), millimetres. An original layout.
TITLE_W = 180.0
TITLE_ROW = 9.0
TITLE_H = 4 * TITLE_ROW
TITLE_CELLS = (
    ("Title", "TITLE", 0.0, 27.0, 120.0, 9.0, 5.0),
    ("PartNumber", "PART NUMBER", 120.0, 27.0, 60.0, 9.0, 3.5),
    ("Description", "DESCRIPTION", 0.0, 18.0, 120.0, 9.0, 3.5),
    ("Material", "MATERIAL", 120.0, 18.0, 60.0, 9.0, 3.5),
    ("DrawnBy", "DRAWN BY", 0.0, 9.0, 45.0, 9.0, 3.5),
    ("Date", "DATE", 45.0, 9.0, 35.0, 9.0, 3.5),
    ("CheckedBy", "CHECKED", 80.0, 9.0, 40.0, 9.0, 3.5),
    ("ApprovedBy", "APPROVED", 120.0, 9.0, 60.0, 9.0, 3.5),
    ("Scale", "SCALE", 0.0, 0.0, 30.0, 9.0, 3.5),
    ("Size", "SIZE", 30.0, 0.0, 20.0, 9.0, 3.5),
    ("Sheet", "SHEET", 50.0, 0.0, 25.0, 9.0, 3.5),
    ("Units", "UNITS", 75.0, 0.0, 20.0, 9.0, 3.5),
    ("Revision", "REV", 95.0, 0.0, 15.0, 9.0, 3.5),
)
TITLE_KEYS = tuple(c[0] for c in TITLE_CELLS)
TITLE_CAPTIONS = {c[0]: c[1].title() if c[1] != "REV" else "Revision" for c in TITLE_CELLS}
# Cells that follow the design and the drawing by themselves until a person types into them.
AUTO_KEYS = ("Title", "PartNumber", "Scale", "Size", "Sheet", "Units", "Material")
PROJECTION_CELL = (110.0, 0.0, 30.0, 9.0)
BRAND_CELL = (140.0, 0.0, 40.0, 9.0)
CAPTION_SIZE = 1.8
FONT = "sans-serif"


def frame_margins(standard):
    """(left, bottom, right, top) between the sheet's edge and the drawing frame. ISO
    leaves a wider left edge for binding."""
    if standard == "ISO":
        return 20.0, 10.0, 10.0, 10.0
    return 10.0, 10.0, 10.0, 10.0


def frame_rect(standard, sheet):
    width, height = sheet_size(standard, sheet)
    left, bottom, right, top = frame_margins(standard)
    return left, bottom, width - right, height - top


def title_block_rect(standard, sheet):
    """(x0, y0, x1, y1) of the title block in page mm: bottom right inside the frame."""
    x0, y0, x1, _y1 = frame_rect(standard, sheet)
    width = min(TITLE_W, x1 - x0)
    return x1 - width, y0, x1, y0 + TITLE_H


def drawing_area(standard, sheet, margin=8.0):
    """Where views go: the frame less a margin, above the title block."""
    x0, y0, x1, y1 = frame_rect(standard, sheet)
    _tx0, _ty0, _tx1, ty1 = title_block_rect(standard, sheet)
    return x0 + margin, ty1 + margin, x1 - margin, y1 - margin


def zone_counts(standard, sheet):
    """(columns, rows) of the zone marks round the frame: about 50 mm per zone."""
    x0, y0, x1, y1 = frame_rect(standard, sheet)
    cols = max(2, int(round((x1 - x0) / 50.0)))
    rows = max(2, int(round((y1 - y0) / 50.0)))
    if cols % 2:
        cols += 1
    if rows % 2:
        rows += 1
    return cols, rows


def title_values(
    design="",
    author="",
    date="",
    scale="",
    standard="ISO",
    sheet="A3",
    sheet_number=1,
    sheet_count=1,
    units="mm",
    material="",
    part_number=None,
    description="",
):
    """The title block filled from the design (Fusion fills Part Name, Part Number,
    Created By, Created Date, Drawing Scale, Paper Size, Sheet Number, Material)."""
    return {
        "Title": design or "",
        "PartNumber": design if part_number is None else part_number,
        "Description": description or "",
        "Material": material or "",
        "DrawnBy": author or "",
        "Date": date or "",
        "CheckedBy": "",
        "ApprovedBy": "",
        "Scale": scale or "",
        "Size": sheet or "",
        "Sheet": "%d / %d" % (sheet_number, sheet_count),
        "Units": units or "",
        "Revision": "",
    }


def _svg_y(height, y):
    return height - y


def _text(x, y, size, value, editable=None, anchor="start", weight="normal"):
    attrs = 'x="%.3f" y="%.3f" font-family="%s" font-size="%.2f" font-weight="%s"' % (
        x,
        y,
        FONT,
        size,
        weight,
    )
    if anchor != "start":
        attrs += ' text-anchor="%s"' % anchor
    if editable:
        attrs += ' freecad:editable="%s"' % editable
    return '<text %s fill="#000000"><tspan x="%.3f" y="%.3f">%s</tspan></text>' % (
        attrs,
        x,
        y,
        escape(value or ""),
    )


def _line(x1, y1, x2, y2, width=0.35):
    return (
        '<line x1="%.3f" y1="%.3f" x2="%.3f" y2="%.3f" stroke="#000000" '
        'stroke-width="%.2f" stroke-linecap="round"/>' % (x1, y1, x2, y2, width)
    )


def _rect(x, y, w, h, width=0.35):
    return (
        '<rect x="%.3f" y="%.3f" width="%.3f" height="%.3f" fill="none" stroke="#000000" '
        'stroke-width="%.2f"/>' % (x, y, w, h, width)
    )


def template_primitives(standard, sheet, values=None, title_block=True):
    """Everything the sheet shows, as plain shapes in page mm (y up):
    [("line", x1, y1, x2, y2, width), ("text", x, y, size, text, key or None, anchor),
     ("circle", cx, cy, r, width)]. The SVG template and the DXF export are drawn from
    this one list, so they always agree."""
    values = dict(values or {})
    width, height = sheet_size(standard, sheet)
    fx0, fy0, fx1, fy1 = frame_rect(standard, sheet)
    out = []

    def rect(x0, y0, x1, y1, w=0.35):
        out.append(("line", x0, y0, x1, y0, w))
        out.append(("line", x1, y0, x1, y1, w))
        out.append(("line", x1, y1, x0, y1, w))
        out.append(("line", x0, y1, x0, y0, w))

    rect(fx0, fy0, fx1, fy1, 0.7)  # the drawing frame
    # zone marks: ticks across the margin and letters / numbers between them
    cols, rows = zone_counts(standard, sheet)
    step_x = (fx1 - fx0) / cols
    step_y = (fy1 - fy0) / rows
    left, bottom, right, top = frame_margins(standard)
    tick = 5.0
    for i in range(1, cols):
        x = fx0 + i * step_x
        out.append(("line", x, fy1, x, fy1 + tick, 0.35))
        out.append(("line", x, fy0, x, fy0 - tick, 0.35))
    for i in range(1, rows):
        y = fy0 + i * step_y
        out.append(("line", fx0, y, fx0 - min(tick, left - 2), y, 0.35))
        out.append(("line", fx1, y, fx1 + tick, y, 0.35))
    for i in range(cols):
        x = fx0 + (i + 0.5) * step_x
        label = str(i + 1)
        out.append(("text", x, fy1 + top / 2.0 - 1.2, 3.0, label, None, "middle"))
        out.append(("text", x, fy0 - bottom / 2.0 - 1.2, 3.0, label, None, "middle"))
    for i in range(rows):
        y = fy0 + (i + 0.5) * step_y - 1.2
        label = LABEL_LETTERS[(rows - 1 - i) % len(LABEL_LETTERS)]
        out.append(("text", fx0 - left / 2.0, y, 3.0, label, None, "middle"))
        out.append(("text", fx1 + right / 2.0, y, 3.0, label, None, "middle"))
    if not title_block:
        return out
    tx0, ty0, tx1, ty1 = title_block_rect(standard, sheet)
    scale_x = (tx1 - tx0) / TITLE_W
    rect(tx0, ty0, tx1, ty1, 0.7)
    for key, caption, x, y, w, h, size in TITLE_CELLS:
        cx0 = tx0 + x * scale_x
        cy0 = ty0 + y
        rect(cx0, cy0, cx0 + w * scale_x, cy0 + h, 0.25)
        out.append(("text", cx0 + 1.2, cy0 + h - 2.4, CAPTION_SIZE, caption, None, "start"))
        out.append(("text", cx0 + 1.5, cy0 + 1.8, size, values.get(key, ""), key, "start"))
    # projection symbol (a truncated cone seen from the side and from its end)
    px, py, pw, ph = PROJECTION_CELL
    px0, py0 = tx0 + px * scale_x, ty0 + py
    rect(px0, py0, px0 + pw * scale_x, py0 + ph, 0.25)
    out.extend(projection_symbol(projection_of(standard), px0 + pw * scale_x / 2.0, py0 + ph / 2.0))
    bx, by, bw, bh = BRAND_CELL
    bx0, by0 = tx0 + bx * scale_x, ty0 + by
    rect(bx0, by0, bx0 + bw * scale_x, by0 + bh, 0.25)
    out.append(("text", bx0 + 1.2, by0 + bh - 2.4, CAPTION_SIZE, "STANDARD", None, "start"))
    out.append(
        (
            "text",
            bx0 + 1.5,
            by0 + 1.8,
            3.5,
            "%s  %s" % (standard, "1st angle" if standard == "ISO" else "3rd angle"),
            None,
            "start",
        )
    )
    return out


def projection_symbol(projection, cx, cy, size=6.0):
    """The projection-method symbol: a truncated cone seen from the side (a trapezoid) and
    from its end (two circles). First angle: circles on the right; third angle: on the left."""
    out = []
    small, big = size * 0.25, size * 0.5
    length = size * 1.1
    gap = size * 0.45
    total = length + gap + 2 * big
    left = cx - total / 2.0
    if projection == "First angle":
        tx0, ccx = left, left + length + gap + big
    else:
        ccx, tx0 = left + big, left + 2 * big + gap
    tx1 = tx0 + length
    out.append(("line", tx0, cy - small, tx1, cy - big, 0.25))
    out.append(("line", tx1, cy - big, tx1, cy + big, 0.25))
    out.append(("line", tx1, cy + big, tx0, cy + small, 0.25))
    out.append(("line", tx0, cy + small, tx0, cy - small, 0.25))
    out.append(("circle", ccx, cy, big, 0.25))
    out.append(("circle", ccx, cy, small, 0.25))
    return out


def template_svg(standard, sheet, values=None, title_block=True):
    """An original SciForge sheet as an SVG template for TechDraw: the frame, zone marks,
    the title block with editable fields (freecad:editable) and the projection symbol."""
    width, height = sheet_size(standard, sheet)
    body = []
    for prim in template_primitives(standard, sheet, values, title_block):
        if prim[0] == "line":
            _k, x1, y1, x2, y2, w = prim
            body.append(_line(x1, _svg_y(height, y1), x2, _svg_y(height, y2), w))
        elif prim[0] == "circle":
            _k, cx, cy, r, w = prim
            body.append(
                '<circle cx="%.3f" cy="%.3f" r="%.3f" fill="none" stroke="#000000" '
                'stroke-width="%.2f"/>' % (cx, _svg_y(height, cy), r, w)
            )
        else:
            _k, x, y, size, text, key, anchor = prim
            body.append(_text(x, _svg_y(height, y), size, text, key, anchor))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'xmlns:freecad="https://www.freecad.org/wiki/index.php?title=Svg_Namespace" '
        'version="1.1" width="%smm" height="%smm" viewBox="0 0 %s %s">\n'
        "<!-- SciForge drawing sheet %s %s (original artwork) -->\n"
        '<g id="sciforge-sheet">\n%s\n</g>\n</svg>\n'
        % (
            _short(width),
            _short(height),
            _short(width),
            _short(height),
            standard,
            sheet,
            "\n".join(body),
        )
    )


# ------------------------------------------------------------------ labels
def next_label(used):
    """The next free section / detail letter: A, B, C... then AA, AB..."""
    taken = {str(u).strip().upper() for u in used if u}
    for letter in LABEL_LETTERS:
        if letter not in taken:
            return letter
    for first in LABEL_LETTERS:
        for second in LABEL_LETTERS:
            if first + second not in taken:
                return first + second
    return "?"


# ------------------------------------------------------------------ projected views
# The 8 places round a parent view, counter-clockwise from the right, and the view each one
# shows in third angle projection (ASME). First angle (ISO) mirrors them.
_THIRD_ANGLE_SECTORS = (
    "Right",
    "FrontTopRight",
    "Top",
    "FrontTopLeft",
    "Left",
    "FrontBottomLeft",
    "Bottom",
    "FrontBottomRight",
)
ISOMETRIC_KINDS = ("FrontTopRight", "FrontTopLeft", "FrontBottomLeft", "FrontBottomRight")


def projected_kind(dx, dy, projection):
    """Which projected view a mouse offset (dx, dy) from the parent view's centre makes
    (page mm, y up). Third angle: up shows the Top view; first angle: up shows the Bottom."""
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return None
    if projection == "First angle":
        dx, dy = -dx, -dy
    angle = math.degrees(math.atan2(dy, dx)) % 360.0
    sector = int(((angle + 22.5) % 360.0) // 45.0)
    return _THIRD_ANGLE_SECTORS[sector]


def projected_offset(kind, dx, dy):
    """Where a projected view goes: orthographic views stay lined up with their parent
    (only the distance changes), isometric ones go where the mouse is."""
    if kind in ("Right", "Left"):
        return dx, 0.0
    if kind in ("Top", "Bottom"):
        return 0.0, dy
    return dx, dy


# The side of the paper each orthographic view is seen from, in its parent's paper axes.
_LOOK = {"Right": (1.0, 0.0), "Top": (0.0, 1.0), "Left": (-1.0, 0.0), "Bottom": (0.0, -1.0)}
_ISO = {
    "FrontTopRight": (1.0, 1.0),
    "FrontTopLeft": (-1.0, 1.0),
    "FrontBottomRight": (1.0, -1.0),
    "FrontBottomLeft": (-1.0, -1.0),
}


def projected_axes(parent_axes, kind):
    """TechDraw Direction and XDirection of a projected view of the kind `kind` (Right,
    Top, Left, Bottom or an isometric corner) made from a parent view with axes (X, Y, D)."""
    x, y, d = parent_axes
    if kind in _LOOK:
        look = _LOOK[kind]
        line = {"t": (-look[1], look[0]), "look": look}
        direction, xdir, _normal = section_axes(parent_axes, line)
        return direction, xdir
    sx, sy = _ISO.get(kind, (1.0, 1.0))
    direction = v_unit(v_add(v_add(v_mul(x, sx), v_mul(y, sy)), d))
    xdir = v_unit(v_add(v_mul(x, 1.0), v_mul(d, -sx)))
    return direction, xdir


def outside(dx, dy, half_w, half_h, margin=2.0):
    """The mouse is out of the parent view's box (Fusion shows no projection over it)."""
    return abs(dx) > half_w + margin or abs(dy) > half_h + margin


# ------------------------------------------------------------------ vectors (3D tuples)
def v_add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def v_sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def v_mul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def v_dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def v_cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def v_unit(a):
    length = math.sqrt(v_dot(a, a))
    if length < 1e-12:
        return (0.0, 0.0, 0.0)
    return (a[0] / length, a[1] / length, a[2] / length)


def view_axes(direction, xdirection):
    """(X, Y, D) of a view: X across the paper, Y up the paper, D towards the viewer
    (TechDraw's Direction). X is made square to D."""
    d = v_unit(direction)
    x = v_sub(xdirection, v_mul(d, v_dot(xdirection, d)))
    x = v_unit(x)
    if x == (0.0, 0.0, 0.0):
        x = v_unit(v_cross((0.0, 0.0, 1.0), d)) or (1.0, 0.0, 0.0)
    y = v_cross(d, x)
    return x, y, d


def to_model(axes, centre, u, v):
    """A point of a view (unscaled, relative to the view's centre) in the model."""
    x, y, _d = axes
    return v_add(centre, v_add(v_mul(x, u), v_mul(y, v)))


def to_view(axes, centre, point):
    """A model point in a view's own coordinates (unscaled, from its centre)."""
    x, y, _d = axes
    rel = v_sub(point, centre)
    return v_dot(rel, x), v_dot(rel, y)


def hatch_lines(box, spacing, angle_deg=45.0):
    """Parallel lines at `angle_deg`, `spacing` apart (measured square to them), through
    the origin's family, long enough to cross the box (umin, vmin, umax, vmax): the
    hatching of a section's cut faces before it is trimmed to them."""
    umin, vmin, umax, vmax = box
    if spacing <= 0 or umax < umin or vmax < vmin:
        return []
    a = math.radians(angle_deg)
    d = (math.cos(a), math.sin(a))  # along the lines
    n = (-d[1], d[0])  # square to them
    corners = [(umin, vmin), (umin, vmax), (umax, vmin), (umax, vmax)]
    offsets = [c[0] * n[0] + c[1] * n[1] for c in corners]
    along = [c[0] * d[0] + c[1] * d[1] for c in corners]
    t0, t1 = min(along) - spacing, max(along) + spacing
    first = math.floor(min(offsets) / spacing)
    last = math.ceil(max(offsets) / spacing)
    lines = []
    for k in range(int(first), int(last) + 1):
        o = k * spacing
        base = (n[0] * o, n[1] * o)
        lines.append(
            (
                (base[0] + d[0] * t0, base[1] + d[1] * t0),
                (base[0] + d[0] * t1, base[1] + d[1] * t1),
            )
        )
    return lines


# ------------------------------------------------------------------ section views
def section_line(p1, p2, side, projection):
    """A section line from p1 to p2 (parent view coordinates, 2D) with the view to be
    placed on the side of the point `side`.

    Returns {"t": along the line, "n": towards where the view goes, "look": towards the
    viewer of the section (the arrows point the other way), "mid": the line's middle} or
    None when the line has no length. Third angle: the viewer stands on the side where the
    view goes (like a projected view); first angle: on the other side."""
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return None
    t = (dx / length, dy / length)
    n = (-t[1], t[0])
    mid = ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0)
    if (side[0] - mid[0]) * n[0] + (side[1] - mid[1]) * n[1] < 0:
        n = (-n[0], -n[1])
    look = n if projection != "First angle" else (-n[0], -n[1])
    return {"t": t, "n": n, "look": look, "mid": mid, "length": length}


def section_axes(parent_axes, line):
    """TechDraw Direction and XDirection of a section view cut along `line`
    (section_line) through a parent view with axes (X, Y, D).

    The section view is a projected view turned about the cut line: on the paper the
    line keeps its own direction, and the side towards the viewer of the section shows
    what lies behind the parent view (-D)."""
    x, y, d = parent_axes
    t2, look = line["t"], line["look"]
    big_t = v_add(v_mul(x, t2[0]), v_mul(y, t2[1]))
    behind = v_mul(d, -1.0)
    # (t, look) is an orthonormal pair on the paper: paper x = t.x * t + look.x * look and
    # paper y = t.y * t + look.y * look; t stands for T in the model, look for behind.
    xdir = v_unit(v_add(v_mul(big_t, t2[0]), v_mul(behind, look[0])))
    ydir = v_unit(v_add(v_mul(big_t, t2[1]), v_mul(behind, look[1])))
    direction = v_unit(v_cross(xdir, ydir))
    normal = v_unit(v_add(v_mul(x, look[0]), v_mul(y, look[1])))
    return direction, xdir, normal


def section_offset(line, dx, dy):
    """A section view moves along its viewing side only, lined up with the parent."""
    n = line["n"]
    along = dx * n[0] + dy * n[1]
    return n[0] * along, n[1] * along


# ------------------------------------------------------------------ dimensions
LINEAR_TYPES = ("Distance", "DistanceX", "DistanceY")
_PARALLEL = math.radians(1.0)
_AXIS = math.radians(0.5)


def _direction(pick):
    (x1, y1), (x2, y2) = pick["p1"], pick["p2"]
    return x2 - x1, y2 - y1


def _is_horizontal(dx, dy):
    return (
        abs(math.atan2(dy, dx)) % math.pi < _AXIS or abs(abs(math.atan2(dy, dx)) - math.pi) < _AXIS
    )


def _is_vertical(dx, dy):
    return abs(abs(math.atan2(dy, dx)) - math.pi / 2.0) < _AXIS


def _span_type(p1, p2, place):
    """Two points: horizontal, vertical or aligned, as the place chosen for the text says
    (Fusion: move the mouse above or beside them)."""
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    if abs(dy) < 1e-6:
        return "DistanceX"
    if abs(dx) < 1e-6:
        return "DistanceY"
    if place is None:
        return "Distance"
    x0, x1 = sorted((p1[0], p2[0]))
    y0, y1 = sorted((p1[1], p2[1]))
    px, py = place
    if x0 <= px <= x1 and not (y0 <= py <= y1):
        return "DistanceX"
    if y0 <= py <= y1 and not (x0 <= px <= x1):
        return "DistanceY"
    return "Distance"


def infer_dimension(picks, place=None):
    """The dimension Fusion's single Dimension command makes from what was clicked.

    picks: up to two dicts {"kind": "line" | "circle" | "arc" | "vertex" | "curve",
    "p1", "p2" (lines), "center", "radius" (circles and arcs), "point" (vertices)}.
    Returns {"type": TechDraw type, "use_centers": [index...]} (circles to be taken by
    their centre point), {"need": "more"} when one more pick is needed, or {"error": text}.
    """
    kinds = [p.get("kind") for p in picks]
    if not picks:
        return {"need": "more"}
    if len(picks) == 1:
        kind = kinds[0]
        if kind == "circle":
            return {"type": "Diameter", "use_centers": []}
        if kind == "arc":
            return {"type": "Radius", "use_centers": []}
        if kind == "line":
            dx, dy = _direction(picks[0])
            if _is_horizontal(dx, dy):
                return {"type": "DistanceX", "use_centers": []}
            if _is_vertical(dx, dy):
                return {"type": "DistanceY", "use_centers": []}
            return {"type": _span_type(picks[0]["p1"], picks[0]["p2"], place), "use_centers": []}
        if kind == "vertex":
            return {"need": "more"}
        return {"error": "This curve has no simple size: pick its end points instead."}
    if len(picks) > 2:
        return {"error": "Pick one or two things for a dimension."}
    a, b = picks
    ka, kb = kinds
    if ka == "line" and kb == "line":
        da, db = _direction(a), _direction(b)
        cross = da[0] * db[1] - da[1] * db[0]
        norms = math.hypot(*da) * math.hypot(*db)
        if norms < 1e-12:
            return {"error": "One of the lines has no length."}
        angle = math.asin(max(-1.0, min(1.0, cross / norms)))
        if abs(angle) < _PARALLEL:
            if _is_horizontal(*da):
                return {"type": "DistanceY", "use_centers": []}
            if _is_vertical(*da):
                return {"type": "DistanceX", "use_centers": []}
            return {"type": "Distance", "use_centers": []}
        return {"type": "Angle", "use_centers": []}
    points = []
    centers = []
    for i, pick in enumerate(picks):
        kind = pick.get("kind")
        if kind == "vertex":
            points.append(pick["point"])
        elif kind in ("circle", "arc"):
            points.append(pick["center"])
            centers.append(i)
        elif kind == "line":
            points.append(None)
        else:
            return {"error": "This curve has no simple size: pick its end points instead."}
    if None in points:
        line = picks[points.index(None)]
        dx, dy = _direction(line)
        if _is_horizontal(dx, dy):
            kind = "DistanceY"
        elif _is_vertical(dx, dy):
            kind = "DistanceX"
        else:
            kind = "Distance"
        return {"type": kind, "use_centers": centers}
    if math.hypot(points[1][0] - points[0][0], points[1][1] - points[0][1]) < 1e-6:
        return {"error": "Both picks are at the same point: pick two different places."}
    return {"type": _span_type(points[0], points[1], place), "use_centers": centers}


DIAMETER_SIGN = "\u2300"  # the diameter sign drawn before a diameter's value


def dimension_format(units, standard, dim_type="Distance"):
    """TechDraw's FormatSpec: up to 2 decimals in mm, 3 in inches, no trailing zeros; a
    diameter starts with the diameter sign and a radius with R (Fusion: "\u230012", "R5")."""
    spec = "%.3w" if units == "in" else "%.2w"
    if dim_type == "Diameter":
        return DIAMETER_SIGN + spec
    if dim_type == "Radius":
        return "R" + spec
    return spec


def format_value(value_mm, units):
    """A length as the drawing shows it ("60", "12.5", "2.362")."""
    if units == "in":
        text = "%.3f" % (value_mm / MM_PER_IN)
    else:
        text = "%.2f" % value_mm
    text = text.rstrip("0").rstrip(".")
    if text in ("-0", ""):
        text = "0"
    return text


# ------------------------------------------------------------------ parts list
PARTS_COLUMNS = (
    ("Item", "ITEM", 12.0),
    ("Qty", "QTY", 12.0),
    ("PartNumber", "PART NUMBER", 46.0),
    ("Description", "DESCRIPTION", 46.0),
    ("Material", "MATERIAL", 34.0),
)
ROW_H = 7.0
TABLE_TEXT = 3.0


def parts_rows(components):
    """Parts-list rows from the components of a design, in their order: [{"name",
    "description", "material"}]. Same part numbers are one row with their count (Qty)."""
    rows = []
    by_name = {}
    for comp in components:
        name = comp.get("name") or ""
        if name in by_name:
            by_name[name]["Qty"] += 1
            by_name[name]["members"].append(comp.get("key", name))
            continue
        row = {
            "Item": len(rows) + 1,
            "Qty": 1,
            "PartNumber": name,
            "Description": comp.get("description") or "",
            "Material": comp.get("material") or "",
            "members": [comp.get("key", name)],
        }
        by_name[name] = row
        rows.append(row)
    return rows


def table_layout(rows, columns=PARTS_COLUMNS, header_at_bottom=False):
    """Lines and texts of the parts-list table, origin at its top left corner, y up
    (everything below 0). Fusion flips the header to the bottom when the table sits in
    the lower half of the sheet; the items then count upwards from the header."""
    width = sum(c[2] for c in columns)
    count = len(rows) + 1
    height = count * ROW_H
    lines = []
    texts = []
    for i in range(count + 1):
        y = -i * ROW_H
        lines.append((0.0, y, width, y, 0.5 if i in (0, count) else 0.25))
    x = 0.0
    for _key, _caption, w in columns:
        if x > 0.0:
            lines.append((x, 0.0, x, -height, 0.25))
        x += w
    lines.append((0.0, 0.0, 0.0, -height, 0.5))
    lines.append((width, 0.0, width, -height, 0.5))
    if header_at_bottom:
        header_slot = count - 1
        data_slots = list(range(count - 2, -1, -1))
    else:
        header_slot = 0
        data_slots = list(range(1, count))
    for slot, row in zip(data_slots, rows):
        x = 0.0
        y = -(slot + 1) * ROW_H + 2.0
        for key, _caption, w in columns:
            anchor = "middle" if key in ("Item", "Qty") else "start"
            tx = x + w / 2.0 if anchor == "middle" else x + 1.5
            texts.append((tx, y, TABLE_TEXT, str(row.get(key, "")), anchor))
            x += w
    x = 0.0
    y = -(header_slot + 1) * ROW_H + 2.0
    for _key, caption, w in columns:
        texts.append((x + w / 2.0, y, TABLE_TEXT, caption, "middle"))
        x += w
    return {"width": width, "height": height, "lines": lines, "texts": texts}


def table_svg(layout):
    """The table as an SVG symbol (TechDraw DrawViewSymbol), its top left at (0, 0)."""
    width, height = layout["width"], layout["height"]
    body = []
    for x1, y1, x2, y2, w in layout["lines"]:
        body.append(_line(x1, -y1, x2, -y2, w))
    for x, y, size, text, anchor in layout["texts"]:
        body.append(
            '<text x="%.3f" y="%.3f" font-family="%s" font-size="%.2f" fill="#000000"%s>%s</text>'
            % (
                x,
                -y,
                FONT,
                size,
                ' text-anchor="middle"' if anchor == "middle" else "",
                escape(text),
            )
        )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="%smm" height="%smm" '
        'viewBox="0 0 %s %s">\n%s\n</svg>\n'
        % (_short(width), _short(height), _short(width), _short(height), "\n".join(body))
    )


def balloon_spot(view_center, anchor, half_w, half_h, index, gap=12.0):
    """Where a balloon goes for a component shown at `anchor` (page mm): out of the view's
    box, away from its centre, staggered by index so balloons do not sit on each other."""
    dx, dy = anchor[0] - view_center[0], anchor[1] - view_center[1]
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        dx, dy = 1.0, 1.0
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    # leave the box along (ux, uy)
    tx = (half_w + gap) / abs(ux) if abs(ux) > 1e-9 else float("inf")
    ty = (half_h + gap) / abs(uy) if abs(uy) > 1e-9 else float("inf")
    reach = min(tx, ty)
    x = view_center[0] + ux * reach
    y = view_center[1] + uy * reach + (index % 3) * 2.0
    return x, y


# ------------------------------------------------------------------ DXF (R12) writer
class DxfWriter:
    """A small DXF writer (AutoCAD R12 / AC1009: no handles, read by every CAD program).
    Units are millimetres."""

    LINETYPES = {
        "CONTINUOUS": ("Solid line", []),
        "HIDDEN": ("Hidden __ __ __", [3.0, -1.5]),
        "CENTER": ("Center ____ _ ____", [12.0, -3.0, 2.0, -3.0]),
    }

    def __init__(self):
        self.layers = {}
        self.entities = []

    def layer(self, name, color=7, linetype="CONTINUOUS"):
        self.layers.setdefault(name, (color, linetype))
        return name

    def line(self, x1, y1, x2, y2, layer="0"):
        self.layer(layer)
        self.entities.append(
            ("LINE", [(8, layer), (10, x1), (20, y1), (30, 0.0), (11, x2), (21, y2), (31, 0.0)])
        )

    def circle(self, cx, cy, r, layer="0"):
        self.layer(layer)
        self.entities.append(("CIRCLE", [(8, layer), (10, cx), (20, cy), (30, 0.0), (40, r)]))

    def arc(self, cx, cy, r, start_deg, end_deg, layer="0"):
        """Counter-clockwise from start to end (degrees)."""
        self.layer(layer)
        self.entities.append(
            (
                "ARC",
                [
                    (8, layer),
                    (10, cx),
                    (20, cy),
                    (30, 0.0),
                    (40, r),
                    (50, start_deg % 360.0),
                    (51, end_deg % 360.0),
                ],
            )
        )

    def text(self, x, y, height, value, layer="0", align="left", rotation=0.0):
        self.layer(layer)
        value = str(value).replace("\n", " ")
        codes = [(8, layer), (10, x), (20, y), (30, 0.0), (40, height), (1, value)]
        if rotation:
            codes.append((50, rotation))
        if align in ("center", "middle"):
            codes += [(72, 1), (11, x), (21, y), (31, 0.0)]
        elif align == "right":
            codes += [(72, 2), (11, x), (21, y), (31, 0.0)]
        self.entities.append(("TEXT", codes))

    def solid(self, points, layer="0"):
        """A filled triangle or quad (arrow heads)."""
        self.layer(layer)
        pts = list(points)
        if len(pts) == 3:
            pts.append(pts[2])
        codes = [(8, layer)]
        for i, (x, y) in enumerate(pts[:4]):
            codes += [(10 + i, x), (20 + i, y), (30 + i, 0.0)]
        self.entities.append(("SOLID", codes))

    def polyline(self, points, layer="0", closed=False):
        """As separate LINE entities (every reader takes them)."""
        pts = list(points)
        for a, b in zip(pts, pts[1:]):
            self.line(a[0], a[1], b[0], b[1], layer)
        if closed and len(pts) > 2:
            self.line(pts[-1][0], pts[-1][1], pts[0][0], pts[0][1], layer)

    @staticmethod
    def _pair(code, value):
        if isinstance(value, float):
            value = ("%.6f" % value).rstrip("0").rstrip(".") if value == value else "0"
            if value in ("-0", ""):
                value = "0"
        return "%3d\n%s\n" % (code, value)

    def to_text(self):
        out = []
        p = out.append
        p(self._pair(0, "SECTION") + self._pair(2, "HEADER"))
        p(self._pair(9, "$ACADVER") + self._pair(1, "AC1009"))
        p(self._pair(0, "ENDSEC"))
        p(self._pair(0, "SECTION") + self._pair(2, "TABLES"))
        p(self._pair(0, "TABLE") + self._pair(2, "LTYPE") + self._pair(70, len(self.LINETYPES)))
        for name, (desc, pattern) in self.LINETYPES.items():
            p(self._pair(0, "LTYPE") + self._pair(2, name) + self._pair(70, 0))
            p(self._pair(3, desc) + self._pair(72, 65) + self._pair(73, len(pattern)))
            p(self._pair(40, float(sum(abs(x) for x in pattern))))
            for item in pattern:
                p(self._pair(49, float(item)))
        p(self._pair(0, "ENDTAB"))
        layers = dict(self.layers)
        layers.setdefault("0", (7, "CONTINUOUS"))
        p(self._pair(0, "TABLE") + self._pair(2, "LAYER") + self._pair(70, len(layers)))
        for name, (color, linetype) in layers.items():
            p(self._pair(0, "LAYER") + self._pair(2, name) + self._pair(70, 0))
            p(self._pair(62, color) + self._pair(6, linetype))
        p(self._pair(0, "ENDTAB"))
        p(self._pair(0, "ENDSEC"))
        p(self._pair(0, "SECTION") + self._pair(2, "ENTITIES"))
        for kind, codes in self.entities:
            p(self._pair(0, kind))
            for code, value in codes:
                p(self._pair(code, value))
        p(self._pair(0, "ENDSEC") + self._pair(0, "EOF"))
        return "".join(out)


def read_dxf_entities(text):
    """[(kind, {code: [values]})] of a DXF's ENTITIES section (for tests and checks)."""
    lines = [line.strip() for line in text.splitlines()]
    pairs = []
    for i in range(0, len(lines) - 1, 2):
        try:
            pairs.append((int(lines[i]), lines[i + 1]))
        except ValueError:
            continue
    entities = []
    inside = False
    current = None
    for idx, (code, value) in enumerate(pairs):
        if code == 2 and value == "ENTITIES" and idx and pairs[idx - 1] == (0, "SECTION"):
            inside = True
            continue
        if not inside:
            continue
        if code == 0:
            if current is not None:
                entities.append(current)
                current = None
            if value in ("ENDSEC", "EOF"):
                inside = False
                continue
            current = (value, {})
        elif current is not None:
            current[1].setdefault(code, []).append(value)
    if current is not None:
        entities.append(current)
    return entities
