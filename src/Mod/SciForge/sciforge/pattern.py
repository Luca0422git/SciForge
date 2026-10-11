# SPDX-License-Identifier: LGPL-2.1-or-later
"""Rectangular Pattern, Circular Pattern, Pattern on Path and Mirror: the document side
(no Qt), shared by the dialogs (pattern_ui.py, mirror_ui.py) and the golden models.

What gets built, by Fusion's Pattern Type:

  Features  PartDesign::LinearPattern / PolarPattern / Mirrored, the features FreeCAD's
            own commands make (Direction 2 is LinearPattern's second direction). Features
            FreeCAD cannot repeat (fillets, chamfers, shells, Press Pull...) and Pattern on
            Path use SciForge's PatternFeature below.
  Faces     PatternFeature: the picked faces are closed into a solid (the hole or boss
            they bound), which is copied and joined or cut at every instance.
  Bodies    the same FreeCAD features in "Whole shape" mode: the body's shape is copied
            (copies that touch it join it; the others stay separate solids of the body).

Spacing rules (Quantity, Distance, Extent/Spacing, One Direction/Symmetric, Full/Angle/
Symmetric) live in pattern_core.py. Every feature carries SciForgeType (the timeline shows
it as Fusion's step and opens SciForge's dialog on it) and a hidden JSON property with the
dialog choices FreeCAD has no property for.

FreeCAD 1.1.4 stores LinearPattern.Spacings2 = [0.0] by default, which stacks a second row
on the first (core patch #4 fixes the default in C++). SciForge always writes both spacing
lists itself, so two-direction patterns are right on stock FreeCAD and in old files too.
"""
import json
import math
import re

import FreeCAD as App
import Part

from . import pattern_core as core
from .pattern_core import PatternError

KINDS = ("rectangular", "circular", "path", "mirror")
TITLES = {
    "rectangular": "Rectangular Pattern",
    "circular": "Circular Pattern",
    "path": "Pattern on Path",
    "mirror": "Mirror",
}
NATIVE = {
    "rectangular": "PartDesign::LinearPattern",
    "circular": "PartDesign::PolarPattern",
    "mirror": "PartDesign::Mirrored",
}
KIND_OF_TYPE = {type_id: kind for kind, type_id in NATIVE.items()}
SCIFORGE_TYPE = {
    "rectangular": "RectangularPattern",
    "circular": "CircularPattern",
    "path": "PatternOnPath",
    "mirror": "Mirror",
}
KIND_OF_SCIFORGE = {value: kind for kind, value in SCIFORGE_TYPE.items()}
ENGINE = "PartDesign::FeaturePython"
META = "SciForgePattern"
LINE_TYPES = ("App::Line", "PartDesign::Line", "Part::DatumLine")
PLANE_TYPES = ("App::Plane", "PartDesign::Plane", "Part::DatumPlane")
SKETCH = "Sketcher::SketchObject"
SUBTRACTIVE = (
    "PartDesign::Pocket",
    "PartDesign::Groove",
    "PartDesign::Hole",
)
TOL = 1e-7

DEFAULTS = {
    "pattern_type": "features",  # "faces", "bodies" or "features"
    "objects": [],  # [(feature, "")], [(feature, "FaceN")] or [(body, "")]
    # rectangular (and the shared fields of Pattern on Path)
    "direction": None,
    "quantity": 2,
    "distance": 20.0,
    "direction_type": "one",
    "direction2": None,
    "quantity2": 1,
    "distance2": 20.0,
    "direction_type2": "one",
    "distribution": "extent",
    # circular
    "axis": None,
    "circular_type": "full",
    "angle": 360.0,
    # mirror
    "plane": None,
    "operation": "new_body",  # Mirror of a body: "new_body" or "join"
    # pattern on path
    "path": None,
    "orientation": "identical",  # or "path": copies turn with the path
    "suppressed": [],  # Suppression: copies (index among the copies) that are not made
    "expressions": {},  # value field key -> formula typed in the dialog
}


class NeedsPick(PatternError):
    """A selection the pattern cannot do without is still empty: the dialog waits for it
    (Fusion shows no error for that, the selection box is just still blue)."""


def with_defaults(options):
    merged = dict(DEFAULTS)
    merged.update(options or {})
    merged["expressions"] = dict(merged.get("expressions") or {})
    merged["objects"] = list(merged.get("objects") or [])
    merged["suppressed"] = sorted({int(i) for i in (merged.get("suppressed") or [])})
    return merged


# -- objects in the document ---------------------------------------------------------------
def owner_body(obj):
    if obj is None:
        return None
    if obj.TypeId == "PartDesign::Body":
        return obj
    try:
        parent = obj.getParentGeoFeatureGroup()
    except Exception:
        return None
    if parent is not None and parent.TypeId == "PartDesign::Body":
        return parent
    return None


def alive(obj):
    if obj is None:
        return False
    try:
        if hasattr(obj, "isAttachedToDocument"):
            return obj.isAttachedToDocument()
        return bool(obj.Name)
    except Exception:
        return False


def kind_of(obj):
    """'rectangular' / 'circular' / 'path' / 'mirror' for a pattern feature, else None."""
    if obj is None:
        return None
    kind = KIND_OF_SCIFORGE.get(getattr(obj, "SciForgeType", ""))
    if kind is not None:
        return kind
    return KIND_OF_TYPE.get(obj.TypeId)


def is_pattern(obj):
    return kind_of(obj) is not None


def is_solid_feature(obj):
    """A step of a body's history that has a solid (what Features can pattern)."""
    try:
        return obj.isDerivedFrom("PartDesign::Feature") and obj.TypeId not in (
            "PartDesign::Body",
            "PartDesign::FeatureBase",
        )
    except Exception:
        return False


def is_add_sub(obj):
    try:
        return obj.isDerivedFrom("PartDesign::FeatureAddSub")
    except Exception:
        return False


def is_subtractive(obj):
    if obj.TypeId in SUBTRACTIVE or obj.TypeId.startswith("PartDesign::Subtractive"):
        return True
    if getattr(obj, "SciForgeType", "") == "Extrude":
        return getattr(obj, "Operation", "") == "Cut"
    return False


def _is_dress_up(obj):
    try:
        return obj.isDerivedFrom("PartDesign::DressUp")
    except Exception:
        return False


def natively_patternable(features):
    """True when FreeCAD's own pattern features can repeat every one of `features`."""
    return bool(features) and all(is_add_sub(f) for f in features)


def body_history(body):
    """The body's solid steps, in timeline order."""
    return [o for o in body.Group if is_solid_feature(o)] if body is not None else []


def before(body, feature, other):
    """True if `other` comes before `feature` in the body's timeline."""
    order = [o.Name for o in body.Group]
    try:
        return order.index(other.Name) < order.index(feature.Name)
    except ValueError:
        return False


# -- references (edges, axes, planes) in body coordinates ----------------------------------
def _element(obj, sub):
    try:
        return obj.Shape.getElement(sub)
    except Exception:
        raise PatternError("%s of %s no longer exists. Pick it again." % (sub, obj.Label))


def _datum_frame(obj):
    """(base point, X direction, Z direction) of an origin/datum element, body coordinates."""
    place = obj.Placement
    return (
        App.Vector(place.Base),
        place.Rotation.multVec(App.Vector(1, 0, 0)),
        place.Rotation.multVec(App.Vector(0, 0, 1)),
    )


def _line_of_datum(obj):
    if obj.TypeId == "App::Line":
        base, x, _z = _datum_frame(obj)
        return base, x
    edges = obj.Shape.Edges if not obj.Shape.isNull() else []
    if edges:
        edge = edges[0]
        return edge.valueAt(edge.FirstParameter), _unit(edge.tangentAt(edge.FirstParameter))
    base, _x, z = _datum_frame(obj)
    return base, z


def _plane_of_datum(obj):
    if obj.TypeId == "App::Plane":
        base, _x, z = _datum_frame(obj)
        return base, z
    faces = obj.Shape.Faces if not obj.Shape.isNull() else []
    if faces:
        face = faces[0]
        return face.CenterOfMass, _unit(face.normalAt(0, 0))
    base, _x, z = _datum_frame(obj)
    return base, z


def _unit(vec):
    vec = App.Vector(vec)
    if vec.Length < 1e-12:
        raise PatternError("That reference has no direction.")
    return vec.normalize()


def _is_line(edge):
    return edge.Curve.TypeId in ("Part::GeomLine", "Part::GeomLineSegment")


def _is_circle(edge):
    return edge.Curve.TypeId in ("Part::GeomCircle", "Part::GeomArcOfCircle")


ORIGIN_NAMES = {
    "X_Axis": "X Axis",
    "Y_Axis": "Y Axis",
    "Z_Axis": "Z Axis",
    "XY_Plane": "XY Plane",
    "XZ_Plane": "XZ Plane",
    "YZ_Plane": "YZ Plane",
}


def ref_label(ref):
    """How a picked reference is shown in a selection box (Fusion's origin names)."""
    if not ref:
        return ""
    obj, sub = ref
    if not alive(obj):
        return ""
    role = getattr(obj, "Role", "")
    if role in ORIGIN_NAMES:
        return ORIGIN_NAMES[role]
    if obj.TypeId in LINE_TYPES + PLANE_TYPES:
        return obj.Label
    if sub:
        return "%s of %s" % (sub.rstrip("0123456789") or sub, obj.Label)
    return obj.Label


