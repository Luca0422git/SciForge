# SPDX-License-Identifier: LGPL-2.1-or-later
"""QA of Join by Bend's First Edge, only real input: with the FLAT plate active, the CREATE
menu's Join by Bend opens on it, but the First Edge is clicked on the upright plate (Fusion
takes a First Edge on any sheet metal body): the dialog moves to the upright plate, then the
flat plate's end edge as the Second Edge joins them (volume worked out by hand); OK puts the
step in the upright plate's body and uses the flat one up; Ctrl+Z undoes it."""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import smmore_steps as st

V = App.Vector
s = {}
JOINED = 50 * 40 + 9 * 40 + 40 * 40 + 3 * 40 + st.BENT90 * 40  # 4174.2478


def panel():
    from sciforge import sheetmetal_bend_join_ui

    return st.panel(sheetmetal_bend_join_ui.JoinBendPanel)


def setup():
    from sciforge import pickpanel

    st.new_design("SmQaJoinOrder")
    s["flat"], _f = st.plate(0, 0, 50, 40, label="Flat")
    s["upright"], _u = st.plate(
        0, 5, 40, 45, z=60, body=st.new_body(), plane="YZ_Plane", label="Upright"
    )
    pickpanel.activate(s["flat"])
    h.fit()


def open_join():
    Gui.Selection.clearSelection()
    st.tab()
    st.menu("CREATE", "Join by Bend")


def opened_on_flat():
    p = panel()
    h.check("Join by Bend open", p is not None)
    h.check("it opened on the active (flat) plate", p is not None and p.body is s["flat"])


def click_upright_first():
    h.fit()
    h.click_edge(V(60, 20, 5))


def moved_to_upright():
    p = panel()
    st.settle(p)
    h.check(
        "the First Edge on the upright plate is taken",
        p is not None and len(p.picks["first"]) == 1,
        p and p.picks,
    )
    h.check(
        "the dialog moved to the upright plate",
        p is not None and p.body is s["upright"],
        p and p.body.Label,
    )
    h.check("the Second Edge box takes the next click", p is not None and p.active == "second")
    Gui.ActiveDocument.ActiveView.viewTop()
    h.fit(iso=False)


def click_flat_second():
    h.click_edge(V(50, 20, 1))


def joined():
    p = panel()
    st.settle(p)
    v = st.volume(s["upright"])
    h.check("joined by one bend into the upright plate", st.close(v, JOINED), (v, JOINED))
    h.check("no message", st.message(p) == "", st.message(p))


def ok():
    st.ok()


def after_ok():
    from sciforge import bodies

    steps = st.steps("SheetMetalJoinBend")
    h.check(
        "one Join by Bend step, in the upright plate's body",
        len(steps) == 1 and bodies.body_of(steps[0]) is s["upright"],
        steps,
    )
    h.check("the flat plate is used up (hidden)", not bodies.is_shown(s["flat"]))
    h.check("the flat plate is as it was", st.close(st.volume(s["flat"]), 2000.0))


def undo():
    st.undo()


def undone():
    from sciforge import bodies

    st.settle()
    h.check("Ctrl+Z: not joined", not st.steps("SheetMetalJoinBend"))
    h.check("the upright plate is as it was", st.close(st.volume(s["upright"]), 1600.0))
    h.check("the flat plate is shown again", bodies.is_shown(s["flat"]))


h.run(
    "smmore_qa_join_order",
    [
        setup,
        open_join,
        opened_on_flat,
        click_upright_first,
        moved_to_upright,
        click_flat_second,
        joined,
        ok,
        after_ok,
        undo,
        undone,
    ],
)
