# SPDX-License-Identifier: LGPL-2.1-or-later
"""Selection like Fusion on the 3D view: box selection (window / crossing, freeform, paint),
Select Other on a long press, selection filters and priorities, Select Through, the
Fusion modifier keys. The rules and maths are in selection_core.py (no Qt, unit tested).

How it is built (SciForge's own code; Fusion's behaviour, see parity/selection.md):

* A Qt event filter on each 3D view's drawing area sees the left button before FreeCAD
  (like orbit_ui.py for the middle button). The press goes on to FreeCAD and to SciForge's
  handles untouched. When the mouse then moves more than a few pixels with the button
  down, SciForge draws its own box (a see-through widget over the view) and swallows the
  moves and the release: FreeCAD, which selects on the release, never selects anything
  for a drag. The box's contents are worked out from the model's geometry projected to
  the screen and selected through Gui.Selection, so every dialog's selection observer
  gets them as picks (and every dialog's selection gate still applies).
* A press that stays put for about a second opens the Select Other list (FreeCAD's own
  long-press "Clarify Selection" menu is turned off while SciForge is on): everything
  under the pointer, front to back; hovering a row shows it on the model.
* The selection filters are a FreeCAD selection gate, so a filtered kind does not even
  light up under the mouse. A dialog that installs its own gate gets it combined with the
  filters (Gui.Selection.addSelectionGate / removeSelectionGate are wrapped while SciForge
  is on), as Fusion's filters also apply inside commands.
* Shift adds (FreeCAD's own Shift does nothing: a Shift click is handed on as a Ctrl
  click, except on something already selected, which Fusion keeps). Ctrl toggles, as in
  FreeCAD. With the Body priority, a click on a face selects the whole body.
* Esc with no command open clears the selection (Fusion); keys 1 / 2 / 3 choose the mode.
"""

import math
import time

import FreeCAD as App
import FreeCADGui as Gui

from . import log, selection_core as core, warn
from .compat import QtCore, QtGui, QtWidgets

PARAMS = "User parameter:BaseApp/Preferences/Mod/SciForge"
KEY_MODE = "SelectionMode"
KEY_OFF = "SelectionFiltersOff"
KEY_THROUGH = "SelectThrough"
VIEW_PARAMS = "User parameter:BaseApp/Preferences/View"
BAND_NAME = "SciForgeSelectionBand"
MENU_NAME = "SciForgeSelectOther"
LEFT = QtCore.Qt.LeftButton
SHIFT = QtCore.Qt.ShiftModifier
CTRL = QtCore.Qt.ControlModifier
TELL_GAP_S = 2.0  # the "filtered out" note at most this often

_state = {
    "on": False,
    "filter": None,
    "widgets": [],
    "area": None,
    "filters": core.Filters(),
    "mode": core.DEFAULT_MODE,
    "gate": None,  # our FilterGate while it is the installed gate
    "inner": None,  # a dialog's own gate, combined with the filters
    "orig_add": None,
    "orig_remove": None,
    "menu": None,
    "told": 0.0,
    "last": None,  # what the last box or Select Other did (tests, Diagnostics)
}


# -- preferences ------------------------------------------------------------------------------


def _params():
    return App.ParamGet(PARAMS)


def load():
    """The remembered mode, filters and Select Through (a fresh install: Fusion's
    defaults)."""
    try:
        params = _params()
        _state["mode"] = params.GetString(KEY_MODE, core.DEFAULT_MODE)
        if _state["mode"] not in core.MODES:
            _state["mode"] = core.DEFAULT_MODE
        _state["filters"] = core.Filters.decode(
            params.GetString(KEY_OFF, ""), params.GetBool(KEY_THROUGH, core.DEFAULT_SELECT_THROUGH)
        )
    except Exception as exc:
        warn("selection settings: %s" % exc)
        _state["mode"], _state["filters"] = core.DEFAULT_MODE, core.Filters()


def _save():
    try:
        params = _params()
        params.SetString(KEY_MODE, _state["mode"])
        params.SetString(KEY_OFF, _state["filters"].encode())
        params.SetBool(KEY_THROUGH, _state["filters"].select_through)
    except Exception as exc:
        warn("selection settings: %s" % exc)


def reset():
    """Fusion's defaults again: window selection, every filter on, Select Through off.

    The tests call it before each scenario: the choices are remembered between sessions,
    and one scenario's Paint Selection or filter must not change how the next one picks."""
    try:
        _state["mode"] = core.DEFAULT_MODE
        _state["filters"] = core.Filters()
        _filters_changed()
    except Exception as exc:
        warn("selection reset: %s" % exc)


def mode():
    return _state["mode"]


def set_mode(name):
    if name not in core.MODES:
        warn("selection mode %r unknown" % (name,))
        return
    _state["mode"] = name
    _save()
    log("selection: %s" % core.MODE_LABELS[name].lower())


def is_window():
    return mode() == "window"


def is_freeform():
    return mode() == "freeform"


def is_paint():
    return mode() == "paint"


def filters():
    """The live Filters (change them through set_filter / toggle_filter / set_priority)."""
    return _state["filters"]


def filter_on(kind):
    return filters().allows(kind)


def set_filter(kind, on):
    filters().set(kind, on)
    _filters_changed()
    log("selection filter %s: %s" % (core.LABELS.get(kind, kind), "on" if on else "off"))


def toggle_filter(kind):
    set_filter(kind, not filter_on(kind))


def select_through():
    return filters().select_through


def set_select_through(on):
    filters().select_through = bool(on)
    _save()
    log("select through: %s" % ("on" if on else "off"))


def priority():
    return filters().priority()


def set_priority(name):
    """Fusion's Selection Priority entry: the one kind on; the active one again: all on."""
    filters().apply_priority(name)
    _filters_changed()
    now = priority()
    log(
        "selection priority: %s"
        % (core.PRIORITY_LABELS[now].lower() if now else "off (every filter on)")
    )


def _filters_changed():
    _save()
    _refresh_gate()
    try:
        Gui.Selection.clearPreselection()  # a highlight of a now-filtered kind goes
    except Exception:
        pass


def bodies_on():
    return filter_on("bodies")


def faces_on():
    return filter_on("faces")


def edges_on():
    return filter_on("edges")


def vertices_on():
    return filter_on("vertices")


def sketch_curves_on():
    return filter_on("sketch_curves")


def sketch_points_on():
    return filter_on("sketch_points")


def work_geometry_on():
    return filter_on("work_geometry")


def is_body_priority():
    return priority() == "body"


def is_face_priority():
    return priority() == "face"


def is_edge_priority():
    return priority() == "edge"


def is_select_through():
    return select_through()


def last():
    """What the last box, paint stroke or Select Other did: {"kind", "mode", "plan",
    "picked": [(object name, element)], ...} (tests, Diagnostics)."""
    return _state["last"]


# -- the selection gate (filters on hover and click) ---------------------------------------------


def _in_body(obj):
    try:
        if obj.TypeId == core.BODY_TYPE:
            return True
        parent = obj.getParentGeoFeatureGroup()
        return parent is not None and parent.TypeId == core.BODY_TYPE
    except Exception:
        return False


def _resolve(obj, sub):
    """(leaf object, element) of a gate question or a pick: FreeCAD names the top object
    (a Body) and a path ("Pad.Face6")."""
    leaf, short = obj, sub or ""
    if "." in short:
        path, short = short.rsplit(".", 1)
        try:
            inner = obj.getSubObject(path + ".", retType=1)
        except Exception:
            inner = None
        if inner is not None:
            leaf = inner
    return leaf, short


