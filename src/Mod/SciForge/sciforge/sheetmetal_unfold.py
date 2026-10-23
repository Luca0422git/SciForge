# SPDX-License-Identifier: LGPL-2.1-or-later
"""The unfolder: lays a sheet metal solid flat (FreeCAD Part only: no document, no Qt).

A sheet metal solid is made of flat walls and cylindrical bends of one thickness T. Fusion's
flat pattern, Unfold and Refold all rest on the same idea, implemented here:

1. Start from a *stationary* planar face (a top or bottom face of a wall, never an edge face).
   T is the distance to the opposite face (a ray through the solid).
2. Walk the faces on the stationary face's side of the sheet: from a face to its neighbour
   only across a *tangent* (G1) edge (wall <-> bend, bend <-> bend), never across the sharp
   edges of the thickness. Those faces are the sheet's "skin" on that side.
3. Give every skin face a map into the result: a wall gets a rigid move; a bend that is
   unfolded is *developed*: a point at angle phi from the bend's entry line goes to the entry
   line + phi * Rn along the sheet, Rn = R_inner + K * T (the neutral layer keeps its length);
   the wall after it is turned back about the bend axis by the bend angle, then moved by the
   developed length. A bend that is kept (Unfold of some bends only) moves rigidly with its
   parent, and so does everything beyond it.
4. Every skin face becomes a *slab* (the face pushed through the thickness), mapped into the
   result; the slabs are fused into one solid. Holes and cuts come through as the faces'
   inner wires; a cut that crosses a bend is developed point by point.

Checks (each a refusal with a reason, never a wrong flat): the stationary face is planar;
the slabs fill the solid (uniform thickness, every part reached through bends: a sharp
corner between two walls is no bend); a closed loop (a tube) needs a Rip; the result must
not overlap itself.

The maps can also be run backwards (Refold): a region cut out of the flat state is cut out
of the folded solid, rigidly for walls, through the development for bends.
"""

import math

import FreeCAD as App
import Part

LIN_TOL = 1e-4  # mm
COS_TANGENT = 1.0 - 1e-6
TWO_PI = 2.0 * math.pi


class UnfoldError(ValueError):
    """A shape that cannot be unfolded; the text says why and what to try."""


# -- small geometry helpers ---------------------------------------------------------------------
def face_index(name):
    """'Face7' -> 6."""
    name = str(name)
    if not name.startswith("Face"):
        raise UnfoldError("%s is not a face" % name)
    return int(name[4:]) - 1


def is_planar(face):
    return isinstance(face.Surface, Part.Plane)


def is_cylinder(face):
    return isinstance(face.Surface, Part.Cylinder)


def inner_point(face):
    """A point inside the face (not in a hole, well away from the boundary)."""
    u0, u1, v0, v1 = face.ParameterRange
    steps = 8
    inside = []
    for i in range(1, steps):
        for j in range(1, steps):
            u = u0 + (u1 - u0) * i / float(steps)
            v = v0 + (v1 - v0) * j / float(steps)
            try:
                ok = face.isPartOfDomain(u, v)
            except Exception:
                ok = False
            if ok:
                inside.append(face.Surface.value(u, v))
    if not inside:
        return face.CenterOfMass
    if len(inside) == 1:
        return inside[0]
    wire = face.OuterWire
    best = None
    for p in inside:
        try:
            d = wire.distToShape(Part.Vertex(p))[0]
            for w in face.Wires:
                if not w.isSame(wire):
                    d = min(d, w.distToShape(Part.Vertex(p))[0])
        except Exception:
            d = 0.0
        if best is None or d > best[0]:
            best = (d, p)
    return best[1]


def normal_at(face, point):
    """The outward normal of a face of a solid at a point on it."""
    u, v = face.Surface.parameter(point)
    n = face.normalAt(u, v)
    return n.normalize() if n.Length > 0 else n


