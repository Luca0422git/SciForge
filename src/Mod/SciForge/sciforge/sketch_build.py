# SPDX-License-Identifier: LGPL-2.1-or-later
"""The shapes SciForge's own sketch tools add to a sketch, with their constraints, and
the curve operations of Trim, Extend and Break (FreeCAD and Part, no Qt: the GUI tools
in sketch_draw_tools.py and sketch_modify_ui.py call these, so do the golden builder
and headless tests).

Every builder adds its curves and the constraints that keep the shape what it is, and
returns a dict: "ids" (new geometry indices) and named "anchors" ((geo, pos) of the
points the user clicked, so the caller can tie them to what the click snapped to).
FreeCAD's point positions: 1 start, 2 end, 3 centre.

The caller opens the undo transaction; nothing here commits.
"""

import math

import FreeCAD as App

from . import sketch_draw_core as core

V = App.Vector
NORMAL = V(0, 0, 1)
START, END, CENTRE = 1, 2, 3


def _v(p):
    return V(p[0], p[1], 0)


def _xy(v):
    return (v.x, v.y)


def _con(*args):
    import Sketcher

    return Sketcher.Constraint(*args)


def _arc(centre, radius, a1, a2):
    import Part

    return Part.ArcOfCircle(Part.Circle(_v(centre), NORMAL, radius), a1, a2)


def _line(a, b):
    import Part

    return Part.LineSegment(_v(a), _v(b))


def _add(sketch, geometry, construction):
    """Add the curves; returns their indices (always a list)."""
    ids = sketch.addGeometry(list(geometry), bool(construction))
    return list(ids) if isinstance(ids, (list, tuple)) else [ids]


# -- lines --------------------------------------------------------------------------------
def add_midpoint_line(sketch, a, b, construction=False, middle_point=True):
    """Fusion's Midpoint Line: the line a-b and (middle_point) a point at its middle held
    there by a Symmetric constraint (FreeCAD's form of Fusion's midpoint constraint).
    Anchors: "start", "end", "middle" (the point, or None)."""
    import Part

    (line,) = _add(sketch, [_line(a, b)], construction)
    anchors = {"start": (line, START), "end": (line, END), "middle": None}
    ids = [line]
    if middle_point:
        (point,) = _add(sketch, [Part.Point(_v(core.mid(a, b)))], False)
        sketch.addConstraint(_con("Symmetric", line, START, line, END, point, START))
        anchors["middle"] = (point, START)
        ids.append(point)
    return {"ids": ids, "anchors": anchors, "line": line}


def add_rectangle_3point(sketch, corners, construction=False):
    """Fusion's 3-Point Rectangle from its corners [p1, p2, p3, p4] (core.rectangle_3point):
    four lines joined end to end, the second square to the first and each side parallel
    to the one opposite (Fusion's perpendicular and parallel constraints), so it stays a
    rectangle at any angle. Anchors: "p1", "p2" (the first side's ends), "p3" (the
    clicked corner: the end of the second side); "edge" is the first side, "width" the
    second."""
    pts = list(corners)
    lines = _add(sketch, [_line(pts[i], pts[(i + 1) % 4]) for i in range(4)], construction)
    cons = [_con("Coincident", lines[i], END, lines[(i + 1) % 4], START) for i in range(4)]
    cons.append(_con("Perpendicular", lines[0], lines[1]))
    cons.append(_con("Parallel", lines[0], lines[2]))
    cons.append(_con("Parallel", lines[1], lines[3]))
    sketch.addConstraint(cons)
    return {
        "ids": lines,
        "anchors": {"p1": (lines[0], START), "p2": (lines[0], END), "p3": (lines[1], END)},
        "edge": lines[0],
        "width": lines[1],
    }


# -- circles ---------------------------------------------------------------------------
def add_circle(sketch, centre, radius, construction=False):
    import Part

    (circle,) = _add(sketch, [Part.Circle(_v(centre), NORMAL, radius)], construction)
    return {"ids": [circle], "anchors": {"centre": (circle, CENTRE)}, "circle": circle}