def direction_of(ref):
    """(point, unit vector) of a rectangular pattern direction, body coordinates.
    A straight edge or axis, or the normal of a flat face or plane."""
    obj, sub = ref
    if obj.TypeId in LINE_TYPES:
        return _line_of_datum(obj)
    if obj.TypeId in PLANE_TYPES:
        return _plane_of_datum(obj)
    if not sub:
        raise PatternError("Pick a straight edge, an axis or a flat face for the direction.")
    element = _element(obj, sub)
    if sub.startswith("Edge"):
        if not _is_line(element):
            raise PatternError("The direction must be a straight edge. Pick a straight edge.")
        return element.valueAt(element.FirstParameter), _unit(element.tangentAt(0))
    if sub.startswith("Face"):
        if element.Surface.TypeId != "Part::GeomPlane":
            raise PatternError("Only a flat face gives a direction (its normal).")
        return element.CenterOfMass, _unit(element.normalAt(0, 0))
    raise PatternError("Pick a straight edge, an axis or a flat face for the direction.")


def axis_of(ref):
    """(point, unit vector) of a circular pattern axis, body coordinates: an axis, a
    straight edge, a circular edge (its centre line) or a round face (its axis)."""
    obj, sub = ref
    if obj.TypeId in LINE_TYPES:
        return _line_of_datum(obj)
    if not sub:
        raise PatternError("Pick an axis, a straight or round edge, or a round face.")
    element = _element(obj, sub)
    if sub.startswith("Edge"):
        if _is_line(element):
            return element.valueAt(element.FirstParameter), _unit(element.tangentAt(0))
        if _is_circle(element):
            return App.Vector(element.Curve.Center), _unit(element.Curve.Axis)
        raise PatternError("That edge has no axis. Pick a straight or round edge.")
    if sub.startswith("Face"):
        surface = element.Surface
        if surface.TypeId in ("Part::GeomCylinder", "Part::GeomCone"):
            return App.Vector(surface.Center), _unit(surface.Axis)
        raise PatternError("That face has no axis. Pick a round face (a hole or a shaft).")
    raise PatternError("Pick an axis, a straight or round edge, or a round face.")


def plane_of(ref):
    """(point, unit normal) of a mirror plane, body coordinates."""
    obj, sub = ref
    if obj.TypeId in PLANE_TYPES:
        return _plane_of_datum(obj)
    if sub.startswith("Face"):
        element = _element(obj, sub)
        if element.Surface.TypeId != "Part::GeomPlane":
            raise PatternError("The mirror plane must be flat. Pick a flat face or a plane.")
        return element.CenterOfMass, _unit(element.normalAt(0, 0))
    raise PatternError("Pick a plane or a flat face to mirror across.")


def native_axis_ref(ref):
    """FreeCAD's PolarPattern takes an axis or an edge, not a face: a round face is
    replaced by one of its circular edges (same axis)."""
    obj, sub = ref
    if not sub.startswith("Face"):
        return ref
    face = _element(obj, sub)
    point, axis = axis_of(ref)
    for i, edge in enumerate(obj.Shape.Edges, start=1):
        if not _is_circle(edge):
            continue
        if not any(edge.isSame(e) for e in face.Edges):
            continue
        if abs(abs(_unit(edge.Curve.Axis).dot(axis)) - 1.0) > 1e-9:
            continue
        offset = App.Vector(edge.Curve.Center) - point
        if (offset - axis * offset.dot(axis)).Length < 1e-6:
            return (obj, "Edge%d" % i)
    raise PatternError("This round face has no circular edge to use as the axis. Pick an axis.")


def to_global(body, point=None, vector=None):
    place = body.getGlobalPlacement() if body is not None else App.Placement()
    out = []
    if point is not None:
        out.append(place.multVec(point))
    if vector is not None:
        out.append(place.Rotation.multVec(vector))
    return out[0] if len(out) == 1 else tuple(out)


# -- what is patterned -----------------------------------------------------------------------
def _features(options):
    return [obj for obj, sub in options["objects"] if not sub and is_solid_feature(obj)]


def _faces(options):
    return [(obj, sub) for obj, sub in options["objects"] if sub.startswith("Face")]


def _bodies(options):
    return [obj for obj, sub in options["objects"] if obj.TypeId == "PartDesign::Body"]


def target_body(options):
    for obj, _sub in options.get("objects") or []:
        body = owner_body(obj)
        if body is not None:
            return body
    return None


def quantity_formulas(options):
    """The quantity fields that follow a parameter or formula."""
    exprs = options.get("expressions") or {}
    return [k for k in ("quantity", "quantity2") if (exprs.get(k) or "").strip()]


def implementation(kind, options):
    """'native' (FreeCAD's pattern features) or 'engine' (SciForge's PatternFeature)."""
    if kind == "path":
        return "engine"
    if options.get("suppressed") and kind != "mirror":
        return "engine"  # FreeCAD's pattern features cannot leave an instance out
    if quantity_formulas(options) and kind != "mirror":
        return "engine"  # a count that follows a parameter: SciForge's feature recounts
    kind_type = options["pattern_type"]
    if kind_type == "faces":
        return "engine"
    if kind_type == "features" and not natively_patternable(_features(options)):
        return "engine"
    return "native"


def total_instances(kind, options):
    """How many instances the pattern has, the original included."""
    if kind == "mirror":
        return 2
    if kind == "circular":
        kind_of = "symmetric" if options["circular_type"] == "symmetric" else "one"
        return core.instance_count(options["quantity"], kind_of)
    total = core.instance_count(options["quantity"], options["direction_type"])
    if kind == "rectangular" and options.get("direction2") is not None:
        total *= core.instance_count(options["quantity2"], options["direction_type2"])
    return total


def check(kind, options):
    """Raise NeedsPick / PatternError when the pattern cannot be built yet."""
    ptype = options["pattern_type"]
    if ptype == "bodies" and quantity_formulas(options) and kind != "mirror":
        raise PatternError(
            "A pattern of bodies takes a plain number as its quantity (each copy is a body)."
        )
    if ptype == "features":
        if not _features(options):
            raise NeedsPick("Select the features to pattern: click them in the timeline.")
    elif ptype == "faces":
        if not _faces(options):
            raise NeedsPick("Select the faces to pattern (all faces of a hole or a boss).")
    elif ptype == "bodies":
        bodies = _bodies(options)
        if not bodies:
            raise NeedsPick("Select the body to pattern.")
        if len(bodies) > 1:
            raise PatternError("Select one body: each body gets its own pattern.")
        if bodies[0].Tip is None or bodies[0].Shape.isNull():
            raise PatternError("%s has no solid to copy yet." % bodies[0].Label)
    else:
        raise PatternError("Unknown pattern type %r." % ptype)
    core.check_total(total_instances(kind, options))
    if kind == "rectangular":
        if options["direction"] is None:
            raise NeedsPick("Select Direction 1: an edge, an axis or a flat face.")
        _check_direction(options, "")
        if options["direction2"] is not None:
            _check_direction(options, "2")
    elif kind == "circular":
        if options["axis"] is None:
            raise NeedsPick("Select the axis: an axis, an edge or a round face.")
        axis_of(options["axis"])
        if int(options["quantity"]) < 1:
            raise PatternError("The quantity must be at least 1.")
        if options["circular_type"] != "full":
            angle = float(options["angle"])
            if abs(angle) < 1e-9:
                raise PatternError("The total angle must not be 0.")
            if abs(angle) > 360.0 + 1e-9:
                raise PatternError("The total angle can be at most 360 deg.")
    elif kind == "mirror":
        if options["plane"] is None:
            raise NeedsPick("Select the mirror plane: a plane or a flat face.")
        plane_of(options["plane"])
    elif kind == "path":
        if options["path"] is None:
            raise NeedsPick("Select the path: an edge or a sketch curve.")
        path_edges(options["path"])
        if int(options["quantity"]) < 1:
            raise PatternError("The quantity must be at least 1.")
        if int(options["quantity"]) > 1 and abs(float(options["distance"])) < 1e-9:
            raise PatternError("The distance must not be 0.")
    else:
        raise PatternError("Unknown pattern %r." % kind)


def _check_direction(options, suffix):
    direction_of(options["direction" + suffix])
    quantity = int(options["quantity" + suffix])
    if quantity < 1:
        raise PatternError("The quantity must be at least 1.")
    if quantity > 1 and abs(float(options["distance" + suffix])) < 1e-9:
        raise PatternError("The distance must not be 0.")


# -- building --------------------------------------------------------------------------------
def build(kind, options, feature=None, name=None):
    """Create the pattern, or update `feature` with new options. Returns the feature (a new
    object when the change needs the other kind of feature: FreeCAD's or SciForge's)."""
    options = with_defaults(options)
    check(kind, options)
    if makes_bodies(kind, options):
        return _build_body_copies(kind, options, feature, name)
    if feature is not None and is_body_pattern(feature):
        remove(feature)  # the copies were new bodies; now they join the body
        feature = None
    impl = implementation(kind, options)
    body = target_body(options)
    if body is None:
        raise PatternError("The picked objects are not in a body.")
    wanted = NATIVE[kind] if impl == "native" else ENGINE
    if feature is not None and alive(feature):
        same = feature.TypeId == wanted and kind_of(feature) == kind
        if same and owner_body(feature) is body:
            _update(feature, kind, options)
            return feature
    new = _create(body, kind, wanted, name or TITLES[kind].replace(" ", ""), feature)
    try:
        _update(new, kind, options)
    except Exception:
        _delete(new)
        raise
    if feature is not None and alive(feature):
        label = feature.Label
        was_tip = owner_body(feature) is not None and owner_body(feature).Tip is feature
        _same_visibility(feature, new)
        # Later steps built on the old pattern (a sketch on its top face, a fillet on its
        # edges, another pattern of it) move over to the new one; FreeCAD would just drop
        # those references when the old one is deleted.
        relink_dependents(feature, new)
        _delete(feature)
        new.Label = label
        if was_tip:
            body.Tip = new
    return new


def _create(body, kind, type_id, name, replacing=None):
    doc = body.Document
    if replacing is not None and alive(replacing) and owner_body(replacing) is body:
        obj = doc.addObject(type_id, name)
        body.insertObject(obj, replacing, False)
    else:
        obj = body.newObject(type_id, name)
        body.Tip = obj  # newObject() does not move the Tip for pattern features
    if type_id == ENGINE:
        PatternFeature(obj)
        _attach_view_provider(obj)
    _mark(obj, kind)
    if hasattr(obj, "Refine"):
        obj.Refine = True  # Fusion never leaves seam faces
    return obj


