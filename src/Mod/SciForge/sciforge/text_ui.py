# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's sketch Text: the Text command and its dialog, and texts in the open sketch.

SKETCH > CREATE > Text opens the TEXT panel at the top of the sketch panel (Fusion's Text
dialog). Type Text: click the frame's first corner, then the opposite one; the letters
appear inside it as you type. Type Text On Path: click a curve of the sketch. Height,
Angle (also the round handle next to the frame; click one of the frame's dots to turn
about it), Font (the fonts of this computer), Bold / Italic / Underline, alignment,
Character Spacing, Flip, Placement Above / Below and Fit to Path (on a path) change the
preview at once; OK makes the text (one undo step), Cancel or Esc drops it.

In the open sketch a text is drawn in the sketch's colours and its letters are shaded
like a closed area. A click on it picks the whole text as a profile (Ctrl / Shift add
more; E and Q extrude what is picked, Fusion's way); press on it and drag to move it
(its frame lines move, any dimension on them holds it); double-click it to change it;
Del deletes it; the right-click menu has Edit Text and Explode Text. After Finish
Sketch the text shows with the sketch and a click selects the whole text.

How a text is stored: text.py. Mouse and keys come from Qt event filters on the 3D view
installed after the sketch session's own (sketch_mode), so they see the events first;
work that changes the document runs from Qt timers or in plain Qt events, never inside
FreeCAD's Coin callbacks.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, log, text, ui_icon_path, warn
from . import text_core as core
from .compat import QtCore, QtWidgets

PREFS = "User parameter:BaseApp/Preferences/Mod/SciForge/SketchText"
LINE = (0.36, 0.70, 1.0)  # the sketch's blue for curves that can still move
LINE_FIXED = (0.94, 0.94, 0.94)  # fully constrained (white on the dark background)
FILL = (0.45, 0.77, 1.0)  # the sketch's profile shade
FILL_TRANSPARENCY = 0.72
PREVIEW = (0.98, 0.78, 0.30)  # the text being placed or edited
HANDLE = (0.30, 0.62, 0.95)  # Fusion's manipulator blue
HANDLE_ACTIVE = (0.55, 0.80, 1.0)
CLICK_SLOP = 4  # pixels: a press and a release this close are a click
NEAR_PX = 6  # pixels: this close to a letter's outline counts as on the text
DOT_PX = 9  # pixels: a click this close to a frame dot picks it
HANDLE_PX = 12
HANDLE_OFFSET_PX = 28  # the turning handle sits this far out from the frame's corner
Z_LINES = 0.004  # mm toward the viewer: letters over the face the sketch lies on

_state = {
    "on": False,
    "layer": None,
    "gui_observer": None,
    "app_observer": None,
    "selection_observer": None,
}


# -- small helpers ----------------------------------------------------------------------------
def _safe(fn):
    """For Qt slots and timers: an error is reported, never let out into Qt's event loop."""
    import functools

    @functools.wraps(fn)
    def run(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            warn("sketch text (%s): %s" % (fn.__name__, exc))
            return None

    return run


def _param():
    return App.ParamGet(PREFS)


def remembered_spec():
    """A new text starts like the last one made (font, height, style, alignment)."""
    spec = text.default_spec()
    try:
        p = _param()
        spec["font"] = p.GetString("Font", "") or ""
        spec["height"] = p.GetFloat("Height", text.DEFAULT_HEIGHT) or text.DEFAULT_HEIGHT
        spec["bold"] = p.GetBool("Bold", False)
        spec["italic"] = p.GetBool("Italic", False)
        spec["underline"] = p.GetBool("Underline", False)
        h_align = p.GetString("HAlign", "left")
        v_align = p.GetString("VAlign", "top")
        spec["h_align"] = h_align if h_align in core.H_ALIGNS else "left"
        spec["v_align"] = v_align if v_align in core.V_ALIGNS else "top"
        spec["spacing"] = p.GetFloat("Spacing", 0.0)
    except Exception:
        pass
    if not spec["font"]:
        try:
            spec["font"] = text.default_family() or ""
        except Exception as exc:
            warn("fonts: %s" % exc)
    return spec


def remember(spec):
    try:
        p = _param()
        p.SetString("Font", spec["font"] or "")
        p.SetFloat("Height", float(spec["height"]))
        p.SetBool("Bold", bool(spec["bold"]))
        p.SetBool("Italic", bool(spec["italic"]))
        p.SetBool("Underline", bool(spec["underline"]))
        p.SetString("HAlign", spec["h_align"])
        p.SetString("VAlign", spec["v_align"])
        p.SetFloat("Spacing", float(spec["spacing"]))
    except Exception:
        pass


def _session():
    try:
        from . import sketch_mode

        return sketch_mode.current()
    except Exception:
        return None


def _alive(obj):
    try:
        return obj is not None and obj.Document.getObject(obj.Name) is obj
    except Exception:
        return False


def _sketch_point(session, pos):
    """Sketch (x, y) under widget pixel `pos` of the open sketch, or None."""
    try:
        return session.areas._sketch_point(pos)
    except Exception:
        return None


def _mm_per_px(session, pos):
    a = _sketch_point(session, pos)
    b = _sketch_point(session, QtCore.QPoint(pos.x() + 10, pos.y()))
    if a is None or b is None:
        return 0.1
    return max(math.hypot(b[0] - a[0], b[1] - a[1]) / 10.0, 1e-9)


def _screen(session, xy):
    """Widget pixel of sketch point (x, y) (QPointF)."""
    placement = session.sketch.getGlobalPlacement()
    world = placement.multVec(App.Vector(xy[0], xy[1], 0))
    x, y = session.view.getPointOnViewport(world)
    ratio = session.gl.devicePixelRatioF()
    return QtCore.QPointF(x / ratio, session.gl.height() - y / ratio)


def _dist(a, b):
    return math.hypot(a.x() - b.x(), a.y() - b.y())


# -- a text in the open sketch: drawing data ------------------------------------------------
class Shown:
    """One text as the open sketch shows it: its plan (or None and why) and the triangles
    a click is tested against."""

    __slots__ = ("obj", "plan", "points", "triangles", "outlines", "region", "reason", "fixed")

    def __init__(self, obj, plan=None, reason=""):
        from . import sketch_areas_core

        self.obj = obj
        self.plan = plan
        self.reason = reason
        self.fixed = False
        if plan is not None:
            self.points, self.triangles = plan.triangles()
            self.outlines = plan.outlines()
        else:
            self.points, self.triangles, self.outlines = [], [], []
        self.region = sketch_areas_core.Region(self.points, self.triangles)


def plan_of(obj, sketch, spec=None):
    """The Plan of a text as it is now in the open sketch (frame lines as they are)."""
    spec = spec if spec is not None else text.spec_of(obj)
    lookup = text.parameter_lookup(obj.Document if obj is not None else sketch.Document)
    return text.plan(spec, sketch, lookup=lookup)


# -- the layer: texts in the open sketch -------------------------------------------------------
class TextLayer(QtCore.QObject):
    """The texts of the open sketch: drawn, picked (through the sketch's AreaPicker),
    dragged, double-clicked, deleted. One per sketch session."""

    def __init__(self, session):
        super().__init__()
        from pivy import coin

        self.coin = coin
        self.session = session
        self.sketch = session.sketch
        self.closed = False
        self.shown = {}  # name -> Shown
        self.hidden = set()  # names drawn by the dialog instead
        self.dialog = None
        self._press = None  # (pos, modifiers, text name) of a left press on a text
        self._drag = None  # {"name", "last": (x, y), "moved": bool}
        self._resize = None  # {"name", "which", "frame", "moved"}: a frame corner dragged
        self._last_draw = None
        self.root = coin.SoSeparator()
        self.root.setName("SciForgeSketchTexts")
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        self.transform = coin.SoTransform()
        self.root.addChild(self.transform)
        offset = coin.SoPolygonOffset()
        offset.factor = -1.5
        offset.units = -1.5
        self.root.addChild(offset)
        hints = coin.SoShapeHints()
        hints.vertexOrdering = coin.SoShapeHints.UNKNOWN_ORDERING
        self.root.addChild(hints)
        self.fill = self._faces(FILL, FILL_TRANSPARENCY)
        self.lines = self._lines(LINE, 1.6)
        self.fixed_lines = self._lines(LINE_FIXED, 1.6)
        self.preview_fill = self._faces(PREVIEW, 0.65)
        self.preview_lines = self._lines(PREVIEW, 2.0)
        self.frame_lines = self._lines(PREVIEW, 1.2, pattern=0xF0F0)
        self.dots = self._dots(HANDLE)
        self.pivot_dot = self._dots(HANDLE_ACTIVE, size=9)
        self.handle_lines = self._lines(HANDLE, 2.5, annotation=True)
        self.attached = False
        self._timer = QtCore.QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(60)
        self._timer.timeout.connect(self._refresh_now)
        self._watching = []
        self._attach(True)
        for widget in (session.gl, session.viewer):
            if widget is not None:
                widget.installEventFilter(self)  # after the session's own: runs first
                self._watching.append(widget)
        self.refresh(now=True)

    # -- Coin nodes -----------------------------------------------------------------------
    def _material(self, sep, color, transparency=0.0):
        material = self.coin.SoMaterial()
        material.diffuseColor.setValue(*color)
        material.emissiveColor.setValue(*[c * 0.6 for c in color])
        material.transparency.setValue(transparency)
        sep.addChild(material)
        return material

    def _faces(self, color, transparency):
        coin = self.coin
        sep = coin.SoSeparator()
        self._material(sep, color, transparency)
        coords = coin.SoCoordinate3()
        faces = coin.SoIndexedFaceSet()
        sep.addChild(coords)
        sep.addChild(faces)
        self.root.addChild(sep)
        return coords, faces

    def _lines(self, color, width, pattern=None, annotation=False):
        coin = self.coin
        sep = coin.SoAnnotation() if annotation else coin.SoSeparator()
        style = coin.SoDrawStyle()
        style.lineWidth = width
        if pattern:
            style.linePattern = pattern
        sep.addChild(style)
        material = self._material(sep, color)
        coords = coin.SoCoordinate3()
        lines = coin.SoIndexedLineSet()
        sep.addChild(coords)
        sep.addChild(lines)
        self.root.addChild(sep)
        return coords, lines, material

    def _dots(self, color, size=7):
        coin = self.coin
        sep = coin.SoAnnotation()
        self._material(sep, color)
        coords = coin.SoCoordinate3()
        markers = coin.SoMarkerSet()
        markers.markerIndex = (
            coin.SoMarkerSet.CIRCLE_FILLED_9_9
            if size >= 9
            else (coin.SoMarkerSet.CIRCLE_FILLED_7_7)
        )
        sep.addChild(coords)
        sep.addChild(markers)
        self.root.addChild(sep)
        return coords, markers

    @staticmethod
    def _set_faces(node, points, triangles, z=0.0):
        coords, faces = node
        coords.point.setNum(0)
        faces.coordIndex.setNum(0)
        if points and triangles:
            coords.point.setValues(0, len(points), [(x, y, z) for x, y in points])
            index = []
            for a, b, c in triangles:
                index += [a, b, c, -1]
            faces.coordIndex.setValues(0, len(index), index)

    @staticmethod
    def _set_lines(node, polylines, z=Z_LINES):
        coords, lines = node[0], node[1]
        coords.point.setNum(0)
        lines.coordIndex.setNum(0)
        points, index = [], []
        for line in polylines:
            if len(line) < 2:
                continue
            base = len(points)
            points += [(x, y, z) for x, y in line]
            index += list(range(base, base + len(line))) + [-1]
        if points:
            coords.point.setValues(0, len(points), points)
            lines.coordIndex.setValues(0, len(index), index)

    @staticmethod
    def _set_dots(node, points, z=Z_LINES * 2):
        coords, markers = node
        coords.point.setNum(0)
        if points:
            coords.point.setValues(0, len(points), [(x, y, z) for x, y in points])
        markers.numPoints = len(points)

    def _attach(self, on):
        try:
            graph = self.session.view.getSceneGraph()
            if on and not self.attached:
                graph.addChild(self.root)
                self.attached = True
            elif not on and self.attached:
                graph.removeChild(self.root)
                self.attached = False
        except Exception as exc:
            warn("sketch text: %s" % exc)

    # -- what is shown -------------------------------------------------------------------
    def texts(self):
        if self.closed or not _alive(self.sketch):
            return []
        return text.texts_of(self.sketch)

    def refresh(self, now=False):
        if self.closed:
            return
        if now:
            self._refresh_now()
        else:
            self._timer.start()

    def _refresh_now(self):
        if self.closed:
            return
        try:
            placement = self.sketch.getGlobalPlacement()
            self.transform.translation.setValue(*placement.Base)
            self.transform.rotation.setValue(*placement.Rotation.Q)
            free = self._free_geometry()
            shown = {}
            for obj in self.texts():
                if obj.Name in self.hidden:
                    continue
                try:
                    item = Shown(obj, plan_of(obj, self.sketch))
                except Exception as exc:
                    item = Shown(obj, None, str(exc))
                item.fixed = self._is_fixed(obj, free)
                shown[obj.Name] = item
            self.shown = shown
            self._draw()
            self._hide_objects()
            areas = getattr(self.session, "areas", None)
            if areas is not None and not self.session.closed:
                areas.refresh(self.session.shading.shaded)  # the texts are pickable areas
        except Exception as exc:
            warn("sketch text: %s" % exc)

    def _free_geometry(self):
        """Geometry indices the solver may still move (FreeCAD 1.x), or None."""
        try:
            return {g for g, _pos in self.sketch.getGeometryWithDependentParameters()}
        except Exception:
            return None

    def _is_fixed(self, obj, free):
        """Fusion draws a text that cannot move any more like other fully defined curves."""
        if free is None or obj.TextType != "Text":
            return False
        indices = [text.geo_index(self.sketch, gid) for gid in obj.FrameIds]
        return bool(indices) and all(i is not None and i not in free for i in indices)

    def _draw(self):
        fill_points, fill_tris = [], []
        free_lines, fixed_lines = [], []
        for item in self.shown.values():
            base = len(fill_points)
            fill_points += item.points
            fill_tris += [(base + a, base + b, base + c) for a, b, c in item.triangles]
            (fixed_lines if item.fixed else free_lines).extend(item.outlines)
        self._set_faces(self.fill, fill_points, fill_tris)
        self._set_lines(self.lines, free_lines)
        self._set_lines(self.fixed_lines, fixed_lines)

    def _hide_objects(self):
        """The text objects themselves are hidden while their sketch is open (this layer
        draws them as they are now)."""
        for obj in self.texts():
            try:
                vobj = obj.ViewObject
                if vobj is not None and vobj.Visibility:
                    vobj.Visibility = False
            except Exception:
                pass

    def area_entries(self):
        """[(text object, points, triangles)] for the sketch's AreaPicker."""
        return [
            (item.obj, item.points, item.triangles)
            for item in self.shown.values()
            if item.triangles and _alive(item.obj)
        ]

    # -- the dialog's preview -------------------------------------------------------------
    def draw_preview(self, plan=None, frame=None, dots=(), pivot=None, handle=None, path=None):
        self._set_faces(self.preview_fill, *(plan.triangles() if plan else ([], [])))
        self._set_lines(self.preview_lines, plan.outlines() if plan else [])
        frames = []
        if frame is not None:
            corners = core.frame_corners(*frame)
            frames.append(corners + [corners[0]])
        if path:
            frames.append(path)
        self._set_lines(self.frame_lines, frames)
        self._set_dots(self.dots, list(dots))
        self._set_dots(self.pivot_dot, [pivot] if pivot is not None else [])
        self._set_lines(self.handle_lines, handle or [])

    def clear_preview(self):
        self.draw_preview()

    # -- what is under the mouse ----------------------------------------------------------
    def text_at(self, pos):
        """The text object under widget pixel `pos`, or None."""
        point = _sketch_point(self.session, pos)
        if point is None:
            return None
        x, y = point
        tolerance = NEAR_PX * _mm_per_px(self.session, pos)
        best = None
        for item in self.shown.values():
            if not item.triangles:
                continue
            x0, y0, x1, y1 = item.region.box
            if x < x0 - tolerance or x > x1 + tolerance or y < y0 - tolerance or y > y1 + tolerance:
                continue
            if item.region.contains(x, y) or _near_lines(item.outlines, x, y, tolerance):
                if best is None or item.region.area < best.region.area:
                    best = item
        return best.obj if best is not None and _alive(best.obj) else None

    def _usable(self):
        """No drawing tool runs, no value box is open, no command waits for curves."""
        session = self.session
        if session.closed or self.closed:
            return False
        try:
            from . import sketch_areas

            if session.editor is not None or sketch_areas._waiting():
                return False
            gl = session.gl
            return gl is not None and gl.cursor().shape() == QtCore.Qt.ArrowCursor
        except Exception:
            return False

    # -- mouse and keys ---------------------------------------------------------------------
    def eventFilter(self, obj, event):
        try:
            if self.closed or self.session.closed:
                return False
            kind = event.type()
            if kind in (QtCore.QEvent.KeyPress, QtCore.QEvent.ShortcutOverride):
                return self._key(event, kind)
            if obj is not self.session.gl:
                return False
            if self.dialog is not None and self.dialog.mouse(event):
                return True
            if kind == QtCore.QEvent.MouseButtonPress:
                return self._pressed(event)
            if kind == QtCore.QEvent.MouseMove:
                return self._moved(event)
            if kind == QtCore.QEvent.MouseButtonRelease:
                return self._released(event)
            if kind == QtCore.QEvent.MouseButtonDblClick:
                return self._double_clicked(event)
        except Exception as exc:
            warn("sketch text: %s" % exc)
        return False

    def frame_corner_at(self, pos):
        """(text, corner number 0..3, frame) of a text frame's corner under widget pixel
        `pos` (Fusion: drag a corner of the frame to resize it), or None."""
        best = None
        for item in self.shown.values():
            obj = item.obj
            if not _alive(obj) or obj.TextType != "Text":
                continue
            frame = text.read_frame(self.sketch, list(obj.FrameIds))
            if frame is None:
                continue
            for which, xy in enumerate(core.frame_corners(*frame)):
                d = _dist(_screen(self.session, xy), QtCore.QPointF(pos))
                if d <= DOT_PX and (best is None or d < best[0]):
                    best = (d, obj, which, frame)
        return best[1:] if best is not None else None

    def _pressed(self, event):
        self._press = None
        self._drag = None
        self._resize = None
        pos = event.position().toPoint()
        if event.button() == QtCore.Qt.RightButton:
            found = self.text_at(pos) if self._usable() else None
            if found is not None:
                self.pick(found, add=False)  # the right-click menu acts on it
            return False
        if event.button() != QtCore.Qt.LeftButton or not self._usable():
            return False
        corner = self.frame_corner_at(pos)
        if corner is not None:
            obj, which, frame = corner
            self._press = (QtCore.QPoint(pos), event.modifiers(), obj.Name)
            self._resize = {"name": obj.Name, "which": which, "frame": frame, "moved": False}
            return True  # the frame's own drag, not FreeCAD's drag of the point
        found = self.text_at(pos)
        if found is None:
            return False
        self._press = (QtCore.QPoint(pos), event.modifiers(), found.Name)
        return True  # FreeCAD must not start a box selection on the text

    def _moved(self, event):
        if self._press is None:
            return False
        if not event.buttons() & QtCore.Qt.LeftButton:
            if self._resize is not None:
                if QtWidgets.QApplication.mouseButtons() & QtCore.Qt.LeftButton:
                    return True  # (xvfb now and then sends a move without the held button)
                resize, self._resize, self._press = self._resize, None, None
                return self._released_resize(resize)  # the release never came: keep it
            self._press = None
            return False
        pos = event.position().toPoint()
        start, _mods, name = self._press
        if self._resize is not None:
            return self._resize_to(start, pos)
        if self._drag is None:
            if (pos - start).manhattanLength() <= CLICK_SLOP:
                return True
            obj = self.sketch.Document.getObject(name)
            if obj is None or obj.TextType != "Text":
                if obj is not None:
                    commands.tell("A text on a path follows its path: move the path instead.")
                self._press = None
                return True
            point = _sketch_point(self.session, start)
            if point is None:
                return True
            self._drag = {"name": name, "last": point, "moved": False}
            self.sketch.Document.openTransaction("Move Text")
        point = _sketch_point(self.session, pos)
        if point is None:
            return True
        dx = point[0] - self._drag["last"][0]
        dy = point[1] - self._drag["last"][1]
        if abs(dx) + abs(dy) > 1e-9:
            obj = self.sketch.Document.getObject(self._drag["name"])
            if obj is not None and text.move_frame(self.sketch, list(obj.FrameIds), dx, dy):
                self._drag["moved"] = True
            self._drag["last"] = point
            self.refresh(now=True)
        return True

    def _resize_to(self, start, pos):
        """A frame corner follows the pointer: the opposite corner stays, the letters keep
        their height and are laid out again in the new frame (Fusion)."""
        resize = self._resize
        if not resize["moved"]:
            if (pos - start).manhattanLength() <= CLICK_SLOP:
                return True
            resize["moved"] = True
            self.sketch.Document.openTransaction("Resize Text Frame")
        point = _sketch_point(self.session, pos)
        obj = self.sketch.Document.getObject(resize["name"])
        if point is None or obj is None:
            return True
        corner, angle, width, height = resize["frame"]
        new = core.resized_frame(
            corner, angle, width, height, resize["which"], point, minimum=self._min_frame()
        )
        resize["held"] = not text.set_frame(self.sketch, list(obj.FrameIds), *new)
        self.refresh(now=True)
        return True

    def _min_frame(self):
        """The smallest frame side a drag leaves (a few pixels' worth)."""
        try:
            gl = self.session.gl
            centre = QtCore.QPoint(gl.width() // 2, gl.height() // 2)
            return max(4 * _mm_per_px(self.session, centre), 1e-3)
        except Exception:
            return 0.5

    def _released_resize(self, resize):
        doc = self.sketch.Document
        if not resize["moved"]:
            return True
        obj = doc.getObject(resize["name"])
        try:
            if obj is not None:
                _keep_frame_values(obj)
                obj.recompute()
            doc.commitTransaction()
        except Exception as exc:
            doc.abortTransaction()
            warn("resize text frame: %s" % exc)
            return True
        if resize.get("held"):
            commands.tell(
                "The frame's dimensions hold its size: change them (double-click one) to "
                "resize the text frame."
            )
        else:
            log("text frame resized")
        self.refresh()
        return True

    def _released(self, event):
        press, self._press = self._press, None
        drag, self._drag = self._drag, None
        resize, self._resize = self._resize, None
        if press is None or event.button() != QtCore.Qt.LeftButton:
            return False
        if resize is not None:
            return self._released_resize(resize)
        doc = self.sketch.Document
        if drag is not None:
            obj = doc.getObject(drag["name"])
            try:
                if obj is not None:
                    _keep_frame_values(obj)
                    obj.recompute()
                doc.commitTransaction()
            except Exception as exc:
                doc.abortTransaction()
                warn("move text: %s" % exc)
            if drag["moved"]:
                log("text moved")
            self.refresh()
            return True
        # a click: the sketch's area picking takes it (the whole text is one profile)
        pos, modifiers, _name = press
        areas = self.session.areas
        areas.pressed(pos, modifiers)
        areas.released(event.position().toPoint())
        return True

    def _double_clicked(self, event):
        if event.button() != QtCore.Qt.LeftButton or not self._usable():
            return False
        found = self.text_at(event.position().toPoint())
        if found is None:
            return False
        QtCore.QTimer.singleShot(0, lambda: open_dialog(self.session, found))
        return True

    def _key(self, event, kind):
        key = event.key()
        if self.dialog is not None:
            if key == QtCore.Qt.Key_Escape:
                if kind == QtCore.QEvent.KeyPress and not event.isAutoRepeat():
                    QtCore.QTimer.singleShot(0, self.dialog.reject)
                event.accept()
                return True
            if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                if kind == QtCore.QEvent.KeyPress and not event.isAutoRepeat():
                    QtCore.QTimer.singleShot(0, self.dialog.accept)
                event.accept()
                return True
            return False
        if key == QtCore.Qt.Key_Delete and event.modifiers() == QtCore.Qt.NoModifier:
            picked = self.picked()
            if picked and not _sketch_selection(self.sketch):
                if kind == QtCore.QEvent.KeyPress and not event.isAutoRepeat():
                    QtCore.QTimer.singleShot(0, lambda: delete_texts(picked))
                event.accept()
                return True
        return False

    # -- picking ---------------------------------------------------------------------------
    def picked(self):
        """The texts picked in the open sketch (as profiles / selected)."""
        try:
            areas = self.session.areas
            keys = getattr(areas, "text_keys", {})
            found = []
            for index in areas.picked_indices():
                obj = keys.get(index)
                if obj is not None and _alive(obj) and obj not in found:
                    found.append(obj)
            return found
        except Exception:
            return []

    def pick(self, obj, add=False):
        """Pick a text as the sketch's areas are picked (it lights up stronger blue)."""
        try:
            item = self.shown.get(obj.Name)
            if item is None or not item.triangles:
                return
            areas = self.session.areas
            if any(o is obj for o in self.picked()):
                return
            a, b, c = item.triangles[0]
            pts = item.points
            anchor = (
                (pts[a][0] + pts[b][0] + pts[c][0]) / 3.0,
                (pts[a][1] + pts[b][1] + pts[c][1]) / 3.0,
            )
            picks = list(areas.picks) if add else []
            areas._set(picks + [anchor])
        except Exception as exc:
            warn("sketch text: %s" % exc)

    # -- end -------------------------------------------------------------------------------------
    def remove(self):
        if self.closed:
            return
        dialog = self.dialog
        if dialog is not None:
            try:
                dialog.settle()
            except Exception as exc:
                warn("text: %s" % exc)
        self.closed = True
        try:
            self._timer.stop()
        except Exception:
            pass
        for widget in self._watching:
            try:
                widget.removeEventFilter(self)
            except Exception:
                pass
        self._watching = []
        self._attach(False)


def _near_lines(polylines, x, y, tolerance):
    t2 = tolerance * tolerance
    for line in polylines:
        for (ax, ay), (bx, by) in zip(line, line[1:]):
            if min(ax, bx) - tolerance > x or max(ax, bx) + tolerance < x:
                continue
            if min(ay, by) - tolerance > y or max(ay, by) + tolerance < y:
                continue
            dx, dy = bx - ax, by - ay
            length2 = dx * dx + dy * dy
            t = (
                0.0
                if length2 < 1e-18
                else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / length2))
            )
            px, py = ax + dx * t - x, ay + dy * t - y
            if px * px + py * py <= t2:
                return True
    return False


def _sketch_selection(sketch):
    """Curves / points of the sketch selected in FreeCAD's selection (they win Del)."""
    try:
        for sel in Gui.Selection.getSelectionEx():
            if sel.Object is sketch and any(sel.SubElementNames):
                return True
    except Exception:
        pass
    return False


def _keep_frame_values(obj):
    """Store the frame's place on the text (used if its lines are ever deleted)."""
    sketch = obj.Sketch
    if sketch is None or obj.TextType != "Text":
        return
    found = text.read_frame(sketch, list(obj.FrameIds))
    if found is None:
        return
    (cx, cy), angle, width, height = found
    corner = App.Vector(cx, cy, 0)
    if (obj.Corner - corner).Length > 1e-9:
        obj.Corner = corner
    if abs(obj.Angle.Value - angle) > 1e-9:
        obj.Angle = angle
    if abs(obj.FrameWidth.Value - width) > 1e-9:
        obj.FrameWidth = max(width, 0.0)
    if abs(obj.FrameHeight.Value - height) > 1e-9:
        obj.FrameHeight = max(height, 0.0)


def current_layer():
    layer = _state["layer"]
    if layer is not None and (layer.closed or layer.session.closed):
        return None
    return layer


def area_entries(session):
    """For sketch_areas.AreaPicker: [(text object, points, triangles)] of the open
    sketch's texts (the whole text is one area: Fusion picks a text as one profile)."""
    layer = current_layer()
    if layer is None or layer.session is not session:
        return []
    return layer.area_entries()


def picked_texts(session=None):
    layer = current_layer()
    if layer is None or (session is not None and layer.session is not session):
        return []
    return layer.picked()


# -- deleting and exploding -------------------------------------------------------------------
@_safe
def delete_texts(objs):
    objs = [o for o in objs if _alive(o)]
    if not objs:
        return
    doc = objs[0].Document
    users = [u.Label for o in objs for u in text.users(o)]
    doc.openTransaction("Delete Text")
    try:
        for obj in objs:
            text.remove(obj)
    except Exception as exc:
        doc.abortTransaction()
        warn("delete text: %s" % exc)
        return
    doc.commitTransaction()
    layer = current_layer()
    if layer is not None:
        try:
            layer.session.areas.clear()
        except Exception:
            pass
        layer.refresh()
    if users:
        commands.tell(
            "%s used the text; it now has no profile. Ctrl+Z brings the text back."
            % ", ".join(sorted(set(users)))
        )
    log("deleted %d text(s)" % len(objs))


@_safe
def explode_texts(objs):
    objs = [o for o in objs if _alive(o)]
    if not objs:
        commands.tell("Explode Text: pick a text in the sketch first.")
        return
    doc = objs[0].Document
    doc.openTransaction("Explode Text")
    count = 0
    try:
        for obj in objs:
            count += text.explode(obj)
    except Exception as exc:
        doc.abortTransaction()
        commands.tell("The text could not be exploded: %s" % exc)
        return
    doc.commitTransaction()
    layer = current_layer()
    if layer is not None:
        try:
            layer.session.areas.clear()
        except Exception:
            pass
        layer.refresh()
    log("exploded %d text(s) into %d curves" % (len(objs), count))


# -- the Text dialog ------------------------------------------------------------------------------
STYLE = """
#SciForgeTextPanel { background: #3b4453; border: 1px solid #56606f; border-radius: 2px; }
#SciForgeTextPanel QLabel { color: #f5f5f5; }
#SciForgeTextPanel QLabel[role="title"] { color: #f5f5f5; font-weight: bold; padding: 6px 8px;
    background: #2f3643; }
#SciForgeTextPanel QLabel[role="hint"] { color: #8cc4ff; }
#SciForgeTextPanel QLabel[role="error"] { color: #ff8a80; }
#SciForgeTextPanel QToolButton { background: #4a5568; border: 1px solid #56606f;
    border-radius: 2px; color: #f5f5f5; min-width: 26px; padding: 2px 4px; }
#SciForgeTextPanel QToolButton:checked { background: #3fa9f5; border: 1px solid #8cc4ff; }
#SciForgeTextPanel QCheckBox { color: #f5f5f5; }
"""


class TextDialog(QtWidgets.QFrame):
    """Fusion's Text dialog, at the top of the sketch panel. `target`: the text being
    edited, or None for a new one."""

    last = None  # the newest dialog (tests and diagnostics)

    def __init__(self, layer, target=None):
        from . import sketch_palette

        panel = sketch_palette.sketch_panel()
        super().__init__(panel)
        TextDialog.last = self
        self.layer = layer
        self.session = layer.session
        self.sketch = layer.sketch
        self.doc = self.sketch.Document
        self.target = target
        self.closed = False
        self.spec = text.spec_of(target) if target is not None else remembered_spec()
        if target is None:
            self.spec["type"] = "text"
        self.frame_placed = target is not None and self.spec["type"] == "text"
        self.corner1 = None  # first corner clicked (new text)
        self.hover = None  # the mouse in sketch coordinates (rubber band)
        self.pivot = "bottom_left"
        self.turning = None  # {"start": (x, y), "angle": a} while the handle is dragged
        self.plan = None
        self.error = ""
        self.formula = text.formula_of(target, "TextHeight") if target is not None else ""
        self._build()
        if panel is not None and panel.layout() is not None:
            panel.layout().insertWidget(0, self)
        self.show()
        self._timer = QtCore.QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._preview)
        if target is not None:
            layer.hidden.add(target.Name)
            layer.refresh(now=True)
            if self.spec["type"] == "text":
                found = text.read_frame(self.sketch, self.spec["frame_ids"])
                if found is not None:
                    (cx, cy), angle, width, height = found
                    self.spec.update(corner=(cx, cy), angle=angle, width=width, frame_height=height)
        self._show_spec()
        self._update_rows()
        self._preview()
        self.text_box.setFocus()
        log("text: %s" % ("editing %s" % target.Label if target is not None else "new text"))

    # -- layout ---------------------------------------------------------------------------
    def _build(self):
        self.setObjectName("SciForgeTextPanel")
        self.setStyleSheet(STYLE)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 6)
        title = QtWidgets.QLabel("TEXT")
        title.setProperty("role", "title")
        layout.addWidget(title)
        body = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(body)
        form.setContentsMargins(10, 4, 10, 4)
        form.setVerticalSpacing(5)
        self.form = form
        layout.addWidget(body)

        self.type_box = QtWidgets.QComboBox()
        self.type_box.addItem("Text", "text")
        self.type_box.addItem("Text On Path", "path")
        self.type_box.currentIndexChanged.connect(self._type_changed)
        form.addRow("Type", self.type_box)

        self.path_button = QtWidgets.QPushButton("Select path")
        self.path_button.setCheckable(True)
        self.path_button.clicked.connect(self._path_clicked)
        self.path_label = QtWidgets.QLabel("Path")
        form.addRow(self.path_label, self.path_button)

        self.text_box = QtWidgets.QPlainTextEdit()
        self.text_box.setObjectName("SciForgeTextBox")
        self.text_box.setFixedHeight(64)
        self.text_box.setToolTip(
            "The text. Fusion's form works too: 'Rev ' + version (text in single quotes, "
            "parameters by name, joined with +)."
        )
        self.text_box.textChanged.connect(self._changed)
        form.addRow("Text", self.text_box)

        self.height = QtWidgets.QLineEdit()
        self.height.setObjectName("SciForgeTextHeight")
        self.height.setToolTip("Height of the letters' em box (a capital is about 0.7 of it)")
        self.height.editingFinished.connect(self._changed)
        self.height.textEdited.connect(lambda _t: self._timer.start())
        form.addRow("Height", self.height)

        self.angle = QtWidgets.QLineEdit()
        self.angle.setObjectName("SciForgeTextAngle")
        self.angle.setToolTip("Turn the frame (or drag the round handle next to it)")
        self.angle.editingFinished.connect(self._changed)
        self.angle.textEdited.connect(lambda _t: self._timer.start())
        self.angle_label = QtWidgets.QLabel("Angle")
        form.addRow(self.angle_label, self.angle)

        self.font_box = QtWidgets.QComboBox()
        self.font_box.setObjectName("SciForgeTextFont")
        self.font_box.setEditable(True)
        self.font_box.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        try:
            families = text.catalog().families()
        except Exception as exc:
            warn("fonts: %s" % exc)
            families = []
        self.font_box.addItems(families)
        completer = self.font_box.completer()
        if completer is not None:
            completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.font_box.activated.connect(lambda _i: self._changed())
        self.font_box.lineEdit().editingFinished.connect(self._changed)
        form.addRow("Font", self.font_box)

        row = QtWidgets.QHBoxLayout()
        self.bold = self._toggle("B", "Bold", row)
        self.italic = self._toggle("I", "Italic", row)
        self.underline = self._toggle("U", "Underline", row)
        row.addStretch(1)
        form.addRow("Typeface", row)

        row = QtWidgets.QHBoxLayout()
        self.h_buttons = {
            "left": self._toggle("Left", "Align left", row, group="h"),
            "center": self._toggle("Center", "Align in the middle", row, group="h"),
            "right": self._toggle("Right", "Align right", row, group="h"),
        }
        row.addStretch(1)
        form.addRow("Horizontal", row)
        row = QtWidgets.QHBoxLayout()
        self.v_buttons = {
            "top": self._toggle("Top", "Align to the frame's top", row, group="v"),
            "middle": self._toggle("Middle", "Middle of the frame", row, group="v"),
            "bottom": self._toggle("Bottom", "Align to the frame's bottom", row, group="v"),
        }
        row.addStretch(1)
        self.v_label = QtWidgets.QLabel("Vertical")
        form.addRow(self.v_label, row)

        self.spacing = QtWidgets.QDoubleSpinBox()
        self.spacing.setObjectName("SciForgeTextSpacing")
        self.spacing.setRange(core.MIN_SPACING, core.MAX_SPACING)
        self.spacing.setDecimals(1)
        self.spacing.setSuffix(" %")
        self.spacing.setToolTip("Percent of the font's own spacing (0 keeps it)")
        self.spacing.valueChanged.connect(self._changed)
        form.addRow("Character Spacing", self.spacing)

        row = QtWidgets.QHBoxLayout()
        self.flip_h = self._toggle("Horizontal", "Mirror the text left to right", row)
        self.flip_v = self._toggle("Vertical", "Mirror the text top to bottom", row)
        row.addStretch(1)
        form.addRow("Flip", row)

        row = QtWidgets.QHBoxLayout()
        self.above = self._toggle("Above", "Letters above the path", row, group="p")
        self.below = self._toggle("Below", "Letters below the path", row, group="p")
        row.addStretch(1)
        self.place_label = QtWidgets.QLabel("Placement")
        form.addRow(self.place_label, row)
        self.fit = QtWidgets.QCheckBox("Fit to Path")
        self.fit.setToolTip("Spread the letters over the whole path")
        self.fit.toggled.connect(self._changed)
        form.addRow(self.fit)

        self.hint = QtWidgets.QLabel("")
        self.hint.setProperty("role", "hint")
        self.hint.setWordWrap(True)
        form.addRow(self.hint)
        self.message = QtWidgets.QLabel("")
        self.message.setProperty("role", "error")
        self.message.setWordWrap(True)
        form.addRow(self.message)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.setObjectName("SciForgeTextButtons")
        buttons.accepted.connect(lambda: QtCore.QTimer.singleShot(0, self.accept))
        buttons.rejected.connect(lambda: QtCore.QTimer.singleShot(0, self.reject))
        self.ok_button = buttons.button(QtWidgets.QDialogButtonBox.Ok)
        form.addRow(buttons)

    def _toggle(self, label, tip, row, group=None):
        button = QtWidgets.QToolButton()
        button.setText(label)
        button.setToolTip(tip)
        button.setCheckable(True)
        button.setObjectName("SciForgeText_%s" % label.replace(" ", ""))
        if group is not None:
            groups = self.__dict__.setdefault("_groups", {})
            if group not in groups:
                groups[group] = QtWidgets.QButtonGroup(self)
                groups[group].setExclusive(True)
            groups[group].addButton(button)
        button.toggled.connect(lambda _on: self._changed())
        row.addWidget(button)
        return button

    def _show_spec(self):
        spec = self.spec
        widgets = (
            [
                self.type_box,
                self.text_box,
                self.font_box,
                self.bold,
                self.italic,
                self.underline,
                self.spacing,
                self.flip_h,
                self.flip_v,
                self.above,
                self.below,
                self.fit,
            ]
            + list(self.h_buttons.values())
            + list(self.v_buttons.values())
        )
        for widget in widgets:
            widget.blockSignals(True)
        try:
            self.type_box.setCurrentIndex(0 if spec["type"] == "text" else 1)
            self.text_box.setPlainText(spec["text"])
            self.height.setText(self.formula or _number(spec["height"]))
            self.angle.setText(_number(spec["angle"]))
            self.font_box.setEditText(spec["font"])
            index = self.font_box.findText(spec["font"])
            if index >= 0:
                self.font_box.setCurrentIndex(index)
            self.bold.setChecked(spec["bold"])
            self.italic.setChecked(spec["italic"])
            self.underline.setChecked(spec["underline"])
            self.h_buttons[spec["h_align"]].setChecked(True)
            self.v_buttons[spec["v_align"]].setChecked(True)
            self.spacing.setValue(spec["spacing"])
            self.flip_h.setChecked(spec["flip_h"])
            self.flip_v.setChecked(spec["flip_v"])
            (self.above if spec["above"] else self.below).setChecked(True)
            self.fit.setChecked(spec["fit"])
        finally:
            for widget in widgets:
                widget.blockSignals(False)

    def _update_rows(self):
        on_path = self.spec["type"] == "path"
        for widget in (
            self.path_label,
            self.path_button,
            self.place_label,
            self.above,
            self.below,
            self.fit,
        ):
            widget.setVisible(on_path)
        for widget in (self.angle, self.angle_label, self.v_label) + tuple(self.v_buttons.values()):
            widget.setVisible(not on_path)
        self.path_button.setText("1 curve" if self.spec["path_id"] and on_path else "Select path")
        self._update_hint()

    def _update_hint(self):
        if self.spec["type"] == "path":
            if not self.spec["path_id"]:
                self.path_button.setChecked(True)
                say = "Click the curve of the sketch the text follows."
            else:
                say = ""
        elif not self.frame_placed:
            say = (
                "Click the first corner of the text frame."
                if self.corner1 is None
                else "Click the opposite corner of the frame."
            )
        else:
            say = "" if self.spec["text"].strip() else "Type the text."
        self.hint.setText(say)

    # -- reading the fields -------------------------------------------------------------------
    def _collect(self):
        spec = self.spec
        spec["type"] = self.type_box.currentData()
        spec["text"] = self.text_box.toPlainText()
        spec["font"] = self.font_box.currentText().strip()
        spec["bold"] = self.bold.isChecked()
        spec["italic"] = self.italic.isChecked()
        spec["underline"] = self.underline.isChecked()
        for name, button in self.h_buttons.items():
            if button.isChecked():
                spec["h_align"] = name
        for name, button in self.v_buttons.items():
            if button.isChecked():
                spec["v_align"] = name
        spec["spacing"] = float(self.spacing.value())
        spec["flip_h"] = self.flip_h.isChecked()
        spec["flip_v"] = self.flip_v.isChecked()
        spec["above"] = self.above.isChecked()
        spec["fit"] = self.fit.isChecked()
        errors = []
        height_text = self.height.text().strip()
        try:
            value, formula = _read_value(self.doc, height_text, "mm")
            core.check_height(value)
            spec["height"] = value
            self.formula = formula
        except Exception as exc:
            errors.append("Height: %s" % exc)
        if spec["type"] == "text":
            try:
                angle, _formula = _read_value(self.doc, self.angle.text().strip(), "deg")
                if abs(angle - spec["angle"]) > 1e-9 and self.frame_placed:
                    spec["corner"] = core.turned_corner(
                        spec["corner"],
                        spec["angle"],
                        spec["width"],
                        spec["frame_height"],
                        self.pivot,
                        angle,
                    )
                spec["angle"] = core.normal_angle(angle)
            except Exception as exc:
                errors.append("Angle: %s" % exc)
        return errors

    @_safe
    def _changed(self, *_args):
        if self.closed:
            return
        self._timer.start()

    @_safe
    def _type_changed(self, _index):
        self._collect()
        self._update_rows()
        self._timer.start()

    @_safe
    def _path_clicked(self):
        self.path_button.setChecked(True)
        self.hint.setText("Click the curve of the sketch the text follows.")

    # -- preview -------------------------------------------------------------------------------
    @_safe
    def _preview(self):
        if self.closed:
            return
        errors = self._collect()
        self.plan = None
        self.error = ""
        notes = []
        if not errors and self._ready():
            try:
                # the dialog's own frame (turned or typed), not the frame lines as they are
                spec = dict(self.spec, frame_ids=[])
                self.plan = text.plan(spec, self.sketch, lookup=text.parameter_lookup(self.doc))
                notes = list(self.plan.notes)
            except core.TextError as exc:
                self.error = str(exc)
            except Exception as exc:
                self.error = str(exc)
        if errors:
            self.error = "; ".join(errors)
        self.message.setText(self.error if self.spec["text"].strip() or errors else "")
        self.message.setVisible(bool(self.message.text()))
        self._update_hint()
        if notes:
            self.hint.setText(" ".join(notes))
        self._draw()

    def _ready(self):
        if self.spec["type"] == "path":
            return bool(self.spec["path_id"])
        return self.frame_placed

    def frame(self):
        """(corner, angle, width, height) of the frame shown now, or None."""
        spec = self.spec
        if spec["type"] != "text":
            return None
        if self.frame_placed:
            return tuple(spec["corner"]), spec["angle"], spec["width"], spec["frame_height"]
        if self.corner1 is not None and self.hover is not None:
            corner, width, height = core.frame_from_points(self.corner1, self.hover)
            return corner, 0.0, width, height
        return None

    def _draw(self):
        try:
            frame = self.frame()
            dots, pivot, handle = (), None, None
            if frame is not None and self.frame_placed:
                points = core.snap_points(*frame)
                dots = list(points.values())
                pivot = points.get(self.pivot)
                handle = self._handle_lines(frame)
            path = None
            if self.spec["type"] == "path" and self.plan is not None:
                path = self.plan.path_points
            self.layer.draw_preview(self.plan, frame, dots, pivot, handle, path)
        except Exception as exc:
            warn("text preview: %s" % exc)

    def handle_point(self, frame=None):
        """Where the round turning handle sits: out from the frame's top right corner."""
        frame = frame or self.frame()
        if frame is None:
            return None
        corner, angle, width, height = frame
        tr = core.snap_points(corner, angle, width, height)["top_right"]
        mm = _mm_per_px(self.session, self.session.gl.rect().center())
        reach = HANDLE_OFFSET_PX * mm
        a = math.radians(angle + 45.0)
        return (tr[0] + reach * math.cos(a), tr[1] + reach * math.sin(a))

    def _handle_lines(self, frame):
        center = self.handle_point(frame)
        if center is None:
            return None
        mm = _mm_per_px(self.session, self.session.gl.rect().center())
        r = 7 * mm
        circle = [
            (
                center[0] + r * math.cos(2 * math.pi * i / 24),
                center[1] + r * math.sin(2 * math.pi * i / 24),
            )
            for i in range(25)
        ]
        tr = core.snap_points(*frame)["top_right"]
        return [circle, [tr, center]]

    # -- the mouse (from the layer's filter) -----------------------------------------------
    def mouse(self, event):
        """True if the dialog took the mouse event (frame corners, the path, the turning
        handle, a frame dot)."""
        kind = event.type()
        if kind not in (
            QtCore.QEvent.MouseButtonPress,
            QtCore.QEvent.MouseMove,
            QtCore.QEvent.MouseButtonRelease,
        ):
            return False
        pos = event.position().toPoint()
        session = self.session
        if kind == QtCore.QEvent.MouseMove:
            if self.turning is not None:
                self._turn_to(pos)
                return True
            if self.spec["type"] == "text" and not self.frame_placed:
                point = self._snapped(pos)
                if point is not None:
                    self.hover = point
                    self._draw()
            return False
        if event.button() != QtCore.Qt.LeftButton:
            return False
        if kind == QtCore.QEvent.MouseButtonRelease:
            if self.turning is not None:
                self.turning = None
                self._show_angle()
                return True
            return False
        # a press
        if self.spec["type"] == "path" and self.path_button.isChecked():
            return self._pick_path(pos)
        if self.spec["type"] == "text" and not self.frame_placed:
            point = self._snapped(pos)
            if point is None:
                return True
            if self.corner1 is None:
                self.corner1 = point
                self.hover = point
                self._update_hint()
                self._draw()
                return True
            self._place_frame(self.corner1, point)
            return True
        if self.frame_placed and self.spec["type"] == "text":
            frame = self.frame()
            handle = self.handle_point(frame)
            if (
                handle is not None
                and _dist(_screen(session, handle), QtCore.QPointF(pos)) <= HANDLE_PX
            ):
                start = _sketch_point(session, pos)
                if start is not None:
                    self.turning = {
                        "start": start,
                        "angle": self.spec["angle"],
                        "corner": tuple(self.spec["corner"]),
                    }
                    return True
            for name, point in core.snap_points(*frame).items():
                if _dist(_screen(session, point), QtCore.QPointF(pos)) <= DOT_PX:
                    self.pivot = name
                    self._draw()
                    return True
        return False

    def _snapped(self, pos):
        """The sketch point under the mouse; on a point of the sketch FreeCAD lights up,
        that point exactly."""
        point = _sketch_point(self.session, pos)
        try:
            pre = Gui.Selection.getPreselection()
            if getattr(pre, "ObjectName", "") == self.sketch.Name:
                for name in pre.SubElementNames:
                    short = name.rsplit(".", 1)[-1]
                    if short.startswith("Vertex"):
                        geo, where = self.sketch.getGeoVertexIndex(int(short[6:]) - 1)
                        p = self.sketch.getPoint(geo, where)
                        return (p.x, p.y)
        except Exception:
            pass
        return point

    def _place_frame(self, first, second):
        corner, width, height = core.frame_from_points(first, second)
        if width < 1e-6 or height < 1e-6:
            # a click without a drag: a frame just around the text, from that point
            try:
                info = text.resolve_font(self.spec["font"], self.spec["bold"], self.spec["italic"])[
                    0
                ]
                sample = self.spec["text"].strip() or "Text"
                width, height = core.text_extent(
                    sample, info, self.spec["height"], self.spec["spacing"]
                )
                corner = (first[0], first[1])
            except Exception:
                width, height = 10.0 * self.spec["height"], 1.5 * self.spec["height"]
        self.spec.update(corner=corner, angle=0.0, width=width, frame_height=height)
        self.frame_placed = True
        self.corner1 = None
        self._show_angle()
        self._update_hint()
        self.text_box.setFocus()
        self._timer.start()
        log("text: frame placed (%.2f x %.2f mm)" % (width, height))

    def _turn_to(self, pos):
        now = _sketch_point(self.session, pos)
        if now is None:
            return
        frame = (
            self.turning["corner"],
            self.turning["angle"],
            self.spec["width"],
            self.spec["frame_height"],
        )
        pivot = core.snap_points(*frame)[self.pivot]
        turn = core.angle_about(pivot, self.turning["start"], now)
        angle = core.normal_angle(round(self.turning["angle"] + turn, 2))
        self.spec["corner"] = core.turned_corner(*frame, pivot=self.pivot, new_angle_deg=angle)
        self.spec["angle"] = angle
        self._show_angle()
        self._timer.start()

    def _show_angle(self):
        self.angle.blockSignals(True)
        self.angle.setText(_number(self.spec["angle"]))
        self.angle.blockSignals(False)

    def _pick_path(self, pos):
        """A press while the Path box waits: the sketch curve under the mouse."""
        index = _curve_under_mouse(self.sketch)
        if index is None:
            commands.tell("Click a curve of the sketch (a line, an arc, a circle or a spline).")
            return True
        geo = self.sketch.Geometry[index]
        if geo.TypeId == "Part::GeomPoint":
            commands.tell("A text follows a curve, not a point.")
            return True
        if any(gid == self.sketch.getGeometryId(index) for gid in self._own_frame_ids()):
            commands.tell("That is the text's own frame: pick another curve.")
            return True
        self.spec["path_id"] = self.sketch.getGeometryId(index)
        self.path_button.setChecked(False)
        self._update_rows()
        self._timer.start()
        log("text: path is %s" % geo.TypeId.split("::")[-1])
        return True

    def _own_frame_ids(self):
        return list(self.target.FrameIds) if self.target is not None else []

    # -- OK / Cancel ------------------------------------------------------------------------------
    @_safe
    def accept(self):
        if self.closed:
            return
        self._timer.stop()
        self._preview()
        if self.spec["type"] == "text" and not self.frame_placed:
            self._say("Place the frame first: click two corners in the sketch.")
            return
        if self.spec["type"] == "path" and not self.spec["path_id"]:
            self._say("Select the path: click a curve of the sketch.")
            return
        if self.error or self.plan is None:
            self._say(self.error or "Type some text first: an empty text makes no profile.")
            return
        try:
            obj = self._apply()
        except Exception as exc:
            self._say(str(exc))
            return
        remember(self.spec)
        log(
            "text %s: '%s'"
            % (
                "changed" if self.target is not None else "made",
                obj.ResolvedText if obj is not None else "",
            )
        )
        self._close()

    def _say(self, msg):
        self.message.setText(msg)
        self.message.setVisible(True)

    def _apply(self):
        doc = self.doc
        spec = dict(self.spec)
        doc.openTransaction("Edit Text" if self.target is not None else "Text")
        try:
            if self.target is None:
                obj = text.make(self.sketch, spec)
            else:
                obj = self.target
                if spec["type"] == "text":
                    if (
                        not spec["frame_ids"]
                        or text.read_frame(self.sketch, spec["frame_ids"]) is None
                    ):
                        spec["frame_ids"] = text.add_frame(
                            self.sketch,
                            spec["corner"],
                            spec["angle"],
                            spec["width"],
                            spec["frame_height"],
                        )
                    else:
                        now = text.read_frame(self.sketch, spec["frame_ids"])
                        wanted = (
                            tuple(spec["corner"]),
                            spec["angle"],
                            spec["width"],
                            spec["frame_height"],
                        )
                        if not _same_frame(now, wanted):
                            if not text.set_frame(self.sketch, spec["frame_ids"], *wanted):
                                commands.tell(
                                    "The frame's dimensions hold it: it stayed where they put it."
                                )
                elif obj.TextType == "Text" and obj.FrameIds:
                    text.remove_frame(self.sketch, list(obj.FrameIds))
                    spec["frame_ids"] = []
                text.set_height_formula(obj, self.formula)  # (before: a number replaces it)
                text.apply_spec(obj, spec)
            text.set_height_formula(obj, self.formula)
            _keep_frame_values(obj)
            obj.recompute()
            if "Invalid" in list(obj.State):
                raise core.TextError(obj.getStatusString())
        except Exception:
            doc.abortTransaction()
            raise
        doc.commitTransaction()
        return obj

    @_safe
    def reject(self):
        if self.closed:
            return
        log("text: cancelled")
        self._close()

    def settle(self):
        """The sketch closes under the dialog (Finish Sketch, E): keep a valid text."""
        if self.closed:
            return
        try:
            self._timer.stop()
            self._preview()
            if self.plan is not None and not self.error and self._ready():
                self._apply()
                remember(self.spec)
                log("text kept as the sketch closed")
        except Exception as exc:
            warn("text: %s" % exc)
        self._close(refresh=False)

    def _close(self, refresh=True):
        if self.closed:
            return
        self.closed = True
        try:
            self._timer.stop()
        except Exception:
            pass
        layer = self.layer
        if layer.dialog is self:
            layer.dialog = None
        if self.target is not None:
            layer.hidden.discard(self.target.Name)
        try:
            layer.clear_preview()
        except Exception:
            pass
        if refresh:
            layer.refresh(now=True)
        try:
            self.hide()
            self.setParent(None)
            self.deleteLater()
        except Exception:
            pass
        try:
            gl = self.session.gl
            if gl is not None:
                gl.setFocus()
        except Exception:
            pass

    def keyPressEvent(self, event):
        key = event.key()
        if key == QtCore.Qt.Key_Escape:
            QtCore.QTimer.singleShot(0, self.reject)
            event.accept()
            return
        if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            # (the Text box keeps Enter for new lines; Ctrl+Enter is OK there)
            QtCore.QTimer.singleShot(0, self.accept)
            event.accept()
            return
        super().keyPressEvent(event)


