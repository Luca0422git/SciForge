# SPDX-License-Identifier: LGPL-2.1-or-later
"""Recovery copies and crash recovery, like Fusion (docs/sciforge/parity/versions.md).

The recovery interval is set to 2 seconds for the test (Fusion: minutes).
Path 1, autosave: a changed, never-saved design gets a recovery copy with a sidecar that
  names it; a design that did not change gets none.
Path 2, a clean save removes the copy; a change after it brings a new copy, keyed by the
  file; Ctrl+Shift+S writes the copies at once.
Path 3, crash recovery: the copy is made to look like another session's (a crash), the
  start-up check runs again: "Recover unsaved work?" lists the design; Recover opens it
  under its own file name, shown as changed; Ctrl+S suggests "Recovered after a crash",
  Enter saves it into the file as the next version and the copy is gone.
Path 4, nothing to recover: the check finds nothing and says so; Delete in the dialog
  throws a copy away; a closed design's copy goes too.
Path 5, Fusion's rule: no recovery copy while a command runs (a dialog is open).
"""

import json
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
    return sum(o.Shape.Volume for o in document.Objects if o.TypeId == "PartDesign::Body")


def near(a, b, tol=1e-3):
    return a is not None and abs(a - b) < tol


def recovery():
    from sciforge import versions_ui

    return versions_ui.recovery()


def copies():
    from sciforge import versions

    return versions.list_recovery(recovery().folder)


def setup():
    Gui.activateWorkbench("SciForgeWorkbench")
    s["project"] = tempfile.mkdtemp(prefix="sciforge-project-")
    App.ParamGet(PREFS).SetString("ProjectFolder", s["project"])
    App.ParamGet(PREFS).SetInt("AutosaveTestSeconds", 2)
    App.ParamGet(PREFS).SetBool("AskDescription", True)
    rec = recovery()
    h.check("recovery copies are on while SciForge is on", rec is not None and rec.timer.isActive())
    rec.restart()
    h.check(
        "the interval is 2 seconds for the test", rec.timer.interval() == 2000, rec.timer.interval()
    )
    for entry in copies():
        from sciforge import versions

        versions.discard_recovery(rec.folder, entry["key"])
    s["quiet"] = App.newDocument("Quiet")
    s["doc"] = App.newDocument("Gear")
    s["box"] = make_box(s["doc"], "Body", 10, 10, 10)
    h.fit()
    h.check("an unsaved design with a box", not doc().FileName and Gui.ActiveDocument.Modified)
    s["written"] = rec.written


# -- Path 1: autosave ----
def p1_wait():
    pass


p1_wait.wait_ms = 3500


def p1_copy():
    rec = recovery()
    found = copies()
    h.check(
        "P1 a recovery copy was written", rec.written > s["written"], (rec.written, s["written"])
    )
    labels = [e["label"] for e in found]
    h.check("P1 it is the changed design", "Gear" in labels, found)
    h.check("P1 the unchanged design got none", "Quiet" not in labels, labels)
    gear = [e for e in found if e["label"] == "Gear"]
    h.check(
        "P1 never saved: no file name in the sidecar", gear and gear[0]["file_name"] == "", gear
    )
    h.check("P1 the copy is a design file", gear and gear[0]["size"] > 1000, gear)
    h.check("P1 keyed by its name", gear and gear[0]["key"] == "unsaved-Gear", gear)
    s["written"] = rec.written


# -- Path 2: a clean save removes the copy ----
def p2_save():
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


def p2_name():
    h.check("P2 the Save dialog", vi.fill_save_dialog(name="Gear"))
    vi.click_save()


def p2_saved():
    s["path"] = os.path.join(s["project"], "Gear.FCStd")
    h.check("P2 saved as Gear.FCStd", os.path.isfile(s["path"]))
    labels = [e["label"] for e in copies()]
    h.check("P2 a clean save removed the recovery copy", "Gear" not in labels, labels)
    s["box"].Group[0].Height = 20
    doc().recompute()
    h.check("P2 changed again", Gui.ActiveDocument.Modified)
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier | QtCore.Qt.ShiftModifier)


