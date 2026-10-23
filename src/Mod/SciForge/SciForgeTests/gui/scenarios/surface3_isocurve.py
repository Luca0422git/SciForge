# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sketch > Project / Include > Isoparametric Curve (Fusion, March 2026; surface part 3), only
real input.

A cylinder r 10, 30 high (built for the scenario). Create Sketch, click the XZ plane's square.
Path I1 (a U curve through the click): CREATE > Project / Include > Isoparametric Curve; the
        panel waits for a face; click the cylinder's front: one U curve (a straight line 30
        long up the side) through the clicked place, drawn purple; its Distance from the
        face's first edge is shown.
Path I2 (refusal): type 100 mm (the face is 62.8 round): the panel says the distance must be
        from 0 to the face's width and OK is greyed.
Path I3 (V, Distributed): Direction V, Type Distributed: three circles round the cylinder at
        7.5, 15 and 22.5; Enter: kept in the sketch ("Isoparametric Curves", 3 curves of
        62.83).
Path I4 (they follow the face): Finish Sketch; the cylinder's radius 12: the circles are
        75.40 long.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtWidgets

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import sketch_tools_steps as st

V = App.Vector
s = {}


def doc():
    return App.ActiveDocument


def setup():
    import Part
    import Sketcher

    from sciforge import commands, extrude, sketch_ui

    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Surface3IsoCurve")
    body = commands.ensure_body()
    xy = (sketch_ui.origin_planes(body)["XY_Plane"], "")
    circ = sketch_ui.create_sketch(body, xy)
    c = circ.addGeometry(Part.Circle(V(0, 0, 0), V(0, 0, 1), 10))
    s["radius"] = circ.addConstraint(Sketcher.Constraint("Radius", c, 10.0))
    circ.addConstraint(Sketcher.Constraint("DistanceX", -1, 1, c, 3, 0.0))
    circ.addConstraint(Sketcher.Constraint("DistanceY", -1, 1, c, 3, 0.0))
    doc().recompute()
    extrude.make(body, circ, {"distance": 30.0})
    commands.leave_edit()
    s["circle"] = circ
    doc().recompute()
    h.fit()


def create_sketch():
    h.ribbon("Create Sketch")


def pick_plane():
    pl.click_square("XZ_Plane")


def start_tool():
    sk = h.in_sketch()
    h.check("a sketch on XZ open", sk is not None)
    s["sk"] = sk
    si.menu_item("CREATE", "Isoparametric Curve")


def _box(name):
    for w in Gui.getMainWindow().findChildren(QtWidgets.QWidget, name):
        if w.isVisible():
            return w
    return None


def click_face():
    h.check("Isoparametric Curve runs", st.tool_title() == "Isoparametric Curve", st.tool_title())
    h.check("its panel is shown", _box("SciForgeIsoCurve") is not None)
    si.click(V(0, -10, 12), V(0.0, -1.0, 0))  # the cylinder's front


def one_u_curve():
    t = st.tool()
    h.check("the cylinder's face is picked", t is not None and t.face is not None, t and t.face)
    if t is None or t.face is None:
        return
    edges = t.curves()
    h.check("one U curve", len(edges) == 1, len(edges))
    h.check("a straight line 30 up the side", edges and abs(edges[0].Length - 30.0) < 1e-6)
    h.check("the curve runs through the clicked place", t.distance > 0.0, t.distance)
    h.shot("1-iso-u")
    box = _box("SciForgeIsoDistance")
    h.check("the Distance box", box is not None)
    if box is not None:
        ui.type_into(box, "100")


def refused():
    t = st.tool()
    hint = _box("SciForgeIsoHint")
    text = hint.text() if hint is not None else ""
    h.check("the panel says why", "distance must be from 0" in text, text)
    ok = _box("SciForgeIsoOK")
    h.check("OK is greyed", ok is not None and not ok.isEnabled())
    h.check("the tool still runs", t is not None and t.active)
    box = _box("SciForgeIsoDirection")
    h.check("chose V", box is not None and ui.choose(box, "V"))


def v_chosen():
    box = _box("SciForgeIsoType")
    h.check("chose Distributed", box is not None and ui.choose(box, "Distributed"))


def three_circles():
    t = st.tool()
    if t is None:
        h.check("the tool runs", False)
        return
    edges = t.curves()
    h.check("three V curves", len(edges) == 3, len(edges))
    lengths = [round(e.Length, 3) for e in edges]
    h.check(
        "circles round the cylinder (62.83)",
        all(abs(x - 20 * math.pi) < 1e-3 for x in lengths),
        lengths,
    )
    heights = sorted(round(e.BoundBox.ZMin, 3) for e in edges)
    h.check("at 7.5, 15 and 22.5", heights == [7.5, 15.0, 22.5], heights)
    h.check("OK is enabled", _box("SciForgeIsoOK").isEnabled())
    h.gl_widget().setFocus()
    st.enter()


three_circles.wait_ms = 900


def kept():
    from sciforge import sketch_companions, surface_iso

    found = [o for o in sketch_companions.companions(s["sk"]) if surface_iso.is_iso(o)]
    h.check("Isoparametric Curves kept in the sketch", len(found) == 1, found)
    if found:
        obj = found[0]
        s["iso"] = obj.Name
        h.check("3 curves", len(obj.Shape.Edges) == 3, len(obj.Shape.Edges))
        h.check("V, Distributed", (obj.Direction, obj.Mode) == ("V", "Distributed"))
    h.check("the tool closed", st.tool_title() != "Isoparametric Curve", st.tool_title())
    h.shot("2-iso-v-distributed")


def finish():
    h.ribbon("Finish Sketch")


def follow():
    h.check("left the sketch", h.in_sketch() is None)
    s["circle"].setDatum(s["radius"], App.Units.Quantity("12 mm"))
    doc().recompute()


def followed():
    obj = doc().getObject(s.get("iso", ""))
    lengths = [round(e.Length, 3) for e in obj.Shape.Edges] if obj is not None else []
    h.check(
        "the circles follow the cylinder (75.40)",
        lengths and all(abs(x - 24 * math.pi) < 1e-3 for x in lengths),
        lengths,
    )


h.run(
    "surface3_isocurve",
    [
        setup,
        create_sketch,
        pick_plane,
        start_tool,
        click_face,
        one_u_curve,
        refused,
        v_chosen,
        three_circles,
        kept,
        finish,
        follow,
        followed,
    ],
)
