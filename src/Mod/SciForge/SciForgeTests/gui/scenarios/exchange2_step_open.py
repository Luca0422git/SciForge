# SPDX-License-Identifier: LGPL-2.1-or-later
"""File > Open of STEP and IGES files: a design with the file's components (exchange-2,
docs/sciforge/parity/insert-export.md Part 2). Only real input: Ctrl+O and the menus; the
system's file dialog is the only stand-in (exchange_ui.OPEN_PICKER).

Fixture robot.step (made with FreeCAD's STEP writer, exchange_steps.make_robot): Robot >
Base (box, blue), Drive > Axle, Wheel (red), the Wheel again (a second occurrence).

P1  Ctrl+O, robot.step: a new design "robot" (unsaved) with Base, Drive, and in Drive Axle,
    Wheel and Wheel:2, a linked copy of Wheel; one body each, the volumes of the file, where
    the file has them; Base blue, Wheel and its copy red; the browser lists Wheel:1 and
    Wheel:2; the timeline has a step per component and the bodies' steps.
P2  The copy follows its original: the Wheel's body made 2 mm thicker (its base shape)
    shows in Wheel:2 at the next compute.
P3  Saved, closed and opened again with Ctrl+O: the same components, copy, bodies and
    colours.
P4  File > Open (the application menu) of two_parts.step (two free parts): components Plate
    and Peg, one body each, blue and red.
P5  An IGES file (written by SciForge's IGES export of two boxes): the solids as two bodies
    at the root (IGES keeps no assemblies).
P6  A SAT file: refused, the message says FreeCAD cannot read ACIS and to save STEP; no
    design is made.
P7  A broken STEP file: refused with the reason; no design is left behind.
P8  The Data Panel: Upload robot.step (it is copied into the project folder and listed as
    "robot.step"); double-click it: a new design with the robot's components; right-click
    it > Insert into Current Design: the robot comes in as one component "robot" (the
    Move dialog opens; Esc).
"""

import os

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import exchange_steps as x
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as i
from SciForgeTests.gui import timeline_input as t

s = {}


def ctrl_o():
    h.press(QtCore.Qt.Key_O, QtCore.Qt.ControlModifier)


def setup():
    Gui.activateWorkbench("SciForgeWorkbench")
    s["robot"] = x.make_robot(x.out("robot.step"))
    s["broken"], s["sat"] = x.make_bad_files()
    App.newDocument("Start")
    h.fit()
    h.check("the robot file is written", os.path.isfile(s["robot"]))


# -- P1 ----------------------------------------------------------------------------------------
def p1_open():
    x.use_open_file(s["robot"])
    s["docs"] = set(App.listDocuments())
    ctrl_o()


p1_open.wait_ms = 2500


def p1_check():
    doc = App.ActiveDocument
    new = set(App.listDocuments()) - s["docs"]
    h.check("P1 a new design was made", len(new) == 1, new)
    h.check("P1 it is named after the file", doc is not None and doc.Label == "robot", doc.Label)
    h.check("P1 it is not saved yet (Ctrl+S asks where)", doc is not None and not doc.FileName)
    x.check_robot("P1")
    for label, colour in (("Base", x.BLUE), ("Wheel", x.RED), ("Wheel:2", x.RED)):
        body = x.body_of(label)
        h.check(
            "P1 %s has the file's colour" % label,
            body is not None and x.same_colour(x.look_of(body), colour),
            body and x.look_of(body),
        )
    rows = t.labels()
    h.check(
        "P1 the browser lists the components and the copies",
        all(any(r.startswith(name) for r in rows) for name in ("Base", "Drive", "Axle"))
        and any("Wheel:1" in r for r in rows)
        and any("Wheel:2" in r for r in rows),
        rows,
    )
    titles = i.timeline_titles()
    h.check(
        "P1 the timeline shows the components",
        all(name in titles for name in ("Base", "Drive", "Axle", "Wheel")),
        titles,
    )
    h.check("P1 no pop-up", not h.popups(), h.popups())
    h.check("P1 SciForge says what came in", "4 components, 1 copy, 3 bodies" in x.told(), x.told())
    h.fit()
    h.shot("1-robot")


# -- P2 ----------------------------------------------------------------------------------------
def p2_thicker():
    import Part

    wheel = x.body_of("Wheel")
    base = wheel.BaseFeature
    base.Shape = Part.makeCylinder(8, 7, App.Vector(0, 0, 0), App.Vector(0, 1, 0))
    App.ActiveDocument.recompute()


p2_thicker.wait_ms = 1500


