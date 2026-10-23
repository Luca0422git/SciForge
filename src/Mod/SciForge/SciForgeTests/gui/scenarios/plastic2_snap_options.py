# SPDX-License-Identifier: LGPL-2.1-or-later
"""PLASTIC > Snap Fit: its other types and options, a refusal, Cancel, components and an empty
design, like a Fusion user, real input.

The base (60 x 40 x 20, 2 mm walls) under a 2 mm lid; a sketch of three points on the
parting plane: against the right wall (58, 20), the left wall (2, 20) and the middle (30,
20). The lid hidden with its eye; Snap Fit; Selection Mode Manual; a click on the middle
point: 1 point. Hook and Loop: the loop stands on the base's floor (+186.76, worked out in
the golden model plastic2_snap_loop). Perpendicular Hook and Groove: there is no wall across
the beam there, so no other body (said in the dialog), the hook alone. Parallel; Extent Type
Distance: an arrow for the base's length, the base stands above the lid, dragged 4 mm
longer it grows by its section times the drag; To Next again: as before. Automatic,
a click on the sketch's browser row: 3 points; Aligned: the catches face away from the
middle, two grooves in the side walls (2 x 21.824) and a note that one snap fit found no
wall. Independent with the angles 0, 180, 90: the same two grooves. Catch Length 1 (shorter
than the lead-in ramp): refused with the reason, OK keeps the dialog. Esc: nothing left.
Then the base and the lid as components, the lid's component moved up 20 (its lid drawn at
0 .. 2 in it): a Snap Fit across the components cuts the same groove; a point added off the
part is left out with a note (the same one groove). An empty design: Snap Fit and Lip say
what they need, no dialog.
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plastic2_steps as ps
from SciForgeTests.gui import revolve_input as ri

V = App.Vector
s = {}
LOOP = 186.76


def base_change():
    return ps.volume(s["base"]) - ps.BASE


def setup():
    base, lid = ps.enclosure("SnapOptions", lid="plate")
    ps.points_sketch(base, [(58, 20), (2, 20), (30, 20)])
    s["base"], s["lid"] = base, lid
    h.fit()
    ps.click_eye("Lid")


def open_snap():
    h.check("the lid is hidden", not s["lid"].ViewObject.Visibility)
    ps.plastic_tab()
    h.ribbon("Snap Fit")


def manual():
    p = ps.snap_panel()
    if not h.check("the dialog", p is not None):
        return
    ps.choose(p.selection, "Manual")


def click_middle_point():
    ps.settle(ps.snap_panel)
    sk = ps.by_label("SnapPoints")
    h.check("the sketch is shown to pick its points", sk.ViewObject.Visibility)
    h.fit()
    h.click(V(30, 20, 20))


def one_point():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    text = p.field.button.text()
    h.check("Manual: the clicked point only", text.startswith("1 point"), (text, ps.message(p)))
    h.check("its index", p.indices == [2], p.indices)
    ps.choose(p.type, "Hook and Loop")


def loop():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    h.check("the Loop section", p.other_box.title() == "Loop", p.other_box.title())
    h.check("Loop Thickness shown", p.fields["loop_thickness"].widget.isVisible())
    h.check("the loop on the floor: +186.76", ps.near(base_change(), LOOP, 1e-6), base_change())
    h.check("the loop's body is the base", p.other_label.text() == "Base", p.other_label.text())
    ps.choose(p.type, "Perpendicular Hook and Groove")


def perpendicular():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    h.check("the Hook Undercut section", p.other_box.title() == "Hook Undercut")
    h.check("no wall across the beam: no other body", p.other_label.text() == "(none found)")
    h.check("the base unchanged", ps.near(base_change(), 0.0, 1e-9), base_change())
    h.check("the hook is made", ps.volume(s["lid"]) > 4800 + 150, ps.volume(s["lid"]))
    ps.choose(p.type, "Parallel Hook and Groove")


def to_distance():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    h.check("To Next: no arrow for the base", "extent_distance" not in p.arrows, sorted(p.arrows))
    s["lid_next"] = ps.volume(s["lid"])
    ps.choose(p.extent, "Distance")


def distance_arrow():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    h.check("Distance: its box shown", p.fields["extent_distance"].widget.isVisible())
    if not h.check(
        "Distance: an arrow for the base's length", "extent_distance" in p.arrows, sorted(p.arrows)
    ):
        return
    s["d1"] = p.options["extent_distance"]
    s["lid_d1"] = ps.volume(s["lid"])
    h.check(
        "the base now stands above the 2 mm lid",
        s["lid_d1"] > s["lid_next"] + 1.0,
        (s["d1"], s["lid_d1"], s["lid_next"]),
    )
    s["drag"] = ps.drag_arrow(p, "extent_distance", s["d1"] + 4.0)


def distance_dragged():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    o = p.options
    d2 = o["extent_distance"]
    h.check("the arrow dragged the base longer", d2 > s["d1"] + 1.0, (s["d1"], d2))
    grown = ps.volume(s["lid"]) - s["lid_d1"]
    want = o["thickness"] * o["width"] * (d2 - s["d1"])
    h.check("the base grew by its section x the drag", ps.near(grown, want, 1e-6), (grown, want))
    ps.choose(p.extent, "To Next")


def to_next_again():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    h.check("To Next again: the arrow gone", "extent_distance" not in p.arrows, sorted(p.arrows))
    lid = ps.volume(s["lid"])
    h.check("the lid as with To Next", ps.near(lid, s["lid_next"], 1e-9), (lid, s["lid_next"]))


def automatic():
    ps.settle(ps.snap_panel)
    ps.choose(ps.snap_panel().selection, "Automatic")


def pick_sketch_row():
    ps.settle(ps.snap_panel)
    ps.click_row("SnapPoints")


def three_points():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    text = p.field.button.text()
    h.check("Automatic: the sketch's 3 points", text.startswith("3 points"), text)
    ps.choose(p.selection, "Manual")


def manual_empty():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    text = p.field.button.text()
    h.check("Manual: no point until one is clicked", text.startswith("0 points"), text)
    h.check("Manual: nothing built yet", not ps.snap_steps())
    h.check("Manual: the hook gone from the lid", ps.near(ps.volume(s["lid"]), 4800.0))
    ps.choose(p.selection, "Automatic")


def automatic_again():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    text = p.field.button.text()
    h.check("Automatic again: 3 points", text.startswith("3 points"), text)
    ps.choose(p.rotation, "Aligned")


def aligned():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    cut = -base_change()
    h.check("Aligned: two grooves in the side walls", ps.near(cut, 2 * ps.GROOVE, 1e-6), cut)
    h.check("the note: one snap fit found no wall", "1 of 3" in ps.message(p), ps.message(p))
    h.check("Face In shown for Aligned", p.inward.isVisible())
    ps.choose(p.rotation, "Independent")


def independent():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    h.check("Angles shown for Independent", p.angles.isVisible() and not p.angle.widget.isVisible())
    ps.ui.type_into(p.angles, "0, 180, 90")


def independent_angles():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    h.check("the angles taken", p.options["angles"] == [0.0, 180.0, 90.0], p.options["angles"])
    cut = -base_change()
    h.check("Independent 0 / 180: the same two grooves", ps.near(cut, 2 * ps.GROOVE, 1e-6), cut)
    turns = sorted(k for k in p.arrows if k.startswith("angle"))
    h.check("a rotation handle per snap fit", turns == ["angle1", "angle2", "angle3"], turns)
    handle = p.arrows.get("angle1")
    if handle is not None:
        h.fit()
        ri.drag_handle(p.arrows["angle1"], 90.0)


independent_angles.wait_ms = 1200


def turned_one():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    first = p.options["angles"][0]
    h.check("its handle turned the first snap fit only", 60.0 < first < 120.0, p.options["angles"])
    h.check("the others kept their angles", p.options["angles"][1:] == [180.0, 90.0])
    h.check("the Angles field follows", p.angles.text().startswith("%g" % first), p.angles.text())
    cut = -base_change()
    h.check("the right groove changed", not ps.near(cut, 2 * ps.GROOVE, 1e-6), cut)
    ps.choose(p.rotation, "Aligned")


def align_box():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    h.check("Align To shown for Aligned", p.align_field.widget.isVisible())
    ps.ui.click(p.align_field.button)


def click_right_face():
    h.check("the Align To box takes the clicks", ps.snap_panel().active == "align")
    h.fit()
    h.shot("plastic2_snap_align_click")
    h.click(V(60, 34, 4))


def aligned_to_face():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    h.check(
        "aligned to the right wall's face",
        "Face" in p.align_field.button.text(),
        p.align_field.button.text(),
    )
    cut = -base_change()
    # the right hook now faces into the box: its groove box only grazes the right wall (the
    # 0.1 clearance behind the catch: 0.1 x 6.2 x 3.2); the left one cuts its groove; the
    # middle one finds no wall
    graze = 0.1 * 6.2 * 3.2
    h.check("the catches face away from it", ps.near(cut, ps.GROOVE + graze, 1e-6), cut)
    h.check("the note: one found no wall", "1 of 3" in ps.message(p), ps.message(p))
    ps.ui.click(p.align_field.clear)


def align_cleared():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    cut = -base_change()
    h.check("cleared: the middle of the points again", ps.near(cut, 2 * ps.GROOVE, 1e-6), cut)
    ps.ui.click(p.align_field.button)


def click_front_edge():
    h.fit()
    h.click_edge(V(45, 0, 20))


def aligned_to_edge():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    text = p.align_field.button.text()
    h.check("aligned to the clicked edge", "Edge" in text, (text, ps.message(p)))
    line = p.options.get("align_line")
    h.check("a line: each catch faces straight away from it", bool(line), line)
    placed = __import__("sciforge.plastic_snap", fromlist=["x"]).frames(
        p.sketch, p.options, p.indices
    )
    dirs = [round(axes[0].y, 6) for _o, axes in placed]
    h.check("all three catches face +Y (away from the front edge)", dirs == [1.0, 1.0, 1.0], dirs)
    ps.ui.click(p.align_field.clear)


def edge_cleared():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    h.check("cleared again", ps.near(-base_change(), 2 * ps.GROOVE, 1e-6), base_change())
    ps.ui.click(p.other_field.button)


def click_base_as_other():
    h.check("the Body box takes the clicks", ps.snap_panel().active == "other")
    h.fit()
    h.click(V(60, 34, 4))


def other_picked():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    h.check(
        "the other body picked: Base",
        p.other_field.button.text() == "Base",
        p.other_field.button.text(),
    )
    h.check("still the grooves", ps.near(-base_change(), 2 * ps.GROOVE, 1e-6), base_change())
    ps.toggle(p.hide_other)


def other_hidden():
    p = ps.snap_panel()
    h.check("Hide Other Body hides the base", not s["base"].ViewObject.Visibility)
    ps.toggle(p.hide_other)


def other_shown():
    p = ps.snap_panel()
    h.check("and shows it again", s["base"].ViewObject.Visibility)
    ps.type_field(p, "catch_length", "1")


def refused():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    text = ps.message(p)
    h.check("Catch Length 1 refused: shorter than the lead-in", "lead-in" in text, text)
    ps.ok()


def ok_refused():
    p = ps.snap_panel()
    h.check("OK keeps the dialog open", p is not None)
    ps.esc()


def esc_leaves_nothing():
    h.check("Esc closed it", ps.snap_panel() is None)
    h.check("nothing left: no snap fit", not ps.snap_steps())
    h.check("the base as it was", ps.near(base_change(), 0.0, 1e-9), base_change())
    h.check("the lid as it was", ps.near(ps.volume(s["lid"]), 4800.0))


def components_design():
    from sciforge import components

    base, lid = ps.enclosure("SnapComponents", lid=None)
    top = ps.doc().addObject("PartDesign::Body", "Lid")
    top.Label = "Lid"
    ps._box(top, "Additive", "LidBox", (60, 40, 2), (0, 0, 0))
    ps.doc().recompute()
    parts = components.from_bodies(ps.doc(), [base, top])
    parts[1].Placement = App.Placement(V(0, 0, 20), App.Rotation())
    ps.points_sketch(base, [(58, 20)])
    s["base"], s["lid"] = base, top
    h.check("two components", len(parts) == 2)
    h.fit()
    ps.plastic_tab()
    h.ribbon("Snap Fit")


def pick_in_components():
    ps.settle(ps.snap_panel)
    ps.click_row("SnapPoints")


def across_components():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    if not h.check("the dialog", p is not None):
        return
    cut = -base_change()
    h.check("the groove in the base component: 21.824", ps.near(cut, ps.GROOVE, 1e-6), cut)
    added = ps.volume(s["lid"]) - 4800.0
    h.check("the hook on the lid component", 150 < added < 165, added)
    from sciforge import bodies

    box = bodies.global_shape(s["lid"]).BoundBox
    h.check("the hook hangs from the moved lid (z 8)", ps.near(box.ZMin, 8.0, 1e-6), box)
    ps.ui.click(p.hook_field.button)


def click_base_for_hooks():
    h.check("the Hook Body box takes the clicks", ps.snap_panel().active == "hook")
    h.fit()
    h.click(V(30, 0, 10))


def hooks_on_base_refused():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    h.check("Hook Body: Base", p.hook_field.button.text() == "Base", p.hook_field.button.text())
    text = ps.message(p)
    h.check("no part above the point in the base: says so, names Flip", "Flip" in text, text)
    ps.toggle(p.flip)


def hooks_on_base_flipped():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    h.check("Flip: the hooks stand on the base", "⚠" not in ps.message(p), ps.message(p))
    h.check("the base gained the hook", base_change() > 150, base_change())
    from sciforge import bodies

    h.check("the snap fit is in the base now", bodies.body_of(p.target) is s["base"])
    ps.toggle(p.flip)


def unflip():
    ps.settle(ps.snap_panel)
    ps.ui.click(ps.snap_panel().hook_field.clear)


def hooks_back_on_lid():
    ps.settle(ps.snap_panel)
    p = ps.snap_panel()
    from sciforge import bodies

    h.check("cleared: the hooks on the lid again", bodies.body_of(p.target) is s["lid"])
    h.check("and the groove again", ps.near(-base_change(), ps.GROOVE, 1e-6), base_change())
    ps.ok()


def point_off_the_part():
    """A point added to the sketch off the part (x = 80, the lid ends at 60): that snap fit
    is left out with a note, the others stay, and the other body gets no groove for it."""
    import Part

    h.check("OK closed the dialog", ps.snap_panel() is None)
    sk = ps.by_label("SnapPoints")
    sk.addGeometry(Part.Point(V(80, 20, 0)), False)
    ps.doc().recompute()
    steps = ps.snap_steps()
    if not h.check("still one Snap Fit", len(steps) == 1, steps):
        return
    state = steps[0].State
    h.check("a point off the part: it still computes", "Invalid" not in state, state)
    note = getattr(steps[0], "SciForgeWarning", "")
    h.check("and says that snap fit is left out", "2 left out" in note, note)
    h.check("the same one groove", ps.near(-base_change(), ps.GROOVE, 1e-6), base_change())


def empty_design():
    h.check("OK closed it", ps.snap_panel() is None)
    h.check("one Snap Fit", len(ps.snap_steps()) == 1)
    App.newDocument("Empty")
    ps.plastic_tab()
    h.ribbon("Snap Fit")


def no_snap_dialog():
    QtTest.QTest.qWait(300)
    h.check("an empty design: no Snap Fit dialog", not Gui.Control.activeDialog())
    h.ribbon("Lip")


def no_lip_dialog():
    QtTest.QTest.qWait(300)
    h.check("an empty design: no Lip dialog", not Gui.Control.activeDialog())


h.run(
    "plastic2_snap_options",
    [
        setup,
        open_snap,
        manual,
        click_middle_point,
        one_point,
        loop,
        perpendicular,
        to_distance,
        distance_arrow,
        distance_dragged,
        to_next_again,
        automatic,
        pick_sketch_row,
        three_points,
        manual_empty,
        automatic_again,
        aligned,
        independent,
        independent_angles,
        turned_one,
        align_box,
        click_right_face,
        aligned_to_face,
        align_cleared,
        click_front_edge,
        aligned_to_edge,
        edge_cleared,
        click_base_as_other,
        other_picked,
        other_hidden,
        other_shown,
        refused,
        ok_refused,
        esc_leaves_nothing,
        components_design,
        pick_in_components,
        across_components,
        click_base_for_hooks,
        hooks_on_base_refused,
        hooks_on_base_flipped,
        unflip,
        hooks_back_on_lid,
        point_off_the_part,
        empty_design,
        no_snap_dialog,
        no_lip_dialog,
    ],
)
