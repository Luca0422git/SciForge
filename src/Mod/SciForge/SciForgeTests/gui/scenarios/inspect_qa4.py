# SPDX-License-Identifier: LGPL-2.1-or-later
"""INSPECT and CONSTRUCT mixed into everyday modelling (QA), only real input. Each path is
what Fusion does, checked on the design:

  S  Measure inside a sketch (Fusion's SKETCH tab has INSPECT > Measure): I while sketching
     keeps the sketch open; a sketch line measures 20, two parallel lines are 10 apart at
     0 degrees, a third pick (the circle) starts again (radius 3); Esc ends Measure only
     (still sketching, the curves untouched); I again, then Finish Sketch also ends Measure.
  T  Center of Mass of every visible body (20, 15, 5), then Measure from its marker: the
     marker's centre is a point (X 20, Y 15, Z 5), 5 from the top face.
  W  A second body (New Body, 20 x 30 x 10 at x = 50 .. 70): the Center of Mass follows
     (both Steel: x = 33.333); body 2 made Aluminium in Physical Material: the centre of
     the mass moves to the heavier box (x = 25.838 with 7900 and 2700 kg/m^3); Undo / Redo
     of the material move it back and forth.
  Z  Press Pull of body 1's right face 15 into body 2, then Interference of the two bodies
     (Compute): 5 x 30 x 10 = 1500 shared; the Center of Mass followed the pull too.
  V  Esc while the Offset Plane arrow is held down: the command ends, nothing is made, no
     undo step; letting go of the mouse afterwards changes nothing and the next click on the
     part selects its face (the arrow is not stuck to the mouse).
  X  Offset Plane of the front face typed as a sum "2.5 * 2" + one Enter: finished at once
     (y = -5). Point at Vertex then clicks the corner (0, 0, 0) through that plane, which
     stands in front of it (Fusion picks through what the box cannot take).
  U  Section Analysis on body 1's front face, -15 typed, then Q with the dialog open: the
     section is kept and Press Pull opens; body 1's top face (still shown) pulled 5; the
     section keeps cutting; Undo takes back the pull only.

Part: box 40 x 30 x 10 from the origin (real input). Hand-derived values are in the steps.
"""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as bs
from SciForgeTests.gui import dialog_input as di
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import inspect_steps as s
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import timeline_input as ti

V = App.Vector
st = {}
STEEL = 7900.0  # kg/m^3, FreeCAD's Steel-Generic (a body on FreeCAD's Default counts as Steel)
ALU = 2700.0  # kg/m^3, Aluminum-Generic


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


def number(text):
    try:
        return float(str(text).split()[0])
    except Exception:
        return None


def bodies():
    return doc().findObjects("PartDesign::Body")


def com_x(volumes_densities_centres):
    """Hand formula: the x of the centre of mass of boxes (volume, density, centre x)."""
    mass = sum(v * d for v, d, _x in volumes_densities_centres)
    return sum(v * d * x for v, d, x in volumes_densities_centres) / mass


def com_position():
    from sciforge import analysis

    found = analysis.of_kind(doc(), analysis.COM_KIND)
    return V(found[0].Position) if found else None


# -- S: Measure inside a sketch ---------------------------------------------------------------
def s_sketch():
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def s_top():
    h.click(V(30, 25, 10))


def s_draw():
    sk = h.in_sketch()
    h.check("a sketch on the box top", sk is not None)
    if sk is None:
        return
    st["sketch"] = sk.Name
    x0, y0 = h.to_sketch(sk, V(5, 5, 10))
    x1, y1 = h.to_sketch(sk, V(25, 15, 10))
    h.draw_rectangle(sk, x0, y0, x1, y1)
    cx, cy = h.to_sketch(sk, V(32, 22, 10))
    h.draw_circle(sk, cx, cy, 3)
    st["curves"] = sk.GeometryCount
    h.fit()
    h.press("i")


def s_open():
    sk = obj("sketch")
    p = measure_panel()
    h.check("I opened Measure", p is not None)
    h.check("still sketching", h.in_sketch() is sk, h.in_sketch())
    if p is None:
        return
    h.check("Measure works in the sketch", p.sketch is sk, p.sketch)
    h.check("shown in the sketch's panel", p.frame is not None and p.frame.isVisible())
    h.check("it asks for a pick", "Click" in p.message.text(), p.message.text())
    s.no_popups("I in a sketch")
    h.shot("S-measure-in-sketch")
    si.click(V(15, 5, 10))


