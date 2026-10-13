# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Collinear, Concentric, Midpoint and Curvature constraints with Fusion's pick
flow (sketch_constrain_tools.py): start the command, click two things, the constraint is
added, the command waits for the next pair; with two things selected first it applies at
once; Esc ends it.

Collinear: two lines end up on one line (FreeCAD: a line-line Tangent).
Concentric: a circle and an arc share their centre (Coincident centres).
Midpoint: a point goes to the middle of a line (Symmetric), another to the middle of an
arc (on the arc, on the bisector of its ends).
Curvature: a spline and the line it starts from: tangent join plus the spline's second
pole on the line, so the curvature at the join is 0 (exact G2). A spline and an arc: only
tangent (FreeCAD's solver has no curvature constraint), and the hint says so.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import sketch_tools_steps as st

V = App.Vector
s = st.s


def add(geo):
    return st.sketch().addGeometry(geo)


def reference():
    import Part

    s["l1"] = add(Part.LineSegment(V(-85, 25, 0), V(-65, 25, 0)))
    s["l2"] = add(Part.LineSegment(V(-55, 32, 0), V(-35, 35, 0)))
    s["c1"] = add(Part.Circle(V(-55, -25, 0), V(0, 0, 1), 10))
    s["a1"] = add(Part.ArcOfCircle(Part.Circle(V(-50, -20, 0), V(0, 0, 1), 5), 0.0, math.pi))
    s["m"] = add(Part.LineSegment(V(5, 25, 0), V(45, 25, 0)))
    s["p"] = add(Part.Point(V(30, 35, 0)))
    s["arc"] = add(Part.ArcOfCircle(Part.Circle(V(25, -30, 0), V(0, 0, 1), 10), 0.2, 2.5))
    s["q"] = add(Part.Point(V(40, -15, 0)))
    s["l3"] = add(Part.LineSegment(V(-85, -55, 0), V(-65, -55, 0)))
    s["l4"] = add(Part.LineSegment(V(-55, -60, 0), V(-35, -58, 0)))
    spline = Part.BSplineCurve()
    spline.buildFromPoles([V(55, 15, 0), V(60, 30, 0), V(70, 30, 0), V(75, 20, 0)], False, 3)
    s["spline"] = add(spline)
    st.sketch().exposeInternalGeometry(s["spline"])
    s["ll"] = add(Part.LineSegment(V(45, 5, 0), V(55, 15, 0)))
    spline2 = Part.BSplineCurve()
    spline2.buildFromPoles([V(55, -45, 0), V(60, -35, 0), V(70, -35, 0), V(75, -45, 0)], False, 3)
    s["spline2"] = add(spline2)
    st.sketch().exposeInternalGeometry(s["spline2"])
    s["arc2"] = add(
        Part.ArcOfCircle(Part.Circle(V(85, -45, 0), V(0, 0, 1), 10), math.pi, 1.5 * math.pi)
    )
    App.ActiveDocument.recompute()


def geo(name):
    return st.sketch().Geometry[s[name]]


def cross2(a, b):
    return a.x * b.y - a.y * b.x


# == Collinear ==============================================================================
def co_open():
    si.menu_item("CONSTRAINTS", "Collinear")


def co_pick():
    h.check("Collinear runs", st.tool_title() == "Collinear", st.tool_title())
    st.click(V(-75, 25, 0))
    st.hover(V(-45, 33.5, 0))
    h.check("the line under the pointer lights up", len(st.preview().get("picked", [])) == 2)
    st.click(V(-45, 33.5, 0))


def co_check():
    a, b = geo("l1"), geo("l2")
    d = a.EndPoint - a.StartPoint
    off = [abs(cross2(d, p - a.StartPoint)) / d.Length for p in (b.StartPoint, b.EndPoint)]
    h.check("both lines on one line", max(off) < 1e-6, off)
    h.check(
        "FreeCAD's form: a Tangent between the lines",
        any(
            c[0] == "Tangent" and {c[1], c[3]} == {s["l1"], s["l2"]}
            for c in st.constraints_of(s["l1"])
        ),
        st.constraints_of(s["l1"]),
    )
    h.check("the command waits for the next pair", st.tool_title() == "Collinear")
    st.sketch_ok("collinear")


def co_preselected():
    st.esc()
    sk = st.sketch()
    Gui.Selection.clearSelection()
    for name in ("l3", "l4"):
        Gui.Selection.addSelection(sk.Document.Name, sk.Name, "Edge%d" % (s[name] + 1))
    si.menu_item("CONSTRAINTS", "Collinear")


def co_preselected_check():
    a, b = geo("l3"), geo("l4")
    d = a.EndPoint - a.StartPoint
    off = [abs(cross2(d, p - a.StartPoint)) / d.Length for p in (b.StartPoint, b.EndPoint)]
    h.check("two lines selected first: made collinear at once", max(off) < 1e-6, off)
    h.check("...and the command is done", st.tool() is None, st.tool_title())


# == Concentric =========================================================================
def cc_open():
    si.menu_item("CONSTRAINTS", "Concentric")


def cc_pick():
    h.check("Concentric runs", st.tool_title() == "Concentric", st.tool_title())
    st.click(V(-50, -15, 0))  # the arc's top
    st.click(V(-65, -25, 0))  # the circle's left side


def cc_check():
    h.check(
        "the centres meet",
        st.vnear(geo("c1").Center, geo("a1").Center, 1e-9),
        (geo("c1").Center, geo("a1").Center),
    )
    st.sketch_ok("concentric")
    st.esc()


# == Midpoint ================================================================================
def mp_open():
    si.menu_item("CONSTRAINTS", "Midpoint")


def mp_line():
    h.check("Midpoint runs", st.tool_title() == "Midpoint", st.tool_title())
    st.click(V(30, 35, 0))  # the point
    st.click(V(15, 25, 0))  # the line


def mp_line_check():
    line = geo("m")
    p = geo("p")
    middle = (line.StartPoint + line.EndPoint) * 0.5
    h.check(
        "the point is at the line's middle",
        st.vnear(V(p.X, p.Y, 0), middle, 1e-9),
        (p.X, p.Y, middle),
    )
    h.check(
        "FreeCAD's form: Symmetric",
        "Symmetric" in st.types(st.constraints_of(s["p"])),
        st.constraints_of(s["p"]),
    )
    st.sketch_ok("midpoint line")


def mp_arc():
    st.click(V(40, -15, 0))  # the point
    st.click(V(25, -20, 0))  # the arc's top


def mp_arc_check():
    arc = geo("arc")
    q = geo("q")
    middle = arc.value((arc.FirstParameter + arc.LastParameter) / 2.0)
    h.check(
        "the point is at the arc's middle",
        st.vnear(V(q.X, q.Y, 0), middle, 1e-7),
        (q.X, q.Y, middle),
    )
    st.sketch_ok("midpoint arc")
    st.esc()


# == Curvature =================================================================================
def cu_open():
    si.menu_item("CONSTRAINTS", "Curvature")


def cu_pick_line():
    h.check("Curvature runs", st.tool_title() == "Curvature", st.tool_title())
    # on the spline at its middle: (P0 + 3 P1 + 3 P2 + P3) / 8 = (65, 26.875)
    st.click(V(65, 26.875, 0))
    st.click(V(50, 10, 0))  # the line


def cu_line_check():
    sp = geo("spline")
    line = geo("ll")
    start = sp.value(sp.FirstParameter)
    h.check(
        "joined at the line's end", st.vnear(start, line.EndPoint, 1e-7), (start, line.EndPoint)
    )
    t = sp.tangent(sp.FirstParameter)[0]
    d = (line.EndPoint - line.StartPoint).normalize()
    h.check("tangent there", abs(cross2(t, d)) < 1e-7, (t, d))
    k = sp.curvature(sp.FirstParameter)
    h.check("curvature 0 at the join (G2 with the line)", abs(k) < 1e-7, k)
    st.sketch_ok("curvature with a line")


def cu_pick_arc():
    st.click(V(65, -37.5, 0))  # the second spline's middle
    # the arc at 225 degrees about (85, -45): (85 - 7.071, -45 - 7.071)
    st.click(V(85 - 7.0711, -45 - 7.0711, 0))


def cu_arc_check():
    sp = geo("spline2")
    arc = geo("arc2")
    end = sp.value(sp.LastParameter)
    h.check(
        "joined to the arc",
        st.vnear(end, arc.StartPoint, 1e-7) or st.vnear(end, arc.EndPoint, 1e-7),
        (end, arc.StartPoint, arc.EndPoint),
    )
    t = st.tool()
    h.check(
        "the hint says G1 only (FreeCAD has no curvature constraint)",
        t is not None and "tangent (G1)" in t.hint_text(),
        t and t.hint_text(),
    )
    st.sketch_ok("curvature with an arc")


def cu_esc():
    st.esc()
    h.check("Esc ends the command", st.tool() is None)


def finish():
    h.ribbon("Finish Sketch")


h.run(
    "sketch_tools_constraints",
    si.watched(
        st.start_steps("SketchToolsConstraints")
        + [
            reference,
            co_open,
            co_pick,
            co_check,
            co_preselected,
            co_preselected_check,
            cc_open,
            cc_pick,
            cc_check,
            mp_open,
            mp_line,
            mp_line_check,
            mp_arc,
            mp_arc_check,
            cu_open,
            cu_pick_line,
            cu_line_check,
            cu_pick_arc,
            cu_arc_check,
            cu_esc,
            finish,
        ]
    ),
)
