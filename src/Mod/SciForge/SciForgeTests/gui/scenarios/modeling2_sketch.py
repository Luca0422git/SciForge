# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's sketch Chamfer with its three types, the sketch fillet radius and typed line
angles (wave 4, modeling-2), with real clicks and keys.

A 40 x 20 rectangle from (10, 10) to (50, 30) (fully dimensioned: 40, 20, its corner (50, 10)
50 and 10 from the origin). MODIFY > Chamfer:
1. Distance and angle (chosen in the type box): click the corner (50, 10), type 5, Tab, 30,
   Enter: the chamfer runs from (45, 10) to (50, 10 + 5 tan 30); a 5 mm dimension from the old
   corner (kept as a construction point) and a 30 degree angle between the bottom line and
   the chamfer; the sketch stays fully constrained.
2. Equal distance: click the corner (50, 30); 30 is refused (longer than the side, the reason
   beside the pointer); type 4, Enter: (50, 26) to (46, 30); two 4 mm
   dimensions, the second follows the first (fx): changing the first to 6 moves both.
3. Two distances: click the top line, then the left line, type 3, Tab, 6, Enter: 3 along
   the top line, 6 down the left one. Ctrl+Z takes it away, Ctrl+Y brings it back.
MODIFY > Fillet: click the two lines at the corner (10, 10), the radius box opens, type 4.
LINE: click (70, 0), type 30, Tab, 45, Enter: a 30 mm line at 45 degrees; then 20, Tab,
135: the angle is measured from the sketch's X axis, as Fusion does (Autodesk forum: the
typed angle follows the sketch's horizontal, not the previous line); both become
dimensions (length and angle to the X axis).
Finish Sketch, Extrude 10. Save, close, reopen: the chamfer's fx dimension still follows.

