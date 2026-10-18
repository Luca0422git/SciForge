# SPDX-License-Identifier: LGPL-2.1-or-later
"""Send to Slicer (UTILITIES > MAKE > 3D Print): the slicers found on the computer, Other...,
Save file only, Save a copy, and what the slicer gets. Only real input: the system's program
picker is stood in for, and the slicers are FAKE ones (small scripts made here, in the
scenario's folder, that write the arguments they were started with into a log). SciForge is
told to look for slicers in that folder instead of the machine's (export_ui.SLICER_ENV), so
the scenario gives the same answers on any computer.

Bodies: box1 0..40 x 0..30 x 10 (12000 mm3) and box2 50..80 x 0..30 x 10 (9000, a New Body),
saved as pi_case.FCStd.

A  No slicer on the computer: UTILITIES > 3D Print: Send to lists only "Other... (pick the
   program)" and "Save file only", starts at Save file only, and the dialog says plainly that
   no slicer was found. Other... with the picker cancelled, OK: the dialog says so again,
   nothing is written and nothing started. Cancel.
B  A slicer installed (a fake "prusa-slicer" on the PATH): 3D Print lists PrusaSlicer first
   and starts at it, both visible bodies ticked, Format 3MF, Unit Type greyed at Millimeter;
   "Also save a copy next to the design" ticked, OK: the fake PrusaSlicer was started with a
   3MF in SciForge's print folder; read back with FreeCAD's Mesh module it is 21000 mm3 with
   the bodies' bounding box 0..80 x 0..30 x 0..10 (mm, placed as in the design), two objects
   named after the two bodies, unit millimeter; the copy pi_case.3mf is beside the design.
C  3D Print again, Send to Other... (the picker answers a second fake slicer), only box1
   ticked, Format STL (Binary), OK: the second fake got box1's STL: 12000 mm3, 0..40 x 0..30 x
   0..10; the copy beside the design is named after the body; the choice and the program are
   remembered.
D  3D Print again: it starts at Other... with that program; Save file only: Save a copy greyed,
   the folder option and Unit Type back on; Cancel: nothing written, no slicer started.
E  Preferences > 3D Print: Send to shows Other with the program, the page names PrusaSlicer
   as found; Send to "Save file only", OK: the next 3D Print starts at Save file only.
"""

import glob
import os
import re
import time
import zipfile

import FreeCAD as App

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as i
from SciForgeTests.gui import misc_steps as m
from SciForgeTests.gui import widget_input as w

OUT = os.path.join(i.OUT, "send_to_slicer")
BIN = os.path.join(OUT, "bin")  # where the fake PrusaSlicer is "installed"
EMPTY = os.path.join(OUT, "empty")  # a PATH with no slicer at all
OTHER = os.path.join(OUT, "other_slicer.sh")
PRUSA_LOG = os.path.join(OUT, "prusa.log")
OTHER_LOG = os.path.join(OUT, "other.log")
state = {}


def dialog():
    from sciforge import export_ui

    d = export_ui.PrintDialog.last
    try:
        return d if d is not None and d.isVisible() else None
    except RuntimeError:
        return None


def entries(combo):
    return [combo.itemText(k) for k in range(combo.count())]


def fake_slicer(path, log):
    """A stand-in slicer: writes each argument it gets on a line of `log`."""
    with open(path, "w") as handle:
        handle.write('#!/bin/sh\nfor a in "$@"; do echo "$a" >> "%s"; done\n' % log)
    os.chmod(path, 0o755)


def read_log(log, wait_s=5.0):
    """The lines the fake slicer wrote (it runs on its own, so it may need a moment)."""
    end = time.time() + wait_s
    while time.time() < end:
        if os.path.isfile(log) and open(log).read().strip():
            break
        time.sleep(0.1)
    return open(log).read().split("\n")[:-1] if os.path.isfile(log) else []


def print_folder_files():
    from sciforge import export_ui

    return sorted(glob.glob(os.path.join(export_ui.print_folder(), "*")))


def out_files():
    return sorted(p for p in glob.glob(os.path.join(OUT, "*")) if os.path.isfile(p))


def mesh_info(path):
    import Mesh

    mesh = Mesh.Mesh(path)
    box = mesh.BoundBox
    bounds = (box.XMin, box.YMin, box.ZMin, box.XMax, box.YMax, box.ZMax)
    return mesh.Volume, bounds, mesh.isSolid()


def same_box(a, c, tol=1e-3):
    return all(abs(x - y) <= tol for x, y in zip(a, c))


