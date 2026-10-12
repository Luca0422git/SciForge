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

No FreeCAD, no Qt here: plain (x, y) tuples in sketch millimetres, so it is unit tested.
`px` is how many millimetres one screen pixel is at the moment, so tolerances given in
pixels feel the same at every zoom.
"""

import math

HORIZONTAL, VERTICAL = "h", "v"
PERPENDICULAR, PARALLEL = "perp", "parallel"
# a guide keeps one coordinate of a point: "x" = straight above/below it (a vertical
# guide line), "y" = level with it (a horizontal guide line)
SAME_X, SAME_Y = "x", "y"


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
    kind      None, HORIZONTAL, VERTICAL, PERPENDICULAR or PARALLEL (the new line's
              direction)
    direction the unit direction of the new line for `kind`
    other     the other line's geometry index (PERPENDICULAR / PARALLEL)
    on_line   True when the point lies on `other` (a line ending on another line)
    corner    where the right-angle mark goes (PERPENDICULAR), with `along` the other
              line's direction from there
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


# -- the inference ----------------------------------------------------------------
def infer(raw, start, acquired, lines, vertices, curves, px, opt, parallel_lines=()):
    """Where the line tool's point should go (a Result), or None to leave the pointer
    alone.

    raw        the pointer on the sketch
    start      the first point of the line being drawn, or None before the first click
    acquired   [(key, point)] points that make guides (hovered + this command's)
    lines      [(geo, a, b)] lines a new line can be perpendicular to (not construction)
    vertices   [(key, point)] every point FreeCAD snaps to
    curves     every curve FreeCAD snaps to (see curve_distance)
    parallel_lines  [(geo, a, b)] hovered lines a new line can be parallel to
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
    best_x, best_y = _guides(raw, start, acquired, px, opt)
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


def _direction(raw, start, lines, parallel_lines, px, opt):
    """(kind, unit direction, other line, corner, along) the new line snaps to, or None.
    Level/upright first (FreeCAD adds that constraint itself), then perpendicular to a
    line through the start, then parallel to a hovered line (when switched on)."""
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


def _guides(raw, start, acquired, px, opt):
    """The nearest vertical guide (same x) and horizontal guide (same y), or None."""
    tol = opt.guide_px * px
    eps = max(1e-4, 0.05 * px)
    best_x = best_y = None
    for key, point in acquired:
        if start is not None and dist(point, start) <= eps:
            continue  # the line's own start: level/upright covers it
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
    it stays on, so the free coordinate lands exactly on the grid as before."""
    if result.kind in (PERPENDICULAR, PARALLEL) or result.on_line:
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
