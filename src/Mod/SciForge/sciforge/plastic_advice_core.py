# SPDX-License-Identifier: LGPL-2.1-or-later
"""Design Advice (PLASTIC > INSPECT), the pure part: the checks against the plastic rule, the
ray casting they use, the colours and the rows of the issues list. No FreeCAD, no Qt: unit
tested (test_plastic2_core.py); plastic_advice.py measures the bodies.

Fusion's Design Advice (docs/sciforge/dev/research/fusion-plastic.md 2.11, 4.7; Autodesk)
uses the plastic rule of the component that holds a body and flags:

  thickness   walls thinner than the rule's minimum or thicker than its maximum
  variation   walls whose thickness strays from the rule's nominal Thickness by more than
              the Thickness Variation (a percentage, as Autodesk's blog has it)
  draft       faces with less draft against the pull direction than the rule's Minimum
              Draft Angle (faces square to the pull are fine)
  knife       knife edges: two faces meeting so sharply that, one knife-edge threshold in
              from the edge, the material is thinner than that threshold (a wedge under
              2 atan(1/2) = 53.13 degrees), and walls thinner than the threshold
  undercut    faces a two-part mould cannot reach: blocked along the pull direction they face
              (side faces: blocked both ways)

The local wall thickness at a point is the distance along the inward normal to the next face
of the body (the ray test SciForge's Accessibility Analysis uses too).
"""

import math

CHECKS = ("thickness", "variation", "draft", "knife", "undercut")
CHECK_TITLES = {
    "thickness": "Thickness",
    "variation": "Thickness Variation",
    "draft": "Draft",
    "knife": "Knife Edges",
    "undercut": "Undercuts",
}
KNIFE_ANGLE = math.degrees(2.0 * math.atan(0.5))  # 53.13 degrees
SQUARE = 89.5  # degrees of draft from which a face counts as square to the pull (a top)
EPS = 1e-12

# colours of the overlay (r, g, b)
OK = (0.30, 0.75, 0.35)
THIN = (0.20, 0.45, 0.95)
THICK = (0.95, 0.50, 0.10)
VARIES = (0.95, 0.80, 0.15)
DRAFT = (0.95, 0.85, 0.20)
UNDERCUT = (0.65, 0.25, 0.85)
KNIFE = (0.90, 0.10, 0.10)
ISSUE_COLORS = {
    "thin": THIN,
    "thick": THICK,
    "variation": VARIES,
    "draft": DRAFT,
    "undercut": UNDERCUT,
    "knife": KNIFE,
}
# which issue colours a face when it has several (most serious first)
PRIORITY = ("undercut", "knife", "thin", "thick", "draft", "variation")


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _unit(a):
    n = math.sqrt(_dot(a, a))
    if n < EPS:
        raise ValueError("zero vector")
    return (a[0] / n, a[1] / n, a[2] / n)


def draft_of(normal, pull):
    """Draft in degrees (0 .. 90) of a point with this outward normal for a part pulled along
    `pull` either way (a two-part mould): 0 = parallel to the pull, 90 = square to it."""
    d = abs(_dot(_unit(normal), _unit(pull)))
    return math.degrees(math.asin(min(1.0, d)))


def draft_issue(normal, pull, minimum):
    """True when a point has less draft than `minimum` degrees (square faces are fine)."""
    angle = draft_of(normal, pull)
    if angle >= SQUARE:
        return False
    return angle < minimum - 1e-9


def thickness_issue(t, rule):
    """ "thin", "thick" or "" for a local thickness t (mm) against the rule's range."""
    if t is None:
        return ""
    if t < rule["minimum_thickness"] - 1e-6:
        return "thin"
    if t > rule["maximum_thickness"] + 1e-6:
        return "thick"
    return ""


def variation_issue(t, rule):
    """True when t strays from the rule's Thickness by more than its Thickness Variation
    (percent)."""
    if t is None:
        return False
    nominal = rule["thickness"]
    if nominal <= 0:
        return False
    return abs(t - nominal) / nominal * 100.0 > rule["thickness_variation"] + 1e-6


def knife_issue(interior_angle, t=None, threshold=None):
    """True for a convex edge sharper than KNIFE_ANGLE (degrees, measured in the material), or a
    wall thinner than the knife edge threshold."""
    if interior_angle is not None and interior_angle < KNIFE_ANGLE - 1e-9:
        return True
    return t is not None and threshold is not None and t < threshold - 1e-6


