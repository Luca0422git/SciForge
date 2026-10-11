# SPDX-License-Identifier: LGPL-2.1-or-later
"""No FreeCAD overlay title over the 3D view (Fusion shows only the command dialog).

FreeCAD 1.1 floats the Tasks panel over the 3D view with a title bar of its own: an
empty "Tasks" header with three small buttons stayed over the view when no command was
open, and a white strip sat above every dialog. Checked with nothing open, while Press
Pull waits for a face, and after Cancel; the dialog itself must still show and work."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtWidgets

from SciForgeTests.gui import harness as h


def in_overlay(widget):
    parent = widget.parentWidget()
    while parent is not None:
        if parent.metaObject().className() in ("Gui::OverlayTabWidget", "Gui::OverlaySplitter"):
            return True
        parent = parent.parentWidget()
    return False


def titles():
    """Title bars over the 3D view (in FreeCAD's overlay) that take up room on screen."""
    found = []
    for w in Gui.getMainWindow().findChildren(QtWidgets.QWidget):
        if w.metaObject().className() == "Gui::OverlayTitleBar" and w.isVisible():
            if w.height() > 0 and in_overlay(w):
                found.append(w.geometry().getRect())
    return found


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("OverlayTitle")
    h.fit()


def browser_header():
    """The BROWSER panel is docked, not over the view: its header stays."""
    from sciforge import browser_ui

    dock = browser_ui._state.get("dock")
    bar = dock.titleBarWidget() if dock is not None else None
    return bar is None or (bar.isVisible() and bar.height() > 0)


def nothing_open():
    h.check("no overlay title with nothing open", not titles(), titles())
    h.check("the BROWSER header is still there", browser_header())
    h.shot("1-nothing-open")


def start_press_pull():
    h.click_empty()
    h.press("q")


def dialog_open():
    h.check("Press Pull dialog open", bool(Gui.Control.activeDialog()))
    h.check("no overlay title above the dialog", not titles(), titles())
    h.check("the BROWSER header is still there", browser_header())
    h.shot("2-dialog")
    h.task_button("Cancel")


def closed():
    h.check("Cancel closed the dialog", not Gui.Control.activeDialog())
    h.check("no overlay title after Cancel", not titles(), titles())


h.run("overlay_title", [new_design, nothing_open, start_press_pull, dialog_open, closed])
