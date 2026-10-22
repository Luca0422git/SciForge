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
from .sketch_geometry import set_geometry

LINE = "Part::GeomLineSegment"
ARC = "Part::GeomArcOfCircle"
CIRCLE = "Part::GeomCircle"
POINT = "Part::GeomPoint"
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


def _cut_end(sketch, geo, joint):
    """(the end of curve `geo` that FreeCAD's fillet tied to the fillet arc / chamfer line
    `joint`, i.e. the end it cut back; the end of `joint` there), or (None, None)."""
    for c in sketch.Constraints:
        refs = ((c.First, c.FirstPos), (c.Second, c.SecondPos))
        mine = [pos for g, pos in refs if g == geo and pos in (1, 2)]
        theirs = [pos for g, pos in refs if g == joint and pos in (1, 2)]
        if mine and theirs:
            return mine[0], theirs[0]
    return None, None


def _end_point(geometry, pos):
    return geometry.StartPoint if pos == 1 else geometry.EndPoint


def _with_end(geometry, pos, point):
    """A copy of a line or arc with its end `pos` (1 start, 2 end) moved to `point` (an arc
    keeps its circle: its range changes)."""
    g = geometry.copy()
    v = App.Vector(point[0], point[1], 0)
    if g.TypeId == LINE:
        if pos == 1:
            g.StartPoint = v
        else:
            g.EndPoint = v
        return g
    u = g.parameter(v)
    first, last = g.FirstParameter, g.LastParameter
    if pos == 1:
        first = u
        while first >= last:
            first -= 2 * math.pi
    else:
        last = u
        while last <= first:
            last += 2 * math.pi
    g.setParameterRange(first, last)
    return g


def _joint(starts_at, ends_at, centre_radius):
    """The fillet arc (centre_radius: (centre, radius)) or chamfer line from `starts_at` to
    `ends_at` (its start and end as FreeCAD made them), or None when the arc would turn the
    other way round (then the solver places it)."""
    import Part

    s = App.Vector(starts_at[0], starts_at[1], 0)
    e = App.Vector(ends_at[0], ends_at[1], 0)
    if centre_radius is None:
        return Part.LineSegment(s, e)
    (cx, cy), radius = centre_radius
    a = math.atan2(s.y - cy, s.x - cx)
    b = math.atan2(e.y - cy, e.x - cx)
    while b <= a:
        b += 2 * math.pi
    if b - a > math.pi + 1e-6:  # FreeCAD's fillet arcs turn the short way, anticlockwise
        return None
    circle = Part.Circle(App.Vector(cx, cy, 0), App.Vector(0, 0, 1), radius)
    return Part.ArcOfCircle(circle, a, b)


