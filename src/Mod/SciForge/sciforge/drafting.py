# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Draft (type Fixed Plane) on top of FreeCAD's PartDesign::Draft, without GUI
code: the Draft dialog (draft_ui.py) and the golden-model builder both use this module.

What the user picks:
  plane  the fixed plane: an origin plane, a construction plane of the body, or a flat
         face of the part. The drafted faces turn about the line where they meet it.
  faces  the faces to tilt (flat side faces, or round ones whose axis is the pull
         direction). Tangent Chain picks the faces that continue a picked one smoothly.
Options: {"angle": degrees, "flip": bool, "tangent": bool}.

The pull direction is the way a mould would be pulled off the part: across the plane,
out of a picked face (its outward side) or along an origin/construction plane's normal,
and "flip" turns it round. A positive angle makes the part narrower toward the pull
direction, as Fusion does. FreeCAD's Draft always pulls along the plane's own normal
and has a Reversed switch; apply() works out which to use.

FreeCAD's Draft is silent about some failures (a face it cannot tilt is just skipped,
with a message in the Report view only), so check() refuses such faces first and
undrafted() finds any face the result left untouched.
"""
import json
import math

NATIVE = "PartDesign::Draft"
PLANE_TYPES = ("App::Plane", "PartDesign::Plane")
META = "SciForgeDraft"
PARALLEL = 1.0 - 1e-6


class DraftError(ValueError):
    """The draft cannot be made; the message says why and what to try."""


def default_options():
    return {"angle": 1.0, "flip": False, "tangent": True}


def is_draft(obj):
    return obj is not None and getattr(obj, "TypeId", "") == NATIVE


def _unit(vector):
    v = vector.__class__(vector)
    if v.Length > 1e-12:
        v.normalize()
    return v


# -- the plane -------------------------------------------------------------------------
def is_plane_object(obj):
    return obj is not None and getattr(obj, "TypeId", "") in PLANE_TYPES


def plane_label(ref):
    obj, sub = ref
    if sub:
        return "%s (%s)" % (sub, obj.Label)
    return obj.Label


def plane_frame(ref):
    """(point, FreeCAD's plane axis, default pull direction) of a plane reference
    (object, element name) in the body's coordinates. Raises DraftError."""
    import FreeCAD as App

    obj, sub = ref
    if obj is None:
        raise DraftError("Pick the fixed plane first.")
    if not sub:
        if not is_plane_object(obj):
            raise DraftError("The fixed plane must be a plane or a flat face.")
        place = obj.Placement
        axis = _unit(place.Rotation.multVec(App.Vector(0, 0, 1)))
        return App.Vector(place.Base), axis, axis
    try:
        face = obj.Shape.getElement(sub)
    except Exception:
        raise DraftError("The fixed plane %s no longer exists. Pick it again." % sub)
    if face.Surface.__class__.__name__ != "Plane":
        raise DraftError("The fixed plane must be flat: pick a flat face or a plane.")
    axis = _unit(face.Surface.Axis)
    point = face.CenterOfMass
    u, v = face.Surface.parameter(point)
    outward = _unit(face.normalAt(u, v))  # points out of the solid (feature guide #4)
    return point, axis, outward


def pull_direction(ref, flip=False):
    """Unit pull direction (body coordinates) for the plane reference."""
    _point, _axis, pull = plane_frame(ref)
    return -pull if flip else pull


def reversed_flag(ref, flip=False):
    """FreeCAD's Draft.Reversed giving our pull direction (FreeCAD pulls along the axis)."""
    _point, axis, _pull = plane_frame(ref)
    return pull_direction(ref, flip).dot(axis) < 0


# -- the faces -------------------------------------------------------------------------
def why_not(shape, name, pull, plane_ref=None):
    """Why face `name` cannot be drafted with this pull direction, or "" if it can."""
    if plane_ref is not None and plane_ref[1] == name:
        return "The fixed plane's own face cannot be drafted."
    try:
        face = shape.getElement(name)
    except Exception:
        return "%s no longer exists." % name
    kind = face.Surface.__class__.__name__
    if kind == "Plane":
        u, v = face.Surface.parameter(face.CenterOfMass)
        normal = _unit(face.normalAt(u, v))
        if abs(normal.dot(pull)) >= PARALLEL:
            return "A face parallel to the fixed plane cannot be drafted."
        return ""
    if kind in ("Cylinder", "Cone"):
        if abs(_unit(face.Surface.Axis).dot(pull)) >= PARALLEL:
            return ""
        return "A round face can only be drafted when its axis is the pull direction."
    return "This kind of face (%s) cannot be drafted." % kind.lower()


def tangent_faces(shape, names):
    from . import shelling

    return shelling.tangent_faces(shape, names)


def check(shape, plane_ref, names, options):
    """Raise DraftError if the draft cannot be made (before touching the document)."""
    if plane_ref is None or plane_ref[0] is None:
        raise DraftError("Pick the fixed plane first (a plane or a flat face).")
    if not names:
        raise DraftError("Pick the faces to draft.")
    angle = float(options.get("angle", 0.0))
    if abs(angle) < 1e-9:
        raise DraftError("The draft angle must not be 0.")
    if abs(angle) >= 89.9:
        raise DraftError("The draft angle must be between -89.9 and 89.9 degrees.")
    pull = pull_direction(plane_ref, bool(options.get("flip")))
    for name in names:
        reason = why_not(shape, name, pull, plane_ref)
        if reason:
            raise DraftError("%s (%s)" % (reason, name))


def undrafted(base_shape, result_shape, names):
    """Faces of `names` the result left as they were (FreeCAD skips a face it cannot tilt
    and only says so in the Report view)."""
    left = []
    for name in names:
        try:
            face = base_shape.getElement(name)
        except Exception:
            continue
        for other in result_shape.Faces:
            if (
                abs(other.Area - face.Area) < 1e-7 * max(1.0, face.Area)
                and (other.CenterOfMass - face.CenterOfMass).Length < 1e-6
                and other.Surface.__class__ is face.Surface.__class__
            ):
                left.append(name)
                break
    return left


# -- the angle handle --------------------------------------------------------------------
def handle_frame(shape, plane_ref, names, options):
    """Where the angle handle goes: (pivot point, turning axis, zero direction) in the
    body's coordinates, or None. The handle turns about the line where the first drafted
    face meets the fixed plane (turning toward axis x zero is a positive angle)."""
    if plane_ref is None or not names:
        return None
    try:
        point0, _axis, _out = plane_frame(plane_ref)
        pull = pull_direction(plane_ref, bool(options.get("flip")))
        face = shape.getElement(names[0])
    except Exception:
        return None
    center = face.CenterOfMass
    try:
        u, v = face.Surface.parameter(center)
        normal = _unit(face.normalAt(u, v))
    except Exception:
        return None
    if face.Surface.__class__.__name__ != "Plane":
        # a round face: use the tangent plane at its middle
        u0, u1, v0, v1 = face.ParameterRange
        center = face.valueAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)
        normal = _unit(face.normalAt((u0 + u1) / 2.0, (v0 + v1) / 2.0))
    axis = normal.cross(pull)
    if axis.Length < 1e-6:
        return None
    axis = _unit(axis)
    across = axis.cross(normal)  # in the face, across the pivot line
    denom = across.dot(pull)
    if abs(denom) < 1e-9:
        return None
    s = (point0 - center).dot(pull) / denom
    pivot = center + across * s
    # The handle sits on the face's continuation beyond the pivot line, outside the part:
    # a handle inside the see-through part could not be grabbed (Coin gives the click to
    # the part's face in front of it). Turning it leans that continuation, so positive
    # angles still lean the face itself into the part.
    toward_face = center - pivot
    zero = -pull if toward_face.dot(pull) >= 0 else pull
    return pivot, axis, zero