def thickness_at(solid, face, point=None):
    """Distance from a point of the face, straight into the material, to the far side."""
    p = point if point is not None else inner_point(face)
    n = normal_at(face, p)
    span = solid.BoundBox.DiagonalLength + 1.0
    ray = Part.makeLine(p, p - n * span)
    try:
        cut = solid.section(ray)
    except Exception as exc:
        raise UnfoldError("the thickness could not be measured: %s" % exc)
    found = [(v.Point - p).Length for v in cut.Vertexes]
    found = [d for d in found if d > 10 * LIN_TOL]
    if not found:
        raise UnfoldError("the thickness could not be measured at that face")
    return min(found)


def _edge_key(edge):
    return edge.hashCode()


def _radial(point, center, axis):
    d = point - center
    return d - axis * d.dot(axis)


def _signed_angle(ref, vec, axis):
    return math.atan2(axis.dot(ref.cross(vec)), ref.dot(vec))


def _rotation_about(center, axis, angle_rad):
    return App.Placement(App.Vector(), App.Rotation(axis, math.degrees(angle_rad)), center)


def _matrix(placement):
    return placement.toMatrix()


def _same_line(p1, d1, p2, d2, tol=1e-3):
    if abs(abs(d1.dot(d2)) - 1.0) > 1e-6:
        return False
    w = p2 - p1
    off = w - d1 * w.dot(d1)
    return off.Length < tol


# -- the face maps --------------------------------------------------------------------------------
class FaceMap:
    """How one skin face goes into the result.

    kind "wall": rigid (App.Matrix). kind "kept": a bend moved rigidly. kind "bend": developed
    from its entry line: parent (App.Matrix, the rigid map of the tangent plane at the entry
    line), center/axis/radius, rho0 (unit radial at entry), sign (the way the face turns),
    tangent (unit, in the entry tangent plane, away from the parent), rn (neutral radius).
    """

    def __init__(self, index, face, kind):
        self.index = index
        self.face = face
        self.kind = kind
        self.rigid = App.Matrix()
        self.parent = App.Matrix()
        self.center = None
        self.axis = None
        self.radius = 0.0
        self.inner_radius = 0.0
        self.rho0 = None
        self.sign = 1.0
        self.tangent = None
        self.rn = 0.0
        self.angle = 0.0
        self.concave = False
        self.normal_in = None  # into the material at the entry line (bends)

    # angle of a point of the bend from its entry line, >= 0 along the face
    def phi(self, point):
        rho = _radial(point, self.center, self.axis)
        if rho.Length < 1e-12:
            return 0.0
        a = self.sign * _signed_angle(self.rho0, rho, self.axis)
        if a < 0.0:
            a = 0.0 if a > -1e-7 else a + TWO_PI
        return a

    def develop_local(self, point):
        """A point of the bend into the tangent plane at its entry line (parent not applied)."""
        phi = self.phi(point)
        back = _rotation_about(self.center, self.axis, -self.sign * phi)
        return back.multVec(point) + self.tangent * (phi * self.rn)

    def map_point(self, point):
        if self.kind == "bend":
            return self.parent.multiply(self.develop_local(point))
        return self.rigid.multiply(point)

    def exit_rigid(self, edge):
        """The rigid map of a neighbour reached across edge (a line of this face)."""
        if self.kind != "bend":
            return App.Matrix(self.rigid)
        mid = edge.valueAt(0.5 * (edge.FirstParameter + edge.LastParameter))
        phi = self.phi(mid)
        turn = _rotation_about(self.center, self.axis, -self.sign * phi)
        move = App.Placement(self.tangent * (phi * self.rn), App.Rotation())
        local = move.multiply(turn).toMatrix()
        return self.parent.multiply(local)

    # backwards (Refold): a point of the developed bend's local tangent space -> folded
    def fold_local(self, point):
        base = self.center + self.rho0 * self.radius
        w = point - base
        along = w.dot(self.axis)
        dist = w.dot(self.tangent)
        height = w.dot(self.rho0)
        phi = dist / self.rn if self.rn > 0 else 0.0
        radial = self.radius + height
        turn = _rotation_about(self.center, self.axis, self.sign * phi)
        p = self.center + self.rho0 * radial + self.axis * along
        return turn.multVec(p)


