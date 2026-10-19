# SPDX-License-Identifier: LGPL-2.1-or-later
"""Design steps for CONSTRUCT and INSPECT, built with the same SciForge code the dialogs
use (sciforge/construct.py, measure.py, section.py, analysis.py), registered on
core.Builder when the package is imported. The golden models' checks that measure with
these picks (construct_expect, measure_expect, section_expect, com_expect,
interference_expect) are in SciForgeTests/golden/checks.py.

A pick ("ref") is one of:
  {"plane": "XY"|"XZ"|"YZ"}  {"axis": "X"|"Y"|"Z"}  {"origin": true}   the origin
  {"face": selector}  {"edge": selector}                                 the part now
  {"vertex": [x, y, z]}                                                  a corner of it
  {"construct": "p1"}                                                    an earlier construction

  {"op": "construct", "id": "p1", "preset": "OffsetPlane", "refs": [ref, ...],
   "values": {"distance": 5, "angle": 30, "fraction": 0.5, "distance_type": "physical"},
   "points": [[x, y, z] | null, ...]}            (where a face was clicked, per ref)
  {"op": "construct_extrude", "id": "e2", "plane": "p1", "circles": [[x, y, z, r], ...],
   "distance": 5, "operation": "join", "direction": "one_side"|"symmetric", "flip": false}
      Create Sketch on the construction plane with circles centred at global points on it
      (circles: where the plane's own axes point does not matter), then Extrude
  {"op": "body_material", "feature": "e2", "material": "aluminium"}
      the Physical Material of that step's body (a key of sciforge/material.py LIBRARY), set
      the way the Physical Material dialog does (material.assign)
"""
import FreeCAD as App

from . import selectors
from .core import Builder, BuildError, _circle

V = App.Vector
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


def op_body_material(self, step):
    from sciforge import material

    bodies = _bodies(self, {"op": step["op"], "features": [step["feature"]]})
    try:
        material.assign(bodies[0], step["material"])
    except material.MaterialError as exc:
        raise BuildError("body_material: %s" % exc)
    self.doc.recompute()


for _name, _fn in list(globals().items()):
    if _name.startswith("op_") and callable(_fn):
        setattr(Builder, _name, _fn)
