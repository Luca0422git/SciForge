# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's orbit choice and mouse details on the 3D view.

What a person gets (Fusion's behaviour, SciForge's own code and words):

* **Orbit choice** (navigation bar, Orbit drop-down): Constrained (default, never rolls) or
  Free (tumbles). Remembered in SciForge's own preferences; applied as FreeCAD's
  OrbitStyle while SciForge is on, so the user's own FreeCAD setting comes back when
  SciForge is switched off (theme.keep_and_set / give_back).
* **Double-click of the middle button**: Fit. A single middle click does nothing (FreeCAD's
  "Revit" style, which SciForge uses for Fusion's mouse layout, would re-centre the view on
  the clicked point).
* **Ctrl + Shift + middle-drag**: zoom (up = in). The Revit style has nothing on it; FreeCAD
  gets the events as Ctrl + middle, its own zoom drag.
* **Shift + a single middle click** on the model: the orbit centre (pivot) goes there, with
  a small green dot. Shift + middle-drag stays the orbit; with a pivot set, SciForge turns
  the camera about the pivot itself (FreeCAD cannot be told a centre from Python).
* **Set Orbit Center / Reset Orbit Center** (right-click menu and commands): the next click
  on the model sets the pivot; Reset removes it and the dot.

How: a Qt event filter on each 3D view's drawing area sees the mouse before FreeCAD does
(like sketch_mode._ViewFilter). A middle press is held back until the mouse really moves;
then FreeCAD gets a copy of the press and the drag goes on as before (pan, orbit, or the
zoom with Ctrl only), so FreeCAD never sees a "quick middle click" to re-centre on. A press
that ends without a move is a click: nothing, Fit (double) or the pivot (Shift).
"""
import math

import FreeCAD as App
import FreeCADGui as Gui

from . import log, orbit, viewcube, warn
from .compat import QtCore, QtGui, QtWidgets

PARAMS = "User parameter:BaseApp/Preferences/Mod/SciForge"
MODE_KEY = "OrbitMode"  # "constrained" or "free", SciForge's own, kept across sessions
VIEW_PARAMS = "User parameter:BaseApp/Preferences/View"
CLICK_SLOP = 4  # pixels the mouse may move and still count as a click (a shaky hand)

MIDDLE = QtCore.Qt.MiddleButton
LEFT = QtCore.Qt.LeftButton
SHIFT = QtCore.Qt.ShiftModifier
CTRL = QtCore.Qt.ControlModifier
MODIFIERS = SHIFT | CTRL | QtCore.Qt.AltModifier | QtCore.Qt.MetaModifier

_state = {
    "filter": None,
    "widgets": [],
    "area": None,
    "arming": False,
    "on": False,
    "observer": None,
}
# document name -> {"doc": the App document, "point": (x, y, z), "marker": PivotMarker}.
# The entry goes when the design closes (_DocObserver), and is ignored for another design
# that happens to have the same name (the "doc" check).
_pivots = {}


# -- the orbit choice ----------------------------------------------------------------------


def mode():
    """The remembered orbit mode ("constrained" or "free")."""
    try:
        return orbit.normalise_mode(App.ParamGet(PARAMS).GetString(MODE_KEY, orbit.DEFAULT_MODE))
    except Exception as exc:
        warn("orbit mode: %s" % exc)
        return orbit.DEFAULT_MODE


def is_constrained():
    return mode() == orbit.CONSTRAINED


def is_free():
    return mode() == orbit.FREE


def apply_mode():
    """Set FreeCAD's OrbitStyle for the remembered mode. Called by theme.apply() right after
    the user's own value was kept, and by set_mode while SciForge is on."""
    App.ParamGet(VIEW_PARAMS).SetInt("OrbitStyle", orbit.freecad_style(mode()))


def set_mode(name):
    """Remember the orbit mode and, while SciForge is on, apply it to FreeCAD's orbit."""
    name = orbit.normalise_mode(name)
    App.ParamGet(PARAMS).SetString(MODE_KEY, name)
    from . import shell

    if shell.is_on():
        apply_mode()
    log("orbit: %s" % orbit.LABELS[name].lower())


# -- the orbit centre (pivot) ----------------------------------------------------------------