# -- the feature -------------------------------------------------------------------------
def load_meta(feature):
    try:
        return json.loads(getattr(feature, META, "") or "{}")
    except Exception:
        return {}


def _save_meta(feature, meta):
    if META not in feature.PropertiesList:
        feature.addProperty("App::PropertyString", META, "Base", "", 4)  # hidden
    text = json.dumps(meta, sort_keys=True)
    if getattr(feature, META) != text:
        setattr(feature, META, text)


def _set(feature, prop, value):
    from . import shelling

    shelling._set(feature, prop, value)


def owner_body(obj):
    from . import shelling

    return shelling.owner_body(obj)


def solid_base(body):
    from . import shelling

    return shelling.solid_base(body)


def apply(feature, base, plane_ref, names, options, formula=""):
    """Write the picks and options onto the Draft feature."""
    names = list(names or [])
    old = feature.Base
    if not (old and old[0] is base and [s for s in old[1] if s] == names):
        feature.Base = (base, names)
    obj, sub = plane_ref
    old_plane = feature.NeutralPlane
    if not (old_plane and old_plane[0] is obj and [s for s in old_plane[1] if s] == [sub]):
        feature.NeutralPlane = (obj, [sub] if sub else [""])
    if feature.PullDirection is not None and feature.PullDirection[0] is not None:
        feature.PullDirection = None  # pulled across the plane (Fusion's Fixed Plane)
    flip = bool(options.get("flip"))
    _set(feature, "Reversed", reversed_flag(plane_ref, flip))
    from . import shelling

    shelling._set_formula(feature, "Angle", formula or "")
    _set(feature, "Angle", float(options.get("angle", 1.0)))
    if not feature.Refine:
        feature.Refine = True  # Fusion never leaves seam faces
    _save_meta(
        feature,
        {"v": 1, "flip": flip, "tangent": bool(options.get("tangent", True)), "formula": formula},
    )


