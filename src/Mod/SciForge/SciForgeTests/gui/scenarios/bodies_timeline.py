# SPDX-License-Identifier: LGPL-2.1-or-later
"""The body tools together with the timeline, undo and files, only real input.

Body1 = -20..20 x -15..15 x 10 (12000), Body2 = 10..50 x -15..15 x 10 (12000, New Body);
they overlap in 10..20 (3000). Combine Join: Body1 = 21000, Body2 used up (hidden).

  T1 right-click Body2's extrude > Roll History Marker Here: the Combine is rolled back,
     Body1 = 12000 and Body2 shows again; the timeline's Go to end: joined and hidden again.
  T2 right-click the Combine > Suppress Features: Body2 back; Unsuppress: hidden again.
  T3 right-click the Combine > Delete: Body2 back, Body1 12000; Ctrl+Z: joined again.
  T4 Split Body at the YZ square: Body1 keeps 0..50 (15000), a new body -20..0 (6000).
     Right-click the Split Body > Delete: the new body goes with it. Undo twice: back.
  T5 Move/Copy with Create Copy, X Distance 100: a copy. Delete the Move in the timeline:
     the copy goes. Undo twice: back.
  T6 Ctrl+Z while Move/Copy is open: the dialog closes and nothing moved.
  T7 save, close, open the file again: same bodies and volumes, no error; double-click the
     Combine: its dialog opens with the bodies; Cancel.
"""
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import widget_input as w

V = App.Vector
state = {}


def body1():
    return s.bodies()[0]


def body2():
    return s.bodies()[1]


def combine():
    found = s.steps_of_kind("Combine")
    return found[0] if found else None


def tl():
    from sciforge import timeline_ui

    widget = timeline_ui.widget()
    widget.refresh(force=True)
    QtWidgets.QApplication.processEvents()
    return widget


def step_button(obj):
    for button in tl()._buttons:
        if button.item.name == obj.Name:
            return button
    h.check("timeline shows %s" % obj.Name, False, tl().titles())
    return None


def timeline_menu(obj, entry):
    button = step_button(obj)
    ok = button is not None and w.right_click(button, w.center(button), entry)
    h.check("timeline menu %s > %s" % (obj.Label, entry), ok)


def extrude_of(body):
    found = [
        o
        for o in body.Group
        if "BaseFeature" in o.PropertiesList and o.TypeId != "PartDesign::FeatureBase"
    ]
    return found[0] if found else None


# -- the part -----------------------------------------------------------------------------------
def combine_open():
    h.click_empty()
    h.fit()
    h.ribbon("Combine")


def combine_target():
    h.click(V(-10, 0, 10))


def combine_tool():
    h.click(V(40, 0, 10))


def combine_ok():
    h.task_button("OK")


def joined():
    h.check("joined: 21000", s.close(s.volume(body1()), 21000), s.volume(body1()))
    state["e2"] = extrude_of(body2())
    h.check("Body2's extrude found", state["e2"] is not None)


def joined_view():
    h.check("Body2 hidden", not s.shown(body2()))


# -- T1 ------------------------------------------------------------------------------------------
def t1_roll():
    timeline_menu(state["e2"], "Roll History Marker Here")


def t1_rolled():
    h.check("rolled back: Body1 12000", s.close(s.volume(body1()), 12000), s.volume(body1()))


def t1_rolled_view():
    h.check("rolled back: Body2 shown", s.shown(body2()))


def t1_end():
    w.click(tl().findChild(QtWidgets.QToolButton, "SciForgeTimeline_end"))


def t1_at_end():
    h.check("at the end: 21000", s.close(s.volume(body1()), 21000), s.volume(body1()))


def t1_at_end_view():
    h.check("at the end: Body2 hidden", not s.shown(body2()))


# -- T2 ------------------------------------------------------------------------------------------
def t2_suppress():
    timeline_menu(combine(), "Suppress Features")


