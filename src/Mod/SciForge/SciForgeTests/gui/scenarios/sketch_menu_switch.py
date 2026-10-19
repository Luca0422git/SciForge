# SPDX-License-Identifier: LGPL-2.1-or-later
"""Right click inside a sketch shows the sketch's own marking menu, also after switching to
another program and back while the sketch is open (Fusion: the sketch menu whenever a
sketch is open).

Luca saw the part menu in a sketch. Two right-click filters sit on the 3D view (the part
menu's and the sketch's); Qt asks the one installed last first, and switching to another
program and back installed the part filter again, in front of the sketch's.

A  New design, Create Sketch on XY, right click: the sketch menu.
B  Leave SciForge for another program and come back (what Qt does then), right click:
   still the sketch menu, twice.
C  The design's window is activated again (another design tab and back): still the sketch
   menu.
E  A second design while the sketch stays open in the first: right click in its view gives
   the part menu; back in the first design's tab, the sketch menu again.
D  Finish Sketch from the menu, right click: the part menu.
"""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import sketch_input as si

V = App.Vector
EMPTY = V(45, 45, 0)  # empty space of the XY plane, away from everything
SKETCH_ONLY = {"Finish Sketch", "Line"}
PART_ONLY = {"Hole", "Press Pull", "Create Sketch"}
st = {}


def right_click():
    h.click(EMPTY, button=QtCore.Qt.RightButton)


def close_menu():
    menu = si.marking_menu()
    if menu is not None:
        QtTest.QTest.keyClick(menu, QtCore.Qt.Key_Escape)
        QtWidgets.QApplication.processEvents()


def check_sketch_menu(label):
    labels = si.marking_labels()
    h.check("%s: a marking menu opens" % label, si.marking_menu() is not None, labels)
    h.check("%s: it is the sketch menu" % label, SKETCH_ONLY <= set(labels), labels)
    h.check("%s: no part commands in it" % label, not PART_ONLY & set(labels), labels)


def a_new():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("SketchMenuSwitch")
    h.fit()
    # xvfb has no window manager: make the main window the active one, as on a desktop.
    QtWidgets.QApplication.setActiveWindow(Gui.getMainWindow())


def a_create():
    h.ribbon("Create Sketch")


def a_pick():
    pl.click_on_plane(V(12, -8, 0))


def a_open():
    st["sk"] = h.in_sketch()
    h.check("A: sketch open on XY", st["sk"] is not None)
    right_click()


def a_menu():
    check_sketch_menu("A")
    h.shot("A-sketch-menu")
    close_menu()


def b_switch_away():
    area = Gui.getMainWindow().findChild(QtWidgets.QMdiArea)
    st["activated"] = 0

    def count(*_):
        st["activated"] += 1

    st["count"] = count
    area.subWindowActivated.connect(count)
    app = QtWidgets.QApplication.instance()
    # What Qt does when the user switches to another program and back.
    QtWidgets.QApplication.sendEvent(app, QtCore.QEvent(QtCore.QEvent.ApplicationDeactivate))
    QtWidgets.QApplication.setActiveWindow(None)


def b_switch_back():
    app = QtWidgets.QApplication.instance()
    QtWidgets.QApplication.sendEvent(app, QtCore.QEvent(QtCore.QEvent.ApplicationActivate))
    QtWidgets.QApplication.setActiveWindow(Gui.getMainWindow())


def b_right_click():
    area = Gui.getMainWindow().findChild(QtWidgets.QMdiArea)
    try:
        area.subWindowActivated.disconnect(st["count"])
    except Exception:
        pass
    h.check("B: coming back activated the design's window", st["activated"] >= 1, st["activated"])
    h.check("B: the sketch is still open", h.in_sketch() is st["sk"])
    right_click()


def b_menu():
    check_sketch_menu("B")
    h.shot("B-sketch-menu-after-switch")
    close_menu()
    right_click()


def b_menu_again():
    check_sketch_menu("B (second right click)")
    close_menu()
    # The design's window is activated again (as after another design tab and back).
    area = Gui.getMainWindow().findChild(QtWidgets.QMdiArea)
    area.subWindowActivated.emit(area.activeSubWindow())


def c_right_click():
    right_click()


def c_menu():
    check_sketch_menu("C")
    close_menu()
    # E: a second design while the sketch stays open in the first
    App.newDocument("SketchMenuOther")
    h.fit()


def e_other_view():
    right_click()


def e_part_menu():
    labels = si.marking_labels()
    h.check("E: the other design's view gives a menu", si.marking_menu() is not None, labels)
    h.check("E: it is the part menu (the sketch is in the other design)", "Create Sketch" in labels, labels)
    h.check("E: no Finish Sketch there", "Finish Sketch" not in labels, labels)
    close_menu()
    area = Gui.getMainWindow().findChild(QtWidgets.QMdiArea)
    for sub in area.subWindowList():
        if "SketchMenuSwitch" in sub.windowTitle():
            area.setActiveSubWindow(sub)  # back to the first design's tab
    QtWidgets.QApplication.processEvents()


def e_back():
    right_click()


def e_sketch_menu_again():
    check_sketch_menu("E (back in the sketch's design)")
    si.marking_slot("Finish Sketch")


def d_right_click():
    h.check("D: Finish Sketch from the menu closed the sketch", h.in_sketch() is None)
    right_click()


def d_menu():
    labels = si.marking_labels()
    h.check("D: a marking menu opens", si.marking_menu() is not None, labels)
    h.check("D: outside the sketch it is the part menu", "Create Sketch" in labels, labels)
    h.check("D: no Finish Sketch outside a sketch", "Finish Sketch" not in labels, labels)
    h.shot("D-part-menu")
    close_menu()


h.run(
    "sketch_menu_switch",
    [
        a_new,
        a_create,
        a_pick,
        a_open,
        a_menu,
        b_switch_away,
        b_switch_back,
        b_right_click,
        b_menu,
        b_menu_again,
        c_right_click,
        c_menu,
        e_other_view,
        e_part_menu,
        e_back,
        e_sketch_menu_again,
        d_right_click,
        d_menu,
    ],
)
