# SPDX-License-Identifier: LGPL-2.1-or-later
"""Split Body shows its splitting tool in red (Luca: "the splitting tool should show an
extension of the face it is using to split the body. in red. like fusion"), only real input.

Body1 = rectangle -20..20 x -15..15, extruded 10; Body2 (New Body) = 25..35 x -5..5, 20 high,
beside it. "rim" is split_core.margin of what the red sheet has to cover.

  A  Split Body, click Body1: nothing red yet; click the big YZ square: one red sheet in the
     plane x = 0, over all of Body1 and a rim more, no bigger (not an endless sheet across
     the screen); a pixel just outside Body1 on that plane is red.
  B  clear the Splitting Tool(s) box: the red sheet goes; click Body2's face at y = -5
     (Extend on): the red sheet is now the plane y = -5, over Body1 and that face together;
     still one sheet (the plane before it is gone).
  C  Extend Splitting Tool off: only the face itself is red (25..35 x 0..20), the dialog
     says it does not cut; Extend on again: the whole plane again.
  D  clear the box, click Body2 in the browser: Body2 itself is the red tool (its 6 faces).
  E  clear the box, click the YZ square, OK: no red left in the view.
  F  double-click the Split Body in the timeline: the red YZ sheet shows at once, over the
     whole of Body1 as it was before the split; Cancel: no red left.
  G  Split Body, click Body1, click the XZ square: red; Cancel: no red left. The same with
     Esc.
"""

import FreeCAD as App
from PySide import QtCore, QtGui

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import widget_input as wi

V = App.Vector
TOL = 1e-4
BODY1 = (-20.0, -15.0, 0.0, 20.0, 15.0, 10.0)
FACE = (25.0, -5.0, 0.0, 35.0, -5.0, 20.0)  # Body2's face at y = -5
BODY2 = (25.0, -5.0, 0.0, 35.0, 5.0, 20.0)
state = {}


def body1():
    return s.bodies()[0]


def body2():
    return s.bodies()[1]


def splits():
    return s.steps_of_kind("SplitBody")


def red_nodes():
    from sciforge import cut_preview

    return cut_preview.find()


def red_shape():
    p = s.panel()
    view = getattr(p, "tool_view", None)
    return view.shape if view is not None and view.shown else None


def box_of(shape):
    b = shape.BoundBox
    return (b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax)


def union(a, b):
    return tuple(min(a[i], b[i]) for i in range(3)) + tuple(max(a[i], b[i]) for i in range(3, 6))


def rim(box):
    from sciforge import split_core

    return split_core.margin(box)


def near(a, b):
    return all(abs(x - y) <= TOL for x, y in zip(a, b))


def pixel(point):
    """(r, g, b) of the screen where the 3D point shows (a screen grab: the GL view renders
    under xvfb, the widget's own grab does not see GL output)."""
    pos = h.screen_point(point)
    gl = h.gl_widget()
    at = gl.mapToGlobal(QtCore.QPoint(int(pos.x()), int(pos.y())))
    screen = QtGui.QGuiApplication.primaryScreen()
    image = screen.grabWindow(0).toImage()
    ratio = image.width() / float(max(screen.geometry().width(), 1))
    x = min(max(int(at.x() * ratio), 0), image.width() - 1)
    y = min(max(int(at.y() * ratio), 0), image.height() - 1)
    c = image.pixelColor(x, y)
    return (c.red(), c.green(), c.blue())


def reddish(rgb):
    r, g, b = rgb
    return r > g + 40 and r > b + 40


