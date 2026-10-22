# SPDX-License-Identifier: LGPL-2.1-or-later
"""Drawing annotations as plain shapes: leaders with text, feature control frames (GD&T),
datum identifiers, surface texture symbols, ordinate dimensions and arc lengths. Pure
Python (no FreeCAD, no Qt), unit tested (SciForgeTests/unit/test_drawing_annot_core.py).

Every annotation is a list of primitives in page millimetres (origin at the sheet's
bottom left, y up); the sheet shows them as an SVG symbol (TechDraw DrawViewSymbol) and
the DXF export writes the same list, so both always agree:

    ("line", x1, y1, x2, y2, width)
    ("circle", cx, cy, r, width)
    ("arc", cx, cy, r, start_deg, end_deg, width)      counter-clockwise from start
    ("poly", [(x, y), ...], filled, width)             closed
    ("text", x, y, size, text, anchor, rotation_deg)    y: the baseline; anchor start,
                                                        middle or end

The GD&T and surface texture symbols are drawn from lines and circles (ISO 1101,
ISO 1302 / ASME Y14.5, Y14.36 shapes), never from a font, so they look the same on
every computer and in the DXF.
"""

import math
from xml.sax.saxutils import escape

FONT = "sans-serif"
LINE = 0.25  # line width of annotations (mm)
TEXT = 3.5  # text height (mm)
ARROW_LENGTH = 3.0
ARROW_HALF = 0.55
CHAR_WIDTH = 0.6  # average character width / text height (sans-serif)

# Fusion's Feature Control Frame characteristics (ISO 1101 / ASME Y14.5).
CHARACTERISTICS = (
    ("position", "Position"),
    ("concentricity", "Concentricity"),
    ("symmetry", "Symmetry"),
    ("parallelism", "Parallelism"),
    ("perpendicularity", "Perpendicularity"),
    ("angularity", "Angularity"),
    ("cylindricity", "Cylindricity"),
    ("flatness", "Flatness"),
    ("circularity", "Circularity"),
    ("straightness", "Straightness"),
    ("profile_surface", "Profile of a Surface"),
    ("profile_line", "Profile of a Line"),
    ("circular_runout", "Circular Runout"),
    ("total_runout", "Total Runout"),
)
CHARACTERISTIC_NAMES = tuple(c[0] for c in CHARACTERISTICS)
# the Unicode characters for the symbols (Miscellaneous Technical block): the text a
# drawn symbol stands for, for the searchable text of a PDF (spoken=True)
CHARACTERISTIC_CHARS = {
    "position": "\u2316",
    "concentricity": "\u25ce",
    "symmetry": "\u232f",
    "parallelism": "\u2225",
    "perpendicularity": "\u27c2",
    "angularity": "\u2220",
    "cylindricity": "\u232d",
    "flatness": "\u23e5",
    "circularity": "\u25cb",
    "straightness": "\u23e4",
    "profile_surface": "\u2313",
    "profile_line": "\u2312",
    "circular_runout": "\u2197",
    "total_runout": "\u2330",
}
DIAMETER_CHAR = "\u2300"
# characteristics that take no datum (form tolerances)
FORM_ONLY = ("cylindricity", "flatness", "circularity", "straightness")
MODIFIERS = (("", "None"), ("M", "Maximum material (M)"), ("L", "Least material (L)"))

SURFACE_KINDS = (
    ("basic", "Basic"),
    ("removal", "Material removal required"),
    ("no_removal", "Material removal prohibited"),
)
LAYS = ("", "=", "⊥", "X", "M", "C", "R", "P")


# ------------------------------------------------------------------ small helpers
def text_width(text, size=TEXT):
    return CHAR_WIDTH * size * len(str(text))


def unit(dx, dy):
    n = math.hypot(dx, dy)
    if n < 1e-12:
        return 1.0, 0.0
    return dx / n, dy / n


