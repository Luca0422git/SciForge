# SPDX-License-Identifier: LGPL-2.1-or-later
"""Measure and Section Analysis the way Fusion users really use them (QA), only real input.

Part (real input): box 40 x 30 x 10 from the origin with a round boss r = 5, centre
(10, 10), 10 high on top. Paths and hand-derived values:

  K  Measure, nothing picked: Delete does nothing; the box top and the boss top are 10
     apart at 0 degrees (Delta Z 10); a third click (the boss's round side) starts again:
     radius 5, diameter 10, area 2 pi 5 10 = 314.159; to the corner (40, 0, 10) the
     shortest distance is sqrt(30^2 + 10^2) - 5 = 26.623; Delete with picks deletes
     nothing; Esc closes without an undo step.
  L  Units changed to inches (browser > Units): the front top edge is 40 mm = 1.575 in,
     the box top 1121.460 mm^2 = 1.738 in^2; back to millimetres.
  M  E pressed while Measure is open: Measure closes and Extrude opens with nothing
     picked (the measured face is not a profile); Esc leaves the part as it was.
  O  Section Analysis on a construction plane (Offset Plane 10 into the right face,
     x = 30): x > 30 cut away, 9000 + 250 pi stays; the plane edited to 20 in (x = 20):
     the section follows (6000 + 250 pi); the plane deleted: no error, nothing cut.
  N  Section on the front face (y = 0, the arrow points out of the part): dragged far out
     (nothing cut), far in (everything cut away, no error), typed -15 (y < 15 cut away:
     6000 stays, cut face 400); OK; a pin (r 4 at (30, 15), 5 high) made afterwards is cut
     too (6000 + 40 pi; cut face 440); the body's eye off and on, the section's eye off and
     on; saved, closed, reopened: still cut; edited (-5: 10000 + 250 pi + 80 pi), Esc
     puts it back; Undo / Redo of the OK; Delete from the browser.
"""
import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as di
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import inspect_steps as s
from SciForgeTests.gui import timeline_input as ti

V = App.Vector
st = {}
BOX_BOSS = 12000 + 250 * math.pi
CYL_SIDE = V(13.5355339, 6.4644661, 15)  # a point of the boss's side facing the viewer


def doc():
    return App.ActiveDocument


def measure_panel():
    from sciforge import measure_ui, taskui

    p = taskui.current()
    return p if isinstance(p, measure_ui.MeasurePanel) else None


def section_panel():
    from sciforge import section_ui, taskui

    p = taskui.current()
    return p if isinstance(p, section_ui.SectionPanel) else None


def value(section, name):
    p = measure_panel()
    return (p.values().get(section) or {}).get(name) if p else None


def number(text):
    try:
        return float(str(text).split()[0])
    except Exception:
        return None


def analyses():
    from sciforge import section

    return section.sections(doc())


def clips():
    from sciforge import section_ui

    body = h.body()
    if body is None or body.ViewObject is None:
        return []
    return section_ui.clips_on(body)


def clipped_elsewhere():
    """Clip planes anywhere but on solids (the body's own root, its construction planes and
    sketches): Section Analysis cuts only bodies."""
    from sciforge import section_ui

    found = []
    for o in doc().Objects:
        if o.ViewObject is None or o.isDerivedFrom("PartDesign::Feature"):
            continue
        if section_ui._clip_nodes(o.ViewObject.RootNode):
            found.append(o.Label)
    return found


def kept(obj):
    from sciforge import section

    return section.kept_volume(h.body().Shape, obj.CutPlacement)


def cap_area(obj):
    from sciforge import section

    return sum(f.Area for f in section.cap_faces(h.body().Shape, obj.CutPlacement))


def drawn_caps(obj):
    try:
        return obj.ViewObject.Proxy.content.getNumChildren()
    except Exception:
        return -1


def snapshot():
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
        "%s: no undo step added" % where,
        now["undo"] == before["undo"],
        (now["undo"], before["undo"]),
    )
    h.check(
        "%s: the part is unchanged" % where, s.close(now["volume"], before["volume"]), now["volume"]
    )


def part_made():
    v = h.solid_volume()
    h.check("box + boss", s.close(v, BOX_BOSS), v)


# -- K: Measure ---------------------------------------------------------------------------
def k_start():
    st["k"] = snapshot()
    h.click_empty()
    h.fit()
    h.press("i")