class _TextBoxKeys(QtCore.QObject):
    """Ctrl+Enter in the Text box is OK; Esc there cancels (Enter makes a new line)."""

    def __init__(self, dialog):
        super().__init__(dialog)
        self.dialog = dialog

    def eventFilter(self, obj, event):
        try:
            if event.type() == QtCore.QEvent.KeyPress:
                key = event.key()
                if key == QtCore.Qt.Key_Escape:
                    QtCore.QTimer.singleShot(0, self.dialog.reject)
                    return True
                if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter) and (
                    event.modifiers() & QtCore.Qt.ControlModifier
                ):
                    QtCore.QTimer.singleShot(0, self.dialog.accept)
                    return True
        except Exception as exc:
            warn("text box: %s" % exc)
        return False


def _same_frame(a, b, tol=1e-6):
    if a is None or b is None:
        return False
    (ax, ay), aa, aw, ah = a
    (bx, by), ba, bw, bh = b
    return (
        abs(ax - bx) < tol
        and abs(ay - by) < tol
        and abs(core.normal_angle(aa - ba)) < 1e-6
        and abs(aw - bw) < tol
        and abs(ah - bh) < tol
    )


def _number(value):
    text_value = ("%.4f" % float(value)).rstrip("0").rstrip(".")
    return "0" if text_value in ("-0", "") else text_value


