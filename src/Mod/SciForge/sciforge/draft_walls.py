# SPDX-License-Identifier: LGPL-2.1-or-later
"""Draft of side walls that OpenCASCADE's draft cannot tilt, without GUI code (drafting.py
calls it for the faces FreeCAD's PartDesign::Draft refuses).

Fusion drafts any face that runs along the pull direction: flat, round, or free-form (the
side of an extruded spline or ellipse). OpenCASCADE's draft (BRepOffsetAPI_DraftAngle,
behind FreeCAD's Draft) only knows planes, and cylinders / cones whose axis is the pull
direction: every other face is skipped with "Failed to add some face for drafting".

A "wall" is a face whose normal is square to the pull direction everywhere: the side of a
shape extruded along the pull direction. Its cross-section C (the curve where it meets the
fixed plane) stays where it is; the drafted wall is the ruled surface W through C whose
rulings lean by the draft angle from the pull direction, toward the inside of the part on
the pull side (a positive angle makes the part narrower toward the pull direction, as
Fusion does). At the height h above the fixed plane, W lies h * tan(angle) inside the old
wall: on a straight wall W is a plane, on a round one a cone, otherwise a ruled B-spline.

How the solid is changed: the thin slab next to the wall (the wall thickened inward and
outward, as far as its edges go) is split by W. Material inside the wall but outside W is
taken away, room outside the wall but inside W is filled. The slab's top and bottom follow
the wall's own edges, so caps square to the pull direction (the usual top and bottom faces)
end exactly on W. Where the wall ends at a face that is not drafted with it, the slab goes
on past the end and the filling stops at that face, so the face meets W like Fusion's.

Walls that touch each other are drafted together in one cut and one fuse: tangent chains of
flat, round and free-form walls stay tangent.
"""

import math

WALL_TOL = 1e-5  # |normal . pull| below this everywhere: the face runs along the pull
TOL = 1e-7


def _err(message):
    from .drafting import DraftError

    return DraftError(message)


def _unit(vector):
    v = vector.__class__(vector)
    if v.Length > 1e-12:
        v.normalize()
    return v


# -- which faces ------------------------------------------------------------------------------
def kind(face):
    return face.Surface.__class__.__name__


def native_ok(face, pull, parallel=1.0 - 1e-6):
    """True when OpenCASCADE's draft can tilt the face (FreeCAD's Draft does it)."""
    name = kind(face)
    if name == "Plane":
        u, v = face.Surface.parameter(face.CenterOfMass)
        return abs(_unit(face.normalAt(u, v)).dot(pull)) < parallel
    if name in ("Cylinder", "Cone"):
        return abs(_unit(face.Surface.Axis).dot(pull)) >= parallel
    return False


def is_wall(face, pull):
    """True when the face runs along the pull direction (its normal square to it everywhere)."""
    try:
        u0, u1, v0, v1 = face.ParameterRange
    except Exception:
        return False
    seen = 0
    for i in range(5):
        for j in range(5):
            u = u0 + (u1 - u0) * (0.05 + 0.225 * i)
            v = v0 + (v1 - v0) * (0.05 + 0.225 * j)
            try:
                normal = face.normalAt(u, v)
            except Exception:
                continue  # a degenerate point of the surface
            if normal.Length < 1e-12:
                continue
            if abs(_unit(normal).dot(pull)) > WALL_TOL:
                return False
            seen += 1
    return seen >= 5


def _adjacent(face_a, face_b):
    for edge in face_a.Edges:
        for other in face_b.Edges:
            if edge.isSame(other):
                return True
    return False


# A live preview rebuilds the draft many times on the same shape (only the angle changes):
# what does not depend on the angle (which faces are walls, their cross-sections, ends and
# neighbours) is worked out once and kept here, keyed by drafting.shape_key.
_CACHE = {}
_CACHE_SIZE = 256


def _cached(key, make):
    if key not in _CACHE:
        if len(_CACHE) >= _CACHE_SIZE:
            _CACHE.clear()
        _CACHE[key] = make()
    return _CACHE[key]


def _vec_key(v):
    return (round(v.x, 9), round(v.y, 9), round(v.z, 9))


def engine_names(shape, names, pull):
    """The faces of `names` this module drafts: the walls OpenCASCADE cannot tilt, and the
    walls joined to them through other picked walls (a tangent chain of flat, round and
    spline walls is drafted as one, so it stays tangent)."""
    from .drafting import shape_key

    key = ("engine", shape_key(shape), tuple(names), _vec_key(pull))
    return list(_cached(key, lambda: (_engine_names(shape, names, pull), shape))[0])


def _engine_names(shape, names, pull):
    faces = {}
    for name in names:
        try:
            faces[name] = shape.getElement(name)
        except Exception:
            continue
    walls = [n for n, f in faces.items() if is_wall(f, pull)]
    group = [n for n in walls if not native_ok(faces[n], pull)]
    todo = list(group)
    while todo:
        name = todo.pop()
        for other in walls:
            if other not in group and _adjacent(faces[name], faces[other]):
                group.append(other)
                todo.append(other)
    return [n for n in names if n in group]


# -- the cross-section of one wall ----------------------------------------------------------
def _heights(face, pull, origin):
    values = []
    for edge in face.Edges:
        try:
            points = edge.discretize(24)
        except Exception:
            points = [v.Point for v in edge.Vertexes]
        values += [(p - origin).dot(pull) for p in points]
    return min(values), max(values)


