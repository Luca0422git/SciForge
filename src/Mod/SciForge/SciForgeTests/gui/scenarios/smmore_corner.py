# SPDX-License-Identifier: LGPL-2.1-or-later
"""SHEET METAL > MODIFY > Corner Closure the way a Fusion user does it, only real input: a
notched plate with two edge flanges (an open corner), the MODIFY menu's Corner Closure, click
the dominant flange's corner edge then the submissive one's: both are taken in line to half the
rule's gap short of the corner's bisector (Symmetric Gap); Overlap with a 0 gap (the dominant
runs over the other's end); the Round relief is greyed with its reason; OK; the timeline's
Corner Closure 1; Ctrl+Z / Ctrl+Y; edit back to Symmetric Gap; Cancel keeps it."""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import smmore_steps as st

V = App.Vector
s = {}
OUTLINE = [(0, 0), (95, 0), (95, 5), (100, 5), (100, 40), (0, 40)]
DOMINANT = V(100, 5, 12)
SUBMISSIVE = V(95, 0, 12)


def panel():
    from sciforge import sheetmetal_corner_ui

    return st.panel(sheetmetal_corner_ui.CornerPanel)


def inside(point):
    shape = s["body"].Shape
    return shape.isInside(point, 1e-6, True)


def setup():
    st.new_design("SmCorner")
    s["body"], _p = st.plate(0, 0, 100, 40, outline=OUTLINE)
    st.edge_flange(s["body"], V(100, 20, 1), 20)
    st.edge_flange(s["body"], V(50, 0, 1), 20)
    s["open"] = st.volume(s["body"])
    h.fit()


def open_corner():
    Gui.Selection.clearSelection()
    h.check("two flanges made", s["open"] > 4000, s["open"])
    h.check("the corner is open", not inside(V(99.5, 2.5, 12)))
    st.tab()
    st.menu("MODIFY", "Corner Closure")


def waiting():
    p = panel()
    h.check("Corner Closure dialog open", p is not None)
    h.check(
        "Symmetric Gap, rule gap",
        p is not None and p.value("alignment") == "symmetric" and p.value("use_rule_gap"),
    )
    box = p.fields["relief"] if p else None
    item = box.model().item(1) if box else None
    h.check(
        "Round relief offered", item is not None and item.isEnabled() and item.text() == "Round"
    )


def click_dominant():
    h.fit()
    h.click_edge(DOMINANT)


def click_submissive():
    p = panel()
    h.check("dominant edge picked", p is not None and len(p.picks["dominant"]) == 1, p and p.picks)
    h.click_edge(SUBMISSIVE)


def closed():
    p = panel()
    st.settle(p)
    h.check(
        "submissive edge picked", p is not None and len(p.picks["submissive"]) == 1, p and p.picks
    )
    h.check(
        "the corner is closed: the flanges reach the bisector",
        inside(V(99.5, 2.5, 12)) and inside(V(97.5, 0.5, 12)),
    )
    h.check("a gap is left at the corner", not inside(V(99.5, 0.5, 12)))
    h.check("more material", st.volume(s["body"]) > s["open"] + 5)
    h.check("no message", st.message(p) == "", st.message(p))
    h.shot("smmore-corner-1-symmetric")
    s["sym"] = st.volume(s["body"])


def choose_round():
    st.choose(panel(), "relief", "Round")


def round_cut():
    p = panel()
    st.settle(p, 15000)
    v = st.volume(s["body"])
    h.check(
        "Round relief cut where the bends meet", s["sym"] - 40 < v < s["sym"] - 0.5, (v, s["sym"])
    )
    h.check(
        "relief size rows shown (rule size)",
        p.rows["use_rule_relief"][0].isVisible() and not p.rows["relief_value"][0].isVisible(),
    )
    h.check("no message", st.message(p) == "", st.message(p))
    h.shot("smmore-corner-1b-round")
    s["round"] = v


def choose_square():
    st.choose(panel(), "relief", "Square")


def square_cut():
    p = panel()
    st.settle(p, 15000)
    v = st.volume(s["body"])
    h.check(
        "Square relief cut (more than the round of the same size)",
        v < s["round"] - 0.1,
        (v, s["round"]),
    )


def overlap():
    p = panel()
    st.choose(p, "alignment", "Overlap")


def overlap_refused():
    p = panel()
    st.settle(p)
    h.check(
        "a relief with Overlap is explained", "lies over itself" in st.message(p), st.message(p)
    )
    st.choose(p, "relief", "Trim To Bend")


def zero_gap():
    p = panel()
    st.toggle(p, "use_rule_gap")


def type_zero():
    st.type_into(panel(), "gap_value", "0")


def overlapped():
    p = panel()
    st.settle(p)
    h.check("Overlap: the dominant runs over the other's end", inside(V(99.5, 0.5, 12)))
    h.check("no message", st.message(p) == "", st.message(p))
    h.shot("smmore-corner-2-overlap")


def ok():
    st.ok()


def after_ok():
    steps = st.steps("SheetMetalCornerClosure")
    h.check("one Corner Closure step", len(steps) == 1, steps)
    h.check(
        "timeline shows Corner Closure 1",
        "Corner Closure 1" in st.timeline_titles(),
        st.timeline_titles(),
    )
    s["over"] = st.volume(s["body"])


def undo():
    st.undo()


def after_undo():
    h.check("Ctrl+Z: the corner is open again", st.close(st.volume(s["body"]), s["open"]))


def redo():
    st.redo()


def after_redo():
    h.check("Ctrl+Y: closed again", st.close(st.volume(s["body"]), s["over"]))


def edit():
    st.double_click_timeline("Corner Closure 1")


def edit_symmetric():
    p = panel()
    h.check(
        "edit opens with both edges",
        p is not None
        and p.editing
        and len(p.picks["dominant"]) == 1
        and len(p.picks["submissive"]) == 1,
    )
    h.check(
        "Overlap and the 0 gap are back",
        p is not None and p.value("alignment") == "overlap" and not p.value("use_rule_gap"),
    )
    if p:
        st.choose(p, "alignment", "Symmetric Gap")
        st.toggle(p, "use_rule_gap")


def edit_ok():
    st.settle(panel())
    st.ok()


def after_edit():
    h.check("back to the symmetric closure", st.close(st.volume(s["body"]), s["sym"]))


def edit_cancel():
    st.double_click_timeline("Corner Closure 1")


def change_cancel():
    p = panel()
    if p:
        st.choose(p, "alignment", "Overlap")
        st.settle(p)
    st.cancel()


def after_cancel():
    h.check(
        "Cancel keeps the symmetric closure",
        panel() is None and st.close(st.volume(s["body"]), s["sym"]),
    )


h.run(
    "smmore_corner",
    [
        setup,
        open_corner,
        waiting,
        click_dominant,
        click_submissive,
        closed,
        choose_round,
        round_cut,
        choose_square,
        square_cut,
        overlap,
        overlap_refused,
        zero_gap,
        type_zero,
        overlapped,
        ok,
        after_ok,
        undo,
        after_undo,
        redo,
        after_redo,
        edit,
        edit_symmetric,
        edit_ok,
        after_edit,
        edit_cancel,
        change_cancel,
        after_cancel,
    ],
)