class PivotMarker:
    """The small green dot at the orbit centre: one Coin node in the view's scene, drawn on
    top of the model, never picked. Only a picture (like cut_preview.py's), nothing in the
    document."""

    def __init__(self):
        self.view = None
        self.node = None

    def show(self, view, point):
        from pivy import coin

        self.clear()
        node = coin.SoSeparator()
        node.setName(orbit.MARKER_NAME)
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE  # clicks go through to the model
        node.addChild(pick)
        top = coin.SoAnnotation()  # drawn after (over) everything else
        lighting = coin.SoLightModel()
        lighting.model = coin.SoLightModel.BASE_COLOR
        top.addChild(lighting)
        coords = coin.SoCoordinate3()
        coords.setName("point")
        coords.point.setValue(point.x, point.y, point.z)
        top.addChild(coords)
        dot_colour = coin.SoMaterial()
        dot_colour.diffuseColor.setValue(*orbit.MARKER_COLOUR)
        top.addChild(dot_colour)
        dot = coin.SoMarkerSet()
        dot.markerIndex.setValue(coin.SoMarkerSet.CIRCLE_FILLED_9_9)
        top.addChild(dot)
        rim_colour = coin.SoMaterial()
        rim_colour.diffuseColor.setValue(0.10, 0.35, 0.16)  # a darker rim: readable anywhere
        top.addChild(rim_colour)
        rim = coin.SoMarkerSet()
        rim.markerIndex.setValue(coin.SoMarkerSet.CIRCLE_LINE_9_9)
        top.addChild(rim)
        node.addChild(top)
        view.getSceneGraph().addChild(node)
        self.view, self.node = view, node

    def clear(self):
        node, self.node = self.node, None
        view, self.view = self.view, None
        if node is None or view is None:
            return
        try:
            view.getSceneGraph().removeChild(node)
        except Exception:
            pass  # the view closed with its design: the node went with it


def _doc_name():
    try:
        gdoc = Gui.ActiveDocument
        return gdoc.Document.Name if gdoc is not None else ""
    except Exception:
        return ""


def _active_view():
    try:
        view = Gui.ActiveDocument.ActiveView
        return view if hasattr(view, "getCameraNode") else None
    except Exception:
        return None


def _active_document():
    try:
        gdoc = Gui.ActiveDocument
        return gdoc.Document if gdoc is not None else None
    except Exception:
        return None


def _entry():
    """The active design's pivot entry, or None. An entry left by a closed design of the
    same name (the observer missed it) is dropped here."""
    name = _doc_name()
    entry = _pivots.get(name)
    if entry is None:
        return None
    try:
        if App.getDocument(name) is not entry["doc"]:
            _pivots.pop(name, None)
            return None
    except Exception:
        _pivots.pop(name, None)
        return None
    return entry


def pivot():
    """The orbit centre of the active design (App.Vector), or None when none is set."""
    entry = _entry()
    return App.Vector(*entry["point"]) if entry else None


def set_pivot(point, view=None):
    """Make `point` (App.Vector, global) the orbit centre of the active design: the dot
    shows there and Shift + middle-drag turns about it."""
    view = view if view is not None else _active_view()
    doc = _active_document()
    if view is None or doc is None:
        warn("orbit centre: no 3D view")
        return
    entry = _entry()
    if entry is None:
        entry = _pivots[doc.Name] = {"doc": doc, "marker": PivotMarker()}
    entry["point"] = (float(point.x), float(point.y), float(point.z))
    entry["marker"].show(view, point)
    log("orbit centre set to (%.2f, %.2f, %.2f)" % (point.x, point.y, point.z))


def clear_pivot():
    """Reset Orbit Center: the orbit turns about the middle of the window again."""
    entry = _entry()
    if entry is not None:
        entry = _pivots.pop(_doc_name(), None)
    if entry is not None:
        entry["marker"].clear()
        log("orbit centre reset")
    else:
        log("orbit centre reset (none was set)")


def _clear_all_pivots():
    for entry in _pivots.values():
        try:
            entry["marker"].clear()
        except Exception:
            pass
    _pivots.clear()


class _DocObserver:
    """Forgets a design's orbit centre when the design is closed: its view and the dot go
    with it, and the next design with the same name must not inherit the centre (the
    orbit would turn about an invisible point)."""

    def slotDeletedDocument(self, doc):
        try:
            _pivots.pop(doc.Name, None)
        except Exception as exc:
            warn("orbit centre: %s" % exc)


