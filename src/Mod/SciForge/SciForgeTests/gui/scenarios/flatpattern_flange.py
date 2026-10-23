# SPDX-License-Identifier: LGPL-2.1-or-later
"""Flat pattern of a part made with the Flange (sm-forming): a 50 x 30 base flange with a
10 mm edge flange 10 wide in the middle of its right edge and straight bend reliefs (made in
setup with the Flange's own code). Real input: SHEET METAL > Create Flat Pattern, a click on
the plate's top: 59.26 x 30.00, 1 bend (48 + BA + 9); OK; the flat is one up bend, the
reliefs are in its outline; Export DXF: the outline is straight lines only (the reliefs are
square), one up centre line, two extent lines; Unfold All Bends from the same face lays the
body flat in the timeline with the same size; Esc cancels it."""

import os

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import flatpattern_steps as fs
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}
FLAT = 48 + fs.BA + 9
STEPS = [
    {"op": "sketch", "id": "s1", "plane": "XY", "geometry": [{"rect": [0, 0, 50, 30]}]},
    {"op": "sf_flange", "id": "f1", "kind": "base", "profile": "s1"},
    {
        "op": "sf_flange",
        "id": "f2",
        "kind": "edge",
        "edges": [[50, 15, 1]],
        "options": {
            "height": 10,
            "width_type": "symmetric",
            "width": 10,
            "override_bend_relief": True,
            "relief_shape": "straight",
            "relief_width": 1,
            "relief_depth": 0.5,
            "relief_remnant": 2,
        },
    },
]
PLATE = V(20, 15, 1)


def setup():
    fs.build("FlatFlange", STEPS)
    s["volume"] = fs.volume()
    s["dxf"] = os.path.join(fs.out_dir(), "flat_flange.dxf")
    if os.path.exists(s["dxf"]):
        os.remove(s["dxf"])


def made():
    from sciforge import sheetmetal

    h.check("the flange part is sheet metal", sheetmetal.is_sheet_metal_body(fs.body()))
    h.check("folded volume 1588.561945", fs.close(s["volume"], 1588.561945), s["volume"])
    fs.tab("sheet_metal")


def create():
    Gui.Selection.clearSelection()
    h.ribbon("Create Flat Pattern")


def click_plate():
    h.fit()
    h.click(PLATE)


def size_said():
    fs.settle()
    text = fs.message()
    h.check(
        "dialog says 59.26 x 30.00 and 1 bend", "59.26 x 30.00" in text and "1 bend" in text, text
    )


def press_ok():
    fs.ok()


def flat_made():
    fs.settle()
    from sciforge import flatpattern

    fp = fs.flat()
    bb = fs.flat_box(fp)
    h.check(
        "flat 59.26195 x 30",
        bb is not None and fs.close(bb.XLength, FLAT) and fs.close(bb.YLength, 30),
        bb,
    )
    bends = flatpattern.bends(fp)
    h.check(
        "one up bend of 90 degrees, R 1",
        len(bends) == 1
        and bends[0]["up"]
        and abs(bends[0]["angle"] - 90) < 1e-6
        and abs(bends[0]["radius"] - 1) < 1e-6,
        bends,
    )
    v = fp.Shape.Solids[0].Volume
    expect = s["volume"] - 10 * 3.141592653589793 / 2 * 3 / 2 + fs.BA * 10
    h.check("flat volume: the bend laid out as BA x 10", fs.close(v, expect), (v, expect))
    h.shot("1-flat")


def export():
    h.ribbon("Export DXF")


def export_path():
    p = fs.export_panel()
    h.check("Export DXF open", p is not None)
    if p is not None:
        ui.type_into(p.path, s["dxf"])


def export_ok():
    fs.ok()


def read_back():
    counts = fs.dxf_counts(s["dxf"]) if os.path.exists(s["dxf"]) else {}
    outer = counts.get("OUTER_PROFILES", {})
    h.check(
        "outline written, straight lines only",
        outer and set(outer) == {"LINE"} and outer["LINE"] > 8,
        counts,
    )
    h.check("one up centre line", counts.get("BEND_CENTER_LINES_UP") == {"LINE": 1}, counts)
    h.check("two extent lines", counts.get("BEND_EXTENT_LINES") == {"LINE": 2}, counts)


def finish():
    h.ribbon("Finish Flat Pattern")


def unfold():
    Gui.Selection.clearSelection()
    h.ribbon("Unfold")


def unfold_pick():
    h.fit()
    h.click(PLATE)


def unfold_all():
    p = fs.sheet_panel()
    if p is not None:
        fs.click_check(p.all_bends)


def unfold_preview():
    fs.settle()
    p = fs.sheet_panel()
    t = p.target if p is not None else None
    bb = t.Shape.BoundBox if t is not None else None
    h.check(
        "Unfold lays the flange part flat, 59.26195 long",
        bb is not None and fs.close(bb.XLength, FLAT),
        bb,
    )


def unfold_esc():
    fs.esc()


def unfold_cancelled():
    fs.settle()
    h.check(
        "Esc: no Unfold left",
        not any(t.startswith("Unfold") for t in fs.timeline_titles()),
        fs.timeline_titles(),
    )
    h.check("folded part back", fs.close(fs.volume(), s["volume"]), fs.volume())


h.run(
    "flatpattern_flange",
    [
        setup,
        made,
        create,
        click_plate,
        size_said,
        press_ok,
        flat_made,
        export,
        export_path,
        export_ok,
        read_back,
        finish,
        unfold,
        unfold_pick,
        unfold_all,
        unfold_preview,
        unfold_esc,
        unfold_cancelled,
    ],
)
