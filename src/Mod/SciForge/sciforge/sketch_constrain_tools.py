# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Collinear, Concentric, Midpoint and Curvature constraints with Fusion's pick
flow, on SciForge's own sketch handler (sketch_draw.py): start the command, click the two
things (the one under the pointer lights up, the picked ones stay lit), the constraint is
added and the command waits for the next pair; Esc ends it. With two fitting things
selected before the command, it applies at once.

FreeCAD's forms (checked in FreeCAD 1.1.4, docs/sciforge/parity/sketch.md):
- Collinear: a Tangent between two lines (FreeCAD's line-line tangency is collinearity).
- Concentric: a Coincident between the two centres.
- Midpoint: Symmetric (the line's ends about the point); on an arc: the point on the arc
  and a construction line from the centre through it that the arc's ends are symmetric
  about.
- Curvature (G2): FreeCAD's solver has no curvature constraint. A spline and a line: a
  tangent join plus the spline's third pole on the line too (curvature 0 at the join,
  exact G2); a spline and an arc, circle or another spline: tangent only (G1), said in a note.
"""

from . import log, warn
from . import sketch_build as build
from . import sketch_draw as draw
from . import sketch_infer_core as icore

LINE = ("Part::GeomLineSegment",)
ROUND = (
    "Part::GeomCircle",
    "Part::GeomArcOfCircle",
    "Part::GeomEllipse",
    "Part::GeomArcOfEllipse",
)
SPLINE = ("Part::GeomBSplineCurve",)
LINE_OR_ARC = ("Part::GeomLineSegment", "Part::GeomArcOfCircle")
CURVES = LINE + ROUND + SPLINE + ("Part::GeomArcOfHyperbola", "Part::GeomArcOfParabola")


def _con(*args):
    import Sketcher

    return Sketcher.Constraint(*args)


class PickConstraint(draw.DrawTool):
    """Click two things; `fits(picks + [item])` says whether an item can be the next pick
    (an item is (geo, pos): pos 0 for a whole curve)."""

    needs = 2
    points_ok = False  # a sketch point can be picked (Midpoint)

    def steps(self):
        return self.needs

    def item_at(self, snap):
        """The point or curve under the pointer: (geo, pos), or None."""
        geo = self.geometry()
        tol = draw.pick_pixels() * self._px()
        if self.points_ok:
            hit = icore.nearest_vertex(snap.raw, geo.verts, tol)
            if hit is not None:
                return hit[0]
        found = geo.curve_at(snap.raw, tol, kinds=CURVES)
        if found is not None:
            return (found[0], 0)
        if not self.points_ok:
            # a click on a circle's centre picks the circle
            hit = icore.nearest_vertex(snap.raw, geo.verts, tol)
            if hit is not None and hit[0][1] == 3 and hit[0][0] >= 0:
                return (hit[0][0], 0)
        return None

    def kind_of(self, item):
        geo, pos = item
        if pos != 0:
            return "point"
        return draw._type_of(self.sketch, geo)

    def fits(self, picks, item):
        return True

    def use_selection(self, selection):
        picks = []
        for item in selection:
            if self.fits(picks, item):
                picks.append(item)
            if len(picks) == self.needs:
                break
        if len(picks) == self.needs:
            self.picks = picks
            self._apply()
            self.stop()  # Fusion: with a selection made first the constraint is all

    def moved(self, snap):
        item = self.item_at(snap)
        lit = [self._shape(p) for p in self.picks]
        points = [self._point(p) for p in self.picks if p[1] != 0]
        hover = []
        if item is not None and self.fits(self.picks, item):
            if item[1] == 0:
                hover = [self._shape(item)]
            else:
                points.append(self._point(item))
        self.preview.show(picked=[s for s in lit + hover if s], points=[p for p in points if p])

    def _shape(self, item):
        if item[1] != 0:
            return []
        return draw.curve_points(self.sketch, item[0])

    def _point(self, item):
        geo = self.geometry()
        return geo.keyed.get(item)

    def released(self, press_snap, snap, moved):
        item = self.item_at(press_snap)
        if item is None or not self.fits(self.picks, item):
            self.say("%s: %s" % (self.title, self.prompt()))
            return
        if item in self.picks:
            return
        self.picks.append(item)
        if len(self.picks) < self.needs:
            self.step = len(self.picks)
            self._tell()
            return
        self._apply()
        self.picks = []
        self.step = 0
        self.preview.clear()
        self._tell()

    def _apply(self):
        doc = self.doc
        sketch = self.sketch
        first = len(sketch.Constraints)
        doc.openTransaction(self.title)
        try:
            note = self.constrain(self.picks)
            sketch.solve()
            conflicting = set(sketch.ConflictingConstraints)
            if any(i + 1 in conflicting for i in range(first, len(sketch.Constraints))):
                raise ValueError("it does not fit the sketch's other constraints")
            # what the sketch says already is dropped (FreeCAD would warn about it)
            redundant = set(sketch.RedundantConstraints)
            ours = [i for i in range(first, len(sketch.Constraints)) if i + 1 in redundant]
            for i in reversed(ours):
                sketch.delConstraint(i)
            if ours:
                sketch.solve()
            if len(sketch.Constraints) == first:
                raise ValueError("it is so already")
        except Exception as exc:
            doc.abortTransaction()
            try:
                sketch.solve()
            except Exception:
                pass
            self.say("%s: could not be added (%s)." % (self.title, _plain(exc)))
            log("%s: refused: %s" % (self.title, exc))
            return False
        doc.commitTransaction()
        self._geometry = None
        added = ", ".join(c.Type for c in sketch.Constraints[first:])
        log("%s: added (%s)" % (self.title, added))
        if note:
            self.say(note)
        return True

    def constrain(self, picks):
        """Add the constraint(s); returns a note to show, or None."""
        raise NotImplementedError


def _plain(exc):
    text = str(exc).strip().splitlines()[0] if str(exc).strip() else exc.__class__.__name__
    return text[:120]


# -- Collinear -------------------------------------------------------------------------------
class Collinear(PickConstraint):
    title = "Collinear"
    command = "SciForge_SketchCollinear"

    def prompt(self):
        return "click the first line." if not self.picks else "click the line to bring onto it."

    def fits(self, picks, item):
        return item[1] == 0 and self.kind_of(item) in LINE and item not in picks

    def constrain(self, picks):
        (a, _), (b, _) = picks
        if a < 0 and b < 0:
            raise ValueError("two fixed lines cannot be moved")
        self.sketch.addConstraint(_con("Tangent", a, b))
        return None


# -- Concentric ---------------------------------------------------------------------------
class Concentric(PickConstraint):
    title = "Concentric"
    command = "SciForge_SketchConcentric"

    def prompt(self):
        return (
            "click a circle, arc or ellipse."
            if not self.picks
            else "click the one to share its centre."
        )

    def fits(self, picks, item):
        return item[1] == 0 and self.kind_of(item) in ROUND and item not in picks

    def constrain(self, picks):
        (a, _), (b, _) = picks
        self.sketch.addConstraint(_con("Coincident", a, 3, b, 3))
        return None


# -- Midpoint ------------------------------------------------------------------------------
class Midpoint(PickConstraint):
    title = "Midpoint"
    command = "SciForge_SketchMidpoint"
    points_ok = True

    def prompt(self):
        if not self.picks:
            return "click a point, then the line or arc whose middle it goes to."
        if self.picks[0][1] != 0:
            return "click the line or arc whose middle the point goes to."
        return "click the point to put at its middle."

    def fits(self, picks, item):
        kind = self.kind_of(item)
        if item in picks:
            return False
        if not picks:
            return kind == "point" or kind in LINE_OR_ARC
        first = self.kind_of(picks[0])
        if first == "point":
            return kind in LINE_OR_ARC and item[0] != picks[0][0]
        return kind == "point" and item[0] != picks[0][0]

    def constrain(self, picks):
        point = picks[0] if picks[0][1] != 0 else picks[1]
        curve = picks[1][0] if picks[0][1] != 0 else picks[0][0]
        sketch = self.sketch
        if draw._type_of(sketch, curve) in LINE:
            sketch.addConstraint(_con("Symmetric", curve, 1, curve, 2, point[0], point[1]))
            return None
        # an arc: the point on it, on the line from the centre that bisects its ends. The
        # point is first put at the arc's middle (Fusion snaps it there): started far
        # off, the solver can settle with the constraints unmet (checked in FreeCAD)
        import Part

        g = build.geometry(sketch, curve)
        middle = g.value((g.FirstParameter + g.LastParameter) / 2.0)
        try:
            sketch.moveGeometry(point[0], point[1], middle, False)
        except Exception:
            pass
        g = build.geometry(sketch, curve)
        where = sketch.getPoint(point[0], point[1])
        line = sketch.addGeometry(Part.LineSegment(g.Center, where), True)
        first = len(sketch.Constraints)
        sketch.addConstraint(
            [
                _con("Coincident", line, 1, curve, 3),
                _con("Coincident", line, 2, point[0], point[1]),
                _con("PointOnObject", point[0], point[1], curve),
                _con("Symmetric", curve, 1, curve, 2, line),
            ]
        )
        sketch.solve()
        if any(
            abs(sketch.calculateConstraintError(i)) > 1e-6
            for i in range(first, len(sketch.Constraints))
        ):
            raise ValueError("the point cannot reach the arc's middle")
        return None


# -- Curvature ---------------------------------------------------------------------------
G2_NOTE = (
    "Curvature: FreeCAD's sketch solver has no curvature (G2) constraint for a spline and "
    "%s, so the two are made tangent (G1). A spline and a line join with matching curvature."
)


class Curvature(PickConstraint):
    title = "Curvature"
    command = "SciForge_SketchCurvature"

    def prompt(self):
        if not self.picks:
            return "click a spline, then the curve it joins."
        return (
            "click the curve joined to it."
            if self.kind_of(self.picks[0]) in SPLINE
            else ("click the spline joined to it.")
        )

    def fits(self, picks, item):
        if item[1] != 0 or item in picks or item[0] < 0:
            return False
        kind = self.kind_of(item)
        if not picks:
            return kind in SPLINE or kind in LINE_OR_ARC
        first = self.kind_of(picks[0])
        if first in SPLINE:
            return kind in LINE_OR_ARC or kind in SPLINE
        return kind in SPLINE

    def constrain(self, picks):
        sketch = self.sketch
        a, b = picks[0][0], picks[1][0]
        spline, other = (a, b) if self.kind_of(picks[0]) in SPLINE else (b, a)
        s_pos, o_pos = _closest_ends(sketch, spline, other)
        sketch.addConstraint(_con("Tangent", spline, s_pos, other, o_pos))
        kind = self.kind_of((other, 0))
        if kind in LINE and sketch.Geometry[spline].NbPoles >= 4:
            # tangent: the second pole is on the line already; curvature 0 at the join
            # (G2 with a line): the third pole on the line too
            pole = _pole_circle(sketch, spline, 2 if s_pos == 1 else -3)
            if pole is None:
                raise ValueError("the spline's control points are not shown")
            sketch.addConstraint(_con("PointOnObject", pole, 3, other))
            return None
        if kind in LINE:
            what = "a line (a spline of three control points cannot flatten at its end)"
        else:
            what = "an arc" if kind == "Part::GeomArcOfCircle" else "another spline"
        return G2_NOTE % what


def _ends(sketch, geo):
    g = sketch.Geometry[geo]
    return {1: g.StartPoint, 2: g.EndPoint}


def _closest_ends(sketch, a, b):
    """(pos on a, pos on b) of the two end points nearest each other."""
    best = None
    for pa, va in _ends(sketch, a).items():
        for pb, vb in _ends(sketch, b).items():
            d = (va - vb).Length
            if best is None or d < best[0]:
                best = (d, pa, pb)
    return best[1], best[2]


def _pole_circle(sketch, spline, index):
    """The construction circle of the spline's pole `index` (negative from the end),
    shown first when the spline's control points are hidden."""
    poles = build.conic_poles(sketch, spline)
    g = sketch.Geometry[spline]
    if len(poles) != g.NbPoles:
        try:
            sketch.exposeInternalGeometry(spline)
        except Exception as exc:
            warn("Curvature: %s" % exc)
        poles = build.conic_poles(sketch, spline)
    if len(poles) != g.NbPoles or not poles:
        return None
    return poles[index]


TOOLS = {cls.command: cls for cls in (Collinear, Concentric, Midpoint, Curvature)}
