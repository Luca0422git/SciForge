# SPDX-License-Identifier: LGPL-2.1-or-later
"""The maths of SciForge's sketch inference (sketch_infer.py does the mouse and the
drawing): where the point FreeCAD's line tool gets should go, and why.

Fusion, while you draw a line:
- remembers the last few points you hovered ("acquired" points) and the points of the
  lines drawn in the current command; when the pointer lines up with one of them
  horizontally or vertically, a dashed guide shows and the point snaps onto it;
- snaps a line that is nearly level or upright to exactly level or upright;
- snaps a line that starts from, or ends on, another line at about 90 degrees to
  exactly 90 degrees (perpendicular);
- (unconfirmed, off by default here) snaps a line nearly parallel to a line you hovered.

A point or curve right under the pointer always wins: that is FreeCAD's own snapping
(end points, middles, centres, curves), which SciForge leaves alone.

The same guides apply to every point the other drawing tools place (rectangle corners,
circle centres and rim points, arc points, polygon centre and corner, slot centres); the
level/upright/perpendicular direction applies to the line and to the slot's centre line.
Fusion's tangent arc (press on the end of the line being drawn and drag) has its maths
here too (tangent_arc, chain_tangent).

No FreeCAD, no Qt here: plain (x, y) tuples in sketch millimetres, so it is unit tested.
`px` is how many millimetres one screen pixel is at the moment, so tolerances given in
pixels feel the same at every zoom.
"""

import math

HORIZONTAL, VERTICAL = "h", "v"
PERPENDICULAR, PARALLEL = "perp", "parallel"
DIAGONAL = "diag"  # 45, 135, 225 or 315 degrees (beyond Fusion: Luca's wish)
# a guide keeps one coordinate of a point: "x" = straight above/below it (a vertical
# guide line), "y" = level with it (a horizontal guide line)
SAME_X, SAME_Y = "x", "y"

# Which FreeCAD / SciForge drawing command places which kind of shape. The guides apply
# to the points a tool places with a click (POINTS says how many); after that a tool
# asks for sizes (a corner radius, a slot's width, an arc's angle), which get no guides.
TOOLS = {
    "SciForge_SketchLine": "line",
    "Sketcher_CreateLine": "line",
    "Sketcher_CreateRectangle": "rect",
    "Sketcher_CreateRectangle_Center": "rect_center",
    "Sketcher_CreateCircle": "circle",
    "Sketcher_Create3PointCircle": "circle3",
    "Sketcher_CreateArc": "arc",
    "Sketcher_Create3PointArc": "arc3",
    "Sketcher_CreateSlot": "slot",
    "SciForge_PolygonCircumscribed": "polygon",
    "SciForge_PolygonInscribed": "polygon",
    "Sketcher_CreateHexagon": "polygon",
    "Sketcher_CreateTriangle": "polygon",
    "Sketcher_CreateSquare": "polygon",
    "Sketcher_CreatePentagon": "polygon",
    "Sketcher_CreateHeptagon": "polygon",
    "Sketcher_CreateOctagon": "polygon",
    "Sketcher_CreateRegularPolygon": "polygon",
}
# clicked points per shape: line start/end; rectangle two corners (or centre + corner);
# circle centre + rim point (or three rim points); arc centre + start (its end is on the
# circle at the pointer's angle: no guide), or three points; polygon centre + corner;
# slot two centres (the third click gives the width)
POINTS = {
    "line": 2,
    "rect": 2,
    "rect_center": 2,
    "circle": 2,
    "circle3": 3,
    "arc": 2,
    "arc3": 3,
    "slot": 2,
    "polygon": 2,
}
# shapes whose second point is the end of a direction from the first (level / upright /
# perpendicular apply, and the constraint goes on a line of the shape)
DIRECTION = ("line", "slot")


class Options:
    """Tolerances (pixels or degrees). The Fusion values are not published; these are
    SciForge's starting values (sketch_infer.PARAMS lets them be changed)."""

    def __init__(self, **values):
        self.guide_px = 6.0  # how close (pixels) the pointer must be to a guide
        self.pick_px = 6.0  # a point or curve this close is FreeCAD's snap, not ours
        self.hv_deg = 4.0  # level/upright within this angle snaps (FreeCAD alone: 2)
        self.perp_deg = 4.0  # 90 degrees to a touching line within this angle snaps
        self.parallel = False  # parallel to a hovered line (Fusion: unconfirmed)
        self.parallel_deg = 3.0
        self.diag_deg = 4.0  # 45 / 135 / 225 / 315 degrees within this angle snaps
        self.min_len_px = 10.0  # shorter lines have no direction to infer from
        self.grid = None  # grid spacing (mm) when grid snap is on, else None
        for name, value in values.items():
            if not hasattr(self, name):
                raise AttributeError(name)
            setattr(self, name, value)


class Guide:
    """A dashed alignment guide from an acquired point `anchor` (sketch vertex `key`)."""

    def __init__(self, key, anchor, axis):
        self.key = key
        self.anchor = anchor
        self.axis = axis

    def __repr__(self):
        return "Guide(%r, %r, %r)" % (self.key, self.anchor, self.axis)


