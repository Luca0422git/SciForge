# SPDX-License-Identifier: LGPL-2.1-or-later
"""AI tools for SOLID > MODIFY beyond fillet, chamfer and shell: Press Pull, Fillet with
selection sets, Rule and Full Round Fillet, Draft, Scale, Combine, Split Body, Split Face,
Silhouette Split, Replace Face, Delete (faces, bodies), Remove, Move/Copy, Align, Physical
Material, Appearance and Capture Design History. Pure Python."""

import copy

from . import kit
from .kit import (
    BODY_PICK_HELP,
    UNITS,
    angle,
    array,
    boolean,
    either,
    enum,
    integer,
    length,
    number,
    obj,
    positive,
    schema,
    step_id,
    step_ids,
    string,
)
from .registry import define, example

TOP_FACE = {"normal": [0, 0, 1], "count": 1}


# -- Press Pull ---------------------------------------------------------------------------------
def _extra_press_pull(args, problems):
    mode = kit.exactly_one(
        args, ("faces", "edges", "fillet_face"), problems, "what is pressed or pulled"
    )
    if mode:
        kit.check_selector(args[mode], mode, "edges" if mode == "edges" else "faces", problems)
    if "offset_type" in args and mode != "faces":
        problems.append("offset_type only applies to faces")


def _steps_press_pull(a, sid):
    if "faces" in a and "offset_type" in a:
        return [
            {
                "op": "press_pull_type",
                "id": sid,
                "faces": copy.deepcopy(a["faces"]),
                "distance": a["distance"],
                "offset_type": a["offset_type"],
            }
        ]
    step = {"op": "press_pull", "id": sid, "distance": a["distance"]}
    for key in ("faces", "edges", "fillet_face"):
        if key in a:
            step[key] = copy.deepcopy(a[key])
    return [step]


define(
    "press_pull",
    "Press pull",
    "modify",
    "SOLID > MODIFY > Press Pull (Q)",
    "Fusion's Press Pull: push or pull faces by a distance (mm, negative pushes in), or give "
    "edges (they get a fillet of that radius), or fillet_face (a face a fillet made: that "
    "fillet's radius becomes distance). offset_type (faces): automatic (default), new (a new "
    "Press Pull step), modify (change the extrude that made the faces, no new step).",
    schema(
        {
            "faces": kit.selector("the faces to move"),
            "edges": kit.selector("edges to round", "edges"),
            "fillet_face": kit.selector("a face of a fillet"),
            "distance": number("mm (a radius for edges / fillet faces)"),
            "offset_type": enum(["automatic", "new", "modify"], default="automatic"),
        },
        ["distance"],
    ),
    ops=["press_pull", "press_pull_type"],
    steps=_steps_press_pull,
    extra=_extra_press_pull,
    needs=("solid",),
    id_base="PressPull",
    title_fn=lambda a: (
        "AI: Press Pull %s mm" % kit.fmt(a["distance"])
        if kit.is_type(a.get("distance"), "number")
        else "AI: Press Pull"
    ),
    examples=[example({"faces": TOP_FACE, "distance": 5}, "pull the top face up 5 mm")],
)


# -- Fillet sets, Rule, Full Round --------------------------------------------------------------
def _extra_fillet_sets(args, problems):
    kind = args.get("kind", "fillet")
    for i, row in enumerate(args.get("sets") or []):
        where = "sets[%d]" % i
        if not isinstance(row, dict):
            continue
        if not ({"edges", "faces", "features"} & set(row)):
            problems.append("%s: pick with edges, faces or features" % where)
        if "edges" in row:
            kit.check_selector(row["edges"], where + ".edges", "edges", problems)
        if "faces" in row:
            kit.check_selector(row["faces"], where + ".faces", "faces", problems)
        if kind == "fillet":
            rtype = row.get("radius_type", "constant")
            if rtype == "chord" and "chord" not in row:
                problems.append("%s: radius_type chord needs chord" % where)
            if rtype == "variable" and not ({"start", "end", "points"} & set(row)):
                problems.append("%s: radius_type variable needs start / end (and points)" % where)
            if rtype == "constant" and "radius" not in row:
                problems.append("%s: radius is missing" % where)
            for key in ("chamfer_type", "distance", "distance2", "angle", "flip"):
                if key in row:
                    problems.append("%s.%s is a chamfer field (kind chamfer)" % (where, key))
        else:
            if "distance" not in row:
                problems.append("%s: distance is missing" % where)
            for key in ("radius", "radius_type", "chord", "start", "end", "points"):
                if key in row:
                    problems.append("%s.%s is a fillet field (kind fillet)" % (where, key))


