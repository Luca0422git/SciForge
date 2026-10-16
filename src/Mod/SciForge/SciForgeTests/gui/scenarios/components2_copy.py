# SPDX-License-Identifier: LGPL-2.1-or-later
"""Copy / Paste / Paste New of components (and Paste of a body), only real input.

Setup: a 40 x 30 x 10 box made into the component "Bracket"; a body "Free" (150..170 x
0..20, 10 high) at the root.

  A  Bracket's row selected, Ctrl+C, Ctrl+V: a linked instance "Bracket:2" appears (the
     browser now reads Bracket:1 and Bracket:2), no new timeline step, and Move/Copy opens
     on it (Components, Bracket:2 picked); X Distance 60, OK: Bracket:2 at x 60..100.
  B  Double-click Extrude 1 (the original's) in the timeline, distance 20, OK: Bracket and
     Bracket:2 are both 20 high (24000 each): editing one changes all.
  C  Right-click Bracket:1, Paste New: an independent "Bracket (1)" with its own steps, Move
     opens on it; Y Distance 50, OK. Extrude 1 to 30: Bracket and Bracket:2 grow to 36000,
     Bracket (1) keeps 24000.
  D  Ctrl+V again: Bracket:3; Esc closes the move and keeps the paste (on the original).
     Undo: Bracket:3 gone; Redo: back; Delete key on its row: gone.
  E  Click the activate ring of Bracket:2: Bracket (its original) becomes the active one.
  F  Click the body Free, Ctrl+C, Ctrl+V: Move/Copy opens on it with Create Copy on; X
     Distance 30, OK: a second body at x 180..200, Free stays.
  G  Save, close, reopen: Bracket:2 is still an instance; Extrude 1 back to 10: both
     follow (12000).
"""

import os
import tempfile

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import component2_steps as c
from SciForgeTests.gui import component_steps as cs
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import timeline_input as t

V = App.Vector
state = {}


def bracket():
    return c.part("Bracket")


def instances_mod():
    from sciforge import instances

    return instances


def new_design():
    s.new_design("Components2Copy")()


def setup_component():
    found = cs.bodies()
    h.check("two bodies", len(found) == 2, [x.Label for x in found])
    state["b1"], state["free"] = found[0].Name, found[1].Name
    state["l1"] = found[0].Label
    t.row_menu(state["l1"], "Create Components from Bodies")


def setup_rename():
    cs.rename_row(state["l1"], "Bracket")


def setup_done():
    h.check("Bracket exists", bracket() is not None, c.labels())
    state["steps0"] = len(c.doc().Objects)
    state["titles0"] = list(cs.all_timeline_titles())


# -- A --------------------------------------------------------------------------------------------
def a_select():
    h.click_empty()
    t.click_row("Bracket")


def a_copy():
    h.press(QtCore.Qt.Key_C, QtCore.Qt.ControlModifier)


def a_paste():
    h.press(QtCore.Qt.Key_V, QtCore.Qt.ControlModifier)


def a_pasted():
    copy = c.part("Bracket:2")
    if not h.check("an instance Bracket:2 was pasted", copy is not None, c.labels()):
        return
    state["i2"] = copy.Name
    h.check("it is linked to Bracket", instances_mod().source_of(copy) is bracket())
    h.check("on top of the original", c.close(c.volume(copy), 12000), c.volume(copy))
    c.box_is("right on the original", copy, [0, 0, 0, 40, 30, 10])
    labels = c.browser_labels()
    h.check("browser: Bracket:1 and Bracket:2", {"Bracket:1", "Bracket:2"} <= set(labels), labels)
    h.check(
        "no new timeline step",
        list(cs.all_timeline_titles()) == state["titles0"],
        cs.all_timeline_titles(),
    )
    p = c.component_panel()
    if h.check("Move opens on the paste", p is not None, c.panel()):
        h.check("Bracket:2 picked", p.options.get("components") == [copy], p.options)
    h.shot("A-pasted")


def a_move():
    p = c.component_panel()
    if p is not None:
        c.type_value(p, "dx", "60")


