# SPDX-License-Identifier: LGPL-2.1-or-later
"""3D-view pieces of the SURFACE dialogs (surface_ui.py):

- ShapeOverlay: picked curves (thick) and faces (see-through) drawn over the design, as
  Fusion highlights what a command picked. Picture only: clicks go through it.
- CellPicker: the cells of Trim and Boundary Fill drawn over the design; the cell under the
  mouse lights up and a click on it calls back (Fusion's cells are picked by clicking them).
  The cells are found by casting the mouse ray at their triangles, so a cell shows and can
  be clicked even where nothing of the design is drawn (a piece Trim removes).

Mouse events come through FreeCAD's view.addEventCallback (safe; feature guide rule 1),
work is deferred with Qt timers (rule 2), and no FreeCAD-owned Coin node is kept.
"""

import time

import FreeCAD as App

from . import profile_pick, warn
from .compat import QtCore

BLUE = (0.12, 0.53, 0.90)
LIGHT = (0.55, 0.80, 1.0)
RED = (0.90, 0.25, 0.22)
GREY = (0.70, 0.74, 0.80)
GREEN = (0.20, 0.75, 0.35)


def tessellate(shape, fine=0.004):
    """(points, triangles as index triples) of a shape's faces."""
    try:
        size = max(shape.BoundBox.DiagonalLength, 1.0)
        points, facets = shape.tessellate(size * fine)
        return [App.Vector(p) for p in points], [tuple(f) for f in facets]
    except Exception:
        return [], []


def polyline(edge, count=None):
    try:
        if count is None:
            count = 2 if edge.Curve.TypeId in ("Part::GeomLine", "Part::GeomLineSegment") else 48
        return list(edge.discretize(count))
    except Exception:
        return []


def _material(coin, color, transparency):
    m = coin.SoMaterial()
    m.diffuseColor.setValue(*color)
    m.emissiveColor.setValue(*[c * 0.45 for c in color])
    m.transparency.setValue(transparency)
    return m


def _faces_node(coin, points, triangles):
    sep = coin.SoSeparator()
    hints = coin.SoShapeHints()
    hints.vertexOrdering = coin.SoShapeHints.UNKNOWN_ORDERING  # both sides lit
    sep.addChild(hints)
    coords = coin.SoCoordinate3()
    coords.point.setValues(0, len(points), [(p.x, p.y, p.z) for p in points])
    sep.addChild(coords)
    faces = coin.SoIndexedFaceSet()
    index = []
    for a, b, c in triangles:
        index.extend([a, b, c, -1])
    faces.coordIndex.setValues(0, len(index), index)
    sep.addChild(faces)
    return sep


def _lines_node(coin, polylines, width, dashed=False):
    sep = coin.SoSeparator()
    style = coin.SoDrawStyle()
    style.lineWidth.setValue(width)
    if dashed:
        style.linePattern.setValue(0xF0F0)
    sep.addChild(style)
    for pts in polylines:
        if len(pts) < 2:
            continue
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, len(pts), [(p.x, p.y, p.z) for p in pts])
        sep.addChild(coords)
        line = coin.SoLineSet()
        line.numVertices.setValue(len(pts))
        sep.addChild(line)
    return sep


class ShapeOverlay:
    """Named groups of curves and faces drawn over the design (see the module text)."""

    def __init__(self, view, on_top=False):
        from pivy import coin

        self.coin = coin
        self.view = view
        self.root = coin.SoAnnotation() if on_top else coin.SoSeparator()
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        offset = coin.SoPolygonOffset()
        offset.factor.setValue(-1.0)
        offset.units.setValue(-1.0)
        self.root.addChild(offset)
        self.groups = {}
        view.getSceneGraph().addChild(self.root)

    def show(self, name, shapes, color=BLUE, transparency=0.55, width=4.0, dashed=False):
        """Draw `shapes` (faces see-through, edges and wires as thick lines) as group
        `name`, replacing what was drawn under that name."""
        self.clear(name)
        coin = self.coin
        sep = coin.SoSeparator()
        sep.addChild(_material(coin, color, transparency))
        lines = []
        for shape in shapes or []:
            if shape is None or shape.isNull():
                continue
            if shape.Faces:
                points, triangles = tessellate(shape)
                if triangles:
                    sep.addChild(_faces_node(coin, points, triangles))
            else:
                for edge in shape.Edges:
                    lines.append(polyline(edge))
        if lines:
            line_sep = coin.SoSeparator()
            line_sep.addChild(_material(coin, color, 0.0))
            line_sep.addChild(_lines_node(coin, lines, width, dashed))
            sep.addChild(line_sep)
        self.root.addChild(sep)
        self.groups[name] = sep

    def clear(self, name):
        sep = self.groups.pop(name, None)
        if sep is not None:
            try:
                self.root.removeChild(sep)
            except Exception:
                pass

    def remove(self):
        self.groups = {}
        try:
            self.view.getSceneGraph().removeChild(self.root)
        except Exception:
            pass


