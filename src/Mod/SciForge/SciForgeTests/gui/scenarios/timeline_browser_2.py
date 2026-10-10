# SPDX-License-Identifier: LGPL-2.1-or-later
"""The BROWSER with the mouse, like in Fusion, and one timeline for a design with two
bodies. Eye toggles, selection both ways (browser <-> 3D view <-> timeline), hover
highlight, Rename, Activate, Isolate, Delete, Edit Sketch, Look At, Create Sketch
on an origin plane, Document Settings > Units, Named Views. Hand-worked numbers:

  body 1   40 x 30 x 10 box           = 12000
  body 2   20 x 20 x 10 box           = 4000
"""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import widget_input as w

V = App.Vector
s = {}


def tree():
    from sciforge import browser_ui

    t = browser_ui.widget()
    t.refresh()  # rebuilds only when the design changed (rows stay valid)
    return t


def row(label):
    item = tree().row(label)
    h.check("browser row %r" % label, item is not None, tree().labels())
    return item


def tl():
    from sciforge import timeline_ui

    t = timeline_ui.widget()
    t.refresh(force=True)
    return t


def vol(name):
    obj = App.ActiveDocument.getObject(name)
    if obj is None or obj.Shape.isNull():
        return 0.0
    return obj.Shape.Volume


def near(a, b):
    return abs(a - b) <= 1e-6 * max(1.0, abs(b))


def _row_point(label, eye=False):
    """(tree, point) of a row, read in one go so the row cannot be rebuilt in between."""
    t = tree()
    item = t.row(label)
    h.check("browser row %r" % label, item is not None, t.labels())
    if item is None:
        return t, None
    return t, (t.eye_point(item) if eye else t.label_point(item))


def click_row(label, modifiers=QtCore.Qt.NoModifier):
    t, pos = _row_point(label)
    if pos is not None:
        w.click(t.viewport(), pos, modifiers)


def click_eye(label):
    t, pos = _row_point(label, eye=True)
    if pos is not None:
        w.click(t.viewport(), pos)


def double_click_row(label):
    t, pos = _row_point(label)
    if pos is not None:
        w.double_click(t.viewport(), pos)


def menu(label, entry):
    t, pos = _row_point(label)
    ok = pos is not None and w.right_click(t.viewport(), pos, entry)
    h.check("browser menu %s > %s" % (label, entry), ok)


def choose(combo, text):
    """Pick an entry of a drop-down with the keyboard (arrow keys), like a person can."""
    combo.setFocus()
    target = combo.findText(text)
    for _ in range(10):
        if combo.currentIndex() == target:
            break
        key = QtCore.Qt.Key_Down if combo.currentIndex() < target else QtCore.Qt.Key_Up
        w.key(combo, key)


def selected():
    return [x.ObjectName for x in Gui.Selection.getSelectionEx()]


def selected_rows():
    return [i.text(1) for i in tree().selectedItems()]


# -- a part, made with the mouse -----------------------------------------------------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Browser")
    h.fit()


def empty_browser():
    top = tree().topLevelItem(0)
    labels = [top.child(i).text(1) for i in range(top.childCount())]
    h.check(
        "new design: Document Settings and Named Views",
        labels[:2] == ["Document Settings", "Named Views"],
        labels,
    )


def create_sketch():
    h.ribbon("Create Sketch")


def pick_xy():
    h.click(V(12, -8, 0))


def draw():
    sk = h.in_sketch()
    h.check("sketch open", sk is not None)
    if sk:
        h.draw_rectangle(sk, 0, 0, 40, 30)


def finish():
    h.ribbon("Finish Sketch")


def extrude():
    h.fit()
    h.press("e")


def extrude_ok():
    h.task_button("OK")


