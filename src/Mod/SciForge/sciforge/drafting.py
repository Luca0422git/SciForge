# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Draft (Fixed Plane and Parting Line, One Side / Two Side / Symmetric), without
GUI code: the Draft dialog (draft_ui.py) and the golden-model builder both use this module.

What the user picks:
  plane  the fixed plane: an origin plane, a construction plane of the body, or a flat
         face of the part. The drafted faces turn about the line where they meet it.
  faces  the faces to tilt: faces that run along the pull direction (flat, round or
         free-form side walls; flat and conical faces may lean already). Tangent Chain picks
         the faces that continue a picked one smoothly.
Options: {"angle": degrees, "flip": bool, "tangent": bool, "draft_type": "fixed" or
"parting", "sides": "one", "two" or "symmetric", "angle2": degrees, "parting": [refs]}.

Fixed Plane, One Side is FreeCAD's PartDesign::Draft. Two Side and Symmetric (the faces split
at the fixed plane, each side drafted away from it: Angle 1 toward the pull direction, Angle 2
(Two Side) or Angle 1 (Symmetric) toward the other way) and Parting Line (Fusion: the faces
turn about a parting line, a plane, a flat face, edges or sketch curves; the pull direction
is picked on its own; Fix Parting Line keeps the line where it is; One Side drafts the pull
side only) are SciForge's DraftFeature at the end of this file.

The pull direction is the way a mould would be pulled off the part: across the plane,
out of a picked face (its outward side) or along an origin/construction plane's normal,
and "flip" turns it round. A positive angle makes the part narrower toward the pull
direction, as Fusion does. FreeCAD's Draft always pulls along the plane's own normal
and has a Reversed switch; apply() works out which to use.

OpenCASCADE's draft (FreeCAD's Draft) only tilts planes and round faces about the pull
direction; every other wall (the side of an extruded spline or ellipse...) is drafted by
SciForge's draft_walls.py, in _scratch(), and its step is always a DraftFeature.

FreeCAD's Draft is silent about some failures (a face it cannot tilt is just skipped,
with a message in the Report view only), so check() refuses such faces first and
undrafted() finds any face the result left untouched.
"""
import json
import math

NATIVE = "PartDesign::Draft"
OWN_TYPE = "PartDesign::FeaturePython"
KIND = "Draft"  # SciForgeType of SciForge's own draft (DraftFeature)
PLANE_TYPES = ("App::Plane", "PartDesign::Plane")
META = "SciForgeDraft"
PARALLEL = 1.0 - 1e-6


class DraftError(ValueError):
    """The draft cannot be made; the message says why and what to try."""


def default_options():
    return {
        "angle": 1.0,
        "flip": False,
        "tangent": True,
        "draft_type": "fixed",  # Fusion's Type: "fixed" (Fixed Plane) or "parting" (Parting Line)
        "sides": "one",  # Draft Sides: "one", "two" (Two Side) or "symmetric"
        "angle2": 1.0,  # the other side's angle (Two Side)
        "parting": [],  # Parting Line: the parting tool, [(object, element name)]
        "parting_mode": "fix",  # Fix Parting Line (Move Parting Line is not built)
    }


def is_draft(obj):
    return obj is not None and (getattr(obj, "TypeId", "") == NATIVE or is_own(obj))


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
    from . import draft_walls

    kind = face.Surface.__class__.__name__
    if kind == "Plane":
        u, v = face.Surface.parameter(face.CenterOfMass)
        normal = _unit(face.normalAt(u, v))
        if abs(normal.dot(pull)) >= PARALLEL:
            return "A face parallel to the fixed plane cannot be drafted."
        return ""
    if draft_walls.native_ok(face, pull) or draft_walls.is_wall(face, pull):
        return ""  # FreeCAD's Draft, or a side wall along the pull (draft_walls)
    return (
        "Only faces that run along the pull direction (side walls, flat, round or free-form) "
        "can be drafted; this %s face does not." % _KIND_WORDS.get(kind, "curved")
    )


_KIND_WORDS = {
    "Cylinder": "round",
    "Cone": "conical",
    "Sphere": "spherical",
    "Toroid": "torus",
    "BSplineSurface": "free-form",
    "BezierSurface": "free-form",
    "SurfaceOfExtrusion": "free-form",
    "SurfaceOfRevolution": "revolved",
}


def needs_engine(shape, plane_ref, names, options):
    """True when some face needs SciForge's draft_walls (FreeCAD's Draft cannot tilt it)."""
    from . import draft_walls

    if shape is None or plane_ref is None or not names:
        return False
    try:
        pull = pull_direction(plane_ref, bool(options.get("flip")))
        return bool(draft_walls.engine_names(shape, list(names), pull))
    except Exception:
        return False


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
    if options.get("sides", "one") == "two":
        angle2 = float(options.get("angle2", 0.0))
        if abs(angle2) < 1e-9:
            raise DraftError("Angle 2 must not be 0.")
        if abs(angle2) >= 89.9:
            raise DraftError("Angle 2 must be between -89.9 and 89.9 degrees.")
    if options.get("draft_type", "fixed") == "parting":
        if options.get("parting_mode", "fix") != "fix":
            raise DraftError("Move Parting Line is not available yet: use Fix Parting Line.")
        if not options.get("parting"):
            raise DraftError("Pick the parting tool: a plane, a flat face, edges or sketch curves.")
    pull = pull_direction(plane_ref, bool(options.get("flip")))
    for name in names:
        reason = why_not(shape, name, pull, plane_ref)
        if reason:
            raise DraftError("%s (%s)" % (reason, name))


def undrafted(base_shape, result_shape, names):
    """Faces of `names` the result left as they were (FreeCAD skips a face it cannot tilt
    and only says so in the Report view). Only the result's faces with the same box as a
    picked face are measured (comparing every face's area and centre took 0.5 s a preview
    on a part of 180 faces; the boxes are kept per shape: shape_checks.face_boxes)."""
    from . import shape_checks

    boxes = shape_checks.face_boxes(result_shape)
    left = []
    for name in names:
        try:
            face = base_shape.getElement(name)
        except Exception:
            continue
        box = face.BoundBox
        kind = face.Surface.__class__
        area = center = None
        for other, other_box in boxes:
            if not _same_box(box, other_box):
                continue
            if other.Surface.__class__ is not kind:
                continue
            if area is None:
                area, center = face.Area, face.CenterOfMass
            if (
                abs(other.Area - area) < 1e-7 * max(1.0, area)
                and (other.CenterOfMass - center).Length < 1e-6
            ):
                left.append(name)
                break
    return left


def _same_box(a, b, tol=1e-4):
    """Two bounding boxes alike (an unchanged face keeps its box; the tolerance allows for a
    box grown by a changed edge tolerance)."""
    return (
        abs(a.XMin - b.XMin) < tol
        and abs(a.XMax - b.XMax) < tol
        and abs(a.YMin - b.YMin) < tol
        and abs(a.YMax - b.YMax) < tol
        and abs(a.ZMin - b.ZMin) < tol
        and abs(a.ZMax - b.ZMax) < tol
    )


# -- the angle handle --------------------------------------------------------------------
def handle_frame(shape, plane_ref, names, options, point0=None):
    """Where the angle handle goes: (pivot point, turning axis, zero direction) in the
    body's coordinates, or None. The handle turns about the line where the first drafted
    face meets the fixed plane (turning toward axis x zero is a positive angle). `point0`: a
    point of the hinge when it is not the plane's (a Parting Line)."""
    if plane_ref is None or not names:
        return None
    try:
        if point0 is None:
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


