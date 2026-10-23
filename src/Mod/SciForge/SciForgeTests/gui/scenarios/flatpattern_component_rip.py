# SPDX-License-Identifier: LGPL-2.1-or-later
"""Rip Between Points and a flat pattern inside a component, real input only: a sheet metal
tube (40 x 30 x 20, corner radius 2, 1 mm) in its own component "Box". SHEET METAL > Rip,
Type Between Points, a click on the front wall's top edge and on its bottom edge, both
offsets typed 18 (the middle of the 36 mm wall): a 1 mm slot cuts the wall from top to
bottom (20 mm3 gone), OK. Along Edge on a bend's tangent edge is refused ("rip the bend face
instead"). Create Flat Pattern from the right wall: 123 + 4 BA = 132.0478 long (the front
wall in two halves 17.5 long), 4 bends; the Flat Pattern lives in the component and its
browser row is under it."""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import flatpattern_steps as fs
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}
WALL = {"type": "plane", "normal": [0, -1, 0], "at": {"axis": "y", "value": "min"}, "count": 1}
FLAT = 123 + 4 * fs.BA


def setup():
    builder = fs.build("FlatBox", fs.TUBE_STEPS, WALL)
    builder.run({"op": "components_from_bodies", "id": "comp", "bodies": ["e1"], "label": "Box"})
    App.ActiveDocument.recompute()
    s["comp"] = builder.objects["comp"]
    s["volume"] = fs.volume()
    h.fit()


def in_component():
    from sciforge import components, sheetmetal

    h.check("the body is in component Box", components.container_of(fs.body()) is s["comp"])
    h.check("sheet metal", sheetmetal.is_sheet_metal_body(fs.body()))
    fs.tab("sheet_metal")


def rip():
    Gui.Selection.clearSelection()
    h.ribbon("Rip")


def rip_points():
    p = fs.sheet_panel()
    h.check("Rip dialog open", p is not None)
    if p is not None:
        h.check("Between Points offered", fs.choose(p.kind, "Between Points"))


def click_top_edge():
    h.fit()
    h.click_edge(V(20, 0, 20))


def click_bottom_edge():
    h.click_edge(V(20, 0, 0))


def points_picked():
    fs.settle()
    p = fs.sheet_panel()
    h.check(
        "point 1 on an edge", p is not None and p.pick("point1").startswith("Edge"), p and p.picks
    )
    h.check(
        "point 2 on an edge", p is not None and p.pick("point2").startswith("Edge"), p and p.picks
    )
    h.check("offsets shown for points", p is not None and p.offset1.widget.isVisible())


def type_offsets():
    p = fs.sheet_panel()
    if p is not None:
        ui.type_into(p.offset1.widget, "18")
        ui.type_into(p.offset2.widget, "18")


def slot_preview():
    fs.settle()
    v = fs.volume()
    h.check(
        "a 1 mm slot down the front wall (20 mm3)", fs.close(v, s["volume"] - 20), (v, s["volume"])
    )
    h.check("no message", "⚠" not in fs.message(), fs.message())
    h.shot("1-rip-points")


def rip_ok():
    fs.ok()


def ripped():
    fs.settle()
    h.check("Rip closed", not fs.dialog_open())
    s["ripped"] = fs.volume()


def edge_rip():
    Gui.Selection.clearSelection()
    h.ribbon("Rip")


def edge_click():
    h.fit()
    # the right wall's front edge where it meets the corner bend (a tangent edge)
    h.click_edge(V(40, 2, 10))


def edge_refused():
    fs.settle()
    text = fs.message()
    p = fs.sheet_panel()
    picked = p.pick("edge") if p is not None else ""
    h.check("an edge picked", picked.startswith("Edge"), p and p.picks)
    h.check("tangent edge refused: rip the bend face", "bend face" in text, text)
    h.check("no rip step made", p is not None and p.target is None)


def edge_cancel():
    fs.cancel()


def edge_after():
    fs.settle()
    h.check("Cancel: unchanged", fs.close(fs.volume(), s["ripped"]), fs.volume())


def flat():
    Gui.Selection.clearSelection()
    h.ribbon("Create Flat Pattern")


def flat_click():
    h.fit()
    h.click(V(40, 15, 10))


def flat_ok():
    fs.settle()
    text = fs.message()
    h.check("dialog says 132.05 x 20.00", "132.05 x 20.00" in text, text)
    fs.ok()


def flat_made():
    fs.settle()
    from sciforge import components

    fp = fs.flat()
    bb = fs.flat_box(fp)
    h.check("flat 132.0478 long", bb is not None and fs.close(bb.XLength, FLAT), bb)
    h.check("4 bends", fp is not None and fp.BendCount == 4)
    h.check(
        "flat pattern in component Box", fp is not None and components.container_of(fp) is s["comp"]
    )
    h.shot("2-flat")


def finish():
    h.ribbon("Finish Flat Pattern")


def browser_row():
    node = fs.browser_node("flat_pattern")
    h.check("Flat Pattern row in the browser", node is not None)
    comp = fs.browser_node("component")
    inside = comp is not None and any(
        c.get("kind") == "flat_pattern" for c in comp.get("children") or []
    )
    h.check(
        "its row is under the component",
        inside,
        comp and [c.get("kind") for c in comp.get("children") or []],
    )


h.run(
    "flatpattern_component_rip",
    [
        setup,
        in_component,
        rip,
        rip_points,
        click_top_edge,
        click_bottom_edge,
        points_picked,
        type_offsets,
        slot_preview,
        rip_ok,
        ripped,
        edge_rip,
        edge_click,
        edge_refused,
        edge_cancel,
        edge_after,
        flat,
        flat_click,
        flat_ok,
        flat_made,
        finish,
        browser_row,
    ],
)
