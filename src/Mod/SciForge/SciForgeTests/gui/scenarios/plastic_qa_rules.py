# SPDX-License-Identifier: LGPL-2.1-or-later
"""QA paths of the plastic rules the builder's scenario does not walk, real input only.

An empty design: Assign Plastic Rule opens and gives the design the default rule (Ctrl+Z
takes it away), Manage Plastic Rules opens and Esc closes it, Rule Fillet says it needs a
solid. Then a 60 x 40 x 10 part: assign ABS 2 mm, Shell with the rule's wall; assign
another rule (ABS 1.5 mm) and the Shell follows it, Ctrl+Z puts both back; Manage, edit
the rule to 3 mm (the Shell follows while the dialog is open), Esc drops the edit and the
Shell's wall; rename the rule in Manage (the design keeps it assigned under its new name,
the browser row says so), Ctrl+Z puts the old name back. Last, a 40 x 30 x 10 box with
PP 1.5 mm (draft 1.5 deg): Draft opens with 1.5 deg, the front face drafted, OK; the 3D-print
rule FDM PLA 2 mm has no draft (0 deg): the Draft step keeps its 1.5 deg (a draft of 0 is
no draft: it stays valid) and a new Draft opens with its own 1 deg, not 0 (which it
refuses); ABS 2 mm (1 deg) then moves the linked Draft to 1 deg."""

import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import plastic_steps as ps
from SciForgeTests.gui import shell_draft_steps as sd

V = App.Vector
s = {}

SHELL_2 = 24000 - 56 * 36 * 8  # 60 x 40 x 10 shelled 2 mm, top open
SHELL_15 = 24000 - 57 * 37 * 8.5
SHELL_3 = 24000 - 54 * 34 * 7


# -- an empty design -------------------------------------------------------------------------------
def empty():
    ps.clear_library_prefs()
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("PlasticQAEmpty")
    ps.plastic_tab()
    Gui.Selection.clearSelection()
    h.ribbon("Assign Plastic Rule")


def empty_assign_open():
    p = ps.assign_panel()
    h.check("empty design: Assign opens", p is not None)
    if p is None:
        return
    h.check(
        "the only component is the design",
        p.combo.count() == 1 and p.combo.currentText() == "PlasticQAEmpty",
        p.combo.currentText(),
    )
    h.check("the library's default picked", p.rules.current() == ("library", "Default (mm)"))
    h.check("no error", p.message.text() == "", p.message.text())


def empty_assign_ok():
    ps.ok()


def empty_assigned():
    from sciforge import plastic

    doc = App.ActiveDocument
    h.check("dialog closed", ps.assign_panel() is None)
    h.check("the design has the default rule", plastic.assigned_rule_name(doc) == "Default (mm)")


def empty_undo():
    ps.undo()


def empty_undone():
    from sciforge import plastic

    doc = App.ActiveDocument
    h.check("Ctrl+Z: no rule", plastic.assigned_rule_name(doc) == "")
    h.check("Ctrl+Z: no design rule left", plastic.design_rules(doc) == [])


def empty_manage():
    ps.menu("SETUP", "Manage Plastic Rules")


def empty_manage_open():
    p = ps.manage_panel()
    h.check("empty design: Manage opens", p is not None)
    if p is None:
        return
    h.check("In This Design is empty", p.rules.design.childCount() == 0)
    h.check("the library is listed", p.rules.library.childCount() == 16)
    ps.esc()


def empty_manage_closed():
    h.check("Esc closes Manage", ps.manage_panel() is None and not Gui.Control.activeDialog())
    ps.menu("MODIFY", "Rule Fillet")


def empty_rule_fillet():
    from sciforge import fillet_ui

    p = fillet_ui.FilletPanel.last
    h.check(
        "Rule Fillet with no part: no dialog",
        not Gui.Control.activeDialog() and (p is None or p._closed),
    )
    App.closeDocument(App.ActiveDocument.Name)


# -- a part with a rule ----------------------------------------------------------------------------
def setup():
    from sciforge import bodies

    ps.clear_library_prefs()
    doc = App.newDocument("PlasticQARules")
    body = ps.box_body(doc, "Case", 0, 10, "top", shell=False)
    doc.recompute()
    bodies.set_active_body(body)
    s.update(body=body.Name)
    h.check("part made", ps.near(ps.volume(body), 24000.0, 1e-6), ps.volume(body))
    h.fit()
    ps.plastic_tab()


