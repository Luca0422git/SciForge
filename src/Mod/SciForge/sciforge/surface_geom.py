# SPDX-License-Identifier: LGPL-2.1-or-later
"""The geometry of SciForge's surface tools, on FreeCAD's Part module (OpenCASCADE).

No document and no Qt: every function takes shapes in design coordinates and returns a new
shape, so the feature (surface.py), the golden-model builder and headless tests share it.
Problems raise surface_core.SurfaceError with a message that says why and what to try.

    extrude_curves, revolve_curves, sweep_curves, loft_sections     CREATE from curves
    patch, ruled, offset_faces, thicken, fill_cells                  CREATE from a design
    trim, untrim, extend, stitch, unstitch, reverse                  MODIFY a surface body
    cells_for_trim, boundary_cells                                   the pieces to click
"""

import math

import FreeCAD as App
import Part

from . import surface_core as core
from .surface_core import NeedsPick, SurfaceError

TOL = 1e-6
SAME = 1e-4  # mm: two points closer than this are one point
SAMPLES = 32  # points per curve where a ruled / extended edge is fitted
TANGENCY_TOLERANCE = math.radians(2.0)  # a Tangent / Curvature patch may be off by this


# -- small helpers -------------------------------------------------------------------------------
def vec(value):
    return App.Vector(*value) if not isinstance(value, App.Vector) else App.Vector(value)


def unit(v):
    v = App.Vector(v)
    if v.Length < 1e-12:
        raise SurfaceError("A direction of zero length.")
    v.normalize()
    return v


def compound(shapes):
    shapes = [s for s in shapes if s is not None and not s.isNull()]
    if not shapes:
        return Part.Shape()
    if len(shapes) == 1:
        return shapes[0]
    return Part.makeCompound(shapes)


def bound_box(shapes):
    box = None
    for shape in shapes:
        if shape is None or shape.isNull():
            continue
        b = shape.BoundBox
        if box is None:
            box = App.BoundBox(b)
        else:
            box.add(b)
    return box


def reach(shapes, extra=0.0):
    """A length surely longer than anything in `shapes` (for endless planes and lines)."""
    box = bound_box(shapes)
    size = box.DiagonalLength if box is not None else 100.0
    centre = box.Center if box is not None else App.Vector()
    return max(size, 1.0) * 4.0 + centre.Length + extra + 10.0


def plane_face(point, normal, size):
    """A square face of side 2*size centred on `point`, square to `normal`."""
    n = unit(normal)
    return Part.Plane(vec(point), n).toShape(-size, size, -size, size)


def wires_of(edges):
    """The edges sorted into connected wires (Part.sortEdges), each a Part.Wire."""
    edges = [e for e in edges if e is not None and not e.isNull()]
    if not edges:
        return []
    try:
        groups = Part.sortEdges(edges)
    except Exception:
        groups = [[e] for e in edges]
    wires = []
    for group in groups:
        try:
            wires.append(Part.Wire(group))
        except Exception:
            wires.extend(Part.Wire([e]) for e in group)
    return wires


def plane_of(shapes):
    """(point, normal) of the plane the shapes lie in, or None (not flat, or a line)."""
    shape = compound([s.copy() for s in shapes])
    try:
        plane = shape.findPlane()
    except Exception:
        plane = None
    if plane is None:
        return None
    return App.Vector(plane.Position), unit(plane.Axis)


def free_edges(shape):
    """Boundary edges of a surface: edges of only one face (seams of round faces are not
    boundaries). The edges are `shape`'s own (isSame works on them)."""
    found = []
    if shape is None or shape.isNull():
        return found
    in_shell = []
    for shell in shape.Shells:
        in_shell.extend(shell.Faces)
        try:
            found.extend(shell.getFreeEdges().Edges)
        except Exception:
            pass
    for face in shape.Faces:
        if any(face.isSame(f) for f in in_shell):
            continue
        try:
            found.extend(Part.Shell([face]).getFreeEdges().Edges)
        except Exception:
            pass
    own = []
    for edge in found:
        match = next((e for e in shape.Edges if e.isSame(edge)), None)
        if match is None:
            match = _same_place_edge(shape.Edges, edge)
        if match is not None and not any(match.isSame(o) for o in own):
            own.append(match)
    return own


def _same_place_edge(edges, edge):
    mid = edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2.0)
    best = None
    for e in edges:
        try:
            d = e.distToShape(Part.Vertex(mid))[0]
        except Exception:
            continue
        if d < SAME and abs(e.Length - edge.Length) < SAME * 10 and (best is None or d < best[0]):
            best = (d, e)
    return best[1] if best else None


def is_free(shape, edge):
    return any(e.isSame(edge) for e in free_edges(shape))


def faces_of_edge(shape, edge):
    try:
        return list(shape.ancestorsOfType(edge, Part.Face))
    except Exception:
        return []


def edge_point(edge, fraction):
    u = edge.FirstParameter + (edge.LastParameter - edge.FirstParameter) * fraction
    return edge.valueAt(u), unit(edge.tangentAt(u)) if _has_tangent(edge, u) else None


def _has_tangent(edge, u):
    try:
        return edge.tangentAt(u).Length > 1e-12
    except Exception:
        return False


def face_normal_at(face, point):
    """The face's outward-facing normal at (near) `point` (respects the face orientation)."""
    u, v = face.Surface.parameter(point)
    return unit(face.normalAt(u, v))


def away_in_face(face, edge, point, tangent):
    """The direction in `face`, square to `edge` at `point`, pointing out of the face."""
    n = face_normal_at(face, point)
    side = unit(n.cross(tangent))
    size = max(face.BoundBox.DiagonalLength, 1.0)
    for eps in (1e-4, 1e-3, 1e-2):
        probe = point - side * (size * eps)
        try:
            u, v = face.Surface.parameter(probe)
            if face.isInside(face.valueAt(u, v), size * eps * 0.5, True):
                return side
        except Exception:
            pass
        probe = point + side * (size * eps)
        try:
            u, v = face.Surface.parameter(probe)
            if face.isInside(face.valueAt(u, v), size * eps * 0.5, True):
                return side * -1.0
        except Exception:
            pass
    return side


