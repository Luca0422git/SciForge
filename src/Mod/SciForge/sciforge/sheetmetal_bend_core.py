# SPDX-License-Identifier: LGPL-2.1-or-later
"""The maths of SciForge's SHEET METAL forming tools Bend, Hem, Join by Bend, Corner Closure,
Lofted Flange and the sheet metal Fillet / Chamfer: pure Python (no FreeCAD, no Qt), unit
tested. The FreeCAD side (sheetmetal_bend.py, sheetmetal_hem.py, ...) turns these numbers into
solids.

Everything here works in a 2D cross-section: x across the sheet (outward from the edge or along
the bend's moving side), y through the thickness. A strip of sheet is described like a turtle
walk of its centre line: straight runs and arcs (each arc given by its INNER radius, the radius
of the sheet face on the inside of the turn, Fusion's Bend Radius). The outline of the strip (a
closed loop of lines and arcs, thickness T) is what the FreeCAD side extrudes along the edge.

Sources (docs/sciforge/dev/research/fusion-sheet-metal.md): bend allowance and the Bend Line
positions (2.3, 4.2), hem types and their values (2.4), bend positions (4.4), facet control
(2.2.4). Where Fusion's exact shape is unknown the choice is ours (G) and named in
docs/sciforge/parity/sheet-metal-more.md.
"""

import math

from .sheetmetal_core import bend_allowance

# -- Bend (Fusion's Fold) ------------------------------------------------------------------------
BEND_POSITIONS = ("start", "center", "end")
POSITION_LABELS = {"start": "Start", "center": "Center", "end": "End"}


def zone_start(position, allowance):
    """Where the bend zone starts, measured from the bend line toward the moving side, in the
    flat sheet. Start: the line is the zone's start (stationary side); Center: the line is the
    zone's centre line; End: the line is the zone's far end (Fusion's Bend Line position)."""
    if position not in BEND_POSITIONS:
        raise ValueError("Bend Line position must be Start, Center or End")
    return {"start": 0.0, "center": -allowance / 2.0, "end": -allowance}[position]


def bend_zone(position, angle_deg, inner_radius, thickness, k_factor):
    """(s0, s1): the bend zone in the flat sheet, from the bend line, toward the moving side."""
    ba = bend_allowance(angle_deg, inner_radius, thickness, k_factor)
    s0 = zone_start(position, ba)
    return s0, s0 + ba


def check_bend(angle_deg, inner_radius, thickness):
    """[] or the reasons the dialog shows."""
    problems = []
    if not 0.0 < angle_deg <= 180.0:
        problems.append("The bend angle must be more than 0° and at most 180°.")
    if inner_radius < 0:
        problems.append("The bend radius cannot be negative.")
    if thickness <= 0:
        problems.append("The sheet has no thickness.")
    return problems


# -- strips of sheet: a centre line walked like a turtle -----------------------------------------
def walk(segments, start=(0.0, 0.0), heading_deg=0.0, thickness=1.0):
    """Walk the centre line. segments: ("line", length) and ("arc", turn_deg, inner_radius)
    (turn > 0 turns left, counter-clockwise). Returns a list of pieces, each a dict:
      line: {"kind": "line", "a": (x, y), "b": (x, y), "heading": deg}
      arc:  {"kind": "arc", "center": (x, y), "radius": centre-line radius, "start": deg,
             "sweep": signed deg, "inner": inner radius, "heading": heading at its start}
    and the end state (x, y, heading)."""
    x, y = start
    heading = heading_deg
    pieces = []
    half = thickness / 2.0
    for seg in segments:
        if seg[0] == "line":
            length = float(seg[1])
            if length < -1e-9:
                raise ValueError("a straight run cannot be negative")
            h = math.radians(heading)
            bx, by = x + length * math.cos(h), y + length * math.sin(h)
            if length > 1e-9:
                pieces.append({"kind": "line", "a": (x, y), "b": (bx, by), "heading": heading})
            x, y = bx, by
        elif seg[0] == "arc":
            turn, inner = float(seg[1]), float(seg[2])
            if abs(turn) < 1e-9:
                continue
            if inner < -1e-9:
                raise ValueError("a bend radius cannot be negative")
            rc = inner + half
            h = math.radians(heading)
            left = (-math.sin(h), math.cos(h))
            side = 1.0 if turn > 0 else -1.0
            cx, cy = x + side * rc * left[0], y + side * rc * left[1]
            a0 = math.degrees(math.atan2(y - cy, x - cx))
            a1 = a0 + turn
            pieces.append(
                {
                    "kind": "arc",
                    "center": (cx, cy),
                    "radius": rc,
                    "start": a0,
                    "sweep": turn,
                    "inner": inner,
                    "heading": heading,
                }
            )
            x = cx + rc * math.cos(math.radians(a1))
            y = cy + rc * math.sin(math.radians(a1))
            heading += turn
        else:
            raise ValueError("unknown segment %r" % (seg[0],))
    return pieces, (x, y, heading)


