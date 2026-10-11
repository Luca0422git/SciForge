# SPDX-License-Identifier: LGPL-2.1-or-later
"""Body tools on multi-body and multi-feature parts (QA pass, second file), only real input.

Every path uses only real input: ribbon buttons, keys, clicks on the bodies, the browser and
the timeline, typing into the dialog fields.

  I  Two bodies (0..20 x 0..20 x 10 and 40..60, both 4000) moved at once with Create Copy,
     Y 50: two copies. Edited from the timeline (Y 60): both copies follow. The first
     original deleted (browser, Modify > Delete): its copy keeps its shape. Undo. The
     original's extrude edited to 20 high: its copy follows (it copies the body as it was at
     that point of the timeline).
  J  A part made of several features: box 40 x 30 x 10, a round boss r 3 x 5 on top, a hole
     r 5 x 10 deep. Moved up 20 (Translate). The box's extrude edited to 15 high: the move
     and everything on top follow. Split Body with the boss's round face (Extend Splitting
     Tool): a plug r 3 through the whole part becomes its own body. Undo.
  K  Combine with two tool bodies; a click on a picked tool drops it again (it is drawn
     solid again and stays in the design after OK). Edited from the timeline: the dropped
     body clicked back in.
  L  Rotate about a straight edge of the body (the vertical edge at x 40, y 0), -90
     typed: the body turns about that edge.
  M  Combine with Body2 as the target (the first body used up), saved, closed, opened again;
     Create Sketch on XY and E: the new extrude must be shown (not go into the hidden body).
  N  The used-up body (listed with its eye off) clicked in the browser and Del pressed there
     (the browser's own Delete, as Luca tidies up): the Combine keeps its result. Undo.
  P  (on J's part) Point to Point, a click on the boss's round top edge right next to where
     OpenCASCADE starts the circle: the origin point is the circle's centre, as in Fusion.
  O  Construct > Offset Plane 4 mm under the top face, then Split Body with that construction
     plane (picked in the browser): 7200 + 4800. Undo.
  Q  Appearance on the top face only (blue), then Move/Copy (X 50, Z 5, Z Angle 90): the top
     face is still the blue one after the move (a face keeps its look when it moves). Undo.
  R  Combine Join, then Press Pull (Q) on the joined top face +5 (31500); the Combine edited
     to Cut from the timeline: the merged top face is made another way now, so the Press Pull
     says in the timeline that its face must be picked again (FreeCAD's naming, the same with
     its own Boolean; no Report-view error, no pop-up). Undo: joined and pulled again.
"""
import math

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import pattern_steps as ps

V = App.Vector
state = {}
BOSS = 45 * math.pi
HOLE = 250 * math.pi


def moves():
    return s.steps_of_kind("MoveCopy")


def combines():
    return s.steps_of_kind("Combine")


def splits():
    return s.steps_of_kind("SplitBody")


def bbox(body):
    return body.Shape.BoundBox


def box_is(name, box, expect, tol=1e-6):
    got = [box.XMin, box.YMin, box.ZMin, box.XMax, box.YMax, box.ZMax]
    ok = all(abs(a - c) <= tol for a, c in zip(got, expect))
    return h.check(name, ok, (got, expect))


def extrude_of(body):
    found = [
        o
        for o in body.Group
        if "BaseFeature" in o.PropertiesList and o.TypeId != "PartDesign::FeatureBase"
    ]
    return found[0] if found else None


def no_problems(where):
    from sciforge import timeline_ops

    found = []
    for obj, _b in timeline_ops.steps(App.ActiveDocument):
        kind, why = timeline_ops.problem(obj)
        if kind == "error":
            found.append((obj.Label, why))
    h.check("no step in error after %s" % where, not found, found)


# == I: two bodies copied at once ===============================================================
def i_open():
    h.click_empty()
    h.fit()
    h.press("m")


def i_body1():
    h.click(V(10, 10, 10))


def i_body2():
    h.click(V(50, 10, 10))


