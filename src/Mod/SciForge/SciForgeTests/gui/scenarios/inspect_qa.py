# SPDX-License-Identifier: LGPL-2.1-or-later
"""CONSTRUCT the way Fusion users really use it (QA), only real input. Each path is what
Fusion does, checked on the design:

  A  beginner: Offset Plane, OK with nothing picked (the dialog stays, says what to click,
     nothing is made), then Esc: the design and its undo list are as before.
  B  Midplane, Esc after the first pick: nothing left behind (no plane, no hidden helper).
  C  Midplane picked "the wrong way round": the XY origin square first, then the top face:
     the plane halfway (z = 5).
  D  Plane at Angle on the front top edge: typed 30, the ball dragged far the other way
     (negative angles), a formula "20 + 25" -> 45, OK.
  E  edited from the timeline twice (60, then 75), Undo / Redo afterwards.
  F  Plane Along Path: the dot dragged far past the end stops at the end (1.0), Physical
     distance longer than the edge is refused in the dialog (OK waits), 12.5 mm is taken.
  G  another command's key while the dialog is open: I (Measure) keeps a finished Offset
     Plane and opens Measure; with nothing picked yet it leaves nothing behind.
  H  Ctrl+Z inside the dialog cancels just the construction; Delete with a face picked
     deletes nothing; Enter finishes.
  I  a part of several features (box + boss): an Offset Plane on the boss's top face, a
     sketch on it extruded down; editing the boss height moves the plane, the sketch and
     its extrude; editing the plane's distance moves the extrude again.
  J  saved, closed, reopened: every construction is still there and editable (Plane at
     Angle edited from the timeline), Undo after reopening.

Part: box 40 x 30 x 10 from the origin. Hand-derived values are in the steps.
"""
import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as di
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import inspect_steps as s
from SciForgeTests.gui import timeline_input as ti

V = App.Vector
st = {}
TOP = V(20, 15, 10)
FRONT_TOP_EDGE = V(20, 0, 10)


def doc():
    return App.ActiveDocument


def helpers():
    from sciforge import construct

    return [o.Name for o in doc().Objects if construct.is_helper(o)]


def snapshot():
    """What must not change when a dialog is cancelled."""
    return {
        "objects": sorted(o.Name for o in doc().Objects),
        "undo": list(doc().UndoNames),
        "volume": h.solid_volume(),
    }


def same_as(before, where):
    now = snapshot()
    h.check(
        "%s: no object added or removed" % where,
        now["objects"] == before["objects"],
        (now["objects"], before["objects"]),
    )
    h.check(
        "%s: the undo list is unchanged" % where,
        now["undo"] == before["undo"],
        (now["undo"], before["undo"]),
    )
    h.check(
        "%s: the part is unchanged" % where, s.close(now["volume"], before["volume"]), now["volume"]
    )


def plane_named(label):
    for o in s.datums("PartDesign::Plane"):
        if o.Label == label:
            return o
    return None


def angle_between(n1, n2):
    a, b2 = V(n1), V(n2)
    a.normalize()
    b2.normalize()
    return math.degrees(math.acos(max(-1.0, min(1.0, abs(a.dot(b2))))))


def measure_panel():
    from sciforge import measure_ui, taskui

    p = taskui.current()
    return p if isinstance(p, measure_ui.MeasurePanel) else None


# -- A: OK with nothing picked ------------------------------------------------------------
def a_start():
    st["a"] = snapshot()
    h.click_empty()
    h.ribbon("Offset Plane")


def a_ok_with_nothing():
    h.task_button("OK")


def a_still_open():
    p = s.construct_panel()
    h.check("OK with nothing picked keeps the dialog open", p is not None)
    if p is None:
        return
    h.check("it says what to click", "flat face" in p.message.text(), p.message.text())
    h.check("nothing made", p.datum is None and not s.datums(), s.datums())
    h.check("no helper made", not helpers(), helpers())
    s.no_popups("OK with nothing picked")
    h.shot("A-ok-nothing")
    s.press_escape()


