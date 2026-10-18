# SPDX-License-Identifier: LGPL-2.1-or-later
"""Revolve on a real part, with the other tools around it (QA, only real input).

The part: Create Sketch on XY, R, a 40 x 30 rectangle from the origin, E, OK (10 high);
Q on the top face, 5 up (15 high). Saved to a temporary file.

Path 6, a groove along an edge of the part: Create Sketch on the front face, a 6 x 4
        rectangle hanging from the top front edge, Finish. Revolve: the area is taken; click
        the part's top front edge as the axis. A full turn adds three quarters of a round
        bar (Join). 90 and -90: one of them turns into the part and Fusion switches to Cut
        by itself (a quarter groove), the other adds a quarter round; OK on the groove. Then
        the Press Pull before it is edited to 8: the sketch, the edge and the groove follow.
        Ctrl+Z.
Path 7, another command's key while Revolve is open: F with nothing usable picked drops
        the revolve and opens Fillet; Esc. A flat face and an edge picked in the dialog,
        then E: the revolve is kept and Extrude opens; Esc. Ctrl+Z inside the dialog cancels
        only the revolve being made (the earlier steps stay). Ctrl+S with the dialog open
        finishes it first and saves.
Path 8, close and reopen the file: the revolves are there; edit one from the timeline,
        OK; Ctrl+Z.
Path 9, New Body then Ctrl+Z: the new body goes, the first body is the active one again
        and the next command works on it.
Path 10, Revolve started from the SOLID tab while a sketch is still open: the sketch is
        finished, its area is taken (Fusion), the axis is an edge of the part.

Volumes by hand: box 40 x 30 x 15 = 18000; a round bar about an edge from a w x r
rectangle: pi r^2 w (a quarter of it per 90 degrees).
"""

import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore
from PySide6 import QtTest

from SciForgeTests.gui import arrow_input as arrows
from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import revolve_input as ri
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import timeline_input as ti
from SciForgeTests.gui import versions_input as vi

V = App.Vector
PI = math.pi
BOX = 18000.0
s = {}


def doc():
    return App.ActiveDocument


def panel():
    return ri.panel()


def msg():
    p = panel()
    return p.message.text() if p is not None else ""


def dialog_open():
    return bool(Gui.Control.activeDialog())


def near(a, c, tol=1e-6):
    return ri.near(a, c, tol)


def esc():
    h.press(QtCore.Qt.Key_Escape)


def vol():
    return h.solid_volume()


def first_body():
    return doc().getObject(s["body"]) if doc() is not None else None


def body_vol():
    body = first_body()
    return body.Shape.Volume if body is not None and not body.Shape.isNull() else 0.0


def body_shown():
    return ri.shown(first_body())


def invalid():
    return [o.Label for o in doc().Objects if "Invalid" in o.State]


def ring(sketch, point, direction=V(1, 0, 0)):
    """Volume a full turn of the sketch's one area about the line (point, direction) makes
    (Pappus: area x the path of its centre). The area is drawn with the mouse next to an
    edge of the part, so it may sit a hair off the edge: a ring, not a full bar."""
    areas = ri.regions(sketch)
    return ri.pappus(areas[0][1], point, direction) if len(areas) == 1 else 0.0


def rect_size(sketch):
    """(width along the edge, height away from it) of the one area of a sketch."""
    areas = ri.regions(sketch)
    if len(areas) != 1:
        return None
    bb = areas[0][1].BoundBox
    dims = sorted([bb.XLength, bb.YLength, bb.ZLength])
    return dims[2], dims[1]


# == the part ======================================================================================
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("RevolveQAPart")
    h.fit()
    h.ribbon("Create Sketch")


def box_plane():
    pl.click_on_plane(V(12, -8, 0))


def box_rect():
    h.check("sketch on XY", h.in_sketch() is not None)
    h.press("r")


def box_corner():
    si.click(V(0, 0, 0))


def box_size():
    si.move_towards(V(12, 9, 0), V(0.8, 0.6, 0))
    si.type_text("40", enter=False)
    si.tab()
    si.type_text("30")


def box_finish():
    esc()
    h.ribbon("Finish Sketch")


def box_extrude():
    h.fit()
    h.press("e")


def box_ok():
    arrows.type_distance("10")  # Extrude starts at 0 (Fusion): type the distance
    h.task_button("OK")


def box_pull():
    h.check("block 40 x 30 x 10", near(vol(), 12000.0), vol())
    s["body"] = h.body().Name
    h.fit()
    h.click_empty()
    h.press("q")


def pull_top():
    h.click(V(20, 15, 10))


