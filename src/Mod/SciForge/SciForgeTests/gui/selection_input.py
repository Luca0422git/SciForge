# SPDX-License-Identifier: LGPL-2.1-or-later
"""Real mouse input for the selection scenarios (scenarios/selection_*.py): box drags
over the 3D view, a long press, the Select Other list, the SELECT ribbon menu.

Everything goes through Qt test events on the real widgets, as a person's mouse would:
SciForge's own event filter, FreeCAD's picking and the dialogs' observers all run.
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import widget_input as w

V = App.Vector
LEFT = QtCore.Qt.LeftButton
NONE = QtCore.Qt.NoModifier
SHIFT = QtCore.Qt.ShiftModifier
CTRL = QtCore.Qt.ControlModifier


def _process():
    QtWidgets.QApplication.processEvents()


def selection_ui():
    from sciforge import selection_ui

    return selection_ui


# -- what is selected ---------------------------------------------------------------------------
def selected():
    """[(object name, (element, ...))] of FreeCAD's selection."""
    return [(s.ObjectName, tuple(s.SubElementNames)) for s in Gui.Selection.getSelectionEx()]


def selected_elements():
    """The element names selected on any object ("Face6", "Edge3"...), as a set."""
    found = set()
    for s in Gui.Selection.getSelectionEx():
        for name in s.SubElementNames:
            found.add(name)
    return found


def selected_objects():
    """Names of objects selected whole (no element)."""
    return [s.ObjectName for s in Gui.Selection.getSelectionEx() if not s.SubElementNames]


def preselected():
    """(object name, element) FreeCAD highlights under the mouse, or None."""
    try:
        pre = Gui.Selection.getPreselection()
        if not pre.ObjectName:
            return None
        subs = tuple(pre.SubElementNames)
        return pre.ObjectName, subs[0] if subs else ""
    except Exception:
        return None


# -- the part's elements by where they are --------------------------------------------------------
def name_map(body=None):
    """Element names of the box 40 x 30 x 10 by position: top, bottom, front (y=0), back,
    left (x=0), right, the top edges (edge_front_top...), the corners."""
    body = body or h.body()
    shape = body.Shape
    names = {}
    for i, face in enumerate(shape.Faces, start=1):
        c = face.CenterOfMass
        if abs(c.z - 10) < 1e-6:
            names["top"] = "Face%d" % i
        elif abs(c.z) < 1e-6:
            names["bottom"] = "Face%d" % i
        elif abs(c.y) < 1e-6:
            names["front"] = "Face%d" % i
        elif abs(c.y - 30) < 1e-6:
            names["back"] = "Face%d" % i
        elif abs(c.x) < 1e-6:
            names["left"] = "Face%d" % i
        elif abs(c.x - 40) < 1e-6:
            names["right"] = "Face%d" % i
    for i, edge in enumerate(shape.Edges, start=1):
        c = edge.CenterOfMass
        if abs(c.z - 10) < 1e-6:
            if abs(c.y) < 1e-6:
                names["edge_front_top"] = "Edge%d" % i
            elif abs(c.y - 30) < 1e-6:
                names["edge_back_top"] = "Edge%d" % i
            elif abs(c.x) < 1e-6:
                names["edge_left_top"] = "Edge%d" % i
            elif abs(c.x - 40) < 1e-6:
                names["edge_right_top"] = "Edge%d" % i
        elif abs(c.z - 5) < 1e-6:  # the vertical edges, by their corner
            if abs(c.x) < 1e-6 and abs(c.y) < 1e-6:
                names["edge_up_front_left"] = "Edge%d" % i
            elif abs(c.x - 40) < 1e-6 and abs(c.y - 30) < 1e-6:
                names["edge_up_back_right"] = "Edge%d" % i
    names["top_edges"] = {
        names.get(k) for k in ("edge_front_top", "edge_back_top", "edge_left_top", "edge_right_top")
    }
    return names


