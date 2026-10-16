# SPDX-License-Identifier: LGPL-2.1-or-later
"""The protractor wheel shown while an angle handle is held, and the angle snap every turn
handle uses (Move's triad and Rotate handle, Revolve, the taper and Draft discs, Plane at
Angle, Section, Emboss, the Mesh plane cut, the patterns).

Luca: "maybe add a visual wheel of where its snapping and the angle its at". The wheel lies
in the plane the handle turns in, centred on its axis: a thin ring with a tick every 15
degrees (long ones at every 45, longest at every 90), the tick the angle snapped to lit, a
needle at the current angle and the angle as text beside it ("45.0 deg"). The snap itself
is angle_snap_core (always on; Ctrl held = free; Incremental Move keeps its steps).
"""

import math

import FreeCAD as App

from . import angle_snap_core as core
from . import warn

RING = (0.86, 0.88, 0.92)
LIT = (1.0, 0.85, 0.35)  # the snapped tick and its text (Move's hover yellow)
FREE = (0.92, 0.94, 0.98)


def ctrl_held():
    """True while Ctrl is held (the angle moves freely)."""
    try:
        from .compat import QtCore, QtWidgets

        mods = QtWidgets.QApplication.keyboardModifiers()
        return bool(mods & QtCore.Qt.ControlModifier)
    except Exception:
        return False


def ring_pixels(view, center, axis, zero, radius):
    """How big (radius, pixels) a ring of `radius` mm about `axis` at `center` is drawn: its
    widest extent on the screen (seen at a slant it is an ellipse)."""
    try:
        axis = App.Vector(axis).normalize()
        zero = App.Vector(zero).normalize()
        side = axis.cross(zero)
        cx, cy = view.getPointOnViewport(App.Vector(center))
        best = 0.0
        for k in range(8):
            a = math.pi * k / 8.0
            p = App.Vector(center) + (zero * math.cos(a) + side * math.sin(a)) * radius
            x, y = view.getPointOnViewport(p)
            best = max(best, math.hypot(float(x) - float(cx), float(y) - float(cy)))
        return best
    except Exception:
        return 0.0


def snap_angle(view, raw, center, axis, zero, radius, free=None):
    """(angle to use, snap angle or None) for a handle dragged to `raw` degrees (from its
    zero). Ctrl held: free; Incremental Move on: its steps; else the 45-degree snap with a
    pull of a few pixels along the ring as drawn."""
    from . import increments

    if free is None:
        free = ctrl_held()
    step = None
    try:
        if increments.is_on():
            step = increments.angular_step()
    except Exception:
        step = None
    tolerance = core.tolerance_degrees(ring_pixels(view, center, axis, zero, radius))
    return core.snap(raw, tolerance, free=free, step=step)