_SET_ROW = obj(
    {
        "edges": kit.selector("edges of this set", "edges"),
        "faces": kit.selector("every sharp edge around these faces"),
        "features": step_ids("the edges these steps made"),
        "tangent_chain": boolean("this set's Tangent Chain"),
        "radius": positive("constant radius (mm)"),
        "radius_type": enum(["constant", "chord", "variable"], default="constant"),
        "chord": positive("chord length (mm)"),
        "start": positive("variable: radius at the start (mm)"),
        "end": positive("variable: radius at the end (mm)"),
        "points": array(kit.numbers(2), "variable: [[position 0..1, radius], ...]"),
        "chamfer_type": enum(["equal", "two", "angle"], default="equal"),
        "distance": positive("mm"),
        "distance2": positive("mm"),
        "angle": number("degrees", above=0, maximum=89),
        "flip": boolean(),
    },
    description="one selection set (a row of the dialog)",
)
define(
    "fillet_sets",
    "Fillet / chamfer with sets",
    "modify",
    "SOLID > MODIFY > Fillet / Chamfer (several selection sets, Chord Length, Variable)",
    'Fusion\'s Fillet or Chamfer dialog with several selection sets in one step (the "+" '
    "rows): each set picks edges / faces / features and has its own size. Fillet rows: "
    "radius, radius_type constant | chord (chord) | variable (start, end, points [[position "
    "0..1, radius]]), tangent_chain. Chamfer rows (kind chamfer): chamfer_type equal | two | "
    "angle, distance, distance2, angle, flip. tangent_chain (the step's, default true). " + UNITS,
    schema(
        {
            "kind": enum(["fillet", "chamfer"], default="fillet"),
            "sets": array(_SET_ROW, "the selection sets", 1),
            "tangent_chain": boolean(default=True),
        },
        ["sets"],
    ),
    op="fillet_sets",
    extra=_extra_fillet_sets,
    needs=("solid",),
    id_base="Fillet",
    title_fn=lambda a: "AI: %s (%d sets)"
    % (str(a.get("kind", "fillet")).capitalize(), len(a.get("sets") or [])),
    examples=[
        example(
            {
                "sets": [
                    {
                        "edges": {"type": "line", "at": {"axis": "z", "value": "max"}, "count": 4},
                        "radius": 3,
                    },
                    {"edges": {"type": "line", "parallel": [0, 0, 1], "count": 4}, "radius": 1},
                ]
            },
            "3 mm on the top edges and 1 mm on the vertical edges, one step",
        )
    ],
)


def _extra_rule(args, problems):
    if not ({"faces", "features"} & set(args)):
        problems.append("give faces and / or features (what the rule looks at)")
    if args.get("rule") == "between" and not ({"faces2", "features2"} & set(args)):
        problems.append("rule between needs faces2 / features2 (the second group)")
    for key in ("faces", "faces2"):
        if key in args:
            kit.check_selector(args[key], key, "faces", problems)


define(
    "rule_fillet",
    "Rule fillet",
    "modify",
    "SOLID > MODIFY > Fillet (Type: Rule Fillet)",
    "Fusion's Rule Fillet: round every edge a rule finds, found again whenever the part "
    "changes. rule all (every edge of faces / features) or between (the edges between the "
    "first group and faces2 / features2); rounds (concave edges) and fillets (convex) on or "
    "off; radius (mm).",
    schema(
        {
            "radius": positive("mm"),
            "rule": enum(["all", "between"], default="all"),
            "faces": kit.selector("the faces (first group)"),
            "features": step_ids("steps whose faces form the first group"),
            "faces2": kit.selector("the second group, rule between"),
            "features2": step_ids("steps for the second group"),
            "rounds": boolean(default=True),
            "fillets": boolean(default=True),
        },
        ["radius"],
    ),
    op="rule_fillet",
    extra=_extra_rule,
    needs=("solid",),
    id_base="Fillet",
    title_fn=lambda a: "AI: Rule fillet",
    examples=[
        example(
            {"radius": 1, "rule": "all", "features": ["Extrude2"]},
            "round every edge the boss Extrude2 made",
        )
    ],
)


