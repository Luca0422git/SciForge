# SPDX-License-Identifier: LGPL-2.1-or-later
"""Move/Copy of whole components (Move Object: Components), only real input.

Setup: a 40 x 30 x 10 box made into the component "Bracket" (Create Components from
Bodies, then renamed), and a second box "Free" (x 60..100) left at the root.

  A  M, Move Object Components (the dialog switches), click the box: the component is
     picked, the manipulator sits at its middle (20, 15, 5). Drag the X arrow about 15 mm:
     the component follows. Type X Distance 10, tick Capture Position, OK: Bracket stands
     at x 10 (its Placement), its body is unchanged inside it, the timeline has a Move.
  B  Undo: back at 0, no Move; Redo: at 10 again with its Move.
  C  Double-click the Move in the timeline: the dialog edits it (Capture on, Components);
     Y Distance 5, OK: Bracket at (10, 5, 0), still one Move step.
  D  Select Bracket's browser row, M: the dialog opens on Components with Bracket picked.
     Set Pivot, click near the corner (10, 5, 10): the manipulator jumps there and nothing
     moves; Done; Z Angle 90: Bracket turns about the vertical line through the corner:
     x -20..10, y 5..45. OK without Capture Position: no new timeline step.
  E  M on Bracket's row, X Distance 30, Esc: nothing moved.
  F  Ground Bracket (browser), M, Components, click it: refused, the dialog says it is
     grounded and picks nothing; Cancel; Unground.
  G  M, Components, click the root body Free: refused (it is in no component).
  H  The history marker dragged before the Move: Bracket goes back to where it was before
     the captured move (0, 0, 0); the marker to the end: at (10, 5, 0) again.
  I  Save, close, reopen: Bracket at (10, 5, 0), the Move step there; editing it opens the
     component dialog with Y Distance 5.
"""

import os
import tempfile

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import component2_steps as c
from SciForgeTests.gui import component_steps as cs
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import timeline_input as t

V = App.Vector
state = {}
BOX = 12000.0


def bracket():
    return c.part("Bracket")


def new_design():
    s.new_design("Components2Move")()


def setup_component():
    bodies = cs.bodies()
    h.check("two bodies", len(bodies) == 2, [b.Label for b in bodies])
    state["b1"], state["b2"] = bodies[0].Name, bodies[1].Name
    state["l1"], state["l2"] = bodies[0].Label, bodies[1].Label
    t.row_menu(state["l1"], "Create Components from Bodies")


def setup_rename():
    h.check("a component named after the body", c.part(state["l1"]) is not None, c.labels())
    cs.rename_row(state["l1"], "Bracket")


def setup_done():
    h.check("Bracket exists", bracket() is not None, c.labels())
    c.box_is("Bracket where the box was", bracket(), [0, 0, 0, 40, 30, 10])
    state["moves0"] = len(c.moves())


# -- A --------------------------------------------------------------------------------------------
def a_press_m():
    h.click_empty()
    h.fit()
    h.press("m")


def a_switch():
    p = c.panel()
    if h.check("Move/Copy open", p is not None and p.title == "Move/Copy", p):
        h.check("Move Object offers Components", p.move_object.findText("Components") >= 0)
        c.choose(p.move_object, "Components", closes=True)


def a_switched():
    p = c.component_panel()
    if h.check("the components dialog took over", p is not None, c.panel()):
        h.check("Move Object reads Components", p.move_object.currentText() == "Components")
        h.check("Capture Position offered, off", not p.capture.isChecked())
        h.check("the objects box waits", p.active == "objects", p.active)


def a_click():
    h.click(V(20, 15, 10))


def a_picked():
    p = c.component_panel()
    if not h.check("dialog open", p is not None):
        return
    h.check("Bracket picked", p.options.get("components") == [bracket()], p.options)
    triad = getattr(p, "triad", None)
    if h.check("manipulator shown", triad is not None):
        h.check("at Bracket's middle", (triad.center - V(20, 15, 5)).Length < 1e-6, triad.center)
    h.shot("A-picked")


def a_drag():
    c.drag_arrow(0, 15)


def a_dragged():
    p = c.component_panel()
    dx = p.options["dx"] if p is not None else 0
    h.check("drag moved about 15 in X", abs(dx - 15) < 2.0, dx)
    h.check("Bracket follows", abs(c.at(bracket()).x - dx) < 1e-6, (c.at(bracket()), dx))


def a_type():
    p = c.component_panel()
    if p is not None:
        c.type_value(p, "dx", "10")
        c.toggle(p.capture)


def a_typed():
    c.placed("Bracket at x 10", bracket(), V(10, 0, 0))
    p = c.component_panel()
    h.check("Capture Position ticked", p is not None and p.capture.isChecked())