class Result:
    """Where the point goes and why.

    point     the exact sketch point (the line tool gets the screen pixel nearest to it;
              the exact value is set after the click)
    guides    Guide objects the point lies on
    kind      None, HORIZONTAL, VERTICAL, DIAGONAL, PERPENDICULAR or PARALLEL (the new
              line's direction)
    direction the unit direction of the new line for `kind`
    other     the other line's geometry index (PERPENDICULAR / PARALLEL)
    on_line   True when the point lies on `other` (a line ending on another line)
    corner    where the right-angle mark goes (PERPENDICULAR), with `along` the other
              line's direction from there
    snap      the SnapPoint the point sits on (an end, a middle, a centre...), or None
    """

    def __init__(self, point, guides=(), kind=None, direction=None, other=None):
        self.point = point
        self.guides = list(guides)
        self.kind = kind
        self.direction = direction
        self.other = other
        self.on_line = False
        self.corner = None
        self.along = None
        self.start = None  # the line's first point (None before the first click)
        self.snap = None  # SnapPoint the point sits on exactly (snap_result), or None

    def __repr__(self):
        return "Result(%r, guides=%r, kind=%r, other=%r)" % (
            self.point,
            self.guides,
            self.kind,
            self.other,
        )


# -- small vector helpers (2D tuples) -------------------------------------------------
def sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def add(a, b):
    return (a[0] + b[0], a[1] + b[1])


def mul(a, k):
    return (a[0] * k, a[1] * k)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def length(a):
    return math.hypot(a[0], a[1])


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def unit(a):
    n = length(a)
    return (a[0] / n, a[1] / n) if n > 1e-12 else None


def angle_between(a, b):
    """Angle (radians, 0..pi) between two directions."""
    na, nb = length(a), length(b)
    if na < 1e-12 or nb < 1e-12:
        return math.pi
    c = max(-1.0, min(1.0, dot(a, b) / (na * nb)))
    return math.acos(c)


def segment_distance(p, a, b):
    """Distance from p to the segment a-b."""
    ab = sub(b, a)
    n2 = dot(ab, ab)
    if n2 < 1e-24:
        return dist(p, a)
    t = max(0.0, min(1.0, dot(sub(p, a), ab) / n2))
    return dist(p, add(a, mul(ab, t)))


def curve_distance(p, curve):
    """Distance from p to a curve given as ("seg", a, b), ("line", point, direction)
    (endless, the axes), ("circle", centre, radius) or ("poly", [points])."""
    kind = curve[0]
    if kind == "seg":
        return segment_distance(p, curve[1], curve[2])
    if kind == "line":
        d = unit(curve[2])
        if d is None:
            return dist(p, curve[1])
        v = sub(p, curve[1])
        return abs(v[0] * d[1] - v[1] * d[0])
    if kind == "circle":
        return abs(dist(p, curve[1]) - curve[2])
    if kind == "poly":
        pts = curve[1]
        if len(pts) == 1:
            return dist(p, pts[0])
        return min(segment_distance(p, pts[i], pts[i + 1]) for i in range(len(pts) - 1))
    return float("inf")


def poly(points):
    """A curve given by points ("poly", points, bounding box) for near_curve."""
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return ("poly", list(points), (min(xs), min(ys), max(xs), max(ys)))


def near_curve(p, curve, tol):
    """The curve passes within tol of p (a quick box test first: this runs for every
    curve of the sketch on every mouse move)."""
    kind = curve[0]
    if kind == "seg":
        return segment_within(p, curve[1], curve[2], tol)
    if kind == "poly" and len(curve) > 2:
        x0, y0, x1, y1 = curve[2]
        if p[0] < x0 - tol or p[0] > x1 + tol or p[1] < y0 - tol or p[1] > y1 + tol:
            return False
    return curve_distance(p, curve) <= tol


def grid_line(value, grid):
    """The nearest grid line (FreeCAD's rounding)."""
    q = value / grid
    return (math.ceil(q - 0.5) if q < 0 else math.floor(q + 0.5)) * grid


def grid_snap(value, grid):
    """FreeCAD's grid snap of one coordinate: to the nearest grid line when closer
    than a fifth of the spacing."""
    if not grid or grid <= 0:
        return value
    nearest = grid_line(value, grid)
    return nearest if abs(value - nearest) < grid / 5.0 else value


def segment_within(p, a, b, tol):
    """The segment a-b passes within tol of p (box test first)."""
    if p[0] < min(a[0], b[0]) - tol or p[0] > max(a[0], b[0]) + tol:
        return False
    if p[1] < min(a[1], b[1]) - tol or p[1] > max(a[1], b[1]) + tol:
        return False
    return segment_distance(p, a, b) <= tol


def touches(point, a, b, eps):
    """The point is an end of the segment a-b or lies on it."""
    return segment_within(point, a, b, eps)


# -- what is under the pointer --------------------------------------------------------
def nearest_vertex(raw, vertices, tol):
    """(key, point) of the vertex nearest to raw within tol, or None."""
    best = None
    for key, point in vertices:
        d = dist(raw, point)
        if d <= tol and (best is None or d < best[0]):
            best = (d, key, point)
    return (best[1], best[2]) if best else None


