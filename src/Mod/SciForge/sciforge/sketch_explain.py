# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sketch constraints that explain themselves (docs/sciforge/dev/cadcraft-lessons.md, idea 1):
the FreeCAD side. The words are in sketch_explain_core.py.

- Name the culprits. When a constraint or a dimension would fight the sketch, the message
  names the constraints it fights ("conflicts with the Horizontal on Line 2 and the 30 mm
  dimension") and those are highlighted in the sketch for a moment (selected, so FreeCAD
  draws them in the selection colour; the next click or key, or 2.5 s, puts the selection
  back). FreeCAD's solver lists conflicting constraints whole (the group, the new one with
  the ones it fights), but of a redundant group it names only the one it would remove: the
  others are found by switching the sketch's constraints off one at a time (IsActive, the
  geometry is not touched) and seeing which ones make the redundancy go away.
- Fusion's padlock: fully_constrained() reads what the solver already knows (no solve), so
  the browser and the timeline can ask every refresh.
- Inferred constraints in priority order: add_checked() adds all of them (the fast path)
  and, only when some do not fit, again one by one, strongest first.

Never lets an exception out of a timer or event handler (warn() and carry on).
"""

import time

import FreeCAD as App

from . import log, sketch_geometry, warn
from . import sketch_explain_core as core

HIGHLIGHT_MS = 2500
PROBE_LIMIT = 150  # constraints switched off at most to find a redundancy's culprits
PROBE_SECONDS = 1.0  # in all, to find a redundancy's culprits (each try is a solve)


# -- reading constraints ----------------------------------------------------------------------
def constraint_info(sketch, index, c=None):
    """One constraint as a plain dict for sketch_explain_core.describe()."""
    c = c if c is not None else sketch.Constraints[index]
    return {
        "index": index,
        "type": c.Type,
        "first": c.First,
        "first_pos": c.FirstPos,
        "second": c.Second,
        "second_pos": c.SecondPos,
        "third": getattr(c, "Third", core.GEO_UNDEF),
        "third_pos": getattr(c, "ThirdPos", 0),
        "value": c.Value,
        "name": c.Name,
        "driving": c.Driving,
    }


def names(sketch):
    """({geo: "Line 2"}, {geo: TypeId}) of the sketch's own curves."""
    type_ids = [g.TypeId for g in sketch.Geometry]
    return core.curve_names(type_ids), dict(enumerate(type_ids))


def words(sketch, indices, limit=3):
    """(the constraints `indices` in words, how many) for a message."""
    if not indices:
        return "", 0
    cons = sketch.Constraints
    curve_names, kinds = names(sketch)
    items = [constraint_info(sketch, i, cons[i]) for i in indices if 0 <= i < len(cons)]
    return core.culprit_list(items, curve_names, kinds, limit), len(items)


def bad_sets(sketch):
    """(conflicting, redundant) constraint indices from the last solve (from 0)."""
    conflicting = {i - 1 for i in sketch.ConflictingConstraints}
    redundant = {i - 1 for i in sketch.RedundantConstraints}
    return conflicting, redundant


def _geos(c):
    return [g for g in (c.First, c.Second, getattr(c, "Third", core.GEO_UNDEF)) if g >= 0]


def component(sketch, seeds):
    """Indices of the constraints connected to the constraints `seeds` through the sketch's
    own curves (the axes and projected curves are fixed: they connect nothing). Only those
    can take part in a seed's conflict or redundancy (FreeCAD's solver splits the sketch
    the same way)."""
    cons = sketch.Constraints
    by_geo = {}
    for i, c in enumerate(cons):
        for g in _geos(c):
            by_geo.setdefault(g, []).append(i)
    seen = set(seeds)
    todo = list(seeds)
    geos = set()
    while todo:
        i = todo.pop()
        if not 0 <= i < len(cons):
            continue
        for g in _geos(cons[i]):
            if g in geos:
                continue
            geos.add(g)
            for j in by_geo.get(g, ()):
                if j not in seen:
                    seen.add(j)
                    todo.append(j)
    return seen


def _nameable(c):
    """A constraint the user put there and the solver uses: driving, switched on, not the
    internal shape of a spline or an ellipse."""
    return c.Driving and getattr(c, "IsActive", True) and c.Type != "InternalAlignment"