def i_values():
    p = s.panel()
    if h.check("Move open", p is not None):
        h.check("both bodies picked", p.options["bodies"] == s.bodies()[:2], p.options)
        b.choose(p.move_type, "Translate")
        s.type_value(p.distance_fields[1].widget, "50")
        s.toggle(p.copy)


def i_preview():
    found = s.bodies()
    h.check("preview: four bodies", len(found) == 4, [x.Label for x in found])
    if len(found) == 4:
        h.check(
            "originals stay", s.close(bbox(found[0]).YMin, 0) and s.close(bbox(found[1]).YMin, 0)
        )
        h.check(
            "copies at y 50", s.close(bbox(found[2]).YMin, 50) and s.close(bbox(found[3]).YMin, 50)
        )
    h.shot("I-copies")


def i_ok():
    h.task_button("OK")


def i_done():
    found = moves()
    h.check("one step per copy", len(found) == 2, found)
    if len(found) == 2:
        h.check("they share one Move", found[0].MoveId == found[1].MoveId)
    h.check("copies 4000 each", [round(s.volume(x)) for x in s.bodies()] == [4000] * 4)


def i_edit():
    s.timeline_double_click(moves()[0])


def i_edit_y():
    p = s.panel()
    if h.check("Move edit open", p is not None and p.editing, p):
        h.check("edit lists both bodies", p.options["bodies"] == s.bodies()[:2], p.options)
        s.type_value(p.distance_fields[1].widget, "60")


def i_edit_ok():
    h.task_button("OK")


def i_edited():
    found = s.bodies()
    h.check("still four bodies", len(found) == 4, [x.Label for x in found])
    if len(found) == 4:
        h.check("both copies at y 60", all(s.close(bbox(x).YMin, 60) for x in found[2:]))


def i_pick_body1():
    state["copy1"] = s.bodies()[2].Name
    s.click_browser_row(s.bodies()[0].Label)


def i_delete_body1():
    s.menu("MODIFY", "Delete")


i_delete_body1.wait_ms = 1200


def i_deleted():
    found = s.bodies()
    h.check("three bodies left", len(found) == 3, [x.Label for x in found])
    copy = App.ActiveDocument.getObject(state["copy1"])
    h.check("the copy of the deleted body is still there", copy is not None)
    if copy is not None:
        h.check("it keeps its shape", s.close(s.volume(copy), 4000), s.volume(copy))
        h.check("and its place", s.close(bbox(copy).YMin, 60), bbox(copy))
        h.check("and is shown", s.shown(copy))
    no_problems("deleting a copied body")


def i_undo():
    s.undo()


def i_undone():
    found = s.bodies()
    h.check("undo: four bodies", len(found) == 4, [x.Label for x in found])


def i_edit_extrude():
    h.fit()
    s.timeline_double_click(extrude_of(s.bodies()[0]))


i_edit_extrude.wait_ms = 1200


def i_height():
    p = b.active_panel()
    field = getattr(getattr(p, "distance", None), "widget", None)
    if h.check("extrude edit", field is not None):
        s.type_value(field, "20")


def i_height_ok():
    h.task_button("OK")


i_height_ok.wait_ms = 1200


def i_followed():
    found = s.bodies()
    vols = [round(s.volume(x)) for x in found]
    h.check("original and its copy 8000, the others 4000", vols == [8000, 4000, 8000, 4000], vols)
    no_problems("editing a copied body's extrude")


# == J: a part of several features ============================================================
def j_open():
    state["j_volume"] = h.solid_volume()
    h.click_empty()
    h.fit()
    h.press("m")


def j_body():
    h.click(V(32, 25, 10))


def j_up():
    p = s.panel()
    if h.check("Move open", p is not None):
        b.choose(p.move_type, "Translate")
        s.type_value(p.distance_fields[2].widget, "20")


def j_ok():
    h.task_button("OK")


def j_moved():
    box = bbox(s.bodies()[0])
    box_is("moved up 20", box, [0, 0, 20, 40, 30, 35])
    h.check("volume kept", s.close(s.volume(s.bodies()[0]), state["j_volume"]))