def a_escaped():
    h.check("Esc closed it", s.construct_panel() is None and not Gui.Control.activeDialog())
    same_as(st["a"], "OK-then-Esc")


# -- L: a drag that ends over the part ----------------------------------------------------
def l_start():
    h.click_empty()
    h.ribbon("Offset Plane")


def l_pick():
    h.fit()
    h.click(TOP)


def l_drag_onto_part():
    """Drag the arrow down and let go over the top face: FreeCAD's selection takes that
    release (it selects the face under the mouse)."""
    p = s.construct_panel()
    if p is None or p.handle is None:
        h.check("Offset Plane with its arrow", False)
        return
    handle = p.handle
    grab = handle.base_point() + handle.direction * (handle.size * 0.55)
    h.drag(s.screen(grab), s.screen(V(30, 8, 10)), steps=16)


def l_let_go():
    p = s.construct_panel()
    if p is None or p.handle is None:
        return
    st["l_value"] = p.values["distance"]
    h.check("the drag changed the distance", abs(st["l_value"] - 10.0) > 0.5, st["l_value"])
    h.check("the arrow is let go", not p.handle.dragging())
    h.move(s.screen(V(5, 25, 10)))  # the mouse moves on, no button down


def l_not_stuck():
    p = s.construct_panel()
    if p is None:
        return
    h.check(
        "moving the mouse afterwards changes nothing (the arrow is not stuck to it)",
        s.close(p.values["distance"], st["l_value"]),
        (p.values["distance"], st["l_value"]),
    )
    h.click(V(20, 0, 5))


def l_front_picked():
    p = s.construct_panel()
    d = p.datum if p else None
    h.check(
        "a click after the drag picks the front face",
        d is not None and s.near(s.normal_of(d), V(0, -1, 0), 1e-6),
        d and s.normal_of(d),
    )
    h.check(
        "the front face, not the XZ origin plane lying in it",
        p is not None and "face" in s.box_value(p, 0),
        p and s.box_value(p, 0),
    )
    s.press_escape()


def l_escaped():
    h.check("Esc closed it", not Gui.Control.activeDialog())
    h.check("nothing kept", not s.datums(), s.datums())


# -- B: Esc in the middle of the picks ------------------------------------------------------
def b_start():
    st["b"] = snapshot()
    s.menu("CONSTRUCT", "Midplane")


def b_first_pick():
    h.fit()
    h.click(TOP)


def b_half_picked():
    p = s.construct_panel()
    h.check("Midplane open", p is not None and p.key == "Midplane")
    if p is None:
        return
    h.check("the face went into Plane 1", "face" in s.box_value(p, 0), s.box_value(p, 0))
    h.check("Plane 2 is the blue box now", p.boxes[1].button.isChecked())
    h.check("no plane yet with one pick", p.datum is None, p.datum)
    s.press_escape()


def b_escaped():
    h.check("Esc closed Midplane", not Gui.Control.activeDialog())
    h.check("no helper left behind", not helpers(), helpers())
    same_as(st["b"], "Esc-after-one-pick")


# -- C: picks the other way round -----------------------------------------------------------
def c_start():
    s.menu("CONSTRUCT", "Midplane")


def c_square_first():
    h.fit()
    pl.click_square("XY_Plane")  # where the XY square shows


def c_square_taken():
    p = s.construct_panel()
    h.check(
        "the XY square went into Plane 1",
        p is not None and "XY" in s.box_value(p, 0),
        s.box_value(p, 0) if p else None,
    )
    h.click(TOP)


def c_preview():
    p = s.construct_panel()
    d = p.datum if p else None
    h.check("the midplane is shown", d is not None)
    if d is None:
        return
    gp = d.getGlobalPlacement()
    h.check("halfway between XY and the top: z = 5", s.close(gp.Base.z, 5.0), gp)
    h.check("parallel to them", s.near(abs(s.normal_of(d).z), 1.0), s.normal_of(d))
    h.task_button("OK")