def face_point(face):
    """A point well inside the face (on it), to stand for it."""
    try:
        com = face.CenterOfMass
        u, v = face.Surface.parameter(com)
        p = face.valueAt(u, v)
        if face.isInside(p, 1e-6, True) and _inner_margin(face, p) > 1e-3:
            return p
    except Exception:
        pass
    u0, u1, v0, v1 = face.ParameterRange
    best = None
    for i in range(1, 12):
        for j in range(1, 12):
            u = u0 + (u1 - u0) * i / 12.0
            v = v0 + (v1 - v0) * j / 12.0
            try:
                p = face.valueAt(u, v)
                if not face.isInside(p, 1e-6, True):
                    continue
                margin = _inner_margin(face, p)
            except Exception:
                continue
            if best is None or margin > best[0]:
                best = (margin, p)
    if best is not None:
        return best[1]
    return face.CenterOfMass


def _inner_margin(face, point):
    try:
        return face.OuterWire.distToShape(Part.Vertex(point))[0]
    except Exception:
        return 0.0


def solid_point(solid):
    """A point inside the solid."""
    try:
        com = solid.CenterOfMass
        if solid.isInside(com, 1e-6, False):
            return com
    except Exception:
        pass
    size = max(solid.BoundBox.DiagonalLength, 1.0)
    for face in sorted(solid.Faces, key=lambda f: -f.Area):
        p = face_point(face)
        n = face_normal_at(face, p)
        for eps in (1e-3, 1e-2, 5e-2):
            q = p - n * (size * eps)
            if solid.isInside(q, 1e-7, False):
                return q
            q = p + n * (size * eps)
            if solid.isInside(q, 1e-7, False):
                return q
    return solid.CenterOfMass


def distance(shape, point):
    try:
        return shape.distToShape(Part.Vertex(vec(point)))[0]
    except Exception:
        return float("inf")


def sew(faces, tolerance=0.0):
    """The faces sewn into shells where their edges meet (gaps up to `tolerance` closed).
    Returns a Shell, a Face or a Compound."""
    faces = [f.copy() for f in faces]
    if not faces:
        return Part.Shape()
    if len(faces) == 1:
        return faces[0]
    comp = Part.makeCompound(faces)
    sewn = comp.copy()
    try:
        sewn.sewShape()
    except Exception:
        sewn = comp
    if tolerance > 1e-6 and _open_count(sewn) > 0:
        # FreeCAD 1.1.4's sewShape() ignores its tolerance (TopoShapePy::sewShape parses it
        # and drops it): OpenCASCADE's shell sewing takes the shape's own tolerance, so the
        # faces are given that tolerance first (Fusion's "tolerant edges").
        loose = Part.makeCompound([f.copy() for f in faces])
        try:
            loose.fixTolerance(tolerance)
            shell = Part.Shell(loose.Faces)
            if _open_count(shell) < _open_count(sewn):
                sewn = shell
        except Exception:
            pass
    return sewn


def _open_count(shape):
    try:
        return len(free_edges(shape))
    except Exception:
        return 0


def shells_or_faces(shape):
    """The connected pieces of a surface: its shells, plus faces in no shell."""
    pieces = list(shape.Shells)
    taken = [f for s in pieces for f in s.Faces]
    for face in shape.Faces:
        if not any(face.isSame(t) for t in taken):
            pieces.append(face)
    return pieces


def surface_result(shape):
    """A surface result: faces only, at least one, valid."""
    if shape is None or shape.isNull() or not shape.Faces:
        raise SurfaceError("The result has no surface. Check the picks and the values.")
    return shape


# -- CREATE: Extrude -----------------------------------------------------------------------------
def extrude_curves(edges, normal, options, to_object=None):
    """Fusion's surface Extrude of open or closed curves along `normal` (the sketch's).
    options: start / start_offset, direction / distance / distance2 / measurement, taper /
    taper2, extent ('distance' | 'to_object' with `to_object` = (point, normal) of a plane)."""
    o = core.with_defaults("extrude", options)
    core.check_values("extrude", o)
    n = unit(normal)
    wires = wires_of(edges)
    if not wires:
        raise NeedsPick("Select the profile: sketch curves or edges of a body.")
    flat = plane_of(wires)
    if flat is not None and abs(abs(flat[1].dot(n)) - 1.0) > 1e-6:
        flat = None  # curves in a plane not square to the direction: still fine
    shift = n * (float(o["start_offset"]) if o["start"] == "offset" else 0.0)
    if o["extent"] == "to_object":
        if to_object is None:
            raise NeedsPick("Select the object to extrude to: a plane or a flat face.")
        return _extrude_to_plane(wires, n, shift, to_object)
    start, end = core.extrude_range(o["direction"], o["distance"], o["distance2"], o["measurement"])
    faces = []
    for wire in wires:
        base = wire.copy()
        base.translate(shift)
        taper_one = float(o["taper"])
        taper_two = float(o["taper2"]) if o["direction"] == "two_sides" else taper_one
        if end > 1e-9:
            faces.extend(_extrude_piece(base, n, end, taper_one, flat).Faces)
        if start < -1e-9:
            faces.extend(_extrude_piece(base, n, start, taper_two, flat).Faces)
    return surface_result(sew(faces))


def _extrude_piece(wire, n, length, taper, flat):
    if abs(taper) < 1e-9:
        return wire.extrude(n * length)
    delta = abs(length) * math.tan(math.radians(taper))
    far = _offset_in_plane(wire, n, delta)
    far.translate(n * length)
    try:
        return Part.makeLoft([wire, far], False, True)
    except Exception:
        pieces = []
        for a, b in zip(wire.OrderedEdges, far.OrderedEdges):
            pieces.append(Part.makeRuledSurface(a, b))
        return sew([f for p in pieces for f in p.Faces])


def _offset_in_plane(wire, n, delta):
    """`wire` moved sideways in its plane by `delta`: a closed curve grows outwards (a
    negative delta shrinks it); an open curve moves to its left (looking along `n`)."""
    if wire.isClosed():
        try:
            out = wire.makeOffset2D(delta, 2, False, False, False)
            if out.Wires:
                return out.Wires[0]
        except Exception as exc:
            raise SurfaceError(
                "The taper shrinks the profile to nothing (%s). Use a smaller angle or "
                "distance." % exc
            )
    edges = [_offset_edge(e, n, delta) for e in wire.OrderedEdges]
    return Part.Wire(edges) if _joined(edges) else Part.Wire(edges[:1])


def _joined(edges):
    for a, b in zip(edges, edges[1:]):
        if (a.Vertexes[-1].Point - b.Vertexes[0].Point).Length > SAME:
            return False
    return True


