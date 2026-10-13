# SPDX-License-Identifier: LGPL-2.1-or-later
"""Align's maths (Fusion's Modify > Align): pure Python, no FreeCAD, unit tested.

A frame is what a pick means: {"point": (x, y, z), "axis": (x, y, z) or None,
"oriented": bool}. A flat face gives its centre and its outward normal (oriented); a round
edge its centre and the normal of the flat face it bounds (oriented) or its own axis; a
straight edge a point on it and its direction (not oriented: an edge has no "outside"); a
corner or a ball only a point.

movement(from, to, flip, turns) is the move that puts the From frame onto the To frame:
  * both have an axis: the From axis is turned onto the To axis; two oriented axes (faces)
    end up facing each other, like a part put down on a table (Fusion: the faces end up
    aligned); unoriented ones take the smaller turn. Flip turns the result 180 degrees.
  * Angle turns the result 90 degrees about the To axis per click (Fusion's Angle button).
  * then the From point is moved onto the To point.
Rotations are quaternions (x, y, z, w); a point p moves to R(p) + T.
"""

import math

EPS = 1e-12


def _v(a):
    return (float(a[0]), float(a[1]), float(a[2]))


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def scale(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def length(a):
    return math.sqrt(dot(a, a))


def unit(a):
    n = length(a)
    if n < EPS:
        raise ValueError("a direction of no length")
    return scale(a, 1.0 / n)


IDENTITY = (0.0, 0.0, 0.0, 1.0)


def axis_angle(axis, degrees):
    """Quaternion for a right-handed turn about ``axis``."""
    x, y, z = unit(axis)
    half = math.radians(degrees) / 2.0
    s = math.sin(half)
    return (x * s, y * s, z * s, math.cos(half))


def multiply(q, r):
    """q * r: first r, then q."""
    x1, y1, z1, w1 = q
    x2, y2, z2, w2 = r
    return (
        w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
        w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
        w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
        w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
    )


def rotate(q, v):
    """The vector ``v`` turned by the quaternion ``q``."""
    x, y, z, w = q
    qv = (x, y, z)
    t = scale(cross(qv, v), 2.0)
    return add(add(v, scale(t, w)), cross(qv, t))


def perpendicular(a):
    """Some unit vector at right angles to ``a``."""
    a = unit(a)
    other = (1.0, 0.0, 0.0) if abs(a[0]) < 0.9 else (0.0, 1.0, 0.0)
    return unit(cross(a, other))


def between(a, b):
    """The smallest turn that takes direction ``a`` onto direction ``b``."""
    a, b = unit(a), unit(b)
    c = dot(a, b)
    if c > 1.0 - 1e-12:
        return IDENTITY
    if c < -1.0 + 1e-12:
        return axis_angle(perpendicular(a), 180.0)
    axis = cross(a, b)
    return axis_angle(axis, math.degrees(math.acos(max(-1.0, min(1.0, c)))))


def frame(point, axis=None, oriented=False):
    return {
        "point": _v(point),
        "axis": _v(unit(axis)) if axis is not None else None,
        "oriented": bool(oriented) and axis is not None,
    }


def movement(src, dst, flip=False, turns=0):
    """(quaternion, translation) moving frame ``src`` onto frame ``dst`` (see the module
    text). ``turns``: quarter turns about the To axis (Fusion's Angle button)."""
    p1, a1 = _v(src["point"]), src.get("axis")
    p2, a2 = _v(dst["point"]), dst.get("axis")
    rotation = IDENTITY
    if a1 is not None and a2 is not None:
        a1, a2 = unit(a1), unit(a2)
        if src.get("oriented") and dst.get("oriented"):
            wanted = scale(a2, -1.0)  # the faces face each other
        else:
            wanted = a2 if dot(a1, a2) >= 0.0 else scale(a2, -1.0)
        if flip:
            wanted = scale(wanted, -1.0)
        rotation = between(a1, wanted)
    elif flip:
        turn_about = perpendicular(a2 if a2 is not None else (a1 if a1 is not None else (0, 0, 1)))
        rotation = axis_angle(turn_about, 180.0)
    turn_axis = a2 if a2 is not None else a1
    if turns % 4 and turn_axis is not None:
        rotation = multiply(axis_angle(turn_axis, 90.0 * (turns % 4)), rotation)
    translation = sub(p2, rotate(rotation, p1))
    return rotation, translation


def apply(rotation, translation, point):
    return add(rotate(rotation, _v(point)), translation)


def describe(flip, turns):
    """What the Flip / Angle buttons did, for the dialog."""
    parts = []
    if flip:
        parts.append("flipped")
    if turns % 4:
        parts.append("turned %d degrees" % (90 * (turns % 4)))
    return ", ".join(parts) if parts else ""
