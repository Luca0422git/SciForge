# SPDX-License-Identifier: LGPL-2.1-or-later
"""Export Everything (UTILITIES > MAKE menu, File menu): the whole design to open formats in
one go; only real input (the folder opener is recorded, the folder dialog stood in for).

Body: box 0..40 x 0..30 x 10 (12000 mm3).

A  The design saved as Bracket.FCStd; MAKE > Export Everything: the folder Bracket-export
   beside it holds Bracket.step (1 solid, 12000), Bracket.stl, Bracket.3mf, Bracket.obj
   (12000 each), Bracket.png (a picture) and README.txt naming them; the folder was opened.
B  A design never saved: the folder dialog asks where; the files land in <name>-export there.
C  An empty design: a message, nothing written, no folder opened, no error.
"""

import os

import FreeCAD as App

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as i

V = App.Vector
OUT = os.path.join(i.OUT, "export_everything")
state = {}


def listing(folder):
    return sorted(os.listdir(folder)) if os.path.isdir(folder) else None


# -- A ----------------------------------------------------------------------------------------
def a_save():
    os.makedirs(OUT, exist_ok=True)
    App.ActiveDocument.saveAs(os.path.join(OUT, "Bracket.FCStd"))
    i.record_exports()
    del i.opened_folders[:]
    h.fit()


def a_export():
    i.ribbon_tab("UTILITIES")
    i.menu("MAKE", "Export Everything")


a_export.wait_ms = 2500


def a_check():
    folder = os.path.join(OUT, "Bracket-export")
    found = listing(folder)
    h.check(
        "the export folder beside the design holds every format",
        found
        == [
            "Bracket.3mf",
            "Bracket.obj",
            "Bracket.png",
            "Bracket.step",
            "Bracket.stl",
            "README.txt",
        ],
        found,
    )
    if not found:
        return
    solids, volume = i.read_step(os.path.join(folder, "Bracket.step"))
    h.check(
        "STEP: 1 solid of 12000", solids == 1 and i.close(volume, 12000.0, 1e-4), (solids, volume)
    )
    for name in ("Bracket.stl", "Bracket.3mf", "Bracket.obj"):
        mesh_volume = i.read_mesh_volume(os.path.join(folder, name))[0]
        h.check("%s: 12000" % name, i.within(mesh_volume, 12000.0, 0.005), mesh_volume)
    h.check("a picture", os.path.getsize(os.path.join(folder, "Bracket.png")) > 1000)
    readme = open(os.path.join(folder, "README.txt")).read()
    h.check(
        "README names the files", "Bracket.step" in readme and "Bracket.3mf" in readme, readme[:200]
    )
    h.check(
        "the folder was opened",
        i.opened_folders and i.opened_folders[-1] == folder,
        i.opened_folders,
    )
    s.no_popups("Export Everything")


# -- B ----------------------------------------------------------------------------------------
def b_unsaved():
    where = os.path.join(OUT, "chosen")
    os.makedirs(where, exist_ok=True)
    i.record_exports(folder=where)
    del i.opened_folders[:]
    state["where"] = where


def b_export():
    i.ribbon_tab("UTILITIES")
    i.menu("MAKE", "Export Everything")


b_export.wait_ms = 2500


def b_check():
    label = App.ActiveDocument.Label
    folder = os.path.join(state["where"], label + "-export")
    found = listing(folder)
    h.check(
        "unsaved design: files in the chosen folder",
        found is not None and label + ".step" in found,
        (folder, found),
    )
    h.check(
        "the folder was opened",
        i.opened_folders and i.opened_folders[-1] == folder,
        i.opened_folders,
    )


# -- C ----------------------------------------------------------------------------------------
def c_empty():
    del i.opened_folders[:]
    i.ribbon_tab("UTILITIES")
    i.menu("MAKE", "Export Everything")


c_empty.wait_ms = 1500


def c_check():
    h.check("empty design: no folder opened", not i.opened_folders, i.opened_folders)
    from sciforge import RECENT

    h.check("it said why", any("no solid body" in line for line in RECENT[-5:]), RECENT[-3:])
    h.shot("end")


h.run(
    "export_everything",
    [i.new_design("Bracket")]
    + s.box_steps("box", (0, 0, 40, 30), 10, i.XY_CLICK)
    + [a_save, a_export, a_check]
    + [i.new_design("Loose"), lambda: i.ribbon_tab("SOLID")]
    + s.box_steps("box2", (0, 0, 40, 30), 10, i.XY_CLICK)
    + [b_unsaved, b_export, b_check]
    + [i.new_design("Empty"), c_empty, c_check],
)