def _offset_edge(edge, n, delta):
    curve = edge.Curve
    a, b = edge.FirstParameter, edge.LastParameter
    if curve.TypeId in ("Part::GeomLine", "Part::GeomLineSegment"):
        p0, p1 = edge.valueAt(a), edge.valueAt(b)
        side = unit(n.cross(unit(p1 - p0)))
        return Part.LineSegment(p0 + side * delta, p1 + side * delta).toShape()
    points = []
    for i in range(SAMPLES + 1):
        u = a + (b - a) * i / float(SAMPLES)
        p = edge.valueAt(u)
        side = unit(n.cross(unit(edge.tangentAt(u))))
        points.append(p + side * delta)
    spline = Part.BSplineCurve()
    spline.interpolate(points)
    return spline.toShape()


def _extrude_to_plane(wires, n, shift, target):
    point, normal = vec(target[0]), unit(target[1])
    if abs(normal.dot(n)) < 1e-6:
        raise SurfaceError(
            "The object is parallel to the extrude direction, so the extrusion never "
            "reaches it. Pick a plane or face across the direction."
        )
    faces = []
    for wire in wires:
        base = wire.copy()
        base.translate(shift)
        heights = [(point - v.Point).dot(normal) / n.dot(normal) for v in base.Vertexes]
        if not heights:
            continue
        if all(abs(h) < 1e-7 for h in heights):
            raise SurfaceError("The profile already lies on that object. Pick another one.")
        if max(heights) > 1e-7 and min(heights) < -1e-7:
            raise SurfaceError("The object crosses the profile. Pick one beside the profile.")
        flat = max(abs(h) for h in heights) - min(abs(h) for h in heights) < 1e-7
        if flat:
            faces.extend(base.extrude(n * heights[0]).Faces)
            continue
        sign = 1.0 if max(heights) > 0 else -1.0
        far = max(abs(h) for h in heights) * 1.5 + reach([base])
        long = base.extrude(n * sign * far)
        keep = _halfspace(point, normal * (-1.0 if normal.dot(n * sign) > 0 else 1.0), [long])
        faces.extend(long.common(keep).Faces)
    return surface_result(sew(faces))


def _halfspace(point, keep_dir, around):
    """A big box with one face on the plane through `point`, lying on `keep_dir`'s side."""
    size = reach(around)
    k = unit(keep_dir)
    square = plane_face(point, k, size)
    return square.extrude(k * size)


# -- CREATE: Revolve -------------------------------------------------------------------------------
def revolve_curves(edges, center, axis, options):
    o = core.with_defaults("revolve", options)
    core.check_values("revolve", o)
    wires = wires_of(edges)
    if not wires:
        raise NeedsPick("Select the profile: sketch curves or edges of a body.")
    a = unit(axis)
    c = vec(center)
    _check_axis(wires, c, a)
    start, sweep = core.revolve_range(o["type"], o["direction"], o["angle"], o["angle2"])
    faces = []
    for wire in wires:
        base = wire.copy()
        if abs(start) > 1e-9:
            base.rotate(c, a, start)
        try:
            faces.extend(base.revolve(c, a, sweep).Faces)
        except Exception as exc:
            raise SurfaceError("The curves cannot be turned about that axis (%s)." % exc)
    return surface_result(sew(faces))


def _check_axis(wires, c, a):
    line = Part.LineSegment(c - a * 1e6, c + a * 1e6).toShape()
    for wire in wires:
        try:
            dist = wire.distToShape(line)[0]
        except Exception:
            continue
        if dist > SAME:
            continue
        # The curves touch the axis: fine at an end, not where they cross it (points on
        # both sides of the axis).
        radial = []
        for v in wire.discretize(64):
            r = (v - c) - a * (v - c).dot(a)
            if r.Length > SAME:
                radial.append(r)
        if any(r1.dot(r2) < 0 for r1 in radial for r2 in radial[:8]):
            raise SurfaceError(
                "The axis crosses the profile, so the surface would cut through itself. "
                "Pick an axis beside the profile."
            )


# -- CREATE: Sweep ---------------------------------------------------------------------------------
def sweep_curves(profile_edges, path, options):
    """`path`: a curves.Path. The profile curves (open or closed) are carried along it from
    where they sit (sweep.Plan: Distance, Distance Two)."""
    from . import curves, sweep as sweep_core

    o = core.with_defaults("sweep", options)
    core.check_values("sweep", o)
    wires = wires_of(profile_edges)
    if not wires:
        raise NeedsPick("Select the profile: sketch curves or edges of a body.")
    centre = bound_box(wires).Center
    try:
        point = path.wire().distToShape(Part.Vertex(centre))[1][0][0]
    except Exception:
        point = path.start
    s_p = path.length_at(point)
    try:
        plan = sweep_core.Plan(
            path,
            s_p,
            {"distance": o["distance"], "distance2": o["distance2"], "type": "single"},
        )
    except Exception as exc:
        raise SurfaceError(str(exc))
    faces = []
    for spine, sign in plan.side_paths():
        aux = None
        if abs(float(o["twist"])) > 1e-9 and o["orientation"] == "perpendicular":
            turn = float(o["twist"]) * spine.length / max(plan.side1 + plan.side2, 1e-9) * sign
            radius = max(1.0, bound_box(wires).DiagonalLength)
            aux = curves.twist_guide(spine, turn, radius)
        for wire in wires:
            faces.extend(_pipe(spine.wire(), wire, o["orientation"], aux).Faces)
    return surface_result(sew(faces))


def _pipe(spine, wire, orientation, aux=None):
    try:
        mk = Part.BRepOffsetAPI.MakePipeShell(spine)
        mk.setTolerance(1e-6, 1e-4, 1e-2)
        mk.setTransitionMode(2)  # right corner, like Fusion's mitred bend
        if aux is not None:
            mk.setAuxiliarySpine(aux, True, 0)
        elif orientation == "parallel":
            mk.setTrihedronMode(App.Vector(0, 0, 0), App.Vector(0, 0, 1))
        else:
            mk.setFrenetMode(False)
        mk.add(wire, False, False)
        if not mk.isReady():
            raise SurfaceError("The sweep cannot be set up with this profile and path.")
        mk.build()
        return mk.shape()
    except SurfaceError:
        raise
    except Exception as exc:
        raise SurfaceError(
            "The profile cannot follow this path (%s). A path that turns sharper than the "
            "profile is wide often causes this." % (str(exc) or type(exc).__name__)
        )