def needs_own_feature(options, shape=None, plane_ref=None, names=None):
    """True when FreeCAD's Draft cannot make it: a Parting Line draft, Two Side / Symmetric
    (both split the faces at a line first), or a face only draft_walls can tilt (a free-form
    side wall; give the base shape, plane and faces to check that)."""
    if options.get("draft_type", "fixed") == "parting" or options.get("sides", "one") != "one":
        return True
    return needs_engine(shape, plane_ref, names, options)


def is_own(obj):
    return (
        obj is not None
        and getattr(obj, "TypeId", "") == OWN_TYPE
        and getattr(obj, "SciForgeType", "") == KIND
    )


def apply(feature, base, plane_ref, names, options, formula="", formula2=""):
    """Write the picks and options onto the Draft feature (FreeCAD's or SciForge's)."""
    names = list(names or [])
    if is_own(feature):
        _apply_own(feature, base, plane_ref, names, options, formula, formula2)
        return
    if needs_own_feature(options, base.Shape if base else None, plane_ref, names):
        raise DraftError("FreeCAD's draft cannot do this; use update() to switch.")
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
    _save_meta(feature, _meta(options, formula))


def _meta(options, formula="", formula2=""):
    return {
        "v": 2,
        "flip": bool(options.get("flip")),
        "tangent": bool(options.get("tangent", True)),
        "formula": formula or "",
        "formula2": formula2 or "",
        "draft_type": options.get("draft_type", "fixed"),
        "sides": options.get("sides", "one"),
        "parting_mode": options.get("parting_mode", "fix"),
    }


def make(body, base, plane_ref, names, options, name="Draft", formula="", formula2="", before=None):
    """A new Draft at the end of `body` (or just before `before`) on `base` (normally
    body.Tip). FreeCAD's Draft for Fixed Plane / One Side, SciForge's DraftFeature for the
    rest. Not recomputed."""
    if base is None or base.Shape.isNull() or not base.Shape.Solids:
        raise DraftError("Make a solid first (Create Sketch, then Extrude).")
    if needs_own_feature(options, base.Shape, plane_ref, names):
        if before is not None:
            feature = body.Document.addObject(OWN_TYPE, name)
            body.insertObject(feature, before, False)
        else:
            feature = body.newObject(OWN_TYPE, name)
        DraftFeature(feature)
        _attach_view_provider(feature)
    elif before is not None:
        feature = body.Document.addObject(NATIVE, name)
        body.insertObject(feature, before, False)
    else:
        feature = body.newObject(NATIVE, name)
    if before is None:
        body.Tip = feature  # newObject() does not always move the Tip (feature guide #5)
    apply(feature, base, plane_ref, names, options, formula, formula2)
    return feature


