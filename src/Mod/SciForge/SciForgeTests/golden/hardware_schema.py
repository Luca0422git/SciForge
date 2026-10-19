# SPDX-License-Identifier: LGPL-2.1-or-later
"""Golden-model checks for the hardware steps (pure Python, unit tested): sf_hardware and
sf_hardware_edit (sciforge/ai/ops/hardware_ops.py builds them with the dialog's code).
Imported at the end of schema.py; it adds its step keys and wraps schema.validate, as
gear_schema does."""

from . import schema

OPTIONS = {
    "standard",
    "size",
    "length",
    "flip",
    "make_hole",
    "fit",
    "sink_head",
    "hole_depth",
    "clearance",
}
CHOICES = {
    "standard": ("iso4762", "iso7380", "iso10642", "iso4032", "iso7089", "insert", "magnet"),
    "fit": ("close", "normal", "loose"),
    "hole_depth": ("all", "length"),
}
FLAGS = ("flip", "make_hole", "sink_head")

schema.STEP_KEYS["sf_hardware"] = (
    {"id"},
    {"face", "at", "edge", "hardware_bbox", "comment"} | OPTIONS,
)
schema.STEP_KEYS["sf_hardware_edit"] = ({"target", "set"}, {"hardware_bbox", "comment"})


def _check_values(here, values):
    for key, value in values.items():
        if key not in OPTIONS:
            schema._fail(here, "cannot set %r" % key)
        if key in CHOICES:
            if value not in CHOICES[key]:
                schema._fail(here, "'%s' must be one of %s" % (key, CHOICES[key]))
        elif key in FLAGS:
            if not isinstance(value, bool):
                schema._fail(here, "'%s' is true or false" % key)
        elif key == "size":
            if not isinstance(value, str):
                schema._fail(here, '\'size\' is a text: "3", "2.5", "6x3"')
        else:
            schema._check_number(here + "." + key, value)


def _check_bbox(here, step):
    box = step.get("hardware_bbox")
    if box is None:
        return
    if not isinstance(box, list) or len(box) != 6:
        schema._fail(here, "'hardware_bbox' is [xmin, ymin, zmin, xmax, ymax, zmax]")
    for i, v in enumerate(box):
        schema._check_number("%s.hardware_bbox[%d]" % (here, i), v)


def check_steps(model):
    where = model.get("id", "<no id>")
    seen = {}
    for i, step in enumerate(model["steps"]):
        here = "%s.steps[%d]" % (where, i)
        op = step["op"]
        if op == "sf_hardware":
            if ("face" in step) == ("edge" in step):
                schema._fail(here, "give either 'face' (with 'at') or 'edge'")
            if "face" in step:
                at = step.get("at")
                if not isinstance(at, list) or len(at) != 3:
                    schema._fail(here, "'at' is [x, y, z]: where the face is clicked")
            _check_values(here, {k: v for k, v in step.items() if k in OPTIONS})
            _check_bbox(here, step)
        if op == "sf_hardware_edit":
            if seen.get(step["target"]) != "sf_hardware":
                schema._fail(here, "'target' must name an earlier sf_hardware step")
            if not isinstance(step["set"], dict) or not step["set"]:
                schema._fail(here, "'set' is a non-empty object of options")
            _check_values(here, step["set"])
            _check_bbox(here, step)
        if "id" in step:
            seen[step["id"]] = op


_validate_before_hardware = schema.validate


def validate(model):
    _validate_before_hardware(model)
    check_steps(model)
    return model


schema.validate = validate
