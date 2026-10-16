# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sketch areas on and in front of the part, with real input (Luca: "when i create a sketch
on an item ... I want to be able to select a specific part of the sketch").

A sketch drawn ON the box's top face, two rectangles A and B, Finish Sketch. Fusion,
with no command running:
- B lights up under the mouse and a click selects B (FreeCAD gave the click to the top
  face under it, so E extruded the whole face: 24000 instead of 14400);
- E then extrudes only B, also from the top view; Ctrl+click A adds A; Q on B is an
  Extrude of B; Del on B deletes nothing and says why (an area goes with its curves);
- the top face outside the areas is still the face (Q pulls it), and a sketch curve on
  the face can still be clicked.

Commands that cannot use sketch areas click through them (sketch_area_pick.py):
- Shell and Create Sketch inside B, on the face: the top face;
- a finished sketch 20 mm ABOVE the box (a loft's next profile): Shell, Hole, Create
  Sketch and Offset Plane on the top face seen through its area take the face (Shell
  picked nothing, Hole placed nothing, Create Sketch opened on the XY origin plane behind
  the part);
- Extrude's To Object box: the top face through the area (it said "Pick a face...").

Box 40 x 30 x 10 = 12000 mm^3. A = x 4..16, B = x 24..36, both y 5..25: 240 mm^2 each.
B extruded 10 mm on top: 14400; A and B: 16800."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import arrow_input as arrows
from SciForgeTests.gui import blend_steps as bs
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import hole_steps as hs
from SciForgeTests.gui import shell_draft_steps as sd

V = App.Vector
CTRL = QtCore.Qt.ControlModifier
Z = 10.0  # the top face
A, B = V(10, 15, Z), V(30, 15, Z)  # the middles of the two areas
BETWEEN = V(20, 15, Z)  # on the top face, outside both areas
s = {}


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def selection():
    return [(x.ObjectName, list(x.SubElementNames)) for x in Gui.Selection.getSelectionEx()]


def preselected():
    """(object, element) lit up under the mouse ("Body", "Sketch001.InternalFace2" ->
    ("Sketch001", "InternalFace2"))."""
    pre = Gui.Selection.getPreselection()
    for sub in pre.SubElementNames:
        if sub:
            parts = sub.split(".")
            return (parts[-2] if len(parts) > 1 else pre.ObjectName, parts[-1])
    return (pre.ObjectName or None, None)


def area_name(point, sketch):
    """ "InternalFaceN" of a finished sketch's area around a global point."""
    from sciforge import profile_pick

    shape = sketch.InternalShape
    if shape.isNull():
        return None
    placement = sketch.getGlobalPlacement()
    for i, face in enumerate(shape.Faces, start=1):
        face = face.copy()
        face.Placement = placement.multiply(face.Placement)
        if profile_pick.inside(face, point):
            return "InternalFace%d" % i
    return None


def extrude_panel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return p if p is not None and not p._closed and Gui.Control.activeDialog() else None


def profiles():
    p = extrude_panel()
    return sorted((o.Name, sub) for o, sub in (p.profiles if p else []))


def top_face():
    """(feature, "FaceN") of the box's top face."""
    tip = h.body().Tip
    for i, face in enumerate(tip.Shape.Faces, start=1):
        if abs(face.CenterOfMass.z - Z) < 1e-6 and abs(face.normalAt(0, 0).z - 1) < 1e-6:
            return (tip.Name, "Face%d" % i)
    return None


def front_state(sketch):
    """(shift, areas clickable) of SciForge's nodes in the sketch's display."""
    from sciforge import sketch_area_pick

    entry = sketch_area_pick._state["nodes"].get((sketch.Document.Name, sketch.Name))
    if not entry or entry == sketch_area_pick._SKIP:
        return None
    pick = entry.pick
    return (entry.front.translation.getValue()[2], pick is None or pick.style.isIgnored())


def cancel():
    h.task_button("Cancel")


# -- Luca's case: a sketch on the top face ----------------------------------------------
def sketch_on_top():
    h.check("the box is there", near(h.solid_volume(), 12000.0), h.solid_volume())
    # Preferences > Design > Auto project off (as in Fusion's default): this scenario is
    # about the face outside the drawn areas; with the face's edges projected that is a
    # profile too (scenario sketch_projected_profiles)
    App.ParamGet("User parameter:BaseApp/Preferences/Mod/SciForge/SketchInference").SetBool(
        "AutoProject", False
    )
    h.ribbon("Create Sketch")


def click_top():
    h.click(V(36, 27, Z))


def draw():
    sk = h.in_sketch()
    h.check("sketch open on the top face", sk is not None and "Face" in str(sk.AttachmentSupport))
    if sk is None:
        return
    s["sk"] = sk
    for p0, p1 in ((V(4, 5, Z), V(16, 25, Z)), (V(24, 5, Z), V(36, 25, Z))):
        a, b = h.to_sketch(sk, p0), h.to_sketch(sk, p1)
        h.draw_rectangle(sk, min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))


