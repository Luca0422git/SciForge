# SPDX-License-Identifier: LGPL-2.1-or-later
"""The geometry of Fusion's sketch Chamfer (no FreeCAD, no Qt: unit tested).

Two lines meet at a corner (a shared end, or where their extensions cross). The chamfer
cuts the corner off with a straight line from a point P1 on the first line to a point P2 on
the second; the setbacks are the distances from the corner to P1 and to P2. Fusion's three
types (Autodesk help "Add chamfers to sketch geometry"):

  equal           one distance: both setbacks the same
  distance_angle  the setback on the first line and the angle between the first line and
                  the chamfer (at P1, inside the corner): the second setback follows from
                  the triangle corner-P1-P2 (law of sines)
  two_distances   a setback on each line (the first one on the first line picked)

Points are (x, y) tuples, angles radians.
"""

import math

KINDS = ("equal", "distance_angle", "two_distances")
WHOLE = 1e-6  # a setback this close to a line's reach takes the line whole (mm)
LABELS = {
    "equal": "Equal distance",
    "distance_angle": "Distance and angle",
    "two_distances": "Two distances",
}
EPS = 1e-9


class ChamferError(ValueError):
    """The chamfer cannot be made; the message says why."""


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1])


def _scale(a, k):
    return (a[0] * k, a[1] * k)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _length(a):
    return math.hypot(a[0], a[1])


def _unit(a):
    n = _length(a)
    if n <= EPS:
        raise ChamferError("A line has no length.")
    return (a[0] / n, a[1] / n)


def crossing(line1, line2):
    """Where the (extended) lines cross, or None when they are parallel."""
    (a1, a2), (b1, b2) = line1, line2
    d1, d2 = _sub(a2, a1), _sub(b2, b1)
    den = _cross(d1, d2)
    if abs(den) <= 1e-12 * max(1.0, _length(d1) * _length(d2)):
        return None
    t = _cross(_sub(b1, a1), d2) / den
    return _add(a1, _scale(d1, t))


def _side(line, corner, keep):
    """(unit direction from the corner along the part of `line` that stays, how far the
    line reaches from the corner that way). `keep`: a point on the part that stays (the
    click), or None for the end farther from the corner."""
    a, b = line
    if keep is None:
        far = a if _length(_sub(a, corner)) >= _length(_sub(b, corner)) else b
        return _unit(_sub(far, corner)), _length(_sub(far, corner))
    along = _unit(_sub(b, a))
    if _dot(_sub(keep, corner), along) < 0:
        along = _scale(along, -1.0)
    reach = max(_dot(_sub(a, corner), along), _dot(_sub(b, corner), along))
    return along, reach


def corner(line1, line2, keep1=None, keep2=None):
    """(corner point, u1, u2, reach1, reach2, angle): the corner of the two lines, the
    directions from it along the parts that stay, how far each line reaches from the
    corner, and the angle between the lines at the corner (0..pi)."""
    point = crossing(line1, line2)
    if point is None:
        raise ChamferError("Those lines are parallel: they make no corner.")
    u1, reach1 = _side(line1, point, keep1)
    u2, reach2 = _side(line2, point, keep2)
    if reach1 <= EPS or reach2 <= EPS:
        raise ChamferError("Click the lines on the side that stays.")
    angle = math.acos(max(-1.0, min(1.0, _dot(u1, u2))))
    if angle <= 1e-6 or angle >= math.pi - 1e-6:
        raise ChamferError("Those lines make no corner.")
    return point, u1, u2, reach1, reach2, angle


def default_angle(angle):
    """The angle a Distance and angle chamfer starts with: the one that cuts both lines
    back by the same amount (45 degrees in a square corner)."""
    return (math.pi - angle) / 2.0


