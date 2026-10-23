# SPDX-License-Identifier: LGPL-2.1-or-later
"""Design steps for the body tools (Combine, Split Body, Move/Copy, Delete Face), built
with the same SciForge code as their dialogs (sciforge/combine.py, split.py, move.py,
delete.py). Registered on core.Builder when the package is imported.

Bodies are named by a step that made them (its body): "e1" is the body of extrude e1.

  {"op": "combine", "id": "c1", "target": "e1", "tools": ["e2"],
   "operation": "join" | "cut" | "intersect", "new_body": false, "new_component": false,
   "keep_tools": false}
      Measured: the target body (with new_body / new_component: the new body).

  {"op": "split_body", "id": "s1", "body": "e1",
   "tool": "XY" | "XZ" | "YZ" | {"face": selector, "of": "e2"} | {"body": "e2"} |
           {"sketch": "s3", "edge": 1} (a sketch curve, cut straight through),
   "tools": [tool, tool, ...] (instead of "tool": several splitting tools, one step),
   "extend": true}
      Measured: every body the split leaves (the split body and the new ones).

  {"op": "move_bodies", "id": "m1", "bodies": ["e1"], "move_type": "free" | "translate" |
   "rotate" | "point_to_point", "dx", "dy", "dz", "rx", "ry", "rz", "pivot": [x, y, z],
   "axis": "X" | "Y" | "Z" (rotate about that origin axis), "angle",
   "from_point": [x, y, z], "to_point": [x, y, z], "px", "py", "pz" (point_to_position:
   where from_point goes), "copy": false}
      Measured: the moved bodies (and the copies).

  {"op": "delete_face", "id": "d1", "faces": selector}
      Delete (Del) on faces of the body as it is now.

  {"op": "body_tool_edit", "target": "c1", "set": {option: value}}
      Double-click the step in the timeline and change its fields (same option names).

  {"op": "measure_bodies", "steps": ["e1", "e2"]}  measure these bodies from now on (a
      pattern of bodies, "p1": the new bodies it made)

  {"op": "delete_bodies", "steps": ["e2"]}
      Delete (Del) on bodies (picked in the browser); what used them keeps working.
"""

import Part

from . import selectors
from .core import _AXIS_ROLE, _PLANE_ROLE, Builder, BuildError

MOVE_KEYS = ("move_type", "dx", "dy", "dz", "rx", "ry", "rz", "angle", "px", "py", "pz", "copy")


def _body(builder, step_id):
    from sciforge import bodies

    obj = builder.objects.get(step_id)
    if obj is None:
        raise BuildError("unknown step %r" % step_id)
    body = bodies.body_of(obj)
    if body is None:
        from sciforge import move

        if move.is_copy(obj):
            body = move.copy_body(obj)
    if body is None:
        raise BuildError("step %r is not in a body" % step_id)
    return body


def _origin(body, roles, name):
    for feature in body.Origin.OriginFeatures:
        if feature.Role == roles[name]:
            return feature
    raise BuildError("origin %s not found" % name)


def _check_state(step, objects):
    for obj in objects:
        state = list(getattr(obj, "State", []))
        if "Invalid" in state or "Error" in state:
            raise BuildError(
                "step %r (%s) failed: %s"
                % (step.get("id", step.get("target")), step["op"], obj.getStatusString())
            )


def _measure(builder, found):
    builder.measure_bodies = [b.Name for b in found]


def op_combine(self, step):
    from sciforge import bodies, combine

    options = {
        "target": _body(self, step["target"]),
        "tools": [_body(self, t) for t in step["tools"]],
        "operation": step.get("operation", "join"),
        "new_body": bool(step.get("new_body", False)),
        "new_component": bool(step.get("new_component", False)),
        "keep_tools": bool(step.get("keep_tools", False)),
    }
    try:
        feature = combine.build(options)
    except combine.CombineError as exc:
        raise BuildError("combine %r: %s" % (step["id"], exc))
    self.doc.recompute()
    _check_state(step, [feature])
    self.objects[step["id"]] = feature
    self.ops[step["id"]] = "combine"
    self.body = bodies.body_of(feature)
    _measure(self, [self.body])
    return feature


def _split_tool(self, step, body):
    spec = step["tool"]
    if isinstance(spec, str):
        return (_origin(body, _PLANE_ROLE, spec), "")
    if "body" in spec:
        return (_body(self, spec["body"]), "")
    if "sketch" in spec:
        sketch = self.objects.get(spec["sketch"])
        if sketch is None:
            raise BuildError("split_body %r: unknown sketch %r" % (step["id"], spec["sketch"]))
        return (sketch, "Edge%d" % int(spec.get("edge", 1)))
    if "face" in spec:
        owner = _body(self, spec["of"]) if "of" in spec else body
        tip = owner.Tip
        names = selectors.select(tip.Shape, spec["face"], "faces")
        if len(names) != 1:
            raise BuildError("split_body %r: the face selector must pick one face" % step["id"])
        return (tip, names[0])
    raise BuildError("split_body %r: tool must be a plane name, a face or a body" % step["id"])


def op_split_body(self, step):
    from sciforge import split

    body = _body(self, step["body"])
    if "tools" in step:  # Splitting Tool(s): several at once, one step (components-2)
        tools = [_split_tool(self, dict(step, tool=spec), body) for spec in step["tools"]]
    else:
        tools = [_split_tool(self, step, body)]
    options = {
        "body": body,
        "tools": tools,
        "extend": step.get("extend", True),
    }
    try:
        feature = split.build(options)
    except split.SplitError as exc:
        raise BuildError("split_body %r: %s" % (step["id"], exc))
    self.doc.recompute()
    _check_state(step, [feature] + split.pieces_of(feature))
    self.objects[step["id"]] = feature
    self.ops[step["id"]] = "split_body"
    self.body = body
    _measure(self, [body] + split.piece_bodies(feature))
    return feature


