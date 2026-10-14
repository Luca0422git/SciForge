# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's loft end conditions on top of OpenCASCADE's loft (no GUI code).

OpenCASCADE lofts through the profiles (Part.makeLoft); every side face it makes is a
B-spline surface (a cone or a ruled face is converted to one) running along the profile in u
and from the first profile to the last in v. Its rows of control points at the profiles are
kept, and each column is interpolated again (loft_ends_core.interpolate, cubic) with the end
derivatives the conditions ask for; the faces are then sewn to the profile faces into a solid.

  Direction       (sketch profile) the loft leaves the profile along its normal, tilted by
                  the takeoff angle, with a derivative of weight x the distance to the next
                  profile
  Tangent         (face of a body) the loft carries on the faces next to the picked one,
                  tangent to them (G1)
  Curvature       (face of a body) the same, and as curved as those faces across the edge (G2)
  Point Tangent   (point) the loft closes over the point like a dome: tangent there to the
                  plane of the profile next to it
The other end of a loft with one condition is free (no bend there: a natural end).
"""

import FreeCAD as App

from . import loft_ends_core as core
from .loft_ends_core import EndError

TOL = 1e-7


def kind_of(section):
    """sketch / face / point: which end conditions a profile offers."""
    if section.point is not None:
        return "point"
    from . import extrude

    return "sketch" if extrude.is_sketch(section.profile[0]) else "face"


def active(options):
    """True when a start or end condition other than free is set."""
    return options.get("start_condition", "free") != "free" or (
        options.get("end_condition", "free") != "free"
    )


def check(sections, options):
    """Refuse conditions the end profiles cannot take (with the reason)."""
    for which, section in (("start", sections[0]), ("end", sections[-1])):
        condition = options.get(which + "_condition", "free")
        try:
            core.check(
                condition,
                kind_of(section),
                options.get(which + "_weight", core.DEFAULT_WEIGHT),
                options.get(which + "_angle", core.DEFAULT_ANGLE),
            )
        except EndError as exc:
            raise EndError("%s profile: %s" % ("First" if which == "start" else "Last", exc))


# -- the loft ----------------------------------------------------------------------------------
def thru(sections, index, options):
    """The solid lofted through wire `index` of every section (a point stays a point), its
    ends meeting the end conditions."""
    import Part

    items = []
    caps = []
    for s in sections:
        if s.point is not None:
            items.append(Part.Vertex(s.point))
            caps.append(None)
            continue
        wire = polynomial_wire(s.wires[index])
        items.append(wire)
        caps.append(wire)
    try:
        shell = Part.makeLoft(items, False, False, False)
    except Exception as exc:
        raise EndError(
            "The profiles cannot be lofted (%s). Check that they face the same way and do not "
            "cross each other." % (str(exc) or type(exc).__name__)
        )
    centers = [s.center for s in sections]
    params = core.chord_params([(c.x, c.y, c.z) for c in centers])
    ends = (
        _end_rule(sections, 0, options, "start"),
        _end_rule(sections, len(sections) - 1, options, "end"),
    )
    faces = [_rebuilt(face, sections, params, ends) for face in shell.Faces]
    for wire in (caps[0], caps[-1]):
        if wire is not None:
            faces.append(Part.Face(wire))
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


# -- one side face -------------------------------------------------------------------------------
def _bspline(face, sections):
    """The face's surface as a non-periodic B-spline cut to the face."""
    import Part

    surface = face.Surface
    if surface.TypeId == "Part::GeomPlane":
        return _ruled_plane(face, sections)
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


def _ruled_plane(face, sections):
    """A flat side between two straight edges (or an edge and a point: OpenCASCADE makes
    triangles when a polygon is lofted to a point) as a bilinear B-spline surface, from the
    edge on the first profile to the one (or the point) on the last."""
    import Part

    first, last = sections[0], sections[-1]
    refused = EndError("These end conditions cannot be built for these profiles.")
    if not all(_straight(e) for e in face.Edges):
        raise refused

    def on(edge, section):
        return all(_plane_distance(v.Point, section) < 1e-6 for v in edge.Vertexes)

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
    if section.point is not None:
        return (point - section.point).Length
    return abs((point - section.center).dot(section.normal))


def _iso_params(surface, sections):
    """The v of each section on the surface (first and last at the ends), and whether the
    surface runs from the last section to the first."""
    u0, u1, v0, v1 = surface.bounds()
    um = (u0 + u1) / 2.0
    first, last = sections[0], sections[-1]
    at_start = surface.value(um, v0)
    reverse = _plane_distance(at_start, last) < _plane_distance(at_start, first) - 1e-9
    order = list(reversed(sections)) if reverse else list(sections)
    values = [v0]
    for section in order[1:-1]:
        values.append(_find_v(surface, section, um, values[-1], v1))
    values.append(v1)
    return values, reverse


def _find_v(surface, section, um, lo, hi):
    """v in (lo, hi) where the surface's iso line u = um crosses the section's plane."""

    def f(v):
        return (surface.value(um, v) - section.center).dot(section.normal)

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
    raise EndError("internal: a profile is not on the loft's side surface")


def _rebuilt(face, sections, params, ends):
    """The side face again, its columns re-interpolated with the end conditions."""
    import Part

    surface = _bspline(face, sections)
    values, reverse = _iso_params(surface, sections)
    isos = [surface.vIso(v) for v in values]
    count = surface.NbUPoles
    rows = []
    weights = []
    for iso in isos:
        poles = iso.getPoles()
        w = iso.getWeights() if iso.isRational() else [1.0] * count
        weights.append(w)
        rows.append(poles)
    order = list(range(len(sections)))
    if reverse:
        order.reverse()
    # The data in loft order (first profile first), as the rules expect it.
    data = [rows[order.index(k)] for k in range(len(sections))]
    wdata = [weights[order.index(k)] for k in range(len(sections))]
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
def _end_rule(sections, k, options, which):
    """A function (data rows, weight rows) -> the interpolation's end condition."""
    condition = options.get(which + "_condition", "free")
    if condition == "free":
        return lambda data, wdata: ("free",)
    weight = float(options.get(which + "_weight", core.DEFAULT_WEIGHT))
    angle = float(options.get(which + "_angle", core.DEFAULT_ANGLE))
    section = sections[k]
    neighbour = sections[1] if which == "start" else sections[-2]
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
    wire = section.wires[0]
    points = [v.Point for v in wire.Vertexes] + wire.discretize(64)
    reach = max((p - section.center).Length for p in points) if points else 0.0
    if reach < 1e-9:
        raise EndError("The profile is too small for an end condition.")
    return reach


class _FaceGuide:
    """The faces of the part next to a picked face: which way they run away from its edges
    (into the part's side) and how they bend across them."""

    def __init__(self, section, toward):
        from . import curves

        obj, _sub = section.profile
        shape = curves.to_global(obj.Shape, obj)
        picked = section.face
        self.normal = _toward(section.normal, toward)  # out of the part, toward the loft
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
