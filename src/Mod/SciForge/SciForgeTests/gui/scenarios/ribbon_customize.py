# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pin to Toolbar and Change Keyboard Shortcut, like Fusion's three-dot menu of a command
(Luca, 2026-10-16: "There should be a way to change the keybinds of each tool"; "there should
be a way to pin tools to the toolbar"). Only real input: menus, buttons, keys.

A  SOLID > CREATE menu, the pointer on Coil: a three-dot button appears at the row's right
   end; clicked: Pin to Toolbar. CREATE gets a large Coil icon after its own; it runs Coil
   (the dialog opens; Esc).
B  A right-click on the pinned Coil icon: Unpin from Toolbar: the icon goes.
C  Coil pinned again (right-click on Coil in the menu); a right-click on the ribbon's empty
   space: Reset All Toolbar Customization asks first (No keeps it), Yes takes it off.
D  MODIFY menu, three dots on Fillet, Change Keyboard Shortcut...: the dialog shows F; Shift+F
   pressed, OK. Shift+F over the 3D view opens Fillet; F alone no longer does; the menu shows
   Shift+F. The dialog's Reset gives F back.
E  CREATE menu, Extrude's dialog: F pressed: it names Fillet, OK reads Override; Override:
   F opens Extrude, Fillet has no key (its menu row shows none), E does nothing.
F  Preferences > Keyboard Shortcuts lists Extrude with F; Reset All Shortcuts (Yes): E is
   Extrude's again and F Fillet's.
G  The pins and keys survive a rebuild of the ribbon (they are read from the settings).
"""

import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si

s = {}


# -- helpers --------------------------------------------------------------------------------------
def group(title):
    return si._group_widget(title)


def big(label):
    for button in h.ribbon_buttons():
        if button.objectName() == "SciForgeBig_" + label.replace(" ", "_"):
            return button
    return None


def row_text(title, label):
    g = group(title)
    path = si._find(g.menu, label) if g is not None else []
    return path[-1][1].text() if path else None


def popup():
    return QtWidgets.QApplication.activePopupWidget()


def close_popups():
    p = popup()
    while p is not None:
        p.close()
        p = popup()


def click_menu_action(menu, text):
    """Click a menu row. The click goes out a moment later: what it starts may open its own
    window (a question box) and wait, and the steps after it must go on meanwhile."""
    for action in menu.actions():
        if action.text().replace("&", "").split("\t")[0] == text:
            rect = menu.actionGeometry(action)
            QtTest.QTest.mouseMove(menu, rect.center())
            QtCore.QTimer.singleShot(
                0,
                lambda: QtTest.QTest.mouseClick(
                    menu, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, rect.center()
                ),
            )
            return True
    return False


def later(steps, done, i=0, tries=0):
    """Run `steps` (functions returning True when they did their part) one after another,
    each when it can, while a menu's own event loop runs."""
    if i >= len(steps):
        done["ok"] = True
        return
    try:
        ok = steps[i]()
    except Exception as exc:
        done["error"] = str(exc)
        close_popups()
        return
    if ok and i + 1 == len(steps):
        done["ok"] = True
    elif ok:
        QtCore.QTimer.singleShot(250, lambda: later(steps, done, i + 1))
    elif tries < 30:
        QtCore.QTimer.singleShot(150, lambda: later(steps, done, i, tries + 1))
    else:
        done["stuck"] = i
        close_popups()


def menu_options(title, label, option):
    """Open the group's menu, put the pointer on `label`, click the three-dot button, click
    `option` in the options menu."""
    g = group(title)
    if not h.check("group %s shown" % title, g is not None):
        return False
    done = {}
    state = {}

    def hover():
        menu = popup()
        if menu is not g.menu:
            return False
        path = si._find(menu, label)
        if not path:
            done["missing"] = label
            close_popups()
            return False
        rect = menu.actionGeometry(path[0][1])
        for x in (rect.left() + 10, rect.center().x(), rect.right() - 30):
            QtTest.QTest.mouseMove(menu, QtCore.QPoint(x, rect.center().y()))
        state["button_seen"] = g.menu._sf_options.button.isVisible()
        return True

    def dots():
        button = g.menu._sf_options.button
        if not button.isVisible():
            return False
        state["button_at_right"] = button.geometry().right() > g.menu.width() - 40
        # (a moment later: the options menu it opens waits for its own click)
        QtCore.QTimer.singleShot(0, lambda: QtTest.QTest.mouseClick(button, QtCore.Qt.LeftButton))
        return True

    def choose():
        menu = popup()
        if menu is None or menu is g.menu or menu.objectName() != "SciForgeCommandOptions":
            return False
        state["options"] = [a.text() for a in menu.actions()]
        return click_menu_action(menu, option)

    QtCore.QTimer.singleShot(300, lambda: later([hover, dots, choose], done))
    guard = QtCore.QTimer()
    guard.setSingleShot(True)
    guard.timeout.connect(close_popups)
    guard.start(8000)
    g.open_menu()
    guard.stop()
    QtWidgets.QApplication.processEvents()
    s["last_options"] = state
    return h.check(
        "%s > %s > three dots > %s" % (title, label, option), done.get("ok"), (done, state)
    )


def right_click(widget, option, pos=None):
    """A right-click on a widget (its context menu), then `option` in the menu."""
    done = {}

    def choose():
        menu = popup()
        if menu is None:
            return False
        return click_menu_action(menu, option)

    QtCore.QTimer.singleShot(300, lambda: later([choose], done))
    guard = QtCore.QTimer()
    guard.setSingleShot(True)
    guard.timeout.connect(close_popups)
    guard.start(6000)
    pos = pos or QtCore.QPoint(widget.width() // 2, widget.height() // 2)
    event = QtGui.QContextMenuEvent(
        QtGui.QContextMenuEvent.Mouse, pos, widget.mapToGlobal(pos), QtCore.Qt.NoModifier
    )
    QtWidgets.QApplication.sendEvent(widget, event)
    guard.stop()
    QtWidgets.QApplication.processEvents()
    return h.check("right-click > %s" % option, done.get("ok"), done)


def answer_question(button_text):
    """Click a button of the question box that is about to open (QMessageBox)."""

    def click(tries=0):
        box = QtWidgets.QApplication.activeModalWidget()
        if isinstance(box, QtWidgets.QMessageBox):
            for button in box.buttons():
                if button.text().replace("&", "") == button_text:
                    button.click()
                    return
        if tries < 30:
            QtCore.QTimer.singleShot(150, lambda: click(tries + 1))

    QtCore.QTimer.singleShot(300, click)


def key_dialog():
    from sciforge import command_options

    d = command_options.KeyDialog.last
    try:
        return d if d is not None and d.isVisible() else None
    except RuntimeError:
        return None


def dialog_open(cls_name):
    dlg = Gui.Control.activeDialog()
    return bool(dlg)


def press_view(key, modifiers=QtCore.Qt.NoModifier):
    h.fit()
    Gui.Selection.clearSelection()
    h.press(key, modifiers)


def close_dialog():
    h.press(QtCore.Qt.Key_Escape)
    QtWidgets.QApplication.processEvents()


# -- A --------------------------------------------------------------------------------------------
def a_pin_coil():
    s["coil_before"] = big("Coil") is not None
    menu_options("CREATE", "Coil", "Pin to Toolbar")


def a_pinned():
    h.check("Coil was not a large icon before", not s.get("coil_before"))
    state = s.get("last_options", {})
    h.check("the three dots showed on the hovered row", state.get("button_seen"), state)
    h.check("at the row's right end", state.get("button_at_right"), state)
    h.check(
        "the options: Pin to Toolbar and Change Keyboard Shortcut",
        state.get("options") == ["Pin to Toolbar", "Change Keyboard Shortcut..."],
        state.get("options"),
    )
    button = big("Coil")
    h.check("a large Coil icon in CREATE", button is not None and button.isVisible())
    g = group("CREATE")
    last = g.buttons[-1] if g is not None and g.buttons else None
    h.check("after the group's own icons", last is button, last and last.objectName())
    h.shot("a-pinned")
    if button is not None:
        button.click()


def a_coil_opened():
    h.check("the pinned icon runs Coil", bool(Gui.Control.activeDialog()))
    close_dialog()


# -- B --------------------------------------------------------------------------------------------
def b_unpin():
    button = big("Coil")
    if h.check("the pinned Coil icon", button is not None):
        right_click(button, "Unpin from Toolbar")


def b_unpinned():
    h.check("Unpin takes the icon off", big("Coil") is None)


# -- C --------------------------------------------------------------------------------------------
def c_pin_by_right_click():
    g = group("CREATE")
    done = {}

    def right():
        menu = popup()
        if menu is not g.menu:
            return False
        path = si._find(menu, "Coil")
        rect = menu.actionGeometry(path[0][1])
        QtTest.QTest.mouseMove(menu, rect.center())
        event = QtGui.QContextMenuEvent(
            QtGui.QContextMenuEvent.Mouse, rect.center(), menu.mapToGlobal(rect.center())
        )
        QtWidgets.QApplication.postEvent(menu, event)
        return True

    def choose():
        menu = popup()
        if menu is None or menu.objectName() != "SciForgeCommandOptions":
            return False
        return click_menu_action(menu, "Pin to Toolbar")

    QtCore.QTimer.singleShot(300, lambda: later([right, choose], done))
    guard = QtCore.QTimer()
    guard.setSingleShot(True)
    guard.timeout.connect(close_popups)
    guard.start(8000)
    g.open_menu()
    guard.stop()
    QtWidgets.QApplication.processEvents()
    h.check("right-click on Coil in the menu > Pin to Toolbar", done.get("ok"), done)
    h.check("Coil pinned again", big("Coil") is not None)


def _ribbon_empty_spot():
    from sciforge import shell

    ribbon = shell.ribbon()
    page = ribbon.pages.currentWidget()
    # right of the last group, inside the page: empty ribbon space
    return ribbon, page, QtCore.QPoint(page.width() - 20, page.height() // 2)


def c_reset_no():
    ribbon, page, pos = _ribbon_empty_spot()
    answer_question("No")
    right_click(page, "Reset All Toolbar Customization", pos)


def c_kept():
    h.check("No keeps the pin", big("Coil") is not None)


def c_reset_yes():
    ribbon, page, pos = _ribbon_empty_spot()
    answer_question("Yes")
    right_click(page, "Reset All Toolbar Customization", pos)


def c_reset():
    h.check("Yes takes every pin off", big("Coil") is None)


# -- D --------------------------------------------------------------------------------------------
def d_open_dialog():
    menu_options("MODIFY", "Fillet", "Change Keyboard Shortcut...")


def d_dialog():
    d = key_dialog()
    if not h.check("Change Keyboard Shortcut dialog open", d is not None):
        return
    h.check("it shows the current key F", "F" in d.now.text(), d.now.text())
    d.edit.setFocus()
    d.edit.clear()
    QtTest.QTest.keyClick(d.edit, QtCore.Qt.Key_F, QtCore.Qt.ShiftModifier)
    QtWidgets.QApplication.processEvents()


def d_ok():
    d = key_dialog()
    if d is None:
        return
    h.check("the new key is Shift+F", d.key() == "Shift+F", d.key())
    h.check("no conflict: OK", d.ok_button.text() == "OK", d.ok_button.text())
    d.ok_button.click()


def d_shift_f():
    h.check("the dialog closed", key_dialog() is None)
    h.check("the menu shows Shift+F", (row_text("MODIFY", "Fillet") or "").endswith("Shift+F"))
    press_view(QtCore.Qt.Key_F, QtCore.Qt.ShiftModifier)


def d_fillet_opened():
    h.check("Shift+F opens Fillet", b.blend_panel() is not None, Gui.Control.activeDialog())
    close_dialog()


def d_plain_f():
    press_view(QtCore.Qt.Key_F)


def d_plain_f_nothing():
    h.check("F alone does nothing now", not Gui.Control.activeDialog())
    close_dialog()
    menu_options("MODIFY", "Fillet", "Change Keyboard Shortcut...")


def d_reset():
    d = key_dialog()
    if h.check("the dialog again", d is not None):
        h.check("it shows Shift+F", "Shift+F" in d.now.text(), d.now.text())
        d.reset_button.click()


def d_reset_done():
    h.check("Reset: the menu shows F again", (row_text("MODIFY", "Fillet") or "").endswith("\tF"))
    press_view(QtCore.Qt.Key_F)


def d_f_again():
    h.check("F opens Fillet again", b.blend_panel() is not None)
    close_dialog()


# -- E --------------------------------------------------------------------------------------------
def e_open_dialog():
    menu_options("CREATE", "Extrude", "Change Keyboard Shortcut...")


def e_press_f():
    d = key_dialog()
    if not h.check("Extrude's dialog open", d is not None):
        return
    d.edit.setFocus()
    d.edit.clear()
    QtTest.QTest.keyClick(d.edit, QtCore.Qt.Key_F)
    QtWidgets.QApplication.processEvents()
    h.check("it names Fillet", "Fillet" in d.message.text(), d.message.text())
    h.check("OK reads Override", d.ok_button.text() == "Override", d.ok_button.text())
    h.shot("e-conflict")
    d.ok_button.click()


def e_f_extrudes():
    h.check("Fillet's menu row has no key", row_text("MODIFY", "Fillet") == "Fillet")
    h.check("Extrude's row shows F", (row_text("CREATE", "Extrude") or "").endswith("\tF"))
    press_view(QtCore.Qt.Key_F)


def e_extrude_opened():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    h.check("F opens Extrude", bool(Gui.Control.activeDialog()) and p is not None and not p._closed)
    close_dialog()


def e_plain_e():
    press_view(QtCore.Qt.Key_E)


def e_e_nothing():
    h.check("E does nothing now", not Gui.Control.activeDialog())
    close_dialog()


# -- F --------------------------------------------------------------------------------------------
def f_preferences():
    from sciforge import preferences_ui

    Gui.runCommand("SciForge_Preferences")
    QtWidgets.QApplication.processEvents()
    dlg = preferences_ui.PreferencesDialog.last
    if not h.check("Preferences open", dlg is not None and dlg.isVisible()):
        return
    page = getattr(dlg, "keyboard", None)
    if not h.check("a Keyboard Shortcuts page", page is not None):
        return
    for i in range(dlg.pages.topLevelItemCount()):
        item = dlg.pages.topLevelItem(i)
        if item.text(0) == "Keyboard Shortcuts":
            dlg.pages.setCurrentItem(item)
    row = page.row_of("Extrude")
    h.check(
        "Extrude listed with F",
        row >= 0 and page.table.item(row, 1).text() == "F",
        row >= 0 and page.table.item(row, 1).text(),
    )
    page.search.setText("fillet")
    visible = [page.rows[i][0] for i in range(len(page.rows)) if not page.table.isRowHidden(i)]
    h.check("search finds Fillet", "Fillet" in visible, visible)
    page.search.setText("")
    h.shot("f-keyboard-page")
    answer_question("Yes")
    page.reset_button.click()
    QtWidgets.QApplication.processEvents()


def f_reset():
    from sciforge import preferences_ui

    dlg = preferences_ui.PreferencesDialog.last
    page = dlg.keyboard if dlg is not None else None
    if page is not None:
        row = page.row_of("Extrude")
        h.check("the list shows E again", page.table.item(row, 1).text() == "E")
        dlg.reject()
    h.check("Extrude's row shows E", (row_text("CREATE", "Extrude") or "").endswith("\tE"))
    h.check("Fillet's row shows F", (row_text("MODIFY", "Fillet") or "").endswith("\tF"))
    press_view(QtCore.Qt.Key_E)


def f_e_extrudes():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    h.check("E opens Extrude again", bool(Gui.Control.activeDialog()) and p is not None)
    close_dialog()


# -- G --------------------------------------------------------------------------------------------
def g_pin_and_key():
    menu_options("CREATE", "Coil", "Pin to Toolbar")


def g_rebuild():
    from sciforge import shell

    shell.ribbon().refresh_customization()
    h.check("the pin is read back from the settings", big("Coil") is not None)


h.run(
    "ribbon_customize",
    b.box_steps("RibbonCustomize")
    + [
        a_pin_coil,
        a_pinned,
        a_coil_opened,
        b_unpin,
        b_unpinned,
        c_pin_by_right_click,
        c_reset_no,
        c_kept,
        c_reset_yes,
        c_reset,
        d_open_dialog,
        d_dialog,
        d_ok,
        d_shift_f,
        d_fillet_opened,
        d_plain_f,
        d_plain_f_nothing,
        d_reset,
        d_reset_done,
        d_f_again,
        e_open_dialog,
        e_press_f,
        e_f_extrudes,
        e_extrude_opened,
        e_plain_e,
        e_e_nothing,
        f_preferences,
        f_reset,
        f_e_extrudes,
        g_pin_and_key,
        g_rebuild,
    ],
)