def _big_plane(point, normal, size):
    import Part

    plane = Part.Plane(point, normal)
    return plane.toShape(-size, size, -size, size)


class _Wall:
    """One wall: its cross-section on the fixed plane and what the draft does to it."""

    def __init__(self, shape, name, origin, pull, tan_a, size):
        self.name = name
        self.face = shape.getElement(name)
        self.origin = origin
        self.pull = pull
        self.tan_a = tan_a
        self.size = size
        self.hmin, self.hmax = _heights(self.face, pull, origin)
        if self.hmax - self.hmin < 1e-6:
            raise _err("%s has no height along the pull direction." % name)
        # the cross-section: the face's surface (untrimmed) cut at mid height, moved to the plane
        hmid = 0.5 * (self.hmin + self.hmax)
        surface = self.face.Surface
        curve = self._extruded_curve(surface)
        if curve is None:
            curve = self._section_curve(surface, hmid)
        self.curve = curve  # Part.Edge on the fixed plane
        self.closed = curve.isClosed()
        self.u0, self.u1 = curve.FirstParameter, curve.LastParameter
        # which way is out of the part
        um = 0.5 * (self.u0 + self.u1)
        point = curve.valueAt(um) + pull * hmid
        u, v = surface.parameter(point)
        out = _unit(self.face.normalAt(u, v))
        self.sign = 1.0 if self._side(um).dot(out) >= 0 else -1.0
        self.kind = self._geometry_kind()
        self._radii()
        self._ends(shape)

    def _extruded_curve(self, surface):
        """The side of an extrusion along the pull: its own profile curve, exact, moved onto
        the fixed plane (a section of the surface would be an approximation)."""
        if kind(self.face) != "SurfaceOfExtrusion":
            return None
        try:
            if abs(_unit(surface.Direction).dot(self.pull)) < 1.0 - 1e-9:
                return None
            u0, u1 = self.face.ParameterRange[:2]
            edge = surface.BasisCurve.toShape(u0, u1)
        except Exception:
            return None
        start = edge.valueAt(edge.FirstParameter)
        edge.translate(self.pull * (-(start - self.origin).dot(self.pull)))
        return edge

    def _section_curve(self, surface, hmid):
        """The face's surface (untrimmed) cut at mid height, moved onto the fixed plane; one
        smooth curve (planes and round faces give exact lines and circles)."""
        import Part

        patch = surface.toShape(*self.face.ParameterRange)
        cut = patch.section(_big_plane(self.origin + self.pull * hmid, self.pull, self.size))
        edges = [e for e in cut.Edges if e.Length > 1e-7]
        if not edges:
            raise _err("The cross-section of %s could not be found." % self.name)
        if len(edges) > 1 or (
            edges[0].Curve.__class__.__name__ == "BSplineCurve"
            and edges[0].Curve.Continuity == "C0"
        ):
            try:
                edges = Part.__sortEdges__(edges)
                wire = Part.Wire(edges)
                count = max(64, min(400, int(wire.Length / 0.05)))
                points = wire.discretize(count)
                curve = Part.BSplineCurve()
                closed = wire.isClosed()
                if closed:
                    points = points[:-1]
                    curve.interpolate(points, PeriodicFlag=True)
                else:
                    curve.approximate(points, DegMin=3, DegMax=8, Tolerance=1e-6, Continuity="C2")
                edges = [curve.toShape()]
            except Exception:
                raise _err("The cross-section of %s could not be made smooth." % self.name)
        edge = edges[0].copy()
        start = edge.valueAt(edge.FirstParameter)
        edge.translate(self.pull * (-(start - self.origin).dot(self.pull)))
        return edge

    # 2D helpers (vectors in 3D, square to the pull direction)
    def _side(self, u):
        return _unit(self.pull.cross(self.curve.tangentAt(u)))

    def normal(self, u):
        """Out of the part, square to the pull direction, at the cross-section's u."""
        return self._side(u) * self.sign

    def _geometry_kind(self):
        name = self.curve.Curve.__class__.__name__
        if name in ("Line", "LineSegment"):
            return "line"
        if name in ("Circle", "ArcOfCircle"):
            return "circle"
        return "curve"

    def shift(self, h):
        """How far the drafted wall lies out of the old one at height h (negative: in)."""
        return -h * self.tan_a

    def _radii(self):
        """The tightest bend of the cross-section with its centre inside / outside the part:
        offsetting further than that toward the centre folds the curve over."""
        self.r_in = self.r_out = float("inf")
        if self.kind == "line":
            return
        count = 48
        for i in range(count + 1):
            u = self.u0 + (self.u1 - self.u0) * i / count
            try:
                k = self.curve.curvatureAt(u)
            except Exception:
                continue
            if k < 1e-9:
                continue
            try:
                center = self.curve.centerOfCurvatureAt(u)
            except Exception:
                continue
            side = (center - self.curve.valueAt(u)).dot(self.normal(u))
            if side < 0:
                self.r_in = min(self.r_in, 1.0 / k)
            else:
                self.r_out = min(self.r_out, 1.0 / k)

    def _ends(self, shape):
        """For an open wall: per end (u, outward tangent, the face there or None when that face
        is drafted with it is decided later)."""
        self.end_info = []
        if self.closed:
            return
        for u, direction in ((self.u0, -1.0), (self.u1, 1.0)):
            point = self.curve.valueAt(u)
            tangent = _unit(self.curve.tangentAt(u)) * direction
            neighbours, lo, hi = [], None, None
            for edge in self.face.Edges:
                pts = edge.discretize(5)
                flat = [p - self.pull * (p - self.origin).dot(self.pull) for p in pts]
                if all((q - point).Length < 1e-5 for q in flat):
                    hs = [(p - self.origin).dot(self.pull) for p in pts]
                    lo = min(hs) if lo is None else min(lo, min(hs))
                    hi = max(hs) if hi is None else max(hi, max(hs))
                    for i, other in enumerate(shape.Faces, start=1):
                        if other.isSame(self.face):
                            continue
                        if any(e.isSame(edge) for e in other.Edges):
                            neighbours.append("Face%d" % i)
            self.end_info.append(
                {
                    "u": u,
                    "point": point,
                    "tangent": tangent,
                    "faces": neighbours,
                    "lo": lo,
                    "hi": hi,
                }
            )

    def side_of(self, point):
        """(t, h) of a point: t its distance out of the wall's (extended) cross-section, h its
        height above the fixed plane."""
        import Part

        h = (point - self.origin).dot(self.pull)
        q = point - self.pull * h
        if self.kind == "line":
            base = self.curve.valueAt(self.u0)
            return (q - base).dot(self.normal(self.u0)), h
        if self.kind == "circle":
            circle = self.curve.Curve
            center = circle.Center
            center = center - self.pull * (center - self.origin).dot(self.pull)
            radial = (q - center).Length - circle.Radius
            outward = (self.curve.valueAt(self.u0) - center).dot(self.normal(self.u0)) > 0
            return (radial if outward else -radial), h
        vertex = Part.Vertex(q)
        _dist, pairs, info = self.curve.distToShape(vertex)
        u = info[0][2] if info and info[0][0] == "Edge" else self.curve.Curve.parameter(pairs[0][0])
        u = min(max(u, self.u0), self.u1)
        if not self.closed:
            for end in self.end_info:
                if abs(u - end["u"]) < 1e-9 * max(1.0, abs(self.u1 - self.u0)):
                    if (q - end["point"]).dot(end["tangent"]) > 0:
                        return self.end_side(end, point)
        base = self.curve.valueAt(u)
        return (q - base).dot(self.normal(u)), h

    def end_side(self, end, point):
        """(t, h) of a point past an end, the wall going on along its tangent there."""
        h = (point - self.origin).dot(self.pull)
        q = point - self.pull * h
        return (q - end["point"]).dot(self.normal(end["u"])), h

    def inside_drafted(self, point, end=None):
        """True when the point is on the part's side of the drafted wall (past `end`: of the
        wall going on along its tangent there)."""
        t, h = self.side_of(point) if end is None else self.end_side(end, point)
        return t < self.shift(h)

    def end_tool(self, end, reach, length):
        """The drafted wall going on along its tangent past `end` (a splitting tool)."""
        return self._strip(end, self.hmin - reach, self.hmax + reach, length, -0.25 * length)

    # -- the drafted surface (a splitting tool, larger than the slab) --------------------------
    def drafted_surface(self, reach):
        import Part

        lo = self.hmin - reach
        hi = self.hmax + reach
        if self.kind == "line":
            p = self.curve.valueAt(self.u0)
            t = _unit(self.curve.tangentAt(self.u0))
            n = self.normal(self.u0)
            lean = _unit(self.pull - n * self.tan_a)  # going up, inward by tan(angle)
            normal = _unit(t.cross(lean))
            plane = Part.Plane(p, normal)
            u, v = plane.parameter(p)
            s = self.size
            return plane.toShape(u - s, u + s, v - s, v + s)
        if self.kind == "circle":
            circle = self.curve.Curve
            center = circle.Center - self.pull * (circle.Center - self.origin).dot(self.pull)
            outward = (self.curve.valueAt(self.u0) - center).dot(self.normal(self.u0)) > 0
            sgn = 1.0 if outward else -1.0
            r_lo = circle.Radius + sgn * self.shift(lo)
            r_hi = circle.Radius + sgn * self.shift(hi)
            if r_lo <= TOL or r_hi <= TOL:
                raise _err(
                    "%s is too small for this angle: the drafted wall would close up. Try a "
                    "smaller angle." % self.name
                )
            base = center + self.pull * lo
            if abs(r_lo - r_hi) < 1e-9:
                solid = Part.makeCylinder(r_lo, hi - lo, base, self.pull)
            else:
                solid = Part.makeCone(r_lo, r_hi, hi - lo, base, self.pull)
            return [f for f in solid.Faces if kind(f) != "Plane"][0]
        # any other curve: a ruled surface between the cross-section offset at both heights,
        # with flat strips along the tangents past an open curve's ends
        ruled = self._ruled(self.curve, lo, hi)
        faces = list(ruled.Faces)
        if not self.closed:
            for end in self.end_info:
                faces.append(self._strip(end, lo, hi, reach * 2.0 + self.size * 0.25))
        return Part.makeCompound(faces)

    def _offset_edge(self, d, h):
        import Part

        if abs(d) < 1e-12:
            edge = self.curve.copy()
        elif self.kind == "line":
            edge = self.curve.copy()
            edge.translate(self.normal(self.u0) * d)
        elif self.kind == "circle":
            # a concentric circle with the same frame: same parameters, exact
            circle = self.curve.Curve.copy()
            center = circle.Center
            outward = (self.curve.valueAt(self.u0) - center).dot(self.normal(self.u0)) > 0
            radius = circle.Radius + (d if outward else -d)
            if radius <= TOL:
                raise _err("%s is too small for this angle. Try a smaller angle." % self.name)
            circle.Radius = radius
            edge = circle.toShape(self.u0, self.u1)
        else:
            probe = Part.OffsetCurve(self.curve.Curve, 1.0, self.pull)
            um = 0.5 * (self.u0 + self.u1)
            k = 1.0 if (probe.value(um) - self.curve.valueAt(um)).dot(self.normal(um)) > 0 else -1.0
            offset = Part.OffsetCurve(self.curve.Curve, k * d, self.pull)
            # an offset-curve edge makes OpenCASCADE's split / booleans go wrong: a B-spline
            # (same parameters, so the ruled surface stays exact along its rulings)
            edge = offset.toBSpline(self.u0, self.u1).toShape()
        start = edge.valueAt(edge.FirstParameter)
        edge.translate(self.pull * (h - (start - self.origin).dot(self.pull)))
        return edge

    def _ruled(self, curve, lo, hi):
        """Ruled between offset rows; the row on the fixed plane is the cross-section itself
        (exact), so the surface goes exactly through the hinge (a wall drafted about its own
        bottom edge: a near miss there makes OpenCASCADE's split do nothing)."""
        import Part

        faces = [face for _a, _b, face in self._ruled_bands(lo, hi)]
        return faces[0] if len(faces) == 1 else Part.makeCompound(faces)

    def _ruled_bands(self, lo, hi):
        """[(bottom height, top height, ruled face)] of the drafted surface from lo to hi,
        made once per wall and height range: the wedges cut their drafted face out of these
        same surfaces, so FreeCAD's Refine merges it with the pieces the corners leave (it
        merges B-spline faces only when their definitions are identical)."""
        import Part

        cache = self.__dict__.setdefault("_bands", {})
        key = (round(lo, 9), round(hi, 9), round(self.tan_a, 12))
        if key not in cache:
            on_edge = min(abs(self.hmin), abs(self.hmax)) < 1e-6
            heights = [lo, 0.0, hi] if on_edge and lo < -1e-9 and hi > 1e-9 else [lo, hi]
            rows = [self._offset_edge(self.shift(h), h) for h in heights]
            bands = []
            for (ha, bottom), (hb, top) in zip(zip(heights, rows), zip(heights[1:], rows[1:])):
                face = Part.makeRuledSurface(bottom, top)
                if face.isNull() or face.Area < TOL:
                    raise _err("The drafted surface of %s could not be made." % self.name)
                bands.append((ha, hb, face))
            cache[key] = bands
        return cache[key]

    def _strip(self, end, lo, hi, length, start=0.0):
        import Part

        n = self.normal(end["u"])
        p, t = end["point"], end["tangent"]
        corners = []
        for h in (lo, hi):
            base = p + n * self.shift(h) + self.pull * h
            corners.append(base + t * start)
            corners.append(base + t * length)
        a, b, c, d = corners[0], corners[1], corners[3], corners[2]
        return Part.Face(Part.makePolygon([a, b, c, d, a]))

    # -- the slab ---------------------------------------------------------------------------------
    def rectangular(self):
        """True when the wall is a plain band: cut square at a top and a bottom height (the
        usual extruded side), no holes. Its slab can be a prism with flat ends, which merge
        with the part's flat top and bottom (an offset face's ends are flat B-splines)."""
        if len(self.face.Wires) != 1:
            return False
        for edge in self.face.Edges:
            points = edge.discretize(9)
            hs = [(p - self.origin).dot(self.pull) for p in points]
            if all(abs(h - self.hmin) < 1e-6 for h in hs) or all(
                abs(h - self.hmax) < 1e-6 for h in hs
            ):
                continue  # the top or bottom edge
            flat = [p - self.pull * h for p, h in zip(points, hs)]
            if all((q - flat[0]).Length < 1e-6 for q in flat):
                continue  # an upright edge (an end, or a seam)
            return False
        return True

    def _prism_slab(self, outward, depth):
        import Part

        if not self.rectangular():
            return None
        try:
            off = self._offset_edge(depth if outward else -depth, 0.0)
            if self.closed:
                face = Part.makeFace(
                    [Part.Wire([self.curve.copy()]), Part.Wire([off])], "Part::FaceMakerBullseye"
                )
            else:
                a0, a1 = self.curve.Vertexes[0].Point, self.curve.Vertexes[-1].Point
                b0, b1 = off.Vertexes[0].Point, off.Vertexes[-1].Point
                if (a0 - b0).Length + (a1 - b1).Length > (a0 - b1).Length + (a1 - b0).Length:
                    b0, b1 = b1, b0
                edges = [self.curve.copy(), off]
                for a, b in ((a0, b0), (a1, b1)):
                    edges.append(Part.LineSegment(a, b).toShape())
                face = Part.Face(Part.Wire(Part.__sortEdges__(edges)))
            if face.isNull() or face.Area < TOL:
                return None
            face.translate(self.pull * self.hmin)
            solid = _prism(face, self.pull, self.hmax - self.hmin)
            if solid.isNull() or not solid.isValid() or solid.Volume < TOL:
                return None
            return solid
        except Exception:
            return None

    def slab(self, outward, depth):
        """The wall thickened `depth` out of (outward) or into the part, as far as its edges
        go."""
        thick = self._prism_slab(outward, depth)
        if thick is not None:
            return thick
        offset = depth if outward else -depth
        thick = self.face.makeOffsetShape(offset, TOL, fill=True)
        if thick.isNull() or not thick.Solids:
            raise _err("%s could not be thickened (offset %.3g)." % (self.name, depth))
        thick = thick.Solids[0]
        # makeOffsetShape follows the face's own orientation: check the side
        um = 0.5 * (self.u0 + self.u1)
        hmid = 0.5 * (self.hmin + self.hmax)
        probe = (
            self.curve.valueAt(um)
            + self.pull * hmid
            + self.normal(um) * (0.5 * depth if outward else -0.5 * depth)
        )
        if not thick.isInside(probe, 1e-9, True):
            thick = self.face.makeOffsetShape(-offset, TOL, fill=True).Solids[0]
        return thick

    # -- the wedges, built directly (the fast way) ----------------------------------------------
    # The material a draft takes away (or adds) next to a plain band of a wall is a wedge:
    # between the old wall and the drafted one, from the band's bottom to its top. Built from
    # its faces it costs a few milliseconds; splitting a slab with the drafted surface (slab()
    # and _pieces(), still used for other walls and at corners) cost ~60 ms a wall, most of a
    # live preview's time.
    def wedges(self, outward):
        """The wedge(s) of material to add (outward) or take away, as solids, or None when
        the wall is no plain band (then slab() and _pieces() do it)."""
        if not self.rectangular() or abs(self.tan_a) < 1e-12:
            return None
        lo, hi = self.hmin, self.hmax
        # where the drafted wall lies out of the old one (shift > 0) or in it (shift < 0)
        spans = [(max(lo, 0.0), hi), (lo, min(hi, 0.0))]
        found = []
        for ha, hb in spans:
            if hb - ha < 1e-9:
                continue
            mid = 0.5 * (ha + hb)
            if (self.shift(mid) > 0) != outward:
                continue
            solid = self._wedge(ha, hb)
            if solid is None:
                return None
            found.append(solid)
        return found

    def _wedge(self, ha, hb):
        import Part

        try:
            da, db = self.shift(ha), self.shift(hb)
            base_a = self._offset_edge(0.0, ha)
            base_b = self._offset_edge(0.0, hb)
            rows = {
                ha: (base_a, self._offset_edge(da, ha), da),
                hb: (base_b, self._offset_edge(db, hb), db),
            }
            faces = [base_a.extrude(self.pull * (hb - ha)), self._drafted_band(ha, hb, rows)]
            for h in (ha, hb):
                old, new, d = rows[h]
                if abs(d) < 1e-9:
                    continue  # on the fixed plane: the wedge ends in an edge there
                faces.append(self._cap(old, new))
            if not self.closed:
                for end in self.end_info:
                    n = self.normal(end["u"])
                    p = end["point"]
                    ring = [p + self.pull * ha, p + self.pull * hb]
                    if abs(db) > 1e-9:
                        ring.append(p + n * db + self.pull * hb)
                    if abs(da) > 1e-9:
                        ring.append(p + n * da + self.pull * ha)
                    faces.append(Part.Face(Part.makePolygon(ring + [ring[0]])))
            shape = Part.makeCompound(faces)
            shape.sewShape()
            if len(shape.Shells) != 1:
                return None
            solid = Part.Solid(shape.Shells[0])
            if solid.Volume < 0:
                solid.reverse()
            if not solid.isValid() or solid.Volume < 1e-12:
                return None
            return solid
        except Exception:
            return None

    def _drafted_band(self, ha, hb, rows):
        """The drafted wall between heights ha and hb: a plane, a cone (exact) or a ruled
        B-spline between the offset rows."""
        import Part

        a, b = rows[ha][1], rows[hb][1]
        if self.kind == "line":
            pts = [a.Vertexes[0].Point, a.Vertexes[-1].Point]
            pts += [b.Vertexes[-1].Point, b.Vertexes[0].Point]
            if (pts[0] - pts[3]).Length > (pts[0] - pts[2]).Length:
                pts[2], pts[3] = pts[3], pts[2]
            return Part.Face(Part.makePolygon(pts + [pts[0]]))
        if self.kind == "circle":
            # the line from row to row at the arc's start, turned round the axis: a cone
            circle = self.curve.Curve
            center = circle.Center - self.pull * (circle.Center - self.origin).dot(self.pull)
            p, n = self.curve.valueAt(self.u0), self.normal(self.u0)
            p = p - self.pull * (p - self.origin).dot(self.pull)
            da, db = rows[ha][2], rows[hb][2]
            line = Part.LineSegment(p + n * da + self.pull * ha, p + n * db + self.pull * hb)
            angle = math.degrees(self.u1 - self.u0)
            return line.toShape().revolve(center, circle.Axis, angle).Faces[0]
        reach = getattr(self, "reach", None)
        if reach is not None:
            # trimmed from the drafted surface itself (see _ruled_bands)
            for h0, h1, face in self._ruled_bands(self.hmin - reach, self.hmax + reach):
                if h0 - 1e-9 <= ha and hb <= h1 + 1e-9:
                    surface = face.Surface
                    u0, u1, v0, v1 = face.ParameterRange
                    um = 0.5 * (u0 + u1)
                    z0 = (surface.value(um, v0) - self.origin).dot(self.pull)
                    z1 = (surface.value(um, v1) - self.origin).dot(self.pull)
                    if abs(z1 - z0) < 1e-12:
                        break

                    def v_at(h):
                        return v0 + (v1 - v0) * (h - z0) / (z1 - z0)

                    va, vb = sorted((v_at(ha), v_at(hb)))
                    return surface.toShape(u0, u1, va, vb)
        return Part.makeRuledSurface(a, b)

    def _cap(self, old, new):
        """The flat face between the old and the drafted wall at one height."""
        import Part

        if self.closed:
            return Part.makeFace([Part.Wire([old]), Part.Wire([new])], "Part::FaceMakerBullseye")
        a0, a1 = old.Vertexes[0].Point, old.Vertexes[-1].Point
        b0, b1 = new.Vertexes[0].Point, new.Vertexes[-1].Point
        if (a0 - b0).Length + (a1 - b1).Length > (a0 - b1).Length + (a1 - b0).Length:
            b0, b1 = b1, b0
        edges = [old, new, Part.LineSegment(a0, b0).toShape(), Part.LineSegment(a1, b1).toShape()]
        return Part.Face(Part.Wire(Part.__sortEdges__(edges)))

    def end_box(self, end, outward, depth):
        """Past an end of the wall: the slab going on along the tangent for a while (the
        corner with the next face is finished there), or None."""
        import Part

        if end["lo"] is None or end["hi"] - end["lo"] < 1e-9:
            return None
        n = self.normal(end["u"])
        p, t = end["point"], end["tangent"]
        length = END_LENGTH * depth + 0.5
        t0, t1 = (0.0, depth) if outward else (-depth, 0.0)
        ring = [
            p + n * t0 + self.pull * end["lo"],
            p + n * t1 + self.pull * end["lo"],
            p + n * t1 + t * length + self.pull * end["lo"],
            p + n * t0 + t * length + self.pull * end["lo"],
        ]
        face = Part.Face(Part.makePolygon(ring + [ring[0]]))
        return _prism(face, self.pull, end["hi"] - end["lo"])

    def end_zone(self, end, depth, margin):
        """Around an end of the wall: from END_LENGTH slab depths back along it to past its
        end box, as deep as the slabs on both sides (where the corner rule applies), `margin`
        above and below the wall (less than any drafted surface goes past it: a zone as tall
        as the other wall's surface is not split by it)."""
        import Part

        n = self.normal(end["u"])
        p, t = end["point"], end["tangent"]
        length = END_LENGTH * depth + 0.5
        back, ahead, deep = length, 1.5 * length, 2.0 * depth + 0.5
        lo = self.hmin - margin
        ring = [
            p - t * back - n * deep + self.pull * lo,
            p + t * ahead - n * deep + self.pull * lo,
            p + t * ahead + n * deep + self.pull * lo,
            p - t * back + n * deep + self.pull * lo,
        ]
        face = Part.Face(Part.makePolygon(ring + [ring[0]]))
        return _prism(face, self.pull, self.hmax - self.hmin + 2.0 * margin)


