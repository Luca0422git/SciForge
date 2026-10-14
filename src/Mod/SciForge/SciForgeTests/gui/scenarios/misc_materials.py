# SPDX-License-Identifier: LGPL-2.1-or-later
"""Manage Materials (MODIFY > Manage Materials): Fusion's Material Browser, only real input
(docs/sciforge/parity/misc.md). A body: a box 40 x 30 x 10 (12 cm³), no material yet.

P1 MODIFY > Manage Materials: the Material Browser with Physical and Appearance tabs; the
   Physical tab: In This Design (Steel, the default, 1 body), Favorites, the Library by group,
   My Materials.
P2 Aluminium picked in the Library: its density 2.7 g/cm³ and other values shown; the star adds
   it to Favorites (listed there); again: removed.
P3 The body selected in the 3D view, Assign to Selection: the body is Aluminium (32.4 g); In
   This Design says so; Ctrl+Z: Steel again.
P4 New Material from PLA: "My PETG", 1.27 g/cm³, Create: in My Materials, in FreeCAD's User
   library, offered by Physical Material too; assigned: the body weighs 15.24 g.
P5 New Material called "Steel" or with density 0: refused with the reason.
P6 Delete My PETG: gone from the list; the body keeps it.
P7 Appearance tab: New Appearance "Signal Blue" #2050c0: in My Appearances; assigned to the
   body: its look; the search "blue" lists only blue entries.
P8 The body keeps its own material in the design (name, density). A design from another
   computer (its body made of "Lost Nylon", 1.14 g/cm³, which this one never had): opened,
   the material is made again in My Materials and the body is Lost Nylon (13.68 g), its look
   still Signal Blue, the design not changed by it. Deleted My PETG: the name can be used again.
"""

import os

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import misc_steps as m
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import widget_input as w

V = App.Vector
s = {}


def browser():
    from sciforge import materials_ui

    d = materials_ui.MaterialBrowser.last
    try:
        return d if d is not None and d.isVisible() else None
    except RuntimeError:
        return None


def tab(kind):
    d = browser()
    return getattr(d, kind) if d is not None else None


def group_names(t):
    return [t.tree.topLevelItem(r).text(0) for r in range(t.tree.topLevelItemCount())]


def leaves(t, under):
    return [i.text(0) for i in t.items(under=under)]


def click_entry(t, label, under="Library"):
    for item in t.items(under=under):
        if item.text(0) == label or item.text(0).startswith(label + " ("):
            t.tree.scrollToItem(item)
            m.process()
            rect = t.tree.visualItemRect(item)
            w.click(t.tree.viewport(), rect.center())
            return item
    h.check("listed under %s: %s" % (under, label), False, leaves(t, under))
    return None


def press(name):
    d = browser()
    button = m.find_child(d, name)
    if h.check("button %s" % name, button is not None and button.isEnabled()):
        w.click(button)
        m.process()


def message():
    d = browser()
    return d.message.text() if d is not None else ""


def body():
    return App.ActiveDocument.getObject(s["body"])


def setup():
    from sciforge import commands, extrude, material, sketch_ui

    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Materials")
    b = commands.ensure_body()
    planes = sketch_ui.origin_planes(b)
    sk = sketch_ui.create_sketch(b, (planes["XY_Plane"], ""))
    h.draw_rectangle(sk, 0, 0, 40, 30)
    extrude.make(b, sk, {"distance": 10.0})
    App.ActiveDocument.recompute()
    s["body"] = b.Name
    h.fit()
    for row in material.user_entries():  # a profile left from an earlier run
        material.delete_user_material(row["key"])


# -- P1 ----------------------------------------------------------------------------------------
def p1_open():
    si.menu_item("MODIFY", "Manage Materials")


p1_open.wait_ms = 1500


def p1_check():
    d = browser()
    h.check(
        "P1 the Material Browser",
        d is not None and d.windowTitle() == "Material Browser",
        h.popups(),
    )
    if d is None:
        return
    tabs = [d.tabs.tabText(i) for i in range(d.tabs.count())]
    h.check("P1 Physical and Appearance tabs", tabs == ["Physical", "Appearance"], tabs)
    t = tab("physical")
    h.check(
        "P1 its sections",
        group_names(t) == ["In This Design", "Favorites", "Library", "My Materials"],
        group_names(t),
    )
    h.check(
        "P1 In This Design: Steel (default), 1 body",
        leaves(t, "In This Design") == ["Steel (default) (1)"],
        leaves(t, "In This Design"),
    )
    groups = [
        t.tree.topLevelItem(2).child(i).text(0) for i in range(t.tree.topLevelItem(2).childCount())
    ]
    h.check("P1 the Library by group", groups == ["Metal", "Plastic", "Other"], groups)
    h.shot("1-browser")