def arrow(tip, direction, length=ARROW_LENGTH, half=ARROW_HALF):
    """A filled arrow head with its point at `tip`, pointing along `direction`."""
    dx, dy = unit(*direction)
    bx, by = tip[0] - dx * length, tip[1] - dy * length
    return (
        "poly",
        [(tip[0], tip[1]), (bx - dy * half, by + dx * half), (bx + dy * half, by - dx * half)],
        True,
        LINE,
    )


def _rect(x0, y0, x1, y1, w=LINE):
    return [
        ("line", x0, y0, x1, y0, w),
        ("line", x1, y0, x1, y1, w),
        ("line", x1, y1, x0, y1, w),
        ("line", x0, y1, x0, y0, w),
    ]


def text_lines(lines, x, y, size=TEXT, anchor="start"):
    """Lines of text whose first line's middle is at height y (more lines go below)."""
    out = []
    for i, line in enumerate(lines):
        out.append(("text", x, y - size * 0.35 - i * size * 1.5, size, line, anchor, 0.0))
    return out


# ------------------------------------------------------------------ leader and note
def leader(anchor, place, lines, size=TEXT, arrowhead=True):
    """Fusion's Leader: an arrow on the edge, a line to the text and a short landing;
    the text sits beside the landing (right of it when placed to the right)."""
    lines = [str(t) for t in (lines or [""])]
    right = place[0] >= anchor[0]
    landing = 3.0 if right else -3.0
    end = (place[0] + landing, place[1])
    out = [("line", anchor[0], anchor[1], place[0], place[1], LINE)]
    out.append(("line", place[0], place[1], end[0], end[1], LINE))
    if arrowhead:
        out.append(arrow(anchor, (anchor[0] - place[0], anchor[1] - place[1])))
    gap = 1.0 if right else -1.0
    out += text_lines(lines, end[0] + gap, end[1], size, "start" if right else "end")
    return out


def leader_to_box(anchor, box):
    """A leader from an edge point to the nearest side's middle of a box (x0, y0, x1,
    y1): an arrow on the edge, a straight line (feature control frames)."""
    x0, y0, x1, y1 = box
    candidates = [
        (x0, (y0 + y1) / 2.0),
        (x1, (y0 + y1) / 2.0),
        ((x0 + x1) / 2.0, y0),
        ((x0 + x1) / 2.0, y1),
    ]
    target = min(candidates, key=lambda p: math.hypot(p[0] - anchor[0], p[1] - anchor[1]))
    if math.hypot(target[0] - anchor[0], target[1] - anchor[1]) < 0.5:
        return []
    return [
        ("line", anchor[0], anchor[1], target[0], target[1], LINE),
        arrow(anchor, (anchor[0] - target[0], anchor[1] - target[1])),
    ]


