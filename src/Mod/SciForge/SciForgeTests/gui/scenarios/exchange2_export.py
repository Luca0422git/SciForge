# SPDX-License-Identifier: LGPL-2.1-or-later
"""Export with structure (exchange-2, docs/sciforge/parity/insert-export.md Part 2): STEP
that keeps the components, IGES, a component as 3MF in its own coordinates, Save As DXF of
a sketch, DXF of a flat face, DWG refused without a converter, Save As Mesh from the
browser. Real input (the ribbon, the dialog, the browser's right-click menu, clicks in the
window); the stand-ins are the system's file / folder dialogs and the folder opener.

The design: robot.step opened (exchange_steps), plus a sketch in Base's body on the XZ
plane: a 30 x 20 rectangle from (0, 0) and a circle r 5 at (15, 10) in its own coordinates.

P1  UTILITIES > Export, STEP, Whole design: robot_out.step; opened again (Ctrl+O): the
    same components, the copy, the bodies where they were, the colours.
P2  IGES: the four solids come back as four bodies (IGES has no components).
P3  A component (Drive) as 3MF: the axle and both wheels, in Drive's own coordinates.
P4  Browser: right-click the sketch > Save As DXF: read back, the rectangle and the circle
    in the sketch's own X / Y (the sketch stands on XZ).
P5  The base's top face clicked, Export, Type DXF, Use Selection: its outline, 60 x 40,
    in the face's own frame (centred).
P6  DWG: refused with the converters to install (none in this machine); the dialog stays.
P7  Browser: right-click Drive > Save As Mesh: the Export dialog on Drive, 3MF.
P8  DXF with nothing picked: refused, says to pick a sketch or a flat face.
"""

import os
import shutil

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import exchange_steps as x
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as i
from SciForgeTests.gui import timeline_input as t

V = App.Vector
OUT = os.path.join(h.OUT_DIR, "exchange2-export")
s = {}


def dialog():
    from sciforge import export_ui

    d = export_ui.ExportDialog.last
    return d if d is not None and d.isVisible() else None


def open_export():
    h.fit()
    i.ribbon_tab("UTILITIES")
    h.ribbon("Export")


def fill(name, kind):
    d = dialog()
    if not h.check("the Export dialog", d is not None):
        return None
    b.choose(d.type, kind)
    b.type_into(d.folder, OUT)
    b.type_into(d.name, name)
    return d


def press_export():
    d = dialog()
    if d is not None:
        b.click_widget(d.export_button)


def setup():
    import Part

    from sciforge import exchange_ui

    Gui.activateWorkbench("SciForgeWorkbench")
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    s["robot"] = x.make_robot(x.out("robot.step"))
    exchange_ui.open_file(s["robot"])
    doc = App.ActiveDocument
    body = x.body_of("Base")
    sketch = body.newObject("Sketcher::SketchObject", "Sketch")
    plane = [f for f in body.Origin.OriginFeatures if f.Role == "XZ_Plane"][0]
    sketch.AttachmentSupport = [(plane, "")]
    sketch.MapMode = "FlatFace"
    corners = [V(0, 0, 0), V(30, 0, 0), V(30, 20, 0), V(0, 20, 0)]
    for a, c in zip(corners, corners[1:] + corners[:1]):
        sketch.addGeometry(Part.LineSegment(a, c))
    sketch.addGeometry(Part.Circle(V(15, 10, 0), V(0, 0, 1), 5))
    doc.recompute()
    sketch.ViewObject.Visibility = False
    i.record_exports()
    del i.opened_folders[:]
    h.fit()


# -- P1 ----------------------------------------------------------------------------------------
def p1_open():
    open_export()


def p1_fill():
    d = fill("robot_out", "STEP")
    if d is not None:
        h.check("P1 Whole design", d.what.currentText() == "Whole design", d.what.currentText())
        h.check("P1 the note says STEP keeps the components", "components" in d.note.text())


def p1_export():
    press_export()


p1_export.wait_ms = 2000


def p1_reopen():
    path = os.path.join(OUT, "robot_out.step")
    h.check("P1 robot_out.step written", os.path.isfile(path), os.listdir(OUT))
    h.check("P1 the dialog closed", dialog() is None)
    h.check("P1 the folder was opened", i.opened_folders and i.opened_folders[-1] == OUT)
    s["design"] = App.ActiveDocument.Name
    x.use_open_file(path)
    h.press(QtCore.Qt.Key_O, QtCore.Qt.ControlModifier)


