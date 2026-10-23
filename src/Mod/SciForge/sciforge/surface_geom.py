# SPDX-License-Identifier: LGPL-2.1-or-later
"""The geometry of SciForge's surface tools, on FreeCAD's Part module (OpenCASCADE).

No document and no Qt: every function takes shapes in design coordinates and returns a new
shape, so the feature (surface.py), the golden-model builder and headless tests share it.
Problems raise surface_core.SurfaceError with a message that says why and what to try.

    extrude_curves, revolve_curves, sweep_curves, loft_surface      CREATE from curves
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


def stitched_edges(shapes, result, limit=400):
    """Stitch: the open edges of the surfaces `shapes` that `result` (their stitch) closed,
    the ones Fusion draws green. An edge counts as closed when its middle lies on none of
    the edges the result leaves open. At most `limit` edges are looked at (a preview)."""
    still = free_edges(result)
    left = compound(still) if still else None
    found = []
    for shape in shapes:
        for edge in free_edges(shape):
            if len(found) >= limit:
                return found
            try:
                mid = edge.valueAt(0.5 * (edge.FirstParameter + edge.LastParameter))
                if left is None or left.distToShape(Part.Vertex(mid))[0] > 1e-3:
                    found.append(edge)
            except Exception:
                continue
    return found


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
def extrude_curves(edges, normal, options, to_object=None, start=None, through=None):
    """Fusion's surface Extrude of open or closed curves along `normal` (the sketch's).

    options: start ('profile' | 'offset' | 'object') / start_offset, direction / distance /
    distance2 / measurement, taper / taper2, extent ('distance' | 'to_object' | 'all'), flip.
    to_object / start: the picked object, as surface.target_of_ref gives it:
      ("plane", point, normal) | ("point", point) | ("shape", shape)
    through: the shapes of the visible bodies Extent All goes through.

    Start From Object: a plane or flat face parallel to the profile, or a point, starts the
    extrusion at that height (Offset moves it on); a slanted plane or a curved face starts
    every line of the extrusion where it meets the object, nearest the profile."""
    o = core.with_defaults("extrude", options)
    core.check_values("extrude", o)
    n = unit(normal)
    wires = wires_of(edges)
    if not wires:
        raise NeedsPick("Select the profile: sketch curves or edges of a body.")
    flat = plane_of(wires)
    if flat is not None and abs(abs(flat[1].dot(n)) - 1.0) > 1e-6:
        flat = None  # curves in a plane not square to the direction: still fine
    origin = App.Vector(wires[0].Vertexes[0].Point)
    lift = float(o["start_offset"]) if o["start"] in ("offset", "object") else 0.0
    height = lift
    if o["start"] == "object":
        if start is None:
            raise NeedsPick("Select where the extrusion starts: a plane, a face or a point.")
        level = _start_height(start, n, origin)
        if level is None:
            face = _start_face(start, n, lift, wires)
            return _extrude_from_face(wires, n, origin, face, o, to_object, through)
        height = level + lift
    shift = n * height
    if o["extent"] == "to_object":
        if to_object is None:
            raise NeedsPick("Select the object to extrude to: a plane, a face, a body or a point.")
        if to_object[0] == "plane":
            return _extrude_to_plane(wires, n, shift, (to_object[1], to_object[2]))
        if to_object[0] == "point":
            return _extrude_to_plane(wires, n, shift, (to_object[1], n))
        return _extrude_to_shape(wires, n, origin, height, to_object[1])
    if o["extent"] == "all":
        up, down = _reach_of(through, origin + shift, n)
        up, down = core.all_lengths(o["direction"], o.get("flip"), up, down)
        start_, end = -down, up
    else:
        start_, end = core.extrude_range(
            o["direction"], o["distance"], o["distance2"], o["measurement"]
        )
    faces = []
    for wire in wires:
        base = wire.copy()
        base.translate(shift)
        taper_one = float(o["taper"])
        taper_two = float(o["taper2"]) if o["direction"] == "two_sides" else taper_one
        if start_ < -1e-9 and end > 1e-9 and abs(taper_one) < 1e-9 and abs(taper_two) < 1e-9:
            base.translate(n * start_)  # both ways, straight: one face per curve, as Fusion
            faces.extend(base.extrude(n * (end - start_)).Faces)
            continue
        if end > 1e-9:
            faces.extend(_extrude_piece(base, n, end, taper_one, flat).Faces)
        if start_ < -1e-9:
            faces.extend(_extrude_piece(base, n, start_, taper_two, flat).Faces)
    return surface_result(sew(faces))


def _start_height(start, n, origin):
    """How far (along n) a start object that is parallel to the profile lies from it, or None
    when the object is slanted or curved (each line then starts where it meets it)."""
    kind = start[0]
    if kind == "point":
        return (vec(start[1]) - origin).dot(n)
    if kind == "plane":
        if abs(abs(unit(start[2]).dot(n)) - 1.0) < 1e-7:
            return (vec(start[1]) - origin).dot(n)
        return None
    shape = start[1]
    faces = shape.Faces
    if len(faces) == 1 and faces[0].Surface.TypeId == "Part::GeomPlane":
        face = faces[0]
        if abs(abs(face_normal_at(face, face_point(face)).dot(n)) - 1.0) < 1e-7:
            return (face_point(face) - origin).dot(n)
    return None


def _start_face(start, n, lift, wires):
    """The slanted plane (a big square) or the curved faces the extrusion starts on, moved
    on by the offset."""
    if start[0] == "plane":
        size = reach(wires, (vec(start[1]) - bound_box(wires).Center).Length)
        face = plane_face(start[1], start[2], size)
    else:
        shape = start[1]
        if shape.Solids or not shape.Faces:
            raise SurfaceError("Start from a plane, a face or a point (not a whole body).")
        face = compound([f.copy() for f in shape.Faces])
    if abs(lift) > 1e-12:
        face = face.copy()
        face.translate(n * lift)
    return face


def _hits(shape, point, n, size):
    """Where the line through `point` along n meets `shape`: the lengths along n (sorted)."""
    line = Part.LineSegment(point - n * size, point + n * size).toShape()
    try:
        section = line.section(shape)
    except Exception:
        return []
    found = []
    for vertex in section.Vertexes:
        t = (vertex.Point - point).dot(n)
        if not any(abs(t - x) < 1e-7 for x in found):
            found.append(t)
    return sorted(found)


def _samples(wires, count=8):
    """Points along the curves (inside each edge, where a line of the extrusion runs)."""
    points = []
    for wire in wires:
        for edge in wire.Edges:
            a, b = edge.FirstParameter, edge.LastParameter
            for k in range(count + 1):
                f = 0.02 + 0.96 * k / float(count)
                points.append(edge.valueAt(a + (b - a) * f))
    return points


def _split_band(faces, cutters):
    """The band's faces cut where the cutters cross them (pieces of the band only)."""
    cutters = [c for c in cutters if c is not None and not c.isNull()]
    if not cutters:
        return list(faces)
    args = list(faces) + cutters
    try:
        _result, pieces_map = args[0].generalFuse(args[1:])
    except Exception as exc:
        raise SurfaceError("The extrusion cannot be cut at the object (%s)." % exc)
    pieces = []
    for i, face in enumerate(faces):
        found = [f for shape in (pieces_map[i] if i < len(pieces_map) else []) for f in shape.Faces]
        pieces.extend(found or [face])
    return pieces


