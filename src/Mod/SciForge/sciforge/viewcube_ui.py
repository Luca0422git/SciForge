# SPDX-License-Identifier: LGPL-2.1-or-later
"""SciForge's ViewCube: the orientation cube in the top-right corner of every 3D view.

What a person can do with it (Fusion's behaviour, SciForge's own drawing and words):

* click a face, an edge or a corner: the view turns there, with FreeCAD's smooth camera
  animation (faces straight on, edges halfway between two faces, corners isometric);
* drag the cube: the model orbits exactly like Shift + middle-drag (it turns about the
  up axis and tilts, it never rolls); a click that moves only a few pixels is still a click;
* when a face is seen straight on: small triangles turn to the next face (90 degrees) and
  two curved arrows turn the picture 90 degrees;
* the small house above it: Go Home. Home is stored in the design (survives save and
  reopen); without one it is the isometric view from the front-right-top, fitted;
* right-click: Go Home, Orthographic / Perspective, Set Current View as Home (Fit to View
  or Fixed Distance), Reset Home;
* Ctrl+Alt+V hides or shows it.

How it works: a small see-through Qt widget sits on top of each 3D view's drawing area (a
child of FreeCAD's OpenGL widget). A light timer reads the camera of the active view 25
times a second (a few microseconds each time) and repaints the cube only when the camera
has moved. The cube's shape and all the maths are in viewcube.py (no Qt). FreeCAD's own
cube (the "NaviCube") is switched off by theme.VIEWER_SETTINGS while SciForge is on and
comes back when leaving SciForge.
"""
import re
import time

import FreeCAD as App
import FreeCADGui as Gui

from . import log, viewcube, warn
from .compat import QtCore, QtGui, QtWidgets

NAME = "SciForgeViewCube"
PARAMS = "User parameter:BaseApp/Preferences/Mod/SciForge"
HOME_KEY = "SciForgeHome"  # in the document's Meta: saved with the design

# Layout in widget pixels. The widget fits in the 142 px FreeCAD keeps free above the
# command dialog that floats on the right of the view (its "overlay").
WIDTH, HEIGHT = 140, 140
CX, CY, SIZE = 72.0, 78.0, 33.0  # centre of the cube and half its width
HOME_AT = (6.0, 6.0, 18.0)  # the house: left, top, side
TRIAD_AT = (21.0, HEIGHT - 21.0)  # far enough in that its letters are never cut off
TRIAD_LENGTH = 11.0
MARGIN_RIGHT, MARGIN_TOP = 2, 2
IDLE_OPACITY = 0.55  # see-through while the mouse is elsewhere
POLL_MS = 40
DRAG_START = 5  # pixels the mouse may move on a click before it becomes a drag

FACE = QtGui.QColor(236, 239, 243)
BEVEL = QtGui.QColor(204, 210, 219)
OUTLINE = QtGui.QColor(112, 120, 134)
LABEL = QtGui.QColor(66, 72, 84)
HOVER = QtGui.QColor("#6fb7f0")
BUTTON = QtGui.QColor(214, 219, 226)
AXIS_COLOURS = {
    "X": QtGui.QColor(232, 86, 76),
    "Y": QtGui.QColor(88, 178, 92),
    "Z": QtGui.QColor(80, 150, 245),
}

_state = {"on": False, "timer": None, "shown": True, "warned": set(), "view": None, "cube": None}


def _warn_once(msg):
    """A problem in the timer would repeat 25 times a second: say it once."""
    if msg not in _state["warned"]:
        _state["warned"].add(msg)
        warn(msg)


def _shade(colour, factor):
    return QtGui.QColor(
        min(255, int(colour.red() * factor)),
        min(255, int(colour.green() * factor)),
        min(255, int(colour.blue() * factor)),
    )


def _polygon(points):
    return QtGui.QPolygonF([QtCore.QPointF(x, y) for x, y in points])


def orientation_of(view):
    return tuple(view.getCameraOrientation().Q)


def set_orientation_now(view, rotation):
    """Turn the camera at once (no animation), about the point it looks at."""
    animated = view.isAnimationEnabled()
    try:
        if animated:
            view.setAnimationEnabled(False)
        view.setCameraOrientation(tuple(rotation))
    finally:
        if animated:
            view.setAnimationEnabled(True)


def _animation_seconds():
    group = App.ParamGet("User parameter:BaseApp/Preferences/View")
    if not group.GetBool("UseNavigationAnimations", True):
        return 0.0
    return max(0, group.GetInt("AnimationDuration", 500)) / 1000.0


