# SPDX-License-Identifier: LGPL-2.1-or-later
"""The maths of Fusion's surface analyses (INSPECT menu), without FreeCAD or Qt: unit tested.

Vectors are plain 3-tuples. Colours are (r, g, b) in 0..1. The analyses themselves
(surface_analysis.py) feed these with points, normals and curvatures of the model.

  Draft Analysis       draft_angle / draft_class / draft_color: each point of the model is
                       coloured by its draft angle against the pull direction.
  Zebra Analysis       zebra_parameter: where a point's reflection lands on striped
                       surroundings (a ball round the model with rings of stripes), so
                       the stripes move when the view turns or zooms.
  Curvature Comb       comb_params / comb_gain / comb_tooth / comb_color.
  Curvature Map        gaussian_color / principal_value / limit_color.
  Isocurve             iso_values (and the comb functions).
  Accessibility        ray_hits_triangle / accessible.
  Minimum Radius       concave_radius / min_radius_color.
"""

import math

# -- vectors -------------------------------------------------------------------------------
EPS = 1e-12


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def scale(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def length(a):
    return math.sqrt(dot(a, a))


def unit(a):
    n = length(a)
    if n < EPS:
        raise ValueError("a direction of length 0")
    return (a[0] / n, a[1] / n, a[2] / n)


def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def mix(a, b, t):
    """Colour (or vector) a .. b at t in 0..1."""
    t = clamp(t, 0.0, 1.0)
    if t <= 0.0:
        return tuple(a)
    if t >= 1.0:
        return tuple(b)
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def ramp(stops, t):
    """Colour along evenly spaced stops at t in 0..1."""
    t = clamp(t, 0.0, 1.0)
    if len(stops) == 1:
        return stops[0]
    x = t * (len(stops) - 1)
    i = min(int(x), len(stops) - 2)
    return mix(stops[i], stops[i + 1], x - i)


# -- colours -------------------------------------------------------------------------------
GREEN = (0.18, 0.74, 0.30)
BLUE = (0.20, 0.45, 0.95)
RED = (0.90, 0.20, 0.18)
YELLOW = (0.98, 0.84, 0.18)
ORANGE = (0.98, 0.55, 0.12)
INDIGO = (0.30, 0.22, 0.80)
VIOLET = (0.58, 0.25, 0.85)
NEUTRAL = (0.62, 0.64, 0.68)  # nothing to show here (a flat face in a radius map)


# -- Draft Analysis --------------------------------------------------------------------------
def draft_angle(normal, pull):
    """Draft angle in degrees of a point whose outward normal is `normal`, for a part pulled
    out of its mould along `pull`: +90 faces straight along the pull, 0 is parallel to it
    (a wall with no draft), -90 faces straight against it."""
    n = unit(normal)
    d = unit(pull)
    return math.degrees(math.asin(clamp(dot(n, d), -1.0, 1.0)))


def draft_class(angle, start, stop):
    """Which side a draft angle is on, against the Draft Angle range start .. stop
    (degrees, 0 <= start <= stop):
      "positive"   angle >= stop: comes out along the pull (green)
      "negative"   angle <= -stop: comes out against it, the other mould half (blue)
      "vertical"   |angle| < start: not enough draft either way (red)
      "tolerance+" start <= angle < stop (between red and green)
      "tolerance-" -stop < angle <= -start (between red and blue)"""
    start, stop = sorted((abs(float(start)), abs(float(stop))))
    if stop > 0:
        if angle >= stop:
            return "positive"
        if angle <= -stop:
            return "negative"
    elif abs(angle) > 1e-9:
        return "positive" if angle > 0 else "negative"
    if abs(angle) < start or start == stop:
        return "vertical"
    return "tolerance+" if angle > 0 else "tolerance-"


def draft_color(angle, start, stop, tolerance_zone=False):
    """The colour of a draft angle: green / blue with enough draft along / against the pull,
    red without; between start and stop a blend (or yellow with Tolerance Zone on)."""
    kind = draft_class(angle, start, stop)
    if kind == "positive":
        return GREEN
    if kind == "negative":
        return BLUE
    if kind == "vertical":
        return RED
    if tolerance_zone:
        return YELLOW
    lo, hi = sorted((abs(float(start)), abs(float(stop))))
    t = (abs(angle) - lo) / (hi - lo) if hi > lo else 1.0
    return mix(RED, GREEN if kind == "tolerance+" else BLUE, t)


# -- Zebra Analysis --------------------------------------------------------------------------
def reflect(direction, normal):
    """`direction` mirrored at a surface with unit `normal`."""
    return sub(direction, scale(normal, 2.0 * dot(direction, normal)))


def sphere_exit(point, direction, centre, radius):
    """Where the ray from `point` (inside the sphere) along unit `direction` leaves it."""
    oc = sub(point, centre)
    b = dot(oc, direction)
    c = dot(oc, oc) - radius * radius
    t = -b + math.sqrt(max(0.0, b * b - c))
    return add(point, scale(direction, max(0.0, t)))


def zebra_parameter(point, normal, view, right, up, centre, radius, vertical=False):
    """Stripe coordinate (0..1) of what the surface at `point` (unit outward `normal`)
    reflects towards a camera looking along unit `view`, with the screen's `right` and `up`.
    The surroundings are a large ball round the model (`centre`, `radius`) painted with
    stripes: rings round the screen's up axis (horizontal stripes) or round its right axis
    (vertical ones), seen from the camera. The coordinate is the latitude where the
    reflected ray leaves the ball: smooth everywhere, so smooth surfaces give smooth
    stripes, a kink in the surface a kink in the stripes and a step a break, which is what
    a zebra analysis is for. The ball is near, so a flat face shows stripes too, and they
    move when the view turns or zooms."""
    n = unit(normal)
    if dot(n, view) > 0:  # seen from behind (inside a hole): mirror it the same way
        n = scale(n, -1.0)
    r = unit(reflect(view, n))
    hit = sphere_exit(point, r, centre, radius)
    rel = sub(hit, centre)
    size = length(rel)
    if size < EPS:
        return 0.5
    axis = right if vertical else up
    return 0.5 + math.asin(clamp(dot(rel, axis) / size, -1.0, 1.0)) / math.pi


def stripe_of(parameter, repeats):
    """0 (dark) or 1 (light): which stripe a coordinate falls in with `repeats` stripe pairs."""
    x = parameter * max(1, int(repeats))
    return 1 if (x - math.floor(x)) < 0.5 else 0


# -- Curvature Comb and Isocurve ---------------------------------------------------------------
DENSITY_RANGE = (2, 100)


def comb_params(first, last, density):
    """`density` parameters from `first` to `last` (both ends included), the comb's teeth.
    Density is clamped to Fusion's 2 .. 100."""
    count = int(clamp(int(density), DENSITY_RANGE[0], DENSITY_RANGE[1]))
    step = (last - first) / (count - 1)
    return [first + step * i for i in range(count)]


def comb_gain(curvatures, reference, scale_factor=1.0):
    """Length per unit of curvature so that the tallest tooth is a quarter of `reference`
    (the size of what is analysed) at Scale 1. 0 when everything is straight."""
    peak = max([abs(k) for k in curvatures] or [0.0])
    if peak < EPS or reference <= 0:
        return 0.0
    return 0.25 * reference * max(0.0, float(scale_factor)) / peak


def comb_tooth(point, to_centre, curvature, gain):
    """Tip of a comb tooth: from `point` away from the centre of curvature (`to_centre` is
    the unit principal normal, pointing at that centre), as long as curvature x gain."""
    return sub(point, scale(to_centre, abs(curvature) * gain))


def comb_color(curvature, peak):
    """Teeth from blue (straight) through green and yellow to red (the tightest bend)."""
    if peak < EPS:
        return BLUE
    return ramp([BLUE, GREEN, YELLOW, RED], abs(curvature) / peak)


def iso_values(lo, hi, count):
    """`count` evenly spaced values strictly between lo and hi (the isocurves of a face)."""
    count = max(0, int(count))
    return [lo + (hi - lo) * (i + 1) / (count + 1) for i in range(count)]


# -- Curvature Map ---------------------------------------------------------------------------
MAP_TYPES = ("Gaussian", "Principal Minimum", "Principal Maximum")
GAUSS_POSITIVE = [GREEN, YELLOW, ORANGE, RED]
GAUSS_NEGATIVE = [GREEN, BLUE, INDIGO, VIOLET]
BANDS = 4  # colour steps on each side with Display = Bands


def gaussian_level(k1, k2, size, scale_factor=1.0):
    """-1 .. 1: how strongly the surface curves both ways (Gaussian curvature k1 k2), signed
    (+ dome, - saddle), measured against the size of the model so a corner round of a tenth
    of the part shows in the warm colours at Scale 1."""
    gauss = k1 * k2
    if abs(gauss) < EPS:
        return 0.0
    strength = math.sqrt(abs(gauss)) * size * max(0.0, float(scale_factor)) / 20.0
    return math.copysign(clamp(strength, 0.0, 1.0), gauss)


def gaussian_color(level, bands=False):
    """Positive: green -> yellow -> orange -> red; negative: green -> blue -> indigo ->
    violet; 0 (flat one way or both) green. Bands: no blending between colours."""
    t = abs(level)
    if bands:
        t = math.ceil(t * BANDS - 1e-9) / BANDS
    return ramp(GAUSS_POSITIVE if level >= 0 else GAUSS_NEGATIVE, t)


def principal_value(k1, k2, kind):
    """The curvature a Principal map shows: the smaller (Principal Minimum) or larger
    (Principal Maximum) of the two principal curvatures, as a magnitude."""
    a, b = abs(k1), abs(k2)
    return min(a, b) if kind == "Principal Minimum" else max(a, b)


def limit_color(curvature, limit_radius):
    """Green where the surface bends less than a radius of `limit_radius` would, turning
    yellow towards it, red where it bends as tight or tighter."""
    if limit_radius <= 0:
        return RED if curvature > EPS else GREEN
    t = curvature * limit_radius
    if t >= 1.0 - 1e-9:
        return RED
    return mix(GREEN, YELLOW, t)


# -- Accessibility ---------------------------------------------------------------------------
ACCESS_MODES = ("Direction 1", "Direction 2", "Both Directions")
ACCESSIBLE = GREEN
BLOCKED = RED


def ray_hits_triangle(origin, direction, a, b, c, near=1e-6):
    """True when the ray origin + t direction (t > near) passes through triangle abc
    (Moeller-Trumbore)."""
    e1 = sub(b, a)
    e2 = sub(c, a)
    p = cross(direction, e2)
    det = dot(e1, p)
    if abs(det) < EPS:
        return False
    inv = 1.0 / det
    s = sub(origin, a)
    u = dot(s, p) * inv
    if u < -1e-9 or u > 1.0 + 1e-9:
        return False
    q = cross(s, e1)
    v = dot(direction, q) * inv
    if v < -1e-9 or u + v > 1.0 + 1e-9:
        return False
    return dot(e2, q) * inv > near


def accessible(point, normal, direction, triangles, lift=1e-4):
    """True when a tool coming along -`direction` (it moves in `direction` to leave) reaches
    `point`: the surface faces it and nothing of the part (`triangles`, [(a, b, c)]) is in
    the way."""
    d = unit(direction)
    if dot(unit(normal), d) <= 1e-9:
        return False
    start = add(point, scale(d, lift))
    return not any(ray_hits_triangle(start, d, a, b, c) for a, b, c in triangles)


def access_directions(pull, mode):
    """The directions a tool may come from for an Accessibility mode."""
    d = unit(pull)
    if mode == "Direction 2":
        return [scale(d, -1.0)]
    if mode == "Both Directions":
        return [d, scale(d, -1.0)]
    return [d]


def reachable_points(points, normals, directions, triangles, size=None):
    """For each point: True when a tool coming along one of `directions` reaches it (see
    accessible). Uses numpy when there is one (FreeCAD has it), plain Python otherwise."""
    if size is None:
        size = _extent(points)
    lift = max(1e-9, 1e-6 * size)
    try:
        import numpy
    except ImportError:
        numpy = None
    if numpy is None or not triangles:
        return [
            any(accessible(p, n, d, triangles, lift) for d in directions)
            for p, n in zip(points, normals)
        ]
    return _reachable_numpy(numpy, points, normals, directions, triangles, lift)


def _extent(points):
    if not points:
        return 1.0
    lo = [min(p[i] for p in points) for i in range(3)]
    hi = [max(p[i] for p in points) for i in range(3)]
    return max(1e-9, length(sub(hi, lo)))


def _reachable_numpy(np, points, normals, directions, triangles, lift, chunk=256):
    P = np.asarray(points, dtype=float)
    N = np.asarray(normals, dtype=float)
    T = np.asarray(triangles, dtype=float)  # (t, 3, 3)
    A = T[:, 0, :]
    E1 = T[:, 1, :] - A
    E2 = T[:, 2, :] - A
    ok = np.zeros(len(P), dtype=bool)
    for d in directions:
        d = np.asarray(unit(d), dtype=float)
        facing = N.dot(d) > 1e-9
        pvec = np.cross(d, E2)  # (t, 3)
        det = (E1 * pvec).sum(axis=1)  # (t,)
        good = np.abs(det) > EPS
        inv = np.where(good, 1.0 / np.where(good, det, 1.0), 0.0)
        for start in range(0, len(P), chunk):
            sl = slice(start, start + chunk)
            want = facing[sl] & ~ok[sl]
            if not want.any():
                continue
            origin = P[sl][want] + d * lift  # (m, 3)
            s = origin[:, None, :] - A[None, :, :]  # (m, t, 3)
            u = (s * pvec[None, :, :]).sum(axis=2) * inv[None, :]
            q = np.cross(s, E1[None, :, :])
            v = (q * d[None, None, :]).sum(axis=2) * inv[None, :]
            t = (q * E2[None, :, :]).sum(axis=2) * inv[None, :]
            hit = (
                good[None, :]
                & (u >= -1e-9)
                & (u <= 1.0 + 1e-9)
                & (v >= -1e-9)
                & (u + v <= 1.0 + 1e-9)
                & (t > lift)
            )
            free = ~hit.any(axis=1)
            idx = np.nonzero(want)[0] + start
            ok[idx[free]] = True
    return [bool(x) for x in ok]


def zebra_parameters(points, normals, view, right, up, centre, radius, vertical=False):
    """zebra_parameter for many points at once (numpy when there is one)."""
    try:
        import numpy as np
    except ImportError:
        return [
            zebra_parameter(p, n, view, right, up, centre, radius, vertical)
            for p, n in zip(points, normals)
        ]
    P = np.asarray(points, dtype=float).reshape(-1, 3)
    N = np.asarray(normals, dtype=float).reshape(-1, 3)
    d = np.asarray(unit(view), dtype=float)
    lens = np.linalg.norm(N, axis=1)
    N = N / np.where(lens > EPS, lens, 1.0)[:, None]
    N[N.dot(d) > 0] *= -1.0
    R = d[None, :] - 2.0 * (N.dot(d))[:, None] * N
    rl = np.linalg.norm(R, axis=1)
    R = R / np.where(rl > EPS, rl, 1.0)[:, None]
    oc = P - np.asarray(centre, dtype=float)[None, :]
    b = (oc * R).sum(axis=1)
    c = (oc * oc).sum(axis=1) - radius * radius
    t = -b + np.sqrt(np.maximum(0.0, b * b - c))
    rel = oc + R * np.maximum(0.0, t)[:, None]
    size = np.linalg.norm(rel, axis=1)
    axis = np.asarray(right if vertical else up, dtype=float)
    ratio = rel.dot(axis) / np.where(size > EPS, size, 1.0)
    out = 0.5 + np.arcsin(np.clip(ratio, -1.0, 1.0)) / math.pi
    out[size <= EPS] = 0.5
    return [float(v) for v in out]


# -- Minimum Radius --------------------------------------------------------------------------
def concave_radius(k1, k2):
    """Radius of the tightest concave bend at a point, from its principal curvatures signed
    against the outward normal (positive = concave, the surface bends towards the outside:
    an inside corner round), or None where it is not concave."""
    concave = [k for k in (k1, k2) if k > EPS]
    if not concave:
        return None
    return 1.0 / max(concave)


def min_radius_color(radius, minimum, tool):
    """Concave regions a tool of radius `tool` fits into (radius >= tool) green; regions
    tighter than `minimum` red; in between a blend through yellow. Not concave: neutral."""
    if radius is None:
        return NEUTRAL
    lo, hi = sorted((max(0.0, float(minimum)), max(0.0, float(tool))))
    if radius >= hi:
        return GREEN
    if radius <= lo:
        return RED
    t = (radius - lo) / (hi - lo) if hi > lo else 1.0
    return ramp([RED, YELLOW, GREEN], t)


# -- mesh helpers ------------------------------------------------------------------------------
def subdivide(points, triangles, max_edge):
    """Split the triangles whose longest side is longer than `max_edge` into four, again and
    again (shared midpoints), so values worked out per point are drawn finely enough. The
    new points lie in the old triangles: the model's own surface is not moved.
    points: [(x, y, z)], triangles: [(i, j, k)] -> (points, triangles)."""
    points = list(points)
    tris = list(triangles)
    if max_edge <= 0:
        return points, tris
    limit = max_edge * max_edge
    for _round in range(8):
        cache = {}
        out = []
        split_any = False

        def midpoint(i, j):
            key = (i, j) if i < j else (j, i)
            found = cache.get(key)
            if found is None:
                a, b = points[i], points[j]
                points.append(((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0, (a[2] + b[2]) / 2.0))
                found = len(points) - 1
                cache[key] = found
            return found

        for i, j, k in tris:
            a, b, c = points[i], points[j], points[k]
            longest = max(dot(sub(a, b), sub(a, b)), dot(sub(b, c), sub(b, c)))
            longest = max(longest, dot(sub(c, a), sub(c, a)))
            if longest <= limit:
                out.append((i, j, k))
                continue
            split_any = True
            ij, jk, ki = midpoint(i, j), midpoint(j, k), midpoint(k, i)
            out += [(i, ij, ki), (ij, j, jk), (ki, jk, k), (ij, jk, ki)]
        # A neighbour that was not split keeps a long side with a midpoint on it (a
        # T-junction): harmless for colours, the surface stays the same plane.
        tris = out
        if not split_any or len(points) > 400000:
            break
    return points, tris