def j_edit_box():
    h.fit()
    s.timeline_double_click(extrude_of(s.bodies()[0]))


j_edit_box.wait_ms = 1200


def j_height():
    p = b.active_panel()
    field = getattr(getattr(p, "distance", None), "widget", None)
    if h.check("extrude edit", field is not None):
        s.type_value(field, "15")


def j_height_ok():
    h.task_button("OK")


j_height_ok.wait_ms = 1500


def j_followed():
    body = s.bodies()[0]
    box_is("the move follows: z 20..40", bbox(body), [0, 0, 20, 40, 30, 40])
    expect = 18000 + BOSS - HOLE
    h.check("boss and hole follow", s.close(s.volume(body), expect), (s.volume(body), expect))
    no_problems("editing the first step under a move")
    h.fit()
    h.shot("J-followed")


def j_split_open():
    h.click_empty()
    h.fit()
    h.ribbon("Split Body")


def j_split_body():
    h.click(V(32, 25, 35))


def j_split_boss():
    p = s.panel()
    if p is not None:
        h.check("body taken", p.options["body"] is s.bodies()[0], p.options)
    r = 3.0 / math.sqrt(2.0)
    h.click(V(8 + r, 8 - r, 37.5))  # the boss's round side, facing the camera


def j_split_preview():
    p = s.panel()
    if p is not None:
        h.check("the boss's face is the tool", p.options["tool"] is not None, p.options)
        h.check("Extend on", p.extend.isChecked())
    found = s.bodies()
    h.check("preview: two bodies", len(found) == 2, [x.Label for x in found])
    if len(found) == 2:
        plug = 9 * math.pi * 20  # r 3 from z 20 to 40
        h.check(
            "the plug: r 3 through the part", s.close(s.volume(found[1]), plug), s.volume(found[1])
        )
        h.check(
            "nothing lost",
            s.close(s.volume(found[0]) + s.volume(found[1]), 18000 + BOSS - HOLE),
        )
    h.shot("J-split-round")


def j_split_ok():
    h.task_button("OK")


def j_split_done():
    h.check("dialog closed", s.panel() is None)
    h.check("two bodies", len(s.bodies()) == 2)
    no_problems("splitting with a round face")


def j_undo():
    s.undo()


def j_undone():
    h.check("undo: one body", len(s.bodies()) == 1, [x.Label for x in s.bodies()])


# == K: Combine with two tools, one dropped again ===============================================
def k_open():
    h.click_empty()
    h.fit()
    h.ribbon("Combine")


def k_target():
    h.click(V(5, 5, 10))


def k_tool2():
    h.click(V(60, 15, 10))


def k_tool3():
    h.click(V(15, 45, 10))


def k_three():
    p = s.panel()
    if p is not None:
        h.check("two tools", len(p.options["tools"]) == 2, p.options)
    # 12000 + 12000 - 3000 + 3000 - 1000
    h.check(
        "join of three: 23000", s.close(s.volume(s.bodies()[0]), 23000), s.volume(s.bodies()[0])
    )
    h.check("tools see-through", s.bodies()[1].ViewObject.Transparency > 0)
    h.shot("K-two-tools")


def k_drop():
    h.click(V(60, 15, 10))  # Body2 again: dropped


def k_dropped():
    p = s.panel()
    if p is not None:
        h.check("one tool left", p.options["tools"] == [s.bodies()[2]], p.options)
    h.check(
        "join without Body2: 14000",
        s.close(s.volume(s.bodies()[0]), 14000),
        s.volume(s.bodies()[0]),
    )
    h.check("Body2 drawn solid again", s.bodies()[1].ViewObject.Transparency == 0)
    h.check("Body2 shown", s.shown(s.bodies()[1]))


def k_ok():
    h.task_button("OK")


def k_done():
    found = s.bodies()
    h.check("Body2 stays in the design", s.shown(found[1]))
    h.check("Body3 used up", not s.shown(found[2]))
    h.check("Body1 14000", s.close(s.volume(found[0]), 14000), s.volume(found[0]))


