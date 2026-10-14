# SPDX-License-Identifier: LGPL-2.1-or-later
"""A drawing is saved with its design and comes back whole when the design is opened
again; it still follows the design and its edits still undo, with real clicks.

The filleted block (drawing_fixtures.block), ISO A3, base view Top at 1:1 at (130, 190),
the bottom edge's dimension (50) and a centre mark on the hole by clicks; by script: a
projected view below the base view, a section A-A through the hole, the note "NOTE 1"
and the title block's Description typed "Plate" (the subject here is save and reopen).

A  Ctrl+S on the sheet: the Save dialog; name "Reo" and the folder typed; Save: Reo.FCStd.
B  The design closed and opened again (by script, as insert_reopen does): the browser's
   Drawings folder lists the drawing; a double-click opens it in its own tab with the
   DRAWING tab: the three views (the projected view still under the base view, the
   section still hatched), the dimension 50, the centre mark (two lines), the note, the
   title block with "Plate" kept as typed; the design's timeline has no drawing steps;
   the design is not marked as changed (opening a drawing changes nothing).
C  Dimension on the left edge (30); Ctrl+Z removes it; Ctrl+Y brings it back.
D  Workspace > Design, Fillet 1 radius 8 in the timeline; back on the drawing the bottom
   edge's dimension reads 44 and the left edge's 24: the reopened drawing still follows
   the design.
"""

import os
import shutil

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import drawing_fixtures as fx
from SciForgeTests.gui import drawing_input as d
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import versions_input as vi
from SciForgeTests.gui import widget_input as wi

BASE = (130.0, 190.0)
OUT = os.path.join(d.OUT, "reopen")
state = {}


def new_design():
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT, exist_ok=True)
    s.new_design("Reo")()
    fx.block(App.ActiveDocument)
    h.fit()


def base():
    return d.bases()[0]


def at(u, v):
    from sciforge import drawing

    return drawing.local_to_page(base(), (u, v))


def dims():
    from sciforge import drawing

    page = d.page()
    return [o for o in drawing.annotations(page) if o.TypeId == drawing.DIMENSION] if page else []


def values():
    from sciforge import drawing

    return sorted(round(drawing.dimension_value(x), 6) for x in dims())


def dimension(name, pick, place):
    def start():
        h.ribbon("Dimension")

    def picked():
        d.click_at(*at(*pick))
        d.move_to(*at(place[0] + 2, place[1] + 2))

    def placed():
        d.click_at(*at(*place))

    def end():
        d.key(QtCore.Qt.Key_Escape)

    picked.wait_ms = 1000
    placed.wait_ms = 1000
    steps = [start, picked, placed, end]
    for step in steps:
        step.__name__ = "%s_%s" % (name, step.__name__)
    return steps


def mark_start():
    h.ribbon("Center Mark")


def mark_pick():
    d.click_at(*at(0, 6))


mark_pick.wait_ms = 1000


def mark_end():
    d.key(QtCore.Qt.Key_Return)


def scripted():
    from sciforge import drawing
    from sciforge import drawing_core as core

    page = d.page()
    kind = core.projected_kind(0.0, -1.0, page.ProjectionType)
    drawing.add_projected(base(), kind, BASE[0], BASE[1] - 70.0)
    drawing.add_section(base(), (0, 26), (0, -26), (10, 0), (BASE[0] + 90.0, BASE[1]))
    drawing.add_text(page, ["NOTE 1"], (60.0, 60.0))
    drawing.set_title(page, {"Description": "Plate"})
    page.Document.recompute()


scripted.wait_ms = 3000


def before():
    from sciforge import drawing

    page = d.page()
    state["page"] = page.Label
    state["views"] = sorted(v.Label for v in drawing.all_views(page))
    state["positions"] = {v.Label: drawing.view_position(v) for v in drawing.all_views(page)}
    h.check("three views", len(state["views"]) == 3, state["views"])
    h.check("the dimension 50", values() == [50.0], values())
    h.check("a centre mark", len(drawing.center_marks(base())) == 1)
    h.check("Plate typed", drawing.title(page).get("Description") == "Plate", drawing.title(page))


