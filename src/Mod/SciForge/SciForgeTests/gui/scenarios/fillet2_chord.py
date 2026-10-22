# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Radius Type Chord Length: the width of the round is given, and SciForge gives each
edge the radius that makes that chord on its own corner. One set holds a 90 degree edge and a
120 degree edge: the chord is measured on the finished part for both (3 mm), and the radii are
3 / sqrt(2) and 3. Only real input: F, clicks, the Radius Type drop-down, typing, dragging the
arrow, OK, edit from the timeline, Ctrl+Z / Ctrl+Y.

The part: a profile with corners of 90, 120 and 150 degrees, extruded 10 mm. The removed
cross-section of a round of radius R in a corner of angle g (the faces' normals turn by
t = 180 - g) is R^2 (cot(g / 2) - t / 2) (the kite between the corner, the two tangent points
and the centre, minus the sector)."""

import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import fillet2_steps as f2
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}
SLANT = V(40 - 10 * math.cos(math.radians(30)), 25, 0)  # (31.34, 25)
PROFILE = [V(0, 0, 0), V(40, 0, 0), V(40, 20, 0), SLANT, V(0, 25, 0)]
FRONT_TOP = V(20, 0, 10)
CORNER_120 = V(40, 20, 5)  # the vertical edge between the right face and the slanted one


def profile(sketch):
    import Part

    for a, c in zip(PROFILE, PROFILE[1:] + PROFILE[:1]):
        sketch.addGeometry(Part.LineSegment(a, c))
    App.ActiveDocument.recompute()


def spandrel(r, corner_deg):
    g = math.radians(corner_deg)
    t = math.pi - g
    return r * r * (1.0 / math.tan(g / 2.0) - t / 2.0)


def removed(chord):
    r90 = chord / math.sqrt(2.0)
    r120 = chord  # the normals turn 60 degrees: chord = 2 R sin 30 = R
    return 40 * spandrel(r90, 90) + 10 * spandrel(r120, 120)


def start():
    s["v0"] = h.solid_volume()
    Gui.Selection.clearSelection()
    h.fit()
    h.press("f")


def pick():
    h.click_edge(FRONT_TOP)


def pick_more():
    p = b.blend_panel()
    h.check("first edge picked", p is not None and len(p.refs) == 1, p and p.refs)
    h.click_edge(CORNER_120)


def choose_chord():
    p = b.blend_panel()
    h.check("both edges in one set", p is not None and len(p.refs) == 2, p and p.refs)
    if p:
        b.choose(p.radius_type, "Chord Length")


def chord_rows():
    p = b.blend_panel()
    if p is None:
        return
    h.check(
        "Chord Length shows its own box, not Radius",
        p.chord_field.widget.isVisible() and not p.radius.widget.isVisible(),
    )
    h.check("Chord Length makes it SciForge's step", f2.is_sets(p.target), p.target)
    b.type_into(p.chord_field.widget, "3")


def chord_3():
    p = b.blend_panel()
    v = h.solid_volume()
    expect = s["v0"] - removed(3)
    h.check("chord 3 on both corners (R 2.12 and R 3)", b.close(v, expect), (v, expect))
    c90 = f2.round_chord(length=40)
    c120 = f2.round_chord(length=10)
    h.check("measured chord on the 90 degree edge is 3 mm", c90 and abs(c90 - 3) < 1e-6, c90)
    h.check("measured chord on the 120 degree edge is 3 mm", c120 and abs(c120 - 3) < 1e-6, c120)
    radii = sorted(
        round(f.Surface.Radius, 6)
        for f in h.body().Shape.Faces
        if type(f.Surface).__name__ == "Cylinder"
    )
    h.check("radii 3/sqrt(2) and 3", radii == [round(3 / math.sqrt(2), 6), 3.0], radii)
    h.check(
        "the arrow sets the chord", p is not None and p.arrows and p.arrows[0][1]["what"] == "chord"
    )
    h.shot("1-chord")
    if p and p.arrows:
        s["c"] = p.chord_field.value()
        a, c = b.arrow_screen(p, 0, along=1.0)
        h.drag(a, c)


def dragged():
    p = b.blend_panel()
    c = p.spec["sets"][0]["chord"] if p else 0
    h.check("dragging the arrow grows the chord", c > s["c"] + 0.3, (s["c"], c))
    v = h.solid_volume()
    h.check("preview follows the dragged chord", b.close(v, s["v0"] - removed(c)), v)
    s["chord"] = c
    if p:
        b.type_into(p.chord_field.widget, "2")


def ok():
    h.task_button("OK")


def after_ok():
    v = h.solid_volume()
    h.check("kept: chord 2", b.close(v, s["v0"] - removed(2)), v)
    c90 = f2.round_chord(length=40)
    h.check("chord measured 2 after OK", c90 and abs(c90 - 2) < 1e-6, c90)
    steps = f2.steps()
    h.check("one step", len(steps) == 1)
    if steps:
        spec = f2.spec_of(steps[0])
        h.check(
            "the step keeps Chord Length (not a radius)",
            spec["sets"][0]["radius_type"] == "chord" and abs(spec["sets"][0]["chord"] - 2) < 1e-9,
            spec["sets"],
        )
    s["v"] = v
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def undone():
    h.check(
        "Ctrl+Z removes it",
        b.close(h.solid_volume(), s["v0"]) and not f2.steps(),
        (
            h.solid_volume(),
            s["v0"],
            [(o.Name, o.TypeId) for o in f2.steps()],
            App.ActiveDocument.UndoNames,
            App.ActiveDocument.RedoNames,
        ),
    )
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def redone():
    h.check("Ctrl+Y brings it back", b.close(h.solid_volume(), s["v"]))
    h.fit()
    b.timeline_double_click("Fillet 1", click_first=True)


def edit_open():
    p = b.blend_panel()
    h.check("edit opens the dialog", p is not None and not p.created)
    if p is None:
        return
    h.check(
        "Chord Length and 2 mm shown",
        p.radius_type.currentText() == "Chord Length" and abs(p.chord_field.value() - 2) < 1e-9,
        (p.radius_type.currentText(), p.chord_field.value()),
    )
    b.type_into(p.chord_field.widget, "100")


def too_big():
    """Luca, 2026-10-21: a chord past what fits is held at the largest that works (it was
    refused before)."""
    p = b.blend_panel()
    note = p.limit_label.text() if p and p.limit_label.isVisible() else ""
    chord = p.options.get("chord", 0) if p else 0
    h.check("a chord too big is held at the largest that fits", 2.0 < chord < 100.0, chord)
    h.check("and said", note == "100 mm does not fit: limited to %.2f mm" % chord, note)
    h.check("no error", p is not None and p.message.text() == "", p and p.message.text())
    h.press(QtCore.Qt.Key_Escape)


def end():
    h.check("Esc keeps the step as it was", b.close(h.solid_volume(), s["v"]))
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("no kernel errors", not f2.report_errors(), f2.report_errors())
    h.shot("2-end")


h.run(
    "fillet2_chord",
    b.box_steps("Chord", profile=profile)
    + [
        start,
        pick,
        pick_more,
        choose_chord,
        chord_rows,
        chord_3,
        dragged,
        ok,
        after_ok,
        undone,
        redone,
        edit_open,
        too_big,
        end,
    ],
)
