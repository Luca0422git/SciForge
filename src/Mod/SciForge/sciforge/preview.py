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


def end_transaction(doc, abort=False):
    """Close the dialog's undo step. FreeCAD's doc.commitTransaction()/abortTransaction()
    only close a step that holds changes; a dialog OK'd or cancelled without any change
    left its name pending, and the next change anywhere (even right after an Undo) opened a
    step under that name and threw away the Redo list. The pending name is closed too.

    In a design without history (or for an open base feature's bodies) the steps the
    command made are first baked into the bodies, in this same undo step (direct.py)."""
    if not abort:
        catch_up(doc)  # the steps after the marker, in this undo step
        if _bakes(doc):
            return
    if abort:
        release(doc)
        doc.abortTransaction()
    else:
        doc.commitTransaction()
    try:
        App.closeActiveTransaction(abort)
    except Exception:
        pass


def _bakes(doc):
    """True when direct.py took over the end of the undo step (it commits a moment later)."""
    try:
        from . import direct

        return direct.takes_commit(doc)
    except Exception as exc:
        from . import warn

        warn("could not apply the change without history: %s" % exc)
        return False


def recompute(doc):
    """doc.recompute() without FreeCAD's failure messages in the Report view. While a
    dialog holds the steps after the history marker (hold()), those wait."""
    with quiet():
        names = _waiting(doc)
        if names:
            doc.recompute([o for o in doc.Objects if o.Name not in names])
        else:
            doc.recompute()


# -- the steps after the history marker wait while a dialog is open ---------------------------
# Fusion computes nothing after the history marker, and editing a step rolls the marker to it
# (Autodesk: later features are greyed out and not computed; everything is computed on the way
# forward when the edit ends). FreeCAD recomputes every step that depends on a changed one,
# wherever the marker stands: a preview while editing the first of 30 steps rebuilt all 30 on
# every change. While a SciForge dialog is open (taskui.Panel), its previews rebuild only what
# is not after the marker; the steps after it, and what depends on them (the body), wait. They
# are rebuilt once when the dialog's undo step closes (catch_up(), in that same undo step).
# taskui.edit_object rolls the marker to the step being edited, so the steps after it wait.
_HELD = {}  # document name -> names of the objects waiting


def hold(doc):
    """Make the steps after the history marker wait (a dialog opens)."""
    try:
        names = _after_marker(doc)
    except Exception as exc:
        from . import warn

        warn("previews rebuild every step: %s" % exc)
        names = set()
    if names:
        _HELD[doc.Name] = frozenset(names)
    else:
        _HELD.pop(doc.Name, None)


def catch_up(doc):
    """The dialog is done: the steps that waited are rebuilt now. True when some waited."""
    try:
        name = doc.Name
    except Exception:
        return False  # the document was closed
    if _HELD.pop(name, None) is None:
        return False
    recompute(doc)
    return True


def release(doc):
    """Forget the waiting steps without rebuilding them (the dialog was cancelled: they go
    back to what they were with the undo step)."""
    try:
        _HELD.pop(doc.Name, None)
    except Exception:
        pass


def holding(doc):
    try:
        return doc.Name in _HELD
    except Exception:
        return False


def _after_marker(doc):
    from . import timeline_ops

    timeline = timeline_ops.timeline(doc, deps=False)
    names = set()
    for item in timeline.items:
        if item.state != "rolled_back":
            continue
        obj = doc.getObject(item.name)
        if obj is None:
            continue
        names.add(obj.Name)
        names.update(o.Name for o in obj.InListRecursive)
    return names


def _waiting(doc):
    """The objects that wait now: the held ones, except the open dialog's own step(s) and
    what they are built on (a dialog may open on a step that is after the marker)."""
    try:
        names = _HELD.get(doc.Name)
    except Exception:
        return None
    if not names:
        return None
    try:
        from . import taskui

        panel = taskui.current()
        own = [panel.feature()] if panel is not None else []
        own += [getattr(m, "target", None) for m in getattr(panel, "members", [])]
        keep = set()
        for obj in own:
            if obj is None or obj.Document is not doc:
                continue
            keep.add(obj.Name)
            keep.update(o.Name for o in obj.OutListRecursive)
        if keep & names:
            names = names - keep
    except Exception:
        pass
    return names


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

    def press(self):
        """Esc pressed somewhere that keeps the key to itself (the value box next to an
        arrow): cancel just the same, once the key has been handled."""
        self._pressed()

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