def _neighbours(sketch, index):
    """The constraints on the same curves as constraint `index` (the last resort when the
    culprits cannot be told apart)."""
    cons = sketch.Constraints
    mine = set(_geos(cons[index]))
    return [j for j, c in enumerate(cons) if j != index and _nameable(c) and mine & set(_geos(c))]


# -- finding the culprits ---------------------------------------------------------------------
class Finding:
    """What is wrong with some new constraints: kind "conflict", "redundant" or "" (all
    fine); `bad`: the new ones that do not fit; `culprits`: the existing ones they fight;
    `partial`: the culprits are only some of them (the search was cut short)."""

    def __init__(self, kind="", bad=(), culprits=()):
        self.kind = kind
        self.bad = list(bad)
        self.culprits = list(culprits)
        self.partial = bool(getattr(culprits, "partial", False))

    def __bool__(self):
        return bool(self.kind)

    def __repr__(self):
        return "Finding(%r, bad=%r, culprits=%r)" % (self.kind, self.bad, self.culprits)


def conflict_culprits(sketch, new):
    """The existing constraints the constraints `new` conflict with, from the last solve
    (FreeCAD lists a conflict's whole group)."""
    conflicting, _redundant = bad_sets(sketch)
    new = set(new)
    near = component(sketch, new)
    cons = sketch.Constraints
    return sorted(
        i
        for i in conflicting
        if i not in new and i in near and 0 <= i < len(cons) and _nameable(cons[i])
    )


def _nearness(sketch, index, candidates):
    """`candidates` (constraint indices) closest to constraint `index` first: the ones on its
    own curves, then those one curve further, and so on; within a ring the directions and
    relations (the usual reason a constraint is so already) before the dimensions, and the
    joins last."""
    cons = sketch.Constraints
    by_geo = {}
    for i, c in enumerate(cons):
        for g in _geos(c):
            by_geo.setdefault(g, []).append(i)
    distance = {g: 0 for g in _geos(cons[index])}
    ring = list(distance)
    while ring:
        following = []
        for g in ring:
            for j in by_geo.get(g, ()):
                for h in _geos(cons[j]):
                    if h not in distance:
                        distance[h] = distance[g] + 1
                        following.append(h)
        ring = following
    likely = {0: 1, 1: 0, 2: 0, 3: 2, 4: 3}  # meaning_rank -> probe order

    def key(j):
        geos = _geos(cons[j])
        near = min((distance.get(g, 10**6) for g in geos), default=10**6)
        info = {"type": cons[j].Type}
        return (near, likely.get(core.meaning_rank(info), 3), j)

    return sorted(candidates, key=key)


class Culprits(list):
    """Culprits found by switching constraints off; `partial`: the search was cut short."""

    partial = False


def _solves_itself(sketch):
    """FreeCAD solves the sketch on every change of its constraints itself (setActive too)
    while it is open for editing and the Sketcher's "Auto-update" is off (its default; its
    task panel sets the sketch's noRecomputes then, which Python cannot read)."""
    if not _in_edit(sketch):
        return False
    try:
        group = App.ParamGet("User parameter:BaseApp/Preferences/Mod/Sketcher")
        return not group.GetBool("AutoRecompute", False)
    except Exception:
        return False


def redundant_culprits(sketch, index, exclude=(), solved=False):
    """The existing constraints that already say what constraint `index` says. FreeCAD names
    only the one it would drop, so the constraints connected to it are switched off in turn,
    the nearest first: the ones whose absence ends the redundancy are the culprits. Each try
    is a solve of the whole sketch, so on a big sketch the search stops after PROBE_SECONDS
    in all (the solves before and after included): then only the culprits found so far are
    named (none: the message says it is so already, no guess). `solved`: the caller has
    just solved the sketch as it is. The constraints are put back as they were (and the
    curves, should the solver have nudged them)."""
    started = time.time()
    found = Culprits()
    cons = sketch.Constraints
    exclude = set(exclude) | {index}
    candidates = [
        j for j in component(sketch, [index]) if j not in exclude and _nameable(cons[j])
    ]
    if not candidates:
        return found
    candidates = _nearness(sketch, index, candidates)[:PROBE_LIMIT]
    if not solved:
        sketch.solve()
    _conflicting, redundant = bad_sets(sketch)
    base = len(redundant)
    if index not in redundant or not base:
        return found
    geometry = sketch_geometry.snapshot(sketch)
    itself = _solves_itself(sketch)  # then setActive solves: no second solve of ours
    tries = 0
    slowest = 0.0
    complete = True
    try:
        for j in candidates:
            # room left for this try (and for the solve that puts the sketch back, unless
            # setActive does that)
            if time.time() - started + (1 if itself else 2) * slowest > PROBE_SECONDS:
                complete = False
                log(
                    "explain: stopped looking for culprits after %d of %d tries (%.1f s)"
                    % (tries, len(candidates), time.time() - started)
                )
                break
            tries += 1
            began = time.time()
            sketch.setActive(j, False)
            try:
                if not itself:
                    sketch.solve()
                _c, now = bad_sets(sketch)
                if index not in now and len(now) < base:
                    found.append(j)
            finally:
                sketch.setActive(j, True)
            slowest = max(slowest, time.time() - began)
    finally:
        if not itself:  # (else the last setActive solved the sketch as it is)
            sketch.solve()
        _restore_geometry(sketch, geometry)
    if found or not complete:
        found.partial = not complete
        return found
    # every one tried, none alone ends it (it is said twice over): the ones on its curves
    found.extend(_neighbours(sketch, index))
    return found