def add_tangent_circle(sketch, centre, radius, lines, construction=False):
    """A circle touching each of `lines` (sketch geometry indices of lines): Tangent
    constraints (edge to edge)."""
    built = add_circle(sketch, centre, radius, construction)
    circle = built["circle"]
    sketch.addConstraint([_con("Tangent", circle, line) for line in lines])
    return built


# -- arcs ------------------------------------------------------------------------------------
def add_tangent_arc(sketch, arc, prev, construction=False):
    """The arc (sketch_infer_core.Arc) tangent to the curve end `prev` (geo, pos):
    FreeCAD's end-to-end tangency also joins the two points. Anchors: "joint", "end"."""
    (index,) = _add(sketch, [_arc(arc.centre, arc.radius, arc.a1, arc.a2)], construction)
    sketch.addConstraint(_con("Tangent", prev[0], prev[1], index, arc.joint_pos))
    return {
        "ids": [index],
        "anchors": {"joint": (index, arc.joint_pos), "end": (index, arc.free_pos)},
        "arc": index,
    }


# -- polygons --------------------------------------------------------------------------------
def add_edge_polygon(sketch, p1, p2, sides, side_point, construction=False):
    """Fusion's Edge Polygon: the clicked edge p1-p2 and the side it goes to. Built like
    SciForge's inscribed polygon (equal sides, corners on a construction circle: 4 degrees
    of freedom, the edge's two ends). Anchors: "p1", "p2"; "edge" is the clicked edge's
    line."""
    from . import sketch_polygon

    shape = core.edge_polygon(p1, p2, sides, side_point)
    if shape is None:
        raise ValueError("the edge has no length")
    _corners, centre, _radius = shape
    side = 1.0 if core.cross(core.sub(p2, p1), core.sub(side_point, p1)) >= 0 else -1.0
    ids = sketch_polygon.add_polygon(sketch, sides, _v(centre), _v(p1), False, construction)
    sides = int(sides)
    lines = ids[:sides]
    if side > 0:
        edge, p2_anchor = lines[0], (lines[0], END)
    else:
        edge, p2_anchor = lines[sides - 1], (lines[sides - 1], START)
    return {
        "ids": ids,
        "anchors": {"p1": (lines[0], START), "p2": p2_anchor},
        "edge": edge,
        "circle": ids[sides],
    }


# -- slots -----------------------------------------------------------------------------------
def add_linear_slot(sketch, kind, first, second, width, construction=False):
    """A linear slot (core.CENTER_TO_CENTER, OVERALL, CENTER_POINT) from the two clicked
    points and the width: two end arcs, two sides, FreeCAD's slot constraints (tangent
    joins, equal ends) and a construction line through the slot: centre to centre
    (centre-to-centre and centre-point slots) or end to end (the overall slot). The
    centre-point slot also gets a point at its middle, on the middle of that line.
    Anchors: "first", "second" (the clicked points), "centre_line"."""
    import Part

    found = core.slot_centres(kind, first, second, width)
    if found is None:
        raise ValueError("the slot is too short for its width")
    c1, c2, r = found
    arc1, arc2, side1, side2 = core.slot_outline(c1, c2, r)
    geometry = [
        _arc(arc1[1], arc1[2], arc1[3], arc1[4]),
        _arc(arc2[1], arc2[2], arc2[3], arc2[4]),
        _line(side1[1], side1[2]),
        _line(side2[1], side2[2]),
    ]
    a1, a2, l1, l2 = _add(sketch, geometry, construction)
    constraints = [
        _con("Tangent", a1, START, l1, START),
        _con("Tangent", a1, END, l2, START),
        _con("Tangent", a2, END, l1, END),
        _con("Tangent", a2, START, l2, END),
        _con("Equal", a1, a2),
    ]
    anchors = {}
    if kind == core.OVERALL:
        (line,) = _add(sketch, [_line(first, second)], True)
        constraints += [
            _con("PointOnObject", a1, CENTRE, line),
            _con("PointOnObject", a2, CENTRE, line),
            _con("PointOnObject", line, START, a1),
            _con("PointOnObject", line, END, a2),
        ]
        anchors["first"], anchors["second"] = (line, START), (line, END)
        ids = [a1, a2, l1, l2, line]
    else:
        (line,) = _add(sketch, [_line(c1, c2)], True)
        constraints += [
            _con("Coincident", line, START, a1, CENTRE),
            _con("Coincident", line, END, a2, CENTRE),
        ]
        ids = [a1, a2, l1, l2, line]
        if kind == core.CENTER_POINT:
            (point,) = _add(sketch, [Part.Point(_v(first))], False)
            constraints.append(_con("Symmetric", line, START, line, END, point, START))
            anchors["first"], anchors["second"] = (point, START), (a2, CENTRE)
            ids.append(point)
        else:
            anchors["first"], anchors["second"] = (a1, CENTRE), (a2, CENTRE)
    sketch.addConstraint(constraints)
    anchors["centre_line"] = line
    return {"ids": ids, "anchors": anchors, "arcs": (a1, a2), "line": line}


