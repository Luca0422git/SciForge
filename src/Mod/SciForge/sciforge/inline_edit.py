# SPDX-License-Identifier: LGPL-2.1-or-later
"""The name field that opens in place to rename something (timeline step, browser
row), like Fusion's: Enter keeps the new name, Esc cancels, clicking elsewhere
keeps it. The 3D view takes the keyboard focus back right after a selection
change; the field ignores that for a moment instead of closing under the user."""
from .compat import QtCore, QtWidgets

GRACE_MS = 600


class InlineEditor(QtCore.QObject):
    def __init__(self, parent, rect, text, on_commit, name="SciForgeRename"):
        super().__init__(parent)
        self.on_commit = on_commit
        self._done = False
        self._clock = QtCore.QElapsedTimer()
        self._clock.start()
        self.field = QtWidgets.QLineEdit(parent)
        self.field.setObjectName(name)
        self.field.setText(text)
        self.field.selectAll()
        self.field.setGeometry(rect)
        self.field.setStyleSheet(
            "QLineEdit { background: #2a2a2a; border: 1px solid #63b3ff; padding: 1px 3px; }"
        )
        self.field.installEventFilter(self)
        self.field.returnPressed.connect(self.commit)
        self.field.show()
        self.field.setFocus()

    def is_open(self):
        return not self._done

    def eventFilter(self, obj, event):
        try:
            return self._filter(obj, event)
        except Exception:  # never let an exception out of Qt's event handling
            return False

    def _filter(self, obj, event):
        if self._done or obj is not self.field:
            return False
        if event.type() == QtCore.QEvent.KeyPress and event.key() == QtCore.Qt.Key_Escape:
            self.cancel()
            return True
        if event.type() == QtCore.QEvent.FocusOut:
            if self._clock.elapsed() < GRACE_MS or event.reason() in (
                QtCore.Qt.PopupFocusReason,
                QtCore.Qt.ActiveWindowFocusReason,
                QtCore.Qt.MenuBarFocusReason,
            ):
                QtCore.QTimer.singleShot(0, self._refocus)
            else:
                QtCore.QTimer.singleShot(0, self.commit)
        return False

    def _refocus(self):
        if not self._done:
            try:
                self.field.setFocus()
            except RuntimeError:
                pass

    def commit(self):
        if self._done:
            return
        text = self.field.text()
        self._close()
        self.on_commit(text)

    def cancel(self):
        if not self._done:
            self._close()
            self.on_commit(None)

    def _close(self):
        self._done = True
        try:
            self.field.removeEventFilter(self)
            self.field.hide()
            self.field.deleteLater()
        except RuntimeError:
            pass