# ------------------------------------------------------------------ GD&T symbols
def characteristic_symbol(name, cx, cy, s=TEXT):
    """The geometric characteristic `name` drawn in a square of side ~s centred at
    (cx, cy)."""
    h = s * 0.5
    w = LINE
    out = []
    if name == "straightness":
        out.append(("line", cx - h, cy, cx + h, cy, w))
    elif name == "flatness":
        k = h * 0.45
        out.append(
            (
                "poly",
                [
                    (cx - h, cy - k),
                    (cx + h * 0.55, cy - k),
                    (cx + h, cy + k),
                    (cx - h * 0.55, cy + k),
                ],
                False,
                w,
            )
        )
    elif name == "circularity":
        out.append(("circle", cx, cy, h * 0.8, w))
    elif name == "cylindricity":
        r = h * 0.6
        out.append(("circle", cx, cy, r, w))
        out.append(("line", cx - h, cy - h, cx - r * 0.2, cy + h, w))
        out.append(("line", cx + r * 0.2, cy - h, cx + h, cy + h, w))
    elif name == "profile_line":
        out.append(("arc", cx, cy - h * 0.5, h, 0.0, 180.0, w))
    elif name == "profile_surface":
        out.append(("arc", cx, cy - h * 0.5, h, 0.0, 180.0, w))
        out.append(("line", cx - h, cy - h * 0.5, cx + h, cy - h * 0.5, w))
    elif name == "angularity":
        out.append(("line", cx - h, cy - h * 0.7, cx + h, cy - h * 0.7, w))
        out.append(("line", cx - h, cy - h * 0.7, cx + h * 0.7, cy + h * 0.8, w))
    elif name == "perpendicularity":
        out.append(("line", cx - h, cy - h * 0.8, cx + h, cy - h * 0.8, w))
        out.append(("line", cx, cy - h * 0.8, cx, cy + h, w))
    elif name == "parallelism":
        out.append(("line", cx - h * 0.8, cy - h, cx - h * 0.1, cy + h, w))
        out.append(("line", cx + h * 0.1, cy - h, cx + h * 0.8, cy + h, w))
    elif name == "position":
        r = h * 0.6
        out.append(("circle", cx, cy, r, w))
        out.append(("line", cx - h, cy, cx + h, cy, w))
        out.append(("line", cx, cy - h, cx, cy + h, w))
    elif name == "concentricity":
        out.append(("circle", cx, cy, h * 0.85, w))
        out.append(("circle", cx, cy, h * 0.45, w))
    elif name == "symmetry":
        out.append(("line", cx - h * 0.6, cy + h * 0.55, cx + h * 0.6, cy + h * 0.55, w))
        out.append(("line", cx - h, cy, cx + h, cy, w))
        out.append(("line", cx - h * 0.6, cy - h * 0.55, cx + h * 0.6, cy - h * 0.55, w))
    elif name == "circular_runout":
        out.append(("line", cx - h * 0.7, cy - h, cx + h * 0.5, cy + h * 0.7, w))
        out.append(arrow((cx + h * 0.7, cy + h), (1.2, 1.7), length=h * 0.7, half=h * 0.3))
    elif name == "total_runout":
        out.append(("line", cx - h, cy - h, cx + h * 0.3, cy - h, w))
        out.append(("line", cx - h * 0.9, cy - h, cx - h * 0.2, cy + h * 0.6, w))
        out.append(("line", cx - h * 0.1, cy - h, cx + h * 0.6, cy + h * 0.6, w))
        out.append(arrow((cx - h * 0.05, cy + h), (0.7, 1.0), length=h * 0.55, half=h * 0.25))
        out.append(arrow((cx + h * 0.75, cy + h), (0.7, 1.0), length=h * 0.55, half=h * 0.25))
    return out


def diameter_symbol(cx, cy, s=TEXT):
    r = s * 0.32
    return [
        ("circle", cx, cy, r, LINE),
        ("line", cx - r * 1.3, cy - r * 1.3, cx + r * 1.3, cy + r * 1.3, LINE),
    ]


def modifier_symbol(letter, cx, cy, s=TEXT):
    """A circled M or L (material condition)."""
    return [
        ("circle", cx, cy, s * 0.45, LINE),
        ("text", cx, cy - s * 0.27, s * 0.7, letter, "middle", 0.0),
    ]


def _runs_width(runs, s):
    width = 0.0
    for run in runs:
        if run[0] == "dia":
            width += s * 1.0
        elif run[0] == "mod":
            width += s * 1.15
        else:
            width += text_width(run[1], s)
    return width


def _draw_runs(runs, x, cy, s, spoken=False):
    """The runs of a cell; spoken=True also gives the diameter sign as text, joined to the
    tolerance after it (searchable PDF text: "\u23000.05")."""
    out = []
    sign = None
    for run in runs:
        if run[0] == "dia":
            out += diameter_symbol(x + s * 0.5, cy, s)
            sign = x
            x += s * 1.0
        elif run[0] == "mod":
            out += modifier_symbol(run[1], x + s * 0.575, cy, s)
            x += s * 1.15
        else:
            if sign is not None and spoken:
                out.append(("text", sign, cy - s * 0.35, s, DIAMETER_CHAR + run[1], "start", 0.0))
                sign = None
            else:
                out.append(("text", x, cy - s * 0.35, s, run[1], "start", 0.0))
            x += text_width(run[1], s)
    if sign is not None and spoken:
        out.append(("text", sign, cy - s * 0.35, s, DIAMETER_CHAR, "start", 0.0))
    return out


