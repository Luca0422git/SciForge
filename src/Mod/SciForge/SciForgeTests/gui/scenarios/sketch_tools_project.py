# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Project to Surface (CREATE > Project / Include > Project to Surface), with
real clicks: a block 40 x 30 x 10 (x 0..40, y 10..40) and a sketch on its bottom plane
holding a construction line and a circle (centre (15, 25), radius 5).

Click the block's top face (seen through the sketch), Next, click the circle, OK: a
"Projected Curves" object holds one closed curve: the circle lifted onto the top face
(every point at z = 10, 5 from (15, 25, 10)); the sketch's construction line before the
circle does not shift which curve is projected. One Ctrl+Z removes it.
Again with Projection Type Along Vector (keyboard in the type box), Enter for Next and
Enter for OK: the same circle on the top face. Esc after picking a face: nothing made,
the panel goes.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import sketch_tools_steps as st

V = App.Vector
s = st.s
CENTRE = V(15, 25, 0)
ON_CIRCLE = V(15 + 5 * math.cos(math.pi / 4), 25 + 5 * math.sin(math.pi / 4), 0)
FACE = V(25, 35, 0)


def setup():
    import Part

    from sciforge import commands, extrude, sketch_ui

    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("SketchToolsProject")
    body = commands.ensure_body()
    xy = (sketch_ui.origin_planes(body)["XY_Plane"], "")
    base = sketch_ui.create_sketch(body, xy)
    h.draw_rectangle(base, 0, 10, 40, 40)
    extrude.make(body, base, {"distance": 10.0})
    sk = sketch_ui.create_sketch(body, xy)
    sk.addGeometry(Part.LineSegment(V(-30, -20, 0), V(-10, -20, 0)), True)
    s["circle"] = sk.addGeometry(Part.Circle(CENTRE, V(0, 0, 1), 5))
    App.ActiveDocument.recompute()
    s["sk"] = sk
    h.fit()


def open_sketch():
    from sciforge import sketch_ui

    sketch_ui.edit_sketch(s["sk"])


open_sketch.wait_ms = 1500


def projected():
    return [o for o in App.ActiveDocument.Objects if o.Name.startswith("ProjectedCurves")]


def panel():
    for w in Gui.getMainWindow().findChildren(QtWidgets.QFrame, "SciForgeProjectToSurface"):
        if w.isVisible():
            return w
    return None


def button(name):
    p = panel()
    return p.findChild(QtWidgets.QPushButton, name) if p is not None else None


def press_button(name):
    b = button(name)
    if b is None:
        h.check("the panel's %s button" % name, False)
        return
    QtTest.QTest.mouseClick(b, QtCore.Qt.LeftButton)
    QtWidgets.QApplication.processEvents()


def tool_lists():
    t = st.tool()
    if t is None:
        return [], []
    return t.faces, t.curves


def circle_on_top(obj, where):
    edges = obj.Shape.Edges
    h.check("%s: one projected curve" % where, len(edges) == 1, len(edges))
    if not edges:
        return
    e = edges[0]
    span = e.LastParameter - e.FirstParameter
    pts = [e.valueAt(e.FirstParameter + span * i / 16.0) for i in range(17)]
    h.check(
        "%s: it lies on the top face (z = 10)" % where,
        all(abs(p.z - 10.0) < 1e-6 for p in pts),
        [round(p.z, 6) for p in pts],
    )
    radii = [math.hypot(p.x - 15.0, p.y - 25.0) for p in pts]
    h.check(
        "%s: it is the circle (5 from its centre)" % where,
        all(abs(r - 5.0) < 1e-3 for r in radii),
        radii,
    )
    h.check("%s: closed" % where, e.isClosed())
    h.check("%s: valid" % where, "Invalid" not in obj.State, obj.State)


# == Closest Point ===========================================================================
def pt_open():
    h.check("sketch open", h.in_sketch() is s["sk"])
    s["before"] = len(projected())
    si.menu_item("CREATE", "Project to Surface")


