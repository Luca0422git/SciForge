# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's 3D Sketch (parity/sketch.md "Sketch, part 2"), real input only.

A sketch on the XY plane; SKETCH PALETTE > 3D Sketch.

  A  L: click the origin, click the manipulator's ZX plane, click 20 above the origin: a
     3D line straight up (off the sketch plane) in the sketch's "3D Curves"; the
     manipulator's XY plane, then a click 15 along X at that height: a second line from
     the same point; Esc
  B  a click on the top end point shows the triad; type 5, Enter: the point goes 5 up
     (one undo step "Move 3D Point"); Ctrl+Z / Ctrl+Y
  C  a drag of the triad's Y arrow moves the point along Y only; Ctrl+Z
  D  CREATE > Spline > Fit Point Spline (3D): two points on the plane, the manipulator's
     ZX plane, a third point 10 up; Enter: a spline through the three points
  I  L, the manipulator's XY plane, a triangle on the sketch plane closed on its first
     point: three ordinary sketch lines (joined, a profile; no 3D line); a click on its
     corner, the ZX plane, a click 15 up: a 3D line tied to the triangle's corner
  E  Finish Sketch: the browser lists "3D Curves" under the sketch; the timeline has no
     step for it; the sketch's eye hides and shows it; the triangle is a closed profile
  F  a circle (radius 2) sketched on XY at the origin, CREATE > Sweep: the circle, then a
     click on the 3D line: a tube 20 high (pi 2^2 20)
  G  save, close, reopen: the curves, their sketch and the tube are there
  H  3D Sketch off: L draws on the sketch plane again
"""

import math
import os
import tempfile

import FreeCAD as App
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import sketch_tools_steps as st
from SciForgeTests.gui import sweep_loft_steps as sw

V = App.Vector
s = st.s
TOL = 0.35  # mm: a point placed on a plane between grid lines lands within a pixel


def curves():
    from sciforge import sketch3d

    sk = s.get("sk3d")
    return sketch3d.curves_of(sk) if sk is not None else None


def points():
    from sciforge import sketch3d

    obj = curves()
    return sketch3d.resolved_points(obj, s["sk3d"]) if obj is not None else []


def vnear(p, q, tol=1e-6):
    return all(abs(p[i] - q[i]) <= tol for i in range(3))


def layer():
    from sciforge import sketch3d_ui

    return sketch3d_ui.layer(st.session(), create=False)


def click_global(point):
    """Hover, then click the global point (the sketch lies on XY: sketch = global)."""
    for f in (3.0, 1.5, 0.5, 0.0):
        h.move(h.screen_point(point + V(1.0, 0.6, 0) * f))
    QtTest.QTest.qWait(60)
    pos = h.screen_point(point)
    QtTest.QTest.mouseClick(h.gl_widget(), QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, pos)
    QtWidgets.QApplication.processEvents()


def click_manipulator(plane):
    """Click the middle of one of the manipulator's planes."""
    t = st.tool()
    corners = t.manipulator.corners.get(plane) if t is not None else None
    if not corners:
        h.check("the manipulator shows its %s plane" % plane, False)
        return
    mid = V(*[sum(c[i] for c in corners) / 4.0 for i in range(3)])
    click_global(s["sk3d"].getGlobalPlacement().multVec(mid))


# -- setup -------------------------------------------------------------------------------------
def setup_view():
    from sciforge import grid_ui

    s["sk3d"] = s["sk"]
    grid_ui.put("Subdivisions", 10)
    grid_ui.apply_subdivisions()
    h.view().viewIsometric()
    cam = h.view().getCameraNode()
    try:
        cam.height.setValue(90.0)
    except Exception:
        pass
    h.view().getCameraNode().position.setValue(*(V(5, 0, 10) + V(1, -1, 1) * 100))
    QtWidgets.QApplication.processEvents()


def palette_3d():
    h.check("3D Sketch starts off", not st.session() or not layer() or not layer().on)
    si.palette_click("SciForgePalette_sketch3d")