# -- casting the mouse ray at triangles ---------------------------------------------------------
def ray_triangle(origin, direction, a, b, c):
    """Distance along the ray to triangle abc (Moeller-Trumbore), or None."""
    e1 = b - a
    e2 = c - a
    p = direction.cross(e2)
    det = e1.dot(p)
    if abs(det) < 1e-12:
        return None
    inv = 1.0 / det
    s = origin - a
    u = s.dot(p) * inv
    if u < -1e-9 or u > 1.0 + 1e-9:
        return None
    q = s.cross(e1)
    v = direction.dot(q) * inv
    if v < -1e-9 or u + v > 1.0 + 1e-9:
        return None
    t = e2.dot(q) * inv
    return t if t > -1e-9 else None


def nearest_hit(meshes, origin, direction):
    """(index, distance) of the nearest mesh the ray meets: meshes = [(points, triangles)]."""
    best = None
    for index, (points, triangles) in enumerate(meshes):
        for i, j, k in triangles:
            t = ray_triangle(origin, direction, points[i], points[j], points[k])
            if t is not None and (best is None or t < best[1]):
                best = (index, t)
    return best


class CellPicker:
    """The cells of Trim / Boundary Fill, drawn and clickable (see the module text).

    set_cells(shapes, states): states per cell, one of "idle" (not drawn but clickable),
    "shown" (see-through grey), "chosen" (blue) or "removed" (red); the hovered cell is
    drawn light blue. on_click(index) is called (from a Qt timer) for a click on a cell."""

    def __init__(self, view, on_click, blocked=None):
        self.view = view
        self.on_click = on_click
        self.blocked = blocked
        self.overlay = ShapeOverlay(view)
        self.meshes = []
        self.shapes = []
        self.states = []
        self.hovered = None
        self.last_click = 0.0
        self._last_move = 0.0
        self._pending_move = None
        self._timer = QtCore.QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._hover_now)
        self.callbacks = [
            ("SoMouseButtonEvent", view.addEventCallback("SoMouseButtonEvent", self._button)),
            ("SoLocation2Event", view.addEventCallback("SoLocation2Event", self._moved)),
        ]

    def set_cells(self, shapes, states):
        self.shapes = list(shapes)
        self.states = list(states)
        self.meshes = [tessellate(s) for s in self.shapes]
        if self.hovered is not None and self.hovered >= len(self.shapes):
            self.hovered = None
        self.paint()

    def set_states(self, states):
        self.states = list(states)
        self.paint()

    def paint(self):
        groups = {"chosen": [], "removed": [], "shown": []}
        for i, shape in enumerate(self.shapes):
            state = self.states[i] if i < len(self.states) else "idle"
            if i == self.hovered:
                continue
            if state in groups:
                groups[state].append(shape)
        self.overlay.show("chosen", groups["chosen"], BLUE, 0.35)
        self.overlay.show("removed", groups["removed"], RED, 0.45)
        self.overlay.show("shown", groups["shown"], GREY, 0.8)
        hover = [self.shapes[self.hovered]] if self.hovered is not None else []
        self.overlay.show("hover", hover, LIGHT, 0.3)

    def cell_at(self, position):
        if not self.meshes:
            return None
        try:
            origin, direction = profile_pick.mouse_ray(self.view, tuple(position))
            # start far behind the eye: an orthographic camera's point can sit in front of
            # what it shows
            origin = origin - direction * 1e5
        except Exception:
            return None
        hit = nearest_hit(self.meshes, origin, direction)
        return hit[0] if hit is not None else None

    def _button(self, info):
        try:
            if info.get("Button") != "BUTTON1":
                return
            position = info["Position"]
            # The press picks, as the origin planes and axes of the other SciForge dialogs
            # do: FreeCAD does not always pass the release on (drag_guard.py).
            if info.get("State") != "DOWN":
                return
            try:
                from . import handles3d

                if handles3d.dragging():
                    return  # a handle took this press
            except Exception:
                pass
            if self.blocked is not None and self.blocked(position):
                return
            index = self.cell_at(position)
            if index is not None:
                self.last_click = time.time()
                QtCore.QTimer.singleShot(0, lambda: self._clicked(index))
        except Exception as exc:
            warn("cell pick: %s" % exc)

    def _clicked(self, index):
        try:
            self.on_click(index)
        except Exception as exc:
            warn("cell pick: %s" % exc)

    def clicked_recently(self, seconds=0.6):
        return time.time() - self.last_click < seconds

    def _moved(self, info):
        try:
            self._pending_move = info["Position"]
            if not self._timer.isActive():
                self._timer.start()
        except Exception:
            pass

    def _hover_now(self):
        try:
            position = self._pending_move
            if position is None:
                return
            if self.blocked is not None and self.blocked(position):
                index = None
            else:
                index = self.cell_at(position)
            if index != self.hovered:
                self.hovered = index
                self.paint()
        except Exception as exc:
            warn("cell hover: %s" % exc)

    def remove(self):
        try:
            self._timer.stop()
        except Exception:
            pass
        for kind, callback in self.callbacks:
            try:
                self.view.removeEventCallback(kind, callback)
            except Exception:
                pass
        self.callbacks = []
        self.overlay.remove()
        self.meshes = []
