# SPDX-License-Identifier: LGPL-2.1-or-later
"""Where a design keeps its sheet metal rules, and which bodies are sheet metal (FreeCAD,
no Qt: the golden-model builder, headless tests and the dialogs all use this).

The contract of the SHEET METAL builders (wave 6; extend it, never rename or remove):

- A design's rules live in one hidden ``App::FeaturePython`` named ``SheetMetalRules``
  (``RulesJson``: a JSON list of rule dicts, sheetmetal_core.FIELDS; ``ActiveRule``: the
  rule new sheet metal in the root component gets). A design that never used sheet metal has
  no such object; it is made on first use with the library's default rule in it (Fusion: a
  design starts with the default rule "In This Design").
- Copying objects that link the store (Insert a design, Paste New) brings a copy of it under
  another name (``SheetMetalRules001``...): its rules count as the design's too (QA, wave 6).
- A component (``App::Part``) may carry ``SciForgeSheetMetalRule``: its active rule (Fusion
  keeps the active rule per component). The root component's is ``ActiveRule`` above.
- A **sheet metal body** is a ``PartDesign::Body`` with a non-empty
  ``SciForgeSheetMetalRule`` property: the name of the rule it follows. Its solid is made of
  flat walls and cylindrical bends of the rule's thickness (what the unfolder reads).

    rules_object(doc, create=False)    the store, made on demand
    design_rules(doc)                  the rules "In This Design" (dicts, as stored)
    find_rule(doc, name)               one of them, or None
    save_rule(doc, rule)               add or replace by name; recomputes bodies that use it
    delete_rule(doc, name)             refused (ValueError) while a body uses it
    active_rule_name(doc, component)   the component's active rule (root: None)
    set_active_rule(doc, name, component)
    is_sheet_metal_body(body)
    make_sheet_metal_body(body, rule_name)
    body_rule_name(body)
    rule_for_body(body)                the body's rule, evaluated (lengths in mm, floats)
    sheet_metal_bodies(doc)
    find_sheet_body(doc, active, component)   the body a SHEET METAL tool works on (or None)
"""

import json

from . import bodies, log, sheetmetal_core as core, warn

STORE_NAME = "SheetMetalRules"
RULE_PROP = "SciForgeSheetMetalRule"


def rules_object(doc, create=False):
    """The design's rule store, or None. create=True makes it (with the default rule)."""
    if doc is None:
        return None
    obj = doc.getObject(STORE_NAME)
    if obj is not None or not create:
        return obj
    obj = doc.addObject("App::FeaturePython", STORE_NAME)
    obj.Label = "Sheet Metal Rules"
    obj.addProperty("App::PropertyString", "RulesJson", "SheetMetal", "The design's rules")
    obj.addProperty("App::PropertyString", "ActiveRule", "SheetMetal", "Root component's rule")
    obj.RulesJson = json.dumps([core.library_rule(core.DEFAULT_RULE)])
    obj.ActiveRule = core.DEFAULT_RULE
    for prop in ("RulesJson", "ActiveRule"):
        try:
            obj.setEditorMode(prop, 2)
        except Exception:
            pass
    try:
        view = obj.ViewObject
        if view is not None:
            view.ShowInTree = False
    except Exception:
        pass
    return obj


def _stray_stores(doc):
    """Rule stores that came in with copied objects: FreeCAD copies the store a flange links
    (Insert a design, Paste New of a component) under another name (SheetMetalRules001...).
    Their rules belong to the design too (the inserted parts follow them)."""
    found = []
    for obj in doc.Objects:
        if (
            obj.Name != STORE_NAME
            and obj.Name.startswith(STORE_NAME)
            and obj.TypeId == "App::FeaturePython"
            and "RulesJson" in obj.PropertiesList
        ):
            found.append(obj)
    return found


def _stored(obj):
    rules = json.loads(obj.RulesJson or "[]")
    return [r for r in rules if isinstance(r, dict) and r.get("name")]


def design_rules(doc):
    """The rules In This Design: the store's, then those only a copied store has (an
    inserted design's own rules; the next save_rule keeps them in the store)."""
    obj = rules_object(doc)
    rules = [core.library_rule(core.DEFAULT_RULE)]
    if obj is not None:
        try:
            rules = _stored(obj)
        except Exception as exc:
            warn("sheet metal rules of %s unreadable: %s" % (doc.Name, exc))
    names = {r["name"] for r in rules}
    for stray in _stray_stores(doc):
        try:
            extra = _stored(stray)
        except Exception:
            continue
        for rule in extra:
            if rule["name"] not in names:
                rules.append(rule)
                names.add(rule["name"])
    return rules


def find_rule(doc, name):
    for rule in design_rules(doc):
        if rule["name"] == name:
            return dict(rule)
    return None