def marker_points(view=None):
    """Where orbit-centre dots are drawn in the view's scene (tests: the dot is at the
    clicked point, and gone after Reset)."""
    found = []
    try:
        view = view if view is not None else _active_view()
        root = view.getSceneGraph()
        for i in range(root.getNumChildren()):
            node = root.getChild(i)
            if node.getName().getString() != orbit.MARKER_NAME:
                continue
            coords = _find_coordinates(node)
            if coords is not None and coords.point.getNum():
                found.append(App.Vector(*coords.point.getValues()[0].getValue()))
    except Exception as exc:
        warn("orbit centre: %s" % exc)
    return found


def _find_coordinates(node):
    """The SoCoordinate3 inside a marker node (its point), searching the children."""
    from pivy import coin

    if isinstance(node, coin.SoCoordinate3):
        return node
    if isinstance(node, coin.SoGroup):
        for i in range(node.getNumChildren()):
            found = _find_coordinates(node.getChild(i))
            if found is not None:
                return found
    return None


# -- Set Orbit Center: waiting for a click -----------------------------------------------


def arm():
    """Set Orbit Center: the next click on the model sets the pivot."""
    _state["arming"] = True
    from . import commands

    commands.tell("Click a point on the model to set the orbit centre (Esc cancels)")


def disarm():
    _state["arming"] = False


def is_arming():
    return _state["arming"]


# -- turning the camera -------------------------------------------------------------------


def _camera(view):
    from pivy import coin  # noqa: F401  (view.getCameraNode() fails before pivy is loaded)

    cam = view.getCameraNode()
    position = tuple(cam.position.getValue().getValue())
    rotation = tuple(cam.orientation.getValue().getValue())  # (x, y, z, w)
    return cam, position, rotation


def _place(view, cam, position, rotation):
    try:
        view.stopAnimating()  # a turn still under way (a ViewCube click) must not fight it
    except Exception:
        pass
    cam.orientation.setValue(*rotation)
    cam.position.setValue(*position)


def _sensitivity():
    """FreeCAD's orbit sensitivity (View preference "Sensitivity", 2 by default): its own
    orbit multiplies the turn by it when it is above 1."""
    try:
        return App.ParamGet(VIEW_PARAMS).GetFloat("Sensitivity", 2.0)
    except Exception:
        return 2.0


def turn_about_pivot(view, centre, dx, dy, width, height):
    """Shift + middle-drag with a pivot set: the view turns about `centre` for a mouse move
    of (dx, dy) pixels, as much per pixel as FreeCAD's own orbit on a view this size."""
    cam, position, rotation = _camera(view)
    deg_x, deg_y = orbit.degrees_per_pixel(width, height, _sensitivity())
    new_position, new_rotation = orbit.orbit_camera(
        position, rotation, (centre.x, centre.y, centre.z), dx, dy, mode(), deg_x, deg_y
    )
    _place(view, cam, new_position, new_rotation)


def drag_camera(view, dx, dy, deg_per_pixel=viewcube.ORBIT_DEG_PER_PIXEL):
    """The ViewCube's drag: the same orbit as Shift + middle-drag, in the chosen mode and
    about the pivot when one is set (else about the point the camera looks at)."""
    cam, position, rotation = _camera(view)
    centre = pivot()
    if centre is None:
        centre = App.Vector(*orbit.focal_point(position, rotation, cam.focalDistance.getValue()))
    new_position, new_rotation = orbit.orbit_camera(
        position, rotation, (centre.x, centre.y, centre.z), dx, dy, mode(), deg_per_pixel
    )
    _place(view, cam, new_position, new_rotation)


def fit_view():
    try:
        Gui.runCommand("Std_ViewFitAll")
    except Exception as exc:
        warn("fit: %s" % exc)


# -- the mouse filter -----------------------------------------------------------------------


def _is_valid(widget):
    """The widget still exists (a closed view leaves Python wrappers of deleted widgets,
    whose old address can be reused by a new view)."""
    try:
        import shiboken6

        return widget is not None and shiboken6.isValid(widget)
    except Exception:
        try:
            widget.objectName()
            return True
        except Exception:
            return False