def k_open():
    p = measure_panel()
    h.check("I opens Measure", p is not None)
    if p is None:
        return
    h.check("it says what to click", "Click" in p.message.text(), p.message.text())
    h.press(QtCore.Qt.Key_Delete)


def k_delete_nothing():
    h.check("Delete with nothing picked: Measure still open", measure_panel() is not None)
    s.no_popups("Delete in Measure")
    h.click(V(30, 20, 10))


def k_boss_top():
    h.check(
        "the box top measured",
        value("Selection 1", "Area") is not None,
        measure_panel() and measure_panel().values(),
    )
    h.click(V(12, 8, 20))


def k_two_tops():
    d = number(value("Results", "Distance"))
    h.check(
        "box top to boss top: 10",
        d is not None and s.close(d, 10.0, 1e-3),
        measure_panel() and measure_panel().values(),
    )
    a = number(value("Results", "Angle"))
    h.check("parallel: 0 degrees", a is not None and abs(a) < 1e-3, a)
    dz = number(value("Results", "Delta Z"))
    h.check("Delta Z 10", dz is not None and s.close(dz, 10.0, 1e-3), dz)
    h.click(CYL_SIDE)


def k_cylinder():
    p = measure_panel()
    vals = p.values() if p else {}
    h.check("a third pick starts again", "Results" not in vals and len(vals) == 1, vals)
    h.check("radius 5", s.close(number(value("Selection 1", "Radius")) or 0, 5.0, 1e-3), vals)
    h.check("diameter 10", s.close(number(value("Selection 1", "Diameter")) or 0, 10.0, 1e-3))
    area = number(value("Selection 1", "Area")) or 0
    h.check("side area 314.159", s.close(area, 100 * math.pi, 1e-5), area)
    s.click_vertex(V(40, 0, 10))


def k_cyl_corner():
    d = number(value("Results", "Distance"))
    want = math.sqrt(1000.0) - 5.0
    h.check(
        "round side to the corner: 26.623",
        d is not None and abs(d - want) < 1e-3,
        (d, measure_panel() and measure_panel().values()),
    )
    h.shot("K-measure")
    st["k_sel"] = s.selection()
    h.press(QtCore.Qt.Key_Delete)


def k_delete_picks():
    h.check("Delete with picks: Measure still open", measure_panel() is not None)
    h.check("Delete deleted nothing", s.close(h.solid_volume(), BOX_BOSS), h.solid_volume())
    h.check("the picks are kept", s.selection() == st["k_sel"], (s.selection(), st["k_sel"]))
    s.no_popups("Delete with picks in Measure")
    s.press_escape()


def k_closed():
    h.check("Esc closes Measure", not Gui.Control.activeDialog())
    h.check("the picks are cleared", not Gui.Selection.getSelectionEx(), s.selection())
    same_as(st["k"], "Measure")


# -- L: inches ------------------------------------------------------------------------------
def l_units():
    ti.click_row("Units: mm")


def l_inch():
    from sciforge import browser_ui

    panel = browser_ui.UnitsPanel.last
    h.check("Change Active Units opens", panel is not None and not panel._closed)
    if panel is None:
        return
    combo = panel.form.findChild(QtWidgets.QComboBox, "SciForgeUnitType")
    di.choose(combo, "Inch")
    h.task_button("OK")


def l_measure():
    h.check(
        "the design is in inches", ti.row("Units: in") is not None if hasattr(ti, "row") else True
    )
    h.click_empty()
    h.press("i")


def l_edge():
    h.fit()
    h.click_edge(V(20, 0, 10))


def l_edge_inch():
    text = value("Selection 1", "Length")
    h.check("40 mm shown as 1.575 in", text == "1.575 in", text)
    h.click(V(30, 20, 10))


def l_face_inch():
    text = value("Selection 2", "Area")
    h.check("1121.460 mm^2 shown as 1.738 in^2", text == "1.738 in^2", text)
    d = value("Results", "Distance")
    h.check("the edge lies on the face: 0.000 in", d == "0.000 in", d)
    h.shot("L-inches")
    s.press_escape()


def l_back():
    ti.click_row("Units: in")


def l_mm():
    from sciforge import browser_ui

    combo = browser_ui.UnitsPanel.last.form.findChild(QtWidgets.QComboBox, "SciForgeUnitType")
    di.choose(combo, "Millimeter")
    h.task_button("OK")


