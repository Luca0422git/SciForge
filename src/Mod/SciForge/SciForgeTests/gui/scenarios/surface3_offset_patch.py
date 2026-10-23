# SPDX-License-Identifier: LGPL-2.1-or-later
"""SURFACE > Offset Type (Sharp / Rounded) and Patch's Group Edges, per-edge Continuity and
Reverse Normal + Flip (surface part 3), only real input in the dialogs.

Path E (empty design): SURFACE > Offset with nothing in the design: the Faces box waits, the
        dialog says what to pick, nothing is built; Esc: nothing made.
A 40 x 30 x 10 box (built for the scenario).
Path O1 (Offset, Sharp): SURFACE > Offset, click the top face: Offset Type reads Sharp
        Offset; type 3: a 40 x 30 face at z 13 (1200). Click the front face too: the two
        offset faces carried on until they meet, sharp (40 x 33 + 40 x 13 = 1840, 2 faces).
Path O2 (Rounded): Offset Type Rounded Offset: the two faces where they were (1200 + 400)
        and a quarter cylinder r 3 along the edge (188.50): 1788.50, 3 faces. OK: "Offset 1".
Path O3 (edit, undo / redo): double-click Offset 1: Rounded read back; Sharp; OK: 1840. Undo:
        1788.50; Redo: 1840.
Path O4 (a step saved before part 3): the step's saved choices without Offset Type read as
        Rounded (a reopened old design keeps its shape): 1788.50; put back: 1840.
Path P1 (Patch, per edge): four walls (a 20 x 20 square at x 60, extruded 10 as a surface).
        SURFACE > Patch, click a top edge: the loop; Tangency Weight shows 0.5 (greyed);
        Group Edges off: one Continuity row per edge (4); edge 1 Tangent: refused with the
        reason (the walls are too steep), OK waits; edge 1 Connected again: a flat lid (400).
Path P2 (Reverse Normal + Flip): Reverse Normal: the lid faces down; Flip: up again; Flip:
        down. OK: "Patch 1"; double-click it: Group Edges off, the four rows and Reverse
        Normal read back; Cancel: nothing changes.
"""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import surface_steps as st

V = App.Vector
s = {}
SHARP = 40 * 33 + 40 * 13
ROUNDED = 1200 + 400 + 3.141592653589793 / 2 * 3 * 40


def doc():
    return App.ActiveDocument


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Surface3OffsetPatch")
    h.fit()
    h.click_empty()
    st.tab("SURFACE")
    st.menu("CREATE", "Offset")


def empty_waits():
    p = st.panel()
    h.check("Offset dialog open", p is not None and p.kind == "offset")
    if p is None:
        return
    h.check("the Faces box waits", p.active == "faces", p.active)
    h.check("nothing built", p.step is None)
    h.check("the dialog says what to pick", "face" in st.message().lower(), st.message())
    st.esc()


def empty_closed():
    h.check("Esc closed it", st.panel() is None)
    h.check("no body made", not st.bodies(), st.bodies())


def make_box():
    from sciforge import commands, extrude, sketch_ui

    body = commands.ensure_body()
    planes = sketch_ui.origin_planes(body)
    base = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    h.draw_rectangle(base, 0, 0, 40, 30)
    s["box_step"] = extrude.make(body, base, {"distance": 10.0})
    doc().recompute()
    s["box"] = body
    h.fit()


def offset_menu():
    from sciforge import commands

    commands.leave_edit()
    h.check("a box of 12000", st.near(st.volume(s["box"]), 12000.0), st.volume(s["box"]))
    h.fit()
    h.click_empty()
    st.menu("CREATE", "Offset")


def click_top():
    p = st.panel()
    h.check("Offset dialog open again", p is not None and p.kind == "offset")
    if p is None:
        return
    h.check(
        "Offset Type reads Sharp Offset",
        p.rows["offset_type"][0].currentText() == "Sharp Offset",
        p.rows["offset_type"][0].currentText(),
    )
    items = [p.rows["offset_type"][0].itemText(i) for i in range(2)]
    h.check("Sharp Offset / Rounded Offset", items == ["Sharp Offset", "Rounded Offset"], items)
    h.click(V(20, 15, 10))


def type_three():
    st.settle()
    p = st.panel()
    h.check("the top face", p is not None and len(p.picks["faces"]) == 1, p and p.picks)
    st.type_field("distance", "3")


def one_face():
    st.settle()
    body = st.step_body()
    s["offset"] = body
    h.check("a 40 x 30 face at z 13", body is not None and st.near(st.area(body), 1200.0))
    if body is not None:
        b = body.Shape.BoundBox
        h.check("at z 13", st.near(b.ZMin, 13.0) and st.near(b.ZMax, 13.0), b)
    h.click(V(20, 0, 5))


