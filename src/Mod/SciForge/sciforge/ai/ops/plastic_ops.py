# SPDX-License-Identifier: LGPL-2.1-or-later
"""Design steps for the PLASTIC steps (plastic rules, Boss, Rest), built with the same SciForge
code the dialogs use, registered on core.Builder when the package is imported. The step format
is checked by SciForgeTests/golden/plastic_schema.py.

  {"op": "sf_plastic_rule", "rule": "PC 2 mm", "set": {"thickness": "2.5"}}
      Assign Plastic Rule (the root component; a library rule is copied into the design),
      optionally editing the design's copy (Manage Plastic Rules > Edit).
  {"op": "sf_boss", "id": "b1", "plane": "XY", "offset": 20, "points": [[10, 10]],
   "screw": 3, "flip": false, "position": 0, "side1": {...}, "side2": {...}}
      A sketch with the points on the plane (offset along its normal), then the Boss (both
      sides find their bodies). side1 / side2 change that side's settings
      (plastic_boss.side_defaults keys). objects[id] is the head side's step (else the
      thread side's), objects[id + "_head"] / objects[id + "_thread"] each side's.
  {"op": "sf_rest", "id": "r1", "plane": "XY", "offset": 22, "rect": [x0, y0, x1, y1],
   "thickness": 2, "draft": 0, "flip": false}
      A rectangle sketched on the plane, then the Rest on the current body; thickness /
      draft left out follow the plastic rule.
"""

import FreeCAD as App
import Part

from .core import Builder, BuildError
from .primitive_ops import _settle

_PLANE_ROLE = {"XY": "XY_Plane", "XZ": "XZ_Plane", "YZ": "YZ_Plane"}


def _sketch(builder, step, name):
    sketch = builder.body.newObject("Sketcher::SketchObject", name)
    plane = step.get("plane", "XY")
    if plane not in _PLANE_ROLE:
        raise BuildError("%s %r: plane must be XY, XZ or YZ" % (step["op"], step["id"]))
    sketch.AttachmentSupport = (builder._origin(_PLANE_ROLE[plane]), [""])
    sketch.MapMode = "FlatFace"
    if step.get("offset"):
        sketch.AttachmentOffset = App.Placement(
            App.Vector(0, 0, float(step["offset"])), App.Rotation()
        )
    return sketch


def op_sf_plastic_rule(self, step):
    from sciforge import plastic

    try:
        plastic.assign_rule(self.doc, step["rule"], None)
        if step.get("set"):
            rule = plastic.find_rule(self.doc, step["rule"])
            rule.update({k: str(v) for k, v in step["set"].items()})
            plastic.save_rule(self.doc, rule)
        plastic.apply_material(self.doc, None)
    except ValueError as exc:
        raise BuildError("sf_plastic_rule: %s" % exc)
    self.doc.recompute()
    return None


def op_sf_boss(self, step):
    from sciforge import plastic, plastic_boss

    sketch = _sketch(self, step, step["id"] + "_points")
    for x, y in step["points"]:
        sketch.addGeometry(Part.Point(App.Vector(float(x), float(y), 0)))
    self.doc.recompute()
    try:
        rule = plastic.rule_for_body(self.body)
        options = plastic_boss.default_options(rule, float(step.get("screw", 3.0)))
        options["flip"] = bool(step.get("flip", False))
        options["offset"] = float(step.get("position", 0.0))
        for side in ("side1", "side2"):
            for key, value in (step.get(side) or {}).items():
                options[side][key] = value
                options["links"]["%s.%s" % (side, key)] = False
        refs = [(sketch, name) for name in plastic_boss.point_names(sketch)]
        steps = plastic_boss.make(refs, options)
    except plastic_boss.BossError as exc:
        raise BuildError("sf_boss %r: %s" % (step["id"], exc))
    head = thread = None
    for feature in steps:
        side = plastic_boss.side_of(options, 1 if feature.Toward >= 0 else -1)
        if side == 1:
            head = feature
        else:
            thread = feature
    if head is not None:
        self.objects[step["id"] + "_head"] = head
        self.ops[step["id"] + "_head"] = "sf_boss"
    if thread is not None:
        self.objects[step["id"] + "_thread"] = thread
        self.ops[step["id"] + "_thread"] = "sf_boss"
    self.doc.recompute()
    for feature in steps:
        self._recompute(step, feature)
    return _settle(self, step, head or thread, "sf_boss")


def op_sf_rest(self, step):
    from sciforge import plastic, plastic_rest

    sketch = _sketch(self, step, step["id"] + "_profile")
    x0, y0, x1, y1 = [float(v) for v in step["rect"]]
    pts = [App.Vector(x0, y0, 0), App.Vector(x1, y0, 0), App.Vector(x1, y1, 0)]
    pts.append(App.Vector(x0, y1, 0))
    for i in range(4):
        sketch.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))
    self.doc.recompute()
    try:
        options = plastic_rest.default_options(plastic.rule_for_body(self.body))
        for key in ("thickness", "draft"):
            if key in step:
                options[key] = float(step[key])
                options["links"][key] = False
        options["flip"] = bool(step.get("flip", False))
        feature = plastic_rest.make(self.body, [(sketch, "")], options, name=step["id"])
    except plastic_rest.RestError as exc:
        raise BuildError("sf_rest %r: %s" % (step["id"], exc))
    return _settle(self, step, feature, "sf_rest")


Builder.op_sf_plastic_rule = op_sf_plastic_rule
Builder.op_sf_boss = op_sf_boss
Builder.op_sf_rest = op_sf_rest
