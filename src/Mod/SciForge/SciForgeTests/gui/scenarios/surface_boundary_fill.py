# SPDX-License-Identifier: LGPL-2.1-or-later
"""SURFACE > Boundary Fill like a Fusion user, only real input.

A tube: a circle of radius 5 on XY surface-extruded 7 each way (z -7 .. 7). Boundary Fill
with the tube alone: no space is closed, the list says so and OK waits; Cancel.
A cone: on XZ the line (0, 6) - (10, -1.5) (z = 6 (1 - r / 8)) and the axis line, surface
Revolve Full. Boundary Fill: click the tube, the cone and the XY plane (Tools); click the
Cells box: two cells, the one inside the tube under the cone and a ring outside it:
inside = 2 pi int_0^5 r 6 (1 - r / 8) dr = 12 pi (12.5 - 125 / 24) = 274.89, ring =
12 pi (32 - 512 / 24 - 12.5 + 125 / 24) = 127.23. Click the inner cell: a new solid body of
274.89; tick the ring in the list: 402.12; untick it; OK. The surfaces stay (Remove Tools
off). Undo / Redo. Edit from the timeline: the cell reads back; Remove Tools; OK: the
tube and the cone are used up (hidden). Undo: shown again. The SOLID tab's Boundary Fill
opens the same dialog (Esc).
"""

import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import surface_steps as st

V = App.Vector
s = {}
INNER = 12 * math.pi * (12.5 - 125.0 / 24.0)
RING = 12 * math.pi * (32 - 512.0 / 24.0 - 12.5 + 125.0 / 24.0)


def shown(obj):
    from sciforge import bodies

    return bodies.is_shown(obj)


def fill_body():
    p = st.panel()
    from sciforge import surface

    step = p.step if p is not None else None
    if step is None:
        step = next(
            (x for x in App.ActiveDocument.Objects if surface.kind_of(x) == "boundary_fill"), None
        )
    return surface.created_body(step) if step is not None else None


def tick(text_part):
    """Click the tick box of the cells list row whose text has `text_part`."""
    p = st.panel()
    if p is None:
        return False
    for i in range(p.list.count()):
        item = p.list.item(i)
        if text_part in item.text():
            rect = p.list.visualItemRect(item)
            QtTest.QTest.mouseClick(
                p.list.viewport(),
                QtCore.Qt.LeftButton,
                QtCore.Qt.NoModifier,
                QtCore.QPoint(rect.left() + 10, rect.center().y()),
            )
            QtWidgets.QApplication.processEvents()
            return True
    return h.check(
        "a list row with %s" % text_part,
        False,
        [p.list.item(i).text() for i in range(p.list.count())],
    )


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("BoundaryFill")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xy():
    st.open_sketch_clicked(V(12, -8, 0))


def draw_circle():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None)
    if sk:
        st.add_circle(sk, 0, 0, 5)


def finish():
    h.ribbon("Finish Sketch")


def extrude_tube():
    h.fit()
    h.click_empty()
    st.tab("SURFACE")
    st.menu("CREATE", "Extrude")


def click_circle():
    h.check("clicked the circle", h.click_edge(V(0, -5, 0)))
    st.choose("direction", "Symmetric")


def tube_distance():
    st.type_field("distance", "7")


def tube_ok():
    st.settle()
    body = st.step_body()
    h.check(
        "a tube (2 pi 5 14)",
        body is not None and st.near(st.area(body), 140 * math.pi, 1e-5),
        st.area(body),
    )
    s["tube"] = body
    st.ok()


def fill_tube_alone():
    h.check("tube made", st.panel() is None)
    h.fit()
    st.menu("CREATE", "Boundary Fill")


def click_tube_alone():
    p = st.panel()
    h.check("Boundary Fill dialog open", p is not None and p.kind == "boundary_fill")
    h.check(
        "the Tools box waits, planes drawn",
        p is not None and p.active == "tools" and p.planes is not None,
    )
    pl.click_on_plane(V(0, -5, 5))


def nothing_closed():
    st.settle()
    p = st.panel()
    if p is None:
        return
    h.check("the tube is a tool", [x[0] for x in p.picks["tools"]] == [s["tube"]], p.picks)
    rows = [p.list.item(i).text() for i in range(p.list.count())]
    h.check("the list says no space is closed", any("No closed cell" in r for r in rows), rows)
    st.ok()


def ok_waits():
    h.check("OK waits", st.panel() is not None)
    st.cancel()


def cancelled():
    h.check("Cancel closed it", st.panel() is None)
    h.check("no solid", not any(x.Shape.Solids for x in st.bodies()))


def cone_sketch():
    st.tab("SOLID")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xz():
    st.open_sketch_clicked(V(12, 0, 30))  # above the tube: nothing behind that spot


def draw_cone_line():
    sk = h.in_sketch()
    h.check("sketch open on XZ", sk is not None and sk.AttachmentSupport[0][0].Role == "XZ_Plane")
    if sk:
        st.add_lines(sk, [(0, 6), (10, -1.5)])  # z = 6 (1 - r / 8)
        st.add_lines(sk, [(0, -3), (0, 10)])  # the axis: global Z


def finish_2():
    h.ribbon("Finish Sketch")


def revolve_cone():
    h.fit()
    h.click_empty()
    st.tab("SURFACE")
    st.menu("CREATE", "Revolve")


def click_slope():
    h.check("clicked the cone's line", h.click_edge(V(9, 0, -0.75)))


def click_axis():
    p = st.panel()
    h.check(
        "the Axis box takes the next click", p is not None and p.active == "axis", p and p.active
    )
    h.check("clicked the axis line", h.click_edge(V(0, 0, 9)))
    st.choose("type", "Full")


