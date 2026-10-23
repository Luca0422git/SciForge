# SPDX-License-Identifier: LGPL-2.1-or-later
"""Surface part 3, QA: Extrude of a flat face with a hole up to an object with Extend Faces,
and Patch's per-edge Continuity saved and reopened (real input in the dialogs).

The design (built for the scenario): a flat 10 x 10 patch at the origin with a round hole r 2
at (5, 5); a box x -20 .. 5, y -5 .. 15, z 20 .. 30 hanging over part of it; walls round a
20 x 20 square at x 60 leaning in 20 degrees, 10 high (a tapered surface extrude).
Path X (a flat face with a hole as the profile): SURFACE > Extrude, click the patch: its
        curves are the profile, the hole's too; type 5: walls round the outside and round the
        hole ((40 + 4 pi) x 5 = 262.83). Extent To Object, Faces Extend Faces, click the box's
        top: the top carried on past its edges, every wall up to z 30 ((40 + 4 pi) x 30 =
        1576.99). OK. Double-click it: To Object and Extend Faces read back; Cancel: the same.
        Undo: no walls; Redo: back.
Path P (per-edge Continuity, save / reopen): SURFACE > Patch, click a top edge of the leaning
        walls: the loop; Continuity Tangent: the patch bulges (more than the flat lid);
        Group Edges off: four rows, all Tangent; edge 1 Connected: refused, the reason names
        the mix (where a Connected edge meets a Tangent one OpenCASCADE's patch bends away
        for a long way), OK waits; Cancel. Gentle walls (50 x 50 at x 120, 4 high, 15 degrees
        from flat): Patch, Tangent, Group Edges off, edge 1 Connected: a different patch, no
        refusal. OK. Saved, closed, opened: the patch is the same; double-click it: Group
        Edges off and Connected / Tangent / Tangent / Tangent read back; Esc: unchanged.
"""

import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import surface_steps as st

V = App.Vector
s = {}
WALLS_5 = (40 + 4 * math.pi) * 5
WALLS_30 = (40 + 4 * math.pi) * 30


def doc():
    return App.ActiveDocument


def by_label(label):
    found = doc().getObjectsByLabel(label)
    return found[0] if found else None


def new_design():
    import Part

    from sciforge import bodies, commands, extrude, sketch_ui, surface

    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Surface3QA3")
    body = commands.ensure_body()
    planes = sketch_ui.origin_planes(body)
    # the box over part of the patch (z 20 .. 30)
    base = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    base.AttachmentOffset = App.Placement(V(0, 0, 20), App.Rotation())
    h.draw_rectangle(base, -20, -5, 5, 15)
    extrude.make(body, base, {"distance": 10.0})
    commands.leave_edit()
    doc().recompute()
    s["box"] = body
    # the flat patch with a hole
    sk = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    st.add_lines(sk, [(0, 0), (10, 0), (10, 10), (0, 10)], closed=True)
    sk.addGeometry(Part.Circle(V(5, 5, 0), V(0, 0, 1), 2))
    commands.leave_edit()
    doc().recompute()
    step = surface.build("patch", {"refs": [(sk, "Edge%d" % (i + 1)) for i in range(5)]}, {})
    doc().recompute()
    s["patch"] = bodies.body_of(step)
    # the leaning walls
    wk = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    st.add_lines(wk, [(60, 0), (80, 0), (80, 20), (60, 20)], closed=True)
    commands.leave_edit()
    doc().recompute()
    edges = [(wk, "Edge%d" % (i + 1)) for i in range(4)]
    walls = surface.build("extrude", {"refs": edges}, {"distance": 10.0, "taper": -20.0})
    doc().recompute()
    s["walls"] = bodies.body_of(walls)
    # gentle walls: 50 x 50 at x 120, 4 high, leaning in 75 degrees (15 from flat)
    gk = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    st.add_lines(gk, [(120, 0), (170, 0), (170, 50), (120, 50)], closed=True)
    commands.leave_edit()
    doc().recompute()
    edges = [(gk, "Edge%d" % (i + 1)) for i in range(4)]
    gentle = surface.build("extrude", {"refs": edges}, {"distance": 4.0, "taper": -75.0})
    doc().recompute()
    s["gentle"] = bodies.body_of(gentle)
    for obj in doc().Objects:
        if obj.TypeId == "Sketcher::SketchObject":
            bodies.set_shown(obj, False)
    s["count"] = len(st.bodies())
    h.fit()


