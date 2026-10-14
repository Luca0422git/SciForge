# SPDX-License-Identifier: LGPL-2.1-or-later
"""Several sheets in one drawing (Fusion's Sheet Bar), with real clicks.

The plate (drawing_fixtures.plate), ISO A3, base view Top at 1:1 on sheet 1.

A  The drawing's tab has a sheet bar: one tab "Sheet 1" and a +; the title block reads
   1 / 1.
B  + : a new empty sheet, shown in the drawing's one tab; the bar has Sheet 1 and
   Sheet 2 (the current one); title blocks 2 / 2 and 1 / 2.
C  On sheet 2: a Base View placed by a click, then a Section View through hole 1: both
   are on sheet 2's page.
D  The bar's Sheet 1 tab: sheet 1 again (its base view); the Sheet 2 tab: back.
E  Right-click Sheet 2 > Rename Sheet: its name in a box on the tab; typed "Sections",
   Enter: the tab and the drawing's tab title say so.
F  Right-click Sections > Move Left: Sections is sheet 1 of 2 now, Sheet 1 is 2 of 2.
   Undo: back; Redo: moved again.
G  EXPORT > Export PDF, All Sheets: one PDF with 2 pages; Current Sheet: 1 page.
   Export DXF, All Sheets: a DXF per sheet named after it; the Sections one has its
   section's label.
H  + then right-click the new sheet > Delete Sheet: 2 sheets again; Undo: 3; Redo: 2.
I  Right-click Sheet 1 (the drawing's first page) > Delete Sheet: the drawing keeps its
   name with the one sheet left; deleting that one too is refused (delete the drawing in
   the browser instead). Undo brings Sheet 1 back.
"""

import os

import FreeCAD as App
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import drawing2_steps as w
from SciForgeTests.gui import drawing_input as d
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import widget_input as wi

state = {}
OUT = os.path.join(h.OUT_DIR, "drawing2")


def bar():
    from sciforge import drawing_sheets_ui

    page = d.page()
    return drawing_sheets_ui.bar_of(page) if page is not None else None


def tab_texts():
    b = bar()
    return [b.tabs.tabText(i) for i in range(b.tabs.count())] if b is not None else []


def tab_pos(text):
    b = bar()
    for i in range(b.tabs.count()):
        if b.tabs.tabText(i) == text:
            return b.tabs.tabRect(i).center()
    return None


def click_tab(text):
    pos = tab_pos(text)
    if h.check("a sheet tab %s" % text, pos is not None, tab_texts()):
        wi.click(bar().tabs, pos)


def menu_on_tab(text, entry):
    pos = tab_pos(text)
    if h.check("a sheet tab %s" % text, pos is not None, tab_texts()):
        h.check("%s > %s" % (text, entry), wi.right_click(bar().tabs, pos, entry))


def sheets():
    from sciforge import drawing_sheets

    return drawing_sheets.sheets(d.page()) if d.page() is not None else []


def title_of(page):
    from sciforge import drawing

    return drawing.title(page).get("Sheet")


def drawing_tabs():
    from sciforge import drawing_ui

    area = drawing_ui._area()
    return [
        s.windowTitle().replace("[*]", "").strip()
        for s in area.subWindowList()
        if s.widget() is not None and s.widget().metaObject().className() == drawing_ui.PAGE_VIEW
    ]


def doc():
    return App.ActiveDocument


# -- A ------------------------------------------------------------------------------------------
def a_bar():
    b = bar()
    if not h.check("a sheet bar", b is not None and b.isVisible()):
        return
    h.check("one sheet", tab_texts() == ["Sheet 1"], tab_texts())
    h.check("a + button", b.plus.isVisible())
    h.check("1 / 1", title_of(d.page()) == "1 / 1", title_of(d.page()))
    state["main"] = d.page().Name
    state["label"] = d.page().Label


# -- B ------------------------------------------------------------------------------------------
def b_plus():
    wi.click(bar().plus)


b_plus.wait_ms = 2500