END_LENGTH = 6.0  # how far past a wall's end its corner is finished, in slab depths


# -- the draft --------------------------------------------------------------------------------
def _wall(shape, name, origin, pull, tan_a, size):
    """A _Wall, its angle-free part made once per shape (see _CACHE)."""
    from .drafting import shape_key

    key = ("wall", shape_key(shape), name, _vec_key(origin), _vec_key(pull), round(size, 6))
    wall = _cached(key, lambda: _Wall(shape, name, origin, pull, tan_a, size))
    if wall.tan_a != tan_a:
        wall.tan_a = tan_a
        wall.__dict__.pop("_bands", None)  # the drafted surfaces of the old angle
    wall.__dict__.pop("reach", None)
    return wall


def _prism(face, pull, height):
    """`face` (square to `pull`) extruded by `height` along `pull`. Extruded against its own
    normal, OpenCASCADE's prism comes out inside-out (splits and booleans then go wrong)."""
    u, v = face.Surface.parameter(face.Vertexes[0].Point)
    if face.normalAt(u, v).dot(pull) < 0:
        face = face.copy()
        face.reverse()
    return face.extrude(pull * height)


def _piece_point(solid):
    """A point well inside a solid (thin wedges: their middle can lie outside them)."""
    from .drafting import _inner_point

    center = solid.CenterOfMass
    if solid.isInside(center, 1e-9, False):
        return center
    for face in sorted(solid.Faces, key=lambda f: -f.Area):
        try:
            point = _inner_point(face)
            u, v = face.Surface.parameter(point)
            normal = _unit(face.normalAt(u, v))
        except Exception:
            continue
        for eps in (1e-2, 1e-3, 1e-4, 1e-5):
            probe = point - normal * eps
            if solid.isInside(probe, 1e-9, False):
                return probe
    return center