def kind_of_pick(obj, sub):
    """The filter kind of (object, element), or None when it is not filtered."""
    try:
        leaf, short = _resolve(obj, sub)
        if leaf is None:
            return None
        return core.kind_of(leaf.TypeId, short, _in_body(leaf))
    except Exception:
        return None


class FilterGate:
    """Refuses the kinds the selection filters have off. Whole objects picked anywhere
    but in the 3D view (the browser, the timeline) are never refused: Fusion's filters
    are about the canvas."""

    def allow(self, doc, obj, sub):
        try:
            if not _state["on"] or obj is None:
                return True
            if not sub:
                return True
            kind = kind_of_pick(obj, sub)
            return filters().allows(kind)
        except Exception:
            return True


class _Combined:
    """A dialog's own gate and the selection filters together."""

    def __init__(self, inner):
        self.inner = inner
        self.filters = FilterGate()

    def allow(self, doc, obj, sub):
        try:
            if not self.inner.allow(doc, obj, sub):
                return False
        except Exception:
            return False
        return self.filters.allow(doc, obj, sub)


def _has_allow(gate):
    return gate is not None and callable(getattr(gate, "allow", None))


def _add_gate(gate, *args, **kwargs):
    """Gui.Selection.addSelectionGate while SciForge is on: the dialog's gate is combined
    with the filters."""
    original = _state["orig_add"]
    _state["gate"] = None
    if _state["on"] and _has_allow(gate):
        _state["inner"] = gate
        return original(_Combined(gate), *args, **kwargs)
    _state["inner"] = None
    return original(gate, *args, **kwargs)


def _remove_gate(*args, **kwargs):
    """Gui.Selection.removeSelectionGate while SciForge is on: the filters come back."""
    original = _state["orig_remove"]
    _state["inner"] = None
    result = original(*args, **kwargs)
    _state["gate"] = None
    if _state["on"]:
        _refresh_gate()
    return result


def _patch_gate_api():
    if _state["orig_add"] is not None:
        return
    try:
        _state["orig_add"] = Gui.Selection.addSelectionGate
        _state["orig_remove"] = Gui.Selection.removeSelectionGate
        Gui.Selection.addSelectionGate = _add_gate
        Gui.Selection.removeSelectionGate = _remove_gate
    except Exception as exc:
        _state["orig_add"] = _state["orig_remove"] = None
        warn("selection filters cannot follow dialogs: %s" % exc)


def _unpatch_gate_api():
    try:
        if _state["orig_add"] is not None:
            Gui.Selection.addSelectionGate = _state["orig_add"]
        if _state["orig_remove"] is not None:
            Gui.Selection.removeSelectionGate = _state["orig_remove"]
    except Exception as exc:
        warn("selection filters: %s" % exc)
    _state["orig_add"] = _state["orig_remove"] = None


def _refresh_gate():
    """Our own gate is installed exactly when the filters restrict something and no
    dialog has a gate of its own (the combined gate reads the live filters)."""
    if not _state["on"] or _state["inner"] is not None:
        return
    add, remove = _state["orig_add"], _state["orig_remove"]
    if add is None or remove is None:
        return
    try:
        if filters().is_restrictive():
            if _state["gate"] is None:
                gate = FilterGate()
                add(gate)
                _state["gate"] = gate
        elif _state["gate"] is not None:
            _state["gate"] = None
            remove()
    except Exception as exc:
        warn("selection filters: %s" % exc)


# -- the view, the pointer and what is under it --------------------------------------------------


def _view_for(gl):
    from .orbit_ui import _view_for as view_for

    return view_for(gl)


def _coin_pixel(gl, pos):
    """Qt widget pixel -> Coin pixel (origin bottom-left, device pixels)."""
    ratio = gl.devicePixelRatioF()
    return pos.x() * ratio, (gl.height() - pos.y()) * ratio


def _info_at(view, gl, pos, radius=None):
    x, y = _coin_pixel(gl, pos)
    try:
        if radius is None:
            return view.getObjectInfo((int(round(x)), int(round(y))))
        return view.getObjectInfo((int(round(x)), int(round(y))), float(radius))
    except Exception:
        return None


def _infos_at(view, gl, pos, radius):
    x, y = _coin_pixel(gl, pos)
    try:
        found = view.getObjectsInfo((int(round(x)), int(round(y))), float(radius))
    except Exception:
        found = None
    return list(found or [])


def _pick_target(info):
    """(document name, object name, sub name) to select for a pick dictionary of
    getObjectInfo: the Body with "Pad.Face6" when the element belongs to a body."""
    parent = info.get("ParentObject")
    if parent is not None and info.get("SubName"):
        return info["Document"], parent.Name, info["SubName"]
    return info["Document"], info["Object"], info.get("Component", "")


def _pick_object(info):
    """The object a pick dictionary names (the feature, not the body), or None."""
    try:
        return App.getDocument(info["Document"]).getObject(info["Object"])
    except Exception:
        return None


def _kind_of_info(info):
    obj = _pick_object(info)
    if obj is None:
        return None
    return core.kind_of(obj.TypeId, info.get("Component", ""), _in_body(obj))


def _body_of_info(info):
    parent = info.get("ParentObject")
    if parent is not None and getattr(parent, "TypeId", "") == core.BODY_TYPE:
        return parent
    obj = _pick_object(info)
    if obj is not None and obj.TypeId == core.BODY_TYPE:
        return obj
    return None


def _in_dialog():
    """A command is open (not the Sketcher's own task panel)."""
    try:
        from . import marking_menu

        return marking_menu._dialog_open()
    except Exception:
        try:
            return bool(Gui.Control.activeDialog())
        except Exception:
            return False


def _in_edit():
    """Something is in FreeCAD's edit mode (a sketch, a datum, a transform): FreeCAD or
    the Sketcher handles the mouse then, not SciForge's selection."""
    try:
        gdoc = Gui.ActiveDocument
        if gdoc is not None and gdoc.getInEdit() is not None:
            return True
        from . import sketch_mode

        return sketch_mode.sketch_edited_anywhere()
    except Exception:
        return False


def _grabbed(view):
    """A Coin dragger (an arrow handle) holds the mouse, or one of SciForge's own handles
    was pressed and is being dragged (Move's triad, the Insert Mesh manipulator, Scale's
    arrows, Revolve's angle handle...: handles3d.dragging), or was just used: the drag is
    theirs, not a box, and a long press on it is not Select Other."""
    try:
        from . import handles3d

        if handles3d.dragging() or handles3d.just_used():
            return True
    except Exception:
        pass
    try:
        from pivy import coin  # noqa: F401  (the event manager needs pivy loaded)

        action = view.getViewer().getSoEventManager().getHandleEventAction()
        return action.getGrabber() is not None
    except Exception:
        return False


HANDLE_MARGIN = 10.0  # pixels around a handle's drawn width that still count as the handle


