# SPDX-License-Identifier: LGPL-2.1-or-later
"""Real-input helpers for the drag arrows of Extrude and Press Pull and the value box next
to them (scenarios extrude_feel*.py).

harness.drag() sends every mouse move at once inside one step, so a check after it only
sees the end of the drag. HeldDrag moves the mouse like a hand does: the button goes down
on the arrow, the mouse moves on a little every few milliseconds while the program keeps
running between the moves, and a look is taken after each move (what the dialog, the
value box and the part show while the button is still down). Not a scenario itself.
"""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h

BOX_NAME = "SciForgeArrowValue"


def value_boxes(visible_only=True):
    """The value boxes over the 3D view."""
    try:
        widget = h.gl_widget()
    except Exception:
        return []
    found = [w for w in widget.findChildren(QtWidgets.QLineEdit) if w.objectName() == BOX_NAME]
    return [w for w in found if w.isVisible()] if visible_only else found


def head_point(dragger, reach=0.9):
    """A 3D point on the arrow's head (where a person grabs it)."""
    distance = dragger.distance()
    side = 1.0 if distance >= 0 else -1.0
    return dragger.origin + dragger.direction * (distance + side * reach * dragger.size)


class HeldDrag:
    """Press on `start` (widget pixel), move to `end` in `moves` steps `every_ms` apart with
    the left button held, call sample(index) after each move, keep the button down for
    `hold_ms` more (sample(-1) then), release. self.done turns True at the end."""

    def __init__(self, start, end, moves=50, every_ms=20, hold_ms=250, sample=None):
        self.start, self.end = start, end
        self.moves, self.every_ms, self.hold_ms = moves, every_ms, hold_ms
        self.sample = sample
        self.done = False
        self.index = 0
        self.error = None

    @property
    def total_ms(self):
        return self.moves * self.every_ms + self.hold_ms + 200

    def run(self):
        widget = h.gl_widget()
        h.move(self.start)
        QtTest.QTest.mousePress(widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, self.start)
        QtWidgets.QApplication.processEvents()
        QtCore.QTimer.singleShot(self.every_ms, self._next)

    def _pos(self, i):
        t = float(i) / self.moves
        return QtCore.QPointF(
            self.start.x() + (self.end.x() - self.start.x()) * t,
            self.start.y() + (self.end.y() - self.start.y()) * t,
        )

    def _next(self):
        try:
            self.index += 1
            widget = h.gl_widget()
            pos = self._pos(self.index)
            event = QtGui.QMouseEvent(
                QtCore.QEvent.MouseMove,
                pos,
                QtCore.QPointF(widget.mapToGlobal(pos.toPoint())),
                QtCore.Qt.NoButton,
                QtCore.Qt.LeftButton,
                QtCore.Qt.NoModifier,
            )
            QtWidgets.QApplication.sendEvent(widget, event)
            if self.sample:
                self.sample(self.index)
            if self.index < self.moves:
                QtCore.QTimer.singleShot(self.every_ms, self._next)
            else:
                QtCore.QTimer.singleShot(self.hold_ms, self._release)
        except Exception as exc:
            self.error = str(exc)
            self._release()

    def _release(self):
        try:
            if self.sample:
                self.sample(-1)  # held still, button still down
            widget = h.gl_widget()
            QtTest.QTest.mouseRelease(
                widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, self.end
            )
            QtWidgets.QApplication.processEvents()
        except Exception as exc:
            self.error = self.error or str(exc)
        self.done = True


def type_in_box(box, text, enter=True):
    """Click the value box, select what it shows and type, as a person does; Enter at the
    end when asked."""
    QtTest.QTest.mouseClick(box, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, QtCore.QPoint(8, 6))
    QtWidgets.QApplication.processEvents()
    QtTest.QTest.keyClick(box, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
    QtTest.QTest.keyClicks(box, text)
    QtWidgets.QApplication.processEvents()
    if enter:
        QtTest.QTest.keyClick(box, QtCore.Qt.Key_Return)
        QtWidgets.QApplication.processEvents()


def box_near(box, dragger, pixels=150):
    """(ok, detail): the box is shown just next to the arrow's tip on the screen."""
    tip = h.screen_point(dragger.anchor())
    centre = box.geometry().center()
    gap = (centre - tip).manhattanLength()
    return gap <= pixels, "box at %s, arrow tip at %s (%d px apart)" % (
        (centre.x(), centre.y()),
        (tip.x(), tip.y()),
        gap,
    )


def focus_name():
    widget = QtWidgets.QApplication.focusWidget()
    if widget is None:
        return None
    return widget.objectName() or widget.metaObject().className()


def cut_nodes():
    from sciforge import cut_preview

    return cut_preview.find()


def scene_children():
    return Gui.ActiveDocument.ActiveView.getSceneGraph().getNumChildren()


def red_material(node):
    """(diffuse rgb, transparency) of the first material in the node, or None."""
    from pivy import coin

    for i in range(node.getNumChildren()):
        child = node.getChild(i)
        if child.isOfType(coin.SoMaterial.getClassTypeId()):
            rgb = child.diffuseColor[0].getValue()
            return tuple(rgb), child.transparency[0]
    return None


def node_box(node):
    """The bounding box (App.BoundBox) of the first coordinates in the node."""
    from pivy import coin

    for i in range(node.getNumChildren()):
        child = node.getChild(i)
        if child.isOfType(coin.SoCoordinate3.getClassTypeId()):
            box = App.BoundBox()
            for k in range(child.point.getNum()):
                x, y, z = child.point[k].getValue()
                box.add(App.Vector(x, y, z))
            return box
    return None
