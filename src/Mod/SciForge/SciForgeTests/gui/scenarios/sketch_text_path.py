# SPDX-License-Identifier: LGPL-2.1-or-later
"""Text On Path (a name round a circle, like on a coin or a knob), real input only.
Fusion's behaviour (Autodesk help "Create text in a sketch": Type Text On Path, Path,
Placement Above / Below, Fit to Path; Fusion forum threads on text on a circle):

P1  Type "Text On Path": the dialog asks for the path; a click on the circle picks it.
P2  typing shows the letters along the circle, standing on it (Above); Center puts them
    at the top of the circle.
P3  Below puts them inside the circle, hanging under it.
P4  Fit to Path spreads them round the whole circle.
P5  OK makes the text (one undo step "Text", no frame lines: the circle holds it).
P6  the text follows its path: dimensioning the circle 50 mm moves the letters out.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import text_input as ti

V = App.Vector
C = (30.0, 30.0)
R = 20.0
HEIGHT = 5.0
s = {}


def doc():
    return App.ActiveDocument


def wait_preview():
    QtTest.QTest.qWait(120)
    QtWidgets.QApplication.processEvents()


def ring(points, center=C):
    """(smallest, largest) distance of the points from the circle's centre."""
    d = [math.hypot(x - center[0], y - center[1]) for x, y in points]
    return (min(d), max(d)) if d else (0.0, 0.0)


def preview_points():
    d = ti.dialog()
    if d is None or d.plan is None:
        return []
    return [p for line in d.plan.outlines() for p in line]


def turn_span(points, center=C):
    """How far round the centre the points reach, in degrees (0..360)."""
    angles = sorted(math.degrees(math.atan2(y - center[1], x - center[0])) % 360 for x, y in points)
    if len(angles) < 2:
        return 0.0
    gaps = [b - a for a, b in zip(angles, angles[1:])] + [angles[0] + 360 - angles[-1]]
    return 360.0 - max(gaps)


def even_round(center=C):
    """True if the gap from the last previewed letter round to the first is like the
    gaps between the others (Fit to Path on a circle)."""
    from sciforge import text_core

    d = ti.dialog()
    if d is None or d.plan is None or len(d.plan.glyphs) < 3:
        return False
    angles = []
    for g in d.plan.glyphs:
        pts = [text_core.apply(g.transform, x, y) for line in g.shape.outlines for x, y in line]
        mx = sum(p[0] for p in pts) / len(pts)
        my = sum(p[1] for p in pts) / len(pts)
        angles.append(math.degrees(math.atan2(my - center[1], mx - center[0])) % 360)
    # the letters go round clockwise: each step from one letter to the next, and the
    # step from the last back to the first
    steps = sorted((a - b) % 360 for a, b in zip(angles, angles[1:]))
    wrap = (angles[-1] - angles[0]) % 360
    return wrap > 0.7 * steps[len(steps) // 2]


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("TextPath")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xy():
    pl.click_square("XY_Plane")  # where the square shows (was 12, -8, 0)


def sketch_open():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None)
    s["sketch"] = sk
    h.view().viewTop()
    cam = h.view().getCameraNode()
    try:
        cam.height.setValue(110.0)
    except Exception:
        pass
    cam.position.setValue(C[0], C[1], 100.0)
    QtWidgets.QApplication.processEvents()


def circle_key():
    h.press("c")


def circle_centre():
    si.click(V(C[0], C[1], 0))


def circle_radius():
    si.click(V(C[0] + R, C[1], 0))


def circle_done():
    h.press(QtCore.Qt.Key_Escape)


def circle_check():
    circles = si.circles(s["sketch"], construction=False)
    h.check(
        "setup: one circle r 20 at (30, 30)",
        len(circles) == 1 and si.near(circles[0][1].Radius, R, 1e-3),
        circles,
    )
    h.press(QtCore.Qt.Key_Escape)


# -- P1 -----------------------------------------------------------------------------------------
def p1_open():
    ti.open_text_tool()


def p1_type_on_path():
    d = ti.dialog()
    h.check("P1 the Text dialog opened", d is not None)
    if d is None:
        return
    d.type_box.setFocus()
    QtTest.QTest.keyClick(d.type_box, QtCore.Qt.Key_Down)
    QtWidgets.QApplication.processEvents()


def p1_waits_for_path():
    d = ti.dialog()
    h.check("P1 Type is Text On Path", d.type_box.currentData() == "path")
    h.check("P1 it asks for the path", "curve" in d.hint.text(), d.hint.text())
    h.check("P1 the Path box waits", d.path_button.isChecked())
    h.check("P1 no Angle row on a path", not d.angle.isVisible())
    si.click(V(C[0], C[1] + R, 0))


