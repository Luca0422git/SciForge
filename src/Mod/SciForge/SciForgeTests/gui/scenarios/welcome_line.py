# SPDX-License-Identifier: LGPL-2.1-or-later
"""The small welcome on Home (brief beta-release.md, R4; Luca: "its supposed to feel like
fusion ... dont overdo it"), used with real clicks.

Path 1, a fresh profile (the preference WelcomeShown not set): Home shows one slim line in the
  look of the recovery banner, "Welcome to SciForge 0.1.0-beta. It works like Fusion: ...
  save often.", with [Cheat sheet] [Open an example] [Report a problem] [x]. No popup, no
  tour; the preference is set at once.
Path 2, [Cheat sheet] opens the cheat sheet in a window of its own, offline; if the module's
  copy is missing the page on GitHub is opened instead (browser seam).
Path 3, [Open an example] opens the Raspberry Pi 5 case design (a copy in SciForge's folder, so
  saving works): a design with its bodies, in front of Home.
Path 4, [Report a problem] opens Report a Problem.
Path 5, the x hides the line for good: Home opened again, and "the next start", show nothing.
Path 6, a start after the line was shown never shows it again; with the example missing from
  the install the button is not there.
"""

import os

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtWidgets

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import widget_input as wi

s = {"urls": []}
PREFS = "User parameter:BaseApp/Preferences/Mod/SciForge"


def home():
    from sciforge import home_ui

    return home_ui.view()


def notices():
    page = home()
    return getattr(page, "notices", None) if page is not None else None


def flag():
    return App.ParamGet(PREFS).GetBool("WelcomeShown", False)


def reopen_home():
    from sciforge import home_ui

    home_ui.close()
    home_ui.show()


