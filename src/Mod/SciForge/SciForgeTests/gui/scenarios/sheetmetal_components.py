# SPDX-License-Identifier: LGPL-2.1-or-later
"""SHEET METAL with components and SOLID tools, like a Fusion user, only real input.

A: a 50 x 30 sketch; Flange with Operation New Component: the plate goes into a new Sheet
Metal component (its active rule Steel (mm)), the browser shows the component with the sheet
metal icon; OK; the sketch's own body is left as it was.
B: a new design, a plate (base flange). A circle sketched on XY and the SOLID Extrude (E)
up through the plate: Extrude cuts into a sheet metal body (Fusion allows it), the body stays
sheet metal with its rule. A rectangle beside the plate: Flange, its profile, Operation Join:
one 70 x 30 plate (with the hole), no new body; OK; Undo / Redo.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import arrow_input as ai
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import sheetmetal_steps as sm
from SciForgeTests.gui import surface_steps as st

V = App.Vector
s = {}
HOLE = math.pi * 25


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("SheetComponents")
    h.fit()


def create_sketch():
    h.ribbon("Create Sketch")


def pick_xy():
    st.open_sketch_clicked(V(12, -8, 0))


def draw_rect():
    s["sketch"] = sm.rect_sketch(0, 0, 50, 30)


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


def new_component():
    sm.settle()
    h.check("Operation offered", sm.shown("operation"))
    sm.choose("operation", "New Component")


def in_component():
    sm.settle()
    from sciforge import components, sheetmetal, sheetmetal_component

    body = sm.target_body()
    s["body"] = body
    part = components.container_of(body) if body is not None else None
    s["part"] = part
    h.check("the plate is in a new component", part is not None, part)
    h.check("a 1 mm plate", body is not None and sm.near(sm.volume(body), 1500.0))
    if part is None:
        return
    h.check("a Sheet Metal component", sheetmetal_component.is_sheet_metal(part))
    h.check(
        "its active rule Steel (mm)",
        sheetmetal.active_rule_name(App.ActiveDocument, part) == "Steel (mm)",
    )
    from sciforge import bodies

    h.check("the sketch's body left alone", bodies.body_of(s["sketch"]) is not body)


def ok_component():
    sm.ok()


def component_done():
    h.check("dialog closed", sm.panel() is None)
    node = sm.browser_node("component:" + s["part"].Name) if s.get("part") else None
    h.check(
        "browser: the sheet metal component icon",
        node is not None and node["icon"] == "sm_component",
        node and node["icon"],
    )
    h.shot("1-component")


def design_b():
    App.newDocument("SheetSolidTools")
    h.fit()


def b_sketch():
    h.ribbon("Create Sketch")


def b_xy():
    st.open_sketch_clicked(V(12, -8, 0))


def b_rect():
    sm.rect_sketch(0, 0, 50, 30)


def b_finish():
    h.ribbon("Finish Sketch")


def b_flange():
    h.fit()
    h.click_empty()
    sm.tab()
    h.ribbon("Flange")


def b_profile():
    h.fit()
    h.click(V(25, 15, 0))


def b_ok():
    sm.settle()
    s["plate"] = sm.target_body()
    sm.ok()


def hole_sketch():
    h.check("a plate", s["plate"] is not None and sm.near(sm.volume(s["plate"]), 1500.0))
    h.fit()
    h.ribbon("Create Sketch")


def hole_plane():
    pl.click_square("XY_Plane")


def hole_circle():
    sk = h.in_sketch()
    h.check("a sketch is open", sk is not None)
    if sk is not None:
        st.add_circle(sk, 25, 15, 5)


def hole_finish():
    h.ribbon("Finish Sketch")


def extrude():
    h.fit()
    h.click_empty()
    h.press("e")


def extrude_distance():
    sm.wait(300)
    h.check("distance typed", ai.give_distance("5"))


def extrude_ok():
    h.task_button("OK")


def cut_made():
    from sciforge import sheetmetal

    vol = sm.volume(s["plate"])
    h.check("Extrude cut a hole through the sheet", sm.near(vol, 1500.0 - HOLE, 1e-7), vol)
    h.check("still a sheet metal body", sheetmetal.is_sheet_metal_body(s["plate"]))
    h.check("still Steel (mm)", sheetmetal.body_rule_name(s["plate"]) == "Steel (mm)")
    h.check("Extrude 1 in the timeline", "Extrude 1" in sm.timeline_titles(), sm.timeline_titles())


def tab_sketch():
    h.fit()
    h.click_empty()
    h.ribbon("Create Sketch")


def tab_plane():
    pl.click_square("XY_Plane")


def tab_rect():
    sm.rect_sketch(50, 0, 70, 30)


def tab_finish():
    h.ribbon("Finish Sketch")


def tab_flange():
    h.fit()
    h.click_empty()
    sm.tab()
    h.ribbon("Flange")


def tab_profile():
    h.fit()
    h.click(V(60, 15, 0))


def tab_join():
    sm.settle()
    p = sm.panel()
    h.check("a base flange", p is not None and p.kind == "base")
    sm.choose("operation", "Join")


def joined():
    sm.settle()
    vol = sm.volume(s["plate"])
    h.check("one 70 x 30 plate with its hole", sm.near(vol, 2100.0 - HOLE, 1e-7), vol)
    h.check("no Rule box for Join (the body's rule)", not sm.shown("rule"))
    h.check("no new body", len(sm.sheet_bodies()) == 1, sm.sheet_bodies())


def join_ok():
    sm.ok()


def join_done():
    h.check("dialog closed", sm.panel() is None)
    box = s["plate"].Shape.BoundBox
    h.check("70 long", abs(box.XLength - 70) < 1e-6, box)
    h.shot("2-joined")


def undo():
    sm.undo()


def undone():
    h.check("undo: the plate with its hole", sm.near(sm.volume(s["plate"]), 1500.0 - HOLE, 1e-7))


def redo():
    sm.redo()


def redone():
    h.check("redo: joined again", sm.near(sm.volume(s["plate"]), 2100.0 - HOLE, 1e-7))


h.run(
    "sheetmetal_components",
    [
        new_design,
        create_sketch,
        pick_xy,
        draw_rect,
        finish_sketch,
        flange,
        click_profile,
        new_component,
        in_component,
        ok_component,
        component_done,
        design_b,
        b_sketch,
        b_xy,
        b_rect,
        b_finish,
        b_flange,
        b_profile,
        b_ok,
        hole_sketch,
        hole_plane,
        hole_circle,
        hole_finish,
        extrude,
        extrude_distance,
        extrude_ok,
        cut_made,
        tab_sketch,
        tab_plane,
        tab_rect,
        tab_finish,
        tab_flange,
        tab_profile,
        tab_join,
        joined,
        join_ok,
        join_done,
        undo,
        undone,
        redo,
        redone,
    ],
)
