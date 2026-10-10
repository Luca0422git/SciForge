# SPDX-License-Identifier: LGPL-2.1-or-later
"""Live-preview helpers shared by SciForge's feature dialogs (Extrude, Press Pull).

While a Fusion dialog is open, a value that cannot be built (a zero distance, a face
the extrusion cannot reach, a taper too steep for the profile) is shown *in the
dialog* and the dialog stays open. FreeCAD prints the same failure to the Report
view as well, which a Fusion user reads as "errors everywhere". quiet() mutes
FreeCAD's error and warning output for the length of one preview recompute; the
dialog then reads the failure from the feature (obj.getStatusString()) and shows it.

Only the dialog's own recomputes are wrapped. Everything else (opening files,
editing earlier steps from the timeline) reports as usual.
"""
import contextlib

import FreeCAD as App

_TYPES = ("Err", "Wrn")


@contextlib.contextmanager
def quiet():
    saved = []
    try:
        for name in App.Console.GetObservers():
            for kind in _TYPES:
                try:
                    status = App.Console.GetStatus(name, kind)
                except Exception:
                    continue
                if status:
                    saved.append((name, kind))
                    App.Console.SetStatus(name, kind, False)
    except Exception:
        pass
    try:
        yield
    finally:
        for name, kind in saved:
            try:
                App.Console.SetStatus(name, kind, True)
            except Exception:
                pass


def recompute(doc):
    """doc.recompute() without FreeCAD's failure messages in the Report view."""
    with quiet():
        doc.recompute()


class EscapeCancels:
    """Fusion: Esc cancels the command in progress, wherever the mouse is. FreeCAD's task
    panel only sees Esc when it has the keyboard focus; this shortcut on the main
    window catches it in the 3D view too. remove() when the dialog closes."""

    def __init__(self, panel):
        import FreeCADGui as Gui

        from .compat import QtCore, QtGui

        self.panel = panel
        self.shortcut = QtGui.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key_Escape), Gui.getMainWindow()
        )
        self.shortcut.activated.connect(self._pressed)

    def _pressed(self):
        from .compat import QtCore

        QtCore.QTimer.singleShot(0, self._cancel)

    def _cancel(self):
        try:
            panel = self.panel
            if panel is not None and not getattr(panel, "_closed", True):
                panel.reject()
        except Exception as exc:
            from . import warn

            warn("Esc: %s" % exc)

    def remove(self):
        try:
            self.shortcut.setEnabled(False)
            self.shortcut.setParent(None)
            self.shortcut.deleteLater()
        except Exception:
            pass
        self.panel = None


class EnterFinishes:
    """Fusion: Enter finishes the command (OK), also with the mouse over the 3D view.
    FreeCAD's task panel only sees Enter while one of its fields has the keyboard focus
    (it then presses OK itself); this catches it over the 3D view. OK that is not
    possible yet keeps the dialog open and says why. remove() when the dialog closes."""

    def __init__(self, panel):
        import FreeCADGui as Gui

        self.panel = panel
        self.view = None
        self.callback = None
        try:
            self.view = Gui.ActiveDocument.ActiveView
            self.callback = self.view.addEventCallback("SoKeyboardEvent", self._key)
        except Exception:
            self.view = None

    def _key(self, info):
        from .compat import QtCore, QtWidgets

        try:
            if info.get("State") != "UP" or info.get("Key") not in ("RETURN", "PAD_ENTER", "ENTER"):
                return
            if QtWidgets.QApplication.mouseButtons() != QtCore.Qt.NoButton:
                return  # never while a handle is being dragged
            QtCore.QTimer.singleShot(0, self._ok)
        except Exception as exc:
            from . import warn

            warn("Enter: %s" % exc)

    def _ok(self):
        try:
            panel = self.panel
            if panel is not None and not getattr(panel, "_closed", True):
                panel.accept()
        except Exception as exc:
            from . import warn

            warn("Enter: %s" % exc)

    def remove(self):
        if self.view is not None and self.callback is not None:
            try:
                self.view.removeEventCallback("SoKeyboardEvent", self.callback)
            except Exception:
                pass
        self.view = self.callback = None
        self.panel = None


