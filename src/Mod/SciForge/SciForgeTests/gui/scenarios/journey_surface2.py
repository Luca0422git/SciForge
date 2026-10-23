# SPDX-License-Identifier: LGPL-2.1-or-later
"""Journey (wave 6), part 2: a surface worked over with the SURFACE tools in a row, real input.

The design (built for the scenario, part 1 clicks these): a slanted line on the YZ plane
from (y 5, z 4) to (y 25, z 8) extruded as a surface Two Sides 45 / 5 (Extrude 1): the plane
z = 3 + 0.2 y over x -5 .. 45 (50 x W, W = 20.396); a sketch line on XY along x = 0 (y -10
.. 40), the trim tool.

1. SURFACE > CREATE > Offset: click the surface: Offset Type Sharp Offset; type 3 (towards
   the top): a copy 3 mm above it (same area). OK.
2. SURFACE > MODIFY > Trim: click the sketch line (the tool), click the copy's piece at
   x < 0: it keeps x 0 .. 45 (45 W). OK.
3. SURFACE > MODIFY > Extend: Natural, click its edge at x = 45, 5: x 0 .. 50, still one
   flat face (50 W). OK.
4. Q (Press Pull), click it: 2: it moves 2 mm out along its normal (the same area). OK.
5. SURFACE > CREATE > Mirror: click it, Operation Join, the YZ square: stitched along x 0:
   2 faces, 100 W, one shell. OK.
6. SURFACE > MODIFY > Merge: click both faces: one face. OK.
7. INSPECT > Environmental Map Analysis: click it: drawn. OK.
8. SURFACE > CREATE > Thicken: click it, 2, OK: a solid of 200 W.
9. Double-click Extrude 1: Distance 55: every later step follows (x -60 .. 60, a solid of
   240 W), none fails. Undo / Redo.
10. Save, close, reopen: the same timeline, the solid, the analysis.
11. Double-click Extrude 1: One Side: the surface now starts on the trim line, so the Trim
    cannot cut: it turns red with the reason (the later steps red too, nothing built wrong);
    Ctrl+Z: all back.
"""

import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import analysis_steps as a
from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import pattern_steps as ps
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import surface4_steps as s4
from SciForgeTests.gui import surface_steps as st

V = App.Vector
s = {}
W = math.sqrt(20**2 + 4**2)
N = V(0, -0.2, 1) * (1 / math.sqrt(1.04))  # the surface's upward normal


def doc():
    return App.ActiveDocument


def titles():
    return st.timeline_titles()


def title(prefix):
    return next((t for t in titles() if t.startswith(prefix)), None)


def on_copy(x, up=3.0):
    """A point of the offset copy (`up` mm above the surface) at x, across its middle."""
    return V(x, 15, 6) + N * up


def bad_steps():
    return [o.Label for o in doc().Objects if "Invalid" in o.State or "Error" in o.State]


def setup():
    from sciforge import bodies, surface

    s4.new_design("JourneySurface2")
    line = s4.sketch([(5, 4), (25, 8)], plane="YZ_Plane", closed=False)
    step = surface.build(
        "extrude",
        {"refs": [(line, "Edge1")]},
        {"direction": "two_sides", "distance": 45.0, "distance2": 5.0},
    )
    doc().recompute()
    bodies.set_shown(line, False)
    s["surf"] = bodies.body_of(step)
    tool = s4.sketch([(0, -10), (0, 40)], closed=False, body=bodies.body_of(line))
    s["tool"] = tool
    h.fit()
    bb = s["surf"].Shape.BoundBox
    h.check("the surface: 50 x W", st.near(st.area(s["surf"]), 50 * W), st.area(s["surf"]))
    h.check(
        "x -5 .. 45, z 4 .. 8",
        st.near(bb.XMin, -5)
        and st.near(bb.XMax, 45)
        and st.near(bb.ZMin, 4)
        and st.near(bb.ZMax, 8),
        bb,
    )
    h.click_empty()
    st.tab("SURFACE")
    st.menu("CREATE", "Offset")


# -- 1. Offset ----------------------------------------------------------------------------------
def offset_click():
    h.check("Extrude 1 in the timeline", "Extrude 1" in titles(), titles())
    p = st.panel()
    h.check("Offset open", p is not None and p.kind == "offset")
    if p is not None:
        h.check(
            "Offset Type Sharp Offset",
            p.rows["offset_type"][0].currentText() == "Sharp Offset",
            p.rows["offset_type"][0].currentText(),
        )
    h.click(V(20, 15, 6))


def offset_type():
    st.settle()
    p = st.panel()
    h.check("the face picked", p is not None and len(p.picks["faces"]) == 1, p and p.picks)
    st.type_field("distance", "3")


