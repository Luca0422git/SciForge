# SPDX-License-Identifier: LGPL-2.1-or-later
"""A pattern of bodies, a Combine of its copy into the original, and the history marker
(Luca's report of 2026-10-16, fixpattern_steps.py), only real input:

  A  A 40 x 30 x 10 box; Rectangular Pattern, Pattern Type Bodies along X, Spacing 40,
     Quantity 2: Body2 at x 40..80, touching the original.
  B  MODIFY > Combine: target the original, tool Body2, Join: one 80 x 30 x 10 body (24000),
     Body2 used up. (Before the fix the pattern copied the whole original, so the Combine
     made a dependency cycle: FreeCAD printed "The graph must be a DAG" and the copy grew.)
  C  Extrude 1 edited from the timeline to 15: the copy follows, the Combine too: 36000.
  D  The history marker dragged before the pattern: the pattern and the Combine are rolled
     back, the copy is hidden (Fusion: it does not exist there), the original is 18000.
  E  A boss r 3, 5 high at (8, 8) is added there: the new extrude goes in before the
     pattern in the timeline (Fusion adds a step at the marker), the marker stays before
     the pattern.
  F  The marker dragged to the end: the copy has the boss too (it was made before the
     pattern), the combined body is 2 x (18000 + 45 pi). Back before the pattern and to the
     end once more.

Hand-derived: a boss r 3, 5 high adds 45 pi.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import fixpattern_steps as f
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import pattern_steps as ps
from SciForgeTests.gui import timeline_input as tl

V = App.Vector
BOSS = 45 * math.pi
state = {}


def original():
    return f.original()


def copy_body():
    found = f.copies()
    return found[0] if found else None


def vol(body):
    return s.volume(body) if body is not None else 0.0


# -- A ----------------------------------------------------------------------------------------
def a_start():
    Gui.Selection.clearSelection()
    h.click_empty()
    h.ribbon("Rectangular Pattern")


def a_bodies():
    b.choose(ps.panel().pattern_type, "Bodies")


def a_part():
    h.fit()
    h.click(V(20, 15, 10))


def a_box():
    ps.click_box("direction")


def a_axis():
    h.fit()
    pl.click_on_plane(V(-12, 0, 0))


def a_values():
    p = ps.panel()
    b.choose(p.distribution, "Spacing")
    ps.type_quantity(p.quantity, 2)
    ps.type_value(p.distance_field.widget, "40")


def a_ok():
    h.task_button("OK")


def a_made():
    found = f.copies()
    h.check("one copy body", len(found) == 1, [x.Label for x in found])
    if found:
        bb = found[0].Shape.BoundBox
        h.check("at x 40..80", abs(bb.XMin - 40) < 1e-6 and abs(bb.XMax - 80) < 1e-6, bb)
    f.no_red("pattern")


# -- B ----------------------------------------------------------------------------------------
def b_combine():
    h.click_empty()
    h.fit()
    h.ribbon("Combine")


def b_target():
    h.click(V(10, 15, 10))


def b_tool():
    p = s.panel()
    h.check(
        "the original is the target",
        p is not None and p.options["target"] is original(),
        p and p.options["target"],
    )
    h.click(V(60, 15, 10))


def b_preview():
    p = s.panel()
    h.check(
        "the copy is the tool",
        p is not None and p.options["tools"] == [copy_body()],
        p and p.options["tools"],
    )
    h.check("preview: 24000", s.close(vol(original()), 24000), vol(original()))
    h.task_button("OK")


def b_joined():
    h.check("Combine closed", s.panel() is None)
    h.check("one body 80 x 30 x 10", s.close(vol(original()), 24000), vol(original()))
    h.check("the copy is used up (hidden)", not s.shown(copy_body()))
    f.no_red("combine")


# -- C ----------------------------------------------------------------------------------------
def c_edit():
    h.click_empty()
    ps.timeline_double_click("Extrude 1")


def c_distance():
    p = b.active_panel()
    field = getattr(getattr(p, "distance", None), "widget", None)
    if h.check("the extrude's dialog", field is not None, p):
        s.type_value(field, "15")


def c_ok():
    h.task_button("OK")


def c_edited():
    h.check("the copy follows: 18000", s.close(vol(copy_body()), 18000), vol(copy_body()))
    h.check("combined: 36000", s.close(vol(original()), 36000), vol(original()))
    f.no_red("edit")


# -- D ----------------------------------------------------------------------------------------
def d_marker():
    tl.drag_marker(before_title="Rectangular Pattern 1")


def d_rolled():
    st = tl.states()
    h.check(
        "the pattern is rolled back",
        st.get("Rectangular Pattern 1", ("",))[0] == "rolled_back",
        st,
    )
    h.check("the Combine is rolled back", st.get("Combine 1", ("",))[0] == "rolled_back", st)
    h.check("the copy is hidden", not s.shown(copy_body()))
    h.check("the original as it was: 18000", s.close(vol(original()), 18000), vol(original()))
    h.shot("D-rolled")


# -- E ----------------------------------------------------------------------------------------
def e_sketch():
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def e_top():
    h.click(V(30, 25, 15))


def e_circle():
    sk = h.in_sketch()
    h.check("sketch open on the original's top", sk is not None)
    if sk is not None:
        x, y = h.to_sketch(sk, V(8, 8, 15))
        h.draw_circle(sk, x, y, 3)


def e_finish():
    h.ribbon("Finish Sketch")


def e_extrude():
    h.fit()
    h.press("e")


def e_height():
    p = b.active_panel()
    field = getattr(getattr(p, "distance", None), "widget", None)
    if h.check("extrude dialog open", field is not None):
        s.type_value(field, "5")


def e_ok():
    h.task_button("OK")


def e_added():
    titles = ps.timeline_titles()
    h.check(
        "the new extrude is before the pattern in the timeline",
        "Extrude 2" in titles
        and "Rectangular Pattern 1" in titles
        and titles.index("Extrude 2") < titles.index("Rectangular Pattern 1"),
        titles,
    )
    st = tl.states()
    h.check(
        "the pattern is still after the marker",
        st.get("Rectangular Pattern 1", ("",))[0] == "rolled_back",
        st,
    )
    h.check("the original with the boss", s.close(vol(original()), 18000 + BOSS), vol(original()))
    h.check("the copy still hidden", not s.shown(copy_body()))
    f.no_red("boss at the marker")


# -- F ----------------------------------------------------------------------------------------
def f_marker_end():
    tl.drag_marker(to_end=True)


def f_rolled_forward():
    h.check("the copy has the boss too", s.close(vol(copy_body()), 18000 + BOSS), vol(copy_body()))
    h.check(
        "combined: 2 x (18000 + 45 pi)",
        s.close(vol(original()), 2 * (18000 + BOSS)),
        vol(original()),
    )
    h.check("the copy is used up again (hidden)", not s.shown(copy_body()))
    f.no_red("rolled to the end")
    h.shot("F-end")


def f_marker_back():
    tl.drag_marker(before_title="Rectangular Pattern 1")


def f_back():
    st = tl.states()
    h.check(
        "rolled back again: the pattern after the marker",
        st.get("Rectangular Pattern 1", ("",))[0] == "rolled_back",
        st,
    )
    h.check("rolled back again: the copy hidden", not s.shown(copy_body()))
    h.check(
        "rolled back again: the original with its boss",
        s.close(vol(original()), 18000 + BOSS),
        vol(original()),
    )
    tl.drag_marker(to_end=True)


def f_end_again():
    h.check(
        "at the end again: combined", s.close(vol(original()), 2 * (18000 + BOSS)), vol(original())
    )
    h.check("at the end again: the copy used up (hidden)", not s.shown(copy_body()))
    f.no_red("at the end again")


h.run(
    "fixpattern_marker",
    b.box_steps("FixPatternMarker")
    + [a_start, a_bodies, a_part, a_box, a_axis, a_values, a_ok, a_made]
    + [b_combine, b_target, b_tool, b_preview, b_joined]
    + [c_edit, c_distance, c_ok, c_edited]
    + [d_marker, d_rolled]
    + [e_sketch, e_top, e_circle, e_finish, e_extrude, e_height, e_ok, e_added]
    + [f_marker_end, f_rolled_forward, f_marker_back, f_back, f_end_again],
)