# -- CREATE: Loft ----------------------------------------------------------------------------------
def loft_sections(sections, closed=False):
    """`sections`: wires (open or closed curves) or Part.Vertex (a point at either end)."""
    if len(sections) < 2:
        raise NeedsPick("Select at least two profiles, in loft order.")
    kinds = set()
    for i, s in enumerate(sections):
        if s.ShapeType == "Vertex":
            if 0 < i < len(sections) - 1:
                raise SurfaceError("A point can only be the first or the last profile.")
            continue
        kinds.add(s.isClosed())
    if len(kinds) > 1:
        raise SurfaceError(
            "Some profiles are closed and some are open. Loft open curves with open curves, "
            "closed with closed."
        )
    if closed and len(sections) < 3:
        raise SurfaceError("A closed loft needs at least three profiles.")
    try:
        shape = Part.makeLoft(list(sections), False, False, bool(closed))
    except Exception as exc:
        raise SurfaceError(
            "The profiles cannot be lofted (%s). Check their order and that each is one "
            "connected curve." % exc
        )
    return surface_result(shape)


# -- CREATE: Patch ---------------------------------------------------------------------------------
def patch(boundary, continuity="connected", interior=(), points=()):
    """Fusion's Patch: a surface filling closed boundary loops.

    boundary: [(edge, support face or None)]; a support face (the face of a body the edge
    bounds) carries the continuity (Connected G0, Tangent G1, Curvature G2); sketch curves
    have none (Fusion ignores the continuity for them too). interior: curves the patch must
    pass through; points: Part.Vertex / App.Vector it must pass through."""
    order = core.CONTINUITY[continuity]
    edges = [e for e, _f in boundary]
    wires = wires_of(edges)
    if not wires:
        raise NeedsPick("Select the boundary: edges of a body or sketch curves.")
    open_wires = [w for w in wires if not w.isClosed()]
    if open_wires:
        raise SurfaceError(
            "The boundary is not closed: %d of its curves do not meet another one at both "
            "ends. Pick curves that form a closed loop." % len(open_wires[0].Edges)
        )
    supports = [(e, f) for e, f in boundary if f is not None]
    flat = plane_of(wires)
    plain = (order == 0 or not supports) and not interior and not points
    if flat is not None and plain:
        try:
            face = Part.makeFace(wires, "Part::FaceMakerBullseye")
            return surface_result(face)
        except Exception:
            pass
    faces = []
    for wire in wires:
        faces.append(_fill(wire, boundary, order, interior, points))
    return surface_result(compound(faces))


_G2 = {}


def g2_available():
    """True when FreeCAD hands Curvature (G2) continuity to OpenCASCADE: stock FreeCAD
    1.1.4 turns its order 2 into C1, which OpenCASCADE's filling ignores (the patch stays
    flat); SciForge's core patch #14 fixes that and also takes 3 for G2, which is how its
    presence is told here."""
    if "ok" not in _G2:
        try:
            mk = Part.BRepOffsetAPI.MakeFilling()
            edge = Part.LineSegment(App.Vector(0, 0, 0), App.Vector(1, 0, 0)).toShape()
            mk.add(edge, Part.makePlane(1, 1), 3, True)
            _G2["ok"] = True
        except Exception:
            _G2["ok"] = False
    return _G2["ok"]


def _occ_order(order):
    return 3 if order >= 2 else order


def _fill(wire, boundary, order, interior, points):
    if order >= 2 and any(f is not None for _e, f in boundary) and not g2_available():
        raise SurfaceError(
            "Curvature continuity needs SciForge's next full build: FreeCAD 1.1.4 passes it "
            "to OpenCASCADE as a setting OpenCASCADE ignores (core patch #14 fixes it). Use "
            "Continuity Tangent for now."
        )
    mk = Part.BRepOffsetAPI.MakeFilling()
    for edge in wire.OrderedEdges:
        support = None
        for e, f in boundary:
            if f is not None and (e.isSame(edge) or _same_place_edge([e], edge) is not None):
                support = f
                break
        if support is not None and order > 0:
            mk.add(edge, support, _occ_order(order), True)
        else:
            mk.add(edge, 0, True)
    for edge in interior:
        mk.add(edge, 0, False)
    for point in points:
        mk.add(vec(point.Point if hasattr(point, "Point") else point))
    try:
        mk.build()
        shape = mk.shape()
    except Exception as exc:
        if order > 0:
            raise SurfaceError(
                "A patch %s to the faces around these edges cannot be built here (%s). Try "
                "Continuity Connected, or patch a smaller opening."
                % ("tangent" if order == 1 else "curvature-continuous", exc)
            )
        raise SurfaceError("The boundary cannot be patched (%s)." % exc)
    face = shape.Faces[0] if shape.Faces else None
    if face is None or not face.isValid():
        raise SurfaceError("The patch came out broken. Try Continuity Connected.")
    if order > 0 and any(f is not None for _e, f in boundary):
        # OpenCASCADE's patch bends a flat sheet along its normal: it cannot turn to meet
        # walls that rise square to it (a cylinder's rim), and then silently stays flat.
        # Fusion would make a dome; SciForge says so instead of faking tangency.
        off = _tangency_off(face, boundary)
        if off > TANGENCY_TOLERANCE:
            raise SurfaceError(
                "Tangent continuity cannot be reached along these edges (off by %.0f degrees): "
                "OpenCASCADE's patch cannot turn to meet walls this steep. Use Continuity "
                "Connected, or patch an opening whose walls slope less." % math.degrees(off)
            )
    return face


def _tangency_off(face, boundary):
    """The biggest angle (radians) between the patch and the faces it should be tangent
    to, measured along the boundary (OpenCASCADE's own G1Error() reads 0 for curvature
    constraints even when the patch stays flat)."""
    worst = 0.0
    for edge, support in boundary:
        if support is None:
            continue
        for i in range(1, 6):
            u = edge.FirstParameter + (edge.LastParameter - edge.FirstParameter) * i / 6.0
            p = edge.valueAt(u)
            try:
                a = face.normalAt(*face.Surface.parameter(p))
                b = support.normalAt(*support.Surface.parameter(p))
                dot = min(1.0, abs(a.dot(b)) / max(a.Length * b.Length, 1e-12))
                worst = max(worst, math.acos(dot))
            except Exception:
                continue
    return worst