def nearest_line(raw, lines, tol):
    """(geo, a, b) of the inference line nearest to raw within tol, or None."""
    best = None
    for geo, a, b in lines:
        if not segment_within(raw, a, b, tol):
            continue
        d = segment_distance(raw, a, b)
        if best is None or d < best[0]:
            best = (d, (geo, a, b))
    return best[1] if best else None


def remember(items, item, keep):
    """Add item as the newest of a short "last hovered" list (Fusion keeps 3)."""
    items = [i for i in items if i != item]
    items.append(item)
    return items[-keep:] if keep > 0 else []


# -- snap points (Fusion: end points, middles, centres; SciForge adds quadrants and the
# crossings of curves) ----------------------------------------------------------------
END, MIDDLE, CENTRE, QUADRANT, CROSSING = "end", "mid", "centre", "quadrant", "crossing"
VERTEX_KINDS = (END, CENTRE)  # FreeCAD sketch points: a click there gets a Coincident
QUADRANTS = (0.0, 0.5 * math.pi, math.pi, 1.5 * math.pi)


class SnapPoint:
    """A point a click snaps to exactly.

    kind   END (a curve's end, a sketch point, the origin), MIDDLE (of a line or arc),
           CENTRE (of a circle, arc or ellipse), QUADRANT (0/90/180/270 degrees on a
           circle or arc), CROSSING (where two curves cross)
    point  (x, y) in sketch millimetres
    key    (geo, pos) of FreeCAD's sketch point for END / CENTRE (Coincident), else None
    geo    the curve it belongs to (MIDDLE, QUADRANT, CROSSING: the first curve)
    other  CROSSING: the second curve
    """

    __slots__ = ("kind", "point", "key", "geo", "other")

    def __init__(self, kind, point, key=None, geo=None, other=None):
        self.kind = kind
        self.point = point
        self.key = key
        self.geo = geo
        self.other = other

    def __repr__(self):
        return "SnapPoint(%s, %r, key=%r, geo=%r, other=%r)" % (
            self.kind,
            self.point,
            self.key,
            self.geo,
            self.other,
        )


def _angle(c, p):
    return math.atan2(p[1] - c[1], p[0] - c[0])


def on_arc(angle, start, end, mid):
    """True when the direction `angle` (radians, from the centre) lies on the arc that
    runs from the angle `start` to `end` through `mid` (either way round)."""
    two_pi = 2.0 * math.pi

    def ccw(a, b):  # the counterclockwise sweep from a to b, 0..2pi
        return (b - a) % two_pi

    sweep = ccw(start, end)
    if ccw(start, mid) <= sweep:  # the arc runs counterclockwise from start to end
        return ccw(start, angle) <= sweep + 1e-12
    return ccw(end, angle) <= two_pi - sweep + 1e-12


def snap_points(items):
    """Every snap point of the sketch's curves and of its projected (external) curves.

    items: descriptions of the curves (sketch_infer.describe), each starting with its
    kind and FreeCAD geometry index:
      ("point", geo, p)
      ("line", geo, a, b)
      ("circle", geo, centre, radius)
      ("arc", geo, centre, radius, start, end, mid)      (mid: the arc's middle point)
      ("ellipse", geo, centre)
      ("conic_arc", geo, centre, start, end)             (arcs of ellipse, hyperbola...)
      ("spline", geo, start, end)
    FreeCAD numbers a curve's points 1 (start), 2 (end), 3 (centre)."""
    out = []
    for item in items:
        kind, geo = item[0], item[1]
        if kind == "point":
            out.append(SnapPoint(END, item[2], (geo, 1)))
        elif kind == "line":
            a, b = item[2], item[3]
            out += [SnapPoint(END, a, (geo, 1)), SnapPoint(END, b, (geo, 2))]
            if dist(a, b) > 1e-9:
                out.append(SnapPoint(MIDDLE, mul(add(a, b), 0.5), geo=geo))
        elif kind == "circle":
            c, r = item[2], item[3]
            out.append(SnapPoint(CENTRE, c, (geo, 3)))
            for q in QUADRANTS:
                p = (c[0] + r * math.cos(q), c[1] + r * math.sin(q))
                out.append(SnapPoint(QUADRANT, p, geo=geo))
        elif kind == "arc":
            c, r, start, end, mid = item[2:7]
            out += [
                SnapPoint(END, start, (geo, 1)),
                SnapPoint(END, end, (geo, 2)),
                SnapPoint(CENTRE, c, (geo, 3)),
                SnapPoint(MIDDLE, mid, geo=geo),
            ]
            a0, a1, am = _angle(c, start), _angle(c, end), _angle(c, mid)
            eps = 1e-9 * max(1.0, r)
            for q in QUADRANTS:
                p = (c[0] + r * math.cos(q), c[1] + r * math.sin(q))
                if not on_arc(q, a0, a1, am):
                    continue
                if min(dist(p, start), dist(p, end), dist(p, mid)) <= eps:
                    continue  # already an end or the middle
                out.append(SnapPoint(QUADRANT, p, geo=geo))
        elif kind == "ellipse":
            out.append(SnapPoint(CENTRE, item[2], (geo, 3)))
        elif kind == "conic_arc":
            out += [
                SnapPoint(END, item[3], (geo, 1)),
                SnapPoint(END, item[4], (geo, 2)),
                SnapPoint(CENTRE, item[2], (geo, 3)),
            ]
        elif kind == "spline":
            out += [SnapPoint(END, item[2], (geo, 1)), SnapPoint(END, item[3], (geo, 2))]
    return out


