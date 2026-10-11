# SPDX-License-Identifier: LGPL-2.1-or-later
"""Golden-model steps for Fusion's Sweep, Loft, Rib and Web, built with the same SciForge code
their dialogs use (sciforge/sweep.py, loft.py, rib.py). Registered on builder.Builder when
builder.py is imported.

  {"op": "sf_curves", "id": "p1", "plane": "XZ", "offset": 0,
   "curves": [{"line": [x1, y1, x2, y2]}, {"arc": [cx, cy, r, a0, a1]}, {"point": [x, y]},
              {"circle": [cx, cy, r]}, {"polyline": [[x, y], ...]}]}
      a sketch with open curves (paths, rails, rib curves) and points; arcs run counter-
      clockwise from a0 to a1 (degrees); a polyline stays open.

  {"op": "sf_sweep", "id": "w1", "profile": "s1" | "regions": [[x, y]] | "face": selector,
   "path": <curves>, "rail": <curves>, "type": "single" | "rail", "distance": 1,
   "distance2": 1, "taper": 0, "twist": 0, "orientation": "perpendicular" | "parallel",
   "scaling": "scale" | "stretch" | "none", "operation": "auto" | join | cut | intersect |
   new_body}
      <curves>  "p1"                             every curve of sketch p1
                {"sketch": "p1", "at": [x, y]}   the curve through that sketch point and
                                                 the curves joined to it smoothly (Fusion's
                                                 Chain Selection; "chain": false for just it)
                {"edge": selector}               edges of the part as it is now
      profile   a sketch step (its one area, like the dialog takes it; a sketch with several
                areas is taken whole), "regions" to click areas of "profile", or "face"

  {"op": "sf_sweep_edit", "target": "w1", "set": {"distance": 0.5, ...}}
      double-click the sweep in the timeline and change these options.
"""
import math

import FreeCAD as App
import Part

from . import selectors
from .builder import _PLANE_ROLE, Builder, BuildError

SWEEP_KEYS = (
    "type",
    "distance",
    "distance2",
    "taper",
    "twist",
    "orientation",
    "scaling",
    "operation",
)


def op_sf_curves(self, step):
    sketch = self.body.newObject("Sketcher::SketchObject", step["id"])
    sketch.AttachmentSupport = (self._origin(_PLANE_ROLE[step["plane"]]), [""])
    sketch.MapMode = "FlatFace"
    if step.get("offset"):
        sketch.AttachmentOffset = App.Placement(App.Vector(0, 0, step["offset"]), App.Rotation())
    for item in step["curves"]:
        if "line" in item:
            x1, y1, x2, y2 = item["line"]
            sketch.addGeometry(Part.LineSegment(App.Vector(x1, y1, 0), App.Vector(x2, y2, 0)))
        elif "arc" in item:
            cx, cy, r, a0, a1 = item["arc"]
            circle = Part.Circle(App.Vector(cx, cy, 0), App.Vector(0, 0, 1), r)
            sketch.addGeometry(Part.ArcOfCircle(circle, math.radians(a0), math.radians(a1)))
        elif "circle" in item:
            cx, cy, r = item["circle"]
            sketch.addGeometry(Part.Circle(App.Vector(cx, cy, 0), App.Vector(0, 0, 1), r))
        elif "point" in item:
            x, y = item["point"]
            sketch.addGeometry(Part.Point(App.Vector(x, y, 0)))
        elif "polyline" in item:
            pts = item["polyline"]
            for a, b in zip(pts, pts[1:]):
                sketch.addGeometry(
                    Part.LineSegment(App.Vector(a[0], a[1], 0), App.Vector(b[0], b[1], 0))
                )
        else:
            raise BuildError("sf_curves %r: unknown curve %r" % (step["id"], item))
    self.objects[step["id"]] = sketch
    self.ops[step["id"]] = "sf_curves"
    self.doc.recompute()
    if "Invalid" in list(sketch.State):
        raise BuildError("sf_curves %r: the sketch is invalid" % step["id"])
    return sketch


def _sketch(builder, name, where):
    sketch = builder.objects.get(name)
    if sketch is None or builder.ops.get(name) not in ("sketch", "sf_curves"):
        raise BuildError("%s: %r is not a sketch step" % (where, name))
    return sketch


