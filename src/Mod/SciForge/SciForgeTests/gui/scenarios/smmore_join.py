# SPDX-License-Identifier: LGPL-2.1-or-later
"""SHEET METAL > Join by Bend the way a Fusion user does it, only real input: the CREATE menu's
Join by Bend, the First Edge on the upright plate's bottom, a Second Edge on a parallel plate
(refused in the dialog: no bend joins parallel sheets; OK waits), Esc; again with the flat plate's
end edge as the Second Edge: both are extended and joined by one bend of the rule's radius
(volume worked out by hand), OK; the flat plate's body is used up (hidden); Ctrl+Z / Ctrl+Y;
edit from the timeline with a 3 mm Bend Radius."""

import math

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
    st.new_design("SmJoin")
    s["flat"], _f = st.plate(0, 0, 50, 40, label="Flat")
    s["upright"], _u = st.plate(
        0, 5, 40, 45, z=60, body=st.new_body(), plane="YZ_Plane", label="Upright"
    )
    s["other"], _o = st.plate(
        0, 5, 40, 45, z=90, body=st.new_body(), plane="YZ_Plane", label="Parallel"
    )
    from sciforge import pickpanel

    pickpanel.activate(s["upright"])
    h.fit()


def open_join():
    Gui.Selection.clearSelection()
    st.tab()
    st.menu("CREATE", "Join by Bend")


def waiting():
    p = panel()
    h.check("Join by Bend dialog open", p is not None)
    h.check(
        "it works on the upright plate",
        p is not None and p.body is s["upright"],
        p and p.body.Label,
    )
    h.check("First Edge box takes the clicks", p is not None and p.active == "first")


def click_first():
    h.fit()
    h.click_edge(V(60, 20, 5))


def click_parallel():
    p = panel()
    h.check("first edge picked", p is not None and len(p.picks["first"]) == 1, p and p.picks)
    h.click_edge(V(90, 20, 5))


def parallel_refused():
    p = panel()
    st.settle(p)
    h.check("second edge picked", p is not None and len(p.picks["second"]) == 1, p and p.picks)
    h.check("parallel sheets explained", "parallel" in st.message(p), st.message(p))


def ok_refused():
    st.ok()


def still_open():
    h.check("OK waits", panel() is not None)
    h.shot("smmore-join-1-refused")


def escape():
    st.esc()


def after_esc():
    h.check("Esc: nothing joined", panel() is None and not st.steps("SheetMetalJoinBend"))
    h.check("the upright plate is as it was", st.close(st.volume(s["upright"]), 1600.0))


def open_again():
    open_join()


def first_again():
    h.fit()
    h.click_edge(V(60, 20, 5))


def view_top():
    p = panel()
    h.check("first edge picked again", p is not None and len(p.picks["first"]) == 1)
    Gui.ActiveDocument.ActiveView.viewTop()  # the upright plate hid the flat one's end
    h.fit(iso=False)


def second_flat():
    h.click_edge(V(50, 20, 1))


def joined():
    p = panel()
    st.settle(p)
    v = st.volume(s["upright"])
    h.check(
        "joined by one bend (50x40 + 9x40 + 40x40 + 3x40 + pi/2 x 40 x 1.5)",
        st.close(v, JOINED),
        (v, JOINED),
    )
    h.check("no message", st.message(p) == "", st.message(p))
    h.shot("smmore-join-2-joined")


def ok():
    st.ok()


def after_ok():
    steps = st.steps("SheetMetalJoinBend")
    h.check("one Join by Bend step", len(steps) == 1, steps)
    h.check(
        "timeline shows Join by Bend 1",
        "Join by Bend 1" in st.timeline_titles(),
        st.timeline_titles(),
    )
    from sciforge import bodies

    h.check("the flat plate's body is used up (hidden)", not bodies.is_shown(s["flat"]))


def undo():
    st.undo()


def after_undo():
    h.check(
        "Ctrl+Z: not joined",
        st.close(st.volume(s["upright"]), 1600.0) and not st.steps("SheetMetalJoinBend"),
    )


def redo():
    st.redo()


def after_redo():
    h.check("Ctrl+Y: joined again", st.close(st.volume(s["upright"]), JOINED))


def edit():
    st.double_click_timeline("Join by Bend 1")


def edit_radius():
    p = panel()
    h.check(
        "edit opens with both edges",
        p is not None and p.editing and len(p.picks["first"]) == 1 and len(p.picks["second"]) == 1,
    )
    if p:
        st.toggle(p, "use_rule_radius")
        st.type_into(p, "radius", "3")


def radius_previewed():
    p = panel()
    st.settle(p)
    # mid radius 3.5: the plates reach to 3.5 from where their middles meet
    want = (
        50 * 40
        + (60.5 - 3.5 - 50) * 40
        + 40 * 40
        + (5 - 0.5 - 3.5) * 40
        + (math.pi / 2 * (4**2 - 3**2) / 2 * 40)
    )
    h.check(
        "Bend Radius 3 previewed",
        st.close(st.volume(s["upright"]), want),
        (st.volume(s["upright"]), want),
    )


def edit_ok():
    st.ok()


def after_edit():
    h.check(
        "dialog closed, still one step",
        panel() is None and len(st.steps("SheetMetalJoinBend")) == 1,
    )


h.run(
    "smmore_join",
    [
        setup,
        open_join,
        waiting,
        click_first,
        click_parallel,
        parallel_refused,
        ok_refused,
        still_open,
        escape,
        after_esc,
        open_again,
        first_again,
        view_top,
        second_flat,
        joined,
        ok,
        after_ok,
        undo,
        after_undo,
        redo,
        after_redo,
        edit,
        edit_radius,
        radius_previewed,
        edit_ok,
        after_edit,
    ],
)