def fcf_rows(data):
    """The frame's rows from its settings: [{"char", "dia", "tol", "mod", "datums":
    [(letter, modifier)]}], the second row only when there is one."""
    rows = []
    for key in ("row1", "row2"):
        row = data.get(key)
        if not row:
            continue
        datums = [
            (str(d[0]).strip().upper(), d[1] if len(d) > 1 else "")
            for d in row.get("datums", [])
            if d and str(d[0]).strip()
        ][:3]
        rows.append(
            {
                "char": row.get("char") or data.get("char") or "position",
                "dia": bool(row.get("dia")),
                "tol": str(row.get("tol", "")).strip() or "0",
                "mod": row.get("mod", "") or "",
                "datums": datums,
            }
        )
    return rows


def feature_control_frame(data, x, y, s=TEXT, spoken=False):
    """A feature control frame with its top left corner at (x, y): one row, or two
    (composite: the second row shares the characteristic cell; else two frames
    stacked). Returns (primitives, box (x0, y0, x1, y1)). spoken=True adds the drawn
    symbols as text too (CHARACTERISTIC_CHARS, DIAMETER_CHAR), for a PDF's searchable
    text; never for what is drawn."""
    rows = fcf_rows(data) or [
        {"char": "position", "dia": False, "tol": "0", "mod": "", "datums": []}
    ]
    composite = bool(data.get("composite")) and len(rows) == 2
    h = s * 2.0
    pad = s * 0.6
    char_w = h
    cells = []
    for row in rows:
        tol_runs = []
        if row["dia"]:
            tol_runs.append(("dia",))
        tol_runs.append(("text", row["tol"]))
        if row["mod"]:
            tol_runs.append(("mod", row["mod"]))
        datum_runs = []
        for letter, mod in row["datums"]:
            runs = [("text", letter)]
            if mod:
                runs.append(("mod", mod))
            datum_runs.append(runs)
        cells.append((tol_runs, datum_runs))
    tol_w = max(_runs_width(c[0], s) for c in cells) + 2 * pad
    datum_count = max(len(c[1]) for c in cells)
    datum_w = []
    for i in range(datum_count):
        widths = [_runs_width(c[1][i], s) for c in cells if i < len(c[1])]
        datum_w.append(max(h, max(widths) + 2 * pad))
    out = []
    total_w = char_w + tol_w + sum(datum_w)
    for r, row in enumerate(rows):
        top = y - r * h
        bottom = top - h
        cy = (top + bottom) / 2.0
        row_w = char_w + tol_w + sum(datum_w[: len(cells[r][1])])
        top_from = x + char_w if (composite and r == 1) else x
        bottom_from = x + char_w if (composite and r == 0) else x
        out.append(("line", top_from, top, x + row_w, top, LINE))
        out.append(("line", bottom_from, bottom, x + row_w, bottom, LINE))
        out.append(("line", x, bottom, x, top, LINE))
        out.append(("line", x + row_w, bottom, x + row_w, top, LINE))
        # the characteristic cell
        if not (composite and r == 1):
            if composite and r == 0:
                out.append(("line", x + char_w, top, x + char_w, top - 2 * h, LINE))
                out += characteristic_symbol(row["char"], x + char_w / 2.0, top - h, s)
                sym_y = top - h
            else:
                out.append(("line", x + char_w, top, x + char_w, bottom, LINE))
                out += characteristic_symbol(row["char"], x + char_w / 2.0, cy, s)
                sym_y = cy
            if spoken and row["char"] in CHARACTERISTIC_CHARS:
                char = CHARACTERISTIC_CHARS[row["char"]]
                out.append(("text", x + char_w / 2.0, sym_y - s * 0.35, s, char, "middle", 0.0))
        cx = x + char_w
        out += _draw_runs(cells[r][0], cx + pad, cy, s, spoken)
        cx += tol_w
        for i, runs in enumerate(cells[r][1]):
            out.append(("line", cx, top, cx, bottom, LINE))
            width = _runs_width(runs, s)
            out += _draw_runs(runs, cx + (datum_w[i] - width) / 2.0, cy, s)
            cx += datum_w[i]
    return out, (x, y - len(rows) * h, x + total_w, y)