def b_new():
    from sciforge import drawing_sheets

    page = d.page()
    h.check(
        "a new sheet shows", page is not None and page.Name != state["main"], page and page.Name
    )
    h.check("one tab for the drawing", len(drawing_tabs()) == 1, drawing_tabs())
    h.check("two sheets in the bar", tab_texts() == ["Sheet 1", "Sheet 2"], tab_texts())
    h.check("Sheet 2 is the current tab", bar().tabs.currentIndex() == 1)
    h.check("2 / 2", title_of(page) == "2 / 2", title_of(page))
    main = doc().getObject(state["main"])
    h.check("sheet 1: 1 / 2", title_of(main) == "1 / 2", title_of(main))
    h.check("the same drawing", drawing_sheets.main_page(page).Name == state["main"])
    h.check("still one drawing in the browser", len(d.drawing_module().drawings(doc())) == 1)
    h.check("empty", not d.drawing_module().all_views(page))
    state["sheet2"] = page.Name
    h.shot("b-two-sheets")


# -- C ------------------------------------------------------------------------------------------
def c_base():
    h.ribbon("Base View")


c_base.wait_ms = 1500


def c_place():
    p = d.panel_of("BaseViewPanel")
    if not h.check("Base View on sheet 2", p is not None, d.panel()):
        return
    d.move_to(150, 210)
    d.click_at(130, 200)
    d.choose(p.orientation, "Top")
    d.set_combo_text(p.scale, "1:1")


c_place.wait_ms = 1500


def c_ok():
    d.ok()


c_ok.wait_ms = 2500


def c_section():
    h.ribbon("Section View")


def c_cut():
    w.click(10.0, 5.0)
    w.click(-20.0, 33.0)
    w.click(-20.0, -33.0)
    x, y = w.at(0.0, 0.0)
    d.move_to(x + 70, y + 3)
    d.move_to(x + 90, y + 2)


c_cut.wait_ms = 2500


def c_put():
    x, y = w.at(0.0, 0.0)
    d.click_at(x + 90, y + 2)


def c_ok2():
    d.ok()


c_ok2.wait_ms = 2500


def c_check():
    from sciforge import drawing

    page = d.page()
    views = drawing.all_views(page)
    h.check("sheet 2 has its views", len(views) == 2, [v.Label for v in views])
    h.check(
        "a section among them",
        any(drawing.is_section(v) for v in views),
        [v.TypeId for v in views],
    )
    main = doc().getObject(state["main"])
    h.check("sheet 1 keeps its one view", len(drawing.all_views(main)) == 1)


# -- D ------------------------------------------------------------------------------------------
def d_sheet1():
    click_tab("Sheet 1")


d_sheet1.wait_ms = 2500


def d_shown():
    page = d.page()
    h.check("sheet 1 shows", page is not None and page.Name == state["main"], page and page.Name)
    h.check("one tab for the drawing", len(drawing_tabs()) == 1, drawing_tabs())
    h.check("its bar: Sheet 1 current", bar() is not None and bar().tabs.currentIndex() == 0)
    click_tab("Sheet 2")


d_shown.wait_ms = 2500


def d_back():
    page = d.page()
    h.check("sheet 2 again", page is not None and page.Name == state["sheet2"], page and page.Name)


# -- E ------------------------------------------------------------------------------------------
def e_rename():
    menu_on_tab("Sheet 2", "Rename Sheet")


e_rename.wait_ms = 1500