def c_made():
    plane = plane_named("Plane1")
    h.check("Midplane kept as Plane1", plane is not None, [o.Label for o in s.datums()])
    if plane is not None:
        st["mid"] = plane.Name
        h.check("in the timeline", s.timeline_title_of(plane) is not None, s.timeline_titles())
    h.check("one helper for it", len(helpers()) == 1, helpers())


# -- D: Plane at Angle, typed, dragged far, a formula ---------------------------------------
def d_start():
    h.click_empty()
    s.menu("CONSTRUCT", "Plane at Angle")


def d_edge():
    h.fit()
    h.click_edge(FRONT_TOP_EDGE)


def d_zero():
    p = s.construct_panel()
    d = p.datum if p else None
    h.check("Plane at Angle previews at 0", d is not None and p.key == "PlaneAtAngle")
    if d is None:
        return
    st["n0"] = s.normal_of(d)
    h.check("the plane contains the edge (normal across X)", abs(st["n0"].x) < 1e-9, st["n0"])
    s.type_into(p.angle.widget, "30")


def d_30():
    p = s.construct_panel()
    if p is None or p.datum is None:
        h.check("Plane at Angle still open", False)
        return
    a = angle_between(s.normal_of(p.datum), st["n0"])
    h.check("typed 30: turned 30 degrees about the edge", s.close(a, 30.0, 1e-6), a)
    h.check("the ball follows the typed value", s.close(p.handle.angle(), 30.0), p.handle.angle())


def d_drag_far():
    p = s.construct_panel()
    if p is None or p.handle is None:
        return
    handle = p.handle
    start = s.screen(handle.point_at(handle.angle()))
    end = s.screen(handle.point_at(-100.0))
    h.drag(start, end, steps=24)


def d_dragged():
    p = s.construct_panel()
    if p is None or p.datum is None:
        h.check("still open after the drag", False)
        return
    value = p.values["angle"]
    h.check("dragged far the other way: a negative angle", value < -20, value)
    h.check(
        "the Angle field follows", s.close(p.angle.value(), value, 1e-2), (p.angle.value(), value)
    )
    expected = App.Rotation(p.handle.axis, value).multVec(st["n0"])
    h.check(
        "the plane follows the ball",
        s.near(s.normal_of(p.datum), expected, 1e-6),
        (s.normal_of(p.datum), expected),
    )
    h.shot("D-dragged-far")
    s.type_into(p.angle.widget, "20 + 25")


def d_formula():
    p = s.construct_panel()
    if p is None or p.datum is None:
        h.check("still open after the formula", False)
        return
    h.check("the formula gives 45", s.close(p.values["angle"], 45.0), p.values["angle"])
    a = angle_between(s.normal_of(p.datum), st["n0"])
    h.check("the plane at 45", s.close(a, 45.0, 1e-6), a)
    h.check("no message", not p.message.text(), p.message.text())
    h.task_button("OK")


def d_made():
    plane = plane_named("Plane2")
    h.check("Plane at Angle kept as Plane2", plane is not None, [o.Label for o in s.datums()])
    if plane is None:
        return
    st["angle"] = plane.Name
    a = angle_between(s.normal_of(plane), st["n0"])
    h.check("Plane2 at 45 after OK", s.close(a, 45.0, 1e-6), a)
    h.check("dialog closed", not Gui.Control.activeDialog())


# -- E: edit twice from the timeline, undo / redo ------------------------------------------
def e_edit1():
    s.double_click_timeline(doc().getObject(st["angle"]))


def e_edit1_dialog():
    p = s.construct_panel()
    h.check("double-click opens Plane at Angle", p is not None and p.editing)
    if p is None:
        return
    h.check("with the edge", "edge" in s.box_value(p, 0), s.box_value(p, 0))
    h.check("and 45 (the formula's value)", s.close(p.angle.value(), 45.0), p.angle.value())
    s.type_into(p.angle.widget, "60")


def e_ok1():
    h.task_button("OK")


def e_edit2():
    plane = doc().getObject(st["angle"])
    a = angle_between(s.normal_of(plane), st["n0"])
    h.check("first edit: 60", s.close(a, 60.0, 1e-6), a)
    s.double_click_timeline(plane)


