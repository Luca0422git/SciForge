# SPDX-License-Identifier: LGPL-2.1-or-later
"""INSPECT > Section Analysis with real input: nothing selected (the origin squares wait), the
XZ square clicked, the blue arrow dragged, a typed distance, Flip, a custom colour swatch,
Show Hatch, X Angle, OK; the analysis in the browser's Analysis folder, its eye; undo / redo;
edited again (selected in the browser, Section Analysis again); Cancel and Esc leave nothing;
a second section started with the right face selected, both cutting at once, undo.

Part (real input): box 40 x 30 x 10 from the origin with a round boss r = 5 on top, centre
(10, 10), 10 high. Hand-derived values (what stays visible = the part on the kept side):
  XZ plane (normal -Y), distance -15: the cut is at y = 15, y < 15 is cut away:
    kept 40 * 15 * 10 = 6000 (the boss, y = 5 .. 15, is all cut away); cut face 40 * 10 = 400
  flipped: y > 15 is cut away: kept 6000 + pi * 25 * 10 = 6785.398
  edited to distance -10 (still flipped): kept 40 * 10 * 10 + half the boss
    (pi * 25 / 2 * 10) = 4392.699; cut face 400 + 10 * 10 (the boss) = 500
  X Angle 90: the cut turns about the XZ plane's X axis through the middle of the part
    (20, 15, 10): horizontal at z = 10, so what stays is the box (12000) or the boss
    (pi * 25 * 10 = 785.398)
  right face (normal +X), distance -10: the cut is at x = 30, x > 30 is cut away:
    kept 30 * 30 * 10 + the boss (x = 5 .. 15) = 9000 + 250 pi; cut face 30 * 10 = 300"""
import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as di
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import hole_steps as hs
from SciForgeTests.gui import inspect_steps as s

V = App.Vector
st = {}
FULL = 12000 + math.pi * 250


def panel():
    from sciforge import section_ui, taskui

    p = taskui.current()
    return p if isinstance(p, section_ui.SectionPanel) else None


def analyses():
    from sciforge import section

    return section.sections(App.ActiveDocument)


def kept(obj=None):
    from sciforge import section

    p = panel()
    obj = obj or (p.analysis if p else None)
    if obj is None:
        return None
    return section.kept_volume(h.body().Shape, obj.CutPlacement)


def cap_area(obj=None):
    from sciforge import section

    p = panel()
    obj = obj or (p.analysis if p else None)
    return sum(f.Area for f in section.cap_faces(h.body().Shape, obj.CutPlacement))


def clips():
    from sciforge import section_ui

    root = h.body().ViewObject.RootNode
    return section_ui._clip_nodes(root)


def start():
    h.click_empty()
    h.ribbon("Section Analysis")


def waits():
    p = panel()
    h.check("Section Analysis open", p is not None)
    if p is None:
        return
    h.check("nothing made yet", p.analysis is None and not analyses())
    h.check("origin squares to click", p.planes is not None)
    h.check("Faces box is blue", p.box.button.isChecked())
    s.no_popups("Section Analysis")


def click_xz():
    h.fit()
    h.click(V(20, 0, -12))


def cut_at_xz():
    p = panel()
    a = p.analysis if p else None
    h.check("an analysis is shown", a is not None, p and p.message.text())
    if a is None:
        return
    h.check("on the XZ plane", "XZ" in p.box.button.text(), p.box.button.text())
    h.check("the body display is cut", len(clips()) == 1, clips())
    h.check("nothing of the part cut away yet", s.close(kept(), FULL), kept())
    h.check("arrow and angle balls", sorted(p.handles) == ["distance", "x", "y"], list(p.handles))
    h.check("listed as Section1", a.Label == "Section1", a.Label)


def drag_arrow():
    p = panel()
    if p is None or "distance" not in p.handles:
        return
    handle = p.handles["distance"]
    st["before"] = p.options["distance"]
    grab = handle.base_point() + handle.direction * (handle.size * 0.55)
    end = handle.base_point() + handle.direction * (handle.size * 0.55 + 8)
    h.drag(s.screen(grab), s.screen(end), steps=16)


