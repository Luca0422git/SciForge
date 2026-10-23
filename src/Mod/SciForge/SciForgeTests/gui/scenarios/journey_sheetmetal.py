# SPDX-License-Identifier: LGPL-2.1-or-later
"""A whole sheet metal part built the way a Fusion user builds it, across every SHEET METAL
tool of wave 6 together (sm-forming, sm-more, sm-flat), only real input: ribbon, menus,
clicks in the 3D view and in the dialogs, typed values, keys.

A new design; SHEET METAL tab; Sheet Metal Rules: Aluminum (mm) (1.5 mm, R = Thickness,
K 0.44, gap = Thickness) copied from the library into the design and made active. Create
Sketch on XY, a 60 x 40 rectangle, Finish Sketch. Flange, a click inside the rectangle: a
1.5 mm base plate following Aluminum (mm). Flange again on the right (x = 60) and front
(y = 0) edges together, Height 15: both walls, mitred at their corner (volume by hand). Hem
(Open) on the back edge (volume from the hem's cross-section, 57 mm of edge). Corner
Closure on the mitred corner (front wall's end edge, then the right wall's), gap 0.2:
the walls reach further into the corner. Create Sketch on the right wall's outside, a
circle r 3, Finish Sketch, E, -10: a hole cut through the wall. Create Flat Pattern from
the plate's top: its size is the bend allowance maths (60 - (R + T) + BA + (H - R) by
13.5 + BA + 37 + the hem's flat length); FLAT PATTERN > Export DXF read back (outline,
the hole as a circle, three up bend centre lines, six extent lines); Finish Flat Pattern.
Then the rule's Thickness edited to 2: the folded part (2 mm, top at 17) and the flat
pattern (73.52 long) follow; Ctrl+Z / Ctrl+Y. Save (Ctrl+S, version described), close,
reopen: the flat pattern and the timeline are intact."""

import math
import os

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import flatpattern_steps as fs
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sheetmetal_steps as sm
from SciForgeTests.gui import smmore_steps as smm
from SciForgeTests.gui import surface_steps as st
from SciForgeTests.gui import versions_input as vi

V = App.Vector
s = {}
LX, LY, H = 60.0, 40.0, 15.0
K = 0.44
PLATE = V(20, 20, 1.5)  # on the plate's top (seen in the home view)


# -- the maths (Aluminum (mm): T = R = gap = 1.5, K 0.44) ----------
def ring(t, r):
    return math.pi / 4 * ((r + t) ** 2 - r**2)


def ba90(t, r):
    return math.pi / 2 * (r + K * t)


def mitred_volume(t=1.5, r=1.5, gap=1.5, height=H):
    """Plate cut back by R + T along both flanged edges (the corner once), two flanges of
    the whole edge length, each cut on the corner's bisector gap / 2 back (the golden model
    sheetmetal_edge_flange_miter's sum, for these sizes)."""
    back = r + t
    plate = (LX * LY - back * LY - back * LX + back * back) * t
    sec = ring(t, r) + t * (height - r)
    r1, r2 = r, r + t
    centroid = 4 * (r2**3 - r1**3) / (3 * math.pi * (r2**2 - r1**2))
    off = gap / math.sqrt(2)
    cut = (t / 2 + off) * t * (height - r) + ((r + t) - centroid + off) * ring(t, r)
    return plate + (LX + LY) * sec - 2 * cut


def hem_added(t=1.5, r=1.5):
    """What the Open hem adds per mm of edge (sheetmetal_bend_core's cross-section): the
    sheet cut back by x0 (x0 T taken away), the strip of sheet added."""
    from sciforge import sheetmetal_bend_core as core

    opts = core.hem_defaults(t)
    opts["type"] = "open"
    pieces, x0, _inner = core.hem_profile(opts, t, r)
    return x0 * t + core.strip_area(pieces, t)


def hem_flat(t, length, gap):
    """How far the flat runs past the hemmed edge: cut back gap / 2 + T, a 180 degree bend
    BA = pi (gap / 2 + K T), the straight run Length - (gap / 2 + T) (golden sm_flat_hem_open)."""
    ri = gap / 2
    return -(ri + t) + math.pi * (ri + K * t) + (length - (ri + t))


