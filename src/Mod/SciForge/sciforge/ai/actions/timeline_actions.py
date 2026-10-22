# SPDX-License-Identifier: LGPL-2.1-or-later
"""AI actions for the timeline and parameters: list the steps, read and edit one (the way
double-clicking it opens its dialog), move the history marker, suppress, delete, reorder,
rename, group; list, delete and set parameters. The timeline work is timeline_ops.py (the
code behind the timeline's menus and drags, each one Undo step of its own); edits run the
"*_edit" design steps of sciforge/ai/ops or the dialogs' own read / apply functions, so the
later steps keep their faces and edges (follow.py)."""

from ... import warn
from .. import bridge_core, executor, value_fit
from ..executor import UserError, _broken, json_result, jsonable, summary
from . import action


def _round(value):
    try:
        return round(float(value), 6)
    except Exception:
        return value


def _values_of(doc):
    """{object name: {label: value}} of every step's main values (model parameters)."""
    from ... import parameters

    found = {}
    try:
        for row in parameters.model_parameters(doc):
            entry = found.setdefault(row["object"], {})
            value = _round(row["value"])
            entry[row["label"]] = (
                {"value": value, "expression": row["expression"]} if row["expression"] else value
            )
    except Exception:
        pass
    return found


@action("get_timeline")
def get_timeline(ctx, args):
    from ... import timeline_ops

    doc = ctx.need_doc()
    tl = timeline_ops.timeline(doc)
    values = _values_of(doc)
    rows = []
    for item in tl.items:
        obj = doc.getObject(item.name)
        row = {
            "index": item.index,
            "id": item.name,
            "name": item.display,
            "kind": item.kind,
            "type": obj.TypeId if obj is not None else item.type_id,
            "body": item.body,
            "state": item.state,
        }
        if item.component:
            row["component"] = item.component_name or item.component
        if item.suppressed:
            row["suppressed"] = True
        if item.status != "ok":
            row["status"] = item.status
            row["message"] = item.message
        if item.group:
            row["group"] = item.group
            row["group_name"] = item.group_name
        if item.name in values:
            row["values"] = values[item.name]
        rows.append(row)
    after = tl.items[tl.marker - 1].name if 0 < tl.marker <= len(tl.items) else None
    return json_result(
        {
            "steps": rows,
            "history_marker": {"after_step": after, "slot": tl.marker, "at_end": tl.at_end},
        }
    )


# -- what kind of step --------------------------------------------------------------------------
_NATIVE = {
    "PartDesign::Pad": "extrude",
    "PartDesign::Pocket": "extrude",
    "PartDesign::Revolution": "revolve",
    "PartDesign::Groove": "revolve",
    "PartDesign::Fillet": "fillet",
    "PartDesign::Chamfer": "chamfer",
    "PartDesign::Thickness": "shell",
    "PartDesign::Hole": "hole",
    "PartDesign::LinearPattern": "pattern_rect",
    "PartDesign::PolarPattern": "pattern_circ",
}


def step_kind(obj):
    """The kind of edit a step takes (the name of its *_edit design step, or a kind of
    our own)."""
    from ... import (
        align,
        blend,
        coil,
        combine,
        construct,
        drafting,
        emboss,
        extrude,
        fillet_sets,
        gear,
        hardware,
        hole,
        loft,
        move,
        move_face,
        pattern,
        pipe,
        presspull,
        primitives,
        replace_face,
        revolve,
        rib,
        scale,
        shelling,
        silhouette,
        split,
        split_face,
        surface,
        sweep,
        text,
        thread,
    )

    checks = (
        ("sketch", lambda o: o.TypeId == "Sketcher::SketchObject"),
        ("text", text.is_text),
        ("fusion_pattern", pattern.is_pattern),
        ("sf_revolve", revolve.is_revolve),
        ("sf_sweep", sweep.is_sweep),
        ("sf_loft", loft.is_loft),
        ("sf_rib", rib.is_rib),
        ("sf_shell", shelling.is_shell),
        ("sf_draft2", drafting.is_draft),
        ("sf_scale_sketch", scale.is_sketch_scale),
        ("sf_scale", scale.is_scale),
        ("sf_coil", coil.is_ours),
        ("sf_pipe", pipe.is_ours),
        ("sf_gear", gear.is_ours),
        ("sf_primitive", primitives.is_ours),
        ("sf_hardware", hardware.is_hardware),
        ("fillet_sets", fillet_sets.is_sets),
        ("blend", blend.is_blend),
        ("sf_surface", surface.is_surface_step),
        ("combine", combine.is_combine),
        ("split_body", split.is_split),
        ("move_bodies", move.is_move),
        ("replace_face", replace_face.is_replace_face),
        ("split_face", split_face.is_split_face),
        ("silhouette_split", silhouette.is_silhouette),
        ("align_bodies", align.is_align),
        ("move_face", move_face.is_move_face),
        ("extrude", extrude.is_extrude),
        ("hole", hole.is_hole),
        ("thread", thread.is_thread),
        ("emboss", emboss.is_emboss),
        ("press_pull", presspull.is_press_pull),
        ("construct", lambda o: o.TypeId in construct.DATUM_TYPES),
    )
    for kind, test in checks:
        try:
            if test(obj):
                return kind
        except Exception:
            continue
    return _NATIVE.get(obj.TypeId)


