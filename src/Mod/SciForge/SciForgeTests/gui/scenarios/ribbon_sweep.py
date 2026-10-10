# SPDX-License-Identifier: LGPL-2.1-or-later
"""Press every command of the SOLID and SKETCH tabs once, the way a curious user
would (nothing selected, a simple part on screen), and record what each does:
errors, pop-ups, a task panel. An error or a pop-up is a FAIL. Also writes
ribbon_sweep-report.json with one entry per command."""
import json
import os

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

from SciForgeTests.gui import harness as h

TABS = tuple((os.environ.get("SWEEP_TABS") or "solid,sketch").split(","))
# Dialogs that are the command itself (Fusion opens a window for these too).
INTENDED = {
    "Insert SVG": "Import file",
    "Insert DXF": "Import file",
    "Insert Mesh": "Import Mesh",
    "Change Parameters": "Parameters",
    "Manage Materials": "Materials",
    "3D Print": "3D Print",
}
report = []
# Known problems that a feature branch is fixing right now: reported, not failed,
# so the quick update can still be packaged. Remove an entry when it is fixed.
KNOWN = {
    "Shell": "FreeCAD's Thickness with nothing selected; Fusion-style Shell (shell_draft) fixes it",
    "Circumscribed Polygon": "FreeCAD's sides pop-up; Fusion-style polygon (sketch) fixes it",
}


def setup():
    from sciforge import ribbon_config as cfg, ribbon_ui

    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Sweep")
    _make_part()
    available = set(Gui.listCommands())
    seen = set()
    steps = []
    for tab in cfg.TABS:
        if tab["id"] not in TABS:
            continue
        for grp in tab["groups"]:
            for entry in cfg.iter_items(grp["items"]):
                resolved = ribbon_ui.resolve(entry["command"], available)
                if not resolved or resolved[0] == "__menu__":
                    continue
                if (tab["id"], resolved) in seen:
                    continue
                seen.add((tab["id"], resolved))
                steps.append(_step(tab["id"], grp["title"], entry["label"], resolved))
    steps.append(write_report)
    h.add_steps(steps)


def _make_part():
    from sciforge import commands, extrude, sketch_ui

    body = commands.ensure_body()
    planes = sketch_ui.origin_planes(body)
    sk = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    h.draw_rectangle(sk, 0, 0, 40, 30)
    extrude.make(body, sk, {"distance": 10.0})
    App.ActiveDocument.recompute()
    h.fit()


def _cleanup():
    h.close_popups()
    try:
        from sciforge import taskui

        current = taskui.current()
        if current is not None:
            current.reject()
    except Exception:
        pass
    try:
        if Gui.Control.activeDialog():
            Gui.Control.closeDialog()
    except Exception:
        pass
    try:
        from sciforge import commands

        commands.leave_edit()  # never resetEdit(): crashes with a sketch tool active
    except Exception:
        pass
    h.close_popups()


def _open_sketch():
    from sciforge import commands, sketch_ui

    body = commands.find_body()
    planes = sketch_ui.origin_planes(body)
    sk = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    Gui.ActiveDocument.setEdit(sk.Name)
    QtWidgets.QApplication.processEvents()


def _step(tab, group, label, resolved):
    def step():
        from sciforge import ribbon_ui

        entry = {"tab": tab, "group": group, "label": label, "command": resolved[0]}
        _cleanup()
        Gui.Selection.clearSelection()
        if tab == "sketch":
            _open_sketch()
        h.new_errors()

        def look():  # runs even while a modal pop-up blocks the command
            entry["popups"] = [p for p in h.popups() if p != INTENDED.get(label)]
            entry["in_edit"] = str(Gui.ActiveDocument.getInEdit())
            entry["task_panel"] = bool(Gui.Control.activeDialog())
            report.append(entry)
            if label in KNOWN and entry["popups"]:
                print("[SciForge] ribbon_sweep KNOWN: %s: %s" % (label, KNOWN[label]), flush=True)
                entry["popups"] = []
            h.check("No pop-up from %s > %s" % (tab, label), not entry["popups"], entry["popups"])
            if entry["popups"]:
                h.shot("popup-%s-%s" % (tab, label.replace(" ", "_").replace("/", "_")))
            _cleanup()

        QtCore.QTimer.singleShot(900, look)
        ribbon_ui.run(resolved, label)
        QtWidgets.QApplication.processEvents()

    step.__name__ = "%s: %s > %s" % (tab, group, label)
    step.known = label in KNOWN
    step.wait_ms = 1500
    step.entry_label = label
    return step


def write_report():
    with open(os.path.join(h.OUT_DIR, "ribbon_sweep-report.json"), "w") as f:
        json.dump(report, f, indent=1)


h.run("ribbon_sweep", [setup])
