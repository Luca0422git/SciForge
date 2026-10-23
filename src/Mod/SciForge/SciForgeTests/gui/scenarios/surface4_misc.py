# SPDX-License-Identifier: LGPL-2.1-or-later
"""SURFACE > MODIFY: Align, Combine and Physical Material with a surface body, real input.

An open box of surfaces (30 x 20 floor, walls 10 high: area 1600) and a 20 x 20 x 10 solid
box at x 50 .. 70. SURFACE tab, MODIFY > Align: click the surface box's floor (From), then
the solid's top face (To): the surface box goes onto the solid's top, its floor in that
plane; OK: an "Align" step in the surface body, still a surface of area 1600. Undo, Redo.
MODIFY > Combine: click the surface box (Target), then the solid (Tool): refused, the dialog
says Combine works on solids and to use Stitch or Thicken; Esc. MODIFY > Physical Material:
pick Aluminium, click the surface box's row in the browser: it is made of aluminium (a surface
body has a material, only no mass) and listed under In This Design; OK. MODIFY > Appearance:
pick a look, click the surface box's row: it has that look; OK.
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore
from PySide6 import QtTest

from SciForgeTests.gui import bodies_steps as bs
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import surface4_steps as s4
from SciForgeTests.gui import surface_steps as st

V = App.Vector
s = {}


def doc():
    return App.ActiveDocument


def setup():
    from sciforge import bodies, extrude

    s4.new_design("Surface4Misc")
    s["box"] = s4.surface_box()
    sk = s4.sketch([(50, 0), (70, 0), (70, 20), (50, 20)])
    solid = bodies.body_of(sk)
    extrude.make(solid, sk, {"distance": 10.0})
    doc().recompute()
    bodies.set_shown(sk, False)
    s["solid"] = solid
    h.fit()
    st.tab("SURFACE")
    Gui.Selection.clearSelection()
    st.menu("MODIFY", "Align")


def click_floor():
    p = bs.panel()
    h.check("the Align dialog", p is not None and p.title == "Align", p)
    h.click(V(8, 16, 0))


def click_solid_top():
    p = bs.panel()
    h.check("the surface box moves", p is not None and p.moving is s["box"], p and p.moving)
    h.click(V(60, 10, 10))


def aligned_preview():
    h.idle_step()()
    floor = [f for f in s["box"].Shape.Faces if f.BoundBox.ZLength < 1e-6]
    zs = sorted(round(f.BoundBox.ZMin, 6) for f in floor)
    h.check("the floor lies in the solid's top plane (z 10)", 10.0 in zs, zs)
    h.check("the same area", st.near(st.area(s["box"]), 1600.0), st.area(s["box"]))
    h.shot("1-align")
    h.task_button("OK")


def aligned():
    from sciforge import align, surfmod

    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("still a surface body", surfmod.is_surface_body(s["box"]))
    h.check("an Align step in it", align.is_align(s["box"].Tip), s["box"].Tip.Label)
    s["bb"] = s["box"].Shape.BoundBox
    st.undo()


def undone():
    bb = s["box"].Shape.BoundBox
    h.check("undo: back at z 0 .. 10", abs(bb.ZMin) < 1e-6 and abs(bb.ZMax - 10) < 1e-6, bb)
    st.redo()


def redone():
    bb = s["box"].Shape.BoundBox
    h.check("redo: aligned again", abs(bb.ZMin - s["bb"].ZMin) < 1e-6, bb)
    Gui.Selection.clearSelection()
    h.fit()
    st.menu("MODIFY", "Combine")


def combine_target():
    p = bs.panel()
    h.check("the Combine dialog", p is not None and p.title == "Combine", p)
    box = s["box"].Shape.BoundBox
    h.click(V((box.XMin + box.XMax) / 2, box.YMin, (box.ZMin + box.ZMax) / 2))


def combine_tool():
    h.idle_step()()
    h.click(V(70, 10, 5))


def combine_refused():
    h.idle_step()()
    p = bs.panel()
    text = p.message.text() if p is not None else ""
    h.check("says Combine works on solids, use Stitch", "Stitch" in text, text)
    st.esc()


def combine_closed():
    h.idle_step()()
    h.check("Esc closed it", not Gui.Control.activeDialog())
    h.check("the solid unchanged", st.near(st.volume(s["solid"]), 4000.0))
    Gui.Selection.clearSelection()
    st.menu("MODIFY", "Physical Material")


def pick_aluminium():
    from sciforge import material_ui

    p = bs.panel()
    h.check("the Physical Material dialog", isinstance(p, material_ui.MaterialPanel), p)
    if p is None:
        return
    for i in range(p.library.count()):
        item = p.library.item(i)
        if item.data(QtCore.Qt.UserRole) == "aluminium":
            rect = p.library.visualItemRect(item)
            p.library.scrollToItem(item)
            rect = p.library.visualItemRect(item)
            QtTest.QTest.mouseClick(
                p.library.viewport(), QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, rect.center()
            )
            break


def click_box_body():
    bs.click_browser_row(s["box"].Label)  # (aligned onto the solid, it is behind it here)


def material_given():
    from sciforge import material

    h.idle_step()()
    h.check("the surface body is aluminium", material.key_of(s["box"]) == "aluminium")
    p = bs.panel()
    rows = [p.design.item(i).text() for i in range(p.design.count())] if p is not None else []
    h.check("listed under In This Design", any(s["box"].Label in r for r in rows), rows)
    h.task_button("OK")


def done():
    h.check("dialog closed", not Gui.Control.activeDialog())
    Gui.Selection.clearSelection()
    st.menu("MODIFY", "Appearance")


def pick_look():
    from sciforge import appearance_ui

    p = bs.panel()
    h.check("the Appearance dialog", isinstance(p, appearance_ui.AppearancePanel), p)
    if p is None or p.library.count() < 2:
        return
    item = p.library.item(1)
    s["look"] = item.data(QtCore.Qt.UserRole)
    rect = p.library.visualItemRect(item)
    QtTest.QTest.mouseClick(
        p.library.viewport(), QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, rect.center()
    )


def click_box_row():
    bs.click_browser_row(s["box"].Label)


def look_given():
    from sciforge import appearance

    h.idle_step()()
    look = appearance.get(s["box"]).get("body")
    want = s.get("look") or {}
    h.check(
        "the surface body has the look",
        bool(look) and look.get("label") == want.get("label"),
        (look, want.get("label")),
    )
    h.task_button("OK")


def look_kept():
    h.check("dialog closed", not Gui.Control.activeDialog())


h.run(
    "surface4_misc",
    [
        setup,
        click_floor,
        click_solid_top,
        aligned_preview,
        aligned,
        undone,
        redone,
        combine_target,
        combine_tool,
        combine_refused,
        combine_closed,
        pick_aluminium,
        click_box_body,
        material_given,
        done,
        pick_look,
        click_box_row,
        look_given,
        look_kept,
    ],
)