def objects_3mf(path):
    """(object names, unit) written in a 3MF file."""
    with zipfile.ZipFile(path) as z:
        model = [n for n in z.namelist() if n.endswith(".model")]
        text = z.read(model[0]).decode("utf-8") if model else ""
    names = re.findall(r'<object [^>]*name="([^"]*)"', text)
    unit = re.search(r'<model[^>]* unit="([a-z]+)"', text)
    return names, unit.group(1) if unit else None


def open_print():
    i.ribbon_tab("UTILITIES")
    h.ribbon("3D Print")


# -- the design -----------------------------------------------------------------------------
def setup():
    from sciforge import export, export_ui

    os.makedirs(OUT, exist_ok=True)
    os.makedirs(BIN, exist_ok=True)
    os.makedirs(EMPTY, exist_ok=True)
    for path in out_files() + glob.glob(os.path.join(BIN, "*")):
        os.remove(path)
    App.ActiveDocument.saveAs(os.path.join(OUT, "pi_case.FCStd"))
    state["labels"] = [x.Label for x in s.bodies()]
    h.check("two bodies", len(state["labels"]) == 2, state["labels"])
    i.record_exports(program=None)  # the program picker: cancelled
    i.real_program_start()  # the fake slicers really get started
    del i.opened_folders[:]
    export.set_print_send_to("")
    export.set_slicer_program("")
    export.set_print_save_copy(False)
    export_ui.SLICER_ENV = {"PATH": EMPTY, "HOME": EMPTY}
    state["print_before"] = print_folder_files()


# -- A: no slicer found ---------------------------------------------------------------------
def a_open():
    h.fit()
    open_print()


a_open.wait_ms = 1500


def a_dialog():
    d = dialog()
    h.check("A 3D Print dialog", d is not None and d.windowTitle() == "3D Print", d)
    if d is None:
        return
    h.check(
        "A Send to: only Other... and Save file only",
        entries(d.send_to) == ["Other... (pick the program)", "Save file only"],
        entries(d.send_to),
    )
    h.check("A starts at Save file only", d.send_to.currentText() == "Save file only")
    h.check(
        "A says no slicer was found",
        "No slicer was found" in d.found_note.text() and d.found_note.isVisible(),
        d.found_note.text(),
    )
    h.shot("A-no-slicer")
    b.choose(d.send_to, "Other... (pick the program)")


a_dialog.wait_ms = 1000


def a_ok():
    d = dialog()
    if d is None:
        return
    h.check("A Program field empty (picker cancelled)", d.program.text() == "", d.program.text())
    h.check("A Program field can be typed in", d.program.isEnabled())
    i.dialog_button(d, "OK")


a_ok.wait_ms = 1200


def a_check():
    d = dialog()
    h.check(
        "A OK without a program: the dialog stays and says why",
        d is not None and "No slicer was found" in d.message.text(),
        d and d.message.text(),
    )
    h.check("A nothing written", print_folder_files() == state["print_before"], print_folder_files())
    if d is not None:
        i.dialog_button(d, "Cancel")


def a_closed():
    h.check("A Cancel closes", dialog() is None)
    h.check("A Cancel wrote nothing", print_folder_files() == state["print_before"])
    from sciforge import export

    h.check("A nothing remembered on Cancel", export.print_send_to() == "", export.print_send_to())


# -- B: a slicer is installed ---------------------------------------------------------------
def b_install():
    from sciforge import export_ui

    fake_slicer(os.path.join(BIN, "prusa-slicer"), PRUSA_LOG)
    export_ui.SLICER_ENV = {"PATH": BIN, "HOME": EMPTY}
    open_print()


b_install.wait_ms = 1500


def b_dialog():
    d = dialog()
    h.check("B 3D Print dialog", d is not None, d)
    if d is None:
        return
    h.check(
        "B PrusaSlicer found and listed first",
        entries(d.send_to) == ["PrusaSlicer", "Other... (pick the program)", "Save file only"],
        entries(d.send_to),
    )
    h.check("B starts at PrusaSlicer", d.send_to.currentText() == "PrusaSlicer")
    h.check(
        "B the program found is shown (not editable)",
        d.program.text() == os.path.join(BIN, "prusa-slicer") and not d.program.isEnabled(),
        d.program.text(),
    )
    h.check("B the note names it", "PrusaSlicer" in d.found_note.text(), d.found_note.text())
    h.check(
        "B all visible bodies ticked",
        sorted(x.Label for x in d.bodies.chosen()) == sorted(state["labels"]),
        [x.Label for x in d.bodies.chosen()],
    )
    h.check("B Format 3MF", d.format.currentText() == "3MF", d.format.currentText())
    h.check("B Refinement Medium", d.refinement.level.currentText() == "Medium")
    h.check(
        "B Unit Type greyed at Millimeter",
        d.unit.currentText() == "Millimeter" and not d.unit.isEnabled(),
        d.unit.currentText(),
    )
    h.check("B Save a copy offered", d.save_copy.isEnabled() and not d.save_copy.isChecked())
    i.set_check(d.save_copy, True)
    h.shot("B-dialog")


