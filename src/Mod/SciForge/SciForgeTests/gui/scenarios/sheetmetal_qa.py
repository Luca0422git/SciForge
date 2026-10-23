# SPDX-License-Identifier: LGPL-2.1-or-later
"""SHEET METAL paths the builder's scenarios left out (QA, wave 6), only real input.

1. An empty design: Flange waits, OK is refused with what to pick, Esc leaves the design
   empty and adds no undo step. Sheet Metal Rules on the empty design: Steel (mm) active;
   Edit shows only Save / Cancel, Esc goes back to the lists; New, units "in": the plain
   lengths are converted, expressions stay; Cancel; Esc closes; nothing added.
2. A 50 x 30 plate. An edge picked before Flange starts an edge flange on it; Cancel leaves
   the plate. Two edges that meet, Height 15: the mitred corner; OK. Save, close, reopen:
   steps, view providers and the rule link come back, the same solid after a recompute.
   Double-click "Flange 2": its two edges, Height 15; Height 20, Cancel: as it was, no undo
   step. Sheet Metal Rules: Steel (mm) Thickness 2 rebuilds the whole part; Undo, Redo. A
   later Flange on the two plate edges next to the earlier flanges is taken (their side faces
   run on into the flanges' end faces). Editing Flange 2 again: an edge of the later flange
   is refused ("made by a later step"); Esc. New Component (Sheet Metal, Aluminum (mm)):
   deleting that rule is refused (the component's active rule).
3. A second design: a plate made as New Component, Rule Copper (mm) then Aluminum (mm)
   after the pick: the component's rule follows, Copper (mm) is not left in the design. Two
   edges with Bend Position Outside: the override fields start at the body's rule, the walls
   run on to the mitre and close the corner up to the gap. To Object up to the top of the
   part's own wall (and a face picked on the preview maps to the same plane before it).
4. A third design: a plate, then a sketch standing on it (XZ): Flange Join is refused with
   the reason (a corner between two sheets needs a bend), OK keeps the dialog open, Esc
   leaves the plate. To Object chosen, then Distance again: the next click is an edge again.
"""

import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sheetmetal_steps as sm
from SciForgeTests.gui import surface_steps as st

V = App.Vector
s = {}


def _doc():
    return App.ActiveDocument


def _undo_count():
    try:
        return int(_doc().UndoCount)
    except Exception:
        return -1


# -- an empty design -----------------------------------------------------------------------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("SheetQA")
    h.fit()


def empty_flange():
    h.click_empty()
    sm.tab()
    s["undo0"] = _undo_count()
    h.ribbon("Flange")


def empty_waits():
    p = sm.panel()
    h.check("Flange dialog open on an empty design", p is not None)
    h.check("nothing built", p is not None and p.target is None and not sm.bodies())


def empty_ok():
    sm.ok()


def empty_ok_refused():
    p = sm.panel()
    h.check("OK with nothing picked keeps the dialog open", p is not None)
    h.check("it says what to pick", "closed sketch profile" in sm.message(), sm.message())
    h.check("the design is still empty", not _doc().Objects, [o.Name for o in _doc().Objects])


def empty_esc():
    sm.esc()


def empty_escaped():
    h.check("Esc closed the dialog", sm.panel() is None)
    h.check("still empty after Esc", not _doc().Objects, [o.Name for o in _doc().Objects])
    h.check("no undo step", _undo_count() == s["undo0"], (_undo_count(), s["undo0"]))
    h.check("no pop-up", not h.popups(), h.popups())


def empty_rules():
    h.ribbon("Sheet Metal Rules")


def empty_rules_open():
    d = sm.rules_dialog()
    h.check("Sheet Metal Rules open on an empty design", d is not None)
    if d is None:
        return
    design = [d.design.item(i).text() for i in range(d.design.count())]
    h.check("In This Design: Steel (mm), active", design == ["Steel (mm) (active)"], design)


def empty_rules_edit():
    sm.pick_rule("design", "Steel (mm)")
    sm.click_rules_button("design_edit")


def empty_rules_editor():
    d = sm.rules_dialog()
    h.check("the editor page", d is not None and d.pages.currentIndex() == 1)
    h.check("only Save / Cancel while editing", d is not None and not d.close_button.isVisible())
    sm.rule_field("thickness", "3")


