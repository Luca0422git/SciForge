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

from . import log, warn
from . import sketch_explain_core as core

HIGHLIGHT_MS = 2500
PROBE_LIMIT = 150  # constraints switched off at most to find a redundancy's culprits
PROBE_SECONDS = 1.5


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
    fine); `bad`: the new ones that do not fit; `culprits`: the existing ones they fight."""

    def __init__(self, kind="", bad=(), culprits=()):
        self.kind = kind
        self.bad = list(bad)
        self.culprits = list(culprits)

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


def redundant_culprits(sketch, index, exclude=()):
    """The existing constraints that already say what constraint `index` says. FreeCAD names
    only the one it would drop, so each constraint connected to it is switched off in turn:
    the ones whose absence ends the redundancy are the culprits. The constraints are put
    back as they were (and the curves, should the solver have nudged them)."""
    cons = sketch.Constraints
    exclude = set(exclude) | {index}
    candidates = [
        j for j in sorted(component(sketch, [index])) if j not in exclude and _nameable(cons[j])
    ][:PROBE_LIMIT]
    if not candidates:
        return []
    sketch.solve()
    _conflicting, redundant = bad_sets(sketch)
    base = len(redundant)
    if index not in redundant or not base:
        return []
    geometry = sketch.Geometry
    found = []
    started = time.time()
    try:
        for j in candidates:
            if time.time() - started > PROBE_SECONDS:
                log("explain: stopped looking for culprits after %d tries" % len(found))
                break
            sketch.setActive(j, False)
            try:
                sketch.solve()
                _c, now = bad_sets(sketch)
                if index not in now and len(now) < base:
                    found.append(j)
            finally:
                sketch.setActive(j, True)
    finally:
        sketch.solve()
        _restore_geometry(sketch, geometry)
    return found or _neighbours(sketch, index)


def _restore_geometry(sketch, geometry):
    """Put the curves back if the solver moved any while constraints were switched off (it
    should not: the curves already met every constraint)."""
    try:
        now = sketch.Geometry
        if len(now) != len(geometry):
            return
        for a, b in zip(now, geometry):
            if not _same_curve(a, b):
                sketch.Geometry = geometry
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


def check_new(sketch, new, probe=True):
    """Solve and look at the constraints `new` (indices): a Finding (empty when they fit)."""
    sketch.solve()
    conflicting, redundant = bad_sets(sketch)
    new = [i for i in new if 0 <= i < len(sketch.Constraints)]
    bad = [i for i in new if i in conflicting]
    if bad:
        return Finding("conflict", bad, conflict_culprits(sketch, new))
    bad = [i for i in new if i in redundant]
    if bad:
        culprits = redundant_culprits(sketch, bad[0], exclude=new) if probe else []
        return Finding("redundant", bad, culprits)
    return Finding()


def refusal(sketch, title, finding):
    """The constraint tool's message for `finding` (sketch_explain_core.refused_constraint)."""
    text, count = words(sketch, finding.culprits)
    return core.refused_constraint(title, finding.kind, text, count)


def log_finding(where, sketch, finding):
    text, _count = words(sketch, finding.culprits, limit=12)
    log("%s: %s with %s" % (where, finding.kind or "fits", text or "(none named)"))


# -- highlighting ---------------------------------------------------------------------------------
_highlight = {"doc": None, "sketch": None, "subs": [], "timer": None, "filter": None}


def highlight(sketch, indices, ms=HIGHLIGHT_MS):
    """Select the constraints `indices` in the open sketch for a moment, so FreeCAD draws
    them in the selection colour. The next click or key anywhere, or `ms`, ends it."""
    clear_highlight()
    indices = [i for i in indices if 0 <= i < len(sketch.Constraints)]
    if not indices or not App.GuiUp:
        return
    try:
        import FreeCADGui as Gui

        from .compat import QtCore, QtWidgets

        doc, name = sketch.Document.Name, sketch.Name
        Gui.Selection.clearSelection()
        subs = ["Constraint%d" % (i + 1) for i in indices]
        for sub in subs:
            Gui.Selection.addSelection(doc, name, sub)
        _highlight.update(doc=doc, sketch=name, subs=subs)
        timer = QtCore.QTimer()
        timer.setSingleShot(True)
        timer.setInterval(ms)
        timer.timeout.connect(clear_highlight)
        timer.start()
        _highlight["timer"] = timer
        app = QtWidgets.QApplication.instance()
        if app is not None:
            watcher = _NextAction()
            app.installEventFilter(watcher)
            _highlight["filter"] = watcher
    except Exception as exc:
        warn("explain: could not highlight the constraints: %s" % exc)


def highlighted():
    """Indices of the constraints highlighted now (tests)."""
    return [int(s[len("Constraint") :]) - 1 for s in _highlight["subs"]]


def clear_highlight():
    """Unselect what highlight() selected (only that: a selection the user made meanwhile
    stays)."""
    subs = _highlight["subs"]
    doc, name = _highlight["doc"], _highlight["sketch"]
    timer, watcher = _highlight["timer"], _highlight["filter"]
    _highlight.update(doc=None, sketch=None, subs=[], timer=None, filter=None)
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
    """True when nothing in the sketch can move (Fusion's padlock): read from what the
    solver last found, no solve."""
    try:
        return core.is_fully_constrained(
            sketch.GeometryCount,
            sketch.FullyConstrained,
            sketch.DoF,
            sketch.ConflictingConstraints,
            sketch.MalformedConstraints,
            sketch.RedundantConstraints,
        )
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


def add_checked(sketch, constraints):
    """Add inferred constraints and keep those that fit. Fast path: all at once; when one or
    more turn out redundant or conflicting, they are taken out and tried again one by one,
    strongest first (sketch_explain_core.inference_rank), each kept only if the sketch stays
    clean, so a weak guess (parallel) never pushes out a strong one (a snapped corner).
    Returns the constraints kept (as they are now in the sketch)."""
    constraints = [c for c in constraints if c is not None]
    if not constraints:
        return []
    sketch.solve()
    conflicting, redundant = bad_sets(sketch)
    before = len(conflicting | redundant)
    first = len(sketch.Constraints)
    sketch.addConstraint(constraints)
    sketch.solve()
    conflicting, redundant = bad_sets(sketch)
    bad = conflicting | redundant
    if not any(i in bad for i in range(first, len(sketch.Constraints))) and len(bad) <= before:
        return list(sketch.Constraints[first:])
    for i in reversed(range(first, len(sketch.Constraints))):
        sketch.delConstraint(i)
    sketch.solve()

    def try_add(c):
        index = sketch.addConstraint(c)
        sketch.solve()
        conflicting, redundant = bad_sets(sketch)
        now = conflicting | redundant
        if index in now or len(now) > before:
            sketch.delConstraint(index)
            sketch.solve()
            return False
        return True

    kept = core.add_in_order(constraints, lambda c: inference_rank(sketch, c), try_add)
    if len(kept) < len(constraints):
        log(
            "sketch: inferred constraints tried one by one: kept %s, left out %d"
            % (", ".join(c.Type for c in kept) or "none", len(constraints) - len(kept))
        )
    return list(sketch.Constraints[first:])
