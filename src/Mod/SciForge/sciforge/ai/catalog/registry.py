# SPDX-License-Identifier: LGPL-2.1-or-later
"""The list every AI tool is entered in (catalog/__init__.py explains what reads it).

define() makes one entry. A tool either becomes design steps (the JSON language of the
golden models, built by sciforge/ai/ops: give op= for the plain case, steps= for a mapping
of its own) or is an action the executor does itself (sciforge/ai/actions). Pure Python.
"""

import copy

from . import kit

TOOLS = []
BY_NAME = {}

# (key, title) in the order the documentation and list_tools show them.
CATEGORIES = (
    ("help", "Help"),
    ("document", "Designs and files"),
    ("inspect", "Inspect and measure"),
    ("sketch", "Sketch"),
    ("create", "Create (SOLID)"),
    ("modify", "Modify"),
    ("surface", "Surface"),
    ("construct", "Construct"),
    ("assemble", "Assemble"),
    ("timeline", "Timeline (history)"),
    ("parameters", "Parameters"),
    ("import_export", "Import and export"),
    ("drawing", "Drawings"),
    ("view", "View"),
)
CATEGORY_KEYS = tuple(c[0] for c in CATEGORIES)

# What a tool needs before it can run (catalog.availability says why not, in a sentence).
NEEDS = {
    "design": "No design is open: call new_design or open_design first (or create_sketch, "
    "which starts a new design).",
    "solid": "The design has no solid body yet: make one first (create_sketch + extrude, or "
    "primitive).",
    "gui": "This needs the SciForge window, and SciForge is running without one (headless / "
    "command line).",
    "drawing": "The design has no drawing yet: call create_drawing first.",
}


def _plain_steps(op, with_id=True):
    def steps(args, step_id):
        step = {"op": op}
        if step_id is not None and with_id:
            step["id"] = step_id
        step.update(copy.deepcopy(args or {}))
        return [step]

    return steps


def define(
    name,
    title,
    category,
    ribbon,
    description,
    input_schema,
    *,
    changes=True,
    writes_files=False,
    confirm_overwrite=False,
    destructive=False,
    op=None,
    ops=None,
    steps=None,
    extra=None,
    selectors=None,
    examples=(),
    needs=None,
    id_base=None,
    title_fn=None,
    core=False,
    own_id=True,
):
    """Enter a tool in the catalogue and return its entry.

    ribbon: where the command sits in Fusion ("SOLID > CREATE > Extrude"); op / ops: the
    design step(s) it builds (ops lists every op the tool can emit); steps(args, step_id):
    the mapping when it is not one plain op; extra(args, problems): the rules a schema cannot
    say; selectors {argument: "faces" | "edges"}: top-level arguments checked as selectors;
    needs: what must exist first ("design", "solid", "gui", "drawing"); id_base: how the
    new step's id starts ("Extrude" -> Extrude1); title_fn(args): its Undo / timeline title
    ("AI: Extrude 10 mm"); core: offered first where an AI app takes only some tools;
    own_id: the step made gets a new id (False: the tool changes something that exists)."""
    if name in BY_NAME:
        raise ValueError("tool %r defined twice" % name)
    if category not in CATEGORY_KEYS:
        raise ValueError("tool %r: unknown category %r" % (name, category))
    if op is not None and steps is None:
        steps = _plain_steps(op, own_id)
    if ops is None:
        ops = [op] if op else []
    if needs is None:
        needs = ("design",)
    entry = {
        "name": name,
        "title": title,
        "category": category,
        "ribbon": ribbon,
        "description": description,
        "input_schema": input_schema,
        "changes_design": bool(changes),
        "writes_files": bool(writes_files),
        "confirm_overwrite": bool(confirm_overwrite),
        "destructive": bool(destructive),
        "ops": list(ops),
        "kind": "steps" if steps is not None else "action",
        "examples": [copy.deepcopy(e) for e in examples],
        "needs": tuple(needs),
        "id_base": id_base or "".join(w.capitalize() for w in name.split("_")),
        "core": bool(core),
        "own_id": bool(own_id),
        "_steps": steps,
        "_extra": extra,
        "_selectors": dict(selectors or {}),
        "_title": title_fn,
    }
    for need in entry["needs"]:
        if need not in NEEDS:
            raise ValueError("tool %r: unknown need %r" % (name, need))
    TOOLS.append(entry)
    BY_NAME[name] = entry
    return entry


def example(args, note):
    """One example call for the documentation: the arguments and what they do."""
    return {"arguments": args, "note": note}


def is_read_only(entry):
    return not (entry["changes_design"] or entry["writes_files"])


def mm(args, key):
    value = (args or {}).get(key)
    return " %s mm" % kit.fmt(value) if kit.is_type(value, "number") else ""