def nearest_snap(raw, points, tol):
    """The snap point nearest to raw within tol, or None. Where points lie on top of
    each other (a corner of the sketch on a projected corner, an end on a middle) a
    sketch point (Coincident) wins, then the sketch's own curves over projected ones."""
    best = None
    for s in points:
        d = dist(raw, s.point)
        if d > tol:
            continue
        rank = (0 if s.kind in VERTEX_KINDS else 1, 0 if _own(s) else 1)
        if best is None or d < best[0] - 1e-9 or (abs(d - best[0]) <= 1e-9 and rank < best[1]):
            best = (d, rank, s)
    return best[2] if best else None


def _own(snap):
    geo = snap.key[0] if snap.key is not None else snap.geo
    return geo is not None and geo >= 0


def crossings(raw, items, tol):
    """Where two curves near `raw` (within tol) cross, as CROSSING snap points (lines,
    circles, arcs; the ends of curves are END points already and are left out)."""
    near = []
    for item in items:
        kind = item[0]
        if kind == "line" and segment_within(raw, item[2], item[3], tol):
            near.append(item)
        elif kind in ("circle", "arc") and abs(dist(raw, item[2]) - item[3]) <= tol:
            near.append(item)
    out = []
    for i in range(len(near)):
        for j in range(i + 1, len(near)):
            for p in _cross(near[i], near[j]):
                if dist(p, raw) > tol or _is_end(p, near[i]) or _is_end(p, near[j]):
                    continue
                out.append(SnapPoint(CROSSING, p, geo=near[i][1], other=near[j][1]))
    return out


def _is_end(p, item, eps=1e-7):
    if item[0] == "line":
        return dist(p, item[2]) <= eps or dist(p, item[3]) <= eps
    if item[0] == "arc":
        return dist(p, item[4]) <= eps or dist(p, item[5]) <= eps
    return False


def _cross(a, b):
    """Crossing points of two curve descriptions (line / circle / arc)."""
    if a[0] != "line" and b[0] == "line":
        a, b = b, a
    if a[0] == "line" and b[0] == "line":
        p = _line_line(a[2], a[3], b[2], b[3])
        return [p] if p is not None else []
    if a[0] == "line":
        points = _line_circle(a[2], a[3], b[2], b[3])
        return [p for p in points if _on_item(p, b)]
    points = _circle_circle(a[2], a[3], b[2], b[3])
    return [p for p in points if _on_item(p, a) and _on_item(p, b)]


def _on_item(p, item):
    if item[0] != "arc":
        return True
    c, _r, start, end, mid = item[2:7]
    return on_arc(_angle(c, p), _angle(c, start), _angle(c, end), _angle(c, mid))


def _line_line(a, b, c, d):
    r, s = sub(b, a), sub(d, c)
    den = r[0] * s[1] - r[1] * s[0]
    if abs(den) < 1e-12 * max(1.0, length(r) * length(s)):
        return None  # parallel
    t = ((c[0] - a[0]) * s[1] - (c[1] - a[1]) * s[0]) / den
    u = ((c[0] - a[0]) * r[1] - (c[1] - a[1]) * r[0]) / den
    if -1e-9 <= t <= 1 + 1e-9 and -1e-9 <= u <= 1 + 1e-9:
        return add(a, mul(r, t))
    return None


def _line_circle(a, b, c, r):
    d = sub(b, a)
    f = sub(a, c)
    qa = dot(d, d)
    if qa < 1e-24:
        return []
    qb = 2 * dot(f, d)
    qc = dot(f, f) - r * r
    disc = qb * qb - 4 * qa * qc
    if disc < 0:
        return []
    root = math.sqrt(disc)
    out = []
    for t in ((-qb - root) / (2 * qa), (-qb + root) / (2 * qa)):
        if -1e-9 <= t <= 1 + 1e-9:
            p = add(a, mul(d, t))
            if all(dist(p, q) > 1e-9 for q in out):
                out.append(p)
    return out


def _circle_circle(c1, r1, c2, r2):
    d = dist(c1, c2)
    if d < 1e-12 or d > r1 + r2 + 1e-9 or d < abs(r1 - r2) - 1e-9:
        return []
    a = (r1 * r1 - r2 * r2 + d * d) / (2 * d)
    h = math.sqrt(max(0.0, r1 * r1 - a * a))
    u = mul(sub(c2, c1), 1.0 / d)
    m = add(c1, mul(u, a))
    n = (-u[1], u[0])
    points = [add(m, mul(n, h))]
    if h > 1e-9:
        points.append(add(m, mul(n, -h)))
    return points


def snap_result(snap, start=None):
    """The Result of a click on a snap point (the point is placed exactly there)."""
    result = Result(snap.point)
    result.snap = snap
    result.start = start
    return result


