# SPDX-License-Identifier: LGPL-2.1-or-later
"""Insert Derive (INSERT menu), only real input (docs/sciforge/parity/misc.md).

Source design Bracket.FCStd (saved, closed): component "Arm" moved 10 mm along X holding Body1
(a box 20 x 10 x 5 = 1000), the sketch "Outline" (a line and a circle), the construction plane
"Top Plane" (z 5) and the user parameter width = 12 mm.

P1 INSERT > Insert Derive in a new, unsaved design: the Save dialog comes first (the source is
   kept relative to this design's file); after the save the Derive dialog lists Bodies,
   Sketches, Construction and Parameters with tick boxes. Tick Body1, Outline, Top Plane and
   width; OK: one Derive step in the timeline; Body1 (1000) at x 10..30 (where it is in the
   source design); the sketch's curves fixed; the plane at z 5; width = 12 shown greyed in
   Change Parameters and usable in a formula.
P2 A cylinder step added on the derived body (work built on it).
P3 Bracket saved again with a 40 mm box and width 15: the Derive turns yellow (out of date) in
   the timeline and a note says so.
P4 Right-click the Derive > Update Derive: Body1 is 2000 + the cylinder, width 15, up to date.
P5 Ctrl+Z: back to 1000 (+ cylinder), out of date; Ctrl+Y: 2000 again.
P6 Double-click the Derive (Edit Derive): untick Outline, tick Place Objects At Origin, OK: the
   sketch is gone, Body1 at x 0..40 (the Arm's own origin).
P7 Ctrl+S: saved, the source kept as "Bracket.FCStd" (relative); closed and opened again: the
   Derive is there, up to date, Body1 2000 + cylinder, width 15.
P8 Insert Derive, then Cancel: nothing added. Insert Derive of the design itself: refused with
   the reason.
"""

import math
import os

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import misc_steps as m
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import timeline_input as t
from SciForgeTests.gui import versions_input as vi

V = App.Vector
s = {}
CYL = math.pi * 2 * 2 * 5


def doc():
    return App.getDocument(s["doc"]) if s.get("doc") in App.listDocuments() else None


def master():
    from sciforge import derive

    d = doc()
    found = derive.masters(d) if d is not None else []
    return found[0] if found else None


def derived(kind):
    from sciforge import derive

    mm = master()
    if mm is None:
        return []
    if kind == "body":
        return derive.result_bodies(mm)
    return [
        o
        for o in derive.result_steps(mm)
        if (o.TypeId == "Sketcher::SketchObject") == (kind == "sketch")
    ]


def body_volume():
    found = derived("body")
    return found[0].Shape.Volume if found and not found[0].Shape.isNull() else None


def setup():
    from sciforge import derive_ui

    Gui.activateWorkbench("SciForgeWorkbench")
    s["folder"] = m.project_folder()
    s["source"] = m.make_box_design(s["folder"], "Bracket", component="Arm", offset=V(10, 0, 0))
    derive_ui.FILE_PICKER = lambda title: s["pick"]
    s["pick"] = s["source"]
    d = App.newDocument("Assembly")
    s["doc"] = d.Name
    h.fit()
    h.check("Bracket saved and closed", os.path.isfile(s["source"]))


# -- P1 ----------------------------------------------------------------------------------------
def p1_open():
    si.menu_item("INSERT", "Insert Derive")


p1_open.wait_ms = 1500


def p1_save_first():
    d = vi.save_dialog()
    h.check("P1 an unsaved design is saved first", d is not None, h.popups())
    h.check("P1 the reason is said", "Save the design first" in m.told(), m.told())
    vi.fill_save_dialog(name="Assembly")
    vi.click_save()


p1_save_first.wait_ms = 2500


def p1_dialog():
    p = m.derive_panel()
    h.check("P1 the Derive dialog opened after the save", p is not None, h.popups())
    if p is None:
        return
    h.check("P1 the design was saved", bool(doc().FileName))
    groups = [p.tree.topLevelItem(i).text(0) for i in range(p.tree.topLevelItemCount())]
    h.check(
        "P1 the source's browser: Bodies, Sketches, Construction, Parameters",
        groups == ["Bodies", "Sketches", "Construction", "Parameters"],
        groups,
    )
    h.check("P1 nothing ticked yet", p.ticked() == [], p.ticked())
    text = p.item_for("body:Body").text(0) if p.item_for("body:Body") else ""
    h.check("P1 Body1 shown in its component", text == "Arm > Body1", text)
    h.shot("1-dialog")
    for key in ("body:Body", "sketch:Sketch", "construction:DatumPlane", "parameter:width"):
        m.tick(p, key)


def p1_ok():
    p = m.derive_panel()
    h.check("P1 the dialog says what comes in", p is not None and "Brings in" in p.info.text())
    h.task_button("OK")


p1_ok.wait_ms = 1500


