# SPDX-License-Identifier: LGPL-2.1-or-later
"""A mesh body goes to the printer and out to files (UTILITIES > 3D Print, Export, Export
Everything) like a solid; only real input (the system dialogs are stood in for).

A  Insert Mesh part.stl (a closed 20 x 10 x 5 box, 1000 mm3). UTILITIES > 3D Print: the mesh
   body is ticked, Number of Triangles 12 (its own triangles); Refinement Low: still 12 (a
   mesh body is printed as it is). OK: part.3mf of 1000 mm3, 12 triangles, watertight.
B  UTILITIES > Export, Type STEP: Export says STEP holds solid bodies only (convert the mesh
   first, or STL / 3MF / OBJ) and the dialog stays, nothing written; STL (Binary): part.stl,
   1000 mm3.
C  Saved as MeshOnly.FCStd; MAKE > Export Everything: the folder holds the STL, 3MF, OBJ, a
   picture and the README (no STEP, and the README does not name one); no error.
"""

import os

import FreeCAD as App

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as i
from SciForgeTests.gui import mesh_steps as m

OUT = os.path.join(i.OUT, "mesh_print")
state = {}


def part_file():
    return m.write_stl("part.stl", m.box_triangles())


def print_dialog():
    from sciforge import export_ui

    d = export_ui.PrintDialog.last
    return d if d is not None and d.isVisible() else None


def export_dialog():
    from sciforge import export_ui

    d = export_ui.ExportDialog.last
    return d if d is not None and d.isVisible() else None


def count(d):
    text = d.refinement.triangles.text().replace(" ", "") if d else ""
    return int(text) if text.isdigit() else None


def listing(folder):
    return sorted(os.listdir(folder)) if os.path.isdir(folder) else None


# -- A ----------------------------------------------------------------------------------------
def a_open():
    os.makedirs(OUT, exist_ok=True)
    for name in os.listdir(OUT):
        path = os.path.join(OUT, name)
        if os.path.isfile(path):
            os.remove(path)
    i.record_exports(save_path=os.path.join(OUT, "part.3mf"))
    del i.opened_folders[:]
    h.fit()
    i.ribbon_tab("UTILITIES")
    h.ribbon("3D Print")


a_open.wait_ms = 1500


def a_dialog():
    d = print_dialog()
    h.check("3D Print dialog", d is not None, d)
    if d is None:
        return
    h.check(
        "the mesh body is ticked",
        [x.Label for x in d.bodies.chosen()] == ["part"],
        [x.Label for x in d.bodies.chosen()],
    )
    h.check("12 triangles (its own)", count(d) == 12, count(d))
    b.choose(d.refinement.level, "Low")


a_dialog.wait_ms = 1500


def a_low():
    d = print_dialog()
    h.check("Low: still 12", count(d) == 12, count(d))
    b.choose(d.send_to, "Save file only")
    i.dialog_button(d, "OK")


a_low.wait_ms = 2000


def a_check():
    path = os.path.join(OUT, "part.3mf")
    h.check("part.3mf written", os.path.isfile(path), listing(OUT))
    if os.path.isfile(path):
        volume, facets, solid = i.read_mesh_volume(path)
        h.check(
            "1000 mm3, 12 triangles, watertight",
            i.close(volume, 1000.0, 1e-4) and facets == 12 and solid,
            (volume, facets, solid),
        )
    h.check("dialog closed", print_dialog() is None)
    s.no_popups("3D Print")


# -- B ----------------------------------------------------------------------------------------
def b_open():
    h.ribbon("Export")


b_open.wait_ms = 1500


def b_step():
    d = export_dialog()
    h.check("Export dialog", d is not None, d)
    if d is None:
        return
    h.check(
        "the mesh body is listed and ticked",
        [x.Label for x in d.bodies.chosen()] == ["part"],
        [x.Label for x in d.bodies.chosen()],
    )
    b.choose(d.type, "STEP")
    b.type_into(d.folder, OUT)
    b.type_into(d.name, "part")
    b.click_widget(d.export_button)


b_step.wait_ms = 1500


def b_refused():
    d = export_dialog()
    h.check("the dialog stays", d is not None)
    if d is None:
        return
    text = d.message.text()
    h.check(
        "STEP holds solid bodies only: convert first, or STL / 3MF / OBJ",
        "STEP holds solid bodies only" in text and "Convert Mesh" in text,
        text,
    )
    h.check("nothing written", not os.path.exists(os.path.join(OUT, "part.step")), listing(OUT))
    b.choose(d.type, "STL (Binary)")
    b.click_widget(d.export_button)


b_refused.wait_ms = 1500


def b_check():
    path = os.path.join(OUT, "part.stl")
    h.check("part.stl written", os.path.isfile(path), listing(OUT))
    if os.path.isfile(path):
        volume, facets, _solid = i.read_mesh_volume(path)
        h.check(
            "1000 mm3, 12 triangles",
            i.close(volume, 1000.0, 1e-4) and facets == 12,
            (volume, facets),
        )
    h.check("dialog closed", export_dialog() is None)


# -- C ----------------------------------------------------------------------------------------
def c_save():
    App.ActiveDocument.saveAs(os.path.join(OUT, "MeshOnly.FCStd"))
    del i.opened_folders[:]
    i.menu("MAKE", "Export Everything")


c_save.wait_ms = 2500


def c_check():
    folder = os.path.join(OUT, "MeshOnly-export")
    found = listing(folder)
    h.check(
        "the folder holds the mesh formats, a picture and the README (no STEP)",
        found == ["MeshOnly.3mf", "MeshOnly.obj", "MeshOnly.png", "MeshOnly.stl", "README.txt"],
        found,
    )
    if not found:
        return
    for name in ("MeshOnly.stl", "MeshOnly.3mf", "MeshOnly.obj"):
        volume = i.read_mesh_volume(os.path.join(folder, name))[0]
        h.check("%s: 1000 mm3" % name, i.close(volume, 1000.0, 1e-4), volume)
    readme = open(os.path.join(folder, "README.txt")).read()
    h.check(
        "the README names no STEP file",
        ".step" not in readme and "MeshOnly.3mf" in readme,
        readme[:300],
    )
    h.check(
        "the folder was opened",
        i.opened_folders and i.opened_folders[-1] == folder,
        i.opened_folders,
    )
    h.shot("end")


h.run(
    "mesh_print",
    [i.new_design("MeshPrint")]
    + m.insert_file(part_file())
    + [a_open, a_dialog, a_low, a_check, b_open, b_step, b_refused, b_check, c_save, c_check],
)
