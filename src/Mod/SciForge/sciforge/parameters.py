# SPDX-License-Identifier: LGPL-2.1-or-later
"""User and model parameters (outline 7.4). No GUI code.

User parameters are properties of an App::VarSet named "Parameters" in the
document, so they are saved with it and any expression can use them
(FreeCAD spelling `Parameters.width`; the dialog lets you write `width`).
Model parameters are the dimensions already in the design: feature values
(extrude length, fillet radius, ...) and sketch dimensions.
"""
import FreeCAD as App

from . import parameters_core as core

GROUP = "Parameters"
DERIVED_GROUP = "Derived"  # parameters a Derive brought in (derive.py): read-only, linked

# Feature type -> [(property, label)] shown as model parameters.
FEATURE_PROPS = {
    "PartDesign::Pad": [("Length", "Distance"), ("Length2", "Distance 2"), ("TaperAngle", "Taper")],
    "PartDesign::Pocket": [
        ("Length", "Distance"),
        ("Length2", "Distance 2"),
        ("TaperAngle", "Taper"),
    ],
    "PartDesign::Revolution": [("Angle", "Angle")],
    "PartDesign::Groove": [("Angle", "Angle")],
    "PartDesign::Fillet": [("Radius", "Radius")],
    "PartDesign::Chamfer": [("Size", "Distance"), ("Size2", "Distance 2"), ("Angle", "Angle")],
    "PartDesign::Thickness": [("Value", "Thickness")],
    "PartDesign::Hole": [("Diameter", "Diameter"), ("Depth", "Depth")],
    "PartDesign::LinearPattern": [("Occurrences", "Quantity"), ("Offset", "Spacing")],
    "PartDesign::PolarPattern": [("Occurrences", "Quantity"), ("Angle", "Angle")],
    "PartDesign::Draft": [("Angle", "Angle")],
}
# SciForge's own features (their SciForgeType) -> [(property, label)], shown the same way.
SCIFORGE_PROPS = {
    "PressPull": [("Distance", "Distance")],
    "OffsetFace": [("Distance", "Distance")],
    "Shell": [("InsideThickness", "Inside Thickness"), ("OutsideThickness", "Outside Thickness")],
    "Scale": [
        ("Factor", "Scale Factor"),
        ("FactorX", "X Scale"),
        ("FactorY", "Y Scale"),
        ("FactorZ", "Z Scale"),
    ],
    "SketchText": [("TextHeight", "Text Height")],
    "Emboss": [
        ("Depth", "Depth"),
        ("HorizontalDistance", "Horizontal Distance"),
        ("VerticalDistance", "Vertical Distance"),
        ("RotationAngle", "Rotation Angle"),
    ],
}
# SciForge's own Fillet / Chamfer step (fillet_sets.py): one size per selection set (row)
SCIFORGE_PROPS["FilletSets"] = [("Size%d" % i, "Set %d Size" % i) for i in range(1, 13)]
SCIFORGE_PROPS["ChamferSets"] = [
    item
    for i in range(1, 13)
    for item in (
        ("Size%d" % i, "Set %d Distance" % i),
        ("SizeB%d" % i, "Set %d Distance 2" % i),
        ("Angle%d" % i, "Set %d Angle" % i),
    )
]
DIMENSION_TYPES = {"Distance", "DistanceX", "DistanceY", "Radius", "Diameter", "Angle"}


def container(doc, create=False):
    obj = doc.getObject(core.CONTAINER)
    if obj is None and create:
        obj = doc.addObject("App::VarSet", core.CONTAINER)
        obj.Label = "Parameters"
    return obj


def user_names(doc):
    """Every parameter a formula can name: the user's own and the derived ones."""
    obj = container(doc)
    if obj is None:
        return []
    return [p for p in obj.PropertiesList if obj.getGroupOfProperty(p) in (GROUP, DERIVED_GROUP)]


def own_names(doc):
    """The user's own parameters (the ones Change Parameters edits)."""
    obj = container(doc)
    if obj is None:
        return []
    return [p for p in obj.PropertiesList if obj.getGroupOfProperty(p) == GROUP]


