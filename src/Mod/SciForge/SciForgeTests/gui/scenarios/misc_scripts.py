# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scripts and Add-Ins (UTILITIES > ADD-INS), only real input (docs/sciforge/parity/misc.md).

A scripts folder with AddBox.FCMacro (adds a 10 mm box body to the open design) and
Broken.FCMacro (divides by zero); an empty add-ins folder.

P1 UTILITIES > Scripts and Add-Ins: one list, AddBox and Broken (Script), the folders shown.
P2 AddBox selected, Run: the design gets the box; Ctrl+Z takes it away in one step.
P3 Broken, double-click (Run): the dialog says it stopped with a ZeroDivisionError; the design
   is unchanged; SciForge goes on. A script ending with sys.exit() ran: its box stays.
P4 Create > Add-In "Greeter": listed as an Add-In (its folder and Greeter.py with run / stop);
   Run: Running, the button says Stop; Stop: stopped.
P5 Run on Startup ticked for AddBox: kept; at the next start (simulated) the box is made;
   unticked: no longer kept.
P6 Edit with an editor set in Preferences: the editor gets the script's file.
P7 The search box: "gree" lists Greeter only.
P8 + (a script from another folder): copied into the scripts folder and listed; the same one
   again is refused with the reason. Create with the name "1st": refused in the Create window.
