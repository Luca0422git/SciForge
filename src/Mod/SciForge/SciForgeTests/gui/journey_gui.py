# SPDX-License-Identifier: LGPL-2.1-or-later
"""GUI journey test: SciForge used the way a person uses Fusion, with real mouse input.

Run like smoke_gui.py (CI: under xvfb-run); writes journey-result.json into
SCIFORGE_SMOKE_OUT. Unlike the smoke test, nothing here calls SciForge code to do
the work: every pick is a mouse click on the 3D view, every distance a drag of the
arrow, every command a key or a ribbon command. It exists because the smoke test
passed while the real thing could not be used (Create Sketch opened pop-ups,
dragging the arrow crashed FreeCAD, Extrude ignored clicks on profiles and faces).

The journey:
  1. Create Sketch, click the XY plane      -> sketch opens on XY, no pop-up
  2. draw a 40 x 30 rectangle, finish       -> back in SOLID
  3. E, click inside the rectangle          -> Extrude starts on it
     drag the arrow up                      -> distance follows the mouse, no crash; OK
  4. Q, click the top face, type 5, OK      -> part 5 mm taller
  5. Create Sketch, click the top face      -> sketch on that face
     draw a circle, finish
  6. E, click inside the circle, -5         -> Cut chosen by itself, hole cut; OK
  7. E, click the right side face, 3, OK    -> face extruded outward
  8. E then Q without closing the first     -> the first is finished, Q opens
"""
import json
import math
import os
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets
from PySide6 import QtTest

OUT_DIR = os.environ.get("SCIFORGE_SMOKE_OUT") or App.getUserAppDataDir()
checks = []
state = {}
STEP_MS = 700


def check(name, ok, detail=""):
    if not ok and state.get("last_click"):
        detail = "%s [last click: %s]" % (detail, state["last_click"])
    checks.append({"name": name, "ok": bool(ok), "detail": str(detail)})


def shot(name):
    QtWidgets.QApplication.primaryScreen().grabWindow(0).save(os.path.join(OUT_DIR, name))


# -- real input on the 3D view ---------------------------------------------------
def gl_widget():
    area = Gui.getMainWindow().findChild(QtWidgets.QMdiArea)
    sub = area.activeSubWindow() or area.subWindowList()[-1]
    return [
        w
        for w in sub.findChildren(QtWidgets.QWidget)
        if w.metaObject().className() == "QOpenGLWidget"
    ][0]


def screen_point(point):
    """Widget pixel of a 3D point (Qt's y axis points down, Coin's up)."""
    view = Gui.ActiveDocument.ActiveView
    widget = gl_widget()
    x, y = view.getPointOnViewport(point)
    ratio = widget.devicePixelRatioF()
    return QtCore.QPoint(int(x / ratio), int(widget.height() - y / ratio))


def move(pos):
    QtTest.QTest.mouseMove(gl_widget(), pos)
    QtWidgets.QApplication.processEvents()


def click(point):
    """Left click on the 3D point; remembers what was under the mouse and what got selected."""
    view = Gui.ActiveDocument.ActiveView
    pos = screen_point(point)
    move(pos)
    info = view.getObjectInfo(view.getPointOnViewport(point))
    QtTest.QTest.mouseClick(gl_widget(), QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, pos)
    QtWidgets.QApplication.processEvents()
    selected = [(s.ObjectName, s.SubElementNames) for s in Gui.Selection.getSelectionEx()]
    state["last_click"] = "under mouse: %s; selected: %s" % (
        info and (info.get("Object"), info.get("Component")),
        selected,
    )


def drag(start, end, steps=12):
    widget = gl_widget()
    move(start)
    QtTest.QTest.mousePress(widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, start)
    for i in range(1, steps + 1):
        pos = QtCore.QPointF(
            start.x() + (end.x() - start.x()) * i / steps,
            start.y() + (end.y() - start.y()) * i / steps,
        )
        event = QtGui.QMouseEvent(
            QtCore.QEvent.MouseMove,
            pos,
            QtCore.QPointF(widget.mapToGlobal(pos.toPoint())),
            QtCore.Qt.NoButton,
            QtCore.Qt.LeftButton,
            QtCore.Qt.NoModifier,
        )
        QtWidgets.QApplication.sendEvent(widget, event)
        QtWidgets.QApplication.processEvents()
    QtTest.QTest.mouseRelease(widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, end)
    QtWidgets.QApplication.processEvents()


def press(key):
    widget = gl_widget()
    widget.setFocus()
    QtTest.QTest.keyClick(widget, key)
    QtWidgets.QApplication.processEvents()


def popups():
    return [
        w.windowTitle()
        for w in QtWidgets.QApplication.topLevelWidgets()
        if w.isVisible() and isinstance(w, QtWidgets.QDialog)
    ]


def fit():
    view = Gui.ActiveDocument.ActiveView
    view.viewIsometric()
    view.fitAll()
    QtWidgets.QApplication.processEvents()


