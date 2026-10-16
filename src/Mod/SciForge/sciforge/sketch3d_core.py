# SPDX-License-Identifier: LGPL-2.1-or-later
"""The maths of Fusion's 3D Sketch (no FreeCAD, no Qt: unit tested).

Fusion (Autodesk help "Create a 3D sketch"; Autodesk tech tip "Allow 3D sketching of lines
and splines"; Fusion forum): with 3D Sketch checked in the Sketch Palette, lines and
splines can have points off the sketch plane. A manipulator (three small planes and the
axes) shows where the next point is drawn: on the active plane through the last point
placed (the sketch's own plane to begin with); a click on one of its planes makes that
plane the active one. A point placed on geometry of the design (a corner of a body)
lands there. A point already drawn can be moved in 3D with the arrows of a triad.

Coordinates are the sketch's own (x, y on its plane, z along its normal): planes
"XY" (the sketch plane), "YZ" and "ZX". Points are (x, y, z) tuples.
"""

import math

PLANES = ("XY", "YZ", "ZX")
NORMALS = {"XY": (0.0, 0.0, 1.0), "YZ": (1.0, 0.0, 0.0), "ZX": (0.0, 1.0, 0.0)}
# the two in-plane axes of each plane (for the grid and the manipulator's squares)
AXES = {
    "XY": ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    "YZ": ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    "ZX": ((0.0, 0.0, 1.0), (1.0, 0.0, 0.0)),
}
AXIS_DIRECTIONS = {"X": (1.0, 0.0, 0.0), "Y": (0.0, 1.0, 0.0), "Z": (0.0, 0.0, 1.0)}
EPS = 1e-12


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def length(a):
    return math.sqrt(dot(a, a))


def ray_plane(origin, direction, point, plane):
    """Where the ray (origin, direction) meets the plane `plane` through `point`, or None
    when the ray runs along it."""
    n = NORMALS[plane]
    den = dot(direction, n)
    if abs(den) <= 1e-9:
        return None
    t = dot(sub(point, origin), n) / den
    return add(origin, mul(direction, t))


def grid_snap(point, anchor, plane, grid):
    """The point's in-plane coordinates moved onto the grid lines (the grid runs through
    the sketch origin, as the sketch's own grid) when within a fifth of the spacing, as
    FreeCAD's sketch snaps (sketch_infer_core.grid_snap); the plane's offset is kept."""
    if not grid or grid <= 0:
        return point
    out = point
    for axis in AXES[plane]:
        value = dot(point, axis)
        nearest = round(value / grid) * grid
        if abs(value - nearest) < grid / 5.0:
            out = add(out, mul(axis, nearest - value))
    return out


def closest_on_axis(ray_origin, ray_dir, axis_point, axis_dir):
    """How far along the axis (from axis_point, in units of axis_dir) the point of the
    axis nearest to the ray lies (the drag of a triad arrow), or None when they run
    side by side."""
    w0 = sub(axis_point, ray_origin)
    a = dot(axis_dir, axis_dir)
    b = dot(axis_dir, ray_dir)
    c = dot(ray_dir, ray_dir)
    d = dot(axis_dir, w0)
    e = dot(ray_dir, w0)
    den = a * c - b * b
    if abs(den) <= 1e-12 * max(1.0, a * c):
        return None
    return (b * e - c * d) / den


def squares(anchor, size):
    """{plane: four corners} of the manipulator's small plane squares at the anchor: each
    in its plane's first quadrant, from a fifth of `size` to `size`."""
    out = {}
    lo, hi = size * 0.2, size
    for plane in PLANES:
        u, v = AXES[plane]
        out[plane] = [
            add(anchor, add(mul(u, a), mul(v, b)))
            for a, b in ((lo, lo), (hi, lo), (hi, hi), (lo, hi))
        ]
    return out


def point_in_polygon(x, y, poly):
    """Even-odd test of a screen point in a polygon [(x, y)]."""
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            cross = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < cross:
                inside = not inside
    return inside


def segment_distance(p, a, b):
    """Screen distance from p to the segment a-b ((x, y) tuples)."""
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    den = dx * dx + dy * dy
    if den <= EPS:
        return math.hypot(p[0] - ax, p[1] - ay)
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / den))
    return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))


def next_plane(plane):
    """The plane after `plane` (a key cycles them)."""
    return PLANES[(PLANES.index(plane) + 1) % len(PLANES)]


def on_sketch_plane(points, tol=1e-9):
    """True when every point lies on the sketch's own plane (z = 0)."""
    return all(abs(p[2]) <= tol for p in points)


# -- the stored curves ---------------------------------------------------------------------
def pairs(flat):
    """[(a, b)] from a flat list [a0, b0, a1, b1, ...] (the stored lines)."""
    return [(flat[i], flat[i + 1]) for i in range(0, len(flat) - 1, 2)]


def parse_spline(text):
    """[indices] of a stored spline ("0,3,4")."""
    return [int(p) for p in text.split(",") if p.strip() != ""]


def join_index(points, point, tol=1e-9):
    """The index of a stored point at `point`, or None (a new line starting where another
    ends shares its point, so moving it moves both)."""
    for i, q in enumerate(points):
        if length(sub(q, point)) <= tol:
            return i
    return None