def _handle_under(gl, pos):
    """One of the open dialog's drag handles (an arrow, an angle disc, a point handle) is
    under widget pixel `pos`: a press there is the start of its drag, never of a box.
    Decided at the press from the handles' own screen extents (every handle carries a
    value box that records where the handle is drawn, taskui.BoxCarrier): a dialog may
    replace its arrow while the drag runs (the preview recomputes), and then nothing
    holds the event grab any more although the person is still dragging; a Coin pick from
    Python was not dependable either."""
    try:
        from . import arrow_box_core, taskui

        point = (float(pos.x()), float(pos.y()))

        def near(pixels):
            if pixels is None:
                return False
            tail, tip, radius = pixels
            return (
                arrow_box_core._segment_point(tail, tip, point) <= max(radius, 0.0) + HANDLE_MARGIN
            )

        panel = taskui.current()
        boxes = getattr(getattr(panel, "value_boxes", None), "boxes", None) if panel else None
        for box in list((boxes or {}).values()):
            try:
                if near(box.handle_pixels):
                    return True
            except RuntimeError:
                continue
        # A handle without a value box (Draft's angle disc...) is a handle all the same.
        for handle in taskui.live_handles():
            if near(taskui.handle_pixels(handle, gl)):
                return True
    except Exception as exc:
        warn("selection: %s" % exc)
    return False


def _tell(msg):
    now = time.time()
    if now - _state["told"] < TELL_GAP_S:
        return
    _state["told"] = now
    try:
        from . import commands

        commands.tell(msg)
    except Exception:
        log(msg)


# -- the box over the view ------------------------------------------------------------------------


def _colour(rgba):
    return QtGui.QColor.fromRgbF(*rgba)


class RubberBand(QtWidgets.QWidget):
    """The window (solid, blue) or crossing (dashed, green) box drawn over the 3D view
    while the left button is down. A child of the view's drawing area, never in the way
    of the mouse."""

    def __init__(self, gl):
        super().__init__(gl)
        self.setObjectName(BAND_NAME)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.points = []  # Qt widget pixels: 2 for a rectangle, more for a lasso
        self.crossing = False
        self.lasso = False
        self.hide()

    def start(self, pos):
        self.points = [QtCore.QPointF(pos)]
        self.crossing = False
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.rect())
        self.raise_()
        self.show()

    def follow(self, pos, crossing, lasso):
        self.crossing = bool(crossing)
        self.lasso = bool(lasso)
        if lasso:
            self.points.append(QtCore.QPointF(pos))
        else:
            self.points = self.points[:1] + [QtCore.QPointF(pos)]
        self.update()

    def stop(self):
        self.hide()
        self.points = []

    def shape(self):
        """The polygon as plain (x, y) widget pixels (what gets tested against the model)."""
        if not self.points:
            return []
        if self.lasso:
            pts = [(p.x(), p.y()) for p in self.points]
            return core.simplify_lasso(pts)
        a, b = self.points[0], self.points[-1]
        return core.rect_polygon(a.x(), a.y(), b.x(), b.y())

    def paintEvent(self, event):
        try:
            pts = self.shape()
            if len(pts) < 2:
                return
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            line = core.CROSSING_LINE if self.crossing else core.WINDOW_LINE
            fill = core.CROSSING_FILL if self.crossing else core.WINDOW_FILL
            pen = QtGui.QPen(_colour(line), 1.5)
            if self.crossing:
                pen.setDashPattern(list(core.CROSSING_DASH))
            painter.setPen(pen)
            painter.setBrush(QtGui.QBrush(_colour(fill)))
            polygon = QtGui.QPolygonF([QtCore.QPointF(x, y) for x, y in pts])
            painter.drawPolygon(polygon)
        except Exception as exc:
            warn("selection box: %s" % exc)


def band_of(gl):
    """The box widget of a view's drawing area, made the first time it is needed."""
    band = gl.findChild(QtWidgets.QWidget, BAND_NAME)
    if band is None:
        band = RubberBand(gl)
    return band


# -- what a box takes -----------------------------------------------------------------------------


class _Element:
    """One thing a box can select: how to select it and where it is on the screen."""

    __slots__ = (
        "doc",
        "obj",
        "sub",
        "feature",
        "short",
        "kind",
        "points",
        "segments",
        "outline",
        "samples",
    )

    def __init__(self, doc, obj, sub, feature, short, kind):
        self.doc, self.obj, self.sub = doc, obj, sub
        self.feature, self.short, self.kind = feature, short, kind
        self.points, self.segments, self.outline, self.samples = [], [], None, []

    def key(self):
        return (self.feature.Name if self.feature is not None else self.obj, self.short)

    def is_selected(self):
        try:
            if self.short:
                return bool(Gui.Selection.isSelected(self.feature, self.short))
            return bool(Gui.Selection.isSelected(self.feature))
        except Exception:
            return False


def _project(view):
    """A function 3D point -> (x, y) Coin pixels for this view."""

    def to_screen(p):
        x, y = view.getPointOnViewport(App.Vector(p))
        return float(x), float(y)

    return to_screen


def _edge_points(edge):
    try:
        if edge.Curve.TypeId == "Part::GeomLine":
            return [edge.Vertexes[0].Point, edge.Vertexes[-1].Point]
        return edge.discretize(Number=core.FACE_SAMPLES)
    except Exception:
        try:
            return [v.Point for v in edge.Vertexes]
        except Exception:
            return []


def _polyline(points):
    return [(points[i], points[i + 1]) for i in range(len(points) - 1)]


def _face_geometry(face, to_screen):
    """points, segments, outline (the outer wire) of a face on screen, and sample points
    on the face for the visibility test."""
    points, segments, outline = [], [], []
    try:
        wires = face.Wires
        outer = face.OuterWire
    except Exception:
        wires, outer = [], None
    for wire in wires:
        try:
            edges = wire.OrderedEdges
        except Exception:
            edges = wire.Edges
        for edge in edges:
            screen = [to_screen(p) for p in _edge_points(edge)]
            points.extend(screen)
            segments.extend(_polyline(screen))
            if outer is not None and wire.isSame(outer):
                outline.extend(screen)
    samples = []
    try:
        com = face.CenterOfMass
        if face.isInside(com, 1e-6, True):
            samples.append(com)
    except Exception:
        pass
    try:
        u0, u1, v0, v1 = face.ParameterRange
        mid = face.valueAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)
        if face.isInside(mid, 1e-6, True):
            samples.append(mid)
    except Exception:
        pass
    if not samples:
        try:
            samples.append(face.Vertexes[0].Point)
        except Exception:
            pass
    return points, segments, outline, samples


def _candidates(doc):
    """[(object to select by, feature with the shape, shape, selection path prefix)] of the
    visible things a box can take: bodies (their Tip's shape), loose Part features,
    sketches that are not being edited."""
    found = []
    try:
        objects = list(doc.Objects)
    except Exception:
        return found
    for obj in objects:
        try:
            if obj.TypeId == core.BODY_TYPE:
                tip = obj.Tip
                if tip is None or not obj.ViewObject.Visibility:
                    continue
                shape = obj.Shape
                if shape.isNull():
                    continue
                found.append((obj, tip, shape, tip.Name + "."))
            elif obj.TypeId == core.SKETCH_TYPE:
                if not obj.ViewObject.Visibility or _is_edited(obj):
                    continue
                shape = obj.Shape
                if shape.isNull():
                    continue
                found.append((obj, obj, shape, ""))
            elif obj.TypeId.startswith("Part::") and "Shape" in obj.PropertiesList:
                if obj.getParentGeoFeatureGroup() is not None or not obj.ViewObject.Visibility:
                    continue
                if obj.TypeId in core.WORK_TYPES or getattr(obj, "SciForgeType", ""):
                    continue
                shape = obj.Shape
                if shape.isNull() or not (shape.Faces or shape.Edges):
                    continue
                found.append((obj, obj, shape, ""))
        except Exception:
            continue
    return found


