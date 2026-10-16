# SPDX-License-Identifier: LGPL-2.1-or-later
"""Milestones and closing a changed design, like Fusion (docs/sciforge/parity/versions.md).

A box 10 x 20 x 5 (1000) in a new design; the project folder is a fresh temporary folder
(git is installed here, so versions are commits; a milestone is a tag on its commit).

P1 Ctrl+S: Save dialog, "Gear", Save: v1.
P2 The box grows (2000); Ctrl+S: the Version Description box has a Milestone box; tick it,
   type "first print", Enter: v2, a milestone.
P3 Version History: v2 shows the milestone mark; Milestones only lists v2 alone; off again,
   select v1, Mark as Milestone: v1 is one too (the button says Remove Milestone); Remove
   Milestone takes it off again.
P4 Milestones only, select v2, Open: "Gear v2" opens read-only with the 2000 box; it closes.
P5 Automatic version on close (on, Fusion's default): the box grows to 3000, the tab is
   closed (Ctrl+F4): no question, the design is closed, v3 "Automatic version on close".
P6 Automatic version on close off: Gear opened again, changed to 4000, the tab closed: the
   Close dialog asks. Cancel: the design stays open and changed. Closed again, "bigger"
   typed, Enter: v4 "bigger", closed.
P7 Opened, changed to 5000, closed, Don't Save: closed, no v5, the file keeps 4000.
P8 A design never saved, closed: the dialog says so; Save... opens the Save dialog;
   "Sprocket", Save: Sprocket.FCStd v1, the design is closed.
P9 Quitting with a changed design (the main window's close): the dialog asks first; Cancel
   keeps SciForge open and the design changed; then Don't Save closes it (SciForge then
   quits: the quit itself is not run in the test, the main window's close is answered).
"""

import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import polish2_steps as p2
from SciForgeTests.gui import versions_input as vi
from SciForgeTests.gui import widget_input as wi

s = {}


def gear():
    return p2.doc_named("Gear")


def history_of(path=None):
    from sciforge import versions_ui

    return versions_ui.store_of(path or s["path"]).versions()


def set_height(document, height):
    body = document.getObject("Body")
    body.Group[0].Height = height
    document.recompute()


