# SPDX-License-Identifier: LGPL-2.1-or-later
"""Golden-model steps for the Gear tool (SOLID > CREATE > Gear), built with the same
SciForge code its dialog uses (sciforge/gear.py), registered on builder.Builder when
builder.py is imported. The step format is checked by gear_schema.py.

  {"op": "sf_gear", "id": "g1", "plane": "XY", "x": 0, "y": 0, "type": "spur",
   "standard": "metric", "module": 2, "teeth": 24, "pressure_angle": 20,
   "backlash": 0, "fillet": 0.5, "thickness": 10, "symmetric": false, "hole": 10,
   "operation": "new_body"}
      type      spur | internal (rim) | rack (rack_size teeth | length, rack_length,
                rack_height)
      standard  metric (module) | english (diametral_pitch, teeth per inch)
      plane     "XY" / "XZ" / "YZ" or {"face": selector}, as sf_primitive
      operation join | cut | new_body (default, as the dialog) | new_component
      expressions {field: formula}: a parameter typed in that field

  {"op": "sf_gear_edit", "target": "g1", "set": {"teeth": 30}}
      double-click the gear in the timeline and change these options
"""

from .builder import Builder, BuildError
from .primitive_ops import _plane, _settle

GEAR_KEYS = (
    "x",
    "y",
    "type",
    "standard",
    "module",
    "diametral_pitch",
    "teeth",
    "pressure_angle",
    "backlash",
    "fillet",
    "thickness",
    "symmetric",
    "hole",
    "rim",
    "rack_size",
    "rack_length",
    "rack_height",
    "operation",
)


def op_sf_gear(self, step):
    from sciforge import gear, primitives

    ref = _plane(self, step)
    options = {k: step[k] for k in GEAR_KEYS if k in step}
    options["expressions"] = dict(step.get("expressions", {}))
    try:
        feature = gear.make(ref, options, name=step["id"])
    except primitives.PrimitiveError as exc:
        raise BuildError("sf_gear %r: %s" % (step["id"], exc))
    return _settle(self, step, feature, "sf_gear")


def op_sf_gear_edit(self, step):
    from sciforge import gear, primitives

    target = self.objects.get(step["target"])
    if target is None or self.ops.get(step["target"]) != "sf_gear":
        raise BuildError("sf_gear_edit: %r is not a gear step" % step["target"])
    try:
        feature = gear.update(target, options=dict(step["set"]))
    except primitives.PrimitiveError as exc:
        raise BuildError("sf_gear_edit %r: %s" % (step["target"], exc))
    self.objects[step["target"]] = feature
    body = feature.getParentGeoFeatureGroup()
    if body is not None:
        self.body = body
    self._recompute(step, feature)
    return feature


Builder.op_sf_gear = op_sf_gear
Builder.op_sf_gear_edit = op_sf_gear_edit