def _esc_in_rules():
    """Esc typed in the Sheet Metal Rules window (where the person's focus is)."""
    from PySide import QtCore
    from PySide6 import QtTest

    d = sm.rules_dialog()
    if not h.check("Sheet Metal Rules still open", d is not None):
        return
    target = d.focusWidget() or d
    QtTest.QTest.keyClick(target, QtCore.Qt.Key_Escape)
    QtTest.QTest.qWait(50)


def empty_rules_esc_editor():
    _esc_in_rules()


def empty_rules_back():
    d = sm.rules_dialog()
    h.check(
        "Esc in the editor goes back to the lists", d is not None and d.pages.currentIndex() == 0
    )
    h.check("the edit was not saved", not _doc().Objects, [o.Name for o in _doc().Objects])
    h.check("Close is back", d is not None and d.close_button.isVisible())


def empty_rules_new():
    sm.pick_rule("design", "Steel (mm)")
    sm.click_rules_button("design_new")


def empty_rules_inch():
    from SciForgeTests.gui import dialog_input as ui

    d = sm.rules_dialog()
    h.check("a new rule: units can be chosen", d is not None and d.units_field.isEnabled())
    if d is None:
        return
    h.check("chose in", ui.choose(d.units_field, "in"))
    thickness = d.fields["thickness"].text()
    h.check("its thickness converted: 1 mm = 0.0394 in", thickness == "0.0394 in", thickness)
    radius = d.fields["bend_radius"].text()
    h.check("an expression stays", radius == "Thickness", radius)


def empty_rules_cancel_new():
    sm.click_rules_button("back")


def empty_rules_esc():
    _esc_in_rules()


def empty_rules_closed():
    h.check("Esc closed Sheet Metal Rules", sm.rules_dialog() is None)
    h.check("the design is still empty", not _doc().Objects, [o.Name for o in _doc().Objects])
    h.check("no undo step for a visit that changed nothing", _undo_count() == s["undo0"])
    h.check("no rule row in the browser yet", sm.browser_node("settings:sheet_metal") is None)


# -- a plate -------------------------------------------------------------------------------
def create_sketch():
    h.ribbon("Create Sketch")


def pick_xy():
    st.open_sketch_clicked(V(12, -8, 0))


def draw_rect():
    sm.rect_sketch(0, 0, 50, 30)


def finish_sketch():
    h.ribbon("Finish Sketch")


def flange_plate():
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


def plate_done():
    h.check("dialog closed", sm.panel() is None)
    h.check("a 1 mm plate", s["body"] is not None and sm.near(sm.volume(s["body"]), 1500.0))
    h.check("now the rule row shows", sm.browser_node("settings:sheet_metal") is not None)


# -- an edge picked before Flange; Cancel ----------------------------------------------------
def preselect_edge():
    h.fit()
    h.click_empty()
    h.check("clicked the plate's 30 mm edge", h.click_edge(V(50, 15, 1)))


def flange_preselected():
    h.check("the edge is selected", bool(Gui.Selection.getSelectionEx()), h.state["last_click"])
    s["undo1"] = _undo_count()
    h.ribbon("Flange")


def preselected_flange():
    sm.settle()
    p = sm.panel()
    h.check("an edge flange on the preselected edge", p is not None and p.kind == "edge")
    h.check("one edge", p is not None and len(p.refs) == 1, p and p.refs)
    h.check("the wall is previewed", sm.volume(s["body"]) > 1500.0 + 1.0, sm.volume(s["body"]))


def cancel_preselected():
    sm.cancel()


def cancelled():
    h.check("Cancel closed the dialog", sm.panel() is None)
    h.check("the plate as it was", sm.near(sm.volume(s["body"]), 1500.0), sm.volume(s["body"]))
    titles = sm.timeline_titles()
    h.check("no Flange 2 in the timeline", "Flange 2" not in titles, titles)
    h.check("no undo step", _undo_count() == s["undo1"], (_undo_count(), s["undo1"]))


# -- a mitred corner, saved and reopened -----------------------------------------------------
def flange_corner():
    h.fit()
    h.click_empty()
    h.ribbon("Flange")


