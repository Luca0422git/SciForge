# SPDX-License-Identifier: LGPL-2.1-or-later
"""Help > Report a Problem (brief beta-release.md, R2), used with real clicks.

Path 1, the app menu (the Menu button at the top left) > Help > Report a Problem... opens the
  dialog; Open on GitHub, Save and Copy wait until something is written under "What
  happened?".
Path 2, what the preview shows: the version, the system (OS, Qt, graphics card, screen), what
  was typed, SciForge's recent messages; the home folder is "~", other people's folders and
  the user name are gone, an API key in a log line is removed; "Include the last crash log"
  is greyed when there is none.
Path 3, a crash log exists: the box is ticked and the log's end is in the preview; unticking
  takes it out again.
Path 4, Save report... writes the preview's text (the test picks the file, the default name
  is SciForge-report-<date>.txt); Copy puts the same text on the clipboard.
Path 5, Open on GitHub calls the browser seam (report_ui.OPEN_URL) with an address that parses
  back to the typed fields (template bug_report.yml, ids what_happened, expected, version,
  system, diagnostics), and puts the whole report on the clipboard; a log too long for an
  address is replaced by a note, the address stays short, and the dialog says to paste.
No real browser is ever opened here.
"""

import os
import re
import shutil
import tempfile
import time
from urllib.parse import parse_qs, urlparse

import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import widget_input as wi

s = {"opened": [], "picked": [], "defaults": []}
TYPED = "I pressed Q on a face and SciForge closed."
EXPECTED = "The face should move."


def dialog():
    from sciforge import report_ui

    return report_ui.dialog()


def text_of(dlg):
    return dlg.preview.toPlainText()


def pause(step, ms=400):
    step.wait_ms = ms
    return step


# -- Path 1 -------------------------------------------------------------------------------
def prepare():
    import sciforge
    from sciforge import crashlog, report_ui

    s["tmp"] = tempfile.mkdtemp(prefix="sciforge-report-")
    s["old_folder"] = crashlog._state["folder"]
    # no crash log of an earlier scenario: the crash folder is an empty one of our own
    s["crash_folder"] = os.path.join(s["tmp"], "crash")
    os.makedirs(s["crash_folder"])
    crashlog._state["folder"] = s["crash_folder"]
    report_ui.OPEN_URL = lambda url: s["opened"].append(url) or True
    report_ui.SAVE_PICKER = _pick
    report_ui.IDENTITY = lambda: ("/home/testuser", "testuser")
    report_ui._state["gl"] = None
    # what SciForge said earlier: paths of this person, another person's, a key
    sciforge._remember("info", "opened /home/testuser/Designs/arm.FCStd for testuser")
    sciforge._remember("WARNING", "could not read C:\\Users\\Anna\\Desktop\\old.step")
    sciforge._remember("info", "AI chat: key sk-ant-api03-AbCdEfGhIjKlMnOpQrStUvWxYz0123 kept")
    s["clipboard"] = QtWidgets.QApplication.clipboard()
    s["clipboard"].setText("nothing yet")


def _pick(default):
    s["defaults"].append(default)
    return s["picked"][-1] if s["picked"] else ""


def open_from_the_menu():
    """Menu button > Help > Report a Problem..., clicking through like a person."""
    from sciforge import ribbon_ui  # noqa: F401 (the app menu lives there)

    button = wi.quick_access("Menu")
    h.check("the Menu button is in the application bar", button is not None)
    if button is None:
        return
    path = ["Help", "Report a Problem..."]
    s["menu_result"] = {"tries": 0, "seen": []}

    def pick():
        state = s["menu_result"]
        menu = QtWidgets.QApplication.activePopupWidget()
        wanted = path[len(state["seen"])] if len(state["seen"]) < len(path) else None
        if not isinstance(menu, QtWidgets.QMenu) or wanted is None:
            if state["tries"] < 40:
                state["tries"] += 1
                QtCore.QTimer.singleShot(60, pick)
            return
        texts = [a.text().replace("&", "").strip() for a in menu.actions()]
        state.setdefault("levels", []).append(texts)
        action = next(
            (a for a in menu.actions() if a.text().replace("&", "").strip() == wanted), None
        )
        if action is None or not action.isEnabled():
            QtTest.QTest.keyClick(menu, QtCore.Qt.Key_Escape)
            return
        rect = menu.actionGeometry(action)
        for i in range(6):
            QtTest.QTest.mouseMove(menu, QtCore.QPoint(rect.left() + 10 + 6 * i, rect.center().y()))
        QtTest.QTest.mouseMove(menu, rect.center())
        QtTest.QTest.mouseClick(menu, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, rect.center())
        state["seen"].append(wanted)
        state["tries"] = 0
        if len(state["seen"]) < len(path):
            QtCore.QTimer.singleShot(150, pick)  # the submenu opens

    QtCore.QTimer.singleShot(80, pick)
    wi.click(button)


