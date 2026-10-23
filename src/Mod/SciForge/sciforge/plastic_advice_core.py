# SPDX-License-Identifier: LGPL-2.1-or-later
"""Design Advice (PLASTIC > INSPECT), the pure part: the checks against the plastic rule, the
ray casting they use, the colours and the rows of the issues list. No FreeCAD, no Qt: unit
tested (test_plastic_advice_core.py); plastic_advice.py measures the bodies.

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
def first_hits(origins, directions, triangles, near=1e-6, chunk=128):
    """For each ray (origin, direction): the distance to the first triangle it meets beyond
    `near`, or None. triangles: [((x, y, z), (x, y, z), (x, y, z))]. numpy when there is one."""
    if not origins:
        return []
    try:
        import numpy as np
    except ImportError:
        np = None
    if np is None or not triangles:
        return [_first_hit_py(o, d, triangles, near) for o, d in zip(origins, directions)]
    T = np.asarray(triangles, dtype=float)
    A = T[:, 0, :]
    E1 = T[:, 1, :] - A
    E2 = T[:, 2, :] - A
    O = np.asarray(origins, dtype=float)
    D = np.asarray(directions, dtype=float)
    out = []
    for start in range(0, len(O), chunk):
        o = O[start : start + chunk]
        d = D[start : start + chunk]
        pvec = np.cross(d[:, None, :], E2[None, :, :])  # (m, t, 3)
        det = (E1[None, :, :] * pvec).sum(axis=2)  # (m, t)
        good = np.abs(det) > 1e-14
        inv = np.where(good, 1.0 / np.where(good, det, 1.0), 0.0)
        s = o[:, None, :] - A[None, :, :]
        u = (s * pvec).sum(axis=2) * inv
        q = np.cross(s, E1[None, :, :])
        v = (q * d[:, None, :]).sum(axis=2) * inv
        t = (q * E2[None, :, :]).sum(axis=2) * inv
        hit = (
            good & (u >= -1e-9) & (u <= 1 + 1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9) & (t > near)
        )
        t = np.where(hit, t, np.inf)
        best = t.min(axis=1)
        out += [None if not math.isfinite(x) else float(x) for x in best]
    return out


def _first_hit_py(origin, direction, triangles, near):
    best = None
    for a, b, c in triangles:
        t = _ray_triangle(origin, direction, a, b, c)
        if t is not None and t > near and (best is None or t < best):
            best = t
    return best


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
