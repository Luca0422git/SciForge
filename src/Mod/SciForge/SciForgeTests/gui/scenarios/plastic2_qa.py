# SPDX-License-Identifier: LGPL-2.1-or-later
"""PLASTIC part 2, the paths QA added (edits from the timeline, Cancel / Ctrl+Z inside an edit,
Undo / Redo of an edit, Hide Other Body ticked first, refusals), real input.

Snap Fit: the enclosure of plastic2_snap (base 60 x 40 x 20 with 2 mm walls, a 2 mm lid, one
sketch point at (58, 20) on the parting plane). Hide Other Body ticked before the sketch is
picked: the base (the other body, found once the snap fit is made) is hidden; OK shows it
again. Double-click "Snap Fit 1": Type Hook and Loop changes the base, Cancel puts back the
groove exactly (one groove step, Parallel). Double-click again: the Hook Body box takes a
click on the base and says the hooks stay on the lid (they cannot move to another body in an
edit); Beam Length 14, OK; Undo: Beam Length 12 and both bodies as before the edit; Redo:
the edit back. Double-click, Beam Length 16, Ctrl+Z over the 3D view: the dialog closes as
cancelled, the design as before it (14). A sketch with only a line: Snap Fit says it has no
points; Esc leaves nothing.

Lip: base and shell lid, the lid hidden, the four inside rim edges clicked, OK. Double-click
"Lip 1": Type Groove (the lid left alone), Cancel: the lip and the lid's groove back exactly.
Double-click: Lip Height 1.5, OK; Undo: as before; Redo: the taller lip.

Design Advice on that design: the Display switched to Thickness redraws the colours from the
results kept without checking the design again; OK does not check it again either (seconds
on a big part). Esc on a second Design Advice leaves only the first. A plate in a component
turned 90 degrees about X: its pull is the component's Z (the design's -Y), so its own four
sides lack draft; Esc leaves nothing.

Manual points: three points, the second picked; the first deleted from the sketch (the
indices shift): the snap fit stays on its point, and its edit shows it.
"""

import FreeCAD as App
import Part

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plastic2_steps as ps

V = App.Vector
s = {}
EDGES = [V(30, 2, 20), V(30, 38, 20), V(2, 20, 20), V(58, 20, 20)]


def bodies_volumes():
    return ps.volume(s["base"]), ps.volume(s["lid"])


def same(a, b, tol=1e-9):
    return all(ps.near(x, y, tol) for x, y in zip(a, b))


# -- Snap Fit ------------------------------------------------------------------------------------
def setup():
    base, lid = ps.enclosure("SnapQA", lid="plate")
    ps.points_sketch(base, [(58, 20)])
    s["base"], s["lid"] = base, lid
    h.fit()
    h.check("the enclosure", ps.near(ps.volume(base), ps.BASE) and ps.near(ps.volume(lid), 4800))


def open_snap():
    ps.plastic_tab()
    h.ribbon("Snap Fit")


def tick_hide_other_first():
    p = ps.snap_panel()
    if not h.check("the Snap Fit dialog is open", p is not None):
        return
    ps.toggle(p.hide_other)
    h.check("Hide Other Body ticked", p.hide_other.isChecked())
    h.check("nothing to hide yet: the base still shown", s["base"].ViewObject.Visibility)
    ps.click_row("SnapPoints")


def other_hidden_once_made():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    if not h.check("still open", p is not None):
        return
    h.check("the groove in the base", ps.near(ps.BASE - ps.volume(s["base"]), ps.GROOVE, 1e-6))
    h.check("the other body is the base", p.other_label.text() == "Base", p.other_label.text())
    h.check(
        "Hide Other Body ticked first: the base hidden once found",
        not s["base"].ViewObject.Visibility,
    )
    ps.ok()


def ok_shows_other():
    h.check("the dialog closed", ps.snap_panel() is None)
    h.check("OK shows the base again", s["base"].ViewObject.Visibility)
    s["ok"] = bodies_volumes()
    h.check("one Snap Fit", len(ps.snap_steps()) == 1, ps.titles())
    h.check("double-click opens the edit", ps.double_click_timeline("Snap Fit 1"))