def _ruled_band(wires, n, origin, cutters, keep, size):
    """The curves carried along n both ways, cut by the cutters; keeps the pieces whose middle
    lies where keep(foot, height) says (foot: where its line meets the profile's plane,
    height: how far along n it is from there)."""
    faces = []
    for wire in wires:
        base = wire.copy()
        base.translate(n * -size)
        faces.extend(base.extrude(n * (2.0 * size)).Faces)
    kept = []
    for piece in _split_band(faces, cutters):
        q = face_point(piece)
        t = (q - origin).dot(n)
        if keep(q - n * t, t):
            kept.append(piece)
    if not kept:
        raise SurfaceError("Nothing is left between the start and the end. Check the picks.")
    return surface_result(sew(kept))


def _nearest_hit(shape, foot, n, size):
    hits = _hits(shape, foot, n, size)
    return min(hits, key=abs) if hits else None


def _extrude_from_face(wires, n, origin, start, o, target, through):
    """Start From Object on a slanted plane or a curved face: every line of the extrusion
    starts where it meets the object nearest the profile."""
    if abs(float(o["taper"])) > 1e-9 or (
        o["direction"] == "two_sides" and abs(float(o["taper2"])) > 1e-9
    ):
        raise SurfaceError(
            "A taper needs a start parallel to the profile (Profile Plane, Offset, or a plane, "
            "flat face or point parallel to it). Set the taper to 0."
        )
    shapes = [start] + list(wires) + ([target[1]] if target and target[0] == "shape" else [])
    size = reach(shapes + list(through or []), 0.0)
    for p in _samples(wires):
        if _nearest_hit(start, p, n, size) is None:
            raise SurfaceError(
                "The start object does not lie across the whole profile along the extrusion: "
                "part of it would start nowhere. Pick a bigger face or a plane."
            )

    def start_of(foot):
        return _nearest_hit(start, foot, n, size)

    if o["extent"] == "distance":
        lo, hi = core.extrude_range(o["direction"], o["distance"], o["distance2"], o["measurement"])
        cutters = [start]
        for amount in (lo, hi):
            if abs(amount) > 1e-9:
                moved = start.copy()
                moved.translate(n * amount)
                cutters.append(moved)

        def keep(foot, t):
            h = start_of(foot)
            return h is not None and h + lo + 1e-7 < t < h + hi - 1e-7

        return _ruled_band(wires, n, origin, cutters, keep, size)
    if o["extent"] == "to_object":
        if target is None:
            raise NeedsPick("Select the object to extrude to: a plane, a face, a body or a point.")
        end = _target_shape(target, n, size)
        side = _side_towards(wires, end, start_of, n, size)

        def keep(foot, t):
            h = start_of(foot)
            if h is None:
                return False
            return _between(h, t, _hits(end, foot, n, size), side)

        return _ruled_band(wires, n, origin, [start, end], keep, size)
    up, down = _levels(through, n)
    base = origin.dot(n)
    top, bottom = up - base, down - base
    heights = [h for h in (start_of(p) for p in _samples(wires)) if h is not None]
    room_up = max(top - h for h in heights)
    room_down = max(h - bottom for h in heights)
    room_up, room_down = core.all_lengths(o["direction"], o.get("flip"), room_up, room_down)
    cutters = [start]
    if room_up > 1e-7:
        cutters.append(plane_face(origin + n * top, n, size))
    if room_down > 1e-7:
        cutters.append(plane_face(origin + n * bottom, n, size))

    def keep(foot, t):
        h = start_of(foot)
        if h is None:
            return False
        if room_up > 1e-7 and h + 1e-7 < t < top - 1e-7:
            return True
        return room_down > 1e-7 and bottom + 1e-7 < t < h - 1e-7

    return _ruled_band(wires, n, origin, cutters, keep, size)


def _between(h, t, ends, side):
    """True when height t lies past h (the start) and before the first crossing of the end
    object on `side` (+1 along n, -1 against it)."""
    if side > 0:
        ahead = [e for e in ends if e > h + 1e-7]
        return bool(ahead) and h + 1e-7 < t < min(ahead) - 1e-7
    behind = [e for e in ends if e < h - 1e-7]
    return bool(behind) and max(behind) + 1e-7 < t < h - 1e-7


def _target_shape(target, n, size):
    if target[0] == "plane":
        return plane_face(target[1], target[2], size)
    if target[0] == "point":
        return plane_face(target[1], n, size)
    return target[1]


def _side_towards(wires, end, start_of, n, size):
    """+1 when the end object lies along n from the start, -1 when against it (the side most
    of the profile meets it first; ahead when both)."""
    votes = 0.0
    for p in _samples(wires, 4):
        h = start_of(p)
        if h is None:
            continue
        hits = _hits(end, p, n, size)
        ahead = [e - h for e in hits if e > h + 1e-7]
        behind = [h - e for e in hits if e < h - 1e-7]
        if ahead and (not behind or min(ahead) <= min(behind)):
            votes += 1.0
        elif behind:
            votes -= 1.0
    if votes == 0.0:
        raise SurfaceError(
            "The extrusion never reaches that object. Pick one the profile's lines run into."
        )
    return 1.0 if votes > 0 else -1.0


