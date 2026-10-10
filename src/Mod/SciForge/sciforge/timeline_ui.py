"""The feature timeline: a bar along the bottom of the window, Fusion style.

Playback buttons on the left, one icon per feature of the active body, a
marker after the current step, a settings button on the right. Click
selects, double-click edits, right click rolls back or forward. Rolling back
sets the body's Tip, which is how FreeCAD represents the timeline marker."""

import FreeCAD as App
import FreeCADGui as Gui

from . import timeline_core as core
from . import ui_icon, warn
from .compat import QtCore, QtGui, QtWidgets, Signal

ICON = 24  # feature icon size, as in Fusion's timeline

_dock = None


class _Marker(QtWidgets.QFrame):
    """The history marker. Drag it left or right and drop it between features."""

    def __init__(self, timeline):
        super().__init__()
        self.timeline = timeline
        self.setProperty("role", "marker")
        self.setCursor(QtCore.Qt.SizeHorCursor)
        self.setToolTip("History marker: drag it to roll the design back or forward")
        self._guide = None

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._guide = QtWidgets.QFrame(self.timeline._inner)
            self._guide.setStyleSheet("background: #6fb7f0;")
            self._guide.resize(2, self.height())
            self._guide.show()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._guide is not None:
            x = self.timeline._inner.mapFromGlobal(event.globalPosition().toPoint()).x()
            self._guide.move(x, self.y())
            event.accept()

    def mouseReleaseEvent(self, event):
        if self._guide is None:
            return
        self._guide.deleteLater()
        self._guide = None
        try:
            self.timeline.drop_marker(event.globalPosition().toPoint())
        except Exception as exc:
            warn("timeline marker: %s" % exc)
        event.accept()


class _ItemButton(QtWidgets.QToolButton):
    doubleClicked = Signal()

    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit()
        event.accept()


def _snapshot():
    """(body, features, tip_name) for the active body, or (None, [], None)."""
    try:
        body = Gui.ActiveDocument.ActiveView.getActiveObject("pdbody")
    except Exception:
        body = None
    if body is None:
        return None, [], None
    features = [
        {"name": o.Name, "label": o.Label, "type_id": _type_id(o)}
        for o in body.Group
        if o.TypeId != "App::Origin"
    ]
    tip = body.Tip.Name if getattr(body, "Tip", None) else None
    return body, features, tip


def _type_id(obj):
    """SciForge's own Python features report "SciForge::<Type>" so the timeline knows them."""
    kind = getattr(obj, "SciForgeType", "")
    return "SciForge::" + kind if kind else obj.TypeId


def _select(body, name):
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(body.Document.Name, name)


def _edit(body, name):
    from . import taskui

    taskui.edit_object(body.Document.getObject(name))  # the feature's SciForge dialog


def _set_tip(body, target_name, label):
    doc = body.Document
    target = doc.getObject(target_name)
    if target is None:
        return
    doc.openTransaction("SciForge: %s" % label)
    body.Tip = target
    doc.recompute()
    doc.commitTransaction()


class TimelineWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SciForgeTimeline")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self._sig = None
        self._body = None
        self._items = []
        self._buttons = []

        outer = QtWidgets.QHBoxLayout(self)
        outer.setContentsMargins(8, 3, 8, 3)
        outer.setSpacing(2)
        for icon, where, tip in (
            ("tl_start", "start", "Go to beginning"),
            ("tl_prev", "prev", "Step back"),
            ("tl_play", "play", "Play the history"),
            ("tl_next", "next", "Step forward"),
            ("tl_end", "end", "Go to end"),
        ):
            outer.addWidget(self._tool(icon, tip, lambda _=False, w=where: self.step(w), 18))
        outer.addSpacing(16)

        self._scroll = QtWidgets.QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self._scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self._scroll.setFixedHeight(ICON + 14)
        self._inner = QtWidgets.QWidget()
        self._row = QtWidgets.QHBoxLayout(self._inner)
        self._row.setContentsMargins(0, 0, 0, 0)
        self._row.setSpacing(2)
        self._scroll.setWidget(self._inner)
        outer.addWidget(self._scroll, 1)
        outer.addWidget(self._tool("tl_settings", "Timeline settings", self._settings, 18))

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(400)
        self._timer.timeout.connect(self.refresh)
        self._play_timer = QtCore.QTimer(self)
        self._play_timer.setInterval(450)
        self._play_timer.timeout.connect(self._play_step)

    def _tool(self, icon, tip, slot, size):
        button = QtWidgets.QToolButton()
        button.setIcon(ui_icon(icon))
        button.setIconSize(QtCore.QSize(size, size))
        button.setToolTip(tip)
        button.setAutoRaise(True)
        button.clicked.connect(slot)
        return button

    def start(self):
        self.refresh()
        self._timer.start()

    def stop(self):
        self._timer.stop()
        self._play_timer.stop()

    def refresh(self):
        try:
            body, features, tip = _snapshot()
            items = core.build_items(features, tip)
            sig = core.signature(items, body.Name if body else None)
        except Exception as exc:  # e.g. an object deleted mid-read
            warn("timeline refresh skipped: %s" % exc)
            return
        if sig == self._sig:
            return
        self._sig = sig
        self._body = body
        self._items = items
        self._rebuild()

    def titles(self):
        """Feature titles in timeline order ("Sketch 1", "Extrude 1", ...); used by tests."""
        return [item.title for item in self._items]

    def _clear(self):
        while self._row.count():
            entry = self._row.takeAt(0)
            widget = entry.widget()
            if widget is not None:
                widget.deleteLater()

    def _rebuild(self):
        self._clear()
        if self._body is None:
            hint = QtWidgets.QLabel("No active design. Use Create Sketch to begin.")
            hint.setStyleSheet("color: #c3cad4;")
            self._row.addWidget(hint)
            self._row.addStretch(1)
            return
        self._buttons = []
        for item in self._items:
            button = self._item_button(item)
            self._buttons.append(button)
            self._row.addWidget(button)
            if item.state == "tip":
                self._row.addWidget(self._marker())
        if not any(item.state == "tip" for item in self._items):
            self._row.addWidget(self._marker())
        self._row.addStretch(1)

    def _item_button(self, item):
        button = _ItemButton()
        icon = ui_icon(core.icon_for(item.kind))
        if item.state == "rolled_back":
            # Greyed-out icon, like features after Fusion's marker.
            icon = QtGui.QIcon(icon.pixmap(ICON, ICON, QtGui.QIcon.Disabled))
        button.setIcon(icon)
        button.setIconSize(QtCore.QSize(ICON, ICON))
        button.setAccessibleName(item.title)
        button.setProperty("state", item.state)
        button.setToolTip("%s\n%s" % (item.label, item.title))
        button.clicked.connect(lambda _=False, n=item.name: _select(self._body, n))
        button.doubleClicked.connect(lambda n=item.name: _edit(self._body, n))
        button.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        button.customContextMenuRequested.connect(
            lambda pos, b=button, i=item: self._menu(b, i, pos)
        )
        return button

    def _marker(self):
        marker = _Marker(self)
        marker.setFixedSize(6, ICON + 6)
        return marker

    def drop_marker(self, global_pos):
        """Roll the design to where the marker was dropped."""
        slot = sum(
            1 for b in self._buttons if b.mapToGlobal(b.rect().center()).x() < global_pos.x()
        )
        target = core.drop_target(self._items, slot)
        if target and self._body is not None:
            _set_tip(self._body, target, "move history marker")

    def step(self, where):
        if self._body is None:
            return
        if where == "play":
            first = core.step_target(self._items, "start")
            if first:
                _set_tip(self._body, first, "play")
            self._play_timer.start()
            return
        target = core.step_target(self._items, where)
        if target:
            _set_tip(self._body, target, where)

    def _play_step(self):
        try:
            self.refresh()
            target = core.step_target(self._items, "next")
            if self._body is None or target is None:
                self._play_timer.stop()
                return
            _set_tip(self._body, target, "play")
        except Exception as exc:
            self._play_timer.stop()
            warn("timeline play stopped: %s" % exc)

    def _settings(self):
        menu = QtWidgets.QMenu(self)
        hide = menu.addAction("Hide timeline")
        chosen = menu.exec_(QtGui.QCursor.pos())
        if chosen is hide:
            hide_timeline()

    def _menu(self, button, item, pos):
        menu = QtWidgets.QMenu(button)
        edit = menu.addAction("Edit Feature")
        back_target = core.rollback_target(self._items, item.index)
        back = menu.addAction("Roll History Marker Here")
        back.setEnabled(back_target is not None)
        forward = menu.addAction("Roll History Marker to End")
        forward.setEnabled(core.can_roll_forward(self._items))
        chosen = menu.exec_(button.mapToGlobal(pos))
        if chosen is edit:
            _edit(self._body, item.name)
        elif chosen is back and back_target:
            _set_tip(self._body, back_target, "roll back")
        elif chosen is forward:
            _set_tip(self._body, core.last_solid_name(self._items), "roll forward")


def _ensure_dock():
    global _dock
    if _dock is None:
        main = Gui.getMainWindow()
        _dock = QtWidgets.QDockWidget("Timeline", main)
        _dock.setObjectName("SciForgeTimelineDock")
        _dock.setTitleBarWidget(QtWidgets.QWidget())  # no title bar, like Fusion
        _dock.setFeatures(QtWidgets.QDockWidget.NoDockWidgetFeatures)
        _dock.setWidget(TimelineWidget())
        main.addDockWidget(QtCore.Qt.BottomDockWidgetArea, _dock)
    return _dock


def show():
    dock = _ensure_dock()
    dock.show()
    dock.widget().start()


def hide():
    if _dock is not None:
        _dock.widget().stop()
        _dock.hide()


hide_timeline = hide


def toggle():
    dock = _ensure_dock()
    if dock.isVisible():
        hide()
    else:
        show()
