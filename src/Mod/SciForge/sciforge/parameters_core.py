# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion-style parameter names in expressions. Pure Python, unit tested.

In Fusion you write `width * 2`. FreeCAD needs `Parameters.width * 2` (the
user parameters live in an App::VarSet object named "Parameters"). These
helpers translate between the two, leaving units, functions and other
objects' properties alone.
"""
import keyword
import re

CONTAINER = "Parameters"
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# Words that are units or functions in FreeCAD expressions, so not parameter names.
RESERVED = {
    "mm",
    "cm",
    "m",
    "km",
    "um",
    "nm",
    "in",
    "ft",
    "thou",
    "mil",
    "yd",
    "mi",
    "deg",
    "rad",
    "gon",
    "g",
    "kg",
    "s",
    "min",
    "h",
    "N",
    "Pa",
    "pi",
    "e",
    "abs",
    "acos",
    "asin",
    "atan",
    "atan2",
    "ceil",
    "cos",
    "cosh",
    "exp",
    "floor",
    "log",
    "log10",
    "mod",
    "pow",
    "round",
    "sin",
    "sinh",
    "sqrt",
    "tan",
    "tanh",
    "trunc",
    "min",
    "max",
    "sum",
    "average",
    "count",
    "stddev",
    "create",
    "list",
    "tuple",
    "vector",
    "matrix",
    "rotation",
    "placement",
    "str",
    "hiddenref",
    "href",
}


class ParameterError(ValueError):
    pass


def check_name(name, existing=()):
    """Raise ParameterError unless `name` can be a parameter name."""
    if not name or not _IDENT.fullmatch(name):
        raise ParameterError(
            "'%s' is not a valid name: use letters, digits and _, " "starting with a letter." % name
        )
    if keyword.iskeyword(name) or name in RESERVED:
        raise ParameterError("'%s' is a unit or function name; pick another name." % name)
    if name in existing:
        raise ParameterError("A parameter named '%s' already exists." % name)
    return name


def _replace(expr, fn):
    """Apply fn(identifier) to identifiers that are bare names (not after '.',
    not a function call, not inside quotes)."""
    out = []
    i = 0
    while i < len(expr):
        ch = expr[i]
        if ch in "'\"":
            end = expr.find(ch, i + 1)
            end = len(expr) if end < 0 else end + 1
            out.append(expr[i:end])
            i = end
            continue
        match = _IDENT.match(expr, i)
        if match and (i == 0 or not (expr[i - 1].isalnum() or expr[i - 1] in "_.")):
            word = match.group(0)
            after = expr[match.end() :].lstrip()
            if after.startswith("(") or after.startswith("."):
                out.append(word)  # a function call or another object's property
            else:
                out.append(fn(word))
            i = match.end()
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def to_freecad(expr, names):
    """'width * 2' -> 'Parameters.width * 2' for the given parameter names."""
    names = set(names)
    return _replace(expr, lambda w: "%s.%s" % (CONTAINER, w) if w in names else w)


def from_freecad(expr):
    """'Parameters.width * 2' -> 'width * 2' (what the user typed)."""
    return re.sub(
        r"(?<![A-Za-z0-9_.])(?:<<%s>>|%s)\.([A-Za-z_][A-Za-z0-9_]*)" % (CONTAINER, CONTAINER),
        r"\1",
        expr,
    )


UNITS = {"mm": "App::PropertyLength", "deg": "App::PropertyAngle", "": "App::PropertyFloat"}


def property_type(unit):
    if unit not in UNITS:
        raise ParameterError("Unit must be one of: mm, deg, or empty (no unit).")
    return UNITS[unit]


def unit_of(property_type):
    for unit, kind in UNITS.items():
        if kind == property_type:
            return unit
    return ""