def e_edit2_dialog():
    p = s.construct_panel()
    h.check("opens again", p is not None and p.editing)
    if p is None:
        return
    h.check("shows 60", s.close(p.angle.value(), 60.0), p.angle.value())
    s.type_enter(p.angle.widget, "70 + 5")  # a formula, finished with Enter in the field


def e_ok2():
    h.check("Enter in the field finished the edit", not Gui.Control.activeDialog())


def e_edited():
    plane = doc().getObject(st["angle"])
    a = angle_between(s.normal_of(plane), st["n0"])
    h.check("second edit: 75", s.close(a, 75.0, 1e-6), a)
    h.check("still two planes", len(s.datums("PartDesign::Plane")) == 2, s.datums())
    h.check("still Plane2", plane.Label == "Plane2", plane.Label)
    s.undo()


def e_undone():
    plane = doc().getObject(st["angle"])
    a = angle_between(s.normal_of(plane), st["n0"])
    h.check("Undo: back to 60", s.close(a, 60.0, 1e-6), a)
    s.redo()


def e_redone():
    plane = doc().getObject(st["angle"])
    a = angle_between(s.normal_of(plane), st["n0"])
    h.check("Redo: 75 again", s.close(a, 75.0, 1e-6), a)


def e_hide_planes():
    """Plane2 stands over the top face: hide it with its eye, like a person would."""
    s.eye("Plane2")


# -- F: Plane Along Path ---------------------------------------------------------------------
def f_start():
    h.click_empty()
    s.menu("CONSTRUCT", "Plane Along Path")


def f_edge():
    h.fit()
    h.click_edge(V(30, 0, 10))


def f_preview():
    p = s.construct_panel()
    d = p.datum if p else None
    h.check("Plane Along Path previews", d is not None)
    if d is None:
        return
    gp = d.getGlobalPlacement()
    h.check("halfway along the 40 mm edge", s.near(gp.Base, V(20, 0, 10), 1e-6), gp)
    h.check("a dot to slide", p.handle is not None and p.handle_key == "path")


def f_drag_far():
    p = s.construct_panel()
    if p is None or p.handle is None:
        return
    edge = p.handle.edge
    end_point = edge.valueAt(edge.LastParameter)
    start = s.screen(p.handle.point())
    far = s.screen(end_point + (end_point - p.handle.point()) * 3.0)
    h.drag(start, far, steps=24)


def f_stopped_at_end():
    p = s.construct_panel()
    if p is None or p.datum is None:
        h.check("still open after the drag", False)
        return
    h.check(
        "dragged past the end: stops at 1", s.close(p.fraction.value(), 1.0), p.fraction.value()
    )
    x = p.datum.getGlobalPlacement().Base.x
    h.check("the plane sits on the edge's end", s.close(x, 0.0) or s.close(x, 40.0), x)
    st["end_x"] = x
    h.check("no message", not p.message.text(), p.message.text())
    di.choose(p.path_type, "Physical")


def f_physical():
    p = s.construct_panel()
    if p is None:
        return
    h.check(
        "Physical shows the length so far: 40",
        s.close(p.distance.value(), 40.0),
        p.distance.value(),
    )
    s.type_into(p.distance.widget, "55")


def f_too_long():
    p = s.construct_panel()
    if p is None:
        return
    h.check(
        "55 on a 40 mm edge is refused in the dialog", "40" in p.message.text(), p.message.text()
    )
    h.task_button("OK")


def f_ok_refused():
    p = s.construct_panel()
    h.check("OK waits while the distance is too long", p is not None)
    s.no_popups("too long a distance")
    if p is not None:
        s.type_into(p.distance.widget, "12.5")


def f_12_5():
    p = s.construct_panel()
    if p is None or p.datum is None:
        h.check("Plane Along Path at 12.5", False)
        return
    x = p.datum.getGlobalPlacement().Base.x
    want = 12.5 if s.close(st["end_x"], 40.0) else 27.5
    h.check("12.5 mm from the start of the edge", s.close(x, want), (x, want))
    h.check("the message is gone", not p.message.text(), p.message.text())
    s.press_enter()


