# SPDX-License-Identifier: LGPL-2.1-or-later
"""Surface part 3, QA: Revolve To with Two Sides that would overlap (refusal, Esc) and
INSPECT > Environmental Map Analysis undone and redone (real input in the dialogs).

The design (built for the scenario): on XZ a line P1 (10, 0) - (10, 10) and the axis line
(0, -3) - (0, 25) (global Z); on XY a line (3, 3) - (12, 12) (half-plane at 45 degrees round
Z); a 10 x 10 x 10 box at x 30.
Path V (overlap): SURFACE > Revolve, click P1, the axis line; Type To, click the YZ plane: a
        quarter turn (157.08); Direction Two Sides, click the 45 degree line: the second side
        would turn 315 degrees the other way, more than a full turn with the first: refused
        with the reason ("overlap"), OK waits; Esc: no revolve, no body added.
Path M (Environmental Map, undo / redo): INSPECT > Environmental Map Analysis, click the box,
        OK: one analysis; Ctrl+Z: gone; Ctrl+Y: back, still Studio at 70 %.
"""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import analysis_steps as a
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import surface_steps as st
from SciForgeTests.gui import timeline_input as tl

V = App.Vector
s = {}
QUARTER = 3.141592653589793 * 10 * 10 / 2


def doc():
    return App.ActiveDocument


def _on(sketch, x, y):
    return sketch.getGlobalPlacement().multVec(V(x, y, 0))


def new_design():
    from sciforge import commands, extrude, sketch_ui

    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Surface3QA4")
    body = commands.ensure_body()
    planes = sketch_ui.origin_planes(body)
    axis = sketch_ui.create_sketch(body, (planes["XZ_Plane"], ""))
    st.add_lines(axis, [(0, -3), (0, 25)])
    st.add_lines(axis, [(10, 0), (10, 10)])
    commands.leave_edit()
    s["axis_sketch"] = axis
    diag = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    st.add_lines(diag, [(3, 3), (12, 12)])
    commands.leave_edit()
    s["diag"] = diag
    base = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    h.draw_rectangle(base, 30, 0, 40, 10)
    extrude.make(body, base, {"distance": 10.0})
    commands.leave_edit()
    doc().recompute()
    s["box"] = body
    s["count"] = len(st.bodies())
    h.fit()


def revolve_menu():
    h.click_empty()
    st.tab("SURFACE")
    st.menu("CREATE", "Revolve")


def profile():
    h.check("Revolve dialog open", st.panel() is not None)
    h.check("clicked P1", h.click_edge(_on(s["axis_sketch"], 10, 5)))


def axis():
    st.settle()
    h.check("clicked the axis line", h.click_edge(_on(s["axis_sketch"], 0, 22)))


def type_to():
    st.settle()
    st.choose("type", "To")


def first_object():
    st.settle()
    p = st.panel()
    h.check("the Object box takes the clicks", p is not None and p.active == "to_object")
    h.fit()
    pl.click_on_plane(V(0, -12, 8))


def quarter():
    st.settle()
    area = st.area(st.step_body())
    h.check("to YZ: a quarter turn (157.08)", st.near(area, QUARTER, 1e-5), area)
    st.choose("direction", "Two Sides")


def second_object():
    st.settle()
    p = st.panel()
    h.check("Object Two takes the clicks", p is not None and p.active == "to_object2")
    h.check("clicked the 45 degree line", h.click_edge(_on(s["diag"], 9, 9)))


def overlap_refused():
    st.settle()
    p = st.panel()
    h.check("two objects", p is not None and len(p.refs()["refs3"]) == 2, p and p.refs())
    text = st.message()
    h.check("refused: the two sides would overlap", "overlap" in text, text)
    st.ok()


def ok_waits():
    st.settle()
    h.check("OK waits", st.panel() is not None)
    st.esc()


def escaped():
    h.check("Esc closed it", st.panel() is None)
    titles = st.timeline_titles()
    h.check("no Revolve in the timeline", not any(t.startswith("Revolve") for t in titles), titles)
    h.check("no body added", len(st.bodies()) == s["count"], st.bodies())
    a.inspect("Environmental Map Analysis")


def envmap_box():
    p = a.panel()
    h.check("Environmental Map dialog open", p is not None)
    h.fit()
    h.click(V(35, 5, 10))


def envmap_ok():
    st.wait(600)
    found = a.analyses("EnvironmentMapAnalysis")
    h.check("an analysis on the box", len(found) == 1, found)
    h.task_button("OK")


def envmap_done():
    h.check("dialog closed", a.panel() is None)
    h.check("one analysis kept", len(a.analyses("EnvironmentMapAnalysis")) == 1)
    tl.undo()


def envmap_undone():
    h.check("Ctrl+Z: no analysis", not a.analyses("EnvironmentMapAnalysis"))
    tl.redo()


def envmap_redone():
    found = a.analyses("EnvironmentMapAnalysis")
    h.check("Ctrl+Y: the analysis back", len(found) == 1, found)
    if found:
        obj = found[0]
        h.check(
            "Studio at 70 %",
            (obj.Environment, obj.ReflectionStrength) == ("Studio", 70),
            (obj.Environment, obj.ReflectionStrength),
        )
    tl.no_popups("the Revolve refusal and the Environmental Map")


h.run(
    "surface3_qa4",
    [
        new_design,
        revolve_menu,
        profile,
        axis,
        type_to,
        first_object,
        quarter,
        second_object,
        overlap_refused,
        ok_waits,
        escaped,
        envmap_box,
        envmap_ok,
        envmap_done,
        envmap_undone,
        envmap_redone,
    ],
)