def _read_value(doc, typed, unit):
    """(value, formula) of a field: a number ("5", "5 mm", "0.2 in") or a formula of
    parameters ("h * 2", "=h+1"): then formula is the text to keep on the property."""
    typed = (typed or "").strip()
    if not typed:
        raise core.TextError("type a value")
    try:
        quantity = App.Units.Quantity(typed)
        if quantity.Unit == App.Units.Quantity(1.0).Unit:
            return float(quantity.Value), ""
        return float(quantity.getValueAs(unit).Value), ""
    except Exception:
        pass
    from . import extrude

    try:
        return extrude.evaluate(doc, typed), typed.lstrip("=").strip()
    except Exception as exc:
        raise core.TextError(str(exc))


def _curve_under_mouse(sketch):
    """Index of the sketch curve FreeCAD lights up under the mouse, or None."""
    try:
        pre = Gui.Selection.getPreselection()
        if getattr(pre, "ObjectName", "") != sketch.Name:
            return None
        for name in pre.SubElementNames:
            short = name.rsplit(".", 1)[-1]
            if short.startswith("Edge"):
                return int(short[4:]) - 1
    except Exception:
        pass
    return None


@_safe
def open_dialog(session=None, target=None):
    """Open the Text dialog in the open sketch (a new text, or `target`)."""
    session = session or _session()
    if session is None or session.closed:
        commands.tell("Text works inside a sketch: click Create Sketch (or edit a sketch) first.")
        return None
    layer = ensure_layer(session)
    if layer is None:
        return None
    if layer.dialog is not None:
        if target is not None and layer.dialog.target is target:
            return layer.dialog
        layer.dialog.settle()
    try:
        session.finish_tool() if session.tool_running() else None
    except Exception:
        pass
    try:
        session.areas.clear()
    except Exception:
        pass
    dialog = TextDialog(layer, target)
    dialog.text_box.installEventFilter(_TextBoxKeys(dialog))
    layer.dialog = dialog
    return dialog


