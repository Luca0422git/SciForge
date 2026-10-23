# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sheet metal forming geometry: Fusion's Flange (base, contour and edge flanges), built with
FreeCAD's Part module only (no document, no Qt), so the dialogs, the golden-model builder, the
unit tests and the other sheet metal tools (sm-more's Hem, sm-flat's unfolder) share it.

Every solid made here is flat walls plus cylindrical bends of one thickness, with each bend's
inside radius the rule's bend radius: what a flat pattern can be unfolded from.

Coordinates are design (global) coordinates; the caller moves shapes in and out of a body.

    base_flange(faces, normal, thickness, orientation)          closed profile -> plate
    contour_flange(edges, normal, thickness, radius, distance, ...)  open chain -> bent strip
    edge_frame(shape, edge_name, thickness, flip)               where a sheet edge is
    bend_wall(frame, t0, t1, thickness, radius, angle, length, position)
                                                                one bend + wall on an edge
    edge_flange(shape, edge_names, rule, options)               the whole Edge flange

All raise FormError with a reason the dialog shows (what is wrong and what to try).
"""

import math

import FreeCAD as App
import Part

from . import sheetmetal_core as core

V = App.Vector
TOL = 1e-6
LINEAR_TOL = 1e-4  # mm: sizes that must match (thickness of a side face, ...)


class FormError(ValueError):
    """The flange cannot be made; the message says why and what to try."""


# -- 2D chains of lines and arcs ---------------------------------------------------------------
class Plane2D:
    """A plane with 2D coordinates: p((x, y)) is the 3D point, q(point) the 2D one."""

    def __init__(self, origin, xdir, ydir):
        self.o = V(origin)
        self.x = V(xdir).normalize()
        self.y = V(ydir).normalize()
        self.n = self.x.cross(self.y)

    def p(self, q):
        return self.o + self.x * q[0] + self.y * q[1]

    def q(self, point):
        d = V(point) - self.o
        return (d.dot(self.x), d.dot(self.y))


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def _add(a, b, k=1.0):
    return (a[0] + b[0] * k, a[1] + b[1] * k)


def _len(a):
    return math.hypot(a[0], a[1])


def _unit(a):
    n = _len(a)
    if n < TOL:
        raise FormError("a curve of the profile has no length")
    return (a[0] / n, a[1] / n)


def _left(d):
    return (-d[1], d[0])


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def line(a, b):
    return {"kind": "line", "a": tuple(a), "b": tuple(b)}


def arc(center, radius, a0, sweep):
    """An arc from angle a0 (radians), turning `sweep` (positive: counter-clockwise)."""
    return {"kind": "arc", "c": tuple(center), "r": float(radius), "a0": a0, "sweep": sweep}


def seg_start(seg):
    if seg["kind"] == "line":
        return seg["a"]
    return _add(seg["c"], (math.cos(seg["a0"]), math.sin(seg["a0"])), seg["r"])


def seg_end(seg):
    if seg["kind"] == "line":
        return seg["b"]
    a1 = seg["a0"] + seg["sweep"]
    return _add(seg["c"], (math.cos(a1), math.sin(a1)), seg["r"])


def seg_dir(seg, at_end=False):
    """Unit direction of travel at the start (or end) of a segment."""
    if seg["kind"] == "line":
        return _unit(_sub(seg["b"], seg["a"]))
    angle = seg["a0"] + (seg["sweep"] if at_end else 0.0)
    if seg["sweep"] > 0:
        return (-math.sin(angle), math.cos(angle))
    return (math.sin(angle), -math.cos(angle))


def reversed_seg(seg):
    if seg["kind"] == "line":
        return line(seg["b"], seg["a"])
    return arc(seg["c"], seg["r"], seg["a0"] + seg["sweep"], -seg["sweep"])


def offset_seg(seg, s):
    """The segment moved `s` to its left (an arc's radius shrinks on its inside)."""
    if seg["kind"] == "line":
        n = _left(_unit(_sub(seg["b"], seg["a"])))
        return line(_add(seg["a"], n, s), _add(seg["b"], n, s))
    r = seg["r"] - s if seg["sweep"] > 0 else seg["r"] + s
    if r < -LINEAR_TOL:
        raise FormError(
            "an arc of radius %.3f mm is tighter than the sheet: draw it larger" % seg["r"]
        )
    return arc(seg["c"], max(r, 0.0), seg["a0"], seg["sweep"])


def _edges_3d(segs, plane):
    edges = []
    for seg in segs:
        if seg["kind"] == "line":
            a, b = plane.p(seg["a"]), plane.p(seg["b"])
            if (b - a).Length > TOL:
                edges.append(Part.LineSegment(a, b).toShape())
        elif seg["r"] > TOL and abs(seg["sweep"]) > 1e-9:
            mid = arc(seg["c"], seg["r"], seg["a0"], seg["sweep"] / 2.0)
            edges.append(
                Part.Arc(
                    plane.p(seg_start(seg)), plane.p(seg_end(mid)), plane.p(seg_end(seg))
                ).toShape()
            )
    return edges


def section_face(segs, s0, s1, plane):
    """The cross-section of a sheet laid along a tangent chain of segments: the region
    between the chain moved s0 and s1 to its left, closed by straight caps at both ends."""
    low = [offset_seg(s, s0) for s in segs]
    high = [offset_seg(s, s1) for s in segs]
    caps = [
        line(seg_end(low[-1]), seg_end(high[-1])),
        line(seg_start(high[0]), seg_start(low[0])),
    ]
    edges = _edges_3d(low, plane) + _edges_3d(caps[:1], plane)
    edges += _edges_3d([reversed_seg(s) for s in reversed(high)], plane)
    edges += _edges_3d(caps[1:], plane)
    try:
        wire = Part.Wire(Part.__sortEdges__(edges))
        face = Part.Face(wire)
    except Exception as exc:
        raise FormError("the sheet's cross-section could not be made (%s)" % exc)
    if not wire.isClosed() or face.Area < TOL:
        raise FormError("the sheet's cross-section does not close")
    return face


# -- base flange --------------------------------------------------------------------------------
def base_flange(faces, normal, thickness, orientation="side1"):
    """A flat plate from closed profiles: each face (planar, design coordinates) thickened by
    `thickness` along `normal` (the sketch's normal): Side 1 on the normal's side, Side 2 on
    the other, Centered half each. Touching plates fuse into one solid."""
    if not faces:
        raise FormError("Pick a closed profile of a sketch for the plate.")
    if thickness <= 0:
        raise FormError("The rule's thickness must be more than 0.")
    n = V(normal).normalize()
    s0, s1 = core.thickness_offsets(orientation, thickness)
    plates = []
    for face in faces:
        try:
            moved = face.copy()
            moved.translate(n * s0)
            plates.append(moved.extrude(n * (s1 - s0)))
        except Exception as exc:
            raise FormError("a profile could not be thickened (%s)" % exc)
    result = plates[0]
    if len(plates) > 1:
        result = plates[0].fuse(plates[1:])
    return _clean(result)


# -- contour flange -----------------------------------------------------------------------------
def _edge_seg(edge, plane):
    curve = edge.Curve
    u0, u1 = edge.FirstParameter, edge.LastParameter
    if isinstance(curve, (Part.Line, Part.LineSegment)):
        return line(plane.q(edge.valueAt(u0)), plane.q(edge.valueAt(u1)))
    if isinstance(curve, Part.Circle):
        if abs(abs(curve.Axis.dot(plane.n)) - 1.0) > 1e-6:
            raise FormError("an arc of the profile is not in the sketch's plane")
        c = plane.q(curve.Center)
        start = plane.q(edge.valueAt(u0))
        a0 = math.atan2(start[1] - c[1], start[0] - c[0])
        sign = 1.0 if curve.Axis.dot(plane.n) > 0 else -1.0
        if edge.Orientation == "Reversed":
            start = plane.q(edge.valueAt(u1))
            a0 = math.atan2(start[1] - c[1], start[0] - c[0])
            return arc(c, curve.Radius, a0, -sign * (u1 - u0))
        return arc(c, curve.Radius, a0, sign * (u1 - u0))
    raise FormError(
        "a contour flange takes lines and arcs: a %s cannot be bent to the rule's radius"
        % type(curve).__name__
    )


def _close(a, b, tol=1e-5):
    return _len(_sub(a, b)) <= tol


def chain_segments(edges, plane):
    """The edges (design coordinates) as one ordered open chain of 2D segments; raises
    FormError for a closed loop, a branch or pieces that do not join."""
    segs = [_edge_seg(e, plane) for e in edges]
    if not segs:
        raise FormError("Pick an open sketch line (or a chain of lines and arcs).")
    ends = []
    for s in segs:
        ends += [seg_start(s), seg_end(s)]
    free = [p for p in ends if sum(1 for q in ends if _close(p, q)) == 1]
    if not free:
        raise FormError("The profile is closed: a closed profile makes a base flange (a plate).")
    if len(free) > 2:
        raise FormError(
            "Pick one connected chain of lines and arcs (this one has a branch or gap)."
        )
    start = free[0]
    ordered, left = [], list(segs)
    point = start
    while left:
        for i, s in enumerate(left):
            if _close(seg_start(s), point):
                ordered.append(s)
                break
            if _close(seg_end(s), point):
                ordered.append(reversed_seg(s))
                break
        else:
            raise FormError("Pick one connected chain of lines and arcs.")
        left.pop(i)
        point = seg_end(ordered[-1])
    return ordered


def bend_corners(segs, s0, s1, radius):
    """The chain with every sharp corner between two lines turned into an arc whose
    inside (the sheet's inner face) has the rule's bend radius. Raises FormError when a line
    is too short for its bends or a corner touches an arc without being tangent."""
    out = [dict(s) for s in segs]
    result = []
    trims = {}  # index -> [trim at start, trim at end]
    fillets = {}
    for i in range(len(out) - 1):
        a, b = out[i], out[i + 1]
        d1, d2 = seg_dir(a, at_end=True), seg_dir(b)
        turn = _cross(d1, d2)
        cosang = max(-1.0, min(1.0, _dot(d1, d2)))
        theta = math.acos(cosang)
        if theta < 1e-7:
            continue  # tangent: already smooth
        if a["kind"] != "line" or b["kind"] != "line":
            raise FormError(
                "A corner next to an arc must be tangent: draw the arc tangent or use lines."
            )
        if theta > math.pi - 1e-6:
            raise FormError(
                "A line folds straight back on itself: use a Hem for a 180 degree fold."
            )
        left = turn > 0
        rp = core.path_radius(left, s0, s1, radius)
        tl = rp * math.tan(theta / 2.0)
        corner = a["b"]
        trims.setdefault(i, [0.0, 0.0])[1] = tl
        trims.setdefault(i + 1, [0.0, 0.0])[0] = tl
        p_start = _add(corner, d1, -tl)
        side = _left(d1) if left else (-_left(d1)[0], -_left(d1)[1])
        center = _add(p_start, side, rp)
        a0 = math.atan2(p_start[1] - center[1], p_start[0] - center[0])
        fillets[i] = arc(center, rp, a0, theta if left else -theta)
    for i, s in enumerate(out):
        if s["kind"] == "line" and i in trims:
            d = _unit(_sub(s["b"], s["a"]))
            length = _len(_sub(s["b"], s["a"]))
            t_start, t_end = trims[i]
            if t_start + t_end > length + LINEAR_TOL:
                raise FormError(
                    "A line of %.2f mm is too short for its bends (they need %.2f mm): "
                    "draw it longer or use a smaller bend radius." % (length, t_start + t_end)
                )
            s = line(_add(s["a"], d, t_start), _add(s["b"], d, -t_end))
        if s["kind"] == "line" and _len(_sub(s["b"], s["a"])) < LINEAR_TOL:
            pass  # a line used up by its two bends
        else:
            result.append(s)
        if i in fillets:
            result.append(fillets[i])
    return result


def contour_section(edges, plane, thickness, radius, orientation="side1"):
    """The cross-section face of a contour flange (in the sketch's plane) and its chain."""
    if thickness <= 0:
        raise FormError("The rule's thickness must be more than 0.")
    s0, s1 = core.thickness_offsets(orientation, thickness)
    segs = bend_corners(chain_segments(edges, plane), s0, s1, radius)
    return section_face(segs, s0, s1, plane), segs


def contour_flange(
    edges,
    plane,
    thickness,
    radius,
    distance,
    orientation="side1",
    direction="one_side",
    distance2=0.0,
    flip=False,
):
    """Fusion's contour flange: an open chain of sketch lines/arcs (design coordinates) in
    `plane` (a Plane2D of the sketch) with the sheet on one side (orientation), every sharp
    corner bent to the rule's inside radius, extruded `distance` along the sketch normal
    (direction one_side, flipped to the other side by `flip`; symmetric: distance in total
    centred; two_sides: distance one way, distance2 the other)."""
    if distance <= 0 or (direction == "two_sides" and distance2 < 0):
        raise FormError("The distance must be more than 0.")
    face, _segs = contour_section(edges, plane, thickness, radius, orientation)
    n = plane.n * (-1.0 if flip else 1.0)
    if direction == "symmetric":
        start, length = -distance / 2.0, distance
    elif direction == "two_sides":
        start, length = -distance2, distance + distance2
    else:
        start, length = 0.0, distance
    face.translate(n * start)
    return _clean(face.extrude(n * length))


def contour_attachment(shape, edges, plane, thickness):
    """Where an open sketch chain starts on a sheet edge of `shape` (design coordinates):
    (edge name, the chain's end point on it) when one end of the chain is at an end of a
    straight sheet edge that runs square to the sketch plane, else None. Fusion runs such a
    contour flange along that edge and bends it out of the sheet (G)."""
    if shape is None or shape.isNull() or not shape.Solids:
        return None
    try:
        segs = chain_segments(edges, plane)
    except FormError:
        return None
    ends = [plane.p(seg_start(segs[0])), plane.p(seg_end(segs[-1]))]
    for i, edge in enumerate(shape.Edges, 1):
        if not isinstance(edge.Curve, (Part.Line, Part.LineSegment)):
            continue
        a, b = edge.Vertexes[0].Point, edge.Vertexes[-1].Point
        direction = b - a
        if direction.Length < TOL or abs(abs(direction.normalize().dot(plane.n)) - 1.0) > 1e-7:
            continue
        for end in ends:
            if (end - a).Length < 1e-5 or (end - b).Length < 1e-5:
                try:
                    edge_frame(shape, "Edge%d" % i, thickness)
                except FormError:
                    continue
                return "Edge%d" % i, end
    return None


def contour_on_edge(shape, edges, plane, thickness, radius, edge_name, start):
    """Fusion's contour flange on a sheet edge: the sketched chain (in a plane square to the
    edge, starting at the edge's end) carries on from the sheet, the corner between the sheet
    and its first line bent with the rule's radius, run along the whole edge and joined. The
    thickness side is the one that continues the sheet. Returns the new solid."""
    frame = edge_frame(shape, edge_name, thickness)
    segs = chain_segments(edges, plane)
    p0 = plane.q(start)
    if not _close(seg_start(segs[0]), p0):
        segs = [reversed_seg(s) for s in reversed(segs)]
    out2 = _unit(_sub(plane.q(start + frame.out), p0))
    lead = 10.0 * thickness + radius + 10.0
    first = line(_add(p0, out2, -lead), p0)
    left3 = plane.n.cross(frame.out)
    # the sheet lies on the far side of its face from frame.up: the band goes that way
    s0, s1 = (-thickness, 0.0) if left3.dot(frame.up) > 0 else (0.0, thickness)
    bent = bend_corners([first] + segs, s0, s1, radius)
    lead_end = seg_end(bent[0])
    cut_back = _len(_sub(p0, lead_end))
    bent = bent[1:]
    if not bent:
        raise FormError("The contour runs back along the sheet: draw it out from the edge.")
    face = section_face(bent, s0, s1, plane)
    edge = shape.getElement(edge_name)
    a, b = edge.Vertexes[0].Point, edge.Vertexes[-1].Point
    other = b if (a - start).Length < 1e-5 else a
    solid = _clean(face.extrude(other - start))
    base = shape
    if cut_back > TOL:
        base = shape.cut(frame.box(-cut_back, 0.0, 0.0, thickness, 0.0, frame.length))
    if solid.common(base).Volume > 1e-3:
        raise FormError(
            "The contour flange would run into the part: draw it away from the sheet, or flip "
            "the line's direction."
        )
    result = _clean(base.fuse(solid))
    if len(result.Solids) != len(shape.Solids):
        raise FormError("The contour flange does not join the sheet at its edge.")
    return result


# -- edge flange --------------------------------------------------------------------------------
class EdgeFrame:
    """Where a sheet edge is: `origin` on the edge's line, on the sheet's outer face (the
    face the flange turns away from); `axis` along the edge (length `length`); `out` in the
    sheet's plane, away from the material; `up` the side the flange turns to. The sheet lies
    at x <= 0 (x along out), between z = 0 (outer face) and z = thickness (inner face)."""

    def __init__(self, origin, axis, out, up, length, thickness, name=""):
        self.origin = V(origin)
        self.axis = V(axis).normalize()
        self.out = V(out).normalize()
        self.up = V(up).normalize()
        self.length = float(length)
        self.thickness = float(thickness)
        self.name = name

    def point(self, x, z, t=0.0):
        return self.origin + self.out * x + self.up * z + self.axis * t

    def plane_at(self, t):
        return Plane2D(self.point(0.0, 0.0, t), self.out, self.up)

    def box(self, x0, x1, z0, z1, t0, t1):
        """A box in frame coordinates (any order of the bounds)."""
        x0, x1 = min(x0, x1), max(x0, x1)
        z0, z1 = min(z0, z1), max(z0, z1)
        t0, t1 = min(t0, t1), max(t0, t1)
        face = Part.Face(
            Part.makePolygon(
                [
                    self.point(x0, z0, t0),
                    self.point(x1, z0, t0),
                    self.point(x1, z1, t0),
                    self.point(x0, z1, t0),
                    self.point(x0, z0, t0),
                ]
            )
        )
        return face.extrude(self.axis * (t1 - t0))


def _planar(face):
    return isinstance(face.Surface, Part.Plane)


def _normal_at(face, point):
    u, v = face.Surface.parameter(point)
    return face.normalAt(u, v)


def _extent(face, direction):
    values = [v.Point.dot(direction) for v in face.Vertexes]
    return max(values) - min(values) if values else 0.0


def edge_frame(shape, edge_name, thickness, flip=False):
    """The EdgeFrame of a sheet edge `edge_name` ("EdgeN") of `shape`: a straight edge where
    a top or bottom face of the sheet meets a side face square to it whose width is the
    sheet's thickness. Raises FormError with the reason otherwise."""
    try:
        edge = shape.getElement(edge_name)
    except Exception:
        raise FormError("%s is gone: pick the edge again." % edge_name)
    if not isinstance(edge.Curve, (Part.Line, Part.LineSegment)):
        raise FormError(
            "%s is curved: a flange is bent along a straight edge "
            "(use a contour flange with arcs for a rounded shape)." % edge_name
        )
    faces = shape.ancestorsOfType(edge, Part.Face)
    if len(faces) != 2 or not all(_planar(f) for f in faces):
        raise FormError(
            "%s is not a sheet edge: pick an edge where the flat top or bottom face meets a "
            "side face." % edge_name
        )
    p0, p1 = edge.Vertexes[0].Point, edge.Vertexes[-1].Point
    mid = (p0 + p1) * 0.5
    candidates = []
    for i, face in enumerate(faces):
        other = faces[1 - i]
        n = _normal_at(face, mid)
        if abs(_extent(other, n) - thickness) <= LINEAR_TOL:
            candidates.append((face.Area, i, n))
    if not candidates:
        raise FormError(
            "%s is not on the sheet's %.3g mm thickness: pick a long edge of the top or bottom "
            "face, not an edge across the thickness." % (edge_name, thickness)
        )
    candidates.sort(key=lambda c: -c[0])
    _area, index, n_face = candidates[0]
    side = faces[1 - index]
    out = _normal_at(side, mid)
    if abs(out.dot(n_face)) > 1e-6:
        raise FormError("%s: the side face must be square to the sheet." % edge_name)
    up = n_face * (-1.0 if flip else 1.0)
    origin = p0 - up * thickness if not flip else V(p0)
    frame = EdgeFrame(origin, p1 - p0, out, up, (p1 - p0).Length, thickness, edge_name)
    frame.edge_z = 0.0 if flip else thickness  # where the picked edge itself lies
    return frame


class BendWall:
    """The result of bend_wall: `solid` (bend + wall), `trim` (the strip of plate the bend
    replaces, or None), `bend_x` (where the bend starts, frame x), `center` (2D bend axis in
    the frame's (x, z)), `wall_dir` (2D), `wall_start` / `wall_end` (2D, on the outer face)."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


def bend_wall(frame, t0, t1, thickness, radius, angle, length, position="inside"):
    """One bend plus a straight wall standing on a sheet edge (Fusion's edge flange; sm-more's
    Hem reuses it). `frame` is an EdgeFrame; the bend turns `angle` degrees (0 < angle <=
    180) towards frame.up with inside radius `radius`; the wall after it is `length` long;
    `position` is Fusion's Bend Position (inside / outside / adjacent / tangent). The flange
    covers the edge from t0 to t1 (mm along frame.axis). The caller cuts `trim` from the
    plate and fuses `solid` to it."""
    if not 0.0 < angle <= 180.0 + 1e-9:
        raise FormError("The angle must be more than 0 and at most 180 degrees.")
    if radius < 0:
        raise FormError("The bend radius cannot be negative.")
    if length <= TOL:
        raise FormError("The flange's wall must be longer than 0.")
    if t1 - t0 <= TOL:
        raise FormError("The flange width must be more than 0.")
    T, R = thickness, radius
    a = math.radians(angle)
    try:
        xc = core.bend_start_x(position, angle, R, T)
    except ValueError as exc:
        raise FormError("Bend Position: %s." % exc)
    center = (xc, T + R)
    outer = arc(center, R + T, -math.pi / 2.0, a)
    end = seg_end(outer)
    wall_dir = (math.cos(a), math.sin(a))
    wall = line(end, _add(end, wall_dir, length))
    face = section_face([outer, wall], 0.0, T, frame.plane_at(t0))
    solid = face.extrude(frame.axis * (t1 - t0))
    trim = frame.box(xc, 0.0, 0.0, T, t0, t1) if xc < -TOL else None
    return BendWall(
        solid=_clean(solid),
        trim=trim,
        bend_x=xc,
        center=center,
        wall_dir=wall_dir,
        wall_start=end,
        wall_end=wall["b"],
    )


def _relief(frame, a, b, bend_x, rule, shape_name):
    """The bend relief cut at one end of a flange: from the edge back across the bend zone
    and Relief Depth more, between a and b along the edge."""
    T = frame.thickness
    depth = rule["bend_relief_depth"]
    x_end = min(bend_x, 0.0) - depth
    if shape_name == "tear":
        width = core.TEAR_SLIT
        a, b = (a, a + width) if b - a > width and a > 0 else (b - width, b)
        return frame.box(x_end, 0.01, -0.01, T + 0.01, a, b)
    cut = frame.box(x_end, 0.01, -0.01, T + 0.01, a, b)
    if shape_name == "round" and b - a > TOL:
        r = (b - a) / 2.0
        straight = frame.box(x_end + r, 0.01, -0.01, T + 0.01, a, b)
        disc = Part.makeCylinder(
            r, T + 0.02, frame.point(x_end + r, -0.01, (a + b) / 2.0), frame.up
        )
        cut = straight.fuse(disc)
    return cut


def _half_space(point, normal, size):
    """The solid on the +normal side of the plane through point (a big slab)."""
    n = V(normal).normalize()
    face = Part.Plane(point, n).toShape(-size, size, -size, size)
    return face.extrude(n * size)


def flange_options(options=None):
    """Edge flange options with Fusion's defaults filled in (fusion-sheet-metal.md 2.2.2)."""
    out = {
        "height": 10.0,
        "extent": "distance",
        "datum": "inner",
        "position": "inside",
        "angle": 90.0,
        "flip": False,
        "width_type": "full",
        "width": 10.0,
        "distance1": 5.0,
        "distance2": 5.0,
        "target": None,  # To Object: (point, normal) of the plane the flange runs to
        "offset_planes": None,  # Two Offsets: two (point, normal) references across the edge
        "target_offset": 0.0,
        "bend_radius": None,  # overrides (None: the rule's)
        "relief_shape": None,
        "relief_width": None,
        "relief_depth": None,
        "relief_remnant": None,
        "miter_gap": None,
    }
    out.update(options or {})
    return out


def effective_rule(rule, options):
    """The rule's values with the flange's overrides applied (lengths in mm)."""
    eff = dict(rule)
    for key, field in (
        ("bend_radius", "bend_radius"),
        ("relief_shape", "bend_relief_shape"),
        ("relief_width", "bend_relief_width"),
        ("relief_depth", "bend_relief_depth"),
        ("relief_remnant", "bend_relief_remnant"),
        ("miter_gap", "miter_gap"),
    ):
        if options.get(key) is not None:
            eff[field] = options[key]
    return eff


def _wall_length(frame, opts, rule, angle):
    T, R = frame.thickness, rule["bend_radius"]
    if opts["extent"] == "to_object":
        target = opts.get("target")
        if not target:
            raise FormError("To Object: pick the face or plane the flange runs to.")
        point, normal = V(target[0]), V(target[1]).normalize()
        try:
            xc = core.bend_start_x(opts["position"], angle, R, T)
        except ValueError as exc:
            raise FormError("Bend Position: %s." % exc)
        a = math.radians(angle)
        start2d = (xc + (R + T / 2.0) * math.sin(a), T + R - (R + T / 2.0) * math.cos(a))
        start = frame.point(start2d[0], start2d[1], frame.length / 2.0)
        direction = frame.out * math.cos(a) + frame.up * math.sin(a)
        along = direction.dot(normal)
        if abs(along) < 1e-6:
            raise FormError("The flange runs parallel to that face and never reaches it.")
        length = (point - start).dot(normal) / along + opts.get("target_offset", 0.0)
        if length <= TOL:
            raise FormError("That face is behind the bend: pick a face the flange runs towards.")
        return length
    try:
        return core.wall_length(opts["height"], opts["datum"], angle, R, T)
    except ValueError as exc:
        raise FormError("Height: %s." % exc)


def _crossing(frame, plane):
    """Where (mm along the edge from frame.origin) a reference plane (point, normal) crosses
    the edge's line; ValueError when it runs parallel to the edge."""
    point, normal = V(plane[0]), V(plane[1]).normalize()
    along = frame.axis.dot(normal)
    if abs(along) < 1e-6:
        raise ValueError("a reference runs along the edge and never crosses it")
    return (point - frame.point(0.0, getattr(frame, "edge_z", 0.0))).dot(normal) / along


def _shared_vertex(fa, fb):
    """(point, ta, tb): the end the two frames share (ta/tb: 0 or the edge length), or None."""
    for ta in (0.0, fa.length):
        pa = fa.point(0.0, 0.0, ta) + fa.up * 0.0
        for tb in (0.0, fb.length):
            pb = fb.point(0.0, 0.0, tb)
            if (pa - pb).Length <= 1e-5:
                return pa, ta, tb
    return None


def edge_flange(shape, edge_names, rule, options=None):
    """Fusion's edge flange on the sheet metal solid `shape` (design coordinates): a bend
    and a wall on every named edge, the plate cut back where the bend position needs it,
    bend reliefs where a flange stops inside its edge, and mitred corners (the rule's
    Miter/Rip/Seam Gap apart) where two picked edges meet. `rule` is an evaluated rule
    (sheetmetal_core.evaluated: lengths in mm). Returns the new solid."""
    opts = flange_options(options)
    if not edge_names:
        raise FormError("Pick one or more edges of a sheet metal body.")
    if opts["extent"] == "to_object" and len(edge_names) > 1:
        raise FormError("To Object works with one edge: pick a single edge.")
    if shape is None or shape.isNull() or not shape.Solids:
        raise FormError("The edges must be on a sheet metal body with a solid.")
    eff = effective_rule(rule, opts)
    T = rule["thickness"]
    angle = float(opts["angle"])
    if not 0.0 < angle <= 180.0 + 1e-9:
        raise FormError("The angle must be more than 0 and at most 180 degrees.")
    frames = [edge_frame(shape, name, T, bool(opts["flip"])) for name in edge_names]
    length = _wall_length(frames[0], opts, eff, angle)
    pieces, cuts, ranges = [], [], []
    refs = opts.get("offset_planes") if opts["width_type"] == "two_offsets" else None
    for frame in frames:
        try:
            if refs:
                t_a, t_b = (_crossing(frame, plane) for plane in refs)
                t0, t1 = core.width_between(t_a, t_b, opts["distance1"], opts["distance2"])
            else:
                t0, t1 = core.width_range(
                    opts["width_type"],
                    frame.length,
                    opts["width"],
                    opts["distance1"],
                    opts["distance2"],
                )
        except ValueError as exc:
            raise FormError("Width: %s." % exc)
        made = bend_wall(frame, t0, t1, T, eff["bend_radius"], angle, length, opts["position"])
        pieces.append(made)
        ranges.append((t0, t1))
        if made.trim is not None:
            cuts.append(made.trim)
        for a, b in core.relief_ends(
            t0, t1, frame.length, eff["bend_relief_width"], eff["bend_relief_remnant"]
        ):
            cuts.append(_relief(frame, a, b, made.bend_x, eff, eff["bend_relief_shape"]))
    size = 10.0 * (shape.BoundBox.DiagonalLength + length + 10.0 * T + 10.0)
    solids = [p.solid for p in pieces]
    gap = eff["miter_gap"]
    for i in range(len(frames)):
        for j in range(i + 1, len(frames)):
            shared = _shared_vertex(frames[i], frames[j])
            if shared is None:
                continue
            point, ta, tb = shared
            reach_a = ranges[i][0] <= TOL if ta == 0.0 else ranges[i][1] >= frames[i].length - TOL
            reach_b = ranges[j][0] <= TOL if tb == 0.0 else ranges[j][1] >= frames[j].length - TOL
            if not (reach_a and reach_b):
                continue
            diff = frames[j].out - frames[i].out
            if diff.Length < 1e-6 or (frames[i].up - frames[j].up).Length > 1e-6:
                continue
            # m: across the corner's bisector plane, towards edge i's side (an outside corner
            # and an inside one of an L-shaped plate put it on opposite sides)
            m = diff.normalize()
            mid_i = frames[i].point(0.0, 0.0, frames[i].length / 2.0)
            if (mid_i - point).dot(m) < 0:
                m = m * -1.0
            solids[i] = _clean(solids[i].cut(_half_space(point + m * (gap / 2.0), m * -1.0, size)))
            solids[j] = _clean(solids[j].cut(_half_space(point - m * (gap / 2.0), m, size)))
    base = shape
    if cuts:
        base = shape.cut(cuts)
    for i, solid in enumerate(solids):
        if solid.common(base).Volume > 1e-3:
            raise FormError(
                "The flange on %s would run into the part: change the side (Flip), the "
                "height or the bend position." % frames[i].name
            )
        for j in range(i + 1, len(solids)):
            if solid.common(solids[j]).Volume > 1e-3:
                raise FormError(
                    "The flanges on %s and %s overlap: pick edges that meet at a corner of the "
                    "same face, or make them one at a time." % (frames[i].name, frames[j].name)
                )
    result = base.fuse(solids)
    result = _clean(result)
    if len(result.Solids) != len(shape.Solids):
        raise FormError("The flange does not join the part (it would make a separate piece).")
    return result


def _clean(shape):
    try:
        shape = shape.removeSplitter()
    except Exception:
        pass
    if len(shape.Solids) == 1:
        return shape.Solids[0]
    return shape
