# SPDX-License-Identifier: LGPL-2.1-or-later
"""A third sheet metal journey: an open tray, real input only, in the default rule Steel (mm)
(T = R = 1, K 0.44, gap 1, 2-bend corner relief Round 4 mm at the bend lines' crossing).
Create Sketch on XY, an 80 x 50 rectangle; Flange, a click inside: a 1 mm plate; Flange on
all four top edges (four clicks), Height 20: a tray, four mitred corners. MODIFY > Corner
Closure on the front-right corner with a Round relief: the closed corner laid flat, a
4 mm hole cut where the bends cross and folded back (less material). Create Flat Pattern
from the floor: (80 - 2 (R + T)) + 2 BA + 2 (H - R) by (50 - 2 (R + T)) + 2 BA + 2 (H - R),
4 bends, every corner relieved (the rule's Round at the three mitred corners, the closure's
own at the fourth); Export DXF read back: the reliefs are arcs of the outline. Finish Flat
Pattern; Ctrl+Z takes the flat pattern back out, Ctrl+Y."""

import math
import os

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import flatpattern_steps as fs
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sheetmetal_steps as sm
from SciForgeTests.gui import smmore_steps as smm
from SciForgeTests.gui import surface_steps as st

V = App.Vector
s = {}
LX, LY, H = 80.0, 50.0, 20.0
T = R = 1.0
BA = math.pi / 2 * (R + 0.44 * T)
FLAT_X = (LX - 2 * (R + T)) + 2 * BA + 2 * (H - R)
FLAT_Y = (LY - 2 * (R + T)) + 2 * BA + 2 * (H - R)
O = 0.5 * math.sqrt(2)  # the rule's 1 mm gap: each mitred end 0.5 mm off the bisector


def doc():
    return App.ActiveDocument


def body():
    return doc().getObject(s["body"]) if s.get("body") else None


def vol():
    b = body()
    return sm.volume(b) if b is not None else 0.0


def solid_ok(where):
    b = body()
    bad = [o.Label for o in doc().Objects if "Invalid" in o.State or "Error" in o.State]
    h.check("%s: nothing in error" % where, not bad, bad)
    h.check(
        "%s: one valid solid" % where,
        b is not None and b.Shape.isValid() and len(b.Shape.Solids) == 1,
    )


def corner_panel():
    from sciforge import sheetmetal_corner_ui

    return smm.panel(sheetmetal_corner_ui.CornerPanel)


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("JourneyTray")
    h.fit()
    folder = os.path.join(h.OUT_DIR, "journey_sheetmetal")
    os.makedirs(folder, exist_ok=True)
    s["dxf"] = os.path.join(folder, "journey_tray.dxf")
    if os.path.exists(s["dxf"]):
        os.remove(s["dxf"])


def sheet_metal_tab():
    sm.tab()


def create_sketch():
    h.ribbon("Create Sketch")


def pick_xy():
    st.open_sketch_clicked(V(12, -8, 0))


def draw_rect():
    sk = h.in_sketch()
    if h.check("a sketch opens on XY", sk is not None):
        h.draw_rectangle(sk, 0, 0, LX, LY)


def finish_sketch():
    h.ribbon("Finish Sketch")


def flange_base():
    h.fit()
    h.click_empty()
    h.ribbon("Flange")


def click_profile():
    h.fit()
    h.click(V(40, 25, 0))


def base_ok():
    sm.settle()
    b = sm.target_body()
    h.check("a 1 mm plate", b is not None and sm.near(sm.volume(b), LX * LY))
    if b is not None:
        s["body"] = b.Name
    sm.ok()


def flange_edges():
    h.fit()
    Gui.Selection.clearSelection()
    h.ribbon("Flange")


def edge_clicker(name, point):
    def click():
        sm.settle()
        h.fit()
        h.check("clicked the %s edge" % name, h.click_edge(point))

    click.__name__ = "click_%s_edge" % name
    return click


def height_20():
    sm.settle()
    p = sm.panel()
    h.check(
        "an edge flange on four edges",
        p is not None and p.kind == "edge" and len(p.refs) == 4,
        p and p.refs,
    )
    sm.type_field("height", "20")


def tray_ok():
    sm.settle()
    h.check("no message", not sm.message(), sm.message())
    sm.ok()


def tray_made():
    h.check("dialog closed", sm.panel() is None)
    bb = body().Shape.BoundBox
    h.check(
        "a tray 80 x 50, walls up to 21", abs(bb.XLength - LX) < 1e-6 and abs(bb.ZMax - 21) < 1e-6
    )
    for name, p in (
        ("front-right", V(LX - 0.3, 0.3, 10)),
        ("front-left", V(0.3, 0.3, 10)),
        ("back-right", V(LX - 0.3, LY - 0.3, 10)),
        ("back-left", V(0.3, LY - 0.3, 10)),
    ):
        h.check(
            "%s corner mitred (open on the bisector)" % name,
            not body().Shape.isInside(p, 1e-6, True),
        )
    solid_ok("tray")
    s["tray"] = vol()
    h.shot("1-tray")


def closure_start():
    h.fit()
    Gui.Selection.clearSelection()
    smm.menu("MODIFY", "Corner Closure")


