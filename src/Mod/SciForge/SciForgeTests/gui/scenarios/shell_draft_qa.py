# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shell and Draft on a rounded block and on a second body, only real input:
  * a block with rounded corners (40 x 30, corner radius 5, 10 high);
  * Shell taking the top face away: Tangent Chain stays on the top (its edges are sharp);
  * Draft about XY: one click on the front face picks the whole tangent run of sides and
    rounds (8 faces); unticking Tangent Chain leaves just the clicked face, ticking it
    again brings the run back; the rounds become cones;
  * a second body: Draft started with the first body active follows a click on the other
    body (Fusion drafts any body's faces), its top face as the fixed plane; Shell does the
    same and its Cancel leaves both bodies as they were.
Hand-derived volumes (A(d, t): area of the rounded rectangle moved in by d + t,
(40 - 2d - 2t)(30 - 2d - 2t) - (4 - pi)(5 - d - t)^2):
  shell, top away, wall t:   10 A(0, 0) - (10 - t) A(0, t)
  sides drafted by a:         prismatoid of A(z tan a, 0) over z = 0..10, minus the same
                              (vertical) cavity
  second body 20^3, front face drafted 5 deg about its top (pull up): + 20 * 20^2 tan5 / 2
"""
import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import shell_draft_steps as sd
from SciForgeTests.gui import widget_input as w

V = App.Vector
s = {}
R, L, W, H = 5.0, 40.0, 30.0, 10.0
TOP = V(20, 15, 10)
FRONT = V(20, 0, 5)
XY_SQUARE = V(12, -8, 0)
B2_TOP = V(70, 10, 20)
B2_FRONT = V(70, 0, 10)
B2_RIGHT = V(80, 10, 10)


def rounded(sketch):
    import Part

    z = V(0, 0, 1)
    geo = [
        Part.LineSegment(V(R, 0, 0), V(L - R, 0, 0)),
        Part.ArcOfCircle(Part.Circle(V(L - R, R, 0), z, R), -math.pi / 2, 0),
        Part.LineSegment(V(L, R, 0), V(L, W - R, 0)),
        Part.ArcOfCircle(Part.Circle(V(L - R, W - R, 0), z, R), 0, math.pi / 2),
        Part.LineSegment(V(L - R, W, 0), V(R, W, 0)),
        Part.ArcOfCircle(Part.Circle(V(R, W - R, 0), z, R), math.pi / 2, math.pi),
        Part.LineSegment(V(0, W - R, 0), V(0, R, 0)),
        Part.ArcOfCircle(Part.Circle(V(R, R, 0), z, R), math.pi, 1.5 * math.pi),
    ]
    for g in geo:
        sketch.addGeometry(g)
    App.ActiveDocument.recompute()


def area(d, t=0.0):
    return (L - 2 * d - 2 * t) * (W - 2 * d - 2 * t) - (4 - math.pi) * (R - d - t) ** 2


def open_rounded(t):
    return H * area(0) - (H - t) * area(0, t)


def drafted(a, t):
    k = math.tan(math.radians(a))
    outer = H / 6.0 * (area(0) + 4 * area(H / 2 * k) + area(H * k))
    return outer - (H - t) * area(0, t)


def vol(body):
    return body.Shape.Volume if body is not None and not body.Shape.isNull() else 0.0


def block_made():
    v = h.solid_volume()
    h.check("rounded block: 10 (1200 - (4 - pi) 25)", sd.close(v, H * area(0)), v)
    s["b1"] = h.body()


def shell():
    Gui.Selection.clearSelection()
    h.ribbon("Shell")


def shell_top():
    h.fit()
    h.click(TOP)


def shell_top_only():
    p = sd.shell_panel()
    h.check(
        "Tangent Chain on, but the top's edges are sharp: just the top",
        p is not None and p.names() and len(p.names()) == 1,
        p and p.names(),
    )
    v = h.solid_volume()
    h.check("open rounded box, 1 mm", sd.close(v, open_rounded(1)), (v, open_rounded(1)))
    h.task_button("OK")


def draft():
    s["v1"] = h.solid_volume()
    sd.modify_menu("Draft")


def draft_plane():
    h.fit()
    h.click(XY_SQUARE)


def draft_front():
    h.click(FRONT)


def chain_picked():
    p = sd.draft_panel()
    h.check(
        "one click picks the tangent run: 4 sides and 4 rounds",
        p is not None and len(p.names()) == 8,
        p and p.names(),
    )
    h.check("the run is highlighted", sum(len(x[1]) for x in sd.selected()) == 8, sd.selected())
    if p:
        sd.type_into(p.angle.widget, "2")


def chain_preview():
    v = h.solid_volume()
    h.check("sides and rounds drafted 2 deg (rounds become cones)", sd.close(v, drafted(2, 1)), v)
    h.shot("1-chain")
    p = sd.draft_panel()
    if p:
        w.click(p.tangent, _box_point(p.tangent))


def _box_point(checkbox):
    from PySide import QtCore

    return QtCore.QPoint(8, checkbox.height() // 2)


def chain_off():
    p = sd.draft_panel()
    h.check("Tangent Chain unticked", p is not None and not p.tangent.isChecked())
    h.check("just the clicked face now", p is not None and len(p.names()) == 1, p and p.names())
    if p:
        w.click(p.tangent, _box_point(p.tangent))


def chain_on_again():
    p = sd.draft_panel()
    h.check("ticked again: the run is back", p is not None and len(p.names()) == 8)
    h.task_button("OK")


def draft_done():
    v = h.solid_volume()
    h.check("draft kept: 2 deg on the run", sd.close(v, drafted(2, 1)), v)
    h.check("valid", h.body().Shape.isValid())
    s["v1"] = v
    # A second body (as if made with Extrude > New Body): a 20 mm cube at x = 60.
    doc = App.ActiveDocument
    body2 = doc.addObject("PartDesign::Body", "Body001")
    cube = body2.newObject("PartDesign::AdditiveBox", "Cube")
    cube.Length = cube.Width = cube.Height = 20
    cube.Placement = App.Placement(V(60, 0, 0), App.Rotation())
    doc.recompute()
    s["b2"] = body2
    Gui.ActiveDocument.ActiveView.setActiveObject("pdbody", s["b1"])
    h.fit()


def draft_other_body():
    Gui.Selection.clearSelection()
    sd.modify_menu("Draft")


def other_plane():
    h.fit()
    h.click(B2_TOP)


def other_followed():
    p = sd.draft_panel()
    h.check("the Draft moved to the clicked body", p is not None and p.body is s["b2"])
    h.check(
        "its top face is the fixed plane",
        p is not None and p.plane_ref is not None and p.plane_ref[1].startswith("Face"),
        p and p.plane_ref,
    )
    h.click(B2_FRONT)


def other_face():
    p = sd.draft_panel()
    h.check("the cube's front face picked", p is not None and len(p.names()) == 1)
    if p:
        sd.type_into(p.angle.widget, "5")


def other_ok():
    h.task_button("OK")


def other_done():
    v2 = vol(s["b2"])
    expect = 8000 + 20 * 400 * math.tan(math.radians(5)) / 2
    h.check("cube drafted about its top (wider at the bottom)", sd.close(v2, expect), (v2, expect))
    h.check("the draft is in the cube's body", s["b2"].Tip.TypeId == "PartDesign::Draft")
    h.check("the first body is untouched", sd.close(vol(s["b1"]), s["v1"]), vol(s["b1"]))
    s["v2"] = v2
    Gui.ActiveDocument.ActiveView.setActiveObject("pdbody", s["b1"])


def shell_other_body():
    Gui.Selection.clearSelection()
    h.ribbon("Shell")


def shell_other_click():
    h.fit()
    h.click(B2_RIGHT)


def shell_other_followed():
    p = sd.shell_panel()
    h.check("Shell moved to the clicked body", p is not None and p.body is s["b2"])
    h.check("its face picked", p is not None and len(p.names()) == 1, p and p.names())
    h.check(
        "a preview in that body", p is not None and p.target is not None, p and p.message.text()
    )
    h.shot("2-other-body")
    h.task_button("Cancel")


def shell_other_cancelled():
    h.check("Cancel: the cube is as it was", sd.close(vol(s["b2"]), s["v2"]), vol(s["b2"]))
    h.check("and the first body too", sd.close(vol(s["b1"]), s["v1"]), vol(s["b1"]))
    h.check("no shell left in the cube's body", s["b2"].Tip.TypeId == "PartDesign::Draft")
    h.check("no errors in the Report view", not sd.report_errors(), sd.report_errors())


h.run(
    "shell_draft_qa",
    b.box_steps("ShellDraftQA", profile=rounded)
    + [
        block_made,
        shell,
        shell_top,
        shell_top_only,
        draft,
        draft_plane,
        draft_front,
        chain_picked,
        chain_preview,
        chain_off,
        chain_on_again,
        draft_done,
        draft_other_body,
        other_plane,
        other_followed,
        other_face,
        other_ok,
        other_done,
        shell_other_body,
        shell_other_click,
        shell_other_followed,
        shell_other_cancelled,
    ],
)
