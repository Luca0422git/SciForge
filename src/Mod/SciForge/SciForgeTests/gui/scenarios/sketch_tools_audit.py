# SPDX-License-Identifier: LGPL-2.1-or-later
"""The audit of the SKETCH tab (docs/sciforge/parity/sketch.md, "the audit"): where a
tool did not behave like Fusion's, with real clicks and keys.

3-Point Rectangle (CREATE > Rectangle): two clicks give one side at an angle, the third
the width: a rectangle with right angles (FreeCAD's "3 corners" mode makes a
parallelogram through the third click, so SciForge draws it itself); a typed width is
exact and kept as a dimension.
Fit Point Spline: three clicks, Enter: the spline is made through the clicked points and
the tool ends (Fusion; before, Enter dropped the spline); one Ctrl+Z takes it all away,
Ctrl+Y brings it back. Esc halfway: the spline being drawn is cancelled, nothing of it
stays, and a later change and its Ctrl+Z do not bring it back (FreeCAD's spline tool
leaves its points outside any undo step).
Control Point Spline: four clicks, OK in the right-click menu: the spline is made.
P runs SciForge's Project; Trim in the right-click menu's list runs SciForge's Trim.
"""

import FreeCAD as App
from PySide import QtCore
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import sketch_tools_steps as st

V = App.Vector
s = st.s
CLICK = 0.6


def splines():
    sk = st.sketch()
    return [(i, g) for i, g in enumerate(sk.Geometry) if g.TypeId == "Part::GeomBSplineCurve"]


# == 3-Point Rectangle =========================================================================
def r3_open():
    s["count"] = len(st.sketch().Geometry)
    s["cons"] = len(st.sketch().Constraints)
    si.menu_item("CREATE", "3-Point Rectangle")


def r3_clicks():
    h.check("SciForge's 3-Point Rectangle runs", st.tool_title() == "3-Point Rectangle")
    st.click(V(-55, 25, 0))
    st.click(V(-25, 35, 0), towards=V(0, 0, 0))
    st.hover(V(-35, 55, 0))
    h.check(
        "the whole rectangle shows before the third click",
        len(st.preview().get("curves", [])) == 1 and len(st.preview()["curves"][0]) == 5,
        st.preview().get("curves"),
    )
    st.click(V(-35, 55, 0))


def rectangle_sides(new):
    lines = st.of_type(new, "Part::GeomLineSegment", construction=False)
    return [g.EndPoint - g.StartPoint for _, g in lines], lines


def r3_check():
    new = st.new_geometry(s["count"])
    dirs, lines = rectangle_sides(new)
    h.check("four sides", len(lines) == 4, [g.TypeId for _, g in new])
    if len(lines) == 4:
        right = all(
            abs(dirs[i].dot(dirs[(i + 1) % 4])) < 1e-6 * dirs[i].Length * dirs[(i + 1) % 4].Length
            for i in range(4)
        )
        h.check("right angles at every corner (not FreeCAD's parallelogram)", right, dirs)
        first = (V(-25, 35, 0) - V(-55, 25, 0)).Length
        h.check(
            "the first side is the clicked one (31.62 long)",
            st.near(dirs[0].Length, first, 2 * CLICK),
            (dirs[0].Length, first),
        )
        # the third click's distance from the first side: 22.14
        h.check(
            "the width is the third click's distance from that side",
            st.near(dirs[1].Length, 22.136, 2 * CLICK),
            dirs[1].Length,
        )
        kinds = [c.Type for c in st.sketch().Constraints[s["cons"] :]]
        h.check(
            "Fusion's constraints: perpendicular and parallel",
            "Perpendicular" in kinds and kinds.count("Parallel") == 2,
            kinds,
        )
    st.sketch_ok("3-point rectangle")
    h.check("the tool waits for the next rectangle", st.tool_title() == "3-Point Rectangle")
    h.shot("1-three-point-rectangle")


def r3_typed():
    s["count"] = len(st.sketch().Geometry)
    s["cons"] = len(st.sketch().Constraints)
    st.click(V(-85, -25, 0))
    st.click(V(-65, -15, 0), towards=V(0, 0, 0))
    st.hover(V(-75, -5, 0))
    st.keys("12\n")


def r3_typed_check():
    new = st.new_geometry(s["count"])
    dirs, lines = rectangle_sides(new)
    h.check("a second rectangle", len(lines) == 4, len(lines))
    if len(lines) == 4:
        h.check("the typed width: exactly 12", st.near(dirs[1].Length, 12.0, 1e-9), dirs[1].Length)
        h.check(
            "...kept as a dimension",
            any(
                c.Type == "Distance" and c.First == lines[1][0] and st.near(c.Value, 12.0, 1e-9)
                for c in st.sketch().Constraints
            ),
        )
    st.sketch_ok("3-point rectangle typed")
    st.esc()
    h.check("Esc ends it", st.tool() is None, st.tool_title())


# == splines ===============================================================================
def fit_open():
    s["count"] = len(st.sketch().Geometry)
    s["splines"] = len(splines())
    si.menu_item("CREATE", "Fit Point Spline")


def fit_clicks():
    for p in (V(5, 15, 0), V(25, 35, 0), V(45, 15, 0)):
        si.click(st.g(p))


def fit_enter():
    st.enter()


fit_enter.wait_ms = 1000