def curves_of(builder, spec, where):
    """Curve references for a path / rail / rib spec (see the module text)."""
    from sciforge import curves

    if isinstance(spec, str):
        return curves.normalize([(_sketch(builder, spec, where), "")])
    if "edge" in spec:
        tip = builder._tip()
        names = selectors.select(tip.Shape, spec["edge"], "edges")
        if not names:
            raise BuildError("%s: the edge selector picks nothing" % where)
        return [(tip, n) for n in names]
    sketch = _sketch(builder, spec["sketch"], where)
    found = []
    for at in spec["at"] if isinstance(spec["at"][0], list) else [spec["at"]]:
        point = sketch.getGlobalPlacement().multVec(App.Vector(at[0], at[1], 0))
        probe = Part.Vertex(point)
        hit = None
        for i, edge in enumerate(sketch.Shape.Edges, start=1):
            if edge.distToShape(probe)[0] < 1e-6:
                hit = "Edge%d" % i
                break
        if hit is None:
            raise BuildError("%s: no curve of %s through %s" % (where, spec["sketch"], at))
        names = curves.chain(sketch, hit) if spec.get("chain", True) else [hit]
        found += [(sketch, n) for n in names]
    return curves.normalize(found)


def profiles_of(builder, step, where):
    from sciforge import extrude

    if "face" in step:
        tip = builder._tip()
        names = selectors.select(tip.Shape, step["face"], "faces")
        if len(names) != 1:
            raise BuildError("%s: 'face' must select one face" % where)
        return [(tip, names[0])]
    sketch = _sketch(builder, step["profile"], where)
    if "regions" in step:
        return [builder._region(step, [sketch], point) for point in step["regions"]]
    areas = extrude.regions(sketch)
    if len(areas) == 1:
        return [(sketch, areas[0][0])]
    return [(sketch, "")]


def _settle(builder, step, feature, owner_body):
    builder.objects[step["id"]] = feature
    builder.ops[step["id"]] = step["op"]
    body = owner_body(feature)
    if body is not None and body is not builder.body:
        builder.body = body  # Fusion: a new body becomes the one you work on
    builder._recompute(step, feature)
    return feature


def op_sf_sweep(self, step):
    from sciforge import curves, sweep

    where = "sf_sweep %r" % step["id"]
    profiles = profiles_of(self, step, where)
    path = curves_of(self, step["path"], where)
    rail = curves_of(self, step["rail"], where) if "rail" in step else []
    options = {k: step[k] for k in SWEEP_KEYS if k in step}
    if options.get("operation", "auto") == "auto":
        tip = self.body.Tip
        base = None
        if tip is not None and not tip.Shape.isNull():
            base = curves.to_global(tip.Shape, tip)
        options["operation"] = sweep.auto_operation(base, profiles, path, rail, options)
    try:
        feature = sweep.make(profiles, path, options, rail, step["id"])
    except (sweep.SweepError, curves.CurveError) as exc:
        raise BuildError("%s: %s" % (where, exc))
    return _settle(self, step, feature, sweep.owner_body)


def _edit(builder, step, op, module, error_types):
    target = builder.objects.get(step["target"])
    if target is None or builder.ops.get(step["target"]) != op:
        raise BuildError("%s_edit: %r is not a %s step" % (op, step["target"], op))
    try:
        feature = module.update(target, options=dict(step["set"]))
    except error_types as exc:
        raise BuildError("%s_edit %r: %s" % (op, step["target"], exc))
    builder.objects[step["target"]] = feature
    body = module.owner_body(feature)
    if body is not None:
        builder.body = body
    builder.doc.recompute()
    broken = [o.Label for o in builder.body.Group if "Invalid" in list(getattr(o, "State", []))]
    if broken:
        raise BuildError(
            "after editing %r these features broke: %s" % (step["target"], ", ".join(broken))
        )
    return feature


def op_sf_sweep_edit(self, step):
    from sciforge import curves, sweep

    return _edit(self, step, "sf_sweep", sweep, (sweep.SweepError, curves.CurveError))


Builder.op_sf_curves = op_sf_curves
Builder.op_sf_sweep = op_sf_sweep
Builder.op_sf_sweep_edit = op_sf_sweep_edit
