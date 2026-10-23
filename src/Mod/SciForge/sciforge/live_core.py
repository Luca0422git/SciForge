# SPDX-License-Identifier: LGPL-2.1-or-later
"""The arithmetic of the live pictures of Shell, Press Pull / Offset Face and Extrude
(live_shapes.py), without FreeCAD: unit tested in SciForgeTests/unit/test_live_core.py.

While a handle of these dialogs is dragged, the dialog shows the faces that move as a
picture that follows every mouse move, and builds the exact solid only when the mouse rests
or is let go (as Draft does since 2026-10-22: draft_live.py). Each point of a picture moves
along a straight line as the value changes:

    point(value) = start + a(value) * A + b(value) * B

A and B are worked out once per set of picks (here), a and b per value (a few numbers per
group of points), so a mouse move costs a fraction of a millisecond.

Offsets (Press Pull, Offset Face, Shell): a point of a face that moves by `d` along its
normal must end `d` away from where the face was, and stay on every face beside it that does
not move (a box's top pulled up: its corner slides up the two sides it touches; Shell: a wall
point at the rim stays on the opened face's plane). With rows (n_i, r_i) - the outward
normal of each face the point lies on and how far that face moves per unit of the value
(1 for a moved face, 0 for one that stays) - the move per unit value is the shortest vector
w with w . n_i = r_i for every row (offset_move). Two pulled faces that share an edge then
meet in a sharp corner (w . n1 = w . n2 = 1), what Press Pull and a sharp Shell make; faces
that continue each other smoothly count once.

Extrude: the profile's triangles at the start and at the end of each side, and quads along
its outline between them; a taper moves the outline inward square to it in the profile's
plane by L * tan(taper) (in_plane_move: the shortest in-plane vector w with w . m_i = 1 for
the outline's in-plane outward normals m_i at the point: a corner moves along its bisector).
"""

import math

EPS = 1e-12