b_dialog.wait_ms = 1000


def b_ok():
    d = dialog()
    if d is not None:
        i.dialog_button(d, "OK")


b_ok.wait_ms = 2500


def b_check():
    from sciforge import export, export_ui

    h.check("B dialog closed", dialog() is None)
    lines = read_log(PRUSA_LOG)
    h.check("B PrusaSlicer was started with one file", len(lines) == 1, lines)
    sent = lines[0] if lines else ""
    h.check("B it is a 3MF", sent.endswith(".3mf"), sent)
    h.check(
        "B in SciForge's print folder",
        os.path.dirname(sent) == export_ui.print_folder(),
        (sent, export_ui.print_folder()),
    )
    h.check("B the file exists", os.path.isfile(sent), sent)
    if os.path.isfile(sent):
        volume, bounds, solid = mesh_info(sent)
        h.check("B 21000 mm3 (both bodies)", i.close(volume, 21000.0, 1e-4), volume)
        h.check(
            "B placed as in the design, in mm",
            same_box(bounds, (0, 0, 0, 80, 30, 10)),
            bounds,
        )
        h.check("B watertight", solid)
        names, unit = objects_3mf(sent)
        h.check(
            "B two objects named after the bodies",
            sorted(names) == sorted(state["labels"]),
            (names, state["labels"]),
        )
        h.check("B unit millimeter", unit == "millimeter", unit)
    copy = os.path.join(OUT, "pi_case.3mf")
    h.check("B the copy is beside the design", os.path.isfile(copy), out_files())
    if os.path.isfile(copy) and os.path.isfile(sent):
        h.check("B the copy is the same file", open(copy, "rb").read() == open(sent, "rb").read())
    h.check("B PrusaSlicer remembered", export.print_send_to() == "prusaslicer")
    h.check("B no folder opened when sending", not i.opened_folders, i.opened_folders)
    s.no_popups("3D Print")


# -- C: Other... ----------------------------------------------------------------------------
def c_open():
    fake_slicer(OTHER, OTHER_LOG)
    i.record_exports(program=OTHER)  # the program picker answers the second fake
    i.real_program_start()
    open_print()


c_open.wait_ms = 1500


def c_other():
    d = dialog()
    h.check("C 3D Print dialog", d is not None, d)
    if d is None:
        return
    h.check("C starts at PrusaSlicer (remembered)", d.send_to.currentText() == "PrusaSlicer")
    h.check("C Save a copy remembered", d.save_copy.isChecked())
    b.choose(d.send_to, "Other... (pick the program)")


c_other.wait_ms = 1000


def c_one_body_stl():
    d = dialog()
    if d is None:
        return
    h.check("C the picked program is shown", d.program.text() == OTHER, d.program.text())
    first = state["labels"][0]
    for k in range(d.bodies.count()):
        i.check_list_item(d.bodies, k, d.bodies.item(k).text() == first)
    h.check("C only box1 ticked", [x.Label for x in d.bodies.chosen()] == [first])
    b.choose(d.format, "STL (Binary)")
    h.check("C Unit Type still millimetres", d.unit.currentText() == "Millimeter")
    i.dialog_button(d, "OK")


c_one_body_stl.wait_ms = 2500


def c_check():
    from sciforge import export

    h.check("C dialog closed", dialog() is None)
    lines = read_log(OTHER_LOG)
    h.check("C the other slicer was started with one file", len(lines) == 1, lines)
    sent = lines[0] if lines else ""
    first = state["labels"][0]
    h.check("C an STL named after the body", os.path.basename(sent) == first + ".stl", sent)
    if os.path.isfile(sent):
        volume, bounds, solid = mesh_info(sent)
        h.check("C 12000 mm3 (box1 only)", i.close(volume, 12000.0, 1e-4), volume)
        h.check("C in mm, where box1 is", same_box(bounds, (0, 0, 0, 40, 30, 10)), bounds)
    h.check(
        "C copy beside the design, named after the body",
        os.path.isfile(os.path.join(OUT, first + ".stl")),
        out_files(),
    )
    h.check("C PrusaSlicer not started again", len(read_log(PRUSA_LOG, 0.5)) == 1)
    h.check("C Other remembered", export.print_send_to() == "other", export.print_send_to())
    h.check("C its program remembered", export.slicer_program() == OTHER, export.slicer_program())
    h.check("C STL remembered", export.print_format() == "STL (Binary)", export.print_format())


