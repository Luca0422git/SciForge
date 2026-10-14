# SPDX-License-Identifier: LGPL-2.1-or-later
"""INSPECT > Draft Analysis and Accessibility Analysis with real input, on the box with its
top edges rounded (r = 4). Draft: started with the body selected first (it is used); pull
direction +Z by default: the top face green (comes out of the mould), the walls red (no
draft); Draft Angle start / stop and Tolerance Zone (the rounds' in-between band yellow);
the direction picked on the right face (it turns green, the top red), Flip (blue), the
direction box cleared (Z again); Opacity 0 (the body's own grey); OK; undo / redo; edited
by selecting it in the browser and running Draft Analysis again. Accessibility: Direction 1
(+Z): the top reachable (green), the walls not (red); Direction 2: the top not; Both; Esc
leaves nothing."""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import analysis_steps as a
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import inspect_steps as s
from SciForgeTests.gui import timeline_input as ti
from SciForgeTests.gui import widget_input as w

V = App.Vector
st = {}
DRAFT = "DraftAnalysis"
ACCESS = "AccessibilityAnalysis"


def draft():
    found = a.analyses(DRAFT)
    return found[0] if found else None


# -- Draft ------------------------------------------------------------------------------------
def select_body():
    h.click_empty()
    h.click(a.TOP_FACE)


def start_draft():
    picked = [x.ObjectName for x in Gui.Selection.getSelectionEx()]
    h.check("the top face is selected first", bool(picked), picked)
    a.inspect("Draft Analysis", keep_selection=True)


def colours_z():
    p = a.panel()
    d = draft()
    h.check("Draft Analysis open with the body already picked", p is not None and p.entries)
    h.check("Draft1 made at once", d is not None and d.Label == "Draft1")
    if d is None:
        return
    h.check(
        "the direction box says Z axis",
        p.dir_box.button.text() == "Z axis",
        p.dir_box.button.text(),
    )
    h.check("pull direction +Z", (d.PullVector - V(0, 0, 1)).Length < 1e-9, d.PullVector)
    h.check(
        "the top face is green (it comes out)",
        a.name_at(a.TOP_FACE) == "green",
        a.color_at(a.TOP_FACE),
    )
    h.check(
        "the front wall is red (no draft)",
        a.name_at(a.FRONT_FACE) == "red",
        a.color_at(a.FRONT_FACE),
    )
    h.check("the model's faces are off under the colours", not a.model_faces_shown())
    h.shot("1-draft-z")
    s.type_into(p.field("DraftStart"), "10")


def start_10():
    p = a.panel()
    s.type_into(p.field("DraftStop"), "60")


def range_set():
    d = draft()
    h.check("Draft Angle start 10", d is not None and abs(d.DraftStart.Value - 10) < 1e-9)
    h.check("Draft Angle stop 60", d is not None and abs(d.DraftStop.Value - 60) < 1e-9)
    st["no_zone"] = a.colors()  # the in-between band: a blend from red to green
    a.tick(a.panel().field("ToleranceZone"), True)


def zone():
    d = draft()
    h.check("Tolerance Zone on", d is not None and d.ToleranceZone)
    counts = a.colors()
    before = a.share(st["no_zone"], "yellow")
    h.check(
        "the rounds' in-between band turns yellow",
        a.share(counts, "yellow") > 2 * before + 0.02,
        (counts, st["no_zone"]),
    )
    h.shot("2-tolerance")
    a.tick(a.panel().field("ToleranceZone"), False)
    s.type_into(a.panel().field("DraftStart"), "1")


def back_to_1():
    s.type_into(a.panel().field("DraftStop"), "3")


def pick_direction():
    p = a.panel()
    w.click(p.dir_box.button)


def direction_box_blue():
    p = a.panel()
    h.check("the Direction box is blue", p.dir_box.button.isChecked())
    h.check("the Bodies box is not", not p.box.button.isChecked())
    h.click(a.RIGHT_FACE)


def direction_x():
    p = a.panel()
    d = draft()
    h.check(
        "pull direction +X (the right face's normal)",
        d is not None and (d.PullVector - V(1, 0, 0)).Length < 1e-6,
        d and d.PullVector,
    )
    h.check("the box names the face", "face" in p.dir_box.button.text(), p.dir_box.button.text())
    h.check("the bodies stay picked", len(p.entries) == 1)
    h.check(
        "the right face is green now", a.name_at(a.RIGHT_FACE) == "green", a.color_at(a.RIGHT_FACE)
    )
    h.check("the top face is red now", a.name_at(a.TOP_FACE) == "red", a.color_at(a.TOP_FACE))
    h.shot("3-draft-x")
    w.click(p.flip)


