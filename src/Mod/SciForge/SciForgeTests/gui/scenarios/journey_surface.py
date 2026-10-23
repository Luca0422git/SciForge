# SPDX-License-Identifier: LGPL-2.1-or-later
"""Journey (wave 6): a hybrid solid + surface part, the way a Fusion user builds it, real input.

1. New design. Create Sketch, click the YZ square: a slanted line from (y -5, z 4) to
   (y 35, z 12) (the sketch geometry is added as the sketch scenarios do), Finish Sketch.
2. SOLID > CREATE > Box: the XY square, corners (0, 0) and (40, 30), Height 20, OK: 24000.
3. SURFACE > CREATE > Extrude: click the line, Direction Two Sides, 45 and 5: the plane
   z = 5 + 0.2 y over x -5 .. 45, y -5 .. 35 (50 x 40.79 = 2039.61), a surface body.
4. SURFACE > MODIFY > Split Body: click the box, click the surface in front of it: below
   9600, above 14400 (the box's body keeps the bigger piece). OK.
5. SURFACE tab: click the top face of the upper piece, Del: no healing, it becomes a surface
   body (5 faces, 2903.77).
6. Select the vertical edge at (0, 0), MODIFY > Fillet, Radius 3, OK; select the vertical edge
   at (40, 0), MODIFY > Chamfer, Distance 2, OK (areas worked out over the slanted floor).
7. SURFACE > CREATE > Patch: click the rim (z 20): the loop of 6 edges; Group Edges off: one
   Continuity row per edge; edge 1 Tangent onto the vertical walls is refused with the reason;
   back to Connected: a flat lid of 1200 - 9 (1 - pi / 4) - 2. OK.
8. SURFACE > MODIFY > Stitch: the upper piece and the lid: Closed; Operation Join: it joins
   the lower piece (24000 less the rounded and the bevelled corner). OK.
9. SOLID tab: click the chamfer's face, Del: refused with the reason (its foot meets a sliver
   of the lower piece's slanted top that healing would have to make vanish); Ctrl+click the
   sliver too, Del: SOLID Delete heals both (the corner sharp again).
10. Double-click Extrude 1 (the early surface step): Symmetric 15 (half length): the split
    still runs through the whole box (Extend Splitting Tool), every later step follows.
11. Double-click Box 1: Height 25: every later step follows (the lid at z 25, the rounded
    corner 20 high): 30000 less the rounded corner. Undo / Redo.
12. Ctrl+S, close, reopen: the same timeline and volume; the Patch edits again (its rows).
"""

import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import primitive_input as pi
from SciForgeTests.gui import surface4_steps as s4
from SciForgeTests.gui import surface_steps as st

V = App.Vector
s = {}
SLANT = math.sqrt(1.04)  # the plane z = 5 + 0.2 y: area factor over the XY plane
S_AREA = 50 * math.sqrt(40**2 + 8**2)
BELOW = 9600.0
R = 3.0  # fillet radius
D = 2.0  # chamfer distance


def height(top):
    """Height of the upper piece above the slanted floor at y = 0."""
    return top - 5.0


def fillet_volume(top, r=R):
    """What a vertical round of radius r at a corner on y = 0 takes from the upper piece:
    over the corner region (area r^2 (1 - pi / 4)) the height top - 5 - 0.2 y."""
    area = r * r * (1 - math.pi / 4)
    first_moment = r**3 * (0.5 + 1.0 / 3.0 - math.pi / 4)  # integral of y over the region
    return height(top) * area - 0.2 * first_moment


def chamfer_volume(top, d=D):
    return height(top) * d * d / 2 - 0.2 * d**3 / 6


def upper_open_area(top=20.0):
    """The upper piece without its top: walls and the slanted floor."""
    h0 = height(top)
    front = 40 * h0
    back = 40 * (h0 - 6)
    sides = 2 * 30 * (h0 + h0 - 6) / 2
    floor = 40 * math.sqrt(30**2 + 6**2)
    return front + back + sides + floor


def fillet_area_change(top=20.0, r=R):
    h0 = height(top)
    walls = r * h0 + (r * h0 - 0.1 * r * r)
    arc = r * (h0 * math.pi / 2 - 0.2 * r * (math.pi / 2 - 1))
    floor = r * r * (1 - math.pi / 4) * SLANT
    return arc - walls - floor