def p2_forced():
    from sciforge import versions

    found = [e for e in copies() if e["label"] == "Gear"]
    h.check("P2 Ctrl+Shift+S wrote a recovery copy at once", len(found) == 1, copies())
    key = versions.recovery_key("Gear", s["path"])
    h.check("P2 keyed by the file now", found and found[0]["key"] == key, found)
    h.check(
        "P2 the sidecar names the file",
        found and os.path.normcase(found[0]["file_name"]) == os.path.normcase(s["path"]),
    )
    h.check("P2 no version was made by it", len(_versions()) == 1, _versions())
    h.check("P2 the design still shows as changed", Gui.ActiveDocument.Modified)
    s["copy"] = found[0]["copy"] if found else None
    s["key"] = key


def _versions():
    from sciforge import versions_ui

    return [v.number for v in versions_ui.store_of(s["path"]).versions()]


# -- Path 3: crash recovery ----
def p3_crash():
    """The copy becomes another session's (what a crash leaves). A crash never gets to
    the clean-close cleanup, so the copy and its sidecar are kept aside while the design
    is closed and put back after; then the start-up check runs again."""
    from sciforge import versions_ui

    side = s["copy"][: -len(".FCStd")] + ".json"
    data = json.load(open(side, encoding="utf-8"))
    data["session"] = "crashed-session"
    with open(side, "w", encoding="utf-8") as handle:
        json.dump(data, handle)
    kept = {path: open(path, "rb").read() for path in (s["copy"], side)}
    rec = recovery()
    rec.timer.stop()
    Gui.getDocument(s["doc"].Name).Modified = False
    App.closeDocument(s["doc"].Name)
    for path, data in kept.items():
        with open(path, "wb") as handle:
            handle.write(data)
    h.check("P3 the crashed session's copy is there", os.path.isfile(s["copy"]))
    h.check(
        "P3 the saved file holds the 1000 box (the change was not saved)",
        near(_file_volume(s["path"]), 1000.0),
        _file_volume(s["path"]),
    )
    h.check("P3 the start-up check finds it", versions_ui.startup_check())


def _file_volume(path):
    from sciforge import versions_ui

    return versions_ui.volume_of_file(path)


def p3_dialog():
    d = vi.recover_dialog()
    h.check(
        "P3 'Recover unsaved work?' is shown",
        d is not None and d.windowTitle() == "Recover unsaved work?",
        h.popups(),
    )
    entries = vi.recover_entries()
    h.check(
        "P3 it lists Gear with its file",
        len(entries) == 1 and entries[0].startswith("Gear"),
        entries,
    )
    h.shot("3-recover")
    h.check("P3 Recover clicked", vi.recover_button("Open"))


def p3_recovered():
    from sciforge import versions_ui

    recovered = App.ActiveDocument
    h.check(
        "P3 the recovered design is open",
        recovered is not None and recovered.Label == "Gear",
        recovered and recovered.Label,
    )
    h.check(
        "P3 with the unsaved change (2000)",
        recovered is not None and near(volume(recovered), 2000.0),
        recovered and volume(recovered),
    )
    h.check(
        "P3 under its own file name",
        recovered is not None
        and os.path.normcase(recovered.FileName) == os.path.normcase(s["path"]),
        recovered and recovered.FileName,
    )
    h.check(
        "P3 shown as changed (to be saved)",
        recovered is not None and Gui.getDocument(recovered.Name).Modified,
    )
    h.check("P3 the copy is kept until the save", os.path.isfile(s["copy"]))
    h.check(
        "P3 known as recovered", recovered is not None and recovered.Name in versions_ui._recovered
    )
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


def p3_save():
    d = vi.version_dialog()
    h.check("P3 Ctrl+S asks for the version description", d is not None, h.popups())
    text = vi.child(d, "SciForgeVersionDescription").text() if d else ""
    h.check("P3 it suggests 'Recovered after a crash'", text == "Recovered after a crash", text)
    vi.accept_save()