def e_type():
    b = bar()
    editor = b.editor if b is not None else None
    if not h.check("a box on the tab", editor is not None and editor.isVisible()):
        return
    h.check("with the name", editor.text() == "Sheet 2", editor.text())
    QtTest.QTest.keyClick(editor, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
    QtTest.QTest.keyClicks(editor, "Sections")
    QtTest.QTest.keyClick(editor, QtCore.Qt.Key_Return)


e_type.wait_ms = 2000


def e_renamed():
    h.check("the tab says Sections", tab_texts() == ["Sheet 1", "Sections"], tab_texts())
    page = doc().getObject(state["sheet2"])
    h.check("the sheet's title", page.Label == state["label"] + ": Sections", page.Label)
    h.check("the drawing's tab title", drawing_tabs() == [page.Label], drawing_tabs())


# -- F ------------------------------------------------------------------------------------------
def f_move():
    menu_on_tab("Sections", "Move Left")


f_move.wait_ms = 2000


def f_moved():
    h.check("Sections first", tab_texts() == ["Sections", "Sheet 1"], tab_texts())
    main = doc().getObject(state["main"])
    sheet2 = doc().getObject(state["sheet2"])
    h.check("Sections: 1 / 2", title_of(sheet2) == "1 / 2", title_of(sheet2))
    h.check("Sheet 1: 2 / 2", title_of(main) == "2 / 2", title_of(main))
    d.undo()


f_moved.wait_ms = 2000


def f_undone():
    order = [p.Name for p in sheets()]
    h.check("undo: the old order", order == [state["main"], state["sheet2"]], order)
    main = doc().getObject(state["main"])
    h.check("Sheet 1: 1 / 2 again", title_of(main) == "1 / 2", title_of(main))
    d.redo()


f_undone.wait_ms = 2000


def f_redone():
    order = [p.Name for p in sheets()]
    h.check("redo: moved", order == [state["sheet2"], state["main"]], order)
    h.check("the bar follows", tab_texts() == ["Sections", "Sheet 1"], tab_texts())


# -- G ------------------------------------------------------------------------------------------
def export_dialog():
    from sciforge import drawing_ui

    dlg = drawing_ui.ExportDialog.last
    try:
        return dlg if dlg is not None and dlg.isVisible() else None
    except RuntimeError:
        return None


def g_pdf():
    os.makedirs(OUT, exist_ok=True)
    h.ribbon("Export PDF")


g_pdf.wait_ms = 1500


def g_pdf_fill():
    dlg = export_dialog()
    if not h.check("the Export PDF dialog", dlg is not None):
        return
    h.check("All Sheets by default", dlg.sheets.currentText() == "All Sheets")
    h.check("named after the drawing", dlg.name.text() == state["label"], dlg.name.text())
    if dlg.open_after.isChecked():
        w.toggle(dlg.open_after)
    d.type_into(dlg.name, "sheets_all")
    d.type_into(dlg.folder, OUT)
    wi.click(dlg.export_button)


g_pdf_fill.wait_ms = 6000


def g_pdf_check():
    from sciforge import drawing_pdf

    path = os.path.join(OUT, "sheets_all.pdf")
    if h.check("the PDF is written", os.path.isfile(path), os.listdir(OUT)):
        with open(path, "rb") as handle:
            pages = drawing_pdf.page_count(handle.read())
        h.check("2 pages", pages == 2, pages)
    leftovers = [f for f in os.listdir(OUT) if f.endswith(".tmp.pdf")]
    h.check("no part files left", not leftovers, leftovers)
    h.ribbon("Export PDF")


g_pdf_check.wait_ms = 1500


def g_current():
    dlg = export_dialog()
    if not h.check("the dialog again", dlg is not None):
        return
    d.choose(dlg.sheets, "Current Sheet")
    if dlg.open_after.isChecked():
        w.toggle(dlg.open_after)
    d.type_into(dlg.name, "sheets_current")
    d.type_into(dlg.folder, OUT)
    wi.click(dlg.export_button)


g_current.wait_ms = 4000


def g_current_check():
    from sciforge import drawing_pdf

    path = os.path.join(OUT, "sheets_current.pdf")
    if h.check("the current sheet's PDF", os.path.isfile(path)):
        with open(path, "rb") as handle:
            pages = drawing_pdf.page_count(handle.read())
        h.check("1 page", pages == 1, pages)
    h.ribbon("Export DXF")


g_current_check.wait_ms = 1500


def g_dxf():
    dlg = export_dialog()
    if not h.check("the Export DXF dialog", dlg is not None):
        return
    d.type_into(dlg.name, "sheets")
    d.type_into(dlg.folder, OUT)
    wi.click(dlg.export_button)


g_dxf.wait_ms = 3000


def g_dxf_check():
    from sciforge import drawing_core

    names = sorted(f for f in os.listdir(OUT) if f.startswith("sheets") and f.endswith(".dxf"))
    h.check("a DXF per sheet", names == ["sheets - Sections.dxf", "sheets - Sheet 1.dxf"], names)
    path = os.path.join(OUT, "sheets - Sections.dxf")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as handle:
            ents = drawing_core.read_dxf_entities(handle.read())
        words = [e[1].get(1, [""])[0] for e in ents if e[0] == "TEXT"]
        h.check("the Sections DXF has the section's label", "SECTION A-A" in words, words)
        h.check("and its title block's 1 / 2", "1 / 2" in words, words)


# -- H ------------------------------------------------------------------------------------------
def h_plus():
    wi.click(bar().plus)


h_plus.wait_ms = 2500


def h_three():
    h.check("three sheets", len(sheets()) == 3, tab_texts())
    state["sheet3"] = d.page().Name
    menu_on_tab(tab_texts()[-1], "Delete Sheet")


h_three.wait_ms = 2500


def h_two():
    h.check("two sheets again", len(sheets()) == 2, tab_texts())
    h.check("its page went", doc().getObject(state["sheet3"]) is None)
    h.check("one tab for the drawing", len(drawing_tabs()) == 1, drawing_tabs())
    d.undo()


h_two.wait_ms = 2500


def h_undone():
    h.check("undo: three", len(sheets()) == 3, [p.Label for p in sheets()])
    d.redo()


h_undone.wait_ms = 2500


def h_redone():
    h.check("redo: two", len(sheets()) == 2, [p.Label for p in sheets()])


# -- I ------------------------------------------------------------------------------------------
def i_delete_first():
    menu_on_tab("Sheet 1", "Delete Sheet")


i_delete_first.wait_ms = 3000


def i_promoted():
    from sciforge import drawing

    found = drawing.drawings(doc())
    h.check("still one drawing", len(found) == 1, [p.Label for p in found])
    if found:
        h.check("it keeps its name", found[0].Label == state["label"], found[0].Label)
        h.check("now made of Sections", found[0].Name == state["sheet2"], found[0].Name)
    h.check("one sheet", tab_texts() == ["Sections"], tab_texts())
    h.check("1 / 1", title_of(d.page()) == "1 / 1", title_of(d.page()))
    Gui_run("SciForge_DrawingDeleteSheet")


i_promoted.wait_ms = 1500


def Gui_run(name):
    import FreeCADGui as Gui

    Gui.runCommand(name)
    QtWidgets.QApplication.processEvents()


def i_refused():
    h.check("the last sheet stays", len(sheets()) == 1, tab_texts())
    h.check("and says why", "at least one sheet" in d.tooltip_text(), d.tooltip_text())
    d.undo()


i_refused.wait_ms = 3000


def i_undone():
    from sciforge import drawing

    h.check("undo: Sheet 1 is back", doc().getObject(state["main"]) is not None)
    found = drawing.drawings(doc())
    h.check("one drawing", len(found) == 1, [p.Label for p in found])
    h.check("two sheets", len(sheets()) == 2, [p.Label for p in sheets()])


h.run(
    "drawing2_sheets",
    [w.new_design("Sh")]
    + w.sheet_steps()
    + [d.wait_geometry(1500), a_bar]
    + [b_plus, b_new]
    + [c_base, c_place, c_ok, d.wait_geometry(1500), c_section, c_cut, c_put, c_ok2, c_check]
    + [d_sheet1, d_shown, d_back]
    + [e_rename, e_type, e_renamed]
    + [f_move, f_moved, f_undone, f_redone]
    + [g_pdf, g_pdf_fill, g_pdf_check, g_current, g_current_check, g_dxf, g_dxf_check]
    + [h_plus, h_three, h_two, h_undone, h_redone]
    + [i_delete_first, i_promoted, i_refused, i_undone],
)
