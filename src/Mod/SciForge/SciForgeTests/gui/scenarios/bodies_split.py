# SPDX-License-Identifier: LGPL-2.1-or-later
"""Split Body (Modify > Split Body), only real input.

Body1 = rectangle -20..20 x -15..15, extruded 10 (12000), so the origin planes cross it.

  A  nothing selected: the Split Body button opens the dialog waiting for the body; click
     Body1, then the big YZ origin square: the preview splits it at x = 0 into two bodies of
     6000 (Body1 keeps x < 0, the new body x > 0, both 6 faces); OK. Ctrl+Z gives one body
     of 12000 back, Ctrl+Y the two halves.
  B  double-click the Split Body in the timeline, click the Splitting Tool box (the origin
     squares show again), click the XZ square: now split at y = 0 (Body1 keeps y < 0). OK.
  C  Cancel: Split Body, click Body1, click the XY square... the bottom face plane does not
     cut; the reason is in the dialog; Cancel leaves the model unchanged.
  D  a second body (New Body, 25..35 x -5..5, 20 high) as the tool owner: Body1 selected
     first, Split Body, click the face of that body at y = -5 with Extend Splitting Tool off:
     the face does not reach Body1, the reason is shown; tick Extend: the plane y = -5
     splits Body1 (y -15..0) into 4000 (kept) and 2000 (new body). OK.
  E  Esc cancels an open Split Body.
  F  a new design: a box 40 x 30 x 10, a sketch on its top with a line from corner to corner,
     Finish Sketch; Split Body, click the box, click the line: two wedges of 6000 (5 faces).
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


def b_click_box():
    p = s.panel()
    if h.check("edit dialog open", p is not None and p.editing, p):
        h.check("edit: the tool box is the active one", p.active == "tool", p.active)
        h.check("no squares over the part while a tool is picked", p.plane_picker is None)
    s.click_box("tool")


def b_click_xz():
    p = s.panel()
    if p is not None:
        h.check("clicking the box shows the squares", p.plane_picker is not None)
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


# -- F: a sketch line as the splitting tool (a new design) -----------------------------------------
def f_sketch():
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def f_click_top():
    h.click(V(30, 25, 10))


def f_line():
    import Part

    sk = h.in_sketch()
    if h.check("sketch on the top face", sk is not None):
        a = h.to_sketch(sk, V(0, 0, 10))
        b = h.to_sketch(sk, V(40, 30, 10))
        sk.addGeometry(Part.LineSegment(V(a[0], a[1], 0), V(b[0], b[1], 0)))
        App.ActiveDocument.recompute()
        state["line_sketch"] = sk


def f_finish():
    h.ribbon("Finish Sketch")


def f_open():
    h.click_empty()
    h.fit()
    h.ribbon("Split Body")


def f_click_body():
    h.click(V(32, 6, 10))


def f_click_line():
    h.check("the sketch is shown", s.shown(state["line_sketch"]))
    h.click_edge(V(20, 15, 10))


def f_preview():
    p = s.panel()
    if h.check("dialog open", p is not None):
        tool = p.options["tool"]
        h.check(
            "the sketch line is the tool",
            tool is not None and tool[0] is state["line_sketch"],
            tool,
        )
    found = s.bodies()
    h.check("two wedges", len(found) == 2, [b.Label for b in found])
    h.check(
        "6000 each", all(s.close(s.volume(b), 6000) for b in found), [s.volume(b) for b in found]
    )
    h.check(
        "5 faces each",
        all(len(b.Shape.Faces) == 5 for b in found),
        [len(b.Shape.Faces) for b in found],
    )
    h.shot("F-sketch-line")


def f_ok():
    h.task_button("OK")


def f_done():
    h.check("dialog closed", s.panel() is None)
    h.check("two bodies", len(s.bodies()) == 2)


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
        b_click_box,
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
        s.new_design("SplitLine"),
    ]
    + s.box_steps("box", (0, 0, 40, 30), 10, V(12, -8, 0))
    + [
        f_sketch,
        f_click_top,
        f_line,
        f_finish,
        f_open,
        f_click_body,
        f_click_line,
        f_preview,
        f_ok,
        f_done,
    ],
)
