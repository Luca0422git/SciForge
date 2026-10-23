# SPDX-License-Identifier: LGPL-2.1-or-later
"""Press Pull (Q) of two faces of a surface body that face different ways (Fusion's Offset
Face on several faces), real input.

An open box of surfaces (30 x 20 floor, 10 high walls: area 1600). Q, click the front wall
(y = 0), then the right wall (x = 30): both picked. Type 2 outward (the sign follows the
walls' normals, read from the box: they point into it): each wall moves 2 along its own
normal, the floor and the other two walls follow: a 32 x 22 box, area 704 + 640 + 440 =
1784. OK: one "Press Pull" step. Double-click it: both faces read back; 3 outward: 33 x 23,
area 759 + 660 + 460 = 1879; OK. Undo: 1784; Redo: 1879. A refusal: double-click it again,
25 inward: further than the walls next to them reach, said in the dialog; Esc: the box as
it was.
"""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import surface4_steps as s4
from SciForgeTests.gui import surface_steps as st

V = App.Vector
s = {}


def doc():
    return App.ActiveDocument


def outward(distance):
    """The distance to type for `distance` outward (the walls' normals point into the box)."""
    return "%g" % (distance * s["out"])


def box_area(width, depth):
    return width * depth + 2 * width * 10 + 2 * depth * 10


def setup():
    s4.new_design("Surface4PressPullFaces")
    s["box"] = s4.surface_box()
    h.fit()
    h.check("the open box", st.near(st.area(s["box"]), 1600.0), st.area(s["box"]))
    front = next((f for f in s["box"].Shape.Faces if abs(f.CenterOfMass.y) < 1e-6), None)
    h.check("the front wall", front is not None)
    if front is not None:
        u0, u1, v0, v1 = front.ParameterRange
        s["out"] = -1.0 if front.normalAt((u0 + u1) / 2, (v0 + v1) / 2).y > 0 else 1.0
    else:
        s["out"] = -1.0
    st.tab("SURFACE")
    Gui.Selection.clearSelection()
    h.press("q")


def click_front():
    h.click(V(15, 0, 5))


def click_right():
    s4.settle()
    p = s4.panel()
    h.check(
        "the surface Press Pull with the front wall",
        p is not None and p.kind == "surface_press_pull" and len(p.picked) == 1,
        p and p.picked,
    )
    h.click(V(30, 10, 5))


def type_two():
    s4.settle()
    p = s4.panel()
    h.check("both walls picked", p is not None and len(p.picked) == 2, p and p.picked)
    text = s4.message()
    h.check("walls facing different ways are not refused", "different ways" not in text, text)
    s4.type_main(outward(2))


def preview_two():
    s4.settle()
    want = box_area(32, 22)
    h.check("preview: 32 x 22, area 1784", st.near(st.area(s["box"]), want), st.area(s["box"]))
    h.shot("1-two-walls")
    st.ok()


def done():
    h.check("dialog closed", s4.panel() is None)
    h.check("area 1784", st.near(st.area(s["box"]), box_area(32, 22)), st.area(s["box"]))
    bb = s["box"].Shape.BoundBox
    h.check(
        "the box now x 0..32, y -2..20",
        abs(bb.XMax - 32) < 1e-6 and abs(bb.YMin + 2) < 1e-6 and abs(bb.XMin) < 1e-6,
        bb,
    )
    h.check("still 5 faces", s4.faces(s["box"]) == 5, s4.faces(s["box"]))
    titles = st.timeline_titles()
    s["title"] = next((t for t in titles if t.startswith("Press Pull")), None)
    h.check("one Press Pull in the timeline", s["title"] is not None, titles)
    h.check("double-clicked it", st.double_click_timeline(s["title"] or "Press Pull 1"))


def edit_open():
    s4.settle()
    p = s4.panel()
    h.check("edit dialog", p is not None and p.editing)
    h.check("both faces read back", p is not None and len(p.picked) == 2, p and p.picked)
    s4.type_main(outward(3))


def edit_ok():
    s4.settle()
    st.ok()


def edited():
    h.check("area 1879", st.near(st.area(s["box"]), box_area(33, 23)), st.area(s["box"]))
    st.undo()


def undone():
    h.check("undo: 1784", st.near(st.area(s["box"]), box_area(32, 22)), st.area(s["box"]))
    st.redo()


def redone():
    h.check("redo: 1879", st.near(st.area(s["box"]), box_area(33, 23)), st.area(s["box"]))
    st.double_click_timeline(s["title"] or "Press Pull 1")


def too_far():
    s4.settle()
    s4.type_main(outward(-25))


def refused():
    s4.settle()
    text = s4.message()
    h.check("says it is further than the walls reach", "further" in text, text)
    st.esc()


def unchanged():
    s4.settle()
    h.check("Esc closed it", s4.panel() is None)
    h.check("the box as it was", st.near(st.area(s["box"]), box_area(33, 23)), st.area(s["box"]))


h.run(
    "surface4_presspull_faces",
    [
        setup,
        click_front,
        click_right,
        type_two,
        preview_two,
        done,
        edit_open,
        edit_ok,
        edited,
        undone,
        redone,
        too_far,
        refused,
        unchanged,
    ],
)
