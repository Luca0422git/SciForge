# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Home tab (docs/sciforge/parity/home.md, brief home-cloud-ai.md M1), used with real
clicks.

Path 1, start: SciForge opens on its Home tab (the first document tab, the active one),
  the ribbon's top bar and the timeline shown, its commands hidden on Home (Luca: "on the
  home screen, lets hide the toolbar"), the Home button at the left of the application bar,
  no navigation bar over Home (both come back on a design).
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
Path 9, Luca's sketch: rows top to bottom, Recent then This computer. This computer shows
  where designs are saved (its path) and every design in it, its folders' too ("in
  Robots"), and a design saved in another folder of this computer; its ... menu: Show in
  Folder, Change Folder.... A new design's Save dialog starts in that folder, even after a
  save in another folder (Luca: his saves did not show in This computer).
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


def tiles(row="recent"):
    page = home()
    return page.items(row) if page is not None else []


def names(row="recent"):
    return [text.split("\n")[0] for _k, _key, _p, text, _s in tiles(row)]


def at(name, row="recent"):
    """(the row's tile list viewport, the tile's centre) for real clicks."""
    page = home()
    tiles_list = page.row(row).list
    for i in range(tiles_list.count()):
        item = tiles_list.item(i)
        if item.text().split("\n")[0] == name:
            tiles_list.scrollToItem(item)
            page.scroll.ensureWidgetVisible(tiles_list)
            return tiles_list.viewport(), tiles_list.visualItemRect(item).center()
    return tiles_list.viewport(), None


def commands_shown():
    from sciforge import shell

    ribbon = shell.ribbon()
    return ribbon is not None and ribbon.command_area.isVisible()


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
    h.check("... its commands hidden on Home, the top bar kept", not commands_shown())
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
    # (given back at the end: a CI shard's later scenarios share this profile)
    s["old_project"] = App.ParamGet(FILES).GetString("ProjectFolder", "")
    App.ParamGet(FILES).SetString("ProjectFolder", s["project"])
    os.makedirs(os.path.join(s["project"], "Robots"))
    state = home_core.empty()
    state["merged_mru"] = True  # (an earlier scenario's designs are not this one's)
    home_ui.save_state(state)
    home().refresh()


# -- Path 2 -------------------------------------------------------------------------------
def empty_list():
    recent = home().row("recent")
    h.check("an empty list says what to do", recent.empty.isVisible(), recent.empty.text())
    h.check("... New design and Open", "New design" in recent.empty.text(), recent.empty.text())
    h.check("no Clear List on an empty list", not recent.clear_button.isVisible())


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
    h.check("the ribbon's commands are back on the design", commands_shown())
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
    h.check("... and in This computer's row", "Arm" in names("local"), names("local"))
    h.check("it says where and when", "This computer, edited just now" in text, text)
    h.check("... and its version (v1: the first save)", text.endswith(", v1"), text)
    h.shot("recent")


wait_tiles(closing_the_last_design_shows_home)


def double_click_arm():
    wi.double_click(*at("Arm"))


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
    h.check("Pin is in Arm's menu", wi.right_click(*at("Arm"), "Pin"))


def arm_pinned_first():
    from sciforge import home_core, home_ui, versions

    h.check("a pinned design comes first", names()[:2] == ["Arm", "Base"], names())
    entry = home_core.find(home_ui.load_state(), versions.path_key(s["arm"]))
    h.check("... and is kept pinned", entry is not None and entry["pinned"], entry)
    texts = [t for t, _on in wi.menu_texts(*at("Arm"))]
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
    texts = [t for t, _on in wi.menu_texts(*at("Base"))]
    h.check(
        "its menu: Locate..., Remove from List, no Open",
        "Locate..." in texts and "Remove from List" in texts and "Open" not in texts,
        texts,
    )
    h.shot("missing")


wait_tiles(base_missing)


def double_click_missing():
    wi.double_click(*at("Base"))


def nothing_opened():
    h.check("double-click on a missing design opens nothing", not App.listDocuments())


def remove_base():
    h.check(
        "Remove from List is there",
        wi.right_click(*at("Base"), "Remove from List"),
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
        wi.right_click(*at("Arm"), "Locate..."),
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
    recent = home().row("recent")
    h.check("no tile matches zzz", not names() and not names("local"), names("local"))
    h.check("... and it says so", "zzz" in recent.empty.text() and recent.empty.isVisible())


def search_arm():
    vi.type_into(home().search, "arm")


def arm_found_by_search():
    h.check("search finds Arm", names() == ["Arm"], names())
    vi.type_into(home().search, "")


# -- Path 9 -------------------------------------------------------------------------------
def rows_in_order():
    page = home()
    order = [page.rows_layout.itemAt(i).widget() for i in range(page.rows_layout.count())]
    ids = [w.row_id for w in order if w is not None and hasattr(w, "row_id")]
    h.check("rows top to bottom: Recent, then This computer", ids[:2] == ["recent", "local"], ids)
    local = page.row("local")
    h.check(
        "This computer's row says where designs are saved", local.path_label.text() == s["project"]
    )
    h.check("... and is shown", local.path_label.isVisible())
    h.check("it shows Arm, kept in its folder Robots", names("local") == ["Arm"], names("local"))
    text = [t for _k, _key, _p, t, _st in tiles("local")]
    h.check("... saying so", bool(text) and text[0].split("\n")[1].startswith("in Robots"), text)
    texts = [a.text() for a in page.place_menu("local").actions() if a.text()]
    h.check(
        "its ... menu: Show in Folder, Change Folder...",
        texts == ["Show in Folder", "Change Folder..."],
        texts,
    )
    h.shot("rows")


wait_tiles(rows_in_order)


def save_elsewhere():
    from sciforge import versions_ui

    s["other"] = tempfile.mkdtemp(prefix="sciforge-home-other-")
    doc = App.newDocument("Bracket")
    make_box(doc, 12)
    s["bracket"] = os.path.join(s["other"], "Bracket.FCStd")
    versions_ui._first_save(doc.Name, s["bracket"])  # the Save dialog's save, in another folder


save_elsewhere.wait_ms = 1500


def new_save_starts_in_this_computer():
    from sciforge import versions_ui

    close_all()
    doc = App.newDocument("Gear")
    dialog = versions_ui.SaveDialog(doc)
    h.check(
        "a new design's Save starts in This computer's folder (not the last one used)",
        dialog.location.text() == s["project"],
        (dialog.location.text(), s["project"]),
    )
    dialog.reject()
    dialog.deleteLater()
    close_all()


def elsewhere_shown():
    text = [t for _k, _key, p, t, _st in tiles("local") if p == s["bracket"]]
    h.check(
        "a design saved in another folder shows with This computer", len(text) == 1, names("local")
    )
    h.check("... saying it is another folder", bool(text) and "another folder" in text[0], text)


wait_tiles(elsewhere_shown)


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
    shutil.rmtree(s.get("other", ""), ignore_errors=True)
    if s.get("old_project"):
        App.ParamGet(FILES).SetString("ProjectFolder", s["old_project"])
    else:
        App.ParamGet(FILES).RemString("ProjectFolder")


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
        rows_in_order,
        save_elsewhere,
        new_save_starts_in_this_computer,
        elsewhere_shown,
        leave_recovery_copy,
        banner_shown,
        recover_dialog_open,
        banner_gone,
        option_off,
        close_with_option_off,
        no_home_with_option_off,
    ],
)