def _reach(wall, go_in, go_out):
    """How far the drafted surface goes past the wall's height: past the slab, but never so
    far that it bends round further than the cross-section's tightest radius (it would fold)."""
    height = wall.hmax - wall.hmin
    reach = max(0.5, 0.1 * height)
    t = abs(wall.tan_a)
    if t > 1e-12:
        for radius, gone in ((wall.r_in, go_in), (wall.r_out, go_out)):
            if radius < float("inf"):
                reach = min(reach, max(1e-3, 0.5 * (radius - gone) / t))
    return reach


def _pieces(slab, tool):
    """`slab` split by the faces of `tool`. The faces go in as separate arguments: the faces
    of one compound argument are not joined to each other, and the seam between a drafted
    wall and its tangent strip then leaves a gap the split leaks through."""
    try:
        result, _map = slab.generalFuse(list(tool.Faces), 1e-6)
    except Exception as exc:
        raise _err("The drafted wall could not be cut into the part: %s" % exc)
    solids = [s for s in result.Solids if s.Volume > 1e-12]
    return solids or [slab]


def _inner_region(shape, name, size):
    """The material side of face `name` of `shape`, its surface extended."""
    from . import presspull_core as pp
    from . import replace_face

    face = shape.getElement(name)
    from .drafting import _inner_point

    point = _inner_point(face)
    normal = pp.face_normal(face)
    surface = replace_face.target_surface(face, shape, size)
    return replace_face._inner_region(
        surface, kind(face), point - normal * 1e-3, size, shape, normal
    )


