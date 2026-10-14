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
  type       angle | to | full     (full = 360 degrees, no direction; to = as far as the
             object in "to": a plane or flat face that contains the axis, or a point)
  to         (object, sub-element) the revolve goes to (type "to"): an origin or
             construction plane, a flat face of a body, a vertex, a construction point or
             a straight edge; it stops at the half-plane through the axis that the object
             marks, turning the shorter way (and follows the object when it moves)
  direction  one_side | two_sides | symmetric
  angle      degrees. One side: signed, a negative angle turns the other way.
             Symmetric: the angle on each side (the whole revolve is twice that, like
             Fusion's symmetric revolve). Two sides: side one (its sign picks the side).
  angle2     degrees of side two (two sides), turning the other way
  expressions {"angle": formula, "angle2": formula}: values typed as a parameter or a
             formula ("turn", "turn / 2 + 10"); they become expressions on the feature, so
             the revolve follows the parameter (Fusion takes formulas in every value field)
  bodies     Fusion's Objects To Cut: the bodies a Join, Cut or Intersect acts on (a list,
             "auto" = every body the revolve passes through, None = an existing revolve
             keeps its list; a new one acts on the profile's body only). One step: the
             revolve is the lead in one of them, hidden follower steps change the others
             (extrude_bodies.py, the same machinery as Extrude's)

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

OPERATIONS = ("join", "cut", "intersect", "new_body", "new_component")
TYPES = ("angle", "to", "full")
DIRECTIONS = ("one_side", "two_sides", "symmetric")

DEFAULTS = {
    "operation": "join",
    "type": "angle",
    "direction": "one_side",
    "angle": 360.0,
    "angle2": 90.0,
    "to": None,
    "bodies": None,
}

META = "SciForgeRevolve"
ROLE = "SciForgeRole"
FP_TYPE = "PartDesign::FeaturePython"
LINE_TYPES = ("App::Line", "PartDesign::Line", "Part::DatumLine")
PLANE_TYPES = ("App::Plane", "PartDesign::Plane", "Part::DatumPlane")
POINT_TYPES = ("PartDesign::Point", "Part::DatumPoint")
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


def to_label(target):
    """The object a Type "To" revolve goes to, in words, for the dialog."""
    if not target or target[0] is None:
        return ""
    obj, sub = target
    if obj.TypeId == "App::Plane":
        role = getattr(obj, "Role", "") or obj.Name
        return role.replace("_Plane", " Plane")
    if not sub:
        return obj.Label
    if is_sketch(obj):
        return ("Line of %s" if sub.startswith("Edge") else "Point of %s") % obj.Label
    # A face, edge or corner of the part: named after its body (what the browser shows),
    # not after the step that happened to make it.
    body = owner_body(obj)
    name = body.Label if body is not None else obj.Label
    if sub.startswith("Vertex"):
        return "Corner of %s" % name
    if sub.startswith("Edge"):
        return "Edge of %s" % name
    return "Face of %s" % name


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
    merged["expressions"] = {
        k: v for k, v in dict(merged.get("expressions") or {}).items() if v and k in FORMULAS
    }
    return merged


def check_options(options):
    """Raise RevolveError for angles Fusion's dialog would refuse."""
    if options["type"] == "full":
        return
    if options["type"] == "to":
        if not options.get("to") or options["to"][0] is None:
            raise RevolveError(
                "Select the object to revolve to: a plane or flat face through the axis, or a "
                "point."
            )
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
    return revolve_faces(
        global_faces(profiles), point, direction, resolved(profiles, axis, options)
    )


def resolved(profiles, axis, options):
    """Options with Type "To" turned into the angle it comes to (one side)."""
    options = options_with_defaults(options)
    if options["type"] != "to":
        return options
    angle = stop_angle(global_faces(profiles), axis, options["to"])
    return dict(options, type="angle", direction="one_side", angle=angle)


# -- Type "To": as far as an object --------------------------------------------------------------
def target_from_pick(obj, sub):
    """The "To" object for something clicked, or raise RevolveError saying why not."""
    if obj is None:
        raise RevolveError(TO_HINT)
    if obj.TypeId in PLANE_TYPES or obj.TypeId in POINT_TYPES:
        return (obj, "")
    if sub.startswith(("Face", "Edge", "Vertex")):
        try:
            element = obj.Shape.getElement(sub)
        except Exception:
            raise RevolveError("That no longer exists. Pick the object again.")
        if sub.startswith("Face") and element.Surface.TypeId != "Part::GeomPlane":
            raise RevolveError("Pick a flat face, a plane or a point to revolve to.")
        if sub.startswith("Edge") and not is_line_edge(element):
            raise RevolveError("Pick a straight edge, a flat face, a plane or a point.")
        return (obj, sub)
    raise RevolveError(TO_HINT)


TO_HINT = "Pick a plane or a flat face that contains the axis, or a point, to revolve to."


def _radial(p, point, direction, what):
    v = p - point
    v = v - direction * v.dot(direction)
    if v.Length < 1e-7:
        raise RevolveError("%s lies on the axis: pick another object to revolve to." % what)
    v.normalize()
    return v


def _plane_halves(normal, origin, point, direction, size):
    """The two directions (perpendicular to the axis) of a plane that contains the axis."""
    normal = App.Vector(normal)
    normal.normalize()
    if abs(normal.dot(direction)) > 1e-6 or abs((origin - point).dot(normal)) > 1e-6 * size:
        raise RevolveError(
            "The revolve can go to a plane or a flat face that contains the axis, or to a "
            "point. Pick another object."
        )
    w = normal.cross(direction)
    w.normalize()
    return [w, w * -1.0]


def target_directions(target, point, direction):
    """Unit directions (from the axis, square to it) of the half-planes the object marks:
    one for a point, an edge or a face, both halves for an endless plane."""
    obj, sub = target
    if obj is None:
        raise RevolveError(TO_HINT)
    if obj.TypeId in PLANE_TYPES:
        placement = obj.getGlobalPlacement()
        normal = placement.Rotation.multVec(Z)
        return _plane_halves(normal, App.Vector(placement.Base), point, direction, 100.0)
    if obj.TypeId in POINT_TYPES:
        where = App.Vector(obj.getGlobalPlacement().Base)
        return [_radial(where, point, direction, "The point")]
    try:
        element = to_global(obj.Shape.getElement(sub), obj)
    except Exception:
        raise RevolveError("The object to revolve to is gone. Pick it again.")
    if sub.startswith("Vertex"):
        return [_radial(element.Point, point, direction, "The point")]
    if sub.startswith("Edge"):
        middle = element.valueAt(element.FirstParameter + element.Length / 2.0)
        return [_radial(middle, point, direction, "The edge")]
    if element.Surface.TypeId != "Part::GeomPlane":
        raise RevolveError(TO_HINT)
    size = max(1.0, element.BoundBox.DiagonalLength)
    halves = _plane_halves(
        extrude.face_normal(element), element.Vertexes[0].Point, point, direction, size
    )
    inside = extrude.interior_point(element) - point
    return [w for w in halves if w.dot(inside) > 0][:1] or halves


def stop_angle(faces, axis, target):
    """Signed degrees from the profile to the object, the shorter way round."""
    import math

    point, direction = axis_line(axis)
    if not faces:
        raise RevolveError("Select a profile to revolve.")
    start = _radial(extrude.interior_point(faces[0]), point, direction, "The profile")
    best = None
    for w in target_directions(target, point, direction):
        angle = math.degrees(math.atan2(direction.dot(start.cross(w)), start.dot(w)))
        if abs(angle) < 1e-6:
            continue
        shorter = best is None or abs(angle) < abs(best) - 1e-9
        if shorter or (abs(abs(angle) - abs(best)) <= 1e-9 and angle > best):
            best = angle  # half a turn either way: the positive way, like the handle
    if best is None:
        raise RevolveError(
            "The object is where the profile already is. Pick one the revolve turns to."
        )
    return best


class RevolveTo:
    """A hidden helper that works out, on every recompute, how far a Type "To" revolve
    turns: from its profile to the object it goes to. The revolve's angle follows it (an
    expression), so moving the plane, the face or the corner moves the revolve's end too.
    A face, edge or corner of the part is remembered by where it is and found again when
    FreeCAD renames it (an edit before it can renumber them), like FaceLink.
    Saved documents store "sciforge.revolve.RevolveTo": keep the name stable."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc, flags=0):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, "To", doc, flags)
                if kind == "App::PropertyString":
                    obj.setEditorMode(name, 2)

        add("App::PropertyLinkGlobal", "Target", "The object the revolve goes to")
        add("App::PropertyString", "TargetSub", "Which part of it", 16)
        add("App::PropertyString", "TargetData", "Where that part is", 16)
        add("App::PropertyLinkGlobal", "AxisSource", "The axis' object")
        add("App::PropertyString", "AxisSub", "Which axis of it")
        add("App::PropertyLinkListGlobal", "Sources", "The profiles' objects")
        add("App::PropertyString", "SourceSubs", "The profiles turned")
        add("App::PropertyFloat", "Angle", "Signed degrees to the object", 16)

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        import Part

        faces = []
        for name, sub in json.loads(obj.SourceSubs or "[]"):
            linked = obj.Document.getObject(name)
            if linked is not None:
                faces += [to_global(f, linked) for f in local_faces(linked, sub)]
        if obj.AxisSource is None:
            raise RevolveError("The axis this revolve turns about is gone. Pick it again.")
        if obj.Target is None:
            raise RevolveError("The object this revolve goes to is gone. Pick it again.")
        axis = (obj.AxisSource, obj.AxisSub)
        sub = obj.TargetSub
        if sub:
            memory = json.loads(obj.TargetData or "{}")
            found = _refind_element(obj.Target.Shape, sub, memory)
            if found is None:
                raise RevolveError(
                    "The object this revolve goes to is gone from the part. Edit the revolve "
                    "and pick it again."
                )
            name, fresh = found
            if name != sub:
                obj.TargetSub = name
                sub = name
            text = json.dumps(fresh, sort_keys=True)
            if text != obj.TargetData:
                obj.TargetData = text
        angle = stop_angle(faces, axis, (obj.Target, sub))
        if abs(obj.Angle - angle) > 1e-12:
            obj.Angle = angle
        point, direction = axis_line(axis)
        body = owner_body(obj)
        inverse = body.getGlobalPlacement().inverse() if body is not None else App.Placement()
        a = inverse.multVec(point)
        d = inverse.Rotation.multVec(direction)
        obj.Shape = Part.LineSegment(a, a + d).toShape()

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def _element_memory(element, kind):
    """Where an element of a part is (its own body's coordinates), to find it again."""
    if kind == "Vertex":
        p = element.Point
        return {"kind": kind, "point": [p.x, p.y, p.z]}
    if kind == "Edge":
        p = element.valueAt(element.FirstParameter + element.Length / 2.0)
        return {"kind": kind, "point": [p.x, p.y, p.z], "length": element.Length}
    entry = _face_entry(_Named(""), "", element)
    entry["kind"] = kind
    return entry


def _refind_element(shape, sub, memory):
    """(name, fresh memory) of the remembered vertex / edge / face in `shape`, or None: the
    one still at the remembered place, else the one of that name (it moved with the part),
    else the nearest one of its kind."""
    kind = sub.lstrip("?").rstrip("0123456789")
    name = sub.lstrip("?")
    if kind not in ("Vertex", "Edge", "Face"):
        return None
    if kind == "Face" and memory.get("point"):
        found = _find_face(shape, dict(memory, sub=name, obj=""))
        if found is None:
            return None
        face, fresh = found
        return fresh["sub"], _element_memory(face, kind)
    items = shape.Vertexes if kind == "Vertex" else shape.Edges
    if not items:
        return None

    def where(item):
        if kind == "Vertex":
            return item.Point
        return item.valueAt(item.FirstParameter + item.Length / 2.0)

    size = max(1.0, shape.BoundBox.DiagonalLength)
    index = int(name[len(kind) :]) if name[len(kind) :].isdigit() else 0
    pick = None
    if memory.get("point"):
        old = _vec(memory["point"])
        same = [
            i for i, item in enumerate(items, start=1) if (where(item) - old).Length < 1e-7 * size
        ]
        if index in same:
            pick = index
        elif same:
            pick = same[0]
        elif 0 < index <= len(items):
            pick = index
        else:
            pick = min(range(1, len(items) + 1), key=lambda i: (where(items[i - 1]) - old).Length)
    elif 0 < index <= len(items):
        pick = index
    if pick is None:
        return None
    return "%s%d" % (kind, pick), _element_memory(items[pick - 1], kind)


def _to_link(body, feature, fp_profiles, axis, target, angle, existing=None):
    """A hidden RevolveTo in `body`, just before `feature`."""
    link = existing
    if link is None or not isinstance(getattr(link, "Proxy", None), RevolveTo):
        link = body.Document.addObject("Part::Part2DObjectPython", "RevolveTo")
        RevolveTo(link)
        body.insertObject(link, feature, False)
        _mark(link, "RevolveTo")
    link.Label = "%s to" % feature.Label
    obj, sub = target
    memory = ""
    if sub:
        kind = sub.rstrip("0123456789")
        try:
            memory = json.dumps(_element_memory(obj.Shape.getElement(sub), kind), sort_keys=True)
        except Exception:
            raise RevolveError("The object to revolve to is gone. Pick it again.")
    if link.Target is not obj:
        link.Target = obj
    if link.TargetSub != sub or link.TargetData != memory:
        link.TargetSub = sub
        link.TargetData = memory
        link.touch()
    if link.AxisSource is not axis[0]:
        link.AxisSource = axis[0]
    if link.AxisSub != axis[1]:
        link.AxisSub = axis[1]
    sources = []
    for source, _sub in fp_profiles:
        if source not in sources:
            sources.append(source)
    if list(link.Sources) != sources:
        link.Sources = sources
    subs = json.dumps([[source.Name, sub] for source, sub in fp_profiles])
    if link.SourceSubs != subs:
        link.SourceSubs = subs
    link.Angle = angle
    _hide(link)
    return link


def auto_operation(base_shape, profiles, axis, options):
    """Fusion: revolving into material becomes a cut, out of it a join, and a revolve that
    does not touch the part (or the first solid) a new body. The revolve goes "into
    material" when more of its volume lies inside the part than outside (a groove drawn
    inside a shaft, a face turned into the part). base_shape is global."""
    if base_shape is None or base_shape.isNull() or not base_shape.Solids:
        return "new_body"
    try:
        tool = tool_shape(profiles, axis, options)
        inside = base_shape.common(tool).Volume
        outside = tool.Volume - inside
        if inside < 1e-9 and base_shape.distToShape(tool)[0] > 1e-6:
            return "new_body"  # Fusion: a revolve that does not touch the part is a new body
    except Exception:
        return "join"
    return "cut" if inside > outside + 1e-6 * max(1.0, tool.Volume) else "join"


def joins_nothing(profiles, axis, options, feature=None):
    """True when a Join would not even touch the part it is made in: Fusion then makes a
    new body (it never leaves a separate piece in a body)."""
    src = _source_body(profiles)
    before = feature if feature is not None and owner_body(feature) is src else None
    tip = before.BaseFeature if before is not None else src.Tip
    if tip is None or tip.Shape.isNull() or not tip.Shape.Solids:
        return False  # the first solid of a body is a new body already
    base = tip.Shape.copy()
    base.Placement = src.getGlobalPlacement().multiply(base.Placement)
    try:
        return auto_operation(base, profiles, axis, options) == "new_body"
    except Exception:
        return False


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
    return getattr(obj, ROLE, "") in ("RevolveProfile", "RevolveAxis", "RevolveFace", "RevolveTo")


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


class FaceLink:
    """A hidden copy of the flat faces of the part that a revolve turns (faces picked as
    its profile). FreeCAD names faces by number, and it loses a name when an earlier step
    changes the faces around it: the revolve then failed ("missing element reference",
    "Select a profile"). Fusion keeps the face. This finds each face again by where it
    was: the face on the same plane that holds the same inside point; else the face of
    that name if it still faces the same way (it moved, e.g. the part got taller); else
    the face facing that way nearest to where it was. It remembers each face as found.
    Saved documents store "sciforge.revolve.FaceLink": keep the name stable."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        if "Sources" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyLinkListGlobal", "Sources", "Profile", "The steps the faces are of"
            )
        if "Faces" not in obj.PropertiesList:
            # Output: remembering where a face was found does not ask for a recompute
            obj.addProperty("App::PropertyString", "Faces", "Profile", "Where each face is", 16)
            obj.setEditorMode("Faces", 2)

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        import Part

        entries = _face_entries(obj)
        if not entries:
            raise RevolveError("Select a profile to revolve.")
        body = owner_body(obj)
        here = body.getGlobalPlacement() if body is not None else App.Placement()
        faces, changed = [], False
        for entry in entries:
            src = obj.Document.getObject(entry.get("obj", ""))
            if src is None or src.Shape.isNull():
                raise RevolveError(
                    "The part the profile face was on is gone. Edit the revolve and pick the "
                    "profile again."
                )
            found = _find_face(src.Shape, entry)
            if found is None:
                raise RevolveError(
                    "The profile face is gone from the part. Edit the revolve and pick the "
                    "profile again."
                )
            face, fresh = found
            if fresh != entry:
                entry.clear()
                entry.update(fresh)
                changed = True
            move = here.inverse().multiply(_body_placement(src))
            if not move.isIdentity():
                face = face.copy()
                face.transformShape(move.toMatrix())
            faces.append(face)
        obj.Shape = faces[0] if len(faces) == 1 else Part.makeCompound(faces)
        if changed:
            obj.Faces = json.dumps(entries, sort_keys=True)

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def _face_entries(link):
    try:
        data = json.loads(getattr(link, "Faces", "") or "[]")
        return [e for e in data if isinstance(e, dict)]
    except Exception:
        return []


def _vec(values):
    return App.Vector(*[float(v) for v in values])


def _face_entry(obj, sub, face):
    """What FaceLink remembers of a face (coordinates of its own body)."""
    normal = extrude.face_normal(face)
    point = extrude.interior_point(face)
    center = face.CenterOfMass
    return {
        "obj": obj.Name,
        "sub": sub,
        "point": [point.x, point.y, point.z],
        "normal": [normal.x, normal.y, normal.z],
        "center": [center.x, center.y, center.z],
        "area": face.Area,
    }


def _find_face(shape, entry):
    """(face, fresh entry) of the remembered face in `shape`, or None."""
    point, normal = _vec(entry["point"]), _vec(entry["normal"])
    size = max(1.0, shape.BoundBox.DiagonalLength)
    tol = 1e-7 * size

    def facing(face):
        try:
            return face.Surface.TypeId == "Part::GeomPlane" and (
                extrude.face_normal(face).dot(normal) > 1.0 - 1e-9
            )
        except Exception:
            return False

    def holds(face):
        if abs((point - face.Vertexes[0].Point).dot(normal)) > tol * 10:
            return False
        try:
            return face.isInside(point, tol * 10, True)
        except Exception:
            return False

    faces = list(shape.Faces)
    sub = entry.get("sub", "")
    named = None
    if sub.startswith("Face") and sub[4:].isdigit() and 0 < int(sub[4:]) <= len(faces):
        named = int(sub[4:])
    pick = None
    if named is not None and facing(faces[named - 1]) and holds(faces[named - 1]):
        pick = named  # unchanged
    if pick is None:
        for i, face in enumerate(faces, start=1):
            if facing(face) and holds(face):
                pick = i  # the same place under another name
                break
    if pick is None and named is not None and facing(faces[named - 1]):
        pick = named  # the face moved (the part around it changed size)
    if pick is None:
        center = _vec(entry.get("center", entry["point"]))
        near = [
            (i, (face.CenterOfMass - center).Length)
            for i, face in enumerate(faces, start=1)
            if facing(face)
        ]
        if near:
            pick = min(near, key=lambda x: x[1])[0]
    if pick is None:
        return None
    face = faces[pick - 1]
    fresh = _face_entry(_Named(entry["obj"]), "Face%d" % pick, face)
    return face, fresh


class _Named:
    def __init__(self, name):
        self.Name = name


def _face_link(body, feature, picks, existing=None):
    """A hidden FaceLink in `body`, just before `feature`, holding the picked faces."""
    link = existing
    if link is None or not isinstance(getattr(link, "Proxy", None), FaceLink):
        link = body.Document.addObject("Part::Part2DObjectPython", "RevolveFace")
        FaceLink(link)
        body.insertObject(link, feature, False)
        _mark(link, "RevolveFace")
    link.Label = "%s profile" % feature.Label
    entries = []
    for obj, sub in picks:
        try:
            face = obj.Shape.getElement(sub)
        except Exception:
            raise RevolveError("That face is gone. Pick the profile again.")
        entries.append(_face_entry(obj, sub, face))
    sources = []
    for obj, _sub in picks:
        if obj not in sources:
            sources.append(obj)
    text = json.dumps(entries, sort_keys=True)
    if list(link.Sources) != sources:
        link.Sources = sources
    if link.Faces != text:
        link.Faces = text
        link.touch()
    _hide(link)
    return link


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


def _new_body(src_body, component=False):
    """A new body beside the source body (New Body), or inside a new component (New
    Component)."""
    from . import components

    return components.body_for_new(src_body, component)


def _source_body(profiles):
    body = owner_body(profiles[0][0])
    if body is None:
        raise RevolveError("The profile must belong to a body. Use Create Sketch first.")
    return body


def _structure(feature, profiles, options, participants=None):
    """(target body or None for 'make a new one', feature type, source body).
    `participants`: the bodies the revolve acts on (None: the profile's body)."""
    src = _source_body(profiles)
    meta = load_meta(feature) if feature is not None else {}
    created = None
    if feature is not None and meta.get("created_body"):
        created = feature.Document.getObject(meta["created_body"])
    if created is not None:
        from .components_core import same_new

        if not same_new(meta.get("operation"), options["operation"]):
            created = None  # New Body <-> New Component: the result moves (made again)
    if options["operation"] in ("new_body", "new_component"):
        if created is not None:
            target = created
        elif options["operation"] == "new_component":
            target = None  # always a new component with a new body in it
        elif feature is not None and owner_body(feature) is src and not _has_solid(src, feature):
            target = src  # the first solid of a body already is a new body
        elif feature is None and not _has_solid(src):
            target = src
        else:
            target = None
    elif participants:
        from .extrude_bodies import lead_body

        target = lead_body(src, participants)
    else:
        target = src
    return target, feature_type(options["operation"]), src


def build(profiles, axis, options, name="Revolve", feature=None, hide=True):
    """Create the revolve, or rebuild `feature` with new profiles/axis/options.
    Returns the feature (a different object when its kind had to change). hide=False
    keeps the profile sketches visible (the dialog hides them on OK, like Fusion)."""
    from .extrude_bodies import (
        _show_only_tip,
        ends_body,
        merge_tip,
        nothing_touched,
        participants_of,
        sync_followers,
    )

    profiles = check_profiles(profiles)
    options = options_with_defaults(options)
    check_options(options)
    check_axis(profiles, axis)
    doc = profiles[0][0].Document
    participants = participants_of(
        feature, doc, options, lambda: tool_shape(profiles, axis, options)
    )
    if participants is not None and not participants:
        if options["operation"] != "join":
            raise RevolveError(nothing_touched(options, "revolve"))
        options = dict(options, operation="new_body")  # a Join touching nothing
        participants = None
    elif (
        participants is None
        and options["operation"] == "join"
        and joins_nothing(profiles, axis, options, feature)
    ):
        options = dict(options, operation="new_body")  # Fusion: a new body, never a lump
    target, type_id, src = _structure(feature, profiles, options, participants)
    if feature is not None:
        same = feature.TypeId == type_id and (type_id != FP_TYPE or is_intersect(feature))
        if owner_body(feature) is target and same:
            _update(feature, target, profiles, axis, options, hide)
            sync_followers(feature, participants, options)
            if participants is not None:
                _show_only_tip(target)
            return feature
        moving = target is None or owner_body(feature) is not target
        blocking = [o for o in _users(feature) if not is_helper(o)]
        if blocking and moving:
            # A step in this body may not link to another body's faces (FreeCAD).
            raise RevolveError(
                "%s is used by %s, so it cannot become a new body. Make a new revolve "
                "instead." % (feature.Label, ", ".join(o.Label for o in blocking))
            )
    old_meta = load_meta(feature) if feature is not None else {}
    created = None
    if target is None:
        target = created = _new_body(src, options["operation"] == "new_component")
    elif old_meta.get("created_body") == target.Name:
        created = target
    before = feature if (feature is not None and owner_body(feature) is target) else None
    was_tip = before is not None and ends_body(target, before)
    after = None
    if feature is not None and before is None and created is None:
        # The revolve moves to another body (its sketch's body was left out of Objects To
        # Cut, or taken back): at its own place in time there, as Extrude's lead does.
        from .extrude_bodies import insert_point, place_in

        after = place_in(target, feature)
        if after is target.Tip:
            after = None
    if after is not None:
        new = doc.addObject(type_id, name)
        target.insertObject(new, insert_point(target, after, feature), True)
    else:
        new = _insert(target, type_id, name, before)
    if feature is not None:
        extrude._keep_timeline_place(new, feature)
    if type_id == FP_TYPE:
        RevolveFeature(new)
        _attach_view_provider(new)
    _save_meta(new, {"created_body": created.Name if created is not None else None})
    try:
        _update(new, target, profiles, axis, options, hide)
    except Exception:
        _remove(new, keep_body=created is None or before is not None)
        raise
    # The other bodies' steps follow the new lead (before the old one goes, with its links).
    sync_followers(new, participants, options, old=feature)
    if feature is not None:
        label = feature.Label
        old_body = owner_body(feature)
        users = _users(feature)
        if users:
            # Fusion: later steps keep their faces/edges when Join becomes Cut (a sketch on
            # its face, another revolve about its edge): point them at the new step.
            try:
                new.recompute()
            except Exception:
                pass
            _relink_users(feature, new, users)
        _remove(feature, keep_body=old_body is target)
        new.Label = label
        if old_body is not None and old_body is not target:
            _show_tip(old_body)
    if (before is None and after is None) or was_tip:
        target.Tip = new
    elif after is not None:
        _show_only_tip(target)
    merge_tip(new)
    if participants is not None:
        _show_only_tip(target)  # a removed merge or old step left the body's end hidden
    return new


def _users(feature):
    """Objects that link to `feature` other than its own helpers, its body and the step
    after it through its history (BaseFeature: FreeCAD moves that one itself)."""
    own = set(load_meta(feature).get("helpers", []))
    found = []
    for obj in feature.InList:
        if obj.TypeId in ("PartDesign::Body", "App::Part") or obj.Name in own:
            continue
        if getattr(obj, "SciForgeRole", "") == extrude.FOLLOWER_ROLE:
            continue  # its steps in other bodies move over with sync_followers
        if isinstance(getattr(obj, "Proxy", None), FaceLink):
            found.append(obj)
            continue
        if extrude._links_to(obj, feature, ("BaseFeature",)):
            found.append(obj)
    return found


def _same_element(shape, element, kind):
    """Name of the element of `shape` that is `element` by geometry (same place and
    size), or None."""
    size = max(1.0, shape.BoundBox.DiagonalLength)
    tol = 1e-6 * size
    if kind == "Vertex":
        items = shape.Vertexes
    elif kind == "Edge":
        items = shape.Edges
    elif kind == "Face":
        items = shape.Faces
    else:
        return None
    for i, item in enumerate(items, start=1):
        try:
            if kind == "Vertex":
                same = (item.Point - element.Point).Length < tol
            elif kind == "Edge":
                same = (
                    abs(item.Length - element.Length) < tol
                    and (item.CenterOfMass - element.CenterOfMass).Length < tol
                    and len(item.Vertexes) == len(element.Vertexes)
                    and all(
                        min((v.Point - w.Point).Length for w in item.Vertexes) < tol
                        for v in element.Vertexes
                    )
                )
            else:
                same = (
                    item.Surface.TypeId == element.Surface.TypeId
                    and abs(item.Area - element.Area) < tol * size
                    and (item.CenterOfMass - element.CenterOfMass).Length < tol
                )
        except Exception:
            same = False
        if same:
            return "%s%d" % (kind, i)
    return None


def _map_subs(old, new, subs):
    """The element names of `old` in `subs` as names of `new` (found by geometry; a name
    with no twin is kept, FreeCAD's naming decides then)."""
    out = []
    for sub in subs:
        name = (sub or "").lstrip("?")
        kind = name.rstrip("0123456789")
        mapped = None
        if kind in ("Vertex", "Edge", "Face"):
            try:
                mapped = _same_element(new.Shape, old.Shape.getElement(name), kind)
            except Exception:
                mapped = None
        out.append(mapped or sub)
    return out


def _relink_users(old, new, users):
    """Point every link of `users` to `old` (and its faces/edges) at `new`."""
    for obj in users:
        try:
            if isinstance(getattr(obj, "Proxy", None), FaceLink):
                entries = _face_entries(obj)
                for entry in entries:
                    if entry.get("obj") == old.Name:
                        entry["obj"] = new.Name
                obj.Faces = json.dumps(entries, sort_keys=True)
                obj.Sources = [new if s is old else s for s in obj.Sources]
                obj.touch()
                continue
            for prop in obj.PropertiesList:
                if prop == "BaseFeature":
                    continue
                kind = obj.getTypeIdOfProperty(prop)
                if "Link" not in kind or "Hidden" in kind:
                    continue
                value = getattr(obj, prop)
                swapped, changed = _swap_links(value, old, new, "Sub" in kind)
                if changed:
                    setattr(obj, prop, swapped)
        except Exception:
            pass  # the user step then shows FreeCAD's own complaint, like any lost link


def _swap_links(value, old, new, with_subs):
    if value is old:
        return new, True
    if isinstance(value, tuple) and len(value) == 2 and value[0] is old and with_subs:
        subs = value[1]
        subs = [subs] if isinstance(subs, str) else list(subs)
        return (new, _map_subs(old, new, subs)), True
    if isinstance(value, list):
        out, changed = [], False
        for item in value:
            swapped, did = _swap_links(item, old, new, with_subs)
            out.append(swapped)
            changed = changed or did
        return out, changed
    return value, False


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
    old_faces = [h for h in old if getattr(h, ROLE, "") == "RevolveFace"]
    helpers = []
    # Faces of the part go through a FaceLink (found again by place when FreeCAD loses
    # their names); sketch areas are linked as they are.
    direct = [(obj, sub) for obj, sub in profiles if is_sketch(obj)]
    picks = [(obj, sub) for obj, sub in profiles if not is_sketch(obj)]
    if picks:
        faces = _face_link(body, feature, picks, old_faces[0] if old_faces else None)
        helpers.append(faces)
        direct.append((faces, ""))
    if _needs_binder(body, direct):
        existing = old_profile[0] if old_profile else None
        binder = _binder(body, feature, direct, existing)
        helpers.append(binder)
        link = binder
        fp_profiles = [(binder, "")]
    else:
        link = _direct_profile(direct)
        fp_profiles = list(direct)
    axis_link = _local_axis(body, feature, axis, helpers, old_axis)
    to_helper = None
    if options["type"] == "to":
        # How far it turns is worked out again on every recompute (the object can move).
        angle = stop_angle(global_faces(profiles), axis, options["to"])
        old_to = [h for h in old if getattr(h, ROLE, "") == "RevolveTo"]
        to_helper = _to_link(
            body, feature, fp_profiles, axis, options["to"], angle, old_to[0] if old_to else None
        )
        helpers.append(to_helper)
        options = dict(options, angle=angle)
    keep = {h.Name for h in helpers}
    gone = [name for name in old_names if name not in keep]
    # A formula on the revolve that reads a helper about to go (Type To's angle, when the
    # type changes back to Angle) is dropped first: it would point at nothing.
    for prop, expr in list(dict(feature.ExpressionEngine).items()):
        if any(name in expr for name in gone):
            feature.setExpression(prop, None)
    for name in gone:
        helper = doc.getObject(name)
        if helper is not None:
            _delete(helper)
    if is_intersect(feature):
        feature.Profiles = [(obj, [sub]) for obj, sub in fp_profiles]
    else:
        feature.Profile = link
        if hasattr(feature, "AllowMultiFace"):
            feature.AllowMultiFace = True
    feature.ReferenceAxis = (axis_link[0], [axis_link[1]])
    _apply(feature, options, to_helper)
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
            "to": _ref_json(options.get("to")) if options["type"] == "to" else None,
            "helpers": [h.Name for h in helpers],
        }
    )
    _save_meta(feature, meta)
    if hide:
        hide_sketches(profiles)


# Dialog value -> the feature property its formula drives.
FORMULAS = {"angle": "Angle", "angle2": "Angle2"}


def _formula_used(key, options):
    if options["type"] in ("full", "to"):
        return False
    if key == "angle2":
        return options["direction"] == "two_sides"
    return True


def _wrap(key, expr, options):
    """The property's expression for a formula typed in the dialog: FreeCAD's Angle is the
    whole positive turn (a symmetric revolve's is twice the angle of one side; a negative
    angle is a reversed revolve of the positive one)."""
    if key != "angle":
        return expr
    negative = float(options["angle"]) < 0
    if options["direction"] == "symmetric":
        return "%s * (%s)" % ("-2" if negative else "2", expr)
    return "-(%s)" % expr if negative else expr


def _unwrap(key, expr):
    if key == "angle":
        for head in ("-2 * (", "2 * (", "-("):
            if expr.startswith(head) and expr.endswith(")"):
                return expr[len(head) : -1]
    return expr


def _apply_expressions(feature, options):
    """Formulas typed in the dialog become expressions on the feature's properties; a value
    typed as a plain number (or dragged) removes the formula again."""
    from . import parameters, parameters_core

    typed = options.get("expressions") or {}
    names = parameters.user_names(feature.Document)
    engine = dict(feature.ExpressionEngine)
    for key, prop in FORMULAS.items():
        if prop not in feature.PropertiesList:
            continue
        text = (typed.get(key) or "").strip()
        if text and _formula_used(key, options):
            expr = _wrap(key, parameters_core.to_freecad(text, names), options)
            if engine.get(prop) != expr:
                feature.setExpression(prop, expr)
        elif prop in engine:
            feature.setExpression(prop, None)


def formulas_of(feature):
    """{"angle": formula, ...} driving an existing revolve (bare parameter names)."""
    from . import parameters_core

    try:
        engine = dict(feature.ExpressionEngine)
    except Exception:
        return {}
    # The angle a Type To revolve gets from its helper is no formula the user typed.
    helpers = load_meta(feature).get("helpers", [])
    found = {}
    for key, prop in FORMULAS.items():
        if prop in engine and not any(name in engine[prop] for name in helpers):
            found[key] = _unwrap(key, parameters_core.from_freecad(engine[prop]))
    return found


def _apply(feature, options, to_helper=None):
    """Type / angles / direction onto a Revolution, Groove or intersect feature."""
    a1, a2 = float(options["angle"]), float(options["angle2"])
    if options["type"] == "to":
        kind, angle, angle2, mid, rev = "Angle", abs(a1), 0.0, False, a1 < 0
    elif options["type"] == "full":
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
    _apply_expressions(feature, options)
    engine = dict(feature.ExpressionEngine)
    if to_helper is not None:
        for prop, expr in (
            ("Angle", "abs(%s.Angle)" % to_helper.Name),
            ("Reversed", "%s.Angle < 0 ? 1 : 0" % to_helper.Name),
        ):
            if engine.get(prop) != expr:
                feature.setExpression(prop, expr)
    elif "Reversed" in engine:
        feature.setExpression("Reversed", None)


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
    from .extrude_bodies import followers_of, remove_follower

    meta = load_meta(feature)
    doc = feature.Document
    body = owner_body(feature)
    helpers = [doc.getObject(n) for n in meta.get("helpers", [])]
    for follower in followers_of(feature):  # its steps in other bodies go too
        remove_follower(follower)
    _delete(feature)
    for helper in helpers:
        if helper is not None:
            _delete(helper)
    if not keep_body and body is not None and meta.get("created_body") == body.Name:
        rest = [o for o in body.Group if o.TypeId != "App::Origin"]
        if not rest:
            from . import components

            container = components.container_of(body)
            body.removeObjectsFromDocument()
            doc.removeObject(body.Name)
            components.drop_if_empty(container)  # a New Component that failed


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


def problem(feature):
    """What is wrong with a computed revolve that FreeCAD accepts without a word, or ''.
    FreeCAD's Groove that misses the part changes nothing, and one that takes everything
    leaves an empty body, both "valid"; Fusion says so (like SciForge's Extrude)."""
    try:
        if feature is None or feature.TypeId != "PartDesign::Groove":
            return ""
        if "Invalid" in list(feature.State) or "Error" in list(feature.State):
            return ""  # FreeCAD's own failure text is shown instead
        base = feature.BaseFeature
        if base is None or base.Shape.isNull() or not base.Shape.Solids:
            # FreeCAD's Groove then shows the revolved solid itself, as if it were a Join
            return "There is no solid to cut yet: this revolve makes the first one. Use New Body."
        shape = feature.Shape
        if shape.isNull() or not shape.Solids or shape.Volume < TOL:
            return "This cut would remove the whole body. Make the profile smaller or turn it less."
        before = base.Shape.Volume
        if abs(before - shape.Volume) <= 1e-9 * max(1.0, before):
            return (
                "The cut does not touch the body. Turn it the other way, pick another profile "
                "or use Join."
            )
    except Exception:
        return ""
    return ""


def make(profiles, axis, options, name="Revolve"):
    """New revolve with Fusion-style options (see the module text for the forms)."""
    return build(normalize(profiles), axis, options, name)


def update(feature, profiles=None, axis=None, options=None):
    """Rebuild an existing revolve; what is not given stays as it is."""
    old_profiles, old_axis, old_options = read(feature)
    merged = dict(old_options)
    options = dict(options or {})
    formulas = dict(old_options.get("expressions") or {})
    for key in FORMULAS:
        if key in options:
            formulas.pop(key, None)  # a plain value replaces the formula, as in the dialog
    formulas.update(options.pop("expressions", None) or {})
    merged.update(options)
    merged["expressions"] = formulas
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
        # Faces of the part: as the FaceLink found them last (their names may have moved)
        links = [doc.getObject(n) for n in meta.get("helpers", [])]
        links = [h for h in links if h is not None and getattr(h, ROLE, "") == "RevolveFace"]
        if links:
            faces = [
                (doc.getObject(e.get("obj", "")), e.get("sub", "")) for e in _face_entries(links[0])
            ]
            found = [p for p in found if is_sketch(p[0])] + [f for f in faces if f[0] is not None]
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
        if getattr(obj, ROLE, "") == "RevolveFace":
            for e in _face_entries(obj):
                linked = doc.getObject(e.get("obj", ""))
                if linked is not None:
                    found.append((linked, e.get("sub", "")))
        elif (
            getattr(obj, ROLE, "") == "RevolveProfile" or obj.TypeId == "PartDesign::SubShapeBinder"
        ):
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
        made = meta.get("operation")
        options["operation"] = made if made in ("new_body", "new_component") else "join"
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
    if meta.get("type") == "to":
        options["type"] = "to"
        options["direction"] = "one_side"
        options["to"] = _ref_load(feature.Document, meta.get("to"))
        # The helper has the element's name as it is now (FreeCAD can renumber them).
        for name in meta.get("helpers", []):
            helper = feature.Document.getObject(name)
            if helper is not None and getattr(helper, ROLE, "") == "RevolveTo":
                if helper.Target is not None:
                    options["to"] = (helper.Target, helper.TargetSub)
    options["expressions"] = formulas_of(feature)
    from .extrude_bodies import stored_bodies

    options["bodies"] = stored_bodies(feature)
    return profiles_of(feature), axis_of(feature), options
