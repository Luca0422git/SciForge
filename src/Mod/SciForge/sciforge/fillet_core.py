# SPDX-License-Identifier: LGPL-2.1-or-later
"""The maths of Fusion's Fillet / Chamfer options that one PartDesign feature cannot hold:
radius sets, Chord Length, Variable radius, Rule Fillet's choice of edges, Full Round,
chamfer sets. No FreeCAD, no Qt (unit tested: SciForgeTests/unit/test_fillet_core.py);
fillet_sets.py builds the geometry, fillet_ui.py is the dialog.

The step's settings ("spec") are a plain dict, saved as JSON on the step:

  kind          "fillet" | "chamfer"
  mode          "fillet" | "rule" | "full_round"      (Fusion's Type; chamfer: "fillet")
  corner        "rolling_ball" (fillet) | "chamfer" (chamfer)
  sets          one dict per row of Fusion's selection box (its "+" adds one):
      fillet     {"count", "radius_type": constant|chord|variable, "radius", "chord",
                  "start", "end", "points": [[position 0..1, radius], ...],
                  "tangent_chain": True: edges tangent to a picked edge are rounded with
                  it (Fusion's default; a setting of each set, as in Fusion's API)}
      chamfer    {"count", "chamfer_type": equal|two|angle, "distance", "distance2",
                  "angle", "flip"}
      full_round {"count": 3}  (side face, centre face, side face)
                 "count" is how many of the step's picks (in order) belong to the set.
  rule          "all" | "between"   (Rule Fillet: every edge of the faces / features in
                the first box, or only the edges shared by the two boxes)
  rounds        Rule Fillet rounds outside (convex) edges
  fillets       Rule Fillet fills inside (concave) edges
  radius        Rule Fillet's radius
"""

import json
import math

KINDS = ("fillet", "chamfer")
MODES = (
    ("fillet", "Fillet"),
    ("rule", "Rule Fillet"),
    ("full_round", "Full Round Fillet"),
)
RADIUS_TYPES = (
    ("constant", "Constant"),
    ("chord", "Chord Length"),
    ("variable", "Variable"),
)
RULES = (("all", "All Edges"), ("between", "Between Faces/Features"))
CHAMFER_TYPES = ("equal", "two", "angle")
TINY = 1e-9
POINT_GAP = 1e-3  # two radius points closer than this (of the edge's length) are one point


class SetError(ValueError):
    """The settings cannot make a fillet / chamfer; the message says why and what to do."""


# -- Chord Length -----------------------------------------------------------------------------
def chord_radius(chord, turn):
    """The radius of the round whose chord is `chord` on an edge where the faces' normals turn
    by `turn` (radians: 90 degrees on a box edge, 60 on a hexagon's).

    A round is an arc tangent to both faces; it turns by the same angle as the normals, so its
    chord (the straight distance between the two lines where it meets the faces, Fusion's
    "Chord Length") is 2 R sin(turn / 2)."""
    chord = float(chord)
    if chord <= 0:
        raise SetError("The chord length must be more than 0 mm.")
    half = math.sin(float(turn) / 2.0)
    if half < 1e-6:
        raise SetError("The faces at this edge are tangent: there is nothing to round.")
    return chord / (2.0 * half)


def radius_chord(radius, turn):
    """The chord of a round of `radius` (inverse of chord_radius)."""
    return 2.0 * float(radius) * math.sin(float(turn) / 2.0)


# -- Variable radius --------------------------------------------------------------------------
def variable_points(start, end, mids=()):
    """[(position, radius), ...] from 0 (the start of the edge) to 1 (its end), the points in
    between sorted by position (Fusion sorts them from start to end whatever order they were
    added in). Raises SetError for a radius of 0 or less, a position outside 0..1, or two
    points on one spot."""
    points = [(0.0, float(start))]
    inner = sorted((float(p), float(r)) for p, r in (mids or ()))
    for position, radius in inner:
        if not 0.0 < position < 1.0:
            raise SetError(
                "A radius point's position must be between 0 (start) and 1 (end); "
                "%g is not." % position
            )
        if position - points[-1][0] < POINT_GAP:
            raise SetError(
                "Two radius points are at the same place (position %g). Move or remove one."
                % position
            )
        points.append((position, radius))
    if 1.0 - points[-1][0] < POINT_GAP:
        raise SetError("A radius point sits on the end of the edge. Move it or remove it.")
    points.append((1.0, float(end)))
    for position, radius in points:
        if radius <= 0:
            if position == 0.0:
                where = "start radius"
            elif position == 1.0:
                where = "end radius"
            else:
                where = "radius at position %g" % position
            raise SetError("The %s must be more than 0 mm." % where)
    return points


