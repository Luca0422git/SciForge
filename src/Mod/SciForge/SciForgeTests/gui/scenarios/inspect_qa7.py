# SPDX-License-Identifier: LGPL-2.1-or-later
"""INSPECT (and CONSTRUCT) in a part of several features and bodies, third QA round (only real
input). Each path is what Fusion does, checked on the design:

  T  The timeline marker dragged back before the boss: an Offset Plane made there (5 above the
     box top, z = 15) goes in before the boss, which stays rolled back (12000 shown); the
     marker dragged to the end: box + boss (12000 + 250 pi), the plane still at z = 15.
     Measure (I): the boss top circle (z = 20) and the plane are 5 apart at 0 deg.
  S  Section Analysis on the box top, -5 (z > 5 cut away: 6000 of the box stays). A second
     body made afterwards (New Body, 20 x 20 x 10 at x 50..70, y 0..20) is cut too (2000
     stays). The section's eye off: nothing cut; on: cut again. Opened again from the browser:
     the arrow dragged (let go over the part), the box clicked, the front face picked, -5:
     y < 5 cut away (box 10000 + 250 pi, body 2 3000); Flip: y > 5 cut away (2000 and 1000);
     Esc: back on the top face (6000 and 2000).
  I  A third body (New Body, 20 x 30 x 10 at x 30..50, y 10..40) overlaps the box (10 x 20 x
     10 = 2000) and touches body 2 (the face x = 50). Interference of the three: one overlap;
     Include Coincident Faces: also body 2 / body 3 "touching". OK. Body 3's extrude edited
     to 5 from the timeline: the stored result follows (1000). Undo: 2000 again.

Part: box 40 x 30 x 10 from the origin with a round boss r = 5 at (10, 10), 10 high (real input).
"""
import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as bs
from SciForgeTests.gui import dialog_input as di
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import hole_steps as hs
from SciForgeTests.gui import inspect_steps as s
from SciForgeTests.gui import timeline_input as ti

V = App.Vector
st = {}
BOSS = 250 * math.pi  # r 5, 10 high
TOP = V(30, 20, 10)  # the box top, away from the boss
CIRCLE_TOP = V(13.5355339, 6.4644661, 20)  # a point of the boss top edge facing the viewer


def doc():
    return App.ActiveDocument


def obj(key):
    return doc().getObject(st[key]) if st.get(key) else None


def base_of(o):
    return o.getGlobalPlacement().Base


def measure_panel():
    from sciforge import measure_ui, taskui

    p = taskui.current()
    return p if isinstance(p, measure_ui.MeasurePanel) else None


def value(section, name):
    p = measure_panel()
    return (p.values().get(section) or {}).get(name) if p else None


def section_panel():
    from sciforge import section_ui, taskui

    p = taskui.current()
    return p if isinstance(p, section_ui.SectionPanel) else None


def sections():
    from sciforge import section

    return section.sections(doc())


def bodies():
    return bs.bodies()


def kept(body, place=None):
    """What of `body` the section shows (the kept side of its cut)."""
    from sciforge import section

    if place is None:
        p = section_panel()
        a = p.analysis if p is not None else (sections() or [None])[0]
        place = a.CutPlacement if a is not None else None
    if place is None or body is None:
        return None
    return section.kept_volume(body.Shape, place)


def clipped(body):
    from sciforge import section_ui

    return len(section_ui.clips_on(body)) if body is not None else -1


def boss_title():
    titles = s.timeline_titles()
    return titles[-1] if titles else None


# -- T: a construction made with the marker rolled back -----------------------------------------
def t_roll_back():
    st["boss"] = ti.obj(boss_title()).Name if boss_title() else None
    h.check("T the boss is the last step", st["boss"] is not None, s.timeline_titles())
    ti.drag_marker(before_title=boss_title())


def t_rolled_back():
    v = h.solid_volume()
    h.check("T rolled back: the box only", s.close(v, 12000.0), v)
    h.click_empty()
    h.ribbon("Offset Plane")


def t_pick():
    h.fit()
    h.click(TOP)


def t_type():
    p = s.construct_panel()
    if p is not None:
        s.type_enter(p.distance.widget, "5")


