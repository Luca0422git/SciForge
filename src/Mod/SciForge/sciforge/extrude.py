# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Extrude on top of PartDesign. No GUI code: the Extrude command and the
golden-model builder both call this module, so they behave the same.

Profiles (what is extruded), a list of (object, sub-element):
  (sketch, "InternalFace2")   one closed region of a sketch, like a Fusion profile. A
                              circle inside a rectangle gives two regions (the ring and
                              the disc); crossing curves split regions too. FreeCAD makes
                              them when the sketch's MakeInternals is on (ensure_regions).
  (sketch, "")                the whole sketch (holes stay holes), as FreeCAD does
  (feature, "Face6")          a flat face of a body

Options (dict, see DEFAULTS):
  operation    join | cut | intersect | new_body
  start        profile | offset | object      (+ start_offset mm / start_object ref)
  direction    one_side | two_sides | symmetric
  extent       distance | to_object | all     (side 1; extent2 for side 2)
  distance     mm along the profile normal; negative goes the other way (one side, two
               sides). Symmetric: each side's length ("half") or the total ("whole"),
               see measurement.
  extent_object  (object, sub) where "to_object" ends: a face, a plane or a body
  taper        degrees, positive widens (Fusion: outward)
  distance2 / extent2 / extent_object2 / taper2   the second side (two_sides)
  flip         extent "all": go against the profile normal
  expressions  {"distance" | "distance2" | "taper" | "taper2": "width * 2"}: values typed as
               a formula of parameters (Fusion's fields take "width", "width*2"); they
               become expressions on the feature, so it follows the parameters

What is built:
  join / cut     a PartDesign Pad / Pocket in the body the profile belongs to
  new_body       a new PartDesign Body holding a Pad (the first solid of an empty body is
                 simply a Pad there: that already is a new body)
  intersect      SciForge's ExtrudeFeature: the body keeps what lies inside the extrusion
A hidden PartDesign SubShapeBinder carries the profile into the feature when FreeCAD
cannot link it directly: a start offset, profiles from several sketches, or a profile
in another body. Fusion-only choices (start, measurement, operation, original picks)
are stored as JSON in the feature's hidden "SciForgeExtrude" property, so editing the
extrude from the timeline offers them again.
"""
import json
import math

import FreeCAD as App

OPERATIONS = ("join", "cut", "intersect", "new_body")
DIRECTIONS = ("one_side", "two_sides", "symmetric")
EXTENTS = ("distance", "to_object", "all")
STARTS = ("profile", "offset", "object")
MEASUREMENTS = ("half", "whole")

DEFAULTS = {
    "operation": "join",
    "start": "profile",
    "start_offset": 0.0,
    "start_object": None,
    "direction": "one_side",
    "extent": "distance",
    "distance": 10.0,
    "extent_object": None,
    "taper": 0.0,
    "extent2": "distance",
    "distance2": 10.0,
    "extent_object2": None,
    "taper2": 0.0,
    "measurement": "whole",
    "flip": False,
}

META = "SciForgeExtrude"
ROLE = "SciForgeRole"
INTERSECT_TYPE = "PartDesign::FeaturePython"
PLANE_TYPES = ("App::Plane", "PartDesign::Plane")
Z = App.Vector(0, 0, 1)
TOL = 1e-7


class ExtrudeError(ValueError):
    """The extrude cannot be built as asked; the message says why and what to do."""


class NeedsPick(ExtrudeError):
    """A selection box (To Object, Start: Object) waits for its click: not a mistake, the
    dialog shows it as a hint and keeps the last preview, like Fusion."""


# -- profiles -------------------------------------------------------------------------
def is_sketch(obj):
    return obj is not None and obj.isDerivedFrom("Sketcher::SketchObject")


def ensure_regions(sketch):
    """Turn on the sketch's regions (FreeCAD's MakeInternals): every closed area becomes
    an "InternalFaceN" that a Pad can use as its profile."""
    from . import preview

    if not sketch.MakeInternals:
        sketch.MakeInternals = True
        with preview.quiet():  # a sketch FreeCAD cannot make areas from just has none
            sketch.recompute()
    elif sketch.InternalShape.isNull() and not sketch.Shape.isNull():
        with preview.quiet():
            sketch.recompute()


def regions(sketch):
    """[(sub-element, face in global coordinates)] for every closed region of a sketch."""
    ensure_regions(sketch)
    placement = sketch.getGlobalPlacement()
    found = []
    for i, face in enumerate(sketch.InternalShape.Faces, start=1):
        face = face.copy()
        face.Placement = placement.multiply(face.Placement)
        found.append(("InternalFace%d" % i, face))
    return found


def normalize(profile):
    """Profiles in the list form [(obj, sub), ...] from the forms callers use."""
    if profile is None:
        return []
    items = profile if isinstance(profile, list) else [profile]
    found, seen = [], set()
    for item in items:
        if isinstance(item, tuple):
            obj, subs = item[0], item[1] if len(item) > 1 else ""
            subs = [subs] if isinstance(subs, str) else (list(subs) or [""])
        else:
            obj, subs = item, [""]
        for sub in subs:
            key = (obj.Name, sub)
            if key not in seen:
                seen.add(key)
                found.append((obj, sub))
    return found


def key(profile):
    return (profile[0].Name, profile[1])


def owner_body(obj):
    if obj is None:
        return None
    if obj.TypeId == "PartDesign::Body":
        return obj
    parent = obj.getParentGeoFeatureGroup()
    while parent is not None and parent.TypeId != "PartDesign::Body":
        parent = parent.getParentGeoFeatureGroup()
    return parent


def _whole_sketch_faces(sketch):
    import Part

    wires = [w for w in sketch.Shape.Wires if w.isClosed()]
    if not wires:
        return []
    return list(Part.makeFace(wires, "Part::FaceMakerBullseye").Faces)


def local_faces(obj, sub):
    """Faces of one profile in its body's coordinates."""
    if is_sketch(obj):
        if sub.startswith("Internal"):
            ensure_regions(obj)
        if not sub:
            return _whole_sketch_faces(obj)
    shape = obj.getSubObject(sub) if sub else obj.Shape
    if shape is None or shape.isNull():
        return []
    return list(shape.Faces)


