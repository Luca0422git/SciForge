# SPDX-License-Identifier: LGPL-2.1-or-later
"""Design steps for INSERT > Hardware... (screws, nuts, washers, heat-set inserts,
magnets and the hole each needs), built with the same SciForge code as the dialog
(sciforge/hardware.py). Registered on core.Builder when core.py is imported; the step
format is checked by SciForgeTests/golden/hardware_schema.py.

  {"op": "sf_hardware", "id": "hw1", "face": <face selector>, "at": [x, y, z],
   "standard": "iso4762", "size": "3", "length": 10, "make_hole": true, ...}
  {"op": "sf_hardware", "id": "hw1", "edge": <edge selector of one round edge>, ...}
      Click a flat face of the current body at `at` (design coordinates), or a round edge
      (a hole's rim): a new component with the part, and its Hole step in the current body.
      Options: standard (iso4762 | iso7380 | iso10642 | iso4032 | iso7089 | insert |
      magnet), size ("3", "6x3"), length, flip, make_hole, fit (close | normal | loose),
      sink_head, hole_depth (all | length), clearance (a magnet's pocket).
      "hardware_bbox": [xmin, ymin, zmin, xmax, ymax, zmax] checks where the part ended up
      (design coordinates). The measured body stays the clicked one; expect_bodies with the
      step's id measures the part's own body.

  {"op": "sf_hardware_edit", "target": "hw1", "set": {"length": 16}}
      double-click the Hardware step in the timeline and change these options (its hole
      follows); "hardware_bbox" as above.
"""

from . import selectors
from .core import Builder, BuildError

HARDWARE_KEYS = (
    "standard",
    "size",
    "length",
    "flip",
    "make_hole",
    "fit",
    "sink_head",
    "hole_depth",
    "clearance",
)


def _options(step):
    from sciforge import hardware_core

    options = {k: step[k] for k in HARDWARE_KEYS if k in step}
    if "standard" in options:
        options["kind"] = hardware_core.kind_of(options["standard"])
    return options


def _check_bbox(step, feature):
    want = step.get("hardware_bbox")
    if want is None:
        return
    from sciforge import hardware

    shape = feature.Shape.copy()
    component = hardware.component_of(feature)
    if component is not None:
        shape.transformShape(component.getGlobalPlacement().toMatrix())
    box = shape.BoundBox
    have = [box.XMin, box.YMin, box.ZMin, box.XMax, box.YMax, box.ZMax]
    if any(abs(a - b) > 1e-4 for a, b in zip(have, want)):
        raise BuildError(
            "%s: the part's box is %s, expected %s"
            % (step.get("id", step.get("target")), [round(v, 6) for v in have], want)
        )


def _settle(self, step, feature):
    from sciforge import hardware

    self.doc.recompute()
    for obj in (feature, hardware.hole_of(feature)):
        if obj is None:
            continue
        state = list(getattr(obj, "State", []))
        if "Invalid" in state or "Error" in state or obj.Shape.isNull():
            raise BuildError(
                "step %r (%s): %s failed: %s"
                % (step.get("id", step.get("target")), step["op"], obj.Label, state)
            )
    _check_bbox(step, feature)
    return feature


def op_sf_hardware(self, step):
    import FreeCAD as App

    from sciforge import hardware, hardware_core

    tip = self._tip()
    if "edge" in step:
        names = selectors.select(tip.Shape, step["edge"], "edges")
        if len(names) != 1:
            raise BuildError("sf_hardware %r: 'edge' must select one edge" % step["id"])
        pick = (tip, names[0], None)
    else:
        names = selectors.select(tip.Shape, step["face"], "faces")
        if len(names) != 1:
            raise BuildError("sf_hardware %r: 'face' must select one face" % step["id"])
        pick = (tip, names[0], App.Vector(*step["at"]))
    try:
        feature = hardware.make(self.doc, pick, _options(step))
    except hardware_core.HardwareError as exc:
        raise BuildError("sf_hardware %r: %s" % (step["id"], exc))
    self.objects[step["id"]] = feature
    self.ops[step["id"]] = "sf_hardware"
    return _settle(self, step, feature)


def op_sf_hardware_edit(self, step):
    from sciforge import hardware, hardware_core

    target = self.objects.get(step["target"])
    if target is None or self.ops.get(step["target"]) != "sf_hardware":
        raise BuildError("sf_hardware_edit: %r is not a hardware step" % step["target"])
    options = _options(step["set"])
    try:
        feature = hardware.update(target, options=options)
    except hardware_core.HardwareError as exc:
        raise BuildError("sf_hardware_edit %r: %s" % (step["target"], exc))
    return _settle(self, step, feature)


Builder.op_sf_hardware = op_sf_hardware
Builder.op_sf_hardware_edit = op_sf_hardware_edit