def _restore_geometry(sketch, geometry):
    """Put the curves back (`geometry`: sketch_geometry.snapshot) if the solver moved any
    while constraints were switched off (it should not: the curves already met every
    constraint). Construction flags and geometry ids stay (sketch_geometry.restore)."""
    try:
        now = sketch.Geometry
        if len(now) != len(geometry):
            return
        for a, b in zip(now, sketch_geometry.curves(geometry)):
            if not _same_curve(a, b):
                sketch_geometry.restore(sketch, geometry)
                sketch.solve()
                return
    except Exception as exc:
        warn("explain: could not compare the curves: %s" % exc)


def _same_curve(a, b, tol=1e-9):
    for name in ("StartPoint", "EndPoint", "Center"):
        pa, pb = getattr(a, name, None), getattr(b, name, None)
        if pa is not None and pb is not None and (pa - pb).Length > tol:
            return False
    if hasattr(a, "X") and hasattr(b, "X"):  # a point
        return abs(a.X - b.X) <= tol and abs(a.Y - b.Y) <= tol
    return True


FAILED = -1  # SketchObject.solve(): the solver found no solution
REDUNDANT = -2  # SketchObject.solve(): redundant constraints (the others are worse)


def _solve_without(sketch, new):
    """(solve code, conflicting, redundant) of the sketch with the constraints `new`
    switched off, then switched on again (the curves put back)."""
    geometry = sketch_geometry.snapshot(sketch)
    try:
        for i in new:
            sketch.setActive(i, False)
        code = sketch.solve()
        conflicting, redundant = bad_sets(sketch)
    finally:
        for i in new:
            sketch.setActive(i, True)
        sketch.solve()
        _restore_geometry(sketch, geometry)
    return code, conflicting, redundant


def check_new(sketch, new, probe=True):
    """Solve and look at the constraints `new` (indices): a Finding (empty when they fit).
    FreeCAD does not always flag the new constraint itself: a redundancy can be pinned on
    older constraints (a Symmetry that repeats a rectangle's Horizontal and Vertical), and
    when the solver finds no solution at all it lists nothing (a corner pinned to the origin
    of a rectangle centred elsewhere). Then the sketch is solved once without the new ones:
    when it was fine (or better) before, they do not fit."""
    code = sketch.solve()
    conflicting, redundant = bad_sets(sketch)
    new = [i for i in new if 0 <= i < len(sketch.Constraints)]
    bad = [i for i in new if i in conflicting]
    if bad:
        return Finding("conflict", bad, conflict_culprits(sketch, new))
    bad = [i for i in new if i in redundant]
    if bad:
        culprits = (
            redundant_culprits(sketch, bad[0], exclude=new, solved=True) if probe else []
        )
        return Finding("redundant", bad, culprits)
    if code == 0 or not new:
        return Finding()
    partial = {i - 1 for i in getattr(sketch, "PartiallyRedundantConstraints", ())}
    before, conflicting_before, redundant_before = _solve_without(sketch, new)
    worse = (
        before == 0
        or len(conflicting) > len(conflicting_before)
        or len(redundant) > len(redundant_before)
        or (before == REDUNDANT and code != REDUNDANT)
    )
    if not worse:
        return Finding()  # it was so before the new ones: not theirs
    near = component(sketch, new)
    cons = sketch.Constraints

    def named(indices):
        return sorted(
            i for i in indices if i not in new and i in near and _nameable(cons[i])
        )

    if code == REDUNDANT:
        # FreeCAD pinned the redundancy on older ones: with the new ones they say it twice
        return Finding("redundant", new, named(redundant - redundant_before))
    culprits = named(conflicting - conflicting_before) or named(partial)
    return Finding("conflict", new, culprits)


