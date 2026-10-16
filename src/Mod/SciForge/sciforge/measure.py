# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Measure, the maths: what one picked thing measures (length, area, volume,
position...) and what two picked things measure together (minimum distance, angle, the X / Y /
Z parts of the distance). No Qt code; measure_ui.py shows it and the unit tests call it.

Everything is in global coordinates and millimetres (and degrees); fmt() turns a value into
the text Fusion shows in the design's units with the chosen precision.

Picks:
  point   a corner, a sketch point, a construction / origin point, a snap point
  edge    an edge or sketch curve (length; radius / diameter when round)
  face    a face (area; radius / diameter when round)
  body    a whole body (volume, area)
  plane   a construction / origin plane (endless)
  axis    a construction / origin axis (endless)
"""
import math

try:
    import FreeCAD as App

    V = App.Vector
except ImportError:  # unit tests of the formatting run without FreeCAD
    App = V = None

PLANE_TYPES = ("App::Plane", "PartDesign::Plane", "Part::DatumPlane")
LINE_TYPES = ("App::Line", "PartDesign::Line", "Part::DatumLine")
POINT_TYPES = ("App::Point", "PartDesign::Point", "Part::DatumPoint")

# Fusion's design units -> millimetres per unit
UNIT_MM = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4, "ft": 304.8}
PRECISIONS = ["0", "0.1", "0.12", "0.123", "0.1234", "0.12345", "0.123456", "0.1234567"]
DEFAULT_PRECISION = 3


class MeasureError(ValueError):
    pass


class Entity:
    """One pick. kind: point / edge / face / body / plane / axis. shape: a Part shape in
    global coordinates (None for endless planes and axes, which keep origin + direction)."""

    def __init__(self, kind, obj=None, sub="", shape=None, point=None, direction=None, label=""):
        self.kind = kind
        self.obj = obj
        self.sub = sub
        self.shape = shape
        self.point = point  # a point's position, a plane's / axis' origin
        self.direction = direction  # a plane's normal, an axis' direction
        self.label = label

    def key(self):
        if self.obj is None:
            return ("snap", round(self.point.x, 9), round(self.point.y, 9), round(self.point.z, 9))
        return (self.obj.Name, self.sub)


# -- turning a pick into an entity ---------------------------------------------------------------
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


def global_element(obj, sub):
    try:
        item = obj.Shape.getElement(sub).copy()
    except Exception:
        raise MeasureError("%s %s is no longer there." % (obj.Label, sub))
    place = _parent_placement(obj)
    if not place.isIdentity():
        item.transformShape(place.toMatrix())
    return item


def global_shape(obj):
    shape = obj.Shape.copy()
    place = _parent_placement(obj)
    if not place.isIdentity():
        shape.transformShape(place.toMatrix())
    return shape


def body_of(obj):
    """The body a pick belongs to (the body itself for a body)."""
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


def entity(obj, sub="", point=None, whole_body=False):
    """The Entity for a pick (object, element name, picked point). whole_body: the body the
    pick belongs to (Selection Filter: Body)."""
    sub = (sub or "").split(".")[-1]
    if whole_body:
        body = body_of(obj)
        target = body if body is not None else obj
        # a body's Shape is placed by the body already; a loose solid by its parents
        shape = target.Shape.copy() if body is not None else global_shape(target)
        if shape.isNull() or not shape.Solids:
            raise MeasureError("%s has no solid to measure." % target.Label)
        return Entity("body", target, "", shape=shape, label=target.Label)
    if obj.TypeId in PLANE_TYPES:
        gp = obj.getGlobalPlacement()
        return Entity(
            "plane",
            obj,
            "",
            point=gp.Base,
            direction=gp.Rotation.multVec(V(0, 0, 1)),
            label=_name(obj),
        )
    if obj.TypeId in LINE_TYPES:
        gp = obj.getGlobalPlacement()
        local = V(1, 0, 0) if obj.TypeId == "App::Line" else V(0, 0, 1)
        return Entity(
            "axis", obj, "", point=gp.Base, direction=gp.Rotation.multVec(local), label=_name(obj)
        )
    if obj.TypeId in POINT_TYPES:
        gp = obj.getGlobalPlacement()
        return Entity("point", obj, "", point=gp.Base, label=_name(obj))
    if obj.TypeId == "PartDesign::Body" and not sub:
        return entity(obj, "", point, whole_body=True)
    if sub.startswith("Vertex"):
        item = global_element(obj, sub)
        return Entity("point", obj, sub, shape=item, point=item.Point, label=_label(obj, "point"))
    if sub.startswith("Edge"):
        item = global_element(obj, sub)
        return Entity("edge", obj, sub, shape=item, label=_label(obj, "edge"))
    if sub.startswith("Face"):
        item = global_element(obj, sub)
        return Entity("face", obj, sub, shape=item, point=point, label=_label(obj, "face"))
    if not sub:
        try:
            shape = global_shape(obj)
        except Exception:
            shape = None
        if shape is not None and not shape.isNull() and shape.Solids:
            return Entity("body", obj, "", shape=shape, label=obj.Label)
    raise MeasureError("%s cannot be measured." % obj.Label)


def component_of(obj):
    """The component (App::Part) a pick lies in: the nearest one holding it, or None at the
    design's root."""
    from . import components

    if obj is None:
        return None
    return components.component_of(obj)


