# SPDX-License-Identifier: LGPL-2.1-or-later
"""Design steps of Modify part 2, built with the same SciForge code as the dialogs
(sciforge/drafting.py, shelling.py, scale.py, move_face.py, presspull...). Registered on
core.Builder when the package is imported. The step formats are checked by
SciForgeTests/golden/modify2_schema.py.
"""

from . import selectors
from .core import _PLANE_ROLE, Builder, BuildError


def _select_faces(tip, spec, what):
    names = selectors.select(tip.Shape, spec, "faces")
    if not names:
        raise BuildError("%s: the face selector picked nothing" % what)
    return names


def _body_of_step(builder, name):
    from sciforge import bodies

    obj = builder.objects.get(name)
    if obj is None:
        raise BuildError("unknown step %r" % name)
    body = bodies.body_of(obj) or (obj if bodies.is_body(obj) else None)
    if body is None:
        raise BuildError("%r is not in a body" % name)
    return body


def _failed(objs, what):
    for obj in objs:
        state = list(getattr(obj, "State", []))
        if "Invalid" in state or "Error" in state:
            raise BuildError("%s failed: %s" % (what, obj.getStatusString()))


def _ref(builder, spec, tip, what, element="faces"):
    """An origin plane name, {"face": sel}, {"edges": sel}, {"sketch": id[, "edge": n]}."""
    if isinstance(spec, str):
        if spec not in _PLANE_ROLE:
            raise BuildError("%s: %r is no origin plane" % (what, spec))
        return [(builder._origin(_PLANE_ROLE[spec]), "")]
    if "face" in spec:
        names = selectors.select(tip.Shape, spec["face"], "faces")
        if len(names) != 1:
            raise BuildError("%s: the face selector must pick one face" % what)
        return [(tip, names[0])]
    if "edges" in spec:
        names = selectors.select(tip.Shape, spec["edges"], "edges")
        if not names:
            raise BuildError("%s: the edge selector picked nothing" % what)
        return [(tip, n) for n in names]
    if "sketch" in spec:
        sketch = builder.objects.get(spec["sketch"])
        if sketch is None:
            raise BuildError("%s: unknown sketch %r" % (what, spec["sketch"]))
        return [(sketch, "Edge%d" % spec["edge"] if "edge" in spec else "")]
    raise BuildError("%s: cannot read %r" % (what, spec))


# -- Draft: Two Side, Symmetric, Parting Line, several bodies --------------------------------------
def _draft_members(builder, step, what):
    """[(body, base, names)]: the faces to draft, per body (the first is the lead's)."""
    from sciforge import modify_bodies

    spec = step["faces"]
    if isinstance(spec, list):
        out = []
        for item in spec:
            body = _body_of_step(builder, item["body"])
            base = body.Tip if not out else modify_bodies.base_for(None, body)
            out.append((body, base, _select_faces(base, item["faces"], what)))
        return out
    base = builder._tip()
    return [(builder.body, base, _select_faces(base, spec, what))]


def _draft_options(builder, step, base, what):
    options = {
        "angle": float(step.get("angle", 1.0)),
        "angle2": float(step.get("angle2", step.get("angle", 1.0))),
        "flip": bool(step.get("flip", False)),
        "draft_type": step.get("draft_type", "fixed"),
        "sides": step.get("sides", "one"),
    }
    if "parting" in step:
        options["parting"] = _ref(builder, step["parting"], base, what, "edges")
    return options


def op_sf_draft2(self, step):
    from sciforge import drafting, modify_bodies

    what = "sf_draft2 %r" % step["id"]
    members = _draft_members(self, step, what)
    body, base, names = members[0]
    plane = _ref(self, step["plane"], base, what)[0]
    options = _draft_options(self, step, base, what)
    try:
        drafting.check(base.Shape, plane, names, options)
        feature = drafting.make(body, base, plane, names, options, name=step["id"])
        if len(members) > 1:
            modify_bodies.sync(
                feature,
                [(b, n) for b, _base, n in members[1:]],
                modify_bodies.DraftFollower,
                "Draft",
            )
    except (drafting.DraftError, modify_bodies.FollowerError) as exc:
        raise BuildError("%s: %s" % (what, exc))
    self.objects[step["id"]] = feature
    self.ops[step["id"]] = "sf_draft2"
    self.doc.recompute()
    _failed([feature] + modify_bodies.followers_of(feature), what)
    if len(members) > 1:
        self.all_bodies = True
    return feature


