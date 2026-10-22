# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's sketch Fillet (SKETCH > MODIFY > Fillet) on SciForge's own drawing handler
(sketch_draw.DrawTool), for lines, arcs and circles in any pair.

Fusion (Autodesk help "Sketch modification tools"): pick a corner, two lines, two arcs or
a line and an arc, then drag or type the radius; Enter makes the fillet; the arc is
tangent to both curves, they are trimmed to it and the radius is a dimension.

Here: click a point where two curves end (the corner), or the two curves on the parts
that stay; the pointer gives the radius (the arc passes as far from the corner as the
pointer is) and the R box takes a typed one (Enter, or a click, makes it). FreeCAD's own
sketch fillet makes the arc and trims (SketchObject::fillet: the same rule as the
preview, sketch_fillet_core.py); a corner of two lines keeps its old point as a
construction point with the constraints that were on it, as FreeCAD's fillet tool does.
The radius becomes a Radius dimension. One undo step per fillet; the tool waits for the
next corner, Esc ends it. A radius past what the curves can take (the pointer far out, or
a number typed) stops at the largest that fits, and the text by the pointer says so (Luca,
2026-10-21; Fusion refuses it: value_limits.py).

FreeCAD's own fillet tool picks through FreeCAD's preselection, which never registered a
click on CI's virtual screen (CI #123-#126): this tool computes its picks itself.
Never lets an exception out (warn() and carry on).
"""

import math

import FreeCAD as App

from . import log, value_limits
from . import sketch_draw as draw
from . import sketch_fillet_core as core
from .sketch_draw import LENGTH, Field

LINE = "Part::GeomLineSegment"
ARC = "Part::GeomArcOfCircle"
CIRCLE = "Part::GeomCircle"
KINDS = (LINE, ARC, CIRCLE)


def _xy(v):
    return (v.x, v.y)


def curve_of(geometry):
    """The sketch geometry as sketch_fillet_core's curve tuple, or None."""
    kind = geometry.TypeId
    if kind == LINE:
        return ("line", _xy(geometry.StartPoint), _xy(geometry.EndPoint))
    if kind == ARC:
        c = geometry.Center
        s, e = geometry.StartPoint, geometry.EndPoint
        return (
            "arc",
            _xy(c),
            geometry.Radius,
            math.atan2(s.y - c.y, s.x - c.x),
            math.atan2(e.y - c.y, e.x - c.x),
        )
    if kind == CIRCLE:
        return ("circle", _xy(geometry.Center), geometry.Radius)
    return None


def middle(geometry):
    """A point in the middle of a curve (FreeCAD's corner fillet uses the lines' middles
    as the parts that stay)."""
    if geometry.TypeId == LINE:
        return _xy((geometry.StartPoint + geometry.EndPoint) * 0.5)
    try:
        t = (geometry.FirstParameter + geometry.LastParameter) / 2.0
        return _xy(geometry.value(t))
    except Exception:
        return _xy(geometry.StartPoint)


