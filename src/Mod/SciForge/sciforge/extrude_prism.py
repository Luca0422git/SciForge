# SPDX-License-Identifier: LGPL-2.1-or-later
"""The solid an extrusion sweeps (no boolean with the body), built with Part only.

PartDesign's Pad and Pocket build this themselves for Join and Cut. Intersect has no
PartDesign feature, so SciForge's Intersect extrude builds the same prism here and
keeps only the part of the body inside it. The rules copy Pad's, so switching an
extrude between Join, Cut and Intersect keeps the same shape:

  - taper: positive widens the extrusion along its direction (Fusion: "outward"),
    holes follow the outer boundary's draft (FreeCAD's "same as outer");
  - symmetric: the distance is the whole length, half on each side;
  - "to object": up to a flat face or plane (extended), like Fusion's To Object.
"""
import math

import FreeCAD as App
import Part

TOL = 1e-7


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


def _plane_of(target):
    """(point, normal) of a flat face or a plane shape."""
    surface = getattr(target, "Surface", None)
    if target.ShapeType == "Face" and surface is not None and hasattr(surface, "Axis"):
        if surface.TypeId == "Part::GeomPlane":
            return target.CenterOfMass, App.Vector(surface.Axis)
    plane = target.findPlane() if hasattr(target, "findPlane") else None
    if plane is None:
        raise PrismError("Extruding up to a curved face is not available for Intersect yet.")
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


def side(faces, direction, method, length, taper, target=None, reach=()):
    """The prism of one side: method "Length" | "ThroughAll" | "UpToFace" | "UpToLast"."""
    direction = App.Vector(direction).normalize()
    start = faces[0].CenterOfMass
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
        run, exact = _run_to_plane(faces, direction, target)
    else:
        run = big_length(list(reach) + list(faces), start)
    pieces = [tapered(face, direction * run, taper) for face in faces]
    prism = pieces[0] if len(pieces) == 1 else pieces[0].fuse(pieces[1:])
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


def build(faces, normal, spec, reach=()):
    """The full prism. spec keys: side_type ("One side" | "Two sides" | "Symmetric"),
    reversed, start_offset, type, length, taper, target, type2, length2, taper2, target2."""
    normal = App.Vector(normal).normalize()
    offset = float(spec.get("start_offset", 0.0))
    if abs(offset) > TOL:
        moved = []
        for face in faces:
            face = face.copy()
            face.translate(normal * offset)
            moved.append(face)
        faces = moved
    direction = normal * (-1.0 if spec.get("reversed") else 1.0)
    side_type = spec.get("side_type", "One side")
    parts = []
    if side_type == "Symmetric":
        half = float(spec.get("length", 0.0)) / 2.0
        for d in (direction, direction * -1.0):
            parts.append(
                side(
                    faces,
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
                faces,
                direction,
                spec.get("type", "Length"),
                float(spec.get("length", 0.0)),
                spec.get("taper", 0.0),
                spec.get("target"),
                reach,
            )
        )
        if side_type == "Two sides":
            parts.append(
                side(
                    faces,
                    direction * -1.0,
                    spec.get("type2", "Length"),
                    float(spec.get("length2", 0.0)),
                    spec.get("taper2", 0.0),
                    spec.get("target2"),
                    reach,
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