open_from_the_menu.wait_ms = 1200


def dialog_opened():
    state = s.get("menu_result", {})
    levels = state.get("levels", [])
    h.check(
        "the app menu has a Help menu",
        bool(levels) and "Help" in levels[0],
        levels[:1],
    )
    h.check(
        "... whose first entry is Report a Problem...",
        len(levels) > 1 and levels[1][:1] == ["Report a Problem..."],
        levels[1:2],
    )
    dlg = dialog()
    h.check("Report a Problem... opens the dialog", dlg is not None)
    if dlg is None:
        return
    h.check("... titled Report a Problem", dlg.windowTitle() == "Report a Problem")
    h.check(
        "... it says nothing is sent by SciForge itself",
        "sends nothing by itself" in dlg.findChild(QtWidgets.QLabel, "SciForgeReportIntro").text(),
    )
    h.check("Open on GitHub waits for a text", not dlg.open_button.isEnabled())
    h.check("Save report... waits for a text", not dlg.save_button.isEnabled())
    h.check("Copy waits for a text", not dlg.copy_button.isEnabled())
    h.check(
        "... and the dialog says what to do first",
        "Write what happened" in dlg.status.text(),
        dlg.status.text(),
    )
    h.check(
        "no crash log: the box is greyed and not ticked",
        not dlg.crash_box.isEnabled() and not dlg.crash_box.isChecked(),
    )
    h.check(
        "the preview shows the version already", "Version: " in text_of(dlg), text_of(dlg)[:200]
    )


# -- Path 2 -------------------------------------------------------------------------------
def type_it():
    dlg = dialog()
    if dlg is None:
        return h.check("the dialog is open to type in", False)
    QtTest.QTest.mouseClick(dlg.what, QtCore.Qt.LeftButton)
    wi.type_text(dlg.what, TYPED)
    QtTest.QTest.mouseClick(dlg.expected, QtCore.Qt.LeftButton)
    wi.type_text(dlg.expected, EXPECTED)


def the_preview():
    import sciforge

    dlg = dialog()
    if dlg is None:
        return h.check("the dialog is open", False)
    text = text_of(dlg)
    h.check(
        "the three buttons are ready once something is typed",
        dlg.open_button.isEnabled() and dlg.save_button.isEnabled() and dlg.copy_button.isEnabled(),
    )
    h.check("the preview has the version", "SciForge %s" % sciforge.__version__ in text, text[:300])
    h.check("... what happened", TYPED in text)
    h.check("... what was expected", EXPECTED in text)
    for part in ("OS: ", "Qt: ", "OpenGL: ", "Screen: "):
        h.check("... the system line %s" % part.strip(), part in text, text[:600])
    h.check("... the screen's size and scaling", re.search(r"Screen: \d+x\d+, scaling \d+%", text))
    h.check("... the recent SciForge messages", "Recent SciForge messages (newest last):" in text)
    h.check("... the home folder shown as ~", "opened ~/Designs/arm.FCStd for <user>" in text, text)
    h.check("... another person's folder as ~", "~\\Desktop\\old.step" in text)
    for secret in ("testuser", "Anna", "sk-ant", "AbCdEfGhIjKl"):
        h.check("... %s is not in it" % secret, secret not in text)
    h.check("... a removed key says so", "<key removed>" in text)
    h.check("... there is no crash section", "Crash log" not in text)
    h.shot("dialog")


