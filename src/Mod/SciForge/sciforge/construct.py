# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's CONSTRUCT menu: construction planes, axes and points. No Qt code (the dialog is
construct_ui.py; the golden-model builder calls this module too).

Every entry makes a PartDesign datum (PartDesign::Plane / Line / Point) in a body, so it is
listed in the browser's Construction folder and in the timeline, and Create Sketch,
Extrude, Revolve, Mirror and the patterns take it like an origin plane or axis.

How each one is attached:
  Offset Plane (geometry of its own body): FreeCAD's FlatFace on the face or plane, the
    distance in AttachmentOffset (a formula goes on that offset as an expression).
  Everything else (and an Offset Plane on another body's face): FreeCAD's attacher has no
    mode for a midplane, a plane at an angle about an edge, a point where three planes
    meet..., and its edge modes print warnings for straight edges. A hidden helper
    (ConstructionFrame, a Part2DObjectPython just before the datum in the same body,
    SciForgeTimeline = False) links the picked geometry, works the frame out every
    recompute and the datum is attached to it (ObjectXY / ObjectZ / ObjectOrigin). The
    construction follows the model when an earlier step changes, as in Fusion, and the
    datum's own SciForgeRefs link tells the timeline what it is built on.

Inputs are picks (object, element name, picked point): an element "FaceN" / "EdgeN" /
"VertexN" of a solid or a sketch, or "" for a whole datum / origin plane, axis or point.
Values: "distance" (mm), "angle" (degrees), "distance_type" ("proportional" /
"physical") with "fraction" (0..1) or "distance" for the Along Path entries.
Problems raise ConstructError with a sentence for the dialog.
"""
try:
    import FreeCAD as App

    V = App.Vector
except ImportError:  # the ribbon's unit tests read SPECS without FreeCAD
    App = V = None

from . import labels  # noqa: E402

EPS = 1e-9
TOL = 1e-6  # mm: "on", "meets", "in one plane"

PLANE_TYPES = ("App::Plane", "PartDesign::Plane", "Part::DatumPlane")
LINE_TYPES = ("App::Line", "PartDesign::Line", "Part::DatumLine")
POINT_TYPES = ("App::Point", "PartDesign::Point", "Part::DatumPoint")
DATUM_TYPES = ("PartDesign::Plane", "PartDesign::Line", "PartDesign::Point")
SKETCH_TYPES = ("Sketcher::SketchObject",)
REVOLVED = ("Cylinder", "Cone", "Toroid", "Sphere")

PROP_KEY = "SciForgeConstruct"  # the CONSTRUCT entry a datum was made with
PROP_REFS = "SciForgeRefs"  # what it is built on (the timeline reads it)
HELPER_CLASS = "ConstructionFrame"


class ConstructError(ValueError):
    pass


class LostReference(ConstructError):
    """What a construction is built on is gone (deleted, or its face / edge no longer
    exists after an edit)."""


LOST = "Lost what it was built on (deleted or changed). Edit it and pick again."
WARNING = "SciForgeWarning"  # the timeline shows this text as the step's warning


def _inp(name, kinds, optional=False, hint=""):
    return {"name": name, "kinds": set(kinds), "optional": optional, "hint": hint}


# key -> spec. "type": the datum made; "inputs": the selection boxes in order;
# "value": the field the dialog shows (None, "distance", "angle" or "path").
SPECS = {
    "OffsetPlane": {
        "label": "Offset Plane",
        "type": "PartDesign::Plane",
        "inputs": [_inp("Plane", {"plane"}, hint="a flat face or a plane")],
        "value": "distance",
        "default": 10.0,
    },
    "PlaneAtAngle": {
        "label": "Plane at Angle",
        "type": "PartDesign::Plane",
        "inputs": [_inp("Line", {"line"}, hint="a straight edge, a sketch line or an axis")],
        "value": "angle",
        "default": 0.0,
    },
    "TangentPlane": {
        "label": "Tangent Plane",
        "type": "PartDesign::Plane",
        "inputs": [_inp("Face", {"curved"}, hint="a round face (cylinder, cone, sphere)")],
        "value": "angle",
        "default": 0.0,
    },
    "Midplane": {
        "label": "Midplane",
        "type": "PartDesign::Plane",
        "inputs": [
            _inp("Plane 1", {"plane"}, hint="a flat face or a plane"),
            _inp("Plane 2", {"plane"}, hint="a second flat face or plane"),
        ],
        "value": None,
    },
    "PlaneTwoEdges": {
        "label": "Plane Through Two Edges",
        "type": "PartDesign::Plane",
        "inputs": [
            _inp("Line 1", {"line"}, hint="a straight edge, a sketch line or an axis"),
            _inp("Line 2", {"line"}, hint="a second line in the same plane"),
        ],
        "value": None,
    },
    "PlaneThreePoints": {
        "label": "Plane Through Three Points",
        "type": "PartDesign::Plane",
        "inputs": [
            _inp("Point 1", {"point"}, hint="a corner, a sketch point or a point"),
            _inp("Point 2", {"point"}, hint="a second point"),
            _inp("Point 3", {"point"}, hint="a third point"),
        ],
        "value": None,
    },
    "PlaneAtPoint": {
        "label": "Plane Tangent to Face at Point",
        "type": "PartDesign::Plane",
        "inputs": [
            _inp("Face", {"face"}, hint="a face"),
            _inp("Point", {"point"}, hint="a point on (or above) the face"),
        ],
        "value": None,
    },
    "PlaneAlongPath": {
        "label": "Plane Along Path",
        "type": "PartDesign::Plane",
        "inputs": [_inp("Path", {"path"}, hint="an edge or a sketch curve")],
        "value": "path",
        "default": 0.5,
    },
    "AxisCylinder": {
        "label": "Axis Through Cylinder/Cone/Torus",
        "type": "PartDesign::Line",
        "inputs": [_inp("Face", {"round"}, hint="a round face or a circular edge")],
        "value": None,
    },
    "AxisNormal": {
        "label": "Axis Perpendicular to Face at Point",
        "type": "PartDesign::Line",
        "inputs": [
            _inp("Face", {"face"}, hint="a face, clicked where the axis goes"),
            _inp("Point", {"point"}, optional=True, hint="optional: a point to go through"),
        ],
        "value": None,
    },
    "AxisTwoPlanes": {
        "label": "Axis Through Two Planes",
        "type": "PartDesign::Line",
        "inputs": [
            _inp("Plane 1", {"plane"}, hint="a flat face or a plane"),
            _inp("Plane 2", {"plane"}, hint="a second flat face or plane"),
        ],
        "value": None,
    },
    "AxisTwoPoints": {
        "label": "Axis Through Two Points",
        "type": "PartDesign::Line",
        "inputs": [
            _inp("Point 1", {"point"}, hint="a corner, a sketch point or a point"),
            _inp("Point 2", {"point"}, hint="a second point"),
        ],
        "value": None,
    },
    "AxisEdge": {
        "label": "Axis Through Edge",
        "type": "PartDesign::Line",
        "inputs": [_inp("Edge", {"line"}, hint="a straight edge or a sketch line")],
        "value": None,
    },
    "PointVertex": {
        "label": "Point at Vertex",
        "type": "PartDesign::Point",
        "inputs": [_inp("Point", {"point"}, hint="a corner or a sketch point")],
        "value": None,
    },
    "PointTwoEdges": {
        "label": "Point Through Two Edges",
        "type": "PartDesign::Point",
        "inputs": [
            _inp("Edge 1", {"path", "line"}, hint="an edge or a sketch line"),
            _inp("Edge 2", {"path", "line"}, hint="a second edge that crosses it"),
        ],
        "value": None,
    },
    "PointThreePlanes": {
        "label": "Point Through Three Planes",
        "type": "PartDesign::Point",
        "inputs": [
            _inp("Plane 1", {"plane"}, hint="a flat face or a plane"),
            _inp("Plane 2", {"plane"}, hint="a second flat face or plane"),
            _inp("Plane 3", {"plane"}, hint="a third flat face or plane"),
        ],
        "value": None,
    },
    "PointCenter": {
        "label": "Point at Center of Circle/Sphere/Torus",
        "type": "PartDesign::Point",
        "inputs": [_inp("Circle/Sphere/Torus", {"center"}, hint="a circular edge or a ball")],
        "value": None,
    },
    "PointEdgePlane": {
        "label": "Point at Edge and Plane",
        "type": "PartDesign::Point",
        "inputs": [
            _inp("Edge", {"path", "line"}, hint="an edge, a sketch line or an axis"),
            _inp("Plane", {"plane"}, hint="a flat face or a plane it crosses"),
        ],
        "value": None,
    },
    "PointAlongPath": {
        "label": "Point Along Path",
        "type": "PartDesign::Point",
        "inputs": [_inp("Path", {"path"}, hint="an edge or a sketch curve")],
        "value": "path",
        "default": 0.5,
    },
}

# Kept for the ribbon data, the unit tests and older callers.
PRESETS = {key: (spec["label"], spec["type"], []) for key, spec in SPECS.items()}
NEEDS = {
    key: len([i for i in spec["inputs"] if not i["optional"]])
    for key, spec in SPECS.items()
    if len(spec["inputs"]) > 1
}
DISTANCE = {"OffsetPlane"}
ANGLE = {"PlaneAtAngle", "TangentPlane"}
PATH = {"PlaneAlongPath", "PointAlongPath"}
SHORT_NAMES = {
    "PartDesign::Plane": "Plane",
    "PartDesign::Line": "Axis",
    "PartDesign::Point": "Point",
}


def required(key):
    return [i for i in SPECS[key]["inputs"] if not i["optional"]]


# -- what a pick is ------------------------------------------------------------------------
def alive(obj):
    if obj is None:
        return False
    try:
        if hasattr(obj, "isAttachedToDocument"):
            return obj.isAttachedToDocument()
        return bool(obj.Name)
    except Exception:
        return False


def _surface_kind(face):
    return type(face.Surface).__name__


def _curve_kind(edge):
    return type(edge.Curve).__name__


def is_straight(edge):
    return _curve_kind(edge) in ("Line", "LineSegment")


def is_circular(edge):
    return _curve_kind(edge) in ("Circle", "ArcOfCircle")


def normalize_pick(obj, sub):
    """(object, element) as the construct code stores it: a datum / origin plane, axis or
    point is the whole object (FreeCAD reports a click on a datum plane as "Plane")."""
    if obj is None:
        return None, ""
    sub = (sub or "").split(".")[-1]
    if obj.TypeId in PLANE_TYPES + LINE_TYPES + POINT_TYPES:
        return obj, ""
    return obj, sub


def kinds_of(obj, sub):
    """What a pick can stand for: a set of "plane", "line", "point", "face", "curved",
    "round", "center", "path"."""
    obj, sub = normalize_pick(obj, sub)
    if obj is None:
        return set()
    if obj.TypeId in PLANE_TYPES:
        return {"plane"}
    if obj.TypeId in LINE_TYPES:
        return {"line"}
    if obj.TypeId in POINT_TYPES:
        return {"point"}
    try:
        element = obj.Shape.getElement(sub) if sub else None
    except Exception:
        return set()
    if element is None:
        return set()
    if sub.startswith("Vertex"):
        return {"point"}
    if sub.startswith("Edge"):
        found = {"path"}
        if is_straight(element):
            found.add("line")
        elif is_circular(element):
            found |= {"round", "center"}
        return found
    if sub.startswith("Face"):
        kind = _surface_kind(element)
        found = {"face"}
        if kind == "Plane":
            found.add("plane")
        elif kind in REVOLVED:
            found.add("curved")
            if kind in ("Cylinder", "Cone", "Toroid"):
                found.add("round")
            if kind in ("Sphere", "Toroid"):
                found.add("center")
        return found
    return set()


def seam_face(obj, sub):
    """The face whose seam `sub` is (the line FreeCAD draws along a cylinder or cone where
    its surface closes; Fusion draws none, so a click there means the face), or None."""
    if not sub or not sub.startswith("Edge"):
        return None
    try:
        import Part

        shape = obj.Shape
        edge = shape.getElement(sub)
        faces = shape.ancestorsOfType(edge, Part.Face)
    except Exception:
        return None
    if not faces or any(not f.isSame(faces[0]) for f in faces[1:]):
        return None
    face = faces[0]
    try:
        if not edge.isSeam(face):
            return None
    except Exception:
        return None
    for i, candidate in enumerate(shape.Faces, start=1):
        if candidate.isSame(face):
            return "Face%d" % i
    return None


def as_input(key, index, obj, sub):
    """(obj, sub) to store when the pick goes into input `index` of `key`, or None if it
    does not fit. A click on a seam counts as a click on its face."""
    inputs = SPECS[key]["inputs"]
    if index < 0 or index >= len(inputs):
        return None
    obj, sub = normalize_pick(obj, sub)
    if obj is None:
        return None
    wanted = inputs[index]["kinds"]
    if wanted & kinds_of(obj, sub):
        return obj, sub
    if wanted & {"face", "curved", "round", "center"}:
        face = seam_face(obj, sub)
        if face is not None and wanted & kinds_of(obj, face):
            return obj, face
    return None


def fits(key, index, obj, sub):
    """May the pick go into input `index` of entry `key`?"""
    return as_input(key, index, obj, sub) is not None


def describe(obj, sub):
    """A short text for a selection box ("Extrude1 face", "XY plane", "Sketch line")."""
    obj, sub = normalize_pick(obj, sub)
    if obj is None:
        return ""
    role = getattr(obj, "Role", "") or ""
    if obj.TypeId in PLANE_TYPES + LINE_TYPES + POINT_TYPES and role:
        return {
            "X_Axis": "X axis",
            "Y_Axis": "Y axis",
            "Z_Axis": "Z axis",
            "XY_Plane": "XY plane",
            "XZ_Plane": "XZ plane",
            "YZ_Plane": "YZ plane",
            "Origin": "Origin",
        }.get(role, obj.Label)
    if not sub:
        return obj.Label
    what = {"Face": "face", "Edge": "edge", "Vertex": "point"}
    for start, word in what.items():
        if sub.startswith(start):
            if obj.TypeId in SKETCH_TYPES and start == "Edge":
                word = "sketch curve"
            elif obj.TypeId in SKETCH_TYPES:
                word = "sketch point"
            return "%s %s" % (_owner_label(obj), word)
    return "%s %s" % (obj.Label, sub)


def _owner_label(obj):
    body = owner_body(obj)
    if body is not None and obj.TypeId not in SKETCH_TYPES:
        return body.Label
    return obj.Label


# -- geometry in global coordinates --------------------------------------------------------
def owner_body(obj):
    try:
        parent = obj.getParentGeoFeatureGroup()
    except Exception:
        return None
    if parent is not None and parent.TypeId == "PartDesign::Body":
        return parent
    return None


def _parent_placement(obj):
    try:
        parent = obj.getParentGeoFeatureGroup()
    except Exception:
        parent = None
    if parent is None:
        return App.Placement()
    try:
        return parent.getGlobalPlacement()
    except Exception:
        return App.Placement()


def element(obj, sub):
    """Element `sub` of `obj` in global coordinates (a copy)."""
    try:
        item = obj.Shape.getElement(sub)
    except Exception:
        raise LostReference("%s is no longer there. Pick it again." % describe(obj, sub))
    item = item.copy()
    place = _parent_placement(obj)
    if not place.isIdentity():
        item.transformShape(place.toMatrix())
    return item


def _unit(v):
    v = V(v)
    if v.Length < EPS:
        raise ConstructError("A direction could not be worked out here.")
    v.normalize()
    return v


def any_perpendicular(d):
    d = _unit(d)
    other = V(1, 0, 0) if abs(d.x) < 0.9 else V(0, 1, 0)
    return _unit(d.cross(other))


def _face_point(face, point=None):
    """(u, v) on the face: at `point` projected onto it, else the middle of the face."""
    if point is not None:
        try:
            u, v = face.Surface.parameter(V(point))
            return u, v
        except Exception:
            pass
    u0, u1, v0, v1 = face.ParameterRange
    return (u0 + u1) / 2.0, (v0 + v1) / 2.0


def plane_of(ref):
    """(origin, normal) of a flat face or a plane, global. A face's normal points out of
    the part (FreeCAD's normalAt already takes the face's orientation into account)."""
    obj, sub = ref[0], ref[1]
    if obj.TypeId in PLANE_TYPES:
        gp = obj.getGlobalPlacement()
        return gp.Base, _unit(gp.Rotation.multVec(V(0, 0, 1)))
    if not sub.startswith("Face"):
        raise ConstructError("%s is not flat: pick a flat face or a plane." % describe(obj, sub))
    face = element(obj, sub)
    if _surface_kind(face) != "Plane":
        raise ConstructError("%s is not flat: pick a flat face or a plane." % describe(obj, sub))
    u, v = _face_point(face)
    normal = _unit(face.normalAt(u, v))
    centre = face.CenterOfMass
    origin = centre - normal * (centre - face.valueAt(u, v)).dot(normal)
    return origin, normal


def plane_frame(ref):
    """The frame of a plane or flat face (global): local Z its normal (out of the part for a
    face), local X the plane's own X (an origin or construction plane) or the face's."""
    obj, sub = ref[0], ref[1]
    if obj.TypeId in PLANE_TYPES:
        gp = obj.getGlobalPlacement()
        return App.Placement(gp.Base, gp.Rotation)
    origin, normal = plane_of(ref)
    x = None
    try:
        surface = element(obj, sub).Surface
        x = V(surface.value(1.0, 0.0)) - V(surface.value(0.0, 0.0))  # the face's u direction
    except Exception:
        x = None
    return frame(origin, normal, x)


def line_of(ref):
    """(point, direction, length or None) of a straight edge, sketch line or axis."""
    obj, sub = ref[0], ref[1]
    if obj.TypeId in LINE_TYPES:
        gp = obj.getGlobalPlacement()
        local = V(1, 0, 0) if obj.TypeId == "App::Line" else V(0, 0, 1)
        return gp.Base, _unit(gp.Rotation.multVec(local)), None
    if not sub.startswith("Edge"):
        raise ConstructError("%s is not a line: pick a straight edge or an axis." % describe(*ref))
    edge = element(obj, sub)
    if not is_straight(edge):
        raise ConstructError(
            "%s is not straight: pick a straight edge or an axis." % describe(*ref)
        )
    a = edge.valueAt(edge.FirstParameter)
    b = edge.valueAt(edge.LastParameter)
    return a, _unit(b - a), (b - a).Length


def point_of(ref):
    obj, sub = ref[0], ref[1]
    if obj.TypeId in POINT_TYPES:
        return obj.getGlobalPlacement().Base
    if not sub.startswith("Vertex"):
        raise ConstructError("%s is not a point: pick a corner or a point." % describe(*ref))
    return element(obj, sub).Point


def edge_of(ref):
    obj, sub = ref[0], ref[1]
    if obj.TypeId in LINE_TYPES or not sub.startswith("Edge"):
        raise ConstructError("%s is not an edge: pick an edge or a sketch curve." % describe(*ref))
    return element(obj, sub)


def face_of(ref):
    obj, sub = ref[0], ref[1]
    if not sub.startswith("Face"):
        raise ConstructError("%s is not a face: pick a face." % describe(*ref))
    return element(obj, sub)


def upward(v):
    """`v` turned to point "up": its Z part positive, else its Y part, else its X part.
    Angles turn right-handed about such an axis, so they do not depend on which way
    OpenCASCADE happens to run an edge or a surface's axis."""
    v = _unit(v)
    for part in (v.z, v.y, v.x):
        if abs(part) > 1e-9:
            return v if part > 0 else v * -1.0
    return v


def revolution_of(ref):
    """(centre, axis, kind) of a cylinder / cone / torus / sphere face or a circular edge;
    the axis points up (see upward)."""
    obj, sub = ref[0], ref[1]
    if sub.startswith("Edge"):
        edge = element(obj, sub)
        if not is_circular(edge):
            raise ConstructError("%s is not round: pick a round face or a circle." % describe(*ref))
        return V(edge.Curve.Center), upward(edge.Curve.Axis), "Circle"
    face = face_of(ref)
    surface = face.Surface
    kind = _surface_kind(face)
    if kind not in REVOLVED:
        raise ConstructError(
            "%s is not round: pick a cylinder, cone, torus or ball face." % describe(*ref)
        )
    centre = V(surface.Apex) if kind == "Cone" else V(surface.Center)
    return centre, upward(surface.Axis), kind


# -- frames ------------------------------------------------------------------------------
def frame(origin, z, x=None):
    """Placement at `origin` whose local Z is `z` (and X along `x` where possible)."""
    z = _unit(z)
    if x is None or V(x).cross(z).Length < 1e-6:
        x = any_perpendicular(z)
    x = _unit(V(x) - z * V(x).dot(z))
    y = z.cross(x)
    return App.Placement(V(origin), App.Rotation(x, y, z, "ZXY"))


def rotate_about(point, centre, axis, degrees):
    rot = App.Rotation(V(axis), degrees)
    return V(centre) + rot.multVec(V(point) - V(centre))


def _project_on_line(point, base, direction):
    return V(base) + V(direction) * (V(point) - V(base)).dot(V(direction))


def zero_normal(ref, direction):
    """Plane at Angle at 0 degrees: the plane the line lies in already. A sketch line: its
    sketch; an edge of the part: the flat face it bounds; an origin axis: XY for X, YZ for
    Y, XZ for Z (FreeCAD's own planes through those axes); a construction axis: any."""
    obj, sub = ref[0], ref[1]
    n0 = None
    if obj.TypeId in SKETCH_TYPES:
        n0 = obj.getGlobalPlacement().Rotation.multVec(V(0, 0, 1))
    elif obj.TypeId == "App::Line":
        n0 = obj.getGlobalPlacement().Rotation.multVec(V(0, 0, 1))
    elif obj.TypeId in LINE_TYPES:
        n0 = obj.getGlobalPlacement().Rotation.multVec(V(1, 0, 0))
    elif sub.startswith("Edge"):
        try:
            edge = obj.Shape.getElement(sub)
            place = _parent_placement(obj)
            for face in obj.Shape.ancestorsOfType(edge, _face_type()):
                if _surface_kind(face) == "Plane":
                    face = face.copy()
                    if not place.isIdentity():
                        face.transformShape(place.toMatrix())
                    u, v = _face_point(face)
                    n0 = face.normalAt(u, v)
                    break
        except Exception:
            n0 = None
    if n0 is not None:
        n0 = V(n0) - direction * V(n0).dot(direction)
        if n0.Length > 1e-6:
            return _unit(n0)
    return any_perpendicular(direction)


def _face_type():
    import Part

    return Part.Face


def _scale(*points):
    size = 1.0
    for p in points:
        size = max(size, abs(p.x), abs(p.y), abs(p.z))
    return size


def path_parameter(edge, values):
    """The curve parameter of the Along Path position (proportional by length, or a
    physical distance from the path's start)."""
    length = edge.Length
    if values.get("distance_type", "proportional") == "physical":
        s = float(values.get("distance", 0.0))
        if s < -TOL or s > length + TOL:
            raise ConstructError(
                "The path is %.4g mm long: the distance must be between 0 and that." % length
            )
    else:
        f = float(values.get("fraction", 0.5))
        if f < -1e-9 or f > 1 + 1e-9:
            raise ConstructError("The distance along the path goes from 0 to 1.")
        s = f * length
    s = min(max(s, 0.0), length)
    if s <= 0.0:
        return edge.FirstParameter
    if s >= length:
        return edge.LastParameter
    return edge.getParameterByLength(s)


def compute(key, refs, points=None, values=None):
    """The global Placement of the construction `key` built on `refs` [(obj, sub)], with
    `points` (picked point per ref, or None) and `values`. Raises ConstructError."""
    spec = SPECS[key]
    values = dict(values or {})
    points = list(points or [])
    points += [None] * (len(refs) - len(points))
    need = required(key)
    if len(refs) < len(need):
        missing = need[len(refs)]
        raise ConstructError("Select %s." % missing["hint"])
    refs = [(r[0], r[1]) for r in refs]
    for ref in refs:
        if not alive(ref[0]):
            raise LostReference("Something it was built on is gone. Pick it again.")
    handler = globals()["_c_" + key]
    return handler(refs, points, values, spec)


def _c_OffsetPlane(refs, points, values, spec):
    origin, normal = plane_of(refs[0])
    d = float(values.get("distance", spec.get("default", 0.0)))
    base = frame(origin, normal)
    return frame(origin + normal * d, normal, base.Rotation.multVec(V(1, 0, 0)))


def angle_line(ref):
    """(middle point, upward direction) of the line Plane at Angle turns about."""
    p, d, length = line_of(ref)
    if length:
        p = p + d * (length / 2.0)
    return p, upward(d), length


def _c_PlaneAtAngle(refs, points, values, spec):
    p, d, length = angle_line(refs[0])
    n0 = zero_normal(refs[0], d)
    n = App.Rotation(d, float(values.get("angle", 0.0))).multVec(n0)
    return frame(p, n, d)


def _c_TangentPlane(refs, points, values, spec):
    face = face_of(refs[0])
    centre, axis, kind = revolution_of(refs[0])
    u, v = _face_point(face, points[0])
    p0 = face.valueAt(u, v)
    n0 = _unit(face.normalAt(u, v))
    angle = float(values.get("angle", 0.0))
    p = rotate_about(p0, centre, axis, angle)
    n = App.Rotation(axis, angle).multVec(n0)
    x = axis if kind != "Sphere" else None
    if x is not None and V(x).cross(n).Length < 1e-6:
        x = None
    return frame(p, n, x)


def _c_Midplane(refs, points, values, spec):
    o1, n1 = plane_of(refs[0])
    o2, n2 = plane_of(refs[1])
    if n1.cross(n2).Length < 1e-7:
        gap = (o2 - o1).dot(n1)
        if abs(gap) < TOL:
            raise ConstructError("The two planes are the same plane: pick two different ones.")
        mid = (o1 + o2) * 0.5
        mid = mid - n1 * (mid - o1).dot(n1) + n1 * (gap / 2.0)
        return frame(mid, n1)
    d = _unit(n1.cross(n2))
    point = _plane_line_point(o1, n1, o2, n2, d)
    centre = _project_on_line((o1 + o2) * 0.5, point, d)
    n = n1 - n2
    if n.Length < 1e-7:
        n = n1 + n2
    return frame(centre, _unit(n), d)


def _plane_line_point(o1, n1, o2, n2, d):
    """A point on the line where two planes meet (d = n1 x n2, unit)."""
    d1, d2 = o1.dot(n1), o2.dot(n2)
    raw = n1.cross(n2)
    denom = raw.Length**2
    return (n2.cross(raw) * d1 + raw.cross(n1) * d2) * (1.0 / denom)


def _c_PlaneTwoEdges(refs, points, values, spec):
    p1, d1, l1 = line_of(refs[0])
    p2, d2, l2 = line_of(refs[1])
    if l1:
        p1 = p1 + d1 * (l1 / 2.0)
    if l2:
        p2 = p2 + d2 * (l2 / 2.0)
    gap = p2 - p1
    n = d1.cross(d2)
    if n.Length < 1e-7:  # parallel
        n = d1.cross(gap)
        if n.Length < TOL:
            raise ConstructError("The two lines lie on one line: pick two different lines.")
    n = _unit(n)
    if abs(gap.dot(n)) > TOL * _scale(p1, p2):
        raise ConstructError("The two lines are not in one plane: pick lines that are.")
    return frame((p1 + p2) * 0.5, n, d1)


def _c_PlaneThreePoints(refs, points, values, spec):
    a, b, c = (point_of(r) for r in refs[:3])
    n = (b - a).cross(c - a)
    if n.Length < TOL * _scale(a, b, c):
        raise ConstructError("The three points are on one line: pick points that are not.")
    return frame((a + b + c) * (1.0 / 3.0), n, b - a)


def _c_PlaneAtPoint(refs, points, values, spec):
    face = face_of(refs[0])
    q = point_of(refs[1])
    u, v = _face_point(face, q)
    return frame(face.valueAt(u, v), face.normalAt(u, v))


def _path_frame(refs, values):
    edge = edge_of(refs[0])
    u = path_parameter(edge, values)
    p = edge.valueAt(u)
    t = _unit(edge.tangentAt(u))
    return p, t, edge


def _c_PlaneAlongPath(refs, points, values, spec):
    p, t, edge = _path_frame(refs, values)
    x = None
    try:
        x = edge.normalAt(path_parameter(edge, values))
    except Exception:
        x = None
    return frame(p, t, x)


def _line_frame(point, direction):
    return frame(point, direction)


def _c_AxisCylinder(refs, points, values, spec):
    centre, axis, kind = revolution_of(refs[0])
    obj, sub = refs[0]
    try:
        middle = element(obj, sub).CenterOfMass if sub.startswith("Face") else centre
    except Exception:
        middle = centre
    return _line_frame(_project_on_line(middle, centre, axis), axis)


def _c_AxisNormal(refs, points, values, spec):
    face = face_of(refs[0])
    target = points[0]
    if len(refs) > 1 and refs[1] is not None:
        target = point_of(refs[1])
    u, v = _face_point(face, target)
    return _line_frame(face.valueAt(u, v), face.normalAt(u, v))


def _c_AxisTwoPlanes(refs, points, values, spec):
    o1, n1 = plane_of(refs[0])
    o2, n2 = plane_of(refs[1])
    raw = n1.cross(n2)
    if raw.Length < 1e-7:
        raise ConstructError("The two planes are parallel: they never meet in a line.")
    d = _unit(raw)
    point = _plane_line_point(o1, n1, o2, n2, d)
    return _line_frame(_project_on_line((o1 + o2) * 0.5, point, d), d)


def _c_AxisTwoPoints(refs, points, values, spec):
    a, b = point_of(refs[0]), point_of(refs[1])
    if (b - a).Length < TOL:
        raise ConstructError("The two points are at the same place: pick two different ones.")
    return _line_frame((a + b) * 0.5, b - a)


def _c_AxisEdge(refs, points, values, spec):
    p, d, length = line_of(refs[0])
    if length:
        p = p + d * (length / 2.0)
    return _line_frame(p, d)


def _c_PointVertex(refs, points, values, spec):
    return App.Placement(point_of(refs[0]), App.Rotation())


def _line_or_edge(ref):
    obj, sub = ref
    if obj.TypeId in LINE_TYPES:
        p, d, _l = line_of(ref)
        return ("line", p, d, None)
    edge = edge_of(ref)
    if is_straight(edge):
        p, d, _l = line_of(ref)
        return ("line", p, d, edge)
    return ("curve", None, None, edge)


def _c_PointTwoEdges(refs, points, values, spec):
    a, b = _line_or_edge(refs[0]), _line_or_edge(refs[1])
    if a[0] == "line" and b[0] == "line":
        p1, d1, p2, d2 = a[1], a[2], b[1], b[2]
        w = d1.cross(d2)
        if w.Length < 1e-7:
            raise ConstructError("The two lines are parallel: they never cross.")
        # closest points of the two (endless) lines, like Fusion's extended edges
        r = p2 - p1
        t1 = r.cross(d2).dot(w) / w.Length**2
        t2 = r.cross(d1).dot(w) / w.Length**2
        q1, q2 = p1 + d1 * t1, p2 + d2 * t2
        if (q1 - q2).Length > TOL * _scale(p1, p2):
            raise ConstructError("The two edges do not cross: pick edges that meet.")
        return App.Placement((q1 + q2) * 0.5, App.Rotation())
    shape_a = a[3] if a[3] is not None else _long_line(a[1], a[2], b[3])
    shape_b = b[3] if b[3] is not None else _long_line(b[1], b[2], a[3])
    dist, pairs, _info = shape_a.distToShape(shape_b)
    if dist > TOL * 10:
        raise ConstructError("The two edges do not cross: pick edges that meet.")
    return App.Placement(V(pairs[0][0]), App.Rotation())


def _long_line(point, direction, near_shape):
    import Part

    reach = 1000.0
    if near_shape is not None:
        box = near_shape.BoundBox
        reach = max(reach, 4 * box.DiagonalLength + (box.Center - point).Length)
    return Part.LineSegment(point - direction * reach, point + direction * reach).toShape()


def _c_PointThreePlanes(refs, points, values, spec):
    planes = [plane_of(r) for r in refs[:3]]
    (o1, n1), (o2, n2), (o3, n3) = planes
    det = n1.dot(n2.cross(n3))
    if abs(det) < 1e-7:
        raise ConstructError("These three planes do not meet in one point.")
    p = (n2.cross(n3) * o1.dot(n1) + n3.cross(n1) * o2.dot(n2) + n1.cross(n2) * o3.dot(n3)) * (
        1.0 / det
    )
    return App.Placement(p, App.Rotation())


def _c_PointCenter(refs, points, values, spec):
    obj, sub = refs[0]
    if sub.startswith("Edge"):
        edge = element(obj, sub)
        if not is_circular(edge):
            raise ConstructError("Pick a circle, an arc, a ball or a torus.")
        return App.Placement(V(edge.Curve.Center), App.Rotation())
    face = face_of(refs[0])
    if _surface_kind(face) not in ("Sphere", "Toroid"):
        raise ConstructError("Pick a circle, an arc, a ball or a torus.")
    return App.Placement(V(face.Surface.Center), App.Rotation())


def _c_PointEdgePlane(refs, points, values, spec):
    o, n = plane_of(refs[1])
    kind, p, d, edge = _line_or_edge(refs[0])
    if kind == "line":
        denom = d.dot(n)
        if abs(denom) < 1e-9:
            raise ConstructError("The line runs along the plane: they never cross.")
        t = (o - p).dot(n) / denom
        return App.Placement(p + d * t, App.Rotation())
    import Part

    box = edge.BoundBox
    size = 4 * box.DiagonalLength + (box.Center - o).Length + 10.0
    x = any_perpendicular(n)
    y = n.cross(x)
    corner = o - x * size - y * size
    plane = Part.makePlane(2 * size, 2 * size, corner, n, x)
    section = edge.section(plane)
    if not section.Vertexes:
        raise ConstructError("The edge does not cross the plane: pick ones that meet.")
    start = edge.valueAt(edge.FirstParameter)
    best = min(section.Vertexes, key=lambda vx: (vx.Point - start).Length)
    return App.Placement(best.Point, App.Rotation())


def _c_PointAlongPath(refs, points, values, spec):
    p, _t, _edge = _path_frame(refs, values)
    return App.Placement(p, App.Rotation())


# -- the helper ----------------------------------------------------------------------------
class ConstructionFrame:
    """The hidden frame a SciForge construction is attached to (see the module text).
    Saved documents store "sciforge.construct.ConstructionFrame": keep the name stable."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        props = obj.PropertiesList
        add = [
            ("App::PropertyString", "Kind", "The CONSTRUCT entry"),
            ("App::PropertyLinkSubListGlobal", "Refs", "What it is built on"),
            ("App::PropertyVectorList", "Points", "Where each pick was clicked (global)"),
            ("App::PropertyBoolList", "HasPoint", "Which picks have a clicked point"),
            ("App::PropertyDistance", "Distance", "Offset or distance along the path"),
            ("App::PropertyAngle", "Angle", "Angle"),
            ("App::PropertyFloat", "Fraction", "Proportional distance along the path (0..1)"),
            ("App::PropertyString", "DistanceType", "proportional or physical"),
        ]
        for kind, name, doc in add:
            if name not in props:
                obj.addProperty(kind, name, "Construction", doc)
        if "SciForgeTimeline" not in props:
            obj.addProperty("App::PropertyBool", "SciForgeTimeline", "SciForge", "Not a step")
            obj.SciForgeTimeline = False
        if "SciForgeRole" not in props:
            obj.addProperty("App::PropertyString", "SciForgeRole", "SciForge", "Helper of")
            obj.SciForgeRole = "ConstructionFrame"
        if "Problem" not in props:
            obj.addProperty("App::PropertyString", "Problem", "SciForge", "Why it stays put")
            _output(obj, "Problem")

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        """Work the frame out from the picks. When that is not possible any more (what it
        was built on was deleted, or an earlier edit made the picks unusable) the frame
        stays where it was and the construction shows a warning in the timeline, like a
        Fusion construction that lost its references. It never fails: a failed helper
        stopped its whole body from recomputing, and the part vanished from the view."""
        refs = helper_refs(obj)
        try:
            if len(refs) < len(obj.HasPoint) or any(not alive(r[0]) for r in refs):
                raise LostReference(LOST)
            place = compute(obj.Kind, refs, helper_points(obj), helper_values(obj))
        except LostReference:
            report_problem(obj, LOST)
            return
        except Exception as exc:
            report_problem(obj, str(exc) or "This construction cannot be built any more.")
            return
        body = owner_body(obj)
        if body is not None:
            place = body.getGlobalPlacement().inverse().multiply(place)
        report_problem(obj, "")
        if not obj.Placement.isSame(place, 1e-12):
            obj.Placement = place

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def _output(obj, prop):
    """A worked-out property: writing it does not mark the object as changed."""
    try:
        obj.setPropertyStatus(prop, ["Output", "Hidden"])
    except Exception:
        pass


def users_of(helper):
    """The construction datums attached to `helper`."""
    found = []
    try:
        for obj in helper.InList:
            if obj.TypeId in DATUM_TYPES and helper_of(obj) is helper:
                found.append(obj)
    except Exception:
        pass
    return found


def report_problem(helper, text):
    """Keep `text` on the helper and show it as the timeline warning of its construction
    ("" clears both)."""
    text = text or ""
    if getattr(helper, "Problem", "") != text:
        helper.Problem = text
    for datum in users_of(helper):
        try:
            if WARNING not in datum.PropertiesList:
                if not text:
                    continue
                datum.addProperty("App::PropertyString", WARNING, "SciForge", "Timeline warning")
                _output(datum, WARNING)
            if getattr(datum, WARNING) != text:
                setattr(datum, WARNING, text)
        except Exception:
            continue


def expand(value):
    """[(obj, sub)] of a link-sub-list property's value. FreeCAD groups picks of the same
    object that follow each other into one entry (obj, (sub1, sub2)); the order stays."""
    refs = []
    for obj, subs in value or []:
        names = list(subs) if isinstance(subs, (list, tuple)) else [subs]
        for name in names or [""]:
            refs.append((obj, name or ""))
    return refs


def helper_refs(helper):
    return expand(helper.Refs)


def helper_points(helper):
    """The clicked point of each pick (None where there is none). helper.Refs groups picks
    of the same object into one entry, so count the picks themselves."""
    flags = list(helper.HasPoint)
    points = list(helper.Points)
    count = len(helper_refs(helper))
    return [
        V(points[i]) if i < len(flags) and i < len(points) and flags[i] else None
        for i in range(count)
    ]


def helper_values(helper):
    return {
        "distance": float(helper.Distance.Value),
        "angle": float(helper.Angle.Value),
        "fraction": float(helper.Fraction),
        "distance_type": helper.DistanceType or "proportional",
    }


def is_helper(obj):
    return alive(obj) and type(getattr(obj, "Proxy", None)).__name__ == HELPER_CLASS


def helper_of(datum):
    try:
        for obj, _subs in datum.AttachmentSupport:
            if is_helper(obj):
                return obj
    except Exception:
        pass
    return None


# -- making and editing --------------------------------------------------------------------
def target_body(refs, fallback=None):
    """The body the construction goes in: the one its first pick belongs to (Fusion puts
    construction geometry in the component of what it is built on), else `fallback`."""
    for ref in refs:
        if ref is None:
            continue
        body = owner_body(ref[0])
        if body is not None:
            return body
    return fallback


def _native(key, body, refs):
    """Offset Plane on geometry of its own body: FreeCAD's FlatFace does exactly that."""
    if key != "OffsetPlane" or not refs:
        return False
    obj = refs[0][0]
    return owner_body(obj) is body


def next_number(doc, type_id):
    """The number of the next Plane / Axis / Point (Fusion: Plane1, Plane2, ...)."""
    import re

    base = SHORT_NAMES[type_id]
    used = 0
    for obj in doc.Objects:
        if obj.TypeId != type_id:
            continue
        match = re.match(r"^%s\s*(\d+)$" % base, obj.Label or "")
        if match:
            used = max(used, int(match.group(1)))
    return used + 1


def next_label(doc, type_id):
    """Fusion's names: Plane1, Plane2, ... Axis1, Point1."""
    return "%s%d" % (SHORT_NAMES[type_id], next_number(doc, type_id))


def default_values(key):
    spec = SPECS[key]
    values = {"distance": 0.0, "angle": 0.0, "fraction": 0.5, "distance_type": "proportional"}
    if spec["value"] == "distance":
        values["distance"] = spec.get("default", 0.0)
    elif spec["value"] == "angle":
        values["angle"] = spec.get("default", 0.0)
    elif spec["value"] == "path":
        values["fraction"] = spec.get("default", 0.5)
    return values


def make(body, key, refs, values=None, points=None, offset=None):
    """New construction datum `key` in `body` (or the body of the first pick) on `refs`.
    `offset` is the old way of passing the distance."""
    if key not in SPECS:
        raise ConstructError("Unknown construction %r." % key)
    values = dict(default_values(key), **(values or {}))
    if offset is not None:
        values["distance"] = float(offset)
    refs = [normalize_pick(r[0], r[1]) for r in refs if r is not None]
    compute(key, refs, points, values)  # refuse what cannot be built before adding objects
    body = target_body(refs, body) or body
    if body is None:
        raise ConstructError("There is no body to put the construction in.")
    spec = SPECS[key]
    doc = body.Document
    datum = body.newObject(spec["type"], SHORT_NAMES[spec["type"]])
    labels.set_free(datum, SHORT_NAMES[spec["type"]], next_number(doc, spec["type"]))
    _mark(datum, key)
    update(datum, key, refs, values, points)
    return datum


def _mark(datum, key):
    if PROP_KEY not in datum.PropertiesList:
        datum.addProperty("App::PropertyString", PROP_KEY, "SciForge", "CONSTRUCT entry")
    setattr(datum, PROP_KEY, key)
    if PROP_REFS not in datum.PropertiesList:
        datum.addProperty("App::PropertyLinkSubListGlobal", PROP_REFS, "SciForge", "Built on")


def _same_refs(a, b):
    if len(a) != len(b):
        return False
    return all(x[0] is y[0] and (x[1] or "") == (y[1] or "") for x, y in zip(a, b))


def _link_list(refs):
    out = []
    for obj, sub in refs:
        out.append((obj, [sub] if sub else [""]))
    return out


def update(datum, key, refs, values=None, points=None, formulas=None):
    """Put `datum` on `refs` with `values` (the dialog calls this on every change)."""
    values = dict(default_values(key), **(values or {}))
    refs = [normalize_pick(r[0], r[1]) for r in refs if r is not None]
    points = list(points or [])
    points += [None] * (len(refs) - len(points))
    formulas = formulas or {}
    body = owner_body(datum)
    _mark(datum, key)
    if getattr(datum, PROP_KEY) != key:
        setattr(datum, PROP_KEY, key)
    if not _same_refs(expand(getattr(datum, PROP_REFS)), refs):
        setattr(datum, PROP_REFS, _link_list(refs))
    helper = helper_of(datum)
    if _native(key, body, refs):
        if helper is not None:
            _drop_helper(datum, helper)
        _set_support(datum, [refs[0]], "FlatFace")
        offset = App.Placement(V(0, 0, values["distance"]), App.Rotation())
        _set_expression(datum, ".AttachmentOffset.Base.z", formulas.get("distance"))
        if not formulas.get("distance") and not datum.AttachmentOffset.isSame(offset, 1e-12):
            datum.AttachmentOffset = offset
        _clear_warning(datum)  # picked again: no longer "lost what it was on"
        return datum
    _set_expression(datum, ".AttachmentOffset.Base.z", None)
    if not datum.AttachmentOffset.isIdentity():
        datum.AttachmentOffset = App.Placement()
    if helper is None:
        helper = _new_helper(datum)
    _fill_helper(helper, key, refs, points, values, formulas)
    mode = {
        "PartDesign::Plane": "ObjectXY",
        "PartDesign::Line": "ObjectZ",
        "PartDesign::Point": "ObjectOrigin",
    }[datum.TypeId]
    _set_support(datum, [(helper, "")], mode)
    return datum


def _clear_warning(datum):
    try:
        if WARNING in datum.PropertiesList and getattr(datum, WARNING):
            setattr(datum, WARNING, "")
    except Exception:
        pass


def _set_support(datum, refs, mode):
    try:
        current = expand(datum.AttachmentSupport)
    except Exception:
        current = []
    if not _same_refs(current, refs):
        datum.AttachmentSupport = _link_list(refs)
    if datum.MapMode != mode:
        datum.MapMode = mode


def _set_expression(obj, path, formula):
    """`formula` (bare parameter names, as typed) on obj's `path`, or none."""
    try:
        engine = dict(obj.ExpressionEngine)
    except Exception:
        engine = {}
    if formula:
        from . import parameters, parameters_core

        expr = parameters_core.to_freecad(formula, parameters.user_names(obj.Document))
        if engine.get(path) != expr:
            obj.setExpression(path, expr)
    elif path in engine:
        obj.setExpression(path, None)


def formula_of(obj, path):
    try:
        expr = dict(obj.ExpressionEngine).get(path, "")
    except Exception:
        return ""
    if not expr:
        return ""
    try:
        from . import parameters_core

        return parameters_core.from_freecad(expr)
    except Exception:
        return expr


def _new_helper(datum):
    doc = datum.Document
    helper = doc.addObject("Part::Part2DObjectPython", "ConstructionFrame")
    ConstructionFrame(helper)
    body = owner_body(datum)
    if body is not None:
        body.insertObject(helper, datum, False)
    helper.Label = "%s frame" % datum.Label
    try:
        if helper.ViewObject is not None:
            helper.ViewObject.Visibility = False
            helper.ViewObject.ShowInTree = False
    except Exception:
        pass
    return helper


def _drop_helper(datum, helper):
    """The construction no longer needs its helper (Offset Plane back on its own body)."""
    _set_support(datum, [], "Deactivated")
    body = owner_body(helper)
    try:
        if body is not None and helper in body.Group:
            body.removeObject(helper)
        datum.Document.removeObject(helper.Name)
    except Exception:
        pass


def _fill_helper(helper, key, refs, points, values, formulas):
    if helper.Kind != key:
        helper.Kind = key
    if not _same_refs(expand(helper.Refs), refs):
        helper.Refs = _link_list(refs)
    flags = [p is not None for p in points]
    vectors = [V(p) if p is not None else V() for p in points]
    if list(helper.HasPoint) != flags:
        helper.HasPoint = flags
    if [V(p) for p in helper.Points] != vectors:
        helper.Points = vectors
    for prop, name in (("Distance", "distance"), ("Angle", "angle"), ("Fraction", "fraction")):
        _set_expression(helper, prop, formulas.get(name))
        if formulas.get(name):
            continue
        current = getattr(helper, prop)
        current = float(getattr(current, "Value", current))
        if abs(current - float(values[name])) > 1e-12:
            setattr(helper, prop, float(values[name]))
    kind = values.get("distance_type", "proportional")
    if helper.DistanceType != kind:
        helper.DistanceType = kind
    helper.touch()


def read(datum):
    """(key, refs, points, values, formulas) of a construction datum, for editing it. A
    datum not made by SciForge's CONSTRUCT gives its key from FreeCAD's attachment where
    that is clear, else None."""
    key = getattr(datum, PROP_KEY, "") or guess_key(datum)
    if not key or key not in SPECS:
        return None
    values = default_values(key)
    formulas = {}
    helper = helper_of(datum)
    if helper is not None:
        refs = helper_refs(helper)
        points = helper_points(helper)
        values.update(helper_values(helper))
        for prop, name in (("Distance", "distance"), ("Angle", "angle"), ("Fraction", "fraction")):
            text = formula_of(helper, prop)
            if text:
                formulas[name] = text
        return key, refs, points, values, formulas
    try:
        refs = [normalize_pick(o, s) for o, s in expand(datum.AttachmentSupport)]
    except Exception:
        refs = []
    points = [None] * len(refs)
    values["distance"] = float(datum.AttachmentOffset.Base.z)
    text = formula_of(datum, ".AttachmentOffset.Base.z")
    if text:
        formulas["distance"] = text
    return key, refs, points, values, formulas


def guess_key(datum):
    """Offset Plane for a datum plane FreeCAD attached flat to one face or plane with only a
    height offset (also what earlier SciForge versions made); None otherwise."""
    try:
        if datum.TypeId != "PartDesign::Plane" or datum.MapMode != "FlatFace":
            return None
        support = list(datum.AttachmentSupport)
        rot = datum.AttachmentOffset.Rotation
        base = datum.AttachmentOffset.Base
        if len(support) == 1 and rot.isIdentity() and abs(base.x) < EPS and abs(base.y) < EPS:
            return "OffsetPlane"
    except Exception:
        return None
    return None


def failure(datum):
    """The reason a construction does not compute, or ''."""
    helper = helper_of(datum)
    if helper is not None and getattr(helper, "Problem", ""):
        return helper.Problem
    for obj in (helper, datum):
        if obj is None:
            continue
        state = list(getattr(obj, "State", []))
        if "Invalid" in state or "Error" in state:
            try:
                text = obj.getStatusString()
            except Exception:
                text = ""
            return text or "This construction cannot be built on that selection."
    return ""


def delete(datum):
    """Remove a construction datum and its helper (a cancelled preview)."""
    doc = datum.Document
    helper = helper_of(datum)
    for obj in (datum, helper):
        if obj is None or not alive(obj):
            continue
        body = owner_body(obj)
        try:
            if body is not None and obj in body.Group:
                body.removeObject(obj)
            doc.removeObject(obj.Name)
        except Exception:
            pass