def red_covers(where, box, plane_axis=None, plane_at=None):
    """The red sheet covers `box` and a rim more, and is not bigger than that (in the two
    directions of its plane; `plane_axis` 0/1/2 is the one it is flat in)."""
    shape = red_shape()
    if not h.check("%s: a red splitting tool is shown" % where, shape is not None):
        return
    got = box_of(shape)
    r = rim(box)
    if plane_axis is not None:
        h.check(
            "%s: flat in its plane" % where,
            abs(got[plane_axis] - plane_at) <= TOL and abs(got[plane_axis + 3] - plane_at) <= TOL,
            got,
        )
    for i in range(3):
        if i == plane_axis:
            continue
        lo, hi = box[i] - r, box[i + 3] + r
        h.check(
            "%s: covers the body and a rim in %s" % (where, "XYZ"[i]),
            abs(got[i] - lo) <= TOL and abs(got[i + 3] - hi) <= TOL,
            (got, lo, hi),
        )


# -- A ----------------------------------------------------------------------------------------
def a_open():
    h.click_empty()
    h.fit()
    h.ribbon("Split Body")


def a_click_body():
    h.click(V(-10, -5, 10))


def a_nothing_red():
    p = s.panel()
    if h.check("Split Body open", p is not None and p.title == "Split Body", p):
        h.check("Body1 picked", p.options["body"] is body1(), p.options)
    h.check("A: no tool yet, nothing red", not red_nodes(), len(red_nodes()))


def a_click_yz():
    pl.click_square("YZ_Plane")


a_click_yz.wait_ms = 800  # the preview is rebuilt a moment after the change


def a_red_plane():
    p = s.panel()
    h.check("A: the YZ plane is the tool", p is not None and p.options["tool"] is not None)
    h.check("A: one red sheet in the view", len(red_nodes()) == 1, len(red_nodes()))
    red_covers("A", BODY1, plane_axis=0, plane_at=0.0)
    h.check("A: preview split in two", len(s.bodies()) == 3, [b.Label for b in s.bodies()])
    # just in front of Body1 (towards the camera), on the plane x = 0
    rgb = pixel(V(0, -15 - rim(BODY1) / 2.0, 5))
    h.check("A: the sheet is drawn red outside the body", reddish(rgb), rgb)
    h.shot("A-red-plane")


# -- B ----------------------------------------------------------------------------------------
def b_clear():
    p = s.panel()
    if p is not None:
        wi.click(p.fields["tool"].clear)


def b_no_tool():
    h.check("B: no tool, nothing red", not red_nodes(), len(red_nodes()))


def b_click_face():
    h.click(V(30, -5, 10))


b_click_face.wait_ms = 800  # the preview is rebuilt a moment after the change


def b_red_face_plane():
    p = s.panel()
    tool = p.options["tool"] if p is not None else None
    h.check("B: Body2's face is the tool", tool is not None and tool[1].startswith("Face"), tool)
    h.check("B: still one red sheet", len(red_nodes()) == 1, len(red_nodes()))
    red_covers("B", union(BODY1, FACE), plane_axis=1, plane_at=-5.0)
    h.shot("B-red-face-extended")


# -- C ----------------------------------------------------------------------------------------
def c_extend_off():
    p = s.panel()
    if p is not None and p.extend.isChecked():
        s.toggle(p.extend)


c_extend_off.wait_ms = 800  # the preview is rebuilt a moment after the change


def c_face_only():
    p = s.panel()
    h.check("C: Extend off", p is not None and not p.extend.isChecked())
    shape = red_shape()
    if h.check("C: the face is still red", shape is not None):
        h.check("C: only the face itself", near(box_of(shape), FACE), box_of(shape))
    if p is not None:
        h.check("C: does not cut, said", "does not cut" in p.message.text(), p.message.text())
    h.shot("C-red-face-only")


def c_extend_on():
    p = s.panel()
    if p is not None and not p.extend.isChecked():
        s.toggle(p.extend)


c_extend_on.wait_ms = 800  # the preview is rebuilt a moment after the change


def c_extended_again():
    red_covers("C", union(BODY1, FACE), plane_axis=1, plane_at=-5.0)


# -- D ----------------------------------------------------------------------------------------
def d_clear():
    b_clear()