def click_first():
    h.fit()
    h.check("clicked the 30 mm edge", h.click_edge(V(50, 15, 1)))


def click_second():
    sm.settle()
    h.check("clicked the 50 mm edge", h.click_edge(V(25, 30, 1)))


def height_15():
    sm.settle()
    p = sm.panel()
    h.check("two edges", p is not None and len(p.refs) == 2, p and p.refs)
    sm.type_field("height", "15")


def ok_corner():
    sm.settle()
    s["v15"] = sm.volume(s["body"])
    h.check("one valid solid", s["body"].Shape.isValid() and len(s["body"].Shape.Solids) == 1)
    sm.ok()


def corner_done():
    h.check("dialog closed", sm.panel() is None)
    titles = sm.timeline_titles()
    h.check("Flange 2 in the timeline", "Flange 2" in titles, titles)
    s["label"] = s["body"].Label
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-sheet-qa-"), "sheet_qa.FCStd")
    s["path"] = path
    _doc().saveAs(path)
    h.check("saved", os.path.isfile(path), path)


def close():
    App.closeDocument(_doc().Name)


def reopen():
    App.openDocument(s["path"])
    h.fit()


def reopened():
    from sciforge import sheetmetal, sheetmetal_flange

    doc = _doc()
    found = [b for b in doc.Objects if b.TypeId == "PartDesign::Body" and b.Label == s["label"]]
    h.check("the body is back", len(found) == 1)
    if not found:
        return
    body = s["body"] = found[0]
    h.check("still sheet metal, Steel (mm)", sheetmetal.body_rule_name(body) == "Steel (mm)")
    steps = [o for o in body.Group if sheetmetal_flange.is_flange(o)]
    h.check("two flange steps", len(steps) == 2, [o.Name for o in steps])
    h.check(
        "their proxies came back",
        all(type(o.Proxy).__name__ == "FlangeFeature" for o in steps),
        [type(o.Proxy).__name__ for o in steps],
    )
    h.check(
        "their view providers came back",
        all(type(o.ViewObject.Proxy).__name__ == "ViewProviderFlange" for o in steps),
        [type(o.ViewObject.Proxy).__name__ for o in steps],
    )
    h.check(
        "the rule store link came back",
        all(o.SciForgeRules is sheetmetal.rules_object(doc) for o in steps),
    )
    for obj in body.Group:
        obj.touch()
    doc.recompute()
    h.check("the same part after a recompute", sm.near(sm.volume(body), s["v15"], 1e-7))
    h.check("one valid solid", body.Shape.isValid() and len(body.Shape.Solids) == 1)
    s["undo2"] = _undo_count()


def edit_corner():
    sm.double_click_timeline("Flange 2")


def edit_open():
    p = sm.panel()
    h.check("the dialog opens on Flange 2", p is not None and p.editing and p.kind == "edge")
    h.check("its two edges", p is not None and len(p.refs) == 2, p and p.refs)
    h.check("Height 15 read back", p is not None and abs(p.options["height"] - 15) < 1e-9)


def height_20():
    sm.type_field("height", "20")


def taller():
    sm.settle()
    vol = sm.volume(s["body"])
    h.check("Height 20 changes the part", vol > s["v15"] + 10.0, (vol, s["v15"]))


def cancel_edit():
    sm.cancel()


def edit_cancelled():
    h.check("Cancel closed the dialog", sm.panel() is None)
    h.check("Cancel: the part as it was", sm.near(sm.volume(s["body"]), s["v15"], 1e-7))
    h.check("no undo step", _undo_count() == s["undo2"], (_undo_count(), s["undo2"]))
    from sciforge import sheetmetal_flange

    step = [o for o in s["body"].Group if sheetmetal_flange.is_flange(o)][-1]
    h.check("Height 15 kept", abs(step.Height.Value - 15) < 1e-9, step.Height)


# -- a rule edit after the reopen, undo / redo ------------------------------------------------
def open_rules():
    h.click_empty()
    sm.tab()
    h.ribbon("Sheet Metal Rules")


def edit_steel():
    sm.pick_rule("design", "Steel (mm)")
    sm.click_rules_button("design_edit")


def thickness_2():
    sm.rule_field("thickness", "2")
    sm.click_rules_button("save")