def _is_edited(obj):
    try:
        edit = Gui.getDocument(obj.Document.Name).getInEdit()
        return edit is not None and edit.Object is not None and edit.Object.Name == obj.Name
    except Exception:
        return False


def _elements_in(view, gl, polygon_qt, crossing, filters_):
    """The elements a box takes: those of the kinds the filters allow that the box
    encloses (window) or touches (crossing), and, without Select Through, only the ones
    the view actually shows."""
    doc = App.ActiveDocument
    if doc is None or len(polygon_qt) < 3:
        return []
    ratio = gl.devicePixelRatioF()
    height = gl.height()
    poly = [(x * ratio, (height - y) * ratio) for x, y in polygon_qt]
    box_mode = "crossing" if crossing else "window"
    kinds = core.box_kinds(filters_)
    to_screen = _project(view)
    found = []
    started = time.perf_counter()
    for obj, feature, shape, prefix in _candidates(doc):
        is_sketch = obj.TypeId == core.SKETCH_TYPE
        doc_name = obj.Document.Name
        if is_sketch:
            if "sketch_curves" not in kinds:
                continue
            for i, edge in enumerate(shape.Edges, start=1):
                el = _Element(doc_name, obj.Name, "Edge%d" % i, obj, "Edge%d" % i, "sketch_curves")
                el.points = [to_screen(p) for p in _edge_points(edge)]
                el.segments = _polyline(el.points)
                el.samples = [edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2.0)]
                found.append(el)
            continue
        if "bodies" in kinds:
            el = _Element(doc_name, obj.Name, "", obj, "", "bodies")
            el.points = [to_screen(v.Point) for v in shape.Vertexes]
            faces = []
            for face in shape.Faces:
                pts, segs, outline, samples = _face_geometry(face, to_screen)
                faces.append((pts, segs, outline))
                el.segments.extend(segs)
                el.samples.extend(samples)
            el.outline = faces  # every face's outline: the box inside any of them touches
            found.append(el)
            continue
        if "faces" in kinds:
            for i, face in enumerate(shape.Faces, start=1):
                short = "Face%d" % i
                el = _Element(doc_name, obj.Name, prefix + short, feature, short, "faces")
                el.points, el.segments, el.outline, el.samples = _face_geometry(face, to_screen)
                found.append(el)
        if "edges" in kinds:
            for i, edge in enumerate(shape.Edges, start=1):
                short = "Edge%d" % i
                el = _Element(doc_name, obj.Name, prefix + short, feature, short, "edges")
                el.points = [to_screen(p) for p in _edge_points(edge)]
                el.segments = _polyline(el.points)
                try:
                    el.samples = [edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2.0)]
                except Exception:
                    el.samples = [edge.Vertexes[0].Point]
                found.append(el)
        if "vertices" in kinds:
            for i, vertex in enumerate(shape.Vertexes, start=1):
                short = "Vertex%d" % i
                el = _Element(doc_name, obj.Name, prefix + short, feature, short, "vertices")
                el.points = [to_screen(vertex.Point)]
                el.samples = [vertex.Point]
                found.append(el)
    taken = []
    for el in found:
        if core.quick_reject(el.points, poly):
            continue
        if el.kind == "bodies":
            if box_mode == "window":
                hit = core.element_selected(el.points, el.segments, poly, "window")
            else:
                hit = any(
                    core.element_selected(pts, segs, poly, "crossing", outline)
                    for pts, segs, outline in el.outline
                )
        else:
            hit = core.element_selected(el.points, el.segments, poly, box_mode, el.outline)
        if hit:
            taken.append(el)
    if not filters_.select_through and taken:
        taken = [el for el in taken if _is_visible(view, gl, el, to_screen)]
    spent = time.perf_counter() - started
    if spent > 0.5:
        log("box selection took %.1f s on %d elements" % (spent, len(found)))
    return taken


def _pixel_mm(view, gl):
    """How many model units one screen pixel spans (at the view's focal plane)."""
    try:
        x, y = int(gl.width() / 2), int(gl.height() / 2)
        a = App.Vector(view.getPoint(x, y))
        b = App.Vector(view.getPoint(x + 1, y))
        return max(0.0, (a - b).Length)
    except Exception:
        return 0.0


def _is_visible(view, gl, el, to_screen):
    """Without Select Through: the element shows at one of its sample points (the pick
    there lands on it, not on something in front of it).

    "In front" is measured along the line of sight: a sketch curve lying on a face is
    seen, though the pick at its pixel may land on the face a pixel's width beside the
    curve's own point (graphics drivers break that depth tie differently)."""
    try:
        diag = el.feature.Shape.BoundBox.DiagonalLength
    except Exception:
        diag = 100.0
    tol = core.depth_tolerance(diag)
    try:
        look = App.Vector(view.getViewDirection())
        look = App.Vector(look).normalize() if look.Length > 1e-12 else None
    except Exception:
        look = None
    slack = 2.0 * _pixel_mm(view, gl)
    ratio = gl.devicePixelRatioF()
    for point in el.samples:
        x, y = to_screen(point)
        if not (0 <= x < gl.width() * ratio and 0 <= y < gl.height() * ratio):
            continue
        try:
            info = view.getObjectInfo((int(round(x)), int(round(y))))
        except Exception:
            info = None
        if not info:
            continue
        if info.get("Object") == el.feature.Name and info.get("Component") == el.short:
            return True
        picked = App.Vector(info["x"], info["y"], info["z"])
        offset = picked - App.Vector(point)
        if offset.Length <= tol:
            return True
        if look is not None and slack > 0:
            depth = offset.dot(look)  # below zero: what the pick hit is nearer the eye
            beside = (offset - look * depth).Length
            if beside <= slack and depth >= -(tol + slack):
                return True
    return False


def _apply(elements, plan, doc_name=None):
    """Select the elements as the plan says; returns [(object name, element)] selected."""
    picked = []
    if plan == "replace":
        try:
            if doc_name:
                Gui.Selection.clearSelection(doc_name)
            else:
                Gui.Selection.clearSelection()
        except Exception:
            pass
    for el in elements:
        try:
            selected = el.is_selected()
            if plan == "toggle" and selected:
                Gui.Selection.removeSelection(el.doc, el.obj, el.sub)
            elif not selected:
                Gui.Selection.addSelection(el.doc, el.obj, el.sub)
                picked.append(el.key())
            else:
                picked.append(el.key())
        except Exception as exc:
            warn("selection: %s %s: %s" % (el.obj, el.sub, exc))
    return picked


# -- Select Other ---------------------------------------------------------------------------------


class _Row:
    __slots__ = ("doc", "obj", "sub", "feature", "short", "kind", "label", "icon")

    def __init__(self, doc, obj, sub, feature, short, kind, label, icon):
        self.doc, self.obj, self.sub = doc, obj, sub
        self.feature, self.short, self.kind = feature, short, kind
        self.label, self.icon = label, icon


ROW_ICONS = {
    "faces": "select_face",
    "edges": "select_edge",
    "vertices": "select_vertex",
    "bodies": "select_body",
    "sketch_curves": "select_sketch",
    "sketch_points": "select_sketch",
    "work_geometry": "select_work",
}


