# SPDX-License-Identifier: LGPL-2.1-or-later
"""Deleting a design from Home and from the Data Panel (Luca, 2026-10-23: "In the Home
Screen, clicking on a file should give you the option to delete it. Same in the data
panel"; docs/sciforge/parity/home.md and versions.md "Delete").

A project folder with Arm, Base, Gear (saved, closed), Robots/Bolt and a STEP file.
Path 1, Home, right-click Arm > Delete: the question says where it goes; Move to Trash:
  Arm.FCStd is in the project's trash folder, gone from Recent and from This computer.
Path 2, Home, click Base, then its ... button: the tile's menu; Delete, then Cancel: Base
  stays.
Path 3, Home, click Gear in This computer, then the Delete key: the question; Move to
  Trash: Gear is gone.
Path 4, Base open with a change: Home > Delete says its tab will be closed and the change
  lost; Move to Trash closes it and moves the file.
Path 5, the Data Panel: a click on Bolt (in Robots) shows its details with a Delete
  button; Delete, Move to Trash: Bolt is in the project's trash folder, its card and
  details gone.
Path 6, the Data Panel, right-click the STEP file > Delete: it keeps its .step name in the
  trash folder.
"""

import os
import shutil
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import widget_input as wi

s = {}
FILES = "User parameter:BaseApp/Preferences/Mod/SciForge/Files"
TRASH = ".sciforge-trash"


def home():
    from sciforge import home_ui

    return home_ui.view()


def names(row="recent"):
    page = home()
    return [text.split("\n")[0] for _k, _key, _p, text, _s in page.items(row)] if page else []


def tile(name, row="recent"):
    page = home()
    tiles = page.row(row).list
    for i in range(tiles.count()):
        item = tiles.item(i)
        if item.text().split("\n")[0] == name:
            tiles.scrollToItem(item)
            page.scroll.ensureWidgetVisible(tiles)
            return tiles, item
    return tiles, None


def save_new(name, size, folder=None):
    doc = App.newDocument(name)
    body = doc.addObject("PartDesign::Body", "Body")
    box = doc.addObject("PartDesign::AdditiveBox", "Box")
    body.addObject(box)
    box.Length = box.Width = box.Height = size
    doc.recompute()
    h.fit()
    path = os.path.join(folder or s["project"], name + ".FCStd")
    doc.saveAs(path)
    return doc, path


def close_all():
    for name in list(App.listDocuments()):
        Gui.getDocument(name).Modified = False
        App.closeDocument(name)


def trashed(name):
    return os.path.join(s["project"], TRASH, name)


def answer(yes, seen):
    """A person answering the Delete question once it shows (it is a modal box)."""

    def look():
        box = QtWidgets.QApplication.activeModalWidget()
        if box is None or box.objectName() != "SciForgeDeleteQuestion":
            seen["tries"] = seen.get("tries", 0) + 1
            if seen["tries"] < 80:
                QtCore.QTimer.singleShot(50, look)
            return
        seen["text"] = box.text()
        seen["title"] = box.windowTitle()
        name = "SciForgeDeleteYes" if yes else "SciForgeDeleteCancel"
        button = box.findChild(QtWidgets.QPushButton, name)
        if button is None:
            box.reject()
            return
        wi.click(button)
        seen["answered"] = True

    QtCore.QTimer.singleShot(50, look)


def setup():
    from sciforge import home_core, home_ui

    Gui.activateWorkbench("SciForgeWorkbench")
    s["project"] = tempfile.mkdtemp(prefix="sciforge-delete-")
    s["old_project"] = App.ParamGet(FILES).GetString("ProjectFolder", "")
    App.ParamGet(FILES).SetString("ProjectFolder", s["project"])
    robots = os.path.join(s["project"], "Robots")
    os.makedirs(robots)
    state = home_core.empty()
    state["merged_mru"] = True
    home_ui.save_state(state)
    for name, size in (("Gear", 8), ("Base", 20), ("Arm", 10)):
        _doc, s[name] = save_new(name, size)
    _doc, s["Bolt"] = save_new("Bolt", 4, robots)
    s["step"] = os.path.join(s["project"], "robot.step")
    shutil.copy(
        os.path.join(os.path.dirname(h.__file__), "..", "fixtures", "two_parts.step"), s["step"]
    )
    close_all()
    home_ui.show()
    home().refresh()


setup.wait_ms = 2500


# -- Path 1 -------------------------------------------------------------------------------------
def p1_delete():
    h.check("P1 Arm is in Recent", "Arm" in names(), names())
    tiles, item = tile("Arm")
    if item is None:
        return
    s["p1"] = {}
    answer(True, s["p1"])
    ok = wi.right_click(tiles.viewport(), tiles.visualItemRect(item).center(), "Delete")
    h.check("P1 right-click Arm > Delete", ok)


p1_delete.wait_ms = 2000


def p1_gone():
    seen = s["p1"]
    h.check("P1 the question was asked", seen.get("answered"), seen)
    h.check(
        "P1 it says where it goes",
        "trash folder" in seen.get("text", "") and TRASH in seen.get("text", ""),
        seen.get("text"),
    )
    h.check("P1 Arm.FCStd left the project", not os.path.exists(s["Arm"]))
    h.check("P1 it is in the trash folder", os.path.isfile(trashed("Arm.FCStd")))
    h.check("P1 gone from Recent", "Arm" not in names(), names())
    h.check("P1 and from This computer", "Arm" not in names("local"), names("local"))