def _read(obj, kind):
    """The step's options as its dialog shows them (JSON-ready), or None."""
    from ... import (
        align,
        blend,
        coil,
        combine,
        construct,
        drafting,
        emboss,
        extrude,
        fillet_sets,
        gear,
        hardware,
        hole,
        loft,
        move,
        move_face,
        pattern,
        pipe,
        primitives,
        replace_face,
        revolve,
        rib,
        scale,
        shelling,
        silhouette,
        split,
        split_face,
        surface,
        sweep,
        text,
        thread,
    )

    readers = {
        "text": lambda o: text.spec_of(o),
        "fusion_pattern": lambda o: dict(zip(("kind", "options"), pattern.read(o))),
        "sf_revolve": lambda o: dict(zip(("profiles", "axis", "options"), revolve.read(o))),
        "sf_sweep": lambda o: sweep.read(o),
        "sf_loft": lambda o: loft.read(o),
        "sf_rib": lambda o: rib.read(o),
        "sf_shell": lambda o: dict(zip(("base", "faces", "options", "formulas"), shelling.read(o))),
        "sf_draft2": lambda o: dict(
            zip(("base", "plane", "faces", "options", "formula"), drafting.read(o))
        ),
        "sf_scale": lambda o: dict(zip(("base", "point", "options", "formulas"), scale.read(o))),
        "sf_coil": lambda o: coil.read(o),
        "sf_pipe": lambda o: pipe.read(o),
        "sf_gear": lambda o: gear.read(o),
        "sf_primitive": lambda o: dict(zip(("kind", "ref", "options"), primitives.read(o))),
        "sf_hardware": lambda o: hardware.read(o),
        "fillet_sets": lambda o: fillet_sets.read(o),
        "blend": lambda o: {
            "kind": blend.kind_of(o),
            "options": blend.read(o),
            "edges": blend.refs_of(o)[1],
        },
        "sf_surface": lambda o: dict(zip(("kind", "refs", "options"), surface.read(o))),
        "combine": lambda o: combine.read(o),
        "split_body": lambda o: split.read(o),
        "move_bodies": lambda o: move.read(o)[0],
        "replace_face": lambda o: replace_face.read(o),
        "split_face": lambda o: split_face.read(o),
        "silhouette_split": lambda o: silhouette.read(o),
        "align_bodies": lambda o: align.read(o),
        "move_face": lambda o: move_face.read(o),
        "extrude": lambda o: dict(zip(("profiles", "options"), extrude.read(o))),
        "hole": lambda o: hole.read(o),
        "thread": lambda o: thread.read(o),
        "emboss": lambda o: dict(
            zip(("base", "profiles", "faces", "options", "formulas"), emboss.read(o))
        ),
        "construct": lambda o: dict(
            zip(("preset", "refs", "points", "values", "formulas"), construct.read(o) or ())
        ),
    }
    reader = readers.get(kind)
    if reader is None:
        return None
    return jsonable(reader(obj))