def visible_elements(body=None):
    """Faces and edges of the body that the camera can see (a face whose outward normal
    points toward the camera; an edge of such a face)."""
    body = body or h.body()
    shape = body.Shape
    direction = h.view().getViewDirection()
    faces = set()
    for i, face in enumerate(shape.Faces, start=1):
        u0, u1, v0, v1 = face.ParameterRange
        normal = face.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
        if normal.dot(direction) < -1e-6:
            faces.add("Face%d" % i)
    edges = set()
    for i, edge in enumerate(shape.Edges, start=1):
        for j, face in enumerate(shape.Faces, start=1):
            if "Face%d" % j in faces and any(e.isSame(edge) for e in face.Edges):
                edges.add("Edge%d" % i)
                break
    return faces, edges


# -- box drags -----------------------------------------------------------------------------------
def screen_rect(points, margin=0):
    """The widget pixel rectangle around 3D points (+ margin px): (x0, y0, x1, y1)."""
    xs, ys = [], []
    for p in points:
        q = h.screen_point(p)
        xs.append(q.x())
        ys.append(q.y())
    return min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin


def drag_box(x0, y0, x1, y1, crossing=False, modifiers=NONE, steps=10):
    """Drag a selection box over widget pixels (x0, y0)-(x1, y1): from the left edge for a
    window, from the right edge for a crossing box (Fusion's direction rule)."""
    if crossing:
        start, end = QtCore.QPoint(x1, y0), QtCore.QPoint(x0, y1)
    else:
        start, end = QtCore.QPoint(x0, y0), QtCore.QPoint(x1, y1)
    h.drag(start, end, steps=steps, modifiers=modifiers)
    _process()
    QtTest.QTest.qWait(80)  # the box's selection is applied a moment after the release
    _process()


def box_around(points, margin=12, crossing=False, modifiers=NONE):
    """A box around 3D points, with a margin in pixels."""
    drag_box(*screen_rect(points, margin), crossing=crossing, modifiers=modifiers)


def box_at(point, half=6, crossing=True, modifiers=NONE):
    """A small box (2 * half px) centred on a 3D point."""
    c = h.screen_point(point)
    drag_box(
        c.x() - half,
        c.y() - half,
        c.x() + half,
        c.y() + half,
        crossing=crossing,
        modifiers=modifiers,
    )


def lasso(points_3d, margin=14, crossing=False, modifiers=NONE):
    """A freeform drag around 3D points: along the (padded) screen rectangle's corners,
    from the left for a window, from the right for a crossing selection."""
    x0, y0, x1, y1 = screen_rect(points_3d, margin)
    cx = (x0 + x1) / 2.0
    if crossing:
        corners = [(x1, y0), (x1, y1), (cx, y1 + 8), (x0, y1), (x0, y0), (cx, y0 - 8)]
    else:
        corners = [(x0, y0), (cx, y0 - 8), (x1, y0), (x1, y1), (cx, y1 + 8), (x0, y1)]
    widget = h.gl_widget()
    start = QtCore.QPoint(int(corners[0][0]), int(corners[0][1]))
    h.move(start)
    QtTest.QTest.mousePress(widget, LEFT, modifiers, start)
    last = start
    for x, y in corners[1:] + [corners[0]]:
        target = QtCore.QPoint(int(x), int(y))
        for i in range(1, 5):
            pos = QtCore.QPointF(
                last.x() + (target.x() - last.x()) * i / 4.0,
                last.y() + (target.y() - last.y()) * i / 4.0,
            )
            event = QtGui.QMouseEvent(
                QtCore.QEvent.MouseMove,
                pos,
                QtCore.QPointF(widget.mapToGlobal(pos.toPoint())),
                QtCore.Qt.NoButton,
                LEFT,
                modifiers,
            )
            QtWidgets.QApplication.sendEvent(widget, event)
            _process()
        last = target
    QtTest.QTest.mouseRelease(widget, LEFT, modifiers, last)
    _process()
    QtTest.QTest.qWait(80)
    _process()


