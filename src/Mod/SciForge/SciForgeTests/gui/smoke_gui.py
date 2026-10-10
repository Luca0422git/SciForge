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
from PySide6 import QtTest

OUT_DIR = os.environ.get("SCIFORGE_SMOKE_OUT") or App.getUserAppDataDir()
EXPECTED_SHORTCUTS = {
    "SciForge_CommandSearch": "S",
    "SciForge_Extrude": "E",
    "SciForge_SketchLine": "L",  # Fusion's chained line (FreeCAD's polyline tool)
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


def _preferences():
    """The preferences SciForge changes: {(group, name): value or None if unset}."""
    from sciforge import theme

    snapshot = {}
    for path, kind, name, _ in theme.VIEWER_SETTINGS:
        group = App.ParamGet(path)
        exists = name in getattr(group, "Get" + kind + "s")()
        snapshot[(path, name)] = getattr(group, "Get" + kind)(name) if exists else None
    return snapshot


def step_activate():
    state["prefs_before"] = _preferences()
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
    from sciforge import shortcuts

    for name, key in EXPECTED_SHORTCUTS.items():
        got = shortcuts.bound_keys().get(key)
        check("Key %s bound to %s" % (key, name), got == name, got)
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
    _check_browser()
    shot("screenshot.png")
    press("S")
    later(400, step_search_open)


def _browser_labels():
    from sciforge import browser_ui

    tree = browser_ui.widget()
    labels = []
    it = QtWidgets.QTreeWidgetItemIterator(tree)
    while it.value():
        labels.append(it.value().text(1))
        it += 1
    return tree, labels


def _check_browser():
    from sciforge import browser_ui

    tree, labels = _browser_labels()
    dock = Gui.getMainWindow().findChild(QtWidgets.QDockWidget, "Model")
    check(
        "Browser replaces the tree inside FreeCAD's dock",
        dock is not None and dock.widget() is tree and dock.windowTitle() == "BROWSER",
    )
    for folder in ("Document Settings", "Named Views", "Origin", "Bodies", "Sketches"):
        check("Browser shows %s" % folder, folder in labels, labels)
    check("Browser hides features (they are in the timeline)", "Pad" not in labels, labels)
    # Click the eye of the sketch: it must show/hide the sketch in the 3D view.
    tree.refresh()
    item = [
        i for i in tree.findItems("Sketch", QtCore.Qt.MatchExactly | QtCore.Qt.MatchRecursive, 1)
    ][0]
    sketch = App.ActiveDocument.getObject("Sketch")
    before = sketch.ViewObject.Visibility
    tree._clicked(item, 0)
    check("Browser eye toggles visibility", sketch.ViewObject.Visibility != before)
    sketch.ViewObject.Visibility = before


def view_widget():
    area = Gui.getMainWindow().findChild(QtWidgets.QMdiArea)
    return (
        area.activeSubWindow().widget() if area and area.activeSubWindow() else Gui.getMainWindow()
    )


def press(key):
    """A real key press on the 3D view, as the user would type it."""
    widget = view_widget()
    widget.setFocus()
    QtTest.QTest.keyClick(widget, key)


def step_search_open():
    from sciforge import search_ui

    popups = [
        w
        for w in QtWidgets.QApplication.topLevelWidgets()
        if isinstance(w, search_ui.CommandSearchDialog) and w.isVisible()
    ]
    check("Pressing S opens command search", bool(popups))
    for w in popups:
        w.close()
    later(200, step_open_menu)


def step_open_menu():
    from sciforge import shell

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
    check(
        "FreeCAD toolbars stay hidden after the sketch",
        visible_toolbars() == ["SciForgeRibbonBar"],
        visible_toolbars(),
    )
    later(300, step_presspull)


def _top_face_name(obj):
    shape = obj.Shape
    best = max(range(len(shape.Faces)), key=lambda i: shape.Faces[i].CenterOfMass.z)
    return "Face%d" % (best + 1)


def step_presspull():
    """Q with the top face selected, type 5, OK: the box grows to 40x20x15."""
    from sciforge import commands

    body = commands.active_body()
    tip = body.Tip
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(App.ActiveDocument.Name, tip.Name, _top_face_name(tip))
    press("Q")
    panel = Gui.Control.activeDialog() and _active_panel()
    check("Pressing Q opens Press Pull", panel is not None)
    check("Press Pull dialog opens with the face", panel is not None and panel.target is not None)
    check("Press Pull arrow shown in the 3D view", panel is not None and panel.dragger is not None)
    panel.field.widget.setProperty("rawValue", 5.0)
    state["panel"] = panel
    later(600, step_presspull_ok)


def _active_panel():
    from sciforge import presspull_ui

    return presspull_ui.PressPullPanel.last


def step_presspull_ok():
    from sciforge import commands, timeline_ui

    state["panel"].accept()
    body = commands.active_body()
    check(
        "Press Pull +5 gives 12000 mm^3", abs(body.Shape.Volume - 12000.0) < 1e-6, body.Shape.Volume
    )
    timeline_ui._dock.widget().refresh()
    titles = timeline_ui._dock.widget().titles()
    check("Timeline shows Press Pull 1", "Press Pull 1" in titles, titles)
    shot("screenshot-presspull.png")
    # Cancel must leave the model untouched.
    tip = body.Tip
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(App.ActiveDocument.Name, tip.Name, _top_face_name(tip))
    Gui.runCommand("SciForge_PressPull")
    panel = _active_panel()
    panel.field.widget.setProperty("rawValue", -3.0)
    state["panel"] = panel
    later(600, step_presspull_cancel)


def step_presspull_cancel():
    from sciforge import commands

    state["panel"].reject()
    body = commands.active_body()
    check(
        "Cancel leaves the part unchanged",
        abs(body.Shape.Volume - 12000.0) < 1e-6,
        body.Shape.Volume,
    )
    check(
        "Cancel removes the unfinished feature",
        len([o for o in body.Group if getattr(o, "SciForgeType", "") == "PressPull"]) == 1,
    )
    later(300, step_extrude)


def step_extrude():
    """A circle sketch on top, E, distance -5: Fusion switches to Cut by itself."""
    import Part

    from sciforge import commands, extrude_ui

    body = commands.active_body()
    top = body.Shape.BoundBox.ZMax
    sketch = body.newObject("Sketcher::SketchObject", "HoleSketch")
    sketch.AttachmentSupport = (body.Origin.OriginFeatures[3], [""])
    sketch.MapMode = "FlatFace"
    sketch.AttachmentOffset = App.Placement(App.Vector(0, 0, top), App.Rotation())
    sketch.addGeometry(Part.Circle(App.Vector(20, 10, 0), App.Vector(0, 0, 1), 4))
    App.ActiveDocument.recompute()
    state["volume_before"] = body.Shape.Volume
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(App.ActiveDocument.Name, sketch.Name)
    press("E")
    panel = extrude_ui.ExtrudePanel.last
    check(
        "Pressing E opens Extrude with the sketch", panel is not None and panel.target is not None
    )
    panel.distance.widget.setProperty("rawValue", -5.0)
    state["panel"] = panel
    later(600, step_extrude_ok)


def step_extrude_ok():
    import math

    from sciforge import commands, timeline_ui

    panel = state["panel"]
    check(
        "Dragging into the part switches to Cut",
        panel.operation.currentData() == "cut",
        panel.operation.currentData(),
    )
    shot("screenshot-extrude.png")
    panel.accept()
    body = commands.active_body()
    expected = state["volume_before"] - math.pi * 16 * 5
    check(
        "Extrude cut removes pi*4^2*5",
        abs(body.Shape.Volume - expected) < 1e-6,
        (body.Shape.Volume, expected),
    )
    timeline_ui._dock.widget().refresh()
    titles = timeline_ui._dock.widget().titles()
    check("Timeline calls the cut Extrude 2", "Extrude 2" in titles, titles)
    # A short right click on the 3D view opens the marking menu.
    gl = [
        w
        for w in view_widget().findChildren(QtWidgets.QWidget)
        if w.metaObject().className() == "QOpenGLWidget"
    ][0]
    QtTest.QTest.mouseClick(
        gl, QtCore.Qt.RightButton, QtCore.Qt.NoModifier, QtCore.QPoint(300, 300)
    )
    later(400, step_marking_menu)


def step_marking_menu():
    from sciforge import marking_menu

    menu = marking_menu._last_menu["widget"]
    visible = menu is not None and menu.isVisible()
    check("Right click opens the marking menu", visible)
    if visible:
        check("Marking menu has 8 slots", len(menu.slots) == 8, len(menu.slots))
        check(
            "Slot 1 repeats the last command",
            menu.slots[0].text().startswith("Repeat ") and menu.slots[0].isEnabled(),
            menu.slots[0].text(),
        )
        shot("screenshot-marking-menu.png")
        menu.close()
    menus = [
        w
        for w in QtWidgets.QApplication.topLevelWidgets()
        if isinstance(w, QtWidgets.QMenu) and w.isVisible()
    ]
    check("FreeCAD's own context menu did not open", not menus)
    later(200, step_parameters)


def step_parameters():
    """Change Parameters: add 'wall', drive the Press Pull distance with it."""
    from sciforge import commands, parameters_ui

    Gui.runCommand("SciForge_ChangeParameters")
    dialog = parameters_ui.ParametersDialog.last
    check("Change Parameters opens", dialog is not None and dialog.isVisible())
    dialog.add_parameter("wall", "mm", "5")
    dialog.reload()
    rows = [dialog.model.topLevelItem(i) for i in range(dialog.model.topLevelItemCount())]
    owners = [r.text(0) for r in rows]
    check("Model parameters list the features", "Pad" in owners and "PressPull" in owners, owners)
    press = [r for r in rows if r.text(0) == "PressPull"][0].child(0)
    press.setText(2, "wall * 2")  # Fusion-style: just the parameter name
    App.ActiveDocument.recompute()
    body = commands.active_body()
    pp = [o for o in body.Group if getattr(o, "SciForgeType", "") == "PressPull"][0]
    check("Press Pull follows the parameter", abs(pp.Distance.Value - 10.0) < 1e-9, pp.Distance)
    shot("screenshot-parameters.png")
    dialog.accept()
    later(300, step_construct)


def step_construct():
    """Construct > Offset Plane on the top face: a datum plane 10 mm above it."""
    from sciforge import commands, construct_ui

    body = commands.active_body()
    tip = body.Tip
    top = tip.Shape.BoundBox.ZMax
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(App.ActiveDocument.Name, tip.Name, _top_face_name(tip))
    Gui.runCommand("SciForge_Construct_OffsetPlane")
    panel = construct_ui.ConstructPanel.last
    check(
        "Offset Plane created from the selected face", panel is not None and panel.datum is not None
    )
    panel.accept()
    App.ActiveDocument.recompute()
    plane = panel.datum
    check(
        "Offset Plane sits 10 mm above the face",
        abs(plane.Placement.Base.z - (top + 10)) < 1e-6,
        plane.Placement.Base.z,
    )
    later(300, step_marker)


def step_marker():
    """Drag the history marker to the start: the design rolls back to the first extrude."""
    from sciforge import commands, timeline_ui

    widget = timeline_ui._dock.widget()
    widget.refresh()
    marker = [
        w for w in widget._inner.findChildren(QtWidgets.QFrame) if w.property("role") == "marker"
    ][0]
    first = widget._buttons[0]
    target = marker.mapFromGlobal(first.mapToGlobal(first.rect().center()) - QtCore.QPoint(20, 0))
    QtTest.QTest.mousePress(marker, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, QtCore.QPoint(2, 5))
    QtTest.QTest.mouseMove(marker, target)
    QtTest.QTest.mouseRelease(marker, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, target)
    body = commands.active_body()
    check(
        "Dragging the marker to the start rolls back to the first extrude",
        body.Tip is not None and body.Tip.Name == "Pad",
        body.Tip and body.Tip.Name,
    )
    widget.refresh()
    widget.step("end")
    check("Go to end rolls forward again", body.Tip.Name != "Pad", body.Tip.Name)
    later(300, step_print)


def step_print():
    """Utilities > 3D Print: a 3MF a slicer can read, with the body's volume."""
    import Mesh

    from sciforge import commands, make3d_ui

    Gui.runCommand("SciForge_3DPrint")
    dialog = make3d_ui.PrintDialog.last
    dialog.open_folder.setChecked(False)
    path = os.path.join(OUT_DIR, "print-test.3mf")
    ok = dialog.save(path)
    body = commands.active_body()
    mesh = Mesh.Mesh(path) if ok and os.path.exists(path) else None
    check("3D Print writes a 3MF", mesh is not None and mesh.CountFacets > 0)
    if mesh is not None:
        error = abs(mesh.Volume - body.Shape.Volume) / body.Shape.Volume
        check("3MF volume within 1% of the body", error < 0.01, (mesh.Volume, body.Shape.Volume))
    Gui.activateWorkbench("PartDesignWorkbench")
    later(800, step_left)


def step_left():
    from sciforge import shell

    check("Leaving SciForge turns the interface off", not shell.is_on())
    check(
        "Stylesheet restored", QtWidgets.QApplication.instance().styleSheet() == state["qss_before"]
    )
    check("Menu bar back", Gui.getMainWindow().menuBar().isVisible())
    after = _preferences()
    changed = {
        k: (state["prefs_before"][k], after[k])
        for k in after
        if after[k] != state["prefs_before"][k]
    }
    check("FreeCAD preferences exactly as before SciForge", not changed, changed)
    dock = Gui.getMainWindow().findChild(QtWidgets.QDockWidget, "Model")
    from sciforge import browser_ui

    check(
        "FreeCAD's tree is back in its dock",
        dock is not None and dock.isVisible() and dock.widget() is not browser_ui.widget(),
        dock and dock.windowTitle(),
    )
    check("FreeCAD toolbars back", len(visible_toolbars()) > 3, visible_toolbars())
    from sciforge import shortcuts

    check("Keys released after leaving", shortcuts.bound_keys() == {}, shortcuts.bound_keys())
    distx = Gui.Command.get("Sketcher_ConstrainDistanceX")
    check("FreeCAD's own L key given back", distx.getShortcut() == "L", distx.getShortcut())
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