def offset_side():
    st.settle()
    body = st.step_body()
    s["copy"] = body
    bb = body.Shape.BoundBox if body is not None else None
    s["typed"] = "3"
    if bb is not None and bb.ZMax < 8:
        st.type_field("distance", "-3")  # the preview went below: the other way
        s["typed"] = "-3"
    h.check("offset typed %s (towards the top)" % s["typed"], bb is not None)


def offset_ok():
    st.settle()
    body = st.step_body()
    s["copy"] = body
    h.check("the same area", body is not None and st.near(st.area(body), 50 * W, 1e-6))
    if body is not None:
        bb = body.Shape.BoundBox
        want = 4 + 3 * N.z
        h.check("3 mm above the surface", st.near(bb.ZMin, want, 1e-6), (bb.ZMin, want))
    st.ok()


def offset_done():
    from sciforge import surface

    h.check("dialog closed", st.panel() is None)
    h.check("Offset 1 in the timeline", "Offset 1" in titles(), titles())
    h.check("a surface body", surface.is_surface_body(s["copy"]))
    h.click_empty()
    st.menu("MODIFY", "Trim")


# -- 2. Trim ------------------------------------------------------------------------------------
def trim_tool():
    p = st.panel()
    h.check("Trim open", p is not None and p.kind == "trim")
    h.check("clicked the sketch line", h.click_edge(V(0, 38, 0)))


def trim_piece():
    st.settle()
    p = st.panel()
    tool = p.picks["tool"] if p is not None else []
    h.check("the sketch line is the tool", len(tool) == 1 and tool[0][0] is s["tool"], tool)
    h.click(on_copy(-2.5))


def trimmed():
    st.settle()
    area = st.area(s["copy"])
    h.check("the copy keeps x 0 .. 45", st.near(area, 45 * W, 1e-6), (area, 45 * W))
    h.check("the surface itself untouched", st.near(st.area(s["surf"]), 50 * W, 1e-6))
    st.ok()


def trim_done():
    h.check("dialog closed", st.panel() is None)
    s["trim"] = title("Trim")
    h.check("Trim in the timeline", s["trim"] is not None, titles())
    bb = s["copy"].Shape.BoundBox
    h.check("x 0 .. 45", st.near(bb.XMin, 0) and st.near(bb.XMax, 45), bb)
    h.click_empty()
    st.menu("MODIFY", "Extend")


# -- 3. Extend ----------------------------------------------------------------------------------
def extend_edge():
    p = st.panel()
    h.check("Extend open", p is not None and p.kind == "extend")
    if p is not None:
        h.check("Natural", p.options["extend_type"] == "natural", p.options)
    h.check("clicked the copy's edge at x 45", h.click_edge(on_copy(45)))


def extend_type():
    st.settle()
    st.type_field("distance", "5")


def extended():
    st.settle()
    area = st.area(s["copy"])
    h.check("x 0 .. 50 (50 W)", st.near(area, 50 * W, 1e-6), (area, 50 * W))
    h.check("still one flat face", s4.faces(s["copy"]) == 1, s4.faces(s["copy"]))
    st.ok()


def extend_done():
    h.check("dialog closed", st.panel() is None)
    bb = s["copy"].Shape.BoundBox
    h.check("x 0 .. 50", st.near(bb.XMin, 0) and st.near(bb.XMax, 50), bb)
    Gui.Selection.clearSelection()
    h.press("q")


# -- 4. Press Pull ------------------------------------------------------------------------------
def pp_click():
    h.click(on_copy(30))


def pp_type():
    s4.settle()
    p = s4.panel()
    h.check(
        "the surface Press Pull", p is not None and p.kind == "surface_press_pull", p and p.kind
    )
    s4.type_main("2")


def pp_ok():
    s4.settle()
    st.ok()


def pulled():
    h.check("dialog closed", s4.panel() is None)
    bb = s["copy"].Shape.BoundBox
    want = 4 + 5 * N.z
    h.check("moved 2 more along its normal", st.near(bb.ZMin, want, 1e-6), (bb.ZMin, want))
    h.check("the same area", st.near(st.area(s["copy"]), 50 * W, 1e-6), st.area(s["copy"]))
    h.check("Press Pull in the timeline", title("Press Pull") is not None, titles())
    h.click_empty()
    Gui.Selection.clearSelection()
    st.menu("CREATE", "Mirror")


# -- 5. Mirror, Join ----------------------------------------------------------------------------
def mirror_click():
    h.click(on_copy(30, 5.0))


def mirror_join():
    p = ps.panel() if hasattr(ps, "panel") else None
    if p is None:
        from sciforge import pattern_ui

        p = getattr(pattern_ui, "PatternPanel", None) and pattern_ui.PatternPanel.last
    h.check("Mirror open", p is not None)
    if p is None:
        return
    s["mirror_panel"] = p
    b.choose(p.operation, "Join")


def mirror_plane_box():
    ps.click_box("plane")