@action("get_step")
def get_step(ctx, args):
    from ... import timeline_ops

    obj = ctx.resolve(args["step"])
    doc = obj.Document
    kind = step_kind(obj)
    info = {"id": obj.Name, "label": obj.Label, "type": obj.TypeId, "kind": kind}
    try:
        item = timeline_ops.timeline(doc).find(obj.Name)
        if item is not None:
            info.update(
                name=item.display, state=item.state, status=item.status, suppressed=item.suppressed
            )
            if item.message:
                info["message"] = item.message
    except Exception:
        pass
    try:
        info["uses"] = sorted(timeline_ops.uses(obj))
    except Exception:
        pass
    if kind == "sketch":
        info["note"] = "A sketch: read it with get_sketch."
    else:
        try:
            read = _read(obj, kind)
            if read is not None:
                info["definition"] = read
        except Exception as exc:
            info["definition_error"] = str(exc)
    values = _values_of(doc).get(obj.Name)
    if values:
        info["values"] = values
    formulas = {p: e for p, e in obj.ExpressionEngine}
    if formulas:
        from ... import parameters_core

        info["formulas"] = {p: parameters_core.from_freecad(e) for p, e in formulas.items()}
    return json_result(info)


# -- edit -----------------------------------------------------------------------------------------
_EDIT_OPS = {
    "fusion_pattern": "pattern_edit",
    "sf_revolve": "sf_revolve_edit",
    "sf_sweep": "sf_sweep_edit",
    "sf_loft": "sf_loft_edit",
    "sf_rib": "sf_rib_edit",
    "sf_shell": "sf_shell_edit",
    "sf_draft2": "sf_draft2_edit",
    "sf_scale": "sf_scale_edit",
    "sf_coil": "sf_primitive_edit",
    "sf_pipe": "sf_primitive_edit",
    "sf_primitive": "sf_primitive_edit",
    "sf_gear": "sf_gear_edit",
    "sf_hardware": "sf_hardware_edit",
    "sf_surface": "sf_surface_edit",
    "combine": "body_tool_edit",
    "split_body": "body_tool_edit",
    "move_bodies": "body_tool_edit",
    "replace_face": "modify_edit",
    "split_face": "modify_edit",
    "silhouette_split": "modify_edit",
    "align_bodies": "modify_edit",
}
_EXTRUDE_KEYS = {
    "distance": "distance",
    "distance2": "distance2",
    "taper": "taper",
    "taper2": "taper2",
    "direction": "direction",
    "operation": "operation",
    "measurement": "measurement",
    "start_offset": "start_offset",
    "object_offset": "object_offset",
    "object_offset2": "object_offset2",
}


def _option_keys(obj, kind):
    """The option names an edit of this kind of step takes (the options its dialog shows:
    get_step's definition), or None when they cannot be listed here (the edit then checks
    them itself, or the "nothing changed" check below catches a name it ignored)."""
    from ... import (
        blend,
        coil,
        combine,
        drafting,
        emboss,
        gear,
        hole,
        loft,
        pattern,
        pipe,
        primitives,
        replace_face,
        revolve,
        rib,
        shelling,
        silhouette,
        split_face,
        surface,
        sweep,
        thread,
    )
    from ..ops import bodies_ops, core, hardware_ops

    refs = ("target", "tool", "direction", "from", "to")  # (modify_edit: picked again)
    readers = {
        "blend": lambda o: blend.read(o),
        "hole": lambda o: hole.read(o),
        "thread": lambda o: thread.read(o),
        "emboss": lambda o: emboss.read(o)[3],
        "sf_shell": lambda o: list(shelling.read(o)[2]) + ["thickness"],
        "sf_primitive": lambda o: primitives.read(o)[2],
        "sf_coil": lambda o: coil.read(o)[1],
        "sf_pipe": lambda o: pipe.read(o)[1],
        "sf_gear": lambda o: gear.read(o)[1],
        "sf_draft2": lambda o: drafting.read(o)[3],
        "sf_revolve": lambda o: list(revolve.read(o)[2]) + ["expressions"],
        "sf_sweep": lambda o: list(sweep.read(o)[3]) + ["expressions"],
        "sf_loft": lambda o: loft.read(o)[3],
        "sf_rib": lambda o: rib.read(o)[1],
        "sf_surface": lambda o: surface.read(o)[2],
        "combine": lambda o: combine.read(o),
        "fusion_pattern": lambda o: list(pattern.read(o)[1]) + ["type"],
        "replace_face": lambda o: list(replace_face.read(o)) + list(refs),
        "split_face": lambda o: list(split_face.read(o)) + list(refs),
        "silhouette_split": lambda o: list(silhouette.read(o)) + list(refs),
        "split_body": lambda o: ("tool", "extend"),
        "move_bodies": lambda o: bodies_ops.MOVE_KEYS + ("pivot", "from_point", "to_point"),
        "sf_hardware": lambda o: hardware_ops.HARDWARE_KEYS,
        "sf_scale": lambda o: ("factor", "factors"),
        "sf_scale_sketch": lambda o: ("factor",),
        "move_face": lambda o: ("move", "rotate"),
        "extrude": lambda o: tuple(_EXTRUDE_KEYS) + ("through_all", "flip"),
        "construct": lambda o: ("distance", "angle", "fraction", "distance_type"),
    }
    reader = readers.get(kind)
    if reader is None:
        reader = (lambda o: core._EDIT_PROPS[kind]) if kind in core._EDIT_PROPS else None
    if reader is None:
        return None
    try:
        return sorted(str(k) for k in reader(obj))
    except Exception as exc:
        warn("AI edit_step: the options of %s could not be listed (%s)" % (obj.Name, exc))
        return None


