# SPDX-License-Identifier: LGPL-2.1-or-later
"""The second sheet metal journey: a part modelled as a SOLID, turned into sheet metal, ripped
open and laid flat, only real input. Create Sketch on XY, a 40 x 30 rectangle, E, 20, OK: a
block. F: its four vertical edges rounded 2 (three seen from the home view, the fourth after
turning the view). Shell: the top face, the view turned over, the bottom face, 1 mm inside: a
tube with rounded corners (a shelled box with sharp corners cannot be converted: the
parity doc's documented refusal, the same as Fusion's forum answer). SHEET METAL > MODIFY >
Convert to Sheet Metal, a click on the front wall: 1.000 mm found, 4 bends, Template Rule,
OK: the body is sheet metal. Rip, Type Face, a click on the back-right corner: the corner bend
is cut away. Create Flat Pattern from the front wall: 36 + 26 + 36 + 26 + 3 BA long (T 1,
R 1, K 0.44), 20 wide, 3 bends; Finish Flat Pattern; Ctrl+Z takes the flat pattern away,
Ctrl+Y brings it back."""

import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import flatpattern_steps as fs
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import shell_draft_steps as sd
from SciForgeTests.gui import surface_steps as st

V = App.Vector
s = {}
L, W, HT = 40.0, 30.0, 20.0
TUBE = 2 * (36 + 26) * 20 + 4 * (math.pi / 4) * 3 * 20
CORNER = V(38 + 2 * math.cos(math.radians(30)), 28 + 2 * math.sin(math.radians(30)), 10)


def doc():
    return App.ActiveDocument


def body():
    return doc().getObject(s["body"]) if s.get("body") else None


def vol():
    bd = body()
    return bd.Shape.Volume if bd is not None and bd.Shape.Solids else 0.0


def look_from(direction):
    view = Gui.ActiveDocument.ActiveView
    view.setCameraOrientation(App.Rotation(V(0, 0, -1), V(*direction)).Q)
    view.fitAll()
    QtCore.QCoreApplication.processEvents()


def part_ok(where):
    bad = [o.Label for o in doc().Objects if "Invalid" in o.State or "Error" in o.State]
    h.check("%s: nothing in error" % where, not bad, bad)
    bd = body()
    h.check(
        "%s: one valid solid" % where,
        bd is not None and bd.Shape.isValid() and len(bd.Shape.Solids) == 1,
    )


def extrude_panel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return p if p is not None and not getattr(p, "_closed", False) else None


# -- 1. a block, rounded, shelled into a tube ----------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("JourneyConvert")
    h.fit()


def create_sketch():
    h.ribbon("Create Sketch")


def pick_xy():
    st.open_sketch_clicked(V(12, -8, 0))


def draw_rect():
    sk = h.in_sketch()
    if h.check("a sketch opens on XY", sk is not None):
        h.draw_rectangle(sk, 0, 0, L, W)


def finish_sketch():
    h.ribbon("Finish Sketch")


def extrude():
    h.fit()
    Gui.Selection.clearSelection()
    h.press(QtCore.Qt.Key_E)


def extrude_height():
    p = extrude_panel()
    if h.check("E: Extrude on the rectangle", p is not None and len(p.profiles) == 1):
        ui.type_into(p.distance.widget, "20")
        fs.settle()


def extrude_ok():
    h.task_button("OK")


def block_made():
    bd = h.body()
    s["body"] = bd.Name if bd is not None else ""
    h.check("block 40 x 30 x 20", fs.close(vol(), L * W * HT), vol())
    part_ok("block")


def fillet_start():
    h.fit()
    Gui.Selection.clearSelection()
    h.press(QtCore.Qt.Key_F)


def fillet_seen_edges():
    for x, y in ((0, 0), (L, 0), (L, W)):
        h.click_edge(V(x, y, HT / 2))


def fillet_turn():
    p = b.blend_panel()
    h.check("three corners picked", p is not None and len(p.refs) == 3, p and p.refs)
    look_from((1, -1, -1))


def fillet_back_edge():
    h.click_edge(V(0, W, HT / 2))


def fillet_radius():
    p = b.blend_panel()
    h.check("four corners picked", p is not None and len(p.refs) == 4, p and p.refs)
    if p:
        b.type_into(p.radius.widget, "2")
        fs.settle()


def fillet_ok():
    h.task_button("OK")


def rounded():
    h.fit()
    expect = L * W * HT - 4 * (4 - math.pi) * HT
    h.check("vertical corners rounded 2", fs.close(vol(), expect), (vol(), expect))
    part_ok("fillet")


def shell_start():
    Gui.Selection.clearSelection()
    h.ribbon("Shell")


def shell_top():
    h.fit()
    h.click(V(L / 2, W / 2, HT))


def shell_bottom():
    p = sd.shell_panel()
    h.check("the top picked", p is not None and len(p.names()) == 1, p and p.names())
    h.view().viewBottom()  # the person turns the part over to reach its bottom
    h.view().fitAll()
    h.click(V(L / 2, W / 2, 0))
    h.fit()


def shell_thickness():
    p = sd.shell_panel()
    h.check("top and bottom picked", p is not None and len(p.names()) == 2, p and p.names())
    if p:
        sd.type_into(p.inside.widget, "1")
        fs.settle()


