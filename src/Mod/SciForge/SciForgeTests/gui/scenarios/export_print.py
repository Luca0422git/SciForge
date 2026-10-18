# SPDX-License-Identifier: LGPL-2.1-or-later
"""3D Print (UTILITIES > MAKE > 3D Print): format, refinement, save to a file or send to the
slicer; only real input (the save dialog is stood in for; a tiny script plays the slicer).

Body: a cylinder, radius 10, height 10 (3141.6 mm3), from a circle sketch and E.

A  UTILITIES > 3D Print: the dialog, the body ticked, Format 3MF, Refinement Medium, the
   Number of Triangles shown.
B  Refinement Low: fewer triangles; High: more; Custom with Surface Deviation 0.5 mm and
   Normal Deviation 45: fewer than Low.
C  Medium again; OK: cyl.3mf written (the stood-in save dialog), its volume within 2 % of the
   body, watertight; the folder was opened.
D  3D Print again, Send to 3D Print Utility with the stand-in slicer, OK: the slicer got the
   3MF file (slicer.log names it); no folder opened this time.
E  3D Print with nothing ticked: the dialog says so and stays; Cancel.
"""

import os
import time

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import insert_steps as i

V = App.Vector
OUT = os.path.join(i.OUT, "export_print")
CYLINDER_VOLUME = 3.141592653589793 * 100 * 10
state = {}


def dialog():
    from sciforge import export_ui

    d = export_ui.PrintDialog.last
    return d if d is not None and d.isVisible() else None


def count():
    d = dialog()
    text = d.refinement.triangles.text().replace(" ", "") if d else ""
    return int(text) if text.isdigit() else None


# -- the cylinder --------------------------------------------------------------------------------
def sketch():
    h.fit()
    h.ribbon("Create Sketch")


def pick_xy():
    pl.click_on_plane(i.XY_CLICK)


def draw():
    sk = h.in_sketch()
    h.check("sketch open", sk is not None)
    if sk is not None:
        h.draw_circle(sk, 0, 0, 10)


def finish():
    h.ribbon("Finish Sketch")


def extrude():
    h.fit()
    h.press("e")


def distance():
    panel = b.active_panel()
    field = getattr(getattr(panel, "distance", None), "widget", None)
    if h.check("extrude dialog", field is not None):
        b.type_into(field, "10")
        from PySide6 import QtTest

        QtTest.QTest.keyClick(field, QtCore.Qt.Key_Tab)


distance.wait_ms = 1200


def extrude_ok():
    h.task_button("OK")


def made():
    h.check(
        "cylinder 3141.6 mm3", i.close(s.total_volume(), CYLINDER_VOLUME, 1e-4), s.total_volume()
    )
    os.makedirs(OUT, exist_ok=True)
    for name in os.listdir(OUT):
        os.remove(os.path.join(OUT, name))
    del i.opened_folders[:]


# -- A ----------------------------------------------------------------------------------------
def a_open():
    i.record_exports(save_path=os.path.join(OUT, "cyl.3mf"))
    i.ribbon_tab("UTILITIES")
    h.ribbon("3D Print")


a_open.wait_ms = 1200


def a_dialog():
    d = dialog()
    h.check("3D Print dialog", d is not None and d.windowTitle() == "3D Print", d)
    if d is None:
        return
    h.check("the body is ticked", len(d.bodies.chosen()) == 1, [x.Label for x in d.bodies.chosen()])
    h.check("Format 3MF", d.format.currentText() == "3MF", d.format.currentText())
    h.check("Refinement Medium", d.refinement.level.currentText() == "Medium")
    h.check("triangles shown", count() is not None and count() > 0, count())
    state["medium"] = count()


# -- B ----------------------------------------------------------------------------------------
def b_low():
    d = dialog()
    if d is not None:
        b.choose(d.refinement.level, "Low")


def b_check_low():
    state["low"] = count()
    h.check(
        "Low: fewer triangles than Medium",
        state["low"] is not None and state["low"] < state["medium"],
        (state["low"], state["medium"]),
    )


def b_high():
    d = dialog()
    if d is not None:
        b.choose(d.refinement.level, "High")


def b_check_high():
    state["high"] = count()
    h.check(
        "High: more triangles than Medium",
        state["high"] is not None and state["high"] > state["medium"],
        (state["high"], state["medium"]),
    )


