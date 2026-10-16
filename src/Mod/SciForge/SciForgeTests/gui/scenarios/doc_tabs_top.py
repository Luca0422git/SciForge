# SPDX-License-Identifier: LGPL-2.1-or-later
"""The open documents as tabs at the top, like Fusion (Luca, 2026-10-16: "the toolbar where
open documents sit should be at the top. like fusion"). Only real input on the tabs.

A  Two designs open (Alpha, then Beta): the top bar shows a tab for each (and FreeCAD's start
   page if it is open), Beta's current; FreeCAD's tab bar under the 3D view is hidden; the 3D
   view reaches down to the timeline (nothing under it).
B  A click on Alpha's tab: Alpha is the active design; its tab is the current one.
C  Beta's x: Beta closes (no question: nothing changed); one design tab left.
D  Another workbench (SciForge off): FreeCAD's own tab bar under the view is back; SciForge
   on again: hidden again, the tabs at the top show Alpha.
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h

s = {}


def top():
    from sciforge import shell

    return shell.ribbon().doc_tabs


def mdi_bar():
    from sciforge import doc_tabs

    return doc_tabs.mdi_tabs()


def texts():
    bar = top()
    bar.sync()
    return [bar.tabText(i) for i in range(bar.count())]


def index_of(start):
    for i, text in enumerate(texts()):
        if text.startswith(start):
            return i
    return -1


def a_two_designs():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Alpha")
    App.newDocument("Beta")
    QtWidgets.QApplication.processEvents()


a_two_designs.wait_ms = 1200


def a_tabs():
    names = texts()
    h.check("a tab for Alpha", index_of("Alpha") >= 0, names)
    h.check("a tab for Beta", index_of("Beta") >= 0, names)
    h.check("Beta's tab is current", top().currentIndex() == index_of("Beta"), names)
    h.check(
        "the tabs are in the top bar",
        top().isVisible() and top().mapTo(Gui.getMainWindow(), QtCore.QPoint(0, 0)).y() < 80,
    )
    bar = mdi_bar()
    h.check("FreeCAD's tab bar under the 3D view is hidden", bar is None or not bar.isVisible())
    h.shot("a-tabs")


def b_click_alpha():
    bar = top()
    i = index_of("Alpha")
    if h.check("Alpha's tab", i >= 0, texts()):
        QtTest.QTest.mouseClick(
            bar, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, bar.tabRect(i).center()
        )
        QtWidgets.QApplication.processEvents()


def b_alpha_active():
    h.check(
        "Alpha is the active design", App.ActiveDocument.Name == "Alpha", App.ActiveDocument.Name
    )
    h.check("its tab is current", top().currentIndex() == index_of("Alpha"))


def c_close_beta():
    bar = top()
    i = index_of("Beta")
    if not h.check("Beta's tab", i >= 0, texts()):
        return
    button = bar.tabButton(i, QtWidgets.QTabBar.RightSide) or bar.tabButton(
        i, QtWidgets.QTabBar.LeftSide
    )
    if h.check("Beta's tab has an x", button is not None):
        QtTest.QTest.mouseClick(button, QtCore.Qt.LeftButton)
        QtWidgets.QApplication.processEvents()


c_close_beta.wait_ms = 1000


def c_closed():
    h.check("Beta is closed", "Beta" not in App.listDocuments(), list(App.listDocuments()))
    h.check("no tab for Beta", index_of("Beta") < 0, texts())
    h.check("Alpha's tab stays", index_of("Alpha") >= 0, texts())


def d_other_workbench():
    Gui.activateWorkbench("PartDesignWorkbench")
    QtWidgets.QApplication.processEvents()


d_other_workbench.wait_ms = 1200


def d_freecad_bar():
    bar = mdi_bar()
    h.check("SciForge off: FreeCAD's tab bar is back", bar is not None and bar.isVisible())
    Gui.activateWorkbench("SciForgeWorkbench")
    QtWidgets.QApplication.processEvents()


d_freecad_bar.wait_ms = 1200


def d_back():
    bar = mdi_bar()
    h.check("SciForge on: hidden again", bar is None or not bar.isVisible())
    h.check("the top tabs show Alpha", index_of("Alpha") >= 0, texts())


h.run(
    "doc_tabs_top",
    [
        a_two_designs,
        a_tabs,
        b_click_alpha,
        b_alpha_active,
        c_close_beta,
        c_closed,
        d_other_workbench,
        d_freecad_bar,
        d_back,
    ],
)
