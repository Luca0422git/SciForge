# SPDX-License-Identifier: LGPL-2.1-or-later
"""Surface part 3, QA: Stitch's Operation changed while the dialog is open, Esc, and an edit
that moves a Join stitch back to New Body (real input in the dialogs).

The design (built for the scenario, as surface3_stitch_trim_ruled's): a 10 x 10 x 10 box at
the origin; four surface walls round x 5 .. 15, y 0 .. 10, 10 high, a bottom patch at z 0 and
a top patch at z 10 (they close a cube overlapping the box by half).
Path O (live Operation): SURFACE > Stitch, click the walls, the top, the bottom's row:
        "Closed", New Body: the cube is a solid (1000) in the walls' body, the box 1000;
        Cut: the box loses the half the cube covers (500), the walls' body no longer holds
        the cube; Intersect: the box keeps that half (500); New Body again: the box 1000,
        the cube 1000. Esc: nothing changed (the box 1000, the surfaces open and shown, no
        Stitch in the timeline).
Path J (edit Join -> New Body): SURFACE > Stitch the three again with Join: 1500; OK. Double-
        click Stitch 1, New Body: the box 1000 and the cube 1000 in the walls' body; OK.
        Undo: Join again (the box 1500, the surfaces used up); Redo: New Body (1000).
"""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import surface_steps as st
from SciForgeTests.gui import timeline_input as tl

V = App.Vector
s = {}


def doc():
    return App.ActiveDocument


def _sketch(body, plane, points, closed=False, offset=0.0):
    from sciforge import commands, sketch_ui

    planes = sketch_ui.origin_planes(body)
    sk = sketch_ui.create_sketch(body, (planes[plane], ""))
    if offset:
        sk.AttachmentOffset = App.Placement(V(0, 0, offset), App.Rotation())
    st.add_lines(sk, points, closed=closed)
    commands.leave_edit()
    doc().recompute()
    return sk


def _surface(kind, sk, options=None):
    from sciforge import bodies, surface

    n = len(sk.Shape.Edges)
    step = surface.build(
        kind, {"refs": [(sk, "Edge%d" % (i + 1)) for i in range(n)]}, options or {}
    )
    doc().recompute()
    return bodies.body_of(step)


def new_design():
    from sciforge import bodies, commands, extrude, sketch_ui

    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Surface3QA2")
    body = commands.ensure_body()
    planes = sketch_ui.origin_planes(body)
    base = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    h.draw_rectangle(base, 0, 0, 10, 10)
    extrude.make(body, base, {"distance": 10.0})
    commands.leave_edit()
    s["box"] = body
    square = [(5, 0), (15, 0), (15, 10), (5, 10)]
    s["walls"] = _surface("extrude", _sketch(body, "XY_Plane", square, True), {"distance": 10.0})
    s["bottom"] = _surface("patch", _sketch(body, "XY_Plane", square, True))
    s["top"] = _surface("patch", _sketch(body, "XY_Plane", square, True, offset=10.0))
    for obj in doc().Objects:
        if obj.TypeId == "Sketcher::SketchObject":
            bodies.set_shown(obj, False)
    s["count"] = len(st.bodies())
    h.fit()


def _solid_volume(body):
    try:
        return sum(x.Volume for x in body.Shape.Solids)
    except Exception:
        return 0.0


def stitch_menu():
    h.check("a box of 1000", st.near(st.volume(s["box"]), 1000.0), st.volume(s["box"]))
    h.click_empty()
    st.tab("SURFACE")
    st.menu("MODIFY", "Stitch")


def click_walls():
    p = st.panel()
    h.check("Stitch dialog open", p is not None and p.kind == "stitch")
    h.click(V(15, 5, 4))


def click_top():
    st.settle()
    h.click(V(13, 6, 10))


def click_bottom_row():
    st.settle()
    h.check("the bottom patch's row clicked", tl.click_row(s["bottom"].Label))


def new_body():
    st.settle()
    p = st.panel()
    if p is None:
        h.check("the dialog is open", False)
        return
    h.check("three bodies", len(p.picks["bodies"]) == 3, p.picks["bodies"])
    h.check("Closed", "Closed" in p.open_label.text(), p.open_label.text())
    h.check("New Body by default", p.options["operation"] == "new_body", p.options)
    from sciforge import bodies

    host = bodies.body_of(p.step) if p.step is not None else None
    h.check("the cube is a solid (1000)", st.near(_solid_volume(host), 1000.0, 1e-6))
    h.check("the box still 1000", st.near(st.volume(s["box"]), 1000.0), st.volume(s["box"]))
    st.choose("operation", "Cut")


def cut():
    st.settle()
    p = st.panel()
    from sciforge import bodies

    step = p.step if p is not None else None
    h.check("Cut: the step is in the box", step is not None and bodies.body_of(step) is s["box"])
    v = st.volume(s["box"])
    h.check("Cut: the box loses the half the cube covers (500)", st.near(v, 500.0, 1e-6), v)
    h.check("the walls' body holds no cube now", _solid_volume(s["walls"]) < 1e-6)
    h.check("no warning", "⚠" not in st.message(), st.message())
    st.choose("operation", "Intersect")