# -- the inference ----------------------------------------------------------------
def infer(raw, start, acquired, lines, vertices, curves, px, opt, parallel_lines=(), anchors=()):
    """Where the point the tool is placing should go (a Result), or None to leave the
    pointer alone.

    raw        the pointer on the sketch
    start      the point the new direction starts from (a line's first point, a slot's
               first centre), or None when the point has no direction (before the first
               click; a rectangle corner, a circle's centre...)
    acquired   [(key, point)] points that make guides (hovered + this command's)
    lines      [(geo, a, b)] lines a new line can be perpendicular to (not construction)
    vertices   [(key, point)] every point FreeCAD snaps to
    curves     every curve FreeCAD snaps to (see curve_distance)
    parallel_lines  [(geo, a, b)] hovered lines a new line can be parallel to
    anchors    points this shape already placed (a rectangle's first corner, a circle's
               centre): no guide from them (lining the new point up with them would
               flatten the shape; for a line, level/upright covers it)
    """
    pick = opt.pick_px * px
    if nearest_vertex(raw, vertices, pick) is not None:
        return None  # FreeCAD snaps to that point
    if any(near_curve(raw, c, pick) for c in curves):
        result = _ends_on_line(raw, start, lines, pick, px, opt) if start else None
        if result is not None:
            result.start = start
        return result  # None: FreeCAD snaps onto that curve
    direction = None
    if start is not None and dist(raw, start) >= opt.min_len_px * px:
        direction = _direction(raw, start, lines, parallel_lines, px, opt)
    best_x, best_y = _guides(raw, start, acquired, px, opt, anchors)
    result = _combine(raw, start, direction, best_x, best_y, px, opt)
    if result is not None:
        result.start = start
    return result


def _ends_on_line(raw, start, lines, pick, px, opt):
    """A new line ending on another line at about 90 degrees: the point goes to the
    foot of the perpendicular from the start (on that line)."""
    eps = max(1e-4, 0.05 * px)
    best = None
    for geo, a, b in lines:
        if not segment_within(raw, a, b, pick) or touches(start, a, b, eps):
            continue
        ab = sub(b, a)
        n2 = dot(ab, ab)
        if n2 < 1e-18:
            continue
        t = dot(sub(start, a), ab) / n2
        if t < -1e-9 or t > 1 + 1e-9:
            continue  # the foot is beyond the line's ends
        foot = add(a, mul(ab, t))
        if dist(foot, start) < opt.min_len_px * px:
            continue
        if abs(t - 0.5) < 0.05:
            continue  # FreeCAD snaps to the line's middle there (SnapManager: 5%)
        deviation = angle_between(sub(raw, start), sub(foot, start))
        if deviation <= math.radians(opt.perp_deg) and (best is None or deviation < best[0]):
            best = (deviation, geo, a, b, foot)
    if best is None:
        return None
    _deviation, geo, a, b, foot = best
    d = unit(sub(foot, start))
    kind = _axis_kind(d, math.radians(0.1))
    result = Result(foot, kind=kind or PERPENDICULAR, direction=d, other=None if kind else geo)
    result.on_line = True
    if not kind:
        result.corner = foot
        far = a if dist(a, foot) > dist(b, foot) else b
        result.along = unit(sub(far, foot))
    return result


def _axis_kind(d, tol):
    """HORIZONTAL / VERTICAL when the direction d is that close to an axis."""
    ang = abs(math.atan2(d[1], d[0]))
    if ang <= tol or math.pi - ang <= tol:
        return HORIZONTAL
    if abs(ang - math.pi / 2) <= tol:
        return VERTICAL
    return None


def diagonal(d, tol):
    """The unit direction at 45, 135, 225 or 315 degrees that d is within tol (radians)
    of, or None."""
    ang = math.atan2(d[1], d[0])
    nearest = (math.floor(ang / (math.pi / 2)) + 0.5) * (math.pi / 2)
    if abs(ang - nearest) <= tol:
        return (math.cos(nearest), math.sin(nearest))
    return None


def diagonal_angle(d):
    """The multiple of 45 degrees (radians, -pi..pi) nearest to the direction d."""
    ang = math.atan2(d[1], d[0])
    snapped = round(ang / (math.pi / 4)) * (math.pi / 4)
    return snapped - 2 * math.pi if snapped > math.pi + 1e-12 else snapped