def flat_size(t, height=H):
    """The flat's X and Y lengths for thickness t (R = t) and the flanges' height: the right
    flange laid out along x, the front flange and the hem along y."""
    r = t
    hem = hem_step()
    length = float(hem.Length) if hem is not None else 4 * 1.5
    gap = float(hem.Gap) if hem is not None else 0.5 * 1.5
    x = (LX - (r + t)) + ba90(t, r) + (height - r)
    y = (height - r) + ba90(t, r) + (LY - (r + t)) + hem_flat(t, length, gap)
    return x, y


# -- helpers ----------
def doc():
    return App.ActiveDocument


def body():
    return doc().getObject(s["body"]) if s.get("body") and doc() else None


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
        b and len(b.Shape.Solids),
    )


def steps_of(kind):
    from sciforge import bodies

    return [o for o in doc().Objects if bodies.kind(o) == kind]


def hem_step():
    found = [o for o in doc().Objects if hasattr(o, "HemType")]
    return found[0] if found else None


def inside(point):
    b = body()
    return b is not None and b.Shape.isInside(point, 1e-6, True)


def hem_panel():
    from sciforge import sheetmetal_hem_ui

    return smm.panel(sheetmetal_hem_ui.HemPanel)


def corner_panel():
    from sciforge import sheetmetal_corner_ui

    return smm.panel(sheetmetal_corner_ui.CornerPanel)


def extrude_panel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return p if p is not None and not getattr(p, "_closed", False) else None


def out(name):
    folder = os.path.join(h.OUT_DIR, "journey_sheetmetal")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name)
    if os.path.exists(path):
        os.remove(path)
    return path


def check_flat(where, t, height=H):
    fp = fs.flat()
    bb = fs.flat_box(fp)
    x, y = flat_size(t, height)
    h.check(
        "%s: flat %.4f x %.4f (bend allowance maths)" % (where, x, y),
        bb is not None and fs.close(bb.XLength, x) and fs.close(bb.YLength, y),
        (bb, x, y),
    )
    h.check("%s: flat valid" % where, fp is not None and "Invalid" not in fp.State, fp and fp.State)


# -- 1. rules ----------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("JourneySheet")
    h.fit()
    s["dxf"] = out("journey_flat.dxf")
    s["path"] = out("journey_sheet.FCStd")


def sheet_metal_tab():
    sm.tab()


def open_rules():
    h.check("SHEET METAL tab", fs.current_tab() == "sheet_metal", fs.current_tab())
    h.ribbon("Sheet Metal Rules")


def copy_aluminum():
    h.check("Sheet Metal Rules open", sm.rules_dialog() is not None)
    sm.pick_rule("library", "Aluminum (mm)")
    sm.click_rules_button("library_copy")


def set_active():
    d = sm.rules_dialog()
    names = [d.design.item(i).data(256) for i in range(d.design.count())] if d else []
    h.check("Aluminum (mm) copied into the design", "Aluminum (mm)" in names, names)
    sm.pick_rule("design", "Aluminum (mm)")
    sm.click_rules_button("design_set")


def close_rules():
    from sciforge import sheetmetal

    h.check(
        "Aluminum (mm) is the active rule",
        sheetmetal.active_rule_name(doc()) == "Aluminum (mm)",
        sheetmetal.active_rule_name(doc()),
    )
    sm.click_rules_button("close")


def rules_closed():
    h.check("Sheet Metal Rules closed", sm.rules_dialog() is None)
    h.check("no pop-up", not h.popups(), h.popups())
    node = sm.browser_node("settings:sheet_metal")
    h.check(
        "Document Settings shows the active rule",
        node is not None and "Aluminum (mm)" in node["label"],
        node and node["label"],
    )


# -- 2. base plate ----------
def create_sketch():
    h.ribbon("Create Sketch")


def pick_xy():
    st.open_sketch_clicked(V(12, -8, 0))


def draw_rect():
    sk = h.in_sketch()
    if h.check("a sketch opens on XY", sk is not None):
        h.draw_rectangle(sk, 0, 0, LX, LY)
        s["sketch"] = sk.Name


def finish_sketch():
    h.ribbon("Finish Sketch")


def flange_base():
    h.check("left the sketch", h.in_sketch() is None)
    h.fit()
    h.click_empty()
    h.ribbon("Flange")


def click_profile():
    h.fit()
    h.click(V(30, 20, 0))


def base_plate():
    sm.settle()
    p = sm.panel()
    b = sm.target_body()
    h.check("a base flange", p is not None and p.kind == "base", p and p.kind)
    from sciforge import sheetmetal

    h.check(
        "the Rule box starts at the active rule",
        p is not None and sm.widget("rule").currentText().startswith("Aluminum (mm)"),
        p and sm.widget("rule").currentText(),
    )
    h.check("a 1.5 mm plate (60 x 40)", b is not None and sm.near(sm.volume(b), 3600.0))
    h.check("a sheet metal body", b is not None and sheetmetal.is_sheet_metal_body(b))
    if b is not None:
        s["body"] = b.Name
    sm.ok()


