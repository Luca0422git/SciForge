# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's 3D Sketch in the open sketch: the palette's 3D Sketch box, the 3D Line and 3D
Spline tools with the manipulator, and the triad that moves a 3D point.

Fusion (Autodesk help "Create a 3D sketch"; tech tip "Allow 3D sketching of lines and
splines"; forum answers; parity/sketch.md "Sketch, part 2"):

- 3D Sketch in the SKETCH PALETTE: Line and Fit Point Spline then draw in 3D. A
  manipulator sits at the last point placed (the sketch origin at first): three small
  planes; the next point lands on the active plane through that point (the sketch's own
  plane to begin with); a click on one of the manipulator's planes makes it the active
  one. A click on a corner of the design (or on a point already drawn) puts the point
  there; Ctrl places it exactly under the pointer on the plane, without snapping.
- A point of a 3D curve, clicked with no tool running, shows a triad (three arrows along
  the sketch's X, Y and Z): dragging an arrow moves the point along it; typing a distance
  and Enter moves it that far from where it was (one undo step either way).

The 3D curves live in the sketch's "3D Curves" object (sketch3d.py). The tools run on
SciForge's own sketch handler (sketch_draw.DrawTool): they compute their picks themselves.
Never lets an exception out (warn() and carry on).
"""

import math

import FreeCAD as App
import FreeCADGui as Gui

from . import handle_look, log, warn
from . import sketch3d
from . import sketch3d_core as core
from . import sketch_draw as draw
from .compat import QtCore, QtWidgets

COLOURS = {"XY": (0.30, 0.55, 1.0), "YZ": (1.0, 0.35, 0.35), "ZX": (0.35, 0.85, 0.40)}
AXIS_COLOURS = {"X": (1.0, 0.35, 0.35), "Y": (0.35, 0.85, 0.40), "Z": (0.30, 0.55, 1.0)}
MANIPULATOR_PX = 56  # the manipulator's planes reach this far from the point (pixels)
TRIAD_PX = 70  # a triad arrow's length (pixels)
ARROW_PICK_PX = 8
POINT_PICK_PX = 8
LABELS = {"XY": "XY plane", "YZ": "YZ plane", "ZX": "ZX plane"}


def _vec(p):
    return App.Vector(p[0], p[1], p[2])


def _tuple(v):
    return (v.x, v.y, v.z)


# -- the view, in sketch coordinates ------------------------------------------------------
class View3D:
    """The pointer's ray and screen positions in the open sketch's own coordinates."""

    def __init__(self, session):
        self.session = session
        self.view = session.view
        self.gl = session.gl
        self.ratio = self.gl.devicePixelRatioF() or 1.0
        self.place = session.sketch.getGlobalPlacement()
        self.inverse = self.place.inverse()

    def coin(self, pos):
        return (
            int(round(pos.x()) * self.ratio),
            int((self.gl.height() - round(pos.y()) - 1) * self.ratio),
        )

    def ray(self, pos):
        """(origin, direction) of the pointer's ray in sketch coordinates."""
        from .profile_pick import mouse_ray

        point, direction = mouse_ray(self.view, self.coin(pos))
        origin = self.inverse.multVec(point)
        d = self.inverse.Rotation.multVec(direction)
        return _tuple(origin), _tuple(d)

    def screen(self, local):
        """Widget pixel (x, y) of a sketch point (x, y, z)."""
        world = self.place.multVec(_vec(local))
        x, y = self.view.getPointOnViewport(world)
        return (x / self.ratio, self.gl.height() - y / self.ratio)

    def mm_per_px(self, local):
        a = self.screen(local)
        b = self.screen(core.add(local, (1.0, 0.0, 0.0)))
        c = self.screen(core.add(local, (0.0, 1.0, 0.0)))
        d = max(math.hypot(a[0] - b[0], a[1] - b[1]), math.hypot(a[0] - c[0], a[1] - c[1]))
        return 1.0 / d if d > 1e-9 else 0.25


def _pixel(pos):
    return (pos.x(), pos.y())


# -- the session's 3D state ---------------------------------------------------------------
def layer(session, create=True):
    """The open sketch's 3D Sketch layer (made on first use)."""
    found = getattr(session, "sketch3d", None)
    if found is None and create and not session.closed:
        found = Layer(session)
        session.sketch3d = found
    return found


def is_on(session):
    found = layer(session, create=False) if session is not None else None
    return bool(found is not None and found.on)


def set_on(session, on):
    found = layer(session)
    if found is not None:
        found.set_on(on)


def starts_on(sketch):
    """A sketch that already has 3D curves opens with 3D Sketch checked (Guess)."""
    obj = sketch3d.curves_of(sketch)
    return obj is not None and bool(obj.Lines or obj.Splines)


class Layer(QtCore.QObject):
    """3D Sketch for one open sketch: the on / off state and the active plane, the points
    of the 3D curves picked and moved with the triad (when no tool runs)."""

    def __init__(self, session):
        super().__init__()
        self.session = session
        self.on = False
        self.plane = "XY"
        self.triad = None  # Triad while a 3D point is picked
        self._watching = []
        for widget in (session.gl, session.viewer):
            if widget is not None:
                widget.installEventFilter(self)  # after the session's: runs first
                self._watching.append(widget)

    def set_on(self, on, quiet=False):
        on = bool(on)
        if on == self.on:
            return
        self.on = on
        if not on:
            self.drop_triad()
        try:
            palette = getattr(self.session, "palette", None)
            box = getattr(palette, "sketch3d", None)
            if box is not None and box.isChecked() != on:
                box.setChecked(on)
        except Exception:
            pass
        log("3D Sketch %s" % ("on" if on else "off"))
        if quiet:
            return
        from . import commands

        commands.tell(
            "3D Sketch: Line and Fit Point Spline now draw in 3D (click the manipulator's "
            "planes to draw on another plane; click a 3D point to move it with the arrows)."
            if on
            else "3D Sketch off: the sketch tools draw on the sketch plane."
        )

    # -- the 3D points ---------------------------------------------------------------------
    def curves(self):
        return sketch3d.curves_of(self.session.sketch)

    def point_at(self, pos):
        """(index, sketch point) of a 3D point under the pointer, or None."""
        obj = self.curves()
        if obj is None:
            return None
        v = View3D(self.session)
        best = None
        for i, p in enumerate(sketch3d.resolved_points(obj, self.session.sketch)):
            s = v.screen(p)
            d = math.hypot(s[0] - pos.x(), s[1] - pos.y())
            if d <= POINT_PICK_PX and (best is None or d < best[0]):
                best = (d, i, p)
        return (best[1], best[2]) if best else None

    def drop_triad(self):
        triad, self.triad = self.triad, None
        if triad is not None:
            triad.remove()

    # -- events ------------------------------------------------------------------------------
    def _idle(self):
        """No tool runs: the triad and point picks are ours."""
        session = self.session
        tool = getattr(session, "tool", None)
        if tool is not None and tool.active:
            return False
        try:
            return not session.tool_running() and session.editor is None
        except Exception:
            return False

    def eventFilter(self, obj, event):
        try:
            session = self.session
            if not self.on or session.closed:
                return False
            kind = event.type()
            if kind in (QtCore.QEvent.KeyPress, QtCore.QEvent.ShortcutOverride):
                if self.triad is not None and self._idle():
                    return self.triad.key(event, kind)
                return False
            if obj is not session.gl or not self._idle():
                return False
            if self.triad is not None and self.triad.mouse(event):
                return True
            if kind == QtCore.QEvent.MouseButtonPress and event.button() == QtCore.Qt.LeftButton:
                found = self.point_at(event.position())
                if found is not None:
                    self.drop_triad()
                    self.triad = Triad(self, found[0])
                    log("3D Sketch: point %d picked (drag an arrow, or type a distance)" % found[0])
                    return True
                if self.triad is not None:
                    self.drop_triad()
        except Exception as exc:
            warn("3D Sketch: %s" % exc)
        return False

    def remove(self):
        self.drop_triad()
        for widget in self._watching:
            try:
                widget.removeEventFilter(self)
            except Exception:
                pass
        self._watching = []


# -- the triad --------------------------------------------------------------------------------
BOX_STYLE = draw.BOX_STYLE


class Triad:
    """Three arrows on a 3D point: drag one to move the point along it; or type a
    distance (it goes along the arrow used last, Z at first) and press Enter."""

    def __init__(self, layer_, index):
        from pivy import coin

        self.layer = layer_
        self.session = layer_.session
        self.index = index
        self.axis = "Z"
        self.drag = None  # {"axis", "t0", "moved"}
        self.typing = None
        obj = layer_.curves()
        self.start = sketch3d.resolved_points(obj, self.session.sketch)[index]
        # Drawn like every SciForge handle (handle_look: Fusion's arrows, over the part,
        # TRIAD_PX long on the screen whatever the zoom), in the axis colours.
        self.root = handle_look.top_root(coin)
        self.root.setName("SciForgeSketch3DTriad")
        self.transform = coin.SoTransform()
        self.root.addChild(self.transform)
        self.at = coin.SoTranslation()  # the point, in sketch coordinates
        self.root.addChild(self.at)
        shapes = coin.SoSeparator()
        for axis in ("X", "Y", "Z"):
            sep = coin.SoSeparator()
            turn = coin.SoRotation()  # the arrow is built along +Y
            rot = App.Rotation(App.Vector(0, 1, 0), App.Vector(*core.AXIS_DIRECTIONS[axis]))
            turn.rotation.setValue(*rot.Q)
            sep.addChild(turn)
            arrow, _paint = handle_look.arrow_shape(
                coin, AXIS_COLOURS[axis], handle_look.core.AXIS_HOT, length=TRIAD_PX
            )
            sep.addChild(arrow)
            shapes.addChild(sep)
        self.pixels = handle_look.PixelScale(coin, shapes)
        self.root.addChild(self.pixels.node)
        self.session.view.getSceneGraph().addChild(self.root)
        self.box = QtWidgets.QLineEdit(self.session.gl)
        self.box.setObjectName("SciForgeSketch3DValue")
        self.box.setFocusPolicy(QtCore.Qt.NoFocus)
        self.box.setReadOnly(True)
        self.box.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.box.setStyleSheet(BOX_STYLE)
        self.draw()

    def point(self):
        obj = self.layer.curves()
        return sketch3d.resolved_points(obj, self.session.sketch)[self.index]

    def arrows(self, v):
        """{axis: (base, tip)} in sketch coordinates."""
        p = self.point()
        world = v.place.multVec(App.Vector(*p))
        size = TRIAD_PX * handle_look.mm_per_px(v.view, world)  # as handle_look draws it
        return {
            axis: (p, core.add(p, core.mul(core.AXIS_DIRECTIONS[axis], size)))
            for axis in ("X", "Y", "Z")
        }

    def draw(self):
        v = View3D(self.session)
        place = v.place
        self.transform.translation.setValue(*place.Base)
        self.transform.rotation.setValue(*place.Rotation.Q)
        p = self.point()
        self.at.translation.setValue(*p)
        self.pixels.update(v.view, v.place.multVec(App.Vector(*p)))
        self._box(v)

    def _box(self, v):
        moved = core.dot(core.sub(self.point(), self.start), core.AXIS_DIRECTIONS[self.axis])
        text = "%s %s" % (
            self.axis,
            self.typing if self.typing is not None else "%s mm" % _num(moved),
        )
        if self.box.text() != text:
            self.box.setText(text)
        self.box.setFixedWidth(max(64, self.box.fontMetrics().horizontalAdvance(text + "00") + 14))
        tip = self.arrows(v)[self.axis][1]
        x, y = v.screen(tip)
        gl = self.session.gl
        x = max(2, min(int(x) + 12, gl.width() - self.box.width() - 2))
        y = max(2, min(int(y) + 8, gl.height() - self.box.height() - 2))
        self.box.move(x, y)
        if not self.box.isVisible():
            self.box.show()
            self.box.raise_()

    def arrow_at(self, pos):
        v = View3D(self.session)
        best = None
        for axis, (a, b) in self.arrows(v).items():
            d = core.segment_distance(_pixel(pos), v.screen(a), v.screen(b))
            if d <= ARROW_PICK_PX and (best is None or d < best[0]):
                best = (d, axis)
        return best[1] if best else None

    def _t(self, pos, axis, base):
        v = View3D(self.session)
        origin, direction = v.ray(pos)
        return core.closest_on_axis(origin, direction, base, core.AXIS_DIRECTIONS[axis])

    # -- the mouse ------------------------------------------------------------------------
    def mouse(self, event):
        kind = event.type()
        if kind == QtCore.QEvent.MouseButtonPress and event.button() == QtCore.Qt.LeftButton:
            axis = self.arrow_at(event.position())
            if axis is None:
                return False
            self.axis = axis
            self.typing = None
            base = self.point()
            t0 = self._t(event.position(), axis, base)
            if t0 is None:
                return True
            self.drag = {"axis": axis, "t0": t0, "base": base, "moved": False}
            self.draw()
            return True
        if kind == QtCore.QEvent.MouseMove and self.drag is not None:
            if not event.buttons() & QtCore.Qt.LeftButton:
                if QtWidgets.QApplication.mouseButtons() & QtCore.Qt.LeftButton:
                    return True  # (xvfb now and then sends a move without the held button)
                self._end_drag()
                return True
            t = self._t(event.position(), self.drag["axis"], self.drag["base"])
            if t is None:
                return True
            if not self.drag["moved"]:
                self.session.doc.openTransaction("Move 3D Point")
                self.drag["moved"] = True
            d = core.AXIS_DIRECTIONS[self.drag["axis"]]
            self._move(core.add(self.drag["base"], core.mul(d, t - self.drag["t0"])))
            return True
        if kind == QtCore.QEvent.MouseButtonRelease and self.drag is not None:
            self._end_drag()
            return True
        return False

    def _end_drag(self):
        drag, self.drag = self.drag, None
        if drag is not None and drag["moved"]:
            self.session.doc.commitTransaction()
            log("3D Sketch: point %d moved along %s" % (self.index, drag["axis"]))
        self.draw()

    def _move(self, point):
        obj = self.layer.curves()
        if obj is None:
            return
        sketch3d.move_point(obj, self.index, point)
        self.draw()

    # -- typing -------------------------------------------------------------------------
    def key(self, event, kind):
        key = event.key()
        text = event.text()
        if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            if self.typing is None:
                return False
            if kind == QtCore.QEvent.KeyPress and not event.isAutoRepeat():
                QtCore.QTimer.singleShot(0, self._apply_typed)
            event.accept()
            return True
        if key == QtCore.Qt.Key_Escape:
            if kind == QtCore.QEvent.KeyPress:
                QtCore.QTimer.singleShot(0, self.layer.drop_triad)
            return False  # the sketch's own Esc goes on (it clears the selection)
        if key == QtCore.Qt.Key_Backspace and self.typing is not None:
            if kind == QtCore.QEvent.KeyPress:
                self.typing = self.typing[:-1]
                self.draw()
            event.accept()
            return True
        value_char = text and (text.isdigit() or text in ".,-+")
        if value_char or (text and text.isalpha() and self.typing):
            if kind == QtCore.QEvent.KeyPress:
                self.typing = (self.typing or "") + text
                self.draw()
            event.accept()
            return True
        return False

    def _apply_typed(self):
        """The typed distance, Enter (from a Qt timer: nothing gets out)."""
        try:
            self._apply_typed_now()
        except Exception as exc:
            warn("3D Sketch: %s" % exc)

    def _apply_typed_now(self):
        text, self.typing = self.typing, None
        try:
            field = draw.Field("distance", draw.LENGTH)
            value = _signed(field, text)
        except ValueError as exc:
            from . import commands

            commands.tell("3D Sketch: %s" % exc)
            self.draw()
            return
        doc = self.session.doc
        doc.openTransaction("Move 3D Point")
        try:
            d = core.AXIS_DIRECTIONS[self.axis]
            self._move(core.add(self.start, core.mul(d, value)))
        except Exception as exc:
            doc.abortTransaction()
            warn("3D Sketch: %s" % exc)
            return
        doc.commitTransaction()
        log("3D Sketch: point %d set %s mm along %s" % (self.index, _num(value), self.axis))

    def remove(self):
        try:
            self.session.view.getSceneGraph().removeChild(self.root)
        except Exception:
            pass
        try:
            self.box.hide()
            self.box.setParent(None)
            self.box.deleteLater()
        except Exception:
            pass


def _signed(field, text):
    """A typed distance that may be negative (the other way along the arrow)."""
    text = (text or "").strip()
    negative = text.startswith("-")
    value = field.parse(text[1:] if negative else text)
    return -value if negative else value


def _num(value):
    text = "%.2f" % value
    text = text.rstrip("0").rstrip(".")
    return text if text not in ("-0", "") else "0"


# -- the manipulator --------------------------------------------------------------------------
class Manipulator:
    """Fusion's 3D Sketch manipulator: three small planes at the anchor; the active one
    filled. Drawn over the design (an annotation), in the sketch's coordinates."""

    def __init__(self, session):
        from pivy import coin

        self.session = session
        self.root = coin.SoAnnotation()
        self.root.setName("SciForgeSketch3DManipulator")
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        self.transform = coin.SoTransform()
        self.root.addChild(self.transform)
        hints = coin.SoShapeHints()
        hints.vertexOrdering = coin.SoShapeHints.UNKNOWN_ORDERING
        self.root.addChild(hints)
        self.parts = {}
        for plane in core.PLANES:
            sep = coin.SoSeparator()
            material = coin.SoMaterial()
            material.diffuseColor.setValue(*COLOURS[plane])
            material.emissiveColor.setValue(*COLOURS[plane])
            style = coin.SoDrawStyle()
            style.lineWidth = 2.0
            coords = coin.SoCoordinate3()
            lines = coin.SoLineSet()
            face_sep = coin.SoSeparator()
            face_material = coin.SoMaterial()
            face_material.diffuseColor.setValue(*COLOURS[plane])
            face_material.emissiveColor.setValue(*COLOURS[plane])
            face_material.transparency.setValue(0.55)
            faces = coin.SoFaceSet()
            face_sep.addChild(face_material)
            face_sep.addChild(faces)
            for node in (material, style, coords, lines, face_sep):
                sep.addChild(node)
            self.root.addChild(sep)
            self.parts[plane] = (coords, lines, faces)
        self.attached = False
        self.corners = {}

    def show(self, anchor, active):
        v = View3D(self.session)
        self.transform.translation.setValue(*v.place.Base)
        self.transform.rotation.setValue(*v.place.Rotation.Q)
        size = MANIPULATOR_PX * v.mm_per_px(anchor)
        self.corners = core.squares(anchor, size)
        for plane, pts in self.corners.items():
            coords, lines, faces = self.parts[plane]
            coords.point.setNum(0)
            coords.point.setValues(0, 5, pts + pts[:1])
            lines.numVertices.setNum(0)
            lines.numVertices.setValues(0, 1, [5])
            faces.numVertices.setNum(0)
            if plane == active:
                faces.numVertices.setValues(0, 1, [4])
        if not self.attached:
            self.session.view.getSceneGraph().addChild(self.root)
            self.attached = True

    def plane_at(self, pos):
        """The manipulator plane under widget pixel `pos`, or None."""
        if not self.corners:
            return None
        v = View3D(self.session)
        for plane in core.PLANES:
            poly = [v.screen(p) for p in self.corners[plane]]
            if core.point_in_polygon(pos.x(), pos.y(), poly):
                return plane
        return None

    def remove(self):
        try:
            if self.attached:
                self.session.view.getSceneGraph().removeChild(self.root)
        except Exception:
            pass
        self.attached = False


# -- the 3D tools ---------------------------------------------------------------------------
class Snap3D:
    """Where a 3D point goes: point (sketch x, y, z), tie (a sketch point: "v:id:pos"),
    on (what it sits on, for the hint: "point", "corner", "edge", "plane"), vertex (the
    sketch vertex (geo, pos) it sits on, the origin and projected points too, or None)."""

    def __init__(self, point, tie="", on="plane", free=False, vertex=None):
        self.point = tuple(point)
        self.tie = tie
        self.on = on
        self.free = free
        self.vertex = vertex
        self.raw = (point[0], point[1])
        self.key = None

    def __repr__(self):
        return "Snap3D(%r, %s)" % (self.point, self.on)


class Line3D(draw.DrawTool):
    """Lines joined end to end whose points may leave the sketch plane."""

    title = "3D Line"
    command = "SciForge_SketchLine"

    def __init__(self, session):
        super().__init__(session)
        self.chain = []  # [(point, tie)] of the chain being drawn
        self.manipulator = Manipulator(session)
        self.made = []  # (object, edge number) of the curves made (tests)
        self.flat = []  # geometry numbers of the sketch lines made on its plane (tests)

    # -- life cycle ---------------------------------------------------------------------
    def start(self):
        super().start()
        self._show_manipulator()

    def stop(self):
        try:
            self.manipulator.remove()
        except Exception:
            pass
        super().stop()

    def prompt(self):
        plane = LABELS[layer(self.session).plane]
        if not self.chain:
            return (
                "click the start point (on the %s, or a corner); the manipulator's planes "
                "change the plane." % plane
            )
        return "click the next point (on the %s); Enter or Esc ends." % plane

    def steps(self):
        return 2

    def fields(self):
        return []

    def anchor(self):
        return self.chain[-1][0] if self.chain else (0.0, 0.0, 0.0)

    def _show_manipulator(self):
        try:
            self.manipulator.show(self.anchor(), layer(self.session).plane)
        except Exception as exc:
            warn("3D Sketch: %s" % exc)

    # -- where the pointer is ------------------------------------------------------------
    def _view(self, obj, event):
        return View3D(self.session)

    def snap_for(self, view, event):
        ctrl = bool(event.modifiers() & QtCore.Qt.ControlModifier)
        return self.snap3d(view, event.position(), ctrl)

    def snap3d(self, v, pos, ctrl=False):
        plane = layer(self.session).plane
        anchor = self.anchor()
        origin, direction = v.ray(pos)
        hit = core.ray_plane(origin, direction, anchor, plane)
        if ctrl:
            return Snap3D(hit if hit is not None else anchor, free=True)
        # points drawn in 3D, the sketch's own points, then corners and edges of the design
        found = self._near_point(v, pos)
        if found is not None:
            return found
        found = self._on_design(v, pos)
        if found is not None:
            return found
        if hit is None:
            return Snap3D(anchor)
        from .sketch_infer import _grid_size

        return Snap3D(core.grid_snap(hit, anchor, plane, _grid_size(self.session)))

    def _near_point(self, v, pos):
        best = None
        candidates = []
        obj = sketch3d.curves_of(self.sketch)
        if obj is not None:
            candidates += [(p, "", None) for p in sketch3d.resolved_points(obj, self.sketch)]
        candidates += [(p, "", None) for p, _t in self.chain]
        geometry = self.geometry()
        for key, (x, y) in geometry.verts:
            tie = sketch3d.ref_of(self.sketch, key[0], key[1]) if key[0] >= 0 else ""
            candidates.append(((x, y, 0.0), tie, key))
        pick = draw.pick_pixels()
        for p, tie, key in candidates:
            s = v.screen(p)
            d = math.hypot(s[0] - pos.x(), s[1] - pos.y())
            if d <= pick and (best is None or d < best[0]):
                best = (d, p, tie, key)
        if best is None:
            return None
        return Snap3D(best[1], best[2], "point", vertex=best[3])

    def _on_design(self, v, pos):
        """A corner (or an edge) of a body under the pointer: the point lands on it."""
        try:
            info = v.view.getObjectInfo(v.coin(pos))
        except Exception:
            info = None
        if not info:
            return None
        doc = self.sketch.Document
        name = info.get("Object", "")
        if name == self.sketch.Name:
            return None
        found = doc.getObject(name)
        curves = sketch3d.curves_of(self.sketch)
        if found is None or (curves is not None and found is curves):
            return None
        component = str(info.get("Component", ""))
        if not component.startswith(("Vertex", "Edge")):
            return None
        world = App.Vector(info["x"], info["y"], info["z"])
        on = "edge"
        if component.startswith("Vertex"):
            try:
                parent = info.get("ParentObject")
                sub = info.get("SubName", "")
                shape = parent.getSubObject(sub) if parent is not None else None
                if shape is None or shape.isNull():
                    shape = found.Shape.getElement(component)
                world = shape.Vertexes[0].Point
                on = "corner"
            except Exception:
                pass
        return Snap3D(_tuple(v.inverse.multVec(world)), "", on)

    # -- the mouse ----------------------------------------------------------------------------
    def pressed(self, snap, view):
        plane = self.manipulator.plane_at(self.press_pos) if self.press_pos is not None else None
        self._plane_press = plane

    def released(self, press_snap, snap, moved):
        plane = getattr(self, "_plane_press", None)
        if plane is not None:
            layer(self.session).plane = plane
            log("3D Sketch: drawing on the %s" % LABELS[plane])
            self._show_manipulator()
            self._tell()
            return
        self.place(press_snap)

    def moved(self, snap):
        guides = []
        curves = []
        points = [snap.point]
        if self.chain:
            curves.append([self.chain[-1][0], snap.point])
        if snap.on != "plane" or snap.free:
            guides = []
        self.preview.show(curves=curves, guides=guides, points=points)
        self._show_manipulator()

    def place(self, snap):
        """A click: the chain's next point."""
        point, tie = snap.point, snap.tie
        if not self.chain:
            self.chain = [(point, tie)]
            self._after_point()
            return
        last, last_tie = self.chain[-1]
        if core.length(core.sub(point, last)) <= 1e-9:
            return  # the same point again
        flat = core.on_sketch_plane([last, point])
        doc = self.doc
        doc.openTransaction(self.title)
        try:
            if flat:
                geo = self._flat_line(last, point)
                # the 3D curves that start or end here follow the line's ends
                last_tie = last_tie or sketch3d.ref_of(self.sketch, geo, 1)
                tie = sketch3d.ref_of(self.sketch, geo, 2)
                sketch3d.tie_point(self.sketch, last, last_tie)
                self.chain[-1] = (last, last_tie)
            else:
                made = sketch3d.add_line(self.sketch, last, point, last_tie, tie)
        except Exception as exc:
            doc.abortTransaction()
            warn("3D Line: %s" % exc)
            self._geometry = None
            return
        doc.commitTransaction()
        self._geometry = None  # the sketch's points changed
        if flat:
            self.flat.append(geo)
        else:
            self.made.append(made)
        first = self.chain[0][0]
        self.chain.append((point, tie))
        if len(self.chain) > 2 and core.length(core.sub(point, first)) <= 1e-9:
            self.chain = []  # closed: the next click starts a new chain
            log("3D Line: closed")
        self._after_point()

    def _flat_line(self, a, b):
        """A line that lies on the sketch plane: an ordinary sketch line (Fusion: with 3D
        Sketch on, curves stay in the sketch's plane unless they leave it, so they make
        profiles), Coincident with the sketch points at its ends, level or upright when it
        is. Returns its geometry number (inside the caller's transaction)."""
        import Part
        import Sketcher

        sketch = self.sketch
        construction = False
        try:
            from . import sketch_mode

            construction = bool(sketch_mode.construction_mode())
        except Exception:
            pass
        ends = [self._vertex_at(a), self._vertex_at(b)]
        segment = Part.LineSegment(App.Vector(a[0], a[1], 0.0), App.Vector(b[0], b[1], 0.0))
        geo = sketch.addGeometry(segment, construction)
        ties = [
            Sketcher.Constraint("Coincident", geo, pos, key[0], key[1])
            for pos, key in ((1, ends[0]), (2, ends[1]))
            if key is not None
        ]
        if abs(a[1] - b[1]) <= 1e-9:
            ties.append(Sketcher.Constraint("Horizontal", geo))
        elif abs(a[0] - b[0]) <= 1e-9:
            ties.append(Sketcher.Constraint("Vertical", geo))
        self._add_checked(ties)
        sketch.solve()
        log("3D Line: on the sketch plane, a sketch line (Edge%d)" % (geo + 1))
        return geo

    def _vertex_at(self, p, tol=1e-6):
        """The sketch vertex (geo, pos) at sketch point p (the origin too), or None."""
        for key, (x, y) in draw.Geometry(self.sketch).verts:
            if abs(x - p[0]) <= tol and abs(y - p[1]) <= tol:
                return key
        return None

    def _after_point(self):
        self.preview.clear()
        self._show_manipulator()
        self._tell()

    def enter_without_values(self):
        return False  # the sketch's Enter completes the tool

    def undone(self):
        super().undone()
        self.chain = []
        self._show_manipulator()

    def state(self):
        out = super().state()
        out["chain"] = list(self.chain)
        out["plane"] = layer(self.session).plane
        return out


class Spline3D(Line3D):
    """A fit-point spline whose points may leave the sketch plane: click the points, Enter
    (or OK) makes it, Esc drops it."""

    title = "3D Spline"
    command = "SciForge_SketchFitSpline"

    def prompt(self):
        plane = LABELS[layer(self.session).plane]
        if len(self.chain) < 2:
            return "click the spline's points (on the %s, or corners); Enter makes it." % plane
        return "click more points, Enter to make the spline, Esc to drop it."

    def place(self, snap):
        point = snap.point
        if self.chain and core.length(core.sub(point, self.chain[-1][0])) <= 1e-9:
            return
        self.chain.append((point, snap.tie))
        self._after_point()
        self._draw_spline()

    def moved(self, snap):
        self._draw_spline(snap.point)
        self._show_manipulator()

    def _draw_spline(self, pointer=None):
        pts = [p for p, _t in self.chain] + ([pointer] if pointer is not None else [])
        curve = _spline_points(pts)
        self.preview.show(curves=[curve] if curve else [], points=pts)

    def _after_point(self):
        self._show_manipulator()
        self._tell()

    def on_finish(self):
        """Enter / OK: the spline is made (one undo step)."""
        if len(self.chain) < 2:
            return
        doc = self.doc
        doc.openTransaction(self.title)
        try:
            made = sketch3d.add_spline(
                self.sketch, [p for p, _t in self.chain], [t for _p, t in self.chain]
            )
        except Exception as exc:
            doc.abortTransaction()
            warn("3D Spline: %s" % exc)
            return
        doc.commitTransaction()
        self.made.append(made)
        self.chain = []


def _spline_points(pts, n=48):
    """A polyline along the spline through the points (the preview)."""
    if len(pts) < 2:
        return []
    try:
        import Part

        curve = Part.BSplineCurve()
        curve.interpolate([_vec(p) for p in pts])
        return [_tuple(p) for p in curve.discretize(n)]
    except Exception:
        return [tuple(p) for p in pts]


# -- the commands ---------------------------------------------------------------------------
def run_line(session):
    """L with 3D Sketch on."""
    return draw.run(Line3D)


def run_spline(session):
    return draw.run(Spline3D)


class FitSplineCommand:
    """SKETCH > CREATE > Spline > Fit Point Spline: FreeCAD's fit-point spline, or the 3D
    spline while 3D Sketch is on."""

    def GetResources(self):
        from . import ui_icon_path

        return {
            "MenuText": "Fit Point Spline",
            "ToolTip": "A smooth curve through the points you click (in 3D while 3D Sketch "
            "is on in the palette); Enter makes it",
            "Pixmap": ui_icon_path("sk_spline"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            from . import recent, sketch_mode

            session = sketch_mode.current()
            if session is not None and is_on(session):
                run_spline(session)
                return
            # FreeCAD's own tool: the sketch's spline handling knows it by its name
            recent.record("Sketcher_CreateBSplineByInterpolation", "Fit Point Spline")
            Gui.runCommand("Sketcher_CreateBSplineByInterpolation")
        except Exception as exc:
            warn("Fit Point Spline failed: %s" % exc)


COMMANDS = {"SciForge_SketchFitSpline": FitSplineCommand}
