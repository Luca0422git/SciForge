# SPDX-License-Identifier: LGPL-2.1-or-later
"""Design steps for the SURFACE tab, part 3, built with the same SciForge code the dialogs use,
registered on core.Builder when the package is imported. The step format is checked by
SciForgeTests/golden/surface3_schema.py. (Empty until that area's builder fills it.)"""

# --- surface-4 ---
# SURFACE > MODIFY on surface bodies (sciforge/surfmod.py, the code the dialogs run):
#   {"op": "sf_surface_modify", "id": "f1", "kind": "surface_fillet", "edges": selector,
#    "options": {"radius": 3}}
#      kind: surface_fillet / surface_chamfer (edges), surface_delete_face / surface_merge /
#      surface_press_pull (faces); options as surfmod_core.DEFAULTS. Works on the body the
#      model is on (the last surface step's body), at its end.
#   {"op": "sf_surface_modify_edit", "target": "f1", "set": {"radius": 2}}
#      double-click the step in the timeline and change its values
from .core import Builder as _Builder  # noqa: E402
from .core import BuildError as _BuildError  # noqa: E402


def op_sf_surface_modify(self, step):
    from sciforge import surfmod

    from . import selectors

    kind = step["kind"]
    where = "sf_surface_modify %r" % step["id"]
    body = self.body
    base = body.Tip if body is not None else None
    if base is None:
        raise _BuildError("%s: no body to work on" % where)
    what = "edges" if "edges" in step else "faces"
    try:
        names = selectors.select(base.Shape, step[what], what)
    except Exception as exc:
        raise _BuildError("%s: %s" % (where, exc))
    try:
        feature = surfmod.make(kind, body, base, names, dict(step.get("options") or {}))
    except surfmod.SurfaceModifyError as exc:
        raise _BuildError("%s: %s" % (where, exc))
    self.doc.recompute()
    _surface4_check(feature, where)
    self.objects[step["id"]] = feature
    self.ops[step["id"]] = "sf_surface_modify"
    return feature


def op_sf_surface_modify_edit(self, step):
    from sciforge import surfmod

    where = "sf_surface_modify_edit %r" % step["target"]
    feature = self.objects.get(step["target"])
    if feature is None or not surfmod.is_step(feature):
        raise _BuildError("%s: not a surface modify step" % where)
    base, names, options = surfmod.read(feature)
    options.update(step["set"])
    try:
        surfmod.preview(surfmod.kind_of(feature), feature.BaseFeature.Shape, names, options)
    except surfmod.SurfaceModifyError as exc:
        raise _BuildError("%s: %s" % (where, exc))
    surfmod.apply(feature, base, names, options)
    self.doc.recompute()
    _surface4_check(feature, where)
    return feature


def _surface4_check(feature, where):
    state = list(getattr(feature, "State", []))
    if "Invalid" in state or "Error" in state:
        raise _BuildError("%s failed: %s" % (where, feature.getStatusString()))


_Builder.op_sf_surface_modify = op_sf_surface_modify
_Builder.op_sf_surface_modify_edit = op_sf_surface_modify_edit