def check_structure():
    h.check("box", near(vol("Body"), 12000), vol("Body"))
    top = tree().topLevelItem(0)
    labels = [top.child(i).text(1) for i in range(top.childCount())]
    h.check(
        "Fusion's folders",
        labels == ["Document Settings", "Named Views", "Origin", "Bodies", "Sketches"],
        labels,
    )
    body = row("Body")
    h.check("active body is bold", body is not None and body.font(1).bold())
    h.check(
        "features are not in the browser",
        "Pad" not in tree().labels() and "Extrude" not in tree().labels(),
    )
    h.shot("1-browser")


# -- eye, selection, hover ---------------------------------------------------------------
def eye_sketch_on():
    click_eye("Sketch")


def check_eye_on():
    sk = App.ActiveDocument.getObject("Sketch")
    h.check("eye shows the sketch", sk.ViewObject.Visibility)


def eye_sketch_off():
    click_eye("Sketch")


def check_eye_off():
    h.check("eye hides it again", not App.ActiveDocument.getObject("Sketch").ViewObject.Visibility)


def eye_body_off():
    click_eye("Body")


def check_body_hidden():
    h.check(
        "body eye hides the body", not App.ActiveDocument.getObject("Body").ViewObject.Visibility
    )
    click_eye("Body")


def check_body_shown():
    h.check("body eye shows it again", App.ActiveDocument.getObject("Body").ViewObject.Visibility)


def select_body_row():
    click_row("Body")


def check_body_selected():
    h.check("browser click selects the body in 3D", selected() == ["Body"], selected())


def click_background():
    h.click_empty()


def check_cleared():
    h.check(
        "3D background click clears the browser selection", selected_rows() == [], selected_rows()
    )


def timeline_sketch():
    b = [x for x in tl()._buttons if x.item.display == "Sketch 1"][0]
    w.click(b)


def check_synced():
    h.check("timeline click selects the sketch", selected() == ["Sketch"], selected())
    QtWidgets.QApplication.processEvents()
    h.check("and the browser shows it selected", selected_rows() == ["Sketch"], selected_rows())


def hover_body():
    h.click_empty()
    t, pos = _row_point("Body")
    if pos is not None:
        w.move(t.viewport(), pos + QtCore.QPoint(5, 0))
        w.move(t.viewport(), pos)


def check_hover():
    pre = Gui.Selection.getPreselection()
    h.check(
        "hover lights up the body",
        pre is not None and pre.ObjectName == "Body",
        pre and pre.ObjectName,
    )
    w.move(h.gl_widget(), QtCore.QPoint(20, 20))


# -- rename --------------------------------------------------------------------------------
def rename_body():
    menu("Body", "Rename")


