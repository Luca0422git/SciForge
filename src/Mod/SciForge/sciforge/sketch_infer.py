# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's sketch inference on top of FreeCAD's own line tool, in Python.

What it does while a sketch tool draws:

- Ctrl held: no snapping and no automatic constraints at all (Fusion's meaning; in
  FreeCAD Ctrl turns on 5-degree angle steps). For each mouse event FreeCAD handles
  while Ctrl is down, SciForge switches FreeCAD's snapping ("Snap") and the sketch's
  "Autoconstraints" off and puts them back right after. A click with Ctrl that
  finishes a shape turns the automatic constraints back on as soon as FreeCAD has
  added the shape, so the constraints of points placed earlier (the start of the
  line, where it joins the previous one) are kept; only the Ctrl point stays free.
- Line tool, alignment guides: the last 3 points the pointer hovered, and the points
  of the lines drawn since the tool started, are remembered. When the pointer lines
  up with one of them (straight above/below or level, within a few pixels) a dashed
  guide is drawn from that point to the pointer and the point snaps onto it. After
  the click the alignment becomes a constraint (Vertical/Horizontal between the two
  points; Fusion's behaviour on click is unconfirmed, parameter GuideConstraint).
- Line tool, perpendicular: a line starting from, or ending on, another line at about
  90 degrees snaps to exactly 90 degrees, a small right-angle mark shows at the
  corner, and a Perpendicular constraint is added after the click.
- Line tool, level/upright: within 4 degrees (FreeCAD alone: 2) the line snaps level
  or upright; FreeCAD then adds its Horizontal/Vertical constraint itself.
- Line tool, parallel to a hovered line: off by default (Fusion unconfirmed),
  parameter Parallel.

How: FreeCAD decides the snapped point in C++ from the mouse position. The sketch's
view filter (sketch_mode._ViewFilter) gives every mouse event to Inference.mouse()
first. When the point should go somewhere else, the event is swallowed and a copy is
sent to the 3D view with the position moved to the screen pixel nearest to the wanted
point, so FreeCAD's own tool lands there (its grid snap is off for that one event; the
free coordinate is grid-snapped here instead). A pixel is coarse (about 0.1-0.3 mm),
so after the click the new point is moved exactly onto the guide and the constraint is
added, in one undo step glued to FreeCAD's ("Inferred Constraints").

