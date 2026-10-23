# SPDX-License-Identifier: LGPL-2.1-or-later
"""SHEET METAL > Bend in an empty design (says why it cannot start, no dialog, no error), then
a plate inside a moved component bent along two lines at once (a U, bent farthest first; the
volume worked out by hand), with the Bend Radius override; OK."""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import smmore_steps as st

V = App.Vector
s = {}
SHIFT = V(10, 20, 5)
U = 4000 - 2 * st.BA90 * 40 + 2 * st.BENT90 * 40  # 4007.5398


def panel():
    from sciforge import sheetmetal_bend_ui

    return st.panel(sheetmetal_bend_ui.BendPanel)


def empty():
    st.new_design("SmEmpty")
    h.fit()


def bend_in_empty():
    Gui.Selection.clearSelection()
    st.tab()
    h.ribbon("Bend")


def refused_start():
    h.check(
        "no Bend dialog without a sheet metal body",
        panel() is None and not Gui.Control.activeDialog(),
    )
    h.check("no pop-up", not h.popups(), h.popups())
    App.closeDocument(App.ActiveDocument.Name)


def setup():
    from sciforge import components

    st.new_design("SmBendTwo")
    doc = App.ActiveDocument
    part = components.new_component(doc, "Bracket")
    part.Placement = App.Placement(SHIFT, App.Rotation())
    body = components.new_body_in(doc, part)
    s["body"], _p = st.plate(0, 0, 100, 40, body=body)
    st.bend_sketch(s["body"], [(30, -5, 30, 45), (70, -5, 70, 45)])
    from sciforge import pickpanel

    pickpanel.activate(s["body"])
    h.fit()


def open_bend():
    Gui.Selection.clearSelection()
    st.tab()
    h.ribbon("Bend")


def click_second():
    h.click_edge(V(70, 30, 1) + SHIFT)


def click_face():
    h.click(V(10, 20, 1) + SHIFT)


def face_first():
    p = panel()
    h.check("Bend dialog open on the plate in the component", p is not None and p.body is s["body"])
    h.fit()


def line_one():
    p = panel()
    h.check(
        "the Bend Lines box takes the clicks after the face", p is not None and p.active == "lines"
    )
    h.click_edge(V(30, 30, 1) + SHIFT)


def u_shape():
    p = panel()
    st.settle(p)
    h.check(
        "the face in the moved component is picked",
        p is not None and len(p.picks["stationary"]) == 1,
        p and p.picks,
    )
    h.check(
        "a U: two 90 degree bends (4000 - 2 x 2.26195 x 40 + 2 x 94.2478)",
        st.close(st.volume(s["body"]), U),
        st.volume(s["body"]),
    )
    box = s["body"].Shape.BoundBox
    h.check("both sides stand up", box.ZMax > 25 and box.XMax < 72, box)
    h.shot("smmore-bend-two-u")


def line_two_own_angle():
    p = panel()
    box = p.fields["line"] if p else None
    h.check(
        "Values For lists All lines, Line 1, Line 2",
        box is not None
        and [box.itemText(i) for i in range(box.count())] == ["All lines", "Line 1", "Line 2"],
        box and [box.itemText(i) for i in range(box.count())],
    )
    st.choose(p, "line", "Line 2")


def type_45():
    st.type_into(panel(), "angle", "45")


def line_two_at_45():
    import math

    p = panel()
    st.settle(p)
    a45 = math.radians(45)
    want = (
        4000
        - st.BA90 * 40
        - a45 * (st.R + st.K * st.T) * 40
        + st.BENT90 * 40
        + a45 * ((st.R + st.T) ** 2 - st.R**2) / 2 * 40
    )
    h.check(
        "Line 2 bent 45, Line 1 still 90",
        st.close(st.volume(s["body"]), want),
        (st.volume(s["body"]), want),
    )
    st.choose(p, "line", "All lines")


def all_lines_back():
    p = panel()
    h.check("All lines shows the common 90", p is not None and abs(p.value("angle") - 90) < 1e-9)
    st.choose(p, "line", "Line 2")


def line_two_kept():
    p = panel()
    h.check("Line 2 keeps its own 45", p is not None and abs(p.value("angle") - 45) < 1e-9)
    st.type_into(p, "angle", "90")


def override_radius():
    p = panel()
    st.toggle(p, "override_radius")
    st.type_into(p, "radius", "2")


def radius_2():
    p = panel()
    st.settle(p)
    # R 2: BA = pi/2 (2 + 0.44) per bend, bent ring pi/2 x ((3^2 - 2^2) / 2)
    import math

    ba = math.pi / 2 * (2 + 0.44)
    want = 4000 - 2 * ba * 40 + 2 * math.pi / 2 * (9 - 4) / 2 * 40
    h.check(
        "Bend Radius 2 for both bends",
        st.close(st.volume(s["body"]), want),
        (st.volume(s["body"]), want),
    )


def ok():
    st.ok()


def after_ok():
    bends = st.steps("SheetMetalBend")
    h.check(
        "one Bend step holds both lines",
        len(bends) == 1 and len(bends[0].BendLines[0][1]) == 2,
        bends and bends[0].BendLines,
    )
    h.check("state fine", bends and "Invalid" not in list(bends[0].State))


h.run(
    "smmore_bend_two",
    [
        empty,
        bend_in_empty,
        refused_start,
        setup,
        open_bend,
        face_first,
        click_face,
        line_one,
        click_second,
        u_shape,
        line_two_own_angle,
        type_45,
        line_two_at_45,
        all_lines_back,
        line_two_kept,
        override_radius,
        radius_2,
        ok,
        after_ok,
    ],
)
