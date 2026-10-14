# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shared steps and checks for the INSPECT analysis and navigation bar scenarios
(scenarios/inspect_analysis_*.py, scenarios/navbar_*.py). Everything acts like a person:
ribbon menus, the navigation bar's drop-downs, clicks and drags in the 3D view, typing into
the dialogs, the browser's eyes and menus. Not a scenario itself.

The part: the 40 x 30 x 10 box (blend_steps.box_steps) with its four top edges rounded
r = 4 (Fillet, real clicks). Its faces: 6 flat, 4 cylindrical rounds (Gaussian curvature 0,
principal curvatures 0 and 1/4; at the corners two rounds meet in a mitre).

Pixel checks read the screen (QScreen.grabWindow works under xvfb) inside the part's
outline, leaving out the task dialog floating over the view.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import widget_input as w

V = App.Vector
R = 4.0
TOP_EDGES = [V(20, 0, 10), V(40, 15, 10), V(20, 30, 10), V(0, 15, 10)]
TOP_FACE = V(20, 15, 10)
FRONT_FACE = V(20, 0, 4)
RIGHT_FACE = V(40, 15, 4)
FRONT_ROUND = V(20, R * (1 - math.cos(math.radians(45))), 10 - R * (1 - math.sin(math.radians(45))))


def filleted_volume(r=R):
    return b.BOX - (40 + 30 + 40 + 30) * b.spandrel(r) + 4 * b.corner(r)


def filleted_block_steps(name):
    """Steps: the box with real input, then Fillet (F) on its four top edges, r = 4."""

    def fillet():
        Gui.Selection.clearSelection()
        h.fit()
        h.press("f")

    def edge_step(point):
        def pick_edge():
            h.click_edge(point)

        return pick_edge

    def radius():
        p = b.blend_panel()
        h.check("Fillet dialog with four edges", p is not None and len(p.refs) == 4, p and p.refs)
        if p is not None:
            b.type_into(p.radius.widget, "%g" % R)

    def ok():
        h.task_button("OK")

    def made():
        v = h.solid_volume()
        h.check("filleted block made", b.close(v, filleted_volume(), 1e-5), (v, filleted_volume()))
        faces = len(h.body().Shape.Faces)
        h.check("10 faces (6 flat, 4 rounds)", faces == 10, faces)
        h.fit()

    edges = [edge_step(p) for p in TOP_EDGES]
    return b.box_steps(name) + [fillet] + edges + [radius, ok, made]


# -- the dialog ----------------------------------------------------------------------------------
def panel():
    from sciforge import surface_analysis_ui as ui

    p = ui.AnalysisPanel.last
    if p is None or p._closed:
        return None
    return p


def analyses(kind=None):
    from sciforge import surface_analysis as sa

    return sa.analyses(App.ActiveDocument, kind) if App.ActiveDocument else []


def inspect(label):
    """INSPECT > `label` in the ribbon menu, with the mouse."""
    from SciForgeTests.gui import sketch_input as si

    h.click_empty()
    return si.menu_item("INSPECT", label)


def set_combo(combo, text):
    """Choose `text` in a drop-down with the keyboard, as a person can."""
    index = combo.findText(text)
    h.check("the list has %s" % text, index >= 0, [combo.itemText(i) for i in range(combo.count())])
    if index < 0:
        return
    w.click(combo)
    QtWidgets.QApplication.processEvents()
    popup = QtWidgets.QApplication.activePopupWidget()
    view = combo.view()
    if popup is not None and view is not None and view.isVisible():
        rect = view.visualRect(view.model().index(index, 0))
        QtTest.QTest.mouseClick(
            view.viewport(), QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, rect.center()
        )
    else:
        combo.setCurrentIndex(index)
    QtWidgets.QApplication.processEvents()
    if combo.currentIndex() != index:  # the list did not take the click: keys
        combo.setFocus()
        while combo.currentIndex() < index:
            QtTest.QTest.keyClick(combo, QtCore.Qt.Key_Down)
        while combo.currentIndex() > index:
            QtTest.QTest.keyClick(combo, QtCore.Qt.Key_Up)
    QtWidgets.QApplication.processEvents()


