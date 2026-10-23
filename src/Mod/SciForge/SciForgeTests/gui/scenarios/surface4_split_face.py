# SPDX-License-Identifier: LGPL-2.1-or-later
"""SURFACE > MODIFY > Split Face on a surface body, then Merge of the pieces (the two tools
that undo each other in Fusion), real input.

An open box of surfaces centred on the origin (30 x 20 floor, 10 high walls: area 1600), so
the YZ origin plane crosses its floor. SURFACE tab, MODIFY > Split Face: click the floor,
then the Splitting Tool box and the YZ square: the floor is split at x = 0 (6 faces, the
same area, still a surface body); OK: a "Split Face" step. MODIFY > Merge: click the two
floor halves: "The 2 faces become one face"; OK: 5 faces again. Undo: 6 faces; Redo: 5.
"""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import direct_steps as d
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import surface4_steps as s4
from SciForgeTests.gui import surface_steps as st

V = App.Vector
s = {}


def doc():
    return App.ActiveDocument


def setup():
    from sciforge import bodies, surface

    s4.new_design("Surface4SplitFace")
    sk = s4.sketch([(-15, -10), (15, -10), (15, 10), (-15, 10)])
    walls = surface.build("extrude", {"refs": s4.edges(sk)}, {"distance": 10.0})
    doc().recompute()
    floor = surface.build("patch", {"refs": s4.edges(sk)}, {})
    doc().recompute()
    pieces = [(bodies.body_of(walls), ""), (bodies.body_of(floor), "")]
    stitch = surface.build("stitch", {"refs": pieces}, {})
    doc().recompute()
    bodies.set_shown(sk, False)
    s["box"] = bodies.body_of(stitch)
    h.fit()
    h.check("an open box of 5 faces", s4.faces(s["box"]) == 5, s4.faces(s["box"]))
    h.check("area 1600", st.near(st.area(s["box"]), 1600.0), st.area(s["box"]))
    st.tab("SURFACE")
    Gui.Selection.clearSelection()
    d.ribbon_menu("MODIFY", "Split Face")


def click_floor():
    p = d.panel()
    h.check("the Split Face dialog", p is not None and p.title == "Split Face", p)
    h.click(V(-8, 6, 0))


def tool_box():
    p = d.panel()
    picked = p is not None and p.options["faces"] is not None and len(p.options["faces"][1]) == 1
    h.check("the floor picked", picked, p and p.options.get("faces"))
    d.click_box("tool")


def click_yz():
    p = d.panel()
    h.check("the tool box waits", p is not None and p.active == "tool", p and p.active)
    pl.click_square("YZ_Plane")


def preview():
    from sciforge import surfmod

    st.settle()
    h.idle_step()()
    p = d.panel()
    h.check("YZ plane picked", p is not None and p.options["tool"] is not None)
    h.check("preview: one more face", s4.faces(s["box"]) == 6, s4.faces(s["box"]))
    h.check("the same area", st.near(st.area(s["box"]), 1600.0), st.area(s["box"]))
    h.check("still a surface body", surfmod.is_surface_body(s["box"]))
    text = p.message.text() if p is not None else ""
    h.check("no refusal", not text, text)
    h.shot("1-split-face")
    h.task_button("OK")


def split_done():
    h.idle_step()()
    h.check("dialog closed", d.panel() is None)
    titles = st.timeline_titles()
    h.check("a Split Face step", any(t.startswith("Split Face") for t in titles), titles)
    h.check("6 faces", s4.faces(s["box"]) == 6, s4.faces(s["box"]))
    Gui.Selection.clearSelection()
    st.menu("MODIFY", "Merge")


def merge_first():
    p = s4.panel()
    h.check("the Merge dialog", p is not None and p.kind == "surface_merge")
    h.click(V(-8, 6, 0))


def merge_second():
    s4.settle()
    h.click(V(2, 6, 0))  # the right wall hides the floor past x = 5 in this view


def merge_ok():
    s4.settle()
    text = s4.message()
    h.check("says they become one face", "become one face" in text, text)
    st.ok()


def merged():
    h.idle_step()()
    h.check("dialog closed", s4.panel() is None)
    h.check("5 faces again", s4.faces(s["box"]) == 5, s4.faces(s["box"]))
    h.check("area 1600", st.near(st.area(s["box"]), 1600.0), st.area(s["box"]))
    st.undo()


def undone():
    h.check("undo: the floor in two", s4.faces(s["box"]) == 6, s4.faces(s["box"]))
    st.redo()


def redone():
    h.check("redo: one floor", s4.faces(s["box"]) == 5, s4.faces(s["box"]))


h.run(
    "surface4_split_face",
    [
        setup,
        click_floor,
        tool_box,
        click_yz,
        preview,
        split_done,
        merge_first,
        merge_second,
        merge_ok,
        merged,
        undone,
        redone,
    ],
)