def pull_type():
    from sciforge import presspull_ui

    p = presspull_ui.PressPullPanel.last
    h.check("Press Pull took the top face", p is not None and p.target is not None)
    if p is not None:
        ui.type_into(p.field.widget, "5")


def pull_ok():
    h.task_button("OK")


def part_saved():
    h.check("the part: 40 x 30 x 15", near(vol(), BOX), vol())
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-revolve-qa-"), "revolve_qa.FCStd")
    s["path"] = path
    doc().saveAs(path)  # File > Save As (its file dialog cannot be driven by the test)
    h.check("saved", os.path.isfile(path), path)


# == Path 6: a groove along an edge of the part =====================================================
FRONT_TOP = V(30, 0, 15)  # on the part's top front edge, away from the sketch
FRONT_AXIS = V(0, 0, 15)  # that edge's line (along X)


def p6_sketch():
    h.fit()
    h.click_empty()
    h.ribbon("Create Sketch")


def p6_face():
    h.click(V(30, 0, 7))  # the front face


def p6_rect():
    s["sk"] = h.in_sketch()
    sk = s["sk"]
    h.check("P6 a sketch on the front face", sk is not None)
    if sk is not None:
        h.check(
            "P6 attached to a face of the part",
            str(sk.AttachmentSupport[0][1][0]).startswith("Face"),
            sk.AttachmentSupport,
        )
    h.press("r")


def p6_corner():
    si.click(V(10, 0, 15), approach=V(1.0, 0, -0.6))


def p6_size():
    si.move_towards(V(14, 0, 12), V(0.8, 0, -0.6))
    si.type_text("6", enter=False)
    si.tab()
    si.type_text("4")


def p6_finish():
    esc()
    h.ribbon("Finish Sketch")


def p6_revolve():
    s["rect"] = rect_size(s["sk"])
    h.check("P6 one 6 x 4 area", s["rect"] is not None and near(s["rect"][0], 6.0), s["rect"])
    areas = ri.regions(s["sk"])
    if areas:
        bb = areas[0][1].BoundBox
        h.check("P6 just under the top edge", 14.0 < bb.ZMax <= 15.0 and near(bb.YMax, 0.0), bb)
    s["ring"] = ring(s["sk"], FRONT_AXIS)
    h.fit()
    h.ribbon("Revolve")


def p6_axis():
    p = panel()
    h.check("P6 the area is taken by itself", p is not None and len(p.profiles) == 1)
    h.fit()
    h.click_edge(FRONT_TOP)


def p6_full():
    p = panel()
    if p is None:
        return
    h.check("P6 the part's edge is the axis", p.axis is not None and p.axis[1].startswith("Edge"))
    want = BOX + s["ring"] * 0.75  # the part fills the quarter between its two faces
    h.check("P6 a full turn adds three quarters of a ring", near(vol(), want), (vol(), want))
    h.check("P6 Join", p.operation.currentText() == "Join", p.operation.currentText())
    h.shot("p6-full")
    ui.type_into(p.angle.widget, "90")


def p6_plus90():
    p = panel()
    s["op90"] = p.operation.currentText()
    s["v90"] = vol()
    ui.type_into(p.angle.widget, "-90")


def p6_minus90():
    p = panel()
    quarter = s["ring"] / 4.0
    ops = sorted([s["op90"], p.operation.currentText()])
    h.check(
        "P6 one way cuts, the other joins (auto Cut into the part)", ops == ["Cut", "Join"], ops
    )
    vols = sorted([s["v90"], vol()])
    h.check(
        "P6 a quarter groove one way, a quarter round the other",
        near(vols[0], BOX - quarter) and near(vols[1], BOX + quarter),
        (vols, BOX - quarter, BOX + quarter),
    )
    if p.operation.currentText() != "Cut":
        ui.type_into(p.angle.widget, "90")


def p6_ok():
    p = panel()
    h.check("P6 the groove is shown", p is not None and p.operation.currentText() == "Cut")
    h.shot("p6-groove")
    h.task_button("OK")


def p6_grooved():
    want = BOX - s["ring"] / 4.0
    h.check("P6 the groove is kept", near(vol(), want), (vol(), want))
    h.check("P6 a Groove", [o.TypeId for o in ri.revolves()] == ["PartDesign::Groove"])
    h.check("P6 valid", h.body().Shape.isValid())
    h.check("P6 nothing broken", not invalid(), invalid())
    b.timeline_double_click("Press Pull 1", click_first=True)