def type_spin(box, value):
    """Type a number into a spin box and press Enter."""
    box.setFocus()
    w.click(box)
    QtTest.QTest.keyClick(box, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
    QtTest.QTest.keyClicks(box, str(value))
    QtTest.QTest.keyClick(box, QtCore.Qt.Key_Tab)
    QtWidgets.QApplication.processEvents()


def slide(slider, value):
    """Move a slider to `value` with the keyboard (Page Up / Down, arrows)."""
    slider.setFocus()
    w.click(slider)
    QtWidgets.QApplication.processEvents()
    for _i in range(400):
        if slider.value() == value:
            break
        key = QtCore.Qt.Key_Right if slider.value() < value else QtCore.Qt.Key_Left
        QtTest.QTest.keyClick(slider, key)
    QtWidgets.QApplication.processEvents()


def tick(box, on=True):
    if box.isChecked() != on:
        w.click(box, QtCore.QPoint(8, box.height() // 2))
    QtWidgets.QApplication.processEvents()


# -- pixels ---------------------------------------------------------------------------------------
def _dialog_rects():
    rects = []
    main = Gui.getMainWindow()
    for widget in main.findChildren(QtWidgets.QWidget):
        try:
            name = widget.metaObject().className()
            if name in ("Gui::TaskView::TaskView", "Gui::TaskView::TaskBox") and widget.isVisible():
                top = widget.mapToGlobal(QtCore.QPoint(0, 0))
                rects.append(QtCore.QRect(top, widget.size()))
        except RuntimeError:
            continue
    return rects


def part_rect(obj=None, margin=0):
    """Global screen rectangle of the part (its box's corners) in the 3D view."""
    shape = (obj or h.body()).Shape
    box = shape.BoundBox
    gl = h.gl_widget()
    xs, ys = [], []
    for x in (box.XMin, box.XMax):
        for y in (box.YMin, box.YMax):
            for z in (box.ZMin, box.ZMax):
                p = h.screen_point(V(x, y, z))
                g = gl.mapToGlobal(p)
                xs.append(g.x())
                ys.append(g.y())
    top = gl.mapToGlobal(QtCore.QPoint(0, 0))
    left = max(min(xs) - margin, top.x())
    right = min(max(xs) + margin, top.x() + gl.width() - 1)
    upper = max(min(ys) - margin, top.y())
    lower = min(max(ys) + margin, top.y() + gl.height() - 1)
    return QtCore.QRect(QtCore.QPoint(left, upper), QtCore.QPoint(right, lower))


def classify(r, g, b_):
    """A rough name for a screen colour."""
    if abs(r - 42) <= 4 and abs(g - 42) <= 4 and abs(b_ - 42) <= 4:
        return "background"
    if r < 40 and g < 40 and b_ < 40:
        return "black"
    if r > 215 and g > 215 and b_ > 215:
        return "white"
    if max(r, g, b_) - min(r, g, b_) < 18:
        return "grey"
    if r > 170 and g < 110 and b_ < 110:
        return "red"
    if r > 170 and g > 140 and b_ < 110:
        return "yellow"
    if r > 170 and 90 <= g <= 160 and b_ < 90:
        return "orange"
    if g > 120 and r < 140 and b_ < 140 and g > r + 20 and g > b_ + 20:
        return "green"
    if b_ > 150 and r < 140 and b_ > r + 40:
        return "blue"
    if r > 120 and b_ > 150 and g < 120:
        return "violet"
    return "other"


def colors(rect=None, step=3):
    """{colour name: count} of the screen inside `rect` (default: the part), without the
    task dialog."""
    rect = rect or part_rect()
    image = QtWidgets.QApplication.primaryScreen().grabWindow(0).toImage()
    skip = _dialog_rects()
    counts = {}
    for y in range(rect.top(), rect.bottom(), step):
        for x in range(rect.left(), rect.right(), step):
            if any(r.contains(x, y) for r in skip):
                continue
            c = image.pixelColor(x, y)
            name = classify(c.red(), c.green(), c.blue())
            counts[name] = counts.get(name, 0) + 1
    return counts


def share(counts, *names):
    total = float(sum(counts.values())) or 1.0
    return sum(counts.get(n, 0) for n in names) / total


def color_at(point):
    """The screen colour (r, g, b) at a 3D point."""
    gl = h.gl_widget()
    g = gl.mapToGlobal(h.screen_point(point))
    image = QtWidgets.QApplication.primaryScreen().grabWindow(0).toImage()
    c = image.pixelColor(g.x(), g.y())
    return c.red(), c.green(), c.blue()


def name_at(point):
    return classify(*color_at(point))


# -- the browser ------------------------------------------------------------------------------
def open_analysis_folder():
    """Open the browser's Analysis folder (and the design's row above it) like a person with
    the keyboard: click the row, press Right."""
    from SciForgeTests.gui import timeline_input as ti

    t = ti.tree()
    item = t.row("Analysis")
    if item is None:
        h.check("the browser has an Analysis folder", False, ti.labels())
        return False
    chain = []
    while item is not None:
        chain.insert(0, item)
        item = item.parent()
    for row in chain:
        if row.isExpanded():
            continue
        t = ti.tree()
        if not t.visualItemRect(row).isValid():
            h.check("the row %s can be seen" % row.text(1), False)
            return False
        w.click(t.viewport(), t.label_point(row))
        w.key(t, QtCore.Qt.Key_Right)
    return True


def model_faces_shown(body=None):
    """True when the model's own faces are drawn (no analysis covers them)."""
    from sciforge import surface_analysis_ui as ui
    from pivy import coin

    body = body or h.body()
    for feature in ui._displays(body):
        for node in ui._face_styles(feature):
            if node.style.getValue() == coin.SoDrawStyle.INVISIBLE:
                return False
    return True


def save_reopen(path_name):
    """Save the design to a file in the test folder, close it, open it again."""
    import os

    path = os.path.join(h.OUT_DIR, path_name)
    if os.path.exists(path):
        os.remove(path)
    App.ActiveDocument.saveAs(path)
    App.closeDocument(App.ActiveDocument.Name)
    QtWidgets.QApplication.processEvents()
    App.openDocument(path)
    QtWidgets.QApplication.processEvents()
    h.fit()
    return path
