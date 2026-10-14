# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Variable radius: a start radius, an end radius and radius points along the edge,
each with its position (0 = start of the edge, 1 = its end) and radius. Only real input: F,
a click on the edge, the Radius Type drop-down, typing the start and end radii, a click on
the picked edge (adds a radius point there, like Fusion's dot on the edge), typing its
position and radius, Add Point and its remove button, dragging a point's arrow, a value box,
OK, Ctrl+Z / Ctrl+Y, save, close, reopen and edit, a radius of 0 refused.

Measured on the finished part: a round of radius R on a 90 degree box edge passes
(sqrt(2) - 1) R from the old corner, so the radius at the start (x = 0), at the point
(x = 20) and at the end (x = 40) is read off the part."""

import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import arrow_input as ai
from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import fillet2_steps as f2
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}
FRONT_TOP = V(20, 0, 10)


def radii():
    return [round(f2.radius_at(V(x, 0, 10)), 3) for x in (0, 20, 40)]


def start():
    Gui.Selection.clearSelection()
    h.fit()
    h.press("f")


def pick():
    h.click_edge(FRONT_TOP)


def variable():
    p = b.blend_panel()
    h.check("edge picked", p is not None and len(p.refs) == 1, p and p.refs)
    if p:
        b.choose(p.radius_type, "Variable")


def variable_rows():
    p = b.blend_panel()
    if p is None:
        return
    h.check(
        "Variable shows Start Radius, End Radius and the points",
        p.start_field.widget.isVisible()
        and p.end_field.widget.isVisible()
        and p.add_point_button.isVisible()
        and not p.radius.widget.isVisible(),
    )
    h.check("an arrow at the start and one at the end", len(p.arrows) == 2, len(p.arrows))
    h.check("Variable makes it SciForge's step", f2.is_sets(p.target), p.target)
    b.type_into(p.start_field.widget, "1")


def end_radius():
    p = b.blend_panel()
    if p:
        b.type_into(p.end_field.widget, "1.5")


def click_on_edge():
    p = b.blend_panel()
    h.check("start 1, end 1.5", p and p.options["start"] == 1 and p.options["end"] == 1.5)
    h.click_edge(FRONT_TOP)


def point_added():
    p = b.blend_panel()
    if p is None:
        return
    points = p.options.get("points", [])
    h.check("a click on the edge adds a radius point there", len(points) == 1, points)
    h.check("the edge is still picked", len(p.refs) == 1, p.refs)
    if points:
        h.check("the point is near the middle", abs(points[0][0] - 0.5) < 0.05, points)
    h.check("its row is in the dialog", len(p.point_rows) == 1, len(p.point_rows))
    if p.point_rows:
        f2.type_point(p, 0, position=0.5, radius=3)


def three_points():
    p = b.blend_panel()
    points = p.options.get("points", []) if p else []
    h.check("point at 0.5 with radius 3", points == [[0.5, 3.0]], points)
    r = radii()
    h.check(
        "measured radius 1 at the start, 3 at the point, 1.5 at the end",
        abs(r[0] - 1) < 0.01 and abs(r[1] - 3) < 0.01 and abs(r[2] - 1.5) < 0.01,
        r,
    )
    h.check("three arrows: start, point, end", p is not None and len(p.arrows) == 3)
    h.check("a value box beside each", len(ai.value_boxes()) == 3, len(ai.value_boxes()))
    faces = [f for f in h.body().Shape.Faces if type(f.Surface).__name__ != "Plane"]
    h.check("one round face", len(faces) == 1, [type(f.Surface).__name__ for f in faces])
    h.shot("1-variable")
    if p:
        b.click_widget(p.add_point_button)


def added_more():
    p = b.blend_panel()
    points = p.options.get("points", []) if p else []
    h.check("Add Point adds a second point in the widest gap", len(points) == 2, points)
    if p and len(p.point_rows) == 2:
        b.click_widget(p.point_rows[1][2])


def removed():
    p = b.blend_panel()
    points = p.options.get("points", []) if p else []
    h.check("its remove button takes it away", points == [[0.5, 3.0]], points)
    index = [i for i, a in enumerate(p.arrows) if a[1]["what"] == "pt0"] if p else []
    if h.check("the point has an arrow", bool(index)):
        s["r"] = p.options["points"][0][1]
        a, c = b.arrow_screen(p, index[0], along=1.0)
        h.drag(a, c)


def dragged():
    p = b.blend_panel()
    r = p.options["points"][0][1] if p else 0
    h.check("dragging the point's arrow grows its radius", r > s["r"] + 0.3, (s["r"], r))
    index = [i for i, a in enumerate(p.arrows) if a[1]["what"] == "pt0"] if p else []
    box = ai.value_box("pt0#%d" % index[0]) if index else None
    if h.check("the point's value box", box is not None):
        ai.type_in_box(box, "3")  # Enter: OK


def after_ok():
    h.check("Enter in the value box finished the command", not Gui.Control.activeDialog())
    r = radii()
    h.check(
        "kept: 1 / 3 / 1.5",
        abs(r[0] - 1) < 0.01 and abs(r[1] - 3) < 0.01 and abs(r[2] - 1.5) < 0.01,
        r,
    )
    steps = f2.steps()
    h.check("one step", len(steps) == 1)
    s["v"] = h.solid_volume()
    h.check("no kernel errors", not f2.report_errors(), f2.report_errors())
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def undone():
    h.check("Ctrl+Z", b.close(h.solid_volume(), b.BOX) and not f2.steps(), h.solid_volume())
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def redone():
    h.check("Ctrl+Y", b.close(h.solid_volume(), s["v"]))
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-fillet2-"), "variable.FCStd")
    s["path"] = path
    App.ActiveDocument.saveAs(path)
    App.closeDocument(App.ActiveDocument.Name)


def reopen():
    App.openDocument(s["path"])
    h.fit()


def reopened():
    h.check("reopened: same part", b.close(h.solid_volume(), s["v"]))
    r = radii()
    h.check("reopened: 1 / 3 / 1.5", abs(r[1] - 3) < 0.01, r)
    b.timeline_double_click("Fillet 1", click_first=True)


def edit_open():
    p = b.blend_panel()
    h.check("edit opens the dialog", p is not None and not p.created)
    if p is None:
        return
    h.check(
        "Variable with its point shown",
        p.radius_type.currentText() == "Variable"
        and p.options.get("points") == [[0.5, 3.0]]
        and len(p.point_rows) == 1
        and abs(p.end_field.value() - 1.5) < 1e-9,
        (p.radius_type.currentText(), p.options),
    )
    b.type_into(p.end_field.widget, "0")


def refused():
    p = b.blend_panel()
    text = p.message.text() if p else ""
    h.check("an end radius of 0 is refused, with the reason", "end radius" in text, text)
    h.check("the part keeps the last good result", b.close(h.solid_volume(), s["v"]))
    h.press(QtCore.Qt.Key_Escape)


def end():
    h.check("Esc: unchanged", b.close(h.solid_volume(), s["v"]))
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("no kernel errors", not f2.report_errors(), f2.report_errors())
    h.shot("2-end")


h.run(
    "fillet2_variable",
    b.box_steps("Variable")
    + [
        start,
        pick,
        variable,
        variable_rows,
        end_radius,
        click_on_edge,
        point_added,
        three_points,
        added_more,
        removed,
        dragged,
        after_ok,
        undone,
        redone,
        reopen,
        reopened,
        edit_open,
        refused,
        end,
    ],
)