# -- the layer follows the sketch sessions ------------------------------------------------------
def ensure_layer(session=None):
    session = session or _session()
    if session is None or session.closed:
        return None
    layer = _state["layer"]
    if layer is not None and layer.session is session and not layer.closed:
        return layer
    if layer is not None:
        layer.remove()
    try:
        layer = TextLayer(session)
    except Exception as exc:
        warn("sketch text: %s" % exc)
        layer = None
    _state["layer"] = layer
    return layer


def _session_changed():
    """A sketch opened or closed: the layer follows (from a timer, after sketch_mode)."""
    try:
        session = _session()
        layer = _state["layer"]
        if session is None:
            if layer is not None:
                layer.remove()
                _state["layer"] = None
                QtCore.QTimer.singleShot(150, sync_all)
            return
        ensure_layer(session)
    except Exception as exc:
        warn("sketch text: %s" % exc)


class _GuiObserver:
    def slotInEdit(self, vp):
        QtCore.QTimer.singleShot(50, _session_changed)

    def slotResetEdit(self, vp):
        QtCore.QTimer.singleShot(50, _session_changed)


class _AppObserver:
    """Changes that concern texts. Only schedules work."""

    def slotChangedObject(self, obj, prop):
        try:
            layer = current_layer()
            if layer is not None and prop in ("Geometry", "Constraints", "Placement"):
                if obj is layer.sketch:
                    layer.refresh()
                    return
            if prop == "Visibility" and obj.TypeId == "Sketcher::SketchObject":
                key = (obj.Document.Name, obj.Name)
                QtCore.QTimer.singleShot(0, lambda: _sync_sketch(*key))
            elif text.is_text(obj) and layer is not None and obj.Sketch is layer.sketch:
                if prop not in ("Visibility", "Shape", "ResolvedText", "FontUsed"):
                    layer.refresh()
        except Exception:
            pass

    def slotCreatedObject(self, obj):
        self._texts_changed()

    def slotDeletedObject(self, obj):
        try:
            if obj.TypeId == "Sketcher::SketchObject":
                doc = obj.Document.Name
                QtCore.QTimer.singleShot(0, lambda: remove_orphans(doc))
        except Exception:
            pass
        self._texts_changed()

    def slotUndoDocument(self, doc):
        self._texts_changed()

    def slotRedoDocument(self, doc):
        self._texts_changed()

    def _texts_changed(self):
        layer = current_layer()
        if layer is not None:
            layer.refresh()


