# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Data Panel, part 2 (Luca's requests of 2026-10-23: "a more robust data panel,
similar to how Fusion does it" and "drag files from the data panel into open files ...
a copy of the file"; docs/sciforge/parity/versions.md "Data Panel, part 2").

A project folder with the folders Parts and Robots; Parts/Wheel (a 10 mm cube, v1 and v2),
Arm (v1), Cart (inserts Wheel, v1 and v2), Robot (two components: Base, a 20 mm cube, and Gripper,
a 5 mm cube). An open design "Target" with a plate.
P1  The cards: folders first, then the designs with their pictures and version badges.
P2  Sort by Last saved (the drop-down, by keyboard): newest first; back to Name; the
    choice is remembered.
P3  Search "whe": Wheel from the Parts folder ("in Parts"); Esc brings the folder back.
P4  The list view and back to the grid.
P5  Details: a click on Cart shows its picture, Open, Insert, its version and Uses (Wheel);
    in Parts, Wheel's two versions (newest first) and Used In (Cart); the X closes them.
P6  Dragging the Robot card starts a drag that carries Robot's file; dropped on Target's 3D
    view, a copy comes in: one component "Robot" with Base and Gripper and both cubes, no
    link to Robot's file, Robot not left open, FreeCAD's own file drop never runs; the
    Move dialog places it (Cancel: where it came in); Ctrl+Z takes it out. A drop on the
    ribbon is refused.
