# SPDX-License-Identifier: LGPL-2.1-or-later
"""Save makes versions, like Fusion (docs/sciforge/parity/versions.md).

A box 10 x 20 x 5 in a new design; the project folder is a fresh temporary folder (git is
installed here, so versions are commits in it).
Path 1, the first save: Ctrl+S opens the Save dialog with Name and Location (the project
  folder); type "Bracket", Save: Bracket.FCStd is in the project folder, v1, the design
  shows as saved, no FreeCAD pop-up.
Path 2, the second save: the box grows; Ctrl+S opens the Version Description box; type
  "taller box", Enter: the file is written again, v2 with that description.
Path 3, the history: Version History lists v2 (current) and v1, newest first, with date,
  description and size.
Path 4, open a version: select v1, Open: a second tab "Bracket v1" with the old box
  (volume 1000); Ctrl+S there is blocked (Fusion: an older version cannot be saved; Save
  As Latest or Save As a new design), Esc leaves everything as it was.
Path 5, promote: select v1, Promote: the Save As Latest dialog, Enter: the design is v1's
  box again, recorded as v3 ("Promoted v1"), v2 stays in the list, the read-only tab is
  closed, the design tab reloaded.
Path 6, compare: select v2, Compare: the rows, with the volume and the date differing.
Path 7, git underneath: the project folder is a repository with 3 commits of the file.
Path 8, Save As: a copy "Bracket copy" in a new folder is v1 there, the original keeps v3.
"""

import os
import shutil
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import versions_input as vi

s = {}
PREFS = "User parameter:BaseApp/Preferences/Mod/SciForge/Files"


def doc():
    return App.ActiveDocument


def make_box(document, name, length, width, height):
    body = document.addObject("PartDesign::Body", name)
    box = document.addObject("PartDesign::AdditiveBox", name + "Box")
    body.addObject(box)
    box.Length, box.Width, box.Height = length, width, height
    document.recompute()
    Gui.getDocument(document.Name).ActiveView.setActiveObject("pdbody", body)
    return body


def volume(document=None):
    document = document or doc()
    total = 0.0
    for obj in document.Objects:
        if obj.TypeId == "PartDesign::Body" and not obj.Shape.isNull():
            total += obj.Shape.Volume
    return total


def near(a, b, tol=1e-3):
    return abs(a - b) < tol


# -- setup ----
def setup():
    from sciforge import versions

    Gui.activateWorkbench("SciForgeWorkbench")
    s["project"] = tempfile.mkdtemp(prefix="sciforge-project-")
    App.ParamGet(PREFS).SetString("ProjectFolder", s["project"])
    App.ParamGet(PREFS).SetBool("UseGit", True)
    App.ParamGet(PREFS).SetBool("AskDescription", True)
    s["git"] = versions.git_available()
    document = App.newDocument("Design")
    s["box"] = make_box(document, "Body", 10, 20, 5)
    h.fit()
    h.check("a box of 1000 in a new, unsaved design", near(volume(), 1000.0) and not doc().FileName)


# -- Path 1: the first save ----
def p1_ctrl_s():
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


def p1_dialog():
    d = vi.save_dialog()
    h.check("P1 Ctrl+S opens the Save dialog (Name, Location)", d is not None, h.popups())
    if d is None:
        return
    location = vi.child(d, "SciForgeSaveLocation").text()
    h.check(
        "P1 the Location is the project folder",
        os.path.normcase(location) == os.path.normcase(s["project"]),
        location,
    )
    h.check("P1 the Name is filled in", bool(vi.child(d, "SciForgeSaveName").text()))
    vi.fill_save_dialog(name="Bracket")
    h.shot("1-save-dialog")
    vi.click_save()


def p1_saved():
    path = os.path.join(s["project"], "Bracket.FCStd")
    s["path"] = path
    h.check(
        "P1 Bracket.FCStd is in the project folder", os.path.isfile(path), os.listdir(s["project"])
    )
    h.check(
        "P1 the design knows its file", os.path.normcase(doc().FileName) == os.path.normcase(path)
    )
    h.check("P1 the design shows as saved", not Gui.ActiveDocument.Modified)
    h.check("P1 no FreeCAD pop-up", not h.popups(), h.popups())
    from sciforge import versions, versions_ui

    store = versions_ui.store_of(path)
    listed = store.versions()
    h.check("P1 one version, v1", [v.number for v in listed] == [1], listed)
    h.check(
        "P1 git is used inside the project folder" if s["git"] else "P1 copies are used (no git)",
        store.backend == ("git" if s["git"] else "copy"),
        store.backend,
    )
    h.check("P1 the file holds a box of 1000", versions.summary(path)["bodies"] == 1)


