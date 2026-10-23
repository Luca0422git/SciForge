# SPDX-License-Identifier: LGPL-2.1-or-later
"""Plastic rules the way a Fusion user works with them, real input only: PLASTIC > SETUP >
Assign Plastic Rule on a plain 60 x 40 x 10 part (the dialog lists In This Design and the
Library, each rule opening to its values), pick "PC 2 mm" (it is copied into the design, the
part becomes Polycarbonate), Ctrl+Z / Ctrl+Y; Shell from the PLASTIC tab opens with the
rule's 2 mm wall, click the top face, OK (volume by hand); Manage Plastic Rules: edit the
rule to 2.5 mm (Save Rule, OK) and the next Shell opens with 2.5 mm; a rule in use and the
library's default rule cannot be deleted (said in the dialog); a rule whose thickness lies
outside its range is refused; New and Copy then Esc drops them; Set As Default in the
library; a component gets its own rule (picked by clicking its body in the browser); Rule
Fillet opens the Fillet dialog in its Rule mode with the rule's nominal radius; save and
reopen keep the rules."""

import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plastic_steps as ps
from SciForgeTests.gui import shell_draft_steps as sd

V = App.Vector
s = {}


def setup():
    from sciforge import components

    ps.clear_library_prefs()
    Gui.activateWorkbench("SciForgeWorkbench")
    doc = App.newDocument("PlasticRules")
    body = ps.box_body(doc, "Case", 0, 10, "top", shell=False)
    comp = components.new_component(doc, "Cover")
    cover = ps.box_body(doc, "CoverBody", 0, 4, "bottom", shell=False, component=comp)
    comp.Placement = App.Placement(V(80, 0, 0), App.Rotation())  # beside the case
    doc.recompute()
    from sciforge import bodies

    bodies.set_active_body(body)
    s.update(body=body.Name, comp=comp.Name, cover=cover.Name)
    h.check("part made", ps.near(ps.volume(body), 24000.0, 1e-6), ps.volume(body))
    h.fit()
    ps.plastic_tab()


def body():
    return App.ActiveDocument.getObject(s["body"])


def assign():
    Gui.Selection.clearSelection()
    h.ribbon("Assign Plastic Rule")


def assign_open():
    p = ps.assign_panel()
    h.check("Assign dialog open", p is not None)
    if p is None:
        return
    h.check(
        "component: the design (root)",
        p.combo.currentText() == "PlasticRules",
        p.combo.currentText(),
    )
    tree = p.rules.tree
    h.check(
        "two lists: In This Design, Library",
        [tree.topLevelItem(i).text(0) for i in range(tree.topLevelItemCount())]
        == ["In This Design", "Library"],
    )
    h.check(
        "the library holds 16 rules",
        p.rules.library.childCount() == 16,
        p.rules.library.childCount(),
    )
    h.check(
        "the default rule picked",
        p.rules.current() == ("library", "Default (mm)"),
        p.rules.current(),
    )
    row = p.rules.library.child(0)
    h.check(
        "a rule row opens to its values",
        row.childCount() >= 10 and row.child(2).text(0) == "Thickness",
        row.child(2).text(0) if row.childCount() > 2 else None,
    )
    h.shot("1-assign")


def pick_pc():
    p = ps.assign_panel()
    ps.click_tree_row(p.rules.tree, "PC 2 mm", "Library")


def pc_picked():
    p = ps.assign_panel()
    h.check("PC 2 mm picked", p.rules.current() == ("library", "PC 2 mm"), p.rules.current())
    h.check("the material named", "Polycarbonate" in p.info.text(), p.info.text())


def assign_ok():
    ps.ok()


def assigned():
    from sciforge import material, plastic

    doc = App.ActiveDocument
    h.check("dialog closed", ps.assign_panel() is None)
    h.check("copied into the design", [r["name"] for r in plastic.design_rules(doc)] == ["PC 2 mm"])
    h.check("the root component follows it", plastic.assigned_rule_name(doc, None) == "PC 2 mm")
    h.check(
        "the part is Polycarbonate now",
        material.key_of(body()) == "polycarbonate",
        material.key_of(body()),
    )
    h.check("default_for gives the wall", plastic.default_for(body(), "thickness") == 2.0)
    cover = doc.getObject(s["cover"])
    h.check(
        "the Cover component has no rule (its own)", plastic.default_for(cover, "thickness") is None
    )