# -- CREATE: Ruled ---------------------------------------------------------------------------------
def ruled(items, ruled_type, distance, angle=0.0, direction=None, mitered=False):
    """Fusion's Ruled: a band leaving each edge. items: [(edge, face or None, plane normal
    for a sketch curve or None, alternate)]: a body edge rules from its face (with
    `alternate`, its other face), a sketch curve from its sketch plane."""
    if not items:
        raise NeedsPick("Select edges of a body or sketch curves.")
    d = float(distance)
    if abs(d) < 1e-7:
        raise NeedsPick("Drag the arrow or type a distance.")
    faces = []
    ends = []  # one record per edge end: (point, ruling there, direction into that end)
    for index, (edge, face, plane_normal, _alt) in enumerate(items):
        rule = _ruling(edge, face, plane_normal, ruled_type, angle, direction)
        faces.append(_ruled_face(edge, rule, d))
        a, b = edge.FirstParameter, edge.LastParameter
        ends.append((index, edge.valueAt(a), rule(a), unit(edge.tangentAt(a)) * -1.0))
        ends.append((index, edge.valueAt(b), rule(b), unit(edge.tangentAt(b))))
    faces.extend(_corners(ends, d, mitered))
    return surface_result(sew(faces))


def _ruling(edge, face, plane_normal, ruled_type, angle, direction):
    """A function u -> the unit ruling direction at curve parameter u."""
    if face is None and plane_normal is None:
        flat = plane_of([edge])
        plane_normal = flat[1] if flat is not None else None
        if plane_normal is None and ruled_type != "direction":
            raise SurfaceError(
                "This curve is not flat, so it has no face or plane to rule from. Pick an edge "
                "of a body, or use Ruled Type Direction."
            )
    dvec = tuple(unit(direction)) if direction is not None else None

    def rule(u):
        p = edge.valueAt(u)
        t = unit(edge.tangentAt(u))
        if face is not None:
            n = face_normal_at(face, p)
            away = away_in_face(face, edge, p, t)
        else:
            n = unit(plane_normal)
            away = unit(n.cross(t))
        out = core.ruling_direction(ruled_type, tuple(n), tuple(away), angle, dvec)
        return App.Vector(*out)

    return rule


def _ruled_face(edge, rule, d):
    a, b = edge.FirstParameter, edge.LastParameter
    curve = edge.Curve
    if curve.TypeId in ("Part::GeomLine", "Part::GeomLineSegment"):
        r0, r1 = rule(a), rule(b)
        if (r0 - r1).Length < 1e-9:
            p0, p1 = edge.valueAt(a), edge.valueAt(b)
            return Part.Face(Part.makePolygon([p0, p1, p1 + r0 * d, p0 + r0 * d, p0]))
    points = []
    count = SAMPLES if curve.TypeId not in ("Part::GeomLine",) else 8
    for i in range(count + 1):
        u = a + (b - a) * i / float(count)
        points.append(edge.valueAt(u) + rule(u) * d)
    if edge.isClosed() and (points[0] - points[-1]).Length < SAME:
        points = points[:-1]
        spline = Part.BSplineCurve()
        spline.interpolate(points, PeriodicFlag=True)
    else:
        spline = Part.BSplineCurve()
        spline.interpolate(points)
    try:
        return Part.makeRuledSurface(edge, spline.toShape())
    except Exception as exc:
        raise SurfaceError("The ruled surface cannot be built along that edge (%s)." % exc)


def _corners(ends, d, mitered):
    """Faces closing the gap where two picked edges meet and their bands open apart (an
    outside corner): a rounded sector, or with Mitered Corners a sharp corner. `ends`:
    (edge index, point, ruling, direction along the edge into that point)."""
    faces = []
    sign = 1.0 if d >= 0 else -1.0
    for i in range(len(ends)):
        for j in range(i + 1, len(ends)):
            ei, v, ra, ta = ends[i]
            ej, w, rb, tb = ends[j]
            if ei == ej or (v - w).Length > SAME:
                continue
            ra, rb = ra * sign, rb * sign
            if (rb - ra).Length < 1e-6 or (rb - ra).dot(ta) <= 1e-9:
                continue  # no gap, or an inside corner (the bands cross there)
            face = _corner_face(v, ra, rb, ta, tb, abs(d), mitered)
            if face is not None:
                faces.append(face)
    return faces


def _corner_face(v, ra, rb, ta, tb, d, mitered):
    pa, pb = v + ra * d, v + rb * d
    try:
        if mitered:
            m = _meet(pa, ta, pb, tb)
            if m is not None:
                return Part.Face(Part.makePolygon([v, pa, m, pb, v]))
        if ra.cross(rb).Length < 1e-9:
            return None
        mid = unit(ra + rb)
        arc = Part.Arc(pa, v + mid * d, pb).toShape()
        wire = Part.Wire(
            [Part.LineSegment(v, pa).toShape(), arc, Part.LineSegment(pb, v).toShape()]
        )
        return Part.Face(wire)
    except Exception:
        return None


def _meet(pa, ta, pb, tb):
    """Where the lines pa + s*ta and pb + k*tb (s, k >= 0: both carried on past the corner)
    meet, or None when they miss each other."""
    w = pa - pb
    a, b, c = ta.dot(ta), ta.dot(tb), tb.dot(tb)
    dd, e = ta.dot(w), tb.dot(w)
    den = a * c - b * b
    if abs(den) < 1e-12:
        return None
    s = (b * e - c * dd) / den
    k = (a * e - b * dd) / den
    x, y = pa + ta * s, pb + tb * k
    if (x - y).Length > SAME * 10 or s < -SAME or k < -SAME:
        return None
    return (x + y) * 0.5


# -- CREATE: Offset --------------------------------------------------------------------------------
def offset_faces(faces, distance):
    """New surfaces `distance` from the faces (positive along each face's normal)."""
    if not faces:
        raise NeedsPick("Select the faces to offset.")
    d = float(distance)
    if abs(d) < 1e-7:
        raise NeedsPick("Drag the arrow or type a distance.")
    out = []
    for piece in shells_or_faces(sew(faces)):
        try:
            result = piece.makeOffsetShape(d, 1e-6, False, False, 0, 0, False)
        except Exception as exc:
            raise SurfaceError(
                "These faces cannot be offset by %g mm (%s). A curved face whose radius is "
                "smaller than the distance often causes this." % (d, exc)
            )
        out.extend(result.Faces)
    return surface_result(sew(out))


