# SPDX-License-Identifier: LGPL-2.1-or-later
"""Design steps for Fusion's Rectangular Pattern, Circular Pattern, Pattern on Path and
Mirror, built with the same SciForge code as their dialogs (sciforge/pattern.py). Registered
on core.Builder when the package is imported.

What is patterned (exactly one):
  "features": ["e2", ...]    steps of the body (Pattern Type Features)
  "faces": <face selector>    faces of the part as it is now (Pattern Type Faces)
  "body": true                the whole body (Pattern Type Bodies: the copies are new bodies;
                              the model is then measured over every body)

  {"op": "rectangular_pattern", "id": "p1", <what>, "direction": "X" | {"edge": sel} |
   {"face": sel}, "quantity": 3, "distance": 40, "distribution": "extent" | "spacing",
   "direction_type": "one" | "symmetric", "direction2": ..., "quantity2", "distance2",
   "direction_type2", "expressions": {"distance": "gap"}, "suppressed": [2]}
      ("suppressed": copies left out, by their index among the copies, Suppression)

  {"op": "circular_pattern", "id": "p1", <what>, "axis": "Z" | {"edge": sel} | {"face": sel},
   "quantity": 6, "type": "full" | "angle" | "symmetric", "angle": 90}

  {"op": "path_pattern", "id": "p1", <what>, "path": {"sketch": "s3", "edge": 1},
   "quantity": 4, "distance": 30, "distribution", "direction_type", "orientation":
   "identical" | "path"}

  {"op": "fusion_mirror", "id": "m1", <what>, "plane": "YZ" | {"face": sel},
   "operation": "join" | "new_body" (bodies only)}

  {"op": "pattern_edit", "target": "p1", "set": {"quantity": 5, ...}}
      Double-click the pattern in the timeline and change its fields (same option names).
"""

from . import selectors
from .core import _AXIS_ROLE, _PLANE_ROLE, Builder, BuildError

COMMON = ("features", "faces", "body", "comment", "expressions")
VALUE_KEYS = (
    "quantity",
    "distance",
    "distribution",
    "direction_type",
    "quantity2",
    "distance2",
    "direction_type2",
    "angle",
    "orientation",
    "operation",
    "suppressed",
    "compute",  # Compute Option: optimized | identical | adjust (modify-2)
    "start_point",  # Pattern on Path: 0 (path start) .. 1 (path end) (modify-2)
)


def _objects(builder, step):
    keys = [k for k in ("features", "faces", "body") if k in step]
    if len(keys) != 1:
        raise BuildError("%s %r: give one of features, faces, body" % (step["op"], step["id"]))
    if "features" in step:
        return "features", [(builder.objects[name], "") for name in step["features"]]
    if "faces" in step:
        tip = builder._tip()
        names = selectors.select(tip.Shape, step["faces"], "faces")
        if not names:
            raise BuildError("%s %r: the face selector picked nothing" % (step["op"], step["id"]))
        return "faces", [(tip, name) for name in names]
    return "bodies", [(builder.body, "")]


def _ref(builder, step, key, roles):
    spec = step[key]
    if isinstance(spec, str):
        return (builder._origin(roles[spec]), "")
    tip = builder._tip()
    if "edge" in spec:
        names = selectors.select(tip.Shape, spec["edge"], "edges")
        what = "edge"
    elif "face" in spec:
        names = selectors.select(tip.Shape, spec["face"], "faces")
        what = "face"
    else:
        raise BuildError(
            "%s %r: %r must be an origin name, edge or face" % (step["op"], step["id"], key)
        )
    if len(names) != 1:
        raise BuildError("%s %r: %r must select one %s" % (step["op"], step["id"], key, what))
    return (tip, names[0])


def _options(builder, step):
    ptype, objects = _objects(builder, step)
    options = {"pattern_type": ptype, "objects": objects}
    for key in VALUE_KEYS:
        if key in step:
            options[key] = step[key]
    if "type" in step:
        options["circular_type"] = step["type"]
    options["expressions"] = dict(step.get("expressions", {}))
    return options


def _build(builder, step, kind, options):
    from sciforge import pattern

    try:
        feature = pattern.build(kind, options, name=step["id"])
    except pattern.PatternError as exc:
        raise BuildError("%s %r: %s" % (step["op"], step["id"], exc))
    builder.objects[step["id"]] = feature
    builder.ops[step["id"]] = "fusion_pattern"
    if pattern.is_body_pattern(feature):
        builder.all_bodies = True  # the copies are new bodies: measure all of them
    builder.doc.recompute()
    _check(builder, step, feature)
    return feature


def _check(builder, step, feature):
    from sciforge import pattern

    objs = [feature] + [c for c in feature.InList if pattern.is_body_copy(c)]
    for obj in objs:
        state = list(getattr(obj, "State", []))
        if "Invalid" in state or "Error" in state:
            raise BuildError(
                "%s %r failed: %s"
                % (step["op"], step.get("id", step.get("target")), obj.getStatusString())
            )


def op_rectangular_pattern(self, step):
    options = _options(self, step)
    options["direction"] = _ref(self, step, "direction", _AXIS_ROLE)
    if "direction2" in step:
        options["direction2"] = _ref(self, step, "direction2", _AXIS_ROLE)
    return _build(self, step, "rectangular", options)


def op_circular_pattern(self, step):
    options = _options(self, step)
    options.setdefault("quantity", 3)  # the Circular Pattern dialog's default (Fusion's)
    options["axis"] = _ref(self, step, "axis", _AXIS_ROLE)
    return _build(self, step, "circular", options)


def op_path_pattern(self, step):
    options = _options(self, step)
    spec = step["path"]
    sketch = self.objects.get(spec["sketch"])
    if sketch is None or self.ops.get(spec["sketch"]) != "sketch":
        raise BuildError("path_pattern %r: 'path' must name a sketch step" % step["id"])
    options["path"] = (sketch, "Edge%d" % spec["edge"] if "edge" in spec else "")
    return _build(self, step, "path", options)


def op_fusion_mirror(self, step):
    options = _options(self, step)
    options["plane"] = _ref(self, step, "plane", _PLANE_ROLE)
    return _build(self, step, "mirror", options)


def op_pattern_edit(self, step):
    """Double-click a pattern in the timeline and change its fields."""
    from sciforge import pattern

    target = self.objects.get(step["target"])
    if target is None or self.ops.get(step["target"]) != "fusion_pattern":
        raise BuildError("pattern_edit: %r is not a pattern step" % step["target"])
    kind, options = pattern.read(target)
    for key, value in step.get("set", {}).items():
        options["circular_type" if key == "type" else key] = value
    try:
        feature = pattern.build(kind, options, feature=target)
    except pattern.PatternError as exc:
        raise BuildError("pattern_edit %r: %s" % (step["target"], exc))
    self.objects[step["target"]] = feature
    self.doc.recompute()
    _check(self, step, feature)
    return feature


_plain_shape = Builder.shape


def shape(self):
    """The part to measure: every body once a pattern made new bodies (Fusion's Bodies)."""
    if not getattr(self, "all_bodies", False):
        return _plain_shape(self)
    import Part

    solids = []
    for body in self.doc.findObjects("PartDesign::Body"):
        if not body.Shape.isNull():
            solids.extend(body.Shape.Solids)
    return Part.makeCompound(solids)


Builder.shape = shape
Builder.op_rectangular_pattern = op_rectangular_pattern
Builder.op_circular_pattern = op_circular_pattern
Builder.op_path_pattern = op_path_pattern
Builder.op_fusion_mirror = op_fusion_mirror
Builder.op_pattern_edit = op_pattern_edit