class Bend:
    """One unfolded bend, for the flat pattern's bend lines and the DXF."""

    def __init__(self, fmap, lines, width):
        self.face_index = fmap.index
        self.angle = math.degrees(fmap.angle)
        self.inner_radius = fmap.inner_radius
        self.up = fmap.concave
        self.allowance = fmap.angle * fmap.rn
        self.width = width
        self.start, self.centre, self.end = lines  # (p1, p2) pairs in the result

    def as_dict(self):
        def pt(v):
            return [round(v.x, 6), round(v.y, 6), round(v.z, 6)]

        return {
            "face": self.face_index + 1,
            "angle": round(self.angle, 6),
            "radius": round(self.inner_radius, 6),
            "up": bool(self.up),
            "allowance": round(self.allowance, 6),
            "start": [pt(p) for p in self.start],
            "centre": [pt(p) for p in self.centre],
            "end": [pt(p) for p in self.end],
        }


# -- mapping edges and faces ------------------------------------------------------------------
def _samples(edge, count):
    a, b = edge.FirstParameter, edge.LastParameter
    return [edge.valueAt(a + (b - a) * i / float(count)) for i in range(count + 1)]


def _collinear(points, tol=1e-6):
    p0, p1 = points[0], points[-1]
    d = p1 - p0
    if d.Length < tol:
        return False
    d = App.Vector(d).normalize()
    for p in points[1:-1]:
        w = p - p0
        if (w - d * w.dot(d)).Length > tol:
            return False
    return True


def _map_edge(edge, fn, oriented=True):
    """The edge with every point sent through fn, as a line when it stays straight, else a
    B-spline through samples."""
    curve = edge.Curve
    if isinstance(curve, Part.Line) or isinstance(curve, Part.LineSegment):
        count = 2
    else:
        span = abs(edge.LastParameter - edge.FirstParameter)
        count = max(12, min(96, int(edge.Length / 0.5) + 4, int(span * 24) + 12))
    pts = [fn(p) for p in _samples(edge, count)]
    closed = (pts[0] - pts[-1]).Length < 1e-7
    if not closed and _collinear(pts):
        return Part.makeLine(pts[0], pts[-1])
    bs = Part.BSplineCurve()
    if closed:
        bs.interpolate(pts[:-1], PeriodicFlag=True)
    else:
        bs.interpolate(pts)
    return bs.toShape()


def _map_wire(wire, fn):
    edges = [_map_edge(e, fn) for e in wire.OrderedEdges]
    try:
        return Part.Wire(edges)
    except Exception:
        return Part.Wire(Part.__sortEdges__(edges))


def develop_face(fmap):
    """The bend face developed into its entry tangent plane (parent not applied)."""
    fn = fmap.develop_local
    outer = _map_wire(fmap.face.OuterWire, fn)
    inner = [_map_wire(w, fn) for w in fmap.face.Wires if not w.isSame(fmap.face.OuterWire)]
    face = Part.makeFace([outer] + inner, "Part::FaceMakerBullseye")
    if face.isNull() or face.Area < 1e-9:
        raise UnfoldError("bend %d could not be developed" % (fmap.index + 1))
    return face


def folded_slab_volume(fmap, thickness):
    """The material under a skin face in the folded solid (exact for walls and bends)."""
    area = fmap.face.Area
    if fmap.kind == "wall":
        return area * thickness
    r = fmap.radius
    if r <= 0:
        return 0.0
    if fmap.concave:
        return area * thickness * (r + thickness / 2.0) / r
    return area * thickness * (r - thickness / 2.0) / r


def _bend_slab_folded(fmap, thickness):
    """The material under a bend face, in the folded solid (for kept bends)."""
    face = fmap.face
    try:
        slab = face.makeOffsetShape(-thickness, 1e-6, fill=True)
        if slab.Volume < 0:
            slab.reverse()
        if slab.isValid() and abs(slab.Volume) > 1e-9:
            return slab
    except Exception:
        pass
    raise UnfoldError("bend %d could not be kept folded" % (fmap.index + 1))