def t2_suppressed():
    h.check("suppressed: 12000", s.close(s.volume(body1()), 12000), s.volume(body1()))


def t2_suppressed_view():
    h.check("suppressed: Body2 shown", s.shown(body2()))


def t2_unsuppress():
    timeline_menu(combine(), "Unsuppress Features")


def t2_back():
    h.check("unsuppressed: 21000", s.close(s.volume(body1()), 21000), s.volume(body1()))


def t2_back_view():
    h.check("unsuppressed: Body2 hidden", not s.shown(body2()))


# -- T3 ------------------------------------------------------------------------------------------
def t3_delete():
    timeline_menu(combine(), "Delete")


def t3_deleted():
    h.check("deleted: no Combine", combine() is None)
    h.check("deleted: 12000", s.close(s.volume(body1()), 12000), s.volume(body1()))


def t3_deleted_view():
    h.check("deleted: Body2 shown", s.shown(body2()))


def t3_undo():
    s.undo()


def t3_undone():
    h.check("undo: Combine back, 21000", s.close(s.volume(body1()), 21000), s.volume(body1()))


def t3_undone_view():
    h.check("undo: Body2 hidden", not s.shown(body2()))


# -- T4 ------------------------------------------------------------------------------------------
def t4_open():
    h.click_empty()
    h.fit()
    h.ribbon("Split Body")


def t4_body():
    h.click(V(30, 0, 10))


def t4_plane():
    h.click(V(0, -30, 25))


def t4_ok():
    h.task_button("OK")


def t4_split():
    found = [b for b in s.bodies() if s.shown(b)]
    h.check("two shown bodies", len(found) == 2, [b.Label for b in found])
    h.check("Body1 = 15000", s.close(s.volume(body1()), 15000), s.volume(body1()))
    state["bodies"] = len(s.bodies())


def t4_delete():
    timeline_menu(s.steps_of_kind("SplitBody")[0], "Delete")


def t4_deleted():
    h.check(
        "split deleted: its body went too",
        len(s.bodies()) == state["bodies"] - 1,
        [b.Label for b in s.bodies()],
    )
    h.check("Body1 = 21000 again", s.close(s.volume(body1()), 21000), s.volume(body1()))


def t4_undo():
    s.undo()


def t4_undo_again():
    s.undo()


def t4_undone():
    h.check("undo twice: split back", len(s.steps_of_kind("SplitBody")) == 1)
    h.check(
        "undo twice: two pieces", len(s.bodies()) == state["bodies"], [b.Label for b in s.bodies()]
    )
    h.check("Body1 = 15000", s.close(s.volume(body1()), 15000), s.volume(body1()))


# -- T5 ------------------------------------------------------------------------------------------
def t5_open():
    h.click_empty()
    h.fit()
    h.press("m")


def t5_body():
    h.click(V(30, 0, 10))


def t5_copy():
    p = s.panel()
    if h.check("Move dialog", p is not None):
        s.toggle(p.copy)
        s.type_value(p.distance_fields[0].widget, "100")


def t5_ok():
    h.task_button("OK")


def t5_copied():
    h.check("a copy", len(s.bodies()) == state["bodies"] + 1, [b.Label for b in s.bodies()])
    copies = [m for m in s.steps_of_kind("MoveCopy")]
    h.check("one Move step", len(copies) == 1, copies)


def t5_delete():
    timeline_menu(s.steps_of_kind("MoveCopy")[0], "Delete")


def t5_deleted():
    h.check(
        "copy step deleted: the copy went",
        len(s.bodies()) == state["bodies"],
        [b.Label for b in s.bodies()],
    )


def t5_undo():
    s.undo()


def t5_undo_again():
    s.undo()


def t5_undone():
    h.check(
        "undo twice: the copy is back",
        len(s.bodies()) == state["bodies"] + 1,
        [b.Label for b in s.bodies()],
    )


# -- T6 ------------------------------------------------------------------------------------------
def t6_open():
    h.click_empty()
    h.press("m")


