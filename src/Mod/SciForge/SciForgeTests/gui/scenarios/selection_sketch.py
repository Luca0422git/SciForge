# SPDX-License-Identifier: LGPL-2.1-or-later
"""Selection and an open sketch (parity/selection.md): inside a sketch FreeCAD's own
Sketcher handles the mouse; SciForge's box, Select Other and mode keys stay out of the way.
Real input, box 40 x 30 x 10.

  A  Create Sketch on the top face, a 20 x 10 rectangle drawn; a left drag around it draws
     no SciForge box (FreeCAD's Sketcher gets the drag; what it selects is recorded).
  B  a long press on a sketch line opens no Select Other list.
  C  keys 1 / 2 / 3 inside the sketch do not change the selection mode (digits are values
     there); Esc keeps the sketch open.
  D  Finish Sketch: outside, a window around the box selects its faces and edges again,
     and a window around the sketch's curves (Sketch Curves on) selects them as curves.
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import selection_input as si

V = App.Vector
RECT = (10, 10, 30, 20)  # sketch coordinates on the top face
st = {}


def step(fn, wait_ms):
    fn.wait_ms = wait_ms
    return fn


def rect_points_3d():
    """The rectangle's corners in global coordinates (the sketch lies on z = 10)."""
    sk = st.get("sketch")
    if sk is None:
        return [V(10, 10, 10), V(30, 10, 10), V(30, 20, 10), V(10, 20, 10)]
    place = sk.getGlobalPlacement()
    x0, y0, x1, y1 = RECT
    return [place.multVec(V(x, y, 0)) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]


# -- A -------------------------------------------------------------------------------------------
def a_create_sketch():
    h.fit()
    h.click_empty()
    h.ribbon("Create Sketch")


def a_click_top():
    h.click(V(20, 15, 10))


def a_draw():
    sk = h.in_sketch()
    h.check("A a sketch is open on the top face", sk is not None)
    if sk is not None:
        st["sketch"] = sk
        h.draw_rectangle(sk, *RECT)
    h.fit(iso=False)
    st["last_before"] = dict(si.selection_ui().last() or {})


def a_drag_in_sketch():
    si.box_around(rect_points_3d(), margin=20)
    st["sketch_selection"] = si.selected()


def a_check():
    band = si.band()
    h.check("A no SciForge box in a sketch", band is None or not band.isVisible())
    h.check(
        "A SciForge made no selection of its own",
        (si.selection_ui().last() or {}) == st.get("last_before"),
        si.selection_ui().last(),
    )
    h.check("A the sketch is still open", h.in_sketch() is not None)
    # What FreeCAD's own Sketcher did with the drag is recorded for the parity doc.
    App.Console.PrintMessage(
        "[SciForge] selection_sketch: the Sketcher's drag selected %s\n"
        % (st.get("sketch_selection"),)
    )


# -- B -------------------------------------------------------------------------------------------
def b_hold_on_line():
    pts = rect_points_3d()
    mid = (pts[0] + pts[1]) * 0.5  # the bottom line of the rectangle
    st["pos"] = si.hold(mid)


def b_no_list():
    h.check("B a long press in a sketch opens no Select Other list", si.select_other_menu() is None)
    si.let_go(st["pos"])
    Gui.Selection.clearSelection()


# -- C -------------------------------------------------------------------------------------------
def c_keys():
    h.press("3")
    h.press("2")
    h.check(
        "C keys 1 / 2 / 3 do not change the selection mode in a sketch",
        si.selection_ui().mode() == "window",
        si.selection_ui().mode(),
    )
    h.press(QtCore.Qt.Key_Escape)


def c_check():
    h.check("C Esc keeps the sketch open", h.in_sketch() is not None)


# -- D -------------------------------------------------------------------------------------------
def d_finish():
    h.ribbon("Finish Sketch")


def d_box_body():
    h.check("D the sketch is closed", h.in_sketch() is None)
    h.fit()
    box = h.body().Shape.BoundBox
    si.box_around(
        [
            V(x, y, z)
            for x in (box.XMin, box.XMax)
            for y in (box.YMin, box.YMax)
            for z in (box.ZMin, box.ZMax)
        ],
        margin=25,
    )


def d_body_check():
    sel = si.selected_elements()
    faces = {n for n in sel if n.startswith("Face")}
    h.check(
        "D outside the sketch the window selects the box's visible faces again",
        len(faces) == 3,
        sorted(sel),
    )
    sk = st.get("sketch")
    sketch_picks = [
        s for s in Gui.Selection.getSelectionEx() if sk is not None and s.ObjectName == sk.Name
    ]
    h.check(
        "D ... and the sketch's 4 curves (fully inside the window)",
        len(sketch_picks) == 1 and len(sketch_picks[0].SubElementNames) == 4,
        [(s.ObjectName, s.SubElementNames) for s in sketch_picks],
    )
    h.click_empty()
    Gui.runCommand("SciForge_SelectFilterSketchCurves")
    si.box_around(rect_points_3d(), margin=10)


def d_curves_off_check():
    sk = st.get("sketch")
    sketch_picks = [
        s for s in Gui.Selection.getSelectionEx() if sk is not None and s.ObjectName == sk.Name
    ]
    h.check(
        "D with Sketch Curves off a window around the rectangle takes no curve",
        not sketch_picks,
        [(s.ObjectName, s.SubElementNames) for s in sketch_picks],
    )
    Gui.runCommand("SciForge_SelectFilterSketchCurves")
    h.check("D Sketch Curves on again", si.selection_ui().sketch_curves_on())
    h.click_empty()


steps = b.box_steps("SelSketch") + [
    a_create_sketch,
    a_click_top,
    a_draw,
    a_drag_in_sketch,
    a_check,
    step(b_hold_on_line, 1500),
    b_no_list,
    c_keys,
    c_check,
    d_finish,
    d_box_body,
    d_body_check,
    d_curves_off_check,
]

h.run("selection_sketch", steps)