def palette_3d_on():
    h.check("A the palette's 3D Sketch box turned 3D Sketch on", layer() is not None and layer().on)
    h.press("l")


# -- A ----------------------------------------------------------------------------------------
def a_origin():
    h.check("A L runs the 3D Line", st.tool_title() == "3D Line", st.tool_title())
    click_global(V(0, 0, 0))


def a_plane_zx():
    t = st.tool()
    h.check(
        "A the chain starts at the origin",
        t is not None and len(t.chain) == 1 and vnear(t.chain[0][0], (0, 0, 0)),
        t and t.chain,
    )
    h.shot("A-manipulator")
    click_manipulator("ZX")


def a_up():
    h.check("A the ZX plane is the drawing plane", layer().plane == "ZX", layer().plane)
    click_global(V(0, 0, 20))


a_up.wait_ms = 900


def a_plane_xy():
    obj = curves()
    h.check(
        "A a 3D line was made", obj is not None and len(obj.Lines) == 2, obj and list(obj.Lines)
    )
    pts = points()
    h.check(
        "A from the origin straight up to 20",
        len(pts) == 2 and vnear(pts[0], (0, 0, 0)) and vnear(pts[1], (0, 0, 20), TOL),
        pts,
    )
    s["top"] = pts[1] if len(pts) > 1 else (0, 0, 20)
    click_manipulator("XY")


def a_along():
    h.check("A the XY plane is the drawing plane again", layer().plane == "XY", layer().plane)
    click_global(V(15, 0, s["top"][2]))


a_along.wait_ms = 900


def a_check():
    obj = curves()
    pts = points()
    h.check(
        "A two lines joined at the top point",
        obj is not None and len(obj.Lines) == 4 and list(obj.Lines)[1] == list(obj.Lines)[2],
        obj and list(obj.Lines),
    )
    h.check(
        "A the second line runs 15 along X at that height",
        len(pts) == 3 and vnear(pts[2], (15, 0, s["top"][2]), TOL),
        pts,
    )
    h.check(
        "A the shape: two edges",
        obj is not None and len(obj.Shape.Edges) == 2,
        obj and len(obj.Shape.Edges),
    )
    from sciforge import sketch_companions

    h.check(
        "A the 3D curves belong to the sketch",
        obj is not None and sketch_companions.owner(obj) is s["sk3d"],
    )
    s["end"] = pts[2] if len(pts) > 2 else (15, 0, 20)
    h.shot("A-3d-lines")
    st.esc()


# -- B ----------------------------------------------------------------------------------------
def b_pick():
    h.check("B the tool ended", st.tool() is None, st.tool_title())
    click_global(V(*s["end"]))


def b_type():
    h.check(
        "B the triad shows on the point",
        layer().triad is not None and layer().triad.index == 2,
        layer().triad and layer().triad.index,
    )
    s["undo"] = len(App.ActiveDocument.UndoNames)
    st.keys("5\n")


b_type.wait_ms = 900


def b_check():
    pts = points()
    want = (s["end"][0], s["end"][1], s["end"][2] + 5)
    h.check("B 5 typed: the point went 5 up", len(pts) == 3 and vnear(pts[2], want), pts)
    names = App.ActiveDocument.UndoNames
    h.check("B one undo step 'Move 3D Point'", names and names[0] == "Move 3D Point", names[:3])
    st.undo()


def b_undone():
    pts = points()
    h.check("B Ctrl+Z puts it back", len(pts) == 3 and vnear(pts[2], s["end"]), pts)
    st.redo()


def b_redone():
    pts = points()
    want = (s["end"][0], s["end"][1], s["end"][2] + 5)
    h.check("B Ctrl+Y moves it again", len(pts) == 3 and vnear(pts[2], want), pts)
    s["end"] = pts[2] if len(pts) > 2 else want