def make(body, base, plane_ref, names, options, name="Draft", formula=""):
    """A new Draft at the end of `body` on `base` (normally body.Tip). Not recomputed."""
    if base is None or base.Shape.isNull() or not base.Shape.Solids:
        raise DraftError("Make a solid first (Create Sketch, then Extrude).")
    feature = body.newObject(NATIVE, name)
    body.Tip = feature  # newObject() does not always move the Tip (feature guide #5)
    apply(feature, base, plane_ref, names, options, formula)
    return feature


def read(feature):
    """(base, plane_ref, names, options, formula) of an existing Draft."""
    meta = load_meta(feature)
    link = feature.Base
    base = feature.BaseFeature or (link[0] if link else None)
    names = [s for s in (link[1] if link else []) if s]
    plane = feature.NeutralPlane
    plane_ref = None
    if plane and plane[0] is not None:
        subs = [s for s in plane[1] if s]
        plane_ref = (plane[0], subs[0] if subs else "")
    options = default_options()
    options["angle"] = feature.Angle.Value
    flip = bool(meta.get("flip", False))
    if plane_ref is not None and "flip" not in meta:
        # A draft made elsewhere: find the flip that gives its Reversed.
        try:
            flip = reversed_flag(plane_ref, False) != bool(feature.Reversed)
        except DraftError:
            flip = False
    options["flip"] = flip
    options["tangent"] = bool(meta.get("tangent", True))
    from . import shelling

    formula = shelling.formula_of(feature, "Angle")
    return base, plane_ref, names, options, formula


def remove(feature):
    from . import shelling

    shelling.remove(feature)


def friendly(text):
    """FreeCAD's error text for a failed Draft (often empty), in plain words."""
    low = (text or "").lower()
    if not low or "failed" in low or "command not done" in low or "null" in low:
        return "The faces cannot be tilted this far: try a smaller angle, or draft fewer faces."
    if "multiple solids" in low:
        return "This draft would cut the part into pieces. Try a smaller angle."
    if "neutral plane" in low and "planar" in low:
        return "The fixed plane must be flat: pick a flat face or a plane."
    return text


def to_degrees(radians):
    return math.degrees(radians)