def undercut_issue(normal, pull, blocked_along, blocked_against, tol=1e-3):
    """True when a two-part mould pulled along `pull` cannot reach the point: a point facing
    along the pull must be free along it, one facing against it free against it, a side
    point free either way."""
    s = _dot(_unit(normal), _unit(pull))
    if s > tol:
        return bool(blocked_along)
    if s < -tol:
        return bool(blocked_against)
    return bool(blocked_along) and bool(blocked_against)


def face_color(issues):
    """The overlay colour of a face with these issues."""
    for name in PRIORITY:
        if name in issues:
            return ISSUE_COLORS[name]
    return OK


def heat_color(t, lo, hi):
    """Thickness heat map: blue (thin) .. green (nominal) .. red (thick)."""
    if t is None:
        return (0.6, 0.6, 0.6)
    if hi <= lo:
        return OK
    x = max(0.0, min(1.0, (t - lo) / (hi - lo)))
    if x < 0.5:
        k = x / 0.5
        return (0.2 * (1 - k) + 0.3 * k, 0.45 * (1 - k) + 0.75 * k, 0.95 * (1 - k) + 0.35 * k)
    k = (x - 0.5) / 0.5
    return (0.3 * (1 - k) + 0.9 * k, 0.75 * (1 - k) + 0.15 * k, 0.35 * (1 - k) + 0.1 * k)


def blended_thickness(point, samples, power=2.0):
    """The thickness at `point` from a face's samples [(x, y, z, t)], weighted by the inverse
    distance (the Thickness display shades each face smoothly between its samples)."""
    if not samples:
        return None
    total = weight = 0.0
    for x, y, z, t in samples:
        d2 = (point[0] - x) ** 2 + (point[1] - y) ** 2 + (point[2] - z) ** 2
        if d2 < 1e-18:
            return t
        w = 1.0 / d2 ** (power / 2.0)
        total += w * t
        weight += w
    return total / weight


def blended_many(points, samples, power=2.0):
    """blended_thickness for many points (numpy when there is one)."""
    if not samples:
        return [None] * len(points)
    try:
        import numpy as np
    except ImportError:
        return [blended_thickness(p, samples, power) for p in points]
    if not len(points):
        return []
    P = np.asarray(points, dtype=float).reshape(-1, 3)
    S = np.asarray(samples, dtype=float).reshape(-1, 4)
    d2 = ((P[:, None, :] - S[None, :, :3]) ** 2).sum(axis=2)
    exact = d2 < 1e-18
    w = 1.0 / np.maximum(d2, 1e-18) ** (power / 2.0)
    t = (w * S[None, :, 3]).sum(axis=1) / w.sum(axis=1)
    hit = exact.any(axis=1)
    if hit.any():
        t[hit] = S[np.argmax(exact[hit], axis=1), 3]
    return [float(x) for x in t]


# -- rows of the issues list -------------------------------------------------------------------
def describe(issue, value):
    """The text of one issue for the list."""
    if issue == "thin":
        return "Too thin: %.2f mm" % value
    if issue == "thick":
        return "Too thick: %.2f mm" % value
    if issue == "variation":
        return "Thickness varies: %.2f mm" % value
    if issue == "draft":
        return "Draft %.2f deg" % value
    if issue == "undercut":
        return "Undercut"
    if issue == "knife":
        return "Knife edge: %.1f deg" % value if value is not None else "Knife edge"
    return issue


CHECK_OF = {
    "thin": "thickness",
    "thick": "thickness",
    "variation": "variation",
    "draft": "draft",
    "undercut": "undercut",
    "knife": "knife",
}


def rows(results):
    """[(check title, body label, element, text)] of every issue, grouped by check."""
    out = []
    order = {c: i for i, c in enumerate(CHECKS)}
    for body in results.get("bodies", []):
        for element, data in sorted(body.get("faces", {}).items(), key=lambda kv: _num(kv[0])):
            for issue, value in data.get("issues", {}).items():
                out.append(
                    (CHECK_OF[issue], body["label"], element, describe(issue, value), body["name"])
                )
        for element, value in sorted(body.get("edges", {}).items(), key=lambda kv: _num(kv[0])):
            out.append(("knife", body["label"], element, describe("knife", value), body["name"]))
    out.sort(key=lambda r: (order[r[0]], r[1], _num(r[2])))
    return [(CHECK_TITLES[c], label, el, text, name) for c, label, el, text, name in out]


