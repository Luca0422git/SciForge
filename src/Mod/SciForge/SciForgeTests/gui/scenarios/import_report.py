# SPDX-License-Identifier: LGPL-2.1-or-later
"""What an import did not bring in (sciforge/export_report*.py): the short message after
Insert Mesh, Insert DXF and File > Open of a STEP file; only real input (the system's file
dialogs are the only stand-ins). The files are made at the start
(SciForgeTests/golden/export_checks.make_import_file, the golden models' own files).

A  INSERT > Insert Mesh with open_box.stl (a box with one side missing), OK: the message
   "Inserted open_box.stl / Not brought in, or changed:" says the mesh is not closed (4 open
   edges); no pop-up.
B  UTILITIES > Export, STL of the design (only that mesh body): the export message says
   only that the mesh body is not closed (an inserted mesh has no history of its own).
C  A new design, Insert Mesh with the closed box_20x10x5.stl, OK, then Export STL: nothing
   is wrong and nothing is lost, so no message either time.
D  INSERT > Insert DXF with extras.dxf, click the XY square, OK: the message lists the hatch
   FreeCAD cannot read, the text and the point (only curves go into the sketch).
E  Ctrl+O, mixed.step (one part: a solid, 5 loose faces, a line): a new design with one
   body; the message says the 5 loose faces and the curve did not come in.
"""

import os
import shutil

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as i
from SciForgeTests.gui import plane_input as pl

OUT = os.path.join(i.OUT, "import_report")
state = {}


def notice_text():
    from sciforge import export_report_ui

    n = export_report_ui.current()
    if n is None:
        return ""
    return "%s\n%s\n%s" % (n.title.text(), n.lead.text(), n.body.text())


def recent_count():
    from sciforge import export_report_ui

    return len(export_report_ui.recent())


def setup():
    from SciForgeTests.golden import export_checks

    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    for name in ("open_box.stl", "extras.dxf", "mixed.step"):
        state[name] = export_checks.make_import_file(name, OUT)
    i.record_exports()


# -- A ----------------------------------------------------------------------------------------
def a_open():
    i.use_file(state["open_box.stl"])
    h.fit()
    h.ribbon("Insert Mesh")


a_open.wait_ms = 1500


def a_ok():
    p = i.panel()
    if h.check("Insert Mesh dialog", p is not None and p.title == "Insert Mesh", p):
        h.task_button("OK")


a_ok.wait_ms = 1200


def a_check():
    text = notice_text()
    h.check("A the message shows", bool(text), text)
    h.check("A titled after the file", "Inserted open_box.stl" in text, text)
    h.check("A lead", "Not brought in, or changed:" in text, text)
    h.check("A the mesh is not closed: 4 open edges", "4 open edges" in text, text)
    s.no_popups("Insert Mesh (the message is no pop-up)")
    h.check(
        "A the Report view has the line",
        "[SciForge] Inserted open_box.stl. Not brought in, or changed:" in h.report_text(),
        h.report_text()[-600:],
    )
    state["recent"] = recent_count()
    h.shot("mesh-message")


# -- B, C: export of mesh bodies -------------------------------------------------------------
def export_stl(name):
    def step():
        from sciforge import export_ui

        h.fit()
        i.ribbon_tab("UTILITIES")
        h.ribbon("Export")
        d = export_ui.ExportDialog.last
        if h.check("Export dialog", d is not None and d.isVisible()):
            b.choose(d.type, "STL (Binary)")
            b.type_into(d.folder, OUT)
            b.type_into(d.name, name)

    step.__name__ = "export_stl_" + name
    return step


def press_export():
    from sciforge import export_ui

    d = export_ui.ExportDialog.last
    if d is not None and d.isVisible():
        b.click_widget(d.export_button)


press_export.wait_ms = 1500


