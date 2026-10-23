# SPDX-License-Identifier: LGPL-2.1-or-later
"""Flat pattern of a tray (sm-forming's Flange: a 50 x 30 base flange with four 10 mm edge
flanges, mitred at the corners; made in setup with the Flange's own code), real input: SHEET
METAL > Create Flat Pattern, a click on the tray's floor: a cross-shaped flat 68.52 x 48.52
(46 + 2 (BA + 9) by 26 + 2 (BA + 9)), four up bends; at each corner, where two bends meet,
the rule's Round corner relief (4 mm across) is cut out of the flat; Export DXF: the reliefs
are arcs of the outline."""

import os

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import flatpattern_steps as fs
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}
STEPS = [
    {"op": "sketch", "id": "s1", "plane": "XY", "geometry": [{"rect": [0, 0, 50, 30]}]},
    {"op": "sf_flange", "id": "f1", "kind": "base", "profile": "s1"},
    {
        "op": "sf_flange",
        "id": "f2",
        "kind": "edge",
        "edges": [[50, 15, 1], [25, 30, 1], [0, 15, 1], [25, 0, 1]],
        "options": {"height": 10},
    },
]


def setup():
    fs.build("FlatTray", STEPS)
    s["dxf"] = os.path.join(fs.out_dir(), "flat_tray.dxf")
    if os.path.exists(s["dxf"]):
        os.remove(s["dxf"])
    fs.tab("sheet_metal")


def create():
    Gui.Selection.clearSelection()
    h.ribbon("Create Flat Pattern")


def click_floor():
    h.fit()
    h.click(V(25, 15, 1))


def press_ok():
    fs.settle()
    text = fs.message()
    h.check(
        "dialog says 68.52 x 48.52, 4 bends", "68.52 x 48.52" in text and "4 bend" in text, text
    )
    fs.ok()


def flat_made():
    fs.settle()
    fp = fs.flat()
    bb = fs.flat_box(fp)
    w = 46 + 2 * (fs.BA + 9)
    d = 26 + 2 * (fs.BA + 9)
    h.check(
        "cross-shaped flat 68.52 x 48.52",
        bb is not None and fs.close(bb.XLength, w) and fs.close(bb.YLength, d),
        bb,
    )
    h.check("four bends", fp.BendCount == 4)
    h.check("corner reliefs on", fp.CornerReliefs)
    with_reliefs = fp.Shape.Solids[0].Volume
    s["with"] = with_reliefs
    h.shot("1-tray-flat")


def export():
    h.ribbon("Export DXF")


def export_path():
    p = fs.export_panel()
    if h.check("Export DXF open", p is not None):
        ui.type_into(p.path, s["dxf"])


def export_ok():
    fs.ok()


def read_back():
    counts = fs.dxf_counts(s["dxf"]) if os.path.exists(s["dxf"]) else {}
    outer = counts.get("OUTER_PROFILES", {})
    h.check("the corner reliefs are arcs of the outline", outer.get("ARC", 0) >= 4, counts)
    h.check("4 up bend centre lines", counts.get("BEND_CENTER_LINES_UP") == {"LINE": 4}, counts)


def finish():
    h.ribbon("Finish Flat Pattern")


def reliefs_off():
    # the Flat Pattern's own Corner Reliefs setting (property): without it the flat is whole
    fp = fs.flat()
    fp.CornerReliefs = False
    App.ActiveDocument.recompute()
    v = fp.Shape.Solids[0].Volume
    h.check("the four reliefs took material away", v > s["with"] + 1.0, (v, s["with"]))


h.run(
    "flatpattern_tray",
    [
        setup,
        create,
        click_floor,
        press_ok,
        flat_made,
        export,
        export_path,
        export_ok,
        read_back,
        finish,
        reliefs_off,
    ],
)
