# SPDX-License-Identifier: LGPL-2.1-or-later
"""SURFACE > MODIFY on surface bodies in a design WITHOUT history (Fusion's direct modelling,
where Fusion offers Merge), real input.

An open box of surfaces (30 x 20 floor, 10 high walls: area 1600) and a strip of surfaces
with two faces in one plane (an extruded polyline 0-10-20 along y = 40 and a turn). The
design's right-click menu: Do Not Capture Design History, Remove History: no timeline.
SURFACE tab, MODIFY > Merge: click the two faces in the plane y = 40, OK: one face (2 faces
left, the same area). Ctrl+Z: 3 faces; Ctrl+Y: 2. Click the box's floor, Del: the face
goes, the hole stays (4 faces, area 1000). Click the edge between the back wall and the
right wall, F, radius 2, OK: rounded (two 2 x 10 strips of the walls become a quarter
cylinder of radius 2: area 1000 - 40 + 10 pi). Then Capture Design History again: the
history is captured, both bodies as they were.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import direct_steps as d
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import surface4_steps as s4
from SciForgeTests.gui import surface_steps as st

V = App.Vector
s = {}


def doc():
    return App.ActiveDocument


def setup():
    from sciforge import bodies, surface

    s4.new_design("Surface4Direct")
    s["box"] = s4.surface_box()
    strip = s4.sketch([(0, 40), (10, 40), (20, 40), (20, 50)], closed=False)
    step = surface.build("extrude", {"refs": s4.edges(strip)}, {"distance": 10.0})
    doc().recompute()
    bodies.set_shown(strip, False)
    s["strip"] = bodies.body_of(step)
    h.fit()
    h.check("the open box", s4.faces(s["box"]) == 5)
    h.check("the strip: 3 faces", s4.faces(s["strip"]) == 3, s4.faces(s["strip"]))
    d.design_menu("Do Not Capture Design History")


def remove_history():
    d.answer_history(remove=True)


def direct_now():
    d.wait_timeline()
    h.check("without history", d.is_direct())
    h.check("no timeline", not d.timeline_shown())
    h.check("the box still 5 faces", s4.faces(s["box"]) == 5, s4.faces(s["box"]))
    h.check("the strip still 3 faces", s4.faces(s["strip"]) == 3, s4.faces(s["strip"]))
    st.tab("SURFACE")
    Gui.Selection.clearSelection()
    st.menu("MODIFY", "Merge")


def merge_first():
    p = s4.panel()
    h.check("the Merge dialog", p is not None and p.kind == "surface_merge")
    h.click(V(5, 40, 5))


def merge_second():
    s4.settle()
    h.click(V(15, 40, 5))


def merge_ok():
    s4.settle()
    text = s4.message()
    h.check("says they become one face", "become one face" in text, text)
    st.ok()


def merged():
    h.idle_step()()
    h.check("dialog closed", s4.panel() is None)
    h.check("2 faces", s4.faces(s["strip"]) == 2, s4.faces(s["strip"]))
    h.check("the same area", st.near(st.area(s["strip"]), 300.0), st.area(s["strip"]))
    h.check("still without history", d.is_direct())
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def undone():
    h.idle_step()()
    h.check("Ctrl+Z: 3 faces again", s4.faces(s["strip"]) == 3, s4.faces(s["strip"]))
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def redone():
    h.idle_step()()
    h.check("Ctrl+Y: merged again", s4.faces(s["strip"]) == 2, s4.faces(s["strip"]))
    Gui.Selection.clearSelection()
    h.click(V(8, 16, 0))


def delete_floor():
    h.check("the floor is selected", bool(Gui.Selection.getSelectionEx()))
    h.press(QtCore.Qt.Key_Delete)


def floor_gone():
    h.idle_step()()
    h.check("4 faces left", s4.faces(s["box"]) == 4, s4.faces(s["box"]))
    h.check("area 1000 (the hole stays)", st.near(st.area(s["box"]), 1000.0), st.area(s["box"]))
    h.check("still without history", d.is_direct())
    Gui.Selection.clearSelection()
    h.click_edge(V(30, 20, 5))


def fillet_key():
    h.check("the edge is selected", bool(Gui.Selection.getSelectionEx()))
    h.press(QtCore.Qt.Key_F)


def fillet_radius():
    s4.settle()
    p = s4.panel()
    h.check(
        "the surface Fillet with the edge",
        p is not None and p.kind == "surface_fillet" and len(p.picked) == 1,
        p and p.picked,
    )
    s4.type_main("2")


def fillet_ok():
    s4.settle()
    st.ok()


def filleted():
    h.idle_step()()
    h.check("dialog closed", s4.panel() is None)
    # the corner's two 2 x 10 strips become a quarter cylinder of radius 2, 10 high
    want = 1000.0 - 2 * 2 * 10 + math.pi * 2 / 2 * 10
    h.check("rounded: the area", st.near(st.area(s["box"]), want, 1e-6), (st.area(s["box"]), want))
    h.check("5 faces (the round one added)", s4.faces(s["box"]) == 5, s4.faces(s["box"]))
    s["area"] = st.area(s["box"])
    d.design_menu("Capture Design History")


def history_back():
    d.wait_timeline()
    h.check("history captured again", not d.is_direct())
    h.check("the box as it was", st.near(st.area(s["box"]), s["area"], 1e-6))
    h.check("the strip as it was", s4.faces(s["strip"]) == 2, s4.faces(s["strip"]))


h.run(
    "surface4_direct",
    [
        setup,
        remove_history,
        direct_now,
        merge_first,
        merge_second,
        merge_ok,
        merged,
        undone,
        redone,
        delete_floor,
        floor_gone,
        fillet_key,
        fillet_radius,
        fillet_ok,
        filleted,
        history_back,
    ],
)