# -- vectors (tuples) ------------------------------------------------------------------------
def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def scale(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def norm(a):
    return math.sqrt(dot(a, a))


def unit(a):
    n = norm(a)
    if n < EPS:
        return (0.0, 0.0, 0.0)
    return scale(a, 1.0 / n)


# -- offsets ---------------------------------------------------------------------------------
def _independent(rows, parallel):
    """The rows with (nearly) parallel normals merged: a moved face wins over one that
    stays (a face tangent to the moved one: the moved one decides), else the first."""
    kept = []
    for n, r in rows:
        n = unit(n)
        if dot(n, n) < 0.5:
            continue
        for i, (m, s) in enumerate(kept):
            c = dot(m, n)
            if abs(abs(c) - 1.0) < parallel:
                sign = 1.0 if c > 0 else -1.0
                if abs(s) < EPS and abs(r) > EPS:
                    kept[i] = (n, r)  # the moved face decides
                elif abs(r) > EPS and abs(s) > EPS and abs(s - sign * r) > EPS:
                    kept[i] = (m, 0.5 * (s + sign * r))  # two moves: their middle
                break
        else:
            kept.append((n, r))
    return kept


def _solve(matrix, rhs):
    """Gaussian elimination with pivoting; None when singular."""
    n = len(rhs)
    a = [list(row) + [rhs[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[piv][col]) < 1e-12:
            return None
        a[col], a[piv] = a[piv], a[col]
        for r in range(n):
            if r != col:
                f = a[r][col] / a[col][col]
                if f:
                    for c in range(col, n + 1):
                        a[r][c] -= f * a[col][c]
    return [a[i][n] / a[i][i] for i in range(n)]


def offset_move(rows, parallel=1e-4):
    """The shortest vector w with w . n_i = r_i for every row (n_i, r_i) (see the module
    text); rows that cannot all hold (more than three directions, or three in one plane that
    disagree) keep the moved faces' rows first. (0, 0, 0) when no row moves."""
    kept = _independent(rows, parallel)
    if not any(abs(r) > EPS for _n, r in kept):
        return (0.0, 0.0, 0.0)
    # moved faces first, then the ones that stay; add rows while they stay independent
    kept.sort(key=lambda row: 0 if abs(row[1]) > EPS else 1)
    chosen = []
    for row in kept:
        trial = chosen + [row]
        if len(trial) > 3:
            break
        gram = [[dot(a[0], b[0]) for b in trial] for a in trial]
        if _solve(gram, [0.0] * len(trial)) is None and len(trial) > 1:
            continue  # dependent on the rows chosen (three normals in one plane)
        chosen = trial
    gram = [[dot(a[0], b[0]) for b in chosen] for a in chosen]
    coef = _solve(gram, [r for _n, r in chosen])
    if coef is None:
        return (0.0, 0.0, 0.0)
    w = (0.0, 0.0, 0.0)
    for c, (n, _r) in zip(coef, chosen):
        w = add(w, scale(n, c))
    return w


def in_plane_move(normals, plane_normal, parallel=1e-4):
    """The shortest vector w in the plane square to `plane_normal` with w . m_i = 1 for every
    in-plane outward normal m_i of the outline at a point (a straight piece: m itself; a
    corner: along its bisector, so both sides move by 1)."""
    pn = unit(plane_normal)
    rows = []
    for m in normals:
        m = sub(m, scale(pn, dot(m, pn)))
        if norm(m) < 1e-9:
            continue
        rows.append((m, 1.0))
    rows.append((pn, 0.0))
    return offset_move(rows, parallel)


# -- extrude sides -----------------------------------------------------------------------------
def extrude_ends(direction, distance, distance2=0.0, measurement="whole", start=0.0, two=False):
    """[(position along the extrude direction, length from the start)] of the two ends of an
    extrusion (the first one the start side), as Extrude builds them with distances:
    One Side: start .. start + distance; Symmetric: start - L .. start + L (L = distance, or
    half of it when the whole length is given); Two Sides: start - distance2 .. start +
    distance (each with its own length, for the taper)."""
    d = float(distance)
    if direction == "symmetric":
        half = abs(d) / 2.0 if measurement == "whole" else abs(d)
        return [(start - half, half), (start + half, half)]
    if direction == "two_sides" or two:
        d2 = float(distance2)
        return [(start - d2, abs(d2)), (start + d, abs(d))]
    return [(start, 0.0), (start + d, abs(d))]


def taper_inset(length, taper_deg):
    """How far the outline moves inward at the end of a side of this length with this taper
    (positive taper: the extrusion gets narrower away from the profile)."""
    return float(length) * math.tan(math.radians(float(taper_deg)))


# -- quads -------------------------------------------------------------------------------------
def strip(count, first_a, first_b):
    """Triangles of the quads between two rows of `count` points that follow each other
    (row a starts at index first_a, row b at first_b)."""
    tris = []
    for k in range(count - 1):
        a0, a1 = first_a + k, first_a + k + 1
        b0, b1 = first_b + k, first_b + k + 1
        tris.append((a0, a1, b1))
        tris.append((a0, b1, b0))
    return tris


def point_segment_distance(p, a, b):
    """Distance from p to the segment a-b."""
    ab = sub(b, a)
    len2 = dot(ab, ab)
    if len2 < EPS:
        return norm(sub(p, a))
    t = max(0.0, min(1.0, dot(sub(p, a), ab) / len2))
    return norm(sub(p, add(a, scale(ab, t))))


def near_polyline(p, line, tol):
    """True when p lies within `tol` of the polyline (a list of points)."""
    for a, b in zip(line, line[1:]):
        lo = [min(a[i], b[i]) - tol for i in range(3)]
        hi = [max(a[i], b[i]) + tol for i in range(3)]
        if any(p[i] < lo[i] or p[i] > hi[i] for i in range(3)):
            continue
        if point_segment_distance(p, a, b) <= tol:
            return True
    return False
