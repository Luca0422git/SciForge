# SPDX-License-Identifier: LGPL-2.1-or-later
"""Golden-model steps for whole components (components-2): Create Components from Bodies, Move
of a component (Capture Position), Paste / Paste New and patterns of components, built with
the same SciForge code as their dialogs (sciforge/components.py, component_move.py,
instances.py, component_pattern.py). Registered on builder.Builder when builder.py is imported.

  {"op": "components_from_bodies", "id": "k1", "bodies": ["e1"], "label": "Bracket"}
      Right-click a body > Create Components from Bodies (then renamed). Measured: k1.

  {"op": "component_move", "id": "m1", "components": ["k1"], "move_type": "translate",
   "dx", "dy", "dz", "rx", "ry", "rz", "pivot": [x, y, z], "axis": "X" | "Y" | "Z",
   "angle", "capture": true}
      Move/Copy with Move Object Components (capture: a Move step in the timeline).

  {"op": "component_paste", "id": "i1", "component": "k1", "new": false,
   "dx": 0, "dy": 0, "dz": 0}
      Copy, then Paste (a linked instance "k1:2") or Paste New (an independent copy), then
      moved by dx / dy / dz. Measured: k1 and the paste.

  {"op": "component_pattern", "id": "p1", "component": "k1", "kind": "circular" |
   "rectangular", "axis": "Z", "direction": "X", "direction2": "Y", "quantity": 6,
   "quantity2": 1, "distance": 100, "distance2": 0, "angle": 360,
   "circular_type": "full", "distribution": "extent"}
      Pattern Type Components; axes and directions are the design's origin axes.
      Measured: the component and every copy.

  {"op": "measure_components", "steps": ["k1", "p1"]}
      Measure these components (a pattern: its component and copies) from now on, in design
      coordinates.

A "roll" step may stand "before" a step (the history marker right before it).
"""

import FreeCAD as App
import Part

from .builder import _AXIS_ROLE, Builder, BuildError

MOVE_KEYS = ("move_type", "dx", "dy", "dz", "rx", "ry", "rz", "angle")


def _part(builder, step_id):
    from sciforge import components

    obj = builder.objects.get(step_id)
    if not components.is_component(obj):
        raise BuildError("step %r is not a component" % step_id)
    return obj


def _frame_axis(builder, name):
    from sciforge import component_move

    frame = component_move.frame_object(builder.doc)
    if frame is None:
        raise BuildError("no origin to take the %s axis from" % name)
    for feature in frame.Origin.OriginFeatures:
        if feature.Role == _AXIS_ROLE[name]:
            return feature
    raise BuildError("origin axis %s not found" % name)


def _measure(builder, parts):
    builder.measure_components = [p.Name for p in parts]


def op_components_from_bodies(self, step):
    from sciforge import bodies, components

    found = []
    for step_id in step["bodies"]:
        body = bodies.body_of(self.objects.get(step_id))
        if body is None:
            raise BuildError("components_from_bodies: %r is not in a body" % step_id)
        found.append(body)
    made = components.from_bodies(self.doc, found)
    if step.get("label") and len(made) == 1:
        made[0].Label = step["label"]
    self.doc.recompute()
    self.objects[step["id"]] = made[0]
    self.ops[step["id"]] = "component"
    _measure(self, made)
    return made[0]