def _extrude_to_shape(wires, n, origin, height, shape):
    """To Object on a curved face (its surface carried on, Fusion's To Selected Face) or a body
    (where the extrusion first meets it)."""
    size = reach(list(wires) + [shape], abs(height))

    def start_of(_foot):
        return height

    targets = [shape]
    if not shape.Solids and len(shape.Faces) == 1:
        bigger = extended_face(shape.Faces[0])
        if bigger is not None:
            targets.append(bigger)
    problem = None
    for end in targets:
        try:
            side = _side_towards(wires, end, start_of, n, size)
        except SurfaceError as exc:
            problem = exc
            continue
        if not all(_reaches(end, p, n, size, height, side) for p in _samples(wires)):
            problem = SurfaceError(
                "Part of the profile never reaches that object along the extrusion. Pick a "
                "bigger face, a body that covers the whole profile, or a plane."
            )
            continue

        def keep(foot, t, end=end, side=side):
            return _between(height, t, _hits(end, foot, n, size), side)

        start_plane = plane_face(origin + n * height, n, size)
        return _ruled_band(wires, n, origin, [start_plane, end], keep, size)
    raise problem


def _reaches(end, p, n, size, height, side):
    hits = _hits(end, p, n, size)
    if side > 0:
        return any(e > height + 1e-7 for e in hits)
    return any(e < height - 1e-7 for e in hits)


def extended_face(face):
    """The face's surface carried on past its edges (Fusion's To Selected Face), or None when
    it cannot be (a free-form surface)."""
    surface = face.Surface
    u0, u1, v0, v1 = face.ParameterRange
    size = max(face.BoundBox.DiagonalLength, 1.0) * 4.0
    kind = surface.TypeId
    try:
        if kind == "Part::GeomPlane":
            return plane_face(face_point(face), face_normal_at(face, face_point(face)), size * 4)
        if kind in ("Part::GeomCylinder", "Part::GeomCone"):
            return surface.toShape(u0, u1, v0 - size, v1 + size)
        if kind in ("Part::GeomSphere", "Part::GeomToroid"):
            return surface.toShape()
        if kind == "Part::GeomSurfaceOfExtrusion":
            return surface.toShape(u0, u1, v0 - size, v1 + size)
    except Exception:
        return None
    return None


def _reach_of(shapes, point, n):
    """How far the shapes reach from `point` along n and against it (mm; <= 0: nothing that
    way)."""
    shapes = [s for s in shapes or [] if s is not None and not s.isNull()]
    if not shapes:
        raise SurfaceError(
            "There is no visible body for All to extrude through. Show one, or use Distance."
        )
    size = reach(shapes, (point - bound_box(shapes).Center).Length)
    found = []
    for d in (n, n * -1.0):
        far = plane_face(point + d * size, d, size * 2.0)
        best = None
        for shape in shapes:
            try:
                gap = shape.distToShape(far)[0]
            except Exception:
                continue
            best = gap if best is None else min(best, gap)
        found.append(size - best if best is not None else 0.0)
    return found[0], found[1]


def _levels(shapes, n):
    """The highest and the lowest level (along n, from the origin) the shapes reach, or
    None for none."""
    shapes = [s for s in shapes or [] if s is not None and not s.isNull()]
    if not shapes:
        raise SurfaceError(
            "There is no visible body for All to extrude through. Show one, or use Distance."
        )
    up, down = _reach_of(shapes, App.Vector(0, 0, 0), n)
    return up, -down


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
def project_axis(edges, center, axis, plane=None):
    """Revolve's Project Axis: the axis line laid into the plane of the profile (moved
    square onto it), as Fusion projects it onto the profile's sketch plane (`plane`: (point,
    normal) of that sketch; else the plane the curves lie in). A profile that is not flat,
    or an axis that already lies in its plane, keeps the axis as it is."""
    flat = plane if plane is not None else plane_of(wires_of(edges))
    c, a = vec(center), unit(axis)
    if flat is None:
        return c, a
    origin, n = flat
    along = a - n * a.dot(n)
    if along.Length < 1e-7:
        raise SurfaceError(
            "The axis stands square to the profile's plane, so it cannot be projected onto "
            "it. Clear Project Axis, or pick an axis beside the profile."
        )
    return c - n * (c - origin).dot(n), unit(along)


def revolve_curves(edges, center, axis, options, to_directions=None, second=None):
    """Fusion's surface Revolve. Type To: `to_directions` are the half-planes (unit vectors
    from the axis) the picked object marks (revolve.target_directions); the curves turn the
    shorter way to the nearest one. With Two Sides, the first side turns the right-handed
    way to the first object and the second the other way to `second`'s."""
    o = core.with_defaults("revolve", options)
    core.check_values("revolve", o)
    wires = wires_of(edges)
    if not wires:
        raise NeedsPick("Select the profile: sketch curves or edges of a body.")
    a = unit(axis)
    c = vec(center)
    _check_axis(wires, c, a)
    if o["type"] == "to":
        if not to_directions:
            raise NeedsPick(
                "Select the object to revolve to: a plane or flat face through the axis, an "
                "edge or a point."
            )
        start_dir = _radial_of(wires, c, a)
        first = [tuple(unit(w)) for w in to_directions]
        if o["direction"] == "two_sides":
            if not second:
                raise NeedsPick("Select the object the second side revolves to.")
            start, sweep = core.two_sided_to(
                tuple(start_dir), first, [tuple(unit(w)) for w in second], tuple(a)
            )
        else:
            angle = core.stop_angle(tuple(start_dir), first, tuple(a))
            start, sweep = 0.0, angle
    else:
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


def revolve_to_angle(edges, center, axis, to_directions):
    """The signed angle a Type To revolve turns (for the dialog's handle)."""
    wires = wires_of(edges)
    a = unit(axis)
    start_dir = _radial_of(wires, vec(center), a)
    return core.stop_angle(tuple(start_dir), [tuple(unit(w)) for w in to_directions], tuple(a))