def t6_body():
    h.click(V(30, 0, 10))


def t6_type():
    p = s.panel()
    if h.check("Move dialog", p is not None):
        s.type_value(p.distance_fields[1].widget, "7")
    state["before"] = s.volume(body1())


def t6_ctrl_z():
    h.check("preview moved", s.close(body1().Shape.BoundBox.YMin, -8), body1().Shape.BoundBox)
    h.press("z", QtCore.Qt.ControlModifier)


def t6_cancelled():
    h.check("Ctrl+Z closed the dialog", s.panel() is None)
    h.check("nothing moved", s.close(body1().Shape.BoundBox.YMin, -15), body1().Shape.BoundBox)


# -- T7 ------------------------------------------------------------------------------------------
def t7_save_close():
    doc = App.ActiveDocument
    state["volumes"] = [round(s.volume(b), 6) for b in s.bodies()]
    state["shown"] = [s.shown(b) for b in s.bodies()]
    state["path"] = os.path.join(tempfile.mkdtemp(), "bodies_timeline.FCStd")
    doc.saveAs(state["path"])
    App.closeDocument(doc.Name)


def t7_open():
    App.openDocument(state["path"])
    QtWidgets.QApplication.processEvents()


def t7_reopened():
    volumes = [round(s.volume(b), 6) for b in s.bodies()]
    h.check("same bodies and volumes", volumes == state["volumes"], (volumes, state["volumes"]))
    h.check("same bodies shown", [s.shown(b) for b in s.bodies()] == state["shown"])
    App.ActiveDocument.recompute()
    from sciforge import timeline_ops

    problems = [
        (o.Name, timeline_ops.problem(o)) for o, _b in timeline_ops.steps(App.ActiveDocument)
    ]
    problems = [p for p in problems if p[1][0] == "error"]
    h.check("no step in error", not problems, problems)
    h.fit()


def t7_edit():
    s.timeline_double_click(combine())


def t7_dialog():
    p = s.panel()
    h.check("Combine dialog after reopening", p is not None and p.editing, p)
    if p is not None:
        h.check("target read back", p.options["target"] is body1(), p.options)
        h.check("tool read back", p.options["tools"] == [body2()], p.options)


def t7_cancel():
    h.task_button("Cancel")


def t7_cancelled():
    h.check("dialog closed", s.panel() is None)
    volumes = [round(s.volume(b), 6) for b in s.bodies()]
    h.check("unchanged", volumes == state["volumes"], volumes)


h.run(
    "bodies_timeline",
    [s.new_design("Timeline")]
    + s.box_steps("body1", (-20, -15, 20, 15), 10, V(12, -22, 0))
    + s.box_steps("body2", (10, -15, 50, 15), 10, V(5, -24, 0), new_body=True)
    + [
        combine_open,
        combine_target,
        combine_tool,
        combine_ok,
        joined,
        joined_view,
        t1_roll,
        t1_rolled,
        t1_rolled_view,
        t1_end,
        t1_at_end,
        t1_at_end_view,
        t2_suppress,
        t2_suppressed,
        t2_suppressed_view,
        t2_unsuppress,
        t2_back,
        t2_back_view,
        t3_delete,
        t3_deleted,
        t3_deleted_view,
        t3_undo,
        t3_undone,
        t3_undone_view,
        t4_open,
        t4_body,
        t4_plane,
        t4_ok,
        t4_split,
        t4_delete,
        t4_deleted,
        t4_undo,
        t4_undo_again,
        t4_undone,
        t5_open,
        t5_body,
        t5_copy,
        t5_ok,
        t5_copied,
        t5_delete,
        t5_deleted,
        t5_undo,
        t5_undo_again,
        t5_undone,
        t6_open,
        t6_body,
        t6_type,
        t6_ctrl_z,
        t6_cancelled,
        t7_save_close,
        t7_open,
        t7_reopened,
        t7_edit,
        t7_dialog,
        t7_cancel,
        t7_cancelled,
    ],
)