def base_done():
    from sciforge import sheetmetal

    h.check("dialog closed", sm.panel() is None)
    b = body()
    h.check(
        "the body follows Aluminum (mm)",
        b is not None and sheetmetal.body_rule_name(b) == "Aluminum (mm)",
        b and sheetmetal.body_rule_name(b),
    )
    titles = sm.timeline_titles()
    h.check("Flange 1 in the timeline", "Flange 1" in titles, titles)
    h.check("the sketch hidden", not doc().getObject(s["sketch"]).ViewObject.Visibility)
    h.check("bbox 60 x 40 x 1.5", b is not None and _box_is(b.Shape.BoundBox, 60, 40, 1.5))
    solid_ok("base plate")
    h.shot("1-plate")


def _box_is(bb, x, y, z, tol=1e-6):
    return (
        abs(bb.XMin) < tol
        and abs(bb.YMin) < tol
        and abs(bb.ZMin) < tol
        and abs(bb.XMax - x) < tol
        and abs(bb.YMax - y) < tol
        and abs(bb.ZMax - z) < tol
    )


# -- 3. two edge flanges, mitred ----------
def flange_edges():
    h.fit()
    Gui.Selection.clearSelection()
    h.ribbon("Flange")


def click_right_edge():
    h.fit()
    h.check("clicked the right edge", h.click_edge(V(LX, 20, 1.5)))


def click_front_edge():
    sm.settle()
    h.check("clicked the front edge", h.click_edge(V(30, 0, 1.5)))


def height_15():
    sm.settle()
    p = sm.panel()
    h.check("an edge flange on two edges", p is not None and p.kind == "edge" and len(p.refs) == 2)
    sm.type_field("height", "15")


def mitred():
    sm.settle()
    v = vol()
    expect = mitred_volume()
    h.check(
        "two walls mitred at the corner (volume by hand)", sm.near(v, expect, 1e-6), (v, expect)
    )
    b = body()
    h.check("walls up to T + H = 16.5", b is not None and _box_is(b.Shape.BoundBox, 60, 40, 16.5))
    h.check("the mitre gap is open", not inside(V(59.6, 0.4, 10)))
    h.check("no message", not sm.message(), sm.message())
    h.shot("2-mitred")
    sm.ok()


def flanges_done():
    h.check("dialog closed", sm.panel() is None)
    titles = sm.timeline_titles()
    h.check("Flange 2 in the timeline", "Flange 2" in titles, titles)
    s["mitred"] = vol()
    solid_ok("flanges")


# -- 4. hem ----------
def hem_start():
    h.fit()
    Gui.Selection.clearSelection()
    h.ribbon("Hem")


def hem_click():
    h.fit()
    h.check("clicked the back edge", h.click_edge(V(30, LY, 1.5)))


def hem_preview():
    p = hem_panel()
    smm.settle(p)
    h.check("Hem: the edge picked", p is not None and len(p.picks["edges"]) == 1, p and p.picks)
    h.check("Open by default", p is not None and p.value("type") == "open")
    added = vol() - s["mitred"]
    expect = (LX - 3.0) * hem_added()
    h.check(
        "the hem on the 57 mm edge (cross-section)", sm.near(added, expect, 1e-4), (added, expect)
    )
    h.check("no message", smm.message(p) == "", smm.message(p))
    smm.ok()


def hem_done():
    h.check("Hem dialog closed", hem_panel() is None)
    titles = sm.timeline_titles()
    h.check("Hem 1 in the timeline", "Hem 1" in titles, titles)
    s["hemmed"] = vol()
    solid_ok("hem")
    h.shot("3-hem")


# -- 5. corner closure ----------
FRONT_END = V(LX - 0.75 * math.sqrt(2), 0, 10)  # the front wall's mitred end, outside
RIGHT_END = V(LX, 0.75 * math.sqrt(2), 10)  # the right wall's mitred end, outside


def closure_start():
    h.fit()
    Gui.Selection.clearSelection()
    smm.menu("MODIFY", "Corner Closure")


def closure_dominant():
    p = corner_panel()
    h.check("Corner Closure dialog open", p is not None)
    h.fit()
    h.check("clicked the front wall's end edge", h.click_edge(FRONT_END))


