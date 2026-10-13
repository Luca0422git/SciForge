# SPDX-License-Identifier: LGPL-2.1-or-later
"""Export (UTILITIES > MAKE > Export): STEP, STL, 3MF, OBJ with the refinement, whole design or
chosen bodies, one file or one per body; only real input (the system dialogs are stood in
for: the folder opener is recorded).

Bodies: box1 0..40 x 0..30 x 10 (12000) and box2 50..80 x 0..30 x 10 (9000, a New Body).

A  UTILITIES > Export: the Export dialog, Whole design, both bodies ticked; Type STEP;
   Location = the test folder, Name "two", Export: two.step with 2 solids of 21000 mm3; the
   folder was opened.
B  Export, STL (Binary), Refinement High: the Number of Triangles shows; Export: two.stl
   holds 21000 mm3 (within 0.5 %).
C  Export, 3MF, One File Per Body: one file per body, each with its body's volume and name.
D  Export, OBJ, Selected bodies with only the second ticked: 9000 mm3.
E  Export, Cancel: nothing new is written.
"""

import glob
import os

import FreeCAD as App

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as i

V = App.Vector
OUT = os.path.join(i.OUT, "export_formats")
state = {}


def dialog():
    from sciforge import export_ui

    d = export_ui.ExportDialog.last
    return d if d is not None and d.isVisible() else None


def files(pattern):
    return sorted(glob.glob(os.path.join(OUT, pattern)))


def setup():
    os.makedirs(OUT, exist_ok=True)
    for path in files("*"):
        os.remove(path)
    App.ActiveDocument.saveAs(os.path.join(OUT, "two.FCStd"))
    i.record_exports()
    del i.opened_folders[:]


def open_export():
    h.fit()
    i.ribbon_tab("UTILITIES")
    h.ribbon("Export")


def set_location_and_name(name):
    d = dialog()
    if d is None:
        return
    b.type_into(d.folder, OUT)
    b.type_into(d.name, name)


# -- A ----------------------------------------------------------------------------------------
def a_open():
    open_export()


def a_dialog():
    d = dialog()
    h.check("Export dialog", d is not None and d.windowTitle() == "Export", d)
    if d is None:
        return
    h.check("Whole design", d.what.currentText() == "Whole design", d.what.currentText())
    h.check("both bodies ticked", len(d.bodies.chosen()) == 2, [x.Label for x in d.bodies.chosen()])
    h.check("Type STEP first", d.type.currentText() == "STEP", d.type.currentText())
    h.check("mesh rows off for STEP", not d.refinement.level.isEnabled())
    set_location_and_name("two")


def a_export():
    d = dialog()
    if d is not None:
        b.click_widget(d.export_button)


a_export.wait_ms = 1500


def a_check():
    path = os.path.join(OUT, "two.step")
    h.check("two.step written", os.path.isfile(path), files("*"))
    if os.path.isfile(path):
        solids, volume = i.read_step(path)
        h.check(
            "2 solids, 21000 mm3", solids == 2 and i.close(volume, 21000.0, 1e-4), (solids, volume)
        )
    h.check(
        "the folder was opened", i.opened_folders and i.opened_folders[-1] == OUT, i.opened_folders
    )
    h.check("dialog closed", dialog() is None)
    s.no_popups("Export")


# -- B ----------------------------------------------------------------------------------------
def b_open():
    open_export()


def b_stl_high():
    d = dialog()
    if d is None:
        return
    b.choose(d.type, "STL (Binary)")
    h.check("mesh rows on for STL", d.refinement.level.isEnabled())
    b.choose(d.refinement.level, "High")
    set_location_and_name("two")


b_stl_high.wait_ms = 1200


def b_count_shown():
    d = dialog()
    if d is not None:
        text = d.refinement.triangles.text()
        h.check("Number of Triangles shown", text.strip().replace(" ", "").isdigit(), text)
        state["count"] = text


def b_export():
    d = dialog()
    if d is not None:
        b.click_widget(d.export_button)


b_export.wait_ms = 1500


def b_check():
    path = os.path.join(OUT, "two.stl")
    h.check("two.stl written", os.path.isfile(path), files("*"))
    if os.path.isfile(path):
        volume, facets, _solid = i.read_mesh_volume(path)
        h.check("21000 mm3 within 0.5 %", i.within(volume, 21000.0, 0.005), volume)
        h.check("binary STL", open(path, "rb").read(5) != b"solid")
        h.check(
            "triangle count matches",
            str(facets) == state.get("count", "").replace(" ", ""),
            (facets, state.get("count")),
        )


# -- C ----------------------------------------------------------------------------------------
def c_open():
    open_export()


def c_3mf_per_body():
    d = dialog()
    if d is None:
        return
    b.choose(d.type, "3MF")
    b.choose(d.structure, "One File Per Body")
    set_location_and_name("two")


def c_export():
    d = dialog()
    if d is not None:
        b.click_widget(d.export_button)


c_export.wait_ms = 1500


def c_check():
    found = files("two-*.3mf")
    h.check("one 3MF per body", len(found) == 2, found)
    volumes = sorted(round(i.read_mesh_volume(p)[0], 1) for p in found)
    h.check("each body in its file", volumes == [9000.0, 12000.0], volumes)
    labels = sorted(x.Label for x in s.bodies())
    names = sorted(os.path.basename(p) for p in found)
    h.check(
        "named after the bodies",
        all(any(lab in n for lab in labels) for n in names),
        (names, labels),
    )


# -- D ----------------------------------------------------------------------------------------
def d_open():
    open_export()


def d_obj_second_body():
    d = dialog()
    if d is None:
        return
    b.choose(d.type, "OBJ")
    b.choose(d.what, "Selected bodies")
    i.check_list_item(d.bodies, 0, False)
    h.check("one body ticked", len(d.bodies.chosen()) == 1, [x.Label for x in d.bodies.chosen()])
    set_location_and_name("second")


def d_export():
    d = dialog()
    if d is not None:
        b.click_widget(d.export_button)


d_export.wait_ms = 1500


def d_check():
    path = os.path.join(OUT, "second.obj")
    h.check("second.obj written", os.path.isfile(path), files("*"))
    if os.path.isfile(path):
        volume, _facets, _solid = i.read_mesh_volume(path)
        h.check("9000 mm3 (the second body)", i.within(volume, 9000.0, 0.005), volume)


# -- E ----------------------------------------------------------------------------------------
def e_open():
    state["before"] = files("*")
    open_export()


def e_cancel():
    d = dialog()
    if d is not None:
        i.dialog_button(d, "Cancel")


def e_check():
    h.check("Cancel: nothing new", files("*") == state["before"], files("*"))
    h.check("dialog closed", dialog() is None)
    h.shot("end")


h.run(
    "export_formats",
    [i.new_design("ExportFormats")]
    + s.box_steps("box1", (0, 0, 40, 30), 10, i.XY_CLICK)
    + s.box_steps("box2", (50, 0, 80, 30), 10, i.XY_CLICK, new_body=True)
    + [
        setup,
        a_open,
        a_dialog,
        a_export,
        a_check,
        b_open,
        b_stl_high,
        b_count_shown,
        b_export,
        b_check,
        c_open,
        c_3mf_per_body,
        c_export,
        c_check,
        d_open,
        d_obj_second_body,
        d_export,
        d_check,
        e_open,
        e_cancel,
        e_check,
    ],
)