def _move_options(self, step, found):
    options = {"bodies": found}
    for key in MOVE_KEYS:
        if key in step:
            options[key] = step[key]
    for key in ("pivot", "from_point", "to_point"):
        if key in step:
            options[key] = list(step[key])
    if options.get("move_type") == "free" and "pivot" not in options:
        from sciforge import bodies

        options["pivot"] = list(bodies.center_of(found))
    if "axis" in step:
        line = _origin(found[0], _AXIS_ROLE, step["axis"])
        from sciforge import move

        point, direction = move.axis_of(line, "")
        options["axis_point"], options["axis_dir"] = list(point), list(direction)
        options["axis_label"] = step["axis"]
    return options


def op_move_bodies(self, step):
    from sciforge import move

    found = [_body(self, s) for s in step["bodies"]]
    options = _move_options(self, step, found)
    try:
        steps = move.build(options)
    except move.MoveError as exc:
        raise BuildError("move_bodies %r: %s" % (step["id"], exc))
    self.doc.recompute()
    _check_state(step, steps)
    self.objects[step["id"]] = steps[0]
    self.ops[step["id"]] = "move_bodies"
    measured = list(found)
    if options.get("copy"):
        measured += [move.copy_body(s) for s in steps]
    _measure(self, measured)
    return steps[0]


def op_delete_face(self, step):
    from sciforge import delete

    tip = self._tip()
    names = selectors.select(tip.Shape, step["faces"], "faces")
    if not names:
        raise BuildError("delete_face %r: the face selector picked nothing" % step["id"])
    try:
        feature = delete.delete_faces(tip, names)
    except delete.DeleteError as exc:
        raise BuildError("delete_face %r: %s" % (step["id"], exc))
    self.doc.recompute()
    _check_state(step, [feature])
    self.objects[step["id"]] = feature
    self.ops[step["id"]] = "delete_face"
    return feature


def op_body_tool_edit(self, step):
    from sciforge import bodies, combine, move, split

    target = self.objects.get(step["target"])
    op = self.ops.get(step["target"])
    if target is None:
        raise BuildError("body_tool_edit: unknown step %r" % step["target"])
    changes = step.get("set", {})
    try:
        if op == "combine":
            options = combine.read(target)
            options.update(changes)
            feature = combine.build(options, target)
            self.body = bodies.body_of(feature)
            _measure(self, [self.body])
        elif op == "split_body":
            options = split.read(target)
            if "tool" in changes:
                fake = dict(step, tool=changes["tool"], id=step["target"])
                options["tool"] = _split_tool(self, fake, options["body"])
            if "extend" in changes:
                options["extend"] = changes["extend"]
            feature = split.build(options, target)
            _measure(self, [options["body"]] + split.piece_bodies(feature))
        elif op == "move_bodies":
            options, steps = move.read(target)
            for key in MOVE_KEYS:
                if key in changes:
                    options[key] = changes[key]
            for key in ("pivot", "from_point", "to_point"):
                if key in changes:
                    options[key] = list(changes[key])
            feature = move.build(options, steps)[0]
        else:
            raise BuildError("body_tool_edit: %r is not a body-tool step" % step["target"])
    except (combine.CombineError, split.SplitError, move.MoveError) as exc:
        raise BuildError("body_tool_edit %r: %s" % (step["target"], exc))
    self.objects[step["target"]] = feature
    self.doc.recompute()
    _check_state(step, [feature])
    return feature


def op_delete_bodies(self, step):
    from sciforge import delete

    found = [_body(self, s) for s in step["steps"]]
    try:
        delete.run(self.doc, delete.plan([(b, "") for b in found]))
    except delete.DeleteError as exc:
        raise BuildError("delete_bodies: %s" % exc)
    names = {b.Name for b in found}
    for key in [k for k, obj in self.objects.items() if not _alive(obj)]:
        self.objects.pop(key, None)
    left = [n for n in getattr(self, "measure_bodies", None) or [] if n not in names]
    self.measure_bodies = left or None
    self.doc.recompute()


def _alive(obj):
    try:
        return obj.isAttachedToDocument()
    except Exception:
        return False


def op_measure_bodies(self, step):
    found = []
    for name in step["steps"]:
        found += _bodies_of(self, name)
    _measure(self, found)


def _bodies_of(builder, step_id):
    """The body a step is in; for a pattern of bodies (or a mirror with New Body): the new
    bodies it made."""
    from sciforge import pattern

    obj = builder.objects.get(step_id)
    if obj is not None and pattern.is_body_pattern(obj):
        return pattern.copy_bodies(obj)
    return [_body(builder, step_id)]


_previous_shape = Builder.shape


def shape(self):
    """The part to measure: the bodies the last body-tool step names, else as before."""
    names = getattr(self, "measure_bodies", None)
    if not names:
        return _previous_shape(self)
    solids = []
    for name in names:
        body = self.doc.getObject(name)
        if body is not None and not body.Shape.isNull():
            if body.Shape.Solids:
                solids.extend(body.Shape.Solids)
            else:  # a surface body (Split Body / Move of a surface, surface-4): its faces
                solids.extend(body.Shape.Shells or body.Shape.Faces)
    if not solids:
        return Part.Shape()
    return solids[0] if len(solids) == 1 else Part.makeCompound(solids)


Builder.shape = shape
Builder.op_combine = op_combine
Builder.op_split_body = op_split_body
Builder.op_move_bodies = op_move_bodies
Builder.op_delete_face = op_delete_face
Builder.op_body_tool_edit = op_body_tool_edit
Builder.op_measure_bodies = op_measure_bodies
Builder.op_delete_bodies = op_delete_bodies