def closure_submissive():
    p = corner_panel()
    h.check("dominant edge picked", p is not None and len(p.picks["dominant"]) == 1, p and p.picks)
    h.check("clicked the right wall's end edge", h.click_edge(RIGHT_END))


def closure_gap():
    p = corner_panel()
    smm.settle(p)
    h.check(
        "submissive edge picked", p is not None and len(p.picks["submissive"]) == 1, p and p.picks
    )
    if p is not None:
        smm.toggle(p, "use_rule_gap")
        smm.type_into(p, "gap_value", "0.2")


def closure_preview():
    p = corner_panel()
    smm.settle(p, 15000)
    h.check("no message", smm.message(p) == "", smm.message(p))
    h.check("the walls reach into the corner", vol() > s["hemmed"] + 1, (vol(), s["hemmed"]))
    h.check("front wall closer to the corner", inside(V(58.6, 0.75, 10)))
    h.check("right wall closer to the corner", inside(V(59.25, 1.4, 10)))
    h.check("a 0.2 gap is left on the bisector", not inside(V(59.6, 0.4, 10)))
    h.shot("4-closure")
    smm.ok()


def closure_done():
    h.check("Corner Closure dialog closed", corner_panel() is None)
    titles = sm.timeline_titles()
    h.check("Corner Closure 1 in the timeline", "Corner Closure 1" in titles, titles)
    s["closed"] = vol()
    solid_ok("corner closure")


# -- 6. a hole through the right wall ----------
def hole_sketch():
    h.fit()
    Gui.Selection.clearSelection()
    h.ribbon("Create Sketch")


def pick_wall():
    h.click(V(LX, 20, 10))


def draw_circle():
    sk = h.in_sketch()
    if not h.check("a sketch on the right wall", sk is not None):
        return
    normal = sk.getGlobalPlacement().Rotation.multVec(V(0, 0, 1))
    h.check("it faces outwards (+x)", normal.x > 0.99, normal)
    cx, cy = h.to_sketch(sk, V(LX, 20, 10))
    h.draw_circle(sk, cx, cy, 3)
    s["hole_sketch"] = sk.Name


def finish_hole_sketch():
    h.ribbon("Finish Sketch")


def extrude_hole():
    h.fit()
    Gui.Selection.clearSelection()
    h.press(QtCore.Qt.Key_E)


def hole_depth():
    p = extrude_panel()
    if not h.check(
        "E opens Extrude on the circle", p is not None and len(p.profiles) == 1, p and p.profiles
    ):
        return
    ui.type_into(p.distance.widget, "-10")
    sm.settle()


def hole_ok():
    p = extrude_panel()
    h.check(
        "into the part: a Cut",
        p is not None and p.operation.currentText() == "Cut",
        p and p.operation.currentText(),
    )
    h.check("no message", p is not None and p.message.text() == "", p and p.message.text())
    h.task_button("OK")


def hole_made():
    h.check("Extrude closed", extrude_panel() is None)
    v = vol()
    expect = s["closed"] - math.pi * 9 * 1.5
    h.check("a 6 mm hole through the 1.5 mm wall", sm.near(v, expect, 1e-6), (v, expect))
    h.check("the hole goes through", not inside(V(LX - 0.75, 20, 10)))
    solid_ok("hole")
    s["titles"] = sm.timeline_titles()
    h.shot("5-hole")


# -- 7. flat pattern ----------
def create_flat():
    h.fit()
    Gui.Selection.clearSelection()
    sm.tab()
    h.ribbon("Create Flat Pattern")


def click_plate():
    h.fit()
    h.click(PLATE)


def flat_said():
    fs.settle()
    x, y = flat_size(1.5)
    text = fs.message()
    h.check("the dialog says %.2f x %.2f" % (x, y), "%.2f x %.2f" % (x, y) in text, text)
    h.check("3 bends", "3 bend" in text, text)


def flat_ok():
    fs.ok()