# -- A ------------------------------------------------------------------------------------------
def a_save():
    d.click_at(380, 250)  # the sheet has the keyboard
    d.key(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


a_save.wait_ms = 1500


def a_dialog():
    if h.check("Ctrl+S on the sheet: the Save dialog", vi.save_dialog() is not None, h.popups()):
        vi.fill_save_dialog(name="Reo", location=OUT)
        vi.click_save()


a_dialog.wait_ms = 3000


def a_saved():
    state["file"] = os.path.join(OUT, "Reo.FCStd")
    h.check("Reo.FCStd written", os.path.isfile(state["file"]), os.listdir(OUT))
    h.check("the design is saved", App.ActiveDocument.FileName == state["file"])


# -- B ------------------------------------------------------------------------------------------
def b_close():
    App.closeDocument(App.ActiveDocument.Name)


b_close.wait_ms = 1500


def b_open():
    App.openDocument(state["file"])


b_open.wait_ms = 4000


def b_browser():
    tree = s.browser()
    h.check("browser: Drawings folder", "Drawings" in tree.labels(), tree.labels())
    item = tree.row(state["page"])
    if h.check("browser row of the drawing", item is not None, tree.labels()):
        wi.double_click(tree.viewport(), tree.label_point(item))


b_browser.wait_ms = 4000


def b_whole():
    from SciForgeTests.gui import timeline_input as t
    from sciforge import drawing

    page = d.page()
    if not h.check("the drawing's tab", page is not None and page.Label == state["page"]):
        return
    h.check("the DRAWING tab", d.current_tab() == "drawing", d.current_tab())
    import FreeCADGui as Gui

    h.check("looking at it changed nothing", not Gui.getDocument(page.Document.Name).Modified)
    views = drawing.all_views(page)
    h.check("the three views", sorted(v.Label for v in views) == state["views"], views)
    h.check("all drawn", all(drawing.has_geometry(v) for v in views))
    for v in views:
        x, y = drawing.view_position(v)
        ex, ey = state["positions"][v.Label]
        h.check("%s where it was" % v.Label, abs(x - ex) < 1e-6 and abs(y - ey) < 1e-6, (x, y))
    sections = [v for v in views if v.TypeId == drawing.SECTION]
    h.check(
        "the section hatched",
        len(sections) == 1 and sections[0].CutSurfaceDisplay == "PatHatch",
        sections,
    )
    h.check("the dimension 50", values() == [50.0], values())
    marks = drawing.center_marks(base())
    h.check("the centre mark", len(marks) == 1 and len(base().CosmeticEdges) == 2, marks)
    notes = [o for o in drawing.annotations(page) if o.TypeId == drawing.ANNOTATION]
    h.check("the note", [list(n.Text) for n in notes] == [["NOTE 1"]], notes)
    title = drawing.title(page)
    h.check("Plate kept", title.get("Description") == "Plate", title)
    h.check("the title", title.get("Title") == "Reo", title)
    h.check("still ISO A3", drawing.standard_of(page) == "ISO" and drawing.sheet_of(page) == "A3")
    h.check("no drawing steps in the timeline", t.titles() == ["Box 1", "Cylinder 1", "Fillet 1"])
    h.shot("b-reopened")


# -- C ------------------------------------------------------------------------------------------
def c_check():
    h.check("the 30 dimension added", values() == [30.0, 50.0], values())
    d.undo()


c_check.wait_ms = 1200


def c_undone():
    h.check("Ctrl+Z: gone", values() == [50.0], values())
    d.redo()


c_undone.wait_ms = 1200


def c_redone():
    h.check("Ctrl+Y: back", values() == [30.0, 50.0], values())


# -- D ------------------------------------------------------------------------------------------
def d_design():
    d.workspace("Design")


d_design.wait_ms = 1200


def d_edit():
    h.fit()
    b.timeline_double_click("Fillet 1")


d_edit.wait_ms = 1500


def d_radius():
    p = b.blend_panel()
    if h.check("editing Fillet 1", p is not None and p.target is not None and not p.created):
        b.type_into(p.radius.widget, "8")


d_radius.wait_ms = 1500


def d_ok():
    h.task_button("OK")


d_ok.wait_ms = 1500


def d_back():
    d.workspace("Drawing", state["page"])


d_back.wait_ms = 2500


def d_followed():
    # (the straight parts of the edges: 60 - 2 x 8 and 40 - 2 x 8)
    h.check("the edges read 44 and 24", values() == [24.0, 44.0], values())


h.run(
    "drawing_reopen",
    [new_design]
    + d.drawing_steps("sheet", base_at=BASE, scale="1:1", orientation="Top", style="Visible Edges")
    + dimension("length", (0, -20), (0, -32))
    + [mark_start, mark_pick, mark_end, scripted, before]
    + [a_save, a_dialog, a_saved]
    + [b_close, b_open, b_browser, b_whole]
    + dimension("height", (-30, 0), (-42, 0))
    + [c_check, c_undone, c_redone]
    + [d_design, d_edit, d_radius, d_ok, d_back, d_followed],
)
