# SPDX-License-Identifier: LGPL-2.1-or-later
"""Drag arrows show in front of the part and can be grabbed through it (Luca, 2026-10-13:
"arrows for dragging currently get occluded by bodies").

Fusion's manipulators are drawn over the model and never hidden by it. Block 40 x 30 x 10,
click the top face, Q: the Press Pull arrow stands on the top face pointing up. The camera
is put below the block, looking up at a slant: the arrow is now behind the block.

A  The pixel at the arrow's head shows the arrow's blue, not the block.
B  A press on that pixel and a drag along the arrow move the face (the arrow was grabbed
   through the block; the block's bottom face was not picked instead).
C  Esc closes the dialog and the arrow goes.
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

from SciForgeTests.gui import arrow_input as a
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}


def panel():
    from sciforge import presspull_ui

    return presspull_ui.PressPullPanel.last


def pixel(pos):
    """(r, g, b) of the screen at widget pixel `pos` of the 3D view (a screen grab: the GL
    view renders under xvfb, and the widget's own grab does not see GL output)."""
    gl = h.gl_widget()
    at = gl.mapToGlobal(QtCore.QPoint(int(pos.x()), int(pos.y())))
    screen = QtGui.QGuiApplication.primaryScreen()
    image = screen.grabWindow(0).toImage()
    ratio = image.width() / float(max(screen.geometry().width(), 1))
    x = min(max(int(at.x() * ratio), 0), image.width() - 1)
    y = min(max(int(at.y() * ratio), 0), image.height() - 1)
    c = image.pixelColor(x, y)
    return (c.red(), c.green(), c.blue())


def blue_dominant(rgb):
    r, g, b = rgb
    return b > r + 40 and b >= g


def setup():
    from sciforge import commands, extrude, sketch_ui

    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("HandlesOnTop")
    body = commands.ensure_body()
    sk = sketch_ui.create_sketch(body, (sketch_ui.origin_planes(body)["XY_Plane"], ""))
    h.draw_rectangle(sk, 0, 0, 40, 30)
    extrude.make(body, sk, {"distance": 10.0})
    App.ActiveDocument.recompute()
    h.fit()
    s["volume"] = h.solid_volume()


def pick_top():
    h.click(V(20, 15, 10))


def press_q():
    h.press("q")


def opened():
    p = panel()
    h.check("Press Pull opened on the top face", p is not None and p.target is not None)
    h.check("it has an arrow", p is not None and p.dragger is not None)
    s["target"] = p.target if p is not None else None


def look_from_below():
    # Below the block, looking up at a slant: the arrow above the top face is behind it.
    view = h.view()
    # Coin's camera looks along -Z by default: turn that onto a direction with +Z (upward).
    look = App.Vector(0.35, 0.25, 0.9)
    view.setCameraOrientation(tuple(App.Rotation(App.Vector(0, 0, -1), look).Q))
    view.fitAll()
    QtWidgets.QApplication.processEvents()


look_from_below.wait_ms = 900


def a_arrow_visible():
    p = panel()
    head = a.head_point(p.dragger)
    pos = h.screen_point(head)
    s["head_px"] = pos
    rgb = pixel(pos)
    direction = h.view().getViewDirection()
    h.check("A: the camera looks up from below", direction.z > 0.5, direction)
    h.check("A: the arrow's head is drawn through the block (blue pixel)", blue_dominant(rgb), rgb)
    # the bottom face itself, beside the arrow, is the block's colour
    beside = pixel(h.screen_point(V(5, 5, 0)))
    h.check("A: the block beside it is not blue", not blue_dominant(beside), beside)
    h.shot("A-arrow-through-block")


def b_drag_through():
    p = panel()
    gl = h.gl_widget()
    start = s["head_px"]
    # along the arrow as it shows on the screen
    o = h.screen_point(p.dragger.origin)
    t = h.screen_point(p.dragger.origin + p.dragger.direction * 10.0)
    along = QtCore.QPointF(t.x() - o.x(), t.y() - o.y())
    length = max((along.x() ** 2 + along.y() ** 2) ** 0.5, 1e-6)
    step = QtCore.QPointF(along.x() / length * 50.0, along.y() / length * 50.0)
    end = QtCore.QPoint(int(start.x() + step.x()), int(start.y() + step.y()))
    s["before"] = p.dragger.distance()
    h.drag(QtCore.QPoint(start), end, steps=20)
    s["gl"] = gl


b_drag_through.wait_ms = 1500


def b_moved():
    p = panel()
    h.check("B: the dialog is still open", p is not None and not getattr(p, "_closed", True))
    if p is None:
        return
    h.check(
        "B: the arrow was grabbed through the block (distance changed)",
        abs(p.dragger.distance() - s["before"]) > 1.0,
        (s["before"], p.dragger.distance()),
    )
    h.check("B: the face moved with it", abs(p.field.value()) > 1.0, p.field.value())
    h.check("B: the target face was not swapped by the click", p.target == s["target"], p.target)
    h.check("B: the block's face was not selected instead", not Gui.Selection.getSelectionEx())
    h.shot("B-dragged")


def c_esc():
    h.press(QtCore.Qt.Key_Escape)


def c_closed():
    h.check("C: Esc closed the dialog", panel() is None or getattr(panel(), "_closed", True))
    h.check(
        "C: the block is unchanged", abs(h.solid_volume() - s["volume"]) < 1e-6, h.solid_volume()
    )
    h.check("C: no pop-ups", not h.popups(), h.popups())


h.run(
    "handles_on_top",
    [
        setup,
        pick_top,
        press_q,
        opened,
        look_from_below,
        a_arrow_visible,
        b_drag_through,
        b_moved,
        c_esc,
        c_closed,
    ],
)