def flat_made():
    fs.settle()
    h.check("FLAT PATTERN tab", fs.current_tab() == "flat_pattern", fs.current_tab())
    check_flat("made", 1.5)
    from sciforge import flatpattern

    bends = flatpattern.bends(fs.flat())
    angles = sorted(round(b["angle"]) for b in bends)
    h.check("bends 90, 90 and the hem's 180", angles == [90, 90, 180], bends)
    fp = fs.flat()
    h.check("the flat is shown", fp.ViewObject.Visibility)
    h.check("the folded body is hidden", not body().ViewObject.Visibility)
    h.shot("6-flat")


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
    h.check("the outline on OUTER_PROFILES", outer.get("LINE", 0) >= 8, counts)
    h.check(
        "the hole on INTERIOR_PROFILES", counts.get("INTERIOR_PROFILES") == {"CIRCLE": 1}, counts
    )
    up = counts.get("BEND_CENTER_LINES_UP", {}).get("LINE", 0)
    down = counts.get("BEND_CENTER_LINES_DOWN", {}).get("LINE", 0)
    h.check("three bend centre lines", up + down == 3, counts)
    h.check("six bend extent lines", counts.get("BEND_EXTENT_LINES") == {"LINE": 6}, counts)


def finish_flat():
    h.ribbon("Finish Flat Pattern")


def flat_finished():
    fs.settle()
    h.check("back to the folded part", fs.current_tab() != "flat_pattern", fs.current_tab())
    h.check("the folded body shown", body().ViewObject.Visibility)
    h.check("the flat hidden", not fs.flat().ViewObject.Visibility)
    titles = sm.timeline_titles()
    h.check("the timeline as before", titles == s["titles"], (titles, s["titles"]))


# -- 8. the rule's thickness ----------
def rules_again():
    sm.tab()
    h.ribbon("Sheet Metal Rules")


def edit_aluminum():
    sm.pick_rule("design", "Aluminum (mm)")
    sm.click_rules_button("design_edit")


def thickness_2():
    sm.rule_field("thickness", "2")
    sm.click_rules_button("save")


def close_rules_2():
    d = sm.rules_dialog()
    h.check("saved", d is not None and d.pages.currentIndex() == 0, sm.rules_message())
    sm.click_rules_button("close")


def thick_part():
    fs.settle()
    from sciforge import sheetmetal

    b = body()
    h.check("the rule is 2 mm", fs.close(sheetmetal.rule_for_body(b)["thickness"], 2.0))
    h.check("the folded part 2 mm: top at T + H = 17", _box_is(b.Shape.BoundBox, 60, 40, 17))
    h.check("bigger than in 1.5 mm", vol() > s["closed"] * 1.2, vol())
    h.check("the hole still goes through", not inside(V(LX - 1.0, 20, 10)))
    solid_ok("2 mm")
    check_flat("2 mm", 2.0)
    s["thick"] = vol()
    h.shot("7-thick")


def undo_thickness():
    smm.undo()


def thickness_undone():
    fs.settle()
    b = body()
    h.check("undo: 1.5 mm again", _box_is(b.Shape.BoundBox, 60, 40, 16.5), b.Shape.BoundBox)
    h.check("undo: the volume as before", sm.near(vol(), s["closed"] - math.pi * 9 * 1.5, 1e-6))
    check_flat("undo", 1.5)


def redo_thickness():
    smm.redo()


def thickness_redone():
    fs.settle()
    h.check("redo: 2 mm", sm.near(vol(), s["thick"], 1e-6), vol())
    check_flat("redo", 2.0)


# -- 9. save, close, reopen ----------
def save():
    doc().saveAs(s["path"])
    h.check("saved", os.path.isfile(s["path"]), s["path"])


def ctrl_s():
    doc().recompute()
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


def describe():
    h.check("Ctrl+S asks for a version description", vi.version_dialog() is not None)
    vi.accept_save()


def reopen():
    h.check("nothing unsaved", not doc().isTouched())
    s["titles_saved"] = sm.timeline_titles()
    App.closeDocument(doc().Name)
    App.openDocument(s["path"])
    h.fit()


def reopened():
    fs.settle()
    from sciforge import sheetmetal

    b = body()
    h.check("the body is back", b is not None)
    if b is None:
        return
    h.check("still sheet metal, Aluminum (mm)", sheetmetal.body_rule_name(b) == "Aluminum (mm)")
    h.check("still 2 mm", fs.close(sheetmetal.rule_for_body(b)["thickness"], 2.0))
    h.check("the same part", sm.near(vol(), s["thick"], 1e-6), (vol(), s["thick"]))
    titles = sm.timeline_titles()
    h.check("the timeline intact", titles == s["titles_saved"], (titles, s["titles_saved"]))
    h.check("a flat pattern kept", len(fs.flat_patterns()) == 1, fs.flat_patterns())
    check_flat("reopened", 2.0)
    h.check("the flat hidden after reopening", not fs.flat().ViewObject.Visibility)
    solid_ok("reopened")


