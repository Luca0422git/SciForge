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
DIMENSION_TYPES = {"Distance", "DistanceX", "DistanceY", "Radius", "Diameter", "Angle"}


def container(doc, create=False):
    obj = doc.getObject(core.CONTAINER)
    if obj is None and create:
        obj = doc.addObject("App::VarSet", core.CONTAINER)
        obj.Label = "Parameters"
    return obj


def user_names(doc):
    obj = container(doc)
    if obj is None:
        return []
    return [p for p in obj.PropertiesList if obj.getGroupOfProperty(p) == GROUP]


def user_parameters(doc):
    """[{name, unit, expression, value, comment}] in creation order."""
    obj = container(doc)
    rows = []
    if obj is None:
        return rows
    expressions = dict(obj.ExpressionEngine)
    for name in user_names(doc):
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
    users = _users_of(doc, name)
    if users:
        raise core.ParameterError(
            "'%s' is used by: %s. Change those first." % (name, ", ".join(users))
        )
    container(doc).removeProperty(name)


def _users_of(doc, name):
    needle = "%s.%s" % (core.CONTAINER, name)
    found = []
    for obj in doc.Objects:
        for _path, expr in obj.ExpressionEngine:
            if needle in expr or ("<<%s>>.%s" % (core.CONTAINER, name)) in expr:
                found.append(obj.Label)
                break
    return found


def set_user(doc, name, text):
    """A number ('25', '25 mm') or an expression ('width / 2')."""
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
        elif getattr(obj, "SciForgeType", "") == "PressPull":
            rows.append(
                _row(obj, "Distance", "Distance", obj.Distance, expressions.get("Distance", ""))
            )
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