def f_made():
    plane = plane_named("Plane3")
    h.check("Plane Along Path kept as Plane3", plane is not None, [o.Label for o in s.datums()])
    if plane is not None:
        st["path"] = plane.Name
    h.check("dialog closed by Enter", not Gui.Control.activeDialog())


# -- G: another command's key while the dialog is open --------------------------------------
def g_start():
    s.eye("Plane3")
    h.click_empty()
    h.ribbon("Offset Plane")


def g_pick():
    h.fit()
    h.click(TOP)


def g_type_below():
    p = s.construct_panel()
    if p is None:
        h.check("Offset Plane open", False)
        return
    s.type_into(p.distance.widget, "-20")


def g_press_i():
    p = s.construct_panel()
    h.check(
        "the plane previews 20 below the top",
        p is not None
        and p.datum is not None
        and s.close(p.datum.getGlobalPlacement().Base.z, -10.0),
    )
    h.press("i")


def g_measure_open():
    h.check("I opened Measure", measure_panel() is not None, Gui.Control.activeDialog())
    plane = plane_named("Plane4")
    h.check(
        "the finished Offset Plane was kept (Plane4)",
        plane is not None,
        [o.Label for o in s.datums()],
    )
    if plane is not None:
        st["below"] = plane.Name
        h.check("at z = -10", s.close(plane.getGlobalPlacement().Base.z, -10.0))
    h.check("no construct dialog left", s.construct_panel() is None)
    s.no_popups("I during Offset Plane")
    s.press_escape()


def g_incomplete_start():
    st["g"] = snapshot()
    h.check("Esc closed Measure", not Gui.Control.activeDialog())
    s.menu("CONSTRUCT", "Midplane")


def g_incomplete_i():
    h.check("Midplane open", s.construct_panel() is not None)
    h.press("i")


def g_incomplete_measure():
    h.check("I opened Measure", measure_panel() is not None)
    h.check("no helper left by the unfinished Midplane", len(helpers()) == 3, helpers())
    same_as(st["g"], "I during an unfinished Midplane")
    s.press_escape()


# -- H: Ctrl+Z and Delete inside the dialog --------------------------------------------------
def h_start():
    st["h"] = snapshot()
    h.click_empty()
    h.ribbon("Offset Plane")


def h_pick():
    h.fit()
    h.click(TOP)


def h_ctrl_z():
    p = s.construct_panel()
    h.check("a preview to undo", p is not None and p.datum is not None)
    ti.ctrl("z")


def h_undone():
    h.check("Ctrl+Z closed the dialog", not Gui.Control.activeDialog())
    same_as(st["h"], "Ctrl+Z in Offset Plane")
    h.check("Plane4 (the step before) is still there", doc().getObject(st["below"]) is not None)


def h_again():
    h.click_empty()
    h.ribbon("Offset Plane")


def h_again_pick():
    h.fit()
    h.click(TOP)


def h_delete_key():
    p = s.construct_panel()
    h.check("the face is picked", p is not None and p.datum is not None)
    st["h2"] = snapshot()
    h.press(QtCore.Qt.Key_Delete)


def h_nothing_deleted():
    p = s.construct_panel()
    h.check("Delete leaves the dialog open", p is not None)
    h.check("Delete removed nothing", s.close(h.solid_volume(), 12000.0), h.solid_volume())
    h.check(
        "the objects are all there", sorted(o.Name for o in doc().Objects) == st["h2"]["objects"]
    )
    s.no_popups("Delete in Offset Plane")
    if p is not None:
        s.type_into(p.distance.widget, "-30")


def h_enter():
    s.press_enter()


def h_made():
    plane = plane_named("Plane5")
    h.check("Enter kept it as Plane5", plane is not None, [o.Label for o in s.datums()])
    if plane is not None:
        h.check("at z = -20", s.close(plane.getGlobalPlacement().Base.z, -20.0))
        st["below2"] = plane.Name


# -- K: Press Pull before and after a construction ------------------------------------------
BOX = 48 * 30 * 10  # the box after the press pull below


