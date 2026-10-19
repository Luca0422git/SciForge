# SPDX-License-Identifier: LGPL-2.1-or-later
"""The design timeline: a bar along the bottom of the window, like Fusion's.

One row for the whole design (every body, sketch, construction plane and
feature, in the order they were made). Playback buttons on the left, the
history marker after the last active step, a settings button on the right.

  click            select the step (Ctrl/Shift: add to the selection)
  double-click     edit it (the feature's own SciForge dialog)
  drag a step      reorder; a red line and a tooltip say why when it cannot go there
  drag the marker  roll the design back or forward
  right click      Edit Feature, Edit Profile Sketch, Suppress, Roll History Marker
                   Here, Rename, Delete, Find in Browser, Find in Window
  Delete / F2      delete / rename the selected step

Steps in error are red, steps with a warning yellow, with the reason when you
hover them; suppressed steps are struck through. The document work is done by
timeline_ops.py, the layout logic by timeline_core.py."""

import FreeCAD as App
import FreeCADGui as Gui

from . import _remember, components, timeline_core as core
from . import timeline_ops as ops
from . import ui_icon, warn
from .compat import QtCore, QtGui, QtWidgets, Signal
from .inline_edit import InlineEditor

ICON = 24  # step icon size, as in Fusion's timeline
_dock = None

STYLE = """
#SciForgeTimeline QToolButton[role="step"] { background: transparent; border: 1px solid transparent;
    border-radius: 3px; padding: 2px; }
#SciForgeTimeline QToolButton[role="step"]:hover { background: #56647a; }
#SciForgeTimeline QToolButton[role="step"][status="warning"] { background: #6e5c1c;
    border: 1px solid #f2c440; }
#SciForgeTimeline QToolButton[role="step"][status="error"] { background: #74302f;
    border: 1px solid #ff6b6b; }
#SciForgeTimeline QToolButton[role="step"][selected="true"] { background: #2f5d8c;
    border: 1px solid #63b3ff; }
#SciForgeTimeline QFrame[role="marker"] { background: transparent; }
#SciForgeTimeline QFrame[role="drop"] { background: #63b3ff; }
#SciForgeTimeline QFrame[role="group_end"] { background: #8a94a6; border-radius: 1px; }
#SciForgeTimeline QFrame[role="drop"][refused="true"] { background: #ff5c5c; }
#SciForgeTimeline QLineEdit { background: #2a2a2a; border: 1px solid #63b3ff; padding: 1px 3px; }
"""


def _doc():
    return App.ActiveDocument


def _later(fn, *args):
    """Run document work after the current mouse/menu event has finished."""

    def run():
        try:
            fn(*args)
        except ops.TimelineError as exc:
            _tell(str(exc))
        except Exception as exc:
            warn("timeline: %s" % exc)

    QtCore.QTimer.singleShot(0, run)


def _tell(msg):
    from . import commands

    commands.tell(msg)


def _defer(fn, ms=0):
    """Run document work after FreeCAD's signal/event has finished (never inside it)."""

    def run():
        try:
            fn()
        except Exception as exc:
            warn("timeline: %s" % exc)

    QtCore.QTimer.singleShot(ms, run)


def _command_open():
    """A command dialog is open or something is being edited (a sketch, a base feature)."""
    try:
        if Gui.Control.activeDialog():
            return True
        if _base_feature_open():
            return True  # editing a base feature: the marker waits for Finish Base Feature
        gdoc = Gui.ActiveDocument
        return gdoc is not None and gdoc.getInEdit() is not None
    except Exception:
        return False


def _base_feature_open():
    try:
        from . import direct

        return direct.session(_doc()) is not None
    except Exception:
        return False


def _without_history(doc):
    """A design that does not capture history has no timeline (Fusion)."""
    try:
        from . import direct

        return doc is not None and direct.is_direct(doc)
    except Exception:
        return False


def _ready():
    """Fusion ends the command in progress when you use the timeline."""
    from . import commands

    return commands.finish_open_dialog()