def derived_names(doc):
    obj = container(doc)
    if obj is None:
        return []
    return [p for p in obj.PropertiesList if obj.getGroupOfProperty(p) == DERIVED_GROUP]


def derived_parameters(doc):
    """[{name, unit, value, comment}] of the parameters a Derive brought in (Fusion shows
    them greyed: they change in their source design)."""
    obj = container(doc)
    rows = []
    for name in derived_names(doc):
        value = getattr(obj, name)
        rows.append(
            {
                "name": name,
                "unit": core.unit_of(obj.getTypeIdOfProperty(name)),
                "expression": "",
                "value": value.Value if hasattr(value, "Value") else value,
                "comment": obj.getDocumentationOfProperty(name),
            }
        )
    return rows


def user_parameters(doc):
    """[{name, unit, expression, value, comment}] in creation order."""
    obj = container(doc)
    rows = []
    if obj is None:
        return rows
    expressions = dict(obj.ExpressionEngine)
    for name in own_names(doc):
        value = getattr(obj, name)
        rows.append(
            {
                "name": name,
                "unit": core.unit_of(obj.getTypeIdOfProperty(name)),
                "expression": core.from_freecad(expressions.get(name, "")),
                "value": value.Value if hasattr(value, "Value") else value,
                "comment": obj.getDocumentationOfProperty(name),
            }
        )
    return rows


def add_user(doc, name, unit="mm", text="1", comment=""):
    core.check_name(name, existing=set(user_names(doc)))
    obj = container(doc, create=True)
    obj.addProperty(core.property_type(unit), name, GROUP, comment)
    set_user(doc, name, text)
    return obj


def remove_user(doc, name):
    if name in derived_names(doc):
        raise core.ParameterError(
            "'%s' comes from another design (Derive): untick it in the Derive to remove it."
            % name
        )
    users = _users_of(doc, name)
    if users:
        raise core.ParameterError(
            "'%s' is used by: %s. Change those first." % (name, ", ".join(users))
        )
    container(doc).removeProperty(name)


def _users_of(doc, name):
    import re

    needle = "%s.%s" % (core.CONTAINER, name)
    # Another parameter's formula ("half = w / 2") lives in the container itself, where
    # FreeCAD writes the reference without the container's name ("w / 2"): look for the bare
    # name there (before, deleting w left half with a broken formula).
    bare = re.compile(r"(?<![A-Za-z0-9_.])%s(?![A-Za-z0-9_])" % re.escape(name))
    holder = container(doc)
    found = []
    for obj in doc.Objects:
        for path, expr in obj.ExpressionEngine:
            if obj is holder and path != name and bare.search(expr):
                found.append("the parameter %s" % path)
                continue
            if needle in expr or ("<<%s>>.%s" % (core.CONTAINER, name)) in expr:
                found.append(obj.Label)
                break
    return found


def set_user(doc, name, text):
    """A number ('25', '25 mm') or an expression ('width / 2')."""
    if name in derived_names(doc):
        raise core.ParameterError(
            "'%s' comes from another design (Derive): change it there and update the Derive."
            % name
        )
    obj = container(doc)
    _set(obj, name, text, user_names(doc))


def model_parameters(doc):
    """[{owner, object, path, label, value, unit, expression}] for every dimension in the design."""
    rows = []
    for obj in doc.Objects:
        expressions = dict(obj.ExpressionEngine)
        if obj.TypeId in FEATURE_PROPS:
            for prop, label in FEATURE_PROPS[obj.TypeId]:
                if prop not in obj.PropertiesList or obj.getEditorMode(prop):
                    continue  # hidden or read-only for this feature's mode
                value = getattr(obj, prop)
                rows.append(_row(obj, prop, label, value, expressions.get(prop, "")))
        elif getattr(obj, "SciForgeType", "") in SCIFORGE_PROPS:
            for prop, label in SCIFORGE_PROPS[obj.SciForgeType]:
                if prop not in obj.PropertiesList or obj.getEditorMode(prop):
                    continue  # hidden: not used by this feature's choices
                value = getattr(obj, prop)
                rows.append(_row(obj, prop, label, value, expressions.get(prop, "")))
        elif obj.TypeId == "Sketcher::SketchObject":
            for i, constraint in enumerate(obj.Constraints):
                if constraint.Type not in DIMENSION_TYPES or not constraint.Driving:
                    continue
                path = ".Constraints[%d]" % i
                label = constraint.Name or "d%d" % (i + 1)
                quantity = obj.getDatum(i)
                expr = expressions.get(path, "")
                if not expr and constraint.Name:
                    expr = expressions.get(".Constraints.%s" % constraint.Name, "")
                rows.append(_row(obj, path, label, quantity, expr))
    return rows


