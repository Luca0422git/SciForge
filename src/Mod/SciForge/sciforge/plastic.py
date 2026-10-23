# SPDX-License-Identifier: LGPL-2.1-or-later
"""Where a design keeps its plastic rules, and which component follows which rule (FreeCAD,
no Qt: the golden-model builder, headless tests and the dialogs all use this).

The contract of the PLASTIC builders (wave 6; extend it, never rename or remove):

- A design's rules live in one hidden ``App::FeaturePython`` named ``PlasticRules``
  (``RulesJson``: a JSON list of rule dicts, plastic_core.FIELDS; ``RootRule``: the rule
  assigned to the root component, "" for none). It is made on first use.
- Fusion assigns a plastic rule to a **component**, never to a single body (Assign Plastic
  Rule). A component (``App::Part``) carries ``SciForgePlasticRule``: its rule's name. The
  root component (the document) keeps it in ``RootRule``. A body follows its component's
  rule.
- A tool asks ``default_for(body, "thickness")``: the value (mm / degrees) of the body's
  component's rule, or None when that component has no rule (the tool then keeps its own
  default, so non-plastic designs behave as before). The PLASTIC-only tools (Boss, Snap Fit,
  Lip, Rest) use ``rule_for_body(body)``, which falls back to the library's default rule.

    rules_object(doc, create=False)
    design_rules(doc), find_rule(doc, name)
    save_rule(doc, rule)                 add or replace by name; recomputes the users
    delete_rule(doc, name)               refused (ValueError) while assigned
    assigned_rule_name(doc, component)   "" for none (component None = the root)
    assign_rule(doc, name, component)    copies a library rule into the design first
    rule_for_component(doc, component, fallback=False)
    rule_for_body(body, fallback=True)
    default_for(body, field)
"""

import json

from . import bodies, components, log, plastic_core as core, warn

STORE_NAME = "PlasticRules"
RULE_PROP = "SciForgePlasticRule"


def rules_object(doc, create=False):
    if doc is None:
        return None
    obj = doc.getObject(STORE_NAME)
    if obj is not None or not create:
        return obj
    obj = doc.addObject("App::FeaturePython", STORE_NAME)
    obj.Label = "Plastic Rules"
    obj.addProperty("App::PropertyString", "RulesJson", "Plastic", "The design's rules")
    obj.addProperty("App::PropertyString", "RootRule", "Plastic", "Root component's rule")
    obj.RulesJson = "[]"
    obj.RootRule = ""
    for prop in ("RulesJson", "RootRule"):
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


def design_rules(doc):
    obj = rules_object(doc)
    if obj is None:
        return []
    try:
        rules = json.loads(obj.RulesJson or "[]")
        return [r for r in rules if isinstance(r, dict) and r.get("name")]
    except Exception as exc:
        warn("plastic rules of %s unreadable: %s" % (doc.Name, exc))
        return []


def find_rule(doc, name):
    for rule in design_rules(doc):
        if rule["name"] == name:
            return dict(rule)
    return None


def _components_using(doc, name):
    """Components (None = the root) whose assigned rule is name."""
    found = [c for c in components.list_components(doc) if getattr(c, RULE_PROP, "") == name]
    obj = rules_object(doc)
    if obj is not None and obj.RootRule == name:
        found.insert(0, None)
    return found


def _touch_users(doc, name):
    for component in _components_using(doc, name):
        for body in components.bodies_in(doc, component, recursive=True):
            for feature in getattr(body, "Group", []):
                try:
                    feature.touch()
                except Exception:
                    pass


def save_rule(doc, rule):
    problems = core.validate(rule)
    if problems:
        raise ValueError(problems[0])
    obj = rules_object(doc, create=True)
    rules = [r for r in design_rules(doc) if r["name"] != rule["name"]]
    rules.append(dict(rule))
    obj.RulesJson = json.dumps(rules)
    _touch_users(doc, rule["name"])
    log("plastic rule '%s' saved" % rule["name"])


def delete_rule(doc, name):
    users = _components_using(doc, name)
    if users:
        names = [c.Label if c is not None else doc.Label for c in users]
        raise ValueError(
            "'%s' is assigned to %s; assign another rule first" % (name, ", ".join(names))
        )
    obj = rules_object(doc)
    if obj is not None:
        obj.RulesJson = json.dumps([r for r in design_rules(doc) if r["name"] != name])


def assigned_rule_name(doc, component=None):
    if component is not None:
        return getattr(component, RULE_PROP, "") or ""
    obj = rules_object(doc)
    return obj.RootRule if obj is not None else ""


def assign_rule(doc, name, component=None):
    """Assign the rule to the component (None: the root). A library rule is copied into the
    design first; "" removes the assignment."""
    if name and find_rule(doc, name) is None:
        rule = core.library_rule(name)
        if rule is None:
            raise ValueError("no plastic rule named '%s'" % name)
        save_rule(doc, rule)
    if component is None:
        rules_object(doc, create=True).RootRule = name
    else:
        if not hasattr(component, RULE_PROP):
            component.addProperty("App::PropertyString", RULE_PROP, "Plastic", "Plastic rule")
        setattr(component, RULE_PROP, name)
    if name:
        _touch_users(doc, name)


def rule_for_component(doc, component=None, fallback=False):
    """The evaluated rule (plastic_core.evaluated) assigned to the component, or None; with
    fallback=True the library's default rule when none is assigned."""
    name = assigned_rule_name(doc, component)
    rule = (find_rule(doc, name) or core.library_rule(name)) if name else None
    if name and rule is None:
        warn("plastic rule '%s' not found; using the default" % name)
    if rule is None:
        if not fallback:
            return None
        rule = core.library_rule(core.DEFAULT_RULE)
    return core.evaluated(rule)


def rule_for_body(body, fallback=True):
    """The rule of the body's component (see rule_for_component)."""
    if not bodies.is_body(body):
        return core.evaluated(core.library_rule(core.DEFAULT_RULE)) if fallback else None
    return rule_for_component(body.Document, components.container_of(body), fallback)


def default_for(body, field):
    """A plastic default for an existing tool's field: the value of the body's component's
    rule, or None when that component has no rule."""
    try:
        rule = rule_for_body(body, fallback=False)
    except Exception as exc:
        warn("plastic rule: %s" % exc)
        return None
    return None if rule is None else rule.get(field)
