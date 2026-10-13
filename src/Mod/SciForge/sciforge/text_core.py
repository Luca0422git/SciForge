# SPDX-License-Identifier: LGPL-2.1-or-later
"""Where the letters of a sketch text go, Fusion's way. Pure Python (no FreeCAD, no Qt):
positions and transforms only; text.py turns them into glyph outlines.

Fusion's Text dialog (Autodesk help "Reference: Text dialog", "Create text in a sketch"):
  Type          Text (inside a rectangular frame placed with two clicks) or Text On Path
  Text          one or more lines. Since Fusion's September 2025 release the box is an
                expression: literal text in single quotes, joined with + to parameter
                names ('Rev ' + version). evaluate() reads that, and plain text without
                any quote as typed (Fusion shows it red and greys out OK).
  Height        the height of the font's em box (a capital is about 0.7 of it in Arial)
  Angle         the frame's rotation (Text)
  Font, Bold / Italic / Underline
  Alignment     Horizontal Left / Center / Right, Vertical Top / Middle / Bottom inside
                the frame; on a path: Left / Center / Right along the path
  Character Spacing  percent of the font's own spacing, 0 = the font's spacing
  Flip          Horizontal and / or Vertical
  Placement     Above / Below the path, Fit to Path (Text On Path)

Coordinates: the frame's own axes have their origin at the frame's bottom left corner
(before the Angle turns it), x to the right, y up; sketch millimetres.
An affine transform is a tuple (a, b, c, d, e, f): x' = a x + b y + e, y' = c x + d y + f.
"""

import math

TYPE_TEXT = "text"
TYPE_PATH = "path"
TYPES = (TYPE_TEXT, TYPE_PATH)
H_ALIGNS = ("left", "center", "right")
V_ALIGNS = ("top", "middle", "bottom")
MIN_HEIGHT = 0.01  # mm
MAX_HEIGHT = 100000.0
MIN_SPACING = -50.0  # percent: below this letters run into each other
MAX_SPACING = 1000.0
MAX_CHARS = 2000  # a pasted page of text would take minutes to outline
BOLD_EXTRA = 1.0 / 24.0  # FreeType's embolden: the outline grows by em/48 on each side
ITALIC_SLANT = 0.2126  # tan(12 degrees), FreeType's oblique slant
SNAP_NAMES = (
    "bottom_left",
    "bottom",
    "bottom_right",
    "right",
    "top_right",
    "top",
    "top_left",
    "left",
    "center",
)


class TextError(ValueError):
    """The text cannot be made as asked; the message says why and what to do."""


# -- the Text box --------------------------------------------------------------------------
def _tokens(expr):
    """[("str", text) | ("name", name) | ("num", text) | ("plus", "+")] or TextError."""
    tokens = []
    i, n = 0, len(expr)
    while i < n:
        ch = expr[i]
        if ch in " \t\r\n":
            i += 1
        elif ch == "+":
            tokens.append(("plus", "+"))
            i += 1
        elif ch in "'‘’":
            i += 1
            out = []
            while True:
                if i >= n:
                    raise TextError("A quote is not closed: end the text with ' (a single quote).")
                c = expr[i]
                if c == "\\" and i + 1 < n:
                    out.append(expr[i + 1])
                    i += 2
                    continue
                if c in "'‘’":
                    i += 1
                    break
                out.append(c)
                i += 1
            tokens.append(("str", "".join(out)))
        elif ch.isalpha() or ch == "_":
            j = i
            while j < n and (expr[j].isalnum() or expr[j] in "_."):
                j += 1
            tokens.append(("name", expr[i:j]))
            i = j
        elif ch.isdigit() or (ch in ".-" and i + 1 < n and expr[i + 1].isdigit()):
            j = i + 1
            while j < n and (expr[j].isdigit() or expr[j] == "."):
                j += 1
            tokens.append(("num", expr[i:j]))
            i = j
        else:
            raise TextError("'%s' cannot be read here." % ch)
    return tokens