# -- CREATE: Thicken -------------------------------------------------------------------------------
def thicken(faces, thickness, direction="one_side", thicken_type="sharp"):
    """A solid from faces given a thickness (One Side along the normal, Symmetric about the
    faces). Sharp corners meet in an edge, Rounded ones in an arc of the thickness (half of
    it for Symmetric) about the corner."""
    if not faces:
        raise NeedsPick("Select the faces (or a surface body) to thicken.")
    t = float(thickness)
    if abs(t) < 1e-7:
        raise NeedsPick("Drag the arrow or type a thickness.")
    solids = []
    for piece in shells_or_faces(sew(faces)):
        try:
            solid = _thick_sharp(piece, t, direction)
            if thicken_type == "rounded":
                solid = _round_corners(piece, solid, t, direction)
        except SurfaceError:
            raise
        except Exception as exc:
            raise SurfaceError(
                "These faces cannot be thickened by %g mm (%s). Use a smaller thickness: a "
                "curved face whose radius is smaller than the thickness cannot thicken "
                "inwards." % (t, exc)
            )
        for s in solid.Solids:
            if s.Volume < 0:
                s = s.copy()
                s.reverse()
            if not s.isValid() or s.Volume < 1e-9:
                raise SurfaceError(
                    "The thickened shape is broken: the thickness is too big for these faces. "
                    "Use a smaller thickness."
                )
            solids.append(s)
    if not solids:
        raise SurfaceError("Nothing could be thickened. Check the faces.")
    return compound(solids)


def _offset_solid(piece, depth):
    """The solid between a face / shell and its offset by `depth` (corners meet sharp)."""
    solid = piece.makeOffsetShape(depth, 1e-6, False, False, 0, 2, True)
    found = list(solid.Solids)
    if not found:
        found = [Part.Solid(Part.Shell(solid.Faces))]
    return found[0] if len(found) == 1 else compound(found)


def _thick_sharp(piece, t, direction):
    if direction != "symmetric":
        return _offset_solid(piece, t)
    try:  # half the thickness each way: offset back by t/2, then thicken by t
        moved = piece.makeOffsetShape(-t / 2.0, 1e-6, False, False, 0, 2, False)
        base = moved.Shells[0] if moved.Shells else moved.Faces[0]
        solid = _offset_solid(base, t)
        if solid.isValid() and solid.Volume > 1e-9:
            return solid
    except Exception:
        pass
    both = _offset_solid(piece, t / 2.0).fuse(_offset_solid(piece, -t / 2.0))
    return both.removeSplitter()


def _sharp_edges(piece):
    """Edges two faces of `piece` share at an angle (not tangent)."""
    found = []
    for edge in piece.Edges:
        faces = piece.ancestorsOfType(edge, Part.Face)
        if len(faces) != 2:
            continue
        try:
            point = edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2.0)
            n1 = face_normal_at(faces[0], point)
            n2 = face_normal_at(faces[1], point)
            if abs(n1.dot(n2)) < 1.0 - 1e-6 or n1.dot(n2) < 0:
                found.append(edge)
        except Exception:
            continue
    return found


def _tube(edge, radius):
    """A solid round bar of `radius` along an edge."""
    if edge.Curve.TypeId in ("Part::GeomLine", "Part::GeomLineSegment"):
        a = edge.valueAt(edge.FirstParameter)
        b = edge.valueAt(edge.LastParameter)
        return Part.makeCylinder(radius, (b - a).Length, a, b - a)
    start = edge.valueAt(edge.FirstParameter)
    circle = Part.Wire([Part.makeCircle(radius, start, edge.tangentAt(edge.FirstParameter))])
    return Part.Wire([edge]).makePipeShell([circle], True, True)


def _round_corners(piece, sharp, t, direction):
    """Rounded: where two faces meet at an angle, the outside corner of the sharp solid
    becomes an arc about the corner. The rounded solid is the sharp one cut down to the
    faces thickened one by one plus a round bar of the thickness along each corner and a
    ball where corners meet (OCC's own arc join cannot close an open surface into a
    solid)."""
    corners = _sharp_edges(piece)
    if not corners:
        return sharp
    radius = abs(t) / 2.0 if direction == "symmetric" else abs(t)
    parts = [_thick_sharp(face, t, direction) for face in piece.Faces]
    parts += [_tube(edge, radius) for edge in corners]
    for vertex in piece.Vertexes:  # where corners meet, a ball rounds the corner off
        if sum(1 for edge in corners if any(vertex.isSame(v) for v in edge.Vertexes)) >= 2:
            parts.append(Part.makeSphere(radius, vertex.Point))
    blob = parts[0].fuse(parts[1:]) if len(parts) > 1 else parts[0]
    out = sharp.common(blob).removeSplitter()
    if not out.Solids:
        raise SurfaceError("The corners could not be rounded: use Thicken Type Sharp.")
    if len(out.Solids) == 1:
        return out.Solids[0]
    return out


# -- cells -----------------------------------------------------------------------------------------
def _on(shape, edge, tol=1e-5):
    try:
        mid = edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2.0)
        return shape.distToShape(Part.Vertex(mid))[0] < tol
    except Exception:
        return False


