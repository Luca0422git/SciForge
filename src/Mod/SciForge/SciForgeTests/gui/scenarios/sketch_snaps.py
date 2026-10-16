# SPDX-License-Identifier: LGPL-2.1-or-later
"""One snapping engine for sketch and projected geometry (sciforge/sketch_infer_core.
snap_points, used by FreeCAD's tools through sketch_infer.py and by SciForge's own tools
through sketch_draw.py), with real mouse moves and clicks a few pixels off the target, as
a hand lands. Luca: "Projected edges should have the same snap points as sketch elements
(endpoint, midpoint)"; "lines are often not connected because it's slightly off the
corner"; "circles and arcs ... should show their middle ... and you should be able to snap
to them".

A block 40 x 30 x 10; Create Sketch on its top face: the face's four edges are projected
(Auto project).
A  Rectangle (R) from 3 px off the projected corner (0, 0) to (10, 10): the corner is
   exactly (0, 0), joined to the projected corner (Coincident); two areas (100, 1100).
B  Line (L) from 3 px off the middle of the projected top edge (20, 30): it starts exactly
   there (Symmetric about the projected edge's ends), down to (20, 18).
C  Circle (C) centre (30, 12), rim (34, 12); L from 3 px off its top quadrant (30, 16) to
   3 px off its centre: exactly on both (on the circle; Coincident with the centre).
D  An arc (reference, centre (10, 22), r 4, upper half); L from 3 px off its middle
   (10, 26): exactly there, on the arc.
E  A line (15, 25) - (27, 25) crossing the line of B: L from 3 px off the crossing
   (20, 25): exactly there, on both lines.
F  SciForge's own Midpoint Line, its middle clicked 3 px off the middle of the projected
   left edge (0, 15): exactly there (Symmetric).
G  Ctrl: L from 3 px off the projected corner (40, 0) with Ctrl held: the point stays
   where the pointer is, nothing joined.
H  Undo takes back B's line with its constraints; Redo brings them back. Finish Sketch:
   valid, no errors.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si

V = App.Vector
s = {}
Z = 10.0
CTRL = QtCore.Qt.ControlModifier
OFF = 3.0  # pixels off the target, as a hand lands


def g(x, y):
    return V(x, y, Z)


def off(x, y, dx=1.0, dy=0.6):
    """3 pixels off the sketch point (x, y), in the direction (dx, dy)."""
    n = math.hypot(dx, dy)
    k = OFF * s["px"] / n
    return g(x + dx * k, y + dy * k)


def cons(sk=None):
    sk = sk or s["sk"]
    return [
        (c.Type, c.First, c.FirstPos, c.Second, c.SecondPos, getattr(c, "Third", -2000))
        for c in sk.Constraints
    ]


def lines():
    return si.lines(s["sk"])


def vertex_at(x, y, tol=1e-9):
    """(geo, pos) of a sketch point of the sketch's own curves exactly at (x, y)."""
    sk = s["sk"]
    for i, geo in enumerate(sk.Geometry):
        for pos in (1, 2, 3):
            try:
                p = sk.getPoint(i, pos)
            except Exception:
                continue
            if abs(p.x - x) <= tol and abs(p.y - y) <= tol:
                return (i, pos)
    return None


def esc():
    h.press(QtCore.Qt.Key_Escape)


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    doc = App.newDocument("SketchSnaps")
    body = doc.addObject("PartDesign::Body", "Body")
    sk = body.newObject("Sketcher::SketchObject", "Sketch")
    sk.AttachmentSupport = [(doc.getObject("XY_Plane"), "")]
    sk.MapMode = "FlatFace"
    h.draw_rectangle(sk, 0, 0, 40, 30)
    pad = body.newObject("PartDesign::Pad", "Extrude")
    pad.Profile = sk
    pad.Length = Z
    doc.recompute()
    sk.Visibility = False
    h.fit()


def create_sketch():
    h.ribbon("Create Sketch")


def click_top():
    h.click(g(33, 24))


def ready():
    sk = h.in_sketch()
    s["sk"] = sk
    h.check("sketch open on the top face", sk is not None)
    if sk is None:
        return
    s["px"] = si.mm_per_pixel(sk)
    ext = list(sk.ExternalGeo)[2:]
    h.check("Auto project: the face's four edges are in the sketch", len(ext) == 4, ext)
    import Sketcher

    defining = [Sketcher.ExternalGeometryFacade(e).testFlag("Defining") for e in ext]
    h.check("... as profile-making (purple) curves", all(defining), defining)
    # the reference arc of D (upper half, centre (10, 22), r 4)
    import Part

    circle = Part.Circle(V(10, 22, 0), V(0, 0, 1), 4.0)
    s["arc"] = sk.addGeometry(Part.ArcOfCircle(circle, 0.0, math.pi), True)
    App.ActiveDocument.recompute()