def k_press_pull():
    for label in ("Plane1", "Plane4", "Plane5"):
        s.eye(label)
    h.click_empty()
    h.fit()
    h.press("q")


def k_right_face():
    h.fit()
    h.click(V(40, 15, 5))


def k_pull_5():
    from sciforge import presspull_ui

    p = presspull_ui.PressPullPanel.last
    h.check(
        "Press Pull took the right face", p is not None and not p._closed and p.names, p and p.names
    )
    if p is not None:
        s.type_into(p.field.widget, "5")


def k_pull_ok():
    h.task_button("OK")


def k_offset_right():
    v = h.solid_volume()
    h.check("pulled 5: 45 long", s.close(v, 13500.0), v)
    h.click_empty()
    h.ribbon("Offset Plane")


def k_click_right():
    h.fit()
    h.click(V(45, 15, 5))


def k_offset_10():
    p = s.construct_panel()
    d = p.datum if p else None
    h.check("an Offset Plane on the pulled face", d is not None)
    if d is not None:
        x = d.getGlobalPlacement().Base.x
        h.check("10 out of the pulled face: x = 55", s.close(x, 55.0), x)
    h.task_button("OK")


def k_edit_pull():
    plane = plane_named("Plane6")
    h.check("kept as Plane6", plane is not None, [o.Label for o in s.datums()])
    if plane is not None:
        st["right_plane"] = plane.Name
    pulls = [o for o in h.body().Group if "PressPull" in o.Name or "Press" in o.Label]
    h.check("one Press Pull step", len(pulls) == 1, [o.Label for o in h.body().Group])
    if pulls:
        s.double_click_timeline(pulls[0])


def k_pull_8():
    from sciforge import presspull_ui

    p = presspull_ui.PressPullPanel.last
    h.check("Press Pull opens for editing", p is not None and not p._closed and p.editing)
    if p is not None:
        s.type_into(p.field.widget, "8")


def k_pull_edit_ok():
    h.task_button("OK")


def k_plane_followed():
    v = h.solid_volume()
    h.check("pulled 8: 48 long", s.close(v, BOX), v)
    plane = doc().getObject(st.get("right_plane", "")) if st.get("right_plane") else None
    x = plane.getGlobalPlacement().Base.x if plane is not None else None
    h.check("Plane6 followed the edited Press Pull: x = 58", x is not None and s.close(x, 58.0), x)
    h.shot("K-press-pull")
    s.eye("Plane6")


# -- I: a part of several features ----------------------------------------------------------
def i_boss_made():
    feats = [o for o in h.body().Group if o.isDerivedFrom("PartDesign::Feature")]
    st["boss"] = feats[-1].Name if feats else None
    h.check("box, press pull and boss", len(feats) == 3, [o.Name for o in feats])
    v = h.solid_volume()
    h.check("the boss joined the 48 long box", s.close(v, BOX + 250 * math.pi), v)


def i_offset_boss():
    h.click_empty()
    h.ribbon("Offset Plane")


def i_click_boss_top():
    h.fit()
    h.click(V(12, 8, 20))


def i_boss_plane():
    p = s.construct_panel()
    d = p.datum if p else None
    h.check("an Offset Plane on the boss top", d is not None)
    if d is None:
        return
    h.check(
        "10 above the boss top: z = 30",
        s.close(d.getGlobalPlacement().Base.z, 30.0),
        d.getGlobalPlacement(),
    )
    s.type_into(p.distance.widget, "5")


def i_boss_ok():
    h.task_button("OK")


def i_boss_plane_made():
    plane = plane_named("Plane7")
    h.check("kept as Plane7", plane is not None, [o.Label for o in s.datums()])
    if plane is None:
        return
    st["boss_plane"] = plane.Name
    h.check("z = 25", s.close(plane.getGlobalPlacement().Base.z, 25.0))
    s.double_click_timeline(doc().getObject(st["boss"]))


def i_boss_edit():
    from SciForgeTests.gui import blend_steps as bs

    panel = bs.active_panel()
    field = getattr(getattr(panel, "distance", None), "widget", None)
    h.check("the boss extrude opened for editing", field is not None)
    if field is not None:
        s.type_into(field, "15")