def after_turn(view, target, then):
    """Run `then` once the camera has reached `target` (at once when FreeCAD does not
    animate; else when its animation ends, or after it should have)."""

    def finish():
        try:
            # FreeCAD's animation moves the camera in steps relative to where it is, and
            # can still be running here (Home on a view already at Home: the turn is done
            # at once, the move to the model's centre is not). Stopped first, so it does
            # not slide the view after `then` placed it.
            view.stopAnimating()
            if not viewcube.same_orientation(orientation_of(view), target, 1e-9):
                set_orientation_now(view, target)
        except Exception:
            pass  # the view was closed meanwhile: `then` says so
        try:
            then()
        except Exception as exc:
            warn("ViewCube: %s" % exc)

    if viewcube.same_orientation(orientation_of(view), target, 1e-6):
        finish()
        return
    started = time.time()
    limit = _animation_seconds() + 1.0

    def poll():
        try:
            arrived = viewcube.same_orientation(orientation_of(view), target, 1e-6)
        except Exception:
            return  # the view was closed meanwhile
        if arrived or time.time() - started > limit:
            finish()
        else:
            QtCore.QTimer.singleShot(30, poll)

    QtCore.QTimer.singleShot(30, poll)


# -- Home ------------------------------------------------------------------------------------


def _document(name):
    try:
        return App.getDocument(name) if name else App.ActiveDocument
    except Exception:
        return App.ActiveDocument


def home_of(doc):
    """The design's Home ({'rotation', 'fit', 'camera'}): stored, else the default one."""
    text = None
    try:
        text = doc.Meta.get(HOME_KEY) if doc is not None else None
    except Exception:
        text = None
    return viewcube.decode_home(text) or viewcube.default_home()


def set_home(view, doc, fit):
    """Remember the current view as the design's Home (stored in the document, so it is
    saved with it). fit True: "Fit to View", Home shows the whole model; False: "Fixed
    Distance", Home also comes back to this zoom and position."""
    camera = None if fit else view.getCamera()
    text = viewcube.encode_home(orientation_of(view), fit, camera)
    meta = dict(doc.Meta)
    meta[HOME_KEY] = text
    doc.Meta = meta
    log("Home set to the current view (%s)" % ("fit to view" if fit else "fixed distance"))


def reset_home(doc):
    meta = dict(doc.Meta)
    if HOME_KEY in meta:
        del meta[HOME_KEY]
        doc.Meta = meta
    log("Home reset to the isometric view")


def _camera_like(view, stored):
    """The stored Fixed Distance camera, as the current camera type: position, direction
    and the point looked at come from Home, the camera type (orthographic or perspective)
    stays the one chosen now."""
    current = view.getCamera()

    def kind(text):
        found = re.search(r"(\w+Camera)\s*\{", text or "")
        return found.group(1) if found else None

    if kind(stored) == kind(current):
        return stored
    for field in ("position", "orientation", "focalDistance"):
        line = re.search(r"^[ \t]*%s[ \t].*$" % field, stored, re.M)
        if line:
            current = re.sub(
                r"^[ \t]*%s[ \t].*$" % field, lambda _m: line.group(0), current, flags=re.M
            )
    return current


def go_home(view, doc):
    """Turn to the design's Home (animated when FreeCAD animates), then fit the model
    (Fit to View) or restore the stored zoom and position (Fixed Distance)."""
    home = home_of(doc)
    target = home["rotation"]
    view.setCameraOrientation(tuple(target), bool(home["fit"]))  # fit: centre on the model

    def finish():
        if home["fit"]:
            view.fitAll()
        else:
            view.setCamera(_camera_like(view, home["camera"]))

    after_turn(view, target, finish)


# -- the widget --------------------------------------------------------------------------------


