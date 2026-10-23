# SPDX-License-Identifier: LGPL-2.1-or-later
"""The update check and "Update now" (brief docs/sciforge/dev/briefs/beta-release.md, R3), against a
FAKE GitHub (SciForgeTests/gui/fake_github.py: a web server on this computer's own address; the
test run refuses every other address). Nothing is installed and SciForge is never quit: the
hand-over (update_ui.HAND_OVER) and the quit (update_ui.QUIT) are stand-ins that record what they
were asked.

P1  Home is up, no update line. The daily check, started the way the timer after the start does,
    does not hold the window up (GitHub answers slowly; the window keeps running), finds
    0.1.0-beta.2: one line under Home's heading, in the blue of the update line with an accent
    "Update now", on the screen. The request says "SciForge/0.1.0-beta" and nothing more.
P2  Once a day: asking again at once does not ask GitHub; two days later it does; with
    "Check for updates when SciForge starts" off it never does.
P3  Later hides the line (until the next version: a newer one shows it again). Help > Check for
    Updates asks at once and answers in a box with Update now / What's new / Later; What's new
    opens the release page.
P4  Nothing newer: "SciForge 0.1.0-beta is up to date." and no line.
P5  Channels: only a beta is newer; Stable only says up to date, Betas too offers it.
P6  Offline (the server is gone): the manual check says "Could not reach GitHub"; the check at
    the start says nothing (one log line) and the line stays as it was.
P7  Update now on a module update (same core): a dialog with a progress bar and Cancel, the file
    comes down, its SHA-256 is checked, the update zip is unpacked, the hand-over gets
    powershell -File install_update.ps1 -Target <folder> -WaitPid <this process> -Restart
    -Quiet, SciForge is asked to quit.
P8  Cancel stops the download and leaves no file.
P9  A file whose checksum is wrong is refused and deleted: nothing is handed over.
P10 A different core (the program itself changed): the full installer; the dialog says Windows
    may warn; the hand-over waits for SciForge and starts the installer.
P11 A command still open: Update now says to finish it first and downloads nothing.
P12 Cancel at "save your changes?" (the quit says no): the helper is stopped, the update is off.
P13 After the update: "Updated to 0.1.0-beta." once, What's new opens the notes, Dismiss hides it.
P14 Linux (the AppImage cannot replace itself): the release page and one line of what to do.
P15 Preferences > General > Updates: the two options, their defaults, and they work.
P16 The update icon in the top bar (top right, left of the search button, like Fusion's): hidden
    while nothing newer is known, shown (lit, on the real screen) when the check finds a newer
    SciForge, still shown after Later (that only hides Home's line), gone when up to date; its
    menu offers Update now and What's new.
"""

import hashlib
import os
import time

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import fake_github as fg
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import misc_steps as m
from SciForgeTests.gui import widget_input as w

PARAMS = "User parameter:BaseApp/Preferences/Mod/SciForge"
VERSION = "0.1.0-beta"
WINDOWS = {"os": "windows", "kind": "installed", "home": "C:\\Program Files\\SciForge"}
APPIMAGE = {"os": "linux", "kind": "appimage", "home": "/tmp/.mount_SciForge"}
s = {}


# -- helpers ---------------------------------------------------------------------------------
def group():
    return App.ParamGet(PARAMS)


def forget_prefs():
    for kind, name in (
        ("Float", "UpdateLastCheck"),
        ("String", "UpdateLater"),
        ("String", "UpdateAvailable"),
        ("String", "UpdateJustInstalled"),
        ("String", "UpdateChannel"),
        ("Bool", "CheckForUpdates"),
    ):
        try:
            getattr(group(), "Rem" + kind)(name)
        except Exception:
            pass


def wait_for(condition, seconds=15.0):
    end = time.time() + seconds
    while time.time() < end:
        QtWidgets.QApplication.processEvents()
        if condition():
            return True
        QtTest.QTest.qWait(30)
    return bool(condition())


def checking_done():
    from sciforge import update_ui

    return not update_ui._state["busy"]


def line():
    from sciforge import home_ui

    page = home_ui.view()
    return getattr(page, "update_line", None) if page is not None else None


def line_text():
    found = line()
    return found.text.text() if found is not None and found.isVisible() else ""


def answer():
    """The box a check or Update now answered with (None when none is open)."""
    from sciforge import update_ui

    box = update_ui._state.get("answer")
    try:
        return box if box is not None and box.isVisible() else None
    except RuntimeError:
        return None


def box_button(box, text):
    for button in box.buttons():
        if button.text() == text:
            return button
    return None


def close_answer():
    box = answer()
    if box is not None:
        w.click(box.buttons()[0])
        wait_for(lambda: answer() is None, 3)


def reset_state():
    """Between paths: what the last path found is forgotten, the seams stay."""
    from sciforge import update_ui

    update_ui._state["release"] = None
    update_ui._state["version"] = ""
    update_ui._state["updated"] = ""
    update_ui._state["answer"] = None
    forget_prefs()
    s["opened"].clear()
    s["handed"].clear()
    s["quit"].clear()
    s["fake"].clear()
    s["fake"].hits.clear()
    s["fake"].slow = False
    s["fake"].delay = 0.0
    update_ui.INSTALLED = {"version": VERSION, "core": "testcore"}
    update_ui.LAYOUT = dict(WINDOWS)
    s["quit_answer"] = True
    update_ui._changed()
    QtWidgets.QApplication.processEvents()


