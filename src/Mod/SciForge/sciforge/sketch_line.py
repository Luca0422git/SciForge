# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Line (L): lines joined end to end, with the length and angle typed while
drawing.

FreeCAD has two line tools: the old polyline (joins lines, but takes no typed values)
and the new line tool (on-screen Length and Angle fields: type 50, Tab, 30, Enter,
which also adds the dimension, like Fusion) that draws one line per two clicks. SciForge
runs the new tool and joins the lines itself: when a line has been added, the next one
starts at its end (the end point is clicked for you, so FreeCAD makes the two ends
coincident as if you had clicked it). Clicking the first point of the chain closes the
shape and the next click starts a new chain, like Fusion. Esc stops the tool.

The click is sent from a Qt timer after FreeCAD has finished adding the line (never from
inside FreeCAD's own click handling).
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import log, warn
from .compat import QtCore, QtGui, QtWidgets

COMMAND = "Sketcher_CreateLine"
TOLERANCE = 1e-6


class LineChain:
    """One per sketch session; active while SciForge's Line tool runs."""

    def __init__(self, session):
        self.session = session
        self.active = False
        self.chain_start = None  # sketch point where the current chain began
        self.seen = 0  # geometry count already looked at

    def start(self):
        sketch = self.session.sketch
        self.active = True
        self.chain_start = None
        self.seen = len(sketch.Geometry)
        Gui.runCommand(COMMAND)

    def stop(self):
        self.active = False
        self.chain_start = None

    def _tool_running(self):
        """The line tool is still the active tool: it was the last command started and
        FreeCAD's drawing cursor is still on the 3D view."""
        from . import recent

        last = recent.last()
        if last is not None and last[0] not in ("SciForge_SketchLine", COMMAND):
            return False
        gl = self.session.gl
        try:
            return gl is not None and gl.cursor().shape() != QtCore.Qt.ArrowCursor
        except Exception:
            return False

    def committed(self):
        """Something was committed in the sketch (FreeCAD's document signal): look at it
        later, from a timer."""
        if self.active:
            QtCore.QTimer.singleShot(0, self._continue)

    def _continue(self):
        if not self.active or self.session.closed:
            return
        try:
            sketch = self.session.sketch
            count = len(sketch.Geometry)
            if count < self.seen:  # undone
                self.seen = count
                self.chain_start = None
                return
            if count == self.seen:
                return
            new = list(range(self.seen, count))
            self.seen = count
            if not self._tool_running():
                self.stop()
                return
            lines = [i for i in new if sketch.Geometry[i].TypeId == "Part::GeomLineSegment"]
            if len(lines) != 1 or len(new) != 1:
                return  # not a single line from the tool (a pattern, a paste...)
            line = sketch.Geometry[lines[0]]
            if self.chain_start is None:
                self.chain_start = App.Vector(line.StartPoint)
            end = App.Vector(line.EndPoint)
            if (end - self.chain_start).Length <= TOLERANCE:
                # back on the first point: the shape is closed; the next click starts anew
                self.chain_start = None
                return
            if not self._click_at(end):
                self.chain_start = None
                from . import commands

                commands.tell("Line: click the end of the last line to go on from it.")
        except Exception as exc:
            warn("line: %s" % exc)

    def _click_at(self, sketch_point):
        """Click the sketch point on the 3D view (and put the pointer back where the hand
        is). False when that point is not on the screen."""
        session = self.session
        gl = session.gl
        if gl is None:
            return False
        world = session.sketch.getGlobalPlacement().multVec(sketch_point)
        x, y = session.view.getPointOnViewport(world)
        ratio = gl.devicePixelRatioF()
        pos = QtCore.QPointF(x / ratio, gl.height() - y / ratio)
        if not (0 <= pos.x() < gl.width() and 0 <= pos.y() < gl.height()):
            return False
        hand = gl.mapFromGlobal(QtGui.QCursor.pos())
        left, none = QtCore.Qt.LeftButton, QtCore.Qt.NoButton
        mods = QtCore.Qt.NoModifier
        for kind, button, buttons, at in (
            (QtCore.QEvent.MouseMove, none, none, pos),
            (QtCore.QEvent.MouseButtonPress, left, left, pos),
            (QtCore.QEvent.MouseButtonRelease, left, none, pos),
        ):
            event = QtGui.QMouseEvent(
                kind, at, QtCore.QPointF(gl.mapToGlobal(at.toPoint())), button, buttons, mods
            )
            QtWidgets.QApplication.sendEvent(gl, event)
        if gl.rect().contains(hand) and (QtCore.QPointF(hand) - pos).manhattanLength() > 2:
            back = QtCore.QPointF(hand)
            event = QtGui.QMouseEvent(
                QtCore.QEvent.MouseMove,
                back,
                QtCore.QPointF(gl.mapToGlobal(hand)),
                none,
                none,
                mods,
            )
            QtWidgets.QApplication.sendEvent(gl, event)
        log("line: next line from the end of the last one")
        return True