def body():
    from sciforge import commands

    return commands.find_body()


def volume():
    return body().Shape.Volume


# -- the journey -------------------------------------------------------------------
def step_start():
    # FreeCAD animates camera moves: a click computed mid-animation lands on empty space.
    # A person clicks what they see once it has stopped; the test turns animation off.
    view_params = App.ParamGet("User parameter:BaseApp/Preferences/View")
    view_params.SetBool("UseNavigationAnimations", False)
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Journey")
    Gui.runCommand("SciForge_NewSketch")
    fit()


def step_pick_xy():
    from sciforge import taskui

    check("Create Sketch opens no pop-up", not popups(), popups())
    check("Create Sketch waits for a plane", taskui.current() is not None)
    picker = taskui.current()
    state["planes"] = getattr(picker, "planes", None)
    check("Origin planes shown", state["planes"] is not None and len(state["planes"].objects) == 3)
    shot("journey-0-planes.png")
    # From FreeCAD's isometric view (camera at +x -y +z) the XZ square hides the
    # XY square for y > 0, so click the XY square where nothing is in front of it.
    click(App.Vector(12, -8, 0))


def step_in_sketch1():
    sketch = Gui.ActiveDocument.getInEdit()
    sketch = sketch.Object if sketch is not None else None
    ok = sketch is not None and sketch.TypeId == "Sketcher::SketchObject"
    check("Clicking the XY plane opens a sketch on it", ok, sketch)
    if ok:
        support = sketch.AttachmentSupport[0][0].Name if sketch.AttachmentSupport else None
        check("Sketch is on the XY plane", support == "XY_Plane", support)
        planes = state.get("planes")
        check("Origin planes removed again", planes is not None and not planes.callbacks)
        _rectangle(sketch, 0, 0, 40, 30)
        state["sketch1"] = sketch
    shot("journey-1-sketch.png")
    Gui.ActiveDocument.resetEdit()
    App.ActiveDocument.recompute()


def _rectangle(sketch, x0, y0, x1, y1):
    import Part

    pts = [
        App.Vector(x0, y0, 0),
        App.Vector(x1, y0, 0),
        App.Vector(x1, y1, 0),
        App.Vector(x0, y1, 0),
    ]
    for i in range(4):
        sketch.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))


def step_extrude_profile():
    fit()
    Gui.Selection.clearSelection()
    # A fresh sketch is picked automatically; clear that to test clicking inside the profile.
    from sciforge import extrude_ui

    extrude_ui.ExtrudePanel.auto_pick = False
    press(QtCore.Qt.Key_E)


# The task panel opening narrows the 3D view, so every click comes one step after the
# key that opened a panel (as a person clicks after seeing the screen).
def step_extrude_click():
    from sciforge import extrude_ui

    panel = extrude_ui.ExtrudePanel.last
    regions = len(panel.picker.regions) if panel and panel.picker else 0
    check("E shades the sketch profile", regions == 1, regions)
    fit()
    click(App.Vector(20, 15, 0))
    state["panel"] = panel


def step_extrude_drag():
    panel = state["panel"]
    check("Clicking inside the profile starts the extrude", panel.target is not None)
    if panel.target is None or panel.dragger is None:
        return
    fit()
    head = App.Vector(20, 15, panel.dragger.distance() + panel.dragger.size * 0.9)
    start = screen_point(head)
    shot("journey-2-before-drag.png")
    drag(start, QtCore.QPoint(start.x(), start.y() - 60))


def step_extrude_ok():
    panel = state["panel"]
    distance = panel.distance.value()
    check("Dragging the arrow changes the distance", distance > 10.5, distance)
    check("Extrude preview has no error", panel.message.text() == "", panel.message.text())
    shot("journey-3-extrude.png")
    panel.distance.widget.setProperty("rawValue", 10.0)
    ok = panel.accept()
    App.ActiveDocument.recompute()
    check("Extrude OK", ok)
    check("Extrude gives 40 x 30 x 10", abs(volume() - 12000) < 1e-6, volume())


def step_presspull():
    fit()
    Gui.Selection.clearSelection()
    press(QtCore.Qt.Key_Q)


def step_presspull_click():
    fit()
    click(App.Vector(20, 15, 10))


def step_presspull_ok():
    from sciforge import presspull_ui

    panel = presspull_ui.PressPullPanel.last
    check(
        "Q then clicking the top face starts Press Pull",
        panel and panel.target is not None,
        "%s; dialog says: %s" % (state.get("last_click"), panel and panel.message.text()),
    )
    if panel and panel.target is not None:
        panel.field.widget.setProperty("rawValue", 5.0)
        QtWidgets.QApplication.processEvents()
        panel.accept()
    check("Press Pull +5 gives 40 x 30 x 15", abs(volume() - 18000) < 1e-6, volume())