def intersect():
    st.settle()
    v = st.volume(s["box"])
    h.check("Intersect: the half the cube covers (500)", st.near(v, 500.0, 1e-6), v)
    b = s["box"].Shape.BoundBox
    h.check("that half is x 5 .. 10", st.near(b.XMin, 5.0) and st.near(b.XMax, 10.0), b)
    st.choose("operation", "New Body")


def new_body_again():
    st.settle()
    p = st.panel()
    from sciforge import bodies

    v = st.volume(s["box"])
    h.check("New Body again: the box 1000", st.near(v, 1000.0, 1e-6), v)
    host = bodies.body_of(p.step) if p is not None and p.step is not None else None
    h.check("and the cube 1000", st.near(_solid_volume(host), 1000.0, 1e-6))
    st.esc()


def escaped():
    from sciforge import bodies

    h.check("Esc closed the dialog", st.panel() is None)
    h.check("the box 1000", st.near(st.volume(s["box"]), 1000.0, 1e-6), st.volume(s["box"]))
    h.check("the walls open again", _solid_volume(s["walls"]) < 1e-6)
    used = bodies.consumed(doc())
    h.check(
        "the surfaces not used up",
        not any(s[k].Name in used for k in ("walls", "top", "bottom")),
        used,
    )
    h.check(
        "the surfaces shown",
        all(bodies.is_shown(s[k]) for k in ("walls", "top", "bottom")),
    )
    titles = st.timeline_titles()
    h.check("no Stitch in the timeline", not any(t.startswith("Stitch") for t in titles), titles)
    h.check("no body added", len(st.bodies()) == s["count"], st.bodies())
    h.click_empty()
    st.menu("MODIFY", "Stitch")


def again_walls():
    h.check("Stitch dialog again", st.panel() is not None)
    h.click(V(15, 5, 4))


def again_top():
    st.settle()
    h.click(V(13, 6, 10))


def again_bottom():
    st.settle()
    h.check("the bottom patch's row clicked", tl.click_row(s["bottom"].Label))


def join():
    st.settle()
    st.choose("operation", "Join")


def joined():
    st.settle()
    v = st.volume(s["box"])
    h.check("Join: 1500", st.near(v, 1500.0, 1e-6), v)
    st.ok()


def join_done():
    h.check("dialog closed", st.panel() is None)
    titles = st.timeline_titles()
    h.check("Stitch 1 in the timeline", "Stitch 1" in titles, titles)
    h.check("edited from the timeline", st.double_click_timeline("Stitch 1"))


def edit_new_body():
    st.settle()
    p = st.panel()
    h.check("Stitch dialog for editing", p is not None and p.kind == "stitch" and p.editing)
    if p is None:
        return
    h.check("Join read back", p.options["operation"] == "join", p.options)
    st.choose("operation", "New Body")


def edited_preview():
    st.settle()
    p = st.panel()
    from sciforge import bodies

    v = st.volume(s["box"])
    h.check("New Body: the box 1000", st.near(v, 1000.0, 1e-6), v)
    host = bodies.body_of(p.step) if p is not None and p.step is not None else None
    h.check("the cube 1000 in a surface's body", host is not None and host is not s["box"])
    h.check("its volume 1000", st.near(_solid_volume(host), 1000.0, 1e-6))
    st.ok()


def edited():
    from sciforge import bodies

    h.check("dialog closed", st.panel() is None)
    h.check("still the box 1000", st.near(st.volume(s["box"]), 1000.0, 1e-6))
    titles = st.timeline_titles()
    h.check("one Stitch in the timeline", sum(t.startswith("Stitch") for t in titles) == 1, titles)
    h.check("the walls hold the cube", st.near(_solid_volume(s["walls"]), 1000.0, 1e-6))
    used = bodies.consumed(doc())
    h.check("the top and bottom used up", all(s[k].Name in used for k in ("top", "bottom")), used)
    st.undo()


def edit_undone():
    from sciforge import bodies

    v = st.volume(s["box"])
    h.check("Undo: Join again (1500)", st.near(v, 1500.0, 1e-6), v)
    used = bodies.consumed(doc())
    h.check(
        "the surfaces used up",
        all(s[k].Name in used for k in ("walls", "top", "bottom")),
        used,
    )
    st.redo()


def edit_redone():
    v = st.volume(s["box"])
    h.check("Redo: New Body (the box 1000)", st.near(v, 1000.0, 1e-6), v)
    h.check("the cube back", st.near(_solid_volume(s["walls"]), 1000.0, 1e-6))
    tl.no_popups("the Stitch operations")


h.run(
    "surface3_qa2",
    [
        new_design,
        stitch_menu,
        click_walls,
        click_top,
        click_bottom_row,
        new_body,
        cut,
        intersect,
        new_body_again,
        escaped,
        again_walls,
        again_top,
        again_bottom,
        join,
        joined,
        join_done,
        edit_new_body,
        edited_preview,
        edited,
        edit_undone,
        edit_redone,
    ],
)