def chamfer_area_change(top=20.0, d=D):
    h0 = height(top)
    walls = d * h0 + (d * h0 - 0.1 * d * d)
    bevel = d * math.sqrt(2) * (h0 - 0.1 * d)
    floor = d * d / 2 * SLANT
    return bevel - walls - floor


LID = 1200 - R * R * (1 - math.pi / 4) - D * D / 2


def doc():
    return App.ActiveDocument


def vol(body):
    return st.volume(body)


def titles():
    return st.timeline_titles()


def title(prefix):
    return next((t for t in titles() if t.startswith(prefix)), None)


def told():
    from sciforge import commands

    return commands._TOLD.get("msg") or ""


# -- 1. the sketch ------------------------------------------------------------------------------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("JourneySurface")
    h.fit()
    h.ribbon("Create Sketch")


def pick_yz():
    h.check("no pop-up", not h.popups(), h.popups())
    pl.click_on_plane(V(0, 12, 8))


def draw_line():
    sk = h.in_sketch()
    h.check(
        "sketch open on YZ",
        sk is not None and sk.AttachmentSupport[0][0].Role == "YZ_Plane",
        sk and sk.AttachmentSupport,
    )
    if sk is None:
        return
    st.add_lines(sk, [(-5, 4), (35, 12)])
    s["sketch"] = sk


def finish_sketch():
    h.ribbon("Finish Sketch")


def sketch_done():
    h.check("left the sketch", h.in_sketch() is None)
    sk = s.get("sketch")
    ends = sorted((v.Point.y, v.Point.z, v.Point.x) for v in sk.Shape.Vertexes) if sk else []
    h.check(
        "the line runs from (y -5, z 4) to (y 35, z 12) at x 0",
        len(ends) == 2
        and all(st.near(a, b, 1e-9) for a, b in zip(ends[0], (-5, 4, 0)))
        and all(st.near(a, b, 1e-9) for a, b in zip(ends[1], (35, 12, 0))),
        ends,
    )
    h.fit()
    pi.menu("Box")


# -- 2. the box ---------------------------------------------------------------------------------
def box_plane():
    p = pi.panel("BoxPanel")
    h.check("Box dialog open", p is not None)
    pl.click_on_plane(V(15, -15, 0))


def box_corner1():
    pl.click_on_plane(V(0, 0, 0))


def box_corner2():
    p = pi.panel("BoxPanel")
    h.check(
        "first corner on the origin", p is not None and p.points == [(0.0, 0.0)], p and p.points
    )
    pl.click_on_plane(V(40, 30, 0))


box_corner2.wait_ms = 1200


def box_height():
    p = pi.panel("BoxPanel")
    if p is None:
        h.check("Box dialog still open", False)
        return
    h.check("40 x 30", (p.length.value(), p.width.value()) == (40.0, 30.0), p.length.value())
    ui.type_into(p.height.widget, "20")


def box_ok():
    h.check("24000 previewed", st.near(pi.total_volume(), 24000.0), pi.total_volume())
    h.task_button("OK")


def box_done():
    h.check("Box dialog closed", pi.no_dialog())
    h.check("Box 1 in the timeline", "Box 1" in titles(), titles())
    s["box"] = h.body()
    h.check("a 24000 box", st.near(vol(s["box"]), 24000.0), vol(s["box"]))
    bb = s["box"].Shape.BoundBox
    h.check(
        "40 x 30 x 20 at the origin",
        [round(x, 6) for x in (bb.XMin, bb.YMin, bb.ZMin, bb.XMax, bb.YMax, bb.ZMax)]
        == [0, 0, 0, 40, 30, 20],
        bb,
    )
    h.fit()
    h.click_empty()
    st.tab("SURFACE")
    st.menu("CREATE", "Extrude")


# -- 3. the surface -----------------------------------------------------------------------------
def click_line():
    p = st.panel()
    h.check("surface Extrude open", p is not None and p.kind == "extrude")
    h.check("clicked the line in front of the box", h.click_edge(V(0, -3, 4.4)))


def two_sides():
    st.settle()
    p = st.panel()
    h.check("the line is the profile", p is not None and len(p.picks["profile"]) == 1)
    st.choose("direction", "Two Sides")


def type_45():
    st.settle()
    st.type_field("distance", "45")


def type_5():
    st.settle()
    st.type_field("distance2", "5")