# -- Path 2: the second save with a description ----
def p2_change():
    s["box"].Group[0].Height = 10
    doc().recompute()
    h.check("P2 the box grew to 2000", near(volume(), 2000.0), volume())
    h.check("P2 the design shows as changed", Gui.ActiveDocument.Modified)
    s["mtime"] = os.path.getmtime(s["path"])
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


def p2_describe():
    d = vi.version_dialog()
    h.check("P2 Ctrl+S on a saved design asks for a Version Description", d is not None, h.popups())
    h.check("P2 not the Name/Location dialog again", vi.save_dialog() is None)
    h.shot("2-version-dialog")
    vi.describe_and_save("taller box")


def p2_saved():
    h.check("P2 the dialog closed", vi.version_dialog() is None)
    h.check("P2 the file was written again", os.path.getmtime(s["path"]) >= s["mtime"])
    h.check("P2 the design shows as saved", not Gui.ActiveDocument.Modified)
    from sciforge import versions_ui

    listed = versions_ui.store_of(s["path"]).versions()
    h.check("P2 two versions", [v.number for v in listed] == [1, 2], listed)
    h.check(
        "P2 v2 carries the description",
        len(listed) == 2 and listed[1].description == "taller box" and listed[1].current,
        listed,
    )
    h.check("P2 v1 has no description", len(listed) == 2 and listed[0].description == "")


# -- Path 3: the history ----
def p3_open_history():
    Gui.runCommand("SciForge_VersionHistory")


def p3_rows():
    rows = vi.history_rows()
    h.check("P3 the Version History dialog is open", vi.history_dialog() is not None)
    h.check("P3 two rows, newest first", [r[0].split()[0] for r in rows] == ["v2", "v1"], rows)
    h.check("P3 v2 is marked current", rows and "current" in rows[0][0], rows)
    h.check("P3 the description column", rows and rows[0][2] == "taller box" and rows[1][2] == "")
    h.check("P3 dates and sizes", all(r[1] and r[3] for r in rows), rows)
    h.shot("3-history")


# -- Path 4: open an older version read-only ----
def p4_open_v1():
    h.check("P4 v1 selected", vi.history_select("v1"))
    h.check("P4 Open clicked", vi.history_button("Open"))


def p4_opened():
    from sciforge import versions_ui

    opened = App.ActiveDocument
    s["v1_doc"] = opened.Name
    h.check("P4 a new tab with v1", opened.Label == "Bracket v1", opened.Label)
    h.check("P4 it holds the old box (1000)", near(volume(opened), 1000.0), volume(opened))
    h.check("P4 known as an older version", versions_ui.version_of(opened) == (s["path"], 1))
    h.check(
        "P4 the design tab is still there", len(App.listDocuments()) == 2, list(App.listDocuments())
    )
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


def p4_blocked():
    d = vi.older_dialog()
    h.check(
        "P4 Save on an older version is blocked (Save As Latest / Save As offered)", d is not None
    )
    h.shot("4-older-version")
    vi.cancel_dialog(d)


def p4_unchanged():
    from sciforge import versions_ui

    h.check(
        "P4 Esc: nothing saved",
        [v.number for v in versions_ui.store_of(s["path"]).versions()] == [1, 2],
    )
    h.check(
        "P4 no pop-up left (but the history)",
        not vi.popups_except({"SciForgeHistoryDialog"}),
        h.popups(),
    )


# -- Path 5: promote v1 ----
def p5_promote():
    d = vi.history_dialog()
    h.check("P5 the history dialog is still open", d is not None)
    h.check("P5 v1 selected", vi.history_select("v1"))
    h.check("P5 Promote clicked", vi.history_button("Promote"))


def p5_describe():
    d = vi.version_dialog()
    h.check("P5 the Save As Latest dialog asks for a description", d is not None, h.popups())
    if d is not None:
        text = vi.child(d, "SciForgeVersionDescription").text()
        h.check("P5 it suggests 'Promoted v1'", text == "Promoted v1", text)
    h.shot("5-promote")
    vi.accept_save()


p5_describe.wait_ms = 2500


def p5_promoted():
    from sciforge import versions_ui

    listed = versions_ui.store_of(s["path"]).versions()
    h.check("P5 three versions now", [v.number for v in listed] == [1, 2, 3], listed)
    h.check(
        "P5 v3 says Promoted v1",
        len(listed) == 3 and listed[2].description == "Promoted v1",
        listed,
    )
    h.check(
        "P5 v2 is still in the list", len(listed) == 3 and listed[1].description == "taller box"
    )
    h.check(
        "P5 the read-only tab was closed",
        s["v1_doc"] not in App.listDocuments(),
        list(App.listDocuments()),
    )
    current = versions_ui.doc_for_file(s["path"])
    h.check("P5 the design tab was reloaded", current is not None and current is App.ActiveDocument)
    h.check("P5 and holds v1's box (1000)", current is not None and near(volume(current), 1000.0))
    h.check(
        "P5 it shows as saved", current is not None and not Gui.getDocument(current.Name).Modified
    )
    rows = vi.history_rows()
    h.check(
        "P5 the history dialog shows v3 current",
        rows and rows[0][0].startswith("v3") and "current" in rows[0][0],
        rows,
    )
    h.check("P5 no pop-up left", not vi.popups_except({"SciForgeHistoryDialog"}), h.popups())


