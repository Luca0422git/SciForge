# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pure 2D maths of the flat pattern (no FreeCAD, no Qt; unit tested).

Corner reliefs: where two bends meet at a corner (a tray's corner, two flanges on adjacent
edges), Fusion puts the rule's 2-bend corner relief on the flat pattern, centred where the
two bend centre lines cross (research 4.6, A[R1]: "Intersection"). corner_points() finds
those crossings from the flat's bend centre lines.
"""

import math

RELIEF_SHAPES = ("round", "square")  # the 2-bend shapes that are a hole in the flat


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def _len(v):
    return math.hypot(v[0], v[1])


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def line_crossing(a1, a2, b1, b2):
    """Where the lines through a1-a2 and b1-b2 cross, or None when they are parallel."""
    da = _sub(a2, a1)
    db = _sub(b2, b1)
    den = _cross(da, db)
    if abs(den) < 1e-9 * max(1.0, _len(da) * _len(db)):
        return None
    t = _cross(_sub(b1, a1), db) / den
    return (a1[0] + da[0] * t, a1[1] + da[1] * t)


def _near_end(point, p1, p2, reach):
    """point lies on or beyond the segment's ends (not in its middle), within reach of one."""
    d = min(_len(_sub(point, p1)), _len(_sub(point, p2)))
    return d <= reach


def corner_points(bends, reach):
    """[(x, y, i, j)]: the crossings of the centre lines of bends i and j that meet at a
    corner (the crossing within `reach` of an end of both lines, the lines not parallel).
    bends: dicts with "centre" [(x, y), (x, y)]."""
    found = []
    for i in range(len(bends)):
        for j in range(i + 1, len(bends)):
            a1, a2 = [tuple(p) for p in bends[i]["centre"]]
            b1, b2 = [tuple(p) for p in bends[j]["centre"]]
            da, db = _sub(a2, a1), _sub(b2, b1)
            if _len(da) < 1e-9 or _len(db) < 1e-9:
                continue
            sin = abs(_cross(da, db)) / (_len(da) * _len(db))
            if sin < 0.1:
                continue  # (nearly) parallel bends never meet at a corner
            x = line_crossing(a1, a2, b1, b2)
            if x is None:
                continue
            if _near_end(x, a1, a2, reach) and _near_end(x, b1, b2, reach):
                found.append((x[0], x[1], i, j))
    return found


def relief_size(rule):
    """(shape, size) of the rule's 2-bend corner relief when it is a hole in the flat, else
    (shape, 0). Size: the round relief's diameter, the square's side (sm-forming's choice)."""
    shape = rule.get("corner_relief_2bend_shape", "round")
    size = float(rule.get("corner_relief_2bend_size", 0.0) or 0.0)
    if shape not in RELIEF_SHAPES or size <= 0:
        return shape, 0.0
    return shape, size


def _unit(v):
    n = _len(v)
    return (v[0] / n, v[1] / n) if n > 1e-12 else (0.0, 0.0)


def bend_frame(bend):
    """(point, direction, outward, half) of a flat bend (a dict with "start", "centre", "end"
    lines): a point on its centre line, the line's direction, the unit vector across the bend
    from its start (the side nearer the stationary face) toward its end, and half the bend
    zone's width."""
    a, b = [tuple(p[:2]) for p in bend["centre"]]
    s0 = tuple(bend["start"][0][:2])
    e0 = tuple(bend["end"][0][:2])
    d = _unit(_sub(b, a))
    w = _sub(e0, s0)
    along = w[0] * d[0] + w[1] * d[1]
    across = (w[0] - d[0] * along, w[1] - d[1] * along)
    return a, d, _unit(across), _len(across) / 2.0


def relief_centre(placement, bend_a, bend_b, size):
    """Where a 2-bend corner relief is centred on the flat (bends as bend_frame gives them),
    or None when the bends are parallel:

    * intersection: where the two bend centre lines cross;
    * tangent: moved toward the flanges so the relief (diameter or side `size`) reaches the
      far side of both bend zones and clears their whole crossing (sm-more's Corner Closure
      places its Tangent relief the same way);
    * vertex: where both bends start (the inner corner)."""
    offsets = []
    for _p, _d, _o, half in (bend_a, bend_b):
        if placement == "tangent":
            offsets.append(half - size / 2.0)
        elif placement == "vertex":
            offsets.append(-half)
        else:
            offsets.append(0.0)
    lines = []
    for (p, d, o, _half), off in zip((bend_a, bend_b), offsets):
        q = (p[0] + o[0] * off, p[1] + o[1] * off)
        lines.append((q, (q[0] + d[0], q[1] + d[1])))
    return line_crossing(lines[0][0], lines[0][1], lines[1][0], lines[1][1])


def nearest(point, items, reach):
    """The index of the item (x, y, z) nearest to point within reach, else None."""
    best = None
    for i, q in enumerate(items):
        d = math.sqrt(sum((point[k] - q[k]) ** 2 for k in range(3)))
        if d <= reach and (best is None or d < best[0]):
            best = (d, i)
    return None if best is None else best[1]


def axes_meet(p, u, q, v):
    """The midpoint of the closest points of the 3D lines p + t u and q + s v (the corner
    where two bends' axes meet), or None when they are parallel."""

    def dot(a, b):
        return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

    w = [p[k] - q[k] for k in range(3)]
    a, b, c = dot(u, u), dot(u, v), dot(v, v)
    d, e = dot(u, w), dot(v, w)
    den = a * c - b * b
    if abs(den) < 1e-12 * max(1.0, a * c):
        return None
    t = (b * e - c * d) / den
    s = (a * e - b * d) / den
    return tuple((p[k] + u[k] * t + q[k] + v[k] * s) / 2.0 for k in range(3))