def due_again():
    """Pretend the last check was two days ago, as the next day's start would find it."""
    group().SetFloat("UpdateLastCheck", time.time() - 2 * 24 * 3600)


def auto_check():
    """What the timer a few seconds after the start does."""
    from sciforge import update_ui

    due_again()
    update_ui._start_if_due()
    return wait_for(checking_done)


def manual_check():
    """Help > Check for Updates: the menu entry itself, then the answer."""
    bar = Gui.getMainWindow().menuBar()
    for top in bar.actions():
        if top.text().replace("&", "") == "Help" and top.menu() is not None:
            for entry in top.menu().actions():
                if entry.text() == "Check for Updates...":
                    entry.trigger()
                    wait_for(checking_done)
                    wait_for(lambda: answer() is not None, 5)
                    return True
    return False


def updates_folder(version):
    from sciforge import update_core

    return update_core.updates_dir(App.getUserAppDataDir(), version)


def files_in(folder):
    found = []
    for root, _dirs, names in os.walk(folder):
        found += [os.path.join(root, n) for n in names]
    return found


def press_update_now():
    found = line()
    h.check("the update line has Update now", found is not None and found.update_button.isVisible())
    w.click(found.update_button)


def icon_button():
    from sciforge import shell

    ribbon = shell.ribbon()
    return getattr(ribbon, "update_icon", None) if ribbon is not None else None


def icon_lit():
    """How many pixels of the icon's light blue the real screen shows on the button."""
    button = icon_button()
    if button is None or not button.isVisible():
        return 0
    top = button.mapToGlobal(QtCore.QPoint(0, 0))
    image = QtWidgets.QApplication.primaryScreen().grabWindow(0).toImage()
    return sum(
        1
        for x in range(button.width())
        for y in range(button.height())
        if near(image.pixelColor(top.x() + x, top.y() + y), (0x8F, 0xD0, 0xFF), 40)
    )


def pixel(widget, dx, dy):
    top = widget.mapToGlobal(QtCore.QPoint(dx, dy))
    image = QtWidgets.QApplication.primaryScreen().grabWindow(0).toImage()
    return image.pixelColor(top.x(), top.y())


def near(colour, rgb, tol=14):
    return all(abs(a - b) <= tol for a, b in zip((colour.red(), colour.green(), colour.blue()), rgb))


# -- setup -----------------------------------------------------------------------------------
def setup():
    from sciforge import home_ui, update_core, update_ui

    Gui.activateWorkbench("SciForgeWorkbench")
    s["fake"] = fg.FakeGitHub()
    s["old_base"] = update_core.API_BASE
    update_core.API_BASE = s["fake"].base
    # The scenario is a 0.1.0-beta install (its fake releases 0.1.0-beta.2 ... are newer),
    # whatever the VERSION file says: the update code reads the running version here
    s["old_version"] = update_ui.__version__
    update_ui.__version__ = VERSION
    s["opened"], s["handed"], s["quit"] = [], [], []
    s["quit_answer"] = True

    class Helper:
        """What the hand-over starts: only remembers being stopped."""

        terminated = False

        def terminate(self):
            Helper.terminated = True

    s["helper"] = Helper

    def hand_over(argv):
        s["handed"].append(list(argv))
        return Helper()

    def quit_now():
        s["quit"].append(1)
        return s["quit_answer"]

    update_ui.OPEN_URL = s["opened"].append
    update_ui.HAND_OVER = hand_over
    update_ui.QUIT = quit_now
    forget_prefs()
    reset_state()
    home_ui.show()
    QtWidgets.QApplication.processEvents()
    h.check("a test run may only talk to this computer", update_core.blocked("https://api.github.com/x"))
    h.check("the test's fake GitHub is allowed", not update_core.blocked(s["fake"].base))


# -- P1 --------------------------------------------------------------------------------------
def p1_home_without_line():
    from sciforge import home_ui, update_ui

    page = home_ui.view()
    h.check("P1 Home is open", page is not None)
    found = line()
    h.check("P1 Home has an update line widget", found is not None)
    h.check("P1 ... hidden: nothing is known yet", found is not None and not found.isVisible())
    h.check("P1 the automatic check did not run by itself in a test", s["fake"].hits == [], s["fake"].hits)
    h.check("P1 Preferences' check at start is on by default", update_ui.check_on_start())
    button = icon_button()
    h.check("P1 the top bar has an update icon button", button is not None)
    h.check("P1 ... hidden: nothing is known yet", button is not None and not button.isVisible())
    from sciforge import diagnostics

    from sciforge import update_core

    # ('unknown' for a source tree or a test run's quick update; a build carries its real id,
    # written into core_info.py at build time, and Diagnostics must say that one)
    core_id = update_core.installed_core() or "unknown"
    h.check(
        "P1 Diagnostics names the core id (%s)" % core_id,
        "Update core: %s" % core_id in diagnostics.report(),
    )