def _extra_full_round(args, problems):
    for i, sel in enumerate(args.get("faces") or []):
        kit.check_selector(sel, "faces[%d]" % i, "faces", problems)


define(
    "full_round_fillet",
    "Full round fillet",
    "modify",
    "SOLID > MODIFY > Fillet (Type: Full Round Fillet)",
    "Fusion's Full Round Fillet: each selector picks one centre face (a rib's top, say); it "
    "is replaced by a round that touches both side faces.",
    schema(
        {"faces": array(kit.selector("one centre face"), "one selector per round", 1)}, ["faces"]
    ),
    op="full_round",
    extra=_extra_full_round,
    needs=("solid",),
    id_base="Fillet",
    title_fn=lambda a: "AI: Full round fillet",
    examples=[example({"faces": [TOP_FACE]}, "round off the top of a thin wall")],
)


# -- Draft --------------------------------------------------------------------------------------
_DRAFT2 = ("draft_type", "parting", "sides", "angle2")


def _extra_draft(args, problems):
    faces = args.get("faces")
    if isinstance(faces, list):
        for i, item in enumerate(faces):
            if not isinstance(item, dict) or set(item) != {"body", "faces"}:
                problems.append('faces[%d] must be {"body": step id, "faces": selector}' % i)
            else:
                kit.check_selector(item["faces"], "faces[%d].faces" % i, "faces", problems)
    elif isinstance(faces, dict):
        kit.check_selector(faces, "faces", "faces", problems)
    else:
        problems.append("faces must be a face selector or a list of {body, faces}")
    kit.check_plane_or_face(args.get("plane"), "plane", problems)
    if args.get("draft_type") == "parting" and "parting" not in args:
        problems.append("draft_type parting needs parting (the parting line)")
    if "angle2" in args and args.get("sides") != "two":
        problems.append("angle2 is only used with sides two")


def _steps_draft(a, sid):
    new = any(k in a for k in _DRAFT2) or isinstance(a.get("faces"), list)
    step = {"op": "sf_draft2" if new else "sf_draft", "id": sid}
    step.update(copy.deepcopy(a))
    return [step]


define(
    "draft",
    "Draft",
    "modify",
    "SOLID > MODIFY > Draft",
    "Fusion's Draft: tilt faces by an angle for a mould. plane: the fixed plane (XY | XZ | YZ "
    'or {"face": selector}: a flat face, its outward side the pull direction); faces: the '
    "faces to tilt (or [{body, faces}, ...] for several bodies in one step); angle (degrees, "
    "positive narrows the part toward the pull direction); flip. draft_type fixed (default) | "
    'parting (with parting: XY / {"face": sel} / {"edges": sel} / {"sketch": id}, the '
    "parting line); sides one | two (with angle2) | symmetric.",
    schema(
        {
            "plane": either('XY, XZ, YZ or {"face": selector}'),
            "faces": {
                "type": ["object", "array"],
                "description": "a face selector, or [{body, faces}] for several bodies",
            },
            "angle": angle(default=1),
            "flip": boolean(default=False),
            "draft_type": enum(["fixed", "parting"], default="fixed"),
            "parting": either("parting line: a plane name, face, edges or sketch"),
            "sides": enum(["one", "two", "symmetric"], default="one"),
            "angle2": angle("side two"),
        },
        ["plane", "faces"],
    ),
    ops=["sf_draft", "sf_draft2"],
    steps=_steps_draft,
    extra=_extra_draft,
    needs=("solid",),
    id_base="Draft",
    title_fn=lambda a: (
        "AI: Draft %s degrees" % kit.fmt(a.get("angle", 1))
        if kit.is_type(a.get("angle", 1), "number")
        else "AI: Draft"
    ),
    examples=[
        example(
            {"plane": "XY", "faces": {"along": [0, 0, 1], "count": 4}, "angle": 3},
            "3 degrees on the four side walls, pulled up from XY",
        )
    ],
)


