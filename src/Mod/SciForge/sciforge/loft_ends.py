# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's loft end conditions and Tangent Edges Merge on top of OpenCASCADE's loft (no GUI
code). The solid Loft (loft.py) and the surface Loft (surface_geom.py) both use it.

OpenCASCADE lofts through the profiles (Part.makeLoft); every side face it makes is a
B-spline surface (a cone or a ruled face is converted to one) running along the profile in u
and from the first profile to the last in v. Its rows of control points at the profiles are
kept, and each column is interpolated again (loft_ends_core.interpolate, cubic) with the end
derivatives the conditions ask for; the faces are then sewn to the profile faces into a solid
(a surface loft keeps them open).

  Direction       (sketch profile) the loft leaves the profile along its normal, tilted by
                  the takeoff angle, with a derivative of weight x the distance to the next
                  profile
  Tangent         (face of a body, or edges of a body for a surface loft) the loft carries on
                  the faces next to the picked face (the faces the edges bound), tangent to
                  them (G1)
  Curvature       the same, and as curved as those faces across the edge (G2)
  Point Tangent   (point) the loft closes over the point like a dome: tangent there to the
                  plane of the profile next to it
The other end of a loft with one condition is free (no bend there: a natural end).

The rows the columns go through are the profiles, plus, for a loft along rails or a
centerline, the stations SciForge places between them (thru_rows): the end conditions then
bend the loft between the end profile and the first station only, and the rails or the
centerline lead it everywhere else. A closed loft runs through its first profile twice (as its
start and its end): a condition there gives both the same direction, so the loop passes
smoothly through that profile.

