# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Sheet Bar: the sheets of a drawing as tabs along the bottom of its tab, a +
for a new sheet, right-click for New Sheet, Rename Sheet, Delete Sheet, Move Left / Right;
drag a tab to move the sheet, double-click it to rename it in place. A drawing shows one
sheet at a time in one tab, like Fusion's (the logic is in drawing_sheets.py)."""

import FreeCADGui as Gui

from . import commands, drawing, drawing_sheets, drawing_ui, log, taskui, warn
from .compat import QtCore, QtWidgets

BAR_NAME = "SciForgeSheetBar"
TABS_NAME = "SciForgeSheetTabs"
_BARS = []  # the bars made (kept here: PySide drops a subclass' Python side otherwise)


def _later(fn, *args, ms=0):
    drawing_ui._later(fn, *args, ms=ms)


# ------------------------------------------------------------------ the bar
def _sub_of(page):
    """The MDI sub-window (tab) showing a drawing sheet."""
    area = drawing_ui._area()
    if area is None:
        return None
    for sub in area.subWindowList():
        try:
            if drawing.same(drawing_ui.page_of_window(sub), page):
                return sub
        except RuntimeError:
            continue
    return None


def _bar_in(window):
    for bar in list(_BARS):
        try:
            if bar.parent() is window:
                return bar
        except RuntimeError:
            _BARS.remove(bar)  # (its tab was closed)
    return None


def bar_of(page):
    sub = _sub_of(page)
    if sub is None or sub.widget() is None:
        return None
    return _bar_in(sub.widget())


def ensure_bar(page):
    """The Sheet Bar of the tab showing `page` (made the first time), up to date."""
    sub = _sub_of(page)
    if sub is None:
        return None
    window = sub.widget()
    if not isinstance(window, QtWidgets.QMainWindow):
        return None
    bar = _bar_in(window)
    if bar is None:
        bar = SheetBar(window)
        _BARS.append(bar)
        window.addToolBar(QtCore.Qt.BottomToolBarArea, bar)
    bar.sheet_bar.page = page
    bar.sheet_bar.refresh()
    return bar


