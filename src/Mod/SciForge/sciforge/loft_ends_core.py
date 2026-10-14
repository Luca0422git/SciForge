# SPDX-License-Identifier: LGPL-2.1-or-later
"""Loft end conditions: the math (no FreeCAD, no Qt), unit tested.

Fusion's Loft lets the first and the last profile set how the loft leaves / meets it:
  sketch profile    Connected (free) | Direction (Takeoff Weight, Takeoff Angle)
  face of a body    Connected (G0)   | Tangent (G1) | Curvature (G2) (Tangency Weight)
  point             Sharp            | Point Tangent (a dome; Tangency Weight)

SciForge builds such a loft from OpenCASCADE's loft (sloft.py): every side face is a
B-spline surface whose rows of control points across the profiles are re-interpolated here,
one cubic B-spline per column, with the end derivatives the condition asks for. Every column
is interpolated with the same parameters and the same kind of end conditions, so one matrix
serves them all (`interpolate` solves it once for every column).

End conditions for `interpolate` (one per end), values are flat rows (one number per column):
  ("free",)               the second derivative is 0 there (a natural end)
  ("d1", d1)              the first derivative is d1
  ("d2", d1, d2)          the first and the second derivative are given
"""

import math

DEGREE = 3

CONDITIONS = ("free", "direction", "tangent", "curvature", "point_tangent")
SKETCH_CONDITIONS = ("free", "direction")
FACE_CONDITIONS = ("free", "tangent", "curvature")
POINT_CONDITIONS = ("free", "point_tangent")
LABELS = {
    "sketch": [("Connected", "free"), ("Direction", "direction")],
    "face": [
        ("Connected (G0)", "free"),
        ("Tangent (G1)", "tangent"),
        ("Curvature (G2)", "curvature"),
    ],
    "point": [("Sharp", "free"), ("Point Tangent", "point_tangent")],
}
DEFAULT_WEIGHT = 1.0
DEFAULT_ANGLE = 0.0
MAX_WEIGHT = 20.0


class EndError(ValueError):
    """The end condition cannot be used as asked; the message says why."""


def allowed(kind):
    """The end conditions a profile of `kind` (sketch / face / point) offers."""
    return {"sketch": SKETCH_CONDITIONS, "face": FACE_CONDITIONS, "point": POINT_CONDITIONS}[kind]


def check(condition, kind, weight, angle=0.0):
    """Refuse an end condition the profile cannot take, or values out of range."""
    if condition not in CONDITIONS:
        raise EndError("unknown end condition %r" % (condition,))
    if condition not in allowed(kind):
        what = {"sketch": "a sketch profile", "face": "a face", "point": "a point"}[kind]
        names = ", ".join(label for label, _key in LABELS[kind])
        raise EndError("%s can only end %s." % (what.capitalize(), names))
    if condition == "free":
        return
    if not (0.0 < float(weight) <= MAX_WEIGHT):
        raise EndError("The weight must be more than 0 and at most %g." % MAX_WEIGHT)
    if condition == "direction" and not (-89.0 <= float(angle) <= 89.0):
        raise EndError("The takeoff angle must be between -89 and 89 degrees.")


# -- small linear algebra (no numpy in SciForge) ---------------------------------------------
def solve(matrix, rhs):
    """Solve matrix * X = rhs (Gaussian elimination with partial pivoting). `matrix` is a
    list of n rows of n numbers, `rhs` a list of n rows of m numbers; returns n rows of m."""
    n = len(matrix)
    a = [list(map(float, row)) + list(map(float, r)) for row, r in zip(matrix, rhs)]
    width = len(a[0])
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-14:
            raise EndError("The loft's end conditions give a singular system.")
        a[col], a[pivot] = a[pivot], a[col]
        lead = a[col][col]
        row = [x / lead for x in a[col]]
        a[col] = row
        for r in range(n):
            if r != col and a[r][col] != 0.0:
                f = a[r][col]
                a[r] = [x - f * y for x, y in zip(a[r], row)]
    return [row[n:width] for row in a]


# -- B-spline basis ---------------------------------------------------------------------------
def find_span(knots, degree, count, t):
    """Index of the knot span holding t (Piegl & Tiller A2.1); count = number of controls."""
    n = count - 1
    if t >= knots[n + 1]:
        return n
    if t <= knots[degree]:
        return degree
    low, high = degree, n + 1
    mid = (low + high) // 2
    while t < knots[mid] or t >= knots[mid + 1]:
        if t < knots[mid]:
            high = mid
        else:
            low = mid
        mid = (low + high) // 2
    return mid


def basis_derivatives(knots, degree, span, t, order):
    """Values and derivatives up to `order` of the degree+1 basis functions that are not 0
    at t (Piegl & Tiller A2.3): ders[k][j] for N_{span-degree+j}^(k)(t)."""
    p = degree
    ndu = [[0.0] * (p + 1) for _ in range(p + 1)]
    left = [0.0] * (p + 1)
    right = [0.0] * (p + 1)
    ndu[0][0] = 1.0
    for j in range(1, p + 1):
        left[j] = t - knots[span + 1 - j]
        right[j] = knots[span + j] - t
        saved = 0.0
        for r in range(j):
            ndu[j][r] = right[r + 1] + left[j - r]
            temp = ndu[r][j - 1] / ndu[j][r]
            ndu[r][j] = saved + right[r + 1] * temp
            saved = left[j - r] * temp
        ndu[j][j] = saved
    ders = [[0.0] * (p + 1) for _ in range(order + 1)]
    for j in range(p + 1):
        ders[0][j] = ndu[j][p]
    a = [[0.0] * (p + 1) for _ in range(2)]
    for r in range(p + 1):
        s1, s2 = 0, 1
        a[0][0] = 1.0
        for k in range(1, order + 1):
            d = 0.0
            rk = r - k
            pk = p - k
            if r >= k:
                a[s2][0] = a[s1][0] / ndu[pk + 1][rk]
                d = a[s2][0] * ndu[rk][pk]
            j1 = 1 if rk >= -1 else -rk
            j2 = k - 1 if r - 1 <= pk else p - r
            for j in range(j1, j2 + 1):
                a[s2][j] = (a[s1][j] - a[s1][j - 1]) / ndu[pk + 1][rk + j]
                d += a[s2][j] * ndu[rk + j][pk]
            if r <= pk:
                a[s2][k] = -a[s1][k - 1] / ndu[pk + 1][r]
                d += a[s2][k] * ndu[r][pk]
            ders[k][r] = d
            s1, s2 = s2, s1
    factor = p
    for k in range(1, order + 1):
        for j in range(p + 1):
            ders[k][j] *= factor
        factor *= p - k
    return ders