def p1_check_does_not_hold_the_window_up():
    from sciforge import update_ui

    fake = s["fake"]
    fake.publish("0.1.0-beta", prerelease=True)
    fake.publish("0.1.0-beta.2", core="testcore", extra_kb=700)
    fake.delay = 0.7  # a slow GitHub
    ticks = []
    timer = QtCore.QTimer()
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start(40)
    due_again()
    started = time.time()
    update_ui._start_if_due()
    took = time.time() - started
    h.check("P1 starting the check returns at once (%.2f s)" % took, took < 0.3)
    h.check("P1 it is running", update_ui._state["busy"])
    done = wait_for(checking_done)
    timer.stop()
    h.check("P1 the check finished", done)
    h.check("P1 the window kept running while GitHub was slow (%d ticks)" % len(ticks), len(ticks) >= 8)
    h.check("P1 the request named SciForge's version", fake.agents and fake.agents[0] == "SciForge/" + VERSION, fake.agents)
    h.check(
        "P1 it asked for the newest releases, and for nothing else but the release's json",
        fake.hits[0] == "/repos/Luca0422git/SciForge/releases?per_page=10"
        and all(p.endswith("sciforge-release.json") for p in fake.hits[1:]),
        fake.hits,
    )
    h.check("P1 the time of the check was remembered", abs(group().GetFloat("UpdateLastCheck", 0.0) - time.time()) < 60)
    h.check("P1 the found version was remembered", group().GetString("UpdateAvailable", "") == "0.1.0-beta.2")


