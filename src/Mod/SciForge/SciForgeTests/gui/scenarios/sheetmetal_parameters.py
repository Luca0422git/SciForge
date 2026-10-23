# SPDX-License-Identifier: LGPL-2.1-or-later
"""SHEET METAL > Flange with parameters, like a Fusion user: a user parameter typed into the
Height field drives the flange; changing the parameter moves the flange; the edit dialog
shows it; a number typed instead removes the formula.

A user parameter lip = 15 mm (made the way Change Parameters makes it). A plate (base flange),
Flange on its 30 mm edge, "lip" typed in Height: the flange is 15 high (volume by hand); OK.
lip = 20: the flange follows. Double-click the flange: its Height carries the formula; type 10:
the formula goes, OK; lip = 25 leaves it at 10. Change Parameters lists the flange's Height.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sheetmetal_steps as sm
from SciForgeTests.gui import surface_steps as st

V = App.Vector
s = {}


def flange_volume(height):
    """The 50 x 30 plate with an edge flange of this height (Inside, Inner Faces, T = R = 1)."""
    return 1440 + 30 * 3 * math.pi / 4 + 30 * (height - 1)


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("SheetParams")
    from sciforge import parameters

    parameters.add_user(App.ActiveDocument, "lip", "mm", "15")
    App.ActiveDocument.recompute()
    h.fit()


def create_sketch():
    h.ribbon("Create Sketch")


def pick_xy():
    st.open_sketch_clicked(V(12, -8, 0))


def draw_rect():
    sm.rect_sketch(0, 0, 50, 30)


def finish_sketch():
    h.ribbon("Finish Sketch")


def flange():
    h.fit()
    h.click_empty()
    sm.tab()
    h.ribbon("Flange")


def click_profile():
    h.fit()
    h.click(V(25, 15, 0))


def ok_plate():
    sm.settle()
    s["body"] = sm.target_body()
    sm.ok()


def flange_edge():
    h.check("a plate", sm.near(sm.volume(s["body"]), 1500.0))
    h.fit()
    h.ribbon("Flange")


def click_edge():
    h.fit()
    h.check("clicked the edge", h.click_edge(V(50, 15, 1)))


def type_parameter():
    sm.settle()
    sm.type_field("height", "lip")


def follows_h():
    sm.settle()
    vol = sm.volume(s["body"])
    h.check("Height = lip = 15", sm.near(vol, flange_volume(15), 1e-7), (vol, sm.message()))


def ok():
    sm.ok()


def stored():
    from sciforge import preview

    h.check("dialog closed", sm.panel() is None)
    s["flange"] = s["body"].Tip
    h.check(
        "the formula is on the flange",
        preview.formula_of(s["flange"], "Height") == "lip",
        preview.formula_of(s["flange"], "Height"),
    )
    from sciforge import parameters

    parameters.set_user(App.ActiveDocument, "lip", "20")
    App.ActiveDocument.recompute()


def follows_20():
    vol = sm.volume(s["body"])
    h.check("lip = 20: the flange follows", sm.near(vol, flange_volume(20), 1e-7), vol)
    from sciforge import parameters

    rows = parameters.model_parameters(App.ActiveDocument)
    text = repr(rows)
    h.check("Change Parameters lists the flange's Height", "Height" in text, text[:300])


def edit():
    sm.double_click_timeline("Flange 2")


def edit_shows():
    p = sm.panel()
    h.check("the edit dialog", p is not None and p.editing)
    h.check(
        "it knows the formula", p is not None and p.formulas.get("height") == "lip", p and p.formulas
    )


def type_10():
    sm.type_field("height", "10")


def ok_10():
    sm.settle()
    h.check("10 high", sm.near(sm.volume(s["body"]), flange_volume(10), 1e-7), sm.volume(s["body"]))
    sm.ok()


def no_formula():
    from sciforge import parameters, preview

    h.check("the formula is gone", not preview.formula_of(s["flange"], "Height"))
    parameters.set_user(App.ActiveDocument, "lip", "25")
    App.ActiveDocument.recompute()


def stays_10():
    h.check("lip = 25 leaves it at 10", sm.near(sm.volume(s["body"]), flange_volume(10), 1e-7))


h.run(
    "sheetmetal_parameters",
    [
        new_design,
        create_sketch,
        pick_xy,
        draw_rect,
        finish_sketch,
        flange,
        click_profile,
        ok_plate,
        flange_edge,
        click_edge,
        type_parameter,
        follows_h,
        ok,
        stored,
        follows_20,
        edit,
        edit_shows,
        type_10,
        ok_10,
        no_formula,
        stays_10,
    ],
)
