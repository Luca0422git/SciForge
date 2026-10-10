# SPDX-License-Identifier: LGPL-2.1-or-later
"""Real-input helpers for the sketch scenarios (scenarios/sketch*.py), on top of
harness.py: open a ribbon group's drop-down menu and click an entry (also inside a
submenu) with the mouse, click a widget of the sketch palette, read sketch results.

Kept outside scenarios/ because every file there is run as a scenario."""
import FreeCAD as App
import FreeCADGui as Gui

from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h


def _group_widget(title):
    from sciforge import ribbon_ui, shell

    ribbon = shell.ribbon()
    if ribbon is None:
        return None
    page = ribbon.pages.currentWidget()
    for widget in page.findChildren(ribbon_ui.GroupWidget):
        if widget.group["title"] == title and widget.isVisible():
            return widget
    return None


def _find(menu, label):
    """[(menu, action), ...] from `menu` down to the entry `label` (through submenus)."""
    for action in menu.actions():
        text = action.text().split("\t")[0]
        if text == label:
            return [(menu, action)]
        if action.menu() is not None:
            deeper = _find(action.menu(), label)
            if deeper:
                return [(menu, action)] + deeper
    return []


def menu_item(group_title, label):
    """Click the group's name in the ribbon (opens its menu), then click `label` in
    the menu with the mouse, opening submenus on the way. True if it was clicked."""
    group = _group_widget(group_title)
    if group is None:
        h.check("Ribbon group %s is shown" % group_title, False)
        return False
    path = _find(group.menu, label)
    if not path:
        h.check("Menu entry %s > %s exists" % (group_title, label), False)
        return False
    done = {"clicked": False}

    def click(step):
        try:
            menu, action = path[step]
            if not menu.isVisible():
                QtCore.QTimer.singleShot(150, lambda: click(step))
                return
            rect = menu.actionGeometry(action)
            QtTest.QTest.mouseMove(menu, rect.center())
            QtTest.QTest.mouseClick(menu, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, rect.center())
            if step + 1 < len(path):
                QtCore.QTimer.singleShot(400, lambda: click(step + 1))
            else:
                done["clicked"] = True
        except Exception as exc:
            h.check("Menu click %s" % label, False, exc)
            QtWidgets.QApplication.activePopupWidget() and QtWidgets.QApplication.activePopupWidget().close()

    def safety():  # never leave a menu open (it would block the scenario)
        popup = QtWidgets.QApplication.activePopupWidget()
        while popup is not None:
            popup.close()
            popup = QtWidgets.QApplication.activePopupWidget()

    QtCore.QTimer.singleShot(300, lambda: click(0))
    QtCore.QTimer.singleShot(4000, safety)
    group.label.click()  # the menu runs its own loop until it closes
    QtWidgets.QApplication.processEvents()
    h.check("Clicked %s > %s" % (group_title, label), done["clicked"])
    return done["clicked"]


def notifications():
    """Messages FreeCAD put in its notification area (shown to the user as a pop-up
    balloon; they do not reach the Report view the harness watches)."""
    found = []
    for widget in Gui.getMainWindow().findChildren(QtWidgets.QPushButton):
        if widget.metaObject().className() != "Gui::NotificationArea":
            continue
        menu = widget.menu()
        if menu is None:
            continue
        for action in menu.actions():
            tree = getattr(action, "defaultWidget", lambda: None)()
            if isinstance(tree, QtWidgets.QTreeWidget):
                for i in range(tree.topLevelItemCount()):
                    item = tree.topLevelItem(i)
                    found.append(" | ".join(item.text(c) for c in range(item.columnCount())))
    return found


_seen = {"count": None}


def check_notifications(where):
    msgs = notifications()
    if _seen["count"] is None:
        _seen["count"] = 0
    fresh = msgs[: len(msgs) - _seen["count"]] if len(msgs) > _seen["count"] else []
    _seen["count"] = len(msgs)
    return h.check("No FreeCAD notification (pop-up balloon) after %s" % where, not fresh, fresh)


def watched(steps):
    """The steps, each also checking FreeCAD's notification balloons of the step before
    (the harness only reads the Report view), plus a last check at the end."""
    wrapped = []
    previous = ["start"]
    for step in steps:

        def run(step=step):
            check_notifications(previous[0])
            previous[0] = step.__name__
            step()

        run.__name__ = step.__name__
        for attr in ("wait_ms",):
            if hasattr(step, attr):
                setattr(run, attr, getattr(step, attr))
        wrapped.append(run)

    def notifications_at_the_end():
        check_notifications(previous[0])

    wrapped.append(notifications_at_the_end)
    return wrapped


def palette():
    from sciforge import sketch_mode

    session = sketch_mode.current()
    return session.palette if session is not None else None