def s_line():
    h.check("the line measures 20", value("Selection 1", "Length") == "20.000 mm", measure_values())
    si.click(V(15, 15, 10))


def measure_values():
    p = measure_panel()
    return p.values() if p else None


def s_two_lines():
    d = number(value("Results", "Distance"))
    a = number(value("Results", "Angle"))
    h.check("the two lines are 10 apart", d is not None and s.close(d, 10.0), measure_values())
    h.check("parallel: 0 degrees", a is not None and s.close(a, 0.0), measure_values())
    p = measure_panel()
    h.check(
        "a line is drawn between them", p is not None and p.relation is not None, measure_values()
    )
    h.shot("S-two-lines")
    si.click(V(32, 25, 10))


def s_third():
    got = measure_values() or {}
    h.check("a third pick starts again", "Selection 2" not in got and "Results" not in got, got)
    h.check("the circle: radius 3", value("Selection 1", "Radius") == "3.000 mm", got)
    h.check("diameter 6", value("Selection 1", "Diameter") == "6.000 mm", got)
    st["s_panel"] = measure_panel()
    s.press_escape()


def s_escaped():
    sk = obj("sketch")
    p = st.get("s_panel")
    h.check("Esc ended Measure", p is not None and p._closed)
    h.check("the sketch is still open", h.in_sketch() is sk, h.in_sketch())
    h.check("its curves untouched", sk is not None and sk.GeometryCount == st["curves"])
    h.check(
        "Measure's panel is gone",
        not any(
            w.isVisible()
            for w in Gui.getMainWindow().findChildren(QtWidgets.QFrame, "SciForgeMeasureInSketch")
        ),
    )
    h.check("the sketch palette is still there", si.palette() is not None)
    s.no_popups("Esc in Measure in a sketch")
    h.press("i")


def s_again():
    p = measure_panel()
    h.check("I again: Measure in the sketch", p is not None and p.sketch is obj("sketch"))
    si.click(V(25, 10, 10))


def s_right_line():
    h.check("the right line measures 10", value("Selection 1", "Length") == "10.000 mm")
    st["s_panel"] = measure_panel()
    h.ribbon("Finish Sketch")


def s_finished():
    p = st.get("s_panel")
    h.check("Finish Sketch ended Measure too", p is not None and p._closed)
    h.check("the sketch is finished", h.in_sketch() is None, h.in_sketch())
    h.check("no dialog left open", not Gui.Control.activeDialog())
    sk = obj("sketch")
    h.check("the sketch kept its curves", sk is not None and sk.GeometryCount == st["curves"])
    s.eye(sk.Label if sk is not None else "Sketch")  # hide it: the rest clicks the part


# -- T: Measure from the Center of Mass marker --------------------------------------------------
def t_com():
    h.click_empty()
    s.menu("INSPECT", "Center of Mass")


def t_com_ok():
    p = b.active_panel()
    got = [p.coords[a].text() for a in "XYZ"] if p is not None else None
    h.check("the box's centre", got == ["20.000 mm", "15.000 mm", "5.000 mm"], got)
    h.task_button("OK")


def t_measure():
    h.click_empty()
    h.fit()
    h.press("i")


def t_click_marker():
    p = measure_panel()
    h.check("Measure open", p is not None and p.sketch is None)
    h.check(
        "the Center of Mass can be clicked", p is not None and p.com_dots is not None, p.com_dots
    )
    h.click(V(20, 15, 5))


def t_marker():
    got = measure_values()
    h.check(
        "the marker measures as a point (20, 15, 5)",
        [value("Selection 1", k) for k in "XYZ"] == ["20.000 mm", "15.000 mm", "5.000 mm"],
        got,
    )
    p = measure_panel()
    label = p.tree.topLevelItem(0).text(1) if p is not None and p.tree.topLevelItemCount() else ""
    h.check("named after the analysis", label == "Center of Mass1", label)
    h.check("nothing else picked with it", "Selection 2" not in (got or {}), got)
    h.click(V(35, 25, 10))


def t_to_top():
    d = number(value("Results", "Distance"))
    h.check(
        "5 from the centre to the top face", d is not None and s.close(d, 5.0), measure_values()
    )
    dz = number(value("Results", "Delta Z"))
    h.check("all of it in Z", dz is not None and s.close(abs(dz), 5.0), measure_values())
    h.shot("T-measure-com")
    h.task_button("Close")