def edit_to_loop():
    p = ps.snap_panel()
    if not h.check("the edit dialog", p is not None and p.editing):
        return
    ps.choose(p.type, "Hook and Loop")


def loop_shown():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    if not h.check("still open", p is not None):
        return
    base, lid = bodies_volumes()
    h.check("Hook and Loop: the base's groove is gone", not ps.near(base, s["ok"][0]), base)
    h.check("the section is called Loop", p.other_box.title() == "Loop", p.other_box.title())
    ps.cancel()


def cancel_restores():
    h.check("Cancel closed the dialog", ps.snap_panel() is None)
    h.check("Cancel: both bodies exactly as before the edit", same(bodies_volumes(), s["ok"]))
    steps = ps.snap_steps()
    h.check("still one Snap Fit", len(steps) == 1)
    if steps:
        h.check(
            "still Parallel", steps[0].SnapType == "Parallel Hook and Groove", steps[0].SnapType
        )
        followers = ps.followers(steps[0])
        h.check("one groove step, in the base", len(followers) == 1, followers)
        bad = [o.Name for o in ps.doc().Objects if "Invalid" in o.State or "Error" in o.State]
        h.check("every step computed", not bad, bad)
    h.check("double-click opens the edit again", ps.double_click_timeline("Snap Fit 1"))


def hook_body_box():
    p = ps.snap_panel()
    if not h.check("the edit dialog", p is not None and p.editing):
        return
    ps.ui.click(p.hook_field.button)
    h.check("the Hook Body box takes the clicks", p.active == "hook", p.active)
    h.click(V(30, 0, 10))  # the base's front face


def hook_body_refused():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    if not h.check("still open", p is not None):
        return
    text = ps.message(p)
    h.check("an edit keeps the hooks on the lid: said why", "stay on Lid" in text, text)
    h.check("the design not changed by the click", same(bodies_volumes(), s["ok"]))
    ps.type_field(p, "length", "14")


def edit_longer():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    if not h.check("still open", p is not None):
        return
    h.check("Beam Length 14: the hook grows", ps.volume(s["lid"]) > s["ok"][1] + 20)
    ps.ok()


def edit_done():
    h.check("the dialog closed", ps.snap_panel() is None)
    s["edited"] = bodies_volumes()
    step = ps.snap_steps()[0]
    h.check("Beam Length 14 kept", ps.near(step.BeamLength.Value, 14.0), step.BeamLength)
    ps.undo()


def edit_undone():
    step = ps.snap_steps()[0] if ps.snap_steps() else None
    h.check("Undo the edit: still the Snap Fit", step is not None)
    if step is None:
        return
    h.check("Undo: Beam Length 12", ps.near(step.BeamLength.Value, 12.0), step.BeamLength)
    h.check("Undo: both bodies as before the edit", same(bodies_volumes(), s["ok"]))
    ps.redo()


def edit_redone():
    step = ps.snap_steps()[0] if ps.snap_steps() else None
    if not h.check("Redo: the Snap Fit", step is not None):
        return
    h.check("Redo: Beam Length 14", ps.near(step.BeamLength.Value, 14.0), step.BeamLength)
    h.check("Redo: the edited bodies", same(bodies_volumes(), s["edited"]))
    h.check("double-click opens the edit", ps.double_click_timeline("Snap Fit 1"))


def edit_then_ctrl_z():
    p = ps.snap_panel()
    if not h.check("the edit dialog", p is not None and p.editing):
        return
    ps.type_field(p, "length", "16")
    ps.settle(ps.snap_panel)
    h.check("Beam Length 16 shown", ps.volume(s["lid"]) > s["edited"][1] + 5)
    h.click_empty()
    ps.tl.ctrl("z")


