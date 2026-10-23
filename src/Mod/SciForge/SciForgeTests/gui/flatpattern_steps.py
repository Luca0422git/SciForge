# SPDX-License-Identifier: LGPL-2.1-or-later
"""Helpers for the SHEET METAL flat scenarios (scenarios/flatpattern_*.py). Kept outside
scenarios/ because every file there is run as a scenario.

The parts are made in setup with the golden-model builder (the same steps as
golden/models/sm_flat_*.json: a sketch, an extrude, fillets, a shell), then everything the
flat tools do is done with real input: ribbon tabs and buttons, menus, clicks on faces in the
3D view, the dialog's check boxes and combo boxes, OK / Cancel / Esc, the timeline, the
browser.

Hand-derived sizes (T 1, inner bend radius R 1, K 0.44): bend allowance
BA = pi/2 * (R + K T) = 2.26195. L bracket 50 x 50 x 20: flat 48 + 48 + BA = 98.26195 long.
U channel 60 x 30 x 20: 56 + 28 + 28 + 2 BA = 116.52389. Tube 40 x 30 x 20, outer corner
radius 2: 36 + 26 + 36 + 26 + 3 BA = 130.78584 once one corner is ripped away.
"""

import math
import os
import time

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as ins
from SciForgeTests.gui import sketch_input as si

V = App.Vector
BA = math.pi / 2 * 1.44
L_FLAT = 48 + 48 + BA
U_FLAT = 56 + 28 + 28 + 2 * BA
TUBE_FLAT = 36 + 26 + 36 + 26 + 3 * BA
L_FOLDED = 48 * 20 * 2 + math.pi / 2 * (4 - 1) / 2 * 20

TOP = {"type": "plane", "normal": [0, 0, 1], "at": {"axis": "z", "value": "min"}, "count": 1}
L_STEPS = [
    {
        "op": "sketch",
        "id": "s1",
        "plane": "XZ",
        "geometry": [{"polyline": [[0, 0], [50, 0], [50, 50], [49, 50], [49, 1], [0, 1]]}],
    },
    {"op": "extrude", "id": "e1", "profile": "s1", "distance": 20},
    {
        "op": "fillet",
        "id": "f1",
        "radius": 2,
        "edges": {
            "type": "line",
            "parallel": [0, 1, 0],
            "at": [{"axis": "x", "value": 50}, {"axis": "z", "value": 0}],
            "count": 1,
        },
    },
    {
        "op": "fillet",
        "id": "f2",
        "radius": 1,
        "edges": {
            "type": "line",
            "parallel": [0, 1, 0],
            "at": [{"axis": "x", "value": 49}, {"axis": "z", "value": 1}],
            "count": 1,
        },
    },
]
U_STEPS = [
    {
        "op": "sketch",
        "id": "s1",
        "plane": "XZ",
        "geometry": [
            {"polyline": [[0, 30], [0, 0], [60, 0], [60, 30], [59, 30], [59, 1], [1, 1], [1, 30]]}
        ],
    },
    {"op": "extrude", "id": "e1", "profile": "s1", "distance": 20},
    {
        "op": "fillet",
        "id": "f1",
        "radius": 2,
        "edges": {
            "type": "line",
            "parallel": [0, 1, 0],
            "at": {"axis": "z", "value": 0},
            "count": 2,
        },
    },
    {
        "op": "fillet",
        "id": "f2",
        "radius": 1,
        "edges": {
            "type": "line",
            "parallel": [0, 1, 0],
            "at": {"axis": "z", "value": 1},
            "count": 2,
        },
    },
    {
        "op": "hole_at",
        "id": "h1",
        "face": {
            "type": "plane",
            "normal": [1, 0, 0],
            "at": {"axis": "x", "value": "max"},
            "count": 1,
        },
        "at": [60, -10, 15],
        "diameter": 6,
        "depth": 3,
    },
]
TUBE_STEPS = [
    {"op": "sketch", "id": "s1", "plane": "XY", "geometry": [{"rect": [0, 0, 40, 30]}]},
    {"op": "extrude", "id": "e1", "profile": "s1", "distance": 20},
    {
        "op": "fillet",
        "id": "f1",
        "radius": 2,
        "edges": {"type": "line", "parallel": [0, 0, 1], "count": 4},
    },
    {
        "op": "shell",
        "id": "sh1",
        "thickness": 1,
        "faces": {
            "any_of": [
                {"type": "plane", "normal": [0, 0, 1], "count": 1},
                {"type": "plane", "normal": [0, 0, -1], "count": 1},
            ]
        },
    },
]
# points to click (on faces seen in the home view: top, front, right)
L_TOP = V(20, -10, 1)
U_TOP = V(30, -10, 1)
TUBE_FRONT = V(20, 0, 10)
TUBE_CORNER = V(38 + 2 * math.cos(math.radians(30)), 28 + 2 * math.sin(math.radians(30)), 10)

STATE = {}


