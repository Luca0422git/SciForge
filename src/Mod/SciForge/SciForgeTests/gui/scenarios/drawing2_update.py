# SPDX-License-Identifier: LGPL-2.1-or-later
"""Annotations, tolerances and the new views follow the design (Fusion: a drawing is
linked to its design), with real clicks for the design edits.

The plate (drawing_fixtures.plate), ISO A3, base view Top at 1:1, set up by script with
the same functions the commands use (drawing2_steps.furnish: the subject here is what
follows): hole 1's diameter toleranced H7 shown as limits, an ordinate to hole 1, a
leader on hole 1, a feature control frame on hole 2, datum A, a surface texture, the
automated centre marks, an edge extension at the R8 corner, its arc length, a Slice
section through hole 1 and an offset section through both holes.

A  Workspace > Design, Fillet 1 radius 12 in the timeline, OK; Workspace > Drawing: the
   arc length reads 18.85 (12 x pi / 2), the edge extension still meets at the corner
   (the lines longer now), the rest unchanged.
B  Hole 1 moved to (25, 15) and made 12 mm across (by script): the diameter's limits are
   12.018 / 12.000 (H7 at 12), the ordinate reads 25, the leader's arrow is on the moved
   hole, the centre mark went with it, the frame stays on hole 2, the Slice section's
   lines beyond the cut are worked out again, the offset section still has its geometry.
C  Back in the design, Ctrl+Z (the fillet edit undone): the arc length reads 12.57 again.
"""

import math

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import drawing2_steps as w
from SciForgeTests.gui import drawing_input as d
from SciForgeTests.gui import harness as h

state = {}
DIA = w.DIA


def obj(key):
    return App.ActiveDocument.getObject(state["made"][key])


def setup():
    state["made"] = w.furnish()
    state["label"] = d.page().Label


setup.wait_ms = 4000


def s_check():
    from sciforge import drawing, drawing_annot

    h.check(
        "limits at 10",
        obj("dim").FormatSpec == DIA + "10.015\n" + DIA + "10.000",
        obj("dim").FormatSpec,
    )
    h.check("ordinate 20", round(drawing_annot.ordinate_value(obj("ordinate")), 3) == 20.0)
    h.check("arc 12.57", w.describe(obj("arc")) == "⌒12.57", w.describe(obj("arc")))
    h.check("the offset section has geometry", len(obj("offset").getVisibleEdges()) > 0)
    h.check("the slice section has geometry", len(obj("slice").getVisibleEdges()) > 0)
    from sciforge import drawing_depth

    h.check("the slice switches lines off", len(drawing_depth.stored(obj("slice"))) > 0)
    state["sig"] = drawing_depth.signature(obj("slice"))
    state["ext"] = drawing.extensions_of(w.base())[0]
    h.shot("s-set-up")


# -- A ------------------------------------------------------------------------------------------
def a_design():
    d.workspace("Design")


a_design.wait_ms = 1500


def a_edit():
    h.check("the design's tab", d.page() is None)
    h.fit()
    b.timeline_double_click("Fillet 1")


a_edit.wait_ms = 1500


def a_radius():
    p = b.blend_panel()
    if h.check("editing Fillet 1", p is not None and p.target is not None and not p.created):
        b.type_into(p.radius.widget, "12")


a_radius.wait_ms = 1500


def a_ok():
    h.task_button("OK")


a_ok.wait_ms = 2000


def a_open():
    d.workspace("Drawing", state["label"])


a_open.wait_ms = 4000


def a_followed():
    from sciforge import drawing

    h.check("the drawing's tab", d.page() is not None)
    h.check("arc 18.85", w.describe(obj("arc")) == "⌒18.85", w.describe(obj("arc")))
    items = drawing.extensions_of(w.base())
    h.check("one edge extension", len(items) == 1, items)
    if items:
        point = items[0]["point"]
        h.check(
            "still meeting at the corner",
            abs(point[0] - 40) < 1e-6 and abs(point[1] - 25) < 1e-6,
            point,
        )
        h.check(
            "its edges are shorter now (the lines longer)",
            items[0]["a"] != state["ext"]["a"],
            items[0],
        )
    h.check(
        "limits unchanged",
        obj("dim").FormatSpec == DIA + "10.015\n" + DIA + "10.000",
        obj("dim").FormatSpec,
    )
    h.shot("a-fillet")


# -- B ------------------------------------------------------------------------------------------
def b_hole():
    doc = App.ActiveDocument
    hole = doc.getObject("Hole1")
    hole.Placement.Base = App.Vector(25.0, 15.0, 0)
    hole.Radius = 6.0
    doc.recompute()


b_hole.wait_ms = 4000


def b_followed():
    from sciforge import drawing, drawing_annot

    h.check(
        "limits at 12",
        obj("dim").FormatSpec == DIA + "12.018\n" + DIA + "12.000",
        obj("dim").FormatSpec,
    )
    h.check("ordinate 25", round(drawing_annot.ordinate_value(obj("ordinate")), 3) == 25.0)
    data = drawing_annot.annotation_data(obj("leader"))
    sig = data["anchor"]["sig"]
    h.check(
        "the leader on the moved hole", abs(sig[0] + 15.0) < 1e-3 and abs(sig[2] - 6.0) < 1e-3, sig
    )
    point = drawing_annot.anchor_point(data["anchor"])
    h.check(
        "its arrow on that circle",
        abs(math.hypot(point[0] + 15.0, point[1] + 10.0) - 6.0) < 1e-6,
        point,
    )
    fcf = drawing_annot.annotation_data(obj("fcf"))["anchor"]["sig"]
    h.check(
        "the frame stays on hole 2", abs(fcf[0] - 20.0) < 1e-3 and abs(fcf[2] - 5.0) < 1e-3, fcf
    )
    marks = drawing.auto_marks_of(w.base()).get("marks", [])
    h.check(
        "the centre mark went",
        [-15.0, -10.0, 6.0] in [[round(v, 3) for v in m] for m in marks],
        marks,
    )
    from sciforge import drawing_depth

    sig = drawing_depth.signature(obj("slice"))
    h.check("the slice's lines worked out again", sig != state["sig"], (sig, state["sig"]))
    h.check("it still switches lines off", len(drawing_depth.stored(obj("slice"))) > 0)
    h.check("the offset section still drawn", len(obj("offset").getVisibleEdges()) > 0)
    h.shot("b-hole")


# -- C ------------------------------------------------------------------------------------------
def c_design():
    d.workspace("Design")


c_design.wait_ms = 1500


def c_undo():
    h.fit()
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


c_undo.wait_ms = 3000


def c_back():
    d.workspace("Drawing", state["label"])


c_back.wait_ms = 4000


def c_followed():
    h.check("arc 12.57 again", w.describe(obj("arc")) == "⌒12.57", w.describe(obj("arc")))


h.run(
    "drawing2_update",
    [w.new_design("Upd2")]
    + w.sheet_steps()
    + [d.wait_geometry(2000), setup, d.wait_geometry(2500), s_check]
    + [a_design, a_edit, a_radius, a_ok, a_open, a_followed]
    + [b_hole, b_followed]
    + [c_design, c_undo, c_back, c_followed],
)