def p2_check():
    import math

    wheel, copy = x.body_of("Wheel"), x.body_of("Wheel:2")
    want = math.pi * 64 * 7
    h.check("P2 the Wheel is 7 mm thick", wheel is not None and x.near(wheel.Shape.Volume, want))
    h.check(
        "P2 its copy Wheel:2 too",
        copy is not None and x.near(copy.Shape.Volume, want),
        copy and copy.Shape.Volume,
    )


# -- P3 ----------------------------------------------------------------------------------------
def p3_save_reopen():
    import tempfile

    doc = App.ActiveDocument
    # the Wheel back to 5 mm (P2 was a change made by code; this one too)
    import Part

    x.body_of("Wheel").BaseFeature.Shape = Part.makeCylinder(
        8, 5, App.Vector(0, 0, 0), App.Vector(0, 1, 0)
    )
    doc.recompute()
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-exchange2-"), "Robot.FCStd")
    doc.saveAs(path)
    s["saved"] = path
    Gui.getDocument(doc.Name).Modified = False
    App.closeDocument(doc.Name)
    # a click on the tab of the design left open (its 3D view takes the keys again)
    from PySide import QtWidgets as QW

    area = Gui.getMainWindow().findChild(QW.QMdiArea)
    for sub in area.subWindowList():
        if sub.windowTitle().startswith("Start :"):
            area.setActiveSubWindow(sub)


p3_save_reopen.wait_ms = 1500


def p3_ctrl_o():
    h.check(
        "P3 the design is closed",
        "Robot" not in [App.getDocument(n).Label for n in App.listDocuments()],
    )
    x.use_open_file(s["saved"])  # File > Open (Ctrl+O) of the saved design
    ctrl_o()


p3_ctrl_o.wait_ms = 2500


def p3_check():
    x.check_robot("P3")
    body = x.body_of("Wheel:2")
    h.check(
        "P3 the copy is still red",
        body is not None and x.same_colour(x.look_of(body), x.RED),
        body and x.look_of(body),
    )
    h.fit()
    h.shot("3-reopened")


# -- P4 ----------------------------------------------------------------------------------------
def p4_open_menu():
    from SciForgeTests.gui import misc_steps as m

    x.use_open_file(i.fixture("two_parts.step"))
    s["menu"] = m.app_menu_item(["File", "Open"])


p4_open_menu.wait_ms = 2500


def p4_check():
    doc = App.ActiveDocument
    h.check("P4 File > Open was clicked", s["menu"]["clicked"])
    h.check(
        "P4 the design is named two_parts",
        doc is not None and doc.Label == "two_parts",
        doc and doc.Label,
    )
    h.check("P4 components Peg and Plate", x.labels() == ["Peg", "Plate"], x.labels())
    plate, peg = x.body_of("Plate"), x.body_of("Peg")
    h.check("P4 Plate 6000 mm3", plate is not None and x.near(plate.Shape.Volume, i.PLATE_VOLUME))
    h.check("P4 Peg 1178.1 mm3", peg is not None and x.near(peg.Shape.Volume, i.PEG_VOLUME))
    h.check("P4 Plate blue", plate is not None and x.same_colour(x.look_of(plate), x.BLUE))
    h.check("P4 Peg red", peg is not None and x.same_colour(x.look_of(peg), x.RED))


# -- P5 ----------------------------------------------------------------------------------------
def p5_iges():
    from sciforge import exchange

    # an IGES file of two boxes, written by SciForge's own IGES export
    doc = App.newDocument("IgesSource")
    from sciforge import components

    import Part

    for label, shape in (("Block", Part.makeBox(20, 10, 5)), ("Pin", Part.makeCylinder(3, 12))):
        body = components.new_body_in(doc, None, label)
        base = doc.addObject("Part::Feature", "B")
        base.Shape = shape
        body.BaseFeature = base
    doc.recompute()
    s["iges"] = x.out("two_solids.igs")
    exchange.export_cad(doc, "iges", s["iges"])
    Gui.getDocument(doc.Name).Modified = False
    App.closeDocument(doc.Name)
    x.use_open_file(s["iges"])
    ctrl_o()


p5_iges.wait_ms = 2500


def p5_check():
    import math

    doc = App.ActiveDocument
    h.check("P5 the IGES design", doc is not None and doc.Label == "two_solids", doc and doc.Label)
    from sciforge import components

    found = components.bodies_in(doc, None)
    volumes = sorted(round(b.Shape.Volume, 1) for b in found)
    h.check(
        "P5 two solid bodies at the root",
        volumes == sorted([1000.0, round(math.pi * 9 * 12, 1)]),
        volumes,
    )
    h.check("P5 no components (IGES has none)", not x.comps(), x.labels())