def _radial_of(wires, c, a):
    """The direction from the axis to the curves (their middle, else their farthest point)."""
    middle = bound_box(wires).Center
    r = (middle - c) - a * (middle - c).dot(a)
    if r.Length > SAME:
        return unit(r)
    best = None
    for wire in wires:
        for p in wire.discretize(64):
            q = (p - c) - a * (p - c).dot(a)
            if best is None or q.Length > best.Length:
                best = q
    if best is None or best.Length <= SAME:
        raise SurfaceError("The profile lies on the axis: there is nothing to revolve.")
    return unit(best)


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
def sweep_curves(profile_edges, path, options, rail=None, guide=None):
    """`path`, `rail`: curves.Path. The profile curves (open or closed) are carried along the
    path from where they sit (sweep.Plan: Distance, Distance Two). Single Path: Orientation,
    Twist Angle and Taper Angle (Perpendicular); Path + Guide Rail: the rail turns the profile
    and, with Profile Scaling Scale / Stretch, resizes it to keep reaching the rail; its
    Extent stops the sweep square to the path where the shorter of path and rail ends
    (Perpendicular to Path) or runs both to their ends (Full Extents), and Guide Rail
    Distance uses that share of the rail. Path + Guide Surface (`guide`: faces): the
    profile keeps the angle it has to the surface along the path (sweep.py's solid rule)."""
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
    with_rail = o["type"] == "rail"
    with_surface = o["type"] == "surface"
    if with_rail and rail is None:
        raise NeedsPick("Select the guide rail: sketch curves or edges of a body.")
    if with_surface and not guide:
        raise NeedsPick("Select the guide surface: faces the path runs along.")
    if with_rail and rail.closed != path.closed:
        raise SurfaceError("The guide rail must be open or closed like the path.")
    if with_rail:
        path, rail = _rail_extent(path, rail, o, at_end=s_p > 0.5 * path.length)
        try:
            point = path.wire().distToShape(Part.Vertex(centre))[1][0][0]
        except Exception:
            point = path.start
        s_p = path.length_at(point)
    try:
        plan = sweep_core.Plan(
            path,
            s_p,
            {
                "distance": o["distance"],
                "distance2": o["distance2"],
                "type": "rail" if with_rail else "single",
            },
        )
    except Exception as exc:
        raise SurfaceError(str(exc))
    perpendicular = o["orientation"] == "perpendicular"
    faces = []
    for spine, sign in plan.side_paths():
        aux = None
        sections_for = None
        try:
            if with_surface:
                size = max(1.0, bound_box(wires).DiagonalLength)
                aux = sweep_core._surface_aux(spine, guide, size)
            elif with_rail:
                part = sweep_core._rail_part(rail, path, plan, spine, sign)
                aux = part.wire()
                if o["scaling"] != "none":
                    count = 2 if (spine.is_straight() and part.is_straight()) else STATIONS
                    sections_for = sweep_core._rail_sections(
                        spine, part, o["orientation"], o["scaling"], count
                    )
            else:
                if abs(float(o["twist"])) > 1e-9 and perpendicular:
                    total = max(plan.side1 + plan.side2, 1e-9)
                    turn = float(o["twist"]) * spine.length / total * sign
                    radius = max(1.0, bound_box(wires).DiagonalLength)
                    aux = curves.twist_guide(spine, turn, radius)
                if abs(float(o["taper"])) > 1e-9 and perpendicular:
                    sections_for = _taper_sections(spine, wires, o, aux)
            for wire in wires:
                sections = sections_for(wire) if sections_for else [wire]
                faces.extend(_pipe(spine.wire(), sections, o["orientation"], aux).Faces)
        except sweep_core.SweepError as exc:
            raise SurfaceError(str(exc))
    return surface_result(sew(faces))


STATIONS = 9  # sections along a guide rail that does not keep a straight course


def _rail_extent(path, rail, o, at_end=False):
    """Path + Guide Rail: the path and rail the sweep runs along. Guide Rail Distance takes
    that share of the rail (from the end the profile sits at); Perpendicular to Path stops
    where the plane square to the path through the rail's end (or the path's, when the path
    is the shorter) cuts the other; Full Extents runs each to its own end. at_end: the
    profile sits at the path's end (the sweep runs back along it)."""
    if at_end and not path.closed:
        back_path, back_rail = _rail_extent(path.reversed(), rail.reversed(), o)
        return back_path.reversed(), back_rail.reversed()
    share = float(o.get("rail_distance", 1.0))
    if share < 1e-6:
        raise SurfaceError("Guide Rail Distance is 0: type a share of the rail above 0.")
    if path.closed:
        return path, rail
    if share < 1.0 - 1e-9:
        rail = rail.sub(0.0, rail.length * share)
    if o.get("rail_extent", "perpendicular") != "perpendicular":
        return path, rail
    # where the plane square to the path end meets the rail, and the other way round
    end = path.end
    t = path.tangent_at(path.length)
    reach_rail = _plane_cut(rail, end, t)
    if reach_rail is not None and reach_rail < rail.length - 1e-6:
        return path, rail.sub(0.0, reach_rail)
    r_end = rail.end
    r_t = rail.tangent_at(rail.length)
    reach_path = _plane_cut(path, r_end, r_t)
    if reach_path is not None and reach_path < path.length - 1e-6:
        return path.sub(0.0, reach_path), rail
    return path, rail


def _plane_cut(curve_path, point, normal):
    """The length along `curve_path` where it crosses the plane through `point` square to
    `normal` (the last crossing), or None."""
    n = unit(normal)
    count = 200
    previous = None
    found = None
    for k in range(count + 1):
        s = curve_path.length * k / float(count)
        h = (curve_path.point_at(s) - point).dot(n)
        if previous is not None and (previous[1] < 0) != (h < 0):
            a, b = previous[0], s
            ha = previous[1]
            for _i in range(40):  # bisection on the crossing
                m = 0.5 * (a + b)
                hm = (curve_path.point_at(m) - point).dot(n)
                if (ha < 0) == (hm < 0):
                    a, ha = m, hm
                else:
                    b = m
            found = 0.5 * (a + b)
        previous = (s, h)
    return found


def _taper_sections(spine, wires, o, aux):
    """Taper Angle: the end section scaled about the path's end so that the profile's nearest
    point to the path moves out by length * tan(angle) (its farthest when the path runs
    through the profile)."""
    from . import sweep as sweep_core

    start = spine.start
    reach_ = min(w.distToShape(Part.Vertex(start))[0] for w in wires)
    if reach_ < 1e-6:
        reach_ = max((p - start).Length for w in wires for p in w.discretize(64))
    factor = core.taper_factor(spine.length, o["taper"], reach_)

    def sections(wire):
        end = sweep_core._transported(spine.wire(), wire, o["orientation"], aux, 2)[-1]
        scaled = end.copy()
        scaled.scale(factor, spine.end)
        return [wire, scaled]

    return sections


def _pipe(spine, sections, orientation, aux=None):
    if not isinstance(sections, (list, tuple)):
        sections = [sections]
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
        for section in sections:
            mk.add(section, False, False)
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
RAIL_STATIONS = 8  # sections fitted to the rails between two profiles (as the solid loft)


def loft_sections(sections, closed=False):
    """`sections`: wires (open or closed curves) or Part.Vertex (a point at either end)."""
    return loft_surface(sections, {"closed": bool(closed)})


