# SPDX-License-Identifier: LGPL-2.1-or-later
"""Selection inside an open sketch (parity/selection.md, parity/sketch.md "Sketch, part
2"): Fusion's double-click chain selection and its box modifiers, with real input.

A sketch on the XY plane: a 40 x 30 rectangle drawn with R (two clicks), an open chain of
two lines, a circle, a construction line touching the rectangle's corner.

  A  a double-click on the rectangle's bottom edge selects its four edges, nothing else
     (not the construction line that touches it, not the other chain)
  B  a double-click on the open chain selects its two lines; on the circle: the circle
  C  a plain window around the circle replaces the selection (only the circle and its
     centre); Shift + window around the open chain adds its lines
  D  a crossing box (right to left) touching the rectangle's top edge selects it alone
  E  Ctrl + crossing box over that edge again takes it out, the others stay
  F  Esc clears the selection; a double-click on empty space selects nothing; the Line
     tool's double-click still ends a chain (it is not a chain selection)
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import selection_input as sel
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import sketch_tools_steps as st

V = App.Vector
s = st.s


def names():
    """The selected element names of the open sketch, as a set."""
    found = set()
    for x in Gui.Selection.getSelectionEx():
        if x.Object is s.get("sk"):
            for n in x.SubElementNames:
                found.add(n.rsplit(".", 1)[-1])
    return found


def edges(indices):
    return {"Edge%d" % (i + 1) for i in indices}


def dclick_at(pos):
    """A real mouse's double-click: press, release, double-click, release (Qt's test
    double-click sends no release after the double-click event)."""
    widget = h.gl_widget()
    QtTest.QTest.mouseDClick(widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, pos)
    QtTest.QTest.mouseRelease(widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, pos)
    QtWidgets.QApplication.processEvents()


def double_click(point):
    st.hover(point)
    dclick_at(h.screen_point(st.g(point)))


# -- drawing ---------------------------------------------------------------------------------
def grid_fine():
    from sciforge import grid_ui

    grid_ui.put("Subdivisions", 10)
    grid_ui.apply_subdivisions()
    h.fit(iso=False)


def rect_key():
    s["before"] = s["sk"].GeometryCount
    h.press("r")


def rect_a():
    si.click(st.g(V(0, 0, 0)))


def rect_b():
    si.click(st.g(V(40, 30, 0)))


def rect_done():
    st.esc()
    sk = s["sk"]
    s["rect"] = list(range(s["before"], sk.GeometryCount))
    h.check("R drew four lines", len(s["rect"]) == 4, sk.GeometryCount - s["before"])


def others():
    import Part
    import Sketcher

    sk = s["sk"]
    App.ActiveDocument.openTransaction("setup")
    a = sk.addGeometry(Part.LineSegment(V(55, 0, 0), V(75, 0, 0)))
    b = sk.addGeometry(Part.LineSegment(V(75, 0, 0), V(75, 20, 0)))
    sk.addConstraint(Sketcher.Constraint("Coincident", a, 2, b, 1))
    c = sk.addGeometry(Part.Circle(V(-25, 15, 0), V(0, 0, 1), 8))
    k = sk.addGeometry(Part.LineSegment(V(40, 30, 0), V(50, 40, 0)), True)
    sk.addConstraint(Sketcher.Constraint("Coincident", s["rect"][1], 2, k, 1))
    App.ActiveDocument.commitTransaction()
    sk.solve()
    App.ActiveDocument.recompute()
    s["chain"], s["circle"], s["constr"] = [a, b], c, k
    Gui.Selection.clearSelection()
    h.fit(iso=False)


def _edge_at(where):
    """The rectangle's line through the sketch point `where`."""
    sk = s["sk"]
    for i in s["rect"]:
        g = sk.Geometry[i]
        if (g.StartPoint - where).Length + (g.EndPoint - where).Length - g.length() < 1e-6:
            return i
    return None


# -- A ----------------------------------------------------------------------------------------
def a_double():
    Gui.Selection.clearSelection()
    double_click(V(20, 0, 0))


a_double.wait_ms = 900


def a_check():
    got = names()
    h.check(
        "A double-click on an edge selects the rectangle's four edges",
        got == edges(s["rect"]),
        sorted(got),
    )
    h.check(
        "A ...not the construction line touching it",
        "Edge%d" % (s["constr"] + 1) not in got,
        sorted(got),
    )
    h.shot("A-chain")


# -- B ----------------------------------------------------------------------------------------
def b_double_chain():
    st.esc()
    st.esc()
    double_click(V(75, 10, 0))


b_double_chain.wait_ms = 900


def b_chain_check():
    got = names()
    h.check(
        "B Esc cleared, the open chain's double-click selects its two lines",
        got == edges(s["chain"]),
        sorted(got),
    )
    st.esc()
    st.esc()
    double_click(V(-25, 23, 0))


