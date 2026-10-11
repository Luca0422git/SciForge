# SPDX-License-Identifier: LGPL-2.1-or-later
"""Curves picked as a path, a guide rail, a centerline or a rib/web curve (Sweep, Loft, Rib,
Web). No GUI code.

A curve reference is (object, "EdgeN"): an edge of a sketch or of a body's feature, the
way FreeCAD's selection names it. refs_edges() gives the edges in global coordinates,
chain() finds the edges a Fusion "Chain Selection" click takes (the tangent chain), and
Path is one connected curve with a direction and a length scale:

    path = Path(refs_edges(refs))
    path.length, path.closed, path.point_at(s), path.tangent_at(s), path.sub(s0, s1)

Every edge of a Path runs forward along it (pieces of reversed edges are rebuilt the other
way round), so a Path's wire starts where the Path starts. OpenCASCADE's sweep follows the
wire's own direction for twist, taper and guide rails.
"""
import math

import FreeCAD as App

TOL = 1e-6


class CurveError(ValueError):
    """The picked curves cannot be used; the message says why and what to do."""


# -- references --------------------------------------------------------------------------
def owner_body(obj):
    if obj is None:
        return None
    if obj.TypeId == "PartDesign::Body":
        return obj
    parent = obj.getParentGeoFeatureGroup()
    while parent is not None and parent.TypeId != "PartDesign::Body":
        parent = parent.getParentGeoFeatureGroup()
    return parent


def is_sketch(obj):
    return obj is not None and obj.isDerivedFrom("Sketcher::SketchObject")


def _placement(obj):
    """Placement that takes `obj`'s shape (in its body) to global coordinates."""
    body = owner_body(obj)
    if body is None or body is obj:
        return App.Placement()
    return body.getGlobalPlacement()


def to_global(shape, obj):
    placement = _placement(obj)
    if placement.isIdentity():
        return shape.copy()
    shape = shape.copy()
    shape.Placement = placement.multiply(shape.Placement)
    return shape


def edge_of(obj, sub):
    """The edge `sub` of `obj` in global coordinates, or None."""
    try:
        edge = obj.Shape.getElement(sub)
    except Exception:
        return None
    if edge is None or edge.isNull() or edge.ShapeType != "Edge":
        return None
    return to_global(edge, obj)


def normalize(refs):
    """[(obj, "EdgeN"), ...] without repeats; (obj, "") stands for every edge of obj."""
    found, seen = [], set()
    for item in refs or []:
        obj, sub = item[0], item[1] if len(item) > 1 else ""
        if obj is None:
            continue
        subs = [sub] if isinstance(sub, str) else list(sub)
        if subs == [""] or not subs:
            try:
                subs = ["Edge%d" % i for i in range(1, len(obj.Shape.Edges) + 1)]
            except Exception:
                subs = []
        for s in subs:
            key = (obj.Name, s)
            if key not in seen:
                seen.add(key)
                found.append((obj, s))
    return found


def refs_edges(refs):
    """Global edges of curve references; raises CurveError if one is gone."""
    edges = []
    for obj, sub in normalize(refs):
        edge = edge_of(obj, sub)
        if edge is None:
            raise CurveError(
                "A curve picked from %s is gone. Pick the curve again." % getattr(obj, "Label", "?")
            )
        edges.append(edge)
    return edges


def is_curve_pick(obj, sub):
    """True for an edge of a sketch or of a part (what a path or rail click gives)."""
    return obj is not None and (sub or "").startswith("Edge")


def label(refs):
    """The curves in words, for a selection box."""
    refs = normalize(refs)
    if not refs:
        return ""
    names = sorted({obj.Label for obj, _ in refs})
    count = len(refs)
    return "%d curve%s (%s)" % (count, "" if count == 1 else "s", ", ".join(names))