def rules_saved():
    d = sm.rules_dialog()
    h.check("saved: back to the lists", d is not None and d.pages.currentIndex() == 0)
    body = s["body"]
    box = body.Shape.BoundBox
    s["v2"] = sm.volume(body)
    h.check("the whole part follows: thicker", s["v2"] > s["v15"] * 1.5, (s["v2"], s["v15"]))
    h.check("one valid solid in 2 mm", body.Shape.isValid() and len(body.Shape.Solids) == 1)
    h.check("the plate still starts at z = 0", abs(box.ZMin) < 1e-6, box)


def close_rules():
    sm.click_rules_button("close")


def undo_rule():
    h.check("Sheet Metal Rules closed", sm.rules_dialog() is None)
    sm.undo()


def rule_undone():
    h.check("undo: 1 mm again", sm.near(sm.volume(s["body"]), s["v15"], 1e-7), sm.volume(s["body"]))


def redo_rule():
    sm.redo()


def rule_redone():
    h.check("redo: 2 mm again", sm.near(sm.volume(s["body"]), s["v2"], 1e-7), sm.volume(s["body"]))
    h.check("one valid solid", s["body"].Shape.isValid())
    h.shot("1-redone")


# -- later flanges on the edges next to the earlier ones -------------------------------------
def flange_later():
    h.fit()
    h.click_empty()
    h.ribbon("Flange")


def click_front_edge():
    h.fit()
    h.check("clicked the plate's front edge", h.click_edge(V(25, 0, 2)))


def click_left_edge():
    sm.settle()
    h.check("clicked the plate's left edge", h.click_edge(V(0, 13, 2)))


def later_flanges():
    sm.settle()
    p = sm.panel()
    # their side faces run on into the earlier flanges' end faces: still sheet edges
    h.check(
        "two more edges taken", p is not None and len(p.refs) == 2, (p and p.refs, sm.message())
    )
    h.check("no refusal", not sm.message(), sm.message())
    body = s["body"]
    h.check("more walls", sm.volume(body) > s["v2"] + 100.0, (sm.volume(body), s["v2"]))
    h.check("one valid solid", body.Shape.isValid() and len(body.Shape.Solids) == 1)


def ok_later():
    sm.ok()


def later_done():
    h.check("dialog closed", sm.panel() is None)
    titles = sm.timeline_titles()
    h.check("Flange 3 in the timeline", "Flange 3" in titles, titles)
    h.shot("2-four-walls")
    s["v_later"] = sm.volume(s["body"])


# -- editing the earlier flange: an edge of the later one is not taken ---------------------------
def edit_earlier():
    sm.double_click_timeline("Flange 2")


def click_later_edge():
    sm.settle()
    p = sm.panel()
    h.check("editing Flange 2", p is not None and p.editing and len(p.refs) == 2, p and p.refs)
    h.fit()
    # the top of Flange 3's front wall (T = R = 2 now: the wall runs z 4 .. 12)
    h.check("clicked the later wall's top edge", h.click_edge(V(25, 0, 12)))


def later_edge_refused():
    sm.settle()
    p = sm.panel()
    h.check("still its two edges", p is not None and len(p.refs) == 2, p and p.refs)
    h.check("says why", "later step" in sm.message(), sm.message())


def esc_earlier():
    sm.esc()


def earlier_unchanged():
    h.check("Esc closed it", sm.panel() is None)
    h.check("the part as it was", sm.near(sm.volume(s["body"]), s["v_later"], 1e-7))
    h.check("one valid solid", s["body"].Shape.isValid() and len(s["body"].Shape.Solids) == 1)


# -- a Sheet Metal component's rule cannot be deleted ----------------------------------------
def new_component():
    sm.menu("CREATE", "New Component")


def component_sheet_metal():
    from sciforge import components_ui

    from SciForgeTests.gui import dialog_input as ui

    p = components_ui.NewComponentPanel.last
    h.check("New Component open", p is not None and not p._closed)
    if p is None:
        return
    h.check("chose Sheet Metal", ui.choose(p.type_box, "Sheet Metal"))
    h.check("chose Aluminum", ui.choose(p.rule_box, "Aluminum (mm) (Library)"))