# -- D: Save file only, Cancel ----------------------------------------------------------------
def d_open():
    state["out_before"] = out_files()
    state["print_before"] = print_folder_files()
    open_print()


d_open.wait_ms = 1500


def d_file_only():
    d = dialog()
    h.check("D 3D Print dialog", d is not None, d)
    if d is None:
        return
    h.check(
        "D starts at Other... with its program",
        d.send_to.currentText() == "Other... (pick the program)" and d.program.text() == OTHER,
        (d.send_to.currentText(), d.program.text()),
    )
    b.choose(d.send_to, "Save file only")
    h.check("D Save a copy greyed", not d.save_copy.isEnabled())
    h.check("D Open the folder offered", d.open_folder.isEnabled())
    h.check("D Unit Type back on", d.unit.isEnabled())
    h.check("D Program greyed", not d.program.isEnabled())
    i.dialog_button(d, "Cancel")


d_file_only.wait_ms = 1200


def d_check():
    from sciforge import export

    h.check("D Cancel closes", dialog() is None)
    h.check("D nothing written beside the design", out_files() == state["out_before"], out_files())
    h.check("D nothing in the print folder", print_folder_files() == state["print_before"])
    h.check("D no slicer started", len(read_log(OTHER_LOG, 0.5)) == 1)
    h.check("D Cancel kept the choice", export.print_send_to() == "other")


# -- E: Preferences > 3D Print ----------------------------------------------------------------
def prefs():
    from sciforge import preferences_ui

    d = preferences_ui.PreferencesDialog.last
    try:
        return d if d is not None and d.isVisible() else None
    except RuntimeError:
        return None


def e_open():
    i.ribbon_tab("UTILITIES")
    h.ribbon("Preferences")
    m.process()


e_open.wait_ms = 1500


def e_page():
    from PySide import QtCore

    d = prefs()
    if not h.check("E Preferences window", d is not None):
        return
    for item in d.pages.findItems("*", QtCore.Qt.MatchWildcard | QtCore.Qt.MatchRecursive):
        if item.data(0, QtCore.Qt.UserRole) == "print":
            d.pages.scrollToItem(item)
            w.click(d.pages.viewport(), d.pages.visualItemRect(item).center())
            break
    h.check("E the 3D Print page", d.current_page() == "print", d.current_page())
    send_to = d.widgets.get("print_send_to")
    program = d.widgets.get("slicer_program")
    h.check(
        "E Send to shows Other",
        send_to is not None and send_to.currentData() == "other",
        send_to and send_to.currentText(),
    )
    h.check(
        "E the program is shown",
        program is not None and program.field.text() == OTHER,
        program and program.field.text(),
    )
    note = getattr(d, "print_note", None)
    h.check(
        "E the page names the slicer found",
        note is not None and "PrusaSlicer" in note.text(),
        note.text() if note is not None else None,
    )
    h.shot("E-preferences")
    if send_to is not None:
        b.choose(send_to, "Save file only")
    ok = m.find_child(d, "SciForgePreferencesOK")
    if h.check("E OK button", ok is not None):
        w.click(ok)
        m.process()


e_page.wait_ms = 1200


def e_print():
    from sciforge import export

    h.check("E Preferences closed", prefs() is None)
    h.check("E kept", export.print_send_to() == "file", export.print_send_to())
    open_print()


e_print.wait_ms = 1500


def e_check():
    d = dialog()
    h.check(
        "E 3D Print starts at Save file only",
        d is not None and d.send_to.currentText() == "Save file only",
        d and d.send_to.currentText(),
    )
    if d is not None:
        i.dialog_button(d, "Cancel")


def cleanup():
    from sciforge import export, export_ui

    export_ui.SLICER_ENV = None
    export_ui.PROGRAM_DIALOG = None
    export.set_print_send_to("")
    export.set_slicer_program("")
    export.set_print_format("3MF")
    export.set_print_save_copy(False)
    h.check("dialog closed at the end", dialog() is None)
    h.shot("end")


h.run(
    "send_to_slicer",
    [i.new_design("SendToSlicer")]
    + s.box_steps("box1", (0, 0, 40, 30), 10, i.XY_CLICK)
    + s.box_steps("box2", (50, 0, 80, 30), 10, i.XY_CLICK, new_body=True)
    + [
        setup,
        a_open,
        a_dialog,
        a_ok,
        a_check,
        a_closed,
        b_install,
        b_dialog,
        b_ok,
        b_check,
        c_open,
        c_other,
        c_one_body_stl,
        c_check,
        d_open,
        d_file_only,
        d_check,
        e_open,
        e_page,
        e_print,
        e_check,
        cleanup,
    ],
)