def extrude_menu():
    h.check("the patch with its hole", st.near(st.area(s["patch"]), 100 - 4 * math.pi, 1e-6))
    b = s["walls"].Shape.BoundBox
    top = [e for e in s["walls"].Shape.Edges if e.BoundBox.ZMin > 10 - 1e-6]
    width = max((e.BoundBox.XMax for e in top), default=0.0) - min(
        (e.BoundBox.XMin for e in top), default=0.0
    )
    h.check("the walls lean in (narrower at the top)", 0 < width < 20.0 - 1e-3, (width, b))
    # frame the patch: from the whole design its face is a few pixels from its edges
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(doc().Name, s["patch"].Tip.Name)
    Gui.SendMsgToActiveView("ViewSelection")
    Gui.Selection.clearSelection()
    h.click_empty()
    st.tab("SURFACE")
    st.menu("CREATE", "Extrude")


def click_patch():
    p = st.panel()
    h.check("Extrude dialog open", p is not None and p.kind == "extrude")
    h.click(V(8, 8, 0))


def type_five():
    st.settle()
    p = st.panel()
    picks = p.picks["profile"] if p is not None else []
    h.check("the patch's face is the profile", len(picks) == 1 and picks[0][1].startswith("Face"))
    st.type_field("distance", "5")


def walls_five():
    st.settle()
    body = st.step_body()
    s["x"] = body
    area = st.area(body)
    h.check("walls round the outside and the hole (262.83)", st.near(area, WALLS_5, 1e-6), area)
    h.check("5 faces (4 sides, the hole's wall)", body is not None and len(body.Shape.Faces) == 5)
    st.choose("extent", "To Object")


def to_object():
    st.settle()
    p = st.panel()
    h.check("the Object box takes the clicks", p is not None and p.active == "object")
    st.choose("chain_faces", "Extend Faces")


def click_box_top():
    st.settle()
    h.fit()
    h.click(V(-10, 5, 30))


def walls_thirty():
    st.settle()
    p = st.panel()
    h.check("the box's top picked", p is not None and len(p.picks["object"]) == 1, p and p.picks)
    body = st.step_body()
    s["x"] = body
    area = st.area(body)
    h.check("Extend Faces: every wall up to z 30 (1576.99)", st.near(area, WALLS_30, 1e-6), area)
    if body is not None:
        b = body.Shape.BoundBox
        h.check("from z 0 to z 30", st.near(b.ZMin, 0.0) and st.near(b.ZMax, 30.0), b)
    st.ok()


def x_done():
    h.check("dialog closed", st.panel() is None)
    titles = st.timeline_titles()
    found = [t for t in titles if t.startswith("Extrude")]
    h.check("an Extrude in the timeline", len(found) >= 2, titles)
    s["x_title"] = found[-1] if found else ""
    h.check("edited from the timeline", st.double_click_timeline(s["x_title"]))


def x_reads_back():
    st.settle()
    p = st.panel()
    h.check("Extrude dialog for editing", p is not None and p.kind == "extrude" and p.editing)
    if p is None:
        return
    h.check("To Object read back", p.options["extent"] == "to_object", p.options)
    box = p.rows["chain_faces"][0]
    h.check("Extend Faces read back", box.currentText() == "Extend Faces", box.currentText())
    h.check("the face profile read back", len(p.picks["profile"]) == 1, p.picks)
    st.cancel()


def x_cancelled():
    h.check("dialog closed", st.panel() is None)
    area = st.area(s["x"])
    h.check("Cancel: unchanged (1576.99)", st.near(area, WALLS_30, 1e-6), area)
    st.undo()


def x_undone():
    h.check("Undo: no walls body", len(st.bodies()) == s["count"], st.bodies())
    st.redo()


def x_redone():
    h.check("Redo: the walls back", len(st.bodies()) == s["count"] + 1, st.bodies())
    from sciforge import bodies

    for body in st.bodies():
        if body.Label == s["x"].Label:
            bodies.set_shown(body, False)  # out of the way of the leaning walls
    s["count"] = len(st.bodies())
    h.click_empty()
    st.menu("CREATE", "Patch")


# -- Patch: a Continuity per edge, saved and reopened ---------------------------------------------
def click_rim():
    p = st.panel()
    h.check("Patch dialog open", p is not None and p.kind == "patch")
    top = [e for e in s["walls"].Shape.Edges if e.BoundBox.ZMin > 10 - 1e-6]
    edge = top[0] if top else None
    point = edge.valueAt(0.5 * (edge.FirstParameter + edge.LastParameter)) if edge else V()
    h.check("clicked a top edge of the walls", h.click_edge(point))


def flat_lid():
    st.settle()
    p = st.panel()
    h.check("the loop", p is not None and len(p.picks["boundary"]) == 4, p and p.picks)
    s["flat"] = st.area(st.step_body())
    st.choose("continuity", "Tangent")


def tangent_lid():
    st.settle()
    area = st.area(st.step_body())
    s["tangent"] = area
    h.check("Tangent: the lid bulges (more than flat)", area > s["flat"] + 1.0, (area, s["flat"]))
    h.check("no refusal", "⚠" not in st.message(), st.message())
    st.toggle_check("group_edges")