def p1_picked():
    d = ti.dialog()
    sk = s["sketch"]
    h.check(
        "P1 the click picked the circle",
        d.spec["path_id"] == sk.getGeometryId(0),
        (d.spec["path_id"], d.hint.text()),
    )
    h.check("P1 the Path box shows it", d.path_button.text() == "1 curve", d.path_button.text())
    ti.type_text("SCIFORGE")
    ti.type_field(d.height, "%g" % HEIGHT)


# -- P2 -----------------------------------------------------------------------------------------
def p2_center():
    d = ti.dialog()
    ti.press_button(d.h_buttons["center"])


def p2_above():
    wait_preview()
    points = preview_points()
    low, high = ring(points)
    h.check("P2 the letters show along the circle", len(points) > 50, len(points))
    h.check(
        "P2 standing on it (Above): outside the circle, within the height",
        low > R - 0.3 and high < R + HEIGHT + 0.3,
        (low, high),
    )
    xs = [x for x, _y in points]
    ys = [y for _x, y in points]
    middle = (min(xs) + max(xs)) / 2.0
    h.check(
        "P2 Center puts them at the top",
        abs(middle - C[0]) < 0.5 and min(ys) > C[1],
        (middle, min(ys)),
    )
    h.shot("p2-above")
    ti.press_button(ti.dialog().below)


def p3_below():
    wait_preview()
    low, high = ring(preview_points())
    h.check(
        "P3 Below: inside the circle, hanging under it",
        low > R - HEIGHT - 0.3 and high < R + 0.3,
        (low, high),
    )
    s["span"] = turn_span(preview_points())
    ti.press_button(ti.dialog().fit)


def p4_fit():
    wait_preview()
    span = turn_span(preview_points())
    h.check(
        "P4 Fit to Path spreads them round the circle",
        span > 300.0 and span > s["span"] + 100,
        (span, s["span"]),
    )
    h.check("P4 evenly: the last letter does not run into the first", even_round())
    h.shot("p4-fit")
    d = ti.dialog()
    ti.press_button(d.fit)
    ti.press_button(d.above)


def p5_ok():
    wait_preview()
    ti.ok()


def p5_made():
    sk = s["sketch"]
    found = ti.texts(sk)
    h.check("P5 OK made the text", len(found) == 1 and ti.dialog() is None, found)
    if not found:
        return
    obj = s["text"] = found[0]
    h.check("P5 a text on a path", obj.TextType == "Text On Path", obj.TextType)
    h.check("P5 no frame lines (the circle holds it)", len(sk.Geometry) == 1, len(sk.Geometry))
    h.check(
        "P5 one undo step 'Text'",
        doc().UndoNames and doc().UndoNames[0] == "Text",
        doc().UndoNames[:3],
    )
    shape = obj.Shape.copy()
    shape.Placement = App.Placement()
    low, high = ring([(v.X, v.Y) for v in shape.Vertexes])
    h.check("P5 the letters stand on the circle", low > R - 0.3 and high < R + HEIGHT + 0.3)


# -- P6 -----------------------------------------------------------------------------------------
def p6_dimension_key():
    h.press("d")


def p6_pick_circle():
    a = math.radians(-60.0)  # low on the circle, away from the letters
    si.click(V(C[0] + R * math.cos(a), C[1] + R * math.sin(a), 0))


def p6_place():
    si.click(V(C[0] + 6, C[1] - 4, 0))


def p6_type():
    si.type_text("50")


def p6_followed():
    h.press(QtCore.Qt.Key_Escape)
    circles = si.circles(s["sketch"], construction=False)
    h.check(
        "P6 the circle is 50 mm across",
        circles and si.near(circles[0][1].Radius, 25.0, 1e-6),
        circles,
    )
    QtTest.QTest.qWait(150)
    obj = s["text"]
    layer = ti.layer()
    shown = layer.shown.get(obj.Name) if layer is not None else None
    points = [p for line in shown.outlines for p in line] if shown is not None else []
    center = circles[0][1].Center if circles else V(*C, 0)
    low, high = ring(points, (center.x, center.y))
    h.check(
        "P6 the letters moved out with the circle",
        low > 25.0 - 0.3 and high < 25.0 + HEIGHT + 0.3,
        (low, high),
    )
    h.shot("p6-followed")


h.run(
    "sketch_text_path",
    [
        new_design,
        pick_xy,
        sketch_open,
        circle_key,
        circle_centre,
        circle_radius,
        circle_done,
        circle_check,
        p1_open,
        p1_type_on_path,
        p1_waits_for_path,
        p1_picked,
        p2_center,
        p2_above,
        p3_below,
        p4_fit,
        p5_ok,
        p5_made,
        p6_dimension_key,
        p6_pick_circle,
        p6_place,
        p6_type,
        p6_followed,
    ],
)