def cells_for_trim(target, cutter):
    """The pieces (cells) of a surface `target` cut by `cutter` (any shape), each
    {"faces": [...], "point": a point on it, "size": its area}. One cell: nothing is cut."""
    faces = list(target.Faces)
    if not faces:
        return []
    # Every face is its own argument, so the map gives each face's pieces (a shell or a
    # compound argument is not mapped) and faces that shared an edge still share it.
    args = list(faces) + [cutter]
    try:
        _result, pieces_map = args[0].generalFuse(args[1:])
    except Exception as exc:
        raise SurfaceError("The trim tool cannot cut this surface (%s)." % exc)
    pieces = []
    for i, face in enumerate(faces):
        found = [f for shape in (pieces_map[i] if i < len(pieces_map) else []) for f in shape.Faces]
        pieces.extend(found or [face])
    # Faces that share an edge belong to one cell unless that edge lies on the cutter.
    parent = list(range(len(pieces)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(pieces)):
        for j in range(i + 1, len(pieces)):
            if find(i) == find(j):
                continue
            for e1 in pieces[i].Edges:
                if any(e1.isSame(e2) for e2 in pieces[j].Edges) and not _on(cutter, e1):
                    parent[find(i)] = find(j)
                    break
    groups = {}
    for i, face in enumerate(pieces):
        groups.setdefault(find(i), []).append(face)
    cells = []
    for members in groups.values():
        biggest = max(members, key=lambda f: f.Area)
        cells.append(
            {"faces": members, "point": face_point(biggest), "size": sum(f.Area for f in members)}
        )
    cells.sort(key=lambda c: (-round(c["size"], 6), tuple(round(x, 6) for x in c["point"])))
    return cells


def match_cells(cells, points, solid=False):
    """Indices of the cells the stored points (lists) name, and the points that found none.
    A point names the cell it lies on (inside, for solid cells), else the nearest one."""
    if not points:
        return [], []
    box = bound_box([compound(c["faces"]) if "faces" in c else c["solid"] for c in cells])
    tol = max(1e-3, (box.DiagonalLength if box is not None else 1.0) * 0.05)
    rows = []
    for p in points:
        point = vec(p)
        row = []
        for cell in cells:
            if solid:
                s = cell["solid"]
                row.append(0.0 if s.isInside(point, 1e-6, True) else distance(s, point))
            else:
                row.append(min(distance(f, point) for f in cell["faces"]))
        rows.append(row)
    return core.choose_cells(rows, tol)


def trim(target, cutter, points):
    """`target` without the cells the points name."""
    cells = cells_for_trim(target, cutter)
    if len(cells) < 2:
        raise SurfaceError(
            "The trim tool does not cut this surface into pieces. Pick a tool that crosses it "
            "(a surface, a plane, a sketch curve or a body)."
        )
    chosen, lost = match_cells(cells, points)
    if lost and not chosen:
        raise SurfaceError(
            "The pieces picked to remove are not there any more (an earlier step changed "
            "them). Edit the Trim and pick them again."
        )
    keep = [c for i, c in enumerate(cells) if i not in chosen]
    if not keep:
        raise SurfaceError("That would remove all of the surface. Keep at least one piece.")
    faces = [f for c in keep for f in c["faces"]]
    return surface_result(sew(faces))


def boundary_cells(tools):
    """Fusion's Boundary Fill cells: the closed volumes the tools (bodies, surfaces, planes
    as big faces) enclose, each {"solid", "point", "size"}, biggest first."""
    real = [t for t in tools if t is not None and not t.isNull()]
    if not real:
        return []
    box = bound_box(real)
    margin = max(box.DiagonalLength * 0.25, 5.0)
    big = Part.makeBox(
        box.XLength + 2 * margin,
        box.YLength + 2 * margin,
        box.ZLength + 2 * margin,
        App.Vector(box.XMin - margin, box.YMin - margin, box.ZMin - margin),
    )
    try:
        _result, pieces_map = big.generalFuse(real)
    except Exception as exc:
        raise SurfaceError("The tools cannot be intersected (%s)." % exc)
    outer = big.BoundBox
    cells = []
    for shape in pieces_map[0] if pieces_map else []:
        for solid in shape.Solids:
            b = solid.BoundBox
            touches = (
                b.XMin <= outer.XMin + SAME
                or b.YMin <= outer.YMin + SAME
                or b.ZMin <= outer.ZMin + SAME
                or b.XMax >= outer.XMax - SAME
                or b.YMax >= outer.YMax - SAME
                or b.ZMax >= outer.ZMax - SAME
            )
            if touches or solid.Volume < 1e-9:
                continue
            cells.append({"solid": solid, "point": solid_point(solid), "size": solid.Volume})
    cells.sort(key=lambda c: (-round(c["size"], 6), tuple(round(x, 6) for x in c["point"])))
    return cells


def fill_cells(tools, points):
    """The solid made of the cells the points name (Boundary Fill)."""
    cells = boundary_cells(tools)
    if not cells:
        raise SurfaceError(
            "The tools do not enclose any closed volume. Pick bodies, surfaces and planes that "
            "close a space on every side."
        )
    if not points:
        raise NeedsPick("Select the cells to fill (click them, or tick them in the list).")
    chosen, lost = match_cells(cells, points, solid=True)
    if not chosen:
        raise SurfaceError(
            "The cells picked are not there any more (an earlier step changed the tools). "
            "Edit the Boundary Fill and pick the cells again."
        )
    solids = [cells[i]["solid"] for i in chosen]
    shape = solids[0] if len(solids) == 1 else solids[0].fuse(solids[1:])
    try:
        shape = shape.removeSplitter()
    except Exception:
        pass
    return shape


# -- MODIFY ----------------------------------------------------------------------------------------
def untrim(target, faces, loop_type="all", extend=0.0):
    """Fusion's Untrim: faces of `target` lose their loops that touch no other face
    (Internal: holes; External: the outer boundary, back to the surface's own; All: both),
    the outer boundary pushed out by `extend` where the surface allows."""
    if not faces:
        raise NeedsPick("Select the faces to untrim.")
    free = free_edges(target)
    replaced = []
    changed = 0
    for face in target.Faces:
        if not any(face.isSame(f) for f in faces):
            replaced.append(face)
            continue
        new = _untrim_face(face, free, loop_type, float(extend or 0.0))
        if new is None:
            replaced.append(face)
            continue
        changed += 1
        replaced.append(new)
    if not changed:
        raise SurfaceError(
            "There is no loop to remove: only loops of a face that touch no other face can be "
            "untrimmed. Pick a face with a hole or a free outer edge."
        )
    return surface_result(sew(replaced))


def _free_wire(wire, free):
    return all(any(e.isSame(f) for f in free) for e in wire.Edges)


def _untrim_face(face, free, loop_type, extend):
    surface = face.Surface
    outer = face.OuterWire
    inner = [w for w in face.Wires if not w.isSame(outer)]
    drop_inner = loop_type in ("all", "internal") and any(_free_wire(w, free) for w in inner)
    drop_outer = loop_type in ("all", "external") and _free_wire(outer, free)
    if not drop_inner and not drop_outer:
        return None
    keep_inner = [w for w in inner if not (drop_inner and _free_wire(w, free))]
    if drop_outer:
        base = _natural_face(face, extend)
    else:
        base = Part.Face(surface, outer)
    for hole in keep_inner:
        try:
            base = base.cut(Part.Face(surface, hole))
        except Exception:
            pass
    faces = base.Faces
    return faces[0] if len(faces) == 1 else compound(faces)


def _natural_face(face, extend):
    surface = face.Surface
    u0, u1, v0, v1 = face.ParameterRange
    kind = surface.TypeId
    if kind == "Part::GeomPlane":
        e = max(extend, 0.0)
        return surface.toShape(u0 - e, u1 + e, v0 - e, v1 + e)
    if kind in ("Part::GeomCylinder", "Part::GeomCone"):
        radius = getattr(surface, "Radius", 1.0) or 1.0
        du = min(extend / radius, math.pi)
        a, b = u0 - du, u1 + du
        if b - a >= 2 * math.pi - 1e-9:
            a, b = 0.0, 2 * math.pi
        return surface.toShape(a, b, v0 - extend, v1 + extend)
    try:
        b = surface.bounds()
        return surface.toShape(b[0], b[1], b[2], b[3])
    except Exception:
        return surface.toShape(u0, u1, v0, v1)


def extend(target, edges, distance, extend_type="natural", alignment="free"):
    """Fusion's Extend: free edges of a surface carried on by `distance`. Natural continues
    the face's own surface (a flat face stays one flat face); Tangent adds flat faces that
    carry the face on; Perpendicular adds faces square to it."""
    if not edges:
        raise NeedsPick("Select edges on the outside of a surface body.")
    d = float(distance)
    if abs(d) < 1e-7:
        raise NeedsPick("Drag the arrow or type a distance.")
    free = free_edges(target)
    for edge in edges:
        if not any(edge.isSame(f) for f in free):
            raise SurfaceError(
                "Only edges on the outside of a surface (that touch one face) can be extended. "
                "Pick a free edge."
            )
    if extend_type == "natural":
        natural = _natural_extend(target, edges, d)
        if natural is not None:
            return natural
    ruled_type = "normal" if extend_type == "perpendicular" else "tangent"
    items = []
    for edge in edges:
        owners = faces_of_edge(target, edge)
        if not owners:
            raise SurfaceError("An edge picked has no face to extend.")
        items.append((edge, owners[0], None, False))
    bands = ruled(items, ruled_type, d, 0.0, None, mitered=extend_type != "perpendicular")
    joined = sew(list(target.Faces) + list(bands.Faces))
    if extend_type == "natural":
        try:
            joined = joined.removeSplitter()  # a flat face carried on stays one face
        except Exception:
            pass
    return surface_result(joined)


def _natural_extend(target, edges, d):
    """Natural extension where the face's own surface can simply be made bigger: a face
    whose boundary is its surface's parameter rectangle (a flat rectangle, a piece of a
    cylinder...). None when that does not apply (the Tangent bands are used instead)."""
    by_face = {}
    for edge in edges:
        owners = faces_of_edge(target, edge)
        if not owners:
            return None
        key = owners[0].hashCode()
        by_face.setdefault(key, (owners[0], []))[1].append(edge)
    rebuilt = {}
    for key, (face, picked) in by_face.items():
        if face.Surface.TypeId == "Part::GeomPlane":
            return None  # flat faces: the tangent bands, merged into the face, are exact
        new = _grow_rectangle(face, picked, d)
        if new is None:
            return None
        rebuilt[key] = new
    faces = [rebuilt.get(f.hashCode(), f) for f in target.Faces]
    return surface_result(sew(faces))


def _grow_rectangle(face, picked, d):
    surface = face.Surface
    if surface.TypeId not in ("Part::GeomCylinder", "Part::GeomCone"):
        return None
    if len(face.Wires) != 1 or len(face.Edges) != 4:
        return None
    u0, u1, v0, v1 = face.ParameterRange
    radius = getattr(surface, "Radius", 1.0) or 1.0
    du, dv = d / radius, d
    for edge in picked:
        mid = edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2.0)
        u, v = surface.parameter(mid)
        if abs(u - u0) < 1e-6:
            u0 -= du
        elif abs(u - u1) < 1e-6:
            u1 += du
        elif abs(v - v0) < 1e-6:
            v0 -= dv
        elif abs(v - v1) < 1e-6:
            v1 += dv
        else:
            return None
    if u1 - u0 > 2 * math.pi + 1e-9:
        raise SurfaceError(
            "The extension would wrap the curved face round onto itself. Use a smaller " "distance."
        )
    return surface.toShape(u0, u1, v0, v1)