def _rows_under(view, gl, pos):
    """Everything under the pointer the filters allow, nearest first, then the bodies they
    belong to (Fusion's Parents tab, as rows)."""
    try:
        radius = float(view.getViewer().getPickRadius()) * 2.0
    except Exception:
        radius = 10.0
    infos = _infos_at(view, gl, pos, radius)
    if not infos:
        return []
    cam = None
    try:
        cam_node = view.getCameraNode()
        cam = tuple(cam_node.position.getValue().getValue())
        direction = tuple(view.getViewDirection())
    except Exception:
        direction = None
    items = []
    for info in infos:
        obj = _pick_object(info)
        if obj is None:
            continue
        short = info.get("Component", "")
        kind = core.kind_of(obj.TypeId, short, _in_body(obj))
        if not filters().allows(kind):
            continue
        doc_name, obj_name, sub = _pick_target(info)
        owner = _body_of_info(info)
        owner_label = owner.Label if owner is not None else obj.Label
        label = core.row_label(short, owner_label)
        if short.startswith("InternalFace"):
            label = "Profile  ·  %s" % obj.Label
        row = _Row(doc_name, obj_name, sub, obj, short, kind, label, ROW_ICONS.get(kind, "select"))
        items.append(((obj.Name, short), (row, (info["x"], info["y"], info["z"]))))
    items = core.dedupe(items)
    items = _with_adjacent_faces(items)
    payloads = [payload for _, payload in items]
    if cam is not None and direction is not None:
        rows = core.order_front_to_back(payloads, cam, direction)
    else:
        rows = [row for row, _ in payloads]
    parents = []
    if filters().allows("bodies"):
        seen = set()
        for info in infos:
            body = _body_of_info(info)
            if body is None or body.Name in seen:
                continue
            seen.add(body.Name)
            parents.append(
                _Row(
                    body.Document.Name, body.Name, "", body, "", "bodies", body.Label, "select_body"
                )
            )
    return rows + ([None] + parents if parents else [])


def _with_adjacent_faces(items):
    """An edge under the pointer brings the faces it bounds into the list (the pointer is
    on them too; a ray through the very edge may miss one of them)."""
    extra = []
    keys = {key for key, _ in items}
    for (obj_name, short), (row, point) in items:
        if row.kind != "edges" or not filters().allows("faces"):
            continue
        try:
            shape = row.feature.Shape
            edge = shape.getElement(short)
            faces = shape.ancestorsOfType(edge, type(shape.Faces[0]))
            for face in faces:
                for i, candidate in enumerate(shape.Faces, start=1):
                    if candidate.isSame(face):
                        face_short = "Face%d" % i
                        break
                else:
                    continue
                if (obj_name, face_short) in keys:
                    continue
                keys.add((obj_name, face_short))
                sub = row.sub[: -len(short)] + face_short if row.sub.endswith(short) else face_short
                owner = row.label.split("\u00b7")[-1].strip() if "\u00b7" in row.label else ""
                face_row = _Row(
                    row.doc,
                    row.obj,
                    sub,
                    row.feature,
                    face_short,
                    "faces",
                    core.row_label(face_short, owner),
                    ROW_ICONS["faces"],
                )
                extra.append(((obj_name, face_short), (face_row, point)))
        except Exception as exc:
            warn("Select Other: %s" % exc)
    return items + extra


class SelectOtherMenu(QtWidgets.QMenu):
    """Fusion's Select Other list: what is under the pointer, front to back. Hovering a
    row shows it on the model; a click selects it (with the modifiers of the press);
    Esc or a click elsewhere closes it."""

    def __init__(self, parent, rows, plan):
        super().__init__(parent)
        from . import ui_icon

        self.setObjectName(MENU_NAME)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)
        self.plan = plan
        self.rows = []
        self.chosen = None
        for row in rows:
            if row is None:
                self.addSeparator()
                continue
            action = self.addAction(ui_icon(row.icon), row.label)
            action.setData(len(self.rows))
            self.rows.append(row)
        self.hovered.connect(self._hover)
        self.triggered.connect(self._pick)
        self.aboutToHide.connect(self._hidden)

    def _row(self, action):
        try:
            index = action.data()
            return self.rows[index] if index is not None else None
        except Exception:
            return None

    def _hover(self, action):
        row = self._row(action)
        if row is None:
            return
        try:
            obj = App.getDocument(row.doc).getObject(row.obj)
            Gui.Selection.setPreselection(obj, row.sub)
        except Exception as exc:
            warn("Select Other: %s" % exc)

    def _pick(self, action):
        row = self._row(action)
        if row is None:
            return
        self.chosen = row
        QtCore.QTimer.singleShot(0, lambda: _select_row(row, self.plan))

    def _hidden(self):
        try:
            Gui.Selection.clearPreselection()
        except Exception:
            pass

    def leaveEvent(self, event):
        try:
            Gui.Selection.clearPreselection()
        except Exception:
            pass
        super().leaveEvent(event)


def _select_row(row, plan):
    try:
        el = _Element(row.doc, row.obj, row.sub, row.feature, row.short, row.kind)
        picked = _apply([el], plan, row.doc)
        _state["last"] = {"kind": "other", "plan": plan, "picked": picked, "row": row.label}
        log("Select Other: %s" % row.label)
    except Exception as exc:
        warn("Select Other: %s" % exc)


def select_other_menu():
    """The open Select Other list (tests), or None."""
    menu = _state["menu"]
    try:
        if menu is not None and menu.isVisible():
            return menu
    except RuntimeError:
        pass
    return None


def _close_menu():
    menu, _state["menu"] = _state["menu"], None
    if menu is not None:
        try:
            menu.close()
            menu.deleteLater()
        except RuntimeError:
            pass


def show_select_other(gl, pos, global_pos, plan):
    """Open the Select Other list for widget pixel `pos` of the drawing area `gl`. False
    when nothing is under the pointer."""
    view = _view_for(gl)
    if view is None:
        return False
    rows = _rows_under(view, gl, pos)
    if not rows:
        return False
    _close_menu()
    menu = SelectOtherMenu(gl, rows, plan)
    _state["menu"] = menu
    _state["last"] = {"kind": "other-list", "rows": [r.label for r in rows if r is not None]}
    menu.popup(QtCore.QPoint(global_pos.x() + 2, global_pos.y() + 2))
    return True


# -- the mouse and the keys on the view -----------------------------------------------------------


class _Press:
    """One left-button press being followed."""

    def __init__(self, event, gl):
        self.pos = QtCore.QPointF(event.position())
        self.global_pos = QtCore.QPointF(event.globalPosition())
        self.modifiers = event.modifiers()
        self.time = time.time()
        self.gl = gl
        self.on_handle = False  # the press landed on a drag handle: its drag, not a box
        self.boxing = False  # a box or paint stroke is under way
        self.cancelled = False  # Esc: the release does nothing
        self.listed = False  # the Select Other list opened on this press
        self.mode = mode()
        self.painted = set()
        self.cleared = False  # paint: the selection was replaced at the first stroke
        self.in_dialog = _in_dialog()
        self.dragging = None  # joints_drag: the press moves a component (Component Drag)


def _distance(a, b):
    return math.hypot(a.x() - b.x(), a.y() - b.y())


