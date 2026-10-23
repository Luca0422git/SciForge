# SPDX-License-Identifier: LGPL-2.1-or-later
"""What the SHEET METAL flat tools refuse, and why, real input only. An empty design: Create
Flat Pattern, Unfold, Refold and Rip say why next to the mouse and open nothing; Convert to
Sheet Metal says there is no solid. A shelled box with sharp corners: Convert names the sharp
edge and says to fillet it, then convert; OK waits; Esc closes, nothing changed. A stepped block
(two thicknesses): "not one sheet of even thickness"; Cancel. Never a pop-up or a Report
error."""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import flatpattern_steps as fs
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}

SHARP_BOX = [
    {"op": "sketch", "id": "s1", "plane": "XY", "geometry": [{"rect": [0, 0, 30, 20]}]},
    {"op": "extrude", "id": "e1", "profile": "s1", "distance": 10},
    {
        "op": "shell",
        "id": "sh1",
        "thickness": 1,
        "faces": {"type": "plane", "normal": [0, 0, 1], "count": 1},
    },
]
STEPPED = [
    {"op": "sketch", "id": "s1", "plane": "XY", "geometry": [{"rect": [0, 0, 30, 20]}]},
    {"op": "extrude", "id": "e1", "profile": "s1", "distance": 3},
    {"op": "sketch", "id": "s2", "plane": "XY", "geometry": [{"rect": [0, 0, 10, 20]}]},
    {"op": "extrude", "id": "e2", "profile": "s2", "distance": 8},
]


def empty_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("FlatEmpty")
    fs.tab("sheet_metal")


def empty_flat():
    h.ribbon("Create Flat Pattern")


def empty_flat_said():
    h.check("Create Flat Pattern on an empty design opens nothing", not fs.dialog_open())
    fs.no_popups("Create Flat Pattern")


def empty_unfold():
    h.ribbon("Unfold")


def empty_unfold_said():
    h.check("Unfold on an empty design opens nothing", not fs.dialog_open())


def empty_refold():
    h.ribbon("Refold")


def empty_refold_said():
    h.check("Refold on an empty design opens nothing", not fs.dialog_open())


def empty_rip():
    h.ribbon("Rip")


def empty_rip_said():
    h.check("Rip on an empty design opens nothing", not fs.dialog_open())
    fs.no_popups("Rip")


def empty_convert():
    fs.menu("MODIFY", "Convert to Sheet Metal")


def empty_convert_said():
    p = fs.sheet_panel()
    h.check("Convert dialog open", p is not None and fs.dialog_open())
    text = fs.message()
    h.check("says there is no solid", "no solid body" in text, text)


def empty_convert_ok():
    fs.ok()


def empty_convert_waits():
    h.check("OK waits without a solid", fs.dialog_open())


def empty_convert_cancel():
    fs.cancel()


def sharp_box():
    App.closeDocument(App.ActiveDocument.Name)
    fs.build("FlatSharp", SHARP_BOX)
    s["volume"] = fs.volume()
    fs.tab("sheet_metal")


def sharp_convert():
    Gui.Selection.clearSelection()
    fs.menu("MODIFY", "Convert to Sheet Metal")


def sharp_click():
    h.fit()
    h.click(V(15, 0, 5))  # the front wall


def sharp_refused():
    fs.settle()
    text = fs.message()
    h.check("sharp corner named", "sharp corner" in text and "Edge" in text, text)
    # Rip works on sheet metal only: the advice is to fillet the corner, then convert (QA)
    h.check(
        "says fillet it, then convert (not Rip)",
        "fillet" in text and "then convert" in text and "Rip" not in text,
        text,
    )
    p = fs.sheet_panel()
    h.check("no thickness shown", p is not None and p.thickness.text() == "-")


def sharp_ok():
    fs.ok()


def sharp_waits():
    fs.settle()
    h.check("OK refused: dialog still open", fs.dialog_open())
    from sciforge import sheetmetal

    h.check("not converted", not sheetmetal.is_sheet_metal_body(fs.body()))


def sharp_esc():
    fs.esc()


def sharp_after():
    fs.settle()
    h.check("Esc closes the dialog", not fs.dialog_open())
    h.check("part unchanged", fs.close(fs.volume(), s["volume"]), fs.volume())
    titles = fs.timeline_titles()
    h.check("no Convert step left", not any(t.startswith("Convert") for t in titles), titles)


def stepped():
    App.closeDocument(App.ActiveDocument.Name)
    fs.build("FlatStepped", STEPPED)
    fs.tab("sheet_metal")


def stepped_convert():
    Gui.Selection.clearSelection()
    fs.menu("MODIFY", "Convert to Sheet Metal")


def stepped_click():
    h.fit()
    h.click(V(20, 10, 3))  # the low top face


def stepped_refused():
    fs.settle()
    text = fs.message()
    h.check("uneven thickness refused", "even thickness" in text, text)


def stepped_cancel():
    fs.cancel()


def stepped_after():
    fs.settle()
    h.check("Cancel closes the dialog", not fs.dialog_open())
    fs.no_popups("Cancel")


h.run(
    "flatpattern_refusals",
    [
        empty_design,
        empty_flat,
        empty_flat_said,
        empty_unfold,
        empty_unfold_said,
        empty_refold,
        empty_refold_said,
        empty_rip,
        empty_rip_said,
        empty_convert,
        empty_convert_said,
        empty_convert_ok,
        empty_convert_waits,
        empty_convert_cancel,
        sharp_box,
        sharp_convert,
        sharp_click,
        sharp_refused,
        sharp_ok,
        sharp_waits,
        sharp_esc,
        sharp_after,
        stepped,
        stepped_convert,
        stepped_click,
        stepped_refused,
        stepped_cancel,
        stepped_after,
    ],
)