def _mark(obj, kind):
    if "SciForgeType" not in obj.PropertiesList:
        obj.addProperty("App::PropertyString", "SciForgeType", "Base", "", 4)  # hidden
    obj.SciForgeType = SCIFORGE_TYPE[kind]
    if META not in obj.PropertiesList:
        obj.addProperty("App::PropertyString", META, "Base", "", 4)


def _attach_view_provider(obj):
    if not App.GuiUp:
        return
    try:
        from .pattern_ui import ViewProviderPattern

        ViewProviderPattern(obj.ViewObject)
    except Exception:
        pass


def _delete(obj):
    doc = obj.Document
    body = owner_body(obj)
    try:
        if body is not None:
            body.removeObject(obj)
    except Exception:
        pass
    try:
        doc.removeObject(obj.Name)
    except Exception:
        pass


def _same_visibility(old, new):
    """A pattern rebuilt in the middle of the timeline stays hidden like the step it replaces
    (FreeCAD shows a new feature, which drew it over the part)."""
    if not App.GuiUp:
        return
    try:
        new.ViewObject.Visibility = bool(old.ViewObject.Visibility)
    except Exception:
        pass


# -- later steps that use a pattern which is rebuilt as another feature -------------------------
# Changing a pattern can need the other kind of feature (FreeCAD's LinearPattern cannot leave a
# copy out, follow a parameter in its count or repeat faces; SciForge's PatternFeature can), so
# the step is rebuilt as a new object. Fusion keeps everything that was built on the pattern: a
# sketch on its top face, a fillet on its edges. FreeCAD clears links to a deleted object, so
# before the old one goes, every link to it is moved to the new one, each face / edge / vertex
# found again on the new shape by where it is.
_CHAIN = {"BaseFeature", "_Body", "Group", "Tip", "Origin"}
_ELEMENT = re.compile(r"^(Face|Edge|Vertex)(\d+)$")


def _quiet():
    from .preview import quiet

    return quiet()


def _computed(obj):
    """obj recomputed on its own (its base is up to date), quietly: (True if it has a shape)."""
    try:
        with _quiet():
            obj.recompute()
    except Exception:
        pass
    try:
        return not obj.Shape.isNull()
    except Exception:
        return False


def _sample_points(element):
    """A few points that lie on `element` (inside a face, along an edge)."""
    kind = element.ShapeType
    if kind == "Vertex":
        return [element.Point]
    if kind == "Edge":
        a, b = element.FirstParameter, element.LastParameter
        return [element.valueAt(a + (b - a) * t) for t in (0.5, 0.31, 0.73)]
    points = []
    try:
        u0, u1, v0, v1 = element.ParameterRange
        for fu, fv in ((0.5, 0.5), (0.31, 0.37), (0.71, 0.67), (0.29, 0.73), (0.73, 0.27)):
            p = element.valueAt(u0 + (u1 - u0) * fu, v0 + (v1 - v0) * fv)
            if element.isInside(p, 1e-6, True):
                points.append(p)
    except Exception:
        pass
    if not points:  # a narrow face (a ring, a sliver): the middles of its facets
        try:
            vertices, triangles = element.tessellate(0.5)
            surface = element.Surface
            for a, b, c in triangles[:5]:
                middle = (vertices[a] + vertices[b] + vertices[c]) * (1.0 / 3.0)
                points.append(surface.value(*surface.parameter(middle)))
        except Exception:
            points = []
    return points or [element.CenterOfMass]


def _size(element):
    kind = element.ShapeType
    if kind == "Face":
        return element.Area
    if kind == "Edge":
        return element.Length
    return 0.0


def twin_element(shape, element, tol=1e-6):
    """Name ("Face7") of the element of `shape` at the place of `element` (the same plane
    and spot, the same edge line...), or None. When a face was split or grew (a copy left
    out), the one covering most of it wins."""
    kind = element.ShapeType
    pool = {"Face": shape.Faces, "Edge": shape.Edges, "Vertex": shape.Vertexes}.get(kind)
    if not pool:
        return None
    points = _sample_points(element)
    probes = [Part.Vertex(p) for p in points]
    size = _size(element)
    best = None
    for i, candidate in enumerate(pool, start=1):
        try:
            if kind == "Face" and candidate.Surface.TypeId != element.Surface.TypeId:
                continue
            if kind == "Edge" and candidate.Curve.TypeId != element.Curve.TypeId:
                continue
            box = candidate.BoundBox
            box.enlarge(10 * tol)
            if not any(box.isInside(p) for p in points):
                continue
            hits = sum(1 for v in probes if candidate.distToShape(v)[0] < 10 * tol)
        except Exception:
            continue
        if not hits:
            continue
        key = (hits, -abs(_size(candidate) - size))
        if best is None or key > best[0]:
            best = (key, i)
    return "%s%d" % (kind, best[1]) if best is not None else None


def _mapped(sub, old_shape, new_shape, cache):
    """`sub` of the old pattern ("Face5", or a long name ending in it) as the same place on
    the new shape; the old name when it cannot be found."""
    if not sub or new_shape is None:
        return sub
    short = sub.split(".")[-1]
    if not _ELEMENT.match(short):
        return sub
    if short not in cache:
        found = None
        try:
            found = twin_element(new_shape, old_shape.getElement(short))
        except Exception:
            found = None
        cache[short] = found or short
    return cache[short]


def _swapped(value, old, new, old_shape, new_shape, cache):
    """(value with `old` replaced by `new` and its element names mapped, changed?)."""
    if value is None:
        return value, False
    if hasattr(value, "TypeId"):  # a single link
        return (new, True) if value is old else (value, False)
    if isinstance(value, tuple) and len(value) == 2 and hasattr(value[0], "TypeId"):
        obj, subs = value
        if obj is not old:
            return value, False
        if isinstance(subs, str):
            return (new, _mapped(subs, old_shape, new_shape, cache)), True
        return (new, [_mapped(s, old_shape, new_shape, cache) for s in subs]), True
    if isinstance(value, (list, tuple)):
        out, changed = [], False
        for item in value:
            swapped, did = _swapped(item, old, new, old_shape, new_shape, cache)
            out.append(swapped)
            changed = changed or did
        return out, changed
    return value, False


def relink_dependents(old, new):
    """Point every object that links to `old` (except the body's own history chain) at `new`,
    with its faces/edges/vertices found again on `new`'s shape. Returns the objects changed."""
    if old is None or new is None or old is new:
        return []
    users = [o for o in old.InList if o is not new and o.TypeId != "PartDesign::Body"]
    if not users:
        return []
    old_shape = None
    try:
        old_shape = old.Shape if not old.Shape.isNull() else None
    except Exception:
        old_shape = None
    new_shape = new.Shape if _computed(new) else None
    cache = {}
    changed = []
    for user in users:
        for prop in user.PropertiesList:
            if prop in _CHAIN:
                continue
            try:
                kind = user.getTypeIdOfProperty(prop)
            except Exception:
                continue
            if not kind.startswith(("App::PropertyLink", "App::PropertyXLink")):
                continue
            try:
                value = getattr(user, prop)
            except Exception:
                continue
            if old_shape is None:
                swapped, did = _swapped(value, old, new, None, None, cache)
            else:
                swapped, did = _swapped(value, old, new, old_shape, new_shape, cache)
            if not did:
                continue
            try:
                setattr(user, prop, swapped)
                if user not in changed:
                    changed.append(user)
            except Exception:
                pass
    return changed


# -- a pattern whose features were all deleted -----------------------------------------------------
# FreeCAD's pattern features return without touching their shape when none of the features they
# repeat is left (FeatureTransformed.cpp: "originals.empty() -> StdReturn"): the part kept the
# copies of a deleted hole, and froze there (a later change of the box never reached the steps
# after the pattern). Fusion shows such a pattern with a warning and it adds nothing: SciForge
# passes the shape before it through and says why in the timeline.
WARNING_PROP = "SciForgeWarning"  # the timeline shows this text as the step's warning
ORPHAN_NOTE = (
    "Nothing to repeat: the features it used were deleted or suppressed. Edit it to pick "
    "others, or delete it."
)


def live_originals(obj):
    return [o for o in (getattr(obj, "Originals", None) or []) if alive(o) and not _suppressed(o)]


def _suppressed(obj):
    try:
        return bool(getattr(obj, "Suppressed", False))
    except Exception:
        return False


def orphaned(obj):
    """True for a pattern of features (FreeCAD's or SciForge's) with nothing left to repeat."""
    try:
        if kind_of(obj) is None or is_body_pattern(obj) or _suppressed(obj):
            return False
        if obj.TypeId == ENGINE:
            if _enum_get(obj, "PatternType") != "features":
                return False
        elif getattr(obj, "TransformMode", "Features") != "Features":
            return False
        return not live_originals(obj)
    except Exception:
        return False


def set_note(obj, text):
    """The warning the timeline shows on a step ('' clears it); never marks it for recompute."""
    if WARNING_PROP not in obj.PropertiesList:
        if not text:
            return
        # 4 = hidden, 16 = changing it does not mark the step for recompute
        obj.addProperty("App::PropertyString", WARNING_PROP, "SciForge", "Timeline warning", 4 | 16)
    if getattr(obj, WARNING_PROP) != text:
        setattr(obj, WARNING_PROP, text)


def _base_shape(obj):
    base = getattr(obj, "BaseFeature", None)
    if base is not None and not base.Shape.isNull():
        return base.Shape.copy()
    return Part.Shape()