def t_made():
    h.check("T Enter finished", not Gui.Control.activeDialog())
    planes = s.datums("PartDesign::Plane")
    h.check("T one plane", len(planes) == 1, planes)
    if not planes:
        return
    plane = planes[0]
    st["t"] = plane.Name
    h.check("T 5 above the box top: z = 15", s.close(base_of(plane).z, 15.0), base_of(plane))
    titles = s.timeline_titles()
    mine, boss = s.timeline_title_of(plane), s.timeline_title_of(obj("boss"))
    h.check(
        "T the plane goes in before the boss",
        mine in titles and boss in titles and titles.index(mine) < titles.index(boss),
        titles,
    )
    v = h.solid_volume()
    h.check("T the boss stays rolled back", s.close(v, 12000.0), v)
    ti.drag_marker(to_end=True)


def t_at_end():
    v = h.solid_volume()
    h.check("T marker at the end: box + boss", s.close(v, 12000.0 + BOSS), v)
    plane = obj("t")
    h.check("T the plane still at z = 15", plane is not None and s.close(base_of(plane).z, 15.0))
    h.click_empty()
    h.press("i")


def t_click_edge():
    h.fit()
    p = measure_panel()
    h.check("T Measure open", p is not None)
    h.click_edge(CIRCLE_TOP)  # the boss's top circle stands above Plane1 (z = 20)


def t_click_plane():
    p = measure_panel()
    first = p.entities[0] if p is not None and p.entities else None
    h.check(
        "T Selection 1 is the boss's top circle",
        first is not None and first.kind == "edge",
        first and (first.kind, first.label),
    )
    h.click(V(-6, 34, 15))  # Plane1 where it is drawn beside the part


def t_measured():
    p = measure_panel()
    rows = p.values() if p else {}
    second = p.entities[1] if p is not None and len(p.entities) > 1 else None
    h.check(
        "T Selection 2 is the plane",
        second is not None and second.kind == "plane" and second.obj is obj("t"),
        second and (second.kind, second.label),
    )
    h.check(
        "T the circle (z = 20) and the plane (z = 15): 5 apart",
        value("Results", "Distance") == "5.000 mm",
        rows,
    )
    h.check("T Delta Z 5", value("Results", "Delta Z") == "5.000 mm", rows)
    s.press_escape()


def t_closed():
    h.check("T Esc closed Measure", measure_panel() is None and not Gui.Control.activeDialog())
    s.eye("Plane1")  # it stands over the part: hide it like a person would


# -- S: a section, a body made after it, the face picked again after a drag ---------------------
def s_start():
    h.click_empty()
    h.ribbon("Section Analysis")


def s_top():
    h.fit()
    h.click(TOP)


def s_type():
    p = section_panel()
    h.check("S on the top face", p is not None and p.analysis is not None)
    if p is not None:
        s.type_into(p.distance.widget, "-5")


def s_cut():
    p = section_panel()
    if p is None or p.analysis is None:
        h.check("S still open", False)
        return
    b1 = bodies()[0]
    h.check("S z > 5 cut away: 6000 stays", s.close(kept(b1), 6000.0), kept(b1))
    st["s_ref"] = (p.ref[0].Name, p.ref[1])
    h.task_button("OK")


def s_kept():
    found = sections()
    h.check("S Section1 kept", [o.Label for o in found] == ["Section1"], found)
    if found:
        st["s"] = found[0].Name


def s_body2_made():
    b2 = bodies()[-1]
    st["b2"] = b2.Name
    h.check("S body 2 is cut too", clipped(b2) == 1, clipped(b2))
    place = obj("s").CutPlacement
    h.check("S ...2000 of it stays", s.close(kept(b2, place), 2000.0), kept(b2, place))
    h.check("S the box still cut", clipped(bodies()[0]) == 1)
    s.expand_folder("Analysis")


def s_eye_off():
    s.eye("Section1")


def s_off():
    h.check("S section hidden: body 1 whole", clipped(bodies()[0]) == 0)
    h.check("S section hidden: body 2 whole", clipped(obj("b2")) == 0)
    s.eye("Section1")


