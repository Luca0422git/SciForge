# SPDX-License-Identifier: LGPL-2.1-or-later
"""Draft with a Parting Line, Two Side and Symmetric (Fusion's Draft dialog), only real input.

Part: the 40 x 30 x 10 box (blend_steps.box_steps) and a construction plane 5 mm under its top
(CONSTRUCT > Offset Plane: click the top face, type -5, OK): the parting plane at z = 5.

Path D1, MODIFY > Draft with nothing selected: choose Type Parting Line (the Parting Tool box
        and Fix / Move Parting Line appear; Move is greyed with the reason); click the top face
        (the pull direction: up); OK now is refused with what is missing (the parting tool);
        click the plane's row in the browser (the parting tool); click the front and the right
        faces: One Side drafts only what lies above the parting line (1 deg).
Path D2, Draft Sides Two Side: Angle 1 = 5, Angle 2 = 3: above the line the faces lean in by
        5 deg toward the pull direction, below by 3 deg the other way. OK: SciForge's own
        Draft step, "Draft 1" in the timeline; Ctrl+Z / Ctrl+Y.
Path D3, the step edited from the timeline: it opens on Parting Line, Two Side, 5 / 3; choose
        Symmetric, type 4: both sides lean 4 deg; OK.
Path D4, Draft again, Esc: nothing changes.

Hand-derived volumes (h = 5 on each side of the line; front 40 long, right 30):
  a wedge pair leaning by a over h:  70 h^2 tan(a) / 2 - h^3 tan(a)^2 / 3 taken away
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import inspect_steps as ins
from SciForgeTests.gui import modify2_steps as m
from SciForgeTests.gui import shell_draft_steps as sd

V = App.Vector
s = {}
TOP = V(20, 15, 10)
FRONT_UP = V(20, 0, 8)
RIGHT_UP = V(40, 15, 8)
BOX = 12000.0


def removed(a, height=5.0):
    t = m.tan(a)
    return 70.0 * height * height * t / 2.0 - height**3 * t * t / 3.0


def panel():
    return m.panel_of("draft_ui", "DraftPanel")


def plane():
    name = s.get("plane")
    return App.ActiveDocument.getObject(name) if name else None


# -- the parting plane -------------------------------------------------------------------------
def offset_start():
    h.click_empty()
    h.fit()
    h.ribbon("Offset Plane")


def offset_top():
    h.click(V(32, 5, 10))


def offset_distance():
    p = ins.construct_panel()
    if h.check("Offset Plane open on the top face", p is not None and p.picks[0]):
        b.type_into(p.distance.widget, "-5")


def offset_ok():
    h.task_button("OK")


def plane_made():
    found = [o for o in h.body().Group if o.TypeId == "PartDesign::Plane"]
    h.check("a construction plane made", len(found) == 1, found)
    if found:
        s["plane"] = found[0].Name
        z = found[0].Placement.Base.z
        h.check("it is 5 mm under the top: z = 5", abs(z - 5.0) < 1e-6, z)
    h.check("the box is unchanged", m.close(h.solid_volume(), BOX), h.solid_volume())


# -- D1 -------------------------------------------------------------------------------------------
def draft_start():
    Gui.Selection.clearSelection()
    h.click_empty()
    sd.modify_menu("Draft")


def waiting():
    p = panel()
    h.check("Draft dialog open", p is not None and Gui.Control.activeDialog())
    if p is None:
        return
    labels = [p.type.itemText(i) for i in range(p.type.count())]
    h.check("Type: Fixed Plane, Parting Line", labels == ["Fixed Plane", "Parting Line"], labels)
    h.check("Parting Line can be chosen", m.item_enabled(p.type, "Parting Line")[1])
    sides = [p.sides.itemText(i) for i in range(p.sides.count())]
    h.check(
        "Draft Sides: One Side, Two Side, Symmetric",
        sides == ["One Side", "Two Side", "Symmetric"],
        sides,
    )
    h.check("every Draft Sides choice is open", all(m.item_enabled(p.sides, x)[1] for x in sides))
    h.check("no Parting Tool box for a fixed plane", not p.parting_box.widget.isVisible())
    h.check("choose Parting Line", b.choose(p.type, "Parting Line"))


def parting_rows():
    p = panel()
    if p is None:
        return
    h.check("the Parting Tool box shows", p.parting_box.widget.isVisible())
    h.check("Parting Line Type shows", p.mode.isVisible())
    present, enabled, tip = m.item_enabled(p.mode, "Move Parting Line")
    h.check("Move Parting Line is listed but greyed", present and not enabled)
    h.check("the reason is in its tooltip", "Fix Parting Line" in tip, tip)
    h.check("still waits for the pull direction", p.active == "plane", p.active)
    h.shot("1-parting-line")
    h.fit()
    h.click(TOP)


def pull_picked():
    p = panel()
    if p is None:
        return
    h.check(
        "the top face is the pull direction",
        p.plane_ref is not None and p.plane_ref[1].startswith("Face"),
        p.plane_ref,
    )
    h.check("the Parting Tool box takes the clicks now", p.active == "parting", p.active)
    h.check("no step yet", p.target is None)
    h.task_button("OK")


def ok_refused():
    p = panel()
    h.check("OK waits", p is not None)
    text = m.message(p)
    h.check("it says the parting tool is missing", "parting tool" in text.lower(), text)
    m.click_row(plane().Label if plane() else "Plane")


def parting_picked():
    p = panel()
    if p is None:
        return
    h.check(
        "the plane is the parting tool",
        len(p.parting) == 1 and p.parting[0][0] is plane(),
        p.parting,
    )
    h.check("the Faces box takes the clicks", p.active == "faces", p.active)
    h.check(
        "the box names it",
        plane().Label in p.parting_box.button.text(),
        p.parting_box.button.text(),
    )
    h.fit()
    h.click(FRONT_UP)


def front_up():
    h.click(RIGHT_UP)


def one_side():
    p = panel()
    if p is None:
        return
    h.check("front and right faces picked", len(p.names()) == 2, p.names())
    v = h.solid_volume()
    want = BOX - removed(1.0)
    h.check("One Side: only above the line, 1 deg", m.close(v, want), (v, want))
    h.check(
        "SciForge's own Draft step",
        p.target is not None and getattr(p.target, "SciForgeType", "") == "Draft",
    )
    h.shot("2-one-side")
    h.check("choose Two Side", b.choose(p.sides, "Two Side"))


def two_side_rows():
    p = panel()
    if p is None:
        return
    h.check("Angle 2 shows for Two Side", p.angle2.widget.isVisible())
    h.check("the first angle is Angle 1", p.angle_label.text() == "Angle 1", p.angle_label.text())
    sd.type_into(p.angle.widget, "5")


def angle2():
    p = panel()
    if p:
        sd.type_into(p.angle2.widget, "3")


def two_side():
    v = h.solid_volume()
    want = BOX - removed(5.0) - removed(3.0)
    h.check("Two Side: 5 deg above, 3 deg below", m.close(v, want), (v, want))
    h.shot("3-two-side")


def ok():
    h.task_button("OK")


def after_ok():
    h.check("dialog closed", m.no_dialog())
    shape = h.body().Shape
    want = BOX - removed(5.0) - removed(3.0)
    h.check("kept: two sides drafted", m.close(shape.Volume, want), (shape.Volume, want))
    h.check("valid solid", shape.isValid())
    h.check("8 faces (front and right split at the line)", len(shape.Faces) == 8, len(shape.Faces))
    tip = h.body().Tip
    h.check("the Draft is the body's end", getattr(tip, "SciForgeType", "") == "Draft", tip.Name)
    h.check("timeline shows Draft 1", "Draft 1" in sd.timeline_titles(), sd.timeline_titles())
    h.check("no errors in the Report view", not sd.report_errors(), sd.report_errors())
    h.check("no leftover selection", not Gui.Selection.getSelectionEx(), m.selected_names())
    h.check(
        "one undo step: Draft",
        App.ActiveDocument.UndoNames[:1] == ["Draft"],
        App.ActiveDocument.UndoNames,
    )
    s["two"] = shape.Volume


def undo():
    m.undo()


def after_undo():
    d = App.ActiveDocument
    h.check(
        "Ctrl+Z takes the draft away",
        m.close(h.solid_volume(), BOX),
        (h.solid_volume(), d.UndoNames, d.RedoNames),
    )


def redo():
    m.redo()


def after_redo():
    h.check("Ctrl+Y brings it back", m.close(h.solid_volume(), s["two"]), h.solid_volume())
    h.fit()


# -- D3 -------------------------------------------------------------------------------------------
def edit():
    sd.timeline_double_click("Draft 1")


def edit_open():
    p = panel()
    h.check("the Draft dialog opens on the step", p is not None and p.editing)
    if p is None:
        return
    h.check("it reads Parting Line", p.type.currentText() == "Parting Line", p.type.currentText())
    h.check("it reads Two Side", p.sides.currentText() == "Two Side", p.sides.currentText())
    h.check("angles 5 and 3", abs(p.angle.value() - 5) < 1e-9 and abs(p.angle2.value() - 3) < 1e-9)
    h.check("the parting tool is the plane", len(p.parting) == 1 and p.parting[0][0] is plane())
    h.check("its two faces", len(p.names()) == 2, p.names())
    h.shot("4-edit")
    h.check("choose Symmetric", b.choose(p.sides, "Symmetric"))


def symmetric():
    p = panel()
    if p is None:
        return
    h.check("one angle for Symmetric", not p.angle2.widget.isVisible())
    sd.type_into(p.angle.widget, "4")


def symmetric_preview():
    v = h.solid_volume()
    want = BOX - 2 * removed(4.0)
    h.check("Symmetric: 4 deg each way", m.close(v, want), (v, want))
    h.task_button("OK")


def after_edit():
    h.check("dialog closed", m.no_dialog())
    v = h.solid_volume()
    h.check("kept: symmetric 4 deg", m.close(v, BOX - 2 * removed(4.0)), v)
    drafts = m.objects(kind="Draft")
    h.check("still one Draft step", len(drafts) == 1, drafts)
    s["sym"] = v


# -- D4 -------------------------------------------------------------------------------------------
def esc_start():
    h.click_empty()
    sd.modify_menu("Draft")


def esc_pick():
    h.fit()
    h.click(TOP)


def esc_press():
    h.check("a second Draft dialog", panel() is not None)
    h.press(QtCore.Qt.Key_Escape)


def after_esc():
    h.check("Esc closes it", m.no_dialog())
    h.check("the part is as it was", m.close(h.solid_volume(), s["sym"]), h.solid_volume())
    h.check("no new step", len(m.objects(kind="Draft")) == 1)
    h.check("no errors in the Report view", not sd.report_errors(), sd.report_errors())
    h.shot("5-end")


h.run(
    "modify2_draft",
    sd.box_steps("Modify2Draft")
    + [
        offset_start,
        offset_top,
        offset_distance,
        offset_ok,
        plane_made,
        draft_start,
        waiting,
        parting_rows,
        pull_picked,
        ok_refused,
        parting_picked,
        front_up,
        one_side,
        two_side_rows,
        angle2,
        two_side,
        ok,
        after_ok,
        undo,
        after_undo,
        redo,
        after_redo,
        edit,
        edit_open,
        symmetric,
        symmetric_preview,
        after_edit,
        esc_start,
        esc_pick,
        esc_press,
        after_esc,
    ],
)