Tangent Edges Merge (merged_wire): every run of profile edges joined smoothly becomes one
edge, so the loft makes one smooth side face for it instead of one face per edge (Fusion's
Merge; its Keep is the plain loft).
"""

import FreeCAD as App

from . import loft_ends_core as core
from .loft_ends_core import EndError

TOL = 1e-7
TANGENT_COS = 1.0 - 1e-6  # two directions this close are one (a tangent joint)


def kind_of(section):
    """sketch / face / point (edge: an edge of a body in a surface loft, which offers what a
    face offers): which end conditions a profile offers."""
    kind = getattr(section, "kind", None)
    if kind:
        return kind
    if section.point is not None:
        return "point"
    from . import extrude

    return "sketch" if extrude.is_sketch(section.profile[0]) else "face"


def _conditions_kind(kind):
    return "face" if kind == "edge" else kind


def active(options):
    """True when a start or end condition other than free is set."""
    return options.get("start_condition", "free") != "free" or (
        options.get("end_condition", "free") != "free"
    )


def check(sections, options, closed=False):
    """Refuse conditions the end profiles cannot take (with the reason)."""
    for which, section in (("start", sections[0]), ("end", sections[-1])):
        condition = options.get(which + "_condition", "free")
        if closed and which == "end":
            continue
        try:
            core.check(
                condition,
                _conditions_kind(kind_of(section)),
                options.get(which + "_weight", core.DEFAULT_WEIGHT),
                options.get(which + "_angle", core.DEFAULT_ANGLE),
            )
        except EndError as exc:
            raise EndError("%s profile: %s" % ("First" if which == "start" else "Last", exc))
    if closed:
        # The loop goes on from the last profile back to the first: the last profile's
        # condition does not apply (the callers pass it as free).
        if options.get("start_condition", "free") not in ("free", "direction"):
            raise EndError(
                "A closed loft runs through its first profile, so it cannot end on faces "
                "there. Use Direction (a sketch profile), or clear Closed."
            )


# -- the rows a loft goes through -------------------------------------------------------------
class Row:
    """One section a loft goes through: a profile, or a station between two profiles (rails,
    a centerline). `normal` is None for a section that is not flat (found on the loft's sides
    by its distance instead of its plane)."""

    def __init__(self, item, center, normal=None, point=None):
        self.item = item
        self.center = App.Vector(center)
        self.normal = App.Vector(normal) if normal is not None else None
        self.point = App.Vector(point) if point is not None else None


class CurveSection:
    """A surface loft's profile, for its end conditions: a curve (a wire, open or closed) or
    a point. kind: "sketch" (sketch curves: Connected / Direction, `normal` the sketch's),
    "edge" (edges of a body: Connected / Tangent / Curvature along the faces they bound,
    `guide_pairs` [(edge, face)]), "point" (Sharp / Point Tangent)."""

    def __init__(self, item, kind, normal=None, guide_pairs=None, profile=None):
        import Part

        self.kind = kind
        self.profile = profile
        self.face = None
        self.guide_pairs = guide_pairs
        if item.ShapeType == "Vertex":
            self.point = App.Vector(item.Point)
            self.wires = []
            self.center = App.Vector(item.Point)
            self.normal = None
            return
        self.point = None
        self.wires = [item]
        self.normal = App.Vector(normal) if normal is not None else None
        self.center = item.BoundBox.Center
        if item.isClosed() and self.normal is not None:
            try:
                self.center = Part.Face(item).CenterOfMass
            except Exception:
                pass


def profile_row(section, index=0, merge=False):
    """The row of a profile (its wire `index`, made polynomial, its tangent runs joined with
    merge; a point stays a point)."""
    import Part

    if section.point is not None:
        return Row(Part.Vertex(section.point), section.point, None, section.point)
    wire = section.wires[index]
    if merge:
        wire = merged_wire(wire)
    return Row(polynomial_wire(wire), section.center, section.normal)


def as_wire(shape):
    """A Part.Wire of the shape's edges (transformGeometry and MakePipeShell.simulate give
    plain shapes)."""
    import Part

    if isinstance(shape, Part.Wire):
        return shape
    if shape.Wires and len(shape.Wires) == 1 and isinstance(shape.Wires[0], Part.Wire):
        return shape.Wires[0]
    return Part.Wire(Part.__sortEdges__(shape.Edges))


def between_profiles(path, first, last):
    """The part of a centerline (curves.Path) from where the first profile sits to where the
    last one does (Fusion's loft ends at its profiles even when the line runs on)."""
    s0 = path.length_at(first)
    s1 = path.length_at(last)
    if s1 - s0 < 1e-6 or (s0 < 1e-6 and s1 > path.length - 1e-6):
        return path
    return path.sub(s0, s1)


def simulated(mk, count):
    """The sections a pipe shell (MakePipeShell) passes through at `count` places along its
    spine, as wires (OpenCASCADE gives the last one twice: repeats are dropped)."""
    found = []
    for shape in mk.simulate(count):
        if not shape.Edges:
            continue
        wire = as_wire(shape)
        if found and (wire.BoundBox.Center - found[-1].BoundBox.Center).Length < 1e-6:
            continue
        found.append(wire)
    return found


def station_row(wire):
    """A row for a station wire (flat or not)."""
    import Part

    wire = as_wire(wire)
    normal = None
    try:
        plane = wire.findPlane()
        if plane is not None:
            normal = App.Vector(plane.Axis)
    except Exception:
        normal = None
    center = wire.BoundBox.Center
    if wire.isClosed() and normal is not None:
        try:
            center = Part.Face(wire).CenterOfMass
        except Exception:
            pass
    return Row(polynomial_wire(wire), center, normal)


# -- the loft ----------------------------------------------------------------------------------
def thru(sections, index, options, merge=False):
    """The solid lofted through wire `index` of every section (a point stays a point), its
    ends meeting the end conditions."""
    rows = [profile_row(s, index, merge) for s in sections]
    return thru_rows(rows, sections[0], sections[-1], options, solid=True)


def thru_rows(
    rows,
    first,
    last,
    options,
    solid=True,
    closed=False,
    first_next=None,
    last_next=None,
):
    """The loft through `rows` (profiles and stations, in loft order) with the end conditions
    of profile sections `first` and `last` (Section-like: point, wires, center, normal,
    profile). first_next / last_next: the profile next to each end (for the derivative's
    length and the Direction's side; default the neighbouring row). solid: caps the ends
    and makes a solid; else the open side faces (a surface). closed: the loft returns to the
    first profile (rows already end with it again); the first profile's condition sets the
    direction it passes through it with."""
    import Part

    items = [r.item for r in rows]
    try:
        shell = Part.makeLoft(items, False, False, False)
    except Exception as exc:
        raise EndError(
            "The profiles cannot be lofted (%s). Check that they face the same way and do not "
            "cross each other." % (str(exc) or type(exc).__name__)
        )
    centers = [r.center for r in rows]
    params = core.chord_params([(c.x, c.y, c.z) for c in centers])
    start = _end_rule(first, first_next or rows[1], options, "start")
    if closed:
        end = start  # through the first profile again, the same way
    else:
        end = _end_rule(last, last_next or rows[-2], options, "end")
    faces = [_rebuilt(face, rows, params, (start, end)) for face in shell.Faces]
    if not solid:
        return _open_shell(faces)
    if not closed:
        for row in (rows[0], rows[-1]):
            if row.point is None:
                faces.append(Part.Face(row.item))
    return _close(faces)


def polynomial_wire(wire):
    """The wire with every rational edge (circle, arc, ellipse, rational spline) replaced by
    a polynomial B-spline within 1e-7 mm. OpenCASCADE measures the volume of rational
    B-spline faces up to 1 % wrong (a cone lofted from a circle to a point came out 1055.8
    instead of 1047.2 mm^3; its mesh 1047.1), so Inspect and the golden models would lie;
    polynomial sides measure right."""
    import Part

    edges = []
    changed = False
    for edge in wire.OrderedEdges:
        curve = edge.Curve
        if curve.TypeId in ("Part::GeomLine", "Part::GeomLineSegment") or not _rational(edge):
            edges.append(edge)
            continue
        try:
            spline = edge.toNurbs().Edges[0].Curve
            plain = spline.approximateBSpline(1e-7, 64, 8, "C2")
            if edge.Orientation == "Reversed":
                plain.reverse()
            edges.append(Part.Edge(plain))
            changed = True
        except Exception:
            edges.append(edge)
    if not changed:
        return wire
    try:
        return Part.Wire(edges)
    except Exception:
        return wire


def _rational(edge):
    try:
        spline = edge.toNurbs().Edges[0].Curve
        return spline.isRational()
    except Exception:
        return False


def _close(faces):
    import Part

    try:
        sewing = Part.makeShell(faces)
    except Exception as exc:
        raise EndError("The loft with these end conditions does not close (%s)." % exc)
    shell = sewing
    try:
        sewn = sewing.copy()
        sewn.sewShape()
        if sewn.Shells:
            shell = sewn.Shells[0]
    except Exception:
        pass
    if shell.ShapeType != "Shell":
        raise EndError("The loft with these end conditions does not close.")
    try:
        # Part.makeSolid, not Part.Solid: FreeCAD 1.1's constructor lets its error pass
        # every except clause (the script just stops).
        solid = Part.makeSolid(shell)
    except Exception as exc:
        raise EndError("The loft with these end conditions does not close (%s)." % exc)
    if solid.ShapeType != "Solid" and solid.Solids:
        solid = solid.Solids[0]
    if solid.Volume < 0:
        solid = solid.copy()
        solid.reverse()
    if not solid.isValid():
        fixed = solid.copy()
        try:
            fixed.fix(TOL, TOL, 1e-3)
        except Exception:
            pass
        if not fixed.isValid():
            raise EndError(
                "These end conditions fold the loft over itself. Lower the weight or change "
                "the angle."
            )
        solid = fixed
    return solid


def _open_shell(faces):
    """The side faces of a surface loft sewn where they meet."""
    import Part

    if len(faces) == 1:
        return faces[0]
    compound = Part.makeCompound(faces)
    sewn = compound.copy()
    try:
        sewn.sewShape()
    except Exception:
        return compound
    if sewn.isNull() or not sewn.Faces:
        return compound
    return sewn


# -- Tangent Edges Merge ---------------------------------------------------------------------------
def merged_wire(wire):
    """Fusion's Tangent Edges Merge for one profile: every run of edges joined smoothly
    (tangent) becomes one polynomial B-spline edge, so the loft makes one face for the run.
    Edges meeting at a corner stay apart. Returns the wire unchanged when nothing joins."""
    import Part

    edges = list(wire.OrderedEdges)
    if len(edges) < 2:
        return wire
    runs = _traversal(edges)
    if runs is None:
        return wire
    closed = wire.isClosed()
    joints = [_tangent_joint(runs[i], runs[i + 1]) for i in range(len(runs) - 1)]
    wrap = _tangent_joint(runs[-1], runs[0]) if closed else False
    if not any(joints) and not wrap:
        return wire
    # Chains of edges joined smoothly; on a closed wire a chain may run over the start.
    chains = [[runs[0]]]
    for i, smooth in enumerate(joints):
        if smooth:
            chains[-1].append(runs[i + 1])
        else:
            chains.append([runs[i + 1]])
    if closed and wrap and len(chains) > 1:
        chains[0] = chains[-1] + chains[0]
        chains.pop()
    out = []
    for chain in chains:
        if len(chain) == 1:
            out.append(chain[0][0])
            continue
        joined = _joined(chain)
        if joined is None:
            out.extend(e for e, _rev in chain)
        else:
            out.append(joined)
    try:
        merged = Part.Wire(out)
    except Exception:
        return wire
    return merged if merged.isClosed() == closed else wire


def _traversal(edges):
    """[(edge, reversed)] in wire order, `reversed` when the edge runs last -> first along
    the wire; None when the edges do not connect end to end."""
    out = []
    for i, edge in enumerate(edges):
        a = edge.valueAt(edge.FirstParameter)
        b = edge.valueAt(edge.LastParameter)
        if i == 0:
            if len(edges) > 1:
                nxt = edges[1]
                ends = [nxt.valueAt(nxt.FirstParameter), nxt.valueAt(nxt.LastParameter)]
                rev = min((a - p).Length for p in ends) < min((b - p).Length for p in ends)
            else:
                rev = False
        else:
            prev_edge, prev_rev = out[-1]
            end = prev_edge.valueAt(
                prev_edge.FirstParameter if prev_rev else prev_edge.LastParameter
            )
            if (a - end).Length <= (b - end).Length:
                rev = False
                gap = (a - end).Length
            else:
                rev = True
                gap = (b - end).Length
            if gap > 1e-5:
                return None
        out.append((edge, rev))
    return out


def _direction(edge, rev, at_end):
    """Unit tangent along the wire's direction at the edge's start (at_end False) / end."""
    u = edge.LastParameter if (at_end != rev) else edge.FirstParameter
    t = App.Vector(edge.tangentAt(u))
    if rev:
        t = t * -1.0
    if t.Length < 1e-12:
        return None
    t.normalize()
    return t


def _tangent_joint(a, b):
    ta = _direction(a[0], a[1], True)
    tb = _direction(b[0], b[1], False)
    return ta is not None and tb is not None and ta.dot(tb) >= TANGENT_COS


def _polynomial_piece(edge, rev):
    """The edge as a polynomial B-spline curve running along the wire."""
    import Part

    curve = edge.Curve
    a, b = edge.FirstParameter, edge.LastParameter
    if curve.TypeId in ("Part::GeomLine", "Part::GeomLineSegment"):
        p0, p1 = edge.valueAt(a), edge.valueAt(b)
        if rev:
            p0, p1 = p1, p0
        spline = Part.BSplineCurve()
        spline.buildFromPolesMultsKnots([p0, p1], [2, 2], [0.0, 1.0], False, 1)
        return spline
    spline = edge.toNurbs().Edges[0].Curve
    try:
        spline = spline.copy()
        lo, hi = spline.FirstParameter, spline.LastParameter
        if abs(lo - a) > 1e-12 or abs(hi - b) > 1e-12:
            if lo <= a + 1e-12 and b <= hi + 1e-12:
                spline.segment(a, b)
    except Exception:
        pass
    if spline.isRational():
        spline = spline.approximateBSpline(1e-7, 64, 8, "C2")
    if rev:
        spline.reverse()
    return spline


def _joined(chain):
    """One B-spline curve edge through the chain's edges, or None."""
    try:
        pieces = [_polynomial_piece(e, rev) for e, rev in chain]
        degree = max(p.Degree for p in pieces)
        for p in pieces:
            if p.Degree < degree:
                p.increaseDegree(degree)
        curve = pieces[0]
        for p in pieces[1:]:
            if not curve.join(p):
                return None
        return curve.toShape()
    except Exception:
        return None


# -- one side face -------------------------------------------------------------------------------
def _bspline(face, rows):
    """The face's surface as a non-periodic B-spline cut to the face."""
    import Part

    surface = face.Surface
    if surface.TypeId == "Part::GeomPlane":
        return _ruled_plane(face, rows)
    if surface.TypeId != "Part::GeomBSplineSurface":
        surface = face.toNurbs().Faces[0].Surface
    else:
        surface = surface.copy()
    for periodic, unset in (
        (surface.isUPeriodic(), surface.setUNotPeriodic),
        (surface.isVPeriodic(), surface.setVNotPeriodic),
    ):
        if periodic:
            unset()
    u0, u1, v0, v1 = face.ParameterRange
    b = surface.bounds()
    if (
        abs(u0 - b[0]) > 1e-9
        or abs(u1 - b[1]) > 1e-9
        or abs(v0 - b[2]) > 1e-9
        or abs(v1 - b[3]) > 1e-9
    ):
        surface.segment(u0, u1, v0, v1)
    if not isinstance(surface, Part.BSplineSurface):
        raise EndError("internal: the loft's side is not a B-spline surface")
    return surface


def _ruled_plane(face, rows):
    """A flat side between two straight edges (or an edge and a point: OpenCASCADE makes
    triangles when a polygon is lofted to a point) as a bilinear B-spline surface, from the
    edge on the first profile to the one (or the point) on the last."""
    import Part

    first, last = rows[0], rows[-1]
    refused = EndError("These end conditions cannot be built for these profiles.")
    if not all(_straight(e) for e in face.Edges):
        raise refused

    def on(edge, row):
        return all(_plane_distance(v.Point, row) < 1e-6 for v in edge.Vertexes)

    bottom = [e for e in face.Edges if on(e, first) and not on(e, last)]
    top = [e for e in face.Edges if on(e, last) and not on(e, first)]
    if len(bottom) != (0 if first.point is not None else 1):
        raise refused
    if len(top) != (0 if last.point is not None else 1):
        raise refused
    if bottom:
        a, b = bottom[0].Vertexes[0].Point, bottom[0].Vertexes[-1].Point
    else:
        a = b = first.point
    if top:
        q0, q1 = top[0].Vertexes[0].Point, top[0].Vertexes[-1].Point
        if bottom:
            other = _side_end(face, a, first)
            if other is not None and (other - q1).Length < (other - q0).Length:
                q0, q1 = q1, q0
    else:
        q0 = q1 = last.point
    surface = Part.BSplineSurface()
    surface.buildFromPolesMultsKnots(
        [[a, q0], [b, q1]], [2, 2], [2, 2], [0.0, 1.0], [0.0, 1.0], False, False, 1, 1
    )
    return surface


def _straight(edge):
    ps = [v.Point for v in edge.Vertexes]
    return len(ps) == 2 and abs(edge.Length - (ps[1] - ps[0]).Length) < 1e-7


def _side_end(face, point, first):
    """The far end of the face's edge that leaves `point` off the first profile's plane (a
    side edge of the loft), or None."""
    for edge in face.Edges:
        ps = [v.Point for v in edge.Vertexes]
        if len(ps) != 2:
            continue
        for here, there in ((ps[0], ps[1]), (ps[1], ps[0])):
            if (here - point).Length < 1e-7 and _plane_distance(there, first) > 1e-6:
                return there
    return None


def _plane_distance(point, section):
    """How far `point` is from a section: from its point, its plane, or (a section that is
    not flat) its curve."""
    if section.point is not None:
        return (point - section.point).Length
    if section.normal is not None:
        return abs((point - section.center).dot(section.normal))
    return _wire_distance(point, section)


def _wire_distance(point, row):
    import Part

    try:
        return row.item.distToShape(Part.Vertex(point))[0]
    except Exception:
        return float("inf")


def _iso_params(surface, rows):
    """The v of each row on the surface (first and last at the ends), and whether the
    surface runs from the last row to the first."""
    u0, u1, v0, v1 = surface.bounds()
    um = (u0 + u1) / 2.0
    first, last = rows[0], rows[-1]
    at_start = surface.value(um, v0)
    reverse = False
    # A closed loft starts and ends on the same profile: it runs the way it was built.
    if not _same_row(first, last):
        reverse = _plane_distance(at_start, last) < _plane_distance(at_start, first) - 1e-9
    order = list(reversed(rows)) if reverse else list(rows)
    values = [v0]
    for row in order[1:-1]:
        values.append(_find_v(surface, row, um, values[-1], v1))
    values.append(v1)
    return values, reverse


def _same_row(a, b):
    if a is b:
        return True
    if a.point is not None or b.point is not None:
        return False
    try:
        return (a.center - b.center).Length < 1e-9 and abs(a.item.Length - b.item.Length) < 1e-9
    except Exception:
        return False


def _find_v(surface, row, um, lo, hi):
    """v in (lo, hi) where the surface's iso line u = um meets the row."""
    if row.point is None and row.normal is None:
        return _nearest_v(surface, row, um, lo, hi)

    def f(v):
        return (surface.value(um, v) - row.center).dot(row.normal)

    steps = 64
    prev_v, prev_f = lo, f(lo)
    for i in range(1, steps + 1):
        v = lo + (hi - lo) * i / float(steps)
        fv = f(v)
        if abs(fv) < 1e-12:
            return v
        if (prev_f < 0) != (fv < 0):
            a, b, fa = prev_v, v, prev_f
            for _ in range(80):
                m = (a + b) / 2.0
                fm = f(m)
                if (fa < 0) == (fm < 0):
                    a, fa = m, fm
                else:
                    b = m
            return (a + b) / 2.0
        prev_v, prev_f = v, fv
    return _nearest_v(surface, row, um, lo, hi)


def _nearest_v(surface, row, um, lo, hi):
    """v in (lo, hi) where the iso line u = um comes nearest the row's curve."""

    def f(v):
        return _wire_distance(surface.value(um, v), row)

    steps = 48
    best = None
    for i in range(1, steps):
        v = lo + (hi - lo) * i / float(steps)
        d = f(v)
        if best is None or d < best[0]:
            best = (d, v)
    if best is None:
        raise EndError("internal: a profile is not on the loft's side surface")
    step = (hi - lo) / float(steps)
    a, b = max(lo, best[1] - step), min(hi, best[1] + step)
    g = 0.6180339887498949
    c, d = b - g * (b - a), a + g * (b - a)
    fc, fd = f(c), f(d)
    for _ in range(60):
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - g * (b - a)
            fc = f(c)
        else:
            a, c, fc = c, d, fd
            d = a + g * (b - a)
            fd = f(d)
    v = (a + b) / 2.0
    if f(v) > 1e-3:
        raise EndError("internal: a profile is not on the loft's side surface")
    return v


def _rebuilt(face, rows, params, ends):
    """The side face again, its columns re-interpolated with the end conditions."""
    import Part

    surface = _bspline(face, rows)
    values, reverse = _iso_params(surface, rows)
    isos = [surface.vIso(v) for v in values]
    count = surface.NbUPoles
    data_rows = []
    weights = []
    for iso in isos:
        poles = iso.getPoles()
        w = iso.getWeights() if iso.isRational() else [1.0] * count
        weights.append(w)
        data_rows.append(poles)
    order = list(range(len(rows)))
    if reverse:
        order.reverse()
    # The data in loft order (first profile first), as the rules expect it.
    data = [data_rows[order.index(k)] for k in range(len(rows))]
    wdata = [weights[order.index(k)] for k in range(len(rows))]
    start = ends[0](data, wdata)
    end = ends[1](data, wdata)
    flat = []
    for poles, w in zip(data, wdata):
        line = []
        for p, wi in zip(poles, w):
            line += [p.x * wi, p.y * wi, p.z * wi, wi]
        flat.append(line)
    knots, controls = core.interpolate(params, flat, start, end)
    if reverse:
        # Back to the surface's own direction (its u and its outside stay as they were).
        knots = [1.0 - k for k in reversed(knots)]
        controls = list(reversed(controls))
    vknots, vmults = core.knots_and_mults(knots)
    poles, pweights = [], []
    for i in range(count):
        column, wcol = [], []
        for c in controls:
            wi = c[4 * i + 3]
            if wi <= 1e-9:
                raise EndError("These end conditions cannot be built for these profiles.")
            column.append(App.Vector(c[4 * i] / wi, c[4 * i + 1] / wi, c[4 * i + 2] / wi))
            wcol.append(wi)
        poles.append(column)
        pweights.append(wcol)
    new = Part.BSplineSurface()
    new.buildFromPolesMultsKnots(
        poles,
        surface.getUMultiplicities(),
        vmults,
        surface.getUKnots(),
        vknots,
        False,
        False,
        surface.UDegree,
        core.DEGREE,
        pweights,
    )
    result = Part.Face(new)
    if face.Orientation == "Reversed":
        result.reverse()
    return result


# -- the rules at each end -------------------------------------------------------------------
def _end_rule(section, neighbour, options, which):
    """A function (data rows, weight rows) -> the interpolation's end condition, for the end
    profile `section` (the first: which "start"; the last: "end"); `neighbour` is the profile
    (or station) next to it."""
    condition = options.get(which + "_condition", "free")
    if condition == "free":
        return lambda data, wdata: ("free",)
    weight = float(options.get(which + "_weight", core.DEFAULT_WEIGHT))
    angle = float(options.get(which + "_angle", core.DEFAULT_ANGLE))
    chord = (neighbour.center - section.center).Length
    m = core.magnitude(weight, chord)
    sign = 1.0 if which == "start" else -1.0
    row = 0 if which == "start" else -1
    near_row = 1 if which == "start" else -2  # the profile next to a point

    def homogeneous(vectors, w):
        line = []
        for t, wi in zip(vectors, w):
            line += [t.x * wi, t.y * wi, t.z * wi, 0.0]
        return line

    if condition == "direction":
        if section.normal is None:
            raise EndError("Direction needs a flat profile (a sketch).")
        normal = _toward(section.normal, neighbour.center - section.center)
        rho = _reach(section)

        def direction(data, wdata):
            vectors = []
            for p in data[row]:
                out = p - section.center
                out = out - normal * out.dot(normal)
                d = core.takeoff(tuple(normal), tuple(out * (1.0 / rho)), angle)
                # The loft leaves the first profile along d and arrives at the last one
                # against it (d points from each end profile into the loft).
                vectors.append(App.Vector(*d) * (m * sign))
            return ("d1", homogeneous(vectors, wdata[row]))

        return direction
    if condition == "point_tangent":
        normal = neighbour.normal
        if normal is None:
            raise EndError("Point Tangent needs a flat profile next to the point.")
        rho = _reach(neighbour)

        def dome(data, wdata):
            vectors = []
            for q in data[near_row]:
                r = q - neighbour.center
                r = r - normal * r.dot(normal)
                vectors.append(r * (m / rho) * sign)
            return ("d1", homogeneous(vectors, wdata[row]))

        return dome
    if condition in ("tangent", "curvature"):
        guide = _FaceGuide(section, neighbour.center - section.center)

        def carry(data, wdata):
            firsts, seconds = [], []
            for p in data[row]:
                w, accel = guide.at(p, condition == "curvature")
                # Leaving the face (start): against w; arriving (end): along w.
                firsts.append(w * (-m if which == "start" else m))
                seconds.append(accel * (m * m))
            if condition == "tangent":
                return ("d1", homogeneous(firsts, wdata[row]))
            return ("d2", homogeneous(firsts, wdata[row]), homogeneous(seconds, wdata[row]))

        return carry
    raise EndError("unknown end condition %r" % condition)


def _toward(normal, direction):
    n = App.Vector(normal)
    return n * -1.0 if n.dot(direction) < 0 else n


def _reach(section):
    """How far the profile reaches from its middle: the largest distance of its outline (the
    radius of a circle, the corner of a square)."""
    wire = section.wires[0] if getattr(section, "wires", None) else section.item
    points = [v.Point for v in wire.Vertexes] + wire.discretize(64)
    reach = max((p - section.center).Length for p in points) if points else 0.0
    if reach < 1e-9:
        raise EndError("The profile is too small for an end condition.")
    return reach


class _FaceGuide:
    """The faces of the part next to a picked face (or, for edges of a body picked as a
    surface loft's profile, the faces those edges bound): which way they run away from the
    edges and how they bend across them."""

    def __init__(self, section, toward):
        self.normal = None
        if section.normal is not None:
            self.normal = _toward(section.normal, toward)  # out of the part, toward the loft
        pairs = getattr(section, "guide_pairs", None)
        if pairs is not None:
            if not pairs:
                raise EndError("The picked edges have no face next to them to be tangent to.")
            self.pairs = list(pairs)
            self.corners = []
            for edge, _face in self.pairs:
                self.corners += [v.Point for v in edge.Vertexes]
            return
        from . import curves

        obj, _sub = section.profile
        shape = curves.to_global(obj.Shape, obj)
        picked = section.face
        others = [f for f in shape.Faces if not _same_face(f, picked)]
        self.pairs = []  # (an edge of the picked face, the part's face on its other side)
        for edge in picked.Edges:
            face = next((f for f in others if _shares(f, edge)), None)
            if face is None:
                raise EndError("The picked face has no face next to it to be tangent to.")
            self.pairs.append((edge, face))
        self.corners = [v.Point for v in picked.Vertexes]

    def at(self, point, curvature):
        """(w, acceleration) where `point` (a control point of the profile's outline) is:
        w the unit direction in the neighbouring face, square to the edge, running into that
        face; at a corner the mean of the faces meeting there (the loft's sides stay closed)."""
        here = _vertex(point)
        if any((point - c).Length < 1e-6 for c in self.corners):
            pairs = [(e, f) for e, f in self.pairs if e.distToShape(here)[0] < 1e-6]
        else:
            pairs = []
        if not pairs:
            pairs = [min(self.pairs, key=lambda pair: pair[0].distToShape(here)[0])]
        ws, accels = [], []
        for edge, face in pairs:
            w, accel = self._one(edge, face, point, curvature)
            ws.append(w)
            accels.append(accel)
        w = App.Vector()
        for x in ws:
            w += x
        if w.Length < 1e-12:
            raise EndError("The faces next to the profile meet it from opposite sides.")
        w.normalize()
        accel = App.Vector()
        for x in accels:
            accel += x * (1.0 / len(accels))
        return w, accel

    def _one(self, edge, face, point, curvature):
        q = edge.distToShape(_vertex(point))[1][0][0]
        t = edge.tangentAt(edge.Curve.parameter(q))
        t.normalize()
        surface = face.Surface
        u, v = surface.parameter(q)
        su = surface.getDN(u, v, 1, 0)
        sv = surface.getDN(u, v, 0, 1)
        n = su.cross(sv)
        if n.Length < 1e-12:
            raise EndError("The face next to the profile has no tangent plane there.")
        n.normalize()
        w = n.cross(t)
        if w.Length < 1e-12:
            raise EndError("The face next to the profile runs along its edge.")
        w.normalize()
        if not self._runs_into(face, surface, u, v, w, su, sv):
            w = w * -1.0
        accel = App.Vector()
        if curvature:
            a, b = _in_basis(w, su, sv)
            suu = surface.getDN(u, v, 2, 0)
            suv = surface.getDN(u, v, 1, 1)
            svv = surface.getDN(u, v, 0, 2)
            second = suu * (a * a) + suv * (2 * a * b) + svv * (b * b)
            accel = n * second.dot(n)
        return w, accel

    def _runs_into(self, face, surface, u, v, w, su, sv):
        """True when a small step along w from the edge lands on the face itself."""
        a, b = _in_basis(w, su, sv)
        size = max(face.BoundBox.DiagonalLength, 1.0)
        for step in (1e-3, 1e-2):
            scale = step * size / max(w.Length, 1e-12)
            try:
                spot = surface.value(u + a * scale, v + b * scale)
                if face.isInside(spot, 1e-6 * size, True):
                    return True
                back = surface.value(u - a * scale, v - b * scale)
                if face.isInside(back, 1e-6 * size, True):
                    return False
            except Exception:
                continue
        if self.normal is None:
            return True
        return w.dot(self.normal) < 0  # can't tell: the face lies on the part's side


def _same_face(a, b):
    return abs(a.Area - b.Area) < 1e-9 and (a.CenterOfMass - b.CenterOfMass).Length < 1e-9


def _shares(face, edge):
    for e in face.Edges:
        if e.isSame(edge):
            return True
        if (
            abs(e.Length - edge.Length) < 1e-7
            and (e.CenterOfMass - edge.CenterOfMass).Length < 1e-7
        ):
            return True
    return False


def _in_basis(w, su, sv):
    """a, b with a su + b sv = w (least squares)."""
    g11, g12, g22 = su.dot(su), su.dot(sv), sv.dot(sv)
    r1, r2 = w.dot(su), w.dot(sv)
    det = g11 * g22 - g12 * g12
    if abs(det) < 1e-18:
        return 0.0, 0.0
    return (r1 * g22 - r2 * g12) / det, (g11 * r2 - g12 * r1) / det


def _vertex(point):
    import Part

    return Part.Vertex(point)
