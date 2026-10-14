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
    """The chamfer must leave something of each line."""
    if s1 >= reach1 - 1e-7:
        raise ChamferError("The chamfer is longer than the first line: make it smaller.")
    if s2 >= reach2 - 1e-7:
        raise ChamferError("The chamfer is longer than the second line: make it smaller.")


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