# -- W: a second body, materials -------------------------------------------------------------
def w_follow():
    found = bodies()
    h.check("two bodies", len(found) == 2, [o.Label for o in found])
    if len(found) == 2:
        st["b1"], st["b2"] = found[0].Name, found[1].Name
    p = com_position()
    x = com_x([(12000, STEEL, 20), (6000, STEEL, 60)])
    h.check(
        "the Center of Mass followed the new body (both Steel): x = 33.333",
        p is not None and s.close(p.x, x, 1e-6) and s.close(p.y, 15.0) and s.close(p.z, 5.0),
        (p, x),
    )
    h.click_empty()
    s.menu("MODIFY", "Physical Material")


def w_aluminium():
    p = bs.panel()
    if h.check("Physical Material open", p is not None and hasattr(p, "library"), p):
        from SciForgeTests.gui import widget_input as w

        item = p.item_for("Aluminium")
        p.library.scrollToItem(item)
        w.click(p.library.viewport(), p.library.visualItemRect(item).center())


def w_click_body2():
    h.click(V(60, 15, 10))


def w_material_ok():
    h.task_button("OK")


def w_weighted():
    b2 = obj("b2")
    h.check(
        "body 2 is Aluminium",
        b2 is not None and b2.ShapeMaterial.Name == "Aluminum-Generic",
        b2 and b2.ShapeMaterial.Name,
    )
    p = com_position()
    x = com_x([(12000, STEEL, 20), (6000, ALU, 60)])
    st["w_x"] = x
    h.check(
        "the centre of mass moved to the heavier steel box: x = %.3f" % x,
        p is not None and s.close(p.x, x, 1e-6),
        (p, x),
    )
    h.shot("W-materials")
    s.undo()


def w_undone():
    p = com_position()
    x = com_x([(12000, STEEL, 20), (6000, STEEL, 60)])
    b2 = obj("b2")
    h.check("Undo: body 2 is not Aluminium", b2.ShapeMaterial.Name != "Aluminum-Generic")
    h.check("and the centre is back: x = 33.333", p is not None and s.close(p.x, x, 1e-6), p)
    s.redo()


def w_redone():
    p = com_position()
    h.check("Redo: x = %.3f again" % st["w_x"], p is not None and s.close(p.x, st["w_x"], 1e-6), p)


# -- Z: Press Pull into the other body, then Interference ------------------------------------
def z_pull():
    h.click_empty()
    h.fit()
    h.press("q")


def z_face():
    h.click(V(40, 15, 5))


def z_15():
    from sciforge import presspull_ui

    p = presspull_ui.PressPullPanel.last
    h.check("Press Pull took body 1's right face", p is not None and not p._closed and p.names)
    if p is not None:
        s.type_into(p.field.widget, "15")


def z_ok():
    h.task_button("OK")


def z_pulled():
    b1 = obj("b1")
    v = b1.Shape.Volume if b1 is not None else 0.0
    h.check("body 1 is 55 long now: 16500", s.close(v, 16500.0), v)
    h.check("body 2 untouched: 6000", s.close(obj("b2").Shape.Volume, 6000.0))
    p = com_position()
    x = com_x([(16500, STEEL, 27.5), (6000, ALU, 60)])
    h.check(
        "the Center of Mass followed the pull: x = %.3f" % x,
        p is not None and s.close(p.x, x, 1e-6),
        p,
    )
    h.click_empty()
    s.menu("INSPECT", "Interference")


def z_b1():
    h.click(V(5, 5, 10))


def z_b2():
    h.click(V(65, 25, 10))


def z_compute():
    p = b.active_panel()
    h.check("two bodies picked", p is not None and len(p.picked) == 2, p and p.picked)
    if p is not None:
        di.click(p.compute)


def z_result():
    p = b.active_panel()
    rows = p.rows() if p is not None else []
    h.check("one interference", len(rows) == 1, rows)
    h.check("1500 shared", bool(rows) and rows[0][3] == "1500.000 mm^3", rows)
    h.check(
        "the overlap is shown",
        p is not None and p.target is not None and s.close(p.target.Overlap.Volume, 1500.0),
    )
    h.shot("Z-interference")
    h.task_button("OK")