def extrude_ok():
    st.settle()
    body = st.step_body()
    s["surf"] = body
    h.check("2039.61", body is not None and st.near(st.area(body), S_AREA, 1e-6), st.area(body))
    if body is not None:
        bb = body.Shape.BoundBox
        h.check(
            "x -5 .. 45, y -5 .. 35, z 4 .. 12",
            all(
                st.near(a, b, 1e-6)
                for a, b in zip(
                    (bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax), (-5, 45, -5, 35, 4, 12)
                )
            ),
            bb,
        )
    h.shot("1-surface")
    st.ok()


def extrude_done():
    from sciforge import surface

    h.check("dialog closed", st.panel() is None)
    h.check("Extrude 1 in the timeline", "Extrude 1" in titles(), titles())
    h.check("a surface body", surface.is_surface_body(s["surf"]))
    h.check("the box untouched", st.near(vol(s["box"]), 24000.0))
    h.click_empty()
    Gui.Selection.clearSelection()
    st.menu("MODIFY", "Split Body")


# -- 4. Split Body ------------------------------------------------------------------------------
def split_panel():
    from sciforge import split_ui

    p = split_ui.SplitPanel.last
    return p if p is not None and not p._closed else None


def split_click_box():
    h.check("Split Body open", split_panel() is not None)
    h.click(V(40, 25, 1))


def split_click_surface():
    p = split_panel()
    h.check("the box to split", p is not None and p.options["body"] is s["box"], p and p.options)
    h.click(V(20, -2.5, 4.5))


def split_pieces():
    from sciforge import split

    st.settle()
    h.idle_step()()
    p = split_panel()
    h.check(
        "the surface is the tool",
        p is not None and p.options["tools"] == [(s["surf"], "")],
        p and p.options["tools"],
    )
    feature = p.target if p is not None else None
    others = split.piece_bodies(feature) if feature is not None else []
    h.check("one new body", len(others) == 1, others)
    if others:
        s["lower"] = others[0]
    h.check("the box keeps 14400 (above)", st.near(vol(s["box"]), 24000 - BELOW), vol(s["box"]))
    h.check("the new body 9600 (below)", others and st.near(vol(others[0]), BELOW), others)
    h.shot("2-split")
    st.ok()


def split_done():
    from sciforge import surface

    h.check("dialog closed", split_panel() is None)
    s["split_title"] = title("Split Body")
    h.check("Split Body in the timeline", s["split_title"] is not None, titles())
    h.check("the surface is still a surface", surface.is_surface_body(s["surf"]))
    bb = s["box"].Shape.BoundBox
    h.check("the upper piece: z 5 .. 20", st.near(bb.ZMin, 5) and st.near(bb.ZMax, 20), bb)
    st.tab("SURFACE")
    Gui.Selection.clearSelection()
    h.click(V(20, 15, 20))


# -- 5. SURFACE Delete --------------------------------------------------------------------------
def delete_top():
    h.check("the top face is selected", bool(Gui.Selection.getSelectionEx()))
    h.press(QtCore.Qt.Key_Delete)


def top_deleted():
    from sciforge import surfmod

    upper = s["box"]
    h.check("the upper piece is a surface body now", surfmod.is_surface_body(upper))
    h.check("5 faces", s4.faces(upper) == 5, s4.faces(upper))
    h.check(
        "its area without the top (2903.77)",
        st.near(st.area(upper), upper_open_area(), 1e-6),
        (st.area(upper), upper_open_area()),
    )
    h.check("the lower piece untouched", st.near(vol(s["lower"]), BELOW), vol(s["lower"]))
    h.check("Delete Face in the timeline", title("Delete Face") is not None, titles())
    s["area"] = st.area(upper)
    Gui.Selection.clearSelection()
    h.click_edge(V(0, 0, 12))


# -- 6. Fillet, Chamfer -------------------------------------------------------------------------
def fillet_menu():
    h.check("the corner edge is selected", bool(Gui.Selection.getSelectionEx()))
    st.menu("MODIFY", "Fillet")


def fillet_radius():
    s4.settle()
    p = s4.panel()
    h.check("the surface Fillet", p is not None and p.kind == "surface_fillet", p and p.kind)
    h.check("on the upper piece", p is not None and p.body is s["box"], p and p.body)
    h.check("one edge", p is not None and len(p.picked) == 1, p and p.picked)
    s4.type_main("3")


