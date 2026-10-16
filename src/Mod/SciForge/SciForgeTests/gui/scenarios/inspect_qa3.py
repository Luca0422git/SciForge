# SPDX-License-Identifier: LGPL-2.1-or-later
"""What happens to constructions and analyses when what they are built on goes away, and to
Center of Mass / Interference across save and reopen (QA, only real input). Fusion keeps
working: a construction whose reference was deleted stays where it was with a warning in the
timeline, the rest of the part is untouched, nothing shows an error or a pop-up.

Part (real input): box 40 x 30 x 10 with a round boss r = 5 at (10, 10), 10 high.

  P  Axis Through Cylinder on the boss, Point at Center of its top circle, a Section on its
     top face moved 5 into the part (z = 15: 12000 + 125 pi stays). The boss extrude deleted
     from the timeline: the box is still shown (12000), the axis and the point stay where
     they were with a warning, the section keeps cutting at z = 15; Axis1 opened from the
     timeline waits for a new face (the lost one is not offered); Undo / Redo / Undo (each a
     recompute of everything) show no error; the boss is back and the warnings are gone.
  M  Midplane of the YZ origin square and the right face (x = 20); the boss mirrored about
     it (Mirror, the construction plane as mirror plane): a second boss at (30, 10).
  Q  A second body (20 x 20 x 5 from (30, 20, 5), New Body) overlaps the box by 10 x 10 x 5:
     Interference finds 500; a Center of Mass of body 2 (40, 30, 7.5); a Center of Mass of
     every visible body. Saved, closed, reopened: all three are back with their results and
     the overlap is drawn; Interference opened again shows its table. Body 2 deleted from the
     browser: no error; Interference has nothing to compare (it says so when opened); the
     Center of Mass of body 2 hides its marker; the one of every body follows (box + boss).
     Undo brings body 2 and every result back.
  R  Interference with one body picked: Compute and OK say what is missing and wait.
"""

import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as di
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import inspect_steps as s
from SciForgeTests.gui import timeline_input as ti

V = App.Vector
st = {}
BOX_BOSS = 12000 + 250 * math.pi
CYL_SIDE = V(13.5355339, 6.4644661, 15)
TOP_CIRCLE = V(13.5355339, 6.4644661, 20)


def doc():
    return App.ActiveDocument


def obj(key):
    return doc().getObject(st[key]) if st.get(key) else None


def panel():
    from sciforge import taskui

    return taskui.current()


def body1():
    return obj("b1") or h.body()


def solids(body):
    try:
        return body.Shape.Volume
    except Exception:
        return 0.0


def step_status(o):
    title = s.timeline_title_of(o)
    return ti.states().get(title, (None, None, None))[1] if title else None


def clips():
    from sciforge import section_ui

    return section_ui.clips_on(body1())


def kinds(kind):
    from sciforge import analysis

    return analysis.of_kind(doc(), kind)


# -- P: the boss deleted under its constructions and section --------------------------------
def p_axis():
    h.click_empty()
    s.menu("CONSTRUCT", "Axis Through Cylinder/Cone/Torus")


def p_axis_click():
    h.fit()
    h.click(CYL_SIDE)


def p_axis_ok():
    p = panel()
    h.check("Axis Through Cylinder previews", p is not None and getattr(p, "datum", None))
    h.task_button("OK")


def p_point():
    found = s.datums("PartDesign::Line")
    h.check("Axis1 made", len(found) == 1, found)
    if found:
        st["axis"] = found[0].Name
        st["axis_place"] = found[0].getGlobalPlacement()
    h.click_empty()
    s.menu("CONSTRUCT", "Point at Center of Circle/Sphere/Torus")


def p_point_click():
    h.fit()
    h.click_edge(TOP_CIRCLE)


def p_point_ok():
    h.task_button("OK")


def p_section():
    found = s.datums("PartDesign::Point")
    h.check("Point1 made", len(found) == 1, found)
    if found:
        st["point"] = found[0].Name
        st["point_place"] = found[0].getGlobalPlacement()
        h.check(
            "at the circle's centre",
            s.near(found[0].getGlobalPlacement().Base, V(10, 10, 20), 1e-6),
        )
    st["b1"] = h.body().Name
    h.click_empty()
    h.ribbon("Section Analysis")