def _font_missing(doc_name):
    """text.TextFeature found a text whose font this computer lacks while a design opens:
    say so once the design is open (FreeCAD tells observers of no finished restore)."""
    try:
        QtCore.QTimer.singleShot(300, lambda: _tell_missing_fonts(doc_name))
    except Exception:
        pass


def _tell_missing_fonts(doc_name):
    """After a design opens: say (next to the pointer) which texts lost their font."""
    try:
        missing = text._FONTS["missing"]
        notes = [msg for name, msg in missing if name == doc_name]
        missing[:] = [(name, msg) for name, msg in missing if name != doc_name]
        if notes:
            commands.tell("\n".join(notes))
    except Exception as exc:
        log("text: font notes: %s" % exc)


class _SelectionObserver:
    """Fusion selects a text as one thing: a click on one letter of a finished sketch's
    text selects the whole text (FreeCAD would select that letter's face)."""

    def addSelection(self, doc, obj_name, sub, pnt):
        if not sub:
            return
        try:
            d = App.getDocument(doc)
            obj = d.getObject(obj_name) if d is not None else None
        except Exception:
            return
        if not text.is_text(obj):
            return
        QtCore.QTimer.singleShot(0, lambda: _whole_text(doc, obj_name))


def _whole_text(doc_name, name):
    try:
        if Gui.Control.activeDialog():
            return  # a command's own picking is in charge (Extrude takes the whole text)
        doc = App.getDocument(doc_name)
        obj = doc.getObject(name)
        if obj is None:
            return
        entries = Gui.Selection.getSelectionEx(doc_name)
        others = [(s.Object, s.SubElementNames) for s in entries if s.Object is not obj]
        Gui.Selection.clearSelection()
        for other, subs in others:
            for sub in subs or [""]:
                Gui.Selection.addSelection(doc_name, other.Name, sub)
        Gui.Selection.addSelection(doc_name, name)
    except Exception as exc:
        warn("text selection: %s" % exc)


