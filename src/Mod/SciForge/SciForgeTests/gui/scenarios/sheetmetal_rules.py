# SPDX-License-Identifier: LGPL-2.1-or-later
"""SHEET METAL > MODIFY > Sheet Metal Rules like a Fusion user, only real input.

A base flange (50 x 30 sketch, 1 mm Steel (mm) plate). Sheet Metal Rules from the ribbon: the
design lists Steel (mm) (active), the library SciForge's eight rules with Steel (mm) as the
Default. Edit Steel (mm): Thickness 2, Save: the plate is 2 mm (the body follows its rule).
K Factor 1.5 is refused with the reason, a name already used is refused. Delete Steel (mm) is
refused while the body uses it. Library: Edit on a built-in rule is refused; Copy to Design
of Aluminum (mm); New from it (keeps mm), named "My Alu", Thickness Thickness-expression,
Save into the library, then Delete it. Set Active Aluminum (mm): the Document Settings row
follows; deleting the active rule is refused; Steel active again, Aluminum deleted. Close.
Undo takes the whole visit back (the plate is 1 mm again); Redo.
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
    App.newDocument("SheetRules")
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


def plate():
    h.check("a 1 mm plate", s["body"] is not None and sm.near(sm.volume(s["body"]), 1500.0))


def open_rules():
    h.ribbon("Sheet Metal Rules")


def rules_open():
    d = sm.rules_dialog()
    h.check("Sheet Metal Rules open", d is not None)
    if d is None:
        return
    h.check("no pop-up besides it", len(h.popups()) <= 1, h.popups())
    design = [d.design.item(i).text() for i in range(d.design.count())]
    library = [d.library.item(i).text() for i in range(d.library.count())]
    h.check("In This Design: Steel (mm), active", design == ["Steel (mm) (active)"], design)
    h.check("Library: eight rules", len(library) == 8, library)
    h.check("Steel (mm) is the library default", "Steel (mm) (Default)" in library, library)
    h.shot("1-rules")


def edit_steel():
    sm.pick_rule("design", "Steel (mm)")
    sm.click_rules_button("design_edit")


def editor_open():
    d = sm.rules_dialog()
    h.check("the rule's fields", d is not None and d.pages.currentIndex() == 1)
    h.check("thickness shown with its unit", d.fields["thickness"].text() == "1.0 mm")
    h.check("bend radius follows Thickness", d.fields["bend_radius"].text() == "Thickness")
    h.check("units fixed for an existing rule", not d.units_field.isEnabled())
    h.shot("2-editor")


def bad_k():
    sm.rule_field("k_factor", "1.5")
    sm.click_rules_button("save")


def k_refused():
    d = sm.rules_dialog()
    h.check("K 1.5 refused", "between 0 and 1" in sm.rules_message(), sm.rules_message())
    h.check("still editing", d.pages.currentIndex() == 1)


def thickness_2():
    sm.rule_field("k_factor", "0.44")
    sm.rule_field("thickness", "2")
    sm.click_rules_button("save")


def plate_2mm():
    d = sm.rules_dialog()
    h.check("saved: back to the lists", d.pages.currentIndex() == 0, sm.rules_message())
    h.check(
        "the plate follows its rule: 2 mm",
        sm.near(sm.volume(s["body"]), 3000.0),
        sm.volume(s["body"]),
    )


def delete_used():
    sm.pick_rule("design", "Steel (mm)")
    sm.click_rules_button("design_delete")


def delete_refused():
    h.check("in use: refused", "used by" in sm.rules_message(), sm.rules_message())
    d = sm.rules_dialog()
    h.check("still listed", d.design.count() == 1)


def edit_builtin():
    sm.pick_rule("library", "Aluminum (mm)")
    sm.click_rules_button("library_edit")


def builtin_refused():
    h.check("built-in rules are not edited", "built-in" in sm.rules_message(), sm.rules_message())


def copy_to_design():
    sm.click_rules_button("library_copy")


def copied():
    d = sm.rules_dialog()
    names = [d.design.item(i).data(256) for i in range(d.design.count())]
    h.check("Aluminum (mm) in this design", "Aluminum (mm)" in names, names)


def new_in_library():
    sm.pick_rule("library", "Aluminum (mm)")
    sm.click_rules_button("library_new")


def new_editor():
    d = sm.rules_dialog()
    h.check(
        "a new rule from Aluminum (mm)",
        d.name_field.text() == "Aluminum (mm) 2",
        d.name_field.text(),
    )
    h.check("units can be chosen for a new rule", d.units_field.isEnabled())
    sm.rule_field("name", "Steel (mm)")
    sm.click_rules_button("save")


def duplicate_refused():
    h.check("a used name is refused", "already" in sm.rules_message(), sm.rules_message())
    sm.rule_field("name", "My Alu")
    sm.rule_field("thickness", "3")
    sm.rule_field("bend_radius", "Thickness / 2")
    sm.click_rules_button("save")


def my_alu():
    from sciforge import sheetmetal_rules

    rule = sheetmetal_rules.find_library_rule("My Alu")
    h.check("My Alu in the library", rule is not None and rule["thickness"] == "3", rule)
    h.check("its radius an expression", rule is not None and rule["bend_radius"] == "Thickness / 2")
    sm.pick_rule("library", "My Alu")
    sm.click_rules_button("library_delete")


def my_alu_gone():
    from sciforge import sheetmetal_rules

    h.check("My Alu deleted", sheetmetal_rules.find_library_rule("My Alu") is None)


def set_active():
    sm.pick_rule("design", "Aluminum (mm)")
    sm.click_rules_button("design_set")


def active_changed():
    from sciforge import sheetmetal

    h.check("Aluminum (mm) active", sheetmetal.active_rule_name(sm.doc()) == "Aluminum (mm)")
    d = sm.rules_dialog()
    texts = [d.design.item(i).text() for i in range(d.design.count())]
    h.check("marked in the list", "Aluminum (mm) (active)" in texts, texts)
    sm.pick_rule("design", "Aluminum (mm)")
    sm.click_rules_button("design_delete")


def active_refused():
    h.check(
        "the active rule is not deleted", "active rule" in sm.rules_message(), sm.rules_message()
    )
    sm.pick_rule("design", "Steel (mm)")
    sm.click_rules_button("design_set")


def delete_aluminum():
    sm.pick_rule("design", "Aluminum (mm)")
    sm.click_rules_button("design_delete")


def aluminum_gone():
    d = sm.rules_dialog()
    names = [d.design.item(i).data(256) for i in range(d.design.count())]
    h.check("Aluminum (mm) deleted", names == ["Steel (mm)"], names)


def close():
    sm.click_rules_button("close")


def closed():
    h.check("dialog closed", sm.rules_dialog() is None)
    h.check("still 2 mm", sm.near(sm.volume(s["body"]), 3000.0))
    h.shot("3-closed")


def undo():
    sm.undo()


def undone():
    from sciforge import sheetmetal

    body = s["body"]
    tip = body.Tip
    detail = (
        sm.volume(body),
        body.Shape.isNull(),
        list(tip.State) if tip else None,
        tip.Shape.Volume if tip and not tip.Shape.isNull() else None,
        sheetmetal.find_rule(sm.doc(), "Steel (mm)")["thickness"],
        sm.doc().UndoNames,
        sm.doc().RedoNames,
    )
    h.check("undo: the plate 1 mm again", sm.near(sm.volume(s["body"]), 1500.0), detail)


def redo():
    sm.redo()


def redone():
    h.check("redo: 2 mm", sm.near(sm.volume(s["body"]), 3000.0), sm.volume(s["body"]))


h.run(
    "sheetmetal_rules",
    [
        new_design,
        create_sketch,
        pick_xy,
        draw_rect,
        finish_sketch,
        flange,
        click_profile,
        ok_plate,
        plate,
        open_rules,
        rules_open,
        edit_steel,
        editor_open,
        bad_k,
        k_refused,
        thickness_2,
        plate_2mm,
        delete_used,
        delete_refused,
        edit_builtin,
        builtin_refused,
        copy_to_design,
        copied,
        new_in_library,
        new_editor,
        duplicate_refused,
        my_alu,
        my_alu_gone,
        set_active,
        active_changed,
        active_refused,
        delete_aluminum,
        aluminum_gone,
        close,
        closed,
        undo,
        undone,
        redo,
        redone,
    ],
)
