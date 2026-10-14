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
Never lets an exception out (warn() and carry on).
"""

import math

import FreeCAD as App

from . import log, warn
from . import sketch_chamfer_core as core
from . import sketch_draw as draw
from .compat import QtCore, QtWidgets
from .sketch_draw import ANGLE, LENGTH, Field

CHOOSER_NAME = "SciForgeSketchChamferType"
CHOOSER_STYLE = (
    "QWidget#SciForgeSketchChamferType { background: #2b2f36; border: 1px solid #4a5260;"
    " border-radius: 3px; } QLabel { color: #e8edf3; padding: 0 2px; }"
)
LINE = "Part::GeomLineSegment"


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
        super()._enter_step(step)

    def prompt(self):
        kind = core.LABELS[SketchChamfer.kind]
        if self.step == 0:
            return "%s: click a corner, or the first line." % kind
        if self.step == 1:
            return "%s: click the second line." % kind
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
        """The lines of the sketch with an end at `point` (sketch x, y)."""
        found = []
        for i, g in enumerate(self.sketch.Geometry):
            if g.TypeId != LINE:
                continue
            for end in _ends(g):
                if math.hypot(end[0] - point[0], end[1] - point[1]) <= 1e-7:
                    found.append(i)
                    break
        return found

    def _corner(self):
        """(corner, u1, u2, reach1, reach2, angle) of the picked lines."""
        l1, l2 = self.picks
        g1, g2 = self.sketch.Geometry[l1], self.sketch.Geometry[l2]
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
        try:
            return geo >= 0 and self.sketch.Geometry[geo].TypeId == LINE
        except Exception:
            return False

    def pick(self, snap):
        if self.step == 0 and snap.key is not None and snap.key[0] >= 0:
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
        hit = self.geometry().curve_at(snap.raw, draw.pick_pixels() * self._px(), kinds=(LINE,))
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
        d = self.boxes.typed("distance")
        d = given["distance"] if d is None else d
        second = None
        if kind == "two_distances":
            second = self.boxes.typed("distance2")
            second = given["distance2"] if second is None else second
        elif kind == "distance_angle":
            second = self.boxes.typed("angle")
        s1, s2 = core.setbacks(kind, angle, d, second)
        return s1, s2, data

    def moved(self, snap):
        if self.step < 2:
            hit = self.geometry().curve_at(snap.raw, draw.pick_pixels() * self._px(), kinds=(LINE,))
            picked = [draw.curve_points(self.sketch, g) for g in self.picks]
            if hit is not None and hit[0] >= 0 and hit[0] not in self.picks:
                picked.append(draw.curve_points(self.sketch, hit[0]))
            points = [snap.point] if snap.key is not None else []
            self.preview.show(picked=[p for p in picked if p], points=points)
            return
        picked = [draw.curve_points(self.sketch, g) for g in self.picks]
        try:
            s1, s2, data = self.values(snap)
        except core.ChamferError:
            self.preview.show(picked=[p for p in picked if p])
            return
        point, u1, u2, _r1, _r2, angle = data
        p1, p2 = core.points(point, u1, u2, s1, s2)
        for name, anchor in (
            ("distance", ((point[0] + p1[0]) / 2, (point[1] + p1[1]) / 2)),
            ("distance2", ((point[0] + p2[0]) / 2, (point[1] + p2[1]) / 2)),
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
            s1, s2, data = self.values(snap)
            core.check_fits(s1, s2, data[3], data[4])
        except core.ChamferError as exc:
            self.say(str(exc))
            return
        self.snaps.append(snap)
        self.make()

    # -- making it -------------------------------------------------------------------------
    def build(self, construction):
        import Sketcher

        sketch = self.sketch
        s1, s2, data = self.values(self.snaps[-1])
        point, u1, u2, reach1, reach2, angle = data
        core.check_fits(s1, s2, reach1, reach2)
        l1, l2 = self.picks
        # FreeCAD's fillet in chamfer mode: trims both lines, keeps the corner as a
        # construction point (constraints on the old corner move to it).
        refs = [
            App.Vector(point[0] + u[0] * r / 2, point[1] + u[1] * r / 2, 0)
            for u, r in ((u1, reach1), (u2, reach2))
        ]
        radius = core.fillet_radius(min(s1, s2), angle)
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
        p1 = App.Vector(point[0] + u1[0] * s1, point[1] + u1[1] * s1, 0)
        first_end = 1 if (ch.StartPoint - p1).Length <= (ch.EndPoint - p1).Length else 2
        on1 = ch.StartPoint if first_end == 1 else ch.EndPoint
        on2 = ch.EndPoint if first_end == 1 else ch.StartPoint
        pos1 = self._end_at(l1, on1)
        pos2 = self._end_at(l2, on2)
        kind = SketchChamfer.kind
        added = [sketch.addConstraint(Sketcher.Constraint("Distance", corner, 1, l1, pos1, s1))]
        if kind == "distance_angle":
            added.append(
                sketch.addConstraint(self._angle(l1, pos1, line, first_end, s1, s2, angle))
            )
        else:
            added.append(
                sketch.addConstraint(Sketcher.Constraint("Distance", corner, 1, l2, pos2, s2))
            )
        sketch.solve()
        bad = set(sketch.RedundantConstraints) | set(sketch.ConflictingConstraints)
        for index in added:
            if index + 1 in bad:
                sketch.setDriving(index, False)  # the sketch already fixes it: a reference
        if kind == "equal" and not (bad & {added[0] + 1, added[1] + 1}):
            # Fusion: one value sizes both sides; the second follows the first (fx).
            name = self._free_name()
            sketch.renameConstraint(added[0], name)
            sketch.renameConstraint(added[1], name + "b")
            sketch.setExpression("Constraints.%sb" % name, "Constraints.%s" % name)
        self.made = {"line": line, "corner": corner, "constraints": added, "kind": kind}
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