def mirror_yz():
    pl.click_square("YZ_Plane")


def mirrored_preview():
    st.settle()
    h.idle_step()()
    area = st.area(s["copy"])
    h.check("both halves: 100 W", st.near(area, 100 * W, 1e-6), (area, 100 * W))
    h.task_button("OK")


def mirror_done():
    st.settle()
    copy = s["copy"]
    h.check("2 faces", s4.faces(copy) == 2, s4.faces(copy))
    h.check("one shell", len(copy.Shape.Shells) == 1, len(copy.Shape.Shells))
    bb = copy.Shape.BoundBox
    h.check("x -50 .. 50", st.near(bb.XMin, -50) and st.near(bb.XMax, 50), bb)
    h.check("Mirror in the timeline", title("Mirror") is not None, titles())
    h.click_empty()
    Gui.Selection.clearSelection()
    st.menu("MODIFY", "Merge")


# -- 6. Merge -----------------------------------------------------------------------------------
def merge_first():
    p = s4.panel()
    h.check("the Merge dialog", p is not None and p.kind == "surface_merge")
    h.click(on_copy(25, 5.0))


def merge_second():
    s4.settle()
    h.click(on_copy(-25, 5.0))


def merge_ok():
    s4.settle()
    st.ok()


def merged():
    h.check("dialog closed", s4.panel() is None)
    h.check("one face", s4.faces(s["copy"]) == 1, s4.faces(s["copy"]))
    h.check("the same area", st.near(st.area(s["copy"]), 100 * W, 1e-6), st.area(s["copy"]))
    h.check("Merge in the timeline", title("Merge") is not None, titles())
    a.inspect("Environmental Map Analysis")


# -- 7. Environmental Map -----------------------------------------------------------------------
def envmap_click():
    p = a.panel()
    h.check("Environmental Map open", p is not None and p.kind == "EnvironmentMapAnalysis")
    h.click(on_copy(20, 5.0))


def envmap_ok():
    st.wait(600)
    found = a.analyses("EnvironmentMapAnalysis")
    h.check("an Environmental Map analysis", len(found) == 1, found)
    if found:
        h.check("on the copy", found[0].Targets and found[0].Targets[0][0] is s["copy"])
    h.shot("1-envmap")
    h.task_button("OK")


def envmap_done():
    h.check("dialog closed", a.panel() is None)
    h.click_empty()
    st.menu("CREATE", "Thicken")


# -- 8. Thicken ---------------------------------------------------------------------------------
def thicken_click():
    p = st.panel()
    h.check("Thicken open", p is not None and p.kind == "thicken")
    h.click(on_copy(20, 5.0))


def thicken_type():
    st.settle()
    st.type_field("thickness", "2")


def thicken_ok():
    st.settle()
    body = st.step_body()
    s["plate"] = body
    v = st.volume(body)
    h.check("a solid plate of 100 W x 2", st.near(v, 200 * W, 1e-6), (v, 200 * W))
    st.ok()


def thicken_done():
    h.check("dialog closed", st.panel() is None)
    h.check("Thicken in the timeline", title("Thicken") is not None, titles())
    h.shot("2-thickened")
    h.check("double-clicked Extrude 1", st.double_click_timeline("Extrude 1"))


# -- 9. edit the early step ---------------------------------------------------------------------
def edit_extrude():
    st.settle()
    p = st.panel()
    h.check("Edit Extrude", p is not None and p.kind == "extrude" and p.editing)
    st.type_field("distance", "55")


def edit_ok():
    st.settle()
    st.ok()


def followed():
    st.settle()
    h.idle_step()()
    h.check("dialog closed", st.panel() is None)
    bb = s["surf"].Shape.BoundBox
    h.check("the surface x -5 .. 55", st.near(bb.XMin, -5) and st.near(bb.XMax, 55), bb)
    bad = bad_steps()
    h.check("no later step fails", not bad, bad)
    cb = s["copy"].Shape.BoundBox
    h.check("the copy follows: x -60 .. 60", st.near(cb.XMin, -60) and st.near(cb.XMax, 60), cb)
    h.check("still one face", s4.faces(s["copy"]) == 1, s4.faces(s["copy"]))
    v = st.volume(s["plate"])
    h.check("the plate follows: 240 W", st.near(v, 240 * W, 1e-6), (v, 240 * W))
    s["v"] = v
    st.undo()


def edit_undone():
    v = st.volume(s["plate"])
    h.check("Undo: 200 W", st.near(v, 200 * W, 1e-6), v)
    st.redo()


