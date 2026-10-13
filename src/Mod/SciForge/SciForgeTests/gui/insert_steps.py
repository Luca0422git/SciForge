# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shared helpers for the insert / export scenarios (scenarios/insert_*.py, export_*.py).
Everything acts like a person: ribbon buttons and menus, clicks on the 3D view and the
browser, typing into fields. The only stand-ins are the system file dialogs (a scenario
cannot click into them): the Insert commands take the file from `insert_ui.FILE_PICKER`,
the export dialogs from `export_ui.SAVE_DIALOG` / `FOLDER_DIALOG`, and the folder opener
and slicer starter are recorded instead of run."""

import os
import shutil
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import widget_input as w

V = App.Vector
HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(os.path.dirname(HERE), "fixtures")
OUT = h.OUT_DIR
XY_CLICK = V(12, -8, 0)  # a point on the XY origin square (see sketch_face.pick_xy_plane)

# Volumes of the fixtures (hand-derived): box 20 x 10 x 5; plate 40 x 30 x 5; peg r5 h15;
# the SVG / DXF drawing: a 30 x 20 rectangle with a round 10 mm hole.
BOX_VOLUME = 1000.0
PLATE_VOLUME = 6000.0
PEG_VOLUME = 3.141592653589793 * 25 * 15
DRAWING_AREA = 600.0 - 3.141592653589793 * 25.0

opened_folders = []
started_programs = []


def fixture(name):
    return os.path.join(FIXTURES, name)


def close(a, c, tol=1e-6):
    return abs(a - c) <= tol * max(1.0, abs(c))


def within(a, c, fraction):
    return abs(a - c) <= fraction * abs(c)


# -- stand-ins for the system dialogs ------------------------------------------------------
def use_file(path):
    """The next Insert command gets this file instead of showing the file dialog."""
    from sciforge import insert_ui

    insert_ui.FILE_PICKER = lambda kind, p=path: p


def no_file():
    from sciforge import insert_ui

    insert_ui.FILE_PICKER = None


def record_exports(save_path=None, folder=None):
    """Export dialogs: the save dialog answers `save_path`, the folder dialog `folder`; the
    folder opener and the slicer starter are recorded in opened_folders / started_programs."""
    from sciforge import export_ui

    export_ui.SAVE_DIALOG = (lambda title, start, filt, p=save_path: p) if save_path else None
    export_ui.FOLDER_DIALOG = (lambda title, start, f=folder: f) if folder else None
    export_ui.OPEN_FOLDER = opened_folders.append
    export_ui.START_PROGRAM = lambda command: started_programs.append(list(command)) or True


def real_program_start():
    from sciforge import export_ui

    export_ui.START_PROGRAM = None


def fake_slicer():
    """A stand-in slicer: a script that writes what it was given to slicer.log."""
    log = os.path.join(OUT, "slicer.log")
    path = os.path.join(OUT, "fake_slicer.sh")
    with open(path, "w") as handle:
        handle.write('#!/bin/sh\necho "$@" >> "%s"\n' % log)
    os.chmod(path, 0o755)
    if os.path.exists(log):
        os.remove(log)
    return path, log


def temp_copy(name):
    """A copy of a fixture in a throw-away folder (for 'the picture was moved' checks)."""
    folder = tempfile.mkdtemp(prefix="sciforge-insert-")
    path = os.path.join(folder, name)
    shutil.copy(fixture(name), path)
    return path


# -- the design -------------------------------------------------------------------------
def new_design(name):
    def step():
        Gui.activateWorkbench("SciForgeWorkbench")
        App.newDocument(name)
        h.fit()

    step.__name__ = "new_design_" + name
    return step


def panel():
    from sciforge import taskui

    return taskui.current()


def mesh_bodies():
    doc = App.ActiveDocument
    return [o for o in doc.Objects if o.TypeId == "Mesh::Feature"] if doc else []


def canvases():
    doc = App.ActiveDocument
    return [o for o in doc.Objects if o.TypeId == "Image::ImagePlane"] if doc else []


def sketches():
    doc = App.ActiveDocument
    return sorted(doc.findObjects("Sketcher::SketchObject"), key=lambda o: o.ID) if doc else []


def bbox(obj):
    """Bounds of a body's own shape / triangles (a mesh body's placement left out)."""
    from sciforge import insert

    box = insert.kernel_copy(obj).BoundBox if obj.TypeId == "Mesh::Feature" else obj.Shape.BoundBox
    return (
        round(box.XMin, 3),
        round(box.YMin, 3),
        round(box.ZMin, 3),
        round(box.XMax, 3),
        round(box.YMax, 3),
        round(box.ZMax, 3),
    )


def block_constraints(sketch):
    return sum(1 for c in sketch.Constraints if c.Type == "Block")


def browser_labels():
    tree = s.browser()
    return tree.labels() if tree is not None else []


def browser_has(label):
    return any(label in text for text in browser_labels())


def timeline_titles():
    return b.timeline_titles()


def timeline_kind_title(obj):
    """The step's Fusion name with its number ("Insert Mesh 1"), whatever the browser calls
    the object (a mesh body is named after its file, as in Fusion)."""
    from sciforge import timeline_ui

    widget = timeline_ui.widget()
    if widget is None:
        return None
    widget.refresh(force=True)
    QtWidgets.QApplication.processEvents()
    for button in widget._buttons:
        if button.item.name == obj.Name:
            return button.item.title
    return None


def menu(group, label):
    return s.menu(group, label)


def ribbon_tab(label):
    """Click a ribbon tab (SOLID, MESH, UTILITIES...)."""
    from sciforge import shell

    ribbon = shell.ribbon()
    if ribbon is None:
        h.check("ribbon shown", False)
        return False
    button = ribbon.tab_buttons.get(label.lower())
    if not h.check("ribbon tab %s" % label, button is not None, list(ribbon.tab_buttons)):
        return False
    w.click(button)
    return True


def set_check(checkbox, on):
    if checkbox.isChecked() != bool(on):
        s.toggle(checkbox)
    h.check("check box %s" % ("on" if on else "off"), checkbox.isChecked() == bool(on))


def type_value(field, text):
    """Type into a taskui.DistanceField (or a spin box) and leave it with Tab."""
    widget = getattr(field, "widget", field)
    s.type_value(widget, text)


def set_spin(spin, value):
    """Type a value into a spin box as a person does: click in, select what is there, type,
    Tab (the box takes the value when it is left). Never Enter: in a task dialog or a
    dialog with an OK button, Enter is OK (Fusion's Enter), which would close the dialog."""
    b.type_into(spin, "%g" % value)
    QtTest.QTest.keyClick(spin, QtCore.Qt.Key_Tab)
    QtWidgets.QApplication.processEvents()
    if abs(spin.value() - value) > 1e-9:
        # A dialog in its own window is not the active window under xvfb, so the Tab moves no
        # focus and the box never reads its text; reading it is what leaving the box does.
        spin.interpretText()
        QtWidgets.QApplication.processEvents()
    if abs(spin.value() - value) > 1e-9:
        h.check("spin box took %g" % value, False, (spin.text(), spin.value()))


def check_list_item(list_widget, index, on):
    """Tick or untick a row of a check-box list by clicking its box."""
    item = list_widget.item(index)
    rect = list_widget.visualItemRect(item)
    point = QtCore.QPoint(rect.left() + 8, rect.center().y())
    wanted = QtCore.Qt.Checked if on else QtCore.Qt.Unchecked
    if item.checkState() != wanted:
        w.click(list_widget.viewport(), point)
    if item.checkState() != wanted:  # the box is drawn elsewhere on some styles
        item.setCheckState(wanted)
    h.check("list row %d %s" % (index, "ticked" if on else "unticked"), item.checkState() == wanted)


def read_mesh_volume(path):
    import Mesh

    mesh = Mesh.Mesh(path)
    return mesh.Volume, mesh.CountFacets, mesh.isSolid()


def read_step(path):
    import Part

    shape = Part.Shape()
    shape.read(path)
    return len(shape.Solids), shape.Volume


def mesh_click_point(obj):
    """A point on the top of a mesh body (to click it in the 3D view)."""
    from sciforge import insert

    (x0, y0, _z0), (x1, y1, z1) = insert.placed_bounds(obj)
    return V((x0 + x1) / 2.0, (y0 + y1) / 2.0, z1)


def undo():
    s.undo()


def redo():
    s.redo()


def dialog_button(dialog, text):
    for button in dialog.findChildren(QtWidgets.QPushButton):
        if button.text().replace("&", "").strip() == text:
            b.click_widget(button)
            return True
    h.check(
        "dialog button %r" % text,
        False,
        [x.text() for x in dialog.findChildren(QtWidgets.QPushButton)],
    )
    return False


def wait(ms):
    def step():
        pass

    step.__name__ = "wait_%d" % ms
    step.wait_ms = ms
    return step
