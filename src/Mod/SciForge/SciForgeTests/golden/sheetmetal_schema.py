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
    {"profile", "at", "edges", "rule", "operation", "options", "target", "comment"},
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
            target = step.get("target")
            if target is not None and (
                not isinstance(target, dict) or target.get("plane") not in ("XY", "XZ", "YZ")
            ):
                schema._fail(here, "'target' is {'plane': 'XY'|'XZ'|'YZ', 'offset': d}")
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


# --- sm-more ---
# Bend, Hem, Join by Bend, Corner Closure, Lofted Flange, sheet metal Fillet / Chamfer
# (sciforge/ai/ops/sheetmetal_ops.py, its "sm-more" block).
SMM_OPTIONS = {
    "sf_sm_bend": {
        "angle": "number",
        "position": ("start", "center", "end"),
        "flip": "bool",
        "bend_relief": "bool",
        "corner_relief": "bool",
        "override_radius": "bool",
        "radius": "number",
    },
    "sf_sm_hem": {
        "type": ("flat", "open", "rolled", "teardrop", "rope", "double"),
        "length": "number",
        "gap": "number",
        "radius": "number",
        "angle": "number",
        "setback": "number",
        "position": ("inside", "outside", "adjacent", "tangent"),
        "flip": "bool",
        "miter": "bool",
        "override": "bool",
        "radius_override": "number",
    },
    "sf_sm_join_bend": {"use_rule_radius": "bool", "radius": "number"},
    "sf_sm_corner_closure": {
        "alignment": ("symmetric", "overlap"),
        "gap": "number",
        "overlap": "number",
        "flip_overlap": "bool",
        "extend_aligned": "bool",
        "relief": ("round", "square", "trim_to_bend"),
        "relief_size": "number",
    },
    "sf_sm_lofted_flange": {
        "forming": ("brake", "die"),
        "control": ("chord_tolerance", "facet_angle", "facet_distance", "facet_number"),
        "value": "number",
        "orientation": ("side1", "side2", "center"),
    },
}
SMM_POINT = "a point [x, y, z]"
schema.STEP_KEYS["sf_sm_bend"] = ({"id", "face", "lines"}, {"at", "options", "comment"})
schema.STEP_KEYS["sf_sm_hem"] = ({"id", "edges"}, {"options", "comment"})
schema.STEP_KEYS["sf_sm_join_bend"] = ({"id", "first", "other", "second"}, {"options", "comment"})
schema.STEP_KEYS["sf_sm_corner_closure"] = (
    {"id", "dominant", "submissive"},
    {"options", "comment"},
)
schema.STEP_KEYS["sf_sm_lofted_flange"] = (
    {"id", "profile1", "profile2"},
    {"rule", "operation", "options", "comment"},
)
schema.STEP_KEYS["sf_sm_fillet"] = ({"id", "sets"}, {"comment"})
schema.STEP_KEYS["sf_sm_chamfer"] = ({"id", "sets"}, {"comment"})
schema.STEP_KEYS["sf_sm_more_edit"] = ({"target", "set"}, {"comment"})


def _smm_point_ok(here, value):
    if not isinstance(value, list) or len(value) != 3:
        schema._fail(here, "expected %s" % SMM_POINT)
    for c in value:
        schema._check_number(here, c)


def _smm_options(here, op, values):
    table = SMM_OPTIONS.get(op, {})
    if not isinstance(values, dict):
        schema._fail(here, "'options' is an object")
    for key, value in values.items():
        kind = table.get(key)
        if kind is None:
            schema._fail(here, "%s option %r is unknown" % (op, key))
        if kind == "number":
            schema._check_number(here + "." + key, value)
        elif kind == "bool" and not isinstance(value, bool):
            schema._fail(here, "'%s' is true or false" % key)
        elif isinstance(kind, tuple) and value not in kind:
            schema._fail(here, "'%s' must be one of %s" % (key, kind))


def check_smm_steps(model):
    where = model.get("id", "<no id>")
    seen = {}
    for i, step in enumerate(model["steps"]):
        here = "%s.steps[%d]" % (where, i)
        op = step["op"]
        if op == "sf_sm_bend":
            _smm_point_ok(here + ".face", step["face"])
            if seen.get(step["lines"]) not in ("sketch", "sf_curves"):
                schema._fail(here, "'lines' must name an earlier sketch step")
        if op == "sf_sm_hem":
            if not isinstance(step["edges"], list) or not step["edges"]:
                schema._fail(here, "'edges' is a list of points [x, y, z]")
            for point in step["edges"]:
                _smm_point_ok(here + ".edges", point)
        if op == "sf_sm_join_bend":
            _smm_point_ok(here + ".first", step["first"])
            _smm_point_ok(here + ".second", step["second"])
            if step["other"] not in seen:
                schema._fail(here, "'other' must name an earlier step (of the other body)")
        if op == "sf_sm_corner_closure":
            _smm_point_ok(here + ".dominant", step["dominant"])
            _smm_point_ok(here + ".submissive", step["submissive"])
        if op == "sf_sm_lofted_flange":
            for key in ("profile1", "profile2"):
                if seen.get(step[key]) not in ("sketch", "sf_curves"):
                    schema._fail(here, "'%s' must name an earlier sketch step" % key)
            if step.get("operation", "new_body") not in ("new_body", "join"):
                schema._fail(here, "'operation' must be new_body or join")
        if op in ("sf_sm_fillet", "sf_sm_chamfer"):
            if not isinstance(step["sets"], list) or not step["sets"]:
                schema._fail(here, "'sets' is a list of {edges, value}")
            for entry in step["sets"]:
                if not isinstance(entry, dict) or set(entry) != {"edges", "value"}:
                    schema._fail(here, "each set is {'edges': [points], 'value': mm}")
                schema._check_number(here + ".value", entry["value"])
                for point in entry["edges"]:
                    _smm_point_ok(here + ".edges", point)
        if op in SMM_OPTIONS:
            _smm_options(here, op, step.get("options", {}))
        if op == "sf_sm_more_edit":
            target_op = seen.get(step["target"])
            if target_op not in (
                "sf_sm_bend",
                "sf_sm_hem",
                "sf_sm_corner_closure",
                "sf_sm_lofted_flange",
            ):
                schema._fail(
                    here,
                    "'target' must name an earlier Bend / Hem / Corner Closure "
                    "/ Lofted Flange step",
                )
            _smm_options(here, target_op, step["set"])
        if "id" in step:
            seen[step["id"]] = op


_validate_before_smm = schema.validate


def _validate_smm(model):
    _validate_before_smm(model)
    check_smm_steps(model)
    return model


schema.validate = _validate_smm
