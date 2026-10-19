# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Home tab (docs/sciforge/parity/home.md, brief home-cloud-ai.md M1), used with real
clicks.

Path 1, start: SciForge opens on its Home tab (the first document tab, the active one),
  the ribbon and the timeline shown, the Home button at the left of the application bar,
  no navigation bar over Home (it comes back on a design).
Path 2, an empty list says what to do; New design starts a design with a body, Home stays
  as a tab.
Path 3, a design saved and closed: closing the last design shows Home again, the design
  first in Recent with its picture, "This computer, edited just now"; double-click opens it.
Path 4, the Home tab closed with its x; the Home button brings it back.
Path 5, a second design is newer, so first; Pin the older one: it comes first.
Path 6, a design deleted behind SciForge's back is greyed "Not found"; its menu offers
  Locate... and Remove from List, no Open; Remove from List takes it off.
Path 7, a design moved: Locate... finds it again, still pinned.
Path 8, search narrows the tiles; nothing found says so.
Path 9, This computer lists the project folder (its folder and design); double-click the
  folder goes in, Up comes back.
Path 10, a recovery copy left by an earlier session shows the banner; Recover... opens the
  Recover dialog.
Path 11, Show Home at start off: closing the last design leaves the window empty, as before.
"""

import os
import shutil
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtWidgets

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import versions_input as vi
from SciForgeTests.gui import widget_input as wi

s = {}
FILES = "User parameter:BaseApp/Preferences/Mod/SciForge/Files"


def home():
    from sciforge import home_ui

    return home_ui.view()


def tab_texts():
    bar = h.document_tabs()
    return [bar.tabText(i) for i in range(bar.count())] if bar is not None else []


def current_tab():
    bar = h.document_tabs()
    return bar.tabText(bar.currentIndex()) if bar is not None and bar.count() else ""


def tiles():
    page = home()
    return page.items() if page is not None else []


def names():
    return [text.split("\n")[0] for _k, _key, _p, text, _s in tiles()]


def tile_pos(name):
    page = home()
    for i in range(page.list.count()):
        item = page.list.item(i)
        if item.text().split("\n")[0] == name:
            return page.list.visualItemRect(item).center()
    return None


def make_box(doc, size):
    body = doc.addObject("PartDesign::Body", "Body")
    box = doc.addObject("PartDesign::AdditiveBox", "Box")
    body.addObject(box)
    box.Length = box.Width = box.Height = size
    doc.recompute()
    return body


def save_new(name, size):
    doc = App.newDocument(name)
    make_box(doc, size)
    h.fit()
    path = os.path.join(s["project"], name + ".FCStd")
    doc.saveAs(path)
    return doc, path


def close_all():
    for name in list(App.listDocuments()):
        Gui.getDocument(name).Modified = False
        App.closeDocument(name)


def wait_tiles(step):
    """Run once the tiles have their pictures (the worker thread answers)."""
    step.wait_ms = 1500
    return step


# -- Path 1 -------------------------------------------------------------------------------
def at_start():
    from sciforge import home_ui, shell

    h.check("SciForge is on at start", shell.is_on())
    h.check("the Home tab is open at start", home() is not None)
    h.check("Home is the active tab", home_ui.is_active() and current_tab() == "Home", tab_texts())
    h.check("Home is the first document tab", tab_texts()[:1] == ["Home"], tab_texts())
    main = Gui.getMainWindow()
    ribbon = main.findChild(QtWidgets.QToolBar, "SciForgeRibbonBar")
    h.check("the ribbon is shown", ribbon is not None and ribbon.isVisible())
    timeline = main.findChild(QtWidgets.QDockWidget, "SciForgeTimelineDock")
    h.check("the timeline is shown", timeline is not None and timeline.isVisible())
    button = wi.quick_access("Home")
    h.check("the Home button is in the application bar", button is not None)
    data = wi.quick_access("Data Panel")
    h.check(
        "... at the far left, before the Data Panel button",
        button is not None and data is not None and button.x() < data.x(),
    )
    from sciforge import navbar_ui

    nav = navbar_ui.bar()
    h.check("no navigation bar over Home", nav is None or not nav.isVisible())
    h.shot("start")


def setup():
    from sciforge import home_core, home_ui

    s["project"] = tempfile.mkdtemp(prefix="sciforge-home-project-")
    App.ParamGet(FILES).SetString("ProjectFolder", s["project"])
    App.ParamGet(FILES).SetBool("AskDescription", False)
    os.makedirs(os.path.join(s["project"], "Robots"))
    state = home_core.empty()
    state["merged_mru"] = True  # (an earlier scenario's designs are not this one's)
    home_ui.save_state(state)
    home().refresh()


# -- Path 2 -------------------------------------------------------------------------------
def empty_list():
    page = home()
    h.check("an empty list says what to do", page.empty.isVisible(), page.empty.text())
    h.check("... New design and Open", "New design" in page.empty.text(), page.empty.text())
    h.check("no Clear List on an empty list", not page.clear_button.isVisible())


def new_design():
    wi.click(home().new_button)


def new_design_made():
    from sciforge import commands, home_ui

    doc = App.ActiveDocument
    h.check("New design made a design", doc is not None and len(App.listDocuments()) == 1)
    h.check("... with a body", commands.find_body() is not None)
    h.check("... in front", not home_ui.is_active() and current_tab() != "Home", current_tab())
    h.check("Home stays as a tab", "Home" in tab_texts(), tab_texts())
    from sciforge import navbar_ui

    nav = navbar_ui.bar()
    h.check("the navigation bar is back on the design", nav is not None and nav.isVisible())
    close_all()


# -- Path 3 -------------------------------------------------------------------------------
def save_arm():
    _doc, s["arm"] = save_new("Arm", 10)


save_arm.wait_ms = 1500


def close_arm():
    close_all()


def closing_the_last_design_shows_home():
    from sciforge import home_core, home_ui, versions

    h.check("closing the last design shows Home", home_ui.is_active(), current_tab())
    h.check("Arm is first in Recent", names()[:1] == ["Arm"], names())
    page = home()
    h.check("its picture is loaded", page.loading() == 0, page.loading())
    key = versions.path_key(s["arm"])
    status, mtime = home_core.file_status(s["arm"])
    cached = home_core.thumb_file(home_ui.thumbs_dir(), key, mtime)
    h.check("the design's own picture is cached", os.path.isfile(cached), cached)
    text = [t for _k, _key, _p, t, _s in tiles()][0] if tiles() else ""
    h.check("it says where and when", "This computer, edited just now" in text, text)
    h.check("... and its version (v1: the first save)", text.endswith(", v1"), text)
    h.shot("recent")


wait_tiles(closing_the_last_design_shows_home)


def double_click_arm():
    wi.double_click(home().list.viewport(), tile_pos("Arm"))


def arm_opened():
    from sciforge import versions

    docs = [d for d in App.listDocuments().values() if versions.same_path(d.FileName, s["arm"])]
    h.check("double-click opened Arm", len(docs) == 1, list(App.listDocuments()))
    h.check("Arm is in front", current_tab().startswith("Arm"), current_tab())


# -- Path 4 -------------------------------------------------------------------------------
def close_home_tab():
    bar = h.document_tabs()
    index = tab_texts().index("Home")
    button = bar.tabButton(index, QtWidgets.QTabBar.RightSide)
    wi.click(button)


def home_tab_closed():
    h.check("the x closed the Home tab", home() is None and "Home" not in tab_texts(), tab_texts())
    h.check("Arm is still open", any(t.startswith("Arm") for t in tab_texts()), tab_texts())


def home_button():
    wi.click(wi.quick_access("Home"))


def home_back():
    from sciforge import home_ui

    h.check("the Home button brought Home back", home() is not None and home_ui.is_active())
    h.check("... with Arm in Recent", "Arm" in names(), names())


wait_tiles(home_back)


# -- Path 5 -------------------------------------------------------------------------------
def save_base():
    close_all()
    _doc, s["base"] = save_new("Base", 20)


save_base.wait_ms = 1500


def base_first():
    close_all()


def newest_first():
    h.check("the newer design comes first", names()[:2] == ["Base", "Arm"], names())


wait_tiles(newest_first)


def pin_arm():
    h.check("Pin is in Arm's menu", wi.right_click(home().list.viewport(), tile_pos("Arm"), "Pin"))


def arm_pinned_first():
    from sciforge import home_core, home_ui, versions

    h.check("a pinned design comes first", names()[:2] == ["Arm", "Base"], names())
    entry = home_core.find(home_ui.load_state(), versions.path_key(s["arm"]))
    h.check("... and is kept pinned", entry is not None and entry["pinned"], entry)
    texts = [t for t, _on in wi.menu_texts(home().list.viewport(), tile_pos("Arm"))]
    h.check("its menu says Unpin", "Unpin" in texts, texts)


wait_tiles(arm_pinned_first)


# -- Path 6 -------------------------------------------------------------------------------
def delete_base():
    os.remove(s["base"])
    home().refresh()


def base_missing():
    from sciforge import home_core

    found = [t for t in tiles() if t[3].startswith("Base")]
    h.check("a deleted design is still listed", len(found) == 1, names())
    h.check(
        "... greyed, Not found",
        bool(found) and found[0][4] == home_core.MISSING and "Not found" in found[0][3],
        found,
    )
    texts = [t for t, _on in wi.menu_texts(home().list.viewport(), tile_pos("Base"))]
    h.check(
        "its menu: Locate..., Remove from List, no Open",
        "Locate..." in texts and "Remove from List" in texts and "Open" not in texts,
        texts,
    )
    h.shot("missing")


wait_tiles(base_missing)


def double_click_missing():
    wi.double_click(home().list.viewport(), tile_pos("Base"))


def nothing_opened():
    h.check("double-click on a missing design opens nothing", not App.listDocuments())


def remove_base():
    h.check(
        "Remove from List is there",
        wi.right_click(home().list.viewport(), tile_pos("Base"), "Remove from List"),
    )


def base_gone():
    h.check("Remove from List took it off", "Base" not in names(), names())
    h.check("... Arm stays", "Arm" in names(), names())


wait_tiles(base_gone)


# -- Path 7 -------------------------------------------------------------------------------
def move_arm():
    s["arm_moved"] = os.path.join(s["project"], "Robots", "Arm.FCStd")
    shutil.move(s["arm"], s["arm_moved"])
    home().refresh()


def locate_arm():
    from sciforge import home_ui

    home_ui.LOCATE_PICKER = lambda: s["arm_moved"]
    h.check(
        "Locate... is there",
        wi.right_click(home().list.viewport(), tile_pos("Arm"), "Locate..."),
    )


wait_tiles(locate_arm)


def arm_found():
    from sciforge import home_core, home_ui, versions

    home_ui.LOCATE_PICKER = None
    entry = home_core.find(home_ui.load_state(), versions.path_key(s["arm_moved"]))
    h.check("Locate... found Arm at its new place", entry is not None, entry)
    h.check("... still pinned", entry is not None and entry["pinned"], entry)
    h.check("... inside This computer", entry is not None and entry["rel"] == "Robots/Arm.FCStd")
    found = [t for t in tiles() if t[3].startswith("Arm")]
    h.check("... no longer greyed", bool(found) and found[0][4] == home_core.OK, found)


wait_tiles(arm_found)


# -- Path 8 -------------------------------------------------------------------------------
def search_nothing():
    vi.type_into(home().search, "zzz")


def nothing_found():
    page = home()
    h.check("no tile matches zzz", not names(), names())
    h.check("... and it says so", "zzz" in page.empty.text() and page.empty.isVisible())


def search_arm():
    vi.type_into(home().search, "arm")


def arm_found_by_search():
    h.check("search finds Arm", names() == ["Arm"], names())
    vi.type_into(home().search, "")


# -- Path 9 -------------------------------------------------------------------------------
def click_this_computer():
    page = home()
    for i in range(page.places.count()):
        item = page.places.item(i)
        if item.text() == "This computer":
            wi.click(page.places.viewport(), page.places.visualItemRect(item).center())


def project_listed():
    page = home()
    h.check("This computer lists the project folder", page.mode == "local", page.mode)
    h.check("... its folder Robots", "Robots" in names(), names())
    h.check("the title names the place", page.title.text() == "This computer", page.title.text())


def into_robots():
    wi.double_click(home().list.viewport(), tile_pos("Robots"))


def in_robots():
    page = home()
    h.check("double-click went into Robots", "Arm" in names(), names())
    h.check("... the title says so", page.title.text() == "This computer / Robots")
    h.check("... Up is offered", page.up.isVisible())


wait_tiles(in_robots)


def click_up():
    wi.click(home().up)


def back_up():
    h.check("Up came back", "Robots" in names(), names())
    page = home()
    for i in range(page.places.count()):
        item = page.places.item(i)
        if item.text() == "Recent":
            wi.click(page.places.viewport(), page.places.visualItemRect(item).center())


# -- Path 10 ------------------------------------------------------------------------------
def leave_recovery_copy():
    from sciforge import versions, versions_ui

    folder = versions_ui.recovery_folder()
    os.makedirs(folder, exist_ok=True)
    s["recovery_key"] = "home-scenario"
    copy, _side = versions.recovery_paths(folder, s["recovery_key"])
    shutil.copy(s["arm_moved"], copy)
    versions.write_recovery_sidecar(folder, s["recovery_key"], "Arm", s["arm_moved"], "earlier")
    home().update_banner()


def banner_shown():
    page = home()
    h.check("the recovery banner shows", page.banner.isVisible(), page.banner_text.text())
    h.check("... it counts the design", "1 design" in page.banner_text.text())
    wi.click(page.recover_button)


def recover_dialog_open():
    from sciforge import versions, versions_ui

    dialog = vi.recover_dialog()
    h.check("Recover... opened the Recover dialog", dialog is not None)
    if dialog is not None:
        vi.cancel_dialog(dialog)
    versions.discard_recovery(versions_ui.recovery_folder(), s["recovery_key"])
    home().update_banner()


def banner_gone():
    h.check("no banner once nothing is left to recover", not home().banner.isVisible())
    h.check("no pop-up left", not h.popups(), h.popups())


# -- Path 11 ------------------------------------------------------------------------------
def option_off():
    from sciforge import home_ui, preferences_ui

    preferences_ui.save({"show_home": False})
    h.check("the option is kept", not home_ui.show_at_start())
    home_ui.close()
    vi_open = home_ui.open_design(s["arm_moved"])
    h.check("Arm opened again", vi_open is not None)


def close_with_option_off():
    close_all()


def no_home_with_option_off():
    from sciforge import home_ui, preferences_ui

    h.check("option off: closing the last design shows no Home", home() is None, tab_texts())
    preferences_ui.save({"show_home": True})
    h.check("the option is on again", home_ui.show_at_start())
    App.newDocument("Scratch")  # (the harness ends on a design)


h.run(
    "home_screen",
    [
        at_start,
        setup,
        empty_list,
        new_design,
        new_design_made,
        save_arm,
        close_arm,
        closing_the_last_design_shows_home,
        double_click_arm,
        arm_opened,
        close_home_tab,
        home_tab_closed,
        home_button,
        home_back,
        save_base,
        base_first,
        newest_first,
        pin_arm,
        arm_pinned_first,
        delete_base,
        base_missing,
        double_click_missing,
        nothing_opened,
        remove_base,
        base_gone,
        move_arm,
        locate_arm,
        arm_found,
        search_nothing,
        nothing_found,
        search_arm,
        arm_found_by_search,
        click_this_computer,
        project_listed,
        into_robots,
        in_robots,
        click_up,
        back_up,
        leave_recovery_copy,
        banner_shown,
        recover_dialog_open,
        banner_gone,
        option_off,
        close_with_option_off,
        no_home_with_option_off,
    ],
)