def fillet_ok():
    s4.settle()
    st.ok()


def filleted():
    h.check("dialog closed", s4.panel() is None)
    upper = s["box"]
    want = s["area"] + fillet_area_change()
    h.check("6 faces", s4.faces(upper) == 6, s4.faces(upper))
    h.check(
        "the area with the round corner",
        st.near(st.area(upper), want, 1e-6),
        (st.area(upper), want),
    )
    s["area"] = st.area(upper)
    Gui.Selection.clearSelection()
    h.click_edge(V(40, 0, 12))


def chamfer_menu():
    h.check("the other corner edge is selected", bool(Gui.Selection.getSelectionEx()))
    st.menu("MODIFY", "Chamfer")


def chamfer_distance():
    s4.settle()
    p = s4.panel()
    h.check("the surface Chamfer", p is not None and p.kind == "surface_chamfer", p and p.kind)
    h.check("starts with the edge", p is not None and len(p.picked) == 1, p and p.picked)
    s4.type_main("2")


def chamfer_ok():
    s4.settle()
    st.ok()


def chamfered():
    h.check("dialog closed", s4.panel() is None)
    upper = s["box"]
    want = s["area"] + chamfer_area_change()
    h.check("7 faces", s4.faces(upper) == 7, s4.faces(upper))
    h.check("the area with the bevel", st.near(st.area(upper), want, 1e-6), (st.area(upper), want))
    h.check("Fillet and Chamfer in the timeline", title("Fillet") and title("Chamfer"), titles())
    h.shot("3-round-and-bevel")
    h.click_empty()
    Gui.Selection.clearSelection()
    st.menu("CREATE", "Patch")


# -- 7. Patch, per-edge continuity --------------------------------------------------------------
def patch_rim():
    p = st.panel()
    h.check("Patch open", p is not None and p.kind == "patch")
    h.check("clicked the rim", h.click_edge(V(20, 0, 20)))


def patch_loop():
    st.settle()
    p = st.panel()
    if p is None:
        return
    h.check("the whole rim: 6 edges", len(p.picks["boundary"]) == 6, p.picks["boundary"])
    body = st.step_body(p)
    s["lid"] = body
    h.check("a flat lid", body is not None and st.near(st.area(body), LID, 1e-6), st.area(body))
    st.toggle_check("group_edges")


def per_edge():
    st.settle()
    p = st.panel()
    if p is None:
        return
    h.check("one Continuity row per edge", len(p.edge_combos) == 6, len(p.edge_combos))
    h.check("chose Tangent for edge 1", ui.choose(p.edge_combos[0], "Tangent"))


def tangent_refused():
    st.settle()
    p = st.panel()
    text = st.message()
    h.check("Tangent onto the vertical walls is refused with the reason", "Connected" in text, text)
    if p is not None:
        h.check("back to Connected", ui.choose(p.edge_combos[0], "Connected"))


def patch_ok():
    st.settle()
    body = st.step_body()
    s["lid"] = body
    h.check("the lid again", body is not None and st.near(st.area(body), LID, 1e-6), st.area(body))
    if body is not None:
        bb = body.Shape.BoundBox
        h.check("at z 20", st.near(bb.ZMin, 20) and st.near(bb.ZMax, 20), bb)
    st.ok()


def patch_done():
    h.check("dialog closed", st.panel() is None)
    h.check("Patch 1 in the timeline", "Patch 1" in titles(), titles())
    h.click_empty()
    st.menu("MODIFY", "Stitch")


# -- 8. Stitch, Join ----------------------------------------------------------------------------
def stitch_walls():
    p = st.panel()
    h.check("Stitch open", p is not None and p.kind == "stitch")
    h.click(V(20, 0, 15))


def stitch_lid():
    st.settle()
    h.click(V(20, 15, 20))


def stitch_closed():
    st.settle()
    p = st.panel()
    if p is None:
        return
    h.check("two bodies", len(p.picks["bodies"]) == 2, p.picks["bodies"])
    h.check("Closed", "Closed" in p.open_label.text(), p.open_label.text())
    st.choose("operation", "Join")