def op_sf_draft2_edit(self, step):
    from sciforge import drafting, follow

    target = self.objects.get(step["target"])
    what = "sf_draft2_edit %r" % step["target"]
    if target is None or self.ops.get(step["target"]) != "sf_draft2":
        raise BuildError("%s: not a sf_draft2 step" % what)
    base, plane, names, options, formula = drafting.read(target)
    options.update(step["set"])
    later = follow.snapshot(self.body, target)
    try:
        drafting.check(base.Shape, plane, names, options)
        target = drafting.update(target, base, plane, names, options, formula)
    except drafting.DraftError as exc:
        raise BuildError("%s: %s" % (what, exc))
    self.objects[step["target"]] = target
    follow.recompute(self.doc, later)
    _failed([target], what)
    return target


Builder.op_sf_draft2 = op_sf_draft2
Builder.op_sf_draft2_edit = op_sf_draft2_edit


# -- Shell and Scale over several bodies, Scale of sketches ------------------------------
SHELL_OPTIONS = ("inside", "outside", "direction", "shell_type")


def op_sf_shell_bodies(self, step):
    """One Shell over several bodies: [{"body": id, "faces": sel}] takes faces away, a bare
    {"body": id} makes that body hollow."""
    from sciforge import modify_bodies, shelling

    what = "sf_shell_bodies %r" % step["id"]
    members = []
    for item in step["bodies"]:
        body = _body_of_step(self, item["body"])
        base = body.Tip
        base.Shape.tessellate(0.1)  # as drawn in the view (see shell_draft_ops)
        names = _select_faces(base, item["faces"], what) if "faces" in item else []
        members.append((body, base, names))
    options = {k: step[k] for k in SHELL_OPTIONS if k in step}
    body, base, names = members[0]
    try:
        for _b, other, other_names in members:
            shelling.trial(other.Shape, other_names, options)
        feature = shelling.make(body, base, names, options, name=step["id"])
        modify_bodies.sync(
            feature, [(b, n) for b, _base, n in members[1:]], modify_bodies.ShellFollower, "Shell"
        )
    except (shelling.ShellError, modify_bodies.FollowerError) as exc:
        raise BuildError("%s: %s" % (what, exc))
    self.objects[step["id"]] = feature
    self.ops[step["id"]] = "sf_shell_bodies"
    self.doc.recompute()
    _failed([feature] + modify_bodies.followers_of(feature), what)
    self.all_bodies = True
    return feature


def _design_point(step):
    import FreeCAD as App

    point = step.get("point")
    return App.Vector(*point) if point else None


def _scale_options(step):
    if "factors" in step:
        return {"uniform": False, "factors": [float(v) for v in step["factors"]]}
    return {"uniform": True, "factor": float(step.get("factor", 1.0))}


def op_sf_scale_bodies(self, step):
    """One Scale over several bodies, about the design origin (or a corner at "point")."""
    from sciforge import modify_bodies, scale

    what = "sf_scale_bodies %r" % step["id"]
    members = [_body_of_step(self, name) for name in step["bodies"]]
    options = _scale_options(step)
    point = _design_point(step)
    body = members[0]
    base = body.Tip
    ref = None
    if point is not None:
        for i, vertex in enumerate(base.Shape.Vertexes, start=1):
            if (vertex.Point - point).Length < 1e-6:
                ref = (base, "Vertex%d" % i)
        if ref is None:
            raise BuildError("%s: no corner of the first body at %s" % (what, list(point)))
    try:
        feature = scale.make(body, base, ref, options, name=step["id"])
        modify_bodies.sync(
            feature, [(b, None) for b in members[1:]], modify_bodies.ScaleFollower, "Scale"
        )
    except (scale.ScaleError, modify_bodies.FollowerError) as exc:
        raise BuildError("%s: %s" % (what, exc))
    self.objects[step["id"]] = feature
    self.ops[step["id"]] = "sf_scale_bodies"
    self.doc.recompute()
    _failed([feature] + modify_bodies.followers_of(feature), what)
    self.all_bodies = True
    return feature