# == A: rectangle from the projected corner =================================================
def a_key():
    h.press("r")


def a_first():
    si.click(off(0, 0, 1.0, 0.7))


def a_second():
    si.click(g(10, 10))


def a_check():
    esc()
    corner = vertex_at(0.0, 0.0)
    h.check("A: the rectangle's corner is exactly the projected corner", corner is not None)
    joined = [
        c
        for c in cons()
        if c[0] == "Coincident"
        and corner is not None
        and ((c[1], c[2]) == corner and c[3] <= -3 or (c[3], c[4]) == corner and c[1] <= -3)
    ]
    h.check("A: ... joined to it (Coincident with the projected corner)", len(joined) >= 1, cons())
    from sciforge import sketch_regions

    areas = sorted(round(f.Area, 6) for f in sketch_regions.sketch_regions(s["sk"]))
    h.check("A: two areas, the rectangle and the rest of the face", areas == [100.0, 1100.0], areas)
    h.shot("A-corner")


# == B: middle of a projected edge ===========================================================
def b_key():
    h.press("l")


def b_first():
    si.click(off(20, 30, 0.6, -1.0))


def b_second():
    si.click(g(20, 18))


def b_check():
    esc()
    start = vertex_at(20.0, 30.0)
    h.check("B: the line starts exactly at the projected edge's middle", start is not None)
    sym = [c for c in cons() if c[0] == "Symmetric" and c[1] <= -3 and start and c[5] == start[0]]
    h.check("B: ... held there (Symmetric about the projected edge's ends)", len(sym) == 1, cons())
    s["b_line"] = start[0] if start else None


# == C: circle quadrant and centre ===========================================================
def c_key():
    h.press("c")


def c_centre():
    si.click(g(30, 12))


def c_rim():
    si.click(g(34, 12))


def c_line():
    esc()
    s["circle"] = len(s["sk"].Geometry) - 1
    h.press("l")


def c_first():
    si.click(off(30, 16, 1.0, 0.8))


def c_second():
    si.click(off(30, 12, -1.0, 0.5))


def c_check():
    esc()
    sk = s["sk"]
    line = sk.Geometry[-1]
    circle = sk.Geometry[s["circle"]]  # (its centre click lies on a pixel, near (30, 12))
    top = circle.Center + V(0, circle.Radius, 0)
    h.check(
        "C: the line starts exactly on the circle's top quadrant",
        si.vnear(line.StartPoint, top, 1e-9),
        (line, top),
    )
    h.check(
        "C: ... and ends exactly on its centre",
        si.vnear(line.EndPoint, circle.Center, 1e-9),
        (line, circle.Center),
    )
    index = len(sk.Geometry) - 1
    on_circle = [
        c for c in cons() if c[0] == "PointOnObject" and c[1] == index and c[3] == s["circle"]
    ]
    centre = [
        c
        for c in cons()
        if c[0] == "Coincident" and index in (c[1], c[3]) and s["circle"] in (c[1], c[3])
    ]
    h.check("C: on the circle (PointOnObject)", len(on_circle) == 1, cons())
    h.check("C: joined to the centre (Coincident)", len(centre) == 1, cons())


# == D: middle of an arc =====================================================================
def d_key():
    h.press("l")


def d_first():
    si.click(off(10, 26, 0.8, 1.0))


def d_second():
    si.click(g(4, 28))


def d_check():
    esc()
    sk = s["sk"]
    line = sk.Geometry[-1]
    h.check(
        "D: the line starts exactly at the arc's middle",
        si.vnear(line.StartPoint, V(10, 26, 0), 1e-9),
        line,
    )
    index = len(sk.Geometry) - 1
    on_arc = [c for c in cons() if c[0] == "PointOnObject" and c[1] == index and c[3] == s["arc"]]
    h.check("D: ... on the arc (PointOnObject)", len(on_arc) == 1, cons())


# == E: a crossing ===========================================================================
def e_key():
    h.press("l")


def e_first():
    si.click(g(15, 25))


def e_second():
    si.click(g(27, 25))


def e_line():
    esc()
    s["e_cross"] = len(s["sk"].Geometry) - 1
    h.press("l")