def _to_global(shape, obj):
    body = owner_body(obj)
    if body is None or (obj is body):
        return shape
    shape = shape.copy()
    shape.Placement = body.getGlobalPlacement().multiply(shape.Placement)
    return shape


def global_faces(profiles):
    found = []
    for obj, sub in normalize(profiles):
        found += [_to_global(face, obj) for face in local_faces(obj, sub)]
    return found


def face_normal(face):
    """Outward normal at the middle of a face (normalAt already handles Reversed faces)."""
    u0, u1, v0, v1 = face.ParameterRange
    return face.normalAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)


def interior_point(face):
    """A point inside the face (a ring's centre of mass is in its hole)."""
    center = face.CenterOfMass
    try:
        if face.isInside(center, 1e-6, True):
            return center
        u0, u1, v0, v1 = face.ParameterRange
        n = 20
        points, inside = {}, set()
        for i in range(n + 1):
            for j in range(n + 1):
                p = face.valueAt(u0 + (u1 - u0) * i / float(n), v0 + (v1 - v0) * j / float(n))
                points[(i, j)] = p
                if face.isInside(p, 1e-6, True):
                    inside.add((i, j))
        # Prefer a sample whose neighbours are inside too: clear of the edges.
        deep = [
            k
            for k in inside
            if all((k[0] + a, k[1] + b) in inside for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        ]
        for pool in (deep, list(inside)):
            if pool:
                # the one nearest the middle (a ring: next to the hole)
                return min((points[k] for k in pool), key=lambda p: (p - center).Length)
    except Exception:
        pass
    return center


def profile_normal(profiles, local=False):
    """The Fusion extrude direction for distance > 0: the sketch's normal, or the outward
    normal of a picked body face. Global unless local=True (body coordinates)."""
    profiles = normalize(profiles)
    if not profiles:
        raise ExtrudeError("Select a profile first.")
    obj, sub = profiles[0]
    if is_sketch(obj):
        placement = obj.Placement if local else obj.getGlobalPlacement()
        return placement.Rotation.multVec(Z)
    faces = local_faces(obj, sub)
    if not faces:
        raise ExtrudeError("The picked face no longer exists. Pick the profile again.")
    normal = face_normal(faces[0])
    if not local:
        body = owner_body(obj)
        if body is not None and body is not obj:
            normal = body.getGlobalPlacement().Rotation.multVec(normal)
    return normal


def profile_frame(profiles):
    """(a point inside the first profile, its normal), global: where the arrow goes."""
    faces = global_faces(profiles)
    if not faces:
        raise ExtrudeError("The profile has no closed area to extrude.")
    return interior_point(faces[0]), profile_normal(profiles)


def check_profiles(profiles):
    """Raise ExtrudeError unless the profiles can be extruded together."""
    profiles = normalize(profiles)
    if not profiles:
        raise ExtrudeError("Select a profile: click inside a sketch area or on a flat face.")
    normal = profile_normal(profiles)
    for obj, sub in profiles:
        faces = local_faces(obj, sub)
        if not faces:
            raise ExtrudeError(
                "%s has no closed area to extrude. Close the sketch's outline." % obj.Label
            )
        for face in faces:
            if face.Surface.TypeId != "Part::GeomPlane":
                raise ExtrudeError("Only flat faces can be extruded. Pick a flat face or a sketch.")
            n = _to_global(face, obj)
            if abs(abs(face_normal(n).dot(normal)) - 1.0) > 1e-6:
                raise ExtrudeError(
                    "All profiles must lie in parallel planes. Extrude the others separately."
                )
    return profiles


def expand_whole(profiles):
    """Profiles with every "whole sketch" entry replaced by the sketch areas it covers
    (holes stay out), so a dialog can show and toggle them one by one."""
    found = []
    for obj, sub in normalize(profiles):
        if not (is_sketch(obj) and sub == ""):
            found.append((obj, sub))
            continue
        try:
            whole = [_to_global(f, obj) for f in _whole_sketch_faces(obj)]
            for name, face in regions(obj):
                point = interior_point(face)
                if any(w.isInside(point, 1e-6, True) for w in whole):
                    found.append((obj, name))
        except Exception:
            found.append((obj, sub))
    return normalize(found)


def profile_label(profiles):
    profiles = normalize(profiles)
    if not profiles:
        return "Nothing selected"
    if len(profiles) == 1:
        obj, sub = profiles[0]
        if is_sketch(obj):
            return "%s (whole sketch)" % obj.Label if not sub else "1 profile of %s" % obj.Label
        return "1 face of %s" % obj.Label
    names = sorted({obj.Label for obj, _ in profiles})
    return "%d profiles (%s)" % (len(profiles), ", ".join(names))


# -- options ----------------------------------------------------------------------------
def options_with_defaults(options):
    merged = dict(DEFAULTS)
    merged.update({k: v for k, v in (options or {}).items() if v is not None or k in merged})
    if merged["operation"] not in OPERATIONS:
        raise ExtrudeError("unknown operation %r" % merged["operation"])
    if merged["direction"] not in DIRECTIONS:
        raise ExtrudeError("unknown direction %r" % merged["direction"])
    for name in ("extent", "extent2"):
        if merged[name] == "through_all":
            merged[name] = "all"
        if merged[name] not in EXTENTS:
            raise ExtrudeError("unknown extent %r" % merged[name])
    if merged["start"] not in STARTS:
        raise ExtrudeError("unknown start %r" % merged["start"])
    if merged["measurement"] not in MEASUREMENTS:
        raise ExtrudeError("unknown measurement %r" % merged["measurement"])
    return merged


def taper_possible(options, extent):
    """True if a taper can be built with this extent. Always: what PartDesign's Pad and
    Pocket cannot taper (up to an object, a join through All) SciForge's own extrude
    feature builds (see own_feature_needed)."""
    return True


def native_taper(operation, extent):
    """True if PartDesign tapers this extent itself: Distance, and a cut's All (ThroughAll).
    FreeCAD's Pad and Pocket silently ignore a taper up to a face, and a Pad's UpToLast."""
    return extent == "distance" or (extent == "all" and operation == "cut")


def own_feature_needed(options):
    """True when the extrude is SciForge's own feature instead of a Pad/Pocket: Intersect,
    and tapers PartDesign cannot build (Fusion tapers every extent)."""
    if options["operation"] == "intersect":
        return True
    sides = [("extent", "taper")]
    if options["direction"] == "two_sides":
        sides.append(("extent2", "taper2"))
    for extent, taper in sides:
        if abs(float(options[taper])) > 1e-9 and not native_taper(
            options["operation"], options[extent]
        ):
            return True
    return False


def check_options(options):
    """Raise ExtrudeError for values Fusion's dialog would reject."""
    sides = [("extent", "distance", "extent_object", "taper", "")]
    if options["direction"] == "two_sides":
        sides.append(("extent2", "distance2", "extent_object2", "taper2", " (side two)"))
    for extent, distance, target, taper, where in sides:
        if options[extent] == "distance" and abs(float(options[distance])) < 1e-6:
            raise ExtrudeError("The distance%s must not be zero." % where)
        if options[extent] == "to_object" and options.get(target) is None:
            raise NeedsPick("Click the face, plane or body to extrude to%s." % where)
        if abs(float(options[taper])) >= 89.9:
            raise ExtrudeError("The taper angle%s must be between -89.9 and 89.9 degrees." % where)
    if options["direction"] == "symmetric" and options["extent"] == "to_object":
        raise ExtrudeError("Symmetric extrudes go a distance or through all.")
    if options["start"] == "object" and options.get("start_object") is None:
        raise NeedsPick("Click the face or plane the extrusion starts from.")


def feature_type(operation, options=None):
    """FreeCAD type of the feature an operation (with these options) builds."""
    if operation == "intersect" or (options is not None and own_feature_needed(options)):
        return INTERSECT_TYPE
    if operation == "cut":
        return "PartDesign::Pocket"
    return "PartDesign::Pad"


# The operation of SciForge's own extrude feature (its "Operation" property).
OWN_OPERATIONS = {"intersect": "Intersect", "join": "Join", "new_body": "Join", "cut": "Cut"}


def _ref_shape(ref):
    obj, sub = ref
    if sub:
        return obj.getSubObject(sub)
    return obj.Shape


def _ref_global(ref):
    obj, sub = ref
    shape = obj.getSubObject(sub) if sub else obj.Shape
    if obj.TypeId in PLANE_TYPES:
        shape = obj.Shape.copy()
        shape.Placement = obj.getGlobalPlacement()
        return shape
    return _to_global(shape, obj)


def _plane_of_ref(ref):
    """(point, normal) of a flat face or plane reference (global), or None."""
    shape = _ref_global(ref)
    if shape is None or shape.isNull():
        return None
    faces = shape.Faces
    if len(faces) != 1 or faces[0].Surface.TypeId != "Part::GeomPlane":
        return None
    return faces[0].CenterOfMass, face_normal(faces[0])


def start_offset_of(profiles, options):
    """Signed start offset along the profile normal (mm)."""
    if options["start"] == "offset":
        return float(options["start_offset"])
    if options["start"] == "object":
        if not options.get("start_object"):
            raise NeedsPick("Click the face or plane the extrusion starts from.")
        plane = _plane_of_ref(options["start_object"])
        if plane is None:
            raise ExtrudeError("Start from a flat face or a plane.")
        point, normal = plane
        n = profile_normal(profiles)
        if abs(abs(normal.dot(n)) - 1.0) > 1e-6:
            raise ExtrudeError(
                "The start face must be parallel to the profile. Pick a parallel face or plane."
            )
        origin = interior_point(global_faces(profiles)[0])
        return (point - origin).dot(n)
    return 0.0


def side_of(ref, profiles, options):
    """+1 if the object lies along the profile normal, else -1 (To Object picks the side)."""
    shape = _ref_global(ref)
    origin = interior_point(global_faces(profiles)[0])
    origin = origin + profile_normal(profiles) * start_offset_of(profiles, options)
    n = profile_normal(profiles)
    if shape is None or shape.isNull():
        return 1.0
    if shape.Faces and len(shape.Faces) == 1:
        target = shape.Faces[0].CenterOfMass
    else:
        target = shape.BoundBox.Center
    if shape.Faces and len(shape.Faces) == 1 and shape.Faces[0].Surface.TypeId == "Part::GeomPlane":
        plane = shape.Faces[0]
        normal = face_normal(plane)
        denom = n.dot(normal)
        if abs(denom) > 1e-9:  # where the profile normal line meets the plane
            t = (plane.CenterOfMass - origin).dot(normal) / denom
            return 1.0 if t >= 0 else -1.0
    return 1.0 if (target - origin).dot(n) >= 0 else -1.0


def _sign1(profiles, options):
    if options["direction"] == "symmetric":
        return 1.0
    if options["extent"] == "to_object":
        return side_of(options["extent_object"], profiles, options)
    sign = 1.0 if float(options["distance"]) >= 0 else -1.0
    if options["extent"] == "all" and options.get("flip"):
        sign = -sign  # "All" keeps the side the distance was on; Flip turns it round
    return sign


# -- meta --------------------------------------------------------------------------------
def _ref_json(ref):
    if not ref:
        return None
    return [ref[0].Name, ref[1]]


def _ref_load(doc, data):
    if not data:
        return None
    obj = doc.getObject(data[0])
    return (obj, data[1]) if obj is not None else None


def load_meta(feature):
    try:
        text = getattr(feature, META, "")
        return json.loads(text) if text else {}
    except Exception:
        return {}


def _save_meta(feature, meta):
    if META not in feature.PropertiesList:
        feature.addProperty("App::PropertyString", META, "SciForge", "Fusion extrude options", 0)
        feature.setEditorMode(META, 2)  # hidden
    text = json.dumps(meta, sort_keys=True)
    if getattr(feature, META) != text:
        setattr(feature, META, text)


def _mark(obj, role):
    if ROLE not in obj.PropertiesList:
        obj.addProperty("App::PropertyString", ROLE, "SciForge", "What SciForge made this for", 0)
        obj.setEditorMode(ROLE, 2)
    setattr(obj, ROLE, role)


def is_helper(obj):
    return getattr(obj, ROLE, "") in ("ExtrudeProfile", "ExtrudeRef")


# -- the intersect feature -----------------------------------------------------------------
def _set_enum(obj, prop, items):
    """(Re)set an enumeration's choices, keeping its value (older files lack new ones)."""
    try:
        current = getattr(obj, prop)
    except Exception:
        current = None
    try:
        if list(obj.getEnumerationsOfProperty(prop) or []) == list(items):
            return
    except Exception:
        pass
    setattr(obj, prop, list(items))
    if current in items:
        setattr(obj, prop, current)


class ExtrudeFeature:
    """SciForge's own extrude: Intersect (the body keeps what lies inside the extrusion),
    and Join/Cut with a taper PartDesign cannot build (up to an object, a join through
    All). Saved documents store "sciforge.extrude.ExtrudeFeature": keep the name stable;
    files from before "Operation" existed are Intersect extrudes."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc, group="Extrude"):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, group, doc)
                return True
            return False

        add("App::PropertyLinkSubList", "Profiles", "The profiles that are extruded")
        if add("App::PropertyEnumeration", "Operation", "Intersect, join or cut"):
            obj.Operation = ["Intersect", "Join", "Cut"]
        if add("App::PropertyEnumeration", "SideType", "One side, two sides or symmetric"):
            obj.SideType = ["One side", "Two sides", "Symmetric"]
        for suffix in ("", "2"):
            add("App::PropertyEnumeration", "Type" + suffix, "How far the side goes")
            _set_enum(obj, "Type" + suffix, ["Length", "ThroughAll", "UpToFace", "UpToLast"])
            add("App::PropertyLength", "Length" + suffix, "Distance")
            add("App::PropertyAngle", "TaperAngle" + suffix, "Taper angle (+ widens)")
            add("App::PropertyLinkSub", "UpToFace" + suffix, "Face or plane where the side ends")
        add("App::PropertyBool", "Reversed", "Go against the profile's normal")
        add("App::PropertyDistance", "StartOffset", "Start this far from the profile plane")
        if add("App::PropertyBool", "Refine", "Merge coplanar faces, like Fusion"):
            obj.Refine = True
        if "SciForgeType" not in obj.PropertiesList:
            obj.addProperty("App::PropertyString", "SciForgeType", "Base", "", 4)
            obj.SciForgeType = "Extrude"

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        from . import extrude_prism as prism

        base = obj.BaseFeature
        has_base = base is not None and not base.Shape.isNull() and bool(base.Shape.Solids)
        operation = getattr(obj, "Operation", "Intersect")
        if not has_base and operation != "Join":
            raise ExtrudeError(
                "%s needs a solid before it in the timeline."
                % ("Cut" if operation == "Cut" else "Intersect")
            )
        faces = []
        for linked, subs in obj.Profiles:
            for sub in subs or [""]:
                faces += local_faces(linked, sub)
        if not faces:
            raise ExtrudeError("Select a profile to extrude.")
        profiles = [(linked, (subs or [""])[0]) for linked, subs in obj.Profiles]
        normal = _profile_normal_in_body(profiles, obj)

        def target(link):
            if not link or link[0] is None:
                return None
            linked, subs = link[0], link[1]
            return _ref_shape((linked, subs[0] if subs else ""))

        spec = {
            "side_type": obj.SideType,
            "reversed": obj.Reversed,
            "start_offset": obj.StartOffset.Value,
            "type": obj.Type,
            "length": obj.Length.Value,
            "taper": obj.TaperAngle.Value,
            "target": target(obj.UpToFace),
            "type2": obj.Type2,
            "length2": obj.Length2.Value,
            "taper2": obj.TaperAngle2.Value,
            "target2": target(obj.UpToFace2),
        }
        try:
            tool = prism.build(faces, normal, spec, reach=[base.Shape] if has_base else [])
            if operation == "Intersect":
                result = base.Shape.common(tool)
            elif operation == "Cut":
                result = base.Shape.cut(tool)
            else:
                result = base.Shape.fuse(tool) if has_base else tool
            if obj.Refine:
                result = result.removeSplitter()
        except prism.PrismError as exc:
            raise ExtrudeError(str(exc))
        if result.isNull() or not result.Solids or result.Volume < TOL:
            if operation == "Cut":
                raise ExtrudeError("This cut would remove the whole body.")
            raise ExtrudeError(
                "The extrusion does not overlap the body, so Intersect would leave nothing."
            )
        if len(result.Solids) > 1:
            raise ExtrudeError(
                "%s would leave %d separate pieces; a body holds one solid. "
                "Change the profile or the distance." % (operation, len(result.Solids))
            )
        if operation == "Cut" and abs(result.Volume - base.Shape.Volume) < 1e-9:
            raise ExtrudeError("The cut does not touch the body. Flip it or pick another object.")
        obj.Shape = result.Solids[0] if len(result.Solids) == 1 else result

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def _profile_normal_in_body(profiles, feature):
    """Profile normal in the coordinates of the feature's body."""
    obj = profiles[0][0]
    if is_helper(obj) or owner_body(obj) is not owner_body(feature):
        normal = _helper_normal(obj, feature)
        if normal is not None:
            return normal
    return profile_normal(profiles, local=True)


def _helper_normal(binder, feature):
    """For a binder-carried profile: the original profile's normal, stored in the meta."""
    meta = load_meta(feature)
    vec = meta.get("normal")
    if vec:
        return App.Vector(*vec)
    return None


def is_intersect(obj):
    return getattr(obj, "SciForgeType", "") == "Extrude" and obj.TypeId == INTERSECT_TYPE


def is_extrude(obj):
    return obj is not None and (
        obj.TypeId in ("PartDesign::Pad", "PartDesign::Pocket") or is_intersect(obj)
    )


def _attach_view_provider(obj):
    if not App.GuiUp:
        return
    try:
        from .extrude_ui import ViewProviderExtrude

        ViewProviderExtrude(obj.ViewObject)
    except Exception:
        pass


# -- building ---------------------------------------------------------------------------------
def _has_solid(body, before=None):
    """True if `body` already has a solid where the new feature goes."""
    tip = before.BaseFeature if before is not None else body.Tip
    return tip is not None and not tip.Shape.isNull() and bool(tip.Shape.Solids)


def _links_to(obj, target, skip=("BaseFeature",)):
    for prop in obj.PropertiesList:
        if prop in skip:
            continue
        try:
            kind = obj.getTypeIdOfProperty(prop)
        except Exception:
            continue
        if "Link" not in kind or "Hidden" in kind:
            continue
        try:
            value = getattr(obj, prop)
        except Exception:
            continue
        if _contains(value, target):
            return True
    return False


def _contains(value, target):
    if value is target:
        return True
    if isinstance(value, (list, tuple)):
        return any(_contains(v, target) for v in value)
    return False


def dependents(feature):
    """Later features that use this extrude's own faces/edges (not just its result)."""
    found = []
    for obj in feature.InList:
        if obj.TypeId in ("PartDesign::Body", "App::Part") or is_helper(obj):
            continue
        if _links_to(obj, feature):
            found.append(obj)
    return found


def _source_body(profiles):
    body = owner_body(profiles[0][0])
    if body is None:
        raise ExtrudeError("The profile must belong to a body. Use Create Sketch first.")
    return body


def _needs_binder(target_body, profiles, options):
    if options["start"] != "profile":
        return True
    if len({obj.Name for obj, _ in profiles}) != 1:
        return True
    obj = profiles[0][0]
    return owner_body(obj) is not target_body


def _direct_profile(profiles):
    obj = profiles[0][0]
    subs = [sub for _, sub in profiles]
    if "" in subs:
        return obj  # the whole sketch
    return (obj, subs)


def _insert(body, type_id, name, before=None):
    """New feature in `body`: at the timeline marker, or just before `before`."""
    doc = body.Document
    if before is not None:
        obj = doc.addObject(type_id, name)
        body.insertObject(obj, before, False)
        return obj
    obj = body.newObject(type_id, name)
    return obj


def _binder(body, feature, sources, offset, existing=None, role="ExtrudeProfile"):
    """A hidden SubShapeBinder in `body`, just before `feature`, copying `sources`."""
    doc = body.Document
    binder = existing
    if binder is None:
        binder = doc.addObject("PartDesign::SubShapeBinder", "ExtrudeProfile")
        body.insertObject(binder, feature, False)
        _mark(binder, role)
        binder.Label = "%s profile" % feature.Label
    grouped = {}
    order = []
    for obj, sub in sources:
        if obj.Name not in grouped:
            grouped[obj.Name] = (obj, [])
            order.append(obj.Name)
        if sub:
            grouped[obj.Name][1].append(sub)
    binder.Support = [(grouped[n][0], tuple(grouped[n][1])) for n in order]
    shift = App.Vector(offset)
    rot = body.getGlobalPlacement().Rotation
    binder.Placement = App.Placement(rot.inverted().multVec(shift), App.Rotation())
    try:
        binder.Visibility = False
    except Exception:
        pass
    if App.GuiUp:
        try:
            binder.ViewObject.Visibility = False
            if "ShowInTree" in binder.ViewObject.PropertiesList:
                binder.ViewObject.ShowInTree = False
        except Exception:
            pass
    return binder


def _local_ref(body, feature, ref, helpers, old_refs):
    """A reference FreeCAD may link from `feature` (same body); otherwise a hidden binder
    (re-used from the last update when there is one)."""
    obj, sub = ref
    if obj.TypeId in PLANE_TYPES and owner_body(obj) is body:
        return (obj, "")
    if owner_body(obj) is body:
        if obj is body:
            raise ExtrudeError("Pick a face of the body, a plane, or another body to extrude to.")
        return (obj, sub)
    existing = old_refs.pop(0) if old_refs else None
    binder = _binder(body, feature, [ref], App.Vector(), existing=existing, role="ExtrudeRef")
    binder.Label = "%s target" % feature.Label
    helpers.append(binder)
    return (binder, "Face1" if sub.startswith("Face") else "")


def _native_normal(feature):
    """The direction FreeCAD's Pad/Pocket extrudes before 'Reversed' (body coordinates)."""
    import Part

    obj, subs = feature.Profile[0], list(feature.Profile[1]) if feature.Profile else []
    if obj.isDerivedFrom("Part::Part2DObject"):
        normal = obj.Placement.Rotation.multVec(Z)
    else:
        shapes = [obj.getSubObject(s) if s else obj.Shape for s in (subs or [""])]
        shapes = [s for s in shapes if s is not None and not s.isNull()]
        compound = shapes[0] if len(shapes) == 1 else Part.Compound(shapes)
        plane = compound.findPlane()
        if plane is not None:
            normal = App.Vector(plane.Axis)
        else:
            normal = face_normal(compound.Faces[0])
    if feature.TypeId == "PartDesign::Pocket":
        normal = normal * -1.0
    return normal


def _side_props(feature, suffix, extent, length, taper, ref, cut):
    setattr(feature, "TaperAngle" + suffix, float(taper))
    if extent == "distance":
        setattr(feature, "Type" + suffix, "Length")
        setattr(feature, "Length" + suffix, max(abs(float(length)), 1e-6))
    elif extent == "all":
        setattr(feature, "Type" + suffix, "ThroughAll" if cut else "UpToLast")
    else:
        obj, sub = ref
        is_shape = not sub and obj.TypeId not in PLANE_TYPES
        if is_shape and "UpToShape" + suffix in feature.PropertiesList:
            setattr(feature, "Type" + suffix, "UpToShape")
            setattr(feature, "UpToShape" + suffix, [(obj, [])])
        else:
            setattr(feature, "Type" + suffix, "UpToFace")
            setattr(feature, "UpToFace" + suffix, (obj, [sub] if sub else [""]))


def _apply(feature, body, profiles, options, refs):
    """Write the options onto the feature (its Profile/Profiles is already set)."""
    want = profile_normal(profiles, local=False)
    want = body.getGlobalPlacement().Rotation.inverted().multVec(want)
    sign = _sign1(profiles, options)
    direction = options["direction"]
    distance = float(options["distance"])
    if direction == "symmetric":
        length = abs(distance) if options["measurement"] == "whole" else 2.0 * abs(distance)
    else:
        length = abs(distance)
    side_type = {"one_side": "One side", "two_sides": "Two sides", "symmetric": "Symmetric"}[
        direction
    ]
    if is_intersect(feature):
        feature.Operation = OWN_OPERATIONS[options["operation"]]
        feature.SideType = side_type
        feature.Reversed = sign < 0
        feature.StartOffset = 0.0  # a start offset travels with the profile's binder
        _fp_side(feature, "", options["extent"], length, options["taper"], refs.get(1))
        if direction == "two_sides":
            _fp_side(
                feature,
                "2",
                options["extent2"],
                options["distance2"],
                options["taper2"],
                refs.get(2),
            )
        feature.Refine = True
        return
    cut = feature.TypeId == "PartDesign::Pocket"
    feature.SideType = side_type
    _side_props(feature, "", options["extent"], length, options["taper"], refs.get(1), cut)
    if direction == "two_sides":
        _side_props(
            feature,
            "2",
            options["extent2"],
            options["distance2"],
            options["taper2"],
            refs.get(2),
            cut,
        )
    native = _native_normal(feature)
    feature.Reversed = (want * sign).dot(native) < 0
    if hasattr(feature, "Refine"):
        feature.Refine = True
    if hasattr(feature, "AllowMultiFace"):
        feature.AllowMultiFace = True


def _fp_side(feature, suffix, extent, length, taper, ref):
    setattr(feature, "TaperAngle" + suffix, float(taper))
    setattr(feature, "Length" + suffix, max(abs(float(length)), 1e-6))
    if extent == "distance":
        setattr(feature, "Type" + suffix, "Length")
    elif extent == "all":
        # A join goes as far as the part reaches (Pad's UpToLast); a cut through it all.
        join = getattr(feature, "Operation", "Intersect") == "Join"
        setattr(feature, "Type" + suffix, "UpToLast" if join else "ThroughAll")
    else:
        obj, sub = ref
        if not sub and obj.TypeId not in PLANE_TYPES:
            what = "A taper" if feature.Operation != "Intersect" else "Intersect"
            raise ExtrudeError(
                "%s can go up to a flat face or a plane, not a whole body. Pick a face of it."
                % what
            )
        setattr(feature, "Type" + suffix, "UpToFace")
        setattr(feature, "UpToFace" + suffix, (obj, [sub] if sub else [""]))


# Dialog value -> the feature property that holds it (Pad, Pocket and SciForge's own).
EXPRESSION_PROPS = {
    "distance": "Length",
    "distance2": "Length2",
    "taper": "TaperAngle",
    "taper2": "TaperAngle2",
}


def _expression_used(key, options):
    two = options["direction"] == "two_sides"
    if key == "distance":
        return options["extent"] == "distance"
    if key == "distance2":
        return two and options["extent2"] == "distance"
    if key == "taper2":
        return two
    return True


def _wrap(key, expr, options):
    """The property's expression for a dialog value's formula: a negative distance is a
    reversed extrude of the positive length, a symmetric half length is half of it."""
    if key != "distance":
        return expr
    if options["direction"] == "symmetric":
        return "2 * (%s)" % expr if options["measurement"] == "half" else expr
    return "-(%s)" % expr if float(options["distance"]) < 0 else expr


def _unwrap(key, expr, options):
    for head in ("2 * (", "-("):
        if key == "distance" and expr.startswith(head) and expr.endswith(")"):
            return expr[len(head) : -1]
    return expr


def _apply_expressions(feature, options):
    """Formulas typed in the dialog become expressions on the feature's properties; a value
    typed as a plain number (or dragged) removes the formula again."""
    from . import parameters, parameters_core

    typed = options.get("expressions") or {}
    names = parameters.user_names(feature.Document)
    engine = dict(feature.ExpressionEngine)
    for key, prop in EXPRESSION_PROPS.items():
        if prop not in feature.PropertiesList:
            continue
        text = (typed.get(key) or "").strip()
        if text and _expression_used(key, options):
            expr = _wrap(key, parameters_core.to_freecad(text, names), options)
            if engine.get(prop) != expr:
                feature.setExpression(prop, expr)
        elif prop in engine:
            feature.setExpression(prop, None)


def evaluate(doc, text):
    """Value of a formula typed in a field ("width * 2", "=width+5 mm"): a float in mm (or
    degrees for an angle). Raises ExtrudeError with the reason when it is no value."""
    from . import parameters, parameters_core

    text = (text or "").strip().lstrip("=").strip()
    expr = parameters_core.to_freecad(text, parameters.user_names(doc))
    host = parameters.container(doc)
    if host is None:
        if not doc.Objects:
            raise ExtrudeError("%s is not a value." % text)
        host = doc.Objects[0]
    try:
        value = host.evalExpression(expr)
    except Exception as exc:
        raise ExtrudeError("'%s' is not a value here: %s" % (text, exc))
    try:
        return float(getattr(value, "Value", value))
    except Exception:
        raise ExtrudeError("'%s' is not a number." % text)


def _hide_sketches(profiles):
    if not App.GuiUp:
        return
    for obj, _ in profiles:
        if is_sketch(obj):
            try:
                obj.ViewObject.Visibility = False
            except Exception:
                pass


def _new_body(src_body):
    doc = src_body.Document
    body = doc.addObject("PartDesign::Body", "Body")
    container = src_body.getParentGeoFeatureGroup()
    if container is not None and hasattr(container, "addObject"):
        container.addObject(body)
    count = len([o for o in doc.Objects if o.TypeId == "PartDesign::Body"])
    body.Label = "Body%d" % count
    return body


def _structure(feature, profiles, options):
    """(target body or None for 'make a new one', feature type, needs binder)."""
    src = _source_body(profiles)
    meta = load_meta(feature) if feature is not None else {}
    created = None
    if feature is not None and meta.get("created_body"):
        created = feature.Document.getObject(meta["created_body"])
    op = options["operation"]
    if op == "new_body":
        if created is not None:
            target = created
        elif feature is not None and owner_body(feature) is src and not _has_solid(src, feature):
            target = src  # the first solid of a body is already a new body
        elif feature is None and not _has_solid(src):
            target = src
        else:
            target = None  # a new body
    else:
        target = src
    return target, feature_type(op, options), src


def build(profiles, options, name="Extrude", feature=None):
    """Create the extrude, or rebuild `feature` with new profiles/options.
    Returns the feature (a different object when its kind had to change)."""
    profiles = check_profiles(profiles)
    options = options_with_defaults(options)
    check_options(options)
    target, type_id, src = _structure(feature, profiles, options)
    if feature is not None:
        same_type = feature.TypeId == type_id and (
            type_id != INTERSECT_TYPE or is_intersect(feature)
        )
        if owner_body(feature) is target and same_type:
            _update(feature, target, profiles, options)
            return feature
        blocking = dependents(feature)
        if blocking:
            raise ExtrudeError(
                "%s is used by %s, and this change needs a new kind of extrude (another "
                "operation or body, or a taper FreeCAD's extrude cannot make), so it cannot be "
                "made here. Make a new extrude instead."
                % (feature.Label, ", ".join(o.Label for o in blocking))
            )
    old_meta = load_meta(feature) if feature is not None else {}
    created = None
    if target is None:
        target = created = _new_body(src)
    elif old_meta.get("created_body") == target.Name:
        created = target  # still the body this extrude made
    before = feature if (feature is not None and owner_body(feature) is target) else None
    was_tip = before is not None and target.Tip is before
    new = _insert(target, type_id, name, before)
    if type_id == INTERSECT_TYPE:
        ExtrudeFeature(new)
        _attach_view_provider(new)
    _save_meta(new, {"created_body": created.Name if created is not None else None})
    try:
        _update(new, target, profiles, options)
    except Exception:
        # Nothing half-made stays behind; the old feature is still there, untouched.
        _remove(new, keep_body=created is None or (feature is not None and before is not None))
        raise
    if feature is not None:
        label = feature.Label
        _remove(feature, keep_body=owner_body(feature) is target)
        new.Label = label
    if before is None or was_tip:
        target.Tip = new
        show_tip(target)
    return new


def _update(feature, body, profiles, options):
    meta = load_meta(feature)
    doc = feature.Document
    old_helpers = [doc.getObject(n) for n in meta.get("helpers", [])]
    old_helpers = [h for h in old_helpers if h is not None]
    old_profile = [h for h in old_helpers if getattr(h, ROLE, "") == "ExtrudeProfile"]
    old_refs = [h for h in old_helpers if getattr(h, ROLE, "") == "ExtrudeRef"]
    helpers = []
    normal = profile_normal(profiles)
    if _needs_binder(body, profiles, options):
        offset = start_offset_of(profiles, options)
        existing = old_profile[0] if old_profile else None
        binder = _binder(body, feature, profiles, normal * offset, existing=existing)
        helpers.append(binder)
        link = binder
        fp_profiles = [(binder, "")]
    else:
        link = _direct_profile(profiles)
        fp_profiles = list(profiles)
    if is_intersect(feature):
        feature.Profiles = [(obj, [sub]) for obj, sub in fp_profiles]  # "" = whole object
    else:
        feature.Profile = link
    refs = {}
    for side, opt, ext in ((1, "extent_object", "extent"), (2, "extent_object2", "extent2")):
        if side == 2 and options["direction"] != "two_sides":
            continue
        if options[ext] == "to_object" and options.get(opt) is not None:
            refs[side] = _local_ref(body, feature, options[opt], helpers, old_refs)
    # Helpers that are no longer needed go (a profile binder after "start: profile", ...).
    keep = {h.Name for h in helpers}
    for helper in old_helpers:
        if helper.Name not in keep:
            _delete(helper)
    meta["normal"] = list(body.getGlobalPlacement().Rotation.inverted().multVec(normal))
    _save_meta(feature, meta)  # the intersect feature reads the normal when it computes
    _apply(feature, body, profiles, options, refs)
    _apply_expressions(feature, options)
    meta.update(
        {
            "v": 1,
            "operation": options["operation"],
            "start": options["start"],
            "start_offset": float(options["start_offset"]),
            "start_object": _ref_json(options.get("start_object")),
            "measurement": options["measurement"],
            "flip": bool(options.get("flip")),
            "profiles": [[obj.Name, sub] for obj, sub in profiles],
            "extent_object": _ref_json(options.get("extent_object")),
            "extent_object2": _ref_json(options.get("extent_object2")),
            "helpers": [h.Name for h in helpers],
            "normal": list(body.getGlobalPlacement().Rotation.inverted().multVec(normal)),
        }
    )
    _save_meta(feature, meta)
    _hide_sketches(profiles)


def _delete(obj):
    doc = obj.Document
    body = owner_body(obj)
    try:
        if body is not None and body is not obj:
            body.removeObject(obj)
    except Exception:
        pass
    try:
        doc.removeObject(obj.Name)
    except Exception:
        pass


def show_tip(body):
    """FreeCAD draws a body through its Tip feature, and a new feature hides the one before
    it. A feature removed by code (FreeCAD's own Delete does this itself) left the new Tip
    hidden: the whole part vanished from the view although it was still there."""
    tip = body.Tip if body is not None else None
    if tip is None:
        return
    try:
        if App.GuiUp and tip.ViewObject is not None:
            tip.ViewObject.Visibility = True
        else:
            tip.Visibility = True
    except Exception:
        pass


def _remove(feature, keep_body=True):
    """Delete an extrude with its helpers (and the body it created, when asked)."""
    meta = load_meta(feature)
    doc = feature.Document
    body = owner_body(feature)
    was_tip = body is not None and body.Tip is feature
    helpers = [doc.getObject(n) for n in meta.get("helpers", [])]
    _delete(feature)
    for helper in helpers:
        if helper is not None:
            _delete(helper)
    if not keep_body and body is not None and meta.get("created_body") == body.Name:
        rest = [o for o in body.Group if o.TypeId != "App::Origin"]
        if not rest:
            body.removeObjectsFromDocument()
            doc.removeObject(body.Name)
            return
    if was_tip:
        show_tip(body)


def remove(feature):
    _remove(feature, keep_body=False)


def make(body, profile, options, name="Extrude"):
    """New extrude with Fusion-style options. `profile`: a sketch (whole sketch),
    (feature, "FaceN"), (sketch, "InternalFaceN") or a list of those. `body` is used
    when the profile does not say (kept for callers of the first version)."""
    profiles = normalize(profile)
    if not profiles:
        raise ExtrudeError("Select a profile first.")
    feature = build(profiles, options, name)
    return feature


def update(feature, profile, options):
    return build(normalize(profile), options, feature=feature)


# -- reading back ------------------------------------------------------------------------
def profiles_of(feature):
    """The profiles of an existing extrude, as picked (binders resolved)."""
    meta = load_meta(feature)
    doc = feature.Document
    if meta.get("profiles"):
        found = []
        for name, sub in meta["profiles"]:
            obj = doc.getObject(name)
            if obj is not None:
                found.append((obj, sub))
        if found:
            return found
    if is_intersect(feature):
        return [(obj, (subs or [""])[0]) for obj, subs in feature.Profiles]
    value = feature.Profile
    obj = value[0] if isinstance(value, tuple) else value
    subs = [s for s in (list(value[1]) if isinstance(value, tuple) and len(value) > 1 else [])]
    subs = [s for s in subs if s]
    if obj is None:
        return []
    if getattr(obj, ROLE, "") == "ExtrudeProfile":
        found = []
        for linked, linked_subs in obj.Support:
            for sub in linked_subs or [""]:
                found.append((linked, sub))
        return found
    if not subs:
        return [(obj, "")]
    return [(obj, s) for s in subs]


def profile_of(feature):
    """First-version name: the profile in make()'s form."""
    profiles = profiles_of(feature)
    if len(profiles) == 1:
        obj, sub = profiles[0]
        return obj if not sub else (obj, sub)
    return profiles


def read(feature):
    """(profiles, options) of an existing extrude, the way the dialog shows them."""
    meta = load_meta(feature)
    doc = feature.Document
    profiles = profiles_of(feature)
    options = dict(DEFAULTS)
    intersect = is_intersect(feature)
    own = getattr(feature, "Operation", "Intersect") if intersect else None
    cut = feature.TypeId == "PartDesign::Pocket" or own == "Cut"
    if intersect and own == "Intersect":
        operation = "intersect"
    elif cut:
        operation = "cut"
    else:
        operation = "new_body" if meta.get("operation") == "new_body" else "join"
    options["operation"] = operation
    for name in ("start", "measurement"):
        if meta.get(name) in (STARTS if name == "start" else MEASUREMENTS):
            options[name] = meta[name]
    options["start_offset"] = float(meta.get("start_offset", 0.0))
    options["start_object"] = _ref_load(doc, meta.get("start_object"))
    options["flip"] = bool(meta.get("flip", False))
    options["direction"] = {"Symmetric": "symmetric", "Two sides": "two_sides"}.get(
        feature.SideType, "one_side"
    )

    def extent_of(kind):
        if kind == "Length":
            return "distance"
        if kind in ("ThroughAll", "UpToLast"):
            return "all"
        if kind in ("UpToFace", "UpToShape"):
            return "to_object"
        return "distance"

    options["extent"] = extent_of(feature.Type)
    options["extent2"] = extent_of(feature.Type2)
    options["taper"] = feature.TaperAngle.Value
    options["taper2"] = feature.TaperAngle2.Value
    options["extent_object"] = _ref_load(doc, meta.get("extent_object")) or _link_ref(feature, "")
    options["extent_object2"] = _ref_load(doc, meta.get("extent_object2")) or _link_ref(
        feature, "2"
    )
    length = feature.Length.Value
    # Direction actually used, against the profile normal: the sign of the distance.
    sign = 1.0
    try:
        if intersect:
            sign = -1.0 if feature.Reversed else 1.0
        elif profiles:
            body = owner_body(feature)
            want = profile_normal(profiles)
            if body is not None:
                want = body.getGlobalPlacement().Rotation.inverted().multVec(want)
            native = _native_normal(feature)
            used = native * (-1.0 if feature.Reversed else 1.0)
            sign = 1.0 if used.dot(want) >= 0 else -1.0
    except Exception:
        pass
    if options["direction"] == "symmetric":
        options["distance"] = length if options["measurement"] == "whole" else length / 2.0
    else:
        options["distance"] = sign * length
    options["flip"] = False  # the sign of the distance already says which side
    options["distance2"] = feature.Length2.Value
    try:
        from . import parameters_core

        engine = dict(feature.ExpressionEngine)
        options["expressions"] = {
            key: _unwrap(key, parameters_core.from_freecad(engine[prop]), options)
            for key, prop in EXPRESSION_PROPS.items()
            if prop in engine
        }
    except Exception:
        options["expressions"] = {}
    return profiles, options


def _link_ref(feature, suffix):
    if ("UpToFace" + suffix) in feature.PropertiesList:
        kind = getattr(feature, "Type" + suffix, "")
        if kind == "UpToFace":
            link = getattr(feature, "UpToFace" + suffix)
            if link and link[0] is not None:
                sub = link[1][0] if link[1] else ""
                return (link[0], sub)
        if kind == "UpToShape":
            links = getattr(feature, "UpToShape" + suffix)
            if links:
                return (links[0][0], "")
    return None


# -- auto operation ----------------------------------------------------------------------
def goes_into_material(base_shape, profiles, distance, options=None):
    """True if extruding the profile by `distance` starts inside existing material, which
    is when Fusion switches the operation to Cut on its own. base_shape is in the body's
    coordinates (a feature's Shape)."""
    if base_shape is None or base_shape.isNull() or not base_shape.Solids:
        return False
    try:
        profiles = normalize(profiles)
        obj, sub = profiles[0]
        faces = local_faces(obj, sub)
        if not faces:
            return False
        point = interior_point(faces[0])
        normal = profile_normal(profiles, local=True)
        if options is not None and options.get("start") != "profile":
            point = point + normal * start_offset_of(profiles, options)
        step = 0.01 if distance >= 0 else -0.01
        return base_shape.isInside(point + normal * step, 1e-7, True)
    except Exception:
        return False


# -- first-version names (golden builder, tests) ----------------------------------------------
def apply(feature, options):
    """Rewrite the options of an existing extrude in place (first-version API)."""
    profiles = profiles_of(feature)
    return build(profiles, options, feature=feature)


def switch(body, feature, options):
    return build(profiles_of(feature), options, feature=feature)