def p_section_click():
    h.fit()
    h.click(V(12, 8, 20))


def p_section_5_in():
    p = panel()
    h.check("a section on the boss top", p is not None and getattr(p, "analysis", None))
    if p is not None:
        s.type_into(p.distance.widget, "-5")


def p_section_ok():
    h.task_button("OK")


def p_delete_boss():
    from sciforge import section

    found = section.sections(doc())
    h.check("Section1 kept", len(found) == 1, found)
    if found:
        st["section"] = found[0].Name
        st["cut"] = found[0].CutPlacement
        v = section.kept_volume(body1().Shape, found[0].CutPlacement)
        h.check("cut at z = 15: 12000 + 125 pi", s.close(v, 12000 + 125 * math.pi), v)
    feats = [o for o in body1().Group if o.isDerivedFrom("PartDesign::Feature")]
    st["boss"] = feats[-1].Name
    st["undo"] = list(doc().UndoNames)
    ti.menu(s.timeline_title_of(feats[-1]), "Delete")


def p_deleted():
    body = body1()
    h.check("the boss is deleted", obj("boss") is None)
    h.check("the box is still there: 12000", s.close(solids(body), 12000.0), solids(body))
    h.check(
        "the body is up to date (nothing blocks its recompute)",
        "Touched" not in list(body.State) and "Invalid" not in list(body.State),
        list(body.State),
    )
    axis, point = obj("axis"), obj("point")
    h.check(
        "Axis1 stays where it was",
        axis is not None and axis.getGlobalPlacement().isSame(st["axis_place"], 1e-9),
    )
    h.check(
        "Point1 stays where it was",
        point is not None and point.getGlobalPlacement().isSame(st["point_place"], 1e-9),
    )
    h.check("Axis1 shows a warning in the timeline", step_status(axis) == "warning", ti.states())
    h.check("Point1 shows a warning in the timeline", step_status(point) == "warning", ti.states())
    a = obj("section")
    h.check(
        "the section keeps cutting at z = 15",
        a is not None and len(clips()) == 1 and a.CutPlacement.isSame(st["cut"], 1e-9),
        clips(),
    )
    s.no_popups("deleting the boss")
    h.shot("P-boss-deleted")
    s.double_click_timeline(axis)


def p_axis_dialog():
    p = s.construct_panel()
    h.check("Axis1 opens for editing", p is not None and p.editing)
    if p is None:
        return
    h.check(
        "its lost face is not offered (the box waits)",
        s.box_value(p, 0) == "Select",
        s.box_value(p, 0),
    )
    h.check("it says what to click", "round face" in p.message.text(), p.message.text())
    s.no_popups("editing a construction that lost its face")
    s.press_escape()


def p_axis_escaped():
    h.check("Esc closed it", not Gui.Control.activeDialog())
    axis = obj("axis")
    h.check(
        "Axis1 still where it was",
        axis is not None and axis.getGlobalPlacement().isSame(st["axis_place"], 1e-9),
    )
    s.undo()


def p_undone():
    h.check("Undo brings the boss back", obj("boss") is not None)
    s.redo()


def p_redone():
    """Redo deletes the boss again and recomputes everything: still no error anywhere."""
    h.check("Redo deletes the boss again", obj("boss") is None)
    h.check("Axis1 warns again", step_status(obj("axis")) == "warning", ti.states())
    h.check("the box 12000", s.close(solids(body1()), 12000.0), solids(body1()))
    s.undo()


def p_back():
    body = body1()
    h.check("Undo brings the boss back", obj("boss") is not None)
    h.check("box + boss again", s.close(solids(body), BOX_BOSS), solids(body))
    h.check(
        "Axis1 without a warning", step_status(obj("axis")) not in ("warning", "error"), ti.states()
    )
    h.check(
        "Point1 without a warning",
        step_status(obj("point")) not in ("warning", "error"),
        ti.states(),
    )
    from sciforge import section

    a = obj("section")
    h.check(
        "the section is fine again",
        a is not None and not section.problem(a),
        a and section.problem(a),
    )


