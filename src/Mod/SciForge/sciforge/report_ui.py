# SPDX-License-Identifier: LGPL-2.1-or-later
"""Help > Report a Problem (brief docs/sciforge/dev/briefs/beta-release.md, R2).

A small dialog: what happened (required), what was expected (optional), "Include the last
crash log" (ticked when there is one) and a read-only preview of exactly what a report
holds: the version, the system (OS, Qt, graphics card, screen scaling), SciForge's
Diagnostics, its last 200 messages and the end of the crash log, all redacted (report_core:
the home folder, the user name and anything like an API key are gone). Three buttons:
  * Open on GitHub: the browser opens the new-issue form with the fields filled in; the whole
    report is on the clipboard too (a long log does not fit into an address);
  * Save report...: SciForge-report-<date>.txt, on the Desktop by default;
  * Copy: everything to the clipboard.
SciForge sends nothing itself: the browser does the GitHub part, after the person has seen
the report. The AI chat and the stored keys are never part of it.

Test seams: OPEN_URL (a function taking the address; None = the real browser),
SAVE_PICKER (a function taking the default file path and returning the path to write, or "";
None = the Save dialog), IDENTITY (a function returning (home folder, user name)).
"""

import os
import platform
import sys
import time

from . import RECENT, __version__, commands, log, warn
from .compat import QtCore, QtGui, QtWidgets
from . import report_core as core

OPEN_URL = None
SAVE_PICKER = None
IDENTITY = None

HINT = "Write what happened above, then Open on GitHub, Save report and Copy are ready."

_state = {"dialog": None, "gl": None}


# -- what a report holds -------------------------------------------------------------------------
def identity():
    """(home folder, user name) of this person, for redaction."""
    if IDENTITY is not None:
        return IDENTITY()
    home, user = "", ""
    try:
        home = os.path.expanduser("~")
        if home == "~":
            home = ""
    except Exception:
        pass
    try:
        import getpass

        user = getpass.getuser()
    except Exception:
        user = os.environ.get("USERNAME") or os.environ.get("USER") or ""
    return home, user


def gl_info():
    """ "renderer / vendor / version" of the graphics card, from the 3D view's OpenGL
    context when there is one (else a context of its own, else "unknown"). Read once."""
    if _state["gl"] is not None:
        return _state["gl"]
    text = "unknown"
    try:
        text = _read_gl() or "unknown"
    except Exception as exc:
        warn("report: OpenGL info: %s" % exc)
    _state["gl"] = text
    return text


def _gl_strings(functions):
    out = []
    for name in (0x1F01, 0x1F00, 0x1F02):  # RENDERER, VENDOR, VERSION
        value = functions.glGetString(name)
        if isinstance(value, (bytes, bytearray)):
            value = bytes(value).decode("utf-8", "replace")
        out.append(str(value or "").strip("\x00 "))
    return " / ".join(part for part in out if part)


def _read_gl():
    import FreeCADGui as Gui

    from PySide6 import QtOpenGLWidgets

    main = Gui.getMainWindow()
    for widget in main.findChildren(QtOpenGLWidgets.QOpenGLWidget):
        if widget.isValid():
            widget.makeCurrent()
            try:
                text = _gl_strings(widget.context().functions())
            finally:
                widget.doneCurrent()
            if text:
                return text
    context = QtGui.QOpenGLContext()
    if not context.create():
        return ""
    surface = QtGui.QOffscreenSurface()
    surface.setFormat(context.format())
    surface.create()
    if not context.makeCurrent(surface):
        return ""
    try:
        return _gl_strings(context.functions())
    finally:
        context.doneCurrent()


def screen_info():
    try:
        app = QtWidgets.QApplication.instance()
        screens = app.screens()
        screen = app.primaryScreen()
        size = screen.size()
        scale = int(round(screen.devicePixelRatio() * 100))
        dpi = screen.logicalDotsPerInch()
        text = "%dx%d, scaling %d%% (%d dpi)" % (size.width(), size.height(), scale, round(dpi))
        if len(screens) > 1:
            text += ", %d screens" % len(screens)
        return text
    except Exception:
        return "unknown"


def os_info():
    try:
        text = platform.platform()
        if sys.platform.startswith("win"):
            version = platform.win32_ver()
            text = "Windows %s (%s) %s" % (version[0], version[1], platform.machine())
        return text
    except Exception:
        return sys.platform


def system_text():
    """The OS, Qt, graphics card and screen, one per line."""
    try:
        qt = QtCore.qVersion()
    except Exception:
        qt = "unknown"
    lines = [
        "OS: %s" % os_info(),
        "Qt: %s" % qt,
        "OpenGL: %s" % gl_info(),
        "Screen: %s" % screen_info(),
    ]
    return "\n".join(lines)


def version_text():
    try:
        from . import build_info

        build = "%s %s" % (build_info.COMMIT, build_info.DATE)
    except Exception:
        build = "unknown build"
    return "%s (%s)" % (__version__, build.strip())


def crash_file():
    """(session id, path) of the last crash log, or None."""
    try:
        from . import crashlog

        return crashlog.last_crash_log()
    except Exception:
        return None