def paint(points_3d, modifiers=NONE, steps=6):
    """Drag the pointer along 3D points with the left button down (Paint Selection)."""
    widget = h.gl_widget()
    pts = [h.screen_point(p) for p in points_3d]
    h.move(pts[0])
    QtTest.QTest.mousePress(widget, LEFT, modifiers, pts[0])
    last = pts[0]
    for target in pts[1:]:
        for i in range(1, steps + 1):
            pos = QtCore.QPointF(
                last.x() + (target.x() - last.x()) * i / float(steps),
                last.y() + (target.y() - last.y()) * i / float(steps),
            )
            event = QtGui.QMouseEvent(
                QtCore.QEvent.MouseMove,
                pos,
                QtCore.QPointF(widget.mapToGlobal(pos.toPoint())),
                QtCore.Qt.NoButton,
                LEFT,
                modifiers,
            )
            QtWidgets.QApplication.sendEvent(widget, event)
            _process()
        last = target
    QtTest.QTest.mouseRelease(widget, LEFT, modifiers, last)
    _process()
    QtTest.QTest.qWait(80)
    _process()


def band():
    """SciForge's box widget over the active view (None before the first box)."""
    return h.gl_widget().findChild(QtWidgets.QWidget, selection_ui().BAND_NAME)


def press_and_move(point, dx, dy, modifiers=NONE):
    """Press on a 3D point and move (dx, dy) px with the button held: a box under way.
    Returns the current widget pixel; release_at() ends it."""
    widget = h.gl_widget()
    start = h.screen_point(point)
    h.move(start)
    QtTest.QTest.mousePress(widget, LEFT, modifiers, start)
    pos = start
    for i in range(1, 7):
        pos = QtCore.QPoint(start.x() + dx * i // 6, start.y() + dy * i // 6)
        event = QtGui.QMouseEvent(
            QtCore.QEvent.MouseMove,
            QtCore.QPointF(pos),
            QtCore.QPointF(widget.mapToGlobal(pos)),
            QtCore.Qt.NoButton,
            LEFT,
            modifiers,
        )
        QtWidgets.QApplication.sendEvent(widget, event)
        _process()
    return pos


def release_at(pos, modifiers=NONE):
    QtTest.QTest.mouseRelease(h.gl_widget(), LEFT, modifiers, pos)
    _process()
    QtTest.QTest.qWait(80)
    _process()


# -- the long press (Select Other) -------------------------------------------------------------
def hold(point, modifiers=NONE):
    """Press the left button on a 3D point and keep it down (the next step, after the
    long-press time, finds the Select Other list). Returns the widget pixel."""
    h.uncover(point)
    pos = h.screen_point(point)
    h.move(pos)
    QtTest.QTest.mousePress(h.gl_widget(), LEFT, modifiers, pos)
    _process()
    return pos


def let_go(pos, modifiers=NONE):
    """The button comes up (with the list open, FreeCAD must not select here)."""
    QtTest.QTest.mouseRelease(h.gl_widget(), LEFT, modifiers, pos)
    _process()


def select_other_menu():
    return selection_ui().select_other_menu()


def rows(menu):
    """The row texts of the Select Other list ("" for a separator)."""
    return [a.text() if not a.isSeparator() else "" for a in menu.actions()]


def _action(menu, text):
    for action in menu.actions():
        if action.text() == text:
            return action
    return None


def hover_row(menu, text):
    action = _action(menu, text)
    if action is None:
        h.check("Select Other row %r exists" % text, False, rows(menu))
        return False
    rect = menu.actionGeometry(action)
    for i in range(4):
        QtTest.QTest.mouseMove(menu, QtCore.QPoint(rect.left() + 8 + 6 * i, rect.center().y()))
        _process()
    QtTest.QTest.mouseMove(menu, rect.center())
    _process()
    return True


def click_row(menu, text):
    action = _action(menu, text)
    if action is None:
        h.check("Select Other row %r exists" % text, False, rows(menu))
        return False
    rect = menu.actionGeometry(action)
    QtTest.QTest.mouseMove(menu, rect.center())
    _process()
    QtTest.QTest.mouseClick(menu, LEFT, NONE, rect.center())
    _process()
    QtTest.QTest.qWait(80)
    _process()
    return True


# -- the SELECT ribbon menu -------------------------------------------------------------------
def select_group():
    from sciforge import shell

    ribbon = shell.ribbon()
    if ribbon is None:
        return None
    for button in ribbon.findChildren(QtWidgets.QToolButton):
        if button.isVisible() and button.text().replace("▾", "").strip() == "SELECT":
            return button
    return None


def _menu_entries(menu):
    return [
        (a.text().replace("&", "").split("\t")[0].strip(), a.isEnabled(), a.isChecked())
        for a in menu.actions()
        if not a.isSeparator()
    ]


def choose_select(path):
    """Open the SELECT group's menu and click the entry `path` (["Window Selection"] or
    ["Selection Filters", "Body Faces"]); path None only reads the menu. Returns
    {"ok", "entries": [(text, enabled, checked)], "sub": [(text, enabled, checked)]}."""
    result = {"ok": False, "entries": [], "sub": []}
    button = select_group()
    if button is None:
        h.check("the ribbon has a SELECT group", False)
        return result
    path = list(path or [])

    def pick(tries=0):
        menu = QtWidgets.QApplication.activePopupWidget()
        if not isinstance(menu, QtWidgets.QMenu):
            if tries < 40:
                QtCore.QTimer.singleShot(50, lambda: pick(tries + 1))
            return
        result["entries"] = _menu_entries(menu)
        if not path:
            QtTest.QTest.keyClick(menu, QtCore.Qt.Key_Escape)
            return
        action = None
        for a in menu.actions():
            if a.text().replace("&", "").split("\t")[0].strip() == path[0]:
                action = a
        if action is None or not action.isEnabled():
            QtTest.QTest.keyClick(menu, QtCore.Qt.Key_Escape)
            return
        rect = menu.actionGeometry(action)
        if len(path) == 1:
            _click_in(menu, rect)
            result["ok"] = True
            return
        # A submenu: hover its row, then click inside the submenu once it is open.
        QtTest.QTest.mouseMove(menu, rect.center())
        _process()
        menu.setActiveAction(action)
        _process()

        def pick_sub(tries=0):
            sub = action.menu()
            if sub is None or not sub.isVisible():
                if tries < 40:
                    QtCore.QTimer.singleShot(50, lambda: pick_sub(tries + 1))
                else:
                    QtTest.QTest.keyClick(menu, QtCore.Qt.Key_Escape)
                return
            result["sub"] = _menu_entries(sub)
            target = None
            for a in sub.actions():
                if a.text().replace("&", "").split("\t")[0].strip() == path[1]:
                    target = a
            if target is None or not target.isEnabled():
                QtTest.QTest.keyClick(sub, QtCore.Qt.Key_Escape)
                QtTest.QTest.keyClick(menu, QtCore.Qt.Key_Escape)
                return
            _click_in(sub, sub.actionGeometry(target))
            result["ok"] = True

        QtCore.QTimer.singleShot(80, pick_sub)

    QtCore.QTimer.singleShot(50, pick)
    w.click(button)  # the drop-down runs its own event loop; pick() runs inside it
    _process()
    return result


def _click_in(menu, rect):
    for i in range(5):
        QtTest.QTest.mouseMove(menu, QtCore.QPoint(rect.left() + 10 + 8 * i, rect.center().y()))
    QtTest.QTest.mouseMove(menu, rect.center())
    QtTest.QTest.mouseClick(menu, LEFT, NONE, rect.center())
    _process()
