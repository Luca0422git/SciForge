# SPDX-License-Identifier: LGPL-2.1-or-later
"""Split Body (Modify > Split Body), only real input.

Body1 = rectangle -20..20 x -15..15, extruded 10 (12000), so the origin planes cross it.

  A  nothing selected: the Split Body button opens the dialog waiting for the body; click
     Body1, then the big YZ origin square: the preview splits it at x = 0 into two bodies of
     6000 (Body1 keeps x < 0, the new body x > 0, both 6 faces); OK. Ctrl+Z gives one body
     of 12000 back, Ctrl+Y the two halves.
  B  double-click the Split Body in the timeline, click the XZ square: now split at y = 0
     (Body1 keeps y < 0). OK.
  C  Cancel: Split Body, click Body1, click the XY square... the bottom face plane does not
     cut; the reason is in the dialog; Cancel leaves the model unchanged.
  D  a second body (New Body, 25..35 x -5..5, 20 high) as the tool owner: Body1 selected
     first, Split Body, click the face of that body at y = -5 with Extend Splitting Tool off:
     the face does not reach Body1, the reason is shown; tick Extend: the plane y = -5
     splits Body1 (y -15..0) into 4000 (kept) and 2000 (new body). OK.
  E  Esc cancels an open Split Body.
"""
import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h

V = App.Vector
state = {}


def body1():
    return s.bodies()[0]


def splits():
    return s.steps_of_kind("SplitBody")


def bb(body):
    return body.Shape.BoundBox


# -- A ----------------------------------------------------------------------------------------
def a_open():
    h.click_empty()
    h.fit()
    h.ribbon("Split Body")


def a_waits():
    p = s.panel()
    h.check("Split Body dialog open", p is not None and p.title == "Split Body", p)
    s.no_popups("Split Body")
    if p is not None:
        h.check("body box takes the first click", p.active == "body", p.active)
        h.check("hint asks for the body", "body" in p.info.text().lower(), p.info.text())


def a_click_body():
    h.click(V(-10, -5, 10))


def a_click_yz():
    p = s.panel()
    if p is not None:
        h.check("Body1 picked", p.options["body"] is body1(), p.options)
        h.check("tool box waits", p.active == "tool", p.active)
        h.check("origin squares drawn", p.plane_picker is not None)
    h.click(V(0, -24, 20))


def a_preview():
    found = s.bodies()
    h.check("preview: two bodies", len(found) == 2, [x.Label for x in found])
    if len(found) == 2:
        h.check("Body1 = 6000", s.close(s.volume(found[0]), 6000), s.volume(found[0]))
        h.check("new body = 6000", s.close(s.volume(found[1]), 6000), s.volume(found[1]))
        h.check("Body1 keeps x < 0", s.close(bb(found[0]).XMax, 0), bb(found[0]))
        h.check("new body is x > 0", s.close(bb(found[1]).XMin, 0), bb(found[1]))
    h.shot("A-preview")


def a_ok():
    h.task_button("OK")


def a_done():
    found = s.bodies()
    h.check("dialog closed", s.panel() is None)
    h.check("two bodies", len(found) == 2)
    h.check("one Split Body step", len(splits()) == 1, splits())
    if len(found) == 2:
        h.check("6 faces each", [len(x.Shape.Faces) for x in found] == [6, 6])
        h.check("both shown", s.shown(found[0]) and s.shown(found[1]))
    h.shot("A-split")


def a_undo():
    s.undo()


def a_undone():
    h.check("undo: one body", len(s.bodies()) == 1, [x.Label for x in s.bodies()])
    h.check("undo: 12000", s.close(s.volume(body1()), 12000), s.volume(body1()))


def a_redo():
    s.redo()


def a_redone():
    found = s.bodies()
    h.check("redo: two bodies", len(found) == 2, [x.Label for x in found])
    h.check("redo: 6000 + 6000", s.close(s.total_volume(), 12000), s.total_volume())


# -- B ----------------------------------------------------------------------------------------
def b_edit():
    h.fit()
    s.timeline_double_click(splits()[0])


def b_click_xz():
    p = s.panel()
    if h.check("edit dialog open", p is not None and p.editing, p):
        h.check("edit waits for the tool", p.active == "tool", p.active)
    h.click(V(15, 0, 18))