# -- the unfolder -----------------------------------------------------------------------------
class Result:
    """What an unfold gives: the result solid, its bends, the face maps and the thickness."""

    def __init__(self):
        self.shape = None
        self.thickness = 0.0
        self.k_factor = 0.44
        self.maps = []
        self.bends = []
        self.slabs = []  # (FaceMap, slab solid in the result)
        self.stationary = None  # Face of the input
        self.normal = None  # outward normal of the stationary face
        self.flat = False  # every bend unfolded


def _adjacency(shape):
    """edge key -> [face indices]."""
    table = {}
    for i, face in enumerate(shape.Faces):
        for edge in face.Edges:
            key = _edge_key(edge)
            lst = table.setdefault(key, [])
            if i not in lst:
                lst.append(i)
    return table


def _tangent(face_a, face_b, edge):
    try:
        mid = edge.valueAt(0.5 * (edge.FirstParameter + edge.LastParameter))
        na = normal_at(face_a, mid)
        nb = normal_at(face_b, mid)
    except Exception:
        return False
    return na.dot(nb) > COS_TANGENT


def _bend_matches(fmap, picks):
    """picks: list of (center, axis) of the bends the user picked (any face of the bend)."""
    for center, axis in picks:
        if _same_line(fmap.center, fmap.axis, center, axis):
            return True
    return False


def bend_key(face):
    """(center, axis) of a bend face (inner or outer cylinder): what Unfold remembers."""
    cyl = face.Surface
    return (App.Vector(cyl.Center), App.Vector(cyl.Axis).normalize())


def unfold(shape, face_name, k_factor, bends=None, thickness=None, check=True):
    """Unfold the solid shape. face_name: the stationary face ('FaceN' of shape). bends: None
    for every bend, else a list of bend_key(face) of the bends to unfold. Returns a Result.
    Raises UnfoldError with the reason."""
    if shape is None or shape.isNull():
        raise UnfoldError("there is no solid to unfold")
    solids = shape.Solids
    if len(solids) != 1:
        raise UnfoldError("the body must be one solid (it has %d)" % len(solids))
    solid = solids[0]
    index = face_index(face_name)
    if index >= len(shape.Faces):
        raise UnfoldError("%s does not exist any more" % face_name)
    # face indices of shape and of its single solid are the same for a one-solid shape
    faces = solid.Faces
    start = faces[index]
    if not is_planar(start):
        raise UnfoldError(
            "the stationary face must be a flat face of a wall (a top or bottom face)"
        )
    T = thickness if thickness else thickness_at(solid, start)
    if T <= LIN_TOL:
        raise UnfoldError("the sheet has no thickness at that face")
    # a top/bottom face is wider than the thickness; an edge face is as wide as it
    if start.Area / max(e.Length for e in start.Edges) <= T * 1.01:
        raise UnfoldError(
            "that is an edge face of the sheet: pick a wide top or bottom face of a wall"
        )
    k = float(k_factor)
    result = Result()
    result.thickness = T
    result.k_factor = k
    result.stationary = start
    result.normal = normal_at(start, inner_point(start))
    adj = _adjacency(solid)

    first = FaceMap(index, start, "wall")
    maps = {index: first}
    order = [first]
    queue = [first]
    all_bends = bends is None
    picks = [] if bends is None else list(bends)
    while queue:
        cur = queue.pop(0)
        for edge in cur.face.Edges:
            for other in adj.get(_edge_key(edge), []):
                if other == cur.index:
                    continue
                face = faces[other]
                if not _tangent(cur.face, face, edge):
                    continue
                if other in maps:
                    _check_loop(cur, maps[other], edge, T)
                    continue
                fmap = _new_map(other, face, cur, edge, T, k, all_bends, picks)
                maps[other] = fmap
                order.append(fmap)
                queue.append(fmap)
    result.maps = order
    if check:
        _check_fill(solid, order, T)
    slabs = []
    for fmap in order:
        slabs.append((fmap, _slab(fmap, T)))
    result.slabs = slabs
    shapes = [s for _m, s in slabs]
    if len(shapes) == 1:
        fused = shapes[0]
    else:
        fused = shapes[0].fuse(shapes[1:])
    try:
        fused = fused.removeSplitter()
    except Exception:
        pass
    total = sum(s.Volume for s in shapes)
    if check and fused.Volume < total - max(1e-3, total * 1e-4):
        raise UnfoldError(
            "the flat shape overlaps itself (%.3f mm3 counted twice): add a Rip or "
            "change the stationary face" % (total - fused.Volume)
        )
    if len(fused.Solids) != 1:
        raise UnfoldError("the unfolded shape falls apart into %d pieces" % len(fused.Solids))
    result.shape = fused.Solids[0]
    result.flat = all(m.kind != "kept" for m in order)
    result.bends = [_bend_lines(m, T) for m in order if m.kind == "bend"]
    return result


