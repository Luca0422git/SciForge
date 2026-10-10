# SPDX-License-Identifier: LGPL-2.1-or-later
"""Golden-model steps for Fusion's Hole and Thread, built with the same SciForge code as the
Hole (H) and Thread dialogs (sciforge/hole.py, sciforge/thread.py). Registered on
builder.Builder when builder.py is imported.

  {"op": "hole_at", "id": "h1", "face": <face selector>, "at": [x, y, z],
   "references": [{"edge": <edge selector>, "distance": 3}, ...], <hole options>}
      Single Hole: click `face` at `at` (body coordinates); up to two straight edges of the
      part measure the hole's centre (they follow the edges when the part changes).

  {"op": "hole_points", "id": "h1", "sketch": "s2", <hole options>}
      From Sketch: a hole at every point and circle centre of the sketch step; the holes go
      into the part (turned round by themselves when the sketch lies under it).

  hole options (Fusion's dialog, defaults in sciforge/hole.py DEFAULTS):
      "extent": "distance" | "all" | "to", "depth", "to": {"plane": "XY"} or {"face": sel},
      "hole_type": "simple" | "counterbore" | "countersink", "diameter",
      "cbore_diameter", "cbore_depth", "csink_diameter", "csink_angle",
      "drill_point": "flat" | "angle", "drill_angle",
      "tap_type": "simple" | "clearance" | "tapped", "standard": "iso" | "ansi",
      "size", "designation" (e.g. "M6x1", "1/4-20 UNC"), "fit": "close" | "normal" | "loose",
      "thread_class", "direction": "right" | "left", "modeled", "full_tap", "tap_depth", "flip"

  {"op": "thread", "id": "t1", "faces": <face selector of cylinders>, "modeled": true,
   "full_length": true, "length": 8, "offset": 2, "from_end": false, "standard": "iso",
   "designation": "M6x1", "direction": "right"}
      Thread: the size comes from the face when no designation is given; modeled cuts the
      ISO 68-1 groove (sciforge/thread_core.py has the formulas), cosmetic changes nothing.

`edit` steps can change a hole's "diameter" / "depth" and a thread's "length" / "offset".
"""

import FreeCAD as App

from . import selectors
from .builder import _EDIT_PROPS, _PLANE_ROLE, Builder, BuildError

HOLE_OPTIONS = (
    "extent",
    "depth",
    "hole_type",
    "diameter",
    "cbore_diameter",
    "cbore_depth",
    "csink_diameter",
    "csink_angle",
    "drill_point",
    "drill_angle",
    "tap_type",
    "standard",
    "size",
    "designation",
    "fit",
    "thread_class",
    "direction",
    "modeled",
    "full_tap",
    "tap_depth",
    "flip",
)
THREAD_OPTIONS = (
    "standard",
    "size",
    "designation",
    "thread_class",
    "direction",
    "modeled",
    "full_length",
    "length",
    "offset",
    "from_end",
)

_EDIT_PROPS["thread"] = {"length": "Length", "offset": "Offset"}


def _hole_options(builder, step):
    options = {k: step[k] for k in HOLE_OPTIONS if k in step}
    if "to" in step:
        spec = step["to"]
        if "plane" in spec:
            options["to"] = (builder._origin(_PLANE_ROLE[spec["plane"]]), "")
        else:
            tip = builder._tip()
            names = selectors.select(tip.Shape, spec["face"], "faces")
            if len(names) != 1:
                raise BuildError("%s %r: 'to' must select one face" % (step["op"], step["id"]))
            options["to"] = (tip, names[0])
    return options


def _finish(builder, step, feature, op):
    builder.objects[step["id"]] = feature
    builder.ops[step["id"]] = op  # "edit" steps use the hole / thread option names
    builder._recompute(step, feature)
    return feature


def op_hole_at(self, step):
    """Fusion's Single Hole (sciforge/hole.py, exactly what the H dialog builds)."""
    from sciforge import hole

    base = self._tip()
    names = selectors.select(base.Shape, step["face"], "faces")
    if len(names) != 1:
        raise BuildError("hole_at %r: 'face' must select one face" % step["id"])
    refs = []
    for ref in step.get("references", []):
        edges = selectors.select(base.Shape, ref["edge"], "edges")
        if len(edges) != 1:
            raise BuildError("hole_at %r: each reference must select one edge" % step["id"])
        refs.append(((base, edges[0]), ref["distance"]))
    try:
        feature = hole.make_single(
            self.body,
            base,
            names[0],
            App.Vector(*step["at"]),
            _hole_options(self, step),
            step["id"],
            refs,
        )
    except hole.HoleError as exc:
        raise BuildError("hole_at %r: %s" % (step["id"], exc))
    if len(hole.references(feature)) != len(refs):
        raise BuildError("hole_at %r: a reference edge could not be used" % step["id"])
    return _finish(self, step, feature, "hole")


def op_hole_points(self, step):
    """Fusion's Hole > From Sketch: every point and circle centre of a sketch step."""
    from sciforge import hole

    sketch = self.objects.get(step["sketch"])
    if sketch is None or self.ops.get(step["sketch"]) != "sketch":
        raise BuildError("hole_points %r: 'sketch' must name an earlier sketch" % step["id"])
    self.doc.recompute()
    try:
        feature = hole.make_from_sketch(
            self.body, sketch, [], _hole_options(self, step), step["id"]
        )
    except hole.HoleError as exc:
        raise BuildError("hole_points %r: %s" % (step["id"], exc))
    return _finish(self, step, feature, "hole")


def op_thread(self, step):
    """Fusion's Thread (sciforge/thread.py, exactly what the Thread dialog builds)."""
    from sciforge import thread

    base = self._tip()
    names = selectors.select(base.Shape, step["faces"], "faces")
    if not names:
        raise BuildError("thread %r: the face selector picked nothing" % step["id"])
    try:
        feature = thread.make(
            self.body,
            base,
            names,
            {k: step[k] for k in THREAD_OPTIONS if k in step},
            step["id"],
        )
    except thread.ThreadError as exc:
        raise BuildError("thread %r: %s" % (step["id"], exc))
    return _finish(self, step, feature, "thread")


Builder.op_hole_at = op_hole_at
Builder.op_hole_points = op_hole_points
Builder.op_thread = op_thread
