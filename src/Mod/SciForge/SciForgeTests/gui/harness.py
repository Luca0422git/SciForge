# SPDX-License-Identifier: LGPL-2.1-or-later
"""Helpers for GUI scenario tests that use SciForge like a person does.

A scenario is a Python file run by the FreeCAD GUI (CI: under xvfb-run) that does

    from SciForgeTests.gui import harness as h
    h.run("my-scenario", [step_a, step_b, ...])

Each step is a plain function. Steps run one at a time with a pause between
them (a person also waits to see the screen). Use the helpers below to act:
click(App.Vector) / drag / press(key) / ribbon(label) / menu_item(group, label).
Use check(name, ok, detail) to assert.

Every error FreeCAD prints (Report view: C++ and Python, SciForge or not), every
Python traceback and every SciForge warning fails the scenario, because those are
exactly what a user sees as "errors everywhere". A crash fails it too: the result
file is only written at the end.

The result goes to $SCIFORGE_SMOKE_OUT/<name>-result.json, screenshots to
$SCIFORGE_SMOKE_OUT/<name>-*.png.
"""
import json
import os
import re
import traceback

import FreeCAD as App
import FreeCADGui as Gui

from PySide import QtCore, QtGui, QtWidgets
from PySide6 import QtTest

OUT_DIR = os.environ.get("SCIFORGE_SMOKE_OUT") or App.getUserAppDataDir()
STEP_MS = int(os.environ.get("SCIFORGE_STEP_MS", "700"))
checks = []
state = {"name": "scenario", "errors_seen": 0}
# Report-view lines that are not problems (start-up chatter of stock FreeCAD).
IGNORED_ERRORS = (
    re.compile(r"Migrating Start Workbench"),
    re.compile(r"Cannot find icon"),
)


def check(name, ok, detail=""):
    if not ok and state.get("last_click"):
        detail = "%s [last click: %s]" % (detail, state["last_click"])
    checks.append({"name": name, "ok": bool(ok), "detail": str(detail)[:4000]})
    return bool(ok)


def shot(label):
    path = os.path.join(OUT_DIR, "%s-%s.png" % (state["name"], label))
    QtWidgets.QApplication.primaryScreen().grabWindow(0).save(path)


# -- errors -----------------------------------------------------------------------
def report_text():
    for widget in Gui.getMainWindow().findChildren(QtWidgets.QTextEdit):
        if widget.metaObject().className() == "Gui::DockWnd::ReportOutput":
            return widget.toPlainText()
    return ""


class _ConsoleTap:
    """Catches errors/warnings printed through App.Console from Python."""

    def __init__(self):
        self.lines = []
        self._error = App.Console.PrintError
        self._warning = App.Console.PrintWarning
        App.Console.PrintError = self._on_error
        App.Console.PrintWarning = self._on_warning

    def _on_error(self, msg):
        self.lines.append("ERROR " + str(msg).strip())
        self._error(msg)

    def _on_warning(self, msg):
        if "[SciForge]" in str(msg):
            self.lines.append("WARNING " + str(msg).strip())
        self._warning(msg)


_tap = None


def _report_errors():
    """Error lines of the Report view (FreeCAD shows errors in red with 'Error'/'<Exception>')."""
    found = []
    for line in report_text().splitlines():
        low = line.lower()
        if any(p.search(line) for p in IGNORED_ERRORS):
            continue
        if (
            "error" in low
            or "exception" in low
            or "traceback" in low
            or "failed" in low
            or "invalid" in low
            or "[sciforge] warning" in low
        ):
            found.append(line.strip())
    return found


def new_errors():
    """Errors that appeared since the last call (Report view + console tap)."""
    lines = _report_errors() + (_tap.lines if _tap else [])
    fresh = lines[state["errors_seen"] :]
    state["errors_seen"] = len(lines)
    return fresh


def expect_no_errors(where):
    fresh = new_errors()
    return check("No errors after %s" % where, not fresh, fresh)


# -- the 3D view ------------------------------------------------------------------
def gl_widget():
    area = Gui.getMainWindow().findChild(QtWidgets.QMdiArea)
    sub = area.activeSubWindow() or area.subWindowList()[-1]
    return [
        w
        for w in sub.findChildren(QtWidgets.QWidget)
        if w.metaObject().className() == "QOpenGLWidget"
    ][0]


def view():
    return Gui.ActiveDocument.ActiveView