def two_faces_sharp():
    st.settle()
    p = st.panel()
    h.check("two faces picked", p is not None and len(p.picks["faces"]) == 2, p and p.picks)
    body = s.get("offset")
    area = st.area(body)
    h.check("Sharp: the faces carried on to meet (1840)", st.near(area, SHARP, 1e-6), area)
    h.check("2 faces", body is not None and len(body.Shape.Faces) == 2)
    h.shot("1-offset-sharp")
    st.choose("offset_type", "Rounded Offset")


def rounded():
    st.settle()
    body = s.get("offset")
    area = st.area(body)
    h.check(
        "Rounded: a quarter cylinder fills the corner (1788.50)", st.near(area, ROUNDED, 1e-6), area
    )
    h.check("3 faces", body is not None and len(body.Shape.Faces) == 3)
    h.shot("2-offset-rounded")
    st.ok()


def offset_done():
    h.check("dialog closed", st.panel() is None)
    titles = st.timeline_titles()
    h.check("Offset 1 in the timeline", "Offset 1" in titles, titles)
    from sciforge import surface

    h.check("a surface body", surface.is_surface_body(s["offset"]))
    h.check("edited from the timeline", st.double_click_timeline("Offset 1"))


def edit_reads_back():
    st.settle()
    p = st.panel()
    h.check("Offset dialog for editing", p is not None and p.kind == "offset" and p.editing)
    if p is None:
        return
    h.check("Rounded read back", p.options["offset_type"] == "rounded", p.options)
    h.check("two faces read back", len(p.picks["faces"]) == 2, p.picks)
    st.choose("offset_type", "Sharp Offset")


def edit_ok():
    st.settle()
    st.ok()


def edited():
    h.check("dialog closed", st.panel() is None)
    h.check("Sharp again: 1840", st.near(st.area(s["offset"]), SHARP, 1e-6), st.area(s["offset"]))
    st.undo()


def undone():
    h.check("Undo: Rounded (1788.50)", st.near(st.area(s["offset"]), ROUNDED, 1e-6))
    st.redo()


def redone():
    h.check("Redo: Sharp (1840)", st.near(st.area(s["offset"]), SHARP, 1e-6))


def old_file():
    """A step saved before Offset Type existed has no offset_type in its saved choices."""
    from sciforge import bodies, surface

    step = s["offset"].Tip
    meta = bodies.load_meta(step, surface.META)
    s["meta"] = dict(meta)
    options = dict(meta.get("options") or {})
    options.pop("offset_type", None)
    meta["options"] = options
    bodies.save_meta(step, surface.META, meta)
    step.touch()
    doc().recompute()


def old_file_rounded():
    from sciforge import bodies, surface

    area = st.area(s["offset"])
    h.check("an old Offset keeps its rounded corner (1788.50)", st.near(area, ROUNDED, 1e-6), area)
    step = s["offset"].Tip
    bodies.save_meta(step, surface.META, s["meta"])
    step.touch()
    doc().recompute()


def back_to_sharp():
    h.check("its choice put back: Sharp", st.near(st.area(s["offset"]), SHARP, 1e-6))


# -- Patch -----------------------------------------------------------------------------------------
def make_walls():
    import Sketcher  # noqa: F401
    from sciforge import commands, surface, sketch_ui

    body = s["box"]
    planes = sketch_ui.origin_planes(body)
    sk = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    st.add_lines(sk, [(60, 0), (80, 0), (80, 20), (60, 20)], closed=True)
    commands.leave_edit()
    doc().recompute()
    edges = [(sk, "Edge%d" % (i + 1)) for i in range(4)]
    s["walls_step"] = surface.build("extrude", {"refs": edges}, {"distance": 10.0})
    doc().recompute()
    from sciforge import bodies

    s["walls"] = bodies.body_of(s["walls_step"])
    bodies.set_shown(sk, False)
    h.fit()


def patch_menu():
    h.check("walls of 800", st.near(st.area(s["walls"]), 800.0), st.area(s["walls"]))
    h.click_empty()
    st.menu("CREATE", "Patch")


def click_rim():
    p = st.panel()
    h.check("Patch dialog open", p is not None and p.kind == "patch")
    if p is None:
        return
    weight = p.number_fields["weight"]
    h.check("Tangency Weight shows 0.5", st.near(weight.value(), 0.5), weight.value())
    h.check("and is greyed", not weight.widget.isEnabled())
    h.check("Group Edges on by default", p.rows["group_edges"][0].isChecked())
    h.check("Reverse Normal off", not p.rows["reverse"][0].isChecked())
    h.check("clicked a top edge of the walls", h.click_edge(V(70, 0, 10)))


