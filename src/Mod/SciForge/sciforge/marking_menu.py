# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion-style right-click marking menu in the 3D view.

A short right click (press and release without dragging) on the 3D view
opens a ring of 8 commands around the cursor plus a list underneath, instead
of FreeCAD's context menu. Slot 1 repeats the last command. The layout is
data in ribbon_config.MARKING_MENU / MARKING_LIST.

While a command's dialog is open, slot 1 is OK and the list starts with Cancel (Fusion
offers both there, so a right click finishes the command without going to the panel).
"""
import math

import FreeCADGui as Gui

from . import recent, registry, ribbon_config as cfg, taskui, ui_icon, warn
from .compat import QtCore, QtGui, QtWidgets
from .ribbon_ui import build_menu, resolve, run

RADIUS = 110
CLICK_SLOP = 6  # pixels the mouse may move and still count as a click

_filters = []
_last_menu = {"widget": None}


class MarkingMenu(QtWidgets.QWidget):
    def __init__(self, center, parent=None):
        super().__init__(parent, QtCore.Qt.Popup | QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.setObjectName("SciForgeMarkingMenu")
        self.setStyleSheet(STYLE)  # before building, so buttons size themselves with it
        self.ensurePolished()
        available = registry.available_commands()
        size = 2 * RADIUS + 200
        self.resize(size, size + 220)
        self.move(center.x() - size // 2, center.y() - size // 2)
        mid = QtCore.QPoint(size // 2, size // 2)
        self.slots = []
        ring = list(cfg.MARKING_MENU)
        in_command = _dialog_open()
        if in_command:
            ring[0] = cfg.item("OK", "__ok__", "finish_sketch")
        for i, entry in enumerate(ring):
            angle = math.radians(90 - 45 * i)  # N first, clockwise
            pos = mid + QtCore.QPoint(int(RADIUS * math.cos(angle)), int(-RADIUS * math.sin(angle)))
            self.slots.append(self._slot(entry, pos, available))
        listing = build_menu(self, cfg.MARKING_LIST, available)
        if in_command:
            first = listing.actions()[0] if listing.actions() else None
            cancel = listing.addAction(ui_icon("cancel"), "Cancel\tEsc")
            cancel.setEnabled(taskui.dialog_button("reject") is not None)
            cancel.triggered.connect(lambda *_: taskui.press_dialog_button("reject"))
            if first is not None:
                listing.insertAction(first, cancel)  # moves it to the top
        self.list = QtWidgets.QListWidget(self)
        self.list.setObjectName("SciForgeMarkingList")
        self.list.setFixedWidth(200)
        for action in listing.actions():
            if action.isSeparator():
                continue
            row = QtWidgets.QListWidgetItem(action.icon(), action.text().replace("\t", "    "))
            row.setData(QtCore.Qt.UserRole, action)
            if not action.isEnabled():
                row.setFlags(QtCore.Qt.NoItemFlags)
            self.list.addItem(row)
        self.list.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        row_height = max(self.list.sizeHintForRow(0), 24) if self.list.count() else 24
        self.list.setFixedHeight(self.list.count() * row_height + 8)
        self.list.move(mid.x() - 100, mid.y() + RADIUS + 34)
        self.list.itemClicked.connect(self._list_clicked)
        self._listing = listing
        self._shape(mid)
        _last_menu["widget"] = self

    def _shape(self, mid):
        """Cut the window to the ring, the buttons and the list: no rectangle behind
        them, without needing a compositor for transparency."""
        region = QtGui.QRegion(
            QtCore.QRect(
                mid.x() - RADIUS - 2, mid.y() - RADIUS - 2, 2 * RADIUS + 4, 2 * RADIUS + 4
            ),
            QtGui.QRegion.Ellipse,
        )
        for child in self.slots + [self.list]:
            region = region.united(QtGui.QRegion(child.geometry().adjusted(-1, -1, 1, 1)))
        self.setMask(region)

    def _slot(self, entry, pos, available):
        button = QtWidgets.QToolButton(self)
        button.setObjectName("SciForgeMarkingSlot")
        label = entry["label"]
        if entry["command"] == "__ok__":
            enabled = taskui.dialog_button("accept") is not None
            button.clicked.connect(lambda *_: self._press("accept"))
        else:
            if entry["command"] == "__repeat__":
                last = recent.last()
                label = "Repeat " + last[2] if last else "Repeat"
                resolved = (last[0], last[1]) if last else None
            else:
                resolved = resolve(entry["command"], available)
            enabled = resolved is not None
            button.clicked.connect(lambda _=False, r=resolved, l=label: self._run(r, l))
        button.setText(label)
        button.setIcon(ui_icon(entry["icon"]))
        button.setIconSize(QtCore.QSize(20, 20))
        button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        button.ensurePolished()
        button.setFixedSize(button.sizeHint())
        button.move(pos.x() - button.width() // 2, pos.y() - button.height() // 2)
        button.setEnabled(enabled)
        return button

    def _press(self, role):
        self.close()
        QtCore.QTimer.singleShot(0, lambda: taskui.press_dialog_button(role))

    def _run(self, resolved, label):
        self.close()
        QtCore.QTimer.singleShot(0, lambda: run(resolved, label))

    def _list_clicked(self, row):
        action = row.data(QtCore.Qt.UserRole)
        if action is None or not action.isEnabled():
            self.close()
            return
        # Hidden, not closed: closing deletes the menu and the row's action with it, and
        # Qt then silently drops the delayed action.trigger (no list row ever ran).
        self.hide()

        def go():
            try:
                action.trigger()
            except Exception as exc:
                warn("marking menu: %s" % exc)
            try:
                self.close()
            except RuntimeError:
                pass

        QtCore.QTimer.singleShot(0, go)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        mid = QtCore.QPointF(self.width() / 2, (self.height() - 220) / 2)
        painter.setPen(QtGui.QPen(QtGui.QColor("#56606f"), 1.5))
        painter.setBrush(QtGui.QColor("#30363f"))
        painter.drawEllipse(mid, RADIUS, RADIUS)
        painter.setBrush(QtGui.QColor("#3b4453"))
        painter.drawEllipse(mid, 6, 6)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)


STYLE = """
#SciForgeMarkingMenu QToolButton#SciForgeMarkingSlot { background: #454f61; color: #f5f5f5;
    border: 1px solid #56606f; border-radius: 3px; padding: 4px 8px; }