def add_arc_slot(sketch, slot, construction=False):
    """The three-point arc slot (core.arc_slot's dict): outer arc, the two end caps, the
    inner arc, with FreeCAD's arc slot's constraints. (A construction centre arc through
    the end centres would over-constrain it: its radius already follows from the caps.)
    Anchors: "first", "second" (the end centres as clicked), "centre"."""
    centre, radius, a1, a2, r = slot["centre"], slot["radius"], slot["a1"], slot["a2"], slot["r"]
    end1, end2 = core.polar(a1, radius, centre), core.polar(a2, radius, centre)
    geometry = [
        _arc(centre, radius + r, a1, a2),
        _arc(end1, r, a1 + math.pi, a1 + 2.0 * math.pi),
        _arc(end2, r, a2, a2 + math.pi),
        _arc(centre, radius - r, a1, a2),
    ]
    outer, cap1, cap2, inner = _add(sketch, geometry, construction)
    sketch.addConstraint(
        [
            _con("Coincident", outer, CENTRE, inner, CENTRE),
            _con("Tangent", inner, END, cap2, END),
            _con("Tangent", inner, START, cap1, START),
            _con("Tangent", outer, END, cap2, START),
            _con("Tangent", outer, START, cap1, END),
        ]
    )
    first, second = (cap1, CENTRE), (cap2, CENTRE)
    if slot.get("reversed"):
        first, second = second, first
    return {
        "ids": [outer, cap1, cap2, inner],
        "anchors": {"first": first, "second": second, "centre": (outer, CENTRE)},
        "caps": (cap1, cap2),
    }