def format_value(value):
    """A parameter's value as it appears in text: 12, 2.5 (no unit, no trailing zeros)."""
    if isinstance(value, str):
        return value
    try:
        number = float(getattr(value, "Value", value))
    except (TypeError, ValueError):
        return str(value)
    if abs(number - round(number)) < 1e-9:
        return str(int(round(number)))
    return ("%.6f" % number).rstrip("0").rstrip(".")


def is_expression(expr):
    """True when the Text box holds Fusion's expression form (it has a quote)."""
    return any(q in (expr or "") for q in "'‘’")


def evaluate(expr, lookup=None):
    """The text a Text box `expr` stands for. lookup(name) gives a parameter's value (or
    raises KeyError). Without any quote the box is taken as typed, except when it is
    exactly a parameter's name."""
    expr = expr if expr is not None else ""
    if not is_expression(expr):
        name = expr.strip()
        if lookup is not None and name and name.replace("_", "a").replace(".", "a").isalnum():
            try:
                return format_value(lookup(name))
            except KeyError:
                pass
        return expr
    tokens = _tokens(expr)
    if not tokens:
        return ""
    parts = []
    want_term = True
    for kind, text in tokens:
        if want_term:
            if kind == "str":
                parts.append(text)
            elif kind == "num":
                parts.append(format_value(float(text)))
            elif kind == "name":
                if lookup is None:
                    raise TextError("'%s' is not a parameter." % text)
                try:
                    parts.append(format_value(lookup(text)))
                except KeyError:
                    raise TextError(
                        "'%s' is not a parameter. Put text in single quotes: '%s'." % (text, text)
                    )
            else:
                raise TextError("A + needs text or a parameter on both sides.")
            want_term = False
        else:
            if kind != "plus":
                raise TextError("Join text and parameters with +, e.g. 'Rev ' + version.")
            want_term = True
    if want_term:
        raise TextError("A + needs text or a parameter on both sides.")
    return "".join(parts)


def literal(text):
    """The Text box form of plain text (quoted, quotes escaped): Fusion's own spelling."""
    return "'" + (text or "").replace("\\", "\\\\").replace("'", "\\'") + "'"


def check_text(text):
    """Raise TextError unless the text has something to draw."""
    if text is None or not text.strip():
        raise TextError("Type some text first: an empty text makes no profile.")
    if len(text) > MAX_CHARS:
        raise TextError(
            "That is too much text (%d characters, at most %d)." % (len(text), MAX_CHARS)
        )


def check_height(height):
    if height is None or not (MIN_HEIGHT <= float(height) <= MAX_HEIGHT):
        raise TextError("The height must be between %g and %g mm." % (MIN_HEIGHT, MAX_HEIGHT))


def check_spacing(spacing):
    if not (MIN_SPACING <= float(spacing) <= MAX_SPACING):
        raise TextError(
            "Character Spacing must be between %g %% and %g %%." % (MIN_SPACING, MAX_SPACING)
        )


# -- affine transforms ---------------------------------------------------------------------------
IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def compose(outer, inner):
    """outer after inner."""
    a1, b1, c1, d1, e1, f1 = outer
    a2, b2, c2, d2, e2, f2 = inner
    return (
        a1 * a2 + b1 * c2,
        a1 * b2 + b1 * d2,
        c1 * a2 + d1 * c2,
        c1 * b2 + d1 * d2,
        a1 * e2 + b1 * f2 + e1,
        c1 * e2 + d1 * f2 + f1,
    )


def chain(*transforms):
    """The transforms applied left to right (the first one first)."""
    result = IDENTITY
    for t in transforms:
        result = compose(t, result)
    return result


def apply(t, x, y):
    a, b, c, d, e, f = t
    return (a * x + b * y + e, c * x + d * y + f)


def translation(dx, dy):
    return (1.0, 0.0, 0.0, 1.0, float(dx), float(dy))


