# SPDX-License-Identifier: LGPL-2.1-or-later
"""SHEET METAL > Hem the way a Fusion user does it, only real input: Hem with nothing picked
(waits), click the plate's end edge: an Open hem previews (volume worked out from the hem's
cross-section, sheetmetal_bend_core); every type in turn (Flat, Rolled, Teardrop, Rope, Double)
from the Type list; drag the Length arrow (its value box follows); a Length too short (refused
in the dialog, OK waits) then fixed; a second edge meeting at the corner (mitred); OK; the
timeline's Hem 1; Ctrl+Z / Ctrl+Y; edit from the timeline (Flip); Cancel keeps the part."""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import arrow_input as ai
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import smmore_steps as st

V = App.Vector
s = {}
FLAT = 100.0 * 40.0
EDGE = V(100, 20, 1)
EDGE2 = V(50, 40, 1)


def panel():
    from sciforge import sheetmetal_hem_ui

    return st.panel(sheetmetal_hem_ui.HemPanel)


def vol():
    return st.volume(s["body"])


def expected(kind, **extra):
    from sciforge import sheetmetal_bend_core as core

    opts = core.hem_defaults(st.T)
    opts["type"] = kind
    opts.update(extra)
    pieces, x0, _inner = core.hem_profile(opts, st.T, st.R)
    return FLAT + x0 * 40 + core.strip_area(pieces, st.T) * 40


def setup():
    st.new_design("SmHem")
    s["body"], s["plate"] = st.plate(0, 0, 100, 40)
    h.fit()


def open_hem():
    Gui.Selection.clearSelection()
    st.tab()
    h.ribbon("Hem")


def waiting():
    p = panel()
    h.check("Hem dialog open", p is not None and Gui.Control.activeDialog())
    if p is None:
        return
    h.check("nothing picked, no error", p.picks["edges"] == [] and st.message(p) == "")
    h.check("type Open by default", p.value("type") == "open")
    h.check(
        "Open shows Length and Gap only",
        p.rows["length"][0].isVisible()
        and p.rows["gap"][0].isVisible()
        and not p.rows["radius"][0].isVisible()
        and not p.rows["angle"][0].isVisible(),
    )


def click_edge():
    h.fit()
    h.click_edge(EDGE)


def open_preview():
    p = panel()
    st.settle(p)
    h.check("the edge is picked", p is not None and len(p.picks["edges"]) == 1, p and p.picks)
    h.check("Open hem previewed", st.close(vol(), expected("open")), (vol(), expected("open")))
    h.check("the Length arrow is shown", p is not None and "length" in p.handles)
    h.shot("smmore-hem-1-open")


def make_type(kind, label):
    def choose():
        st.choose(panel(), "type", label)

    def check():
        p = panel()
        st.settle(p)
        want = expected(kind)
        h.check("%s hem previewed" % label, st.close(vol(), want), (vol(), want))
        h.check("%s: no message" % label, st.message(p) == "", st.message(p))

    choose.__name__ = "choose_" + kind
    check.__name__ = "check_" + kind
    return [choose, check]


def rows_rolled():
    p = panel()
    h.check(
        "Rolled shows Radius and Angle",
        p.rows["radius"][0].isVisible()
        and p.rows["angle"][0].isVisible()
        and not p.rows["length"][0].isVisible(),
    )


def back_to_open():
    st.choose(panel(), "type", "Open")


def drag_length():
    p = panel()
    st.settle(p)
    handle = p.handles.get("length") if p else None
    if handle is None:
        h.check("Length arrow to drag", False)
        return
    s["before"] = p.value("length")
    start = h.screen_point(ai.head_point(handle))
    end = h.screen_point(handle.origin + handle.direction * (s["before"] + 6.0 + 0.9 * handle.size))
    s["drag"] = ai.HeldDrag(start, end, moves=30, every_ms=25, hold_ms=300)
    s["drag"].run()