b_chain_check.wait_ms = 900


def b_circle_check():
    got = names()
    h.check(
        "B a double-click on the circle selects only the circle",
        got == edges([s["circle"]]),
        sorted(got),
    )
    # a selection to be replaced by the next box
    st.esc()
    st.esc()
    double_click(V(0, 15, 0))


b_circle_check.wait_ms = 900


# -- C ----------------------------------------------------------------------------------------
def c_window():
    h.check("C (the rectangle is selected first)", names() == edges(s["rect"]), sorted(names()))
    pts = [st.g(V(-34, 6, 0)), st.g(V(-16, 24, 0))]
    sel.box_around(pts, margin=4)


c_window.wait_ms = 900


def c_window_check():
    got = names()
    h.check(
        "C a plain window replaces the selection: the circle",
        "Edge%d" % (s["circle"] + 1) in got and not (got & edges(s["rect"])),
        sorted(got),
    )
    pts = [st.g(V(53, -3, 0)), st.g(V(78, 23, 0))]
    sel.box_around(pts, margin=4, modifiers=sel.SHIFT)


c_window_check.wait_ms = 900


def c_shift_check():
    got = names()
    h.check("C Shift + window adds the open chain's lines", edges(s["chain"]) <= got, sorted(got))
    h.check("C ...the circle stays selected", "Edge%d" % (s["circle"] + 1) in got, sorted(got))


# -- D / E ------------------------------------------------------------------------------------
def d_crossing():
    st.esc()
    st.esc()
    s["top"] = _edge_at(V(20, 30, 0))
    pts = [st.g(V(18, 27, 0)), st.g(V(22, 33, 0))]
    sel.box_around(pts, margin=2, crossing=True)


d_crossing.wait_ms = 900


def d_check():
    got = names()
    h.check(
        "D a crossing box over the top edge selects it",
        "Edge%d" % (s["top"] + 1) in got,
        sorted(got),
    )
    h.check(
        "D ...and no other rectangle edge",
        not ((got - {"Edge%d" % (s["top"] + 1)}) & edges(s["rect"])),
        sorted(got),
    )
    # add the circle with Shift + window, then take the top edge out with Ctrl
    pts = [st.g(V(-34, 6, 0)), st.g(V(-16, 24, 0))]
    sel.box_around(pts, margin=4, modifiers=sel.SHIFT)


d_check.wait_ms = 900


def e_ctrl():
    s["before_ctrl"] = names()
    pts = [st.g(V(18, 27, 0)), st.g(V(22, 33, 0))]
    sel.box_around(pts, margin=2, crossing=True, modifiers=sel.CTRL)


e_ctrl.wait_ms = 900


def e_check():
    got = names()
    top = "Edge%d" % (s["top"] + 1)
    h.check(
        "E (before: the top edge and the circle)",
        {top, "Edge%d" % (s["circle"] + 1)} <= s["before_ctrl"],
        sorted(s["before_ctrl"]),
    )
    h.check("E Ctrl + box takes the selected top edge out", top not in got, sorted(got))
    h.check("E ...the circle stays", "Edge%d" % (s["circle"] + 1) in got, sorted(got))


# -- F ----------------------------------------------------------------------------------------
def f_empty():
    st.esc()
    st.esc()
    double_click(V(-25, 34, 0))


f_empty.wait_ms = 900


def f_check():
    h.check(
        "F Esc cleared; a double-click on empty space selects nothing", not names(), sorted(names())
    )
    s["count"] = s["sk"].GeometryCount
    h.press("l")


def f_line_a():
    si.click(st.g(V(0, 36, 0)))


def f_line_b():
    si.click(st.g(V(20, 36, 0)))


def f_line_end():
    dclick_at(h.screen_point(st.g(V(20, 36, 0))))


f_line_end.wait_ms = 900


def f_line_check():
    sk = s["sk"]
    h.check(
        "F the Line tool drew its line",
        sk.GeometryCount == s["count"] + 1,
        sk.GeometryCount - s["count"],
    )
    h.check("F its double-click selected no chain", not names(), sorted(names()))
    st.esc()


def finish():
    h.ribbon("Finish Sketch")


def finished():
    h.check("left the sketch", h.in_sketch() is None)


h.run(
    "sketch2_select",
    si.watched(
        st.start_steps("Sketch2Select")
        + [
            grid_fine,
            rect_key,
            rect_a,
            rect_b,
            rect_done,
            others,
            a_double,
            a_check,
            b_double_chain,
            b_chain_check,
            b_circle_check,
            c_window,
            c_window_check,
            c_shift_check,
            d_crossing,
            d_check,
            e_ctrl,
            e_check,
            f_empty,
            f_check,
            f_line_a,
            f_line_b,
            f_line_end,
            f_line_check,
            finish,
            finished,
        ]
    ),
)