def fcf_text(data):
    """The frame as one line of text (DXF readers without the shapes, logs, tests)."""
    names = dict(CHARACTERISTICS)
    parts = []
    for row in fcf_rows(data):
        tol = ("⌀" if row["dia"] else "") + row["tol"] + ("(%s)" % row["mod"] if row["mod"] else "")
        datums = ["%s%s" % (d, "(%s)" % m if m else "") for d, m in row["datums"]]
        parts.append("|".join([names.get(row["char"], row["char"]), tol] + datums))
    return " / ".join(parts)


def feature_control(anchor, place, data, s=TEXT, spoken=False):
    """A feature control frame placed with its left middle at `place`, with a leader
    from the edge point `anchor` (no leader when anchor is None)."""
    rows = len(fcf_rows(data)) or 1
    h = s * 2.0
    frame, box = feature_control_frame(data, place[0], place[1] + rows * h / 2.0, s, spoken)
    out = list(frame)
    if anchor is not None:
        out += leader_to_box(anchor, box)
    return out, box


# ------------------------------------------------------------------ datum identifier
def datum_identifier(anchor, place, letter, tangent=None, s=TEXT):
    """A datum feature symbol: a filled triangle standing on the edge at `anchor`, a line
    to a square with the datum letter centred at `place`."""
    letter = str(letter or "A").strip().upper() or "A"
    side = max(s * 2.0, text_width(letter, s) + s)
    half = side / 2.0
    out = _rect(place[0] - half, place[1] - half, place[0] + half, place[1] + half)
    out.append(("text", place[0], place[1] - s * 0.35, s, letter, "middle", 0.0))
    d = unit(place[0] - anchor[0], place[1] - anchor[1])
    if tangent is not None:
        tx, ty = unit(*tangent)
        n = (-ty, tx)
        if n[0] * d[0] + n[1] * d[1] < 0:
            n = (-n[0], -n[1])
    else:
        n = d
        tx, ty = -d[1], d[0]
    tri_h = s * 0.85
    base = s * 0.55
    apex = (anchor[0] + n[0] * tri_h, anchor[1] + n[1] * tri_h)
    out.append(
        (
            "poly",
            [
                (anchor[0] - tx * base, anchor[1] - ty * base),
                (anchor[0] + tx * base, anchor[1] + ty * base),
                apex,
            ],
            True,
            LINE,
        )
    )
    # the line from the triangle to the nearest side of the box
    candidates = [
        (place[0] - half, place[1]),
        (place[0] + half, place[1]),
        (place[0], place[1] - half),
        (place[0], place[1] + half),
    ]
    target = min(candidates, key=lambda p: math.hypot(p[0] - apex[0], p[1] - apex[1]))
    out.append(("line", apex[0], apex[1], target[0], target[1], LINE))
    return out


