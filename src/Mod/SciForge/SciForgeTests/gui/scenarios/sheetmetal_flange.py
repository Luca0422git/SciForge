# SPDX-License-Identifier: LGPL-2.1-or-later
"""SHEET METAL > Flange like a Fusion user, only real input: a base flange, then an edge flange.

Create Sketch on XY, a 50 x 30 rectangle, Finish Sketch. SHEET METAL tab, Flange with
nothing picked: the dialog waits, nothing is built. A click inside the rectangle: a base
flange, a 1 mm plate (the default rule Steel (mm)), in a sheet metal body. Orientation Side 2
puts it under the sketch; back to Side 1; OK: "Flange 1" in the timeline, the bent-sheet icon
in the browser. Flange again, click the plate's top edge on x = 50: an edge flange, the
L bracket of the golden model (volume by hand). Height Datum Outer Faces (wall 1 mm shorter),
Bend Position Outside (outer face 1 mm out), back to Inside / Inner Faces; drag the height
arrow out; type 10 in the Height field; OK: "Flange 2". Undo / Redo. Double-click "Flange 2":
Angle 45 changes the part; Esc leaves it as it was. Double-click again, Angle 135 OK.
"""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sheetmetal_steps as sm
from SciForgeTests.gui import surface_steps as st

V = App.Vector
s = {}


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("SheetFlange")
    h.fit()


def create_sketch():
    h.ribbon("Create Sketch")


def pick_xy():
    st.open_sketch_clicked(V(12, -8, 0))


def draw_rect():
    s["sketch"] = sm.rect_sketch(0, 0, 50, 30)


def finish_sketch():
    h.ribbon("Finish Sketch")


def sheet_metal_tab():
    h.check("left the sketch", h.in_sketch() is None)
    h.fit()
    h.click_empty()
    sm.tab()


def flange_nothing_picked():
    h.check("nothing selected", not Gui.Selection.getSelectionEx())
    h.ribbon("Flange")


def dialog_waits():
    p = sm.panel()
    h.check("Flange dialog open", p is not None)
    if p is None:
        return
    h.check("no pop-up", not h.popups(), h.popups())
    h.check("nothing built yet", p.target is None and not sm.sheet_bodies(), sm.bodies())
    h.check("it says what to pick", "closed sketch profile" in p.mode.text(), p.mode.text())
    h.check("no options before a pick", not sm.shown("height") and not sm.shown("orientation"))
    h.shot("1-waiting")


def click_profile():
    h.fit()
    h.click(V(25, 15, 0))


def plate():
    sm.settle()
    p = sm.panel()
    body = sm.target_body()
    h.check("a base flange", p is not None and p.kind == "base", p and p.kind)
    h.check("a 1 mm plate (50 x 30)", body is not None and sm.near(sm.volume(body), 1500.0))
    from sciforge import sheetmetal

    h.check("a sheet metal body", body is not None and sheetmetal.is_sheet_metal_body(body))
    h.check("following Steel (mm)", sheetmetal.body_rule_name(body) == "Steel (mm)")
    h.check("Rule and Orientation shown", sm.shown("rule") and sm.shown("orientation"))
    h.check("no edge options", not sm.shown("height") and not sm.shown("position"))
    s["body"] = body
    h.shot("2-plate")


def rule_aluminum():
    sm.choose("rule", "Aluminum (mm) (Library)")


def thicker():
    sm.settle()
    h.check(
        "Aluminum (mm): a 1.5 mm plate", sm.near(sm.volume(s["body"]), 2250.0), sm.volume(s["body"])
    )


def rule_steel():
    sm.choose("rule", "Steel (mm)")


def steel_again():
    sm.settle()
    h.check("Steel (mm): 1 mm again", sm.near(sm.volume(s["body"]), 1500.0), sm.volume(s["body"]))


def side_2():
    sm.choose("orientation", "Side 2")


def under_sketch():
    sm.settle()
    box = s["body"].Shape.BoundBox
    h.check("Side 2: under the sketch", abs(box.ZMin + 1.0) < 1e-6 and abs(box.ZMax) < 1e-6, box)


def side_1():
    sm.choose("orientation", "Side 1")


def ok_plate():
    sm.settle()
    sm.ok()