def _row(obj, path, label, value, expr):
    number = value.Value if hasattr(value, "Value") else value
    unit = str(value.Unit) if hasattr(value, "Unit") else ""
    return {
        "owner": obj.Label,
        "object": obj.Name,
        "path": path,
        "label": label,
        "value": number,
        "unit": "deg" if "Angle" in unit else ("mm" if "Length" in unit else ""),
        "expression": core.from_freecad(expr),
    }


def set_model(doc, row, text):
    obj = doc.getObject(row["object"])
    _set(obj, row["path"], text, user_names(doc))


def is_plain_number(text):
    """'25', '25 mm', '1.5 in', '30 deg' -> True; 'width * 2', 'Sketch.x' -> False."""
    import re

    words = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text)
    if any(w not in core.RESERVED or w in ("pi", "e") for w in words):
        return False
    try:
        App.Units.Quantity(text)
        return True
    except Exception:
        return False


def _set(obj, path, text, names):
    """Plain numbers set the value; anything else becomes an expression."""
    text = (text or "").strip()
    if not text:
        obj.setExpression(path, None)
        return
    if not is_plain_number(text):
        obj.setExpression(path, core.to_freecad(text, names))
        return
    obj.setExpression(path, None)
    number = App.Units.Quantity(text)
    if path.startswith(".Constraints["):
        obj.setDatum(int(path[len(".Constraints[") : -1]), number)
    elif "Integer" in obj.getTypeIdOfProperty(path):
        setattr(obj, path, int(round(number.Value)))
    elif obj.getTypeIdOfProperty(path) == "App::PropertyFloat":
        setattr(obj, path, number.Value)
    else:
        setattr(obj, path, number)


# -- Change Parameters checked on a trial ------------------------------------------------------
# Fusion's idea, CADCraft's habit (docs/sciforge/dev/cadcraft-lessons.md, idea 1): a parameter
# change that would break the design is refused with the step and the dimension it would break,
# and nothing changes. The change is made, the design recomputed, and when a step that was fine
# is now broken (a feature fails, a sketch's constraints conflict, a sketch length or radius
# becomes 0 or less), the change is put back and the design recomputed again. Change Parameters
# keeps everything in one transaction until OK, so the change is undone by hand, not aborted.
SKIP_TYPES = (
    "PartDesign::Body",
    "App::Part",
    "App::Origin",
    "App::DocumentObjectGroup",
)
SIGNED = ("DistanceX", "DistanceY")  # FreeCAD keeps their sign: it is their direction


def broken_steps(doc, signs=None, typed=None):
    """{object name: reason} of the steps that are broken now, in document order (the first
    problem of each, see broken_problems for `signs` and `typed`)."""
    return {
        name: next(iter(found.values()))
        for name, found in broken_problems(doc, signs, typed).items()
    }


def broken_problems(doc, signs=None, typed=None):
    """{object name: {problem key: reason}} of the steps that are broken now: every problem
    of a step, so that a step already broken in one way (a sketch's dimension of 0 written
    before) still shows a new problem (review X2: one old problem hid every new one).
    `signs` (from signs_of): a horizontal/vertical sketch dimension whose sign is not the one
    it had has turned inside out (the profile flips), which breaks its sketch too. `typed`
    ({"Parameters.width": -5.0}): a value typed for a length parameter that FreeCAD held
    at 0 (a length is never negative to it), for the formulas that use it."""
    out = {}
    for obj in doc.Objects:
        if obj.TypeId in SKIP_TYPES:
            continue
        try:
            found = _problems(obj, signs, typed)
        except Exception:
            found = []
        if found:
            out[obj.Name] = dict(found)
    return out