def _direction(raw, start, lines, parallel_lines, px, opt):
    """(kind, unit direction, other line, corner, along) the new line snaps to, or None.
    Level/upright first (FreeCAD adds that constraint itself), then perpendicular to a
    line through the start, then 45 degrees (and 135, 225, 315: beyond Fusion), then
    parallel to a hovered line (when switched on)."""
    d = sub(raw, start)
    kind = _axis_kind(d, math.radians(opt.hv_deg))
    if kind == HORIZONTAL:
        return (kind, (1.0 if d[0] >= 0 else -1.0, 0.0), None, None, None)
    if kind == VERTICAL:
        return (kind, (0.0, 1.0 if d[1] >= 0 else -1.0), None, None, None)
    eps = max(1e-4, 0.05 * px)
    best = None
    for geo, a, b in lines:
        if not touches(start, a, b, eps):
            continue
        u = unit(sub(b, a))
        if u is None:
            continue
        n = (-u[1], u[0])
        if dot(d, n) < 0:
            n = (-n[0], -n[1])
        deviation = angle_between(d, n)
        if deviation <= math.radians(opt.perp_deg) and (best is None or deviation < best[0]):
            far = a if dist(a, start) > dist(b, start) else b
            along = unit(sub(far, start)) if dist(far, start) > eps else u
            best = (deviation, geo, n, along)
    if best is not None:
        return (PERPENDICULAR, best[2], best[1], start, best[3])
    if opt.diag_deg > 0:
        diag = diagonal(d, math.radians(opt.diag_deg))
        if diag is not None:
            return (DIAGONAL, diag, None, None, None)
    if opt.parallel:
        best = None
        for geo, a, b in parallel_lines:
            if touches(start, a, b, eps):
                continue  # parallel to a line through the start = on top of it
            u = unit(sub(b, a))
            if u is None:
                continue
            if dot(d, u) < 0:
                u = (-u[0], -u[1])
            deviation = angle_between(d, u)
            if deviation <= math.radians(opt.parallel_deg) and (
                best is None or deviation < best[0]
            ):
                best = (deviation, geo, u)
        if best is not None:
            return (PARALLEL, best[2], best[1], None, None)
    return None


def _guides(raw, start, acquired, px, opt, anchors=()):
    """The nearest vertical guide (same x) and horizontal guide (same y), or None."""
    tol = opt.guide_px * px
    eps = max(1e-4, 0.05 * px)
    near = opt.pick_px * px  # anchors are where FreeCAD put them, known to a pixel or so
    best_x = best_y = None
    for key, point in acquired:
        if start is not None and dist(point, start) <= eps:
            continue  # the line's own start: level/upright covers it
        if any(dist(point, a) <= near for a in anchors):
            continue  # a point of the shape being drawn
        dx, dy = abs(raw[0] - point[0]), abs(raw[1] - point[1])
        if dx <= tol and (best_x is None or dx < best_x[0]):
            best_x = (dx, Guide(key, point, SAME_X))
        if dy <= tol and (best_y is None or dy < best_y[0]):
            best_y = (dy, Guide(key, point, SAME_Y))
    return (best_x[1] if best_x else None), (best_y[1] if best_y else None)


def _combine(raw, start, direction, guide_x, guide_y, px, opt):
    tol = opt.guide_px * px
    if direction is not None:
        kind, d, other, corner, along = direction
        best = None
        for guide in (guide_x, guide_y):
            if guide is None:
                continue
            i = 0 if guide.axis == SAME_X else 1
            if abs(d[i]) < 1e-9:
                continue  # the guide runs along the line: nothing to meet
            t = (guide.anchor[i] - start[i]) / d[i]
            if t <= 0:
                continue
            point = add(start, mul(d, t))
            gap = dist(point, raw)
            if gap <= 2 * tol and (best is None or gap < best[0]):
                best = (gap, point, guide)
        if best is not None:
            result = Result(best[1], [best[2]], kind, d, other)
        else:
            t = dot(sub(raw, start), d)
            point = add(start, mul(d, t))
            if kind == HORIZONTAL:
                point = (grid_snap(point[0], opt.grid), point[1])
            elif kind == VERTICAL:
                point = (point[0], grid_snap(point[1], opt.grid))
            result = Result(point, [], kind, d, other)
        if kind == PERPENDICULAR:
            result.corner, result.along = corner, along
        return result
    if guide_x is None and guide_y is None:
        return None
    x = guide_x.anchor[0] if guide_x else grid_snap(raw[0], opt.grid)
    y = guide_y.anchor[1] if guide_y else grid_snap(raw[1], opt.grid)
    return Result((x, y), [g for g in (guide_x, guide_y) if g is not None])


def locked_values(result, start=None):
    """The coordinates a result fixes: (axis index, value) pairs (a guide keeps x or y,
    a level line keeps the start's y, an upright one its x)."""
    start = start if start is not None else result.start
    locked = [((0, g.anchor[0]) if g.axis == SAME_X else (1, g.anchor[1])) for g in result.guides]
    if start is not None and result.kind == HORIZONTAL:
        locked.append((1, start[1]))
    elif start is not None and result.kind == VERTICAL:
        locked.append((0, start[0]))
    return locked


def grid_off(result, grid, px):
    """True when FreeCAD's own grid snap has to be off while it takes this point: it
    would pull a fixed coordinate (or a slanted direction) off the inference. Otherwise
    it stays on, so the free coordinate lands exactly on the grid as before. A snap
    point is exact already (the grid must not pull it off)."""
    if result.snap is not None or result.kind in (PERPENDICULAR, PARALLEL, DIAGONAL):
        return True
    if result.on_line:
        return True
    if not grid or grid <= 0:
        return False
    for _axis, value in locked_values(result):
        off = abs(value - grid_line(value, grid))
        if 1e-6 < off < grid / 5.0 + px:
            return True
    return False