def plate_done():
    h.check("dialog closed", sm.panel() is None)
    titles = sm.timeline_titles()
    h.check("Flange 1 in the timeline", "Flange 1" in titles, titles)
    h.check("plate above the sketch again", abs(s["body"].Shape.BoundBox.ZMin) < 1e-6)
    icon = sm.browser_icon_of(s["body"])
    h.check("browser: the sheet metal icon", icon == "sheet_metal_body", icon)
    h.check("the sketch is hidden", not s["sketch"].ViewObject.Visibility)
    node = sm.browser_node("settings:sheet_metal")
    h.check(
        "Document Settings shows the rule",
        node is not None and node["label"] == "Sheet Metal Rule: Steel (mm)",
        node and node["label"],
    )


def flange_again():
    h.fit()
    h.ribbon("Flange")


def click_edge():
    h.fit()
    h.check("clicked the plate's edge", h.click_edge(V(50, 15, 1)))


def l_bracket():
    sm.settle()
    p = sm.panel()
    h.check("an edge flange", p is not None and p.kind == "edge", p and p.kind)
    h.check("one edge", p is not None and len(p.refs) == 1, p and p.refs)
    vol = sm.volume(s["body"])
    h.check("the L bracket (hand-derived volume)", sm.near(vol, sm.L_BRACKET, 1e-7), vol)
    box = s["body"].Shape.BoundBox
    h.check(
        "outer face on the edge, top at T + H",
        abs(box.XMax - 50) < 1e-6 and abs(box.ZMax - 11) < 1e-6,
        box,
    )
    h.check("edge options shown", sm.shown("height") and sm.shown("position") and sm.shown("datum"))
    h.check("no Rule for an edge flange (the body's)", not sm.shown("rule"))
    h.check("the height arrow is there", "height" in p.arrows, list(p.arrows))
    h.shot("3-edge")


def datum_outer():
    sm.choose("datum", "Outer Faces")


def outer_checked():
    sm.settle()
    vol = sm.volume(s["body"])
    h.check("Outer Faces: the wall 1 mm shorter", sm.near(vol, sm.L_BRACKET - 30, 1e-7), vol)


def position_outside():
    sm.choose("position", "Outside")


def outside_checked():
    sm.settle()
    box = s["body"].Shape.BoundBox
    h.check("Outside: the flange 1 mm out", abs(box.XMax - 51) < 1e-6, box)


def back_inside():
    sm.choose("position", "Inside")


def back_inner():
    sm.settle()
    sm.choose("datum", "Inner Faces")


def drag_height():
    sm.settle()
    s["drag"] = sm.drag_arrow("height", 20.0)


drag_height.wait_ms = 2200


def dragged():
    sm.settle()
    d = s.get("drag")
    h.check("the drag finished", d is not None and d.done, getattr(d, "error", None))
    p = sm.panel()
    height = p.options["height"] if p else 0
    h.check("the drag set the height (about 20)", 12.0 < height < 28.0, height)
    expect = 1440 + 30 * (3 * 3.141592653589793 / 4) + 30 * (height - 1)
    h.check(
        "the flange followed",
        sm.near(sm.volume(s["body"]), expect, 1e-6),
        (sm.volume(s["body"]), expect),
    )


def type_height():
    sm.type_field("height", "10")


def ok_edge():
    sm.settle()
    vol = sm.volume(s["body"])
    h.check("height 10 again", sm.near(vol, sm.L_BRACKET, 1e-7), vol)
    sm.ok()


def edge_done():
    h.check("dialog closed", sm.panel() is None)
    titles = sm.timeline_titles()
    h.check("Flange 2 in the timeline", "Flange 2" in titles, titles)
    h.shot("4-done")


def undo():
    sm.undo()


def undone():
    h.check("undo: the plate alone", sm.near(sm.volume(s["body"]), 1500.0), sm.volume(s["body"]))


def redo():
    sm.redo()


def redone():
    h.check("redo: the L again", sm.near(sm.volume(s["body"]), sm.L_BRACKET, 1e-7))


def edit_from_timeline():
    sm.double_click_timeline("Flange 2")


def edit_open():
    p = sm.panel()
    h.check("the Flange dialog opens on Flange 2", p is not None and p.editing and p.kind == "edge")
    h.check("its edge is picked", p is not None and len(p.refs) == 1)


def angle_45():
    sm.type_field("angle", "45")


def angle_changed():
    sm.settle()
    vol = sm.volume(s["body"])
    h.check("45 degrees changes the part", abs(vol - sm.L_BRACKET) > 1.0, vol)
    s["v45"] = vol


def esc_edit():
    sm.esc()


def unchanged():
    h.check("Esc closed the dialog", sm.panel() is None)
    h.check("Esc: the L bracket as it was", sm.near(sm.volume(s["body"]), sm.L_BRACKET, 1e-7))


