# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's floating green check while a sketch line chain or a spline is being drawn.

Fusion shows a small green check beside the point a line chain goes on from: a click on
it ends the chain and the Line tool stays on, waiting for a new first point (Autodesk's
help, "Create lines in a sketch": click the check icon to finish the line set, then
start another line or press Enter to leave the tool; Autodesk's sketch basics course:
"click the green check mark or double-click the endpoint to end the current chain and
remain in the Line command, or press Esc to exit"). The splines show the same check once
they have two points: it makes the spline from the points clicked so far and the tool
stays on for the next one. Sources and guesses: docs/sciforge/parity/sketch.md.

The check is a child of the 3D view (like the dimension box), never takes the keyboard,
and follows the point while the view turns or zooms (a timer looks every 100 ms). A click
on it goes to the check, not to the sketch underneath.
"""

import time

from . import log, warn
from .compat import QtCore, QtGui, QtWidgets

NAME = "SciForgeSketchCheck"
SIZE = 22  # px, the check's diameter
OFFSET = QtCore.QPoint(20, 22)  # px from the point to the check's centre (down right:
# FreeCAD's length box of the next line sits above it)
POLL_MS = 100
DOUBLE_PRESS_S = 0.05  # a copy of a press handed on by the inference is the same press
GREEN = "#2fa84f"
GREEN_HOVER = "#3cc463"


class CheckButton(QtWidgets.QAbstractButton):
    """The round green check (SciForge's own drawing, not Fusion's artwork)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName(NAME)
        self.setFixedSize(SIZE, SIZE)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setAttribute(QtCore.Qt.WA_Hover, True)
        self.hide()

    def paintEvent(self, _event):
        painter = QtGui.QPainter(self)
        try:
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            colour = GREEN_HOVER if self.underMouse() else GREEN
            painter.setPen(QtGui.QPen(QtGui.QColor("#ffffff"), 1.5))
            painter.setBrush(QtGui.QColor(colour))
            painter.drawEllipse(QtCore.QRectF(1, 1, SIZE - 2, SIZE - 2))
            pen = QtGui.QPen(QtGui.QColor("#ffffff"), 2.4)
            pen.setCapStyle(QtCore.Qt.RoundCap)
            pen.setJoinStyle(QtCore.Qt.RoundJoin)
            painter.setPen(pen)
            s = SIZE / 22.0
            painter.drawPolyline(
                QtGui.QPolygonF(
                    [
                        QtCore.QPointF(6.0 * s, 11.5 * s),
                        QtCore.QPointF(9.5 * s, 15.0 * s),
                        QtCore.QPointF(16.0 * s, 7.5 * s),
                    ]
                )
            )
        finally:
            painter.end()


class _PressCount(QtCore.QObject):
    """Counts left presses on the 3D view (never blocks them): a spline's points so far."""

    def __init__(self, check):
        super().__init__()
        self.check = check

    def eventFilter(self, obj, event):
        try:
            if (
                event.type() == QtCore.QEvent.MouseButtonPress
                and event.button() == QtCore.Qt.LeftButton
            ):
                self.check.pressed(event.position().toPoint())
        except Exception:
            pass
        return False


class FloatingCheck:
    """One per sketch session (sketch_mode.SketchSession): shows the check while there is
    something it can finish, and does it when clicked."""

    def __init__(self, session):
        self.session = session
        self.button = None
        self.kind = None  # "line" | "spline" while shown
        self._spline_on = False
        self._spline_presses = 0
        self._last_press = None  # (widget point, time)
        self._counter = None
        self.timer = None
        gl = session.gl
        if gl is None:
            return
        try:
            for old in gl.findChildren(QtWidgets.QAbstractButton, NAME):
                old.hide()
                old.deleteLater()  # one left over from a sketch that closed badly
            self.button = CheckButton(gl)
            self.button.clicked.connect(self.clicked)
            self._counter = _PressCount(self)
            gl.installEventFilter(self._counter)
        except Exception as exc:
            warn("sketch check: %s" % exc)
            self.button = None
        self.timer = QtCore.QTimer()
        self.timer.setInterval(POLL_MS)
        self.timer.timeout.connect(self.update)
        self.timer.start()

    # -- what it can finish --------------------------------------------------------------------
    def pressed(self, pos):
        now = time.time()
        last = self._last_press
        if last is not None and now - last[1] < DOUBLE_PRESS_S:
            return
        self._last_press = (QtCore.QPoint(pos), now)
        if self._spline_on:
            self._spline_presses += 1

    def _line_anchor(self):
        """The pixel the line chain goes on from, while one is being drawn."""
        line = self.session.line
        if not line.active or line.current is None or not line._tool_running():
            return None
        return line._pixel(line.current)

    def _spline_anchor(self):
        """The last point clicked of a spline being drawn, once it has two."""
        session = self.session
        running = bool(session._spline_tool())
        if running != self._spline_on:
            self._spline_on = running
            self._spline_presses = 0
        if not running or self._spline_presses < 2 or self._last_press is None:
            return None
        return QtCore.QPointF(self._last_press[0])

    def wanted(self):
        """(kind, pixel) the check belongs to now, or (None, None)."""
        session = self.session
        if session.closed or session.editor is not None:
            return None, None
        if session.tool is not None and session.tool.active:
            return None, None  # SciForge's own tools have their own steps and boxes
        at = self._line_anchor()
        if at is not None:
            return "line", at
        at = self._spline_anchor()
        if at is not None:
            return "spline", at
        return None, None

    def update(self):
        button = self.button
        if button is None:
            return
        try:
            from .sketch_mode import _is_valid

            if not _is_valid(button):
                self.button = None
                return
            kind, at = self.wanted()
            self.kind = kind
            if kind is None:
                if button.isVisible():
                    button.hide()
                return
            parent = button.parentWidget()
            centre = QtCore.QPoint(int(round(at.x())), int(round(at.y()))) + OFFSET
            left = max(0, min(parent.width() - SIZE, centre.x() - SIZE // 2))
            top = max(0, min(parent.height() - SIZE, centre.y() - SIZE // 2))
            if button.pos() != QtCore.QPoint(left, top):
                button.move(left, top)
                button.raise_()  # over FreeCAD's length and angle boxes
            tip = (
                "Finish this chain of lines (the Line tool stays on)"
                if kind == "line"
                else "Finish this spline (the tool stays on)"
            )
            if button.toolTip() != tip:
                button.setToolTip(tip)
            if not button.isVisible():
                button.show()
                button.raise_()
        except RuntimeError:
            self.button = None
        except Exception as exc:
            warn("sketch check: %s" % exc)

    # -- the click -----------------------------------------------------------------------------
    def clicked(self):
        """Fusion's check: the chain (or the spline) ends, the tool stays on."""
        kind = self.kind
        session = self.session
        try:
            if kind == "line":
                if session.line.break_chain():
                    log("sketch: green check: line chain finished")
            elif kind == "spline":
                session._commit_spline()
                session._drop_spline(cancelled=False)
                self._spline_presses = 0
                log("sketch: green check: spline finished")
        except Exception as exc:
            warn("sketch check: %s" % exc)
        finally:
            if self.button is not None:
                try:
                    self.button.hide()
                except RuntimeError:
                    self.button = None
            try:
                gl = session.gl
                if gl is not None:
                    gl.setFocus()  # the keys stay with the sketch
            except Exception:
                pass

    def remove(self):
        try:
            if self.timer is not None:
                self.timer.stop()
        except Exception:
            pass
        gl = self.session.gl
        if self._counter is not None and gl is not None:
            try:
                gl.removeEventFilter(self._counter)
            except Exception:
                pass
        self._counter = None
        button, self.button = self.button, None
        if button is not None:
            try:
                button.hide()
                button.deleteLater()
            except RuntimeError:
                pass