def cone_ok():
    st.settle()
    body = st.step_body()
    h.check(
        "a cone (pi 10 12.5)",
        body is not None and st.near(st.area(body), 125 * math.pi, 1e-5),
        st.area(body),
    )
    s["cone"] = body
    st.ok()


def boundary_fill():
    h.check("cone made", st.panel() is None)
    h.fit()
    st.menu("CREATE", "Boundary Fill")


def click_tube():
    pl.click_on_plane(V(0, -5, 5))


def click_cone():
    pl.click_on_plane(V(9, 0, -0.75))


def click_xy():
    pl.click_square("XY_Plane")  # where the XY square shows


def tools_picked():
    st.settle()
    p = st.panel()
    if p is None:
        return
    tools = p.picks["tools"]
    h.check("three tools", len(tools) == 3, tools)
    h.check(
        "the XY plane among them",
        any(getattr(o, "Role", "") == "XY_Plane" for o, _s in tools),
        tools,
    )
    h.check("two cells found", len(p.cell_data) == 2, [c["size"] for c in p.cell_data])
    sizes = sorted(c["size"] for c in p.cell_data)
    h.check(
        "of 127.23 and 274.89",
        len(sizes) == 2 and st.near(sizes[0], RING, 1e-4) and st.near(sizes[1], INNER, 1e-4),
        (sizes, RING, INNER),
    )
    h.check("OK waits for a cell", "cells" in st.message().lower(), st.message())
    st.click_box("cells")


def click_inner():
    h.shot("1-cells")
    pl.click_on_plane(V(0, 0, 3))


def inner_filled():
    st.settle()
    body = fill_body()
    h.check("one cell chosen", st.panel() is not None and len(st.panel().chosen) == 1)
    h.check("a solid of 274.89", st.near(st.volume(body), INNER, 1e-4), (st.volume(body), INNER))
    s["fill"] = body
    tick("%.1f" % RING)


def ring_ticked():
    st.settle()
    v = st.volume(fill_body())
    h.check("with the ring: 402.12", st.near(v, INNER + RING, 1e-4), (v, INNER + RING))
    h.shot("2-both")
    tick("%.1f" % RING)


def ring_unticked():
    st.settle()
    v = st.volume(fill_body())
    h.check("the ring unticked: 274.89", st.near(v, INNER, 1e-4), v)
    st.ok()


def filled():
    h.check("dialog closed", st.panel() is None)
    titles = st.timeline_titles()
    h.check("Boundary Fill 1 in the timeline", "Boundary Fill 1" in titles, titles)
    body = s["fill"]
    h.check("the solid body", body is not None and st.near(st.volume(body), INNER, 1e-4))
    h.check("its icon is a solid's", st.browser_icon_of(body) == "box", st.browser_icon_of(body))
    h.check("the tools stay", shown(s["tube"]) and shown(s["cone"]))
    st.undo()


def undone():
    h.check("undo: no solid", not any(x.Shape.Solids for x in st.bodies() if not x.Shape.isNull()))
    st.redo()


def redone():
    h.check("redo: 274.89", st.near(st.volume(s["fill"]), INNER, 1e-4), st.volume(s["fill"]))


def edit_fill():
    h.check("double-clicked Boundary Fill 1", st.double_click_timeline("Boundary Fill 1"))


def edit_open():
    st.settle()
    p = st.panel()
    h.check("edit dialog open", p is not None and p.editing and p.kind == "boundary_fill")
    if p is None:
        return
    h.check("three tools read back", len(p.picks["tools"]) == 3, p.picks["tools"])
    h.check("the cell read back", len(p.chosen) == 1, p.chosen)
    st.toggle_check("remove_tools")


def edit_ok():
    st.settle()
    st.ok()


def tools_removed():
    h.check("dialog closed", st.panel() is None)
    h.check(
        "the tube and the cone are used up",
        not shown(s["tube"]) and not shown(s["cone"]),
        (shown(s["tube"]), shown(s["cone"])),
    )
    h.check("the solid stays", st.near(st.volume(s["fill"]), INNER, 1e-4))
    st.undo()


def tools_back():
    h.check("undo: the tools shown again", shown(s["tube"]) and shown(s["cone"]))


def solid_tab_fill():
    st.tab("SOLID")
    st.menu("CREATE", "Boundary Fill")


def solid_tab_dialog():
    p = st.panel()
    h.check("SOLID > Boundary Fill opens the dialog", p is not None and p.kind == "boundary_fill")
    st.esc()


def solid_tab_closed():
    h.check("Esc closed it", st.panel() is None)
    h.check("nothing changed", st.near(st.volume(s["fill"]), INNER, 1e-4))


h.run(
    "surface_boundary_fill",
    [
        new_design,
        pick_xy,
        draw_circle,
        finish,
        extrude_tube,
        click_circle,
        tube_distance,
        tube_ok,
        fill_tube_alone,
        click_tube_alone,
        nothing_closed,
        ok_waits,
        cancelled,
        cone_sketch,
        pick_xz,
        draw_cone_line,
        finish_2,
        revolve_cone,
        click_slope,
        click_axis,
        cone_ok,
        boundary_fill,
        click_tube,
        click_cone,
        click_xy,
        tools_picked,
        click_inner,
        inner_filled,
        ring_ticked,
        ring_unticked,
        filled,
        undone,
        redone,
        edit_fill,
        edit_open,
        edit_ok,
        tools_removed,
        tools_back,
        solid_tab_fill,
        solid_tab_dialog,
        solid_tab_closed,
    ],
)