# ------------------------------------------------------------------ surface texture
def surface_texture(anchor, place, data, standard="ISO", s=TEXT):
    """A surface texture symbol (ISO 1302 / ASME Y14.36) whose tip stands at `place`;
    a leader with an arrow from `anchor` (on the surface) when the two differ.
    data: {"kind": basic | removal | no_removal, "value": "Ra 3.2", "lay": "=",
    "all_around": bool}. ISO writes the requirement under a line on the long leg, ASME
    above the V."""
    kind = data.get("kind") or "removal"
    value = str(data.get("value") or "").strip()
    lay = str(data.get("lay") or "").strip()
    tip = place
    h1 = s * 1.45  # short leg height
    h2 = s * 3.0  # long leg height
    k = 1.0 / math.tan(math.radians(60.0))
    left = (tip[0] - h1 * k, tip[1] + h1)
    right = (tip[0] + h2 * k, tip[1] + h2)
    out = [
        ("line", tip[0], tip[1], left[0], left[1], LINE),
        ("line", tip[0], tip[1], right[0], right[1], LINE),
    ]
    short_right = (tip[0] + h1 * k, tip[1] + h1)
    if kind == "removal":
        out.append(("line", left[0], left[1], short_right[0], short_right[1], LINE))
    elif kind == "no_removal":
        r = h1 * 0.42
        out.append(("circle", tip[0], tip[1] + h1 - r - 0.05, r, LINE))
    if standard == "ISO":
        width = max(text_width(value, s) + 2.0, s * 2.0) if value else s * 1.5
        out.append(("line", right[0], right[1], right[0] + width, right[1], LINE))
        if value:
            out.append(("text", right[0] + 1.0, right[1] - s * 1.25, s, value, "start", 0.0))
        if data.get("all_around"):
            out.append(("circle", right[0], right[1], s * 0.3, LINE))
    else:
        if value:
            out.append(("text", tip[0] - 0.3, tip[1] + h1 + s * 0.35, s, value, "end", 0.0))
        if data.get("all_around"):
            out.append(("circle", right[0], right[1], s * 0.3, LINE))
    if lay:
        out.append(("text", tip[0] + h1 * k + 0.8, tip[1] + 0.4, s * 0.85, lay, "start", 0.0))
    if anchor is not None and math.hypot(anchor[0] - tip[0], anchor[1] - tip[1]) > 0.5:
        out.append(("line", anchor[0], anchor[1], tip[0], tip[1], LINE))
        out.append(arrow(anchor, (anchor[0] - tip[0], anchor[1] - tip[1])))
    return out


def surface_text(data):
    names = dict(SURFACE_KINDS)
    parts = [names.get(data.get("kind") or "removal", "")]
    if data.get("value"):
        parts.append(str(data["value"]))
    if data.get("lay"):
        parts.append("lay %s" % data["lay"])
    if data.get("all_around"):
        parts.append("all around")
    return ", ".join(p for p in parts if p)


# ------------------------------------------------------------------ ordinate dimensions
def ordinate_axis(feature, place):
    """Which coordinate an ordinate dimension shows from where its text is put: moving
    up or down from the point measures along x (a vertical leader), sideways along y."""
    dx, dy = place[0] - feature[0], place[1] - feature[1]
    return "x" if abs(dy) >= abs(dx) else "y"


def ordinate(feature, place, axis, text, standard="ISO", s=TEXT, gap=1.5):
    """One ordinate dimension: a leader from near the feature point to the text line
    (`place` gives the line: its y for axis x, its x for axis y) and the value at its
    end. ISO writes x values along the leader (turned 90 degrees), ASME level."""
    out = []
    if axis == "x":
        x = feature[0]
        end = place[1]
        up = end >= feature[1]
        start = feature[1] + (gap if up else -gap)
        if abs(end - feature[1]) < gap + 0.5:
            end = feature[1] + (gap + 0.5 if up else -gap - 0.5)
        out.append(("line", x, start, x, end, LINE))
        if standard == "ISO":
            out.append(
                (
                    "text",
                    x + s * 0.35,
                    end + (0.8 if up else -0.8),
                    s,
                    text,
                    "start" if up else "end",
                    90.0,
                )
            )
        else:
            ty = end + 0.8 if up else end - 0.8 - s
            out.append(("text", x, ty, s, text, "middle", 0.0))
    else:
        y = feature[1]
        end = place[0]
        right = end >= feature[0]
        start = feature[0] + (gap if right else -gap)
        if abs(end - feature[0]) < gap + 0.5:
            end = feature[0] + (gap + 0.5 if right else -gap - 0.5)
        out.append(("line", start, y, end, y, LINE))
        out.append(
            (
                "text",
                end + (0.8 if right else -0.8),
                y - s * 0.35,
                s,
                text,
                "start" if right else "end",
                0.0,
            )
        )
    return out


def ordinate_value(origin, feature, axis, scale=1.0):
    """The distance an ordinate dimension shows (model mm, never negative)."""
    i = 0 if axis == "x" else 1
    return abs(feature[i] - origin[i]) / (scale or 1.0)


