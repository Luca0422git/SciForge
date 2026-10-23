# SPDX-License-Identifier: LGPL-2.1-or-later
"""SURFACE > Patch like a Fusion user, only real input.

Create Sketch on XY: a 20 x 20 square, Finish. SURFACE > Extrude: one click on a side
(Chain Selection takes the four), 10 up: an open square tube. Patch with nothing selected:
the Boundary Edges box waits; one click on a top edge of the tube takes the whole top loop
(Enable Chaining): a flat lid of 400 mm² in a body of its own. Continuity Tangent cannot
be built against flat walls: the dialog says why and OK waits; back to Connected, OK.
Patch the bottom the same way. Create Sketch: a circle r 5, surface-extruded 10 up; Patch
its top circle with Continuity Tangent: a dome (more than pi r² and above the rim). Undo /
Redo. Edit the first Patch from the timeline: Connected read back; Cancel changes
nothing. Refusal: a Patch with Enable Chaining off on one top edge only: "The boundary is
not closed" and OK waits; Cancel. Timeline right-click > Suppress Features on "Patch 1"
(the lid's body's first step): the lid's body is empty, the tube unchanged, nothing red, no
pop-up; Unsuppress Features: the lid is back.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import surface_steps as st

V = App.Vector
PI = math.pi
s = {}


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("SurfacePatch")
    h.fit()


def create_sketch():
    h.ribbon("Create Sketch")


def pick_xy():
    st.open_sketch_clicked(V(12, -8, 0))


def draw_square():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None)
    if sk:
        h.draw_rectangle(sk, 0, 0, 20, 20)
        s["square"] = sk


def finish():
    h.ribbon("Finish Sketch")


def extrude_tube():
    h.fit()
    h.click_empty()
    st.tab("SURFACE")
    st.menu("CREATE", "Extrude")


def click_side():
    h.check("clicked a side of the square", h.click_edge(V(10, 0, 0)))


def chain_took_four():
    p = st.panel()
    h.check(
        "Chain Selection took the four sides",
        p is not None and len(p.picks["profile"]) == 4,
        p.picks["profile"] if p else None,
    )
    st.type_field("distance", "10")


def tube_ok():
    st.settle()
    p = st.panel()
    body = st.step_body(p)
    h.check(
        "an open tube of 4 x 200", body is not None and st.near(st.area(body), 800.0), st.area(body)
    )
    s["tube"] = body
    st.ok()


def patch_nothing_selected():
    h.check("tube made", st.panel() is None and s.get("tube") is not None)
    h.fit()
    st.menu("CREATE", "Patch")


def patch_waits():
    p = st.panel()
    h.check("Patch dialog open", p is not None and p.kind == "patch")
    if p is None:
        return
    h.check("the Boundary Edges box waits", p.active == "boundary", p.active)
    h.check("nothing built yet", p.step is None)
    h.check(
        "Fusion's continuity choices",
        [p.rows["continuity"][0].itemText(i) for i in range(3)]
        == ["Connected", "Tangent", "Curvature"],
    )
    h.check("Enable Chaining on", p.rows["chain"][0].isChecked())
    h.check("Group Edges on", p.rows["group_edges"][0].isChecked())


def click_top_edge():
    h.check("clicked a top edge of the tube", h.click_edge(V(10, 0, 10)))


def lid():
    st.settle()
    p = st.panel()
    if p is None:
        return
    h.check("chaining took the whole top loop", len(p.picks["boundary"]) == 4, p.picks["boundary"])
    body = st.step_body(p)
    h.check("a flat lid of 400", body is not None and st.near(st.area(body), 400.0), st.area(body))
    if body is not None:
        b = body.Shape.BoundBox
        h.check("the lid lies on the top", st.near(b.ZMin, 10.0) and st.near(b.ZMax, 10.0), b)
        h.check("its own body", body is not s["tube"])
    s["lid"] = body
    h.shot("1-lid")


def tangent():
    st.choose("continuity", "Tangent")


def tangent_refused():
    st.settle()
    text = st.message()
    h.check("Tangent against flat walls is explained", "Connected" in text, text)
    st.ok()


def ok_waits():
    h.check("OK waits while it cannot be built", st.panel() is not None)
    st.choose("continuity", "Connected")


def connected_ok():
    st.settle()
    h.check("the lid is back", st.near(st.area(st.step_body()), 400.0), st.area(st.step_body()))
    st.ok()


def bottom_patch():
    h.check("lid made", st.panel() is None)
    st.menu("CREATE", "Patch")


def click_bottom_edge():
    h.check("clicked a bottom edge", h.click_edge(V(10, 0, 0)))


def bottom_ok():
    st.settle()
    p = st.panel()
    body = st.step_body(p)
    h.check("a bottom of 400", body is not None and st.near(st.area(body), 400.0), st.area(body))
    if body is not None:
        h.check("at z 0", st.near(body.Shape.BoundBox.ZMax, 0.0), body.Shape.BoundBox)
    st.ok()


def circle_sketch():  # the sketch of a sloped ring, revolved
    st.tab("SOLID")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xz():
    st.open_sketch_clicked(V(12, 0, 30))  # above the tube: nothing behind that spot


def draw_slope():
    sk = h.in_sketch()
    h.check("sketch open on XZ", sk is not None and sk.AttachmentSupport[0][0].Role == "XZ_Plane")
    if sk:
        st.add_lines(sk, [(10, 0), (5, 3)])  # global (10, 0, 0) -> (5, 0, 3)
        st.add_lines(sk, [(0, 0), (0, 10)])  # the axis: global Z
        s["slope"] = sk


def finish_2():
    h.ribbon("Finish Sketch")


def revolve_ring():
    h.fit()
    h.click_empty()
    st.tab("SURFACE")
    st.menu("CREATE", "Revolve")


def click_slope():
    p = st.panel()
    h.check("Revolve dialog open", p is not None and p.kind == "revolve")
    h.check("clicked the sloped line", h.click_edge(V(7.5, 0, 1.5)))


def axis_waits():
    p = st.panel()
    if p is None:
        return
    h.check("the profile is the sloped line", len(p.picks["profile"]) == 1, p.picks["profile"])
    h.check("the Axis box takes the next click", p.active == "axis", p.active)
    h.check("clicked the axis line", h.click_edge(V(0, 0, 6)))


def full_turn():
    st.choose("type", "Full")


def ring_ok():
    st.settle()
    body = st.step_body()
    expect = PI * (10 + 5) * math.hypot(5, 3)
    h.check(
        "a sloped ring (cone frustum)",
        body is not None and st.near(st.area(body), expect, 1e-5),
        (st.area(body), expect),
    )
    s["ring"] = body
    st.ok()


def dome_patch():
    h.check("ring made", st.panel() is None)
    h.fit()
    st.menu("CREATE", "Patch")


def click_rim():
    h.check("clicked the inner rim", h.click_edge(V(0, -5, 3)))


def dome_tangent():
    st.choose("continuity", "Tangent")


def dome():
    st.settle()
    p = st.panel()
    body = st.step_body(p)
    h.check(
        "a dome: more than a flat disc",
        body is not None and st.area(body) > PI * 25 * 1.05,
        st.area(body),
    )
    if body is not None:
        h.check("rising above the rim", body.Shape.BoundBox.ZMax > 4.0, body.Shape.BoundBox)
    h.shot("2-dome")


def curvature():
    st.choose("continuity", "Curvature")


def curvature_said():
    st.settle()
    from sciforge import surface_geom

    text = st.message()
    if surface_geom.g2_available():
        h.check("curvature dome (patched build)", st.area(st.step_body()) > PI * 25, text)
    else:
        h.check("Curvature on stock FreeCAD is explained", "full build" in text, text)
    st.choose("continuity", "Tangent")


def dome_ok():
    st.settle()
    h.check("tangent dome again", st.area(st.step_body()) > PI * 25 * 1.05, st.area(st.step_body()))
    st.ok()


def undo_dome():
    h.check("dome made", st.panel() is None)
    s["count"] = len(st.surface_bodies())
    st.undo()


def dome_undone():
    h.check("undo removes the dome", len(st.surface_bodies()) == s["count"] - 1)
    st.redo()


def dome_redone():
    h.check("redo brings it back", len(st.surface_bodies()) == s["count"])


def edit_first_patch():
    titles = st.timeline_titles()
    h.check("three Patch steps", sum(1 for t in titles if t.startswith("Patch")) == 3, titles)
    h.check("double-clicked Patch 1", st.double_click_timeline("Patch 1"))


def edit_open():
    p = st.panel()
    h.check("edit dialog open", p is not None and p.editing)
    if p is None:
        return
    h.check("Connected read back", p.options["continuity"] == "connected", p.options)
    h.check("four boundary edges read back", len(p.picks["boundary"]) == 4, p.picks["boundary"])
    st.cancel()


def edit_cancelled():
    h.check("Cancel closed it", st.panel() is None)
    h.check("the lid unchanged", st.near(st.area(s["lid"]), 400.0), st.area(s["lid"]))


def open_boundary_patch():
    st.menu("CREATE", "Patch")


def chaining_off():
    st.toggle_check("chain")
    p = st.panel()
    h.check("Enable Chaining off", p is not None and not p.rows["chain"][0].isChecked())


def click_one_edge():
    h.check("clicked one top edge", h.click_edge(V(20, 10, 10)))


def refused():
    st.settle()
    text = st.message()
    h.check("an open boundary is explained", "not closed" in text, text)
    st.ok()


def still_waits():
    h.check("OK waits", st.panel() is not None)
    st.cancel()


def cancelled():
    from SciForgeTests.gui import timeline_input as tl

    h.check("Cancel closed it", st.panel() is None)
    h.check("no new body", len(st.surface_bodies()) == s["count"], len(st.surface_bodies()))
    h.fit()
    tl.menu("Patch 1", "Suppress Features")


def _no_red(where):
    from sciforge import surface

    steps = [o for o in App.ActiveDocument.Objects if surface.is_surface_step(o)]
    h.check(
        "%s: no step is red" % where,
        all("Invalid" not in list(o.State) and "Error" not in list(o.State) for o in steps),
        [(o.Label, list(o.State)) for o in steps],
    )
    h.check("%s: no error pop-up" % where, not h.popups(), h.popups())


def lid_off():
    from sciforge import bodies
    from SciForgeTests.gui import timeline_input as tl

    h.idle_step()()
    step = s["lid"].Tip
    h.check("Patch 1 is off", step is not None and bodies.is_suppressed(step))
    h.check("the lid's body is empty (Patch 1 is its first step)", st.area(s["lid"]) == 0.0)
    h.check("the tube unchanged", st.near(st.area(s["tube"]), 800.0), st.area(s["tube"]))
    _no_red("Patch 1 suppressed")
    tl.menu("Patch 1", "Unsuppress Features")


def lid_on():
    from sciforge import bodies

    h.idle_step()()
    step = s["lid"].Tip
    h.check("Patch 1 is on", step is not None and not bodies.is_suppressed(step))
    h.check("the lid back: 400", st.near(st.area(s["lid"]), 400.0), st.area(s["lid"]))
    _no_red("Patch 1 unsuppressed")


h.run(
    "surface_patch",
    [
        new_design,
        create_sketch,
        pick_xy,
        draw_square,
        finish,
        extrude_tube,
        click_side,
        chain_took_four,
        tube_ok,
        patch_nothing_selected,
        patch_waits,
        click_top_edge,
        lid,
        tangent,
        tangent_refused,
        ok_waits,
        connected_ok,
        bottom_patch,
        click_bottom_edge,
        bottom_ok,
        circle_sketch,
        pick_xz,
        draw_slope,
        finish_2,
        revolve_ring,
        click_slope,
        axis_waits,
        full_turn,
        ring_ok,
        dome_patch,
        click_rim,
        dome_tangent,
        dome,
        curvature,
        curvature_said,
        dome_ok,
        undo_dome,
        dome_undone,
        dome_redone,
        edit_first_patch,
        edit_open,
        edit_cancelled,
        open_boundary_patch,
        chaining_off,
        click_one_edge,
        refused,
        still_waits,
        cancelled,
        lid_off,
        lid_on,
    ],
)