def undo_assign():
    ps.undo()


def assign_undone():
    from sciforge import plastic

    h.check("Ctrl+Z: no rule", plastic.assigned_rule_name(App.ActiveDocument, None) == "")


def redo_assign():
    ps.redo()


def assign_redone():
    from sciforge import plastic

    h.check(
        "Ctrl+Y: the rule again", plastic.assigned_rule_name(App.ActiveDocument, None) == "PC 2 mm"
    )


def browser_row():
    from SciForgeTests.gui import timeline_input as tl

    labels = tl.labels()
    h.check(
        "the browser shows the rule under Document Settings",
        "Plastic Rule: PC 2 mm" in labels,
        labels,
    )
    ps.click_row("Plastic Rule: PC 2 mm")


def row_opens_assign():
    p = ps.assign_panel()
    h.check("a click on the row opens Assign Plastic Rule", p is not None)
    ps.esc()


def shell():
    Gui.Selection.clearSelection()
    h.ribbon("Shell")


def shell_default():
    p = sd.shell_panel()
    h.check("Shell open", p is not None)
    h.check(
        "Shell's wall from the rule (2 mm)",
        p is not None and abs(p.inside.value() - 2.0) < 1e-9,
        p and p.inside.value(),
    )


def click_top():
    h.fit()
    h.click(V(30, 20, 10))


def shell_ok():
    ps.settle(sd.shell_panel())
    ps.ok()


def shelled():
    v = ps.volume(body())
    h.check(
        "shelled with the rule's wall (24000 - 56*36*8)", ps.near(v, 24000 - 56 * 36 * 8, 1e-6), v
    )


def manage():
    ps.menu("SETUP", "Manage Plastic Rules")


def manage_open():
    p = ps.manage_panel()
    h.check("Manage dialog open", p is not None)
    if p is None:
        return
    h.check(
        "the design's rule listed, in use",
        p.rules.design.childCount() == 1 and p.rules.design.child(0).text(1) == "in use",
    )
    h.check("the library's default marked", p.rules.library.child(0).text(1) == "default")
    h.shot("2-manage")


def pick_design_rule():
    p = ps.manage_panel()
    ps.click_tree_row(p.rules.tree, "PC 2 mm", "In This Design")


def click_edit():
    ps.click(ps.manage_panel().buttons["edit"])


def editor_open():
    p = ps.manage_panel()
    h.check("the rule's fields open", p.editor.isVisible())
    h.check(
        "Thickness shows 2.0", p.fields["thickness"].text() == "2.0", p.fields["thickness"].text()
    )
    h.check("Units fixed for an existing rule", not p.fields["units"].isEnabled())


def type_bad_range():
    p = ps.manage_panel()
    ps.type_into(p.fields["minimum_thickness"], "3")


def save_bad():
    ps.click(ps.manage_panel().save_button)


def bad_refused():
    p = ps.manage_panel()
    h.check(
        "a thickness outside its range is refused",
        "within the thickness range" in p.message.text(),
        p.message.text(),
    )
    h.check("the editor stays open", p.editor.isVisible())


def type_good():
    p = ps.manage_panel()
    ps.type_into(p.fields["minimum_thickness"], "1.0")
    ps.type_into(p.fields["thickness"], "2.5")
    ps.type_into(p.fields["draft_angle"], "1.5")


def save_good():
    ps.click(ps.manage_panel().save_button)


def saved():
    from sciforge import plastic

    p = ps.manage_panel()
    h.check("saved: no message", p.message.text() == "", p.message.text())
    h.check("editor closed", not p.editor.isVisible())
    rule = plastic.find_rule(App.ActiveDocument, "PC 2 mm")
    h.check(
        "the design's rule is 2.5 mm",
        rule and rule["thickness"] == "2.5",
        rule and rule["thickness"],
    )
    h.check(
        "and its draft 1.5 deg", rule and rule["draft_angle"] == "1.5", rule and rule["draft_angle"]
    )


def delete_in_use():
    p = ps.manage_panel()
    ps.click_tree_row(p.rules.tree, "PC 2 mm", "In This Design")
    ps.click(p.buttons["delete"])