def _convex(shape, wall, end):
    """True when the part turns away at this end of the wall (an outside corner, or a wall
    that goes on bending inward): just past the end along the tangent is outside the part."""
    if end["lo"] is None:
        return True
    step = max(0.05, min(1.0, 0.1 * wall.curve.Length))
    h = 0.5 * (end["lo"] + end["hi"])
    probe = end["point"] + end["tangent"] * step + wall.pull * h
    return not shape.isInside(probe, 1e-6, False)


class _Side:
    """One side of a surface, to trim the pieces past a wall's end: the drafted or the old
    surface of a wall drafted with it (its own splitting tool, so the faces it leaves merge
    with the wall's), or the extended surface of a face that is not drafted."""

    def __init__(self, inside, wall=None, tool=None, region=None):
        self.inside = inside
        self.wall = wall
        self.tool = tool
        self.region = region

    def trim(self, pieces):
        out = []
        for piece in pieces:
            if self.wall is None:
                try:
                    kept = piece.common(self.region) if self.inside else piece.cut(self.region)
                except Exception:
                    kept = piece
                out += [s for s in kept.Solids if s.Volume > 1e-12]
                continue
            for part in _pieces(piece, self.tool):
                if self.wall.inside_drafted(_piece_point(part)) == self.inside:
                    out.append(part)
        return out

    def beyond(self, zone):
        """The part of `zone` on the wrong side (what trim() would take away there)."""
        if self.wall is None:
            try:
                return zone.cut(self.region) if self.inside else zone.common(self.region)
            except Exception:
                return None
        parts = [
            p
            for p in _pieces(zone, self.tool)
            if self.wall.inside_drafted(_piece_point(p)) != self.inside
        ]
        if not parts:
            return None
        return parts[0] if len(parts) == 1 else parts[0].multiFuse(parts[1:])