# -- C ----------------------------------------------------------------------------------------
def c_drag():
    from sciforge import sketch3d_ui

    tri = layer().triad
    if tri is None:
        h.check("C the triad is still there", False)
        return
    v = sketch3d_ui.View3D(st.session())
    a, b = tri.arrows(v)["Y"]
    mid = v.screen(tuple((a[i] + b[i]) / 2 for i in range(3)))
    start = QtCore.QPoint(int(mid[0]), int(mid[1]))
    tip = v.screen(b)
    end = QtCore.QPoint(int(tip[0] + (tip[0] - mid[0])), int(tip[1] + (tip[1] - mid[1])))
    h.drag(start, end, steps=12)


c_drag.wait_ms = 900


def c_check():
    pts = points()
    p = pts[2] if len(pts) > 2 else (0, 0, 0)
    h.check(
        "C the Y arrow moved the point along Y",
        abs(p[1] - s["end"][1]) > 1.0
        and abs(p[0] - s["end"][0]) < 1e-6
        and abs(p[2] - s["end"][2]) < 1e-6,
        (p, s["end"]),
    )
    st.undo()


def c_undone():
    pts = points()
    h.check("C Ctrl+Z puts it back", len(pts) == 3 and vnear(pts[2], s["end"]), pts)
    st.esc()


# -- D ----------------------------------------------------------------------------------------
def d_spline():
    si.menu_item("CREATE", "Fit Point Spline")


def d_first():
    h.check(
        "D Fit Point Spline runs the 3D Spline", st.tool_title() == "3D Spline", st.tool_title()
    )
    click_global(V(-20, 0, 0))


def d_second():
    click_global(V(-30, 10, 0))


def d_plane():
    click_manipulator("ZX")


def d_third():
    h.check("D the ZX plane is the drawing plane", layer().plane == "ZX", layer().plane)
    click_global(V(-40, 10, 10))


d_third.wait_ms = 900


def d_enter():
    st.enter()


d_enter.wait_ms = 900


def d_check():
    obj = curves()
    h.check(
        "D a spline was made", obj is not None and len(obj.Splines) == 1, obj and list(obj.Splines)
    )
    if obj is None or not obj.Splines:
        return
    edge = obj.Shape.Edges[-1]
    ends = [edge.valueAt(edge.FirstParameter), edge.valueAt(edge.LastParameter)]
    h.check(
        "D it starts at (-20, 0, 0) and ends at (-40, 10, 10)",
        vnear(ends[0], (-20, 0, 0), TOL) and vnear(ends[1], (-40, 10, 10), TOL),
        ends,
    )
    mid = V(-30, 10, 0)
    h.check(
        "D it passes through (-30, 10, 0)",
        edge.distToShape(__import__("Part").Vertex(mid))[0] < TOL,
    )
    h.check("D the spline tool ended", st.tool() is None, st.tool_title())


# -- I ----------------------------------------------------------------------------------------
def i_line():
    s["count"] = len(s["sk3d"].Geometry)
    s["n3d"] = len(curves().Lines) if curves() is not None else 0
    h.press("l")


def i_plane():
    h.check("I L runs the 3D Line", st.tool_title() == "3D Line", st.tool_title())
    click_manipulator("XY")


def i_a():
    h.check("I the XY plane is the drawing plane", layer().plane == "XY", layer().plane)
    click_global(V(10, -20, 0))


def i_b():
    click_global(V(30, -20, 0))


i_b.wait_ms = 700


def i_c():
    click_global(V(10, -30, 0))


i_c.wait_ms = 700


def i_close():
    click_global(V(10, -20, 0))


i_close.wait_ms = 900