def update(feature, base, plane_ref, names, options, formula="", formula2=""):
    """Change a draft. Returns the feature: a new object when the change needs the other
    kind (FreeCAD's Draft <-> SciForge's DraftFeature); it takes the old one's place and
    label, later steps and the draft's followers in other bodies move over to it."""
    own = needs_own_feature(options, base.Shape if base else None, plane_ref, names)
    if own == is_own(feature):
        apply(feature, base, plane_ref, names, options, formula, formula2)
        return feature
    from . import modify_bodies, shelling

    body = owner_body(feature)
    if body is None:
        raise DraftError("The draft is not in a body.")
    doc = feature.Document
    was_tip = body.Tip is feature
    label = feature.Label
    new = make(
        body, base, plane_ref, names, options, formula=formula, formula2=formula2, before=feature
    )
    shelling._compute(new)  # its faces must exist to point the later steps at them
    shelling._repoint(feature, new)
    modify_bodies.move_followers(feature, new)
    try:
        body.removeObject(feature)
    except Exception:
        pass
    doc.removeObject(feature.Name)
    try:
        new.Label = label
    except Exception:
        pass
    if was_tip:
        body.Tip = new
    shelling.show_tip(body)
    return new


def read(feature):
    """(base, plane_ref, names, options, formula) of an existing Draft (FreeCAD's or
    SciForge's). options carry draft_type, sides, angle2, parting (refs) and formula2."""
    meta = load_meta(feature)
    from . import shelling

    if is_own(feature):
        return _read_own(feature, meta)
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
    options["angle2"] = feature.Angle.Value
    flip = bool(meta.get("flip", False))
    if plane_ref is not None and "flip" not in meta:
        # A draft made elsewhere: find the flip that gives its Reversed.
        try:
            flip = reversed_flag(plane_ref, False) != bool(feature.Reversed)
        except DraftError:
            flip = False
    options["flip"] = flip
    options["tangent"] = bool(meta.get("tangent", True))
    formula = shelling.formula_of(feature, "Angle")
    options["formula2"] = ""
    return base, plane_ref, names, options, formula


def remove(feature):
    from . import modify_bodies, shelling

    modify_bodies.remove_all(feature)
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


# -- SciForge's own draft: Two Side, Symmetric, Parting Line ------------------------------------
# Fusion splits the faces at the fixed plane or the parting line and drafts each side on its
# own. FreeCAD's Draft cannot split a face, and has one pull direction and one plane per
# step. SciForge's DraftFeature splits the picked faces first (OpenCASCADE's general fuse,
# like Split Face), then tilts each group of pieces with FreeCAD's own Draft (the same
# OpenCASCADE draft) run in a hidden scratch document: the pieces on the pull side toward
# the pull direction, the others toward the opposite one, each about the line where it
# meets the plane or the parting line.
def parting_label(refs):
    if not refs:
        return ""
    if len(refs) == 1:
        obj, sub = refs[0]
        return plane_label(refs[0]) if sub else obj.Label
    return "%d objects" % len(refs)


def is_parting_object(obj, sub):
    """What the Parting Tool box takes: a plane, a flat face, an edge, a sketch or one of its
    curves."""
    if obj is None:
        return False
    if not sub:
        return is_plane_object(obj) or obj.TypeId == "Sketcher::SketchObject"
    return sub.startswith(("Face", "Edge"))


def _to_body(obj, target, point=None, vector=None, shape=None):
    """A point / vector / shape of `obj`'s body coordinates in `target`'s body coordinates."""
    from . import modify_bodies

    if target is None or obj is None:
        return point if point is not None else vector if vector is not None else shape
    if point is not None:
        return modify_bodies.point_between(point, obj, target)
    if vector is not None:
        return modify_bodies.vector_between(vector, obj, target)
    return modify_bodies.shape_between(shape, obj, target)


def _parting_geometry(refs, target):
    """("plane", point, normal) for a plane or a flat face, ("curves", compound, [sweep
    directions]) for edges and sketch curves, in `target`'s body coordinates."""
    import FreeCAD as App
    import Part

    if not refs:
        raise DraftError("Pick the parting tool: a plane, a flat face, edges or sketch curves.")
    if len(refs) == 1:
        obj, sub = refs[0]
        if (not sub and is_plane_object(obj)) or sub.startswith("Face"):
            point, axis, _out = plane_frame(refs[0])
            return (
                "plane",
                _to_body(obj, target, point=point),
                _to_body(obj, target, vector=axis),
            )
    edges, sweeps = [], []
    for obj, sub in refs:
        if obj.TypeId == "Sketcher::SketchObject":
            normal = obj.Placement.Rotation.multVec(App.Vector(0, 0, 1))
            found = [obj.Shape.getElement(sub)] if sub.startswith("Edge") else list(obj.Shape.Edges)
            edges += [_to_body(obj, target, shape=e) for e in found if not e.isNull()]
            sweep = _to_body(obj, target, vector=normal)
            if not any(abs(abs(sweep.dot(s)) - 1.0) < 1e-9 for s in sweeps):
                sweeps.append(sweep)
        elif sub.startswith("Edge"):
            try:
                edges.append(_to_body(obj, target, shape=obj.Shape.getElement(sub)))
            except Exception:
                raise DraftError("The parting edge %s no longer exists. Pick it again." % sub)
        elif sub.startswith("Face") or is_plane_object(obj):
            raise DraftError("Pick one plane or flat face as the parting tool, or curves.")
    if not edges:
        raise DraftError("The parting tool has no curves.")
    return "curves", Part.makeCompound(edges), sweeps