def ctrl_z_cancels():
    h.check("Ctrl+Z closed the dialog", ps.snap_panel() is None)
    step = ps.snap_steps()[0] if ps.snap_steps() else None
    if not h.check("the Snap Fit is still there", step is not None):
        return
    h.check("Ctrl+Z: Beam Length 14 again", ps.near(step.BeamLength.Value, 14.0), step.BeamLength)
    h.check("Ctrl+Z: the bodies as before the dialog", same(bodies_volumes(), s["edited"]))


def no_points_sketch():
    sk = s["base"].newObject("Sketcher::SketchObject", "LineOnly")
    sk.Label = "LineOnly"
    sk.Placement = App.Placement(V(0, 0, 20), App.Rotation())
    sk.addGeometry(Part.LineSegment(V(10, 10, 0), V(20, 10, 0)), False)
    ps.doc().recompute()
    s["before_line"] = bodies_volumes()
    ps.plastic_tab()
    h.ribbon("Snap Fit")


def click_line_sketch():
    p = ps.snap_panel()
    if not h.check("the Snap Fit dialog is open", p is not None):
        return
    ps.click_row("LineOnly")


def no_points_said():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    if not h.check("still open", p is not None):
        return
    text = ps.message(p)
    h.check("a sketch with no points: said so", "has no points" in text, text)
    h.check("no new snap fit", len(ps.snap_steps()) == 1, ps.titles())
    ps.esc()


def no_points_esc():
    h.check("Esc closed it", ps.snap_panel() is None)
    h.check("still one Snap Fit", len(ps.snap_steps()) == 1, ps.titles())
    h.check("the bodies unchanged", same(bodies_volumes(), s["before_line"]))


def facing_down_sketch():
    """A sketch whose normal points down into the base (as one on the lid's underside): the
    hook body is on the normal's side, so the hooks go on the base and nothing is in front
    of their catches."""
    sk = s["lid"].newObject("Sketcher::SketchObject", "DownPoints")
    sk.Label = "DownPoints"
    sk.Placement = App.Placement(V(0, 0, 20), App.Rotation(V(1, 0, 0), 180))
    sk.addGeometry(Part.Point(V(58, -20, 0)), False)
    ps.doc().recompute()
    s["before_down"] = bodies_volumes()
    ps.plastic_tab()
    h.ribbon("Snap Fit")


def click_down_sketch():
    p = ps.snap_panel()
    if not h.check("the Snap Fit dialog is open", p is not None):
        return
    ps.click_row("DownPoints")


def no_groove_body_note():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    if not h.check("still open", p is not None):
        return
    text = ps.message(p)
    h.check("no body for the groove: said so", "no body found in front" in text, text)
    h.check("the other body: none found", p.other_label.text() == "(none found)")
    ps.toggle(p.flip)


def flipped_finds_groove():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    if not h.check("still open", p is not None):
        return
    text = ps.message(p)
    h.check("Flip: the groove body found", p.other_label.text() == "Base", p.other_label.text())
    h.check("Flip: the note gone", "no body found" not in text, text)
    ps.esc()


def down_esc():
    h.check("Esc closed it", ps.snap_panel() is None)
    h.check("Esc: the bodies unchanged", same(bodies_volumes(), s["before_down"]))
    h.check("still one Snap Fit", len(ps.snap_steps()) == 1, ps.titles())


def ids_design():
    """Manual points followed through a sketch edit: three points, the second one picked;
    the first point deleted from the sketch afterwards (its indices shift down by one)."""
    App.closeDocument(ps.doc().Name)
    base, lid = ps.enclosure("SnapIds", lid="plate")
    ps.points_sketch(base, [(57, 10), (57, 30), (4, 20)], label="IdPoints")
    s["base"], s["lid"] = base, lid
    h.fit()


def hide_lid():
    """The lid hidden with its eye (a step of its own: the browser shows the new design
    first)."""
    ps.click_eye("Lid")


def ids_open():
    h.check("the lid is hidden", not s["lid"].ViewObject.Visibility)
    ps.plastic_tab()
    h.ribbon("Snap Fit")


def ids_manual():
    p = ps.snap_panel()
    if not h.check("the Snap Fit dialog", p is not None):
        return
    ps.click_row("IdPoints")
    ps.settle(ps.snap_panel)
    ps.choose(p.selection, "Manual")


