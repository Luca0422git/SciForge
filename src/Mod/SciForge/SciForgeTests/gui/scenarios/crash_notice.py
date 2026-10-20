# SPDX-License-Identifier: LGPL-2.1-or-later
"""The crash log and "SciForge closed unexpectedly last time" on Home (brief beta-release.md,
R2), used with real clicks.

Path 1, this session's crash log is on from the start (InitGui.py): faulthandler writes into
  <user data>/SciForge/crash/session-*.log, a marker says the session runs, uncaught Python
  errors are logged there and in the recent messages (the earlier hook still runs).
Path 2, a session that did not end cleanly (a marker whose process is gone, a log with a crash
  in it): Home shows the slim line "SciForge closed unexpectedly last time." in the look of
  the recovery banner, with [Report it] and [Dismiss]; no popup. A marker whose process still
  runs (another SciForge window) shows nothing.
Path 3, Report it opens Report a Problem with the crash log ticked and its end in the preview.
Path 4, Dismiss hides the line and removes the marker (the log with the crash stays for a later
  report); Home opened again shows no line.
Path 5, a session killed without any log text still shows the line; Dismiss removes its marker
  and its empty log.
"""

import faulthandler
import os
import shutil
import sys
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtWidgets

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import widget_input as wi

s = {}


def home():
    from sciforge import home_ui

    return home_ui.view()


def notices():
    page = home()
    return getattr(page, "notices", None) if page is not None else None


def dead_pid():
    """The number of a process that does not exist (never a real one: no process is started)."""
    from sciforge import crashlog_core

    for pid in range(4_000_001, 4_000_200):
        if not crashlog_core.pid_alive(pid):
            return pid
    return 4_000_001


def reopen_home():
    """The Home tab closed and opened again, as when SciForge starts."""
    from sciforge import home_ui

    home_ui.close()
    home_ui.show()