def lid():
    st.settle()
    p = st.panel()
    if p is None:
        return
    h.check("the whole loop", len(p.picks["boundary"]) == 4, p.picks["boundary"])
    body = st.step_body(p)
    s["lid"] = body
    h.check("a flat lid of 400", body is not None and st.near(st.area(body), 400.0), st.area(body))
    h.check("no per-edge rows while grouped", not p.rows["edge_rows"][0].isVisible())
    st.toggle_check("group_edges")


def per_edge_rows():
    st.settle()
    p = st.panel()
    if p is None:
        return
    h.check("Group Edges off", not p.options["group_edges"])
    h.check("one Continuity row per edge", len(p.edge_combos) == 4, len(p.edge_combos))
    h.check("the rows are shown", p.rows["edge_rows"][0].isVisible())
    h.check("the group Continuity is hidden", not p.rows["continuity"][0].isVisible())
    h.check("chose Tangent for edge 1", ui.choose(p.edge_combos[0], "Tangent"))


def edge_tangent_refused():
    st.settle()
    p = st.panel()
    text = st.message()
    h.check("Tangent on the steep walls is explained", "Connected" in text, text)
    h.check(
        "only edge 1 is Tangent",
        p is not None and p.options["edge_continuity"] == ["tangent"] + ["connected"] * 3,
        p and p.options.get("edge_continuity"),
    )
    st.ok()


def ok_waits():
    st.settle()
    p = st.panel()
    h.check("OK waits while the patch cannot be built", p is not None)
    if p is not None:
        h.check("chose Connected for edge 1", ui.choose(p.edge_combos[0], "Connected"))


def lid_again():
    st.settle()
    body = st.step_body()
    s["lid"] = body
    h.check("the lid again (400)", body is not None and st.near(st.area(body), 400.0))
    s["up"] = _normal_z(body)
    h.check("it faces up", s["up"] > 0.99, s["up"])
    st.toggle_check("reverse")


def _normal_z(body):
    try:
        face = body.Shape.Faces[0]
        u0, u1, v0, v1 = face.ParameterRange
        return face.normalAt((u0 + u1) / 2, (v0 + v1) / 2).z
    except Exception:
        return 0.0


def reversed_down():
    st.settle()
    z = _normal_z(st.step_body())
    h.check("Reverse Normal: the lid faces down", z < -0.99, z)
    p = st.panel()
    if p is not None:
        ui.click(p.rows["flip"][0])


def flipped_up():
    st.settle()
    p = st.panel()
    z = _normal_z(st.step_body())
    h.check("Flip: up again", z > 0.99, z)
    h.check("Flip clears Reverse Normal", p is not None and not p.rows["reverse"][0].isChecked())
    if p is not None:
        ui.click(p.rows["flip"][0])


def flipped_down():
    st.settle()
    z = _normal_z(st.step_body())
    h.check("Flip again: down", z < -0.99, z)
    h.shot("3-patch-reversed")
    st.ok()


def patch_done():
    h.check("dialog closed", st.panel() is None)
    titles = st.timeline_titles()
    h.check("Patch 1 in the timeline", "Patch 1" in titles, titles)
    h.check("edited from the timeline", st.double_click_timeline("Patch 1"))


def patch_reads_back():
    st.settle()
    p = st.panel()
    h.check("Patch dialog for editing", p is not None and p.kind == "patch" and p.editing)
    if p is None:
        return
    h.check("Group Edges off read back", not p.rows["group_edges"][0].isChecked())
    h.check("the four rows read back", len(p.edge_combos) == 4, len(p.edge_combos))
    h.check(
        "each row Connected",
        [c.currentData() for c in p.edge_combos] == ["connected"] * 4,
        [c.currentData() for c in p.edge_combos],
    )
    h.check("Reverse Normal read back", p.rows["reverse"][0].isChecked())
    st.cancel()


def cancelled():
    h.check("dialog closed", st.panel() is None)
    z = _normal_z(s["lid"])
    h.check("Cancel: still facing down", z < -0.99, z)


h.run(
    "surface3_offset_patch",
    [
        new_design,
        empty_waits,
        empty_closed,
        make_box,
        offset_menu,
        click_top,
        type_three,
        one_face,
        two_faces_sharp,
        rounded,
        offset_done,
        edit_reads_back,
        edit_ok,
        edited,
        undone,
        redone,
        old_file,
        old_file_rounded,
        back_to_sharp,
        make_walls,
        patch_menu,
        click_rim,
        lid,
        per_edge_rows,
        edge_tangent_refused,
        ok_waits,
        lid_again,
        reversed_down,
        flipped_up,
        flipped_down,
        patch_done,
        patch_reads_back,
        cancelled,
    ],
)