def ids_click_point():
    ps.settle(ps.snap_panel)
    h.fit()
    h.click(V(57, 30, 20))


def ids_picked():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    if not h.check("still open", p is not None):
        return
    h.check("Manual: the second point (index 1)", p.indices == [1], (p.indices, ps.message(p)))
    ps.ok()


def hook_y(lid):
    below = lid.Shape.common(Part.makeBox(60, 40, 15, V(0, 0, 5)))
    return below.BoundBox.Center.y if below.Volume > 1e-6 else None


def ids_point_deleted():
    h.check("the dialog closed", ps.snap_panel() is None)
    s["ids_ok"] = bodies_volumes()
    h.check("the hook at y = 30", abs((hook_y(s["lid"]) or 0) - 30) < 0.5, hook_y(s["lid"]))
    # the design changes: the first point is deleted from the sketch (Sketcher renumbers
    # the points after it)
    sk = ps.by_label("IdPoints")
    sk.delGeometry(0)
    ps.doc().recompute()
    h.check("the sketch has 2 points left", len(sk.Geometry) == 2)
    h.check(
        "the snap fit stays on its point (y = 30)",
        abs((hook_y(s["lid"]) or 0) - 30) < 0.5,
        hook_y(s["lid"]),
    )
    h.check("the same hook and groove", same(bodies_volumes(), s["ids_ok"], 1e-7))
    bad = [o.Name for o in ps.doc().Objects if "Invalid" in o.State or "Error" in o.State]
    h.check("every step computed", not bad, bad)
    h.check("double-click opens the edit", ps.double_click_timeline("Snap Fit 1"))


def ids_edit_reads():
    p = ps.snap_panel()
    if not h.check("the edit dialog", p is not None and p.editing):
        return
    h.check("the edit shows the same point (now index 0)", p.indices == [0], p.indices)
    h.check("1 point", p.field.button.text().startswith("1 point"), p.field.button.text())
    ps.esc()


def ids_esc():
    h.check("Esc closed it", ps.snap_panel() is None)
    h.check("Esc: the same hook and groove", same(bodies_volumes(), s["ids_ok"], 1e-7))


# -- Lip -----------------------------------------------------------------------------------------
def lip_design():
    App.closeDocument(ps.doc().Name)
    base, lid = ps.enclosure("LipQA", lid="shell")
    s["base"], s["lid"] = base, lid
    # hidden as setup (the eye click is plastic2_lip's): an eye click right after the
    # previous design closed selected the row instead in xvfb
    lid.ViewObject.Visibility = False
    h.fit()


def open_lip():
    h.check("the lid is hidden", not s["lid"].ViewObject.Visibility)
    ps.plastic_tab()
    h.ribbon("Lip")


def click_edge(i):
    def step():
        ps.settle(ps.lip_panel)
        if i == 0:
            h.fit()
        h.click_edge(EDGES[i])

    step.__name__ = "lip_edge_%d" % (i + 1)
    return step


def lip_ok():
    ps.settle(ps.lip_panel)
    p = ps.lip_panel()
    if not h.check("the Lip dialog", p is not None):
        return
    h.check("4 edges", p.field.button.text() == "4 edges", (p.field.button.text(), p.names))
    h.check("the other body is the lid", p.mate_label.text() == "Lid", p.mate_label.text())
    ps.ok()


def lip_made():
    h.check("the Lip dialog closed", ps.lip_panel() is None)
    s["lip_ok"] = bodies_volumes()
    h.check("the lip on the base", s["lip_ok"][0] > ps.BASE + 100, s["lip_ok"])
    h.check("the groove in the lid", s["lip_ok"][1] < ps.LID_SHELL - 100, s["lip_ok"])
    h.check("double-click opens the edit", ps.double_click_timeline("Lip 1"))


def lip_to_groove():
    p = ps.lip_panel()
    if not h.check("the Lip edit dialog", p is not None and p.editing):
        return
    ps.choose(p.type, "Groove")


