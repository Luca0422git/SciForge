# SPDX-License-Identifier: LGPL-2.1-or-later
"""SHEET METAL > CREATE > Lofted Flange the way a Fusion user does it, only real input: a 40 mm
square and a 30 mm circle 30 mm above it; the CREATE menu's Lofted Flange; click a side of the
square (the whole square is taken), then the circle: a Brake Form transition in a new sheet
metal body; Chord Tolerance 0.5; Die Form; Face Number 4; OK; Lofted Flange 1 in the timeline;
Ctrl+Z / Ctrl+Y; a square with an open line (refused in the dialog), Esc."""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import smmore_steps as st

V = App.Vector
s = {}


def panel():
    from sciforge import sheetmetal_lofted_ui

    return st.panel(sheetmetal_lofted_ui.LoftedPanel)


def flange_body():
    from sciforge import bodies

    steps = st.steps("SheetMetalLoftedFlange")
    return bodies.body_of(steps[0]) if steps else None


def vol():
    return st.volume(flange_body())


def setup():
    from sciforge import commands

    st.new_design("SmLofted")
    host = commands.ensure_body()
    s["square"] = st.profile_sketch(
        host, [(-20, -20, 20, -20), (20, -20, 20, 20), (20, 20, -20, 20), (-20, 20, -20, -20)]
    )
    s["circle"] = st.profile_sketch(host, [("c", 0, 0, 15)], z=30)
    s["line"] = st.profile_sketch(host, [(-20, 0, 20, 0)], z=60)
    h.fit()


def open_lofted():
    Gui.Selection.clearSelection()
    st.tab()
    st.menu("CREATE", "Lofted Flange")


def waiting():
    p = panel()
    h.check("Lofted Flange dialog open", p is not None)
    h.check(
        "Brake Form, Chord Tolerance",
        p is not None and p.value("forming") == "brake" and p.value("control") == "chord_tolerance",
    )


def click_square():
    h.fit()
    h.click_edge(V(0, -20, 0))


def click_circle():
    p = panel()
    h.check(
        "the square is profile 1", p is not None and len(p.picks["profile1"]) == 1, p and p.picks
    )
    h.click_edge(V(15, 0, 30))


def brake():
    p = panel()
    st.settle(p, 15000)
    h.check(
        "the circle is profile 2", p is not None and len(p.picks["profile2"]) == 1, p and p.picks
    )
    body = flange_body()
    from sciforge import sheetmetal

    h.check(
        "a new sheet metal body holds the flange",
        body is not None and sheetmetal.is_sheet_metal_body(body),
    )
    h.check("Brake Form previewed", vol() > 3500, vol())
    h.check("no message", st.message(p) == "", st.message(p))
    st.type_into(p, "value", "0.5")


def chord_05():
    p = panel()
    st.settle(p, 15000)
    h.check(
        "chord tolerance 0.5: about the golden model (corner fans, 2 %)",
        st.close(vol(), 3867.852, 0.02),
        vol(),
    )
    h.shot("smmore-lofted-1-brake")
    st.choose(p, "forming", "Die Form")


def die():
    p = panel()
    st.settle(p, 15000)
    h.check("Die Form: smooth", st.close(vol(), 3856.8239, 0.02), vol())
    h.check(
        "Die Form is marked as not developable",
        not st.steps("SheetMetalLoftedFlange")[0].Developable,
    )
    h.check("Facet Control hidden for Die Form", not p.rows["control"][0].isVisible())
    h.shot("smmore-lofted-2-die")
    st.choose(p, "forming", "Brake Form")


def face_number():
    p = panel()
    st.choose(p, "control", "Face Number")


def type_4():
    st.type_into(panel(), "value", "4")


def faceted():
    p = panel()
    st.settle(p, 15000)
    h.check("Face Number 4: as the golden model", st.close(vol(), 3961.631044, 0.02), vol())


def ok():
    st.ok()


def after_ok():
    steps = st.steps("SheetMetalLoftedFlange")
    h.check("one Lofted Flange step", len(steps) == 1, steps)
    h.check(
        "timeline shows Lofted Flange 1",
        "Lofted Flange 1" in st.timeline_titles(),
        st.timeline_titles(),
    )
    s["done"] = vol()


def undo():
    st.undo()


def after_undo():
    h.check("Ctrl+Z: no flange", not st.steps("SheetMetalLoftedFlange"))


def redo():
    st.redo()


def after_redo():
    h.check("Ctrl+Y: back", st.close(vol(), s["done"]))


def open_again():
    s["square"].ViewObject.Visibility = True  # shown again from the browser's eye
    s["line"].ViewObject.Visibility = True
    flange_body().ViewObject.Visibility = False  # hidden with the browser's eye: it covers
    open_lofted()  # the square's edges


def square_again():
    h.fit()
    h.click_edge(V(0, -20, 0))


def click_line():
    h.click_edge(V(10, 0, 60))


def mixed_refused():
    p = panel()
    st.settle(p, 15000)
    h.check(
        "open and closed profiles are refused",
        "Both profiles must be open" in st.message(p),
        st.message(p),
    )
    h.shot("smmore-lofted-3-refused")


def escape():
    st.esc()


def after_esc():
    h.check(
        "Esc: still one flange", panel() is None and len(st.steps("SheetMetalLoftedFlange")) == 1
    )


h.run(
    "smmore_lofted",
    [
        setup,
        open_lofted,
        waiting,
        click_square,
        click_circle,
        brake,
        chord_05,
        die,
        face_number,
        type_4,
        faceted,
        ok,
        after_ok,
        undo,
        after_undo,
        redo,
        after_redo,
        open_again,
        square_again,
        click_line,
        mixed_refused,
        escape,
        after_esc,
    ],
)