def d_click_body2():
    state["body2"] = body2().Label
    s.click_browser_row(state["body2"])


d_click_body2.wait_ms = 800  # the preview is rebuilt a moment after the change


def d_red_body():
    p = s.panel()
    tool = p.options["tool"] if p is not None else None
    h.check("D: Body2 is the tool", tool is not None and tool[0] is body2(), tool)
    shape = red_shape()
    if h.check("D: Body2 is red", shape is not None):
        h.check("D: all of Body2", near(box_of(shape), BODY2), box_of(shape))
        h.check("D: its 6 faces", len(shape.Faces) == 6, len(shape.Faces))
    h.shot("D-red-body")


# -- E ----------------------------------------------------------------------------------------
def e_clear():
    b_clear()


def e_click_yz():
    pl.click_square("YZ_Plane")


e_click_yz.wait_ms = 800  # the preview is rebuilt a moment after the change


def e_red():
    h.check("E: red before OK", len(red_nodes()) == 1, len(red_nodes()))


def e_ok():
    h.task_button("OK")


def e_done():
    h.check("E: dialog closed", s.panel() is None)
    h.check("E: one Split Body step", len(splits()) == 1, splits())
    h.check("E: no red left after OK", not red_nodes(), len(red_nodes()))
    h.shot("E-after-ok")


# -- F ----------------------------------------------------------------------------------------
def f_edit():
    h.fit()
    s.timeline_double_click(splits()[0])


f_edit.wait_ms = 800  # the preview is rebuilt a moment after the change


def f_red_at_once():
    p = s.panel()
    if h.check("F: edit dialog open", p is not None and p.editing, p):
        red_covers("F", BODY1, plane_axis=0, plane_at=0.0)


def f_cancel():
    h.task_button("Cancel")


def f_gone():
    h.check("F: dialog closed", s.panel() is None)
    h.check("F: no red left after Cancel", not red_nodes(), len(red_nodes()))


# -- G ----------------------------------------------------------------------------------------
def g_open():
    h.click_empty()
    h.fit()
    h.ribbon("Split Body")


def g_click_body():
    h.click(V(-10, -10, 10))


def g_click_xz():
    pl.click_square("XZ_Plane")


g_click_xz.wait_ms = 800  # the preview is rebuilt a moment after the change


def g_red():
    h.check("G: red while the tool is picked", len(red_nodes()) == 1, len(red_nodes()))


def g_cancel():
    h.task_button("Cancel")


def g_gone():
    h.check("G: dialog closed", s.panel() is None)
    h.check("G: no red left after Cancel", not red_nodes(), len(red_nodes()))
    h.check("G: still one Split Body step", len(splits()) == 1, splits())


def g_escape():
    h.press(QtCore.Qt.Key_Escape)


def g_escaped():
    h.check("G: Esc closed it", s.panel() is None)
    h.check("G: no red left after Esc", not red_nodes(), len(red_nodes()))


h.run(
    "split_preview",
    [s.new_design("SplitPreview")]
    + s.box_steps("body1", (-20, -15, 20, 15), 10, V(12, -22, 0))
    + s.box_steps("body2", (25, -5, 35, 5), 20, V(5, -24, 0), new_body=True)
    + [
        a_open,
        a_click_body,
        a_nothing_red,
        a_click_yz,
        a_red_plane,
        b_clear,
        b_no_tool,
        b_click_face,
        b_red_face_plane,
        c_extend_off,
        c_face_only,
        c_extend_on,
        c_extended_again,
        d_clear,
        d_click_body2,
        d_red_body,
        e_clear,
        e_click_yz,
        e_red,
        e_ok,
        e_done,
        f_edit,
        f_red_at_once,
        f_cancel,
        f_gone,
        g_open,
        g_click_body,
        g_click_xz,
        g_red,
        g_cancel,
        g_gone,
        g_open,
        g_click_body,
        g_click_xz,
        g_red,
        g_escape,
        g_escaped,
    ],
)
