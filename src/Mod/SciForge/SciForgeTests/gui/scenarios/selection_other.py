# SPDX-License-Identifier: LGPL-2.1-or-later
"""Select Other, like Fusion: press and hold the left button on the model for about a
second and a list of everything under the pointer appears, front to back; hovering a row
shows it on the model; a click selects it (parity/selection.md). Real input, box 40 x 30 x 10.

  A  hold on the middle of the top face: the list opens with the top face first, the
     bottom face (behind it) after, then the body it belongs to; letting the button go
     selects nothing (FreeCAD would have selected the face); hovering the bottom face's
     row highlights that face; clicking the row selects it and closes the list.
  B  hold near the front-top edge: the list has the edge and the two faces it bounds; Esc
     closes it and selects nothing.
  C  a press that moves on before the second is up opens no list (it is a box drag).
  D  a hold on empty space opens no list.
  E  the Select Other command (ribbon menu / search) opens the list under the pointer.
  F  inside a command: Fillet open, hold on an edge, click its row: the dialog picks it.
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import selection_input as si

V = App.Vector
TOP = V(20, 15, 10)
FRONT_TOP_EDGE = V(20, 0, 10)
st = {}


def names():
    if "names" not in st:
        st["names"] = si.name_map()
    return st["names"]


def remember_names():
    """The box's element names, read from the plain box (a dialog's preview renumbers)."""
    st["names"] = si.name_map()


def pretty(short):
    from sciforge import selection_core

    return selection_core.pretty_element(short)


def step(fn, wait_ms):
    fn.wait_ms = wait_ms
    return fn


# -- A -------------------------------------------------------------------------------------------
def a_hold_top():
    h.fit()
    h.click_empty()
    st["pos"] = si.hold(TOP)


def a_list_open():
    menu = si.select_other_menu()
    h.check("A after a second the Select Other list is open", menu is not None)
    if menu is None:
        return
    rows = si.rows(menu)
    st["rows"] = rows
    h.check(
        "A the top face is the first row (nearest)",
        rows and rows[0].startswith(pretty(names()["top"])),
        rows,
    )
    bottom = [r for r in rows if r.startswith(pretty(names()["bottom"]))]
    h.check("A the bottom face, behind it, is listed too", len(bottom) == 1, rows)
    h.check("A the body is listed after a separator", "" in rows and rows[-1] == "Body", rows)
    h.shot("A-select-other")
    si.let_go(st["pos"])


def a_release_selects_nothing():
    h.check(
        "A letting the button go selected nothing", not Gui.Selection.hasSelection(), si.selected()
    )
    menu = si.select_other_menu()
    h.check("A the list is still open", menu is not None)
    if menu is None:
        return
    bottom = [r for r in si.rows(menu) if r.startswith(pretty(names()["bottom"]))][0]
    si.hover_row(menu, bottom)


def a_hover_highlights():
    pre = si.preselected()
    h.check(
        "A hovering the bottom face's row highlights that face",
        pre is not None and pre[1].endswith(names()["bottom"]),
        pre,
    )
    menu = si.select_other_menu()
    if menu is None:
        return
    bottom = [r for r in si.rows(menu) if r.startswith(pretty(names()["bottom"]))][0]
    si.click_row(menu, bottom)


def a_row_selected():
    h.check(
        "A clicking the row selects the bottom face",
        si.selected_elements() == {names()["bottom"]},
        si.selected(),
    )
    h.check("A the list closed", si.select_other_menu() is None)
    last = si.selection_ui().last() or {}
    h.check("A the pick came from Select Other", last.get("kind") == "other", last)
    h.click_empty()


# -- B -------------------------------------------------------------------------------------------
def b_hold_edge():
    st["pos"] = si.hold(FRONT_TOP_EDGE)


def b_list_check():
    menu = si.select_other_menu()
    h.check("B the list is open", menu is not None)
    if menu is None:
        return
    rows = si.rows(menu)
    h.check(
        "B the front-top edge is listed",
        any(r.startswith(pretty(names()["edge_front_top"])) for r in rows),
        rows,
    )
    h.check(
        "B the top face is listed", any(r.startswith(pretty(names()["top"])) for r in rows), rows
    )
    h.check(
        "B the front face is listed",
        any(r.startswith(pretty(names()["front"])) for r in rows),
        rows,
    )
    si.let_go(st["pos"])
    QtTest.QTest.keyClick(menu, QtCore.Qt.Key_Escape)
    QtWidgets.QApplication.processEvents()


def b_escape_check():
    h.check("B Esc closed the list", si.select_other_menu() is None)
    h.check("B ... and selected nothing", not Gui.Selection.hasSelection(), si.selected())
    h.check("B nothing stays highlighted", si.preselected() is None, si.preselected())


# -- C -------------------------------------------------------------------------------------------
def c_press_and_move():
    st["pos"] = si.press_and_move(V(14, 14, 10), 60, 40)


def c_no_list():
    h.check("C a press that moved opens no list", si.select_other_menu() is None)
    band = si.band()
    h.check("C ... it is a box drag", band is not None and band.isVisible())
    si.release_at(st["pos"])


def c_box_done():
    band = si.band()
    h.check("C the box ended normally", band is not None and not band.isVisible())
    h.click_empty()


# -- D -------------------------------------------------------------------------------------------
def d_hold_empty():
    gl = h.gl_widget()
    pos = QtCore.QPoint(30, gl.height() - 30)
    h.move(pos)
    QtTest.QTest.mousePress(gl, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, pos)
    st["pos"] = pos


def d_no_list():
    h.check("D a hold on empty space opens no list", si.select_other_menu() is None)
    si.let_go(st["pos"])


# -- E -------------------------------------------------------------------------------------------
def e_command():
    gl = h.gl_widget()
    pos = h.screen_point(TOP)
    QtGui.QCursor.setPos(gl.mapToGlobal(pos))
    QtWidgets.QApplication.processEvents()
    Gui.runCommand("SciForge_SelectOther")


def e_list_check():
    menu = si.select_other_menu()
    h.check("E the Select Other command opened the list under the pointer", menu is not None)
    if menu is not None:
        rows = si.rows(menu)
        h.check(
            "E ... with the top face first",
            rows and rows[0].startswith(pretty(names()["top"])),
            rows,
        )
        QtTest.QTest.keyClick(menu, QtCore.Qt.Key_Escape)
        QtWidgets.QApplication.processEvents()


# -- F -------------------------------------------------------------------------------------------
def f_open_fillet():
    h.press("f")


def f_hold_edge():
    h.check("F the Fillet dialog is open", b.blend_panel() is not None)
    st["pos"] = si.hold(FRONT_TOP_EDGE)


def f_pick_row():
    menu = si.select_other_menu()
    h.check("F the list opens inside the dialog", menu is not None)
    if menu is None:
        return
    si.let_go(st["pos"])
    rows = si.rows(menu)
    edge = [r for r in rows if r.startswith(pretty(names()["edge_front_top"]))]
    h.check("F the edge is listed", len(edge) == 1, rows)
    if edge:
        si.click_row(menu, edge[0])


def f_dialog_got_it():
    panel = b.blend_panel()
    refs = list(getattr(panel, "refs", []) or []) if panel else None
    h.check(
        "F the Fillet dialog picked the edge from the list",
        refs is not None and names()["edge_front_top"] in refs,
        refs,
    )
    h.task_button("Cancel")


steps = b.box_steps("SelOther") + [
    remember_names,
    step(a_hold_top, 1500),
    a_list_open,
    a_release_selects_nothing,
    a_hover_highlights,
    a_row_selected,
    step(b_hold_edge, 1500),
    b_list_check,
    b_escape_check,
    step(c_press_and_move, 1500),
    c_no_list,
    c_box_done,
    step(d_hold_empty, 1500),
    d_no_list,
    e_command,
    e_list_check,
    f_open_fillet,
    step(f_hold_edge, 1500),
    f_pick_row,
    f_dialog_got_it,
]

h.run("selection_other", steps)
