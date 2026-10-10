# SPDX-License-Identifier: LGPL-2.1-or-later
"""Chamfer the way a Fusion user does it, only real input: ribbon button with nothing
selected, click an edge, Equal Distance, Two Distances (with Flip and the second arrow),
Distance and Angle, OK, Ctrl+Z / Ctrl+Y, edit from the timeline, Esc cancels, and a
second chamfer started with edges selected beforehand. Geometry checked with
hand-derived formulas (a chamfer with legs a, b along an edge of length L removes
L * a * b / 2; two equal chamfers meeting at a box corner overlap by d^3 / 3)."""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}
FRONT_TOP = V(20, 0, 10)
TOP_FACE = V(20, 15, 10)
BACK_TOP = V(20, 30, 10)
BACK_RIGHT = V(40, 30, 5)


def legs(a, c):
    return b.BOX - 40 * a * c / 2.0


def cuts():
    """(cut into the top face, cut into the front face) of the front-top chamfer."""
    shape = h.body().Shape
    top = [
        f
        for f in shape.Faces
        if f.Surface.TypeId == "Part::GeomPlane"
        and abs(f.BoundBox.ZMin - 10) < 1e-6
        and abs(f.BoundBox.ZMax - 10) < 1e-6
    ]
    front = [
        f
        for f in shape.Faces
        if f.Surface.TypeId == "Part::GeomPlane"
        and abs(f.BoundBox.YMin) < 1e-6
        and abs(f.BoundBox.YMax) < 1e-6
    ]
    if len(top) != 1 or len(front) != 1:
        return None
    return top[0].BoundBox.YMin, 10 - front[0].BoundBox.ZMax


def arrow_on_top(p, index=0):
    """True if arrow `index` lies on the top face (points along +Y from the front edge)."""
    _dragger, _spot, _origin, direction = p.arrows[index]
    return abs(direction.y - 1.0) < 1e-6


def ribbon_chamfer():
    Gui.Selection.clearSelection()
    h.ribbon("Chamfer")


def waiting():
    p = b.blend_panel()
    h.check("Chamfer dialog open", p is not None and p.title == "Chamfer")
    if p is None:
        return
    h.check(
        "Equal Distance by default",
        p.ctype.currentText() == "Equal Distance",
        p.ctype.currentText(),
    )
    h.check(
        "only one distance field shown",
        not p.distance2.widget.isVisible()
        and not p.angle.widget.isVisible()
        and not p.flip.isVisible(),
    )
    h.check("nothing picked yet", not p.refs and p.target is None)
    b.no_popups("Chamfer with nothing selected")
    h.shot("1-waiting")


def click_edge():
    h.fit()
    h.click_edge(FRONT_TOP)


def equal_1():
    v = h.solid_volume()
    h.check("preview: equal distance 1 (V = 12000 - 40 * 1 * 1 / 2)", b.close(v, legs(1, 1)), v)
    p = b.blend_panel()
    h.check("one arrow for one distance", p is not None and len(p.arrows) == 1)
    if p:
        b.type_into(p.distance.widget, "2")


def equal_2():
    v = h.solid_volume()
    h.check("typed distance 2", b.close(v, legs(2, 2)), v)
    p = b.blend_panel()
    if p:
        b.choose(p.ctype, "Two Distances")


def two_distances_rows():
    p = b.blend_panel()
    if p is None:
        return
    h.check(
        "Two Distances shows Distance 1, Distance 2 and Flip",
        p.distance_label.text() == "Distance 1"
        and p.distance2.widget.isVisible()
        and p.flip.isVisible()
        and not p.angle.widget.isVisible(),
    )
    h.check("a second arrow for Distance 2", len(p.arrows) == 2, len(p.arrows))
    b.type_into(p.distance2.widget, "4")


def two_distances():
    p = b.blend_panel()
    v = h.solid_volume()
    h.check("two distances 2 and 4 (V = 12000 - 40 * 2 * 4 / 2)", b.close(v, legs(2, 4)), v)
    top, front = cuts() or (None, None)
    on_top = arrow_on_top(p, 0)
    s["first_on_top"] = on_top
    expect = (2, 4) if on_top else (4, 2)
    h.check(
        "Distance 1 is measured on the face its arrow lies on",
        top is not None and b.close(top, expect[0]) and b.close(front, expect[1]),
        (top, front, on_top),
    )
    h.shot("2-two-distances")
    b.click_widget(p.flip)


def flipped():
    p = b.blend_panel()
    v = h.solid_volume()
    h.check("Flip keeps the volume", b.close(v, legs(2, 4)), v)
    top, front = cuts() or (None, None)
    on_top = arrow_on_top(p, 0)
    h.check(
        "Flip moves Distance 1 (and its arrow) to the other face",
        on_top != s["first_on_top"],
        on_top,
    )
    expect = (2, 4) if on_top else (4, 2)
    h.check(
        "sizes swapped on the part",
        top is not None and b.close(top, expect[0]) and b.close(front, expect[1]),
        (top, front),
    )
    h.shot("3-flipped")


def drag_second_arrow():
    p = b.blend_panel()
    if p is None or len(p.arrows) < 2:
        h.check("second arrow to drag", False)
        return
    s["d2"] = p.distance2.value()
    start, end = b.arrow_screen(p, 1, along=-1.5)
    h.drag(start, end)


