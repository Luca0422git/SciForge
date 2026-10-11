# SPDX-License-Identifier: LGPL-2.1-or-later
"""CONSTRUCT the way a Fusion user really uses it, third QA round (only real input). Each path
is what Fusion does, checked on the design:

  A  A parameter in the distance: "gap" (15 mm, made in Change Parameters) typed into Offset
     Plane on the top face, one Enter: finished at once, the plane at z = 25 and following
     the parameter (gap = 20: z = 30). Edited from the timeline: the dialog says the distance
     follows "gap"; OK keeps it (gap = 5: z = 15).
  B  The arrow dragged twice (up, letting go in the air; then down, letting go over the part:
     -4, the plane inside the part at z = 6), then the box clicked and the front face picked
     instead: the plane moves to the front face with the same -4 (y = 4). OK. Edited from
     the timeline, the arrow dragged, Cancel: unchanged, nothing added to the undo list.
  C  An Offset Plane of an Offset Plane (10 above the top face, then 5 above that: z = 25).
     The first one deleted from the timeline: the second stays at z = 25 with a warning and
     no error. Edited from the timeline it waits for a new pick: the top face, so z = 15, the
     warning goes. Undo: lost again (z = 25, warning); Redo: z = 15.
  G  Two faces selected before the command (top, Ctrl+front), then Midplane: both taken, the
     plane halves the right angle along their shared edge, through the part (normal
     (0, 1, 1) / sqrt 2, like the top / right Midplane of inspect_construct_planes). OK.
  H  Plane at Angle on the origin's Z axis clicked where it is drawn above the part: 0 deg is
     the XZ plane; 45 typed + Enter: the plane turns 45 deg about Z.
  M  That plane selected in the browser and deleted with the Delete key: the plane and its
     hidden helper go, no error; Undo brings both back and it edits as before (Z axis, 45).
  F  A typo in a formula ("gap +", Enter): the dialog stays open and says so, OK too (Fusion
     does not take a value it cannot read); "gap * 3" + Enter: z = 10 + 15 = 25. Section
     Analysis on the top face with "-gap" typed: the cut at z = 5 (6000 stays).

Part: box 40 x 30 x 10 from the origin (real input). Hand-derived values are in the steps.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import inspect_steps as s
from SciForgeTests.gui import timeline_input as ti
from SciForgeTests.gui import widget_input as w

V = App.Vector
st = {}
TOP = V(20, 15, 10)
FRONT = V(30, 0, 5)


def doc():
    return App.ActiveDocument


def obj(key):
    return doc().getObject(st[key]) if st.get(key) else None


def helpers():
    from sciforge import construct

    return [o.Name for o in doc().Objects if construct.is_helper(o)]


def plane_named(label):
    for o in s.datums():
        if o.Label == label:
            return o
    return None


def base_of(o):
    return o.getGlobalPlacement().Base


def formula(o):
    from sciforge import construct

    helper = construct.helper_of(o)
    if helper is not None:
        return construct.formula_of(helper, "Distance") or construct.formula_of(helper, "Angle")
    return construct.formula_of(o, ".AttachmentOffset.Base.z")


def status(o):
    title = s.timeline_title_of(o) if o is not None else None
    return ti.states().get(title, (None, None, None))[1] if title else None


def snapshot():
    return {
        "objects": sorted(o.Name for o in doc().Objects),
        "undo": list(doc().UndoNames),
        "places": {o.Name: V(base_of(o)) for o in s.datums()},
    }


def angle_between(n1, n2):
    a, c = V(n1), V(n2)
    a.normalize()
    c.normalize()
    return math.degrees(math.acos(max(-1.0, min(1.0, abs(a.dot(c))))))


def set_gap(text):
    from sciforge import parameters

    parameters.set_user(doc(), "gap", text)  # in Change Parameters (its own scenarios)
    doc().recompute()


# -- A: a parameter typed into the distance, one Enter --------------------------------------
def a_start():
    from sciforge import parameters

    parameters.add_user(doc(), "gap", "mm", "15")  # made in Change Parameters
    h.click_empty()
    h.ribbon("Offset Plane")


def a_pick():
    h.fit()
    h.click(TOP)


def a_type_gap():
    p = s.construct_panel()
    d = p.datum if p else None
    h.check("A previews 10 above the top face", d is not None and s.close(base_of(d).z, 20.0))
    if p is not None:
        s.type_enter(p.distance.widget, "gap")


def a_finished():
    h.check("A one Enter after a parameter name finishes", not Gui.Control.activeDialog())
    plane = plane_named("Plane1")
    h.check("A Plane1 made", plane is not None, [o.Label for o in s.datums()])
    if plane is None:
        return
    st["a"] = plane.Name
    h.check("A at z = 10 + gap = 25", s.close(base_of(plane).z, 25.0), base_of(plane))
    h.check("A follows gap", formula(plane) == "gap", formula(plane))
    set_gap("20")


def a_follows():
    plane = obj("a")
    h.check("A gap = 20: z = 30", plane is not None and s.close(base_of(plane).z, 30.0))
    s.double_click_timeline(plane)


def a_edit_dialog():
    p = s.construct_panel()
    h.check("A the edit opens", p is not None and p.editing)
    if p is None:
        return
    h.check("A the distance shows 20", s.close(p.distance.value(), 20.0), p.distance.value())
    text = p.formula_label.text() if hasattr(p, "formula_label") else ""
    h.check("A the dialog says the distance follows gap", "gap" in text, text)
    h.check(
        "A ...and shows it", hasattr(p, "formula_label") and not p.formula_label.isHidden(), text
    )
    h.task_button("OK")


def a_kept():
    plane = obj("a")
    h.check("A OK closed the edit", not Gui.Control.activeDialog())
    h.check("A still follows gap", formula(plane) == "gap", formula(plane))
    set_gap("5")
    h.check("A gap = 5: z = 15", s.close(base_of(plane).z, 15.0), base_of(plane))
    s.eye("Plane1")  # it lies over the part: hide it like a person would


# -- B: two drags, then the face picked again ---------------------------------------------------
def b_start():
    h.click_empty()
    h.ribbon("Offset Plane")


def b_pick():
    h.fit()
    h.click(TOP)


def grab_point(handle):
    return handle.base_point() + handle.direction * (handle.size * 0.55)


def b_drag_up():
    p = s.construct_panel()
    if p is None or p.handle is None:
        h.check("B Offset Plane with its arrow", False)
        return
    grab = grab_point(p.handle)
    h.drag(s.screen(grab), s.screen(grab + V(0, 0, 20)), steps=16)  # let go in the air


def b_dragged_up():
    p = s.construct_panel()
    if p is None or p.handle is None:
        h.check("B still open", False)
        return
    value = p.values["distance"]
    h.check("B dragged up about 20: 30", abs(value - 30.0) < 2.0, value)
    h.check("B the arrow is let go", not p.handle.dragging())
    grab = grab_point(p.handle)
    # down through the top face, letting go over the part (FreeCAD's selection keeps that
    # release): t = -4 + 0.55 size below where the arrow starts
    end = V(20, 15, 10 - 4.0 + p.handle.size * 0.55)
    h.drag(s.screen(grab), s.screen(end), steps=20)


b_dragged_up.wait_ms = 1000


def b_dragged_down():
    p = s.construct_panel()
    if p is None or p.handle is None:
        h.check("B still open", False)
        return
    value = p.values["distance"]
    st["b_value"] = value
    h.check("B dragged down into the part: about -4", abs(value + 4.0) < 1.0, value)
    h.check("B the arrow is let go again", not p.handle.dragging())
    h.check("B the plane follows", s.close(base_of(p.datum).z, 10.0 + value), base_of(p.datum))
    s.click_box(p, 0)


b_dragged_down.wait_ms = 1000


def b_front():
    h.click(FRONT)


def b_moved_to_front():
    p = s.construct_panel()
    d = p.datum if p else None
    h.check("B still open after the new pick", d is not None)
    if d is None:
        return
    h.check("B on the front face now", s.near(s.normal_of(d), V(0, -1, 0), 1e-6), s.normal_of(d))
    h.check("B the box says face", "face" in s.box_value(p, 0).lower(), s.box_value(p, 0))
    value = st.get("b_value", 0.0)
    h.check("B the distance is kept", s.close(p.values["distance"], value), p.values["distance"])
    h.check("B y = -distance", s.close(base_of(d).y, -value), base_of(d))
    h.task_button("OK")


def b_made():
    plane = plane_named("Plane2")
    h.check("B Plane2 made", plane is not None, [o.Label for o in s.datums()])
    h.check("B dialog closed", not Gui.Control.activeDialog())
    if plane is None:
        return
    st["b"] = plane.Name
    st["b_snap"] = snapshot()
    s.double_click_timeline(plane)


def b_edit_drag():
    p = s.construct_panel()
    h.check("B the edit opens", p is not None and p.editing)
    if p is None or p.handle is None:
        return
    grab = grab_point(p.handle)
    h.drag(s.screen(grab), s.screen(grab + V(0, -15, 0)), steps=16)


b_edit_drag.wait_ms = 1000


def b_edit_cancel():
    p = s.construct_panel()
    if p is not None:
        h.check(
            "B the drag moved the preview",
            not s.close(p.values["distance"], st.get("b_value", 0.0)),
            p.values["distance"],
        )
    h.task_button("Cancel")


def b_cancelled():
    now = snapshot()
    before = st.get("b_snap", {})
    h.check("B Cancel: dialog closed", not Gui.Control.activeDialog())
    h.check("B Cancel: same objects", now["objects"] == before.get("objects"), now["objects"])
    h.check("B Cancel: same undo list", now["undo"] == before.get("undo"), now["undo"])
    plane = obj("b")
    h.check(
        "B Cancel: Plane2 where it was",
        plane is not None and s.near(base_of(plane), before["places"][plane.Name], 1e-9),
    )
    s.eye("Plane2")


# -- C: an offset of an offset; the first one deleted ------------------------------------------
def c_start():
    h.click_empty()
    h.ribbon("Offset Plane")


def c_pick():
    h.fit()
    h.click(TOP)


def c_type():
    p = s.construct_panel()
    if p is not None:
        s.type_enter(p.distance.widget, "10")


def c_first():
    plane = plane_named("Plane3")
    h.check("C Plane3 at z = 20", plane is not None and s.close(base_of(plane).z, 20.0))
    if plane is not None:
        st["c1"] = plane.Name
    h.click_empty()
    h.ribbon("Offset Plane")


def c_pick_plane():
    """Plane3 (z = 20) is in front of the part: the click takes Plane3."""
    h.click(V(30, 20, 10))


def c_type2():
    p = s.construct_panel()
    if p is None:
        return
    h.check("C on Plane3", "Plane3" in s.box_value(p, 0), s.box_value(p, 0))
    s.type_enter(p.distance.widget, "5")


def c_second():
    plane = plane_named("Plane4")
    h.check("C Plane4 at z = 25", plane is not None and s.close(base_of(plane).z, 25.0))
    if plane is None:
        return
    st["c2"] = plane.Name
    st["c_helpers"] = helpers()
    ti.menu(s.timeline_title_of(obj("c1")), "Delete")


def c_deleted():
    h.check("C Plane3 deleted", obj("c1") is None)
    plane = obj("c2")
    h.check("C Plane4 still there", plane is not None)
    if plane is None:
        return
    h.check("C ...where it was (z = 25)", s.close(base_of(plane).z, 25.0), base_of(plane))
    h.check("C ...with a warning in the timeline", status(plane) == "warning", ti.states())
    h.check("C the part untouched", s.close(h.solid_volume(), 12000.0), h.solid_volume())
    s.double_click_timeline(plane)


def c_edit_dialog():
    p = s.construct_panel()
    h.check("C the edit opens", p is not None and p.editing)
    if p is None:
        return
    h.check("C it waits for a new pick", p.picks[0] is None, p.picks)
    h.check("C ...and says so", "Click" in p.message.text(), p.message.text())
    h.check("C keeps its 5", s.close(p.distance.value(), 5.0), p.distance.value())
    h.click(TOP)


def c_repicked():
    p = s.construct_panel()
    d = p.datum if p else None
    h.check("C picked the top face", d is not None and "face" in s.box_value(p, 0).lower())
    if d is not None:
        h.check("C 5 above the top face: z = 15", s.close(base_of(d).z, 15.0), base_of(d))
    h.task_button("OK")


def c_ok():
    plane = obj("c2")
    h.check("C OK closed it", not Gui.Control.activeDialog())
    h.check("C z = 15", plane is not None and s.close(base_of(plane).z, 15.0))
    h.check("C the warning is gone", status(plane) not in ("warning", "error"), ti.states())
    s.undo()


def c_undone():
    plane = obj("c2")
    h.check("C Undo: z = 25 again", plane is not None and s.close(base_of(plane).z, 25.0))
    h.check("C Undo: the warning again", status(plane) == "warning", ti.states())
    s.redo()


def c_redone():
    plane = obj("c2")
    h.check("C Redo: z = 15", plane is not None and s.close(base_of(plane).z, 15.0))
    h.check("C Redo: no warning", status(plane) not in ("warning", "error"), ti.states())
    s.eye("Plane4")


# -- G: two faces selected first, then Midplane ---------------------------------------------------
def g_select_top():
    h.click_empty()
    h.fit()
    h.click(TOP)


def g_select_front():
    h.click(FRONT, QtCore.Qt.ControlModifier)
    h.ensure_also_selected(FRONT)


def g_start():
    sel = s.selection()
    h.check("G two faces selected", sum(len(x[1]) for x in sel) == 2, sel)
    s.menu("CONSTRUCT", "Midplane")


def g_preview():
    p = s.construct_panel()
    d = p.datum if p else None
    h.check("G Midplane took both faces", d is not None and all(p.picks), p and p.picks)
    if d is None:
        return
    n = s.normal_of(d)
    want = V(0, 1, 1)  # it runs from the edge diagonally through the part
    want.normalize()
    h.check("G halves the right angle (through the part)", abs(abs(n.dot(want)) - 1.0) < 1e-9, n)
    h.check(
        "G along the shared edge (y = 0, z = 10)",
        abs((base_of(d) - V(20, 0, 10)).dot(n)) < 1e-9,
        base_of(d),
    )
    h.task_button("OK")


def g_made():
    plane = plane_named("Plane5")
    h.check("G Plane5 made", plane is not None, [o.Label for o in s.datums()])
    h.check("G dialog closed", not Gui.Control.activeDialog())
    s.eye("Plane5")


# -- H: Plane at Angle on the origin's Z axis --------------------------------------------------------
def h_start():
    h.click_empty()
    s.menu("CONSTRUCT", "Plane at Angle")


def h_axis():
    h.fit()
    p = s.construct_panel()
    h.check("H the origin axes are drawn to click", p is not None and "axes" in p.overlays)
    h.click(V(0, 0, 30))  # the Z axis line above the part's corner, nothing behind it


def h_preview():
    p = s.construct_panel()
    d = p.datum if p else None
    h.check("H Z axis taken", d is not None and "Z" in s.box_value(p, 0), p and s.box_value(p, 0))
    if d is None:
        return
    n = s.normal_of(d)
    h.check("H 0 deg: the XZ plane", s.near(V(abs(n.x), abs(n.y), abs(n.z)), V(0, 1, 0)), n)
    st["h_n0"] = V(n)
    s.type_enter(p.angle.widget, "45")


def h_made():
    h.check("H Enter finished", not Gui.Control.activeDialog())
    plane = plane_named("Plane6")
    h.check("H Plane6 made", plane is not None, [o.Label for o in s.datums()])
    if plane is None:
        return
    st["h"] = plane.Name
    n = s.normal_of(plane)
    h.check("H still contains the Z axis", abs(n.z) < 1e-9 and base_of(plane).Length < 1e-6, n)
    a = angle_between(n, st.get("h_n0", V(0, 1, 0)))
    h.check("H turned 45 deg about Z", s.close(a, 45.0, 1e-6), a)


# -- M: Delete key in the browser ------------------------------------------------------------------
def m_select():
    st["m_helpers"] = len(helpers())
    st["m_objects"] = len(doc().Objects)
    h.check("M the browser lists Plane6", ti.click_row("Plane6"), ti.labels())


def m_delete():
    w.key(ti.tree(), QtCore.Qt.Key_Delete)


def m_deleted():
    h.check("M Plane6 deleted", obj("h") is None)
    h.check("M its helper too", len(helpers()) == st["m_helpers"] - 1, helpers())
    h.check("M nothing else", len(doc().Objects) == st["m_objects"] - 2, len(doc().Objects))
    s.no_popups("Delete")
    s.undo()


def m_undone():
    plane = obj("h")
    h.check("M Undo: Plane6 back", plane is not None)
    h.check("M Undo: its helper back", len(helpers()) == st["m_helpers"], helpers())
    if plane is None:
        return
    a = angle_between(s.normal_of(plane), st.get("h_n0", V(0, 1, 0)))
    h.check("M Undo: still 45", s.close(a, 45.0, 1e-6), a)
    s.double_click_timeline(plane)


def m_edit_dialog():
    p = s.construct_panel()
    h.check("M edits as before", p is not None and p.editing)
    if p is None:
        return
    h.check("M Z axis", "Z" in s.box_value(p, 0), s.box_value(p, 0))
    h.check("M 45", s.close(p.angle.value(), 45.0), p.angle.value())
    s.press_escape()


def m_end():
    h.check("M Esc closed it", not Gui.Control.activeDialog())
    s.eye("Plane6")


# -- F: a typo in a formula; a parameter in Section Analysis ---------------------------------
def f_start():
    h.check("F gap is 5", s.close(doc().getObject("Parameters").gap.Value, 5.0))
    h.click_empty()
    h.ribbon("Offset Plane")


def f_pick():
    h.fit()
    h.click(TOP)


def f_typo():
    p = s.construct_panel()
    h.check("F previews at z = 20", p is not None and p.datum is not None)
    if p is not None:
        st["f_z"] = base_of(p.datum).z if p.datum is not None else None
        s.type_enter(p.distance.widget, "gap +")


def f_typo_kept_open():
    p = s.construct_panel()
    h.check("F Enter after a typo keeps the dialog open", p is not None)
    s.no_popups("a typo")
    if p is None:
        return
    h.check("F it says the formula is wrong", "⚠" in p.message.text(), p.message.text())
    h.check(
        "F the preview is unchanged",
        p.datum is not None and s.close(base_of(p.datum).z, st.get("f_z") or 0.0),
    )
    h.task_button("OK")


def f_ok_refused():
    p = s.construct_panel()
    h.check("F OK waits too", p is not None)
    if p is not None:
        h.check("F still says why", "⚠" in p.message.text(), p.message.text())
        s.type_enter(p.distance.widget, "gap * 3")


def f_fixed():
    h.check("F the right formula + Enter finished it", not Gui.Control.activeDialog())
    plane = plane_named("Plane7")
    h.check("F Plane7 made", plane is not None, [o.Label for o in s.datums()])
    if plane is None:
        return
    h.check("F z = 10 + 3 * 5 = 25", s.close(base_of(plane).z, 25.0), base_of(plane))
    h.check("F follows gap * 3", formula(plane) == "gap * 3", formula(plane))
    s.eye("Plane7")


def f_section():
    h.click_empty()
    h.ribbon("Section Analysis")


def f_section_top():
    h.fit()
    h.click(TOP)


def f_section_gap():
    from sciforge import section_ui, taskui

    p = taskui.current()
    h.check("F Section on the top face", isinstance(p, section_ui.SectionPanel) and p.analysis)
    if isinstance(p, section_ui.SectionPanel):
        s.type_into(p.distance.widget, "-gap")


def f_section_cut():
    from sciforge import section, section_ui, taskui

    p = taskui.current()
    if not isinstance(p, section_ui.SectionPanel) or p.analysis is None:
        h.check("F Section still open", False)
        return
    h.check("F -gap is -5", s.close(p.options["distance"], -5.0), p.options["distance"])
    kept = section.kept_volume(h.body().Shape, p.analysis.CutPlacement)
    h.check("F the cut at z = 5: 6000 stays", s.close(kept, 6000.0), kept)
    text = p.formula_label.text() if hasattr(p, "formula_label") else ""
    h.check("F the dialog says the distance follows -gap", "-gap" in text, text)
    st["f_section"] = p.analysis.Name
    h.task_button("OK")


def f_end():
    from sciforge import section

    h.check("F OK closed it", not Gui.Control.activeDialog())
    set_gap("2")
    a = doc().getObject(st["f_section"]) if st.get("f_section") else None
    kept = section.kept_volume(h.body().Shape, a.CutPlacement) if a is not None else None
    h.check("F gap = 2: the cut follows (z = 8, 9600 stays)", s.close(kept or 0, 9600.0), kept)
    s.no_popups("the end")
    h.shot("end")


STEPS = (
    b.box_steps("InspectQA6")
    + [a_start, a_pick, a_type_gap, a_finished, a_follows, a_edit_dialog, a_kept]
    + [b_start, b_pick, b_drag_up, b_dragged_up, b_dragged_down, b_front, b_moved_to_front]
    + [b_made, b_edit_drag, b_edit_cancel, b_cancelled]
    + [c_start, c_pick, c_type, c_first, c_pick_plane, c_type2, c_second, c_deleted]
    + [c_edit_dialog, c_repicked, c_ok, c_undone, c_redone]
    + [g_select_top, g_select_front, g_start, g_preview, g_made]
    + [h_start, h_axis, h_preview, h_made]
    + [m_select, m_delete, m_deleted, m_undone, m_edit_dialog, m_end]
    + [f_start, f_pick, f_typo, f_typo_kept_open, f_ok_refused, f_fixed]
    + [f_section, f_section_top, f_section_gap, f_section_cut, f_end]
)

h.run("inspect_qa6", ti.watched(STEPS))