def ok_component():
    sm.ok()


def rules_with_component():
    h.ribbon("Sheet Metal Rules")


def delete_component_rule():
    d = sm.rules_dialog()
    h.check("Sheet Metal Rules open", d is not None)
    sm.pick_rule("design", "Aluminum (mm)")
    sm.click_rules_button("design_delete")


def component_rule_kept():
    from sciforge import sheetmetal

    h.check(
        "refused: the component's rule", "active rule" in sm.rules_message(), sm.rules_message()
    )
    h.check("still in the design", sheetmetal.find_rule(_doc(), "Aluminum (mm)") is not None)


def close_rules_2():
    sm.click_rules_button("close")


def rules_closed_2():
    h.check("closed", sm.rules_dialog() is None)


# -- New Component with another rule; an Outside mitre closes its corner ------------------------
def design_2():
    App.newDocument("SheetQA2")
    h.fit()


def d2_sketch():
    h.ribbon("Create Sketch")


def d2_flange():
    h.ribbon("Finish Sketch")
    h.fit()
    h.click_empty()
    sm.tab()
    h.ribbon("Flange")


def d2_profile():
    h.fit()
    h.click(V(25, 15, 0))


def d2_new_component():
    sm.settle()
    sm.choose("operation", "New Component")


def d2_copper():
    sm.settle()
    sm.choose("rule", "Copper (mm) (Library)")


def d2_aluminum():
    sm.settle()
    sm.choose("rule", "Aluminum (mm) (Library)")


def d2_ok():
    sm.settle()
    s["body2"] = sm.target_body()
    sm.ok()


def d2_component():
    from sciforge import components, sheetmetal

    doc = _doc()
    body = s["body2"]
    h.check("dialog closed", sm.panel() is None)
    h.check("the body follows Aluminum (mm)", sheetmetal.body_rule_name(body) == "Aluminum (mm)")
    part = components.container_of(body) if body is not None else None
    h.check("in a new component", part is not None)
    rule = sheetmetal.active_rule_name(doc, part) if part is not None else None
    h.check("the component's active rule follows the Rule box", rule == "Aluminum (mm)", rule)
    h.check("a 1.5 mm plate", sm.near(sm.volume(body), 2250.0), sm.volume(body))
    names = [r["name"] for r in sheetmetal.design_rules(doc)]
    h.check("Copper (mm), tried then left, is not kept in the design", "Copper (mm)" not in names)
    h.check("Aluminum (mm) is", "Aluminum (mm)" in names, names)


def d2_flange_corner():
    h.fit()
    h.click_empty()
    h.ribbon("Flange")


def d2_first():
    h.fit()
    h.check("clicked the 30 mm edge", h.click_edge(V(50, 15, 1.5)))


def d2_second():
    sm.settle()
    h.check("clicked the 50 mm edge", h.click_edge(V(25, 30, 1.5)))


def d2_outside():
    sm.settle()
    sm.choose("position", "Outside")


def d2_closed_corner():
    sm.settle()
    body = s["body2"]
    shape = body.Shape
    h.check("no message", not sm.message(), sm.message())
    h.check("one valid solid", shape.isValid() and len(shape.Solids) == 1)
    p = sm.panel()
    radius = p.options.get("bend_radius") if p is not None else None
    h.check("the Bend Radius override starts at the body's rule (1.5)", radius == 1.5, radius)
    # the walls stand 1.5 mm out past the plate; each runs on to the mitre (gap 1.5 mm)
    h.check("the 30 mm edge's wall reaches the mitre", shape.isInside(V(51.4, 30.1, 6), 1e-6, True))
    h.check("the 50 mm edge's wall reaches the mitre", shape.isInside(V(50.1, 31.4, 6), 1e-6, True))
    h.check("the gap stays open", not shape.isInside(V(50.75, 30.75, 6), 1e-6, True))
    h.shot("3-outside-mitre")


def d2_ok_corner():
    sm.ok()


def d2_done():
    h.check("dialog closed", sm.panel() is None)


# -- To Object: up to the top of the part's own wall (a face clicked on the preview) ----------
def d2_to_flange():
    h.fit()
    h.click_empty()
    h.ribbon("Flange")