def _norm(key):
    return str(key).strip().lower().replace(" ", "_").replace("-", "_")


def _checked_changes(obj, kind, changes):
    """set with the option names as the step has them: "Radius" / "Length" (get_step's
    values spellings) become radius / length, a shell's thickness becomes its inside or
    outside wall (as the shell tool reads it). A name the step does not have is refused with
    the ones it has, instead of being ignored with "Done"."""
    keys = _option_keys(obj, kind)
    if keys is None:
        return changes
    known = {_norm(k): k for k in keys}
    out = {}
    unknown = []
    for key, value in changes.items():
        name = key if key in keys else known.get(_norm(key))
        if name is None:
            unknown.append(key)
        else:
            out[name] = value
    if unknown:
        shown = [k for k in keys if k != "expressions"]
        raise UserError(
            "%s has no option %s: set takes %s (get_step shows their values). Nothing was "
            "changed." % (obj.Label, ", ".join(repr(k) for k in unknown), ", ".join(shown))
        )
    if kind == "sf_shell" and "thickness" in out:
        from ... import shelling

        thickness = out.pop("thickness")
        direction = out.get("direction") or shelling.read(obj)[2].get("direction", "inside")
        for side in ("inside", "outside"):
            if direction in (side, "both"):
                out.setdefault(side, thickness)
    return out


def _edit_state(doc, obj, kind):
    """What an edit can change, to tell an edit that changed nothing: the step's options,
    its formulas, its own shape and every solid."""
    try:
        definition = json_result(_read(obj, kind))["text"] if kind else None
    except Exception:
        definition = None
    try:
        shape = obj.Shape
        box = shape.BoundBox
        own = (
            round(shape.Volume, 6),
            round(shape.Area, 6),
            round(shape.Length, 6),
            len(shape.Faces),
            len(shape.Edges),
            tuple(
                round(v, 6) for v in (box.XMin, box.YMin, box.ZMin, box.XMax, box.YMax, box.ZMax)
            ),
        )
    except Exception:
        own = None
    try:
        formulas = sorted(obj.ExpressionEngine)
    except Exception:
        formulas = None
    return definition, own, formulas, executor.shape_signature(doc)


class _Unchanged(UserError):
    """An edit that left the step exactly as it was (taken back: no Undo step)."""


