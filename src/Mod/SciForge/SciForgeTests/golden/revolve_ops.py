# SPDX-License-Identifier: LGPL-2.1-or-later
"""Golden-model steps for Fusion's Revolve, built with the same SciForge code the Revolve
dialog uses (sciforge/revolve.py), registered on builder.Builder when builder.py is
imported.

  {"op": "sf_revolve", "id": "r1", "profile": "s1", "axis": "Z",
   "type": "angle", "direction": "one_side", "angle": 90, "angle2": 30,
   "operation": "auto"}
      profile   a sketch step (its one area, like the dialog takes it; a sketch with
                several areas is taken whole), "regions": [[x, y], ...] to click areas,
                or "face": a face selector on the part (a flat face as the profile)
      axis      "X" / "Y" / "Z"                      an origin axis
                {"sketch": id, "at": [x, y]}          the sketch line through that point
                {"sketch": id, "construction": [[x1, y1], [x2, y2]]}
                                                      draw a construction line, use it
                                                      ("name": n makes it vertical with a
                                                      dimension "n.x" an edit can change)
                {"sketch": id, "axis": "H" | "V"}     the sketch's own axis
                {"edge": selector}                    a straight edge of the part
      type      angle (default) | full
      direction one_side (default) | two_sides | symmetric
      angle     degrees (one side: signed; symmetric: each side), default 360
      angle2    degrees of side two
      operation auto (default: what the dialog picks by itself) | join | cut |
                intersect | new_body

  {"op": "sf_revolve_edit", "target": "r1", "set": {"angle": 45, "operation": "cut"}}
      double-click the revolve in the timeline and change these options (the feature
      may change kind, Revolution <-> Groove, like the dialog does).
"""

import FreeCAD as App
import Part

from . import selectors
from .builder import Builder, BuildError

OPTION_KEYS = ("type", "direction", "angle", "angle2", "operation")


def _profiles(builder, step):
    from sciforge import extrude

    if "face" in step:
        tip = builder._tip()
        names = selectors.select(tip.Shape, step["face"], "faces")
        if len(names) != 1:
            raise BuildError("sf_revolve %r: 'face' must select one face" % step["id"])
        return [(tip, names[0])]
    sketch = builder.objects[step["profile"]]
    if "regions" in step:
        return [builder._region(step, [sketch], point) for point in step["regions"]]
    areas = extrude.regions(sketch)
    if len(areas) == 1:
        return [(sketch, areas[0][0])]
    return [(sketch, "")]


def _axis(builder, step):
    from sciforge import revolve

    spec = step["axis"]
    if isinstance(spec, str):
        axes = revolve.origin_axes(builder.body)
        if spec not in axes:
            raise BuildError("sf_revolve %r: no origin axis %r" % (step["id"], spec))
        return (axes[spec], "")
    if "edge" in spec:
        tip = builder._tip()
        names = selectors.select(tip.Shape, spec["edge"], "edges")
        if len(names) != 1:
            raise BuildError("sf_revolve %r: the edge selector must pick one edge" % step["id"])
        return (tip, names[0])
    sketch = builder.objects.get(spec["sketch"])
    if sketch is None or builder.ops.get(spec["sketch"]) != "sketch":
        raise BuildError("sf_revolve %r: 'sketch' must name a sketch step" % step["id"])
    if "axis" in spec:
        return (sketch, {"H": "H_Axis", "V": "V_Axis"}[spec["axis"]])
    if "construction" in spec:
        (x1, y1), (x2, y2) = spec["construction"]
        geo = sketch.addGeometry(
            Part.LineSegment(App.Vector(x1, y1, 0), App.Vector(x2, y2, 0)), True
        )
        if "name" in spec:  # a vertical line dimensioned from the origin: "<name>.x"
            import Sketcher

            if abs(x1 - x2) > 1e-9:
                raise BuildError(
                    "sf_revolve %r: a named construction line is vertical" % step["id"]
                )
            sketch.addConstraint(Sketcher.Constraint("Vertical", geo))
            index = sketch.addConstraint(Sketcher.Constraint("DistanceX", -1, 1, geo, 1, x1))
            sketch.renameConstraint(index, spec["name"] + ".x")
        builder.doc.recompute()
        name = revolve.construction_lines(sketch)[-1][0]
        return (sketch, name)
    where = sketch.getGlobalPlacement().multVec(App.Vector(spec["at"][0], spec["at"][1], 0))
    probe = Part.Vertex(where)
    for i, edge in enumerate(sketch.Shape.Edges, start=1):
        if edge.distToShape(probe)[0] < 1e-6:
            return (sketch, "Edge%d" % i)
    raise BuildError("sf_revolve %r: no sketch line through %s" % (step["id"], spec["at"]))


def op_sf_revolve(self, step):
    from sciforge import revolve

    profiles = _profiles(self, step)
    axis = _axis(self, step)
    options = {k: step[k] for k in OPTION_KEYS if k in step}
    if options.get("operation", "auto") == "auto":
        tip = self.body.Tip
        base = None
        if tip is not None and not tip.Shape.isNull():
            base = revolve.to_global(tip.Shape, tip)
        try:
            options["operation"] = revolve.auto_operation(base, profiles, axis, options)
        except revolve.RevolveError as exc:
            raise BuildError("sf_revolve %r: %s" % (step["id"], exc))
    try:
        feature = revolve.make(profiles, axis, options, step["id"])
    except revolve.RevolveError as exc:
        raise BuildError("sf_revolve %r: %s" % (step["id"], exc))
    self.objects[step["id"]] = feature
    self.ops[step["id"]] = "sf_revolve"
    body = revolve.owner_body(feature)
    if body is not None and body is not self.body:
        self.body = body  # Fusion: a new body becomes the one you work on
    self._recompute(step, feature)
    return feature


def op_sf_revolve_edit(self, step):
    from sciforge import revolve

    target = self.objects.get(step["target"])
    if target is None or self.ops.get(step["target"]) != "sf_revolve":
        raise BuildError("sf_revolve_edit: %r is not a sf_revolve step" % step["target"])
    try:
        feature = revolve.update(target, options=dict(step["set"]))
    except revolve.RevolveError as exc:
        raise BuildError("sf_revolve_edit %r: %s" % (step["target"], exc))
    self.objects[step["target"]] = feature
    body = revolve.owner_body(feature)
    if body is not None:
        self.body = body
    self.doc.recompute()
    broken = [o.Label for o in self.body.Group if "Invalid" in list(getattr(o, "State", []))]
    if broken:
        raise BuildError(
            "after editing %r these features broke: %s" % (step["target"], ", ".join(broken))
        )
    return feature


Builder.op_sf_revolve = op_sf_revolve
Builder.op_sf_revolve_edit = op_sf_revolve_edit
