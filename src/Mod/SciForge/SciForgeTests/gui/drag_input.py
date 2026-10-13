# SPDX-License-Identifier: LGPL-2.1-or-later
"""Mouse input the way a real mouse delivers it, and a slow part, for the scenario about
drags whose release gets lost (scenarios/drag_release_lost.py, sciforge/drag_guard.py).

Most scenarios send QTest events straight to the 3D view widget. That skips part of Qt's
own routing, and a lost release is all about that routing. Here input goes to the main
window's QWindow (QTest's QWindow overloads), the path a hardware mouse takes:
  - Qt keeps track of which buttons are down (QApplication.mouseButtons()),
  - Qt's implicit grab sends the release to the widget that took the press,
  - every application event filter sees the event first (FreeCAD's progress bar, which
    swallows mouse releases while the document recomputes).

The slow part (add_slow_part) is an App::FeaturePython that takes about 0.7 s to
recompute while SLOW["on"] is set, like a heavy part does: every preview recompute then
shows FreeCAD's progress bar. release_during_recompute() lets the mouse button come up
from inside that recompute, the moment a person's release gets eaten.

Kept outside scenarios/ because every file there is run as a scenario.
"""

import time
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h

LEFT = QtCore.Qt.LeftButton
NONE = QtCore.Qt.NoModifier


# -- input through the main window's QWindow -----------------------------------------------------
def window():
    return Gui.getMainWindow().windowHandle()


def to_window(pos):
    """A pixel of the 3D view widget as a pixel of the main window's QWindow."""
    return window().mapFromGlobal(h.gl_widget().mapToGlobal(pos))


def press(pos):
    QtTest.QTest.mousePress(window(), LEFT, NONE, to_window(pos))


def move(pos):
    """A mouse move to a 3D view pixel; the left button is down if press() held it."""
    QtTest.QTest.mouseMove(window(), to_window(pos))


def release(pos):
    QtTest.QTest.mouseRelease(window(), LEFT, NONE, to_window(pos))


def click(pos):
    press(pos)
    release(pos)


def person_double_click(pos, gap_ms=150):
    """Two clicks 150 ms apart, the pace of a person's double-click. FreeCAD's navigation
    times a double-click with the wall clock, so it holds the second press back and hands
    it to the scene only together with the release."""
    click(pos)
    QtTest.QTest.qWait(gap_ms)
    click(pos)


def held():
    """Qt's own answer to "is the left button down?" (what drag_guard asks)."""
    return bool(QtWidgets.QApplication.mouseButtons() & LEFT)


def lerp(a, b, t):
    return QtCore.QPoint(
        int(round(a.x() + (b.x() - a.x()) * t)), int(round(a.y() + (b.y() - a.y()) * t))
    )


def moves(points):
    """Mouse moves through these 3D view pixels, one after the other."""
    for pos in points:
        move(pos)
        QtWidgets.QApplication.processEvents()


def coin_pos(pos):
    """A 3D view widget pixel as Coin's viewport position (y up, device pixels)."""
    widget = h.gl_widget()
    ratio = widget.devicePixelRatioF()
    return (pos.x() * ratio, (widget.height() - pos.y()) * ratio)


def inside_view(pos, margin=12):
    widget = h.gl_widget()
    return (
        margin < pos.x() < widget.width() - margin and margin < pos.y() < widget.height() - margin
    )


def under(pos):
    """(object, element) FreeCAD picks at a 3D view pixel, or None over empty space."""
    try:
        info = h.view().getObjectInfo(coin_pos(pos))
    except Exception:
        info = None
    return info and (info.get("Object"), info.get("Component"))


def picks_node(pos, node):
    """True when Coin's pick at this pixel goes through `node` (a dragger in front)."""
    try:
        from pivy import coin

        viewer = h.view().getViewer()
        manager = viewer.getSoRenderManager()
        x, y = coin_pos(pos)
        action = coin.SoRayPickAction(manager.getViewportRegion())
        action.setPoint(coin.SbVec2s(int(x), int(y)))
        action.setRadius(2)
        action.apply(manager.getSceneGraph())
        picked = action.getPickedPoint()
        if picked is None:
            return False
        path = picked.getPath()
        return any(path.getNode(i) == node for i in range(path.getLength()))
    except Exception:
        return False


def grabber_is_none():
    """True when the 3D view has no Coin node holding its mouse events (a dragger keeps
    them while it is being dragged and must give them back)."""
    action = h.view().getViewer().getSoEventManager().getHandleEventAction()
    return action.getGrabber() is None


def wait_until(condition, timeout_ms, step_ms=15):
    """Wait (handling events, so the handles' timers run) until condition() is true.
    Returns the milliseconds it took, or None after timeout_ms."""
    start = time.time()
    while True:
        try:
            if condition():
                return int((time.time() - start) * 1000)
        except Exception:
            pass
        if (time.time() - start) * 1000 > timeout_ms:
            return None
        QtTest.QTest.qWait(step_ms)


def recomputing():
    doc = App.ActiveDocument
    return bool(doc is not None and getattr(doc, "Recomputing", False))