def _check_loft_items(items, closed):
    if len(items) < 2:
        raise NeedsPick("Select at least two profiles, in loft order.")
    kinds = set()
    for i, s in enumerate(items):
        if s.ShapeType == "Vertex":
            if 0 < i < len(items) - 1:
                raise SurfaceError("A point can only be the first or the last profile.")
            continue
        kinds.add(s.isClosed())
    if len(kinds) > 1:
        raise SurfaceError(
            "Some profiles are closed and some are open. Loft open curves with open curves, "
            "closed with closed."
        )
    if closed and len(items) < 3:
        raise SurfaceError("A closed loft needs at least three profiles.")


def loft_surface(items, options, rails=None, centerline=None, profiles=None):
    """Fusion's surface Loft. items: the profiles in loft order (wires, or Part.Vertex at
    either end); options: closed, merge (Tangent Edges Merge), guide (rails | centerline),
    start_ / end_condition, _weight, _angle (loft_ends); rails: curves.Path list;
    centerline: a curves.Path; profiles: loft_ends.CurveSection per item (what each profile
    is, for the end conditions)."""
    from . import loft_ends

    o = core.with_defaults("loft", options)
    core.check_values("loft", o)
    closed = bool(o.get("closed"))
    if closed:
        o["end_condition"] = "free"  # the loop goes on from the last profile to the first
    items = list(items)
    guide_rails = o["guide"] == "rails" and bool(rails)
    guide_line = o["guide"] == "centerline" and centerline is not None
    if (guide_rails or guide_line) and closed:
        raise SurfaceError(
            "A closed loft cannot follow %s. Clear Closed or the %s."
            % (("rails", "rails") if guide_rails else ("a centerline", "centerline"))
        )
    _check_loft_items(items, closed)
    if o.get("merge"):
        items = [s if s.ShapeType == "Vertex" else loft_ends.merged_wire(s) for s in items]
    ends = loft_ends.active(o)
    if ends:
        if profiles is None or len(profiles) != len(items):
            raise SurfaceError("internal: the end conditions need the profiles")
        try:
            loft_ends.check(profiles, o, closed=closed)
        except loft_ends.EndError as exc:
            raise SurfaceError(str(exc))
    try:
        if guide_line:
            return surface_result(_loft_centerline(items, centerline, o, profiles, ends))
        if guide_rails:
            stations, kinds = _rail_stations(items, rails)
            if ends:
                return surface_result(_loft_rows(stations, kinds, profiles, o))
            return surface_result(_thru_shell(stations, False))
        if ends:
            kinds = list(range(len(items)))
            if closed:
                rows = [_profile_row(profiles[k], items[k]) for k in kinds]
                rows.append(rows[0])
                return surface_result(
                    loft_ends.thru_rows(
                        rows,
                        profiles[0],
                        profiles[0],
                        o,
                        solid=False,
                        closed=True,
                        first_next=profiles[1],
                    )
                )
            return surface_result(_loft_rows(items, kinds, profiles, o))
        # a plain loft (no rails, centerline or end conditions): corner meets corner. The
        # rail stations keep the pairing their rails give (_rail_stations reads the plain
        # loft of the profiles as given)
        return surface_result(_thru_shell(match_corners(items), closed))
    except loft_ends.EndError as exc:
        raise SurfaceError(str(exc))


def _corners_of(wire):
    """The points where a closed wire turns sharply (its corners), in order round it, with
    the index of the edge starting at each; [] when it has none (a circle, a smooth
    spline)."""
    edges = list(wire.OrderedEdges)
    found = []
    for i, edge in enumerate(edges):
        before = edges[i - 1]
        try:
            p = edge.valueAt(edge.FirstParameter)
            a = unit(before.tangentAt(before.LastParameter))
            b = unit(edge.tangentAt(edge.FirstParameter))
            if edge.Orientation == "Reversed":
                p = edge.valueAt(edge.LastParameter)
                b = unit(edge.tangentAt(edge.LastParameter)) * -1.0
            if before.Orientation == "Reversed":
                a = unit(before.tangentAt(before.FirstParameter)) * -1.0
        except Exception:
            return []
        if a.getAngle(b) > math.radians(1.0):
            found.append((i, p))
    return found


def match_corners(items):
    """Fusion's closed-profile loft (Sept 2026): when every profile is a closed curve with
    the same number of sharp corners, each one is restarted (and turned round if needed) so
    that corner i of one profile lofts to corner i of the next, the pairing with the least
    twist. Other profiles stay as they are."""
    wires = [w for w in items if w.ShapeType == "Wire"]
    if len(wires) != len(items) or len(wires) < 2 or not all(w.isClosed() for w in wires):
        return list(items)
    corners = [_corners_of(w) for w in wires]
    n = len(corners[0])
    if n < 3 or any(len(c) != n for c in corners):
        return list(items)
    out = [wires[0]]
    prev_points = [p for _i, p in corners[0]]
    prev_centre = wires[0].BoundBox.Center
    for wire, found in zip(wires[1:], corners[1:]):
        centre = wire.BoundBox.Center
        points = [p for _i, p in found]
        shift, reverse = core.corner_shift(
            [tuple(p) for p in prev_points],
            [tuple(p) for p in points],
            tuple(prev_centre),
            tuple(centre),
        )
        edges = list(wire.OrderedEdges)
        start = found[shift][0]
        try:
            if reverse:  # backwards from that corner: the edge ending there comes first
                ordered = [
                    edges[(start - 1 - k) % len(edges)].reversed() for k in range(len(edges))
                ]
            else:
                ordered = edges[start:] + edges[:start]
            new = Part.Wire(ordered)
            if not new.isClosed():
                new = wire
        except Exception:
            new = wire
        out.append(new)
        if reverse:
            prev_points = [points[(shift - i) % n] for i in range(n)]
        else:
            prev_points = [points[(shift + i) % n] for i in range(n)]
        prev_centre = centre
    return out


def _thru_shell(items, closed):
    try:
        return Part.makeLoft(list(items), False, False, bool(closed))
    except Exception as exc:
        raise SurfaceError(
            "The profiles cannot be lofted (%s). Check their order and that each is one "
            "connected curve." % exc
        )


def _profile_row(section, item):
    from . import loft_ends

    row = loft_ends.profile_row(section)
    if row.point is None:
        row.item = loft_ends.polynomial_wire(item)
    return row


def _loft_rows(items, kinds, profiles, o):
    """The loft through items (profiles: kinds[k] = their index; stations: None) with the end
    conditions of the first and the last profile (an open surface)."""
    from . import loft_ends

    rows = []
    for item, kind in zip(items, kinds):
        if kind is None:
            rows.append(loft_ends.station_row(item))
        else:
            rows.append(_profile_row(profiles[kind], item))
    return loft_ends.thru_rows(
        rows,
        profiles[0],
        profiles[-1],
        o,
        solid=False,
        first_next=profiles[1],
        last_next=profiles[-2],
    )