def build_spec(plane_ref, options, target=None):
    """What draft_shape() needs, in `target`'s body coordinates (target None: the plane's
    own body): the pull direction, the fixed plane or the parting tool, sides, angles."""
    flip = bool(options.get("flip"))
    obj = plane_ref[0]
    pull = _unit(_to_body(obj, target, vector=pull_direction(plane_ref, flip)))
    spec = {
        "type": options.get("draft_type", "fixed"),
        "pull": pull,
        "sides": options.get("sides", "one"),
        "angle": float(options.get("angle", 1.0)),
        "angle2": float(options.get("angle2", options.get("angle", 1.0))),
        "plane": None,
        "curves": None,
        "sweeps": [],
    }
    if spec["type"] == "fixed":
        point, axis, _out = plane_frame(plane_ref)
        spec["plane"] = (_to_body(obj, target, point=point), _to_body(obj, target, vector=axis))
        return spec
    geometry = _parting_geometry(list(options.get("parting") or []), target)
    if geometry[0] == "plane":
        spec["plane"] = (geometry[1], geometry[2])
    else:
        spec["curves"], spec["sweeps"] = geometry[1], geometry[2]
    return spec


def spec_of(lead, follower=None):
    """The spec of a draft step (its own or FreeCAD's), in `follower`'s body coordinates
    (a follower in another body reads its lead's options this way)."""
    _base, plane_ref, _names, options, _formula = read(lead)
    if plane_ref is None:
        raise DraftError("The draft has no pull direction.")
    return build_spec(plane_ref, options, follower)


def _check_spec(spec):
    for key in ("angle", "angle2"):
        angle = float(spec.get(key, 0.0))
        if key == "angle2" and spec["sides"] != "two":
            continue
        if abs(angle) < 1e-9:
            raise DraftError("The draft angle must not be 0.")
        if abs(angle) >= 89.9:
            raise DraftError("The draft angle must be between -89.9 and 89.9 degrees.")


def _inner_point(face):
    """A point well inside a face (on its surface), to find it again after other faces
    changed."""
    import FreeCAD as App

    u0, u1, v0, v1 = face.ParameterRange
    for fu, fv in ((0.5, 0.5), (0.37, 0.41), (0.61, 0.57), (0.27, 0.71), (0.73, 0.29)):
        point = face.valueAt(u0 + (u1 - u0) * fu, v0 + (v1 - v0) * fv)
        if face.isInside(point, 1e-7, False):
            return point
    try:
        points, triangles = face.tessellate(0.1)
        best = None
        for a, b, c in triangles:
            pa, pb, pc = App.Vector(points[a]), App.Vector(points[b]), App.Vector(points[c])
            area = (pb - pa).cross(pc - pa).Length
            if best is None or area > best[0]:
                best = (area, (pa + pb + pc) * (1.0 / 3.0))
        if best is not None:
            surface = face.Surface
            return surface.value(*surface.parameter(best[1]))
    except Exception:
        pass
    return face.CenterOfMass


def _big_plane(point, normal, around):
    import Part

    size = max(around.BoundBox.DiagonalLength, 1.0) * 4.0 + 50.0
    plane = Part.Plane(point, normal)
    u, v = plane.parameter(around.BoundBox.Center)
    return plane.toShape(u - size, u + size, v - size, v + size)


def _swept_curves(curves, sweeps, around):
    import Part

    size = max(around.BoundBox.DiagonalLength, 1.0) * 4.0 + 50.0
    sheets = []
    for edge in curves.Edges:
        for sweep in sweeps:
            moved = edge.copy()
            moved.translate(sweep * -size)
            sheets.append(moved.extrude(sweep * (2.0 * size)))
    return Part.makeCompound(sheets)


def _split(shape, faces, spec):
    """`shape` with the picked faces divided where they cross the plane / parting tool."""
    import Part

    if spec["plane"] is not None:
        tool = _big_plane(spec["plane"][0], spec["plane"][1], shape)
    elif spec["curves"] is not None and spec["sweeps"]:
        tool = _swept_curves(spec["curves"], spec["sweeps"], shape)
    else:
        return shape  # edges of the part: they already bound the faces
    edges = []
    for face in faces:
        try:
            edges += [e for e in face.section(tool).Edges if e.Length > 1e-6]
        except Exception as exc:
            raise DraftError("The faces cannot be split at the parting line: %s" % exc)
    if not edges:
        return shape
    try:
        result, _map = shape.generalFuse([Part.makeCompound(edges)])
    except Exception as exc:
        raise DraftError("The faces cannot be split at the parting line: %s" % exc)
    solids = [s for s in result.Solids if s.Volume > 1e-9]
    if len(solids) != len(shape.Solids) or not solids:
        raise DraftError("Splitting the faces at the parting line broke the part.")
    return solids[0] if len(solids) == 1 else Part.makeCompound(solids)


