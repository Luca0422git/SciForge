# SPDX-License-Identifier: LGPL-2.1-or-later
"""Press Pull's Offset Type (no Qt; the Press Pull dialog and the golden-model builder use it).

Fusion's Press Pull on faces has an Offset Type (Autodesk support article "Press Pull does not
create a timeline feature in Fusion"; Community answers):
  Automatic                 Fusion edits the feature that made the face when it can, and adds an
                            Offset Face step when it cannot. SciForge: a fillet's or chamfer's
                            face changes its size, a face of an open base feature is baked into
                            it, every other face gets a Press Pull step (whether Fusion's
                            Automatic also lengthens an extrude when its end face is pulled is
                            not settled by the sources: Modify Existing Feature does that)
  Modify Existing Feature   the feature that made the face is changed, no new step: the end face
                            of an extrude (Distance) makes the extrude longer or shorter, a face
                            moved by an earlier Press Pull / Offset Face changes that step's
                            distance; a face no feature can change that way is refused with the
                            reason
  New Offset                always a new Press Pull step (also on a fillet's face, which is then
                            offset instead of getting another radius)
"""

import FreeCAD as App

from . import bodies

TYPES = ("automatic", "modify", "new")
LABELS = {
    "automatic": "Automatic",
    "modify": "Modify Existing Feature",
    "new": "New Offset",
}
TIPS = {
    "automatic": "Change the feature that made the face when that is how Fusion edits it (a "
    "fillet's radius), else add a Press Pull step",
    "modify": "Change the feature that made the face (an extrude's distance, an earlier Press "
    "Pull's distance): no new step",
    "new": "Always add a new Press Pull step that offsets the faces",
}
TOL = 1e-6


class OffsetTypeError(ValueError):
    """Modify Existing Feature cannot change these faces; the message says why."""


def _normal(face):
    u0, u1, v0, v1 = face.ParameterRange
    return App.Vector(face.normalAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)).normalize()


def _inner_point(face):
    from . import drafting

    return drafting._inner_point(face)


def _extrude_cap(feature, face):
    """+1 / -1 when `face` (body coordinates) lies on the far end of the extrusion of
    `feature` (a one-sided Distance extrude), the sign saying whether pushing the face out of
    the part makes the extrude longer; None otherwise."""
    from . import pattern_adjust

    spec_tuple = pattern_adjust.extrude_spec(feature)
    if spec_tuple is None:
        return None
    faces, wires, normal, spec, _how = spec_tuple
    if wires or not faces:
        return None  # a thin extrude's wall: no single end face
    if spec.get("side_type", "One side") != "One side" or spec.get("type") != "Length":
        return None
    if face.Surface.TypeId != "Part::GeomPlane":
        return None
    direction = App.Vector(normal).normalize() * (-1.0 if spec.get("reversed") else 1.0)
    n = _normal(face)
    if abs(abs(n.dot(direction)) - 1.0) > 1e-9:
        return None
    start = float(spec.get("start_offset", 0.0))
    length = float(spec.get("length", 0.0))
    point = _inner_point(face)
    profile = faces[0]
    reach = (point - profile.CenterOfMass).dot(direction)
    if abs(reach - (start + length)) > TOL:
        return None
    back = point - direction * reach
    if not any(p.isInside(back, 1e-6, True) for p in faces):
        return None
    return 1 if n.dot(direction) > 0 else -1


def _offset_cap(feature, face):
    """+1 when `face` (body coordinates) is where an earlier Press Pull / Offset Face step put
    one of its faces (pushing it further out makes that step's distance bigger); else None."""
    from . import presspull

    if not presspull.is_press_pull(feature) or face.Surface.TypeId != "Part::GeomPlane":
        return None
    link = getattr(feature, "Faces", None)
    if not link or not link[1]:
        return None
    distance = float(feature.Distance.Value)
    n = _normal(face)
    point = _inner_point(face)
    for name in link[1]:
        try:
            moved = link[0].Shape.getElement(name)
        except Exception:
            continue
        if moved.Surface.TypeId != "Part::GeomPlane":
            continue
        n0 = _normal(moved)
        if n.dot(n0) < 1.0 - 1e-9:
            continue
        if abs((point - moved.CenterOfMass).dot(n0) - distance) <= TOL:
            return 1
    return None


def _steps_upto(body, base):
    """The body's solid steps up to `base` (included): what made the faces of `base`."""
    found = []
    for obj in bodies.solid_steps(body):
        found.append(obj)
        if obj is base:
            break
    return found


def modify_target(body, base, names):
    """(feature, property, change per mm) of what Modify Existing Feature changes for faces
    `names` of `base` (the step before the Press Pull): an extrude's "Length" (+1 / -1 per mm
    pushed out of the part) or an earlier Press Pull's "Distance" (+1). The latest step that
    put the face where it is wins. Raises OffsetTypeError with the reason."""
    if not names:
        raise OffsetTypeError("Pick the faces to push or pull.")
    found = None
    for name in names:
        try:
            face = base.Shape.getElement(name)
        except Exception:
            raise OffsetTypeError("The face %s no longer exists." % name)
        hit = None
        for feature in reversed(_steps_upto(body, base)):
            sign = _offset_cap(feature, face)
            if sign is not None:
                hit = (feature, "Distance", sign)
                break
            sign = _extrude_cap(feature, face)
            if sign is not None:
                hit = (feature, "Length", sign)
                break
        if hit is None:
            raise OffsetTypeError(
                "%s was not made as the end of an extrude or by an earlier Press Pull, so no "
                "feature can be changed to move it. Use New Offset (a Press Pull step)." % name
            )
        if any(path.lstrip(".") == hit[1] for path, _e in hit[0].ExpressionEngine):
            raise OffsetTypeError(
                "The distance of %s follows a parameter or a formula: change it there (Change "
                "Parameters), or use New Offset." % hit[0].Label
            )
        if found is None:
            found = hit
        elif found[0] is not hit[0] or found[2] != hit[2]:
            raise OffsetTypeError(
                "The faces come from different features: Modify Existing Feature changes one "
                "feature. Pick the faces of one extrude end, or use New Offset."
            )
    return found


def check_length(feature, prop, value):
    if prop == "Distance":  # a Press Pull: in or out, but it must still move the faces
        if abs(value) <= 1e-6:
            raise OffsetTypeError(
                "That would make the distance of %s 0: the faces would not move. Use another "
                "distance." % feature.Label
            )
        return
    if value <= 1e-6:
        raise OffsetTypeError(
            "That would make %s %s %.4g mm: it must stay longer than 0. Pull less far."
            % (feature.Label, prop.lower(), value)
        )


def apply(feature, prop, start, sign, distance):
    """Set the feature's value for a push of `distance` mm (from `start`, its value before the
    dialog). Returns the new value."""
    value = float(start) + float(sign) * float(distance)
    check_length(feature, prop, value)
    current = getattr(feature, prop)
    current = getattr(current, "Value", current)
    if abs(float(current) - value) > 1e-12:
        setattr(feature, prop, value)
    return value