def colour_of(widget):
    image = QtWidgets.QApplication.primaryScreen().grabWindow(0).toImage()
    top = widget.mapToGlobal(widget.rect().topLeft())
    return image.pixelColor(top.x() + 3, top.y() + widget.height() // 2)


# -- Path 1 -------------------------------------------------------------------------------
def fresh_profile():
    """Like the first start: the preference not set, a new session."""
    from sciforge import home_notices_ui

    s["old_root"] = home_notices_ui.ROOT_OF_MODULE
    home_notices_ui.OPEN_URL = lambda url: s["urls"].append(url) or True
    home_notices_ui.reset_for_tests(False)
    App.ParamGet(PREFS).RemBool("WelcomeShown")
    h.check("the preference is not set (a fresh profile)", flag() is False)
    home_notices_ui.welcome().reset()
    reopen_home()


fresh_profile.wait_ms = 1200


def line_shown():
    import sciforge

    page = notices()
    h.check("Home has its slim lines", page is not None)
    if page is None:
        return
    line = page.welcome
    h.check("the welcome line is shown on the first start", line.isVisible())
    want = (
        "Welcome to SciForge %s. It works like Fusion: the ribbon, the timeline, S for search. "
        "This is a beta: save often." % sciforge.__version__
    )
    h.check("... it says the brief's words", line.text.text() == want, line.text.text())
    names = [
        "SciForgeHomeWelcomeSheet",
        "SciForgeHomeWelcomeExample",
        "SciForgeHomeWelcomeReport",
        "SciForgeHomeWelcomeClose",
    ]
    h.check(
        "... with [Cheat sheet] [Open an example] [Report a problem] [x]",
        list(line.buttons) == names and all(line.buttons[n].isVisible() for n in names),
        list(line.buttons),
    )
    labels = [line.buttons[n].text() for n in names]
    h.check(
        "... worded so",
        labels == ["Cheat sheet", "Open an example", "Report a problem", "x"],
        labels,
    )
    h.check("... slim: one line high", line.height() < 60, line.height())
    colour = line_colour(line)
    h.check(
        "... in the look of the recovery banner (checked on the screen)",
        all(abs(a - b) < 12 for a, b in zip(colour, (0x5A, 0x4A, 0x2A))),
        colour,
    )
    h.check("no pop-up window, no dialog", QtWidgets.QApplication.activeModalWidget() is None)
    h.check("the preference is set at once, so the next start shows nothing", flag() is True)
    h.check("no crash line next to it", not page.crash.isVisible())
    h.check(
        "the heading and the design rows are still there",
        home().findChild(QtWidgets.QLabel, "SciForgeHomeHeading").isVisible()
        and home().new_button.isVisible(),
    )
    h.shot("welcome")


def line_colour(widget):
    c = colour_of(widget)
    return (c.red(), c.green(), c.blue())


# -- Path 2 -------------------------------------------------------------------------------
def cheat_sheet():
    page = notices()
    if page is not None:
        wi.click(page.welcome.buttons["SciForgeHomeWelcomeSheet"])


cheat_sheet.wait_ms = 1200


def cheat_sheet_open():
    from sciforge import home_notices_ui

    dlg = home_notices_ui.cheat_sheet_dialog()
    h.check("[Cheat sheet] opens the cheat sheet in a window", dlg is not None)
    if dlg is None:
        return
    text = dlg.browser.toPlainText()
    h.check(
        "... it is the cheat sheet",
        "cheat sheet" in text.lower() and "Press Pull" in text,
        text[:200],
    )
    h.check("... its tables are drawn (the S key row)", "Command search" in text)
    h.check("no browser was needed", s["urls"] == [], s["urls"])
    h.shot("cheat_sheet")
    dlg.close()


def cheat_sheet_missing():
    """The module's copy gone: the page on GitHub opens instead."""
    from sciforge import home_notices_ui

    home_notices_ui.ROOT_OF_MODULE = os.path.join(os.path.dirname(__file__), "nowhere")
    page = notices()
    if page is not None:
        wi.click(page.welcome.buttons["SciForgeHomeWelcomeSheet"])
    # (SciForge says in a warning that its copy is missing: that is this test's own doing)
    s["warned"] = h.new_errors()


cheat_sheet_missing.wait_ms = 800


def cheat_sheet_on_github():
    from sciforge import home_notices_ui, notices_core

    home_notices_ui.ROOT_OF_MODULE = s["old_root"]
    h.check(
        "without its copy, [Cheat sheet] opens the page on GitHub",
        s["urls"] == [notices_core.CHEAT_SHEET_URL],
        s["urls"],
    )
    h.check("... and no empty window", home_notices_ui.cheat_sheet_dialog() is None)
    h.check(
        "... and says in the log that the copy is missing",
        any("not installed" in line for line in s.get("warned", [])),
        s.get("warned"),
    )


# -- Path 3 -------------------------------------------------------------------------------
def example():
    page = notices()
    if page is not None:
        wi.click(page.welcome.buttons["SciForgeHomeWelcomeExample"])


example.wait_ms = 4000


def example_open():
    from sciforge import home_ui, notices_core

    docs = list(App.listDocuments().values())
    h.check("[Open an example] opened a design", len(docs) == 1, [d.Name for d in docs])
    if not docs:
        return
    doc = docs[0]
    expected = notices_core.example_copy_target(App.getUserAppDataDir())
    h.check(
        "... from a copy in SciForge's own folder (so Save works)",
        os.path.normcase(doc.FileName) == os.path.normcase(expected),
        doc.FileName,
    )
    h.check(
        "... it is the Pi 5 case: two bodies",
        len([o for o in doc.Objects if o.TypeId == "PartDesign::Body"]) == 2,
        [o.Name for o in doc.Objects if o.TypeId == "PartDesign::Body"],
    )
    h.check("... in front of Home", not home_ui.is_active())
    h.fit()
    h.shot("example")


def example_again():
    """A second click does not open a second copy and never overwrites a changed one."""
    from sciforge import home_ui, notices_core

    docs = list(App.listDocuments().values())
    path = docs[0].FileName if docs else ""
    stamp = os.path.getmtime(path) if path else 0
    home_ui.show()
    page = notices()
    if page is not None:
        wi.click(page.welcome.buttons["SciForgeHomeWelcomeExample"])
    s["example_stamp"] = (path, stamp)


example_again.wait_ms = 1500


def example_again_checked():
    path, stamp = s["example_stamp"]
    h.check(
        "a second click opens no second design",
        len(App.listDocuments()) == 1,
        list(App.listDocuments()),
    )
    h.check("... and leaves the copy alone", os.path.getmtime(path) == stamp)
    for name in list(App.listDocuments()):
        Gui.getDocument(name).Modified = False
        App.closeDocument(name)


example_again_checked.wait_ms = 1200


# -- Path 4 -------------------------------------------------------------------------------
def report_button():
    from sciforge import home_ui

    home_ui.show()
    page = notices()
    h.check(
        "Home is back with the welcome line still up", page is not None and page.welcome.isVisible()
    )
    if page is not None:
        wi.click(page.welcome.buttons["SciForgeHomeWelcomeReport"])


report_button.wait_ms = 1500


def report_opened():
    from sciforge import report_ui

    dlg = report_ui.dialog()
    h.check("[Report a problem] opens Report a Problem", dlg is not None)
    if dlg is not None:
        wi.click(dlg.close_button)


# -- Path 5 -------------------------------------------------------------------------------
def the_x():
    page = notices()
    if page is not None:
        wi.click(page.welcome.buttons["SciForgeHomeWelcomeClose"])


the_x.wait_ms = 600


def the_x_done():
    page = notices()
    h.check("the x hides the line", page is not None and not page.welcome.isVisible())
    h.check("... the rest of Home is untouched", home().new_button.isVisible())
    reopen_home()


the_x_done.wait_ms = 1000


def still_hidden():
    page = notices()
    h.check("Home opened again shows no welcome", page is not None and not page.welcome.isVisible())


# -- Path 6 -------------------------------------------------------------------------------
def next_start():
    from sciforge import home_notices_ui

    home_notices_ui.welcome().reset()  # (a new session: the preference is all that is left)
    reopen_home()


next_start.wait_ms = 1000


def next_start_checked():
    page = notices()
    h.check("the next start shows no welcome", page is not None and not page.welcome.isVisible())
    h.check("the preference says it was shown", flag() is True)


def shown_but_not_closed():
    """The first session's line, not closed with the x: the next start still shows nothing."""
    from sciforge import home_notices_ui

    home_notices_ui.reset_for_tests(False)
    h.check("(the line is up again for a fresh profile)", notices().welcome.isVisible())
    home_notices_ui.welcome().reset()  # the next start, the x never pressed
    reopen_home()


shown_but_not_closed.wait_ms = 1000


def shown_but_not_closed_checked():
    page = notices()
    h.check(
        "a start after a line nobody closed shows nothing",
        page is not None and not page.welcome.isVisible(),
    )


def example_missing():
    """An install without the example: no button for it."""
    from sciforge import home_notices_ui

    home_notices_ui.ROOT_OF_MODULE = os.path.join(os.path.dirname(__file__), "nowhere")
    home_notices_ui.reset_for_tests(False)
    reopen_home()


example_missing.wait_ms = 1000


def example_missing_checked():
    from sciforge import home_notices_ui

    page = notices()
    h.check("the line is shown", page is not None and page.welcome.isVisible())
    button = page.welcome.buttons["SciForgeHomeWelcomeExample"] if page is not None else None
    h.check(
        "... without an [Open an example] button when it is not installed",
        button is not None and not button.isVisible(),
    )
    home_notices_ui.ROOT_OF_MODULE = s["old_root"]
    home_notices_ui.OPEN_URL = None
    home_notices_ui.reset_for_tests(True)


h.run(
    "welcome_line",
    [
        fresh_profile,
        line_shown,
        cheat_sheet,
        cheat_sheet_open,
        cheat_sheet_missing,
        cheat_sheet_on_github,
        example,
        example_open,
        example_again,
        example_again_checked,
        report_button,
        report_opened,
        the_x,
        the_x_done,
        still_hidden,
        next_start,
        next_start_checked,
        shown_but_not_closed,
        shown_but_not_closed_checked,
        example_missing,
        example_missing_checked,
    ],
)