def i_check():
    import Part

    sk = s["sk3d"]
    new = list(sk.Geometry)[s["count"] :]
    h.check(
        "I three sketch lines on the sketch plane",
        len(new) == 3 and all(g.TypeId == "Part::GeomLineSegment" for g in new),
        [g.TypeId for g in new],
    )
    h.check("I ...and no 3D line", len(curves().Lines) == s["n3d"], list(curves().Lines))
    want = [(V(10, -20, 0), V(30, -20, 0)), (V(30, -20, 0), V(10, -30, 0))]
    want.append((V(10, -30, 0), V(10, -20, 0)))
    h.check(
        "I ...where they were clicked",
        len(new) == 3
        and all(
            (g.StartPoint - a).Length < TOL and (g.EndPoint - b).Length < TOL
            for g, (a, b) in zip(new, want)
        ),
        [(g.StartPoint, g.EndPoint) for g in new],
    )
    first = s["count"]
    joined = 0
    for c in sk.Constraints:
        if c.Type == "Coincident" and min(c.First, c.Second) >= first:
            joined += 1
    h.check("I ...joined end to end (three Coincident)", joined == 3, joined)
    closed = False
    try:
        closed = Part.Wire(Part.__sortEdges__([g.toShape() for g in new])).isClosed()
    except Exception:
        pass
    h.check("I ...a closed triangle", closed)
    t = st.tool()
    h.check("I closed: the next click starts a new chain", t is not None and not t.chain)
    click_global(V(10, -20, 0))


def i_corner():
    t = st.tool()
    tie = t.chain[0][1] if t is not None and t.chain else ""
    h.check("I the new chain starts on the triangle's corner (tied)", tie.startswith("v:"), tie)
    click_manipulator("ZX")


def i_up():
    h.check("I the ZX plane is the drawing plane", layer().plane == "ZX", layer().plane)
    click_global(V(10, -20, 15))


i_up.wait_ms = 900


def i_up_check():
    from sciforge import sketch3d

    obj = curves()
    lines = list(obj.Lines) if obj is not None else []
    h.check("I a 3D line was made", len(lines) == s["n3d"] + 2, lines)
    if len(lines) < s["n3d"] + 2:
        st.esc()
        return
    a, b = lines[-2], lines[-1]
    pts = points()
    ties = list(obj.PointTies)
    h.check(
        "I from the triangle's corner 15 up",
        vnear(pts[a], (10, -20, 0), TOL) and vnear(pts[b], (10, -20, 15), TOL),
        (pts[a], pts[b]),
    )
    h.check(
        "I ...tied to the corner",
        a < len(ties) and sketch3d.resolve(s["sk3d"], ties[a]) is not None,
        ties,
    )
    st.esc()


# -- E ----------------------------------------------------------------------------------------
def e_finish():
    h.ribbon("Finish Sketch")


def e_browser():
    from sciforge import browser_ui, timeline_ops

    h.check("E left the sketch", h.in_sketch() is None)
    obj = curves()
    tree = browser_ui.widget()
    tree.refresh(force=True)
    item = tree.row(obj.Label) if obj is not None else None
    parent = item.parent() if item is not None else None
    sketch_label = s["sk3d"].Label
    h.check("E the browser lists the 3D Curves", item is not None, tree.labels())
    h.check(
        "E ...under their sketch",
        parent is not None
        and sketch_label
        in (parent.text(1), parent.data(1, browser_ui.ROLE_NODE).get("object_label")),
        parent and parent.text(1),
    )
    names = timeline_ops.timeline(App.ActiveDocument).names()
    h.check("E no timeline step of their own (they are the sketch's)", obj.Name not in names, names)
    s["sk3d"].ViewObject.Visibility = False


def e_hidden():
    h.check("E the sketch hidden: its 3D curves hide too", not curves().ViewObject.Visibility)
    s["sk3d"].ViewObject.Visibility = True


def e_shown():
    h.check("E shown again with the sketch", curves().ViewObject.Visibility)
    wires = s["sk3d"].Shape.Wires
    h.check(
        "E the triangle drawn with 3D Sketch on is a closed profile of the sketch",
        any(w.isClosed() and len(w.Edges) == 3 for w in wires),
        [(w.isClosed(), len(w.Edges)) for w in wires],
    )


# -- F ----------------------------------------------------------------------------------------
def f_profile():
    from sciforge import commands, sketch_ui

    body = commands.ensure_body()
    App.ActiveDocument.openTransaction("profile")
    sk = sketch_ui.create_sketch(body, (sketch_ui.origin_planes(body)["XY_Plane"], ""))
    h.draw_circle(sk, 0, 0, 2)
    App.ActiveDocument.commitTransaction()
    App.ActiveDocument.recompute()
    s["profile"] = sk
    h.fit()
    h.click_empty()