def _loft_centerline(items, centerline, o, profiles, ends):
    """The profiles lofted along the centerline (held square to it, like a sweep)."""
    from . import loft_ends

    try:
        mk = Part.BRepOffsetAPI.MakePipeShell(centerline.wire())
        mk.setTolerance(1e-6, 1e-4, 1e-2)
        mk.setFrenetMode(False)
        for item in items:
            mk.add(item, False, False)
        if not mk.isReady():
            raise SurfaceError("The loft cannot follow this centerline.")
        if ends:
            count = RAIL_STATIONS * (len(items) - 1) + len(items)
            stations = loft_ends.simulated(mk, count)
            if len(stations) < 2:
                raise SurfaceError("The loft cannot follow this centerline.")
            kinds = [None] * len(stations)
            stations[0], stations[-1] = items[0], items[-1]
            kinds[0], kinds[-1] = 0, len(items) - 1
            return _loft_rows(stations, kinds, profiles, o)
        mk.build()
        return mk.shape()
    except SurfaceError:
        raise
    except Exception as exc:
        raise SurfaceError(
            "The profiles cannot follow this centerline (%s). The centerline must run through "
            "the profiles in their order." % (str(exc) or type(exc).__name__)
        )


def _rail_stations(items, rails):
    """The profiles plus, between each pair, RAIL_STATIONS sections of the plain loft moved
    (one rail), or moved, turned and stretched along the line between the rails (two rails;
    the other way they keep the plain loft's size) so that they touch the rails.
    Returns (items, kinds): kinds[k] is the profile index, or None for a station."""
    from . import curves

    if any(s.ShapeType == "Vertex" for s in items):
        raise SurfaceError("Rails need curves as profiles at both ends, not points.")
    if len(rails) > 2:
        raise SurfaceError(
            "SciForge's loft follows one or two rails (%d picked). Take the others away."
            % len(rails)
        )
    base = _thru_shell(items, False)
    faces = list(base.Faces)
    if not faces:
        raise SurfaceError("The profiles cannot be lofted.")
    closed = items[0].isClosed()
    vs = [_profile_params(face, items) for face in faces]
    contacts = []  # contacts[j][i] = (share along profile i, length along rail j)
    for j, rail in enumerate(rails):
        row = []
        for i, wire in enumerate(items):
            try:
                gap, pairs, _info = rail.wire().distToShape(wire)
            except Exception:
                gap, pairs = 1.0, []
            size = max(1.0, wire.BoundBox.DiagonalLength)
            if gap > 1e-3 * size or not pairs:
                raise SurfaceError(
                    "Rail %d does not touch profile %d. A rail must run through every profile."
                    % (j + 1, i + 1)
                )
            point = pairs[0][1]
            path = _anchored(curves, _station(faces, [v[i] for v in vs]), faces, [v[i] for v in vs])
            row.append((path.length_at(point) / max(path.length, 1e-12), rail.length_at(point)))
        lengths = [r[1] for r in row]
        steps = [b - a for a, b in zip(lengths, lengths[1:])]
        if any(d <= 1e-9 for d in steps):
            raise SurfaceError(
                "Rail %d must run from the first profile to the last, through them in order."
                % (j + 1)
            )
        contacts.append(row)
    out, kinds = [], []
    for i in range(len(items) - 1):
        out.append(items[i])
        kinds.append(i)
        for k in range(1, RAIL_STATIONS + 1):
            t = k / float(RAIL_STATIONS + 1)
            here = [v[i] + (v[i + 1] - v[i]) * t for v in vs]
            wire = _station(faces, here)
            path = _anchored(curves, wire, faces, here)
            pairs = []
            for j, rail in enumerate(rails):
                share = core.lerp_fraction(contacts[j][i][0], contacts[j][i + 1][0], t, closed)
                q = path.point_at(share * path.length)
                along = contacts[j][i][1] + (contacts[j][i + 1][1] - contacts[j][i][1]) * t
                pairs.append((q, rail.point_at(along)))
            if len(pairs) == 1:
                matrix = core.similarity(
                    tuple(pairs[0][0]), tuple(pairs[0][0]), tuple(pairs[0][1]), tuple(pairs[0][1])
                )
            else:
                matrix = core.stretch_similarity(
                    tuple(pairs[0][0]), tuple(pairs[1][0]), tuple(pairs[0][1]), tuple(pairs[1][1])
                )
            out.append(wire.transformGeometry(_matrix(matrix)))
            kinds.append(None)
    out.append(items[-1])
    kinds.append(len(items) - 1)
    return out, kinds


def _matrix(rows):
    m = App.Matrix()
    for i in range(3):
        for j in range(4):
            setattr(m, "A%d%d" % (i + 1, j + 1), rows[i][j])
    return m


def _profile_params(face, items):
    """The v of each profile on one side face of the plain loft."""
    from . import loft_ends

    surface = face.Surface
    u0, u1, v0, v1 = face.ParameterRange
    um = (u0 + u1) / 2.0
    first = surface.value(um, v0)
    reverse = (
        items[-1].distToShape(Part.Vertex(first))[0]
        < items[0].distToShape(Part.Vertex(first))[0] - 1e-9
    )
    order = list(reversed(items)) if reverse else list(items)
    values = [v0]
    for item in order[1:-1]:
        row = loft_ends.Row(item, item.BoundBox.Center)
        values.append(loft_ends._nearest_v(surface, row, um, values[-1], v1))
    values.append(v1)
    return list(reversed(values)) if reverse else values


def _station(faces, vs):
    """The section of the loft's side faces at their v values (one per face)."""
    edges = []
    for face, v in zip(faces, vs):
        u0, u1, _v0, _v1 = face.ParameterRange
        edges.append(face.Surface.vIso(v).toShape(u0, u1))
    groups = Part.sortEdges(edges, 1e-5)
    if len(groups) != 1:
        raise SurfaceError("internal: a section of the loft falls apart")
    return Part.Wire(groups[0])


def _anchored(curves, wire, faces, vs):
    """The station wire as a curves.Path starting where the first side face starts at that
    v (the same place on every station, so shares along them match)."""
    u0, _u1, _v0, _v1 = faces[0].ParameterRange
    anchor = faces[0].Surface.value(u0, vs[0])
    path = curves.Path(list(wire.Edges), start_near=anchor)
    if path.closed:
        path = path.restarted(path.length_at(anchor))
    return path