# -- Path 2 -------------------------------------------------------------------------------------
def p2_more():
    tiles, item = tile("Base")
    if not h.check("P2 Base in Recent", item is not None, names()):
        return
    wi.click(tiles.viewport(), tiles.visualItemRect(item).center())
    h.check("P2 Base is the clicked tile", tiles.currentItem() is item and item.isSelected())
    h.shot("P2-clicked-tile")
    s["p2"] = {}
    s["p2_menu"] = {"ok": False}
    answer(False, s["p2"])
    QtCore.QTimer.singleShot(50, wi._picker(s["p2_menu"], "Delete"))
    wi.click(tiles.viewport(), tiles.more_point(item))


p2_more.wait_ms = 2000


def p2_kept():
    h.check("P2 the ... button opened the menu with Delete", s["p2_menu"]["ok"], s["p2_menu"])
    h.check("P2 the question was asked", s["p2"].get("answered"), s["p2"])
    h.check("P2 Cancel keeps Base", os.path.isfile(s["Base"]) and "Base" in names(), names())


# -- Path 3 -------------------------------------------------------------------------------------
def p3_key():
    tiles, item = tile("Gear", "local")
    if not h.check("P3 Gear in This computer", item is not None, names("local")):
        return
    wi.click(tiles.viewport(), tiles.visualItemRect(item).center())
    s["p3"] = {}
    answer(True, s["p3"])
    wi.key(tiles, QtCore.Qt.Key_Delete)


p3_key.wait_ms = 2000


def p3_gone():
    h.check("P3 the Delete key asked", s["p3"].get("answered"), s["p3"])
    h.check("P3 Gear is in the trash folder", os.path.isfile(trashed("Gear.FCStd")))
    h.check("P3 gone from This computer", "Gear" not in names("local"), names("local"))


# -- Path 4 -------------------------------------------------------------------------------------
def p4_open():
    from sciforge import home_ui, versions_ui

    doc = versions_ui.open_design(s["Base"])
    s["base_doc"] = doc.Name if doc else None
    body = doc.getObject("Body") if doc else None
    if body is not None:
        body.Group[-1].Height = 25
        doc.recompute()
        Gui.getDocument(doc.Name).Modified = True
    home_ui.show()


p4_open.wait_ms = 1500


def p4_delete():
    tiles, item = tile("Base")
    if not h.check("P4 Base in Recent", item is not None, names()):
        return
    s["p4"] = {}
    answer(True, s["p4"])
    wi.right_click(tiles.viewport(), tiles.visualItemRect(item).center(), "Delete")


p4_delete.wait_ms = 2000


def p4_closed():
    text = s["p4"].get("text", "")
    h.check(
        "P4 the question says the tab closes and the change is lost",
        "It is open" in text and "unsaved changes are lost" in text,
        text,
    )
    h.check("P4 Base was closed", s["base_doc"] not in App.listDocuments(), App.listDocuments())
    h.check("P4 its file is in the trash folder", os.path.isfile(trashed("Base.FCStd")))
    h.check("P4 no other question popped up", not h.popups(), h.popups())


# -- Path 5 -------------------------------------------------------------------------------------
def panel():
    from sciforge import versions_ui

    return versions_ui.panel()


def card(text_start):
    lst = panel().list
    for i in range(lst.count()):
        if lst.item(i).text().startswith(text_start):
            return lst.item(i)
    return None


def p5_details():
    from sciforge import versions_ui

    versions_ui.show_panel()
    panel().set_folder(os.path.join(s["project"], "Robots"))
    item = card("Bolt")
    if not h.check("P5 the Bolt card", item is not None, panel().items()):
        return
    lst = panel().list
    wi.click(lst.viewport(), lst.visualItemRect(item).center())


p5_details.wait_ms = 1000


def p5_delete():
    details = panel().details
    h.check("P5 a click on Bolt shows its details", details.isVisible() and details.path)
    button = details.delete_button
    h.check("P5 with a Delete button", button.isVisible() and button.text() == "Delete")
    h.shot("P5-details-delete")
    s["p5"] = {}
    answer(True, s["p5"])
    wi.click(button)


p5_delete.wait_ms = 2000


def p5_gone():
    h.check("P5 the question was asked", s["p5"].get("answered"), s["p5"])
    h.check("P5 Bolt is in the project's trash folder", os.path.isfile(trashed("Bolt.FCStd")))
    h.check("P5 not in Robots any more", not os.path.exists(s["Bolt"]))
    h.check("P5 its card is gone", card("Bolt") is None, panel().items())
    h.check("P5 and its details", not panel().details.isVisible())


# -- Path 6 -------------------------------------------------------------------------------------
def p6_step():
    panel().set_folder(s["project"])
    item = card("robot.step")
    if not h.check("P6 the STEP card", item is not None, panel().items()):
        return
    lst = panel().list
    s["p6"] = {}
    answer(True, s["p6"])
    ok = wi.right_click(lst.viewport(), lst.visualItemRect(item).center(), "Delete")
    h.check("P6 right-click > Delete", ok)


p6_step.wait_ms = 2000


def p6_gone():
    h.check("P6 the question named the file", "robot.step" in s["p6"].get("title", ""), s["p6"])
    h.check("P6 it keeps its .step name in the trash", os.path.isfile(trashed("robot.step")))
    h.check("P6 its card is gone", card("robot.step") is None, panel().items())


def cleanup():
    from sciforge import versions_ui

    versions_ui.hide_panel()
    close_all()
    App.ParamGet(FILES).SetString("ProjectFolder", s.get("old_project", ""))
    if not s.get("old_project"):
        App.ParamGet(FILES).RemString("ProjectFolder")
    shutil.rmtree(s["project"], ignore_errors=True)


h.run(
    "delete_designs",
    [
        setup,
        p1_delete,
        p1_gone,
        p2_more,
        p2_kept,
        p3_key,
        p3_gone,
        p4_open,
        p4_delete,
        p4_closed,
        p5_details,
        p5_delete,
        p5_gone,
        p6_step,
        p6_gone,
        cleanup,
    ],
)