class OrphanWatch:
    """Document observer: right after FreeCAD recomputes one of its pattern features that has
    nothing left to repeat, its shape becomes the shape before it (see above)."""

    def slotRecomputedObject(self, obj):
        try:
            if obj.TypeId not in KIND_OF_TYPE:
                return
            if orphaned(obj):
                obj.Shape = _base_shape(obj)
                set_note(obj, ORPHAN_NOTE)
            elif getattr(obj, WARNING_PROP, "") == ORPHAN_NOTE:
                set_note(obj, "")
        except Exception:
            pass


_ORPHANS = {"observer": None}


def install_orphan_watch():
    if _ORPHANS["observer"] is None:
        _ORPHANS["observer"] = OrphanWatch()
        App.addDocumentObserver(_ORPHANS["observer"])


def show_tip(body):
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


def remove(feature):
    """Take a pattern out again (a dialog's preview that is cancelled or dropped)."""
    if not alive(feature):
        return
    if is_body_pattern(feature):
        _remove_body_copies(feature)
        return
    body = owner_body(feature)
    was_tip = body is not None and body.Tip is feature
    _delete(feature)
    if was_tip:
        show_tip(body)


def load_meta(obj):
    try:
        return json.loads(getattr(obj, META, "") or "{}")
    except Exception:
        return {}


def _save_meta(obj, meta):
    if META not in obj.PropertiesList:
        obj.addProperty("App::PropertyString", META, "Base", "", 4)
    text = json.dumps(meta, sort_keys=True)
    if getattr(obj, META) != text:
        setattr(obj, META, text)


def _link(ref):
    obj, sub = ref
    return (obj, [sub])


def _set(obj, prop, value):
    """Set a property only when it changes (no needless recompute of what follows)."""
    current = getattr(obj, prop)
    if hasattr(current, "Value"):
        if abs(current.Value - float(value)) < 1e-12:
            return
    elif current == value:
        return
    setattr(obj, prop, value)


def _set_link(obj, prop, ref):
    value = _link(ref) if ref is not None else None
    current = getattr(obj, prop)
    if value is None:
        if current is not None:
            setattr(obj, prop, None)
        return
    if current is None or current[0] is not value[0] or list(current[1]) != value[1]:
        setattr(obj, prop, value)


def _update(obj, kind, options):
    if obj.TypeId == ENGINE:
        _update_engine(obj, kind, options)
    else:
        _update_native(obj, kind, options)
    meta = {
        "v": 1,
        "kind": kind,
        "pattern_type": options["pattern_type"],
        "distribution": options["distribution"],
        "direction_type": options["direction_type"],
        "direction_type2": options["direction_type2"],
        "circular_type": options["circular_type"],
        "quantity": int(options["quantity"]),
        "quantity2": int(options["quantity2"]),
        "orientation": options["orientation"],
        "expressions": {k: v for k, v in options["expressions"].items() if v},
    }
    _save_meta(obj, meta)


# -- FreeCAD's pattern features ------------------------------------------------------------------
def _update_native(obj, kind, options):
    ptype = options["pattern_type"]
    if ptype == "bodies":
        _set(obj, "TransformMode", "Whole shape")
        if list(obj.Originals):
            obj.Originals = []
        body = _bodies(options)[0]
        if owner_body(obj) is not body:
            raise PatternError("A body pattern must live in the body it copies.")
    else:
        _set(obj, "TransformMode", "Features")
        wanted = _features(options)
        if [o.Name for o in obj.Originals] != [o.Name for o in wanted]:
            obj.Originals = wanted
    if kind == "rectangular":
        _native_direction(obj, options, "")
        if options["direction2"] is not None:
            _native_direction(obj, options, "2")
        else:
            _set_link(obj, "Direction2", None)
            _set(obj, "Occurrences2", 1)
            _set(obj, "Mode2", "Spacing")
            _set_list(obj, "Spacings2", [])
            _clear_expressions(obj, ("Length2", "Offset2", "Spacings2"))
    elif kind == "circular":
        _native_circular(obj, options)
    elif kind == "mirror":
        _set_link(obj, "MirrorPlane", options["plane"])


def _set_list(obj, prop, values):
    values = [float(v) for v in values]
    current = list(getattr(obj, prop))
    if len(current) != len(values) or any(abs(a - b) > 1e-12 for a, b in zip(current, values)):
        setattr(obj, prop, values)


def _clear_expressions(obj, props):
    engine = dict(obj.ExpressionEngine)
    for prop in props:
        if prop in engine:
            obj.setExpression(prop, None)


def _formula(options, key, doc):
    """The formula typed for a value field, in FreeCAD's expression syntax ('' if none)."""
    from . import parameters, parameters_core

    text = (options["expressions"].get(key) or "").strip()
    if not text:
        return ""
    return parameters_core.to_freecad(text, parameters.user_names(doc))


def _expr(obj, prop, expr):
    engine = dict(obj.ExpressionEngine)
    if expr:
        if engine.get(prop) != expr:
            obj.setExpression(prop, expr)
    elif prop in engine:
        obj.setExpression(prop, None)


def _symmetric_list_expression(quantity, offset_prop):
    """The Spacings walk as an expression of Offset, so the copies follow a parameter."""
    terms = []
    for term in core.symmetric_walk_terms(quantity):
        if term == 1:
            terms.append("%s.Value" % offset_prop)
        else:
            k = -term
            terms.append(
                "(%d * %s.Value == 1 ? %r : -%d * %s.Value)"
                % (k, offset_prop, core.SENTINEL - core.NUDGE, k, offset_prop)
            )
    return "list(%s)" % "; ".join(terms)


def _native_direction(obj, options, suffix):
    ref = options["direction" + suffix]
    _set_link(obj, "Direction" + suffix, ref)
    quantity = max(1, int(options["quantity" + suffix]))
    distance = float(options["distance" + suffix])
    distribution = options["distribution"]
    symmetric = options["direction_type" + suffix] == "symmetric"
    formula = _formula(options, "distance" + suffix, obj.Document)
    occurrences = core.instance_count(quantity, options["direction_type" + suffix])
    length_prop, offset_prop = "Length" + suffix, "Offset" + suffix
    spacings_prop = "Spacings" + suffix
    if not symmetric:
        mode = "Extent" if distribution == "extent" else "Spacing"
        _set(obj, "Mode" + suffix, mode)
        _set(obj, "Reversed" + suffix, distance < 0)
        _set(obj, "Occurrences" + suffix, occurrences)
        size = abs(distance)
        wrapped = ("-(%s)" % formula if distance < 0 else formula) if formula else ""
        if mode == "Extent":
            _expr(obj, offset_prop, "")
            _set(obj, length_prop, size)
            _expr(obj, length_prop, wrapped)
        else:
            _expr(obj, length_prop, "")
            _set(obj, offset_prop, size)
            _expr(obj, offset_prop, wrapped)
        _expr(obj, spacings_prop, "")
        _set_list(obj, spacings_prop, [core.SENTINEL] * (occurrences - 1))
        return
    # Symmetric: a walk of gaps, 0, s, .. (n-1)s, then over to -(n-1)s and back up to -s.
    step = abs(core.step_of(quantity, distance, distribution))
    _set(obj, "Mode" + suffix, "Spacing")
    _set(obj, "Reversed" + suffix, False)
    _set(obj, "Occurrences" + suffix, occurrences)
    _expr(obj, length_prop, "")
    if quantity > 1:
        _set(obj, offset_prop, step)
    if formula and quantity > 1:
        if distribution == "extent":
            _expr(obj, offset_prop, "abs(%s) / %d" % (formula, quantity - 1))
        else:
            _expr(obj, offset_prop, "abs(%s)" % formula)
    else:
        _expr(obj, offset_prop, "")
    gaps = [step * t for t in core.symmetric_walk_terms(quantity)]
    if formula and quantity > 1:
        _expr(obj, spacings_prop, _symmetric_list_expression(quantity, offset_prop))
    else:
        _expr(obj, spacings_prop, "")
        _set_list(obj, spacings_prop, core.safe_walk(gaps))


def _native_circular(obj, options):
    ref = native_axis_ref(options["axis"])
    _set_link(obj, "Axis", ref)
    ctype = options["circular_type"]
    quantity = max(1, int(options["quantity"]))
    angle = float(options["angle"])
    formula = _formula(options, "angle", obj.Document)
    occurrences = core.instance_count(quantity, "symmetric" if ctype == "symmetric" else "one")
    if ctype in ("full", "angle"):
        _set(obj, "Mode", "Extent")
        _set(obj, "Occurrences", occurrences)
        if ctype == "full":
            _set(obj, "Reversed", False)
            _expr(obj, "Angle", "")
            _set(obj, "Angle", 360.0)
        else:
            _set(obj, "Reversed", angle < 0)
            _set(obj, "Angle", min(abs(angle), 360.0))
            _expr(obj, "Angle", ("abs(%s)" % formula) if formula else "")
        _expr(obj, "Offset", "")
        _expr(obj, "Spacings", "")
        _set_list(obj, "Spacings", [core.SENTINEL] * (occurrences - 1))
        return
    step = abs(angle) / (quantity - 1) if quantity > 1 else 0.0
    _set(obj, "Mode", "Spacing")
    _set(obj, "Reversed", False)
    _set(obj, "Occurrences", occurrences)
    _expr(obj, "Angle", "")
    if quantity > 1:
        _set(obj, "Offset", step)
        _expr(obj, "Offset", ("abs(%s) / %d" % (formula, quantity - 1)) if formula else "")
        if formula:
            _expr(obj, "Spacings", _symmetric_list_expression(quantity, "Offset"))
        else:
            _expr(obj, "Spacings", "")
            gaps = [step * t for t in core.symmetric_walk_terms(quantity)]
            _set_list(obj, "Spacings", core.safe_walk(gaps))
    else:
        _expr(obj, "Offset", "")
        _expr(obj, "Spacings", "")
        _set_list(obj, "Spacings", [])