def p3_saved():
    from sciforge import versions_ui

    h.check("P3 saved into the file: 2000", near(_file_volume(s["path"]), 2000.0))
    listed = versions_ui.store_of(s["path"]).versions()
    h.check("P3 recorded as v2", [v.number for v in listed] == [1, 2], listed)
    h.check(
        "P3 with the description",
        len(listed) == 2 and listed[1].description == "Recovered after a crash",
        listed,
    )
    h.check("P3 the recovery copy is gone", not os.path.isfile(s["copy"]))
    h.check("P3 shown as saved", not Gui.ActiveDocument.Modified)
    h.check("P3 no pop-up", not h.popups(), h.popups())


# -- Path 4: nothing to recover, Delete, a closed design ----
def p4_nothing():
    from sciforge import versions, versions_ui

    h.check("P4 nothing left to recover", not versions_ui.startup_check())
    h.check("P4 no dialog", vi.recover_dialog() is None)
    # A copy of a never-saved design from a "crash": Delete throws it away.
    folder = recovery().folder
    copy, _ = versions.recovery_paths(folder, "unsaved-Old_Lid")
    shutil.copy(s["path"], copy)
    versions.write_recovery_sidecar(folder, "unsaved-Old_Lid", "Old Lid", "", "crashed-session")
    Gui.runCommand("SciForge_RecoverDocuments")


def p4_delete():
    entries = vi.recover_entries()
    h.check(
        "P4 Recover Documents lists the old copy",
        len(entries) == 1 and entries[0].startswith("Old Lid"),
        entries,
    )
    h.check("P4 it says 'never saved'", entries and "never saved" in entries[0], entries)
    h.check("P4 Delete clicked", vi.recover_button("Delete"))


def p4_deleted():
    labels = [e["label"] for e in copies()]
    h.check("P4 the copy is gone", "Old Lid" not in labels, labels)
    h.check("P4 the dialog closed", vi.recover_dialog() is None)
    # A changed design closed on purpose (discarding) takes its copy with it.
    s["box"] = doc().getObject("Body")
    s["box"].Group[0].Height = 30
    doc().recompute()
    rec = recovery()
    h.check("P4 a copy of the changed design", rec.save_all(forced=False) == 1)
    h.check("P4 is there", any(e["label"] == "Gear" for e in copies()), copies())
    Gui.getDocument(doc().Name).Modified = False
    App.closeDocument(doc().Name)


def p4_closed():
    h.check(
        "P4 closing the design removed its copy",
        not any(e["label"] == "Gear" for e in copies()),
        copies(),
    )


# -- Path 5: not while a command runs ----
def p5_busy():
    document = App.newDocument("Busy")
    s["busy_box"] = make_box(document, "Body", 5, 5, 5)
    h.fit()
    h.press("e")


def p5_check():
    from sciforge import taskui

    h.check("P5 Extrude's dialog is open", taskui.current() is not None)
    rec = recovery()
    h.check(
        "P5 a recovery copy is postponed while a command runs", rec.save_all(forced=False) == -1
    )
    h.check("P5 none was written", not any(e["label"] == "Busy" for e in copies()), copies())
    h.press(QtCore.Qt.Key_Escape)


def p5_after():
    from sciforge import taskui

    h.check("P5 the dialog closed", taskui.current() is None)
    rec = recovery()
    h.check("P5 after the command the copy is written", rec.save_all(forced=False) == 1)
    h.check("P5 it is there", any(e["label"] == "Busy" for e in copies()), copies())


def cleanup():
    from sciforge import versions

    for name in list(App.listDocuments()):
        Gui.getDocument(name).Modified = False
        App.closeDocument(name)
    for entry in copies():
        versions.discard_recovery(recovery().folder, entry["key"])
    App.ParamGet(PREFS).RemInt("AutosaveTestSeconds")
    App.ParamGet(PREFS).RemString("ProjectFolder")
    recovery().restart()
    shutil.rmtree(s["project"], ignore_errors=True)


h.run(
    "versions_recovery",
    [
        setup,
        p1_wait,
        p1_copy,
        p2_save,
        p2_name,
        p2_saved,
        p2_forced,
        p3_crash,
        p3_dialog,
        p3_recovered,
        p3_save,
        p3_saved,
        p4_nothing,
        p4_delete,
        p4_deleted,
        p4_closed,
        p5_busy,
        p5_check,
        p5_after,
        cleanup,
    ],
)
