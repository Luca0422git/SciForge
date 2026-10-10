# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Revolve on top of PartDesign. No GUI code: the Revolve command and the
golden-model builder both call this module, so they behave the same.

Profiles (what is revolved), a list of (object, sub-element), as for Extrude:
  (sketch, "InternalFace2")   one closed region of a sketch (a Fusion profile)
  (sketch, "")                the whole sketch
  (feature, "Face6")          a flat face of a body

Axis (what it turns about), one (object, sub-element):
  (origin axis, "")           the X, Y or Z axis of a body's origin (App::Line)
  (datum axis, "")            a construction axis (PartDesign::Line)
  (sketch, "Edge3")           a straight line of a sketch
  (sketch, "Axis0")           a construction line of a sketch (FreeCAD numbers them)
  (sketch, "H_Axis")          the sketch's own horizontal / vertical axis
  (feature, "Edge7")          a straight edge of a body

Options (dict, see DEFAULTS):
  operation  join | cut | intersect | new_body
  type       angle | full          (full = 360 degrees, no direction)
  direction  one_side | two_sides | symmetric
  angle      degrees. One side: signed, a negative angle turns the other way.
             Symmetric: the angle on each side (the whole revolve is twice that, like
             Fusion's symmetric revolve). Two sides: side one (its sign picks the side).
  angle2     degrees of side two (two sides), turning the other way

A positive angle turns right-handed about the axis direction, which is FreeCAD's own
direction for that reference (an origin axis points along +X/+Y/+Z, a line from its
start to its end), so FreeCAD's "Reversed" is simply "angle < 0".

What is built:
  join / cut     a PartDesign Revolution / Groove in the body of the profile. Changing
                 the operation swaps one for the other (the timeline keeps its place).
  new_body       a new PartDesign Body holding a Revolution (the first solid of an empty
                 body is simply a Revolution there: that already is a new body)
  intersect      SciForge's RevolveFeature: the body keeps what lies inside the revolve
Hidden helpers carry references FreeCAD cannot link directly (a profile from several
sketches or from another body, an axis in another body). Fusion-only choices (type,
direction, the picks as made) are stored as JSON in the hidden "SciForgeRevolve"
property, so editing the revolve from the timeline offers them again.
"""
import json

import FreeCAD as App

from . import extrude

OPERATIONS = ("join", "cut", "intersect", "new_body")
TYPES = ("angle", "full")
DIRECTIONS = ("one_side", "two_sides", "symmetric")

DEFAULTS = {
    "operation": "join",
    "type": "angle",
    "direction": "one_side",
    "angle": 360.0,
    "angle2": 90.0,
}

META = "SciForgeRevolve"
ROLE = "SciForgeRole"
FP_TYPE = "PartDesign::FeaturePython"
LINE_TYPES = ("App::Line", "PartDesign::Line", "Part::DatumLine")
SKETCH_AXES = ("H_Axis", "V_Axis", "N_Axis")
X = App.Vector(1, 0, 0)
Y = App.Vector(0, 1, 0)
Z = App.Vector(0, 0, 1)
TOL = 1e-7


class RevolveError(ValueError):
    """The revolve cannot be built as asked; the message says why and what to do."""


# -- small geometry helpers ---------------------------------------------------------------
owner_body = extrude.owner_body
is_sketch = extrude.is_sketch
normalize = extrude.normalize
key = extrude.key


def _body_placement(obj):
    body = owner_body(obj)
    if body is None or body is obj:
        return App.Placement()
    return body.getGlobalPlacement()


def to_global(shape, obj):
    """A shape of `obj` (in its body's coordinates) in global coordinates."""
    placement = _body_placement(obj)
    if placement.isIdentity():
        return shape
    shape = shape.copy()
    shape.Placement = placement.multiply(shape.Placement)
    return shape


def global_faces(profiles):
    return extrude.global_faces(profiles)


def local_faces(obj, sub):
    return extrude.local_faces(obj, sub)


def _unit(vec):
    vec = App.Vector(vec)
    if vec.Length < 1e-12:
        raise RevolveError("The axis has no direction. Pick another line.")
    vec.normalize()
    return vec


# -- axes -------------------------------------------------------------------------------------
def construction_lines(sketch):
    """[("AxisN", start, end)] of a sketch's construction lines, in sketch coordinates.
    FreeCAD numbers construction line segments in geometry order ("Axis0" is the first)."""
    found = []
    count = 0
    for i, geo in enumerate(sketch.Geometry):
        try:
            construction = sketch.getConstruction(i)
        except Exception:
            construction = False
        if construction and geo.TypeId == "Part::GeomLineSegment":
            found.append(("Axis%d" % count, App.Vector(geo.StartPoint), App.Vector(geo.EndPoint)))
            count += 1
    return found


def _sketch_axis_points(sketch, sub):
    """(start, end) of a sketch axis in sketch coordinates."""
    if sub == "H_Axis":
        return App.Vector(0, 0, 0), X
    if sub == "V_Axis":
        return App.Vector(0, 0, 0), Y
    if sub == "N_Axis":
        return App.Vector(0, 0, 0), Z
    for name, start, end in construction_lines(sketch):
        if name == sub:
            return start, end
    raise RevolveError(
        "The construction line used as the axis is gone from %s. Pick the axis again."
        % sketch.Label
    )


def is_line_edge(edge):
    try:
        return edge.Curve.TypeId in ("Part::GeomLine", "Part::GeomLineSegment")
    except Exception:
        return False


def axis_from_pick(obj, sub):
    """The axis reference for something clicked, or raise RevolveError saying why not."""
    if obj is None:
        raise RevolveError("Pick a line, an edge or an axis.")
    if obj.TypeId in LINE_TYPES:
        return (obj, "")
    if is_sketch(obj) and (sub in SKETCH_AXES or sub.startswith("Axis")):
        return (obj, sub)
    if sub.startswith("Edge"):
        try:
            edge = obj.Shape.getElement(sub)
        except Exception:
            raise RevolveError("That edge no longer exists. Pick the axis again.")
        if not is_line_edge(edge):
            raise RevolveError("The axis must be straight. Pick a straight line or edge.")
        return (obj, sub)
    raise RevolveError("Pick a line, a straight edge or an axis to revolve about.")


def axis_line(ref, local=False):
    """(point, unit direction) of an axis reference: global coordinates, or the
    coordinates of the reference's own body with local=True. The direction is the one
    FreeCAD uses for that reference, so Reversed=False turns right-handed about it."""
    obj, sub = ref
    if obj is None:
        raise RevolveError("Pick an axis.")
    if obj.TypeId in LINE_TYPES:
        placement = obj.getGlobalPlacement()
        if local:
            placement = _body_placement(obj).inverse().multiply(placement)
        base_dir = X if obj.TypeId == "App::Line" else Z
        return App.Vector(placement.Base), _unit(placement.Rotation.multVec(base_dir))
    if is_sketch(obj) and (sub in SKETCH_AXES or sub.startswith("Axis")):
        start, end = _sketch_axis_points(obj, sub)
        placement = obj.Placement if local else obj.getGlobalPlacement()
        a, b = placement.multVec(start), placement.multVec(end)
        return a, _unit(b - a)
    if sub.startswith("Edge"):
        try:
            edge = obj.Shape.getElement(sub)
        except Exception:
            raise RevolveError("The axis edge no longer exists. Pick the axis again.")
        if not is_line_edge(edge):
            raise RevolveError("The axis must be straight. Pick a straight line or edge.")
        point = App.Vector(edge.Curve.Location)
        direction = App.Vector(edge.Curve.Direction)
        if not local:
            placement = _body_placement(obj)
            point = placement.multVec(point)
            direction = placement.Rotation.multVec(direction)
        return point, _unit(direction)
    raise RevolveError("Pick a line, a straight edge or an axis to revolve about.")


def axis_label(ref):
    """The axis in words, for the dialog."""
    if not ref:
        return ""
    obj, sub = ref
    if obj.TypeId == "App::Line":
        role = getattr(obj, "Role", "") or obj.Name
        return role.replace("_Axis", " Axis")
    if obj.TypeId in LINE_TYPES:
        return obj.Label
    if is_sketch(obj):
        if sub.startswith("Axis"):
            return "Construction line of %s" % obj.Label
        if sub in SKETCH_AXES:
            return "%s axis of %s" % (sub[0], obj.Label)
        return "Line of %s" % obj.Label
    if sub.startswith("Edge"):
        return "Edge of %s" % obj.Label
    return obj.Label


def origin_axes(body):
    """{"X": line, "Y": line, "Z": line} of a body's origin."""
    found = {}
    if body is None:
        return found
    try:
        features = body.Origin.OriginFeatures
    except Exception:
        return found
    for feature in features:
        role = getattr(feature, "Role", "") or feature.Name
        for name in ("X", "Y", "Z"):
            if role.startswith(name + "_Axis"):
                found[name] = feature
    return found


def overlay_lines(body, sketches, half_length):
    """Lines the Revolve dialog draws so they can be clicked as the axis, global:
    [(ref, kind, start, end)], kind "X"/"Y"/"Z" (origin axes, `half_length` both ways)
    or "construction" (a sketch's construction line, its own length)."""
    found = []
    for name, line in sorted(origin_axes(body).items()):
        point, direction = axis_line((line, ""))
        found.append(
            ((line, ""), name, point - direction * half_length, point + direction * half_length)
        )
    seen = set()
    for sketch in sketches:
        if sketch is None or sketch.Name in seen:
            continue
        seen.add(sketch.Name)
        placement = sketch.getGlobalPlacement()
        for sub, start, end in construction_lines(sketch):
            a, b = placement.multVec(start), placement.multVec(end)
            if (b - a).Length > 1e-9:
                found.append(((sketch, sub), "construction", a, b))
    return found


# -- profiles ----------------------------------------------------------------------------------
def check_profiles(profiles):
    """Raise RevolveError unless every profile is a flat closed area."""
    profiles = normalize(profiles)
    if not profiles:
        raise RevolveError("Select a profile: click inside a sketch area or on a flat face.")
    for obj, sub in profiles:
        faces = local_faces(obj, sub)
        if not faces:
            raise RevolveError(
                "%s has no closed area to revolve. Close the sketch's outline." % obj.Label
            )
        for face in faces:
            if face.Surface.TypeId != "Part::GeomPlane":
                raise RevolveError("Only flat faces can be revolved. Pick a flat face or a sketch.")
    return profiles


def check_axis(profiles, axis):
    """Raise RevolveError if the axis cannot carry these profiles (missing, through the
    profile, or square to its plane: FreeCAD fails on those)."""
    if not axis or axis[0] is None:
        raise RevolveError("Select an axis: click a line, a straight edge or an origin axis.")
    point, direction = axis_line(axis)
    for face in global_faces(profiles):
        normal = extrude.face_normal(face)
        if abs(abs(normal.dot(direction)) - 1.0) < 1e-9:
            raise RevolveError(
                "The axis is square to the profile. Pick an axis that lies in the profile's plane."
            )
        if axis_crosses(face, point, direction):
            raise RevolveError(
                "The axis goes through the profile. Pick a line along the profile's edge or "
                "outside it."
            )


def axis_crosses(face, point, direction):
    """True if the infinite axis line passes through the inside of a flat face (the
    profile would sweep through itself)."""
    import Part

    try:
        box = face.BoundBox
        reach = box.DiagonalLength + (box.Center - point).Length + 10.0
        line = Part.LineSegment(point - direction * reach, point + direction * reach).toShape()
        common = face.common(line)
        normal = extrude.face_normal(face)
        side = direction.cross(normal)
        if side.Length < 1e-9:
            return False
        side.normalize()
        eps = max(1e-4, box.DiagonalLength * 1e-5)
        samples = []
        for edge in common.Edges:
            if edge.Length > 1e-6:
                samples += [
                    edge.valueAt(edge.FirstParameter + edge.Length * t) for t in (0.25, 0.5, 0.75)
                ]
        for vertex in common.Vertexes:
            samples.append(vertex.Point)
        for p in samples:
            a, b = p + side * eps, p - side * eps
            if face.isInside(a, 1e-9, True) and face.isInside(b, 1e-9, True):
                return True
    except Exception:
        return False
    return False


# -- options ----------------------------------------------------------------------------------
def options_with_defaults(options):
    merged = dict(DEFAULTS)
    merged.update({k: v for k, v in (options or {}).items() if v is not None})
    if merged["operation"] not in OPERATIONS:
        raise RevolveError("unknown operation %r" % merged["operation"])
    if merged["type"] not in TYPES:
        raise RevolveError("unknown type %r" % merged["type"])
    if merged["direction"] not in DIRECTIONS:
        raise RevolveError("unknown direction %r" % merged["direction"])
    merged["angle"] = float(merged["angle"])
    merged["angle2"] = float(merged["angle2"])
    return merged


def check_options(options):
    """Raise RevolveError for angles Fusion's dialog would refuse."""
    if options["type"] == "full":
        return
    a1, a2 = options["angle"], options["angle2"]
    if abs(a1) < 1e-6:
        raise RevolveError("The angle must not be zero.")
    if abs(a1) > 360.0 + 1e-9:
        raise RevolveError("The angle can be at most 360 degrees.")
    if options["direction"] == "symmetric" and abs(a1) > 180.0 + 1e-9:
        raise RevolveError(
            "A symmetric revolve turns the angle each way: at most 180 degrees per side."
        )
    if options["direction"] == "two_sides":
        if a2 < 1e-6:
            raise RevolveError("The angle of side two must be more than zero.")
        if abs(a1) + a2 > 360.0 + 1e-9:
            raise RevolveError(
                "The two angles add up to more than 360 degrees. Make one of them smaller."
            )


def sweep(options):
    """(start, sweep) in degrees about the axis: the profile is first turned by start,
    then swept by sweep (signed, right-handed about the axis direction)."""
    options = options_with_defaults(options)
    a1, a2 = options["angle"], options["angle2"]
    if options["type"] == "full":
        return 0.0, 360.0
    if options["direction"] == "symmetric":
        return -abs(a1), 2.0 * abs(a1)
    if options["direction"] == "two_sides":
        sign = -1.0 if a1 < 0 else 1.0
        return -sign * a2, sign * (abs(a1) + a2)
    return 0.0, a1


def revolve_faces(faces, point, direction, options):
    """The solid the faces sweep about the axis (all in one coordinate system)."""
    start, angle = sweep(options)
    solids = []
    for face in faces:
        face = face.copy()
        if abs(start) > 1e-12:
            face.rotate(point, direction, start)
        swept = face.revolve(point, direction, angle)
        solids += list(swept.Solids)
    if not solids:
        raise RevolveError("The profile does not make a solid when revolved.")
    tool = solids[0]
    if len(solids) > 1:
        tool = solids[0].multiFuse(solids[1:])
    return tool


def tool_shape(profiles, axis, options):
    """The revolved solid (global coordinates), as the preview would add or remove it."""
    point, direction = axis_line(axis)
    return revolve_faces(global_faces(profiles), point, direction, options)


def auto_operation(base_shape, profiles, axis, options):
    """Fusion: revolving into material becomes a cut, out of it a join (a new body when
    there is no solid yet). The revolve goes "into material" when more of its volume lies
    inside the part than outside (a groove drawn inside a shaft, a face turned into the
    part). base_shape is global."""
    if base_shape is None or base_shape.isNull() or not base_shape.Solids:
        return "new_body"
    try:
        tool = tool_shape(profiles, axis, options)
        inside = base_shape.common(tool).Volume
        outside = tool.Volume - inside
    except Exception:
        return "join"
    return "cut" if inside > outside + 1e-6 * max(1.0, tool.Volume) else "join"


def feature_type(operation):
    if operation == "cut":
        return "PartDesign::Groove"
    if operation == "intersect":
        return FP_TYPE
    return "PartDesign::Revolution"


# -- meta ---------------------------------------------------------------------------------------
def _ref_json(ref):
    if not ref or ref[0] is None:
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
        feature.addProperty("App::PropertyString", META, "SciForge", "Fusion revolve options", 0)
        feature.setEditorMode(META, 2)  # hidden
    text = json.dumps(meta, sort_keys=True)
    if getattr(feature, META) != text:
        setattr(feature, META, text)


def _mark(obj, role):
    if ROLE not in obj.PropertiesList:
        obj.addProperty("App::PropertyString", ROLE, "SciForge", "What SciForge made this for", 0)
        obj.setEditorMode(ROLE, 2)
    setattr(obj, ROLE, role)
    # Not a step of its own: the timeline shows only the revolve.
    if "SciForgeTimeline" not in obj.PropertiesList:
        obj.addProperty("App::PropertyBool", "SciForgeTimeline", "SciForge", "", 4)
    obj.SciForgeTimeline = False


def is_helper(obj):
    return getattr(obj, ROLE, "") in ("RevolveProfile", "RevolveAxis")


def is_intersect(obj):
    return (
        obj is not None and getattr(obj, "SciForgeType", "") == "Revolve" and obj.TypeId == FP_TYPE
    )


def is_revolve(obj):
    return obj is not None and (
        obj.TypeId in ("PartDesign::Revolution", "PartDesign::Groove") or is_intersect(obj)
    )


# -- the intersect feature ---------------------------------------------------------------------
class RevolveFeature:
    """Revolve with operation Intersect: the body keeps what lies inside the revolve.
    Saved documents store "sciforge.revolve.RevolveFeature": keep the name stable."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc, group="Revolve"):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, group, doc)
                return True
            return False

        add("App::PropertyLinkSubList", "Profiles", "The profiles that are revolved")
        add("App::PropertyLinkSub", "ReferenceAxis", "The axis the profiles turn about")
        if add("App::PropertyEnumeration", "Type", "One angle, or one angle per side"):
            obj.Type = ["Angle", "TwoAngles"]
        if add("App::PropertyAngle", "Angle", "Angle (side one)"):
            obj.Angle = 360.0
        add("App::PropertyAngle", "Angle2", "Angle of side two")
        add("App::PropertyBool", "Midplane", "Symmetric to the profile plane")
        add("App::PropertyBool", "Reversed", "Turn the other way")
        if add("App::PropertyBool", "Refine", "Merge coplanar faces, like Fusion"):
            obj.Refine = True
        if "SciForgeType" not in obj.PropertiesList:
            obj.addProperty("App::PropertyString", "SciForgeType", "Base", "", 4)
            obj.SciForgeType = "Revolve"

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        base = obj.BaseFeature
        if base is None or base.Shape.isNull() or not base.Shape.Solids:
            raise RevolveError("Intersect needs a solid before it in the timeline.")
        faces = []
        for linked, subs in obj.Profiles:
            for sub in subs or [""]:
                faces += local_faces(linked, sub)
        if not faces:
            raise RevolveError("Select a profile to revolve.")
        link = obj.ReferenceAxis
        if not link or link[0] is None:
            raise RevolveError("Select an axis to revolve about.")
        ref = (link[0], (link[1] or [""])[0])
        point, direction = axis_line(ref, local=True)
        options = _fp_options(obj)
        tool = revolve_faces(faces, point, direction, options)
        result = base.Shape.common(tool)
        if obj.Refine:
            result = result.removeSplitter()
        if result.isNull() or not result.Solids or result.Volume < TOL:
            raise RevolveError(
                "The revolve does not overlap the body, so Intersect would leave nothing."
            )
        if len(result.Solids) > 1:
            raise RevolveError(
                "Intersect would leave %d separate pieces; a body holds one solid. "
                "Change the profile or the angle." % len(result.Solids)
            )
        obj.Shape = result.Solids[0]

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def _fp_options(obj):
    """Dialog options from the intersect feature's own properties (for execute)."""
    angle = obj.Angle.Value
    if obj.Type == "TwoAngles":
        return {
            "type": "angle",
            "direction": "two_sides",
            "angle": -angle if obj.Reversed else angle,
            "angle2": obj.Angle2.Value,
        }
    if obj.Midplane:
        return {"type": "angle", "direction": "symmetric", "angle": angle / 2.0}
    return {"type": "angle", "direction": "one_side", "angle": -angle if obj.Reversed else angle}


def _attach_view_provider(obj):
    if not App.GuiUp:
        return
    try:
        from .revolve_ui import ViewProviderRevolve

        ViewProviderRevolve(obj.ViewObject)
    except Exception:
        pass


# -- building ---------------------------------------------------------------------------------
def _has_solid(body, before=None):
    tip = before.BaseFeature if before is not None else body.Tip
    return tip is not None and not tip.Shape.isNull() and bool(tip.Shape.Solids)


def _insert(body, type_id, name, before=None):
    """New feature in `body`: at the timeline marker, or just before `before`."""
    if before is not None:
        obj = body.Document.addObject(type_id, name)
        body.insertObject(obj, before, False)
        return obj
    return body.newObject(type_id, name)


def _hide(obj):
    try:
        obj.Visibility = False
    except Exception:
        pass
    if App.GuiUp:
        try:
            obj.ViewObject.Visibility = False
            if "ShowInTree" in obj.ViewObject.PropertiesList:
                obj.ViewObject.ShowInTree = False
        except Exception:
            pass


def _binder(body, feature, sources, existing=None, role="RevolveProfile", label="profile"):
    """A hidden SubShapeBinder in `body`, just before `feature`, copying `sources`."""
    binder = existing
    if binder is None or binder.TypeId != "PartDesign::SubShapeBinder":
        binder = body.Document.addObject("PartDesign::SubShapeBinder", "RevolveRef")
        body.insertObject(binder, feature, False)
        _mark(binder, role)
    binder.Label = "%s %s" % (feature.Label, label)
    grouped, order = {}, []
    for obj, sub in sources:
        if obj.Name not in grouped:
            grouped[obj.Name] = (obj, [])
            order.append(obj.Name)
        if sub:
            grouped[obj.Name][1].append(sub)
    support = [(grouped[n][0], tuple(grouped[n][1])) for n in order]
    if list(binder.Support) != support:
        binder.Support = support
    _hide(binder)
    return binder


class AxisLink:
    """A hidden line in one body that follows an axis of another body: a sketch's
    construction line or own axis, a construction axis, an origin axis. FreeCAD lets a
    feature link only to things in its own body, and a SubShapeBinder can only copy what
    has a shape (construction lines do not), so this reads the axis through a global link
    every recompute: edit the construction line and the revolve follows.
    Saved documents store "sciforge.revolve.AxisLink": keep the name stable."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        if "Source" not in obj.PropertiesList:
            obj.addProperty("App::PropertyLinkGlobal", "Source", "Axis", "The axis' object")
        if "SourceSub" not in obj.PropertiesList:
            obj.addProperty("App::PropertyString", "SourceSub", "Axis", "Which axis of it")

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        import Part

        if obj.Source is None:
            raise RevolveError("The axis this revolve turns about is gone. Pick it again.")
        ref = (obj.Source, obj.SourceSub)
        point, direction = axis_line(ref)
        length = 100.0
        if is_sketch(obj.Source) and obj.SourceSub.startswith("Axis"):
            start, end = _sketch_axis_points(obj.Source, obj.SourceSub)
            length = max((end - start).Length, 1e-3)
        body = owner_body(obj)
        inverse = body.getGlobalPlacement().inverse() if body is not None else App.Placement()
        a = inverse.multVec(point)
        d = inverse.Rotation.multVec(direction)
        obj.Shape = Part.LineSegment(a, a + d * length).toShape()

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def _axis_link(body, feature, axis, existing=None):
    """A hidden AxisLink in `body`, just before `feature`, following `axis`."""
    link = existing
    if link is None or not isinstance(getattr(link, "Proxy", None), AxisLink):
        link = body.Document.addObject("Part::Part2DObjectPython", "RevolveAxis")
        AxisLink(link)
        body.insertObject(link, feature, False)
        _mark(link, "RevolveAxis")
    link.Label = "%s axis" % feature.Label
    if link.Source is not axis[0]:
        link.Source = axis[0]
    if link.SourceSub != axis[1]:
        link.SourceSub = axis[1]
    _hide(link)
    return link


def _local_axis(body, feature, axis, helpers, old):
    """An axis reference FreeCAD may link from `feature` (inside `body`); otherwise a
    hidden helper (re-used from the last update when there is one)."""
    obj, sub = axis
    if owner_body(obj) is body:
        return (obj, sub)
    if obj.TypeId == "App::Line":
        # The same origin axis of this body when both bodies sit at the same place.
        mine = origin_axes(body)
        role = (getattr(obj, "Role", "") or obj.Name)[:1]
        if role in mine and _body_placement(obj).isSame(body.getGlobalPlacement(), 1e-9):
            return (mine[role], "")
    existing = old.pop(0) if old else None
    if sub.startswith("Edge"):
        if existing is not None and existing.TypeId != "PartDesign::SubShapeBinder":
            _delete(existing)
            existing = None
        binder = _binder(body, feature, [axis], existing, role="RevolveAxis", label="axis")
        helpers.append(binder)
        return (binder, "Edge1")
    if existing is not None and not isinstance(getattr(existing, "Proxy", None), AxisLink):
        _delete(existing)
        existing = None
    link = _axis_link(body, feature, axis, existing)
    helpers.append(link)
    return (link, "Edge1")


def _new_body(src_body):
    doc = src_body.Document
    body = doc.addObject("PartDesign::Body", "Body")
    container = src_body.getParentGeoFeatureGroup()
    if container is not None and hasattr(container, "addObject"):
        container.addObject(body)
    count = len([o for o in doc.Objects if o.TypeId == "PartDesign::Body"])
    body.Label = "Body%d" % count
    return body


def _source_body(profiles):
    body = owner_body(profiles[0][0])
    if body is None:
        raise RevolveError("The profile must belong to a body. Use Create Sketch first.")
    return body


def _structure(feature, profiles, options):
    """(target body or None for 'make a new one', feature type, source body)."""
    src = _source_body(profiles)
    meta = load_meta(feature) if feature is not None else {}
    created = None
    if feature is not None and meta.get("created_body"):
        created = feature.Document.getObject(meta["created_body"])
    if options["operation"] == "new_body":
        if created is not None:
            target = created
        elif feature is not None and owner_body(feature) is src and not _has_solid(src, feature):
            target = src  # the first solid of a body already is a new body
        elif feature is None and not _has_solid(src):
            target = src
        else:
            target = None
    else:
        target = src
    return target, feature_type(options["operation"]), src


def build(profiles, axis, options, name="Revolve", feature=None, hide=True):
    """Create the revolve, or rebuild `feature` with new profiles/axis/options.
    Returns the feature (a different object when its kind had to change). hide=False
    keeps the profile sketches visible (the dialog hides them on OK, like Fusion)."""
    profiles = check_profiles(profiles)
    options = options_with_defaults(options)
    check_options(options)
    check_axis(profiles, axis)
    target, type_id, src = _structure(feature, profiles, options)
    if feature is not None:
        same = feature.TypeId == type_id and (type_id != FP_TYPE or is_intersect(feature))
        if owner_body(feature) is target and same:
            _update(feature, target, profiles, axis, options, hide)
            return feature
        blocking = [o for o in extrude.dependents(feature) if not is_helper(o)]
        if blocking:
            raise RevolveError(
                "%s is used by %s, so its operation cannot change here. Make a new revolve "
                "instead." % (feature.Label, ", ".join(o.Label for o in blocking))
            )
    old_meta = load_meta(feature) if feature is not None else {}
    created = None
    if target is None:
        target = created = _new_body(src)
    elif old_meta.get("created_body") == target.Name:
        created = target
    before = feature if (feature is not None and owner_body(feature) is target) else None
    was_tip = before is not None and target.Tip is before
    new = _insert(target, type_id, name, before)
    if type_id == FP_TYPE:
        RevolveFeature(new)
        _attach_view_provider(new)
    _save_meta(new, {"created_body": created.Name if created is not None else None})
    try:
        _update(new, target, profiles, axis, options, hide)
    except Exception:
        _remove(new, keep_body=created is None or before is not None)
        raise
    if feature is not None:
        label = feature.Label
        old_body = owner_body(feature)
        _remove(feature, keep_body=old_body is target)
        new.Label = label
        if old_body is not None and old_body is not target:
            _show_tip(old_body)
    if before is None or was_tip:
        target.Tip = new
    return new


def _needs_binder(body, profiles):
    if len({obj.Name for obj, _ in profiles}) != 1:
        return True
    return owner_body(profiles[0][0]) is not body


def _direct_profile(profiles):
    obj = profiles[0][0]
    subs = [sub for _, sub in profiles]
    if "" in subs:
        return obj
    return (obj, subs)


def _update(feature, body, profiles, axis, options, hide=True):
    meta = load_meta(feature)
    doc = feature.Document
    old = [doc.getObject(n) for n in meta.get("helpers", [])]
    old = [h for h in old if h is not None]
    old_names = [h.Name for h in old]
    old_profile = [h for h in old if getattr(h, ROLE, "") == "RevolveProfile"]
    old_axis = [h for h in old if getattr(h, ROLE, "") == "RevolveAxis"]
    helpers = []
    if _needs_binder(body, profiles):
        existing = old_profile[0] if old_profile else None
        binder = _binder(body, feature, profiles, existing)
        helpers.append(binder)
        link = binder
        fp_profiles = [(binder, "")]
    else:
        link = _direct_profile(profiles)
        fp_profiles = list(profiles)
    axis_link = _local_axis(body, feature, axis, helpers, old_axis)
    keep = {h.Name for h in helpers}
    for name in old_names:
        helper = doc.getObject(name)
        if name not in keep and helper is not None:
            _delete(helper)
    if is_intersect(feature):
        feature.Profiles = [(obj, [sub]) for obj, sub in fp_profiles]
    else:
        feature.Profile = link
        if hasattr(feature, "AllowMultiFace"):
            feature.AllowMultiFace = True
    feature.ReferenceAxis = (axis_link[0], [axis_link[1]])
    _apply(feature, options)
    meta.update(
        {
            "v": 1,
            "operation": options["operation"],
            "type": options["type"],
            "direction": options["direction"],
            "angle": float(options["angle"]),
            "angle2": float(options["angle2"]),
            "profiles": [[obj.Name, sub] for obj, sub in profiles],
            "axis": _ref_json(axis),
            "helpers": [h.Name for h in helpers],
        }
    )
    _save_meta(feature, meta)
    if hide:
        hide_sketches(profiles)


def _apply(feature, options):
    """Type / angles / direction onto a Revolution, Groove or intersect feature."""
    a1, a2 = float(options["angle"]), float(options["angle2"])
    if options["type"] == "full":
        kind, angle, angle2, mid, rev = "Angle", 360.0, 0.0, False, False
    elif options["direction"] == "symmetric":
        kind, angle, angle2, mid, rev = "Angle", min(2.0 * abs(a1), 360.0), 0.0, True, False
    elif options["direction"] == "two_sides":
        kind, angle, angle2, mid, rev = "TwoAngles", abs(a1), abs(a2), False, a1 < 0
    else:
        kind, angle, angle2, mid, rev = "Angle", abs(a1), 0.0, False, a1 < 0
    if feature.Midplane != mid:
        feature.Midplane = mid
    if feature.Type != kind:
        feature.Type = kind
    feature.Angle = angle
    feature.Angle2 = angle2
    if feature.Reversed != rev:
        feature.Reversed = rev
    if hasattr(feature, "Refine"):
        feature.Refine = True


def hide_sketches(profiles):
    """Fusion hides a sketch once a feature uses it."""
    if not App.GuiUp:
        return
    for obj, _ in profiles:
        if is_sketch(obj):
            try:
                obj.ViewObject.Visibility = False
            except Exception:
                pass


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


def _remove(feature, keep_body=True):
    """Delete a revolve with its helpers (and the body it created, when asked)."""
    meta = load_meta(feature)
    doc = feature.Document
    body = owner_body(feature)
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


def remove(feature):
    body = owner_body(feature)
    _remove(feature, keep_body=False)
    _show_tip(body)


def _show_tip(body):
    """Show the body's solid again after its last feature went away: FreeCAD hid the
    feature before it when that one was added, and only shows it again when the
    feature is deleted with its own command."""
    if not App.GuiUp or body is None:
        return
    try:
        if body.Document.getObject(body.Name) is None:
            return
        tip = body.Tip
        if tip is not None and tip.ViewObject is not None and not tip.ViewObject.Visibility:
            tip.ViewObject.Visibility = True
    except Exception:
        pass


def make(profiles, axis, options, name="Revolve"):
    """New revolve with Fusion-style options (see the module text for the forms)."""
    return build(normalize(profiles), axis, options, name)


def update(feature, profiles=None, axis=None, options=None):
    """Rebuild an existing revolve; what is not given stays as it is."""
    old_profiles, old_axis, old_options = read(feature)
    merged = dict(old_options)
    merged.update(options or {})
    return build(
        normalize(profiles) if profiles is not None else old_profiles,
        axis if axis is not None else old_axis,
        merged,
        feature=feature,
    )


# -- reading back ------------------------------------------------------------------------------
def profiles_of(feature):
    """The profiles of an existing revolve, as picked (binders resolved)."""
    meta = load_meta(feature)
    doc = feature.Document
    found = []
    for name, sub in meta.get("profiles", []):
        obj = doc.getObject(name)
        if obj is not None:
            found.append((obj, sub))
    if found:
        return found
    if is_intersect(feature):
        links = [(obj, (subs or [""])[0]) for obj, subs in feature.Profiles]
    else:
        value = feature.Profile
        obj = value[0] if isinstance(value, tuple) else value
        subs = list(value[1]) if isinstance(value, tuple) and len(value) > 1 else []
        subs = [s for s in subs if s]
        if obj is None:
            return []
        links = [(obj, s) for s in subs] if subs else [(obj, "")]
    for obj, sub in links:
        if getattr(obj, ROLE, "") == "RevolveProfile" or obj.TypeId == "PartDesign::SubShapeBinder":
            for linked, linked_subs in obj.Support:
                for s in linked_subs or [""]:
                    found.append((linked, s))
        else:
            found.append((obj, sub))
    return found


def axis_of(feature):
    """The axis of an existing revolve, as picked (helpers resolved), or None."""
    meta = load_meta(feature)
    ref = _ref_load(feature.Document, meta.get("axis"))
    if ref is not None:
        return ref
    link = feature.ReferenceAxis
    if not link or link[0] is None:
        return None
    obj, sub = link[0], (link[1] or [""])[0]
    if isinstance(getattr(obj, "Proxy", None), AxisLink) and obj.Source is not None:
        return (obj.Source, obj.SourceSub)
    if obj.TypeId == "PartDesign::SubShapeBinder" and obj.Support:
        linked, subs = obj.Support[0]
        return (linked, (subs or [""])[0])
    return (obj, sub)


def read(feature):
    """(profiles, axis, options) of an existing revolve, the way the dialog shows them."""
    meta = load_meta(feature)
    options = dict(DEFAULTS)
    if is_intersect(feature):
        options["operation"] = "intersect"
    elif feature.TypeId == "PartDesign::Groove":
        options["operation"] = "cut"
    else:
        options["operation"] = "new_body" if meta.get("operation") == "new_body" else "join"
    angle = feature.Angle.Value
    sign = -1.0 if feature.Reversed else 1.0
    if feature.Type == "TwoAngles":
        options["direction"] = "two_sides"
        options["angle"] = sign * angle
        options["angle2"] = feature.Angle2.Value
    elif feature.Midplane:
        options["direction"] = "symmetric"
        options["angle"] = angle / 2.0
    else:
        options["direction"] = "one_side"
        options["angle"] = sign * angle
    full = meta.get("type") == "full" if "type" in meta else abs(angle - 360.0) < 1e-9
    if full and options["direction"] == "one_side":
        options["type"] = "full"
        options["direction"] = meta.get("direction", "one_side")
        options["angle"] = float(meta.get("angle", 360.0))
    if options["direction"] != "two_sides" and "angle2" in meta:
        options["angle2"] = float(meta["angle2"])
    return profiles_of(feature), axis_of(feature), options