def edit_redone():
    v = st.volume(s["plate"])
    h.check("Redo: 240 W", st.near(v, 240 * W, 1e-6), v)
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-journey-sf2-"), "journey_surface2.FCStd")
    s["path"] = path
    s["labels"] = (s["plate"].Label, s["copy"].Label)
    s["surf_label"] = s["surf"].Label
    trims = [o for o in doc().Objects if o.Label.startswith("Trim") and hasattr(o, "Shape")]
    s["trim_label"] = trims[0].Label if trims else ""
    s["titles"] = titles()
    doc().saveAs(path)
    h.check("saved", os.path.isfile(path), path)


def ctrl_s():
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


def describe():
    from SciForgeTests.gui import versions_input as vi

    h.check("the Save dialog asks for a version description", vi.version_dialog() is not None)
    vi.accept_save()


def close():
    h.check("nothing unsaved", not doc().isTouched())
    App.closeDocument(doc().Name)


def reopen():
    App.openDocument(s["path"])
    h.fit()


def reopened():
    plate = doc().getObjectsByLabel(s["labels"][0])
    copy = doc().getObjectsByLabel(s["labels"][1])
    h.check("the plate and the surface are back", plate and copy, s["labels"])
    if not (plate and copy):
        return
    h.check("the same plate", st.near(st.volume(plate[0]), s["v"], 1e-9), st.volume(plate[0]))
    h.check("the surface one face", s4.faces(copy[0]) == 1, s4.faces(copy[0]))
    h.check("the same timeline", titles() == s["titles"], (titles(), s["titles"]))
    h.check("no step in error", not bad_steps(), bad_steps())
    h.check("the analysis is back", len(a.analyses("EnvironmentMapAnalysis")) == 1)
    s["plate"], s["copy"] = plate[0], copy[0]
    s["surf"] = next(o for o in doc().Objects if o.Label == s["surf_label"])
    h.check("double-clicked Extrude 1", st.double_click_timeline("Extrude 1"))


# -- 11. an edit the later steps cannot follow --------------------------------------------------
def one_side():
    st.settle()
    p = st.panel()
    h.check("Edit Extrude after the reopen", p is not None and p.kind == "extrude" and p.editing)
    st.choose("direction", "One Side")


def one_side_ok():
    """The surface now starts on the trim line (x 0): the Trim cannot cut the copy in two
    any more. It must say so (a red step with the reason), never crash or cut wrong."""
    st.settle()
    st.ok()
    st.settle()
    h.idle_step()()
    errors = h.new_errors()  # the red steps are reported (expected)
    trim = next((o for o in doc().Objects if o.Label == s["trim_label"]), None)
    status = trim.getStatusString() if trim is not None else ""
    h.check(
        "the Trim is red",
        trim is not None and ("Invalid" in trim.State or "Error" in trim.State),
        trim and trim.State,
    )
    h.check("with the reason", "does not cut" in status, (status, errors))
    s["status"] = status


def red_with_reason():
    from sciforge import timeline_core  # noqa: F401  (the timeline shows the red steps)

    later = [o for o in doc().Objects if "Invalid" in o.State or "Error" in o.State]
    h.check("the later steps are red too, not built wrong", len(later) >= 1, later)
    texts = {o.Label: o.getStatusString() for o in later}
    raw = ("Standard_", "Traceback", "BRep", "TopoDS", "Py_")
    h.check(
        "each red step says why in words (no kernel jargon)",
        all(t and t != "Valid" and not any(r in t for r in raw) for t in texts.values()),
        texts,
    )
    v = st.volume(s["plate"])
    h.check("no plate built from a wrong surface", not (v and not st.near(v, s["v"], 1e-9)), v)
    h.new_errors()
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


red_with_reason.wait_ms = 2000


def fixed_by_undo():
    st.settle()
    h.idle_step()()
    h.new_errors()  # the recompute of the red steps before the undo
    h.check("Ctrl+Z: no step in error", not bad_steps(), bad_steps())
    v = st.volume(s["plate"])
    h.check("the plate back: 240 W", st.near(v, 240 * W, 1e-6), v)


h.run(
    "journey_surface2",
    [
        setup,
        offset_click,
        offset_type,
        offset_side,
        offset_ok,
        offset_done,
        trim_tool,
        trim_piece,
        trimmed,
        trim_done,
        extend_edge,
        extend_type,
        extended,
        extend_done,
        pp_click,
        pp_type,
        pp_ok,
        pulled,
        mirror_click,
        mirror_join,
        mirror_plane_box,
        mirror_yz,
        mirrored_preview,
        mirror_done,
        merge_first,
        merge_second,
        merge_ok,
        merged,
        envmap_click,
        envmap_ok,
        envmap_done,
        thicken_click,
        thicken_type,
        thicken_ok,
        thicken_done,
        edit_extrude,
        edit_ok,
        followed,
        edit_undone,
        edit_redone,
        ctrl_s,
        describe,
        close,
        reopen,
        reopened,
        one_side,
        one_side_ok,
        red_with_reason,
        fixed_by_undo,
    ],
)