def screen_point(point):
    """Widget pixel of a 3D point (Qt's y axis points down, Coin's up)."""
    widget = gl_widget()
    x, y = view().getPointOnViewport(point)
    ratio = widget.devicePixelRatioF()
    return QtCore.QPoint(int(x / ratio), int(widget.height() - y / ratio))


def move(pos):
    QtTest.QTest.mouseMove(gl_widget(), pos)
    QtWidgets.QApplication.processEvents()


def under_mouse(point):
    info = view().getObjectInfo(view().getPointOnViewport(point))
    return info and (info.get("Object"), info.get("Component"))


def click(point, modifiers=QtCore.Qt.NoModifier, button=QtCore.Qt.LeftButton):
    """Click on the 3D point; remembers what was under the mouse and what got selected."""
    pos = screen_point(point)
    move(pos)
    hit = under_mouse(point)
    QtTest.QTest.mouseClick(gl_widget(), button, modifiers, pos)
    QtWidgets.QApplication.processEvents()
    selected = [(s.ObjectName, s.SubElementNames) for s in Gui.Selection.getSelectionEx()]
    state["last_click"] = "under mouse: %s; selected: %s" % (hit, selected)
    return hit


def click_empty():
    """Click on empty background (clears the selection, like in Fusion)."""
    widget = gl_widget()
    pos = QtCore.QPoint(15, 15)
    QtTest.QTest.mouseClick(widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, pos)
    QtWidgets.QApplication.processEvents()


def double_click(point):
    pos = screen_point(point)
    move(pos)
    QtTest.QTest.mouseDClick(gl_widget(), QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, pos)
    QtWidgets.QApplication.processEvents()


def drag(start, end, steps=12):
    """Press, move and release the left button, start/end in widget pixels."""
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


def drag_points(a, b):
    """Drag from 3D point a to 3D point b."""
    drag(screen_point(a), screen_point(b))


def press(key, modifiers=QtCore.Qt.NoModifier):
    """A key press on the 3D view. key: a Qt.Key or a one-letter string."""
    widget = gl_widget()
    widget.setFocus()
    if isinstance(key, str):
        QtTest.QTest.keyClicks(widget, key, modifiers)
    else:
        QtTest.QTest.keyClick(widget, key, modifiers)
    QtWidgets.QApplication.processEvents()


def fit(iso=True):
    if iso:
        view().viewIsometric()
    view().fitAll()
    QtWidgets.QApplication.processEvents()


# -- ribbon and dialogs -----------------------------------------------------------
def ribbon_buttons():
    from sciforge import shell

    ribbon = shell.ribbon()
    if ribbon is None:
        return []
    return [b for b in ribbon.findChildren(QtWidgets.QToolButton) if b.isVisible()]


def ribbon(label):
    """Click the big ribbon button with this label (as the user would)."""
    name = "SciForgeBig_" + label.replace(" ", "_")
    for button in ribbon_buttons():
        if button.objectName() == name:
            button.click()
            QtWidgets.QApplication.processEvents()
            return True
    check("Ribbon button %r exists" % label, False, [b.objectName() for b in ribbon_buttons()])
    return False


def task_button(text):
    """Click OK / Cancel / Close in the task panel (as the user would)."""
    main = Gui.getMainWindow()
    for button in main.findChildren(QtWidgets.QPushButton):
        if button.isVisible() and button.text().replace("&", "").strip() == text:
            button.click()
            QtWidgets.QApplication.processEvents()
            return True
    check("Task panel button %r exists" % text, False)
    return False


def popups():
    return [
        w.windowTitle() or w.metaObject().className()
        for w in QtWidgets.QApplication.topLevelWidgets()
        if w.isVisible() and isinstance(w, (QtWidgets.QDialog, QtWidgets.QMessageBox))
    ]


def close_popups():
    for w in QtWidgets.QApplication.topLevelWidgets():
        if w.isVisible() and isinstance(w, QtWidgets.QDialog):
            w.reject()


def in_sketch():
    edit = Gui.ActiveDocument.getInEdit() if Gui.ActiveDocument else None
    obj = edit.Object if edit is not None else None
    return obj if obj is not None and obj.TypeId == "Sketcher::SketchObject" else None


def body():
    from sciforge import commands

    return commands.find_body()


def solid_volume():
    b = body()
    if b is None or b.Shape.isNull():
        return 0.0
    try:
        return b.Shape.Volume
    except Exception:
        return 0.0