class SketchFillet(draw.DrawTool):
    title = "Fillet"
    command = "SciForge_SketchFillet"
    pick_steps = (0, 1)

    def __init__(self, session):
        super().__init__(session)
        self.refs = []  # per picked curve: the click on the part that stays
        self.made = {}  # the last fillet made (tests): arc, radius, constraint
        self.limits = value_limits.Limiter()  # radii past what fits stop at the largest

    def steps(self):
        return 3

    def _enter_step(self, step):
        if step == 0:
            self.refs = []
            if getattr(self, "limits", None) is not None:
                self.limits.note = ""
        super()._enter_step(step)

    def prompt(self):
        if self.step == 0:
            return "click a corner, or the first curve."
        if self.step == 1:
            return "click the second curve."
        note = getattr(self, "limits", None) and self.limits.note
        if note:
            return "%s (Enter makes it)." % note
        return "move to size it, or type the radius, Enter."

    def fields(self):
        if self.step != 2:
            return []
        return [Field("radius", LENGTH, "R")]

    # -- picking -----------------------------------------------------------------------------
    def _curves_at(self, point):
        """Lines and arcs of the sketch with an end at `point`."""
        found = []
        for i, g in enumerate(self.sketch.Geometry):
            if g.TypeId not in (LINE, ARC):
                continue
            for end in (g.StartPoint, g.EndPoint):
                if math.hypot(end.x - point[0], end.y - point[1]) <= 1e-7:
                    found.append(i)
                    break
        return found

    def _curve(self, geo):
        return curve_of(self.sketch.Geometry[geo])

    def _usable(self, geo):
        try:
            return geo >= 0 and self.sketch.Geometry[geo].TypeId in KINDS
        except Exception:
            return False

    def use_selection(self, selection):
        curves = [geo for geo, pos in selection if pos == 0 and self._usable(geo)]
        points = [(geo, pos) for geo, pos in selection if pos in (1, 2) and self._usable(geo)]
        if len(curves) == 2:
            picks = curves
        elif len(points) == 1 and not curves:
            g = self.sketch.Geometry[points[0][0]]
            at = _xy(g.StartPoint if points[0][1] == 1 else g.EndPoint)
            picks = self._curves_at(at)
            if len(picks) != 2:
                return
        else:
            return
        self.picks = picks
        self.refs = [middle(self.sketch.Geometry[g]) for g in picks]
        if self._pair_ok():
            self._enter_step(2)
            self._tell()
        else:
            self.picks, self.refs = [], []

    def pick(self, snap):
        if self.step == 0 and snap.key is not None:  # a point (the origin counts)
            found = self._curves_at(snap.point)
            if len(found) == 2:
                self.picks = found
                self.refs = [middle(self.sketch.Geometry[g]) for g in found]
                if self._pair_ok():
                    self._enter_step(2)
                    self._tell()
                else:
                    self.picks, self.refs = [], []
                return
            if len(found) > 2:
                self.say("more than two curves meet there: click the two curves.")
                return
        hit = self.geometry().curve_at(
            snap.raw, draw.pick_pixels() * self._px(), kinds=KINDS, own=True
        )
        if hit is None or hit[0] < 0:
            self.say("click a corner, a line, an arc or a circle.")
            return
        if hit[0] in self.picks:
            self.say("that curve is picked already; click the other one.")
            return
        self.picks.append(hit[0])
        self.refs.append(tuple(snap.raw))
        if len(self.picks) == 2 and not self._pair_ok():
            self.picks.pop()
            self.refs.pop()
            return
        self.next_step()

    def _pair_ok(self):
        c1, c2 = self._curve(self.picks[0]), self._curve(self.picks[1])
        if c1 is None or c2 is None:
            self.say("only lines, arcs and circles can be filleted.")
            return False
        try:
            core.fillet(c1, c2, core.suggested(c1, c2), self.refs[0], self.refs[1])
        except core.FilletError:
            # parallel lines, curves that cannot touch one arc: refused at once
            if not self._any_radius(c1, c2):
                self.say("no arc can touch both of those curves.")
                return False
        return True

    def _any_radius(self, c1, c2):
        size = core.suggested(c1, c2)
        for k in (0.01, 0.1, 0.5, 2.0, 5.0):
            try:
                core.fillet(c1, c2, size * k, self.refs[0], self.refs[1])
                return True
            except core.FilletError:
                continue
        return False

    # -- the radius ----------------------------------------------------------------------------
    def radius(self, snap):
        """The radius: typed, else the pointer's."""
        typed = self.boxes.typed("radius")
        c1, c2 = self._curve(self.picks[0]), self._curve(self.picks[1])
        given = None
        if snap is not None:
            given = core.radius_through(
                c1, c2, self.refs[0], self.refs[1], snap.raw, 20 * core.suggested(c1, c2)
            )
        if given is None:
            given = core.suggested(c1, c2)
        f = self.boxes.field("radius")
        r = typed if typed is not None else given
        held = self._held(c1, c2, r, typed is not None)
        if f is not None:
            f.value = held if typed is None else given
        return held

    def _held(self, c1, c2, r, typed):
        """`r` held at the largest radius that fits these two curves (found once for them,
        then reused on every pointer move); the text by the pointer says so."""
        before = self.limits.note
        try:
            key = value_limits.make_key("sketch_fillet", c1, c2, self.refs)
            held = self.limits.clamp(key, r, typed)
            if held == r and r > 0:
                try:
                    core.check(c1, c2, r, self.refs[0], self.refs[1])
                except core.FilletError as exc:
                    if value_limits.is_limit_error(str(exc)):
                        refs = list(self.refs)

                        def works(value):
                            core.check(c1, c2, value, refs[0], refs[1])
                            return True

                        start = min(r / 2.0, core.suggested(c1, c2) * 0.01)
                        limit = self.limits.find(key, works, r, start)
                        if limit is not None:
                            self.limits.limited(key, r, limit, typed)
                            held = limit
        except Exception:
            return r
        if self.limits.note != before:
            self._tell()
        return held

    def moved(self, snap):
        if self.step < 2:
            hit = self.geometry().curve_at(
                snap.raw, draw.pick_pixels() * self._px(), kinds=KINDS, own=True
            )
            picked = [draw.curve_points(self.sketch, g) for g in self.picks]
            if hit is not None and hit[0] >= 0 and hit[0] not in self.picks:
                picked.append(draw.curve_points(self.sketch, hit[0]))
            points = [snap.point] if snap.key is not None else []
            self.preview.show(picked=[p for p in picked if p], points=points)
            return
        picked = [draw.curve_points(self.sketch, g) for g in self.picks]
        c1, c2 = self._curve(self.picks[0]), self._curve(self.picks[1])
        r = self.radius(snap)
        try:
            centre, t1, t2 = core.check(c1, c2, r, self.refs[0], self.refs[1])
        except core.FilletError:
            self.preview.show(picked=[p for p in picked if p])
            return
        f = self.boxes.field("radius")
        if f is not None:
            f.anchor = core.arc_points(centre, t1, t2, 2)[1]
        self.preview.show(
            curves=[core.arc_points(centre, t1, t2)],
            picked=[p for p in picked if p],
            points=[t1, t2],
        )

    def _click(self, snap):
        if self.step in self.pick_steps:
            self.pick(snap)
            return
        if not self.boxes.take():
            return
        c1, c2 = self._curve(self.picks[0]), self._curve(self.picks[1])
        try:
            core.check(c1, c2, self.radius(snap), self.refs[0], self.refs[1])
        except core.FilletError as exc:
            self.say(str(exc))
            return
        self.snaps.append(snap)
        self.make()

    # -- making it ---------------------------------------------------------------------------
    def build(self, construction):
        import Sketcher

        sketch = self.sketch
        r = self.radius(self.snaps[-1])
        g1, g2 = self.picks
        lines = all(sketch.Geometry[g].TypeId == LINE for g in (g1, g2))
        refs = [App.Vector(x, y, 0) for x, y in self.refs]
        before = len(sketch.Geometry)
        # FreeCAD's fillet: the arc, the curves trimmed to it, tangents; two lines keep
        # their corner as a construction point with its constraints (FreeCAD's tool too)
        sketch.fillet(g1, g2, refs[0], refs[1], r, True, lines, False)
        new = list(range(before, len(sketch.Geometry)))
        arcs = [i for i in new if sketch.Geometry[i].TypeId == ARC]
        if len(arcs) != 1:
            raise RuntimeError("FreeCAD's sketch fillet did not round that corner")
        arc = arcs[0]
        if construction:
            sketch.toggleConstruction(arc)
        index = sketch.addConstraint(Sketcher.Constraint("Radius", arc, r))
        sketch.solve()
        if index + 1 in set(sketch.RedundantConstraints) | set(sketch.ConflictingConstraints):
            sketch.setDriving(index, False)  # the sketch already sets it: a reference
        self.made = {"arc": arc, "radius": r, "constraint": index}
        return []

    def after_make(self, kept):
        log("Fillet: radius %.4g mm" % self.made.get("radius", 0.0))
        if self.limits.note:
            self.say(self.limits.note)  # a typed radius was held at the largest that fits
            self.limits.note = ""
