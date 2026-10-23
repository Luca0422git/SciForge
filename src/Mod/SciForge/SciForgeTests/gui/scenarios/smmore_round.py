# SPDX-License-Identifier: LGPL-2.1-or-later
"""SHEET METAL > MODIFY > Fillet and Chamfer (sheet metal) the way a Fusion user does it, only
real input: the MODIFY menu's Fillet; a click on a top edge is not taken (only the corners
through the thickness light up); a corner at 5 mm, "+ New Set", another corner at 10 mm
(volumes worked out by hand); OK; Fillet 1 in the timeline; Ctrl+Z / Ctrl+Y; the Chamfer at
4 mm on a third corner; edit the fillet from the timeline (its two sets come back)."""

import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import smmore_steps as st

V = App.Vector
s = {}
FLAT = 6000.0


def cut(r):
    return r * r - math.pi * r * r / 4.0


def fillet_panel():
    from sciforge import sheetmetal_corner_round_ui

    return st.panel(sheetmetal_corner_round_ui.RoundPanel)


def chamfer_panel():
    from sciforge import sheetmetal_corner_round_ui

    return st.panel(sheetmetal_corner_round_ui.ChamferPanel)


def vol():
    return st.volume(s["body"])


def setup():
    st.new_design("SmRound")
    s["body"], _p = st.plate(0, 0, 100, 60)
    h.fit()


def open_fillet():
    Gui.Selection.clearSelection()
    st.tab()
    st.menu("MODIFY", "Fillet")


def waiting():
    p = fillet_panel()
    h.check("sheet metal Fillet dialog open", p is not None)


def click_top_edge():
    h.fit()
    h.click_edge(V(50, 0, 1))


def not_taken():
    p = fillet_panel()
    h.check(
        "a top edge is not taken (only corners)",
        p is not None and p.picks["edges"] == [],
        p and p.picks,
    )


def click_corner():
    h.click_edge(V(0, 0, 0.5))


def type_5():
    p = fillet_panel()
    h.check("the corner is taken", p is not None and len(p.picks["edges"]) == 1, p and p.picks)
    st.type_into(p, "value", "5")


def rounded():
    p = fillet_panel()
    st.settle(p)
    h.check("5 mm corner round", st.close(vol(), FLAT - cut(5)), (vol(), FLAT - cut(5)))


def new_set():
    ui.click(fillet_panel().new_set)


def click_second():
    p = fillet_panel()
    h.check(
        "set 1 kept, the box empty again",
        p is not None and len(p.sets) == 1 and p.picks["edges"] == [],
        p and (p.sets, p.picks),
    )
    h.click_edge(V(100, 0, 0.5))


def type_10():
    st.type_into(fillet_panel(), "value", "10")


def two_sets():
    p = fillet_panel()
    st.settle(p)
    want = FLAT - cut(5) - cut(10)
    h.check("two sets: 5 mm and 10 mm", st.close(vol(), want), (vol(), want))
    h.check("the sets are listed", "Set 1" in p.sets_label.text(), p.sets_label.text())
    h.shot("smmore-round-1-sets")


def ok():
    st.ok()


def after_ok():
    steps = st.steps("SheetMetalFillet")
    h.check("one sheet metal Fillet step", len(steps) == 1, steps)
    h.check("timeline shows Fillet 1", "Fillet 1" in st.timeline_titles(), st.timeline_titles())
    s["filleted"] = vol()


def undo():
    st.undo()


def after_undo():
    h.check("Ctrl+Z: square corners again", st.close(vol(), FLAT))


def redo():
    st.redo()


def after_redo():
    h.check("Ctrl+Y: rounded again", st.close(vol(), s["filleted"]))


def open_chamfer():
    Gui.Selection.clearSelection()
    st.menu("MODIFY", "Chamfer")


def chamfer_corner():
    p = chamfer_panel()
    h.check("sheet metal Chamfer dialog open", p is not None)
    h.fit()
    h.click_edge(V(100, 60, 0.5))


def type_4():
    st.type_into(chamfer_panel(), "value", "4")


def chamfered():
    p = chamfer_panel()
    st.settle(p)
    h.check("4 mm chamfer", st.close(vol(), s["filleted"] - 8.0), vol())
    st.ok()


def after_chamfer():
    h.check("one Chamfer step", len(st.steps("SheetMetalChamfer")) == 1)
    s["chamfered"] = vol()


def edit():
    st.double_click_timeline("Fillet 1")


def edit_open():
    p = fillet_panel()
    h.check(
        "edit opens with set 1 kept and set 2 in the box",
        p is not None and p.editing and len(p.sets) == 1 and len(p.picks["edges"]) == 1,
        p and (p.sets, p.picks),
    )
    h.check("set 2's radius back", p is not None and abs(p.value("value") - 10.0) < 1e-6)
    if p:
        st.type_into(p, "value", "8")


def edit_ok():
    st.settle(fillet_panel())
    st.ok()


def after_edit():
    want = s["chamfered"] + cut(10) - cut(8)
    h.check("set 2 now 8 mm, the chamfer kept", st.close(vol(), want), (vol(), want))


h.run(
    "smmore_round",
    [
        setup,
        open_fillet,
        waiting,
        click_top_edge,
        not_taken,
        click_corner,
        type_5,
        rounded,
        new_set,
        click_second,
        type_10,
        two_sets,
        ok,
        after_ok,
        undo,
        after_undo,
        redo,
        after_redo,
        open_chamfer,
        chamfer_corner,
        type_4,
        chamfered,
        after_chamfer,
        edit,
        edit_open,
        edit_ok,
        after_edit,
    ],
)
