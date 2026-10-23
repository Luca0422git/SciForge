# SPDX-License-Identifier: LGPL-2.1-or-later
"""The geometry of Fusion's sketch Fillet between lines, arcs and circles (no FreeCAD, no
Qt: unit tested). It draws the preview and checks the radius; the fillet itself is made by
FreeCAD's sketch fillet (SketchObject::fillet, the same rule for which arc is kept).

Fusion (Autodesk help "Sketch modification tools": Fillet): pick a corner (a point where
two curves meet) or two curves (two lines, two arcs, a line and an arc), then drag or
type the radius; the arc is tangent to both and the curves are trimmed to it.

The rule (FreeCAD's createFilletGeometry, followed here so the preview is what gets
made): each curve is offset by the radius towards the other curve's pick point; the
fillet's centre is where the offsets cross, the crossing nearest to the two pick points;
the arc touches each curve at the foot of the centre on it.

Curves: ("line", a, b), ("arc", centre, radius, start angle, end angle) (anticlockwise
from start to end, FreeCAD's arcs), ("circle", centre, radius). Points (x, y), angles in
radians.
"""

import math

EPS = 1e-9
WHOLE = 1e-6  # a fillet that leaves less than this of a curve takes it whole (mm)


class FilletError(ValueError):
    """The fillet cannot be made; the message says why."""


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1])


def _mul(a, k):
    return (a[0] * k, a[1] * k)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _len(a):
    return math.hypot(a[0], a[1])


def _unit(a):
    n = _len(a)
    if n <= EPS:
        raise FilletError("A curve has no length.")
    return (a[0] / n, a[1] / n)


def is_round(curve):
    return curve[0] in ("arc", "circle")


# -- the offsets --------------------------------------------------------------------------
def _line_offset(curve, r, toward):
    """The line moved by r to the side of `toward`: (point, direction)."""
    _kind, a, b = curve
    d = _unit(_sub(b, a))
    n = (-d[1], d[0])
    side = 1.0 if _dot(_sub(toward, a), n) >= 0 else -1.0
    return _add(a, _mul(n, side * r)), d


def _circle_offset(curve, r, toward):
    """The circle grown or shrunk by r towards `toward`: (centre, new radius)."""
    c, radius = curve[1], curve[2]
    inside = _len(_sub(toward, c)) < radius
    return c, (radius - r) if inside else (radius + r)


def _line_line(p1, d1, p2, d2):
    den = _cross(d1, d2)
    if abs(den) <= 1e-12:
        return []
    t = _cross(_sub(p2, p1), d2) / den
    return [_add(p1, _mul(d1, t))]


def _line_circle(p, d, c, r):
    if r <= EPS:
        return []
    f = _sub(p, c)
    b = _dot(f, d)
    disc = b * b - (_dot(f, f) - r * r)
    if disc < -1e-12:
        return []
    root = math.sqrt(max(disc, 0.0))
    return [_add(p, _mul(d, -b - root)), _add(p, _mul(d, -b + root))]


def _circle_circle(c1, r1, c2, r2):
    if r1 <= EPS or r2 <= EPS:
        return []
    dist = _len(_sub(c2, c1))
    if dist <= EPS or dist > r1 + r2 + 1e-12 or dist < abs(r1 - r2) - 1e-12:
        return []
    a = (r1 * r1 - r2 * r2 + dist * dist) / (2 * dist)
    h = math.sqrt(max(r1 * r1 - a * a, 0.0))
    u = _unit(_sub(c2, c1))
    m = _add(c1, _mul(u, a))
    n = (-u[1], u[0])
    return [_add(m, _mul(n, h)), _add(m, _mul(n, -h))]


def centres(c1, c2, r, ref1, ref2):
    """The candidate fillet centres of radius r (each curve offset towards the other's
    pick point)."""
    if not is_round(c1) and not is_round(c2):
        p1, d1 = _line_offset(c1, r, ref2)
        p2, d2 = _line_offset(c2, r, ref1)
        return _line_line(p1, d1, p2, d2)
    if is_round(c1) and is_round(c2):
        a, ra = _circle_offset(c1, r, ref2)
        b, rb = _circle_offset(c2, r, ref1)
        return _circle_circle(a, ra, b, rb)
    line, circle, ref_line, ref_circle = (
        (c1, c2, ref1, ref2)
        if not is_round(c1)
        else (
            c2,
            c1,
            ref2,
            ref1,
        )
    )
    p, d = _line_offset(line, r, ref_circle)
    c, rc = _circle_offset(circle, r, ref_line)
    return _line_circle(p, d, c, rc)


