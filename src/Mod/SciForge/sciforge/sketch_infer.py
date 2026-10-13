# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's sketch inference on top of FreeCAD's own drawing tools, in Python.

What it does while a sketch tool draws:

- Ctrl held: no snapping and no automatic constraints at all (Fusion's meaning; in
  FreeCAD Ctrl turns on 5-degree angle steps). For each mouse event FreeCAD handles
  while Ctrl is down, SciForge switches FreeCAD's snapping ("Snap") and the sketch's
  "Autoconstraints" off and puts them back right after. A click with Ctrl that
  finishes a shape turns the automatic constraints back on as soon as FreeCAD has
  added the shape, so the constraints of points placed earlier (the start of the
  line, where it joins the previous one) are kept; only the Ctrl point stays free.
- Alignment guides, in every drawing tool (line, rectangles, circles, arcs, polygons,
  slot): the last 3 points the pointer hovered, and the points of the shapes drawn
  since the tool started, are remembered. When the point being placed lines up with
  one of them (straight above/below or level, within a few pixels) a dashed guide is
  drawn from that point to the pointer and the point snaps onto it. After the click
  the alignment becomes a constraint (Vertical/Horizontal between the two points;
  Fusion's behaviour on click is unconfirmed, parameter GuideConstraint). A point
  that is not a vertex of the shape (a circle's rim point) is only snapped.
- Line and slot, perpendicular: a line (a slot's centre line) starting from, or
  ending on, another line at about 90 degrees snaps to exactly 90 degrees, a small
  right-angle mark shows at the corner, and a Perpendicular constraint is added after
  the click.
- Line and slot, level/upright: within 4 degrees (FreeCAD alone: 2) the line snaps
  level or upright with a small level / upright mark beside it while drawing; the
  Horizontal/Vertical constraint is added after the click (FreeCAD adds it itself
  within its own 2 degrees).
- Line, parallel to a hovered line: off by default (Fusion unconfirmed), parameter
  Parallel.
- Line, tangent arc (Fusion's Line tool): press on the start of the line being drawn
  (the end of the last one) and drag: an arc tangent to the last curve follows the
  pointer; release places its end, and the chain goes on from there. A plain click
  without a drag still places a straight line's end. The arc, its tangency and the
  constraints of its end are one undo step ("Tangent arc").

How: FreeCAD decides the snapped point in C++ from the mouse position. The sketch's
view filter (sketch_mode._ViewFilter) gives every mouse event to Inference.mouse()
first. When the point should go somewhere else, the event is swallowed and a copy is
sent to the 3D view with the position moved to the screen pixel nearest to the wanted
point, so FreeCAD's own tool draws the preview and places the point there (its grid
snap is off for that one event; the free coordinate is grid-snapped here instead). A
pixel is coarse (about 0.1-0.3 mm), so after the click the new point is moved exactly
onto the guide and the constraint is added, in one undo step glued to FreeCAD's
("Inferred Constraints"). Which tool draws comes from the last command SciForge ran
(recent.py); what it has placed so far is read from FreeCAD's preview (the edit curve)
and counted from the clicks.

Never lets an exception out of an event handler or timer (warn() and carry on).
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import log, warn
from . import sketch_infer_core as core
from .compat import QtCore, QtGui, QtWidgets

PARAMS = "User parameter:BaseApp/Preferences/Mod/SciForge/SketchInference"
SNAP = "User parameter:BaseApp/Preferences/Mod/Sketcher/Snap"
SKETCHER_GENERAL = "User parameter:BaseApp/Preferences/Mod/Sketcher/General"
VIEW = "User parameter:BaseApp/Preferences/View"
INFER_STEP = "Inferred Constraints"  # the same as sketch_mode.INFER_STEP (glued in undo)
ARC_STEP = "Tangent arc"  # the arc, its tangency and its end's constraints: one step
GUIDE_COLOR = "#7ee0ff"  # SciForge's own: a light cyan, apart from the blue curves
LINE_COMMANDS = ("SciForge_SketchLine", "Sketcher_CreateLine")

# name: (kind, default), stored under PARAMS (FreeCAD's parameter editor; no dialog yet).
DEFAULTS = {
    "Enabled": ("Bool", True),  # guides, perpendicular, wider level/upright snap
    "CtrlFree": ("Bool", True),  # Ctrl = no snaps, no automatic constraints
    "GuideConstraint": ("Bool", True),  # a click on a guide adds the alignment constraint
    "GuidePixels": ("Float", 6.0),
    "MaxHovered": ("Int", 3),  # Fusion keeps the last 3 hovered points
    "HVDegrees": ("Float", 4.0),  # FreeCAD alone: 2
    "PerpendicularDegrees": ("Float", 4.0),
    "Parallel": ("Bool", False),  # Fusion: unconfirmed
    "ParallelDegrees": ("Float", 3.0),
    "TangentArc": ("Bool", True),  # press-and-drag from the line's start makes an arc
    "DragPixels": ("Float", 6.0),  # a press that moves less is a click
}
SNAP_OFF_MARK = "SnapSwitchedOff"  # set while FreeCAD's Snap is off for a Ctrl event

KINDS = (
    QtCore.QEvent.MouseMove,
    QtCore.QEvent.MouseButtonPress,
    QtCore.QEvent.MouseButtonRelease,
    QtCore.QEvent.MouseButtonDblClick,
)
PRESSES = (QtCore.QEvent.MouseButtonPress, QtCore.QEvent.MouseButtonDblClick)
SWALLOW = "swallow"  # _plan: the event is ours (the tangent-arc drag), FreeCAD never sees it
VERTEX_POSITIONS = {
    "Part::GeomPoint": (1,),
    "Part::GeomLineSegment": (1, 2),
    "Part::GeomCircle": (3,),
    "Part::GeomEllipse": (3,),
    "Part::GeomArcOfCircle": (1, 2, 3),
    "Part::GeomArcOfEllipse": (1, 2, 3),
    "Part::GeomArcOfHyperbola": (1, 2, 3),
    "Part::GeomArcOfParabola": (1, 2, 3),
    "Part::GeomBSplineCurve": (1, 2),
}


def setting(name):
    kind, default = DEFAULTS[name]
    try:
        return getattr(App.ParamGet(PARAMS), "Get" + kind)(name, default)
    except Exception:
        return default


def repair_snap():
    """If FreeCAD stopped while Ctrl had snapping switched off (a crash in that very
    moment), snapping would stay off for good: put it back."""
    try:
        group = App.ParamGet(PARAMS)
        if group.GetBool(SNAP_OFF_MARK, False):
            App.ParamGet(SNAP).SetBool("Snap", True)
            group.RemBool(SNAP_OFF_MARK)
            log("sketch: snapping switched back on (left off by an earlier session)")
    except Exception as exc:
        warn("sketch snapping: %s" % exc)


def _rgb(hex_color):
    value = int(hex_color.lstrip("#"), 16)
    return ((value >> 16) / 255.0, ((value >> 8) & 0xFF) / 255.0, (value & 0xFF) / 255.0)


def _xy(vector):
    return (vector.x, vector.y)


def vertex_point(geo, pos):
    """The point `pos` (1 start, 2 end, 3 centre) of a geometry, or None."""
    try:
        if pos == 3:
            return _xy(geo.Center)
        if geo.TypeId == "Part::GeomPoint":
            return (geo.X, geo.Y)
        return _xy(geo.StartPoint if pos == 1 else geo.EndPoint)
    except Exception:
        return None


class Inference:
    """One per sketch session (sketch_mode.SketchSession.infer)."""

    def __init__(self, session):
        self.session = session
        self.busy = False  # our own copy of an event is being handled
        self.acquired = []  # vertex keys (geo, pos), newest last
        self.hovered_lines = []  # geometry indices of hovered lines (parallel)
        self.tool_points = []  # vertex keys of the shapes this tool run drew
        self.tool_on = False
        self.kind = None  # the shape the tool draws ("line", "rect"...), core.TOOLS
        self.tool_base = session.sketch.GeometryCount  # curves before this tool run
        self.placed = []  # points of the clicks since the shape began (about, see _plan)
        self.current = {"points": []}  # (Result, px) per click of the shape being drawn
        self.pending = []  # records of finished shapes, applied from a timer
        self.seen = session.sketch.GeometryCount
        self.last = None  # last Result (for tests and diagnostics)
        self.last_px = None
        self.last_step = None  # which click `last` was computed for
        self.last_start = None  # the line's first point as last previewed
        self._cache = None
        self._flip = False  # Autoconstraints back on at the next commit (Ctrl click)
        self._applying = False
        self._queued = False
        self.overlay = Overlay(session)
        self.arc = TangentArc(self)

    # -- bookkeeping -------------------------------------------------------------------
    def invalidate(self):
        """The sketch's geometry changed: rebuild the point/curve lists when needed."""
        self._cache = None

    def reset(self):
        """The tool stopped or started afresh (Esc, another tool, L again): forget
        everything of this command; the next mouse event begins a new tool run (its
        curves count from now)."""
        self.tool_on = False
        try:
            self.tool_base = self.session.sketch.GeometryCount
        except Exception:
            pass
        self.acquired = []
        self.hovered_lines = []
        self.tool_points = []
        self.placed = []
        self.current = {"points": []}
        self.last = None
        self.last_step = None
        self.last_start = None
        self.arc.reset()
        self.overlay.clear()

    def close(self):
        self.reset()
        self.overlay.remove()

    def leave(self):
        """The pointer left the 3D view: no guide or mark stays behind (an arc being
        dragged keeps the button held, so no Leave comes while it runs)."""
        try:
            self.overlay.clear()
            self.last = None
        except Exception as exc:
            warn("sketch inference: %s" % exc)

    # -- the mouse ---------------------------------------------------------------------
    def mouse(self, obj, event):
        """Called first for every mouse event of the 3D view while the sketch is open.
        True when the event was replaced by a copy, or taken by the tangent-arc drag
        (the caller then swallows it)."""
        if self.busy or event.type() not in KINDS:
            return False
        try:
            plan = self._plan(obj, event)
        except Exception as exc:
            warn("sketch inference: %s" % exc)
            self.overlay.clear()
            return False
        if plan is None:
            return False
        if plan == SWALLOW:
            return True
        pos, free, nogrid, result, px = plan
        try:
            self._forward(obj, event, pos, free, nogrid)
        except Exception as exc:
            warn("sketch inference: %s" % exc)
        if result is not None and event.type() == QtCore.QEvent.MouseMove:
            try:
                self._check_preview(result, px)
            except Exception as exc:
                warn("sketch inference: %s" % exc)
        return True

    def _plan(self, obj, event):
        """(position, free, nogrid, result, px) for the copy FreeCAD gets, SWALLOW for an
        event of ours, or None to leave the event alone."""
        session = self.session
        if session.closed or session.gl is None:
            return None
        kind = event.type()
        buttons = event.buttons()
        left = QtCore.Qt.LeftButton
        if kind == QtCore.QEvent.MouseMove:
            if buttons not in (QtCore.Qt.NoButton, left):
                self.overlay.clear()  # panning or orbiting
                return None
        elif event.button() != left:
            return None
        if not self._drawing():
            if self.tool_on:
                self.tool_on = False
                self.reset()
            return None
        recorded = self._tool()
        polylines = self._polylines() if recorded is not None else []
        tool = core.tool_kind(recorded, polylines)
        if tool != self.kind or (tool is not None and not self.tool_on):
            self.reset()
            self.tool_on = tool is not None
            self.kind = tool
            self.seen = self.tool_base = session.sketch.GeometryCount
        ctrl = bool(event.modifiers() & QtCore.Qt.ControlModifier)
        start = self._start_point(polylines)
        if start is not None:
            self.last_start = start
        elif not polylines and tool == "line" and self.last_start is not None:
            # with the pointer on the line's own start FreeCAD previews nothing (a line
            # of no length): the start is where it was at the last move. Only there:
            # anywhere else an empty preview means the tool waits for its first click
            view = _ViewMap(session, obj, event.position())
            if view.ok and core.dist(view.raw, self.last_start) <= _pick_pixels() * view.px:
                start = self.last_start
        if tool == "line" and self.arc.handle(obj, event, ctrl, start):
            return SWALLOW
        step = self._step(start) if tool is not None else None
        if ctrl and setting("CtrlFree"):
            self.overlay.clear()
            self.last = None
            if kind in PRESSES and tool is not None:
                view = _ViewMap(session, obj, event.position())
                self._remember_press(None, None, step, view if view.ok else None, True)
            return (event.position(), True, False, None, None)
        if tool is None or not setting("Enabled"):
            self.overlay.clear()
            return None
        if step is None:  # the tool asks for a size now (a radius, a width): no guides
            self.overlay.clear()
            self.last, self.last_step = None, None
            return None
        view = _ViewMap(session, obj, event.position())
        if not view.ok:
            return None
        result, grid = self._infer(view, start)
        self.last, self.last_px, self.last_step = result, view.px, step
        if kind in PRESSES:
            self._remember_press(result, view.px, step, view, False)
        if result is None:
            self.overlay.clear()
            return None
        pos = view.pixel_for(result.point)
        if pos is None:
            self.overlay.clear()
            return None
        self.overlay.show(result, view.px)
        nogrid = core.grid_off(result, grid, view.px)
        return (pos, False, nogrid, result, view.px)

    def _drawing(self):
        """A sketch tool is drawing (FreeCAD's drawing cursor is on the view)."""
        try:
            return self.session.gl.cursor().shape() != QtCore.Qt.ArrowCursor
        except Exception:
            return False

    def _tool(self):
        """The shape the running tool draws (core.TOOLS), or None for a tool the guides
        do not know (a point, an ellipse, a spline: Ctrl still works there)."""
        from . import recent

        last = recent.last()
        if last is not None:
            return core.TOOLS.get(last[0])
        return "line" if self.session.line.active else None

    def _polylines(self):
        """FreeCAD's preview of the shape being drawn (its edit curve) as polylines of
        sketch points. Looked up fresh every time: FreeCAD deletes its edit nodes when
        the sketch closes."""
        from .sketch_mode import find_node

        root = self.session.view.getSceneGraph()
        coords, _parent = find_node(root, "EditCurvesCoordinate")
        lineset, _parent = find_node(root, "EditCurveLineSet")
        if coords is None or lineset is None:
            return []
        points = [v.getValue() for v in coords.point.getValues(0)]
        counts = list(lineset.numVertices.getValues(0))
        out, i = [], 0
        for n in counts:
            if n > 0:  # an emptied preview keeps one entry of no points
                out.append([(float(p[0]), float(p[1])) for p in points[i : i + n]])
            i += n
        return out

    def _start_point(self, polylines=None):
        """The point the new direction starts from (a line's first point, a slot's first
        centre), exactly as FreeCAD previews it, or None (before the first click, or a
        shape without a direction)."""
        if self.kind not in core.DIRECTION:
            return None
        if polylines is None:
            polylines = self._polylines()
        return core.preview_anchor(self.kind, polylines)

    def _step(self, start):
        """Which click of the shape is being placed (0-based), or None when the tool
        asks for a size now. The line's state comes from its preview (`start`: FreeCAD
        refuses a zero-length second click, so counting clicks could drift); the others
        count their clicks since the shape began."""
        if self.kind == "line":
            return 0 if start is None else 1
        n = len(self.placed)
        return n if n < core.POINTS.get(self.kind, 0) else None

    def _check_preview(self, result, px):
        """Never show a guide or mark the shape does not follow: a value typed into
        FreeCAD's field puts the point elsewhere (the click then adds nothing either)."""
        polylines = self._polylines()
        if not polylines:
            return
        if self.kind in core.DIRECTION and result.start is not None:
            pointer = core.preview_pointer(self.kind, polylines, result.point)
            start = core.preview_anchor(self.kind, polylines)
            if pointer is None:
                return
            if start is None or core.exact_point(result, pointer, px, start) is None:
                self.overlay.clear()
                self.last = None
            return
        # the point must lie on the preview (curves are drawn in 50 straight pieces,
        # so a little slack: the pieces cut the corners)
        gap = min(core.curve_distance(result.point, ("poly", poly)) for poly in polylines)
        if gap > 3.0 * px:
            self.overlay.clear()
            self.last = None

    def _infer(self, view, start):
        verts, curves, lines, keyed = self._geometry()
        raw = view.raw
        pick = _pick_pixels()
        opt = core.Options(
            guide_px=setting("GuidePixels"),
            pick_px=pick,
            hv_deg=setting("HVDegrees"),
            perp_deg=setting("PerpendicularDegrees"),
            parallel=setting("Parallel"),
            parallel_deg=setting("ParallelDegrees"),
            grid=_grid_size(self.session),
        )
        # hovering a point acquires it (Fusion keeps the last 3), a line likewise
        keep = max(0, int(setting("MaxHovered")))
        hit = core.nearest_vertex(raw, verts, pick * view.px)
        if hit is not None:
            self.acquired = core.remember(self.acquired, hit[0], keep)
        line = core.nearest_line(raw, lines, pick * view.px)
        if line is not None:
            self.hovered_lines = core.remember(self.hovered_lines, line[0], keep)
        keys = list(self.tool_points) + [k for k in self.acquired if k not in self.tool_points]
        acquired = [(k, keyed[k]) for k in keys if k in keyed]
        by_geo = {geo: (geo, a, b) for geo, a, b in lines}
        parallel = [by_geo[g] for g in self.hovered_lines if g in by_geo]
        result = core.infer(
            raw, start, acquired, lines, verts, curves, view.px, opt, parallel, self.placed
        )
        return result, opt.grid

    def _geometry(self):
        """(vertices, curves, lines, {key: point}) of the sketch, rebuilt when it
        changed. Keys are FreeCAD's (geometry index, point position) pairs."""
        if self._cache is not None:
            return self._cache
        sketch = self.session.sketch
        verts = [((-1, 1), (0.0, 0.0))]  # the origin
        curves = [("line", (0.0, 0.0), (1.0, 0.0)), ("line", (0.0, 0.0), (0.0, 1.0))]
        lines = []
        for i, geo in enumerate(sketch.Geometry):
            try:
                construction = bool(sketch.getConstruction(i))
            except Exception:
                construction = False
            _add_geometry(verts, curves, lines, i, geo, construction)
        try:
            external = list(sketch.ExternalGeo)[2:]  # the first two are the axes
        except Exception:
            external = []
        for k, geo in enumerate(external):
            _add_geometry(verts, curves, lines, -3 - k, geo, False)
        keyed = dict(verts)
        self._cache = (verts, curves, lines, keyed)
        return self._cache

    def _remember_press(self, result, px, step, view, ctrl):
        """A click of the tool: the first one of a shape starts a new record, the next
        ones add to it (applied after FreeCAD has added the shape). The point FreeCAD
        gets is remembered (about: what it snaps to on a curve is not computed) so the
        shape's own points make no guides."""
        if self.kind is None:
            return
        if step == 0:
            self.current = {"points": []}
            self.placed = []
        if step is not None:
            self.current["points"].append((result, px))
        point = None
        if result is not None:
            point = result.point
        elif view is not None:
            point = view.raw
            if not ctrl:
                verts = self._geometry()[0]
                hit = core.nearest_vertex(view.raw, verts, _pick_pixels() * view.px)
                if hit is not None:
                    point = hit[1]
        if point is not None:
            self.placed.append(point)

    def _forward(self, obj, event, pos, free, nogrid):
        """Send FreeCAD a copy of the event at `pos`; with `free` (Ctrl) snapping and
        automatic constraints are off while FreeCAD handles it, with `nogrid` only the
        grid snap (the point is already where it should be)."""
        saved = {}
        sketch_vp = self.session.sketch.ViewObject
        snap = App.ParamGet(SNAP)
        viewer = None
        try:
            if free:
                if snap.GetBool("Snap", True):
                    App.ParamGet(PARAMS).SetBool(SNAP_OFF_MARK, True)
                    snap.SetBool("Snap", False)
                    saved["Snap"] = True
                # FreeCAD's click also jumps to a point marker within the pick radius
                # (ViewProviderSketch::mouseButtonPressed, before any snapping): with
                # a tiny radius nothing is picked, and nothing lights up either
                viewer = self.session.view.getViewer()
                saved["radius"] = viewer.getPickRadius()
                viewer.setPickRadius(0.01)
                if sketch_vp.Autoconstraints:
                    sketch_vp.Autoconstraints = False
                    saved["auto"] = True
                    # a click that finishes the shape: back on at FreeCAD's commit, so
                    # the earlier points keep their constraints (commit_signal)
                    self._flip = event.type() in PRESSES
            elif nogrid and snap.GetBool("SnapToGrid", False):
                snap.SetBool("SnapToGrid", False)
                saved["SnapToGrid"] = True
            global_pos = obj.mapToGlobal(pos)
            copy = QtGui.QMouseEvent(
                event.type(),
                pos,
                QtCore.QPointF(global_pos),
                event.button(),
                event.buttons(),
                event.modifiers(),
            )
            self.busy = True
            try:
                QtWidgets.QApplication.sendEvent(obj, copy)
            finally:
                self.busy = False
        finally:
            self._flip = False
            if viewer is not None and saved.get("radius"):
                viewer.setPickRadius(saved["radius"])
            if saved.get("Snap"):
                snap.SetBool("Snap", True)
                App.ParamGet(PARAMS).RemBool(SNAP_OFF_MARK)
            if saved.get("SnapToGrid"):
                snap.SetBool("SnapToGrid", True)
            if saved.get("auto") and not sketch_vp.Autoconstraints:
                sketch_vp.Autoconstraints = True

    # -- after a click -----------------------------------------------------------------
    def commit_signal(self, kind):
        """FreeCAD committed / undid something in the sketch (document signal: only
        flags and timers here, plus the Ctrl switch-back, which must happen right now)."""
        if kind in ("undo", "redo"):
            self.current = {"points": []}
            self.placed = []
            self.pending = []
            self.last_start = None
            QtCore.QTimer.singleShot(0, self._resync)
            QtCore.QTimer.singleShot(0, self.line_undone)
            return
        if kind != "commit":
            return
        if self._flip:
            self._flip = False
            try:
                self.session.sketch.ViewObject.Autoconstraints = True
            except Exception:
                pass
        if self._applying:
            return
        points = self.current["points"]
        wanted = core.POINTS.get(self.kind, 0)
        if self.tool_on and self.last is not None and 0 < len(points) < wanted:
            # no click for the last point: a shape finished with Enter after a typed
            # value takes what the pointer showed last (FreeCAD drops its own
            # level/upright then)
            if self.last_step == len(points):
                points.append((self.last, self.last_px))
        if any(r is not None for r, _px in points):
            self.pending.append(self.current)
        self.current = {"points": []}
        self.placed = []
        self.last_start = None  # the shape is done: the next one starts afresh
        if not self._queued:
            self._queued = True
            QtCore.QTimer.singleShot(0, self._apply)

    def _resync(self):
        """After undo/redo: count the sketch's curves again."""
        try:
            if not self.session.closed:
                self.seen = self.session.sketch.GeometryCount
                self.tool_points = [k for k in self.tool_points if k[0] < self.seen]
        except Exception as exc:
            warn("sketch inference: %s" % exc)

    def line_undone(self):
        """Undo or redo while the line tool is drawing: FreeCAD's tool keeps the sketch
        point it was started on (the end of a curve that may be gone now), and would
        join the next line to itself ("Both points are equal", the solver fails from
        then on). The tool is stopped and started again, then the chain goes on from
        the end of the newest curve this run drew, or waits for a click."""
        session = self.session
        try:
            if session.closed or not self._drawing() or self._tool() != "line":
                return
            from . import commands

            sketch = session.sketch
            count = sketch.GeometryCount
            Gui.runCommand("Sketcher_StopOperation")
            Gui.runCommand("Sketcher_CreateLine")
            self.seen = count
            self.last_start = None
            self.current = {"points": []}
            self.placed = []
            self.arc.reset()
            self.overlay.clear()
            line = session.line
            line.seen = count  # the chain counts from here too
            end = self._chain_end(sketch, count) if count > self.tool_base else None
            if end is not None and line._click_at(App.Vector(end[0], end[1], 0)):
                self.last_start = end
                log("sketch: line tool started again from the end of curve %d" % count)
            else:
                line.chain_start = None
                commands.tell("Line: click where to start.")
        except Exception as exc:
            warn("sketch inference: %s" % exc)

    def _chain_end(self, sketch, count):
        """The free end of the newest curve (the end the chain would go on from): a
        line's end; an arc's end that does not touch the curve before it."""
        geo = sketch.Geometry[count - 1]
        if geo.TypeId == "Part::GeomLineSegment":
            return _xy(geo.EndPoint)
        if geo.TypeId != "Part::GeomArcOfCircle":
            return None
        ends = [_xy(geo.StartPoint), _xy(geo.EndPoint)]
        if count >= 2:
            before = sketch.Geometry[count - 2]
            touched = [vertex_point(before, pos) for pos in VERTEX_POSITIONS.get(before.TypeId, ())]
            free = [e for e in ends if not any(p and core.dist(e, p) < 1e-6 for p in touched)]
            if len(free) == 1:
                return free[0]
        return ends[1]

    def _apply(self):
        self._queued = False
        session = self.session
        if session.closed:
            return
        try:
            sketch = session.sketch
            count = sketch.GeometryCount
            pending, self.pending = self.pending, []
            if count < self.seen:  # undone
                self.seen = count
                return
            new = list(range(self.seen, count))
            self.seen = count
            self._repair_self_joins(sketch)
            if not new:
                return
            geos = sketch.Geometry
            if self.tool_on:
                for i in new:
                    for pos in VERTEX_POSITIONS.get(geos[i].TypeId, ()):
                        self.tool_points.append((i, pos))
            if not pending:
                return
            self._apply_shape(new, geos, pending[-1])
        except Exception as exc:
            warn("sketch inference: %s" % exc)

    def _repair_self_joins(self, sketch):
        """A Coincident between two points of the same curve (FreeCAD's line tool after
        an undo joined a line's start to its own end: "Both points are equal") makes
        every solve fail: taken out, in a step glued to the one before."""
        bad = [
            i
            for i, c in enumerate(sketch.Constraints)
            if c.Type == "Coincident" and c.First == c.Second and c.First >= 0
        ]
        if not bad:
            return
        doc = self.session.doc
        self._applying = True
        doc.openTransaction(INFER_STEP)
        try:
            for i in reversed(bad):
                sketch.delConstraint(i)
            sketch.solve()
        except Exception:
            doc.abortTransaction()
            self._applying = False
            raise
        doc.commitTransaction()
        self._applying = False
        log(
            "sketch: removed %d constraint(s) joining a point of a curve to itself (curve %s)"
            % (len(bad), ", ".join(str(sketch.Constraints[i].First + 1) for i in bad[:1]))
        )

    def _apply_shape(self, new, geos, record):
        """Put the new shape's points exactly where the guides/inference said and add
        the constraints, in one undo step. Each clicked point is matched to the vertex
        of the new shape that FreeCAD placed there (a rectangle corner, a circle's
        centre...); a point that is no vertex (a circle's rim point) is left as the
        preview placed it."""
        import Sketcher

        sketch = self.session.sketch
        verts = []
        for i in new:
            for pos in VERTEX_POSITIONS.get(geos[i].TypeId, ()):
                point = vertex_point(geos[i], pos)
                if point is not None:
                    verts.append(((i, pos), point))
        moves, constraints = [], []
        start_exact = None  # the direction's start after its own exact move
        for step, (result, px) in enumerate(record["points"]):
            if result is None or not px:
                continue
            hit = core.nearest_vertex(result.point, verts, 1.5 * px)
            if hit is None:
                continue
            key, placed = hit
            directed = result.kind is not None or result.on_line
            start = None
            if directed:
                # the direction's start as the shape has it (the preview's start is
                # single precision: a millionth off, enough to nudge a joined line)
                start = start_exact
                if start is None and result.start is not None:
                    anchor = core.nearest_vertex(result.start, verts, 1.5 * px)
                    start = anchor[1] if anchor is not None else None
            target = core.exact_point(result, placed, px, start)
            if target is None:
                continue
            if core.dist(target, placed) > 1e-9:
                moves.append((key, target))
            if step == 0:
                start_exact = target
            for guide in result.guides:
                constraints.append(self._alignment(key, guide, new))
            if directed:
                line = self._direction_line(new, geos, result)
                if line is None:
                    continue
                if result.kind in (core.HORIZONTAL, core.VERTICAL):
                    name = "Horizontal" if result.kind == core.HORIZONTAL else "Vertical"
                    if not _has(sketch, name, line):
                        constraints.append(Sketcher.Constraint(name, line))
                elif result.kind == core.PERPENDICULAR and result.other is not None:
                    constraints.append(Sketcher.Constraint("Perpendicular", line, result.other))
                elif result.kind == core.PARALLEL and result.other is not None:
                    constraints.append(Sketcher.Constraint("Parallel", line, result.other))
        constraints = [c for c in constraints if c is not None]
        if not moves and not constraints:
            return
        # the curves our constraints refer to (a hovered line's point, the line a slot
        # stands on) stay put while the shape is made exact
        pinned = {c.Second for c in constraints if c.Second >= 0} | {
            c.First for c in constraints if c.First not in new and c.First >= 0
        }
        names = self._transaction(INFER_STEP, moves, constraints, pinned - set(new))
        if names:
            log(
                "sketch: %s added to %s (inferred)"
                % (", ".join(names), ", ".join("curve %d" % (i + 1) for i in new))
            )

    def _direction_line(self, new, geos, result):
        """The line of the new shape that runs along the inferred direction (the line
        itself; a slot's first side). The shape is where the pixel put it, so a few
        degrees of slack."""
        d = result.direction
        for i in new:
            if geos[i].TypeId != "Part::GeomLineSegment":
                continue
            if d is None:
                return i
            u = core.unit(core.sub(_xy(geos[i].EndPoint), _xy(geos[i].StartPoint)))
            if u is not None and abs(u[0] * d[1] - u[1] * d[0]) < 0.1:
                return i
        return None

    def _transaction(self, name, moves, constraints, pinned=()):
        """Moves and constraints in one undo step; constraints that turn out redundant
        or conflicting are dropped. The `pinned` curves are held still meanwhile (a
        Block constraint for the duration): a move solves the sketch, and a free line
        the shape touches would otherwise drift by a micron or two as the solver
        spreads the half-pixel correction. Returns the names of the constraints kept."""
        import Sketcher

        sketch = self.session.sketch
        doc = self.session.doc
        names = []
        self._applying = True
        doc.openTransaction(name)
        try:
            pins = 0
            first = len(sketch.Constraints)
            blocks = [Sketcher.Constraint("Block", g) for g in sorted(pinned)]
            if blocks:
                sketch.addConstraint(blocks)
                sketch.solve()
                if sketch.ConflictingConstraints:  # a pin fights the sketch: do without
                    for i in reversed(range(first, len(sketch.Constraints))):
                        sketch.delConstraint(i)
                    sketch.solve()
                else:
                    pins = len(blocks)
            for (geo, pos), point in moves:
                sketch.moveGeometry(geo, pos, App.Vector(point[0], point[1], 0), False)
            ours_first = len(sketch.Constraints)
            if constraints:
                sketch.addConstraint(constraints)
            sketch.solve()
            bad = set(sketch.RedundantConstraints) | set(sketch.ConflictingConstraints)
            ours = [i for i in range(ours_first, len(sketch.Constraints)) if i + 1 in bad]
            for i in reversed(ours):
                sketch.delConstraint(i)
            names = [c.Type for c in sketch.Constraints[ours_first:]]
            for i in reversed(range(first, first + pins)):  # the pins go again
                sketch.delConstraint(i)
            if ours or pins:
                sketch.solve()
        except Exception:
            doc.abortTransaction()
            self._applying = False
            raise
        doc.commitTransaction()
        self._applying = False
        return names

    def _alignment(self, key, guide, new):
        """The constraint that keeps a point on a guide (None with GuideConstraint off:
        the point is only moved onto it)."""
        if not setting("GuideConstraint"):
            return None
        import Sketcher

        name = "Vertical" if guide.axis == core.SAME_X else "Horizontal"
        geo, other_pos = guide.key
        if geo in new:
            return None
        return Sketcher.Constraint(name, key[0], key[1], geo, other_pos)

    # -- for tests and diagnostics ------------------------------------------------------
    def state(self):
        return {
            "last": self.last,
            "kind": self.kind,
            "step": self.last_step,
            "acquired": list(self.acquired),
            "tool_points": list(self.tool_points),
            "placed": list(self.placed),
            "overlay": self.overlay.drawn(),
            "arc": self.arc.state,
        }


class TangentArc:
    """Fusion's Line tool gesture: press on the start of the line being drawn (the end
    of the last curve) and drag: an arc tangent to that curve follows the pointer;
    release places its end and the chain goes on from there. A press that moves less
    than DragPixels is a click, which FreeCAD alone ignores at that spot too (a line of
    zero length). FreeCAD never sees the press, the drag or the release: its own line
    preview stays at the start, and the line tool is restarted from the arc's end."""

    def __init__(self, infer):
        self.infer = infer
        self.state = None  # None, "armed" (pressed on the start), "dragging"
        self.press = None  # widget position of the press
        self.start = None  # the joint (sketch point)
        self.tangent = None  # unit direction the chain leaves the joint in
        self.prev = None  # (geo, pos) of the previous curve's end at the joint
        self.arc = None  # core.Arc being previewed
        self.end = None  # where its free end is
        self.end_key = None  # a sketch vertex the free end snapped to
        self.guides = []

    def reset(self):
        was = self.state
        self.state = None
        self.press = self.start = self.tangent = self.prev = None
        self.arc = self.end = self.end_key = None
        self.guides = []
        if was is not None:
            self.infer.overlay.clear()

    def handle(self, obj, event, ctrl, start):
        """True when the event belongs to the gesture (swallowed). `start` is the
        first point of the line being drawn (None before the first click)."""
        kind = event.type()
        infer = self.infer
        if self.state is None:
            if kind not in PRESSES or start is None or not setting("TangentArc"):
                return False
            view = _ViewMap(infer.session, obj, event.position())
            if not view.ok or core.dist(view.raw, start) > _pick_pixels() * view.px:
                return False
            # the preview's start is single precision: take the sketch point it is on
            verts = infer._geometry()[0]
            hit = core.nearest_vertex(start, verts, max(1e-6, 0.05 * view.px))
            if hit is None:
                return False  # no curve ends here: nothing to be tangent to
            start = hit[1]
            chain = self._chain(start, max(1e-6, 0.05 * view.px))
            if chain is None:
                return False
            self.tangent, self.prev = chain
            self.state, self.press, self.start = "armed", event.position(), start
            return True
        if kind == QtCore.QEvent.MouseMove:
            if not (event.buttons() & QtCore.Qt.LeftButton):
                self.reset()  # the button went up elsewhere
                return False
            if self.state == "armed":
                if (event.position() - self.press).manhattanLength() < setting("DragPixels"):
                    return True
                self.state = "dragging"
            try:
                self._preview(obj, event, ctrl)
            except Exception as exc:
                warn("tangent arc: %s" % exc)
            return True
        if kind == QtCore.QEvent.MouseButtonRelease:
            dragging = self.state == "dragging"
            if dragging:
                try:
                    self._preview(obj, event, ctrl)
                except Exception as exc:
                    warn("tangent arc: %s" % exc)
            arc, prev, end_key, guides = self.arc, self.prev, self.end_key, self.guides
            self.reset()
            if dragging and arc is not None:
                try:
                    self._place(arc, prev, end_key, guides)
                except Exception as exc:
                    warn("tangent arc: %s" % exc)
            return True
        return kind in PRESSES  # another press while armed: ours too

    def _chain(self, start, eps):
        """(unit tangent, (geo, pos)) of the curve the chain arrived at `start` by."""
        sketch = self.infer.session.sketch
        curves = []
        for i, geo in reversed(list(enumerate(sketch.Geometry))):
            if geo.TypeId == "Part::GeomLineSegment":
                curves.append(("line", i, _xy(geo.StartPoint), _xy(geo.EndPoint)))
            elif geo.TypeId == "Part::GeomArcOfCircle":
                curves.append(("arc", i, _xy(geo.Center), _xy(geo.StartPoint), _xy(geo.EndPoint)))
        return core.chain_tangent(start, curves, eps)

    def _preview(self, obj, event, ctrl):
        infer = self.infer
        view = _ViewMap(infer.session, obj, event.position())
        if not view.ok:
            return
        self.end, self.end_key, self.guides = self._end(view, ctrl)
        opt_min = core.Options().min_len_px * view.px
        self.arc = core.tangent_arc(self.start, self.tangent, self.end, opt_min)
        marks, guides = [], [(g.anchor, self.end) for g in self.guides]
        if self.arc is not None:
            away = core.unit(core.sub(self.start, self.arc.centre))
            marks += core.tangent_mark(self.start, self.tangent, away, 6 * view.px)
        infer.overlay.show_arc(self.arc, guides, marks)

    def _end(self, view, ctrl):
        """Where the arc's free end goes: the pointer (Ctrl), a sketch point under it,
        a guide crossing, or the grid."""
        infer = self.infer
        raw = view.raw
        if ctrl and setting("CtrlFree"):
            return raw, None, []
        verts, _curves, _lines, keyed = infer._geometry()
        pick = _pick_pixels() * view.px
        hit = core.nearest_vertex(raw, verts, pick)
        if hit is not None and core.dist(hit[1], self.start) > pick:
            return hit[1], hit[0], []
        opt = core.Options(
            guide_px=setting("GuidePixels"), pick_px=_pick_pixels(), grid=_grid_size(infer.session)
        )
        keys = list(infer.tool_points) + [k for k in infer.acquired if k not in infer.tool_points]
        acquired = [(k, keyed[k]) for k in keys if k in keyed]
        result = core.infer(raw, None, acquired, [], [], [], view.px, opt, (), [self.start])
        if result is not None and result.guides:
            return result.point, None, list(result.guides)
        return (core.grid_snap(raw[0], opt.grid), core.grid_snap(raw[1], opt.grid)), None, []

    def _place(self, arc, prev, end_key, guides):
        """Add the arc with its tangency (and the constraints of its free end) in one
        undo step, then go on drawing lines from its free end."""
        import Part
        import Sketcher

        from . import sketch_mode

        infer = self.infer
        session = infer.session
        sketch = session.sketch
        circle = Part.Circle(
            App.Vector(arc.centre[0], arc.centre[1], 0), App.Vector(0, 0, 1), arc.radius
        )
        geo = Part.ArcOfCircle(circle, arc.a1, arc.a2)
        doc = session.doc
        infer._applying = True
        doc.openTransaction(ARC_STEP)
        try:
            index = sketch.addGeometry(geo, sketch_mode.construction_mode())
            # tangent end to end: FreeCAD's tangency at a joint also joins the points
            constraints = [Sketcher.Constraint("Tangent", prev[0], prev[1], index, arc.joint_pos)]
            if end_key is not None:
                constraints.append(
                    Sketcher.Constraint("Coincident", index, arc.free_pos, end_key[0], end_key[1])
                )
            for guide in guides:
                c = infer._alignment((index, arc.free_pos), guide, [index])
                if c is not None:
                    constraints.append(c)
            first = len(sketch.Constraints)
            sketch.addConstraint(constraints)
            sketch.solve()
            bad = set(sketch.RedundantConstraints) | set(sketch.ConflictingConstraints)
            ours = [i for i in range(first, len(sketch.Constraints)) if i + 1 in bad]
            for i in reversed(ours):
                sketch.delConstraint(i)
            if ours:
                sketch.solve()
            names = [c.Type for c in sketch.Constraints[first:]]
        except Exception:
            doc.abortTransaction()
            infer._applying = False
            raise
        doc.commitTransaction()
        infer._applying = False
        infer.seen = sketch.GeometryCount
        infer.invalidate()
        for pos in (1, 2, 3):
            infer.tool_points.append((index, pos))
        log(
            "sketch: tangent arc %d (%s) from the end of curve %d"
            % (index + 1, ", ".join(names), prev[0] + 1)
        )
        free = vertex_point(sketch.Geometry[index], arc.free_pos)
        QtCore.QTimer.singleShot(0, lambda: self._go_on(free))

    def _go_on(self, point):
        """The line tool starts again from the arc's free end (FreeCAD's line tool is
        still waiting for the old line's end: restarting it clears that)."""
        session = self.infer.session
        try:
            if session.closed or point is None:
                return
            Gui.runCommand("Sketcher_CreateLine")
            if session.line._click_at(App.Vector(point[0], point[1], 0)):
                # the chain's point, for a press there before any move (no preview then)
                self.infer.last_start = (point[0], point[1])
            else:
                from . import commands

                commands.tell("Line: click the end of the arc to go on from it.")
        except Exception as exc:
            warn("tangent arc: %s" % exc)


def _has(sketch, name, index):
    return any(c.Type == name and c.First == index and c.Second < -1999 for c in sketch.Constraints)


def _add_geometry(verts, curves, lines, i, geo, construction):
    """Points and curves of one sketch geometry for the snapping lists."""
    kind = geo.TypeId
    if kind == "Part::GeomLineSegment":
        a, b = _xy(geo.StartPoint), _xy(geo.EndPoint)
        verts += [((i, 1), a), ((i, 2), b)]
        curves.append(("seg", a, b))
        if not construction:
            lines.append((i, a, b))
    elif kind == "Part::GeomPoint":
        verts.append(((i, 1), (geo.X, geo.Y)))
    elif kind == "Part::GeomCircle":
        verts.append(((i, 3), _xy(geo.Center)))
        curves.append(("circle", _xy(geo.Center), geo.Radius))
    else:
        if hasattr(geo, "StartPoint") and kind != "Part::GeomEllipse":
            verts += [((i, 1), _xy(geo.StartPoint)), ((i, 2), _xy(geo.EndPoint))]
        if hasattr(geo, "Center"):
            verts.append(((i, 3), _xy(geo.Center)))
        try:
            curves.append(core.poly([_xy(p) for p in geo.discretize(48)]))
        except Exception:
            pass


def _pick_pixels():
    try:
        return max(5.0, float(App.ParamGet(VIEW).GetFloat("PickRadius", 5.0)))
    except Exception:
        return 5.0


def _grid_size(session):
    """FreeCAD's grid spacing (mm) when its grid snap is on, else None. FreeCAD keeps
    the spacing it uses in C++; this is the same sum (ViewProviderGridExtension:
    computeGridSize: the adaptive grid grows by 10 as the view zooms out)."""
    import math

    try:
        snap = App.ParamGet(SNAP)
        if not (snap.GetBool("Snap", True) and snap.GetBool("SnapToGrid", False)):
            return None
        vp = session.sketch.ViewObject
        size = float(vp.GridSize.Value) if hasattr(vp.GridSize, "Value") else float(vp.GridSize)
        if size <= 0:
            return None
        if not vp.GridAuto:
            return size
        view = session.view
        width_px, height_px = view.getSize()
        if width_px <= 0 or height_px <= 0:
            return size
        camera = view.getCameraNode()
        if view.getCameraType() == "Orthographic":
            height = camera.height.getValue()
        else:
            height = math.tan(camera.heightAngle.getValue() / 2.0) * 2.0
            height *= camera.focalDistance.getValue()
        width = height
        aspect = float(width_px) / float(height_px)
        if aspect > 1.0:
            width *= aspect
        else:
            height *= aspect
        general = App.ParamGet(SKETCHER_GENERAL)
        threshold = max(1, general.GetInt("GridSizePixelThreshold", 15))
        sub = general.GetInt("GridNumberSubdivision", 10)
        sub = 10 if sub <= 1 else sub
        count = int(max(width_px, height_px) / threshold)
        if count <= 0:
            return size
        exponent = 1 + math.floor(math.log(max(width, height) / count / size) / math.log(sub))
        return size * sub**exponent
    except Exception:
        return None


class _ViewMap:
    """Screen pixel <-> sketch point near the pointer, computed the way FreeCAD's mouse
    handling does it (Quarter: y from the bottom, minus one; times the pixel ratio)."""

    def __init__(self, session, gl, position):
        from .profile_pick import ray_plane

        self.ok = False
        self.gl = gl
        self.ratio = gl.devicePixelRatioF()
        self.height = gl.height()
        sketch = session.sketch
        placement = sketch.getGlobalPlacement()
        self.inverse = placement.inverse()
        self.base = placement.Base
        self.normal = placement.Rotation.multVec(App.Vector(0, 0, 1))
        self.view = session.view
        self._ray_plane = ray_plane
        x, y = round(position.x()), round(position.y())
        self.coin = self._coin(x, y)
        p0 = self._to_sketch(self.coin)
        px = self._to_sketch((self.coin[0] + 1, self.coin[1]))
        py = self._to_sketch((self.coin[0], self.coin[1] + 1))
        if p0 is None or px is None or py is None:
            return
        self.p0 = p0
        self.ex = core.sub(px, p0)  # sketch step for one device pixel right
        self.ey = core.sub(py, p0)  # ... and one device pixel up
        self.px = core.length(self.ex) * self.ratio  # mm per screen (logical) pixel
        self.raw = p0
        self.ok = self.px > 0

    def _coin(self, x, y):
        return (int(x * self.ratio), int((self.height - y - 1) * self.ratio))

    def _to_sketch(self, coin):
        hit = self._ray_plane(self.view, coin, self.base, self.normal)
        if hit is None:
            return None
        local = self.inverse.multVec(hit[0])
        return (local.x, local.y)

    def _from_coin(self, coin):
        du, dv = coin[0] - self.coin[0], coin[1] - self.coin[1]
        return core.add(self.p0, core.add(core.mul(self.ex, du), core.mul(self.ey, dv)))

    def pixel_for(self, point):
        """The widget pixel (QPointF) whose FreeCAD point is nearest to `point`, or
        None when it is off the view."""
        import math

        a, b = self.ex, self.ey
        det = a[0] * b[1] - a[1] * b[0]
        if abs(det) < 1e-18:
            return None
        r = core.sub(point, self.p0)
        du = (r[0] * b[1] - r[1] * b[0]) / det
        dv = (a[0] * r[1] - a[1] * r[0]) / det
        cx, cy = self.coin[0] + du, self.coin[1] + dv
        x = cx / self.ratio
        y = self.height - 1 - cy / self.ratio
        best = None
        for qx in (math.floor(x), math.ceil(x)):
            for qy in (math.floor(y), math.ceil(y)):
                err = core.dist(self._from_coin(self._coin(qx, qy)), point)
                if best is None or err < best[0]:
                    best = (err, qx, qy)
        _err, qx, qy = best
        if not (0 <= qx < self.gl.width() and 0 <= qy < self.height):
            return None
        return QtCore.QPointF(qx, qy)


class Overlay:
    """SciForge's dashed guides, inference marks and the tangent-arc preview, drawn
    over the sketch (Coin nodes of our own under the view's root; never FreeCAD's edit
    nodes)."""

    def __init__(self, session):
        from pivy import coin

        from . import sketch_mode

        self.session = session
        self.attached = False
        self._drawn = {"guides": [], "marks": [], "preview": []}
        self.root = coin.SoAnnotation()  # on top of everything, like Fusion's guides
        self.root.setName("SciForgeSketchInference")
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        self.transform = coin.SoTransform()
        self.root.addChild(self.transform)
        # the arc being dragged: solid, in the colour of the curves being drawn
        preview = coin.SoSeparator()
        preview_color = coin.SoBaseColor()
        preview_color.rgb.setValue(*_rgb(sketch_mode.BLUE))
        preview_style = coin.SoDrawStyle()
        preview_style.lineWidth = 2.0
        self.preview_coords = coin.SoCoordinate3()
        self.preview_lines = coin.SoLineSet()
        for node in (preview_color, preview_style, self.preview_coords, self.preview_lines):
            preview.addChild(node)
        self.root.addChild(preview)
        color = coin.SoBaseColor()
        color.rgb.setValue(*_rgb(GUIDE_COLOR))
        self.root.addChild(color)
        dashed = coin.SoSeparator()
        style = coin.SoDrawStyle()
        style.lineWidth = 1.5
        style.linePattern.setValue(0xF0F0)
        self.guide_coords = coin.SoCoordinate3()
        self.guide_lines = coin.SoLineSet()
        for node in (style, self.guide_coords, self.guide_lines):
            dashed.addChild(node)
        self.root.addChild(dashed)
        solid = coin.SoSeparator()
        mark_style = coin.SoDrawStyle()
        mark_style.lineWidth = 2.0
        self.mark_coords = coin.SoCoordinate3()
        self.mark_lines = coin.SoLineSet()
        for node in (mark_style, self.mark_coords, self.mark_lines):
            solid.addChild(node)
        self.root.addChild(solid)
        self.clear()

    def _attach(self):
        if self.attached:
            return
        self.session.view.getSceneGraph().addChild(self.root)
        self.attached = True

    def show(self, result, px):
        guides = [(g.anchor, result.point) for g in result.guides]
        marks = []
        if result.kind == core.PERPENDICULAR and result.corner and result.along:
            d = result.direction
            u = d if not result.on_line else (-d[0], -d[1])
            marks.append(core.right_angle_mark(result.corner, u, result.along, 10 * px))
        elif result.kind == core.PARALLEL and result.start is not None:
            marks += core.parallel_mark(result.start, result.point, 6 * px)
        elif result.kind == core.HORIZONTAL and result.start is not None:
            marks += core.level_mark(result.start, result.point, 6 * px)
        elif result.kind == core.VERTICAL and result.start is not None:
            marks += core.upright_mark(result.start, result.point, 6 * px)
        self._draw(guides, marks, [])

    def show_arc(self, arc, guides, marks):
        """The tangent arc being dragged (None: no arc, the pointer is straight ahead),
        with the guides and marks of its free end."""
        preview = [arc.points()] if arc is not None else []
        self._draw(guides, marks, preview)

    def _draw(self, guides, marks, preview):
        placement = self.session.sketch.getGlobalPlacement()
        self.transform.translation.setValue(*placement.Base)
        self.transform.rotation.setValue(*placement.Rotation.Q)
        self._set(self.guide_coords, self.guide_lines, guides)
        self._set(self.mark_coords, self.mark_lines, marks)
        self._set(self.preview_coords, self.preview_lines, preview)
        self._drawn = {"guides": guides, "marks": marks, "preview": preview}
        self._attach()

    def _set(self, coords, lineset, polylines):
        points, counts = [], []
        for poly in polylines:
            points += [(p[0], p[1], 0.0) for p in poly]
            counts.append(len(poly))
        coords.point.setNum(0)
        lineset.numVertices.setNum(0)
        if points:
            coords.point.setValues(0, len(points), points)
            lineset.numVertices.setValues(0, len(counts), counts)

    def clear(self):
        if not any(self._drawn.values()) and self.attached:
            return
        self._set(self.guide_coords, self.guide_lines, [])
        self._set(self.mark_coords, self.mark_lines, [])
        self._set(self.preview_coords, self.preview_lines, [])
        self._drawn = {"guides": [], "marks": [], "preview": []}

    def drawn(self):
        return {key: list(value) for key, value in self._drawn.items()}

    def remove(self):
        try:
            if self.attached:
                self.session.view.getSceneGraph().removeChild(self.root)
        except Exception:
            pass
        self.attached = False