def knot_vector(params, start_extra=0, end_extra=0):
    """Clamped cubic knots with inner knots at the data parameters, and `start_extra` /
    `end_extra` more knots inside the first / last span (an end with two conditions)."""
    inner = list(params[1:-1])
    spans = len(params) - 1
    extra = []
    for s in range(spans):
        count = (start_extra if s == 0 else 0) + (end_extra if s == spans - 1 else 0)
        a, b = params[s], params[s + 1]
        extra += [a + (b - a) * (i + 1) / (count + 1.0) for i in range(count)]
    inner = sorted(inner + extra)
    return [params[0]] * (DEGREE + 1) + inner + [params[-1]] * (DEGREE + 1)


def _conditions(end):
    kind = end[0]
    if kind == "free":
        return [(2, None)]
    if kind == "d1":
        return [(1, end[1])]
    if kind == "d2":
        return [(1, end[1]), (2, end[2])]
    raise EndError("unknown end %r" % (kind,))


def interpolate(params, rows, start=("free",), end=("free",)):
    """Cubic B-spline curves (one per column) through rows[k] at params[k].
    Returns (knots, controls): the full knot vector and one row of numbers per control
    point. The derivative rows of `start` / `end` are given in the same columns."""
    if len(params) != len(rows) or len(params) < 2:
        raise EndError("interpolate needs at least two rows, one per parameter")
    if any(b <= a for a, b in zip(params, params[1:])):
        raise EndError("the parameters must increase")
    width = len(rows[0])
    first = _conditions(start)
    last = _conditions(end)
    knots = knot_vector(params, len(first) - 1, len(last) - 1)
    count = len(knots) - DEGREE - 1
    if count != len(rows) + len(first) + len(last):
        raise EndError("internal: %d controls for %d conditions" % (count, len(rows)))
    matrix, rhs = [], []

    def row_at(t, order):
        span = find_span(knots, DEGREE, count, t)
        ders = basis_derivatives(knots, DEGREE, span, t, order)
        line = [0.0] * count
        for j in range(DEGREE + 1):
            line[span - DEGREE + j] = ders[order][j]
        return line

    matrix.append(row_at(params[0], 0))
    rhs.append(list(rows[0]))
    for order, value in first:
        matrix.append(row_at(params[0], order))
        rhs.append(list(value) if value is not None else [0.0] * width)
    for t, row in zip(params[1:-1], rows[1:-1]):
        matrix.append(row_at(t, 0))
        rhs.append(list(row))
    for order, value in reversed(last):
        matrix.append(row_at(params[-1], order))
        rhs.append(list(value) if value is not None else [0.0] * width)
    matrix.append(row_at(params[-1], 0))
    rhs.append(list(rows[-1]))
    return knots, solve(matrix, rhs)


def evaluate(knots, controls, t, order=0):
    """Value (or a derivative) of the B-spline curve(s) at t: one number per column."""
    count = len(controls)
    span = find_span(knots, DEGREE, count, t)
    ders = basis_derivatives(knots, DEGREE, span, t, order)
    out = [0.0] * len(controls[0])
    for j in range(DEGREE + 1):
        c = controls[span - DEGREE + j]
        f = ders[order][j]
        for i in range(len(out)):
            out[i] += f * c[i]
    return out


def knots_and_mults(knots):
    """Distinct knots and their multiplicities (FreeCAD's form)."""
    values, mults = [], []
    for k in knots:
        if values and abs(k - values[-1]) < 1e-12:
            mults[-1] += 1
        else:
            values.append(k)
            mults.append(1)
    return values, mults


def chord_params(points):
    """Parameters 0..1 by the distances between consecutive points (each a 3-tuple)."""
    lengths = [0.0]
    for a, b in zip(points, points[1:]):
        lengths.append(lengths[-1] + math.dist(a, b))
    total = lengths[-1]
    if total <= 0.0:
        return [i / float(len(points) - 1) for i in range(len(points))]
    return [x / total for x in lengths]


def takeoff(normal, outward, angle_deg):
    """The direction a Direction end leaves its profile: the profile's normal (toward the
    loft) tilted by the takeoff angle toward `outward` (away from the profile's middle;
    positive angles open the loft out, SciForge's guess at Fusion's sign)."""
    a = math.radians(angle_deg)
    return tuple(math.cos(a) * n + math.sin(a) * o for n, o in zip(normal, outward))


def magnitude(weight, chord):
    """How long the end derivative is: the weight times the distance to the next profile
    (SciForge's rule; weight 1 makes a loft between equal profiles a straight prism)."""
    return float(weight) * float(chord)