# -- Path 6: compare ----
def p6_compare():
    h.check("P6 v2 selected", vi.history_select("v2"))
    h.check("P6 Compare clicked", vi.history_button("Compare"))


p6_compare.wait_ms = 2500


def p6_rows():
    d = vi.compare_dialog()
    h.check("P6 the Compare dialog opened", d is not None, h.popups())
    table = vi.child(d, "SciForgeCompareTable")
    rows = {}
    if table is not None:
        for r in range(table.rowCount()):
            rows[table.item(r, 0).text()] = (table.item(r, 1).text(), table.item(r, 2).text())
    h.check(
        "P6 compares v2 with v3",
        d is not None and d.windowTitle() == "Compare v2 and v3",
        d and d.windowTitle(),
    )
    h.check("P6 bodies the same (1 and 1)", rows.get("Bodies") == ("1", "1"), rows)
    vol = rows.get("Total volume (mm^3)")
    h.check("P6 the volume differs (2000 vs 1000)", vol == ("2000.00", "1000.00"), vol)
    h.shot("6-compare")
    vi.cancel_dialog(d)
    vi.cancel_dialog(vi.history_dialog())


# -- Path 7: git underneath ----
def p7_git():
    from sciforge import versions

    if not s["git"]:
        h.check(
            "P7 (no git here: versions are copies)",
            os.path.isdir(os.path.join(s["project"], "Bracket.versions")),
        )
        return
    h.check(
        "P7 the project folder is a git repository",
        os.path.isdir(os.path.join(s["project"], ".git")),
    )
    store = versions.GitStore(s["path"], s["project"])
    h.check("P7 three commits of Bracket.FCStd", store.count() == 3, store.count())
    h.check(
        "P7 a .gitignore for FreeCAD's backup files",
        os.path.isfile(os.path.join(s["project"], ".gitignore")),
    )
    h.check(
        "P7 no .versions folder beside the design",
        not os.path.isdir(os.path.join(s["project"], "Bracket.versions")),
    )


# -- Path 8: Save As ----
def p8_save_as():
    Gui.runCommand("SciForge_SaveAs")


def p8_dialog():
    d = vi.save_dialog()
    h.check(
        "P8 Save As opens the Name/Location dialog", d is not None and d.windowTitle() == "Save As"
    )
    if d is None:
        return
    name = vi.child(d, "SciForgeSaveName").text()
    h.check("P8 a free name is suggested", name == "Bracket copy", name)
    s["folders_before"] = set(os.listdir(s["project"]))
    vi.child(d, "SciForgeSaveNewFolder").click()


def p8_new_folder():
    d = vi.save_dialog()
    made = set(os.listdir(s["project"])) - s["folders_before"]
    h.check("P8 New Folder made a folder in the project", made == {"New Folder"}, made)
    location = vi.child(d, "SciForgeSaveLocation").text() if d else ""
    h.check("P8 and chose it as the Location", location.endswith("New Folder"), location)
    vi.click_save()


def p8_saved():
    from sciforge import versions_ui

    copy = os.path.join(s["project"], "New Folder", "Bracket copy.FCStd")
    h.check("P8 the copy was saved there", os.path.isfile(copy))
    h.check(
        "P8 the open design is now the copy",
        os.path.normcase(doc().FileName) == os.path.normcase(copy),
    )
    h.check(
        "P8 the copy starts at v1", [v.number for v in versions_ui.store_of(copy).versions()] == [1]
    )
    h.check(
        "P8 the original keeps its 3 versions",
        [v.number for v in versions_ui.store_of(s["path"]).versions()] == [1, 2, 3],
    )
    h.check("P8 no pop-up", not h.popups(), h.popups())
    h.shot("8-save-as")


def cleanup():
    for name in list(App.listDocuments()):
        Gui.getDocument(name).Modified = False
        App.closeDocument(name)
    App.ParamGet(PREFS).RemString("ProjectFolder")
    shutil.rmtree(s["project"], ignore_errors=True)


h.run(
    "versions_save",
    [
        setup,
        p1_ctrl_s,
        p1_dialog,
        p1_saved,
        p2_change,
        p2_describe,
        p2_saved,
        p3_open_history,
        p3_rows,
        p4_open_v1,
        p4_opened,
        p4_blocked,
        p4_unchanged,
        p5_promote,
        p5_describe,
        p5_promoted,
        p6_compare,
        p6_rows,
        p7_git,
        p8_save_as,
        p8_dialog,
        p8_new_folder,
        p8_saved,
        cleanup,
    ],
)
