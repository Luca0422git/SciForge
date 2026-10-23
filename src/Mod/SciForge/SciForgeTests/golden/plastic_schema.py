# SPDX-License-Identifier: LGPL-2.1-or-later
"""Golden-model checks for the PLASTIC steps (plastic rules, Boss, Rest) (pure Python). Imported at
the end of schema.py; it adds its step keys and wraps schema.validate, as gear_schema does.
sf_plastic_rule, sf_boss and sf_rest are built by sciforge/ai/ops/plastic_ops.py."""

from . import schema

PLASTIC_RULE_FIELDS = {
    "units",
    "material",
    "thickness",
    "draft_angle",
    "nominal_radius",
    "reveal_height",
    "clearance",
    "minimum_thickness",
    "maximum_thickness",
    "thickness_variation",
    "minimum_draft_angle",
    "knife_edge_threshold",
}
SIDE_CHOICES = {
    "shape": ("blank", "constant_diameter", "constant_thickness"),
    "hole": ("simple", "counterbore", "countersink"),
    "extent": ("through", "from_top", "from_bottom"),
    "step": ("none", "in", "out"),
    "rib_profile": ("none", "chamfer", "fillet"),
    "rib_extent": ("length", "to_next"),
}
SIDE_FLAGS = {"enabled", "ribs"}
SIDE_NUMBERS = {
    "diameter",
    "wall",
    "draft",
    "hole_diameter",
    "hole_draft",
    "hole_depth",
    "major_diameter",
    "major_depth",
    "countersink_angle",
    "step_diameter",
    "step_depth",
    "step_draft",
    "clearance",
    "root_radius",
    "tip_radius",
    "hole_start_radius",
    "hole_end_radius",
    "step_tip_radius",
    "major_tip_radius",
    "major_root_radius",
    "rib_count",
    "rib_total_angle",
    "rib_rotation",
    "rib_cut",
    "rib_chamfer_angle",
    "rib_thickness",
    "rib_draft",
    "rib_outer_draft",
    "rib_length",
    "rib_offset",
}

schema.STEP_KEYS["sf_plastic_rule"] = ({"rule"}, {"set", "comment"})
schema.STEP_KEYS["sf_boss"] = (
    {"id", "points"},
    {"plane", "offset", "screw", "flip", "position", "side1", "side2", "fastener", "comment"},
)
schema.STEP_KEYS["sf_boss_fastener"] = ({"id", "boss"}, {"head", "length", "comment"})
schema.STEP_KEYS["sf_rest"] = (
    {"id", "rect"},
    {"plane", "offset", "thickness", "draft", "flip", "comment"},
)


def _plane(here, step):
    if step.get("plane", "XY") not in ("XY", "XZ", "YZ"):
        schema._fail(here, "'plane' must be XY, XZ or YZ")
    if "offset" in step:
        schema._check_number(here + ".offset", step["offset"])


def _side(here, values):
    if not isinstance(values, dict):
        schema._fail(here, "a side is an object of settings")
    for key, value in values.items():
        if key in SIDE_CHOICES:
            if value not in SIDE_CHOICES[key]:
                schema._fail(here, "'%s' must be one of %s" % (key, SIDE_CHOICES[key]))
        elif key in SIDE_FLAGS:
            if not isinstance(value, bool):
                schema._fail(here, "'%s' is true or false" % key)
        elif key == "rib_extents":
            if not isinstance(value, list) or any(
                v not in ("length", "to_next", "suppressed") for v in value
            ):
                schema._fail(here, "'rib_extents' lists length / to_next / suppressed")
        elif key in SIDE_NUMBERS:
            schema._check_number(here + "." + key, value)
        else:
            schema._fail(here, "unknown boss side setting %r" % key)


def check_steps(model):
    where = model.get("id", "<no id>")
    seen = {}
    for i, step in enumerate(model["steps"]):
        here = "%s.steps[%d]" % (where, i)
        op = step["op"]
        if "id" in step:
            seen.setdefault(step["id"], op)
        if op == "sf_plastic_rule":
            if not isinstance(step["rule"], str) or not step["rule"]:
                schema._fail(here, "'rule' is a rule's name")
            for key in step.get("set", {}) or {}:
                if key not in PLASTIC_RULE_FIELDS:
                    schema._fail(here, "cannot set rule field %r" % key)
        elif op == "sf_boss":
            _plane(here, step)
            points = step["points"]
            if not isinstance(points, list) or not points:
                schema._fail(here, "'points' is a list of [x, y]")
            for p in points:
                if not isinstance(p, list) or len(p) != 2:
                    schema._fail(here, "each point is [x, y]")
                for v in p:
                    schema._check_number(here + ".points", v)
            for key in ("screw", "position"):
                if key in step:
                    schema._check_number(here + "." + key, step[key])
            if "flip" in step and not isinstance(step["flip"], bool):
                schema._fail(here, "'flip' is true or false")
            for side in ("side1", "side2"):
                if side in step:
                    _side(here + "." + side, step[side])
            fastener = step.get("fastener", {})
            if not isinstance(fastener, dict):
                schema._fail(here, "'fastener' is an object")
            for key, value in fastener.items():
                if key == "create" and not isinstance(value, bool):
                    schema._fail(here, "'fastener.create' is true or false")
                elif key == "head" and value not in ("pan", "round", "flat", "hex", "hex_washer"):
                    schema._fail(here, "'fastener.head' is pan, flat or hex")
                elif key == "length":
                    schema._check_number(here + ".fastener.length", value)
                elif key not in ("create", "head", "length"):
                    schema._fail(here, "unknown fastener setting %r" % key)
        elif op == "sf_boss_fastener":
            if seen.get(step["boss"]) != "sf_boss":
                schema._fail(here, "'boss' names an earlier sf_boss step")
            if step.get("head", "pan") not in ("pan", "round", "flat", "hex", "hex_washer"):
                schema._fail(here, "'head' is pan, flat or hex")
            if "length" in step:
                schema._check_number(here + ".length", step["length"])
        elif op == "sf_rest":
            _plane(here, step)
            rect = step["rect"]
            if not isinstance(rect, list) or len(rect) != 4:
                schema._fail(here, "'rect' is [x0, y0, x1, y1]")
            for v in rect:
                schema._check_number(here + ".rect", v)
            for key in ("thickness", "draft"):
                if key in step:
                    schema._check_number(here + "." + key, step[key])
            if "flip" in step and not isinstance(step["flip"], bool):
                schema._fail(here, "'flip' is true or false")


_validate_before_plastic = schema.validate


def validate(model):
    _validate_before_plastic(model)
    check_steps(model)
    return model


schema.validate = validate