def k_edit():
    s.timeline_double_click(combines()[0])


def k_add_back():
    p = s.panel()
    if h.check("Combine edit open", p is not None and p.editing, p):
        h.check("edit shows one tool", p.options["tools"] == [s.bodies()[2]], p.options)
    h.click(V(60, 15, 10))


def k_added():
    p = s.panel()
    if p is not None:
        h.check("two tools again", len(p.options["tools"]) == 2, p.options)
    h.check("23000 again", s.close(s.volume(s.bodies()[0]), 23000), s.volume(s.bodies()[0]))
    h.task_button("OK")


def k_added_done():
    found = s.bodies()
    h.check("Body2 used up now", not s.shown(found[1]))
    h.check("Body3 used up", not s.shown(found[2]))
    h.check("both drawn solid", all(x.ViewObject.Transparency == 0 for x in found))
    no_problems("adding a tool back")


# == L: rotate about an edge of the body ==========================================================
def l_open():
    h.click_empty()
    h.fit()
    h.press("m")


def l_body():
    h.click(V(20, 15, 10))


def l_rotate():
    p = s.panel()
    if h.check("Move open", p is not None):
        b.choose(p.move_type, "Rotate")


def l_edge():
    p = s.panel()
    if p is not None:
        h.check("axis box waits", p.active == "axis", p.active)
    h.click_edge(V(40, 0, 5))


def l_angle():
    p = s.panel()
    if p is not None:
        h.check(
            "the edge is the axis", p.options["axis_dir"] is not None, h.state.get("last_click")
        )
        if p.options["axis_dir"] is not None:
            h.check("vertical axis", abs(abs(p.options["axis_dir"][2]) - 1) < 1e-9, p.options)
        s.type_value(p.angle.widget, "-90")


def turned_about_edge(name):
    """-90 about the edge: the edge's direction (up or down) decides which way, as in
    Fusion; either way the edge stays where it is and the body swings round it."""
    box = bbox(s.bodies()[0])
    got = [box.XMin, box.YMin, box.ZMin, box.XMax, box.YMax, box.ZMax]
    ways = ([40, 0, 0, 70, 40, 10], [10, -40, 0, 40, 0, 10])
    ok = any(all(abs(a - c) <= 1e-6 for a, c in zip(got, way)) for way in ways)
    return h.check(name, ok, (got, ways))


def l_turned():
    turned_about_edge("turned -90 about the edge")
    h.shot("L-rotate-edge")


def l_ok():
    h.task_button("OK")


def l_done():
    turned_about_edge("rotated about the edge")
    no_problems("rotating about an edge")


# == M: a design reopened after a Combine that used up the first body ===========================
def m_open():
    h.click_empty()
    h.fit()
    h.ribbon("Combine")


def m_target():
    h.click(V(60, 15, 10))  # Body2 is the target


def m_tool():
    h.click(V(10, 15, 10))  # the first body is used up


def m_ok():
    h.task_button("OK")


def m_save_close():
    import os
    import tempfile

    found = s.bodies()
    h.check("the first body is used up", not s.shown(found[0]))
    h.check("Body2 joined: 21000", s.close(s.volume(found[1]), 21000), s.volume(found[1]))
    doc = App.ActiveDocument
    state["m_path"] = os.path.join(tempfile.mkdtemp(), "bodies_qa_reopen.FCStd")
    doc.saveAs(state["m_path"])
    App.closeDocument(doc.Name)


def m_reopen():
    from PySide import QtWidgets

    App.openDocument(state["m_path"])
    QtWidgets.QApplication.processEvents()


m_reopen.wait_ms = 1500


def m_sketch():
    state["m_volume"] = s.total_volume()
    h.check("reopened: 21000 shown", s.close(state["m_volume"], 21000), state["m_volume"])
    h.fit()
    h.ribbon("Create Sketch")


def m_pick_xy():
    h.click(V(12, -8, 0))