def a_ok():
    h.task_button("OK")


def a_done():
    h.check("dialog closed", c.panel() is None)
    c.placed("Bracket stands at x 10", bracket(), V(10, 0, 0))
    c.box_is("its box moved with it", bracket(), [10, 0, 0, 50, 30, 10])
    body = App.ActiveDocument.getObject(state["b1"])
    h.check("the body itself is unchanged", c.close(body.Shape.BoundBox.XMin, 0.0))
    h.check("volume kept", c.close(c.volume(bracket()), BOX), c.volume(bracket()))
    h.check("one Move step", len(c.moves()) == state["moves0"] + 1, c.moves())
    if c.moves():
        title = c.timeline_title(c.moves()[-1])
        h.check("the timeline shows it as a Move", (title or "").startswith("Move"), title)
    h.shot("A-done")


# -- B --------------------------------------------------------------------------------------------
def b_undo():
    s.undo()


def b_undone():
    c.placed("Undo: Bracket back at 0", bracket(), V(0, 0, 0))
    h.check("Undo: no Move step", not c.moves(), c.moves())


def b_redo():
    s.redo()


def b_redone():
    c.placed("Redo: Bracket at 10 again", bracket(), V(10, 0, 0))
    h.check("Redo: the Move step back", len(c.moves()) == 1, c.moves())


# -- C --------------------------------------------------------------------------------------------
def c_edit():
    if h.check("a Move step to edit", bool(c.moves())):
        s.timeline_double_click(c.moves()[0])


def c_change():
    p = c.component_panel()
    if not h.check("edit dialog (components)", p is not None and p.editing, c.panel()):
        return
    h.check("editing shows X Distance 10", abs(p.options["dx"] - 10) < 1e-9, p.options["dx"])
    h.check("Capture Position on", p.capture.isChecked())
    h.check("Bracket in the Objects box", p.options.get("components") == [bracket()])
    c.type_value(p, "dy", "5")


def c_ok():
    h.task_button("OK")


def c_done():
    c.placed("Bracket at (10, 5, 0)", bracket(), V(10, 5, 0))
    h.check("still one Move step", len(c.moves()) == 1, c.moves())


# -- D --------------------------------------------------------------------------------------------
def d_select():
    h.click_empty()
    t.click_row("Bracket")


def d_press_m():
    h.fit()
    h.press("m")


def d_opened():
    p = c.component_panel()
    if h.check("M on a component row opens the components dialog", p is not None, c.panel()):
        h.check("Bracket picked at once", p.options.get("components") == [bracket()], p.options)
        h.check("Free Move", p.move_type.currentText() == "Free Move")
        h.check("Set Pivot offered", p.set_pivot.isVisible())


def d_set_pivot():
    p = c.component_panel()
    if p is not None:
        c.click_button(p.set_pivot)


def d_pivot_mode():
    p = c.component_panel()
    if not h.check("dialog open", p is not None):
        return
    h.check("setting the pivot", p.setting_pivot)
    h.check("Done shown", p.pivot_done.isVisible())
    h.check("no turn handles while setting the pivot", p.triad is not None and not p.triad.turns)


def d_click_corner():
    h.click(V(11, 6, 10))


def d_pivot_set():
    p = c.component_panel()
    if not h.check("dialog open", p is not None):
        return
    triad = p.triad
    h.check(
        "the manipulator jumped to the corner",
        triad is not None and (triad.center - V(10, 5, 10)).Length < 1e-6,
        triad.center if triad else None,
    )
    c.placed("nothing moved", bracket(), V(10, 5, 0))
    values = [f.value() for f in p.pivot_fields]
    h.check("Pivot X / Y / Z show it", all(abs(a - b) < 1e-6 for a, b in zip(values, (10, 5, 10))))
    h.shot("D-pivot")


def d_done():
    p = c.component_panel()
    if p is not None:
        c.click_button(p.pivot_done)


def d_turn():
    p = c.component_panel()
    if not h.check("dialog open", p is not None):
        return
    h.check("pivot kept", not p.setting_pivot and p.triad is not None and p.triad.turns)
    c.type_value(p, "rz", "90")


def d_turned():
    c.box_is("turned 90 about the corner", bracket(), [-20, 5, 0, 10, 45, 10])
    h.check("volume kept", c.close(c.volume(bracket()), BOX), c.volume(bracket()))


def d_ok():
    h.task_button("OK")


def d_done_check():
    c.box_is("stays turned", bracket(), [-20, 5, 0, 10, 45, 10])
    h.check("no new step (Capture Position off)", len(c.moves()) == 1, c.moves())
    state["turned"] = App.Placement(bracket().Placement)