# -- M: Midplane of the part, the boss mirrored about it ----------------------------------------
def m_midplane():
    h.click_empty()
    s.menu("CONSTRUCT", "Midplane")


def m_click_yz():
    """The YZ origin square where it shows beside the part (nothing in front of it there)."""
    h.fit()
    pl.click_square("YZ_Plane")  # where the square shows (was 0, 20, 20)


def m_click_right():
    p = s.construct_panel()
    h.check(
        "the YZ square went into Plane 1",
        p is not None and "YZ" in s.box_value(p, 0),
        p and s.box_value(p, 0),
    )
    h.click(V(40, 15, 5))


def m_mid_ok():
    p = s.construct_panel()
    d = p.datum if p else None
    h.check(
        "the midplane of the part: x = 20",
        d is not None and s.close(d.getGlobalPlacement().Base.x, 20.0),
        d and d.getGlobalPlacement(),
    )
    h.task_button("OK")


def m_mirror():
    planes = s.datums("PartDesign::Plane")
    h.check("Plane1 kept", len(planes) == 1, planes)
    if planes:
        st["mid"] = planes[0].Name
    Gui.Selection.clearSelection()
    h.ribbon("Mirror")


def m_click_boss_step():
    from SciForgeTests.gui import pattern_steps as ps

    ps.timeline_click(s.timeline_title_of(obj("boss")))


def m_plane_box():
    from SciForgeTests.gui import pattern_steps as ps

    p = ps.panel()
    h.check(
        "the boss picked",
        p is not None and len(p.options["objects"]) == 1,
        p and p.options["objects"],
    )
    ps.click_box("plane")


def m_click_midplane():
    """The midplane sticks out in front of the part (y < 0)."""
    h.fit()
    h.click(V(20, -6, 5))


def m_mirrored():
    from SciForgeTests.gui import pattern_steps as ps

    p = ps.panel()
    plane = p.options["plane"] if p else None
    h.check(
        "the construction midplane is the mirror plane",
        plane is not None and plane[0].Name == st.get("mid"),
        plane,
    )
    v = solids(body1())
    h.check("a second boss mirrored to (30, 10)", s.close(v, 12000 + 500 * math.pi), v)
    h.task_button("OK")


def m_kept():
    v = solids(body1())
    h.check("Mirror kept: two bosses", s.close(v, 12000 + 500 * math.pi), v)
    h.check("the solid is valid", body1().Shape.isValid())
    h.shot("M-mirror")
    s.undo()


def m_undone():
    v = solids(body1())
    h.check("Undo: one boss again", s.close(v, BOX_BOSS), v)
    s.eye(obj("mid").Label)


# -- Q: two bodies, analyses, save, reopen, delete a body -------------------------------------
def q_sketch():
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def q_click_top():
    h.click(V(32, 22, 10))


