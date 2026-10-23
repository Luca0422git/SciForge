# SPDX-License-Identifier: LGPL-2.1-or-later
"""Which corner relief the flat pattern cuts where two bends meet, real input.

1. A plate 100 x 60 with a 5 x 5 notch at one corner, an edge flange 20 high on its right
   edge and one on its back edge, the corner between them closed by sm-more's Corner Closure
   (Symmetric Gap 1 mm, Tear relief); made in setup with the tools' own code. SHEET METAL >
   Create Flat Pattern, a click on the plate: the flat is 119.26 x 79.26 (100 - 2 + BA + 19
   by 60 - 2 + BA + 19; the walls are 21 - (R + T) = 19 long), 2 bends, and the closed corner
   keeps the Corner Closure's Tear: no rule relief is cut there (the rule's 4 mm Round would
   have been).
2. A tray (four mitred edge flanges 10 high on a 50 x 30 plate): the flat has the rule's
   Round reliefs (arcs in its outline). Then the Flange step is edited in its own dialog
   (timeline double-click): Corner Relief (2 bends) override, Square, 3 mm, OK; the Flat
   Pattern follows the edit: double-click it in the browser, its corners are 3 mm squares (no
   arcs left in the outline), less material taken than by the 4 mm rounds."""

import FreeCAD as App

from SciForgeTests.gui import flatpattern_steps as fs
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sheetmetal_steps as sm

V = App.Vector
s = {}
CLOSURE_STEPS = [
    {
        "op": "sketch",
        "id": "s1",
        "plane": "XY",
        "geometry": [{"polyline": [[0, 0], [100, 0], [100, 55], [95, 55], [95, 60], [0, 60]]}],
    },
    {"op": "sf_flange", "id": "f1", "kind": "base", "profile": "s1"},
    {
        "op": "sf_flange",
        "id": "f2",
        "kind": "edge",
        "edges": [[100, 20, 1]],
        "options": {"height": 20},
    },
    {
        "op": "sf_flange",
        "id": "f3",
        "kind": "edge",
        "edges": [[50, 60, 1]],
        "options": {"height": 20},
    },
    {
        "op": "sf_sm_corner_closure",
        "id": "c1",
        "dominant": [100, 55, 12],
        "submissive": [95, 60, 12],
        "options": {"alignment": "symmetric", "gap": 1.0, "relief": "tear"},
    },
]
TRAY_STEPS = [
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


def _removed(fp):
    """Volume the corner reliefs take away (the flat with them off, less with them on)."""
    doc = App.ActiveDocument
    with_reliefs = fp.Shape.Solids[0].Volume
    fp.CornerReliefs = False
    doc.recompute()
    without = fp.Shape.Solids[0].Volume
    fp.CornerReliefs = True
    doc.recompute()
    return without - with_reliefs


def _arcs(fp):
    from sciforge import flatpattern

    outer, _interior, _bends = flatpattern.dxf_entities(fp)
    return sum(1 for e in outer if e[0] in ("arc", "circle"))


# -- 1. a corner closed by Corner Closure ------------------------------------------------------
def setup():
    fs.build("FlatCornerClosure", CLOSURE_STEPS)
    fs.tab("sheet_metal")


def create():
    h.ribbon("Create Flat Pattern")


def click_plate():
    h.fit()
    h.click(V(50, 30, 1))


def press_ok():
    fs.settle()
    text = fs.message()
    h.check(
        "dialog says 119.26 x 79.26, 2 bends", "119.26 x 79.26" in text and "2 bend" in text, text
    )
    fs.ok()


def closure_flat():
    from sciforge import flatpattern

    fs.settle()
    fp = fs.flat()
    bb = fs.flat_box(fp)
    w = 98 + fs.BA + 19
    d = 58 + fs.BA + 19
    h.check(
        "flat 119.26 x 79.26",
        bb is not None and fs.close(bb.XLength, w) and fs.close(bb.YLength, d),
        bb,
    )
    h.check("two bends", fp.BendCount == 2, fp.BendCount)
    removed = _removed(fp)
    h.check("the closed corner keeps the Corner Closure's Tear: no relief cut", abs(removed) < 1e-6)
    flat = fp.Shape.Solids[0]
    rule_only = flatpattern.with_corner_reliefs(
        flat, flatpattern.bends(fp), fs.body(), float(fp.Thickness)
    )
    h.check(
        "(the rule's 4 mm Round would have been cut at that corner)",
        rule_only.Volume < flat.Volume - 1.0,
        (rule_only.Volume, flat.Volume),
    )
    h.shot("1-closure-flat")


def finish_closure():
    h.ribbon("Finish Flat Pattern")


# -- 2. the Flange's own corner relief, edited after the flat pattern ---------------------------
def setup_tray():
    fs.build("FlatCornerTray", TRAY_STEPS)
    fs.tab("sheet_metal")


def click_floor():
    h.fit()
    h.click(V(25, 15, 1))


def press_ok_tray():
    fs.settle()
    text = fs.message()
    h.check("dialog says 68.52 x 48.52", "68.52 x 48.52" in text, text)
    fs.ok()


def round_reliefs():
    fs.settle()
    fp = fs.flat()
    s["round"] = _removed(fp)
    h.check("the rule's Round reliefs: arcs in the outline", _arcs(fp) >= 4, _arcs(fp))
    h.check("round reliefs take material", s["round"] > 1.0, s["round"])


def finish_tray():
    h.ribbon("Finish Flat Pattern")


def edit_flange():
    fs.settle()
    titles = [t for t in fs.timeline_titles() if t.startswith("Flange")]
    h.check("two Flange steps in the timeline", len(titles) == 2, titles)
    sm.double_click_timeline(titles[-1] if titles else "Flange 2")


def override_on():
    sm.settle()
    sm.toggle("override_corner_relief")


def square():
    sm.settle()
    h.check("Corner Shape shown", sm.shown("corner_shape"))
    sm.choose("corner_shape", "Square")


def size_3():
    sm.settle()
    sm.type_field("corner_size", "3")


def flange_ok():
    sm.settle()
    sm.ok()


def reopen():
    fs.settle()
    App.ActiveDocument.recompute()
    h.check("browser row double-clicked", fs.double_click_browser("Flat Pattern"))


def square_reliefs():
    fs.settle()
    h.check("the flat pattern is open", fs.current_tab() == "flat_pattern", fs.current_tab())
    fp = fs.flat()
    h.check("flat pattern up to date", "Invalid" not in fp.State and "Touched" not in fp.State)
    arcs = _arcs(fp)
    h.check("the Flange's Square reliefs: no arcs left in the outline", arcs == 0, arcs)
    removed = _removed(fp)
    h.check(
        "3 mm squares take less than the 4 mm rounds",
        1.0 < removed < s["round"],
        (removed, s["round"]),
    )
    h.shot("2-square-reliefs")


def finish_square():
    h.ribbon("Finish Flat Pattern")
    fs.settle()
    h.check("back to the folded part", fs.current_tab() != "flat_pattern", fs.current_tab())


h.run(
    "flatpattern_corners",
    [
        setup,
        create,
        click_plate,
        press_ok,
        closure_flat,
        finish_closure,
        setup_tray,
        create,
        click_floor,
        press_ok_tray,
        round_reliefs,
        finish_tray,
        edit_flange,
        override_on,
        square,
        size_3,
        flange_ok,
        reopen,
        square_reliefs,
        finish_square,
    ],
)