P7  Arm dropped on the design's row in the browser: a copy in the design.
P8  Cart dropped on the Robots folder card: it moves there (its link to Wheel follows).
P9  A design dropped on the panel from the file manager is copied into the folder.
P10 A file put into the folder by another program shows by itself a few seconds later.
P11 Keys: Enter opens a folder, Backspace goes up.
"""

import os
import shutil
import tempfile
import time

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import polish2_steps as p2
from SciForgeTests.gui import widget_input as wi

s = {}


def ui():
    from sciforge import versions_ui

    return versions_ui


def dpu():
    from sciforge import data_panel_ui

    return data_panel_ui


def panel():
    return ui().panel()


def texts():
    return [text for _kind, _path, text in panel().items()] if panel() else []


def card(text_start):
    lst = panel().list
    for i in range(lst.count()):
        if lst.item(i).text().startswith(text_start):
            return lst.item(i)
    return None


def click_card(text_start):
    item = card(text_start)
    if not h.check("a card %s" % text_start, item is not None, texts()):
        return None
    lst = panel().list
    lst.scrollToItem(item)
    wi.click(lst.viewport(), lst.visualItemRect(item).center())
    return item


def double_click_card(text_start):
    item = card(text_start)
    if not h.check("a card %s" % text_start, item is not None, texts()):
        return
    lst = panel().list
    wi.double_click(lst.viewport(), lst.visualItemRect(item).center())


def target():
    return App.getDocument(s["target"])


def add_box(document, body, size):
    box = document.addObject("PartDesign::AdditiveBox", body.Name + "Box")
    body.addObject(box)
    box.Length = box.Width = box.Height = size
    return box


def setup():
    Gui.activateWorkbench("SciForgeWorkbench")
    from sciforge import components

    s["project"] = tempfile.mkdtemp(prefix="sciforge-project-")
    p2.set_project(s["project"])
    for folder in ("Parts", "Robots"):
        os.makedirs(os.path.join(s["project"], folder))
    wheel = App.newDocument("Wheel")
    body = p2.make_box(wheel, "Body", 10, 10, 10)
    s["wheel"] = os.path.join(s["project"], "Parts", "Wheel.FCStd")
    p2.save_new(wheel, s["wheel"])
    body.Group[0].Length = 10.0001
    wheel.recompute()
    body.Group[0].Length = 10
    wheel.recompute()
    wheel.save()
    p2.process()
    arm = App.newDocument("Arm")
    p2.make_box(arm, "Body", 30, 10, 10)
    s["arm"] = os.path.join(s["project"], "Arm.FCStd")
    p2.save_new(arm, s["arm"])
    time.sleep(1.1)  # (Cart saved a second later: sorting by date sees it)
    cart = App.newDocument("Cart")
    p2.make_box(cart, "Frame", 40, 20, 2)
    s["cart"] = os.path.join(s["project"], "Cart.FCStd")
    p2.save_new(cart, s["cart"])
    from sciforge import design_insert

    design_insert.insert_linked(cart, wheel)
    cart.save()
    robot = App.newDocument("Robot")
    base = components.new_component(robot, "Base", None)
    add_box(robot, components.new_body_in(robot, base, label="Block"), 20)
    gripper = components.new_component(robot, "Gripper", None)
    jaw = components.new_body_in(robot, gripper, label="Jaw")
    add_box(robot, jaw, 5)
    jaw.Placement = App.Placement(App.Vector(30, 0, 0), App.Rotation())
    robot.recompute()
    time.sleep(1.1)  # (Robot is the newest, a second after Cart's second save)
    s["robot"] = os.path.join(s["project"], "Robot.FCStd")
    p2.save_new(robot, s["robot"])
    p2.process()
    for name in list(App.listDocuments()):
        Gui.getDocument(name).Modified = False
        App.closeDocument(name)
    document = App.newDocument("Target")
    s["target"] = document.Name
    p2.make_box(document, "Plate", 50, 50, 5)
    h.fit()
    ui().show_panel()


setup.wait_ms = 2500


# -- P1 -----------------------------------------------------------------------------------------
def p1_cards():
    listed = texts()
    h.check(
        "P1 folders first, then the designs by name",
        listed == ["Parts", "Robots", "Arm  v1", "Cart  v2", "Robot  v1"],
        listed,
    )
    item = card("Arm")
    h.check(
        "P1 Arm's card has the badge V1",
        item is not None and item.data(dpu().ROLE_BADGE) == "V1",
        item and item.data(dpu().ROLE_BADGE),
    )
    h.check("P1 and its picture", panel().has_thumbnail(s["arm"]))
    h.shot("P1-cards")


# -- P2 -----------------------------------------------------------------------------------------
def p2_sort():
    box = panel().sort_box
    box.setFocus()
    QtTest.QTest.keyClick(box, QtCore.Qt.Key_Down)  # Name -> Last saved
    QtWidgets.QApplication.processEvents()


p2_sort.wait_ms = 800


def p2_sorted():
    listed = texts()
    h.check(
        "P2 Last saved: newest first (folders stay first)",
        listed[:2] == ["Parts", "Robots"] and listed[2:] == ["Robot  v1", "Cart  v2", "Arm  v1"],
        listed,
    )
    remembered = App.ParamGet(ui().PREFS).GetString("DataPanelSort", "")
    h.check("P2 remembered", remembered == "modified", remembered)
    panel().set_sort("name")
    h.check("P2 back to Name", texts()[2:] == ["Arm  v1", "Cart  v2", "Robot  v1"], texts())


# -- P3 -----------------------------------------------------------------------------------------
def p3_search():
    field = panel().search
    wi.click(field)
    QtTest.QTest.keyClicks(field, "whe")
    QtWidgets.QApplication.processEvents()


p3_search.wait_ms = 900


def p3_found():
    found = panel().items()
    h.check(
        "P3 'whe' finds Wheel in Parts",
        [(k, os.path.normcase(p), t) for k, p, t in found]
        == [("design", os.path.normcase(s["wheel"]), "Wheel  v2")],
        found,
    )
    item = card("Wheel")
    h.check(
        "P3 its card says where it is",
        item is not None and item.data(dpu().ROLE_SHORT) == "in Parts",
        item and item.data(dpu().ROLE_SHORT),
    )
    h.check("P3 the status", panel().status.text() == '1 found for "whe"', panel().status.text())
    h.shot("P3-search")
    QtTest.QTest.keyClick(panel().search, QtCore.Qt.Key_Escape)


p3_found.wait_ms = 800


def p3_cleared():
    h.check("P3 Esc: the search is empty", panel().search.text() == "")
    h.check("P3 and the folder is back", texts()[:2] == ["Parts", "Robots"], texts())


# -- P4 -----------------------------------------------------------------------------------------
def p4_list():
    wi.click(panel().view_toggle)
    h.check("P4 the list view", panel().list.viewMode() == QtWidgets.QListView.ListMode, "grid")
    h.shot("P4-list")
    wi.click(panel().view_toggle)
    h.check("P4 back to the grid", panel().list.viewMode() == QtWidgets.QListView.IconMode, "list")


# -- P5 -----------------------------------------------------------------------------------------
def details():
    return panel().details


def rows(widget):
    return [widget.item(i).text() for i in range(widget.count())]


def p5_cart():
    click_card("Cart")


p5_cart.wait_ms = 800


def p5_cart_details():
    d = details()
    h.check("P5 the details show", d.isVisible())
    h.check("P5 Cart's name", d.name.text() == "Cart", d.name.text())
    h.check("P5 its picture", not d.picture.pixmap().isNull())
    h.check("P5 Open and Insert", d.open_button.isVisible() and d.insert_button.isVisible())
    versions = rows(d.versions)
    h.check(
        "P5 its versions, newest first",
        len(versions) == 2 and versions[0].startswith("V2") and versions[1].startswith("V1"),
        versions,
    )
    h.check("P5 Uses: Wheel", rows(d.uses) == ["Wheel"], rows(d.uses))
    h.check("P5 the Uses tab counts it", d.tabs.tabText(1) == "Uses (1)", d.tabs.tabText(1))
    h.shot("P5-details")
    double_click_card("Parts")


p5_cart_details.wait_ms = 800


def p5_wheel():
    click_card("Wheel")


p5_wheel.wait_ms = 800


def p5_wheel_details():
    d = details()
    versions = rows(d.versions)
    h.check(
        "P5 Wheel: V2 then V1",
        len(versions) == 2 and versions[0].startswith("V2") and versions[1].startswith("V1"),
        versions,
    )
    bar = d.tabs.tabBar()
    wi.click(bar, bar.tabRect(2).center())
    h.check("P5 Used In: Cart", rows(d.used_in) == ["Cart"], rows(d.used_in))
    wi.click(d.close_button)
    h.check("P5 the X closes the details", not d.isVisible())
    wi.click(panel().up)


p5_wheel_details.wait_ms = 800


# -- P6 -----------------------------------------------------------------------------------------
def p6_drag():
    item = card("Robot  ")  # (not the Robots folder)
    if not h.check("P6 the Robot card", item is not None, texts()):
        return
    carried = []
    dpu().DRAG_HOOK = carried.append
    try:
        lst = panel().list
        lst.scrollToItem(item)
        start = lst.visualItemRect(item).center()
        wi.drag(lst.viewport(), start, h.gl_widget().mapToGlobal(h.gl_widget().rect().center()))
    finally:
        dpu().DRAG_HOOK = None
    h.check(
        "P6 dragging the card carries Robot's file",
        [[os.path.normcase(p) for p in c] for c in carried] == [[os.path.normcase(s["robot"])]],
        carried,
    )


def _send(widget, kind, pos, mime):
    actions = QtCore.Qt.CopyAction | QtCore.Qt.MoveAction
    if kind == "enter":
        event = QtGui.QDragEnterEvent(pos, actions, mime, QtCore.Qt.LeftButton, wi.NONE)
    elif kind == "move":
        event = QtGui.QDragMoveEvent(pos, actions, mime, QtCore.Qt.LeftButton, wi.NONE)
    else:
        event = QtGui.QDropEvent(QtCore.QPointF(pos), actions, mime, QtCore.Qt.LeftButton, wi.NONE)
    event.ignore()
    QtWidgets.QApplication.sendEvent(widget, event)
    return event.isAccepted()


def drop(widget, pos, paths, session=True):
    """What the window system delivers for a drop of `paths` dragged out of the panel:
    enter, move, drop on `widget` at `pos` (while the panel's drag watch runs)."""
    mime = dpu().make_mime(paths)
    watch = dpu().DropSession() if session else None
    try:
        accepted = [_send(widget, k, pos, mime) for k in ("enter", "move", "drop")]
    finally:
        pending = watch.finish() if watch is not None else None
    return accepted, pending


def p6_drop():
    from sciforge import design_insert

    s["objects"] = len(target().Objects)
    ribbon = Gui.getMainWindow().findChild(QtWidgets.QWidget, "SciForgeRibbon")
    if ribbon is not None:
        accepted, pending = drop(ribbon, QtCore.QPoint(20, 20), [s["robot"]])
        h.check("P6 the ribbon refuses the drop", accepted == [False] * 3 and pending is None)
    gl = h.gl_widget()
    watch = dpu().DropSession()
    try:
        h.check("P6 while a card is dragged, the 3D view takes drops", gl.acceptDrops())
    finally:
        watch.finish()
    accepted, pending = drop(gl, gl.rect().center(), [s["robot"]])
    h.check("P6 the 3D view takes the drop", accepted == [True] * 3, accepted)
    h.check("P6 a copy is asked for", pending is not None and pending[0] == "view", pending)
    h.check("P6 (design_insert can copy)", hasattr(design_insert, "insert_copy"))


p6_drop.wait_ms = 3000


def comps(document):
    from sciforge import components

    return {c.Label: c for c in components.list_components(document)}


def p6_copied():
    from sciforge import components, design_insert

    document = target()
    found = comps(document)
    robot = found.get("Robot")
    h.check("P6 a component Robot", robot is not None, list(found))
    if robot is None:
        return
    inner = sorted(c.Label for c in found.values() if components.container_of(c) is robot)
    h.check("P6 with Base and Gripper in it", inner == ["Base", "Gripper"], inner)
    volumes = sorted(
        round(b.Shape.Volume) for b in components.bodies_in(document, robot, recursive=True)
    )
    h.check("P6 and both cubes", volumes == [125, 8000], volumes)
    h.check(
        "P6 not linked to Robot's file",
        not design_insert.is_linked(robot)
        and not any(design_insert.is_copy_feature(o) for o in document.Objects),
    )
    h.check(
        "P6 Robot is not left open",
        not any(
            os.path.normcase(App.getDocument(n).FileName) == os.path.normcase(s["robot"])
            for n in App.listDocuments()
        ),
        list(App.listDocuments()),
    )
    h.check(
        "P6 FreeCAD's own file drop did not merge anything",
        not any(o.Label.startswith("Unnamed") for o in document.Objects),
    )
    from sciforge import component_move_ui

    h.check("P6 the Move dialog places it", Gui.Control.activeDialog(), component_move_ui)
    h.shot("P6-copied")
    h.task_button("Cancel")  # leaves it where it came in


p6_copied.wait_ms = 1200


def p6_undo():
    h.check("P6 Cancel closed the Move dialog", not Gui.Control.activeDialog())
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


p6_undo.wait_ms = 1200


def p6_undone():
    h.check("P6 Ctrl+Z takes the copy out", "Robot" not in comps(target()), list(comps(target())))


# -- P7 -----------------------------------------------------------------------------------------
def p7_browser():
    from sciforge import browser_ui

    tree = browser_ui.widget()
    tree.refresh(force=True)
    item = tree.item_for("document")
    pos = tree.label_point(item)
    accepted, pending = drop(tree.viewport(), pos, [s["arm"]])
    h.check("P7 the browser takes the drop", accepted == [True] * 3, accepted)
    h.check("P7 a copy is asked for", pending is not None and pending[0] == "browser", pending)


p7_browser.wait_ms = 3000


def p7_copied():
    found = comps(target())
    h.check("P7 a component Arm in Target", "Arm" in found, list(found))
    if Gui.Control.activeDialog():
        h.task_button("Cancel")


p7_copied.wait_ms = 800


# -- P8 -----------------------------------------------------------------------------------------
def p8_move():
    lst = panel().list
    folder = card("Robots")
    if not h.check("P8 the Robots card", folder is not None, texts()):
        return
    pos = lst.visualItemRect(folder).center()
    accepted, _pending = drop(lst.viewport(), pos, [s["cart"]], session=False)
    h.check("P8 the folder card takes Cart", accepted == [True] * 3, accepted)


p8_move.wait_ms = 2500


def p8_moved():
    from sciforge import versions

    moved = os.path.join(s["project"], "Robots", "Cart.FCStd")
    h.check("P8 Cart is in Robots now", os.path.isfile(moved) and not os.path.exists(s["cart"]))
    h.check("P8 its card is gone from here", card("Cart") is None, texts())
    h.check(
        "P8 its link to Wheel follows",
        os.path.isfile(moved) and 'file="../Parts/Wheel.FCStd"' in versions.read_design_xml(moved),
    )
    s["cart"] = moved


# -- P9 -----------------------------------------------------------------------------------------
def p9_outside():
    gear = App.newDocument("Gear")
    p2.make_box(gear, "Body", 8, 8, 8)
    s["outside"] = tempfile.mkdtemp(prefix="sciforge-outside-")
    path = os.path.join(s["outside"], "Gear.FCStd")
    gear.saveAs(path)
    App.closeDocument(gear.Name)
    App.setActiveDocument(s["target"])
    mime = QtCore.QMimeData()
    mime.setUrls([QtCore.QUrl.fromLocalFile(path)])
    lst = panel().list
    empty = QtCore.QPoint(lst.viewport().width() - 10, lst.viewport().height() - 10)
    accepted = [_send(lst.viewport(), k, empty, mime) for k in ("enter", "move", "drop")]
    h.check("P9 the panel takes a file from outside", accepted == [True] * 3, accepted)


p9_outside.wait_ms = 2500


def p9_uploaded():
    copied = os.path.join(s["project"], "Gear.FCStd")
    h.check("P9 Gear is copied into the folder", os.path.isfile(copied))
    h.check("P9 and listed", card("Gear") is not None, texts())
    h.check(
        "P9 the original stays where it was",
        os.path.isfile(os.path.join(s["outside"], "Gear.FCStd")),
    )


# -- P10 ----------------------------------------------------------------------------------------
def p10_elsewhere():
    shutil.copy(s["arm"], os.path.join(s["project"], "Arm Spare.FCStd"))


p10_elsewhere.wait_ms = 6000


def p10_shown():
    h.check("P10 a file put there by another program shows", card("Arm Spare") is not None, texts())


# -- P11 ----------------------------------------------------------------------------------------
def p11_enter():
    click_card("Robots")
    QtTest.QTest.keyClick(panel().list, QtCore.Qt.Key_Return)


p11_enter.wait_ms = 800


def p11_inside():
    h.check("P11 Enter opens the folder", "Robots" in panel().crumbs.text(), panel().crumbs.text())
    h.check("P11 Cart is in it", [t for t in texts() if t.startswith("Cart")] != [], texts())
    panel().list.setFocus()
    QtTest.QTest.keyClick(panel().list, QtCore.Qt.Key_Backspace)


p11_inside.wait_ms = 800


def p11_up():
    h.check("P11 Backspace goes up", texts()[:2] == ["Parts", "Robots"], texts())


def cleanup():
    ui().hide_panel()
    for name in list(App.listDocuments()):
        Gui.getDocument(name).Modified = False
        App.closeDocument(name)
    App.ParamGet(ui().PREFS).RemString("ProjectFolder")
    App.ParamGet(ui().PREFS).RemString("DataPanelSort")
    App.ParamGet(ui().PREFS).RemBool("DataPanelList")
    shutil.rmtree(s["project"], ignore_errors=True)
    shutil.rmtree(s.get("outside", ""), ignore_errors=True)


h.run(
    "data_panel_fusion",
    [
        setup,
        p1_cards,
        p2_sort,
        p2_sorted,
        p3_search,
        p3_found,
        p3_cleared,
        p4_list,
        p5_cart,
        p5_cart_details,
        p5_wheel,
        p5_wheel_details,
        p6_drag,
        p6_drop,
        p6_copied,
        p6_undo,
        p6_undone,
        p7_browser,
        p7_copied,
        p8_move,
        p8_moved,
        p9_outside,
        p9_uploaded,
        p10_elsewhere,
        p10_shown,
        p11_enter,
        p11_inside,
        p11_up,
        cleanup,
    ],
)
