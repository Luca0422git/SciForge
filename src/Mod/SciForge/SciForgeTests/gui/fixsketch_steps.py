# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shared steps for the fixsketch_* scenarios (Luca, 2026-10-16: "sketching on an edited
object will revert it to a previous state, making it impossible to sketch on edited
faces"). Kept outside scenarios/ because every file there is run as a scenario.

Fusion shows and builds on the design as it is at the end of the timeline (at the marker)
while a new sketch is open, also when the sketch sits on a face the first extrude made and
later steps changed; editing a sketch from the timeline shows the design as it is at the
sketch's place (the steps before it). FreeCAD showed the step the sketch hangs on instead,
and a PartDesign body shows one step at a time: the part jumped back to that early step.

Everything acts like a person: Create Sketch in the ribbon, a click on the face, C and two
clicks for a circle, Finish Sketch, E, the distance, OK, a double-click in the timeline.
"""

import math

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import bodies_steps as bst
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import sketch_input as si

V = App.Vector


def close(a, c, tol=1e-6):
    return abs(a - c) <= tol * max(1.0, abs(c))


def one_mm_grid():
    """Clicks below land on whole millimetres (the default grid snaps to 2 mm)."""
    from sciforge import grid_ui

    grid_ui.put("Subdivisions", 10)
    grid_ui.apply_subdivisions()


def body_of(obj):
    parent = obj.getParentGeoFeatureGroup() if obj is not None else None
    return parent if parent is not None and parent.TypeId == "PartDesign::Body" else None


def shown_steps(body):
    """The solid steps of `body` drawn in the 3D view (PartDesign draws one at a time)."""
    if body is None:
        return []
    return [
        o.Name
        for o in body.Group
        if o.isDerivedFrom("PartDesign::Feature")
        and o.ViewObject is not None
        and o.ViewObject.Visibility
    ]


def volume(body):
    try:
        return body.Shape.Volume if body is not None and not body.Shape.isNull() else 0.0
    except Exception:
        return 0.0


def solids(body):
    try:
        return len(body.Shape.Solids)
    except Exception:
        return 0


def obj(name):
    return App.ActiveDocument.getObject(name) if name and App.ActiveDocument else None


def design_kept(where, state, body=None):
    """The checks of the bug: the body still draws its newest step (the Tip, every edit),
    its marker did not move and the part did not change."""
    body = body or obj(state.get("body"))
    if body is None:
        h.check("%s: the body exists" % where, False)
        return
    h.check(
        "%s: the part is drawn as it is now (%s), not as an earlier step"
        % (where, state.get("tip")),
        shown_steps(body) == [state.get("tip")],
        shown_steps(body),
    )
    h.check(
        "%s: the history marker stayed at %s" % (where, state.get("tip")),
        body.Tip is not None and body.Tip.Name == state.get("tip"),
        body.Tip and body.Tip.Name,
    )
    h.check(
        "%s: the part did not change" % where,
        close(volume(body), state.get("volume", -1.0)),
        (volume(body), state.get("volume")),
    )


def remember(state, body=None):
    """Note the body, its Tip and volume (what must stay while sketching)."""
    body = body or h.body()
    state["body"] = body.Name if body is not None else None
    state["tip"] = body.Tip.Name if body is not None and body.Tip is not None else None
    state["volume"] = volume(body)


def sketch_on(tag, point, state, support=None, body_after=None):
    """Steps: Create Sketch, click `point` on the part. While the sketch is open the part
    is drawn as it is now. `support`: (step name or a function of state, why) the sketch
    must hang on; `body_after`: a function giving the body the sketch goes in (another
    body's face)."""

    def create():
        h.click_empty()
        h.fit()
        if body_after is None:
            remember(state)
        h.ribbon("Create Sketch")

    def pick():
        pl.click_on_plane(point)

    def opened():
        sk = h.in_sketch()
        h.check("%s: the sketch opens on the face" % tag, sk is not None)
        if sk is None:
            return
        state["sketch"] = sk.Name
        if body_after is not None:
            remember(state, body_after())
        h.check(
            "%s: the sketch is in the clicked body" % tag,
            body_of(sk) is not None and body_of(sk).Name == state["body"],
            body_of(sk) and body_of(sk).Name,
        )
        target = sk.AttachmentSupport[0][0] if sk.AttachmentSupport else None
        state["support"] = target.Name if target is not None else None
        if support is not None:
            want, why = support
            want = want(state) if callable(want) else want
            h.check(
                "%s: the sketch hangs on %s (%s)" % (tag, want, why),
                state["support"] == want,
                state["support"],
            )
        design_kept("%s, sketch open" % tag, state)
        h.shot("%s-sketching" % tag)

    steps = [create, pick, opened]
    for step in steps:
        step.__name__ = "%s_%s" % (tag, step.__name__)
    return steps


def circle(tag, centre, radius, state, rim=None):
    """Steps: C, click the centre, click a point `radius` away (along X, or `rim`), Esc.
    The drawn circle is noted (state["r"], state["centre"]: measured, global).
    The sketch grid follows the zoom (1, 2, 5 or 10 mm) and FreeCAD snaps a coordinate
    within a fifth of it to a grid line: every coordinate clicked (in the sketch, whole
    millimetres) ends in 0, 3, 5 or 7, which no grid size moves."""

    def key():
        state["circles"] = len(si.circles(obj(state["sketch"]), construction=False))
        h.press("c")

    def centre_click():
        si.click(centre)

    def rim_click():
        si.click(rim if rim is not None else centre + V(radius, 0, 0))

    def drawn():
        h.press(QtCore.Qt.Key_Escape)
        sk = obj(state["sketch"])
        found = si.circles(sk, construction=False)
        ok = h.check(
            "%s: one circle drawn" % tag,
            len(found) == state["circles"] + 1,
            [(i, c.Radius) for i, c in found],
        )
        if not ok:
            return
        geo = found[-1][1]
        state["r"] = geo.Radius
        state["centre"] = sk.getGlobalPlacement().multVec(geo.Center)
        h.check("%s: radius %g" % (tag, radius), abs(geo.Radius - radius) < 0.6, geo.Radius)
        h.check(
            "%s: where it was clicked" % tag,
            (state["centre"] - centre).Length < 0.6,
            (state["centre"], centre),
        )
        design_kept("%s, circle drawn" % tag, state)

    steps = [key, centre_click, rim_click, drawn]
    for step in steps:
        step.__name__ = "%s_%s" % (tag, step.__name__)
    return steps


def finish_and_extrude(tag, distance, state):
    """Steps: Finish Sketch, E, the distance, OK. The boss joins the part as it is now: a
    step on the Tip that was shown (every edit kept), one solid, volume + pi r^2 d."""

    def finish():
        h.ribbon("Finish Sketch")

    def extrude():
        h.check("%s: the sketch is closed" % tag, h.in_sketch() is None)
        design_kept("%s, sketch finished" % tag, state)
        h.fit()
        h.press("e")

    def typed():
        from sciforge import extrude_ui

        p = extrude_ui.ExtrudePanel.last
        if h.check("%s: Extrude took the circle" % tag, p is not None and len(p.profiles) == 1):
            ui.type_into(p.distance.widget, "%g" % distance)

    def ok():
        h.task_button("OK")

    def made():
        body = obj(state["body"])
        boss = math.pi * state.get("r", 0.0) ** 2 * distance
        expect = state["volume"] + boss
        h.check(
            "%s: the boss joins the part as it is now" % tag,
            close(volume(body), expect),
            (volume(body), expect),
        )
        h.check("%s: one solid" % tag, solids(body) == 1, solids(body))
        tip = body.Tip
        base = getattr(tip, "BaseFeature", None)
        h.check(
            "%s: the extrude builds on %s (every edit)" % (tag, state["tip"]),
            base is not None and base.Name == state["tip"],
            base and base.Name,
        )
        h.check("%s: the part is drawn with the boss" % tag, shown_steps(body) == [tip.Name])
        state["boss_" + tag] = tip.Name
        state["sketch_" + tag] = state["sketch"]
        state["before_" + tag] = state["tip"]
        h.shot("%s-boss" % tag)
        remember(state, body)

    steps = [finish, extrude, typed, ok, made]
    for step in steps:
        step.__name__ = "%s_%s" % (tag, step.__name__)
    return steps


def edit_later(tag, of, state):
    """Steps: double-click the sketch of path `of` in the timeline. Fusion shows the design
    as it is at the sketch's place: the step before the sketch (every edit made before it),
    without the boss made from it. Finish Sketch: everything is drawn again, unchanged."""

    def edit():
        h.click_empty()
        remember(state)
        bst.timeline_double_click(obj(state["sketch_" + of]))

    def editing():
        sk = h.in_sketch()
        h.check(
            "%s: the sketch opens from the timeline" % tag,
            sk is not None and sk.Name == state["sketch_" + of],
            sk and sk.Name,
        )
        body = obj(state["body"])
        before = state["before_" + of]
        h.check(
            "%s: the design is drawn as it is at the sketch (%s, not the first extrude)"
            % (tag, before),
            shown_steps(body) == [before],
            shown_steps(body),
        )
        h.check("%s: the marker did not move" % tag, body.Tip.Name == state["tip"])
        h.shot("%s-editing" % tag)

    def finish():
        h.ribbon("Finish Sketch")

    def back():
        h.check("%s: the sketch is closed" % tag, h.in_sketch() is None)
        design_kept("%s, after the edit" % tag, state)

    steps = [edit, editing, finish, back]
    for step in steps:
        step.__name__ = "%s_%s" % (tag, step.__name__)
    return steps


def undo_redo(tag, of, state):
    """Steps: Ctrl+Z takes the boss of path `of` back (the part as it was before it, drawn
    with every edit), Ctrl+Y brings it back."""

    def undo():
        remember(state)
        bst.undo()

    def undone():
        body = obj(state["body"])
        before = state["before_" + of]
        h.check(
            "%s: Ctrl+Z: the boss is gone" % tag,
            obj(state["boss_" + of]) is None,
            state["boss_" + of],
        )
        h.check(
            "%s: Ctrl+Z: the part is drawn with every edit (%s)" % (tag, before),
            shown_steps(body) == [before] and body.Tip.Name == before,
            (shown_steps(body), body.Tip and body.Tip.Name),
        )

    def redo():
        bst.redo()

    def redone():
        body = obj(state["body"])
        h.check(
            "%s: Ctrl+Y: the boss is back" % tag,
            close(volume(body), state["volume"]),
            (volume(body), state["volume"]),
        )
        h.check(
            "%s: Ctrl+Y: drawn with the boss" % tag,
            shown_steps(body) == [state["tip"]],
            shown_steps(body),
        )

    steps = [undo, h.idle_step("%s_wait_undo" % tag), undone, redo]
    steps += [h.idle_step("%s_wait_redo" % tag), redone]
    for step in (undo, undone, redo, redone):
        step.__name__ = "%s_%s" % (tag, step.__name__)
    return steps


def no_errors_in_design(where):
    bad = [o.Name for o in App.ActiveDocument.Objects if "Invalid" in o.State]
    h.check("%s: nothing in error" % where, not bad, bad)
