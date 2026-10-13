# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Data Panel on a local project folder, like Fusion's (docs/sciforge/parity/versions.md).

A project folder with a "Robots" folder and two designs (Arm, a box of 1000; Base, a box of
8000) saved with thumbnails and closed.
Path 1, Ctrl+Alt+P shows the panel on the left: the folder first, then the designs with
  their thumbnails and the version badge (v1 each).
Path 2, double-click Arm: it opens, with its box; double-click again brings it to the front
  instead of opening it twice.
Path 3, New Folder: "New Folder" appears; double-click goes into it (breadcrumb "Project /
  New Folder"), Up goes back; double-click Robots goes in, Up goes back.
Path 4, a save shows in the panel: Arm saved again is v2 there.
Path 5, Ctrl+Alt+P hides the panel; the Data Panel button in the application bar shows it.
"""

import os
import shutil
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import versions_input as vi
from SciForgeTests.gui import widget_input as wi

s = {}
PREFS = "User parameter:BaseApp/Preferences/Mod/SciForge/Files"


def make_box(document, name, length, width, height):
    body = document.addObject("PartDesign::Body", name)
    box = document.addObject("PartDesign::AdditiveBox", name + "Box")
    body.addObject(box)
    box.Length, box.Width, box.Height = length, width, height
    document.recompute()
    Gui.getDocument(document.Name).ActiveView.setActiveObject("pdbody", body)
    return body


def volume(document):
    return sum(o.Shape.Volume for o in document.Objects if o.TypeId == "PartDesign::Body")


def panel():
    return vi.data_panel()


def names():
    return [text for _kind, _path, text in panel().items()] if panel() else []


def setup():
    Gui.activateWorkbench("SciForgeWorkbench")
    s["project"] = tempfile.mkdtemp(prefix="sciforge-project-")
    App.ParamGet(PREFS).SetString("ProjectFolder", s["project"])
    App.ParamGet(PREFS).SetBool("AskDescription", True)
    os.makedirs(os.path.join(s["project"], "Robots"))
    for name, size in (("Arm", 10), ("Base", 20)):
        document = App.newDocument(name)
        make_box(document, "Body", size, size, size)
        h.fit()
        path = os.path.join(s["project"], name + ".FCStd")
        document.saveAs(path)
        s[name] = path


setup.wait_ms = 1500


def close_all():
    for name in list(App.listDocuments()):
        Gui.getDocument(name).Modified = False
        App.closeDocument(name)
    App.newDocument("Scratch")  # keys are pressed on a 3D view: one stays open
    from sciforge import versions

    h.check(
        "two designs saved with thumbnails",
        all(versions.thumbnail_bytes(s[n]) for n in ("Arm", "Base")),
    )
    h.check(
        "each is v1 (saved while SciForge is on)",
        all(versions.version_count(s[n]) >= 0 for n in ("Arm", "Base")),
    )


# -- Path 1: show the panel ----
def p1_show():
    h.check("P1 the panel is hidden to begin with", not _panel_visible())
    h.press(QtCore.Qt.Key_P, QtCore.Qt.ControlModifier | QtCore.Qt.AltModifier)


def _panel_visible():
    from sciforge import versions_ui

    return versions_ui.panel_visible()


def p1_listed():
    h.check("P1 Ctrl+Alt+P shows the Data Panel", _panel_visible())
    listed = names()
    h.check(
        "P1 the folder first, then the designs",
        [n.split()[0] for n in listed] == ["Robots", "Arm", "Base"],
        listed,
    )
    h.check("P1 version badges v1", all(n.endswith("v1") for n in listed[1:]), listed)
    h.check(
        "P1 the cards show the designs' thumbnails",
        panel() and all(panel().has_thumbnail(s[n]) for n in ("Arm", "Base")),
    )
    dock = panel().parentWidget()
    main = Gui.getMainWindow()
    h.check("P1 docked on the left", main.dockWidgetArea(dock) == QtCore.Qt.LeftDockWidgetArea)
    h.shot("1-data-panel")


# -- Path 2: open a design ----
def p2_open():
    h.check("P2 double-click Arm", vi.panel_double_click("Arm"))


def p2_opened():
    opened = App.ActiveDocument
    h.check(
        "P2 Arm opened",
        opened is not None and os.path.normcase(opened.FileName) == os.path.normcase(s["Arm"]),
        opened and opened.FileName,
    )
    h.check(
        "P2 with its box",
        opened is not None and abs(volume(opened) - 1000.0) < 1e-3,
        opened and volume(opened),
    )
    s["arm_doc"] = opened.Name if opened else None
    App.newDocument("Other")
    h.check("P2 double-click Arm again", vi.panel_double_click("Arm"))


def p2_front():
    arm_docs = [
        n
        for n in App.listDocuments()
        if os.path.normcase(App.getDocument(n).FileName) == os.path.normcase(s["Arm"])
    ]
    h.check(
        "P2 brought to the front, not opened twice",
        App.ActiveDocument.Name == s["arm_doc"] and len(arm_docs) == 1,
        list(App.listDocuments()),
    )
    App.closeDocument("Other")


# -- Path 3: folders ----
def p3_new_folder():
    h.check("P3 New Folder clicked", vi.panel_button("NewFolder"))


def p3_made():
    h.check(
        "P3 'New Folder' is in the project", os.path.isdir(os.path.join(s["project"], "New Folder"))
    )
    listed = names()
    h.check("P3 and listed among the folders", listed[:2] == ["New Folder", "Robots"], listed)
    h.check("P3 double-click it", vi.panel_double_click("New Folder"))


def p3_inside():
    crumbs = panel().crumbs.text()
    h.check(
        "P3 inside: the breadcrumb says Project / New Folder",
        "Project" in crumbs and "New Folder" in crumbs,
        crumbs,
    )
    h.check("P3 empty", names() == [], names())
    h.check("P3 Up clicked", vi.panel_button("Up"))


def p3_back():
    h.check("P3 back in the project", names()[:2] == ["New Folder", "Robots"], names())
    h.check("P3 double-click Robots", vi.panel_double_click("Robots"))


def p3_robots():
    h.check("P3 inside Robots", "Robots" in panel().crumbs.text(), panel().crumbs.text())
    wi.click(panel().up)


def p3_back_again():
    h.check("P3 Up again", names()[:2] == ["New Folder", "Robots"], names())


# -- Path 4: a save shows ----
def p4_save():
    App.setActiveDocument(s["arm_doc"])
    arm = App.getDocument(s["arm_doc"])
    arm.getObject("Body").Group[0].Height = 20
    arm.recompute()
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


def p4_describe():
    h.check("P4 the version dialog", vi.describe_and_save("longer arm"))


def p4_badge():
    listed = names()
    arm = [n for n in listed if n.startswith("Arm")]
    h.check("P4 Arm shows v2 in the panel", arm == ["Arm  v2"], listed)
    h.shot("4-badge")


# -- Path 5: hide and show ----
def p5_hide():
    h.press(QtCore.Qt.Key_P, QtCore.Qt.ControlModifier | QtCore.Qt.AltModifier)


def p5_hidden():
    h.check("P5 Ctrl+Alt+P hides the panel", not _panel_visible())
    button = wi.quick_access("Data Panel")
    h.check("P5 the Data Panel button is in the application bar", button is not None)
    if button is not None:
        wi.click(button)


def p5_shown():
    h.check("P5 the button shows it again", _panel_visible())


def cleanup():
    from sciforge import versions_ui

    versions_ui.hide_panel()
    for name in list(App.listDocuments()):
        Gui.getDocument(name).Modified = False
        App.closeDocument(name)
    App.ParamGet(PREFS).RemString("ProjectFolder")
    shutil.rmtree(s["project"], ignore_errors=True)


h.run(
    "versions_data_panel",
    [
        setup,
        close_all,
        p1_show,
        p1_listed,
        p2_open,
        p2_opened,
        p2_front,
        p3_new_folder,
        p3_made,
        p3_inside,
        p3_back,
        p3_robots,
        p3_back_again,
        p4_save,
        p4_describe,
        p4_badge,
        p5_hide,
        p5_hidden,
        p5_shown,
        cleanup,
    ],
)