# -- Scale --------------------------------------------------------------------------------------
def _extra_scale(args, problems):
    if "sketch" in args:
        if "factors" in args or "bodies" in args:
            problems.append("a sketch scales uniformly: give factor, without bodies")
        if "factor" not in args:
            problems.append("factor is missing")
    elif ("factor" in args) == ("factors" in args):
        problems.append("give factor (uniform) or factors [x, y, z], one of them")
    point = args.get("point")
    if isinstance(point, str) and point != "origin":
        problems.append('point must be "origin" or [x, y, z]')


def _steps_scale(a, sid):
    if "sketch" in a:
        step = {"op": "sf_scale_sketch", "id": sid, "sketch": a["sketch"], "factor": a["factor"]}
        if isinstance(a.get("point"), list):
            step["point"] = list(a["point"])
        return [step]
    step = {"op": "sf_scale_bodies" if "bodies" in a else "sf_scale", "id": sid}
    step.update(copy.deepcopy(a))
    if "bodies" in a and step.get("point") == "origin":
        step.pop("point")
    return [step]


define(
    "scale",
    "Scale",
    "modify",
    "SOLID > MODIFY > Scale",
    "Fusion's Scale: make the current body (or bodies: several step ids, one step; or a "
    "sketch: its curves and dimensions) bigger or smaller. factor (uniform) or factors "
    '[x, y, z] (non-uniform, bodies only); point: "origin" (default) or [x, y, z], a corner '
    "of the part to scale about.",
    schema(
        {
            "factor": positive("uniform scale factor"),
            "factors": array(positive(), "[x, y, z] factors", 3, 3),
            "point": {
                "type": ["string", "array"],
                "items": {"type": "number"},
                "description": '"origin" or [x, y, z] (a corner of the part)',
            },
            "bodies": step_ids("several bodies, by a step of each"),
            "sketch": step_id("scale this sketch instead"),
        },
    ),
    ops=["sf_scale", "sf_scale_bodies", "sf_scale_sketch"],
    steps=_steps_scale,
    extra=_extra_scale,
    needs=("solid",),
    id_base="Scale",
    title_fn=lambda a: "AI: Scale",
    examples=[
        example({"factor": 2}, "twice as big about the origin"),
        example({"factors": [1, 1, 0.5]}, "half as tall"),
    ],
)


# -- body tools ---------------------------------------------------------------------------------
define(
    "combine",
    "Combine",
    "modify",
    "SOLID > MODIFY > Combine",
    "Fusion's Combine: join, cut or intersect bodies. target: the body kept (a step id of "
    "it); tools: the bodies used (step ids). keep_tools keeps them; new_body / new_component "
    "puts the result in a new body / component.",
    schema(
        {
            "target": step_id("the target body (a step in it)"),
            "tools": step_ids("the tool bodies"),
            "operation": enum(["join", "cut", "intersect"], default="join"),
            "new_body": boolean(default=False),
            "new_component": boolean(default=False),
            "keep_tools": boolean(default=False),
        },
        ["target", "tools"],
    ),
    op="combine",
    id_base="Combine",
    title_fn=lambda a: "AI: Combine (%s)" % a.get("operation", "join"),
    examples=[
        example(
            {"target": "Extrude1", "tools": ["Extrude2"], "operation": "cut"},
            "cut Extrude2's body out of Extrude1's",
        )
    ],
)


def _check_split_tool(spec, path, problems):
    if isinstance(spec, str):
        if spec not in kit.PLANES:
            problems.append("%s must be XY, XZ, YZ or a tool object" % path)
        return
    if not isinstance(spec, dict) or len({"face", "body", "sketch"} & set(spec)) != 1:
        problems.append(
            '%s must be a plane name, {"face": selector, "of": id}, {"body": id} '
            'or {"sketch": id, "edge": n}' % path
        )
        return
    if "face" in spec:
        kit.check_selector(spec["face"], path + ".face", "faces", problems)