def in_use_refused():
    p = ps.manage_panel()
    h.check(
        "a rule in use is not deleted",
        "assign another rule first" in p.message.text(),
        p.message.text(),
    )


def delete_default():
    p = ps.manage_panel()
    ps.click_tree_row(p.rules.tree, "Default (mm)", "Library")
    ps.click(p.buttons["delete"])


def default_refused():
    p = ps.manage_panel()
    h.check(
        "the default library rule is not deleted",
        "default rule" in p.message.text(),
        p.message.text(),
    )


def manage_ok():
    ps.ok()


def shell_again():
    Gui.Selection.clearSelection()
    h.ribbon("Shell")


def shell_follows_rule():
    p = sd.shell_panel()
    h.check(
        "the next Shell opens with the edited rule (2.5 mm)",
        p is not None and abs(p.inside.value() - 2.5) < 1e-9,
        p and p.inside.value(),
    )


def esc_shell():
    ps.esc()


def draft():
    Gui.Selection.clearSelection()
    h.ribbon("Draft")


def draft_follows_rule():
    from sciforge import draft_ui

    p = draft_ui.DraftPanel.last
    h.check(
        "Draft opens with the rule's angle (1.5 deg)",
        p is not None and abs(p.angle.value() - 1.5) < 1e-9,
        p and p.angle.value(),
    )
    ps.esc()


def rib():
    Gui.Selection.clearSelection()
    ps.menu("CREATE", "Rib")


def rib_follows_rule():
    from sciforge import rib_ui

    p = rib_ui.RibPanel.last
    h.check(
        "Rib opens with 0.6 x the rule's wall (1.5 mm)",
        p is not None and abs(p.thickness.value() - 1.5) < 1e-9,
        p and p.thickness.value(),
    )
    ps.esc()


def extrude():
    Gui.Selection.clearSelection()
    h.ribbon("Extrude")


def extrude_follows_rule():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    h.check(
        "Extrude's thin wall from the rule (2.5 mm)",
        p is not None and abs(p.options["wall_thickness"] - 2.5) < 1e-9,
        p and p.options["wall_thickness"],
    )
    h.check("Extrude's distance still starts at 0", p is not None and p.options["distance"] == 0.0)
    ps.esc()


def no_rule_no_change():
    """A design without a rule keeps the tools' own defaults (checked on the Cover, whose
    component has no rule yet)."""
    from sciforge import plastic

    cover = App.ActiveDocument.getObject(s["cover"])
    opts = {"inside": 1.0}
    h.check(
        "no rule: Shell keeps its own 1 mm",
        plastic.apply_defaults(opts, cover, "shell") == [] and opts["inside"] == 1.0,
    )


def manage_again():
    ps.menu("SETUP", "Manage Plastic Rules")


def new_rule():
    p = ps.manage_panel()
    ps.click_tree_row(p.rules.tree, "PC 2 mm", "In This Design")
    ps.click(p.buttons["new"])


def new_editor():
    p = ps.manage_panel()
    h.check(
        "New opens the editor named New rule",
        p.editor.isVisible() and p.fields["name"].text() == "New rule",
        p.fields["name"].text(),
    )
    ps.type_into(p.fields["thickness"], "3")


def save_new():
    ps.click(ps.manage_panel().save_button)


def copy_new():
    p = ps.manage_panel()
    ps.click_tree_row(p.rules.tree, "New rule", "In This Design")
    ps.click(p.buttons["copy"])


def three_rules():
    from sciforge import plastic

    names = [r["name"] for r in plastic.design_rules(App.ActiveDocument)]
    h.check("New and Copy in the design", names == ["PC 2 mm", "New rule", "New rule (2)"], names)


def set_default():
    p = ps.manage_panel()
    ps.click_tree_row(p.rules.tree, "ABS 1.5 mm", "Library")
    ps.click(p.buttons["default"])


def default_set():
    from sciforge import plastic

    h.check("ABS 1.5 mm is the library's default now", plastic.default_rule_name() == "ABS 1.5 mm")


def esc_manage():
    ps.esc()


