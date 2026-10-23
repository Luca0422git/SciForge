# SPDX-License-Identifier: LGPL-2.1-or-later
"""The largest value that fits, told to an AI whose value does not fit.

In the dialogs a fillet radius, chamfer distance, draft angle, shell thickness... dragged or
typed past what fits stops at the largest value that works (sciforge/value_limits.py, Luca's
decision of 2026-10-21). An AI tool call is different: the agent asked for an exact value, so
SciForge never builds a smaller one in its place. The call fails, as before, and the answer
now says the largest value that does fit ("Largest radius that fits here: 3.47 mm"), found
with the same bisection the dialogs use (value_limits.search: time budgeted, rounded toward
the safe side to a tidy value and built once more to be sure). The agent decides what to do
with it.

Which values: the ones the dialogs hold (the audit in docs/sciforge/sessions/
2026-10-21-limits.md) whose safe side is toward 0: fillet / rule fillet radius, chamfer
distances, fillet sets' sizes, shell thicknesses, draft angles, press pull distance, extrude
taper and thin wall, surface thicken, torus tube, coil section / taper, pipe section /
wall, gear bore / root fillet / backlash.

Pure Python: the executor passes `trial(args) -> bool` (build the same call with these
arguments in a transaction that is then taken back). Unit tested in SciForgeTests/unit.
"""

import copy
import time

from .. import value_limits

BUDGET = 3.0  # seconds the whole search may take, every try counted (the dialogs: 1.5 s)

# tool -> [(path into the arguments, words for the value, unit)]; "*" in a path: every item
# of a list (fillet_sets' sets).
LIMITED = {
    "fillet": [(("radius",), "radius", "mm")],
    "rule_fillet": [(("radius",), "radius", "mm")],
    "chamfer": [(("distance",), "distance", "mm"), (("distance2",), "second distance", "mm")],
    "fillet_sets": [
        (("sets", "*", "radius"), "radius", "mm"),
        (("sets", "*", "chord"), "chord length", "mm"),
        (("sets", "*", "start"), "start radius", "mm"),
        (("sets", "*", "end"), "end radius", "mm"),
        (("sets", "*", "distance"), "distance", "mm"),
        (("sets", "*", "distance2"), "second distance", "mm"),
    ],
    "shell": [
        (("thickness",), "thickness", "mm"),
        (("inside",), "inside thickness", "mm"),
        (("outside",), "outside thickness", "mm"),
    ],
    "draft": [(("angle",), "angle", "deg"), (("angle2",), "second angle", "deg")],
    "press_pull": [(("distance",), "distance", "mm")],
    "extrude": [
        (("taper",), "taper angle", "deg"),
        (("taper2",), "side two's taper angle", "deg"),
        (("thin", "thickness"), "wall thickness", "mm"),
    ],
    "surface": [(("options", "thickness"), "thickness", "mm")],
    "primitive": [(("torus_diameter",), "tube diameter", "mm")],
    "coil": [(("section_size",), "section size", "mm"), (("angle",), "taper angle", "deg")],
    "pipe": [(("thickness",), "wall thickness", "mm"), (("section_size",), "section size", "mm")],
    "gear": [
        (("hole",), "bore diameter", "mm"),
        (("fillet",), "root fillet", "mm"),
        (("backlash",), "backlash", "mm"),
    ],
}


# words for an option name (edit_step's set keys)
WORDS = {
    "inside": "inside thickness",
    "outside": "outside thickness",
    "distance2": "second distance",
    "size2": "second distance",
    "angle2": "second angle",
    "taper": "taper angle",
    "taper2": "side two's taper angle",
    "chord": "chord length",
    "start": "start radius",
    "end": "end radius",
    "torus_diameter": "tube diameter",
    "section_size": "section size",
    "hole": "bore diameter",
    "fillet": "root fillet",
}


def words_for(key):
    return WORDS.get(key.lower(), key.lower().replace("_", " "))


def candidates(tool, args):
    """[(path, words, unit, value)] of the limited values this call gives (not 0), in the
    order they are tried. A value written as a formula ("expressions") is left alone, as the
    dialogs leave a formula alone."""
    out = []
    formulas = (args or {}).get("expressions") or {}
    for path, words, unit in LIMITED.get(tool, ()):
        for full in _expand(args, path):
            value = _get(args, full)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value == 0:
                continue
            if full[-1] in formulas:
                continue
            out.append((full, words, unit, float(value)))
    if tool == "surface" and (args or {}).get("kind") != "thicken":
        return []
    return out


def _expand(args, path):
    if "*" not in path:
        return [path]
    at = path.index("*")
    items = _get(args, path[:at])
    if not isinstance(items, list):
        return []
    out = []
    for n in range(len(items)):
        out += _expand(args, path[:at] + (n,) + path[at + 1 :])
    return out