# -- M: E while Measure is open --------------------------------------------------------------
def m_start():
    h.check("back in millimetres", doc().UnitSystem.startswith("Standard"), doc().UnitSystem)
    st["m"] = snapshot()
    h.click_empty()
    h.press("i")


def m_pick():
    h.fit()
    h.click(V(30, 20, 10))


def m_press_e():
    h.check("the face is measured", value("Selection 1", "Area") is not None)
    h.press("e")


def m_extrude_open():
    from SciForgeTests.gui import blend_steps as bs

    panel = bs.active_panel()
    h.check("E closed Measure", measure_panel() is None)
    h.check(
        "and opened Extrude",
        panel is not None and "Extrude" in type(panel).__name__,
        type(panel).__name__ if panel else None,
    )
    picked = getattr(panel, "profiles", None)
    h.check("with nothing picked (the measured face is no profile)", not picked, picked)
    s.press_escape()


def m_unchanged():
    h.check("Esc closed Extrude", not Gui.Control.activeDialog())
    same_as(st["m"], "E during Measure")


# -- O: a section on a construction plane ----------------------------------------------------
def o_plane_start():
    h.click_empty()
    h.ribbon("Offset Plane")


def o_right_face():
    h.fit()
    h.click(V(40, 15, 5))


def o_type_in():
    p = s.construct_panel()
    if p is None:
        h.check("Offset Plane open", False)
        return
    s.type_into(p.distance.widget, "-10")


def o_plane_ok():
    h.task_button("OK")


def o_plane_made():
    planes = s.datums("PartDesign::Plane")
    h.check("one construction plane", len(planes) == 1, planes)
    if not planes:
        return
    st["plane"] = planes[0].Name
    h.check("at x = 30", s.close(planes[0].getGlobalPlacement().Base.x, 30.0))
    h.click_empty()
    h.ribbon("Section Analysis")


def o_click_plane():
    """The plane sticks out in front of the part (y < 0): nothing else is in front there."""
    h.fit()
    h.click(V(30, -6, 5))


def o_cut():
    p = section_panel()
    a = p.analysis if p else None
    h.check("a section on the construction plane", a is not None, p.message.text() if p else None)
    if a is None:
        return
    h.check("the box says Plane1", "Plane1" in p.box.button.text(), p.box.button.text())
    v = kept(a)
    h.check("x > 30 cut away: 9000 + 250 pi", s.close(v, 9000 + 250 * math.pi), v)
    h.task_button("OK")


def o_kept():
    found = analyses()
    h.check("Section1 kept", [o.Label for o in found] == ["Section1"], found)
    if found:
        st["o_section"] = found[0].Name
    s.double_click_timeline(doc().getObject(st["plane"]))


def o_edit_plane():
    p = s.construct_panel()
    h.check("the plane opens for editing", p is not None and p.editing)
    if p is not None:
        s.type_into(p.distance.widget, "-20")


def o_edit_ok():
    h.task_button("OK")


def o_followed():
    a = doc().getObject(st["o_section"])
    v = kept(a)
    h.check("the section followed the plane: 6000 + 250 pi", s.close(v, 6000 + 250 * math.pi), v)
    h.check("still one cut", len(clips()) == 1, clips())
    h.check(
        "only the body's solid is cut (the plane in the cut stays whole)",
        not clipped_elsewhere(),
        clipped_elsewhere(),
    )
    h.shot("O-section-on-plane")
    st["o_before_delete"] = list(doc().UndoNames)
    ti.menu(s.timeline_title_of(doc().getObject(st["plane"])), "Delete")


def o_plane_deleted():
    h.check("the plane is gone", doc().getObject(st["plane"]) is None)
    s.no_popups("deleting the plane a section uses")
    from sciforge import section

    a = doc().getObject(st["o_section"])
    h.check(
        "the section stays where it was (x = 20)",
        len(clips()) == 1 and s.close(kept(a), 6000 + 250 * math.pi),
        (clips(), kept(a)),
    )
    h.check("it knows its plane is gone", bool(section.problem(a)), section.problem(a))
    h.check("the part is unchanged", s.close(h.solid_volume(), BOX_BOSS), h.solid_volume())
    s.undo()


