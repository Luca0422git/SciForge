# SPDX-License-Identifier: LGPL-2.1-or-later
"""Compute All (MODIFY > Compute All, Ctrl+B), Fusion-style: every parameter and every step of
the design is computed again from the start, with a progress message while it runs, then a
summary: how many steps, how long, and the steps that failed or warn with the reason, each
one found in the timeline with a click. Sources: docs/sciforge/parity/misc.md.
"""

import time

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, log, ui_icon, ui_icon_path, warn
from .compute_core import ordered, summary_words
from .compat import QtCore, QtWidgets

_state = {"dialog": None}


def _steps(doc):
    from . import timeline_ops

    try:
        return [obj for obj, _body in timeline_ops.steps(doc)]
    except Exception:
        return []


def problems(doc):
    """[(object name, label, "error" | "warning", reason)] of the steps, in timeline order."""
    from . import timeline_ops

    found = []
    for obj in _steps(doc):
        try:
            if timeline_ops.is_suppressed(obj):
                continue
            kind, reason = timeline_ops.problem(obj)
        except Exception:
            continue
        if kind:
            found.append((obj.Name, obj.Label, kind, reason))
    return found


def _status(text):
    try:
        Gui.getMainWindow().statusBar().showMessage(text, 6000)
    except Exception:
        pass


def compute_all(doc):
    """Touch everything and recompute (quietly: failures are shown in the timeline, never as
    Report-view errors). Returns (step count, seconds, problems)."""
    from . import timeline_ops

    steps = _steps(doc)
    _status("Computing all %d steps of %s..." % (len(steps), doc.Label))
    QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
    QtWidgets.QApplication.processEvents()
    start = time.perf_counter()
    try:
        for obj in doc.Objects:
            try:
                obj.touch()
            except Exception:
                pass
        timeline_ops.recompute(doc)
    finally:
        QtWidgets.QApplication.restoreOverrideCursor()
    seconds = time.perf_counter() - start
    found = ordered(problems(doc))
    words = summary_words(len(steps), seconds, found)
    _status(words)
    log(words)
    return len(steps), seconds, found


class SummaryDialog(QtWidgets.QDialog):
    """The steps that failed or warn after Compute All; double-click (or Find in Timeline)
    selects the step in the timeline."""

    last = None

    def __init__(self, doc, words, found, parent=None):
        super().__init__(parent or Gui.getMainWindow())
        SummaryDialog.last = self
        self.doc_name = doc.Name
        self.setObjectName("SciForgeComputeAll")
        self.setWindowTitle("Compute All")
        self.setWindowIcon(ui_icon("compute"))
        self.resize(560, 300)
        layout = QtWidgets.QVBoxLayout(self)
        self.words = QtWidgets.QLabel(words)
        self.words.setObjectName("SciForgeComputeAllSummary")
        self.words.setWordWrap(True)
        layout.addWidget(self.words)
        self.list = QtWidgets.QTreeWidget()
        self.list.setObjectName("SciForgeComputeAllList")
        self.list.setHeaderLabels(["Step", "", "Why"])
        self.list.setRootIsDecorated(False)
        for name, label, kind, reason in found:
            item = QtWidgets.QTreeWidgetItem(
                self.list, [label, "Error" if kind == "error" else "Warning", reason]
            )
            item.setData(0, QtCore.Qt.UserRole, name)
            item.setToolTip(2, reason)
        for c in range(3):
            self.list.resizeColumnToContents(c)
        self.list.itemDoubleClicked.connect(lambda *_: self.find_selected())
        layout.addWidget(self.list, 1)
        row = QtWidgets.QHBoxLayout()
        self.find_button = QtWidgets.QPushButton("Find in Timeline")
        self.find_button.setObjectName("SciForgeComputeAllFind")
        self.find_button.clicked.connect(self.find_selected)
        close = QtWidgets.QPushButton("Close")
        close.setObjectName("SciForgeComputeAllClose")
        close.clicked.connect(self.reject)
        row.addWidget(self.find_button)
        row.addStretch(1)
        row.addWidget(close)
        layout.addLayout(row)
        if self.list.topLevelItemCount():
            self.list.setCurrentItem(self.list.topLevelItem(0))

    def find_selected(self):
        item = self.list.currentItem()
        if item is None:
            return False
        name = item.data(0, QtCore.Qt.UserRole)
        try:
            from . import timeline_ui

            return timeline_ui.find(name)
        except Exception as exc:
            warn("Compute All: %s" % exc)
            return False


def run():
    doc = App.ActiveDocument
    if doc is None:
        commands.tell("Open a design first: Compute All computes the open design again.")
        return None
    if not commands.finish_open_dialog():
        return None
    count, seconds, found = compute_all(doc)
    words = summary_words(count, seconds, found)
    old = _state.get("dialog")
    try:
        if old is not None:
            old.close()
    except RuntimeError:
        pass
    _state["dialog"] = None
    if not found:
        commands.tell(words)
        return None
    dialog = SummaryDialog(doc, words, found)
    _state["dialog"] = dialog

    def closed(*_):
        from . import preferences_ui

        QtCore.QTimer.singleShot(0, preferences_ui.refocus_main)

    dialog.finished.connect(closed)
    dialog.show()
    return dialog


class ComputeAllCommand:
    def GetResources(self):
        return {
            "MenuText": "Compute All",
            "ToolTip": "Compute every parameter and step of the design again (Ctrl+B); the "
            "steps that fail are listed",
            "Pixmap": ui_icon_path("compute"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            run()
        except Exception as exc:
            warn("Compute All: %s" % exc)
            commands.tell("Compute All did not finish: %s" % exc)


COMMANDS = {"SciForge_ComputeAll": ComputeAllCommand}