def gather():
    """The parts of a report that do not depend on what the person types."""
    from . import crashlog, diagnostics

    parts = {
        "version": version_text(),
        "system": system_text(),
        "recent": list(RECENT[-200:]),
        "crash": crash_file(),
    }
    try:
        text = diagnostics.report(recent_lines=0)
    except Exception as exc:
        text = "(Diagnostics could not be read: %s)" % exc
    try:
        unclean = crashlog.pending()
        if unclean:
            text += "\n\nThe session before this one did not end cleanly (%s)." % ", ".join(
                s["when"] for s in unclean
            )
    except Exception:
        pass
    parts["diagnostics"] = text
    return parts


def build(parts, what, expected, include_crash):
    """The report for what the person typed (report_core.make, redacted)."""
    home, user = identity()
    crash_name, crash_text = "", ""
    if include_crash and parts.get("crash"):
        sid, path = parts["crash"]
        try:
            from . import crashlog

            crash_text = crashlog.tail(path) or "(the crash log is empty)"
            crash_name = os.path.basename(path)
        except Exception:
            crash_text = ""
    return core.make(
        what,
        expected,
        parts["version"],
        parts["system"],
        parts["diagnostics"],
        parts["recent"],
        crash_name,
        crash_text,
        home,
        user,
    )


# -- the dialog ---------------------------------------------------------------------------------
def default_save_path():
    """SciForge-report-<date>.txt on the Desktop (the home folder when there is no Desktop)."""
    folder = ""
    try:
        folder = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DesktopLocation)
    except Exception:
        pass
    if not folder or not os.path.isdir(folder):
        folder = os.path.expanduser("~")
    return os.path.join(folder, "SciForge-report-%s.txt" % time.strftime("%Y-%m-%d"))


def open_url(url):
    """The address in the browser (the seam OPEN_URL replaces it in tests)."""
    if OPEN_URL is not None:
        return OPEN_URL(url)
    return QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))


class ReportDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SciForgeReportDialog")
        self.setWindowTitle("Report a Problem")
        self.resize(760, 680)
        self.parts = gather()
        self.report = None
        column = QtWidgets.QVBoxLayout(self)
        intro = QtWidgets.QLabel(
            "Tell us what went wrong. Below is everything a report holds, so you can see it "
            "first. SciForge sends nothing by itself: Open on GitHub opens your browser (you "
            "need a free GitHub account for that); Save or Copy work without one."
        )
        intro.setObjectName("SciForgeReportIntro")
        intro.setWordWrap(True)
        column.addWidget(intro)

        column.addWidget(QtWidgets.QLabel("What happened?"))
        self.what = QtWidgets.QPlainTextEdit()
        self.what.setObjectName("SciForgeReportWhat")
        self.what.setPlaceholderText("For example: I pressed Q on a face and SciForge closed.")
        self.what.setFixedHeight(96)
        column.addWidget(self.what)

        column.addWidget(QtWidgets.QLabel("What did you expect? (optional)"))
        self.expected = QtWidgets.QPlainTextEdit()
        self.expected.setObjectName("SciForgeReportExpected")
        self.expected.setFixedHeight(56)
        column.addWidget(self.expected)

        crash = self.parts.get("crash")
        self.crash_box = QtWidgets.QCheckBox("Include the last crash log")
        self.crash_box.setObjectName("SciForgeReportCrash")
        if crash:
            self.crash_box.setChecked(True)
            self.crash_box.setToolTip(os.path.basename(crash[1]))
        else:
            self.crash_box.setEnabled(False)
            self.crash_box.setText("Include the last crash log (there is none)")
        column.addWidget(self.crash_box)

        column.addWidget(QtWidgets.QLabel("What will be included:"))
        self.preview = QtWidgets.QPlainTextEdit()
        self.preview.setObjectName("SciForgeReportPreview")
        self.preview.setReadOnly(True)
        self.preview.setFont(QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont))
        self.preview.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        column.addWidget(self.preview, 1)

        self.status = QtWidgets.QLabel("")
        self.status.setObjectName("SciForgeReportStatus")
        self.status.setWordWrap(True)
        column.addWidget(self.status)

        row = QtWidgets.QHBoxLayout()
        self.open_button = QtWidgets.QPushButton("Open on GitHub")
        self.open_button.setObjectName("SciForgeReportOpen")
        self.open_button.setDefault(True)
        self.save_button = QtWidgets.QPushButton("Save report...")
        self.save_button.setObjectName("SciForgeReportSave")
        self.copy_button = QtWidgets.QPushButton("Copy")
        self.copy_button.setObjectName("SciForgeReportCopy")
        self.close_button = QtWidgets.QPushButton("Close")
        self.close_button.setObjectName("SciForgeReportClose")
        row.addWidget(self.open_button)
        row.addWidget(self.save_button)
        row.addWidget(self.copy_button)
        row.addStretch(1)
        row.addWidget(self.close_button)
        column.addLayout(row)

        self.what.textChanged.connect(self.update)
        self.expected.textChanged.connect(self.update)
        self.crash_box.toggled.connect(self.update)
        self.open_button.clicked.connect(lambda *_: self.on_open())
        self.save_button.clicked.connect(lambda *_: self.on_save())
        self.copy_button.clicked.connect(lambda *_: self.on_copy())
        self.close_button.clicked.connect(self.close)
        self.update()

    def update(self, *_args):
        """The preview and the buttons follow what is typed."""
        try:
            self.report = build(
                self.parts,
                self.what.toPlainText(),
                self.expected.toPlainText(),
                self.crash_box.isChecked(),
            )
            self.preview.setPlainText(self.report["text"])
            ready = bool(self.what.toPlainText().strip())
            for button in (self.open_button, self.save_button, self.copy_button):
                button.setEnabled(ready)
                button.setToolTip("" if ready else "Say what happened first.")
            if not ready:
                self.say(HINT)
            elif self.status.text() == HINT:
                self.say("")
        except RuntimeError:
            pass
        except Exception as exc:
            warn("report: %s" % exc)

    def say(self, text):
        self.status.setText(text)

    # -- the buttons
    def on_copy(self):
        try:
            QtWidgets.QApplication.clipboard().setText(self.report["text"])
            self.say("Copied. Paste it into an email or an issue.")
        except Exception as exc:
            warn("report: copy: %s" % exc)
            self.say("Could not copy: %s" % exc)

    def on_save(self):
        try:
            default = default_save_path()
            if SAVE_PICKER is not None:
                path = SAVE_PICKER(default)
            else:
                path, _filter = QtWidgets.QFileDialog.getSaveFileName(
                    self, "Save report", default, "Text files (*.txt)"
                )
            if not path:
                return
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write(self.report["text"])
            log("report saved: %s" % path)
            self.say("Saved: %s" % path)
        except Exception as exc:
            warn("report: save: %s" % exc)
            self.say("Could not save the report: %s" % exc)

    def on_open(self):
        try:
            url, cut = core.issue_url(self.report)
            # the whole report goes to the clipboard too: a long log does not fit into an
            # address, and a form field that is missing loses nothing this way
            QtWidgets.QApplication.clipboard().setText(self.report["text"])
            opened = open_url(url)
            log("report: opened GitHub (%d characters%s)" % (len(url), ", cut" if cut else ""))
            if opened is False:
                self.say(
                    "The browser could not be opened. The report is on your clipboard: paste "
                    "it into a new issue at %s" % core.NEW_ISSUE
                )
            elif cut:
                self.say(
                    "GitHub is opening in your browser. The log was too long for the address, "
                    "so the whole report is on your clipboard: paste it (Ctrl+V) into the "
                    "issue's Diagnostics box."
                )
            else:
                self.say(
                    "GitHub is opening in your browser with the form filled in. The whole "
                    "report is on your clipboard too."
                )
        except Exception as exc:
            warn("report: open: %s" % exc)
            self.say("Could not open GitHub: %s" % exc)


