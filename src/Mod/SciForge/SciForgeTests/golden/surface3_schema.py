# SPDX-License-Identifier: LGPL-2.1-or-later
"""Golden-model checks for the SURFACE tab, part 3 (pure Python). Imported at the end of schema.py;
it adds its step keys and wraps schema.validate, as gear_schema does. (Empty until that area's
builder fills it.)"""

from . import schema  # noqa: F401

# --- surface-4 ---
# SURFACE > MODIFY on surface bodies (sciforge/ai/ops/surface3_ops.py, surface-4 block).
SURFACE4_KINDS = {
    "surface_fillet": ("edges", {"radius", "radius_type", "radius2", "tangent_chain"}),
    "surface_chamfer": (
        "edges",
        {"chamfer_type", "distance", "distance2", "angle", "flip", "tangent_chain"},
    ),
    "surface_delete_face": ("faces", set()),
    "surface_merge": ("faces", set()),
    "surface_press_pull": ("faces", {"distance"}),
}
schema.STEP_KEYS["sf_surface_modify"] = (
    {"id", "kind"},
    {"edges", "faces", "options", "comment"},
)
schema.STEP_KEYS["sf_surface_modify_edit"] = ({"target", "set"}, {"comment"})


def _surface4_values(here, kind, values):
    if not isinstance(values, dict):
        schema._fail(here, "'options' / 'set' is an object of values")
    allowed = SURFACE4_KINDS[kind][1]
    for key, value in values.items():
        if key not in allowed:
            schema._fail(here, "%s takes no %r" % (kind, key))
        if key == "chamfer_type":
            if value not in ("equal", "two", "angle"):
                schema._fail(here, "'chamfer_type' must be equal, two or angle")
        elif key == "radius_type":
            if value not in ("constant", "chord", "variable"):
                schema._fail(here, "'radius_type' must be constant, chord or variable")
        elif key in ("flip", "tangent_chain"):
            if not isinstance(value, bool):
                schema._fail(here, "%r is true or false" % key)
        else:
            schema._check_number(here + "." + key, value)


def _surface4_steps(model):
    where = model.get("id", "<no id>")
    seen = {}
    for i, step in enumerate(model["steps"]):
        here = "%s.steps[%d]" % (where, i)
        op = step["op"]
        if op == "sf_surface_modify":
            kind = step["kind"]
            if kind not in SURFACE4_KINDS:
                schema._fail(here, "'kind' must be one of %s" % sorted(SURFACE4_KINDS))
            what = SURFACE4_KINDS[kind][0]
            if what not in step or ({"edges", "faces"} - {what}) & set(step):
                schema._fail(here, "%s picks %s: give an '%s' selector" % (kind, what, what))
            _surface4_values(here, kind, step.get("options", {}))
            seen[step["id"]] = kind
        elif op == "sf_surface_modify_edit":
            kind = seen.get(step["target"])
            if kind is None:
                schema._fail(here, "'target' must name an earlier sf_surface_modify step")
            if not step["set"]:
                schema._fail(here, "'set' is a non-empty object of values")
            _surface4_values(here, kind, step["set"])


_validate_before_surface4 = schema.validate


def _validate_surface4(model):
    _validate_before_surface4(model)
    _surface4_steps(model)
    return model


schema.validate = _validate_surface4
