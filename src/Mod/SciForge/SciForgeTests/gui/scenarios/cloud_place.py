# SPDX-License-Identifier: LGPL-2.1-or-later
"""Places: a cloud folder connected and used (docs/sciforge/parity/cloud.md, brief
home-cloud-ai.md M2), with real clicks.

A temporary folder poses as a Dropbox folder: the wizard finds it through a Dropbox
info.json (read by the same rules as on a real computer: locations_core.dropbox_folders).
This computer's name is LAPTOP.

Path 1, Home > + Connect a cloud or NAS: the wizard offers the Dropbox folder found, with a
  SciForge folder inside; Connect: Dropbox is a place on Home (the folder made).
Path 2, a design saved there through the Save dialog's Place row: versions kept as copies
  (Bracket.versions/), never git; its picture beside it (.sciforge/thumbs/) and this
  computer's note while it is open (.sciforge/locks/).
Path 3, the file changed behind SciForge's back (another computer): Ctrl+S asks; Keep both
  saves mine as "Bracket (LAPTOP)" and leaves theirs untouched.
Path 4, Dropbox's "conflicted copy" shows a Conflict tile; its menu has Compare and Keep
  This One; Compare opens the comparison.
Path 5, a design open on another computer (its note): opening it asks; Open read-only:
  Ctrl+S then saves nothing.
Path 6, the cloud folder gone (app not running): the place says Offline, its page says so.
Path 7, Disconnect: the place leaves Home, the folder and designs stay.
"""

import json
import os
import shutil
import tempfile
import time

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import versions_input as vi
from SciForgeTests.gui import widget_input as wi

s = {}
FILES = "User parameter:BaseApp/Preferences/Mod/SciForge/Files"


def home():
    from sciforge import home_ui

    return home_ui.view()


def place_rows():
    page = home()
    return [page.places.item(i).text() for i in range(page.places.count())] if page else []


def click_place(text_start):
    page = home()
    for i in range(page.places.count()):
        item = page.places.item(i)
        if item.text().startswith(text_start):
            wi.click(page.places.viewport(), page.places.visualItemRect(item).center())
            return True
    return False


def names():
    page = home()
    return [t.split("\n")[0] for _k, _key, _p, t, _s in page.items()] if page else []


def tile_pos(name):
    page = home()
    for i in range(page.list.count()):
        item = page.list.item(i)
        if item.text().split("\n")[0] == name:
            return page.list.visualItemRect(item).center()
    return None


def dialog(name):
    return vi.dialog(name)


def make_box(doc, size):
    body = doc.addObject("PartDesign::Body", "Body")
    box = doc.addObject("PartDesign::AdditiveBox", "Box")
    body.addObject(box)
    box.Length = box.Width = box.Height = size
    doc.recompute()
    return body


def ctrl_s():
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


def close_all():
    for name in list(App.listDocuments()):
        Gui.getDocument(name).Modified = False
        App.closeDocument(name)


# -- setup ------------------------------------------------------------------------------------
def setup():
    from sciforge import home_core, home_ui, locations_core, locations_ui

    s["tmp"] = tempfile.mkdtemp(prefix="sciforge-cloud-")
    s["dropbox"] = os.path.join(s["tmp"], "Dropbox")
    os.makedirs(s["dropbox"])
    info = os.path.join(s["tmp"], "info.json")
    with open(info, "w", encoding="utf-8") as handle:
        json.dump({"personal": {"path": s["dropbox"], "host": 1}}, handle)

    def detect():  # the real rules, on this made-up computer
        with open(info, encoding="utf-8") as handle:
            text = handle.read()
        return locations_core.detect(dropbox=locations_core.dropbox_folders([text]))

    locations_ui.DETECT = detect
    locations_ui.COMPUTER = "LAPTOP"
    s["old_project"] = App.ParamGet(FILES).GetString("ProjectFolder", "")
    s["old_ask"] = App.ParamGet(FILES).GetBool("AskDescription", True)
    s["project"] = os.path.join(s["tmp"], "Project")
    os.makedirs(s["project"])
    App.ParamGet(FILES).SetString("ProjectFolder", s["project"])
    App.ParamGet(FILES).SetBool("AskDescription", False)  # (given back at the end)
    state = home_core.empty()
    state["merged_mru"] = True
    home_ui.save_state(state)
    home_ui.show()
    home().refresh()