def dialog():
    """The open dialog (tests), or None."""
    page = _state["dialog"]
    try:
        if page is not None and page.isVisible():
            return page
    except RuntimeError:
        pass
    return None


def open_dialog():
    """Help > Report a Problem. Opens the dialog (or brings the open one forward)."""
    try:
        import FreeCADGui as Gui

        page = dialog()
        if page is not None:
            page.raise_()
            page.activateWindow()
            return page
        page = ReportDialog(Gui.getMainWindow())
        page.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        _state["dialog"] = page
        page.open()
        page.what.setFocus()
        log("report: dialog opened")
        return page
    except Exception as exc:
        warn("report: could not open the dialog: %s" % exc)
        commands.tell("The Report a Problem window could not be opened: %s" % exc)
        return None


# -- Help menu --------------------------------------------------------------------------------
ENTRY_NAME = "SciForgeReportProblemAction"


def add_help_entry(help_menu):
    """Put "Report a Problem..." at the top of FreeCAD's Help menu (the app menu lists it),
    once; the entry stays until FreeCAD rebuilds that menu, and the app menu asks again."""
    try:
        for action in help_menu.actions():
            if action.objectName() == ENTRY_NAME:
                return
        action = QtGui.QAction("Report a Problem...", help_menu)
        action.setObjectName(ENTRY_NAME)
        action.setToolTip("Tell us what went wrong: a report you see before anything is sent")
        action.triggered.connect(lambda *_: open_dialog())
        first = help_menu.actions()[0] if help_menu.actions() else None
        if first is not None:
            help_menu.insertAction(first, action)
            help_menu.insertSeparator(first)
        else:
            help_menu.addAction(action)
    except Exception as exc:
        warn("report: Help menu: %s" % exc)


class ReportProblemCommand:
    def GetResources(self):
        return {
            "MenuText": "Report a Problem...",
            "ToolTip": "Tell us what went wrong: a report you see before anything is sent",
        }

    def IsActive(self):
        return True

    def Activated(self):
        try:
            open_dialog()
        except Exception as exc:
            warn("Report a Problem: %s" % exc)


COMMANDS = {"SciForge_ReportProblem": ReportProblemCommand}
