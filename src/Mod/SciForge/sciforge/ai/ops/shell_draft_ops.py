# SPDX-License-Identifier: LGPL-2.1-or-later
"""Design steps for Fusion's Shell, Draft and Scale, built with the same SciForge code
the dialogs use (sciforge/shelling.py, drafting.py, scale.py), registered on
core.Builder when the package is imported.

  {"op": "sf_shell", "id": "sh1", "faces": selector | "body": true,
   "inside": 2, "outside": 1, "direction": "inside" | "outside" | "both",
   "shell_type": "sharp" | "rounded"}
      faces taken away (selector on the part), or the whole body made hollow
  {"op": "sf_shell_edit", "target": "sh1", "set": {"direction": "both", "outside": 1}}

  {"op": "sf_draft", "id": "d1", "plane": "XY" | "XZ" | "YZ" | {"face": selector},
   "faces": selector, "angle": 5, "flip": false}
      the fixed plane (an origin plane, or a flat face of the part: its outward side is
      the pull direction), the faces to tilt; positive angles narrow the part toward
      the pull direction
  {"op": "sf_draft_edit", "target": "d1", "set": {"angle": 3, "flip": true}}

  {"op": "sf_scale", "id": "sc1", "factor": 2 | "factors": [2, 1, 0.5],
   "point": "origin" | [x, y, z]}
      uniform (factor) or non uniform (factors X, Y, Z) about the origin or the corner
      of the part at [x, y, z]
  {"op": "sf_scale_edit", "target": "sc1", "set": {"factor": 1.5}}
"""

import FreeCAD as App

from . import selectors
from .core import Builder, BuildError

_PLANE_ROLE = {"XY": "XY_Plane", "XZ": "XZ_Plane", "YZ": "YZ_Plane"}
SHELL_OPTIONS = ("inside", "outside", "direction", "shell_type")


def _check_broken(builder, what):
    broken = [o.Label for o in builder.body.Group if "Invalid" in list(getattr(o, "State", []))]
    if broken:
        raise BuildError("after %s these features broke: %s" % (what, ", ".join(broken)))


# -- Shell --------------------------------------------------------------------------------
def op_sf_shell(self, step):
    from sciforge import shelling

    base = self._tip()
    # The 3D view has drawn the part before Shell is used: its triangles change what
    # BoundBox returns (a round part's box gets a little smaller). Do the same here.
    base.Shape.tessellate(0.1)
    names = [] if step.get("body") else selectors.select(base.Shape, step["faces"], "faces")
    options = {k: step[k] for k in SHELL_OPTIONS if k in step}
    try:
        shelling.trial(base.Shape, names, options)  # the dialog refuses what fails here
        feature = shelling.make(self.body, base, names, options, name=step["id"])
    except shelling.ShellError as exc:
        raise BuildError("sf_shell %r: %s" % (step["id"], exc))
    self.objects[step["id"]] = feature
    self.ops[step["id"]] = "sf_shell"
    self._recompute(step, feature)
    return feature


def op_sf_shell_edit(self, step):
    from sciforge import follow, shelling

    target = self.objects.get(step["target"])
    if target is None or self.ops.get(step["target"]) != "sf_shell":
        raise BuildError("sf_shell_edit: %r is not a sf_shell step" % step["target"])
    base, names, options, formulas = shelling.read(target)
    options.update(step["set"])
    later = follow.snapshot(self.body, target)  # as the dialog does: later steps follow
    try:
        shelling.trial(base.Shape, names, options)
        feature = shelling.update(target, base, names, options, formulas)
    except shelling.ShellError as exc:
        raise BuildError("sf_shell_edit %r: %s" % (step["target"], exc))
    self.objects[step["target"]] = feature
    follow.recompute(self.doc, later)
    _check_broken(self, "editing %r" % step["target"])
    return feature


# -- Draft --------------------------------------------------------------------------------
def _draft_plane(builder, step, base):
    plane = step["plane"]
    if isinstance(plane, str):
        return (builder._origin(_PLANE_ROLE[plane]), "")
    names = selectors.select(base.Shape, plane["face"], "faces")
    if len(names) != 1:
        raise BuildError("sf_draft %r: the plane selector must pick one face" % step["id"])
    return (base, names[0])