def exact_point(result, placed, px, start=None):
    """Where the point FreeCAD placed (`placed`, at most a pixel away from the guide)
    goes exactly, or None when FreeCAD put it somewhere else (a typed length, a point
    it snapped to instead). A free coordinate FreeCAD placed elsewhere (a typed length)
    is kept.
    `start`: the line's first point as it is now (default: as it was when inferred)."""
    tol = 1.5 * px
    start = start if start is not None else result.start
    if result.snap is not None:
        return result.point if dist(placed, result.point) <= tol else None
    if result.on_line or (result.guides and result.direction is not None):
        return result.point if dist(placed, result.point) <= tol else None
    if result.guides or result.kind in (HORIZONTAL, VERTICAL):
        # a free coordinate within a pixel of the inferred one (the grid) takes its value
        point = [
            result.point[i] if abs(placed[i] - result.point[i]) <= tol else placed[i]
            for i in (0, 1)
        ]
        for axis, value in locked_values(result, start):
            if abs(placed[axis] - value) > tol:
                return None
            point[axis] = value
        if result.kind in (HORIZONTAL, VERTICAL) and dot(sub(placed, start), result.direction) <= 0:
            return None
        return tuple(point)
    if result.direction is not None and start is not None:
        d = result.direction
        v = sub(placed, start)
        if abs(v[0] * d[1] - v[1] * d[0]) > tol or dot(v, d) <= 0:
            return None
        return add(start, mul(d, dot(v, d)))
    return None


def right_angle_mark(corner, a, b, size):
    """The little square corner symbol for a right angle at `corner` between the unit
    directions a and b: three points of a polyline."""
    p1 = add(corner, mul(a, size))
    p2 = add(p1, mul(b, size))
    p3 = add(corner, mul(b, size))
    return [p1, p2, p3]


def parallel_mark(a, b, size):
    """Two short strokes beside the middle of the segment a-b (the parallel symbol)."""
    d = unit(sub(b, a))
    if d is None:
        return []
    n = (-d[1], d[0])
    mid = mul(add(a, b), 0.5)
    strokes = []
    for k in (1.0, 1.8):
        c = add(mid, mul(n, size * k))
        strokes.append([add(c, mul(d, -size * 0.6)), add(c, mul(d, size * 0.6))])
    return strokes


# The marks sit near the pointer's end: FreeCAD's length and angle boxes cover the
# middle of the line (above it and below it).
MARK_ALONG = 0.92


def level_mark(a, b, size):
    """SciForge's level mark: a short horizontal stroke under the level line a-b, near
    its end b (shown while drawing; FreeCAD's own glyph takes over after the click)."""
    at = add(a, mul(sub(b, a), MARK_ALONG))
    c = (at[0], at[1] - size * 1.2)
    return [[(c[0] - size * 0.8, c[1]), (c[0] + size * 0.8, c[1])]]


def upright_mark(a, b, size):
    """SciForge's upright mark: a short vertical stroke beside the upright line a-b,
    near its end b."""
    at = add(a, mul(sub(b, a), MARK_ALONG))
    c = (at[0] + size * 1.2, at[1])
    return [[(c[0], c[1] - size * 0.8), (c[0], c[1] + size * 0.8)]]


def tangent_mark(joint, tangent, away, size):
    """SciForge's tangent mark while a tangent arc is dragged: a short stroke along the
    tangent, a little outside the joint (on the side away from the arc's centre)."""
    c = add(joint, mul(away, size * 1.2))
    return [[add(c, mul(tangent, -size * 0.8)), add(c, mul(tangent, size * 0.8))]]


# -- the other tools' previews --------------------------------------------------------
def preview_anchor(kind, polylines):
    """The point the direction of the shape's next point starts from, read from
    FreeCAD's preview (its edit curve, split into polylines), or None. A line: its first
    point; a slot: the centre of its first arc (a half circle: the middle of the chord
    between the arc's ends). Other shapes have no direction."""
    if kind == "line":
        if len(polylines) == 1 and len(polylines[0]) == 2:
            return polylines[0][0]
        return None
    if kind == "slot":
        if len(polylines) >= 3 and len(polylines[0]) >= 3:
            arc = polylines[0]
            return mul(add(arc[0], arc[-1]), 0.5)
        return None
    return None


def preview_kind(polylines):
    """The shape a preview (FreeCAD's edit curve as polylines) belongs to, as far as it
    can be told from its parts: "line", "circle" (a circle, or the first step of an arc
    or three-point circle), "rect" (four sides), "polygon", "slot" (two arcs, two
    sides), "arc" (an arc and two radius lines), "arc3" (a circle and a line), or
    None for no preview."""
    if not polylines:
        return None
    sizes = [len(p) for p in polylines]
    curved = sum(1 for n in sizes if n > 2)
    straight = len(sizes) - curved
    if len(sizes) == 1:
        return "line" if sizes[0] == 2 else "circle"
    if curved == 0:
        return "rect" if straight == 4 else "polygon"
    if curved == 2 and straight == 2:
        return "slot"
    if curved == 1 and straight == 2:
        return "arc"
    if curved == 1 and straight == 1:
        return "arc3"
    return None