def _offset_piece(piece, offset):
    """The piece moved `offset` to its left (negative: right). Lines: two points; arcs: the
    same centre, the radius changed (a left turn's left side is its inside)."""
    if piece["kind"] == "line":
        h = math.radians(piece["heading"])
        nx, ny = -math.sin(h) * offset, math.cos(h) * offset
        a, b = piece["a"], piece["b"]
        return {"kind": "line", "a": (a[0] + nx, a[1] + ny), "b": (b[0] + nx, b[1] + ny)}
    side = 1.0 if piece["sweep"] > 0 else -1.0
    radius = piece["radius"] - side * offset
    return {
        "kind": "arc",
        "center": piece["center"],
        "radius": radius,
        "start": piece["start"],
        "sweep": piece["sweep"],
    }


def arc_point(arc, fraction):
    ang = math.radians(arc["start"] + arc["sweep"] * fraction)
    return (
        arc["center"][0] + arc["radius"] * math.cos(ang),
        arc["center"][1] + arc["radius"] * math.sin(ang),
    )


def _ends(piece):
    if piece["kind"] == "line":
        return piece["a"], piece["b"]
    return arc_point(piece, 0.0), arc_point(piece, 1.0)


def _reverse(piece):
    if piece["kind"] == "line":
        return {"kind": "line", "a": piece["b"], "b": piece["a"]}
    out = dict(piece)
    out["start"] = piece["start"] + piece["sweep"]
    out["sweep"] = -piece["sweep"]
    return out


def outline(pieces, thickness):
    """The closed outline of a strip of thickness T along the walked centre line: the left
    side forward, an end cap, the right side backward, a start cap. A list of pieces ("line"
    a->b, "arc" centre/radius/start/sweep), each one's end the next one's start. Arcs whose
    side collapses to radius 0 (a fold with no inner radius) leave just their point."""
    half = thickness / 2.0
    left = [_offset_piece(p, half) for p in pieces]
    right = [_offset_piece(p, -half) for p in pieces]
    left = [p for p in left if p["kind"] == "line" or p["radius"] > 1e-9]
    right = [p for p in right if p["kind"] == "line" or p["radius"] > 1e-9]
    if not left or not right:
        raise ValueError("nothing to build")
    loop = list(left)
    loop.append({"kind": "line", "a": _ends(left[-1])[1], "b": _ends(right[-1])[1]})
    loop += [_reverse(p) for p in reversed(right)]
    loop.append({"kind": "line", "a": _ends(right[0])[0], "b": _ends(left[0])[0]})
    return loop


def strip_area(pieces, thickness):
    """Cross-section area of the strip (centre-line length x T: exact for lines and arcs)."""
    total = 0.0
    for p in pieces:
        if p["kind"] == "line":
            total += math.hypot(p["b"][0] - p["a"][0], p["b"][1] - p["a"][1])
        else:
            total += abs(math.radians(p["sweep"])) * p["radius"]
    return total * thickness


def neutral_length(pieces, thickness, k_factor):
    """Flat (developed) length of the strip: straight runs plus each arc's neutral layer
    (inner radius + K * T) times its angle (the flat pattern's length of this strip)."""
    total = 0.0
    for p in pieces:
        if p["kind"] == "line":
            total += math.hypot(p["b"][0] - p["a"][0], p["b"][1] - p["a"][1])
        else:
            total += abs(math.radians(p["sweep"])) * (p["inner"] + k_factor * thickness)
    return total


