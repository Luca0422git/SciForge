# SPDX-License-Identifier: LGPL-2.1-or-later
"""Press/Pull geometry (outline 7.0, 9.1). Needs FreeCAD's Part module, no GUI.

What the selection means, as in Fusion's Press Pull:
  faces         -> move the faces along their normals by `distance`
                   (positive = outward = add material, negative = remove)
  edges         -> fillet the edges, `distance` is the radius
  a fillet face -> edit that fillet's radius

How faces are moved (v1): the slab of material between each face and its
offset copy is built with OpenCASCADE's offset (BRepOffset, "fill" mode) and
fused to / cut from the body. This is exact for faces whose neighbours meet
them at right angles (boxes, pockets, holes, bosses: most printable parts).
Known gap: where a neighbour is slanted, Fusion extends the neighbour, v1
leaves a step. Multi-face edits that share an edge leave the corner unfilled.
Both are tracked as xfail golden models (pp_*); the fix is a per-face offset
in C++ (BRepOffset_MakeOffset::SetOffsetOnFace), outline 9.1.
"""
import math

TOL = 1e-6


class PressPullError(ValueError):
    """The edit would not give a valid solid; the message says why and what to try."""


def face_normal(face):
    u0, u1, v0, v1 = face.ParameterRange
    return face.normalAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)


def slab(face, distance):
    """Solid between a face and its copy offset by `distance` along its outward normal.

    Planes and cylinders are built exactly (prism / revolved ring) so their side
    and end faces are true planes that merge with the neighbours when refined,
    like Fusion's result. Other surfaces use OpenCASCADE's offset with fill."""
    kind = type(face.Surface).__name__
    try:
        if kind == "Plane":
            solid = face.extrude(face_normal(face) * distance)
        elif kind == "Cylinder":
            solid = _cylinder_slab(face, distance)
        else:
            solid = face.makeOffsetShape(distance, TOL, False, False, 0, 0, True)
    except PressPullError:
        raise
    except Exception as exc:
        raise PressPullError(
            "This face cannot be offset by %g mm (%s). Try a smaller distance." % (distance, exc)
        )
    if solid.isNull() or solid.Volume < TOL:
        raise PressPullError("Offsetting this face by %g mm gives no material." % distance)
    return solid


def _cylinder_slab(face, distance):
    import FreeCAD as App
    import Part

    surf = face.Surface
    axis = App.Vector(surf.Axis).normalize()
    center = App.Vector(surf.Center)
    radius = surf.Radius
    u0, u1, v0, v1 = face.ParameterRange
    # Which way is "outward" for this face: away from the axis (a boss) or towards it (a hole)?
    um, vm = (u0 + u1) / 2.0, (v0 + v1) / 2.0
    point = face.valueAt(um, vm)
    radial = point - (center + axis * axis.dot(point - center))
    outward_grows = face.normalAt(um, vm).dot(radial) > 0
    new_radius = radius + distance if outward_grows else radius - distance
    if new_radius <= TOL:
        raise PressPullError(
            "Pushing this round face by %g mm would shrink its radius (%g mm) to nothing. "
            "Use a distance smaller than the radius." % (distance, radius)
        )
    r_in, r_out = sorted((radius, new_radius))
    start = face.valueAt(u0, vm)
    direction = start - (center + axis * axis.dot(start - center))
    direction.normalize()
    bottom = center + axis * axis.dot(face.valueAt(u0, v0) - center)
    top = center + axis * axis.dot(face.valueAt(u0, v1) - center)
    profile = Part.Face(
        Part.makePolygon(
            [
                bottom + direction * r_in,
                bottom + direction * r_out,
                top + direction * r_out,
                top + direction * r_in,
                bottom + direction * r_in,
            ]
        )
    )
    sweep = math.degrees(u1 - u0)
    if sweep >= 360.0 - 1e-6:
        sweep = 360.0
    return profile.revolve(center, axis, sweep)


def press_pull(base, faces, distance, refine=True):
    """New shape: `base` with `faces` (Part.Face objects of base) moved by `distance` mm."""
    if not faces:
        raise PressPullError("Select one or more faces to push or pull.")
    if abs(distance) < TOL:
        return base.copy()
    slabs = [slab(face, distance) for face in faces]
    tool = slabs[0] if len(slabs) == 1 else slabs[0].multiFuse(slabs[1:])
    try:
        result = base.fuse(tool) if distance > 0 else base.cut(tool)
        if refine:
            result = result.removeSplitter()
    except Exception as exc:
        raise PressPullError("The kernel could not combine the result: %s" % exc)
    check_result(base, result, distance)
    return result


def check_result(base, result, distance):
    if result.isNull() or not result.Solids:
        raise PressPullError(
            "Pushing by %g mm would remove the whole body. Use a smaller distance." % distance
        )
    if len(result.Solids) > len(base.Solids):
        raise PressPullError(
            "Pushing by %g mm would cut the part into separate pieces (the offset collapses a "
            "wall). Use a smaller distance." % distance
        )
    if not result.isValid():
        raise PressPullError(
            "The result is not a valid solid. Try a smaller distance or fewer faces."
        )


def same_face(a, b, tol=1e-6):
    """Geometric identity check that survives re-computation (same surface, size, position)."""
    if a.isSame(b):
        return True
    if type(a.Surface) is not type(b.Surface):
        return False
    if abs(a.Area - b.Area) > tol * max(1.0, a.Area):
        return False
    return (a.CenterOfMass - b.CenterOfMass).Length < 1e-5


def face_names(shape, faces):
    """Element names ("Face3") in `shape` of the given faces, matched geometrically."""
    names = []
    for face in faces:
        for i, candidate in enumerate(shape.Faces, start=1):
            if same_face(face, candidate):
                names.append("Face%d" % i)
                break
        else:
            raise PressPullError("A selected face is not on the current end of the body.")
    return names


def is_round_blend(face):
    return type(face.Surface).__name__ in (
        "Cylinder",
        "Toroid",
        "SurfaceOfRevolution",
        "BSplineSurface",
        "OffsetSurface",
    )


def owning_fillet(body, face):
    """The Fillet/Chamfer feature of `body` that created `face`, or None.

    A face was made by a fillet if it exists in the fillet's result but not in
    the fillet's input (BaseFeature)."""
    for feature in reversed(body.Group):
        if feature.TypeId not in ("PartDesign::Fillet", "PartDesign::Chamfer"):
            continue
        base = feature.BaseFeature
        if base is None or feature.Shape.isNull():
            continue
        made_here = any(same_face(face, f) for f in feature.Shape.Faces) and not any(
            same_face(face, f) for f in base.Shape.Faces
        )
        if made_here:
            return feature
    return None


def describe(distance):
    return "%+.3g mm" % distance if not math.isnan(distance) else "?"