# -- chains --------------------------------------------------------------------------------
def _ends(edge):
    """((start point, direction leaving the start), (end point, direction leaving the end))."""
    a, b = edge.FirstParameter, edge.LastParameter
    try:
        ta = edge.tangentAt(a)
        tb = edge.tangentAt(b)
    except Exception:
        ta = tb = None
    pa, pb = edge.valueAt(a), edge.valueAt(b)
    da = App.Vector(ta) if ta is not None else App.Vector()
    db = App.Vector(-tb.x, -tb.y, -tb.z) if tb is not None else App.Vector()
    return (pa, da), (pb, db)


def _tangent(d1, d2):
    """True if two directions leaving a shared vertex continue each other (G1)."""
    if d1.Length < 1e-12 or d2.Length < 1e-12:
        return False
    a, b = App.Vector(d1), App.Vector(d2)
    a.normalize()
    b.normalize()
    return a.dot(b) < -1.0 + 1e-6


def chain(obj, sub, tangent=True):
    """Names of the edges of `obj` connected to edge `sub`: through tangent joints only
    (Fusion's Chain Selection, tangent=True) or through any shared end (tangent=False).
    A joint where three or more curves meet stops the chain."""
    try:
        edges = list(obj.Shape.Edges)
    except Exception:
        return [sub]
    try:
        start = int(sub[4:]) - 1
    except Exception:
        return [sub]
    if not 0 <= start < len(edges):
        return [sub]
    ends = [_ends(e) for e in edges]

    def meeting(point):
        found = []
        for i, pair in enumerate(ends):
            for j, (p, d) in enumerate(pair):
                if (p - point).Length < 1e-6:
                    found.append((i, j, d))
        return found

    taken = {start}
    todo = [start]
    while todo:
        i = todo.pop()
        for _j, (p, d) in enumerate(ends[i]):
            at = [m for m in meeting(p) if m[0] != i]
            if len(at) != 1:
                continue  # an open end or a branch: the chain stops here
            k, _jj, dk = at[0]
            if k in taken:
                continue
            if tangent and not _tangent(d, dk):
                continue
            taken.add(k)
            todo.append(k)
    return ["Edge%d" % (i + 1) for i in sorted(taken)]


# -- a connected curve with a direction -----------------------------------------------------
def forward_piece(edge, u0, u1, reverse=False):
    """The piece of `edge` between curve parameters u0 < u1, running u0 -> u1 (or u1 -> u0
    with reverse=True, rebuilt on the reversed curve so the edge itself runs that way)."""
    curve = edge.Curve
    if not reverse:
        if abs(u0 - edge.FirstParameter) < 1e-12 and abs(u1 - edge.LastParameter) < 1e-12:
            return edge.copy()
        return curve.toShape(u0, u1)
    back = curve.copy()
    back.reverse()
    a, b = curve.reversedParameter(u1), curve.reversedParameter(u0)
    return back.toShape(min(a, b), max(a, b))


