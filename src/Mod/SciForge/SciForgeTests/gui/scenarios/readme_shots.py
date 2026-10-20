# SPDX-License-Identifier: LGPL-2.1-or-later
"""The pictures of the GitHub page (README.md, docs/sciforge/images/), made by using SciForge.
tools/sciforge/screenshots.sh runs this scenario and crops the window out of the screen grabs.

Not a test of behaviour (the checks only say that each picture shows what it should): it
walks to five views and takes a screen grab of each, with the dark look, at 1920 x 1200.

  1 home      the Home tab with a few designs in Recent / This computer
  2 sketch    a sketch with the sketch palette, its dimensions and a rectangle and circle
  3 timeline  a finished design (the Raspberry Pi 5 case example) with its timeline
  4 presspull Press Pull on a box: the arrow and the distance box
  5 ai        the AI panel open on a design

Every design is made or opened here; nothing of the person's own is used, and the project
folder is a temporary one (given back at the end, a CI shard shares one profile).
"""

import os
import shutil
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import widget_input as wi

V = App.Vector
s = {}
FILES = "User parameter:BaseApp/Preferences/Mod/SciForge/Files"
EXAMPLE = "pi5_case.FCStd"


def home():
    from sciforge import home_ui

    return home_ui.view()


def example_path():
    """docs/sciforge/examples/pi5-case/pi5_case.FCStd of the repository (run from a checkout)."""
    here = os.path.dirname(os.path.abspath(__file__))
    folder = here
    for _n in range(8):
        folder = os.path.dirname(folder)
        candidate = os.path.join(folder, "docs", "sciforge", "examples", "pi5-case", EXAMPLE)
        if os.path.isfile(candidate):
            return candidate
    return ""


def make_box(doc, x, y, z):
    body = doc.addObject("PartDesign::Body", "Body")
    box = doc.addObject("PartDesign::AdditiveBox", "Box")
    body.addObject(box)
    box.Length, box.Width, box.Height = x, y, z
    doc.recompute()
    return body


def save_design(name, sizes, hole=False):
    doc = App.newDocument(name)
    make_box(doc, *sizes)
    h.fit()
    path = os.path.join(s["project"], name + ".FCStd")
    doc.saveAs(path)
    return doc


def close_all():
    for name in list(App.listDocuments()):
        Gui.getDocument(name).Modified = False
        App.closeDocument(name)


# -- 1 Home ---------------------------------------------------------------------------------
def setup():
    from sciforge import home_core, home_ui

    s["root"] = tempfile.mkdtemp(prefix="sciforge-readme-")
    s["project"] = os.path.join(s["root"], "SciForge")
    os.makedirs(s["project"])
    s["old_project"] = App.ParamGet(FILES).GetString("ProjectFolder", "")
    App.ParamGet(FILES).SetString("ProjectFolder", s["project"])
    state = home_core.empty()
    state["merged_mru"] = True
    home_ui.save_state(state)
    home().refresh()
    s["example"] = example_path()
    h.check("the Pi 5 example is in the repository", bool(s["example"]), s["example"])


def make_designs():
    # three designs saved one after the other: Recent lists the newest first
    save_design("Bracket", (40, 25, 8))
    close_all()
    save_design("Enclosure", (60, 40, 22))
    close_all()
    if s["example"]:
        target = os.path.join(s["project"], "Pi 5 case.FCStd")
        shutil.copyfile(s["example"], target)
        doc = App.openDocument(target)
        App.setActiveDocument(doc.Name)
        h.fit()
        s["pi5_name"] = doc.Name
        doc.save()
        close_all()


make_designs.wait_ms = 2500


def show_home():
    from sciforge import home_ui

    h.check("closing the last design shows Home", home_ui.is_active())
    page = home()
    page.refresh()
    s["rows"] = [
        text.split("\n")[0] for _k, _key, _p, text, _s in (page.items("recent") if page else [])
    ]
    h.check("Recent lists the designs", len(s["rows"]) >= 3, s["rows"])


show_home.wait_ms = 2500


def shoot_home():
    page = home()
    h.check("the pictures of the tiles are loaded", page.loading() == 0, page.loading())
    h.shot("home")


shoot_home.wait_ms = 1500


# -- 2 the sketch ---------------------------------------------------------------------------
def new_design():
    App.newDocument("Sketch")
    Gui.activateWorkbench("SciForgeWorkbench")
    h.fit()


def create_sketch():
    h.ribbon("Create Sketch")


def pick_xy():
    pl.click_square("XY_Plane")


def draw():
    import Part
    import Sketcher

    sk = h.in_sketch()
    h.check("a sketch is open on XY", sk is not None)
    if sk is None:
        return
    h.draw_rectangle(sk, -30, -18, 30, 18)
    h.draw_circle(sk, -10, 0, 6)
    h.draw_circle(sk, 10, 0, 6)
    sk.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, 60.0))
    sk.addConstraint(Sketcher.Constraint("DistanceY", 1, 1, 1, 2, 36.0))
    sk.addConstraint(Sketcher.Constraint("Diameter", 4, 12.0))
    App.ActiveDocument.recompute()
    h.fit(iso=False)


