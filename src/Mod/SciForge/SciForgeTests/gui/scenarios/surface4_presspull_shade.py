# SPDX-License-Identifier: LGPL-2.1-or-later
"""Press Pull (Q) of a flat face whose neighbour meets it at an angle: the lid of a lampshade
of surfaces, real input.

A lampshade: a circle of radius 10 extruded 10 high with its wall leaning in atan(0.4) (a
cone frustum, radius 6 at the top), a Patch on its top edge (the lid), Stitch. Q, click the
lid, type 2 (its normal points up): the cone is carried on to z = 12 (radius 5.2 there) and
the lid shrinks with it; OK: a "Press Pull" step. Double-click it: type -5: the cone is cut
back to z = 5 (radius 8), the lid grows; OK. Undo, Redo. A refusal: double-click it, 16:
past the cone's tip (z = 25), said in the dialog; Esc keeps -5.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui
import Part

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import surface4_steps as s4
from SciForgeTests.gui import surface_steps as st

V = App.Vector
s = {}


def doc():
    return App.ActiveDocument


def shade_area(height):
    """The frustum from radius 10 at z 0 to radius 10 - 0.4 height at z = height, with its
    lid."""
    r1 = 10 - 0.4 * height
    return math.pi * (10 + r1) * math.sqrt(height**2 + (10 - r1) ** 2) + math.pi * r1**2


def setup():
    from sciforge import bodies, commands, sketch_ui, surface

    s4.new_design("Surface4PressPullShade")
    body = commands.ensure_body()
    planes = sketch_ui.origin_planes(body)
    sk = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    sk.addGeometry(Part.Circle(V(0, 0, 0), V(0, 0, 1), 10))
    s4._leave()
    doc().recompute()
    taper = -math.degrees(math.atan(0.4))
    wall = surface.build("extrude", {"refs": [(sk, "Edge1")]}, {"distance": 10.0, "taper": taper})
    doc().recompute()
    top = s4.edge_name_at(wall, V(0, 6, 10))  # (6, 0, 10) is also on the seam
    lid = surface.build("patch", {"refs": [(wall, top)]}, {})
    doc().recompute()
    refs = [(bodies.body_of(wall), ""), (bodies.body_of(lid), "")]
    stitched = surface.build("stitch", {"refs": refs}, {})
    doc().recompute()
    bodies.set_shown(sk, False)
    s["shade"] = bodies.body_of(stitched)
    h.fit()
    h.check("the lampshade: 2 faces", s4.faces(s["shade"]) == 2, s4.faces(s["shade"]))
    h.check(
        "its area: the frustum and the lid",
        st.near(st.area(s["shade"]), shade_area(10)),
        (st.area(s["shade"]), shade_area(10)),
    )
    st.tab("SURFACE")
    Gui.Selection.clearSelection()
    h.press("q")


def click_lid():
    h.click(V(0, 0, 10))


def type_two():
    s4.settle()
    p = s4.panel()
    h.check(
        "the surface Press Pull with the lid",
        p is not None and p.kind == "surface_press_pull" and len(p.picked) == 1,
        p and p.picked,
    )
    s4.type_main("2")


def preview_up():
    s4.settle()
    text = s4.message()
    h.check("not refused", "angle" not in text and "further" not in text, text)
    h.check(
        "preview: the cone carried on to z = 12",
        st.near(st.area(s["shade"]), shade_area(12)),
        (st.area(s["shade"]), shade_area(12)),
    )
    h.shot("1-lid-up")
    st.ok()


def done():
    h.check("dialog closed", s4.panel() is None)
    bb = s["shade"].Shape.BoundBox
    h.check("the lid at z = 12", abs(bb.ZMax - 12) < 1e-6, bb)
    h.check("still 2 faces", s4.faces(s["shade"]) == 2, s4.faces(s["shade"]))
    lid = next((f for f in s["shade"].Shape.Faces if f.Surface.TypeId == "Part::GeomPlane"), None)
    h.check(
        "the lid's radius 5.2: its area",
        lid is not None and st.near(lid.Area, math.pi * 5.2**2),
        lid and lid.Area,
    )
    titles = st.timeline_titles()
    s["title"] = next((t for t in titles if t.startswith("Press Pull")), None)
    h.check("Press Pull in the timeline", s["title"] is not None, titles)
    st.double_click_timeline(s["title"] or "Press Pull 1")


def edit_down():
    s4.settle()
    p = s4.panel()
    h.check("edit dialog", p is not None and p.editing)
    s4.type_main("-5")


def edit_ok():
    s4.settle()
    st.ok()


def edited():
    h.check(
        "the cone cut back to z = 5",
        st.near(st.area(s["shade"]), shade_area(5)),
        (st.area(s["shade"]), shade_area(5)),
    )
    st.undo()


def undone():
    h.check("undo: z = 12 again", st.near(st.area(s["shade"]), shade_area(12)))
    st.redo()


def redone():
    h.check("redo: z = 5", st.near(st.area(s["shade"]), shade_area(5)))
    st.double_click_timeline(s["title"] or "Press Pull 1")


def past_tip():
    s4.settle()
    s4.type_main("16")


def refused():
    s4.settle()
    text = s4.message()
    h.check("past the cone's tip: further than it reaches", "further" in text, text)
    st.esc()


def unchanged():
    s4.settle()
    h.check("Esc closed it", s4.panel() is None)
    h.check("still z = 5", st.near(st.area(s["shade"]), shade_area(5)))


h.run(
    "surface4_presspull_shade",
    [
        setup,
        click_lid,
        type_two,
        preview_up,
        done,
        edit_down,
        edit_ok,
        edited,
        undone,
        redone,
        past_tip,
        refused,
        unchanged,
    ],
)