def finish():
    h.ribbon("Finish Sketch")


def finished():
    sk = s["sk"]
    h.check("left the sketch", h.in_sketch() is None)
    faces = 0 if sk.InternalShape.isNull() else len(sk.InternalShape.Faces)
    h.check("the finished sketch stays visible with its two areas",
            sk.ViewObject.Visibility and faces == 2, (sk.ViewObject.Visibility, faces))
    s["A"], s["B"] = area_name(A, sk), area_name(B, sk)
    h.check("A and B are two areas", s["A"] and s["B"] and s["A"] != s["B"], (s["A"], s["B"]))
    s["top"] = top_face()
    h.fit()
    Gui.Selection.clearSelection()
    import time

    from sciforge import sketch_area_pick

    start = time.perf_counter()
    for _i in range(200):
        sketch_area_pick.update()  # (runs before every mouse move)
    print("[SciForge] sketch_areas_face: update() takes %.3f ms (2 sketches)"
          % ((time.perf_counter() - start) * 1000.0 / 200), flush=True)
    h.move(h.screen_point(B + V(3, 3, 0)))
    h.move(h.screen_point(B))


def hover_b():
    h.check("B (on the face) lights up under the mouse, not the face",
            preselected() == (s["sk"].Name, s["B"]), preselected())
    state = front_state(s["sk"])
    h.check("no command: the sketch is a hair in front of the face, its areas clickable",
            state is not None and 0 < state[0] < 0.1 and state[1], state)
    h.click(B)


def clicked_b():
    h.check("a click inside B selects B, not the top face",
            selection() == [(s["sk"].Name, [s["B"]])], selection())
    h.shot("1-b-on-face")
    h.press("e")


def e_takes_b():
    h.check("E opens Extrude", extrude_panel() is not None)
    h.check("E extrudes only B", profiles() == [(s["sk"].Name, s["B"])], profiles())
    arrows.give_distance("10")  # Extrude starts at 0 (Fusion): type the distance
    h.check("box + B 10 mm: 14400 (not the whole face: 24000)",
            near(h.solid_volume(), 14400.0), h.solid_volume())
    h.shot("2-e-b")
    h.move(h.screen_point(B + V(1, 1, 0)))  # (the nodes follow the mouse)
    state = front_state(s["sk"])
    h.check("in Extrude (it picks areas itself): no shift, areas clickable",
            state == (0.0, True), state)
    cancel()


def top_view():
    h.check("Cancel: back to the box", near(h.solid_volume(), 12000.0), h.solid_volume())
    Gui.Selection.clearSelection()
    h.view().viewTop()
    h.view().fitAll()
    h.click(B)


def top_view_b():
    h.check("top view: a click inside B selects B",
            selection() == [(s["sk"].Name, [s["B"]])], selection())
    h.click(A, CTRL)


def ctrl_a():
    names = sorted(sum((subs for _o, subs in selection()), []))
    h.check("Ctrl+click adds A", names == sorted([s["A"], s["B"]]), selection())
    h.press("e")


def e_takes_both():
    h.check("E extrudes A and B",
            profiles() == sorted([(s["sk"].Name, s["A"]), (s["sk"].Name, s["B"])]), profiles())
    arrows.give_distance("10")  # Extrude starts at 0 (Fusion): type the distance
    h.check("box + A + B: 16800", near(h.solid_volume(), 16800.0), h.solid_volume())
    cancel()


def delete_b():
    h.fit()
    Gui.Selection.clearSelection()
    h.click(B)
    s["curves"] = s["sk"].GeometryCount
    h.press(QtCore.Qt.Key_Delete)


def b_not_deleted():
    from SciForgeTests.gui import sketch_input as si

    told = si.tooltip()
    h.check("Del on area B deletes nothing (an area goes with its curves)",
            App.ActiveDocument.getObject(s["sk"].Name) is not None
            and s["sk"].GeometryCount == s["curves"], s["sk"].GeometryCount)
    h.check("... and says why", "sketch area" in told, told)


def b_for_q():
    h.fit()
    Gui.Selection.clearSelection()
    h.click(B)
    s["before_q"] = extrude_panel()


def press_q():
    h.check("B selected for Q", selection() == [(s["sk"].Name, [s["B"]])], selection())
    h.press("q")