def p1_check():
    from sciforge import parameters

    d = doc()
    mm = master()
    h.check("P1 a Derive step", mm is not None)
    if mm is None:
        return
    title = m.timeline_title(mm)
    h.check("P1 the timeline shows the Derive", title is not None and "Derive" in title, title)
    h.check("P1 only one new step in the timeline", len(t.titles()) == 1, t.titles())
    h.check("P1 Body1 derived (1000)", m.near(body_volume(), 1000.0), body_volume())
    b = derived("body")[0]
    box = b.Shape.BoundBox
    h.check(
        "P1 where it is in the source (x 10..30)",
        m.near(box.XMin, 10) and m.near(box.XMax, 30),
        box,
    )
    h.check("P1 the derived body keeps its name", b.Label == "Body1", b.Label)
    sketches = derived("sketch")
    h.check("P1 the sketch Outline derived", len(sketches) == 1 and sketches[0].Label == "Outline")
    if sketches:
        sk = sketches[0]
        blocks = [c for c in sk.Constraints if c.Type == "Block"]
        h.check("P1 its two curves, fixed", sk.GeometryCount == 2 and len(blocks) == 2)
    planes = [o for o in derived("construction")]
    h.check(
        "P1 the plane at z 5",
        len(planes) == 1 and m.near(planes[0].getGlobalPlacement().Base.z, 5),
        [p.Placement for p in planes],
    )
    h.check("P1 width derived (12)", m.near(d.getObject("Parameters").width.Value, 12.0))
    h.check(
        "P1 width is a derived parameter, not one of the user's own",
        parameters.derived_names(d) == ["width"] and parameters.own_names(d) == [],
    )
    h.check("P1 the browser lists Body1", "Body1" in t.labels(), t.labels())
    h.check("P1 up to date", mm.SourceStamp and "Bracket" == mm.SourceName)
    h.shot("1-derived")


def p1_parameters_dialog():
    from sciforge import parameters_ui

    Gui.runCommand("SciForge_ChangeParameters")
    m.process()
    dialog = parameters_ui.ParametersDialog.last
    h.check("P1 Change Parameters opened", dialog is not None and dialog.isVisible())
    if dialog is None:
        return
    rows = [dialog.user.item(r, 0).text() for r in range(dialog.user.rowCount())]
    h.check("P1 width listed", rows == ["width"], rows)
    item = dialog.user.item(0, 2)
    h.check(
        "P1 greyed: it cannot be typed over",
        item is not None and not (item.flags() & QtCore.Qt.ItemIsEditable),
    )
    comment = dialog.user.item(0, 4).text() if dialog.user.item(0, 4) else ""
    h.check("P1 its comment names the source", "Bracket" in comment, comment)
    dialog.reject()


# -- P2 ----------------------------------------------------------------------------------------
def p2_build_on():
    d = doc()
    b = derived("body")[0]
    cyl = b.newObject("PartDesign::AdditiveCylinder", "Cylinder")
    cyl.Radius, cyl.Height = 2, 5
    cyl.Placement.Base = V(20, 5, 5)
    b.Tip = cyl
    d.recompute()
    h.check("P2 a cylinder on the derived body", m.near(body_volume(), 1000 + CYL), body_volume())


# -- P3 ----------------------------------------------------------------------------------------
def p3_change_source():
    from sciforge import parameters

    def change(src):
        src.getObject("Box").Length = 40
        parameters.set_user(src, "width", "15")

    m.edit_saved(s["source"], change)
    Gui.getDocument(s["doc"]).ActiveView  # the destination in front again
    App.setActiveDocument(s["doc"])
    Gui.setActiveDocument(s["doc"])


p3_change_source.wait_ms = 2000


def p3_out_of_date():
    from sciforge import derive, derive_core

    mm = master()
    h.check("P3 the Derive is out of date", derive.state(mm) == derive_core.NEWER)
    item = m.timeline_item(mm)
    h.check(
        "P3 yellow in the timeline with the reason",
        item is not None and item.status == "warning" and "Out of date" in item.message,
        item and (item.status, item.message),
    )
    h.check("P3 a note says so", "out of date" in m.told(), m.told())
    h.check("P3 nothing changed yet", m.near(body_volume(), 1000 + CYL), body_volume())
    entries = t.menu_entries(m.timeline_title(mm))
    h.check(
        "P3 right-click offers Update Derive and Break Link",
        ("Update Derive", True) in entries and ("Break Link", True) in entries,
        entries,
    )
    h.shot("3-out-of-date")


# -- P4 ----------------------------------------------------------------------------------------
def p4_update():
    t.menu(m.timeline_title(master()), "Update Derive")


p4_update.wait_ms = 2000


def p4_check():
    from sciforge import derive, derive_core

    mm = master()
    h.check(
        "P4 Body1 follows: 2000 + the cylinder", m.near(body_volume(), 2000 + CYL), body_volume()
    )
    h.check("P4 width 15", m.near(doc().getObject("Parameters").width.Value, 15.0))
    h.check("P4 up to date", derive.state(mm) == derive_core.UP_TO_DATE)
    item = m.timeline_item(mm)
    h.check("P4 no longer yellow", item is not None and item.status == "ok", item and item.status)


