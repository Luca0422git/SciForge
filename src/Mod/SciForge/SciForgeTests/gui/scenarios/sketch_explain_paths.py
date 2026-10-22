# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sketch constraints that explain themselves, whatever the way the constraint came in
(fixes of the review of 2026-10-22, docs/sciforge/sessions/2026-10-22-fix-sketch.md), with real
input. The sketch (built by script in one undo step "Setup": the clicks are what is tested):
a 40 x 20 rectangle centred on the origin (its corners symmetric about it, fully constrained),
a slanted line from (60, 0) to (80, 30) whose horizontal size is 20 mm, and a level line ending
on an arc whose centre and radius are fixed.

A  Preselect: click the slanted line, then CONSTRAINTS > Horizontal/Vertical (FreeCAD's step
   "Add horizontal/vertical constraint"): refused, "Vertical: not added, it conflicts with the
   20 mm dimension"; nothing is left to Redo.
B  Two points: Horizontal/Vertical, click both ends of the slanted line ("Add vertical
   alignment"): refused the same way.
C  Tangent on the level line and the arc whose ends are joined (FreeCAD swaps the Coincident
   for an end-to-end Tangent: the count does not grow): refused; the Coincident is back.
D  Symmetry of the rectangle's bottom ends about the Y axis: FreeCAD flags the old Horizontal
   and Vertical as redundant, not the new one: refused, they are named; the sketch solves.
E  Coincident of a corner and the origin: the solver finds no solution and lists nothing:
   refused, "it conflicts with the Symmetry about the origin"; the sketch solves.
F  Ctrl+Y after the refusals: nothing to redo, nothing changes.
G  The Sketch Palette says "Redundant constraints" (not "Fully constrained") for a sketch with
   a redundant constraint; a fully constrained sketch with a redundant constraint (FreeCAD 1.1
   marks it as an error) gets no padlock, a clean one does.
H  A big sketch (a strip of 60 squares, 181 lines): Parallel on square 2's lines, which the
   two Horizontals already make so: refused within the time limit, naming a Horizontal and no
   dimension.
"""

import time

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import sketch_tools_steps as st

V = App.Vector
s = st.s
TIMES = {}


def sk():
    return st.sketch()


def told():
    from sciforge import commands

    return commands._TOLD.get("msg") or ""


def freedom_text():
    from PySide import QtWidgets

    pal = si.palette()
    label = pal.findChild(QtWidgets.QLabel, "SciForgePaletteFreedom") if pal else None
    return label.text() if label is not None else None


def state(tag):
    d = App.ActiveDocument
    c = sk().Constraints
    print(
        "[SciForge] paths %s: n=%d conflicting=%s redundant=%s undo=%s redo=%s told=%r"
        % (
            tag,
            len(c),
            list(sk().ConflictingConstraints),
            list(sk().RedundantConstraints),
            d.UndoNames[:3],
            d.RedoNames[:3],
            told(),
        ),
        flush=True,
    )


def setup():
    import math

    import Part
    import Sketcher

    from sciforge import commands, sketch_explain

    for name in ("check_new", "redundant_culprits"):  # timed (H)
        original = getattr(sketch_explain, name)

        def timed(*args, _original=original, _name=name, **kwargs):
            started = time.time()
            try:
                return _original(*args, **kwargs)
            finally:
                TIMES.setdefault(_name, []).append(time.time() - started)

        setattr(sketch_explain, name, timed)
    s0 = sk()
    d = App.ActiveDocument
    d.openTransaction("Setup")
    pts = [V(-20, -10, 0), V(20, -10, 0), V(20, 10, 0), V(-20, 10, 0)]
    for i in range(4):
        s0.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))
    cons = [Sketcher.Constraint("Coincident", i, 2, (i + 1) % 4, 1) for i in range(4)]
    cons += [
        Sketcher.Constraint("Horizontal", 0),
        Sketcher.Constraint("Horizontal", 2),
        Sketcher.Constraint("Vertical", 1),
        Sketcher.Constraint("Vertical", 3),
        Sketcher.Constraint("DistanceX", 0, 1, 0, 2, 40),
        Sketcher.Constraint("DistanceY", 1, 1, 1, 2, 20),
        Sketcher.Constraint("Symmetric", 0, 1, 1, 2, -1, 1),
    ]
    slant = s0.addGeometry(Part.LineSegment(V(60, 0, 0), V(80, 30, 0)))
    cons.append(Sketcher.Constraint("DistanceX", slant, 1, slant, 2, 20.0))
    line = s0.addGeometry(
        Part.LineSegment(V(60, 45, 0), V(85 - 10 * math.cos(math.pi / 6), 45, 0))
    )
    arc = s0.addGeometry(
        Part.ArcOfCircle(
            Part.Circle(V(85, 50, 0), V(0, 0, 1), 10), 7 * math.pi / 6, 11 * math.pi / 6
        )
    )
    cons += [
        Sketcher.Constraint("Horizontal", line),
        Sketcher.Constraint("DistanceX", -1, 1, line, 1, 60.0),
        Sketcher.Constraint("DistanceY", -1, 1, line, 1, 45.0),
        Sketcher.Constraint("Coincident", line, 2, arc, 1),
        Sketcher.Constraint("DistanceX", -1, 1, arc, 3, 85.0),
        Sketcher.Constraint("DistanceY", -1, 1, arc, 3, 50.0),
        Sketcher.Constraint("Radius", arc, 10.0),
    ]
    s0.addConstraint(cons)
    s0.solve()
    d.commitTransaction()
    d.recompute()
    Gui.SendMsgToActiveView("ViewFit")
    commands._TOLD["msg"] = ""
    state("setup")
    h.check("setup: the sketch solves", s0.solve() == 0 and not s0.RedundantConstraints)


setup.wait_ms = 1500


def expect_refused(tag, title, words):
    state(tag)
    text = told()
    h.check("%s: not added" % tag, len(sk().Constraints) == s["count"], len(sk().Constraints))
    h.check("%s: the sketch solves cleanly" % tag, sk().solve() == 0)
    h.check(
        "%s: nothing in conflict or redundant" % tag,
        not sk().ConflictingConstraints and not sk().RedundantConstraints,
    )
    h.check("%s: the message" % tag, text.startswith("%s: not added" % title), text)
    for word in words:
        h.check("%s: the message names %s" % (tag, word), word in text, text)
    h.check("%s: Undo as before (Setup on top)" % tag, App.ActiveDocument.UndoNames[:1] == ["Setup"])
    h.check(
        "%s: nothing left to Redo" % tag,
        not App.ActiveDocument.RedoNames,
        App.ActiveDocument.RedoNames,
    )


def start(tool):
    def step():
        from sciforge import commands

        st.esc()
        st.esc()
        commands._TOLD["msg"] = ""
        s["count"] = len(sk().Constraints)
        if tool:
            si.menu_item("CONSTRAINTS", tool)

    step.__name__ = "start_" + (tool or "select").replace("/", "_")
    return step


def clicker(point, name):
    def step():
        st.click(point)

    step.__name__ = name
    return step


def checker(tag, title, words):
    def step():
        expect_refused(tag, title, words)

    step.__name__ = "check_" + tag
    step.wait_ms = 1500
    return step


# A: the line first, then Horizontal/Vertical
def a_hv():
    si.menu_item("CONSTRAINTS", "Horizontal/Vertical")


# C: the swap leaves the join
def c_join_back():
    joins = [c for c in sk().Constraints if c.Type == "Coincident" and c.First == 5]
    h.check("C: the Coincident of the line and the arc is back", len(joins) == 1)
    h.check("C: no Tangent left", not [c for c in sk().Constraints if c.Type == "Tangent"])


# F: Ctrl+Y
def f_redo():
    st.esc()
    st.esc()
    s["count"] = len(sk().Constraints)
    st.redo()


def f_check():
    h.check("F: Ctrl+Y adds nothing", len(sk().Constraints) == s["count"])
    h.check("F: no conflict", not sk().ConflictingConstraints)


f_check.wait_ms = 1200


# G: palette and padlock
def g_redundant():
    import Sketcher

    d = App.ActiveDocument
    d.openTransaction("Script")
    sk().addConstraint(Sketcher.Constraint("Horizontal", 5))  # the level line, again
    sk().solve()
    d.commitTransaction()


def g_palette():
    state("redundant")
    h.check("G: the palette says so", freedom_text() == "Redundant constraints", freedom_text())
    st.undo()


g_palette.wait_ms = 1200


def g_padlock():
    import Part
    import Sketcher

    from sciforge import sketch_explain

    h.check("G: after Undo the palette counts again", "left to define" in (freedom_text() or ""))
    d = App.ActiveDocument
    out = {}
    for name, extra in (("FullOk", False), ("FullRed", True)):
        other = d.addObject("Sketcher::SketchObject", name)
        pts = [V(0, 0, 0), V(40, 0, 0), V(40, 20, 0), V(0, 20, 0)]
        for i in range(4):
            other.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))
        cons = [Sketcher.Constraint("Coincident", i, 2, (i + 1) % 4, 1) for i in range(4)]
        cons += [
            Sketcher.Constraint("Horizontal", 0),
            Sketcher.Constraint("Horizontal", 2),
            Sketcher.Constraint("Vertical", 1),
            Sketcher.Constraint("Vertical", 3),
            Sketcher.Constraint("DistanceX", 0, 1, 0, 2, 40),
            Sketcher.Constraint("DistanceY", 1, 1, 1, 2, 20),
            Sketcher.Constraint("Coincident", 0, 1, -1, 1),
        ]
        if extra:
            cons.append(Sketcher.Constraint("Parallel", 0, 2))
        other.addConstraint(cons)
        other.Visibility = False
        other.recompute()
        out[name] = (sketch_explain.fully_constrained(other), list(other.State))
    h.check("G: a clean fully constrained sketch has the padlock", out["FullOk"][0], out)
    h.check("G: no padlock with a redundant constraint", not out["FullRed"][0], out)
    for name in out:
        d.removeObject(name)


# H: a big sketch
N = 60
Y0 = -100.0


def h_setup():
    import Part
    import Sketcher

    s0 = sk()
    d = App.ActiveDocument
    d.openTransaction("Big")
    first = s0.GeometryCount
    geo = [Part.LineSegment(V(10 * i, Y0, 0), V(10 * i + 10, Y0, 0)) for i in range(N)]
    geo += [Part.LineSegment(V(10 * i, Y0 + 10, 0), V(10 * i + 10, Y0 + 10, 0)) for i in range(N)]
    geo += [Part.LineSegment(V(10 * i, Y0, 0), V(10 * i, Y0 + 10, 0)) for i in range(N + 1)]
    s0.addGeometry(geo)

    def bottom(i):
        return first + i

    def top(i):
        return first + N + i

    def side(i):
        return first + 2 * N + i

    cons = []
    for i in range(N):
        cons += [
            Sketcher.Constraint("Horizontal", bottom(i)),
            Sketcher.Constraint("Horizontal", top(i)),
            Sketcher.Constraint("Coincident", bottom(i), 1, side(i), 1),
            Sketcher.Constraint("Coincident", top(i), 1, side(i), 2),
            Sketcher.Constraint("Coincident", bottom(i), 2, side(i + 1), 1),
            Sketcher.Constraint("Coincident", top(i), 2, side(i + 1), 2),
            Sketcher.Constraint("DistanceX", bottom(i), 1, bottom(i), 2, 10),
        ]
    cons += [Sketcher.Constraint("Vertical", side(i)) for i in range(N + 1)]
    cons += [
        Sketcher.Constraint("DistanceY", side(0), 1, side(0), 2, 10),
        Sketcher.Constraint("DistanceX", -1, 1, bottom(0), 1, 10),
        Sketcher.Constraint("DistanceY", bottom(0), 1, -1, 1, -Y0),
    ]
    s0.addConstraint(cons)
    s0.solve()
    d.commitTransaction()
    d.recompute()
    view = Gui.ActiveDocument.ActiveView
    view.viewTop()
    import pivy.coin as coin

    cam = view.getCameraNode()
    cam.position.setValue(coin.SbVec3f(25, Y0 + 5, 100))
    cam.height.setValue(40)
    h.check("H: the big sketch solves", s0.solve() == 0 and not s0.RedundantConstraints)


h_setup.wait_ms = 3000


def h_check():
    state("big")
    text = told()
    took = max(TIMES.get("check_new", [0.0]) or [0.0])
    print("[SciForge] paths check_new times %s" % TIMES.get("check_new"), flush=True)
    h.check("H: not added", len(sk().Constraints) == s["count"], len(sk().Constraints))
    h.check("H: refused", text.startswith("Parallel: not added"), text)
    h.check("H: names a Horizontal", "Horizontal on Line" in text, text)
    h.check("H: and no dimension", "dimension" not in text, text)
    # one solve of this sketch takes about 0.2 s here: the check stays within about 1.2 s
    # (its own solve plus at most PROBE_SECONDS), with room for a loaded machine
    h.check("H: within the time limit", took < 2.0, took)


h_check.wait_ms = 6000


h.run(
    "sketch_explain_paths",
    st.start_steps("ExplainPaths")
    + [
        setup,
        start(None),
        clicker(V(70, 15, 0), "a_pick_line"),
        a_hv,
        checker("A", "Vertical", ["20 mm dimension"]),
        start("Horizontal/Vertical"),
        clicker(V(60, 0, 0), "b_p1"),
        clicker(V(80, 30, 0), "b_p2"),
        checker("B", "Vertical", ["20 mm dimension"]),
        start("Tangent"),
        clicker(V(66, 45, 0), "c_line"),
        clicker(V(85, 40, 0), "c_arc"),
        checker("C", "Tangent", []),
        c_join_back,
        start("Symmetry"),
        clicker(V(-20, -10, 0), "d_p1"),
        clicker(V(20, -10, 0), "d_p2"),
        clicker(V(0, 15, 0), "d_axis"),
        checker("D", "Symmetry", ["Horizontal on Line 1", "Vertical on Line 2"]),
        start("Coincident"),
        clicker(V(-20, -10, 0), "e_corner"),
        clicker(V(0, 0, 0), "e_origin"),
        checker("E", "Coincident", ["Symmetry about the origin"]),
        f_redo,
        f_check,
        g_redundant,
        g_palette,
        g_padlock,
        h_setup,
        start("Parallel"),
        clicker(V(15, Y0, 0), "h_bottom"),
        clicker(V(15, Y0 + 10, 0), "h_top"),
        h_check,
    ],
)
