# SPDX-License-Identifier: LGPL-2.1-or-later
"""Golden-model checks for the SHEET METAL forming steps (rules, Flange, Hem, Bend) (pure Python).
Imported at the end of schema.py; it adds its step keys and wraps schema.validate, as
gear_schema does. Steps: sf_sheet_rule, sf_flange, sf_flange_edit (built by
sciforge/ai/ops/sheetmetal_ops.py)."""

from . import schema

KINDS = ("base", "contour", "edge")
OPERATIONS = ("new_body", "new_component", "join")
CHOICES = {
    "orientation": ("side1", "side2", "centered"),
    "direction": ("one_side", "symmetric", "two_sides"),
    "extent": ("distance", "to_object"),
    "datum": ("inner", "outer", "tangent"),
    "position": ("inside", "outside", "adjacent", "tangent"),
    "width_type": ("full", "symmetric", "two_sides", "two_offsets"),
    "relief_shape": ("straight", "tear", "round"),
    "corner_shape": (
        "round",
        "square",
        "tear",
        "trim_to_bend",
        "linear_weld",
        "arc_weld",
        "laser_weld",
    ),
    "corner_placement": ("intersection", "tangent"),
    "corner3_shape": ("no_replacement", "intersection", "full_round", "round_with_radius"),
}
NUMBERS = {
    "height",
    "distance",
    "distance2",
    "width",
    "distance1",
    "width2",
    "target_offset",
    "angle",
    "bend_radius",
    "relief_width",
    "relief_depth",
    "relief_remnant",
    "corner_size",
    "corner3_radius",
}
BOOLS = {
    "flip",
    "override_bend_radius",
    "override_bend_relief",
    "override_corner_relief",
    "override_corner3_relief",
}
OPTIONS = set(CHOICES) | NUMBERS | BOOLS
RULE_FIELDS = {
    "units",
    "thickness",
    "bend_radius",
    "k_factor",
    "unfold_rule",
    "miter_gap",
    "bend_relief_shape",
    "bend_relief_width",
    "bend_relief_depth",
    "bend_relief_remnant",
    "corner_relief_2bend_shape",
    "corner_relief_2bend_placement",
    "corner_relief_2bend_size",
    "corner_relief_3bend_shape",
    "corner_relief_3bend_radius",
}

schema.STEP_KEYS["sf_sheet_rule"] = ({"name"}, {"from", "set", "active", "comment"})
schema.STEP_KEYS["sf_flange"] = (
    {"id", "kind"},
    {"profile", "at", "edges", "rule", "operation", "options", "target", "offset_refs", "comment"},
)
schema.STEP_KEYS["sf_flange_edit"] = ({"target", "set"}, {"comment"})


def _check_options(here, values):
    if not isinstance(values, dict):
        schema._fail(here, "'options' / 'set' is an object of flange options")
    for key, value in values.items():
        if key not in OPTIONS:
            schema._fail(here, "flange option %r is unknown" % key)
        if key in CHOICES and value not in CHOICES[key]:
            schema._fail(here, "'%s' must be one of %s" % (key, CHOICES[key]))
        if key in BOOLS and not isinstance(value, bool):
            schema._fail(here, "'%s' is true or false" % key)
        if key in NUMBERS:
            schema._check_number(here + "." + key, value)


def check_steps(model):
    where = model.get("id", "<no id>")
    seen = {}
    for i, step in enumerate(model["steps"]):
        here = "%s.steps[%d]" % (where, i)
        op = step["op"]
        if op == "sf_sheet_rule":
            values = step.get("set", {})
            if not isinstance(values, dict) or any(k not in RULE_FIELDS for k in values):
                schema._fail(here, "'set' is {rule field: value}")
        if op == "sf_flange":
            if step["kind"] not in KINDS:
                schema._fail(here, "'kind' must be one of %s" % (KINDS,))
            if step["kind"] == "edge":
                if not isinstance(step.get("edges"), list) or not step["edges"]:
                    schema._fail(here, "an edge flange needs 'edges': [[x, y, z], ...]")
                for point in step["edges"]:
                    if not isinstance(point, list) or len(point) != 3:
                        schema._fail(here, "each edge is a point [x, y, z] on it")
            elif "profile" not in step:
                schema._fail(here, "a base or contour flange needs 'profile' (a sketch id)")
            elif seen.get(step["profile"]) not in ("sketch", "sf_curves"):
                schema._fail(here, "'profile' must name an earlier sketch step")
            if step.get("operation", "new_body") not in OPERATIONS:
                schema._fail(here, "'operation' must be one of %s" % (OPERATIONS,))
            _check_options(here, step.get("options", {}))
            targets = [step["target"]] if "target" in step else []
            refs = step.get("offset_refs", [])
            if not isinstance(refs, list) or len(refs) not in (0, 2):
                schema._fail(here, "'offset_refs' is two planes")
            for target in targets + list(refs):
                if not isinstance(target, dict) or target.get("plane") not in ("XY", "XZ", "YZ"):
                    schema._fail(here, "a plane is {'plane': 'XY'|'XZ'|'YZ', 'offset': d}")
        if op == "sf_flange_edit":
            if seen.get(step["target"]) != "sf_flange":
                schema._fail(here, "'target' must name an earlier sf_flange step")
            if not step["set"]:
                schema._fail(here, "'set' is a non-empty object of options")
            _check_options(here, step["set"])
        if "id" in step:
            seen[step["id"]] = op


_validate_before_sheetmetal = schema.validate


def validate(model):
    _validate_before_sheetmetal(model)
    check_steps(model)
    return model


schema.validate = validate