def _same(a, b):
    """The same live Qt object (Python wrappers of one widget are not always the same)."""
    if not _is_valid(a) or not _is_valid(b):
        return False
    try:
        import shiboken6

        return shiboken6.getCppPointer(a)[0] == shiboken6.getCppPointer(b)[0]
    except Exception:
        return a is b


def _view_for(gl):
    """The 3D view whose drawing area is the widget `gl`."""
    views = []
    active = _active_view()
    if active is not None:
        views.append(active)
    try:
        for name in App.listDocuments():
            gdoc = Gui.getDocument(name)
            views.extend(gdoc.mdiViewsOfType("Gui::View3DInventor"))
    except Exception:
        pass
    for view in views:
        try:
            if _same(view.graphicsView().viewport(), gl):
                return view
        except Exception:
            continue
    return active


def _picked_point(gl, pos):
    """The point of the model under widget pixel `pos` (App.Vector), or None."""
    view = _view_for(gl)
    if view is None:
        return None
    ratio = gl.devicePixelRatioF()
    x = int(round(pos.x() * ratio))
    y = int(round((gl.height() - pos.y()) * ratio))
    info = view.getObjectInfo((x, y))
    if not info:
        return None
    return App.Vector(info["x"], info["y"], info["z"])


def _plan(modifiers):
    """What a middle press with these modifiers means, or None for FreeCAD's own handling
    (Ctrl + middle is FreeCAD's zoom drag already)."""
    held = modifiers & MODIFIERS
    if held == QtCore.Qt.NoModifier:
        return "pan"
    if held == SHIFT:
        return "orbit"
    if held == (CTRL | SHIFT):
        return "zoom"
    return None


def _distance(a, b):
    return math.hypot(a.x() - b.x(), a.y() - b.y())


class _Press:
    """One middle-button press being handled."""

    def __init__(self, event, plan, double, centre):
        self.pos = QtCore.QPointF(event.position())
        self.global_pos = QtCore.QPointF(event.globalPosition())
        self.modifiers = event.modifiers()
        self.buttons = event.buttons()
        self.plan = plan  # "pan", "orbit" or "zoom"
        self.double = double  # the press of a double-click
        self.centre = centre  # the pivot, for an orbit with one set
        self.forwarded = False  # FreeCAD got the press (the mouse moved)
        self.turning = False  # SciForge orbits about the pivot itself
        self.done = False  # acted on already (a double-click): only its release is left
        self.last = QtCore.QPointF(event.position())


