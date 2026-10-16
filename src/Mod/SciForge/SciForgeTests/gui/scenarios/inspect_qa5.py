# SPDX-License-Identifier: LGPL-2.1-or-later
"""CONSTRUCT and INSPECT with other commands around them (QA), only real input. Each path is
what Fusion does, checked on the design:

  P  The sweep set-up: a path line sketched in front of the part, Plane Along Path on it
     (0.25 typed: the plane stands at x = 10, across the line), Create Sketch on that plane
     (clicked where it stands in front of the origin squares), a circle on it; the plane
     edited from the timeline to 0.75: the plane, its sketch and the circle move to x = 30.
  M  The path sketch opened again from the timeline, its line clicked, then I: Measure
     starts with that line (40 long) and the sketch stays open; Esc ends Measure only;
     Finish Sketch.
  E  Interference with both bodies clicked (not computed yet), then E: the Interference is
     kept, computed (10 x 10 x 5 = 500), and Extrude opens; Esc leaves the part as it was.
  Q  Center of Mass of body 2 (40, 30, 2.5), then Q: it is kept and Press Pull opens; Esc.

Part (real input): box 40 x 30 x 10 from the origin; body 2 (New Body) 20 x 20 x 5 at
x = 30 .. 50, y = 20 .. 40, z = 0 .. 5.
"""
import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as bs
from SciForgeTests.gui import dialog_input as di
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import inspect_steps as s
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import timeline_input as ti

V = App.Vector
st = {}


def doc():
    return App.ActiveDocument


def obj(key):
    return doc().getObject(st[key]) if st.get(key) else None


def measure_panel():
    from sciforge import measure_ui

    p = measure_ui.MeasurePanel.last
    return p if p is not None and not p._closed else None


def value(section, name):
    p = measure_panel()
    return (p.values().get(section) or {}).get(name) if p else None


def volumes():
    return [round(o.Shape.Volume, 6) for o in doc().findObjects("PartDesign::Body")]


def kinds(kind):
    from sciforge import analysis

    return analysis.of_kind(doc(), kind)


# -- P: Plane Along Path on a sketch line, a sketch on it -------------------------------------
def p_sketch():
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def p_xy():
    pl.click_square("XY_Plane")  # where the square shows (was 12, -8, 0)


def p_line():
    import Part

    sk = h.in_sketch()
    h.check("a sketch on XY", sk is not None)
    if sk is None:
        return
    st["path_sketch"] = sk.Name
    a = V(*h.to_sketch(sk, V(0, -20, 0)), 0)
    c = V(*h.to_sketch(sk, V(40, -20, 0)), 0)
    sk.addGeometry(Part.LineSegment(a, c))
    doc().recompute()


def p_finish():
    h.ribbon("Finish Sketch")


def p_plane():
    h.click_empty()
    s.menu("CONSTRUCT", "Plane Along Path")


def p_click_line():
    h.fit()
    h.click_edge(V(10, -20, 0))


def p_half():
    p = s.construct_panel()
    d = p.datum if p is not None else None
    h.check("the path picked: a plane halfway", d is not None, p and s.box_value(p, 0))
    if d is None:
        return
    gp = d.getGlobalPlacement()
    h.check("at x = 20", s.near(gp.Base, V(20, -20, 0), 1e-6), gp)
    n = s.normal_of(d)
    h.check("across the line", abs(abs(n.x) - 1.0) < 1e-9, n)
    di.type_into(p.fraction, "0.25")


def p_quarter():
    p = s.construct_panel()
    d = p.datum if p is not None else None
    x = d.getGlobalPlacement().Base.x if d is not None else None
    h.check("0.25 typed: x = 10", x is not None and s.close(x, 10.0), x)
    h.task_button("OK")


def p_kept():
    planes = s.datums("PartDesign::Plane")
    h.check("the plane kept", len(planes) == 1, [o.Label for o in planes])
    if planes:
        st["plane"] = planes[0].Name
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def p_click_plane():
    """The plane stands in front of the part and of the XY / XZ origin squares there."""
    h.click(V(10, -20, 4))


def p_on_plane():
    sk = h.in_sketch()
    h.check("a sketch opened", sk is not None)
    if sk is None:
        return
    st["profile"] = sk.Name
    support = [o.Name for o, _subs in (sk.AttachmentSupport or [])]
    h.check("on the construction plane", st.get("plane") in support, support)
    gp = sk.getGlobalPlacement()
    h.check("at x = 10", s.close(gp.Base.x, 10.0), gp)
    cx, cy = h.to_sketch(sk, V(10, -20, 0))
    h.draw_circle(sk, cx, cy, 2)


def p_finish2():
    h.ribbon("Finish Sketch")


def p_edit():
    plane = obj("plane")
    if h.check("the plane is there", plane is not None):
        s.double_click_timeline(plane)


def p_edit_dialog():
    p = s.construct_panel()
    h.check("Plane Along Path opens for editing", p is not None and p.editing)
    if p is None:
        return
    h.check("0.25 shown", abs(p.fraction.value() - 0.25) < 1e-9, p.fraction.value())
    di.type_into(p.fraction, "0.75")


def p_edit_ok():
    h.task_button("OK")