def z_kept():
    from sciforge import analysis

    found = analysis.of_kind(doc(), analysis.INTERFERENCE_KIND)
    h.check("Interference1 kept", [o.Label for o in found] == ["Interference1"], found)
    st["planes_before"] = len(s.datums("PartDesign::Plane"))
    st["undo_before"] = list(doc().UndoNames)


# -- V: Esc while the arrow is held ------------------------------------------------------------
def v_start():
    h.click_empty()
    h.fit()
    h.ribbon("Offset Plane")


def v_pick():
    h.click(V(45, 25, 10))


def v_hold():
    """Press on the arrow and move: the button stays down (the next step presses Esc)."""
    p = s.construct_panel()
    handle = p.handle if p is not None else None
    h.check("Offset Plane with its arrow", handle is not None)
    if handle is None:
        return
    grab = handle.base_point() + handle.direction * (handle.size * 0.55)
    up = grab + handle.direction * 12.0
    widget = h.gl_widget()
    start, end = s.screen(grab), s.screen(up)
    st["v_end"] = end
    h.move(start)
    QtTest.QTest.mousePress(widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, start)
    for i in range(1, 11):
        pos = QtCore.QPointF(
            start.x() + (end.x() - start.x()) * i / 10.0,
            start.y() + (end.y() - start.y()) * i / 10.0,
        )
        event = QtGui.QMouseEvent(
            QtCore.QEvent.MouseMove,
            pos,
            QtCore.QPointF(widget.mapToGlobal(pos.toPoint())),
            QtCore.Qt.NoButton,
            QtCore.Qt.LeftButton,
            QtCore.Qt.NoModifier,
        )
        QtWidgets.QApplication.sendEvent(widget, event)
        QtWidgets.QApplication.processEvents()


def v_esc():
    p = s.construct_panel()
    h.check("the arrow is being dragged", p is not None and p.handle and p.handle.dragging())
    h.check(
        "the distance follows the drag",
        p is not None and abs(p.values["distance"] - 10.0) > 1.0,
        p and p.values,
    )
    st["v_panel"] = p
    h.press(QtCore.Qt.Key_Escape)


def v_release():
    QtTest.QTest.mouseRelease(
        h.gl_widget(), QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, st.get("v_end")
    )
    QtWidgets.QApplication.processEvents()


def v_after():
    p = st.get("v_panel")
    h.check(
        "Esc ended Offset Plane", p is not None and p._closed and not Gui.Control.activeDialog()
    )
    h.check(
        "no plane made",
        len(s.datums("PartDesign::Plane")) == st["planes_before"],
        [o.Label for o in s.datums()],
    )
    h.check("no undo step", list(doc().UndoNames) == st["undo_before"], doc().UndoNames)
    h.move(s.screen(V(30, 5, 10)))
    h.click(V(45, 25, 10))


def v_click_selects():
    sel = s.selection()
    h.check(
        "the next click selects the face (the arrow is not stuck to the mouse)",
        len(sel) == 1 and len(sel[0][1]) == 1 and sel[0][1][0].startswith("Face"),
        sel,
    )
    h.click_empty()


# -- X: a sum and one Enter; picking through a construction plane -----------------------------
def x_offset():
    h.click_empty()
    h.fit()
    h.ribbon("Offset Plane")


def x_front():
    h.click(V(20, 0, 5))


def x_sum_enter():
    p = s.construct_panel()
    h.check("Offset Plane on the front face", p is not None and p.datum is not None)
    st["x_panel"] = p
    if p is not None:
        s.type_enter(p.distance.widget, "2.5 * 2")


def x_done():
    p = st.get("x_panel")
    h.check("one Enter after the sum finished it", p is not None and p._closed)
    h.check("no dialog left", not Gui.Control.activeDialog())
    planes = s.datums("PartDesign::Plane")
    h.check("a new plane", len(planes) == st["planes_before"] + 1, [o.Label for o in planes])
    if planes:
        plane = planes[-1]
        st["x_plane"] = plane.Name
        y = plane.getGlobalPlacement().Base.y
        h.check("5 in front of the face: y = -5", s.close(y, -5.0), y)
    h.click_empty()
    h.fit()
    hit = h.under_mouse(V(0, 0, 0))
    h.check(
        "the plane stands in front of the corner",
        bool(hit) and hit[0] == st.get("x_plane"),
        hit,
    )
    s.menu("CONSTRUCT", "Point at Vertex")


