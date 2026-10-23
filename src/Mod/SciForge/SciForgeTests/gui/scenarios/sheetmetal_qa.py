# SPDX-License-Identifier: LGPL-2.1-or-later
"""SHEET METAL paths the builder's scenarios left out (QA, wave 6), only real input.

An empty design: Flange waits, OK is refused with what to pick, Esc leaves the design empty
and adds no undo step; Sheet Metal Rules on the empty design lists Steel (mm) as active, Edit
then Esc goes back to the lists, Esc closes, nothing is added. Then a 50 x 30 plate (base
flange), an edge preselected before Flange starts an edge flange on it, Cancel leaves the
plate as it was. Two edges that meet, Height 15: the mitred corner; OK. Save, close, reopen:
the steps and their view providers come back, the same solid after a recompute; double-click
"Flange 2": its two edges and Height 15; Height 20 changes the part, Cancel puts it back
with no undo step. Sheet Metal Rules after the reopen: Steel (mm) Thickness 2 recomputes the
whole part (2 mm, still one valid solid); Undo takes it back to 1 mm, Redo to 2 mm. A later
Flange on the two plate edges next to the earlier flanges (their side faces run on into the
flanges' end faces) is taken. New Component, Type Sheet Metal with Aluminum (mm): deleting
that rule in Sheet Metal Rules is refused (it is the component's active rule).
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
        new_component,
        component_sheet_metal,
        ok_component,
        rules_with_component,
        delete_component_rule,
        component_rule_kept,
        close_rules_2,
        rules_closed_2,
    ],
)