class ViewCube(QtWidgets.QWidget):
    """The cube over one 3D view (child of its OpenGL widget)."""

    def __init__(self, gl, view, doc_name):
        super().__init__(gl)
        self.setObjectName(NAME)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        # The cube only: a style sheet without a selector would also reach its right-click
        # menu (a child) and paint that see-through.
        self.setStyleSheet("#%s { background: transparent; }" % NAME)
        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setCursor(QtCore.Qt.ArrowCursor)
        self.resize(WIDTH, HEIGHT)
        self.view = view
        self.doc_name = doc_name
        self.q = None
        self.parts = []  # visible cube parts, back to front (viewcube.layout)
        self.buttons = []  # the house, plus the arrows while a face is straight on
        self.face = None  # the face seen straight on, if any
        self.hover = None
        self.inside = False
        self.press = None  # (position, what was pressed) while the left button is down
        self.last = None
        self.dragging = False
        self.target = None  # (orientation, time) of the last arrow click
        self.right_on_cube = False  # the right button went down on the cube
        self.place()

    # -- following the view ----------------------------------------------------------------
    def place(self):
        """Top-right corner of the view (checked on every timer tick: the view gets
        narrower or wider when panels open and close)."""
        parent = self.parentWidget()
        if parent is None:
            return
        x = max(0, parent.width() - WIDTH - MARGIN_RIGHT)
        if self.x() != x or self.y() != MARGIN_TOP:
            self.move(x, MARGIN_TOP)
            self.raise_()

    def sync(self, view):
        """Follow the view: keep to its corner, redraw only when the camera moved."""
        self.view = view
        self.place()
        q = orientation_of(view)
        if self.q is None or not viewcube.same_orientation(q, self.q, 1e-9):
            self.set_orientation(q)
        elif getattr(self, "face_from_aim", False) and self._turning_to(q) is None:
            # The arrows were kept for a turn that is over or was stopped (a zoom or a pan
            # stops FreeCAD's animation part way): only a face seen straight on has them.
            self.set_orientation(q)

    def set_orientation(self, q):
        self.q = q
        self.parts = viewcube.layout(q, CX, CY, SIZE)
        self.face = viewcube.face_on(q)
        self.face_from_aim = False
        if self.face is None:
            # An arrow click is still turning the view to a face: the arrows stay, so a
            # quick second click adds up (and does not fall through to the model).
            aim = self._turning_to(q)
            self.face = viewcube.face_on(aim) if aim is not None else None
            self.face_from_aim = self.face is not None
        self.buttons = [
            c
            for c in viewcube.controls(CX, CY, SIZE, HOME_AT)
            if c["id"] == "home" or self.face is not None
        ]
        if self.hover is not None and self.hover not in self.targets():
            self.hover = None
        self.update()

    def _turning_to(self, q):
        """Where the last arrow click is still taking the view, or None."""
        last = getattr(self, "target", None)
        if last is None:
            return None
        aim, when = last
        if time.time() - when > _animation_seconds() + 0.2:
            return None
        if viewcube.same_orientation(q, aim, 1e-6):
            return None
        return aim

    def targets(self):
        """Everything clickable now: cube parts and buttons, {id: widget pixel to aim at}."""
        found = {}
        for part in self.parts:
            found[part["name"]] = viewcube.centroid(part["points"])
        for control in self.buttons:
            found[control["id"]] = viewcube.control_centre(control)
        return found

    def hit(self, x, y):
        for control in self.buttons:
            if viewcube.hit_control(control, x, y):
                return control["id"]
        return viewcube.pick(self.parts, x, y)

    # -- drawing ---------------------------------------------------------------------------
    def paintEvent(self, event):
        try:
            ratio = self.devicePixelRatioF()
            image = QtGui.QImage(
                int(WIDTH * ratio), int(HEIGHT * ratio), QtGui.QImage.Format_ARGB32_Premultiplied
            )
            image.setDevicePixelRatio(ratio)
            image.fill(QtCore.Qt.transparent)
            painter = QtGui.QPainter(image)
            try:
                painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
                painter.setRenderHint(QtGui.QPainter.TextAntialiasing, True)
                self._draw(painter)
            finally:
                painter.end()
            # Drawn whole first, then laid over the view at once: overlapping strokes do not
            # show through each other when the cube is see-through.
            painter = QtGui.QPainter(self)
            try:
                painter.setOpacity(1.0 if (self.inside or self.dragging) else IDLE_OPACITY)
                painter.drawImage(0, 0, image)
            finally:
                painter.end()
        except Exception as exc:
            _warn_once("ViewCube drawing: %s" % exc)

    def _draw(self, painter):
        if self.q is None:
            return
        pen = QtGui.QPen(OUTLINE, 1.0)
        pen.setJoinStyle(QtCore.Qt.RoundJoin)
        for part in self.parts:
            base = FACE if part["kind"] == "face" else BEVEL
            colour = HOVER if part["name"] == self.hover else _shade(base, part["shade"])
            painter.setPen(pen)
            painter.setBrush(colour)
            painter.drawPolygon(_polygon(part["points"]))
            if part["kind"] == "face" and part["facing"] > 0.12:
                self._draw_label(painter, part["name"])
        for control in self.buttons:
            self._draw_button(painter, control)
        self._draw_triad(painter)

    def _draw_label(self, painter, face):
        text = viewcube.FACE_LABELS[face]
        # Text is laid out in hundredths of the cube's half width, then mapped flat onto
        # the face (Qt fonts need whole pixel sizes).
        m11, m12, m21, m22, dx, dy = viewcube.label_transform(self.q, face, CX, CY, SIZE)
        k = 0.01
        transform = QtGui.QTransform(m11 * k, m12 * k, m21 * k, m22 * k, dx, dy)
        font = QtGui.QFont(QtWidgets.QApplication.font())
        font.setBold(True)
        font.setPixelSize(34)
        width = QtGui.QFontMetricsF(font).horizontalAdvance(text)
        room = 2 * viewcube.INNER * 100 * 0.86
        if width > room:
            font.setPixelSize(max(8, int(34 * room / width)))
        painter.save()
        painter.setTransform(transform, True)
        painter.setFont(font)
        painter.setPen(LABEL)
        painter.drawText(QtCore.QRectF(-100, -50, 200, 100), QtCore.Qt.AlignCenter, text)
        painter.restore()

    def _draw_button(self, painter, control):
        colour = HOVER if control["id"] == self.hover else BUTTON
        kind = control["kind"]
        painter.setPen(QtGui.QPen(OUTLINE, 1.0))
        painter.setBrush(colour)
        if kind == "triangle":
            painter.drawPolygon(_polygon(control["points"]))
        elif kind == "home":
            left, top, side = control["rect"]
            mid = left + side / 2.0
            roof = [
                (mid, top + 1.0),
                (left + side, top + side * 0.5),
                (left + side * 0.82, top + side * 0.5),
                (left + side * 0.82, top + side - 1.0),
                (left + side * 0.18, top + side - 1.0),
                (left + side * 0.18, top + side * 0.5),
                (left, top + side * 0.5),
            ]
            painter.drawPolygon(_polygon(roof))
            painter.setBrush(OUTLINE)
            door = QtCore.QRectF(mid - side * 0.1, top + side * 0.66, side * 0.2, side * 0.34 - 1)
            painter.drawRect(door)
        elif kind == "arc":
            cx, cy = control["centre"]
            r = control["radius"]
            rect = QtCore.QRectF(cx - r, cy - r, 2 * r, 2 * r)
            start = int(control["start"] * 16)
            span = int((control["end"] - control["start"]) * 16)
            for width, stroke in ((5.0, OUTLINE), (3.0, colour)):
                pen = QtGui.QPen(stroke, width)
                pen.setCapStyle(QtCore.Qt.FlatCap)
                painter.setPen(pen)
                painter.setBrush(QtCore.Qt.NoBrush)
                painter.drawArc(rect, start, span)
            painter.setPen(QtGui.QPen(OUTLINE, 1.0))
            painter.setBrush(colour)
            painter.drawPolygon(_polygon(viewcube.arc_head(control)))

    def _draw_triad(self, painter):
        ox, oy = TRIAD_AT
        axes = []
        for letter, direction in (("X", (1, 0, 0)), ("Y", (0, 1, 0)), ("Z", (0, 0, 1))):
            local = viewcube.project(self.q, direction)
            axes.append((local[2], letter, local))
        font = QtGui.QFont(QtWidgets.QApplication.font())
        font.setBold(True)
        font.setPixelSize(9)
        painter.setFont(font)
        for _, letter, local in sorted(axes):
            colour = AXIS_COLOURS[letter]
            end = QtCore.QPointF(ox + local[0] * TRIAD_LENGTH, oy - local[1] * TRIAD_LENGTH)
            pen = QtGui.QPen(colour, 2.0)
            pen.setCapStyle(QtCore.Qt.RoundCap)
            painter.setPen(pen)
            painter.drawLine(QtCore.QPointF(ox, oy), end)
            # The letter just past the end of its axis.
            lx, ly = local[0], -local[1]
            length = (lx * lx + ly * ly) ** 0.5
            if length > 0.2:
                tx, ty = end.x() + lx / length * 5.5, end.y() + ly / length * 5.5
            else:  # the axis points at you (or away): its letter beside the origin
                tx, ty = ox - 6.0, oy + 6.0
            painter.drawText(QtCore.QRectF(tx - 6, ty - 6, 12, 12), QtCore.Qt.AlignCenter, letter)

    # -- the mouse -------------------------------------------------------------------------
    def enterEvent(self, event):
        self.inside = True
        self.update()

    def leaveEvent(self, event):
        self.inside = False
        if not self.dragging:
            self.hover = None
        self.update()

    def mousePressEvent(self, event):
        try:
            button = event.button()
            pos = event.position()
            target = self.hit(pos.x(), pos.y())
            if button == QtCore.Qt.RightButton:
                # On the cube: its menu opens from contextMenuEvent. On a see-through corner:
                # the 3D view's own right-click (the marking menu).
                self.right_on_cube = target is not None
                event.setAccepted(self.right_on_cube)
                return
            if button != QtCore.Qt.LeftButton:
                event.ignore()  # middle button: pan/orbit in the view underneath
                return
            if target is None:
                event.ignore()  # see-through corner: the click is for the model behind
                return
            self.press = (QtCore.QPointF(pos), target)
            self.last = QtCore.QPointF(pos)
            self.dragging = False
            event.accept()
        except Exception as exc:
            warn("ViewCube: %s" % exc)

    def mouseMoveEvent(self, event):
        try:
            pos = event.position()
            if self.press is not None:
                start = self.press[0]
                moved = ((pos.x() - start.x()) ** 2 + (pos.y() - start.y()) ** 2) ** 0.5
                if not self.dragging and moved > DRAG_START:
                    self.dragging = True
                    self.hover = None
                if self.dragging:
                    self.drag_by(pos.x() - self.last.x(), pos.y() - self.last.y())
                    self.last = QtCore.QPointF(pos)
                event.accept()
                return
            if event.buttons() != QtCore.Qt.NoButton:
                event.ignore()
                return
            target = self.hit(pos.x(), pos.y())
            if target != self.hover:
                self.hover = target
                self.update()
            if target is None:
                event.ignore()  # over a see-through corner: the view shows its pre-selection
            else:
                event.accept()
        except Exception as exc:
            warn("ViewCube: %s" % exc)

    def mouseReleaseEvent(self, event):
        try:
            if event.button() == QtCore.Qt.RightButton:
                event.setAccepted(self.right_on_cube)
                return
            if event.button() != QtCore.Qt.LeftButton or self.press is None:
                event.ignore()
                return
            event.accept()
            target, dragged = self.press[1], self.dragging
            self.press, self.dragging = None, False
            pos = event.position()
            self.hover = self.hit(pos.x(), pos.y())
            self.update()
            if not dragged:
                self.activate(target)
        except Exception as exc:
            self.press, self.dragging = None, False
            warn("ViewCube: %s" % exc)

    def wheelEvent(self, event):
        """The wheel over the cube zooms the view underneath: the event is left for Qt to
        pass on to the view (FreeCAD's view also gets its own wheel events that way)."""
        event.ignore()

    def contextMenuEvent(self, event):
        try:
            pos = event.pos()
            if self.hit(pos.x(), pos.y()) is None:
                event.ignore()  # a see-through corner: for the 3D view
                return
            event.accept()
            self.open_menu(event.globalPos())
        except Exception as exc:
            warn("ViewCube menu: %s" % exc)

    # -- what a click does -----------------------------------------------------------------
    def activate(self, target):
        if target == "home":
            go_home(self.view, _document(self.doc_name))
        elif target.startswith("turn-"):
            self.step(lambda q: viewcube.turn(q, target[len("turn-") :]))
        elif target.startswith("roll-"):
            self.step(lambda q: viewcube.roll(q, target == "roll-cw"))
        else:
            self.view.setCameraOrientation(tuple(viewcube.target_orientation(target)))

    def step(self, change):
        """An arrow click: turn from the current view, or from where the previous arrow
        click is still taking it (quick clicks add up, like FreeCAD's cube)."""
        current = orientation_of(self.view)
        aim = self._turning_to(current)
        new = change(aim if aim is not None else current)
        self.target = (new, time.time())
        self.view.setCameraOrientation(tuple(new))

    def drag_by(self, dx, dy):
        """Orbit the model like Shift + middle-drag (turntable: about Z and sideways)."""
        new = viewcube.orbit(orientation_of(self.view), dx, dy)
        set_orientation_now(self.view, new)
        self.set_orientation(orientation_of(self.view))

    # -- the right-click menu --------------------------------------------------------------
    def open_menu(self, global_pos):
        view, doc_name = self.view, self.doc_name
        menu = QtWidgets.QMenu(self)
        menu.setObjectName("SciForgeViewCubeMenu")
        menu.addAction("Go Home", lambda: _safely(lambda: go_home(view, _document(doc_name))))
        menu.addSeparator()
        kind = view.getCameraType()
        for label in ("Orthographic", "Perspective"):
            action = menu.addAction(label, lambda t=label: _safely(lambda: _camera(view, t)))
            action.setCheckable(True)
            action.setChecked(kind == label)
        menu.addSeparator()
        sub = menu.addMenu("Set Current View as Home")
        sub.addAction(
            "Fit to View", lambda: _safely(lambda: set_home(view, _document(doc_name), True))
        )
        sub.addAction(
            "Fixed Distance", lambda: _safely(lambda: set_home(view, _document(doc_name), False))
        )
        menu.addAction("Reset Home", lambda: _safely(lambda: reset_home(_document(doc_name))))
        menu.exec_(global_pos)
        menu.deleteLater()


