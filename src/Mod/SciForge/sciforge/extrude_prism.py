# SPDX-License-Identifier: LGPL-2.1-or-later
"""The solid an extrusion sweeps (no boolean with the body), built with Part only.

PartDesign's Pad and Pocket build this themselves for Join and Cut. Intersect, thin
extrudes and tapers PartDesign cannot make have no PartDesign feature, so SciForge's own
extrude feature builds the same prism here and keeps, adds or removes it. The rules copy
Pad's, so switching an extrude between Join, Cut and Intersect keeps the same shape:

  - taper: positive widens the extrusion along its direction (Fusion: "outward"),
    holes follow the outer boundary's draft (FreeCAD's "same as outer");
  - symmetric: the distance is the whole length, half on each side;
  - "to object": up to a flat face or plane (extended), a curved face (its whole surface)
    or a body (where the extrusion first meets it), like Fusion's To Object; a taper ends
    there too (Fusion tapers every extent). Fusion's Extend choices: To Adjacent Faces ends
    on the face and its neighbours as they are (a compound of faces, never extended),
    Through Body goes on through the body to where it leaves it; an offset moves the end
    that far along the extrusion (past the object; negative: short of it).

Thin extrude (Fusion's Extrude type "Thin Extrude"): a wall of a given thickness along the
profile's outline instead of the filled profile. Closed profiles (sketch areas, flat faces)
get a wall along every loop of their outline (a rectangle gives a rectangular tube, a ring
a wall at both circles); open sketch curves (a line, an L, an arc) get a wall along the
curve. Wall Location: "side1" (closed: into the profile; open: to the left of the curve,
seen from the sketch's normal), "side2" (the other side) or "center" (half on each side).
A taper tilts the wall and keeps its thickness (positive: towards side two, i.e. outward
for a closed profile).
"""

import math

import FreeCAD as App
import Part

TOL = 1e-7
LOCATIONS = ("side1", "center", "side2")
JOIN = 2  # makeOffset2D: "intersection" (sharp corners, like a wall drawn with lines)


class PrismError(ValueError):
    pass


def big_length(shapes, point):
    """A length that reaches past everything in `shapes`, starting at `point`."""
    size = 1.0
    for shape in shapes:
        if shape is None or shape.isNull():
            continue
        box = shape.BoundBox
        size = max(size, box.DiagonalLength + (box.Center - point).Length)
    return 2.0 * size + 10.0


def tapered(face, vec, taper_deg):
    """Solid swept by `face` along `vec`, its walls tilted by `taper_deg`."""
    if abs(taper_deg) < 1e-9:
        return face.extrude(vec)
    if abs(taper_deg) >= 89.9:
        raise PrismError("The taper angle must be between -89.9 and 89.9 degrees.")
    length = vec.Length
    delta = length * math.tan(math.radians(taper_deg))
    outer = face.OuterWire

    def drafted(wire):
        try:
            top = wire.makeOffset2D(delta, 2, False, False, False)
        except Exception:
            raise PrismError(
                "The taper angle is too steep for this profile over %.4g mm: the profile "
                "would shrink to nothing. Use a smaller angle or a shorter distance." % length
            )
        top.translate(vec)
        return Part.makeLoft([wire, top], True, True)

    solid = drafted(outer)
    for wire in face.Wires:
        if wire.isSame(outer):
            continue
        solid = solid.cut(drafted(wire))
    return solid


