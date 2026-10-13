# SPDX-License-Identifier: LGPL-2.1-or-later
"""Real-input helpers for the direct-modeling and Modify scenarios (scenarios/direct_*.py,
scenarios/modify_*.py): the design's right-click menu (Capture Design History), the question
before history goes, the Finish Base Feature bar, the Press Pull / Offset Face / Modify
dialogs, STEP files made with FreeCAD's own Part / Import for test input. Not a scenario
(it lives outside scenarios/)."""
import os

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtWidgets

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import timeline_input as t
from SciForgeTests.gui import widget_input as w

V = App.Vector


def doc():
    return App.ActiveDocument


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def bodies():
    d = doc()
    return sorted(d.findObjects("PartDesign::Body"), key=lambda o: o.ID) if d else []


def body_labelled(label):
    for body in bodies():
        if body.Label == label:
            return body
    return None


def volume(obj):
    try:
        return obj.Shape.Volume if obj is not None and not obj.Shape.isNull() else 0.0
    except Exception:
        return 0.0


def solid_steps(body):
    return [o for o in body.Group if "BaseFeature" in o.PropertiesList]


def is_direct():
    from sciforge import direct

    return direct.is_direct(doc())


def session():
    from sciforge import direct

    return direct.session(doc())


def timeline_shown():
    from sciforge import timeline_ui

    dock = timeline_ui._dock
    QtWidgets.QApplication.processEvents()
    return bool(dock is not None and dock.isVisible())


def wait_timeline():
    """Let the timeline's 0.4 s refresh run (it hides itself for a design without history)."""
    from PySide6 import QtTest

    QtTest.QTest.qWait(500)


# -- the design's right-click menu ------------------------------------------------------------
def design_menu(entry):
    """Right-click the design's top row in the browser and choose ``entry``."""
    return t.row_menu(doc().Label, entry)


def design_menu_entries():
    return [text for text, _enabled in t.row_menu_entries(doc().Label)]


def history_dialog():
    from sciforge import direct_ui

    return direct_ui.history_dialog()


def answer_history(remove=True):
    """Click Remove History (or Cancel) in the question before history goes."""
    dialog = history_dialog()
    if not h.check("the question before history goes is open", dialog is not None):
        return False
    name = "SciForgeHistoryOffRemove" if remove else "SciForgeHistoryOffCancel"
    button = dialog.findChild(QtWidgets.QPushButton, name)
    if not h.check("button %s" % name, button is not None):
        return False
    w.click(button)
    return True


# -- the Finish Base Feature bar ------------------------------------------------------------------
def bar():
    from sciforge import direct_ui

    return direct_ui.bar()


def finish_bar():
    widget = bar()
    if not h.check("the Finish Base Feature bar is shown", widget is not None):
        return False
    w.click(widget.button)
    return True


# -- dialogs ---------------------------------------------------------------------------------------
def panel():
    from sciforge import taskui

    return taskui.current()


def press_pull_panel():
    from sciforge import presspull_ui

    p = presspull_ui.PressPullPanel.last
    return p if p is not None and not p._closed else None


def type_distance(text):
    p = press_pull_panel()
    if not h.check("Press Pull dialog open", p is not None):
        return False
    ui.type_into(p.field.widget, text)
    return True


def click_box(name):
    p = panel()
    fields = getattr(p, "fields", {})
    if h.check("dialog has a %s box" % name, name in fields, list(fields)):
        w.click(fields[name].button)


def choose(combo_attr, text):
    p = panel()
    combo = getattr(p, combo_attr, None)
    if h.check("dialog has %s" % combo_attr, combo is not None):
        ui.choose(combo, text)


def message():
    p = panel()
    try:
        return p.message.text() if p is not None else ""
    except RuntimeError:
        return ""


def ribbon_menu(group, label):
    from SciForgeTests.gui import sketch_input

    return sketch_input.menu_item(group, label)


# -- STEP files for test input (made with FreeCAD's own Part / Import, as Luca's downloads) ----
def step_file(name, shape):
    """Write ``shape`` as a STEP file in the scenario's output folder; returns the path."""
    path = os.path.join(h.OUT_DIR, "%s-%s.step" % (h.state["name"], name))
    shape.exportStep(path)
    return path


def import_step(path):
    """FreeCAD's own STEP import (File > Import): plain solids, no history. Returns the new
    solids."""
    import Import

    d = doc()
    before = {o.Name for o in d.Objects}
    Import.insert(path, d.Name)
    d.recompute()
    found = []
    for obj in d.Objects:
        if obj.Name in before:
            continue
        try:
            if obj.isDerivedFrom("Part::Feature") and obj.Shape.Solids:
                found.append(obj)
        except Exception:
            continue
    return found


def plain_solids():
    from sciforge import direct

    return [o for o in doc().Objects if direct.is_adoptable(o)]


def shown(obj):
    try:
        return bool(obj.ViewObject.Visibility)
    except Exception:
        return False


def selected():
    return [(x.ObjectName, list(x.SubElementNames)) for x in Gui.Selection.getSelectionEx()]


def told():
    """The last note SciForge put next to the pointer (commands.tell)."""
    from sciforge import commands

    return commands._TOLD.get("msg") or ""
