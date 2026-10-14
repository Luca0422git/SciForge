# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Rule Fillet: Type Rule Fillet, Rule All Edges, the box's Extrude picked in the
timeline, radius 1: every edge of it is rounded. Rounds / Fillets: with Rounds off nothing
fits on a box (all its edges are outside edges) and the dialog says so. Then the model is
edited (a hole drawn in Sketch 1, from the timeline): the rule applies again and the hole's
new edges are rounded too, which a plain fillet would not do. Only real input.

Volumes by hand. A box a x b x c with every edge rounded by r is the Minkowski sum
  (a-2r)(b-2r)(c-2r) + 2r[(a-2r)(b-2r) + (b-2r)(c-2r) + (a-2r)(c-2r)]
  + pi r^2 [(a-2r) + (b-2r) + (c-2r)] + 4/3 pi r^3.
A round of radius r on the rim of a hole of radius h removes, by Pappus, the round's
cross-section r^2 (1 - pi/4) turned about the hole's axis at h + its centroid's distance."""

import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import fillet2_steps as f2
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}


def rounded_box(a, bb, c, r):
    a2, b2, c2 = a - 2 * r, bb - 2 * r, c - 2 * r
    return (
        a2 * b2 * c2
        + 2 * r * (a2 * b2 + b2 * c2 + a2 * c2)
        + math.pi * r * r * (a2 + b2 + c2)
        + 4.0 / 3.0 * math.pi * r**3
    )


def rim(hole, r):
    return 2 * math.pi * (hole + b.xbar(r)) * b.spandrel(r)


def _rim(edge):
    """A sharp circular edge of radius 5 at the top or the bottom (a rim not rounded)."""
    try:
        curve = edge.Curve
    except Exception:
        return False  # (where rounds meet: an edge without a curve)
    return (
        type(curve).__name__ == "Circle"
        and abs(curve.Radius - 5) < 1e-6
        and min(abs(curve.Center.z), abs(curve.Center.z - 10)) < 1e-6
    )


def start():
    Gui.Selection.clearSelection()
    h.fit()
    h.press("f")


def rule_type():
    p = b.blend_panel()
    if p:
        b.choose(p.type, "Rule Fillet")


def rule_rows():
    p = b.blend_panel()
    if p is None:
        return
    h.check(
        "Rule Fillet shows Rule, Rounds/Fillets and Radius; no sets",
        p.rule.isVisible()
        and p.rounds.isVisible()
        and p.fillets.isVisible()
        and p.radius.widget.isVisible()
        and not p.rows.isVisible()
        and not p.radius_type.isVisible(),
    )
    h.check("Rule: All Edges by default", p.rule.currentText() == "All Edges")
    button = b.timeline_button("Extrude 1")
    if h.check("timeline shows Extrude 1", button is not None, b.timeline_titles()):
        b.click_widget(button)


def feature_picked():
    p = b.blend_panel()
    h.check(
        "the Extrude is in the rule's box",
        p is not None and [f.Name for f in p.features] == ["Extrude"],
        p and p.features,
    )
    h.check("the box says 1 selected", p is not None and p.select_button.text() == "1 selected")
    v = h.solid_volume()
    expect = rounded_box(40, 30, 10, 1)
    h.check("every edge rounded (r 1)", b.close(v, expect), (v, expect))
    h.check("one arrow for the rule's radius", p is not None and len(p.arrows) == 1)
    h.shot("1-rule")
    if p:
        f2.click_check(p.rounds)


def rounds_off():
    p = b.blend_panel()
    text = p.message.text() if p else ""
    h.check(
        "Rounds off: a box has no inside edges, the dialog says so", "fits the rule" in text, text
    )
    if p:
        f2.click_check(p.rounds)


def rounds_on():
    p = b.blend_panel()
    h.check("Rounds on again: no message", p is not None and p.message.text() == "")
    h.task_button("OK")


def after_ok():
    v = h.solid_volume()
    h.check("kept", b.close(v, rounded_box(40, 30, 10, 1)), v)
    steps = f2.steps()
    h.check("one Rule Fillet step", len(steps) == 1 and f2.spec_of(steps[0])["mode"] == "rule")
    h.check("timeline: Fillet 1", "Fillet 1" in b.timeline_titles(), b.timeline_titles())
    b.timeline_double_click("Sketch 1", click_first=True)


def in_sketch():
    sk = h.in_sketch()
    h.check("editing Sketch 1", sk is not None)
    if sk:
        h.draw_circle(sk, 20, 15, 5)


def finish():
    h.ribbon("Finish Sketch")


def edited():
    v = h.solid_volume()
    expect = rounded_box(40, 30, 10, 1) - math.pi * 25 * 10 - 2 * rim(5, 1)
    h.check("the hole's new edges are rounded by the rule too", b.close(v, expect), (v, expect))
    shape = h.body().Shape
    sharp_circles = [e for e in shape.Edges if _rim(e)]
    h.check("no sharp rim is left on the hole", not sharp_circles, len(sharp_circles))
    steps = f2.steps()
    h.check(
        "the rule step computes",
        steps and "Invalid" not in steps[0].State,
        steps and steps[0].State,
    )
    h.check("valid solid", shape.isValid())
    h.check("no kernel errors", not f2.report_errors(), f2.report_errors())
    h.shot("2-edited")
    b.timeline_double_click("Fillet 1", click_first=True)


def edit_open():
    p = b.blend_panel()
    h.check("editing the rule fillet", p is not None and not p.created)
    if p is None:
        return
    h.check(
        "Rule Fillet, its Extrude and radius shown",
        p.type.currentText() == "Rule Fillet"
        and [f.Name for f in p.features] == ["Extrude"]
        and abs(p.radius.value() - 1) < 1e-9,
        (p.type.currentText(), p.features, p.radius.value()),
    )
    b.type_into(p.radius.widget, "0.5")


def edit_ok():
    h.task_button("OK")


def end():
    v = h.solid_volume()
    expect = rounded_box(40, 30, 10, 0.5) - math.pi * 25 * 10 - 2 * rim(5, 0.5)
    h.check("radius 0.5 everywhere", b.close(v, expect), (v, expect))
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("no kernel errors", not f2.report_errors(), f2.report_errors())


h.run(
    "fillet2_rule",
    b.box_steps("Rule")
    + [
        start,
        rule_type,
        rule_rows,
        feature_picked,
        rounds_off,
        rounds_on,
        after_ok,
        in_sketch,
        finish,
        edited,
        edit_open,
        edit_ok,
        end,
    ],
)