@action("edit_step")
def edit_step(ctx, args):
    obj = ctx.resolve(args["step"])
    doc = obj.Document
    kind = step_kind(obj)
    changes = dict(args.get("set") or {})
    if kind is None:
        raise UserError("SciForge cannot edit a %s step here." % obj.TypeId.split("::")[-1])
    if kind == "sketch":
        raise UserError(
            "A sketch is changed with add_to_sketch, set_sketch_dimension, "
            "sketch_constraint and sketch_delete."
        )
    if kind == "fillet_sets":
        raise UserError(
            "Change this fillet's sizes with set_model_parameter (label \"Set 1 "
            'Size"...): list_parameters shows them.'
        )
    if (args.get("add_edges") or args.get("add_faces")) and kind != "blend":
        raise UserError("add_edges / add_faces only apply to a fillet or chamfer.")
    changes = _checked_changes(obj, kind, changes)
    builder = ctx.builder(doc)
    before = _broken(doc)
    state = _edit_state(doc, obj, kind)

    def work(changes=changes):
        target = obj.Name
        builder.objects[target] = obj
        if kind in _EDIT_OPS:
            op = _EDIT_OPS[kind]
            builder.ops[target] = kind
            step = {"op": op, "target": target, "set": changes}
            if op == "sf_scale_sketch_edit":
                step = {"op": op, "target": target, "factor": changes.get("factor")}
            builder.run(step)
        elif kind == "sf_scale_sketch":
            if "factor" not in changes:
                raise UserError('A sketch scale takes set {"factor": ...}.')
            builder.run(
                {"op": "sf_scale_sketch_edit", "target": target, "factor": changes["factor"]}
            )
        elif kind == "move_face":
            step = {"op": "move_face_edit", "target": target}
            for key in ("move", "rotate"):
                if key in changes:
                    step[key] = changes[key]
            if len(step) == 2:
                raise UserError(
                    'A face move takes set {"move": [dx, dy, dz]} or {"rotate": '
                    '{"axis": [x, y, z], "angle": deg, "center": [x, y, z]}}.'
                )
            builder.run(step)
        elif kind == "blend":
            step = {"op": "blend_edit", "target": target, "set": changes}
            for key in ("add_edges", "add_faces"):
                if key in args:
                    step[key] = args[key]
            builder.run(step)
        elif kind == "extrude":
            _edit_extrude(doc, obj, changes)
        elif kind == "hole":
            _edit_with(doc, obj, changes, "hole")
        elif kind == "thread":
            _edit_with(doc, obj, changes, "thread")
        elif kind == "emboss":
            _edit_with(doc, obj, changes, "emboss")
        elif kind == "construct":
            _edit_construct(doc, obj, changes)
        elif kind == "text":
            _edit_text(doc, obj, changes)
        else:  # PartDesign's own features and Press Pull: the "edit" step's option names
            builder.ops[target] = kind
            builder.run({"op": "edit", "target": target, "set": changes})
        doc.recompute()

    def checked_work():
        work()
        if _edit_state(doc, obj, kind) == state:
            raise _Unchanged(obj.Label)  # (taken back by ctx.change: no Undo step)

    try:
        ctx.change(checked_work)
    except _Unchanged:
        return bridge_core.result(
            "No change: %s already has these values, so nothing was done (no Undo step). "
            "get_step shows its options and values." % obj.Label
        )
    except Exception as exc:
        text = executor._plain(exc)
        extra = ""
        if value_fit.is_limit(text) and edit_candidates(kind, changes):
            extra = _largest_edit(ctx, doc, kind, changes, work)
        if not extra:
            raise
        text = executor._clean(text).rstrip()
        raise UserError(
            "Not done (%s): %s%s%s" % (ctx.title, text, "" if text.endswith(".") else ".", extra)
        )
    return ctx.done("Done: %s." % ctx.title, doc, before)


# Values of a step whose safe side is toward 0 (value_fit, as the dialogs hold them), per
# kind of step; "*": every kind not named.
_EDIT_LIMITED = {
    "extrude": ("taper", "taper2"),
    "*": (
        "radius",
        "chord",
        "start",
        "end",
        "distance",
        "distance2",
        "size",
        "size2",
        "thickness",
        "inside",
        "outside",
        "angle",
        "angle2",
        "torus_diameter",
        "section_size",
        "hole",
        "fillet",
        "backlash",
    ),
}
_EDIT_NOT_LIMITED = (
    "construct",
    "hole",
    "thread",
    "text",
    "fusion_pattern",
    "sf_scale",
    "sf_revolve",
    "emboss",
    "move_face",
    "sf_scale_sketch",
    "sf_hardware",
)