def _pieces(split_shape, faces):
    """The faces of `split_shape` that are (pieces of) the picked faces."""
    import Part

    found = []
    for piece in split_shape.Faces:
        point = _inner_point(piece)
        probe = Part.Vertex(point)
        for face in faces:
            if type(face.Surface) is not type(piece.Surface):
                continue
            try:
                if face.distToShape(probe)[0] < 1e-6:
                    found.append(piece)
                    break
            except Exception:
                continue
    return found


def _hinge(piece, spec, pull, point):
    """(side, (hinge point, hinge normal)) of a piece: "above" on the pull side of the plane
    or parting line, else "below"; the hinge plane the piece turns about."""
    import Part

    if spec["plane"] is not None:
        origin, normal = spec["plane"]
        normal = _unit(normal)
        across = normal.dot(pull)
        if abs(across) < 1e-6:
            raise DraftError(
                "The parting plane runs along the pull direction: pick a plane across it."
            )
        toward = normal if across > 0 else -normal
        side = "above" if (point - origin).dot(toward) > 0 else "below"
        return side, (origin, normal)
    curves = spec["curves"]
    dist, pairs, _info = curves.distToShape(Part.Vertex(point))
    nearest = pairs[0][0]
    side = "above" if (point - nearest).dot(pull) >= 0 else "below"
    best = None
    for edge in piece.Edges:
        try:
            mid = edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2.0)
            if curves.distToShape(Part.Vertex(mid))[0] > 1e-5:
                continue
        except Exception:
            continue
        if best is None or edge.Length > best.Length:
            best = edge
    if best is None:
        return side, (nearest, pull)
    mid = best.valueAt((best.FirstParameter + best.LastParameter) / 2.0)
    if best.Curve.TypeId in ("Part::GeomLine", "Part::GeomLineSegment"):
        d = _unit(best.valueAt(best.LastParameter) - best.valueAt(best.FirstParameter))
        across = pull - d * pull.dot(d)
        if across.Length < 1e-6:
            raise DraftError(
                "The parting line runs along the pull direction there: a face cannot turn "
                "about it. Pick another parting line or pull direction."
            )
        return side, (mid, _unit(across))
    try:
        plane = Part.Wire([best]).findPlane()
    except Exception:
        plane = None
    if plane is None:
        raise DraftError("The parting line is not flat where it meets %s." % "a face")
    import FreeCAD as App

    return side, (mid, _unit(App.Vector(plane.Axis)))


def draft_shape(shape, names, spec):
    """`shape` (body coordinates) with faces `names` drafted as `spec` says (build_spec).
    Raises DraftError with the reason.

    The last few results (and refusals) are kept per shape, faces and spec: the limit search
    builds an angle (value_limits) and the preview then builds the same one in the document
    (a DraftFeature's execute) - once is enough. The result is shared: callers do not change
    it (DraftFeature refines a copy)."""
    _check_spec(spec)
    key = _result_key(shape, names, spec)
    if key is not None:
        for k, kept, result in _RESULTS:
            if k == key and kept.isSame(shape):
                if isinstance(result, DraftError):
                    raise DraftError(str(result))
                return result
    try:
        result = _draft_shape(shape, names, spec)
    except DraftError as exc:
        _remember(key, shape, DraftError(str(exc)))
        raise
    _remember(key, shape, result)
    return result


_RESULTS = []  # [(key, base shape, result or DraftError)], newest last
_KEEP_RESULTS = 8


def _remember(key, shape, result):
    if key is None:
        return
    _RESULTS.append((key, shape, result))
    del _RESULTS[:-_KEEP_RESULTS]


def _result_key(shape, names, spec):
    """What a draft_shape() result depends on, as a hashable key (None: do not keep it)."""
    try:

        def vec(v):
            return (round(v.x, 9), round(v.y, 9), round(v.z, 9))

        plane = spec.get("plane")
        curves = spec.get("curves")
        curve_key = None
        if curves is not None:
            curve_key = tuple(
                (
                    e.Curve.__class__.__name__,
                    round(e.Length, 9),
                    vec(e.valueAt(e.FirstParameter)),
                    vec(e.valueAt(e.LastParameter)),
                    vec(e.valueAt(0.5 * (e.FirstParameter + e.LastParameter))),
                )
                for e in curves.Edges
            )
        return (
            shape_key(shape),
            tuple(names),
            spec.get("type"),
            spec.get("sides"),
            round(float(spec.get("angle", 0.0)), 9),
            round(float(spec.get("angle2", 0.0)), 9),
            vec(spec["pull"]),
            None if plane is None else (vec(plane[0]), vec(plane[1])),
            curve_key,
            tuple(vec(v) for v in spec.get("sweeps") or []),
        )
    except Exception:
        return None


