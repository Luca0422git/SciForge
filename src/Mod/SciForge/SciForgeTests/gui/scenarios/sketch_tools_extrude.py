# SPDX-License-Identifier: LGPL-2.1-or-later
"""A closed profile drawn with one of SciForge's own sketch tools is a real profile:
Overall Slot (CREATE > Slot > Overall Slot), click one end, type 40, Tab, 0, Enter
(length and angle), type 10, Enter (width); Esc, Finish Sketch, E, type 10, OK.

Hand-derived: the slot is a 30 x 10 rectangle with two half circles of radius 5:
area = 30 * 10 + pi * 5^2 = 378.5398...; extruded 10: 3785.398...
"""

import math

import FreeCAD as App

from SciForgeTests.gui import arrow_input as arrows
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import sketch_tools_steps as st

V = App.Vector
s = st.s
AREA = 30.0 * 10.0 + math.pi * 5.0**2


def slot_open():
    si.menu_item("CREATE", "Overall Slot")


def slot_first():
    h.check("Overall Slot runs", st.tool_title() == "Overall Slot", st.tool_title())
    st.click(V(-25, 15, 0))
    st.hover(V(15, 16, 0))


def slot_length():
    st.keys("40\t0\n")


def slot_width():
    st.hover(V(-5, 25, 0))
    st.keys("10\n")


slot_width.wait_ms = 800


def slot_check():
    sk = st.sketch()
    st.sketch_ok("overall slot")
    import Part

    edges = [
        g.toShape()
        for i, g in enumerate(sk.Geometry)
        if not sk.getConstruction(i) and not isinstance(g, Part.Point)
    ]
    wires = [Part.Wire(group) for group in Part.sortEdges(edges)] if edges else []
    h.check("one closed outline", len(wires) == 1 and wires[0].isClosed(), len(wires))
    if wires:
        area = Part.Face(wires[0]).Area
        h.check("its area: 30 x 10 + pi 5^2 = 378.54", si.near(area, AREA, 1e-6), (area, AREA))
    st.esc()


def finish():
    h.ribbon("Finish Sketch")


def extrude():
    h.check("left the sketch", h.in_sketch() is None)
    h.fit()
    h.press("e")


def extrude_ok():
    arrows.type_distance("10")
    h.task_button("OK")


def extrude_check():
    v = h.solid_volume()
    h.check("the slot extruded 10: V = 3785.40", si.near(v, AREA * 10.0, 1e-6), (v, AREA * 10))
    h.shot("1-slot-extruded")


h.run(
    "sketch_tools_extrude",
    si.watched(
        st.start_steps("SketchToolsExtrude")
        + [
            slot_open,
            slot_first,
            slot_length,
            slot_width,
            slot_check,
            finish,
            extrude,
            extrude_ok,
            extrude_check,
        ]
    ),
)