def _extra_split_body(args, problems):
    if ("tool" in args) == ("tools" in args):
        problems.append("give tool or tools, one of them")
    if "tool" in args:
        _check_split_tool(args["tool"], "tool", problems)
    for i, spec in enumerate(args.get("tools") or []):
        _check_split_tool(spec, "tools[%d]" % i, problems)


define(
    "split_body",
    "Split body",
    "modify",
    "SOLID > MODIFY > Split Body",
    "Fusion's Split Body: cut a body into pieces (new bodies). body: the body (a step id); "
    'tool: XY | XZ | YZ, {"face": selector, "of": step id} (a face, of another body with of), '
    '{"body": step id} or {"sketch": id, "edge": n} (a sketch curve, cut straight through); '
    "tools: several at once. extend (default true): the splitting face is extended.",
    schema(
        {
            "body": step_id("the body to split"),
            "tool": either("the splitting tool"),
            "tools": array(either("a splitting tool"), "several splitting tools", 1),
            "extend": boolean(default=True),
        },
        ["body"],
    ),
    op="split_body",
    extra=_extra_split_body,
    needs=("solid",),
    id_base="SplitBody",
    title_fn=lambda a: "AI: Split body",
    examples=[example({"body": "Extrude1", "tool": "YZ"}, "split the body in two at YZ")],
)


def _extra_split_face(args, problems):
    kit.check_selector(args.get("faces"), "faces", "faces", problems)
    kit.check_body_pick(args.get("tool"), "tool", problems)
    if "direction" in args:
        kit.check_body_pick(args["direction"], "direction", problems)
    if args.get("split_type") == "vector" and "direction" not in args:
        problems.append("split_type vector needs direction")


define(
    "split_face",
    "Split face",
    "modify",
    "SOLID > MODIFY > Split Face",
    "Fusion's Split Face: split faces of a body with a tool, so they can be drafted or "
    "coloured on their own. faces (selector, of: the body's step), tool: a body pick, extend, "
    "split_type surface | vector (along direction) | closest. " + BODY_PICK_HELP,
    schema(
        {
            "faces": kit.selector("the faces to split"),
            "of": step_id("the body the faces are on (default: the current one)"),
            "tool": either("the splitting tool (a body pick)"),
            "extend": boolean(default=False),
            "split_type": enum(["surface", "vector", "closest"], default="surface"),
            "direction": either("split_type vector: the direction (a body pick)"),
        },
        ["faces", "tool"],
    ),
    op="split_face",
    extra=_extra_split_face,
    needs=("solid",),
    id_base="SplitFace",
    title_fn=lambda a: "AI: Split face",
    examples=[
        example(
            {"faces": {"along": [0, 0, 1], "count": 4}, "tool": "XY"},
            "split the side walls at the XY plane",
        )
    ],
)


def _extra_silhouette(args, problems):
    kit.check_body_pick(args.get("direction"), "direction", problems)


define(
    "silhouette_split",
    "Silhouette split",
    "modify",
    "SOLID > MODIFY > Silhouette Split",
    "Fusion's Silhouette Split: split a body along its outline seen from a direction. body "
    "(step id), direction (a body pick: a plane, face, edge or axis), operation faces (split "
    "the faces) | body (two bodies) | shelled (for a shelled part).",
    schema(
        {
            "body": step_id("the body"),
            "direction": either("the view direction (a body pick)"),
            "operation": enum(["faces", "body", "shelled"], default="faces"),
        },
        ["body", "direction"],
    ),
    op="silhouette_split",
    extra=_extra_silhouette,
    needs=("solid",),
    id_base="SilhouetteSplit",
    title_fn=lambda a: "AI: Silhouette split",
    examples=[
        example(
            {"body": "Revolve1", "direction": "Z", "operation": "body"},
            "split a round part into two halves seen from Z",
        )
    ],
)