# -- CREATE: Patch ---------------------------------------------------------------------------------
def patch(boundary, continuity="connected", interior=(), points=(), reverse=False):
    """Fusion's Patch: a surface filling closed boundary loops.

    boundary: [(edge, support face or None[, order])]; a support face (the face of a body
    the edge bounds) carries the continuity (Connected G0, Tangent G1, Curvature G2); sketch
    curves have none (Fusion ignores the continuity for them too). An order per edge (0, 1,
    2: Group Edges off) replaces `continuity` for that edge. interior: curves the patch
    must pass through; points: Part.Vertex / App.Vector it must pass through. reverse:
    Fusion's Reverse Normal in the Patch dialog (the patch faces the other way)."""
    group = core.CONTINUITY[continuity]
    boundary = [(b[0], b[1], group if len(b) < 3 or b[2] is None else int(b[2])) for b in boundary]
    order = max([o for _e, f, o in boundary if f is not None] or [0])
    edges = [e for e, _f, _o in boundary]
    wires = wires_of(edges)
    if not wires:
        raise NeedsPick("Select the boundary: edges of a body or sketch curves.")
    open_wires = [w for w in wires if not w.isClosed()]
    if open_wires:
        raise SurfaceError(
            "The boundary is not closed: %d of its curves do not meet another one at both "
            "ends. Pick curves that form a closed loop." % len(open_wires[0].Edges)
        )
    supports = [(e, f) for e, f, o in boundary if f is not None and o > 0]
    flat = plane_of(wires)
    plain = not supports and not interior and not points
    result = None
    if flat is not None and plain:
        try:
            result = Part.makeFace(wires, "Part::FaceMakerBullseye")
        except Exception:
            result = None
    if result is None:
        faces = []
        for wire in wires:
            faces.append(_fill(wire, boundary, order, interior, points))
        result = compound(faces)
    if reverse:
        result = result.copy()
        result.reverse()
    return surface_result(result)


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
    if any(o >= 2 and f is not None for _e, f, o in boundary) and not g2_available():
        raise SurfaceError(
            "Curvature continuity needs SciForge's next full build: FreeCAD 1.1.4 passes it "
            "to OpenCASCADE as a setting OpenCASCADE ignores (core patch #14 fixes it). Use "
            "Continuity Tangent for now."
        )
    mk = Part.BRepOffsetAPI.MakeFilling()
    for edge in wire.OrderedEdges:
        support, own = None, 0
        for e, f, o in boundary:
            if f is not None and (e.isSame(edge) or _same_place_edge([e], edge) is not None):
                support, own = f, o
                break
        if support is not None and own > 0:
            mk.add(edge, support, _occ_order(own), True)
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
    if order > 0 and any(f is not None and o > 0 for _e, f, o in boundary):
        # OpenCASCADE's patch bends a flat sheet along its normal: it cannot turn to meet
        # walls that rise square to it (a cylinder's rim), and then silently stays flat.
        # Fusion would make a dome; SciForge says so instead of faking tangency.
        off = _tangency_off(face, [(e, f) for e, f, o in boundary if o > 0])
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
def offset_faces(faces, distance, offset_type="sharp"):
    """New surfaces `distance` from the faces (positive along each face's normal). Offset
    Type Sharp: where the offset faces part at a convex corner they are carried on until
    they meet (OpenCASCADE's intersection join); Rounded: an arc of the distance about the
    corner fills the gap (arc join)."""
    if not faces:
        raise NeedsPick("Select the faces to offset.")
    d = float(distance)
    if abs(d) < 1e-7:
        raise NeedsPick("Drag the arrow or type a distance.")
    join = 2 if offset_type == "sharp" else 0
    out = []
    for piece in shells_or_faces(sew(faces)):
        try:
            result = piece.makeOffsetShape(d, 1e-6, False, False, 0, join, False)
            if join == 2 and (result.isNull() or not result.Faces or not result.isValid()):
                raise ValueError("the sharp corners do not close")
        except Exception as exc:
            if join == 2:
                raise SurfaceError(
                    "These faces cannot be offset by %g mm with sharp corners (%s). Try "
                    "Offset Type Rounded Offset, or a smaller distance." % (d, exc)
                )
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


def untrim_loops(target, loops, extend=0.0):
    """Untrim Type Manual: the loops (wires) holding the picked edges are removed from their
    faces; the outer one goes back to the face's own surface, pushed out by `extend`. A loop
    that touches another face cannot be removed (the API's rule)."""
    if not loops:
        raise NeedsPick("Select the loops to remove: click an edge of each.")
    free = free_edges(target)
    picked = {}
    for edge in loops:
        owners = faces_of_edge(target, edge)
        if not owners:
            raise SurfaceError("An edge picked has no face.")
        face = owners[0]
        wire = next((w for w in face.Wires if any(e.isSame(edge) for e in w.Edges)), None)
        if wire is None or not _free_wire(wire, free):
            raise SurfaceError(
                "That loop touches another face, so it cannot be untrimmed: only loops whose "
                "edges belong to one face can be removed. Unstitch the face first."
            )
        key = face.hashCode()
        picked.setdefault(key, (face, []))[1].append(wire)
    faces = []
    for face in target.Faces:
        entry = picked.get(face.hashCode())
        if entry is None or not any(face.isSame(entry[0]) for _x in [0]):
            faces.append(face)
            continue
        drop = entry[1]
        outer = face.OuterWire
        drop_outer = any(w.isSame(outer) for w in drop)
        base = _natural_face(face, float(extend or 0.0)) if drop_outer else None
        if base is None:
            base = Part.Face(face.Surface, outer)
        for hole in face.Wires:
            if hole.isSame(outer) or any(hole.isSame(w) for w in drop):
                continue
            try:
                base = base.cut(Part.Face(face.Surface, hole))
            except Exception:
                pass
        faces.extend(base.Faces)
    return surface_result(sew(faces))


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
    # a refitted face may differ from its neighbours' shared edges by a hair: sew loosely
    return surface_result(sew(faces, 1e-3 if len(faces) > 1 else 0.0))


# Surfaces whose own definition reaches past the face (toShape takes a bigger rectangle):
# u (around) of these is an angle, v runs on along a line or an arc.
_OPEN_SURFACES = (
    "Part::GeomCylinder",
    "Part::GeomCone",
    "Part::GeomSphere",
    "Part::GeomToroid",
    "Part::GeomSurfaceOfRevolution",
    "Part::GeomSurfaceOfExtrusion",
)
_ANGLE_IN_U = (
    "Part::GeomCylinder",
    "Part::GeomCone",
    "Part::GeomSphere",
    "Part::GeomToroid",
    "Part::GeomSurfaceOfRevolution",
)
REFIT = 24  # rows and columns of points a free-form face is refitted through


