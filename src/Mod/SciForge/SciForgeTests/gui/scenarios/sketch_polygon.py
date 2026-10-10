# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's polygons, with the mouse, without the "how many sides?" pop-up.

SKETCH > CREATE > Polygon > Circumscribed Polygon: 6 sides already, click the
centre, then the middle of an edge (the preview follows that rule while moving).
D on the polygon's construction circle, type 20: that is the size across the flats.
Inscribed Polygon: change Sides to 5 in the panel, click centre and a corner.
Second use of the same command works again. Finish, E: the hexagon prism.

Hand-derived: a regular hexagon with across-flats 20 (apothem a = 10) has area
2*sqrt(3)*a^2 = 346.410...; extruded 10 mm: V = 3464.10...
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si

V = App.Vector
s = {}


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Polygon")
    h.fit()


def create_sketch():
    h.ribbon("Create Sketch")


def pick_xy_plane():
    h.click(V(12, -8, 0))


def open_circumscribed():
    s["sk"] = h.in_sketch()
    h.check("sketch open", s["sk"] is not None)
    si.menu_item("CREATE", "Circumscribed Polygon")


def no_popup():
    h.check("no pop-up asking for sides", not h.popups(), h.popups())
    h.close_popups()
    field = si.sides_field()
    h.check("sides field shown in the panel", field is not None)
    if field is not None:
        h.check("6 sides by default", "6" in field.text(), field.text())


def centre_click():
    si.click(V(0, 0, 0))


def preview_move():
    h.move(h.screen_point(V(14, 3, 0)))
    h.move(h.screen_point(V(12, 0.4, 0)))
    h.move(h.screen_point(V(12, 0, 0)))


def preview_check():
    from sciforge import sketch_mode

    preview = sketch_mode.current().polygon
    h.check("circumscribed preview drawn", preview.node is not None)
    if preview.node is not None:
        pts = [App.Vector(*v.getValue()) for v in preview.coords.point.getValues(0)]
        s["preview"] = [V(p.x, p.y, 0) for p in pts[:-1]]
        mids = [(pts[i] + pts[i + 1]) * 0.5 for i in range(len(pts) - 1)]
        # the pointer snaps to the grid: (12, 0) -> (10, 0)
        best = min(abs(m.y) + abs(m.x - 10.0) for m in mids) if mids else 99
        h.check("preview: the pointer is on the middle of an edge", best < 1e-3, (best, pts))
    h.shot("1-preview")


def edge_click():
    h.click(V(12, 0, 0))


def hexagon_check():
    h.press(QtCore.Qt.Key_Escape)
    sk = s["sk"]
    lines = si.lines(sk)
    h.check("6 lines", len(lines) == 6, len(lines))
    circles = si.circles(sk, construction=True)
    inner = min(circles, key=lambda c: c[1].Radius) if circles else None
    h.check("construction circle inside", inner is not None)
    if inner is not None:
        s["inner"] = inner
        h.check("circle centred on the click", si.vnear(inner[1].Center, V(0, 0, 0), 1e-6))
        for i, g in lines:
            d = g.toShape().distToShape(Part_vertex(V(0, 0, 0)))[0]
            if not si.near(d, inner[1].Radius, 1e-6):
                h.check("every edge touches the circle", False, (i, d, inner[1].Radius))
                break
        mid = (lines[0][1].StartPoint + lines[0][1].EndPoint) * 0.5
        h.check("the click is the middle of an edge (y = 0)", si.near(mid.y, 0.0, 1e-6), mid)
        corners = [g.StartPoint for _, g in lines]
        same = (
            all(min((c - p).Length for p in s.get("preview", [])) < 1e-3 for c in corners)
            and len(s.get("preview", [])) == 6
        )
        h.check("the polygon is the one previewed", same, (corners, s.get("preview")))
    h.check("polygon has 4 degrees of freedom or fewer", sk.solve() == 0)
    h.shot("2-hexagon")


def Part_vertex(p):
    import Part

    return Part.Vertex(p)


def dim_key():
    h.press("d")


def dim_circle():
    i, circle = s["inner"]
    r = circle.Radius
    # towards a corner: the farthest the circle gets from the edges
    a = math.radians(30)
    si.click(circle.Center + V(r * math.cos(a), r * math.sin(a), 0), V(0.3, -0.5, 0))


