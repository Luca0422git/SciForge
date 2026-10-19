# SPDX-License-Identifier: LGPL-2.1-or-later
"""Design steps for direct modeling and the Modify tools of outline 7.13 / 7.3 / 7.7
(Capture Design History, Replace Face, Split Face, Silhouette Split, Align, Remove), built
with the same SciForge code as their dialogs (sciforge/direct.py, replace_face.py,
split_face.py, silhouette.py, align.py, remove.py). Registered on core.Builder when
the package is imported.

Bodies are named by a step that made them (its body), as in bodies_ops.py. A pick ("ref")
is one of:
  "XY" | "XZ" | "YZ"                    an origin plane (of the body worked on)
  "X" | "Y" | "Z"                       an origin axis
  {"face": selector, "of": "e2"}        a face of that body as it is now ("of" left out:
  {"edge": selector, "of": "e2"}        the body worked on); edges and corners likewise
  {"vertex": selector, "of": "e2"}
  {"body": "e2"}                        a whole body

  {"op": "history_off"} / {"op": "history_on"}
      Do Not Capture Design History / Capture Design History (the design's menu).

  {"op": "replace_face", "id": "r1", "faces": selector, "of": "e1", "tangent_chain": true,
   "target": ref}
      Measured: the body whose faces moved.

  {"op": "split_face", "id": "f1", "faces": selector, "of": "e1", "tool": ref,
   "extend": false, "split_type": "surface" | "vector" | "closest", "direction": ref}
      Measured: that body.

  {"op": "silhouette_split", "id": "l1", "body": "e1", "direction": ref,
   "operation": "faces" | "body" | "shelled"}
      Measured: the body and the bodies the split made.

  {"op": "align_bodies", "id": "a1", "from": ref, "to": ref, "flip": false, "turns": 0}
      Measured: the body that moved.

  {"op": "modify_edit", "target": "r1", "set": {option: value or ref}}
      Double-click one of the steps above in the timeline and change it.

  {"op": "remove_bodies", "steps": ["e2"]}
      Remove (a timeline step): measured from then on: the bodies still in the design.
"""

from . import selectors
from .bodies_ops import _alive, _body, _check_state, _measure, _origin
from .core import _AXIS_ROLE, _PLANE_ROLE, Builder, BuildError

ELEMENTS = {"face": "faces", "edge": "edges", "vertex": "vertexes"}


def _owner(self, spec):
    return _body(self, spec["of"]) if "of" in spec else self.body


def _ref(self, spec, step_id):
    """(object, sub) for a pick spec."""
    if isinstance(spec, str):
        if spec in _PLANE_ROLE:
            return (_origin(self.body, _PLANE_ROLE, spec), "")
        if spec in _AXIS_ROLE:
            return (_origin(self.body, _AXIS_ROLE, spec), "")
        raise BuildError("%s: unknown plane or axis %r" % (step_id, spec))
    if "body" in spec:
        return (_body(self, spec["body"]), "")
    for key, kind in ELEMENTS.items():
        if key in spec:
            tip = _owner(self, spec).Tip
            names = _select(tip.Shape, spec[key], kind)
            if len(names) != 1:
                raise BuildError(
                    "%s: the %s selector must pick one, got %s" % (step_id, key, names)
                )
            return (tip, names[0])
    raise BuildError(
        "%s: a pick is a plane, an axis, a face, an edge, a vertex or a body" % step_id
    )


def _select(shape, selector, kind):
    if kind != "vertexes":
        return selectors.select(shape, selector, kind)
    # corners: the vertexes at the extremes the selector's "at" names (no other filters)
    found = list(enumerate(shape.Vertexes, 1))
    conditions = selector.get("at", [])
    for cond in conditions if isinstance(conditions, list) else [conditions]:
        axis = {"x": 0, "y": 1, "z": 2}[cond["axis"]]
        values = [(v.Point.x, v.Point.y, v.Point.z)[axis] for _i, v in found]
        want = cond["value"]
        want = max(values) if want == "max" else min(values) if want == "min" else want
        found = [
            (i, v) for i, v in found if abs((v.Point.x, v.Point.y, v.Point.z)[axis] - want) < 1e-6
        ]
    return ["Vertex%d" % i for i, _v in found]


def _faces(self, step):
    body = _body(self, step["of"]) if "of" in step else self.body
    tip = body.Tip
    names = selectors.select(tip.Shape, step["faces"], "faces")
    if not names:
        raise BuildError("%s: the face selector picked nothing" % step["id"])
    return body, (tip, names)


def _done(self, step, feature, kind, measured, checked=None):
    self.doc.recompute()
    _check_state(step, checked or [feature])
    self.objects[step["id"]] = feature
    self.ops[step["id"]] = kind
    _measure(self, measured)
    return feature


def op_history_off(self, step):
    from sciforge import direct

    direct.history_off(self.doc)
    self._forget_dead()


def op_history_on(self, step):
    from sciforge import direct

    direct.history_on(self.doc)
    self.doc.recompute()


def _forget_dead(self):
    for key in [k for k, obj in self.objects.items() if not _alive(obj)]:
        self.objects.pop(key, None)