def m_draw():
    sk = h.in_sketch()
    if h.check("sketch open", sk is not None):
        h.draw_rectangle(sk, 80, 0, 100, 20)


def m_finish():
    h.ribbon("Finish Sketch")


def m_extrude():
    h.fit()
    h.press("e")


def m_height():
    p = b.active_panel()
    field = getattr(getattr(p, "distance", None), "widget", None)
    if h.check("extrude dialog", field is not None):
        s.type_value(field, "10")


def m_extrude_ok():
    h.task_button("OK")


def m_extruded():
    got = s.total_volume()
    h.check("the new extrude is shown", s.close(got, state["m_volume"] + 4000), got)
    h.check("the used-up body is unchanged", s.close(s.volume(s.bodies()[0]), 12000))
    h.check("and still hidden", not s.shown(s.bodies()[0]))
    h.shot("M-after-reopen")


# == N: Del in the browser on the used-up body ==================================================
def n_pick_used_up_row():
    state["n_volume"] = s.volume(s.bodies()[1])
    state["n_bodies"] = len(s.bodies())
    s.click_browser_row(s.bodies()[0].Label)


def n_del_key():
    from SciForgeTests.gui import widget_input as w

    tree = s.browser()
    if h.check("browser", tree is not None):
        h.check("the used-up body is selected", s.selected_names() == [s.bodies()[0].Name])
        w.key(tree, QtCore.Qt.Key_Delete)


n_del_key.wait_ms = 1500


def n_deleted():
    found = s.bodies()
    h.check(
        "the used-up body is gone", len(found) == state["n_bodies"] - 1, [x.Label for x in found]
    )
    combine = combines()[0] if combines() else None
    if h.check("the Combine is still there", combine is not None):
        h.check("and still works", "Invalid" not in list(combine.State), combine.State)
    joined = [x for x in found if s.close(s.volume(x), state["n_volume"])]
    h.check("the joined body keeps its 21000", bool(joined), [s.volume(x) for x in found])
    no_problems("deleting a used-up body in the browser")


def n_undo():
    s.undo()


def n_undone():
    found = s.bodies()
    h.check("undo: the body is back", len(found) == state["n_bodies"], [x.Label for x in found])
    if found:
        h.check("undo: still used up", not s.shown(found[0]))
    h.check("undo: joined 21000", s.close(s.volume(found[1]), state["n_volume"]))
    no_problems("undoing the browser delete")


# == O: Split Body with a construction plane ======================================================
def o_offset_plane():
    h.click_empty()
    h.fit()
    h.ribbon("Offset Plane")


def o_top_face():
    h.click(V(20, 15, 10))


def o_distance():
    p = s.panel()
    field = getattr(getattr(p, "field", None), "widget", None)
    if h.check("Offset Plane dialog", field is not None, p):
        s.type_value(field, "-4")


def o_plane_ok():
    h.task_button("OK")


def o_plane_made():
    planes = [o for o in App.ActiveDocument.Objects if o.TypeId == "PartDesign::Plane"]
    if h.check("a construction plane", len(planes) == 1, planes):
        state["o_plane"] = planes[0].Label
        h.check(
            "6 mm up", abs(planes[0].getGlobalPlacement().Base.z - 6) < 1e-6, planes[0].Placement
        )


def o_split_open():
    h.click_empty()
    h.fit()
    h.ribbon("Split Body")


def o_split_body():
    h.click(V(20, 15, 10))


def o_pick_plane():
    s.click_browser_row(state.get("o_plane", "DatumPlane"))


def o_preview():
    p = s.panel()
    if p is not None:
        h.check("the plane is the tool", p.options["tool"] is not None, p.options)
    found = s.bodies()
    vols = [round(s.volume(x)) for x in found]
    h.check("split at z 6: 7200 and 4800", vols == [7200, 4800], vols)
    h.task_button("OK")


def o_done():
    found = s.bodies()
    h.check("dialog closed", s.panel() is None)
    if len(found) == 2:
        h.check("the new body is the top", s.close(bbox(found[1]).ZMin, 6), bbox(found[1]))
    no_problems("splitting with a construction plane")