def rows_tangent():
    st.settle()
    p = st.panel()
    if p is None:
        return
    values = [c.currentData() for c in p.edge_combos]
    h.check("four rows, all Tangent", values == ["tangent"] * 4, values)
    h.check("edge 1 Connected", ui.choose(p.edge_combos[0], "Connected"))


def mixed_refused():
    st.settle()
    text = st.message()
    h.check(
        "steep walls, edge 1 Connected: refused, the mix explained",
        "Connected edge meets a Tangent one" in text,
        text,
    )
    st.ok()


def mixed_ok_waits():
    st.settle()
    h.check("OK waits", st.panel() is not None)
    st.cancel()


def gentle_menu():
    h.check("Cancel closed it", st.panel() is None)
    h.fit()
    h.click_empty()
    st.menu("CREATE", "Patch")


def click_gentle_rim():
    p = st.panel()
    h.check("Patch dialog open", p is not None and p.kind == "patch")
    top = [e for e in s["gentle"].Shape.Edges if e.BoundBox.ZMin > 4 - 1e-6]
    edge = top[0] if top else None
    point = edge.valueAt(0.5 * (edge.FirstParameter + edge.LastParameter)) if edge else V()
    h.check("clicked a top edge of the gentle walls", h.click_edge(point))


def gentle_loop():
    st.settle()
    p = st.panel()
    h.check("the loop", p is not None and len(p.picks["boundary"]) == 4, p and p.picks)
    st.choose("continuity", "Tangent")


def gentle_tangent():
    st.settle()
    s["tangent"] = st.area(st.step_body())
    h.check("Tangent: no refusal", "⚠" not in st.message(), st.message())
    st.toggle_check("group_edges")


def gentle_rows():
    st.settle()
    p = st.panel()
    if p is None:
        return
    values = [c.currentData() for c in p.edge_combos]
    h.check("four rows, all Tangent", values == ["tangent"] * 4, values)
    h.check("edge 1 Connected", ui.choose(p.edge_combos[0], "Connected"))


def mixed():
    st.settle()
    body = st.step_body()
    area = st.area(body)
    s["mixed"] = area
    s["lid"] = body
    h.check("edge 1 Connected: another patch", abs(area - s["tangent"]) > 1e-3, (area, s))
    h.check("no refusal on walls this gentle", "⚠" not in st.message(), st.message())
    st.ok()


def save():
    h.check("dialog closed", st.panel() is None)
    titles = st.timeline_titles()
    found = [t for t in titles if t.startswith("Patch")]
    s["patch_title"] = found[-1] if found else ""
    s["lid_label"] = s["lid"].Label if s.get("lid") is not None else ""
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-surface3qa3-"), "surface3qa3.FCStd")
    s["path"] = path
    doc().saveAs(path)
    h.check("saved", os.path.isfile(path), path)


def close():
    App.closeDocument(doc().Name)


def reopen():
    App.openDocument(s["path"])
    h.fit()


def reopened():
    lid = by_label(s["lid_label"])
    area = st.area(lid)
    h.check("the patch is the same after the reopen", st.near(area, s["mixed"], 1e-6), area)
    if lid is not None:
        lid.Tip.touch()
        doc().recompute()
        area = st.area(lid)
        h.check("and after a recompute", st.near(area, s["mixed"], 1e-6), area)
    h.check("edited from the timeline", st.double_click_timeline(s["patch_title"]))


def reopened_reads_back():
    st.settle()
    p = st.panel()
    h.check("Patch dialog for editing", p is not None and p.kind == "patch" and p.editing)
    if p is None:
        return
    h.check("Group Edges off read back", not p.rows["group_edges"][0].isChecked())
    values = [c.currentData() for c in p.edge_combos]
    h.check(
        "Connected / Tangent / Tangent / Tangent read back",
        values == ["connected", "tangent", "tangent", "tangent"],
        values,
    )
    st.esc()


def escaped():
    h.check("Esc closed it", st.panel() is None)
    area = st.area(by_label(s["lid_label"]))
    h.check("unchanged", st.near(area, s["mixed"], 1e-6), area)


h.run(
    "surface3_qa3",
    [
        new_design,
        extrude_menu,
        click_patch,
        type_five,
        walls_five,
        to_object,
        click_box_top,
        walls_thirty,
        x_done,
        x_reads_back,
        x_cancelled,
        x_undone,
        x_redone,
        click_rim,
        flat_lid,
        tangent_lid,
        rows_tangent,
        mixed_refused,
        mixed_ok_waits,
        gentle_menu,
        click_gentle_rim,
        gentle_loop,
        gentle_tangent,
        gentle_rows,
        mixed,
        save,
        close,
        reopen,
        reopened,
        reopened_reads_back,
        escaped,
    ],
)