def foot(curve, point):
    """The point of the (extended) curve nearest to `point`."""
    if is_round(curve):
        c, radius = curve[1], curve[2]
        v = _sub(point, c)
        if _len(v) <= EPS:
            raise FilletError("The fillet would be centred on the arc's centre.")
        return _add(c, _mul(_unit(v), radius))
    _kind, a, b = curve
    d = _unit(_sub(b, a))
    return _add(a, _mul(d, _dot(_sub(point, a), d)))


def fillet(c1, c2, r, ref1, ref2):
    """(centre, touch point on curve 1, touch point on curve 2) of the fillet of radius r.
    Raises FilletError when there is none."""
    if r <= EPS:
        raise FilletError("The radius must be more than 0.")
    found = centres(c1, c2, r, ref1, ref2)
    if not found:
        raise FilletError("No arc of that radius touches both curves: try a smaller radius.")
    centre = min(found, key=lambda p: _len(_sub(p, ref1)) + _len(_sub(p, ref2)))
    return centre, foot(c1, centre), foot(c2, centre)


def arc_points(centre, t1, t2, n=32):
    """A polyline along the shorter arc from t1 to t2 about centre (the preview)."""
    a1 = math.atan2(t1[1] - centre[1], t1[0] - centre[0])
    a2 = math.atan2(t2[1] - centre[1], t2[0] - centre[0])
    span = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
    radius = _len(_sub(t1, centre))
    return [
        (
            centre[0] + radius * math.cos(a1 + span * i / n),
            centre[1] + radius * math.sin(a1 + span * i / n),
        )
        for i in range(n + 1)
    ]


# -- does it fit -----------------------------------------------------------------------------
def _far_end(curve, corner):
    """The end of an open curve away from the corner (the part that stays ends there)."""
    if curve[0] == "line":
        a, b = curve[1], curve[2]
        return a if _len(_sub(a, corner)) >= _len(_sub(b, corner)) else b
    if curve[0] == "arc":
        c, radius, s, e = curve[1], curve[2], curve[3], curve[4]
        start = _add(c, (radius * math.cos(s), radius * math.sin(s)))
        end = _add(c, (radius * math.cos(e), radius * math.sin(e)))
        return start if _len(_sub(start, corner)) >= _len(_sub(end, corner)) else end
    return None


def _ang(c, p):
    return math.atan2(p[1] - c[1], p[0] - c[0])


def leftover(curve, touch, corner):
    """How much of `curve` stays when it is trimmed to `touch` (mm, from the touch point to
    the curve's far end; less than 0: the touch point is beyond that far end). None for a
    circle (it is cut, never used up)."""
    if curve[0] == "circle":
        return None
    far = _far_end(curve, corner)
    if curve[0] == "line":
        to_corner = _sub(corner, far)
        if _len(to_corner) <= EPS:
            return -1.0
        return _dot(_sub(touch, far), _unit(to_corner))
    c, radius, s, e = curve[1], curve[2], curve[3], curve[4]
    span = (e - s) % (2 * math.pi) or 2 * math.pi
    start = _add(c, (radius * math.cos(s), radius * math.sin(s)))
    if _len(_sub(far, start)) <= 1e-9:
        t = (_ang(c, touch) - s) % (2 * math.pi)  # from the start, anticlockwise
    else:
        t = (e - _ang(c, touch)) % (2 * math.pi)  # from the end, clockwise
    if t > span + (2 * math.pi - span) / 2.0:
        t -= 2 * math.pi  # just beyond the far end
    return t * radius


def fits(curve, ref, touch, corner):
    """True when trimming `curve` to `touch` stays on the curve: the touch point lies
    between the curve's far end and the corner (or past the corner, where FreeCAD extends
    the curve), never beyond that far end. Reaching the far end fits: the fillet then takes
    the curve whole (takes_whole)."""
    rest = leftover(curve, touch, corner)
    return rest is None or rest >= -WHOLE


def leftovers(c1, c2, r, ref1, ref2):
    """(what stays of curve 1, of curve 2) after the fillet of radius r (leftover; None for
    a circle, or when the curves make no corner)."""
    _centre, t1, t2 = fillet(c1, c2, r, ref1, ref2)
    corner = corner_of(c1, c2, ref1, ref2)
    if corner is None:
        return None, None
    return leftover(c1, t1, corner), leftover(c2, t2, corner)


