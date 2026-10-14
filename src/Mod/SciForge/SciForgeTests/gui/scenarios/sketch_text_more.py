# SPDX-License-Identifier: LGPL-2.1-or-later
"""A finished sketch's text used the other ways Fusion offers, real input only (Autodesk
help "Press Pull", "Change Parameters", "Delete"):

X1  click a text (no command running), then Q: Press Pull on a sketch profile is an
    Extrude of it, the whole text as one profile.
X2  Q first, then a click on a text: the same; dragging the distance into the part cuts
    the letters in (volume: the letters' area x 0.6).
X3  the text's height is a model parameter (Change Parameters lists it); a new value
    there makes the letters bigger and the cut follows.
X4  deleting a sketch deletes its text with it, in one undo step; Ctrl+Z brings both.
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import arrow_input as arrows
from SciForgeTests.gui import bodies_steps as bs
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import text_input as ti
from SciForgeTests.gui import timeline_input as tl

V = App.Vector
BLOCK = 60.0 * 30.0 * 10.0
s = {}


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def doc():
    return App.ActiveDocument


def xpanel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return p if p is not None and not p._closed else None


def area(obj):
    return sum(f.Area for f in obj.Shape.Faces)


def add_text(body, label, content, corner):
    from sciforge import text

    sketch = body.newObject("Sketcher::SketchObject", "Sketch")
    sketch.Label = label
    sketch.MapMode = "Deactivated"
    sketch.Placement = App.Placement(V(0, 0, 10), App.Rotation())
    sketch.MakeInternals = True
    spec = text.default_spec()
    spec.update(
        text=content,
        height=10.0,
        corner=corner,
        width=24.0,
        frame_height=20.0,
        font=text.default_family(),
        h_align="center",
        v_align="middle",
    )
    return sketch, text.make(sketch, spec)


def new_part():
    """A 60 x 30 x 10 block; on its top two sketches, each with a text: "AB" on the left,
    "CD" on the right (made before, as Text does)."""
    Gui.activateWorkbench("SciForgeWorkbench")
    d = App.newDocument("TextMore")
    from sciforge import commands

    body = commands.ensure_body()
    box = body.newObject("PartDesign::AdditiveBox", "Box")
    box.Length, box.Width, box.Height = 60, 30, 10
    d.recompute()
    d.openTransaction("setup")
    s["sketch_a"], s["a"] = add_text(body, "Sketch A", "AB", (3.0, 5.0))
    s["sketch_b"], s["b"] = add_text(body, "Sketch B", "CD", (33.0, 5.0))
    d.recompute()
    d.commitTransaction()
    s["body"] = body
    h.check("setup: the block", near(h.solid_volume(), BLOCK), h.solid_volume())
    h.view().viewTop()
    h.view().fitAll()


def letter(key):
    return ti.at(s["sketch_" + key], *ti.middle_of_first_letter(s[key]))


# -- X1 -----------------------------------------------------------------------------------------
def x1_click_text():
    h.click(letter("a"))


def x1_q():
    picked = [(x.Object, tuple(x.SubElementNames)) for x in Gui.Selection.getSelectionEx()]
    h.check("X1 the click picked text AB", any(o is s["a"] for o, _subs in picked), picked)
    h.press("q")


def x1_extrude():
    p = xpanel()
    h.check("X1 Q on a text opened Extrude", p is not None)
    h.check(
        "X1 with the whole text as the profile",
        p is not None and p.profiles == [(s["a"], "")],
        p and p.profiles,
    )
    h.press(QtCore.Qt.Key_Escape)


# -- X2 -----------------------------------------------------------------------------------------
def x2_q_first():
    h.check("X2 Esc closed Extrude", xpanel() is None)
    h.check("X2 nothing made", near(h.solid_volume(), BLOCK), h.solid_volume())
    h.click_empty()
    h.press("q")


def x2_click_text():
    from sciforge import presspull_ui

    p = presspull_ui.PressPullPanel.last
    h.check("X2 Press Pull opened", p is not None and not p._closed)
    h.click(letter("b"))


def x2_extrude():
    p = xpanel()
    h.check(
        "X2 the click on the text turned Press Pull into Extrude of it",
        p is not None and p.profiles == [(s["b"], "")],
        p and p.profiles,
    )
    if p is not None:
        arrows.give_distance("-0.6")


def x2_ok():
    p = xpanel()
    h.check(
        "X2 into the part: Cut",
        p is not None and p.operation.currentData() == "cut",
        p and p.operation.currentData(),
    )
    h.task_button("OK")


def x2_cut():
    want = BLOCK - area(s["b"]) * 0.6
    h.check("X2 the letters are cut 0.6 deep", near(h.solid_volume(), want), h.solid_volume())


# -- X3 -----------------------------------------------------------------------------------------
def x3_parameter():
    from sciforge import parameters

    rows = [r for r in parameters.model_parameters(doc()) if r["label"] == "Text Height"]
    owners = sorted(r["owner"] for r in rows)
    h.check("X3 each text's height is a model parameter", len(rows) == 2, owners)
    row = next((r for r in rows if r["object"] == s["b"].Name), None)
    h.check("X3 at 10 mm", row is not None and near(row["value"], 10.0), row)
    if row is None:
        return
    s["area_before"] = area(s["b"])
    parameters.set_model(doc(), row, "12")  # as typed in Change Parameters
    doc().recompute()


def x3_followed():
    obj = s["b"]
    h.check("X3 the text is 12 mm high now", near(obj.TextHeight.Value, 12.0), obj.TextHeight)
    h.check(
        "X3 its letters grew (area x 1.44)",
        near(area(obj), s["area_before"] * 1.44, 1e-3),
        (area(obj), s["area_before"] * 1.44),
    )
    want = BLOCK - area(obj) * 0.6
    h.check("X3 the cut follows", near(h.solid_volume(), want), (h.solid_volume(), want))


# -- X4 -----------------------------------------------------------------------------------------
def x4_select_sketch():
    titles = tl.titles()
    s["step_a"] = next((t for t in titles if "Sketch A" in t), None)
    h.check("X4 Sketch A on the timeline", s["step_a"] is not None, titles)
    tl.click(s["step_a"])


def x4_delete():
    bs.menu("MODIFY", "Delete")


x4_delete.wait_ms = 1200


def x4_deleted():
    from sciforge import text

    names = [o.Name for o in doc().Objects]
    h.check("X4 Sketch A is deleted", s["sketch_a"].Name not in names)
    left = [o.Label for o in doc().Objects if text.is_text(o)]
    h.check("X4 its text with it (text CD stays)", left == [s["b"].Label], left)
    h.check(
        "X4 one undo step",
        doc().UndoNames and doc().UndoNames[0].startswith("Delete"),
        doc().UndoNames[:3],
    )
    h.press("z", QtCore.Qt.ControlModifier)


def x4_back():
    from sciforge import text

    a = doc().getObject(s["sketch_a"].Name)
    h.check("X4 Ctrl+Z brought Sketch A back", a is not None)
    found = text.texts_of(a) if a is not None else []
    h.check("X4 with its text", len(found) == 1 and found[0].ResolvedText == "AB", found)
    h.check("X4 the part as before", near(h.solid_volume(), BLOCK - area(s["b"]) * 0.6))


h.run(
    "sketch_text_more",
    [
        new_part,
        x1_click_text,
        x1_q,
        x1_extrude,
        x2_q_first,
        x2_click_text,
        x2_extrude,
        x2_ok,
        x2_cut,
        x3_parameter,
        x3_followed,
        x4_select_sketch,
        x4_delete,
        x4_deleted,
        x4_back,
    ],
)