_MOUSE = (
    QtCore.QEvent.MouseButtonPress,
    QtCore.QEvent.MouseButtonDblClick,
    QtCore.QEvent.MouseMove,
    QtCore.QEvent.MouseButtonRelease,
)


def _is_gl(obj):
    try:
        return obj.metaObject().className() == "QOpenGLWidget"
    except Exception:
        return False


class _ViewFilter(QtCore.QObject):
    def __init__(self):
        super().__init__()
        self.press = None
        self.busy = False
        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._long_press)
        self.last_escape = 0.0

    # -- dispatch ------------------------------------------------------------------------
    def eventFilter(self, obj, event):
        try:
            if self.busy or not _state["on"]:
                return False
            kind = event.type()
            if kind == QtCore.QEvent.ShortcutOverride:
                # FreeCAD's own 1 / 2 / 3 (front, top, right view) would take the key as a
                # shortcut before the view ever sees it; Fusion's 1 / 2 / 3 pick the
                # selection mode. Accepted here, the key comes back as a KeyPress below.
                if self._mode_key(event) is not None:
                    event.accept()
                    return True
                return False
            if kind == QtCore.QEvent.KeyPress:
                return self._key(obj, event)
            if kind in _MOUSE and not _is_gl(obj):
                return False  # an event Quarter ignored, handed on to the viewer widget
            if kind == QtCore.QEvent.MouseButtonPress:
                return self._pressed(obj, event)
            if kind == QtCore.QEvent.MouseButtonDblClick:
                if event.button() == LEFT:
                    self._drop()
                return False
            if kind == QtCore.QEvent.MouseMove:
                return self._moved(obj, event)
            if kind == QtCore.QEvent.MouseButtonRelease:
                return self._released(obj, event)
        except Exception as exc:
            self._drop()
            warn("selection: %s" % exc)
        return False

    def _drop(self):
        press, self.press = self.press, None
        self.timer.stop()
        if press is not None and press.dragging is not None:
            _safely(press.dragging.finish)  # a component drag keeps where it got to
        if press is not None and press.boxing and press.mode != "paint":
            try:
                band_of(press.gl).stop()
            except RuntimeError:
                pass

    # -- press ---------------------------------------------------------------------------
    def _pressed(self, obj, event):
        if event.button() != LEFT:
            if self.press is not None:
                self._drop()  # another button joined in: not a box any more
            return False
        try:
            from . import orbit_ui

            if orbit_ui.is_arming():
                return False  # Set Orbit Center waits for this click
        except Exception:
            pass
        if _in_edit() or App.ActiveDocument is None:
            return False
        self.press = _Press(event, obj)
        view = _view_for(obj)
        try:
            from . import handles3d

            just_used = handles3d.just_used()
        except Exception:
            just_used = False
        if view is None or just_used or _handle_under(obj, self.press.pos):
            self.press.on_handle = True
            return False  # the handle's drag: no box, no Select Other
        try:
            seconds = App.ParamGet(VIEW_PARAMS).GetFloat("LongPressTimeout", core.LONG_PRESS_S)
        except Exception:
            seconds = core.LONG_PRESS_S
        self.timer.start(int(max(0.2, seconds) * 1000))
        return False  # FreeCAD and the handles get the press as always

    # -- move ----------------------------------------------------------------------------
    def _moved(self, obj, event):
        press = self.press
        if press is None:
            if event.buttons() == QtCore.Qt.NoButton:
                self._hover(obj, event)
            return False
        if not (event.buttons() & LEFT):
            # A move without the button: the button went up somewhere else, or a move Qt
            # made up (a widget shown under the pointer, a tooltip): the real state decides.
            try:
                held = bool(QtWidgets.QApplication.mouseButtons() & LEFT)
            except Exception:
                held = False
            if held:
                # a made-up move: nothing changes
                return press.boxing or press.listed or press.dragging is not None
            self._drop()
            return False
        if press.listed:
            return True  # the list is open: the move is not a drag
        pos = QtCore.QPointF(event.position())
        if press.cancelled:
            return True
        if press.dragging is not None:
            press.dragging.follow(pos)  # Component Drag (joints_drag)
            return True
        if not press.boxing:
            if press.on_handle:
                self.press = None  # a handle's drag: FreeCAD's and the handle's business
                return False
            if _distance(pos, press.pos) <= core.CLICK_SLOP:
                return False
            self.timer.stop()
            view = _view_for(obj)
            if view is None or _in_edit() or _grabbed(view):
                self.press = None
                return False
            # Fusion's Component Drag: a plain drag that starts on a component moves it
            # (outside commands; Shift / Ctrl still draw a box). joints_drag.py does it.
            drag = self._component_drag(obj, view, press)
            if drag is not None:
                press.dragging = drag
                drag.follow(pos)
                return True
            press.boxing = True
            if press.mode != "paint":
                band_of(obj).start(press.pos)
        if press.mode == "paint":
            self._paint(obj, press, pos)
        else:
            crossing = core.box_mode(press.pos.x(), pos.x()) == "crossing"
            band_of(obj).follow(pos, crossing, press.mode == "freeform")
        return True

    def _component_drag(self, gl, view, press):
        if press.in_dialog or press.mode == "paint" or press.modifiers & (SHIFT | CTRL):
            return None
        try:
            from . import joints_drag

            return joints_drag.start(gl, view, press.pos)
        except Exception as exc:
            warn("selection: %s" % exc)
            return None

    def _hover(self, gl, event):
        """With the Body priority, the whole body lights up under the mouse (FreeCAD's own
        highlight of the face is refused by the filter gate)."""
        if not core.only_bodies(filters()) or _in_edit():
            return
        view = _view_for(gl)
        if view is None:
            return
        info = _info_at(view, gl, QtCore.QPointF(event.position()))
        body = _body_of_info(info) if info else None
        # After FreeCAD's own handling of this move (it clears the highlight when the
        # filter gate refuses the face under the mouse).
        QtCore.QTimer.singleShot(0, lambda: _safely(_preselect_body, body))

    def _paint(self, obj, press, pos):
        view = _view_for(obj)
        if view is None:
            return
        info = _info_at(view, obj, pos)
        if not info:
            return
        kind = _kind_of_info(info)
        box_kinds = core.box_kinds(filters())
        if "bodies" in box_kinds:
            body = _body_of_info(info)
            if body is None:
                return
            el = _Element(body.Document.Name, body.Name, "", body, "", "bodies")
        else:
            if kind not in box_kinds:
                return
            doc_name, obj_name, sub = _pick_target(info)
            feature = _pick_object(info)
            el = _Element(doc_name, obj_name, sub, feature, info.get("Component", ""), kind)
        if el.key() in press.painted:
            return
        press.painted.add(el.key())
        plan = core.plan(
            bool(press.modifiers & SHIFT), bool(press.modifiers & CTRL), press.in_dialog
        )
        if plan == "replace":
            plan = "add" if press.cleared else "replace"
            press.cleared = True

        def go():
            picked = _apply([el], plan, el.doc)
            previous = (
                _state["last"] if _state["last"] and _state["last"].get("kind") == "paint" else None
            )
            if previous is not None and previous.get("press") is press:
                previous["picked"].extend(picked)
            else:
                _state["last"] = {
                    "kind": "paint",
                    "plan": plan,
                    "picked": list(picked),
                    "press": press,
                }

        QtCore.QTimer.singleShot(0, lambda: _safely(go))

    # -- release -------------------------------------------------------------------------
    def _released(self, obj, event):
        if event.button() != LEFT:
            return False
        press, self.press = self.press, None
        self.timer.stop()
        if press is None:
            return False
        if press.on_handle:
            return False
        if press.dragging is not None:
            _safely(press.dragging.finish)  # Component Drag: kept, one undo step
            return True  # FreeCAD must not select on this release
        if press.cancelled or press.listed:
            return True  # FreeCAD must not select on this release
        if press.boxing:
            if press.mode == "paint":
                log("paint selection: %d picked" % len(press.painted))
                return True
            band = band_of(obj)
            polygon = band.shape()
            crossing = band.crossing
            band.stop()
            QtCore.QTimer.singleShot(
                0, lambda: _safely(self._finish_box, obj, press, polygon, crossing)
            )
            return True
        return self._click(obj, event, press)

    def _finish_box(self, gl, press, polygon, crossing):
        view = _view_for(gl)
        if view is None or App.ActiveDocument is None:
            return
        plan = core.plan(
            bool(press.modifiers & SHIFT), bool(press.modifiers & CTRL), press.in_dialog
        )
        elements = _elements_in(view, gl, polygon, crossing, filters())
        picked = _apply(elements, plan, App.ActiveDocument.Name)
        _state["last"] = {
            "kind": "box",
            "mode": "crossing" if crossing else "window",
            "shape": press.mode,
            "plan": plan,
            "found": [el.key() for el in elements],
            "picked": picked,
        }
        log(
            "%s selection (%s): %d found, %s"
            % ("crossing" if crossing else "window", press.mode, len(elements), plan)
        )

    def _click(self, gl, event, press):
        """A click (no drag, no long press). FreeCAD selects on this release; SciForge
        steps in only for Fusion's Shift, for the Body priority and to say why a filtered
        element did not take."""
        view = _view_for(gl)
        if view is None:
            return False
        shift = bool(event.modifiers() & SHIFT)
        ctrl = bool(event.modifiers() & CTRL)
        pos = QtCore.QPointF(event.position())
        info = _info_at(view, gl, pos)
        if core.only_bodies(filters()):
            body = _body_of_info(info) if info else None
            if body is None:
                if info:
                    return False  # not a body's element: FreeCAD's own click
                if shift or ctrl:
                    return True  # empty space with a modifier: nothing changes (Fusion)
                return False  # empty space: FreeCAD clears the selection
            el = _Element(body.Document.Name, body.Name, "", body, "", "bodies")
            plan = core.click_plan(shift, ctrl, press.in_dialog, el.is_selected())
            if plan != "keep":
                QtCore.QTimer.singleShot(0, lambda: _safely(_apply, [el], plan, el.doc))
            return True
        if info:
            kind = _kind_of_info(info)
            if kind is not None and not filters().allows(kind):
                _tell(core.filter_message(kind))
                return False
        if shift and not ctrl:
            if not info:
                return True  # Shift on empty space keeps the selection
            doc_name, obj_name, sub = _pick_target(info)
            feature = _pick_object(info)
            el = _Element(doc_name, obj_name, sub, feature, info.get("Component", ""), None)
            if el.is_selected():
                return True  # Fusion's Shift never removes
            self._forward_release(gl, event, CTRL)  # FreeCAD's Ctrl adds
            return True
        return False

    def _forward_release(self, gl, event, modifiers):
        copy = QtGui.QMouseEvent(
            QtCore.QEvent.MouseButtonRelease,
            QtCore.QPointF(event.position()),
            QtCore.QPointF(event.globalPosition()),
            LEFT,
            event.buttons(),
            modifiers,
        )
        self.busy = True
        try:
            QtWidgets.QApplication.sendEvent(gl, copy)
        finally:
            self.busy = False

    # -- the long press ------------------------------------------------------------------
    def _long_press(self):
        try:
            press = self.press
            if press is None or press.boxing or press.cancelled or press.listed:
                return
            gl = press.gl
            view = _view_for(gl)
            if view is None or _in_edit() or _grabbed(view):
                return
            plan = core.click_plan(
                bool(press.modifiers & SHIFT), bool(press.modifiers & CTRL), press.in_dialog, False
            )
            if show_select_other(gl, press.pos, press.global_pos.toPoint(), plan):
                press.listed = True
        except Exception as exc:
            warn("Select Other: %s" % exc)

    # -- keys ----------------------------------------------------------------------------
    def _key(self, obj, event):
        key = event.key()
        if key == QtCore.Qt.Key_Escape:
            if event.isAutoRepeat():
                return False
            press = self.press
            if press is not None and press.dragging is not None and not press.cancelled:
                press.cancelled = True
                _safely(press.dragging.cancel)  # Component Drag: everything goes back
                return True
            if press is not None and press.boxing:
                press.cancelled = True
                if press.mode != "paint":
                    band_of(press.gl).stop()
                log("selection box cancelled")
                return True
            if _in_dialog() or _in_edit():
                return False
            now = time.time()
            if now - self.last_escape < 0.05:
                return False  # the same key seen on the view and its drawing area
            self.last_escape = now
            try:
                if Gui.Selection.hasSelection():
                    Gui.Selection.clearSelection()
                    log("selection cleared (Esc)")
            except Exception:
                pass
            return False
        mode_name = self._mode_key(event)
        if mode_name is not None:
            set_mode(mode_name)
            _tell(core.MODE_LABELS[mode_name])
            return True
        return False

    def _mode_key(self, event):
        """The selection mode a key event asks for (Fusion's 1 / 2 / 3), or None. Not
        while a command or a sketch is open: digits typed there are values."""
        try:
            text = event.text()
            if (
                text not in core.MODE_KEYS
                or event.modifiers() not in (QtCore.Qt.NoModifier, QtCore.Qt.KeypadModifier)
                or event.isAutoRepeat()
            ):
                return None
            if _in_dialog() or _in_edit():
                return None
            return core.MODE_KEYS[text]
        except Exception:
            return None