# -- what reached the 3D view ----------------------------------------------------------------------
class InputSpy(QtCore.QObject):
    """Records the mouse buttons events that reach the 3D view: at the Qt widget (an
    application event filter installed before any recompute, so FreeCAD's progress bar,
    installed later, runs first and an event it eats is not seen here) and at the view's
    Coin callbacks (after FreeCAD's selection, which keeps a release over a part)."""

    def __init__(self):
        super().__init__()
        self.qt = []
        self.coin = []
        self._view = None
        self._callback = None
        QtWidgets.QApplication.instance().installEventFilter(self)

    def eventFilter(self, obj, event):
        try:
            kind = event.type()
            name = None
            if kind == QtCore.QEvent.MouseButtonPress:
                name = "press"
            elif kind == QtCore.QEvent.MouseButtonRelease:
                name = "release"
            elif kind == QtCore.QEvent.MouseButtonDblClick:
                name = "dblclick"
            if name and obj.metaObject().className() == "QOpenGLWidget":
                self.qt.append(name)
        except Exception:
            pass
        return False

    def watch_view(self):
        view = h.view()
        if view is self._view:
            return

        def seen(info):
            if info.get("Button") == "BUTTON1":
                self.coin.append(info.get("State"))

        self._view = view
        self._callback = view.addEventCallback("SoMouseButtonEvent", seen)

    def mark(self):
        return (len(self.qt), len(self.coin))

    def since(self, mark):
        return {"qt": self.qt[mark[0] :], "coin": self.coin[mark[1] :]}


SPY = {}


def spy():
    if "spy" not in SPY:
        SPY["spy"] = InputSpy()
    SPY["spy"].watch_view()
    return SPY["spy"]


class ReleaseSpy:
    """Notes every call of a handle's on_release: its end-of-drag work (the dialog takes the
    final value), which a stuck handle never does."""

    def __init__(self):
        self.calls = []

    def attach(self, handle):
        original = handle.on_release
        if getattr(original, "release_spy", None) is self:
            return

        def on_release(*args):
            self.calls.append(time.time())
            if original is not None:
                return original(*args)
            return None

        on_release.release_spy = self
        handle.on_release = on_release

    def count(self):
        return len(self.calls)


# -- a slow part -----------------------------------------------------------------------------------
SLOW = {"on": False, "seconds": 0.7, "hook": None, "hook_error": None}


class SlowPart:
    """Proxy of the slow part: its recompute takes SLOW["seconds"] while SLOW["on"]. A hook
    set in SLOW["hook"] runs once inside that recompute."""

    def __init__(self, obj):
        obj.Proxy = self

    def execute(self, obj):
        if not SLOW["on"]:
            return
        hook, SLOW["hook"] = SLOW["hook"], None
        if hook is not None:
            try:
                hook()
            except Exception:
                SLOW["hook_error"] = traceback.format_exc()
        time.sleep(SLOW["seconds"])

    def onChanged(self, obj, prop):
        pass

    def dumps(self):
        return None

    def loads(self, state):
        return None


def add_slow_part():
    """The slow part, made outside any dialog (a dialog's Cancel would undo it). SciForge's
    preview recomputes (sciforge.preview.recompute) then also rebuild it while SLOW["on"]."""
    doc = App.ActiveDocument
    obj = doc.getObject("SlowPart")
    if obj is None:
        obj = doc.addObject("App::FeaturePython", "SlowPart")
        SlowPart(obj)
        doc.recompute()
    from sciforge import preview

    if not getattr(preview.recompute, "slow_part", False):
        original = preview.recompute

        def recompute(doc):
            if SLOW["on"]:
                slow = doc.getObject("SlowPart")
                if slow is not None:
                    slow.touch()
            return original(doc)

        recompute.slow_part = True
        preview.recompute = recompute
    return obj


def release_during_recompute(pos, timeout_ms=5000):
    """With the left button down on a handle: move on to `pos` (a few pixels further, so
    the handle asks for one more preview, the slow one) and let the button come up there
    while that preview recomputes. The release is made from inside the slow part's
    recompute, where FreeCAD's progress bar takes it. Returns what happened."""
    info = {"fired": False}
    watcher = spy()

    def let_go():
        info["fired"] = True
        info["recomputing at release"] = recomputing()
        mark = watcher.mark()
        release(pos)
        info["3D view got the release"] = "release" in watcher.since(mark)["qt"]
        info["Qt left button down right after"] = held()

    SLOW["hook_error"] = None
    SLOW["on"] = True
    SLOW["hook"] = let_go
    try:
        move(pos)
        info["ms"] = wait_until(lambda: info["fired"] and not recomputing(), timeout_ms)
    finally:
        SLOW["on"] = False
        SLOW["hook"] = None
    if not info["fired"]:
        release(pos)  # no slow preview came: let go anyway (the case did not happen)
    if SLOW["hook_error"]:
        info["hook error"] = SLOW["hook_error"]
    return info


def widget_press_holds_button():
    """What every other scenario's drag relies on now that handles end a drag when Qt says
    no button is down: a widget-level QTest press (harness.drag) holds Qt's left button
    until its release."""
    widget = QtWidgets.QWidget()
    widget.resize(120, 120)
    widget.show()
    QtWidgets.QApplication.processEvents()
    pos = QtCore.QPoint(40, 40)
    QtTest.QTest.mousePress(widget, LEFT, NONE, pos)
    down = held()
    QtTest.QTest.mouseRelease(widget, LEFT, NONE, pos)
    up = held()
    widget.close()
    widget.deleteLater()
    return down, up