def e_start():
    si.click(off(20, 25, 1.0, 0.9))


def e_end():
    si.click(g(26, 21))


def e_check():
    esc()
    sk = s["sk"]
    line = sk.Geometry[-1]
    # where B's line and E's first line cross, as drawn (each point placed on a pixel)
    a, b = sk.Geometry[s["b_line"]], sk.Geometry[s["e_cross"]]
    cross = a.toShape().Curve.intersect(b.toShape().Curve)
    cross = V(cross[0].X, cross[0].Y, 0) if cross else None
    h.check(
        "E: the line starts exactly where the two lines cross",
        cross is not None and si.vnear(line.StartPoint, cross, 1e-9),
        (line, cross),
    )
    index = len(sk.Geometry) - 1
    on = sorted(c[3] for c in cons() if c[0] == "PointOnObject" and c[1] == index and c[2] == 1)
    h.check("E: ... on both lines", on == sorted([s["e_cross"], s["b_line"]]), cons())


# == F: SciForge's own tool ==================================================================
def f_tool():
    si.menu_item("CREATE", "Midpoint Line")


def f_middle():
    si.click(off(0, 15, 1.0, 0.7))


def f_end():
    si.click(g(3, 18))


def f_check():
    esc()
    sk = s["sk"]
    line = si.lines(sk)[-1][1]
    mid = (line.StartPoint + line.EndPoint) * 0.5
    h.check(
        "F: Midpoint Line: its middle exactly on the projected edge's middle",
        si.vnear(mid, V(0, 15, 0), 1e-7),
        (mid, line),
    )
    h.check(
        "F: ... held there (Symmetric)",
        any(c[0] == "Symmetric" and c[1] <= -3 for c in cons()[-6:]),
        cons(),
    )


# == G: Ctrl frees the point =================================================================
def g_key():
    h.press("l")


def g_first():
    s["g_count"] = len(s["sk"].Constraints)
    s["g_pos"] = si.click_held(off(40, 0, -1.0, 0.8), CTRL)


def g_second():
    si.click(g(34, 6))


def g_check():
    esc()
    sk = s["sk"]
    line = sk.Geometry[-1]
    h.check(
        "G: with Ctrl the start is where the pointer was, not on the corner",
        (line.StartPoint - V(40, 0, 0)).Length > 0.5 * OFF * s["px"],
        line,
    )
    index = len(sk.Geometry) - 1
    joined = [
        c for c in cons() if c[0] in ("Coincident", "PointOnObject") and c[1] == index and c[2] == 1
    ]
    h.check("G: ... and joined to nothing", not joined, cons())


# == H: undo / redo, Finish ==================================================================
def h_undo():
    s["h_before"] = (len(s["sk"].Geometry), len(s["sk"].Constraints))
    Gui.runCommand("Std_Undo")


def h_undone():
    sk = s["sk"]
    h.check(
        "H: Undo takes the last line back", len(sk.Geometry) == s["h_before"][0] - 1, sk.Geometry
    )
    Gui.runCommand("Std_Redo")


def h_redone():
    sk = s["sk"]
    h.check(
        "H: Redo brings it back",
        (len(sk.Geometry), len(sk.Constraints)) == s["h_before"],
        (len(sk.Geometry), len(sk.Constraints), s["h_before"]),
    )
    h.check(
        "H: the sketch solves (no conflicts, nothing redundant)",
        not sk.ConflictingConstraints
        and not sk.RedundantConstraints
        and not sk.MalformedConstraints,
        (sk.ConflictingConstraints, sk.RedundantConstraints),
    )
    h.ribbon("Finish Sketch")


def finished():
    sk = s["sk"]
    h.check("left the sketch", h.in_sketch() is None)
    h.check("the sketch is valid", "Invalid" not in sk.State, sk.State)


h.run(
    "sketch_snaps",
    si.watched(
        [
            new_design,
            create_sketch,
            click_top,
            ready,
            a_key,
            a_first,
            a_second,
            a_check,
            b_key,
            b_first,
            b_second,
            b_check,
            c_key,
            c_centre,
            c_rim,
            c_line,
            c_first,
            c_second,
            c_check,
            d_key,
            d_first,
            d_second,
            d_check,
            e_key,
            e_first,
            e_second,
            e_line,
            e_start,
            e_end,
            e_check,
            f_tool,
            f_middle,
            f_end,
            f_check,
            g_key,
            g_first,
            g_second,
            g_check,
            h_undo,
            h_undone,
            h_redone,
            finished,
        ]
    ),
)