p1_reopen.wait_ms = 2500


def p1_check():
    doc = App.ActiveDocument
    h.check("P1 opened as robot_out", doc is not None and doc.Label == "robot_out", doc.Label)
    x.check_robot("P1 round trip")
    for label, colour in (("Base", x.BLUE), ("Wheel", x.RED), ("Axle", x.GREY)):
        body = x.body_of(label)
        h.check(
            "P1 round trip: %s keeps its colour" % label,
            body is not None and x.same_colour(x.look_of(body), colour),
            body and x.look_of(body),
        )
    h.shot("1-round-trip")
    Gui.getDocument(doc.Name).Modified = False
    App.closeDocument(doc.Name)
    from sciforge import insert

    insert.restore_active_document(s["design"])


p1_check.wait_ms = 1200


# -- P2 ----------------------------------------------------------------------------------------
def p2_open():
    open_export()


def p2_fill():
    d = fill("robot_iges", "IGES")
    if d is not None:
        h.check("P2 IGES note", "not the components" in d.note.text(), d.note.text())


def p2_export():
    press_export()


p2_export.wait_ms = 2000


def p2_check():
    from sciforge import exchange_core, step_import

    path = os.path.join(OUT, "robot_iges.igs")
    h.check("P2 robot_iges.igs written", os.path.isfile(path), os.listdir(OUT))
    if not os.path.isfile(path):
        return
    probe = App.newDocument("IgesProbe")
    try:
        made = step_import.import_file(probe, path, exchange_core.OPEN)
        volumes = sorted(round(b.Shape.Volume, 1) for b in made.bodies)
        want = sorted(round(v, 1) for v in (x.BASE_VOLUME, x.AXLE_VOLUME) + (x.WHEEL_VOLUME,) * 2)
        h.check("P2 four solid bodies back", volumes == want, volumes)
    finally:
        App.closeDocument(probe.Name)
        from sciforge import insert

        insert.restore_active_document(s["design"])


# -- P3 ----------------------------------------------------------------------------------------
def p3_open():
    open_export()


def p3_fill():
    d = fill("drive", "3MF")
    if d is None:
        return
    b.choose(d.what, "A component")
    b.choose(d.component, "Drive")
    h.check("P3 the component list is on", d.component.isEnabled())
    h.check("P3 the bodies list is off", not d.bodies.isEnabled())


def p3_export():
    press_export()


p3_export.wait_ms = 2500


def p3_check():
    import Mesh

    path = os.path.join(OUT, "drive.3mf")
    h.check("P3 drive.3mf written", os.path.isfile(path), os.listdir(OUT))
    if not os.path.isfile(path):
        return
    mesh = Mesh.Mesh(path)
    want = x.AXLE_VOLUME + 2 * x.WHEEL_VOLUME
    h.check("P3 the axle and both wheels", i.within(mesh.Volume, want, 0.02), mesh.Volume)
    box = mesh.BoundBox
    h.check(
        "P3 in Drive's own coordinates (its middle at 0, 17.5, 0)",
        x.near3((box.Center.x, box.Center.y, box.Center.z), (0, 17.5, 0), 0.3),
        box,
    )


# -- P4 ----------------------------------------------------------------------------------------
def p4_save_dxf():
    s["dxf"] = os.path.join(OUT, "Sketch.dxf")
    i.record_exports(save_path=s["dxf"])
    t.row_menu("Sketch", "Save As DXF")


p4_save_dxf.wait_ms = 1500


def p4_check():
    from sciforge import insert

    h.check("P4 Sketch.dxf written", os.path.isfile(s["dxf"]), os.listdir(OUT))
    if not os.path.isfile(s["dxf"]):
        return
    edges = [e for _layer, found in insert.read_curves(s["dxf"]) for e in found]
    lines = [e for e in edges if e.Curve.TypeId == "Part::GeomLine"]
    circles = [e for e in edges if e.Curve.TypeId == "Part::GeomCircle"]
    h.check("P4 four lines and a circle", (len(lines), len(circles)) == (4, 1), len(edges))
    box = insert.curves_bounds(lines)
    h.check(
        "P4 the rectangle in the sketch's own X / Y (0..30 x 0..20)",
        box is not None and x.near3(box[0] + box[1], (0, 0, 30, 20), 1e-3),
        box,
    )
    if circles:
        c = circles[0].Curve
        h.check(
            "P4 the circle r 5 at (15, 10)",
            x.near3((c.Center.x, c.Center.y, c.Radius), (15, 10, 5), 1e-3),
            (c.Center, c.Radius),
        )
    h.check("P4 no pop-up", not h.popups(), h.popups())