def edit_candidates(kind, changes):
    """[(key, value)] of the size values an edit sets that may not fit (tried in order)."""
    if kind in _EDIT_NOT_LIMITED:
        return []
    keys = _EDIT_LIMITED.get(kind, _EDIT_LIMITED["*"])
    out = []
    for key, value in changes.items():
        if key.lower() not in keys or isinstance(value, bool):
            continue
        if isinstance(value, (int, float)) and value != 0:
            out.append((key, float(value)))
    return out


def _largest_edit(ctx, doc, kind, changes, work):
    """The sentence giving the largest value of an edit that fits (value_fit, found by
    trying values in transactions that are taken back), or ""."""
    from ... import value_limits

    def trial(key, value):
        new = dict(changes)
        new[key] = value
        before = _broken(doc)
        doc.openTransaction("AI: trying a value")
        try:
            work(new)
            return not executor.broke_text(doc, before)
        except Exception:
            return False
        finally:
            doc.abortTransaction()

    try:
        for key, value in edit_candidates(kind, changes):
            unit = "deg" if "angle" in key.lower() or "taper" in key.lower() else "mm"
            step = value_limits.step_for(unit)
            if abs(value) <= step:
                continue
            limit, exact = value_limits.search(
                lambda v, k=key: trial(k, v),
                step if value > 0 else -step,
                value,
                step,
                budget=value_fit.BUDGET,
            )
            if limit is not None:
                return value_fit.sentence(
                    value_fit.words_for(key), unit, value, limit, exact, "set." + key
                )
        return ""
    except Exception as exc:
        warn("AI edit_step: the largest value that fits was not found (%s)" % exc)
        return ""
    finally:
        try:
            doc.recompute()
        except Exception:
            pass


def _later(doc, obj):
    from ... import bodies, follow

    return follow.snapshot(bodies.body_of(obj), obj)


def _settle(doc, records):
    from ... import follow

    follow.recompute(doc, records)


def _edit_extrude(doc, feature, changes):
    from ... import extrude

    unknown = set(changes) - set(_EXTRUDE_KEYS) - {"through_all", "flip"}
    if unknown:
        raise UserError(
            "An extrude takes set with %s (not %s)."
            % (
                ", ".join(sorted(_EXTRUDE_KEYS) + ["through_all", "flip"]),
                ", ".join(sorted(unknown)),
            )
        )
    profiles, options = extrude.read(feature)
    sign = -1.0 if options.get("distance", 1.0) < 0 else 1.0
    for key, name in _EXTRUDE_KEYS.items():
        if key in changes:
            options[name] = changes[key]
    if "distance" in changes:
        options["distance"] = sign * abs(float(changes["distance"]))
        options["extent"] = "distance"
    if changes.get("flip"):
        options["distance"] = -options.get("distance", 10.0)
    if "through_all" in changes:
        options["extent"] = "all" if changes["through_all"] else "distance"
    records = _later(doc, feature)
    try:
        extrude.update(feature, profiles, options)
    except extrude.ExtrudeError as exc:
        raise UserError(str(exc))
    _settle(doc, records)


def _edit_with(doc, feature, changes, kind):
    from ... import emboss, hole, thread

    records = _later(doc, feature)
    if kind == "hole":
        options = hole.read(feature)
        options.update(changes)
        try:
            hole.apply(feature, options)
        except hole.HoleError as exc:
            raise UserError(str(exc))
    elif kind == "thread":
        options = thread.read(feature)
        options.update(changes)
        try:
            thread.apply(feature, None, options)
        except thread.ThreadError as exc:
            raise UserError(str(exc))
    else:
        base, profiles, names, options, formulas = emboss.read(feature)
        options.update(changes)
        try:
            emboss.apply(feature, base, profiles, names, options, formulas)
        except Exception as exc:
            raise UserError(str(exc))
    _settle(doc, records)


def _edit_construct(doc, datum, changes):
    from ... import construct

    read = construct.read(datum)
    if read is None:
        raise UserError(
            "%s was not made by SciForge's CONSTRUCT: it cannot be edited here." % datum.Label
        )
    key, refs, points, values, formulas = read
    unknown = set(changes) - {"distance", "angle", "fraction", "distance_type"}
    if unknown:
        raise UserError(
            "A construction takes set with distance, angle, fraction, " "distance_type."
        )
    values = dict(values or {})
    values.update(changes)
    try:
        construct.update(datum, key, refs, values, points, formulas)
    except construct.ConstructError as exc:
        raise UserError(str(exc))


