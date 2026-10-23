# SPDX-License-Identifier: LGPL-2.1-or-later
"""The dimension box and Change Parameters with a value the sketch cannot take (fixes of the
review of 2026-10-22, docs/sciforge/sessions/2026-10-22-fix-sketch.md), with real input.

The sketch: user parameter w = 30; R, a rectangle from (40, 20) to the origin; Sketch Dimension
on the top line, typed =w (30 wide); then (by script, one undo step) a construction diagonal
with a 36.06 mm dimension instead of the height. A diagonal shorter than the width cannot be.

A  Double-click the diagonal's dimension, type 10: the box stays open and says the value
   does not fit (not FreeCAD's "Invalid constraint index").
B  Type =w/2 (a formula FreeCAD can compute, a value the sketch cannot take): the same words,
   not "cannot be computed"; the sketch is not left marked as failed.
C  Type =foo*2 (an unknown name) right after: refused, "That formula cannot be computed", no
   formula kept on the diagonal.
D  Type =w*0: refused, the value must be more than 0.
E  Finish Sketch; Change Parameters' trial with the diagonal set to 20: refused in words, the
   sketch recomputed and fine.
"""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import sketch_tools_steps as st

V = App.Vector
s = st.s
CONFLICT = "That value does not fit"


def sk():
    return st.sketch() or s.get("sketch")


def editor():
    from sciforge import sketch_mode

    session = sketch_mode.current()
    return session.editor if session is not None else None


def p_setup():
    from sciforge import parameters

    parameters.add_user(App.ActiveDocument, "w", "mm", "30")
    App.ActiveDocument.recompute()


def r_rect():
    h.press("r")


def r_c1():
    st.click(V(40, 20, 0))


def r_c2():
    st.click(V(0, 0, 0))


def r_done():
    st.esc()


r_done.wait_ms = 900


def d_dim():
    h.press("d")


def d_pick():
    st.click(V(20, 20, 0))


def d_place():
    st.click(V(20, 28, 0))


def d_type():
    si.type_text("=w")


def d_check():
    st.esc()
    xs = sorted({round(p, 3) for g in sk().Geometry for p in (g.StartPoint.x, g.EndPoint.x)})
    h.check("setup: =w gives a 30 wide rectangle", xs == [0.0, 30.0], xs)


d_check.wait_ms = 1200


def e_setup():
    import Part
    import Sketcher

    s0 = sk()
    s["sketch"] = s0
    d = App.ActiveDocument
    d.openTransaction("Diagonal")
    g = s0.addGeometry(Part.LineSegment(V(0, 0, 0), V(30, 20, 0)), True)
    s0.addConstraint(Sketcher.Constraint("Coincident", g, 1, 2, 1))
    s0.addConstraint(Sketcher.Constraint("Coincident", g, 2, 0, 1))
    s["diag"] = s0.addConstraint(Sketcher.Constraint("Distance", g, 36.05551275463989))
    s0.solve()
    d.commitTransaction()
    d.recompute()
    s["exprs"] = dict(s0.ExpressionEngine)
    h.check("setup: the sketch solves", s0.solve() == 0 and not s0.RedundantConstraints)


e_setup.wait_ms = 1000


def opener(tag):
    def step():
        st.esc()
        h.double_click(si.dimension_label(sk(), s["diag"]))

    step.__name__ = "open_" + tag
    return step


def typer(tag, text):
    def step():
        h.check("%s: the box is open" % tag, editor() is not None)
        si.type_text(text)

    step.__name__ = "type_" + tag
    return step


def checker(tag, words):
    def step():
        ed = editor()
        reason = ed.reason() if ed is not None else ""
        state = list(sk().State)
        print("[SciForge] box %s: %r state=%s exprs=%s" % (tag, reason, state, dict(sk().ExpressionEngine)), flush=True)
        h.check("%s: the box stays open" % tag, ed is not None)
        h.check("%s: and says why" % tag, words in (reason or ""), reason)
        h.check("%s: not FreeCAD's words" % tag, "constraint index" not in (reason or ""), reason)
        h.check("%s: the diagonal keeps its size" % tag, abs(sk().getDatum(s["diag"]).Value - 36.05551275463989) < 1e-6)
        h.check("%s: no formula added" % tag, dict(sk().ExpressionEngine) == s["exprs"], dict(sk().ExpressionEngine))
        h.check("%s: the sketch is not left marked as failed" % tag, "Invalid" not in state, state)
        h.new_errors()  # the trial's own FreeCAD messages (an unknown name...) are expected
        st.esc()

    step.__name__ = "check_" + tag
    step.wait_ms = 1200
    return step


def f_finish():
    st.esc()
    h.ribbon("Finish Sketch")


f_finish.wait_ms = 1500


def f_trial():
    from sciforge import parameters

    d = App.ActiveDocument
    sketch = s["sketch"]
    path = ".Constraints[%d]" % s["diag"]
    rows = [r for r in parameters.model_parameters(d) if r["object"] == sketch.Name and r["path"] == path]
    h.check("E: the diagonal is a model parameter", len(rows) == 1, rows)
    if not rows:
        return
    message = parameters.change_checked(
        d, sketch, path, lambda: parameters.set_model(d, rows[0], "20"), "%s = 20" % rows[0]["label"]
    )
    h.new_errors()
    print("[SciForge] box E: %r state=%s" % (message, list(sketch.State)), flush=True)
    h.check("E: refused in words", message.startswith("Not changed:") and "does not fit" in message, message)
    h.check("E: not FreeCAD's words", "constraint index" not in message, message)
    h.check("E: the diagonal keeps its size", abs(sketch.getDatum(s["diag"]).Value - 36.05551275463989) < 1e-6)
    h.check("E: the sketch is recomputed and fine", list(sketch.State) == ["Up-to-date"], list(sketch.State))


steps = [p_setup, r_rect, r_c1, r_c2, r_done, d_dim, d_pick, d_place, d_type, d_check, e_setup]
for tag, text, words in (
    ("A", "10", CONFLICT),
    ("B", "=w/2", CONFLICT),
    ("C", "=foo*2", "That formula cannot be computed"),
    ("D", "=w*0", "must be more than 0"),
):
    steps += [opener(tag), typer(tag, text), checker(tag, words)]
steps += [f_finish, f_trial]

h.run("sketch_explain_box", st.start_steps("ExplainBox") + steps)
