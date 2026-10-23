# SPDX-License-Identifier: LGPL-2.1-or-later
"""Real-input helpers for the PLASTIC part 2 scenarios (scenarios/plastic2_*.py): Snap Fit, Lip
and Design Advice. Kept outside scenarios/ because every file there is run as a scenario.

The enclosure the scenarios start from is made in their setup (a 60 x 40 x 20 base shelled
2 mm with its top open, a lid on it); everything about the commands under test is done
with the mouse and keyboard: the PLASTIC tab, its buttons and menus, clicks on sketch
points, edges and browser rows, typing into the dialog's fields, dragging its arrows,
double-clicking the timeline, Esc / OK / Cancel, Undo / Redo."""

import time

import FreeCAD as App
import FreeCADGui as Gui
import Part
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import arrow_input as ai
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as ins
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import timeline_input as tl

V = App.Vector
BASE = 60 * 40 * 20 - 56 * 36 * 18  # 11712
LID_PLATE = 60 * 40 * 2  # 4800
LID_SHELL = 60 * 40 * 10 - 56 * 36 * 8  # 7872
GROOVE = 1.1 * 6.2 * 3.2  # 21.824: one snap fit's groove with the default rule


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def doc():
    return App.ActiveDocument


def by_label(label):
    found = doc().getObjectsByLabel(label) if doc() is not None else []
    return found[0] if found else None


def volume(obj):
    try:
        if obj is None or obj.Shape.isNull() or not obj.Shape.Solids:
            return 0.0
        return obj.Shape.Volume
    except Exception:
        return 0.0


# -- the enclosure ---------------------------------------------------------------------------
def _box(body, kind, name, size, at):
    obj = body.newObject("PartDesign::%sBox" % kind, name)
    obj.Length, obj.Width, obj.Height = size
    obj.Placement = App.Placement(V(*at), App.Rotation())
    body.Tip = obj
    return obj


def enclosure(name, lid="plate"):
    """A new design with the base (60 x 40 x 20, 2 mm walls, open top) and a lid on it:
    "plate" (2 mm) or "shell" (60 x 40 x 10, 2 mm walls, open bottom)."""
    Gui.activateWorkbench("SciForgeWorkbench")
    d = App.newDocument(name)
    base = d.addObject("PartDesign::Body", "Base")
    base.Label = "Base"
    _box(base, "Additive", "BaseBox", (60, 40, 20), (0, 0, 0))
    _box(base, "Subtractive", "BaseCavity", (56, 36, 20), (2, 2, 2))
    top = d.addObject("PartDesign::Body", "Lid")
    top.Label = "Lid"
    if lid == "shell":
        _box(top, "Additive", "LidBox", (60, 40, 10), (0, 0, 20))
        _box(top, "Subtractive", "LidCavity", (56, 36, 8), (2, 2, 20))
    else:
        _box(top, "Additive", "LidBox", (60, 40, 2), (0, 0, 20))
    d.recompute()
    return base, top


def points_sketch(body, points, label="SnapPoints", z=20.0):
    """A sketch of points on the plane z (the parting plane)."""
    sk = body.newObject("Sketcher::SketchObject", label)
    sk.Label = label
    sk.Placement = App.Placement(V(0, 0, z), App.Rotation())
    for x, y in points:
        sk.addGeometry(Part.Point(V(x, y, 0)), False)
    doc().recompute()
    return sk


# -- the ribbon -------------------------------------------------------------------------------
def plastic_tab():
    return ins.ribbon_tab("plastic")


def menu(group, label):
    return si.menu_item(group, label)


# -- the dialogs -----------------------------------------------------------------------------
def snap_panel():
    from sciforge import plastic_snap_ui

    p = plastic_snap_ui.SnapFitPanel.last
    return p if p is not None and not p._closed else None


def lip_panel():
    from sciforge import plastic_lip_ui

    p = plastic_lip_ui.LipPanel.last
    return p if p is not None and not p._closed else None


def advice_panel():
    from sciforge import plastic_advice_ui

    p = plastic_advice_ui.DesignAdvicePanel.last
    return p if p is not None and not p._closed else None


def settle(panel_fn, timeout_ms=8000):
    """Let the open dialog's preview catch up (its timer done, no recompute running)."""
    end = time.time() + timeout_ms / 1000.0
    while time.time() < end:
        QtTest.QTest.qWait(50)
        p = panel_fn()
        if p is None:
            break
        timer = getattr(p, "_timer", None)
        busy = (
            (timer is not None and timer.isActive())
            or getattr(p, "_pending", False)
            or getattr(App.ActiveDocument, "Recomputing", False)
        )
        if not busy:
            break
    QtTest.QTest.qWait(100)


def type_field(panel, key, text):
    """Type into the dialog's number field `key` and leave it (Tab)."""
    if panel is None:
        h.check("dialog open to type %s" % key, False)
        return False
    ui.type_into(panel.fields[key].widget, text)
    return True


def choose(combo, text):
    return h.check("chose %s" % text, ui.choose(combo, text))


def toggle(checkbox):
    QtTest.QTest.mouseClick(
        checkbox, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, QtCore.QPoint(6, 6)
    )
    QtWidgets.QApplication.processEvents()


def message(panel):
    return panel.message.text() if panel is not None else ""


def drag_arrow(panel, key, to_distance):
    """Grab the dialog's arrow `key` at its head and drag it to about `to_distance`."""
    dragger = panel.arrows.get(key) if panel is not None else None
    if dragger is None:
        h.check("arrow %s shown" % key, False)
        return None
    head = ai.head_point(dragger)
    start = h.screen_point(head)
    # the hand keeps hold of the head: it moves as far as the value has to
    value_point = dragger.origin + dragger.direction * dragger.distance()
    end = h.screen_point(head + dragger.direction * to_distance - (value_point - dragger.origin))
    drag = ai.HeldDrag(start, end, moves=30, every_ms=25, hold_ms=300)
    drag.run()
    return drag


def ok():
    return h.task_button("OK")


def cancel():
    return h.task_button("Cancel")


def esc():
    h.press(QtCore.Qt.Key_Escape)


def undo():
    tl.undo()


def redo():
    tl.redo()


def titles():
    return ui.timeline_titles()


def double_click_timeline(title):
    return ui.double_click_timeline(title)


def click_row(label):
    return tl.click_row(label)


def click_eye(label):
    return tl.click_eye(label)


def followers(feature):
    from sciforge import modify_bodies

    return modify_bodies.followers_of(feature) if feature is not None else []


def snap_steps():
    from sciforge import plastic_snap

    return [o for o in doc().Objects if plastic_snap.is_snap_fit(o)]


def lip_steps():
    from sciforge import plastic_lip

    return [o for o in doc().Objects if plastic_lip.is_lip(o)]


def no_popups(where):
    return h.check("no pop-up after %s" % where, not h.popups(), h.popups())
