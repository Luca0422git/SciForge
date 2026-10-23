# SPDX-License-Identifier: LGPL-2.1-or-later
"""SHEET METAL > Flange, edge flange options, like a Fusion user, only real input.

A 1 mm plate (base flange of a 50 x 30 sketch). Flange, click two edges that meet at a corner:
both flanges are mitred with the rule's gap (volume by hand, golden model
sheetmetal_edge_flange_miter); OK. Undo. Flange on one edge, Width Symmetric 10 with the Bend
Relief override (Straight, 1 x 0.5): reliefs at both ends (volume by hand); Round reliefs take
a little less. Esc. Refusals: an edge across the thickness says why; a height that does not
reach past the bend says why and OK keeps the dialog open; Esc. To Object: a box above the
plate, its top face clicked: the flange runs up to it; OK. New Component with Type Sheet
Metal and the rule Aluminum (mm): a sheet metal component whose Flange starts with that rule.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sheetmetal_steps as sm
from SciForgeTests.gui import surface_steps as st

V = App.Vector
s = {}
SEC = sm.SEC
CUT = ((30 + 20 + math.sqrt(0.5)) - 49.5) * 9 + (3 * math.pi / 4) * (
    (30 + 20 + math.sqrt(0.5)) - (48 + 28 / (9 * math.pi))
)
MITER = 1344 + 80 * SEC - 2 * CUT


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("SheetEdges")
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


def flange_two():
    h.check("a 1 mm plate", sm.near(sm.volume(s["body"]), 1500.0))
    h.fit()
    h.ribbon("Flange")


def click_first():
    h.fit()
    h.check("clicked the 30 mm edge", h.click_edge(V(50, 15, 1)))


def click_second():
    sm.settle()
    h.check("clicked the 50 mm edge", h.click_edge(V(25, 30, 1)))


def mitred():
    sm.settle()
    p = sm.panel()
    h.check("two edges", p is not None and len(p.refs) == 2, p and p.refs)
    vol = sm.volume(s["body"])
    h.check("mitred corner (volume by hand)", sm.near(vol, MITER, 1e-6), (vol, MITER))
    h.check("one valid solid", s["body"].Shape.isValid() and len(s["body"].Shape.Solids) == 1)
    h.shot("1-miter")


def ok_miter():
    sm.ok()


def undo_miter():
    h.check("dialog closed", sm.panel() is None)
    sm.undo()


def flange_partial():
    h.check("undo: the plate", sm.near(sm.volume(s["body"]), 1500.0), sm.volume(s["body"]))
    h.fit()
    h.ribbon("Flange")


def click_edge():
    h.fit()
    h.check("clicked the edge", h.click_edge(V(50, 15, 1)))


def symmetric():
    sm.settle()
    sm.choose("width_type", "Symmetric")


def width_10():
    sm.settle()
    h.check("Width shown", sm.shown("width"))
    sm.type_field("width", "10")


def relief_override():
    sm.settle()
    sm.toggle("override_bend_relief")


def relief_values():
    sm.settle()
    h.check("relief fields shown", sm.shown("relief_shape") and sm.shown("relief_depth"))
    sm.choose("relief_shape", "Straight")


def relief_sizes():
    sm.settle()
    sm.type_field("relief_width", "1")


def relief_depth():
    sm.settle()
    sm.type_field("relief_depth", "0.5")


def straight_reliefs():
    sm.settle()
    vol = sm.volume(s["body"])
    h.check(
        "10 mm flange with straight reliefs (by hand)", sm.near(vol, 1475 + 10 * SEC, 1e-7), vol
    )
    h.shot("2-reliefs")


def round_reliefs():
    sm.choose("relief_shape", "Round")


def rounder():
    sm.settle()
    vol = sm.volume(s["body"])
    h.check(
        "round ends leave a little more plate", 1475 + 10 * SEC < vol < 1475 + 10 * SEC + 1.0, vol
    )


def esc_partial():
    sm.esc()


def make_box():
    h.check("Esc: the plate as it was", sm.near(sm.volume(s["body"]), 1500.0))
    box = App.ActiveDocument.addObject("Part::Box", "Stop")
    box.Length, box.Width, box.Height = 20, 30, 5
    box.Placement.Base = V(70, 0, 25)
    box2 = App.ActiveDocument.addObject("Part::Box", "Stop2")
    box2.Length, box2.Width, box2.Height = 20, 5, 5
    box2.Placement.Base = V(70, 20, 0)
    App.ActiveDocument.recompute()
    s["box"] = box
    s["box2"] = box2
    h.fit()


def flange_refusals():
    h.ribbon("Flange")


def click_thickness_edge():
    h.fit()
    h.check("clicked the box's edge", h.click_edge(V(80, 0, 30)))


def thickness_refused():
    sm.settle()
    p = sm.panel()
    h.check("nothing picked", p is not None and not p.refs, p and p.refs)
    h.check("says why", "sheet metal body" in sm.message(), sm.message())


def click_good_edge():
    h.fit()
    h.check("clicked the edge", h.click_edge(V(50, 15, 1)))


def datum_outer():
    sm.settle()
    sm.choose("datum", "Outer Faces")


def tiny_height():
    sm.settle()
    sm.type_field("height", "1")


def height_refused():
    sm.settle()
    h.check("says the height must pass the bend", "past the bend" in sm.message(), sm.message())


def ok_refused():
    sm.ok()


def stays_open():
    h.check("OK keeps the dialog open", sm.panel() is not None)
    h.check("still says why", "past the bend" in sm.message(), sm.message())


def esc_refusal():
    sm.esc()


def flange_to_object():
    h.check("Esc: the plate", sm.near(sm.volume(s["body"]), 1500.0) and sm.panel() is None)
    h.ribbon("Flange")


def click_edge_3():
    h.fit()
    h.check("clicked the edge", h.click_edge(V(50, 15, 1)))


def to_object():
    sm.settle()
    sm.choose("extent", "To Object")


def object_box_lit():
    sm.settle()
    p = sm.panel()
    h.check(
        "the Object box takes the clicks", p is not None and p.active == "object", p and p.active
    )
    h.check("Height Datum hidden", not sm.shown("datum") and sm.shown("object"))


def click_box_top():
    h.fit()
    h.click(V(80, 15, 30))


def runs_to_box():
    sm.settle()
    p = sm.panel()
    h.check(
        "the box's face picked",
        p is not None and p.to_object is not None and p.to_object[0] is s["box"],
        p and p.to_object,
    )
    box = s["body"].Shape.BoundBox
    h.check("the flange runs up to the box's top (z 30)", abs(box.ZMax - 30) < 1e-6, box)
    expect = 1440 + 30 * 3 * math.pi / 4 + 28 * 30
    h.check("volume by hand", sm.near(sm.volume(s["body"]), expect, 1e-7), sm.volume(s["body"]))


def ok_object():
    sm.ok()


def object_done():
    h.check("dialog closed", sm.panel() is None)
    h.check("Flange 2 in the timeline", "Flange 2" in sm.timeline_titles(), sm.timeline_titles())


def flange_offsets():
    h.fit()
    h.ribbon("Flange")


def click_left_edge():
    h.fit()
    h.check("clicked the left edge", h.click_edge(V(0, 15, 1)))


def two_offsets():
    sm.settle()
    sm.choose("width_type", "Two Offsets")


def refs_lit():
    sm.settle()
    p = sm.panel()
    h.check(
        "Offset Object 1 takes the clicks", p is not None and p.active == "ref1", p and p.active
    )
    h.check("Offset labels", p is not None and p.rows["distance1"][0].text() == "Offset 1")


def click_xz():
    from SciForgeTests.gui import plane_input as pl

    pl.click_square("XZ_Plane")


def ref1_taken():
    sm.settle()
    p = sm.panel()
    h.check(
        "a first reference", p is not None and p.offset_refs[0] is not None, p and p.offset_refs
    )
    h.check("then Offset Object 2", p is not None and p.active == "ref2", p and p.active)


def click_box2():
    h.fit()
    h.click(V(80, 20, 2.5))


def between():
    sm.settle()
    p = sm.panel()
    ref = p.offset_refs[1] if p is not None else None
    h.check(
        "the box's face is the second", ref is not None and ref[0] is s["box2"], p and p.offset_refs
    )
    shape = s["body"].Shape
    h.check(
        "the wall runs between y 5 and y 15 (offsets 5)",
        shape.isInside(V(0.5, 10, 8), 1e-6, True)
        and not shape.isInside(V(0.5, 25, 8), 1e-6, True)
        and not shape.isInside(V(0.5, 2, 8), 1e-6, True),
        sm.message(),
    )
    h.shot("3-two-offsets")


def esc_offsets():
    sm.esc()


def new_component():
    sm.menu("CREATE", "New Component")


def component_dialog():
    from sciforge import components_ui

    p = components_ui.NewComponentPanel.last
    h.check("New Component open", p is not None and not p._closed)
    h.check("Type Standard first", p.type_box.currentText() == "Standard")
    h.check("no Rule for Standard", not p.rule_box.isVisible())
    h.check("chose Sheet Metal", ui.choose(p.type_box, "Sheet Metal"))


def choose_rule():
    from sciforge import components_ui

    p = components_ui.NewComponentPanel.last
    h.check("Rule shown for Sheet Metal", p.rule_box.isVisible())
    h.check(
        "chose Aluminum", ui.choose(p.rule_box, "Aluminum (mm) (Library)"), p.rule_box.currentText()
    )


def ok_component():
    sm.ok()


def component_made():
    from sciforge import components, sheetmetal, sheetmetal_component

    doc = App.ActiveDocument
    parts = components.list_components(doc)
    h.check("one component", len(parts) == 1, parts)
    if not parts:
        return
    part = parts[0]
    s["part"] = part
    h.check("a Sheet Metal component", sheetmetal_component.is_sheet_metal(part))
    h.check("its rule Aluminum (mm)", sheetmetal.active_rule_name(doc, part) == "Aluminum (mm)")
    h.check(
        "the rule copied into the design", sheetmetal.find_rule(doc, "Aluminum (mm)") is not None
    )
    h.check("it is active", components.active_component(doc) is part)


def flange_in_component():
    h.ribbon("Flange")


def rule_default():
    p = sm.panel()
    h.check("Flange open", p is not None)
    h.check(
        "starts with the component's rule",
        p is not None and p.rule_name == "Aluminum (mm)",
        p and p.rule_name,
    )
    sm.esc()


def closed():
    h.check("Esc closed it", sm.panel() is None)


h.run(
    "sheetmetal_edge_options",
    [
        new_design,
        create_sketch,
        pick_xy,
        draw_rect,
        finish_sketch,
        flange,
        click_profile,
        ok_plate,
        flange_two,
        click_first,
        click_second,
        mitred,
        ok_miter,
        undo_miter,
        flange_partial,
        click_edge,
        symmetric,
        width_10,
        relief_override,
        relief_values,
        relief_sizes,
        relief_depth,
        straight_reliefs,
        round_reliefs,
        rounder,
        esc_partial,
        make_box,
        flange_refusals,
        click_thickness_edge,
        thickness_refused,
        click_good_edge,
        datum_outer,
        tiny_height,
        height_refused,
        ok_refused,
        stays_open,
        esc_refusal,
        flange_to_object,
        click_edge_3,
        to_object,
        object_box_lit,
        click_box_top,
        runs_to_box,
        ok_object,
        object_done,
        flange_offsets,
        click_left_edge,
        two_offsets,
        refs_lit,
        click_xz,
        ref1_taken,
        click_box2,
        between,
        esc_offsets,
        new_component,
        component_dialog,
        choose_rule,
        ok_component,
        component_made,
        flange_in_component,
        rule_default,
        closed,
    ],
)