def _replace_options(self, step):
    body, faces = _faces(self, step)
    return body, {
        "faces": faces,
        "tangent_chain": step.get("tangent_chain", True),
        "target": _ref(self, step["target"], step["id"]),
    }


def op_replace_face(self, step):
    from sciforge import replace_face

    body, options = _replace_options(self, step)
    try:
        feature = replace_face.build(options)
    except replace_face.ReplaceFaceError as exc:
        raise BuildError("replace_face %r: %s" % (step["id"], exc))
    self.body = body
    return _done(self, step, feature, "replace_face", [body])


def _split_face_options(self, step):
    body, faces = _faces(self, step)
    options = {
        "faces": faces,
        "tool": _ref(self, step["tool"], step["id"]),
        "extend": bool(step.get("extend", False)),
        "split_type": step.get("split_type", "surface"),
    }
    if "direction" in step:
        options["direction"] = _ref(self, step["direction"], step["id"])
    return body, options


def op_split_face(self, step):
    from sciforge import split_face

    body, options = _split_face_options(self, step)
    try:
        feature = split_face.build(options)
    except split_face.SplitFaceError as exc:
        raise BuildError("split_face %r: %s" % (step["id"], exc))
    self.body = body
    return _done(self, step, feature, "split_face", [body])


def op_silhouette_split(self, step):
    from sciforge import silhouette, split

    body = _body(self, step["body"])
    options = {
        "direction": _ref(self, step["direction"], step["id"]),
        "body": body,
        "operation": step.get("operation", "faces"),
    }
    try:
        feature = silhouette.build(options)
    except silhouette.SilhouetteError as exc:
        raise BuildError("silhouette_split %r: %s" % (step["id"], exc))
    self.doc.recompute()
    self.body = body
    pieces = split.pieces_of(feature)
    return _done(
        self,
        step,
        feature,
        "silhouette_split",
        [body] + split.piece_bodies(feature),
        [feature] + pieces,
    )


def op_align_bodies(self, step):
    from sciforge import align

    source = _ref(self, step["from"], step["id"])
    options = {
        "objects": "bodies",
        "from_pick": (source[0], source[1], None),
        "to_pick": _ref(self, step["to"], step["id"]) + (None,),
        "flip": bool(step.get("flip", False)),
        "turns": int(step.get("turns", 0)),
    }
    try:
        steps = align.build(options)
    except align.AlignError as exc:
        raise BuildError("align_bodies %r: %s" % (step["id"], exc))
    moved = align.moved_thing(steps[0])
    return _done(self, step, steps[0], "align_bodies", [moved], steps)


def op_modify_edit(self, step):
    from sciforge import align, bodies, replace_face, silhouette, split, split_face

    target = self.objects.get(step["target"])
    kind = self.ops.get(step["target"])
    if target is None:
        raise BuildError("modify_edit: unknown step %r" % step["target"])
    changes = dict(step.get("set", {}))
    refs = ("target", "tool", "direction", "from", "to")
    for key in refs:
        if key in changes:
            changes[key] = _ref(self, changes[key], step["target"])
    try:
        if kind == "replace_face":
            options = replace_face.read(target)
            options.update(changes)
            feature = replace_face.build(options, target)
            measured = [bodies.body_of(feature)]
        elif kind == "split_face":
            options = split_face.read(target)
            options.update(changes)
            feature = split_face.build(options, target)
            measured = [bodies.body_of(feature)]
        elif kind == "silhouette_split":
            options = silhouette.read(target)
            options.update(changes)
            feature = silhouette.build(options, target)
            self.doc.recompute()
            measured = [bodies.body_of(feature)] + split.piece_bodies(feature)
        elif kind == "align_bodies":
            options = align.read(target)
            options.pop("labels", None)
            for key in ("from", "to"):
                if key in changes:
                    obj, sub = changes.pop(key)
                    options[key + "_pick"] = (obj, sub, None)
                    options[key + "_frame"] = None
            options.update(changes)
            feature = align.build(options, [target])[0]
            measured = [align.moved_thing(feature)]
        else:
            raise BuildError("modify_edit: %r is not a Modify step" % step["target"])
    except (
        replace_face.ReplaceFaceError,
        split_face.SplitFaceError,
        silhouette.SilhouetteError,
        align.AlignError,
    ) as exc:
        raise BuildError("modify_edit %r: %s" % (step["target"], exc))
    self.objects[step["target"]] = feature
    self.doc.recompute()
    _check_state(step, [feature])
    _measure(self, measured)
    return feature


def op_remove_bodies(self, step):
    from sciforge import bodies, remove

    found = [_body(self, s) for s in step["steps"]]
    try:
        remove.make(found)
    except remove.RemoveError as exc:
        raise BuildError("remove_bodies: %s" % exc)
    self.doc.recompute()
    left = [b for b in bodies.list_bodies(self.doc) if remove.removed(b) is None]
    _measure(self, left)


Builder._forget_dead = _forget_dead
Builder.op_history_off = op_history_off
Builder.op_history_on = op_history_on
Builder.op_replace_face = op_replace_face
Builder.op_split_face = op_split_face
Builder.op_silhouette_split = op_silhouette_split
Builder.op_align_bodies = op_align_bodies
Builder.op_modify_edit = op_modify_edit
Builder.op_remove_bodies = op_remove_bodies
