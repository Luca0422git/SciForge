# SPDX-License-Identifier: LGPL-2.1-or-later
"""FreeCAD's own tools from SciForge (Luca, 2026-10-19: "there should be a way to
passthrough FreeCADs tools and workflow"), with real clicks.

Path 1, UTILITIES > FreeCAD Tools lists FreeCAD's workbenches; Part Design switches to it:
  FreeCAD's menu bar and toolbars, no ribbon, the design still open, a Back to SciForge
  bar at the top.
Path 2, Back to SciForge: the ribbon, browser and timeline again, the bar gone, the same
  design open.
Path 3, the app menu (the lines at the top left) has FreeCAD Tools too.
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtWidgets

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import widget_input as wi

s = {}


def big(label):
    for button in h.ribbon_buttons():
        if button.objectName() == "SciForgeBig_" + label.replace(" ", "_"):
            return button
    return None


def back_bar():
    return Gui.getMainWindow().findChild(QtWidgets.QToolBar, "SciForgeBackBar")


# -- Path 1 -------------------------------------------------------------------------------
def setup():
    from sciforge import commands, shell

    doc = App.newDocument("PassThrough")
    commands.ensure_body()
    s["doc"] = doc.Name
    wi.click(shell.ribbon().tab_buttons["utilities"])


def open_freecad_tools():
    button = big("FreeCAD Tools")
    h.check("UTILITIES has FreeCAD Tools", button is not None)
    if button is None:
        return
    h.check("... choosing Part Design", wi.click_menu(button, "Part Design"))


open_freecad_tools.wait_ms = 1500


def in_freecad():
    from sciforge import shell

    h.check(
        "FreeCAD's Part Design is active", Gui.activeWorkbench().name() == "PartDesignWorkbench"
    )
    h.check("SciForge stepped aside", not shell.is_on())
    h.check("FreeCAD's menu bar is back", Gui.getMainWindow().menuBar().isVisible())
    ribbon = Gui.getMainWindow().findChild(QtWidgets.QToolBar, "SciForgeRibbonBar")
    h.check("no ribbon", ribbon is None or not ribbon.isVisible())
    h.check("the design is still open", s["doc"] in App.listDocuments())
    bar = back_bar()
    h.check("a Back to SciForge bar at the top", bar is not None and bar.isVisible())
    h.shot("freecad")
    button = bar.findChild(QtWidgets.QToolButton, "SciForgeBackButton") if bar else None
    h.check("... with its button", button is not None and button.text() == "Back to SciForge")
    if button is not None:
        wi.click(button)


in_freecad.wait_ms = 1500


# -- Path 2 -------------------------------------------------------------------------------
def back_in_sciforge():
    from sciforge import shell

    h.check("Back to SciForge: SciForge is on", shell.is_on())
    ribbon = Gui.getMainWindow().findChild(QtWidgets.QToolBar, "SciForgeRibbonBar")
    h.check("... its ribbon shown", ribbon is not None and ribbon.isVisible())
    h.check("... the bar gone", back_bar() is None or not back_bar().isVisible())
    h.check("... the same design open", s["doc"] in App.listDocuments())
    h.check("FreeCAD's menu bar hidden again", not Gui.getMainWindow().menuBar().isVisible())


back_in_sciforge.wait_ms = 1500


# -- Path 3 -------------------------------------------------------------------------------
def app_menu_has_it():
    from sciforge import freecad_tools_ui

    menu = freecad_tools_ui.menu()
    texts = [a.text() for a in menu.actions()]
    h.check("FreeCAD Tools lists Part Design", "Part Design" in texts, texts)
    h.check("... but not SciForge itself", "SciForge" not in texts, texts)
    button = wi.quick_access("Menu") or wi.quick_access("File")
    found = {}
    if button is not None:
        from PySide import QtCore

        def read():
            popup = QtWidgets.QApplication.activePopupWidget()
            if popup is not None:
                found["texts"] = [a.text() for a in popup.actions()]
                popup.close()
            elif found.get("tries", 0) < 20:
                found["tries"] = found.get("tries", 0) + 1
                QtCore.QTimer.singleShot(50, read)

        QtCore.QTimer.singleShot(50, read)
        wi.click(button)
    h.check(
        "the app menu has FreeCAD Tools",
        "FreeCAD Tools" in found.get("texts", []),
        found.get("texts"),
    )
    h.check("no pop-up left", not h.popups(), h.popups())


h.run(
    "freecad_tools",
    [setup, open_freecad_tools, in_freecad, back_in_sciforge, app_menu_has_it],
)
