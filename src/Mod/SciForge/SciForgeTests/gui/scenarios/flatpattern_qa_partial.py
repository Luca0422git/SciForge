# SPDX-License-Identifier: LGPL-2.1-or-later
"""Partial Unfold of a U channel, its edit from the timeline, and deleting the Flat Pattern from
the browser (QA paths the builder's scenarios left out), real input only. A U channel 60 x 30 x
20 with a hole in its right wall (setup, converted).

1. SHEET METAL > Unfold, a click on the floor (Stationary Entity) and on the inside of the
   right bend only: the right wall lies flat, the left one stays up (88.26 long: 2 + 56 + BA
   + 28, 30 high), OK. Refold, OK: the channel is folded again (same volume).
2. The Unfold edited from the timeline (its folder opened): Unfold All Bends ticked, OK: two
   bends laid flat, the Refold after it still folds the channel back (valid, same volume).
   Ctrl+Z: one bend again, still folded.
3. Create Flat Pattern (116.52 long), Finish; the browser's Flat Pattern row > Delete: it is
   gone; Ctrl+Z brings it back (116.52 long), Ctrl+Y deletes it again."""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import flatpattern_steps as fs
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}
BEND_INSIDE_U = V(58.70711, -10, 1.29289)  # inside the right bend, half way round
PARTIAL = 2 + 56 + fs.BA + 28


def setup():
    fs.build("FlatQAPartial", fs.U_STEPS, fs.TOP)
    s["folded"] = fs.volume()


def sheet_tab():
    fs.tab("sheet_metal")


# -- 1. one bend of two ----------------------------------------
def unfold():
    Gui.Selection.clearSelection()
    h.ribbon("Unfold")


def click_floor():
    h.fit()
    h.click(fs.U_TOP)


def look_at_bend():
    fs.settle()
    view = Gui.ActiveDocument.ActiveView
    view.setViewDirection((1, 1, -1))
    view.fitAll()


def click_bend():
    h.click(BEND_INSIDE_U)


def one_bend_flat():
    fs.settle()
    p = fs.sheet_panel()
    h.check("one bend picked", p is not None and len(p.picks["bends"]) == 1, p and p.picks)
    t = p.target if p is not None else None
    bb = t.Shape.BoundBox if t is not None else None
    h.check(
        "the right wall lies flat (88.26 long), the left one stays up (30 high)",
        bb is not None and fs.close(bb.XLength, PARTIAL) and fs.close(bb.ZLength, 30),
        bb,
    )
    h.check("1 bend laid flat", t is not None and t.BendCount == 1, t and t.BendCount)
    h.shot("1-one-bend")


def unfold_ok():
    fs.ok()


def refold():
    fs.settle()
    h.check("Unfold closed", not fs.dialog_open())
    Gui.Selection.clearSelection()
    h.ribbon("Refold")


def refold_ok():
    fs.settle()
    h.check("Refold dialog open", fs.refold_panel() is not None)
    fs.ok()


def folded(where="Refold"):
    fs.settle()
    h.check("%s: dialog closed" % where, not fs.dialog_open())
    v = fs.volume()
    h.check("%s: folded channel, same volume" % where, fs.close(v, s["folded"]), v)
    bb = fs.body().Shape.BoundBox
    h.check(
        "%s: 60 x 20 x 30 again" % where,
        fs.close(bb.XLength, 60) and fs.close(bb.ZLength, 30),
        bb,
    )


def refolded():
    folded("Refold")


# -- 2. edit the Unfold from the timeline ----------------------------------------
def open_group():
    from sciforge import timeline_ui
    from SciForgeTests.gui import widget_input as w

    h.fit()
    widget = timeline_ui.widget()
    widget.refresh()
    header = None
    for slot, _left, _right in widget._slots:
        if slot.objectName().startswith("SciForgeGroup_") and slot.name == "Unfold":
            header = slot
    h.check("the Unfold ... Refold folder is in the timeline", header is not None)
    if header is not None:
        w.click(header)


