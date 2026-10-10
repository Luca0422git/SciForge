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

from . import _remember, timeline_core as core
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

    # -- keys ----------------------------------------------------------------------
    def event(self, event):
        # Delete and F2 belong to the timeline while a step has the focus.
        if event.type() == QtCore.QEvent.ShortcutOverride and event.key() in (
            QtCore.Qt.Key_Delete,
            QtCore.Qt.Key_Backspace,
            QtCore.Qt.Key_F2,
        ):
            event.accept()
            return True
        return super().event(event)

    def keyPressEvent(self, event):
        try:
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


class _GroupButton(QtWidgets.QToolButton):
    """A timeline group: one folder for several steps. Click opens or closes it."""

    def __init__(self, timeline, gid, name, members, opened):
        super().__init__()
        self.timeline = timeline
        self.gid = gid
        self.name = name
        self.members = members
        self.opened = opened
        self.setObjectName("SciForgeGroup_" + gid)
        self.setProperty("role", "step")
        self.setIcon(ui_icon("folder"))
        self.setIconSize(QtCore.QSize(ICON, ICON))
        bad = [m for m in members if m.status == "error"]
        warned = [m for m in members if m.status == "warning"]
        self.setProperty("status", "error" if bad else ("warning" if warned else "ok"))
        lines = [name, "%d steps: %s" % (len(members), ", ".join(m.display for m in members))]
        lines.append("Click to %s the group" % ("close" if opened else "open"))
        for m in bad + warned:
            lines.append("%s: %s" % (m.display, m.message))
        self.setToolTip("\n".join(lines))
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(
            lambda pos: self.timeline._group_menu(self, self.mapToGlobal(pos))
        )
        self.clicked.connect(lambda: _later(self.timeline.toggle_group, self.gid))

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
        self._scroll.setFixedHeight(ICON + 14)
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
            ops.install_guard()
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
            self.refresh(force=True)
        except Exception as exc:
            warn("timeline after undo: %s" % exc)

    # -- reading the design --------------------------------------------------------
    def refresh(self, force=False):
        if self._busy or self._drag is not None or self._editor is not None:
            return  # never pull the widgets from under the mouse or the keyboard
        try:
            doc = _doc()
            if doc is None:
                timeline, name = core.build([], {}), None
            else:
                timeline, name = ops.timeline(doc, deps=False), doc.Name
            sig = core.signature(timeline, name)
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
        self._selected = [n for n in self._selected if timeline.find(n) is not None]
        self._rebuild()

    @property
    def _body(self):
        """The document of the timeline (kept for older callers)."""
        return _doc()

    def titles(self):
        """Step names in timeline order ("Sketch 1", "Extrude 1", ...); used by tests."""
        return [item.display for item in self._items]

    def items(self):
        return list(self._items)

    def button(self, name):
        for b in self._buttons:
            if b.item.name == name:
                return b
        return None

    def marker(self):
        for w in self._inner.findChildren(QtWidgets.QFrame):
            if w.property("role") == "marker":
                return w
        return None

    def _clear(self):
        self._cancel_editor()
        while self._row.count():
            entry = self._row.takeAt(0)
            widget = entry.widget()
            if widget is not None:
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
        # (widget, slot left of it, slot right of it) for drops and the marker
        self._slots = []
        for seg in core.segments(self._timeline, self._open_groups):
            if seg[0] == "step":
                item = seg[1]
                if item.index == marker:
                    self._row.addWidget(self._make_marker())
                self._add_step(item)
                continue
            _kind, gid, name, members, opened = seg
            start, end = members[0].index, members[-1].index + 1
            if start == marker:
                self._row.addWidget(self._make_marker())
            header = _GroupButton(self, gid, name, members, opened)
            self._row.addWidget(header)
            self._slots.append((header, start, start if opened else end))
            if not opened:
                continue
            for item in members:
                if item.index == marker and item.index != start:
                    self._row.addWidget(self._make_marker())
                self._add_step(item)
            cap = QtWidgets.QFrame()
            cap.setProperty("role", "group_end")
            cap.setFixedSize(3, ICON + 4)
            self._row.addWidget(cap)
        if marker >= len(self._items):
            self._row.addWidget(self._make_marker())
        self._row.addStretch(1)
        self._update_selection_look()

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
        tips = core.tips_for_slot(self._timeline, self._slot_at(global_pos))
        if tips:
            ops.roll(doc, tips, "Move History Marker")
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
        tips = core.tips_for_item(self._timeline, item.index)
        if tips:
            ops.roll(doc, tips, "Roll History Marker Here")
        self.refresh(force=True)

    def roll_to_end(self):
        doc = _doc()
        if doc is None or not _ready():
            return
        ops.roll_to_end(doc)
        self.refresh(force=True)

    # -- reordering ----------------------------------------------------------------
    def begin_drag(self, button):
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
        plan = core.plan_move(self._move_timeline, button.item.name, slot)
        refused = bool(not plan.ok and plan.reason)
        line.setProperty("refused", "true" if refused else "false")
        line.style().unpolish(line)
        line.style().polish(line)
        line.move(self._drop_x(slot) - 1, 2)
        if refused:
            QtWidgets.QToolTip.showText(global_pos, plan.reason, self)
        else:
            QtWidgets.QToolTip.hideText()

    def end_drag(self, global_pos):
        if self._drag is None:
            return
        button, line = self._drag
        self._drag = None
        button.unsetCursor()
        slot = self._slot_at(global_pos)
        name = button.item.name
        doc = _doc()
        plan = core.plan_move(self._move_timeline, name, slot)
        if not plan.ok:
            line.deleteLater()
            if plan.reason:
                self._refuse(slot, plan.reason, global_pos)
            return
        line.deleteLater()
        if doc is None or not _ready():
            return
        try:
            ops.move(doc, name, slot)
        except ops.TimelineError as exc:
            self._refuse(slot, str(exc), global_pos)
            return
        self.refresh(force=True)
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
        obj = self._object(name)
        if obj is None:
            return
        try:
            body = ops.body_of(obj)
            if body is not None:
                Gui.ActiveDocument.ActiveView.setActiveObject("pdbody", body)
        except Exception:
            pass
        from . import taskui

        taskui.edit_object(obj)  # the feature's SciForge dialog (EDITORS), else FreeCAD's

    def edit_profile(self, name):
        obj = self._object(name)
        sketch = ops.profile_sketch(obj) if obj is not None else None
        if sketch is not None:
            self.edit(sketch.Name)

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
        if gid in self._open_groups:
            self._open_groups.discard(gid)
        else:
            self._open_groups.add(gid)
        self.refresh(force=True)

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
        )
        menu.addSeparator()
        add(
            "Suppress Features" if any_on else "Unsuppress Features",
            lambda: self.suppress_group(header.gid, any_on),
        )
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
        if obj is None:
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
        hide = menu.addAction("Hide Timeline")
        self._busy += 1
        try:
            chosen = menu.exec_(QtGui.QCursor.pos())
        finally:
            self._busy -= 1
        if chosen is hide:
            hide_timeline()
        elif chosen is to_end:
            _later(self.roll_to_end)

    def _menu(self, button, global_pos):
        item = button.item
        if item.name not in self._selected:
            self._selected = [item.name]
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

        edit = add(
            "Edit Sketch" if item.kind == "sketch" else "Edit Feature", lambda: self.edit(item.name)
        )
        font = edit.font()
        font.setBold(True)
        edit.setFont(font)
        profile = ops.profile_sketch(obj)
        if profile is not None:
            add("Edit Profile Sketch", lambda: self.edit_profile(item.name))
        menu.addSeparator()
        many = len(self._selected) > 1
        add(
            "Unsuppress Features" if item.suppressed else "Suppress Features",
            lambda: self.toggle_suppress(item.name),
            ops.can_suppress(obj) and not many,
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