def p1_the_line_on_screen():
    from sciforge import home_ui

    found = line()
    page = home_ui.view()
    h.check("P1 the line says what is available", line_text() == "SciForge 0.1.0-beta.2 is available.", line_text())
    shown = [b for b in (found.whats_new_button, found.update_button, found.later_button, found.dismiss_button) if b.isVisible()]
    h.check(
        "P1 ... with What's new, Update now, Later",
        [b.text() for b in shown] == ["What's new", "Update now", "Later"],
        [b.text() for b in shown],
    )
    heading = page.findChild(QtWidgets.QLabel, "SciForgeHomeHeading")
    def top(widget):
        return widget.mapTo(page, QtCore.QPoint(0, 0)).y()

    h.check("P1 under Home's heading, above New design", top(heading) < top(found) < top(page.new_button))
    h.check("P1 wide enough to read", found.width() > 400 and found.height() >= 24, (found.width(), found.height()))
    # the colours on the real screen (a grab of the screen: QWidget.grab paints without the style sheets)
    inside = pixel(found, 5, found.height() // 2)
    h.check("P1 the line is the blue of the update line on the screen", near(inside, (0x35, 0x4A, 0x63)), inside.name())
    button = found.update_button
    top = button.mapTo(found, QtCore.QPoint(0, 0))
    accent = pixel(found, top.x() + 4, top.y() + button.height() // 2)
    h.check("P1 Update now is the accent blue on the screen", near(accent, (0x3F, 0xA9, 0xF5), 24), accent.name())
    label = found.text
    image = QtWidgets.QApplication.primaryScreen().grabWindow(0).toImage()
    corner = label.mapToGlobal(QtCore.QPoint(0, 0))
    lightest = max(
        image.pixelColor(corner.x() + x, corner.y() + y).lightness()
        for x in range(0, label.width(), 2)
        for y in range(label.height())
    )
    h.check("P1 the sentence is lit, readable on the blue", lightest > 180, lightest)
    h.shot("line")


def p16_the_icon_on_screen():
    button = icon_button()
    h.check("P16 the update icon is shown", button is not None and button.isVisible())
    if button is None or not button.isVisible():
        return
    h.check(
        "P16 ... its tooltip says what is available",
        button.toolTip() == "SciForge 0.1.0-beta.2 is available. Click to update.",
        button.toolTip(),
    )
    search = [b for b in button.parent().findChildren(QtWidgets.QToolButton) if b.toolTip().startswith("Search commands")]
    h.check("P16 ... top right, just left of the search button", bool(search) and button.x() < search[0].x() and search[0].x() - button.x() < 80)
    h.check("P16 ... in the right half of the window", button.mapToGlobal(QtCore.QPoint(0, 0)).x() > Gui.getMainWindow().width() // 2)
    lit = icon_lit()
    h.check("P16 ... drawn on the screen (its blue arrow is there)", lit >= 10, lit)
    h.shot("update_icon")


def p1b_the_light_look():
    """The line in the light look (Preferences > General > Look): a pale blue with dark text,
    read on the screen, not in the style sheet."""
    from sciforge import theme

    theme.set_theme("light")
    QtTest.QTest.qWait(500)
    found = line()
    h.check("P1 light look: the line is still there", found is not None and found.isVisible())
    if found is None:
        return
    inside = pixel(found, 5, found.height() // 2)
    h.check("P1 light look: the line is pale blue on the screen", near(inside, (0xCD, 0xE2, 0xF7)), inside.name())
    label = found.text
    image = QtWidgets.QApplication.primaryScreen().grabWindow(0).toImage()
    corner = label.mapToGlobal(QtCore.QPoint(0, 0))
    darkest = min(
        image.pixelColor(corner.x() + x, corner.y() + y).lightness()
        for x in range(0, label.width(), 2)
        for y in range(label.height())
    )
    h.check("P1 light look: the sentence is dark on it", darkest < 110, darkest)
    h.shot("line_light")
    theme.set_theme("dark")
    QtTest.QTest.qWait(500)
    again = pixel(found, 5, found.height() // 2)
    h.check("P1 and the dark look again", near(again, (0x35, 0x4A, 0x63)), again.name())


# -- P2 --------------------------------------------------------------------------------------
def p2_once_a_day():
    from sciforge import update_ui

    fake = s["fake"]
    count = fake.count("/repos")
    update_ui._start_if_due()
    wait_for(checking_done, 2)
    QtTest.QTest.qWait(200)
    h.check("P2 asked a moment ago: GitHub is not asked again", fake.count("/repos") == count, fake.hits)
    fake.delay = 0.0
    auto_check()
    h.check("P2 two days later it asks again", fake.count("/repos") == count + 1, fake.hits)
    group().SetBool("CheckForUpdates", False)
    due_again()
    update_ui._start_if_due()
    QtTest.QTest.qWait(300)
    h.check("P2 with 'Check for updates when SciForge starts' off it never asks by itself", fake.count("/repos") == count + 1)
    h.check("P2 ... and nothing is running", checking_done())
    group().RemBool("CheckForUpdates")


# -- P3 --------------------------------------------------------------------------------------
def p3_later_hides_the_line():
    found = line()
    w.click(found.later_button)
    QtTest.QTest.qWait(100)
    h.check("P3 Later hides the line", line_text() == "", line_text())
    h.check("P3 ... for that version", group().GetString("UpdateLater", "") == "0.1.0-beta.2")
    button = icon_button()
    h.check("P16 the top bar icon stays after Later", button is not None and button.isVisible())


def p3_menu_asks_and_answers():
    ok = manual_check()
    h.check("P3 Help has Check for Updates...", ok)
    box = answer()
    h.check("P3 it answers in a box", box is not None)
    if box is None:
        return
    h.check("P3 the box says what is available", "0.1.0-beta.2 is available" in box.text(), box.text())
    h.check(
        "P3 ... with Update now, What's new, Later",
        sorted(b.text() for b in box.buttons()) == ["Later", "Update now", "What's new"],
        [b.text() for b in box.buttons()],
    )
    h.check("P3 the line stays hidden after Later (the person said so)", line_text() == "")
    h.shot("answer_available")


def p3_whats_new():
    box = answer()
    if box is None:
        h.check("P3 the box is open", False)
        return
    w.click(box_button(box, "What's new"))
    wait_for(lambda: bool(s["opened"]), 3)
    h.check(
        "P3 What's new opens the release page of that version",
        s["opened"] and s["opened"][-1].endswith("/releases/tag/sciforge-v0.1.0-beta.2"),
        s["opened"],
    )


def p3_a_newer_version_shows_the_line_again():
    from sciforge import update_ui

    s["fake"].publish("0.1.0-beta.3", core="testcore")
    auto_check()
    h.check("P3 a version newer than the one said Later to shows the line", line_text() == "SciForge 0.1.0-beta.3 is available.", line_text())
    # ... and the box's own Later hides that one
    manual_check()
    box = answer()
    if box is not None:
        w.click(box_button(box, "Later"))
        wait_for(lambda: answer() is None and line_text() == "", 3)
    h.check("P3 the box's Later hides the line too", line_text() == "", line_text())
    h.check("P3 ... and remembers 0.1.0-beta.3", group().GetString("UpdateLater", "") == "0.1.0-beta.3")
    h.check("P3 (the found version is still known)", update_ui._state["version"] == "0.1.0-beta.3")


def p16_the_icon_menu():
    button = icon_button()
    seen = []

    def choose(text):
        seen.append(text)
        return text == "What's new"

    s["opened"].clear()
    ok = False
    if button is not None and button.isVisible():
        ok = w.click_menu(button, "What's new")
    h.check("P16 clicking the icon opens a menu with What's new", ok)
    h.check(
        "P16 ... What's new opens the release page of the version the icon is for",
        bool(s["opened"]) and s["opened"][-1].endswith("/releases/tag/sciforge-v0.1.0-beta.3"),
        s["opened"],
    )
    # the menu also has Update now (it is the one that starts the download)
    texts = []
    from sciforge import update_ui

    if button is not None:
        QtCore.QTimer.singleShot(
            80,
            lambda: (
                texts.extend(a.text() for a in QtWidgets.QApplication.activePopupWidget().actions()),
                QtWidgets.QApplication.activePopupWidget().close(),
            ),
        )
        w.click(button)
    h.check(
        "P16 the menu lists the version, Update now and What's new",
        [t for t in texts if t] == ["SciForge 0.1.0-beta.3 is available", "Update now", "What's new"],
        texts,
    )
    h.check("P16 (update_ui.pending knows the version)", update_ui.pending() == "0.1.0-beta.3")


# -- P4 --------------------------------------------------------------------------------------
def p4_up_to_date():
    reset_state()
    s["fake"].publish("0.1.0-beta", prerelease=True)
    manual_check()
    box = answer()
    h.check("P4 a box answers", box is not None)
    if box is not None:
        h.check("P4 it says up to date", box.text() == "SciForge %s is up to date." % VERSION, box.text())
        h.shot("answer_up_to_date")
    h.check("P4 no line on Home", line_text() == "")
    button = icon_button()
    h.check("P16 the top bar icon is gone when up to date", button is not None and not button.isVisible())
    close_answer()


# -- P5 --------------------------------------------------------------------------------------
def p5_channels():
    reset_state()
    s["fake"].publish("0.1.0-beta.5", core="testcore")
    group().SetString("UpdateChannel", "stable")
    auto_check()
    h.check("P5 Stable only: a newer beta is not offered", line_text() == "", line_text())
    group().SetString("UpdateChannel", "beta")
    auto_check()
    h.check("P5 Betas too: it is", line_text() == "SciForge 0.1.0-beta.5 is available.", line_text())
    group().RemString("UpdateChannel")
    auto_check()
    h.check("P5 no choice made: a beta gets betas", line_text() != "", line_text())
    s["fake"].publish("0.1.0", core="testcore", prerelease=False)
    group().SetString("UpdateChannel", "stable")
    auto_check()
    h.check("P5 Stable only: the finished version is", line_text() == "SciForge 0.1.0 is available.", line_text())


# -- P6 --------------------------------------------------------------------------------------
def p6_offline():
    from sciforge import update_core, update_ui
    import sciforge

    reset_state()
    s["fake"].publish("0.1.0-beta.2", core="testcore")
    auto_check()
    h.check("P6 (a newer version is known: the line shows)", line_text() == "SciForge 0.1.0-beta.2 is available.", line_text())
    s["fake"].stop()
    close_answer()
    h.check("P6 the manual check says so", manual_check())
    box = answer()
    h.check("P6 a box answers", box is not None)
    if box is not None:
        h.check("P6 it says Could not reach GitHub", box.text().startswith("Could not reach GitHub"), box.text())
        h.shot("answer_offline")
    close_answer()
    before = len(sciforge.RECENT)
    auto_check()
    h.check("P6 the check at the start says nothing", answer() is None)
    h.check("P6 ... the line stays as it was", line_text() == "SciForge 0.1.0-beta.2 is available.", line_text())
    logged = [m for m in sciforge.RECENT[before:] if "update check:" in m]
    h.check("P6 ... one [SciForge] line is logged", len(logged) == 1 and "Could not reach GitHub" in logged[0], logged)
    h.check("P6 the busy cursor is gone", QtWidgets.QApplication.overrideCursor() is None)
    # GitHub is back
    s["fake"] = fg.FakeGitHub()
    update_core.API_BASE = s["fake"].base
    reset_state()
    update_ui._changed()


# -- P7 --------------------------------------------------------------------------------------
def p7_update_now_on_a_module_update():
    from sciforge import update_ui

    fake = s["fake"]
    fake.publish("0.1.0-beta.2", core="testcore", extra_kb=900)
    auto_check()
    h.check("P7 the line is there", line_text() == "SciForge 0.1.0-beta.2 is available.", line_text())
    fake.slow = True
    press_update_now()
    ok = wait_for(lambda: update_ui._state["dialog"] is not None, 5)
    h.check("P7 a download dialog opens", ok)
    dialog = update_ui._state["dialog"]
    if dialog is None:
        return
    h.check("P7 it names the version", "0.1.0-beta.2" in dialog.title.text(), dialog.title.text())
    h.check("P7 it has a Cancel button", dialog.cancel_button.isVisible())
    midway = wait_for(lambda: 0 < dialog.bar.value() < 100, 8)
    h.check("P7 the progress bar moves (%d %%)" % dialog.bar.value(), midway)
    h.check("P7 the dialog says how much came down", " of " in dialog.status.text(), dialog.status.text())
    h.shot("download")


def p7_hand_over():
    from sciforge import update_core, update_ui

    fake = s["fake"]
    h.check("P7 the hand-over is called once the file is in", wait_for(lambda: bool(s["handed"]), 25))
    h.check("P7 the dialog is gone", update_ui._state["dialog"] is None)
    folder = updates_folder("0.1.0-beta.2")
    zip_path = os.path.join(folder, "SciForge-quick-update-v0.1.0-beta.2.zip")
    h.check("P7 the file is in SciForge's updates folder", os.path.isfile(zip_path), files_in(folder))
    expected = fake.files["/dl/SciForge-quick-update-v0.1.0-beta.2.zip"]
    h.check("P7 it is the file GitHub has (checksum)", os.path.isfile(zip_path) and update_core.verify(zip_path, hashlib.sha256(expected).hexdigest()))
    script = os.path.join(folder, "module", "install_update.ps1")
    h.check("P7 the update zip was unpacked", os.path.isfile(script) and os.path.isfile(os.path.join(folder, "module", "SciForge", "InitGui.py")))
    if not s["handed"]:
        return
    argv = s["handed"][0]
    h.check("P7 PowerShell runs the update script", argv[0] == "powershell.exe" and "-File" in argv and argv[argv.index("-File") + 1] == script, argv)
    h.check("P7 ... on the SciForge folder", argv[argv.index("-Target") + 1] == WINDOWS["home"], argv)
    h.check("P7 ... waiting for this very process", argv[argv.index("-WaitPid") + 1] == str(os.getpid()), argv)
    h.check("P7 ... restarting SciForge, quietly", "-Restart" in argv and "-Quiet" in argv, argv)
    h.check("P7 SciForge was asked to quit (once)", s["quit"] == [1], s["quit"])
    h.check("P7 the update is remembered for 'Updated to'", group().GetString("UpdateJustInstalled", "") == "0.1.0-beta.2")
    h.check("P7 no stray download is left", not [f for f in files_in(folder) if f.endswith(".part")])


# -- P8 --------------------------------------------------------------------------------------
def p8_cancel():
    from sciforge import update_ui

    reset_state()
    fake = s["fake"]
    fake.publish("0.1.0-beta.6", core="testcore", extra_kb=1500)
    auto_check()
    fake.slow = True
    press_update_now()
    wait_for(lambda: update_ui._state["dialog"] is not None, 5)
    dialog = update_ui._state["dialog"]
    h.check("P8 the dialog is open", dialog is not None)
    if dialog is None:
        return
    wait_for(lambda: dialog.bar.value() > 0, 8)
    w.click(dialog.cancel_button)
    gone = wait_for(lambda: update_ui._state["dialog"] is None and update_ui._state["download"] is None, 10)
    h.check("P8 Cancel closes the dialog and ends the download", gone)
    folder = updates_folder("0.1.0-beta.6")
    h.check("P8 no file is left (not even a half one)", not files_in(folder), files_in(folder))
    h.check("P8 nothing was handed over, SciForge was not asked to quit", not s["handed"] and not s["quit"])
    h.check("P8 nothing is remembered as installed", group().GetString("UpdateJustInstalled", "") == "")


# -- P9 --------------------------------------------------------------------------------------
def p9_wrong_checksum():
    from sciforge import update_ui

    reset_state()
    fake = s["fake"]
    fake.publish("0.1.0-beta.7", core="testcore", bad_module_hash=True)
    auto_check()
    press_update_now()
    refused = wait_for(lambda: answer() is not None, 20)
    h.check("P9 a box says what happened", refused)
    box = answer()
    if box is not None:
        h.check("P9 it mentions the checksum and says nothing was installed", "checksum" in box.text() and "installed nothing" in box.text(), box.text())
        h.shot("hash_refused")
    folder = updates_folder("0.1.0-beta.7")
    h.check("P9 the wrong file was deleted", not files_in(folder), files_in(folder))
    h.check("P9 nothing was handed over", not s["handed"] and not s["quit"])
    h.check("P9 the dialog is gone", update_ui._state["dialog"] is None)
    close_answer()


# -- P10 -------------------------------------------------------------------------------------
def p10_installer_when_the_core_changed():
    from sciforge import update_core, update_ui

    reset_state()
    fake = s["fake"]
    fake.publish("0.1.0-beta.8", core="newcore")  # ours is "testcore": the program itself changed
    auto_check()
    fake.slow = True
    press_update_now()
    wait_for(lambda: update_ui._state["dialog"] is not None, 5)
    dialog = update_ui._state["dialog"]
    h.check("P10 a download dialog opens", dialog is not None)
    if dialog is not None:
        note = dialog.findChild(QtWidgets.QLabel, "SciForgeUpdateNote")
        h.check("P10 it warns about 'Windows protected your PC' beforehand", note is not None and "Windows protected your PC" in note.text() and "Run anyway" in note.text(), note.text() if note else "")
        h.shot("download_installer")
    h.check("P10 the hand-over is called", wait_for(lambda: bool(s["handed"]), 25))
    folder = updates_folder("0.1.0-beta.8")
    installer = os.path.join(folder, "SciForge_v0.1.0-beta.8-Windows-x86_64-py311-installer.exe")
    h.check("P10 the installer is in the updates folder", os.path.isfile(installer), files_in(folder))
    if s["handed"]:
        argv = s["handed"][0]
        command = argv[argv.index("-Command") + 1] if "-Command" in argv else ""
        h.check("P10 PowerShell waits for this process, then starts the installer", ("Wait-Process -Id %d" % os.getpid()) in command and "Start-Process -FilePath '%s'" % installer in command, argv)
        h.check("P10 it is not the module update", "-Target" not in argv and "-Quiet" not in argv)
    h.check("P10 SciForge was asked to quit", s["quit"] == [1])
    h.check("P10 no module was unpacked", not os.path.isdir(os.path.join(folder, "module")))


# -- P11 -------------------------------------------------------------------------------------
class _Dialog:
    """A command's task dialog, open."""

    def __init__(self):
        self.form = QtWidgets.QLabel("A command is open")

    def getStandardButtons(self):
        button = QtWidgets.QDialogButtonBox.Cancel
        return int(getattr(button, "value", button))

    def reject(self):
        Gui.Control.closeDialog()
        return True


def p11_a_command_is_open():
    reset_state()
    fake = s["fake"]
    fake.publish("0.1.0-beta.9", core="testcore")
    auto_check()
    Gui.Control.showDialog(_Dialog())
    QtTest.QTest.qWait(200)
    h.check("P11 a command dialog is open", bool(Gui.Control.activeDialog()))
    asked = fake.count("/dl/SciForge-quick-update")
    press_update_now()
    wait_for(lambda: answer() is not None, 5)
    box = answer()
    h.check("P11 a box asks to finish the command first", box is not None and "command is still open" in box.text(), box.text() if box else "")
    QtTest.QTest.qWait(300)
    h.check("P11 nothing was downloaded", fake.count("/dl/SciForge-quick-update") == asked and not files_in(updates_folder("0.1.0-beta.9")))
    h.check("P11 nothing was handed over", not s["handed"] and not s["quit"])
    h.shot("command_open")
    close_answer()
    Gui.Control.closeDialog()
    QtTest.QTest.qWait(200)


# -- P12 -------------------------------------------------------------------------------------
def p12_cancel_at_save_your_changes():
    from sciforge import update_ui

    s["quit_answer"] = False  # the person pressed Cancel at "save your changes?"
    s["helper"].terminated = False
    press_update_now()
    wait_for(lambda: bool(s["handed"]), 25)
    h.check("P12 the helper was started and SciForge asked to quit", bool(s["handed"]) and s["quit"] == [1])
    wait_for(lambda: answer() is not None, 5)
    h.check("P12 the helper was stopped", s["helper"].terminated)
    h.check("P12 the update is not remembered as under way", group().GetString("UpdateJustInstalled", "") == "")
    box = answer()
    h.check("P12 the person is told the update was stopped", box is not None and "stopped" in box.text(), box.text() if box else "")
    close_answer()
    s["quit_answer"] = True
    h.check("P12 the check is not stuck", update_ui._state["download"] is None and not update_ui._state["busy"])


# -- P13 -------------------------------------------------------------------------------------
def p13_updated_to():
    from sciforge import update_ui
    import sciforge

    reset_state()
    group().SetString("UpdateJustInstalled", "0.1.0-beta.9")  # an update that did not finish
    before = len(sciforge.RECENT)
    update_ui._note_updated()
    update_ui._changed()
    h.check("P13 an update that did not happen says nothing on Home", line_text() == "", line_text())
    h.check("P13 ... it is logged", any("did not finish" in m for m in sciforge.RECENT[before:]))
    group().SetString("UpdateJustInstalled", VERSION)  # the start after a good update
    older = updates_folder("0.1.0-beta.2")  # (the download of an earlier try is left over)
    os.makedirs(older, exist_ok=True)
    kept = updates_folder(VERSION)
    os.makedirs(kept, exist_ok=True)
    with open(os.path.join(kept, "install_update.log"), "w") as handle:
        handle.write("the log of the update that just worked\n")
    update_ui._note_updated()
    wait_for(lambda: not os.path.isdir(older), 5)
    h.check("P13 the downloads of other versions are tidied away", not os.path.isdir(older), older)
    h.check("P13 ... the folder of this one (its log) stays", os.path.isfile(os.path.join(kept, "install_update.log")))
    update_ui._changed()
    found = line()
    h.check("P13 Home says it once", line_text() == "Updated to %s." % VERSION, line_text())
    h.check("P13 ... What's new and Dismiss, not Update now", found.whats_new_button.isVisible() and found.dismiss_button.isVisible() and not found.update_button.isVisible() and not found.later_button.isVisible())
    h.check("P13 it is remembered only for this start", group().GetString("UpdateJustInstalled", "x") == "")
    QtTest.QTest.qWait(250)  # (painted before the screen is looked at)
    inside = pixel(found, 5, found.height() // 2)
    h.check("P13 it is on the screen, in the blue of the update line", near(inside, (0x35, 0x4A, 0x63)), inside.name())
    h.shot("updated_to")
    w.click(found.whats_new_button)
    wait_for(lambda: bool(s["opened"]), 3)
    h.check("P13 What's new opens this version's page", s["opened"] and s["opened"][-1].endswith("/releases/tag/sciforge-v" + VERSION), s["opened"])
    update_ui._note_updated()
    h.check("P13 the next start does not say it again", group().GetString("UpdateJustInstalled", "") == "")
    w.click(found.dismiss_button)
    QtTest.QTest.qWait(100)
    h.check("P13 Dismiss hides it", line_text() == "", line_text())


# -- P14 -------------------------------------------------------------------------------------
def p14_linux_appimage():
    from sciforge import update_ui

    reset_state()
    update_ui.LAYOUT = dict(APPIMAGE)
    fake = s["fake"]
    fake.publish("0.1.0-beta.10", core="testcore")
    auto_check()
    press_update_now()
    wait_for(lambda: answer() is not None, 5)
    box = answer()
    h.check("P14 a box answers", box is not None)
    if box is not None:
        h.check("P14 it says to replace the old AppImage", "replace the old one" in box.text(), box.text())
        w.click(box_button(box, "Open the release page"))
        wait_for(lambda: bool(s["opened"]), 3)
    h.check("P14 the release page opens", s["opened"] and s["opened"][-1].endswith("/releases/tag/sciforge-v0.1.0-beta.10"), s["opened"])
    h.check("P14 nothing was downloaded or handed over", not s["handed"] and fake.count("/dl/SciForge") == 0)
    close_answer()
    update_ui.LAYOUT = dict(WINDOWS)


# -- P15 -------------------------------------------------------------------------------------
def dialog():
    from sciforge import preferences_ui

    d = preferences_ui.PreferencesDialog.last
    try:
        return d if d is not None and d.isVisible() else None
    except RuntimeError:
        return None


def p15_open_preferences():
    from sciforge import home_ui

    reset_state()
    home_ui.show()
    QtTest.QTest.qWait(200)
    w.click(home_ui.view().preferences_button)  # Home's own Preferences button
    QtTest.QTest.qWait(400)


def p15_the_updates_group():
    d = dialog()
    h.check("P15 Preferences is open", d is not None)
    if d is None:
        return
    check = d.widgets.get("check_updates")
    channel = d.widgets.get("update_channel")
    h.check("P15 General has 'Check for updates when SciForge starts'", check is not None and isinstance(check, QtWidgets.QCheckBox))
    h.check("P15 ... on by default", check is not None and check.isChecked())
    h.check("P15 General has the channel choice", channel is not None and [channel.itemText(n) for n in range(channel.count())] == ["Stable only", "Betas too"])
    h.check("P15 ... Betas too while this is a beta", channel is not None and channel.currentText() == "Betas too", channel.currentText() if channel else "")
    boxes = [g.title() for g in d.findChildren(QtWidgets.QGroupBox)]
    h.check("P15 the group is called Updates", "Updates" in boxes, boxes)
    if check is not None:  # scroll the page to the group, then look at it
        parent = check.parentWidget()
        while parent is not None and not isinstance(parent, QtWidgets.QScrollArea):
            parent = parent.parentWidget()
        if parent is not None:
            parent.ensureWidgetVisible(channel)
        QtTest.QTest.qWait(200)
        h.shot("preferences_updates")


def p15_switch_off_and_stable():
    from sciforge import update_ui

    d = dialog()
    check, channel = d.widgets["check_updates"], d.widgets["update_channel"]
    m.set_check(check, False)
    channel.setCurrentIndex(channel.findText("Stable only"))
    w.click(d.ok_button)
    QtTest.QTest.qWait(300)
    h.check("P15 OK keeps the choices", group().GetBool("CheckForUpdates", True) is False and group().GetString("UpdateChannel", "") == "stable")
    h.check("P15 ... the update check reads them", not update_ui.check_on_start() and update_ui.channel() == "stable")
    count = s["fake"].count("/repos")
    due_again()
    update_ui._start_if_due()
    QtTest.QTest.qWait(300)
    h.check("P15 switched off, nothing asks GitHub at the start", s["fake"].count("/repos") == count)
    group().RemBool("CheckForUpdates")
    group().RemString("UpdateChannel")


def teardown():
    from sciforge import home_ui, update_core, update_ui

    forget_prefs()
    update_ui.OPEN_URL = update_ui.HAND_OVER = update_ui.QUIT = None
    update_ui.LAYOUT = update_ui.INSTALLED = None
    update_core.API_BASE = s["old_base"]
    update_ui.__version__ = s["old_version"]
    update_ui._state["answer"] = None
    update_ui._state["release"] = None
    update_ui._state["version"] = ""
    update_ui._changed()
    try:
        s["fake"].stop()
    except Exception:
        pass
    h.check("the real GitHub is the default address again", update_core.API_BASE.startswith("https://api.github.com"))


def _wait(step, ms):
    step.wait_ms = ms
    return step


h.run(
    "update_check",
    [
        setup,
        p1_home_without_line,
        _wait(p1_check_does_not_hold_the_window_up, 300),
        p1_the_line_on_screen,
        _wait(p16_the_icon_on_screen, 300),
        p1b_the_light_look,
        _wait(p2_once_a_day, 300),
        p3_later_hides_the_line,
        p3_menu_asks_and_answers,
        p3_whats_new,
        p3_a_newer_version_shows_the_line_again,
        p16_the_icon_menu,
        p4_up_to_date,
        p5_channels,
        p6_offline,
        p7_update_now_on_a_module_update,
        _wait(p7_hand_over, 500),
        p8_cancel,
        p9_wrong_checksum,
        p10_installer_when_the_core_changed,
        p11_a_command_is_open,
        p12_cancel_at_save_your_changes,
        p13_updated_to,
        p14_linux_appimage,
        p15_open_preferences,
        p15_the_updates_group,
        p15_switch_off_and_stable,
        teardown,
    ],
)
