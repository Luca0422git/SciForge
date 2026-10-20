# SPDX-License-Identifier: LGPL-2.1-or-later
"""The update lines at the top of the Home tab (brief beta-release.md, R3):

  "SciForge 0.1.0-beta.2 is available.   [What's new] [Update now] [Later]"
  "Updated to 0.1.0-beta.2.   [What's new] [Dismiss]"     (the first start after an update)

One slim line in the look of Home's recovery banner, no popup. home_ui.py only calls
attach() when it builds its page; update_ui.py calls changed() when what the line says
changes. Every handler is guarded: a problem here never reaches Home."""

import weakref

from . import theme, warn
from .compat import QtCore, QtWidgets

# Written with the dark colours: the style sheet hook (theme.translate) swaps them in the light look.
QSS = """
#SciForgeHomeUpdate {{ background: {active}; border-radius: 3px; }}
#SciForgeHomeUpdateText {{ color: {text}; }}
#SciForgeHomeUpdateNow {{ background: {accent}; color: #ffffff; border: none; font-weight: bold;
    padding: 4px 14px; border-radius: 2px; }}
#SciForgeHomeUpdateNow:hover {{ background: #5bb8f7; }}
#SciForgeHomeUpdateLink {{ color: {accent}; background: transparent; border: none; padding: 4px 8px; }}
#SciForgeHomeUpdateLink:hover {{ color: #5bb8f7; }}
"""

_lines = []  # weak references to the lines of every Home page


class UpdateLine(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SciForgeHomeUpdate")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setStyleSheet(QSS.format(**theme.DARK))
        self.mode = ""  # "" (hidden) | "available" | "updated"
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(12, 5, 8, 5)
        row.setSpacing(6)
        self.text = QtWidgets.QLabel("")
        self.text.setObjectName("SciForgeHomeUpdateText")
        row.addWidget(self.text, 1)
        self.whats_new_button = self._button("What's new", "SciForgeHomeUpdateLink", _whats_new)
        self.update_button = self._button("Update now", "SciForgeHomeUpdateNow", _update_now)
        self.later_button = self._button("Later", "SciForgeHomeUpdateLink", _later)
        self.dismiss_button = self._button("Dismiss", "SciForgeHomeUpdateLink", _dismiss)
        for button in (
            self.whats_new_button,
            self.update_button,
            self.later_button,
            self.dismiss_button,
        ):
            row.addWidget(button)
        self.hide()

    def _button(self, label, name, handler):
        button = QtWidgets.QPushButton(label)
        button.setObjectName(name)
        button.setCursor(QtCore.Qt.PointingHandCursor)
        button.setFocusPolicy(QtCore.Qt.NoFocus)
        button.clicked.connect(lambda *_: QtCore.QTimer.singleShot(0, handler))
        return button

    def refresh(self):
        from . import update_ui

        version, done = update_ui.available(), update_ui.updated()
        if done:
            self.mode = "updated"
            self.text.setText("Updated to %s." % done)
        elif version:
            self.mode = "available"
            self.text.setText("SciForge %s is available." % version)
        else:
            self.mode = ""
        available = self.mode == "available"
        self.update_button.setVisible(available)
        self.later_button.setVisible(available)
        self.dismiss_button.setVisible(self.mode == "updated")
        self.whats_new_button.setVisible(bool(self.mode))
        self.setVisible(bool(self.mode))


def _guarded(call):
    try:
        call()
    except Exception as exc:
        warn("home: update line: %s" % exc)


def _whats_new():
    from . import update_ui

    _guarded(lambda: update_ui.whats_new(update_ui.available() or update_ui.updated()))


def _update_now():
    from . import update_ui

    _guarded(update_ui.install_now)


def _later():
    from . import update_ui

    _guarded(update_ui.later)


def _dismiss():
    from . import update_ui

    _guarded(update_ui.dismiss_updated)


def attach(view, column):
    """Home's page asks for its line (right under the heading); the page keeps it as
    ``view.update_line``."""
    try:
        line = UpdateLine()
        column.addWidget(line)
        view.update_line = line
        _lines.append(weakref.ref(line))
        line.refresh()
    except Exception as exc:
        warn("home: update line: %s" % exc)


def changed():
    """What the line says may have changed: every Home page's line looks again."""
    for ref in list(_lines):
        line = ref()
        if line is None:
            _lines.remove(ref)
            continue
        try:
            line.refresh()
        except RuntimeError:  # (the tab was closed)
            _lines.remove(ref)
        except Exception as exc:
            warn("home: update line: %s" % exc)
