# SPDX-License-Identifier: LGPL-2.1-or-later
"""SURFACE > CREATE > Pattern > Rectangular Pattern and Circular Pattern of a surface body,
real input.

An open box of surfaces (30 x 20 floor, walls 10 high: area 1600). SURFACE tab, CREATE >
Pattern > Rectangular Pattern with nothing picked: the dialog opens on the shown surface body.
Click a wall: the surface body is the object (Pattern Type turns to Bodies). Direction: the X
axis; Spacing 50, Quantity 3: two new surface bodies at x 50 .. 80 and 100 .. 130, each 1600.
OK: a "Rectangular Pattern" step. Undo removes the copies, Redo brings them back. Circular
Pattern of the box about the Z axis, Quantity 4: three more surface bodies, each 1600 (turned
90, 180, 270 degrees). Cancel (Esc) of a third pattern leaves the design as it was.
"""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import pattern_steps as ps
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import surface4_steps as s4
from SciForgeTests.gui import surface_steps as st

V = App.Vector
s = {}


def surfaces():
    from sciforge import bodies

    return [x for x in st.surface_bodies() if bodies.is_shown(x)]


def setup():
    s4.new_design("Surface4Pattern")
    s["box"] = s4.surface_box()
    h.fit()
    st.tab("SURFACE")
    Gui.Selection.clearSelection()
    ps.menu("Rectangular Pattern")


def click_wall():
    p = ps.panel()
    h.check("the Rectangular Pattern dialog", p is not None and p.kind == "rectangular")
    h.click(V(15, 0, 5))


def direction_box():
    p = ps.panel()
    h.check(
        "the surface body is the object",
        p is not None and p.options["objects"] == [(s["box"], "")],
        p and p.options["objects"],
    )
    h.check("Pattern Type Bodies", p is not None and p.pattern_type.currentData() == "bodies")
    ps.click_box("direction")


def x_axis():
    h.fit()
    pl.click_on_plane(V(-12, 0, 0))


def values():
    p = ps.panel()
    if p is None:
        h.check("dialog open", False)
        return
    b.choose(p.distribution, "Spacing")
    ps.type_quantity(p.quantity, 3)
    ps.type_value(p.distance_field.widget, "50")


def preview():
    h.idle_step()()
    found = [x for x in surfaces() if x is not s["box"]]
    h.check("two copies", len(found) == 2, [x.Label for x in found])
    xs = sorted(round(x.Shape.BoundBox.XMin, 6) for x in found)
    h.check("at x 50 and 100", xs == [50.0, 100.0], xs)
    h.check("each 1600", all(st.near(st.area(x), 1600.0) for x in found))
    h.shot("1-rect")
    h.task_button("OK")


def made():
    h.check("dialog closed", not Gui.Control.activeDialog())
    titles = ps.timeline_titles()
    h.check("Rectangular Pattern in the timeline", "Rectangular Pattern 1" in titles, titles)
    h.check("three surface bodies", len(surfaces()) == 3, [x.Label for x in surfaces()])
    st.undo()


def undone():
    h.check("undo: the copies go", len(surfaces()) == 1, [x.Label for x in surfaces()])
    st.redo()


def redone():
    h.check("redo: back", len(surfaces()) == 3, [x.Label for x in surfaces()])
    Gui.Selection.clearSelection()
    h.fit()
    h.click(V(15, 0, 5))


def circular_menu():
    h.check("a wall selected", bool(Gui.Selection.getSelectionEx()))
    ps.menu("Circular Pattern")


def axis_box():
    p = ps.panel()
    h.check(
        "the selected surface body is the object",
        p is not None and p.options["objects"] == [(s["box"], "")],
        p and p.options["objects"],
    )
    ps.click_box("axis")


def z_axis():
    h.fit()
    pl.click_on_plane(V(0, 0, 22))


def quantity():
    p = ps.panel()
    if p is not None:
        ps.type_quantity(p.quantity, 4)


def circular_ok():
    h.idle_step()()
    h.task_button("OK")


def circular_made():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("six surface bodies", len(surfaces()) == 6, [x.Label for x in surfaces()])
    h.check("each 1600", all(st.near(st.area(x), 1600.0) for x in surfaces()))
    s["count"] = len(surfaces())
    Gui.Selection.clearSelection()
    ps.menu("Rectangular Pattern")


def cancel_click():
    h.fit()
    h.click(V(15, 0, 5))


def cancel():
    h.idle_step()()
    st.esc()


def cancelled():
    h.idle_step()()
    h.check("Esc closed it", not Gui.Control.activeDialog())
    h.check("nothing added", len(surfaces()) == s["count"], [x.Label for x in surfaces()])


h.run(
    "surface4_pattern",
    [
        setup,
        click_wall,
        direction_box,
        x_axis,
        values,
        preview,
        made,
        undone,
        redone,
        circular_menu,
        axis_box,
        z_axis,
        quantity,
        circular_ok,
        circular_made,
        cancel_click,
        cancel,
        cancelled,
    ],
)