def setbacks(kind, angle, distance, second=None):
    """(setback on line 1, setback on line 2). `second`: the angle (distance_angle) or the
    second distance (two_distances)."""
    if kind not in KINDS:
        raise ChamferError("Unknown chamfer type %r." % kind)
    if distance is None or distance <= EPS:
        raise ChamferError("The distance must be more than 0.")
    if kind == "equal":
        return distance, distance
    if kind == "two_distances":
        if second is None or second <= EPS:
            raise ChamferError("The second distance must be more than 0.")
        return distance, second
    alpha = default_angle(angle) if second is None else second
    limit = math.pi - angle
    if alpha <= 1e-6 or alpha >= limit - 1e-6:
        raise ChamferError(
            "The angle must be between 0 and %.4g degrees here." % math.degrees(limit)
        )
    return distance, distance * math.sin(alpha) / math.sin(angle + alpha)


def chamfer_angle(angle, s1, s2):
    """The angle between the first line and the chamfer (at P1, inside the corner) of the
    setbacks s1, s2 at a corner of `angle`."""
    p2 = (s2 * math.cos(angle), s2 * math.sin(angle))
    to_corner = (-s1, 0.0)
    to_p2 = _sub(p2, (s1, 0.0))
    c = _dot(to_corner, to_p2) / (_length(to_corner) * _length(to_p2))
    return math.acos(max(-1.0, min(1.0, c)))


def check_fits(s1, s2, reach1, reach2):
    """The chamfer must not run past the far end of a line. It may reach it: the chamfer
    then takes that line whole (takes_whole) and meets the next corner."""
    if s1 > reach1 + WHOLE:
        raise ChamferError("The chamfer is longer than the first line: make it smaller.")
    if s2 > reach2 + WHOLE:
        raise ChamferError("The chamfer is longer than the second line: make it smaller.")


def takes_whole(setback, reach):
    """True when the setback reaches the far end of its line: nothing of the line is left
    (it is kept as construction, the chamfer runs to its far end)."""
    return setback >= reach - WHOLE


def largest(kind, name, angle, reach1, reach2, second=None):
    """The largest value of `name` ("distance" or "distance2") that fits the two lines at a
    corner of `angle`: the chamfer then runs to the far end of a line. `second`: the angle
    of Distance and angle (None: default_angle). None when nothing limits it."""
    if kind == "equal":
        return min(reach1, reach2)
    if kind == "two_distances":
        return reach1 if name == "distance" else reach2
    if kind != "distance_angle" or name != "distance":
        return None
    alpha = default_angle(angle) if second is None else second
    ratio = math.sin(alpha) / math.sin(angle + alpha)  # second setback per unit of the first
    if ratio <= EPS:
        return reach1
    return min(reach1, reach2 / ratio)


def points(point, u1, u2, s1, s2):
    """(P1, P2): the ends of the chamfer line."""
    return _add(point, _scale(u1, s1)), _add(point, _scale(u2, s2))


def pointer_values(kind, point, u1, u2, angle, pointer):
    """What the pointer gives while placing: {"distance": ..., "distance2" or "angle": ...}.
    Equal distance: the chamfer runs through the pointer (square to the corner's
    bisector); the other types: the pointer's distance from the corner along each line."""
    rel = _sub(pointer, point)
    t1 = max(_dot(rel, u1), 0.0)
    t2 = max(_dot(rel, u2), 0.0)
    if kind == "equal":
        bisector = _unit(_add(u1, u2))
        t = max(_dot(rel, bisector), 0.0)
        return {"distance": t / math.cos(angle / 2.0)}
    if kind == "two_distances":
        return {"distance": t1, "distance2": t2}
    return {"distance": t1, "angle": default_angle(angle)}


def fillet_radius(setback, angle):
    """The radius of the arc that touches both lines `setback` from the corner (FreeCAD's
    sketch fillet / chamfer works with that radius)."""
    return setback * math.tan(angle / 2.0)


