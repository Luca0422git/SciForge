# SPDX-License-Identifier: LGPL-2.1-or-later
"""The two lists of Fusion's Sheet Metal Rules dialog, without Qt (sheetmetal_rules_ui.py
shows them; the golden builder and tests call the same functions):

- **In This Design**: the rules kept in the design (sheetmetal.py's store). Editing one
  recomputes every sheet metal body that follows it; a rule in use, or the last one, cannot
  be deleted; renaming one renames it on every body and component that follows it.
- **Library**: SciForge's built-in rules (sheetmetal_core.LIBRARY, read-only: Fusion keeps its
  default rule) plus the user's own rules, kept in the user's preferences (shared by every
  design on this computer, like Fusion's per-user library).
"""

import json

import FreeCAD as App

from . import log, sheetmetal, warn
from . import sheetmetal_core as core

PREFS = "User parameter:BaseApp/Preferences/Mod/SciForge/SheetMetal"


# -- the library ---------------------------------------------------------------------------------
def _prefs():
    return App.ParamGet(PREFS)


def user_library():
    """The user's own library rules (dicts)."""
    try:
        rules = json.loads(_prefs().GetString("Library", "[]") or "[]")
        return [r for r in rules if isinstance(r, dict) and r.get("name")]
    except Exception as exc:
        warn("sheet metal library unreadable: %s" % exc)
        return []


def _write_user_library(rules):
    _prefs().SetString("Library", json.dumps(rules))


def is_builtin(name):
    return core.library_rule(name) is not None


def library_rules():
    """Built-in rules first, then the user's own."""
    rules = [dict(r) for r in core.LIBRARY]
    names = {r["name"] for r in rules}
    rules += [dict(r) for r in user_library() if r["name"] not in names]
    return rules


def find_library_rule(name):
    for rule in library_rules():
        if rule["name"] == name:
            return dict(rule)
    return None


def save_library_rule(rule, old_name=None):
    """Add or change one of the user's library rules (built-in ones stay as shipped)."""
    problems = core.validate(rule)
    if problems:
        raise ValueError(problems[0])
    if is_builtin(rule["name"]) or (old_name and is_builtin(old_name)):
        raise ValueError(
            "'%s' is one of SciForge's built-in rules: copy it (New) to make your own"
            % (old_name or rule["name"])
        )
    taken = [r["name"] for r in library_rules() if r["name"] != (old_name or rule["name"])]
    problem = core.check_name(rule["name"], taken)
    if problem:
        raise ValueError(problem)
    rules = [r for r in user_library() if r["name"] not in (old_name, rule["name"])]
    rules.append(dict(rule))
    _write_user_library(rules)
    log("sheet metal library rule '%s' saved" % rule["name"])


def delete_library_rule(name):
    if is_builtin(name):
        raise ValueError("'%s' is one of SciForge's built-in rules and cannot be deleted" % name)
    _write_user_library([r for r in user_library() if r["name"] != name])


# -- In This Design ---------------------------------------------------------------------------
def in_use(doc, name):
    """Labels of the bodies following the rule."""
    return [
        b.Label for b in sheetmetal.sheet_metal_bodies(doc) if sheetmetal.body_rule_name(b) == name
    ]


def save_design_rule(doc, rule, old_name=None):
    """Add or change a rule In This Design; a new name renames it everywhere it is used. The
    caller recomputes (every body following it changes)."""
    problems = core.validate(rule)
    if problems:
        raise ValueError(problems[0])
    names = [r["name"] for r in sheetmetal.design_rules(doc)]
    taken = [n for n in names if n != (old_name or rule["name"])]
    problem = core.check_name(rule["name"], taken)
    if problem:
        raise ValueError(problem)
    sheetmetal.save_rule(doc, rule)
    if old_name and old_name != rule["name"]:
        for body in sheetmetal.sheet_metal_bodies(doc):
            if sheetmetal.body_rule_name(body) == old_name:
                setattr(body, sheetmetal.RULE_PROP, rule["name"])
                for feature in body.Group:
                    try:
                        feature.touch()
                    except Exception:
                        pass
        for obj in doc.Objects:
            if getattr(obj, sheetmetal.RULE_PROP, None) == old_name and obj.TypeId == "App::Part":
                setattr(obj, sheetmetal.RULE_PROP, rule["name"])
        store = sheetmetal.rules_object(doc)
        if store is not None and store.ActiveRule == old_name:
            store.ActiveRule = rule["name"]
        sheetmetal.delete_rule(doc, old_name)


def delete_design_rule(doc, name):
    """Remove a rule from the design: refused while a body follows it, for the active rule
    and for the last rule (a design keeps one)."""
    users = in_use(doc, name)
    if users:
        raise ValueError(
            "'%s' is used by %s: give those bodies another rule first" % (name, ", ".join(users))
        )
    rules = sheetmetal.design_rules(doc)
    if len(rules) <= 1:
        raise ValueError("A design keeps at least one rule.")
    if sheetmetal.active_rule_name(doc) == name:
        raise ValueError("'%s' is the active rule: make another rule active first." % name)
    sheetmetal.delete_rule(doc, name)


def copy_to_design(doc, name):
    """A library rule copied into the design (a new name when the design has one by that
    name). Returns the name it got."""
    rule = find_library_rule(name)
    if rule is None:
        raise ValueError("No library rule named '%s'." % name)
    taken = [r["name"] for r in sheetmetal.design_rules(doc)]
    rule["name"] = core.unique_name(rule["name"], taken)
    sheetmetal.save_rule(doc, rule)
    return rule["name"]


def copy_to_library(doc, name):
    """A design rule copied into the user's library. Returns the name it got."""
    rule = sheetmetal.find_rule(doc, name)
    if rule is None:
        raise ValueError("No rule named '%s' in this design." % name)
    rule["name"] = core.unique_name(rule["name"], [r["name"] for r in library_rules()])
    save_library_rule(rule)
    return rule["name"]


def new_rule_from(rule, taken):
    """Fusion's New Rule: a copy of `rule` (its units stay) with a free name."""
    base = dict(rule)
    base["name"] = core.unique_name(rule["name"], taken)
    return base


def set_body_rule(body, name):
    """Give a sheet metal body another rule of the design (Fusion swaps rules, never detaches
    them). The caller recomputes."""
    doc = body.Document
    if sheetmetal.find_rule(doc, name) is None:
        copy_to_design(doc, name)
    setattr(body, sheetmetal.RULE_PROP, name)
    for feature in body.Group:
        try:
            feature.touch()
        except Exception:
            pass
