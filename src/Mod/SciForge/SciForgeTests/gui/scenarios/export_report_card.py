# SPDX-License-Identifier: LGPL-2.1-or-later
"""The export report card in the real window (sciforge/export_report_ui.py), the problems a
review found on 2026-10-22 (docs/sciforge/sessions/2026-10-22-fix-export.md):

Design: box1 and box2 drawn and extruded (box2 a New Body, then made into the component
"Lid"), and a mesh body (a 10 mm cube) beside them; saved as Bracket.FCStd (setup).

A  UTILITIES > MAKE > Export Everything: the card lists, among others, the component as
   lost in all four files (the STEP is written body by body, flat: no "(STL, 3MF, OBJ)"
   after it, F3) and the mesh body as not in the STEP but in the STL, 3MF and OBJ, without
   the advice to export it as STL, 3MF or OBJ (F8). The title wraps (four file names) and
   several lines wrap: every line is still fully inside the card (F1).
B  Export, 3MF, Selected bodies with only the mesh body ticked: nothing is lost, so no new
   card, and the Export Everything card is gone too (it would read as if it described
   this export, F6).
C  The window made 1100 x 700 and Export Everything again: the card does not cover the
   navigation bar (F7), it is inside the 3D view and every line shows (F1).
"""

import os
import shutil

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as i

OUT = os.path.join(i.OUT, "export_report_card")
state = {}


def notice():
    from sciforge import export_report_ui

    return export_report_ui.current()


def notice_text():
    n = notice()
    if n is None:
        return ""
    return "%s\n%s\n%s" % (n.title.text(), n.lead.text(), n.body.text())


def navbar_rect(n):
    from sciforge import navbar_ui

    bar = navbar_ui.bar()
    if bar is None or not bar.isVisible():
        return None
    return QtCore.QRect(bar.mapTo(n.parentWidget(), QtCore.QPoint(0, 0)), bar.size())


def check_lines_fit(tag):
    """Every label gets the height its wrapped text needs, inside the card."""
    n = notice()
    if not h.check("%s card shown" % tag, n is not None):
        return
    for name in ("title", "lead", "body"):
        label = getattr(n, name)
        need = label.heightForWidth(label.width()) if label.wordWrap() else label.sizeHint().height()
        geo = label.geometry()
        h.check(
            "%s every line of the card's %s shows" % (tag, name),
            geo.height() >= need and geo.bottom() < n.height(),
            (name, need, geo, n.size()),
        )


def setup():
    import Mesh

    from sciforge import bodies, components, export_report_ui, insert

    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    doc = App.ActiveDocument
    doc.saveAs(os.path.join(OUT, "Bracket.FCStd"))
    i.record_exports(folder=OUT)
    second = bodies.list_bodies(doc)[1]
    made = components.from_bodies(doc, [second])
    made[0].Label = "Lid"
    cube = insert.make_mesh_body(doc, Mesh.createBox(10, 10, 10), os.path.join(OUT, "cube.stl"))
    cube.Placement.Base = App.Vector(0, 60, 0)
    doc.recompute()
    state["mesh"] = cube.Name
    export_report_ui.clear_recent()
    h.fit()


# -- A ----------------------------------------------------------------------------------------
def a_everything():
    i.ribbon_tab("UTILITIES")
    i.menu("MAKE", "Export Everything")


a_everything.wait_ms = 4000


def a_check():
    text = notice_text()
    h.check("A the card shows", notice() is not None, text)
    h.check("A title names the four files", "Bracket.step" in text and "Bracket.obj" in text, text)
    h.check(
        "A the component is lost in every file (the STEP is flat)",
        "the components (1): every body is written on its own, flat\n" in text + "\n"
        and "flat (STL" not in text,
        text,
    )
    h.check(
        "A the mesh body: not in the STEP, in the mesh files, no advice to export it again",
        "1 mesh body not in the STEP (exact solids only): it is in the STL, 3MF, OBJ" in text
        and "export it" not in text
        and "export them" not in text,
        text,
    )
    h.check("A no line ends in two sets of brackets", ") (" not in text, text)
    check_lines_fit("A")
    h.shot("everything")


# -- B ----------------------------------------------------------------------------------------
def b_open_export():
    h.fit()
    i.ribbon_tab("UTILITIES")
    h.ribbon("Export")


def b_mesh_only_3mf():
    from sciforge import export_ui

    d = export_ui.ExportDialog.last
    if not h.check("B Export dialog open", d is not None and d.isVisible()):
        return
    b.choose(d.type, "3MF")
    b.choose(d.what, "Selected bodies")
    for k in range(d.bodies.count()):
        on = d.bodies.item(k).data(QtCore.Qt.UserRole) == state["mesh"]
        i.check_list_item(d.bodies, k, on)
    b.type_into(d.folder, OUT)
    b.type_into(d.name, "cubeonly")


def b_press_export():
    from sciforge import export_ui

    d = export_ui.ExportDialog.last
    if d is not None and d.isVisible():
        b.click_widget(d.export_button)


b_press_export.wait_ms = 2000


def b_check():
    from sciforge import export_report_ui

    h.check("B cubeonly.3mf written", os.path.isfile(os.path.join(OUT, "cubeonly.3mf")))
    titles = [r["title"] for r in export_report_ui.recent()]
    h.check("B nothing lost: no new report", not any("cubeonly" in t for t in titles), titles)
    h.check("B the Export Everything card is gone", notice() is None, notice_text())


# -- C ----------------------------------------------------------------------------------------
def c_shrink():
    window = Gui.getMainWindow()
    window.showNormal()
    window.resize(1100, 700)


c_shrink.wait_ms = 1500


def c_everything_again():
    from sciforge import export_ui

    export_ui.export_everything(App.ActiveDocument, open_after=False)


c_everything_again.wait_ms = 3000


def c_check():
    n = notice()
    if not h.check("C the card shows", n is not None):
        return
    bar = navbar_rect(n)
    h.check("C the navigation bar is up", bar is not None)
    geo = n.geometry()
    if bar is not None:
        h.check("C the card keeps clear of the navigation bar", not geo.intersects(bar), (geo, bar))
    area = n.parentWidget().centralWidget()
    top = area.mapTo(n.parentWidget(), QtCore.QPoint(0, 0)).y()
    h.check("C the card is inside the 3D view", geo.top() >= top, (geo, top))
    check_lines_fit("C")
    h.shot("small")


def c_restore():
    Gui.getMainWindow().showMaximized()
    QtWidgets.QApplication.processEvents()


h.run(
    "export_report_card",
    [i.new_design("ExportCard")]
    + s.box_steps("box1", (0, 0, 40, 30), 10, i.XY_CLICK)
    + s.box_steps("box2", (50, 0, 80, 30), 10, i.XY_CLICK, new_body=True)
    + [
        setup,
        a_everything,
        a_check,
        b_open_export,
        b_mesh_only_3mf,
        b_press_export,
        b_check,
        c_shrink,
        c_everything_again,
        c_check,
        c_restore,
    ],
)