def _sync_sketch(doc_name, name):
    """A text shows when its sketch shows (not while the sketch is open: the layer draws
    it then)."""
    try:
        doc = App.getDocument(doc_name)
        sketch = doc.getObject(name) if doc is not None else None
        if sketch is None:
            return
        layer = current_layer()
        if layer is not None and layer.sketch is sketch:
            return
        visible = (
            bool(sketch.ViewObject.Visibility) if sketch.ViewObject else bool(sketch.Visibility)
        )
        for obj in text.texts_of(sketch):
            vobj = obj.ViewObject
            if vobj is not None and bool(vobj.Visibility) != visible:
                vobj.Visibility = visible
    except Exception:
        pass


def sync_all():
    """Every text shows exactly when its sketch does (after a sketch was closed)."""
    try:
        for doc in App.listDocuments().values():
            for sketch in doc.findObjects("Sketcher::SketchObject"):
                if text.texts_of(sketch):
                    _sync_sketch(doc.Name, sketch.Name)
    except Exception:
        pass


def remove_orphans(doc_name, tries=0):
    """Texts whose sketch was deleted (by FreeCAD's own Delete; SciForge's takes them along)
    go too, as their own undo step, like the copies of a deleted pattern."""
    try:
        doc = App.getDocument(doc_name)
    except Exception:
        return
    try:
        if getattr(doc, "Transacting", False) or getattr(doc, "Restoring", False):
            return  # an undo / redo / opening brings its texts along itself
        if getattr(doc, "Recomputing", False) or doc.HasPendingTransaction:
            if tries < 50:
                QtCore.QTimer.singleShot(100, lambda: remove_orphans(doc_name, tries + 1))
            return
        lost = [o for o in doc.Objects if text.is_text(o) and o.Sketch is None]
        if not lost:
            return
        doc.openTransaction("Delete texts of a deleted sketch")
        try:
            for obj in lost:
                text.remove(obj)
        except Exception:
            doc.abortTransaction()
            raise
        doc.commitTransaction()
        log("removed %d text(s) whose sketch was deleted" % len(lost))
    except Exception as exc:
        warn("text: %s" % exc)