def dim_place():
    si.click(V(-25, 25, 0))


def dim_type():
    si.type_text("20")


def across_flats():
    h.press(QtCore.Qt.Key_Escape)
    sk = s["sk"]
    i, circle = s["inner"]
    circle = sk.Geometry[i]
    h.check("across flats 20 (circle diameter)", si.near(circle.Radius, 10.0, 1e-6), circle)
    lines = si.lines(sk)
    for _, g in lines:
        if not si.near(g.length(), 20.0 / math.sqrt(3.0), 1e-6):
            h.check("hexagon sides 20/sqrt(3)", False, g.length())
            break
    s["count"] = len(sk.Geometry)


def inscribed_menu():
    si.menu_item("CREATE", "Inscribed Polygon")


def five_sides():
    field = si.sides_field()
    h.check("sides field for the inscribed polygon", field is not None)
    if field is not None:
        si.type_into(field, "5")


def inscribed_centre():
    si.click(V(-40, 0, 0))


def inscribed_corner():
    si.click(V(-40, 10, 0))


def pentagon_check():
    h.press(QtCore.Qt.Key_Escape)
    sk = s["sk"]
    new = list(range(s["count"], len(sk.Geometry)))
    lines = [i for i in new if sk.Geometry[i].TypeId == "Part::GeomLineSegment"]
    circles = [i for i in new if sk.Geometry[i].TypeId == "Part::GeomCircle"]
    h.check("5 sides typed in the panel: 5 lines", len(lines) == 5, len(lines))
    h.check("one construction circle through the corners", len(circles) == 1, circles)
    if circles:
        c = sk.Geometry[circles[0]]
        corner = sk.Geometry[lines[-1]].EndPoint
        h.check("corner on the clicked point", si.vnear(corner, V(-40, 10, 0), 0.6), corner)
        h.check("corners on the circle", si.near((corner - c.Center).Length, c.Radius, 1e-6))
    s["count"] = len(sk.Geometry)


def again():
    si.menu_item("CREATE", "Circumscribed Polygon")


def again_centre():
    si.click(V(40, 0, 0))


def again_edge():
    h.click(V(40, 8, 0))


def again_check():
    h.press(QtCore.Qt.Key_Escape)
    sk = s["sk"]
    new = [i for i in range(s["count"], len(sk.Geometry)) if not sk.getConstruction(i)]
    h.check("second use: another polygon", len(new) >= 5, len(new))
    h.check("no pop-up", not h.popups(), h.popups())


def remove_extra():
    """Undo the last two polygons with Ctrl+Z: the hexagon alone stays (one undo step
    per polygon, plus its auto constraints)."""
    sk = s["sk"]
    for _ in range(6):
        if len([1 for i, _ in si.lines(sk)]) <= 6:
            break
        h.press("z", QtCore.Qt.ControlModifier)


def hexagon_only():
    sk = s["sk"]
    h.check("Ctrl+Z removed the extra polygons", len(si.lines(sk)) == 6, len(si.lines(sk)))


def finish():
    h.ribbon("Finish Sketch")


def extrude():
    h.check("left the sketch", h.in_sketch() is None)
    h.fit()
    h.press("e")


def extrude_ok():
    h.task_button("OK")


def prism_check():
    v = h.solid_volume()
    expected = 2 * math.sqrt(3) * 10.0**2 * 10.0
    h.check("hexagon prism: V = 2*sqrt(3)*10^2*10", si.near(v, expected, 1e-6), (v, expected))
    shape = h.body().Shape
    h.check("8 faces", len(shape.Faces) == 8, len(shape.Faces))
    h.shot("3-prism")


h.run(
    "sketch_polygon",
    [
        new_design,
        create_sketch,
        pick_xy_plane,
        open_circumscribed,
        no_popup,
        centre_click,
        preview_move,
        preview_check,
        edge_click,
        hexagon_check,
        dim_key,
        dim_circle,
        dim_place,
        dim_type,
        across_flats,
        inscribed_menu,
        five_sides,
        inscribed_centre,
        inscribed_corner,
        pentagon_check,
        again,
        again_centre,
        again_edge,
        again_check,
        remove_extra,
        hexagon_only,
        finish,
        extrude,
        extrude_ok,
        prism_check,
    ],
)
