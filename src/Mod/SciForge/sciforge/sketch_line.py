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
        if self.session.infer is not None:
            # L again halfway through a line: the old start must not pull the new one
            self.session.infer.reset()
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
                if self.session.infer is not None:
                    # FreeCAD's tool still holds the point it was started on (gone
                    # now): started again, else the next line is joined to itself
                    self.session.infer.line_undone()
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
            elif self.session.infer is not None:
                # the chain's point, for a press-and-drag there before any move
                # (FreeCAD previews nothing then): the tangent arc
                self.session.infer.last_start = (end.x, end.y)
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
        pos = QtCore.QPointF(round(x / ratio), round(gl.height() - y / ratio))
        if not (0 <= pos.x() < gl.width() and 0 <= pos.y() < gl.height()):
            return False
        pos = self._aim_at_vertex(pos)
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

    def _aim_at_vertex(self, pos):
        """FreeCAD's click takes what its last mouse move found under the pixel: on a
        tilted view (a sketch on a turned plane) the point's own pixel can find the
        line through it instead, and the next line then only sits on that line, a bit
        short of its end. The pointer is moved over the pixels around (within 3) until
        FreeCAD lights up a point; that pixel is clicked. Else the pixel itself."""
        session = self.session
        gl = session.gl
        sketch = session.sketch
        none = QtCore.Qt.NoButton

        def point_lit():
            pre = Gui.Selection.getPreselection()
            if getattr(pre, "Object", None) is not sketch:
                return False
            names = getattr(pre, "SubElementNames", None) or ()
            return any(n.rsplit(".", 1)[-1].startswith("Vertex") for n in names)

        try:
            for radius in range(0, 4):
                for dx in range(-radius, radius + 1):
                    for dy in range(-radius, radius + 1):
                        if max(abs(dx), abs(dy)) != radius:
                            continue
                        at = QtCore.QPointF(pos.x() + dx, pos.y() + dy)
                        event = QtGui.QMouseEvent(
                            QtCore.QEvent.MouseMove,
                            at,
                            QtCore.QPointF(gl.mapToGlobal(at.toPoint())),
                            none,
                            none,
                            QtCore.Qt.NoModifier,
                        )
                        QtWidgets.QApplication.sendEvent(gl, event)
                        if point_lit():
                            return at
        except Exception as exc:
            warn("line: %s" % exc)
        return pos