def signs_of(doc):
    """{(sketch name, constraint index): +1/-1} of the horizontal/vertical dimensions."""
    out = {}
    for obj in doc.Objects:
        if obj.TypeId != "Sketcher::SketchObject":
            continue
        for i, c in enumerate(obj.Constraints):
            if c.Type in SIGNED and c.Driving and abs(c.Value) > 1e-7:
                out[(obj.Name, i)] = 1 if c.Value > 0 else -1
    return out


def _formula_value(obj, index, value, typed=None):
    """The value a sketch dimension's formula gives (FreeCAD stores 0 for a length whose
    formula gives less: the message says what it gave, with the values `typed`)."""
    import re

    expr = dict(obj.ExpressionEngine).get(".Constraints[%d]" % index)
    if not expr:
        return value
    for ref, number in (typed or {}).items():
        expr = re.sub(r"(?<![\w.])%s(?![\w])" % re.escape(ref), "(%r mm)" % number, expr)
    try:
        got = obj.evalExpression(expr)
        return float(got.Value) if hasattr(got, "Value") else float(got)
    except Exception:
        return value


def _broken(obj, signs=None, typed=None):
    found = _problems(obj, signs, typed)
    return found[0][1] if found else ""


def _problems(obj, signs=None, typed=None):
    """[(key, reason)] of what is broken in `obj`, the first being what _broken says."""
    from . import sketch_explain_core as explain_core

    if obj.TypeId == "App::VarSet":
        # a parameter whose formula cannot be computed (an unknown name): it keeps its old
        # value, and every dimension that uses it silently stops following
        out = []
        for prop, expr in dict(obj.ExpressionEngine).items():
            try:
                obj.evalExpression(expr)
            except Exception:
                reason = "the formula %s of %s cannot be computed (a name in it is unknown)" % (
                    core.from_freecad(expr),
                    prop.lstrip("."),
                )
                out.append((("formula", prop), reason))
        return out
    out = []
    if obj.TypeId == "Sketcher::SketchObject":
        from . import sketch_explain

        curve_names, _kinds = sketch_explain.names(obj)
        for i, c in enumerate(obj.Constraints):
            if not c.Driving or c.Type not in explain_core.LENGTHS:
                continue
            value = _formula_value(obj, i, c.Value, typed)
            # an offset between two points (a shape placed at the origin: 'g0.x' = 0) may be 0
            # and may change sides; a size may not (review X2)
            offset = explain_core.is_offset(c.Type, c.First, c.Second)
            flipped = (
                signs is not None
                and not offset
                and c.Type in SIGNED
                and (obj.Name, i) in signs
                and value * signs[(obj.Name, i)] < 0
            )
            if flipped or explain_core.bad_size(c.Type, value, offset):
                info = sketch_explain.constraint_info(obj, i, c)
                info["value"] = value
                out.append((("size", i), explain_core.bad_size_reason(info, curve_names)))
        conflicting = [i - 1 for i in obj.ConflictingConstraints]
        if conflicting:
            text, _count = sketch_explain.words(obj, conflicting)
            reason = "its constraints would conflict%s" % ((": " + text) if text else "")
            out.append((("conflict",), reason))
        if obj.MalformedConstraints:
            out.append((("malformed",), "its constraints would break"))
        for i, g in enumerate(obj.Geometry):
            if sketch_explain.collapsed(g):
                reason = "its %s would shrink to nothing" % curve_names.get(i, "curve")
                out.append((("collapsed", i), reason))
        if out:
            return out
    state = list(obj.State)
    if "Invalid" in state or "Error" in state:
        if obj.TypeId == "Sketcher::SketchObject":
            try:
                failed = "solving the sketch failed" in obj.getStatusString().lower()
            except Exception:
                failed = False
            if failed:  # the solver found no solution (no conflict list to name)
                return [(("state",), NO_FIT)]
        from . import timeline_ops

        _kind, reason = timeline_ops.problem(obj)
        return [(("state",), reason or "it could not be computed")]
    if obj.TypeId.startswith("PartDesign::") and obj.TypeId not in NOT_SOLID_STEPS:
        shape = getattr(obj, "Shape", None)
        if shape is not None and (shape.isNull() or shape.Volume < 1e-6):
            return [(("empty",), "its solid would be empty")]
    return []