def groove_shown():
    ps.settle(ps.lip_panel)
    p = ps.lip_panel()
    if not h.check("still open", p is not None):
        return
    base, lid = bodies_volumes()
    h.check("Groove: the base loses material", base < ps.BASE, base)
    h.check("Groove: the lid left alone", ps.near(lid, ps.LID_SHELL), lid)
    ps.cancel()


def lip_cancel_restores():
    h.check("Cancel closed the dialog", ps.lip_panel() is None)
    h.check("Cancel: the lip and the groove back exactly", same(bodies_volumes(), s["lip_ok"]))
    steps = ps.lip_steps()
    h.check("one Lip", len(steps) == 1)
    if steps:
        h.check("still Lip And Groove", steps[0].LipType == "Lip And Groove", steps[0].LipType)
        h.check("its groove step in the lid", len(ps.followers(steps[0])) == 1)
    h.check("double-click opens the edit again", ps.double_click_timeline("Lip 1"))


def lip_taller():
    p = ps.lip_panel()
    if not h.check("the Lip edit dialog", p is not None and p.editing):
        return
    ps.type_field(p, "lip_height", "1.5")
    ps.settle(ps.lip_panel)
    h.check("Lip Height 1.5: the base gains", ps.volume(s["base"]) > s["lip_ok"][0] + 50)
    ps.ok()


def lip_taller_done():
    h.check("the dialog closed", ps.lip_panel() is None)
    s["lip_tall"] = bodies_volumes()
    ps.undo()


def lip_edit_undone():
    h.check("Undo the edit: the bodies as before it", same(bodies_volumes(), s["lip_ok"]))
    steps = ps.lip_steps()
    if h.check("still the Lip", len(steps) == 1):
        h.check("Undo: Lip Height 1", ps.near(steps[0].LipHeight.Value, 1.0), steps[0].LipHeight)
    ps.redo()


def lip_edit_redone():
    h.check("Redo: the taller lip", same(bodies_volumes(), s["lip_tall"]))


# -- Design Advice -----------------------------------------------------------------------------
def count_checks():
    """Count the Design Advice checks run from here on."""
    from sciforge import plastic_advice

    if not hasattr(plastic_advice, "_qa_measure"):
        plastic_advice._qa_measure = plastic_advice.measure

        def counted(obj):
            s["checks"] = s.get("checks", 0) + 1
            return plastic_advice._qa_measure(obj)

        plastic_advice.measure = counted
    s["checks"] = 0
    ps.click_eye("Lid")
    ps.plastic_tab()
    ps.menu("INSPECT", "Design Advice")


def advice_first():
    ps.settle(ps.advice_panel)
    p = ps.advice_panel()
    if not h.check("the Design Advice dialog", p is not None):
        return
    h.check("checked once", s.get("checks") == 1, s.get("checks"))
    h.check("a summary", bool(p.summary.text()), (p.summary.text(), ps.message(p)))
    s["results"] = p.analysis.Results
    ps.choose(p.display, "Thickness")


def thickness_redrawn():
    ps.settle(ps.advice_panel)
    h.idle_step()
    p = ps.advice_panel()
    if not h.check("still open", p is not None):
        return
    h.check("Display Thickness kept", p.analysis.Display == "Thickness", p.analysis.Display)
    h.check("the display change did not check the design again", s.get("checks") == 1, s)
    h.check("the same results", p.analysis.Results == s["results"])
    proxy = p.analysis.ViewObject.Proxy
    drawn = getattr(proxy, "drawn", {})
    h.check("the thickness map drawn on both bodies", len(drawn) == 2, drawn)
    h.check("the analysis is not waiting for a recompute", "Touched" not in p.analysis.State)
    ps.ok()


def advice_kept():
    h.check("the dialog closed", ps.advice_panel() is None)
    h.check("OK did not check the design again", s.get("checks") == 1, s.get("checks"))
    from sciforge import plastic_advice

    h.check("one Design Advice", len(plastic_advice.advices(ps.doc())) == 1)
    ps.plastic_tab()
    ps.menu("INSPECT", "Design Advice")