def op_sf_draft(self, step):
    from sciforge import drafting

    base = self._tip()
    plane = _draft_plane(self, step, base)
    names = selectors.select(base.Shape, step["faces"], "faces")
    options = {"angle": step.get("angle", 1.0), "flip": bool(step.get("flip", False))}
    try:
        drafting.check(base.Shape, plane, names, options)
        feature = drafting.make(self.body, base, plane, names, options, name=step["id"])
    except drafting.DraftError as exc:
        raise BuildError("sf_draft %r: %s" % (step["id"], exc))
    self.objects[step["id"]] = feature
    self.ops[step["id"]] = "sf_draft"
    self._recompute(step, feature)
    left = drafting.undrafted(base.Shape, feature.Shape, names)
    if left:
        raise BuildError("sf_draft %r: faces not drafted: %s" % (step["id"], left))
    return feature


def op_sf_draft_edit(self, step):
    from sciforge import drafting, follow

    target = self.objects.get(step["target"])
    if target is None or self.ops.get(step["target"]) != "sf_draft":
        raise BuildError("sf_draft_edit: %r is not a sf_draft step" % step["target"])
    base, plane, names, options, formula = drafting.read(target)
    options.update(step["set"])
    later = follow.snapshot(self.body, target)
    try:
        drafting.check(base.Shape, plane, names, options)
        drafting.apply(target, base, plane, names, options, formula)
    except drafting.DraftError as exc:
        raise BuildError("sf_draft_edit %r: %s" % (step["target"], exc))
    follow.recompute(self.doc, later)
    _check_broken(self, "editing %r" % step["target"])
    return target


# -- Scale --------------------------------------------------------------------------------
def _scale_options(spec):
    if "factors" in spec:
        return {"uniform": False, "factors": [float(v) for v in spec["factors"]]}
    return {"uniform": True, "factor": float(spec.get("factor", 1.0))}


def _scale_point(step, base):
    point = step.get("point", "origin")
    if point == "origin":
        return None
    probe = App.Vector(*point)
    for i, vertex in enumerate(base.Shape.Vertexes, start=1):
        if (vertex.Point - probe).Length < 1e-6:
            return (base, "Vertex%d" % i)
    raise BuildError("sf_scale %r: no corner of the part at %s" % (step["id"], point))


def op_sf_scale(self, step):
    from sciforge import scale

    base = self._tip()
    point = _scale_point(step, base)
    options = _scale_options(step)
    try:
        scale.trial(base.Shape, point, options)
        feature = scale.make(self.body, base, point, options, name=step["id"])
    except scale.ScaleError as exc:
        raise BuildError("sf_scale %r: %s" % (step["id"], exc))
    self.objects[step["id"]] = feature
    self.ops[step["id"]] = "sf_scale"
    self._recompute(step, feature)
    return feature


def op_sf_scale_edit(self, step):
    from sciforge import follow, scale

    target = self.objects.get(step["target"])
    if target is None or self.ops.get(step["target"]) != "sf_scale":
        raise BuildError("sf_scale_edit: %r is not a sf_scale step" % step["target"])
    base, point, options, formulas = scale.read(target)
    options.update(_scale_options(step["set"]))
    later = follow.snapshot(self.body, target)
    try:
        scale.trial(base.Shape, point, options)
        scale.apply(target, base, point, options, formulas)
    except scale.ScaleError as exc:
        raise BuildError("sf_scale_edit %r: %s" % (step["target"], exc))
    follow.recompute(self.doc, later)
    _check_broken(self, "editing %r" % step["target"])
    return target


Builder.op_sf_shell = op_sf_shell
Builder.op_sf_shell_edit = op_sf_shell_edit
Builder.op_sf_draft = op_sf_draft
Builder.op_sf_draft_edit = op_sf_draft_edit
Builder.op_sf_scale = op_sf_scale
Builder.op_sf_scale_edit = op_sf_scale_edit