# -- Path 1 -----------------------------------------------------------------------------------
def click_connect():
    h.check(
        "Home offers + Connect a cloud or NAS",
        any(r.startswith("+ Connect") for r in place_rows()),
        place_rows(),
    )
    click_place("+ Connect")


def wizard_found_dropbox():
    d = dialog("SciForgeConnectDialog")
    h.check("the Connect wizard opened", d is not None)
    if d is None:
        return
    kind = vi.child(d, "SciForgeConnectKind")
    folder = vi.child(d, "SciForgeConnectFolder")
    note = vi.child(d, "SciForgeConnectNote")
    s["root"] = os.path.join(s["dropbox"], "SciForge")
    h.check("it chose Dropbox (found)", kind.currentData() == "dropbox", kind.currentText())
    h.check(
        "... with a SciForge folder in it",
        os.path.normpath(folder.text()) == s["root"],
        folder.text(),
    )
    h.check("... and says it was found", "Found Dropbox" in note.text(), note.text())
    h.check("no git choice for a cloud", not vi.child(d, "SciForgeConnectGit").isVisible())
    h.shot("wizard")
    wi.click(vi.child(d, "SciForgeConnectOK"))


def dropbox_connected():
    from sciforge import locations_ui

    h.check("the wizard closed", dialog("SciForgeConnectDialog") is None)
    h.check("Dropbox is a place on Home", "Dropbox" in place_rows(), place_rows())
    h.check("This computer is never shown offline", "This computer" in place_rows(), place_rows())
    h.check("its SciForge folder was made", os.path.isdir(s["root"]))
    kept = locations_ui.kept()
    h.check("it is kept (locations.json)", [p["kind"] for p in kept] == ["dropbox"], kept)
    click_place("Dropbox")


def dropbox_page():
    page = home()
    h.check("the Dropbox page is shown", page.mode == "dropbox", page.mode)
    h.check("... empty for now", page.empty.isVisible() and "No designs" in page.empty.text())


# -- Path 2 -----------------------------------------------------------------------------------
def new_design():
    wi.click(home().new_button)


def model_and_save():
    doc = App.ActiveDocument
    make_box(doc, 10)
    h.fit()
    s["doc"] = doc.Name
    ctrl_s()


model_and_save.wait_ms = 1500


def save_in_dropbox():
    d = vi.save_dialog()
    h.check("the Save dialog opened", d is not None)
    if d is None:
        return
    place = vi.child(d, "SciForgeSavePlace")
    items = [place.itemText(i) for i in range(place.count())]
    h.check(
        "its Place row lists This computer and Dropbox",
        items == ["This computer", "Dropbox"],
        items,
    )
    place.setFocus()
    QtTest.QTest.keyClick(place, QtCore.Qt.Key_Down)  # (the keyboard picks the next place)
    location = vi.child(d, "SciForgeSaveLocation")
    h.check(
        "picking Dropbox puts its folder in Location",
        os.path.normpath(location.text()) == s["root"],
        location.text(),
    )
    vi.fill_save_dialog(name="Bracket")
    vi.click_save()


save_in_dropbox.wait_ms = 2000


def saved_in_dropbox():
    from sciforge import locations_core

    s["file"] = os.path.join(s["root"], "Bracket.FCStd")
    h.check("Bracket was saved in the Dropbox folder", os.path.isfile(s["file"]))
    h.check(
        "its versions are copies beside it",
        os.path.isfile(os.path.join(s["root"], "Bracket.versions", "index.json")),
        os.listdir(s["root"]),
    )
    h.check("no git in a cloud folder", not os.path.exists(os.path.join(s["root"], ".git")))
    sidecar = locations_core.sidecar_file(s["root"], s["file"])
    h.check("its picture is beside it for the other computers", os.path.isfile(sidecar), sidecar)
    note = locations_core.note_file(s["root"], s["file"])
    ok = os.path.isfile(note)
    h.check("this computer's note while it is open", ok, note)
    if ok:
        with open(note, encoding="utf-8") as handle:
            h.check("... signed LAPTOP", json.load(handle)["computer"] == "LAPTOP")