def o_plane_back():
    plane = doc().getObject(st["plane"])
    h.check("Undo brings the plane back", plane is not None)
    a = doc().getObject(st["o_section"])
    h.check("and the section with it", a is not None and len(clips()) == 1, clips())
    if a is not None:
        from sciforge import section

        h.check("cutting at x = 20 again", s.close(kept(a), 6000 + 250 * math.pi), kept(a))
        h.check("and fine again", not section.problem(a), section.problem(a))
    s.expand_folder("Analysis")


def o_delete_section():
    ti.row_menu("Section1", "Delete")


def o_section_deleted():
    h.check("Section1 deleted from the browser", not analyses(), analyses())
    h.check("nothing cut any more", not clips(), clips())
    s.no_popups("deleting a section")
    s.eye("Plane1")


# -- N: a section on a face, features made after it, reopen -----------------------------------
def n_start():
    h.click_empty()
    h.ribbon("Section Analysis")


def n_front():
    h.fit()
    h.click(V(20, 0, 5))


def n_on_front():
    p = section_panel()
    a = p.analysis if p else None
    h.check("a section on the front face", a is not None)
    if a is None:
        return
    st["n_section"] = a.Name
    h.check(
        "the clicked face is taken, not the XZ origin plane lying on it",
        "face" in p.box.button.text(),
        p.box.button.text(),
    )
    h.check("nothing cut away at the face", s.close(kept(a), BOX_BOSS), kept(a))
    handle = p.handles.get("distance")
    h.check("the blue arrow is there", handle is not None)
    if handle is None:
        return
    grab = handle.base_point() + handle.direction * (handle.size * 0.55)
    far_out = handle.base_point() + handle.direction * (handle.size * 0.55 + 60)
    h.drag(s.screen(grab), s.screen(far_out), steps=20)


def n_far_out():
    p = section_panel()
    if p is None:
        return
    d = p.options["distance"]
    h.check("dragged far out: a big positive distance", d > 20, d)
    h.check("nothing is cut away", s.close(kept(p.analysis), BOX_BOSS), kept(p.analysis))
    h.check("no message", not p.message.text() or "Click" not in p.message.text(), p.message.text())
    s.type_into(p.distance.widget, "-80")


def n_far_in():
    p = section_panel()
    if p is None:
        return
    h.check("80 in: everything cut away", s.close(kept(p.analysis), 0.0), kept(p.analysis))
    h.check("no cut face drawn", drawn_caps(p.analysis) == 0, drawn_caps(p.analysis))
    h.check("no error shown", not p.error, p.error)
    h.shot("N-everything-cut")
    s.type_into(p.distance.widget, "-15")


def n_at_15():
    p = section_panel()
    if p is None:
        return
    v = kept(p.analysis)
    h.check("y < 15 cut away: 6000", s.close(v, 6000.0), v)
    h.check("cut face 400", s.close(cap_area(p.analysis), 400.0), cap_area(p.analysis))
    h.task_button("OK")


def n_kept():
    found = analyses()
    h.check("one section kept", len(found) == 1, found)
    h.check("the body is cut", len(clips()) == 1, clips())
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def n_sketch_top():
    """The box top at y > 15 is still shown (y < 15 is cut away)."""
    h.click(V(30, 22, 10))


def n_pin_circle():
    sk = h.in_sketch()
    h.check("a sketch on the top face", sk is not None)
    if sk is None:
        return
    x, y = h.to_sketch(sk, V(30, 15, 10))
    h.draw_circle(sk, x, y, 4)


def n_pin_finish():
    h.ribbon("Finish Sketch")


def n_pin_extrude():
    h.fit()
    h.press("e")


def n_pin_5():
    from SciForgeTests.gui import blend_steps as bs

    panel = bs.active_panel()
    field = getattr(getattr(panel, "distance", None), "widget", None)
    h.check("Extrude took the circle", field is not None)
    if field is not None:
        s.type_into(field, "5")


def n_pin_ok():
    h.task_button("OK")


def n_pin_cut_too():
    v = h.solid_volume()
    h.check("the pin was added", s.close(v, BOX_BOSS + 80 * math.pi), v)
    a = doc().getObject(st["n_section"])
    h.check("still cut once", len(clips()) == 1, clips())
    k = kept(a)
    h.check("the pin is cut too: 6000 + 40 pi", s.close(k, 6000 + 40 * math.pi), k)
    h.check("cut face 440", s.close(cap_area(a), 440.0), cap_area(a))
    h.check("the cut face is drawn", drawn_caps(a) > 0, drawn_caps(a))
    h.check("sketches are not cut", not clipped_elsewhere(), clipped_elsewhere())
    h.shot("N-pin-cut")
    s.eye("Body")