class UndoCancels:
    """Keys and document events that would pull the document from under an open dialog.

    Ctrl+Z: the step being made is what gets undone, so the dialog is cancelled (its
      preview removed). Before, FreeCAD committed the unfinished preview and undid it under
      the open dialog, which then worked on deleted objects. Text fields keep Ctrl+Z.
    Ctrl+Y: nothing to redo inside a command; ignored while the dialog is open.
    Ctrl+S, Ctrl+N, Ctrl+O: like starting any other command, the open dialog is finished
      first (OK if possible, else cancelled), so a file never holds a half-made preview.
    Undo/Redo from the toolbar still reach FreeCAD: the dialog then closes as cancelled.
    The document closed under the dialog: the dialog closes (it was left working on a
    deleted document). remove() when the dialog closes."""

    FINISH_FIRST = {"S": "Std_Save", "N": "Std_New", "O": "Std_Open"}

    def __init__(self, panel):
        from .compat import QtCore, QtWidgets

        self.panel = panel
        guard = self

        class KeyFilter(QtCore.QObject):
            def eventFilter(self, obj, event):
                return guard._filter(event)

        self.filter = KeyFilter()
        QtWidgets.QApplication.instance().installEventFilter(self.filter)

        class DocWatch:
            def slotUndoDocument(self, doc):
                guard._undone(doc)

            def slotRedoDocument(self, doc):
                guard._undone(doc)

            def slotDeletedDocument(self, doc):
                guard._document_gone(doc)

        self.watch = DocWatch()
        App.addDocumentObserver(self.watch)

    def _filter(self, event):
        from .compat import QtCore, QtGui, QtWidgets

        try:
            kind = event.type()
            if kind not in (QtCore.QEvent.ShortcutOverride, QtCore.QEvent.KeyPress):
                return False
            if not isinstance(event, QtGui.QKeyEvent) or self.panel is None:
                return False
            mods = event.modifiers()
            if not (mods & QtCore.Qt.ControlModifier) or (
                mods & (QtCore.Qt.ShiftModifier | QtCore.Qt.AltModifier)
            ):
                return False
            keys = {
                QtCore.Qt.Key_Z: "Z",
                QtCore.Qt.Key_Y: "Y",
                QtCore.Qt.Key_S: "S",
                QtCore.Qt.Key_N: "N",
                QtCore.Qt.Key_O: "O",
            }
            key = keys.get(event.key())
            if key is None:
                return False
            focus = QtWidgets.QApplication.focusWidget()
            editors = (
                QtWidgets.QLineEdit,
                QtWidgets.QAbstractSpinBox,
                QtWidgets.QTextEdit,
                QtWidgets.QPlainTextEdit,
            )
            if key in ("Z", "Y") and isinstance(focus, editors):
                return False  # undo/redo of the typing in the field
            event.accept()  # ShortcutOverride accepted: SciForge's own shortcut does not fire
            if kind == QtCore.QEvent.KeyPress and not event.isAutoRepeat():
                if key == "Z":
                    QtCore.QTimer.singleShot(0, self._cancel)
                elif key in self.FINISH_FIRST:
                    command = self.FINISH_FIRST[key]
                    QtCore.QTimer.singleShot(0, lambda: self._finish_then(command))
            return True
        except Exception:
            return False

    def _cancel(self):
        try:
            panel = self.panel
            if panel is not None and not getattr(panel, "_closed", True):
                panel.reject()
        except Exception as exc:
            from . import warn

            warn("Ctrl+Z in a dialog: %s" % exc)

    def _finish_then(self, command):
        import FreeCADGui as Gui

        try:
            panel = self.panel
            if panel is not None and not getattr(panel, "_closed", True):
                panel.finish()
            Gui.runCommand(command)
        except Exception as exc:
            from . import warn

            warn("%s with a dialog open: %s" % (command, exc))

    def _undone(self, doc):
        """Undo/redo reached the document anyway (toolbar): the preview is gone, close."""
        try:
            panel = self.panel
            if panel is None or getattr(panel, "_closed", True) or doc is not panel.doc:
                return
            panel._timer.stop()  # nothing may rebuild from the objects the undo removed
            from .compat import QtCore

            QtCore.QTimer.singleShot(0, self._close_undone)
        except Exception as exc:
            from . import warn

            warn("undo in a dialog: %s" % exc)

    def _close_undone(self):
        try:
            panel = self.panel
            if panel is None or getattr(panel, "_closed", True):
                return
            panel.target = None  # deleted by the undo
            panel.cleanup()
            panel._close()
            recompute(panel.doc)
            from . import log

            log("%s cancelled by undo" % panel.title)
        except Exception as exc:
            from . import warn

            warn("undo in a dialog: %s" % exc)

    def _document_gone(self, doc):
        """The dialog's document is being closed: drop the dialog without touching it."""
        try:
            panel = self.panel
            if panel is None or getattr(panel, "_closed", True):
                return
            if doc.Name != panel.doc.Name:
                return
            panel._timer.stop()
            panel.target = None
            try:
                panel.cleanup()
            except Exception:
                pass
            from . import taskui
            from .compat import QtCore

            if taskui._OPEN["dialog"] is panel:
                taskui._OPEN["dialog"] = None
            QtCore.QTimer.singleShot(0, _close_task_panel)
        except Exception as exc:
            from . import warn

            warn("document closed under a dialog: %s" % exc)

    def remove(self):
        from .compat import QtWidgets

        try:
            QtWidgets.QApplication.instance().removeEventFilter(self.filter)
        except Exception:
            pass
        try:
            App.removeDocumentObserver(self.watch)
        except Exception:
            pass
        self.panel = None


def _close_task_panel():
    import FreeCADGui as Gui

    try:
        if Gui.Control.activeDialog():
            Gui.Control.closeDialog()
    except Exception:
        pass


def failure(obj):
    """The error text of a feature that failed to compute, or ''."""
    if obj is None:
        return ""
    try:
        state = list(getattr(obj, "State", []))
    except Exception:
        return ""
    if "Invalid" in state or "Error" in state:
        try:
            text = obj.getStatusString()
        except Exception:
            text = ""
        return text or "This step cannot be built with these values."
    return ""