def pt_face():
    h.check("Project to Surface runs", st.tool_title() == "Project to Surface", st.tool_title())
    h.check("its panel shows", panel() is not None)
    st.click(FACE)


def pt_face_check():
    faces, _curves = tool_lists()
    h.check("the clicked face is picked", len(faces) == 1, faces)
    if faces:
        obj, sub = faces[0]
        face = obj.Shape.getElement(sub)
        h.check("...the block's top face", abs(face.CenterOfMass.z - 10.0) < 1e-6, sub)
    labels = [w.text() for w in panel().findChildren(QtWidgets.QLabel)] if panel() else []
    h.check("the panel counts it", "1 selected" in labels, labels)
    press_button("SciForgeProjectNext")


def pt_curve():
    h.check("Next: now the curves", st.tool() is not None and st.tool().step == 1)
    st.click(ON_CIRCLE)


def pt_curve_check():
    _faces, curves = tool_lists()
    h.check(
        "the circle is picked (the sketch's own numbering: Edge%d)" % (s["circle"] + 1),
        curves == [(s["sk"], "Edge%d" % (s["circle"] + 1))],
        curves,
    )
    h.shot("1-project-picked")
    press_button("SciForgeProjectOK")


pt_curve_check.wait_ms = 800


def pt_check():
    found = projected()
    h.check("OK made Projected Curves", len(found) == s["before"] + 1, [o.Label for o in found])
    if found:
        obj = found[-1]
        circle_on_top(obj, "closest point")
        h.check(
            "it projects the circle, not the construction line before it",
            bool(obj.Curves) and tuple(obj.Curves[0][1]) == ("Edge1",),
            obj.Curves,
        )
    h.check("the tool ended", st.tool() is None, st.tool_title())
    h.check("its panel went", panel() is None)
    h.shot("2-projected")


def pt_undo():
    st.undo()


def pt_undo_check():
    h.check("one Ctrl+Z removes it", len(projected()) == s["before"], len(projected()))


# == Along Vector ============================================================================
def av_open():
    si.menu_item("CREATE", "Project to Surface")


def av_face():
    st.click(FACE)
    st.enter()  # Next


def av_curve():
    h.check("Enter: Next", st.tool() is not None and st.tool().step == 1)
    st.click(ON_CIRCLE)
    p = panel()
    box = p.findChild(QtWidgets.QComboBox, "SciForgeProjectType") if p is not None else None
    if box is None:
        h.check("the Projection Type box", False)
        return
    box.setFocus()
    QtTest.QTest.keyClick(box, QtCore.Qt.Key_Down)
    QtWidgets.QApplication.processEvents()
    h.check("Along Vector chosen", box.currentText() == "Along Vector", box.currentText())
    h.gl_widget().setFocus()


def av_ok():
    st.enter()  # OK


av_ok.wait_ms = 800


def av_check():
    found = projected()
    h.check("Enter made it", len(found) == s["before"] + 1, len(found))
    if found:
        obj = found[-1]
        h.check("its type: Along Vector", obj.Type == "Along Vector", obj.Type)
        circle_on_top(obj, "along vector")


# == Esc =====================================================================================
def esc_open():
    s["before"] = len(projected())
    si.menu_item("CREATE", "Project to Surface")


def esc_face():
    st.click(FACE)
    st.esc()


def esc_check():
    h.check("Esc: nothing made", len(projected()) == s["before"], len(projected()))
    h.check("the tool ended", st.tool() is None, st.tool_title())
    h.check("the panel went", panel() is None)


def finish():
    h.ribbon("Finish Sketch")


h.run(
    "sketch_tools_project",
    si.watched(
        [
            setup,
            open_sketch,
            pt_open,
            pt_face,
            pt_face_check,
            pt_curve,
            pt_curve_check,
            pt_check,
            pt_undo,
            pt_undo_check,
            av_open,
            av_face,
            av_curve,
            av_ok,
            av_check,
            esc_open,
            esc_face,
            esc_check,
            finish,
        ]
    ),
)