def b_custom():
    d = dialog()
    if d is None:
        return
    b.choose(d.refinement.level, "Custom")
    h.check(
        "custom fields enabled",
        d.refinement.surface.isEnabled() and d.refinement.normal.isEnabled(),
    )
    i.set_spin(d.refinement.surface, 0.5)
    i.set_spin(d.refinement.normal, 45)
    h.check(
        "the typed deviations are taken",
        abs(d.refinement.surface.value() - 0.5) < 1e-9
        and abs(d.refinement.normal.value() - 45) < 1e-9,
        (d.refinement.surface.value(), d.refinement.normal.value()),
    )


def b_check_custom():
    custom = count()
    h.check(
        "Custom 0.5 mm / 45 deg: coarser than Low",
        custom is not None and custom < state["low"],
        (custom, state["low"]),
    )


# -- C ----------------------------------------------------------------------------------------
def c_medium_ok():
    d = dialog()
    if d is None:
        return
    b.choose(d.refinement.level, "Medium")
    i.set_check(d.send, False)
    i.dialog_button(d, "OK")


c_medium_ok.wait_ms = 1500


def c_check():
    path = os.path.join(OUT, "cyl.3mf")
    h.check("cyl.3mf written", os.path.isfile(path), os.listdir(OUT))
    if os.path.isfile(path):
        volume, facets, solid = i.read_mesh_volume(path)
        h.check("volume within 2 % of the body", i.within(volume, CYLINDER_VOLUME, 0.02), volume)
        h.check("watertight", solid)
        h.check("Medium triangle count", facets == state["medium"], (facets, state["medium"]))
    h.check(
        "the folder was opened", i.opened_folders and i.opened_folders[-1] == OUT, i.opened_folders
    )
    h.check("dialog closed", dialog() is None)


# -- D ----------------------------------------------------------------------------------------
def d_open():
    state["slicer"], state["log"] = i.fake_slicer()
    i.real_program_start()
    del i.opened_folders[:]
    h.ribbon("3D Print")


d_open.wait_ms = 1200


def d_send():
    d = dialog()
    if d is None:
        return
    i.set_check(d.send, True)
    h.check("program row enabled", d.program.isEnabled())
    b.type_into(d.program, state["slicer"])
    i.dialog_button(d, "OK")


d_send.wait_ms = 2500


def d_check():
    log = state["log"]
    for _ in range(20):
        if os.path.isfile(log):
            break
        time.sleep(0.1)
    text = open(log).read() if os.path.isfile(log) else ""
    h.check("the slicer got a 3MF file", text.strip().endswith(".3mf"), text)
    h.check("that file exists", os.path.isfile(text.strip()), text)
    h.check("no folder opened when sending", not i.opened_folders, i.opened_folders)
    from sciforge import export

    h.check(
        "the slicer is remembered",
        export.slicer_program() == state["slicer"],
        export.slicer_program(),
    )


# -- E ----------------------------------------------------------------------------------------
def e_open():
    i.record_exports(save_path=os.path.join(OUT, "none.3mf"))
    h.ribbon("3D Print")


e_open.wait_ms = 1200


def e_untick_ok():
    d = dialog()
    if d is None:
        return
    i.set_check(d.send, False)
    i.check_list_item(d.bodies, 0, False)
    i.dialog_button(d, "OK")


def e_check():
    d = dialog()
    h.check(
        "dialog stays open and says so",
        d is not None and "Tick" in d.message.text(),
        d and d.message.text(),
    )
    h.check("nothing written", not os.path.isfile(os.path.join(OUT, "none.3mf")))
    if d is not None:
        i.dialog_button(d, "Cancel")


def e_closed():
    h.check("Cancel closes", dialog() is None)
    from sciforge import export

    export.set_slicer_program("")
    h.shot("end")


h.run(
    "export_print",
    [
        i.new_design("ExportPrint"),
        sketch,
        pick_xy,
        draw,
        finish,
        extrude,
        distance,
        extrude_ok,
        made,
        a_open,
        a_dialog,
        b_low,
        b_check_low,
        b_high,
        b_check_high,
        b_custom,
        b_check_custom,
        c_medium_ok,
        c_check,
        d_open,
        d_send,
        d_check,
        e_open,
        e_untick_ok,
        e_check,
        e_closed,
    ],
)
