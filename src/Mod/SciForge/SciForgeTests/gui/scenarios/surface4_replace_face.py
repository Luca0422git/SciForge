# SPDX-License-Identifier: LGPL-2.1-or-later
"""SURFACE > MODIFY > Replace Face on a surface body, real input.

An open box of surfaces (0..30 x 0..20 floor, 10 high walls: area 1600), a low block
40..60 x 0..20 x 4 and a tall block 70..90 x 0..20 x 14 (solids, Extrude). SURFACE tab,
MODIFY > Replace Face: click the box's floor, then the Target Faces box and the low block's
top: the floor goes up to z = 4 and the walls are cut back to it (area 600 + 2 x 30 x 6 +
2 x 20 x 6 = 1200), still a surface body; OK: a "Replace Face" step. Undo: 1600; Redo:
1200. Double-click it, clear the target, click the tall block's top (z = 14, above the
walls' top): the reason is said in the dialog; Cancel: still 1200. Edit again: a roller
(a cylinder of radius 42 along x, beside the blocks) as the target: the floor becomes a piece
of its surface, arched, and the walls are cut back to it; OK.
"""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import direct_steps as d
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import surface4_steps as s4
from SciForgeTests.gui import surface_steps as st
from SciForgeTests.gui import widget_input as wi

V = App.Vector
s = {}


def doc():
    return App.ActiveDocument


def block(x0, x1, height):
    from sciforge import bodies, extrude

    body = bodies.new_body(doc(), "Block")
    sk = s4.sketch([(x0, 0), (x1, 0), (x1, 20), (x0, 20)], body=body)
    extrude.make(body, sk, {"distance": height})
    doc().recompute()
    bodies.set_shown(sk, False)
    return body


def cylinder():
    """A cylinder of radius 42 along x (x 100..130), its axis at y = 10, z = -40: its top at
    z = 2."""
    import Part

    from sciforge import bodies, extrude, sketch_ui

    body = bodies.new_body(doc(), "Roller")
    planes = sketch_ui.origin_planes(body)
    sk = sketch_ui.create_sketch(body, (planes["YZ_Plane"], ""))
    sk.AttachmentOffset = App.Placement(V(0, 0, 100), App.Rotation())
    sk.addGeometry(Part.Circle(V(10, -40, 0), V(0, 0, 1), 42))
    s4._leave()
    doc().recompute()
    extrude.make(body, sk, {"distance": 30.0})
    doc().recompute()
    bodies.set_shown(sk, False)
    return body


def setup():
    s4.new_design("Surface4ReplaceFace")
    s["box"] = s4.surface_box()
    s["low"] = block(40, 60, 4.0)
    s["tall"] = block(70, 90, 14.0)
    s["roller"] = cylinder()
    h.fit()
    bb = s["roller"].Shape.BoundBox  # a round body's box is a little loose: 0.1
    h.check(
        "the roller x 100..130, its top at z = 2",
        abs(bb.XMin - 100) < 0.1 and abs(bb.XMax - 130) < 0.1 and abs(bb.ZMax - 2) < 0.1,
        bb,
    )
    h.check("the open box", st.near(st.area(s["box"]), 1600.0), st.area(s["box"]))
    h.check("the low block", st.near(st.volume(s["low"]), 1600.0), st.volume(s["low"]))
    h.check("the tall block", st.near(st.volume(s["tall"]), 5600.0), st.volume(s["tall"]))
    st.tab("SURFACE")
    Gui.Selection.clearSelection()
    d.ribbon_menu("MODIFY", "Replace Face")


def click_floor():
    p = d.panel()
    h.check("the Replace Face dialog", p is not None and p.title == "Replace Face", p)
    h.click(V(8, 16, 0))


def target_box():
    p = d.panel()
    picked = p is not None and p.options["faces"] is not None and len(p.options["faces"][1]) == 1
    h.check("the floor picked", picked, p and p.options.get("faces"))
    d.click_box("target")


def click_low_top():
    h.click(V(50, 15, 4))


def preview():
    from sciforge import surfmod

    st.settle()
    h.idle_step()()
    h.check(
        "preview: the floor at z = 4, area 1200",
        st.near(st.area(s["box"]), 1200.0),
        (st.area(s["box"]), d.message()),
    )
    h.check("still a surface body", surfmod.is_surface_body(s["box"]))
    h.shot("1-replace-face")
    h.task_button("OK")


def done():
    h.idle_step()()
    h.check("dialog closed", d.panel() is None)
    bb = s["box"].Shape.BoundBox
    h.check("the box now z 4..10", abs(bb.ZMin - 4) < 1e-6 and abs(bb.ZMax - 10) < 1e-6, bb)
    h.check("5 faces", s4.faces(s["box"]) == 5, s4.faces(s["box"]))
    titles = st.timeline_titles()
    s["title"] = next((t for t in titles if t.startswith("Replace Face")), None)
    h.check("a Replace Face step", s["title"] is not None, titles)
    st.undo()


def undone():
    h.check("undo: 1600", st.near(st.area(s["box"]), 1600.0), st.area(s["box"]))
    st.redo()


def redone():
    h.check("redo: 1200", st.near(st.area(s["box"]), 1200.0), st.area(s["box"]))
    h.fit()
    h.check("double-clicked it", ui.double_click_timeline(s["title"] or "Replace Face 1"))


def clear_target():
    p = d.panel()
    if not h.check("the edit dialog", p is not None and p.editing, p):
        return
    wi.click(p.fields["target"].clear)


def click_tall_top():
    h.click(V(80, 15, 14))


def refused():
    st.settle()
    h.idle_step()()
    msg = d.message()
    h.check("the reason is said: beyond the walls", "beyond the faces" in msg, msg)
    h.task_button("Cancel")


def cancelled():
    h.idle_step()()
    h.check("dialog closed", d.panel() is None)
    h.check("cancel: still 1200", st.near(st.area(s["box"]), 1200.0), st.area(s["box"]))
    h.check("double-clicked it again", ui.double_click_timeline(s["title"] or "Replace Face 1"))


def clear_again():
    p = d.panel()
    if not h.check("the edit dialog again", p is not None and p.editing, p):
        return
    wi.click(p.fields["target"].clear)


def click_roller():
    h.click(V(115, 10, 2))


def arched():
    import math

    st.settle()
    h.idle_step()()
    r = 42.0
    seg = 10 * math.sqrt(r * r - 100) + r * r * math.asin(10 / r)
    low = math.sqrt(r * r - 100) - 40
    want = 30 * 2 * r * math.asin(10 / r) + 2 * (200 - (seg - 800)) + 2 * 30 * (10 - low)
    area = st.area(s["box"])
    h.check("the floor arched on the roller's surface", st.near(area, want, 1e-6), (area, want))
    h.shot("2-curved-target")
    h.task_button("OK")


def arched_kept():
    h.idle_step()()
    h.check("dialog closed", d.panel() is None)
    floor = [f for f in s["box"].Shape.Faces if f.Surface.TypeId == "Part::GeomCylinder"]
    h.check("the floor is a piece of the cylinder", len(floor) == 1, len(floor))


h.run(
    "surface4_replace_face",
    [
        setup,
        click_floor,
        target_box,
        click_low_top,
        preview,
        done,
        undone,
        redone,
        clear_target,
        click_tall_top,
        refused,
        cancelled,
        clear_again,
        click_roller,
        arched,
        arched_kept,
    ],
)
