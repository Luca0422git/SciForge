# SPDX-License-Identifier: LGPL-2.1-or-later
"""Real input on a drawing's sheet and the drawing dialogs, for the drawing_* scenarios.

Clicks go to TechDraw's page view at a point given in page millimetres (origin at the
sheet's bottom left, y up), exactly where a person would click; the menus are opened and
clicked with the mouse. Kept outside scenarios/ because every file there is a scenario."""

import os

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import widget_input as wi

OUT = os.path.join(h.OUT_DIR, "drawings")


def _process():
    QtWidgets.QApplication.processEvents()


# -- the sheet ----------------------------------------------------------------------------
def page():
    from sciforge import drawing_ui

    return drawing_ui.active_page()


def gv():
    from sciforge import drawing_ui

    return drawing_ui.page_widget()


def widget_point(x, y):
    from sciforge import drawing_ui

    view = gv()
    return drawing_ui.to_widget(view, page(), (x, y))


def move_to(x, y):
    view = gv()
    if view is None:
        h.check("a drawing tab is active", False)
        return
    QtTest.QTest.mouseMove(view.viewport(), widget_point(x, y))
    _process()


def click_at(x, y, modifiers=QtCore.Qt.NoModifier):
    """Move to a page point (mm) and click there, as a person does."""
    view = gv()
    if view is None:
        h.check("a drawing tab is active", False)
        return
    pos = widget_point(x, y)
    QtTest.QTest.mouseMove(view.viewport(), pos)
    _process()
    QtTest.QTest.mouseClick(view.viewport(), QtCore.Qt.LeftButton, modifiers, pos)
    _process()
    h.state["last_click"] = "page (%.2f, %.2f) mm -> pixel (%d, %d)" % (x, y, pos.x(), pos.y())


def double_click_at(x, y):
    view = gv()
    if view is None:
        h.check("a drawing tab is active", False)
        return
    wi.double_click(view.viewport(), widget_point(x, y))


def key(k, modifiers=QtCore.Qt.NoModifier):
    """A key with the sheet focused (the sheet has the keyboard after a click on it)."""
    view = gv()
    if view is None:
        h.check("a drawing tab is active", False)
        return
    view.setFocus()
    if isinstance(k, str):
        QtTest.QTest.keyClicks(view, k, modifiers)
    else:
        QtTest.QTest.keyClick(view, k, modifiers)
    _process()