def q_square():
    sk = h.in_sketch()
    h.check("a sketch on the box top", sk is not None)
    if sk:
        x0, y0 = h.to_sketch(sk, V(30, 20, 10))
        x1, y1 = h.to_sketch(sk, V(50, 40, 10))
        h.draw_rectangle(sk, min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def q_finish():
    h.ribbon("Finish Sketch")


def q_extrude():
    h.fit()
    h.press("e")


def q_new_body():
    p = b.active_panel()
    h.check("Extrude open", p is not None and hasattr(p, "operation"))
    if p is not None:
        h.check("New Body chosen", di.choose(p.operation, "New Body"))


def q_down_5():
    p = b.active_panel()
    if p is not None:
        s.type_into(p.distance.widget, "-5")


def q_extrude_ok():
    h.task_button("OK")


def q_two_bodies():
    bodies = doc().findObjects("PartDesign::Body")
    h.check("two bodies", len(bodies) == 2, bodies)
    if len(bodies) == 2:
        st["b2"] = [x for x in bodies if x.Name != st["b1"]][0].Name
        h.check("body 2 is 2000", s.close(solids(obj("b2")), 2000.0), solids(obj("b2")))
    h.click_empty()
    s.menu("INSPECT", "Interference")


def q_int_b1():
    h.fit()
    h.click(V(5, 5, 10))


def q_int_b2():
    h.click(V(45, 35, 10))


def q_int_compute():
    p = panel()
    h.check("both bodies picked", p is not None and len(getattr(p, "picked", [])) == 2)
    if p is not None:
        di.click(p.compute)


def q_int_result():
    p = panel()
    rows = p.rows() if p is not None and hasattr(p, "rows") else []
    h.check("one overlap of 500", len(rows) == 1 and rows[0][3] == "500.000 mm^3", rows)
    h.task_button("OK")


def q_com_b2():
    from sciforge import analysis

    found = kinds(analysis.INTERFERENCE_KIND)
    h.check("Interference1 kept", len(found) == 1, found)
    if found:
        st["int"] = found[0].Name
    h.click_empty()
    s.menu("INSPECT", "Center of Mass")


def q_com_pick_b2():
    h.fit()
    h.click(V(45, 35, 10))


def q_com_b2_ok():
    p = panel()
    pos = p.position() if p is not None and hasattr(p, "position") else None
    h.check(
        "Center of Mass of body 2: (40, 30, 7.5)",
        pos is not None and s.near(pos, V(40, 30, 7.5), 1e-6),
        pos,
    )
    h.task_button("OK")


def q_com_all():
    h.click_empty()
    s.menu("INSPECT", "Center of Mass")


def q_com_all_ok():
    h.task_button("OK")


def q_save():
    from sciforge import analysis

    found = kinds(analysis.COM_KIND)
    h.check("two Centers of Mass", len(found) == 2, found)
    if len(found) == 2:
        st["com_b2"], st["com_all"] = found[0].Name, found[1].Name
        st["com_all_pos"] = V(found[1].Position)
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge_inspect_qa3_"), "inspect_qa3.FCStd")
    st["path"] = path
    doc().saveAs(path)


def q_close():
    App.closeDocument(doc().Name)


def q_reopen():
    App.openDocument(st["path"])


def q_reopened():
    h.fit()
    com_b2, com_all, itf = obj("com_b2"), obj("com_all"), obj("int")
    h.check("the analyses are back", None not in (com_b2, com_all, itf))
    if None in (com_b2, com_all, itf):
        return
    h.check("Center of Mass of body 2 kept", s.near(com_b2.Position, V(40, 30, 7.5), 1e-6))
    h.check("Center of Mass of all kept", s.near(com_all.Position, st["com_all_pos"], 1e-6))
    h.check("Interference result kept", len(itf.Results) == 1, itf.Results)
    try:
        drawn = itf.ViewObject.Proxy.content.getNumChildren()
    except Exception:
        drawn = -1
    h.check("the overlap is drawn after reopening", drawn > 0, drawn)
    s.expand_folder("Analysis")


def q_select_int():
    h.click_empty()
    ti.click_row(obj("int").Label)


def q_edit_int():
    s.menu("INSPECT", "Interference")


def q_int_dialog():
    p = panel()
    rows = p.rows() if p is not None and hasattr(p, "rows") else []
    h.check("Interference opens with its table", len(rows) == 1, rows)
    h.task_button("Cancel")


def q_delete_b2():
    st["b2_label"] = obj("b2").Label
    ti.row_menu(st["b2_label"], "Delete")


def q_b2_deleted():
    from sciforge import analysis

    h.check("body 2 deleted", obj("b2") is None)
    s.no_popups("deleting body 2")
    itf, com_b2, com_all = obj("int"), obj("com_b2"), obj("com_all")
    h.check(
        "Interference has nothing to compare",
        itf is not None and analysis.problem(itf) and not itf.Results,
        itf and (analysis.problem(itf), itf.Results),
    )
    h.check(
        "its overlap is no longer drawn",
        itf is not None and itf.ViewObject.Proxy.content.getNumChildren() == 0,
    )
    h.check(
        "the Center of Mass of body 2 says its body is gone",
        com_b2 is not None and analysis.problem(com_b2),
        com_b2 and analysis.problem(com_b2),
    )
    h.check(
        "and does not fall back to the other body",
        com_b2 is not None and not analysis.all_bodies(com_b2),
    )
    body = body1()
    centre = body.Shape.Solids[0].CenterOfMass if body.Shape.Solids else None
    h.check(
        "the Center of Mass of every body follows (body 1 only)",
        centre is not None and s.near(com_all.Position, centre, 1e-6),
        (com_all.Position, centre),
    )
    h.shot("Q-body2-deleted")
    ti.click_row(obj("int").Label)


def q_edit_after_delete():
    s.menu("INSPECT", "Interference")


def q_int_problem():
    p = panel()
    h.check("Interference opens", p is not None and hasattr(p, "rows"))
    if p is None:
        return
    h.check("it says it needs two bodies", "two bodies" in p.message.text(), p.message.text())
    h.check("no stale table", not p.rows(), p.rows())
    h.task_button("Cancel")


def q_undo():
    s.undo()


def q_restored():
    from sciforge import analysis

    h.check("Undo brings body 2 back", obj("b2") is not None)
    itf, com_b2 = obj("int"), obj("com_b2")
    h.check(
        "the overlap is found again",
        itf is not None and len(itf.Results) == 1 and not analysis.problem(itf),
        itf and itf.Results,
    )
    h.check(
        "the Center of Mass of body 2 is back",
        com_b2 is not None
        and not analysis.problem(com_b2)
        and s.near(com_b2.Position, V(40, 30, 7.5), 1e-6),
    )


# -- R: Interference with one body ---------------------------------------------------------------
def r_start():
    h.click_empty()
    s.menu("INSPECT", "Interference")


def r_one():
    if panel() is None and not st.get("r_retried"):
        # The menu click can land while FreeCAD is still busy (CI #114): open it again.
        st["r_retried"] = True
        s.menu("INSPECT", "Interference")
        h.state["queue"].insert(0, r_one)
        return
    h.fit()
    h.click(V(5, 5, 10))


def r_compute():
    p = panel()
    if p is not None:
        di.click(p.compute)


def r_said():
    p = panel()
    h.check(
        "Compute with one body says what is missing",
        p is not None and "two" in p.message.text(),
        p and p.message.text(),
    )
    h.task_button("OK")


def r_ok_waits():
    p = panel()
    h.check("OK waits for a second body", p is not None and hasattr(p, "rows"))
    s.no_popups("Interference with one body")
    s.press_escape()


def r_escaped():
    from sciforge import analysis

    h.check("Esc closed it", not Gui.Control.activeDialog())
    h.check("no new Interference", len(kinds(analysis.INTERFERENCE_KIND)) == 1)


def the_end():
    s.no_popups("the end")
    h.shot("end")


STEPS = (
    b.box_steps("InspectQA3")
    + s.boss_steps()
    + [p_axis, p_axis_click, p_axis_ok, p_point, p_point_click, p_point_ok, p_section]
    + [p_section_click, p_section_5_in, p_section_ok, p_delete_boss, p_deleted]
    + [p_axis_dialog, p_axis_escaped, p_undone, p_redone, p_back]
    + [m_midplane, m_click_yz, m_click_right, m_mid_ok, m_mirror, m_click_boss_step]
    + [m_plane_box, m_click_midplane, m_mirrored, m_kept, m_undone]
    + [q_sketch, q_click_top, q_square, q_finish, q_extrude, q_new_body, q_down_5]
    + [q_extrude_ok, q_two_bodies, q_int_b1, q_int_b2, q_int_compute, q_int_result]
    + [q_com_b2, q_com_pick_b2, q_com_b2_ok, q_com_all, q_com_all_ok, q_save, q_close]
    + [q_reopen, q_reopened, q_select_int, q_edit_int, q_int_dialog, q_delete_b2]
    + [q_b2_deleted, q_edit_after_delete, q_int_problem, q_undo, q_restored]
    + [h.idle_step(), r_start, r_one, r_compute, r_said, r_ok_waits, r_escaped, the_end]
)

h.run("inspect_qa3", ti.watched(STEPS))