# PartDesign objects that are no solid step (a solid step whose solid is empty is broken)
NOT_SOLID_STEPS = (
    "PartDesign::Plane",
    "PartDesign::Line",
    "PartDesign::Point",
    "PartDesign::CoordinateSystem",
    "PartDesign::ShapeBinder",
    "PartDesign::SubShapeBinder",
)



def _step_names(doc):
    """{object name: what the timeline calls it} ("Sketch 1", "Extrude 2")."""
    try:
        from . import timeline_ops

        return {item.name: item.display for item in timeline_ops.timeline(doc, deps=False).items}
    except Exception:
        return {}


def _snapshot(obj, path):
    """What `path` of `obj` holds now (its expressions and its value), to put it back."""
    expressions = dict(obj.ExpressionEngine)
    if path.startswith(".Constraints["):
        value = obj.getDatum(int(path[len(".Constraints[") : -1]))
    else:
        value = getattr(obj, path)
    return expressions, value


def _sketch_shots(doc):
    """{sketch name: its curves} of every sketch (sketch_geometry.snapshot), to put them
    back after a refused change: with the value back, the solver starts from where the
    change moved the curves, and a sketch that is not fully constrained stayed moved (a
    rectangle with only its width set came back shifted and twice as tall)."""
    from . import sketch_geometry

    shots = {}
    for obj in doc.Objects:
        if obj.TypeId == "Sketcher::SketchObject":
            try:
                shots[obj.Name] = sketch_geometry.snapshot(obj)
            except Exception:
                pass
    return shots


def _put_back_sketches(doc, shots):
    """Every sketch's curves where they were before the change (construction flags and ids
    kept); only sketches whose curves moved are touched."""
    from . import sketch_geometry

    for name, shot in shots.items():
        sketch = doc.getObject(name)
        if sketch is None or len(sketch.Geometry) != len(shot):
            continue
        try:
            if not sketch_geometry.moved(sketch, shot):
                continue
            sketch_geometry.restore(sketch, shot)
            sketch.touch()
        except Exception as exc:
            from . import warn

            warn("parameters: %s not put back as it was: %s" % (sketch.Label, exc))


def _put_back(obj, path, snapshot):
    expressions, value = snapshot
    now = dict(obj.ExpressionEngine)
    for key in now:
        if key not in expressions:
            obj.setExpression(key, None)
    for key, expr in expressions.items():
        if now.get(key) != expr:
            obj.setExpression(key, expr)
    if path in expressions:
        return  # its formula is back: the value follows it
    if path.startswith(".Constraints["):
        index = int(path[len(".Constraints[") : -1])
        try:
            obj.setDatum(index, value)
        except Exception:
            # the sketch cannot solve until the value is back: through a formula, which
            # sets the value without asking the solver first, then the formula goes again
            obj.setExpression(path, str(value))
            obj.recompute()
            obj.setExpression(path, None)
    else:
        setattr(obj, path, value)


# a sketch whose solver finds no solution with the new value (no conflict list to name)
NO_FIT = "that value does not fit its other dimensions and constraints"

# FreeCAD's setDatum words for a value its solver cannot take (SketchObjectPyImp.cpp): -1 no
# solution ("Invalid constraint index", the index itself is valid here), -2 redundant, -3
# conflicting, -4 over-constrained or negative ("Negative datum"), -5 zero
SOLVER_WORDS = (
    "invalid constraint index",
    "is invalid",
    "conflicting constraints",
    "negative datum",
    "zero is not a valid datum",
)


