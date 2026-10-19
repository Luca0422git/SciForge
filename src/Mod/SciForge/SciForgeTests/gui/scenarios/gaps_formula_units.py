# SPDX-License-Identifier: LGPL-2.1-or-later
"""A formula of the wrong kind in a value field is refused, like Fusion (its formulas carry
units: a length is no angle), only real input. Before, the bare number was taken: "gap"
(12 mm) typed as a draft angle made a 12 degree draft.

Part: box 40 x 30 x 10 with a through hole r 2 at (8, 8). User parameters (Change Parameters
made them): n = 3 (no unit), gap = 12 mm, turn = 30 deg.
Path F1, Rectangular Pattern of the hole along X: "gap" in Quantity is a length, not a
         number (said, the field keeps 2); "turn" in Distance is an angle, not a length;
         then "n" and "gap*2": holes at x = 8, 20, 32. Cancel.
Path F2, Draft of the front face from the XY plane: "gap" in Angle is refused (the preview
         keeps 1 degree); "turn / 3": 10 degrees. Cancel.
Path F3, Plane at Angle on the front top edge: "gap" is refused and OK waits; "turn": the
         plane turns 30 degrees; "gap / 1 mm" has no unit: 12 degrees. OK.
Path F4, Extrude of the top face: "gap" in Taper Angle and "turn" in Distance are refused.
         Cancel: nothing changed.

Hand-derived: box 12000 less the hole pi 2^2 10; a draft of the 40 long front face by a
(10 high, pivot at the bottom) removes 40 * 10^2 tan(a) / 2.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import inspect_steps as s
from SciForgeTests.gui import pattern_steps as ps
from SciForgeTests.gui import shell_draft_steps as sd

V = App.Vector
R = 2.0
HOLE = ps.hole(R)
PART = ps.BOX - HOLE
st = {}


def tan(a):
    return math.tan(math.radians(a))


def drafted(a):
    return PART - 40 * 100.0 * tan(a) / 2.0


def centres():
    return ps.circle_centres(h.body().Shape, R, z=10)


def params():
    from sciforge import parameters

    doc = App.ActiveDocument
    # Change Parameters (its own dialog, tested by its own scenarios) made these:
    parameters.add_user(doc, "n", "", "3")
    parameters.add_user(doc, "gap", "mm", "12")
    parameters.add_user(doc, "turn", "deg", "30")
    doc.recompute()
    h.check("box with a hole", ps.close(h.solid_volume(), PART), h.solid_volume())


# -- F1: Rectangular Pattern --------------------------------------------------------------------
def f1_start():
    Gui.Selection.clearSelection()
    h.ribbon("Rectangular Pattern")


def f1_pick():
    ps.timeline_click("Extrude 2")


def f1_box():
    ps.click_box("direction")


def f1_axis():
    h.fit()
    pl.click_on_plane(V(-12, 0, 0))


def f1_quantity_gap():
    p = ps.panel()
    h.check("X axis picked", p and p.options["direction"] is not None)
    st["quantity"] = p.quantity.value()
    ps.type_quantity(p.quantity, "gap")


def f1_quantity_refused():
    p = ps.panel()
    text = p.message.text()
    h.check("Quantity: 'gap' is a length, not a number", "a length, not a number" in text, text)
    h.check("no formula taken", "quantity" not in p.options["expressions"])
    h.check("the field is as it was", p.quantity.value() == st["quantity"], p.quantity.value())
    ps.type_value(p.distance_field.widget, "turn")


def f1_distance_refused():
    p = ps.panel()
    text = p.message.text()
    h.check("Distance: 'turn' is an angle, not a length", "an angle, not a length" in text, text)
    h.check("no formula taken", "distance" not in p.options["expressions"])
    ps.type_quantity(p.quantity, "n")


def f1_n():
    p = ps.panel()
    h.check("n is a number: 3", p.quantity.value() == 3, p.quantity.value())
    ps.type_value(p.distance_field.widget, "gap*2")


def f1_three():
    p = ps.panel()
    h.check("3 holes", centres() == [(8, 8), (20, 8), (32, 8)], centres())
    h.check("no complaint now", "⚠" not in p.message.text(), p.message.text())
    h.shot("1-pattern")
    h.task_button("Cancel")


def f1_cancelled():
    h.check("Cancel: no pattern", not ps.patterns() and ps.close(h.solid_volume(), PART))


# -- F2: Draft ----------------------------------------------------------------------------------
def f2_start():
    Gui.Selection.clearSelection()
    sd.modify_menu("Draft")


def f2_xy():
    h.fit()
    pl.click_square("XY_Plane")  # where the square shows (was 12, -8, 0)


def f2_front():
    h.fit()
    pl.click_on_plane(V(20, 0, 5))


def f2_gap():
    p = sd.draft_panel()
    h.check("one degree to start", ps.close(h.solid_volume(), drafted(1.0)), h.solid_volume())
    ui.type_into(p.angle.widget, "gap")


def f2_refused():
    p = sd.draft_panel()
    text = p.message.text()
    h.check("Angle: 'gap' is a length, not an angle", "a length, not an angle" in text, text)
    h.check("the preview keeps 1 degree", ps.close(h.solid_volume(), drafted(1.0)))
    ui.type_into(p.angle.widget, "turn / 3")


def f2_ten():
    p = sd.draft_panel()
    h.check("turn / 3: 10 degrees", ps.close(h.solid_volume(), drafted(10.0)), h.solid_volume())
    h.check("no complaint now", "⚠" not in p.message.text(), p.message.text())
    h.task_button("Cancel")


def f2_cancelled():
    h.check("Cancel: no draft", not sd.drafts() and ps.close(h.solid_volume(), PART))


# -- F3: Plane at Angle -------------------------------------------------------------------------
def f3_start():
    h.click_empty()
    s.menu("CONSTRUCT", "Plane at Angle")


def f3_edge():
    h.fit()
    h.click_edge(V(25, 0, 10))


def f3_gap():
    p = s.construct_panel()
    if h.check("plane shown after the edge click", p is not None and p.datum is not None):
        s.type_into(p.angle.widget, "gap")


def f3_refused():
    p = s.construct_panel()
    text = p.message.text()
    h.check("Angle: 'gap' is a length, not an angle", "a length, not an angle" in text, text)
    n = s.normal_of(p.datum)
    h.check("the plane stays at 0 degrees", abs(n.z) < 1e-6, n)
    h.task_button("OK")


def f3_ok_waits():
    p = s.construct_panel()
    h.check("OK waits", p is not None and Gui.Control.activeDialog())
    if p is not None:
        s.type_into(p.angle.widget, "turn")


def f3_thirty():
    p = s.construct_panel()
    n = s.normal_of(p.datum)
    h.check("turn: 30 degrees", abs(abs(n.z) - 0.5) < 1e-6, n)
    h.check("no complaint now", "⚠" not in p.message.text(), p.message.text())
    s.type_into(p.angle.widget, "gap / 1 mm")


def f3_twelve():
    p = s.construct_panel()
    n = s.normal_of(p.datum)
    sine = math.sin(math.radians(12.0))
    h.check("gap / 1 mm has no unit: 12 degrees", abs(abs(n.z) - sine) < 1e-6, n)
    h.task_button("OK")


def f3_made():
    planes = s.datums("PartDesign::Plane")
    h.check("Plane1 made", len(planes) == 1, planes)


# -- F4: Extrude --------------------------------------------------------------------------------
def f4_start():
    h.click_empty()
    h.fit()
    h.click(V(30, 20, 10))


def f4_e():
    h.press("e")


def f4_taper():
    p = b.active_panel()
    if h.check("Extrude open", p is not None and getattr(p, "taper", None) is not None):
        ui.type_into(p.taper.widget, "gap")


def f4_taper_refused():
    p = b.active_panel()
    text = p.message.text()
    h.check("Taper: 'gap' is a length, not an angle", "a length, not an angle" in text, text)
    ui.type_into(p.distance.widget, "turn")


def f4_distance_refused():
    p = b.active_panel()
    text = p.message.text()
    h.check("Distance: 'turn' is an angle, not a length", "an angle, not a length" in text, text)
    h.shot("2-extrude")
    h.task_button("Cancel")


def f4_cancelled():
    h.check("Cancel: nothing changed", ps.close(h.solid_volume(), PART), h.solid_volume())
    s.no_popups("the end")


h.run(
    "gaps_formula_units",
    b.box_steps("FormulaUnits")
    + ps.make_cut("hole", (8, 8), R)
    + [
        params,
        f1_start,
        f1_pick,
        f1_box,
        f1_axis,
        f1_quantity_gap,
        f1_quantity_refused,
        f1_distance_refused,
        f1_n,
        f1_three,
        f1_cancelled,
        f2_start,
        f2_xy,
        f2_front,
        f2_gap,
        f2_refused,
        f2_ten,
        f2_cancelled,
        f3_start,
        f3_edge,
        f3_gap,
        f3_refused,
        f3_ok_waits,
        f3_thirty,
        f3_twelve,
        f3_made,
        f4_start,
        f4_e,
        f4_taper,
        f4_taper_refused,
        f4_distance_refused,
        f4_cancelled,
    ],
)
