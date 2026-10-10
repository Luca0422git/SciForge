# SPDX-License-Identifier: LGPL-2.1-or-later
"""Press/Pull geometry (outline 7.0, 9.1). Needs FreeCAD's Part module, no GUI.

What the selection means, as in Fusion's Press Pull:
  faces         -> move the faces along their normals by `distance`
                   (positive = outward = add material, negative = remove)
  edges         -> fillet the edges, `distance` is the radius
  a fillet face -> edit that fillet's radius

How faces are moved: the slab of material between each face and its offset
copy (exact prisms for planes, rings for cylinders, OpenCASCADE's offset with
fill for other surfaces) is fused to / cut from the body. Where a slab's side
does not continue a face that stays put, it leaves a "step": a sloped
neighbour, or the corner between two moved faces that share an edge. Fusion
extends the neighbours instead; SciForge does the same by removing the step
faces with OpenCASCADE's defeaturing (BRepAlgoAPI_Defeaturing), which extends
the adjacent faces until they meet. Spike 9.1 compared the alternatives:
BRepOffsetAPI_MakeOffsetShape (join Intersection) offsets every face of the
solid and per-face values (SetOffsetOnFace) are not reachable from Python;
LocOpe/BRepFeat need a profile; defeaturing works on the B-rep FreeCAD already
has and gives exact planes (golden models pp_multi_face_corner and
pp_slanted_neighbours).
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


def press_pull(base, faces, distance, refine=True, report=None):
    """New shape: `base` with `faces` (Part.Face objects of base) moved by `distance` mm.

    Like Fusion, the faces next to the moved ones are extended (or trimmed) to meet them:
    a sloped side keeps its slope, two pulled faces that share an edge meet in a filled
    corner. The slabs give the moved faces; where a slab's side does not merge with an
    unmoved face it is a "step", and OpenCASCADE's defeaturing removes it by extending
    the neighbours until they meet (BRepAlgoAPI_Defeaturing). `report`, a list, gets a
    note when the neighbours could not be extended (the step then stays)."""
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
    steps = step_faces(base, faces, slabs, result)
    if steps:
        healed = extend_neighbours(result, steps, refine)
        if healed is not None:
            result = healed
        elif report is not None:
            report.append(
                "The faces next to the moved ones could not be extended to meet them; "
                "the result keeps a step there."
            )
    check_result(base, result, distance)
    return result


def _same_surface(a, b, tol=1e-6):
    """True if two faces lie on the same plane or the same cylinder."""
    sa, sb = a.Surface, b.Surface
    kind = type(sa).__name__
    if kind != type(sb).__name__:
        return False
    if kind == "Plane":
        na, nb = sa.Axis, sb.Axis
        if abs(abs(na.dot(nb)) - 1.0) > tol:
            return False
        return abs((sb.Position - sa.Position).dot(na)) < 1e-5
    if kind == "Cylinder":
        if abs(sa.Radius - sb.Radius) > 1e-5:
            return False
        if abs(abs(sa.Axis.dot(sb.Axis)) - 1.0) > tol:
            return False
        offset = sb.Center - sa.Center
        return (offset - sa.Axis * offset.dot(sa.Axis)).Length < 1e-5
    return False


def _parallel_surface(a, b, tol=1e-6):
    """Parallel planes, or cylinders on the same axis (any radius): a face and its offset."""
    sa, sb = a.Surface, b.Surface
    kind = type(sa).__name__
    if kind != type(sb).__name__:
        return False
    if kind == "Plane":
        return abs(abs(sa.Axis.dot(sb.Axis)) - 1.0) < tol
    if kind == "Cylinder":
        if abs(abs(sa.Axis.dot(sb.Axis)) - 1.0) > tol:
            return False
        offset = sb.Center - sa.Center
        return (offset - sa.Axis * offset.dot(sa.Axis)).Length < 1e-5
    return _same_surface(a, b)


def _on_face(face, point, tol=1e-5):
    try:
        return face.isInside(point, tol, True)
    except Exception:
        return False


def step_faces(base, moved, slabs, result):
    """Faces of `result` left by the side of a slab that does not continue a face which
    stays where it is: they have to go (the neighbours are extended instead)."""
    unmoved = [f for f in base.Faces if not any(f.isSame(m) or same_face(f, m) for m in moved)]
    sides = []
    for face, solid in zip(moved, slabs):
        for side in solid.Faces:
            if _parallel_surface(side, face):
                continue  # the slab's bottom (the face itself) or its top (the moved face)
            sides.append(side)
    steps = []
    for candidate in result.Faces:
        if any(_same_surface(candidate, u) for u in unmoved):
            continue
        point = _inner_point(candidate)
        for side in sides:
            if _same_surface(candidate, side) and _on_face(side, point):
                steps.append(candidate)
                break
    return steps


def _inner_point(face):
    center = face.CenterOfMass
    if _on_face(face, center):
        return center
    u0, u1, v0, v1 = face.ParameterRange
    for i in range(1, 8):
        for j in range(1, 8):
            p = face.valueAt(u0 + (u1 - u0) * i / 8.0, v0 + (v1 - v0) * j / 8.0)
            if _on_face(face, p):
                return p
    return center


def extend_neighbours(shape, steps, refine=True):
    """`shape` without the step faces, its neighbours extended to close the gap
    (OpenCASCADE defeaturing). None if that fails or gives an invalid solid."""
    try:
        healed = shape.defeaturing(steps)
        if refine:
            healed = healed.removeSplitter()
    except Exception:
        return None
    if healed.isNull() or not healed.Solids or not healed.isValid():
        return None
    if len(healed.Solids) != len(shape.Solids):
        return None
    return healed


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


# -- picking faces while the preview shows the result --------------------------------------
def moved_surface(face, distance):
    """A face whose surface is `face`'s surface moved by `distance` (for matching clicks
    on the preview), or None for surfaces that are not planes or cylinders."""
    import Part

    kind = type(face.Surface).__name__
    try:
        if kind == "Plane":
            moved = face.copy()
            moved.translate(face_normal(face) * distance)
            return moved
        if kind == "Cylinder":
            surf = face.Surface
            u0, u1, v0, v1 = face.ParameterRange
            um, vm = (u0 + u1) / 2.0, (v0 + v1) / 2.0
            point = face.valueAt(um, vm)
            axis = surf.Axis
            radial = point - (surf.Center + axis * axis.dot(point - surf.Center))
            grows = face.normalAt(um, vm).dot(radial) > 0
            radius = surf.Radius + (distance if grows else -distance)
            if radius <= TOL:
                return None
            return Part.Cylinder(surf.Center, surf.Center + axis, radius).toShape()
    except Exception:
        return None
    return None


def match_pick(base, picked, point, selected=(), distance=0.0):
    """Which face of `base` a click on `picked` (a face of the preview) means: the base face
    on the same surface under the click point, else on the same surface, else a selected
    face whose moved copy was clicked. Returns "FaceN" or None."""
    for i, face in enumerate(base.Faces, start=1):
        if same_face(face, picked):
            return "Face%d" % i  # the very same face: the part before any change
    candidates = []
    for i, face in enumerate(base.Faces, start=1):
        if _same_surface(face, picked):
            candidates.append(("Face%d" % i, face))
    if point is not None:
        for name, face in candidates:
            if _on_face(face, point, 1e-4):
                return name
    if candidates:
        return candidates[0][0]
    for name in selected:
        try:
            moved = moved_surface(base.getElement(name), distance)
        except Exception:
            moved = None
        if moved is not None and _same_surface(moved, picked):
            return name
    return None


def _normal_near(face, point):
    u, v = face.Surface.parameter(point)
    return face.normalAt(u, v)


def tangent_chain(shape, names):
    """The faces of `shape` reached from `names` across smooth (tangent) edges, like
    Fusion's Tangent Chain: picking one face of a filleted run picks the whole run."""
    faces = shape.Faces
    index = {"Face%d" % i: face for i, face in enumerate(faces, start=1)}
    found = list(names)
    queue = list(names)
    while queue:
        name = queue.pop(0)
        face = index[name]
        for other_name, other in index.items():
            if other_name in found:
                continue
            for edge in face.Edges:
                if not any(edge.isSame(e) for e in other.Edges):
                    continue
                mid = edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2.0)
                try:
                    a = _normal_near(face, mid)
                    b = _normal_near(other, mid)
                except Exception:
                    continue
                if a.getAngle(b) < math.radians(1.0):
                    found.append(other_name)
                    queue.append(other_name)
                    break
    return found