class SheetBar(QtWidgets.QToolBar):
    """The tabs of a drawing's sheets and the + button."""

    def __init__(self, parent):
        super().__init__("Sheets", parent)
        self.setObjectName(BAR_NAME)
        self.setMovable(False)
        self.setFloatable(False)
        self.sheet_bar = self
        self.page = None
        self.building = False
        self.editor = None
        self.tabs = QtWidgets.QTabBar()
        self.tabs.setObjectName(TABS_NAME)
        self.tabs.setMovable(True)
        self.tabs.setExpanding(False)
        self.tabs.setDrawBase(False)
        self.tabs.setFocusPolicy(QtCore.Qt.NoFocus)
        self.tabs.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.addWidget(self.tabs)
        self.plus = QtWidgets.QToolButton()
        self.plus.setText("+")
        self.plus.setToolTip("New Sheet")
        self.plus.setObjectName("SciForgeNewSheet")
        self.plus.setFocusPolicy(QtCore.Qt.NoFocus)
        self.addWidget(self.plus)
        self.tabs.currentChanged.connect(self._clicked)
        self.tabs.tabMoved.connect(self._moved)
        self.tabs.customContextMenuRequested.connect(self._menu)
        self.tabs.tabBarDoubleClicked.connect(self.rename_inline)
        self.plus.clicked.connect(lambda: _later(new_sheet, self.page))

    def sheets(self):
        return drawing_sheets.sheets(self.page) if drawing.alive(self.page) else []

    def refresh(self):
        if not drawing.alive(self.page):
            return
        self.building = True
        try:
            while self.tabs.count():
                self.tabs.removeTab(0)
            current = 0
            for i, sheet in enumerate(self.sheets()):
                index = self.tabs.addTab(drawing_sheets.sheet_name(sheet))
                self.tabs.setTabData(index, sheet.Name)
                self.tabs.setTabToolTip(index, "Sheet %d: right-click for more" % (i + 1))
                if drawing.same(sheet, self.page):
                    current = index
            self.tabs.setCurrentIndex(current)
        finally:
            self.building = False

    def sheet_at(self, index):
        name = self.tabs.tabData(index)
        doc = self.page.Document if drawing.alive(self.page) else None
        obj = doc.getObject(name) if doc is not None and name else None
        return obj if drawing.alive(obj) else None

    # -- events -------------------------------------------------------------------------
    def _clicked(self, index):
        if self.building or index < 0:
            return
        target = self.sheet_at(index)
        if target is not None and not drawing.same(target, self.page):
            _later(switch_to, target)

    def _moved(self, src, dst):
        if self.building:
            return
        sheet = self.sheet_at(dst)
        if sheet is not None:
            _later(move, sheet, dst)

    def _menu(self, pos):
        try:
            index = self.tabs.tabAt(pos)
            sheet = self.sheet_at(index) if index >= 0 else self.page
            menu = QtWidgets.QMenu(self)
            menu.setObjectName("SciForgeSheetMenu")
            count = self.tabs.count()
            actions = [
                (
                    "New Sheet",
                    lambda: _later(new_sheet, sheet, index + 1 if index >= 0 else None),
                    True,
                ),
                ("Rename Sheet", lambda: _later(self.rename_inline, index), index >= 0),
                ("Delete Sheet", lambda: _later(delete, sheet), count > 1),
                ("Move Left", lambda: _later(move, sheet, index - 1), index > 0),
                ("Move Right", lambda: _later(move, sheet, index + 1), 0 <= index < count - 1),
            ]
            for text, fn, enabled in actions:
                action = menu.addAction(text)
                action.setEnabled(enabled)
                action.triggered.connect(fn)
            menu.popup(self.tabs.mapToGlobal(pos))
        except Exception as exc:
            warn("sheet menu: %s" % exc)

    def rename_inline(self, index):
        """Fusion: the sheet's name becomes a box to type in; Enter keeps it, Esc not."""
        try:
            if index < 0:
                return
            sheet = self.sheet_at(index)
            if sheet is None:
                return
            if self.editor is not None:
                self.editor.deleteLater()
            editor = QtWidgets.QLineEdit(self.tabs)
            editor.setObjectName("SciForgeSheetRename")
            editor.setText(drawing_sheets.sheet_name(sheet))
            editor.selectAll()
            editor.setGeometry(self.tabs.tabRect(index))
            editor.show()
            editor.setFocus()
            self.editor = editor
            done = {"finished": False}

            def finish(keep):
                if done["finished"]:
                    return
                done["finished"] = True
                text = editor.text()
                editor.hide()
                editor.deleteLater()
                self.editor = None
                if keep:
                    _later(rename, sheet, text)

            editor.returnPressed.connect(lambda: finish(True))
            editor.editingFinished.connect(lambda: finish(True))
            editor.installEventFilter(_EscapeFilter(editor, lambda: finish(False)))
        except Exception as exc:
            warn("rename sheet: %s" % exc)


class _EscapeFilter(QtCore.QObject):
    def __init__(self, parent, on_escape):
        super().__init__(parent)
        self.on_escape = on_escape

    def eventFilter(self, obj, event):
        try:
            if event.type() == QtCore.QEvent.KeyPress and event.key() == QtCore.Qt.Key_Escape:
                self.on_escape()
                return True
        except Exception:
            pass
        return False


# ------------------------------------------------------------------ switching sheets
def _area_tabs():
    area = drawing_ui._area()
    if area is None:
        return None
    for bar in area.findChildren(QtWidgets.QTabBar, "", QtCore.Qt.FindDirectChildrenOnly):
        return bar
    return None


def _tab_index(title):
    bar = _area_tabs()
    if bar is None:
        return -1
    for i in range(bar.count()):
        if bar.tabText(i).replace("[*]", "").strip() == title:
            return i
    return -1


def switch_to(target):
    """Show another sheet of the drawing in its place (one tab per drawing, like
    Fusion's): the target's tab opens where the current sheet's was, which closes."""
    current = drawing_ui.active_page()
    if not drawing.alive(target) or drawing.same(current, target):
        return False
    if not commands.finish_open_dialog():
        return False
    gdoc = Gui.getDocument(target.Document.Name)
    saved = not gdoc.Modified
    old_index = _tab_index(current.Label) if current is not None else -1
    drawing_ui.open_drawing(target)
    if current is not None and drawing.same(
        drawing_sheets.main_page(current), drawing_sheets.main_page(target)
    ):
        tab = drawing_ui.active_tab()
        drawing_ui.close_tab(current)
        drawing_ui.restore_tab(tab)
        bar = _area_tabs()
        new_index = _tab_index(target.Label)
        if bar is not None and old_index >= 0 and new_index > old_index:
            try:
                bar.moveTab(new_index, old_index)
            except Exception as exc:
                log("sheet tab not moved: %s" % exc)
    if saved:
        drawing_ui._not_modified(gdoc)
        _later(drawing_ui._not_modified, gdoc, ms=0)
    _later(drawing_ui.sync_mode, ms=30)
    log("sheet %s shown" % target.Label)
    return True