# -- SciForge's own pattern feature ---------------------------------------------------------------
ENUMS = {
    "PatternType": ["Features", "Faces", "Bodies"],
    "Distribution": ["Extent", "Spacing"],
    "DirectionType": ["One Direction", "Symmetric"],
    "DirectionType2": ["One Direction", "Symmetric"],
    "CircularType": ["Full", "Angle", "Symmetric"],
    "Orientation": ["Identical", "Path Direction"],
}
ENUM_VALUES = {
    "PatternType": ["features", "faces", "bodies"],
    "Distribution": ["extent", "spacing"],
    "DirectionType": ["one", "symmetric"],
    "DirectionType2": ["one", "symmetric"],
    "CircularType": ["full", "angle", "symmetric"],
    "Orientation": ["identical", "path"],
}


def _enum_set(obj, prop, value):
    label = ENUMS[prop][ENUM_VALUES[prop].index(value)]
    if getattr(obj, prop) != label:
        setattr(obj, prop, label)


def _enum_get(obj, prop):
    try:
        return ENUM_VALUES[prop][ENUMS[prop].index(getattr(obj, prop))]
    except (ValueError, AttributeError):
        return ENUM_VALUES[prop][0]


class PatternFeature:
    """A PartDesign feature that repeats faces, features FreeCAD's patterns cannot repeat,
    or anything along a path. Its shape is the body before it with the copies joined or
    cut. Saved files store "sciforge.pattern.PatternFeature": keep the name stable."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, "Pattern", doc)
                return True
            return False

        for prop, labels in ENUMS.items():
            if add("App::PropertyEnumeration", prop, "Dialog choice (Fusion's field)"):
                setattr(obj, prop, labels)
        add("App::PropertyLinkSub", "Faces", "The faces that are patterned")
        add("App::PropertyLinkList", "Originals", "The features that are patterned")
        add("App::PropertyLinkSub", "Direction", "Direction 1")
        add("App::PropertyLinkSub", "Direction2", "Direction 2")
        add("App::PropertyLinkSub", "Axis", "Axis of a circular pattern")
        add("App::PropertyLinkSub", "MirrorPlane", "Mirror plane")
        add("App::PropertyLinkSub", "Path", "Path of a pattern on path")
        if add("App::PropertyInteger", "Quantity", "Instances (the original included)"):
            obj.Quantity = 2
        if add("App::PropertyInteger", "Quantity2", "Instances in direction 2"):
            obj.Quantity2 = 1
        add("App::PropertyDistance", "Distance", "Distance (extent or spacing)")
        add("App::PropertyDistance", "Distance2", "Distance in direction 2")
        if add("App::PropertyAngle", "Angle", "Total angle of a circular pattern"):
            obj.Angle = 360.0
        if add("App::PropertyBool", "Refine", "Merge faces that end up coplanar, like Fusion"):
            obj.Refine = True
        add("App::PropertyIntegerList", "SuppressedCopies", "Copies left out (Suppression)")

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        base = obj.BaseFeature
        if base is None or base.Shape.isNull() or not base.Shape.Solids:
            raise PatternError("A pattern needs a solid before it in the timeline.")
        if orphaned(obj):  # every feature it repeated was deleted: it adds nothing
            obj.Shape = base.Shape.copy()
            set_note(obj, ORPHAN_NOTE)
            return
        if getattr(obj, WARNING_PROP, "") == ORPHAN_NOTE:
            set_note(obj, "")
        kind = kind_of(obj)
        options = read_engine(obj)
        tools = engine_tools(obj, options, base)
        # A path pattern starts where the dialog's arrow is: nearest the objects' centre.
        center = objects_center(options)[0] if kind == "path" else None
        moves = placements(kind, options, tools, center)
        obj.Shape = apply_tools(base.Shape, tools, moves, kind, refine=obj.Refine)

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def _update_engine(obj, kind, options):
    body = owner_body(obj)
    base = obj.BaseFeature
    if base is None and body is not None:
        group = body_history(body)
        if obj in group and group.index(obj) > 0:
            obj.BaseFeature = group[group.index(obj) - 1]
    ptype = options["pattern_type"]
    _enum_set(obj, "PatternType", ptype)
    if ptype == "faces":
        faces = _faces(options)
        owner = faces[0][0]
        names = [sub for o, sub in faces if o is owner]
        if len(names) != len(faces):
            raise PatternError("Pick faces of one part.")
        current = obj.Faces
        if current is None or current[0] is not owner or list(current[1]) != names:
            obj.Faces = (owner, names)
    elif obj.Faces is not None:
        obj.Faces = None
    wanted = _features(options) if ptype == "features" else []
    if [o.Name for o in obj.Originals] != [o.Name for o in wanted]:
        obj.Originals = wanted
    _enum_set(obj, "Distribution", options["distribution"])
    _enum_set(obj, "DirectionType", options["direction_type"])
    _enum_set(obj, "DirectionType2", options["direction_type2"])
    _enum_set(obj, "CircularType", options["circular_type"])
    _enum_set(obj, "Orientation", options["orientation"])
    for prop, key in (
        ("Direction", "direction"),
        ("Direction2", "direction2"),
        ("MirrorPlane", "plane"),
        ("Path", "path"),
    ):
        _set_link(obj, prop, options[key] if kind in _USES[prop] else None)
    _set_link(obj, "Axis", options["axis"] if kind == "circular" else None)
    _set(obj, "Quantity", max(1, int(options["quantity"])))
    _set(obj, "Quantity2", max(1, int(options["quantity2"])))
    for prop, key in (
        ("Distance", "distance"),
        ("Distance2", "distance2"),
        ("Angle", "angle"),
        ("Quantity", "quantity"),
        ("Quantity2", "quantity2"),
    ):
        if key.startswith("quantity"):
            formula = _formula(options, key, obj.Document)
            _expr(obj, prop, "round(%s)" % formula if formula else "")
            continue
        _set(obj, prop, float(options[key]))
        _expr(obj, prop, _formula(options, key, obj.Document))
    _set_suppressed(obj, options)


def _set_suppressed(obj, options):
    wanted = [int(i) for i in options.get("suppressed") or []]
    if list(obj.SuppressedCopies) != wanted:
        obj.SuppressedCopies = wanted


_USES = {
    "Direction": ("rectangular",),
    "Direction2": ("rectangular",),
    "MirrorPlane": ("mirror",),
    "Path": ("path",),
}


def read_engine(obj):
    """The options of a PatternFeature (values as FreeCAD has them now)."""
    options = with_defaults({})
    options["pattern_type"] = _enum_get(obj, "PatternType")
    options["distribution"] = _enum_get(obj, "Distribution")
    options["direction_type"] = _enum_get(obj, "DirectionType")
    options["direction_type2"] = _enum_get(obj, "DirectionType2")
    options["circular_type"] = _enum_get(obj, "CircularType")
    options["orientation"] = _enum_get(obj, "Orientation")
    for prop, key in (
        ("Direction", "direction"),
        ("Direction2", "direction2"),
        ("Axis", "axis"),
        ("MirrorPlane", "plane"),
        ("Path", "path"),
    ):
        link = getattr(obj, prop)
        options[key] = (link[0], (list(link[1]) or [""])[0]) if link else None
    options["quantity"] = int(obj.Quantity)
    options["quantity2"] = int(obj.Quantity2)
    options["distance"] = obj.Distance.Value
    options["distance2"] = obj.Distance2.Value
    options["angle"] = obj.Angle.Value
    options["suppressed"] = list(getattr(obj, "SuppressedCopies", []) or [])
    if options["pattern_type"] == "faces" and obj.Faces:
        options["objects"] = [(obj.Faces[0], sub) for sub in obj.Faces[1]]
    elif options["pattern_type"] == "features":
        options["objects"] = [(o, "") for o in obj.Originals]
    else:
        body = owner_body(obj)
        options["objects"] = [(body, "")] if body is not None else []
    return options


# -- the copies ----------------------------------------------------------------------------------
def placements(kind, options, tools=None, center=None):
    """Body-coordinate transforms of the copies that are made (the original's identity not
    included, suppressed copies left out): App.Placement for moves, ("mirror", point, normal)
    for the mirror."""
    moves = all_placements(kind, options, tools, center)
    skip = set(options.get("suppressed") or []) if kind != "mirror" else set()
    return [move for i, move in enumerate(moves) if i not in skip]


def all_placements(kind, options, tools=None, center=None):
    """Every copy's transform, suppressed ones included (Suppression shows them as dots)."""
    core.check_total(total_instances(kind, options))
    if kind == "rectangular":
        _p, u1 = direction_of(options["direction"])
        offsets1 = core.linear_offsets(
            options["quantity"],
            options["distance"],
            options["distribution"],
            options["direction_type"],
        )
        offsets2 = [0.0]
        u2 = App.Vector()
        if options["direction2"] is not None:
            _p, u2 = direction_of(options["direction2"])
            offsets2 = core.linear_offsets(
                options["quantity2"],
                options["distance2"],
                options["distribution"],
                options["direction_type2"],
            )
        moves = []
        for a, b in core.grid(offsets1, offsets2)[1:]:
            moves.append(App.Placement(u1 * a + u2 * b, App.Rotation()))
        return moves
    if kind == "circular":
        point, axis = axis_of(options["axis"])
        angles = core.circular_angles(
            options["quantity"], options["angle"], options["circular_type"]
        )
        return [App.Placement(App.Vector(), App.Rotation(axis, a), point) for a in angles[1:]]
    if kind == "mirror":
        point, normal = plane_of(options["plane"])
        return [("mirror", point, normal)]
    if kind == "path":
        return path_placements(options, tools, center)
    raise PatternError("Unknown pattern %r." % kind)


def _moved(shape, move):
    if isinstance(move, tuple):
        _tag, point, normal = move
        return shape.mirror(point, normal)
    copy = shape.copy()
    copy.transformShape(move.toMatrix())
    return copy


