# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Trim (T), Extend and Break on SciForge's own handler (sketch_modify_tools.py),
with real clicks, a press-drag and keys.

Lines are put in the sketch first.
Trim: T (Fusion's key) starts SciForge's Trim; the piece of the line y = 5 between the
upright lines x = -75 and x = -45 lights up in red under the pointer and a click removes
it (the two outer pieces stay, each end kept on the line it was cut at); a press and
drag across the upper ends of three upright lines removes all three pieces down to the
line y = -20 they cross, in one Ctrl+Z.
Extend: a click near the right end of the line (5, 15)-(25, 15) extends it to the upright
line x = 45 (exactly), its end kept on that line; a line with nothing ahead stays as it is
(and says so).
Break: a click on the upright line x = 65 between the lines y = -15 and y = 5 breaks it
there into three pieces joined end to end; a circle crossed by a line breaks into two
arcs joined at both cuts (separate curves, as Fusion breaks them).
"""

import FreeCAD as App

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import sketch_tools_steps as st

V = App.Vector
s = st.s


def add_line(a, b):
    import Part

    return st.sketch().addGeometry(Part.LineSegment(a, b))


def reference():
    import Part

    # trim by a click
    s["h"] = add_line(V(-85, 5, 0), V(-25, 5, 0))
    s["v1"] = add_line(V(-75, -15, 0), V(-75, 25, 0))
    s["v2"] = add_line(V(-45, -15, 0), V(-45, 25, 0))
    # trim by dragging: three uprights through the line y = -20
    s["cut"] = add_line(V(5, -20, 0), V(45, -20, 0))
    s["uprights"] = [add_line(V(x, -35, 0), V(x, -5, 0)) for x in (15, 25, 35)]
    # extend
    s["e1"] = add_line(V(5, 15, 0), V(25, 15, 0))
    s["target"] = add_line(V(45, 5, 0), V(45, 25, 0))
    s["lonely"] = add_line(V(-85, -45, 0), V(-65, -45, 0))
    # break
    s["b1"] = add_line(V(65, -35, 0), V(65, 25, 0))
    add_line(V(55, -15, 0), V(75, -15, 0))
    add_line(V(55, 5, 0), V(75, 5, 0))
    s["circle"] = st.sketch().addGeometry(Part.Circle(V(-35, -35, 0), V(0, 0, 1), 6))
    add_line(V(-45, -35, 0), V(-25, -35, 0))
    App.ActiveDocument.recompute()


def lines_on_y(y):
    sk = st.sketch()
    return [
        (i, g)
        for i, g in enumerate(sk.Geometry)
        if g.TypeId == "Part::GeomLineSegment"
        and abs(g.StartPoint.y - y) < 1e-9
        and abs(g.EndPoint.y - y) < 1e-9
    ]


def lines_on_x(x):
    sk = st.sketch()
    return [
        (i, g)
        for i, g in enumerate(sk.Geometry)
        if g.TypeId == "Part::GeomLineSegment"
        and abs(g.StartPoint.x - x) < 1e-9
        and abs(g.EndPoint.x - x) < 1e-9
    ]


def spans(items, axis):
    out = []
    for _i, g in items:
        a, b = getattr(g.StartPoint, axis), getattr(g.EndPoint, axis)
        out.append((round(min(a, b), 6), round(max(a, b), 6)))
    return sorted(out)


# == Trim =================================================================================
def trim_key():
    st.hover(V(-60, 15, 0))
    h.press("t")


def trim_hover():
    h.check("T runs SciForge's Trim", st.tool_title() == "Trim", st.tool_title())
    st.hover(V(-60, 5, 0))
    remove = st.preview().get("remove", [])
    ok = len(remove) == 1 and len(remove[0]) > 2
    h.check("the piece to remove lights up", ok, remove)
    if ok:
        xs = sorted(p[0] for p in remove[0])
        h.check(
            "it is the piece between the two uprights",
            st.near(xs[0], -75.0, 1e-6) and st.near(xs[-1], -45.0, 1e-6),
            (xs[0], xs[-1]),
        )
    h.shot("1-trim-hover")


def trim_click():
    s["before"] = len(st.sketch().Geometry)
    st.click(V(-60, 5, 0), towards=V(0, 0, 0))


def trim_check():
    pieces = [p for p in spans(lines_on_y(5), "x") if p[1] < 0]
    h.check(
        "the middle piece went, the outer pieces stay",
        pieces == [(-85.0, -75.0), (-45.0, -25.0)],
        pieces,
    )
    st.sketch_ok("trim click")
    h.check("Trim waits for the next piece", st.tool_title() == "Trim")


def trim_drag():
    s["drag_before"] = [spans(lines_on_x(x), "y") for x in (15, 25, 35)]
    st.press(V(10, -10, 0))
    end = st.drag_to(V(40, -10, 0), steps=16)
    st.release(end)


trim_drag.wait_ms = 1000


def trim_drag_check():
    after = [spans(lines_on_x(x), "y") for x in (15, 25, 35)]
    h.check(
        "the drag removed the three upper pieces down to y = -20",
        after == [[(-35.0, -20.0)]] * 3,
        (s["drag_before"], after),
    )
    st.sketch_ok("trim drag")


def trim_drag_undo():
    st.undo()


def trim_drag_undo_check():
    after = [spans(lines_on_x(x), "y") for x in (15, 25, 35)]
    h.check("one Ctrl+Z brings all three back", after == [[(-35.0, -5.0)]] * 3, after)
    st.esc()


# == Extend ===============================================================================
def extend_open():
    si.menu_item("MODIFY", "Extend")


def extend_hover():
    h.check("SciForge's Extend runs", st.tool_title() == "Extend", st.tool_title())
    st.hover(V(22, 15, 0))
    curves = st.preview().get("curves", [])
    ok = len(curves) == 1 and len(curves[0]) == 2
    h.check("the extension shows", ok, curves)
    if ok:
        h.check(
            "from the line's end to the upright line",
            st.vnear(V(*curves[0][0], 0), V(25, 15, 0), 1e-6)
            and st.vnear(V(*curves[0][1], 0), V(45, 15, 0), 1e-6),
            curves,
        )


def extend_click():
    st.click(V(22, 15, 0), towards=V(0, 0, 0))


def extend_check():
    g = st.sketch().Geometry[s["e1"]]
    h.check("the line now ends on x = 45", st.vnear(g.EndPoint, V(45, 15, 0), 1e-9), g.EndPoint)
    h.check("its start stayed", st.vnear(g.StartPoint, V(5, 15, 0), 1e-9), g.StartPoint)
    h.check(
        "its end is kept on the upright line",
        any(
            c[0] == "PointOnObject" and c[1] == s["e1"] and c[3] == s["target"]
            for c in st.constraints_of(s["e1"])
        ),
        st.constraints_of(s["e1"]),
    )
    st.sketch_ok("extend")


def extend_nothing():
    st.click(V(-68, -45, 0), towards=V(0, 0, 0))


def extend_nothing_check():
    g = st.sketch().Geometry[s["lonely"]]
    h.check("a line with nothing ahead stays", st.near(g.EndPoint.x, -65.0, 1e-9), g.EndPoint)
    t = st.tool()
    h.check("...and says why", t is not None and "no curve" in t.hint_text(), t and t.hint_text())
    st.esc()


# == Break ================================================================================
def break_open():
    si.menu_item("MODIFY", "Break")


def break_click():
    h.check("SciForge's Break runs", st.tool_title() == "Break", st.tool_title())
    st.hover(V(65, -5, 0))
    picked = st.preview().get("picked", [])
    h.check("the piece between the crossings shows", len(picked) == 1, picked)
    st.click(V(65, -5, 0), towards=V(0, 0, 0))


def break_check():
    pieces = spans(lines_on_x(65), "y")
    h.check("three pieces", pieces == [(-35.0, -15.0), (-15.0, 5.0), (5.0, 25.0)], pieces)
    joins = [c for c in st.sketch().Constraints if c.Type == "Coincident"]
    on65 = {i for i, _g in lines_on_x(65)}
    h.check(
        "joined end to end (two Coincident)",
        len([c for c in joins if c.First in on65 and c.Second in on65]) == 2,
        [(c.First, c.Second) for c in joins],
    )
    st.sketch_ok("break line")


def break_circle():
    s["arcs_before"] = len([g for g in st.sketch().Geometry if g.TypeId == "Part::GeomArcOfCircle"])
    st.click(V(-35, -29, 0), towards=V(0, 0, 0))


def break_circle_check():
    sk = st.sketch()
    arcs = [(i, g) for i, g in enumerate(sk.Geometry) if g.TypeId == "Part::GeomArcOfCircle"]
    circles = [g for g in sk.Geometry if g.TypeId == "Part::GeomCircle"]
    h.check(
        "the circle became two arcs",
        len(circles) == 0 and len(arcs) == 2,
        (len(circles), len(arcs)),
    )
    if len(arcs) == 2:
        (i, a), (j, b) = arcs
        h.check("still on one circle (concentric as drawn)", st.vnear(a.Center, b.Center, 1e-6))
        spans_ = sorted(
            [
                round(a.LastParameter - a.FirstParameter, 6),
                round(b.LastParameter - b.FirstParameter, 6),
            ]
        )
        h.check(
            "each half the circle (the line through its centre)",
            spans_ == [3.141593, 3.141593],
            spans_,
        )
        joins = [
            c for c in sk.Constraints if c.Type == "Coincident" and {c.First, c.Second} == {i, j}
        ]
        h.check(
            "joined at both cuts",
            len(joins) == 2 and all(c.FirstPos != 3 for c in joins),
            [(c.FirstPos, c.SecondPos) for c in joins],
        )
    st.sketch_ok("break circle")


def break_undo():
    st.esc()
    st.undo()


def break_undo_check():
    circles = [g for g in st.sketch().Geometry if g.TypeId == "Part::GeomCircle"]
    h.check("one Ctrl+Z gives the circle back", len(circles) == 1, len(circles))


def finish():
    h.ribbon("Finish Sketch")


h.run(
    "sketch_tools_modify",
    si.watched(
        st.start_steps("SketchToolsModify")
        + [
            reference,
            trim_key,
            trim_hover,
            trim_click,
            trim_check,
            trim_drag,
            trim_drag_check,
            trim_drag_undo,
            trim_drag_undo_check,
            extend_open,
            extend_hover,
            extend_click,
            extend_check,
            extend_nothing,
            extend_nothing_check,
            break_open,
            break_click,
            break_check,
            break_circle,
            break_circle_check,
            break_undo,
            break_undo_check,
            finish,
        ]
    ),
)