# -- P5 ----------------------------------------------------------------------------------------
def p5_undo():
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


p5_undo.wait_ms = 1200


def p5_undone():
    from sciforge import derive, derive_core

    h.check("P5 Ctrl+Z: 1000 + cylinder again", m.near(body_volume(), 1000 + CYL), body_volume())
    h.check("P5 out of date again", derive.state(master()) == derive_core.NEWER)
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


p5_undone.wait_ms = 1200


def p5_redone():
    h.check("P5 Ctrl+Y: 2000 + cylinder", m.near(body_volume(), 2000 + CYL), body_volume())


# -- P6 ----------------------------------------------------------------------------------------
def p6_edit():
    t.double_click(m.timeline_title(master()))


p6_edit.wait_ms = 1500


def p6_change():
    p = m.derive_panel()
    h.check("P6 Edit Derive opened", p is not None and p.mode == "edit", p)
    if p is None:
        return
    h.check("P6 the four items ticked", len(p.ticked()) == 4, p.ticked())
    h.check(
        "P6 it says it is up to date", "Up to date" in p.state_label.text(), p.state_label.text()
    )
    m.tick(p, "sketch:Sketch", False)
    m.set_check(p.origin, True)


def p6_ok():
    h.task_button("OK")


p6_ok.wait_ms = 1500


def p6_check():
    h.check("P6 the sketch is gone", derived("sketch") == [], derived("sketch"))
    h.check("P6 no sketch named Outline left", not any(o.Label == "Outline" for o in doc().Objects))
    b = derived("body")
    box = b[0].Shape.BoundBox if b else None
    h.check(
        "P6 Body1 at the Arm's origin (x 0..40)",
        box is not None and m.near(box.XMin, 0) and m.near(box.XMax, 40),
        box,
    )
    h.check("P6 still 2000 + cylinder", m.near(body_volume(), 2000 + CYL), body_volume())
    h.check("P6 the Derive remembers it", master().PlaceAtOrigin and len(master().Items) == 3)


# -- P7 ----------------------------------------------------------------------------------------
def p7_save():
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


def p7_accept():
    h.check("P7 the version dialog", vi.accept_save())


p7_accept.wait_ms = 1500


def p7_reopen():
    path = doc().FileName
    s["path"] = path
    h.check("P7 saved", not Gui.getDocument(s["doc"]).Modified)
    h.check(
        "P7 the source kept by its relative path",
        master().SourceRelative == "Bracket.FCStd",
        master().SourceRelative,
    )
    m.close_all()
    d = App.openDocument(path)
    s["doc"] = d.Name


p7_reopen.wait_ms = 2500


def p7_check():
    from sciforge import derive, derive_core

    mm = master()
    h.check("P7 the Derive is back", mm is not None)
    if mm is None:
        return
    h.check("P7 up to date", derive.state(mm) == derive_core.UP_TO_DATE)
    h.check("P7 Body1 2000 + cylinder", m.near(body_volume(), 2000 + CYL), body_volume())
    h.check("P7 width 15", m.near(doc().getObject("Parameters").width.Value, 15.0))
    item = m.timeline_item(mm)
    h.check("P7 not yellow", item is not None and item.status == "ok", item and item.status)
    h.fit()


# -- P8 ----------------------------------------------------------------------------------------
def p8_open():
    s["count"] = len(doc().Objects)
    si.menu_item("INSERT", "Insert Derive")


p8_open.wait_ms = 1500


def p8_cancel():
    p = m.derive_panel()
    h.check("P8 the dialog opened", p is not None)
    h.task_button("Cancel")


p8_cancel.wait_ms = 1000


def p8_self():
    h.check("P8 Cancel added nothing", len(doc().Objects) == s["count"])
    h.check("P8 still one Derive", len(t.titles()) == 2, t.titles())  # Derive + Cylinder
    s["pick"] = s["path"]
    si.menu_item("INSERT", "Insert Derive")


p8_self.wait_ms = 1500


def p8_refused():
    h.check("P8 no dialog for the design itself", m.derive_panel() is None)
    h.check("P8 the reason is said", "cannot derive from itself" in m.told(), m.told())


def cleanup():
    from sciforge import derive_ui

    derive_ui.FILE_PICKER = None
    m.close_all()
    h.new_errors()


h.run(
    "misc_derive",
    [
        setup,
        p1_open,
        p1_save_first,
        p1_dialog,
        p1_ok,
        p1_check,
        p1_parameters_dialog,
        p2_build_on,
        p3_change_source,
        p3_out_of_date,
        p4_update,
        p4_check,
        p5_undo,
        p5_undone,
        p5_redone,
        p6_edit,
        p6_change,
        p6_ok,
        p6_check,
        p7_save,
        p7_accept,
        p7_reopen,
        p7_check,
        p8_open,
        p8_cancel,
        p8_self,
        p8_refused,
        cleanup,
    ],
)