def _safely(step, *args):
    try:
        step(*args)
    except Exception as exc:
        warn("selection: %s" % exc)


def _preselect_body(body):
    try:
        if body is None:
            pre = Gui.Selection.getPreselection()
            if pre.ObjectName and not pre.SubElementNames:
                Gui.Selection.clearPreselection()
        else:
            Gui.Selection.setPreselection(body, "")
    except Exception:
        pass  # the body went (deleted, undone) between the move and this moment


def active_press():
    """The press being followed (tests): None, or an object with .boxing / .listed."""
    filt = _state["filter"]
    return filt.press if filt is not None else None


# -- turning it on and off ---------------------------------------------------------------------


def _install():
    if _state["filter"] is None:
        return
    from .orbit_ui import _is_valid, _same, _view_widgets

    try:
        widgets = _view_widgets()
    except RuntimeError:
        return
    _state["widgets"] = [w for w in _state["widgets"] if _is_valid(w)]
    for widget in widgets:
        try:
            if not any(_same(widget, w) for w in _state["widgets"]):
                widget.installEventFilter(_state["filter"])
                _state["widgets"].append(widget)
        except RuntimeError:
            pass
    # An open sketch keeps its own filter in front (marking_menu does the same).
    try:
        from . import sketch_mode

        session = sketch_mode.current()
        if session is not None and session.gl is not None and session.filter is not None:
            session.gl.installEventFilter(session.filter)
    except Exception:
        pass