# -- the conic -----------------------------------------------------------------------------
def add_conic(sketch, start, end, apex, rho, construction=False):
    """Fusion's rho conic as an exact rational quadratic B-spline: poles start, apex,
    end with weights 1, rho/(1-rho), 1; its control points shown (FreeCAD's construction
    circles, the apex weight held by a Weight constraint so rho stays) and two
    construction guidelines from the ends to the apex (Fusion's guidelines: make them
    tangent or collinear to neighbouring curves). Anchors: "start", "end", "apex".
    Returns also "spline", "apex_pole" and "weight" (the Weight constraint's index)."""
    import Part

    w = core.conic_weight(rho)
    spline = Part.BSplineCurve()
    spline.buildFromPolesMultsKnots(
        [_v(start), _v(apex), _v(end)], [3, 3], [0.0, 1.0], False, 2, [1.0, w, 1.0]
    )
    (index,) = _add(sketch, [spline], construction)
    before = sketch.GeometryCount
    sketch.exposeInternalGeometry(index)
    poles = conic_poles(sketch, index)
    if len(poles) != 3:
        raise ValueError("the conic's control points could not be shown")
    apex_pole = poles[1]
    # FreeCAD ties the poles' weights with Equal / Weight constraints as it found them:
    # the apex gets its own Weight (rho), the end poles keep theirs
    for i in reversed(range(len(sketch.Constraints))):
        c = sketch.Constraints[i]
        if c.Type in ("Equal", "Weight") and apex_pole in (c.First, c.Second):
            sketch.delConstraint(i)
    weight = sketch.addConstraint(_con("Weight", apex_pole, w))
    g1, g2 = _add(sketch, [_line(start, apex), _line(apex, end)], True)
    sketch.addConstraint(
        [
            _con("Coincident", g1, START, poles[0], CENTRE),
            _con("Coincident", g1, END, apex_pole, CENTRE),
            _con("Coincident", g2, START, apex_pole, CENTRE),
            _con("Coincident", g2, END, poles[2], CENTRE),
        ]
    )
    ids = [index] + list(range(before, sketch.GeometryCount))
    return {
        "ids": ids,
        "anchors": {"start": (index, START), "end": (index, END), "apex": (apex_pole, CENTRE)},
        "spline": index,
        "apex_pole": apex_pole,
        "weight": weight,
        "guides": (g1, g2),
    }


def conic_poles(sketch, spline):
    """The pole circles of a B-spline in pole order (FreeCAD's internal alignment)."""
    found = []
    for c in sketch.Constraints:
        if c.Type != "InternalAlignment" or c.Second != spline:
            continue
        geo = sketch.Geometry[c.First]
        if geo.TypeId != "Part::GeomCircle":
            continue
        found.append(c.First)
    poles = sketch.Geometry[spline].getPoles()
    order = []
    for pole in poles:
        best = min(found, key=lambda g: (sketch.Geometry[g].Center - pole).Length, default=None)
        if best is not None:
            order.append(best)
    return order


def is_conic(sketch, geo):
    """A SciForge conic: a rational quadratic B-spline with three poles."""
    try:
        g = sketch.Geometry[geo]
        return (
            g.TypeId == "Part::GeomBSplineCurve"
            and g.Degree == 2
            and g.NbPoles == 3
            and not g.isPeriodic()
        )
    except Exception:
        return False


def conic_rho(sketch, geo):
    """The rho of a conic B-spline (from its apex weight)."""
    weights = sketch.Geometry[geo].getWeights()
    w = weights[1] / math.sqrt(weights[0] * weights[2])
    return core.conic_rho(w)


def conic_weight_constraint(sketch, geo):
    """The index of the Weight constraint on the conic's apex pole, or None."""
    poles = conic_poles(sketch, geo)
    if len(poles) != 3:
        return None
    for i, c in enumerate(sketch.Constraints):
        if c.Type == "Weight" and c.First == poles[1]:
            return i
    return None


# -- the curves a click can hit; intersections ---------------------------------------------
def curves(sketch, external=True):
    """[(geo, Part geometry)] of the sketch's curves (no points); with `external` also
    projected / included edges (negative indices from -3; FreeCAD's axes -1 / -2 are
    left out: Fusion trims at drawn and projected curves, not at the origin axes)."""
    out = []
    for i, g in enumerate(sketch.Geometry):
        if g.TypeId != "Part::GeomPoint":
            out.append((i, g))
    if external:
        try:
            for k, g in enumerate(list(sketch.ExternalGeo)[2:]):
                if g.TypeId != "Part::GeomPoint":
                    out.append((-3 - k, g))
        except Exception:
            pass
    return out


def _is_closed(g):
    return g.TypeId in ("Part::GeomCircle", "Part::GeomEllipse") or (
        g.TypeId == "Part::GeomBSplineCurve" and g.isPeriodic()
    )


