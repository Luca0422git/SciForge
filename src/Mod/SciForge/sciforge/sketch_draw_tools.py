# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's sketch drawing tools that FreeCAD's Sketcher does not have, on SciForge's own
drawing handler (sketch_draw.DrawTool): Midpoint Line, 2-Point Circle, 2-Tangent and
3-Tangent Circle, Tangent Arc, Edge Polygon, the linear slots (centre to centre, overall,
centre point), the three-point arc slot and the conic curve.

The maths is in sketch_draw_core.py (unit tested), the shapes and their constraints in
sketch_build.py; here: the clicks, the preview and the value boxes of each tool. The
behaviour each one copies is in docs/sciforge/parity/sketch.md (with its sources).
"""

import math

from . import sketch_build as build
from . import sketch_draw as draw
from . import sketch_draw_core as core
from . import sketch_infer_core as icore
from .compat import QtCore
from .sketch_draw import ANGLE, COUNT, LENGTH, RATIO, Field, Snap


def _con(*args):
    import Sketcher

    return Sketcher.Constraint(*args)


def _plain(snap, point):
    """The snap moved to `point` by a typed value: what it sat on no longer holds; a
    level / upright direction does (the point stays on the same line from the start)."""
    if snap is not None and core.dist(snap.point, point) <= 1e-9:
        return snap
    result = None
    if (
        snap is not None
        and snap.result is not None
        and snap.result.kind
        in (
            icore.HORIZONTAL,
            icore.VERTICAL,
        )
    ):
        result = icore.Result(point, [], snap.result.kind, snap.result.direction)
        result.start = snap.result.start
    return Snap(point, snap.raw if snap is not None else point, result=result)


class _Directed(draw.DrawTool):
    """A tool whose second point is the end of a length and angle from the first (the
    boxes "length" and "angle"); the typed values move the point."""

    def end_from(self, start, snap):
        length_ = self.boxes.typed("length")
        angle = self.boxes.typed("angle")
        if length_ is None and angle is None:
            return snap.point
        return core.direction_point(start, snap.point, length_, angle)

    def _update_direction_fields(self, start, end, anchor=None):
        f_len, f_ang = self.boxes.field("length"), self.boxes.field("angle")
        if f_len is not None:
            f_len.value = core.dist(start, end)
            f_len.anchor = anchor or core.mid(start, end)
        if f_ang is not None:
            f_ang.value = core.angle_of(core.sub(end, start))
            f_ang.anchor = anchor or core.mid(start, end)

    def _typed_dimensions(self, line, start_anchor=None, end_anchor=None):
        """Typed length and angle become dimensions of `line` (Fusion)."""
        out = []
        length_ = self.boxes.typed("length")
        angle = self.boxes.typed("angle")
        if length_ is not None:
            out.append(_con("Distance", line, length_))
        if angle is not None:
            g = self.sketch.Geometry[line]
            actual = math.atan2(g.EndPoint.y - g.StartPoint.y, g.EndPoint.x - g.StartPoint.x)
            out.append(_con("Angle", line, actual))
        return out


# -- Midpoint Line ---------------------------------------------------------------------------
class MidpointLine(_Directed):
    title = "Midpoint Line"
    command = "SciForge_SketchMidpointLine"
    direction_steps = (1,)

    def prompt(self):
        if self.step == 0:
            return "click the middle of the line."
        return "click the end (or type the length, Tab, the angle, Enter)."

    def fields(self):
        if self.step == 1:
            return [Field("length", LENGTH, "L"), Field("angle", ANGLE, "A")]
        return []

    def ends(self, snap):
        middle = self.snaps[0].point
        length_ = self.boxes.typed("length")
        angle = self.boxes.typed("angle")
        return core.midpoint_line(middle, snap.point, length_, angle)

    def adjust(self, snap):
        if self.step != 1:
            return snap
        found = self.ends(snap)
        if found is None:
            return snap
        return _plain(snap, found[1])

    def accept(self, snap):
        if self.step == 1:
            return core.dist(snap.point, self.snaps[0].point) > 1e-7
        return True

    def moved(self, snap):
        guides, marks, points = self.hint_marks(snap)
        if self.step == 0:
            self.preview.show(guides=guides, marks=marks, points=points)
            return
        middle = self.snaps[0].point
        found = self.ends(snap)
        if found is None:
            self.preview.show(points=[middle])
            return
        a, b = found
        self._update_direction_fields(a, b, core.mid(middle, b))
        self.preview.show(curves=[[a, b]], guides=guides, marks=marks, points=points + [middle])

    def build(self, construction):
        middle_snap, end_snap = self.snaps
        found = core.midpoint_line(middle_snap.point, end_snap.point)
        a, b = found
        on_point = middle_snap.key is not None and not middle_snap.free
        shape = build.add_midpoint_line(self.sketch, a, b, construction, middle_point=not on_point)
        line = shape["line"]
        out = []
        if on_point:
            key = middle_snap.key
            out.append(_con("Symmetric", line, 1, line, 2, key[0], key[1]))
        else:
            out += self.snap_constraints(shape["anchors"]["middle"], middle_snap)
        out += self.snap_constraints((line, 2), end_snap, line=line)
        out += self._typed_dimensions(line)
        return out


# -- circles ----------------------------------------------------------------------------------
class TwoPointCircle(draw.DrawTool):
    title = "2-Point Circle"
    command = "SciForge_SketchCircle2Point"

    def prompt(self):
        if self.step == 0:
            return "click one end of the diameter."
        return "click the other end (or type the diameter, Enter)."

    def fields(self):
        if self.step == 1:
            return [Field("diameter", LENGTH, "D")]
        return []

    def circle(self, snap):
        return core.circle_2point(self.snaps[0].point, snap.point, self.boxes.typed("diameter"))

    def adjust(self, snap):
        if self.step != 1 or self.boxes.typed("diameter") is None:
            return snap
        found = self.circle(snap)
        if found is None:
            return snap
        centre, r = found
        end = core.add(centre, core.sub(centre, self.snaps[0].point))
        return _plain(snap, end)

    def accept(self, snap):
        return self.step != 1 or core.dist(snap.point, self.snaps[0].point) > 1e-7

    def moved(self, snap):
        guides, marks, points = self.hint_marks(snap)
        if self.step == 0:
            self.preview.show(guides=guides, marks=marks, points=points)
            return
        found = self.circle(snap)
        first = self.snaps[0].point
        if found is None:
            self.preview.show(points=[first])
            return
        centre, r = found
        f = self.boxes.field("diameter")
        f.value = 2.0 * r
        f.anchor = core.add(centre, (r * 0.7, r * 0.7))
        self.preview.show(
            curves=[draw.circle_points(centre, r)],
            construction=[[first, core.add(centre, core.sub(centre, first))]],
            guides=guides,
            marks=marks,
            points=points + [first],
        )

    def build(self, construction):
        first, second = self.snaps
        centre, r = core.circle_2point(first.point, second.point)
        shape = build.add_circle(self.sketch, centre, r, construction)
        circle = shape["circle"]
        out = []
        for snap in (first, second):
            # a click on a sketch point: the circle passes through it
            if snap.key is not None and not snap.free:
                out.append(_con("PointOnObject", snap.key[0], snap.key[1], circle))
        diameter = self.boxes.typed("diameter")
        if diameter is not None:
            out.append(_con("Diameter", circle, diameter))
        return out


class _LinePicker(draw.DrawTool):
    """Tools that start with clicks on lines (2-Tangent and 3-Tangent Circle)."""

    lines_needed = 2

    def steps(self):
        return self.lines_needed + 1

    @property
    def pick_steps(self):
        return tuple(range(self.lines_needed))

    def use_selection(self, selection):
        lines = [geo for geo, pos in selection if pos == 0 and build.is_line(self.sketch, geo)][
            : self.lines_needed
        ]
        if len(lines) == self.lines_needed:
            self.picks = list(lines)
            self.step = self.lines_needed
            self.boxes.set_fields(self.fields())
            self._tell()

    def pick(self, snap):
        geo = self.geometry()
        hit = geo.curve_at(
            snap.raw, draw.pick_pixels() * self._px(), kinds=("Part::GeomLineSegment",)
        )
        if hit is None:
            self.say("%s: click a line." % self.title)
            return
        if hit[0] in self.picks:
            self.say("%s: that line is picked already; click another one." % self.title)
            return
        self.picks.append(hit[0])
        self.next_step()

    def line_ends(self, geo):
        if geo == -1:
            return ((0.0, 0.0), (1.0, 0.0))
        if geo == -2:
            return ((0.0, 0.0), (0.0, 1.0))
        g = build.geometry(self.sketch, geo)
        return ((g.StartPoint.x, g.StartPoint.y), (g.EndPoint.x, g.EndPoint.y))

    def picked_lines(self):
        out = []
        for geo in self.picks:
            pts = draw.curve_points(self.sketch, geo)
            if pts:
                out.append(pts)
        return out

    def moved(self, snap):
        if self.step < self.lines_needed:
            geo = self.geometry()
            hit = geo.curve_at(
                snap.raw, draw.pick_pixels() * self._px(), kinds=("Part::GeomLineSegment",)
            )
            hover = draw.curve_points(self.sketch, hit[0]) if hit is not None else []
            self.preview.show(picked=self.picked_lines() + ([hover] if hover else []))
            return
        found = self.circle(snap)
        if found is None:
            self.preview.show(picked=self.picked_lines())
            return
        centre, r = found
        f = self.boxes.field("radius")
        if f is not None:
            f.value = r
            f.anchor = core.add(centre, (r * 0.7, r * 0.7))
        lines = [self.line_ends(g) for g in self.picks]
        self.preview.show(
            curves=[draw.circle_points(centre, r)],
            picked=self.picked_lines(),
            points=[centre] + core.tangent_points(centre, lines),
        )

    def _click(self, snap):
        if self.step < self.lines_needed:
            self.pick(snap)
            return
        if not self.boxes.take():
            return
        if self.circle(snap) is None:
            self.say("%s: no circle touches those lines there." % self.title)
            return
        self.snaps.append(snap)
        self.make()


class TwoTangentCircle(_LinePicker):
    title = "2-Tangent Circle"
    command = "SciForge_SketchCircle2Tangent"
    lines_needed = 2

    def prompt(self):
        return [
            "click the first line.",
            "click the second line.",
            "click on the side the circle goes (or type the radius, Enter).",
        ][min(self.step, 2)]

    def fields(self):
        if self.step == 2:
            return [Field("radius", LENGTH, "R")]
        return []

    def circle(self, snap):
        lines = [self.line_ends(g) for g in self.picks]
        try:
            return core.tangent_circle_2lines(
                lines[0], lines[1], snap.raw, self.boxes.typed("radius")
            )
        except ValueError:
            return None

    def build(self, construction):
        centre, r = self.circle(self.snaps[-1])
        shape = build.add_tangent_circle(self.sketch, centre, r, self.picks, construction)
        radius = self.boxes.typed("radius")
        out = []
        if radius is not None:
            out.append(_con("Radius", shape["circle"], radius))
        return out


class ThreeTangentCircle(_LinePicker):
    title = "3-Tangent Circle"
    command = "SciForge_SketchCircle3Tangent"
    lines_needed = 3

    def prompt(self):
        return [
            "click the first line.",
            "click the second line.",
            "click the third line.",
            "click near the circle you want (each gap between the lines has one).",
        ][min(self.step, 3)]

    def circle(self, snap):
        lines = [self.line_ends(g) for g in self.picks]
        try:
            return core.nearest_circle(core.tangent_circles_3lines(*lines), snap.raw)
        except ValueError:
            return None

    def build(self, construction):
        centre, r = self.circle(self.snaps[-1])
        build.add_tangent_circle(self.sketch, centre, r, self.picks, construction)
        return []


# -- Tangent Arc ------------------------------------------------------------------------------
class TangentArc(draw.DrawTool):
    title = "Tangent Arc"
    command = "SciForge_SketchTangentArc"

    def prompt(self):
        if self.step == 0:
            return "click the end of a line or arc to start from."
        return "click the arc's end (or type the radius, Enter)."

    def fields(self):
        if self.step == 1:
            return [Field("radius", LENGTH, "R")]
        return []

    def _start(self, snap):
        """(start point, unit tangent, (geo, pos)) when the snap is on the end of a line or
        an arc, else None."""
        key = snap.key
        if key is None or key[1] not in (1, 2) or key[0] < 0:
            return None
        g = self.sketch.Geometry[key[0]]
        if g.TypeId == "Part::GeomLineSegment":
            curves = [
                ("line", key[0], (g.StartPoint.x, g.StartPoint.y), (g.EndPoint.x, g.EndPoint.y))
            ]
        elif g.TypeId == "Part::GeomArcOfCircle":
            curves = [
                (
                    "arc",
                    key[0],
                    (g.Center.x, g.Center.y),
                    (g.StartPoint.x, g.StartPoint.y),
                    (g.EndPoint.x, g.EndPoint.y),
                )
            ]
        else:
            return None
        found = icore.chain_tangent(snap.point, curves, 1e-6)
        if found is None:
            return None
        tangent, prev = found
        return snap.point, tangent, prev

    def accept(self, snap):
        if self.step == 0:
            if self._start(snap) is None:
                self.say("Tangent Arc: click the end point of a line or an arc.")
                return False
            return True
        return self.arc(snap) is not None

    def arc(self, snap):
        start, tangent, prev = self._start(self.snaps[0])
        radius = self.boxes.typed("radius")
        if radius is not None:
            found = core.tangent_arc_radius(start, tangent, snap.point, radius)
            if found is None:
                return None
            centre, r, a1, a2, joint = found
            return icore.Arc(centre, r, a1, a2, joint)
        return icore.tangent_arc(start, tangent, snap.point, 1e-6)

    def adjust(self, snap):
        if self.step != 1 or self.boxes.typed("radius") is None:
            return snap
        arc = self.arc(snap)
        if arc is None:
            return snap
        end = arc.point(arc.a2 if arc.free_pos == 2 else arc.a1)
        return _plain(snap, end)

    def moved(self, snap):
        guides, marks, points = self.hint_marks(snap)
        if self.step == 0:
            ok = self._start(snap) is not None
            self.preview.show(points=[snap.point] if ok else [])
            return
        arc = self.arc(snap)
        start = self.snaps[0].point
        if arc is None:
            self.preview.show(points=[start])
            return
        f = self.boxes.field("radius")
        f.value = arc.radius
        f.anchor = arc.point((arc.a1 + arc.a2) / 2.0)
        self.preview.show(
            curves=[arc.points()], guides=guides, marks=marks, points=points + [start]
        )

    def build(self, construction):
        start_snap, end_snap = self.snaps
        arc = self.arc(end_snap)
        if arc is None:
            raise ValueError("no arc there")
        _start, _tangent, prev = self._start(start_snap)
        shape = build.add_tangent_arc(self.sketch, arc, prev, construction)
        out = self.snap_constraints(shape["anchors"]["end"], end_snap)
        radius = self.boxes.typed("radius")
        if radius is not None:
            out.append(_con("Radius", shape["arc"], radius))
        return out


# -- Edge Polygon --------------------------------------------------------------------------
class EdgePolygon(_Directed):
    title = "Edge Polygon"
    command = "SciForge_SketchPolygonEdge"
    direction_steps = (1,)
    sides = 6  # remembered between uses, like FreeCAD's polygon tool

    def steps(self):
        return 3

    def prompt(self):
        return [
            "click one end of an edge.",
            "click the other end (or type the length, Tab, the angle, Enter).",
            "click the side the polygon goes to (U / J or type the number of sides).",
        ][self.step]

    def fields(self):
        if self.step == 1:
            return [Field("length", LENGTH, "L"), Field("angle", ANGLE, "A")]
        if self.step == 2:
            f = Field("sides", COUNT, "Sides", low=3, high=64)
            f.value = EdgePolygon.sides
            return [f]
        return []

    def current_sides(self):
        typed = self.boxes.typed("sides")
        return int(typed) if typed is not None else EdgePolygon.sides

    def adjust(self, snap):
        if self.step == 1:
            end = self.end_from(self.snaps[0].point, snap)
            return _plain(snap, end) if end is not None else snap
        return snap

    def accept(self, snap):
        if self.step == 1:
            return core.dist(snap.point, self.snaps[0].point) > 1e-7
        return True

    def extra_key(self, event):
        if self.step != 2 or self.boxes.typing is not None:
            return False
        key = event.key()
        if key in (QtCore.Qt.Key_U, QtCore.Qt.Key_J):
            sides = self.current_sides() + (1 if key == QtCore.Qt.Key_U else -1)
            EdgePolygon.sides = max(3, min(64, sides))
            f = self.boxes.field("sides")
            if f is not None:
                f.typed = None
                f.value = EdgePolygon.sides
            if self.last is not None:
                self.moved(self.last)
            self.boxes.refresh()
            return True
        return False

    def wants_letter(self, text):
        return self.step == 2 and text.lower() in ("u", "j")

    def moved(self, snap):
        guides, marks, points = self.hint_marks(snap)
        if self.step == 0:
            self.preview.show(guides=guides, marks=marks, points=points)
            return
        p1 = self.snaps[0].point
        if self.step == 1:
            end = self.end_from(p1, snap)
            if end is None:
                self.preview.show(points=[p1])
                return
            self._update_direction_fields(p1, end)
            self.preview.show(curves=[[p1, end]], guides=guides, marks=marks, points=points + [p1])
            return
        p2 = self.snaps[1].point
        shape = core.edge_polygon(p1, p2, self.current_sides(), snap.raw)
        if shape is None:
            return
        corners, centre, r = shape
        f = self.boxes.field("sides")
        if f is not None:
            f.value = EdgePolygon.sides
            f.anchor = centre
        self.preview.show(
            curves=[corners + [corners[0]]],
            construction=[draw.circle_points(centre, r)],
            points=[p1, p2],
        )

    def build(self, construction):
        p1_snap, p2_snap, side_snap = self.snaps
        sides = self.current_sides()
        EdgePolygon.sides = sides
        shape = build.add_edge_polygon(
            self.sketch, p1_snap.point, p2_snap.point, sides, side_snap.raw, construction
        )
        out = self.snap_constraints(shape["anchors"]["p1"], p1_snap)
        out += self.snap_constraints(shape["anchors"]["p2"], p2_snap, line=shape["edge"])
        out += self._typed_dimensions(shape["edge"])
        return out


# -- slots ----------------------------------------------------------------------------------
class LinearSlot(_Directed):
    """Fusion's centre-to-centre, overall and centre-point slots (core.CENTER_TO_CENTER,
    OVERALL, CENTER_POINT)."""

    kind = core.CENTER_TO_CENTER
    direction_steps = (1,)
    PROMPTS = {
        core.CENTER_TO_CENTER: (
            "click the centre of one end.",
            "click the centre of the other end",
        ),
        core.OVERALL: ("click one end of the slot.", "click the other end"),
        core.CENTER_POINT: ("click the middle of the slot.", "click the centre of one end"),
    }

    def steps(self):
        return 3

    def prompt(self):
        first, second = self.PROMPTS[self.kind]
        if self.step == 0:
            return first
        if self.step == 1:
            return second + " (or type the length, Tab, the angle, Enter)."
        return "click to set the width (or type it, Enter)."

    def fields(self):
        if self.step == 1:
            return [Field("length", LENGTH, "L"), Field("angle", ANGLE, "A")]
        if self.step == 2:
            return [Field("width", LENGTH, "W")]
        return []

    def adjust(self, snap):
        if self.step == 1:
            end = self.end_from(self.snaps[0].point, snap)
            return _plain(snap, end) if end is not None else snap
        return snap

    def width(self, snap):
        typed = self.boxes.typed("width")
        if typed is not None:
            return typed
        first, second = self.snaps[0].point, self.snaps[1].point
        found = core.slot_centres(self.kind, first, second, 1e-3)
        if found is None:
            return None
        c1, c2, _r = found
        return core.slot_width_from_pointer(c1, c2, snap.raw)

    def accept(self, snap):
        if self.step == 1:
            return core.dist(snap.point, self.snaps[0].point) > 1e-7
        if self.step == 2:
            w = self.width(snap)
            ok = w is not None and core.slot_centres(
                self.kind, self.snaps[0].point, self.snaps[1].point, w
            )
            if not ok:
                self.say("%s: the slot is too short for that width." % self.title)
            return bool(ok)
        return True

    def _outline(self, c1, c2, r):
        out = []
        for part in core.slot_outline(c1, c2, r):
            if part[0] == "arc":
                out.append(draw.arc_points(part[1], part[2], part[3], part[4]))
            else:
                out.append([part[1], part[2]])
        return out

    def moved(self, snap):
        guides, marks, points = self.hint_marks(snap)
        if self.step == 0:
            self.preview.show(guides=guides, marks=marks, points=points)
            return
        first = self.snaps[0].point
        if self.step == 1:
            end = self.end_from(first, snap)
            if end is None:
                self.preview.show(points=[first])
                return
            self._update_direction_fields(first, end)
            # FreeCAD's slot tool previews a width of 2/5 of the length meanwhile
            found = core.slot_centres(self.kind, first, end, 0.4 * core.dist(first, end) / 2.0)
            curves = self._outline(*found) if found else []
            self.preview.show(
                curves=curves,
                construction=[[first, end]],
                guides=guides,
                marks=marks,
                points=points + [first],
            )
            return
        second = self.snaps[1].point
        w = self.width(snap)
        found = core.slot_centres(self.kind, first, second, w) if w else None
        f = self.boxes.field("width")
        if found is None:
            self.preview.show(construction=[[first, second]], points=[first, second])
            return
        c1, c2, r = found
        f.value = 2.0 * r
        f.anchor = core.add(c2, (r, r))
        self.preview.show(
            curves=self._outline(c1, c2, r), construction=[[c1, c2]], points=[first, second]
        )

    def build(self, construction):
        first, second, width_snap = self.snaps
        w = self.width(width_snap)
        shape = build.add_linear_slot(
            self.sketch, self.kind, first.point, second.point, w, construction
        )
        anchors = shape["anchors"]
        line = shape["line"]
        out = self.snap_constraints(anchors["first"], first)
        out += self.snap_constraints(anchors["second"], second, line=line)
        if self.boxes.typed("width") is not None:
            out.append(_con("Diameter", shape["arcs"][0], w))
        length_ = self.boxes.typed("length")
        if length_ is not None:
            a, b = anchors["first"], anchors["second"]
            out.append(_con("Distance", a[0], a[1], b[0], b[1], length_))
        if self.boxes.typed("angle") is not None:
            g = self.sketch.Geometry[line]
            actual = math.atan2(g.EndPoint.y - g.StartPoint.y, g.EndPoint.x - g.StartPoint.x)
            out.append(_con("Angle", line, actual))
        return out


class CenterToCenterSlot(LinearSlot):
    title = "Center to Center Slot"
    command = "SciForge_SketchSlotCenter"
    kind = core.CENTER_TO_CENTER


class OverallSlot(LinearSlot):
    title = "Overall Slot"
    command = "SciForge_SketchSlotOverall"
    kind = core.OVERALL


class CenterPointSlot(LinearSlot):
    title = "Center Point Slot"
    command = "SciForge_SketchSlotCenterPoint"
    kind = core.CENTER_POINT


class ThreePointArcSlot(draw.DrawTool):
    title = "Three Point Arc Slot"
    command = "SciForge_SketchSlotArc3Point"

    def steps(self):
        return 4

    def prompt(self):
        return [
            "click the centre of one end.",
            "click the centre of the other end.",
            "click a point the slot's centre arc passes through.",
            "click to set the width (or type it, Enter).",
        ][self.step]

    def fields(self):
        if self.step == 3:
            return [Field("width", LENGTH, "W")]
        return []

    def slot(self, snap):
        c1, c2, through = self.snaps[0].point, self.snaps[1].point, self.snaps[2].point
        typed = self.boxes.typed("width")
        if typed is None:
            probe = core.arc_slot(c1, c2, through, 1e-3)
            if probe is None:
                return None
            typed = core.arc_slot_width_from_pointer(probe, snap.raw)
        return core.arc_slot(c1, c2, through, typed)

    def accept(self, snap):
        if self.step == 1:
            return core.dist(snap.point, self.snaps[0].point) > 1e-7
        if self.step == 2:
            ok = core.arc_through(self.snaps[0].point, snap.point, self.snaps[1].point) is not None
            if not ok:
                self.say("Three Point Arc Slot: the three points are in a line; click off it.")
            return ok
        if self.step == 3:
            ok = self.slot(snap) is not None
            if not ok:
                self.say("Three Point Arc Slot: the slot is too wide for its arc.")
            return ok
        return True

    def moved(self, snap):
        guides, marks, points = self.hint_marks(snap)
        if self.step == 0:
            self.preview.show(guides=guides, marks=marks, points=points)
            return
        c1 = self.snaps[0].point
        if self.step == 1:
            self.preview.show(
                construction=[[c1, snap.point]], guides=guides, marks=marks, points=points + [c1]
            )
            return
        c2 = self.snaps[1].point
        if self.step == 2:
            arc = core.arc_through(c1, snap.point, c2)
            if arc is None:
                self.preview.show(construction=[[c1, c2]], points=[c1, c2])
                return
            centre, r, a1, a2 = arc
            self.preview.show(
                construction=[draw.arc_points(centre, r, a1, a2)], points=[c1, c2] + points
            )
            return
        slot = self.slot(snap)
        if slot is None:
            return
        centre, radius, a1, a2, r = (
            slot["centre"],
            slot["radius"],
            slot["a1"],
            slot["a2"],
            slot["r"],
        )
        e1, e2 = core.polar(a1, radius, centre), core.polar(a2, radius, centre)
        f = self.boxes.field("width")
        f.value = 2.0 * r
        f.anchor = core.add(e2, (r, r))
        self.preview.show(
            curves=[
                draw.arc_points(centre, radius + r, a1, a2),
                draw.arc_points(centre, radius - r, a1, a2),
                draw.arc_points(e1, r, a1 + math.pi, a1 + 2 * math.pi),
                draw.arc_points(e2, r, a2, a2 + math.pi),
            ],
            points=[c1, c2],
        )

    def build(self, construction):
        first, second, _through, width_snap = self.snaps
        slot = self.slot(width_snap)
        shape = build.add_arc_slot(self.sketch, slot, construction)
        out = self.snap_constraints(shape["anchors"]["first"], first)
        out += self.snap_constraints(shape["anchors"]["second"], second)
        if self.boxes.typed("width") is not None:
            out.append(_con("Diameter", shape["caps"][0], 2.0 * slot["r"]))
        return out


# -- Conic ------------------------------------------------------------------------------------
class ConicCurve(draw.DrawTool):
    title = "Conic Curve"
    command = "SciForge_SketchConic"

    def steps(self):
        return 4

    def prompt(self):
        return [
            "click the start of the curve.",
            "click its end.",
            "click the apex (where the curve's end directions meet).",
            "move to shape it (rho), click or press Enter (or type rho between 0 and 1).",
        ][self.step]

    def fields(self):
        if self.step == 3:
            f = Field("rho", RATIO, "Rho", low=core.RHO_MIN, high=core.RHO_MAX)
            f.value = 0.5
            return [f]
        return []

    def rho(self, snap=None):
        typed = self.boxes.typed("rho")
        if typed is not None:
            return typed
        if snap is None:
            f = self.boxes.field("rho")
            return f.value if f is not None and f.value is not None else 0.5
        start, end, apex = (s.point for s in self.snaps[:3])
        return core.rho_from_pointer(start, apex, end, snap.raw)

    def accept(self, snap):
        if self.step == 1:
            return core.dist(snap.point, self.snaps[0].point) > 1e-7
        if self.step == 2:
            a, b = self.snaps[0].point, self.snaps[1].point
            ok = core.point_line_distance(snap.point, a, b) > 1e-6
            if not ok:
                self.say("Conic Curve: the apex must be off the line from start to end.")
            return ok
        return True

    def moved(self, snap):
        guides, marks, points = self.hint_marks(snap)
        if self.step == 0:
            self.preview.show(guides=guides, marks=marks, points=points)
            return
        start = self.snaps[0].point
        if self.step == 1:
            self.preview.show(
                construction=[[start, snap.point]],
                guides=guides,
                marks=marks,
                points=points + [start],
            )
            return
        end = self.snaps[1].point
        if self.step == 2:
            apex = snap.point
            curve = []
            if core.point_line_distance(apex, start, end) > 1e-6:
                curve = [core.conic_points(start, apex, end, 0.5)]
            self.preview.show(
                curves=curve,
                construction=[[start, apex, end]],
                guides=guides,
                marks=marks,
                points=points + [start, end],
            )
            return
        apex = self.snaps[2].point
        rho = self.rho(snap)
        f = self.boxes.field("rho")
        if f is not None:
            f.value = rho
            f.anchor = core.conic_shoulder(start, apex, end, rho)
        self.preview.show(
            curves=[core.conic_points(start, apex, end, rho)],
            construction=[[start, apex, end], [core.mid(start, end), apex]],
            points=[start, end, apex, core.conic_shoulder(start, apex, end, rho)],
        )

    def _click(self, snap):
        if self.step == 3:
            if not self.boxes.take():
                return
            f = self.boxes.field("rho")
            if f is not None and f.typed is None:
                f.value = self.rho(snap)
            self.snaps.append(snap)
            self.make()
            return
        super()._click(snap)

    def enter_without_values(self):
        if self.step == 3:
            self.snaps.append(self.last or self.snaps[-1])
            self.make()
            return True
        return False

    def on_finish(self):
        """OK in the right-click menu while rho is being set: the conic is made with the
        rho shown (Fusion's OK), then the tool ends."""
        if self.active and self.step == 3:
            self.snaps.append(self.last or self.snaps[-1])
            self.make()

    def build(self, construction):
        start, end, apex = self.snaps[:3]
        f = self.boxes.field("rho")
        rho = f.typed if f is not None and f.typed is not None else (f.value if f else 0.5)
        rho = max(core.RHO_MIN, min(core.RHO_MAX, rho if rho is not None else 0.5))
        shape = build.add_conic(self.sketch, start.point, end.point, apex.point, rho, construction)
        anchors = shape["anchors"]
        out = self.snap_constraints(anchors["start"], start)
        out += self.snap_constraints(anchors["end"], end)
        out += self.snap_constraints(anchors["apex"], apex)
        return out


TOOLS = {
    cls.command: cls
    for cls in (
        MidpointLine,
        TwoPointCircle,
        TwoTangentCircle,
        ThreeTangentCircle,
        TangentArc,
        EdgePolygon,
        CenterToCenterSlot,
        OverallSlot,
        CenterPointSlot,
        ThreePointArcSlot,
        ConicCurve,
    )
}
