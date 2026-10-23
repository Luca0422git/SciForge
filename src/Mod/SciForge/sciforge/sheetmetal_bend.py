# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's SHEET METAL > CREATE > Bend (the API's Fold): bend a flat sheet metal body along
sketch lines. FreeCAD side, no Qt: the dialog (sheetmetal_bend_ui.py) and the golden-model
builder (ai/ops/sheetmetal_ops.py) both call make() / update().

How a bend is built (the body is reshaped, nothing is added; sources in
docs/sciforge/dev/research/fusion-sheet-metal.md 2.3 and 4.2):

* The Stationary Side is a top or bottom face of the sheet; the side of the bend line where
  the face was clicked stays where it is (Fusion: the stationary side).
* In the flat sheet, the bend zone is a strip as wide as the bend allowance
  BA = angle * (R + K * T), placed against the line by Bend Line position Start / Center / End.
* The sheet beyond the zone moves back by BA and swings round the bend's axis by the angle.
* The zone itself is laid on the bend's cylinders: each point keeps its distance along the
  bend's axis and goes round by (distance into the zone) / (R + K * T). The zone's outline is
  mapped onto the cylinder exactly (a straight line maps to a straight line in the cylinder's
  (angle, height) parameters), so holes and slots in the zone come through, bent.
* The result is flat walls and cylindrical bends of the rule's thickness and inner radius
  (what the flat pattern unfolds).

Several bend lines are bent farthest from the stationary side first (Fusion asks the user to
pick them in that order; SciForge sorts them).