def a_ok():
    h.task_button("OK")


def a_placed():
    copy = c.part("Bracket:2")
    c.box_is("Bracket:2 at x 60..100", copy, [60, 0, 0, 100, 30, 10])
    c.box_is("Bracket stays", bracket(), [0, 0, 0, 40, 30, 10])


# -- B --------------------------------------------------------------------------------------------
def b_edit():
    b.timeline_double_click("Extrude 1")


def b_type():
    p = c.panel()
    field = getattr(getattr(p, "distance", None), "widget", None)
    if h.check("extrude dialog open", field is not None, p):
        b.type_into(field, "20")
        QtTest_tab(field)


def QtTest_tab(widget):
    from PySide import QtWidgets
    from PySide6 import QtTest

    QtTest.QTest.keyClick(widget, QtCore.Qt.Key_Tab)
    QtWidgets.QApplication.processEvents()


def b_ok():
    h.task_button("OK")


def b_both():
    copy = c.part("Bracket:2")
    h.check("Bracket 20 high", c.close(c.volume(bracket()), 24000), c.volume(bracket()))
    h.check("Bracket:2 follows", c.close(c.volume(copy), 24000), c.volume(copy))
    c.box_is("Bracket:2 still at x 60", copy, [60, 0, 0, 100, 30, 20])
    h.shot("B-both")


# -- C --------------------------------------------------------------------------------------------
def c_paste_new():
    entries = [e for e, _ok in t.row_menu_entries("Bracket:1")]
    h.check("the row offers Paste New", "Paste New" in entries, entries)
    t.row_menu("Bracket:1", "Paste New")


def c_pasted():
    copy = c.part("Bracket (1)")
    if not h.check("an independent Bracket (1)", copy is not None, c.labels()):
        return
    state["new"] = copy.Name
    h.check("not an instance", not instances_mod().is_instance(copy))
    h.check(
        "its own steps in the timeline",
        len(cs.all_timeline_titles()) > len(state["titles0"]),
        cs.all_timeline_titles(),
    )
    p = c.component_panel()
    if h.check("Move opens on it", p is not None, c.panel()):
        h.check("Bracket (1) picked", p.options.get("components") == [copy])


def c_move():
    p = c.component_panel()
    if p is not None:
        c.type_value(p, "dy", "50")


def c_ok():
    h.task_button("OK")


def c_edit():
    b.timeline_double_click("Extrude 1")


def c_type():
    p = c.panel()
    field = getattr(getattr(p, "distance", None), "widget", None)
    if h.check("extrude dialog open", field is not None, p):
        b.type_into(field, "30")
        QtTest_tab(field)


def c_ok2():
    h.task_button("OK")


def c_only_one():
    copy = c.part("Bracket:2")
    new = c.doc().getObject(state.get("new", ""))
    h.check("Bracket 30 high", c.close(c.volume(bracket()), 36000), c.volume(bracket()))
    h.check("the instance follows", c.close(c.volume(copy), 36000), c.volume(copy))
    h.check("Paste New does not", new is not None and c.close(c.volume(new), 24000), c.volume(new))
    c.box_is("Bracket (1) moved 50 in Y", new, [0, 50, 0, 40, 80, 20])
    h.shot("C-paste-new")


# -- D --------------------------------------------------------------------------------------------
def d_paste():
    h.click_empty()
    h.press(QtCore.Qt.Key_V, QtCore.Qt.ControlModifier)


def d_escape():
    h.check("Move opened", c.component_panel() is not None, c.panel())
    h.press(QtCore.Qt.Key_Escape)


def d_kept():
    copy = c.part("Bracket:3")
    h.check("Esc keeps the paste", copy is not None, c.labels())
    c.box_is("on the original", copy, [0, 0, 0, 40, 30, 30])


def d_undo():
    s.undo()


def d_undone():
    h.check("Undo: Bracket:3 gone", c.part("Bracket:3") is None, c.labels())


def d_redo():
    s.redo()


def d_redone():
    h.check("Redo: Bracket:3 back", c.part("Bracket:3") is not None, c.labels())