def p6_edit_pull():
    from sciforge import presspull_ui

    p = presspull_ui.PressPullPanel.last
    h.check("P6 editing Press Pull 1", p is not None and not p._closed)
    if p is not None:
        ui.type_into(p.field.widget, "8")


def p6_pull_ok():
    h.task_button("OK")


def p6_followed():
    # The axis is the part's edge, now 3 higher; the sketch's rectangle stays where it was
    # drawn (it is not dimensioned to the edge; Fusion keeps it too).
    want = 40 * 30 * 18 - ring(s["sk"], V(0, 0, 18)) / 4.0
    h.check(
        "P6 the part is 18 high and the groove turns about the moved edge",
        near(vol(), want),
        (vol(), want),
    )
    h.check("P6 nothing broken after the edit", not invalid(), invalid())
    groove = ri.revolves()[0] if ri.revolves() else None
    if groove is not None:
        bb = groove.AddSubShape.BoundBox if not groove.AddSubShape.isNull() else None
        h.check("P6 the groove's tool moved up with the top", bb is not None and bb.ZMax > 17.9, bb)
    h.shot("p6-followed")
    ti.ctrl("z")


def p6_undone():
    want = BOX - s["ring"] / 4.0
    h.check("P6 Ctrl+Z: back to 15 high", near(vol(), want), (vol(), want))
    h.check("P6 nothing broken", not invalid(), invalid())
    s["v6"] = vol()


# == Path 7: another command's key while Revolve is open =========================================
RIGHT_FACE = V(40, 12, 6)
RIGHT_TOP = V(40, 20, 15)


def p7_revolve():
    h.fit()
    h.click_empty()
    s["undo"] = doc().UndoCount
    s["objects"] = len(doc().Objects)
    h.ribbon("Revolve")


def p7_f():
    p = panel()
    h.check("P7 Revolve opens with nothing to take", p is not None and not p.profiles)
    b.press_guarded("f")


def p7_fillet():
    h.check("P7 F closed Revolve", panel() is None)
    h.check("P7 Fillet is open", b.blend_panel() is not None, b.blend_panel())
    h.check("P7 nothing was made", len(doc().Objects) == s["objects"], len(doc().Objects))
    esc()


def p7_revolve2():
    h.check("P7 Esc closes Fillet", not dialog_open())
    h.check("P7 undo history unchanged", doc().UndoCount == s["undo"], doc().UndoCount)
    h.check("P7 no undo step left open", not doc().HasPendingTransaction)
    h.fit()
    h.ribbon("Revolve")


def p7_face():
    h.fit()
    h.click(RIGHT_FACE)


def p7_edge():
    p = panel()
    h.check(
        "P7 the flat face is the profile",
        p is not None and len(p.profiles) == 1 and p.profiles[0][1].startswith("Face"),
        p and p.profiles,
    )
    h.click_edge(RIGHT_TOP)


def p7_e():
    p = panel()
    h.check("P7 the edge is the axis", p is not None and p.axis is not None, p and p.axis)
    # a full turn of the 30 x 15 face about its top edge: three quarters stick out
    s["want7"] = s["v6"] + PI * 15.0 * 15.0 * 30.0 * 0.75
    h.check("P7 preview: three quarters of a bar r15", near(vol(), s["want7"]), (vol(), s["want7"]))
    b.press_guarded("e")


def p7_extrude():
    from sciforge import extrude_ui

    e = extrude_ui.ExtrudePanel.last
    h.check("P7 E kept the revolve", near(body_vol(), s["want7"]), (body_vol(), s["want7"]))
    h.check("P7 two revolves now", len(ri.revolves()) == 2, ri.revolves())
    h.check("P7 Extrude is open", e is not None and not e._closed)
    h.check("P7 Revolve is closed", panel() is None)
    esc()


def p7_revolve3():
    h.check("P7 Esc closes Extrude", not dialog_open())
    s["v7"] = vol()
    s["undo"] = doc().UndoCount
    h.fit()
    h.ribbon("Revolve")


def p7_face3():
    h.fit()
    h.click(V(25, 0, 7))  # the front face


def p7_edge3():
    h.click_edge(V(30, 0, 0))  # its bottom edge


def p7_ctrl_z():
    p = panel()
    h.check("P7 a preview to cancel", p is not None and p.target is not None, msg())
    h.check("P7 the preview changed the part", not near(vol(), s["v7"]), vol())
    ti.ctrl("z")