def _extra_replace(args, problems):
    kit.check_selector(args.get("faces"), "faces", "faces", problems)
    kit.check_body_pick(args.get("target"), "target", problems)


define(
    "replace_face",
    "Replace face",
    "modify",
    "SOLID > MODIFY > Replace Face",
    "Fusion's Replace Face: move faces of a body onto a target (a plane or a face): faces "
    "(selector, of: the body's step), tangent_chain, target (a body pick: XY / XZ / YZ or "
    '{"face": selector, "of": id}).',
    schema(
        {
            "faces": kit.selector("the faces to replace"),
            "of": step_id("the body they are on"),
            "tangent_chain": boolean(default=True),
            "target": either("the new face (a body pick)"),
        },
        ["faces", "target"],
    ),
    op="replace_face",
    extra=_extra_replace,
    needs=("solid",),
    id_base="ReplaceFace",
    title_fn=lambda a: "AI: Replace face",
    examples=[
        example(
            {
                "faces": TOP_FACE,
                "target": {"face": {"normal": [0, 0, 1], "count": 1}, "of": "Extrude2"},
            },
            "move the top face up to another body's top",
        )
    ],
)
define(
    "delete_face",
    "Delete face",
    "modify",
    "SOLID > MODIFY > Delete (faces)",
    "Delete faces of the current body (Fusion: select faces, Delete): the gap heals, as "
    "when a fillet or a hole is removed.",
    schema({"faces": kit.selector("the faces to delete")}, ["faces"]),
    op="delete_face",
    selectors={"faces": "faces"},
    needs=("solid",),
    destructive=True,
    id_base="DeleteFace",
    title_fn=lambda a: "AI: Delete face",
    examples=[
        example(
            {"faces": {"type": "cylinder", "radius": 3, "count": 1}},
            "remove a 6 mm hole's wall: the hole is gone",
        )
    ],
)
define(
    "remove_bodies",
    "Remove",
    "modify",
    "SOLID > MODIFY > Remove",
    "Fusion's Remove: take bodies out of the design from this point of the timeline on (a "
    "timeline step: rolling back before it brings them back). bodies: step ids.",
    schema({"bodies": step_ids("the bodies to remove")}, ["bodies"]),
    steps=lambda a, sid: [{"op": "remove_bodies", "steps": list(a["bodies"])}],
    ops=["remove_bodies"],
    destructive=True,
    title_fn=lambda a: "AI: Remove",
    examples=[example({"bodies": ["Extrude3"]}, "remove the tool body after a combine")],
)
define(
    "delete_bodies",
    "Delete bodies",
    "modify",
    "BROWSER > a body > Delete",
    "Delete bodies (picked in the browser, then Delete): they are gone from the whole "
    "history; what used them keeps working where it can. bodies: step ids.",
    schema({"bodies": step_ids("the bodies to delete")}, ["bodies"]),
    steps=lambda a, sid: [{"op": "delete_bodies", "steps": list(a["bodies"])}],
    ops=["delete_bodies"],
    destructive=True,
    title_fn=lambda a: "AI: Delete bodies",
    examples=[example({"bodies": ["Extrude3"]}, "delete Extrude3's body")],
)


# -- Move/Copy ----------------------------------------------------------------------------------
def _extra_move(args, problems):
    what = kit.exactly_one(args, ("bodies", "faces", "components"), problems, "what is moved")
    move_type = args.get("move_type", "translate" if what == "faces" else "free")
    if what == "faces":
        if move_type not in ("translate", "rotate"):
            problems.append("faces move by translate or rotate only")
        kit.check_selector(args["faces"], "faces", "faces", problems)
        for key in ("copy", "capture", "from_point", "to_point", "px", "py", "pz"):
            if key in args:
                problems.append("%s does not apply to faces" % key)
    if what == "components":
        for key in ("copy", "from_point", "to_point", "px", "py", "pz"):
            if key in args:
                problems.append("%s does not apply to components" % key)
    elif "capture" in args:
        problems.append("capture only applies to components")
    if move_type == "rotate" and "angle" not in args:
        problems.append("rotate needs angle (and axis, an origin axis)")
    if move_type in ("point_to_point",) and not ("from_point" in args and "to_point" in args):
        problems.append("point_to_point needs from_point and to_point")
    if move_type == "point_to_position" and "from_point" not in args:
        problems.append("point_to_position needs from_point (and px, py, pz)")