def palette_click(object_name):
    """Click a widget of the SKETCH PALETTE (a check box or button) with the mouse."""
    pal = palette()
    widget = pal.findChild(QtWidgets.QWidget, object_name) if pal is not None else None
    if widget is None or not widget.isVisible():
        h.check("Palette has %s" % object_name, False)
        return False
    pos = widget.rect().center()
    if isinstance(widget, QtWidgets.QCheckBox):
        pos = QtCore.QPoint(8, widget.height() // 2)  # the box itself
    QtTest.QTest.mouseClick(widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, pos)
    QtWidgets.QApplication.processEvents()
    return True


def type_into(widget, text, enter=True):
    """Click into a field, replace its text by typing, optionally press Enter."""
    QtTest.QTest.mouseClick(widget, QtCore.Qt.LeftButton)
    QtTest.QTest.keyClick(widget, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
    QtTest.QTest.keyClicks(widget, text)
    if enter:
        QtTest.QTest.keyClick(widget, QtCore.Qt.Key_Return)
    QtWidgets.QApplication.processEvents()


def click(point, approach=App.Vector(1.0, 0.6, 0)):
    """Move the mouse towards the 3D point in a few steps (as a hand does: FreeCAD's
    sketch tools pick what is under the pointer from the moves), then click it."""
    for f in (3.0, 1.5, 0.5):
        h.move(h.screen_point(point + approach * f))
    return h.click(point)


def type_text(text, enter=True):
    """Type on the keyboard: the keys go to the widget that has the keyboard focus
    (FreeCAD's on-screen value fields, SciForge's dimension box), like a real keyboard.
    h.press() instead aims at the 3D view and takes the focus from those fields."""
    target = QtWidgets.QApplication.focusWidget() or h.gl_widget()
    QtTest.QTest.keyClicks(target, text)
    if enter:
        target = QtWidgets.QApplication.focusWidget() or target
        QtTest.QTest.keyClick(target, QtCore.Qt.Key_Return)
    QtWidgets.QApplication.processEvents()
    return target


def sides_field():
    """FreeCAD's "Sides" field of the polygon tool (in the panel under the palette)."""
    for widget in Gui.getMainWindow().findChildren(QtWidgets.QWidget):
        if widget.metaObject().className() != "SketcherGui::TaskSketcherTool":
            continue
        labels = [l for l in widget.findChildren(QtWidgets.QLabel) if l.isVisible()]
        for label in labels:
            if label.text().startswith("Sides"):
                buddy = label.buddy()
                if buddy is not None:
                    return buddy
                row = label.parentWidget()
                spins = [s for s in row.findChildren(QtWidgets.QAbstractSpinBox) if s.isVisible()]
                if spins:
                    # the spin box on the same height as the label
                    spins.sort(key=lambda s: abs(s.y() - label.y()))
                    return spins[0]
    return None


def timeline_double_click(title):
    """Double-click the timeline item called `title` (e.g. "Sketch 1")."""
    for widget in QtWidgets.QApplication.allWidgets():
        if (
            isinstance(widget, QtWidgets.QToolButton)
            and widget.accessibleName() == title
            and widget.isVisible()
        ):
            QtTest.QTest.mouseDClick(widget, QtCore.Qt.LeftButton)
            QtWidgets.QApplication.processEvents()
            return True
    h.check("Timeline item %r exists" % title, False)
    return False


def browser_double_click(text):
    """Double-click the browser row whose name is `text`."""
    tree = Gui.getMainWindow().findChild(QtWidgets.QTreeWidget, "SciForgeBrowser")
    if tree is None:
        h.check("Browser exists", False)
        return False
    items = tree.findItems(text, QtCore.Qt.MatchExactly | QtCore.Qt.MatchRecursive, 1)
    if not items:
        h.check("Browser row %r exists" % text, False)
        return False
    item = items[0]
    tree.scrollToItem(item)
    rect = tree.visualItemRect(item)
    pos = QtCore.QPoint(rect.left() + 60, rect.center().y())
    QtTest.QTest.mouseDClick(tree.viewport(), QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, pos)
    QtWidgets.QApplication.processEvents()
    return True


def _point(sketch, geo, pos):
    g = sketch.Geometry[geo]
    if pos == 1:
        return g.StartPoint
    if pos == 2:
        return g.EndPoint
    return g.Center


def dimension_label(sketch, index):
    """Global 3D point where a length dimension's text is drawn (FreeCAD puts it
    LabelDistance away from the measured points, at their middle)."""
    c = sketch.Constraints[index]
    if c.Second >= 0 or c.Second < -2:
        p1, p2 = _point(sketch, c.First, c.FirstPos), _point(sketch, c.Second, c.SecondPos)
    else:
        g = sketch.Geometry[c.First]
        p1, p2 = g.StartPoint, g.EndPoint
    if c.Type == "DistanceX":
        p2 = App.Vector(p2.x, p1.y, 0)
    elif c.Type == "DistanceY":
        p2 = App.Vector(p1.x, p2.y, 0)
    direction = p2 - p1
    if direction.Length < 1e-9:
        return sketch.getGlobalPlacement().multVec(p1)
    direction.normalize()
    normal = App.Vector(-direction.y, direction.x, 0)
    mid = (p1 + p2) * 0.5 + normal * c.LabelDistance + direction * c.LabelPosition
    return sketch.getGlobalPlacement().multVec(mid)


def lines(sketch, construction=False):
    """(index, geometry) of the sketch's line segments (construction ones or not)."""
    return [
        (i, g)
        for i, g in enumerate(sketch.Geometry)
        if g.TypeId == "Part::GeomLineSegment" and bool(sketch.getConstruction(i)) == construction
    ]


def circles(sketch, construction=None):
    return [
        (i, g)
        for i, g in enumerate(sketch.Geometry)
        if g.TypeId == "Part::GeomCircle"
        and (construction is None or bool(sketch.getConstruction(i)) == construction)
    ]


def constraint_types(sketch):
    return [c.Type for c in sketch.Constraints]


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol


def vnear(p, q, tol=1e-6):
    return (App.Vector(p) - App.Vector(q)).Length <= tol