def stitch(shapes, tolerance=core.STITCH_TOLERANCE):
    """Fusion's Stitch: the surfaces joined where their edges meet (gaps up to `tolerance`).
    A closed result is a solid. Returns (shape, number of edges left open)."""
    faces = [f for s in shapes for f in s.Faces]
    if len(faces) < 2:
        raise NeedsPick("Select the surface bodies to stitch (at least two faces).")
    sewn = sew(faces, float(tolerance))
    pieces = []
    for piece in shells_or_faces(sewn):
        if piece.ShapeType == "Shell" and piece.isClosed():
            try:
                solid = Part.Solid(piece)
                if solid.Volume < 0:
                    solid.reverse()
                if not solid.isValid():
                    fixed = solid.copy()
                    fixed.fix(1e-7, 1e-7, float(tolerance))
                    solid = fixed
                pieces.append(solid)
                continue
            except Exception:
                pass
        pieces.append(piece)
    result = compound(pieces)
    return surface_result(result), _open_count(result)


def unstitch(target, faces):
    """Fusion's Unstitch: the picked faces leave the body, each a surface of its own.
    Returns (what stays in the body or None, [each picked face])."""
    if not faces:
        raise NeedsPick("Select the faces (or bodies) to unstitch.")
    taken, rest = [], []
    for face in target.Faces:
        if any(face.isSame(f) for f in faces):
            taken.append(face.copy())
        else:
            rest.append(face.copy())
    if not taken:
        raise SurfaceError("None of the picked faces belongs to that body.")
    if not rest and len(taken) == 1:
        raise SurfaceError("That body has a single face already: there is nothing to unstitch.")
    stay = sew(rest) if rest else None
    return stay, taken


def reverse(target):
    """Fusion's Reverse Normal: every face of a surface turned over."""
    if target.Solids:
        raise SurfaceError(
            "Reverse Normal works on surface bodies: a solid's faces always point out of it."
        )
    out = target.copy()
    out.reverse()
    return surface_result(out)


def thicken_cut(base, tool, operation):
    """A solid (a Thicken or a Boundary Fill) joined to, cut from or intersected with `base`."""
    try:
        if operation == "join":
            result = base.fuse(tool)
        elif operation == "cut":
            result = base.cut(tool)
        else:
            result = base.common(tool)
    except Exception as exc:
        raise SurfaceError("The result cannot be combined with the body (%s)." % exc)
    solids = list(result.Solids)
    if not solids:
        if operation == "intersect":
            raise SurfaceError("It does not overlap the body, so Intersect leaves nothing.")
        raise SurfaceError("That would leave nothing of the body.")
    shape = solids[0] if len(solids) == 1 else Part.makeCompound(solids)
    try:
        shape = shape.removeSplitter()
    except Exception:
        pass
    return shape