def line_colour(line):
    """The colour of the line's background on the real screen (QWidget.grab paints without
    the window's style sheets)."""
    image = QtWidgets.QApplication.primaryScreen().grabWindow(0).toImage()
    top = line.mapToGlobal(line.rect().topLeft())
    return image.pixelColor(top.x() + 3, top.y() + line.height() // 2)


# -- Path 1 -------------------------------------------------------------------------------
def this_session():
    from sciforge import crashlog, crashlog_core

    session = crashlog._state["session"]
    h.check("the crash log is started in this session", session is not None)
    if session is None:
        return
    h.check(
        "... in <user data>/SciForge/crash",
        os.path.dirname(session["log"]) == crashlog_core.folder_in(App.getUserAppDataDir()),
        session["log"],
    )
    h.check("... the log file is there", os.path.isfile(session["log"]))
    h.check("... and the 'session running' marker", os.path.isfile(session["marker"]))
    h.check("faulthandler is writing to it", faulthandler.is_enabled())
    h.check("uncaught Python errors go through our hook", sys.excepthook is crashlog._excepthook)


def a_broken_slot():
    import sciforge
    from sciforge import crashlog

    session = crashlog._state["session"]
    if session is None:
        return h.check("the crash log is started", False)
    earlier = []
    old = crashlog._state["old_excepthook"]
    crashlog._state["old_excepthook"] = lambda *args: earlier.append(args)  # (no traceback print)
    try:
        sys.excepthook(ValueError, ValueError("boom in a slot"), None)
    finally:
        crashlog._state["old_excepthook"] = old
    h.check("the earlier hook still ran", len(earlier) == 1)
    with open(session["log"], encoding="utf-8") as handle:
        text = handle.read()
    h.check(
        "the error is in the session log",
        "Uncaught Python error" in text and "boom in a slot" in text,
        text,
    )
    h.check(
        "... and in the recent messages",
        any("uncaught ValueError: boom in a slot" in m for m in sciforge.RECENT[-5:]),
    )
    open(
        session["log"], "w"
    ).close()  # (a clean exit then removes the log: nothing is left of this test)


# -- Path 2 -------------------------------------------------------------------------------
def a_session_that_crashed():
    from sciforge import crashlog, crashlog_core

    s["tmp"] = tempfile.mkdtemp(prefix="sciforge-crash-scenario-")
    s["folder"] = os.path.join(s["tmp"], "crash")
    os.makedirs(s["folder"])
    s["old_folder"] = crashlog._state["folder"]
    crashlog._state["folder"] = s["folder"]
    # an older session: it was running, its process is gone, faulthandler wrote this
    session = crashlog_core.begin(s["folder"], 1_790_000_000, dead_pid(), "0.1.0-beta")
    s["crashed"] = session
    with open(session["log"], "w", encoding="utf-8") as handle:
        handle.write(
            "Windows fatal exception: access violation\n\nThread 0x000013ac (most recent call "
            'first):\n  File "C:\\Users\\Anna\\x.py", line 3 in run\n'
        )
    # a second SciForge window, still running: its marker must not count
    s["other"] = crashlog_core.begin(s["folder"], 1_790_000_500, os.getpid(), "0.1.0-beta")
    found = crashlog.rescan()
    h.check(
        "the session that did not end cleanly is found",
        [e["id"] for e in found] == [session["id"]],
        [e["id"] for e in found],
    )
    reopen_home()


a_session_that_crashed.wait_ms = 1200


def the_line_is_shown():
    page = notices()
    h.check("Home has its slim lines", page is not None)
    if page is None:
        return
    line = page.crash
    h.check("the 'closed unexpectedly' line is shown", line.isVisible())
    h.check(
        "... it says so",
        line.text.text() == "SciForge closed unexpectedly last time.",
        line.text.text(),
    )
    h.check(
        "... with Report it and Dismiss",
        sorted(line.buttons) == ["SciForgeHomeCrashDismiss", "SciForgeHomeCrashReport"]
        and all(b.isVisible() for b in line.buttons.values()),
    )
    h.check("... slim: one line high", line.height() < 60, line.height())
    colour = line_colour(line)
    banner = (0x5A, 0x4A, 0x2A)
    h.check(
        "... in the look of the recovery banner (checked on the screen)",
        all(abs(a - b) < 12 for a, b in zip((colour.red(), colour.green(), colour.blue()), banner)),
        colour.name(),
    )
    h.check("no pop-up window came up", QtWidgets.QApplication.activeModalWidget() is None)
    h.check(
        "the welcome line is not shown here (it was shown in an earlier start)",
        not page.welcome.isVisible(),
    )
    h.shot("crash_line")


# -- Path 3 -------------------------------------------------------------------------------
def report_it():
    page = notices()
    if page is not None:
        wi.click(page.crash.buttons["SciForgeHomeCrashReport"])


report_it.wait_ms = 1500


def report_opened():
    from sciforge import report_ui

    dlg = report_ui.dialog()
    h.check("Report it opens Report a Problem", dlg is not None)
    if dlg is None:
        return
    h.check("... the crash log is ticked", dlg.crash_box.isEnabled() and dlg.crash_box.isChecked())
    text = dlg.preview.toPlainText()
    h.check("... its end is in the preview", "access violation" in text, text[-300:])
    h.check(
        "... the report says the session before did not end cleanly",
        "did not end cleanly" in text,
        text[-600:],
    )
    h.check("... redacted", "Anna" not in text)
    h.shot("report_from_crash")
    wi.click(dlg.close_button)


# -- Path 4 -------------------------------------------------------------------------------
def dismiss():
    page = notices()
    if page is not None:
        wi.click(page.crash.buttons["SciForgeHomeCrashDismiss"])


dismiss.wait_ms = 800


def dismissed():
    from sciforge import crashlog

    page = notices()
    h.check("Dismiss hides the line", page is not None and not page.crash.isVisible())
    h.check("... the marker is gone", not os.path.exists(s["crashed"]["marker"]))
    h.check("... the log with the crash stays for a report", os.path.exists(s["crashed"]["log"]))
    h.check("... the other window's marker is untouched", os.path.exists(s["other"]["marker"]))
    h.check("... nothing is pending", crashlog.pending() == [])
    reopen_home()


dismissed.wait_ms = 1000


def not_again():
    page = notices()
    h.check("Home opened again shows no line", page is not None and not page.crash.isVisible())


# -- Path 5 -------------------------------------------------------------------------------
def a_session_that_was_killed():
    from sciforge import crashlog, crashlog_core

    session = crashlog_core.begin(s["folder"], 1_790_100_000, dead_pid(), "0.1.0-beta")
    s["killed"] = session
    crashlog.rescan()
    reopen_home()


a_session_that_was_killed.wait_ms = 1000


def killed_shown():
    page = notices()
    h.check(
        "a session without any log text still shows the line",
        page is not None and page.crash.isVisible(),
    )
    if page is not None:
        wi.click(page.crash.buttons["SciForgeHomeCrashDismiss"])


killed_shown.wait_ms = 800


def killed_dismissed():
    page = notices()
    h.check("Dismiss hides it", page is not None and not page.crash.isVisible())
    h.check(
        "... its marker and its empty log are gone",
        not os.path.exists(s["killed"]["marker"]) and not os.path.exists(s["killed"]["log"]),
    )


def tidy():
    from sciforge import crashlog, crashlog_core

    crashlog_core.end(s["folder"], s["other"]["id"])
    crashlog._state["folder"] = s["old_folder"]
    crashlog.rescan()
    shutil.rmtree(s["tmp"], ignore_errors=True)


h.run(
    "crash_notice",
    [
        this_session,
        a_broken_slot,
        a_session_that_crashed,
        the_line_is_shown,
        report_it,
        report_opened,
        dismiss,
        dismissed,
        not_again,
        a_session_that_was_killed,
        killed_shown,
        killed_dismissed,
        tidy,
    ],
)