def _num(name):
    digits = "".join(ch for ch in str(name) if ch.isdigit())
    return (str(name).rstrip("0123456789"), int(digits) if digits else 0)


def summary(results):
    """{check: number of faces / edges with that issue} over all bodies."""
    counts = {c: 0 for c in CHECKS}
    for body in results.get("bodies", []):
        for data in body.get("faces", {}).values():
            for check in {CHECK_OF[i] for i in data.get("issues", {})}:
                counts[check] += 1
        counts["knife"] += len(body.get("edges", {}))
    return counts


def summary_text(results):
    counts = summary(results)
    if not any(counts.values()):
        return "No issues: the design follows its plastic rule."
    parts = ["%s %d" % (CHECK_TITLES[c], counts[c]) for c in CHECKS if counts[c]]
    return "Issues: " + ", ".join(parts)


# -- ray casting --------------------------------------------------------------------------------
def first_hits(origins, directions, triangles, near=1e-6, index=False):
    """For each ray (origin, direction): the distance to the first triangle it meets beyond
    `near` (in lengths of its direction), or None. triangles: [((x, y, z), (x, y, z),
    (x, y, z))]. With index: (distance, triangle index) pairs instead. numpy when there is
    one (RayGrid), plain Python otherwise."""
    if not origins:
        return []
    grid = RayGrid.of(triangles)
    if grid is None:
        found = [_first_hit_py(o, d, triangles, near, True) for o, d in zip(origins, directions)]
        return found if index else [hit[0] for hit in found]
    return grid.cast(origins, directions, near, index)