# -- Path 3 -----------------------------------------------------------------------------------
def changed_elsewhere():
    """Another computer saved Bracket (its box is 20 mm): the sync app brought it here."""
    other = App.newDocument("Other")
    make_box(other, 20)
    temp = os.path.join(s["tmp"], "theirs.FCStd")
    other.saveAs(temp)
    App.closeDocument(other.Name)
    time.sleep(1.1)  # (a newer file date, as a sync app gives it)
    shutil.copy(temp, s["file"])
    with open(s["file"], "rb") as handle:
        s["theirs"] = handle.read()
    doc = App.getDocument(s["doc"])
    area = Gui.getMainWindow().findChild(QtWidgets.QMdiArea)
    for sub in area.subWindowList():  # Bracket's tab in front again
        if sub.windowTitle().replace("[*]", "").startswith(doc.Label):
            area.setActiveSubWindow(sub)
    doc.getObject("Box").Length = 12  # my change
    doc.recompute()
    ctrl_s()


changed_elsewhere.wait_ms = 1500


def asks_keep_both():
    d = dialog("SciForgeChangedDialog")
    h.check("saving asks: changed on another computer", d is not None)
    if d is None:
        return
    keep = vi.child(d, "SciForgeChanged_keep_both")
    h.check("Keep both is the default", keep is not None and keep.isDefault())
    h.shot("changed")
    wi.click(keep)


asks_keep_both.wait_ms = 1500


def both_kept():
    mine = os.path.join(s["root"], "Bracket (LAPTOP).FCStd")
    h.check("mine was saved beside theirs", os.path.isfile(mine), os.listdir(s["root"]))
    with open(s["file"], "rb") as handle:
        h.check("theirs was not touched", handle.read() == s["theirs"])
    doc = App.getDocument(s["doc"])
    h.check(
        "the open design is now mine",
        doc.FileName and os.path.samefile(doc.FileName, mine),
        doc.FileName,
    )
    close_all()


# -- Path 4 -----------------------------------------------------------------------------------
def conflicted_copy():
    s["copy"] = os.path.join(s["root"], "Bracket (Luca's conflicted copy 2026-10-19).FCStd")
    shutil.copy(s["file"], s["copy"])
    from sciforge import home_ui

    home_ui.show()
    click_place("Dropbox")


def conflict_tile():
    page = home()
    found = [(p, t) for _k, _key, p, t, _s in page.items() if p == s["copy"]]
    text = found[0][1] if found else ""
    h.check(
        "the conflicted copy has a Conflict tile", text == "Bracket\nConflict copy, Luca's", text
    )
    pos = page.list.visualItemRect(page.item_for(s["copy"])).center() if found else None
    texts = [t for t, _on in wi.menu_texts(page.list.viewport(), pos)]
    h.check(
        "its menu: Compare with Bracket, Keep This One",
        "Compare with Bracket" in texts and "Keep This One" in texts,
        texts,
    )
    h.shot("conflict")
    h.check("Compare is there", wi.right_click(page.list.viewport(), pos, "Compare with Bracket"))


conflict_tile.wait_ms = 2000


def compare_open():
    d = vi.compare_dialog()
    h.check("Compare opened the comparison", d is not None)
    if d is not None:
        rows = d.rows
        h.check("... with rows", bool(rows), rows)
        vi.cancel_dialog(d)


# -- Path 5 -----------------------------------------------------------------------------------
def note_from_desktop():
    from sciforge import locations_core

    note = locations_core.note_file(s["root"], s["copy"])
    os.makedirs(os.path.dirname(note), exist_ok=True)
    with open(note, "w", encoding="utf-8") as handle:
        json.dump(locations_core.make_note("DESKTOP-AB12C", "luca", time.time() - 600), handle)
    page = home()
    wi.double_click(
        page.list.viewport(), page.list.visualItemRect(page.item_for(s["copy"])).center()
    )


