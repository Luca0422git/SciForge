# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's sketch Chamfer (SKETCH > MODIFY > Chamfer), on SciForge's own drawing handler
(sketch_draw.DrawTool).

Fusion (Autodesk help "Add chamfers to sketch geometry"): choose the chamfer type (Equal
distance, Distance and angle, Two distances), pick the corner (a point where two lines
meet, or the two lines), then drag or type the values; the chamfer line replaces the
corner and the values are dimensions of the sketch.

Here: the type is in a small box at the top left of the view (the last one is
remembered); click a corner point, or the two lines (on the parts that stay); the
pointer gives the distance (Equal distance: the chamfer runs through it), the value boxes
take typed values (Tab between them, Enter makes the chamfer). FreeCAD's sketch fillet in
chamfer mode trims the lines and keeps the old corner as a construction point (with the
constraints that were on the corner moved to it); its helper arc goes again and the values
become dimensions from that corner point: the first distance; Equal distance: the second
distance follows the first (an expression, fx); Distance and angle: the angle between the
first line and the chamfer; Two distances: both. The maths is sketch_chamfer_core.py.
Between two lines, a distance past what the lines can take (the pointer far out, or a
number typed) stops at the largest that fits and the text by the pointer says so (Luca,
2026-10-21; Fusion refuses it: value_limits.py). Never lets an exception out (warn() and
carry on).
"""

import math

import FreeCAD as App

from . import log, value_limits, warn
from . import sketch_chamfer_core as core
from . import sketch_draw as draw
from .compat import QtCore, QtWidgets
from .sketch_draw import ANGLE, LENGTH, Field
from .sketch_fillet_tool import give_back
from .sketch_geometry import set_geometry

CHOOSER_NAME = "SciForgeSketchChamferType"
CHOOSER_STYLE = (
    "QWidget#SciForgeSketchChamferType { background: #2b2f36; border: 1px solid #4a5260;"
    " border-radius: 3px; } QLabel { color: #e8edf3; padding: 0 2px; }"
)
LINE = "Part::GeomLineSegment"
ARC = "Part::GeomArcOfCircle"


class TypeChooser(QtWidgets.QWidget):
    """The chamfer type, at the top left of the 3D view (Fusion's dialog has it)."""

    def __init__(self, gl, kind, on_change):
        super().__init__(gl)
        self.setObjectName(CHOOSER_NAME)
        self.setStyleSheet(CHOOSER_STYLE)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(6, 4, 6, 4)
        row.addWidget(QtWidgets.QLabel("Chamfer Type"))
        self.combo = QtWidgets.QComboBox()
        self.combo.setObjectName("SciForgeSketchChamferType_combo")
        self.combo.setFocusPolicy(QtCore.Qt.NoFocus)  # typed values go to the value boxes
        for key in core.KINDS:
            self.combo.addItem(core.LABELS[key], key)
        self.combo.setCurrentIndex(core.KINDS.index(kind))
        row.addWidget(self.combo)
        self.combo.currentIndexChanged.connect(lambda _i: on_change(self.combo.currentData()))
        self.adjustSize()
        self.move(12, 12)
        self.show()
        self.raise_()

    def set_kind(self, kind):
        index = core.KINDS.index(kind)
        if self.combo.currentIndex() != index:
            self.combo.setCurrentIndex(index)

    def discard(self):
        try:
            self.hide()
            self.setParent(None)
            self.deleteLater()
        except RuntimeError:
            pass


def _ends(geometry):
    return (
        (geometry.StartPoint.x, geometry.StartPoint.y),
        (geometry.EndPoint.x, geometry.EndPoint.y),
    )


def _arc(geometry):
    """A sketch arc as sketch_chamfer_core's (centre, radius, start angle, end angle)."""
    c = geometry.Center
    s, e = geometry.StartPoint, geometry.EndPoint
    return (
        (c.x, c.y),
        geometry.Radius,
        math.atan2(s.y - c.y, s.x - c.x),
        math.atan2(e.y - c.y, e.x - c.x),
    )


class SketchChamfer(draw.DrawTool):
    title = "Chamfer"
    command = "SciForge_SketchChamfer"
    kind = "equal"  # the type used last (Fusion remembers it)
    pick_steps = (0, 1)

    def __init__(self, session):
        super().__init__(session)
        self.keeps = []  # per picked line: the click on the part that stays, or None
        self.chooser = None
        self.made = {}  # the last chamfer made (tests): line, corner point, constraints
        self.limits = value_limits.Limiter()  # distances past what fits stop at the largest

    # -- life cycle ------------------------------------------------------------------------
    def start(self):
        super().start()
        try:
            if self.session.gl is not None:
                self.chooser = TypeChooser(self.session.gl, SketchChamfer.kind, self.set_kind)
        except Exception as exc:
            warn("Chamfer: %s" % exc)

    def stop(self):
        chooser, self.chooser = self.chooser, None
        if chooser is not None:
            chooser.discard()
        super().stop()

    def set_kind(self, kind):
        """The chamfer type changed (the box at the top left)."""
        try:
            if kind not in core.KINDS or (kind == SketchChamfer.kind and self.boxes.fields):
                return
            SketchChamfer.kind = kind
            if self.chooser is not None:
                self.chooser.set_kind(kind)
            if self.step == 2:
                self.boxes.set_fields(self.fields())
                if self.last is not None:
                    self.moved(self.last)
                self.boxes.refresh()
            self._tell()
            log("Chamfer: %s" % core.LABELS[kind])
        except Exception as exc:
            warn("Chamfer: %s" % exc)

    # -- steps -----------------------------------------------------------------------------
    def steps(self):
        return 3

    def _enter_step(self, step):
        if step == 0:
            self.keeps = []
            if getattr(self, "limits", None) is not None:
                self.limits.note = ""
        super()._enter_step(step)

    def prompt(self):
        kind = core.LABELS[SketchChamfer.kind]
        if self.step == 0:
            return "%s: click a corner, or the first line." % kind
        if self.step == 1:
            return "%s: click the second line." % kind
        note = getattr(self, "limits", None) and self.limits.note
        if note:
            return "%s: %s (Enter makes it)." % (kind, note)
        if SketchChamfer.kind == "equal":
            return "%s: move to size it, or type the distance, Enter." % kind
        if SketchChamfer.kind == "two_distances":
            return "%s: type the distance on the first line, Tab, the second, Enter." % kind
        return "%s: type the distance, Tab, the angle, Enter." % kind

    def fields(self):
        if self.step != 2:
            return []
        if SketchChamfer.kind == "equal":
            return [Field("distance", LENGTH, "D")]
        if SketchChamfer.kind == "two_distances":
            return [Field("distance", LENGTH, "D1"), Field("distance2", LENGTH, "D2")]
        return [
            Field("distance", LENGTH, "D"),
            Field("angle", ANGLE, "A", low=1e-6, high=math.pi - 1e-6),
        ]

    # -- picking the corner ----------------------------------------------------------------
    def _lines_at(self, point):
        """The lines and arcs of the sketch with an end at `point` (sketch x, y)."""
        found = []
        for i, g in enumerate(self.sketch.Geometry):
            if g.TypeId not in (LINE, ARC):
                continue
            for end in _ends(g):
                if math.hypot(end[0] - point[0], end[1] - point[1]) <= 1e-7:
                    found.append(i)
                    break
        return found

    def arc_mode(self):
        """A line and an arc are picked (SciForge's line-arc chamfer)."""
        return any(self.sketch.Geometry[g].TypeId == ARC for g in self.picks)

    def _line_first(self):
        return self.sketch.Geometry[self.picks[0]].TypeId == LINE

    def _corner(self):
        """(corner, u1, u2, reach1, reach2, angle) of the picked lines; for a line and an
        arc the dict of sketch_chamfer_core.line_arc_corner."""
        l1, l2 = self.picks
        g1, g2 = self.sketch.Geometry[l1], self.sketch.Geometry[l2]
        if ARC in (g1.TypeId, g2.TypeId):
            if g1.TypeId == ARC and g2.TypeId == ARC:
                raise core.ChamferError("a chamfer needs a line: pick a line and an arc.")
            line_first = g1.TypeId == LINE
            line, arc = (g1, g2) if line_first else (g2, g1)
            keep_line, keep_arc = self.keeps if line_first else self.keeps[::-1]
            return core.line_arc_corner(_ends(line), _arc(arc), keep_line, keep_arc)
        return core.corner(_ends(g1), _ends(g2), self.keeps[0], self.keeps[1])

    def use_selection(self, selection):
        lines = [geo for geo, pos in selection if pos == 0 and self._is_line(geo)]
        points = [(geo, pos) for geo, pos in selection if pos in (1, 2) and self._is_line(geo)]
        if len(lines) == 2:
            self.picks, self.keeps = lines, [None, None]
        elif len(points) == 1 and not lines:
            g = self.sketch.Geometry[points[0][0]]
            at = _ends(g)[points[0][1] - 1]
            found = self._lines_at(at)
            if len(found) != 2:
                return
            self.picks, self.keeps = found, [None, None]
        else:
            return
        try:
            self._corner()
        except core.ChamferError as exc:
            self.picks, self.keeps = [], []
            self.say(str(exc))
            return
        self._enter_step(2)
        self._tell()

    def _is_line(self, geo):
        """A line or an arc (what can be chamfered)."""
        try:
            return geo >= 0 and self.sketch.Geometry[geo].TypeId in (LINE, ARC)
        except Exception:
            return False

    def pick(self, snap):
        if self.step == 0 and snap.key is not None:  # a point (the origin counts)
            found = self._lines_at(snap.point)
            if len(found) == 2:
                self.picks, self.keeps = found, [None, None]
                if self._corner_ok():
                    self._enter_step(2)
                    self._tell()
                return
            if len(found) > 2:
                self.say("more than two lines meet there: click the two lines.")
                return
        hit = self.geometry().curve_at(
            snap.raw, draw.pick_pixels() * self._px(), kinds=(LINE, ARC), own=True
        )
        if hit is None or hit[0] < 0:
            self.say("click a corner where two lines meet, or a line.")
            return
        if hit[0] in self.picks:
            self.say("that line is picked already; click the other one.")
            return
        self.picks.append(hit[0])
        self.keeps.append(tuple(snap.raw))
        if len(self.picks) == 2 and not self._corner_ok():
            self.picks.pop()
            self.keeps.pop()
            return
        self.next_step()

    def _corner_ok(self):
        try:
            self._corner()
            return True
        except core.ChamferError as exc:
            self.say(str(exc))
            if len(self.keeps) == 2 and self.keeps == [None, None]:
                self.picks, self.keeps = [], []
            return False

    # -- the values ------------------------------------------------------------------------
    def values(self, snap):
        """(setback 1, setback 2, angle at the corner, the corner's data) for the pointer
        and the typed values."""
        data = self._corner()
        point, u1, u2, reach1, reach2, angle = data
        kind = SketchChamfer.kind
        given = core.pointer_values(kind, point, u1, u2, angle, snap.raw if snap else point)
        for name in ("distance", "distance2", "angle"):
            f = self.boxes.field(name)
            if f is not None:
                f.value = given.get(name)
        typed_d = self.boxes.typed("distance")
        d = given["distance"] if typed_d is None else typed_d
        second = None
        typed_2 = None
        if kind == "two_distances":
            typed_2 = self.boxes.typed("distance2")
            second = given["distance2"] if typed_2 is None else typed_2
        elif kind == "distance_angle":
            second = self.boxes.typed("angle")
        before = self.limits.note
        angle_given = second if kind == "distance_angle" else None
        d, note = self._held("distance", d, typed_d is not None, data, kind, angle_given)
        if kind == "two_distances":
            second, note2 = self._held("distance2", second, typed_2 is not None, data, kind)
            note = note or note2
        self.limits.note = note
        if note != before:
            self._tell()
        for name, value in (("distance", d), ("distance2", second)):
            f = self.boxes.field(name)
            if f is not None and self.boxes.typed(name) is None and value is not None:
                f.value = value
        s1, s2 = core.setbacks(kind, angle, d, second)
        return s1, s2, data

    def _held(self, name, value, typed, data, kind, angle=None):
        """Between two lines: (`value` held at the largest that fits them, the note). At that
        largest value the chamfer runs to the far end of a line and takes it whole (exact:
        sketch_chamfer_core.largest); a value within the box's precision of it is that
        largest one too, so no sliver of a line is left. `angle`: Distance and angle's."""
        if value is None or value <= 0:
            return value, ""
        point, u1, u2, reach1, reach2, corner_angle = data
        try:
            cap = core.largest(kind, name, corner_angle, reach1, reach2, angle)
            if cap is None or cap <= 0:
                return value, ""
            if value > cap + 1e-9:
                if typed:
                    return cap, value_limits.note_typed(value, cap)
                return cap, value_limits.note_reached(cap, "hi")
            if cap - value < self.limits.step():  # a sliver would be left: take it whole
                return cap, value_limits.note_reached(cap, "hi")
        except Exception:
            pass
        return value, ""

    def arc_values(self, snap):
        """Line and arc: (setback on the line, chord on the arc, P1, P2, data)."""
        data = self._corner()
        kind = SketchChamfer.kind
        line_first = self._line_first()
        pointer = snap.raw if snap else data["point"]
        given = core.line_arc_pointer(kind, data, pointer, line_first)
        for name in ("distance", "distance2"):
            f = self.boxes.field(name)
            if f is not None:
                f.value = given.get(name)
        d = self.boxes.typed("distance")
        d = given["distance"] if d is None else d
        second = None
        if kind == "two_distances":
            second = self.boxes.typed("distance2")
            second = given["distance2"] if second is None else second
        elif kind == "distance_angle":
            second = self.boxes.typed("angle")
        s_line, s_arc, p1, p2 = core.line_arc_values(kind, data, d, second, line_first)
        f = self.boxes.field("angle")
        if f is not None:
            f.value = core.angle_at_line(data, p1, p2)
        return s_line, s_arc, p1, p2, data

    def moved(self, snap):
        if self.step < 2:
            hit = self.geometry().curve_at(
                snap.raw, draw.pick_pixels() * self._px(), kinds=(LINE, ARC), own=True
            )
            picked = [draw.curve_points(self.sketch, g) for g in self.picks]
            if hit is not None and hit[0] >= 0 and hit[0] not in self.picks:
                picked.append(draw.curve_points(self.sketch, hit[0]))
            points = [snap.point] if snap.key is not None else []
            self.preview.show(picked=[p for p in picked if p], points=points)
            return
        picked = [draw.curve_points(self.sketch, g) for g in self.picks]
        if self.arc_mode():
            try:
                _s_line, _s_arc, p1, p2, data = self.arc_values(snap)
            except core.ChamferError:
                self.preview.show(picked=[p for p in picked if p])
                return
            point = data["point"]
            first, second = (p1, p2) if self._line_first() else (p2, p1)
        else:
            try:
                s1, s2, data = self.values(snap)
            except core.ChamferError:
                self.preview.show(picked=[p for p in picked if p])
                return
            point, u1, u2, _r1, _r2, _angle = data
            p1, p2 = core.points(point, u1, u2, s1, s2)
            first, second = p1, p2
        for name, anchor in (
            ("distance", ((point[0] + first[0]) / 2, (point[1] + first[1]) / 2)),
            ("distance2", ((point[0] + second[0]) / 2, (point[1] + second[1]) / 2)),
            ("angle", p1),
        ):
            f = self.boxes.field(name)
            if f is not None:
                f.anchor = anchor
        self.preview.show(
            curves=[[p1, p2]],
            construction=[[p1, point, p2]],
            picked=[p for p in picked if p],
            points=[point, p1, p2],
        )

    def _click(self, snap):
        if self.step in self.pick_steps:
            self.pick(snap)
            return
        if not self.boxes.take():
            return
        try:
            if self.arc_mode():
                self.arc_values(snap)
            else:
                s1, s2, data = self.values(snap)
                core.check_fits(s1, s2, data[3], data[4])
        except core.ChamferError as exc:
            self.say(str(exc))
            return
        self.snaps.append(snap)
        self.make()

    # -- making it -------------------------------------------------------------------------
    def build(self, construction):
        if self.arc_mode():
            return self._build_arc(construction)
        import Sketcher

        sketch = self.sketch
        s1, s2, data = self.values(self.snaps[-1])
        point, u1, u2, reach1, reach2, angle = data
        core.check_fits(s1, s2, reach1, reach2)
        whole = (core.takes_whole(s1, reach1), core.takes_whole(s2, reach2))
        l1, l2 = self.picks
        # FreeCAD's fillet in chamfer mode: trims both lines, keeps the corner as a
        # construction point (constraints on the old corner move to it). A line the
        # chamfer takes whole: first cut less (a line cut to nothing breaks FreeCAD's corner
        # constraints), then it is given back whole and the chamfer runs to its far end.
        refs = [
            App.Vector(point[0] + u[0] * r / 2, point[1] + u[1] * r / 2, 0)
            for u, r in ((u1, reach1), (u2, reach2))
        ]
        first = min(s1, s2) * (0.5 if any(whole) else 1.0)
        radius = core.fillet_radius(first, angle)
        originals = {g: sketch.Geometry[g].copy() for g in (l1, l2)}
        before = len(sketch.Geometry)
        sketch.fillet(l1, l2, refs[0], refs[1], radius, True, True, True)
        new = list(range(before, len(sketch.Geometry)))
        arcs = [i for i in new if sketch.Geometry[i].TypeId == "Part::GeomArcOfCircle"]
        if len(new) != 3 or len(arcs) != 1:
            raise RuntimeError("FreeCAD's sketch chamfer did not cut that corner")
        sketch.delGeometry(arcs[0])  # its helper arc (it would hold both setbacks equal)
        new = list(range(before, len(sketch.Geometry)))
        corner = [i for i in new if sketch.Geometry[i].TypeId == "Part::GeomPoint"][0]
        line = [i for i in new if sketch.Geometry[i].TypeId == LINE][0]
        if construction:
            sketch.toggleConstruction(line)
        ch = sketch.Geometry[line]
        p1 = App.Vector(point[0] + u1[0] * first, point[1] + u1[1] * first, 0)
        first_end = 1 if (ch.StartPoint - p1).Length <= (ch.EndPoint - p1).Length else 2
        on1 = ch.StartPoint if first_end == 1 else ch.EndPoint
        on2 = ch.EndPoint if first_end == 1 else ch.StartPoint
        pos1 = self._end_at(l1, on1)
        pos2 = self._end_at(l2, on2)
        to1, to2 = pos1, pos2  # where the dimensions end: a line taken whole, its far end
        if any(whole):
            p1, p2 = core.points(point, u1, u2, s1, s2)
            far = give_back(sketch, (l1, l2), whole, line, {l1: p1, l2: p2}, originals, corner)
            to1, to2 = far.get(l1, pos1), far.get(l2, pos2)
        kind = SketchChamfer.kind
        added = [sketch.addConstraint(Sketcher.Constraint("Distance", corner, 1, l1, to1, s1))]
        if kind == "distance_angle":
            added.append(
                sketch.addConstraint(self._angle(l1, pos1, line, first_end, s1, s2, angle))
            )
        else:
            added.append(
                sketch.addConstraint(Sketcher.Constraint("Distance", corner, 1, l2, to2, s2))
            )
        self._settle_values(added, kind)
        self.made = {"line": line, "corner": corner, "constraints": added, "kind": kind}
        return []

    def _settle_values(self, added, kind):
        """Values the sketch already fixes become references; Equal distance: the second
        follows the first (fx), as Fusion's one value sizes both sides."""
        sketch = self.sketch
        sketch.solve()
        bad = set(sketch.RedundantConstraints) | set(sketch.ConflictingConstraints)
        for index in added:
            if index + 1 in bad:
                sketch.setDriving(index, False)  # the sketch already fixes it: a reference
        if kind == "equal" and not (bad & {added[0] + 1, added[1] + 1}):
            name = self._free_name()
            sketch.renameConstraint(added[0], name)
            sketch.renameConstraint(added[1], name + "b")
            sketch.setExpression("Constraints.%sb" % name, "Constraints.%s" % name)

    def _build_arc(self, construction):
        """A line and an arc: both are cut back to P1 and P2 (their constraints at the old
        corner go: that point is no longer on them, as FreeCAD's fillet of curves does), a
        chamfer line joins them, and the old corner stays as a construction point on both
        (where the line meets the arc's circle) with the values as dimensions from it."""
        import Part
        import Sketcher

        sketch = self.sketch
        s_line, s_arc, p1, p2, data = self.arc_values(self.snaps[-1])
        kind = SketchChamfer.kind
        line_first = self._line_first()
        g1, g2 = self.picks
        line_geo, arc_geo = (g1, g2) if line_first else (g2, g1)
        point = data["point"]
        corner_v = App.Vector(point[0], point[1], 0)
        q1 = App.Vector(p1[0], p1[1], 0)
        q2 = App.Vector(p2[0], p2[1], 0)
        line_pos = self._end_at(line_geo, corner_v)
        arc_pos = self._end_at(arc_geo, corner_v)
        on_corner = {(line_geo, line_pos), (arc_geo, arc_pos)}
        dropped = []
        for index in range(len(sketch.Constraints) - 1, -1, -1):
            c = sketch.Constraints[index]
            ends = {(c.First, c.FirstPos), (c.Second, c.SecondPos), (c.Third, c.ThirdPos)}
            if ends & on_corner:
                dropped.append(c.Type)
                sketch.delConstraint(index)
        geos = list(sketch.Geometry)
        line_g = geos[line_geo]
        if line_pos == 1:
            line_g.StartPoint = q1
        else:
            line_g.EndPoint = q1
        arc_g = geos[arc_geo]
        u = arc_g.parameter(q2)
        first, last = arc_g.FirstParameter, arc_g.LastParameter
        if arc_pos == 1:
            first = u
            while first >= last:
                first -= 2 * math.pi
        else:
            last = u
            while last <= first:
                last += 2 * math.pi
        arc_g.setParameterRange(first, last)
        # (assigning sketch.Geometry turned construction points into normal ones)
        set_geometry(sketch, {line_geo: line_g, arc_geo: arc_g})
        chamfer = sketch.addGeometry(Part.LineSegment(q1, q2), bool(construction))
        corner = sketch.addGeometry(Part.Point(corner_v), True)
        sketch.addConstraint(
            [
                Sketcher.Constraint("Coincident", chamfer, 1, line_geo, line_pos),
                Sketcher.Constraint("Coincident", chamfer, 2, arc_geo, arc_pos),
                Sketcher.Constraint("PointOnObject", corner, 1, line_geo),
                Sketcher.Constraint("PointOnObject", corner, 1, arc_geo),
            ]
        )
        on_line = sketch.addConstraint(
            Sketcher.Constraint("Distance", corner, 1, line_geo, line_pos, s_line)
        )
        if kind == "distance_angle":
            far = 3 - line_pos
            g = sketch.Geometry[line_geo]
            start = g.StartPoint if far == 1 else g.EndPoint
            end = g.EndPoint if far == 1 else g.StartPoint
            a, b = end - start, q2 - q1
            signed = math.atan2(a.x * b.y - a.y * b.x, a.x * b.x + a.y * b.y)
            alpha = core.angle_at_line(data, p1, p2)
            if signed >= 0:
                angle = Sketcher.Constraint("Angle", line_geo, far, chamfer, 1, alpha)
            else:
                angle = Sketcher.Constraint("Angle", chamfer, 1, line_geo, far, alpha)
            second = sketch.addConstraint(angle)
        else:
            second = sketch.addConstraint(
                Sketcher.Constraint("Distance", corner, 1, arc_geo, arc_pos, s_arc)
            )
        # D1 is the first curve picked's (the arc's when it came first)
        added = [on_line, second] if line_first or kind != "two_distances" else [second, on_line]
        self._settle_values(added, kind)
        if dropped:
            log("Chamfer: constraints at the old corner removed: %s" % ", ".join(dropped))
        self.made = {"line": chamfer, "corner": corner, "constraints": added, "kind": kind}
        return []

    def _end_at(self, geo, where):
        g = self.sketch.Geometry[geo]
        return 1 if (g.StartPoint - where).Length <= (g.EndPoint - where).Length else 2

    def _angle(self, l1, pos1, line, first_end, s1, s2, angle):
        """The angle between the first line and the chamfer, inside the corner: FreeCAD's
        Angle runs from line 1's far end towards the chamfer's end on it, then along the
        chamfer; the lines are put in the order that makes it count anticlockwise."""
        import Sketcher

        g = self.sketch.Geometry[l1]
        far = 3 - pos1
        start = g.StartPoint if far == 1 else g.EndPoint
        end = g.EndPoint if far == 1 else g.StartPoint
        ch = self.sketch.Geometry[line]
        q1 = ch.StartPoint if first_end == 1 else ch.EndPoint
        q2 = ch.EndPoint if first_end == 1 else ch.StartPoint
        a, b = end - start, q2 - q1
        signed = math.atan2(a.x * b.y - a.y * b.x, a.x * b.x + a.y * b.y)
        typed = self.boxes.typed("angle")
        alpha = typed if typed is not None else core.chamfer_angle(angle, s1, s2)
        if signed >= 0:
            return Sketcher.Constraint("Angle", l1, far, line, first_end, alpha)
        return Sketcher.Constraint("Angle", line, first_end, l1, far, alpha)

    def _free_name(self):
        names = {c.Name for c in self.sketch.Constraints if c.Name}
        n = 1
        while "Chamfer%d" % n in names or "Chamfer%db" % n in names:
            n += 1
        return "Chamfer%d" % n

    def after_make(self, kept):
        log("Chamfer: %s corner cut" % core.LABELS[self.made.get("kind", "equal")])
        if self.limits.note:
            self.say(self.limits.note)  # a typed distance was held at the largest that fits
            self.limits.note = ""