def undo():
    key(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def redo():
    key(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


# -- dialogs ------------------------------------------------------------------------------
def panel():
    from sciforge import taskui

    return taskui.current()


def panel_of(cls_name):
    p = panel()
    return p if p is not None and type(p).__name__ == cls_name else None


def ok():
    return h.task_button("OK")


def cancel():
    return h.task_button("Cancel")


def choose(combo, label):
    return b.choose(combo, label)


def type_into(widget, text):
    b.type_into(widget, text)


def set_combo_text(combo, text):
    """An editable drop-down: click in, select all, type (the scale box takes "1:1")."""
    edit = combo.lineEdit()
    b.type_into(edit, text)
    QtTest.QTest.keyClick(edit, QtCore.Qt.Key_Tab)
    _process()


# -- menus --------------------------------------------------------------------------------
def _navigate(labels, done, step=0, tries=0):
    menu = QtWidgets.QApplication.activePopupWidget()
    if not isinstance(menu, QtWidgets.QMenu) or (step > 0 and menu is done.get("menu")):
        if tries < 25:
            QtCore.QTimer.singleShot(120, lambda: _navigate(labels, done, step, tries + 1))
        else:
            _close_popups()
        return
    action = None
    for a in menu.actions():
        if a.text().replace("&", "").split("\t")[0].strip() == labels[step]:
            action = a
            break  # the first one (SciForge's File menu comes before FreeCAD's)
    if action is None:
        done["missing"] = [a.text() for a in menu.actions()]
        _close_popups()
        return
    rect = menu.actionGeometry(action)
    for i in range(6):
        QtTest.QTest.mouseMove(menu, QtCore.QPoint(rect.left() + 8 + 6 * i, rect.center().y()))
    QtTest.QTest.mouseMove(menu, rect.center())
    if action.menu() is not None and step + 1 < len(labels):
        done["menu"] = menu
        menu.setActiveAction(action)
        QtCore.QTimer.singleShot(400, lambda: _navigate(labels, done, step + 1))
        return
    if not action.isEnabled():
        done["disabled"] = labels[step]
        _close_popups()
        return
    QtTest.QTest.mouseClick(menu, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, rect.center())
    done["clicked"] = True


def _close_popups():
    popup = QtWidgets.QApplication.activePopupWidget()
    while popup is not None:
        popup.close()
        popup = QtWidgets.QApplication.activePopupWidget()


def menu_path(open_button, labels):
    """Click a button that opens a menu, then the entries `labels` (submenus on the way)."""
    done = {}
    QtCore.QTimer.singleShot(300, lambda: _navigate(list(labels), done))
    guard = QtCore.QTimer()
    guard.setSingleShot(True)
    guard.timeout.connect(_close_popups)
    guard.start(6000)
    open_button.click()
    guard.stop()
    _process()
    ok = bool(done.get("clicked"))
    h.check("menu %s" % " > ".join(labels), ok, done)
    return ok


def file_menu(label):
    """The app menu (quick-access Menu button) > File > label."""
    from sciforge import shell

    ribbon = shell.ribbon()
    button = None
    for candidate in ribbon.findChildren(QtWidgets.QToolButton):
        if candidate.toolTip().startswith("Menu") and candidate.isVisible():
            button = candidate
    if button is None:
        h.check("the Menu button", False)
        return False
    return menu_path(button, ["File", label])


def workspace(*labels):
    """The workspace button (DESIGN / DRAWING) and its menu entries."""
    from sciforge import shell

    return menu_path(shell.ribbon().workspace, labels)


def group_menu(group, label):
    from SciForgeTests.gui import sketch_input

    return sketch_input.menu_item(group, label)


def ribbon_tab_shown(tab_id):
    from sciforge import shell

    button = shell.ribbon().tab_buttons.get(tab_id)
    return button is not None and button.isVisible()


def current_tab():
    from sciforge import shell

    return shell.ribbon().current_tab()


def tooltip_text():
    return QtWidgets.QToolTip.text() if QtWidgets.QToolTip.isVisible() else ""


# -- what is on the sheet ---------------------------------------------------------------
def drawing_module():
    from sciforge import drawing

    return drawing


def views():
    d = drawing_module()
    p = page()
    return d.all_views(p) if p is not None else []


def bases():
    """The base views of the active drawing."""
    d = drawing_module()
    p = page()
    return d.base_views(p) if p is not None else []


def of_type(type_id):
    p = page()
    if p is None:
        return []
    return [o for o in p.Views if o.TypeId == type_id] + [
        v for v in drawing_module().all_views(p) if v.TypeId == type_id and v not in p.Views
    ]


def position(view):
    return drawing_module().view_position(view)


def to_page(view, local):
    return drawing_module().local_to_page(view, local)


def edges(view):
    """{name: info} of every edge of a view (drawing.edge_info)."""
    d = drawing_module()
    found = {}
    i = 0
    while i < 2000:
        info = d.edge_info(view, "Edge%d" % i)
        if info is None:
            try:
                view.getEdgeBySelection("Edge%d" % i)
            except Exception:
                break
            i += 1
            continue
        found["Edge%d" % i] = info
        i += 1
    return found


def edge_point(view, predicate, at=0.5):
    """A page point on the first edge of `view` that `predicate(info)` accepts (lines: at
    `at` of their length; circles: their rightmost point; arcs: their middle)."""
    import math

    for name, info in edges(view).items():
        if not predicate(info):
            continue
        if info["kind"] == "line":
            (x1, y1), (x2, y2) = info["p1"], info["p2"]
            local = (x1 + (x2 - x1) * at, y1 + (y2 - y1) * at)
        elif info["kind"] in ("circle", "arc"):
            edge = view.getEdgeBySelection(name)
            if info["kind"] == "circle":
                local = (info["center"][0] + info["radius"], info["center"][1])
            else:
                p = edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2.0)
                local = (p.x, p.y)
        else:
            continue
        del math
        return to_page(view, local)
    return None


def wait_geometry(ms=1500):
    def step():
        pass

    step.__name__ = "wait_geometry_%d" % ms
    step.wait_ms = ms
    return step


def visible_edge_count(view):
    try:
        return len(view.getVisibleEdges())
    except Exception:
        return 0


def record_opener():
    from sciforge import drawing_ui

    opened = []
    drawing_ui.OPENER["open"] = lambda path: opened.append(path)
    return opened


def ensure_out():
    os.makedirs(OUT, exist_ok=True)
    return OUT


def active_doc():
    return App.ActiveDocument


def main_window():
    return Gui.getMainWindow()


# -- a drawing made the way a person makes one ---------------------------------------------
def drawing_steps(
    prefix,
    standard=None,
    sheet=None,
    views=None,
    base_at=None,
    scale=None,
    style=None,
    contents=None,
    untick=(),
    orientation=None,
    units=None,
):
    """Steps: File > New Drawing, the dialog's choices, OK; then (manual views) a click
    that places the base view at `base_at`, the style and scale typed, OK."""
    state = {}

    def new_drawing():
        state["before"] = len(drawing_module().drawings(App.ActiveDocument))
        file_menu("New Drawing")

    def dialog():
        p = panel_of("CreateDrawingPanel")
        if not h.check("%s: Create Drawing dialog" % prefix, p is not None, panel()):
            return
        if contents:
            choose(p.contents, contents)
        for label in untick:
            for i in range(p.bodies.count()):
                item = p.bodies.item(i)
                if item.text() == label:
                    rect = p.bodies.visualItemRect(item)
                    wi.click(p.bodies.viewport(), QtCore.QPoint(rect.left() + 8, rect.center().y()))
                    if item.checkState() != QtCore.Qt.Unchecked:
                        item.setCheckState(QtCore.Qt.Unchecked)
        if standard:
            choose(p.standard, standard)
        if units:
            choose(p.units, units)
        if sheet:
            choose(p.sheet, sheet)
        if views:
            choose(p.views, views)

    def accept():
        ok()

    accept.wait_ms = 2500

    def opened():
        count = len(drawing_module().drawings(App.ActiveDocument))
        h.check("%s: a new drawing" % prefix, count == state["before"] + 1, count)
        h.check("%s: its tab is active" % prefix, page() is not None)

    steps = [new_drawing, dialog, accept, opened]
    if base_at is not None:

        def place():
            move_to(base_at[0] + 10, base_at[1] + 10)
            click_at(*base_at)

        def options():
            p = panel_of("BaseViewPanel")
            if not h.check("%s: Base View dialog" % prefix, p is not None, panel()):
                return
            if orientation:
                choose(p.orientation, orientation)
            if style:
                choose(p.style, style)
            if scale:
                set_combo_text(p.scale, scale)

        options.wait_ms = 1200

        def base_ok():
            ok()

        base_ok.wait_ms = 2000

        def placed():
            found = bases()
            h.check("%s: one base view more" % prefix, len(found) >= 1, found)

        steps += [place, options, base_ok, placed]
    for step in steps:
        step.__name__ = "%s_%s" % (prefix, step.__name__)
    return steps


def previews_left():
    """Preview items (the orange outlines and lines a command draws while picking) still
    on the sheet."""
    from sciforge import drawing_ui

    view = gv()
    if view is None:
        return 0
    count = 0
    for item in view.scene().items():
        pen = getattr(item, "pen", None)
        colour = pen().color().name() if callable(pen) else ""
        if item.data(drawing_ui.OVERLAY_KEY) == drawing_ui.OVERLAY_KEY:
            count += 1
        elif colour == drawing_ui.OVERLAY_COLOR:
            count += 1
    return count


def drag_page(a, b, steps=12):
    """Press at page point a, move to b, release (a person dragging a view)."""
    view = gv()
    if view is None:
        h.check("a drawing tab is active", False)
        return
    start = widget_point(*a)
    end = widget_point(*b)
    wi.drag(view.viewport(), start, view.viewport().mapToGlobal(end), steps)
    _process()
