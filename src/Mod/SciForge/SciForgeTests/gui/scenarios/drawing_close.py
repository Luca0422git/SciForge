# SPDX-License-Identifier: LGPL-2.1-or-later
"""Closing a drawing never takes the program down (Luca, 2026-10-16: "when I made a drawing
from a pre-existing body and close the drawing, the entire FreeCAD closes ... when i start
it up again, it says it didn't shut down correctly").

A crash ends the run before the result file is written, so every path below is a check.

A  A block (pre-existing body). File > New Drawing > OK: the drawing opens in its tab and
   the Base View dialog starts by itself. The drawing tab's close button (x) clicked while
   the Base View dialog is still open: the tab closes, the dialog with it, the design's tab
   is current again (SOLID shown), the Report view is clean.
B  The drawing opened again (double-click in the browser's Drawings folder); a base view
   placed and OK'd; the tab's x again: closed, back to the design.
C  Opened again; Window > Close (Ctrl+F4, FreeCAD's close of the current tab).
D  Opened again; the whole design closed (File > Close, nothing saved) while the drawing's
   tab is current; a new design afterwards works (a box extruded).
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import drawing_fixtures as fx
from SciForgeTests.gui import drawing_input as d
from SciForgeTests.gui import harness as h

state = {}


def mdi():
    return d.main_window().findChild(QtWidgets.QMdiArea)


def page_window():
    """The MDI sub-window that shows the drawing, or None."""
    area = mdi()
    if area is None:
        return None
    for sub in area.subWindowList():
        widget = sub.widget()
        if widget is not None and widget.metaObject().className() == "TechDrawGui::MDIViewPage":
            return sub
    return None


def tab_close_button(sub):
    """The x of the drawing's document tab (at the top, as a person clicks it)."""
    bar = h.document_tabs()
    if bar is None or sub is None:
        return None
    title = sub.windowTitle().replace("[*]", "").strip()
    for index in range(bar.count()):
        if bar.tabText(index).replace("[*]", "").strip() == title:
            for side in (QtWidgets.QTabBar.RightSide, QtWidgets.QTabBar.LeftSide):
                button = bar.tabButton(index, side)
                if button is not None:
                    return button
    return None


def click_tab_x():
    sub = page_window()
    if not h.check("the drawing's tab is there", sub is not None):
        return
    button = tab_close_button(sub)
    if h.check("its tab has a close button", button is not None):
        QtTest.QTest.mouseClick(button, QtCore.Qt.LeftButton)
        QtWidgets.QApplication.processEvents()


def closed(where):
    def step():
        h.check("%s: the drawing's tab is closed" % where, page_window() is None)
        h.check("%s: no drawing dialog left" % where, not Gui.Control.activeDialog())
        from sciforge import shell

        ribbon = shell.ribbon()
        h.check(
            "%s: back to the design (SOLID tab)" % where,
            ribbon is not None and d.ribbon_tab_shown("solid"),
        )
        h.check("%s: the design is still there" % where, App.ActiveDocument is not None)
        h.expect_no_errors("closing the drawing (%s)" % where)

    step.__name__ = "closed_" + where.replace(" ", "_")
    return step


def open_again():
    from sciforge import drawing, drawing_ui

    pages = drawing.drawings(App.ActiveDocument)
    if h.check("the drawing is still in the design", len(pages) == 1, pages):
        drawing_ui.open_drawing(pages[0])


open_again.wait_ms = 1500


def opened():
    h.check("the drawing's tab is open again", page_window() is not None)


# -- A ----------------------------------------------------------------------------------------
def new_design():
    s.new_design("CloseDrawing")()


def a_block():
    fx.block(App.ActiveDocument)
    h.fit()


def a_new_drawing():
    d.file_menu("New Drawing")


def a_ok():
    d.ok()


a_ok.wait_ms = 2500


def a_base_view_open():
    h.check("the drawing opened", page_window() is not None)
    h.check("the Base View dialog started by itself", d.panel_of("BaseViewPanel") is not None)
    d.move_to(120, 190)  # the view follows the mouse while the dialog waits


def a_close():
    click_tab_x()


a_close.wait_ms = 1500


# -- B ----------------------------------------------------------------------------------------
def b_base_view():
    if d.panel_of("BaseViewPanel") is None:
        h.ribbon("Base View")


b_base_view.wait_ms = 1500


def b_place():
    d.move_to(120, 190)
    d.click_at(130, 185)


def b_ok():
    p = d.panel_of("BaseViewPanel")
    if p is not None:
        d.ok()


b_ok.wait_ms = 1500


def b_placed():
    h.check("a base view on the drawing", len(d.bases()) >= 1, d.bases())


def b_close():
    click_tab_x()


b_close.wait_ms = 1500


# -- C ----------------------------------------------------------------------------------------
def c_ctrl_w():
    sub = page_window()
    if h.check("the drawing's tab is current", sub is not None):
        mdi().setActiveSubWindow(sub)
        QtWidgets.QApplication.processEvents()
        # Window > Close (Ctrl+F4): FreeCAD's command that closes the current tab
        Gui.runCommand("Std_CloseActiveWindow")
        QtWidgets.QApplication.processEvents()


c_ctrl_w.wait_ms = 1500


# -- D ----------------------------------------------------------------------------------------
def d_close_design():
    sub = page_window()
    if h.check("the drawing's tab is current before closing the design", sub is not None):
        mdi().setActiveSubWindow(sub)
        QtWidgets.QApplication.processEvents()
    name = App.ActiveDocument.Name
    state["closed"] = name
    Gui.ActiveDocument.Modified = False  # nothing to save: no "save changes?" question
    App.closeDocument(name)
    QtWidgets.QApplication.processEvents()


d_close_design.wait_ms = 2000


def d_after():
    h.check("the design is closed", state["closed"] not in App.listDocuments())
    h.check("no drawing tab left", page_window() is None)
    h.expect_no_errors("closing the design with its drawing open")


def d_new_design():
    s.new_design("AfterClose")()


def d_works():
    fx.block(App.ActiveDocument)
    App.ActiveDocument.recompute()
    body = App.ActiveDocument.getObject("Body")
    h.check("a new design works afterwards", body is not None and body.Shape.isValid())


h.run(
    "drawing_close",
    [
        new_design,
        a_block,
        a_new_drawing,
        a_ok,
        a_base_view_open,
        a_close,
        closed("A x with the Base View open"),
        open_again,
        opened,
        b_base_view,
        b_place,
        b_ok,
        b_placed,
        b_close,
        closed("B x after a view"),
        open_again,
        opened,
        c_ctrl_w,
        closed("C Window Close"),
        open_again,
        opened,
        d_close_design,
        d_after,
        d_new_design,
        d_works,
    ],
)