def p_moved():
    plane, sk = obj("plane"), obj("profile")
    x = plane.getGlobalPlacement().Base.x if plane is not None else None
    h.check("the plane moved to x = 30", x is not None and s.close(x, 30.0), x)
    sx = sk.getGlobalPlacement().Base.x if sk is not None else None
    h.check("its sketch moved with it", sx is not None and s.close(sx, 30.0), sx)
    circles = [e for e in sk.Shape.Edges if hasattr(e.Curve, "Radius")] if sk else []
    centre = V(circles[0].Curve.Center) if circles else None
    h.check(
        "and the circle: centre (30, -20, 0)",
        centre is not None and s.near(centre, V(30, -20, 0), 1e-6),
        centre,
    )
    h.shot("P-plane-along-path")
    s.double_click_timeline(obj("path_sketch"))


# -- M: Measure in a sketch with a line picked first ----------------------------------------------
def m_in_sketch():
    sk = h.in_sketch()
    h.check("the path sketch is open", sk is not None and sk.Name == st.get("path_sketch"), sk)
    h.fit()
    si.click(V(20, -20, 0))


def m_press_i():
    sel = s.selection()
    h.check("the line is selected", bool(sel), sel)
    h.press("i")


def m_started_with_it():
    p = measure_panel()
    h.check("Measure in the sketch", p is not None and p.sketch is not None)
    h.check("the picked line measured: 40", value("Selection 1", "Length") == "40.000 mm")
    h.check("the sketch is still open", h.in_sketch() is obj("path_sketch"))
    st["m_panel"] = p
    s.press_escape()


def m_escaped():
    p = st.get("m_panel")
    h.check("Esc ended Measure", p is not None and p._closed)
    h.check("still sketching", h.in_sketch() is obj("path_sketch"))
    h.ribbon("Finish Sketch")


def m_finished():
    h.check("sketch finished", h.in_sketch() is None)
    for key in ("path_sketch", "profile", "plane"):
        o = obj(key)
        if o is not None and o.ViewObject.Visibility:
            s.eye(o.Label)  # out of the way of the clicks below


# -- E: Interference, then E with its dialog open --------------------------------------------------
def e_start():
    st["volumes"] = volumes()
    h.click_empty()
    h.fit()
    s.menu("INSPECT", "Interference")


def e_b1():
    h.click(V(5, 5, 10))


def e_b2():
    h.click(V(45, 35, 5))


def e_press_e():
    p = b.active_panel()
    h.check("two bodies picked", p is not None and len(getattr(p, "picked", [])) == 2)
    h.press("e")


def e_kept():
    found = kinds("InterferenceAnalysis")
    h.check("E kept the Interference", len(found) == 1, found)
    if found:
        from sciforge import analysis

        rows = analysis.results(found[0])
        h.check("computed: 500", len(rows) == 1 and s.close(rows[0][2], 500.0), rows)
    from sciforge import extrude_ui

    p = b.active_panel()
    h.check("Extrude is open", isinstance(p, extrude_ui.ExtrudePanel), p)
    s.press_escape()


def e_escaped():
    h.check("no dialog left", not Gui.Control.activeDialog())
    h.check("the part as it was", volumes() == st["volumes"], (volumes(), st["volumes"]))
    s.no_popups("E in Interference")


# -- Q: Center of Mass, then Q with its dialog open ------------------------------------------------
def q_start():
    h.click_empty()
    s.menu("INSPECT", "Center of Mass")


def q_body2():
    h.click(V(45, 35, 5))


def q_press_q():
    p = b.active_panel()
    got = [p.coords[a].text() for a in "XYZ"] if p is not None else None
    h.check("body 2's centre", got == ["40.000 mm", "30.000 mm", "2.500 mm"], got)
    h.press("q")


def q_kept():
    from sciforge import analysis, presspull_ui

    found = kinds(analysis.COM_KIND)
    h.check("Q kept the Center of Mass", len(found) == 1, found)
    if found:
        h.check("of body 2", s.near(found[0].Position, V(40, 30, 2.5), 1e-6), found[0].Position)
    p = presspull_ui.PressPullPanel.last
    h.check("Press Pull is open", p is not None and not p._closed)
    s.press_escape()


def q_escaped():
    h.check("no dialog left", not Gui.Control.activeDialog())
    h.check("the part as it was", volumes() == st["volumes"], (volumes(), st["volumes"]))
    s.no_popups("the end")
    h.shot("end")


STEPS = (
    b.box_steps("InspectQA5")
    + bs.box_steps("b2", (30, 20, 50, 40), 5, V(6, -6, 0), new_body=True)
    + [p_sketch, p_xy, p_line, p_finish, p_plane, p_click_line, p_half, p_quarter, p_kept]
    + [p_click_plane, p_on_plane, p_finish2, p_edit, p_edit_dialog, p_edit_ok, p_moved]
    + [m_in_sketch, m_press_i, m_started_with_it, m_escaped, m_finished]
    + [e_start, e_b1, e_b2, e_press_e, e_kept, e_escaped]
    + [q_start, q_body2, q_press_q, q_kept, q_escaped]
)

h.run("inspect_qa5", ti.watched(STEPS))
