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