# which previews a tool of each kind can show (the arc tools start with a circle, a
# four-sided polygon looks like a rectangle)
PREVIEWS = {
    "line": ("line",),
    "rect": ("rect",),
    "rect_center": ("rect",),
    "circle": ("circle",),
    "circle3": ("circle",),
    "arc": ("circle", "arc"),
    "arc3": ("circle", "arc3", "arc"),
    "slot": ("slot",),
    "polygon": ("polygon", "rect"),
}


def tool_kind(recorded, polylines):
    """The kind of shape being drawn: the tool SciForge last ran (`recorded`, a kind or
    None), unless FreeCAD's preview shows another shape (a tool started another way,
    FreeCAD's own toolbar): then what the preview shows. No preview: the record."""
    if recorded is None:
        return None
    shown = preview_kind(polylines)
    if shown is None or shown in PREVIEWS.get(recorded, ()):
        return recorded
    return shown


def preview_pointer(kind, polylines, near):
    """The point of FreeCAD's preview that follows the pointer (the line's end, a slot's
    second centre, otherwise the preview vertex nearest to `near`), or None. A typed
    value puts it elsewhere: then the guide is not shown and nothing is added."""
    if not polylines:
        return None
    if kind == "line":
        return polylines[0][1] if len(polylines[0]) == 2 else None
    if kind == "slot":
        if len(polylines) >= 3 and len(polylines[1]) >= 3:
            arc = polylines[1]
            return mul(add(arc[0], arc[-1]), 0.5)
        return None
    best = None
    for poly in polylines:
        for p in poly:
            d = dist(p, near)
            if best is None or d < best[0]:
                best = (d, p)
    return best[1] if best else None


# -- the tangent arc (Fusion's Line tool: press on the last point and drag) -----------
class Arc:
    """An arc of a circle: centre, radius, counterclockwise from angle a1 to a2 (as
    FreeCAD's Part.ArcOfCircle), `joint_pos` the end (1 = start, 2 = end) that joins the
    previous curve, `free_pos` the other one (where the pointer is)."""

    def __init__(self, centre, radius, a1, a2, joint_pos):
        self.centre = centre
        self.radius = radius
        self.a1 = a1
        self.a2 = a2
        self.joint_pos = joint_pos
        self.free_pos = 2 if joint_pos == 1 else 1

    def point(self, angle):
        return (
            self.centre[0] + self.radius * math.cos(angle),
            self.centre[1] + self.radius * math.sin(angle),
        )

    def points(self, n=48):
        """A polyline along the arc (for the preview)."""
        step = (self.a2 - self.a1) / n
        return [self.point(self.a1 + i * step) for i in range(n + 1)]

    def __repr__(self):
        return "Arc(%r, %r, %r, %r, joint=%r)" % (
            self.centre,
            self.radius,
            self.a1,
            self.a2,
            self.joint_pos,
        )


def tangent_arc(start, tangent, point, min_len, straight_deg=1.0):
    """The arc that leaves `start` in the direction `tangent` (unit) and ends at `point`,
    or None when the point is too close (min_len) or straight ahead/behind (within
    straight_deg: that is a line, not an arc). The arc's centre lies on the normal at
    the start; the pointer's side picks the side, so moving across the tangent flips
    the arc (Fusion)."""
    d = sub(point, start)
    if length(d) < min_len:
        return None
    n = (-tangent[1], tangent[0])  # the left normal
    dn = dot(d, n)
    if abs(dn) <= length(d) * math.sin(math.radians(straight_deg)):
        return None
    k = dot(d, d) / (2.0 * dn)  # signed: + = centre on the left = turning left (ccw)
    centre = add(start, mul(n, k))
    radius = abs(k)
    a_start = math.atan2(start[1] - centre[1], start[0] - centre[0])
    a_point = math.atan2(point[1] - centre[1], point[0] - centre[0])
    if k > 0:
        # counterclockwise from the start to the point: the joint is the arc's start
        a1, a2 = a_start, a_point
        joint = 1
    else:
        # clockwise from the start: as a counterclockwise arc it runs point -> start
        a1, a2 = a_point, a_start
        joint = 2
    while a2 <= a1:
        a2 += 2 * math.pi
    return Arc(centre, radius, a1, a2, joint)


def chain_tangent(start, curves, eps):
    """The direction a chain of curves leaves `start` in, and the curve's end there:
    (unit tangent, (geo, pos)), or None when no curve ends at `start`. `curves` newest
    first: ("line", geo, a, b) or ("arc", geo, centre, start point, end point) with
    FreeCAD's counterclockwise arcs. A line's far end tells its direction; an arc's
    tangent at its end follows the arc round."""
    for curve in curves:
        if curve[0] == "line":
            _, geo, a, b = curve
            for here, far, pos in ((b, a, 2), (a, b, 1)):
                if dist(here, start) <= eps:
                    t = unit(sub(here, far))
                    if t is not None:
                        return t, (geo, pos)
        elif curve[0] == "arc":
            _, geo, centre, sp, ep = curve
            for here, pos, sign in ((ep, 2, 1.0), (sp, 1, -1.0)):
                if dist(here, start) <= eps:
                    radial = sub(here, centre)
                    t = unit((-radial[1] * sign, radial[0] * sign))
                    if t is not None:
                        return t, (geo, pos)
    return None