# -- P2 ----------------------------------------------------------------------------------------
def p2_pick():
    t = tab("physical")
    click_entry(t, "Aluminium")
    density = m.find_child(browser(), "SciForgeMaterialValue_Density").text()
    h.check("P2 Aluminium's density shown", density.startswith("2.7"), density)
    young = m.find_child(browser(), "SciForgeMaterialValue_YoungsModulus").text()
    h.check("P2 and its other values", young not in ("", "-"), young)
    press("SciForgeMaterialFavorite_physical")


def p2_favorite():
    t = tab("physical")
    h.check(
        "P2 Aluminium is a favourite",
        leaves(t, "Favorites") == ["Aluminium"],
        leaves(t, "Favorites"),
    )
    click_entry(t, "Aluminium", "Favorites")
    press("SciForgeMaterialFavorite_physical")
    h.check("P2 removed again", leaves(t, "Favorites") == [], leaves(t, "Favorites"))


# -- P3 ----------------------------------------------------------------------------------------
def p3_assign():
    t = tab("physical")
    click_entry(t, "Aluminium")
    Gui.Selection.clearSelection()
    h.click(V(20, 15, 10))  # the body's top face (the browser floats to the side)
    m.process()
    h.check(
        "P3 the body is selected",
        any(
            sel.Object.Name == s["body"]
            or getattr(sel.Object, "getParentGeoFeatureGroup", lambda: None)() is body()
            for sel in Gui.Selection.getSelectionEx()
        ),
        [x.ObjectName for x in Gui.Selection.getSelectionEx()],
    )
    press("SciForgeMaterialAssign_physical")


def p3_check():
    from sciforge import material

    label, _rho = material.effective(body())
    h.check("P3 the body is Aluminium", label == "Aluminium", label)
    grams = material.mass(body()) * 1000.0
    h.check("P3 32.4 g", m.near(grams, 32.4, 0.05), grams)
    t = tab("physical")
    h.check(
        "P3 In This Design says so",
        leaves(t, "In This Design") == ["Aluminium (1)"],
        leaves(t, "In This Design"),
    )
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


p3_check.wait_ms = 1000


def p3_undone():
    from sciforge import material

    label, _rho = material.effective(body())
    h.check("P3 Ctrl+Z: Steel again", label.startswith("Steel"), label)