def _new_map(index, face, parent, edge, T, k, all_bends, picks):
    rigid = parent.exit_rigid(edge)
    if is_planar(face):
        fmap = FaceMap(index, face, "wall")
        fmap.rigid = rigid
        return fmap
    if not is_cylinder(face):
        raise UnfoldError(
            "face %d is curved in two directions (not a bend): sheet metal is made of flat "
            "walls and round bends only" % (index + 1)
        )
    cyl = face.Surface
    axis = App.Vector(cyl.Axis).normalize()
    center = App.Vector(cyl.Center)
    fmap = FaceMap(index, face, "bend")
    fmap.center = center
    fmap.axis = axis
    fmap.radius = cyl.Radius
    mid = edge.valueAt(0.5 * (edge.FirstParameter + edge.LastParameter))
    rho0 = _radial(mid, center, axis)
    if rho0.Length < 1e-9:
        raise UnfoldError("bend %d has no radius" % (index + 1))
    fmap.rho0 = App.Vector(rho0).normalize()
    n = normal_at(face, mid)
    fmap.concave = n.dot(fmap.rho0) < 0  # normal toward the axis: the inside of the bend
    fmap.normal_in = -n
    fmap.inner_radius = fmap.radius if fmap.concave else fmap.radius - T
    if fmap.inner_radius < -LIN_TOL:
        raise UnfoldError(
            "bend %d is tighter than the sheet is thick (radius %.3f < %.3f)"
            % (index + 1, fmap.radius, T)
        )
    fmap.inner_radius = max(0.0, fmap.inner_radius)
    fmap.rn = fmap.inner_radius + k * T
    probe = inner_point(face)
    turn = _signed_angle(fmap.rho0, _radial(probe, center, axis), axis)
    fmap.sign = 1.0 if turn >= 0 else -1.0
    fmap.tangent = axis.cross(fmap.rho0) * fmap.sign
    fmap.angle = max(fmap.phi(v.Point) for v in face.Vertexes) if face.Vertexes else 0.0
    if all_bends or _bend_matches(fmap, picks):
        fmap.parent = rigid
    else:
        fmap.kind = "kept"
        fmap.rigid = rigid
    return fmap


def _check_loop(cur, other, edge, T):
    """Two walked faces meet again: their maps must agree on the shared edge, else the
    sheet closes on itself (a tube, a box) and needs a Rip."""
    mid = edge.valueAt(0.5 * (edge.FirstParameter + edge.LastParameter))
    if cur.kind == "kept" and other.kind == "kept":
        return
    a = cur.map_point(mid)
    b = other.map_point(mid)
    if (a - b).Length > max(1e-3, T * 1e-3):
        raise UnfoldError(
            "the sheet closes on itself (a closed loop, like a tube or a box): add a Rip "
            "to open it, then unfold"
        )


def _check_fill(solid, maps, T):
    want = solid.Volume
    have = sum(folded_slab_volume(m, T) for m in maps)
    if abs(have - want) > max(1e-2, want * 2e-3):
        sharp = _sharp_corner(solid, maps, T)
        if sharp:
            raise UnfoldError(
                "edge %s is a sharp corner between two walls, not a bend: fillet it (inside "
                "with the bend radius, outside with radius + thickness) or Rip it" % sharp
            )
        raise UnfoldError(
            "the body is not one sheet of even thickness %.3f mm (the walls and bends found "
            "from that face hold %.1f of its %.1f mm3)" % (T, have, want)
        )