Also here: the helpers the other forming tools share (frames, strips of sheet, edge analysis).
"""

import FreeCAD as App

from . import bodies, log, sheetmetal, sheetmetal_bend_core as core

V = App.Vector
TYPE = "PartDesign::FeaturePython"
KIND = "SheetMetalBend"
POSITIONS = ["Start", "Center", "End"]
TOL = 1e-6


class SheetMetalError(ValueError):
    """The step cannot be built as asked; the message says why and what to try."""


# -- shared geometry helpers ------------------------------------------------------------------
def unit(vec):
    vec = V(vec)
    length = vec.Length
    if length < 1e-12:
        raise SheetMetalError("a direction of zero length")
    return vec * (1.0 / length)


def frame_box(origin, xdir, ydir, zdir, x0, x1, y0, y1, z0, z1):
    """A box given in the frame (origin, xdir, ydir, zdir): x in [x0, x1] ... (design units)."""
    import Part

    if xdir.cross(ydir).dot(zdir) < 0:  # keep the frame right-handed (a mirrored box is
        zdir, z0, z1 = zdir * -1.0, -z1, -z0  # inside out)
    corner = origin + xdir * x0 + ydir * y0 + zdir * z0
    m = App.Matrix(
        xdir.x, ydir.x, zdir.x, 0, xdir.y, ydir.y, zdir.y, 0, xdir.z, ydir.z, zdir.z, 0, 0, 0, 0, 1
    )
    box = Part.makeBox(x1 - x0, y1 - y0, z1 - z0)
    box.transformShape(m, True)
    box.translate(corner)
    return box


def plane_normal(face):
    u0, u1, v0, v1 = face.ParameterRange
    return unit(face.normalAt(0.5 * (u0 + u1), 0.5 * (v0 + v1)))


def is_plane(face):
    try:
        return face.Surface.TypeId == "Part::GeomPlane"
    except Exception:
        return False


def outline_wire(loop, origin, xdir, ydir):
    """A closed wire from sheetmetal_bend_core.outline() pieces, in the plane of the frame."""
    import Part

    def at(p):
        return origin + xdir * p[0] + ydir * p[1]

    edges = []
    for piece in loop:
        if piece["kind"] == "line":
            a, b = at(piece["a"]), at(piece["b"])
            if (b - a).Length > 1e-9:
                edges.append(Part.LineSegment(a, b).toShape())
        else:
            p0 = at(core.arc_point(piece, 0.0))
            p1 = at(core.arc_point(piece, 0.5))
            p2 = at(core.arc_point(piece, 1.0))
            if abs(piece["sweep"]) >= 359.999:
                raise SheetMetalError("a full circle in a strip")
            edges.append(Part.Arc(p0, p1, p2).toShape())
    wire = Part.Wire(Part.__sortEdges__(edges))
    if not wire.isClosed():
        raise SheetMetalError("the strip's outline does not close")
    return wire


def strip_solid(pieces, thickness, origin, xdir, ydir, along):
    """The strip of sheet walked by `pieces` (core.walk) in the plane (origin, xdir, ydir),
    pulled along the vector `along` (the edge's direction and length)."""
    import Part

    loop = core.outline(pieces, thickness)
    face = Part.Face(outline_wire(loop, origin, xdir, ydir))
    solid = face.extrude(along)
    if solid.Volume < 0:
        solid.reverse()
    return solid


def fuse_all(base, others, refine=True):
    """base fused with others (a fuzzy fuse: their touching faces meet within 1e-5 mm)."""
    shapes = [s for s in others if s is not None and not s.isNull() and s.Volume > 1e-9]
    if not shapes:
        out = base
    else:
        out = base.fuse(shapes, 1e-5)
    if refine:
        try:
            out = out.removeSplitter()
        except Exception:
            pass
    return out


def one_solid(shape, what):
    """The shape's single solid, or a SheetMetalError naming `what` went wrong."""
    solids = list(shape.Solids) if not shape.isNull() else []
    if len(solids) != 1:
        raise SheetMetalError(
            "%s would split the body into %d pieces; check where it is placed."
            % (what, len(solids))
        )
    solid = solids[0]
    if not solid.isValid():
        try:
            solid.fix(1e-6, 1e-6, 1e-4)
        except Exception:
            pass
    if not solid.isValid():
        raise SheetMetalError("%s gives a broken solid here; try other values." % what)
    return solid


def rule_values(body, override_radius=None):
    """(thickness, inner bend radius, K-factor, rule dict) of a sheet metal body."""
    if body is None or not sheetmetal.is_sheet_metal_body(body):
        raise SheetMetalError(
            "This body is not sheet metal. Make it with Flange (SHEET METAL tab) or Convert to "
            "Sheet Metal first."
        )
    rule = sheetmetal.rule_for_body(body)
    radius = rule["bend_radius"] if override_radius is None else float(override_radius)
    return float(rule["thickness"]), float(radius), float(rule["k_factor"]), rule


def face_thickness(shape, face, thickness, tol=1e-3):
    """True when a planar face of the solid has a parallel face T away behind it (it is a top
    or bottom face of the sheet)."""
    n = plane_normal(face)
    p = face.CenterOfMass
    for other in shape.Faces:
        if other.isSame(face) or not is_plane(other):
            continue
        m = plane_normal(other)
        if m.dot(n) > -1.0 + 1e-6:
            continue
        if abs((p - other.CenterOfMass).dot(n) - thickness) < tol:
            return True
    return False


# -- edges of a sheet (Hem, Join by Bend, Corner Closure) -----------------------------------
def edge_frame(shape, edge_name, thickness, tol=1e-3):
    """What a picked edge of a sheet is: a straight edge where a top / bottom face (the
    'big' face) meets a side face as wide as the thickness. Returns a dict:
      edge, start, end, dir (unit, start -> end), length,
      top (the big face), top_name, normal (the big face's outward normal),
      side, side_name, out (the side face's outward normal)
    Raises SheetMetalError with the reason the edge cannot be used."""
    import Part

    try:
        edge = shape.getElement(edge_name)
    except Exception:
        raise SheetMetalError("%s is not an edge of the body any more." % edge_name)
    if not isinstance(edge.Curve, (Part.Line, Part.LineSegment)):
        raise SheetMetalError("Pick a straight edge (curved edges cannot be used here).")
    faces = shape.ancestorsOfType(edge, Part.Face)
    planar = [f for f in faces if is_plane(f)]
    if len(planar) != 2:
        raise SheetMetalError("Pick an edge between a top or bottom face and a side face.")
    a, b = planar
    na, nb = plane_normal(a), plane_normal(b)
    if abs(na.dot(nb)) > 1e-4:
        raise SheetMetalError("Pick an edge where the sheet's face meets its side at 90°.")

    def extent(face, direction):
        vals = [v.Point.dot(direction) for v in face.Vertexes]
        return max(vals) - min(vals)

    a_side = abs(extent(a, nb) - thickness) < tol
    b_side = abs(extent(b, na) - thickness) < tol
    if a_side and b_side:
        top, side = (a, b) if a.Area >= b.Area else (b, a)
    elif b_side:
        top, side = a, b
    elif a_side:
        top, side = b, a
    else:
        raise SheetMetalError(
            "That edge is not on a side as thick as the sheet (%.3g mm); pick an edge of the "
            "sheet's outline." % thickness
        )
    start = edge.Vertexes[0].Point
    end = edge.Vertexes[-1].Point
    names = {}
    for i, f in enumerate(shape.Faces, start=1):
        if f.isSame(top):
            names["top"] = "Face%d" % i
        elif f.isSame(side):
            names["side"] = "Face%d" % i
    return {
        "edge": edge,
        "start": start,
        "end": end,
        "dir": unit(end - start),
        "length": (end - start).Length,
        "top": top,
        "top_name": names.get("top", ""),
        "normal": plane_normal(top),
        "side": side,
        "side_name": names.get("side", ""),
        "out": plane_normal(side),
    }


# -- Bend ------------------------------------------------------------------------------------------
def default_options():
    return {
        "angle": 90.0,
        "position": "center",
        "flip": False,
        "bend_relief": True,
        "corner_relief": True,
        "override_radius": False,
        "radius": None,
    }


def _project(point, origin, normal):
    return point - normal * (point - origin).dot(normal)


def bend_lines_on(face, lines):
    """The bend lines [(a, b)] projected into the stationary face's plane. Lines that are not
    parallel to the face are refused (Fusion: they must lie in a plane parallel to it)."""
    n = plane_normal(face)
    origin = face.Vertexes[0].Point
    out = []
    for line in lines:
        a, b = line[0], line[1]
        extra = line[2] if len(line) > 2 else {}
        d = b - a
        if d.Length < 1e-6:
            raise SheetMetalError("A bend line has no length.")
        if abs(unit(d).dot(n)) > 1e-4:
            raise SheetMetalError(
                "A bend line is not parallel to the stationary face; sketch the bend lines on "
                "that face."
            )
        out.append((_project(a, origin, n), _project(b, origin, n), extra))
    return out


def _zone_faces(zone, plane_point, normal):
    """The zone's faces lying in the stationary face's plane."""
    found = []
    for face in zone.Faces:
        if not is_plane(face):
            continue
        if abs(abs(plane_normal(face).dot(normal)) - 1.0) > 1e-6:
            continue
        if abs((face.CenterOfMass - plane_point).dot(normal)) < 1e-5:
            found.append(face)
    return found


def _map_edge(edge, to_uv, surface):
    """The edge of a flat face drawn on the cylinder: straight lines exactly, curves through
    points (a straight line in the flat zone is a straight line in the cylinder's (angle,
    height) parameters, because the development is linear)."""
    import Part
    from FreeCAD import Base

    if isinstance(edge.Curve, (Part.Line, Part.LineSegment)):
        a = to_uv(edge.Vertexes[0].Point)
        b = to_uv(edge.Vertexes[-1].Point)
        return Part.Geom2d.Line2dSegment(Base.Vector2d(*a), Base.Vector2d(*b)).toShape(surface)
    count = max(24, int(edge.Length / 0.5))
    count = min(count, 80)
    pts = edge.discretize(count)
    uv = [Base.Vector2d(*to_uv(p)) for p in pts]
    closed = edge.isClosed()
    if closed:
        uv = uv[:-1]
    curve = Part.Geom2d.BSplineCurve2d()
    curve.interpolate(uv, PeriodicFlag=closed)
    return curve.toShape(surface)


def _bend_zone_solid(
    zone_faces, origin, along, across, normal, s0, s1, axis_pt, top_radius, thickness, rn, up, angle
):
    """The zone laid onto the bend's cylinders: the full-width slab revolved round the bend's
    axis (exact planes and cylinders), less the parts of the slab that are not sheet (holes,
    notches, a slanted outline), each mapped onto the cylinders and cut away."""
    import Part

    # exact ends of the zone's material along the axis (vertices may miss a curved outline)
    lo, hi = [], []
    for face in zone_faces:
        for edge in face.Edges:
            for p in edge.discretize(24):
                lo.append((p - origin).dot(along))
                hi.append((p - origin).dot(along))
    a0, a1 = min(lo), max(hi)
    top = origin + across * s0
    corners = [
        top + along * a0,
        top + along * a1,
        top + along * a1 - normal * thickness,
        top + along * a0 - normal * thickness,
    ]
    section = Part.Face(Part.makePolygon(corners + [corners[0]]))
    slab = section.revolve(axis_pt, along, angle if up else -angle)
    if slab.ShapeType != "Solid":
        slab = Part.Solid(Part.Shell(slab.Faces)) if slab.Faces else slab
    if slab.Volume < 0:
        slab.reverse()
    # what of the flat slab is not sheet: mapped onto the bend and cut away
    rect = Part.Face(
        Part.makePolygon(
            [
                origin + across * s0 + along * a0,
                origin + across * s1 + along * a0,
                origin + across * s1 + along * a1,
                origin + across * s0 + along * a1,
                origin + across * s0 + along * a0,
            ]
        )
    )
    missing = rect.cut(Part.makeCompound(zone_faces)) if zone_faces else rect
    pieces = [f for f in missing.Faces if f.Area > 1e-6]
    if not pieces:
        return [slab]
    xdir = normal * (-1.0 if up else 1.0)  # from the axis to the zone's start on the face
    axis = xdir.cross(across)  # u grows from xdir toward `across` (the moving side)
    margin = thickness
    inner_radius = top_radius if up else top_radius - thickness
    r_in = max(inner_radius - 0.2 * thickness, 1e-3)
    reach = inner_radius + 1.2 * thickness - r_in
    circle = Part.Circle(axis_pt, axis, r_in)
    circle.XAxis = xdir
    surface = Part.Cylinder(circle)

    def sa(p):
        rel = p - origin
        return rel.dot(across), rel.dot(along)

    def on_boundary(p):
        s, a = sa(p)
        return (abs(s - s0) < 1e-6 or abs(s - s1) < 1e-6, abs(a - a0) < 1e-6 or abs(a - a1) < 1e-6)

    def boundary_edge(edge):
        """An edge of the zone's own rectangle (it lies on one of its four sides)."""
        if not isinstance(edge.Curve, (Part.Line, Part.LineSegment)):
            return False
        ends = [sa(v.Point) for v in edge.Vertexes]
        for k, lo, hi in ((0, s0, s1), (1, a0, a1)):
            for side in (lo, hi):
                if all(abs(e[k] - side) < 1e-6 for e in ends):
                    return True
        return False

    def pushed_corners(wire):
        """Where the piece's corners on the zone's sides go so its plug reaches `margin` past
        the slab: a corner where the outline meets a side slides along the outline (a slanted
        outline keeps its slope, so the cut follows it exactly); the rectangle's own corners
        and the rest move straight out."""
        edges = list(wire.OrderedEdges)
        out = {}
        for i, edge in enumerate(edges):
            nxt = edges[(i + 1) % len(edges)]
            shared = [
                v.Point
                for v in edge.Vertexes
                if any((v.Point - w.Point).Length < 1e-7 for w in nxt.Vertexes)
            ]
            if not shared:
                continue
            p = shared[0]
            on_s, on_a = on_boundary(p)
            if not (on_s or on_a):
                continue
            free = [e for e in (edge, nxt) if not boundary_edge(e)]
            if len(free) != 1 or not isinstance(free[0].Curve, (Part.Line, Part.LineSegment)):
                continue
            far = [v.Point for v in free[0].Vertexes if (v.Point - p).Length > 1e-7]
            if not far:
                continue
            d = unit(p - far[0])
            s, a = sa(p)
            reach_dir = 0.0
            for on, value, lo, normal_dir in ((on_s, s, s0, across), (on_a, a, a0, along)):
                if on:
                    sign = -1.0 if abs(value - lo) < 1e-6 else 1.0
                    reach_dir = max(reach_dir, d.dot(normal_dir) * sign)
            if reach_dir < 0.05:  # the outline runs nearly along the side: push straight out
                continue
            out[(round(p.x, 6), round(p.y, 6), round(p.z, 6))] = p + d * (margin / reach_dir)
        return out

    slid = {}

    def to_uv(p):
        key = (round(p.x, 6), round(p.y, 6), round(p.z, 6))
        if key in slid:
            s, a = sa(slid[key])
            return ((s - s0) / rn, (origin + along * a - axis_pt).dot(axis))
        s, a = sa(p)
        if abs(s - s0) < 1e-6:
            s -= margin
        elif abs(s - s1) < 1e-6:
            s += margin
        if abs(a - a0) < 1e-6:
            a -= margin
        elif abs(a - a1) < 1e-6:
            a += margin
        return ((s - s0) / rn, (origin + along * a - axis_pt).dot(axis))

    cutters = []
    for piece in pieces:
        if len(piece.Wires) != 1:
            raise SheetMetalError("The bend zone holds an island inside a hole; move the line.")
        slid.clear()
        slid.update(pushed_corners(piece.OuterWire))
        edges = [_map_edge(e, to_uv, surface) for e in piece.OuterWire.OrderedEdges]
        mapped = Part.Face(surface, Part.Wire(edges))
        plug = mapped.makeOffsetShape(reach, 1e-6, fill=True)
        if plug.isNull() or not plug.Solids:
            raise SheetMetalError("A hole or notch in the bend zone could not be bent.")
        cutters += list(plug.Solids)
    out = slab.cut(cutters)
    return list(out.Solids)


LINE_KEYS = ("angle", "position", "flip", "bend_relief")  # Fusion: per bend line


def _extent(shape, along):
    """(min, max) of a shape measured along a direction (points on its edges)."""
    lo = hi = None
    for edge in shape.Edges:
        for p in edge.discretize(9):
            d = p.dot(along)
            lo = d if lo is None else min(lo, d)
            hi = d if hi is None else max(hi, d)
    return lo, hi


def _merged_spans(slab, along, base):
    """[[lo, hi]] the solids of a thin slab cover along a direction (measured from `base`),
    overlapping ones merged."""
    spans = []
    for solid in slab.Solids:
        lo, hi = _extent(solid, along)
        spans.append([lo - base, hi - base])
    spans.sort()
    merged = spans[:1]
    for lo, hi in spans[1:]:
        if lo <= merged[-1][1] + 1e-6:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    return merged


def _moving_spans(result, zone, origin, along, across, normal, s0, s1, thickness, big):
    """Where the sheet goes on past the bend zone, along the line: [(m0, m1)] measured from
    `origin`, or None when that covers the whole zone (a bend right across the sheet)."""
    if zone.isNull() or zone.Volume < 1e-9:
        return None
    step = min(0.05, thickness / 4.0)

    def slab(x0, x1):
        return result.common(frame_box(origin, across, along, normal, x0, x1, -big, big, -big, big))

    cap = slab(s1, s1 + step)
    if cap.isNull() or not cap.Solids:
        return None
    base = origin.dot(along)
    merged = _merged_spans(cap, along, base)
    z0, z1 = _extent(zone, along)
    z0, z1 = z0 - base, z1 - base
    covered = sum(min(hi, z1) - max(lo, z0) for lo, hi in merged if hi > z0 and lo < z1)
    if covered >= (z1 - z0) - 1e-6:
        return None
    # a bend line slanted to the sheet's outline (a diagonal line across a rectangle): the
    # zone reaches past the moving side's front only because its ends are slanted. The sheet
    # beyond is as wide as the zone where they meet, so the whole zone bends (no tab)
    width = sum(hi - lo for lo, hi in merged)
    widest = 0.0
    for x0, x1 in ((s0, s0 + step), (s1 - step, s1)):
        piece = slab(x0, x1)
        if not piece.isNull() and piece.Solids:
            widest = max(widest, sum(hi - lo for lo, hi in _merged_spans(piece, along, base)))
    if width >= widest - max(1e-4, 2.0 * step * 1e-3):
        return None
    return [(lo, hi) for lo, hi in merged]


def _partial_zone(
    stationary, zone, spans, origin, along, across, normal, s0, s1, big, values, relief, thickness
):
    """A bend narrower than the sheet it crosses: only the zone in front of what moves bends;
    the rest of the zone stays, and the rule's bend relief is cut at each end of the bend
    where sheet stays beside it. Returns (stationary, zone)."""
    import Part

    keep = [frame_box(origin, across, along, normal, s0, s1, m0, m1, -big, big) for m0, m1 in spans]
    tool = keep[0] if len(keep) == 1 else keep[0].fuse(keep[1:])
    zone_in = zone.common(tool)
    zone_out = zone.cut(tool)
    if zone_out.isNull() or zone_out.Volume < 1e-9:
        return stationary, zone
    if not values.get("bend_relief", True):
        raise SheetMetalError(
            "This bend is narrower than the sheet it crosses (it bends a tab): turn on Bend "
            "Relief so the rule's relief is cut at its ends."
        )
    relief = relief or {}
    shape = relief.get("shape", "round")
    width = float(relief.get("width") or thickness)
    depth = float(relief.get("depth") or 0.0)
    if shape == "tear":
        # Tear removes nothing: the sheet is split along the bend's end. One solid cannot hold
        # two faces touching (a fuse would glue them back), so the split is a hairline slot,
        # the same 0.01 mm as the Flat hem's, across the bend zone only
        shape, width, depth = "straight", core.FLAT_GAP, 0.0
    if width <= 0:
        raise SheetMetalError("The rule's bend relief width must be more than 0.")
    slots = []
    for m0, m1 in spans:
        for a, b in ((m0 - width, m0), (m1, m1 + width)):
            beside = zone_out.common(
                frame_box(origin, across, along, normal, s0, s1, a, b, -big, big)
            )
            if beside.isNull() or beside.Volume < 1e-9:
                continue
            start = s0 - depth
            if shape == "round":
                r = width / 2.0
                slots.append(
                    frame_box(origin, across, along, normal, start + r, s1, a, b, -big, big)
                )
                centre = origin + across * (start + r) + along * (a + r) - normal * big
                slots.append(Part.makeCylinder(r, 2 * big, centre, normal))
            else:
                slots.append(frame_box(origin, across, along, normal, start, s1, a, b, -big, big))
    stationary = fuse_all(stationary, [zone_out], refine=False)
    if slots:
        stationary = stationary.cut(slots)
    return stationary, zone_in


def fold(
    shape, face_name, stationary_point, lines, options, thickness, radius, k_factor, relief=None
):
    """The body's solid bent along `lines` (body-local [(a, b)] or [(a, b, values)]: a line's
    own angle / position / flip, Fusion's row per bend line, over the common `options`).

    A line whose far side is narrower than the sheet it crosses (a tab) bends only that width:
    the rule's bend relief (`relief`: {"shape", "width", "depth"}) is cut into the sheet that
    stays, at both ends of the bend (Bend Relief on), else it is refused with the reason.
    Raises SheetMetalError."""
    for line in lines:
        values = dict(options)
        values.update(line[2] if len(line) > 2 else {})
        problems = core.check_bend(float(values.get("angle", 90.0)), radius, thickness)
        if problems:
            raise SheetMetalError(problems[0])
    try:
        face = shape.getElement(face_name)
    except Exception:
        raise SheetMetalError("The stationary face is gone; pick a top or bottom face again.")
    if not is_plane(face):
        raise SheetMetalError("The stationary face must be flat (a top or bottom face).")
    if not face_thickness(shape, face, thickness):
        raise SheetMetalError(
            "Pick a top or bottom face of the sheet (a face with the sheet's thickness "
            "behind it) as the stationary side."
        )
    if not lines:
        raise SheetMetalError("Pick one or more sketch lines to bend along.")
    normal = plane_normal(face)
    plane_point = face.Vertexes[0].Point
    rn = radius + k_factor * thickness
    flat = bend_lines_on(face, lines)
    point = _project(V(stationary_point), plane_point, normal)
    # farthest from the stationary side first: the lines still to bend stay where they were
    flat.sort(key=lambda ab: -_distance_to_line(point, ab[0], ab[1]))
    big = shape.BoundBox.DiagonalLength * 2.0 + 10.0
    result = shape
    for a, b, extra in flat:
        values = dict(options)
        values.update(extra or {})
        angle = float(values.get("angle", 90.0))
        up = not bool(values.get("flip", False))
        s0, s1 = core.bend_zone(
            values.get("position", "center"), angle, radius, thickness, k_factor
        )
        ba = s1 - s0
        along = unit(b - a)
        across = normal.cross(along)
        side = (point - a).dot(across)
        if abs(side) < 1e-6:
            raise SheetMetalError(
                "The stationary side is on the bend line; click the face on one side of it."
            )
        if side > 0:  # the moving side is away from the click
            along = along * -1.0
            across = across * -1.0
        origin = a

        def box(x0, x1):
            return frame_box(origin, across, along, normal, x0, x1, -big, big, -big, big)

        stationary = result.common(box(-big, s0))
        zone = result.common(box(s0, s1))
        moving = result.common(box(s1, big))
        if moving.isNull() or moving.Volume < 1e-9:
            raise SheetMetalError(
                "Nothing moves: the bend line is at (or past) the end of the sheet. Move the "
                "line or click the stationary face on the other side."
            )
        if stationary.isNull() or stationary.Volume < 1e-9:
            raise SheetMetalError("Nothing stays: click the stationary face on the side to keep.")
        spans = _moving_spans(result, zone, origin, along, across, normal, s0, s1, thickness, big)
        if spans:
            stationary, zone = _partial_zone(
                stationary,
                zone,
                spans,
                origin,
                along,
                across,
                normal,
                s0,
                s1,
                big,
                values,
                relief,
                thickness,
            )
        faces = _zone_faces(zone, plane_point, normal)
        area = sum(f.Area for f in faces)
        if not faces or abs(zone.Volume - area * thickness) > 1e-3 * max(1.0, zone.Volume):
            raise SheetMetalError(
                "The bend zone crosses something that is not flat sheet (a flange, another "
                "bend or a wall). Move the bend line onto a flat part of the sheet."
            )
        if up:
            axis_pt = origin + across * s0 + normal * radius
            top_radius = radius
        else:
            axis_pt = origin + across * s0 - normal * (radius + thickness)
            top_radius = radius + thickness
        bent_zone = _bend_zone_solid(
            faces,
            origin,
            along,
            across,
            normal,
            s0,
            s1,
            axis_pt,
            top_radius,
            thickness,
            rn,
            up,
            angle,
        )
        moved = moving.copy()
        moved.translate(across * (-ba))
        moved.rotate(axis_pt, along, angle if up else -angle)
        merged = fuse_all(stationary, bent_zone + [moved])
        result = one_solid(merged, "This bend")
        # the pieces must add up: the bent zone holds ((R + T)^2 - R^2) / (2 (R + K T) T) of its
        # flat volume at any angle; less means the sheet runs into itself, more a failed cut
        ratio = ((radius + thickness) ** 2 - radius**2) / (2.0 * rn * thickness)
        want = stationary.Volume + zone.Volume * ratio + moving.Volume
        # holes in the zone are laid on the bend by their outline: allow a fifth of their
        # volume for that, no more
        z0, z1 = _extent(zone, along)
        holes = max(0.0, (s1 - s0) * thickness * (z1 - z0) - zone.Volume)
        if abs(result.Volume - want) > 1e-3 + 1e-6 * want + 0.2 * holes:
            log("bend volume check: %.6f made, %.6f expected" % (result.Volume, want))
            raise SheetMetalError(
                "This bend would run the sheet into itself, or it could not be built cleanly "
                "here: check the angle, the bend line and its Bend Line position."
            )
    return result


def _distance_to_line(point, a, b):
    d = unit(b - a)
    rel = point - a
    return (rel - d * rel.dot(d)).Length


# -- the step -------------------------------------------------------------------------------
class BendFeature:
    """Saved in files as "sciforge.sheetmetal_bend.BendFeature": keep the name and properties."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, "Bend", doc)
                return True
            return False

        add("App::PropertyLinkSub", "StationaryFace", "The face that stays where it is")
        add("App::PropertyVector", "StationaryPoint", "Where the stationary face was clicked")
        add("App::PropertyLinkSubList", "BendLines", "The sketch lines bent along")
        if add("App::PropertyAngle", "Angle", "Bend angle"):
            obj.Angle = 90.0
        if add("App::PropertyEnumeration", "BendPosition", "Where the line is on the bend zone"):
            obj.BendPosition = POSITIONS
            obj.BendPosition = "Center"
        add("App::PropertyBool", "Flip", "Bend the other way")
        if add("App::PropertyBool", "BendRelief", "Allow bend relief"):
            obj.BendRelief = True
        if add("App::PropertyBool", "CornerRelief", "Use corner relief"):
            obj.CornerRelief = True
        add("App::PropertyBool", "OverrideRadius", "Use Bend Radius instead of the rule's")
        if add("App::PropertyLength", "BendRadius", "Inner bend radius (override)"):
            obj.BendRadius = 1.0
        if add("App::PropertyBool", "Refine", "Merge faces that end up in one plane"):
            obj.Refine = True
        bodies.mark(obj, KIND)

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)
        show_used(obj)

    def onChanged(self, obj, prop):
        if prop == "OverrideRadius":
            show_used(obj)

    def execute(self, obj):
        try:
            obj.Shape = build(obj)
        except Exception:
            bodies.pass_through(obj)
            raise

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def show_used(obj):
    """Bend Radius is shown (property editor, Change Parameters) only when it overrides the
    rule's."""
    try:
        obj.setEditorMode("BendRadius", 0 if obj.OverrideRadius else 2)
    except Exception:
        pass


def options_of(obj):
    return {
        "angle": float(obj.Angle),
        "position": str(obj.BendPosition).lower(),
        "flip": bool(obj.Flip),
        "bend_relief": bool(obj.BendRelief),
        "corner_relief": bool(obj.CornerRelief),
        "override_radius": bool(obj.OverrideRadius),
        "radius": float(obj.BendRadius),
    }


META = "SciForgeSmBend"


def line_key(owner, sub):
    return "%s:%s" % (owner.Name, sub)


def line_values(obj):
    """{line key: {angle, position, flip}}: the lines' own values (Fusion's rows)."""
    meta = bodies.load_meta(obj, META)
    lines = meta.get("lines") or {}
    return {k: dict(v) for k, v in lines.items() if isinstance(v, dict)}


def line_points(links, values=None):
    """[(a, b, own values)] body-local end points of the linked sketch lines."""
    import Part

    values = values or {}
    out = []
    for owner, subs in links or []:
        for sub in subs:
            try:
                edge = owner.Shape.getElement(sub)
            except Exception:
                raise SheetMetalError("A bend line is gone from its sketch; pick it again.")
            if not isinstance(edge.Curve, (Part.Line, Part.LineSegment)):
                raise SheetMetalError("Bend lines must be straight sketch lines.")
            own = values.get(line_key(owner, sub), {})
            out.append((edge.Vertexes[0].Point, edge.Vertexes[-1].Point, own))
    return out


def build(obj):
    base = obj.BaseFeature
    if base is None or base.Shape.isNull() or not base.Shape.Solids:
        raise SheetMetalError("There is no sheet to bend before this step.")
    body = bodies.body_of(obj)
    opts = options_of(obj)
    thickness, radius, k, rule = rule_values(
        body, opts["radius"] if opts["override_radius"] else None
    )
    link = obj.StationaryFace
    if not link or not link[1]:
        raise SheetMetalError("Pick the stationary face (a top or bottom face of the sheet).")
    shape = base.Shape.copy()
    shape.Placement = App.Placement()
    result = fold(
        shape,
        link[1][0],
        obj.StationaryPoint,
        line_points(obj.BendLines, line_values(obj)),
        opts,
        thickness,
        radius,
        k,
        relief={
            "shape": str(rule.get("bend_relief_shape", "round")),
            "width": float(rule.get("bend_relief_width", thickness)),
            "depth": float(rule.get("bend_relief_depth", thickness / 2.0)),
        },
    )
    if obj.Refine:
        try:
            result = result.removeSplitter()
        except Exception:
            pass
    return result


def make(body, base, face_name, point, lines, options=None, name="Bend", hide=True):
    """A Bend step at the history marker of `body`, built on `base` (its step before).
    lines: [(sketch, ["Edge1", ...])]. hide: the lines' sketches are hidden (used up); the
    dialog hides them only on OK, so more lines can still be clicked meanwhile."""
    opts = default_options()
    opts.update(options or {})
    obj = bodies.insert_after_tip(body, TYPE, name)
    BendFeature(obj)
    obj.BaseFeature = base
    apply(obj, base, face_name, point, lines, opts)
    _view(obj)
    if hide:
        hide_sketches(obj)
    log("bend %s made" % obj.Name)
    return obj


def hide_sketches(obj):
    """Hide the sketches whose lines the bend uses (Fusion consumes them)."""
    for sketch, _subs in obj.BendLines or []:
        try:
            if sketch.ViewObject is not None:
                sketch.ViewObject.Visibility = False
        except Exception:
            pass


def apply(obj, base, face_name, point, lines, options):
    obj.StationaryFace = (base, [face_name])
    obj.StationaryPoint = V(point)
    obj.BendLines = [(s, list(subs)) for s, subs in lines]
    obj.Angle = float(options.get("angle", 90.0))
    obj.BendPosition = core.POSITION_LABELS[options.get("position", "center")]
    obj.Flip = bool(options.get("flip", False))
    obj.BendRelief = bool(options.get("bend_relief", True))
    obj.CornerRelief = bool(options.get("corner_relief", True))
    obj.OverrideRadius = bool(options.get("override_radius", False))
    if options.get("radius") is not None:
        obj.BendRadius = float(options["radius"])
    picked = set(line_key(o, sub) for o, subs in lines for sub in subs)
    own = {}
    for key, entry in (options.get("lines") or {}).items():
        if key in picked and isinstance(entry, dict):
            own[key] = {k: entry[k] for k in LINE_KEYS if k in entry}
    bodies.save_meta(obj, META, {"lines": own})


def read(obj):
    """(base, face name, point, lines, options) of a Bend step (for the dialog)."""
    link = obj.StationaryFace
    face = link[1][0] if link and link[1] else ""
    lines = [(o, list(subs)) for o, subs in (obj.BendLines or [])]
    options = options_of(obj)
    options["lines"] = line_values(obj)
    return obj.BaseFeature, face, V(obj.StationaryPoint), lines, options


def _view(obj):
    if not App.GuiUp:
        return
    try:
        from . import sheetmetal_bend_ui

        sheetmetal_bend_ui.ViewProviderBend(obj.ViewObject)
    except Exception:
        pass