def i_boss_edit_ok():
    h.task_button("OK")


def i_plane_followed():
    plane = doc().getObject(st["boss_plane"])
    z = plane.getGlobalPlacement().Base.z
    h.check("the boss is 15 high now: Plane7 moved to z = 30", s.close(z, 30.0), z)
    v = h.solid_volume()
    h.check("box + boss 15 high", s.close(v, BOX + 375 * math.pi), v)
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def i_click_plane7():
    h.click(V(10, 10, 30))


def i_sketch_on_plane7():
    sk = h.in_sketch()
    h.check("a sketch on Plane7", sk is not None)
    if sk is None:
        return
    support = [o.Name for o, _s in sk.AttachmentSupport]
    h.check("attached to Plane7", support == [st["boss_plane"]], support)
    st["sketch"] = sk.Name
    x, y = h.to_sketch(sk, V(10, 10, 30))
    h.draw_circle(sk, x, y, 3)


def i_finish():
    h.ribbon("Finish Sketch")


def i_extrude():
    h.fit()
    h.press("e")


def i_down_10():
    from SciForgeTests.gui import blend_steps as bs

    panel = bs.active_panel()
    field = getattr(getattr(panel, "distance", None), "widget", None)
    h.check("Extrude took the sketch", field is not None)
    if field is not None:
        s.type_into(field, "-10")


def i_extrude_ok():
    h.task_button("OK")


def i_pin_made():
    v = h.solid_volume()
    want = BOX + 375 * math.pi + 45 * math.pi
    h.check("the pin joined the boss (z 25..30 added)", s.close(v, want), (v, want))
    s.double_click_timeline(doc().getObject(st["boss_plane"]))


def i_plane_edit():
    p = s.construct_panel()
    h.check("Plane7 opens for editing", p is not None and p.editing)
    if p is None:
        return
    h.check("with its 5 mm", s.close(p.distance.value(), 5.0), p.distance.value())
    s.type_into(p.distance.widget, "10")


def i_plane_edit_ok():
    h.task_button("OK")


def i_pin_followed():
    plane = doc().getObject(st["boss_plane"])
    h.check("Plane7 at z = 35", s.close(plane.getGlobalPlacement().Base.z, 35.0))
    sk = doc().getObject(st["sketch"])
    h.check(
        "its sketch moved with it",
        s.close(sk.getGlobalPlacement().Base.z, 35.0),
        sk.getGlobalPlacement(),
    )
    v = h.solid_volume()
    want = BOX + 375 * math.pi + 90 * math.pi
    h.check("the pin follows: z 25..35 added", s.close(v, want), (v, want))
    h.shot("I-pin-followed")


# -- J: save, close, reopen, edit -------------------------------------------------------------
def j_save():
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge_inspect_qa_"), "inspect_qa.FCStd")
    st["path"] = path
    st["before_save"] = {o.Name: V(o.getGlobalPlacement().Base) for o in s.datums()}
    st["volume"] = h.solid_volume()
    doc().saveAs(path)


def j_close():
    App.closeDocument(doc().Name)


def j_reopen():
    h.check("the design is closed", App.ActiveDocument is None or not Gui.Control.activeDialog())
    App.openDocument(st["path"])


def j_reopened():
    h.fit()
    for name, base in st["before_save"].items():
        obj = doc().getObject(name)
        h.check("%s is back" % name, obj is not None)
        if obj is not None:
            h.check(
                "%s where it was" % name,
                s.near(obj.getGlobalPlacement().Base, base, 1e-6),
                (obj.getGlobalPlacement().Base, base),
            )
    h.check("the part is the same", s.close(h.solid_volume(), st["volume"]), h.solid_volume())
    h.check(
        "the helpers are not timeline steps",
        all(t and "frame" not in t for t in s.timeline_titles()),
        s.timeline_titles(),
    )
    s.double_click_timeline(doc().getObject(st["angle"]))