def d2_to_edge():
    h.fit()
    h.check("clicked the plate's front edge", h.click_edge(V(25, 0, 1.5)))


def d2_to_extent():
    sm.settle()
    sm.choose("extent", "To Object")


def d2_to_face():
    sm.settle()
    p = sm.panel()
    h.check("the Object box waits for a pick", p is not None and p.active == "object")
    # the top of the Outside wall on x = 50 (z 11.5: T + R + H - R)
    h.click(V(50.75, 15, 11.5))


def d2_to_check():
    sm.settle()
    p = sm.panel()
    shape = s["body2"].Shape
    picked = p.to_object if p is not None else None
    h.check(
        "the face is taken on the part before the flange",
        picked is not None and p.target is not None and picked[0] is p.target.BaseFeature,
        picked,
    )
    h.check("no message", not sm.message(), sm.message())
    h.check("the new wall runs up to z = 11.5", shape.isInside(V(25, 0.75, 11.4), 1e-6, True))
    h.check("and no higher", not shape.isInside(V(25, 0.75, 11.6), 1e-6, True))
    h.check("one valid solid", shape.isValid() and len(shape.Solids) == 1)
    # the same face can be hit on the preview, which numbers its faces its own way: it must
    # map to the face in the same plane on the part before it (not the same name)
    import Part

    from sciforge import sheetmetal_flange_ui as fui

    target = p.target if p is not None else None
    base = target.BaseFeature if target is not None else None
    name = None
    for i, face in enumerate(target.Shape.Faces if target is not None else [], 1):
        if face.distToShape(Part.Vertex(V(50.75, 15, 11.5)))[0] < 1e-6:
            name = "Face%d" % i
            break
    mapped = fui._same_plane_face(target, name, base) if name else None
    face = base.Shape.getElement(mapped) if mapped else None
    h.check(
        "a face picked on the preview maps to the same plane before it",
        face is not None and abs(face.Vertexes[0].Point.z - 11.5) < 1e-6,
        (name, mapped),
    )


def d2_to_ok():
    sm.ok()


def d2_to_done():
    h.check("dialog closed", sm.panel() is None)


# -- a Join that would stand on the sheet is refused (a third design) --------------------------
def design_3():
    App.newDocument("SheetQA3")
    h.fit()


def d3_sketch():
    h.ribbon("Create Sketch")


def d3_plate_flange():
    h.ribbon("Finish Sketch")
    h.fit()
    h.click_empty()
    sm.tab()
    h.ribbon("Flange")


def d3_plate_profile():
    h.fit()
    h.click(V(25, 15, 0))


def d3_plate_ok():
    sm.settle()
    s["body3"] = sm.target_body()
    sm.ok()


def d3_upright_sketch():
    h.check("dialog closed", sm.panel() is None)
    s["v_d3"] = sm.volume(s["body3"])
    h.check("a 1 mm plate", sm.near(s["v_d3"], 1500.0), s["v_d3"])
    h.fit()
    h.click_empty()
    h.ribbon("Create Sketch")


def d3_xz():
    st.open_sketch_clicked(V(12, 0, 30))


def d3_upright_rect():
    # standing on the plate's top face, along its front edge
    s["upright"] = sm.rect_sketch(10, 1, 40, 20)


def d3_upright_flange():
    h.ribbon("Finish Sketch")
    h.fit()
    h.click_empty()
    h.ribbon("Flange")


def d3_upright_profile():
    h.fit()
    h.click(V(25, 0, 10))


def d3_join():
    sm.settle()
    p = sm.panel()
    h.check("a base flange", p is not None and p.kind == "base", p and p.kind)
    sm.choose("operation", "Join")


def d3_join_refused():
    sm.settle()
    text = sm.message()
    h.check("Join standing on the sheet: refused with why", "plane of the body" in text, text)
    h.check("the plate as it was", sm.near(sm.volume(s["body3"]), s["v_d3"], 1e-7))


def d3_join_ok_refused():
    sm.ok()


def d3_join_stays():
    h.check("OK keeps the dialog open", sm.panel() is not None)
    sm.esc()


def d3_join_escaped():
    h.check("Esc closed it", sm.panel() is None)
    h.check("still the plate as it was", sm.near(sm.volume(s["body3"]), s["v_d3"], 1e-7))
    h.check("no new body", len(sm.sheet_bodies()) == 1, [b.Label for b in sm.sheet_bodies()])