def _solver_refusal(obj, path, exc, what):
    """Why the sketch could not take a typed dimension value (setDatum raised), in words:
    a size of 0 or less, what it conflicts with, or that it does not fit. "" when `exc` is
    something else (a formula FreeCAD cannot read)."""
    if obj.TypeId != "Sketcher::SketchObject" or not path.startswith(".Constraints["):
        return ""
    if not any(w in str(exc).lower() for w in SOLVER_WORDS):
        return ""
    from . import sketch_explain
    from . import sketch_explain_core as explain_core

    index = int(path[len(".Constraints[") : -1])
    c = obj.Constraints[index]
    typed = _typed_number(what)
    if typed is not None and c.Type in explain_core.LENGTHS and typed <= 1e-7:
        info = sketch_explain.constraint_info(obj, index, c)
        info["value"] = typed
        curve_names, _kinds = sketch_explain.names(obj)
        return explain_core.bad_size_reason(info, curve_names)
    try:
        # FreeCAD's failed solve still knows what fought the value
        culprits = sketch_explain.conflict_culprits(obj, [index])
        text, _count = sketch_explain.words(obj, culprits)
    except Exception:
        text = ""
    if text:
        return "that value conflicts with %s" % text
    return NO_FIT


def _typed_number(what):
    """The plain number typed in a change named "width = -5" (None for a formula)."""
    if " = " not in what:
        return None
    text = what.split(" = ", 1)[1]
    if not is_plain_number(text):
        return None
    try:
        return App.Units.Quantity(text).Value
    except Exception:
        return None


def _held_back(obj, path, what):
    """{"Parameters.width": -5.0} when the number typed for a length parameter is not what it
    holds now (FreeCAD keeps a length at 0 or more), else {}."""
    try:
        if obj.TypeId != "App::VarSet" or path in dict(obj.ExpressionEngine):
            return {}
        number = _typed_number(what)
        held = getattr(obj, path)
        held = held.Value if hasattr(held, "Value") else float(held)
        if number is not None and abs(number - held) > 1e-9:
            return {"%s.%s" % (obj.Name, path): number}
    except Exception:
        pass
    return {}


def change_checked(doc, obj, path, apply, what):
    """Make a parameter change (`apply()`), recompute, and take it back when it breaks a step
    that was fine before. `obj`/`path`: the property `apply` changes (a user parameter: the
    Parameters container and its name; a model parameter: the object and its path); `what`
    names the change in the message ("width = 5 mm"). Returns "" when the change stands, else
    the message (and the design is as it was)."""
    from . import log
    from . import sketch_explain_core as explain_core

    before = broken_problems(doc)
    signs = signs_of(doc)
    snapshot = _snapshot(obj, path)
    shots = _sketch_shots(doc)
    try:
        apply()
    except Exception as exc:
        # refused half-way (a formula FreeCAD cannot read, a value the sketch's solver cannot
        # reach): what it did is put back too
        reason = _solver_refusal(obj, path, exc, what)
        try:
            _put_back(obj, path, snapshot)
            _put_back_sketches(doc, shots)
        except Exception:
            pass
        if not reason:
            raise
        doc.recompute()
        labels = _step_names(doc)
        problem = (labels.get(obj.Name) or obj.Label, reason)
        log("parameters: refused %s: %s: %s" % (what, problem[0], reason))
        return explain_core.parameter_refusal(what, [problem])
    doc.recompute()
    new = []
    after = broken_problems(doc, signs, _held_back(obj, path, what))
    for name, found in after.items():
        fresh = [reason for key, reason in found.items() if key not in before.get(name, {})]
        if fresh:
            new.append((name, fresh[0]))
    if not new:
        return ""
    labels = _step_names(doc)
    problems = []
    for name, reason in new:
        found = doc.getObject(name)
        problems.append((labels.get(name) or (found.Label if found else name), reason))
    message = explain_core.parameter_refusal(what, problems)
    log("parameters: refused %s: %s" % (what, "; ".join("%s: %s" % p for p in problems)))
    _put_back(obj, path, snapshot)
    _put_back_sketches(doc, shots)  # (the recompute then solves them from where they were)
    doc.recompute()
    return message