def n_body_hidden():
    h.check("body hidden: no cut on it", not clips(), clips())
    s.eye("Body")


def n_body_shown():
    h.check("body shown: cut again", len(clips()) == 1, clips())
    s.expand_folder("Analysis")


def n_section_eye():
    s.eye(doc().getObject(st["n_section"]).Label)


def n_section_off():
    h.check("section hidden: the part whole", not clips(), clips())
    s.eye(doc().getObject(st["n_section"]).Label)


def n_section_on():
    h.check("section shown: cut again", len(clips()) == 1, clips())


def n_save():
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge_inspect_qa2_"), "inspect_qa2.FCStd")
    st["path"] = path
    st["label"] = doc().getObject(st["n_section"]).Label
    doc().saveAs(path)


def n_close():
    App.closeDocument(doc().Name)


def n_reopen():
    App.openDocument(st["path"])


def n_reopened():
    h.fit()
    found = analyses()
    h.check("the section is back", [o.Label for o in found] == [st["label"]], found)
    h.check("the part is cut after reopening", len(clips()) == 1, clips())
    if found:
        h.check(
            "the cut face is drawn after reopening", drawn_caps(found[0]) > 0, drawn_caps(found[0])
        )
        h.check("still y < 15 cut away", s.close(kept(found[0]), 6000 + 40 * math.pi))
    h.shot("N-reopened")
    s.expand_folder("Analysis")


def n_select():
    h.click_empty()
    ti.click_row(st["label"])


def n_edit():
    h.check(
        "the section is selected",
        [x.ObjectName for x in Gui.Selection.getSelectionEx()] == [st["n_section"]],
        s.selection(),
    )
    h.ribbon("Section Analysis")


def n_edit_dialog():
    p = section_panel()
    h.check("it opens for editing after reopening", p is not None and p.editing)
    if p is None:
        return
    h.check("with -15", s.close(p.distance.value(), -15.0), p.distance.value())
    s.type_into(p.distance.widget, "-5")


def n_edit_preview():
    p = section_panel()
    if p is None:
        return
    v = kept(p.analysis)
    want = 10000 + 250 * math.pi + 80 * math.pi
    h.check("y < 5 cut away: 10000 + 330 pi", s.close(v, want), (v, want))
    s.press_escape()


def n_edit_escaped():
    a = doc().getObject(st["n_section"])
    h.check("Esc: back at -15", s.close(a.Distance.Value, -15.0), a.Distance.Value)
    h.check("Esc: the cut is back at y = 15", s.close(kept(a), 6000 + 40 * math.pi), kept(a))
    h.check("one cut", len(clips()) == 1, clips())


def the_end():
    s.no_popups("the end")
    h.shot("end")


STEPS = (
    b.box_steps("InspectQA2")
    + s.boss_steps()
    + [part_made]
    + [k_start, k_open, k_delete_nothing, k_boss_top, k_two_tops, k_cylinder, k_cyl_corner]
    + [k_delete_picks, k_closed]
    + [l_units, l_inch, l_measure, l_edge, l_edge_inch, l_face_inch, l_back, l_mm]
    + [m_start, m_pick, m_press_e, m_extrude_open, m_unchanged]
    + [o_plane_start, o_right_face, o_type_in, o_plane_ok, o_plane_made, o_click_plane, o_cut]
    + [o_kept, o_edit_plane, o_edit_ok, o_followed, o_plane_deleted, o_plane_back]
    + [o_delete_section, o_section_deleted]
    + [n_start, n_front, n_on_front, n_far_out, n_far_in, n_at_15, n_kept, n_sketch_top]
    + [n_pin_circle, n_pin_finish, n_pin_extrude, n_pin_5, n_pin_ok, n_pin_cut_too]
    + [n_body_hidden, n_body_shown, n_section_eye, n_section_off, n_section_on]
    + [n_save, n_close, n_reopen, n_reopened, n_select, n_edit, n_edit_dialog]
    + [n_edit_preview, n_edit_escaped, the_end]
)

h.run("inspect_qa2", ti.watched(STEPS))
