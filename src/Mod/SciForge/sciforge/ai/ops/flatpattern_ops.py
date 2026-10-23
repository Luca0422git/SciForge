# SPDX-License-Identifier: LGPL-2.1-or-later
"""Design steps for the SHEET METAL flat steps (Unfold, Refold, Flat Pattern, Rip, Convert), built
with the same SciForge code the dialogs use, registered on core.Builder when the package is
imported. The step format is checked by SciForgeTests/golden/flatpattern_schema.py.

    {"op": "sf_sm_convert", "id": "c1", "face": <selector>, "rule": "template"}
    {"op": "sf_flat_pattern", "id": "fp1", "face": <selector>, "measure": true}
    {"op": "sf_unfold", "id": "u1", "face": <selector>, "bends": <selector>, "all": false}
    {"op": "sf_refold", "id": "r1", "unfold": "u1"}
    {"op": "sf_rip", "id": "rp1", "type": "face" | "edge" | "points", "face": <selector>,
     "edge": <selector>, "point1": <selector>, "point2": <selector>, "offset1": 0,
     "offset2": 0, "gap": 1.0}

A flat pattern with "measure": true makes the model measure the flat pattern's solid (the
flat part) instead of the folded body, until a later step changes the body.
"""

from . import selectors
from .core import Builder, BuildError


def _one(shape, selector, kind, step, what):
    names = selectors.select(shape, selector, kind)
    if len(names) != 1:
        raise BuildError(
            "%s %r: %s must pick one element, got %d"
            % (step["op"], step.get("id"), what, len(names))
        )
    return names[0]


def op_sf_sm_convert(self, step):
    from sciforge import sm_convert

    base = self._tip()
    face = _one(base.Shape, step["face"], "faces", step, "face")
    rule = step.get("rule", "template")
    choice = sm_convert.TEMPLATE if rule == "template" else rule
    try:
        feature = sm_convert.make(self.body, base, face, choice, name=step["id"])
    except sm_convert.ConvertError as exc:
        raise BuildError("sf_sm_convert %r: %s" % (step["id"], exc))
    self.objects[step["id"]] = feature
    self.ops[step["id"]] = "sf_sm_convert"
    self._recompute(step, feature)
    self.flat_measure = None
    return feature


def op_sf_flat_pattern(self, step):
    from sciforge import flatpattern

    shape = self.body.Shape
    face = _one(shape, step["face"], "faces", step, "face")
    try:
        fp = flatpattern.create(self.body, face, name=step["id"])
    except flatpattern.FlatPatternError as exc:
        raise BuildError("sf_flat_pattern %r: %s" % (step["id"], exc))
    self.doc.recompute()
    if fp.Shape.isNull() or not fp.Shape.Solids:
        raise BuildError("sf_flat_pattern %r: no flat solid" % step["id"])
    self.objects[step["id"]] = fp
    self.ops[step["id"]] = "sf_flat_pattern"
    self.flat_measure = fp if step.get("measure", True) else None
    return fp


def op_sf_unfold(self, step):
    from sciforge import sheetmetal_flat

    base = self._tip()
    face = _one(base.Shape, step["face"], "faces", step, "face")
    bends = []
    if step.get("bends"):
        bends = selectors.select(base.Shape, step["bends"], "faces")
    try:
        feature = sheetmetal_flat.make_unfold(
            self.body, base, face, bends, bool(step.get("all", not bends)), name=step["id"]
        )
    except sheetmetal_flat.FlatError as exc:
        raise BuildError("sf_unfold %r: %s" % (step["id"], exc))
    self.objects[step["id"]] = feature
    self.ops[step["id"]] = "sf_unfold"
    self._recompute(step, feature)
    self.flat_measure = None
    return feature


def op_sf_refold(self, step):
    from sciforge import sheetmetal_flat

    unfold = self.objects.get(step["unfold"]) if step.get("unfold") else None
    try:
        feature = sheetmetal_flat.make_refold(self.body, unfold, name=step["id"])
    except sheetmetal_flat.FlatError as exc:
        raise BuildError("sf_refold %r: %s" % (step["id"], exc))
    self.objects[step["id"]] = feature
    self.ops[step["id"]] = "sf_refold"
    self._recompute(step, feature)
    self.flat_measure = None
    return feature


def op_sf_rip(self, step):
    from sciforge import rip

    base = self._tip()
    shape = base.Shape
    spec = {"type": step.get("type", "edge"), "gap": float(step.get("gap", 1.0))}
    if step.get("face"):
        spec["face"] = _one(shape, step["face"], "faces", step, "face")
    if step.get("edge"):
        spec["edge"] = _one(shape, step["edge"], "edges", step, "edge")
    for key in ("point1", "point2"):
        if step.get(key):
            sel = step[key]
            kind = "edges"
            spec[key] = _one(shape, sel, kind, step, key)
    spec["offset1"] = float(step.get("offset1", 0.0))
    spec["offset2"] = float(step.get("offset2", 0.0))
    try:
        rip.build(shape, spec)  # the dialog refuses what fails here
        feature = rip.make(self.body, base, spec, name=step["id"])
    except rip.RipError as exc:
        raise BuildError("sf_rip %r: %s" % (step["id"], exc))
    self.objects[step["id"]] = feature
    self.ops[step["id"]] = "sf_rip"
    self._recompute(step, feature)
    self.flat_measure = None
    return feature


_shape = Builder.shape


def _measured_shape(self):
    """The flat pattern's solid after a measuring sf_flat_pattern step, else the body."""
    fp = getattr(self, "flat_measure", None)
    if fp is not None:
        try:
            solids = fp.Shape.Solids
            if solids:
                return solids[0]
        except Exception:
            pass
    return _shape(self)


Builder.op_sf_sm_convert = op_sf_sm_convert
Builder.op_sf_flat_pattern = op_sf_flat_pattern
Builder.op_sf_unfold = op_sf_unfold
Builder.op_sf_refold = op_sf_refold
Builder.op_sf_rip = op_sf_rip
Builder.shape = _measured_shape