# ------------------------------------------------------------------ arc length
def arc_length(center, radius, start_deg, end_deg, place, text, s=TEXT):
    """An arc length dimension: extension lines from the arc's ends, a dimension arc
    through `place` with arrows at its ends, the value with the arc sign before it."""
    a0, a1 = start_deg % 360.0, end_deg % 360.0
    sweep = (a1 - a0) % 360.0 or 360.0
    rd = max(math.hypot(place[0] - center[0], place[1] - center[1]), radius + 3.0)
    out = []
    for a in (a0, a1):
        c, sn = math.cos(math.radians(a)), math.sin(math.radians(a))
        out.append(
            (
                "line",
                center[0] + c * (radius + 1.0),
                center[1] + sn * (radius + 1.0),
                center[0] + c * (rd + 1.5),
                center[1] + sn * (rd + 1.5),
                LINE,
            )
        )
    out.append(("arc", center[0], center[1], rd, a0, a0 + sweep, LINE))
    for a, sign in ((a0, -1.0), (a0 + sweep, 1.0)):
        c, sn = math.cos(math.radians(a)), math.sin(math.radians(a))
        tip = (center[0] + c * rd, center[1] + sn * rd)
        tangent = (-sn * sign, c * sign)
        out.append(arrow(tip, tangent))
    mid = math.radians(a0 + sweep / 2.0)
    tx = center[0] + math.cos(mid) * (rd + s * 0.9)
    ty = center[1] + math.sin(mid) * (rd + s * 0.9)
    out.append(("text", tx, ty - s * 0.35, s, "⌒" + str(text), "middle", 0.0))
    return out


# ------------------------------------------------------------------ bounding box, SVG, DXF
def _text_box(prim):
    _k, x, y, size, text, anchor, rot = prim
    w = text_width(text, size)
    x0 = {"start": 0.0, "middle": -w / 2.0, "end": -w}.get(anchor, 0.0)
    corners = [(x0, -0.25 * size), (x0 + w, -0.25 * size), (x0 + w, size), (x0, size)]
    a = math.radians(rot or 0.0)
    c, sn = math.cos(a), math.sin(a)
    return [(x + u * c - v * sn, y + u * sn + v * c) for u, v in corners]


def _arc_points(prim):
    """The ends of an arc and its extreme points (where it crosses 0, 90, 180, 270)."""
    _k, cx, cy, r, a0, a1, _w = prim
    sweep = (a1 - a0) % 360.0 or 360.0
    angles = [a0, a0 + sweep]
    for quarter in (0.0, 90.0, 180.0, 270.0, 360.0, 450.0, 540.0, 630.0):
        if a0 < quarter < a0 + sweep:
            angles.append(quarter)
    return [
        (cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))) for a in angles
    ]


def bbox(prims):
    """(xmin, ymin, xmax, ymax) of primitives (texts estimated)."""
    xs, ys = [], []
    for p in prims:
        kind = p[0]
        if kind == "line":
            xs += [p[1], p[3]]
            ys += [p[2], p[4]]
        elif kind == "circle":
            xs += [p[1] - p[3], p[1] + p[3]]
            ys += [p[2] - p[3], p[2] + p[3]]
        elif kind == "arc":
            for q in _arc_points(p):
                xs.append(q[0])
                ys.append(q[1])
        elif kind == "poly":
            xs += [q[0] for q in p[1]]
            ys += [q[1] for q in p[1]]
        elif kind == "text":
            for q in _text_box(p):
                xs.append(q[0])
                ys.append(q[1])
    if not xs:
        return 0.0, 0.0, 0.0, 0.0
    return min(xs), min(ys), max(xs), max(ys)


