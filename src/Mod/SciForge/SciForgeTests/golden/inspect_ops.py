# SPDX-License-Identifier: LGPL-2.1-or-later
"""Golden-model steps for CONSTRUCT and INSPECT, built with the same SciForge code the dialogs
use (sciforge/construct.py, measure.py, section.py, analysis.py), registered on
builder.Builder when builder.py is imported. The *_expect steps measure something that is
not the part itself (a construction plane, a distance, a section, a centre of mass, an
interference) and fail the model with the difference when it is off.

A pick ("ref") is one of:
  {"plane": "XY"|"XZ"|"YZ"}  {"axis": "X"|"Y"|"Z"}  {"origin": true}   the origin
  {"face": selector}  {"edge": selector}                                 the part now
  {"vertex": [x, y, z]}                                                  a corner of it
  {"construct": "p1"}                                                    an earlier construction

  {"op": "construct", "id": "p1", "preset": "OffsetPlane", "refs": [ref, ...],
   "values": {"distance": 5, "angle": 30, "fraction": 0.5, "distance_type": "physical"},
   "points": [[x, y, z] | null, ...]}            (where a face was clicked, per ref)
  {"op": "construct_expect", "target": "p1", "point": [x, y, z],
   "normal": [x, y, z] | "direction": [x, y, z]}
      planes: point lies on the plane, normal either way round; axes: point on the line,
      direction either way round; points: the point itself
  {"op": "construct_extrude", "id": "e2", "plane": "p1", "circles": [[x, y, z, r], ...],
   "distance": 5, "operation": "join", "direction": "one_side"|"symmetric", "flip": false}
      Create Sketch on the construction plane with circles centred at global points on it
      (circles: where the plane's own axes point does not matter), then Extrude
  {"op": "measure_expect", "a": ref, "b": ref, "distance": d, "angle": deg}
  {"op": "section_expect", "plane": ref, "distance": 0, "x_angle": 0, "y_angle": 0,
   "flip": false, "kept_volume": v, "cap_area": a}
  {"op": "com_expect", "features": ["e1"] (their bodies; none = every body), "point": [x, y, z]}
  {"op": "interference_expect", "features": ["e1", "e2"], "include_coincident": false,
   "volume": v, "pairs": n}
"""
import FreeCAD as App

from . import selectors
from .builder import Builder, BuildError, _circle

V = App.Vector
TOL = 1e-6
_PLANE_ROLE = {"XY": "XY_Plane", "XZ": "XZ_Plane", "YZ": "YZ_Plane"}
_AXIS_ROLE = {"X": "X_Axis", "Y": "Y_Axis", "Z": "Z_Axis"}


def _ref(builder, spec, what):
    if "plane" in spec:
        return (builder._origin(_PLANE_ROLE[spec["plane"]]), "")
    if "axis" in spec:
        return (builder._origin(_AXIS_ROLE[spec["axis"]]), "")
    if spec.get("origin"):
        return (builder._origin("Origin"), "")
    if "construct" in spec:
        obj = builder.objects.get(spec["construct"])
        if obj is None:
            raise BuildError("%s: no construction %r" % (what, spec["construct"]))
        return (obj, "")
    tip = builder._tip()
    if "face" in spec or "edge" in spec:
        kind = "faces" if "face" in spec else "edges"
        names = selectors.select(tip.Shape, spec["face" if "face" in spec else "edge"], kind)
        if len(names) != 1:
            raise BuildError("%s: the selector must pick one element, got %s" % (what, names))
        return (tip, names[0])
    if "vertex" in spec:
        point = V(*spec["vertex"])
        for i, vertex in enumerate(tip.Shape.Vertexes, start=1):
            if (vertex.Point - point).Length < 1e-6:
                return (tip, "Vertex%d" % i)
        raise BuildError("%s: no corner at %s" % (what, spec["vertex"]))
    raise BuildError("%s: unknown pick %r" % (what, spec))


def op_construct(self, step):
    from sciforge import construct

    refs = [_ref(self, spec, "construct %r" % step["id"]) for spec in step["refs"]]
    points = [V(*p) if p is not None else None for p in step.get("points", [])]
    try:
        datum = construct.make(self.body, step["preset"], refs, step.get("values"), points)
    except construct.ConstructError as exc:
        raise BuildError("construct %r: %s" % (step["id"], exc))
    self.doc.recompute()
    problem = construct.failure(datum)
    if problem:
        raise BuildError("construct %r: %s" % (step["id"], problem))
    self.objects[step["id"]] = datum
    self.ops[step["id"]] = "construct"
    return datum


def _parallel(a, b):
    a, b = V(a), V(b)
    a.normalize()
    b.normalize()
    return a.cross(b).Length < 1e-7


def op_construct_expect(self, step):
    datum = self.objects.get(step["target"])
    if datum is None or self.ops.get(step["target"]) != "construct":
        raise BuildError("construct_expect: %r is not a construct step" % step["target"])
    gp = datum.getGlobalPlacement()
    z = gp.Rotation.multVec(V(0, 0, 1))
    point = V(*step["point"])
    problems = []
    if datum.TypeId == "PartDesign::Plane":
        gap = abs((point - gp.Base).dot(z))
        if gap > TOL:
            problems.append("the point is %.6g from the plane" % gap)
        if "normal" in step and not _parallel(z, step["normal"]):
            problems.append("normal %s, expected %s" % (z, step["normal"]))
    elif datum.TypeId == "PartDesign::Line":
        gap = (point - gp.Base).cross(z).Length
        if gap > TOL:
            problems.append("the point is %.6g from the axis" % gap)
        if "direction" in step and not _parallel(z, step["direction"]):
            problems.append("direction %s, expected %s" % (z, step["direction"]))
    else:
        if (gp.Base - point).Length > TOL:
            problems.append("point at %s, expected %s" % (gp.Base, point))
    if problems:
        raise BuildError("construct_expect %r: %s" % (step["target"], "; ".join(problems)))


