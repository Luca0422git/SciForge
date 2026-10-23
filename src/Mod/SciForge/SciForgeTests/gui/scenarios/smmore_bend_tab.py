# SPDX-License-Identifier: LGPL-2.1-or-later
"""SHEET METAL > Bend on a tab, the way a Fusion user bends a tab up: a plate with a 20 mm
tab, a line drawn across the tab's root; the face, then the line: only the tab bends and the
rule's round bend reliefs are cut into the plate beside it (volume worked out by hand); Bend
Relief off is refused with the reason, back on; OK; the timeline's Bend 1; Ctrl+Z / Ctrl+Y;
the flat pattern lays it flat (the plate and tab less the two reliefs)."""

import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import smmore_steps as st

V = App.Vector
s = {}
OUTLINE = [(0, 0), (100, 0), (100, 40), (60, 40), (60, 60), (40, 60), (40, 40), (0, 40)]
# rule Steel (mm): T = R = 1, K 0.44, bend relief round, width T, depth T / 2
SLOT = 1.0 * (st.BA90 / 2 + 0.5 - 0.5) + math.pi / 8  # a 1 mm slot with a round end
TAB = 4400 - st.BA90 * 20 + st.BENT90 * 20 - 2 * SLOT  # 4398.8376


def panel():
    from sciforge import sheetmetal_bend_ui

    return st.panel(sheetmetal_bend_ui.BendPanel)


def setup():
    st.new_design("SmBendTab")
    s["body"], _p = st.plate(0, 0, 100, 40, outline=OUTLINE)
    st.bend_sketch(s["body"], [(-5, 40, 105, 40)])
    s["flat"] = st.volume(s["body"])
    h.fit()


def open_bend():
    Gui.Selection.clearSelection()
    st.tab()
    h.ribbon("Bend")


def click_face():
    p = panel()
    h.check("Bend dialog open", p is not None)
    h.check("a plate with a tab", st.close(s["flat"], 4400.0), s["flat"])
    h.click(V(10, 20, 1))


def click_line():
    h.click_edge(V(50, 40, 1))


def tab_bent():
    p = panel()
    st.settle(p)
    v = st.volume(s["body"])
    h.check(
        "only the tab bends, round reliefs beside it (4400 - 20 BA + 20 x 2.35619 - 2 slots)",
        st.close(v, TAB),
        (v, TAB),
    )
    box = s["body"].Shape.BoundBox
    h.check("the tab stands up, the plate stays flat", box.ZMax > 15 and box.XMax > 99.9, box)
    h.check(
        "the plate beside the tab is not bent",
        s["body"].Shape.isInside(V(20, 39.5, 0.5), 1e-6, True),
    )
    h.check(
        "a relief slot beside the tab", not s["body"].Shape.isInside(V(39.5, 39.8, 0.5), 1e-6, True)
    )
    h.check("no message", st.message(p) == "", st.message(p))
    h.shot("smmore-bend-tab")


def relief_off():
    st.toggle(panel(), "bend_relief")


def relief_off_refused():
    p = panel()
    st.settle(p)
    h.check(
        "Bend Relief off on a tab is explained",
        "turn on Bend" in st.message(p) and "Relief" in st.message(p),
        st.message(p),
    )


def relief_on():
    st.toggle(panel(), "bend_relief")


def relief_back():
    p = panel()
    st.settle(p)
    h.check(
        "back on: the tab bends again",
        st.close(st.volume(s["body"]), TAB) and st.message(p) == "",
        (st.volume(s["body"]), st.message(p)),
    )


def ok():
    st.ok()


def after_ok():
    bends = st.steps("SheetMetalBend")
    h.check("one Bend step", len(bends) == 1, bends)
    h.check("timeline shows Bend 1", "Bend 1" in st.timeline_titles(), st.timeline_titles())
    h.check("kept after OK", st.close(st.volume(s["body"]), TAB), st.volume(s["body"]))


def undo():
    st.undo()


def after_undo():
    h.check("Ctrl+Z: flat again", st.close(st.volume(s["body"]), s["flat"]))


def redo():
    st.redo()


def after_redo():
    h.check("Ctrl+Y: bent again", st.close(st.volume(s["body"]), TAB))


def lays_flat():
    from sciforge import sheetmetal_unfold as uf

    shape = s["body"].Shape.copy()
    shape.Placement = App.Placement()
    name = None
    for i, face in enumerate(shape.Faces, start=1):
        if face.Surface.TypeId == "Part::GeomPlane" and face.isInside(V(10, 20, 1), 1e-6, True):
            name = "Face%d" % i
    flat = None
    try:
        flat = uf.unfold(shape, name, 0.44).shape.Volume if name else None
    except Exception as exc:
        flat = str(exc)
    h.check(
        "the flat pattern is the plate and tab less the two reliefs",
        isinstance(flat, float) and st.close(flat, 4400 - 2 * SLOT),
        (flat, 4400 - 2 * SLOT),
    )


h.run(
    "smmore_bend_tab",
    [
        setup,
        open_bend,
        click_face,
        click_line,
        tab_bent,
        relief_off,
        relief_off_refused,
        relief_on,
        relief_back,
        ok,
        after_ok,
        undo,
        after_undo,
        redo,
        after_redo,
        lays_flat,
    ],
)
