# SPDX-License-Identifier: LGPL-2.1-or-later
"""Golden-model checks for the Modify part 2 steps (pure Python, unit tested): Pattern
Compute Option and Start Point, Draft with Two Side / Symmetric / Parting Line, Shell /
Draft / Scale over several bodies, Scale of a sketch, Move Face, Press Pull Offset Type.
Imported at the end of schema.py; it adds its step keys and wraps schema.validate (the same
way every area adds its checks), so schema.py itself only gains one import line.

Steps (golden/modify2_ops.py builds them with the dialogs' code):

  rectangular_pattern / circular_pattern / path_pattern / fusion_mirror:
      + "compute": "optimized" | "identical" | "adjust"
  path_pattern: + "start_point": 0.0 .. 1.0

  {"op": "sf_draft2", "id": "d1", "faces": <selector> | [{"body": id, "faces": sel}, ...],
   "draft_type": "fixed" | "parting", "plane": "XY" | {"face": sel} (Fixed Plane: the plane;
   Parting Line: the pull direction), "parting": "XY" | {"face": sel} | {"edges": sel} |
   {"sketch": id}, "sides": "one" | "two" | "symmetric", "angle": 5, "angle2": 3,
   "flip": false}
  {"op": "sf_draft2_edit", "target": "d1", "set": {"sides": ..., "angle": ...}}

  {"op": "sf_shell_bodies", "id": "sh", "bodies": [{"body": id, "faces": sel} | {"body": id}],
   "inside": 1, "outside": 1, "direction": "inside" | "outside" | "both",
   "shell_type": "sharp" | "rounded"}
  {"op": "sf_scale_bodies", "id": "sc", "bodies": [id, ...], "factor": 2 | "factors": [x,y,z],
   "point": [x, y, z]}
  {"op": "sf_scale_sketch", "id": "ss", "sketch": id, "factor": 2, "point": [x, y, z]}
  {"op": "sf_scale_sketch_edit", "target": "ss", "factor": 3}

  {"op": "move_face", "id": "mf", "faces": <selector>, "move": [dx, dy, dz],
   "rotate": {"axis": [x, y, z], "angle": deg, "center": [x, y, z]}}
  {"op": "move_face_edit", "target": "mf", "move": [...]}

  {"op": "press_pull_type", "id": "pp", "faces": <selector>, "distance": 5,
   "offset_type": "automatic" | "modify" | "new"}

  (extrude_bodies_ops' "expect_bodies" checks each body's volume)
"""

from . import schema

COMPUTE = ("optimized", "identical", "adjust")
DRAFT_TYPES = ("fixed", "parting")
DRAFT_SIDES = ("one", "two", "symmetric")
OFFSET_TYPES = ("automatic", "modify", "new")

for _op in ("rectangular_pattern", "circular_pattern", "path_pattern", "fusion_mirror"):
    schema.STEP_KEYS[_op][1].update({"compute"})
schema.STEP_KEYS["path_pattern"][1].update({"start_point"})

schema.STEP_KEYS["sf_draft2"] = (
    {"id", "faces", "plane"},
    {"draft_type", "parting", "sides", "angle", "angle2", "flip", "comment"},
)
schema.STEP_KEYS["sf_draft2_edit"] = ({"target", "set"}, {"comment"})
schema.STEP_KEYS["sf_shell_bodies"] = (
    {"id", "bodies"},
    {"inside", "outside", "direction", "shell_type", "comment"},
)
schema.STEP_KEYS["sf_scale_bodies"] = ({"id", "bodies"}, {"factor", "factors", "point", "comment"})
schema.STEP_KEYS["sf_scale_sketch"] = ({"id", "sketch", "factor"}, {"point", "comment"})
schema.STEP_KEYS["sf_scale_sketch_edit"] = ({"target", "factor"}, {"comment"})
schema.STEP_KEYS["move_face"] = ({"id", "faces"}, {"move", "rotate", "comment"})
schema.STEP_KEYS["move_face_edit"] = ({"target"}, {"move", "rotate", "comment"})
schema.STEP_KEYS["press_pull_type"] = (
    {"id", "faces", "distance"},
    {"offset_type", "comment"},
)