def stitch_joined():
    from sciforge import bodies

    st.settle()
    p = st.panel()
    step = p.step if p is not None else None
    target = bodies.body_of(step) if step is not None else None
    s["solid"] = target
    want = 24000 - fillet_volume(20) - chamfer_volume(20)
    h.check("the step goes into the lower piece's body", target is s["lower"], target)
    h.check(
        "one solid: 24000 less the corners",
        st.near(vol(target), want, 1e-6),
        (vol(target), want),
    )
    st.ok()


def stitch_done():
    from sciforge import bodies

    h.check("dialog closed", st.panel() is None)
    h.check("Stitch 1 in the timeline", "Stitch 1" in titles(), titles())
    used = bodies.consumed(doc())
    h.check("the upper piece and the lid are used up", s["box"].Name in used, used)
    bb = s["solid"].Shape.BoundBox
    h.check("40 x 30 x 20 again", st.near(bb.ZMax, 20) and st.near(bb.XMax, 40), bb)
    h.shot("4-stitched")
    st.tab("SOLID")
    Gui.Selection.clearSelection()
    h.click(V(39, 1, 15))


# -- 9. SOLID Delete heals ----------------------------------------------------------------------
def delete_bevel():
    sel = Gui.Selection.getSelectionEx()
    h.check("the bevel's face is selected", bool(sel) and sel[0].SubElementNames, sel)
    h.press(QtCore.Qt.Key_Delete)


def bevel_alone_refused():
    st.settle()
    v = vol(s["solid"])
    want = 24000 - fillet_volume(20) - chamfer_volume(20)
    # the bevel's foot meets a sliver of the lower piece's slanted top (the triangle the
    # bevel left uncovered): healing the bevel alone would have to make that face vanish
    h.check("the bevel alone: refused", "cannot be deleted" in told(), told())
    h.check(
        "the reason: the sliver must go too (not 'neighbours run parallel': the walls lean)",
        "parallel" not in told() and "Ctrl+click" in told(),
        told(),
    )
    h.check("the solid unchanged", st.near(v, want, 1e-9), v)
    Gui.Selection.clearSelection()
    h.click(V(39, 1, 15))


def ctrl_click_sliver():
    h.click(V(39.333, 0.667, 5.1333), QtCore.Qt.ControlModifier)


def delete_both():
    sel = Gui.Selection.getSelectionEx()
    names = [n for x in sel for n in x.SubElementNames]
    h.check("the bevel and the sliver selected", len(names) == 2, names)
    h.press(QtCore.Qt.Key_Delete)


def healed():
    st.settle()
    h.idle_step()()
    want = 24000 - fillet_volume(20)
    v = vol(s["solid"])
    h.check("SOLID Delete heals: the corner sharp again", st.near(v, want, 1e-6), (v, want, told()))
    h.check("still a solid", s["solid"].Shape.Solids and s["solid"].Shape.isValid())
    deletes = [t for t in titles() if t.startswith("Delete")]
    h.check("a second Delete in the timeline", len(deletes) >= 2, titles())
    h.shot("5-healed")
    st.tab("SURFACE")
    h.check("double-clicked Extrude 1", st.double_click_timeline("Extrude 1"))


# -- 10. edit the early surface step ------------------------------------------------------------
def edit_extrude():
    st.settle()
    p = st.panel()
    h.check("Edit Extrude", p is not None and p.kind == "extrude" and p.editing)
    if p is None:
        return
    h.check("Two Sides read back", p.options["direction"] == "two_sides", p.options)
    st.choose("direction", "Symmetric")


def type_15():
    st.settle()
    p = st.panel()
    h.check("Half Length", p is not None and p.options["measurement"] == "half", p and p.options)
    st.type_field("distance", "15")


def extrude_edit_ok():
    st.settle()
    st.ok()


def extrude_edited():
    st.settle()
    h.idle_step()()
    h.check("dialog closed", st.panel() is None)
    bb = s["surf"].Shape.BoundBox
    h.check("the surface now x -15 .. 15", st.near(bb.XMin, -15) and st.near(bb.XMax, 15), bb)
    want = 24000 - fillet_volume(20)
    h.check(
        "the later steps follow: the split still runs through the box",
        st.near(vol(s["solid"]), want, 1e-6),
        (vol(s["solid"]), want),
    )
    bad = [o.Label for o in doc().Objects if "Invalid" in o.State or "Error" in o.State]
    h.check("no step in error", not bad, bad)
    h.check("double-clicked Box 1", st.double_click_timeline("Box 1"))