def dragged():
    p = b.blend_panel()
    d1, d2 = p.distance.value(), p.distance2.value()
    h.check("dragging the second arrow back shrinks Distance 2", d2 < s["d2"] - 0.3, (s["d2"], d2))
    v = h.solid_volume()
    h.check("preview follows the drag", b.close(v, legs(d1, d2)), (v, legs(d1, d2)))
    b.choose(p.ctype, "Distance and Angle")


def angle_rows():
    p = b.blend_panel()
    if p is None:
        return
    h.check(
        "Distance and Angle shows Distance and Angle",
        p.distance_label.text() == "Distance"
        and p.angle.widget.isVisible()
        and not p.distance2.widget.isVisible(),
    )
    b.type_into(p.distance.widget, "3")


def type_angle():
    p = b.blend_panel()
    if p:
        b.type_into(p.angle.widget, "30")


def ok():
    v = h.solid_volume()
    expect = legs(3, 3 * math.tan(math.radians(30)))
    h.check("distance 3 at 30 degrees (other leg 3 tan 30)", b.close(v, expect), (v, expect))
    h.task_button("OK")


def after_ok():
    shape = h.body().Shape
    expect = legs(3, 3 * math.tan(math.radians(30)))
    h.check("chamfer kept", b.close(shape.Volume, expect), shape.Volume)
    h.check("7 faces", len(shape.Faces) == 7, len(shape.Faces))
    h.check(
        "one Chamfer feature",
        len(b.blends()) == 1 and b.blends()[0].TypeId == "PartDesign::Chamfer",
        b.blends(),
    )
    h.check("dialog closed", not Gui.Control.activeDialog())
    s["v"] = shape.Volume
    h.shot("4-ok")


def undo():
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def after_undo():
    h.check("Ctrl+Z removes the chamfer", b.close(h.solid_volume(), b.BOX) and not b.blends())


def redo():
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def after_redo():
    h.check("Ctrl+Y brings it back", b.close(h.solid_volume(), s["v"]) and len(b.blends()) == 1)
    h.fit()


def edit():
    b.timeline_double_click("Chamfer 1")


def edit_open():
    p = b.blend_panel()
    h.check("double-click opens the Chamfer dialog", p is not None and not p.created)
    if p is None:
        return
    h.check(
        "type, distance, angle and flip shown as saved",
        p.ctype.currentText() == "Distance and Angle"
        and abs(p.distance.value() - 3) < 1e-9
        and abs(p.angle.value() - 30) < 1e-9
        and p.flip.isChecked(),
        (p.ctype.currentText(), p.distance.value(), p.angle.value()),
    )
    h.check("its edge is picked", len(p.refs) == 1, p.refs)
    b.type_into(p.angle.widget, "45")


def edit_ok():
    h.task_button("OK")


def after_edit():
    v = h.solid_volume()
    h.check("edited to 45 degrees (legs 3 and 3)", b.close(v, legs(3, 3)), v)
    s["v"] = v


def esc_start():
    h.ribbon("Chamfer")


def esc_pick():
    h.fit()
    h.click(TOP_FACE)


def esc_press():
    p = b.blend_panel()
    h.check("top face picked", p is not None and p.refs and p.refs[0].startswith("Face"))
    h.check("preview shown", not b.close(h.solid_volume(), s["v"]))
    h.press(QtCore.Qt.Key_Escape)


def after_esc():
    h.check("Esc cancels: model unchanged", b.close(h.solid_volume(), s["v"]), h.solid_volume())
    h.check("Esc closes the dialog", not Gui.Control.activeDialog())
    h.check("still one chamfer", len(b.blends()) == 1)


def preselect():
    h.fit()
    h.click_edge(BACK_TOP)
    h.click_edge(BACK_RIGHT, modifiers=QtCore.Qt.ControlModifier)


def chamfer_with_selection():
    h.ribbon("Chamfer")


def started():
    p = b.blend_panel()
    h.check(
        "Chamfer starts with the selected edges", p is not None and len(p.refs) == 2, p and p.refs
    )
    h.task_button("OK")


def after_second():
    shape = h.body().Shape
    expect = s["v"] - (40 + 10) * 0.5 + 1.0 / 3.0
    h.check(
        "second chamfer: back-top + back-right edges, 1 mm (corner overlap d^3/3)",
        b.close(shape.Volume, expect),
        (shape.Volume, expect),
    )
    h.check("timeline shows Chamfer 2", "Chamfer 2" in b.timeline_titles(), b.timeline_titles())
    h.check("valid solid", shape.isValid())
    h.check(
        "no kernel errors in the Report view",
        not b.report_has_kernel_errors(),
        b.report_has_kernel_errors(),
    )
    h.shot("5-end")


h.run(
    "fillet_chamfer",
    b.box_steps("Chamfer")
    + [
        ribbon_chamfer,
        waiting,
        click_edge,
        equal_1,
        equal_2,
        two_distances_rows,
        two_distances,
        flipped,
        drag_second_arrow,
        dragged,
        angle_rows,
        type_angle,
        ok,
        after_ok,
        undo,
        after_undo,
        redo,
        after_redo,
        edit,
        edit_open,
        edit_ok,
        after_edit,
        esc_start,
        esc_pick,
        esc_press,
        after_esc,
        preselect,
        chamfer_with_selection,
        started,
        after_second,
    ],
)