def component_entity(component):
    """The Entity of a whole component (Selection Filter: Component): every solid of its
    bodies (and of the components inside it) where it shows in the design."""
    import Part

    from . import bodies, components

    solids = []
    for body in components.bodies_in(component.Document, component, recursive=True):
        if not bodies.alive(body) or not bodies.is_shown(body):
            continue
        try:
            shape = bodies.global_shape(body)
        except Exception:
            continue
        if shape is not None and not shape.isNull():
            solids += list(shape.Solids)
    if not solids:
        raise MeasureError("%s has no solid body to measure." % components.label_of(component))
    shape = Part.Compound(solids) if len(solids) > 1 else solids[0]
    return Entity("component", component, "", shape=shape, label=components.label_of(component))


def sketch_entity(sketch, name, point=None):
    """The Entity for a pick in a sketch that is open for editing. The sketch editor names
    its picks after the sketch's own lists, not after its shape: "Edge2" is the second curve
    (construction lines count, the shape leaves them out), "Vertex3" the third sketch point,
    "RootPoint" / "H_Axis" / "V_Axis" the sketch's origin and axes, "ExternalEdge1" the
    first projected curve."""
    name = (name or "").split(".")[-1]
    place = sketch.getGlobalPlacement()
    label = "%s %s" % (
        sketch.Label,
        "point" if "Vertex" in name or name == "RootPoint" else "curve",
    )
    try:
        if name == "RootPoint":
            return Entity("point", sketch, name, point=place.Base, label="%s origin" % sketch.Label)
        if name in ("H_Axis", "V_Axis"):
            local = V(1, 0, 0) if name == "H_Axis" else V(0, 1, 0)
            return Entity(
                "axis",
                sketch,
                name,
                point=place.Base,
                direction=place.Rotation.multVec(local),
                label="%s %s axis"
                % (sketch.Label, "horizontal" if name == "H_Axis" else "vertical"),
            )
        if name.startswith("Vertex"):
            geo, pos = sketch.getGeoVertexIndex(int(name[6:]) - 1)
            if geo < -1999:
                raise MeasureError("That sketch point is no longer there.")
            p = place.multVec(sketch.getPoint(geo, pos))
            return Entity("point", sketch, name, shape=None, point=p, label=label)
        if name.startswith("ExternalEdge"):
            curve = list(sketch.ExternalGeo)[int(name[12:]) + 1]
        elif name.startswith("Edge"):
            curve = list(sketch.Geometry)[int(name[4:]) - 1]
        else:
            raise MeasureError("%s cannot be measured." % name)
        shape = curve.toShape()
        shape.transformShape(place.toMatrix())
        return Entity("edge", sketch, name, shape=shape, label=label)
    except MeasureError:
        raise
    except Exception:
        raise MeasureError("That sketch element is no longer there.")


def snap_entity(point, label="Point"):
    return Entity("point", None, "", point=V(point), label=label)


def _name(obj):
    role = getattr(obj, "Role", "") or ""
    names = {
        "X_Axis": "X axis",
        "Y_Axis": "Y axis",
        "Z_Axis": "Z axis",
        "XY_Plane": "XY plane",
        "XZ_Plane": "XZ plane",
        "YZ_Plane": "YZ plane",
        "Origin": "Origin",
    }
    return names.get(role, obj.Label)


def _label(obj, word):
    body = body_of(obj)
    owner = body.Label if body is not None and obj.TypeId != "Sketcher::SketchObject" else obj.Label
    if obj.TypeId == "Sketcher::SketchObject":
        word = "sketch " + ("point" if word == "point" else "curve")
    return "%s %s" % (owner, word)