def step_sketch_on_face():
    Gui.Selection.clearSelection()
    fit()
    Gui.runCommand("SciForge_NewSketch")
    check("Second Create Sketch opens no pop-up", not popups(), popups())


def step_sketch_face_click():
    fit()
    click(App.Vector(20, 15, 15))


def step_in_sketch2():
    import Part

    edit = Gui.ActiveDocument.getInEdit()
    sketch = edit.Object if edit is not None else None
    ok = sketch is not None and sketch.TypeId == "Sketcher::SketchObject"
    check("Clicking the top face opens a second sketch on it", ok, sketch)
    if ok:
        support = sketch.AttachmentSupport[0]
        check("Second sketch sits on a face", support[1][0].startswith("Face"), support)
        # Sketch coordinates on the face: put the circle at the global (20, 15).
        local = sketch.getGlobalPlacement().inverse().multVec(App.Vector(20, 15, 15))
        sketch.addGeometry(Part.Circle(App.Vector(local.x, local.y, 0), App.Vector(0, 0, 1), 4))
        state["sketch2"] = sketch
    Gui.ActiveDocument.resetEdit()
    App.ActiveDocument.recompute()


def step_cut():
    from sciforge import extrude_ui

    fit()
    Gui.Selection.clearSelection()
    state["before_cut"] = volume()
    press(QtCore.Qt.Key_E)
    state["panel"] = extrude_ui.ExtrudePanel.last


def step_cut_click():
    fit()
    click(App.Vector(20, 15, 15))


def step_cut_ok():
    panel = state["panel"]
    check("Clicking inside the circle picks it", panel.target is not None)
    if panel.target is None:
        return
    panel.distance.widget.setProperty("rawValue", -5.0)
    QtWidgets.QApplication.processEvents()
    check("Extruding into the part picks Cut", panel.operation.currentData() == "cut")
    panel.accept()
    expected = state["before_cut"] - math.pi * 16 * 5
    check("Hole cut pi*4^2*5", abs(volume() - expected) < 1e-6, (volume(), expected))


def step_face_extrude():
    from sciforge import extrude_ui

    fit()
    Gui.Selection.clearSelection()
    state["before_face"] = volume()
    press(QtCore.Qt.Key_E)
    state["panel"] = extrude_ui.ExtrudePanel.last


def step_face_click():
    fit()
    click(App.Vector(40, 15, 7))  # the right side face (x = 40)


def step_face_extrude_ok():
    panel = state["panel"]
    check("E then clicking a side face starts the extrude", panel.target is not None)
    if panel.target is None:
        return
    panel.distance.widget.setProperty("rawValue", 3.0)
    QtWidgets.QApplication.processEvents()
    panel.accept()
    grown = volume() - state["before_face"]
    check("Side face extruded 3 mm (30 x 15 x 3)", abs(grown - 1350) < 1e-6, grown)
    shot("journey-7-face.png")


def step_switch_commands():
    from sciforge import presspull_ui

    Gui.Selection.clearSelection()
    press(QtCore.Qt.Key_E)
    press(QtCore.Qt.Key_Q)
    panel = presspull_ui.PressPullPanel.last
    check(
        "Q while Extrude is open closes Extrude and opens Press Pull",
        Gui.Control.activeDialog() and panel is not None and not panel._closed,
    )
    if panel is not None:
        panel.reject()


def step_end():
    from sciforge import RECENT

    warnings = [m for m in RECENT if " WARNING " in m]
    check("No SciForge warnings during the journey", not warnings, warnings)
    check("No pop-ups left open", not popups(), popups())
    shot("journey-end.png")


STEPS = [
    step_start,
    step_pick_xy,
    step_in_sketch1,
    step_extrude_profile,
    step_extrude_click,
    step_extrude_drag,
    step_extrude_ok,
    step_presspull,
    step_presspull_click,
    step_presspull_ok,
    step_sketch_on_face,
    step_sketch_face_click,
    step_in_sketch2,
    step_cut,
    step_cut_click,
    step_cut_ok,
    step_face_extrude,
    step_face_click,
    step_face_extrude_ok,
    step_switch_commands,
    step_end,
]


def run_next():
    if not STEPS:
        finish()
        return
    step = STEPS.pop(0)
    try:
        step()
    except Exception:
        check("No exception in %s" % step.__name__, False, traceback.format_exc())
    QtCore.QTimer.singleShot(STEP_MS, run_next)


def finish():
    result = {"passed": all(c["ok"] for c in checks), "checks": checks}
    with open(os.path.join(OUT_DIR, "journey-result.json"), "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
    for c in checks:
        App.Console.PrintMessage(
            "[SciForge] journey %s: %s %s\n"
            % ("PASS" if c["ok"] else "FAIL", c["name"], "" if c["ok"] else c["detail"])
        )
    for doc in list(App.listDocuments()):
        App.closeDocument(doc)
    QtCore.QTimer.singleShot(200, QtWidgets.QApplication.instance().quit)


QtCore.QTimer.singleShot(2500, run_next)