def engine_tools(obj, options, base):
    """[(solid, "add" | "cut")] in body coordinates: what each instance adds or removes."""
    ptype = options["pattern_type"]
    if ptype == "faces":
        link = obj.Faces
        if not link:
            raise PatternError("Select the faces to pattern.")
        owner, names = link[0], list(link[1])
        shape = owner.Shape
        faces = [_element(owner, n) for n in names]
        # Faces picked on an earlier step: find them again on the shape this builds on.
        if owner is not base:
            faces = [_same_face(base.Shape, f) for f in faces]
            shape = base.Shape
        return [face_tool(shape, faces)]
    if ptype == "bodies":
        return [(base.Shape.copy(), "add")]
    tools = []
    for feature in obj.Originals:
        tools += feature_tools(feature)
    if not tools:
        raise PatternError("Select the features to pattern.")
    return tools


def _same_face(shape, face):
    for candidate in shape.Faces:
        if (
            abs(candidate.Area - face.Area) < 1e-6 * max(1.0, face.Area)
            and (candidate.CenterOfMass - face.CenterOfMass).Length < 1e-6
        ):
            return candidate
    raise PatternError("A picked face no longer exists after an earlier change. Pick it again.")


def feature_tools(feature):
    """What a feature adds or removes: its tool shape for extrudes, holes and the like, else
    the difference it made to the part (fillets, chamfers, Press Pull...)."""
    if is_add_sub(feature) and not _is_dress_up(feature):
        try:
            tool = feature.AddSubShape
        except Exception:
            tool = None
        if tool is not None and not tool.isNull() and tool.Solids:
            return [(tool.copy(), "cut" if is_subtractive(feature) else "add")]
    before_obj = getattr(feature, "BaseFeature", None)
    after = feature.Shape
    if before_obj is None or before_obj.Shape.isNull():
        return [(after.copy(), "add")]
    before_shape = before_obj.Shape
    tools = []
    added = after.cut(before_shape)
    if added.Solids and added.Volume > TOL:
        tools.append((added, "add"))
    removed = before_shape.cut(after)
    if removed.Solids and removed.Volume > TOL:
        tools.append((removed, "cut"))
    if not tools:
        raise PatternError(
            "%s does not change the part, so there is nothing to repeat." % (feature.Label)
        )
    return tools


def apply_tools(base_shape, tools, moves, kind, refine=True):
    adds, cuts = [], []
    for tool, how in tools:
        for move in moves:
            (adds if how == "add" else cuts).append(_moved(tool, move))
    result = base_shape.copy()
    if adds:
        result = result.fuse(adds)
    if cuts:
        result = result.cut(cuts)
    if refine:
        try:
            result = result.removeSplitter()
        except Exception:
            pass
    if result.isNull() or not result.Solids:
        raise PatternError("The pattern leaves no solid.")
    solids = result.Solids
    return solids[0] if len(solids) == 1 else Part.makeCompound(solids)


# -- closing picked faces into a solid ------------------------------------------------------------
def face_tool(shape, faces):
    """(solid, "add" | "cut"): the solid that the picked faces of `shape` bound together with
    the faces around them (a hole's wall gives the hole's cylinder; a boss's side and top
    give the boss). "cut" when it is a hollow in the part, "add" when it is material."""
    picked = list(faces)
    boundary = []
    for face in picked:
        for edge in face.Edges:
            hosts = [
                f
                for f in shape.ancestorsOfType(edge, Part.Face)
                if not any(f.isSame(p) for p in picked)
            ]
            if hosts and not any(edge.isSame(b[0]) for b in boundary):
                boundary.append((edge, hosts))
    if not boundary:
        raise PatternError(
            "These faces are the whole part. Pick the faces of a hole, a pocket or a boss."
        )
    patches = []
    for group in Part.sortEdges([e for e, _h in boundary]):
        wire = Part.Wire(group)
        if not wire.isClosed():
            raise PatternError(_NOT_CLOSED)
        hosts = None
        for edge in group:
            found = next(h for e, h in boundary if e.isSame(edge))
            names = {_face_key(h) for h in found}
            hosts = names if hosts is None else hosts & names
        if not hosts:
            raise PatternError(_NOT_CLOSED)
        host = next(h for e, hs in boundary for h in hs if _face_key(h) in hosts)
        patches.append(_patch(host, wire))
    try:
        shell = Part.Shell(picked + patches)
        shell.sewShape()  # the patches get their own copies of the boundary edges
        solid = Part.Solid(shell)
        if solid.Volume < 0:
            solid.reverse()
    except Exception:
        raise PatternError(_NOT_CLOSED)
    if not shell.isClosed() or not solid.isValid() or abs(solid.Volume) < TOL:
        raise PatternError(_NOT_CLOSED)
    return solid, _hollow_or_material(shape, picked[0], solid)


_NOT_CLOSED = (
    "These faces do not close up into a feature. Pick every face of the hole, pocket or "
    "boss (for a boss: its sides and its top)."
)


def _face_key(face):
    return (round(face.Area, 9), tuple(round(c, 6) for c in face.CenterOfMass))


def _patch(host, wire):
    """The piece of `host`'s surface inside `wire` (where the feature meets the part)."""
    if host.Surface.TypeId == "Part::GeomPlane":
        try:
            patch = Part.Face(wire)
            if patch.isValid() and patch.Area > TOL:
                return patch
        except Exception:
            pass
    patch = Part.Face(host.Surface, wire)
    patch.validate()
    if not patch.isValid() or patch.Area < TOL:
        raise PatternError(_NOT_CLOSED)
    return patch


def _hollow_or_material(shape, face, solid):
    u0, u1, v0, v1 = face.ParameterRange
    for fu, fv in ((0.5, 0.5), (0.3, 0.6), (0.7, 0.4)):
        u, v = u0 + (u1 - u0) * fu, v0 + (v1 - v0) * fv
        if not face.isInside(face.valueAt(u, v), 1e-6, True):
            continue
        point = face.valueAt(u, v)
        normal = face.normalAt(u, v)
        step = max(1e-3, min(0.05, solid.BoundBox.DiagonalLength * 1e-3))
        if solid.isInside(point - normal * step, 1e-9, False):
            return "add"
        if solid.isInside(point + normal * step, 1e-9, False):
            return "cut"
    raise PatternError(_NOT_CLOSED)


# -- pattern on path ----------------------------------------------------------------------------
def path_edges(ref):
    """The edges of a path pick, in order: one edge, or every edge of a sketch."""
    obj, sub = ref
    if sub.startswith("Edge"):
        return [_element(obj, sub)]
    if obj.TypeId == SKETCH and not sub:
        edges = list(obj.Shape.Edges)
        if not edges:
            raise PatternError("%s has no curves to follow." % obj.Label)
        groups = Part.sortEdges(edges)
        if len(groups) != 1:
            raise PatternError("The sketch has separate curves. Pick one edge as the path.")
        return Part.Wire(groups[0]).OrderedEdges
    raise PatternError("Pick an edge or a sketch curve as the path.")


def _objects_center(options, tools):
    if tools:
        box = None
        for tool, _how in tools:
            box = tool.BoundBox if box is None else box.united(tool.BoundBox)
        return box.Center
    return App.Vector()


class _Path:
    """A path made of edges in order; positions are arc lengths from its start."""

    def __init__(self, edges):
        self.edges = edges
        self.lengths = [e.Length for e in edges]
        self.total = sum(self.lengths)
        try:
            self.closed = Part.Wire(edges).isClosed()
        except Exception:
            self.closed = False
        self.normal = None  # the plane of a flat path (copies turn about it)
        try:
            plane = (
                Part.Wire(edges).findPlane() if not _is_line(edges[0]) or len(edges) > 1 else None
            )
            if plane is not None:
                self.normal = _unit(plane.Axis)
        except Exception:
            self.normal = None

    @staticmethod
    def _flipped(edge):
        return getattr(edge, "Orientation", "Forward") == "Reversed"

    def locate(self, point):
        """Arc length of the point of the path nearest to `point`."""
        best = None
        run = 0.0
        vertex = Part.Vertex(point)
        for edge, length in zip(self.edges, self.lengths):
            dist, pairs, _info = edge.distToShape(vertex)
            param = edge.Curve.parameter(pairs[0][0])
            param = min(max(param, edge.FirstParameter), edge.LastParameter)
            along = _length_between(edge, edge.FirstParameter, param)
            if self._flipped(edge):
                along = length - along
            if best is None or dist < best[0] - 1e-9:
                best = (dist, run + along)
            run += length
        return best[1]

    def at(self, s):
        """(point, unit tangent along the path) at arc length s from the start. A closed path
        (a circle, a closed sketch) goes round and round."""
        if self.closed and self.total > 0:
            s = s % self.total
        if s < -1e-6 or s > self.total + 1e-6:
            raise PatternError(
                "The pattern runs off the end of the path. Make the distance shorter."
            )
        s = min(max(s, 0.0), self.total)
        run = 0.0
        last = len(self.edges) - 1
        for i, (edge, length) in enumerate(zip(self.edges, self.lengths)):
            if s <= run + length + 1e-9 or i == last:
                local = min(max(s - run, 0.0), length)
                flipped = self._flipped(edge)
                param = edge.getParameterByLength(length - local if flipped else local)
                tangent = _unit(edge.tangentAt(param))
                return edge.valueAt(param), tangent * -1.0 if flipped else tangent
            run += length
        raise PatternError("The pattern runs off the end of the path.")


def _length_between(edge, a, b):
    if abs(b - a) < 1e-12:
        return 0.0
    lo, hi = min(a, b), max(a, b)
    try:
        return Part.Edge(edge.Curve, lo, hi).Length
    except Exception:
        return abs(b - a)