def _check_vector(here, value, size=3):
    if not isinstance(value, list) or len(value) != size:
        schema._fail(here, "expected a list of %d numbers" % size)
    for item in value:
        schema._check_number(here, item)


def check_steps(model):
    where = model.get("id", "<no id>")
    seen = {}
    for i, step in enumerate(model["steps"]):
        here = "%s.steps[%d]" % (where, i)
        op = step["op"]
        if "compute" in step and step["compute"] not in COMPUTE:
            schema._fail(here, "'compute' must be one of %s" % (COMPUTE,))
        if op == "path_pattern" and "start_point" in step:
            schema._check_number(here + ".start_point", step["start_point"])
            if not 0.0 <= float(step["start_point"]) <= 1.0:
                schema._fail(here, "'start_point' is a share of the path: 0 to 1")
        if op in ("sf_draft2", "sf_draft2_edit"):
            spec = step if op == "sf_draft2" else step["set"]
            if spec.get("draft_type", "fixed") not in DRAFT_TYPES:
                schema._fail(here, "'draft_type' must be fixed or parting")
            if spec.get("sides", "one") not in DRAFT_SIDES:
                schema._fail(here, "'sides' must be one, two or symmetric")
            for key in ("angle", "angle2"):
                if key in spec:
                    schema._check_number(here + "." + key, spec[key])
            if op == "sf_draft2" and spec.get("draft_type") == "parting" and "parting" not in spec:
                schema._fail(here, "a Parting Line draft needs 'parting'")
        if op == "sf_draft2_edit" and seen.get(step["target"]) != "sf_draft2":
            schema._fail(here, "'target' must name an earlier sf_draft2 step")
        if op in ("sf_shell_bodies", "sf_scale_bodies"):
            items = step["bodies"]
            if not isinstance(items, list) or not items:
                schema._fail(here, "'bodies' is a non-empty list")
            for item in items:
                name = item.get("body") if isinstance(item, dict) else item
                if name not in seen:
                    schema._fail(here, "'bodies' names unknown step %r" % (name,))
        if op == "sf_scale_bodies":
            if ("factor" in step) == ("factors" in step):
                schema._fail(here, "give exactly one of 'factor' or 'factors'")
        if op in ("sf_scale_sketch", "sf_scale_sketch_edit"):
            schema._check_number(here + ".factor", step["factor"], positive=True)
        if op == "sf_scale_sketch" and seen.get(step["sketch"]) != "sketch":
            schema._fail(here, "'sketch' must name an earlier sketch step")
        if op == "sf_scale_sketch_edit" and seen.get(step["target"]) != "sf_scale_sketch":
            schema._fail(here, "'target' must name an earlier sf_scale_sketch step")
        if op in ("move_face", "move_face_edit"):
            if "move" not in step and "rotate" not in step:
                schema._fail(here, "give 'move' and/or 'rotate'")
            if "move" in step:
                _check_vector(here + ".move", step["move"])
            if "rotate" in step:
                rot = step["rotate"]
                if not isinstance(rot, dict) or "axis" not in rot or "angle" not in rot:
                    schema._fail(here, "'rotate' is {axis, angle, center}")
                _check_vector(here + ".rotate.axis", rot["axis"])
                schema._check_number(here + ".rotate.angle", rot["angle"])
                if "center" in rot:
                    _check_vector(here + ".rotate.center", rot["center"])
        if op == "move_face_edit" and seen.get(step["target"]) != "move_face":
            schema._fail(here, "'target' must name an earlier move_face step")
        if op == "press_pull_type" and step.get("offset_type", "automatic") not in OFFSET_TYPES:
            schema._fail(here, "'offset_type' must be one of %s" % (OFFSET_TYPES,))
        if "id" in step:
            seen[step["id"]] = op


_validate_before_modify2 = schema.validate


def validate(model):
    _validate_before_modify2(model)
    check_steps(model)
    return model


schema.validate = validate