class Path:
    """One connected curve made of edges (global coordinates), every edge running forward
    along it. Raises CurveError if the edges do not form one chain."""

    def __init__(self, edges, start_near=None):
        import Part

        edges = [e for e in edges if e is not None and e.Length > TOL]
        if not edges:
            raise CurveError("Pick a curve: click a sketch line or an edge of the part.")
        try:
            groups = Part.sortEdges(edges, 1e-5)
        except Exception:
            groups = [edges]
        if len(groups) != 1:
            raise CurveError(
                "The picked curves are not one connected line (%d separate pieces). Pick curves "
                "that join end to end." % len(groups)
            )
        try:
            wire = Part.Wire(groups[0])
        except Exception as exc:
            raise CurveError("The picked curves do not join into one line: %s" % exc)
        ordered = list(wire.OrderedEdges)
        verts = list(wire.OrderedVertexes)
        current = verts[0].Point if verts else ordered[0].valueAt(ordered[0].FirstParameter)
        self.edges = []
        for e in ordered:
            p0, p1 = e.valueAt(e.FirstParameter), e.valueAt(e.LastParameter)
            if (p0 - current).Length <= (p1 - current).Length:
                self.edges.append(forward_piece(e, e.FirstParameter, e.LastParameter))
                current = p1
            else:
                self.edges.append(forward_piece(e, e.FirstParameter, e.LastParameter, True))
                current = p0
        self._finish()
        if start_near is not None and not self.closed:
            if (self.end - start_near).Length < (self.start - start_near).Length - 1e-9:
                self.edges = Path._reverse_edges(self.edges)
                self._finish()

    @staticmethod
    def _reverse_edges(edges):
        return [forward_piece(e, e.FirstParameter, e.LastParameter, True) for e in reversed(edges)]

    @classmethod
    def from_forward(cls, edges):
        """A Path of edges already running forward one after another."""
        path = cls.__new__(cls)
        path.edges = list(edges)
        path._finish()
        return path

    def _finish(self):
        self.lengths = [e.Length for e in self.edges]
        self.starts = []
        total = 0.0
        for length in self.lengths:
            self.starts.append(total)
            total += length
        self.length = total
        self.start = self.edges[0].valueAt(self.edges[0].FirstParameter)
        last = self.edges[-1]
        self.end = last.valueAt(last.LastParameter)
        self.closed = (self.start - self.end).Length < 1e-5

    # -- reading ---------------------------------------------------------------------------
    def wire(self):
        import Part

        return Part.Wire(self.edges)

    def is_straight(self):
        return len(self.edges) == 1 and self.edges[0].Curve.TypeId in (
            "Part::GeomLine",
            "Part::GeomLineSegment",
        )

    def _locate(self, s):
        s = max(0.0, min(self.length, s))
        for i in range(len(self.edges) - 1, -1, -1):
            if s >= self.starts[i] - 1e-12:
                return i, min(s - self.starts[i], self.lengths[i])
        return 0, 0.0

    def param_at(self, s):
        """(edge index, curve parameter) at length s from the start."""
        i, local = self._locate(s)
        edge = self.edges[i]
        if local <= 1e-12:
            return i, edge.FirstParameter
        if local >= self.lengths[i] - 1e-12:
            return i, edge.LastParameter
        return i, edge.getParameterByLength(local)

    def point_at(self, s):
        i, u = self.param_at(s)
        return self.edges[i].valueAt(u)

    def tangent_at(self, s):
        i, u = self.param_at(s)
        t = App.Vector(self.edges[i].tangentAt(u))
        if t.Length > 1e-12:
            t.normalize()
        return t

    def length_at(self, point):
        """Length from the start to the point of the path nearest `point`."""
        import Part

        probe = Part.Vertex(point)
        best = None
        for i, edge in enumerate(self.edges):
            try:
                dist = edge.distToShape(probe)[0]
            except Exception:
                continue
            if best is None or dist < best[0] - 1e-12:
                best = (dist, i)
        if best is None:
            return 0.0
        i = best[1]
        edge = self.edges[i]
        try:
            near = edge.distToShape(probe)[1][0][0]
            u = edge.Curve.parameter(near)
        except Exception:
            return self.starts[i]
        first, last = edge.FirstParameter, edge.LastParameter
        try:
            if edge.Curve.isPeriodic():
                period = edge.Curve.period()
                while u < first - 1e-9:
                    u += period
                while u > last + 1e-9:
                    u -= period
        except Exception:
            pass
        u = max(first, min(last, u))
        try:
            local = edge.Curve.length(first, u) if u > first else 0.0
        except Exception:
            local = 0.0
        return self.starts[i] + min(local, self.lengths[i])

    # -- making new paths ------------------------------------------------------------------
    def sub(self, s0, s1):
        """The part of the path from length s0 to s1 (s0 > s1 gives it running backwards)."""
        if s0 > s1:
            return self.sub(s1, s0).reversed()
        s0 = max(0.0, s0)
        s1 = min(self.length, s1)
        if s1 - s0 < TOL:
            raise CurveError("The sweep would be too short. Make the distance bigger.")
        pieces = []
        for i, edge in enumerate(self.edges):
            a, b = self.starts[i], self.starts[i] + self.lengths[i]
            lo, hi = max(a, s0), min(b, s1)
            if hi - lo < 1e-9:
                continue
            u0 = edge.FirstParameter if lo - a < 1e-12 else edge.getParameterByLength(lo - a)
            u1 = edge.LastParameter if b - hi < 1e-12 else edge.getParameterByLength(hi - a)
            pieces.append(forward_piece(edge, u0, u1))
        return Path.from_forward(pieces)

    def reversed(self):
        return Path.from_forward(Path._reverse_edges(self.edges))

    def restarted(self, s):
        """A closed path starting (and ending) at length s instead."""
        if not self.closed or s < TOL or s > self.length - TOL:
            return self
        return Path.from_forward(self.sub(s, self.length).edges + self.sub(0.0, s).edges)

    def samples(self, count):
        """[(s, point, unit tangent)] at `count` + 1 evenly spaced lengths."""
        found = []
        for k in range(count + 1):
            s = self.length * k / float(count)
            found.append((s, self.point_at(s), self.tangent_at(s)))
        return found

    def discretize(self, step=None):
        """Points along the path (for drawing it)."""
        points = []
        for edge in self.edges:
            count = 2 if edge.Curve.TypeId in ("Part::GeomLine", "Part::GeomLineSegment") else 24
            pts = edge.discretize(count)
            if points and (points[-1] - pts[0]).Length < 1e-9:
                pts = pts[1:]
            points += pts
        return points


