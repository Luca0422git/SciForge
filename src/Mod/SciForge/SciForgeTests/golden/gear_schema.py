# SPDX-License-Identifier: LGPL-2.1-or-later
"""Golden-model checks for the Gear steps (pure Python, unit tested): sf_gear and
sf_gear_edit (golden/gear_ops.py builds them with the dialog's code). Imported at the end
of schema.py; it adds its step keys and wraps schema.validate, as modify2_schema does."""

from . import schema

GEAR_OPTIONS = {
    "x",
    "y",
    "type",
    "standard",
    "module",
    "diametral_pitch",
    "teeth",
    "pressure_angle",
    "backlash",
    "fillet",
    "thickness",
    "symmetric",
    "hole",
    "rim",
    "rack_size",
    "rack_length",
    "rack_height",
    "operation",
}
CHOICES = {
    "type": ("spur", "internal", "rack"),
    "standard": ("metric", "english"),
    "rack_size": ("teeth", "length"),
    "operation": ("join", "cut", "new_body", "new_component"),
}

schema.STEP_KEYS["sf_gear"] = ({"id"}, {"plane", "expressions", "comment"} | GEAR_OPTIONS)
schema.STEP_KEYS["sf_gear_edit"] = ({"target", "set"}, {"comment"})


def _check_values(here, values):
    for key, value in values.items():
        if key not in GEAR_OPTIONS:
            schema._fail(here, "cannot set %r" % key)
        if key in CHOICES:
            if value not in CHOICES[key]:
                schema._fail(here, "'%s' must be one of %s" % (key, CHOICES[key]))
        elif key == "symmetric":
            if not isinstance(value, bool):
                schema._fail(here, "'symmetric' is true or false")
        else:
            schema._check_number(here + "." + key, value)


def check_steps(model):
    where = model.get("id", "<no id>")
    seen = {}
    for i, step in enumerate(model["steps"]):
        here = "%s.steps[%d]" % (where, i)
        op = step["op"]
        if op == "sf_gear":
            plane = step.get("plane", "XY")
            if isinstance(plane, str):
                if plane not in schema.PLANES:
                    schema._fail(here, "'plane' must be XY, XZ, YZ or {'face': selector}")
            elif not isinstance(plane, dict) or set(plane) != {"face"}:
                schema._fail(here, "'plane' must be XY, XZ, YZ or {'face': selector}")
            _check_values(here, {k: v for k, v in step.items() if k in GEAR_OPTIONS})
            formulas = step.get("expressions", {})
            if not isinstance(formulas, dict) or any(
                k not in GEAR_OPTIONS or not isinstance(v, str) for k, v in formulas.items()
            ):
                schema._fail(here, "'expressions' is {field: formula} for the gear's fields")
        if op == "sf_gear_edit":
            if seen.get(step["target"]) != "sf_gear":
                schema._fail(here, "'target' must name an earlier sf_gear step")
            if not isinstance(step["set"], dict) or not step["set"]:
                schema._fail(here, "'set' is a non-empty object of options")
            _check_values(here, step["set"])
        if "id" in step:
            seen[step["id"]] = op


_validate_before_gear = schema.validate


def validate(model):
    _validate_before_gear(model)
    check_steps(model)
    return model


schema.validate = validate