# -- a line and an arc -------------------------------------------------------------------------
# Fusion's sketch chamfer is documented for two lines (Autodesk help "Add chamfers to sketch
# geometry": a vertex or two lines; the API's chamfers are SketchLines methods). SciForge
# also cuts the corner between a line and an arc (it goes further; the sketch-2 brief asks
# for it): the setback on the line is measured along it, the one on the arc as the straight
# distance from the corner to where the chamfer meets the arc (what a sketch dimension
# between the two points shows). Distance and angle: the distance on the line and the angle
# between the line and the chamfer.
# An arc is (centre, radius, start angle, end angle), anticlockwise from start to end.
TWO_PI = 2.0 * math.pi


def arc_ends(arc):
    c, r, s, e = arc
    return (c[0] + r * math.cos(s), c[1] + r * math.sin(s)), (
        c[0] + r * math.cos(e),
        c[1] + r * math.sin(e),
    )


def _angle_of(c, p):
    return math.atan2(p[1] - c[1], p[0] - c[0])


def _line_circle(a, b, c, r):
    """Where the (extended) line a-b crosses the circle."""
    d = _unit(_sub(b, a))
    f = _sub(a, c)
    k = _dot(f, d)
    disc = k * k - (_dot(f, f) - r * r)
    if disc < -1e-9:
        return []
    root = math.sqrt(max(disc, 0.0))
    return [_add(a, _scale(d, -k - root)), _add(a, _scale(d, -k + root))]


def line_arc_corner(line, arc, keep_line=None, keep_arc=None):
    """The corner of a line and an arc: a dict with the corner point, the line's direction
    from it along the part that stays (u1) and how far it reaches, the arc's tangent there
    towards its part that stays (u2), sigma (+1: that way is anticlockwise), how far round
    the arc that part reaches (radians), and the angle between u1 and u2."""
    c, r, _s, _e = arc
    if r <= EPS:
        raise ChamferError("The arc has no size.")
    start, end = arc_ends(arc)
    a, b = line
    point = None
    for p in (a, b):
        for q in (start, end):
            if _length(_sub(p, q)) <= 1e-7:
                point = p
    if point is None:
        hits = _line_circle(a, b, c, r)
        if not hits:
            raise ChamferError("That line and arc make no corner: they do not meet.")
        refs = [p for p in (keep_line, keep_arc) if p is not None] or [a, b]

        def cost(p):
            return sum(_length(_sub(p, q)) for q in refs)

        point = min(hits, key=cost)
    u1, reach1 = _side(line, point, keep_line)
    theta = _angle_of(c, point)
    d_start, d_end = _length(_sub(start, point)), _length(_sub(end, point))
    if keep_arc is not None:
        # the part that stays runs from the corner past the click
        sigma = 1.0 if (_angle_of(c, keep_arc) - theta) % TWO_PI <= math.pi else -1.0
        if d_start <= 1e-7:
            sigma = 1.0  # the arc leaves its start anticlockwise
        elif d_end <= 1e-7:
            sigma = -1.0
    elif d_start <= 1e-7:
        sigma = 1.0
    elif d_end <= 1e-7:
        sigma = -1.0
    else:
        far = start if d_start >= d_end else end
        sigma = 1.0 if (_angle_of(c, far) - theta) % TWO_PI <= math.pi else -1.0
    far = end if sigma > 0 else start
    reach2 = ((_angle_of(c, far) - theta) * sigma) % TWO_PI
    if reach2 <= 1e-9:
        reach2 = TWO_PI
    u2 = (-math.sin(theta) * sigma, math.cos(theta) * sigma)
    if reach1 <= EPS:
        raise ChamferError("Click the line on the side that stays.")
    angle = math.acos(max(-1.0, min(1.0, _dot(u1, u2))))
    if angle <= 1e-6 or angle >= math.pi - 1e-6:
        raise ChamferError("The line and the arc run on smoothly there: there is no corner.")
    return {
        "point": point,
        "u1": u1,
        "reach1": reach1,
        "u2": u2,
        "sigma": sigma,
        "theta": theta,
        "reach2": reach2,
        "angle": angle,
        "centre": c,
        "radius": r,
    }