def b_preview():
    found = s.bodies()
    h.check("still two bodies", len(found) == 2, [x.Label for x in found])
    if len(found) == 2:
        h.check("Body1 keeps y < 0", s.close(bb(found[0]).YMax, 0), bb(found[0]))
        h.check("Body1 = 6000", s.close(s.volume(found[0]), 6000), s.volume(found[0]))
        h.check("other half y > 0", s.close(bb(found[1]).YMin, 0), bb(found[1]))


def b_ok():
    h.task_button("OK")


def b_done():
    h.check("dialog closed", s.panel() is None)
    h.check("still one Split Body step", len(splits()) == 1, splits())
    h.check("total 12000", s.close(s.total_volume(), 12000), s.total_volume())
    h.shot("B-split-xz")


# -- C ----------------------------------------------------------------------------------------
def c_open():
    h.click_empty()
    h.fit()
    h.ribbon("Split Body")


def c_click_body():
    h.click(V(-10, -10, 10))


def c_click_xy():
    h.click(V(18, -24, 0))


def c_reason():
    p = s.panel()
    if h.check("dialog open", p is not None):
        h.check("XY plane picked", p.options["tool"] is not None, p.options)
        h.check("the reason is shown", "does not cut" in p.message.text(), p.message.text())
    h.check("no third body", len(s.bodies()) == 2, [x.Label for x in s.bodies()])


def c_cancel():
    h.task_button("Cancel")


def c_cancelled():
    h.check("Cancel: dialog closed", s.panel() is None)
    h.check("Cancel: two bodies", len(s.bodies()) == 2)
    h.check("Cancel: 6000 kept", s.close(s.volume(body1()), 6000), s.volume(body1()))


# -- D ----------------------------------------------------------------------------------------
def d_select_body1():
    h.fit()
    h.click(V(-10, -10, 10))


def d_open():
    h.ribbon("Split Body")


def d_body_taken():
    p = s.panel()
    if h.check("dialog open", p is not None):
        h.check("preselected Body1 taken", p.options["body"] is body1(), p.options)
        h.check("tool box waits", p.active == "tool", p.active)


def d_extend_off():
    p = s.panel()
    if p is not None and p.extend.isChecked():
        s.toggle(p.extend)
    h.check("Extend off", p is not None and not p.extend.isChecked())


def d_click_face():
    h.click(V(30, -5, 10))


def d_reason():
    p = s.panel()
    if h.check("dialog open", p is not None):
        h.check(
            "the face is the tool",
            p.options["tool"] is not None and p.options["tool"][1].startswith("Face"),
            p.options,
        )
        h.check("not extended: the reason", "does not cut" in p.message.text(), p.message.text())


def d_extend_on():
    p = s.panel()
    if p is not None:
        s.toggle(p.extend)


def d_preview():
    found = s.bodies()
    h.check("four bodies now", len(found) == 4, [x.Label for x in found])
    h.check("Body1 = 4000 (y -15..-5)", s.close(s.volume(body1()), 4000), s.volume(body1()))
    if len(found) == 4:
        h.check("new piece = 2000", s.close(s.volume(found[3]), 2000), s.volume(found[3]))


def d_ok():
    h.task_button("OK")


def d_done():
    h.check("dialog closed", s.panel() is None)
    h.check("two Split Body steps", len(splits()) == 2, splits())
    h.shot("D-extended-face")


# -- E ----------------------------------------------------------------------------------------
def e_open():
    h.click_empty()
    h.ribbon("Split Body")


def e_escape():
    h.check("dialog open", s.panel() is not None)
    h.press(QtCore.Qt.Key_Escape)


def e_closed():
    h.check("Esc closed it", s.panel() is None)
    h.check("Esc: four bodies", len(s.bodies()) == 4)


h.run(
    "bodies_split",
    [s.new_design("Split")]
    + s.box_steps("body1", (-20, -15, 20, 15), 10, V(12, -22, 0))
    + [
        a_open,
        a_waits,
        a_click_body,
        a_click_yz,
        a_preview,
        a_ok,
        a_done,
        a_undo,
        a_undone,
        a_redo,
        a_redone,
        b_edit,
        b_click_xz,
        b_preview,
        b_ok,
        b_done,
        c_open,
        c_click_body,
        c_click_xy,
        c_reason,
        c_cancel,
        c_cancelled,
    ]
    + s.box_steps("tool_body", (25, -5, 35, 5), 20, V(5, -24, 0), new_body=True)
    + [
        d_select_body1,
        d_open,
        d_body_taken,
        d_extend_off,
        d_click_face,
        d_reason,
        d_extend_on,
        d_preview,
        d_ok,
        d_done,
        e_open,
        e_escape,
        e_closed,
    ],
)