# -- Hem -------------------------------------------------------------------------------------------
HEM_TYPES = ("flat", "open", "rolled", "teardrop", "rope", "double")
HEM_LABELS = {
    "flat": "Flat",
    "open": "Open",
    "rolled": "Rolled",
    "teardrop": "Teardrop",
    "rope": "Rope",
    "double": "Double",
}
# The values each type uses (Fusion's HemFeatureInput set*Hem signatures).
HEM_VALUES = {
    "flat": ("length",),
    "open": ("length", "gap"),
    "rolled": ("radius", "angle"),
    "teardrop": ("radius", "length", "gap"),
    "rope": ("length", "gap", "radius"),
    "double": ("gap", "length", "setback"),
}
HEM_POSITIONS = ("inside", "outside", "adjacent", "tangent")
HEM_POSITION_LABELS = {
    "inside": "Inside",
    "outside": "Outside",
    "adjacent": "Adjacent",
    "tangent": "Tangent",
}
# A Flat hem is pressed shut. One solid cannot hold two layers touching face to face in
# OpenCASCADE (they would merge into one thick layer), so the layers keep this hairline gap.
FLAT_GAP = 0.01


def hem_defaults(thickness):
    """Starting values in mm for a sheet of this thickness (G: Fusion's are not published)."""
    t = thickness
    return {
        "type": "open",
        "length": 4.0 * t,
        "gap": 0.5 * t,
        "radius": 2.0 * t,
        "angle": 270.0,
        "setback": 0.0,
        "position": "inside",
        "flip": False,
        "miter": True,
    }


def hem_start(position, first_inner, thickness):
    """Where the hem's first fold starts (x of the fold's start tangent line), measured from
    the picked edge outward. The sheet is cut back to there. Inside / Tangent: the fold's
    outside stays at the edge (the part's size is kept); Outside: the fold's inside is at the
    edge; Adjacent: the fold starts at the edge (nothing cut)."""
    if position not in HEM_POSITIONS:
        raise ValueError("Bend Position must be Inside, Outside, Adjacent or Tangent")
    if position in ("inside", "tangent"):
        return -(first_inner + thickness)
    if position == "outside":
        return -first_inner
    return 0.0


def _solve(f, lo, hi, steps=80):
    """Bisection for f(x) = 0 on [lo, hi] (f(lo) and f(hi) of opposite signs)."""
    flo = f(lo)
    for _ in range(steps):
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        if (fm > 0) == (flo > 0):
            lo, flo = mid, fm
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _lowest_tip(pieces, end, thickness):
    """Lowest y of the strip's end cap (the tip of the hem's last run)."""
    _x, y, heading = end
    ny = math.cos(math.radians(heading)) * thickness / 2.0
    return min(y + ny, y - ny)


