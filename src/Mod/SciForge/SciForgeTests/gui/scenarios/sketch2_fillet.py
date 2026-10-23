# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sketch Fillet and Chamfer between a line and an arc (parity/sketch.md, "Sketch, part
2"), with real clicks and keys on SciForge's own tools (they compute their picks
themselves, so they also work on CI's virtual screen).

Four shapes on the XY plane, each a line ending on a quarter arc (radius 15) at a corner:
  S1 line (0,0)-(40,0), arc centre (55,0) from (55,15) to (40,0); a second line (0,0)-(0,30)
  S2 the same 40 lower (y = -40), S3 at y = -80, S4 at y = -120.

  A  MODIFY > Fillet: the line, then the arc of S1, type 3, Enter: an arc of radius 3
     tangent to both, the line and the arc cut back to it, a Radius dimension 3; Ctrl+Z
     takes it back in one step, Ctrl+Y brings it again
  B  Fillet at the corner point (0, 0) of two lines: 50 is held at the largest radius that
     fits (30: the 30 mm line) and said by the pointer (Luca's decision of 2026-10-21: it was
     refused); that fillet takes the 30 mm line whole (no sliver of it is left, it stays as
     a construction line); Ctrl+Z; the corner again, 4, Enter: radius 4, the old corner kept
     as a construction point
  C  MODIFY > Chamfer, Equal distance, the corner point (40, -40) of S2: type 4, Enter: the
     chamfer from 4 along the line to 4 (straight) from the corner on the arc, two 4 mm
     dimensions from the old corner, the second following the first (fx)
  D  Two distances, the arc of S3 first, then the line: 5, Tab, 3, Enter: D1 = 5 on the arc,
     D2 = 3 on the line
  E  Distance and angle on S4 (the line first): 5, Tab, 40, Enter: 5 along the line and 40
     degrees between the line and the chamfer; Ctrl+Z / Ctrl+Y
  F  Two arcs cannot be chamfered (the reason by the pointer)
  G  Finish Sketch, save, close, reopen: the dimensions are there; the equal chamfer set to
     3: its arc side follows
