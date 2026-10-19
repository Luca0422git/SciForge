# SPDX-License-Identifier: LGPL-2.1-or-later
"""FreeCAD's own tools, one click away (Luca, 2026-10-19: "there should be a way to
passthrough FreeCADs tools and workflow for those who can use both", so a gap or a bug of
SciForge never stops a project).

UTILITIES > FreeCAD Tools (and the app menu, the File menu): FreeCAD's workbenches (Part
Design, Part, TechDraw, FEM, CAM...). Choosing one switches to it: SciForge steps aside and
FreeCAD's own menus, toolbars and panels come back (shell.on_workbench), the open designs
stay open; they are FreeCAD documents. A small bar "Back to SciForge" stays at the top
while FreeCAD's interface is up, and FreeCAD's own workbench list has SciForge too.
"""

import FreeCADGui as Gui

from . import commands, log, ui_icon, ui_icon_path, warn
from .compat import QtCore, QtWidgets

SCIFORGE = "SciForgeWorkbench"
# not offered: SciForge itself, FreeCAD's empty one, and the Sketcher (SciForge's sketches
# use it: switching to it while SciForge is on is SciForge's own sketch mode)
SKIP = {SCIFORGE, "NoneWorkbench", "SketcherWorkbench"}
BAR = "SciForgeBackBar"
_state = {"told": False}


def workbenches():
    """[(name, menu text)] of FreeCAD's workbenches, by menu text."""
    found = []
    try:
        for name, workbench in Gui.listWorkbenches().items():
            if name in SKIP:
                continue
            text = str(getattr(workbench, "MenuText", "") or name.replace("Workbench", ""))
            found.append((name, text))
    except Exception as exc:
        warn("FreeCAD tools: %s" % exc)
    return sorted(found, key=lambda pair: pair[1].lower())


def switch(name):
    """Go to FreeCAD's workbench `name`: SciForge steps aside, the designs stay open."""
    try:
        Gui.activateWorkbench(name)
        log("FreeCAD tools: switched to %s" % name)
        show_back_bar()
        if not _state["told"]:
            _state["told"] = True
            commands.tell(
                "This is FreeCAD's own interface: all of its menus and tools. Your designs "
                "stay open. Back to SciForge: the button at the top left."
            )
        return True
    except Exception as exc:
        warn("FreeCAD tools: %s: %s" % (name, exc))
        commands.tell("FreeCAD's %s could not be opened: %s" % (name, exc))
        return False


def back():
    """Back to SciForge from FreeCAD's interface."""
    try:
        Gui.activateWorkbench(SCIFORGE)
        hide_back_bar()
        log("FreeCAD tools: back to SciForge")
    except Exception as exc:
        warn("FreeCAD tools: back: %s" % exc)


def menu(parent=None):
    """The menu of FreeCAD's workbenches (UTILITIES > FreeCAD Tools, the app menu)."""
    found = QtWidgets.QMenu("FreeCAD Tools", parent)
    found.setObjectName("SciForgeFreeCADMenu")
    found.setIcon(ui_icon("freecad_tools"))
    found.setToolTipsVisible(True)
    title = found.addAction("Switch to FreeCAD's interface:")
    title.setEnabled(False)
    for name, text in workbenches():
        action = found.addAction(text)
        action.setData(name)
        action.setToolTip("FreeCAD's %s with its own menus and toolbars" % text)
        action.triggered.connect(lambda *_a, n=name: QtCore.QTimer.singleShot(0, lambda: switch(n)))
    return found


# -- the bar back to SciForge -----------------------------------------------------------------------
def _main():
    return Gui.getMainWindow()


def back_bar():
    bar = _main().findChild(QtWidgets.QToolBar, BAR)
    if bar is None:
        bar = QtWidgets.QToolBar("Back to SciForge", _main())
        bar.setObjectName(BAR)
        bar.setMovable(False)
        bar.toggleViewAction().setVisible(False)  # not listed, never saved as hidden
        button = QtWidgets.QToolButton()
        button.setObjectName("SciForgeBackButton")
        button.setText("Back to SciForge")
        button.setIcon(ui_icon("qa_home"))
        button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        button.setToolTip("Leave FreeCAD's interface: SciForge's ribbon, browser and timeline")
        button.clicked.connect(lambda *_: QtCore.QTimer.singleShot(0, back))
        bar.addWidget(button)
        _main().addToolBar(QtCore.Qt.TopToolBarArea, bar)
        _main().insertToolBarBreak(bar)
    return bar


def show_back_bar():
    try:
        back_bar().show()
    except Exception as exc:
        warn("FreeCAD tools: %s" % exc)


def hide_back_bar():
    try:
        bar = _main().findChild(QtWidgets.QToolBar, BAR)
        if bar is not None:
            bar.hide()
    except Exception as exc:
        warn("FreeCAD tools: %s" % exc)


def follow(name):
    """Every workbench change (shell): the bar back shows in FreeCAD's interface only."""
    if str(name) in (SCIFORGE, "SketcherWorkbench"):
        hide_back_bar()
    elif str(name) and str(name) != "NoneWorkbench":
        show_back_bar()


class FreeCADToolsCommand:
    def GetResources(self):
        return {
            "MenuText": "FreeCAD Tools",
            "ToolTip": "All of FreeCAD's tools: switch to one of its workbenches (Part Design, "
            "Part, TechDraw, FEM...). Your designs stay open; Back to SciForge returns.",
            "Pixmap": ui_icon_path("freecad_tools"),
        }

    def IsActive(self):
        return True

    def Activated(self):
        try:
            from .compat import QtGui

            menu(_main()).exec_(QtGui.QCursor.pos())
        except Exception as exc:
            warn("FreeCAD Tools: %s" % exc)


class BackCommand:
    def GetResources(self):
        return {
            "MenuText": "Back to SciForge",
            "ToolTip": "Leave FreeCAD's interface: SciForge's ribbon, browser and timeline",
            "Pixmap": ui_icon_path("qa_home"),
        }

    def IsActive(self):
        return True

    def Activated(self):
        back()


COMMANDS = {"SciForge_FreeCADTools": FreeCADToolsCommand, "SciForge_BackToSciForge": BackCommand}