def dragged():
    p = panel()
    if p is None:
        return
    value = p.options["distance"]
    h.check("dragging the arrow moved the cut", abs(value - st["before"]) > 2, value)
    h.check("the Distance field follows", s.close(p.distance.value(), value, 1e-3))
    s.type_into(p.distance.widget, "-15")


def at_15():
    h.check("cut at y = 15: 6000 left", s.close(kept(), 6000.0), kept())
    h.check("cut face 400", s.close(cap_area(), 400.0), cap_area())
    p = panel()
    h.check(
        "the cut face is drawn",
        p is not None and p.analysis.ViewObject.Proxy.content.getNumChildren() > 0,
    )
    h.shot("1-section-15")
    di.click(p.flip)


def flipped():
    h.check("flipped: the other half stays", s.close(kept(), 6000 + math.pi * 250), kept())
    p = panel()
    di.click(p.swatches[4][0])


def custom_colour():
    p = panel()
    h.check("a swatch picks Custom", p.color_mode.currentText() == "Custom")
    h.check(
        "its colour is stored", s.near(V(*p.analysis.CustomColor[:3]), V(*p.swatches[4][1]), 1e-2)
    )
    hs.click_checkbox(p.hatch)


def hatch_off():
    p = panel()
    h.check(
        "Show Hatch off",
        not p.analysis.ShowHatch,
        (p.hatch.isChecked(), p.options["hatch"], p.hatch.geometry(), p.message.text()),
    )
    hs.click_checkbox(p.hatch)
    h.shot("2-section-flipped")


def ok():
    h.task_button("OK")


def kept_section1():
    found = analyses()
    h.check("one analysis kept", len(found) == 1, [o.Label for o in found])
    if not found:
        return
    st["section"] = found[0].Name
    h.check("dialog closed", panel() is None and not Gui.Control.activeDialog())
    h.check("still cut", len(clips()) == 1 and s.close(kept(found[0]), 6000 + math.pi * 250))
    h.check("not a timeline step", s.timeline_title_of(found[0]) is None, s.timeline_titles())
    from SciForgeTests.gui import timeline_input as ti

    labels = ti.labels()
    h.check("browser Analysis folder", "Analysis" in labels and "Section1" in labels, labels)
    h.check("the part itself unchanged", s.close(h.solid_volume(), FULL))
    s.expand_folder("Analysis")


def eye_click():
    s.eye("Section1")


def eye_off():
    a = App.ActiveDocument.getObject(st["section"])
    h.check("eye hides the analysis", not a.ViewObject.Visibility)
    h.check("the part shows whole again", not clips(), clips())
    s.eye("Section1")


def eye_on():
    h.check("eye shows it again", len(clips()) == 1, clips())
    s.undo()


def undone():
    h.check("Undo removes the analysis", not analyses())
    h.check("Undo: the part shows whole", not clips(), clips())
    s.redo()


def redone():
    h.check("Redo brings it back", len(analyses()) == 1)
    h.check("Redo: cut again", len(clips()) == 1, clips())


def select_in_browser():
    from SciForgeTests.gui import timeline_input as ti
    from SciForgeTests.gui import widget_input as w

    h.click_empty()
    t, pos = ti.row_point("Section1")
    if pos is not None:
        w.click(t.viewport(), pos)


def edit_start():
    h.check(
        "Section1 selected",
        [x.ObjectName for x in Gui.Selection.getSelectionEx()] == [st["section"]],
        s.selection(),
    )
    h.ribbon("Section Analysis")


def edit_dialog():
    p = panel()
    h.check("the selected analysis opens to edit", p is not None and p.editing)
    if p is None:
        return
    h.check("with its distance", s.close(p.distance.value(), -15.0), p.distance.value())
    h.check("and Flip", p.flip.isChecked())
    s.type_into(p.distance.widget, "-10")


def edit_check():
    h.check("cut at y = 10: 4392.699 left", s.close(kept(), 4000 + math.pi * 125), kept())
    h.check("cut face 500", s.close(cap_area(), 500.0), cap_area())
    ok()


def edited():
    found = analyses()
    h.check("still one analysis", len(found) == 1)
    h.check("edited", s.close(kept(found[0]), 4000 + math.pi * 125), kept(found[0]))


def angle_start():
    start()


