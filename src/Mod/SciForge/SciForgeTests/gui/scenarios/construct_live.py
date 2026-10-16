# SPDX-License-Identifier: LGPL-2.1-or-later
"""Construction planes follow the arrow WHILE it is dragged (Luca, 2026-10-16: "construction
planes don't update in real time and do not display the distance near the arrow").

Box 40 x 30 x 10 (real input). CONSTRUCT > Offset Plane, click the top face: a plane 10 mm
above it (z = 20) and the blue arrow with its value box.

A  The arrow pressed and moved up in steps with the button still down: between the moves
   the plane is already higher than z = 20 (it rebuilt during the drag, not only at the
   release), and the value box next to the arrow shows the dragged distance.
B  Released: the plane stays where the drag left it; OK makes one plane there.
"""

from PySide import QtCore, QtGui, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import inspect_steps as s

import FreeCAD as App

V = App.Vector
st = {}


def start():
    h.click_empty()
    h.ribbon("Offset Plane")


def click_top():
    h.fit()
    h.click(V(20, 15, 10))


def preview():
    p = s.construct_panel()
    d = p.datum if p else None
    if not h.check("a plane 10 mm above the top face", d is not None):
        return
    h.check("at z = 20", s.close(d.getGlobalPlacement().Base.z, 20.0), d.getGlobalPlacement())
    h.check("the arrow is there", p.handle is not None and p.handle_key == "distance")


def _move(widget, pos):
    event = QtGui.QMouseEvent(
        QtCore.QEvent.MouseMove,
        QtCore.QPointF(pos),
        QtCore.QPointF(widget.mapToGlobal(pos)),
        QtCore.Qt.NoButton,
        QtCore.Qt.LeftButton,
        QtCore.Qt.NoModifier,
    )
    QtWidgets.QApplication.sendEvent(widget, event)
    QtWidgets.QApplication.processEvents()


def a_press_and_drag():
    p = s.construct_panel()
    if p is None or p.handle is None:
        return
    h.fit()
    handle = p.handle
    grab = handle.base_point() + handle.direction * (handle.size * 0.55)
    start_px = s.screen(grab)
    widget = h.gl_widget()
    h.move(start_px)
    QtTest.QTest.mousePress(widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, start_px)
    seen = []
    # Like a real mouse: a pixel every 10 ms (a mouse reports far more often than the
    # handle's 30 ms poll), about 0.8 s with the button held.
    for i in range(1, 81):
        _move(widget, QtCore.QPoint(start_px.x(), start_px.y() - i))
        QtTest.QTest.qWait(10)
        d = p.datum
        if d is not None:
            seen.append(d.getGlobalPlacement().Base.z)
    st["during"] = seen
    st["widget"], st["end"] = widget, QtCore.QPoint(start_px.x(), start_px.y() - 80)


def a_check_during():
    seen = st.get("during") or []
    h.check(
        "the plane moved up while the button was still down",
        any(z > 20.5 for z in seen),
        seen[-8:],
    )
    # The shared pace rebuilds about every 60 ms on a small part: a 0.8 s drag gives many
    # positions (40 here). Restarting the timer on every poll gave a few jumps (8 here: only
    # when the mouse happened to rest).
    h.check(
        "it followed the drag (many positions while the button was down)",
        len({round(z, 3) for z in seen}) >= 20,
        sorted({round(z, 3) for z in seen}),
    )
    QtTest.QTest.mouseRelease(st["widget"], QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, st["end"])
    QtWidgets.QApplication.processEvents()


def b_released():
    p = s.construct_panel()
    if p is None or p.datum is None:
        h.check("dialog still open after the drag", False)
        return
    value = p.values["distance"]
    z = p.datum.getGlobalPlacement().Base.z
    h.check("the drag lengthened the distance", value > 10.5, value)
    h.check("the plane is where the distance says", s.close(z, 10.0 + value, 1e-6), (z, value))
    st["value"] = value
    h.task_button("OK")


def b_made():
    planes = s.datums()
    h.check("one construction plane made", len(planes) == 1, planes)
    if planes:
        z = planes[0].getGlobalPlacement().Base.z
        h.check("kept where the drag left it", s.close(z, 10.0 + st["value"], 1e-6), z)
    s.no_popups("the end")


h.run(
    "construct_live",
    b.box_steps("ConstructLive")
    + [start, click_top, preview, a_press_and_drag, a_check_during, b_released, b_made],
)