def refusal(sketch, title, finding):
    """The constraint tool's message for `finding` (sketch_explain_core.refused_constraint)."""
    text, count = words(sketch, finding.culprits)
    return core.refused_constraint(title, finding.kind, text, count, finding.partial)


def log_finding(where, sketch, finding):
    text, _count = words(sketch, finding.culprits, limit=12)
    log("%s: %s with %s" % (where, finding.kind or "fits", text or "(none named)"))


# -- highlighting ---------------------------------------------------------------------------------
_highlight = {
    "doc": None,
    "sketch": None,
    "subs": [],
    "timer": None,
    "filter": None,
    "overlay": None,
    "key": None,
}


RING_COLOUR = "#ff6b5c"  # SciForge's own: a warm red apart from the blue/white sketch
RING_PIXELS = 13


def highlight(sketch, indices, ms=HIGHLIGHT_MS):
    """Show the constraints `indices` of the open sketch for a moment: a red ring around
    each in the 3D view (on a dimension's value, or where FreeCAD draws the constraint's
    symbol: by its curves), and selected, so FreeCAD draws them in the selection colour
    (while one of FreeCAD's own constraint tools runs it lets only curves be selected: the
    rings still show). The next click, wheel turn or key anywhere, or `ms`, ends it."""
    clear_highlight()
    indices = [i for i in indices if 0 <= i < len(sketch.Constraints)]
    if not indices or not App.GuiUp:
        return
    try:
        import FreeCADGui as Gui

        from .compat import QtCore

        doc, name = sketch.Document.Name, sketch.Name
        subs = ["Constraint%d" % (i + 1) for i in indices]
        _highlight.update(doc=doc, sketch=name, subs=subs)
        try:
            Gui.Selection.clearSelection()
            for sub in subs:
                Gui.Selection.addSelection(doc, name, sub)
        except Exception:
            pass  # a selection gate (FreeCAD's running tool) refused them: the rings show
        _highlight["overlay"] = _show_rings(sketch, indices)
        timer = QtCore.QTimer()
        timer.setSingleShot(True)
        timer.setInterval(ms)
        timer.timeout.connect(clear_highlight)
        timer.start()
        _highlight["timer"] = timer
        # the filter starts after the event being handled now (the Enter that set a value
        # would otherwise end the highlight on its way up to the box's parents)
        key = object()
        _highlight["key"] = key
        QtCore.QTimer.singleShot(0, lambda: _watch_next_action(key))
    except Exception as exc:
        warn("explain: could not highlight the constraints: %s" % exc)


def _watch_next_action(key):
    try:
        if _highlight.get("key") is not key or not _highlight["subs"]:
            return
        from .compat import QtWidgets

        app = QtWidgets.QApplication.instance()
        if app is not None:
            watcher = _NextAction()
            app.installEventFilter(watcher)
            _highlight["filter"] = watcher
    except Exception as exc:
        warn("explain: highlight: %s" % exc)


def highlighted():
    """Indices of the constraints highlighted now (tests)."""
    return [int(s[len("Constraint") :]) - 1 for s in _highlight["subs"]]


def highlight_rings():
    """The view pixels (x, y) of the rings shown now (tests)."""
    overlay = _highlight.get("overlay")
    try:
        return overlay.pixels() if overlay is not None and overlay.isVisible() else []
    except RuntimeError:
        return []


def clear_highlight():
    """Unselect what highlight() selected (only that: a selection the user made meanwhile
    stays) and take the rings away."""
    subs = _highlight["subs"]
    doc, name = _highlight["doc"], _highlight["sketch"]
    timer, watcher = _highlight["timer"], _highlight["filter"]
    overlay = _highlight.get("overlay")
    _highlight.update(
        doc=None, sketch=None, subs=[], timer=None, filter=None, overlay=None, key=None
    )
    try:
        if timer is not None:
            timer.stop()
    except Exception:
        pass
    try:
        if watcher is not None:
            from .compat import QtWidgets

            QtWidgets.QApplication.instance().removeEventFilter(watcher)
    except Exception:
        pass
    try:
        if overlay is not None:
            overlay.hide()
            overlay.deleteLater()
    except Exception:
        pass  # already gone with its view
    if not subs:
        return
    try:
        import FreeCADGui as Gui

        if App.getDocument(doc) is None:
            return
        for sub in subs:
            Gui.Selection.removeSelection(doc, name, sub)
    except Exception:
        pass  # the document or the sketch went meanwhile