def shell_ok():
    h.task_button("OK")


def tube_made():
    h.check("a 1 mm tube with rounded corners", fs.close(vol(), TUBE), (vol(), TUBE))
    part_ok("shell")
    s["tube"] = vol()
    h.shot("1-tube")


# -- 2. convert ----------
def sheet_tab():
    fs.tab("sheet_metal")


def convert():
    Gui.Selection.clearSelection()
    fs.menu("MODIFY", "Convert to Sheet Metal")


def click_front():
    h.fit()
    h.click(fs.TUBE_FRONT)


def convert_found():
    fs.settle()
    p = fs.sheet_panel()
    h.check(
        "1.000 mm found",
        p is not None and p.thickness.text() == "1.000 mm",
        p and p.thickness.text(),
    )
    h.check("4 bends found", "4 bend" in fs.message(), fs.message())
    h.check("Template Rule", p is not None and p.rule.currentText() == "Template Rule")


def convert_ok():
    fs.ok()


def converted():
    fs.settle()
    from sciforge import sheetmetal

    h.check("dialog closed", not fs.dialog_open())
    h.check("the body is sheet metal", sheetmetal.is_sheet_metal_body(body()))
    rule = sheetmetal.rule_for_body(body())
    h.check("its rule is 1 mm thick", fs.close(rule["thickness"], 1.0), rule)
    titles = fs.timeline_titles()
    h.check(
        "Convert to Sheet Metal in the timeline",
        any(t.startswith("Convert to Sheet Metal") for t in titles),
        titles,
    )
    h.check("shape unchanged", fs.close(vol(), s["tube"]), vol())


# -- 3. rip ----------
def rip():
    Gui.Selection.clearSelection()
    h.ribbon("Rip")


def rip_face():
    p = fs.sheet_panel()
    h.check("Rip dialog open", p is not None and fs.dialog_open())
    if p is not None:
        fs.choose(p.kind, "Face")


def rip_click():
    h.fit()
    h.click(CORNER)


def rip_preview():
    fs.settle()
    p = fs.sheet_panel()
    h.check("the corner face picked", p is not None and len(p.picks["face"]) == 1, p and p.picks)
    corner = (math.pi / 4) * 3 * 20
    h.check("the corner bend cut away", fs.close(vol(), s["tube"] - corner), vol())


def rip_ok():
    fs.ok()


def ripped():
    fs.settle()
    h.check("Rip dialog closed", not fs.dialog_open())
    titles = fs.timeline_titles()
    h.check("Rip 1 in the timeline", "Rip 1" in titles, titles)
    part_ok("rip")
    s["ripped"] = vol()


# -- 4. flat pattern ----------
def create_flat():
    Gui.Selection.clearSelection()
    h.ribbon("Create Flat Pattern")


def flat_click():
    h.fit()
    h.click(fs.TUBE_FRONT)


def flat_size():
    fs.settle()
    text = fs.message()
    h.check("the dialog says 130.79 x 20.00", "130.79 x 20.00" in text, text)


def flat_ok():
    fs.ok()


def flattened():
    fs.settle()
    bb = fs.flat_box()
    h.check(
        "36 + 26 + 36 + 26 + 3 BA = 130.78584 long",
        bb is not None and fs.close(bb.XLength, fs.TUBE_FLAT),
        bb,
    )
    h.check("20 wide", bb is not None and fs.close(bb.YLength, 20), bb)
    h.check("3 bends", fs.flat() is not None and fs.flat().BendCount == 3)
    h.check("FLAT PATTERN tab", fs.current_tab() == "flat_pattern", fs.current_tab())
    h.shot("2-flat")


def finish():
    h.ribbon("Finish Flat Pattern")


def finished():
    fs.settle()
    h.check("back to the folded part", fs.current_tab() != "flat_pattern")
    h.check("the folded body shown", body().ViewObject.Visibility)
    h.check("the ripped part as it was", fs.close(vol(), s["ripped"]), vol())


def undo():
    fs.undo()


def undone():
    fs.settle()
    h.check("undo: no flat pattern", fs.flat_patterns() == [], fs.flat_patterns())


def redo():
    fs.redo()


def redone():
    fs.settle()
    bb = fs.flat_box()
    h.check(
        "redo: the flat pattern back", bb is not None and fs.close(bb.XLength, fs.TUBE_FLAT), bb
    )


h.run(
    "journey_sheetmetal_convert",
    [
        new_design,
        create_sketch,
        pick_xy,
        draw_rect,
        finish_sketch,
        extrude,
        extrude_height,
        extrude_ok,
        block_made,
        fillet_start,
        fillet_seen_edges,
        fillet_turn,
        fillet_back_edge,
        fillet_radius,
        fillet_ok,
        rounded,
        shell_start,
        shell_top,
        shell_bottom,
        shell_thickness,
        shell_ok,
        tube_made,
        sheet_tab,
        convert,
        click_front,
        convert_found,
        convert_ok,
        converted,
        rip,
        rip_face,
        rip_click,
        rip_preview,
        rip_ok,
        ripped,
        create_flat,
        flat_click,
        flat_size,
        flat_ok,
        flattened,
        finish,
        finished,
        undo,
        undone,
        redo,
        redone,
    ],
)
