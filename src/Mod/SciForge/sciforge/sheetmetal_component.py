# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's component Type (Standard / Sheet Metal), without Qt: the New Component dialog
(components_ui.py) and the Flange's New Component call it.

A Sheet Metal component carries ``SciForgeComponentKind = "SheetMetal"`` and its active rule
(``sheetmetal.set_active_rule(doc, name, component)``): the rule the flanges made in it start
with. Fusion makes the change one way (a sheet metal component stays one)."""

from . import log, sheetmetal
from . import sheetmetal_core as core
from . import sheetmetal_flange as flange


def rule_choices(doc):
    """(label, rule name) for the New Component dialog's Rule box: the design's rules, then
    the library's (copied into the design when chosen), the active rule first."""
    active = sheetmetal.active_rule_name(doc)
    out, seen = [], set()
    for rule in sheetmetal.design_rules(doc):
        out.append((rule["name"], rule["name"]))
        seen.add(rule["name"])
    for rule in core.LIBRARY:
        if rule["name"] not in seen:
            out.append(("%s (Library)" % rule["name"], rule["name"]))
    out.sort(key=lambda pair: pair[1] != active)
    return out


def make_sheet_metal(component, rule_name=None):
    """Turn a component into a Sheet Metal component with `rule_name` (default: the design's
    active rule) as its active rule."""
    doc = component.Document
    rule_name = rule_name or sheetmetal.active_rule_name(doc)
    if sheetmetal.find_rule(doc, rule_name) is None:
        rule = core.library_rule(rule_name)
        if rule is None:
            raise ValueError("There is no sheet metal rule named '%s'." % rule_name)
        sheetmetal.save_rule(doc, rule)
    sheetmetal.set_active_rule(doc, rule_name, component)
    flange.mark_sheet_metal_component(component)
    log("component %s is sheet metal (rule %s)" % (component.Label, rule_name))
    return component


def is_sheet_metal(component):
    return flange.is_sheet_metal_component(component)
