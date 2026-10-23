# SPDX-License-Identifier: LGPL-2.1-or-later
"""Values held at their limit: the fixes of the review of 2026-10-22 (findings L3 to L6).

  * L5 Draft, fixed plane XY, the box's front face, 80 typed: held at the steepest angle
    that fits, with the note. Flip clicked: the note goes (it was about the other
    direction; with Flip 80 fits), and 80 typed again builds without a note.
  * L6 Coil, 20 typed for Revolutions (a count): the note has no "mm" ("20 does not fit:
    limited to 9.99").
  * L3 Shell on a busy part (a plate 120 x 120 x 12 with 36 holes and 25 bosses, like an
    imported part), bottom face taken away, 50 typed: the limit search never crashes
    FreeCAD (walls of 8 to 30 mm crashed OpenCASCADE's validity check), the wall is held at
    a thickness that builds, and the dialog says so.
  * L4 A Distance and Angle chamfer on a 90 degree edge and a 135 degree edge together
    (angle 30, Flip): FreeCAD builds it at 6 mm, so the dialog's check must not refuse it
    (each edge is checked with its own second distance)."""

import FreeCAD as App
import FreeCADGui as Gui
import Part

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import primitive_input as pi
from SciForgeTests.gui import shell_draft_steps as sd

V = App.Vector
s = {}


def note(p):
    return p.limit_label.text() if p is not None and p.limit_label.isVisible() else ""


def msg(p):
    return p.message.text() if p is not None else ""


# -- L5: Draft, Flip after a hold ---------------------------------------------------------
def draft():
    Gui.Selection.clearSelection()
    sd.modify_menu("Draft")


def draft_xy():
    h.fit()
    pl.click_square("XY_Plane")


def draft_front():
    h.fit()
    h.click(V(20, 0, 5))


def draft_80():
    p = sd.draft_panel()
    h.check("the Draft dialog", p is not None)
    if p:
        sd.type_into(p.angle.widget, "80")


draft_80.wait_ms = 4000


def draft_held():
    p = sd.draft_panel()
    a = p.options["angle"] if p else 0
    s["angle"] = a
    h.check("80 is held at the steepest angle that fits", 45.0 < a < 80.0, a)
    h.check("and said", note(p) == "80° does not fit: limited to %.1f°" % a, note(p))
    if p:
        ui.click(p.flip)


draft_held.wait_ms = 3000


def draft_flipped():
    p = sd.draft_panel()
    h.check("Flip: the angle stays", p is not None and abs(p.options["angle"] - s["angle"]) < 1e-9)
    h.check("Flip: the note about the other direction goes", note(p) == "", note(p))
    h.check("no error", msg(p) == "", msg(p))
    if p:
        sd.type_into(p.angle.widget, "80")


draft_flipped.wait_ms = 3000


def draft_80_flipped():
    p = sd.draft_panel()
    h.check("with Flip 80 fits", p is not None and p.options["angle"] == 80.0, p and p.options)
    h.check("no note, no error", note(p) == "" and msg(p) == "", (note(p), msg(p)))
    h.task_button("Cancel")


draft_80_flipped.wait_ms = 2000


# -- L6: Coil revolutions -----------------------------------------------------------------
def coil():
    App.newDocument("LimitsReviewCoil")
    h.fit()
    pi.menu("Coil")


def coil_xy():
    pl.click_square("XY_Plane")


def coil_centre():
    pl.click_on_plane(V(0, 0, 0))


def coil_point():
    pl.click_on_plane(V(10, 0, 0))


coil_point.wait_ms = 2000


def coil_20():
    p = pi.panel("CoilPanel")
    h.check("the Coil dialog", p is not None)
    if p:
        ui.type_into(p.revolutions.widget, "20")


coil_20.wait_ms = 3000