# -- 11. edit the box ---------------------------------------------------------------------------
def edit_box():
    p = pi.panel("BoxPanel")
    h.check("Edit Box", p is not None and p.editing)
    if p is not None:
        ui.type_into(p.height.widget, "25")


def box_edit_ok():
    h.task_button("OK")


def box_edited():
    st.settle()
    h.idle_step()()
    want = 30000 - fillet_volume(25)
    v = vol(s["solid"])
    h.check(
        "every later step follows: 30000 less the round corner", st.near(v, want, 1e-6), (v, want)
    )
    bb = s["solid"].Shape.BoundBox
    h.check("25 high", st.near(bb.ZMax, 25), bb)
    bad = [o.Label for o in doc().Objects if "Invalid" in o.State or "Error" in o.State]
    h.check("no step in error", not bad, bad)
    s["v25"] = v
    st.undo()


def box_undone():
    want = 24000 - fillet_volume(20)
    h.check("Undo: 20 high again", st.near(vol(s["solid"]), want, 1e-6), vol(s["solid"]))
    st.redo()


def box_redone():
    h.check("Redo: 25 high", st.near(vol(s["solid"]), s["v25"], 1e-9), vol(s["solid"]))
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-journey-sf-"), "journey_surface.FCStd")
    s["path"] = path
    s["label"] = s["solid"].Label
    s["titles"] = titles()
    doc().saveAs(path)
    h.check("saved", os.path.isfile(path), path)


def ctrl_s():
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


def describe():
    from SciForgeTests.gui import versions_input as vi

    h.check("the Save dialog asks for a version description", vi.version_dialog() is not None)
    vi.accept_save()


def close():
    h.check("nothing unsaved", not doc().isTouched())
    App.closeDocument(doc().Name)


def reopen():
    App.openDocument(s["path"])
    h.fit()


def reopened():
    found = doc().getObjectsByLabel(s["label"])
    solid = found[0] if found else None
    h.check("the part is back", solid is not None, s["label"])
    if solid is None:
        return
    h.check("the same volume", st.near(vol(solid), s["v25"], 1e-9), vol(solid))
    h.check("the same timeline", titles() == s["titles"], (titles(), s["titles"]))
    bad = [o.Label for o in doc().Objects if "Invalid" in o.State or "Error" in o.State]
    h.check("no step in error", not bad, bad)
    h.check("double-clicked Patch 1", st.double_click_timeline("Patch 1"))


def patch_after_reopen():
    st.settle()
    p = st.panel()
    h.check("the Patch edits after the reopen", p is not None and p.kind == "patch" and p.editing)
    if p is None:
        return
    h.check("Group Edges off read back", not p.rows["group_edges"][0].isChecked())
    h.check("its 6 rows", len(p.edge_combos) == 6, len(p.edge_combos))
    s["solid"] = doc().getObjectsByLabel(s["label"])[0]
    st.esc()


def closed_again():
    h.check("Esc closed it", st.panel() is None)
    h.check("unchanged", st.near(vol(s["solid"]), s["v25"], 1e-9), vol(s["solid"]))


h.run(
    "journey_surface",
    [
        new_design,
        pick_yz,
        draw_line,
        finish_sketch,
        sketch_done,
        box_plane,
        box_corner1,
        box_corner2,
        box_height,
        box_ok,
        box_done,
        click_line,
        two_sides,
        type_45,
        type_5,
        extrude_ok,
        extrude_done,
        split_click_box,
        split_click_surface,
        split_pieces,
        split_done,
        delete_top,
        top_deleted,
        fillet_menu,
        fillet_radius,
        fillet_ok,
        filleted,
        chamfer_menu,
        chamfer_distance,
        chamfer_ok,
        chamfered,
        patch_rim,
        patch_loop,
        per_edge,
        tangent_refused,
        patch_ok,
        patch_done,
        stitch_walls,
        stitch_lid,
        stitch_closed,
        stitch_joined,
        stitch_done,
        delete_bevel,
        bevel_alone_refused,
        ctrl_click_sliver,
        delete_both,
        healed,
        edit_extrude,
        type_15,
        extrude_edit_ok,
        extrude_edited,
        edit_box,
        box_edit_ok,
        box_edited,
        box_undone,
        box_redone,
        ctrl_s,
        describe,
        close,
        reopen,
        reopened,
        patch_after_reopen,
        closed_again,
    ],
)
