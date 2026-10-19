# SPDX-License-Identifier: LGPL-2.1-or-later
"""SURFACE > Sweep, Loft, Ruled, Extend, Patch, Trim with a sketch curve and Untrim, like a
Fusion user, only real input.

Sketch on XY: a path (0, 0) - (0, 40) and a line A (20, -5) - (30, -5). Sketch on XZ: a V
(-5, 5) - (0, 10) - (5, 5) and a line B (20, 10) - (30, 10) (z up).
Sweep: click the V (Chain Selection takes both lines), then the path: a trough of
2 sqrt(50) 40 = 565.69; Distance 0.5: half of it; 1 again; OK.
Loft: click A, then B: a flat strip 10 sqrt(5^2 + 10^2) = 111.80; OK.
Ruled: click the strip's lower edge, type 5 (Tangent): a 10 x 5 band = 50; OK.
Extend: click the strip's upper edge, type 5 (Natural): the strip grows to 161.80; OK.
A third sketch on XY: a square (50, 0) - (80, 30) and a circle at (65, 15) of radius 5.
Patch: click the square (chained): 900; OK. Show the sketch again (its eye in the browser),
Trim: click the circle, then the disc inside it: 900 - 25 pi = 821.46; OK. Untrim the face,
Internal Edges: the hole goes, 900; OK. Undo / Redo the Untrim.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import surface_steps as st
from SciForgeTests.gui import timeline_input as tl

V = App.Vector
s = {}
TROUGH = 2 * math.sqrt(50) * 40
STRIP = 10 * math.sqrt(125)


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("SurfaceMisc")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xy():
    st.open_sketch_clicked(V(12, -8, 0))


def draw_xy():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None)
    if sk:
        st.add_lines(sk, [(0, 0), (0, 40)])
        st.add_lines(sk, [(20, -5), (30, -5)])


def finish():
    h.ribbon("Finish Sketch")


def second_sketch():
    h.fit()
    h.ribbon("Create Sketch")


def pick_xz():
    st.open_sketch_clicked(V(12, 0, 30))


def draw_xz():
    sk = h.in_sketch()
    h.check("sketch open on XZ", sk is not None and sk.AttachmentSupport[0][0].Role == "XZ_Plane")
    if sk:
        st.add_lines(sk, [(-5, 5), (0, 10), (5, 5)])
        st.add_lines(sk, [(20, 10), (30, 10)])


def finish_2():
    h.ribbon("Finish Sketch")


# -- Sweep -----------------------------------------------------------------------------------------
def sweep():
    h.fit()
    h.click_empty()
    st.tab("SURFACE")
    st.menu("CREATE", "Sweep")


def click_v():
    p = st.panel()
    h.check("Sweep dialog open", p is not None and p.kind == "sweep")
    h.check("clicked the V", h.click_edge(V(-2.5, 0, 7.5)))


def click_path():
    p = st.panel()
    if p is None:
        return
    h.check("the chain took both lines of the V", len(p.picks["profile"]) == 2, p.picks["profile"])
    h.check("the Path box takes the next click", p.active == "path", p.active)
    h.check("clicked the path", h.click_edge(V(0, 20, 0)))


def trough():
    st.settle()
    body = st.step_body()
    h.check(
        "a trough of 565.69",
        body is not None and st.near(st.area(body), TROUGH, 1e-5),
        st.area(body),
    )
    s["sweep"] = body
    h.shot("1-sweep")
    st.type_field("distance", "0.5")


def half_trough():
    st.settle()
    h.check(
        "Distance 0.5: half", st.near(st.area(s["sweep"]), TROUGH / 2, 1e-5), st.area(s["sweep"])
    )
    st.type_field("distance", "1")


def sweep_ok():
    st.settle()
    h.check("whole again", st.near(st.area(s["sweep"]), TROUGH, 1e-5))
    st.ok()


def sweep_done():
    h.check("dialog closed", st.panel() is None)
    titles = st.timeline_titles()
    h.check("Sweep 1 in the timeline", "Sweep 1" in titles, titles)


# -- Loft ------------------------------------------------------------------------------------------
def loft():
    second = [x for x in App.ActiveDocument.Objects if x.TypeId == "Sketcher::SketchObject"]
    from sciforge import bodies

    for sk in second:  # the sweep hid its sketches; Fusion users show them again
        if not bodies.is_shown(sk):
            tl.click_eye(sk.Label)
    st.menu("CREATE", "Loft")


def click_a():
    p = st.panel()
    h.check("Loft dialog open", p is not None and p.kind == "loft")
    h.check("clicked line A", h.click_edge(V(25, -5, 0)))


def click_b():
    h.check("clicked line B", h.click_edge(V(25, 0, 10)))


def strip():
    st.settle()
    p = st.panel()
    body = st.step_body()
    h.check("two profiles", p is not None and len(p.groups) == 2, p and p.groups)
    h.check(
        "a strip of 111.80", body is not None and st.near(st.area(body), STRIP, 1e-5), st.area(body)
    )
    s["loft"] = body
    st.ok()


def loft_done():
    h.check("dialog closed", st.panel() is None)
    titles = st.timeline_titles()
    h.check("Loft 1 in the timeline", "Loft 1" in titles, titles)


# -- Ruled -----------------------------------------------------------------------------------------
def ruled():
    from sciforge import bodies

    for sk in [x for x in App.ActiveDocument.Objects if x.TypeId == "Sketcher::SketchObject"]:
        if bodies.is_shown(sk):
            tl.click_eye(sk.Label)  # out of the way: the strip's edges lie on its lines
    st.menu("CREATE", "Ruled")


def click_lower_edge():
    p = st.panel()
    h.check("Ruled dialog open", p is not None and p.kind == "ruled")
    h.check("clicked the strip's lower edge", h.click_edge(V(25, -5, 0)))


def ruled_distance():
    st.settle()
    p = st.panel()
    h.check(
        "an edge of the strip",
        p is not None and len(p.picks["edges"]) == 1 and p.picks["edges"][0][1].startswith("Edge"),
        p and p.picks,
    )
    st.type_field("distance", "5")


def band():
    st.settle()
    body = st.step_body()
    h.check("a 10 x 5 band", body is not None and st.near(st.area(body), 50.0, 1e-5), st.area(body))
    st.ok()


def ruled_done():
    h.check("dialog closed", st.panel() is None)
    titles = st.timeline_titles()
    h.check("Ruled 1 in the timeline", "Ruled 1" in titles, titles)
    st.menu("MODIFY", "Extend")


# -- Extend ----------------------------------------------------------------------------------------
def click_upper_edge():
    p = st.panel()
    h.check("Extend dialog open", p is not None and p.kind == "extend")
    h.check("clicked the strip's upper edge", h.click_edge(V(25, 0, 10)))


def extend_distance():
    st.settle()
    p = st.panel()
    h.check("a free edge", p is not None and len(p.picks["edges"]) == 1, p and p.picks)
    st.type_field("distance", "5")


def extended():
    st.settle()
    v = st.area(s["loft"])
    h.check("the strip grows by 10 x 5", st.near(v, STRIP + 50.0, 1e-5), (v, STRIP + 50))
    h.check("still one flat face", len(s["loft"].Shape.Faces) == 1, len(s["loft"].Shape.Faces))
    st.ok()


def extend_done():
    h.check("dialog closed", st.panel() is None)
    titles = st.timeline_titles()
    h.check("Extend 1 in the timeline", "Extend 1" in titles, titles)


# -- Patch, Trim with a sketch curve, Untrim -------------------------------------------------------
def third_sketch():
    st.tab("SOLID")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xy_3():
    st.open_sketch_clicked(V(12, -8, 0))


def draw_square():
    sk = h.in_sketch()
    h.check("third sketch open", sk is not None)
    if sk:
        st.add_lines(sk, [(50, 0), (80, 0), (80, 30), (50, 30)], closed=True)
        st.add_circle(sk, 65, 15, 5)
        s["sketch3"] = sk


def finish_3():
    h.ribbon("Finish Sketch")


def patch():
    h.fit()
    h.click_empty()
    st.tab("SURFACE")
    st.menu("CREATE", "Patch")


def click_square():
    h.check("clicked the square", h.click_edge(V(65, 0, 0)))


def patch_ok():
    st.settle()
    p = st.panel()
    h.check("four sides chained", p is not None and len(p.picks["boundary"]) == 4, p and p.picks)
    body = st.step_body()
    h.check(
        "a 30 x 30 patch", body is not None and st.near(st.area(body), 900.0, 1e-5), st.area(body)
    )
    s["patch"] = body
    st.ok()


def show_sketch():
    h.check("patch made", st.panel() is None)
    tl.click_eye(s["sketch3"].Label)


def trim():
    from sciforge import bodies

    h.check("the sketch shows again", bodies.is_shown(s["sketch3"]))
    h.fit()
    st.menu("MODIFY", "Trim")


def click_circle():
    h.check("clicked the circle", h.click_edge(V(65, 10, 0)))


def cells():
    st.settle()
    p = st.panel()
    if p is None:
        return
    h.check(
        "the circle is the tool",
        [(o.Name, sub) for o, sub in p.picks["tool"]] == [(s["sketch3"].Name, "Edge5")],
        p.picks["tool"],
    )
    h.check("two cells", len(p.cell_data) == 2, len(p.cell_data))
    h.check("the Remove box takes the clicks", p.active == "cells", p.active)


def click_disc():
    pl.click_on_plane(V(65, 15, 0))


def holed():
    st.settle()
    v = st.area(s["patch"])
    h.check("a hole: 900 - 25 pi", st.near(v, 900 - 25 * math.pi, 1e-5), v)
    h.shot("2-hole")
    st.ok()


def trim_done():
    h.check("dialog closed", st.panel() is None)
    tl.click_eye(s["sketch3"].Label)  # hidden again


def untrim():
    st.menu("MODIFY", "Untrim")


def click_face():
    p = st.panel()
    h.check("Untrim dialog open", p is not None and p.kind == "untrim")
    pl.click_on_plane(V(55, 5, 0))


def internal():
    st.settle()
    p = st.panel()
    h.check("the face picked", p is not None and len(p.picks["faces"]) == 1, p and p.picks)
    st.choose("loop_type", "Internal Edges")


def no_hole():
    st.settle()
    v = st.area(s["patch"])
    h.check("Internal Edges: the hole is gone", st.near(v, 900.0, 1e-5), v)
    st.ok()


def untrim_done():
    h.check("dialog closed", st.panel() is None)
    titles = st.timeline_titles()
    h.check("Untrim 1 in the timeline", "Untrim 1" in titles, titles)
    st.undo()


def untrim_undone():
    v = st.area(s["patch"])
    h.check("undo: the hole is back", st.near(v, 900 - 25 * math.pi, 1e-5), v)
    st.redo()


def untrim_redone():
    v = st.area(s["patch"])
    h.check("redo: no hole", st.near(v, 900.0, 1e-5), v)


h.run(
    "surface_misc",
    [
        new_design,
        pick_xy,
        draw_xy,
        finish,
        second_sketch,
        pick_xz,
        draw_xz,
        finish_2,
        sweep,
        click_v,
        click_path,
        trough,
        half_trough,
        sweep_ok,
        sweep_done,
        loft,
        click_a,
        click_b,
        strip,
        loft_done,
        ruled,
        click_lower_edge,
        ruled_distance,
        band,
        ruled_done,
        click_upper_edge,
        extend_distance,
        extended,
        extend_done,
        third_sketch,
        pick_xy_3,
        draw_square,
        finish_3,
        patch,
        click_square,
        patch_ok,
        show_sketch,
        trim,
        click_circle,
        cells,
        click_disc,
        holed,
        trim_done,
        untrim,
        click_face,
        internal,
        no_hole,
        untrim_done,
        untrim_undone,
        untrim_redone,
    ],
)