# -- the text object's display ------------------------------------------------------------------
class ViewProviderText:
    """How a finished sketch's text looks: its letters' outlines in the sketch's line
    colour, the letters shaded like the sketch's areas. A double-click opens the sketch
    and the Text dialog."""

    def __init__(self, vobj):
        vobj.Proxy = self
        self._style(vobj)

    def attach(self, vobj):
        self.Object = vobj.Object

    @staticmethod
    def _style(vobj):
        try:
            vobj.LineColor = (0.94, 0.94, 0.94)
            vobj.LineWidth = 1.5
            vobj.PointSize = 1.0
            vobj.PointColor = (0.94, 0.94, 0.94)
            if "ShapeAppearance" in vobj.PropertiesList:
                material = vobj.ShapeAppearance[0]
                material.DiffuseColor = (FILL[0], FILL[1], FILL[2], 1.0)
                material.AmbientColor = (FILL[0] * 0.5, FILL[1] * 0.5, FILL[2] * 0.5, 1.0)
                material.EmissiveColor = (FILL[0] * 0.3, FILL[1] * 0.3, FILL[2] * 0.3, 1.0)
                vobj.ShapeAppearance = [material]
            else:
                vobj.ShapeColor = FILL
            vobj.Transparency = 55
        except Exception as exc:
            warn("text display: %s" % exc)

    def getIcon(self):
        return ui_icon_path("sk_text")

    def claimChildren(self):
        return []

    def doubleClicked(self, vobj):
        obj = vobj.Object
        QtCore.QTimer.singleShot(0, lambda: edit_text(obj))
        return True

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return None
        obj = vobj.Object
        QtCore.QTimer.singleShot(0, lambda: edit_text(obj))
        return False

    def unsetEdit(self, vobj, mode=0):
        return None

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def edit_text(obj):
    """Open the text's sketch (if it is not open) and the Text dialog on the text."""
    try:
        if not _alive(obj) or obj.Sketch is None:
            return
        session = _session()
        if session is not None and session.sketch is obj.Sketch:
            open_dialog(session, obj)
            return
        if not commands.finish_open_dialog():
            return
        Gui.ActiveDocument.setEdit(obj.Sketch.Name)
        _open_when_ready(obj, 0)
    except Exception as exc:
        warn("could not edit %s: %s" % (getattr(obj, "Label", "the text"), exc))