def give_back(sketch, picks, whole, joint, targets, originals, corner_point=None, arc=None):
    """The curves of `picks` the fillet / chamfer takes whole (`whole`: a flag each) are given
    back whole as construction geometry, with every constraint they had, and `joint` (the
    fillet arc, tangent to them; the chamfer line) ends at their far end: no sliver of them
    is left (Luca's limits, 2026-10-21: "chamfer something to the max"). FreeCAD's fillet
    first cut them back only part of the way (a curve cut to nothing breaks its corner
    constraints); here every curve is put where it ends up (`targets`: where the joint meets
    each pick; `originals`: the picks as they were; `arc`: (centre, radius) of the fillet
    arc, None for a chamfer line), so the solver moves nothing (in a sketch with free
    curves it otherwise dragged them away). The old corner stays: `corner_point` (two lines:
    FreeCAD's construction point, on both) or the curve's own end there, kept on the other
    curve. Raises RuntimeError when FreeCAD's tie at a cut end is missing (the caller's
    transaction is then aborted). Returns {curve given back: its far end}."""
    import Sketcher

    ends = {geo: _cut_end(sketch, geo, joint) for geo in picks}
    if any(cut is None for cut, _j in ends.values()):
        raise RuntimeError("FreeCAD's fillet left a curve without its tie")
    taken = [geo for geo, flag in zip(picks, whole) if flag]
    for geo in taken:
        cut = ends[geo][0]
        for index in range(len(sketch.Constraints) - 1, -1, -1):
            c = sketch.Constraints[index]
            refs = ((c.First, c.FirstPos), (c.Second, c.SecondPos), (c.Third, c.ThirdPos))
            on_corner = (
                corner_point is not None
                and c.Type == "PointOnObject"
                and c.First == corner_point
                and c.Second == geo
            )
            if (geo, cut) in refs or on_corner:
                sketch.delConstraint(index)  # the tie at the cut end; the corner on it
    changes = {}
    at = {}  # joint end -> where it goes
    for geo in picks:
        cut, joint_end = ends[geo]
        at[joint_end] = targets[geo]
        if geo in taken:
            changes[geo] = originals[geo]
        else:
            changes[geo] = _with_end(sketch.Geometry[geo], cut, targets[geo])
    if set(at) == {1, 2}:
        made = _joint(at[1], at[2], arc)
        if made is not None:
            changes[joint] = made
    set_geometry(sketch, changes)
    added = []
    for geo in taken:
        cut, joint_end = ends[geo]
        if corner_point is not None:
            added.append(Sketcher.Constraint("Coincident", corner_point, 1, geo, cut))
        else:  # the curve's own end stays at the corner, if it was there (curves that met)
            other = [g for g in picks if g != geo][0]
            end = _end_point(originals[geo], cut)
            if other not in taken:
                if sketch.isPointOnCurve(other, end.x, end.y):
                    added.append(Sketcher.Constraint("PointOnObject", geo, cut, other))
            elif geo == taken[-1]:
                if (end - _end_point(originals[other], ends[other][0])).Length < 1e-7:
                    added.append(Sketcher.Constraint("Coincident", geo, cut, other, ends[other][0]))
        kind = "Tangent" if arc is not None else "Coincident"
        added.append(Sketcher.Constraint(kind, geo, 3 - cut, joint, joint_end))
    if added:
        sketch.addConstraint(added)
    for geo in taken:
        if not sketch.getConstruction(geo):
            sketch.toggleConstruction(geo)
    return {geo: 3 - ends[geo][0] for geo in taken}


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
        self._largest = {}  # the largest radius that fits, per pair of curves and picks

    def steps(self):
        return 3

    def _enter_step(self, step):
        if step == 0:
            self.refs = []
            if getattr(self, "limits", None) is not None:
                self.limits.note = ""
            self._largest = {}
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
        """`r` held at the largest radius that fits these two curves: the fillet then runs to
        the far end of one of them and takes it whole (found once for them, exactly, then
        reused on every pointer move). A radius within the box's precision of it is that
        largest one too, so no sliver of a curve is left. The text by the pointer says so."""
        before = self.limits.note
        held, note = r, ""
        try:
            if r is not None and r > 0:
                key = value_limits.make_key("sketch_fillet", c1, c2, self.refs)
                if key not in self._largest:
                    self._largest[key] = core.largest_radius(c1, c2, self.refs[0], self.refs[1], r)
                cap = self._largest[key]
                if cap is not None and r > cap + 1e-9:
                    held = cap
                    if typed:
                        note = value_limits.note_typed(r, cap)
                    else:
                        note = value_limits.note_reached(cap, "hi")
                elif cap is not None and cap - r < self.limits.step():
                    held = cap  # less than the box's precision short of it: take it whole
                    note = value_limits.note_reached(cap, "hi")
        except Exception:
            return r
        self.limits.note = note
        if note != before:
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
        c1, c2 = self._curve(g1), self._curve(g2)
        whole = core.takes_whole(c1, c2, r, self.refs[0], self.refs[1])
        originals = {g: sketch.Geometry[g].copy() for g in (g1, g2)}
        before = len(sketch.Geometry)
        # FreeCAD's fillet: the arc, the curves trimmed to it, tangents; two lines keep
        # their corner as a construction point with its constraints (FreeCAD's tool too).
        # A curve the fillet takes whole: first a smaller one (a curve cut to nothing breaks
        # FreeCAD's corner constraints), then the curve is given back whole (give_back).
        sketch.fillet(g1, g2, refs[0], refs[1], r * 0.5 if any(whole) else r, True, lines, False)
        new = list(range(before, len(sketch.Geometry)))
        arcs = [i for i in new if sketch.Geometry[i].TypeId == ARC]
        if len(arcs) != 1:
            raise RuntimeError("FreeCAD's sketch fillet did not round that corner")
        arc = arcs[0]
        if any(whole):
            centre, t1, t2 = core.check(c1, c2, r, self.refs[0], self.refs[1])
            points = [i for i in new if sketch.Geometry[i].TypeId == POINT]
            corner = points[0] if points else None
            targets = {g1: t1, g2: t2}
            give_back(sketch, (g1, g2), whole, arc, targets, originals, corner, (centre, r))
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