def intersections(sketch, geo):
    """The parameters (on curve `geo`) where it meets the sketch's other curves (drawn,
    construction and projected), sorted, without repeats."""
    target = sketch.Geometry[geo]
    params = []
    for other, g in curves(sketch):
        if other == geo:
            continue
        try:
            points = target.intersectCC(g)
        except Exception:
            continue  # overlapping curves and the like: no single points
        for p in points:
            try:
                params.append(target.parameter(V(p.X, p.Y, 0)))
            except Exception:
                pass
    params.sort()
    out = []
    for t in params:
        if not out or abs(t - out[-1]) > 1e-9:
            out.append(t)
    return out


def piece(sketch, geo, point):
    """(t0, t1, closed) of the piece of curve `geo` between the intersections nearest to
    `point` on each side (Fusion's Trim and Break work on that piece); t0/t1 are the
    curve's own ends when no intersection lies that way. For a closed curve with fewer
    than two intersections: None (no piece: the whole curve)."""
    g = sketch.Geometry[geo]
    t = g.parameter(_v(point))
    first, last = g.FirstParameter, g.LastParameter
    cuts = [
        c for c in intersections(sketch, geo) if first + 1e-9 < c < last - 1e-9 or _is_closed(g)
    ]
    if _is_closed(g):
        period = last - first
        if len(cuts) < 2:
            return None
        wrapped = sorted((c - first) % period + first for c in cuts)
        before = [c for c in wrapped if c <= t]
        after = [c for c in wrapped if c > t]
        t0 = before[-1] if before else wrapped[-1] - period
        t1 = after[0] if after else wrapped[0] + period
        return t0, t1, True
    before = [c for c in cuts if c < t]
    after = [c for c in cuts if c > t]
    return (before[-1] if before else first), (after[0] if after else last), False


def piece_points(sketch, geo, t0, t1, n=32):
    """A polyline along curve `geo` from parameter t0 to t1 (a closed curve may wrap)."""
    g = sketch.Geometry[geo]
    out = []
    for i in range(n + 1):
        t = t0 + (t1 - t0) * i / float(n)
        p = g.value(t)
        out.append((p.x, p.y))
    return out


# -- Extend ------------------------------------------------------------------------------------
def extend_plan(sketch, geo, point):
    """What Fusion's Extend does with a click on curve `geo` near `point`: the end nearest
    the click grows until it meets another curve. Returns (pos, new end point, the curve
    it meets, increment for SketchObject.extend) or None (not a line or arc, or nothing
    to meet)."""
    import Part

    g = sketch.Geometry[geo]
    click = _v(point)
    if g.TypeId == "Part::GeomLineSegment":
        a, b = g.StartPoint, g.EndPoint
        pos = START if (click - a).Length < (click - b).Length else END
        tip, other_end = (a, b) if pos == START else (b, a)
        direction = tip - other_end
        if direction.Length < 1e-9:
            return None
        direction.normalize()
        ray = Part.LineSegment(tip + direction * 1e-6, tip + direction * 1e6)
        best = None
        for other, curve in curves(sketch):
            if other == geo:
                continue
            try:
                hits = ray.intersectCC(curve)
            except Exception:
                continue
            for p in hits:
                q = V(p.X, p.Y, 0)
                d = (q - tip).Length
                if d > 1e-7 and (best is None or d < best[0]):
                    best = (d, q, other)
        if best is None:
            return None
        return pos, (best[1].x, best[1].y), best[2], best[0]
    if g.TypeId == "Part::GeomArcOfCircle":
        a, b = g.StartPoint, g.EndPoint
        pos = START if (click - a).Length < (click - b).Length else END
        circle = Part.Circle(g.Center, NORMAL, g.Radius)
        start, end = g.FirstParameter, g.LastParameter
        best = None
        for other, curve in curves(sketch):
            if other == geo:
                continue
            try:
                hits = circle.intersectCC(curve)
            except Exception:
                continue
            for p in hits:
                q = V(p.X, p.Y, 0)
                angle = math.atan2(q.y - g.Center.y, q.x - g.Center.x)
                if pos == END:
                    grow = (angle - end) % (2.0 * math.pi)
                else:
                    grow = (start - angle) % (2.0 * math.pi)
                room = 2.0 * math.pi - (end - start)  # the arc cannot grow round onto itself
                if 1e-7 < grow < room - 1e-7 and (best is None or grow < best[0]):
                    best = (grow, q, other)
        if best is None:
            return None
        return pos, (best[1].x, best[1].y), best[2], best[0]
    return None