def x_corner():
    h.fit()
    found = s.click_vertex(V(0, 0, 0))
    h.check("the corner can be aimed at through the plane", found)


def x_point():
    p = s.construct_panel()
    d = p.datum if p is not None else None
    h.check("Point at Vertex took the corner", d is not None, p and s.box_value(p, 0))
    if d is not None:
        h.check("at (0, 0, 0)", s.near(d.getGlobalPlacement().Base, V(0, 0, 0)), d.Placement)
    h.task_button("OK")


def x_made():
    from sciforge import pickpanel

    points = s.datums("PartDesign::Point")
    h.check("Point kept", len(points) == 1, [o.Label for o in points])
    plane = obj("x_plane")
    styles = []
    if plane is not None:
        styles = [
            n.style.getValue() for n in pickpanel.nodes(plane.ViewObject.RootNode, "SoPickStyle")
        ]
    h.check("the plane can be clicked again", styles and all(v == 0 for v in styles), styles)
    for o in [plane] + points:
        if o is not None:
            s.eye(o.Label)  # out of the way of the clicks below, as a person would


# -- U: Section Analysis, then Q with its dialog open ------------------------------------------
def u_start():
    h.click_empty()
    h.fit()
    h.ribbon("Section Analysis")


def u_front():
    h.click(V(20, 0, 5))


def u_15():
    from sciforge import section_ui

    p = b.active_panel()
    ok = isinstance(p, section_ui.SectionPanel) and p.analysis is not None
    h.check("a section on body 1's front face", ok)
    if ok:
        s.type_into(p.distance.widget, "-15")


def u_press_q():
    st["u_volume"] = obj("b1").Shape.Volume
    h.press("q")


def u_kept():
    from sciforge import presspull_ui, section, section_ui

    found = section.sections(doc())
    h.check("Q kept the section (Fusion finishes the open command)", len(found) == 1, found)
    if found:
        st["u_section"] = found[0].Name
        h.check("at y = 15", s.close(found[0].CutPlacement.Base.y, 15.0), found[0].CutPlacement)
    p = presspull_ui.PressPullPanel.last
    h.check("Press Pull is open", p is not None and not p._closed)
    h.check("body 1 is cut", len(section_ui.clips_on(obj("b1"))) == 1)
    h.click(V(45, 25, 10))


def u_pull_5():
    from sciforge import presspull_ui

    p = presspull_ui.PressPullPanel.last
    h.check("the top face shown behind the cut is picked", p is not None and p.names, p and p.names)
    if p is not None:
        s.type_into(p.field.widget, "5")


def u_ok():
    h.task_button("OK")


def u_pulled():
    from sciforge import section_ui

    v = obj("b1").Shape.Volume
    h.check("body 1 pulled up 5: +8250", s.close(v, st["u_volume"] + 55 * 30 * 5), v)
    h.check("the section still cuts body 1", len(section_ui.clips_on(obj("b1"))) == 1)
    h.shot("U-section-pull")
    s.undo()


def u_undone():
    from sciforge import section, section_ui

    v = obj("b1").Shape.Volume
    h.check("Undo took back the pull", s.close(v, st["u_volume"]), v)
    h.check("the section stays", len(section.sections(doc())) == 1)
    h.check("and cuts", len(section_ui.clips_on(obj("b1"))) == 1)


def the_end():
    s.no_popups("the end")
    h.shot("end")


STEPS = (
    b.box_steps("InspectQA4")
    + [s_sketch, s_top, s_draw, s_open, s_line, s_two_lines, s_third, s_escaped, s_again]
    + [s_right_line, s_finished]
    + [t_com, t_com_ok, t_measure, t_click_marker, t_marker, t_to_top]
    + bs.box_steps("b2", (50, 0, 70, 30), 10, V(6, -6, 0), new_body=True)
    + [w_follow, w_aluminium, w_click_body2, w_material_ok, w_weighted, w_undone, w_redone]
    + [z_pull, z_face, z_15, z_ok, z_pulled, z_b1, z_b2, z_compute, z_result, z_kept]
    + [v_start, v_pick, v_hold, v_esc, v_release, v_after, v_click_selects]
    + [x_offset, x_front, x_sum_enter, x_done, x_corner, x_point, x_made]
    + [u_start, u_front, u_15, u_press_q, u_kept, u_pull_5, u_ok, u_pulled, u_undone, the_end]
)

h.run("inspect_qa4", ti.watched(STEPS))
