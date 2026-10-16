# SPDX-License-Identifier: LGPL-2.1-or-later
"""Known limits are said in the dialogs (Luca, 2026-10-16: "press pulling complex shapes is
rough ... add a small warning sign on press pull and mark it as a work in progress"; "holes
on complex shapes is also kinda rough ... call it a limitation").

A  Box 40 x 30 x 10 (real input). Q: the Press Pull dialog shows the yellow work-in-progress
   note; its ribbon tooltip says it too. Esc.
B  Luca's shape: a body whose solid is a smooth loft from a square to an off-centre hexagon
   (built here as a base feature: the shape, not the loft workflow, is what matters). Hole,
   click a side face of the loft: the hole goes on it and the dialog says the face is
   freeform and the hole does not follow it later. Esc. A Hole on the box's flat top face
   (part A's design) says nothing of the kind.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui
import Part
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import hole_steps as hs

V = App.Vector
s = {}


def dialog_open():
    return bool(Gui.Control.activeDialog())


# -- A: Press Pull --------------------------------------------------------------------------------
def a_press_q():
    Gui.Selection.clearSelection()
    h.fit()
    h.press(QtCore.Qt.Key_Q)


def a_note_shown():
    from sciforge import presspull_ui, ribbon_config

    p = presspull_ui.PressPullPanel.last
    open_ = p is not None and not getattr(p, "_closed", True)
    h.check("Q opens Press Pull", open_)
    note = getattr(p, "wip_note", None) if open_ else None
    h.check("the work-in-progress note is shown", note is not None and note.isVisible())
    h.check(
        "it says work in progress and why",
        note is not None and "Work in progress" in note.text() and "complex" in note.text(),
        note.text() if note is not None else None,
    )
    entry = ribbon_config.find(ribbon_config.SOLID_MODIFY, "Press Pull")
    tip = (entry or {}).get("note", "")
    h.check("the ribbon tooltip says it too", "Work in progress" in tip, tip)
    h.shot("a-presspull-note")
    h.press(QtCore.Qt.Key_Escape)


def a_closed():
    h.check("Esc closes Press Pull", not dialog_open())


def a_hole_on_flat():
    Gui.Selection.clearSelection()
    h.ribbon("Hole")


def a_click_top():
    h.fit()
    h.click(V(20, 15, 10))


def a_no_note_on_flat():
    p = hs.hole_panel()
    h.check("a hole on the flat top face", p is not None and p.target is not None)
    text = p.what.text() if p is not None else ""
    h.check("no freeform note on a flat face", "Freeform" not in text, text)
    h.press(QtCore.Qt.Key_Escape)


# -- B: a hole on a loft from a square to an off-centre hexagon ------------------------------------
def _loft_solid():
    square = Part.makePolygon(
        [V(-15, -15, 0), V(15, -15, 0), V(15, 15, 0), V(-15, 15, 0), V(-15, -15, 0)]
    )
    hexagon = []
    for k in range(7):
        a = math.radians(60 * k + 10)
        hexagon.append(V(6 + 10 * math.cos(a), 4 + 10 * math.sin(a), 30))
    return Part.makeLoft([square, Part.makePolygon(hexagon)], True, False)


def b_new_design():
    doc = App.newDocument("LoftHole")
    body = doc.addObject("PartDesign::Body", "Body")
    shape = doc.addObject("Part::Feature", "LoftShape")
    shape.Shape = _loft_solid()
    body.BaseFeature = shape
    doc.recompute()
    s["body"] = body.Name
    h.check("a loft body", body.Shape.isValid() and body.Shape.Volume > 1000, body.Shape.Volume)
    # a side face of the loft that is freeform and faces the isometric camera
    eye = V(1, -1, 1).normalize()
    best = None
    for i, face in enumerate(body.Shape.Faces, start=1):
        kind = face.Surface.TypeId
        if kind in ("Part::GeomPlane",):
            continue
        u0, u1, v0, v1 = face.ParameterRange
        p = face.valueAt((u0 + u1) / 2, (v0 + v1) / 2)
        n = face.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
        if n.dot(eye) > 0.3 and (best is None or n.dot(eye) > best[0]):
            best = (n.dot(eye), p, kind, i)
    s["spot"] = best
    h.check("a freeform side face faces the camera", best is not None, best)
    Gui.SendMsgToActiveView("ViewFit")
    h.fit()


def b_hole():
    Gui.Selection.clearSelection()
    h.ribbon("Hole")


def b_click_side():
    if s.get("spot"):
        h.fit()
        h.click(s["spot"][1])


def b_note():
    p = hs.hole_panel()
    h.check("the hole is placed on the loft's side", p is not None and p.target is not None)
    text = p.what.text() if p is not None else ""
    h.check("the dialog says the face is freeform", "Freeform face" in text, text)
    h.check("and that the hole does not follow it", "does not follow" in text, text)
    h.shot("b-hole-freeform")
    h.press(QtCore.Qt.Key_Escape)


def b_closed():
    h.check("Esc closes Hole", not dialog_open())


h.run(
    "limits_notes",
    b.box_steps("LimitsNotes")
    + [
        a_press_q,
        a_note_shown,
        a_closed,
        a_hole_on_flat,
        a_click_top,
        a_no_note_on_flat,
        b_new_design,
        b_hole,
        b_click_side,
        b_note,
        b_closed,
    ],
)