def rotation(radians, about=(0.0, 0.0)):
    co, si = math.cos(radians), math.sin(radians)
    px, py = about
    return (co, -si, si, co, px - co * px + si * py, py - si * px - co * py)


def scaling(sx, sy=None, about=(0.0, 0.0)):
    sy = sx if sy is None else sy
    px, py = about
    return (float(sx), 0.0, 0.0, float(sy), px - sx * px, py - sy * py)


def shear_x(k):
    """x' = x + k y (a slant: italic)."""
    return (1.0, float(k), 0.0, 1.0, 0.0, 0.0)


def determinant(t):
    return t[0] * t[3] - t[1] * t[2]


def inverse(t):
    a, b, c, d, e, f = t
    det = a * d - b * c
    if abs(det) < 1e-15:
        raise TextError("A text transform collapsed to nothing.")
    ia, ib, ic, id_ = d / det, -b / det, -c / det, a / det
    return (ia, ib, ic, id_, -(ia * e + ib * f), -(ic * e + id_ * f))


# -- lines of text ----------------------------------------------------------------------------
class Glyph:
    """One character placed: `x`, `y` its pen origin on the baseline (layout mm, before
    flips / frame), `advance` its advance (mm), `line` its line number."""

    __slots__ = ("char", "x", "y", "advance", "line")

    def __init__(self, char, x, y, advance, line):
        self.char = char
        self.x = x
        self.y = y
        self.advance = advance
        self.line = line

    def __repr__(self):
        return "Glyph(%r, %.4f, %.4f)" % (self.char, self.x, self.y)


def line_pens(text, font, spacing=0.0, bold_extra=0.0):
    """([(char, pen x)], advance width) of one line in font units. Character Spacing
    widens each character's advance by `spacing` percent of itself (Fusion: a percent of
    the font's own spacing, 0 keeps it). Pair kerning as FreeType applies it."""
    pens = []
    pen = 0.0
    previous = None
    factor = 1.0 + float(spacing) / 100.0
    last_extra = 0.0
    for char in text:
        if previous is not None:
            pen += font.kerning(previous, char)
        pens.append((char, pen))
        advance = font.advance(char) + bold_extra
        step = advance * factor
        last_extra = step - advance
        pen += step
        previous = char
    width = pen - last_extra if pens else 0.0  # no spacing after the last letter
    return pens, max(0.0, width)