def _ref_point(sketch, geo, pos):
    """The sketch point a constraint refers to: a curve's end (1, 2) or centre (3), its
    middle for the whole curve (0, where FreeCAD puts the constraint's symbol), the origin
    for the root point; None for the axes and projected curves."""
    if geo == -1 and pos == 1:
        return App.Vector(0, 0, 0)
    if geo is None or geo < 0:
        return None
    g = sketch.Geometry[geo]
    if g.TypeId == "Part::GeomPoint":
        return App.Vector(g.X, g.Y, 0)
    if pos == 1:
        return g.StartPoint
    if pos == 2:
        return g.EndPoint
    if pos == 3:
        return getattr(g, "Center", None)
    try:
        return g.value((g.FirstParameter + g.LastParameter) / 2.0)
    except Exception:
        return None


def anchors(sketch, index):
    """Where to ring constraint `index` (sketch points): a dimension at its value, a
    Coincident at its point, others by the middle of the curves they are on."""
    c = sketch.Constraints[index]
    if c.Type in core.LENGTHS:
        try:
            from . import sketch_mode

            point = sketch_mode.label_point(sketch, index)
            if point is not None:
                return [point]
        except Exception:
            pass
    refs = [(c.First, c.FirstPos), (c.Second, c.SecondPos)]
    third = getattr(c, "Third", core.GEO_UNDEF)
    if third != core.GEO_UNDEF:
        refs.append((third, getattr(c, "ThirdPos", 0)))
    points = [p for p in (_ref_point(sketch, g, pos) for g, pos in refs) if p is not None]
    if not points:
        return []
    if c.Type in ("Coincident", "PointOnObject") or (
        c.Type in ("Horizontal", "Vertical") and c.FirstPos == 0
    ):
        return points[:1]
    if c.Type in ("Horizontal", "Vertical", "Distance", "DistanceX", "DistanceY"):
        return [(points[0] + points[-1]) * 0.5]
    unique = []
    for p in points:
        if all((p - q).Length > 1e-6 for q in unique):
            unique.append(p)
    return unique[:2]


def _show_rings(sketch, indices):
    """A see-through layer over the 3D view drawing the rings (mouse clicks go through)."""
    from . import sketch_mode
    from .compat import QtCore, QtGui, QtWidgets

    gl = sketch_mode.gl_widget()
    if gl is None:
        return None
    import FreeCADGui as Gui

    view = Gui.ActiveDocument.ActiveView
    points = [p for i in indices for p in anchors(sketch, i)]
    placement = sketch.getGlobalPlacement()

    class Rings(QtWidgets.QWidget):
        def pixels(self):
            out = []
            ratio = gl.devicePixelRatioF()
            for p in points:
                try:
                    x, y = view.getPointOnViewport(placement.multVec(p))
                    out.append((int(x / ratio), int(gl.height() - y / ratio)))
                except Exception:
                    pass
            return out

        def paintEvent(self, event):
            try:
                painter = QtGui.QPainter(self)
                painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
                colour = QtGui.QColor(RING_COLOUR)
                pen = QtGui.QPen(colour)
                pen.setWidthF(2.5)
                painter.setPen(pen)
                fill = QtGui.QColor(colour)
                fill.setAlpha(50)
                painter.setBrush(fill)
                for x, y in self.pixels():
                    painter.drawEllipse(QtCore.QPointF(x, y), RING_PIXELS, RING_PIXELS)
                painter.end()
            except Exception:
                pass

    rings = Rings(gl)
    rings.setObjectName("SciForgeConstraintRings")
    rings.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
    rings.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)
    rings.setGeometry(gl.rect())
    rings.show()
    rings.raise_()
    return rings