def _edit_text(doc, obj, changes):
    from ... import text

    spec = text.spec_of(obj)
    unknown = set(changes) - set(spec)
    if unknown:
        raise UserError("A text takes set with %s." % ", ".join(sorted(spec)))
    spec.update(changes)
    try:
        text.check_spec(spec)
        text.apply_spec(obj, spec)
    except text.TextError as exc:
        raise UserError(str(exc))


# -- the marker and the steps --------------------------------------------------------------------
def _names(ctx, idents):
    return [ctx.resolve(i, "step").Name for i in idents]


@action("roll_timeline")
def roll_timeline(ctx, args):
    from ... import timeline_core, timeline_ops

    doc = ctx.need_doc()
    tl = timeline_ops.timeline(doc)
    before = None
    if "to" in args:
        where = {"previous": "prev"}.get(args["to"], args["to"])
        tips = timeline_core.tips_for_step(tl, where)
        if tips is None:
            return bridge_core.result(
                "The history marker is already there (%s)." % _marker_text(doc)
            )
        timeline_ops.roll(doc, tips)
    else:
        name = ctx.resolve(args.get("after") or args.get("before"), "step").Name
        names = tl.names()
        if name not in names:
            raise UserError("%r is not a timeline step." % name)
        slot = names.index(name) + (1 if "after" in args else 0)
        tips, before = timeline_core.marker_for_slot(tl, slot)
        if tips is None and (before or "") == (tl.before or ""):
            return bridge_core.result(
                "The history marker is already there (%s)." % _marker_text(doc)
            )
        timeline_ops.roll(doc, tips or {}, before=before)
    ctx.host.after_change(doc)
    return bridge_core.result("History marker moved: %s. %s" % (_marker_text(doc), summary(doc)))


def _marker_text(doc):
    from ... import timeline_ops

    tl = timeline_ops.timeline(doc)
    if tl.at_end:
        return "at the end"
    if tl.marker == 0:
        return "at the start (an empty design)"
    item = tl.items[tl.marker - 1]
    return "after %s (%s), %d step(s) rolled back" % (
        item.display,
        item.name,
        len(tl.items) - tl.marker,
    )


@action("suppress_step")
def suppress_step(ctx, args):
    from ... import timeline_ops

    doc = ctx.need_doc()
    names = _names(ctx, args["steps"])
    on = args.get("suppress", True)
    before = _broken(doc)
    try:
        with_them = timeline_ops.suppress_many(doc, names, on)
    except timeline_ops.TimelineError as exc:
        raise UserError(str(exc))
    ctx.host.after_change(doc)
    others = [n for n in (with_them or []) if n not in names]
    text = "%s %s." % ("Suppressed" if on else "Unsuppressed", ", ".join(names))
    if others:
        text += " With them (they depend on them): %s." % ", ".join(others)
    return ctx.done(text, doc, before)


@action("delete_step")
def delete_step(ctx, args):
    from ... import timeline_ops

    doc = ctx.need_doc()
    names = _names(ctx, args["steps"])
    before = _broken(doc)
    try:
        timeline_ops.delete(doc, names)
    except timeline_ops.TimelineError as exc:
        raise UserError(str(exc))
    from .. import executor

    executor.forget(doc.Name)
    ctx.host.after_change(doc)
    return ctx.done("Deleted %s (undo brings them back)." % ", ".join(names), doc, before)


@action("move_step")
def move_step(ctx, args):
    from ... import timeline_ops

    doc = ctx.need_doc()
    name = ctx.resolve(args["step"], "step").Name
    ref = ctx.resolve(args.get("before") or args.get("after"), "step").Name
    names = timeline_ops.timeline(doc).names()
    if name not in names or ref not in names:
        raise UserError("Both must be timeline steps.")
    slot = names.index(ref) + (0 if "before" in args else 1)
    before = _broken(doc)
    try:
        timeline_ops.move(doc, name, slot)
    except timeline_ops.TimelineError as exc:
        raise UserError("Not moved: %s" % exc)
    ctx.host.after_change(doc)
    return ctx.done(
        "Moved %s %s %s." % (name, "before" if "before" in args else "after", ref), doc, before
    )