# -- E --------------------------------------------------------------------------------------------
def e_open():
    h.click_empty()
    t.click_row("Bracket")
    h.press("m")


def e_type():
    p = c.component_panel()
    if h.check("dialog open", p is not None):
        c.type_value(p, "dx", "30")


def e_moved():
    c.box_is("previewed 30 further", bracket(), [10, 5, 0, 40, 45, 10])


def e_escape():
    h.press(QtCore.Qt.Key_Escape)


def e_back():
    h.check("dialog closed", c.panel() is None)
    h.check("Esc: nothing moved", bracket().Placement.isSame(state["turned"], 1e-9))


# -- F --------------------------------------------------------------------------------------------
def f_ground():
    t.row_menu("Bracket", "Ground")


def f_press_m():
    h.click_empty()
    h.press("m")


def f_switch():
    p = c.panel()
    if h.check("Move/Copy open", p is not None):
        c.choose(p.move_object, "Components", closes=True)


def f_click():
    h.click(V(-5, 25, 10))


def f_refused():
    p = c.component_panel()
    if not h.check("dialog open", p is not None):
        return
    h.check("nothing picked", not p.options.get("components"), p.options.get("components"))
    h.check("says it is grounded", "grounded" in p.message.text(), p.message.text())


# -- G --------------------------------------------------------------------------------------------
def g_click_free():
    h.click(V(80, 15, 10))


def g_refused():
    p = c.component_panel()
    if not h.check("dialog open", p is not None):
        return
    h.check("still nothing picked", not p.options.get("components"))
    h.check("says it is in no component", "no component" in p.message.text(), p.message.text())


def g_cancel():
    h.task_button("Cancel")


def g_unground():
    h.check("dialog closed", c.panel() is None)
    t.row_menu("Bracket", "Unground")


# -- H --------------------------------------------------------------------------------------------
def h_roll():
    title = c.timeline_title(c.moves()[0]) if c.moves() else None
    if h.check("the Move is in the timeline", title is not None):
        t.drag_marker(before_title=title)


def h_rolled():
    c.placed("marker before the Move: Bracket where it was", bracket(), V(0, 0, 0))
    h.shot("H-rolled")


def h_end():
    t.drag_marker(to_end=True)


def h_ended():
    c.placed("marker at the end: the captured move again", bracket(), V(10, 5, 0))


# -- I --------------------------------------------------------------------------------------------
def i_save_close():
    state["path"] = os.path.join(tempfile.mkdtemp(), "components2_move.FCStd")
    App.ActiveDocument.saveAs(state["path"])
    App.closeDocument(App.ActiveDocument.Name)


def i_open():
    App.openDocument(state["path"])
    h.fit()


def i_reopened():
    c.placed("reopened: Bracket at (10, 5, 0)", bracket(), V(10, 5, 0))
    h.check("the Move step is back", len(c.moves()) == 1, c.moves())


def i_edit():
    if c.moves():
        s.timeline_double_click(c.moves()[0])


def i_editing():
    p = c.component_panel()
    if h.check("edit opens the components dialog", p is not None and p.editing, c.panel()):
        h.check("Y Distance 5", abs(p.options["dy"] - 5) < 1e-9, p.options["dy"])


def i_cancel():
    h.task_button("Cancel")


def i_kept():
    c.placed("Cancel keeps it", bracket(), V(10, 5, 0))


h.run(
    "components2_move",
    t.watched(
        [new_design]
        + s.box_steps("box", (0, 0, 40, 30), 10, V(12, -8, 0))
        + s.box_steps("free", (60, 0, 100, 30), 10, V(12, -8, 0), new_body=True)
        + [
            setup_component,
            setup_rename,
            setup_done,
            a_press_m,
            a_switch,
            a_switched,
            a_click,
            a_picked,
            a_drag,
            a_dragged,
            a_type,
            a_typed,
            a_ok,
            a_done,
            b_undo,
            b_undone,
            b_redo,
            b_redone,
            c_edit,
            c_change,
            c_ok,
            c_done,
            d_select,
            d_press_m,
            d_opened,
            d_set_pivot,
            d_pivot_mode,
            d_click_corner,
            d_pivot_set,
            d_done,
            d_turn,
            d_turned,
            d_ok,
            d_done_check,
            e_open,
            e_type,
            e_moved,
            e_escape,
            e_back,
            f_ground,
            f_press_m,
            f_switch,
            f_click,
            f_refused,
            g_click_free,
            g_refused,
            g_cancel,
            g_unground,
            h_roll,
            h_rolled,
            h_end,
            h_ended,
            i_save_close,
            i_open,
            i_reopened,
            i_edit,
            i_editing,
            i_cancel,
            i_kept,
        ]
    ),
)
