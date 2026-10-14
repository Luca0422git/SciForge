# SPDX-License-Identifier: LGPL-2.1-or-later
"""Component Drag: dragging a jointed component with the left mouse button moves it along its
joint, with real mouse and keyboard input (docs/sciforge/parity/joints.md, "Dragging").

Plate = 0..40 x 0..30 x 10, Block = 50..70 x 0..10 x 20; J puts the block upside down on the
plate's top as a Revolute about the upright axis through (20, 15) (block 10..30 x 10..20 x
10..30). Nothing is grounded: the plate holds the pair while it is solved.

  G1 Top view: press on the block's top at (27, 15) and drag round the axis to (20, 22): the
     block turns +90 degrees (the joint reads 90, its footprint turns). One undo step: Ctrl+Z
     turns it back, Ctrl+Y again.
  G2 Esc during a drag: the block is back where the drag started.
  G3 Dragging the plate (the part the free pair hangs on) moves both together in the view
     plane; the joint keeps its angle. Ctrl+Z.
  G4 The plate grounded from the browser: a drag on it moves nothing (a note says why); the
     block still turns on its joint (back to 0). Unground.
  G5 The block dragged to 90 again; J: Fusion's prompt (components moved): Capture Position
     makes "Position 1" and the Joint dialog opens (Esc). Dragged back to 0; J: the prompt
     again: Revert puts the block back at 90; Esc.
  G6 SELECT > Component Drag unticked: a drag on the block draws a selection box and moves
     nothing; ticked again.
  G7 Save, close, reopen: dragging still works (-90 -> 0); Ctrl+Z.
"""

import os
import tempfile

from PySide import QtCore, QtWidgets
from PySide6 import QtGui, QtTest

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import joints_steps as j
from SciForgeTests.gui import timeline_input as t

V = App.Vector
state = {}
ANGLE_TOL = 1.5  # degrees: the pointer lands on whole pixels


def jm():
    return j.joints_module()


def drag_module():
    from sciforge import joints_drag

    return joints_drag


def doc():
    return App.ActiveDocument


def joint():
    found = j.joint_list()
    return found[0] if found else None


def angle_now():
    jt = joint()
    return jm().value(jt)[0] if jt is not None else None


def angle_is(name, expect, tol=ANGLE_TOL):
    got = angle_now()
    return h.check(name, got is not None and abs(got - expect) <= tol, got)


def top_view():
    h.view().viewTop()
    h.view().fitAll()
    QtWidgets.QApplication.processEvents()


def drag3d(a, b, steps=16):
    """A left-button drag from 3D point a to 3D point b (as seen now)."""
    h.drag(h.screen_point(a), h.screen_point(b), steps=steps)
    j.wait(150)


def placement_of(obj):
    return App.Placement(obj.Placement)


# -- the joint ----------------------------------------------------------------------------------
def make_motion():
    p = j.panel()
    j.click_tab(p, "Motion")
    j.choose_type(p, "Revolute")


make_motion.wait_ms = 2600


def make_ok():
    j.ok()


def made():
    j.no_dialog("Joint OK")
    h.check("Revolute 1 made", joint() is not None and joint().Label == "Revolute 1")
    j.block_box("block on the plate", j.ON_PLATE)
    h.check("nothing grounded", not jm().grounds(doc()))


# -- G1 the revolute drag -----------------------------------------------------------------------
def g1_drag():
    top_view()
    state["undos"] = doc().UndoCount
    drag3d(V(27, 15, 30), V(20, 22, 30))


def g1_turned():
    angle_is("the drag turned the block +90", 90)
    j.block_box("its footprint turned", [15, 5, 10, 25, 25, 30], 0.5)
    last = drag_module().last() or {}
    h.check("it was a drag along the joint", last.get("kind") == "joint", last)
    h.check("the plate did not move", j.plate().Placement.isSame(App.Placement(), 1e-9))
    h.check(
        "one undo step", doc().UndoCount == state["undos"] + 1, (state["undos"], doc().UndoCount)
    )
    h.check("nothing selected by the drag", not Gui.Selection.getSelectionEx())
    h.check("no drag left running", drag_module().active() is None)
    h.shot("G1-turned")


def g1_undo():
    s.undo()


def g1_undone():
    angle_is("Ctrl+Z: back at 0", 0, 1e-4)
    j.block_box("the block is back", j.ON_PLATE, 1e-3)


def g1_redo():
    s.redo()


def g1_redone():
    angle_is("Ctrl+Y: at 90 again", 90)


