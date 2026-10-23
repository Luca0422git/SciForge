# SPDX-License-Identifier: LGPL-2.1-or-later
"""Golden-model checks for the SHEET METAL flat steps (Unfold, Refold, Flat Pattern, Rip, Convert)
(pure Python). Imported at the end of schema.py; it adds its step keys and wraps
schema.validate, as gear_schema does."""

from . import schema

RIP_TYPES = ("face", "edge", "points")

schema.STEP_KEYS["sf_sm_convert"] = ({"id", "face"}, {"rule", "comment"})
schema.STEP_KEYS["sf_flat_pattern"] = ({"id", "face"}, {"measure", "comment"})
schema.STEP_KEYS["sf_unfold"] = ({"id", "face"}, {"bends", "all", "comment"})
schema.STEP_KEYS["sf_refold"] = ({"id"}, {"unfold", "comment"})
schema.STEP_KEYS["sf_rip"] = (
    {"id", "type"},
    {"face", "edge", "point1", "point2", "offset1", "offset2", "gap", "comment"},
)


def check_steps(model):
    where = model.get("id", "<no id>")
    seen = {}
    for i, step in enumerate(model["steps"]):
        here = "%s.steps[%d]" % (where, i)
        op = step["op"]
        if op in ("sf_sm_convert", "sf_flat_pattern", "sf_unfold") and not isinstance(
            step["face"], dict
        ):
            schema._fail(here, "'face' is a face selector")
        if op == "sf_sm_convert" and not isinstance(step.get("rule", "template"), str):
            schema._fail(here, "'rule' is 'template' or 'In This Design|<name>' / 'Library|<name>'")
        if op == "sf_flat_pattern" and not isinstance(step.get("measure", True), bool):
            schema._fail(here, "'measure' is true or false")
        if op == "sf_unfold":
            if not isinstance(step.get("all", False), bool):
                schema._fail(here, "'all' is true or false")
            if "bends" in step and not isinstance(step["bends"], dict):
                schema._fail(here, "'bends' is a face selector")
            if not step.get("all") and "bends" not in step:
                schema._fail(here, "an unfold needs 'bends' or 'all': true")
        if op == "sf_refold" and "unfold" in step and seen.get(step["unfold"]) != "sf_unfold":
            schema._fail(here, "'unfold' must name an earlier sf_unfold step")
        if op == "sf_rip":
            kind = step["type"]
            if kind not in RIP_TYPES:
                schema._fail(here, "'type' must be one of %s" % (RIP_TYPES,))
            need = {"face": ("face",), "edge": ("edge",), "points": ("point1", "point2")}[kind]
            for key in need:
                if not isinstance(step.get(key), dict):
                    schema._fail(here, "a %s rip needs '%s' (a selector)" % (kind, key))
            for key in ("gap", "offset1", "offset2"):
                if key in step:
                    schema._check_number(here + "." + key, step[key])
        if "id" in step:
            seen[step["id"]] = op


_validate_before_flat = schema.validate


def validate(model):
    _validate_before_flat(model)
    check_steps(model)
    return model


schema.validate = validate