note_from_desktop.wait_ms = 2000


def asks_open_elsewhere():
    d = dialog("SciForgeOpenElsewhereDialog")
    h.check("opening asks: open on DESKTOP-AB12C", d is not None)
    if d is None:
        return
    label = [w.text() for w in d.findChildren(QtWidgets.QLabel)]
    h.check("... naming the other computer", any("DESKTOP-AB12C" in t for t in label), label)
    wi.click(vi.child(d, "SciForgeOpenReadOnly"))


def read_only_save():
    from sciforge import locations_ui

    docs = [d for d in App.listDocuments().values() if d.FileName.endswith("2026-10-19).FCStd")]
    h.check("the design is open", len(docs) == 1)
    if not docs:
        return
    s["ro"] = docs[0].Name
    h.check("... read-only", s["ro"] in locations_ui._read_only)
    with open(s["copy"], "rb") as handle:
        s["copy_bytes"] = handle.read()
    docs[0].getObject("Box").Length = 30
    docs[0].recompute()
    ctrl_s()


read_only_save.wait_ms = 1500


def nothing_saved():
    with open(s["copy"], "rb") as handle:
        h.check("Ctrl+S on a read-only design saved nothing", handle.read() == s["copy_bytes"])
    h.check("no Save dialog either", vi.save_dialog() is None and vi.version_dialog() is None)
    close_all()


# -- Path 6 -----------------------------------------------------------------------------------
def dropbox_offline():
    from sciforge import home_ui

    s["away"] = s["dropbox"] + "-away"
    os.rename(s["dropbox"], s["away"])
    home_ui.show()
    home_ui.places_changed()


def offline_shown():
    rows = place_rows()
    h.check(
        "the place says Offline",
        any(r.startswith("Dropbox") and "Offline" in r for r in rows),
        rows,
    )
    click_place("Dropbox")


def offline_page():
    page = home()
    h.check("its page says it is offline", "offline" in page.empty.text(), page.empty.text())
    from sciforge import home_ui

    os.rename(s["away"], s["dropbox"])
    home_ui.places_changed()


# -- Path 7 -----------------------------------------------------------------------------------
def disconnect():
    page = home()
    for i in range(page.places.count()):
        item = page.places.item(i)
        if item.text() == "Dropbox":
            pos = page.places.visualItemRect(item).center()
            h.check(
                "Disconnect is in its menu",
                wi.right_click(page.places.viewport(), pos, "Disconnect"),
            )
            return
    h.check("Dropbox is listed before Disconnect", False, place_rows())


def disconnected():
    from sciforge import locations_ui

    h.check("Dropbox left Home", "Dropbox" not in place_rows(), place_rows())
    h.check("it is not kept any more", locations_ui.kept() == [])
    h.check("the folder and designs stay", os.path.isfile(s["file"]))
    h.check("no pop-up left", not h.popups(), h.popups())
    locations_ui.DETECT = None
    locations_ui.COMPUTER = None
    if s.get("old_project"):
        App.ParamGet(FILES).SetString("ProjectFolder", s["old_project"])
    else:
        App.ParamGet(FILES).RemString("ProjectFolder")
    App.ParamGet(FILES).SetBool("AskDescription", s["old_ask"])
    App.newDocument("Scratch")  # (the harness ends on a design)


h.run(
    "cloud_place",
    [
        setup,
        click_connect,
        wizard_found_dropbox,
        dropbox_connected,
        dropbox_page,
        new_design,
        model_and_save,
        save_in_dropbox,
        saved_in_dropbox,
        changed_elsewhere,
        asks_keep_both,
        both_kept,
        conflicted_copy,
        conflict_tile,
        compare_open,
        note_from_desktop,
        asks_open_elsewhere,
        read_only_save,
        nothing_saved,
        dropbox_offline,
        offline_shown,
        offline_page,
        disconnect,
        disconnected,
    ],
)