def dragged():
    p = panel()
    st.settle(p)
    length = p.value("length") if p else 0
    h.check(
        "dragging the arrow makes the hem longer", length > s["before"] + 1.0, (s["before"], length)
    )
    h.check(
        "the preview follows",
        st.close(vol(), expected("open", length=length), 1e-3),
        (vol(), expected("open", length=length)),
    )
    box = p.value_boxes.boxes.get("length") if p else None
    h.check("a value box shows the Length", box is not None, p and p.value_boxes.boxes)


def too_short():
    st.type_into(panel(), "length", "0.5")


def refused():
    p = panel()
    st.settle(p)
    h.check(
        "too short a Length is explained",
        "Length must be more than" in st.message(p),
        st.message(p),
    )


def ok_refused():
    st.ok()


def still_open():
    h.check("OK waits while the hem cannot be made", panel() is not None)
    st.type_into(panel(), "length", "4")


def second_edge():
    h.click_edge(EDGE2)


def mitred():
    p = panel()
    st.settle(p)
    h.check("two edges picked", p is not None and len(p.picks["edges"]) == 2, p and p.picks)
    h.check("two mitred Open hems (4516.4638)", st.close(vol(), 4516.463826, 1e-6), vol())
    h.check("no message", st.message(p) == "", st.message(p))
    h.shot("smmore-hem-2-mitred")


def ok():
    st.ok()


def after_ok():
    hems = st.steps("SheetMetalHem")
    h.check("dialog closed", panel() is None)
    h.check("one Hem step at the end", len(hems) == 1 and s["body"].Tip is hems[0], hems)
    h.check("timeline shows Hem 1", "Hem 1" in st.timeline_titles(), st.timeline_titles())
    s["hemmed"] = vol()


def undo():
    st.undo()


def after_undo():
    h.check("Ctrl+Z: no hem", st.close(vol(), FLAT) and not st.steps("SheetMetalHem"), vol())


def redo():
    st.redo()


def after_redo():
    h.check("Ctrl+Y: the hems are back", st.close(vol(), s["hemmed"]), vol())


def edit():
    st.double_click_timeline("Hem 1")


def edit_open():
    p = panel()
    h.check(
        "edit opens the Hem dialog with both edges",
        p is not None and p.editing and len(p.picks["edges"]) == 2,
    )
    if p:
        st.toggle(p, "flip")


def flipped():
    p = panel()
    st.settle(p)
    box = s["body"].Shape.BoundBox
    h.check("Flip hems under the sheet", box.ZMin < -1.0, box)
    h.check("same volume flipped", st.close(vol(), s["hemmed"], 1e-6), vol())


def edit_ok():
    st.ok()


def after_edit():
    h.check(
        "still one Hem, flipped",
        len(st.steps("SheetMetalHem")) == 1 and s["body"].Shape.BoundBox.ZMin < -1.0,
    )
    s["edited"] = vol()


def edit_again():
    st.double_click_timeline("Hem 1")


def change_and_cancel():
    p = panel()
    h.check("dialog open again", p is not None)
    if p:
        st.choose(p, "type", "Rolled")


def cancel():
    st.settle(panel())
    st.cancel()


def after_cancel():
    h.check("Cancel keeps the hem as it was", st.close(vol(), s["edited"], 1e-6), vol())
    h.check("still Open", st.steps("SheetMetalHem")[0].HemType == "Open")


h.run(
    "smmore_hem",
    [setup, open_hem, waiting, click_edge, open_preview]
    + make_type("flat", "Flat")
    + make_type("rolled", "Rolled")
    + [rows_rolled]
    + make_type("teardrop", "Teardrop")
    + make_type("rope", "Rope")
    + make_type("double", "Double")
    + [
        back_to_open,
        drag_length,
        dragged,
        too_short,
        refused,
        ok_refused,
        still_open,
        second_edge,
        mitred,
        ok,
        after_ok,
        undo,
        after_undo,
        redo,
        after_redo,
        edit,
        edit_open,
        flipped,
        edit_ok,
        after_edit,
        edit_again,
        change_and_cancel,
        cancel,
        after_cancel,
    ],
)