def rotation_minimizing_frames(samples, first_normal):
    """Normals of a rotation-minimizing frame along sampled points (double reflection,
    Wang et al. 2008): the frame a profile keeps when it is swept without twisting."""
    normals = [App.Vector(first_normal)]
    for k in range(len(samples) - 1):
        _s0, x0, t0 = samples[k]
        _s1, x1, t1 = samples[k + 1]
        r0 = normals[-1]
        v1 = x1 - x0
        c1 = v1.dot(v1)
        if c1 < 1e-18:
            normals.append(App.Vector(r0))
            continue
        r_l = r0 - v1 * (2.0 / c1 * v1.dot(r0))
        t_l = t0 - v1 * (2.0 / c1 * v1.dot(t0))
        v2 = t1 - t_l
        c2 = v2.dot(v2)
        r1 = r_l - v2 * (2.0 / c2 * v2.dot(r_l)) if c2 > 1e-18 else r_l
        r1 = r1 - t1 * r1.dot(t1)
        if r1.Length < 1e-12:
            r1 = App.Vector(r0)
        r1.normalize()
        normals.append(r1)
    return normals


def any_normal(direction):
    """A unit vector square to `direction`."""
    d = App.Vector(direction)
    for axis in (App.Vector(0, 0, 1), App.Vector(1, 0, 0), App.Vector(0, 1, 0)):
        n = d.cross(axis)
        if n.Length > 1e-6:
            n.normalize()
            return n
    return App.Vector(1, 0, 0)


def twist_guide(path, turn, radius):
    """A guide curve that winds `turn` degrees round `path` from its start to its end (at
    `radius` from it), for OpenCASCADE's auxiliary-spine sweep: the profile then turns
    with it. Exact helix for a straight path, else interpolated through a
    rotation-minimizing frame."""
    import Part

    if abs(turn) < 1e-12:
        raise CurveError("no twist")
    if path.is_straight():
        pitch = path.length * 360.0 / abs(turn)
        helix = Part.makeHelix(pitch, path.length, radius, 0.0, turn < 0)
        direction = path.end - path.start
        rotation = App.Rotation(App.Vector(0, 0, 1), direction)
        helix.Placement = App.Placement(path.start, rotation)
        return Part.Wire(helix.Edges) if helix.ShapeType != "Wire" else helix
    count = max(48, 24 * len(path.edges))
    samples = path.samples(count)
    normals = rotation_minimizing_frames(samples, any_normal(samples[0][2]))
    points, params = [], []
    for (s, x, t), n in zip(samples, normals):
        angle = math.radians(turn) * s / path.length
        b = t.cross(n)
        points.append(x + (n * math.cos(angle) + b * math.sin(angle)) * radius)
        params.append(s / path.length)
    curve = Part.BSplineCurve()
    curve.interpolate(Points=points, Parameters=params)
    return Part.Wire(curve.toShape())