@action("rename")
def rename(ctx, args):
    from ... import bodies, components, timeline_ops

    doc = ctx.need_doc()
    obj = ctx.resolve(args["target"])
    text = args["name"].strip()
    if not text:
        raise UserError("The new name must not be empty.")
    old = obj.Label
    if components.is_component(obj):
        components.rename(doc, obj, text)
    elif bodies.is_body(obj) or obj.TypeId in ("TechDraw::DrawPage",):
        ctx.change(lambda: setattr(obj, "Label", text))
    else:
        timeline_ops.rename(doc, obj.Name, text)
    ctx.host.after_change(doc)
    return bridge_core.result("Renamed %s (id %r) to %r." % (old, obj.Name, obj.Label))


@action("group_steps")
def group_steps(ctx, args):
    from ... import timeline_ops

    doc = ctx.need_doc()
    if args.get("ungroup"):
        if not timeline_ops.ungroup(doc, args["group"]):
            raise UserError("There is no group %r (get_timeline lists the groups)." % args["group"])
        ctx.host.after_change(doc)
        return bridge_core.result("Ungrouped %s." % args["group"])
    names = _names(ctx, args["steps"])
    try:
        # the name goes in with the group: one undo step (no "Rename Group" after it)
        gid = timeline_ops.group(doc, names, (args.get("name") or "").strip() or None)
    except timeline_ops.TimelineError as exc:
        raise UserError(str(exc))
    ctx.host.after_change(doc)
    return bridge_core.result(
        "Grouped %s as %r (group id %r)." % (", ".join(names), args.get("name") or gid, gid)
    )


# -- parameters ----------------------------------------------------------------------------------
@action("list_parameters")
def list_parameters(ctx, args):
    from ... import parameters

    doc = ctx.need_doc()
    out = {
        "user": [
            {k: _round(v) if k == "value" else v for k, v in row.items()}
            for row in parameters.user_parameters(doc)
        ]
    }
    derived = parameters.derived_parameters(doc)
    if derived:
        out["derived"] = derived
    if args.get("model", True):
        rows = []
        for row in parameters.model_parameters(doc):
            rows.append(
                {
                    "step": row["object"],
                    "step_label": row["owner"],
                    "label": row["label"],
                    "value": _round(row["value"]),
                    "unit": row["unit"],
                    "expression": row["expression"],
                }
            )
        out["model"] = rows
    return json_result(out)


@action("delete_parameter")
def delete_parameter(ctx, args):
    from ... import parameters, parameters_core

    doc = ctx.need_doc()
    if args["name"] not in parameters.user_names(doc):
        raise UserError("There is no user parameter %r." % args["name"])

    def work():
        try:
            parameters.remove_user(doc, args["name"])
        except parameters_core.ParameterError as exc:
            raise UserError(str(exc))

    ctx.change(work)
    return bridge_core.result("Deleted the parameter %s." % args["name"])


@action("set_model_parameter")
def set_model_parameter(ctx, args):
    from ... import parameters, parameters_core

    doc = ctx.need_doc()
    obj = ctx.resolve(args["step"], "step")
    rows = [r for r in parameters.model_parameters(doc) if r["object"] == obj.Name]
    found = [r for r in rows if r["label"] == args["label"]]
    if not found:
        found = [r for r in rows if r["label"].lower() == args["label"].lower()]
    if not found:
        raise UserError(
            "%s has no model parameter %r (it has: %s)."
            % (obj.Name, args["label"], ", ".join(r["label"] for r in rows) or "none")
        )
    row = found[0]
    text = args.get("expression")
    if text is None:
        value = args["value"]
        text = "%r %s" % (float(value), row["unit"]) if row["unit"] else repr(value)
    before = _broken(doc)

    def work():
        try:
            parameters.set_model(doc, row, text)
        except parameters_core.ParameterError as exc:
            raise UserError(str(exc))
        doc.recompute()

    ctx.change(work)
    now = [
        r
        for r in parameters.model_parameters(doc)
        if r["object"] == obj.Name and r["label"] == row["label"]
    ]
    shown = _round(now[0]["value"]) if now else text
    return ctx.done("Done: %s %s = %s." % (obj.Name, row["label"], shown), doc, before)
