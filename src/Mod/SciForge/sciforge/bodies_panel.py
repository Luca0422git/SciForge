# SPDX-License-Identifier: LGPL-2.1-or-later
"""The dialog base of the body tools (Combine, Split Body, Move/Copy, Appearance, Physical
Material): Fusion's selection boxes, clicks in the 3D view taken one moment after FreeCAD
handled them, a live preview, OK / Cancel / Esc / Enter, Ctrl+Z cancelling, one undo step,
problems said in the dialog.

Subclasses fill the form in build_form(), take clicks in picked(obj, short, point), say
whether OK is possible in can_finish(), and rebuild the preview in apply() (raise the core
module's NeedsPick while a box still waits, any other error to show it in red).
"""
import time

import FreeCAD as App
import FreeCADGui as Gui

from . import bodies, bodies_gui, hole_common, log, preview, warn
from .compat import QtCore, QtWidgets
from .taskui import Panel

INFO_STYLE = "color: #8cc4ff;"
NOTE_STYLE = "color: #b8c7d9;"


class BodyPanel(Panel):
    title = "SciForge"
    icon = None
    needs_pick = (Exception,)  # the core's NeedsPick (a hint, not a problem)
    last = None

    def __init__(self, doc, transaction, editing=False):
        super().__init__(doc, transaction)
        type(self).last = self
        BodyPanel.last = self
        self.editing = editing
        self.view = Gui.ActiveDocument.ActiveView
        self.fields = {}
        self.captions = {}
        self.active = None
        self.error = ""
        self.waiting = ""
        self.dirty = False
        self._quiet = False
        self._syncing = False
        self._busy_until = 0.0  # a handle was just dragged: the click is not a pick
        self.escape = preview.EscapeCancels(self)
        self.undo_guard = preview.UndoCancels(self)
        self.enter = preview.EnterFinishes(self)
        self.observer = None
        self.target = None  # what UndoCancels clears when an undo takes the preview away
        bodies.pause(doc)
        self.build_form()
        self.info = QtWidgets.QLabel("")  # what the dialog waits for (not a problem)
        self.info.setWordWrap(True)
        self.info.setStyleSheet(INFO_STYLE)
        self.layout.addRow(self.info)
        self.note = QtWidgets.QLabel("")
        self.note.setWordWrap(True)
        self.note.setStyleSheet(NOTE_STYLE)
        self.layout.addRow(self.note)
        self.finish_layout()
        self._watch()

    # -- form helpers ----------------------------------------------------------------------------
    def build_form(self):
        pass

    def selection_box(self, name, label, empty="Select"):
        field = hole_common.SelectionField(self, name, empty)
        caption = QtWidgets.QLabel(label)
        self.layout.addRow(caption, field.widget)
        self.fields[name] = field
        self.captions[name] = caption
        return field

    def check_box(self, label, checked, on_toggle, tip=""):
        box = QtWidgets.QCheckBox()
        box.setChecked(bool(checked))
        if tip:
            box.setToolTip(tip)
        box.toggled.connect(lambda *_: self._guarded(on_toggle))
        caption = QtWidgets.QLabel(label)
        self.layout.addRow(caption, box)
        return box, caption

    def combo(self, label, pairs, current, on_change):
        box = hole_common.combo(pairs, current)
        box.currentIndexChanged.connect(lambda *_: self._guarded(on_change))
        caption = QtWidgets.QLabel(label)
        self.layout.addRow(caption, box)
        return box, caption

    def _guarded(self, fn):
        if self._quiet or self._closed:
            return
        try:
            fn()
        except Exception as exc:
            warn("%s: %s" % (self.title, exc))

    def show_row(self, widget, caption, shown):
        widget.setVisible(shown)
        if caption is not None:
            caption.setVisible(shown)

    # -- selection boxes (hole_common.SelectionField calls these) ---------------------------------------
    def activate(self, name):
        if name not in self.fields:
            return
        self.active = name
        self._show_active()
        self.activated(name)

    def activated(self, name):
        """A box became the one that takes clicks (subclasses show pickers)."""

    def _show_active(self):
        for name, field in self.fields.items():
            field.set_active(name == self.active)

    def clear_field(self, name):
        self.cleared(name)
        self.activate(name)
        self.changed()

    def cleared(self, name):
        pass

    # -- clicks ------------------------------------------------------------------------------------
    def _watch(self):
        panel = self

        class Observer:
            def addSelection(self, doc, obj, sub, pnt):
                if not panel._syncing:
                    QtCore.QTimer.singleShot(30, panel._selection_changed)

        self.observer = Observer()
        Gui.Selection.addObserver(self.observer)

    def _unwatch(self):
        if self.observer is not None:
            try:
                Gui.Selection.removeObserver(self.observer)
            except Exception:
                pass
            self.observer = None

    def busy(self, seconds=0.6):
        """Hold off picks for a moment (a handle was pressed: FreeCAD still selects what is
        under it when the button comes up)."""
        self._busy_until = time.time() + seconds

    def _selection_changed(self):
        if self._closed:
            return
        try:
            entries = [e for e in bodies_gui.selection_entries() if e[0].Document is self.doc]
            if not entries:
                return
            self._syncing = True
            try:
                Gui.Selection.clearSelection()
            finally:
                self._syncing = False
            if time.time() < self._busy_until:
                return
            for obj, short, point in entries:
                self.picked(obj, short, point)
        except Exception as exc:
            warn("%s pick: %s" % (self.title, exc))

    def picked(self, obj, short, point):
        """A click (subclasses)."""

    def start_from_selection(self):
        """What was selected before the command started, as if clicked now (Fusion takes a
        preselection), then cleared."""
        entries = [e for e in bodies_gui.selection_entries() if e[0].Document is self.doc]
        self._syncing = True
        try:
            Gui.Selection.clearSelection()
        finally:
            self._syncing = False
        for obj, short, point in entries:
            try:
                self.picked(obj, short, point)
            except Exception as exc:
                warn("%s pick: %s" % (self.title, exc))
        return bool(entries)

    # -- the preview -------------------------------------------------------------------------------
    def changed(self):
        """Something changed: rebuild the preview shortly (coalesces typing and drags)."""
        self.dirty = True
        self.schedule()

    def _recompute(self):
        if self._closed:
            return
        if getattr(self.doc, "Recomputing", False):
            self.schedule()  # a long recompute runs timers inside it: try again after
            return
        try:
            if self.dirty:
                self.dirty = False
                self._apply()
            preview.recompute(self.doc)
            self.after_recompute()
            self.show_status()
        except Exception as exc:
            self.message.setText("⚠ %s" % exc)

    def _apply(self):
        self.error = ""
        self.waiting = ""
        try:
            self.apply()
        except self.needs_pick as exc:
            self.waiting = str(exc)
        except Exception as exc:
            self.error = str(exc)

    def apply(self):
        pass

    def after_recompute(self):
        pass

    def preview_steps(self):
        """The steps the preview made (their errors are shown)."""
        return []

    def failure(self):
        for step in self.preview_steps():
            if not bodies.alive(step):
                continue
            text = preview.failure(step)
            if text:
                return _plain(text)
        return ""

    def show_status(self):
        self.info.setText(self.waiting)
        if self.error:
            self.message.setText("⚠ " + self.error)
            return
        if self.waiting:
            self.message.setText("")
            return
        text = self.failure()
        self.message.setText("⚠ " + text if text else "")

    def can_finish(self):
        """'' when OK may close the dialog, else what is missing."""
        return ""

    # -- OK / Cancel ----------------------------------------------------------------------------------
    def accept(self):
        if self._closed:
            return True
        try:
            self._timer.stop()
            if self.dirty:
                self.dirty = False
                self._apply()
            missing = self.waiting or self.can_finish()
            if missing:
                self.message.setText("⚠ " + missing)
                self.info.setText("")
                return False
            if self.error:
                self.message.setText("⚠ " + self.error)
                return False
            preview.recompute(self.doc)
            text = self.failure()
            if text:
                self.message.setText("⚠ " + text)
                return False
            self.before_close(ok=True)
            self.cleanup()
            preview.end_transaction(self.doc)
            self._close()
            self.after_close(ok=True)
            log("%s done" % self.title)
            return True
        except Exception as exc:
            warn("%s: %s" % (self.title, exc))
            self.message.setText("⚠ %s" % exc)
            return False

    def reject(self):
        if self._closed:
            return True
        try:
            self._timer.stop()
            self.before_close(ok=False)
            self.cleanup()
            preview.end_transaction(self.doc, abort=True)
            preview.recompute(self.doc)
            self._close()
            self.after_close(ok=False)
        except Exception as exc:
            warn("%s cancel: %s" % (self.title, exc))
        return True

    def before_close(self, ok):
        pass

    def after_close(self, ok):
        try:
            bodies_gui.sync(self.doc)
        except Exception as exc:
            warn("%s: %s" % (self.title, exc))

    def cleanup(self):
        bodies.resume(self.doc)
        self._unwatch()
        for guard in (self.escape, self.undo_guard, self.enter):
            try:
                guard.remove()
            except Exception:
                pass
        self.remove_handles()
        try:
            self.restore_view()
        except Exception as exc:
            warn("%s: %s" % (self.title, exc))
        super().cleanup()
        # However the dialog ended (OK, Cancel, Esc, Ctrl+Z, another command): the view is
        # brought in line with the design a moment later.
        name = self.doc.Name
        QtCore.QTimer.singleShot(0, lambda: _sync_later(name))

    def restore_view(self):
        """Undo what the dialog changed in the view only (see-through bodies...)."""

    def remove_handles(self):
        pass