def p7_cancelled():
    h.check("P7 Ctrl+Z in the dialog closes it", not dialog_open())
    h.check("P7 only the revolve being made is gone", near(vol(), s["v7"]), (vol(), s["v7"]))
    h.check("P7 the earlier revolve is still there", len(ri.revolves()) == 2, ri.revolves())
    h.check("P7 undo history unchanged", doc().UndoCount == s["undo"], doc().UndoCount)
    h.check("P7 no undo step left open", not doc().HasPendingTransaction)
    h.check("P7 the part is shown", body_shown())
    h.fit()
    h.ribbon("Revolve")


def p7_face4():
    h.fit()
    h.click(V(25, 0, 7))


def p7_edge4():
    h.click_edge(V(30, 0, 0))


def p7_ctrl_s():
    p = panel()
    h.check("P7 a preview again", p is not None and p.target is not None, msg())
    s["v7s"] = vol()
    ti.ctrl("s")


def p7_describe():
    """Fusion's Save asks for a version description on a saved design; Enter skips it."""
    h.check("P7 the Save dialog asks for a version description", vi.version_dialog() is not None)
    vi.accept_save()


def p7_saved():
    h.check("P7 Ctrl+S finished the dialog first", not dialog_open())
    h.check("P7 the revolve was kept", near(vol(), s["v7s"]), (vol(), s["v7s"]))
    h.check("P7 three revolves", len(ri.revolves()) == 3, ri.revolves())
    h.check("P7 the design is saved", not doc().isTouched() and not b.modified())
    h.check("P7 no pop-up", not h.popups(), h.popups())
    s["v8"] = vol()
    App.closeDocument(doc().Name)


# == Path 8: reopen, edit, undo ======================================================================
def p8_open():
    App.openDocument(s["path"])
    h.fit()


def p8_reopened():
    h.check("P8 reopened: the same part", near(vol(), s["v8"]), (vol(), s["v8"]))
    h.check("P8 three revolves", len(ri.revolves()) == 3, ri.revolves())
    h.check("P8 all computed", not invalid(), invalid())
    titles = [t for t in b.timeline_titles() if t.startswith("Revolve")]
    h.check("P8 the timeline lists them", len(titles) == 3, b.timeline_titles())
    s["title"] = titles[-1] if titles else "Revolve 3"
    b.timeline_double_click(s["title"], click_first=True)


def p8_editing():
    p = panel()
    h.check("P8 editing after reopening", p is not None and p.editing)
    if p is None:
        return
    h.check("P8 the face profile is shown", len(p.profiles) == 1, p.profiles)
    h.check("P8 the edge axis is shown", p.axis is not None, p.axis)
    h.check("P8 no warning", "⚠" not in msg(), msg())
    ui.type_into(p.angle.widget, "-90")


def p8_preview():
    p = panel()
    h.check("P8 the preview changed", p is not None and not near(vol(), s["v8"]), vol())
    h.check("P8 no warning", "⚠" not in msg(), msg())
    s["v8e"] = vol()
    h.task_button("OK")


def p8_ok():
    h.check("P8 OK", not dialog_open())
    h.check("P8 kept", near(vol(), s["v8e"]), vol())
    ti.ctrl("z")


def p8_undone():
    h.check("P8 Ctrl+Z undoes the edit", near(vol(), s["v8"]), (vol(), s["v8"]))
    h.check("P8 nothing broken", not invalid(), invalid())
    h.check("P8 the part is shown", body_shown())


# == Path 9: New Body, then Ctrl+Z ===================================================================
BACK_FACE = V(20, 30, 7)


def p9_revolve():
    s["bodies"] = len(doc().findObjects("PartDesign::Body"))
    h.fit()
    h.click_empty()
    h.ribbon("Revolve")


def p9_face():
    p = panel()
    h.check("P9 Revolve opens", p is not None)
    h.fit()
    # the back face is hidden from the iso view: a person turns the view round
    h.view().viewRear()
    h.view().fitAll()
    QtTest.QTest.qWait(50)
    h.click(BACK_FACE)


def p9_edge():
    p = panel()
    h.check("P9 the back face is the profile", p is not None and len(p.profiles) == 1)
    h.click_edge(V(20, 30, 0))  # its bottom edge


def p9_new_body():
    p = panel()
    h.check("P9 the bottom edge is the axis", p is not None and p.axis is not None, p and p.axis)
    if p is not None:
        b.choose(p.operation, "New Body")


def p9_ok():
    p = panel()
    h.check("P9 no warning", "⚠" not in msg(), msg())
    h.task_button("OK")


def p9_made():
    bodies = doc().findObjects("PartDesign::Body")
    h.check("P9 a new body", len(bodies) == s["bodies"] + 1, bodies)
    from sciforge import commands

    active = commands.active_body()
    h.check("P9 the new body is the active one", active is not None and active.Name != s["body"])
    ti.ctrl("z")