class RayGrid:
    """The triangles of a body sorted into a grid of cubes, so a ray only tests the triangles
    in the cubes it passes through (a part's thousands of display triangles against its
    thousands of sample rays would otherwise be millions of tests).

    Along a ray, points are taken every `step`; a triangle is listed in every cube its box,
    grown by half a step, reaches. A ray meeting a triangle passes within half a step of one
    of its points, and that point's cube lists the triangle."""

    CELLS = 48  # cubes along the longest side of the body

    @classmethod
    def of(cls, triangles):
        if not triangles:
            return None
        try:
            import numpy  # noqa: F401
        except ImportError:
            return None
        return cls(triangles)

    def __init__(self, triangles, cells=None):
        import numpy as np

        self.np = np
        T = np.asarray(triangles, dtype=float).reshape(-1, 3, 3)
        self.A = T[:, 0, :]
        self.E1 = T[:, 1, :] - self.A
        self.E2 = T[:, 2, :] - self.A
        lo = T.min(axis=(0, 1))
        hi = T.max(axis=(0, 1))
        span = max(float((hi - lo).max()), 1e-9)
        self.size = span / float(cells or self.CELLS)
        self.step = 0.5 * self.size
        grow = 0.5 * self.step + 1e-9 * span
        self.lo = lo - grow - 1e-9 * span
        self.hi = hi + grow + 1e-9 * span
        self.dims = np.maximum(1, np.ceil((self.hi - self.lo) / self.size).astype(np.int64))
        first = self._cell(T.min(axis=1) - grow)
        last = self._cell(T.max(axis=1) + grow)
        span3 = last - first + 1
        counts = span3.prod(axis=1)
        owner = np.repeat(np.arange(len(T)), counts)
        offset = np.arange(int(counts.sum())) - np.repeat(np.cumsum(counts) - counts, counts)
        width = span3[owner]
        cx = first[owner, 0] + offset % width[:, 0]
        rest = offset // width[:, 0]
        cy = first[owner, 1] + rest % width[:, 1]
        cz = first[owner, 2] + rest // width[:, 1]
        flat = self._flat(cx, cy, cz)
        order = np.argsort(flat, kind="stable")
        self.keys, self.starts = np.unique(flat[order], return_index=True)
        self.ends = np.append(self.starts[1:], len(order))
        self.owners = owner[order]

    def _cell(self, points):
        np = self.np
        found = np.floor((points - self.lo) / self.size).astype(np.int64)
        return np.clip(found, 0, self.dims - 1)

    def _flat(self, cx, cy, cz):
        return (cx * self.dims[1] + cy) * self.dims[2] + cz

    def _span(self, o, d):
        """The part of the ray inside the grid's box: (enter, leave) or None."""
        enter, leave = -math.inf, math.inf
        for k in range(3):
            if abs(d[k]) < 1e-15:
                if o[k] < self.lo[k] or o[k] > self.hi[k]:
                    return None
                continue
            a = (self.lo[k] - o[k]) / d[k]
            b = (self.hi[k] - o[k]) / d[k]
            enter = max(enter, min(a, b))
            leave = min(leave, max(a, b))
        return (enter, leave) if leave >= enter else None

    def candidates(self, o, d, near):
        """Indices of the triangles listed in the cubes the unit ray o + t d (t > near)
        passes through."""
        np = self.np
        span = self._span(o, d)
        if span is None or span[1] < near:
            return None
        start = max(span[0], near)
        count = int(math.ceil((span[1] - start) / self.step)) + 1
        t = start + np.arange(count + 1) * self.step
        cells = self._cell(o[None, :] + t[:, None] * d[None, :])
        flat = np.unique(self._flat(cells[:, 0], cells[:, 1], cells[:, 2]))
        pos = np.searchsorted(self.keys, flat)
        inside = pos < len(self.keys)
        pos, flat = pos[inside], flat[inside]
        pos = pos[self.keys[pos] == flat]
        if not len(pos):
            return None
        parts = [self.owners[self.starts[p] : self.ends[p]] for p in pos]
        return np.unique(np.concatenate(parts))

    def nearest(self, point, radius):
        """(distance, triangle index) of the triangle nearest to `point` if one comes within
        `radius` of it, else None."""
        np = self.np
        p = np.asarray(point, dtype=float)
        lo = self._cell(p - radius)
        hi = self._cell(p + radius)
        ranges = [np.arange(lo[k], hi[k] + 1) for k in range(3)]
        cx, cy, cz = np.meshgrid(*ranges, indexing="ij")
        flat = np.unique(self._flat(cx.ravel(), cy.ravel(), cz.ravel()))
        pos = np.searchsorted(self.keys, flat)
        inside = pos < len(self.keys)
        pos, flat = pos[inside], flat[inside]
        pos = pos[self.keys[pos] == flat]
        if not len(pos):
            return None
        cand = np.unique(np.concatenate([self.owners[self.starts[q] : self.ends[q]] for q in pos]))
        dist = _point_triangle_distances(np, p, self.A[cand], self.E1[cand], self.E2[cand])
        k = int(np.argmin(dist))
        if dist[k] > radius:
            return None
        return (float(dist[k]), int(cand[k]))

    def cast(self, origins, directions, near=1e-6, index=False):
        """first_hits for these rays; near: one distance for all, or one for each ray."""
        np = self.np
        out = []
        nears = near if isinstance(near, (list, tuple)) else [near] * len(origins)
        for origin, direction, near in zip(origins, directions, nears):
            o = np.asarray(origin, dtype=float)
            d = np.asarray(direction, dtype=float)
            length = float(np.sqrt((d * d).sum()))
            if length < 1e-15:
                out.append((None, None) if index else None)
                continue
            u = d / length
            hit = self._first(o, u, near * length)
            if hit[0] is not None:
                hit = (hit[0] / length, hit[1])
            out.append(hit if index else hit[0])
        return out

    def _first(self, o, d, near):
        np = self.np
        cand = self.candidates(o, d, near)
        if cand is None or not len(cand):
            return (None, None)
        A, E1, E2 = self.A[cand], self.E1[cand], self.E2[cand]
        pvec = _cross(np, d[None, :], E2)
        det = (E1 * pvec).sum(axis=1)
        good = np.abs(det) > 1e-14
        inv = np.where(good, 1.0 / np.where(good, det, 1.0), 0.0)
        s = o[None, :] - A
        u = (s * pvec).sum(axis=1) * inv
        q = _cross(np, s, E1)
        v = (q * d[None, :]).sum(axis=1) * inv
        t = (q * E2).sum(axis=1) * inv
        hit = good & (u >= -1e-9) & (u <= 1 + 1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9)
        t = np.where(hit & (t > near), t, np.inf)
        k = int(np.argmin(t))
        if not math.isfinite(t[k]):
            return (None, None)
        return (float(t[k]), int(cand[k]))