def _uses(doc, name):
    return [b for b in sheet_metal_bodies(doc) if body_rule_name(b) == name]


def save_rule(doc, rule):
    """Add the rule to the design or replace the one with its name. The bodies that follow it
    are marked to recompute (their steps read rule_for_body when they run)."""
    problems = core.validate(rule)
    if problems:
        raise ValueError(problems[0])
    obj = rules_object(doc, create=True)
    rules = [r for r in design_rules(doc) if r["name"] != rule["name"]]
    rules.append(dict(rule))
    obj.RulesJson = json.dumps(rules)
    for body in _uses(doc, rule["name"]):
        for feature in getattr(body, "Group", []):
            try:
                feature.touch()
            except Exception:
                pass
    log("sheet metal rule '%s' saved" % rule["name"])


def delete_rule(doc, name):
    users = _uses(doc, name)
    if users:
        raise ValueError(
            "'%s' is used by %s; give those bodies another rule first"
            % (name, ", ".join(b.Label for b in users))
        )
    obj = rules_object(doc)
    if obj is None:
        return
    obj.RulesJson = json.dumps([r for r in design_rules(doc) if r["name"] != name])
    for stray in _stray_stores(doc):
        try:
            kept = [r for r in _stored(stray) if r["name"] != name]
            if len(kept) != len(_stored(stray)):
                stray.RulesJson = json.dumps(kept)
        except Exception:
            pass


def active_rule_name(doc, component=None):
    if component is not None and getattr(component, RULE_PROP, ""):
        return getattr(component, RULE_PROP)
    obj = rules_object(doc)
    if obj is not None and obj.ActiveRule:
        return obj.ActiveRule
    return core.DEFAULT_RULE


def set_active_rule(doc, name, component=None):
    if component is not None:
        if not hasattr(component, RULE_PROP):
            component.addProperty("App::PropertyString", RULE_PROP, "SheetMetal", "Active rule")
        setattr(component, RULE_PROP, name)
        return
    rules_object(doc, create=True).ActiveRule = name


def is_sheet_metal_body(body):
    return bodies.is_body(body) and bool(getattr(body, RULE_PROP, ""))


def body_rule_name(body):
    return getattr(body, RULE_PROP, "") if body is not None else ""


def make_sheet_metal_body(body, rule_name):
    """Flag the body as sheet metal following rule_name (copied into the design from the
    library when the design does not have it yet)."""
    doc = body.Document
    if rules_object(doc) is None:
        # the design keeps its own copy of its rules (a later library change leaves it alone)
        rules_object(doc, create=True)
    if find_rule(doc, rule_name) is None:
        rule = core.library_rule(rule_name)
        if rule is None:
            raise ValueError("no sheet metal rule named '%s'" % rule_name)
        save_rule(doc, rule)
    if not hasattr(body, RULE_PROP):
        body.addProperty("App::PropertyString", RULE_PROP, "SheetMetal", "Sheet metal rule")
    setattr(body, RULE_PROP, rule_name)


def rule_for_body(body):
    """The body's rule with lengths in mm (sheetmetal_core.evaluated). A body whose rule was
    removed from the design gets the default rule (and a warning)."""
    doc = body.Document
    name = body_rule_name(body) or active_rule_name(doc)
    rule = find_rule(doc, name) or core.library_rule(name)
    if rule is None:
        warn("sheet metal rule '%s' of %s not found; using the default" % (name, body.Label))
        rule = core.library_rule(core.DEFAULT_RULE)
    return core.evaluated(rule)


def sheet_metal_bodies(doc):
    return [b for b in bodies.list_bodies(doc) if is_sheet_metal_body(b)]


def find_sheet_body(doc, active=None, component=None, exclude=()):
    """The sheet metal body a SHEET METAL tool works on (sm-forming, wave 6): the active body
    when it is sheet metal, else the first sheet metal body of the component (None: the
    active one, or the root) that exists at the history marker, else None. SOLID tools keep
    using commands.find_body, which takes sheet metal bodies too. `exclude`: bodies passed
    over (a dialog's own preview body, QA)."""
    if doc is None:
        return None
    if active is not None and is_sheet_metal_body(active) and active not in exclude:
        return active
    try:
        from . import components

        if component is None:
            component = components.active_component(doc)
        candidates = components.bodies_in(doc, component)
    except Exception:
        candidates = bodies.list_bodies(doc)
    for body in candidates:
        if not is_sheet_metal_body(body) or body in exclude:
            continue
        if body.Tip is None and any(o.isDerivedFrom("PartDesign::Feature") for o in body.Group):
            continue  # rolled back before its first step: not made yet at the marker
        return body
    return None