def coil_held():
    p = pi.panel("CoilPanel")
    turns = p.options["revolutions"] if p else 0
    h.check("20 turns are held at what fits", 1.0 < turns < 20.0, turns)
    h.check(
        "the note has no unit for a count of turns",
        note(p) == "20 does not fit: limited to %.2f" % turns,
        note(p),
    )
    h.task_button("Cancel")


coil_held.wait_ms = 2000


# -- L3: Shell on a busy part -------------------------------------------------------------
def plate():
    doc = App.newDocument("LimitsReviewShell")
    box = Part.makeBox(120, 120, 12)
    holes = [
        Part.makeCylinder(4, 30, V(10 + i * 20, 10 + j * 20, 0)) for i in range(6) for j in range(6)
    ]
    shape = box.cut(Part.makeCompound(holes)).removeSplitter()
    bosses = [
        Part.makeCylinder(3, 10, V(20 + i * 20, 20 + j * 20, 12)) for i in range(5) for j in range(5)
    ]
    shape = shape.fuse(bosses).removeSplitter()
    part = doc.addObject("Part::Feature", "Plate")
    part.Shape = shape
    body = doc.addObject("PartDesign::Body", "Body")
    body.BaseFeature = part
    doc.recompute()
    h.fit()
    tip = body.Tip
    faces = tip.Shape.Faces
    bottom = [i for i, f in enumerate(faces, 1) if abs(f.CenterOfMass.z) < 1e-6 and f.Area > 1000]
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(doc.Name, body.Name, "%s.Face%d" % (tip.Name, bottom[0]))
    h.ribbon("Shell")


plate.wait_ms = 4000


def shell_50():
    from sciforge import shell_ui

    p = shell_ui.ShellPanel.last
    h.check("the Shell dialog, bottom face taken away", p is not None and len(p.names()) == 1)
    s["shell"] = p
    if p:
        ui.type_into(p.inside.widget, "50")


shell_50.wait_ms = 10000


def shell_held():
    p = s.get("shell")
    t = p.options.get("inside") if p else 0
    h.check("FreeCAD is still there, the wall is held at a thickness that fits", 0.5 < t < 3.0, t)
    h.check("and said", note(p) == "50 mm does not fit: limited to %.2f mm" % t, note(p))
    h.check("no error", msg(p) == "", msg(p))
    h.task_button("Cancel")


shell_held.wait_ms = 2000


# -- L4: Distance and Angle chamfer on edges with different corner angles -----------------
def chamfer_angles():
    from sciforge import blend

    profile = Part.Face(
        Part.makePolygon([V(0, 0, 0), V(40, 0, 0), V(40, 0, 10), V(10, 0, 10), V(0, 0, 0)])
    )
    info = blend.ShapeInfo(profile.extrude(V(0, 30, 0)))

    def edge(x):
        for i, e in enumerate(info.shape.Edges, 1):
            c = e.CenterOfMass
            if abs(c.x - x) < 1e-6 and abs(c.z - 10) < 1e-6:
                return "Edge%d" % i

    refs = [edge(40), edge(10)]  # the 90 degree and the 135 degree top edges
    options = dict(chamfer_type="angle", distance=6, angle=30, flip=True)
    try:
        blend.check_build("chamfer", info, refs, options)
        ok = True
    except blend.BlendError as exc:
        ok = str(exc)
    h.check("a 90 and a 135 degree edge, 6 mm at 30 degrees, Flip: fits", ok is True, ok)
    try:
        blend.check_build("chamfer", info, refs, dict(options, distance=40))
        refused = False
    except blend.BlendError:
        refused = True
    h.check("40 mm does not", refused)


h.run(
    "limits_review",
    sd.box_steps("LimitsReview")
    + [draft, draft_xy, draft_front, draft_80, draft_held, draft_flipped, draft_80_flipped]
    + [coil, coil_xy, coil_centre, coil_point, coil_20, coil_held]
    + [plate, shell_50, shell_held, chamfer_angles],
)
