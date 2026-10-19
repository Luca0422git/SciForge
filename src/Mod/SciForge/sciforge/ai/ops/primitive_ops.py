# SPDX-License-Identifier: LGPL-2.1-or-later
"""Design steps for Fusion's Box, Cylinder, Sphere, Torus, Coil and Pipe, built with
the same SciForge code their dialogs use (sciforge/primitives.py, coil.py, pipe.py),
registered on core.Builder when the package is imported.

  {"op": "sf_primitive", "id": "b1", "kind": "box", "plane": "XY",
   "x": 0, "y": 0, "length": 40, "width": 20, "height": 10, "operation": "auto"}
      kind      box | cylinder | sphere | torus
      plane     "XY" / "XZ" / "YZ" (the current body's origin plane) or
                {"face": selector} (a flat face of the part, as clicked)
      options   as the dialog's fields, in the plane's own frame (see primitives.py):
                box x, y (first corner), sx, sy (+1/-1: the side the box goes to),
                length, width, height (signed); cylinder x, y, diameter, height;
                sphere x, y, diameter; torus x, y, inner_diameter, torus_diameter,
                position (inside / center / outside)
      operation auto (default: what the dialog picks by itself) | join | cut | intersect |
                new_body | new_component (a new component holding the new body)
      expressions {field: formula}: a parameter typed in that field (it keeps driving it;
                the field's value is what the formula gives when the step is made)

  {"op": "sf_coil", "id": "c1", "plane": "XY", "x": 0, "y": 0, "diameter": 20,
   "type": "rev_height", "revolutions": 4, "height": 20, "pitch": 5, "angle": 0,
   "clockwise": true, "section": "circular", "section_position": "inside",
   "section_size": 2, "operation": "auto"}

  {"op": "sf_path_sketch", "id": "p", "plane": "XY",
   "segments": [{"line": [[0, 0], [20, 0]]}, {"arc": [20, 10, 10, -90, 0]}]}
      an open path to follow (lines; arcs as centre x, y, radius, start and end angle
      in degrees, counterclockwise)

  {"op": "sf_pipe", "id": "pp", "path": {"sketch": "p", "edge": 1}, "chain": true,
   "distance": 1, "section": "circular", "section_size": 2, "hollow": false,
   "thickness": 0.5, "operation": "auto"}
      path      {"sketch": id, "edge": n}   the sketch's n-th curve (1 = first), with
                                            its chain when "chain" is true (default)
                {"edges": selector}         edges of the part (a model edge path)

  {"op": "sf_primitive_edit", "target": "b1", "set": {"height": -5}}
      double-click the step in the timeline and change these options (the step may
      change kind, e.g. AdditiveBox -> SubtractiveBox, like the dialog does)
"""
import math

import FreeCAD as App
import Part

from . import selectors
from .core import Builder, BuildError

PRIMITIVE_KEYS = (
    "x",
    "y",
    "sx",
    "sy",
    "length",
    "width",
    "height",
    "diameter",
    "inner_diameter",
    "torus_diameter",
    "position",
    "operation",
)
COIL_KEYS = (
    "x",
    "y",
    "type",
    "diameter",
    "clockwise",
    "revolutions",
    "height",
    "pitch",
    "angle",
    "section",
    "section_position",
    "section_size",
    "operation",
)
PIPE_KEYS = ("distance", "section", "section_size", "hollow", "thickness", "operation")
_PLANE_ROLE = {"XY": "XY_Plane", "XZ": "XZ_Plane", "YZ": "YZ_Plane"}


def _plane(builder, step):
    spec = step.get("plane", "XY")
    if isinstance(spec, str):
        for feature in builder.body.Origin.OriginFeatures:
            if feature.Role == _PLANE_ROLE[spec]:
                return (feature, "")
        raise BuildError("%s %r: no origin plane %r" % (step["op"], step["id"], spec))
    tip = builder._tip()
    names = selectors.select(tip.Shape, spec["face"], "faces")
    if len(names) != 1:
        raise BuildError("%s %r: 'plane' face must select one face" % (step["op"], step["id"]))
    return (tip, names[0])


def _settle(builder, step, feature, op):
    builder.objects[step["id"]] = feature
    builder.ops[step["id"]] = op
    body = feature.getParentGeoFeatureGroup()
    if body is not None and body is not builder.body:
        builder.body = body  # Fusion: a new body becomes the one you work on
    builder._recompute(step, feature)
    return feature


def _base(ref):
    from sciforge import primitives

    return primitives.base_shape(primitives.owner_body(ref[0]))


def op_sf_primitive(self, step):
    from sciforge import primitives

    kind = step["kind"]
    ref = _plane(self, step)
    options = {k: step[k] for k in PRIMITIVE_KEYS if k in step}
    options["expressions"] = dict(step.get("expressions", {}))
    try:
        if options.get("operation", "auto") == "auto":
            tool = primitives.tool_shape(kind, ref, dict(options, operation="join"))
            options["operation"] = primitives.auto_operation(_base(ref), tool)
        feature = primitives.make(kind, ref, options, name=step["id"])
    except primitives.PrimitiveError as exc:
        raise BuildError("sf_primitive %r: %s" % (step["id"], exc))
    return _settle(self, step, feature, "sf_primitive")


