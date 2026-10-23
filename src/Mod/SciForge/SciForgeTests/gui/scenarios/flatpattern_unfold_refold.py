# SPDX-License-Identifier: LGPL-2.1-or-later
"""Unfold, cut across the bend, Refold, the way a Fusion user does it, real input only:
SHEET METAL > Unfold with nothing picked (the dialog waits), a click on the bracket's top
face (Stationary Entity), a click on the inside of the bend (Bends): the bracket lies flat
(98.26195 long), Unfold All Bends ticked gives the same, OK: "Unfold" in the timeline. A
sketch on XY with a 2 x 10 slot on the bend's centre line, E, 5 mm: the slot is cut through
the flat sheet. SHEET METAL > Refold, OK: the bracket is folded again with the slot carried
into the bend (it spans 2 / 1.44 rad there: (2 / 1.44) (2^2 - 1^2) / 2 * 10 removed); the
Unfold ... Refold steps are one timeline group. Undo / redo; Refold with nothing unfolded
says why and opens nothing; Edit the Unfold from the timeline (its picks come back),
Cancel leaves the part as it was."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import flatpattern_steps as fs
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}
SLOT_X = 48 + fs.BA / 2
SLOT_REMOVED = (2 / 1.44) * (4 - 1) / 2 * 10
BEND_INSIDE = V(48.70711, -10, 1.29289)  # the inner bend face, half way round


def setup():
    fs.setup_l("FlatUnfold")
    s["folded"] = fs.volume()


def sheet_tab():
    fs.tab("sheet_metal")


def start_unfold():
    Gui.Selection.clearSelection()
    h.ribbon("Unfold")


def waiting():
    p = fs.sheet_panel()
    h.check("Unfold dialog open", p is not None and fs.dialog_open())
    text = fs.message()
    h.check("asks for the stationary face", "Stationary" in text, text)
    h.check("Unfold All Bends off by default (Fusion)", p is not None and not p.all_bends.isChecked())
    h.check("model unchanged while waiting", fs.close(fs.volume(), s["folded"]))
    fs.no_popups("Unfold")


def click_top():
    h.fit()
    h.click(fs.L_TOP)


def asks_bends():
    fs.settle()
    p = fs.sheet_panel()
    h.check("stationary face picked", p is not None and len(p.picks["face"]) == 1, p and p.picks)
    text = fs.message()
    h.check("asks for the bends", "bends" in text, text)
    h.check("no step yet", p is not None and p.target is None)


def look_at_bend():
    view = Gui.ActiveDocument.ActiveView
    view.setViewDirection((1, 1, -1))
    view.fitAll()


def click_bend():
    h.click(BEND_INSIDE)


def unfolded():
    fs.settle()
    p = fs.sheet_panel()
    h.check("one bend picked", p is not None and len(p.picks["bends"]) == 1, p and p.picks)
    t = p.target if p is not None else None
    h.check("preview step made", t is not None)
    if t is None:
        return
    bb = t.Shape.BoundBox
    h.check("the bracket lies flat: 98.26195 long", fs.close(bb.XLength, fs.L_FLAT), bb)
    h.check("one sheet thick", fs.close(bb.ZLength, 1.0), bb)
    h.check("no message", "⚠" not in fs.message(), fs.message())
    h.shot("1-unfolded")


def tick_all():
    p = fs.sheet_panel()
    if p is not None:
        fs.click_check(p.all_bends)


def all_unfolded():
    fs.settle()
    p = fs.sheet_panel()
    h.check("Unfold All Bends ticked", p is not None and p.all_bends.isChecked())
    t = p.target if p is not None else None
    bb = t.Shape.BoundBox if t is not None else None
    h.check("still flat with every bend", bb is not None and fs.close(bb.XLength, fs.L_FLAT), bb)


def ok_unfold():
    fs.ok()


def after_unfold():
    fs.settle()
    h.check("dialog closed", not fs.dialog_open())
    titles = fs.timeline_titles()
    h.check("Unfold in the timeline", any(t.startswith("Unfold") for t in titles), titles)
    v = fs.volume()
    h.check("body flat: 98.26195 x 20 x 1", fs.close(v, fs.L_FLAT * 20), v)


def new_sketch():
    from sciforge import sketch_ui

    body = fs.body()
    planes = sketch_ui.origin_planes(body)
    s["sketch"] = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    App.ActiveDocument.recompute()


def edit_sketch():
    if h.in_sketch() is None and s.get("sketch") is not None:
        Gui.ActiveDocument.setEdit(s["sketch"].Name)


def draw_slot():
    sk = h.in_sketch() or s.get("sketch")
    h.check("sketch open", sk is not None)
    if sk is not None:
        h.draw_rectangle(sk, SLOT_X - 1, -15, SLOT_X + 1, -5)


def finish_sketch():
    h.ribbon("Finish Sketch")


def extrude():
    h.fit()
    h.press("e")


def extrude_distance():
    from sciforge import taskui

    p = taskui.current()
    field = getattr(getattr(p, "distance", None), "widget", None)
    h.check("Extrude dialog open", field is not None)
    if field is not None:
        ui.type_into(field, "5")


def extrude_ok():
    fs.ok()


def slot_cut():
    fs.settle()
    v = fs.volume()
    h.check("2 x 10 slot cut through the flat sheet", fs.close(v, fs.L_FLAT * 20 - 20), v)
    s["flat_cut"] = v


def refold():
    Gui.Selection.clearSelection()
    h.ribbon("Refold")


def refold_dialog():
    fs.settle()
    p = fs.refold_panel()
    h.check("Refold dialog open", p is not None and fs.dialog_open())
    v = fs.volume()
    h.check("preview: folded with the slot in the bend", fs.close(v, s["folded"] - SLOT_REMOVED), v)


def ok_refold():
    fs.ok()


def refolded():
    fs.settle()
    v = fs.volume()
    h.check("refolded volume", fs.close(v, s["folded"] - SLOT_REMOVED), v)
    bb = fs.body().Shape.BoundBox
    h.check("folded again: 50 x 20 x 50", fs.close(bb.XLength, 50) and fs.close(bb.ZLength, 50), bb)
    from sciforge import timeline_ops

    items = timeline_ops.timeline(App.ActiveDocument, deps=False).items
    groups = {i.kind: i.group for i in items if i.kind in ("unfold", "refold")}
    h.check("Refold in the timeline", "refold" in groups, [i.kind for i in items])
    h.check(
        "Unfold and Refold grouped",
        groups.get("unfold") and groups.get("unfold") == groups.get("refold"),
        groups,
    )
    h.shot("2-refolded")


def undo():
    fs.undo()


def undone():
    v = fs.volume()
    h.check("undo: flat with the slot again", fs.close(v, s["flat_cut"]), v)


def redo():
    fs.redo()


def redone():
    v = fs.volume()
    h.check("redo: refolded again", fs.close(v, s["folded"] - SLOT_REMOVED), v)


def refold_nothing():
    Gui.Selection.clearSelection()
    h.ribbon("Refold")


def nothing_to_refold():
    h.check("Refold with nothing unfolded opens no dialog", not fs.dialog_open())
    fs.no_popups("Refold with nothing to refold")


def open_group():
    from sciforge import timeline_ui
    from SciForgeTests.gui import widget_input as w

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
    h.check("Unfold step shown in the open folder", bool(titles), fs.timeline_titles())
    if titles:
        fs.double_click_timeline(titles[0])


def edit_open():
    fs.settle()
    p = fs.sheet_panel()
    h.check("Edit Unfold dialog open", p is not None and p.editing)
    h.check("its stationary face is back", p is not None and len(p.picks["face"]) == 1)
    h.check("Unfold All Bends still ticked", p is not None and p.all_bends.isChecked())


def edit_cancel():
    fs.cancel()


def after_cancel():
    fs.settle()
    h.check("Cancel: dialog closed", not fs.dialog_open())
    v = fs.volume()
    h.check("Cancel leaves the refolded part", fs.close(v, s["folded"] - SLOT_REMOVED), v)


h.run(
    "flatpattern_unfold_refold",
    [
        setup,
        sheet_tab,
        start_unfold,
        waiting,
        click_top,
        asks_bends,
        look_at_bend,
        click_bend,
        unfolded,
        tick_all,
        all_unfolded,
        ok_unfold,
        after_unfold,
        new_sketch,
        edit_sketch,
        draw_slot,
        finish_sketch,
        extrude,
        extrude_distance,
        extrude_ok,
        slot_cut,
        refold,
        refold_dialog,
        ok_refold,
        refolded,
        undo,
        undone,
        redo,
        redone,
        refold_nothing,
        nothing_to_refold,
        open_group,
        edit_unfold,
        edit_open,
        edit_cancel,
        after_cancel,
    ],
)
_unused = QtCore