def _cross(np, a, b):
    """Row-wise cross products of (n, 3) arrays (one row is spread over the other's rows);
    numpy's own cross is several times slower on these sizes."""
    return np.stack(
        (
            a[:, 1] * b[:, 2] - a[:, 2] * b[:, 1],
            a[:, 2] * b[:, 0] - a[:, 0] * b[:, 2],
            a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0],
        ),
        axis=1,
    )


def point_triangle_distance(p, tri):
    """The distance from point p to the triangle tri ((x, y, z) x 3), plain Python."""
    a, b, c = tri

    def sub(x, y):
        return (x[0] - y[0], x[1] - y[1], x[2] - y[2])

    def cross(x, y):
        return (x[1] * y[2] - x[2] * y[1], x[2] * y[0] - x[0] * y[2], x[0] * y[1] - x[1] * y[0])

    def segment(p0, p1):
        d = sub(p1, p0)
        t = max(0.0, min(1.0, _dot(sub(p, p0), d) / max(_dot(d, d), 1e-30)))
        q = (p0[0] + t * d[0], p0[1] + t * d[1], p0[2] + t * d[2])
        return math.sqrt(_dot(sub(p, q), sub(p, q)))

    e1, e2 = sub(b, a), sub(c, a)
    n = cross(e1, e2)
    nn = _dot(n, n)
    w = sub(p, a)
    if nn > 1e-30:
        u = _dot(cross(w, e2), n) / nn
        v = _dot(cross(e1, w), n) / nn
        if u >= 0 and v >= 0 and u + v <= 1:
            return abs(_dot(w, n)) / math.sqrt(nn)
    return min(segment(a, b), segment(a, c), segment(b, c))


def _point_triangle_distances(np, p, A, E1, E2):
    """The distance from point p to each triangle (A, A + E1, A + E2), numpy arrays (n, 3)."""
    N = _cross(np, E1, E2)
    nn = (N * N).sum(axis=1)
    w = p[None, :] - A
    ok = nn > 1e-30
    safe = np.where(ok, nn, 1.0)
    u = (_cross(np, w, E2) * N).sum(axis=1) / safe
    v = (_cross(np, E1, w) * N).sum(axis=1) / safe
    plane = np.abs((w * N).sum(axis=1)) / np.sqrt(safe)
    inside = ok & (u >= 0) & (v >= 0) & (u + v <= 1)

    def segment(P0, D):
        dd = np.maximum((D * D).sum(axis=1), 1e-30)
        t = np.clip(((p[None, :] - P0) * D).sum(axis=1) / dd, 0.0, 1.0)
        q = P0 + t[:, None] * D
        return np.sqrt(((p[None, :] - q) ** 2).sum(axis=1))

    edges = np.minimum(np.minimum(segment(A, E1), segment(A, E2)), segment(A + E1, E2 - E1))
    return np.where(inside, plane, edges)


def _first_hit_py(origin, direction, triangles, near, index=False):
    best, which = None, None
    for k, (a, b, c) in enumerate(triangles):
        t = _ray_triangle(origin, direction, a, b, c)
        if t is not None and t > near and (best is None or t < best):
            best, which = t, k
    return (best, which) if index else best


def _ray_triangle(o, d, a, b, c):
    e1 = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    e2 = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    p = (d[1] * e2[2] - d[2] * e2[1], d[2] * e2[0] - d[0] * e2[2], d[0] * e2[1] - d[1] * e2[0])
    det = _dot(e1, p)
    if abs(det) < 1e-14:
        return None
    inv = 1.0 / det
    s = (o[0] - a[0], o[1] - a[1], o[2] - a[2])
    u = _dot(s, p) * inv
    if u < -1e-9 or u > 1 + 1e-9:
        return None
    q = (s[1] * e1[2] - s[2] * e1[1], s[2] * e1[0] - s[0] * e1[2], s[0] * e1[1] - s[1] * e1[0])
    v = _dot(d, q) * inv
    if v < -1e-9 or u + v > 1 + 1e-9:
        return None
    return _dot(e2, q) * inv