def op_component_move(self, step):
    from sciforge import component_move, move

    parts = [_part(self, s) for s in step["components"]]
    options = move.with_defaults({k: step[k] for k in MOVE_KEYS if k in step})
    options["components"] = parts
    if "pivot" in step:
        options["pivot"] = list(step["pivot"])
    elif options["move_type"] == "free":
        options["pivot"] = [0.0, 0.0, 0.0]
    if "axis" in step:
        point, direction = move.axis_of(_frame_axis(self, step["axis"]), "")
        options["axis_point"], options["axis_dir"] = list(point), list(direction)
        options["axis_label"] = step["axis"]
    for part in parts:
        why = component_move.refusal(part)
        if why:
            raise BuildError("component_move %r: %s" % (step["id"], why))
    try:
        movement = move.transform(options)
    except move.MoveError as exc:
        raise BuildError("component_move %r: %s" % (step["id"], exc))
    befores = {p.Name: App.Placement(p.Placement) for p in parts}
    for part in parts:
        component_move.place(part, component_move.moved(part, part.Placement, movement))
    made = None
    if step.get("capture"):
        made = component_move.record(options, befores)[0]
    self.doc.recompute()
    self.objects[step["id"]] = made if made is not None else parts[0]
    self.ops[step["id"]] = "component_move"
    _measure(self, parts)
    return made


def op_component_paste(self, step):
    from sciforge import component_move, instances

    source = _part(self, step["component"])
    if step.get("new"):
        made = instances.paste_new(source)
    else:
        made = instances.make_instance(source)
    shift = App.Placement(
        App.Vector(step.get("dx", 0.0), step.get("dy", 0.0), step.get("dz", 0.0)),
        App.Rotation(),
    )
    component_move.place(made, component_move.moved(made, made.Placement, shift))
    self.doc.recompute()
    self.objects[step["id"]] = made
    self.ops[step["id"]] = "component"
    _measure(self, [source, made])
    return made


def op_component_pattern(self, step):
    from sciforge import component_pattern, pattern

    source = _part(self, step["component"])
    kind = step["kind"]
    options = {"pattern_type": "components", "objects": [(source, "")]}
    for key in (
        "quantity",
        "quantity2",
        "distance",
        "distance2",
        "angle",
        "circular_type",
        "distribution",
        "direction_type",
        "direction_type2",
    ):
        if key in step:
            options[key] = step[key]
    if "axis" in step:
        options["axis"] = (_frame_axis(self, step["axis"]), "")
    for key in ("direction", "direction2"):
        if key in step:
            options[key] = (_frame_axis(self, step[key]), "")
    try:
        feature = pattern.build(kind, options)
    except pattern.PatternError as exc:
        raise BuildError("component_pattern %r: %s" % (step["id"], exc))
    self.doc.recompute()
    self.objects[step["id"]] = feature
    self.ops[step["id"]] = "component_pattern"
    _measure(self, [source] + component_pattern.copies(feature))
    return feature


def op_measure_components(self, step):
    from sciforge import component_pattern

    parts = []
    for step_id in step["steps"]:
        obj = self.objects.get(step_id)
        if component_pattern.is_component_pattern(obj):
            parts.append(component_pattern.source_of(obj))
            parts.extend(component_pattern.copies(obj))
        else:
            parts.append(_part(self, step_id))
    _measure(self, [p for p in parts if p is not None])


_previous_shape = Builder.shape


def shape(self):
    """The components a component step names (design coordinates), else as before."""
    from sciforge import bodies, components

    names = getattr(self, "measure_components", None)
    if not names:
        return _previous_shape(self)
    solids = []
    for name in names:
        part = self.doc.getObject(name)
        if part is None:
            continue
        for body in components.bodies_in(self.doc, part, recursive=True):
            if bodies.has_solid(body):
                solids.extend(bodies.global_shape(body).Solids)
    if not solids:
        return Part.Shape()
    return solids[0] if len(solids) == 1 else Part.makeCompound(solids)


_previous_run = Builder.run
BODY_TOOL_OPS = ("combine", "split_body", "move_bodies", "measure_bodies", "delete_bodies")


def run(self, step):
    """A body-tool step measures its bodies again (bodies_ops)."""
    if step.get("op") in BODY_TOOL_OPS:
        self.measure_components = None
    return _previous_run(self, step)


Builder.run = run
Builder.shape = shape
Builder.op_components_from_bodies = op_components_from_bodies
Builder.op_component_move = op_component_move
Builder.op_component_paste = op_component_paste
Builder.op_component_pattern = op_component_pattern
Builder.op_measure_components = op_measure_components