def f_sweep():
    sw.menu("Sweep")


f_sweep.wait_ms = 1200


def f_path():
    p = sw.panel("sweep")
    h.check(
        "F the Sweep took the circle and waits for the path",
        p is not None and len(p.profiles) == 1 and p.active == "path",
        p and p.active,
    )
    h.check("F clicked the 3D line", h.click_edge(V(0, 0, 10)))


f_path.wait_ms = 1200


def f_ok():
    p = sw.panel("sweep")
    h.check(
        "F the path is the 3D line",
        p is not None and len(p.path) == 1 and p.path[0][0] is curves(),
        p and p.path,
    )
    h.task_button("OK")


f_ok.wait_ms = 1500


def f_check():
    want = math.pi * 4.0 * s["top"][2]
    v = h.solid_volume()
    h.check("F a tube of radius 2 up the 3D line", abs(v - want) < 1e-3 * want, (v, want))
    s["volume"] = v


# -- G ----------------------------------------------------------------------------------------
def g_save():
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-sketch3d-"), "sketch3d.FCStd")
    s["path"] = path
    s["names"] = (s["sk3d"].Name, curves().Name)
    App.ActiveDocument.saveAs(path)
    App.closeDocument(App.ActiveDocument.Name)


def g_reopen():
    App.openDocument(s["path"])
    h.fit()


def g_check():
    from sciforge import sketch_companions

    doc = App.ActiveDocument
    sk, cv = doc.getObject(s["names"][0]), doc.getObject(s["names"][1])
    h.check(
        "G reopened: the 3D curves are there",
        cv is not None and len(cv.Shape.Edges) == 4,
        cv and len(cv.Shape.Edges),
    )
    h.check("G ...still the sketch's", cv is not None and sketch_companions.owner(cv) is sk)
    v = h.solid_volume()
    h.check("G reopened: the tube", abs(v - s["volume"]) < 1e-6 * s["volume"], (v, s["volume"]))
    s["sk3d"] = sk


# -- H ----------------------------------------------------------------------------------------
def h_open():
    from sciforge import sketch_ui

    sketch_ui.edit_sketch(s["sk3d"])


h_open.wait_ms = 1500


def h_on():
    h.check("H a sketch with 3D curves opens with 3D Sketch on", layer() is not None and layer().on)
    si.palette_click("SciForgePalette_sketch3d")


def h_line():
    h.check("H 3D Sketch off", not layer().on)
    s["sk"] = s["sk3d"]
    s["count"] = len(s["sk3d"].Geometry)
    h.press("l")


def h_a():
    h.check("H L is the sketch's own Line again", st.tool() is None)
    si.click(V(30, -10, 0))


def h_b():
    si.click(V(50, -10, 0))


def h_check():
    st.esc()
    h.check(
        "H a line on the sketch plane",
        len(s["sk3d"].Geometry) == s["count"] + 1,
        len(s["sk3d"].Geometry) - s["count"],
    )
    h.ribbon("Finish Sketch")


h.run(
    "sketch2_3d",
    si.watched(
        st.start_steps("Sketch2_3D")
        + [
            setup_view,
            palette_3d,
            palette_3d_on,
            a_origin,
            a_plane_zx,
            a_up,
            a_plane_xy,
            a_along,
            a_check,
            b_pick,
            b_type,
            b_check,
            b_undone,
            b_redone,
            c_drag,
            c_check,
            c_undone,
            d_spline,
            d_first,
            d_second,
            d_plane,
            d_third,
            d_enter,
            d_check,
            i_line,
            i_plane,
            i_a,
            i_b,
            i_c,
            i_close,
            i_check,
            i_corner,
            i_up,
            i_up_check,
            e_finish,
            e_browser,
            e_hidden,
            e_shown,
            f_profile,
            f_sweep,
            f_path,
            f_ok,
            f_check,
            g_save,
            g_reopen,
            g_check,
            h_open,
            h_on,
            h_line,
            h_a,
            h_b,
            h_check,
        ]
    ),
)
