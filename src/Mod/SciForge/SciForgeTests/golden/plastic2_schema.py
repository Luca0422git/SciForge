# SPDX-License-Identifier: LGPL-2.1-or-later
"""Golden-model checks for the PLASTIC steps (Snap Fit, Lip and Groove) (pure Python): sf_snap_fit,
sf_snap_fit_edit, sf_lip and sf_lip_edit (sciforge/ai/ops/plastic2_ops.py builds them with
the dialogs' code). Imported at the end of schema.py; it adds its step keys and wraps
schema.validate, as gear_schema does."""

from . import schema

SNAP_CHOICES = {
    "type": ("parallel", "perpendicular", "loop"),
    "selection": ("automatic", "manual"),
    "rotation": ("uniform", "independent", "aligned"),
    "extent": ("to_next", "distance"),
}
SNAP_BOOLS = {"flip", "hook", "groove", "align_inward"}
SNAP_NUMBERS = {
    "angle",
    "extent_distance",
    "length",
    "width",
    "thickness",
    "tip_thickness",
    "catch_depth",
    "catch_length",
    "insertion_angle",
    "retention_angle",
    "draft",
    "fillet",
    "clearance",
    "loop_thickness",
}
LIP_CHOICES = {
    "type": ("lip_and_groove", "lip", "groove"),
    "guide": ("pull", "face"),
}
LIP_BOOLS = {"swap"}
LIP_NUMBERS = {
    "lip_width",
    "lip_height",
    "clearance",
    "clearance_height",
    "groove_width",
    "groove_depth",
    "inner_draft",
    "outer_draft",
    "tip_radius",
    "root_radius",
}

schema.STEP_KEYS["sf_snap_fit"] = (
    {"id", "points"},
    {"plane", "offset", "options", "hook", "other", "comment"},
)
schema.STEP_KEYS["sf_snap_fit_edit"] = ({"target", "set"}, {"comment"})
schema.STEP_KEYS["sf_lip"] = ({"id", "edges"}, {"of", "options", "mate", "comment"})
schema.STEP_KEYS["sf_lip_edit"] = ({"target", "set"}, {"comment"})


def _check_options(here, values, choices, bools, numbers):
    if not isinstance(values, dict):
        schema._fail(here, "options are an object {field: value}")
    for key, value in values.items():
        if key in choices:
            if value not in choices[key]:
                schema._fail(here, "'%s' must be one of %s" % (key, choices[key]))
        elif key in bools:
            if not isinstance(value, bool):
                schema._fail(here, "'%s' is true or false" % key)
        elif key in numbers:
            schema._check_number(here + "." + key, value)
        elif key in ("align_point",):
            if not isinstance(value, list) or len(value) != 3:
                schema._fail(here, "'%s' is [x, y, z]" % key)
            for v in value:
                schema._check_number(here + "." + key, v)
        elif key == "angles":
            if not isinstance(value, list):
                schema._fail(here, "'angles' is a list of numbers")
            for i, a in enumerate(value):
                schema._check_number("%s.angles[%d]" % (here, i), a)
        else:
            schema._fail(here, "unknown option %r" % key)


def check_steps(model):
    where = model.get("id", "<no id>")
    seen = {}
    for i, step in enumerate(model["steps"]):
        here = "%s.steps[%d]" % (where, i)
        op = step["op"]
        if op == "sf_snap_fit":
            if step.get("plane", "XY") not in schema.PLANES:
                schema._fail(here, "'plane' must be XY, XZ or YZ")
            points = step["points"]
            if not isinstance(points, list) or not points:
                schema._fail(here, "'points' is a non-empty list of [x, y]")
            for k, pt in enumerate(points):
                if not isinstance(pt, list) or len(pt) != 2:
                    schema._fail(here, "'points'[%d] must be [x, y]" % k)
                for v in pt:
                    schema._check_number(here + ".points", v)
            if "offset" in step:
                schema._check_number(here + ".offset", step["offset"])
            _check_options(here, step.get("options", {}), SNAP_CHOICES, SNAP_BOOLS, SNAP_NUMBERS)
            for key in ("hook", "other"):
                if key in step and step[key] not in seen:
                    schema._fail(here, "'%s' must name an earlier step" % key)
        elif op == "sf_snap_fit_edit":
            if seen.get(step["target"]) != "sf_snap_fit":
                schema._fail(here, "'target' must name an earlier sf_snap_fit step")
            if not step["set"]:
                schema._fail(here, "'set' is a non-empty object of options")
            _check_options(here, step["set"], SNAP_CHOICES, SNAP_BOOLS, SNAP_NUMBERS)
        elif op == "sf_lip":
            if not isinstance(step["edges"], dict):
                schema._fail(here, "'edges' is a selector")
            _check_options(here, step.get("options", {}), LIP_CHOICES, LIP_BOOLS, LIP_NUMBERS)
            for key in ("of", "mate"):
                if key in step and step[key] not in seen:
                    schema._fail(here, "'%s' must name an earlier step" % key)
        elif op == "sf_lip_edit":
            if seen.get(step["target"]) != "sf_lip":
                schema._fail(here, "'target' must name an earlier sf_lip step")
            if not step["set"]:
                schema._fail(here, "'set' is a non-empty object of options")
            _check_options(here, step["set"], LIP_CHOICES, LIP_BOOLS, LIP_NUMBERS)
        if "id" in step:
            seen[step["id"]] = op


_validate_before_plastic2 = schema.validate


def validate(model):
    _validate_before_plastic2(model)
    check_steps(model)
    return model


schema.validate = validate