#SciForgeMarkingMenu QToolButton#SciForgeMarkingSlot:hover { background: #56647a; }
#SciForgeMarkingMenu QToolButton#SciForgeMarkingSlot:disabled { color: #7d8593; }
#SciForgeMarkingMenu QListWidget#SciForgeMarkingList { background: #454f61; color: #f5f5f5;
    border: 1px solid #56606f; }
#SciForgeMarkingMenu QListWidget#SciForgeMarkingList::item { height: 24px; padding-left: 4px; }
#SciForgeMarkingMenu QListWidget#SciForgeMarkingList::item:hover { background: #56647a; }
"""


def _dialog_open():
    try:
        return bool(Gui.Control.activeDialog())
    except Exception:
        return False


def open_at(global_pos):
    menu = MarkingMenu(global_pos, Gui.getMainWindow())
    menu.show()
    menu.raise_()
    return menu


def _open_for_state(global_pos, view_widget=None):
    """Fusion: inside a sketch the right click offers the sketch's own tools. Decided here,
    at the click, so it does not depend on which of the two right-click filters on the 3D
    view runs first: Qt runs the filter installed last first, and this part filter was
    installed again after switching to another program and back while a sketch was open
    (Luca saw the part menu in a sketch). Only in the view of the open sketch: another
    design's view keeps the part menu."""
    try:
        from . import sketch_mode

        session = sketch_mode.current()
        if (
            session is not None
            and session.gl is not None
            and (view_widget is None or sketch_mode._same(view_widget, session.gl))
        ):
            from . import sketch_marking

            return sketch_marking.open_at(global_pos)
    except Exception as exc:
        warn("marking menu: %s" % exc)
    return open_at(global_pos)


class _RightClickFilter(QtCore.QObject):
    """Turns a short right click on the 3D view into the marking menu."""

    def __init__(self):
        super().__init__()
        self.pressed_at = None

    def eventFilter(self, obj, event):
        try:
            kind = event.type()
            if kind == QtCore.QEvent.MouseButtonPress and event.button() == QtCore.Qt.RightButton:
                self.pressed_at = event.globalPosition().toPoint()
                return True
            if kind == QtCore.QEvent.MouseButtonRelease and event.button() == QtCore.Qt.RightButton:
                start, self.pressed_at = self.pressed_at, None
                pos = event.globalPosition().toPoint()
                if start is not None and (pos - start).manhattanLength() <= CLICK_SLOP:
                    _open_for_state(pos, obj)
                return True
            if kind == QtCore.QEvent.ContextMenu:
                return True  # FreeCAD's own context menu is replaced
        except Exception as exc:
            warn("marking menu: %s" % exc)
        return False


def _view_widgets():
    area = Gui.getMainWindow().findChild(QtWidgets.QMdiArea)
    if area is None:
        return []
    found = []
    for sub in area.subWindowList():
        found.extend(
            w
            for w in sub.findChildren(QtWidgets.QWidget)
            if w.metaObject().className() == "QOpenGLWidget"
        )
    return found


_watch = {"area": None, "filter": None}


def enable():
    """Install on every 3D view, now and for views opened later."""
    if _watch["filter"] is None:
        _watch["filter"] = _RightClickFilter()
    _install()
    area = Gui.getMainWindow().findChild(QtWidgets.QMdiArea)
    if area is not None and _watch["area"] is None:
        area.subWindowActivated.connect(lambda *_: _install())
        _watch["area"] = area


def _install():
    if _watch["filter"] is None:
        return
    try:
        widgets = _view_widgets()
    except RuntimeError:
        return
    for widget in widgets:
        try:
            if widget not in _filters:
                widget.installEventFilter(_watch["filter"])
                _filters.append(widget)
        except RuntimeError:
            # The view of a design that is being closed (Qt deletes it while the next view
            # becomes active): a traceback was printed when a design was closed and another
            # opened.
            pass
    # An open sketch keeps its own filter in front (it closes the dimension box on a press):
    # installing this one again above moved it behind.
    try:
        from . import sketch_mode

        session = sketch_mode.current()
        if session is not None and session.gl is not None and session.filter is not None:
            session.gl.installEventFilter(session.filter)
    except Exception as exc:
        warn("marking menu: %s" % exc)


def disable():
    for widget in _filters:
        try:
            widget.removeEventFilter(_watch["filter"])
        except RuntimeError:
            pass
    _filters.clear()
    _watch["filter"] = None