def open_flat():
    h.check("double-clicked Flat Pattern", fs.double_click_browser("Flat Pattern"))


def flat_opened():
    fs.settle()
    h.check("FLAT PATTERN tab again", fs.current_tab() == "flat_pattern", fs.current_tab())
    h.check("the flat shown", fs.flat().ViewObject.Visibility)
    h.shot("8-reopened")


def finish_again():
    h.ribbon("Finish Flat Pattern")


def done():
    fs.settle()
    h.check("back to the folded part", fs.current_tab() != "flat_pattern")
    h.check("the folded body shown", body().ViewObject.Visibility)


# -- 10. an earlier step edited: everything after it follows ----------
def edit_flanges():
    h.fit()
    Gui.Selection.clearSelection()
    sm.double_click_timeline("Flange 2")


def edit_open():
    sm.settle()
    p = sm.panel()
    h.check(
        "the Flange dialog opens on Flange 2 with its two edges",
        p is not None and p.editing and p.kind == "edge" and len(p.refs) == 2,
        p and (p.kind, p.refs),
    )
    sm.type_field("height", "20")


def edit_ok():
    sm.settle()
    h.check("no message", not sm.message(), sm.message())
    sm.ok()


def edited():
    fs.settle()
    b = body()
    h.check("dialog closed", sm.panel() is None)
    h.check("walls 20 high: top at T + H = 22", _box_is(b.Shape.BoundBox, 60, 40, 22))
    # each wall 5 mm taller, 2 mm thick, as long as it runs (to 0.1 short of the corner's
    # bisector after the Corner Closure: 60 - T / 2 - 0.1 sqrt 2 and 40 - T / 2 - 0.1 sqrt 2)
    grow = 5 * 2 * ((60 - 1 - 0.1 * math.sqrt(2)) + (40 - 1 - 0.1 * math.sqrt(2)))
    added = vol() - s["thick"]
    h.check("the walls 5 mm taller (about 977)", abs(added - grow) < 0.01 * grow, (added, grow))
    h.check("the corner still closed", inside(V(58.6, 0.75, 10)) and inside(V(59.25, 1.4, 10)))
    h.check("the 0.2 gap kept", not inside(V(59.6, 0.4, 10)))
    h.check("the hole still through the wall", not inside(V(LX - 1.0, 20, 10)))
    solid_ok("edited")
    check_flat("edited", 2.0, 20.0)
    titles = sm.timeline_titles()
    h.check("the timeline unchanged", titles == s["titles_saved"], titles)
    h.shot("9-edited")


def undo_edit():
    smm.undo()


def edit_undone():
    fs.settle()
    b = body()
    h.check("undo: 15 high again", _box_is(b.Shape.BoundBox, 60, 40, 17), b.Shape.BoundBox)
    h.check("undo: the part as before", sm.near(vol(), s["thick"], 1e-6), (vol(), s["thick"]))
    check_flat("edit undone", 2.0)


h.run(
    "journey_sheetmetal",
    [
        new_design,
        sheet_metal_tab,
        open_rules,
        copy_aluminum,
        set_active,
        close_rules,
        rules_closed,
        create_sketch,
        pick_xy,
        draw_rect,
        finish_sketch,
        flange_base,
        click_profile,
        base_plate,
        base_done,
        flange_edges,
        click_right_edge,
        click_front_edge,
        height_15,
        mitred,
        flanges_done,
        hem_start,
        hem_click,
        hem_preview,
        hem_done,
        closure_start,
        closure_dominant,
        closure_submissive,
        closure_gap,
        closure_preview,
        closure_done,
        hole_sketch,
        pick_wall,
        draw_circle,
        finish_hole_sketch,
        extrude_hole,
        hole_depth,
        hole_ok,
        hole_made,
        create_flat,
        click_plate,
        flat_said,
        flat_ok,
        flat_made,
        export_dxf,
        export_path,
        export_ok,
        dxf_read_back,
        finish_flat,
        flat_finished,
        rules_again,
        edit_aluminum,
        thickness_2,
        close_rules_2,
        thick_part,
        undo_thickness,
        thickness_undone,
        redo_thickness,
        thickness_redone,
        save,
        ctrl_s,
        describe,
        reopen,
        reopened,
        open_flat,
        flat_opened,
        finish_again,
        done,
        edit_flanges,
        edit_open,
        edit_ok,
        edited,
        undo_edit,
        edit_undone,
    ],
)