def closure_dominant():
    h.check("Corner Closure dialog open", corner_panel() is not None)
    h.fit()
    h.check("clicked the front wall's end edge", h.click_edge(V(LX - O, 0, 10)))


def closure_submissive():
    p = corner_panel()
    h.check("dominant edge picked", p is not None and len(p.picks["dominant"]) == 1, p and p.picks)
    h.check("clicked the right wall's end edge", h.click_edge(V(LX, O, 10)))


def closure_round():
    p = corner_panel()
    smm.settle(p)
    h.check(
        "submissive edge picked", p is not None and len(p.picks["submissive"]) == 1, p and p.picks
    )
    if p is not None:
        h.check("Round chosen", smm.choose(p, "relief", "Round"))


def closure_preview():
    p = corner_panel()
    smm.settle(p, 15000)
    h.check("no message", smm.message(p) == "", smm.message(p))
    v = vol()
    h.check(
        "the Round relief cut at the corner (less material)", v < s["tray"] - 0.5, (v, s["tray"])
    )
    h.shot("2-closure")
    smm.ok()


def closure_done():
    h.check("dialog closed", corner_panel() is None)
    titles = sm.timeline_titles()
    h.check("Corner Closure 1 in the timeline", "Corner Closure 1" in titles, titles)
    solid_ok("corner closure")


def create_flat():
    h.fit()
    Gui.Selection.clearSelection()
    h.ribbon("Create Flat Pattern")


def click_floor():
    h.fit()
    h.click(V(40, 25, 1))


def flat_said():
    fs.settle()
    text = fs.message()
    h.check(
        "the dialog says %.2f x %.2f, 4 bends" % (FLAT_X, FLAT_Y),
        "%.2f x %.2f" % (FLAT_X, FLAT_Y) in text and "4 bend" in text,
        text,
    )


def flat_ok():
    fs.ok()


def flat_made():
    fs.settle()
    fp = fs.flat()
    bb = fs.flat_box(fp)
    h.check(
        "flat %.4f x %.4f (bend allowance maths)" % (FLAT_X, FLAT_Y),
        bb is not None and fs.close(bb.XLength, FLAT_X) and fs.close(bb.YLength, FLAT_Y),
        bb,
    )
    h.check("4 bends", fp is not None and fp.BendCount == 4, fp and fp.BendCount)
    h.check("flat valid", fp is not None and "Invalid" not in fp.State, fp and fp.State)
    # a cross-shaped blank: every corner square under both bends is cut away
    solid = fp.Shape.Solids[0]
    corner = V(bb.XMin + 0.5, bb.YMin + 0.5, (bb.ZMin + bb.ZMax) / 2)
    h.check("the blank's corners are open", not solid.isInside(corner, 1e-6, True))
    h.shot("3-flat")


def export_dxf():
    h.ribbon("Export DXF")


def export_path():
    p = fs.export_panel()
    h.check("Export DXF open", p is not None)
    if p is not None:
        ui.type_into(p.path, s["dxf"])


def export_ok():
    fs.ok()


def dxf_read_back():
    h.check("DXF written", os.path.exists(s["dxf"]), s["dxf"])
    if not os.path.exists(s["dxf"]):
        return
    counts = fs.dxf_counts(s["dxf"])
    outer = counts.get("OUTER_PROFILES", {})
    h.check("the corner reliefs are arcs of the outline", outer.get("ARC", 0) >= 4, counts)
    up = counts.get("BEND_CENTER_LINES_UP", {}).get("LINE", 0)
    h.check("four up bend centre lines", up == 4, counts)
    h.check("eight extent lines", counts.get("BEND_EXTENT_LINES") == {"LINE": 8}, counts)


def finish_flat():
    h.ribbon("Finish Flat Pattern")


def finished():
    fs.settle()
    h.check("back to the folded part", fs.current_tab() != "flat_pattern", fs.current_tab())
    h.check("the tray shown", body().ViewObject.Visibility)


def undo():
    smm.undo()


def undone():
    fs.settle()
    h.check("undo: no flat pattern", fs.flat_patterns() == [], fs.flat_patterns())


def redo():
    smm.redo()


def redone():
    fs.settle()
    bb = fs.flat_box()
    h.check("redo: the flat pattern back", bb is not None and fs.close(bb.XLength, FLAT_X), bb)


h.run(
    "journey_sheetmetal_tray",
    [
        new_design,
        sheet_metal_tab,
        create_sketch,
        pick_xy,
        draw_rect,
        finish_sketch,
        flange_base,
        click_profile,
        base_ok,
        flange_edges,
        edge_clicker("right", V(LX, 25, 1)),
        edge_clicker("front", V(40, 0, 1)),
        edge_clicker("back", V(40, LY, 1)),
        edge_clicker("left", V(0, 25, 1)),
        height_20,
        tray_ok,
        tray_made,
        closure_start,
        closure_dominant,
        closure_submissive,
        closure_round,
        closure_preview,
        closure_done,
        create_flat,
        click_floor,
        flat_said,
        flat_ok,
        flat_made,
        export_dxf,
        export_path,
        export_ok,
        dxf_read_back,
        finish_flat,
        finished,
        undo,
        undone,
        redo,
        redone,
    ],
)
