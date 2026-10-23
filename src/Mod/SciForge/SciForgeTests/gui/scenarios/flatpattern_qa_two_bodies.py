# SPDX-License-Identifier: LGPL-2.1-or-later
"""Unfold in a design with two sheet metal bodies (QA), real input only: the L bracket and a
40 x 30 plate made with the Flange as a new body beside it (setup). SHEET METAL > Unfold, a
click on the bracket's top face, Unfold All Bends ticked: the bracket lies flat (preview).
Then a click on the plate's top face: the dialog moves to the plate, and the bracket is
folded again with no Unfold step left in it (before QA the bracket kept the preview step,
whose stationary face was then set to the plate's face). The plate has no bend: OK is
refused ("no bend to unfold") instead of adding an Unfold that does nothing. Esc: no Unfold
anywhere, both bodies as they were."""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import flatpattern_steps as fs
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}


def setup():
    builder = fs.setup_l("FlatQATwo")
    builder.run(
        {"op": "sketch", "id": "s9", "plane": "XY", "geometry": [{"rect": [70, -30, 110, 0]}]}
    )
    builder.run(
        {"op": "sf_flange", "id": "f9", "kind": "base", "profile": "s9", "operation": "new_body"}
    )
    App.ActiveDocument.recompute()
    from sciforge import bodies

    found = bodies.list_bodies(App.ActiveDocument)
    s["b1"] = fs.body()
    others = [b for b in found if b is not s["b1"]]
    s["b2"] = others[0] if others else None
    s["v1"] = s["b1"].Shape.Volume
    s["v2"] = s["b2"].Shape.Volume if s["b2"] is not None else 0.0
    h.fit()


def two_bodies():
    from sciforge import sheetmetal

    b2 = s["b2"]
    h.check("a second body", b2 is not None)
    h.check("both sheet metal", b2 is not None and sheetmetal.is_sheet_metal_body(b2))
    top = None
    if b2 is not None:
        for face in b2.Shape.Faces:
            n = face.normalAt(0.5, 0.5) if face.Surface.__class__.__name__ == "Plane" else None
            if n is not None and n.z > 0.99 and (top is None or face.Area > top.Area):
                top = face
    h.check("the plate has a top face", top is not None)
    if top is not None:
        bb = top.BoundBox
        s["plate_top"] = V((bb.XMin + bb.XMax) / 2, (bb.YMin + bb.YMax) / 2, bb.ZMax)
    fs.tab("sheet_metal")


def unfold():
    Gui.Selection.clearSelection()
    h.ribbon("Unfold")


def click_bracket():
    h.fit()
    h.click(fs.L_TOP)


def tick_all():
    fs.settle()
    p = fs.sheet_panel()
    if p is not None:
        fs.click_check(p.all_bends)


def bracket_flat():
    fs.settle()
    p = fs.sheet_panel()
    t = p.target if p is not None else None
    from sciforge import bodies

    h.check("preview in the bracket", t is not None and bodies.body_of(t) is s["b1"])
    bb = s["b1"].Shape.BoundBox
    h.check("the bracket lies flat", fs.close(bb.XLength, fs.L_FLAT), bb)


def click_plate():
    h.click(s.get("plate_top", V(90, -15, 1)))


def moved_to_plate():
    fs.settle()
    from sciforge import bodies

    p = fs.sheet_panel()
    h.check("the dialog works on the plate now", p is not None and p.body is s["b2"])
    left = [o.Label for o in s["b1"].Group if bodies.kind(o) == "Unfold"]
    h.check("no Unfold left in the bracket", not left, left)
    bb = s["b1"].Shape.BoundBox
    h.check("the bracket is folded again", fs.close(bb.ZLength, 50), bb)
    t = p.target if p is not None else None
    h.check("any preview is in the plate", t is None or bodies.body_of(t) is s["b2"], t and t.Name)


def ok_flat_plate():
    fs.ok()


def nothing_to_unfold():
    fs.settle()
    text = fs.message()
    h.check("OK on a flat plate is refused: dialog open", fs.dialog_open())
    h.check("it says there is no bend", "no bend" in text, text)


def esc():
    fs.esc()


def nothing_left():
    fs.settle()
    from sciforge import bodies

    h.check("Esc closes the Unfold", not fs.dialog_open())
    steps = [o.Label for o in App.ActiveDocument.Objects if bodies.kind(o) == "Unfold"]
    h.check("no Unfold anywhere", not steps, steps)
    v1, v2 = s["b1"].Shape.Volume, s["b2"].Shape.Volume
    h.check("bracket as it was", fs.close(v1, s["v1"]), v1)
    h.check("plate as it was", fs.close(v2, s["v2"]), v2)
    fs.no_popups("Unfold across two bodies")


h.run(
    "flatpattern_qa_two_bodies",
    [
        setup,
        two_bodies,
        unfold,
        click_bracket,
        tick_all,
        bracket_flat,
        click_plate,
        moved_to_plate,
        ok_flat_plate,
        nothing_to_unfold,
        esc,
        nothing_left,
    ],
)