def path_placements(options, tools, center=None):
    path = _Path(path_edges(options["path"]))
    if center is None:
        center = _objects_center(options, tools)
    start = path.locate(center)
    offsets = core.linear_offsets(
        options["quantity"], options["distance"], options["distribution"], options["direction_type"]
    )
    point0, tangent0 = path.at(start)
    moves = []
    for offset in offsets[1:]:
        point, tangent = path.at(start + offset)
        if options["orientation"] == "path":
            turn = _turn(tangent0, tangent, path.normal)
            moves.append(
                App.Placement(point - point0, App.Rotation()).multiply(
                    App.Placement(App.Vector(), turn, point0)
                )
            )
        else:
            moves.append(App.Placement(point - point0, App.Rotation()))
    return moves


def _turn(t0, t1, normal):
    """The rotation that turns the path's direction t0 into t1: about the plane of a flat path
    (so a copy half way round a circle is turned, not flipped over), else the shortest one."""
    if normal is None:
        return App.Rotation(t0, t1)
    import math

    a = t0 - normal * t0.dot(normal)
    b = t1 - normal * t1.dot(normal)
    if a.Length < 1e-12 or b.Length < 1e-12:
        return App.Rotation(t0, t1)
    a.normalize()
    b.normalize()
    angle = math.degrees(math.atan2(a.cross(b).dot(normal), a.dot(b)))
    return App.Rotation(normal, angle)


# -- reading a pattern back into the dialog --------------------------------------------------------
def read(feature):
    """(kind, options) of an existing pattern or mirror feature."""
    kind = kind_of(feature)
    if kind is None:
        raise PatternError("%s is not a pattern." % feature.Label)
    meta = load_meta(feature)
    if is_body_pattern(feature):
        options = read_body_pattern(feature)
    elif feature.TypeId == ENGINE:
        options = read_engine(feature)
    else:
        options = _read_native(feature, kind, meta)
        if kind == "mirror" and options["pattern_type"] == "bodies":
            options["operation"] = "join"
    options["expressions"] = {
        k: v for k, v in (meta.get("expressions") or {}).items() if _still_formula(feature, k)
    }
    return kind, options


def _still_formula(feature, key):
    props = {
        "distance": ("Length", "Offset", "Distance"),
        "distance2": ("Length2", "Offset2", "Distance2"),
        "angle": ("Angle", "Offset"),
        "quantity": ("Quantity",),
        "quantity2": ("Quantity2",),
    }.get(key, ())
    engine = dict(feature.ExpressionEngine)
    return any(p in engine for p in props)


def _read_native(obj, kind, meta):
    options = with_defaults({})
    if obj.TransformMode == "Whole shape":
        options["pattern_type"] = "bodies"
        body = owner_body(obj)
        options["objects"] = [(body, "")] if body is not None else []
    else:
        options["pattern_type"] = "features"
        options["objects"] = [(o, "") for o in obj.Originals]
    if kind == "rectangular":
        _read_direction(obj, options, meta, "")
        if obj.Direction2 is not None:
            _read_direction(obj, options, meta, "2")
        else:
            options["direction2"] = None
            options["quantity2"] = 1
        if obj.Mode == "Spacing" and meta.get("direction_type", "one") == "one":
            options["distribution"] = "spacing"
        elif obj.Mode == "Extent":
            options["distribution"] = "extent"
        else:
            options["distribution"] = meta.get("distribution", "extent")
    elif kind == "circular":
        link = obj.Axis
        options["axis"] = (link[0], (list(link[1]) or [""])[0]) if link else None
        occurrences = int(obj.Occurrences)
        if obj.Mode == "Spacing" and meta.get("circular_type") == "symmetric":
            quantity = (occurrences + 1) // 2
            options["circular_type"] = "symmetric"
            options["quantity"] = quantity
            options["angle"] = obj.Offset.Value * (quantity - 1) if quantity > 1 else 90.0
        elif obj.Mode == "Spacing":
            options["circular_type"] = "angle"
            options["quantity"] = occurrences
            options["angle"] = obj.Offset.Value * max(occurrences - 1, 1)
        else:
            angle = obj.Angle.Value
            full = abs(angle - 360.0) < 1e-9 and meta.get("circular_type", "full") == "full"
            options["circular_type"] = "full" if full else "angle"
            options["quantity"] = occurrences
            options["angle"] = -angle if obj.Reversed else angle
    elif kind == "mirror":
        link = obj.MirrorPlane
        options["plane"] = (link[0], (list(link[1]) or [""])[0]) if link else None
    return options


def _read_direction(obj, options, meta, suffix):
    link = getattr(obj, "Direction" + suffix)
    options["direction" + suffix] = (link[0], (list(link[1]) or [""])[0]) if link else None
    occurrences = int(getattr(obj, "Occurrences" + suffix))
    mode = getattr(obj, "Mode" + suffix)
    dtype = meta.get("direction_type" + suffix, "one")
    if mode == "Spacing" and dtype == "symmetric":
        quantity = (occurrences + 1) // 2
        step = getattr(obj, "Offset" + suffix).Value
        options["direction_type" + suffix] = "symmetric"
        options["quantity" + suffix] = quantity
        if meta.get("distribution", "extent") == "extent":
            options["distance" + suffix] = step * (quantity - 1)
        else:
            options["distance" + suffix] = step
        return
    options["direction_type" + suffix] = "one"
    options["quantity" + suffix] = occurrences
    value = getattr(obj, ("Length" if mode == "Extent" else "Offset") + suffix).Value
    reversed_ = bool(getattr(obj, "Reversed" + suffix))
    options["distance" + suffix] = -value if reversed_ else value


# -- helpers for the dialogs ------------------------------------------------------------------------
def objects_center(options, base=None):
    """(centre, box) of what is patterned, body coordinates (where the drag arrows start).
    A feature's tool is clipped to the part: a cut through all is as long as the part."""
    box = None
    for obj, sub in options.get("objects") or []:
        try:
            if obj.TypeId == "PartDesign::Body":
                shape = obj.Shape.copy()
                shape.transformShape(obj.getGlobalPlacement().inverse().toMatrix())
                part = shape.BoundBox
            elif sub:
                shape = obj.Shape.getElement(sub)
                part = shape.BoundBox
            elif is_add_sub(obj) and not _is_dress_up(obj) and not obj.AddSubShape.isNull():
                shape = obj.AddSubShape
                part = obj.Shape.BoundBox
            else:
                shape = obj.Shape
                part = shape.BoundBox
        except Exception:
            continue
        found = shape.BoundBox
        if found.intersect(part):
            found = found.intersected(part)
        box = found if box is None else box.united(found)
    return (box.Center if box is not None else App.Vector()), box


def to_global_shape(body, shape):
    """A copy of a body-coordinate shape in global coordinates."""
    copy = shape.copy()
    place = body.getGlobalPlacement() if body is not None else App.Placement()
    if not place.isIdentity():
        copy.transformShape(place.toMatrix())
    return copy


def faces_made_by(feature, shape, limit=400):
    """Faces of `shape` (the part, body coordinates) that `feature` made: they lie on what it
    added or removed (a hole's wall, a boss's sides and top, a fillet's round). For the
    highlight of a picked feature."""
    try:
        tools = [tool for tool, _how in feature_tools(feature)]
    except Exception:
        return []
    if not tools or len(shape.Faces) > limit:
        return []
    found = []
    for face in shape.Faces:
        box = face.BoundBox
        near = [t for t in tools if t.BoundBox.intersect(box)]
        if not near:
            continue
        points = _sample_points(face)[:3]
        if all(any(t.distToShape(Part.Vertex(p))[0] < 1e-5 for t in near) for p in points):
            found.append(face)
    return found


def feature_of_face(body, face, until=None):
    """The step of `body` that made `face` (body coordinates): the last feature before `until`
    whose tool shape has the face on its boundary. None if the face is from the first step
    or cannot be told."""
    point = face.CenterOfMass
    try:
        u0, u1, v0, v1 = face.ParameterRange
        point = face.valueAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)
        if not face.isInside(point, 1e-6, True):
            point = face.CenterOfMass
    except Exception:
        pass
    vertex = Part.Vertex(point)
    found = None
    for feature in body_history(body):
        if until is not None and feature is until:
            break
        if kind_of(feature) is not None:
            continue
        tools = []
        if is_add_sub(feature):
            try:
                if not feature.AddSubShape.isNull():
                    tools.append(feature.AddSubShape)
            except Exception:
                pass
        for tool in tools:
            try:
                if tool.distToShape(vertex)[0] < 1e-5 and _on_shell(feature.Shape, point):
                    found = feature
            except Exception:
                continue
    return found


def _on_shell(shape, point):
    try:
        return shape.distToShape(Part.Vertex(point))[0] < 1e-5
    except Exception:
        return False


# -- Bodies: the copies are new bodies (Fusion) ------------------------------------------------------
# A pattern of a body (or a mirror with Operation New Body) makes one new body per copy, like
# Fusion. The pattern itself is a top-level SciForge feature (the timeline step) that knows the
# source body and the pattern's values; every copy is a small feature (BodyCopyFeature) that a
# new PartDesign body takes as its base feature, so the copies follow the source body and the
# pattern when either changes, and more features can be added to each copy's body.
COPY = "Part::FeaturePython"
BODY_PROPS = (
    ("Direction", "direction", ("rectangular",)),
    ("Direction2", "direction2", ("rectangular",)),
    ("Axis", "axis", ("circular",)),
    ("MirrorPlane", "plane", ("mirror",)),
    ("Path", "path", ("path",)),
)
BODY_ENUMS = (
    ("Distribution", "distribution"),
    ("DirectionType", "direction_type"),
    ("DirectionType2", "direction_type2"),
    ("CircularType", "circular_type"),
    ("Orientation", "orientation"),
)


def makes_bodies(kind, options):
    if options["pattern_type"] != "bodies":
        return False
    return kind != "mirror" or options.get("operation", "new_body") == "new_body"


