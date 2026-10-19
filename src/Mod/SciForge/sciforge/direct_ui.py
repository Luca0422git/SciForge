# SPDX-License-Identifier: LGPL-2.1-or-later
"""Capture Design History on/off, Create / Finish Base Feature and editing a base feature
(the GUI side of direct.py):

  Capture Design History           right-click the design's top row in the browser (or the
  Do Not Capture Design History    timeline's settings): with history off the timeline goes
                                   away and every command changes the bodies directly;
                                   turning it off asks first (the history is removed)
  Create Base Feature              SOLID > CREATE: what is made until Finish Base Feature
                                   is kept as base features, not as single steps
  Finish Base Feature              the bar over the 3D view (and SOLID > CREATE)
  Edit Feature on a Base Feature   double-click it in the timeline: its bodies take direct
                                   edits again, the design rolled back to it meanwhile

The bake that keeps a design without history free of steps runs where a command's undo
step ends (preview.end_transaction / taskui._end_transaction / delete.run call
direct.takes_commit): one undo step per command, as in Fusion. A change a FreeCAD command
made is baked right after its undo step (DocWatch) as an undo step of its own.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, direct, log, theme, ui_icon, ui_icon_path, warn
from . import direct_core as core
from .compat import QtCore, QtWidgets

_DEFERRED = {}  # document name -> the transaction (name, id) whose commit waits for a bake


# -- the deferred end of a command's undo step ----------------------------------------------------
def _schedule(doc_name, transaction):
    _DEFERRED[doc_name] = transaction
    QtCore.QTimer.singleShot(0, lambda: _finish(doc_name, 0))


def _busy(doc):
    try:
        if Gui.Control.activeDialog():
            return True
        gdoc = Gui.getDocument(doc.Name)
        if gdoc is not None and gdoc.getInEdit() is not None:
            return True
        return bool(getattr(doc, "Recomputing", False) or getattr(doc, "Restoring", False))
    except Exception:
        return False


def _finish(doc_name, tries):
    try:
        if doc_name not in _DEFERRED:
            return  # flushed already
        if doc_name not in App.listDocuments():
            _DEFERRED.pop(doc_name, None)
            return
        doc = App.getDocument(doc_name)
        transaction = _DEFERRED.get(doc_name)
        if _busy(doc) and not _still_open(transaction):
            # Another command opened meanwhile (that closed this undo step): its own OK
            # bakes what is left; else it is baked once nothing is open any more.
            if tries < 2000:
                QtCore.QTimer.singleShot(300, lambda: _finish(doc_name, tries + 1))
            return
        if getattr(doc, "Recomputing", False) and tries < 100:
            QtCore.QTimer.singleShot(50, lambda: _finish(doc_name, tries + 1))
            return
        _DEFERRED.pop(doc_name, None)
        direct.finish_deferred(doc, transaction)
    except Exception as exc:
        _DEFERRED.pop(doc_name, None)
        warn("could not finish the change: %s" % exc)


def _still_open(transaction):
    try:
        current = App.getActiveTransaction()
    except Exception:
        return False
    return (
        transaction is not None
        and current is not None
        and direct._tid(current) == direct._tid(transaction)
    )


def flush_deferred():
    """Finish a waiting bake now (a new command is about to open its own undo step, which
    would close the waiting one first). Called by commands.finish_open_dialog()."""
    for name in list(_DEFERRED):
        try:
            transaction = _DEFERRED.pop(name, None)
            if name in App.listDocuments() and _still_open(transaction):
                direct.finish_deferred(App.getDocument(name), transaction)
        except Exception as exc:
            warn("could not finish the change: %s" % exc)


class DocWatch:
    """A change a FreeCAD command (not SciForge's) made in a design without history, or to
    a base feature's bodies, is baked right after its undo step closed; never after an
    undo or a redo. Also ends a base feature session whose design is closed."""

    def __init__(self):
        self._pending = set()

    def slotCommitTransaction(self, doc):
        try:
            name = doc.Name
        except Exception:
            return
        if name in self._pending or name in _DEFERRED:
            return
        if not direct.is_direct(doc) and direct.session(doc) is None:
            return
        self._pending.add(name)
        QtCore.QTimer.singleShot(150, lambda: self._run(name, 0))

    def _run(self, name, tries):
        try:
            if name not in App.listDocuments():
                self._pending.discard(name)
                return
            doc = App.getDocument(name)
            if name in _DEFERRED:
                self._pending.discard(name)
                return
            if _busy(doc) or doc.HasPendingTransaction:
                if tries < 2000:
                    QtCore.QTimer.singleShot(300, lambda: self._run(name, tries + 1))
                else:
                    self._pending.discard(name)
                return
            self._pending.discard(name)
            if direct.bake_step(doc):
                log("a change made without SciForge was applied to the bodies")
        except Exception as exc:
            self._pending.discard(name)
            warn("could not apply the change to the bodies: %s" % exc)

    def slotDeletedDocument(self, doc):
        try:
            direct.forget(doc.Name)
            _DEFERRED.pop(doc.Name, None)
        except Exception:
            pass


_WATCH = {"observer": None}


def install():
    """Hook the bake into the commands (taken by direct.takes_commit) and watch documents."""
    direct.SCHEDULER = _schedule
    if _WATCH["observer"] is None:
        _WATCH["observer"] = DocWatch()
        App.addDocumentObserver(_WATCH["observer"])
    _bar_timer()


# -- Capture Design History --------------------------------------------------------------------
def _doc():
    return App.ActiveDocument


class CaptureHistoryCommand:
    """Capture Design History (the design's right-click menu)."""

    def GetResources(self):
        return {
            "MenuText": core.CAPTURE_ON,
            "ToolTip": "Record the design's history in the timeline again: the bodies as they "
            "are become base features at its start",
            "Pixmap": ui_icon_path("document"),
        }

    def IsActive(self):
        doc = _doc()
        return doc is not None and direct.is_direct(doc)

    def Activated(self):
        try:
            doc = _doc()
            if doc is None or not direct.is_direct(doc):
                return
            if not commands.finish_open_dialog():
                return
            flush_deferred()
            direct.history_on(doc)
            _refresh_panels()
            commands.tell("Design history is captured: the timeline is back.")
        except Exception as exc:
            warn("Capture Design History failed: %s" % exc)


class DoNotCaptureHistoryCommand:
    """Do Not Capture Design History: asks first (the history is removed)."""

    def GetResources(self):
        return {
            "MenuText": core.CAPTURE_OFF,
            "ToolTip": "Stop recording history: every step is baked into its body, the "
            "timeline goes away and every change is made directly (asks first)",
            "Pixmap": ui_icon_path("document"),
        }

    def IsActive(self):
        doc = _doc()
        return doc is not None and not direct.is_direct(doc)

    def Activated(self):
        try:
            doc = _doc()
            if doc is None or direct.is_direct(doc):
                return
            if direct.session(doc) is not None:
                commands.tell("Finish the base feature first (Finish Base Feature).")
                return
            if not commands.finish_open_dialog():
                return
            flush_deferred()
            ask_history_off(doc)
        except Exception as exc:
            warn("Do Not Capture Design History failed: %s" % exc)


class HistoryOffDialog(QtWidgets.QDialog):
    """The question Fusion asks before it removes the history (its own words are not used)."""

    def __init__(self, doc):
        super().__init__(Gui.getMainWindow())
        self.setObjectName("SciForgeHistoryOffDialog")
        self.setWindowTitle(core.CAPTURE_OFF)
        self.setModal(True)
        self.doc_name = doc.Name
        layout = QtWidgets.QVBoxLayout(self)
        text = QtWidgets.QLabel(
            "Stop recording the design's history?\n\n"
            "Every step in the timeline is baked into its body and the timeline goes away: "
            "the bodies keep their shape, but their steps can no longer be edited. Bodies a "
            "Combine or a Remove took out of the design are deleted. Sketches and "
            "construction planes stay. From now on every command changes the bodies "
            "directly.\n\n"
            "Ctrl+Z brings the history back. Capture Design History starts a new timeline "
            "with the bodies as base features."
        )
        text.setWordWrap(True)
        text.setMinimumWidth(420)
        layout.addWidget(text)
        buttons = QtWidgets.QDialogButtonBox()
        self.remove_button = buttons.addButton(
            "Remove History", QtWidgets.QDialogButtonBox.AcceptRole
        )
        self.remove_button.setObjectName("SciForgeHistoryOffRemove")
        cancel = buttons.addButton(QtWidgets.QDialogButtonBox.Cancel)
        cancel.setObjectName("SciForgeHistoryOffCancel")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.remove_button.setDefault(True)


_DIALOGS = {}


def ask_history_off(doc):
    dialog = HistoryOffDialog(doc)
    _DIALOGS["history_off"] = dialog

    def done(result, name=doc.Name):
        try:
            _DIALOGS.pop("history_off", None)
            QtCore.QTimer.singleShot(0, _refocus_main)
            if not result:
                log("design history kept")
                return
            QtCore.QTimer.singleShot(0, lambda: _history_off(name))
        except Exception as exc:
            warn("Do Not Capture Design History: %s" % exc)

    dialog.finished.connect(done)
    dialog.open()
    dialog.raise_()
    dialog.activateWindow()
    return dialog


def _history_off(name):
    try:
        if name not in App.listDocuments():
            return
        doc = App.getDocument(name)
        direct.history_off(doc)
        _refresh_panels()
        commands.tell("Design history is off: changes are made directly to the bodies.")
    except direct.DirectError as exc:
        commands.tell(str(exc))
    except Exception as exc:
        warn("Do Not Capture Design History failed: %s" % exc)


def history_dialog():
    """The open question (tests), or None."""
    dialog = _DIALOGS.get("history_off")
    try:
        return dialog if dialog is not None and dialog.isVisible() else None
    except RuntimeError:
        return None


def _refocus_main():
    """Without a window manager nothing gives the main window the keys back after a dialog
    (versions_ui does the same)."""
    try:
        from . import taskui

        Gui.getMainWindow().activateWindow()
        widget = taskui.view_widget()
        if widget is not None:
            widget.setFocus()
    except Exception:
        pass


def _refresh_panels():
    for module_name in ("timeline_ui", "browser_ui"):
        try:
            import importlib

            module = importlib.import_module("." + module_name, __package__)
            widget = module.widget()
            if widget is not None:
                widget.refresh(force=True)
        except Exception:
            pass


# -- base features -----------------------------------------------------------------------------
class CreateBaseFeatureCommand:
    def GetResources(self):
        return {
            "MenuText": "Create Base Feature",
            "ToolTip": "Make or change bodies directly, without single steps in the timeline: "
            "everything until Finish Base Feature is one base feature per body",
            "Pixmap": ui_icon_path("base_feature"),
        }

    def IsActive(self):
        doc = _doc()
        return doc is not None and not direct.is_direct(doc) and direct.session(doc) is None

    def Activated(self):
        try:
            doc = _doc()
            if doc is None:
                return
            if direct.is_direct(doc):
                commands.tell(
                    "This design does not capture history: every change is already direct."
                )
                return
            if direct.session(doc) is not None:
                commands.tell("A base feature is open: finish it first (Finish Base Feature).")
                return
            if not commands.finish_open_dialog():
                return
            flush_deferred()
            direct.start_base_feature(doc)
            show_bar()
            commands.tell("Base feature: what you make now is not recorded step by step.")
        except direct.DirectError as exc:
            commands.tell(str(exc))
        except Exception as exc:
            warn("Create Base Feature failed: %s" % exc)


class FinishBaseFeatureCommand:
    def GetResources(self):
        return {
            "MenuText": "Finish Base Feature",
            "ToolTip": "Back to the design's history: the base feature is one step per body",
            "Pixmap": ui_icon_path("finish_sketch"),
        }

    def IsActive(self):
        doc = _doc()
        return doc is not None and direct.session(doc) is not None

    def Activated(self):
        finish_base_feature()


def finish_base_feature(doc=None):
    try:
        doc = doc or _doc()
        if doc is None or direct.session(doc) is None:
            return False
        if not commands.finish_open_dialog():
            return False
        flush_deferred()
        direct.finish_base_feature(doc)
        hide_bar()
        _refresh_panels()
        return True
    except Exception as exc:
        warn("Finish Base Feature failed: %s" % exc)
        return False


def edit(step):
    """Edit Feature on a base feature (timeline double-click)."""
    try:
        doc = step.Document
        current = direct.session(doc)
        if current is not None:
            commands.tell("A base feature is open: finish it first (Finish Base Feature).")
            return
        if direct.is_direct(doc):
            commands.tell("This design does not capture history: change the bodies directly.")
            return
        if not commands.finish_open_dialog():
            return
        flush_deferred()
        direct.edit_base_feature(step)
        show_bar()
        _refresh_panels()
    except direct.DirectError as exc:
        commands.tell(str(exc))
    except Exception as exc:
        warn("could not edit %s: %s" % (getattr(step, "Label", "the base feature"), exc))


# -- the Finish Base Feature bar over the 3D view ----------------------------------------------
class FinishBar(theme.OwnBackground, QtWidgets.QFrame):
    """Shown while a base feature is open: what is going on, and Finish Base Feature."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("SciForgeBaseFeatureBar")
        self.setStyleSheet(
            "#SciForgeBaseFeatureBar { background: rgba(40, 44, 52, 230); border: 1px solid "
            "#63b3ff; border-radius: 4px; } QLabel { color: #dfe6ee; } QPushButton { "
            "padding: 3px 10px; }"
        )
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(10, 4, 6, 4)
        row.setSpacing(10)
        self.label = QtWidgets.QLabel("")
        row.addWidget(self.label)
        self.button = QtWidgets.QPushButton(ui_icon("finish_sketch"), "Finish Base Feature")
        self.button.setObjectName("SciForgeFinishBaseFeature")
        self.button.clicked.connect(lambda: QtCore.QTimer.singleShot(0, finish_base_feature))
        row.addWidget(self.button)

    def update_for(self, doc, s):
        what = "Editing %s" % s.label if s.editing and s.label else "Base feature"
        self.label.setText(
            "%s: changes go into its bodies, not into the timeline step by step." % what
        )
        self.adjustSize()
        parent = self.parentWidget()
        if parent is not None:
            self.move(max(8, (parent.width() - self.width()) // 2), 8)


_BAR = {"widget": None, "timer": None}


def _bar_parent():
    from . import taskui

    widget = taskui.view_widget()
    return widget.parentWidget() if widget is not None else None


def show_bar():
    _update_bar()


def hide_bar():
    bar = _BAR.get("widget")
    try:
        if bar is not None:
            bar.hide()
    except RuntimeError:
        _BAR["widget"] = None


def bar():
    """The bar when it is shown (tests), or None."""
    widget = _BAR.get("widget")
    try:
        return widget if widget is not None and widget.isVisible() else None
    except RuntimeError:
        return None


def _update_bar():
    try:
        doc = _doc()
        s = direct.session(doc) if doc is not None else None
        widget = _BAR.get("widget")
        try:
            if widget is not None:
                widget.isVisible()
        except RuntimeError:
            widget = _BAR["widget"] = None
        if s is None:
            if widget is not None and widget.isVisible():
                widget.hide()
            return
        parent = _bar_parent()
        if parent is None:
            return
        if widget is None or widget.parentWidget() is not parent:
            if widget is not None:
                widget.deleteLater()
            widget = _BAR["widget"] = FinishBar(parent)
        widget.update_for(doc, s)
        if not widget.isVisible():
            widget.show()
        widget.raise_()
    except Exception as exc:
        warn("base feature bar: %s" % exc)


def _bar_timer():
    if _BAR["timer"] is not None:
        return
    timer = QtCore.QTimer()
    timer.setInterval(500)
    timer.timeout.connect(_update_bar)
    timer.start()
    _BAR["timer"] = timer


COMMANDS = {
    "SciForge_CaptureDesignHistory": CaptureHistoryCommand,
    "SciForge_DoNotCaptureDesignHistory": DoNotCaptureHistoryCommand,
    "SciForge_CreateBaseFeature": CreateBaseFeatureCommand,
    "SciForge_FinishBaseFeature": FinishBaseFeatureCommand,
}
EDITORS = {"SciForge::BaseFeature": edit, "PartDesign::FeatureBase": edit}

try:
    install()
except Exception as _exc:  # never let an import fail the commands
    warn("design history watch unavailable: %s" % _exc)