def _steps_move(a, sid):
    if "faces" in a:
        step = {"op": "move_face", "id": sid, "faces": copy.deepcopy(a["faces"])}
        if a.get("move_type", "translate") == "rotate":
            axis = {"X": [1, 0, 0], "Y": [0, 1, 0], "Z": [0, 0, 1]}[a.get("axis", "Z")]
            step["rotate"] = {
                "axis": axis,
                "angle": a["angle"],
                "center": list(a.get("pivot", [0, 0, 0])),
            }
        else:
            step["move"] = [a.get("dx", 0), a.get("dy", 0), a.get("dz", 0)]
        return [step]
    if "components" in a:
        step = {"op": "component_move", "id": sid}
        step.update(copy.deepcopy(a))
        return [step]
    step = {"op": "move_bodies", "id": sid}
    step.update(copy.deepcopy(a))
    return [step]


define(
    "move_copy",
    "Move / copy",
    "modify",
    "SOLID > MODIFY > Move/Copy (M)",
    "Fusion's Move/Copy. What moves: bodies (step ids), faces (a selector: the faces move, "
    "the body follows) or components (component ids). move_type free (dx dy dz and rotations "
    "rx ry rz about pivot), translate (dx, dy, dz), rotate (angle about axis X / Y / Z through "
    "pivot), point_to_point (from_point to to_point), point_to_position (from_point goes to "
    "px, py, pz). copy: move a copy (bodies). capture (components): record the move as a "
    "timeline step (Capture Position). " + UNITS,
    schema(
        {
            "bodies": step_ids("the bodies"),
            "faces": kit.selector("the faces"),
            "components": step_ids("the components"),
            "move_type": enum(
                ["free", "translate", "rotate", "point_to_point", "point_to_position"]
            ),
            "dx": length(default=0),
            "dy": length(default=0),
            "dz": length(default=0),
            "rx": angle(default=0),
            "ry": angle(default=0),
            "rz": angle(default=0),
            "angle": angle("rotate"),
            "axis": enum(kit.AXES, "rotate: an origin axis"),
            "pivot": kit.point3("the point rotations turn about"),
            "from_point": kit.point3(),
            "to_point": kit.point3(),
            "px": length(),
            "py": length(),
            "pz": length(),
            "copy": boolean(default=False),
            "capture": boolean("components: a Move step in the timeline", default=False),
        },
    ),
    ops=["move_bodies", "move_face", "component_move"],
    steps=_steps_move,
    extra=_extra_move,
    id_base="Move",
    title_fn=lambda a: "AI: Move" + (" copy" if a.get("copy") else ""),
    examples=[
        example(
            {"bodies": ["Extrude2"], "move_type": "translate", "dx": 30},
            "move a body 30 mm along X",
        ),
        example({"faces": {"normal": [1, 0, 0], "count": 1}, "dx": 5}, "push the +X face out 5 mm"),
    ],
)


def _extra_align(args, problems):
    kit.check_body_pick(args.get("from"), "from", problems)
    kit.check_body_pick(args.get("to"), "to", problems)


define(
    "align",
    "Align",
    "modify",
    "SOLID > MODIFY > Align",
    "Fusion's Align (Objects: Bodies): move a body so that from (a face, edge or corner of "
    "it) lands on to (another face, edge, corner, plane or axis). flip turns it over; turns "
    "(0..3) quarter-turns about the aligned axis. " + BODY_PICK_HELP,
    schema(
        {
            "from": either("on the body that moves (a body pick)"),
            "to": either("where it goes (a body pick)"),
            "flip": boolean(default=False),
            "turns": integer(minimum=0, maximum=3, default=0),
        },
        ["from", "to"],
    ),
    op="align_bodies",
    extra=_extra_align,
    needs=("solid",),
    id_base="Align",
    title_fn=lambda a: "AI: Align",
    examples=[
        example(
            {
                "from": {"face": {"normal": [0, 0, -1], "count": 1}, "of": "Extrude2"},
                "to": {"face": {"normal": [0, 0, 1], "count": 1}, "of": "Extrude1"},
            },
            "stand one body on the other's top face",
        )
    ],
)