# -- thin walls ------------------------------------------------------------------------------
class Wall:
    """One piece of a thin extrude's cross-section: the band along one closed loop of a
    profile, or along one open curve. ``face`` is the band at the profile plane;
    ``extrude(vec, taper)`` sweeps it, keeping the wall's thickness under a taper."""

    def __init__(self, face, curve=None, thickness=0.0, on_left=True, normal=None):
        self.face = face
        self.curve = curve  # an open wire (None for the band of a closed loop)
        self.thickness = thickness  # of the band of `curve`
        self.on_left = on_left  # the band lies on the curve's left (seen from `normal`)
        self.normal = normal

    def extrude(self, vec, taper_deg):
        if abs(taper_deg) < 1e-9:
            return self.face.extrude(vec)
        if self.curve is None:
            return tapered(self.face, vec, taper_deg)  # a closed band: both loops drafted alike
        if abs(taper_deg) >= 89.9:
            raise PrismError("The taper angle must be between -89.9 and 89.9 degrees.")
        delta = vec.Length * math.tan(math.radians(taper_deg))
        # A positive taper tilts the wall towards side two (the curve's right), like a
        # closed profile's wall tilts outward: the band at the top is the band of the curve
        # moved that far sideways (a ruled loft between the two keeps the thickness).
        moved = _shift_open(self.curve, -delta, self.normal)
        if moved is None:
            raise PrismError(
                "The taper is too steep for this curve over %.4g mm. Use a smaller angle or "
                "a shorter distance." % vec.Length
            )
        top = band_of_open(moved, self.thickness, self.on_left, self.normal)
        top.translate(vec)
        try:
            solid = Part.makeLoft([self.face.OuterWire, top.OuterWire], True, True)
        except Exception as exc:
            raise PrismError("The tapered wall cannot be made: %s" % (str(exc) or "OCC error"))
        if solid.isNull() or solid.Volume < TOL:
            raise PrismError("The tapered wall has no volume. Use a smaller angle.")
        return solid


def band_of_open(wire, thickness, on_left, normal):
    """The band `thickness` wide on the left (or right) of an open curve."""
    left = _side_sign(wire, normal, thickness)  # the offset distance that goes left
    return _open_band(wire, left if on_left else -left, normal)


def _ordered_vertexes(wire):
    """The vertexes of a wire in the order it runs (TopExp's order is not that order)."""
    try:
        found = list(wire.OrderedVertexes)
        if found:
            return found
    except Exception:
        pass
    return list(wire.Vertexes)


def _straight(wire):
    """(start, unit direction) when every edge of `wire` lies on one straight line."""
    edges = wire.Edges
    if not edges or any(
        e.Curve.TypeId not in ("Part::GeomLine", "Part::GeomLineSegment") for e in edges
    ):
        return None
    points = [v.Point for v in _ordered_vertexes(wire)]
    start = points[0]
    far = max(points, key=lambda p: (p - start).Length)
    d = far - start
    if d.Length < TOL:
        return None
    d.normalize()
    for p in points:
        off = p - start
        if (off - d * off.dot(d)).Length > 1e-7:
            return None
    return start, d


def _left(wire, normal):
    """The unit vector to the left of the curve at the middle of its first edge (seen from
    `normal`), and that point."""
    edge = wire.OrderedEdges[0] if hasattr(wire, "OrderedEdges") else wire.Edges[0]
    mid = (edge.FirstParameter + edge.LastParameter) / 2.0
    point = edge.valueAt(mid)
    tangent = edge.tangentAt(mid)
    if edge.Orientation == "Reversed":
        tangent = tangent * -1.0
    left = App.Vector(normal).cross(tangent)
    if left.Length < 1e-12:
        raise PrismError("The curve does not lie in the sketch's plane.")
    left.normalize()
    return left, point


def _open_band(wire, signed, normal):
    """The band between an open curve and its offset by `signed` (makeOffset2D's sign
    convention for this wire, see _side_sign)."""
    line = _straight(wire)
    if line is not None:
        # A straight wire has no plane of its own for OpenCASCADE: built directly.
        start, d = line
        points = [v.Point for v in _ordered_vertexes(wire)]
        lo = min((p - start).dot(d) for p in points)
        hi = max((p - start).dot(d) for p in points)
        a, b = start + d * lo, start + d * hi
        left = App.Vector(normal).cross(d)
        left.normalize()
        shift = left * signed
        return Part.Face(Part.makePolygon([a, b, b + shift, a + shift, a]))
    try:
        band = wire.makeOffset2D(signed, JOIN, True, True)
    except Exception as exc:
        raise PrismError(
            "The wall cannot follow this curve: %s. Try a thinner wall." % (str(exc) or "OCC")
        )
    faces = band.Faces
    if len(faces) > 1:
        try:
            faces = band.removeSplitter().Faces
        except Exception:
            pass
    if len(faces) != 1 or band.Area < TOL:
        raise PrismError("The wall cannot follow this curve. Try a thinner wall.")
    return faces[0]