def _next_action_filter():
    from .compat import QtCore

    class NextAction(QtCore.QObject):
        """While constraints are highlighted: the next mouse press, wheel turn or key (not
        a lone Shift/Ctrl) anywhere ends the highlight before it is handled, so the click
        or key acts on the user's own selection, never on the highlighted constraints."""

        def eventFilter(self, obj, event):
            try:
                kind = event.type()
                if kind in (
                    QtCore.QEvent.MouseButtonPress,
                    QtCore.QEvent.MouseButtonDblClick,
                    QtCore.QEvent.Wheel,
                ) or (
                    kind == QtCore.QEvent.KeyPress
                    and event.key()
                    not in (
                        QtCore.Qt.Key_Shift,
                        QtCore.Qt.Key_Control,
                        QtCore.Qt.Key_Alt,
                        QtCore.Qt.Key_Meta,
                    )
                ):
                    clear_highlight()
            except Exception:
                pass
            return False

    return NextAction


_NEXT_ACTION = {"cls": None}


def _NextAction():
    if _NEXT_ACTION["cls"] is None:
        _NEXT_ACTION["cls"] = _next_action_filter()
    return _NEXT_ACTION["cls"]()


# -- Fusion's padlock ------------------------------------------------------------------------------
def fully_constrained(sketch):
    """True when nothing in the sketch can move and nothing is wrong with it (Fusion's
    padlock): read from what the solver last found, no solve."""
    try:
        return core.is_fully_constrained(
            sketch.GeometryCount,
            sketch.FullyConstrained,
            sketch.DoF,
            sketch.ConflictingConstraints,
            sketch.MalformedConstraints,
            sketch.RedundantConstraints,
            broken=_broken(sketch),
        )
    except Exception:
        return False


def _broken(sketch):
    """The sketch's last recompute failed (FreeCAD: "Solving the sketch failed", redundant
    or conflicting constraints). Not asked of the sketch open for editing: its solver has
    been told of every change since, its State only of the last recompute."""
    if not ({"Invalid", "Error"} & set(sketch.State)):
        return False
    return not _in_edit(sketch)


def _in_edit(sketch):
    if not App.GuiUp:
        return False
    try:
        import FreeCADGui as Gui

        gui_doc = Gui.getDocument(sketch.Document.Name)
        vp = gui_doc.getInEdit() if gui_doc is not None else None
        return vp is not None and vp.Object == sketch
    except Exception:
        return False


def freedom(sketch):
    """(degrees of freedom left, fully constrained, conflicting) from the last solve."""
    try:
        return sketch.DoF, fully_constrained(sketch), bool(sketch.ConflictingConstraints)
    except Exception:
        return None, False, False


def paint_padlock(painter, rect, colour="#f0f0f0", outline="#1e232b"):
    """Draw a small padlock (SciForge's own drawing) filling `rect` (a QRect)."""
    from .compat import QtCore, QtGui

    painter.save()
    try:
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        w, h = float(rect.width()), float(rect.height())
        x, y = float(rect.left()), float(rect.top())
        body = QtCore.QRectF(x + w * 0.12, y + h * 0.45, w * 0.76, h * 0.52)
        shackle = QtCore.QRectF(x + w * 0.27, y + h * 0.06, w * 0.46, h * 0.62)
        pen = QtGui.QPen(QtGui.QColor(outline))
        pen.setWidthF(max(1.0, w * 0.26))
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawArc(shackle, 0, 180 * 16)  # a dark rim so it reads on any icon
        pen.setColor(QtGui.QColor(colour))
        pen.setWidthF(max(1.0, w * 0.13))
        painter.setPen(pen)
        painter.drawArc(shackle, 0, 180 * 16)
        painter.setPen(QtGui.QPen(QtGui.QColor(outline), max(1.0, w * 0.08)))
        painter.setBrush(QtGui.QColor(colour))
        painter.drawRoundedRect(body, w * 0.1, w * 0.1)
    finally:
        painter.restore()


# -- inferred constraints in priority order ----------------------------------------------------------
def _lines_touch(sketch, a, b, tol=1e-6):
    """Two lines meet: an end of one on the other."""
    try:
        import Part

        ga, gb = sketch.Geometry[a], sketch.Geometry[b]
        for p in (ga.StartPoint, ga.EndPoint):
            if Part.Vertex(p).distToShape(gb.toShape())[0] <= tol:
                return True
        for p in (gb.StartPoint, gb.EndPoint):
            if Part.Vertex(p).distToShape(ga.toShape())[0] <= tol:
                return True
    except Exception:
        return True  # cannot tell: not demoted
    return False


