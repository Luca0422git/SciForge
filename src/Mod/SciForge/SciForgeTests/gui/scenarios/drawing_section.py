# SPDX-License-Identifier: LGPL-2.1-or-later
"""Section View through the hole (CREATE > Section View), with real clicks.

The filleted block with a 12 mm hole (drawing_fixtures.block), ISO A3 (first angle),
base view Front at 1:1 at (120, 200): the hole shows as two hidden lines at x = +-6.

A  Section View, a click on empty paper: the dialog says to click a view.
B  Click the base view, then the cut line's ends above and below it through the hole's
   middle (a slightly slanted second click is straightened); move right and click: the
   section view A-A, lined up with the base view, seen from the left (first angle: the
   arrows point away from the view), 40 x 20 mm, hatched, the hole cut in two.
C  The label typed B: the view is Section B-B. OK.
D  Undo removes the section view, Redo brings it back.
E  Section View, view clicked, first point clicked, Esc: nothing new.
F  Double-click the section view: its dialog; hatching off; OK.
"""

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import drawing_fixtures as fx
from SciForgeTests.gui import drawing_input as d
from SciForgeTests.gui import harness as h

BASE = (120.0, 200.0)
state = {}


def new_design():
    s.new_design("Block")()
    fx.block(App.ActiveDocument)
    h.fit()


def sections():
    from sciforge import drawing

    page = d.page()
    return [v for v in drawing.all_views(page) if v.TypeId == drawing.SECTION] if page else []


def base_pos():
    from sciforge import drawing

    return drawing.view_position(d.bases()[0])


# -- A ------------------------------------------------------------------------------------------
def a_command():
    h.ribbon("Section View")


def a_paper():
    p = d.panel_of("SectionPanel")
    if h.check("Section View dialog", p is not None, d.panel()):
        d.click_at(330, 60)


def a_message():
    p = d.panel_of("SectionPanel")
    h.check(
        "asks for a view",
        p is not None and "view" in p.message.text().lower(),
        p and p.message.text(),
    )


# -- B ------------------------------------------------------------------------------------------
def b_view():
    x, y = base_pos()
    d.click_at(x + 20, y + 3)  # inside the base view


def b_start():
    x, y = base_pos()
    d.click_at(x, y + 16)


def b_end():
    x, y = base_pos()
    d.click_at(x + 0.4, y - 16)  # a little off upright: straightened


def b_place():
    x, y = base_pos()
    d.move_to(x + 60, y + 15)
    d.move_to(x + 95, y + 12)


b_place.wait_ms = 1500


def b_preview():
    found = sections()
    if not h.check("a section view follows the mouse", len(found) == 1, found):
        return
    x, y = base_pos()
    d.click_at(x + 95, y + 12)


b_preview.wait_ms = 800


def b_placed():
    from sciforge import drawing

    found = sections()
    if not h.check("one section view", len(found) == 1, found):
        return
    sec = found[0]
    bx, by = base_pos()
    sx, sy = drawing.view_position(sec)
    h.check("label A", sec.SectionSymbol == "A", sec.SectionSymbol)
    h.check("lined up with the base view", abs(sy - by) < 1e-4, (sy, by))
    h.check("to the right", sx > bx + 40, (sx, bx))
    d_ = sec.Direction
    h.check("seen from the left (first angle)", abs(d_.x + 1.0) < 1e-6, d_)
    h.check("normal = view direction", (sec.SectionNormal - d_).Length < 1e-6)
    h.check(
        "cut through the hole's middle (x = 30)",
        abs(sec.SectionOrigin.x - 30.0) < 1e-6,
        sec.SectionOrigin,
    )
    h.check("hatched", sec.CutSurfaceDisplay == "PatHatch", sec.CutSurfaceDisplay)
    h.check("the section has geometry", d.visible_edge_count(sec) > 0)
    half_w, half_h = drawing.view_extent(sec)
    h.check("40 x 20 mm", abs(half_w - 20.0) < 0.05 and abs(half_h - 10.0) < 0.05, (half_w, half_h))
    lines_at_hole = [
        e
        for e in sec.getVisibleEdges(True)
        if abs(e.BoundBox.XMin - e.BoundBox.XMax) < 1e-6 and abs(abs(e.BoundBox.XMin) - 6.0) < 1e-4
    ]
    h.check("the hole cuts it in two (lines at +-6)", len(lines_at_hole) >= 2, len(lines_at_hole))
    p = d.panel_of("SectionPanel")
    if h.check("dialog still open", p is not None):
        d.type_into(p.label, "B")


b_placed.wait_ms = 1500


def c_label():
    sec = sections()[0]
    h.check(
        "label B",
        sec.SectionSymbol == "B" and sec.Label == "SECTION B-B",
        (sec.SectionSymbol, sec.Label),
    )
    d.ok()


c_label.wait_ms = 1200


def c_done():
    h.check("dialog closed", d.panel() is None)
    h.shot("c-section")


# -- D ------------------------------------------------------------------------------------------
def d_undo():
    d.undo()


def d_undone():
    h.check("undo: no section", not sections(), sections())


def d_redo():
    d.redo()


d_redo.wait_ms = 1500


def d_redone():
    h.check("redo: the section is back", len(sections()) == 1)


# -- E ------------------------------------------------------------------------------------------
def e_command():
    h.ribbon("Section View")


def e_clicks():
    x, y = base_pos()
    d.click_at(x + 20, y + 3)
    d.click_at(x - 20, y + 16)


def e_escape():
    d.key(QtCore.Qt.Key_Escape)


def e_nothing():
    h.check("Esc: still one section", len(sections()) == 1, sections())
    h.check("dialog closed", d.panel() is None)
    h.check("no preview left on the sheet", d.previews_left() == 0, d.previews_left())


# -- F ------------------------------------------------------------------------------------------
def f_double():
    from sciforge import drawing

    sec = sections()[0]
    x, y = drawing.view_position(sec)
    half_w, half_h = drawing.view_extent(sec)
    d.double_click_at(x + half_w - 2.0, y)


f_double.wait_ms = 1200


def f_dialog():
    p = d.panel_of("SectionPanel")
    if not h.check("the section's dialog", p is not None, d.panel()):
        return
    h.check("editing: its label", p.label.text() == "B", p.label.text())
    s.toggle(p.hatch)


f_dialog.wait_ms = 1200


def f_ok():
    h.check("no hatch", sections()[0].CutSurfaceDisplay == "Hide")
    d.ok()


def f_done():
    h.check("dialog closed", d.panel() is None)
    h.check("still no hatch", sections()[0].CutSurfaceDisplay == "Hide")


h.run(
    "drawing_section",
    [new_design]
    + d.drawing_steps("sheet", base_at=BASE, scale="1:1")
    + [
        a_command,
        a_paper,
        a_message,
        b_view,
        b_start,
        b_end,
        b_place,
        b_preview,
        b_placed,
        c_label,
        c_done,
        d_undo,
        d_undone,
        d_redo,
        d_redone,
        e_command,
        e_clicks,
        e_escape,
        e_nothing,
        f_double,
        f_dialog,
        f_ok,
        f_done,
    ],
)