def q_on_b():
    h.check("Q on area B opens Extrude of B", profiles() == [(s["sk"].Name, s["B"])], profiles())
    arrows.give_distance("10")  # Extrude starts at 0 (Fusion): type the distance
    h.check("box + B: 14400", near(h.solid_volume(), 14400.0), h.solid_volume())
    cancel()


def click_between():
    Gui.Selection.clearSelection()
    h.click(BETWEEN)


def face_between():
    h.check("outside the areas, a click still selects the top face",
            selection() == [(s["top"][0], [s["top"][1]])], (selection(), s["top"]))
    h.press("q")


def q_pulls_face():
    from sciforge import presspull_ui

    p = presspull_ui.PressPullPanel.last
    ok = p is not None and not p._closed and p.mode == "faces"
    h.check("Q on the top face is a Press Pull of the face", ok, p and (p.mode, p.names))
    cancel()


def click_curve():
    Gui.Selection.clearSelection()
    h.click_edge(V(24, 15, Z))  # B's left line, on the top face


def curve_selected():
    sel = selection()
    ok = len(sel) == 1 and sel[0][0] == s["sk"].Name and sel[0][1][0].startswith("Edge")
    h.check("a sketch line lying on the face can still be clicked", ok, sel)
    Gui.Selection.clearSelection()


# -- commands click through the areas on the face -----------------------------------------
def shell_on_face():
    h.fit()
    h.ribbon("Shell")


def shell_click_b():
    h.click(B)


def shell_took_face():
    p = sd.shell_panel()
    h.check("Shell: a click inside B (on the face) picks the top face",
            p is not None and p.picked == [s["top"][1]], p and p.picked)
    state = front_state(s["sk"])
    h.check("in Shell: no shift, the areas let clicks through", state == (0.0, False), state)
    if p is not None:
        cancel()


def sketch_through_b():
    Gui.Selection.clearSelection()
    h.fit()
    h.ribbon("Create Sketch")


def sketch_click_b():
    h.click(B)


def sketch_on_face_through_b():
    sk = h.in_sketch()
    sup = support(sk) if sk is not None else None
    h.check("Create Sketch inside B goes on the top face",
            sk is not None and sk is not s["sk"] and sup == [s["top"]], sup)
    s["sk_b"] = sk
    if sk is not None:
        h.ribbon("Finish Sketch")


def idle_again():
    if s.get("sk_b") is not None:
        App.ActiveDocument.removeObject(s["sk_b"].Name)  # (an empty sketch; not the test)
        App.ActiveDocument.recompute()
    Gui.Selection.clearSelection()
    h.fit()
    h.click(B)


def idle_b_again():
    h.check("after the commands, a click inside B selects B again",
            selection() == [(s["sk"].Name, [s["B"]])], selection())
    Gui.Selection.clearSelection()


# -- a finished sketch 20 mm above the box -----------------------------------------------
def sketch_above():
    from sciforge import sketch_ui

    s["sk"].ViewObject.Visibility = False  # (only the sketch above now)
    body = h.body()
    planes = sketch_ui.origin_planes(body)
    sk = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    sk.AttachmentOffset = App.Placement(V(0, 0, 20), App.Rotation())
    h.draw_rectangle(sk, -10, -10, 50, 40)
    App.ActiveDocument.recompute()
    sk.ViewObject.Visibility = True
    s["above"] = sk
    s["above_area"] = area_name(V(20, 15, 20), sk)
    h.check("the sketch above has its area", s["above_area"] is not None, s["above_area"])
    h.fit()
    h.move(h.screen_point(BETWEEN + V(2, 2, 0)))
    h.move(h.screen_point(BETWEEN))


def above_idle_hover():
    h.check("no command: the area in front lights up (it is nearer than the face)",
            preselected() == (s["above"].Name, s["above_area"]), preselected())
    h.ribbon("Shell")


def above_shell_click():
    h.click(BETWEEN)


def above_shell():
    p = sd.shell_panel()
    h.check("Shell: the top face, seen through a sketch area above it, is picked",
            p is not None and p.picked == [s["top"][1]], p and p.picked)
    if p is not None:
        cancel()


def above_hole():
    Gui.Selection.clearSelection()
    h.fit()
    h.ribbon("Hole")


def above_hole_click():
    h.click(BETWEEN)


def above_hole_placed():
    p = hs.hole_panel()
    h.check("Hole: clicking the top face through the area above places a hole",
            p is not None and getattr(p, "target", None) is not None,
            p and (p.placement.currentData(), p.message.text()))
    if p is not None:
        cancel()


