# SPDX-License-Identifier: LGPL-2.1-or-later
"""SURFACE > Unstitch and Stitch like a Fusion user, only real input.

A 40 x 30 x 10 box (sketch, E, 10, OK). SURFACE > Unstitch, click the top face: Chain
Selection (on) takes every face joined to it, the six faces leave the solid: six surface
bodies (one face each, area 2 (40 30 + 40 10 + 30 10) = 3800 in all, no solid left), the
surface icon in the browser. Undo: the box is back; Redo.
SURFACE > Stitch: click the top, then the front surface: they are drawn stitched, 6 edges
left open (4 + 4 - the shared one, drawn red), the shared one drawn green. Click the front
again: it is dropped (the click lands on the stitched preview); click it once more. The
right surface in the 3D view, the back, left and bottom ones in the browser (they face
away): "Closed", every edge green, the six make a solid of 40 x 30 x 10 = 12000; OK: one
solid body, the other five used up. A solid feature after it: Fillet the top front edge,
radius 3: 12000 - 40 r^2 (1 - pi/4). Undo twice: the six surfaces again; Redo twice. Edit
the Stitch from the timeline: the six read back, Tolerance 0.5, OK: still the filleted
solid. Refusal: Stitch, click the solid: the dialog says it is a solid and takes nothing;
Esc.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import surface_steps as st
from SciForgeTests.gui import timeline_input as tl

V = App.Vector
s = {}
BOX = 12000.0
FILLETED = BOX - 40 * 9 * (1 - math.pi / 4)


def shown(obj):
    from sciforge import bodies

    return bodies.is_shown(obj)


def shown_bodies():
    return [x for x in st.bodies() if shown(x)]


def face_at(point):
    """The surface body whose face goes through `point` (seen as a person would: by where
    it is in the design)."""
    import Part

    for body in st.surface_bodies():
        try:
            if body.Shape.distToShape(Part.Vertex(point))[0] < 1e-6:
                return body
        except Exception:
            pass
    return None


def unstitch_menu():
    s["box"] = h.body()
    h.check("box made", s["box"] is not None and st.near(st.volume(s["box"]), BOX))
    st.tab("SURFACE")
    st.menu("MODIFY", "Unstitch")


def unstitch_waits():
    p = st.panel()
    h.check("Unstitch dialog open", p is not None and p.kind == "unstitch")
    if p is None:
        return
    h.check("the Faces/Bodies box waits", p.active == "faces", p.active)
    h.check("Chain Selection is on", p.chain_on())


def click_top():
    h.click(V(20, 15, 10))


def six_faces():
    st.settle()
    p = st.panel()
    if p is None:
        return
    h.check("the chain took the six faces", len(p.picks["faces"]) == 6, p.picks["faces"])
    surfaces = st.surface_bodies()
    h.check("six surface bodies in the preview", len(surfaces) == 6, [x.Label for x in surfaces])
    h.check("no solid left", not any(x.Shape.Solids for x in st.bodies()))
    total = sum(st.area(x) for x in surfaces)
    h.check("3800 of surface in all", st.near(total, 3800.0), total)
    h.shot("1-unstitch")
    st.ok()


def unstitched():
    h.check("dialog closed", st.panel() is None)
    surfaces = st.surface_bodies()
    h.check("six surface bodies", len(surfaces) == 6, [x.Label for x in surfaces])
    h.check("one face each", all(len(x.Shape.Faces) == 1 for x in surfaces))
    h.check(
        "the surface icon on each",
        all(st.browser_icon_of(x) == "surface_body" for x in surfaces),
        [st.browser_icon_of(x) for x in surfaces],
    )
    titles = st.timeline_titles()
    h.check("Unstitch in the timeline", any(t.startswith("Unstitch") for t in titles), titles)
    st.undo()


def unstitch_undone():
    h.check("undo: the box is back", st.near(st.volume(s["box"]), BOX), st.volume(s["box"]))
    h.check("undo: no surface body", st.surface_bodies() == [], st.surface_bodies())
    st.redo()


def unstitch_redone():
    h.check("redo: six surface bodies", len(st.surface_bodies()) == 6, st.surface_bodies())
    for name, point in (
        ("top", V(20, 15, 10)),
        ("front", V(20, 0, 5)),
        ("right", V(40, 15, 5)),
        ("back", V(20, 30, 5)),
        ("left", V(0, 15, 5)),
        ("bottom", V(20, 15, 0)),
    ):
        s[name] = face_at(point)
    h.check(
        "a surface for each side",
        all(s[k] is not None for k in ("top", "front", "right", "back", "left", "bottom")),
    )


def stitch_menu():
    h.fit()
    st.menu("MODIFY", "Stitch")


def stitch_waits():
    p = st.panel()
    h.check("Stitch dialog open", p is not None and p.kind == "stitch")
    if p is None:
        return
    h.check("the Stitched Surfaces box waits", p.active == "bodies", p.active)
    h.check("Tolerance 1 mm", st.near(float(p.options["tolerance"]), 1.0), p.options["tolerance"])


def click_top_surface():
    h.click(V(20, 15, 10))


def click_front_surface():
    h.click(V(20, 0, 5))


def two_stitched():
    st.settle()
    p = st.panel()
    if p is None:
        return
    h.check(
        "two surfaces picked",
        [x[0] for x in p.picks["bodies"]] == [s["top"], s["front"]],
        p.picks["bodies"],
    )
    text = p.open_label.text()
    h.check("6 edges left open", text.startswith("6 edges") and "open" in text, text)
    # Fusion draws the stitched edges green: the top's front edge and the front's top edge
    stitched = [e.BoundBox for e in p.stitched]
    h.check(
        "the shared edge is drawn green (once from each surface)",
        len(stitched) == 2
        and all(abs(b.YMax) < 1e-6 and abs(b.ZMin - 10) < 1e-6 for b in stitched)
        and "stitched" in p.overlay.groups,
        stitched,
    )
    h.check(
        "the top body previews both (1200 + 400)",
        st.near(st.area(s["top"]), 1600.0),
        st.area(s["top"]),
    )
    h.shot("2-two")


def click_front_again():
    h.click(V(20, 0, 5))


def front_dropped():
    st.settle()
    p = st.panel()
    if p is None:
        return
    h.check(
        "the click on the stitched front dropped it",
        [x[0] for x in p.picks["bodies"]] == [s["top"]],
        p.picks["bodies"],
    )
    h.check(
        "the top body is the top face again", st.near(st.area(s["top"]), 1200.0), st.area(s["top"])
    )


def click_front_once_more():
    h.click(V(20, 0, 5))


def click_right_surface():
    st.settle()
    h.click(V(40, 15, 5))


def click_back_row():
    st.settle()
    tl.click_row(s["back"].Label)


def click_left_row():
    st.settle()
    tl.click_row(s["left"].Label)


def click_bottom_row():
    st.settle()
    tl.click_row(s["bottom"].Label)


def closed():
    st.settle()
    p = st.panel()
    if p is None:
        return
    h.check("six surfaces picked", len(p.picks["bodies"]) == 6, p.picks["bodies"])
    text = p.open_label.text()
    h.check("Closed: a solid", text.startswith("Closed"), text)
    h.check("every edge stitched (green): 6 x 4", len(p.stitched) == 24, len(p.stitched))
    h.check(
        "the preview is the 12000 solid",
        st.near(st.volume(s["top"]), BOX, 1e-4),
        st.volume(s["top"]),
    )
    h.shot("3-closed")
    st.ok()


def stitched():
    h.check("dialog closed", st.panel() is None)
    shown = shown_bodies()
    h.check("one body shown", shown == [s["top"]], [x.Label for x in shown])
    h.check("it is a solid", st.near(st.volume(s["top"]), BOX, 1e-4), st.volume(s["top"]))
    h.check("the solid icon", st.browser_icon_of(s["top"]) == "box", st.browser_icon_of(s["top"]))
    titles = st.timeline_titles()
    h.check("Stitch in the timeline", any(t.startswith("Stitch") for t in titles), titles)
    s["stitch_title"] = next((t for t in titles if t.startswith("Stitch")), "Stitch 1")


def fillet():
    st.tab("SOLID")
    Gui.Selection.clearSelection()
    h.fit()
    h.ribbon("Fillet")


def fillet_edge():
    h.click_edge(V(20, 0, 10))


def fillet_radius():
    p = b.blend_panel()
    h.check("one edge picked", p is not None and len(p.refs) == 1, p and p.refs)
    if p is not None:
        b.type_into(p.radius.widget, "3")


def fillet_ok():
    h.task_button("OK")


def filleted():
    h.check(
        "the stitched solid is filleted",
        st.near(st.volume(s["top"]), FILLETED, 1e-4),
        (st.volume(s["top"]), FILLETED),
    )
    st.undo()


def undo_again():
    h.check("undo: the fillet goes", st.near(st.volume(s["top"]), BOX, 1e-4), st.volume(s["top"]))
    st.undo()


def stitch_undone():
    surfaces = [x for x in st.surface_bodies() if shown(x)]
    h.check("undo: the six surfaces again", len(surfaces) == 6, [x.Label for x in surfaces])
    st.redo()


def redo_again():
    st.redo()


def redone():
    h.check(
        "redo: the filleted solid",
        st.near(st.volume(s["top"]), FILLETED, 1e-4),
        st.volume(s["top"]),
    )
    h.check("redo: one body shown", len(shown_bodies()) == 1, [x.Label for x in shown_bodies()])


def edit_stitch():
    st.tab("SURFACE")
    h.check("double-clicked the Stitch", st.double_click_timeline(s["stitch_title"]))


def edit_open():
    st.settle()
    p = st.panel()
    h.check("edit dialog open", p is not None and p.editing and p.kind == "stitch")
    if p is None:
        return
    h.check("the six read back", len(p.picks["bodies"]) == 6, p.picks["bodies"])
    st.type_field("tolerance", "0.5")


def edit_ok():
    st.settle()
    st.ok()


def edited():
    h.check("dialog closed", st.panel() is None)
    h.check(
        "still the filleted solid",
        st.near(st.volume(s["top"]), FILLETED, 1e-4),
        st.volume(s["top"]),
    )
    from sciforge import surface

    step = next((x for x in App.ActiveDocument.Objects if surface.kind_of(x) == "stitch"), None)
    h.check(
        "tolerance 0.5 kept",
        step is not None and st.near(step.Tolerance.Value, 0.5),
        step and step.Tolerance,
    )


def stitch_a_solid():
    h.fit()
    st.menu("MODIFY", "Stitch")


def click_solid():
    h.click(V(30, 15, 10))


def refused():
    st.settle()
    p = st.panel()
    if p is None:
        return
    h.check("the solid was not taken", p.picks["bodies"] == [], p.picks["bodies"])
    h.check("the dialog says why", "is a solid" in p.message.text(), p.message.text())
    st.esc()


def closed_again():
    h.check("Esc closed it", st.panel() is None)
    h.check("nothing changed", st.near(st.volume(s["top"]), FILLETED, 1e-4), st.volume(s["top"]))


h.run(
    "surface_stitch",
    b.box_steps("SurfaceStitch", 10)
    + [
        unstitch_menu,
        unstitch_waits,
        click_top,
        six_faces,
        unstitched,
        unstitch_undone,
        unstitch_redone,
        stitch_menu,
        stitch_waits,
        click_top_surface,
        click_front_surface,
        two_stitched,
        click_front_again,
        front_dropped,
        click_front_once_more,
        click_right_surface,
        click_back_row,
        click_left_row,
        click_bottom_row,
        closed,
        stitched,
        fillet,
        fillet_edge,
        fillet_radius,
        fillet_ok,
        filleted,
        undo_again,
        stitch_undone,
        redo_again,
        redone,
        edit_stitch,
        edit_open,
        edit_ok,
        edited,
        stitch_a_solid,
        click_solid,
        refused,
        closed_again,
    ],
)
