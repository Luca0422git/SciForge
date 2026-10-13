# SPDX-License-Identifier: LGPL-2.1-or-later
"""Every joint type on two plain bodies, only real input (docs/sciforge/parity/joints.md).

Plate = 0..40 x 0..30 x 10, Block = 50..70 x 0..10 x 20 (Extrude New Body). Every round: J,
click the block's top, click the plate's top (the block lands upside down on the plate), the
Motion tab, the Type; the new motion plays once and comes back; the round's own settings; the
Animate button plays the motion while the test watches where the two joint origins go; OK
(one "<Type> 1" in the timeline and the browser); Ctrl+Z (the joint, the ground and the move
all go in one step).

  R0 Rigid: no motion (no Animate button, no axis); FreeCAD's Fixed joint.
  R1 Slider, Slide axis X, limits -5 .. 15 mm: the block slides along X only, never turns,
     stays inside the limits.
  R2 Cylindrical: turns about and slides along the joint axis (Z).
  R3 Pin-Slot (slot along X): the pin turns about Z and slides along the slot, always in
     the plate's plane; its hidden slot joint goes with the undo.
  R4 Planar: slides anywhere in the plate's plane and turns about its normal, never lifts.
  R5 Ball: turns any way about the joint origin, which never moves.
  R6 Revolute, angle limits -30 .. 45 deg, Rest 10: swings inside the limits only; OK puts it
     at its rest (10 deg); a Rest outside the limits is refused with a message.
"""

import FreeCAD as App

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import joints_steps as j
from SciForgeTests.gui import timeline_input as t

V = App.Vector
state = {}
TIGHT = 1e-5


def jm():
    return j.joints_module()


def the_joint():
    found = j.joint_list()
    return found[0] if found else None


def round_steps(tag, label, kind, freecad_type, setup=(), motion=None, after_ok=None):
    """The steps of one round (see the module text)."""

    def joined():
        p = j.panel()
        h.check("%s: one joint made" % tag, len(j.joint_list()) == 1, len(j.joint_list()))
        j.block_box("%s: block on the plate" % tag, j.ON_PLATE)
        h.check("%s: dialog still open" % tag, p is not None and p.title == "Joint")

    def choose():
        p = j.panel()
        if p is None:
            return
        j.click_tab(p, "Motion")
        if label != "Rigid":
            j.choose_type(p, label)

    choose.wait_ms = 2600  # the new motion plays once (1.8 s) and comes back

    def typed():
        p = j.panel()
        joint = the_joint()
        if p is None or joint is None:
            h.check("%s: dialog and joint" % tag, False)
            return
        h.check(
            "%s: FreeCAD type %s" % (tag, freecad_type),
            joint.JointType == freecad_type,
            joint.JointType,
        )
        h.check(
            "%s: Fusion type %s" % (tag, kind),
            jm().fusion_type(joint) == kind,
            jm().fusion_type(joint),
        )
        h.check("%s: label %s 1" % (tag, label), joint.Label == "%s 1" % label, joint.Label)
        h.check("%s: the preview came back" % tag, p.animator is None, p.animator)
        j.block_box("%s: block back on the plate" % tag, j.ON_PLATE)
        h.check("%s: Animate shown" % tag, p.animate.isVisible() == (kind != "rigid"))
        state[tag + "_plc"] = App.Placement(j.block().Placement)

    def animate():
        p = j.panel()
        joint = the_joint()
        if p is None or joint is None or kind == "rigid":
            return
        b.click_widget(p.animate)
        h.check("%s: Animate pressed" % tag, p.animate.isChecked() and p.animator is not None)
        state[tag] = j.sample(joint, j.block(), 2.1)
        b.click_widget(p.animate)  # press again: it stops and puts the block back

    def animated():
        p = j.panel()
        if kind == "rigid" or p is None:
            return
        samples = state.get(tag) or []
        h.check("%s: watched the motion" % tag, len(samples) >= 5, len(samples))
        h.check("%s: Animate stopped" % tag, not p.animate.isChecked() and p.animator is None)
        j.block_box("%s: block back where it was" % tag, j.ON_PLATE)
        if samples and motion is not None:
            motion(samples)

    def ok():
        j.ok()

    def done():
        j.no_dialog("%s OK" % tag)
        joint = the_joint()
        h.check("%s: one joint after OK" % tag, joint is not None and len(j.joint_list()) == 1)
        if joint is None:
            return
        h.check("%s: timeline shows %s 1" % (tag, label), "%s 1" % label in t.titles(), t.titles())
        h.check("%s: browser lists it" % tag, "%s 1" % label in j.row_labels(), j.row_labels())
        h.check("%s: the solver is happy" % tag, jm().solve(App.ActiveDocument) == 0)
        if after_ok is not None:
            after_ok(joint)

    def undo():
        s.undo()

    def undone():
        h.check(
            "%s: undo removed the joint" % tag,
            not j.joint_list(),
            [x.Label for x in j.joint_list()],
        )
        j.block_box("%s: undo put the block back" % tag, j.HOME)
        h.check("%s: undo removed the ground" % tag, not jm().is_grounded(j.plate()))
        helpers = [o.Name for o in App.ActiveDocument.Objects if jm().is_helper(o)]
        h.check("%s: no hidden helper left" % tag, not helpers, helpers)

    steps = j.pick_pair(tag) + [joined, choose, typed] + list(setup)
    steps += [animate, animated, ok, done, undo, undone]
    for step in steps:
        if not step.__name__.startswith(tag):
            step.__name__ = "%s_%s" % (tag, step.__name__)
    return steps