def _draft_shape(shape, names, spec):
    import Part

    faces = []
    for name in names:
        try:
            faces.append(shape.getElement(name))
        except Exception:
            raise DraftError(
                "The face %s no longer exists. Edit the draft and pick it again." % name
            )
    if not faces:
        raise DraftError("Pick the faces to draft.")
    pull = _unit(spec["pull"])
    for name in names:
        reason = why_not(shape, name, pull)
        if reason:
            raise DraftError("%s (%s)" % (reason, name))
    sides = spec["sides"]
    if spec["type"] == "fixed" and sides == "one":
        point = [_inner_point(f) for f in faces]
        return _scratch(shape, point, spec["plane"], pull, spec["angle"])
    split = _split(shape, faces, spec)
    groups = []
    for piece in _pieces(split, faces):
        point = _inner_point(piece)
        side, hinge = _hinge(piece, spec, pull, point)
        if side == "above":
            direction, angle = pull, spec["angle"]
        elif sides == "one":
            continue  # One Side: only the pull side of the parting line is drafted
        else:
            direction = -pull
            angle = spec["angle2"] if sides == "two" else spec["angle"]
        key = (side, _plane_key(hinge))
        for group in groups:
            if group["key"] == key:
                group["points"].append(point)
                break
        else:
            groups.append(
                {"key": key, "hinge": hinge, "pull": direction, "angle": angle, "points": [point]}
            )
    if not groups:
        raise DraftError(
            "None of the faces lies on the pull side of the parting line. Flip the pull "
            "direction or pick other faces."
        )
    result = split
    for group in groups:
        result = _scratch(result, group["points"], group["hinge"], group["pull"], group["angle"])
    if not isinstance(result, Part.Shape) or result.isNull() or not result.Solids:
        raise DraftError("The draft leaves no solid.")
    return result


def _plane_key(hinge):
    point, normal = hinge
    n = _unit(normal)
    if n.x < -1e-9 or (abs(n.x) < 1e-9 and (n.y < -1e-9 or (abs(n.y) < 1e-9 and n.z < 0))):
        n = -n
    return (round(n.x, 6), round(n.y, 6), round(n.z, 6), round(n.dot(point), 5))


def _faces_at(shape, points):
    names = []
    for point in points:
        found = _face_at(shape, point)
        if found not in names:
            names.append(found)
    return names


def _face_at(shape, point):
    """The name of the face of `shape` that `point` lies on. A live preview asks this for
    every picked face on every rebuild: the faces whose box holds the point are tried by
    projecting it onto their surface (fast), the slow distance search only if that fails."""
    import Part

    key = (shape_key(shape), round(point.x, 9), round(point.y, 9), round(point.z, 9))
    if key in _FACE_AT:
        return _FACE_AT[key][0]
    found = None
    faces = shape.Faces
    for i, face in enumerate(faces, start=1):
        box = face.BoundBox
        box.enlarge(1e-5)
        if not box.isInside(point):
            continue
        try:
            u, v = face.Surface.parameter(point)
            if (face.Surface.value(u, v) - point).Length < 1e-6 and face.isPartOfDomain(u, v):
                found = "Face%d" % i
                break
        except Exception:
            continue
    if found is None:
        probe = Part.Vertex(point)
        for i, face in enumerate(faces, start=1):
            try:
                if face.distToShape(probe)[0] < 1e-6:
                    found = "Face%d" % i
                    break
            except Exception:
                continue
    if found is None:
        raise DraftError("A face to draft was lost while drafting the faces next to it.")
    if len(_FACE_AT) > 256:
        _FACE_AT.clear()
    _FACE_AT[key] = (found, shape)  # the shape is kept: its key cannot be reused meanwhile
    return found


_FACE_AT = {}


def shape_key(shape):
    """Tells shapes apart between rebuilds of a live preview: the same shape (the step before
    a draft, unchanged while only the angle is dragged) gives the same key. Whoever caches
    by it keeps a face of the shape, so the shape (and its key) cannot be reused meanwhile."""
    return (shape.hashCode(), shape.ShapeType)  # (counting its faces costs ~0.5 ms a call)


def _scratch(shape, points, hinge, pull, angle):
    """The faces at `points` of `shape` tilted by `angle` toward `pull` about the hinge plane
    (point, normal): FreeCAD's own Draft for the faces OpenCASCADE can tilt (planes, round
    faces about the pull direction), SciForge's draft_walls for the other walls (free-form
    sides, and the walls joined to them, so a tangent chain stays tangent)."""
    from . import draft_walls

    at = [_face_at(shape, p) for p in points]
    names = []
    for name in at:
        if name not in names:
            names.append(name)
    own = draft_walls.engine_names(shape, names, _unit(pull))
    if not own:
        return _occ_draft(shape, names, hinge, pull, angle)
    own_points = [p for p, name in zip(points, at) if name in own]
    native_points = [p for p, name in zip(points, at) if name not in own]
    if native_points:
        shape = _occ_draft(shape, _faces_at(shape, native_points), hinge, pull, angle)
    return draft_walls.draft(shape, _faces_at(shape, own_points), hinge, pull, angle)