# -- To Object chosen, then Distance again: the next click is an edge again -------------------
def d3_flange_edge():
    h.fit()
    h.click_empty()
    h.ribbon("Flange")


def d3_first_edge():
    h.fit()
    h.check("clicked the 30 mm edge", h.click_edge(V(50, 15, 1)))


def d3_to_object():
    sm.settle()
    sm.choose("extent", "To Object")


def d3_distance_again():
    sm.settle()
    p = sm.panel()
    h.check("To Object waits for a face", p is not None and p.active == "object")
    sm.choose("extent", "Distance")


def d3_second_edge():
    sm.settle()
    p = sm.panel()
    h.check("back to picking edges", p is not None and p.active == "selection", p and p.active)
    h.check("clicked the 50 mm edge", h.click_edge(V(25, 30, 1)))


def d3_two_edges():
    sm.settle()
    p = sm.panel()
    h.check("the second edge is taken", p is not None and len(p.refs) == 2, p and p.refs)
    h.check("no face-pick message", "To Object" not in sm.message(), sm.message())
    sm.esc()


def d3_edges_escaped():
    h.check("Esc closed it", sm.panel() is None)
    h.check("the plate as it was", sm.near(sm.volume(s["body3"]), s["v_d3"], 1e-7))


h.run(
    "sheetmetal_qa",
    [
        new_design,
        empty_flange,
        empty_waits,
        empty_ok,
        empty_ok_refused,
        empty_esc,
        empty_escaped,
        empty_rules,
        empty_rules_open,
        empty_rules_edit,
        empty_rules_editor,
        empty_rules_esc_editor,
        empty_rules_back,
        empty_rules_new,
        empty_rules_inch,
        empty_rules_cancel_new,
        empty_rules_esc,
        empty_rules_closed,
        create_sketch,
        pick_xy,
        draw_rect,
        finish_sketch,
        flange_plate,
        click_profile,
        ok_plate,
        plate_done,
        preselect_edge,
        flange_preselected,
        preselected_flange,
        cancel_preselected,
        cancelled,
        flange_corner,
        click_first,
        click_second,
        height_15,
        ok_corner,
        corner_done,
        close,
        reopen,
        reopened,
        edit_corner,
        edit_open,
        height_20,
        taller,
        cancel_edit,
        edit_cancelled,
        open_rules,
        edit_steel,
        thickness_2,
        rules_saved,
        close_rules,
        undo_rule,
        rule_undone,
        redo_rule,
        rule_redone,
        flange_later,
        click_front_edge,
        click_left_edge,
        later_flanges,
        ok_later,
        later_done,
        edit_earlier,
        click_later_edge,
        later_edge_refused,
        esc_earlier,
        earlier_unchanged,
        new_component,
        component_sheet_metal,
        ok_component,
        rules_with_component,
        delete_component_rule,
        component_rule_kept,
        close_rules_2,
        rules_closed_2,
        design_2,
        d2_sketch,
        pick_xy,
        draw_rect,
        d2_flange,
        d2_profile,
        d2_new_component,
        d2_copper,
        d2_aluminum,
        d2_ok,
        d2_component,
        d2_flange_corner,
        d2_first,
        d2_second,
        d2_outside,
        d2_closed_corner,
        d2_ok_corner,
        d2_done,
        d2_to_flange,
        d2_to_edge,
        d2_to_extent,
        d2_to_face,
        d2_to_check,
        d2_to_ok,
        d2_to_done,
        design_3,
        d3_sketch,
        pick_xy,
        draw_rect,
        d3_plate_flange,
        d3_plate_profile,
        d3_plate_ok,
        d3_upright_sketch,
        d3_xz,
        d3_upright_rect,
        d3_upright_flange,
        d3_upright_profile,
        d3_join,
        d3_join_refused,
        d3_join_ok_refused,
        d3_join_stays,
        d3_join_escaped,
        d3_flange_edge,
        d3_first_edge,
        d3_to_object,
        d3_distance_again,
        d3_second_edge,
        d3_two_edges,
        d3_edges_escaped,
    ],
)