def d_select():
    t.click_row("Bracket:3")


def d_delete():
    from SciForgeTests.gui import widget_input as w

    w.key(t.tree(), QtCore.Qt.Key_Delete)


def d_deleted():
    h.check("Delete: Bracket:3 gone", c.part("Bracket:3") is None, c.labels())
    h.check("the others stay", c.part("Bracket:2") is not None and bracket() is not None)


# -- E --------------------------------------------------------------------------------------------
def e_ring():
    cs.click_radio("Bracket:2")


def e_active():
    h.check("the original is activated", cs.active_label() == "Bracket", cs.active_label())


def e_root():
    cs.click_radio(App.ActiveDocument.Label)


# -- F --------------------------------------------------------------------------------------------
def f_click():
    h.click_empty()
    h.fit()
    h.click(V(160, 10, 10))


def f_copy():
    h.press(QtCore.Qt.Key_C, QtCore.Qt.ControlModifier)


def f_paste():
    h.press(QtCore.Qt.Key_V, QtCore.Qt.ControlModifier)


def f_opened():
    p = c.panel()
    if h.check("Move opens (bodies)", p is not None and p.object_type == "bodies", p):
        free = c.doc().getObject(state["free"])
        h.check("Free picked", p.options["bodies"] == [free], p.options["bodies"])
        h.check("Create Copy on", p.copy.isChecked())
        c.type_value(p, "dx", "30")


def f_ok():
    h.task_button("OK")


def f_copied():
    root = [x for x in cs.bodies() if cs.container_label(x) is None]
    h.check("two root bodies now", len(root) == 2, [x.Label for x in root])
    boxes = sorted(c.box_of(x)[0] for x in root)
    h.check("the copy at x 180", len(boxes) == 2 and abs(boxes[1] - 180) < 1e-6, boxes)


# -- G --------------------------------------------------------------------------------------------
def g_save_close():
    state["path"] = os.path.join(tempfile.mkdtemp(), "components2_copy.FCStd")
    App.ActiveDocument.saveAs(state["path"])
    App.closeDocument(App.ActiveDocument.Name)


def g_open():
    App.openDocument(state["path"])
    h.fit()


def g_reopened():
    copy = c.part("Bracket:2")
    h.check("Bracket:2 back", copy is not None, c.labels())
    h.check("still an instance of Bracket", instances_mod().source_of(copy) is bracket())


def g_edit():
    b.timeline_double_click("Extrude 1")


def g_type():
    p = c.panel()
    field = getattr(getattr(p, "distance", None), "widget", None)
    if h.check("extrude dialog open", field is not None, p):
        b.type_into(field, "10")
        QtTest_tab(field)


def g_ok():
    h.task_button("OK")


def g_follows():
    copy = c.part("Bracket:2")
    h.check("Bracket 12000", c.close(c.volume(bracket()), 12000), c.volume(bracket()))
    h.check("the instance follows after reopening", c.close(c.volume(copy), 12000))


h.run(
    "components2_copy",
    t.watched(
        [new_design]
        + s.box_steps("box", (0, 0, 40, 30), 10, V(6, -6, 0))
        + s.box_steps("free", (150, 0, 170, 20), 10, V(6, -6, 0), new_body=True)
        + [
            setup_component,
            setup_rename,
            setup_done,
            a_select,
            a_copy,
            a_paste,
            a_pasted,
            a_move,
            a_ok,
            a_placed,
            b_edit,
            b_type,
            b_ok,
            b_both,
            c_paste_new,
            c_pasted,
            c_move,
            c_ok,
            c_edit,
            c_type,
            c_ok2,
            c_only_one,
            d_paste,
            d_escape,
            d_kept,
            d_undo,
            d_undone,
            d_redo,
            d_redone,
            d_select,
            d_delete,
            d_deleted,
            e_ring,
            e_active,
            e_root,
            f_click,
            f_copy,
            f_paste,
            f_opened,
            f_ok,
            f_copied,
            g_save_close,
            g_open,
            g_reopened,
            g_edit,
            g_type,
            g_ok,
            g_follows,
        ]
    ),
)