def inference_rank(sketch, c):
    kinds = {}
    try:
        geometry = sketch.Geometry
        for g in (c.First, c.Second):
            if 0 <= g < len(geometry):
                kinds[g] = geometry[g].TypeId
    except Exception:
        pass
    line = "Part::GeomLineSegment"
    lines = kinds.get(c.First) == line and kinds.get(c.Second) == line
    touching = True
    if c.Type == "Perpendicular" and lines:
        touching = _lines_touch(sketch, c.First, c.Second)
    return core.inference_rank(c.Type, c.FirstPos, c.SecondPos, lines, touching)


def collapsed(g, tol=1e-6):
    """A sketch curve with no size left: a line of length 0, a circle or arc of radius 0."""
    if g.TypeId == "Part::GeomLineSegment":
        return (g.EndPoint - g.StartPoint).Length <= tol
    radius = getattr(g, "Radius", None)
    return radius is not None and radius <= tol


def _curves_of(constraints):
    return {g for c in constraints for g in _geos(c)}


def _collapsed_among(sketch, geos, geometry=None):
    geometry = sketch.Geometry if geometry is None else geometry
    return {g for g in geos if 0 <= g < len(geometry) and collapsed(geometry[g])}


def add_checked(sketch, constraints):
    """Add inferred constraints and keep those that fit. Fast path: all at once, one solve
    (as before this check existed). When the sketch is not clean then (a redundant or
    conflicting constraint, no solution, or a curve squeezed to nothing: guesses that only
    fit together by collapsing a line, upright and parallel to a level line, are no conflict
    to FreeCAD), the weakest guesses are taken out until it is clean and the others tried
    again, strongest first (sketch_explain_core.keep_strongest), so a weak guess (parallel)
    never pushes out a strong one (a snapped corner). Each step is one solve; constraints
    are taken out without FreeCAD's own extra solve, and the curves are put back only after
    a collapse. Returns the constraints kept (as they are now in the sketch)."""
    constraints = [c for c in constraints if c is not None]
    if not constraints:
        return []
    touched = _curves_of(constraints)
    geometry = sketch_geometry.snapshot(sketch)  # a cheap copy (only setting it back costs)
    flat_before = _collapsed_among(sketch, touched, sketch_geometry.curves(geometry))
    first = len(sketch.Constraints)
    sketch.addConstraint(constraints)
    present = list(constraints)  # in the sketch from `first` on, in this order
    state = {"collapsed": False, "stale": False, "code": 0}

    def clean():
        state["code"] = sketch.solve()
        state["collapsed"] = bool(_collapsed_among(sketch, touched) - flat_before)
        state["stale"] = False
        return state["code"] == 0 and not state["collapsed"]

    if clean():
        return list(sketch.Constraints[first:])

    def remove(c):
        at = next(k for k, x in enumerate(present) if x is c)
        sketch.delConstraint(first + at, True)  # no solve: the next step solves
        del present[at]
        if state["collapsed"]:
            # the solver squeezed a curve: the curves go back (construction flags, ids kept)
            sketch_geometry.restore(sketch, geometry)
            state["collapsed"] = False
        state["stale"] = True

    def drop(c):
        remove(c)
        return clean()

    def try_add(c):
        sketch.addConstraint(c)
        present.append(c)
        if clean():
            return True
        remove(c)
        return False

    rank = lambda c: inference_rank(sketch, c)  # noqa: E731
    kept = core.keep_strongest(constraints, rank, drop, try_add)
    if kept is None:
        # not clean even without them: it was not before. One by one, each kept when it
        # makes the sketch no worse than it was
        failed_before = state["code"] == FAILED
        conflicting, redundant = bad_sets(sketch)
        before = len(conflicting | redundant)

        def no_worse(c):
            index = sketch.addConstraint(c)
            present.append(c)
            code = sketch.solve()
            state["collapsed"] = bool(_collapsed_among(sketch, touched) - flat_before)
            state["stale"] = False
            conflicting, redundant = bad_sets(sketch)
            now = conflicting | redundant
            if (
                (code == FAILED and not failed_before)
                or index in now
                or len(now) > before
                or state["collapsed"]
            ):
                remove(c)
                return False
            return True

        kept = core.add_in_order(constraints, rank, no_worse)
    if state["stale"]:
        sketch.solve()
    if len(kept) < len(constraints):
        log(
            "sketch: inferred constraints that did not all fit: kept %s, left out %d"
            % (", ".join(c.Type for c in kept) or "none", len(constraints) - len(kept))
        )
    return list(sketch.Constraints[first:])