def _tangent(shape, wall, end, other):
    """True when face `other` goes on smoothly from this end of the wall."""
    if end["lo"] is None:
        return False
    try:
        face = shape.getElement(other)
        h = 0.5 * (end["lo"] + end["hi"])
        point = end["point"] + wall.pull * h
        u, v = face.Surface.parameter(point)
        return _unit(face.normalAt(u, v)).dot(wall.normal(end["u"])) > 1.0 - 1e-6
    except Exception:
        return False


def _depth(go, radius):
    """The slab's depth: past the furthest the drafted wall goes, short of folding over."""
    return go + min(0.5 * (radius - go), 0.5 * go + 0.05)


def draft(shape, names, hinge, pull, angle):
    """`shape` with the walls `names` drafted by `angle` degrees about the hinge plane
    (point, normal), pulled along `pull`. Raises DraftError with the reason.

    Past each end of a wall, the corner with the next face N is finished from the wall's
    side (each region is taken by one wall, whatever N is):
      outside corner  material to add stops at N as drafted (filled up to where the two
                      drafted surfaces meet); material to take away needs no trim
      inside corner   material to take away stops at N as drafted, material to add at N
                      as it was
    N "as drafted" is N itself when it is not drafted with the wall."""
    import copy

    import Part

    pull = _unit(pull)
    origin, normal = hinge
    if abs(_unit(normal).dot(pull)) < 1.0 - 1e-6:
        raise _err(
            "These faces can only turn about a plane square to the pull direction. Pick a "
            "fixed plane across the pull direction."
        )
    tan_a = math.tan(math.radians(float(angle)))
    size = max(shape.BoundBox.DiagonalLength, 1.0) * 3.0 + 50.0
    walls = {}
    for name in names:
        face = shape.getElement(name)
        if not is_wall(face, pull):
            raise _err("%s does not run along the pull direction." % name)
        walls[name] = _wall(shape, name, origin, pull, tan_a, size)
    reach, go = {}, {}
    for name, wall in walls.items():
        shifts = [wall.shift(wall.hmin), wall.shift(wall.hmax)]
        go_in, go_out = max(0.0, -min(shifts)), max(0.0, max(shifts))
        if go_in >= wall.r_in * (1.0 - 1e-6) or go_out >= wall.r_out * (1.0 - 1e-6):
            raise _err(
                "%s bends too tightly for this angle over its height: the drafted wall would "
                "fold over. Try a smaller angle." % name
            )
        go[name] = (go_in, go_out)
        reach[name] = wall.reach = _reach(wall, go_in, go_out)

    tools, olds, regions = {}, {}, {}

    def tool_of(name):
        if name not in tools:
            tools[name] = walls[name].drafted_surface(reach[name])
        return tools[name]

    def old_of(name):
        if name not in olds:
            flat = copy.copy(walls[name])
            flat.tan_a = 0.0
            olds[name] = (flat, flat.drafted_surface(reach[name]))
        return olds[name]

    def region_of(name):
        if name not in regions:
            from .drafting import shape_key

            key = ("region", shape_key(shape), name, round(size, 6))
            regions[name] = _cached(key, lambda: (_inner_region(shape, name, size), shape))[0]
        return regions[name]

    cuts, adds = [], []
    for name, wall in walls.items():
        go_in, go_out = go[name]
        length = END_LENGTH * max(_depth(go_in, wall.r_in), _depth(go_out, wall.r_out)) + 0.5
        for outward, gone, radius in ((False, go_in, wall.r_in), (True, go_out, wall.r_out)):
            if gone <= 0:
                continue
            depth = _depth(gone, radius)
            pieces = wall.wedges(outward)
            if pieces is None:  # no plain band: split the slab with the drafted surface
                pieces = [
                    p
                    for p in _pieces(wall.slab(outward, depth), tool_of(name))
                    if wall.inside_drafted(_piece_point(p)) == outward
                ]
            for end in wall.end_info:
                others = end["faces"]
                if any(o in walls and _tangent(shape, wall, end, o) for o in others):
                    continue  # goes on smoothly into a wall drafted with it: nothing to finish
                box = wall.end_box(end, outward, depth)
                if box is None:
                    continue
                end_tool = wall.end_tool(end, reach[name], 1.5 * length)
                pieces += [
                    p
                    for p in _pieces(box, end_tool)
                    if wall.inside_drafted(_piece_point(p), end) == outward
                ]
                convex = _convex(shape, wall, end)
                if convex and not outward:
                    continue  # taken out of the part only where there is part: no trim
                trimmers = []
                for other in others:
                    if other in walls:
                        if convex or not outward:  # the other wall as drafted
                            trimmers.append(_Side(convex, wall=walls[other], tool=tool_of(other)))
                        else:  # inside corner, material to add: the other wall as it was
                            flat, flat_tool = old_of(other)
                            trimmers.append(_Side(False, wall=flat, tool=flat_tool))
                    else:
                        trimmers.append(_Side(convex, region=region_of(other)))
                # the rule holds near the end only (an extended surface may cross the wall
                # again further on): take away what lies beyond the other face in the end's
                # zone (cutting just that keeps the drafted wall in one face)
                zone = wall.end_zone(end, depth, 0.25 * min(reach.values()))
                for trimmer in trimmers:
                    gone = trimmer.beyond(zone)
                    if gone is None or gone.isNull() or gone.Volume < 1e-12:
                        continue
                    kept = []
                    for piece in pieces:
                        try:
                            kept += [x for x in piece.cut(gone).Solids if x.Volume > 1e-12]
                        except Exception:
                            kept.append(piece)
                    pieces = kept
            (adds if outward else cuts).extend(pieces)
    result = shape
    try:
        # all pieces as tools of one boolean (fusing the thin, overlapping wedges first made
        # a solid the cut then went wrong with)
        if cuts:
            result = result.cut(cuts)
        if adds:
            result = result.fuse(adds)
    except Exception as exc:
        raise _err("The drafted walls could not be joined to the part: %s" % exc)
    solids = [s for s in result.Solids if s.Volume > 1e-9]
    if not solids:
        raise _err("The draft leaves no solid.")
    if len(solids) > len(shape.Solids):
        raise _err("This draft would cut the part into pieces. Try a smaller angle.")
    out = solids[0] if len(solids) == 1 else Part.makeCompound(solids)
    try:
        refined = out.removeSplitter()  # the slab ends merge into the flat top / bottom
        # (OpenCASCADE's volume of B-spline faces is a little off: only a gross change counts)
        if (
            refined.isValid()
            and len(refined.Solids) == len(out.Solids)
            and abs(refined.Volume - out.Volume) < 1e-3 * max(1.0, out.Volume)
        ):
            out = refined
    except Exception:
        pass
    if not out.isValid():
        out = out.copy()
        out.fix(1e-7, 1e-7, 1e-7)
        if not out.isValid():
            raise _err("The drafted part is not a valid solid. Try a smaller angle.")
    return out