def s_on():
    h.check("S shown again: both cut", clipped(bodies()[0]) == 1 and clipped(obj("b2")) == 1)
    ti.double_click_row("Section1")


def s_edit_drag():
    p = section_panel()
    h.check("S opened for editing", p is not None and p.editing)
    if p is None or "distance" not in p.handles:
        return
    st["s_before"] = p.options["distance"]
    st["s_pivot"] = tuple(p.options["pivot"])
    handle = p.handles["distance"]
    grab = handle.base_point() + handle.direction * (handle.size * 0.55)
    # far down, letting go over the part: FreeCAD's selection takes that release and selects
    # whatever face is under the mouse then (the bottom face, seen from inside the cut)
    h.drag(s.screen(grab), s.screen(V(25, 10, 3)), steps=16)


s_edit_drag.wait_ms = 1000


def s_dragged():
    p = section_panel()
    if p is None:
        h.check("S still open", False)
        return
    h.check(
        "S the drag moved the cut",
        not s.close(p.options["distance"], st.get("s_before", 0.0)),
        p.options["distance"],
    )
    h.check("S the arrow is let go", not p.handles["distance"].dragging())
    ref = (p.ref[0].Name, p.ref[1]) if p.ref else None
    h.check(
        "S letting go of the arrow picks nothing: still the top face",
        ref == st.get("s_ref"),
        (ref, st.get("s_ref"), s.selection()),
    )
    h.check(
        "S the cut still turns about the same point",
        tuple(p.options["pivot"]) == st.get("s_pivot"),
        (p.options["pivot"], st.get("s_pivot")),
    )
    s.type_into(p.distance.widget, "-5")


def s_back_to_5():
    p = section_panel()
    if p is None or p.analysis is None:
        h.check("S still open", False)
        return
    b1 = bodies()[0]
    h.check("S -5 again: 6000 of the box", s.close(kept(b1), 6000.0), kept(b1))
    di.click(p.box.button)


def s_front():
    h.click(V(30, 0, 2.5))  # the front face, below the cut


def s_front_picked():
    p = section_panel()
    if p is None:
        h.check("S still open", False)
        return
    h.check("S on the front face now", "face" in p.box.button.text().lower(), p.box.button.text())
    if p.analysis is not None:
        n = p.analysis.CutPlacement.Rotation.multVec(V(0, 0, 1))
        h.check(
            "S the cut stands across Y",
            abs(abs(n.y) - 1.0) < 1e-9,
            (n, p.ref, p.options),
        )
    s.type_into(p.distance.widget, "-5")


def s_front_cut():
    p = section_panel()
    if p is None or p.analysis is None:
        h.check("S still open", False)
        return
    b1, b2 = bodies()[0], obj("b2")
    h.check("S y < 5 cut away: box 10000 + boss", s.close(kept(b1), 10000 + BOSS), kept(b1))
    h.check("S body 2: 3000", s.close(kept(b2), 3000.0), kept(b2))
    di.click(p.flip)


def s_flipped():
    p = section_panel()
    if p is None or p.analysis is None:
        h.check("S still open", False)
        return
    b1, b2 = bodies()[0], obj("b2")
    h.check("S Flip: y > 5 cut away, 2000 of the box", s.close(kept(b1), 2000.0), kept(b1))
    h.check("S Flip: 1000 of body 2", s.close(kept(b2), 1000.0), kept(b2))
    s.press_escape()


def s_escaped():
    h.check("S Esc closed it", not Gui.Control.activeDialog())
    a = obj("s")
    h.check("S still one section", len(sections()) == 1, sections())
    if a is None:
        return
    b1, b2 = bodies()[0], obj("b2")
    h.check("S Esc: on the top face again", s.close(kept(b1, a.CutPlacement), 6000.0))
    h.check("S Esc: body 2 2000 again", s.close(kept(b2, a.CutPlacement), 2000.0))
    h.check("S both cut", clipped(b1) == 1 and clipped(b2) == 1)
    s.eye("Section1")  # the next path clicks bodies whole