def angle_pick():
    h.fit()
    h.click(V(20, 0, -12))


def angle_90():
    p = panel()
    h.check("second analysis previewed", p is not None and p.analysis is not None)
    if p is not None:
        s.type_into(p.x_angle.widget, "90")


def angle_check():
    p = panel()
    if p is None or p.analysis is None:
        return
    from sciforge import section

    n = section.normal_of(p.analysis.CutPlacement)
    h.check(
        "X Angle 90 about the XZ plane's X axis: the cut is horizontal", abs(abs(n.z) - 1) < 1e-9, n
    )
    v = kept()
    h.check(
        "cut at z = 10: the box or the boss stays",
        s.close(v, 12000.0) or s.close(v, math.pi * 250),
        v,
    )
    h.check(
        "turned about the middle of the part",
        s.close(p.analysis.CutPlacement.Base.z, 10.0),
        p.analysis.CutPlacement,
    )
    h.check("two clips while both show", len(clips()) == 2, clips())
    h.task_button("Cancel")


def angle_cancelled():
    h.check("Cancel: one analysis", len(analyses()) == 1)
    h.check("Cancel: one clip", len(clips()) == 1, clips())


def esc_start():
    start()


def esc_pick():
    h.fit()
    h.click(V(20, 0, -12))


def esc_press():
    s.press_escape()


def escaped():
    h.check("Esc closes", not Gui.Control.activeDialog())
    h.check("Esc: one analysis", len(analyses()) == 1)
    h.check("Esc: one clip", len(clips()) == 1, clips())
    h.check("no pop-ups", not h.popups(), h.popups())
    h.shot("3-end")


# -- a second section, started with a face already selected -------------------------------------
def preselect_right_face():
    """Section1 keeps y < 10: the right face (x = 40) is still there at y = 5."""
    h.click_empty()
    h.fit()
    h.click(V(40, 5, 5))


def preselected_start():
    sel = s.selection()
    h.check("the right face is selected", sel and sel[0][1] and "Face" in sel[0][1][0], sel)
    h.ribbon("Section Analysis")


def preselected_cut():
    p = panel()
    h.check("a new section (not an edit)", p is not None and p.analysis is not None)
    if p is None or p.analysis is None:
        return
    h.check("on the selected face", "face" in p.box.button.text().lower(), p.box.button.text())
    h.check("named Section2", p.analysis.Label == "Section2", p.analysis.Label)
    h.check("at the face nothing is cut away", s.close(kept(), FULL), kept())
    s.type_into(p.distance.widget, "-10")


def preselected_10_in():
    """Cut at x = 30, x > 30 cut away: 30 x 30 x 10 + the whole boss; cut face 30 x 10."""
    v = kept()
    h.check("x > 30 cut away: 9000 + 250 pi", s.close(v, 9000 + math.pi * 250), v)
    h.check("cut face 300", s.close(cap_area(), 300.0), cap_area())
    h.check("both sections cut the body", len(clips()) == 2, clips())
    ok()


def two_sections():
    found = analyses()
    h.check("two analyses", [o.Label for o in found] == ["Section1", "Section2"], found)
    h.check("two clips", len(clips()) == 2, clips())
    s.undo()


def second_undone():
    h.check("Undo removes Section2", [o.Label for o in analyses()] == ["Section1"], analyses())
    h.check("one clip again", len(clips()) == 1, clips())
    h.check("no pop-ups at the end", not h.popups(), h.popups())


h.run(
    "inspect_section",
    b.box_steps("InspectSection")
    + s.boss_steps()
    + [
        start,
        waits,
        click_xz,
        cut_at_xz,
        drag_arrow,
        dragged,
        at_15,
        flipped,
        custom_colour,
        hatch_off,
        ok,
        kept_section1,
        eye_click,
        eye_off,
        eye_on,
        undone,
        redone,
        select_in_browser,
        edit_start,
        edit_dialog,
        edit_check,
        edited,
        angle_start,
        angle_pick,
        angle_90,
        angle_check,
        angle_cancelled,
        esc_start,
        esc_pick,
        esc_press,
        escaped,
        preselect_right_face,
        preselected_start,
        preselected_cut,
        preselected_10_in,
        two_sections,
        second_undone,
    ],
)