# -- what one entity measures ---------------------------------------------------------------------
def _round_kind(shape, kind):
    if kind == "edge":
        return type(shape.Curve).__name__ in ("Circle", "ArcOfCircle")
    if kind == "face":
        return type(shape.Surface).__name__ in ("Cylinder",)
    return False


def properties(e):
    """[(name, value, quantity)] that one entity shows. quantity: length / area / volume /
    angle / coordinate."""
    rows = []
    if e.kind == "point":
        p = e.point
        rows += [("X", p.x, "coordinate"), ("Y", p.y, "coordinate"), ("Z", p.z, "coordinate")]
    elif e.kind == "edge":
        rows.append(("Length", e.shape.Length, "length"))
        if _round_kind(e.shape, "edge"):
            r = e.shape.Curve.Radius
            rows += [("Radius", r, "length"), ("Diameter", 2 * r, "length")]
    elif e.kind == "face":
        rows.append(("Area", e.shape.Area, "area"))
        if _round_kind(e.shape, "face"):
            r = e.shape.Surface.Radius
            rows += [("Radius", r, "length"), ("Diameter", 2 * r, "length")]
        rows.append(("Perimeter", perimeter(e.shape), "length"))
    elif e.kind in ("body", "component"):
        rows += [("Volume", e.shape.Volume, "volume"), ("Area", e.shape.Area, "area")]
    elif e.kind == "plane":
        p = e.point
        rows += [("X", p.x, "coordinate"), ("Y", p.y, "coordinate"), ("Z", p.z, "coordinate")]
    elif e.kind == "axis":
        p = e.point
        rows += [("X", p.x, "coordinate"), ("Y", p.y, "coordinate"), ("Z", p.z, "coordinate")]
    return rows


def perimeter(face):
    """Length of a face's boundary: every edge of its outer wire except a seam (the line
    where a cylinder's or cone's surface closes on itself is no boundary: a round side of
    radius 5 and height 10 has the perimeter of its two circles, 62.832, not 72.832)."""
    total = 0.0
    seen = []
    for edge in face.OuterWire.Edges:
        try:
            if edge.isSeam(face):
                continue
        except Exception:
            pass
        if any(edge.isSame(other) for other in seen):
            continue
        seen.append(edge)
        total += edge.Length
    return total


# -- what two entities measure together ----------------------------------------------------------
def _direction(e):
    """('line', d) or ('plane', n) of an entity with a direction, else None."""
    if e.kind == "axis":
        return ("line", e.direction)
    if e.kind == "plane":
        return ("plane", e.direction)
    if e.kind == "edge" and type(e.shape.Curve).__name__ in ("Line", "LineSegment"):
        a = e.shape.valueAt(e.shape.FirstParameter)
        b = e.shape.valueAt(e.shape.LastParameter)
        return ("line", b - a)
    if e.kind == "face" and type(e.shape.Surface).__name__ == "Plane":
        u0, u1, v0, v1 = e.shape.ParameterRange
        return ("plane", e.shape.normalAt((u0 + u1) / 2, (v0 + v1) / 2))
    if e.kind == "face" and type(e.shape.Surface).__name__ in ("Cylinder", "Cone"):
        return ("line", e.shape.Surface.Axis)
    return None


def _acute(a, b):
    a, b = V(a), V(b)
    if a.Length < 1e-12 or b.Length < 1e-12:
        return None
    a.normalize()
    b.normalize()
    c = max(-1.0, min(1.0, abs(a.dot(b))))
    return math.degrees(math.acos(c))


def angle(e1, e2):
    """Angle between two entities that have a direction (lines, flat faces, planes, round
    faces' axes), 0..90 degrees; None when one of them has none."""
    d1, d2 = _direction(e1), _direction(e2)
    if d1 is None or d2 is None:
        return None
    a = _acute(d1[1], d2[1])
    if a is None:
        return None
    if d1[0] == d2[0]:
        return a
    return 90.0 - a  # a line against a plane: measured from the plane


def _proxy(e, other_box):
    """A finite shape for an endless plane or axis, big enough around `other_box`."""
    import Part

    reach = 1000.0
    if other_box is not None:
        reach = max(reach, 4 * other_box.DiagonalLength + (other_box.Center - e.point).Length)
    if e.kind == "plane":
        n = V(e.direction)
        n.normalize()
        x = V(1, 0, 0) if abs(n.x) < 0.9 else V(0, 1, 0)
        x = n.cross(x)
        x.normalize()
        y = n.cross(x)
        corner = e.point - x * reach - y * reach
        return Part.makePlane(2 * reach, 2 * reach, corner, n, x)
    d = V(e.direction)
    d.normalize()
    return Part.LineSegment(e.point - d * reach, e.point + d * reach).toShape()