def hem_segments(values, thickness, rule_radius):
    """The hem's centre-line walk (after the sheet's cut-back end, heading outward, turning
    up = toward the hem side) and its outward extent. values: hem_defaults() keys, lengths in
    mm, angle in degrees. Raises ValueError with the reason a value does not work.

    Our shapes (G where Fusion's is unknown, docs/sciforge/parity/sheet-metal-more.md):
      Flat      180° fold pressed shut (hairline gap), a straight return of Length
      Open      180° fold with inner radius Gap/2, a straight return of Length
      Rolled    a roll of inner radius Radius through Angle
      Teardrop  a roll of inner radius Radius, then a straight run of Length that comes back
                down to Gap above the sheet
      Rope      a roll of inner radius Radius, a reverse bend of the rule radius, then a run of
                Length lying Gap above the sheet
      Double    a 180° fold (inner radius Gap/2), a return of Length, a second 180° fold the
                other way and a run back out that stops Setback short of the hem's outside
    Length is measured from the hem's outside (its outermost point) back over the sheet."""
    t = thickness
    kind = values.get("type", "open")
    if kind not in HEM_TYPES:
        raise ValueError("unknown hem type %r" % kind)
    length = float(values.get("length", 0.0))
    gap = float(values.get("gap", 0.0))
    radius = float(values.get("radius", 0.0))
    angle = float(values.get("angle", 0.0))
    setback = float(values.get("setback", 0.0))
    for key, val in (("Length", length), ("Gap", gap), ("Radius", radius), ("Setback", setback)):
        if key.lower() in HEM_VALUES[kind] and val < 0:
            raise ValueError("%s cannot be negative." % key)
    if kind in ("flat", "open", "double"):
        inner = FLAT_GAP / 2.0 if kind == "flat" else gap / 2.0
        if kind != "flat" and gap <= 0:
            raise ValueError("Gap must be more than 0 (a closed hem is the Flat type).")
        run = length - (inner + t)
        if run <= 1e-6:
            raise ValueError(
                "Length must be more than %.3g mm (the fold itself takes that much)." % (inner + t)
            )
        segs = [("arc", 180.0, inner), ("line", run)]
        if kind == "double":
            back = length - setback
            if back <= 1e-6:
                raise ValueError("Setback must be less than Length.")
            segs += [("arc", -180.0, inner), ("line", back)]
        return segs, inner
    if kind == "rolled":
        if radius <= 0:
            raise ValueError("Radius must be more than 0.")
        if not 0.0 < angle < 360.0:
            raise ValueError("Angle must be more than 0° and less than 360°.")
        if angle > 300.0 and radius < t:
            raise ValueError("A roll this far needs a Radius of at least the thickness.")
        return [("arc", angle, radius)], radius
    if kind == "teardrop":
        if radius <= 0:
            raise ValueError("Radius must be more than 0.")
        if length <= 0:
            raise ValueError("Length must be more than 0.")
        if gap >= 2.0 * radius:
            raise ValueError("Gap must be less than twice the Radius (the drop's width).")

        def low(phi):
            pieces, end = walk([("arc", phi, radius), ("line", length)], (0.0, -t / 2.0), 0.0, t)
            return _lowest_tip(pieces, end, t) - gap

        lo, hi = 180.0, 330.0
        if low(hi) > 0:
            raise ValueError("Length is too short to come back down to the Gap; make it longer.")
        phi = _solve(low, lo, hi)
        return [("arc", phi, radius), ("line", length)], radius
    # rope
    if radius <= 0:
        raise ValueError("Radius must be more than 0.")
    if length <= 0:
        raise ValueError("Length must be more than 0.")
    if gap >= 2.0 * radius:
        raise ValueError("Gap must be less than twice the Radius (the rope's size).")
    r2 = max(rule_radius, 0.0)

    def lower(phi):
        _p, end = walk([("arc", phi, radius), ("arc", -(phi - 180.0), r2)], (0.0, -t / 2.0), 0.0, t)
        return end[1] - t / 2.0 - gap

    if lower(300.0) > 0:
        raise ValueError("The Radius is too small for this Gap; make the Radius larger.")
    phi = _solve(lower, 180.0, 300.0)
    return [("arc", phi, radius), ("arc", -(phi - 180.0), r2), ("line", length)], radius


def hem_profile(values, thickness, rule_radius):
    """(pieces, start_x, first_inner): the hem's centre-line pieces in the edge's cross-section
    (x outward from the picked edge, y up from the picked face: the sheet is y in [-T, 0]) and
    where the sheet is cut back to."""
    segs, inner = hem_segments(values, thickness, rule_radius)
    x0 = hem_start(values.get("position", "inside"), inner, thickness)
    pieces, _end = walk(segs, (x0, -thickness / 2.0), 0.0, thickness)
    return pieces, x0, inner


# -- Join by Bend ----------------------------------------------------------------------------------
def fillet_2d(point, dir_a, dir_b, mid_radius):
    """A bend joining two straight runs that meet at `point`, run a going away along dir_a
    and run b along dir_b (unit 2D vectors): the arc of centre-line radius mid_radius tangent
    to both. Returns (tangent_a, tangent_b, centre, bend_deg). Raises ValueError when the runs
    are parallel (no bend joins them)."""
    ax, ay = dir_a
    bx, by = dir_b
    cos_alpha = max(-1.0, min(1.0, ax * bx + ay * by))
    alpha = math.acos(cos_alpha)  # angle between the two runs at their meeting point
    if alpha < 1e-6 or math.pi - alpha < 1e-6:
        raise ValueError("The two sheets are parallel: no bend can join them.")
    reach = mid_radius / math.tan(alpha / 2.0)
    ta = (point[0] + ax * reach, point[1] + ay * reach)
    tb = (point[0] + bx * reach, point[1] + by * reach)
    sx, sy = ax + bx, ay + by
    norm = math.hypot(sx, sy)
    dist = mid_radius / math.sin(alpha / 2.0)
    centre = (point[0] + sx / norm * dist, point[1] + sy / norm * dist)
    return ta, tb, centre, 180.0 - math.degrees(alpha)