def dropped():
    from sciforge import plastic

    names = [r["name"] for r in plastic.design_rules(App.ActiveDocument)]
    h.check("Esc drops the design's new rules", names == ["PC 2 mm"], names)
    rule = plastic.find_rule(App.ActiveDocument, "PC 2 mm")
    h.check("the earlier edit (OK'd) stays", rule["thickness"] == "2.5", rule["thickness"])


def assign_cover():
    h.ribbon("Assign Plastic Rule")


def click_cover_body():
    ps.click_row("CoverBody")


def cover_picked():
    p = ps.assign_panel()
    h.check(
        "clicking a body picks its component",
        p is not None and p.combo.currentText() == "Cover",
        p and p.combo.currentText(),
    )
    ps.click_tree_row(p.rules.tree, "FDM PLA 2 mm", "Library")


def cover_ok():
    ps.ok()


def cover_assigned():
    from sciforge import material, plastic

    doc = App.ActiveDocument
    cover = doc.getObject(s["cover"])
    h.check(
        "the Cover follows its own rule",
        plastic.assigned_rule_name(doc, doc.getObject(s["comp"])) == "FDM PLA 2 mm",
    )
    h.check("its body's rule: PLA, no draft", plastic.default_for(cover, "draft_angle") == 0.0)
    h.check("its body is PLA", material.key_of(cover) == "pla", material.key_of(cover))
    h.check("the root keeps PC", plastic.assigned_rule_name(doc, None) == "PC 2 mm")


def rule_fillet():
    from sciforge import bodies

    bodies.set_active_body(body())
    Gui.Selection.clearSelection()
    ps.menu("MODIFY", "Rule Fillet")


def rule_fillet_open():
    from sciforge import fillet_ui

    p = fillet_ui.BlendPanel.last
    h.check("the Fillet dialog opens", p is not None and not p._closed)
    if p is None:
        return
    h.check("in its Rule Fillet mode", p.mode == "rule", p.mode)
    h.check(
        "radius = the rule's nominal radius (2.5 / 2)",
        abs(p.spec.get("radius", 0) - 1.25) < 1e-9,
        p.spec.get("radius"),
    )
    h.shot("3-rule-fillet")


def esc_fillet():
    ps.esc()


def save():
    path = os.path.join(tempfile.mkdtemp(prefix="sf-plastic-"), "PlasticRules.FCStd")
    s["path"] = path
    App.ActiveDocument.saveAs(path)


def reopen():
    App.closeDocument(App.ActiveDocument.Name)
    App.openDocument(s["path"])
    h.fit()


def reopened():
    from sciforge import plastic

    doc = App.ActiveDocument
    h.check(
        "reopened: the design's rules",
        sorted(r["name"] for r in plastic.design_rules(doc)) == ["FDM PLA 2 mm", "PC 2 mm"],
    )
    h.check("reopened: the root's rule", plastic.assigned_rule_name(doc, None) == "PC 2 mm")
    h.check(
        "reopened: the Cover's rule",
        plastic.assigned_rule_name(doc, doc.getObject(s["comp"])) == "FDM PLA 2 mm",
    )
    ps.clear_library_prefs()


h.run(
    "plastic_rules",
    [
        setup,
        assign,
        assign_open,
        pick_pc,
        pc_picked,
        assign_ok,
        assigned,
        undo_assign,
        assign_undone,
        redo_assign,
        assign_redone,
        browser_row,
        row_opens_assign,
        shell,
        shell_default,
        click_top,
        shell_ok,
        shelled,
        manage,
        manage_open,
        pick_design_rule,
        click_edit,
        editor_open,
        type_bad_range,
        save_bad,
        bad_refused,
        type_good,
        save_good,
        saved,
        delete_in_use,
        in_use_refused,
        delete_default,
        default_refused,
        manage_ok,
        shell_again,
        shell_follows_rule,
        esc_shell,
        draft,
        draft_follows_rule,
        rib,
        rib_follows_rule,
        extrude,
        extrude_follows_rule,
        no_rule_no_change,
        manage_again,
        new_rule,
        new_editor,
        save_new,
        copy_new,
        three_rules,
        set_default,
        default_set,
        esc_manage,
        dropped,
        assign_cover,
        click_cover_body,
        cover_picked,
        cover_ok,
        cover_assigned,
        rule_fillet,
        rule_fillet_open,
        esc_fillet,
        save,
        reopen,
        reopened,
    ],
)
