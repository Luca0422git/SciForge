# SPDX-License-Identifier: LGPL-2.1-or-later
"""The slim lines at the top of Home, under the recovery banner and in its style (brief
docs/sciforge/dev/briefs/beta-release.md, R2 and R4):

  * after a session that did not end cleanly:
        SciForge closed unexpectedly last time.   [Report it] [Dismiss]
  * the first time SciForge starts:
        Welcome to SciForge 0.1.0-beta. It works like Fusion: the ribbon, the timeline, S for
        search. This is a beta: save often.   [Cheat sheet] [Open an example]
        [Report a problem] [x]
No popup, no tour. home_ui.HomeView holds one Notices widget; each line hides itself when
there is nothing to say. The rules are notices_core.py, the crash log is crashlog.py.

Test seams: OPEN_URL (a function taking an address, for the cheat sheet when its file is
missing; None = the browser).
"""

import os
import shutil

from . import ROOT, __version__, log, warn
from . import notices_core as core
from .compat import QtCore, QtGui, QtWidgets

ROOT_OF_MODULE = os.path.dirname(ROOT)  # src/Mod/SciForge (installed: Mod/SciForge)
PREFS = "User parameter:BaseApp/Preferences/Mod/SciForge"
OPEN_URL = None

# the recovery banner's look (home_ui: #SciForgeHomeRecovery); %s is the line's object name
QSS = """
#%s { background: #5a4a2a; border-radius: 3px; }
#SciForgeHomeNoticeText { background: transparent; }
"""

_state = {"welcome": None, "sheet": None}


# -- the welcome flag -----------------------------------------------------------------------
def _get_flag():
    import FreeCAD as App

    return App.ParamGet(PREFS).GetBool(core.WELCOME_FLAG, False)


def _set_flag(value):
    import FreeCAD as App

    App.ParamGet(PREFS).SetBool(core.WELCOME_FLAG, bool(value))


def welcome():
    if _state["welcome"] is None:
        _state["welcome"] = core.Welcome(_get_flag, _set_flag)
    return _state["welcome"]


def reset_for_tests(shown=True):
    """The scenario harness: later scenarios of a shared profile start without the welcome
    line (shown=True: the flag says it was shown); a scenario that wants it sets the flag
    False and calls this with shown=False."""
    try:
        _set_flag(shown)
        welcome().reset()
        page = _page()
        if page is not None:
            page.refresh()
    except Exception as exc:
        warn("home notices: %s" % exc)


def _page():
    try:
        from . import home_ui

        view = home_ui.view()
        return getattr(view, "notices", None) if view is not None else None
    except Exception:
        return None


# -- the lines ----------------------------------------------------------------------------------
class Line(QtWidgets.QFrame):
    """One slim line: a text and a few buttons."""

    def __init__(self, name, buttons):
        super().__init__()
        self.setObjectName(name)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setStyleSheet(QSS % name)
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(12, 6, 8, 6)
        row.setSpacing(6)
        self.text = QtWidgets.QLabel("")
        self.text.setObjectName("SciForgeHomeNoticeText")
        self.text.setWordWrap(True)
        row.addWidget(self.text, 1)
        self.buttons = {}
        for label, button_name, callback in buttons:
            button = QtWidgets.QPushButton(label)
            button.setObjectName(button_name)
            button.setFocusPolicy(QtCore.Qt.NoFocus)
            # (a button's own click runs a moment later, as Home's buttons do: a command that
            # opens a dialog must not run inside the click)
            button.clicked.connect(lambda *_, cb=callback: QtCore.QTimer.singleShot(0, cb))
            row.addWidget(button)
            self.buttons[button_name] = button
        self.hide()