def o_undo():
    s.undo()


def o_undone():
    h.check("undo: one body", len(s.bodies()) == 1, [x.Label for x in s.bodies()])


# == P: Point to Point from a round edge: its centre, never the circle's hidden start point ========
def p_open():
    state["p_box"] = list(bbox(s.bodies()[0]).Center)
    h.click_empty()
    h.fit()
    h.press("m")


def p_body():
    h.click(V(32, 25, 35))


def p_point_to_point():
    p = s.panel()
    if h.check("Move open", p is not None):
        h.check("body picked", len(p.options["bodies"]) == 1, p.options)
        b.choose(p.move_type, "Point to Point")


def p_round_edge():
    p = s.panel()
    if p is not None:
        h.check("origin point box waits", p.active == "from_point", p.active)
    a = math.radians(10)  # close to where OpenCASCADE starts the circle (angle 0)
    h.click_edge(V(8 + 3 * math.cos(a), 8 + 3 * math.sin(a), 40))


def p_centre():
    p = s.panel()
    if p is not None:
        got = p.options["from_point"]
        h.check(
            "the round edge gives its centre (8, 8, 40)",
            got is not None and (V(*got) - V(8, 8, 40)).Length < 1e-6,
            (got, h.state.get("last_click")),
        )
    h.press(QtCore.Qt.Key_Escape)


def p_nothing_moved():
    h.check("Esc: dialog closed", s.panel() is None)
    c = bbox(s.bodies()[0]).Center
    h.check("nothing moved", (c - V(*state["p_box"])).Length < 1e-9, c)


# == Q: a face's look follows the body when it is moved ==========================================
BLUE = (0.10, 0.28, 0.80)


def tip_colors():
    try:
        return [
            tuple(round(c, 3) for c in m.DiffuseColor[:3])
            for m in s.bodies()[0].Tip.ViewObject.ShapeAppearance
        ]
    except Exception:
        return []


def blue_faces():
    """Indices of the blue faces of the body's end step."""
    return [
        i for i, c in enumerate(tip_colors()) if all(abs(a - b) <= 0.01 for a, b in zip(c, BLUE))
    ]


def is_top(index, z):
    face = s.bodies()[0].Tip.Shape.Faces[index]
    return abs(face.CenterOfMass.z - z) < 1e-6 and face.Area > 1000


def click_item(view, item):
    from SciForgeTests.gui import widget_input as w

    view.scrollToItem(item)
    w.click(view.viewport(), view.visualItemRect(item).center())


def q_open_look():
    state["q_default"] = (tip_colors() or [None])[0]
    h.click_empty()
    h.fit()
    s.menu("MODIFY", "Appearance")


def q_faces_blue():
    p = s.panel()
    if h.check("Appearance open", p is not None and p.title == "Appearance", p):
        b.choose(p.apply_to, "Faces")
        click_item(p.library, p.item_for("Glossy plastic, blue"))


def q_click_top():
    h.click(V(20, 15, 10))


def q_look_ok():
    h.task_button("OK")


def q_blue_top():
    found = blue_faces()
    h.check("one face blue", len(found) == 1, tip_colors())
    if found:
        h.check("the top face", is_top(found[0], 10), found)
    others = [c for i, c in enumerate(tip_colors()) if i not in found]
    grey = state.get("q_default")
    h.check(
        "the other faces keep the part's usual grey",
        grey is not None and all(all(abs(a - b) <= 0.01 for a, b in zip(c, grey)) for c in others),
        (others, grey),
    )


def q_move():
    h.click_empty()
    h.fit()
    h.press("m")


def q_move_body():
    h.click(V(20, 15, 10))


def q_move_values():
    p = s.panel()
    if h.check("Move open", p is not None):
        s.type_value(p.distance_fields[0].widget, "50")
        s.type_value(p.distance_fields[2].widget, "5")
        s.type_value(p.angle_fields[2].widget, "90")