def body():
    return App.ActiveDocument.getObject(s["body"])


def assign():
    Gui.Selection.clearSelection()
    h.ribbon("Assign Plastic Rule")


def pick_abs2():
    ps.click_tree_row(ps.assign_panel().rules.tree, "ABS 2 mm", "Library")


def ok():
    ps.ok()


def assigned_abs2():
    from sciforge import plastic

    h.check("ABS 2 mm assigned", plastic.assigned_rule_name(App.ActiveDocument) == "ABS 2 mm")


def shell():
    Gui.Selection.clearSelection()
    h.ribbon("Shell")


def click_top():
    p = sd.shell_panel()
    h.check("Shell opens with the rule's 2 mm", p and abs(p.inside.value() - 2.0) < 1e-9)
    h.fit()
    h.click(V(30, 20, 10))


def shell_ok():
    ps.settle(sd.shell_panel())
    ps.ok()


def shelled():
    v = ps.volume(body())
    h.check("shelled 2 mm", ps.near(v, SHELL_2, 1e-6), v)


def pick_abs15():
    p = ps.assign_panel()
    h.check(
        "Assign shows the rule assigned now",
        p is not None and "ABS 2 mm" in p.info.text() and p.rules.current()[1] == "ABS 2 mm",
        p and (p.info.text(), p.rules.current()),
    )
    ps.click_tree_row(p.rules.tree, "ABS 1.5 mm", "Library")


def followed_15():
    from sciforge import plastic

    doc = App.ActiveDocument
    h.check("ABS 1.5 mm assigned", plastic.assigned_rule_name(doc) == "ABS 1.5 mm")
    v = ps.volume(body())
    h.check("the Shell follows the new rule's 1.5 mm wall", ps.near(v, SHELL_15, 1e-6), v)


def undo():
    ps.undo()


def back_to_2():
    from sciforge import plastic

    doc = App.ActiveDocument
    h.check("Ctrl+Z: ABS 2 mm again", plastic.assigned_rule_name(doc) == "ABS 2 mm")
    v = ps.volume(body())
    h.check("Ctrl+Z: the Shell's 2 mm wall again", ps.near(v, SHELL_2, 1e-6), v)


def manage():
    Gui.Selection.clearSelection()
    ps.menu("SETUP", "Manage Plastic Rules")


def edit_abs2():
    p = ps.manage_panel()
    h.check("Manage open", p is not None)
    ps.click_tree_row(p.rules.tree, "ABS 2 mm", "In This Design")
    ps.click(p.buttons["edit"])


def type_3():
    p = ps.manage_panel()
    ps.type_into(p.fields["thickness"], "3")
    ps.click(p.save_button)


def followed_3():
    p = ps.manage_panel()
    h.check("saved in the dialog", p is not None and p.message.text() == "", p and p.message.text())
    v = ps.volume(body())
    h.check("the Shell follows at once (3 mm)", ps.near(v, SHELL_3, 1e-6), v)


def esc():
    ps.esc()


def esc_dropped():
    from sciforge import plastic

    doc = App.ActiveDocument
    h.check("Esc closed Manage", ps.manage_panel() is None)
    rule = plastic.find_rule(doc, "ABS 2 mm")
    h.check("Esc: the rule is 2 mm again", rule and rule["thickness"] == "2.0", rule)
    v = ps.volume(body())
    h.check("Esc: the Shell's 2 mm wall again", ps.near(v, SHELL_2, 1e-6), v)


def type_name():
    p = ps.manage_panel()
    ps.type_into(p.fields["name"], "Case rule")
    ps.click(p.save_button)


def renamed():
    from sciforge import plastic
    from SciForgeTests.gui import timeline_input as tl

    doc = App.ActiveDocument
    h.check("Manage closed", ps.manage_panel() is None)
    names = [r["name"] for r in plastic.design_rules(doc)]
    h.check("the design's rule renamed", names == ["Case rule"], names)
    h.check("the design keeps it assigned", plastic.assigned_rule_name(doc) == "Case rule")
    h.check("the rule still drives the tools", plastic.default_for(body(), "thickness") == 2.0)
    labels = tl.labels()
    h.check("the browser row has the new name", "Plastic Rule: Case rule" in labels, labels)
    v = ps.volume(body())
    h.check("the Shell unchanged", ps.near(v, SHELL_2, 1e-6), v)


