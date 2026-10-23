# SPDX-License-Identifier: LGPL-2.1-or-later
"""The arithmetic of Draft's live picture (draft_live.py), without FreeCAD: unit tested in
SciForgeTests/unit/test_draft_live_core.py.

While the angle handle is dragged, the dialog shows the drafted faces moving with the mouse
and builds the exact solid only when the mouse rests (Luca, 2026-10-22: "The whole point of
being able to drag the angle of a draft is to see it update in real time"). The picture is
the picked faces' own triangles, each point moved square to the pull direction:

  A drafted face turns about its hinge (where it meets the fixed plane or the parting line)
  until it leans by the draft angle: OpenCASCADE sets the angle absolutely (a face that
  leans by b already ends at the angle a, not a + b). At the height h above the hinge
  (along the pull direction) a point then moves out of the face by
      shift = -h * (tan(a) - tan(b))                  (negative: into the part)
  along the face's outward normal laid flat (square to the pull direction). The tops and
  bottoms of the walls stay at their heights (a cap square to the pull direction keeps
  its plane), so the point keeps its height.

  Where a drafted face meets another side face (a corner of a box, a rounded corner), the
  point must stay on both: the drafted face moves by its shift, the other one by its own
  (0 when it is not drafted). solve() works out, once per point, how the shifts of the
  faces it lies on move it (two faces at an angle: where both moved planes meet; tangent
  faces: one shift; one face: straight out).

  A wall that ends on a slanted face that is not drafted (a wedge's sloping top, a curved
  top) cannot keep its points at their heights there: the point moves along the turned wall
  (and the faces beside it) until it is back on the slanted face (slide(); review finding
  DRAFT-1-F3: the outline moved half as far as its face, both off the exact solid).

  Two Side / Symmetric (and a Parting Line's One Side) split the faces at the hinge: the
  side away from the pull direction turns the other way (Angle 2, or no turn for One Side).
  The picture's triangles that cross the hinge are split there (split_triangles), so the
  bend sits exactly on it.
"""

import math

EPS = 1e-9


# -- the shifts ------------------------------------------------------------------------------
def lean_tan(normal, pull):
    """tan(b) of a face's lean at a point from its outward normal: positive when the face
    leans in toward the pull direction (the part gets narrower that way, as a positive draft
    makes it); 0 for a wall along the pull direction."""
    up = dot(normal, pull)
    flat = math.sqrt(max(0.0, dot(normal, normal) - up * up))
    if flat < 1e-12:
        return 0.0
    return up / flat


def k_factor(angle, tb, sides="one", kind="fixed", below=False, angle2=None):
    """K with shift = -h * K for a point of a drafted face at height h (below: h < 0, the side
    away from the pull direction). `angle`, `angle2` in degrees; tb: lean_tan of the face."""
    if not below or (sides == "one" and kind == "fixed"):
        return math.tan(math.radians(angle)) - tb
    if sides == "one":
        return 0.0  # Parting Line, One Side: only the pull side is drafted
    other = angle if sides == "symmetric" or angle2 is None else angle2
    # the far side is drafted toward -pull: its height -h, its lean -tb
    return -(math.tan(math.radians(other)) + tb)


def splits(sides, kind):
    """True when the picture bends at the hinge (its triangles are split there)."""
    return not (sides == "one" and kind == "fixed")


