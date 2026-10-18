# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Coin nodes of SciForge's drag handles: one look and one size rule for every distance
arrow, angle disc and slider ball (the sizes, colours and maths are in handle_look_core).

Every handle is drawn in pixel units under FreeCAD's SoShapeScale, which rescales it on
every frame so one unit is one pixel on the screen: the handle keeps its size whatever the
part is and however the view is zoomed (Fusion's handles do). The handle classes do their
own maths (grabbing, the value box, the tests' aim) with mm_per_px(view, point): the same
pixels in millimetres at the handle, worked out from the camera exactly as the drawing is.

The handles are drawn in FreeCAD's 3D-annotation pass (So3DAnnotation): after the part,
over it, with a depth buffer of their own, so a cone's far side never shows through its
near side (Coin's SoAnnotation draws without any depth test, which made the shaded arrows
look broken from some angles).
"""

import math
import time

import FreeCAD as App

from . import handle_look_core as core

_RATIO = {"time": 0.0, "value": 1.0}


def _pixel_ratio():
    """The 3D view's device pixel ratio (looked up at most once a second)."""
    now = time.monotonic()
    if now - _RATIO["time"] > 1.0:
        _RATIO["time"] = now
        try:
            from .taskui import view_widget

            gl = view_widget()
            _RATIO["value"] = float(gl.devicePixelRatioF()) if gl is not None else 1.0
        except Exception:
            _RATIO["value"] = 1.0
        _RATIO["value"] = _RATIO["value"] or 1.0
    return _RATIO["value"]


def mm_per_px(view, point):
    """Millimetres one screen pixel covers at the 3D `point` of `view`, from its camera, as
    SoShapeScale works it out for the drawing (the view volume's smaller side spans the
    camera's height, Coin's ADJUST_CAMERA). Falls back to taskui.mm_per_pixel."""
    try:
        from pivy import coin

        camera = view.getCameraNode()
        size = view.getSize()
        pixels = max(min(float(size[0]), float(size[1])) / _pixel_ratio(), 1.0)
        if camera.isOfType(coin.SoOrthographicCamera.getClassTypeId()):
            height = float(camera.height.getValue())
        else:
            position = App.Vector(*camera.position.getValue().getValue())
            look = App.Vector(view.getViewDirection())
            depth = max((App.Vector(point) - position).dot(look), 1e-6)
            height = 2.0 * depth * math.tan(float(camera.heightAngle.getValue()) / 2.0)
        if height > 0:
            return height / pixels
    except Exception:
        pass
    try:
        from .taskui import mm_per_pixel

        return mm_per_pixel(view, point)
    except Exception:
        return 0.1


def mm(view, point, pixels):
    """`pixels` on the screen in millimetres at `point`."""
    return core.length_mm(mm_per_px(view, point), pixels)


def screen(view, point):
    """Viewport pixel (Coin's: device pixels, y up) of the 3D `point`."""
    x, y = view.getPointOnViewport(App.Vector(point))
    return float(x), float(y)


_GL = {"time": 0.0, "widget": None}


def _gl_widget():
    """The active 3D view's drawing widget (looked up at most every half second)."""
    now = time.monotonic()
    widget = _GL["widget"]
    if widget is not None:
        try:
            widget.objectName()
        except RuntimeError:
            widget = None
    if widget is None or now - _GL["time"] > 0.5:
        _GL["time"] = now
        try:
            from .taskui import view_widget

            widget = view_widget()
        except Exception:
            widget = None
        _GL["widget"] = widget
    return widget


def cursor(view=None):
    """The mouse in viewport pixels (as `screen` gives them), or None when it is not over
    the 3D view or a mouse button is down."""
    try:
        from .compat import QtCore, QtGui, QtWidgets

        if QtWidgets.QApplication.mouseButtons() != QtCore.Qt.NoButton:
            return None
        gl = _gl_widget()
        if gl is None or not gl.isVisible():
            return None
        pos = gl.mapFromGlobal(QtGui.QCursor.pos())
        if not gl.rect().contains(pos):
            return None
        ratio = _pixel_ratio()
        return float(pos.x()) * ratio, float(gl.height() - pos.y()) * ratio
    except Exception:
        return None


def hovered(view, foot, tip, kind="arrow"):
    """True when the mouse (no button down) is on the handle drawn from 3D `foot` to `tip`
    (a disc or a ball: foot == tip)."""
    point = cursor(view)
    if point is None:
        return False
    try:
        a, b = screen(view, foot), screen(view, tip)
        return core.segment_distance(point, a, b) <= core.grab_px(kind) * _pixel_ratio()
    except Exception:
        return False


# -- roots ----------------------------------------------------------------------------------
def top_root(coin, place=None, pickable=False):
    """The root of a handle: drawn over the part (FreeCAD's So3DAnnotation, or Coin's
    SoAnnotation where that is missing). `place` (the handle's SoTransform) is child 0:
    the scenarios read a handle's position from root.getChild(0). pickable: Coin picks the
    handle in front of the part (pick style SHAPE_ON_TOP, for Coin draggers); otherwise
    Coin never picks it (the handle is grabbed by where it is on the screen)."""
    root = None
    try:
        kind = coin.SoType.fromName("So3DAnnotation")
        if not kind.isBad():
            root = kind.createInstance()
    except Exception:
        root = None
    if root is None:
        root = coin.SoAnnotation()
    if place is not None:
        root.addChild(place)
    pick = coin.SoPickStyle()
    pick.style = coin.SoPickStyle.SHAPE_ON_TOP if pickable else coin.SoPickStyle.UNPICKABLE
    root.addChild(pick)
    return root


class PixelScale:
    """A node whose children are in pixels: FreeCAD's SoShapeScale (rescaled every frame),
    else a plain SoScale that update() keeps right.

    plain: always the plain SoScale, for the invisible shape a Coin dragger is picked by.
    SoShapeScale works its scale out only when it draws: a handle made (or a view zoomed
    or fitted) a moment before a press is picked at the scale of the last frame, or at 1
    (one pixel = one mm: a huge arrow) before its first frame. Kept by mm_per_px from the
    start and on every poll, the picked shape is where the handle's maths says it is."""

    def __init__(self, coin, shape, view=None, point=None, plain=False):
        self.coin = coin
        self.shape = shape
        self.kit = None
        self.scale = None
        self._shown = None
        first = mm_per_px(view, point) if view is not None and point is not None else None
        try:
            kind = coin.SoType.fromName("SoShapeScale")
            if not plain and not kind.isBad():
                self.kit = kind.createInstance()
                self.kit.setPart("shape", shape)
                self.kit.scaleFactor.setValue(1.0)
                self.kit.active.setValue(True)
                self.node = self.kit
                return
        except Exception:
            self.kit = None
        self.node = coin.SoSeparator()
        self.scale = coin.SoScale()
        self.node.addChild(self.scale)
        self.node.addChild(shape)
        if first:
            self._set(first)

    def _set(self, value):
        self._shown = value
        self.scale.scaleFactor.setValue(value, value, value)

    def update(self, view, point):
        """Keep the fallback SoScale right for the zoom (SoShapeScale needs nothing)."""
        if self.scale is None:
            return
        value = mm_per_px(view, point)
        if self._shown is None or abs(value - self._shown) > 1e-3 * max(self._shown, 1e-12):
            self._set(value)

    def drawn_mm_per_px(self):
        """The scale the last frame drew with (mm per pixel), or None before one: the
        handle's size as Coin has it now over its size in pixels (SoShapeScale keeps its
        scale in a private part; its bounding box shows it)."""
        try:
            if self.kit is not None:
                coin = self.coin
                sizes = []
                for node in (self.kit, self.shape):
                    action = coin.SoGetBoundingBoxAction(coin.SbViewportRegion(400, 400))
                    action.apply(node)
                    box = action.getBoundingBox()
                    if box.isEmpty():
                        return None
                    sizes.append(box.getMax()[1] - box.getMin()[1])
                return sizes[0] / sizes[1] if sizes[1] > 1e-12 else None
            return self._shown
        except Exception:
            return None


# -- materials -------------------------------------------------------------------------------
class Paint:
    """The material of a handle's body: its own colour, lighter when hot."""

    def __init__(self, coin, colour, hot=None):
        self.material = coin.SoMaterial()
        self.colour = tuple(colour)
        self.hot = hot
        self._state = None
        self.set(False)

    def set(self, hot, colour=None):
        if colour is not None and tuple(colour) != self.colour:
            self.colour = tuple(colour)
            self._state = None
        if self._state == bool(hot):
            return
        self._state = bool(hot)
        diffuse, emissive = core.shaded(core.hot_colour(self.colour, hot, self.hot))
        self.material.diffuseColor.setValue(*diffuse)
        self.material.emissiveColor.setValue(*emissive)
        self.material.specularColor.setValue(0.35, 0.35, 0.35)
        self.material.shininess.setValue(0.35)


def _flat(coin, colour):
    """Children that draw flat in one colour without touching the depth buffer (an outline
    or a disc: drawn in order, under what comes after them)."""
    light = coin.SoLightModel()
    light.model = coin.SoLightModel.BASE_COLOR
    base = coin.SoBaseColor()
    base.rgb.setValue(*colour)
    depth = coin.SoDepthBuffer()
    depth.getField("test").setValue(True)
    depth.getField("write").setValue(False)
    return [light, base, depth], base


def _cylinder_cone(coin, parts, material=None):
    """The shaft (cylinder) and head (cone) of an arrow along +Y (see core.arrow_parts)."""
    sep = coin.SoSeparator()
    if material is not None:
        sep.addChild(material)
    complexity = coin.SoComplexity()
    complexity.value.setValue(0.9)
    sep.addChild(complexity)
    for name in ("shaft", "head"):
        centre, height, radius = parts[name]
        part = coin.SoSeparator()
        move = coin.SoTranslation()
        move.translation.setValue(0.0, centre, 0.0)
        part.addChild(move)
        if name == "shaft":
            shape = coin.SoCylinder()
            shape.radius.setValue(radius)
            shape.height.setValue(height)
        else:
            shape = coin.SoCone()
            shape.bottomRadius.setValue(radius)
            shape.height.setValue(height)
        part.addChild(shape)
        sep.addChild(part)
    return sep


def arrow_shape(coin, colour=core.BLUE, hot=core.BLUE_HOT, length=core.ARROW_PX, start=0.0):
    """Fusion's distance arrow in pixels along +Y, its foot at `start`: a light outline, then
    the shaded body. Returns (node, Paint)."""
    parts = core.arrow_parts(length=length, start=start)
    sep = coin.SoSeparator()
    outline = coin.SoSeparator()
    nodes, _base = _flat(coin, core.OUTLINE)
    for node in nodes:
        outline.addChild(node)
    outline.addChild(_cylinder_cone(coin, core.outline_parts(parts)))
    sep.addChild(outline)
    paint = Paint(coin, colour, hot)
    sep.addChild(_cylinder_cone(coin, parts, paint.material))
    return sep, paint


def unpickable(coin, node):
    """`node` in a separator that Coin never picks (a handle drawn under SoShapeScale,
    picked by its own grab shape: see PixelScale)."""
    sep = coin.SoSeparator()
    style = coin.SoPickStyle()
    style.style = coin.SoPickStyle.UNPICKABLE
    sep.addChild(style)
    sep.addChild(node)
    return sep


def grab_shape(coin, length=core.ARROW_PX, start=0.0):
    """Invisible cylinders along +Y over the arrow as it is drawn, a few pixels wider
    (core.grab_parts: slim round the shaft, wide round the head, nothing behind the foot):
    what a Coin dragger is picked by (Coin picks invisible shapes). A press on what the
    arrow stands on (a profile, a pattern copy's dot) still reaches that."""
    sep = coin.SoSeparator()
    style = coin.SoDrawStyle()
    style.style = coin.SoDrawStyle.INVISIBLE
    sep.addChild(style)
    for centre, height, radius in core.grab_parts(length=length, start=start).values():
        part = coin.SoSeparator()
        move = coin.SoTranslation()
        move.translation.setValue(0.0, centre, 0.0)
        part.addChild(move)
        shape = coin.SoCylinder()
        shape.radius.setValue(radius)
        shape.height.setValue(height)
        part.addChild(shape)
        sep.addChild(part)
    return sep


def _polygon(coin, radius, z=0.0, steps=32):
    sep = coin.SoSeparator()
    coords = coin.SoCoordinate3()
    points = [
        (radius * math.cos(2.0 * math.pi * i / steps), radius * math.sin(2.0 * math.pi * i / steps), z)
        for i in range(steps)
    ]
    coords.point.setValues(0, len(points), points)
    sep.addChild(coords)
    face = coin.SoFaceSet()
    face.numVertices.setValue(len(points))
    sep.addChild(face)
    return sep


class DiscPaint:
    """The disc's face colour: white, light blue when hot."""

    def __init__(self, base, colour=core.DISC, hot=core.DISC_HOT):
        self.base = base
        self.colour = tuple(colour)
        self.hot = tuple(hot)
        self._state = None
        self.set(False)

    def set(self, hot, colour=None):
        if colour is not None and tuple(colour) != self.colour:
            self.colour = tuple(colour)
            self._state = None
        if self._state == bool(hot):
            return
        self._state = bool(hot)
        self.base.rgb.setValue(*(self.hot if hot else self.colour))


def disc_shape(coin, colour=core.DISC, hot=core.DISC_HOT, pick=False):
    """Fusion's angle handle in pixels: a flat disc facing the viewer (a billboard) with a
    dark dot in its middle and a thin rim. pick: also an invisible disc a few pixels
    wider, for a Coin dragger to be picked by. Returns (node, DiscPaint)."""
    sep = coin.SoSeparator()
    face = None
    board = _billboard(coin)
    rim = coin.SoSeparator()
    nodes, _ = _flat(coin, core.DISC_OUTLINE)
    for node in nodes:
        rim.addChild(node)
    rim.addChild(_polygon(coin, core.DISC_RADIUS_PX + core.OUTLINE_PX))
    board.addChild(rim)
    body = coin.SoSeparator()
    nodes, face = _flat(coin, colour)
    for node in nodes:
        body.addChild(node)
    body.addChild(_polygon(coin, core.DISC_RADIUS_PX))
    board.addChild(body)
    dot = coin.SoSeparator()
    nodes, _ = _flat(coin, core.DOT)
    for node in nodes:
        dot.addChild(node)
    dot.addChild(_polygon(coin, core.DOT_RADIUS_PX, steps=20))
    board.addChild(dot)
    if pick:
        board.addChild(_invisible_disc(coin))
    sep.addChild(board)
    return sep, DiscPaint(face, colour, hot)


def _billboard(coin):
    try:
        board = coin.SoVRMLBillboard()
        board.axisOfRotation.setValue(0.0, 0.0, 0.0)  # turned to face the viewer
    except Exception:
        board = coin.SoSeparator()
    return board


def _invisible_disc(coin):
    grab = coin.SoSeparator()
    style = coin.SoDrawStyle()
    style.style = coin.SoDrawStyle.INVISIBLE
    grab.addChild(style)
    grab.addChild(_polygon(coin, core.grab_px("disc")))
    return grab


def disc_grab(coin):
    """An invisible disc facing the viewer, a few pixels wider than the drawn one (pixels):
    what a Coin dragger with a disc_shape is picked by (under PixelScale(plain=True))."""
    board = _billboard(coin)
    board.addChild(_invisible_disc(coin))
    return board


def ball_shape(coin, colour=core.BLUE, hot=core.BLUE_HOT):
    """A blue ball in pixels (a point slid along a path) with the light outline behind it.
    Returns (node, Paint)."""
    sep = coin.SoSeparator()
    outline = coin.SoSeparator()
    nodes, _ = _flat(coin, core.OUTLINE)
    for node in nodes:
        outline.addChild(node)
    ring = coin.SoSphere()
    ring.radius.setValue(core.BALL_RADIUS_PX + core.OUTLINE_PX)
    outline.addChild(ring)
    sep.addChild(outline)
    paint = Paint(coin, colour, hot)
    body = coin.SoSeparator()
    body.addChild(paint.material)
    ball = coin.SoSphere()
    ball.radius.setValue(core.BALL_RADIUS_PX)
    body.addChild(ball)
    sep.addChild(body)
    return sep, paint


class Line:
    """A thin light polyline (the arc a disc rides on, an arrow's guide line) in mm."""

    def __init__(self, coin, colour=core.ARC, width=core.ARC_WIDTH_PX):
        self.node = coin.SoSeparator()
        nodes, self.base = _flat(coin, colour)
        for node in nodes:
            self.node.addChild(node)
        style = coin.SoDrawStyle()
        style.lineWidth.setValue(width)
        self.node.addChild(style)
        self.coords = coin.SoCoordinate3()
        self.lines = coin.SoLineSet()
        self.node.addChild(self.coords)
        self.node.addChild(self.lines)
        self._points = None

    def set_points(self, points):
        flat = [(float(p[0]), float(p[1]), float(p[2])) for p in points]
        if len(flat) < 2:
            flat = (flat * 2)[:2] if flat else [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0)]
        if flat == self._points:
            return
        self._points = flat
        self.coords.point.setValues(0, len(flat), flat)
        self.coords.point.setNum(len(flat))
        self.lines.numVertices.setValue(len(flat))