def edit_again():
    sm.double_click_timeline("Flange 2")


def drag_angle():
    sm.settle()
    p = sm.panel()
    h.check(
        "the angle handle is there", p is not None and "angle" in p.arrows, p and list(p.arrows)
    )
    sm.drag_angle("angle", 120.0)


drag_angle.wait_ms = 1500


def angle_dragged():
    sm.settle()
    p = sm.panel()
    angle = p.options["angle"] if p else 0
    h.check("the drag turned the flange (about 120)", 100.0 < angle < 140.0, angle)
    h.check("one valid solid", s["body"].Shape.isValid() and len(s["body"].Shape.Solids) == 1)


def angle_135():
    sm.type_field("angle", "135")


def ok_135():
    sm.settle()
    h.check("no message", not sm.message(), sm.message())
    sm.ok()


def done_135():
    h.check("dialog closed", sm.panel() is None)
    box = s["body"].Shape.BoundBox
    h.check("135: the wall leans back over the plate", box.XMax <= 50 + 1e-6 and box.ZMax < 11, box)
    h.check("one valid solid", s["body"].Shape.isValid() and len(s["body"].Shape.Solids) == 1)
    s["v135"] = sm.volume(s["body"])
    h.shot("5-135")


def edit_base():
    sm.double_click_timeline("Flange 1")


def base_rule_shown():
    p = sm.panel()
    h.check("the base flange's dialog", p is not None and p.kind == "base" and p.editing)
    h.check("its Rule box (it made the body)", sm.shown("rule"))
    h.check("no Operation when editing", not sm.shown("operation"))


def swap_rule():
    from sciforge import sheetmetal

    # Aluminum (mm), tried in the first Flange dialog and then left for Steel, was not kept
    # In This Design (QA): it is offered from the library again
    h.check(
        "the rule tried and left is not in the design",
        sheetmetal.find_rule(sm.doc(), "Aluminum (mm)") is None,
        [r["name"] for r in sheetmetal.design_rules(sm.doc())],
    )
    sm.choose("rule", "Aluminum (mm) (Library)")


def swapped():
    sm.settle()
    from sciforge import sheetmetal

    h.check(
        "the body follows Aluminum (mm)", sheetmetal.body_rule_name(s["body"]) == "Aluminum (mm)"
    )
    box = s["body"].Shape.BoundBox
    h.check("the whole part 1.5 mm now", abs(box.ZMin) < 1e-6 and s["body"].Shape.isValid(), box)
    h.check("bigger than in 1 mm", sm.volume(s["body"]) > s["v135"] * 1.3, sm.volume(s["body"]))


def ok_swap():
    sm.ok()


def swap_done():
    h.check("dialog closed", sm.panel() is None)
    from sciforge import sheetmetal

    h.check("kept after OK", sheetmetal.body_rule_name(s["body"]) == "Aluminum (mm)")
    node = sm.browser_node("body:" + s["body"].Name)
    h.check(
        "the browser's tooltip names the rule",
        node is not None and "Aluminum (mm)" in node["tip"],
        node and node["tip"],
    )


def undo_swap():
    sm.undo()


def swap_undone():
    from sciforge import sheetmetal

    h.check("undo: Steel (mm) again", sheetmetal.body_rule_name(s["body"]) == "Steel (mm)")
    h.check(
        "undo: the 1 mm part", sm.near(sm.volume(s["body"]), s["v135"], 1e-7), sm.volume(s["body"])
    )


h.run(
    "sheetmetal_flange",
    [
        new_design,
        create_sketch,
        pick_xy,
        draw_rect,
        finish_sketch,
        sheet_metal_tab,
        flange_nothing_picked,
        dialog_waits,
        click_profile,
        plate,
        rule_aluminum,
        thicker,
        rule_steel,
        steel_again,
        side_2,
        under_sketch,
        side_1,
        ok_plate,
        plate_done,
        flange_again,
        click_edge,
        l_bracket,
        datum_outer,
        outer_checked,
        position_outside,
        outside_checked,
        back_inside,
        back_inner,
        drag_height,
        dragged,
        type_height,
        ok_edge,
        edge_done,
        undo,
        undone,
        redo,
        redone,
        edit_from_timeline,
        edit_open,
        angle_45,
        angle_changed,
        esc_edit,
        unchanged,
        edit_again,
        drag_angle,
        angle_dragged,
        angle_135,
        ok_135,
        done_135,
        edit_base,
        base_rule_shown,
        swap_rule,
        swapped,
        ok_swap,
        swap_done,
        undo_swap,
        swap_undone,
    ],
)