def tick(box):
    """Click a check box on its tick (its text runs on: the middle of a wide one is no hit)."""
    if h.check("the check box is there", box is not None):
        wi.click(box, QtCore.QPoint(8, box.height() // 2))


def close_dialog():
    return p2.dialog("SciForgeCloseDialog")


def open_gear():
    from sciforge import versions_ui

    versions_ui.open_design(s["path"])


# -- setup ----
def setup():
    Gui.activateWorkbench("SciForgeWorkbench")
    s["project"] = tempfile.mkdtemp(prefix="sciforge-project-")
    p2.set_project(s["project"])
    App.ParamGet(p2.PREFS).SetBool("VersionOnClose", True)
    document = App.newDocument("Design")
    p2.make_box(document, "Body", 10, 20, 5)
    Gui.getDocument(document.Name).ActiveView.setActiveObject("pdbody", document.Body)
    h.fit()
    h.check("a 1000 box in a new design", p2.near(p2.volume(), 1000.0), p2.volume())


# -- P1, P2: a milestone saved ----
def p1_save():
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


def p1_name():
    h.check("P1 the Save dialog", vi.save_dialog() is not None, h.popups())
    vi.fill_save_dialog(name="Gear")
    vi.click_save()


def p1_saved():
    s["path"] = os.path.join(s["project"], "Gear.FCStd")
    h.check("P1 Gear.FCStd saved", os.path.isfile(s["path"]), os.listdir(s["project"]))
    App.ActiveDocument.Label = "Gear"
    listed = history_of()
    h.check("P1 v1", [v.number for v in listed] == [1], listed)
    h.check("P1 v1 is no milestone", listed and not listed[0].milestone)


def p2_grow():
    set_height(App.ActiveDocument, 10)
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


def p2_milestone_box():
    d = vi.version_dialog()
    h.check("P2 the Version Description dialog", d is not None, h.popups())
    box = vi.child(d, "SciForgeVersionMilestone")
    h.check("P2 it has a Milestone box, off", box is not None and not box.isChecked())
    if box is None:
        return
    wi.click(box, QtCore.QPoint(8, box.height() // 2))  # on its tick box, as a person aims
    h.check("P2 Milestone ticked", box.isChecked())
    h.shot("P2-milestone")
    vi.describe_and_save("first print")


def p2_saved():
    listed = history_of()
    h.check("P2 v2 recorded", [v.number for v in listed] == [1, 2], listed)
    h.check(
        "P2 v2 is a milestone with its description",
        listed[-1].milestone and listed[-1].description == "first print",
        [(v.label, v.milestone, v.description) for v in listed],
    )
    from sciforge import versions

    if versions.git_available():
        out = versions._run_git(["tag", "--list"], s["project"])
        h.check("P2 the milestone is a git tag", versions.MILESTONE_TAG in out, out)


# -- P3: the history's milestones ----
def p3_history():
    Gui.runCommand("SciForge_VersionHistory")


def p3_marked():
    d = vi.history_dialog()
    h.check("P3 Version History opens", d is not None)
    table = vi.child(d, "SciForgeHistoryTable")
    marks = [table.item(r, 4).text() for r in range(table.rowCount())] if table else []
    h.check(
        "P3 v2 (the first row) carries the milestone mark",
        marks[:1] and "Milestone" in marks[0] and not marks[1],
        marks,
    )
    tick(vi.child(d, "SciForgeHistoryMilestonesOnly"))


def p3_only():
    rows = vi.history_rows()
    h.check("P3 Milestones only lists v2 alone", [r[0].split()[0] for r in rows] == ["v2"], rows)
    h.shot("P3-milestones-only")
    tick(vi.child(vi.history_dialog(), "SciForgeHistoryMilestonesOnly"))


def p3_mark_v1():
    h.check("P3 all versions listed again", len(vi.history_rows()) == 2, vi.history_rows())
    vi.history_select("v1")
    button = vi.child(vi.history_dialog(), "SciForgeHistoryMilestone")
    h.check(
        "P3 the button says Mark as Milestone", button.text() == "Mark as Milestone", button.text()
    )
    vi.history_button("Milestone")


def p3_v1_marked():
    h.check("P3 v1 is a milestone now", history_of()[0].milestone, history_of())
    button = vi.child(vi.history_dialog(), "SciForgeHistoryMilestone")
    h.check(
        "P3 v1 still selected; the button says Remove Milestone",
        button.text() == "Remove Milestone",
        button.text(),
    )
    vi.history_button("Milestone")


def p3_v1_unmarked():
    h.check("P3 Remove Milestone took it off", not history_of()[0].milestone, history_of())
    h.check("P3 v2 kept its mark", history_of()[1].milestone)


# -- P4: open a milestone ----
def p4_open():
    tick(vi.child(vi.history_dialog(), "SciForgeHistoryMilestonesOnly"))
    vi.history_select("v2")
    vi.history_button("Open")


def p4_opened():
    copy = p2.doc_named("Gear v2")
    h.check("P4 Gear v2 opened", copy is not None, list(App.listDocuments()))
    if copy is None:
        return
    h.check("P4 with v2's 2000 box", p2.near(p2.volume(copy), 2000.0), p2.volume(copy))
    from sciforge import versions_ui

    h.check("P4 read-only (an older version)", versions_ui.version_of(copy) is not None)
    vi.cancel_dialog(vi.history_dialog())
    App.closeDocument(copy.Name)
    App.setActiveDocument(gear().Name)


# -- P5: automatic version on close ----
def p5_change():
    set_height(gear(), 15)
    h.check("P5 the design shows as changed", Gui.getDocument(gear().Name).Modified)
    p2.close_tab(gear())


def p5_closed():
    h.check(
        "P5 no question asked",
        close_dialog() is None and not vi.popups_except(()),
        vi.popups_except(()),
    )
    h.check("P5 the design closed", gear() is None, list(App.listDocuments()))
    listed = history_of()
    h.check("P5 v3 made by the close", [v.number for v in listed] == [1, 2, 3], listed)
    h.check(
        "P5 described as the automatic version",
        listed and listed[-1].description == "Automatic version on close",
        listed,
    )
    from sciforge import versions

    h.check("P5 the file holds the 3000 box", versions.summary(s["path"])["bodies"] == 1)


# -- P6: asked when the option is off ----
def p6_off():
    App.ParamGet(p2.PREFS).SetBool("VersionOnClose", False)
    open_gear()


def p6_change():
    h.check("P6 Gear open again", gear() is not None)
    h.check("P6 it has the 3000 box", p2.near(p2.volume(gear()), 3000.0), p2.volume(gear()))
    set_height(gear(), 20)
    p2.close_tab(gear())


def p6_asked():
    d = close_dialog()
    h.check("P6 the Close dialog asks", d is not None, vi.popups_except(()))
    h.check("P6 the design is still open", gear() is not None)
    h.shot("P6-close-dialog")
    if d is not None:
        wi.click(p2.child(d, "SciForgeCloseCancel"))


def p6_cancelled():
    h.check("P6 Cancel: still open", gear() is not None)
    h.check(
        "P6 Cancel: still changed", gear() is not None and Gui.getDocument(gear().Name).Modified
    )
    h.check("P6 Cancel: no new version", len(history_of()) == 3, history_of())
    p2.close_tab(gear())


def p6_describe():
    d = close_dialog()
    h.check("P6 asked again", d is not None)
    field = p2.child(d, "SciForgeCloseDescription")
    if field is None:
        return
    vi.type_into(field, "bigger")
    QtTest.QTest.keyClick(field, QtCore.Qt.Key_Return)
    p2.process()


def p6_saved():
    h.check("P6 Enter saved and closed", gear() is None, list(App.listDocuments()))
    listed = history_of()
    h.check("P6 v4 'bigger'", [v.description for v in listed][-1:] == ["bigger"], listed)


# -- P7: Don't Save ----
def p7_open():
    open_gear()


def p7_change():
    s["mtime"] = os.path.getmtime(s["path"])
    set_height(gear(), 25)
    p2.close_tab(gear())


def p7_discard():
    d = close_dialog()
    h.check("P7 asked", d is not None)
    if d is not None:
        wi.click(p2.child(d, "SciForgeCloseDiscard"))


def p7_gone():
    h.check("P7 Don't Save: closed", gear() is None, list(App.listDocuments()))
    h.check("P7 no v5", len(history_of()) == 4, history_of())
    h.check("P7 the file was not written", os.path.getmtime(s["path"]) == s["mtime"])
    open_gear()


def p7_reopened():
    h.check(
        "P7 reopened: the 4000 box (the last saved)",
        p2.near(p2.volume(gear()), 4000.0),
        p2.volume(gear()),
    )
    App.closeDocument(gear().Name)


# -- P8: a design never saved ----
def p8_new():
    document = App.newDocument("Sprocket")
    p2.make_box(document, "Body", 5, 5, 5)
    Gui.getDocument(document.Name).Modified = True
    s["new"] = document.Name
    p2.close_tab(document)


def p8_asked():
    d = close_dialog()
    h.check("P8 the dialog asks about a design never saved", d is not None, vi.popups_except(()))
    h.check(
        "P8 no description field (no version yet)",
        d is not None and p2.child(d, "SciForgeCloseDescription") is None,
    )
    save = p2.child(d, "SciForgeCloseSave")
    h.check(
        "P8 Save... offered",
        save is not None and save.text() == "Save...",
        save.text() if save else None,
    )
    if save is not None:
        wi.click(save)


def p8_name():
    h.check("P8 the Save dialog comes", vi.save_dialog() is not None, vi.popups_except(()))
    vi.fill_save_dialog(name="Sprocket")
    vi.click_save()


def p8_closed():
    path = os.path.join(s["project"], "Sprocket.FCStd")
    h.check("P8 Sprocket.FCStd saved", os.path.isfile(path), os.listdir(s["project"]))
    h.check("P8 then closed", s["new"] not in App.listDocuments(), list(App.listDocuments()))
    if os.path.isfile(path):
        h.check("P8 Sprocket v1", [v.number for v in history_of(path)] == [1])


# -- P9: quitting with a changed design ----
def p9_change():
    open_gear()


def p9_quit():
    set_height(gear(), 30)
    s["main_closed"] = False
    event = QtGui_close_event()
    QtWidgets.QApplication.sendEvent(Gui.getMainWindow(), event)
    s["accepted"] = event.isAccepted()


def QtGui_close_event():
    from PySide import QtGui

    return QtGui.QCloseEvent()


def p9_asked():
    h.check("P9 the quit was held back for the question", not s["accepted"])
    d = close_dialog()
    h.check("P9 the Close dialog asks before quitting", d is not None, vi.popups_except(()))
    if d is not None:
        wi.click(p2.child(d, "SciForgeCloseCancel"))


def p9_cancelled():
    h.check("P9 Cancel: SciForge stays with the design open", gear() is not None)
    h.check("P9 Cancel: still changed", Gui.getDocument(gear().Name).Modified)
    # the version kept: the change is given up by Don't Save on the next close
    p2.close_tab(gear())


def p9_discard():
    d = close_dialog()
    if h.check("P9 asked on the close", d is not None):
        wi.click(p2.child(d, "SciForgeCloseDiscard"))


def p9_done():
    h.check(
        "P9 closed without a new version", gear() is None and len(history_of()) == 4, history_of()
    )
    App.ParamGet(p2.PREFS).SetBool("VersionOnClose", True)


STEPS = [
    setup,
    p1_save,
    p1_name,
    p1_saved,
    p2_grow,
    p2_milestone_box,
    p2_saved,
    p3_history,
    p3_marked,
    p3_only,
    p3_mark_v1,
    p3_v1_marked,
    p3_v1_unmarked,
    p4_open,
    p4_opened,
    p5_change,
    p5_closed,
    p6_off,
    p6_change,
    p6_asked,
    p6_cancelled,
    p6_describe,
    p6_saved,
    p7_open,
    p7_change,
    p7_discard,
    p7_gone,
    p7_reopened,
    p8_new,
    p8_asked,
    p8_name,
    p8_closed,
    p9_change,
    p9_quit,
    p9_asked,
    p9_cancelled,
    p9_discard,
    p9_done,
]

h.run("polish2_versions", STEPS)