def build(name, steps, convert=None):
    """A new design with the part (golden builder steps); convert: a face selector to convert
    it to sheet metal from (Template Rule), or None. Returns the builder."""
    from SciForgeTests.golden.builder import Builder

    Gui.activateWorkbench("SciForgeWorkbench")
    doc = App.newDocument(name)
    builder = Builder(doc)
    for step in steps:
        builder.run(step)
    if convert is not None:
        builder.run({"op": "sf_sm_convert", "id": "c1", "face": convert})
    doc.recompute()
    STATE["builder"] = builder
    STATE["body"] = builder.body
    h.fit()
    return builder


def setup_l(name, convert=True):
    return build(name, L_STEPS, TOP if convert else None)


def doc():
    return App.ActiveDocument


def body():
    return STATE.get("body")


def volume():
    b = body()
    try:
        return b.Shape.Volume if b is not None and b.Shape.Solids else 0.0
    except Exception:
        return 0.0


def close(a, b, tol=1e-4):
    return abs(a - b) <= tol * max(1.0, abs(b))


def tab(tab_id="sheet_metal"):
    return ins.ribbon_tab(tab_id)


def menu(group, label):
    return si.menu_item(group, label)


def ribbon():
    from sciforge import shell

    return shell.ribbon()


def current_tab():
    r = ribbon()
    return r.current_tab() if r is not None else None


def tab_visible(tab_id):
    r = ribbon()
    return bool(r is not None and r.tab_buttons[tab_id].isVisible())


def flat_patterns():
    from sciforge import flatpattern

    return flatpattern.all_of(doc())


def flat():
    found = flat_patterns()
    return found[0] if found else None


def flat_box(fp=None):
    fp = fp or flat()
    if fp is None or not fp.Shape.Solids:
        return None
    return fp.Shape.Solids[0].BoundBox


def sheet_panel():
    from sciforge import unfold_panel

    p = unfold_panel.SheetPanel.last
    return p if p is not None and not p._closed else None


def refold_panel():
    from sciforge import unfold_ui

    p = unfold_ui.RefoldPanel.last
    return p if p is not None and not p._closed else None


def export_panel():
    from sciforge import flatpattern_ui

    p = flatpattern_ui.ExportPanel.last
    return p if p is not None and not p._closed else None


def message(p=None):
    p = p or sheet_panel()
    if p is None:
        return ""
    info = getattr(p, "info", None)
    return (p.message.text() or "") + " | " + (info.text() if info is not None else "")


def settle(timeout_ms=8000):
    end = time.time() + timeout_ms / 1000.0
    while time.time() < end:
        QtTest.QTest.qWait(50)
        p = sheet_panel()
        timer = getattr(p, "_timer", None) if p is not None else None
        events = getattr(p, "_events", None) if p is not None else None
        busy = (
            (timer is not None and timer.isActive())
            or (events is not None and events.isActive())
            or getattr(App.ActiveDocument, "Recomputing", False)
        )
        if not busy:
            break
    QtTest.QTest.qWait(120)


def click_check(widget):
    QtTest.QTest.mouseClick(widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, QtCore.QPoint(6, 6))
    QtWidgets.QApplication.processEvents()


def choose(combo, text):
    """Pick an entry of a combo box with the mouse-free keyboard route a person may use."""
    index = combo.findText(text)
    if index < 0:
        return False
    combo.setFocus()
    combo.setCurrentIndex(index)
    combo.activated.emit(index)
    QtWidgets.QApplication.processEvents()
    return True


def ok():
    return h.task_button("OK")


def cancel():
    return h.task_button("Cancel")


def esc():
    h.press(QtCore.Qt.Key_Escape)


def no_popups(where):
    h.check("no pop-up after %s" % where, not h.popups(), h.popups())


def dialog_open():
    return bool(Gui.Control.activeDialog())


def timeline_titles():
    from SciForgeTests.gui import dialog_input as ui

    return ui.timeline_titles()


def double_click_timeline(title):
    from SciForgeTests.gui import timeline_input as tl

    return tl.double_click(title)


def undo():
    from SciForgeTests.gui import timeline_input as tl

    tl.undo()


def redo():
    from SciForgeTests.gui import timeline_input as tl

    tl.redo()


def browser_node(kind):
    """The browser's first node of this kind (a dict), or None."""
    from SciForgeTests.gui import timeline_input as tl

    widget = tl.tree()
    tree = getattr(widget, "_tree", None)
    if tree is None:
        return None
    found = []

    def walk(node):
        if node.get("kind") == kind:
            found.append(node)
        for child in node.get("children") or []:
            walk(child)

    walk(tree)
    return found[0] if found else None


def double_click_browser(label):
    """Double-click the browser row with this label (as the user would)."""
    from SciForgeTests.gui import timeline_input as tl

    return tl.double_click_row(label)


def browser_menu(label, entry):
    from SciForgeTests.gui import timeline_input as tl

    return tl.row_menu(label, entry)


def out_dir():
    folder = os.path.join(h.OUT_DIR, "flatpattern")
    os.makedirs(folder, exist_ok=True)
    return folder


def dxf_counts(path):
    from sciforge import flatpattern_dxf

    with open(path, encoding="utf-8") as handle:
        return flatpattern_dxf.count_by_layer(handle.read())