class Notices(QtWidgets.QWidget):
    """What Home says besides its designs: the crash line, then the welcome line."""

    def __init__(self):
        super().__init__()
        self.setObjectName("SciForgeHomeNotices")
        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(6)
        self.crash = Line(
            "SciForgeHomeCrash",
            [
                ("Report it", "SciForgeHomeCrashReport", report),
                ("Dismiss", "SciForgeHomeCrashDismiss", self.dismiss_crash),
            ],
        )
        self.crash.text.setText(core.CRASH_TEXT)
        self.welcome = Line(
            "SciForgeHomeWelcome",
            [
                ("Cheat sheet", "SciForgeHomeWelcomeSheet", open_cheat_sheet),
                ("Open an example", "SciForgeHomeWelcomeExample", open_example),
                ("Report a problem", "SciForgeHomeWelcomeReport", report),
                ("x", "SciForgeHomeWelcomeClose", self.close_welcome),
            ],
        )
        close = self.welcome.buttons["SciForgeHomeWelcomeClose"]
        close.setFixedWidth(28)
        close.setStyleSheet("padding: 4px 0px;")
        close.setToolTip("Hide this for good")
        self.welcome.text.setText(core.welcome_text(__version__))
        if not core.module_file(ROOT_OF_MODULE, core.EXAMPLE_FILE):
            self.welcome.buttons["SciForgeHomeWelcomeExample"].hide()  # not installed: no button
        column.addWidget(self.crash)
        column.addWidget(self.welcome)
        self.refresh()

    def refresh(self):
        """Show each line when it has something to say."""
        try:
            from . import crashlog

            self.crash.setVisible(bool(crashlog.pending()))
        except RuntimeError:
            return
        except Exception as exc:
            warn("home notices: crash line: %s" % exc)
        try:
            self.welcome.setVisible(welcome().visible())
        except RuntimeError:
            return
        except Exception as exc:
            warn("home notices: welcome line: %s" % exc)

    def showEvent(self, event):
        super().showEvent(event)
        QtCore.QTimer.singleShot(0, self._refresh_safely)

    def _refresh_safely(self):
        try:
            self.refresh()
        except RuntimeError:
            pass
        except Exception as exc:
            warn("home notices: %s" % exc)

    def dismiss_crash(self):
        try:
            from . import crashlog

            crashlog.dismiss()
            log("home: the unexpected-close line was dismissed")
        except Exception as exc:
            warn("home notices: dismiss: %s" % exc)
        self._refresh_safely()

    def close_welcome(self):
        try:
            welcome().close()
            log("home: the welcome line was hidden for good")
        except Exception as exc:
            warn("home notices: %s" % exc)
        self._refresh_safely()


# -- what the buttons do ---------------------------------------------------------------------
def report():
    """Report it / Report a problem: the dialog (report_ui)."""
    try:
        from . import report_ui

        report_ui.open_dialog()
    except Exception as exc:
        warn("home notices: report: %s" % exc)


def open_url(url):
    if OPEN_URL is not None:
        return OPEN_URL(url)
    return QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))


class CheatSheet(QtWidgets.QDialog):
    """The cheat sheet shown in a window of its own, so it opens without a browser, a Markdown
    program or an internet connection."""

    def __init__(self, parent, markdown):
        super().__init__(parent)
        self.setObjectName("SciForgeCheatSheet")
        self.setWindowTitle("SciForge cheat sheet")
        self.resize(820, 700)
        column = QtWidgets.QVBoxLayout(self)
        self.browser = QtWidgets.QTextBrowser()
        self.browser.setObjectName("SciForgeCheatSheetText")
        self.browser.setOpenLinks(False)
        self.browser.setMarkdown(markdown)
        self.browser.anchorClicked.connect(self._link)
        column.addWidget(self.browser, 1)
        row = QtWidgets.QHBoxLayout()
        row.addStretch(1)
        close = QtWidgets.QPushButton("Close")
        close.setObjectName("SciForgeCheatSheetClose")
        close.clicked.connect(self.close)
        row.addWidget(close)
        column.addLayout(row)

    def _link(self, url):
        try:
            if url.scheme() in ("http", "https"):
                open_url(url.toString())
        except Exception as exc:
            warn("cheat sheet: %s" % exc)


def cheat_sheet_dialog():
    page = _state["sheet"]
    try:
        if page is not None and page.isVisible():
            return page
    except RuntimeError:
        pass
    return None


def open_cheat_sheet():
    """[Cheat sheet]: the module's own copy in a window; the page on GitHub when the copy is
    missing."""
    try:
        import FreeCADGui as Gui

        shown = cheat_sheet_dialog()
        if shown is not None:
            shown.raise_()
            return shown
        path = core.module_file(ROOT_OF_MODULE, core.CHEAT_SHEET_FILE)
        if not path:
            warn("cheat sheet: %s is not installed, opening it on GitHub" % core.CHEAT_SHEET_FILE)
            open_url(core.CHEAT_SHEET_URL)
            return None
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
        page = CheatSheet(Gui.getMainWindow(), text)
        page.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        _state["sheet"] = page
        page.show()
        log("home: cheat sheet opened")
        return page
    except Exception as exc:
        warn("home notices: cheat sheet: %s" % exc)
        return None


def open_example():
    """[Open an example]: the Raspberry Pi 5 case. It is copied once to SciForge's folder
    (the installed copy may be somewhere that cannot be written; an earlier copy, which
    the person may have changed, is never overwritten) and opened from there."""
    try:
        import FreeCAD as App

        from . import home_ui

        source = core.module_file(ROOT_OF_MODULE, core.EXAMPLE_FILE)
        if not source:
            warn("example: %s is not installed" % core.EXAMPLE_FILE)
            return None
        target = core.example_copy_target(App.getUserAppDataDir())
        if not os.path.isfile(target):
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copyfile(source, target)
        log("home: opening the example %s" % target)
        return home_ui.open_design(target)
    except Exception as exc:
        warn("home notices: example: %s" % exc)
        return None