# -- G2 Esc -------------------------------------------------------------------------------------
def g2_drag_escape():
    state["plc"] = placement_of(j.block())
    widget = h.gl_widget()
    a = h.screen_point(V(20, 22, 30))
    b = h.screen_point(V(13, 15, 30))
    h.move(a)
    QtTest.QTest.mousePress(widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, a)
    for i in range(1, 9):
        pos = QtCore.QPointF(a.x() + (b.x() - a.x()) * i / 8.0, a.y() + (b.y() - a.y()) * i / 8.0)
        event = QtGui.QMouseEvent(
            QtCore.QEvent.MouseMove,
            pos,
            QtCore.QPointF(widget.mapToGlobal(pos.toPoint())),
            QtCore.Qt.NoButton,
            QtCore.Qt.LeftButton,
            QtCore.Qt.NoModifier,
        )
        QtWidgets.QApplication.sendEvent(widget, event)
        QtWidgets.QApplication.processEvents()
    state["mid"] = angle_now()
    widget.setFocus()
    QtTest.QTest.keyClick(widget, QtCore.Qt.Key_Escape)
    QtWidgets.QApplication.processEvents()
    QtTest.QTest.mouseRelease(widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, b)
    QtWidgets.QApplication.processEvents()


def g2_back():
    h.check(
        "the block moved while dragging",
        state.get("mid") is not None and state["mid"] > 120,
        state.get("mid"),
    )
    angle_is("Esc: back at 90", 90)
    h.check(
        "exactly where the drag started",
        j.block().Placement.isSame(state["plc"], 1e-6),
        (j.block().Placement, state["plc"]),
    )


# -- G3 the free pair moves together -----------------------------------------------------------
def g3_drag_plate():
    state["plate"] = placement_of(j.plate())
    state["block"] = placement_of(j.block())
    a = h.screen_point(V(4, 27, 10))
    drag_px(a, QtCore.QPoint(a.x() + 60, a.y()))


def drag_px(a, b):
    h.drag(a, b, steps=12)
    j.wait(150)


def g3_moved_together():
    moved = j.plate().Placement.Base - state["plate"].Base
    h.check("the plate moved to the right (+X)", moved.x > 1 and abs(moved.y) < 0.5, moved)
    h.check("in the view plane (no height change)", abs(moved.z) < 1e-6, moved)
    block_moved = j.block().Placement.Base - state["block"].Base
    h.check(
        "the block came along by the same",
        (block_moved - moved).Length < 1e-6,
        (moved, block_moved),
    )
    angle_is("the joint kept its angle", 90)
    last = drag_module().last() or {}
    h.check("a free drag of the pair", last.get("kind") == "free", last)


def g3_undo():
    s.undo()


def g3_undone():
    h.check("Ctrl+Z put the plate back", j.plate().Placement.isSame(state["plate"], 1e-6))


# -- G4 grounded --------------------------------------------------------------------------------
def g4_ground():
    j.browser_menu(j.plate().Label, "Ground")


def g4_drag_plate():
    h.check("the plate is grounded", jm().is_grounded(j.plate()))
    state["plate"] = placement_of(j.plate())
    state["undos"] = doc().UndoCount
    top_view()
    a = h.screen_point(V(4, 27, 10))
    drag_px(a, QtCore.QPoint(a.x() + 60, a.y() + 20))


def g4_held():
    h.check("the grounded plate did not move", j.plate().Placement.isSame(state["plate"], 1e-9))
    last = drag_module().last() or {}
    h.check(
        "the drag said why", last.get("kind") == "held" and "grounded" in last.get("why", ""), last
    )
    h.check("no undo step for it", doc().UndoCount == state["undos"], doc().UndoCount)
    angle_is("the block did not turn", 90)


def g4_drag_block():
    drag3d(V(20, 22, 30), V(27, 15, 30))


def g4_turned_back():
    angle_is("the block still turns on its joint: back to 0", 0)
    h.check("the plate stayed", j.plate().Placement.isSame(state["plate"], 1e-9))


def g4_unground():
    j.browser_menu(j.plate().Label, "Unground")


def g4_free():
    h.check("the plate is free again", not jm().is_grounded(j.plate()))


# -- G5 the Capture Position prompt -------------------------------------------------------------
def g5_drag():
    top_view()
    drag3d(V(27, 15, 30), V(20, 22, 30))


def g5_press_j():
    angle_is("at 90 again", 90)
    h.check("the positions changed", jm().positions_dirty(doc()))
    state["titles"] = t.titles()
    j.press_j()


g5_press_j.wait_ms = 900


def prompt_button(text):
    from sciforge import joints_ui

    box = joints_ui.prompt()
    if not h.check("the Capture Position prompt is shown", box is not None and box.isVisible()):
        return False
    for button in box.buttons():
        if button.text() == text:
            QtTest.QTest.mouseClick(button, QtCore.Qt.LeftButton)
            QtWidgets.QApplication.processEvents()
            return True
    h.check("the prompt has %s" % text, False, [b.text() for b in box.buttons()])
    return False


