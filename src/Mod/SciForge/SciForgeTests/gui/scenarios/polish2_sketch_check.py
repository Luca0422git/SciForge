# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's floating green check while drawing in a sketch (polish-2, plan item 0a).

Fusion (Autodesk's help "Create lines in a sketch", the sketch basics course): while a
chain of lines is drawn a small green check floats beside its last point; a click on it
ends the chain and the Line tool stays on for a new first point (Esc leaves the tool).
The splines show the same check once they have two points: it makes the spline and the
tool stays on.

A  L, two clicks: one line, the chain goes on and the check floats beside its end (down
   right, a few pixels off), on top of the view (a click there reaches the check).
B  The view zoomed: the check follows the end point.
C  A click on the check: the chain ends (no line from the old end), the Line tool stays on;
   the check is gone until the next chain has a line. Two more clicks make a line of
   their own. Ctrl+Z takes that line back.
D  Esc: the tool stops and the check goes.
E  Fit Point Spline: three clicks show the check; a click on it makes the spline and the
   tool stays on (Esc ends it).
F  Finish Sketch: no check is left over the view.
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import sketch_input as si

V = App.Vector
s = {}


def session():
    from sciforge import sketch_mode

    return sketch_mode.current()


def check_button():
    from sciforge import sketch_check

    gl = h.gl_widget()
    for button in gl.findChildren(QtWidgets.QAbstractButton, sketch_check.NAME):
        if button.isVisible():
            return button
    return None


def chain():
    se = session()
    return se.line if se is not None else None


def count():
    return len(s["sk"].Geometry)


def end_pixel(point):
    return h.screen_point(s["sk"].getGlobalPlacement().multVec(point))


def press_check():
    button = check_button()
    if not h.check("the check is there to click", button is not None):
        return False
    centre = button.rect().center()
    QtTest.QTest.mouseMove(button, centre)
    QtTest.QTest.mouseClick(button, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, centre)
    QtWidgets.QApplication.processEvents()
    return True


# -- setup ----------------------------------------------------------------------------------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Polish2Check")
    h.fit()
    Gui.getMainWindow().activateWindow()


def create_sketch():
    h.ribbon("Create Sketch")


def pick_xy():
    pl.click_square("XY_Plane")  # where the square shows (was 12, -8, 0)


def opened():
    s["sk"] = h.in_sketch()
    h.check("sketch open on XY", s["sk"] is not None)
    h.check("no check before anything is drawn", check_button() is None)


# -- A: the check beside the chain's end ----------------------------------------------------
def a_l():
    h.press("l")


def a_p1():
    si.click(V(0, 0, 0))


def a_p2():
    si.click(V(40, 0, 0))


def a_shown():
    h.check("A: one line", count() == 1, count())
    h.check("A: the chain goes on", chain() is not None and chain().current is not None)
    button = check_button()
    if not h.check("A: the green check shows", button is not None):
        return
    end = end_pixel(V(40, 0, 0))
    centre = button.geometry().center()
    dx, dy = centre.x() - end.x(), centre.y() - end.y()
    h.check(
        "A: beside the end point, down and to the right", 8 <= dx <= 40 and 8 <= dy <= 40, (dx, dy)
    )
    on_top = QtWidgets.QApplication.widgetAt(h.gl_widget().mapToGlobal(centre))
    h.check(
        "A: a click there reaches the check",
        on_top is button,
        on_top.objectName() if on_top is not None else None,
    )
    h.check("A: the check does not take the keyboard", not button.hasFocus())
    s["dx"] = dx
    h.shot("A-check")


# -- B: zoomed, it follows --------------------------------------------------------------------
def b_zoom():
    Gui.SendMsgToActiveView("ViewFit")
    h.view().zoomOut()


def b_follows():
    button = check_button()
    if not h.check("B: still shown after zooming", button is not None):
        return
    end = end_pixel(V(40, 0, 0))
    centre = button.geometry().center()
    dx, dy = centre.x() - end.x(), centre.y() - end.y()
    h.check("B: it followed the end point", 8 <= dx <= 40 and 8 <= dy <= 40, (dx, dy))


# -- C: a click on the check ends the chain ----------------------------------------------
def c_click():
    s["before"] = count()
    press_check()


def c_ended():
    c = chain()
    h.check("C: no new line from the click", count() == s["before"], count())
    h.check(
        "C: the chain ended",
        c is not None and c.current is None,
        c.current if c is not None else None,
    )
    h.check("C: the Line tool stays on", c is not None and c.active and si.drawing())
    h.check("C: the check went with the chain", check_button() is None)


def c_p1():
    si.click(V(0, 20, 0))


def c_p2():
    si.click(V(30, 20, 0))


def c_new_line():
    h.check("C: two clicks make a line of their own", count() == s["before"] + 1, count())
    g = s["sk"].Geometry[-1]
    start = V(g.StartPoint)
    h.check(
        "C: it starts at the new click, not at the old end",
        (start - V(0, 20, 0)).Length < 1.0,
        tuple(start),
    )
    h.check("C: the check shows for the new chain", check_button() is not None)
    si.key(QtCore.Qt.Key_Escape)


def c_undo():
    h.check("C: Esc stopped the tool", not si.drawing())
    # Undo on the application bar until the line is gone (FreeCAD records its coincidence
    # and the line as separate steps)
    from SciForgeTests.gui import dialog_input

    for _ in range(3):
        if count() <= s["before"]:
            break
        h.check("C: Undo button", dialog_input.quick_access("Undo"))


def c_undone():
    h.check("C: Ctrl+Z takes the new line back", count() == s["before"], count())


# -- D: Esc removes the check -----------------------------------------------------------------
def d_l():
    h.press("l")


def d_p1():
    si.click(V(0, -20, 0))


def d_p2():
    si.click(V(25, -20, 0))


def d_esc():
    h.check("D: the check shows while drawing", check_button() is not None)
    si.key(QtCore.Qt.Key_Escape)


def d_gone():
    h.check("D: Esc: the tool is off", not si.drawing())
    h.check("D: Esc: no check", check_button() is None)
    s["lines"] = count()


# -- E: a spline --------------------------------------------------------------------------------
def e_spline():
    si.menu_item("CREATE", "Fit Point Spline")


def e_p1():
    si.click(V(-30, 30, 0))


def e_p2():
    si.click(V(-15, 45, 0))


def e_no_check_yet():
    s["spline_before"] = count()


def e_p3():
    si.click(V(0, 33, 0))


def e_shown():
    h.check("E: the check shows on a spline being drawn", check_button() is not None)
    h.shot("E-spline-check")
    press_check()


def e_made():
    splines = [g for g in s["sk"].Geometry if g.TypeId == "Part::GeomBSplineCurve"]
    h.check("E: the check made the spline", len(splines) == 1, [g.TypeId for g in s["sk"].Geometry])
    h.check("E: the spline tool stays on", si.drawing())
    h.check("E: the check went with it", check_button() is None)
    si.key(QtCore.Qt.Key_Escape)


def e_off():
    h.check("E: Esc ends the spline tool", not si.drawing())


# -- F: finish the sketch ------------------------------------------------------------------------
def f_finish():
    h.ribbon("Finish Sketch")


def f_none():
    h.check("F: the sketch is closed", h.in_sketch() is None)
    from sciforge import sketch_check

    left = h.gl_widget().findChildren(QtWidgets.QAbstractButton, sketch_check.NAME)
    h.check("F: no check left over the view", not [b for b in left if b.isVisible()], len(left))


STEPS = [
    new_design,
    create_sketch,
    pick_xy,
    opened,
    a_l,
    a_p1,
    a_p2,
    a_shown,
    b_zoom,
    b_follows,
    c_click,
    c_ended,
    c_p1,
    c_p2,
    c_new_line,
    c_undo,
    c_undone,
    d_l,
    d_p1,
    d_p2,
    d_esc,
    d_gone,
    e_spline,
    e_p1,
    e_p2,
    e_no_check_yet,
    e_p3,
    e_shown,
    e_made,
    e_off,
    f_finish,
    f_none,
]


h.run("polish2_sketch_check", si.watched(STEPS))
