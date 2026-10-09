# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion-style right-click marking menu in the 3D view.

A short right click (press and release without dragging) on the 3D view
opens a ring of 8 commands around the cursor plus a list underneath, instead
of FreeCAD's context menu. Slot 1 repeats the last command. The layout is
data in ribbon_config.MARKING_MENU / MARKING_LIST.
"""
import math

import FreeCADGui as Gui

from . import recent, registry, ribbon_config as cfg, ui_icon, warn
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
        for i, entry in enumerate(cfg.MARKING_MENU):
            angle = math.radians(90 - 45 * i)  # N first, clockwise
            pos = mid + QtCore.QPoint(int(RADIUS * math.cos(angle)), int(-RADIUS * math.sin(angle)))
            self.slots.append(self._slot(entry, pos, available))
        listing = build_menu(self, cfg.MARKING_LIST, available)
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
        if entry["command"] == "__repeat__":
            last = recent.last()
            label = "Repeat " + last[2] if last else "Repeat"
            resolved = (last[0], last[1]) if last else None
        else:
            label = entry["label"]
            resolved = resolve(entry["command"], available)
        button.setText(label)
        button.setIcon(ui_icon(entry["icon"]))
        button.setIconSize(QtCore.QSize(20, 20))
        button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        button.ensurePolished()
        button.setFixedSize(button.sizeHint())
        button.move(pos.x() - button.width() // 2, pos.y() - button.height() // 2)
        button.setEnabled(resolved is not None)
        button.clicked.connect(lambda _=False, r=resolved, l=label: self._run(r, l))
        return button

    def _run(self, resolved, label):
        self.close()
        QtCore.QTimer.singleShot(0, lambda: run(resolved, label))

    def _list_clicked(self, row):
        action = row.data(QtCore.Qt.UserRole)
        self.close()
        if action is not None and action.isEnabled():
            QtCore.QTimer.singleShot(0, action.trigger)

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


def open_at(global_pos):
    menu = MarkingMenu(global_pos, Gui.getMainWindow())
    menu.show()
    menu.raise_()
    return menu


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
                    open_at(pos)
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
    for widget in _view_widgets():
        if widget not in _filters:
            widget.installEventFilter(_watch["filter"])
            _filters.append(widget)


def disable():
    for widget in _filters:
        try:
            widget.removeEventFilter(_watch["filter"])
        except RuntimeError:
            pass
    _filters.clear()
    _watch["filter"] = None