"""

import math
import os
import tempfile

import FreeCAD as App

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import sketch_tools_steps as st

V = App.Vector
s = st.s
R = 15.0
Y = {1: 0.0, 2: -40.0, 3: -80.0, 4: -120.0}
A135 = math.radians(135)


def sk():
    return st.sketch()


def on_arc(n, angle=A135):
    return V(55 + R * math.cos(angle), Y[n] + R * math.sin(angle), 0)


def chooser_combo():
    from PySide import QtWidgets
    from sciforge import sketch_chamfer_tool

    found = h.gl_widget().findChildren(QtWidgets.QWidget, sketch_chamfer_tool.CHOOSER_NAME)
    shown = [w for w in found if w.isVisible()]
    return shown[0].findChild(QtWidgets.QComboBox) if shown else None


def choose(label):
    combo = chooser_combo()
    h.check("the Chamfer Type box is shown", combo is not None)
    if combo is not None:
        h.check("type %s" % label, ui.choose(combo, label))


def geo_count():
    return len(sk().Geometry)


def lines_with_end(point, tol=1e-6):
    out = []
    for i, g in enumerate(sk().Geometry):
        if g.TypeId == "Part::GeomLineSegment" and any(
            (e - point).Length < tol for e in (g.StartPoint, g.EndPoint)
        ):
            out.append(i)
    return out


def hint():
    t = st.tool()
    return t.hint_text() if t is not None else ""


# -- setup ----------------------------------------------------------------------------------
def shapes():
    import Part
    import Sketcher

    from sciforge import grid_ui

    grid_ui.put("Subdivisions", 10)
    grid_ui.apply_subdivisions()
    App.ActiveDocument.openTransaction("shapes")
    s["shape"] = {}
    for n, y in Y.items():
        line = sk().addGeometry(Part.LineSegment(V(0, y, 0), V(40, y, 0)))
        circle = Part.Circle(V(55, y, 0), V(0, 0, 1), R)
        arc = sk().addGeometry(Part.ArcOfCircle(circle, math.pi / 2, math.pi))
        sk().addConstraint(
            [
                Sketcher.Constraint("Coincident", line, 2, arc, 2),
                Sketcher.Constraint("Horizontal", line),
                Sketcher.Constraint("DistanceX", -1, 1, arc, 3, 55.0),
                Sketcher.Constraint("DistanceY", -1, 1, arc, 3, y),
                Sketcher.Constraint("Radius", arc, R),
            ]
        )
        if n > 1:
            sk().addConstraint(Sketcher.Constraint("DistanceX", -1, 1, line, 1, 0.0))
            sk().addConstraint(Sketcher.Constraint("DistanceY", -1, 1, line, 1, y))
        s["shape"][n] = (line, arc)
    up = sk().addGeometry(Part.LineSegment(V(0, 0, 0), V(0, 30, 0)))
    sk().addConstraint(Sketcher.Constraint("Coincident", s["shape"][1][0], 1, up, 1))
    s["up"] = up
    App.ActiveDocument.commitTransaction()
    sk().solve()
    App.ActiveDocument.recompute()
    h.fit(iso=False)


# -- A: fillet a line and an arc ------------------------------------------------------------
def a_open():
    s["n"] = geo_count()
    si.menu_item("MODIFY", "Fillet")


def a_line():
    h.check("A SciForge's Fillet runs", st.tool_title() == "Fillet", st.tool_title())
    st.click(V(20, 0, 0))


def a_arc():
    st.click(on_arc(1))


def a_type():
    h.check("A after two curves the tool asks for the radius", st.tool().step == 2, st.tool().step)
    st.keys("3\n")


a_type.wait_ms = 900


def a_check():
    from sciforge import sketch_fillet_core as core

    g = sk().Geometry
    new = list(range(s["n"], len(g)))
    arcs = [i for i in new if g[i].TypeId == "Part::GeomArcOfCircle"]
    h.check("A one new arc", len(arcs) == 1, [g[i].TypeId for i in new])
    if not arcs:
        return
    s["fillet_arc"] = arcs[0]
    h.check("A its radius is 3", st.near(g[arcs[0]].Radius, 3.0), g[arcs[0]].Radius)
    radius = [c for c in sk().Constraints if c.Type == "Radius" and c.First == arcs[0]]
    h.check(
        "A a Radius dimension of 3",
        len(radius) == 1 and st.near(radius[0].Value, 3.0),
        [(c.Type, c.Value) for c in radius],
    )
    tangents = [
        c for c in sk().Constraints if c.Type == "Tangent" and arcs[0] in (c.First, c.Second)
    ]
    h.check("A tangent to both curves", len(tangents) == 2, len(tangents))
    line, arc = s["shape"][1]
    c1 = ("line", (0.0, 0.0), (40.0, 0.0))
    c2 = ("arc", (55.0, 0.0), R, math.pi / 2, math.pi)
    centre, t1, t2 = core.fillet(c1, c2, 3.0, (20.0, 0.0), (on_arc(1).x, on_arc(1).y))
    end = g[line].EndPoint
    h.check(
        "A the line ends where the fillet touches it",
        st.vnear(end, V(t1[0], t1[1], 0), 1e-5),
        (end, t1),
    )
    h.check(
        "A the arc ends where the fillet touches it",
        any(st.vnear(p, V(t2[0], t2[1], 0), 1e-5) for p in (g[arc].StartPoint, g[arc].EndPoint)),
        (g[arc].StartPoint, g[arc].EndPoint, t2),
    )
    st.sketch_ok("A")
    h.check("A the tool waits for the next corner", st.tool() is not None and st.tool().step == 0)
    h.shot("A-fillet")
    st.esc()
    st.undo()


def a_undone():
    h.check("A one Ctrl+Z takes the fillet back", geo_count() == s["n"], geo_count() - s["n"])
    st.redo()


def a_redone():
    h.check("A Ctrl+Y brings it again", geo_count() == s["n"] + 1, geo_count() - s["n"])


# -- B: fillet at a corner point of two lines -------------------------------------------------
def b_open():
    s["n"] = geo_count()
    si.menu_item("MODIFY", "Fillet")


def b_corner():
    st.click(V(0, 0, 0))


def b_too_big():
    h.check(
        "B the corner point picks both lines",
        st.tool() is not None and st.tool().step == 2,
        st.tool() and st.tool().step,
    )
    st.keys("50\n")


b_too_big.wait_ms = 900


def b_refused():
    g = sk().Geometry
    new = list(range(s["n"], len(g)))
    arcs = [i for i in new if g[i].TypeId == "Part::GeomArcOfCircle"]
    r = g[arcs[0]].Radius if len(arcs) == 1 else 0
    h.check("B 50 makes the largest fillet that fits (the 30 mm line)", st.near(r, 30.0), r)
    h.check(
        "B ...and the pointer says so",
        "50 mm does not fit: limited to %.2f mm" % r in hint(),
        hint(),
    )
    # the largest fillet takes the 30 mm line whole: no sliver of it is left, it stays as a
    # construction line (with its constraints) and the arc ends at its far end (0, 30)
    lines = [(i, x) for i, x in enumerate(g) if x.TypeId == "Part::GeomLineSegment"]
    slivers = [x for i, x in lines if not sk().getConstruction(i) and x.length() < 0.01]
    h.check("B no sliver of the line is left", not slivers, slivers)
    kept = [
        i
        for i, x in lines
        if sk().getConstruction(i)
        and st.vnear(x.StartPoint, V(0, 0, 0))
        and st.vnear(x.EndPoint, V(0, 30, 0))
    ]
    ends = (g[arcs[0]].StartPoint, g[arcs[0]].EndPoint) if len(arcs) == 1 else ()
    h.check("B the 30 mm line stays whole, as construction", len(kept) == 1, lines)
    h.check(
        "B the arc ends at its far end (0, 30)",
        any(st.vnear(p, V(0, 30, 0), 1e-6) for p in ends),
        ends,
    )
    st.sketch_ok("B")
    st.esc()
    st.undo()


b_refused.wait_ms = 900


def b_undone():
    h.check("B Ctrl+Z takes it back", geo_count() == s["n"], geo_count() - s["n"])
    si.menu_item("MODIFY", "Fillet")


def b_corner_again():
    st.click(V(0, 0, 0))


def b_four():
    h.check("B the corner again", st.tool() is not None and st.tool().step == 2)
    st.keys("4\n")


b_four.wait_ms = 900


def b_check():
    g = sk().Geometry
    new = list(range(s["n"], len(g)))
    arcs = [i for i in new if g[i].TypeId == "Part::GeomArcOfCircle"]
    points = [i for i in new if g[i].TypeId == "Part::GeomPoint"]
    h.check(
        "B radius 4", len(arcs) == 1 and st.near(g[arcs[0]].Radius, 4.0), [g[i].TypeId for i in new]
    )
    h.check(
        "B the old corner stays as a construction point at (0, 0)",
        len(points) == 1
        and sk().getConstruction(points[0])
        and st.vnear(V(g[points[0]].X, g[points[0]].Y, 0), V(0, 0, 0), 1e-6),
        points,
    )
    st.sketch_ok("B")
    st.esc()


# -- C: chamfer, equal distance, corner point ------------------------------------------------
def c_open():
    s["n"] = geo_count()
    si.menu_item("MODIFY", "Chamfer")


def c_type():
    choose("Equal distance")


def c_corner():
    st.click(V(40, Y[2], 0))


def c_keys():
    h.check("C the corner point picks the line and the arc", st.tool().step == 2, st.tool().step)
    st.keys("4\n")


c_keys.wait_ms = 900


def _chamfer_check(where, n, s_line, s_arc, angle=None, construction=True):
    from sciforge import sketch_chamfer_core as core

    line, arc = s["shape"][n]
    y = Y[n]
    data = core.line_arc_corner(((0.0, y), (40.0, y)), ((55.0, y), R, math.pi / 2, math.pi))
    p1 = core.line_point(data, s_line)
    p2 = core.arc_point(data, s_arc)
    g = sk().Geometry
    h.check(
        "%s the line ends %g from the corner" % (where, s_line),
        st.vnear(g[line].EndPoint, V(p1[0], p1[1], 0), 1e-5),
        g[line].EndPoint,
    )
    arc_ends = (g[arc].StartPoint, g[arc].EndPoint)
    h.check(
        "%s the arc ends %g (straight) from the corner" % (where, s_arc),
        any(st.vnear(p, V(p2[0], p2[1], 0), 1e-5) for p in arc_ends),
        arc_ends,
    )
    chamfer = [
        i
        for i in range(len(g))
        if g[i].TypeId == "Part::GeomLineSegment"
        and {round(v, 4) for v in (g[i].StartPoint.x, g[i].EndPoint.x)}
        == {round(p1[0], 4), round(p2[0], 4)}
    ]
    h.check("%s a chamfer line joins them" % where, len(chamfer) == 1, chamfer)
    corner = [
        i
        for i in range(len(g))
        if g[i].TypeId == "Part::GeomPoint" and st.vnear(V(g[i].X, g[i].Y, 0), V(40, y, 0), 1e-6)
    ]
    # (FreeCAD does not keep a point's construction flag in the file: a point never makes
    # a profile anyway)
    h.check(
        "%s the old corner is a construction point" % where,
        len(corner) == 1 and (sk().getConstruction(corner[0]) or not construction),
        corner,
    )
    if corner:
        dims = [c for c in sk().Constraints if c.Type == "Distance" and c.First == corner[0]]
        values = sorted(round(c.Value, 6) for c in dims)
        want = sorted([round(s_line, 6)] + ([] if angle is not None else [round(s_arc, 6)]))
        h.check("%s distance dimensions from the corner %s" % (where, want), values == want, values)
        s["corner_%d" % n] = corner[0]
    if angle is not None:
        angles = [c for c in sk().Constraints if c.Type == "Angle"]
        h.check(
            "%s an angle dimension of %g degrees" % (where, angle),
            any(st.near(math.degrees(c.Value), angle, 1e-6) for c in angles),
            [math.degrees(c.Value) for c in angles],
        )
    st.sketch_ok(where)


def c_check():
    _chamfer_check("C", 2, 4.0, 4.0)
    # the line-arc chamfer rewrites the curves it cuts: B's old corner (0, 0) stays a
    # construction point (it came back as a normal point)
    corner_b = [
        i
        for i, x in enumerate(sk().Geometry)
        if x.TypeId == "Part::GeomPoint" and st.vnear(V(x.X, x.Y, 0), V(0, 0, 0), 1e-6)
    ]
    h.check(
        "C B's old corner is still a construction point",
        len(corner_b) == 1 and sk().getConstruction(corner_b[0]),
        [(i, sk().getConstruction(i)) for i in corner_b],
    )
    named = [c for c in sk().Constraints if c.Name.startswith("Chamfer")]
    exprs = [e for e in sk().ExpressionEngine if "Chamfer" in e[0] and "Chamfer" in e[1]]
    h.check(
        "C the second distance follows the first (fx)",
        len(named) == 2 and len(exprs) == 1,
        ([c.Name for c in named], exprs),
    )
    h.shot("C-chamfer")


# -- D: two distances, the arc first -------------------------------------------------------------
def d_type():
    choose("Two distances")


def d_arc():
    st.click(on_arc(3))


def d_line():
    st.click(V(20, Y[3], 0))


def d_keys():
    st.keys("5\t3\n")


d_keys.wait_ms = 900


def d_check():
    _chamfer_check("D", 3, 3.0, 5.0)


# -- E: distance and angle, then undo / redo ------------------------------------------------------
def e_type():
    choose("Distance and angle")


def e_line():
    st.click(V(20, Y[4], 0))


def e_arc():
    st.click(on_arc(4))


def e_keys():
    s["n_e"] = geo_count()
    st.keys("5\t40\n")


e_keys.wait_ms = 900


def e_check():
    from sciforge import sketch_chamfer_core as core

    y = Y[4]
    data = core.line_arc_corner(((0.0, y), (40.0, y)), ((55.0, y), R, math.pi / 2, math.pi))
    p1 = core.line_point(data, 5.0)
    p2, chord = core.arc_point_at_angle(data, p1, math.radians(40))
    _chamfer_check("E", 4, 5.0, chord, angle=40.0)
    st.esc()
    st.undo()


def e_undone():
    h.check("E Ctrl+Z takes the chamfer back", geo_count() == s["n_e"], geo_count() - s["n_e"])
    st.redo()


def e_redone():
    h.check("E Ctrl+Y brings it again", geo_count() == s["n_e"] + 2, geo_count() - s["n_e"])


# -- F: two arcs ------------------------------------------------------------------------------
def f_open():
    s["n"] = geo_count()
    si.menu_item("MODIFY", "Chamfer")


def f_first():
    st.click(on_arc(1, math.radians(100)))


def f_second():
    arc = s.get("fillet_arc")
    g = sk().Geometry[arc]
    mid = g.value((g.FirstParameter + g.LastParameter) / 2.0)
    st.click(mid)


def f_check():
    h.check("F two arcs: refused, nothing made", geo_count() == s["n"], geo_count() - s["n"])
    h.check("F ...the reason by the pointer", "line" in hint(), hint())
    st.esc()


# -- G: save and reopen ---------------------------------------------------------------------------
def g_finish():
    h.ribbon("Finish Sketch")


def g_save():
    h.check("G the sketch closes", h.in_sketch() is None)
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-sketch2-fillet-"), "fillet.FCStd")
    s["path"] = path
    s["name"] = sk().Name
    App.ActiveDocument.saveAs(path)
    App.closeDocument(App.ActiveDocument.Name)


def g_reopen():
    App.openDocument(s["path"])
    h.fit()


def g_check():
    doc = App.ActiveDocument
    sketch = doc.getObject(s["name"])
    s["sk"] = sketch
    h.check("G reopened: the sketch is there", sketch is not None)
    if sketch is None:
        return
    st.sketch_ok("G reopened")
    named = sorted(c.Name for c in sketch.Constraints if c.Name.startswith("Chamfer"))
    h.check("G reopened: the equal chamfer's dimensions", len(named) == 2, named)
    if len(named) == 2:
        sketch.setDatum(named[0], App.Units.Quantity("3 mm"))
        doc.recompute()
        _chamfer_check("G reopened, set to 3", 2, 3.0, 3.0, construction=False)


h.run(
    "sketch2_fillet",
    si.watched(
        st.start_steps("Sketch2Fillet")
        + [
            shapes,
            a_open,
            a_line,
            a_arc,
            a_type,
            a_check,
            a_undone,
            a_redone,
            b_open,
            b_corner,
            b_too_big,
            b_refused,
            b_undone,
            b_corner_again,
            b_four,
            b_check,
            c_open,
            c_type,
            c_corner,
            c_keys,
            c_check,
            d_type,
            d_arc,
            d_line,
            d_keys,
            d_check,
            e_type,
            e_line,
            e_arc,
            e_keys,
            e_check,
            e_undone,
            e_redone,
            f_open,
            f_first,
            f_second,
            f_check,
            g_finish,
            g_save,
            g_reopen,
            g_check,
        ]
    ),
)