def rename_undone():
    from sciforge import plastic

    doc = App.ActiveDocument
    names = [r["name"] for r in plastic.design_rules(doc)]
    h.check("Ctrl+Z: the old name", names == ["ABS 2 mm"], names)
    h.check("Ctrl+Z: assigned under it", plastic.assigned_rule_name(doc) == "ABS 2 mm")
    ps.clear_library_prefs()


# -- a Draft linked to a rule, and a rule without draft (the 3D-print rules) -------------------
def tan(a):
    return math.tan(math.radians(a))


def front_drafted(a):
    """The 40 x 30 x 10 box with its front face drafted by a about the XY plane."""
    return sd.BOX - 40 * 100.0 * tan(a) / 2.0


def assign_rule(name):
    def step():
        ps.plastic_tab()
        Gui.Selection.clearSelection()
        h.ribbon("Assign Plastic Rule")
        ps.settle(ps.assign_panel())
        ps.click_tree_row(ps.assign_panel().rules.tree, name, "Library")
        ps.ok()

    step.__name__ = "assign_" + name.replace(" ", "_").replace(".", "_")
    return step


def draft():
    Gui.Selection.clearSelection()
    h.ribbon("Draft")


def draft_from_pp():
    p = sd.draft_panel()
    h.check("Draft opens with PP's 1.5 deg", p and abs(p.angle.value() - 1.5) < 1e-9)
    h.fit()
    pl.click_square("XY_Plane")


def click_front():
    h.fit()
    h.click(V(20, 0, 5))


def draft_ok():
    ps.settle(sd.draft_panel())
    p = sd.draft_panel()
    h.check("no error", p is not None and p.message.text() == "", p and p.message.text())
    ps.ok()


def drafted_15():
    v = h.solid_volume()
    h.check("front face drafted 1.5 deg", sd.close(v, front_drafted(1.5)), v)


def pla_keeps_draft():
    from sciforge import plastic

    doc = App.ActiveDocument
    h.check("FDM PLA 2 mm assigned", plastic.assigned_rule_name(doc) == "FDM PLA 2 mm")
    steps = sd.drafts()
    h.check(
        "the Draft step stays valid",
        steps and all("Invalid" not in o.State and "Error" not in o.State for o in steps),
        [o.State for o in steps],
    )
    v = h.solid_volume()
    h.check(
        "and keeps its 1.5 deg (no draft is not a draft angle)", sd.close(v, front_drafted(1.5)), v
    )


def draft_own_default():
    p = sd.draft_panel()
    h.check(
        "a new Draft opens with its own 1 deg, not the rule's 0",
        p and abs(p.angle.value() - 1.0) < 1e-9,
        p and p.angle.value(),
    )
    ps.esc()


def abs_moves_draft():
    v = h.solid_volume()
    h.check("ABS 2 mm: the linked Draft follows to 1 deg", sd.close(v, front_drafted(1.0)), v)
    ps.clear_library_prefs()


h.run(
    "plastic_qa_rules",
    [
        empty,
        empty_assign_open,
        empty_assign_ok,
        empty_assigned,
        empty_undo,
        empty_undone,
        empty_manage,
        empty_manage_open,
        empty_manage_closed,
        empty_rule_fillet,
        setup,
        assign,
        pick_abs2,
        ok,
        assigned_abs2,
        shell,
        click_top,
        shell_ok,
        shelled,
        assign,
        pick_abs15,
        ok,
        followed_15,
        undo,
        back_to_2,
        manage,
        edit_abs2,
        type_3,
        followed_3,
        esc,
        esc_dropped,
        manage,
        edit_abs2,
        type_name,
        ok,
        renamed,
        undo,
        rename_undone,
    ]
    + sd.box_steps("PlasticQADraft")
    + [
        assign_rule("PP 1.5 mm"),
        draft,
        draft_from_pp,
        click_front,
        draft_ok,
        drafted_15,
        assign_rule("FDM PLA 2 mm"),
        pla_keeps_draft,
        draft,
        draft_own_default,
        assign_rule("ABS 2 mm"),
        abs_moves_draft,
    ],
)