# -- I: three bodies, overlap and touching --------------------------------------------------------
def i_check_b3():
    b3 = bodies()[-1]
    st["b3"] = b3.Name
    h.check("I three bodies", len(bodies()) == 3, bodies())
    h.click_empty()
    s.menu("INSPECT", "Interference")


def i_b1():
    h.fit()
    h.click(V(5, 25, 10))


def i_b2():
    h.click(V(65, 5, 10))


def i_b3():
    h.click(V(45, 35, 10))


def i_compute():
    p = b.active_panel()
    h.check("I three bodies picked", p is not None and len(p.picked) == 3, p and p.picked)
    if p is not None:
        di.click(p.compute)


def i_result():
    p = b.active_panel()
    rows = p.rows() if p is not None else []
    h.check("I one overlap", len(rows) == 1, rows)
    if rows:
        h.check("I box / body 3: 2000", rows[0][3] == "2000.000 mm^3", rows)
    if p is not None:
        hs.click_checkbox(p.coincident)


def i_coincident():
    p = b.active_panel()
    h.check("I Include Coincident Faces ticked", p is not None and p.coincident.isChecked())
    if p is not None:
        di.click(p.compute)


def i_coincident_result():
    p = b.active_panel()
    rows = p.rows() if p is not None else []
    h.check("I two rows", len(rows) == 2, rows)
    volumes = sorted(r[3] for r in rows)
    h.check("I the overlap and the touching pair", volumes == ["2000.000 mm^3", "touching"], rows)
    h.task_button("OK")


def i_kept():
    from sciforge import analysis

    found = analysis.of_kind(doc(), analysis.INTERFERENCE_KIND)
    h.check("I Interference1 kept", [o.Label for o in found] == ["Interference1"], found)
    if not found:
        return
    st["i"] = found[0].Name
    feature = obj("b3").Tip
    st["b3_tip"] = feature.Name
    s.double_click_timeline(feature)


def i_edit_extrude():
    p = b.active_panel()
    field = getattr(getattr(p, "distance", None), "widget", None)
    h.check("I body 3's extrude opens", field is not None, p)
    if field is not None:
        b.type_into(field, "5")


def i_extrude_ok():
    h.task_button("OK")


def i_follows():
    from sciforge import analysis

    h.check("I the extrude dialog closed", not Gui.Control.activeDialog())
    v = bs.volume(obj("b3"))
    h.check("I body 3 is 5 high now", s.close(v, 3000.0), v)
    found = analysis.results(obj("i")) if obj("i") else []
    vols = sorted(round(r[2], 6) for r in found)
    h.check("I the result follows: 1000 and touching", vols == [0.0, 1000.0], found)
    s.undo()


def i_undone():
    from sciforge import analysis

    v = bs.volume(obj("b3"))
    h.check("I Undo: body 3 10 high again", s.close(v, 6000.0), v)
    found = analysis.results(obj("i")) if obj("i") else []
    vols = sorted(round(r[2], 6) for r in found)
    h.check("I Undo: 2000 again", vols == [0.0, 2000.0], found)
    s.no_popups("the end")
    h.shot("end")


STEPS = (
    b.box_steps("InspectQA7")
    + s.boss_steps()
    + [t_roll_back, t_rolled_back, t_pick, t_type, t_made, t_at_end]
    + [t_click_edge, t_click_plane, t_measured, t_closed]
    + [s_start, s_top, s_type, s_cut, s_kept]
    + bs.box_steps("b2", (50, 0, 70, 20), 10, V(12, -8, 0), new_body=True)
    + [s_body2_made, s_eye_off, s_off, s_on, s_edit_drag, s_dragged, s_back_to_5, s_front]
    + [s_front_picked]
    + [s_front_cut, s_flipped, s_escaped]
    + bs.box_steps("b3", (30, 10, 50, 40), 10, V(12, -8, 0), new_body=True)
    + [i_check_b3, i_b1, i_b2, i_b3, i_compute, i_result, i_coincident, i_coincident_result]
    + [i_kept, i_edit_extrude, i_extrude_ok, i_follows, i_undone]
)

h.run("inspect_qa7", ti.watched(STEPS))
