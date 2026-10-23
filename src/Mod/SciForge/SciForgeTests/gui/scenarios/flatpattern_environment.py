# SPDX-License-Identifier: LGPL-2.1-or-later
"""The FLAT PATTERN environment and the design around it, real input only: Create Flat
Pattern on an L bracket opens it; Ctrl+Z there takes the flat pattern away and closes the
environment (the design's tabs, the folded part shown); Ctrl+Y brings the flat pattern back.
Opened again from the browser, the design is saved (Ctrl+S, a version description) while the
flat pattern is open: it stays open, and the file keeps the folded part shown. Closing the
design closes the environment; reopened, the folded part is shown, the flat pattern hidden,
and the FLAT PATTERN tab opens again with a double-click."""

import os

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import flatpattern_steps as fs
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import versions_input as vi

s = {}


def setup():
    fs.setup_l("FlatEnv")
    s["path"] = os.path.join(fs.out_dir(), "flat_env.FCStd")
    if os.path.exists(s["path"]):
        os.remove(s["path"])
    App.ActiveDocument.saveAs(s["path"])
    fs.tab("sheet_metal")


def create():
    Gui.Selection.clearSelection()
    h.ribbon("Create Flat Pattern")


def click_top():
    h.fit()
    h.click(fs.L_TOP)


def press_ok():
    fs.settle()
    fs.ok()


def in_env():
    fs.settle()
    h.check("FLAT PATTERN open", fs.current_tab() == "flat_pattern", fs.current_tab())
    h.check("folded part hidden", not fs.body().ViewObject.Visibility)


def undo():
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def undone():
    fs.settle()
    h.check("Ctrl+Z takes the flat pattern away", fs.flat_patterns() == [])
    h.check("and closes the FLAT PATTERN tab", fs.current_tab() != "flat_pattern", fs.current_tab())
    h.check("FLAT PATTERN tab hidden", not fs.tab_visible("flat_pattern"))
    h.check("SOLID tab back", fs.tab_visible("solid"))
    h.check("folded part shown", fs.body().ViewObject.Visibility)


def redo():
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def redone():
    fs.settle()
    h.check("Ctrl+Y brings the flat pattern back", len(fs.flat_patterns()) == 1)


def open_row():
    h.check("browser row double-clicked", fs.double_click_browser("Flat Pattern"))


def opened():
    fs.settle()
    h.check("open again", fs.current_tab() == "flat_pattern", fs.current_tab())


def ctrl_s():
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


def describe():
    h.check("the Save dialog asks for a version description", vi.version_dialog() is not None)
    vi.accept_save()


def saved_open():
    fs.settle()
    h.check("saved", not App.ActiveDocument.isTouched())
    h.check("still in the flat pattern after saving", fs.current_tab() == "flat_pattern")
    h.check("folded part still hidden", not fs.body().ViewObject.Visibility)
    h.check("flat still shown", fs.flat().ViewObject.Visibility)


def close():
    App.closeDocument(App.ActiveDocument.Name)


def closed():
    fs.settle()
    h.check("closing the design closes the environment", fs.current_tab() != "flat_pattern")
    h.check("FLAT PATTERN tab hidden", not fs.tab_visible("flat_pattern"))


def reopen():
    App.openDocument(s["path"])
    h.fit()


def reopened():
    from sciforge import bodies

    body = bodies.list_bodies(App.ActiveDocument)[0]
    fs.STATE["body"] = body
    h.check("reopened: the folded part shown", body.ViewObject.Visibility)
    fp = fs.flat()
    h.check("reopened: the flat pattern hidden", fp is not None and not fp.ViewObject.Visibility)


def open_again():
    h.check("browser row double-clicked", fs.double_click_browser("Flat Pattern"))


def opened_again():
    fs.settle()
    h.check("opens again after reopening", fs.current_tab() == "flat_pattern", fs.current_tab())
    bb = fs.flat_box()
    h.check("still 98.26195 long", bb is not None and fs.close(bb.XLength, fs.L_FLAT), bb)


def finish():
    h.ribbon("Finish Flat Pattern")


def done():
    h.check("back to the folded part", fs.body().ViewObject.Visibility)


h.run(
    "flatpattern_environment",
    [
        setup,
        create,
        click_top,
        press_ok,
        in_env,
        undo,
        undone,
        redo,
        redone,
        open_row,
        opened,
        ctrl_s,
        describe,
        saved_open,
        close,
        closed,
        reopen,
        reopened,
        open_again,
        opened_again,
        finish,
        done,
    ],
)
