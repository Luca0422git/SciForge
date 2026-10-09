# SPDX-License-Identifier: LGPL-2.1-or-later
"""GUI smoke test for the SciForge workbench, run inside a real FreeCAD GUI.

Run it by passing this file to the FreeCAD GUI executable (CI uses a virtual
screen via xvfb-run):

    SCIFORGE_SMOKE_OUT=/some/dir FreeCAD smoke_gui.py

It activates the workbench, checks toolbars, shortcuts and diagnostics, builds
a small part, checks the timeline, saves a screenshot and writes
result.json into SCIFORGE_SMOKE_OUT. FreeCAD's own exit code is not reliable
for this, so the runner script reads result.json to decide pass/fail.
"""
import json
import os
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

OUT_DIR = os.environ.get("SCIFORGE_SMOKE_OUT") or App.getUserAppDataDir()
EXPECTED_TOOLBARS = ["SciForge Design", "SciForge Sketch", "SciForge View"]
EXPECTED_SHORTCUTS = {
    "SciForge_CommandSearch": "S",
    "PartDesign_Pad": "E",
    "Sketcher_CreateLine": "L",
}

checks = []  # (name, ok, detail)
errors = []  # every [SciForge] error printed to the console


class _ErrorCatcher:
    """Collects console errors so a swallowed exception still fails the test."""

    def __init__(self):
        self._real = App.Console.PrintError

    def __call__(self, msg):
        if "[SciForge]" in msg:
            errors.append(msg.strip())
        self._real(msg)


def check(name, ok, detail=""):
    checks.append({"name": name, "ok": bool(ok), "detail": str(detail)})


def _build_part():
    import Part

    from sciforge import commands

    Gui.runCommand("SciForge_NewDesign")
    body = commands.active_body()
    check("New Design creates an active body", body is not None)
    if body is None:
        return None
    sketch = body.newObject("Sketcher::SketchObject", "Sketch")
    sketch.AttachmentSupport = (body.Origin.OriginFeatures[3], [""])  # XY plane
    sketch.MapMode = "FlatFace"
    v = App.Vector
    corners = [v(0, 0, 0), v(40, 0, 0), v(40, 20, 0), v(0, 20, 0)]
    for i in range(4):
        sketch.addGeometry(Part.LineSegment(corners[i], corners[(i + 1) % 4]))
    pad = body.newObject("PartDesign::Pad", "Pad")
    pad.Profile = sketch
    pad.Length = 10
    App.ActiveDocument.recompute()
    check("Pad volume is 8000 mm^3", abs(pad.Shape.Volume - 8000.0) < 1e-6, pad.Shape.Volume)
    return body


def step_one():
    try:
        Gui.activateWorkbench("SciForgeWorkbench")
        check(
            "Workbench activates",
            Gui.activeWorkbench().name() == "SciForgeWorkbench",
            Gui.activeWorkbench().name(),
        )

        from sciforge import diagnostics, registry

        report = diagnostics.report()
        missing = sorted(set(registry.MISSING))
        check("All configured commands exist", not missing, ", ".join(missing))

        main = Gui.getMainWindow()
        visible = [t.windowTitle() for t in main.findChildren(QtWidgets.QToolBar) if t.isVisible()]
        for title in EXPECTED_TOOLBARS:
            check("Toolbar visible: %s" % title, title in visible, visible)

        for name, key in EXPECTED_SHORTCUTS.items():
            cmd = Gui.Command.get(name)
            got = cmd.getShortcut() if cmd else None
            check("Shortcut %s = %s" % (name, key), got == key, got)

        _build_part()
        with open(os.path.join(OUT_DIR, "diagnostics.txt"), "w", encoding="utf-8") as handle:
            handle.write(report + "\n")
    except Exception:
        check("No exception in step one", False, traceback.format_exc())
    # The timeline refreshes on a timer, so give it time before reading it.
    QtCore.QTimer.singleShot(1500, step_two)


def step_two():
    try:
        from sciforge import timeline_ui

        widget = timeline_ui._dock.widget() if timeline_ui._dock else None
        titles = []
        if widget is not None:
            row = widget._row
            titles = [
                row.itemAt(i).widget().text() for i in range(row.count()) if row.itemAt(i).widget()
            ]
        check("Timeline shows Sketch 1, Extrude 1", titles == ["Sketch 1", "Extrude 1"], titles)

        shot = os.path.join(OUT_DIR, "screenshot.png")
        check("Screenshot saved", Gui.getMainWindow().grab().save(shot), shot)

        Gui.activateWorkbench("PartDesignWorkbench")
        cmd = Gui.Command.get("PartDesign_Pad")
        check(
            "Shortcuts restored after leaving the workbench",
            cmd.getShortcut() != "E",
            cmd.getShortcut(),
        )
    except Exception:
        check("No exception in step two", False, traceback.format_exc())
    finish()


def finish():
    check("No [SciForge] errors on the console", not errors, errors)
    result = {"passed": all(c["ok"] for c in checks), "checks": checks}
    with open(os.path.join(OUT_DIR, "result.json"), "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
    for c in checks:
        App.Console.PrintMessage(
            "[SciForge] smoke %s: %s %s\n"
            % ("PASS" if c["ok"] else "FAIL", c["name"], "" if c["ok"] else c["detail"])
        )
    for doc in list(App.listDocuments()):
        App.closeDocument(doc)
    QtCore.QTimer.singleShot(200, QtWidgets.QApplication.instance().quit)


App.Console.PrintError = _ErrorCatcher()
# Wait for the main window and start-up modules to settle first.
QtCore.QTimer.singleShot(2000, step_one)