def _occ_draft(shape, names, hinge, pull, angle):
    """FreeCAD's own Draft run on `shape` in a hidden throw-away document."""
    import FreeCAD as App

    doc = _scratch_document()
    try:
        holder = doc.addObject("Part::Feature", "Solid")
        _unseen(holder)
        holder.Shape = shape
        body = doc.addObject("PartDesign::Body", "Body")
        _unseen(body)
        base = body.newObject("PartDesign::FeatureBase", "Base")
        _unseen(base)
        base.BaseFeature = holder
        origin, normal = hinge
        plane = body.newObject("PartDesign::Plane", "Hinge")
        plane.MapMode = "Deactivated"
        plane.Placement = App.Placement(origin, App.Rotation(App.Vector(0, 0, 1), _unit(normal)))
        line = body.newObject("PartDesign::Line", "Pull")
        line.MapMode = "Deactivated"
        line.Placement = App.Placement(origin, App.Rotation(App.Vector(0, 0, 1), _unit(pull)))
        draft = body.newObject("PartDesign::Draft", "Draft")
        _unseen(draft)
        draft.Base = (base, names)
        draft.NeutralPlane = (plane, [""])
        draft.PullDirection = (line, [""])
        draft.Angle = float(angle)
        draft.Reversed = False
        draft.Refine = False
        for obj in (base, plane, line, draft):
            obj.recompute()
        state = list(draft.State)
        out = draft.Shape  # a shape of its own: it outlives the scratch objects (no copy)
        status = draft.getStatusString() if ("Invalid" in state or "Error" in state) else ""
    finally:
        _release_scratch(doc)
    if status or out.isNull() or not out.Solids or not out.isValid():
        raise DraftError(friendly(status))
    if abs(out.Volume - _volume(shape)) < 1e-9:
        raise DraftError(
            "The faces could not be tilted with this plane and angle. Try another angle or "
            "pick other faces."
        )
    return out


def _unseen(obj):
    """A scratch object is never drawn: in the GUI its view provider would tessellate every
    shape it gets (the part, again and again during a limit search)."""
    try:
        view = getattr(obj, "ViewObject", None)
        if view is not None:
            view.Visibility = False
        obj.Visibility = False
    except Exception:
        pass


_VOLUMES = []  # [(shape key, shape, volume)], newest last


def _volume(shape):
    """shape.Volume, kept for the last few shapes (the part before the draft: every trial of
    a limit search compares with it)."""
    key = shape_key(shape)
    for k, kept, volume in _VOLUMES:
        if k == key and kept.isSame(shape):
            return volume
    volume = shape.Volume
    _VOLUMES.append((key, shape, volume))
    del _VOLUMES[:-4]
    return volume


# The throw-away document is kept and reused. In the GUI, closing a document ends the undo
# step that is open (FreeCAD 1.1): a Draft preview inside a dialog cut the dialog's undo step
# in two, the rest of the preview went unrecorded and Ctrl+Z after OK left the drafted shape
# behind. It is closed later, when no undo step is open, nothing is selected and no dialog
# is open (closing a document also clears FreeCAD's selection).
_SCRATCH = {"name": None, "waiting": False}


def _scratch_document():
    import FreeCAD as App

    name = _SCRATCH["name"]
    if name and name in App.listDocuments():
        return App.getDocument(name)
    active = App.ActiveDocument.Name if App.ActiveDocument is not None else None
    doc = App.newDocument("SciForgeScratch", "scratch", True, True)
    try:
        doc.UndoMode = 0
    except Exception:
        pass
    _SCRATCH["name"] = doc.Name
    _restore_active(active)
    return doc


def _release_scratch(doc):
    """Empty the throw-away document; close it now without a GUI, later with one."""
    import FreeCAD as App

    for _attempt in range(3):
        names = [o.Name for o in doc.Objects]
        if not names:
            break
        for name in reversed(names):
            try:
                if doc.getObject(name) is not None:
                    doc.removeObject(name)
            except Exception:
                pass
    if not App.GuiUp:
        _close_scratch()
        return
    if not _SCRATCH["waiting"]:
        _SCRATCH["waiting"] = True
        _close_later()


def _close_later(delay=1500):
    try:
        from PySide import QtCore

        QtCore.QTimer.singleShot(delay, _try_close)
    except Exception:
        _SCRATCH["waiting"] = False


def _try_close():
    import FreeCAD as App

    try:
        busy = App.getActiveTransaction() is not None or any(
            getattr(d, "Recomputing", False) for d in App.listDocuments().values()
        )
        if not busy:
            import FreeCADGui as Gui

            busy = bool(Gui.Control.activeDialog()) or bool(Gui.Selection.getCompleteSelection())
        if busy:
            _close_later(3000)
            return
        _SCRATCH["waiting"] = False
        _close_scratch()
    except Exception:
        _SCRATCH["waiting"] = False


def _close_scratch():
    import FreeCAD as App

    name = _SCRATCH["name"]
    _SCRATCH["name"] = None
    if not name or name not in App.listDocuments():
        return
    active = App.ActiveDocument.Name if App.ActiveDocument is not None else None
    try:
        App.closeDocument(name)
    except Exception:
        pass
    _restore_active(active)


def _restore_active(name):
    import FreeCAD as App

    if not name or name not in App.listDocuments():
        return
    try:
        if App.ActiveDocument is None or App.ActiveDocument.Name != name:
            App.setActiveDocument(name)
    except Exception:
        pass