def extend_curve(sketch, geo, plan):
    """Carry out extend_plan's plan: the end grows and stays on the curve it met (a
    PointOnObject constraint). Returns True when the curve changed."""
    pos, _point, other, increment = plan
    if sketch.extend(geo, float(increment), int(pos)) not in (None, 0):
        return False
    try:
        sketch.addConstraint(_con("PointOnObject", geo, pos, other))
    except Exception:
        pass
    return True


# -- Break ---------------------------------------------------------------------------------------
def break_curve(sketch, geo, point):
    """Fusion's Break: split curve `geo` at the intersections nearest to `point` on each
    side (2 or 3 pieces; on a closed curve two arcs). The pieces stay joined (FreeCAD's
    split puts a Coincident at each cut). Returns the number of cuts made (0: no
    intersection near the click)."""
    g = sketch.Geometry[geo]
    found = piece(sketch, geo, point)
    if found is None:
        return 0
    t0, t1, closed = found
    first, last = g.FirstParameter, g.LastParameter
    cut_points = []
    for t in (t0, t1):
        if closed or first + 1e-9 < t < last - 1e-9:
            p = g.value(t)
            cut_points.append(V(p.x, p.y, 0))
    if closed:
        start_cut = cut_points[0]
        sketch.split(geo, start_cut)  # the circle opens there (one arc)
        sketch.split(geo, cut_points[1])
        # FreeCAD's split joins the second cut and makes the arcs concentric, but leaves
        # the circle's own seam (the first cut) open. Fusion's pieces are separate curves
        # joined where they were cut: both cuts joined, the centres free (with the
        # centres tied as well, the second join would be half redundant)
        a, b = geo, sketch.GeometryCount - 1
        for i in reversed(range(len(sketch.Constraints))):
            c = sketch.Constraints[i]
            if (
                c.Type == "Coincident"
                and {c.First, c.Second} == {a, b}
                and c.FirstPos == CENTRE
                and c.SecondPos == CENTRE
            ):
                sketch.delConstraint(i)
        sketch.addConstraint(_con("Coincident", b, END, a, START))
        return 2
    count = 0
    for p in cut_points:
        # after the first split the curve is two pieces: cut the one that holds p
        target = _holding(sketch, [geo, sketch.GeometryCount - 1] if count else [geo], p)
        if target is None:
            continue
        sketch.split(target, p)
        count += 1
    return count


def _holding(sketch, candidates, p):
    best = None
    for geo in candidates:
        if geo < 0 or geo >= sketch.GeometryCount:
            continue
        g = sketch.Geometry[geo]
        try:
            t = g.parameter(p)
            if not (g.FirstParameter + 1e-9 < t < g.LastParameter - 1e-9):
                continue
            d = (g.value(t) - p).Length
        except Exception:
            continue
        if d < 1e-6 and (best is None or d < best[0]):
            best = (d, geo)
    return best[1] if best else None


# -- small helpers for the tools ---------------------------------------------------------
def line_ends(sketch, geo):
    g = sketch.Geometry[geo]
    return _xy(g.StartPoint), _xy(g.EndPoint)


def is_line(sketch, geo):
    try:
        if geo >= 0:
            return sketch.Geometry[geo].TypeId == "Part::GeomLineSegment"
        return list(sketch.ExternalGeo)[-geo - 1].TypeId == "Part::GeomLineSegment"
    except Exception:
        return False


def geometry(sketch, geo):
    """The Part geometry of a sketch curve (negative: external, -1 / -2 the axes)."""
    if geo >= 0:
        return sketch.Geometry[geo]
    return list(sketch.ExternalGeo)[-geo - 1]
