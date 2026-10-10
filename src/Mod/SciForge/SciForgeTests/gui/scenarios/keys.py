# SPDX-License-Identifier: LGPL-2.1-or-later
"""Standard keys while SciForge is on: Ctrl+Z / Ctrl+Y undo and redo a whole
command. FreeCAD only honours its own Ctrl+Z while its (hidden) menu bar is
visible, so these did nothing until SciForge bound them itself."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import harness as h

V = App.Vector
s = {}


def start():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Keys")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xy():
    h.click(V(12, -8, 0))


def draw():
    sk = h.in_sketch()
    h.check("sketch open", sk is not None)
    if sk:
        h.draw_rectangle(sk, 0, 0, 40, 30)


def finish():
    h.ribbon("Finish Sketch")


def extrude():
    h.fit()
    h.press("e")


def extrude_ok():
    h.task_button("OK")


def after_extrude():
    s["v"] = h.solid_volume()
    h.check("extruded", s["v"] > 1000, s["v"])


def undo():
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def after_undo():
    v = h.solid_volume()
    h.check("Ctrl+Z undoes the extrude", v < 1, v)


def redo():
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def after_redo():
    v = h.solid_volume()
    h.check("Ctrl+Y redoes it", abs(v - s["v"]) < 1e-6, (v, s["v"]))


h.run(
    "keys",
    [
        start,
        pick_xy,
        draw,
        finish,
        extrude,
        extrude_ok,
        after_extrude,
        undo,
        after_undo,
        redo,
        after_redo,
    ],
)