def is_body_pattern(obj):
    return (
        obj is not None
        and obj.TypeId == COPY
        and kind_of(obj) is not None
        and isinstance(getattr(obj, "Proxy", None), BodyPatternFeature)
    )


def is_body_copy(obj):
    return obj is not None and isinstance(getattr(obj, "Proxy", None), BodyCopyFeature)


def feature_body(feature):
    """The body a pattern works on (for a pattern of bodies: the body it copies)."""
    if is_body_pattern(feature):
        return feature.Source
    return owner_body(feature)


def base_of(feature):
    """The step a pattern builds on (for a pattern of bodies: the end of the copied body)."""
    if is_body_pattern(feature):
        source = feature.Source
        return source.Tip if source is not None else None
    return getattr(feature, "BaseFeature", None)


class BodyPatternFeature:
    """The step of a pattern of bodies. Saved as "sciforge.pattern.BodyPatternFeature"."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, "Pattern", doc)
                return True
            return False

        for prop, _key in BODY_ENUMS:
            if add("App::PropertyEnumeration", prop, "Dialog choice (Fusion's field)"):
                setattr(obj, prop, ENUMS[prop])
        # Global links: the references sit inside the copied body, this feature outside it.
        add("App::PropertyLinkGlobal", "Source", "The body that is copied")
        for prop, _key, _kinds in BODY_PROPS:
            add("App::PropertyLinkSubGlobal", prop, prop)
        if add("App::PropertyInteger", "Quantity", "Instances (the original included)"):
            obj.Quantity = 2
        if add("App::PropertyInteger", "Quantity2", "Instances in direction 2"):
            obj.Quantity2 = 1
        add("App::PropertyDistance", "Distance", "Distance (extent or spacing)")
        add("App::PropertyDistance", "Distance2", "Distance in direction 2")
        if add("App::PropertyAngle", "Angle", "Total angle of a circular pattern"):
            obj.Angle = 360.0
        add("App::PropertyIntegerList", "SuppressedCopies", "Copies left out (Suppression)")

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        source = obj.Source
        if source is None or source.Shape.isNull() or not source.Shape.Solids:
            raise PatternError("The body to copy has no solid.")
        copies = body_copy_shapes(obj)
        obj.Shape = Part.makeCompound(copies) if copies else Part.Shape()

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


class BodyCopyFeature:
    """One copy of a pattern of bodies: the base feature of a new body.
    Saved as "sciforge.pattern.BodyCopyFeature"."""

    def __init__(self, obj):
        obj.Proxy = self
        if "Pattern" not in obj.PropertiesList:
            obj.addProperty("App::PropertyLink", "Pattern", "Pattern", "The pattern")
        if "Index" not in obj.PropertiesList:
            obj.addProperty("App::PropertyInteger", "Index", "Pattern", "Which copy")
        _hide_from_timeline(obj)

    def execute(self, obj):
        definition = obj.Pattern
        if definition is None:
            # The pattern step was deleted: the copy keeps its shape (pattern_ui removes such
            # orphans right after a delete, as Fusion deletes the copies with the pattern).
            return
        copies = body_copy_shapes(definition)
        if obj.Index >= len(copies):
            return  # about to be removed by the pattern (fewer copies now)
        obj.Shape = copies[obj.Index]

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def _hide_from_timeline(obj):
    if "SciForgeTimeline" not in obj.PropertiesList:
        obj.addProperty("App::PropertyBool", "SciForgeTimeline", "Base", "", 4)
    obj.SciForgeTimeline = False


def read_body_pattern(obj):
    options = with_defaults({})
    options["pattern_type"] = "bodies"
    options["operation"] = "new_body"
    for prop, key in BODY_ENUMS:
        options[key] = _enum_get(obj, prop)
    for prop, key, _kinds in BODY_PROPS:
        link = getattr(obj, prop)
        options[key] = (link[0], (list(link[1]) or [""])[0]) if link else None
    options["quantity"] = int(obj.Quantity)
    options["quantity2"] = int(obj.Quantity2)
    options["distance"] = obj.Distance.Value
    options["distance2"] = obj.Distance2.Value
    options["angle"] = obj.Angle.Value
    options["suppressed"] = list(getattr(obj, "SuppressedCopies", []) or [])
    options["objects"] = [(obj.Source, "")] if obj.Source is not None else []
    return options


def body_copy_shapes(definition):
    """The copies of a pattern of bodies, in global coordinates (the original not included)."""
    kind = kind_of(definition)
    options = read_body_pattern(definition)
    source = definition.Source
    shape = _baked(source.Shape)  # global: the body's placement is included
    place = source.getGlobalPlacement()
    local = shape.copy()
    local.transformShape(place.inverse().toMatrix(), True)
    center = local.BoundBox.Center if kind == "path" else None
    moves = placements(kind, options, [(local, "add")], center)
    copies = []
    for move in moves:
        if isinstance(move, tuple):
            _tag, point, normal = move
            copies.append(shape.mirror(place.multVec(point), place.Rotation.multVec(normal)))
        else:
            whole = place.multiply(move).multiply(place.inverse())
            copy = shape.copy()
            copy.transformShape(whole.toMatrix(), True)
            copies.append(copy)
    return copies


def _baked(shape):
    """A copy of `shape` with its placement built into the geometry: a body takes the shape of
    its base feature without the placement (the copy landed on top of the original)."""
    place = shape.Placement
    out = shape.copy()
    if not place.isIdentity():
        out.Placement = App.Placement()
        out.transformShape(place.toMatrix(), True)
    return out


def _copies_of(definition):
    found = [o for o in definition.InList if is_body_copy(o)]
    return sorted(found, key=lambda o: o.Index)


def _body_of_copy(copy):
    for obj in copy.InList:
        if obj.TypeId == "PartDesign::Body" and obj.BaseFeature is copy:
            return obj
    return None


def _set_body_props(obj, kind, options):
    source = _bodies(options)[0]
    if obj.Source is not source:
        obj.Source = source
    for prop, key, kinds in BODY_PROPS:
        _set_link(obj, prop, options[key] if kind in kinds else None)
    for prop, key in BODY_ENUMS:
        _enum_set(obj, prop, options[key])
    _set(obj, "Quantity", max(1, int(options["quantity"])))
    _set(obj, "Quantity2", max(1, int(options["quantity2"])))
    for prop, key in (("Distance", "distance"), ("Distance2", "distance2"), ("Angle", "angle")):
        _set(obj, prop, float(options[key]))
        _expr(obj, prop, _formula(options, key, obj.Document))
    _set_suppressed(obj, options)


def _build_body_copies(kind, options, feature, name=None):
    source = _bodies(options)[0]
    doc = source.Document
    label = None
    if feature is not None and alive(feature):
        if not (is_body_pattern(feature) and kind_of(feature) == kind):
            label = feature.Label
            base = None if is_body_pattern(feature) else getattr(feature, "BaseFeature", None)
            if base is not None:
                # the copies leave the body: what was built on the pattern stays on the step
                # before it (its top face is still there, without the copies)
                relink_dependents(feature, base)
            remove(feature)
            feature = None
    else:
        feature = None
    if feature is None:
        feature = doc.addObject(COPY, name or TITLES[kind].replace(" ", ""))
        BodyPatternFeature(feature)
        _mark(feature, kind)
        if label:
            feature.Label = label
        if App.GuiUp:
            try:
                from .pattern_ui import ViewProviderPattern

                ViewProviderPattern(feature.ViewObject)
                feature.ViewObject.Visibility = False
            except Exception:
                pass
    _set_body_props(feature, kind, options)
    _save_meta(
        feature,
        {
            "v": 1,
            "kind": kind,
            "pattern_type": "bodies",
            "operation": "new_body",
            "expressions": {k: v for k, v in options["expressions"].items() if v},
        },
    )
    count = len(body_copy_shapes(feature))
    copies = _copies_of(feature)
    for copy in copies[count:]:
        _remove_copy(copy)
    for index in range(len(copies), count):
        _new_copy(feature, index, source)
    return feature


def _new_copy(definition, index, source):
    doc = definition.Document
    copy = doc.addObject(COPY, "BodyCopy")
    BodyCopyFeature(copy)
    copy.Pattern = definition
    copy.Index = index
    body = doc.addObject("PartDesign::Body", "Body")
    container = source.getParentGeoFeatureGroup()
    if container is not None and hasattr(container, "addObject"):
        container.addObject(body)
    count = len([o for o in doc.Objects if o.TypeId == "PartDesign::Body"])
    body.Label = "Body%d" % count
    body.BaseFeature = copy
    for obj in body.Group:
        if obj.TypeId == "PartDesign::FeatureBase":
            _hide_from_timeline(obj)  # the copy belongs to the pattern's step
    if App.GuiUp:
        try:
            copy.ViewObject.Visibility = False
        except Exception:
            pass
    return body


def _remove_copy(copy):
    doc = copy.Document
    body = _body_of_copy(copy)
    if body is not None:
        try:
            body.removeObjectsFromDocument()
        except Exception:
            pass
        try:
            doc.removeObject(body.Name)
        except Exception:
            pass
    try:
        doc.removeObject(copy.Name)
    except Exception:
        pass


def _remove_body_copies(definition):
    for copy in _copies_of(definition):
        _remove_copy(copy)
    try:
        definition.Document.removeObject(definition.Name)
    except Exception:
        pass


def orphan_copies(doc):
    """Copies whose pattern step was deleted."""
    return [o for o in doc.Objects if is_body_copy(o) and o.Pattern is None]


def remove_orphans(doc):
    """Remove the copies (and their bodies) of deleted patterns. True if any were found."""
    found = orphan_copies(doc)
    for copy in found:
        _remove_copy(copy)
    return bool(found)


def copy_bodies(definition):
    """The new bodies a pattern of bodies made, in order."""
    return [b for b in (_body_of_copy(c) for c in _copies_of(definition)) if b is not None]
