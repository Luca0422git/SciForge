# SPDX-License-Identifier: LGPL-2.1-or-later
"""GUI smoke test for the SciForge interface, run inside a real FreeCAD GUI.

Run it by passing this file to the FreeCAD GUI executable (CI uses a virtual
screen via xvfb-run):

    SCIFORGE_SMOKE_OUT=/some/dir FreeCAD smoke_gui.py

It switches to SciForge, checks the ribbon, theme, shortcuts and timeline,
builds a small part, opens a sketch (the SKETCH tab must appear and the ribbon
must stay), leaves SciForge (FreeCAD must be restored), saves screenshots and
writes result.json into SCIFORGE_SMOKE_OUT. FreeCAD's own exit code is not
reliable for this, so the runner script reads result.json to decide pass/fail.
"""
import json
import os
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

OUT_DIR = os.environ.get("SCIFORGE_SMOKE_OUT") or App.getUserAppDataDir()
EXPECTED_SHORTCUTS = {
    "SciForge_CommandSearch": "S",
    "PartDesign_Pad": "E",
    "Sketcher_CreateLine": "L",
}

checks = []  # (name, ok, detail)
errors = []  # every [SciForge] error printed to the console
state = {}


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


def later(ms, fn):
    def guarded():
        try:
            fn()
        except Exception:
            check("No exception in %s" % fn.__name__, False, traceback.format_exc())
            finish()

    QtCore.QTimer.singleShot(ms, guarded)


def shot(name):
    """Screenshot of the whole virtual screen (includes open menus)."""
    path = os.path.join(OUT_DIR, name)
    screen = QtWidgets.QApplication.primaryScreen()
    ok = screen.grabWindow(0).save(path)
    check("Screenshot %s" % name, ok, path)


def visible_toolbars():
    main = Gui.getMainWindow()
    return [t.objectName() for t in main.findChildren(QtWidgets.QToolBar) if t.isVisible()]


def _build_part():
    import Part

    from sciforge import commands

    Gui.runCommand("SciForge_NewDesign")
    body = commands.active_body()
    check("New Design creates an active body", body is not None)
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
    state["sketch"] = sketch


def step_activate():
    state["qss_before"] = QtWidgets.QApplication.instance().styleSheet()
    state["toolbars_before"] = visible_toolbars()
    Gui.activateWorkbench("SciForgeWorkbench")
    later(800, step_ribbon)


def step_ribbon():
    from sciforge import registry, ribbon_ui, shell

    check("Workbench activates", Gui.activeWorkbench().name() == "SciForgeWorkbench")
    check(
        "All configured commands exist",
        not sorted(set(registry.MISSING)),
        sorted(set(registry.MISSING)),
    )
    ribbon = shell.ribbon()
    check("Ribbon visible", ribbon is not None and ribbon.isVisible())
    check(
        "Only the ribbon toolbar is visible",
        visible_toolbars() == ["SciForgeRibbonBar"],
        visible_toolbars(),
    )
    check("Menu bar hidden like Fusion", not Gui.getMainWindow().menuBar().isVisible())
    check("SOLID tab selected", ribbon.current_tab() == "solid", ribbon.current_tab())
    check("SKETCH tab hidden outside sketches", not ribbon.tab_buttons["sketch"].isVisible())
    groups = ribbon.findChildren(ribbon_ui.GroupWidget)
    solid_titles = [g.group["title"] for g in groups if g.isVisible()]
    check(
        "SOLID groups in Fusion's order",
        solid_titles[:3] == ["CREATE", "MODIFY", "CONSTRUCT"],
        solid_titles,
    )
    check("Dark theme applied", "SciForgeRibbon" in QtWidgets.QApplication.instance().styleSheet())
    for name, key in EXPECTED_SHORTCUTS.items():
        cmd = Gui.Command.get(name)
        got = cmd.getShortcut() if cmd else None
        check("Shortcut %s = %s" % (name, key), got == key, got)
    distx = Gui.Command.get("Sketcher_ConstrainDistanceX")
    check(
        "Clashing FreeCAD key parked (L)",
        distx is None or distx.getShortcut() == "",
        distx and distx.getShortcut(),
    )
    _build_part()
    Gui.SendMsgToActiveView("ViewFit")
    later(1200, step_timeline)


def step_timeline():
    from sciforge import shell, timeline_ui

    widget = timeline_ui._dock.widget() if timeline_ui._dock else None
    titles = widget.titles() if widget else []
    check("Timeline shows Sketch 1, Extrude 1", titles == ["Sketch 1", "Extrude 1"], titles)
    shot("screenshot.png")
    # Open the CREATE menu without blocking, for a screenshot of a drop-down.
    group = [
        g
        for g in shell.ribbon().findChildren(__import__("sciforge.ribbon_ui").ribbon_ui.GroupWidget)
        if g.isVisible()
    ][0]
    group.menu.popup(group.label.mapToGlobal(QtCore.QPoint(0, group.label.height())))
    state["menu"] = group.menu
    later(500, step_menu_shot)


def step_menu_shot():
    shot("screenshot-menu.png")
    state["menu"].hide()
    Gui.ActiveDocument.setEdit(state["sketch"].Name)
    later(1200, step_sketch)


def step_sketch():
    from sciforge import shell

    ribbon = shell.ribbon()
    check("Editing a sketch keeps the SciForge interface", shell.is_on())
    check(
        "SKETCH tab shown while sketching",
        ribbon.current_tab() == "sketch" and ribbon.tab_buttons["sketch"].isVisible(),
        ribbon.current_tab(),
    )
    check(
        "Sketcher toolbars stay hidden",
        visible_toolbars() == ["SciForgeRibbonBar"],
        visible_toolbars(),
    )
    shot("screenshot-sketch.png")
    Gui.ActiveDocument.resetEdit()
    later(1000, step_after_sketch)


def step_after_sketch():
    from sciforge import shell

    check(
        "Back to SOLID after the sketch",
        shell.ribbon().current_tab() == "solid",
        shell.ribbon().current_tab(),
    )
    Gui.activateWorkbench("PartDesignWorkbench")
    later(800, step_left)


def step_left():
    from sciforge import shell

    check("Leaving SciForge turns the interface off", not shell.is_on())
    check(
        "Stylesheet restored", QtWidgets.QApplication.instance().styleSheet() == state["qss_before"]
    )
    check("Menu bar back", Gui.getMainWindow().menuBar().isVisible())
    check("FreeCAD toolbars back", len(visible_toolbars()) > 3, visible_toolbars())
    cmd = Gui.Command.get("PartDesign_Pad")
    check("Shortcuts restored after leaving", cmd.getShortcut() != "E", cmd.getShortcut())
    finish()


def finish():
    if state.get("finished"):
        return
    state["finished"] = True
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
later(2000, step_activate)
