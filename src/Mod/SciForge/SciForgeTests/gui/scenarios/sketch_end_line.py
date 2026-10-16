# SPDX-License-Identifier: LGPL-2.1-or-later
"""Ending a line (and any sketch tool) the way Fusion does (Luca, 2026-10-13: "there's no
way to end a line when sketching. there should be an OK and Cancel option on the right
click radial menu").

Fusion (Autodesk's sketch basics course and "Create lines" help, forum answers): Esc exits
the Line command; the green check or a double-click on the end point ends the chain and
stays in the Line tool; a line that ends on existing geometry ends the chain too; Enter
completes the tool; the right-click marking menu has OK at 3 o'clock and Cancel at 9 o'clock
while a command is active.

A  L, two clicks (one line, the chain goes on). Right click: OK at 3 o'clock, Cancel at 9,
   both enabled. OK: the tool is off, the line stays, the sketch is open.
B  L, two clicks, right click, Cancel: the tool is off, the line stays.
C  L, two clicks, Enter (nothing typed): the tool is off, the line stays.
D  L, one click, pointer moved, 25 typed, Enter: a 25 mm line is drawn and the tool goes
   on (a typed value still draws the shape). Esc.
E  L, two clicks, double-click on the end point: the chain ends, the tool stays on; two
   more clicks make a line of their own (not from the old end). Esc.
F  L, click, click on an existing line's end point: the chain ends there, the tool stays
   on; two more clicks make a line of their own. Esc.
G  Right click with no tool running: no OK / Cancel (Line and Sketch Dimension there).
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import sketch_input as si

V = App.Vector
EMPTY = V(55, 20, 0)
s = {}


def menu():
    return si.marking_menu()


def close_menu():
    m = menu()
    if m is not None:
        QtTest.QTest.keyClick(m, QtCore.Qt.Key_Escape)
        QtWidgets.QApplication.processEvents()


def chain():
    from sciforge import sketch_mode

    session = sketch_mode.current()
    return session.line if session is not None else None


def count():
    return len(s["sk"].Geometry)


def line_at(index):
    g = s["sk"].Geometry[index]
    return App.Vector(g.StartPoint), App.Vector(g.EndPoint)


def all_lines():
    out = []
    for i, g in enumerate(s["sk"].Geometry):
        try:
            out.append(
                (
                    i,
                    tuple(round(v, 2) for v in g.StartPoint),
                    tuple(round(v, 2) for v in g.EndPoint),
                )
            )
        except Exception:
            out.append((i, g.TypeId))
    return out


CLICK = 0.5  # mm: a click lands within a pixel of the aimed point


def right_click():
    h.click(EMPTY, button=QtCore.Qt.RightButton)


# -- setup ----------------------------------------------------------------------------------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("SketchEndLine")
    h.fit()
    QtWidgets.QApplication.setActiveWindow(Gui.getMainWindow())


def create_sketch():
    h.ribbon("Create Sketch")


def pick_xy():
    pl.click_square("XY_Plane")  # where the square shows (was 12, -8, 0)


def opened():
    s["sk"] = h.in_sketch()
    h.check("sketch open on XY", s["sk"] is not None)


# -- A: right click, OK ------------------------------------------------------------------
def a_l():
    h.press("l")


def a_p1():
    si.click(V(0, 0, 0))


def a_p2():
    si.click(V(40, 0, 0))


def a_drawn():
    h.check("A: one line", count() == 1, count())
    h.check("A: the chain goes on (tool running)", si.drawing() and chain().active)
    right_click()


def a_menu():
    m = menu()
    h.check("A: the sketch menu opens while drawing", m is not None, si.marking_labels())
    if m is None:
        return
    h.check("A: OK at 3 o'clock", m.slots[2].text() == "OK", m.slots[2].text())
    h.check("A: OK enabled", m.slots[2].isEnabled())
    h.check("A: Cancel at 9 o'clock", m.slots[6].text() == "Cancel", m.slots[6].text())
    h.check("A: Cancel enabled", m.slots[6].isEnabled())
    h.check("A: Finish Sketch still there", m.slots[4].text() == "Finish Sketch", m.slots[4].text())
    h.shot("A-ok-cancel")
    si.marking_slot("OK")


def a_after_ok():
    h.check("A: OK ended the tool", not si.drawing() and not chain().active)
    h.check("A: the line stays", count() == 1, count())
    h.check("A: the sketch is still open", h.in_sketch() is s["sk"])
    h.check("A: the menu is closed", menu() is None)
    h.check("A: no pop-up", not h.popups(), h.popups())


# -- B: right click, Cancel ---------------------------------------------------------------
def b_l():
    h.press("l")


def b_p1():
    si.click(V(0, 5, 0))


def b_p2():
    si.click(V(40, 5, 0))


def b_drawn():
    h.check("B: two lines", count() == 2, count())
    h.check("B: the chain goes on", si.drawing() and chain().active)
    right_click()


def b_menu():
    m = menu()
    h.check("B: menu opens", m is not None, si.marking_labels())
    if m is None:
        return
    h.check("B: Cancel at 9 o'clock", m.slots[6].text() == "Cancel", m.slots[6].text())
    si.marking_slot("Cancel")


def b_after_cancel():
    h.check("B: Cancel ended the tool", not si.drawing() and not chain().active)
    h.check("B: the lines stay", count() == 2, count())
    h.check("B: the sketch is still open", h.in_sketch() is s["sk"])


# -- C: Enter with nothing typed ------------------------------------------------------------
def c_l():
    h.press("l")


def c_p1():
    si.click(V(0, 15, 0))


def c_p2():
    si.click(V(40, 15, 0))


def c_drawn():
    h.check("C: three lines", count() == 3, count())
    h.check("C: the chain goes on", si.drawing() and chain().active)
    h.check(
        "C: FreeCAD's value field has the keyboard",
        si.focus_class() == "Gui::QuantitySpinBox",
        si.focus_class(),
    )
    si.key(QtCore.Qt.Key_Return)


def c_after_enter():
    h.check("C: Enter completed the tool", not si.drawing() and not chain().active)
    h.check("C: the lines stay (no line to nowhere)", count() == 3, count())
    h.check("C: the sketch is still open", h.in_sketch() is s["sk"])


# -- D: a typed value still draws -----------------------------------------------------------
def d_l():
    h.press("l")


def d_p1():
    si.click(V(0, 25, 0))


def d_aim():
    si.move_towards(V(30, 25, 0), V(1, 0, 0))


def d_type():
    si.type_text("25", enter=True)


d_type.wait_ms = 900


def d_drawn():
    h.check("D: the typed line was drawn", count() == 4, count())
    if count() == 4:
        a, b = line_at(3)
        h.check("D: 25 mm long", abs((b - a).Length - 25.0) < 1e-6, (b - a).Length)
    h.check("D: the chain goes on after a typed value", si.drawing() and chain().active)
    h.press(QtCore.Qt.Key_Escape)


def d_esc():
    h.check("D: Esc ended the tool", not si.drawing())


# -- E: double-click on the end point ends the chain, the tool stays ------------------------
def e_l():
    h.press("l")


def e_p1():
    si.click(V(0, 35, 0))


def e_p2():
    si.click(V(40, 35, 0))


def e_drawn():
    h.check("E: five lines", count() == 5, count())
    c = chain()
    h.check("E: the chain goes on from the end", c.active and c.current is not None, c.current)
    s["e_end"] = line_at(4)[1]  # where the line really ended (FreeCAD snaps to its grid)
    h.double_click(s["e_end"])


e_drawn.wait_ms = 700


def e_after_dbl():
    c = chain()
    h.check(
        "E: double-click ended the chain",
        c.active and c.current is None and c.chain_start is None,
        (c.current, c.chain_start),
    )
    h.check("E: the Line tool is still on", si.drawing())
    h.check("E: no line added by the double-click", count() == 5, count())


def e_q1():
    si.click(V(10, 37, 0))


def e_q2():
    si.click(V(30, 37, 0))


def e_new_chain():
    h.check("E: the next two clicks made one line", count() == 6, count())
    if count() >= 6:
        a, b = line_at(5)
        h.check(
            "E: it starts at the new first click, not at the old end",
            si.vnear(a, V(10, 37, 0), CLICK),
            all_lines(),
        )
    h.press(QtCore.Qt.Key_Escape)


# -- F: ending on existing geometry ends the chain -----------------------------------------
def f_l():
    h.press("l")


def f_p1():
    si.click(V(0, 45, 0))


def f_p2():
    si.click(s["e_end"])  # exactly the end of line E


def f_drawn():
    h.check("F: a line to the existing point", count() == 7, count())
    c = chain()
    h.check(
        "F: the chain ended on existing geometry",
        c.active and c.current is None,
        (c.current, c.chain_start, all_lines(), si.constraint_types(s["sk"])),
    )
    h.check("F: the Line tool is still on", si.drawing())
    joined = [k for k in s["sk"].Constraints if k.Type == "Coincident" and 6 in (k.First, k.Second)]
    h.check("F: its end is joined to that point", bool(joined), si.constraint_types(s["sk"]))


def f_q1():
    si.click(V(10, 47, 0))


def f_q2():
    si.click(V(30, 47, 0))


def f_new_chain():
    h.check("F: the next two clicks made one line", count() == 8, count())
    if count() >= 8:
        a, b = line_at(7)
        h.check(
            "F: it starts at the new first click", si.vnear(a, V(10, 47, 0), CLICK), all_lines()
        )
    h.press(QtCore.Qt.Key_Escape)


# -- G: no tool: no OK / Cancel --------------------------------------------------------------
def g_menu():
    h.check("G: no tool running", not si.drawing())
    right_click()


def g_check():
    m = menu()
    h.check("G: menu opens", m is not None, si.marking_labels())
    if m is None:
        return
    h.check("G: 3 o'clock is Line again", m.slots[2].text() == "Line", m.slots[2].text())
    h.check(
        "G: 9 o'clock is Sketch Dimension again",
        m.slots[6].text() == "Sketch Dimension",
        m.slots[6].text(),
    )
    labels = si.marking_labels()
    h.check("G: no OK / Cancel without a tool", not ({"OK", "Cancel"} & set(labels)), labels)
    close_menu()


def done():
    h.check("sketch still open at the end", h.in_sketch() is s["sk"])
    h.check("no pop-ups", not h.popups(), h.popups())


h.run(
    "sketch_end_line",
    [
        new_design,
        create_sketch,
        pick_xy,
        opened,
        a_l,
        a_p1,
        a_p2,
        a_drawn,
        a_menu,
        a_after_ok,
        b_l,
        b_p1,
        b_p2,
        b_drawn,
        b_menu,
        b_after_cancel,
        c_l,
        c_p1,
        c_p2,
        c_drawn,
        c_after_enter,
        d_l,
        d_p1,
        d_aim,
        d_type,
        d_drawn,
        d_esc,
        e_l,
        e_p1,
        e_p2,
        e_drawn,
        e_after_dbl,
        e_q1,
        e_q2,
        e_new_chain,
        f_l,
        f_p1,
        f_p2,
        f_drawn,
        f_q1,
        f_q2,
        f_new_chain,
        g_menu,
        g_check,
        done,
    ],
)