def law(points, position):
    """The radius at `position` (0..1), straight between the points (the kernel then rounds
    the law off smoothly through them)."""
    position = min(1.0, max(0.0, float(position)))
    for (p0, r0), (p1, r1) in zip(points, points[1:]):
        if position <= p1 + TINY:
            if p1 - p0 < TINY:
                return r1
            return r0 + (r1 - r0) * (position - p0) / (p1 - p0)
    return points[-1][1]


def split_plan(lengths, points):
    """How a chain of edges (lengths in order from the chain's start) is cut so every radius
    point lies on a corner between two pieces, and the radius of each piece at its two ends.

    Returns (cuts, pieces):
      cuts    [(edge index, fraction along that edge from its chain-start end)] for each
              point in between that is not already on a corner of the chain;
      pieces  [(edge index, s0, s1, r0, r1)] in chain order: each piece of an edge, its
              start / end position on the chain (0..1) and the radius there."""
    total = float(sum(lengths))
    if total <= TINY:
        raise SetError("The edge has no length.")
    bounds = [0.0]
    for length in lengths:
        bounds.append(bounds[-1] + float(length) / total)
    bounds[-1] = 1.0
    cuts = []
    pieces = []
    for index in range(len(lengths)):
        a, b = bounds[index], bounds[index + 1]
        span = b - a
        marks = [a]
        for position, _radius in points[1:-1]:
            if a + POINT_GAP * 0.5 < position < b - POINT_GAP * 0.5:
                cuts.append((index, (position - a) / span if span > TINY else 0.0))
                marks.append(position)
        marks.append(b)
        for s0, s1 in zip(marks, marks[1:]):
            pieces.append((index, s0, s1, law(points, s0), law(points, s1)))
    return cuts, pieces


# -- Rule Fillet --------------------------------------------------------------------------------
def rule_keeps(convex, rounds=True, fillets=True):
    """Rule Fillet's Rounds / Fillets: rounds are outside (convex) edges, fillets inside
    (concave) ones."""
    return bool(rounds) if convex else bool(fillets)


def shared_edges(first, second):
    """Edge names in both lists (Between Faces/Features), in the first list's order."""
    other = set(second)
    out = []
    for name in first:
        if name in other and name not in out:
            out.append(name)
    return out


# -- Chamfer Distance and Angle as two distances --------------------------------------------
def angle_distance2(distance, angle, gamma):
    """The distance on the other face of a Distance and Angle chamfer: the bevel leaves the
    measured face at `angle` (degrees) and meets the other face, which makes the corner's
    angle `gamma` (radians, 90 degrees on a box edge) with it. In the triangle of the edge
    and the two lines the bevel ends on (law of sines): d2 = d1 sin(a) / sin(gamma + a)."""
    a = math.radians(float(angle))
    if not 0.0 < a < math.pi:
        raise SetError("The angle must be between 0° and 180°.")
    if a + float(gamma) >= math.pi - 1e-9:
        raise SetError(
            "At %g° the bevel never reaches the face on the other side of the edge. "
            "Use an angle below %g° here."
            % (float(angle), round(180.0 - math.degrees(float(gamma)), 2))
        )
    return float(distance) * math.sin(a) / math.sin(float(gamma) + a)


# -- Full Round ------------------------------------------------------------------------------
def full_round_radius(width):
    """A full round between two parallel side faces `width` apart is a half circle."""
    if width <= TINY:
        raise SetError("The side faces touch: there is no centre face to round.")
    return float(width) / 2.0