def _speed(surface, u, v, along_u):
    """How far the surface moves per unit of u (or v) at (u, v), in mm."""
    try:
        du, dv = surface.getD1(u, v)[1:3] if hasattr(surface, "getD1") else (None, None)
    except Exception:
        du = dv = None
    if du is None:
        h = 1e-4
        a = surface.value(u, v)
        b = surface.value(u + h, v) if along_u else surface.value(u, v + h)
        return max((b - a).Length / h, 1e-9)
    return max((du if along_u else dv).Length, 1e-9)


def _grow_rectangle(face, picked, d):
    """Natural Extend of a face that is its surface's parameter rectangle: the rectangle
    made bigger past each picked side by about `d` mm along the surface. Analytic surfaces
    (cylinders, cones, spheres, tori, revolved and extruded curves) carry their own
    definition on; free-form ones (B-spline, Bezier) are carried on by their own polynomial
    and refitted through REFIT x REFIT points (OpenCASCADE cannot trim a B-spline beyond
    its bounds). None when the face is not a parameter rectangle."""
    surface = face.Surface
    kind = surface.TypeId
    if kind == "Part::GeomPlane":
        return None
    if len(face.Wires) != 1:
        return None
    u0, u1, v0, v1 = face.ParameterRange
    um, vm = 0.5 * (u0 + u1), 0.5 * (v0 + v1)
    grow = [0.0, 0.0, 0.0, 0.0]
    for edge in picked:
        mid = edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2.0)
        try:
            u, v = surface.parameter(mid)
        except Exception:
            return None
        if abs(u - u0) < 1e-6:
            grow[0] = d / _speed(surface, u0, v, True)
        elif abs(u - u1) < 1e-6:
            grow[1] = d / _speed(surface, u1, v, True)
        elif abs(v - v0) < 1e-6:
            grow[2] = d / _speed(surface, u, v0, False)
        elif abs(v - v1) < 1e-6:
            grow[3] = d / _speed(surface, u, v1, False)
        else:
            return None
    # every edge of the face must lie on the rectangle (a trimmed face is not one)
    for edge in face.Edges:
        if edge.Length < 1e-9:
            continue  # a sphere's pole
        mid = edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2.0)
        try:
            u, v = surface.parameter(mid)
        except Exception:
            return None
        on = min(abs(u - u0), abs(u - u1), abs(v - v0), abs(v - v1))
        if on > 1e-5 * max(1.0, abs(u1 - u0), abs(v1 - v0)):
            return None
    a, b, c_, e = u0 - grow[0], u1 + grow[1], v0 - grow[2], v1 + grow[3]
    if kind in _ANGLE_IN_U and b - a > 2 * math.pi + 1e-9:
        raise SurfaceError(
            "The extension would wrap the curved face round onto itself. Use a smaller distance."
        )
    if kind == "Part::GeomSphere" and (c_ < -math.pi / 2 - 1e-9 or e > math.pi / 2 + 1e-9):
        raise SurfaceError(
            "The extension would run past the sphere's pole. Use a smaller distance."
        )
    if kind == "Part::GeomToroid" and e - c_ > 2 * math.pi + 1e-9:
        raise SurfaceError(
            "The extension would wrap the torus round onto itself. Use a smaller distance."
        )
    bounded = _bounded_params(surface)
    if kind in _OPEN_SURFACES and not _outside(bounded, (a, b, c_, e)):
        try:
            grown = surface.toShape(a, b, c_, e)
            if grown.isValid():
                return grown
        except Exception:
            pass
    return _refit(surface, (a, b, c_, e), (um, vm))


def _bounded_params(surface):
    """The surface's own parameter bounds where they are finite and not periodic (a
    revolved B-spline's v, a free-form surface), as (u0, u1, v0, v1) with None for open."""
    try:
        b = list(surface.bounds())
    except Exception:
        return (None, None, None, None)
    out = []
    for i, x in enumerate(b):
        periodic = False
        try:
            periodic = surface.isUPeriodic() if i < 2 else surface.isVPeriodic()
        except Exception:
            pass
        out.append(None if periodic or abs(x) > 1e50 else x)
    return tuple(out)


def _outside(bounds, rect):
    u0, u1, v0, v1 = rect
    lo_u, hi_u, lo_v, hi_v = bounds
    return (
        (lo_u is not None and u0 < lo_u - 1e-9)
        or (hi_u is not None and u1 > hi_u + 1e-9)
        or (lo_v is not None and v0 < lo_v - 1e-9)
        or (hi_v is not None and v1 > hi_v + 1e-9)
    )


def _refit(surface, rect, _middle):
    """A B-spline face through the surface's own points over `rect` (past its bounds the
    surface's last polynomial pieces carry it on)."""
    u0, u1, v0, v1 = rect
    grid = []
    for i in range(REFIT + 1):
        u = u0 + (u1 - u0) * i / float(REFIT)
        row = []
        for j in range(REFIT + 1):
            v = v0 + (v1 - v0) * j / float(REFIT)
            row.append(surface.value(u, v))
        grid.append(row)
    try:
        fitted = Part.BSplineSurface()
        fitted.interpolate(grid)
        face = fitted.toShape()
    except Exception as exc:
        raise SurfaceError("This face cannot be carried on naturally (%s). Try Tangent." % exc)
    if not face.isValid():
        raise SurfaceError("This face cannot be carried on naturally. Try Tangent.")
    return face


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
                if abs(solid.Volume) > 1e-9:  # a face sewn onto a copy of itself is no solid
                    pieces.append(solid)
                    continue
            except Exception:
                pass
        pieces.append(piece)
    result = compound(pieces)
    return surface_result(result), _open_count(result)


def stitched_operation(base, stitched, operation):
    """Stitch with Join / Cut / Intersect: the closed stitch (`stitched`, from stitch())
    combined with the solid `base`. A stitch that does not close is refused."""
    solids = list(stitched.Solids)
    if not solids:
        raise SurfaceError(
            "The surfaces do not close into a solid, so the stitch cannot %s. Close the gaps "
            "(a bigger tolerance or more surfaces), or use New Body." % operation.capitalize()
        )
    tool = solids[0] if len(solids) == 1 else Part.makeCompound(solids)
    if base is None or base.isNull() or not base.Solids:
        raise SurfaceError("Join, Cut and Intersect need a solid body to act on.")
    return thicken_cut(base, tool, operation)


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