def flipped():
    d = draft()
    h.check("Flip: -X", d is not None and (d.PullVector - V(-1, 0, 0)).Length < 1e-6)
    h.check(
        "the right face is blue (the other mould half)",
        a.name_at(a.RIGHT_FACE) == "blue",
        a.color_at(a.RIGHT_FACE),
    )
    w.click(a.panel().flip)
    w.click(a.panel().dir_box.clear)


def cleared():
    d = draft()
    p = a.panel()
    h.check(
        "the direction box cleared: Z again",
        d is not None and (d.PullVector - V(0, 0, 1)).Length < 1e-9,
    )
    h.check("it says Z axis", p.dir_box.button.text() == "Z axis")
    a.slide(p.field("Opacity"), 0)


def see_through():
    counts = a.colors()
    h.check(
        "Opacity 0: the body's own grey", a.share(counts, "red", "green", "blue") < 0.02, counts
    )
    a.slide(a.panel().field("Opacity"), 100)
    h.task_button("OK")


def kept():
    h.check("Draft1 kept", draft() is not None and a.panel() is None)
    h.check("still coloured", a.name_at(a.TOP_FACE) == "green")
    s.undo()


def undone():
    h.check("undo: no draft analysis", draft() is None)
    h.check("the model's faces are back", a.model_faces_shown())
    s.redo()


def redone():
    h.check("redo: Draft1 back", draft() is not None)
    a.open_analysis_folder()
    ti.click_row("Draft1")


redone.wait_ms = 900


def edit_again():
    a.inspect("Draft Analysis", keep_selection=True)


def editing():
    p = a.panel()
    h.check(
        "Draft Analysis with Draft1 selected edits it",
        p is not None and p.editing and p.analysis is draft(),
    )
    h.check("one draft analysis", len(a.analyses(DRAFT)) == 1)
    s.type_into(p.field("DraftStop"), "5")


def edit_ok():
    h.task_button("OK")


def edited():
    d = draft()
    h.check("the edit is kept", d is not None and abs(d.DraftStop.Value - 5) < 1e-9)
    s.eye("Draft1")


# -- Accessibility -----------------------------------------------------------------------------
def access_start():
    h.check("Draft1 hidden", draft() is not None and not draft().ViewObject.Visibility)
    a.inspect("Accessibility Analysis")


def access_pick():
    h.click(a.TOP_FACE)


def access_1():
    objs = a.analyses(ACCESS)
    h.check("Accessibility1 made", len(objs) == 1 and objs[0].Label == "Accessibility1")
    h.check(
        "the top is reachable from +Z (green)",
        a.name_at(a.TOP_FACE) == "green",
        a.color_at(a.TOP_FACE),
    )
    h.check("the walls are not (red)", a.name_at(a.FRONT_FACE) == "red", a.color_at(a.FRONT_FACE))
    h.shot("4-access")
    a.set_combo(a.panel().field("AccessMode"), "Direction 2")


def access_2():
    objs = a.analyses(ACCESS)
    h.check("Direction 2", objs and objs[0].AccessMode == "Direction 2")
    h.check(
        "from -Z the top is not reachable", a.name_at(a.TOP_FACE) == "red", a.color_at(a.TOP_FACE)
    )
    a.set_combo(a.panel().field("AccessMode"), "Both Directions")


def access_both():
    h.check("Both Directions: the top is reachable again", a.name_at(a.TOP_FACE) == "green")
    s.press_escape()


def access_cancelled():
    h.check("Esc leaves no accessibility analysis", not a.analyses(ACCESS))
    h.check("the draft analysis is still there", draft() is not None)
    h.check("hidden things stay hidden: the model's faces show", a.model_faces_shown())


h.run(
    "inspect_analysis_draft",
    a.filleted_block_steps("Draft")
    + [
        select_body,
        start_draft,
        colours_z,
        start_10,
        range_set,
        zone,
        back_to_1,
        pick_direction,
        direction_box_blue,
        direction_x,
        flipped,
        cleared,
        see_through,
        kept,
        undone,
        redone,
        edit_again,
        editing,
        edit_ok,
        edited,
        access_start,
        access_pick,
        access_1,
        access_2,
        access_both,
        access_cancelled,
    ],
)