# -- the settings ------------------------------------------------------------------------------
def new_set(kind="fillet", mode="fillet", like=None):
    """A new row of the selection box: Fusion gives it the values of the row before."""
    if kind == "chamfer":
        row = {
            "count": 0,
            "chamfer_type": "equal",
            "distance": 1.0,
            "distance2": 1.0,
            "angle": 45.0,
            "flip": False,
        }
    elif mode == "full_round":
        row = {"count": 0}
    else:
        row = {
            "count": 0,
            "radius_type": "constant",
            "radius": 1.0,
            "chord": 1.0,
            "start": 1.0,
            "end": 1.0,
            "points": [],
            "tangent_chain": True,
        }
    if like:
        for key, value in like.items():
            if key in row and key not in ("count", "points"):
                row[key] = value
    return row


def default_spec(kind="fillet"):
    return {
        "kind": kind,
        "mode": "fillet",
        "corner": "chamfer" if kind == "chamfer" else "rolling_ball",
        "sets": [new_set(kind)],
        "rule": "all",
        "rounds": True,
        "fillets": True,
        "radius": 1.0,
    }


def check_spec(spec):
    """Raise SetError when the settings are not usable (unknown names, counts that do not add
    up to the picks): a hand-edited or damaged file, never the dialog's own settings."""
    kind = spec.get("kind")
    if kind not in KINDS:
        raise SetError("Unknown blend %r." % (kind,))
    mode = spec.get("mode", "fillet")
    if mode not in [m for m, _l in MODES]:
        raise SetError("Unknown fillet type %r." % (mode,))
    if kind == "chamfer" and mode != "fillet":
        raise SetError("A chamfer has no %s." % dict(MODES)[mode])
    if spec.get("rule", "all") not in [r for r, _l in RULES]:
        raise SetError("Unknown rule %r." % (spec.get("rule"),))
    for row in spec.get("sets", []):
        if int(row.get("count", 0)) < 0:
            raise SetError("A selection set has a negative number of picks.")
        if kind == "chamfer":
            if row.get("chamfer_type", "equal") not in CHAMFER_TYPES:
                raise SetError("Unknown chamfer type %r." % (row.get("chamfer_type"),))
        elif mode == "fillet":
            if row.get("radius_type", "constant") not in [t for t, _l in RADIUS_TYPES]:
                raise SetError("Unknown radius type %r." % (row.get("radius_type"),))
    return spec


def split_refs(spec, refs):
    """The step's picks (one flat list, saved in one link) cut into the rows: [[refs], ...]."""
    out, at = [], 0
    for row in spec.get("sets", []):
        count = max(0, int(row.get("count", 0)))
        out.append(list(refs[at : at + count]))
        at += count
    return out


def join_refs(groups):
    """The rows' picks as one flat list plus each row's count (the inverse of split_refs)."""
    flat, counts = [], []
    for group in groups:
        flat.extend(group)
        counts.append(len(group))
    return flat, counts


def needs_step(spec, groups=None):
    """True when the settings need SciForge's own fillet step: FreeCAD's Fillet / Chamfer
    holds one constant size for every picked edge (one row, Tangent Chain on)."""
    if spec.get("kind") == "chamfer":
        if groups is not None:
            return len([g for g in groups if g]) > 1
        return len(spec.get("sets", [])) > 1
    if spec.get("mode", "fillet") != "fillet":
        return True
    rows = spec.get("sets", [])
    if groups is not None:
        rows = [row for row, group in zip(rows, groups) if group]
    if len(rows) > 1:
        return True
    return any(
        row.get("radius_type", "constant") != "constant" or not row.get("tangent_chain", True)
        for row in rows
    )


def dumps(spec):
    return json.dumps(spec, sort_keys=True)


def loads(text, kind="fillet"):
    """The settings saved on a step (defaults filled in for keys an older SciForge did not
    write)."""
    spec = default_spec(kind)
    try:
        data = json.loads(text or "{}")
    except Exception:
        data = {}
    if isinstance(data, dict):
        spec.update(data)
    rows = []
    for row in spec.get("sets") or []:
        merged = new_set(spec.get("kind", kind), spec.get("mode", "fillet"))
        merged.update(row if isinstance(row, dict) else {})
        rows.append(merged)
    spec["sets"] = rows
    return spec