class ProtractorRing:
    """The wheel (see the module text) about `axis` through `center`, `radius` mm, angle 0
    along `zero`; positive angles turn right-handed about `axis`. update(angle, mark) moves
    the needle and the text and lights the tick `mark` (None: none); remove() takes it away."""

    def __init__(self, view, center, axis, zero, radius):
        from pivy import coin

        self.coin = coin
        self.view = view
        self.center = App.Vector(center)
        self.axis = App.Vector(axis).normalize()
        self.zero = App.Vector(zero).normalize()
        self.side = self.axis.cross(self.zero)
        self.radius = float(radius)
        self.angle = 0.0
        self.mark = None
        self.root = coin.SoAnnotation()  # over the part, like the handles
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        self.root.addChild(self._ring())
        self.root.addChild(self._ticks())
        self.lit_switch = coin.SoSwitch()
        self.lit_coords = coin.SoCoordinate3()
        self.lit_switch.addChild(self._line_node(self.lit_coords, LIT, 3.5))
        self.root.addChild(self.lit_switch)
        self.needle_coords = coin.SoCoordinate3()
        self.root.addChild(self._line_node(self.needle_coords, FREE, 1.5, dashed=True))
        self.text_sep = coin.SoSeparator()
        self.text_material = coin.SoMaterial()
        self.text_move = coin.SoTranslation()
        font = coin.SoFont()
        font.size.setValue(15.0)
        self.label = coin.SoText2()
        for node in (self.text_material, self.text_move, font, self.label):
            self.text_sep.addChild(node)
        self.root.addChild(self.text_sep)
        self.holder = self._skip_fit(self.root)
        self.update(0.0, None)
        self.view.getSceneGraph().addChild(self.holder)

    # -- geometry ------------------------------------------------------------------------------
    def point(self, degrees, scale=1.0):
        a = math.radians(degrees)
        return self.center + (self.zero * math.cos(a) + self.side * math.sin(a)) * (
            self.radius * scale
        )

    def tick_segment(self, degrees):
        """The two ends of the tick at `degrees` (longer at 45 / 90 multiples)."""
        if core.on_snap(degrees, 90.0) is not None:
            inner = 0.78
        elif core.on_snap(degrees, core.SNAP_EVERY) is not None:
            inner = 0.84
        else:
            inner = 0.92
        return self.point(degrees, inner), self.point(degrees, 1.0)

    # -- nodes ---------------------------------------------------------------------------------
    def _skip_fit(self, node):
        try:
            group = self.coin.SoType.fromName("SoSkipBoundingGroup").createInstance()
            group.addChild(node)
            return group
        except Exception:
            return node

    def _material(self, color, transparency=0.0):
        material = self.coin.SoMaterial()
        material.diffuseColor.setValue(*color)
        material.emissiveColor.setValue(*color)
        material.transparency.setValue(transparency)
        return material

    def _line_node(self, coords, color, width, dashed=False):
        coin = self.coin
        sep = coin.SoSeparator()
        style = coin.SoDrawStyle()
        style.lineWidth.setValue(width)
        if dashed:
            style.linePattern.setValue(0xF0F0)
        lines = coin.SoLineSet()
        lines.numVertices.setValue(2)
        for node in (self._material(color), style, coords, lines):
            sep.addChild(node)
        return sep

    def _ring(self):
        coin = self.coin
        sep = coin.SoSeparator()
        style = coin.SoDrawStyle()
        style.lineWidth.setValue(1.5)
        points = [self.point(360.0 * i / 96.0) for i in range(97)]
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, len(points), [(p.x, p.y, p.z) for p in points])
        lines = coin.SoLineSet()
        lines.numVertices.setValue(len(points))
        for node in (self._material(RING, 0.25), style, coords, lines):
            sep.addChild(node)
        return sep

    def _ticks(self):
        coin = self.coin
        sep = coin.SoSeparator()
        style = coin.SoDrawStyle()
        style.lineWidth.setValue(1.5)
        points = []
        for degrees, _long in core.ticks():
            a, b = self.tick_segment(degrees)
            points += [a, b]
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, len(points), [(p.x, p.y, p.z) for p in points])
        lines = coin.SoLineSet()
        lines.numVertices.setValues(0, len(points) // 2, [2] * (len(points) // 2))
        for node in (self._material(RING, 0.15), style, coords, lines):
            sep.addChild(node)
        return sep

    # -- state ---------------------------------------------------------------------------------
    def update(self, angle, mark):
        try:
            self.angle = float(angle)
            self.mark = mark
            a, b = self.center, self.point(self.angle, 1.08)
            self.needle_coords.point.setValues(0, 2, [(a.x, a.y, a.z), (b.x, b.y, b.z)])
            if mark is None:
                self.lit_switch.whichChild = -1
            else:
                a, b = self.point(mark, 0.7), self.point(mark, 1.12)
                self.lit_coords.point.setValues(0, 2, [(a.x, a.y, a.z), (b.x, b.y, b.z)])
                self.lit_switch.whichChild = 0
            spot = self.point(self.angle, 1.2)
            self.text_move.translation.setValue(spot.x, spot.y, spot.z)
            colour = LIT if mark is not None else FREE
            self.text_material.diffuseColor.setValue(*colour)
            self.text_material.emissiveColor.setValue(*colour)
            self.label.string.setValue(core.text(self.angle))
            LAST.update(angle=self.angle, mark=mark, text=core.text(self.angle))
        except Exception as exc:
            warn("protractor: %s" % exc)

    def text(self):
        return core.text(self.angle)

    def remove(self):
        try:
            self.view.getSceneGraph().removeChild(self.holder)
        except Exception:
            pass


class Wheel:
    """A handle's wheel, made when its drag starts and gone when it ends: show(...) /
    update(...) / hide(). WHEELS lists the ones on show (the tests look at them)."""

    def __init__(self):
        self.ring = None

    def show(self, view, center, axis, zero, radius):
        self.hide()
        try:
            self.ring = ProtractorRing(view, center, axis, zero, radius)
            WHEELS.append(self.ring)
        except Exception as exc:
            warn("protractor: %s" % exc)
            self.ring = None

    def update(self, angle, mark):
        if self.ring is not None:
            self.ring.update(angle, mark)

    def hide(self):
        if self.ring is not None:
            self.ring.remove()
            if self.ring in WHEELS:
                WHEELS.remove(self.ring)
            self.ring = None

    def shown(self):
        return self.ring is not None


WHEELS = []
LAST = {"angle": None, "mark": None, "text": ""}  # what the last wheel showed (for tests)