@_safe
def _open_when_ready(obj, tries):
    session = _session()
    if session is not None and session.sketch is obj.Sketch and current_layer() is not None:
        open_dialog(session, obj)
        return
    if tries < 30:
        QtCore.QTimer.singleShot(100, lambda: _open_when_ready(obj, tries + 1))


# -- commands -------------------------------------------------------------------------------------
class TextCommand:
    def GetResources(self):
        return {
            "MenuText": "Text",
            "ToolTip": "Text in the sketch: click two corners of its frame (or pick a curve for "
            "Text On Path), type, pick the font and height; extrude or emboss it",
            "Pixmap": ui_icon_path("sk_text"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            open_dialog()
        except Exception as exc:
            warn("Text failed to start: %s" % exc)


@_safe
def _dialog_when_ready(sketch, tries):
    """The Text dialog in `sketch` once FreeCAD has it open (its edit mode starts later)."""
    session = _session()
    if session is not None and session.sketch is sketch:
        open_dialog(session)  # (it makes the text layer of the sketch when there is none yet)
        return
    if tries < 30:
        QtCore.QTimer.singleShot(100, lambda: _dialog_when_ready(sketch, tries + 1))
    else:
        warn("Text: the sketch did not open")


class FaceTextCommand:
    """SOLID > CREATE > Text (Luca, 2026-10-16: "a text tool to add text to a face"): click
    a flat face or a plane, a sketch opens there with the Text dialog. In Fusion text is a
    sketch tool too (Create Sketch on the face, then Text); Finish Sketch, then Extrude or
    Emboss raises or cuts it."""

    def GetResources(self):
        return {
            "MenuText": "Text",
            "ToolTip": "Text on a face: click a flat face or a plane, then type; Finish Sketch "
            "and Extrude (E) or Emboss it into the part",
            "Pixmap": ui_icon_path("sk_text"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            if _session() is not None:
                open_dialog()  # a sketch is open: text in it, as SKETCH > Text
                return
            if not commands.finish_open_dialog():
                return
            from . import sketch_ui

            sketch_ui.start(
                then=lambda sketch: _dialog_when_ready(sketch, 0), title="Text: pick a face"
            )
        except Exception as exc:
            warn("Text failed to start: %s" % exc)


class EditTextCommand:
    def GetResources(self):
        return {
            "MenuText": "Edit Text",
            "ToolTip": "Change the picked text (or double-click it)",
            "Pixmap": ui_icon_path("sk_text"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            picked = picked_texts()
            if not picked:
                picked = _selected_texts()
            if not picked:
                commands.tell("Edit Text: click a text first (or double-click it).")
                return
            edit_text(picked[0])
        except Exception as exc:
            warn("Edit Text: %s" % exc)


class ExplodeTextCommand:
    def GetResources(self):
        return {
            "MenuText": "Explode Text",
            "ToolTip": "Turn the picked text into ordinary sketch curves (it is no longer "
            "editable as text)",
            "Pixmap": ui_icon_path("sk_text"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            picked = picked_texts() or _selected_texts()
            explode_texts(picked)
        except Exception as exc:
            warn("Explode Text: %s" % exc)


def _selected_texts():
    found = []
    try:
        for sel in Gui.Selection.getSelectionEx():
            if text.is_text(sel.Object) and sel.Object not in found:
                found.append(sel.Object)
    except Exception:
        pass
    return found


def marking_entries():
    """Right-click menu entries while a text is picked in the open sketch."""
    if not picked_texts():
        return []
    from . import ribbon_config as cfg

    return [
        cfg.item("Edit Text", "SciForge_EditText", "sk_text"),
        cfg.item("Explode Text", "SciForge_ExplodeText", "sk_text"),
    ]


# -- on / off (with the SciForge interface) ----------------------------------------------------
def enable():
    if _state["on"]:
        return
    _state["on"] = True
    if _font_missing not in text.ON_FONT_MISSING:
        text.ON_FONT_MISSING.append(_font_missing)
    try:
        _state["gui_observer"] = _GuiObserver()
        Gui.addDocumentObserver(_state["gui_observer"])
        _state["app_observer"] = _AppObserver()
        App.addDocumentObserver(_state["app_observer"])
        _state["selection_observer"] = _SelectionObserver()
        Gui.Selection.addObserver(_state["selection_observer"])
    except Exception as exc:
        warn("sketch text: %s" % exc)
    QtCore.QTimer.singleShot(0, _session_changed)


def disable():
    if not _state["on"]:
        return
    _state["on"] = False
    try:
        text.ON_FONT_MISSING.remove(_font_missing)
    except ValueError:
        pass
    layer = _state["layer"]
    _state["layer"] = None
    if layer is not None:
        layer.remove()
    for key, remover in (
        ("gui_observer", Gui.removeDocumentObserver),
        ("app_observer", App.removeDocumentObserver),
        ("selection_observer", Gui.Selection.removeObserver),
    ):
        observer = _state[key]
        _state[key] = None
        if observer is not None:
            try:
                remover(observer)
            except Exception:
                pass


COMMANDS = {
    "SciForge_SketchText": TextCommand,
    "SciForge_FaceText": FaceTextCommand,
    "SciForge_EditText": EditTextCommand,
    "SciForge_ExplodeText": ExplodeTextCommand,
}