def q_move_ok():
    h.task_button("OK")


q_move_ok.wait_ms = 1200


def q_moved_blue():
    box = bbox(s.bodies()[0])
    h.check("moved (z 5..15)", s.close(box.ZMin, 5) and s.close(box.ZMax, 15), box)
    found = blue_faces()
    h.check("still one face blue after the move", len(found) == 1, tip_colors())
    if found:
        h.check("still the top face", is_top(found[0], 15), found)
    h.fit()
    h.shot("Q-moved-face-look")


def q_undo():
    s.undo()


def q_undone():
    found = blue_faces()
    h.check("undo: the top face is blue", len(found) == 1 and is_top(found[0], 10), found)


# == R: Press Pull after a Combine, then the Combine edited under it ===============================
def presspull_panel():
    from sciforge import presspull_ui

    p = presspull_ui.PressPullPanel.last
    return p if p is not None and not p._closed else None


def r_combine():
    h.click_empty()
    h.fit()
    h.ribbon("Combine")


def r_target():
    h.click(V(10, 15, 10))


def r_tool():
    h.click(V(60, 15, 10))


def r_combine_ok():
    h.task_button("OK")


def r_press_q():
    h.check("joined 21000", s.close(s.volume(s.bodies()[0]), 21000), s.volume(s.bodies()[0]))
    h.click_empty()
    h.fit()
    h.press("q")


def r_top():
    h.click(V(50, 15, 10))  # where Body2 was: the joined top face


def r_distance():
    p = presspull_panel()
    if h.check("Press Pull on the joined top face", p is not None and p.target is not None, p):
        s.type_value(p.field.widget, "5")


def r_presspull_ok():
    h.task_button("OK")


r_presspull_ok.wait_ms = 1200


def r_pulled():
    got = s.volume(s.bodies()[0])
    h.check("pulled up 5: 21000 + 70 x 30 x 5", s.close(got, 31500), got)
    no_problems("Press Pull after a Combine")


def r_edit_combine():
    s.timeline_double_click(combines()[0])


def r_cut():
    p = s.panel()
    if h.check("Combine edit open", p is not None and p.editing, p):
        b.choose(p.operation, "Cut")


def r_cut_ok():
    h.task_button("OK")


r_cut_ok.wait_ms = 1500


def r_followed():
    """Known limit (FreeCAD's naming, the same with FreeCAD's own Boolean): the joined top
    face was made by merging two faces; Cut makes the top face another way, so the Press
    Pull loses it. It must say so in the timeline (select the face again), never as an
    error in the Report view or a pop-up; the Combine itself is a Cut now."""
    from sciforge import timeline_ops

    combine = combines()[0]
    h.check("the Combine is a Cut now", combine.Operation == "Cut", combine.Operation)
    h.check("the Combine itself is fine", "Invalid" not in list(combine.State), combine.State)
    found = [o for o in s.bodies()[0].Group if getattr(o, "SciForgeType", "") == "PressPull"]
    if h.check("the Press Pull is still there", len(found) == 1, found):
        kind, why = timeline_ops.problem(found[0])
        h.check("the timeline says why", kind == "error" and "face" in why.lower(), (kind, why))
    h.check("no pop-up", not h.popups(), h.popups())
    h.fit()
    h.shot("R-presspull-after-combine")


def r_undo():
    s.undo()


def r_undone():
    got = s.volume(s.bodies()[0])
    h.check("undo: joined and pulled again", s.close(got, 31500), got)