def _camera(view, kind):
    view.setCameraType(kind)
    log("camera: %s" % kind.lower())


def _safely(step):
    try:
        step()
    except Exception as exc:
        warn("ViewCube: %s" % exc)


# -- turning it on and off -----------------------------------------------------------------


def _cubes():
    try:
        return Gui.getMainWindow().findChildren(QtWidgets.QWidget, NAME)
    except Exception:
        return []


def cube_of(view):
    """The ViewCube widget of a 3D view (None if it has none yet)."""
    try:
        return view.graphicsView().viewport().findChild(QtWidgets.QWidget, NAME)
    except Exception:
        return None


def _alive(widget):
    try:
        return widget is not None and bool(widget.objectName())
    except RuntimeError:  # its view was closed
        return False


def _cube_for(view):
    """The cube of a 3D view, made the first time the view is used."""
    gl = view.graphicsView().viewport()
    cube = gl.findChild(QtWidgets.QWidget, NAME)
    if cube is None:
        gdoc = Gui.ActiveDocument
        cube = ViewCube(gl, view, gdoc.Document.Name if gdoc is not None else "")
    return cube


def _tick():
    """25 times a second: the active 3D view gets its cube, the cube follows the camera."""
    try:
        if not _state["on"]:
            return
        view = Gui.activeView()
        if view is None or not hasattr(view, "getCameraOrientation"):
            return
        if not hasattr(view, "graphicsView"):
            return
        cube = _state.get("cube")
        if _state.get("view") is not view or not _alive(cube):
            cube = _cube_for(view)
            _state["view"], _state["cube"] = view, cube
        if cube.isVisible() != _state["shown"]:
            cube.setVisible(_state["shown"])
        if _state["shown"]:
            cube.sync(view)
    except Exception as exc:
        _warn_once("ViewCube: %s" % exc)