# -- checks of the watched motion -----------------------------------------------------------------
def every(tag, what, samples, test):
    bad = [i for i, r in enumerate(samples) if not test(r)]
    return h.check("%s: %s" % (tag, what), not bad, ("bad samples", bad[:5], len(samples)))


def slider_motion(samples):
    plc0 = state["r1_plc"]
    every(
        "r1",
        "no turn: the joint origins keep their axes",
        samples,
        lambda r: j.tilt(j.z_of(r["j1"]), j.z_of(r["j2"])) < 1e-3
        and j.tilt(j.x_of(r["j1"]), j.x_of(r["j2"])) < 1e-3,
    )
    every(
        "r1",
        "slides on the joint axis only",
        samples,
        lambda r: j.along(j.offset_of(r), j.z_of(r["j2"]), TIGHT),
    )
    every(
        "r1",
        "the block moves along X only",
        samples,
        lambda r: abs(r["plc"].Base.y - plc0.Base.y) < TIGHT
        and abs(r["plc"].Base.z - plc0.Base.z) < TIGHT
        and r["plc"].Rotation.isSame(plc0.Rotation, 1e-9),
    )
    slides = [r["slide"] for r in samples]
    h.check(
        "r1: inside the limits -5 .. 15",
        min(slides) >= -5 - 1e-6 and max(slides) <= 15 + 1e-6,
        (min(slides), max(slides)),
    )
    h.check(
        "r1: travels across the range",
        max(slides) > 8 and min(slides) < -2.5,
        (min(slides), max(slides)),
    )


def cylindrical_motion(samples):
    every(
        "r2",
        "axes stay parallel",
        samples,
        lambda r: j.tilt(j.z_of(r["j1"]), j.z_of(r["j2"])) < 1e-3,
    )
    every(
        "r2",
        "on the joint axis",
        samples,
        lambda r: j.along(j.offset_of(r), j.z_of(r["j2"]), TIGHT),
    )
    h.check(
        "r2: turns",
        j.spread(r["angle"] for r in samples) > 60,
        j.spread(r["angle"] for r in samples),
    )
    h.check(
        "r2: slides",
        j.spread(r["slide"] for r in samples) > 4,
        j.spread(r["slide"] for r in samples),
    )


def pinslot_motion(samples):
    every(
        "r3",
        "pin axis stays upright",
        samples,
        lambda r: j.tilt(j.z_of(r["j1"]), j.z_of(r["j2"])) < 1e-3,
    )
    every(
        "r3",
        "stays in the plate's plane",
        samples,
        lambda r: abs(j.offset_of(r).dot(j.z_of(r["j2"]))) < TIGHT,
    )
    every(
        "r3",
        "slides along the slot (X) only",
        samples,
        lambda r: j.along(j.offset_of(r), j.x_of(r["j2"]), TIGHT),
    )
    every("r3", "the block stays on the plate", samples, lambda r: abs(r["box"].ZMin - 10) < 1e-4)
    h.check(
        "r3: turns",
        j.spread(r["angle"] for r in samples) > 60,
        j.spread(r["angle"] for r in samples),
    )
    h.check(
        "r3: slides",
        j.spread(r["slide"] for r in samples) > 4,
        j.spread(r["slide"] for r in samples),
    )
    joint = the_joint()
    helpers = jm().helpers_of(joint) if joint is not None else []
    h.check("r3: the hidden slot joint is there", len(helpers) == 1, helpers)


def planar_motion(samples):
    every(
        "r4",
        "normals stay parallel",
        samples,
        lambda r: j.tilt(j.z_of(r["j1"]), j.z_of(r["j2"])) < 1e-3,
    )
    every(
        "r4",
        "stays in the plane",
        samples,
        lambda r: abs(j.offset_of(r).dot(j.z_of(r["j2"]))) < TIGHT,
    )
    every("r4", "never lifts off the plate", samples, lambda r: abs(r["box"].ZMin - 10) < 1e-4)
    h.check(
        "r4: slides in X",
        j.spread(r["plc"].Base.x for r in samples) > 4,
        j.spread(r["plc"].Base.x for r in samples),
    )
    h.check(
        "r4: and in Y",
        j.spread(r["plc"].Base.y for r in samples) > 2,
        j.spread(r["plc"].Base.y for r in samples),
    )