draw.wait_ms = 1500


def shoot_sketch():
    sk = h.in_sketch()
    h.check("still in the sketch", sk is not None)
    h.view().viewTop()
    h.view().fitAll()
    QtWidgets.QApplication.processEvents()
    h.shot("sketch")


shoot_sketch.wait_ms = 1500


def finish_sketch():
    h.ribbon("Finish Sketch")


def closed():
    close_all()


# -- 3 the timeline -------------------------------------------------------------------------
def open_example():
    doc = App.openDocument(os.path.join(s["project"], "Pi 5 case.FCStd"))
    App.setActiveDocument(doc.Name)
    Gui.activeDocument().activeView().viewIsometric()
    h.fit()


open_example.wait_ms = 3000


def shoot_timeline():
    from sciforge import timeline_ui

    h.check("a design is open", App.ActiveDocument is not None)
    del timeline_ui
    h.fit()
    hide_overlay_frames()
    h.shot("timeline")
    show_overlay_frames()


shoot_timeline.wait_ms = 2000


# -- 4 Press Pull ---------------------------------------------------------------------------
def box_for_presspull():
    close_all()
    doc = App.newDocument("PressPull")
    make_box(doc, 40, 20, 10)
    Gui.activateWorkbench("SciForgeWorkbench")
    h.fit()


def press_pull():
    h.click_empty()
    h.press("q")


def click_top():
    h.click(V(20, 10, 10))


def type_distance():
    from sciforge import presspull_ui
    from SciForgeTests.gui import dialog_input as ui

    p = presspull_ui.PressPullPanel.last
    h.check("Press Pull is open on the top face", p is not None and p.target is not None)
    if p is not None and p.target is not None:
        ui.type_into(p.field.widget, "6")


type_distance.wait_ms = 2500


def shoot_presspull():
    h.check("the preview made the box 16 high", h.solid_volume() > 40 * 20 * 15, h.solid_volume())
    h.shot("presspull")


shoot_presspull.wait_ms = 1500


def cancel_presspull():
    h.task_button("Cancel")


# -- 5 the AI panel -------------------------------------------------------------------------
def open_ai_panel():
    from sciforge import shell

    close_all()
    doc = App.newDocument("AIPanel")
    make_box(doc, 40, 30, 10)
    Gui.activateWorkbench("SciForgeWorkbench")
    h.fit()
    wi.click(shell.ribbon().tab_buttons["utilities"])


def click_ai():
    for button in h.ribbon_buttons():
        if button.objectName() == "SciForgeBig_AI":
            wi.click(button)
            return
    h.check("UTILITIES has an AI button", False)


def shoot_ai():
    from sciforge import ai_panel_ui

    h.check("the AI panel is open", ai_panel_ui.is_shown())
    h.fit()
    hide_overlay_frames()
    h.shot("ai")
    show_overlay_frames()


shoot_ai.wait_ms = 2000


def overlay_frames():
    """FreeCAD's empty right overlay panel (OverlayRight): its outline shows over the 3D view
    while a right-side SciForge dock is there (a known cosmetic issue, docs/sciforge/
    known-issues.md); the pictures are taken without it."""
    found = []
    for w in Gui.getMainWindow().findChildren(QtWidgets.QWidget):
        if w.metaObject().className() == "Gui::OverlayTabWidget":
            found.append(w)
    return found


def hide_overlay_frames():
    s["hidden"] = [w for w in overlay_frames() if w.isVisible()]
    for w in s["hidden"]:
        w.hide()
    QtWidgets.QApplication.processEvents()


def show_overlay_frames():
    for w in s.get("hidden", []):
        w.show()
    s["hidden"] = []


def tidy():
    from sciforge import ai_panel_ui

    if ai_panel_ui.is_shown():
        ai_panel_ui.toggle()
    close_all()
    App.ParamGet(FILES).SetString("ProjectFolder", s["old_project"])
    shutil.rmtree(s["root"], ignore_errors=True)
    try:  # Home's list of recent designs must not keep these made-up ones for a later scenario
        from sciforge import home_core, home_ui

        state = home_core.empty()
        state["merged_mru"] = True
        home_ui.save_state(state)
    except Exception as exc:
        print("[SciForge] readme_shots: Home's list was not cleared: %s" % exc, flush=True)


h.run(
    "readme_shots",
    [
        setup,
        make_designs,
        show_home,
        shoot_home,
        new_design,
        create_sketch,
        pick_xy,
        draw,
        shoot_sketch,
        finish_sketch,
        closed,
        open_example,
        shoot_timeline,
        box_for_presspull,
        press_pull,
        click_top,
        type_distance,
        shoot_presspull,
        cancel_presspull,
        open_ai_panel,
        click_ai,
        shoot_ai,
        tidy,
    ],
)