def is_shown():
    return _state["shown"]


def enable():
    """SciForge's interface turned on: a cube on every 3D view (made when a view is used)."""
    _state["on"] = True
    _state["shown"] = App.ParamGet(PARAMS).GetBool("ShowViewCube", True)
    if _state["timer"] is None:
        timer = QtCore.QTimer(Gui.getMainWindow())
        timer.setInterval(POLL_MS)
        timer.timeout.connect(_tick)
        _state["timer"] = timer
    _state["timer"].start()
    _tick()


def disable():
    """SciForge's interface turned off: the cubes go (FreeCAD's own cube comes back)."""
    _state["on"] = False
    if _state["timer"] is not None:
        _state["timer"].stop()
    for cube in _cubes():
        try:
            cube.hide()
            cube.deleteLater()
        except RuntimeError:
            pass
    _state["view"] = _state["cube"] = None


def toggle():
    """Ctrl+Alt+V: hide or show the cube (remembered for the next start)."""
    _state["shown"] = not _state["shown"]
    App.ParamGet(PARAMS).SetBool("ShowViewCube", _state["shown"])
    for cube in _cubes():
        try:
            cube.setVisible(_state["shown"] and _state["on"])
        except RuntimeError:
            pass
    _tick()
    log("ViewCube %s" % ("shown" if _state["shown"] else "hidden"))


class ToggleViewCubeCommand:
    def GetResources(self):
        return {
            "MenuText": "Show/Hide ViewCube",
            "ToolTip": "Show or hide the ViewCube in the top-right corner of the view (Ctrl+Alt+V)",
        }

    def IsActive(self):
        return True

    def Activated(self):
        try:
            toggle()
        except Exception as exc:
            warn("ViewCube: %s" % exc)


COMMANDS = {"SciForge_ToggleViewCube": ToggleViewCubeCommand}