# -- vectors (tuples) ------------------------------------------------------------------------------
def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def scale(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def unit(a):
    n = math.sqrt(dot(a, a))
    return scale(a, 1.0 / n) if n > 1e-15 else (0.0, 0.0, 0.0)


def flat(v, pull):
    """`v` laid square to the pull direction (unit; zero when it runs along it)."""
    return unit(sub(v, scale(pull, dot(v, pull))))


def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


# -- a point on several faces ----------------------------------------------------------------------
def solve(normals, pull, parallel=1e-3):
    """Weights w_i (3D vectors square to `pull`) with the point's move d = sum(w_i * s_i), s_i
    the shift of the i-th face the point lies on (its outward normal flat, `normals`): d
    moves the point by s_i out of every face i. Faces whose normals are (nearly) parallel
    count as one (tangent faces: their weights are shared); two faces at an angle: exact;
    more: least squares. Returns a list as long as `normals`."""
    n = [flat(v, pull) for v in normals]
    groups = []  # [(normal, [indices])]
    for i, v in enumerate(n):
        if dot(v, v) < 0.5:
            continue  # a face square to the pull direction (a cap): no constraint across it
        for g in groups:
            if abs(abs(dot(g[0], v)) - 1.0) < parallel:
                g[1].append((i, 1.0 if dot(g[0], v) > 0 else -1.0))
                break
        else:
            groups.append((v, [(i, 1.0)]))
    weights = [(0.0, 0.0, 0.0)] * len(normals)
    if not groups:
        return weights
    if len(groups) == 1:
        v, members = groups[0]
        for i, sign in members:
            weights[i] = scale(v, sign / len(members))
        return weights
    # several directions: least squares in the plane square to `pull` (exact for two)
    e1 = groups[0][0]
    e2 = unit(cross(pull, e1))
    rows = [((dot(g[0], e1), dot(g[0], e2)), g[1]) for g in groups]
    a11 = sum(r[0][0] * r[0][0] for r in rows)
    a12 = sum(r[0][0] * r[0][1] for r in rows)
    a22 = sum(r[0][1] * r[0][1] for r in rows)
    det = a11 * a22 - a12 * a12
    if abs(det) < 1e-12:
        for i, sign in groups[0][1]:
            weights[i] = scale(groups[0][0], sign / len(groups[0][1]))
        return weights
    # d = (A^-1) * sum(row_g * s_g), s_g the mean shift of the group
    inv = ((a22 / det, -a12 / det), (-a12 / det, a11 / det))
    for (gx, gy), members in rows:
        cx = inv[0][0] * gx + inv[0][1] * gy
        cy = inv[1][0] * gx + inv[1][1] * gy
        w = add(scale(e1, cx), scale(e2, cy))
        for i, sign in members:
            weights[i] = scale(w, sign / len(members))
    return weights


# -- a point on a slanted face that stays ------------------------------------------------------
def slanted_cap(normal, pull, drafted_flats, parallel=0.9):
    """True when a face that is not drafted, with outward `normal` at the point, is a slanted
    cap for it: neither upright nor square to the pull direction, and facing (nearly) the same
    way as a drafted face the point lies on (`drafted_flats`: their normals laid flat). Moving
    square to the pull direction cannot keep the point on both (solve() would share the shift
    between them); slide() keeps it on the cap instead."""
    n = unit(normal)
    up = abs(dot(n, pull))
    if up < 1e-3 or up > 1.0 - 1e-9:
        return False
    f = flat(n, pull)
    return any(abs(dot(f, d)) > parallel for d in drafted_flats)


def turned_row(flat_normal, ta, pull):
    """The normal (not unit) of a drafted face turned to lean by atan(ta): a point moved by d
    stays on it when dot(row, d) is the face's shift (flat_normal: its outward normal laid
    flat, unit)."""
    return add(flat_normal, scale(pull, ta))


def slide(move, cap, rows, pull):
    """`move` (the point's move square to the pull direction, on the moved faces) slid along
    the faces of `rows` (the normals of the faces the point stays on, as moved: turned_row()
    for a drafted face) until the point is back on the slanted face with normal `cap` (which
    passes through the point before the move). Along two faces at an angle: their common
    line; along one: its steepest line."""
    picked = []
    for r in rows:
        u = unit(r)
        if dot(u, u) < 0.5:
            continue
        if picked and math.sqrt(max(0.0, dot(cross(picked[0], u), cross(picked[0], u)))) < 0.05:
            continue  # (nearly) the same plane as the first (tangent faces)
        picked.append(u)
        if len(picked) == 2:
            break
    if len(picked) == 2:
        along = cross(picked[0], picked[1])
    elif picked:
        r = picked[0]
        along = sub(pull, scale(r, dot(r, pull)))
    else:
        along = pull
    den = dot(cap, along)
    if abs(den) < 1e-9:
        return move
    return add(move, scale(along, -dot(cap, move) / den))


# -- bending at the hinge ------------------------------------------------------------------------
def split_triangles(heights, triangles, eps=1e-9):
    """Triangles that cross height 0 cut there. Returns (new points, triangles): each new point
    is (i, j, t), the point t of the way from point i to point j; new points are numbered
    after the old ones (len(heights) + k)."""
    count = len(heights)
    made = []
    found = {}
    out = []

    def cut(i, j):
        key = (min(i, j), max(i, j))
        if key not in found:
            a, b = heights[key[0]], heights[key[1]]
            t = a / (a - b)
            found[key] = count + len(made)
            made.append((key[0], key[1], t))
        return found[key]

    for tri in triangles:
        hs = [heights[k] for k in tri]
        if min(hs) >= -eps or max(hs) <= eps:
            out.append(tuple(tri))
            continue
        polys = ([], [])  # above, below
        for k in range(3):
            i, j = tri[k], tri[(k + 1) % 3]
            hi, hj = heights[i], heights[j]
            side = 0 if hi >= 0 else 1
            polys[side].append(i)
            if (hi > eps and hj < -eps) or (hi < -eps and hj > eps):
                m = cut(i, j)
                polys[0].append(m)
                polys[1].append(m)
            elif abs(hi) <= eps:
                polys[1 - side].append(i)  # on the hinge: a corner of both pieces
        for poly in polys:
            for k in range(1, len(poly) - 1):
                tri2 = (poly[0], poly[k], poly[k + 1])
                if len(set(tri2)) == 3:
                    out.append(tri2)
    return made, out


def split_line(heights, eps=1e-9):
    """A polyline's points with height 0 crossings put in: a list of (i, j, t) (t = 0: point i
    itself)."""
    out = []
    for k, h in enumerate(heights):
        if k:
            a = heights[k - 1]
            if (a > eps and h < -eps) or (a < -eps and h > eps):
                out.append((k - 1, k, a / (a - h)))
        out.append((k, k, 0.0))
    return out