def op_sf_coil(self, step):
    from sciforge import coil, primitives

    ref = _plane(self, step)
    options = {k: step[k] for k in COIL_KEYS if k in step}
    options["expressions"] = dict(step.get("expressions", {}))
    try:
        if options.get("operation", "auto") == "auto":
            full = coil.with_defaults(dict(options, operation="join"))
            options["operation"] = coil.auto_operation(_base(ref), ref, full)
        feature = coil.make(ref, options, name=step["id"])
    except primitives.PrimitiveError as exc:
        raise BuildError("sf_coil %r: %s" % (step["id"], exc))
    return _settle(self, step, feature, "sf_coil")


def op_sf_path_sketch(self, step):
    sketch = self.body.newObject("Sketcher::SketchObject", step["id"])
    role = _PLANE_ROLE[step.get("plane", "XY")]
    plane = [f for f in self.body.Origin.OriginFeatures if f.Role == role][0]
    sketch.AttachmentSupport = (plane, [""])
    sketch.MapMode = "FlatFace"
    for segment in step["segments"]:
        if "line" in segment:
            (x0, y0), (x1, y1) = segment["line"]
            sketch.addGeometry(Part.LineSegment(App.Vector(x0, y0, 0), App.Vector(x1, y1, 0)))
        else:
            cx, cy, r, a0, a1 = segment["arc"]
            circle = Part.Circle(App.Vector(cx, cy, 0), App.Vector(0, 0, 1), r)
            sketch.addGeometry(Part.ArcOfCircle(circle, math.radians(a0), math.radians(a1)))
    self.objects[step["id"]] = sketch
    self.ops[step["id"]] = "sketch"
    self.doc.recompute()
    if "Invalid" in list(sketch.State):
        raise BuildError("sf_path_sketch %r is invalid" % step["id"])
    return sketch


def _path(builder, step):
    from sciforge import pipe

    spec = step["path"]
    chain = step.get("chain", True)
    if "edges" in spec:
        tip = builder._tip()
        names = selectors.select(tip.Shape, spec["edges"], "edges")
        if not names:
            raise BuildError("sf_pipe %r: the edge selector picked nothing" % step["id"])
        return pipe.expand([(tip, n) for n in names], chain)
    sketch = builder.objects.get(spec["sketch"])
    if sketch is None or builder.ops.get(spec["sketch"]) != "sketch":
        raise BuildError("sf_pipe %r: 'sketch' must name a sketch step" % step["id"])
    return pipe.expand([(sketch, "Edge%d" % int(spec.get("edge", 1)))], chain)


def op_sf_pipe(self, step):
    from sciforge import pipe, primitives

    path = _path(self, step)
    options = {k: step[k] for k in PIPE_KEYS if k in step}
    options["expressions"] = dict(step.get("expressions", {}))
    try:
        if options.get("operation", "auto") == "auto":
            src = pipe.source_body(path) or self.body
            tool = pipe.tool_shape(path, dict(options, operation="join"))
            options["operation"] = primitives.auto_operation(primitives.base_shape(src), tool)
        feature = pipe.make(path, options, name=step["id"])
    except primitives.PrimitiveError as exc:
        raise BuildError("sf_pipe %r: %s" % (step["id"], exc))
    return _settle(self, step, feature, "sf_pipe")


def op_sf_primitive_edit(self, step):
    from sciforge import coil, pipe, primitives

    target = self.objects.get(step["target"])
    kind = self.ops.get(step["target"])
    module = {"sf_primitive": primitives, "sf_coil": coil, "sf_pipe": pipe}.get(kind)
    if target is None or module is None:
        raise BuildError(
            "sf_primitive_edit: %r is not a primitive, coil or pipe step" % step["target"]
        )
    try:
        feature = module.update(target, options=dict(step["set"]))
    except primitives.PrimitiveError as exc:
        raise BuildError("sf_primitive_edit %r: %s" % (step["target"], exc))
    self.objects[step["target"]] = feature
    body = feature.getParentGeoFeatureGroup()
    if body is not None:
        self.body = body
    self.doc.recompute()
    broken = [o.Label for o in self.body.Group if "Invalid" in list(getattr(o, "State", []))]
    if broken:
        raise BuildError(
            "after editing %r these features broke: %s" % (step["target"], ", ".join(broken))
        )
    return feature


Builder.op_sf_primitive = op_sf_primitive
Builder.op_sf_coil = op_sf_coil
Builder.op_sf_path_sketch = op_sf_path_sketch
Builder.op_sf_pipe = op_sf_pipe
Builder.op_sf_primitive_edit = op_sf_primitive_edit