# -- P4 ----------------------------------------------------------------------------------------
def p4_new():
    t = tab("physical")
    t.fill()
    click_entry(t, "PLA")
    press("SciForgeMaterialNew_physical")
    h.check("P4 based on PLA", t.based_on.text() == "PLA", t.based_on.text())
    name = m.find_child(browser(), "SciForgeMaterialNewName_physical")
    value = m.find_child(browser(), "SciForgeMaterialNewValue_physical")
    name.setFocus()
    QtTest.QTest.keyClicks(name, "My PETG")
    value.setFocus()
    QtTest.QTest.keyClick(value, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
    QtTest.QTest.keyClicks(value, "1.27")
    press("SciForgeMaterialCreate_physical")


def p4_check():
    from sciforge import material

    t = tab("physical")
    h.check(
        "P4 in My Materials", leaves(t, "My Materials") == ["My PETG"], leaves(t, "My Materials")
    )
    h.check("P4 the browser says so", "My PETG made" in message(), message())
    path = os.path.join(App.getUserAppDataDir(), "Material", "SciForge", "My PETG.FCMat")
    h.check("P4 kept in FreeCAD's User library", os.path.isfile(path), path)
    keys = [r["key"] for r in material.available() if r["label"] == "My PETG"]
    h.check("P4 Physical Material offers it too", len(keys) == 1)
    s["petg"] = keys[0] if keys else None
    h.click(V(20, 15, 10))
    m.process()
    press("SciForgeMaterialAssign_physical")


def p4_assigned():
    from sciforge import material

    label, _rho = material.effective(body())
    h.check("P4 the body is My PETG", label == "My PETG", label)
    grams = material.mass(body()) * 1000.0
    h.check("P4 15.24 g", m.near(grams, 15.24, 0.01), grams)


# -- P5 ----------------------------------------------------------------------------------------
def p5_refused():
    t = tab("physical")
    press("SciForgeMaterialNew_physical")
    name = m.find_child(browser(), "SciForgeMaterialNewName_physical")
    value = m.find_child(browser(), "SciForgeMaterialNewValue_physical")
    name.setFocus()
    QtTest.QTest.keyClick(name, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
    QtTest.QTest.keyClicks(name, "Steel")
    value.setFocus()
    QtTest.QTest.keyClick(value, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
    QtTest.QTest.keyClicks(value, "7.8")
    press("SciForgeMaterialCreate_physical")
    h.check("P5 a taken name is refused", "already a material called Steel" in message(), message())
    name.setFocus()
    QtTest.QTest.keyClick(name, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
    QtTest.QTest.keyClicks(name, "Feather")
    value.setFocus()
    QtTest.QTest.keyClick(value, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
    QtTest.QTest.keyClicks(value, "0")
    press("SciForgeMaterialCreate_physical")
    h.check("P5 density 0 is refused", "more than 0" in message(), message())
    h.check("P5 nothing made", leaves(t, "My Materials") == ["My PETG"], leaves(t, "My Materials"))


# -- P6 ----------------------------------------------------------------------------------------
def p6_delete():
    t = tab("physical")
    click_entry(t, "My PETG", "My Materials")
    press("SciForgeMaterialDelete_physical")


def p6_check():
    from sciforge import material

    t = tab("physical")
    h.check("P6 gone from My Materials", leaves(t, "My Materials") == [], leaves(t, "My Materials"))
    h.check("P6 the body keeps it", material.bodies.material_name(body()) == "My PETG")


# -- P7 ----------------------------------------------------------------------------------------
def p7_appearance():
    d = browser()
    d.tabs.setCurrentIndex(1)
    m.process()
    t = tab("appearance")
    press("SciForgeMaterialNew_appearance")
    name = m.find_child(d, "SciForgeMaterialNewName_appearance")
    value = m.find_child(d, "SciForgeMaterialNewValue_appearance")
    name.setFocus()
    QtTest.QTest.keyClicks(name, "Signal Blue")
    value.setFocus()
    QtTest.QTest.keyClicks(value, "#2050c0")
    press("SciForgeMaterialCreate_appearance")
    h.check(
        "P7 in My Appearances",
        leaves(t, "My Appearances") == ["Signal Blue"],
        leaves(t, "My Appearances"),
    )
    h.click(V(20, 15, 10))
    m.process()
    press("SciForgeMaterialAssign_appearance")


def p7_check():
    from sciforge import appearance

    look = appearance.get(body()).get("body") or {}
    h.check("P7 the body has the look", look.get("label") == "Signal Blue", look)
    t = tab("appearance")
    t.search.setFocus()
    QtTest.QTest.keyClicks(t.search, "blue")
    m.process()
    shown = [i.text(0) for i in t.items()]
    h.check(
        "P7 the search lists only blue ones",
        shown and all("blue" in x.lower() for x in shown),
        shown,
    )
    h.shot("7-appearance")


# -- P8 ----------------------------------------------------------------------------------------
def p8_save():
    import json
    import tempfile

    from sciforge import material

    b = body()
    text = getattr(b, material.USER_PROP, "") if material.USER_PROP in b.PropertiesList else ""
    data = json.loads(text) if text else {}
    h.check(
        "P8 the body keeps its own material in the design",
        data.get("name") == "My PETG" and m.near(data.get("density") or 0, 1.27, 1e-6),
        data,
    )
    # As saved on another computer: its body made of a material this one never had.
    data.update({"name": "Lost Nylon", "density": 1.14})
    setattr(b, material.USER_PROP, json.dumps(data))
    s["path"] = os.path.join(tempfile.mkdtemp(prefix="sciforge-materials-"), "Nylon.FCStd")
    App.ActiveDocument.saveAs(s["path"])
    m.close_all()
    App.openDocument(s["path"])


p8_save.wait_ms = 2500


def p8_reopened():
    from sciforge import appearance, material

    b = App.ActiveDocument.getObject(s["body"])
    label, _rho = material.effective(b)
    h.check("P8 opened: the body is Lost Nylon", label == "Lost Nylon", label)
    mine = [r["label"] for r in material.user_entries()]
    h.check("P8 made again in My Materials", "Lost Nylon" in mine, mine)
    grams = material.mass(b) * 1000.0
    h.check("P8 13.68 g", m.near(grams, 13.68, 0.01), grams)
    look = appearance.get(b).get("body") or {}
    h.check("P8 its look is still Signal Blue", look.get("label") == "Signal Blue", look)
    h.check(
        "P8 the design is not changed by it",
        not Gui.getDocument(App.ActiveDocument.Name).Modified,
    )
    try:
        key = material.create_user_material("My PETG", "pla", 1.27)
        h.check("P8 a deleted material's name can be used again", bool(key))
        material.delete_user_material(key)
    except material.MaterialError as exc:
        h.check("P8 a deleted material's name can be used again", False, str(exc))


def cleanup():
    from sciforge import material, materials_ui

    for row in material.user_entries():
        material.delete_user_material(row["key"])

    d = browser()
    if d is not None:
        d.reject()
    App.ParamGet(materials_ui.PREFS).RemString(materials_ui.MY_LOOKS)
    m.close_all()
    h.new_errors()


h.run(
    "misc_materials",
    [
        setup,
        p1_open,
        p1_check,
        p2_pick,
        p2_favorite,
        p3_assign,
        p3_check,
        p3_undone,
        p4_new,
        p4_check,
        p4_assigned,
        p5_refused,
        p6_delete,
        p6_check,
        p7_appearance,
        p7_check,
        p8_save,
        p8_reopened,
        cleanup,
    ],
)