class _ViewFilter(QtCore.QObject):
    """The mouse on a 3D view's drawing area (and Esc on the view) for the middle button and
    for Set Orbit Center. Never blocks FreeCAD's own handling except as described above."""

    def __init__(self):
        super().__init__()
        self.busy = False  # our own copy of an event is being handled
        self.press = None  # the middle button's press, while it is down
        self.left = None  # a left press while Set Orbit Center waits for a click

    def eventFilter(self, obj, event):
        try:
            if self.busy:
                return False
            kind = event.type()
            if kind == QtCore.QEvent.KeyPress:
                if (
                    _state["arming"]
                    and event.key() == QtCore.Qt.Key_Escape
                    and not event.isAutoRepeat()
                ):
                    disarm()
                    log("Set Orbit Center cancelled")
                return False
            if kind in (QtCore.QEvent.MouseButtonPress, QtCore.QEvent.MouseButtonDblClick):
                return self._pressed(obj, event, kind == QtCore.QEvent.MouseButtonDblClick)
            if kind == QtCore.QEvent.MouseMove:
                return self._moved(obj, event)
            if kind == QtCore.QEvent.MouseButtonRelease:
                return self._released(obj, event)
        except Exception as exc:
            self.press = None
            self.left = None
            warn("orbit: %s" % exc)
        return False

    def _pressed(self, obj, event, double):
        button = event.button()
        if button == MIDDLE:
            plan = _plan(event.modifiers())
            if plan is None:
                return False
            centre = pivot() if plan == "orbit" else None
            self.press = _Press(event, plan, double, centre)
            if double:
                # The second press of a double-click (Qt: press, release, double-click,
                # release). Acted on here, not at its release: Fit, or the pivot with Shift.
                self.press.done = True
                if plan == "pan":
                    QtCore.QTimer.singleShot(0, fit_view)
                elif plan == "orbit":
                    self._pivot_at(obj, self.press.pos)
            return True  # held back: a click does nothing, a move hands it on
        if button == LEFT and _state["arming"] and not double:
            self.left = QtCore.QPointF(event.position())
            return True  # the click is for the orbit centre, not a selection
        return False

    def _moved(self, obj, event):
        press = self.press
        if press is None:
            return False
        if not (event.buttons() & MIDDLE):
            self.press = None  # the button went up somewhere else
            return False
        if press.done:
            # The second press of a double-click was acted on (Fit, the pivot): a move
            # with the button still down must not start a drag that FreeCAD never sees
            # the end of (it would go on panning / orbiting / zooming by itself).
            return True
        pos = QtCore.QPointF(event.position())
        if not press.forwarded and not press.turning:
            if _distance(pos, press.pos) <= CLICK_SLOP:
                return True  # still a click
            if press.plan == "orbit" and press.centre is not None:
                press.turning = True
                # From here, not from the press: FreeCAD's own orbit drops the first move
                # of a drag too, so the two turn the same amount for the same drag.
                press.last = pos
            else:
                modifiers = CTRL if press.plan == "zoom" else press.modifiers
                self._forward(
                    obj,
                    QtCore.QEvent.MouseButtonPress,
                    press.pos,
                    press.global_pos,
                    MIDDLE,
                    press.buttons,
                    modifiers,
                )
                press.forwarded = True
        if press.turning:
            dx, dy = pos.x() - press.last.x(), pos.y() - press.last.y()
            press.last = pos
            view = _view_for(obj)
            if view is not None:
                turn_about_pivot(view, press.centre, dx, dy, obj.width(), obj.height())
            return True
        if press.plan == "zoom":
            self._forward(
                obj,
                QtCore.QEvent.MouseMove,
                pos,
                event.globalPosition(),
                QtCore.Qt.NoButton,
                event.buttons(),
                CTRL,
            )
            return True
        return False  # pan or FreeCAD's orbit: the real move goes on to FreeCAD

    def _released(self, obj, event):
        button = event.button()
        if button == MIDDLE and self.press is not None:
            press, self.press = self.press, None
            if press.turning or press.done:
                return True
            if press.forwarded:
                if press.plan == "zoom":
                    self._forward(
                        obj,
                        QtCore.QEvent.MouseButtonRelease,
                        event.position(),
                        event.globalPosition(),
                        MIDDLE,
                        event.buttons(),
                        CTRL,
                    )
                    return True
                return False
            # A click: the button went up without a move to speak of. Nothing for a plain
            # one (Fusion); with Shift, the orbit centre.
            if press.plan == "orbit":
                self._pivot_at(obj, press.pos)
            return True
        if button == LEFT and self.left is not None:
            start, self.left = self.left, None
            if not _state["arming"]:
                return False
            disarm()
            if _distance(QtCore.QPointF(event.position()), start) <= CLICK_SLOP:
                if not self._pivot_at(obj, event.position()):
                    from . import commands

                    commands.tell("Nothing under the mouse: the orbit centre was not changed")
            return True
        return False

    def _pivot_at(self, obj, pos):
        """The orbit centre goes to the model point under widget pixel `pos` (from a timer,
        never inside the event). False when nothing of the model is there."""
        point = _picked_point(obj, pos)
        if point is None:
            return False
        view = _view_for(obj)
        QtCore.QTimer.singleShot(0, lambda: _safely(set_pivot, point, view))
        return True

    def _forward(self, obj, kind, pos, global_pos, button, buttons, modifiers):
        """Hand FreeCAD a copy of a mouse event (it comes back through this filter, which
        lets it pass)."""
        copy = QtGui.QMouseEvent(
            kind, QtCore.QPointF(pos), QtCore.QPointF(global_pos), button, buttons, modifiers
        )
        self.busy = True
        try:
            QtWidgets.QApplication.sendEvent(obj, copy)
        finally:
            self.busy = False


def _safely(step, *args):
    try:
        step(*args)
    except Exception as exc:
        warn("orbit: %s" % exc)


# -- turning it on and off ------------------------------------------------------------------