def _get(args, path):
    value = args
    for key in path:
        try:
            value = value[key]
        except (KeyError, IndexError, TypeError):
            return None
    return value


def with_value(args, path, value):
    """A copy of the arguments with the value at `path` replaced."""
    out = copy.deepcopy(args)
    target = out
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return out


# A step FreeCAD could not compute says no more than that ("failed to compute: Invalid"); for
# a call with a size value a smaller one may cure it, so the search is tried (it stops after
# one build when even the smallest value fails).
COMPUTE_FAILED = ("failed to compute",)


def is_limit(text):
    """True when a refusal is of the kind a smaller value can cure (value_limits' words, or
    a step that failed to compute)."""
    low = (text or "").lower()
    return value_limits.is_limit_error(text) or any(w in low for w in COMPUTE_FAILED)


def largest(tool, args, trial, budget=BUDGET, per_try=0.0, clock=None):
    """The sentence to add to the refusal of a call whose value does not fit: "Largest radius
    that fits here: 3.47 mm ...", or "" when no smaller value of its limited values works
    (then the refusal is not about a size). `trial(args)` builds the call with these
    arguments and says whether it worked; it never keeps what it built.
    `budget` bounds the whole search, every try counted (each try rebuilds the design: on a
    medium design the search took 12-23 s, review X3); `per_try`: how long the refused call
    took, the first estimate of a try. When not even two tries fit in the budget, nothing is
    tried and the sentence says why (too_slow)."""
    found = candidates(tool, args)
    return search_sentence(
        [
            (lambda v, p=path: trial(with_value(args, p, v)), words, unit, value, _name(path))
            for path, words, unit, value in found
        ],
        budget,
        per_try,
        clock,
    )


def search_sentence(items, budget=BUDGET, per_try=0.0, clock=None):
    """largest() for [(trial(value), words, unit, value, argument name)]: one time budget
    for them all (value_limits.search, strict)."""
    clock = clock or time.perf_counter
    begun = clock()
    slowest = [max(float(per_try or 0.0), 0.0)]

    def timed(try_value):
        def run(value):
            t0 = clock()
            try:
                return try_value(value)
            finally:
                slowest[0] = max(slowest[0], clock() - t0)

        return run

    for try_value, words, unit, value, name in items:
        step = value_limits.step_for(unit)
        good = step if value > 0 else -step
        if abs(value) <= step:
            continue
        left = budget - (clock() - begun)
        if slowest[0] * 2 > left:
            return too_slow(words, unit, value, slowest[0])
        limit, exact = value_limits.search(
            timed(try_value),
            good,
            value,
            step,
            budget=left,
            clock=clock,
            strict=True,
            per_try=slowest[0],
        )
        if limit is None:
            continue
        if not exact and abs(limit - good) < 1e-12:
            return too_slow(words, unit, value, slowest[0])  # (no try got past the smallest)
        return sentence(words, unit, value, limit, exact, name)
    return ""


def too_slow(words, unit, value, per_try):
    """The sentence when the search would take too long: each try rebuilds the design."""
    side = "largest" if value > 0 else "furthest"
    return (
        " SciForge did not search for the %s %s that fits: every try rebuilds this design "
        "(about %s), more than its time limit allows. Try a smaller %s (%s does not fit)."
        % (side, words, _seconds(per_try), words, value_limits.fmt_typed(value, unit))
    )


def _seconds(value):
    return "%.0f s" % value if value >= 1.5 else "%.1f s" % value


def _name(path):
    """The argument as an AI writes it: radius, thin.thickness, sets[1].radius."""
    out = ""
    for key in path:
        if isinstance(key, int):
            out += "[%d]" % key
        else:
            out += ("." if out else "") + key
    return out


def sentence(words, unit, value, limit, exact=True, name=None):
    """Largest radius that fits here: 3.47 mm (...)."""
    side = "hi" if value > 0 else "lo"
    word = "Largest" if side == "hi" else "Furthest"
    shown = value_limits.fmt(limit, unit)
    asked = value_limits.fmt_typed(value, unit)
    arg = name or words
    if exact:
        how = "SciForge did not build a smaller value in its place: give %s %s or less" % (
            arg,
            _plain(limit, unit),
        )
        if side == "lo":
            how = "SciForge did not build another value in its place: give %s between %s and 0" % (
                arg,
                _plain(limit, unit),
            )
        return " %s %s that fits here: %s (%s does not; %s)." % (word, words, shown, asked, how)
    return (
        " %s %s found that fits here: %s (%s does not; the search stopped at its time limit, so "
        "a little more may fit; SciForge did not build a smaller value in its place)."
        % (word, words, shown, asked)
    )


def _plain(value, unit):
    text = value_limits.fmt(value, unit)
    return text.replace("°", "").replace(" mm", "")
