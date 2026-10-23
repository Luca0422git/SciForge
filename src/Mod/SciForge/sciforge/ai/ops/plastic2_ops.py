# SPDX-License-Identifier: LGPL-2.1-or-later
"""Design steps for the PLASTIC steps (Snap Fit, Lip and Groove), built with the same SciForge
code the dialogs use (sciforge/plastic_snap.py, sciforge/plastic_lip.py), registered on
core.Builder when the package is imported. The step format is checked by
SciForgeTests/golden/plastic2_schema.py.

  {"op": "sf_snap_fit", "id": "sf1", "plane": "XY", "offset": 20, "points": [[58, 20]],
   "options": {"type": "parallel", "length": 12, "fillet": 0}, "hook": "e2", "other": "e1"}
      Sketch points on the (offset) plane, then Snap Fit at them. options: the dialog's
      fields (plastic_snap_core.defaults; values given end their link to the plastic rule);
      hook / other: a step id whose body gets the hooks / the grooves (default: found as the
      dialog finds them). The model is measured on the hook body from then on.
  {"op": "sf_snap_fit_edit", "target": "sf1", "set": {"length": 14}}
      double-click the Snap Fit in the timeline and change these options

  {"op": "sf_lip", "id": "l1", "of": "sh1", "edges": selector, "options": {...},
   "mate": "e2"}
      Lip on the edges of the step `of` (default: the current body's last step); options:
      plastic_lip_core.defaults' fields; mate: the touching body (default: found). The model
      is measured on the picked edges' body from then on.
  {"op": "sf_lip_edit", "target": "l1", "set": {"swap": true}}
"""

from .core import Builder, BuildError
from . import selectors

PLANE_ROLE = {"XY": "XY_Plane", "XZ": "XZ_Plane", "YZ": "YZ_Plane"}


def _body_of_step(self, step_id, what):
    from sciforge import bodies

    obj = self.objects.get(step_id)
    if obj is None:
        raise BuildError("%s: no step %r" % (what, step_id))
    body = bodies.body_of(obj)
    if body is None:
        raise BuildError("%s: step %r is in no body" % (what, step_id))
    return body


def _point_sketch(self, step):
    import FreeCAD as App
    import Part

    sketch = self.body.newObject("Sketcher::SketchObject", step["id"] + "Points")
    sketch.AttachmentSupport = (self._origin(PLANE_ROLE[step.get("plane", "XY")]), [""])
    sketch.MapMode = "FlatFace"
    if step.get("offset"):
        sketch.AttachmentOffset = App.Placement(App.Vector(0, 0, step["offset"]), App.Rotation())
    for x, y in step["points"]:
        sketch.addGeometry(Part.Point(App.Vector(x, y, 0)), False)
    self.doc.recompute()
    return sketch


def op_sf_snap_fit(self, step):
    from sciforge import bodies, plastic_snap

    sketch = _point_sketch(self, step)
    hook = _body_of_step(self, step["hook"], "sf_snap_fit") if "hook" in step else None
    other = _body_of_step(self, step["other"], "sf_snap_fit") if "other" in step else None
    try:
        feature = plastic_snap.make(
            sketch,
            dict(step.get("options", {})),
            hook_body=hook,
            groove_body=other,
            name=step["id"],
        )
    except plastic_snap.SnapError as exc:
        raise BuildError("sf_snap_fit %r: %s" % (step["id"], exc))
    self.objects[step["id"]] = feature
    self.ops[step["id"]] = "sf_snap_fit"
    self.body = bodies.body_of(feature)
    self._recompute(step, feature)
    return feature


def op_sf_snap_fit_edit(self, step):
    from sciforge import bodies, plastic_snap

    target = self.objects.get(step["target"])
    if target is None or self.ops.get(step["target"]) != "sf_snap_fit":
        raise BuildError("sf_snap_fit_edit: %r is not a snap fit step" % step["target"])
    try:
        plastic_snap.update(target, options=dict(step["set"]))
    except plastic_snap.SnapError as exc:
        raise BuildError("sf_snap_fit_edit %r: %s" % (step["target"], exc))
    self.body = bodies.body_of(target)
    self._recompute(step, target)
    return target


def op_sf_lip(self, step):
    from sciforge import bodies, plastic_lip

    source = self.objects.get(step["of"]) if "of" in step else self._tip()
    if source is None:
        raise BuildError("sf_lip %r: no step %r" % (step["id"], step.get("of")))
    body = bodies.body_of(source)
    if body is not None and body.Tip is not None:
        source = body.Tip
    names = selectors.select(source.Shape, step["edges"], "edges")
    mate = _body_of_step(self, step["mate"], "sf_lip") if "mate" in step else None
    try:
        feature = plastic_lip.make(
            source, names, dict(step.get("options", {})), mate=mate, name=step["id"]
        )
    except plastic_lip.LipError as exc:
        raise BuildError("sf_lip %r: %s" % (step["id"], exc))
    self.objects[step["id"]] = feature
    self.ops[step["id"]] = "sf_lip"
    self.body = bodies.body_of(feature)
    self._recompute(step, feature)
    return feature


def op_sf_lip_edit(self, step):
    from sciforge import bodies, plastic_lip

    target = self.objects.get(step["target"])
    if target is None or self.ops.get(step["target"]) != "sf_lip":
        raise BuildError("sf_lip_edit: %r is not a lip step" % step["target"])
    try:
        plastic_lip.update(target, options=dict(step["set"]))
    except plastic_lip.LipError as exc:
        raise BuildError("sf_lip_edit %r: %s" % (step["target"], exc))
    self.body = bodies.body_of(target)
    self._recompute(step, target)
    return target


Builder.op_sf_snap_fit = op_sf_snap_fit
Builder.op_sf_snap_fit_edit = op_sf_snap_fit_edit
Builder.op_sf_lip = op_sf_lip
Builder.op_sf_lip_edit = op_sf_lip_edit
