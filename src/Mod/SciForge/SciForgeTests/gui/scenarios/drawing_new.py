# SPDX-License-Identifier: LGPL-2.1-or-later
"""File > New Drawing > From Design, the drawing's own tab and the Base View, with real
clicks (the filleted block with a hole is built by script: drawing_fixtures.block).

A  An empty design: File > New Drawing says there is nothing to draw; no drawing appears.
B  File > New Drawing on the block: the Create Drawing dialog (Full Assembly, ISO, mm, A3,
   SciForge title block, Manual views); OK opens the drawing in its own tab: the ribbon
   shows only DRAWING, the workspace button says DRAWING, the timeline steps aside; the
   title block is filled from the design (name, date, size, units, material, author).
C  The Base View follows the mouse; a click places it; Style Visible Edges (no hidden
   lines); the scale typed 1:1; OK. The title block's scale says 1:1.
D  Undo takes the base view away, Redo brings it back.
E  Base View again, Esc: nothing new.
F  Workspace > Design: back to the design's tab (SOLID, timeline, no drawing steps in it);
   the browser lists the drawing in a Drawings folder; a double-click there opens it again.
"""

import datetime

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import drawing_fixtures as fx
from SciForgeTests.gui import drawing_input as d
from SciForgeTests.gui import harness as h

state = {}


def new_design():
    s.new_design("Bracket")()


# -- A ------------------------------------------------------------------------------------------
def a_new_drawing_empty():
    d.file_menu("New Drawing")


def a_refused():
    from sciforge import drawing

    h.check("no drawing in an empty design", not drawing.drawings(App.ActiveDocument))
    h.check("no dialog opened", d.panel() is None, d.panel())
    h.check("a message says why", "nothing to draw" in d.tooltip_text(), d.tooltip_text())


a_refused.wait_ms = 300


# -- B ------------------------------------------------------------------------------------------
def b_block():
    fx.block(App.ActiveDocument)
    h.fit()
    state["timeline"] = s.steps_of_kind("box") if hasattr(s, "steps_of_kind") else None
    from SciForgeTests.gui import timeline_input as t

    state["titles"] = t.titles()


def b_new_drawing():
    d.file_menu("New Drawing")


def b_dialog():
    p = d.panel_of("CreateDrawingPanel")
    if not h.check("Create Drawing dialog opens", p is not None, d.panel()):
        return
    h.check("Contents: Full Assembly", p.contents.currentText() == "Full Assembly")
    h.check("Standard ISO for a mm design", p.standard.currentText() == "ISO")
    h.check("Units mm", p.units.currentText() == "mm")
    h.check("Sheet A3", p.sheet.currentText() == "A3", p.sheet.currentText())
    h.check("SciForge title block", p.template.currentIndex() == 0)
    d.choose(p.standard, "ASME")
    h.check("ASME sheet sizes", p.sheet.currentText() == "B", p.sheet.currentText())
    d.choose(p.standard, "ISO")
    h.check("back to ISO sizes", p.sheet.currentText() == "A3", p.sheet.currentText())


def b_ok():
    d.ok()


b_ok.wait_ms = 2000


def b_opened():
    from sciforge import drawing

    pages = drawing.drawings(App.ActiveDocument)
    h.check("one drawing", len(pages) == 1, pages)
    page = d.page()
    if not h.check("the drawing's tab is active", page is not None):
        return
    state["page"] = page.Name
    h.check("named after the design", page.Label == "Bracket Drawing", page.Label)
    h.check("first angle (ISO)", page.ProjectionType == "First angle", page.ProjectionType)
    h.check(
        "DRAWING tab shown and current",
        d.ribbon_tab_shown("drawing") and d.current_tab() == "drawing",
    )
    h.check("SOLID tab hidden", not d.ribbon_tab_shown("solid"))
    from sciforge import shell

    h.check("workspace says DRAWING", shell.ribbon().workspace.text().startswith("DRAWING"))
    dock = d.main_window().findChild(QtWidgets.QDockWidget, "SciForgeTimelineDock")
    h.check("timeline steps aside", dock is None or not dock.isVisible())
    title = drawing.title(page)
    h.check("title: design name", title.get("Title") == "Bracket", title)
    h.check("title: part number", title.get("PartNumber") == "Bracket", title)
    h.check("title: date", title.get("Date") == datetime.date.today().isoformat(), title)
    h.check("title: size", title.get("Size") == "A3", title)
    h.check("title: units", title.get("Units") == "mm", title)
    h.check("title: material", title.get("Material") == "Steel", title)
    h.check("title: drawn by", bool(title.get("DrawnBy")), title)
    h.check("title: sheet", title.get("Sheet") == "1 / 1", title)
    h.check("Base View dialog opened", d.panel_of("BaseViewPanel") is not None, d.panel())
    h.shot("b-drawing")


