# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's 2-Tangent Circle, 3-Tangent Circle and Conic Curve (SciForge's own sketch
tools), with real clicks and keys.

Reference lines are put in the sketch first (y = -35 and x = -75 meeting at (-75, -35);
a 3-4-5 triangle with legs 60 and 45 at (5, -35)).
2-Tangent Circle: click the two lines; the pointer at (-65, -25) gives the circle in that
corner centred on the bisector: centre (-65, -25), radius 10 (both distances exact);
typed radius 6: centre (-69, -29). Tangent to both lines (two Tangent constraints), a
typed radius becomes a Radius dimension. Lines selected before the command count.
3-Tangent Circle: click the triangle's three sides, then near its middle: the incircle,
centre (20, -20), radius (60 + 45 - 75) / 2 = 15; near the corner outside the
hypotenuse: the excircle there, radius s = (60 + 45 + 75) / 2 = 90.
Conic: start (5, 25), end (45, 25), apex (25, 45), type rho 0.7: an exact rational
quadratic B-spline (poles start, apex, end; weights 1, 0.7/0.3, 1), its middle at the
shoulder (25, 39) = chord middle + 0.7 * (apex - chord middle); construction guidelines
from the ends to the apex; the apex weight held by a Weight constraint. Esc halfway
adds nothing.
"""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import sketch_tools_steps as st

V = App.Vector
s = st.s
CLICK = 0.6


def reference():
    import Part

    sk = st.sketch()
    s["l1"] = sk.addGeometry(Part.LineSegment(V(-85, -35, 0), V(-25, -35, 0)))
    s["l2"] = sk.addGeometry(Part.LineSegment(V(-75, -45, 0), V(-75, 15, 0)))
    s["a"] = sk.addGeometry(Part.LineSegment(V(5, -35, 0), V(65, -35, 0)))
    s["b"] = sk.addGeometry(Part.LineSegment(V(5, -35, 0), V(5, 10, 0)))
    s["c"] = sk.addGeometry(Part.LineSegment(V(65, -35, 0), V(5, 10, 0)))
    App.ActiveDocument.recompute()
    s["count"] = len(sk.Geometry)


def distance_to_line(p, geo):
    g = st.sketch().Geometry[geo]
    d = (g.EndPoint - g.StartPoint).normalize()
    v = p - g.StartPoint
    return abs(v.x * d.y - v.y * d.x)


# == 2-Tangent Circle ===================================================================
def t2_open():
    si.menu_item("CREATE", "2-Tangent Circle")


def t2_pick_lines():
    h.check("2-Tangent Circle runs", st.tool_title() == "2-Tangent Circle", st.tool_title())
    st.click(V(-45, -35, 0))
    h.check("the first line is picked", st.tool().picks == [s["l1"]], st.tool().picks)
    st.click(V(-45, -35, 0))
    h.check("the same line again is refused", st.tool().picks == [s["l1"]], st.tool().picks)
    st.click(V(-75, -5, 0))
    h.check("the second line is picked", st.tool().picks == [s["l1"], s["l2"]], st.tool().picks)


def t2_follow():
    st.hover(V(-65, -25, 0))
    curves = st.preview().get("curves", [])
    h.check("the circle follows the pointer", len(curves) == 1 and len(curves[0]) > 20, len(curves))
    f = st.field("radius")
    h.check(
        "the radius box shows about 10",
        f is not None and st.near(f.value or 0, 10.0, CLICK),
        f and f.value,
    )
    h.shot("1-two-tangent")


def t2_place():
    st.click(V(-65, -25, 0), towards=V(0, 0, 0))


def t2_check():
    new = st.new_geometry(s["count"])
    circles = st.of_type(new, "Part::GeomCircle")
    h.check("one circle", len(circles) == 1, [g.TypeId for _, g in new])
    if circles:
        i, c = circles[0]
        h.check("about centre (-65, -25), radius 10", st.vnear(c.Center, V(-65, -25, 0), CLICK))
        for line in (s["l1"], s["l2"]):
            h.check(
                "it touches line %d exactly" % line,
                st.near(distance_to_line(c.Center, line), c.Radius, 1e-6),
                (distance_to_line(c.Center, line), c.Radius),
            )
        tangents = [t for t in st.constraints_of(i) if t[0] == "Tangent"]
        h.check("two Tangent constraints", len(tangents) == 2, st.constraints_of(i))
    h.check("the tool waits for the next circle", st.tool_title() == "2-Tangent Circle")
    st.sketch_ok("2-tangent circle")
    s["count"] = len(st.sketch().Geometry)


def t2_typed():
    st.click(V(-45, -35, 0))
    st.click(V(-75, -5, 0))


def t2_typed_hover():
    """(The pointer passes over the tool's own hint and boxes to the view: a tooltip
    there once swallowed the moves and the circle stayed on the click's side.)"""
    st.hover(V(-55, -15, 0))
    t = st.tool()
    last = t.last.raw if t is not None and t.last is not None else None
    h.check(
        "the pointer is in the corner right of the upright line",
        last is not None and last[0] > -75,
        (last, t and t.step, t and t.picks),
    )


def t2_typed_keys():
    st.keys("6\n")


def t2_typed_check():
    new = st.new_geometry(s["count"])
    circles = st.of_type(new, "Part::GeomCircle")
    h.check("typed: one circle", len(circles) == 1, [g.TypeId for _, g in new])
    if circles:
        i, c = circles[0]
        h.check("typed: radius 6", st.near(c.Radius, 6.0, 1e-6), c.Radius)
        h.check("typed: centre (-69, -29)", st.vnear(c.Center, V(-69, -29, 0), 1e-6), c.Center)
        h.check("typed: a Radius dimension", "Radius" in st.types(st.constraints_of(i)))
    st.sketch_ok("typed 2-tangent circle")
    s["count"] = len(st.sketch().Geometry)
    st.esc()


def t2_preselected():
    """Two lines selected first: the command goes straight to placing the circle."""
    sk = st.sketch()
    Gui.Selection.clearSelection()
    for line in (s["l1"], s["l2"]):
        Gui.Selection.addSelection(sk.Document.Name, sk.Name, "Edge%d" % (line + 1))
    si.menu_item("CREATE", "2-Tangent Circle")


def t2_preselected_check():
    t = st.tool()
    h.check(
        "with two lines selected first, they are the picks",
        t is not None and t.picks == [s["l1"], s["l2"]] and t.step == 2,
        t and (t.picks, t.step),
    )
    st.esc()


# == 3-Tangent Circle ===================================================================
def t3_open():
    si.menu_item("CREATE", "3-Tangent Circle")


def t3_pick():
    h.check("3-Tangent Circle runs", st.tool_title() == "3-Tangent Circle", st.tool_title())
    st.click(V(35, -35, 0))
    st.click(V(5, -15, 0))
    st.click(V(35, -12.5, 0))
    t = st.tool()
    h.check("three lines picked", t is not None and len(t.picks) == 3, t and t.picks)


def t3_hover_inside():
    st.hover(V(18, -22, 0))
    curves = st.preview().get("curves", [])
    h.check("the incircle previews", len(curves) == 1, len(curves))


def t3_place_inside():
    st.click(V(18, -22, 0), towards=V(0, 0, 0))


def t3_check():
    new = st.new_geometry(s["count"])
    circles = st.of_type(new, "Part::GeomCircle")
    h.check("one circle", len(circles) == 1, [g.TypeId for _, g in new])
    if circles:
        i, c = circles[0]
        h.check("the incircle: centre (20, -20)", st.vnear(c.Center, V(20, -20, 0), 1e-6), c.Center)
        h.check("radius 15", st.near(c.Radius, 15.0, 1e-6), c.Radius)
        tangents = [t for t in st.constraints_of(i) if t[0] == "Tangent"]
        h.check("three Tangent constraints", len(tangents) == 3, st.constraints_of(i))
    st.sketch_ok("3-tangent circle")
    s["count"] = len(st.sketch().Geometry)
    h.shot("2-three-tangent")


def t3_excircle():
    st.click(V(35, -35, 0))
    st.click(V(5, -15, 0))
    st.click(V(35, -12.5, 0))
    # beyond the hypotenuse, nearer the excircle's centre (95, 55) than the incircle's
    st.click(V(65, 25, 0), towards=V(0, 0, 0))


def t3_excircle_check():
    new = st.new_geometry(s["count"])
    circles = st.of_type(new, "Part::GeomCircle")
    h.check("the excircle", len(circles) == 1, [g.TypeId for _, g in new])
    if circles:
        c = circles[0][1]
        # opposite the right angle (5, -35): centre (5 + 90, -35 + 90), radius 90
        h.check("excircle radius 90", st.near(c.Radius, 90.0, 1e-6), c.Radius)
        h.check("excircle centre (95, 55)", st.vnear(c.Center, V(95, 55, 0), 1e-6), c.Center)
    s["count"] = len(st.sketch().Geometry)
    st.undo()  # (too big for the rest)
    st.esc()


def t3_undone():
    h.check(
        "one Ctrl+Z took the excircle back",
        len(st.sketch().Geometry) == s["count"] - 1,
        len(st.sketch().Geometry),
    )
    s["count"] = len(st.sketch().Geometry)


# == Conic ===================================================================================
def co_open():
    si.menu_item("CREATE", "Conic Curve")


def co_points():
    h.check("Conic Curve runs", st.tool_title() == "Conic Curve", st.tool_title())
    st.click(V(5, 25, 0))
    st.click(V(45, 25, 0))
    st.click(V(25, 45, 0))
    t = st.tool()
    h.check("three points placed, rho next", t is not None and t.step == 3, t and t.step)


def co_rho_hover():
    st.hover(V(25, 31, 0))  # rho 0.3 under the pointer
    f = st.field("rho")
    h.check(
        "the rho box follows the pointer",
        f is not None and st.near(f.value, 0.3, 0.05),
        f and f.value,
    )
    h.shot("3-conic-rho")


def co_rho_type():
    st.keys("0.7\n")


def co_check():
    sk = st.sketch()
    new = st.new_geometry(s["count"])
    splines = st.of_type(new, "Part::GeomBSplineCurve")
    h.check("one conic (a B-spline)", len(splines) == 1, [g.TypeId for _, g in new])
    if not splines:
        return
    i, bs = splines[0]
    s["conic"] = i
    h.check("degree 2, three poles", bs.Degree == 2 and bs.NbPoles == 3, (bs.Degree, bs.NbPoles))
    poles = bs.getPoles()
    h.check(
        "poles start, apex, end where clicked",
        st.vnear(poles[0], V(5, 25, 0), CLICK)
        and st.vnear(poles[1], V(25, 45, 0), CLICK)
        and st.vnear(poles[2], V(45, 25, 0), CLICK),
        poles,
    )
    w = bs.getWeights()
    h.check(
        "weights 1, 0.7/0.3, 1",
        st.near(w[1] / w[0], 0.7 / 0.3, 1e-6) and st.near(w[0], w[2], 1e-9),
        w,
    )
    m = (poles[0] + poles[2]) * 0.5
    shoulder = m + (poles[1] - m) * 0.7
    middle = bs.value((bs.FirstParameter + bs.LastParameter) / 2.0)
    h.check(
        "its middle is the shoulder at rho 0.7",
        st.vnear(middle, shoulder, 1e-6),
        (middle, shoulder),
    )
    guides = st.of_type(new, "Part::GeomLineSegment", construction=True)
    h.check("two construction guidelines to the apex", len(guides) == 2, len(guides))
    weights = [c for c in sk.Constraints if c.Type == "Weight"]
    h.check(
        "the apex weight is held (Weight constraint)",
        any(st.near(c.Value, 0.7 / 0.3, 1e-6) for c in weights),
        [c.Value for c in weights],
    )
    st.sketch_ok("conic")
    s["count"] = len(sk.Geometry)


def co_esc_halfway():
    st.click(V(-45, 35, 0))
    st.click(V(-25, 35, 0))
    st.esc()


def co_esc_check():
    h.check(
        "Esc halfway adds nothing",
        len(st.sketch().Geometry) == s["count"],
        len(st.sketch().Geometry),
    )
    h.check("Esc ends the tool", st.tool() is None)


def finish():
    h.ribbon("Finish Sketch")


def finished():
    h.check("the sketch closes", h.in_sketch() is None)


h.run(
    "sketch_tools_circles",
    si.watched(
        st.start_steps("SketchToolsCircles")
        + [
            reference,
            t2_open,
            t2_pick_lines,
            t2_follow,
            t2_place,
            t2_check,
            t2_typed,
            t2_typed_hover,
            t2_typed_keys,
            t2_typed_check,
            t2_preselected,
            t2_preselected_check,
            t3_open,
            t3_pick,
            t3_hover_inside,
            t3_place_inside,
            t3_check,
            t3_excircle,
            t3_excircle_check,
            t3_undone,
            co_open,
            co_points,
            co_rho_hover,
            co_rho_type,
            co_check,
            co_esc_halfway,
            co_esc_check,
            finish,
            finished,
        ]
    ),
)