def enable():
    """SciForge's interface turned on: the mouse filter on every 3D view, the selection
    filters as FreeCAD's gate, the remembered mode."""
    _state["on"] = True
    load()
    _patch_gate_api()
    _refresh_gate()
    if _state["filter"] is None:
        _state["filter"] = _ViewFilter()
    _install()
    try:
        area = Gui.getMainWindow().findChild(QtWidgets.QMdiArea)
        if area is not None and _state["area"] is None:
            area.subWindowActivated.connect(lambda *_: _state["on"] and _install())
            _state["area"] = area
    except Exception as exc:
        warn("selection: %s" % exc)


def disable():
    """SciForge's interface turned off: FreeCAD's own selection again."""
    _state["on"] = False
    _close_menu()
    filt, _state["filter"] = _state["filter"], None
    if filt is not None:
        filt._drop()
    for widget in _state["widgets"]:
        try:
            if filt is not None:
                widget.removeEventFilter(filt)
            band = widget.findChild(QtWidgets.QWidget, BAND_NAME)
            if band is not None:
                band.stop()
        except RuntimeError:
            pass
    _state["widgets"] = []
    try:
        if _state["gate"] is not None and _state["orig_remove"] is not None:
            _state["gate"] = None
            _state["orig_remove"]()
    except Exception as exc:
        warn("selection filters: %s" % exc)
    _state["inner"] = None
    _unpatch_gate_api()


# -- commands -----------------------------------------------------------------------------------


class _Command:
    title = ""
    tip = ""
    icon = ""

    def GetResources(self):
        from . import ui_icon_path

        res = {"MenuText": self.title, "ToolTip": self.tip}
        if self.icon:
            res["Pixmap"] = ui_icon_path(self.icon)
        return res

    def IsActive(self):
        return True

    def Activated(self):
        try:
            self.run()
        except Exception as exc:
            warn("%s: %s" % (self.title, exc))


class SelectCommand(_Command):
    title = "Select"
    tip = (
        "Click to select; drag a box from left to right for what is fully inside, from "
        "right to left for what it touches; hold the button on the model for Select Other"
    )
    icon = "select"

    def run(self):
        from . import commands

        commands.finish_open_dialog()  # Fusion: the Select tool ends the running command


class _ModeCommand(_Command):
    mode = "window"

    def run(self):
        set_mode(self.mode)


class SelectWindowCommand(_ModeCommand):
    title = "Window Selection"
    tip = "Drag a box: left to right takes what is fully inside, right to left what it touches (1)"
    icon = "select_window"
    mode = "window"


class SelectFreeformCommand(_ModeCommand):
    title = "Freeform Selection"
    tip = "Draw a free shape around things; the drag direction works like the box (2)"
    icon = "select_freeform"
    mode = "freeform"


class SelectPaintCommand(_ModeCommand):
    title = "Paint Selection"
    tip = "Drag over things to select everything the pointer passes (3)"
    icon = "select_paint"
    mode = "paint"


class SelectThroughCommand(_Command):
    title = "Select Through"
    tip = "A box also takes what is hidden behind other faces (off: only what the view shows)"
    icon = "select_through"

    def run(self):
        set_select_through(not select_through())


class _FilterCommand(_Command):
    kind = "bodies"

    def run(self):
        toggle_filter(self.kind)


class FilterBodiesCommand(_FilterCommand):
    title = "Bodies"
    tip = "Whole bodies can be selected"
    icon = "select_body"
    kind = "bodies"


class FilterFacesCommand(_FilterCommand):
    title = "Body Faces"
    tip = "Faces of bodies can be selected"
    icon = "select_face"
    kind = "faces"


class FilterEdgesCommand(_FilterCommand):
    title = "Body Edges"
    tip = "Edges of bodies can be selected"
    icon = "select_edge"
    kind = "edges"


class FilterVerticesCommand(_FilterCommand):
    title = "Body Vertices"
    tip = "Corner points of bodies can be selected"
    icon = "select_vertex"
    kind = "vertices"


class FilterSketchCurvesCommand(_FilterCommand):
    title = "Sketch Curves"
    tip = "Lines and curves of sketches can be selected"
    icon = "select_sketch"
    kind = "sketch_curves"


class FilterSketchPointsCommand(_FilterCommand):
    title = "Sketch Points"
    tip = "Points of sketches can be selected"
    icon = "select_sketch"
    kind = "sketch_points"


class FilterWorkGeometryCommand(_FilterCommand):
    title = "Work Geometry"
    tip = "Construction planes, axes and points can be selected"
    icon = "select_work"
    kind = "work_geometry"


class _PriorityCommand(_Command):
    name = "body"

    def run(self):
        set_priority(self.name)


class PriorityBodyCommand(_PriorityCommand):
    title = "Select Body Priority"
    tip = "Only whole bodies: a click on a face selects its body (again: every filter on)"
    icon = "select_body"
    name = "body"


class PriorityFaceCommand(_PriorityCommand):
    title = "Select Face Priority"
    tip = "Only faces of bodies (again: every filter on)"
    icon = "select_face"
    name = "face"


class PriorityEdgeCommand(_PriorityCommand):
    title = "Select Edge Priority"
    tip = "Only edges of bodies (again: every filter on)"
    icon = "select_edge"
    name = "edge"


class SelectOtherCommand(_Command):
    title = "Select Other"
    tip = "A list of everything under the pointer, front to back (or hold the left button)"
    icon = "select_other"

    def IsActive(self):
        try:
            return Gui.ActiveDocument is not None and Gui.ActiveDocument.ActiveView is not None
        except Exception:
            return False

    def run(self):
        from .orbit_ui import _active_view

        view = _active_view()
        if view is None:
            return
        gl = view.graphicsView().viewport()
        global_pos = QtGui.QCursor.pos()
        pos = gl.mapFromGlobal(global_pos)
        if not gl.rect().contains(pos):
            pos = gl.rect().center()
            global_pos = gl.mapToGlobal(pos)
        if not show_select_other(
            gl, QtCore.QPointF(pos), global_pos, "add" if _in_dialog() else "replace"
        ):
            _tell("Nothing under the pointer to choose from.")


COMMANDS = {
    "SciForge_Select": SelectCommand,
    "SciForge_SelectWindow": SelectWindowCommand,
    "SciForge_SelectFreeform": SelectFreeformCommand,
    "SciForge_SelectPaint": SelectPaintCommand,
    "SciForge_SelectThrough": SelectThroughCommand,
    "SciForge_SelectFilterBodies": FilterBodiesCommand,
    "SciForge_SelectFilterFaces": FilterFacesCommand,
    "SciForge_SelectFilterEdges": FilterEdgesCommand,
    "SciForge_SelectFilterVertices": FilterVerticesCommand,
    "SciForge_SelectFilterSketchCurves": FilterSketchCurvesCommand,
    "SciForge_SelectFilterSketchPoints": FilterSketchPointsCommand,
    "SciForge_SelectFilterWorkGeometry": FilterWorkGeometryCommand,
    "SciForge_SelectPriorityBody": PriorityBodyCommand,
    "SciForge_SelectPriorityFace": PriorityFaceCommand,
    "SciForge_SelectPriorityEdge": PriorityEdgeCommand,
    "SciForge_SelectOther": SelectOtherCommand,
}