def _sync_later(name):
    try:
        if name in App.listDocuments():
            bodies_gui.sync(App.getDocument(name))
    except Exception as exc:
        warn("body tools: %s" % exc)


PLAIN = (
    ("tool shape is null", "A tool body has no solid."),
    ("multiple solids", "The result would be separate pieces."),
)


def _plain(text):
    text = str(text or "").strip()
    for prefix in ("Exception: ", "<Exception> "):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    for needle, said in PLAIN:
        if needle in text.lower():
            return said
    return text


def start(panel_class, *args, **kwargs):
    """Open a dialog the way every SciForge command does: the open one is finished first."""
    from . import commands

    if App.ActiveDocument is None:
        commands.tell("Open or start a design first.")
        return None
    if not commands.finish_open_dialog():
        return None
    panel = panel_class(App.ActiveDocument, *args, **kwargs)
    Gui.Control.showDialog(panel)
    return panel


def edit(panel_class, feature, **kwargs):
    """Open a dialog on an existing step (timeline double-click)."""
    from . import commands

    try:
        if Gui.Control.activeDialog() and not commands.finish_open_dialog():
            return None
        panel = panel_class(feature.Document, feature=feature, **kwargs)
        Gui.Control.showDialog(panel)
        return panel
    except Exception as exc:
        warn("could not edit %s: %s" % (feature.Label, exc))
        return None


def preselection():
    """[(object, short name, point)] selected before a command started."""
    return list(bodies_gui.selection_entries())
