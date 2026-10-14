# SPDX-License-Identifier: LGPL-2.1-or-later
"""A drawing of two components: Contents, the parts list (TABLES > Table) and balloons
(TABLES > Balloon), with real clicks.

drawing_fixtures.assembly: Plate (80 x 50 x 8) and Post (20 x 20 x 30) standing on it.

A  File > New Drawing, Contents Select, Post unticked, OK; the base view placed: the
   drawing shows the plate only (one body, 80 wide).
B  Workspace > Design; File > New Drawing, Full Assembly; base view Front at 1:1 at
   (150, 180) by a click: both components on it.
C  TABLES > Balloon before there is a parts list: it says to make the parts list first.
D  TABLES > Table: the table follows the mouse; a click at (290, 120): the parts list's top
   left corner is there; rows 1 Plate and 2 Post, Qty 1 each; balloons 1 and 2 on the
   view, each pointing at its own component, outside the view. OK: no outline is left.
E  TABLES > Balloon: a click on empty paper says to click a component's edge; a click on
   the Post's top edge, then above it: balloon 2; on the Plate's bottom edge, then below
   it: balloon 1; Enter. Ctrl+Z removes both (one step); Ctrl+Y brings them back.
F  The Post renamed Pillar (by script): the parts list's row 2 says Pillar.
G  Table again: this drawing already has a parts list.
H  The browser's right-click menu of the first drawing (Open Drawing, Rename, Delete);
   Delete: that drawing, its view and its tab are gone, the other drawing (still the
   active tab) and both components stay; Undo (the quick-access button) brings it back with its view.
"""

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import drawing_fixtures as fx
from SciForgeTests.gui import drawing_input as d
from SciForgeTests.gui import harness as h

BASE = (150.0, 180.0)
TABLE_AT = (290.0, 120.0)
state = {}


def new_design():
    s.new_design("Asm")()
    (state["plate"], state["plate_body"]), (state["post"], state["post_body"]) = fx.assembly(
        App.ActiveDocument
    )
    h.fit()


def base():
    return d.bases()[0]


def at(u, v):
    from sciforge import drawing

    return drawing.local_to_page(base(), (u, v))


def balloons():
    from sciforge import drawing

    page = d.page()
    return [o for o in drawing.annotations(page) if o.TypeId == drawing.BALLOON] if page else []


def table():
    from sciforge import drawing

    return drawing.parts_list_of(d.page())


def rows():
    from sciforge import drawing

    t = table()
    return [(r["Item"], r["PartNumber"], r["Qty"]) for r in drawing.table_rows(t)] if t else []


def pointed_at(balloon):
    """The component a balloon's arrow is on."""
    from sciforge import components, drawing

    view = balloon.SourceView
    origin, _spot = drawing.balloon_page_points(balloon)
    body = drawing.component_at(view, drawing.page_to_local(view, origin))
    comp = components.component_of(body) if body is not None else None
    return comp.Label if comp is not None else None


# -- A ------------------------------------------------------------------------------------------
def a_check():
    from sciforge import drawing

    page = d.page()
    sources = [b.Name for b in page.SciForgeSources]
    h.check("the drawing shows one body", sources == [state["plate_body"].Name], sources)
    view = base()
    h.check("the view shows it", [b.Name for b in view.Source] == sources)
    w, _h = drawing.view_extent(view)
    h.check("80 wide", abs(2 * w - 80.0) < 1e-3, 2 * w)


def b_design():
    d.workspace("Design")


b_design.wait_ms = 1200


# -- C ------------------------------------------------------------------------------------------
def c_balloon():
    h.check("both components on the view", len(base().Source) == 2, base().Source)
    h.ribbon("Balloon")


def c_refused():
    tip = d.tooltip_text()
    h.check("make the parts list first", "parts list first" in tip, tip)
    h.check("no Balloon dialog", d.panel() is None, d.panel())


# -- D ------------------------------------------------------------------------------------------
def d_table():
    h.ribbon("Table")


def d_move():
    p = d.panel_of("TablePanel")
    if h.check("the Table dialog", p is not None, d.panel()):
        d.move_to(TABLE_AT[0] + 5, TABLE_AT[1] - 5)


def d_place():
    p = d.panel_of("TablePanel")
    h.check("its outline follows the mouse", p is not None and bool(p.overlay))
    d.click_at(*TABLE_AT)


d_place.wait_ms = 1500


def d_made():
    t = table()
    if not h.check("a parts list", t is not None):
        return
    corner = list(t.SciForgeCorner)
    h.check(
        "its top left corner where clicked",
        abs(corner[0] - TABLE_AT[0]) < 0.5 and abs(corner[1] - TABLE_AT[1]) < 0.5,
        corner,
    )
    h.check("rows 1 Plate, 2 Post", rows() == [(1, "Plate", 1), (2, "Post", 1)], rows())
    found = sorted(balloons(), key=lambda b: b.Text)
    h.check("balloons 1 and 2", [b.Text for b in found] == ["1", "2"], [b.Text for b in found])
    h.check(
        "each on its own component",
        [pointed_at(b) for b in found] == ["Plate", "Post"],
        [pointed_at(b) for b in found],
    )
    from sciforge import drawing

    half_w, half_h = drawing.view_extent(base())
    outside = []
    for b in found:
        u, v = drawing.page_to_local(base(), drawing.balloon_page_points(b)[1])
        outside.append(abs(u) > half_w or abs(v) > half_h)
    h.check("outside the view", all(outside), outside)
    d.ok()