def b_check():
    h.check("B open_mesh.stl written", os.path.isfile(os.path.join(OUT, "open_mesh.stl")))
    text = notice_text()
    h.check("B the export message", "Exported open_mesh.stl" in text, text)
    h.check("B the mesh body is not closed", "1 mesh body not closed" in text, text)
    h.check("B nothing else (no history in an inserted mesh)", text.count("\u2022") == 1, text)
    state["recent"] = recent_count()


def c_insert_closed():
    i.use_file(i.fixture("box_20x10x5.stl"))
    h.fit()
    i.ribbon_tab("SOLID")
    h.ribbon("Insert Mesh")


c_insert_closed.wait_ms = 1500


def c_ok():
    p = i.panel()
    if h.check("Insert Mesh dialog (closed box)", p is not None and p.title == "Insert Mesh", p):
        h.task_button("OK")


c_ok.wait_ms = 1200


def c_check_insert():
    h.check("C clean mesh: no message", recent_count() == state.get("recent"), recent_count())


def c_check_export():
    h.check("C box.stl written", os.path.isfile(os.path.join(OUT, "box.stl")))
    h.check("C nothing lost: no message", recent_count() == state.get("recent"), recent_count())


# -- D ----------------------------------------------------------------------------------------
def d_open_dxf():
    i.use_file(state["extras.dxf"])
    h.fit()
    i.ribbon_tab("SOLID")
    i.menu("INSERT", "Insert DXF")


d_open_dxf.wait_ms = 1500


def d_click_xy():
    p = i.panel()
    if h.check("Insert DXF dialog", p is not None and p.title == "Insert DXF", p):
        pl.click_on_plane(i.XY_CLICK)


d_click_xy.wait_ms = 1200


def d_ok():
    h.task_button("OK")


d_ok.wait_ms = 1500


def d_check():
    text = notice_text()
    h.check("D the message shows", "Inserted extras.dxf" in text, text)
    h.check("D the hatch FreeCAD cannot read", "1 hatch (FreeCAD cannot read them)" in text, text)
    h.check("D the text", "1 text or dimension" in text, text)
    h.check("D the point", "1 point" in text, text)
    sk = i.sketches()[-1] if i.sketches() else None
    h.check(
        "D the line and the circle are in the sketch",
        sk is not None and sk.GeometryCount == 2,
        sk and sk.GeometryCount,
    )


def d_leave_sketch():
    if h.in_sketch() is not None:
        h.ribbon("Finish Sketch")


# -- E ----------------------------------------------------------------------------------------
def e_open():
    from SciForgeTests.gui import exchange_steps as x

    x.use_open_file(state["mixed.step"])
    h.press(QtCore.Qt.Key_O, QtCore.Qt.ControlModifier)


e_open.wait_ms = 2500


def e_check():
    from sciforge import bodies
    from SciForgeTests.gui import exchange_steps as x

    x.use_open_file(None)
    doc = App.ActiveDocument
    h.check("E a new design 'mixed'", doc is not None and doc.Label == "mixed", doc and doc.Label)
    found = bodies.list_bodies(doc) if doc else []
    h.check("E one body (the solid)", len(found) == 1, [f.Label for f in found])
    text = notice_text()
    h.check("E the message shows", "Opened mixed.step" in text, text)
    h.check("E 5 loose faces", "5 loose faces" in text, text)
    h.check("E the line", "1 curve or point" in text, text)
    s.no_popups("Open STEP")
    h.shot("end")


h.run(
    "import_report",
    [
        i.new_design("ImportReport"),
        setup,
        a_open,
        a_ok,
        a_check,
        export_stl("open_mesh"),
        press_export,
        b_check,
        i.new_design("ImportReportClean"),
        c_insert_closed,
        c_ok,
        c_check_insert,
        export_stl("box"),
        press_export,
        c_check_export,
        d_open_dxf,
        d_click_xy,
        d_ok,
        d_check,
        d_leave_sketch,
        e_open,
        e_check,
    ],
)
