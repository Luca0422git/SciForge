# SPDX-License-Identifier: LGPL-2.1-or-later
"""Every command of the SKETCH tab's CREATE, MODIFY and CONSTRAINTS menus, clicked in
its menu with the mouse, in a sketch that already has curves and with nothing
selected (the ribbon sweep only tries an empty sketch). Each must start without a
pop-up, without a FreeCAD notification balloon and without an error; Esc must then
stop it and leave the sketch open. Writes sketch_sweep-report.json."""
import json
import os

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si

V = App.Vector
GROUPS = ("CREATE", "MODIFY", "CONSTRAINTS")
report = []
s = {}


def setup():
    from sciforge import commands, ribbon_config as cfg, ribbon_ui, sketch_ui

    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("SketchSweep")
    body = commands.ensure_body()
    planes = sketch_ui.origin_planes(body)
    sk = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    h.draw_rectangle(sk, 0, 0, 40, 30)
    h.draw_circle(sk, 60, 15, 8)
    s["sk"] = sk
    available = set(Gui.listCommands())
    tab = [t for t in cfg.TABS if t["id"] == "sketch"][0]
    steps = [open_sketch]
    seen = set()
    for grp in tab["groups"]:
        if grp["title"] not in GROUPS:
            continue
        for entry in cfg.iter_items(grp["items"]):
            resolved = ribbon_ui.resolve(entry["command"], available)
            if not resolved or entry["label"] in seen:
                continue
            seen.add(entry["label"])
            steps += _steps(grp["title"], entry["label"], resolved[0])
    steps.append(write_report)
    h.add_steps(si.watched(steps))


def open_sketch():
    si.timeline_double_click("Sketch 1")


def _steps(group, label, command):
    entry = {"group": group, "label": label, "command": command}

    def start():
        h.press(QtCore.Qt.Key_Escape)
        h.press(QtCore.Qt.Key_Escape)
        Gui.Selection.clearSelection()
        h.new_errors()
        si.menu_item(group, label)

    def look():
        from PySide import QtWidgets

        entry["popups"] = h.popups()
        entry["in_sketch"] = h.in_sketch() is s["sk"]
        entry["tool"] = h.gl_widget().cursor().shape() != QtCore.Qt.ArrowCursor
        entry["tip"] = QtWidgets.QToolTip.text() if QtWidgets.QToolTip.isVisible() else ""
        h.check("%s: no pop-up" % label, not entry["popups"], entry["popups"])
        h.close_popups()
        h.press(QtCore.Qt.Key_Escape)

    def after():
        entry["still_in_sketch"] = h.in_sketch() is s["sk"]
        h.check("%s: Esc leaves the sketch open" % label, entry["still_in_sketch"])
        report.append(entry)
        if not entry["still_in_sketch"]:
            open_sketch()

    for f, name in ((start, "start"), (look, "look"), (after, "after")):
        f.__name__ = "%s > %s (%s)" % (group, label, name)
    look.wait_ms = 400
    return [start, look, after]


def write_report():
    with open(os.path.join(h.OUT_DIR, "sketch_sweep-report.json"), "w") as f:
        json.dump(report, f, indent=1)
    h.ribbon("Finish Sketch")


h.run("sketch_sweep", [setup])