def j_edit_dialog():
    p = s.construct_panel()
    h.check("Plane at Angle opens after reopening", p is not None and p.editing)
    if p is None:
        return
    h.check("with its edge", "edge" in s.box_value(p, 0), s.box_value(p, 0))
    h.check("and 75", s.close(p.angle.value(), 75.0), p.angle.value())
    s.type_into(p.angle.widget, "30")


def j_edit_ok():
    h.task_button("OK")


def j_edited():
    plane = doc().getObject(st["angle"])
    a = angle_between(s.normal_of(plane), st["n0"])
    h.check("edited after reopening: 30", s.close(a, 30.0, 1e-6), a)
    s.undo()


def j_undone():
    plane = doc().getObject(st["angle"])
    a = angle_between(s.normal_of(plane), st["n0"])
    h.check("Undo after reopening: 75 again", s.close(a, 75.0, 1e-6), a)
    s.double_click_timeline(doc().getObject(st["boss_plane"]))


def j_offset_dialog():
    p = s.construct_panel()
    h.check("Plane7 opens after reopening", p is not None and p.editing)
    if p is None:
        return
    h.check("with its 10 mm", s.close(p.distance.value(), 10.0), p.distance.value())
    st["j"] = snapshot()
    s.type_into(p.distance.widget, "2")


def j_offset_esc():
    p = s.construct_panel()
    if p is not None:
        z = p.datum.getGlobalPlacement().Base.z
        h.check("the preview moved to z = 27", s.close(z, 27.0), z)
    s.press_escape()


def j_offset_unchanged():
    plane = doc().getObject(st["boss_plane"])
    h.check("Esc: Plane7 back at z = 35", s.close(plane.getGlobalPlacement().Base.z, 35.0))
    v = h.solid_volume()
    h.check("Esc: the pin as it was", s.close(v, st["volume"]), v)


def the_end():
    s.no_popups("the end")
    h.shot("end")


STEPS = (
    b.box_steps("InspectQA")
    + [a_start, a_ok_with_nothing, a_still_open, a_escaped]
    + [l_start, l_pick, l_drag_onto_part, l_let_go, l_not_stuck, l_front_picked]
    + [l_escaped]
    + [b_start, b_first_pick, b_half_picked, b_escaped]
    + [c_start, c_square_first, c_square_taken, c_preview, c_made]
    + [d_start, d_edge, d_zero, d_30, d_drag_far, d_dragged, d_formula, d_made]
    + [e_edit1, e_edit1_dialog, e_ok1, e_edit2, e_edit2_dialog, e_ok2, e_edited]
    + [e_undone, e_redone, e_hide_planes]
    + [f_start, f_edge, f_preview, f_drag_far, f_stopped_at_end, f_physical, f_too_long]
    + [f_ok_refused, f_12_5, f_made]
    + [g_start, g_pick, g_type_below, g_press_i, g_measure_open]
    + [g_incomplete_start, g_incomplete_i, g_incomplete_measure]
    + [h_start, h_pick, h_ctrl_z, h_undone, h_again, h_again_pick, h_delete_key]
    + [h_nothing_deleted, h_enter, h_made]
    + [k_press_pull, k_right_face, k_pull_5, k_pull_ok, k_offset_right, k_click_right]
    + [k_offset_10, k_edit_pull, k_pull_8, k_pull_edit_ok, k_plane_followed]
    + s.boss_steps(BOX)
    + [i_boss_made, i_offset_boss, i_click_boss_top, i_boss_plane, i_boss_ok]
    + [i_boss_plane_made, i_boss_edit, i_boss_edit_ok, i_plane_followed, i_click_plane7]
    + [i_sketch_on_plane7, i_finish, i_extrude, i_down_10, i_extrude_ok, i_pin_made]
    + [i_plane_edit, i_plane_edit_ok, i_pin_followed]
    + [j_save, j_close, j_reopen, j_reopened, j_edit_dialog, j_edit_ok, j_edited, j_undone]
    + [j_offset_dialog, j_offset_esc, j_offset_unchanged, the_end]
)

h.run("inspect_qa", ti.watched(STEPS))