def lines_of(text):
    return (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")


def em_scale(font, height):
    return float(height) / float(font.units_per_em or 1000)


def block(
    text,
    font,
    height,
    spacing=0.0,
    h_align="left",
    v_align="bottom",
    width=0.0,
    frame_height=0.0,
    bold=False,
):
    """Glyphs of a multi-line text set inside a frame of `width` x `frame_height` (mm,
    frame axes). Lines are spaced by the font's line height; each line is aligned
    left / centre / right inside the width; the block top / middle / bottom inside the
    frame height (the font's ascender to descender). Returns (glyphs, lines) where
    lines = [(x0, x1, baseline y)] per line (for the underline)."""
    if h_align not in H_ALIGNS:
        raise TextError("Unknown horizontal alignment %r." % h_align)
    if v_align not in V_ALIGNS:
        raise TextError("Unknown vertical alignment %r." % v_align)
    scale = em_scale(font, height)
    extra = BOLD_EXTRA * font.units_per_em if bold else 0.0
    rows = lines_of(text)
    ascent = font.ascender * scale
    descent = -font.descender * scale  # positive
    step = max(font.line_height * scale, 1e-9)
    count = len(rows)
    block_height = ascent + descent + (count - 1) * step
    if v_align == "top":
        top = frame_height
    elif v_align == "bottom":
        top = block_height
    else:
        top = (frame_height + block_height) / 2.0
    glyphs, lines = [], []
    for number, row in enumerate(rows):
        pens, advance = line_pens(row, font, spacing, extra)
        line_width = advance * scale
        if h_align == "left":
            x0 = 0.0
        elif h_align == "center":
            x0 = (width - line_width) / 2.0
        else:
            x0 = width - line_width
        baseline = top - ascent - number * step
        for char, pen in pens:
            glyphs.append(
                Glyph(char, x0 + pen * scale, baseline, font.advance(char) * scale, number)
            )
        lines.append((x0, x0 + line_width, baseline))
    return glyphs, lines


def text_extent(text, font, height, spacing=0.0, bold=False):
    """(width, height) mm of the text's lines (the frame a text needs)."""
    scale = em_scale(font, height)
    extra = BOLD_EXTRA * font.units_per_em if bold else 0.0
    rows = lines_of(text)
    width = max((line_pens(r, font, spacing, extra)[1] for r in rows), default=0.0) * scale
    ascent = font.ascender * scale
    descent = -font.descender * scale
    step = font.line_height * scale
    return width, ascent + descent + (len(rows) - 1) * step


def underline_box(font, height, x0, x1, baseline):
    """(x0, y_bottom, x1, y_top) of a line's underline (the font's 'post' position)."""
    scale = em_scale(font, height)
    top = baseline + font.underline_position * scale
    bottom = top - max(font.underline_thickness, 1) * scale
    return (x0, bottom, x1, top)


# -- the frame -----------------------------------------------------------------------------------
MIN_FRAME = 1e-6


def frame_from_points(p1, p2):
    """(corner, width, height) of the upright frame between two clicked corners."""
    x0, x1 = sorted((float(p1[0]), float(p2[0])))
    y0, y1 = sorted((float(p1[1]), float(p2[1])))
    return (x0, y0), x1 - x0, y1 - y0


def frame_transform(corner, angle_deg, width, frame_height, flip_h=False, flip_v=False):
    """Frame axes -> sketch: the flips mirror the text about the frame's middle lines,
    then the frame turns by the Angle about its corner and sits at the corner."""
    t = IDENTITY
    if flip_h:
        t = compose((-1.0, 0.0, 0.0, 1.0, float(width), 0.0), t)
    if flip_v:
        t = compose((1.0, 0.0, 0.0, -1.0, 0.0, float(frame_height)), t)
    t = compose(rotation(math.radians(angle_deg)), t)
    return compose(translation(*corner), t)


def frame_corners(corner, angle_deg, width, frame_height):
    """[bottom left, bottom right, top right, top left] in sketch coordinates."""
    t = frame_transform(corner, angle_deg, width, frame_height)
    return [
        apply(t, x, y) for x, y in ((0, 0), (width, 0), (width, frame_height), (0, frame_height))
    ]


def frame_from_corners(bottom_left, bottom_right, top_right, top_left):
    """(corner, angle degrees, width, height) of a frame given its four corners."""
    bx, by = bottom_left
    dx, dy = bottom_right[0] - bx, bottom_right[1] - by
    width = math.hypot(dx, dy)
    angle = math.degrees(math.atan2(dy, dx)) if width > MIN_FRAME else 0.0
    ux, uy = top_left[0] - bx, top_left[1] - by
    # the height along the frame's own up direction (a frame dragged out of square
    # by hand still gives a sensible box)
    up = (-math.sin(math.radians(angle)), math.cos(math.radians(angle)))
    height = ux * up[0] + uy * up[1]
    return (bx, by), angle, width, height


def snap_points(corner, angle_deg, width, frame_height):
    """{name: (x, y)} the frame's corners, edge middles and centre (sketch coordinates):
    the points Fusion lets you click to turn the frame about."""
    t = frame_transform(corner, angle_deg, width, frame_height)
    w, h = width, frame_height
    local = {
        "bottom_left": (0.0, 0.0),
        "bottom": (w / 2.0, 0.0),
        "bottom_right": (w, 0.0),
        "right": (w, h / 2.0),
        "top_right": (w, h),
        "top": (w / 2.0, h),
        "top_left": (0.0, h),
        "left": (0.0, h / 2.0),
        "center": (w / 2.0, h / 2.0),
    }
    return {name: apply(t, *xy) for name, xy in local.items()}


def turned_corner(corner, angle_deg, width, frame_height, pivot, new_angle_deg):
    """The frame's corner after turning it to `new_angle_deg` about the snap point named
    `pivot` (or a point (x, y)), which stays where it is."""
    if isinstance(pivot, str):
        point = snap_points(corner, angle_deg, width, frame_height)[pivot]
    else:
        point = pivot
    delta = math.radians(new_angle_deg - angle_deg)
    return apply(rotation(delta, about=point), *corner)


def angle_about(pivot, start, now):
    """Degrees turned about `pivot` from point `start` to point `now` (a drag)."""
    a0 = math.atan2(start[1] - pivot[1], start[0] - pivot[0])
    a1 = math.atan2(now[1] - pivot[1], now[0] - pivot[0])
    turn = math.degrees(a1 - a0)
    while turn > 180.0:
        turn -= 360.0
    while turn <= -180.0:
        turn += 360.0
    return turn


def normal_angle(angle):
    """An angle in (-180, 180]."""
    angle = math.fmod(float(angle), 360.0)
    if angle > 180.0:
        angle -= 360.0
    elif angle <= -180.0:
        angle += 360.0
    return angle


# -- text on a path -------------------------------------------------------------------------------
def path_slots(glyphs, line_width, path_length, align="left", fit=False):
    """Where each glyph's middle goes along a path (distance from the path's start, in
    reading direction). Fit to Path spreads the letters over the whole path (their
    size stays); otherwise they keep their spacing and sit at the path's start, middle
    or end. Returns [(glyph, distance)]."""
    if not glyphs:
        return []
    mids = [g.x + g.advance / 2.0 for g in glyphs]
    if fit:
        if len(glyphs) == 1:
            return [(glyphs[0], path_length / 2.0)]
        first = glyphs[0].advance / 2.0
        last = glyphs[-1].advance / 2.0
        span = mids[-1] - mids[0]
        room = max(path_length - first - last, 0.0)
        k = room / span if span > 1e-12 else 0.0
        return [(g, first + (m - mids[0]) * k) for g, m in zip(glyphs, mids)]
    if align == "left":
        start = 0.0
    elif align == "center":
        start = (path_length - line_width) / 2.0
    elif align == "right":
        start = path_length - line_width
    else:
        raise TextError("Unknown alignment %r." % align)
    return [(g, start + m) for g, m in zip(glyphs, mids)]


def path_glyph_transform(point, tangent, glyph, baseline_offset, flip_h=False, flip_v=False):
    """Glyph axes (pen origin on the baseline) -> sketch, for a glyph whose middle sits at
    `point` on the path, the path running along `tangent` (unit 2D vector, reading
    direction). The baseline sits `baseline_offset` mm off the path along its left
    normal (0: on the path, Above; minus the ascent: hanging Below). Flip Horizontal
    mirrors the letter about its middle; Flip Vertical mirrors it across the path."""
    tx, ty = tangent
    nx, ny = -ty, tx
    t = translation(-glyph.advance / 2.0, 0.0)
    if flip_h:
        t = compose((-1.0, 0.0, 0.0, 1.0, 0.0, 0.0), t)
    offset = baseline_offset
    if flip_v:
        t = compose((1.0, 0.0, 0.0, -1.0, 0.0, 0.0), t)
        offset = -offset
    t = compose(translation(0.0, offset), t)
    t = compose((tx, nx, ty, ny, 0.0, 0.0), t)
    return compose(translation(point[0], point[1]), t)


def below_offset(font, height):
    """How far the baseline sits under the path for Placement Below (the letters hang
    under it, their ascender on the path)."""
    return -font.ascender * em_scale(font, height)