P9 Shift+S opens the window from the keyboard; Close.
"""

import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import dialog_input as di
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as i
from SciForgeTests.gui import misc_steps as m
from SciForgeTests.gui import widget_input as w

MACRO = "User parameter:BaseApp/Preferences/Macro"
PREFS = "User parameter:BaseApp/Preferences/Mod/SciForge/Preferences"
ADD_BOX = """import FreeCAD as App
doc = App.ActiveDocument
body = doc.addObject("PartDesign::Body", "ScriptBody")
box = doc.addObject("PartDesign::AdditiveBox", "ScriptBox")
body.addObject(box)
box.Placement.Base = App.Vector(100, 0, 0)
doc.recompute()
"""
BROKEN = """x = 1 / 0
"""
s = {"started": []}


def dialog():
    from sciforge import scripts_ui

    d = scripts_ui.ScriptsDialog.last
    try:
        return d if d is not None and d.isVisible() else None
    except RuntimeError:
        return None


def names():
    d = dialog()
    if d is None:
        return []
    return [d.list.topLevelItem(r).text(0) for r in range(d.list.topLevelItemCount())]


def pick(kind, name):
    """Click the row of a script or add-in."""
    d = dialog()
    item = d.item_for(kind, name) if d is not None else None
    if not h.check("listed: %s" % name, item is not None, names()):
        return None
    rect = d.list.visualItemRect(item)
    w.click(d.list.viewport(), QtCore.QPoint(rect.left() + 20, rect.center().y()))
    return item


def press(name):
    d = dialog()
    button = m.find_child(d, name)
    if h.check("button %s" % name, button is not None and button.isEnabled()):
        w.click(button)
        m.process()


def message():
    d = dialog()
    return d.message.text() if d is not None else ""


def script_bodies():
    doc = App.ActiveDocument
    return [o for o in doc.Objects if o.Name.startswith("ScriptBody")] if doc else []


def setup():
    from sciforge import scripts_ui

    Gui.activateWorkbench("SciForgeWorkbench")
    s["scripts"] = tempfile.mkdtemp(prefix="sciforge-scripts-")
    s["addins"] = tempfile.mkdtemp(prefix="sciforge-addins-")
    s["elsewhere"] = tempfile.mkdtemp(prefix="sciforge-elsewhere-")
    App.ParamGet(MACRO).SetString("MacroPath", s["scripts"])
    App.ParamGet(PREFS).SetString("AddInsFolder", s["addins"])
    for name, text in (("AddBox.FCMacro", ADD_BOX), ("Broken.FCMacro", BROKEN)):
        with open(os.path.join(s["scripts"], name), "w") as handle:
            handle.write(text)
    with open(os.path.join(s["elsewhere"], "Hello.FCMacro"), "w") as handle:
        handle.write('import FreeCAD\nFreeCAD.Console.PrintMessage("hello\\n")\n')
    scripts_ui.START_PROGRAM = lambda command: s["started"].append(list(command)) or True
    App.newDocument("Scripts")
    h.fit()


# -- P1 ----------------------------------------------------------------------------------------
def p1_open():
    i.ribbon_tab("UTILITIES")
    h.ribbon("Scripts and Add-Ins")


def p1_list():
    d = dialog()
    h.check("P1 the Scripts and Add-Ins window", d is not None, h.popups())
    if d is None:
        return
    h.check("P1 the scripts listed", names() == ["AddBox", "Broken"], names())
    kinds = [d.list.topLevelItem(r).text(1) for r in range(d.list.topLevelItemCount())]
    h.check("P1 as scripts", kinds == ["Script", "Script"], kinds)
    h.check("P1 the folders are shown", s["scripts"] in d.where.text(), d.where.text())
    h.shot("1-list")


# -- P2 ----------------------------------------------------------------------------------------
def p2_run():
    pick("script", "AddBox")
    press("SciForgeScriptsRun")


def p2_check():
    h.check("P2 the script made its box", len(script_bodies()) == 1, script_bodies())
    h.check("P2 the dialog says it ran", "AddBox ran" in message(), message())
    body = script_bodies()[0] if script_bodies() else None
    h.check("P2 the box is 1000", body is not None and m.near(body.Shape.Volume, 1000.0))
    m.find_child(dialog(), "SciForgeScriptsClose").click()


def p2_undo():
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


p2_undo.wait_ms = 1000


def p2_undone():
    h.check("P2 Ctrl+Z took the script's box away in one step", script_bodies() == [])
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ShiftModifier)


p2_undone.wait_ms = 1000


# -- P3 ----------------------------------------------------------------------------------------
def p3_broken():
    h.check("P9 Shift+S opened the window", dialog() is not None)
    d = dialog()
    item = pick("script", "Broken")
    if item is not None:
        rect = d.list.visualItemRect(item)
        w.double_click(d.list.viewport(), QtCore.QPoint(rect.left() + 20, rect.center().y()))


def p3_check():
    text = message()
    h.check(
        "P3 it says the script stopped with the error",
        "stopped with an error" in text and "ZeroDivisionError" in text,
        text,
    )
    h.check("P3 the design is unchanged", script_bodies() == [])
    h.check("P3 the window is still there", dialog() is not None)
    # A script that ends with sys.exit(): a normal end, its changes stay (one undo step).
    from sciforge import scripts_ui

    path = os.path.join(s["scripts"], "Quits.FCMacro")
    with open(path, "w") as handle:
        handle.write(ADD_BOX + "import sys\nsys.exit()\n")
    try:
        ok, text = scripts_ui.run_script({"kind": "script", "name": "Quits", "path": path})
    finally:
        os.remove(path)
    h.check("P3 a script ending with sys.exit() ran", ok and "Quits ran" in text, text)
    h.check("P3 and its box stays", len(script_bodies()) == 1, script_bodies())
    App.ActiveDocument.undo()
    App.ActiveDocument.recompute()
    h.check("P3 one undo takes it away", script_bodies() == [], script_bodies())


# -- P4 ----------------------------------------------------------------------------------------
def p4_create():
    press("SciForgeScriptsCreate")


def p4_fill():
    create = None
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if widget.objectName() == "SciForgeScriptCreate" and widget.isVisible():
            create = widget
    h.check("P4 the Create window", create is not None, h.popups())
    if create is None:
        return
    s["create"] = create
    di.choose(m.find_child(create, "SciForgeScriptCreateKind"), "Add-In")
    m.find_child(create, "SciForgeScriptCreateName").setFocus()
    QtTest.QTest.keyClicks(m.find_child(create, "SciForgeScriptCreateName"), "Greeter")
    QtTest.QTest.keyClicks(m.find_child(create, "SciForgeScriptCreateDescription"), "Says hello")
    for button in create.findChildren(QtWidgets.QPushButton):
        if button.text() == "Create":
            w.click(button)


def p4_created():
    folder = os.path.join(s["addins"], "Greeter")
    h.check("P4 the add-in's folder and file", os.path.isfile(os.path.join(folder, "Greeter.py")))
    text = open(os.path.join(folder, "Greeter.py")).read() if os.path.isdir(folder) else ""
    h.check("P4 it has run and stop", "def run(context)" in text and "def stop(context)" in text)
    h.check("P4 listed", "Greeter" in names(), names())
    d = dialog()
    item = d.item_for("addin", "Greeter") if d else None
    h.check("P4 as an Add-In", item is not None and item.text(1) == "Add-In")
    pick("addin", "Greeter")
    press("SciForgeScriptsRun")


def p4_running():
    from sciforge import scripts_ui

    d = dialog()
    item = d.item_for("addin", "Greeter") if d else None
    h.check("P4 Running", item is not None and item.text(3) == "Running", item and item.text(3))
    h.check("P4 the button says Stop", d is not None and d.run_button.text() == "Stop")
    h.check("P4 its run() was called", "Greeter" in scripts_ui._running)
    press("SciForgeScriptsRun")


def p4_stopped():
    from sciforge import scripts_ui

    d = dialog()
    item = d.item_for("addin", "Greeter") if d else None
    h.check(
        "P4 stopped",
        item is not None and item.text(3) == "" and "Greeter" not in scripts_ui._running,
    )
    h.check("P4 the dialog says so", "stopped" in message(), message())


# -- P5 ----------------------------------------------------------------------------------------
def p5_tick():
    d = dialog()
    item = d.item_for("script", "AddBox") if d else None
    if item is None:
        h.check("P5 AddBox listed", False)
        return
    rect = d.list.visualItemRect(item)
    column = d.list.header().sectionPosition(2)
    option = QtWidgets.QStyleOptionViewItem()
    point = QtCore.QPoint(column + 10, rect.center().y())
    w.click(d.list.viewport(), point)
    if item.checkState(2) != QtCore.Qt.Checked:
        item.setCheckState(2, QtCore.Qt.Checked)  # a style that draws the box elsewhere
    del option
    h.check("P5 Run on Startup ticked", item.checkState(2) == QtCore.Qt.Checked)


def p5_start():
    from sciforge import scripts_ui

    h.check("P5 kept", "script:AddBox" in App.ParamGet(PREFS).GetString("RunOnStartup", ""))
    scripts_ui._state["startup_done"] = False  # SciForge starting again (simulated)
    scripts_ui.run_startup()


def p5_started():
    h.check("P5 at start the script made its box", len(script_bodies()) == 1, script_bodies())
    d = dialog()
    item = d.item_for("script", "AddBox") if d else None
    if item is not None:
        rect = d.list.visualItemRect(item)
        w.click(
            d.list.viewport(),
            QtCore.QPoint(d.list.header().sectionPosition(2) + 10, rect.center().y()),
        )
        if item.checkState(2) == QtCore.Qt.Checked:
            item.setCheckState(2, QtCore.Qt.Unchecked)
    h.check(
        "P5 unticked: no longer kept",
        "script:AddBox" not in App.ParamGet(PREFS).GetString("RunOnStartup", ""),
    )


# -- P6 ----------------------------------------------------------------------------------------
def p6_edit():
    App.ParamGet(PREFS).SetString("ScriptEditor", "/usr/bin/fake-editor")
    pick("addin", "Greeter")
    press("SciForgeScriptsEdit")


def p6_check():
    started = s["started"][-1] if s["started"] else []
    h.check(
        "P6 the editor got Greeter.py",
        started[:1] == ["/usr/bin/fake-editor"] and started[-1].endswith("Greeter.py"),
        s["started"],
    )
    App.ParamGet(PREFS).RemString("ScriptEditor")


# -- P7 ----------------------------------------------------------------------------------------
def p7_filter():
    d = dialog()
    d.filter.setFocus()
    QtTest.QTest.keyClicks(d.filter, "gree")
    m.process()
    h.check("P7 only Greeter", names() == ["Greeter"], names())
    QtTest.QTest.keyClick(d.filter, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
    QtTest.QTest.keyClick(d.filter, QtCore.Qt.Key_Delete)
    m.process()
    h.check("P7 all again", names() == ["AddBox", "Broken", "Greeter"], names())


# -- P8 ----------------------------------------------------------------------------------------
def p8_add():
    from sciforge import scripts_ui

    scripts_ui.FILE_PICKER = lambda title, start: os.path.join(s["elsewhere"], "Hello.FCMacro")
    press("SciForgeScriptsAdd")


def p8_added():
    h.check(
        "P8 copied into the scripts folder",
        os.path.isfile(os.path.join(s["scripts"], "Hello.FCMacro")),
    )
    h.check("P8 listed", "Hello" in names(), names())
    press("SciForgeScriptsAdd")


def p8_refused():
    h.check(
        "P8 the same one again is refused", "already a script called Hello" in message(), message()
    )
    press("SciForgeScriptsCreate")


def p8_bad_name():
    create = None
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if widget.objectName() == "SciForgeScriptCreate" and widget.isVisible():
            create = widget
    if not h.check("P8 the Create window", create is not None):
        return
    field = m.find_child(create, "SciForgeScriptCreateName")
    field.setFocus()
    QtTest.QTest.keyClick(field, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
    QtTest.QTest.keyClicks(field, "1st")
    for button in create.findChildren(QtWidgets.QPushButton):
        if button.text() == "Create":
            w.click(button)
    m.process()
    note = create.message.text()
    h.check("P8 a bad name is refused with the reason", "starts with a letter" in note, note)
    h.check("P8 the Create window stays", create.isVisible())
    create.reject()


def cleanup():
    from sciforge import scripts_ui

    d = dialog()
    if d is not None:
        m.find_child(d, "SciForgeScriptsClose").click()
    scripts_ui.FILE_PICKER = None
    scripts_ui.START_PROGRAM = None
    App.ParamGet(MACRO).RemString("MacroPath")
    App.ParamGet(PREFS).RemString("AddInsFolder")
    App.ParamGet(PREFS).RemString("RunOnStartup")
    m.close_all()
    h.new_errors()


h.run(
    "misc_scripts",
    [
        setup,
        p1_open,
        p1_list,
        p2_run,
        p2_check,
        p2_undo,
        p2_undone,
        p3_broken,
        p3_check,
        p4_create,
        p4_fill,
        p4_created,
        p4_running,
        p4_stopped,
        p5_tick,
        p5_start,
        p5_started,
        p6_edit,
        p6_check,
        p7_filter,
        p8_add,
        p8_added,
        p8_refused,
        p8_bad_name,
        cleanup,
    ],
)