# -- P5 ----------------------------------------------------------------------------------------
def p5_click_face():
    i.record_exports()
    h.fit()
    h.click(V(10, 10, 10))


p5_click_face.wait_ms = 800


def p5_open():
    sel = Gui.Selection.getSelectionEx()
    subs = [n for sx in sel for n in sx.SubElementNames]
    h.check("P5 a face is picked", any(n.startswith("Face") for n in subs), subs)
    open_export()


def p5_fill():
    d = fill("base_top", "DXF")
    if d is None:
        return
    h.check("P5 the picked face is named", "Face" in d.flat_label.text(), d.flat_label.text())
    h.check("P5 Use Selection is on for DXF", d.use_selection.isEnabled())
    h.check("P5 Export (what) is off for DXF", not d.what.isEnabled())


def p5_export():
    press_export()


p5_export.wait_ms = 1500


def p5_check():
    from sciforge import insert

    path = os.path.join(OUT, "base_top.dxf")
    h.check("P5 base_top.dxf written", os.path.isfile(path), os.listdir(OUT))
    if not os.path.isfile(path):
        return
    edges = [e for _layer, found in insert.read_curves(path) for e in found]
    box = insert.curves_bounds(edges)
    h.check(
        "P5 the top's outline 60 x 40, centred",
        len(edges) == 4 and box is not None and x.near3(box[0] + box[1], (-30, -20, 30, 20), 1e-3),
        (len(edges), box),
    )


# -- P6 ----------------------------------------------------------------------------------------
def p6_open():
    h.fit()
    h.click(V(10, 10, 10))
    open_export()


def p6_dwg():
    d = fill("base_top", "DWG")
    if d is None:
        return
    h.check("P6 the note names the converters", "LibreDWG" in d.note.text(), d.note.text())
    press_export()


p6_dwg.wait_ms = 1200


def p6_check():
    d = dialog()
    h.check("P6 the dialog stays open", d is not None)
    if d is None:
        return
    h.check("P6 it says why", "LibreDWG" in d.message.text(), d.message.text())
    h.check("P6 no DWG was written", not os.path.exists(os.path.join(OUT, "base_top.dwg")))
    b.choose(d.type, "DXF")
    d.flat = None
    d._show_flat()
    press_export()


p6_check.wait_ms = 1200


# -- P8 (DXF with nothing picked) ------------------------------------------------------------------
def p8_check():
    d = dialog()
    h.check("P8 the dialog stays open", d is not None)
    if d is not None:
        h.check(
            "P8 it says to pick a sketch or a flat face",
            "sketch or a flat face" in d.message.text(),
            d.message.text(),
        )
        d.reject()


# -- P7 ----------------------------------------------------------------------------------------
def p7_save_as_mesh():
    t.row_menu("Drive", "Save As Mesh")


p7_save_as_mesh.wait_ms = 1500


def p7_check():
    d = dialog()
    h.check("P7 the Export dialog opened", d is not None)
    if d is None:
        return
    h.check("P7 on the component", d.what.currentText() == "A component", d.what.currentText())
    h.check("P7 Drive", d.component.currentText() == "Drive", d.component.currentText())
    h.check("P7 3MF", d.type.currentText() == "3MF", d.type.currentText())
    h.check("P7 named after it", d.name.text() == "Drive", d.name.text())
    d.reject()


def cleanup():
    for name in list(App.listDocuments()):
        try:
            Gui.getDocument(name).Modified = False
        except Exception:
            pass
        App.closeDocument(name)
    x.use_open_file(None)
    h.new_errors()


h.run(
    "exchange2_export",
    [
        setup,
        p1_open,
        p1_fill,
        p1_export,
        p1_reopen,
        p1_check,
        p2_open,
        p2_fill,
        p2_export,
        p2_check,
        p3_open,
        p3_fill,
        p3_export,
        p3_check,
        p4_save_dxf,
        p4_check,
        p5_click_face,
        p5_open,
        p5_fill,
        p5_export,
        p5_check,
        p6_open,
        p6_dwg,
        p6_check,
        p8_check,
        p7_save_as_mesh,
        p7_check,
        cleanup,
    ],
)