def type_name():
    editor = tree().findChild(QtWidgets.QLineEdit)
    h.check("name field opens on the row", editor is not None and editor.isVisible())
    if editor is not None:
        w.key(editor, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
        w.type_text(editor, "Bracket")
        w.key(editor, QtCore.Qt.Key_Return)


def check_renamed():
    h.check("body renamed", App.ActiveDocument.getObject("Body").Label == "Bracket")
    h.check("row shows the new name", row("Bracket") is not None, tree().labels())


def f2_rename_sketch():
    click_row("Sketch")
    w.key(tree(), QtCore.Qt.Key_F2)


def type_profile():
    editor = tree().findChild(QtWidgets.QLineEdit)
    h.check("F2 opens the name field", editor is not None and editor.isVisible())
    if editor is not None:
        w.key(editor, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
        w.type_text(editor, "Base Profile")
        w.key(editor, QtCore.Qt.Key_Return)


def check_profile_name():
    h.check("sketch renamed", App.ActiveDocument.getObject("Sketch").Label == "Base Profile")
    h.check("timeline shows the new name", "Base Profile" in tl().titles(), tl().titles())


# -- origin ---------------------------------------------------------------------------------
def expand_origin():
    click_row("Origin")
    w.key(tree(), QtCore.Qt.Key_Right)


def eye_xy():
    click_eye("XY")


def check_xy():
    h.check("XY plane shown", App.ActiveDocument.getObject("XY_Plane").ViewObject.Visibility)
    h.shot("2-origin")
    click_eye("XY")


def check_xy_off():
    h.check(
        "XY plane hidden again", not App.ActiveDocument.getObject("XY_Plane").ViewObject.Visibility
    )


# -- units ------------------------------------------------------------------------------------
def open_units():
    click_row("Units: mm")


def pick_inch():
    from sciforge import browser_ui

    panel = browser_ui.UnitsPanel.last
    h.check("Change Active Units opens", panel is not None and not panel._closed)
    combo = panel.form.findChild(QtWidgets.QComboBox, "SciForgeUnitType")
    choose(combo, "Inch")
    s["combo"] = combo.currentText()


def units_ok():
    h.task_button("OK")


def check_inch():
    h.check("Inch chosen", s.get("combo") == "Inch", s.get("combo"))
    h.check("browser says Units: in", row("Units: in") is not None, tree().labels())
    h.check("design uses inches", App.ActiveDocument.UnitSystem.startswith("Imperial decimal"))


def open_units_cancel():
    click_row("Units: in")


def units_cancel():
    from sciforge import browser_ui

    panel = browser_ui.UnitsPanel.last
    combo = panel.form.findChild(QtWidgets.QComboBox, "SciForgeUnitType")
    choose(combo, "Centimeter")
    h.task_button("Cancel")


def check_cancel():
    h.check("Cancel keeps inches", App.ActiveDocument.UnitSystem.startswith("Imperial decimal"))


def back_to_mm():
    click_row("Units: in")


def pick_mm():
    from sciforge import browser_ui

    combo = browser_ui.UnitsPanel.last.form.findChild(QtWidgets.QComboBox, "SciForgeUnitType")
    choose(combo, "Millimeter")
    h.task_button("OK")


def check_mm():
    h.check("back to millimeters", App.ActiveDocument.UnitSystem.startswith("Standard"))
    h.check("Units: mm", row("Units: mm") is not None)


# -- named views ----------------------------------------------------------------------------------
def new_view():
    h.fit()
    s["iso"] = Gui.ActiveDocument.ActiveView.getViewDirection()
    menu("Named Views", "New Named View")


def go_top():
    h.check("saved view listed", row("Named View 1") is not None, tree().labels())
    click_row("TOP")


def check_top():
    d = Gui.ActiveDocument.ActiveView.getViewDirection()
    h.check("TOP looks down", abs(d.z + 1) < 1e-6, d)
    click_row("Named View 1")


def check_saved_view():
    d = Gui.ActiveDocument.ActiveView.getViewDirection()
    h.check("saved view restored", (d - s["iso"]).Length < 1e-6, (d, s["iso"]))
    menu("Named View 1", "Delete")


def check_view_deleted():
    h.check("saved view deleted", tree().row("Named View 1") is None, tree().labels())


# -- a second body: one timeline ---------------------------------------------------------------------
def new_body():
    h.click_empty()
    h.press("s")


def type_body():
    popup = [
        x
        for x in QtWidgets.QApplication.topLevelWidgets()
        if x.isVisible() and isinstance(x, QtWidgets.QDialog)
    ]
    h.check("command search open", bool(popup))
    if popup:
        edit = popup[0].findChild(QtWidgets.QLineEdit)
        w.type_text(edit, "partdesign_body")
        w.key(edit, QtCore.Qt.Key_Return)


def check_body2():
    bodies = [o.Name for o in App.ActiveDocument.Objects if o.TypeId == "PartDesign::Body"]
    h.check("second body made", len(bodies) == 2, bodies)
    s["b2"] = [b for b in bodies if b != "Body"][0] if len(bodies) == 2 else None
    h.fit()


def sketch_b2():
    h.ribbon("Create Sketch")


def pick_xy_b2():
    h.click(V(-30, -25, 0))


def draw_b2():
    sk = h.in_sketch()
    h.check("sketch in body 2", sk is not None and sk.getParentGeoFeatureGroup().Name == s["b2"])
    if sk:
        h.draw_rectangle(sk, -40, -40, -20, -20)


def extrude_b2():
    h.fit()
    h.press("e")


def check_two_bodies():
    h.check("body 2 = 20x20x10", near(vol(s["b2"]), 4000), vol(s["b2"]))
    h.check("body 1 unchanged", near(vol("Body"), 12000), vol("Body"))
    titles = tl().titles()
    h.check(
        "one timeline for both bodies",
        titles == ["Base Profile", "Extrude 1", "Sketch 2", "Extrude 2"],
        titles,
    )
    bodies = row("Bodies")
    h.check("both bodies listed", bodies is not None and bodies.childCount() == 2)
    b2 = tree().row(App.ActiveDocument.getObject(s["b2"]).Label)
    h.check("new body is the active one", b2 is not None and b2.font(1).bold())
    h.shot("3-two-bodies")


def roll_back_body2():
    b = [x for x in tl()._buttons if x.item.display == "Extrude 1"][0]
    w.right_click(b, w.center(b), "Roll History Marker Here")


def check_rolled():
    h.check("rolled back: body 2 not made yet", vol(s["b2"]) < 1e-6, vol(s["b2"]))
    h.check("body 1 still there", near(vol("Body"), 12000), vol("Body"))


def roll_to_end():
    gear = tl().findChild(QtWidgets.QToolButton, "SciForgeTimeline_settings")
    pos = w.center(gear)
    state = {}

    def pick():
        menu = QtWidgets.QApplication.activePopupWidget()
        if isinstance(menu, QtWidgets.QMenu):
            for a in menu.actions():
                if a.text() == "Roll History Marker to End":
                    r = menu.actionGeometry(a)
                    for i in range(8):
                        QtTest.QTest.mouseMove(
                            menu, QtCore.QPoint(r.left() + 10 + 8 * i, r.center().y())
                        )
                    QtTest.QTest.mouseClick(
                        menu, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, r.center()
                    )
                    state["ok"] = True
        elif state.get("n", 0) < 20:
            state["n"] = state.get("n", 0) + 1
            QtCore.QTimer.singleShot(50, pick)

    QtCore.QTimer.singleShot(50, pick)
    w.click(gear, pos)
    h.check("timeline settings > Roll History Marker to End", state.get("ok"))


def check_end():
    h.check("body 2 back", near(vol(s["b2"]), 4000), vol(s["b2"]))


def move_across_bodies():
    """Drag body 2's sketch to the very start of the timeline."""
    b = [x for x in tl()._buttons if x.item.display == "Sketch 2"][0]
    first = tl()._buttons[0]
    w.drag(b, w.center(b), first.mapToGlobal(QtCore.QPoint(1, first.height() // 2)))


def check_moved():
    names = [i.name for i in tl().items()]
    sk2 = [
        o for o in App.ActiveDocument.getObject(s["b2"]).Group if o.TypeId.startswith("Sketcher")
    ][0]
    h.check("body 2's sketch is first now", names and names[0] == sk2.Name, names)
    h.check("volumes unchanged", near(vol(s["b2"]), 4000) and near(vol("Body"), 12000))


def undo_move():
    w.click(w.quick_access("Undo"))


def check_undo_move():
    names = [i.name for i in tl().items()]
    h.check("Undo puts it back", names and names[0] == "Sketch", names)


def activate_body1():
    double_click_row("Bracket")


def check_active():
    from sciforge import commands

    body = commands.active_body()
    h.check(
        "double-click activates the body",
        body is not None and body.Name == "Body",
        body and body.Name,
    )
    h.check("bold follows", row("Bracket").font(1).bold())


def isolate_body2():
    menu(App.ActiveDocument.getObject(s["b2"]).Label, "Isolate")


def check_isolated():
    h.check(
        "Isolate hides the other body",
        not App.ActiveDocument.getObject("Body").ViewObject.Visibility,
    )
    menu("Browser", "Show All Bodies")


def check_all_shown():
    h.check("Show All Bodies", App.ActiveDocument.getObject("Body").ViewObject.Visibility)


def delete_body2():
    menu(App.ActiveDocument.getObject(s["b2"]).Label, "Delete")


def check_body2_gone():
    h.check("body 2 deleted", App.ActiveDocument.getObject(s["b2"]) is None)
    h.check(
        "its steps left the timeline", tl().titles() == ["Base Profile", "Extrude 1"], tl().titles()
    )
    h.check("body 1 untouched", near(vol("Body"), 12000))


def undo_delete_body():
    w.click(w.quick_access("Undo"))


def check_body2_back():
    h.check("Undo brings body 2 back", near(vol(s["b2"]), 4000), vol(s["b2"]))
    h.check("timeline has 4 steps again", len(tl().titles()) == 4, tl().titles())


# -- sketch menu ---------------------------------------------------------------------------------------
def edit_sketch():
    menu("Base Profile", "Edit Sketch")


def check_editing():
    sk = h.in_sketch()
    h.check("Edit Sketch opens it", sk is not None and sk.Name == "Sketch", sk and sk.Name)


def finish_edit():
    h.ribbon("Finish Sketch")


def look_at():
    h.check("left the sketch", h.in_sketch() is None)
    menu("Base Profile", "Look At")


def check_look_at():
    d = Gui.ActiveDocument.ActiveView.getViewDirection()
    h.check("Look At faces the sketch", abs(d.z + 1) < 1e-6, d)
    h.fit()


def sketch_on_xy():
    menu("XY", "Create Sketch")


def check_new_sketch():
    sk = h.in_sketch()
    h.check("Create Sketch on the XY row", sk is not None)
    s["new_sketch"] = sk.Name if sk else None


def finish_new():
    h.ribbon("Finish Sketch")


def delete_new_sketch():
    name = s.get("new_sketch")
    label = App.ActiveDocument.getObject(name).Label if name else "?"
    click_row(label)
    w.key(tree(), QtCore.Qt.Key_Delete)


def check_new_deleted():
    h.check(
        "Delete key in the browser deletes the sketch",
        App.ActiveDocument.getObject(s.get("new_sketch") or "") is None,
    )
    h.check("both bodies fine", near(vol("Body"), 12000) and near(vol(s["b2"]), 4000))
    h.check("no pop-ups", not h.popups(), h.popups())
    h.shot("4-end")


h.run(
    "timeline_browser_2",
    [
        new_design,
        empty_browser,
        create_sketch,
        pick_xy,
        draw,
        finish,
        extrude,
        extrude_ok,
        check_structure,
        eye_sketch_on,
        check_eye_on,
        eye_sketch_off,
        check_eye_off,
        eye_body_off,
        check_body_hidden,
        check_body_shown,
        select_body_row,
        check_body_selected,
        click_background,
        check_cleared,
        timeline_sketch,
        check_synced,
        hover_body,
        check_hover,
        rename_body,
        type_name,
        check_renamed,
        f2_rename_sketch,
        type_profile,
        check_profile_name,
        expand_origin,
        eye_xy,
        check_xy,
        check_xy_off,
        open_units,
        pick_inch,
        units_ok,
        check_inch,
        open_units_cancel,
        units_cancel,
        check_cancel,
        back_to_mm,
        pick_mm,
        check_mm,
        new_view,
        go_top,
        check_top,
        check_saved_view,
        check_view_deleted,
        new_body,
        type_body,
        check_body2,
        sketch_b2,
        pick_xy_b2,
        draw_b2,
        finish,
        extrude_b2,
        extrude_ok,
        check_two_bodies,
        roll_back_body2,
        check_rolled,
        roll_to_end,
        check_end,
        move_across_bodies,
        check_moved,
        undo_move,
        check_undo_move,
        activate_body1,
        check_active,
        isolate_body2,
        check_isolated,
        check_all_shown,
        delete_body2,
        check_body2_gone,
        undo_delete_body,
        check_body2_back,
        edit_sketch,
        check_editing,
        finish_edit,
        look_at,
        check_look_at,
        sketch_on_xy,
        check_new_sketch,
        finish_new,
        delete_new_sketch,
        check_new_deleted,
    ],
)
