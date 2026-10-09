"""The feature timeline: a bar along the bottom of the window showing the
active body's features in order. Click selects, double-click edits, right
click rolls back or forward. Rollback sets the body's Tip, which is how
FreeCAD represents it."""

import FreeCAD as App
import FreeCADGui as Gui

from . import timeline_core as core
from . import warn
from .compat import QtCore, QtWidgets, Signal

_STYLES = {
    "done": "QToolButton { padding: 4px 10px; border: 1px solid #888; border-radius: 4px; }",
    "tip": "QToolButton { padding: 4px 10px; border: 2px solid #2d8cf0; border-radius: 4px; font-weight: bold; }",
    "pending": "QToolButton { padding: 4px 10px; border: 1px dashed #888; border-radius: 4px; }",
    "rolled_back": "QToolButton { padding: 4px 10px; border: 1px dashed #aaa; border-radius: 4px; color: #999; font-style: italic; }",
}

_dock = None


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
        {"name": o.Name, "label": o.Label, "type_id": o.TypeId}
        for o in body.Group
        if o.TypeId != "App::Origin"
    ]
    tip = body.Tip.Name if getattr(body, "Tip", None) else None
    return body, features, tip


def _select(body, name):
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(body.Document.Name, name)


def _edit(body, name):
    Gui.ActiveDocument.setEdit(name)


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
        self._sig = None
        self._body = None
        self._items = []

        outer = QtWidgets.QHBoxLayout(self)
        outer.setContentsMargins(6, 2, 6, 2)
        self._scroll = QtWidgets.QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFixedHeight(46)
        self._inner = QtWidgets.QWidget()
        self._row = QtWidgets.QHBoxLayout(self._inner)
        self._row.setContentsMargins(2, 2, 2, 2)
        self._row.setSpacing(6)
        self._scroll.setWidget(self._inner)
        outer.addWidget(self._scroll)

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(400)
        self._timer.timeout.connect(self.refresh)

    def start(self):
        self.refresh()
        self._timer.start()

    def stop(self):
        self._timer.stop()

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

    def _clear(self):
        while self._row.count():
            entry = self._row.takeAt(0)
            widget = entry.widget()
            if widget is not None:
                widget.deleteLater()

    def _rebuild(self):
        self._clear()
        if self._body is None:
            hint = QtWidgets.QLabel("No active design. Use New Design or Create Sketch to begin.")
            self._row.addWidget(hint)
            self._row.addStretch(1)
            return
        for item in self._items:
            button = _ItemButton()
            button.setText(item.title)
            button.setToolTip("%s\n%s" % (item.label, item.type_id))
            button.setStyleSheet(_STYLES[item.state])
            button.clicked.connect(lambda _=False, n=item.name: _select(self._body, n))
            button.doubleClicked.connect(lambda n=item.name: _edit(self._body, n))
            button.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
            button.customContextMenuRequested.connect(
                lambda pos, b=button, i=item: self._menu(b, i, pos)
            )
            self._row.addWidget(button)
        self._row.addStretch(1)

    def _menu(self, button, item, pos):
        menu = QtWidgets.QMenu(button)
        edit = menu.addAction("Edit")
        back_target = core.rollback_target(self._items, item.index)
        back = menu.addAction("Roll back to here")
        back.setEnabled(back_target is not None)
        forward = menu.addAction("Roll forward to end")
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


def toggle():
    dock = _ensure_dock()
    if dock.isVisible():
        hide()
    else:
        show()