class FormulaInput:
    """Fusion's value fields take a parameter or a formula ("width", "width*2 + 5 mm"), and
    the value then follows the parameter. FreeCAD's number field only takes numbers (it
    silently put the old value back), so the text typed in `field` (a taskui.DistanceField)
    is caught here and handed to the panel:

      panel.formula_typed(key, text, value)   a formula, already evaluated (field shows value)
      panel.formula_cleared(key)              a plain number typed: no formula any more
      panel.formula_failed(key, message)      no value (a typo, wrong units...)

    A formula of another kind than the field (a length in an angle field) is no value, like
    in Fusion: the field's ``unit`` ("mm", "deg", "" for a number) says what it takes.
    """

    def __init__(self, panel, key, field):
        from .compat import QtWidgets

        self.panel = panel
        self.key = key
        self.field = field
        self.unit = getattr(field, "unit", None)
        self.raw = None
        edit = field.widget.findChild(QtWidgets.QLineEdit)
        if edit is not None:
            edit.textEdited.connect(self._edited)
        field.widget.editingFinished.connect(self._finished)

    def _edited(self, text):
        self.raw = text

    def take(self, text):
        """`text` typed for this field somewhere else (the value box next to the arrow in the
        3D view): taken exactly as if typed in the field and Enter pressed. A plain number
        ("25", "1 in") is a value, anything else a formula. True if it gave a value."""
        panel = self.panel
        if getattr(panel, "_closed", True):
            return False
        text = (text or "").strip().lstrip("=").strip()
        if not text:
            return False
        try:
            from . import extrude, parameters

            if parameters.is_plain_number(text):
                try:
                    value = self.field.parse(text)
                except ValueError as exc:
                    panel.formula_failed(self.key, str(exc))
                    return False
                self.field.take(value)
                panel.formula_cleared(self.key)
                return True
            try:
                value = extrude.evaluate(panel.doc, text, self.unit)
            except extrude.ExtrudeError as exc:
                panel.formula_failed(self.key, str(exc))
                return False
            self.field.set_value(value)
            panel.formula_typed(self.key, text, value)
            return True
        except Exception as exc:
            from . import warn

            warn("value %r: %s" % (text, exc))
            return False

    def _finished(self):
        raw, self.raw = self.raw, None
        panel = self.panel
        if raw is None or getattr(panel, "_closed", True):
            return
        text = raw.strip().lstrip("=").strip()
        try:
            from . import extrude, parameters

            if not text or parameters.is_plain_number(text):
                panel.formula_cleared(self.key)
                return
            try:
                value = extrude.evaluate(panel.doc, text, self.unit)
            except extrude.ExtrudeError as exc:
                panel.formula_failed(self.key, str(exc))
                return
            self.field.set_value(value)
            panel.formula_typed(self.key, text, value)
        except Exception as exc:
            from . import warn

            warn("formula %r: %s" % (text, exc))


def set_formula(obj, prop, text):
    """Put a formula typed in a dialog (bare parameter names) on obj.prop as an expression,
    or remove the expression when `text` is empty."""
    from . import parameters, parameters_core

    if obj is None or prop not in obj.PropertiesList:
        return
    engine = dict(obj.ExpressionEngine)
    if text:
        expr = parameters_core.to_freecad(text, parameters.user_names(obj.Document))
        if engine.get(prop) != expr:
            obj.setExpression(prop, expr)
    elif prop in engine:
        obj.setExpression(prop, None)


def formula_of(obj, prop):
    """The formula (bare parameter names) driving obj.prop, or ''."""
    from . import parameters_core

    try:
        expr = dict(obj.ExpressionEngine).get(prop, "")
    except Exception:
        return ""
    return parameters_core.from_freecad(expr) if expr else ""


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
            from . import commands

            Gui.runCommand(commands.preferred(command))
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
            try:
                App.closeActiveTransaction(True)  # the dialog's pending step name
            except Exception:
                pass
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