def p9_undone():
    bodies = doc().findObjects("PartDesign::Body")
    h.check("P9 Ctrl+Z: the new body is gone", len(bodies) == s["bodies"], bodies)
    h.check("P9 the part is as it was", near(body_vol(), s["v8"]), body_vol())
    h.fit()
    h.click_empty()
    h.ribbon("Create Sketch")


def p9_sketch():
    h.check("P9 Create Sketch works after the undo", dialog_open())
    h.check("P9 no pop-up", not h.popups(), h.popups())
    h.click(V(10, 20, 15))  # the top face, where the bars added since do not hide it


# == Path 10: Revolve from the SOLID tab while the sketch is open ===================================
def p10_rect():
    s["sk10"] = h.in_sketch()
    sk = s["sk10"]
    h.check("P10 a sketch on the top face", sk is not None)
    if sk is not None:
        from sciforge import extrude

        h.check(
            "P10 in the first body",
            extrude.owner_body(sk) is not None and extrude.owner_body(sk).Name == s["body"],
        )
    h.press("r")


def p10_corner():
    si.click(V(4, 30, 15), approach=V(1.0, -0.6, 0))


def p10_size():
    si.move_towards(V(9, 28, 15), V(0.8, -0.6, 0))
    si.type_text("8", enter=False)
    si.tab()
    si.type_text("3")


def p10_solid_tab():
    esc()  # the rectangle tool, not the sketch
    from sciforge import shell

    tab = shell.ribbon().tab_buttons["solid"]
    QtTest.QTest.mouseClick(tab, QtCore.Qt.LeftButton)


def p10_revolve():
    h.check("P10 still in the sketch", h.in_sketch() is not None)
    s["v10"] = body_vol()
    s["ring10"] = ring(s["sk10"], V(0, 30, 15))
    h.ribbon("Revolve")


def p10_open():
    p = panel()
    h.check("P10 Revolve opens", p is not None)
    h.check("P10 the sketch is finished", h.in_sketch() is None)
    if p is None:
        return
    h.check(
        "P10 the area of that sketch is taken",
        len(p.profiles) == 1 and p.profiles[0][0] is s["sk10"],
        p.profiles,
    )
    h.fit()
    h.click_edge(V(14, 30, 15))  # the part's top back edge, beside the sketch


def p10_axis():
    p = panel()
    h.check("P10 the top back edge is the axis", p is not None and p.axis is not None)
    want = s["v10"] + s["ring10"] * 0.75
    h.check("P10 a full turn adds three quarters of a ring", near(vol(), want), (vol(), want))
    h.shot("p10-from-sketch")
    h.task_button("OK")


def p10_done():
    want = s["v10"] + s["ring10"] * 0.75
    h.check("P10 kept", not dialog_open() and near(vol(), want), (vol(), want))
    h.check("P10 the sketch is hidden", not s["sk10"].ViewObject.Visibility)
    h.check("P10 nothing broken", not invalid(), invalid())


STEPS = [
    new_design,
    box_plane,
    box_rect,
    box_corner,
    box_size,
    box_finish,
    box_extrude,
    box_ok,
    box_pull,
    pull_top,
    pull_type,
    pull_ok,
    part_saved,
    p6_sketch,
    p6_face,
    p6_rect,
    p6_corner,
    p6_size,
    p6_finish,
    p6_revolve,
    p6_axis,
    p6_full,
    p6_plus90,
    p6_minus90,
    p6_ok,
    p6_grooved,
    p6_edit_pull,
    p6_pull_ok,
    p6_followed,
    p6_undone,
    p7_revolve,
    p7_f,
    p7_fillet,
    p7_revolve2,
    p7_face,
    p7_edge,
    p7_e,
    p7_extrude,
    p7_revolve3,
    p7_face3,
    p7_edge3,
    p7_ctrl_z,
    p7_cancelled,
    p7_face4,
    p7_edge4,
    p7_ctrl_s,
    p7_describe,
    p7_saved,
    p8_open,
    p8_reopened,
    p8_editing,
    p8_preview,
    p8_ok,
    p8_undone,
    p9_revolve,
    p9_face,
    p9_edge,
    p9_new_body,
    p9_ok,
    p9_made,
    p9_undone,
    p9_sketch,
    p10_rect,
    p10_corner,
    p10_size,
    p10_solid_tab,
    p10_revolve,
    p10_open,
    p10_axis,
    p10_done,
]

h.run("revolve_qa_part", ti.watched(STEPS))