def edit_unfold():
    titles = [t for t in fs.timeline_titles() if t.startswith("Unfold")]
    h.check("Unfold shown in the open folder", bool(titles), fs.timeline_titles())
    if titles:
        fs.double_click_timeline(titles[0])


def edit_open():
    fs.settle()
    p = fs.sheet_panel()
    h.check("Edit Unfold open", p is not None and p.editing)
    h.check("its one bend is back", p is not None and len(p.picks["bends"]) == 1, p and p.picks)
    if p is not None:
        fs.click_check(p.all_bends)


def edit_all():
    fs.settle()
    p = fs.sheet_panel()
    t = p.target if p is not None else None
    h.check("Unfold All Bends ticked", p is not None and p.all_bends.isChecked())
    h.check("preview: 2 bends laid flat", t is not None and t.BendCount == 2, t and t.BendCount)
    fs.ok()


def edited():
    folded("edited Unfold")
    from sciforge import bodies

    unfold = refold_step = None
    for obj in fs.body().Group:
        if bodies.kind(obj) == "Unfold":
            unfold = obj
        elif bodies.kind(obj) == "Refold":
            refold_step = obj
    s["unfold"] = unfold
    h.check("the Unfold lays 2 bends flat", unfold is not None and unfold.BendCount == 2)
    h.check(
        "the Refold after it is valid",
        refold_step is not None and "Invalid" not in refold_step.State,
        refold_step and refold_step.State,
    )


def undo_edit():
    fs.undo()


def edit_undone():
    folded("Ctrl+Z")
    u = s.get("unfold")
    h.check("Ctrl+Z: one bend again", u is not None and u.BendCount == 1, u and u.BendCount)


# -- 3. delete the flat pattern from the browser ----------------------------------------
def flat_pattern():
    Gui.Selection.clearSelection()
    h.ribbon("Create Flat Pattern")


def flat_click():
    h.fit()
    h.click(fs.U_TOP)


def flat_ok():
    fs.settle()
    h.check("the dialog says 116.52", "116.52 x 20.00" in fs.message(), fs.message())
    fs.ok()


def finish():
    fs.settle()
    h.check("FLAT PATTERN tab open", fs.current_tab() == "flat_pattern", fs.current_tab())
    h.ribbon("Finish Flat Pattern")


def delete_row():
    fs.settle()
    h.check("one flat pattern", len(fs.flat_patterns()) == 1)
    fs.browser_menu("Flat Pattern", "Delete")


def deleted():
    fs.settle()
    h.check("Delete: no flat pattern", fs.flat_patterns() == [])
    h.check("the design's tabs", fs.current_tab() != "flat_pattern", fs.current_tab())
    fs.no_popups("Delete Flat Pattern")


def undo_delete():
    fs.undo()


def delete_undone():
    fs.settle()
    bb = fs.flat_box()
    h.check("Ctrl+Z: the flat pattern is back", len(fs.flat_patterns()) == 1)
    h.check("still 116.52 long", bb is not None and fs.close(bb.XLength, fs.U_FLAT), bb)


def redo_delete():
    fs.redo()


def delete_redone():
    fs.settle()
    h.check("Ctrl+Y: deleted again", fs.flat_patterns() == [])
    v = fs.volume()
    h.check("the folded part untouched", fs.close(v, s["folded"]), v)
    fs.no_popups("the partial unfold paths")


h.run(
    "flatpattern_qa_partial",
    [
        setup,
        sheet_tab,
        unfold,
        click_floor,
        look_at_bend,
        click_bend,
        one_bend_flat,
        unfold_ok,
        refold,
        refold_ok,
        refolded,
        open_group,
        edit_unfold,
        edit_open,
        edit_all,
        edited,
        undo_edit,
        edit_undone,
        flat_pattern,
        flat_click,
        flat_ok,
        finish,
        delete_row,
        deleted,
        undo_delete,
        delete_undone,
        redo_delete,
        delete_redone,
    ],
)