def _sharp_corner(solid, maps, T):
    """The name of an edge where a walked face meets a wide face at a sharp angle."""
    walked = set(m.index for m in maps)
    adj = _adjacency(solid)
    faces = solid.Faces
    edges = solid.Edges
    keys = {_edge_key(e): i for i, e in enumerate(edges)}
    for m in maps:
        for edge in m.face.Edges:
            for other in adj.get(_edge_key(edge), []):
                if other in walked or other == m.index:
                    continue
                face = faces[other]
                if not is_planar(face):
                    continue
                # an edge face of the sheet is about T wide; a wall is wider
                if face.Area > 2.5 * T * edge.Length:
                    i = keys.get(_edge_key(edge))
                    if i is not None:
                        return "Edge%d" % (i + 1)
    return None


def _slab(fmap, T):
    if fmap.kind == "wall":
        n = normal_at(fmap.face, inner_point(fmap.face))
        slab = fmap.face.extrude(n * (-T))
        out = slab.copy()
        out.transformShape(fmap.rigid)
        return out
    if fmap.kind == "kept":
        slab = _bend_slab_folded(fmap, T)
        out = slab.copy()
        out.transformShape(fmap.rigid)
        return out
    flat = develop_face(fmap)
    slab = flat.extrude(fmap.normal_in * T)
    out = slab.copy()
    out.transformShape(fmap.parent)
    return out


def _bend_lines(fmap, T):
    """Start (entry), centre and end lines of a bend on the stationary side, in the result."""
    lo = hi = None
    for v in fmap.face.Vertexes:
        s = (v.Point - fmap.center).dot(fmap.axis)
        lo = s if lo is None else min(lo, s)
        hi = s if hi is None else max(hi, s)
    for e in fmap.face.Edges:
        for p in _samples(e, 8):
            s = (p - fmap.center).dot(fmap.axis)
            lo, hi = min(lo, s), max(hi, s)
    base = fmap.center + fmap.rho0 * fmap.radius
    base = base - fmap.axis * (base - fmap.center).dot(fmap.axis)

    def line(phi):
        turn = _rotation_about(fmap.center, fmap.axis, fmap.sign * phi)
        p1 = turn.multVec(base + fmap.axis * lo)
        p2 = turn.multVec(base + fmap.axis * hi)
        return (fmap.map_point(p1), fmap.map_point(p2))

    lines = (line(0.0), line(fmap.angle / 2.0), line(fmap.angle))
    return Bend(fmap, lines, hi - lo)


# -- flat pattern frame -------------------------------------------------------------------------
def flat_frame(result):
    """A placement that lays the result on XY: the stationary face at z = 0 facing +Z, its
    longest straight edge along +X, the outline's lower-left corner at the origin."""
    face = result.stationary
    n = App.Vector(result.normal).normalize()
    best = None
    for e in face.Edges:
        if isinstance(e.Curve, (Part.Line, Part.LineSegment)) and (
            best is None or e.Length > best.Length
        ):
            best = e
    if best is not None:
        x = best.Vertexes[-1].Point - best.Vertexes[0].Point
    else:
        x = App.Vector(1, 0, 0) if abs(n.x) < 0.9 else App.Vector(0, 1, 0)
    x = x - n * x.dot(n)
    x.normalize()
    y = n.cross(x)
    origin = face.Vertexes[0].Point
    m = App.Matrix(
        x.x, y.x, n.x, origin.x, x.y, y.y, n.y, origin.y, x.z, y.z, n.z, origin.z, 0, 0, 0, 1
    )
    to_flat = m.inverse()
    moved = result.shape.copy()
    moved.transformShape(to_flat)
    bb = moved.BoundBox
    shift = App.Matrix()
    shift.move(App.Vector(-bb.XMin, -bb.YMin, 0))
    return shift.multiply(to_flat)


