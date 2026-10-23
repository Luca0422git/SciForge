# SPDX-License-Identifier: LGPL-2.1-or-later
"""SURFACE > MODIFY on a surface body inside a moved component, real input.

An open box of surfaces (30 x 20 floor, walls 10 high: area 1600) made into a component,
and the component moved 40 along X (Fusion: a component carries its own position). SURFACE
tab, MODIFY > Fillet: click the corner edge where it is now (x 70), Radius 2, OK: the corner
of the box in the component is round, and it stays in the component at x 40 .. 70. Q, click
the floor, Distance -4, OK: the walls grow by 4 (the arrow and the result follow the
component's position). Click a wall, Del: it goes (no healing). Undo three times: the box
as it was; Redo three times.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import surface4_steps as s4
from SciForgeTests.gui import surface_steps as st

V = App.Vector
s = {}
AREA = 1600.0
DX = 40.0


def fillet_area(r):
    return AREA - 2 * r * 10 + (math.pi * r / 2) * 10 - (r * r - math.pi * r * r / 4)


def doc():
    return App.ActiveDocument


def setup():
    from sciforge import components

    s4.new_design("Surface4Component")
    s["box"] = s4.surface_box()
    made = components.from_bodies(doc(), [s["box"]], parent=None, label="Tray")
    s["part"] = made[0] if made else None
    if s["part"] is not None:
        s["part"].Placement = App.Placement(V(DX, 0, 0), App.Rotation())
    doc().recompute()
    h.fit()
    h.check("the box is in the component", components.container_of(s["box"]) is s["part"])
    bb = global_box()
    h.check("moved with it: x 40 .. 70", abs(bb.XMin - DX) < 1e-6 and abs(bb.XMax - 70) < 1e-6, bb)
    st.tab("SURFACE")
    Gui.Selection.clearSelection()
    st.menu("MODIFY", "Fillet")


def global_box():
    from sciforge import bodies

    return bodies.global_shape(s["box"]).BoundBox


def click_corner():
    p = s4.panel()
    h.check("the surface Fillet dialog", p is not None and p.kind == "surface_fillet")
    h.click_edge(V(DX + 30, 0, 5))


def radius():
    s4.settle()
    p = s4.panel()
    h.check("the edge picked", p is not None and len(p.picked) == 1, p and p.picked)
    h.check("an arrow at the moved corner", p is not None and len(p.arrows) == 1)
    if p is not None and p.arrows:
        origin = p.arrows[0].origin
        h.check("the arrow is where the corner is now", abs(origin.x - (DX + 30)) < 1e-6, origin)
    s4.type_main("2")


def fillet_ok():
    s4.settle()
    st.ok()


def filleted():
    from sciforge import components

    h.check("dialog closed", s4.panel() is None)
    h.check("round corner", s4.near(st.area(s["box"]), fillet_area(2), 1e-5), st.area(s["box"]))
    h.check("still in the component", components.container_of(s["box"]) is s["part"])
    bb = global_box()
    h.check("still at x 40 .. 70", abs(bb.XMin - DX) < 1e-6 and abs(bb.XMax - 70) < 1e-6, bb)
    Gui.Selection.clearSelection()
    h.press("q")


def click_floor():
    h.click(V(DX + 8, 16, 0))


def distance():
    s4.settle()
    p = s4.panel()
    h.check("the surface Press Pull", p is not None and p.kind == "surface_press_pull")
    s4.type_main("-4")


def press_ok():
    s4.settle()
    st.ok()


def pressed():
    h.check("dialog closed", s4.panel() is None)
    s["after_press"] = st.area(s["box"])
    grow = s["after_press"] - fillet_area(2)
    perimeter = 2 * (30 + 20) - 2 * 2 + math.pi * 2 / 2  # the wall ring round the floor
    h.check("the walls grew by 4", abs(grow - 4 * perimeter) < 1e-4, (grow, 4 * perimeter))
    bb = global_box()
    h.check("the floor at z -4", abs(bb.ZMin + 4) < 1e-6, bb)
    Gui.Selection.clearSelection()
    h.click(V(DX + 15, 20, 5))


def delete_wall():
    h.check("a wall selected", bool(Gui.Selection.getSelectionEx()))
    h.press(QtCore.Qt.Key_Delete)


def deleted():
    h.check("the wall went", s4.faces(s["box"]) == 5, s4.faces(s["box"]))
    st.undo()


def undo_2():
    h.check("undo: the wall is back", s4.faces(s["box"]) == 6, s4.faces(s["box"]))
    st.undo()


def undo_3():
    h.check("undo: the floor back at z 0", abs(global_box().ZMin) < 1e-6, global_box())
    st.undo()


def all_undone():
    h.check("undo: the sharp box", s4.near(st.area(s["box"]), AREA), st.area(s["box"]))
    st.redo()


def redo_2():
    st.redo()


def redo_3():
    st.redo()


def all_redone():
    h.check("redo: the wall gone again", s4.faces(s["box"]) == 5, s4.faces(s["box"]))
    h.check("the floor at z -4", abs(global_box().ZMin + 4) < 1e-6, global_box())


h.run(
    "surface4_component",
    [
        setup,
        click_corner,
        radius,
        fillet_ok,
        filleted,
        click_floor,
        distance,
        press_ok,
        pressed,
        delete_wall,
        deleted,
        undo_2,
        undo_3,
        all_undone,
        redo_2,
        redo_3,
        all_redone,
    ],
)