def takes_whole(c1, c2, r, ref1, ref2):
    """(curve 1, curve 2): True for a curve the fillet of radius r uses up (it reaches the
    curve's far end: the curve is kept as construction, the fillet ends there)."""
    rests = leftovers(c1, c2, r, ref1, ref2)
    return tuple(rest is not None and rest < WHOLE for rest in rests)


def largest_radius(c1, c2, ref1, ref2, near):
    """The largest radius whose fillet fits both curves (it then reaches the far end of one
    of them), searched from `near` (any radius, fitting or not): exact, no rounding, so
    nothing of that curve is left. None when no such limit is found (circles)."""

    def ok(r):
        try:
            check(c1, c2, r, ref1, ref2)
            rests = leftovers(c1, c2, r, ref1, ref2)
        except FilletError:
            return False
        return all(rest is None or rest >= 0.0 for rest in rests)  # not even a hair beyond

    near = max(float(near), 1e-6)
    lo = hi = None
    r = near
    if ok(r):
        lo = r
        for _ in range(60):
            r *= 2.0
            if not ok(r):
                hi = r
                break
            lo = r
    else:
        hi = r
        for _ in range(60):
            r /= 2.0
            if ok(r):
                lo = r
                break
            hi = r
    if lo is None or hi is None:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if not lo < mid < hi:
            break
        if ok(mid):
            lo = mid
        else:
            hi = mid
        if hi - lo <= 1e-12 * max(1.0, hi):
            break
    return lo


def corner_of(c1, c2, ref1, ref2):
    """Where the two curves meet (their crossing nearest the pick points), or None."""
    pts = []
    if not is_round(c1) and not is_round(c2):
        pts = _line_line(c1[1], _unit(_sub(c1[2], c1[1])), c2[1], _unit(_sub(c2[2], c2[1])))
    elif is_round(c1) and is_round(c2):
        pts = _circle_circle(c1[1], c1[2], c2[1], c2[2])
    else:
        line, circle = (c1, c2) if not is_round(c1) else (c2, c1)
        pts = _line_circle(line[1], _unit(_sub(line[2], line[1])), circle[1], circle[2])
    if not pts:
        return None
    return min(pts, key=lambda p: _len(_sub(p, ref1)) + _len(_sub(p, ref2)))


def check(c1, c2, r, ref1, ref2):
    """(centre, t1, t2) of a fillet that fits both curves; FilletError (why) otherwise."""
    centre, t1, t2 = fillet(c1, c2, r, ref1, ref2)
    corner = corner_of(c1, c2, ref1, ref2)
    if corner is not None:
        if not fits(c1, ref1, t1, corner):
            raise FilletError("The fillet is larger than the first curve: make it smaller.")
        if not fits(c2, ref2, t2, corner):
            raise FilletError("The fillet is larger than the second curve: make it smaller.")
    return centre, t1, t2


def radius_through(c1, c2, ref1, ref2, pointer, high):
    """The radius the pointer gives (Fusion: drag the fillet out of the corner): the
    fillet whose arc passes as far from the corner as the pointer is, between a tiny one
    and `high`. None when the curves make no corner or no fillet of those radii exists."""
    corner = corner_of(c1, c2, ref1, ref2)
    if corner is None:
        return None
    want = _len(_sub(pointer, corner))

    def gap(r):
        try:
            centre, _t1, _t2 = fillet(c1, c2, r, ref1, ref2)
        except FilletError:
            return None
        return _len(_sub(centre, corner)) - r - want

    lo, hi = high * 1e-4, high
    g_lo, g_hi = gap(lo), gap(hi)
    if g_lo is None or g_hi is None:
        return None
    if g_lo >= 0:
        return lo
    if g_hi <= 0:
        return hi
    for _ in range(60):
        mid = (lo + hi) / 2.0
        g = gap(mid)
        if g is None:
            hi = mid
            continue
        if g < 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def suggested(c1, c2):
    """A starting radius: a fifth of the shorter curve (FreeCAD's tool guesses so)."""
    sizes = []
    for curve in (c1, c2):
        if curve[0] == "line":
            sizes.append(_len(_sub(curve[2], curve[1])))
        elif curve[0] == "arc":
            span = (curve[4] - curve[3]) % (2 * math.pi)
            sizes.append(curve[2] * span)
        else:
            sizes.append(curve[2] * 2 * math.pi)
    return max(min(sizes) * 0.2, 1e-3)
