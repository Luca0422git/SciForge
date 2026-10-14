# SPDX-License-Identifier: LGPL-2.1-or-later
"""Golden-model steps of Modify part 2, built with the same SciForge code as the dialogs
(sciforge/drafting.py, shelling.py, scale.py, move_face.py, presspull...). Registered on
builder.Builder when builder.py is imported. The step formats are in golden/modify2_schema.py.
"""

from . import selectors
from .builder import _PLANE_ROLE, Builder, BuildError


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
