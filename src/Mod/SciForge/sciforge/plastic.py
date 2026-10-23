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

Added by plastic-1 (wave 6):

    library_rules(), library_rule(name)  the built-in library plus the user's own rules
    save_library_rule(rule), delete_library_rule(name)
    default_rule_name(), set_default_rule(name)   Fusion's "Set As Default" (library only)
    is_used(doc, name)                   a design rule assigned to a component
    unique_name(doc, base)               "ABS 2 mm (2)" for a copy
    material_key(rule)                   the rule's physical material in material.LIBRARY
    apply_material(doc, component)       give the component's bodies the rule's material
    plastic_components(doc)              [(component or None, rule name)] with a rule
"""

import json

from . import bodies, components, log, plastic_core as core, warn

STORE_NAME = "PlasticRules"
RULE_PROP = "SciForgePlasticRule"
PREF = "User parameter:BaseApp/Preferences/Mod/SciForge/Plastic"


# -- the library (built in + the user's own, kept in the user's settings) ------------------------
def _pref():
    import FreeCAD as App

    return App.ParamGet(PREF)


def _user_library():
    try:
        rules = json.loads(_pref().GetString("Library", "") or "[]")
        return [r for r in rules if isinstance(r, dict) and r.get("name")]
    except Exception as exc:
        warn("plastic rule library unreadable: %s" % exc)
        return []


def library_rules():
    """Every library rule: the built-in ones (a user's edited copy replaces one), then the
    user's own."""
    user = {r["name"]: r for r in _user_library()}
    found = []
    for rule in core.LIBRARY:
        found.append(dict(user.pop(rule["name"], rule)))
    found += [dict(r) for r in user.values()]
    return found


def library_rule(name):
    for rule in library_rules():
        if rule["name"] == name:
            full = dict(core.make_rule(name))
            full.update(rule)
            return full
    return None


def save_library_rule(rule):
    problems = core.validate(rule)
    if problems:
        raise ValueError(problems[0])
    rules = [r for r in _user_library() if r["name"] != rule["name"]]
    rules.append(dict(rule))
    _pref().SetString("Library", json.dumps(rules))
    log("plastic library rule '%s' saved" % rule["name"])


def delete_library_rule(name):
    if name == default_rule_name():
        raise ValueError("'%s' is the default rule: set another rule as default first" % name)
    if core.library_rule(name) is not None and not any(r["name"] == name for r in _user_library()):
        raise ValueError("'%s' is one of SciForge's own library rules: it cannot be deleted" % name)
    _pref().SetString("Library", json.dumps([r for r in _user_library() if r["name"] != name]))


def default_rule_name():
    name = ""
    try:
        name = _pref().GetString("Default", "")
    except Exception:
        pass
    if name and library_rule(name) is not None:
        return name
    return core.DEFAULT_RULE


def set_default_rule(name):
    if library_rule(name) is None:
        raise ValueError("no library rule named '%s'" % name)
    _pref().SetString("Default", name)


def is_used(doc, name):
    return bool(_components_using(doc, name))


def unique_name(doc, base, library=False):
    taken = {r["name"] for r in (library_rules() if library else design_rules(doc))}
    if base not in taken:
        return base
    i = 2
    while "%s (%d)" % (base, i) in taken:
        i += 1
    return "%s (%d)" % (base, i)


def material_key(rule):
    """The material.LIBRARY key of the rule's material, or None (SciForge has none)."""
    return core.MATERIAL_KEYS.get((rule or {}).get("material", ""))


def apply_material(doc, component=None):
    """Give every body of the component (None: the root's own bodies) the physical material
    of its rule, like Fusion's rule controls the component's material. Returns the
    material key, or None when SciForge's library has no such material."""
    name = assigned_rule_name(doc, component)
    rule = (find_rule(doc, name) or library_rule(name)) if name else None
    key = material_key(rule) if rule else None
    if key is None:
        return None
    from . import material

    for body in components.bodies_in(doc, component, recursive=component is not None):
        try:
            material.assign(body, key)
        except Exception as exc:
            warn("plastic rule material on %s: %s" % (body.Label, exc))
    return key


def plastic_components(doc):
    found = []
    name = assigned_rule_name(doc, None)
    if name:
        found.append((None, name))
    for component in components.list_components(doc):
        name = getattr(component, RULE_PROP, "") or ""
        if name:
            found.append((component, name))
    return found


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
        rule = library_rule(name)
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
    rule = (find_rule(doc, name) or library_rule(name)) if name else None
    if name and rule is None:
        warn("plastic rule '%s' not found; using the default" % name)
    if rule is None:
        if not fallback:
            return None
        rule = library_rule(default_rule_name()) or core.library_rule(core.DEFAULT_RULE)
    return core.evaluated(rule)


def rule_for_body(body, fallback=True):
    """The rule of the body's component (see rule_for_component)."""
    if not bodies.is_body(body):
        if not fallback:
            return None
        return core.evaluated(
            library_rule(default_rule_name()) or core.library_rule(core.DEFAULT_RULE)
        )
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


# The existing SOLID tools' fields that take a plastic rule's value (plastic-1; research
# fusion-plastic.md 1.3): tool -> {option: (rule field, factor)}. Rib / Web 0.6 x the wall
# (generic plastics guidance, G).
TOOL_DEFAULTS = {
    "shell": {"inside": ("thickness", 1.0), "outside": ("thickness", 1.0)},
    "draft": {"angle": ("draft_angle", 1.0), "angle2": ("draft_angle", 1.0)},
    "rib": {"thickness": ("thickness", 0.6)},
    "extrude": {"wall_thickness": ("thickness", 1.0), "wall_thickness2": ("thickness", 1.0)},
    "fillet": {"radius": ("nominal_radius", 1.0)},
}


def apply_defaults(options, body, tool):
    """Put the body's component's rule values into a new dialog's options (in place) for the
    fields of TOOL_DEFAULTS[tool]; nothing for a body whose component has no rule. Returns
    the option names it set. Never raises (a dialog must open whatever happens here)."""
    done = []
    try:
        if body is None or not plastic_components(body.Document):
            return done
        for key, (field, factor) in TOOL_DEFAULTS.get(tool, {}).items():
            value = default_for(body, field)
            if value is None or key not in options:
                continue
            options[key] = round(float(value) * factor, 4)
            done.append(key)
        if done:
            log("plastic rule defaults for %s: %s" % (tool, ", ".join(done)))
    except Exception as exc:
        warn("plastic rule defaults for %s: %s" % (tool, exc))
    return done