def flat_top_face(flat_shape):
    """The face of a laid-out flat solid at z = 0 facing +Z (the stationary side)."""
    best = None
    for f in flat_shape.Faces:
        if not is_planar(f):
            continue
        n = normal_at(f, inner_point(f))
        if n.z > 1 - 1e-6 and abs(f.BoundBox.ZMax) < 1e-4 and abs(f.BoundBox.ZMin) < 1e-4:
            if best is None or f.Area > best.Area:
                best = f
    return best


# -- refold: the flat state's cuts back onto the folded solid ---------------------------------
def refold(folded, result, flat_after, gap=0.02):
    """The folded solid with the material removed from result.shape in flat_after removed
    from it too (walls rigidly, bends through the development). Material added in the flat
    state is added back on walls; added across a bend it is refused."""
    before = result.shape
    removed = before.cut(flat_after)
    added = flat_after.cut(before)
    tools = []
    for fmap, slab in result.slabs:
        if removed.Volume > 1e-6:
            piece = removed.common(slab)
            if piece.Volume > 1e-6:
                tools.extend(_fold_piece(fmap, piece, result.thickness, gap))
    out = folded
    if tools:
        out = out.cut(tools)
    adds = []
    if added.Volume > 1e-6:
        for fmap, slab in result.slabs:
            near = added.common(_grown(slab, result.thickness))
            if near.Volume <= 1e-6:
                continue
            if fmap.kind == "bend":
                raise UnfoldError(
                    "material added across bend %d in the unfolded state cannot be folded "
                    "back: add it after the Refold" % (fmap.index + 1)
                )
        piece = added
        for fmap, _slab in result.slabs:
            if fmap.kind != "bend":
                back = piece.copy()
                back.transformShape(fmap.rigid.inverse())
                adds.append(back)
                break
    if adds:
        out = out.fuse(adds)
    try:
        out = out.removeSplitter()
    except Exception:
        pass
    return out


def _grown(slab, T):
    bb = slab.BoundBox
    return Part.makeBox(
        bb.XLength + 2 * T,
        bb.YLength + 2 * T,
        bb.ZLength + 2 * T,
        App.Vector(bb.XMin - T, bb.YMin - T, bb.ZMin - T),
    )


def _fold_piece(fmap, piece, T, gap):
    if fmap.kind != "bend":
        back = piece.copy()
        back.transformShape(fmap.rigid.inverse())
        return [back]
    local = piece.copy()
    local.transformShape(fmap.parent.inverse())
    # the cut's outline at the stationary-side plane of the bend (h = 0 .. -T); cuts through
    # the sheet are straight in the flat, so one section half way through is the outline
    base = fmap.center + fmap.rho0 * fmap.radius
    mid_h = -T / 2.0 if fmap.normal_in.dot(fmap.rho0) < 0 else T / 2.0
    plane_pt = base + fmap.rho0 * mid_h
    wires = local.slice(fmap.rho0, plane_pt.dot(fmap.rho0))
    tools = []
    lo_r = fmap.inner_radius - gap
    hi_r = fmap.inner_radius + T + gap
    for wire in wires:
        # dense steps: a straight edge of the flat across the bend folds into an arc
        step = max(0.01, min(0.2, fmap.rn * 0.03))
        pts = wire.discretize(Distance=step)
        if len(pts) > 1 and (pts[0] - pts[-1]).Length < 1e-7:
            pts = pts[:-1]
        if len(pts) < 3:
            continue
        rings = []
        for radius in (lo_r, hi_r):
            h = radius - fmap.radius
            ring = [fmap.fold_local(p + fmap.rho0 * (h - (p - base).dot(fmap.rho0))) for p in pts]
            ring.append(ring[0])
            rings.append(Part.makePolygon(ring))
        try:
            tool = Part.makeLoft(rings, True, True)
            if tool.Volume < 0:
                tool.reverse()
            tools.append(tool)
        except Exception as exc:
            raise UnfoldError(
                "the cut across bend %d could not be folded: %s" % (fmap.index + 1, exc)
            )
    return tools