def arc_point(data, chord):
    """The point on the arc `chord` (straight distance) from the corner, along the part
    that stays."""
    r = data["radius"]
    if chord is None or chord <= EPS:
        raise ChamferError("The distance must be more than 0.")
    if chord >= 2 * r - 1e-9:
        raise ChamferError("The distance on the arc is more than the arc's diameter.")
    turn = 2.0 * math.asin(chord / (2.0 * r))
    if turn >= data["reach2"] - 1e-9:
        raise ChamferError("The chamfer is longer than the arc: make it smaller.")
    t = data["theta"] + data["sigma"] * turn
    c = data["centre"]
    return (c[0] + r * math.cos(t), c[1] + r * math.sin(t))


def line_point(data, distance):
    if distance is None or distance <= EPS:
        raise ChamferError("The distance must be more than 0.")
    if distance >= data["reach1"] - 1e-7:
        raise ChamferError("The chamfer is longer than the line: make it smaller.")
    return _add(data["point"], _scale(data["u1"], distance))


def angle_at_line(data, p1, p2):
    """The angle at P1 between the line (towards the corner) and the chamfer."""
    to_corner = _sub(data["point"], p1)
    to_p2 = _sub(p2, p1)
    cosine = _dot(to_corner, to_p2) / (_length(to_corner) * _length(to_p2))
    return math.acos(max(-1.0, min(1.0, cosine)))


def arc_point_at_angle(data, p1, alpha):
    """Distance and angle: where the chamfer leaving P1 at `alpha` from the line (towards
    the corner, turned into the corner) meets the arc; (point, chord from the corner)."""
    if alpha is None or alpha <= 1e-6 or alpha >= math.pi - 1e-6:
        raise ChamferError("The angle must be between 0 and 180 degrees.")
    to_corner = _unit(_sub(data["point"], p1))
    # turn towards the arc's side: the side u2 points to, seen along the line
    side = 1.0 if _cross(to_corner, data["u2"]) >= 0 else -1.0
    ca, sa = math.cos(alpha), math.sin(alpha) * side
    d = (to_corner[0] * ca - to_corner[1] * sa, to_corner[0] * sa + to_corner[1] * ca)
    hits = _line_circle(p1, _add(p1, d), data["centre"], data["radius"])
    ahead = [q for q in hits if _dot(_sub(q, p1), d) > 1e-9]
    if not ahead:
        raise ChamferError("At that angle the chamfer misses the arc: change the angle.")
    best = min(ahead, key=lambda q: _length(_sub(q, data["point"])))
    chord = _length(_sub(best, data["point"]))
    return arc_point(data, chord), chord


def line_arc_values(kind, data, distance, second=None, line_first=True):
    """(setback on the line, chord on the arc, P1, P2) for the type and values.
    two_distances: `distance` belongs to the curve picked first (line_first)."""
    if kind not in KINDS:
        raise ChamferError("Unknown chamfer type %r." % kind)
    if kind == "distance_angle":
        p1 = line_point(data, distance)
        alpha = second
        if alpha is None:
            alpha = angle_at_line(data, p1, arc_point(data, distance))
        p2, chord = arc_point_at_angle(data, p1, alpha)
        return distance, chord, p1, p2
    if kind == "equal":
        s_line = s_arc = distance
    else:
        if second is None or second <= EPS:
            raise ChamferError("The second distance must be more than 0.")
        s_line, s_arc = (distance, second) if line_first else (second, distance)
    return s_line, s_arc, line_point(data, s_line), arc_point(data, s_arc)


def line_arc_pointer(kind, data, pointer, line_first=True):
    """What the pointer gives: its distance from the corner (Equal distance, and the arc's
    distance of Two distances); the line's distance is along the line."""
    rel = _sub(pointer, data["point"])
    along = max(_dot(rel, data["u1"]), 0.0)
    away = _length(rel)
    if kind == "equal":
        return {"distance": away}
    if kind == "two_distances":
        if line_first:
            return {"distance": along, "distance2": away}
        return {"distance": away, "distance2": along}
    return {"distance": along}