def second_advice_esc():
    ps.settle(ps.advice_panel)
    h.check("a second dialog", ps.advice_panel() is not None)
    ps.esc()


def esc_leaves_one():
    from sciforge import plastic_advice

    h.check("Esc closed it", ps.advice_panel() is None)
    h.check("Esc left only the first", len(plastic_advice.advices(ps.doc())) == 1)


def restore_measure():
    from sciforge import plastic_advice

    if hasattr(plastic_advice, "_qa_measure"):
        plastic_advice.measure = plastic_advice._qa_measure
        del plastic_advice._qa_measure


def turned_design():
    """A plate (20 x 20 x 2) in a component turned 90 degrees about X: moulded along its own
    Z, which is the design's -Y now."""
    App.closeDocument(ps.doc().Name)
    ps.clear_plastic_prefs()
    d = App.newDocument("AdviceTurned")
    comp = d.addObject("App::Part", "Comp")
    comp.Label = "Comp"
    comp.Placement = App.Placement(V(0, 0, 0), App.Rotation(V(1, 0, 0), 90))
    body = d.addObject("PartDesign::Body", "Plate")
    body.Label = "Plate"
    comp.addObject(body)
    box = body.newObject("PartDesign::AdditiveBox", "PlateBox")
    box.Length, box.Width, box.Height = 20, 20, 2
    body.Tip = box
    d.recompute()
    s["plate"] = body
    h.fit()


def turned_open():
    ps.plastic_tab()
    ps.menu("INSPECT", "Design Advice")


def turned_checked():
    from sciforge import plastic_advice

    ps.settle(ps.advice_panel)
    p = ps.advice_panel()
    if not h.check("the Design Advice dialog", p is not None):
        return
    found = plastic_advice.results(p.analysis).get("bodies", [])
    if not h.check("the plate checked", len(found) == 1, (found, ps.message(p))):
        ps.esc()
        return
    pull = V(*found[0]["pull"])
    h.check("the pull is the component's Z (the design's -Y)", (pull - V(0, -1, 0)).Length < 1e-9)
    drafty = sorted(n for n, f in found[0]["faces"].items() if "draft" in f.get("issues", {}))
    # the plate's own sides (its Face1..4) run along its Z: no draft; its top and bottom
    # (Face5, Face6) are square to the pull
    h.check(
        "the plate's 4 sides lack draft", drafty == ["Face1", "Face2", "Face3", "Face4"], drafty
    )
    ps.esc()


def turned_esc():
    from sciforge import plastic_advice

    h.check("Esc closed it", ps.advice_panel() is None)
    h.check("Esc left nothing", not plastic_advice.advices(ps.doc()))


h.run(
    "plastic2_qa",
    [
        setup,
        open_snap,
        tick_hide_other_first,
        other_hidden_once_made,
        ok_shows_other,
        edit_to_loop,
        loop_shown,
        cancel_restores,
        hook_body_box,
        hook_body_refused,
        edit_longer,
        edit_done,
        edit_undone,
        edit_redone,
        edit_then_ctrl_z,
        ctrl_z_cancels,
        no_points_sketch,
        click_line_sketch,
        no_points_said,
        no_points_esc,
        facing_down_sketch,
        click_down_sketch,
        no_groove_body_note,
        flipped_finds_groove,
        down_esc,
        ids_design,
        hide_lid,
        ids_open,
        ids_manual,
        ids_click_point,
        ids_picked,
        ids_point_deleted,
        ids_edit_reads,
        ids_esc,
        lip_design,
        open_lip,
        click_edge(0),
        click_edge(1),
        click_edge(2),
        click_edge(3),
        lip_ok,
        lip_made,
        lip_to_groove,
        groove_shown,
        lip_cancel_restores,
        lip_taller,
        lip_taller_done,
        lip_edit_undone,
        lip_edit_redone,
        count_checks,
        advice_first,
        thickness_redrawn,
        advice_kept,
        second_advice_esc,
        esc_leaves_one,
        restore_measure,
        turned_design,
        turned_open,
        turned_checked,
        turned_esc,
    ],
)