def _side_sign(wire, normal, thickness):
    """The makeOffset2D distance that puts a band of `thickness` on the curve's left
    (OpenCASCADE's sign depends on the plane it finds for an open wire)."""
    if _straight(wire) is not None:
        return thickness  # _open_band builds straight bands with "left" = positive
    left, point = _left(wire, normal)
    probe = point + left * min(thickness * 0.5, 1e-3 + thickness * 0.25)
    try:
        band = wire.makeOffset2D(thickness, JOIN, True, True)
        if band.isInside(probe, 1e-6, True):
            return thickness
    except Exception:
        pass
    return -thickness


def _shift_open(wire, signed, normal):
    """The open curve moved sideways by `signed` towards its left (negative: right), or
    None when the offset collapses."""
    if abs(signed) < 1e-12:
        return wire.copy()
    line = _straight(wire)
    if line is not None:
        _start, d = line
        left = App.Vector(normal).cross(d)
        left.normalize()
        moved = wire.copy()
        moved.translate(left * signed)
        return moved
    sign = 1.0 if _side_sign(wire, normal, abs(signed)) > 0 else -1.0
    try:
        moved = wire.makeOffset2D(signed * sign, JOIN, False, True)
    except Exception:
        return None
    if moved.isNull() or not moved.Edges:
        return None
    return moved if moved.ShapeType == "Wire" else Part.Wire(moved.Edges)


TOO_THICK = (
    "The wall is too thick for this profile: it closes up inside it. Use a thinner wall or "
    "another Wall Location."
)


def _offset_region(region, distance):
    """The flat face `region` grown (distance > 0) or shrunk (< 0) by |distance|. A face
    made from a hole's loop faces the other way, and OpenCASCADE then grows it for a
    negative distance: the direction is checked by the area."""
    bigger = distance > 0
    for d in (distance, -distance):
        try:
            found = region.makeOffset2D(d, JOIN)
        except Exception:
            continue
        if found.isNull() or not found.Faces:
            continue
        if (found.Area > region.Area) == bigger:
            return found
    raise PrismError(TOO_THICK)


def _closed_band(wire, outward, inward):
    """The band around a closed loop from `inward` inside it to `outward` outside it (mm,
    both >= 0), as a face with a hole. Worked out on a face of the loop alone (a face's
    offset grows it for a positive distance, whatever way its wire runs)."""
    region = Part.Face(Part.Wire(wire.OrderedEdges if hasattr(wire, "OrderedEdges") else wire))
    outer = _offset_region(region, outward) if outward > TOL else region
    inner = _offset_region(region, -inward) if inward > TOL else region
    if inner.Area < TOL:
        raise PrismError(TOO_THICK)
    band = outer.cut(inner)
    try:
        band = band.removeSplitter()
    except Exception:
        pass
    if (
        band.isNull()
        or band.Area < TOL
        or abs(band.Area - (outer.Area - inner.Area)) > 1e-6 * (1.0 + outer.Area)
    ):
        raise PrismError(TOO_THICK)
    return band


def thin_walls(faces, wires, normal, location, thickness):
    """The cross-section of a thin extrude: a Wall per closed loop of `faces` and per open
    curve of `wires`, `thickness` thick at `location` ("side1" | "center" | "side2")."""
    thickness = float(thickness)
    if thickness < 1e-6:
        raise PrismError("The wall thickness must be more than zero.")
    if location not in LOCATIONS:
        raise PrismError("unknown wall location %r" % location)
    half = thickness / 2.0
    walls = []
    for face in faces:
        outer = face.OuterWire
        for wire in face.Wires:
            hole = not wire.isSame(outer)
            # side1 = into the profile: inward from the outline, outward from a hole.
            if location == "center":
                outward, inward = half, half
            elif (location == "side1") != hole:
                outward, inward = 0.0, thickness
            else:
                outward, inward = thickness, 0.0
            band = _closed_band(wire, outward, inward)
            for piece in band.Faces:
                walls.append(Wall(piece, normal=normal))
    for wire in wires:
        if wire.isClosed():
            face = Part.Face(wire)
            walls.extend(thin_walls([face], [], normal, location, thickness))
            continue
        sides = {"side1": [True], "side2": [False], "center": [True, False]}[location]
        size = half if location == "center" else thickness
        for on_left in sides:
            band = band_of_open(wire, size, on_left, normal)
            walls.append(Wall(band, wire, size, on_left, normal))
    if not walls:
        raise PrismError("The profile has no outline to make a wall along.")
    return walls


