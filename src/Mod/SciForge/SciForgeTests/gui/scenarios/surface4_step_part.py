# SPDX-License-Identifier: LGPL-2.1-or-later
"""SURFACE > Delete on a part without history (a STEP file), real input.

A 30 x 20 x 10 box written as a STEP file and imported with FreeCAD's own STEP import: a
plain solid, no body, no history (as a part downloaded from a supplier). SURFACE tab: click
its top face, Del: the part is taken into a body (its base feature holds the solid) and the
top goes without healing: a surface body, an open box of 5 faces, area 2200 - 600 = 1600,
a "Delete Face" step. Ctrl+Z: the plain solid is back (6000); Ctrl+Y: the open box again.
Then click the edge between the front and right walls, F, radius 2, OK: rounded (the walls'
two 2 x 10 strips become a quarter cylinder, the floor's corner is rounded with it: area
1600 - 40 + 10 pi - (4 - pi)).
"""

import math

import FreeCAD as App
import FreeCADGui as Gui
import Part
from PySide import QtCore

from SciForgeTests.gui import direct_steps as d
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import surface4_steps as s4
from SciForgeTests.gui import surface_steps as st

V = App.Vector
s = {}


def doc():
    return App.ActiveDocument


def surface_bodies():
    from sciforge import surfmod

    return [b for b in d.bodies() if surfmod.is_surface_body(b)]


def setup():
    s4.new_design("Surface4StepPart")
    path = d.step_file("box", Part.makeBox(30, 20, 10))
    found = d.import_step(path)
    h.check("one plain solid imported", len(found) == 1, found)
    s["part"] = found[0] if found else None
    h.check("no body yet", not d.bodies(), [b.Label for b in d.bodies()])
    h.fit()
    st.tab("SURFACE")
    Gui.Selection.clearSelection()
    h.click(V(15, 10, 10))


def press_delete():
    h.check("the top face is selected", bool(Gui.Selection.getSelectionEx()), d.selected())
    h.press(QtCore.Qt.Key_Delete)


def opened():
    from sciforge import surfmod

    h.idle_step()()
    found = surface_bodies()
    h.check("the part is a surface body now", len(found) == 1, [b.Label for b in d.bodies()])
    if not found:
        return
    s["body"] = found[0]
    h.check("5 faces", s4.faces(s["body"]) == 5, s4.faces(s["body"]))
    h.check("area 1600 (the top gone)", st.near(st.area(s["body"]), 1600.0), st.area(s["body"]))
    h.check("a surface Delete Face step", surfmod.kind_of(s["body"].Tip) == "surface_delete_face")
    h.check("no plain solid left shown", not [o for o in d.plain_solids() if d.shown(o)])
    h.shot("1-step-part-opened")
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def undone():
    h.idle_step()()
    solids = [o for o in d.plain_solids() if d.shown(o)]
    h.check("Ctrl+Z: the plain solid is back", len(solids) == 1, solids)
    h.check(
        "its volume 6000",
        solids and st.near(solids[0].Shape.Volume, 6000.0),
        solids and solids[0].Shape.Volume,
    )
    h.check("no surface body", not surface_bodies(), [b.Label for b in surface_bodies()])
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def redone():
    h.idle_step()()
    found = surface_bodies()
    h.check("Ctrl+Y: the open box again", len(found) == 1, [b.Label for b in d.bodies()])
    if found:
        s["body"] = found[0]
        h.check("area 1600", st.near(st.area(s["body"]), 1600.0), st.area(s["body"]))
    Gui.Selection.clearSelection()
    h.click_edge(V(30, 0, 5))


def fillet_key():
    h.check("the edge is selected", bool(Gui.Selection.getSelectionEx()), d.selected())
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
    body = s.get("body")
    # the walls' two 2 x 10 strips become a quarter cylinder; the floor's corner is rounded too
    want = 1600.0 - 2 * 2 * 10 + math.pi * 2 / 2 * 10 - (2 * 2 - math.pi * 2 * 2 / 4)
    h.check(
        "rounded: the area", body and st.near(st.area(body), want, 1e-6), body and st.area(body)
    )


h.run(
    "surface4_step_part",
    [
        setup,
        press_delete,
        opened,
        undone,
        redone,
        fillet_key,
        fillet_radius,
        fillet_ok,
        filleted,
    ],
)