# ------------------------------------------------------------------ sheet operations
def _transaction(doc, name, fn):
    doc.openTransaction(name)
    try:
        result = fn()
    except drawing_sheets.SheetError as exc:
        taskui._end_transaction(doc, abort=True)
        commands.tell(str(exc))
        return None
    except Exception as exc:
        taskui._end_transaction(doc, abort=True)
        warn("%s: %s" % (name, exc))
        return None
    doc.recompute()
    taskui._end_transaction(doc)
    return result


def new_sheet(page, index=None):
    """Fusion's + in the Sheet Bar: a new empty sheet, made the active one."""
    if not drawing.alive(page) or not commands.finish_open_dialog():
        return None
    doc = page.Document
    sheet = _transaction(doc, "New Sheet", lambda: drawing_sheets.add_sheet(page, index))
    if sheet is not None:
        switch_to(sheet)
        _later(_refresh_bars, page, ms=60)
    return sheet


def rename(sheet, name):
    if not drawing.alive(sheet):
        return False
    doc = sheet.Document
    done = _transaction(
        doc, "Rename Sheet", lambda: drawing_sheets.rename_sheet(sheet, name) or True
    )
    _later(_refresh_bars, sheet, ms=30)
    return bool(done)


def move(sheet, index):
    if not drawing.alive(sheet):
        return False
    doc = sheet.Document
    done = _transaction(doc, "Move Sheet", lambda: drawing_sheets.move_sheet(sheet, index) or True)
    _later(_refresh_bars, sheet, ms=30)
    return bool(done)


def delete(sheet):
    """Fusion's Delete Sheet: the sheet and everything on it (one undo step)."""
    if not drawing.alive(sheet) or not commands.finish_open_dialog():
        return None
    doc = sheet.Document
    if len(drawing_sheets.sheets(sheet)) <= 1:
        commands.tell(
            "A drawing keeps at least one sheet: delete the whole drawing in the browser "
            "(Drawings folder) instead."
        )
        return None
    rest = [s for s in drawing_sheets.sheets(sheet) if not drawing.same(s, sheet)]
    order = drawing_sheets.sheets(sheet)
    index = [i for i, s in enumerate(order) if drawing.same(s, sheet)][0]
    show = rest[min(index, len(rest) - 1)]
    if drawing.same(drawing_ui.active_page(), sheet):
        switch_to(show)
    else:
        drawing_ui.close_tab(sheet)
    shown = _transaction(doc, "Delete Sheet", lambda: drawing_sheets.delete_sheet(sheet))
    if shown is not None:
        _later(_refresh_bars, shown, ms=60)
    return shown


def _refresh_bars(page):
    if not drawing.alive(page):
        return
    for sheet in drawing_sheets.sheets(page):
        bar = bar_of(sheet)
        if bar is not None:
            bar.sheet_bar.page = sheet
            bar.sheet_bar.refresh()


def close_orphans():
    """Tabs left open by a sheet that Undo took away (TechDraw keeps a page's tab when
    the page is removed while the tab shows)."""
    area = drawing_ui._area()
    if area is None:
        return
    for sub in list(area.subWindowList()):
        try:
            widget = sub.widget()
            if widget is None or widget.metaObject().className() != drawing_ui.PAGE_VIEW:
                continue
            if drawing_ui.page_of_window(sub) is None:
                log("closing the tab of a sheet that is gone: %s" % sub.windowTitle())
                sub.close()
        except RuntimeError:
            continue


# ------------------------------------------------------------------ commands
class NewSheetCommand(drawing_ui._Base):
    title = "New Sheet"
    tip = "A new empty sheet in this drawing (also the + of the sheet bar)"
    icon = "dw_new"

    def run(self):
        page = drawing_ui._need_page()
        if page is not None:
            new_sheet(page)


class DeleteSheetCommand(drawing_ui._Base):
    title = "Delete Sheet"
    tip = "Delete the active sheet and everything on it"
    icon = "delete"

    def run(self):
        page = drawing_ui._need_page()
        if page is not None:
            delete(page)


COMMANDS = {
    "SciForge_DrawingNewSheet": NewSheetCommand,
    "SciForge_DrawingDeleteSheet": DeleteSheetCommand,
}