# -- C ------------------------------------------------------------------------------------------
def c_move():
    d.move_to(100, 230)
    d.move_to(120, 190)


def c_follows():
    base = d.bases()[0] if d.bases() else None
    if h.check("a base view follows the mouse", base is not None):
        x, y = d.position(base)
        h.check("at the mouse", abs(x - 120) < 1.0 and abs(y - 190) < 1.0, (x, y))


def c_click():
    d.click_at(130, 185)


def c_placed():
    base = d.bases()[0]
    x, y = d.position(base)
    h.check("placed where clicked", abs(x - 130) < 0.5 and abs(y - 185) < 0.5, (x, y))
    d.move_to(200, 100)
    x, y = d.position(base)
    h.check("stays after the click", abs(x - 130) < 0.5 and abs(y - 185) < 0.5, (x, y))
    p = d.panel_of("BaseViewPanel")
    h.check("orientation Front", p.orientation.currentText() == "Front")
    h.check("default style shows hidden edges", p.style.currentText() == "Visible and Hidden Edges")
    h.check("automatic scale 2:1 on A3", p.scale.currentText() == "2:1", p.scale.currentText())


def c_style():
    p = d.panel_of("BaseViewPanel")
    d.choose(p.style, "Visible Edges")
    d.set_combo_text(p.scale, "1:1")


c_style.wait_ms = 1500


def c_styled():
    base = d.bases()[0]
    h.check("no hidden edges", not base.HardHidden)
    h.check("scale 1:1", abs(base.Scale - 1.0) < 1e-9, base.Scale)
    h.check("the view has edges", d.visible_edge_count(base) > 0)


def c_ok():
    d.ok()


c_ok.wait_ms = 1500


def c_done():
    from sciforge import drawing

    h.check("dialog closed", d.panel() is None)
    page = d.page()
    h.check("title block scale 1:1", drawing.title(page).get("Scale") == "1:1", drawing.title(page))
    h.shot("c-base-view")


# -- D ------------------------------------------------------------------------------------------
def d_undo():
    d.undo()


def d_undone():
    h.check("undo: no base view", not d.bases(), d.bases())


def d_redo():
    d.redo()


d_redo.wait_ms = 1500


def d_redone():
    h.check("redo: the base view is back", len(d.bases()) == 1)


# -- E ------------------------------------------------------------------------------------------
def e_base_again():
    h.ribbon("Base View")


def e_escape():
    h.check("Base View dialog", d.panel_of("BaseViewPanel") is not None)
    d.move_to(300, 200)
    d.key(QtCore.Qt.Key_Escape)


def e_nothing_new():
    h.check("Esc: still one base view", len(d.bases()) == 1, d.bases())
    h.check("dialog closed", d.panel() is None)


# -- F ------------------------------------------------------------------------------------------
def f_design():
    d.workspace("Design")


f_design.wait_ms = 1000


def f_back():
    from SciForgeTests.gui import timeline_input as t

    h.check("design tab active", d.page() is None)
    h.check("SOLID shown again", d.ribbon_tab_shown("solid") and not d.ribbon_tab_shown("drawing"))
    dock = d.main_window().findChild(QtWidgets.QDockWidget, "SciForgeTimelineDock")
    h.check("timeline back", dock is not None and dock.isVisible())
    h.check("no drawing steps in the timeline", t.titles() == state.get("titles"), t.titles())
    h.check("browser: Drawings folder", "Drawings" in s.browser().labels(), s.browser().labels())


def f_open():
    s.browser().refresh(force=True)
    item = s.browser().row("Bracket Drawing")
    if h.check("browser row of the drawing", item is not None, s.browser().labels()):
        from SciForgeTests.gui import widget_input as wi

        tree = s.browser()
        wi.double_click(tree.viewport(), tree.label_point(item))


f_open.wait_ms = 1200


def f_opened():
    h.check("the drawing's tab again", d.page() is not None and d.page().Name == state.get("page"))
    h.check("DRAWING tab again", d.current_tab() == "drawing")
    h.shot("f-end")


from PySide import QtWidgets  # noqa: E402

h.run(
    "drawing_new",
    [
        new_design,
        a_new_drawing_empty,
        a_refused,
        b_block,
        b_new_drawing,
        b_dialog,
        b_ok,
        b_opened,
        c_move,
        c_follows,
        c_click,
        c_placed,
        c_style,
        c_styled,
        c_ok,
        c_done,
        d_undo,
        d_undone,
        d_redo,
        d_redone,
        e_base_again,
        e_escape,
        e_nothing_new,
        f_design,
        f_back,
        f_open,
        f_opened,
    ],
)