Hand-derived area: 800 - 5 * 5 tan 30 / 2 - 6 * 6 / 2 - 3 * 6 / 2 - (4^2 - pi 4^2 / 4)
(after the equal chamfer became 6), times 10.
"""

import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import arrow_input as arrows
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import sketch_tools_steps as st

V = App.Vector
s = st.s
T30 = math.tan(math.radians(30))
AREA = 800 - 5 * 5 * T30 / 2 - 6 * 6 / 2 - 3 * 6 / 2 - (16 - math.pi * 4)


def sk():
    return st.sketch()


def chooser():
    from PySide import QtWidgets
    from sciforge import sketch_chamfer_tool

    found = h.gl_widget().findChildren(QtWidgets.QWidget, sketch_chamfer_tool.CHOOSER_NAME)
    shown = [w for w in found if w.isVisible()]
    return shown[0] if shown else None


def choose_type(label):
    from PySide import QtWidgets

    box = chooser()
    combo = box.findChild(QtWidgets.QComboBox) if box is not None else None
    h.check("the Chamfer Type box is shown", combo is not None)
    if combo is not None:
        h.check("type %s" % label, ui.choose(combo, label))


def chamfer_line(a, b, tol=1e-6):
    for i, g in enumerate(sk().Geometry):
        if g.TypeId != "Part::GeomLineSegment":
            continue
        ends = (g.StartPoint, g.EndPoint)
        if any((e - a).Length < tol for e in ends) and any((e - b).Length < tol for e in ends):
            return i
    return None


# -- the rectangle ---------------------------------------------------------------------------
def no_sketch():
    """An empty design: Chamfer (from the command search) says it needs a sketch."""
    from sciforge import commands

    Gui.runCommand("SciForge_SketchChamfer")
    told = commands._TOLD["msg"] or ""
    h.check("no sketch: Chamfer says why", "inside a sketch" in told, told)


def rectangle():
    import Sketcher

    h.draw_rectangle(sk(), 10, 10, 50, 30)
    sk().addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, 40))
    sk().addConstraint(Sketcher.Constraint("DistanceY", 1, 1, 1, 2, 20))
    # placed by its corner (50, 10): the chamfer there keeps these on the old corner point
    sk().addConstraint(Sketcher.Constraint("DistanceX", -1, 1, 1, 1, 50))
    sk().addConstraint(Sketcher.Constraint("DistanceY", -1, 1, 1, 1, 10))
    App.ActiveDocument.recompute()
    h.check("the rectangle is fully constrained", sk().solve() == 0)
    h.fit()


def open_chamfer():
    si.menu_item("MODIFY", "Chamfer")


# -- 1. Distance and angle ------------------------------------------------------------------
def da_type():
    h.check("SciForge's Chamfer runs", st.tool_title() == "Chamfer", st.tool_title())
    choose_type("Distance and angle")


def da_corner():
    s["count"] = len(sk().Geometry)
    st.click(V(50, 10, 0))
    t = st.tool()
    h.check(
        "the corner picks both lines", t is not None and sorted(t.picks) == [0, 1], t and t.picks
    )


def da_hover():
    st.hover(V(46, 13, 0))
    h.check("the chamfer follows the pointer", bool(st.preview().get("curves")), st.preview())
    texts = st.box_texts()
    h.check("a distance and an angle box", len(texts) == 2 and "A " in texts[1], texts)
    h.shot("1-distance-angle")


def da_keys():
    st.keys("5\t30\n")


def da_check():
    line = chamfer_line(V(45, 10, 0), V(50, 10 + 5 * T30, 0))
    h.check("the chamfer (45, 10) - (50, 10 + 5 tan 30)", line is not None, sk().Geometry)
    dims = [(c.Type, round(c.Value, 6)) for c in sk().Constraints if c.Driving]
    h.check("a 5 mm dimension", ("Distance", 5.0) in dims, dims)
    angles = [c for c in sk().Constraints if c.Type == "Angle" and c.Second == line]
    angles += [c for c in sk().Constraints if c.Type == "Angle" and c.First == line]
    h.check(
        "a 30 degree angle to the bottom line",
        len(angles) == 1 and st.near(math.degrees(angles[0].Value), 30.0),
        [(c.First, c.Second, c.Value) for c in angles],
    )
    points = [g for g in sk().Geometry if g.TypeId == "Part::GeomPoint"]
    h.check(
        "the old corner stays as a point",
        any(st.vnear(V(p.X, p.Y, 0), V(50, 10, 0)) for p in points),
    )
    h.check("still fully constrained", sk().solve() == 0 and not sk().RedundantConstraints)
    st.sketch_ok("distance and angle")
    h.check("the tool waits for the next corner", st.tool_title() == "Chamfer")


# -- 2. Equal distance ----------------------------------------------------------------------
def eq_type():
    choose_type("Equal distance")


def eq_corner():
    st.click(V(50, 30, 0))
    st.hover(V(47, 27, 0))


def eq_too_long():
    st.keys("30\n")  # longer than the right side (17 mm left of it): refused


def eq_refused():
    t = st.tool()
    hint = t.hint_text() if t is not None else ""
    h.check(
        "a chamfer longer than the line is refused with the reason",
        "longer than" in hint and t.step == 2,
        (hint, t and t.step),
    )
    h.check("nothing changed", chamfer_line(V(50, 0, 0), V(20, 30, 0)) is None)


def eq_keys():
    st.keys("4\n")


def eq_check():
    line = chamfer_line(V(50, 26, 0), V(46, 30, 0))
    h.check("the chamfer (50, 26) - (46, 30)", line is not None, sk().Geometry)
    engine = dict(sk().ExpressionEngine)
    named = [c.Name for c in sk().Constraints if c.Name.startswith("Chamfer")]
    h.check("two named 4 mm dimensions", len(named) == 2, named)
    follows = [k for k, v in engine.items() if "Chamfer" in k and "Chamfer" in v]
    h.check("the second follows the first (fx)", len(follows) == 1, engine)
    st.sketch_ok("equal distance")
    if named:
        sk().setDatum(sorted(named)[0], App.Units.Quantity("6 mm"))
        App.ActiveDocument.recompute()
        h.check(
            "6 typed on the first: both sides 6",
            chamfer_line(V(50, 24, 0), V(44, 30, 0)) is not None,
            [(g.StartPoint, g.EndPoint) for g in sk().Geometry if hasattr(g, "StartPoint")],
        )


# -- 3. Two distances ---------------------------------------------------------------------
def two_type():
    choose_type("Two distances")


def two_lines():
    s["before_two"] = len(sk().Geometry)
    st.click(V(25, 30, 0))  # the top line (first: its distance is the first value)
    st.click(V(10, 18, 0))  # the left line
    t = st.tool()
    h.check("two lines picked", t is not None and t.step == 2, t and (t.step, t.picks))
    st.hover(V(12, 27, 0))


def two_keys():
    st.keys("3\t6\n")


def two_check():
    line = chamfer_line(V(13, 30, 0), V(10, 24, 0))
    h.check("the chamfer (13, 30) - (10, 24)", line is not None, sk().Geometry)
    dims = sorted(round(c.Value, 6) for c in sk().Constraints if c.Type == "Distance" and c.Driving)
    h.check("3 and 6 mm dimensions", 3.0 in dims and 6.0 in dims, dims)
    st.sketch_ok("two distances")
    s["after_two"] = len(sk().Geometry)
    st.esc()
    st.undo()


def two_undone():
    h.check(
        "Ctrl+Z: the two-distance chamfer goes",
        len(sk().Geometry) == s["before_two"],
        len(sk().Geometry),
    )
    st.redo()


def two_redone():
    h.check("Ctrl+Y: it is back", chamfer_line(V(13, 30, 0), V(10, 24, 0)) is not None)


# -- the sketch fillet ------------------------------------------------------------------------
def fillet():
    si.menu_item("MODIFY", "Fillet")


def fillet_corner():
    si.click(V(16, 10, 0), approach=V(0.0, -1.0, 0))  # the bottom line near the corner
    si.click(V(10, 16, 0), approach=V(-1.0, 0.0, 0))  # then the left line


def fillet_box():
    h.shot("fillet-click")
    sess = st.session()
    h.check("the radius box opens", sess is not None and sess.editor is not None)
    si.type_text("4")


def fillet_check():
    arcs = [g for g in sk().Geometry if g.TypeId == "Part::GeomArcOfCircle"]
    h.check("radius 4", len(arcs) == 1 and st.near(arcs[0].Radius, 4.0), arcs)
    radius = [c for c in sk().Constraints if c.Type == "Radius" and c.Driving]
    h.check("a radius dimension 4", len(radius) == 1 and st.near(radius[0].Value, 4.0), radius)
    st.esc()
    st.esc()


# -- typed line angles -------------------------------------------------------------------------
def line_tool():
    h.press("l")


def line_start():
    s["lines_before"] = len(si.lines(sk()))
    si.click(V(70, 0, 0))


def line_first():
    si.move_towards(V(76, 5, 0), V(1, 1, 0) * 0.7)
    si.type_text("30", enter=False)
    si.tab()
    si.type_text("45")


def line_second():
    si.move_towards(V(85, 30, 0), V(-1, 1, 0) * 0.7)
    si.type_text("20", enter=False)
    si.tab()
    si.type_text("135")


def line_check():
    new = si.lines(sk())[s["lines_before"] :]
    h.check("two typed lines", len(new) == 2, sk().Geometry)
    if len(new) == 2:
        a, b = new[0][1], new[1][1]
        r = 30 / math.sqrt(2)
        # (FreeCAD writes the typed angle with 6 decimals of a radian: 1e-5 mm here)
        h.check("30 long at 45 degrees", st.vnear(a.EndPoint, V(70 + r, r, 0), 1e-4), a)
        d = b.EndPoint - b.StartPoint
        h.check(
            "the second at 135 degrees from the X axis (not from the first line)",
            st.near(math.degrees(math.atan2(d.y, d.x)), 135.0, 1e-4)
            and st.near(d.Length, 20.0, 1e-6),
            d,
        )
        for index, want in ((new[0][0], 45.0), (new[1][0], 135.0)):
            angles = [
                c
                for c in sk().Constraints
                if c.Type == "Angle" and c.First == -1 and c.Second == index  # from X
            ]
            h.check(
                "the typed angle %g is a dimension to the X axis" % want,
                len(angles) == 1 and st.near(math.degrees(angles[0].Value), want, 1e-4),
                [
                    (c.Type, c.First, c.Second, c.Value)
                    for c in sk().Constraints
                    if index in (c.First, c.Second)
                ],
            )
    st.esc()
    st.esc()


def finish():
    h.ribbon("Finish Sketch")


def extrude():
    h.check("the sketch closes", h.in_sketch() is None)
    h.fit()
    h.press("e")


def extrude_ok():
    arrows.type_distance("10")
    h.task_button("OK")


def volume():
    v = h.solid_volume()
    h.check("the plate with its cut corners", st.near(v, AREA * 10, 1e-6), (v, AREA * 10))
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-m2-sketch-"), "m2_sketch.FCStd")
    s["path"] = path
    App.ActiveDocument.saveAs(path)
    App.closeDocument(App.ActiveDocument.Name)


def reopen():
    App.openDocument(s["path"])
    h.fit()


def reopened():
    doc = App.ActiveDocument
    sketches = [o for o in doc.Objects if o.TypeId == "Sketcher::SketchObject"]
    h.check("reopened: same plate", st.near(h.solid_volume(), AREA * 10, 1e-6), h.solid_volume())
    sketch = sketches[0] if sketches else None
    named = (
        sorted(c.Name for c in sketch.Constraints if c.Name.startswith("Chamfer")) if sketch else []
    )
    if sketch is not None and named:
        sketch.setDatum(named[0], App.Units.Quantity("5 mm"))
        doc.recompute()
        area = AREA + 6 * 6 / 2 - 5 * 5 / 2
        h.check(
            "reopened: the equal chamfer's second side still follows",
            st.near(h.solid_volume(), area * 10, 1e-6),
            (h.solid_volume(), area * 10),
        )


h.run(
    "modeling2_sketch",
    si.watched(
        [st.new_design("M2Sketch"), no_sketch, st.create_sketch, st.pick_xy, st.sketch_open]
        + [
            rectangle,
            open_chamfer,
            da_type,
            da_corner,
            da_hover,
            da_keys,
            da_check,
            eq_type,
            eq_corner,
            eq_too_long,
            eq_refused,
            eq_keys,
            eq_check,
            two_type,
            two_lines,
            two_keys,
            two_check,
            two_undone,
            two_redone,
            fillet,
            fillet_corner,
            fillet_box,
            fillet_check,
            line_tool,
            line_start,
            line_first,
            line_second,
            line_check,
            finish,
            extrude,
            extrude_ok,
            volume,
            reopen,
            reopened,
        ]
    ),
)