def _shape(e, other):
    if e.shape is not None:
        return e.shape
    if e.kind in ("plane", "axis"):
        other_box = None
        if other is not None:
            if other.shape is not None:
                other_box = other.shape.BoundBox
            elif other.point is not None:
                import FreeCAD as A

                other_box = A.BoundBox(other.point, other.point)
        return _proxy(e, other_box)
    import Part

    return Part.Vertex(e.point)


def _plane_gap(e1, e2):
    """Distance between two parallel endless planes, or None."""
    if e1.kind != "plane" or e2.kind != "plane":
        return None
    n1, n2 = V(e1.direction), V(e2.direction)
    n1.normalize()
    n2.normalize()
    if n1.cross(n2).Length > 1e-9:
        return 0.0
    return abs((e2.point - e1.point).dot(n1))


def relation(e1, e2):
    """{"distance", "angle" (or None), "dx", "dy", "dz", "points": (p1, p2)} for two
    entities: the minimum distance between them and where it is."""
    gap = _plane_gap(e1, e2)
    if gap is not None and gap > 0:
        n = V(e1.direction)
        n.normalize()
        p1 = e1.point
        p2 = p1 + n * ((e2.point - p1).dot(n))
        dist, pts = gap, (p1, p2)
    else:
        s1, s2 = _shape(e1, e2), _shape(e2, e1)
        try:
            dist, pairs, _info = s1.distToShape(s2)
        except Exception as exc:
            raise MeasureError("Could not measure between these: %s" % exc)
        if not pairs:
            raise MeasureError("Could not measure between these.")
        pts = (V(pairs[0][0]), V(pairs[0][1]))
    delta = pts[1] - pts[0]
    return {
        "distance": float(dist),
        "angle": angle(e1, e2),
        "dx": abs(delta.x),
        "dy": abs(delta.y),
        "dz": abs(delta.z),
        "points": pts,
    }


def results(e1, e2):
    """[(name, value, quantity)] of two entities measured together."""
    r = relation(e1, e2)
    rows = [("Distance", r["distance"], "length")]
    if r["angle"] is not None:
        rows.append(("Angle", r["angle"], "angle"))
    rows += [
        ("Delta X", r["dx"], "length"),
        ("Delta Y", r["dy"], "length"),
        ("Delta Z", r["dz"], "length"),
    ]
    return rows, r


# -- snap points --------------------------------------------------------------------------------
def snap_points(e):
    """Points a person can snap to on an edge or a face: its ends, middle, the centre of a
    circle or arc, the centre of a flat face, the centres of a face's round edges."""
    found = []
    if e is None or e.shape is None:
        return found
    if e.kind == "edge":
        edge = e.shape
        found.append(("Start", edge.valueAt(edge.FirstParameter)))
        found.append(("End", edge.valueAt(edge.LastParameter)))
        try:
            middle = edge.valueAt(edge.getParameterByLength(edge.Length / 2.0))
        except Exception:
            middle = edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2.0)
        found.append(("Middle", middle))
        if type(edge.Curve).__name__ in ("Circle", "ArcOfCircle"):
            found.append(("Centre", V(edge.Curve.Center)))
    elif e.kind == "face":
        face = e.shape
        if type(face.Surface).__name__ == "Plane":
            found.append(("Centre", face.CenterOfMass))
        for edge in face.Edges:
            if type(edge.Curve).__name__ in ("Circle", "ArcOfCircle"):
                found.append(("Centre", V(edge.Curve.Center)))
    unique = []
    for name, p in found:
        if all((p - q).Length > 1e-7 for _n, q in unique):
            unique.append((name, p))
    return unique


# -- text ----------------------------------------------------------------------------------------
_POWER = {"length": 1, "coordinate": 1, "area": 2, "volume": 3}
_SUFFIX = {"area": "^2", "volume": "^3"}


def fmt(value, quantity, decimals=DEFAULT_PRECISION, unit="mm"):
    """Fusion-style text of a measured value in the design's unit."""
    decimals = max(0, min(8, int(decimals)))
    if quantity == "angle":
        return "%.*f deg" % (decimals, value)
    factor = UNIT_MM.get(unit, 1.0) ** _POWER.get(quantity, 1)
    text = "%.*f" % (decimals, value / factor)
    if text.startswith("-") and float(text) == 0.0:
        text = text[1:]
    return "%s %s%s" % (text, unit, _SUFFIX.get(quantity, ""))