# -- Path 3 -------------------------------------------------------------------------------
def crash_log_appears():
    from sciforge import crashlog, crashlog_core, report_ui

    dlg = dialog()
    if dlg is not None:
        dlg.close()
    folder = s["crash_folder"]
    sid = "20261019-221500-4242"
    s["crash_name"] = crashlog_core.log_name(sid)
    with open(os.path.join(folder, s["crash_name"]), "w", encoding="utf-8") as handle:
        handle.write(
            "Fatal Python error: Segmentation fault\n\nCurrent thread 0x0000 (most recent call "
            'first):\n  File "C:\\Users\\Anna\\AppData\\Local\\SciForge\\x.py", line 12 in go\n'
        )
    h.check("a crash log is found", crashlog.last_crash_log() is not None)
    report_ui.open_dialog()


crash_log_appears.wait_ms = 800


def crash_log_in_the_preview():
    dlg = dialog()
    if dlg is None:
        return h.check("the dialog is open", False)
    text = text_of(dlg)
    h.check(
        "the crash box is ticked when there is a crash log",
        dlg.crash_box.isEnabled() and dlg.crash_box.isChecked(),
    )
    h.check(
        "... the log's name and end are in the preview",
        s["crash_name"] in text and "Segmentation fault" in text,
        text[-400:],
    )
    h.check("... its paths are redacted", "Anna" not in text and "~\\AppData\\Local" in text)
    wi.click(dlg.crash_box, QtCore.QPoint(8, dlg.crash_box.height() // 2))
    h.check("unticking takes it out", "Segmentation fault" not in text_of(dlg))
    wi.click(dlg.crash_box, QtCore.QPoint(8, dlg.crash_box.height() // 2))
    h.check("ticking puts it back", "Segmentation fault" in text_of(dlg))
    h.shot("dialog_crash")


def write_it():
    dlg = dialog()
    if dlg is None:
        return h.check("the dialog is open", False)
    dlg.what.setPlainText("")
    QtTest.QTest.mouseClick(dlg.what, QtCore.Qt.LeftButton)
    wi.type_text(dlg.what, TYPED)
    dlg.expected.setPlainText("")
    QtTest.QTest.mouseClick(dlg.expected, QtCore.Qt.LeftButton)
    wi.type_text(dlg.expected, EXPECTED)


# -- Path 4 -------------------------------------------------------------------------------
def save_it():
    dlg = dialog()
    if dlg is None:
        return h.check("the dialog is open", False)
    s["file"] = os.path.join(s["tmp"], "my-report.txt")
    s["picked"].append(s["file"])
    wi.click(dlg.save_button)


def saved():
    dlg = dialog()
    h.check("Save report... wrote the file", os.path.isfile(s["file"]))
    if os.path.isfile(s["file"]):
        with open(s["file"], encoding="utf-8") as handle:
            written = handle.read()
        h.check("... it is the text of the preview", written == dlg.report["text"])
        h.check(
            "... with what was typed and the crash log's end",
            TYPED in written and "Segmentation fault" in written,
        )
        h.check(
            "... and nothing of the person", "testuser" not in written and "Anna" not in written
        )
    default = os.path.basename(s["defaults"][-1]) if s["defaults"] else ""
    h.check(
        "the suggested name is SciForge-report-<date>.txt",
        default == "SciForge-report-%s.txt" % time.strftime("%Y-%m-%d"),
        default,
    )
    h.check("the dialog says where it saved", s["file"] in dlg.status.text(), dlg.status.text())


def copy_it():
    dlg = dialog()
    s["clipboard"].setText("nothing yet")
    if dlg is not None:
        wi.click(dlg.copy_button)


def copied():
    dlg = dialog()
    got = s["clipboard"].text()
    h.check(
        "Copy put the whole report on the clipboard", dlg is not None and got == dlg.report["text"]
    )
    h.check("... it holds what was typed", TYPED in got)
    h.check("the dialog says it was copied", dlg is not None and "Copied" in dlg.status.text())


# -- Path 5 -------------------------------------------------------------------------------
def open_on_github():
    dlg = dialog()
    s["clipboard"].setText("nothing yet")
    del s["opened"][:]
    if dlg is not None:
        wi.click(dlg.open_button)


def github_opened():
    from sciforge import report_core

    dlg = dialog()
    h.check("Open on GitHub called the browser once", len(s["opened"]) == 1, s["opened"])
    if not s["opened"]:
        return
    url = s["opened"][0]
    parts = urlparse(url)
    got = {k: v[0] for k, v in parse_qs(parts.query).items()}
    h.check(
        "the address is the SciForge issue form",
        (parts.netloc, parts.path) == ("github.com", "/Luca0422git/SciForge/issues/new"),
        url[:120],
    )
    h.check(
        "... the template is bug_report.yml", got.get("template") == "bug_report.yml", got.keys()
    )
    h.check("... what_happened is what was typed", got.get("what_happened") == TYPED)
    h.check("... expected is what was expected", got.get("expected") == EXPECTED)
    h.check(
        "... the title starts with the first words",
        got.get("title", "").startswith("[Bug] I pressed Q"),
    )
    import sciforge

    h.check("... version has the SciForge version", sciforge.__version__ in got.get("version", ""))
    h.check("... system is one of the form's dropdown options", got.get("system") in ("Windows 11", "Windows 10", "Linux", "Something else (tell us below)"), got.get("system"))
    h.check("... diagnostics has the log", "Recent SciForge messages" in got.get("diagnostics", ""))
    h.check(
        "... nothing of the person is in the address",
        "testuser" not in url and "Anna" not in url and "sk-ant" not in url,
    )
    h.check("... it is short enough for a browser", len(url) <= report_core.URL_LIMIT, len(url))
    h.check(
        "the whole report is on the clipboard too",
        dlg is not None and s["clipboard"].text() == dlg.report["text"],
    )
    h.check(
        "the dialog says GitHub is opening",
        dlg is not None and "GitHub is opening" in dlg.status.text(),
        dlg.status.text() if dlg else "",
    )


def a_long_log():
    """A log too long for an address: the diagnostics become a note, the rest stays."""
    import sciforge

    for i in range(200):
        sciforge._remember("info", "long line %03d %s" % (i, "x" * 120))
    dlg = dialog()
    if dlg is not None:
        dlg.close()
    from sciforge import report_ui

    report_ui.open_dialog()


a_long_log.wait_ms = 800


def long_log_typed():
    dlg = dialog()
    if dlg is None:
        return h.check("the dialog is open", False)
    QtTest.QTest.mouseClick(dlg.what, QtCore.Qt.LeftButton)
    wi.type_text(dlg.what, TYPED)
    del s["opened"][:]
    wi.click(dlg.open_button)


def long_log_opened():
    from sciforge import report_core

    dlg = dialog()
    h.check("Open on GitHub called the browser", len(s["opened"]) == 1, s["opened"])
    if not s["opened"]:
        return
    url = s["opened"][0]
    got = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
    h.check(
        "the long address is cut to a browser's size", len(url) <= report_core.URL_LIMIT, len(url)
    )
    h.check("... what was typed is still whole", got.get("what_happened") == TYPED)
    h.check(
        "... the diagnostics are a note to paste", got.get("diagnostics") == report_core.PASTE_NOTE
    )
    h.check(
        "the clipboard holds the whole long log",
        dlg is not None and "long line 199" in s["clipboard"].text(),
    )
    h.check(
        "the dialog says to paste it",
        dlg is not None and "paste" in dlg.status.text().lower(),
        dlg.status.text() if dlg else "",
    )
    h.shot("dialog_long")


def browser_that_fails():
    from sciforge import report_ui

    dlg = dialog()
    old = report_ui.OPEN_URL
    report_ui.OPEN_URL = lambda url: False
    try:
        if dlg is not None:
            wi.click(dlg.open_button)
    finally:
        report_ui.OPEN_URL = old
    h.check(
        "a browser that cannot open says so and points to the clipboard",
        dlg is not None and "could not be opened" in dlg.status.text(),
        dlg.status.text() if dlg else "",
    )


def close_it():
    from sciforge import crashlog, report_ui

    dlg = dialog()
    if dlg is not None:
        wi.click(dlg.close_button)
    h.check("Close closes the dialog", dialog() is None)
    report_ui.OPEN_URL = None
    report_ui.SAVE_PICKER = None
    report_ui.IDENTITY = None
    crashlog._state["folder"] = s["old_folder"]
    shutil.rmtree(s["tmp"], ignore_errors=True)


h.run(
    "report_problem",
    [
        prepare,
        open_from_the_menu,
        dialog_opened,
        type_it,
        the_preview,
        crash_log_appears,
        crash_log_in_the_preview,
        write_it,
        save_it,
        saved,
        copy_it,
        copied,
        open_on_github,
        github_opened,
        a_long_log,
        long_log_typed,
        long_log_opened,
        browser_that_fails,
        close_it,
    ],
)