def body_visible():
    b = body()
    return b is not None and b.ViewObject.Visibility and not b.Shape.isNull()


def draw_rectangle(sketch, x0, y0, x1, y1):
    """Rectangle in sketch coordinates with Fusion's constraints (coincident, h/v)."""
    import Part
    import Sketcher

    pts = [
        App.Vector(x0, y0, 0),
        App.Vector(x1, y0, 0),
        App.Vector(x1, y1, 0),
        App.Vector(x0, y1, 0),
    ]
    first = sketch.GeometryCount
    for i in range(4):
        sketch.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))
    for i in range(4):
        sketch.addConstraint(
            Sketcher.Constraint("Coincident", first + i, 2, first + (i + 1) % 4, 1)
        )
    sketch.addConstraint(Sketcher.Constraint("Horizontal", first))
    sketch.addConstraint(Sketcher.Constraint("Horizontal", first + 2))
    sketch.addConstraint(Sketcher.Constraint("Vertical", first + 1))
    sketch.addConstraint(Sketcher.Constraint("Vertical", first + 3))
    App.ActiveDocument.recompute()


def draw_circle(sketch, cx, cy, r):
    import Part

    sketch.addGeometry(Part.Circle(App.Vector(cx, cy, 0), App.Vector(0, 0, 1), r))
    App.ActiveDocument.recompute()


def to_sketch(sketch, point):
    """Global 3D point -> sketch coordinates (x, y)."""
    local = sketch.getGlobalPlacement().inverse().multVec(point)
    return local.x, local.y


# -- running ----------------------------------------------------------------------
def _write(partial):
    name = state["name"]
    result = {
        "name": name,
        "file": os.environ.get("SCIFORGE_SCENARIO", name),
        "passed": (not partial) and all(c["ok"] for c in checks),
        "finished": not partial,
        "checks": checks,
    }
    with open(os.path.join(OUT_DIR, "%s-result.json" % name), "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)


def _finish():
    name = state["name"]
    leftovers = new_errors()
    check("No errors at the end", not leftovers, leftovers)
    _write(partial=False)
    for c in checks:
        App.Console.PrintMessage(
            "[SciForge] %s %s: %s %s\n"
            % (name, "PASS" if c["ok"] else "FAIL", c["name"], "" if c["ok"] else c["detail"])
        )
    try:
        from sciforge import commands

        commands.leave_edit()
    except Exception:
        pass
    for doc in list(App.listDocuments()):
        App.closeDocument(doc)
    QtCore.QTimer.singleShot(200, QtWidgets.QApplication.instance().quit)


def add_steps(steps):
    """Append steps while running (e.g. one per command found at start-up)."""
    state["queue"].extend(steps)


def run(name, steps, check_errors_each_step=True, start_ms=2500):
    """Run the steps one after another; errors are checked after every step."""
    global _tap
    state["name"] = name
    queue = state["queue"] = list(steps)

    def prepare():
        global _tap
        # FreeCAD animates camera moves; a click computed mid-animation misses.
        App.ParamGet("User parameter:BaseApp/Preferences/View").SetBool(
            "UseNavigationAnimations", False
        )
        _tap = _ConsoleTap()
        new_errors()  # start-up messages are not the scenario's

    def next_step():
        if not queue:
            _finish()
            return
        step = queue.pop(0)
        # Progress on stdout and a partial result: a crash still shows where it happened.
        print("[SciForge] %s step: %s" % (state["name"], step.__name__), flush=True)
        _write(partial=True)
        try:
            step()
        except Exception:
            check("No exception in %s" % step.__name__, False, traceback.format_exc())
        if check_errors_each_step:

            def after():
                fresh = new_errors()
                if fresh and getattr(step, "known", False):
                    # A known problem being fixed elsewhere: report it, do not fail. (The note
                    # goes to the Report view too, so it must not look like an error line.)
                    print(
                        "[SciForge] %s: known issue after %s (%d lines, see KNOWN)"
                        % (state["name"], step.__name__, len(fresh)),
                        flush=True,
                    )
                    new_errors()
                elif fresh:
                    check("No errors after %s" % step.__name__, False, fresh)
                    shot("error-" + step.__name__)
                next_step()

            QtCore.QTimer.singleShot(getattr(step, "wait_ms", STEP_MS), after)
        else:
            QtCore.QTimer.singleShot(getattr(step, "wait_ms", STEP_MS), next_step)

    QtCore.QTimer.singleShot(start_ms, lambda: (prepare(), next_step()))