d_made.wait_ms = 1500


def d_done():
    h.check("OK closes it", d.panel() is None)
    h.check("no outline left on the sheet", d.previews_left() == 0, d.previews_left())
    h.shot("d-parts-list")


# -- E ------------------------------------------------------------------------------------------
def e_start():
    state["count"] = len(balloons())
    h.ribbon("Balloon")


def e_paper():
    if h.check("the Balloon dialog", d.panel_of("BalloonPanel") is not None, d.panel()):
        d.click_at(60, 250)


def e_said():
    p = d.panel_of("BalloonPanel")
    h.check(
        "click a component's edge",
        p is not None and "edge of a component" in p.message.text(),
        p and p.message.text(),
    )
    d.click_at(*at(0, 19))  # the Post's top edge


def e_place_post():
    d.move_to(*at(5, 35))
    d.click_at(*at(4, 34))


e_place_post.wait_ms = 1000


def e_plate():
    d.click_at(*at(-30, -19))  # the Plate's bottom edge


def e_place_plate():
    d.move_to(*at(-35, -35))
    d.click_at(*at(-36, -36))


e_place_plate.wait_ms = 1000


def e_enter():
    d.key(QtCore.Qt.Key_Return)


e_enter.wait_ms = 1200


def e_made():
    h.check("Enter ends", d.panel() is None, d.panel())
    h.check("no preview left on the sheet", d.previews_left() == 0, d.previews_left())
    found = balloons()[state["count"] :]
    h.check("two balloons more", len(found) == 2, [b.Text for b in found])
    h.check("2 then 1", [b.Text for b in found] == ["2", "1"], [b.Text for b in found])
    h.check(
        "on the Post, then the Plate",
        [pointed_at(b) for b in found] == ["Post", "Plate"],
        [pointed_at(b) for b in found],
    )
    d.undo()


e_made.wait_ms = 1200


def e_undone():
    h.check("Ctrl+Z: both gone", len(balloons()) == state["count"], len(balloons()))
    d.redo()


e_undone.wait_ms = 1200


def e_redone():
    h.check("Ctrl+Y: both back", len(balloons()) == state["count"] + 2, len(balloons()))


# -- F ------------------------------------------------------------------------------------------
def f_rename():
    state["post"].Label = "Pillar"
    App.ActiveDocument.recompute()


f_rename.wait_ms = 1500


def f_followed():
    h.check("row 2 says Pillar", rows() == [(1, "Plate", 1), (2, "Pillar", 1)], rows())


# -- G ------------------------------------------------------------------------------------------
def g_table():
    h.ribbon("Table")


def g_refused():
    tip = d.tooltip_text()
    h.check("already has a parts list", "already has a parts list" in tip, tip)
    h.check("no Table dialog", d.panel() is None, d.panel())


# -- H ------------------------------------------------------------------------------------------
def drawing_names():
    from sciforge import drawing

    return sorted(p.Label for p in drawing.drawings(App.ActiveDocument))


def part_views():
    from sciforge import drawing

    return [o.Name for o in App.ActiveDocument.Objects if o.TypeId in drawing.VIEW_TYPES]


def h_menu():
    from SciForgeTests.gui import timeline_input as t

    state["views"] = part_views()
    entries = [e for e, _on in t.row_menu_entries("Asm Drawing")]
    h.check(
        "Open Drawing, Rename, Delete",
        all(x in entries for x in ("Open Drawing", "Rename", "Delete")),
        entries,
    )
    t.row_menu("Asm Drawing", "Delete")


h_menu.wait_ms = 1500


def h_gone():
    h.check("the drawing is gone", drawing_names() == ["Asm Drawing 2"], drawing_names())
    from sciforge import drawing_ui

    tabs = [sub.windowTitle().replace("[*]", "") for sub in drawing_ui._area().subWindowList()]
    h.check("its tab closed", "Asm Drawing" not in tabs, tabs)
    h.check("its view too", len(part_views()) == len(state["views"]) - 1, part_views())
    h.check(
        "both components stay",
        abs(state["plate_body"].Shape.Volume - 80 * 50 * 8) < 1e-6
        and abs(state["post_body"].Shape.Volume - 20 * 20 * 30) < 1e-6,
    )
    h.check(
        "the other drawing's tab stays", d.page() is not None and d.page().Label == "Asm Drawing 2"
    )
    from SciForgeTests.gui import timeline_input as t

    t.undo()


h_gone.wait_ms = 2000


def h_back():
    h.check("Undo: the drawing is back", drawing_names() == ["Asm Drawing", "Asm Drawing 2"])
    h.check("with its view", sorted(part_views()) == sorted(state["views"]), part_views())


h.run(
    "drawing_assembly",
    [new_design]
    + d.drawing_steps(
        "plate",
        contents="Select",
        untick=("Post / Body1",),
        base_at=BASE,
        scale="1:1",
        orientation="Top",
    )
    + [a_check, b_design]
    + d.drawing_steps("asm", base_at=BASE, scale="1:1", orientation="Front")
    + [c_balloon, c_refused, d_table, d_move, d_place, d_made, d_done]
    + [e_start, e_paper, e_said, e_place_post, e_plate, e_place_plate, e_enter]
    + [e_made, e_undone, e_redone, f_rename, f_followed, g_table, g_refused]
    + [h_menu, h_gone, h_back],
)