# -- P6 / P7 -----------------------------------------------------------------------------------
def p6_sat():
    s["docs"] = set(App.listDocuments())
    x.use_open_file(s["sat"])
    ctrl_o()


def p6_check():
    h.check("P6 no design made", set(App.listDocuments()) == s["docs"], App.listDocuments())
    msg = x.told()
    h.check("P6 SciForge says why", "SAT" in msg and "STEP" in msg, msg)
    x.use_open_file(s["broken"])
    ctrl_o()


p6_check.wait_ms = 2000
p6_check.known = True  # OpenCASCADE prints its own reader messages for the broken file


def p7_check():
    h.check("P7 no design left behind", set(App.listDocuments()) == s["docs"], App.listDocuments())
    msg = x.told()
    h.check(
        "P7 SciForge says the file could not be read",
        "could not be read" in msg or "Nothing" in msg,
        msg,
    )
    x.use_open_file(None)
    h.new_errors()


# -- P8 ----------------------------------------------------------------------------------------
FILES = "User parameter:BaseApp/Preferences/Mod/SciForge/Files"


def p8_upload():
    import tempfile

    from sciforge import versions_ui

    s["project"] = tempfile.mkdtemp(prefix="sciforge-exchange2-project-")
    App.ParamGet(FILES).SetString("ProjectFolder", s["project"])
    versions_ui.show_panel()
    versions_ui.UPLOAD_PICKER = lambda: s["robot"]


p8_upload.wait_ms = 1500


def p8_click_upload():
    from SciForgeTests.gui import versions_input as vi

    panel = vi.data_panel()
    h.check("P8 the Data Panel is shown", panel is not None)
    if panel is not None:
        h.check("P8 on the project folder", panel.folder == s["project"], panel.folder)
    h.check("P8 the Upload button", vi.panel_button("Upload"))


p8_click_upload.wait_ms = 1500


def p8_open():
    from SciForgeTests.gui import versions_input as vi

    copied = os.path.join(s["project"], "robot.step")
    h.check("P8 the file was copied into the project", os.path.isfile(copied))
    lst = vi.panel_list()
    texts = [lst.item(k).text() for k in range(lst.count())] if lst is not None else []
    h.check(
        "P8 the Data Panel lists robot.step", any(t.startswith("robot.step") for t in texts), texts
    )
    s["docs"] = set(App.listDocuments())
    vi.panel_double_click("robot.step")


p8_open.wait_ms = 2500


def p8_opened():
    new = set(App.listDocuments()) - s["docs"]
    h.check("P8 double-click opened it as a new design", len(new) == 1, new)
    h.check("P8 with the robot's components", "Wheel:2" in x.labels(), x.labels())
    from SciForgeTests.gui import versions_input as vi
    from SciForgeTests.gui import widget_input as w

    lst = vi.panel_list()
    for k in range(lst.count() if lst is not None else 0):
        item = lst.item(k)
        if item.text().startswith("robot.step"):
            ok = w.right_click(
                lst.viewport(), lst.visualItemRect(item).center(), "Insert into Current Design"
            )
            h.check("P8 Data Panel menu > Insert into Current Design", ok)


p8_opened.wait_ms = 2500


def p8_check():
    robot = x.comp("robot")
    h.check("P8 the robot came in as one component", robot is not None, x.labels())
    drives = [c for c in x.comps() if c.Label == "Drive"]
    h.check(
        "P8 with its own Drive inside",
        robot is not None and any(x.parent_label(c) == "robot" for c in drives),
        [(c.Label, x.parent_label(c)) for c in drives],
    )
    h.press(QtCore.Qt.Key_Escape)


p8_check.wait_ms = 1000


def p8_done():
    from sciforge import taskui, versions_ui

    h.check("P8 Esc closed the Move dialog", taskui.current() is None)
    versions_ui.UPLOAD_PICKER = None
    versions_ui.hide_panel()
    App.ParamGet(FILES).RemString("ProjectFolder")
    import shutil

    shutil.rmtree(s["project"], ignore_errors=True)


def cleanup():
    for name in list(App.listDocuments()):
        try:
            Gui.getDocument(name).Modified = False
        except Exception:
            pass
        App.closeDocument(name)
    h.new_errors()


h.run(
    "exchange2_step_open",
    [
        setup,
        p1_open,
        p1_check,
        p2_thicker,
        p2_check,
        p3_save_reopen,
        p3_ctrl_o,
        p3_check,
        p4_open_menu,
        p4_check,
        p5_iges,
        p5_check,
        p6_sat,
        p6_check,
        p7_check,
        p8_upload,
        p8_click_upload,
        p8_open,
        p8_opened,
        p8_check,
        p8_done,
        cleanup,
    ],
)