# -- looks and material -------------------------------------------------------------------------
MATERIALS = (
    "steel",
    "stainless",
    "iron",
    "aluminium",
    "aluminium_6061",
    "copper",
    "titanium",
    "abs",
    "pla",
    "pet",
    "nylon",
    "polycarbonate",
    "acetal",
    "acrylic",
    "polypropylene",
    "ptfe",
    "peek",
    "wood",
    "glass",
)
define(
    "physical_material",
    "Physical material",
    "modify",
    "SOLID > MODIFY > Physical Material",
    "Give a body its physical material (Fusion's Physical Material): density for mass and "
    "the material's look. body: a step of it (default: the current body). material: one of "
    "SciForge's library (list_materials lists them with densities), or a user material "
    "(user:<name>).",
    schema(
        {
            "body": step_id("a step of the body"),
            "material": string("library key, e.g. aluminium, abs, steel"),
        },
        ["material"],
    ),
    ops=["body_material"],
    own_id=False,
    title_fn=lambda a: "AI: Physical material %s" % a.get("material", ""),
    examples=[
        example({"body": "Extrude1", "material": "aluminium_6061"}, "make the part aluminium 6061")
    ],
)
define(
    "list_materials",
    "List materials",
    "modify",
    "SOLID > MODIFY > Physical Material / Appearance (libraries)",
    "List SciForge's physical materials (key, name, density kg/m3, group) and appearances "
    "(key, name, colour), for physical_material and appearance.",
    schema({}),
    changes=False,
    needs=(),
    examples=[example({}, "the material and appearance libraries")],
)


def _extra_appearance(args, problems):
    if ("look" in args) == ("color" in args):
        problems.append("give look (a library key) or color ([r, g, b] 0..1), one of them")
    if "faces" in args:
        kit.check_selector(args["faces"], "faces", "faces", problems)


define(
    "appearance",
    "Appearance",
    "modify",
    "SOLID > MODIFY > Appearance (A)",
    "Fusion's Appearance: colour a body, or some faces of it, without changing its material. "
    "body: a step of it (default: the current body); faces: a selector (only these faces); "
    "look: a library key (list_materials) or color [r, g, b] (0..1) with shininess (0..1) and "
    "transparency (0..1). clear: true removes the body's own appearance.",
    schema(
        {
            "body": step_id("a step of the body"),
            "faces": kit.selector("only these faces"),
            "look": string("an appearance key, e.g. plastic_red"),
            "color": array(number(minimum=0, maximum=1), "[r, g, b] 0..1", 3, 3),
            "shininess": number(default=0.5, minimum=0, maximum=1),
            "transparency": number(default=0, minimum=0, maximum=1),
        },
    ),
    extra=_extra_appearance,
    own_id=False,
    title_fn=lambda a: "AI: Appearance",
    examples=[
        example({"look": "plastic_red"}, "the current body in glossy red"),
        example({"faces": TOP_FACE, "color": [0.1, 0.3, 0.8]}, "just the top face blue"),
    ],
)
define(
    "capture_design_history",
    "Capture design history",
    "timeline",
    "the design's menu: Capture Design History / Do Not Capture Design History",
    "Turn the timeline on or off for the design (Fusion's Capture Design History). on: false "
    "freezes every body into one step (direct modelling: press_pull, move_copy... still "
    "work); on: true starts a timeline again from there.",
    schema({"on": boolean("capture the history")}, ["on"]),
    steps=lambda a, sid: [{"op": "history_on" if a["on"] else "history_off"}],
    ops=["history_on", "history_off"],
    destructive=True,
    title_fn=lambda a: "AI: %s design history" % ("Capture" if a.get("on") else "Do not capture"),
    examples=[example({"on": False}, "switch to direct modelling (no timeline)")],
)