def line_intersection(p, u, q, v):
    """Where the 2D lines p + s u and q + t v meet: (s, t), or None when parallel."""
    det = u[0] * (-v[1]) - u[1] * (-v[0])
    if abs(det) < 1e-12:
        return None
    rx, ry = q[0] - p[0], q[1] - p[1]
    s = (rx * (-v[1]) - ry * (-v[0])) / det
    t = (u[0] * ry - u[1] * rx) / det
    return s, t


# -- Corner Closure --------------------------------------------------------------------------------
CLOSURE_ALIGNMENTS = ("symmetric", "overlap")
CLOSURE_LABELS = {"symmetric": "Symmetric Gap", "overlap": "Overlap"}
CLOSURE_RELIEFS = ("round", "square", "tear", "trim_to_bend")
CLOSURE_RELIEF_LABELS = {
    "round": "Round",
    "square": "Square",
    "tear": "Tear",
    "trim_to_bend": "Trim To Bend",
}
CLOSURE_PLACEMENTS = ("intersection", "tangent", "vertex")
CLOSURE_PLACEMENT_LABELS = {
    "intersection": "Intersection",
    "tangent": "Tangent",
    "vertex": "Vertex",
}


def relief_centre(placement, bend_a, bend_b, size, shape="round"):
    """Where a 2-bend corner relief is centred in the flat state (2D).

    Each bend is (point, direction, outward, half_width): a point on its centre line, the
    line's direction, the unit vector across the bend from the stationary side toward the
    flange, and half the bend zone's width (half the bend allowance).

    * intersection: where the two centre lines cross;
    * vertex: where the bends start on the stationary side (the inner corner);
    * tangent (Round only): the circle (diameter `size`) touches the far side of both bend
      zones, so it clears their whole crossing.
    Raises ValueError with the reason."""
    if placement not in CLOSURE_PLACEMENTS:
        raise ValueError("Relief Placement must be Intersection, Tangent or Vertex.")
    if placement == "tangent" and shape != "round":
        raise ValueError(
            "Tangent placement is for a Round relief only; use Intersection or Vertex."
        )
    offsets = []
    for _point, _direction, _outward, half in (bend_a, bend_b):
        if placement == "intersection":
            offsets.append(0.0)
        elif placement == "vertex":
            offsets.append(-half)
        else:
            offsets.append(half - size / 2.0)
    return _offset_meet(bend_a, offsets[0], bend_b, offsets[1])


def _offset_meet(bend_a, off_a, bend_b, off_b):
    """Where bend_a's centre line moved off_a across it meets bend_b's moved off_b (2D)."""
    lines = []
    for (point, direction, outward, _half), offset in ((bend_a, off_a), (bend_b, off_b)):
        lines.append(((point[0] + outward[0] * offset, point[1] + outward[1] * offset), direction))
    (p, u), (q, v) = lines
    meet = line_intersection(p, u, q, v)
    if meet is None:
        raise ValueError("The two bends are parallel: they do not meet at a corner.")
    return (p[0] + u[0] * meet[0], p[1] + u[1] * meet[0])


def closure_reach(alignment, gap, thickness, overlap=1.0, dominant=True):
    """How far each flange end is taken toward the other flange's plane, as an offset from
    the corner where the two walls' outside faces meet (positive: short of it). Symmetric
    Gap: both stop gap/2 short of the bisector (returned as a bisector offset, see the FreeCAD
    side). Overlap: the dominant flange runs over the other one's end (to its outside face,
    less (1 - overlap) of the thickness); the submissive stops at the dominant's inside face
    plus the gap."""
    if alignment not in CLOSURE_ALIGNMENTS:
        raise ValueError("Alignment must be Symmetric Gap or Overlap")
    if gap < 0:
        raise ValueError("The gap cannot be negative.")
    if alignment == "symmetric":
        return gap / 2.0
    if not 0.0 <= overlap <= 1.0:
        raise ValueError("Overlap must be between 0 and 1.")
    if dominant:
        return (1.0 - overlap) * thickness
    return thickness + gap