def ball_motion(samples):
    every(
        "r5",
        "the ball's centre never moves",
        samples,
        lambda r: j.offset_of(r).Length < TIGHT and (r["j2"].Base - V(20, 15, 10)).Length < TIGHT,
    )
    tilts = [j.tilt(j.z_of(r["j1"]), j.z_of(r["j2"])) for r in samples]
    h.check("r5: tilts any way", max(tilts) > 8, max(tilts))


def revolute_motion(samples):
    every(
        "r6",
        "turns about the joint axis only",
        samples,
        lambda r: j.offset_of(r).Length < TIGHT and j.tilt(j.z_of(r["j1"]), j.z_of(r["j2"])) < 1e-3,
    )
    angles = [r["angle"] for r in samples]
    h.check(
        "r6: inside the limits -30 .. 45",
        min(angles) >= -30 - 1e-6 and max(angles) <= 45 + 1e-6,
        (min(angles), max(angles)),
    )
    h.check(
        "r6: swings across the range",
        max(angles) > 27 and min(angles) < -18,
        (min(angles), max(angles)),
    )


# -- the rounds' own settings ---------------------------------------------------------------------
def r0_no_motion_rows():
    p = j.panel()
    h.check(
        "r0: no axis box for Rigid", not any(box.isVisible() for box, _c in p.axis_boxes.values())
    )
    h.check("r0: no limits for Rigid", not p.angle_limits.rows["min"][0].isVisible())


def r1_axis_x():
    p = j.panel()
    b.choose(p.axis_boxes["Slide"][0], "X Axis")


def r1_limits():
    p = j.panel()
    lim = p.slide_limits.rows
    s.toggle(lim["min"][0])
    s.type_value(lim["min"][1].widget, "-5")
    s.toggle(lim["max"][0])
    s.type_value(lim["max"][1].widget, "15")


def r1_set():
    joint = the_joint()
    h.check("r1: slide axis X stored", jm()._json(joint, jm().PROPS["axes"]).get("slide") == "x")
    lim = jm().limits(joint)["slide"]
    h.check("r1: limits stored", lim["min"] == -5 and lim["max"] == 15, lim)
    h.check("r1: FreeCAD's own limits on", joint.EnableLengthMin and joint.EnableLengthMax)
    j.block_box("r1: block not moved by the settings", j.ON_PLATE)


def r1_after(joint):
    lim = jm().limits(joint)["slide"]
    h.check("r1: limits kept after OK", lim["min"] == -5 and lim["max"] == 15, lim)


def r6_limits():
    p = j.panel()
    lim = p.angle_limits.rows
    s.toggle(lim["min"][0])
    s.type_value(lim["min"][1].widget, "-30")
    s.toggle(lim["max"][0])
    s.type_value(lim["max"][1].widget, "45")


def r6_bad_rest():
    p = j.panel()
    lim = p.angle_limits.rows
    s.toggle(lim["rest"][0])
    s.type_value(lim["rest"][1].widget, "60")


def r6_refused():
    p = j.panel()
    h.check(
        "r6: a rest outside the limits is refused",
        "rest" in p.message.text().lower(),
        p.message.text(),
    )


def r6_good_rest():
    p = j.panel()
    s.type_value(p.angle_limits.rows["rest"][1].widget, "10")


def r6_set():
    p = j.panel()
    h.check("r6: the message went", not p.message.text(), p.message.text())
    lim = jm().limits(the_joint())["angle"]
    h.check("r6: limits stored", lim["min"] == -30 and lim["max"] == 45 and lim["rest"] == 10, lim)
    j.block_box("r6: still at 0 until OK", j.ON_PLATE)


def r6_after(joint):
    angle, _slide = jm().value(joint)
    h.check("r6: OK put the joint at its rest (10 deg)", abs(angle - 10) < 1e-4, angle)


def r0_after(joint):
    angle, slide = jm().value(joint)
    h.check(
        "r0: rigid: the joint stays at 0", abs(angle) < 1e-6 and abs(slide) < 1e-6, (angle, slide)
    )
    h.check("r0: no hidden helper", not jm().helpers_of(joint))


steps = [s.new_design("JointTypes")] + j.two_boxes()
steps += round_steps("r0", "Rigid", "rigid", "Fixed", setup=[r0_no_motion_rows], after_ok=r0_after)
steps += round_steps(
    "r1",
    "Slider",
    "slider",
    "Slider",
    setup=[r1_axis_x, r1_limits, r1_set],
    motion=slider_motion,
    after_ok=r1_after,
)
steps += round_steps("r2", "Cylindrical", "cylindrical", "Cylindrical", motion=cylindrical_motion)
steps += round_steps("r3", "Pin-Slot", "pinslot", "Distance", motion=pinslot_motion)
steps += round_steps("r4", "Planar", "planar", "Distance", motion=planar_motion)
steps += round_steps("r5", "Ball", "ball", "Ball", motion=ball_motion)
steps += round_steps(
    "r6",
    "Revolute",
    "revolute",
    "Revolute",
    setup=[r6_limits, r6_bad_rest, r6_refused, r6_good_rest, r6_set],
    motion=revolute_motion,
    after_ok=r6_after,
)

h.run("joints_types", steps)
