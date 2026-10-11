# SPDX-License-Identifier: LGPL-2.1-or-later
"""Golden-model steps for history edits around Fusion-style fillets and chamfers, built with
the same code as the Fillet / Chamfer dialogs (sciforge/blend.py). Registered on
builder.Builder when builder.py is imported.

  {"op": "blend_insert", "id": "c1", "kind": "fillet" | "chamfer", <options>,
   "edges": sel, "faces": sel}
      A Fillet / Chamfer made while the timeline marker is rolled back (after a "roll"
      step): it goes in at the marker, and the blends after it keep their edges (FreeCAD
      alone lost them: "Invalid edge link"). Options as blend_fillet / blend_chamfer:
      "radius"; "distance", "chamfer_type", "distance2", "angle", "flip".

  {"op": "blend_edit", "target": "f1", "add_edges": sel, "add_faces": sel,
   "set": {"radius": 3}}
      Double-click a Fillet / Chamfer in the timeline, pick more edges / faces (selectors on
      the shape it is applied to) and/or change its options; the blends after it keep
      their edges.
"""

from . import selectors
from .builder import Builder, BuildError

OPTIONS = ("radius", "chamfer_type", "distance", "distance2", "angle", "flip")


def _options(kind, step):
    from sciforge import blend

    options = blend.default_options(kind)
    for key in OPTIONS:
        if key in step:
            options[key] = step[key]
    if kind == "chamfer" and "distance2" not in step and "distance" in step:
        options["distance2"] = step["distance"]
    return options


def _picks(shape, step, edge_key="edges", face_key="faces"):
    refs = []
    if edge_key in step:
        refs += selectors.select(shape, step[edge_key], "edges")
    if face_key in step:
        refs += selectors.select(shape, step[face_key], "faces")
    return refs


def _broken(builder, what):
    broken = [
        o.Label
        for o in builder.body.Group
        if "Invalid" in list(getattr(o, "State", [])) or "Error" in list(getattr(o, "State", []))
    ]
    if broken:
        raise BuildError("%s: these steps broke: %s" % (what, ", ".join(broken)))


def op_blend_insert(self, step):
    from sciforge import blend

    kind = step["kind"]
    base = self._tip()
    info = blend.ShapeInfo(base.Shape)
    refs = _picks(base.Shape, step)
    if not refs:
        raise BuildError("blend_insert %r: nothing picked" % step["id"])
    options = _options(kind, step)
    try:
        blend.trial(kind, info, refs, options)  # the dialog refuses what fails here
        feature = blend.insert(self.body, base, refs, kind, options, step["id"])
    except blend.BlendError as exc:
        raise BuildError("blend_insert %r: %s" % (step["id"], exc))
    self.objects[step["id"]] = feature
    self.ops[step["id"]] = kind
    _broken(self, "blend_insert %r" % step["id"])
    return feature


def op_blend_edit(self, step):
    from sciforge import blend

    target = self.objects[step["target"]]
    kind = blend.kind_of(target)
    if kind is None:
        raise BuildError("blend_edit %r: not a fillet or chamfer" % step["target"])
    base, refs = blend.refs_of(target)
    info = blend.ShapeInfo(base.Shape)
    refs = list(refs) + _picks(base.Shape, step, "add_edges", "add_faces")
    options = blend.read(target)
    options.update(step.get("set", {}))
    keep = blend.References(self.body, target)
    try:
        blend.trial(kind, info, refs, options)
    except blend.BlendError as exc:
        raise BuildError("blend_edit %r: %s" % (step["target"], exc))
    blend.set_refs(target, base, blend.base_subs(info, refs))
    blend.apply(target, options)
    blend.recompute_keeping(self.doc, keep)
    _broken(self, "blend_edit %r" % step["target"])
    return target


Builder.op_blend_insert = op_blend_insert
Builder.op_blend_edit = op_blend_edit