h.run(
    "bodies_qa_2",
    [s.new_design("QA_Multi")]
    + s.box_steps("multi_body1", (0, 0, 20, 20), 10, V(12, -8, 0))
    + s.box_steps("multi_body2", (40, 0, 60, 20), 10, V(12, -8, 0), new_body=True)
    + [
        i_open,
        i_body1,
        i_body2,
        i_values,
        i_preview,
        i_ok,
        i_done,
        i_edit,
        i_edit_y,
        i_edit_ok,
        i_edited,
        i_pick_body1,
        i_delete_body1,
        i_deleted,
        i_undo,
        i_undone,
        i_edit_extrude,
        i_height,
        i_height_ok,
        i_followed,
    ]
    + [s.new_design("QA_Part")]
    + s.box_steps("part_box", (0, 0, 40, 30), 10, V(12, -8, 0))
    + ps.make_boss("part_boss", (8, 8), 3, 5, V(30, 20, 10))
    + ps.make_cut("part_hole", (20, 15), 5, 10.0)
    + [
        j_open,
        j_body,
        j_up,
        j_ok,
        j_moved,
        j_edit_box,
        j_height,
        j_height_ok,
        j_followed,
        j_split_open,
        j_split_body,
        j_split_boss,
        j_split_preview,
        j_split_ok,
        j_split_done,
        j_undo,
        j_undone,
        p_open,
        p_body,
        p_point_to_point,
        p_round_edge,
        p_centre,
        p_nothing_moved,
    ]
    + [s.new_design("QA_Three")]
    + s.box_steps("three_body1", (0, 0, 40, 30), 10, V(12, -8, 0))
    + s.box_steps("three_body2", (30, 0, 70, 30), 10, V(12, -8, 0), new_body=True)
    + s.box_steps("three_body3", (10, 20, 20, 50), 10, V(12, -8, 0), new_body=True)
    + [
        k_open,
        k_target,
        k_tool2,
        k_tool3,
        k_three,
        k_drop,
        k_dropped,
        k_ok,
        k_done,
        k_edit,
        k_add_back,
        k_added,
        k_added_done,
    ]
    + [s.new_design("QA_Rotate")]
    + s.box_steps("rotate_box", (0, 0, 40, 30), 10, V(12, -8, 0))
    + [
        l_open,
        l_body,
        l_rotate,
        l_edge,
        l_angle,
        l_turned,
        l_ok,
        l_done,
    ]
    + [s.new_design("QA_Reopen")]
    + s.box_steps("reopen_body1", (0, 0, 40, 30), 10, V(12, -8, 0))
    + s.box_steps("reopen_body2", (30, 0, 70, 30), 10, V(12, -8, 0), new_body=True)
    + [
        m_open,
        m_target,
        m_tool,
        m_ok,
        m_save_close,
        m_reopen,
        m_sketch,
        m_pick_xy,
        m_draw,
        m_finish,
        m_extrude,
        m_height,
        m_extrude_ok,
        m_extruded,
        n_pick_used_up_row,
        n_del_key,
        n_deleted,
        n_undo,
        n_undone,
    ]
    + [s.new_design("QA_Plane")]
    + s.box_steps("plane_box", (0, 0, 40, 30), 10, V(12, -8, 0))
    + [
        o_offset_plane,
        o_top_face,
        o_distance,
        o_plane_ok,
        o_plane_made,
        o_split_open,
        o_split_body,
        o_pick_plane,
        o_preview,
        o_done,
        o_undo,
        o_undone,
    ]
    + [s.new_design("QA_FaceLook")]
    + s.box_steps("look_box", (0, 0, 40, 30), 10, V(12, -8, 0))
    + [
        q_open_look,
        q_faces_blue,
        q_click_top,
        q_look_ok,
        q_blue_top,
        q_move,
        q_move_body,
        q_move_values,
        q_move_ok,
        q_moved_blue,
        q_undo,
        q_undone,
    ]
    + [s.new_design("QA_PressPull")]
    + s.box_steps("pp_body1", (0, 0, 40, 30), 10, V(12, -8, 0))
    + s.box_steps("pp_body2", (30, 0, 70, 30), 10, V(12, -8, 0), new_body=True)
    + [
        r_combine,
        r_target,
        r_tool,
        r_combine_ok,
        r_press_q,
        r_top,
        r_distance,
        r_presspull_ok,
        r_pulled,
        r_edit_combine,
        r_cut,
        r_cut_ok,
        r_followed,
        r_undo,
        r_undone,
    ],
)