Never lets an exception out of an event handler or timer (warn() and carry on).
"""

import FreeCAD as App

from . import log, warn
from . import sketch_infer_core as core
from .compat import QtCore, QtGui, QtWidgets

PARAMS = "User parameter:BaseApp/Preferences/Mod/SciForge/SketchInference"
SNAP = "User parameter:BaseApp/Preferences/Mod/Sketcher/Snap"
SKETCHER_GENERAL = "User parameter:BaseApp/Preferences/Mod/Sketcher/General"
VIEW = "User parameter:BaseApp/Preferences/View"
INFER_STEP = "Inferred Constraints"  # the same as sketch_mode.INFER_STEP (glued in undo)
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
}
SNAP_OFF_MARK = "SnapSwitchedOff"  # set while FreeCAD's Snap is off for a Ctrl event

KINDS = (
    QtCore.QEvent.MouseMove,
    QtCore.QEvent.MouseButtonPress,
    QtCore.QEvent.MouseButtonRelease,
    QtCore.QEvent.MouseButtonDblClick,
)
PRESSES = (QtCore.QEvent.MouseButtonPress, QtCore.QEvent.MouseButtonDblClick)


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


class Inference:
    """One per sketch session (sketch_mode.SketchSession.infer)."""

    def __init__(self, session):
        self.session = session
        self.busy = False  # our own copy of an event is being handled
        self.acquired = []  # vertex keys (geo, pos), newest last
        self.hovered_lines = []  # geometry indices of hovered lines (parallel)
        self.tool_points = []  # vertex keys of the lines this tool run drew
        self.tool_on = False
        self.current = {}  # what was inferred for the line being drawn
        self.pending = []  # records of finished lines, applied from a timer
        self.seen = session.sketch.GeometryCount
        self.last = None  # last Result (for tests and diagnostics)
        self.last_px = None
        self._cache = None
        self._flip = False  # Autoconstraints back on at the next commit (Ctrl click)
        self._applying = False
        self._queued = False
        self.overlay = Overlay(session)

    # -- bookkeeping -------------------------------------------------------------------
    def invalidate(self):
        """The sketch's geometry changed: rebuild the point/curve lists when needed."""
        self._cache = None

    def reset(self):
        """The tool stopped (Esc, another tool): forget everything of this command."""
        self.acquired = []
        self.hovered_lines = []
        self.tool_points = []
        self.current = {}
        self.last = None
        self.overlay.clear()

    def close(self):
        self.reset()
        self.overlay.remove()

    # -- the mouse ---------------------------------------------------------------------
    def mouse(self, obj, event):
        """Called first for every mouse event of the 3D view while the sketch is open.
        True when the event was replaced by a copy (the caller then swallows it)."""
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
        """(position, free, nogrid, result) for the copy FreeCAD gets, or None to leave
        the event alone."""
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
        ctrl = bool(event.modifiers() & QtCore.Qt.ControlModifier)
        if ctrl and setting("CtrlFree"):
            self.overlay.clear()
            self.last = None
            if kind in PRESSES:
                self._remember_press(None, None)
            return (event.position(), True, False, None, None)
        line_tool = self._line_tool()
        if not line_tool:
            if self.tool_on:
                self.tool_on = False
                self.reset()
            return None
        if not self.tool_on:
            self.tool_on = True
            self.reset()
            self.seen = session.sketch.GeometryCount
        if not setting("Enabled"):
            self.overlay.clear()
            return None
        view = _ViewMap(session, obj, event.position())
        if not view.ok:
            return None
        result, grid = self._infer(view)
        self.last, self.last_px = result, view.px
        if kind in PRESSES:
            self._remember_press(result, view.px)
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

    def _line_tool(self):
        """SciForge's Line (L) or FreeCAD's line tool is the tool drawing."""
        from . import recent

        last = recent.last()
        if last is not None:
            return last[0] in LINE_COMMANDS
        return self.session.line.active

    def _preview(self):
        """(first point, pointer end) of the line FreeCAD previews, or None before the
        first click. Looked up fresh every time: FreeCAD deletes its edit nodes when the
        sketch closes."""
        from .sketch_mode import find_node

        coords, _parent = find_node(self.session.view.getSceneGraph(), "EditCurvesCoordinate")
        if coords is None:
            return None
        points = coords.point.getValues(0)
        if len(points) != 2:
            return None
        (x0, y0, _z0), (x1, y1, _z1) = points[0].getValue(), points[1].getValue()
        return (float(x0), float(y0)), (float(x1), float(y1))

    def _start_point(self):
        """The first point of the line being drawn, or None before the first click."""
        preview = self._preview()
        return preview[0] if preview else None

    def _check_preview(self, result, px):
        """Never show a guide or mark the line does not follow: a length typed into
        FreeCAD's field puts the end elsewhere (the click then adds nothing either)."""
        preview = self._preview() if result.start is not None else None
        if preview is None:
            return
        start, end = preview
        if core.exact_point(result, end, px, start) is None:
            self.overlay.clear()
            self.last = None

    def _infer(self, view):
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
        start = self._start_point()
        result = core.infer(raw, start, acquired, lines, verts, curves, view.px, opt, parallel)
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

    def _remember_press(self, result, px):
        """A click of the line tool: the first one starts a new record, the second one
        completes it (applied after FreeCAD has added the line)."""
        if not self._line_tool():
            return
        try:
            second = self._start_point() is not None
        except Exception:
            second = False
        if second:
            self.current["end"] = result
            self.current["end_px"] = px
        else:
            self.current = {"start": result, "start_px": px}

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
            self.current = {}
            self.pending = []
            QtCore.QTimer.singleShot(0, self._resync)
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
        if "start" in self.current and "end" not in self.current and self.last is not None:
            # no second click: a line finished with Enter after a typed value takes
            # what the pointer showed last (FreeCAD drops its own level/upright then)
            if self.tool_on and self.last.start is not None:
                self.current["end"], self.current["end_px"] = self.last, self.last_px
        if self.current.get("start") is not None or self.current.get("end") is not None:
            self.pending.append(self.current)
            self.current = {}
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
            if not new:
                return
            lines = [i for i in new if sketch.Geometry[i].TypeId == "Part::GeomLineSegment"]
            if self.tool_on:
                for i in lines:
                    for pos in (1, 2):
                        self.tool_points.append((i, pos))
            if len(new) != 1 or len(lines) != 1 or not pending:
                return
            self._apply_line(lines[0], pending[-1])
        except Exception as exc:
            warn("sketch inference: %s" % exc)

    def _apply_line(self, index, record):
        """Put the new line's points exactly where the guides/inference said and add
        the constraints, in one undo step."""
        import Sketcher

        sketch = self.session.sketch
        geo = sketch.Geometry[index]
        start, end = _xy(geo.StartPoint), _xy(geo.EndPoint)
        moves, constraints, names = [], [], []
        start_res, start_px = record.get("start"), record.get("start_px")
        if start_res is not None and start_res.guides and start_px:
            target = core.exact_point(start_res, start, start_px)
            if target is not None:
                if core.dist(target, start) > 1e-9:
                    moves.append((1, target))
                start = target
                for guide in start_res.guides:
                    constraints.append(self._alignment(index, 1, guide))
        end_res, end_px = record.get("end"), record.get("end_px")
        if end_res is not None and end_px:
            target = core.exact_point(end_res, end, end_px, start)
            if target is not None:
                if core.dist(target, end) > 1e-9:
                    moves.append((2, target))
                for guide in end_res.guides:
                    constraints.append(self._alignment(index, 2, guide))
                if end_res.kind in (core.HORIZONTAL, core.VERTICAL):
                    name = "Horizontal" if end_res.kind == core.HORIZONTAL else "Vertical"
                    if not _has(sketch, name, index):
                        constraints.append(Sketcher.Constraint(name, index))
                elif end_res.kind == core.PERPENDICULAR and end_res.other is not None:
                    constraints.append(Sketcher.Constraint("Perpendicular", index, end_res.other))
                elif end_res.kind == core.PARALLEL and end_res.other is not None:
                    constraints.append(Sketcher.Constraint("Parallel", index, end_res.other))
        constraints = [c for c in constraints if c is not None]
        if not moves and not constraints:
            return
        doc = self.session.doc
        self._applying = True
        doc.openTransaction(INFER_STEP)
        try:
            for pos, point in moves:
                sketch.moveGeometry(index, pos, App.Vector(point[0], point[1], 0), False)
            first = len(sketch.Constraints)
            if constraints:
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
            self._applying = False
            raise
        doc.commitTransaction()
        self._applying = False
        if names:
            log("sketch: %s added to line %d (inferred)" % (", ".join(names), index + 1))

    def _alignment(self, index, pos, guide):
        """The constraint that keeps a point on a guide (None with GuideConstraint off:
        the point is only moved onto it)."""
        if not setting("GuideConstraint"):
            return None
        import Sketcher

        name = "Vertical" if guide.axis == core.SAME_X else "Horizontal"
        geo, other_pos = guide.key
        if geo == index:
            return None
        return Sketcher.Constraint(name, index, pos, geo, other_pos)

    # -- for tests and diagnostics ------------------------------------------------------
    def state(self):
        return {
            "last": self.last,
            "acquired": list(self.acquired),
            "tool_points": list(self.tool_points),
            "overlay": self.overlay.drawn(),
        }


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
    """SciForge's dashed guides and inference marks, drawn over the sketch (Coin nodes
    of our own under the view's root; never FreeCAD's edit nodes)."""

    def __init__(self, session):
        from pivy import coin

        self.session = session
        self.attached = False
        self._drawn = {"guides": [], "marks": []}
        self.root = coin.SoAnnotation()  # on top of everything, like Fusion's guides
        self.root.setName("SciForgeSketchInference")
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        self.transform = coin.SoTransform()
        self.root.addChild(self.transform)
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
        placement = self.session.sketch.getGlobalPlacement()
        self.transform.translation.setValue(*placement.Base)
        self.transform.rotation.setValue(*placement.Rotation.Q)
        self._set(self.guide_coords, self.guide_lines, guides)
        self._set(self.mark_coords, self.mark_lines, marks)
        self._drawn = {"guides": guides, "marks": marks}
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
        if not self._drawn["guides"] and not self._drawn["marks"] and self.attached:
            return
        self._set(self.guide_coords, self.guide_lines, [])
        self._set(self.mark_coords, self.mark_lines, [])
        self._drawn = {"guides": [], "marks": []}

    def drawn(self):
        return {"guides": list(self._drawn["guides"]), "marks": list(self._drawn["marks"])}

    def remove(self):
        try:
            if self.attached:
                self.session.view.getSceneGraph().removeChild(self.root)
        except Exception:
            pass
        self.attached = False