def _view_widgets():
    """(drawing area, viewer) of every open 3D view: the mouse goes to the drawing area
    (a QOpenGLWidget), the keyboard to the viewer around it."""
    area = Gui.getMainWindow().findChild(QtWidgets.QMdiArea)
    if area is None:
        return []
    found = []
    for sub in area.subWindowList():
        for widget in sub.findChildren(QtWidgets.QWidget):
            if widget.metaObject().className() != "QOpenGLWidget":
                continue
            viewer = widget.parentWidget()
            while viewer is not None:
                if viewer.metaObject().className() == "Gui::View3DInventorViewer":
                    break
                viewer = viewer.parentWidget()
            found.append(widget)
            if viewer is not None:
                found.append(viewer)
    return found


def _install():
    if _state["filter"] is None:
        return
    try:
        widgets = _view_widgets()
    except RuntimeError:
        return
    _state["widgets"] = [w for w in _state["widgets"] if _is_valid(w)]  # closed views go
    for widget in widgets:
        try:
            if not any(_same(widget, w) for w in _state["widgets"]):
                widget.installEventFilter(_state["filter"])
                _state["widgets"].append(widget)
        except RuntimeError:
            pass  # the view of a design being closed


def enable():
    """SciForge's interface turned on: the filter on every 3D view, now and later ones."""
    _state["on"] = True
    if _state["filter"] is None:
        _state["filter"] = _ViewFilter()
    _install()
    try:
        area = Gui.getMainWindow().findChild(QtWidgets.QMdiArea)
        if area is not None and _state["area"] is None:
            area.subWindowActivated.connect(lambda *_: _state["on"] and _install())
            _state["area"] = area
    except Exception as exc:
        warn("orbit: %s" % exc)
    try:
        if _state["observer"] is None:
            _state["observer"] = _DocObserver()
            App.addDocumentObserver(_state["observer"])
    except Exception as exc:
        _state["observer"] = None
        warn("orbit centre: cannot follow closing designs: %s" % exc)


def disable():
    """SciForge's interface turned off: FreeCAD's own mouse, no dots left in any view."""
    _state["on"] = False
    disarm()
    filt, _state["filter"] = _state["filter"], None
    for widget in _state["widgets"]:
        try:
            if filt is not None and _is_valid(widget):
                widget.removeEventFilter(filt)
        except RuntimeError:
            pass
    _state["widgets"] = []
    observer, _state["observer"] = _state["observer"], None
    if observer is not None:
        try:
            App.removeDocumentObserver(observer)
        except Exception:
            pass
    _clear_all_pivots()


# -- commands -------------------------------------------------------------------------------


class _Command:
    title = ""
    tip = ""

    def GetResources(self):
        return {"MenuText": self.title, "ToolTip": self.tip}

    def IsActive(self):
        return True

    def Activated(self):
        try:
            self.run()
        except Exception as exc:
            warn("%s: %s" % (self.title, exc))


class OrbitConstrainedCommand(_Command):
    title = "Constrained Orbit"
    tip = "Shift + middle-drag turns the model about its up axis and tilts it; it never rolls"

    def run(self):
        set_mode(orbit.CONSTRAINED)


class OrbitFreeCommand(_Command):
    title = "Free Orbit"
    tip = "Shift + middle-drag tumbles the model in any direction, rolling included"

    def run(self):
        set_mode(orbit.FREE)


def _has_view():
    """The two centre commands need a design with a 3D view (Set would otherwise wait for
    a click that can never come)."""
    try:
        return _active_view() is not None
    except Exception:
        return False


class SetOrbitCenterCommand(_Command):
    title = "Set Orbit Center"
    tip = "The next click on the model sets the point the orbit turns about"

    def IsActive(self):
        return _has_view()

    def run(self):
        arm()


class ResetOrbitCenterCommand(_Command):
    title = "Reset Orbit Center"
    tip = "The orbit turns about the middle of the view again; the green dot goes"

    def IsActive(self):
        return _has_view()

    def run(self):
        disarm()
        clear_pivot()


COMMANDS = {
    "SciForge_OrbitConstrained": OrbitConstrainedCommand,
    "SciForge_OrbitFree": OrbitFreeCommand,
    "SciForge_SetOrbitCenter": SetOrbitCenterCommand,
    "SciForge_ResetOrbitCenter": ResetOrbitCenterCommand,
}