# -- Lofted Flange (Brake Form facets) -------------------------------------------------------------
FORMING_TYPES = ("brake", "die")
FORMING_LABELS = {"brake": "Brake Form", "die": "Die Form"}
FACET_CONTROLS = ("chord_tolerance", "facet_angle", "facet_distance", "facet_number")
FACET_LABELS = {
    "chord_tolerance": "Chord Tolerance",
    "facet_angle": "Facet Angle",
    "facet_distance": "Facet Distance",
    "facet_number": "Face Number",
}
FACET_DEFAULTS = {
    "chord_tolerance": 0.1,
    "facet_angle": 10.0,
    "facet_distance": 5.0,
    "facet_number": 6,
}


def facets_for_arc(radius, sweep_deg, control, value):
    """How many straight facets replace an arc of this radius and sweep (Brake Form): the
    fewest that keep the chord within the tolerance / the angle per facet / the facet width,
    or the number asked for. At least one."""
    sweep = abs(math.radians(sweep_deg))
    if sweep < 1e-9 or radius <= 0:
        return 1
    if control == "facet_number":
        return max(1, int(round(value)))
    if control == "facet_angle":
        if value <= 0:
            raise ValueError("Facet Angle must be more than 0.")
        # the angle between a chord and the curve's tangent is half the chord's sweep
        return max(1, int(math.ceil(sweep / (2.0 * math.radians(value)) - 1e-9)))
    if control == "facet_distance":
        if value <= 0:
            raise ValueError("Facet Distance must be more than 0.")
        chord = lambda n: 2.0 * radius * math.sin(sweep / (2.0 * n))  # noqa: E731
        n = 1
        while chord(n) > value + 1e-9 and n < 720:
            n += 1
        return n
    if control == "chord_tolerance":
        if value <= 0:
            raise ValueError("Chord Tolerance must be more than 0.")
        if value >= radius:
            return 1
        # sagitta of a chord sweeping a: r (1 - cos(a/2)) <= tol
        per = 2.0 * math.acos(1.0 - value / radius)
        return max(1, int(math.ceil(sweep / per - 1e-9)))
    raise ValueError("unknown facet control %r" % control)


def triangulate(t1, t2, closed):
    """Triangles between two point lists placed at t1, t2 (0..1: their share of a turn or of
    the length; closed lists without the repeated first point), walking both. Each corner
    of one profile fans out to the stretch of the other that faces it (a square to a
    circle: a fan of facets at each corner, one facet along each side), as a press-brake
    transition is laid out. Index triples into
    list1 + list2 (list2's indices shifted by len(t1))."""
    n1, n2 = len(t1), len(t2)
    tris = []
    i = j = 0
    end1 = n1 if closed else n1 - 1
    end2 = n2 if closed else n2 - 1

    def next_t(ts, k, n):
        return ts[k + 1] if k + 1 < n else 1.0

    while i < end1 or j < end2:
        if i >= end1:
            move_b = True
        elif j >= end2:
            move_b = False
        else:
            # the other profile's points up to the middle of this segment fan out from
            # this point: each corner's fan is centred on it, each side's facet meets the
            # point facing the side's middle
            move_b = next_t(t2, j, n2) <= 0.5 * (t1[i] + next_t(t1, i, n1)) + 1e-12
        if move_b:
            tris.append((i % n1, n1 + (j + 1) % n2, n1 + j % n2))
            j += 1
        else:
            tris.append((i % n1, (i + 1) % n1, n1 + j % n2))
            i += 1
    return tris


# -- sheet metal Fillet / Chamfer ----------------------------------------------------------------
def is_thickness_edge(edge_dir, face_normal, length, thickness, tol=1e-3):
    """True for an edge that runs straight through the sheet: parallel to the sheet's normal
    and as long as the thickness (Fusion lets only these be rounded or chamfered)."""
    dot = abs(sum(a * b for a, b in zip(edge_dir, face_normal)))
    return dot > 1.0 - 1e-6 and abs(length - thickness) <= max(tol, 1e-3 * thickness)