# -- to object -----------------------------------------------------------------------------
def _plane_of(target):
    """(point, normal) of a flat face or a plane shape, or None for anything else."""
    surface = getattr(target, "Surface", None)
    if target.ShapeType == "Face" and surface is not None and hasattr(surface, "Axis"):
        if surface.TypeId == "Part::GeomPlane":
            return target.CenterOfMass, App.Vector(surface.Axis)
    if target.Solids:
        return None
    faces = target.Faces
    if len(faces) == 1 and faces[0].Surface.TypeId != "Part::GeomPlane":
        return None
    plane = target.findPlane() if hasattr(target, "findPlane") else None
    if plane is None:
        return None
    return App.Vector(plane.Position), App.Vector(plane.Axis)


def _beyond(target, start, direction, size):
    """A big slab on the far side of `target`'s plane, seen from `start`."""
    point, normal = _plane_of(target)
    normal = App.Vector(normal).normalize()
    if abs(normal.dot(direction)) < 1e-9:
        raise PrismError("The object is parallel to the extrusion direction; it cannot end there.")
    if (start - point).dot(normal) > 0:
        normal = normal * -1.0
    # A square on the target plane, then pushed away from the profile.
    helper = App.Vector(1, 0, 0) if abs(normal.x) < 0.9 else App.Vector(0, 1, 0)
    u = normal.cross(helper).normalize()
    v = normal.cross(u).normalize()
    corners = [point + u * a * size + v * b * size for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    square = Part.Face(Part.makePolygon(corners + [corners[0]]))
    return square.extrude(normal * size)


def farthest(shapes, start, direction):
    """How far along `direction` (from `start`) the shapes reach: where a join through All
    ends (the part's last point that way, like PartDesign's "up to last")."""
    best = 0.0
    for shape in shapes:
        if shape is None or shape.isNull():
            continue
        points = [v.Point for v in shape.Vertexes]
        try:
            points += list(shape.tessellate(0.05)[0])
        except Exception:
            pass
        for point in points:
            best = max(best, (App.Vector(point) - start).dot(direction))
    return best


def _section_faces(sections):
    return [s.face if isinstance(s, Wall) else s for s in sections]


def _sweep(sections, vec, taper):
    pieces = []
    for section in sections:
        if isinstance(section, Wall):
            pieces.append(section.extrude(vec, taper))
        else:
            pieces.append(tapered(section, vec, taper))
    return pieces[0] if len(pieces) == 1 else pieces[0].fuse(pieces[1:])


def _starts(sections, direction):
    """Points just past the profile, one per section (which pieces of a trimmed prism
    hold the profile)."""
    found = []
    for face in _section_faces(sections):
        try:
            point = _inside_point(face)
        except Exception:
            point = face.CenterOfMass
        found.append(point + direction * 1e-3)
    return found


def _inside_point(face):
    """A point well inside a flat face (a band's centre of mass lies in its hole): the
    centre of its biggest triangle."""
    center = face.CenterOfMass
    if face.isInside(center, 1e-6, True):
        return center
    try:
        points, triangles = face.tessellate(0.1)
        best = None
        for a, b, c in triangles:
            pa, pb, pc = App.Vector(points[a]), App.Vector(points[b]), App.Vector(points[c])
            area = (pb - pa).cross(pc - pa).Length
            if best is None or area > best[0]:
                best = (area, (pa + pb + pc) * (1.0 / 3.0))
        if best is not None:
            return best[1]
    except Exception:
        pass
    return center


def _keep_start(pieces, starts, what):
    kept = []
    for solid in pieces:
        if any(solid.isInside(p, 1e-6, True) for p in starts):
            kept.append(solid)
    if not kept:
        raise PrismError(
            "The extrusion does not reach %s in this direction. Pick another object or flip." % what
        )
    return kept[0] if len(kept) == 1 else kept[0].fuse(kept[1:])


def _surface_shape(face, size):
    """The whole surface a curved face lies on (a cylinder's face: the whole cylinder),
    big enough to cut a prism `size` long: Fusion's To Object ends on the face extended."""
    surface = face.Surface
    try:
        kind = surface.TypeId
        if kind in ("Part::GeomCylinder", "Part::GeomCone"):
            return surface.toShape(0.0, 2.0 * math.pi, -size, size)
        if kind in ("Part::GeomSphere", "Part::GeomToroid"):
            return surface.toShape()
    except Exception:
        pass
    return face  # a free-form face ends the extrusion where it is


def _to_shape(sections, direction, target, run_hint, taper, reach, through=False):
    """The prism up to a curved face or a whole body: a long prism, split by the target,
    keeping the pieces that hold the profile. Raises when part of the profile misses it.
    through: Fusion's Through Body, the prism goes on through the body to where it leaves
    it (with any gap inside the body on the way)."""
    import BOPTools.SplitAPI as split_api

    starts = _section_faces(sections)
    origin = starts[0].CenterOfMass
    run = big_length(list(reach) + [target] + starts, origin)
    prism = _sweep(sections, direction * run, taper)
    points = _starts(sections, direction)
    if target.Solids:
        what = "the body"
        trimmed = prism.cut(target)
        pieces = trimmed.Solids
        kept = _keep_start(pieces, points, what)
        if through:
            inside = prism.common(target).Solids
            if not inside:
                raise PrismError(
                    "The extrusion does not reach the body in this direction. Pick another "
                    "object or flip."
                )
            # gaps inside the body on the way: pieces that do not run on to the far end
            gaps = [
                p
                for p in pieces
                if not any(p.isInside(q, 1e-6, True) for q in points)
                and farthest([p], origin, direction) < run * 0.98
            ]
            kept = kept.fuse(inside + gaps)
            try:
                kept = kept.removeSplitter()
            except Exception:
                pass
    else:
        what = "the face" if len(target.Faces) == 1 else "the face and the faces next to it"
        tool = _surface_shape(target.Faces[0], run * 2.0) if len(target.Faces) == 1 else target
        try:
            pieces = split_api.slice(prism, [tool], "Split").Solids
        except Exception as exc:
            raise PrismError("The extrusion cannot end on that face: %s" % (str(exc) or "OCC"))
        kept = _keep_start(pieces, points, what)
    reached = farthest([kept], origin, direction)
    if reached > run * 0.98:
        raise PrismError(
            "Part of the profile misses %s, so the extrusion would never end there. Pick "
            "another object, or a face that covers the whole profile." % what
        )
    return kept


def side(faces, direction, method, length, taper, target=None, reach=(), extend="", offset=0.0):
    """The prism of one side: method "Length" | "ThroughAll" | "UpToFace" | "UpToLast".
    `faces`: the profile faces, or the Walls of a thin extrude (thin_walls). UpToFace:
    `extend` "adjacent" (target is the face and its neighbours: never extended) or
    "through" (a body: on through it); `offset` moves the end along the extrusion."""
    direction = App.Vector(direction).normalize()
    if method == "UpToFace" and target is not None and abs(float(offset)) > TOL:
        target = target.copy()
        target.translate(direction * float(offset))
    flat = _section_faces(faces)
    start = flat[0].CenterOfMass
    if method == "Length":
        if length < TOL:
            raise PrismError("The distance must not be zero.")
        run = length
    elif method == "UpToLast":
        run = farthest(reach, start, direction)
        if run < TOL:
            raise PrismError(
                "The part does not go on past the profile this way, so All reaches nothing. "
                "Flip the direction or use Distance."
            )
    elif method == "UpToFace":
        if target is None:
            raise PrismError("Pick the face or plane the extrusion goes to.")
        if extend == "through" and target.Solids:
            return _to_shape(faces, direction, target, length, taper, reach, through=True)
        if extend == "adjacent" or _plane_of(target) is None:
            return _to_shape(faces, direction, target, length, taper, reach)
        run, exact = _run_to_plane(flat, direction, target)
    else:
        run = big_length(list(reach) + list(flat), start)
    prism = _sweep(faces, direction * run, taper)
    if method == "UpToFace" and not exact:
        prism = prism.cut(_beyond(target, start, direction, run * 4.0))
    return prism


def _run_to_plane(faces, direction, target):
    """(length, exact) to reach the target's plane from the profile along `direction`.
    A plane parallel to the profile is reached exactly (no trimming, so a taper ends
    right there); an inclined one is passed a little and the prism trimmed by it. The
    target's own size never matters (an origin plane is endless)."""
    point, normal = _plane_of(target)
    normal = App.Vector(normal).normalize()
    denom = direction.dot(normal)
    if abs(denom) < 1e-9:
        raise PrismError("The object is parallel to the extrusion direction; it cannot end there.")
    points = []
    for face in faces:
        points += [v.Point for v in face.Vertexes]
        try:
            points += list(face.tessellate(0.05)[0])
        except Exception:
            pass
        points.append(face.CenterOfMass)
    runs = [(point - App.Vector(p)).dot(normal) / denom for p in points]
    if max(runs) < TOL:
        raise PrismError(
            "The object is behind the profile in this direction. Pick another one or flip."
        )
    if abs(abs(denom) - 1.0) < 1e-9 and max(runs) - min(runs) < 1e-7:
        return max(runs), True
    return max(runs) * 1.05 + 1.0, False


def _moved(shapes, vec):
    moved = []
    for shape in shapes:
        shape = shape.copy()
        shape.translate(vec)
        moved.append(shape)
    return moved


def build(faces, normal, spec, reach=(), wires=()):
    """The full prism. spec keys: side_type ("One side" | "Two sides" | "Symmetric"),
    reversed, start_offset, type, length, taper, target, extend, offset, type2, length2,
    taper2, target2, extend2, offset2, and for a thin extrude "thin": {"location",
    "thickness", "location2", "thickness2"} (`wires`: the open curves of a thin extrude's
    profile)."""
    normal = App.Vector(normal).normalize()
    offset = float(spec.get("start_offset", 0.0))
    wires = list(wires or [])
    if abs(offset) > TOL:
        faces = _moved(faces, normal * offset)
        wires = _moved(wires, normal * offset)
    thin = spec.get("thin")
    if not faces and not (thin and wires):
        raise PrismError("The profile has no closed area to extrude.")

    def sections(second=False):
        if not thin:
            return faces
        location = thin.get("location2" if second else "location", "side1")
        thickness = thin.get("thickness2" if second else "thickness", 1.0)
        return thin_walls(faces, wires, normal, location, thickness)

    direction = normal * (-1.0 if spec.get("reversed") else 1.0)
    side_type = spec.get("side_type", "One side")
    parts = []
    if side_type == "Symmetric":
        half = float(spec.get("length", 0.0)) / 2.0
        first = sections()
        for d in (direction, direction * -1.0):
            parts.append(
                side(
                    first,
                    d,
                    spec.get("type", "Length"),
                    half,
                    spec.get("taper", 0.0),
                    spec.get("target"),
                    reach,
                )
            )
    else:
        parts.append(
            side(
                sections(),
                direction,
                spec.get("type", "Length"),
                float(spec.get("length", 0.0)),
                spec.get("taper", 0.0),
                spec.get("target"),
                reach,
                spec.get("extend", ""),
                spec.get("offset", 0.0),
            )
        )
        if side_type == "Two sides":
            parts.append(
                side(
                    sections(second=True),
                    direction * -1.0,
                    spec.get("type2", "Length"),
                    float(spec.get("length2", 0.0)),
                    spec.get("taper2", 0.0),
                    spec.get("target2"),
                    reach,
                    spec.get("extend2", ""),
                    spec.get("offset2", 0.0),
                )
            )
    prism = parts[0] if len(parts) == 1 else parts[0].fuse(parts[1:])
    try:
        prism = prism.removeSplitter()
    except Exception:
        pass
    if prism.isNull() or prism.Volume < TOL:
        raise PrismError("The extrusion has no volume.")
    return prism