def fit_check():
    found = splines()
    h.check("Enter made the spline", len(found) == s["splines"] + 1, len(found))
    if len(found) > s["splines"]:
        g = found[-1][1]
        ends = [g.value(g.FirstParameter), g.value(g.LastParameter)]
        h.check(
            "through the clicked ends",
            any(st.vnear(e, V(5, 15, 0), CLICK) for e in ends)
            and any(st.vnear(e, V(45, 15, 0), CLICK) for e in ends),
            ends,
        )
        middle = g.toShape().distToShape(__import__("Part").Vertex(V(25, 35, 0)))[0]
        h.check("through the middle click", middle < CLICK, middle)
    h.check("Enter also ended the tool (Fusion)", not si.drawing())
    st.sketch_ok("fit point spline")


def fit_undo():
    s["with_spline"] = len(st.sketch().Geometry)
    st.undo()


def fit_undo_check():
    h.check(
        "one Ctrl+Z takes the whole spline away (points and all)",
        len(st.sketch().Geometry) == s["count"] and len(splines()) == s["splines"],
        (len(st.sketch().Geometry), s["count"]),
    )
    st.redo()


def fit_redo_check():
    h.check(
        "Ctrl+Y brings it back",
        len(st.sketch().Geometry) == s["with_spline"] and len(splines()) == s["splines"] + 1,
        (len(st.sketch().Geometry), s["with_spline"]),
    )


def fit_esc_open():
    s["count"] = len(st.sketch().Geometry)
    s["constraints"] = len(st.sketch().Constraints)
    si.menu_item("CREATE", "Fit Point Spline")


def fit_esc_clicks():
    for p in (V(5, -15, 0), V(25, -35, 0)):
        si.click(st.g(p))
    s["mid_count"] = len(st.sketch().Geometry)


def fit_esc():
    st.esc()


fit_esc.wait_ms = 1000


def fit_esc_check():
    h.check("the spline tool had placed its points", s["mid_count"] > s["count"], s["mid_count"])
    h.check(
        "Esc cancelled the spline being drawn: nothing of it stays",
        len(st.sketch().Geometry) == s["count"]
        and len(st.sketch().Constraints) == s["constraints"],
        (len(st.sketch().Geometry), s["count"]),
    )
    h.check("the tool ended", not si.drawing())


def fit_esc_later():
    """The next change must not bring the cancelled points back (FreeCAD kept them in an
    open undo step that the next change committed)."""
    import Part

    doc = App.ActiveDocument
    doc.openTransaction("Another change")
    st.sketch().addGeometry(Part.LineSegment(V(-85, -55, 0), V(-75, -55, 0)))
    doc.commitTransaction()
    doc.recompute()
    st.undo()


def fit_esc_later_check():
    h.check(
        "after another change and its Ctrl+Z, still nothing of the cancelled spline",
        len(st.sketch().Geometry) == s["count"],
        (len(st.sketch().Geometry), s["count"]),
    )


def cp_open():
    s["splines"] = len(splines())
    si.menu_item("CREATE", "Control Point Spline")


def cp_clicks():
    for p in (V(55, -35, 0), V(65, -15, 0), V(75, -35, 0), V(85, -15, 0)):
        si.click(st.g(p))


def cp_ok():
    h.click(st.g(V(65, -55, 0)), button=QtCore.Qt.RightButton)
    QtCore.QTimer.singleShot(250, lambda: si.marking_slot("OK"))


cp_ok.wait_ms = 1200


def cp_check():
    found = splines()
    h.check(
        "OK in the right-click menu made the spline", len(found) == s["splines"] + 1, len(found)
    )
    if len(found) > s["splines"]:
        poles = found[-1][1].getPoles()
        h.check("its four control points are the clicks", len(poles) == 4, len(poles))
    h.check("...and ended the tool", not si.drawing())
    st.sketch_ok("control point spline")


# == keys and menus ==========================================================================
def p_key():
    from sciforge import recent

    st.hover(V(-60, -45, 0))
    h.press("p")
    last = recent.last()
    h.check(
        "P runs SciForge's Project", last is not None and last[0] == "SciForge_SketchProject", last
    )
    st.esc()


def marking_trim():
    gl = h.gl_widget()
    pos = h.screen_point(st.g(V(-65, -25, 0)))
    QtTest.QTest.mouseClick(gl, QtCore.Qt.RightButton, QtCore.Qt.NoModifier, pos)
    QtCore.QTimer.singleShot(300, _click_trim_row)


def _click_trim_row():
    menu = si.marking_menu()
    if menu is None:
        h.check("the right-click menu opened", False)
        return
    for i in range(menu.list.count()):
        row = menu.list.item(i)
        if row.text().split("    ")[0] == "Trim":
            rect = menu.list.visualItemRect(row)
            QtTest.QTest.mouseClick(
                menu.list.viewport(), QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, rect.center()
            )
            return
    h.check("the menu lists Trim", False)
    menu.close()


marking_trim.wait_ms = 1200


def marking_trim_check():
    h.check(
        "Trim in the right-click menu runs SciForge's Trim",
        st.tool_title() == "Trim",
        st.tool_title(),
    )
    st.esc()


def finish():
    h.ribbon("Finish Sketch")


h.run(
    "sketch_tools_audit",
    si.watched(
        st.start_steps("SketchToolsAudit")
        + [
            r3_open,
            r3_clicks,
            r3_check,
            r3_typed,
            r3_typed_check,
            fit_open,
            fit_clicks,
            fit_enter,
            fit_check,
            fit_undo,
            fit_undo_check,
            fit_redo_check,
            fit_esc_open,
            fit_esc_clicks,
            fit_esc,
            fit_esc_check,
            fit_esc_later,
            fit_esc_later_check,
            cp_open,
            cp_clicks,
            cp_ok,
            cp_check,
            p_key,
            marking_trim,
            marking_trim_check,
            finish,
        ]
    ),
)