def op_construct_extrude(self, step):
    from sciforge import extrude

    plane = self.objects.get(step["plane"])
    if plane is None or plane.TypeId != "PartDesign::Plane":
        raise BuildError("construct_extrude: %r is not a construction plane" % step["plane"])
    sketch = self.body.newObject("Sketcher::SketchObject", step["id"] + "_sketch")
    sketch.AttachmentSupport = [(plane, "")]
    sketch.MapMode = "FlatFace"
    self.doc.recompute()
    inverse = sketch.getGlobalPlacement().inverse()
    for i, (x, y, z, r) in enumerate(step["circles"]):
        local = inverse.multVec(V(x, y, z))
        if abs(local.z) > 1e-6:
            raise BuildError("construct_extrude %r: circle %d is off the plane" % (step["id"], i))
        _circle(sketch, "c%d" % i, local.x, local.y, r)
    self.doc.recompute()
    distance = float(step.get("distance", 1.0))
    options = {
        "operation": step.get("operation", "join"),
        "direction": step.get("direction", "one_side"),
        "extent": "distance",
        "distance": -distance if step.get("flip") else distance,
        "distance2": distance,
        "taper": 0.0,
        "extent2": "distance",
        "taper2": 0.0,
        "measurement": "whole",
        "start": "profile",
        "start_offset": 0.0,
    }
    try:
        feature = extrude.make(self.body, sketch, options, step["id"])
    except extrude.ExtrudeError as exc:
        raise BuildError("construct_extrude %r: %s" % (step["id"], exc))
    self.objects[step["id"]] = feature
    self.ops[step["id"]] = "extrude"
    body = extrude.owner_body(feature)
    if body is not None and body is not self.body:
        self.body = body
    self._recompute(step, feature)
    return feature


def _close(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def op_measure_expect(self, step):
    from sciforge import measure

    a = _ref(self, step["a"], "measure_expect a")
    b = _ref(self, step["b"], "measure_expect b")
    try:
        r = measure.relation(measure.entity(*a), measure.entity(*b))
    except measure.MeasureError as exc:
        raise BuildError("measure_expect: %s" % exc)
    problems = []
    if "distance" in step and not _close(r["distance"], step["distance"]):
        problems.append("distance %.9g, expected %.9g" % (r["distance"], step["distance"]))
    if "angle" in step and (r["angle"] is None or not _close(r["angle"], step["angle"])):
        problems.append("angle %s, expected %.9g" % (r["angle"], step["angle"]))
    if problems:
        raise BuildError("measure_expect: %s" % "; ".join(problems))


def op_section_expect(self, step):
    from sciforge import section

    ref = _ref(self, step["plane"], "section_expect")
    try:
        place = section.cut_frame(
            ref,
            step.get("distance", 0.0),
            step.get("x_angle", 0.0),
            step.get("y_angle", 0.0),
            step.get("flip", False),
        )
    except section.SectionError as exc:
        raise BuildError("section_expect: %s" % exc)
    shape = self.body.Shape
    problems = []
    if "kept_volume" in step:
        kept = section.kept_volume(shape, place)
        if not _close(kept, step["kept_volume"]):
            problems.append("kept volume %.9g, expected %.9g" % (kept, step["kept_volume"]))
    if "cap_area" in step:
        area = sum(f.Area for f in section.cap_faces(shape, place))
        if not _close(area, step["cap_area"]):
            problems.append("cut face %.9g, expected %.9g" % (area, step["cap_area"]))
    if problems:
        raise BuildError("section_expect: %s" % "; ".join(problems))


def _bodies(builder, step):
    from sciforge import analysis

    found = []
    for name in step.get("features", []):
        obj = builder.objects.get(name)
        body = analysis.body_of(obj) if obj is not None else None
        if body is None:
            raise BuildError("%s: step %r has no body" % (step["op"], name))
        if body not in found:
            found.append(body)
    return found


def op_com_expect(self, step):
    from sciforge import analysis

    obj = analysis.make_com(self.doc, _bodies(self, step))
    self.doc.recompute()
    try:
        if "Invalid" in list(obj.State):
            raise BuildError("com_expect: %s" % obj.getStatusString())
        point = V(*step["point"])
        if (obj.Position - point).Length > TOL:
            raise BuildError("com_expect: centre at %s, expected %s" % (obj.Position, point))
    finally:
        self.doc.removeObject(obj.Name)


def op_interference_expect(self, step):
    from sciforge import analysis

    obj = analysis.make_interference(
        self.doc, _bodies(self, step), step.get("include_coincident", False)
    )
    self.doc.recompute()
    try:
        if "Invalid" in list(obj.State):
            raise BuildError("interference_expect: %s" % obj.getStatusString())
        found = analysis.results(obj)
        problems = []
        if "pairs" in step and len(found) != step["pairs"]:
            problems.append("%d pairs, expected %d" % (len(found), step["pairs"]))
        if "volume" in step:
            total = sum(v for _a, _b, v in found)
            if not _close(total, step["volume"]):
                problems.append("overlap %.9g, expected %.9g" % (total, step["volume"]))
        if problems:
            raise BuildError("interference_expect: %s" % "; ".join(problems))
    finally:
        self.doc.removeObject(obj.Name)


for _name, _fn in list(globals().items()):
    if _name.startswith("op_") and callable(_fn):
        setattr(Builder, _name, _fn)