def g5_prompted():
    h.check("no Joint dialog before the answer", j.panel() is None, j.panel())
    prompt_button("Capture Position")


g5_prompted.wait_ms = 1200


def g5_captured():
    h.check("Position 1 in the timeline", "Position 1" in t.titles(), t.titles())
    p = j.panel()
    h.check("the Joint dialog opened", p is not None and p.title == "Joint", p and p.title)
    angle_is("the block stays at 90", 90)
    _CAPTURED["angle"] = angle_now()  # where the drag put it (CI's window: 89.7, CI #121)


_CAPTURED = {"angle": None}


def g5_escape():
    h.press(QtCore.Qt.Key_Escape)


def g5_drag_back():
    j.no_dialog("Esc")
    top_view()
    drag3d(V(20, 22, 30), V(27, 15, 30))


def g5_press_j_again():
    angle_is("dragged back to 0", 0)
    j.press_j()


g5_press_j_again.wait_ms = 900


def g5_revert():
    prompt_button("Revert")


g5_revert.wait_ms = 1200


def g5_reverted():
    captured = _CAPTURED["angle"]
    got = angle_now()
    h.check(
        "Revert: the block is back at the captured angle (about 90)",
        captured is not None and got is not None and abs(got - captured) <= 1e-3,
        (got, captured),
    )
    angle_is("Revert: about 90", 90)
    p = j.panel()
    h.check("the Joint dialog opened after Revert", p is not None and p.title == "Joint")
    h.check("nothing moved since the capture now", not jm().positions_dirty(doc()))


def g5_cancel():
    h.press(QtCore.Qt.Key_Escape)


# -- G6 Component Drag off ----------------------------------------------------------------------
def g6_untick():
    j.no_dialog("Esc")
    s.menu("SELECT", "Component Drag")


def g6_drag():
    h.check("Component Drag is off", not drag_module().enabled())
    state["plc"] = placement_of(j.block())
    top_view()
    from sciforge import selection_ui

    state["box_before"] = selection_ui.last()
    a = h.screen_point(V(16, 6, 30))
    drag_px(a, QtCore.QPoint(a.x() + 70, a.y() - 70))


def g6_boxed():
    from sciforge import selection_ui

    h.check("the block did not move", j.block().Placement.isSame(state["plc"], 1e-9))
    last = selection_ui.last() or {}
    h.check(
        "the drag drew a selection box",
        last is not state.get("box_before") and last.get("kind") == "box",
        last,
    )
    Gui.Selection.clearSelection()


def g6_tick():
    s.menu("SELECT", "Component Drag")


def g6_on():
    h.check("Component Drag is on again", drag_module().enabled())


# -- G7 save / reopen ---------------------------------------------------------------------------
def g7_save_close():
    state["path"] = os.path.join(tempfile.mkdtemp(), "joints2_drag.FCStd")
    doc().saveAs(state["path"])
    App.closeDocument(doc().Name)


def g7_open():
    App.openDocument(state["path"])
    top_view()


def g7_reopened():
    h.check("the joint is back", joint() is not None and joint().Label == "Revolute 1")
    angle_is("still at 90", 90)


def g7_drag():
    top_view()
    state["undos"] = doc().UndoCount
    drag3d(V(20, 22, 30), V(27, 15, 30))


def g7_dragged():
    angle_is("the reopened design drags: back to 0", 0)
    h.check("one undo step", doc().UndoCount == state["undos"] + 1, doc().UndoCount)


def g7_undo():
    s.undo()


def g7_undone():
    angle_is("Ctrl+Z: at 90", 90)


steps = [s.new_design("JointsDrag")] + j.two_boxes() + j.pick_pair("make")
steps += [make_motion, make_ok, made]
steps += [g1_drag, g1_turned, g1_undo, g1_undone, g1_redo, g1_redone]
steps += [g2_drag_escape, g2_back]
steps += [g3_drag_plate, g3_moved_together, g3_undo, g3_undone]
steps += [
    g4_ground,
    g4_drag_plate,
    g4_held,
    g4_drag_block,
    g4_turned_back,
    g4_unground,
    g4_free,
]
steps += [
    g5_drag,
    g5_press_j,
    g5_prompted,
    g5_captured,
    g5_escape,
    g5_drag_back,
    g5_press_j_again,
    g5_revert,
    g5_reverted,
    g5_cancel,
]
steps += [g6_untick, g6_drag, g6_boxed, g6_tick, g6_on]
steps += [g7_save_close, g7_open, g7_reopened, g7_drag, g7_dragged, g7_undo, g7_undone]

h.run("joints2_drag", steps)