def above_sketch():
    Gui.Selection.clearSelection()
    h.fit()
    h.ribbon("Create Sketch")


def above_sketch_click():
    h.click(BETWEEN)


def support(sketch):
    """[(object name, element)] a sketch is attached to."""
    found = []
    for obj, subs in sketch.AttachmentSupport:
        for sub in (subs if isinstance(subs, (list, tuple)) else [subs]) or [""]:
            found.append((obj.Name, sub))
    return found


def above_sketch_on_face():
    sk = h.in_sketch()
    sup = support(sk) if sk is not None else None
    h.check("Create Sketch: the top face through the area above (not the XY plane behind)",
            sk is not None and sup == [s["top"]], sup)
    s["sk_c"] = sk
    if sk is not None:
        h.ribbon("Finish Sketch")


def above_offset_plane():
    if s.get("sk_c") is not None:
        App.ActiveDocument.removeObject(s["sk_c"].Name)  # (an empty sketch; not the test)
        App.ActiveDocument.recompute()
        s["sk_c"] = None
    Gui.Selection.clearSelection()
    h.click_empty()
    h.ribbon("Offset Plane")


def above_offset_click():
    h.fit()
    h.click(BETWEEN)


def above_offset_from_face():
    from SciForgeTests.gui import inspect_steps as ins

    p = ins.construct_panel()
    d = p.datum if p is not None else None
    z = d.getGlobalPlacement().Base.z if d is not None else None
    h.check("Offset Plane: from the top face through the area above (10 above it: z = 20)",
            z is not None and abs(z - 20.0) < 1e-6, (z, p and p.message.text()))
    if p is not None:
        cancel()


def side_sketch():
    """A small square beside the box, 5 mm below XY (x 40..50, y 0..10, against its side),
    seen directly: its extrude is the one sent To Object. (Its first 10 mm reach z = 5,
    so the preview's top does not merge with the box's top face.)"""
    from sciforge import sketch_ui

    body = h.body()
    planes = sketch_ui.origin_planes(body)
    sk = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    sk.AttachmentOffset = App.Placement(V(0, 0, -5), App.Rotation())
    h.draw_rectangle(sk, 40, 0, 50, 10)
    App.ActiveDocument.recompute()
    sk.ViewObject.Visibility = True
    s["side"] = sk
    s["side_area"] = area_name(V(45, 5, -5), sk)
    Gui.Selection.clearSelection()
    h.fit()
    h.click(V(45, 5, -5))


def side_e():
    h.check("the square beside the box is selected",
            selection() == [(s["side"].Name, [s["side_area"]])], selection())
    h.press("e")


def side_to_object():
    p = extrude_panel()
    h.check("E on the square", profiles() == [(s["side"].Name, s["side_area"])], profiles())
    if p is None:
        return
    h.check("choose Extent: To Object", ui.choose(p.extent, "To Object"))
    h.check("the Object box takes the next click", p.active == "extent_object", p.active)


def side_to_object_click():
    h.click(BETWEEN)  # the top face, seen through the area above


def side_to_top_face():
    p = extrude_panel()
    ref = p.options.get("extent_object") if p is not None else None
    got = (ref[0].Name, ref[1]) if ref else None
    h.check("To Object: the top face through the area above (not 'Pick a face')",
            got == s["top"], (got, p and p.message.text()))
    h.check("the square goes up to the top face: 12000 + 10 x 10 x 15",
            near(h.solid_volume(), 13500.0), h.solid_volume())
    h.shot("3-to-object-through-area")
    if p is not None:
        cancel()


steps = bs.box_steps("AreasOnFace") + [
    sketch_on_top,
    click_top,
    draw,
    finish,
    finished,
    hover_b,
    clicked_b,
    e_takes_b,
    top_view,
    top_view_b,
    ctrl_a,
    e_takes_both,
    delete_b,
    b_not_deleted,
    b_for_q,
    press_q,
    q_on_b,
    click_between,
    face_between,
    q_pulls_face,
    click_curve,
    curve_selected,
    shell_on_face,
    shell_click_b,
    shell_took_face,
    sketch_through_b,
    sketch_click_b,
    sketch_on_face_through_b,
    idle_again,
    idle_b_again,
    sketch_above,
    above_idle_hover,
    above_shell_click,
    above_shell,
    above_hole,
    above_hole_click,
    above_hole_placed,
    above_sketch,
    above_sketch_click,
    above_sketch_on_face,
    above_offset_plane,
    above_offset_click,
    above_offset_from_face,
    side_sketch,
    side_e,
    side_to_object,
    side_to_object_click,
    side_to_top_face,
]
h.run("sketch_areas_face", steps)
