# SPDX-License-Identifier: LGPL-2.1-or-later
"""Flat pattern of a U channel with a hole in a wall, exported as DXF and read back, then
saved and reopened, real input only: SHEET METAL > Create Flat Pattern, a click on the
channel's floor, OK (116.52389 long: 56 + 28 + 28 + 2 BA, the hole a circle), FLAT PATTERN >
Export DXF (the file name typed, Convert Splines to Polylines ticked, OK): the DXF holds the
outline (4 lines), the hole (1 circle), one up bend centre line per bend, two extent lines per
bend and a note per bend, each on its own layer; with the bend lines switched off they are
gone. The browser's right-click Export DXF opens the same dialog. Saved (Ctrl+S) and
reopened, the flat pattern is still there, still 116.52389 long, and opens with a
double-click."""

import os

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import flatpattern_steps as fs
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import versions_input as vi

V = App.Vector
s = {}


def setup():
    fs.build("FlatU", fs.U_STEPS, fs.TOP)
    s["path"] = os.path.join(fs.out_dir(), "flat_u.FCStd")
    s["dxf"] = os.path.join(fs.out_dir(), "flat_u.dxf")
    s["dxf2"] = os.path.join(fs.out_dir(), "flat_u_plain.dxf")
    for p in (s["path"], s["dxf"], s["dxf2"]):
        if os.path.exists(p):
            os.remove(p)


def sheet_tab():
    fs.tab("sheet_metal")


def create():
    Gui.Selection.clearSelection()
    h.ribbon("Create Flat Pattern")


def click_floor():
    h.fit()
    h.click(fs.U_TOP)


def picked():
    fs.settle()
    text = fs.message()
    h.check("dialog says 116.52 x 20.00", "116.52 x 20.00" in text, text)
    h.check("two bends", "2 bend" in text, text)


def press_ok():
    fs.ok()


def flat_made():
    fs.settle()
    fp = fs.flat()
    bb = fs.flat_box(fp)
    h.check("flat 116.52389 long", bb is not None and fs.close(bb.XLength, fs.U_FLAT), bb)
    h.check("FLAT PATTERN tab", fs.current_tab() == "flat_pattern", fs.current_tab())
    solid = fp.Shape.Solids[0]
    v = solid.Volume
    h.check(
        "hole through the flat (116.52389 * 20 - 9 pi)",
        fs.close(v, fs.U_FLAT * 20 - 9 * 3.14159265358979),
        v,
    )
    from sciforge import flatpattern

    h.check(
        "both bends up (toward the stationary face)", all(b["up"] for b in flatpattern.bends(fp))
    )
    h.shot("1-flat")


def export_click():
    h.ribbon("Export DXF")


def export_dialog():
    p = fs.export_panel()
    h.check("Export DXF dialog open", p is not None and fs.dialog_open())
    if p is None:
        return
    h.check("bend center lines on by default", p.centre.isChecked())
    h.check("bend extent lines on by default", p.extent.isChecked())
    h.check("Convert Splines to Polylines off by default", not p.polylines.isChecked())
    h.check("tolerance 0.1 mm", abs(p.tolerance.value() - 0.1) < 1e-9, p.tolerance.value())
    from SciForgeTests.gui import dialog_input as ui

    ui.type_into(p.path, s["dxf"])
    fs.click_check(p.polylines)
    h.check("tolerance editable once converting", p.tolerance.widget.isEnabled())


def export_ok():
    fs.ok()


def dxf_read_back():
    h.check("dialog closed", not fs.dialog_open())
    h.check("DXF written", os.path.exists(s["dxf"]), s["dxf"])
    if not os.path.exists(s["dxf"]):
        return
    counts = fs.dxf_counts(s["dxf"])
    h.check("outline: 4 lines", counts.get("OUTER_PROFILES") == {"LINE": 4}, counts)
    h.check("hole: 1 circle", counts.get("INTERIOR_PROFILES") == {"CIRCLE": 1}, counts)
    h.check("2 up bend centre lines", counts.get("BEND_CENTER_LINES_UP") == {"LINE": 2}, counts)
    h.check("no down bend lines", "BEND_CENTER_LINES_DOWN" not in counts, counts)
    h.check("4 bend extent lines", counts.get("BEND_EXTENT_LINES") == {"LINE": 4}, counts)
    h.check("2 bend notes", counts.get("TEXT") == {"TEXT": 2}, counts)
    with open(s["dxf"], encoding="utf-8") as handle:
        text = handle.read()
    h.check("a note says UP 90.0", "UP 90.0" in text)


def browser_export():
    fs.browser_menu("Flat Pattern", "Export DXF")


def browser_export_dialog():
    p = fs.export_panel()
    h.check("right-click > Export DXF opens the dialog", p is not None and fs.dialog_open())
    if p is None:
        return
    from SciForgeTests.gui import dialog_input as ui

    ui.type_into(p.path, s["dxf2"])
    fs.click_check(p.centre)
    fs.click_check(p.extent)


def browser_export_ok():
    fs.ok()


def plain_read_back():
    counts = fs.dxf_counts(s["dxf2"]) if os.path.exists(s["dxf2"]) else {}
    h.check("second DXF written", bool(counts), s["dxf2"])
    h.check("no bend centre lines when switched off", "BEND_CENTER_LINES_UP" not in counts, counts)
    h.check("no extent lines when switched off", "BEND_EXTENT_LINES" not in counts, counts)
    h.check("outline still there", counts.get("OUTER_PROFILES") == {"LINE": 4}, counts)


def finish():
    h.ribbon("Finish Flat Pattern")


def save():
    App.ActiveDocument.saveAs(s["path"])
    h.check("saved", os.path.isfile(s["path"]), s["path"])


def ctrl_s():
    App.ActiveDocument.recompute()
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


def describe():
    h.check("the Save dialog asks for a version description", vi.version_dialog() is not None)
    vi.accept_save()


def reopen():
    h.check("saved (nothing unsaved)", not App.ActiveDocument.isTouched())
    App.closeDocument(App.ActiveDocument.Name)
    App.openDocument(s["path"])
    h.fit()


def reopened():
    fp = fs.flat()
    h.check("flat pattern kept in the file", fp is not None)
    if fp is None:
        return
    bb = fs.flat_box(fp)
    h.check(
        "reopened flat still 116.52389 long", bb is not None and fs.close(bb.XLength, fs.U_FLAT), bb
    )
    h.check("reopened flat valid", "Invalid" not in fp.State, fp.State)
    h.check("flat hidden after reopening", not fp.ViewObject.Visibility)


def open_again():
    h.check("browser row double-clicked", fs.double_click_browser("Flat Pattern"))


def opened_again():
    fs.settle()
    h.check(
        "reopened file: double-click opens it", fs.current_tab() == "flat_pattern", fs.current_tab()
    )


def finish_again():
    h.ribbon("Finish Flat Pattern")


def done():
    h.check("back to the folded part", fs.current_tab() != "flat_pattern")


h.run(
    "flatpattern_u_channel_dxf",
    [
        setup,
        sheet_tab,
        create,
        click_floor,
        picked,
        press_ok,
        flat_made,
        export_click,
        export_dialog,
        export_ok,
        dxf_read_back,
        browser_export,
        browser_export_dialog,
        browser_export_ok,
        plain_read_back,
        finish,
        save,
        ctrl_s,
        describe,
        reopen,
        reopened,
        open_again,
        opened_again,
        finish_again,
        done,
    ],
)