class _Marker(QtWidgets.QFrame):
    """The history marker. Drag it left or right and drop it between steps."""

    def __init__(self, timeline):
        super().__init__()
        self.timeline = timeline
        self.setProperty("role", "marker")
        self.setCursor(QtCore.Qt.SizeHorCursor)
        self.setToolTip("History marker: drag it to roll the design back or forward")
        self.setFocusPolicy(QtCore.Qt.ClickFocus)  # Esc drops a drag
        self._guide = None

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        w, h = self.width(), self.height()
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor("#e8e8e8"))
        painter.drawRoundedRect(QtCore.QRectF(w / 2.0 - 1.5, 0, 3, h), 1, 1)
        painter.drawRoundedRect(QtCore.QRectF(0, 0, w, 7), 2, 2)  # the grip
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.setFocus()
            self._guide = QtWidgets.QFrame(self.timeline._inner)
            self._guide.setStyleSheet("background: #6fb7f0;")
            self._guide.resize(2, self.height())
            self._guide.show()
            event.accept()

    def event(self, event):
        if (
            event.type() == QtCore.QEvent.ShortcutOverride
            and event.key() == QtCore.Qt.Key_Escape
            and self._guide is not None
        ):
            event.accept()
            return True
        return super().event(event)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape and self._guide is not None:
            self._guide.deleteLater()  # Esc: the marker stays where it was
            self._guide = None
            event.accept()
            return
        super().keyPressEvent(event)

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
    """One step. Click selects, double-click edits, drag reorders."""

    doubleClicked = Signal()

    def __init__(self, timeline, item):
        super().__init__()
        self.timeline = timeline
        self.item = item
        self.setProperty("role", "step")
        self.setFocusPolicy(QtCore.Qt.ClickFocus)
        self._press = None
        self._dragging = False

    # -- mouse -------------------------------------------------------------------
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._press = event.globalPosition().toPoint()
            self._dragging = False
            self.setFocus()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._press is None:
            return
        pos = event.globalPosition().toPoint()
        try:
            if not self._dragging:
                if (
                    pos - self._press
                ).manhattanLength() < QtWidgets.QApplication.startDragDistance():
                    return
                self._dragging = True
                self.timeline.begin_drag(self)
            self.timeline.drag_to(pos)
        except Exception as exc:
            warn("timeline drag: %s" % exc)
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() != QtCore.Qt.LeftButton or self._press is None:
            super().mouseReleaseEvent(event)
            return
        pos = event.globalPosition().toPoint()
        dragging = self._dragging
        self._press = None
        self._dragging = False
        try:
            if dragging:
                self.timeline.end_drag(pos)
            else:
                self.timeline.clicked(self.item.name, event.modifiers())
        except Exception as exc:
            warn("timeline: %s" % exc)
        event.accept()

    def mouseDoubleClickEvent(self, event):
        self._press = None
        self.doubleClicked.emit()
        event.accept()

    def enterEvent(self, event):
        try:
            self.timeline.hover(self.item)
        except Exception as exc:
            warn("timeline hover: %s" % exc)
        super().enterEvent(event)

    def leaveEvent(self, event):
        try:
            self.timeline.unhover(self.item)
        except Exception:
            pass
        super().leaveEvent(event)

    # -- keys ----------------------------------------------------------------------
    def event(self, event):
        # Delete and F2 belong to the timeline while a step has the focus, Esc while
        # it is being dragged.
        if event.type() == QtCore.QEvent.ShortcutOverride and (
            event.key() in (QtCore.Qt.Key_Delete, QtCore.Qt.Key_Backspace, QtCore.Qt.Key_F2)
            or (event.key() == QtCore.Qt.Key_Escape and self._dragging)
        ):
            event.accept()
            return True
        return super().event(event)

    def keyPressEvent(self, event):
        try:
            if event.key() == QtCore.Qt.Key_Escape and self._press is not None:
                dragging = self._dragging
                self._press = None  # Fusion: Esc drops the drag, nothing moves
                self._dragging = False
                if dragging:
                    self.timeline.cancel_drag()
                return
            if event.key() in (QtCore.Qt.Key_Delete, QtCore.Qt.Key_Backspace):
                self.timeline.delete_selected()
                return
            if event.key() == QtCore.Qt.Key_F2:
                self.timeline.rename(self.item.name)
                return
        except Exception as exc:
            warn("timeline: %s" % exc)
            return
        super().keyPressEvent(event)

    # -- look ---------------------------------------------------------------------
    def paintEvent(self, event):
        super().paintEvent(event)
        item = self.item
        if not (item.suppressed or item.status != "ok"):
            return
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        w, h = self.width(), self.height()
        if item.suppressed:  # struck through, like a step that is switched off
            pen = QtGui.QPen(QtGui.QColor("#c3cad4"), 2)
            painter.setPen(pen)
            painter.drawLine(4, h - 4, w - 4, 4)
        if item.status != "ok":
            color = "#ff5c5c" if item.status == "error" else "#f2c440"
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QColor(color))
            badge = QtGui.QPolygonF(
                [
                    QtCore.QPointF(w - 10, h - 2),
                    QtCore.QPointF(w - 2, h - 2),
                    QtCore.QPointF(w - 6, h - 10),
                ]
            )
            painter.drawPolygon(badge)
        painter.end()


class _UndoWatcher:
    """Document observer: Undo/Redo -> TimelineWidget.after_undo (deferred, so nothing
    runs inside FreeCAD's undo)."""

    def __init__(self, timeline):
        self.timeline = timeline

    def _later(self, doc):
        QtCore.QTimer.singleShot(0, self.timeline.after_undo)

    slotUndoDocument = slotRedoDocument = _later


class _WheelScroll(QtCore.QObject):
    """The mouse wheel scrolls the timeline sideways (it has no vertical scroll)."""

    def __init__(self, scroll):
        super().__init__(scroll)
        self.scroll = scroll

    def eventFilter(self, obj, event):
        try:
            if event.type() == QtCore.QEvent.Wheel:
                delta = event.angleDelta()
                step = delta.y() if abs(delta.y()) >= abs(delta.x()) else delta.x()
                bar = self.scroll.horizontalScrollBar()
                bar.setValue(bar.value() - step)
                return True
        except Exception:
            pass
        return False


class _GroupButton(QtWidgets.QToolButton):
    """A timeline group: one folder for several steps. Click opens or closes it; drag it to
    move the whole group (Fusion moves a group as one item); Esc drops the drag."""

    def __init__(self, timeline, gid, name, members, opened, holds_marker=False):
        super().__init__()
        self.timeline = timeline
        self.gid = gid
        self.name = name
        self.members = members
        self.opened = opened
        self.holds_marker = holds_marker  # the history marker stands inside the group
        self._press = None
        self._dragging = False
        self.setObjectName("SciForgeGroup_" + gid)
        self.setProperty("role", "step")
        self.setFocusPolicy(QtCore.Qt.ClickFocus)  # Esc drops a drag
        self.setIcon(ui_icon("folder"))
        self.setIconSize(QtCore.QSize(ICON, ICON))
        bad = [m for m in members if m.status == "error"]
        warned = [m for m in members if m.status == "warning"]
        self.setProperty("status", "error" if bad else ("warning" if warned else "ok"))
        lines = [name, "%d steps: %s" % (len(members), ", ".join(m.display for m in members))]
        if holds_marker:
            lines.append("The history marker is inside: the group stays open")
        else:
            lines.append(
                "Click to %s the group, drag it to move it" % ("close" if opened else "open")
            )
        for m in bad + warned:
            lines.append("%s: %s" % (m.display, m.message))
        self.setToolTip("\n".join(lines))
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(
            lambda pos: self.timeline._group_menu(self, self.mapToGlobal(pos))
        )

    # -- mouse: a click opens / closes, a drag moves the group ------------------------
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._press = event.globalPosition().toPoint()
            self._dragging = False
            self.setDown(True)
            self.setFocus()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._press is None:
            return
        pos = event.globalPosition().toPoint()
        try:
            if not self._dragging:
                if (
                    pos - self._press
                ).manhattanLength() < QtWidgets.QApplication.startDragDistance():
                    return
                self._dragging = True
                self.setDown(False)
                self.timeline.begin_drag(self)
            self.timeline.drag_to(pos)
        except Exception as exc:
            warn("timeline group drag: %s" % exc)
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() != QtCore.Qt.LeftButton or self._press is None:
            super().mouseReleaseEvent(event)
            return
        pos = event.globalPosition().toPoint()
        dragging = self._dragging
        self._press = None
        self._dragging = False
        self.setDown(False)
        try:
            if dragging:
                self.timeline.end_drag(pos)
            else:
                _later(self.timeline.toggle_group, self.gid)
        except Exception as exc:
            warn("timeline group: %s" % exc)
        event.accept()

    def event(self, event):
        if (
            event.type() == QtCore.QEvent.ShortcutOverride
            and event.key() == QtCore.Qt.Key_Escape
            and self._dragging
        ):
            event.accept()
            return True
        return super().event(event)

    def keyPressEvent(self, event):
        try:
            if event.key() == QtCore.Qt.Key_Escape and self._press is not None:
                dragging = self._dragging
                self._press = None  # Fusion: Esc drops the drag, nothing moves
                self._dragging = False
                self.setDown(False)
                if dragging:
                    self.timeline.cancel_drag()
                return
        except Exception as exc:
            warn("timeline group: %s" % exc)
            return
        super().keyPressEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor("#e8e8e8"))
        w, h = self.width(), self.height()
        if self.opened:  # small triangle: open (down) or closed (right)
            tri = [
                QtCore.QPointF(w - 9, h - 7),
                QtCore.QPointF(w - 3, h - 7),
                QtCore.QPointF(w - 6, h - 3),
            ]
        else:
            tri = [
                QtCore.QPointF(w - 7, h - 9),
                QtCore.QPointF(w - 7, h - 3),
                QtCore.QPointF(w - 3, h - 6),
            ]
        painter.drawPolygon(QtGui.QPolygonF(tri))
        painter.end()


class TimelineWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SciForgeTimeline")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setStyleSheet(STYLE)
        self._sig = None
        self._doc_name = None
        self._timeline = core.build([], {})
        self._items = []
        self._buttons = []
        self._selected = []
        self._drag = None  # (button, drop indicator)
        self._drop_hint = None
        self._editor = None
        self._pushing = False
        self._busy = 0  # a menu, a drag or a rename is in progress
        self._open_groups = set()  # timeline groups shown open
        self._slots = []
        self._undo_watch = None
        self._move_timeline = self._timeline
        self._hover = None  # timeline_hover.HoverLook, made on first use

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
            button = self._tool(icon, tip, lambda _=False, w=where: self.step(w), 18)
            button.setObjectName("SciForgeTimeline_" + where)
            outer.addWidget(button)
        outer.addSpacing(16)

        self._scroll = QtWidgets.QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self._scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        # A long design scrolls sideways: a thin bar under the icons (the default one
        # covered their lower half) and the mouse wheel. The height stays as it was: the
        # 3D view's size (and so where a click lands) must not change.
        self._scroll.setFixedHeight(ICON + 14)
        self._scroll.horizontalScrollBar().setStyleSheet("QScrollBar:horizontal { height: 6px; }")
        self._wheel = _WheelScroll(self._scroll)
        self._scroll.viewport().installEventFilter(self._wheel)
        self._shown_end = None  # (steps, marker) last scrolled into view
        self._follow = 0  # rebuilds whose marker is still to be scrolled into view
        self._scroll.horizontalScrollBar().rangeChanged.connect(self._range_changed)
        self._inner = QtWidgets.QWidget()
        self._row = QtWidgets.QHBoxLayout(self._inner)
        self._row.setContentsMargins(0, 0, 0, 0)
        self._row.setSpacing(3)
        self._scroll.setWidget(self._inner)
        outer.addWidget(self._scroll, 1)
        settings = self._tool("tl_settings", "Timeline settings", self._settings, 18)
        settings.setObjectName("SciForgeTimeline_settings")
        outer.addWidget(settings)

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
        try:
            ops.install_guard(_defer)
            if self._undo_watch is None:
                self._undo_watch = _UndoWatcher(self)
                App.addDocumentObserver(self._undo_watch)
        except Exception as exc:
            warn("timeline: %s" % exc)
        self.refresh()
        self._timer.start()

    def stop(self):
        self._timer.stop()
        self._play_timer.stop()
        self.unhover()
        ops.remove_guard()
        if self._undo_watch is not None:
            try:
                App.removeDocumentObserver(self._undo_watch)
            except Exception:
                pass
            self._undo_watch = None

    def after_undo(self):
        """Fusion recomputes after Undo/Redo; FreeCAD puts the shapes back but leaves
        steps that were red (or waiting) in that state until the next recompute."""
        try:
            doc = _doc()
            if doc is None or Gui.Control.activeDialog():
                return
            gdoc = Gui.ActiveDocument
            if gdoc is not None and gdoc.getInEdit() is not None:
                return
            stale = False
            for obj, _body in ops.steps(doc):
                state = list(obj.State)
                if "Invalid" in state or "Touched" in state or "Error" in state:
                    stale = True
                    break
            if stale:
                ops.recompute(doc)
            ops.show_marker_state(doc)  # sketches/planes drawn as the marker says
            self.refresh(force=True)
        except Exception as exc:
            warn("timeline after undo: %s" % exc)

    # -- reading the design --------------------------------------------------------
    def refresh(self, force=False):
        if self._busy or self._drag is not None or self._editor is not None:
            return  # never pull the widgets from under the mouse or the keyboard
        self._follow_history_mode()
        try:
            doc = _doc()
            active = None
            if doc is None:
                timeline, name = core.build([], {}), None
            else:
                timeline, name = ops.timeline(doc, deps=False), doc.Name
                active = components.active_component(doc)
            # Fusion: with a component active, the timeline shows that component's
            # features (and those of the components inside it); the root shows all.
            sig = core.signature(timeline, (name, active.Name if active is not None else None))
        except Exception as exc:  # e.g. an object deleted mid-read
            _remember("info", "timeline refresh skipped: %s" % exc)
            return
        self._sync_selection()
        if sig == self._sig and not force:
            return
        self._sig = sig
        self._doc_name = name
        self._timeline = timeline
        self._items = list(timeline.items)
        self._hidden = _hidden_steps(doc, timeline, active)
        self._selected = [n for n in self._selected if timeline.find(n) is not None]
        self._rebuild()

    def _follow_history_mode(self):
        """Fusion: a design that does not capture history has no timeline at the bottom;
        it comes back with Capture Design History (or another design that has one)."""
        try:
            dock = _dock
            if dock is None or dock.widget() is not self:
                return
            without = _without_history(_doc())
            if without and dock.isVisible():
                self._hidden_for_history = True
                dock.hide()
            elif not without and getattr(self, "_hidden_for_history", False):
                self._hidden_for_history = False
                dock.show()
        except Exception as exc:
            _remember("info", "timeline history mode: %s" % exc)

    @property
    def _body(self):
        """The document of the timeline (kept for older callers)."""
        return _doc()

    def titles(self):
        """Step names in timeline order ("Sketch 1", "Extrude 1", ...) as shown: with a
        component active, only its steps; used by tests."""
        hidden = getattr(self, "_hidden", set())
        return [item.display for item in self._items if item.name not in hidden]

    def all_titles(self):
        """Every step's name, also those the active component hides."""
        return [item.display for item in self._items]

    def items(self):
        return list(self._items)

    def button(self, name):
        for b in self._buttons:
            if b.item.name == name:
                return b
        return None

    def marker(self):
        # The marker of the latest rebuild: the old row's widgets wait for deleteLater,
        # which Qt runs only back in the event loop that asked for it, so during a busy
        # moment they are still children here and the first marker found could be the
        # old one (the view then "followed" to where the marker had been).
        current = getattr(self, "_current_marker", None)
        if current is not None:
            try:
                if self._row.indexOf(current) >= 0:
                    return current
            except RuntimeError:
                pass  # deleted
        for w in self._inner.findChildren(QtWidgets.QFrame):
            if w.property("role") == "marker" and not w.isHidden():
                return w
        return None

    def _clear(self):
        self.unhover()  # the step under the mouse may change or go
        self._cancel_editor()
        while self._row.count():
            entry = self._row.takeAt(0)
            widget = entry.widget()
            if widget is not None:
                if widget.hasFocus():
                    # (hidden with the focus, Qt hands it to the next widget in the Tab
                    # order, which may be in another tab: that tab came to the front)
                    widget.clearFocus()
                widget.hide()
                widget.deleteLater()

    def _rebuild(self):
        self._clear()
        self._buttons = []
        if self._doc_name is None or not self._items:
            text = (
                "No design open. Use New Design to begin."
                if self._doc_name is None
                else "Your design's history appears here. Create a sketch to begin."
            )
            hint = QtWidgets.QLabel(text)
            hint.setStyleSheet("color: #c3cad4;")
            self._row.addWidget(hint)
            self._row.addStretch(1)
            return
        marker = self._timeline.marker
        hidden = getattr(self, "_hidden", set())  # steps of other components (Fusion)
        # (widget, slot left of it, slot right of it) for drops and the marker
        self._slots = []
        placed = [False]

        def marker_before(index):
            """The marker stands before the first shown step at or after its slot."""
            if not placed[0] and index >= marker:
                self._row.addWidget(self._make_marker())
                placed[0] = True

        for seg in core.segments(self._timeline, self._open_groups):
            if seg[0] == "step":
                item = seg[1]
                if item.name in hidden:
                    continue
                marker_before(item.index)
                self._add_step(item)
                continue
            _kind, gid, name, members, opened = seg
            shown = [m for m in members if m.name not in hidden]
            if not shown:
                continue
            start, end = members[0].index, members[-1].index + 1
            marker_before(shown[0].index)
            holds = core.marker_in_group(self._timeline, gid)
            header = _GroupButton(self, gid, name, shown, opened, holds)
            self._row.addWidget(header)
            self._slots.append((header, start, start if opened else end))
            if not opened:
                continue
            for item in shown:
                if item is not shown[0]:
                    marker_before(item.index)
                self._add_step(item)
            cap = QtWidgets.QFrame()
            cap.setProperty("role", "group_end")
            cap.setFixedSize(3, ICON + 4)
            self._row.addWidget(cap)
        if not placed[0]:
            self._row.addWidget(self._make_marker())
        if hidden:
            note = QtWidgets.QLabel("%d steps of other components" % len(hidden))
            note.setObjectName("SciForgeTimelineHiddenNote")
            note.setStyleSheet("color: #8a94a6; padding-left: 8px;")
            note.setToolTip(
                "The timeline shows the active component's steps. Activate the design's "
                "top row in the browser to see every step."
            )
            self._row.addWidget(note)
        self._row.addStretch(1)
        self._update_selection_look()
        # Fusion keeps the history marker in view: a new step (or a marker move) on a
        # long design showed the start of the row with the new step off-screen.
        where = (len(self._items), marker)
        if where != self._shown_end:
            self._shown_end = where
            # Once the new row is laid out (its width changes the scroll range).
            self._follow += 1
            QtCore.QTimer.singleShot(60, self._marker_into_view)
            QtCore.QTimer.singleShot(1500, self._stop_following)

    def _stop_following(self):
        self._follow = max(0, self._follow - 1)

    def _range_changed(self, *_args):
        if self._follow:
            self._marker_into_view()

    def _marker_into_view(self):
        try:
            marker = self.marker()
            if marker is not None:
                # The row's new positions first: Qt lays it out later, by a queued event;
                # when that came after this timer (a busy moment, a long design), the view
                # scrolled to where the marker had been and stayed there.
                QtWidgets.QApplication.sendPostedEvents(self._inner, QtCore.QEvent.LayoutRequest)
                self._row.activate()
                self._scroll.ensureWidgetVisible(marker, 60, 0)
        except RuntimeError:
            pass  # rebuilt meanwhile

    def _add_step(self, item):
        button = self._item_button(item)
        self._buttons.append(button)
        self._row.addWidget(button)
        self._slots.append((button, item.index, item.index + 1))

    def _item_button(self, item):
        button = _ItemButton(self, item)
        icon = ui_icon(item.icon)
        if item.state == "rolled_back" or item.suppressed:
            # Greyed-out icon, like steps after Fusion's marker or switched off.
            icon = QtGui.QIcon(icon.pixmap(ICON, ICON, QtGui.QIcon.Disabled))
        button.setIcon(icon)
        button.setIconSize(QtCore.QSize(ICON, ICON))
        button.setObjectName("SciForgeStep_" + item.name)
        button.setAccessibleName(item.display)
        button.setProperty("state", item.state)
        button.setProperty("status", item.status)
        button.setProperty("suppressed", "true" if item.suppressed else "false")
        button.setToolTip(core.tooltip(item))
        button.doubleClicked.connect(lambda n=item.name: self.edit(n))
        button.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        button.customContextMenuRequested.connect(
            lambda pos, b=button: self._menu(b, b.mapToGlobal(pos))
        )
        return button

    def _make_marker(self):
        marker = _Marker(self)
        marker.setFixedSize(8, ICON + 8)
        self._current_marker = marker
        return marker

    # -- selection -----------------------------------------------------------------
    def clicked(self, name, modifiers=QtCore.Qt.NoModifier):
        names = [i.name for i in self._items]
        if modifiers & QtCore.Qt.ShiftModifier and self._selected:
            a, b = names.index(self._selected[-1]), names.index(name)
            lo, hi = min(a, b), max(a, b)
            chosen = list(self._selected) + [n for n in names[lo : hi + 1]]
            self._selected = list(dict.fromkeys(chosen))
        elif modifiers & QtCore.Qt.ControlModifier:
            if name in self._selected:
                self._selected.remove(name)
            else:
                self._selected.append(name)
        else:
            self._selected = [name]
        self._push_selection()
        self._update_selection_look()

    def select(self, names):
        """Select steps (Find in Timeline from the browser); their groups open."""
        hidden = {i.group for i in self._items if i.name in names and i.group}
        if hidden - self._open_groups:
            self._open_groups |= hidden
            self.refresh(force=True)
        self._selected = [n for n in names if self.button(n) is not None]
        self._push_selection()
        self._update_selection_look()
        if self._selected:
            self._scroll.ensureWidgetVisible(self.button(self._selected[0]))

    def selected(self):
        return list(self._selected)

    def _push_selection(self):
        doc = _doc()
        if doc is None:
            return
        self._pushing = True
        try:
            Gui.Selection.clearSelection()
            for n in self._selected:
                if doc.getObject(n) is not None:
                    Gui.Selection.addSelection(doc.Name, n)
        finally:
            self._pushing = False

    def _sync_selection(self):
        """A click elsewhere (empty 3D background...) clears the timeline's selection."""
        if not self._selected:
            return
        try:
            names = {s.ObjectName for s in Gui.Selection.getSelectionEx()}
        except Exception:
            return
        if not names & set(self._selected):
            self._selected = []
            self._update_selection_look()

    def _update_selection_look(self):
        for b in self._buttons:
            on = "true" if b.item.name in self._selected else "false"
            if b.property("selected") != on:
                b.setProperty("selected", on)
                b.style().unpolish(b)
                b.style().polish(b)
                b.update()

    # -- the history marker --------------------------------------------------------
    def _slot_at(self, global_pos):
        """Number of steps left of a screen point (a closed group counts all its steps)."""
        slot = 0
        for widget, _left, right in self._slots:
            if widget.mapToGlobal(widget.rect().center()).x() < global_pos.x():
                slot = max(slot, right)
        return slot

    def drop_marker(self, global_pos):
        """Roll the design to where the marker was dropped."""
        doc = _doc()
        if doc is None or not _ready():
            return
        tips, before = core.marker_for_slot(self._timeline, self._slot_at(global_pos))
        if ops.roll(doc, tips, "Move History Marker", before):
            self.refresh(force=True)

    def step(self, where):
        try:
            doc = _doc()
            if doc is None or not _ready():
                return
            self.refresh()
            if where == "play":
                first = core.tips_for_step(self._timeline, "start")
                if first:
                    ops.roll(doc, first, "Play")
                self._play_timer.start()
                return
            tips = core.tips_for_step(self._timeline, where)
            if tips:
                ops.roll(doc, tips, "Step %s" % where)
                self.refresh(force=True)
        except Exception as exc:
            warn("timeline %s: %s" % (where, exc))

    def _play_step(self):
        try:
            if _command_open():
                # Fusion: starting a command stops the playback; rolling the design
                # under an open dialog would have committed its preview.
                self._play_timer.stop()
                return
            self.refresh()
            doc = _doc()
            tips = core.tips_for_step(self._timeline, "next") if doc else None
            if tips is None:
                self._play_timer.stop()
                return
            ops.roll(doc, tips, "Play")
        except Exception as exc:
            self._play_timer.stop()
            warn("timeline play stopped: %s" % exc)

    def roll_here(self, name):
        doc = _doc()
        item = self._timeline.find(name)
        if doc is None or item is None or not _ready():
            return
        tips, before = core.marker_for_slot(self._timeline, item.index + 1)
        ops.roll(doc, tips, "Roll History Marker Here", before)
        self.refresh(force=True)

    def roll_to_end(self):
        doc = _doc()
        if doc is None or not _ready():
            return
        ops.roll_to_end(doc)
        self.refresh(force=True)

    # -- reordering ----------------------------------------------------------------
    # -- hover: light up what a step made ---------------------------------------------
    def hover(self, item):
        """Fusion: the mouse over a step lights up its faces (sketch: its curves) in the
        3D view. Not for steps after the marker or switched off (they add nothing)."""
        if self._drag is not None or self._busy or item.state != "done" or item.suppressed:
            self.unhover()
            return
        obj = self._object(item.name)
        if obj is None:
            return
        from .timeline_hover import HoverLook

        if self._hover is None:
            self._hover = HoverLook()
        self._hover.show(obj)

    def unhover(self, item=None):
        if self._hover is not None and (item is None or self._hover.name == item.name):
            self._hover.clear()

    def hovered(self):
        """Name of the step lit up in the 3D view, or None (tests)."""
        return self._hover.name if self._hover is not None else None

    def begin_drag(self, button):
        """A step's button (or a group's header: the whole group) starts being dragged."""
        self.unhover()
        line = QtWidgets.QFrame(self._inner)
        line.setProperty("role", "drop")
        line.resize(3, ICON + 8)
        line.show()
        line.raise_()
        doc = _doc()
        # What each step uses, to know where it may go (read once per drag).
        self._move_timeline = ops.timeline(doc) if doc is not None else self._timeline
        self._drag = (button, line)
        button.setCursor(QtCore.Qt.ClosedHandCursor)

    def _plan(self, button, slot):
        """What dropping the dragged step (or group) at ``slot`` would do."""
        if isinstance(button, _GroupButton):
            return core.plan_group_move(self._move_timeline, button.gid, slot)
        return core.plan_move(self._move_timeline, button.item.name, slot)

    def _drop_x(self, slot):
        if not self._slots:
            return 0
        for widget, left, _right in self._slots:
            if left >= slot:
                return widget.geometry().left() - 2
        return self._slots[-1][0].geometry().right() + 2

    def drag_to(self, global_pos):
        if self._drag is None:
            return
        button, line = self._drag
        slot = self._slot_at(global_pos)
        plan = self._plan(button, slot)
        refused = bool(not plan.ok and plan.reason)
        line.setProperty("refused", "true" if refused else "false")
        line.style().unpolish(line)
        line.style().polish(line)
        line.move(self._drop_x(slot) - 1, 2)
        if refused:
            QtWidgets.QToolTip.showText(global_pos, plan.reason, self)
        else:
            QtWidgets.QToolTip.hideText()

    def cancel_drag(self):
        if self._drag is None:
            return
        button, line = self._drag
        self._drag = None
        try:
            button.unsetCursor()
            line.hide()
            line.deleteLater()
        except RuntimeError:
            pass
        QtWidgets.QToolTip.hideText()

    def end_drag(self, global_pos):
        if self._drag is None:
            return
        button, line = self._drag
        self._drag = None
        button.unsetCursor()
        slot = self._slot_at(global_pos)
        group = button.gid if isinstance(button, _GroupButton) else None
        name = None if group else button.item.name
        doc = _doc()
        plan = self._plan(button, slot)
        if not plan.ok:
            line.deleteLater()
            if plan.reason:
                self._refuse(slot, plan.reason, global_pos)
            return
        line.deleteLater()
        if doc is None or not _ready():
            return
        try:
            if group:
                ops.move_group(doc, group, slot)
            else:
                ops.move(doc, name, slot)
        except ops.TimelineError as exc:
            self._refuse(slot, str(exc), global_pos)
            return
        self.refresh(force=True)
        if name:
            self.select([name])

    def _refuse(self, slot, reason, global_pos):
        """Fusion: a red mark where the step cannot go, and why."""
        hint = QtWidgets.QFrame(self._inner)
        hint.setProperty("role", "drop")
        hint.setProperty("refused", "true")
        hint.setToolTip(reason)
        hint.resize(3, ICON + 8)
        hint.move(self._drop_x(slot) - 1, 2)
        hint.show()
        self._drop_hint = (hint, reason)
        QtWidgets.QToolTip.showText(global_pos, reason, self)
        _remember("info", "timeline: %s" % reason)

        def clear():
            try:
                hint.deleteLater()
            except RuntimeError:
                pass
            if self._drop_hint and self._drop_hint[0] is hint:
                self._drop_hint = None

        QtCore.QTimer.singleShot(2500, clear)

    def refusal(self):
        """The reason of the last refused move while it is shown (tests)."""
        return self._drop_hint[1] if self._drop_hint else ""

    def move_group(self, gid, slot):
        """Programmatic move of a whole group (same rules as dragging its header). Returns
        the refusal or ''."""
        doc = _doc()
        try:
            ops.move_group(doc, gid, slot)
        except ops.TimelineError as exc:
            return str(exc)
        self.refresh(force=True)
        return ""

    def move_step(self, name, slot):
        """Programmatic move (same rules as dragging). Returns the refusal or ''."""
        doc = _doc()
        try:
            ops.move(doc, name, slot)
        except ops.TimelineError as exc:
            return str(exc)
        self.refresh(force=True)
        return ""

    # -- actions on steps ---------------------------------------------------------
    def _object(self, name):
        doc = _doc()
        return doc.getObject(name) if doc is not None else None

    def edit(self, name):
        if self._object(name) is None or not _ready():
            return
        obj = self._object(name)  # finishing the open command may have removed it
        if obj is None:
            return
        doc = obj.Document
        back = self._roll_for_edit(doc, name)
        try:
            body = ops.body_of(obj)
            if body is not None:
                components.activate_body(body)  # and its component
        except Exception:
            pass
        from . import taskui

        taskui.edit_object(obj)  # the feature's SciForge dialog (EDITORS), else FreeCAD's
        if back is not None:
            self._roll_back_after_edit(doc.Name, *back)

    def _roll_for_edit(self, doc, name):
        """Fusion: editing a step after the history marker rolls the design to that
        step while its dialog is open (else the edit could not be seen). Returns what
        to roll back to afterwards: (marker count before, marker count while editing)."""
        self.refresh(force=True)
        item = self._timeline.find(name)
        if item is None or item.state != "rolled_back":
            return None
        tips, note = core.marker_for_slot(self._timeline, item.index + 1)
        saved = (core.active_count(self._timeline), self._timeline.before)
        ops.set_marker_untracked(doc, tips, note)
        self.refresh(force=True)
        return saved, (core.active_count(self._timeline), self._timeline.before)

    def _roll_back_after_edit(self, doc_name, before, during):
        """Once the edit is over, put the marker back where it was (unless the user
        moved it meanwhile)."""
        timer = QtCore.QTimer(self)
        timer.setInterval(150)

        def check():
            try:
                if _command_open():
                    return
                timer.stop()
                timer.deleteLater()
                doc = _doc()
                if doc is None or doc.Name != doc_name:
                    return
                tl = ops.timeline(doc, deps=False)
                if (core.active_count(tl), tl.before) != during:
                    return  # the user rolled the marker himself
                count, note = before
                ops.set_marker_untracked(doc, core.tips_for_count(tl, count), note)
                self.refresh(force=True)
            except Exception as exc:
                timer.stop()
                warn("timeline: %s" % exc)

        timer.timeout.connect(check)
        timer.start()

    def edit_profile(self, name):
        obj = self._object(name)
        sketch = ops.profile_sketch(obj) if obj is not None else None
        if sketch is not None:
            self.edit(sketch.Name)

    def suppress_selected(self, on):
        """Suppress Features / Unsuppress Features on every selected step."""
        doc = _doc()
        if doc is None or not self._selected or not _ready():
            return
        ops.suppress_many(doc, list(self._selected), on)
        self.refresh(force=True)

    def toggle_suppress(self, name):
        doc = _doc()
        if doc is None or not _ready():
            return
        with_it = ops.toggle_suppress(doc, name)
        if with_it:
            _remember(
                "info",
                "timeline: %s also switched for %s" % (name, ", ".join(with_it)),
            )
        self.refresh(force=True)

    def delete(self, names):
        doc = _doc()
        if doc is None or not names or not _ready():
            return
        Gui.Selection.clearSelection()
        ops.delete(doc, names)
        self._selected = []
        self.refresh(force=True)

    def delete_selected(self):
        if self._selected:
            _later(self.delete, list(self._selected))

    def rename(self, name):
        """Fusion: the name becomes editable in place; Enter keeps it, Esc cancels."""
        if not _ready():  # a rename is an undo step: never inside a command's own step
            return
        button = self.button(name)
        if button is None:
            return
        self._cancel_editor()
        text = button.item.display
        width = max(140, button.fontMetrics().horizontalAdvance(text) + 24)
        top_left = self.mapFromGlobal(button.mapToGlobal(QtCore.QPoint(0, 0)))
        x = max(0, min(top_left.x(), self.width() - width))
        rect = QtCore.QRect(x, max(0, top_left.y()), width, button.height())
        self._editor = InlineEditor(
            self, rect, text, lambda t, n=name: self._renamed(n, t), "SciForgeTimelineRename"
        )

    def _renamed(self, name, text):
        self._editor = None
        doc = _doc()
        try:
            item = self._timeline.find(name) if self._timeline is not None else None
            if item is not None and (text or "").strip() == item.display:
                text = None  # Enter on the name shown: no rename ("Extrude 1" stays a number)
            if doc is not None and text is not None:
                ops.rename(doc, name, text)
        except Exception as exc:
            warn("rename: %s" % exc)
        self.refresh(force=True)

    def _cancel_editor(self):
        if self._editor is not None:
            editor = self._editor
            self._editor = None
            editor.on_commit = lambda _t: None
            editor.cancel()

    # -- groups ------------------------------------------------------------------
    def toggle_group(self, gid):
        if core.marker_in_group(self._timeline, gid):
            # Fusion's marker stands before or after a collapsed group, never in it.
            _tell(
                "The history marker is inside this group, so it stays open. Move the marker "
                "before or after the group to close it."
            )
            self._open_groups.add(gid)  # it shows open; it stays so once the marker leaves
            return
        if gid in self._open_groups:
            self._open_groups.discard(gid)
        else:
            self._open_groups.add(gid)
        self.refresh(force=True)

    def roll_after_group(self, gid):
        """Roll History Marker Here on a group: the marker goes right after its last step."""
        members = core.group_members(self._timeline, gid)
        if members:
            self.roll_here(members[-1].name)

    def group_selected(self):
        doc = _doc()
        if doc is None or not _ready():
            return
        gid = ops.group(doc, list(self._selected))
        self._open_groups.discard(gid)  # Fusion shows a new group closed
        self.refresh(force=True)

    def group_button(self, gid):
        for widget, _l, _r in self._slots:
            if isinstance(widget, _GroupButton) and widget.gid == gid:
                return widget
        return None

    def ungroup(self, gid):
        doc = _doc()
        if doc is not None and _ready():
            ops.ungroup(doc, gid)
            self._open_groups.discard(gid)
            self.refresh(force=True)

    def rename_group(self, gid):
        if not _ready():
            return
        header = self.group_button(gid)
        if header is None:
            return
        self._cancel_editor()
        top_left = self.mapFromGlobal(header.mapToGlobal(QtCore.QPoint(0, 0)))
        width = max(140, header.fontMetrics().horizontalAdvance(header.name) + 24)
        x = max(0, min(top_left.x(), self.width() - width))
        rect = QtCore.QRect(x, max(0, top_left.y()), width, header.height())
        self._editor = InlineEditor(
            self, rect, header.name, lambda t: self._group_renamed(gid, t), "SciForgeTimelineRename"
        )

    def _group_renamed(self, gid, text):
        self._editor = None
        doc = _doc()
        try:
            if doc is not None and text is not None:
                ops.rename_group(doc, gid, text)
        except Exception as exc:
            warn("rename group: %s" % exc)
        self.refresh(force=True)

    def suppress_group(self, gid, on):
        doc = _doc()
        if doc is None or not _ready():
            return
        ops.suppress_many(doc, ops.group_members(doc, gid), on)
        self.refresh(force=True)

    def _group_menu(self, header, global_pos):
        members = [i.name for i in header.members]
        menu = QtWidgets.QMenu(self)
        menu.setObjectName("SciForgeTimelineGroupMenu")
        actions = {}
        doc = _doc()
        objs = [doc.getObject(n) for n in members] if doc else []
        any_on = any(o is not None and not ops.is_suppressed(o) for o in objs)

        def add(text, fn, enabled=True):
            action = menu.addAction(text)
            action.setEnabled(enabled)
            actions[action] = fn

        add(
            "Collapse Group" if header.opened else "Expand Group",
            lambda: self.toggle_group(header.gid),
            not (header.opened and header.holds_marker),
        )
        menu.addSeparator()
        add(
            "Suppress Features" if any_on else "Unsuppress Features",
            lambda: self.suppress_group(header.gid, any_on),
        )
        add("Roll History Marker Here", lambda: self.roll_after_group(header.gid))
        menu.addSeparator()
        add("Rename", lambda: self.rename_group(header.gid))
        add("Ungroup", lambda: self.ungroup(header.gid))
        add("Delete", lambda: self.delete(members))
        self._busy += 1
        try:
            chosen = menu.exec_(global_pos)
        finally:
            self._busy -= 1
        if chosen in actions:
            _later(actions[chosen])

    def find_in_browser(self, name):
        from . import browser_ui

        browser_ui.find(name)

    def find_in_window(self, name):
        obj = self._object(name)
        if obj is None or not _ready():  # the selection it makes is not a pick
            return
        target = obj
        visible = getattr(obj.ViewObject, "Visibility", False) if obj.ViewObject else False
        if not visible:
            target = ops.body_of(obj) or obj
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(target.Document.Name, target.Name)
        Gui.SendMsgToActiveView("ViewSelection")

    # -- menus ---------------------------------------------------------------------
    def _settings(self):
        menu = QtWidgets.QMenu(self)
        menu.setObjectName("SciForgeTimelineSettings")
        to_end = menu.addAction("Roll History Marker to End")
        to_end.setEnabled(not self._timeline.at_end)
        # No "Hide Timeline" (Fusion has none): with the menu bar hidden a beginner could
        # not get it back.
        groups = {i.group for i in self._items if i.group}
        menu.addSeparator()
        expand = menu.addAction("Expand All Groups")
        expand.setEnabled(bool(groups - self._open_groups))
        collapse = menu.addAction("Collapse All Groups")
        collapse.setEnabled(bool(groups & self._open_groups))
        menu.addSeparator()
        # Fusion's timeline settings switch the design to direct modeling too (it asks).
        no_history = menu.addAction("Do Not Capture Design History")
        no_history.setEnabled(_doc() is not None and not _base_feature_open())
        self._busy += 1
        try:
            chosen = menu.exec_(QtGui.QCursor.pos())
        finally:
            self._busy -= 1
        if chosen is no_history:
            _later(Gui.runCommand, "SciForge_DoNotCaptureDesignHistory")
        if chosen is to_end:
            _later(self.roll_to_end)
        elif chosen is expand:
            self._open_groups |= groups
            _later(self.refresh, True)
        elif chosen is collapse:
            self._open_groups -= groups
            _later(self.refresh, True)

    def _menu(self, button, global_pos):
        item = button.item
        if item.name not in self._selected:
            self._selected = [item.name]
            # A right-click is not a pick: with a command waiting for picks (Fillet
            # takes whole features) it would have used this step. The command ends
            # when a menu entry runs (_ready).
            if not _command_open():
                self._push_selection()
            self._update_selection_look()
        obj = self._object(item.name)
        if obj is None:
            return
        menu = QtWidgets.QMenu(self)
        menu.setObjectName("SciForgeTimelineMenu")
        actions = {}

        def add(text, fn, enabled=True, icon=None):
            action = menu.addAction(ui_icon(icon), text) if icon else menu.addAction(text)
            action.setEnabled(enabled)
            actions[action] = fn
            return action

        first = {"sketch": "Edit Sketch", "component": "Activate"}.get(item.kind, "Edit Feature")
        edit = add(first, lambda: self.edit(item.name))
        font = edit.font()
        font.setBold(True)
        edit.setFont(font)
        profile = ops.profile_sketch(obj)
        if profile is not None:
            add("Edit Profile Sketch", lambda: self.edit_profile(item.name))
        for text, fn, enabled in _menu_extras(obj):  # a Derive's Update Derive, Break Link
            add(text, lambda f=fn: f(obj), enabled and len(self._selected) == 1)
        menu.addSeparator()
        many = len(self._selected) > 1
        if many:  # Fusion: Suppress Features works on the whole selection
            add(
                "Unsuppress Features" if item.suppressed else "Suppress Features",
                lambda: self.suppress_selected(not item.suppressed),
                ops.can_suppress(obj),
            )
        else:
            add(
                "Unsuppress Features" if item.suppressed else "Suppress Features",
                lambda: self.toggle_suppress(item.name),
                ops.can_suppress(obj),
            )
        add("Roll History Marker Here", lambda: self.roll_here(item.name), not many)
        menu.addSeparator()
        add("Rename", lambda: self.rename(item.name), not many)
        add("Delete", lambda: self.delete(list(self._selected)), True, "delete")
        menu.addSeparator()
        add("Find in Browser", lambda: self.find_in_browser(item.name), not many)
        add("Find in Window", lambda: self.find_in_window(item.name), not many)
        if many:
            menu.addSeparator()
            ok, _reason = core.can_group(self._timeline, self._selected)
            add("Group Features", self.group_selected, ok)
        self._busy += 1  # no rebuild under an open menu
        try:
            chosen = menu.exec_(global_pos)
        finally:
            self._busy -= 1
        if chosen in actions:
            _later(actions[chosen])


def _menu_extras(obj):
    """[(text, fn(obj), enabled)] a feature module adds to a step's menu (taskui.MENU_EXTRAS)."""
    from . import taskui

    found = []
    for text, fn, enabled in taskui.MENU_EXTRAS.get(ops.type_key(obj), []):
        try:
            on = bool(enabled(obj))
        except Exception:
            on = False
        found.append((text, fn, on))
    return found


def _hidden_steps(doc, timeline, active):
    """Names of the steps the active component hides (none when the root is active)."""
    if doc is None or active is None:
        return set()
    hidden = set()
    for item in timeline.items:
        try:
            unit = doc.getObject(item.body) if item.body else doc.getObject(item.name)
            if unit is None or not components.is_inside(unit, active):
                hidden.add(item.name)
        except Exception:
            hidden.add(item.name)
    return hidden


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


def widget():
    return _dock.widget() if _dock is not None else None


def find(name):
    """Select a step in the timeline (Find in Timeline)."""
    w = widget()
    if w is None:
        return False
    w.refresh()
    w.select([name])
    return bool(w.selected())


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