def _fmt(v):
    text = ("%.3f" % v).rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def svg(prims, pad=1.0):
    """(SVG text, (cx, cy)): the primitives as an SVG symbol, and the page point its
    middle must be put at (TechDraw places a symbol by its middle)."""
    x0, y0, x1, y1 = bbox(prims)
    x0, y0, x1, y1 = x0 - pad, y0 - pad, x1 + pad, y1 + pad
    w, h = max(x1 - x0, 1.0), max(y1 - y0, 1.0)

    def X(x):
        return _fmt(x - x0)

    def Y(y):
        return _fmt(y1 - y)

    body = []
    for p in prims:
        kind = p[0]
        if kind == "line":
            body.append(
                '<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="#000000" stroke-width="%s" '
                'stroke-linecap="round"/>' % (X(p[1]), Y(p[2]), X(p[3]), Y(p[4]), _fmt(p[5]))
            )
        elif kind == "circle":
            body.append(
                '<circle cx="%s" cy="%s" r="%s" fill="none" stroke="#000000" '
                'stroke-width="%s"/>' % (X(p[1]), Y(p[2]), _fmt(p[3]), _fmt(p[4]))
            )
        elif kind == "arc":
            _k, cx, cy, r, a0, a1, lw = p
            sweep = (a1 - a0) % 360.0 or 360.0
            if sweep >= 359.999:
                body.append(
                    '<circle cx="%s" cy="%s" r="%s" fill="none" stroke="#000000" '
                    'stroke-width="%s"/>' % (X(cx), Y(cy), _fmt(r), _fmt(lw))
                )
                continue
            sx = cx + r * math.cos(math.radians(a0))
            sy = cy + r * math.sin(math.radians(a0))
            ex = cx + r * math.cos(math.radians(a0 + sweep))
            ey = cy + r * math.sin(math.radians(a0 + sweep))
            large = 1 if sweep > 180.0 else 0
            # counter-clockwise with y up is clockwise with y down: sweep flag 0
            body.append(
                '<path d="M %s %s A %s %s 0 %d 0 %s %s" fill="none" stroke="#000000" '
                'stroke-width="%s"/>'
                % (X(sx), Y(sy), _fmt(r), _fmt(r), large, X(ex), Y(ey), _fmt(lw))
            )
        elif kind == "poly":
            pts = " ".join("%s,%s" % (X(q[0]), Y(q[1])) for q in p[1])
            body.append(
                '<polygon points="%s" fill="%s" stroke="#000000" stroke-width="%s"/>'
                % (pts, "#000000" if p[2] else "none", _fmt(p[3]))
            )
        elif kind == "text":
            _k, x, y, size, text, anchor, rot = p
            transform = ""
            if rot:
                transform = ' transform="rotate(%s %s %s)"' % (_fmt(-rot), X(x), Y(y))
            body.append(
                '<text x="%s" y="%s" font-family="%s" font-size="%s" fill="#000000"%s%s>%s'
                "</text>"
                % (
                    X(x),
                    Y(y),
                    FONT,
                    _fmt(size),
                    ' text-anchor="%s"' % anchor if anchor in ("middle", "end") else "",
                    transform,
                    escape(str(text)),
                )
            )
    text = (
        '<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="%smm" height="%smm" '
        'viewBox="0 0 %s %s">\n%s\n</svg>\n' % (_fmt(w), _fmt(h), _fmt(w), _fmt(h), "\n".join(body))
    )
    return text, ((x0 + x1) / 2.0, (y0 + y1) / 2.0)


def to_dxf(dxf, prims, layer):
    """Write primitives into a drawing_core.DxfWriter on `layer`."""
    for p in prims:
        kind = p[0]
        if kind == "line":
            dxf.line(p[1], p[2], p[3], p[4], layer)
        elif kind == "circle":
            dxf.circle(p[1], p[2], p[3], layer)
        elif kind == "arc":
            dxf.arc(p[1], p[2], p[3], p[4], p[5], layer)
        elif kind == "poly":
            pts = list(p[1])
            if p[2] and len(pts) >= 3:
                for i in range(1, len(pts) - 1):
                    dxf.solid([pts[0], pts[i], pts[i + 1]], layer)
            else:
                dxf.polyline(pts, layer, closed=True)
        elif kind == "text":
            _k, x, y, size, text, anchor, rot = p
            align = {"middle": "center", "end": "right"}.get(anchor, "left")
            dxf.text(x, y, size, text, layer, align, rotation=rot or 0.0)


def texts_of(prims):
    return [p[4] for p in prims if p[0] == "text"]