def op_sf_scale_sketch(self, step):
    """Modify > Scale with a sketch picked in the browser: its curves (and dimensions)
    scaled about its origin, or about "point" (design coordinates)."""
    from sciforge import scale

    what = "sf_scale_sketch %r" % step["id"]
    sketch = self.objects.get(step["sketch"])
    try:
        record, _kept = scale.make_sketch_scale(
            self.doc, [sketch], step["factor"], _design_point(step), name=step["id"]
        )
    except scale.ScaleError as exc:
        raise BuildError("%s: %s" % (what, exc))
    self.objects[step["id"]] = record
    self.ops[step["id"]] = "sf_scale_sketch"
    self.doc.recompute()
    _failed([sketch], what)
    return record


def op_sf_scale_sketch_edit(self, step):
    from sciforge import scale

    record = self.objects.get(step["target"])
    try:
        scale.edit_sketch_scale(record, step["factor"])
    except scale.ScaleError as exc:
        raise BuildError("sf_scale_sketch_edit %r: %s" % (step["target"], exc))
    self.doc.recompute()
    return record


Builder.op_sf_shell_bodies = op_sf_shell_bodies
Builder.op_sf_scale_bodies = op_sf_scale_bodies
Builder.op_sf_scale_sketch = op_sf_scale_sketch
Builder.op_sf_scale_sketch_edit = op_sf_scale_sketch_edit


# -- Move/Copy of faces ----------------------------------------------------------------------------
def _move_options(step, options=None):
    options = dict(options or {})
    if "move" in step:
        dx, dy, dz = (float(v) for v in step["move"])
        options.update(move_type="translate", dx=dx, dy=dy, dz=dz)
    if "rotate" in step:
        rot = step["rotate"]
        options.update(
            move_type="rotate",
            axis_point=[float(v) for v in rot.get("center", [0, 0, 0])],
            axis_dir=[float(v) for v in rot["axis"]],
            angle=float(rot["angle"]),
        )
    return options


def op_move_face(self, step):
    """Move/Copy with Move Object Faces: the faces moved (translate) or turned (rotate)."""
    from sciforge import move, move_face

    what = "move_face %r" % step["id"]
    base = self._tip()
    names = _select_faces(base, step["faces"], what)
    options = _move_options(step, {"faces": (base, names)})
    try:
        feature = move_face.build(options, name=step["id"])
    except move.MoveError as exc:
        raise BuildError("%s: %s" % (what, exc))
    self.objects[step["id"]] = feature
    self.ops[step["id"]] = "move_face"
    self._recompute(step, feature)
    return feature


def op_move_face_edit(self, step):
    from sciforge import move, move_face

    target = self.objects.get(step["target"])
    what = "move_face_edit %r" % step["target"]
    options = move_face.read(target)
    for key in ("dx", "dy", "dz", "angle"):
        options[key] = 0.0
    options = _move_options(step, options)
    try:
        move_face.build(options, target)
    except move.MoveError as exc:
        raise BuildError("%s: %s" % (what, exc))
    self.doc.recompute()
    _failed([target], what)
    return target


Builder.op_move_face = op_move_face
Builder.op_move_face_edit = op_move_face_edit


# -- Press Pull Offset Type ------------------------------------------------------------------------
def op_press_pull_type(self, step):
    """Press Pull on faces with an Offset Type: "new" (and "automatic" on plain faces) adds a
    Press Pull step; "modify" changes the extrude that made the faces (no new step)."""
    from sciforge import offset_type, presspull

    what = "press_pull_type %r" % step["id"]
    base = self._tip()
    names = _select_faces(base, step["faces"], what)
    kind = step.get("offset_type", "automatic")
    if kind == "modify":
        try:
            feature, prop, sign = offset_type.modify_target(self.body, base, names)
            start = getattr(feature, prop).Value
            offset_type.apply(feature, prop, start, sign, float(step["distance"]))
        except offset_type.OffsetTypeError as exc:
            raise BuildError("%s: %s" % (what, exc))
        self.objects[step["id"]] = feature
        self.ops[step["id"]] = "press_pull_type"
        self.doc.recompute()
        _failed([feature], what)
        return feature
    obj = presspull.make(self.body, base, names, float(step["distance"]), step["id"])
    self.objects[step["id"]] = obj
    self.ops[step["id"]] = "press_pull_type"
    self._recompute(step, obj)
    return obj


Builder.op_press_pull_type = op_press_pull_type