class DraftFeature:
    """SciForge's Draft (Two Side, Symmetric, Parting Line). Saved documents store
    "sciforge.drafting.DraftFeature": keep the name and the properties."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc, group="Draft"):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, group, doc)
                return True
            return False

        add("App::PropertyLinkSub", "Faces", "The faces drafted")
        if add("App::PropertyEnumeration", "DraftType", "Fixed Plane or Parting Line"):
            obj.DraftType = list(TYPE_LABELS.values())
        add(
            "App::PropertyLinkSubGlobal",
            "Plane",
            "Fixed Plane: the plane; Parting Line: the pull direction (a plane or flat face)",
        )
        add("App::PropertyLinkSubListGlobal", "PartingTool", "The parting line or plane")
        if add("App::PropertyEnumeration", "Sides", "Which sides are drafted"):
            obj.Sides = list(SIDE_LABELS.values())
        if add("App::PropertyAngle", "Angle", "Draft angle (the pull side)"):
            obj.Angle = 1.0
        if add("App::PropertyAngle", "Angle2", "Draft angle of the other side (Two Side)"):
            obj.Angle2 = 1.0
        add("App::PropertyBool", "Flip", "Pull the other way")
        if add("App::PropertyBool", "Refine", "Merge faces that end up in one plane, like Fusion"):
            obj.Refine = True
        if "SciForgeType" not in obj.PropertiesList:
            obj.addProperty("App::PropertyString", "SciForgeType", "Base", "", 4)  # hidden
            obj.SciForgeType = KIND

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        from . import bodies

        base = obj.BaseFeature
        if base is None or base.Shape.isNull() or not base.Shape.Solids:
            raise DraftError("Draft needs a solid before it in the timeline.")
        try:
            link = obj.Faces
            names = [s.lstrip("?") for s in (link[1] if link else []) if s]
            _base, plane_ref, _names, options, _f = _read_own(obj, load_meta(obj))
            if plane_ref is None:
                raise DraftError("Pick the pull direction (a plane or a flat face).")
            spec = build_spec(plane_ref, options, obj)
            # not a copy: the same shape between rebuilds lets draft_walls reuse its work
            result = draft_shape(base.Shape, names, spec)
            if obj.Refine:
                try:
                    result = result.removeSplitter()
                except Exception:
                    pass
        except DraftError:
            bodies.pass_through(obj)
            raise
        except Exception as exc:
            bodies.pass_through(obj)
            raise DraftError(friendly(str(exc)))
        obj.Shape = result

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


TYPE_LABELS = {"fixed": "Fixed Plane", "parting": "Parting Line"}
SIDE_LABELS = {"one": "One Side", "two": "Two Side", "symmetric": "Symmetric"}


def _attach_view_provider(obj):
    try:
        import FreeCAD as App

        if not App.GuiUp or obj.ViewObject is None:
            return
        from .draft_ui import ViewProviderDraft

        ViewProviderDraft(obj.ViewObject)
    except Exception:
        pass


def _link_ref(link):
    if not link or link[0] is None:
        return None
    subs = [s for s in (link[1] or []) if s]
    return (link[0], subs[0] if subs else "")


def _apply_own(feature, base, plane_ref, names, options, formula, formula2):
    from . import shelling

    old = feature.Faces
    if not (old and old[0] is base and [s for s in old[1] if s] == names):
        feature.Faces = (base, names)
    if feature.BaseFeature is not base:
        feature.BaseFeature = base
    obj, sub = plane_ref
    current = _link_ref(feature.Plane)
    if current is None or current[0] is not obj or current[1] != sub:
        feature.Plane = (obj, [sub] if sub else [""])
    refs = list(options.get("parting") or [])
    wanted = (
        [(o, [s] if s else [""]) for o, s in refs] if options.get("draft_type") == "parting" else []
    )
    have = [(o, list(s)) for o, s in (feature.PartingTool or [])]
    if [(o.Name, s) for o, s in have] != [(o.Name, s) for o, s in wanted]:
        feature.PartingTool = wanted
    _set(feature, "DraftType", TYPE_LABELS[options.get("draft_type", "fixed")])
    _set(feature, "Sides", SIDE_LABELS[options.get("sides", "one")])
    _set(feature, "Flip", bool(options.get("flip")))
    shelling._set_formula(feature, "Angle", formula or "")
    shelling._set_formula(feature, "Angle2", formula2 or "")
    _set(feature, "Angle", float(options.get("angle", 1.0)))
    _set(feature, "Angle2", float(options.get("angle2", options.get("angle", 1.0))))
    if not feature.Refine:
        feature.Refine = True
    _save_meta(feature, _meta(options, formula, formula2))


def _read_own(feature, meta):
    from . import shelling

    link = feature.Faces
    base = feature.BaseFeature or (link[0] if link else None)
    names = [s.lstrip("?") for s in (link[1] if link else []) if s]
    plane_ref = _link_ref(feature.Plane)
    labels = {v: k for k, v in TYPE_LABELS.items()}
    sides = {v: k for k, v in SIDE_LABELS.items()}
    options = default_options()
    options.update(
        {
            "angle": feature.Angle.Value,
            "angle2": feature.Angle2.Value,
            "flip": bool(feature.Flip),
            "tangent": bool(meta.get("tangent", True)),
            "draft_type": labels.get(feature.DraftType, "fixed"),
            "sides": sides.get(feature.Sides, "one"),
            "parting": [
                (o, (list(s) or [""])[0]) for o, s in (feature.PartingTool or []) if o is not None
            ],
            "parting_mode": meta.get("parting_mode", "fix"),
            "formula2": shelling.formula_of(feature, "Angle2"),
        }
    )
    return base, plane_ref, names, options, shelling.formula_of(feature, "Angle")
