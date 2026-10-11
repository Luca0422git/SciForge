# SPDX-License-Identifier: LGPL-2.1-or-later
"""Body tools used the way a Fusion user really uses them (QA pass), only real input.

Two bodies made like Luca makes them: Body1 = 0..40 x 0..30 x 10 (12000), Body2 = 30..70 x
0..30 x 10 (12000, Extrude New Body). They overlap in 30..40 (3000).

  A  Combine, beginner order: OK with nothing picked keeps the dialog open and says why; the
     tool body is clicked first by mistake (it becomes the target), then Body1; fixed by
     clicking the Target Body box and Body1 again (Body1 leaves the tools); Body2 as the tool;
     Cut and back to Join while the preview runs; Enter over the 3D view finishes it.
     Afterwards new work must land in a body that is shown (Create Sketch on XY, E): the
     used-up Body2 must not stay the active body.
  B  Edit Body2's extrude from the timeline (20 high): the Combine follows and Body2 stays
     used up (hidden). Edit the Combine twice from the timeline (Cut, then Keep Tools).
     Undo / Redo.
  C  Split Body: Esc after picking the body leaves nothing behind. Then the body clicked
     first (a face of it), Split Body, the YZ square, Extend toggled while the preview runs,
     OK. Combine the two halves back together (one block, 6 faces). Undo.
  D  Move far and negative: X arrow dragged -60, the Z turn handle dragged, Y Distance typed
     while the preview runs, OK. Edit from the timeline twice. Undo / Redo twice.
  E  Another command's key while a body dialog is open: E during Move/Copy keeps the move
     and opens Extrude; Q during a Combine still waiting for its tool leaves nothing behind;
     M during Split Body. Point to Point chosen before the body: the first click still picks
     the body; Esc after the first point: nothing moves.
  F  A part with every body tool (Combine Cut + Keep Tools, Split Body, Create Copy,
     Appearance, Physical Material), saved, closed and opened again: same bodies, volumes,
     looks and material; the Move, the Split Body and the Combine edited again from the
     timeline (each change flows through the steps after it). Undo.
  G  Delete around a Combine: the used-up tool body (browser, Modify > Delete): the Combine
     keeps its result, and edited (Cut) it still uses the deleted body; the target body: the tool body is free and shown again; the target's
     first extrude: the Combine says why in the timeline, no error in the Report view. Undo
     after each.
  H  Appearance with a face selected first (Apply To Faces), Esc puts the look back;
     Ctrl+Z in the Appearance dialog cancels it; Physical Material: PLA dragged onto the body
     (Fusion's way), then Split Body: the new piece is PLA and looks the same, both halves
     weigh the same.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h

V = App.Vector
state = {}


def body1():
    return s.body_named("Body") or s.body_named("Body1") or s.bodies()[0]


def body2():
    return s.bodies()[1]


def combines():
    return s.steps_of_kind("Combine")


def splits():
    return s.steps_of_kind("SplitBody")


def moves():
    return s.steps_of_kind("MoveCopy")


def active_body():
    from sciforge import bodies

    return bodies.active_body(App.ActiveDocument)


def bbox(body):
    return body.Shape.BoundBox


def box_is(name, box, expect, tol=1e-6):
    got = [box.XMin, box.YMin, box.ZMin, box.XMax, box.YMax, box.ZMax]
    ok = all(abs(a - c) <= tol for a, c in zip(got, expect))
    return h.check(name, ok, (got, expect))


def tooltip():
    return QtWidgets.QToolTip.text() if QtWidgets.QToolTip.isVisible() else ""


def enter_on_view():
    h.press(QtCore.Qt.Key_Return)


def drag_arrow(index, along):
    """Drag arrow `index` of the move manipulator by `along` mm, held on its shaft."""
    p = s.panel()
    triad = getattr(p, "triad", None)
    if not h.check("manipulator shown", triad is not None):
        return
    axis = [V(1, 0, 0), V(0, 1, 0), V(0, 0, 1)][index]
    start = triad.center + axis * (0.75 * triad.size)
    h.drag(h.screen_point(start), h.screen_point(start + axis * along), steps=24)


def drag_turn(index, degrees, step=4.0):
    """Drag the turn handle about axis `index` from its ball round its circle by `degrees`,
    the way a hand follows it."""
    p = s.panel()
    triad = getattr(p, "triad", None)
    if not h.check("manipulator with turn handles", triad is not None and triad.turns):
        return
    u, v = triad._frame(index)
    r = 0.6 * triad.size
    center = V(triad.center)
    count = max(1, int(abs(degrees) / step))
    pixels = []
    for i in range(count + 1):
        a = math.radians(45.0 + degrees * i / count)
        pixels.append(h.screen_point(center + u * (r * math.cos(a)) + v * (r * math.sin(a))))
    widget = h.gl_widget()
    h.move(pixels[0])
    QtTest.QTest.mousePress(widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, pixels[0])
    for pixel in pixels[1:]:
        pos = QtCore.QPointF(pixel)
        event = QtGui.QMouseEvent(
            QtCore.QEvent.MouseMove,
            pos,
            QtCore.QPointF(widget.mapToGlobal(pixel)),
            QtCore.Qt.NoButton,
            QtCore.Qt.LeftButton,
            QtCore.Qt.NoModifier,
        )
        QtWidgets.QApplication.sendEvent(widget, event)
        QtWidgets.QApplication.processEvents()
    QtTest.QTest.mouseRelease(widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, pixels[-1])
    QtWidgets.QApplication.processEvents()


def extrude_of(body):
    found = [
        o
        for o in body.Group
        if o.TypeId in ("PartDesign::Pad", "PartDesign::Pocket")
        or getattr(o, "SciForgeType", "") == "Extrude"
    ]
    return found[0] if found else None


def no_problems(where):
    """No timeline step in error (the Report view is checked after every step anyway)."""
    from sciforge import timeline_ops

    found = []
    for obj, _b in timeline_ops.steps(App.ActiveDocument):
        kind, why = timeline_ops.problem(obj)
        if kind == "error":
            found.append((obj.Label, why))
    h.check("no step in error after %s" % where, not found, found)


# == A: Combine, beginner order =================================================================
def a_open():
    h.click_empty()
    h.fit()
    h.ribbon("Combine")


def a_ok_nothing():
    p = s.panel()
    h.check("Combine open", p is not None and p.title == "Combine", p)
    h.task_button("OK")


def a_still_open():
    p = s.panel()
    h.check("OK with nothing picked: still open", p is not None)
    s.no_popups("OK with nothing picked")
    if p is not None:
        text = (p.message.text() + " " + p.info.text()).lower()
        h.check("says to select the target body", "target" in text, text)
    h.check("nothing built", not combines(), combines())


def a_click_wrong_first():
    h.click(V(60, 15, 10))  # Body2 first (meant as the tool)


def a_click_body1_as_tool():
    p = s.panel()
    if p is not None:
        h.check("first click is the target", p.options["target"] is body2(), p.options)
    h.click(V(10, 15, 10))


def a_wrong_preview():
    p = s.panel()
    if p is not None:
        h.check("Body1 is a tool now", p.options["tools"] == [body1()], p.options)
    h.check("wrong way round: Body2 = 21000", s.close(s.volume(body2()), 21000), s.volume(body2()))
    s.click_box("target")


def a_retarget():
    p = s.panel()
    if p is not None:
        h.check("target box active again", p.active == "target", p.active)
    h.click(V(10, 15, 10))


def a_retargeted():
    p = s.panel()
    if h.check("dialog open", p is not None):
        h.check("Body1 is the target", p.options["target"] is body1(), p.options)
        h.check("Body1 left the tools", body1() not in p.options["tools"], p.options)
        h.check("tool box waits", p.active == "tools", p.active)
    h.check("Body2 back to its own 12000", s.close(s.volume(body2()), 12000), s.volume(body2()))
    h.check("Body1 12000", s.close(s.volume(body1()), 12000), s.volume(body1()))
    h.check("Body1 not see-through any more", body1().ViewObject.Transparency == 0)


def a_click_tool():
    h.click(V(60, 15, 10))


def a_cut_while_preview():
    h.check("join preview 21000", s.close(s.volume(body1()), 21000), s.volume(body1()))
    p = s.panel()
    if p is not None:
        b.choose(p.operation, "Cut")


def a_cut_preview():
    h.check("cut preview 9000", s.close(s.volume(body1()), 9000), s.volume(body1()))
    p = s.panel()
    if p is not None:
        b.choose(p.operation, "Join")


def a_join_again():
    h.check("join again 21000", s.close(s.volume(body1()), 21000), s.volume(body1()))
    h.shot("A-preview")
    enter_on_view()


a_join_again.wait_ms = 1200


def a_done():
    h.check("Enter finished the Combine", s.panel() is None)
    h.check("Body1 = 21000", s.close(s.volume(body1()), 21000), s.volume(body1()))
    h.check("one Combine", len(combines()) == 1, combines())
    h.check("Body2 used up", not s.shown(body2()))
    h.check("Body2 drawn solid again", body2().ViewObject.Transparency == 0)
    active = active_body()
    h.check(
        "the active body is a body that is shown (not the used-up Body2)",
        active is not None and s.shown(active),
        active and active.Label,
    )
    state["a_volume"] = s.total_volume()
    h.shot("A-done")


def a_sketch():
    h.fit()
    h.ribbon("Create Sketch")


def a_pick_xy():
    h.click(V(12, -8, 0))


def a_draw():
    sk = h.in_sketch()
    if h.check("sketch open", sk is not None):
        h.draw_rectangle(sk, 80, 0, 100, 20)


def a_finish():
    h.ribbon("Finish Sketch")


def a_extrude():
    h.fit()
    h.press("e")


def a_height():
    p = b.active_panel()
    field = getattr(getattr(p, "distance", None), "widget", None)
    if h.check("extrude dialog", field is not None):
        s.type_value(field, "10")


def a_extrude_ok():
    h.task_button("OK")


def a_extruded():
    got = s.total_volume()
    h.check(
        "the new extrude is shown (+4000 in shown bodies)",
        s.close(got, state["a_volume"] + 4000),
        (got, state["a_volume"]),
    )
    h.check("Body2 still used up", not s.shown(body2()))
    h.check("Body2 unchanged", s.close(s.volume(body2()), 12000), s.volume(body2()))
    h.shot("A-extruded-after-combine")


def a_undo_extrude():
    s.undo()


def a_undone():
    h.check("undo: extrude gone", s.close(s.total_volume(), state["a_volume"]), s.total_volume())


def a_undo_sketch():
    s.undo()


# == B: edits through the Combine =================================================================
def b_edit_tool_extrude():
    h.fit()
    s.timeline_double_click(extrude_of(body2()))


b_edit_tool_extrude.wait_ms = 1200


def b_height_20():
    p = b.active_panel()
    field = getattr(getattr(p, "distance", None), "widget", None)
    if h.check("extrude edit dialog", field is not None):
        s.type_value(field, "20")


def b_extrude_ok():
    h.task_button("OK")


b_extrude_ok.wait_ms = 1200


def b_followed():
    h.check("dialog closed", s.panel() is None)
    # 40 x 30 x 10 + 40 x 30 x 20 - 10 x 30 x 10
    h.check("Combine follows: Body1 = 33000", s.close(s.volume(body1()), 33000), s.volume(body1()))
    h.check("Body2 is 24000", s.close(s.volume(body2()), 24000), s.volume(body2()))
    h.check("Body2 still used up after editing its extrude", not s.shown(body2()))
    no_problems("editing the tool's extrude")
    h.shot("B-followed")


def b_edit_combine():
    s.timeline_double_click(combines()[0])


def b_cut():
    p = s.panel()
    if h.check("Combine edit open", p is not None and p.editing, p):
        h.check("edit: Body2 drawn while editing", s.shown(body2()))
        b.choose(p.operation, "Cut")


def b_cut_ok():
    h.check("cut preview 9000", s.close(s.volume(body1()), 9000), s.volume(body1()))
    h.task_button("OK")


def b_cut_done():
    h.check("cut 9000", s.close(s.volume(body1()), 9000), s.volume(body1()))
    h.check("Body2 used up again", not s.shown(body2()))


def b_edit_again():
    s.timeline_double_click(combines()[0])


def b_keep():
    p = s.panel()
    if h.check("Combine edit open", p is not None and p.editing, p):
        h.check("edit shows Cut", p.operation.currentText() == "Cut", p.operation.currentText())
        s.toggle(p.keep_tools)


def b_keep_ok():
    h.task_button("OK")


def b_kept():
    h.check("Keep Tools: Body2 shown", s.shown(body2()))
    h.check("still 9000", s.close(s.volume(body1()), 9000), s.volume(body1()))
    h.check("Body2 drawn solid", body2().ViewObject.Transparency == 0)


def b_undo():
    s.undo()


def b_undone():
    h.check("undo: Body2 used up again", not s.shown(body2()))
    h.check("undo: Keep Tools off", not combines()[0].KeepTools)


def b_redo():
    s.redo()


def b_redone():
    h.check("redo: Body2 shown", s.shown(body2()))
    h.check("redo: Keep Tools on", combines()[0].KeepTools)


# == C: Split Body ================================================================================
def c_open():
    h.click_empty()
    h.fit()
    h.ribbon("Split Body")


def c_click_body():
    h.click(V(-10, -5, 10))


def c_escape():
    p = s.panel()
    if p is not None:
        h.check("body taken", p.options["body"] is s.bodies()[0], p.options)
        h.check("squares wait for the tool", p.plane_picker is not None)
        state["picker_root"] = p.plane_picker
    h.press(QtCore.Qt.Key_Escape)


def c_nothing_left():
    h.check("Esc closed Split Body", s.panel() is None)
    h.check("still one body", len(s.bodies()) == 1, [x.Label for x in s.bodies()])
    h.check("no Split Body step", not splits(), splits())
    h.check("12000", s.close(s.volume(s.bodies()[0]), 12000), s.volume(s.bodies()[0]))
    h.check("body shown", s.shown(s.bodies()[0]))
    root = Gui.ActiveDocument.ActiveView.getSceneGraph()
    picker = state.get("picker_root")
    leftover = picker is not None and root.findChild(picker.root) >= 0
    h.check("the big squares are gone", not leftover)
    s.no_popups("Esc in Split Body")


def c_select_first():
    h.fit()
    h.click(V(-10, -5, 10))


def c_open_selected():
    h.ribbon("Split Body")


def c_taken():
    p = s.panel()
    if h.check("Split Body open", p is not None):
        h.check("the clicked face's body is taken", p.options["body"] is s.bodies()[0], p.options)
        h.check("tool box waits", p.active == "tool", p.active)
    h.click(V(0, -24, 20))  # the YZ square, in front of the part


def c_extend_off():
    found = s.bodies()
    h.check("preview: two bodies", len(found) == 2, [x.Label for x in found])
    p = s.panel()
    if p is not None:
        s.toggle(p.extend)


def c_extend_on():
    h.check("plane with Extend off: still two", len(s.bodies()) == 2, len(s.bodies()))
    p = s.panel()
    if p is not None:
        s.toggle(p.extend)


def c_ok():
    p = s.panel()
    if p is not None:
        h.check("Extend on", p.extend.isChecked())
    h.task_button("OK")


def c_split():
    found = s.bodies()
    h.check("two bodies", len(found) == 2, [x.Label for x in found])
    h.check("6000 + 6000", [round(s.volume(x)) for x in found] == [6000, 6000], found)
    h.check("both shown", all(s.shown(x) for x in found))
    h.shot("C-split")


def c_combine_open():
    h.click_empty()
    h.fit()
    h.ribbon("Combine")


def c_combine_target():
    h.click(V(-10, -5, 10))


def c_combine_tool():
    h.click(V(10, -5, 10))


def c_combine_ok():
    h.task_button("OK")


def c_combined():
    first = s.bodies()[0]
    h.check("joined back: 12000", s.close(s.volume(first), 12000), s.volume(first))
    h.check("one block again: 6 faces", len(first.Shape.Faces) == 6, len(first.Shape.Faces))
    h.check("one solid", len(first.Shape.Solids) == 1, len(first.Shape.Solids))
    h.check("the other half used up", not s.shown(s.bodies()[1]))
    no_problems("combining the halves")


def c_undo():
    s.undo()


def c_undone():
    found = s.bodies()
    h.check("undo: halves again", [round(s.volume(x)) for x in found] == [6000, 6000])
    h.check("undo: both shown", all(s.shown(x) for x in found))


# == D: Move far and negative, edited twice ===================================================
def d_open():
    h.click_empty()
    h.fit()
    h.press("m")


def d_body():
    h.click(V(20, 15, 10))


def d_drag_negative():
    p = s.panel()
    if p is not None:
        h.check("body picked", p.options["bodies"] == [s.bodies()[0]], p.options)
    drag_arrow(0, -60)


d_drag_negative.wait_ms = 1200


def d_dragged():
    p = s.panel()
    dx = p.options["dx"] if p is not None else 0
    h.check("dragged about -60 in X", abs(dx + 60) < 4.0, dx)
    box = bbox(s.bodies()[0])
    h.check("the body follows the drag", abs(box.XMin - dx) < 1e-6, (box.XMin, dx))
    state["d_dx"] = dx
    h.shot("D-dragged-negative")


def d_turn():
    drag_turn(2, 30)


d_turn.wait_ms = 1200


def d_turned():
    p = s.panel()
    rz = p.options["rz"] if p is not None else 0
    h.check("turned about Z by about 30", abs(rz - 30) < 6.0, rz)
    h.check("dx kept while turning", abs(p.options["dx"] - state["d_dx"]) < 1e-9, p.options["dx"])
    h.check("still 12000", s.close(s.volume(s.bodies()[0]), 12000), s.volume(s.bodies()[0]))


def d_type_y():
    p = s.panel()
    if p is not None:
        s.type_value(p.distance_fields[1].widget, "-25")
        s.type_value(p.angle_fields[2].widget, "90")


def d_typed():
    p = s.panel()
    if p is None:
        return
    # turned 90 about the middle (20, 15, 5): 30 x 40 footprint centred on it, then shifted
    cx, cy = 20 + p.options["dx"], 15 - 25
    box_is(
        "typed while the preview runs",
        bbox(s.bodies()[0]),
        [cx - 15, cy - 20, 0, cx + 15, cy + 20, 10],
    )
    state["d_dx"] = p.options["dx"]


def d_ok():
    h.task_button("OK")


def d_done():
    h.check("one Move step", len(moves()) == 1, moves())
    h.check("12000", s.close(s.volume(s.bodies()[0]), 12000), s.volume(s.bodies()[0]))
    state["d_box1"] = list(bbox(s.bodies()[0]).Center)


def d_edit():
    s.timeline_double_click(moves()[0])


def d_edit_x():
    p = s.panel()
    if h.check("Move edit open", p is not None and p.editing, p):
        h.check("edit: Y Distance -25", abs(p.options["dy"] + 25) < 1e-9, p.options["dy"])
        h.check("edit: Z Angle 90", abs(p.options["rz"] - 90) < 1e-9, p.options["rz"])
        triad = p.triad
        if h.check("edit: manipulator shown", triad is not None):
            want = V(20 + p.options["dx"], 15 - 25, 5)
            h.check(
                "edit: manipulator at the moved middle",
                (triad.center - want).Length < 1e-6,
                triad.center,
            )
        s.type_value(p.distance_fields[0].widget, "-100")


def d_edit_ok():
    h.task_button("OK")


def d_edited():
    box_is("edited once: X -100", bbox(s.bodies()[0]), [-95, -30, 0, -65, 10, 10])
    h.check("still one Move step", len(moves()) == 1, moves())


def d_edit2():
    s.timeline_double_click(moves()[0])


def d_edit2_angle():
    p = s.panel()
    if h.check("Move edit open again", p is not None and p.editing, p):
        h.check("edit 2: X Distance -100", abs(p.options["dx"] + 100) < 1e-9, p.options["dx"])
        s.type_value(p.angle_fields[2].widget, "0")


def d_edit2_ok():
    h.task_button("OK")


def d_edited2():
    box_is("edited twice: no turn", bbox(s.bodies()[0]), [-100, -25, 0, -60, 5, 10])


def d_undo1():
    s.undo()


def d_undone1():
    box_is("undo: X -100 turned", bbox(s.bodies()[0]), [-95, -30, 0, -65, 10, 10])


def d_undo2():
    s.undo()


def d_undone2():
    c = bbox(s.bodies()[0]).Center
    h.check("undo 2: first move", (c - V(*state["d_box1"])).Length < 1e-6, (c, state["d_box1"]))


def d_redo1():
    s.redo()


def d_redo2():
    s.redo()


def d_redone():
    box_is("redo twice", bbox(s.bodies()[0]), [-100, -25, 0, -60, 5, 10])
    no_problems("moving")


# == E: other keys while a dialog is open =================================================
def e_open_move():
    state["e_moves"] = len(moves())
    h.click_empty()
    h.fit()
    h.press("m")


def e_body():
    h.click(V(-80, -10, 10))


def e_type():
    p = s.panel()
    if h.check("Move open", p is not None):
        h.check("body picked", len(p.options["bodies"]) == 1, p.options)
        s.type_value(p.distance_fields[1].widget, "10")


def e_press_e():
    h.check("preview moved", s.close(bbox(s.bodies()[0]).YMin, -15), bbox(s.bodies()[0]))
    h.fit()
    h.press("e")


e_press_e.wait_ms = 1200


def e_extrude_open():
    p = s.panel()
    h.check("Extrude opened", p is not None and "Extrude" in p.title, p and p.title)
    h.check("the move was kept", len(moves()) == state["e_moves"] + 1, moves())
    h.check("moved 10 in Y", s.close(bbox(s.bodies()[0]).YMin, -15), bbox(s.bodies()[0]))
    s.no_popups("E during Move/Copy")
    h.press(QtCore.Qt.Key_Escape)


def e_combine_open():
    h.check("Extrude closed", s.panel() is None)
    h.click_empty()
    h.ribbon("Combine")


def e_combine_target():
    h.click(V(-80, -5, 10))


def e_press_q():
    p = s.panel()
    if h.check("Combine open", p is not None):
        h.check("target picked", p.options["target"] is not None, p.options)
    state["e_steps"] = len(App.ActiveDocument.Objects)
    h.press("q")


e_press_q.wait_ms = 1200


def e_presspull_open():
    p = s.panel()
    h.check("Press Pull opened", p is not None and p.title != "Combine", p and p.title)
    h.check("no Combine left", not combines(), combines())
    s.no_popups("Q during Combine")
    h.press(QtCore.Qt.Key_Escape)


def e_split_open():
    h.check("Press Pull closed", s.panel() is None)
    h.click_empty()
    h.ribbon("Split Body")


def e_press_m():
    p = s.panel()
    h.check("Split Body open", p is not None and p.title == "Split Body", p)
    state["e_bodies"] = len(s.bodies())
    h.press("m")


e_press_m.wait_ms = 1200


def e_move_open():
    p = s.panel()
    h.check("Move/Copy opened", p is not None and p.title == "Move/Copy", p and p.title)
    h.check("no Split Body made", not splits() and len(s.bodies()) == state["e_bodies"])
    if p is not None:
        b.choose(p.move_type, "Point to Point")


def e_ptp_body():
    p = s.panel()
    if p is not None:
        h.check("Point to Point first: Objects box still waits", p.active == "objects", p.active)
    h.click(V(-80, -5, 10))


def e_ptp_from():
    p = s.panel()
    if p is not None:
        h.check("the click picked the body", len(p.options["bodies"]) == 1, p.options)
        h.check("then the origin point box waits", p.active == "from_point", p.active)
    state["e_box"] = list(bbox(s.bodies()[0]).Center)
    box = bbox(s.bodies()[0])
    h.click(V(box.XMin + 0.6, box.YMin + 0.6, box.ZMax))  # near a corner of the top face


def e_ptp_escape():
    p = s.panel()
    if p is not None:
        h.check("corner taken", p.options["from_point"] is not None, p.options)
        h.check("target point waits", p.active == "to_point", p.active)
    h.press(QtCore.Qt.Key_Escape)


def e_ptp_nothing():
    h.check("Esc closed Move/Copy", s.panel() is None)
    c = bbox(s.bodies()[0]).Center
    h.check("nothing moved", (c - V(*state["e_box"])).Length < 1e-9, c)
    h.check("no extra Move step", len(moves()) == state["e_moves"] + 1, moves())
    no_problems("the key presses")


# == F: save, close, reopen, edit again =========================================================
def look_colors(body):
    try:
        return [
            tuple(round(c, 3) for c in m.DiffuseColor[:3])
            for m in body.Tip.ViewObject.ShapeAppearance
        ]
    except Exception:
        return []


def near_color(a, b, tol=0.01):
    return a is not None and b is not None and all(abs(x - y) <= tol for x, y in zip(a, b))


def click_item(view, item):
    from SciForgeTests.gui import widget_input as w

    view.scrollToItem(item)
    w.click(view.viewport(), view.visualItemRect(item).center())


def f_combine_open():
    h.click_empty()
    h.fit()
    h.ribbon("Combine")


def f_target():
    h.click(V(-10, -5, 10))


def f_tool():
    h.click(V(40, -5, 10))


def f_cut_keep():
    p = s.panel()
    if h.check("Combine open", p is not None):
        b.choose(p.operation, "Cut")
        s.toggle(p.keep_tools)


def f_combine_ok():
    h.task_button("OK")


def f_combined():
    h.check("Body1 cut: 9000", s.close(s.volume(s.bodies()[0]), 9000), s.volume(s.bodies()[0]))
    h.check("Body2 kept", s.shown(s.bodies()[1]))


def f_split_open():
    h.click_empty()
    h.fit()
    h.ribbon("Split Body")


def f_split_body():
    h.click(V(-10, -5, 10))


def f_split_xz():
    h.click(V(-10, 0, 18))  # the XZ square above the part


def f_split_ok():
    found = s.bodies()
    h.check("split preview: three bodies", len(found) == 3, [x.Label for x in found])
    h.task_button("OK")


def f_split_done():
    found = s.bodies()
    vols = [round(s.volume(x)) for x in found]
    h.check("Body1 4500, Body2 12000, piece 4500", vols == [4500, 12000, 4500], vols)


def f_copy_open():
    h.click_empty()
    h.fit()
    h.press("m")


def f_copy_body():
    h.click(V(40, -5, 10))


def f_copy_values():
    p = s.panel()
    if h.check("Move open", p is not None):
        b.choose(p.move_type, "Translate")
        s.type_value(p.distance_fields[0].widget, "60")
        s.toggle(p.copy)


def f_copy_ok():
    h.task_button("OK")


def f_copied():
    found = s.bodies()
    h.check("a copy: four bodies", len(found) == 4, [x.Label for x in found])
    if len(found) == 4:
        box = bbox(found[3])
        h.check("copy 60 to the right", s.close(box.XMin, 70), box)
        h.check("original stays", s.close(bbox(found[1]).XMin, 10), bbox(found[1]))


def f_look_open():
    h.click_empty()
    s.menu("MODIFY", "Appearance")


def f_look_red():
    p = s.panel()
    if h.check("Appearance open", p is not None and p.title == "Appearance", p):
        click_item(p.library, p.item_for("Glossy plastic, red"))


def f_look_click():
    h.click(V(-10, -5, 10))


def f_look_ok():
    h.task_button("OK")


def f_material_open():
    h.click_empty()
    s.menu("MODIFY", "Physical Material")


def f_material_pick():
    p = s.panel()
    if h.check("Physical Material open", p is not None, p):
        click_item(p.library, p.item_for("Aluminium"))


def f_material_click():
    h.click(V(40, -5, 10))


def f_material_ok():
    h.task_button("OK")


def f_save_close():
    import os
    import tempfile

    doc = App.ActiveDocument
    state["f_volumes"] = [round(s.volume(x), 6) for x in s.bodies()]
    state["f_shown"] = [s.shown(x) for x in s.bodies()]
    state["f_labels"] = [x.Label for x in s.bodies()]
    state["f_red"] = look_colors(s.bodies()[0])
    h.check("Body1 red before saving", near_color((state["f_red"] or [None])[0], (0.8, 0.08, 0.08)))
    state["f_path"] = os.path.join(tempfile.mkdtemp(), "bodies_qa_file.FCStd")
    doc.saveAs(state["f_path"])
    App.closeDocument(doc.Name)


def f_reopen():
    App.openDocument(state["f_path"])
    QtWidgets.QApplication.processEvents()


f_reopen.wait_ms = 1500


def f_reopened():
    from sciforge import bodies

    found = s.bodies()
    h.check("same bodies", [x.Label for x in found] == state["f_labels"], [x.Label for x in found])
    vols = [round(s.volume(x), 6) for x in found]
    h.check("same volumes", vols == state["f_volumes"], (vols, state["f_volumes"]))
    h.check("same bodies shown", [s.shown(x) for x in found] == state["f_shown"])
    h.check(
        "Body1 still red",
        near_color((look_colors(found[0]) or [None])[0], (0.8, 0.08, 0.08)),
        look_colors(found[0]),
    )
    h.check("Body2 still aluminium", found[1].ShapeMaterial.Name == "Aluminum-Generic")
    h.check("Body2 mass 32.4 g", s.close(bodies.mass(found[1]), 0.0324), bodies.mass(found[1]))
    no_problems("reopening")
    h.fit()


def f_edit_move():
    s.timeline_double_click(moves()[0])


def f_edit_move_x():
    p = s.panel()
    if h.check("Move edit after reopening", p is not None and p.editing, p):
        h.check("reads Translate", p.move_type.currentText() == "Translate")
        h.check("reads Create Copy", p.copy.isChecked())
        h.check("reads X 60", abs(p.options["dx"] - 60) < 1e-9, p.options["dx"])
        s.type_value(p.distance_fields[0].widget, "80")


def f_edit_move_ok():
    h.task_button("OK")


def f_moved_again():
    found = s.bodies()
    h.check("still four bodies", len(found) == 4, [x.Label for x in found])
    if len(found) == 4:
        h.check("copy now 80 to the right", s.close(bbox(found[3]).XMin, 90), bbox(found[3]))
        # made before Body2 became aluminium: a copy is a body of its own (Fusion)
        h.check("copy keeps its own material", found[3].ShapeMaterial.Name != "Aluminum-Generic")


def f_edit_split():
    s.timeline_double_click(splits()[0])


def f_edit_split_tool():
    p = s.panel()
    if h.check("Split edit after reopening", p is not None and p.editing, p):
        h.check("reads the XZ plane", p.options["tool"] is not None, p.options)
    s.click_box("tool")


def f_edit_split_yz():
    h.click(V(0, -17, 15))  # the YZ square (39 wide: 1.3 x the 30 mm body)


def f_edit_split_ok():
    found = s.bodies()
    vols = sorted(round(s.volume(x)) for x in found)
    h.check("split at x = 0 now: 3000 + 6000", vols == [3000, 6000, 12000, 12000], vols)
    h.task_button("OK")


def f_edit_combine():
    s.timeline_double_click(combines()[0])


def f_edit_combine_join():
    p = s.panel()
    if h.check("Combine edit after reopening", p is not None and p.editing, p):
        h.check("reads Cut", p.operation.currentText() == "Cut")
        h.check("reads Keep Tools", p.keep_tools.isChecked())
        b.choose(p.operation, "Join")


def f_edit_combine_ok():
    h.task_button("OK")


def f_joined():
    found = s.bodies()
    vols = [round(s.volume(x)) for x in found]
    # joined 70 x 30 x 10 = 21000, split at x = 0: 6000 (x < 0) + 15000 (x > 0)
    h.check("join flows through the split", sorted(vols) == [6000, 12000, 12000, 15000], vols)
    no_problems("editing after reopening")


def f_undo():
    s.undo()


def f_undone():
    vols = sorted(round(s.volume(x)) for x in s.bodies())
    h.check("undo: cut again", vols == [3000, 6000, 12000, 12000], vols)


# == G: Delete around a Combine ===================================================================
def g_combine_open():
    h.click_empty()
    h.fit()
    h.ribbon("Combine")


def g_target():
    h.click(V(10, 15, 10))


def g_tool():
    h.click(V(60, 15, 10))


def g_ok():
    h.task_button("OK")


def g_joined():
    h.check("joined 21000", s.close(s.volume(s.bodies()[0]), 21000), s.volume(s.bodies()[0]))
    h.check("Body2 used up", not s.shown(s.bodies()[1]))


def g_pick_tool_row():
    tool = s.bodies()[1]
    tree = s.browser()
    h.check(
        "the used-up Body2 is not in the browser (Fusion)",
        tree is not None and tree.row(tool.Label) is None,
        tree.labels() if tree else None,
    )
    # No longer reachable in the browser: select it as a script would, to check that
    # deleting a used-up tool body still keeps the Combine working.
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(App.ActiveDocument.Name, tool.Name)


def g_delete_tool():
    h.check("Body2 selected", s.selected_names() == [s.bodies()[1].Name], s.selected_names())
    s.menu("MODIFY", "Delete")


g_delete_tool.wait_ms = 1200


def g_tool_deleted():
    found = s.bodies()
    h.check("one body left", len(found) == 1, [x.Label for x in found])
    h.check("the Combine keeps its result: 21000", s.close(s.volume(found[0]), 21000))
    no_problems("deleting a used-up tool body")


def g_edit_frozen():
    s.timeline_double_click(combines()[0])


def g_frozen_shown():
    p = s.panel()
    if h.check("Combine edit open", p is not None and p.editing, p):
        text = p.fields["tools"].button.text()
        h.check("the deleted tool body is listed as kept", "deleted" in text.lower(), text)
        h.check("no hint waiting for a tool", not p.info.text(), p.info.text())
        b.choose(p.operation, "Cut")


def g_frozen_cut():
    h.check("cut with the kept tool: 9000", s.close(s.volume(s.bodies()[0]), 9000))
    h.task_button("OK")


def g_frozen_done():
    h.check("dialog closed", s.panel() is None)
    h.check("cut 9000", s.close(s.volume(s.bodies()[0]), 9000), s.volume(s.bodies()[0]))
    no_problems("editing a Combine whose tool body was deleted")


def g_undo_edit():
    s.undo()


def g_undo_tool():
    h.check("undo: joined again", s.close(s.volume(s.bodies()[0]), 21000))
    s.undo()


def g_tool_back():
    found = s.bodies()
    h.check("undo: two bodies", len(found) == 2, [x.Label for x in found])
    if len(found) == 2:
        h.check("undo: Body2 used up again", not s.shown(found[1]))
        h.check("undo: 21000", s.close(s.volume(found[0]), 21000), s.volume(found[0]))


def g_pick_target_row():
    s.click_browser_row(s.bodies()[0].Label)


def g_delete_target():
    s.menu("MODIFY", "Delete")


g_delete_target.wait_ms = 1200


def g_target_deleted():
    found = s.bodies()
    h.check("only Body2 left", len(found) == 1, [x.Label for x in found])
    if found:
        h.check("Body2 free again: shown", s.shown(found[0]))
        h.check("Body2 12000", s.close(s.volume(found[0]), 12000), s.volume(found[0]))
        from sciforge import bodies

        active = bodies.active_body(App.ActiveDocument)
        h.check("Body2 is where new work goes", active is None or active is found[0], active)
    no_problems("deleting the target body")


def g_undo_target():
    s.undo()


def g_target_back():
    found = s.bodies()
    h.check("undo: two bodies", len(found) == 2, [x.Label for x in found])
    if len(found) == 2:
        h.check("undo: joined 21000", s.close(s.volume(found[0]), 21000), s.volume(found[0]))
        h.check("undo: Body2 used up", not s.shown(found[1]))


def g_pick_first_extrude():
    s.click_timeline(extrude_of(s.bodies()[0]))


def g_delete_first_extrude():
    s.menu("MODIFY", "Delete")


g_delete_first_extrude.wait_ms = 1200


def g_first_extrude_deleted():
    found = s.bodies()
    combine = combines()[0] if combines() else None
    h.check("the Combine is still there", combine is not None)
    if combine is not None:
        kind, why = s.timeline_status(combine)
        h.check("the Combine shows why in the timeline", kind in ("error", "warning"), (kind, why))
    h.check("no pop-up", not h.popups(), h.popups())
    state["g_found"] = [x.Label for x in found]


def g_undo_extrude():
    s.undo()


def g_extrude_back():
    h.check("undo: joined 21000", s.close(s.volume(s.bodies()[0]), 21000))
    no_problems("undoing the delete")


# == H: Appearance and material, the selection first, Esc, Ctrl+Z ==================================
def h_select_top():
    state["h_grey"] = (look_colors(s.bodies()[0]) or [None])[0]
    h.fit()
    h.click(V(-10, -5, 10))


def h_open_look():
    s.menu("MODIFY", "Appearance")


def h_green():
    p = s.panel()
    if h.check("Appearance open", p is not None and p.title == "Appearance", p):
        h.check("Apply To switched to Faces", p.apply_to.currentText() == "Faces")
        click_item(p.library, p.item_for("Glossy plastic, green"))


def h_green_face():
    cols = look_colors(s.bodies()[0])
    green = [c for c in cols if near_color(c, (0.10, 0.55, 0.20))]
    h.check("one face green", len(green) == 1, cols)
    h.press(QtCore.Qt.Key_Escape)


def h_escaped():
    h.check("Esc closed Appearance", s.panel() is None)
    cols = look_colors(s.bodies()[0])
    h.check("Esc: no green face", not [c for c in cols if near_color(c, (0.10, 0.55, 0.20))], cols)
    from sciforge import appearance

    h.check("Esc: nothing stored", not appearance.get(s.bodies()[0])["faces"])
    grey = state.get("h_grey")
    h.check(
        "Esc: the part's usual grey again",
        grey is not None and cols and all(near_color(c, grey) for c in cols),
        (cols, grey),
    )


def h_open_again():
    h.click_empty()
    s.menu("MODIFY", "Appearance")


def h_red():
    p = s.panel()
    if h.check("Appearance open", p is not None):
        click_item(p.library, p.item_for("Glossy plastic, red"))


def h_red_body():
    h.click(V(-10, -5, 10))


def h_ctrl_z():
    cols = look_colors(s.bodies()[0])
    h.check("body red", cols and near_color(cols[0], (0.8, 0.08, 0.08)), cols)
    h.press("z", QtCore.Qt.ControlModifier)


def h_undone():
    h.check("Ctrl+Z closed Appearance", s.panel() is None)
    cols = look_colors(s.bodies()[0])
    h.check("Ctrl+Z: not red", not (cols and near_color(cols[0], (0.8, 0.08, 0.08))), cols)


def h_material():
    h.click_empty()
    s.menu("MODIFY", "Physical Material")


def h_pla():
    """Drag PLA from the library onto the body, as in Fusion (the drop events a drag ends
    with)."""
    from sciforge import material_ui

    p = s.panel()
    if not h.check("Physical Material open", p is not None):
        return
    mime = p.library.mimeData([p.item_for("PLA")])
    h.check("a material drag carries the material", material_ui.key_of(mime) == "pla")
    widget = h.gl_widget()
    pos = h.screen_point(V(-10, -5, 10))
    actions = QtCore.Qt.CopyAction
    enter = QtGui.QDragEnterEvent(pos, actions, mime, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier)
    QtWidgets.QApplication.sendEvent(widget, enter)
    h.check("the 3D view takes the material", enter.isAccepted())
    drop = QtGui.QDropEvent(
        QtCore.QPointF(pos), actions, mime, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier
    )
    QtWidgets.QApplication.sendEvent(widget, drop)
    QtWidgets.QApplication.processEvents()


def h_pla_body():
    found = s.bodies()
    h.check("dropped: the body is PLA", found[0].ShapeMaterial.Name == "PLA-Generic")


def h_pla_ok():
    p = s.panel()
    if p is not None:
        h.check("mass shown", "g" in p.masses.text(), p.masses.text())
    h.task_button("OK")


def h_split_open():
    h.click_empty()
    h.fit()
    h.ribbon("Split Body")


def h_split_body():
    h.click(V(-10, -5, 10))


def h_split_yz():
    h.click(V(0, -24, 20))


def h_split_ok():
    h.task_button("OK")


def h_split_material():
    from sciforge import bodies

    found = s.bodies()
    h.check("two pieces", len(found) == 2, [x.Label for x in found])
    if len(found) == 2:
        h.check("the piece is PLA too", found[1].ShapeMaterial.Name == "PLA-Generic")
        m0, m1 = bodies.mass(found[0]), bodies.mass(found[1])
        h.check("each half weighs the same", m0 and m1 and s.close(m0, m1), (m0, m1))
        h.check(
            "the piece looks like its body",
            look_colors(found[1])[:1] == look_colors(found[0])[:1],
            (look_colors(found[0]), look_colors(found[1])),
        )
    h.shot("H-split-material")


h.run(
    "bodies_qa",
    [s.new_design("QA_Combine")]
    + s.box_steps("body1", (0, 0, 40, 30), 10, V(12, -8, 0))
    + s.box_steps("body2", (30, 0, 70, 30), 10, V(12, -8, 0), new_body=True)
    + [
        a_open,
        a_ok_nothing,
        a_still_open,
        a_click_wrong_first,
        a_click_body1_as_tool,
        a_wrong_preview,
        a_retarget,
        a_retargeted,
        a_click_tool,
        a_cut_while_preview,
        a_cut_preview,
        a_join_again,
        a_done,
        a_sketch,
        a_pick_xy,
        a_draw,
        a_finish,
        a_extrude,
        a_height,
        a_extrude_ok,
        a_extruded,
        a_undo_extrude,
        a_undone,
        a_undo_sketch,
        b_edit_tool_extrude,
        b_height_20,
        b_extrude_ok,
        b_followed,
        b_edit_combine,
        b_cut,
        b_cut_ok,
        b_cut_done,
        b_edit_again,
        b_keep,
        b_keep_ok,
        b_kept,
        b_undo,
        b_undone,
        b_redo,
        b_redone,
    ]
    + [s.new_design("QA_Split")]
    + s.box_steps("split_box", (-20, -15, 20, 15), 10, V(12, -22, 0))
    + [
        c_open,
        c_click_body,
        c_escape,
        c_nothing_left,
        c_select_first,
        c_open_selected,
        c_taken,
        c_extend_off,
        c_extend_on,
        c_ok,
        c_split,
        c_combine_open,
        c_combine_target,
        c_combine_tool,
        c_combine_ok,
        c_combined,
        c_undo,
        c_undone,
    ]
    + [s.new_design("QA_Move")]
    + s.box_steps("move_box", (0, 0, 40, 30), 10, V(12, -8, 0))
    + [
        d_open,
        d_body,
        d_drag_negative,
        d_dragged,
        d_turn,
        d_turned,
        d_type_y,
        d_typed,
        d_ok,
        d_done,
        d_edit,
        d_edit_x,
        d_edit_ok,
        d_edited,
        d_edit2,
        d_edit2_angle,
        d_edit2_ok,
        d_edited2,
        d_undo1,
        d_undone1,
        d_undo2,
        d_undone2,
        d_redo1,
        d_redo2,
        d_redone,
        e_open_move,
        e_body,
        e_type,
        e_press_e,
        e_extrude_open,
        e_combine_open,
        e_combine_target,
        e_press_q,
        e_presspull_open,
        e_split_open,
        e_press_m,
        e_move_open,
        e_ptp_body,
        e_ptp_from,
        e_ptp_escape,
        e_ptp_nothing,
    ]
    + [s.new_design("QA_File")]
    + s.box_steps("file_body1", (-20, -15, 20, 15), 10, V(12, -22, 0))
    + s.box_steps("file_body2", (10, -15, 50, 15), 10, V(5, -24, 0), new_body=True)
    + [
        f_combine_open,
        f_target,
        f_tool,
        f_cut_keep,
        f_combine_ok,
        f_combined,
        f_split_open,
        f_split_body,
        f_split_xz,
        f_split_ok,
        f_split_done,
        f_copy_open,
        f_copy_body,
        f_copy_values,
        f_copy_ok,
        f_copied,
        f_look_open,
        f_look_red,
        f_look_click,
        f_look_ok,
        f_material_open,
        f_material_pick,
        f_material_click,
        f_material_ok,
        f_save_close,
        f_reopen,
        f_reopened,
        f_edit_move,
        f_edit_move_x,
        f_edit_move_ok,
        f_moved_again,
        f_edit_split,
        f_edit_split_tool,
        f_edit_split_yz,
        f_edit_split_ok,
        f_edit_combine,
        f_edit_combine_join,
        f_edit_combine_ok,
        f_joined,
        f_undo,
        f_undone,
    ]
    + [s.new_design("QA_Delete")]
    + s.box_steps("delete_body1", (0, 0, 40, 30), 10, V(12, -8, 0))
    + s.box_steps("delete_body2", (30, 0, 70, 30), 10, V(12, -8, 0), new_body=True)
    + [
        g_combine_open,
        g_target,
        g_tool,
        g_ok,
        g_joined,
        g_pick_tool_row,
        g_delete_tool,
        g_tool_deleted,
        g_edit_frozen,
        g_frozen_shown,
        g_frozen_cut,
        g_frozen_done,
        g_undo_edit,
        g_undo_tool,
        g_tool_back,
        g_pick_target_row,
        g_delete_target,
        g_target_deleted,
        g_undo_target,
        g_target_back,
        g_pick_first_extrude,
        g_delete_first_extrude,
        g_first_extrude_deleted,
        g_undo_extrude,
        g_extrude_back,
    ]
    + [s.new_design("QA_Look")]
    + s.box_steps("look_box", (-20, -15, 20, 15), 10, V(12, -22, 0))
    + [
        h_select_top,
        h_open_look,
        h_green,
        h_green_face,
        h_escaped,
        h_open_again,
        h_red,
        h_red_body,
        h_ctrl_z,
        h_undone,
        h_material,
        h_pla,
        h_pla_body,
        h_pla_ok,
        h_split_open,
        h_split_body,
        h_split_yz,
        h_split_ok,
        h_split_material,
    ],
)
