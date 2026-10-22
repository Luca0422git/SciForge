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


# -- later steps that use a sweep / loft rebuilt as another kind of feature -----------------
# An edit can need the other kind of feature (FreeCAD's Pipe has no Distance, taper or twist,
# SciForge's sweep has), so the step is rebuilt as a new object in the same place. Fusion
# keeps what was built on it (a sketch on its end face, a fillet on its edges), while
# FreeCAD clears every link to a deleted object. Before the old step goes, every link of a
# later step to it is moved to the new one, each face / edge / corner found again on the new
# shape: the same place, else the same kind facing the same way nearest to where it was (an
# end face that moved because the sweep got shorter).
_CHAIN = {"BaseFeature", "_Body", "Group", "Tip", "Origin"}


def _element(sub):
    short = (sub or "").split(".")[-1].lstrip("?")
    return short if short.startswith(("Face", "Edge", "Vertex")) else ""


def relink_users(old, new):
    """Point every link of the objects using `old` (but not the body's own history chain) at
    `new`, which must be computed. Returns the objects changed."""
    from . import follow

    if old is None or new is None or old is new:
        return []
    users = [
        o
        for o in old.InList
        if o is not new and o.TypeId not in ("PartDesign::Body", "App::Part", "App::Origin")
    ]
    if not users:
        return []
    try:
        old_shape = None if old.Shape.isNull() else old.Shape
        new_shape = None if new.Shape.isNull() else new.Shape
    except Exception:
        old_shape = new_shape = None
    cache = {}

    def mapped(sub):
        short = _element(sub)
        if not short or old_shape is None or new_shape is None:
            return sub
        if short not in cache:
            try:
                found = follow.find(new_shape, old_shape.getElement(short))
            except Exception:
                found = None
            cache[short] = found or short
        return cache[short]

    def swapped(value):
        if value is None:
            return value, False
        if hasattr(value, "TypeId"):
            return (new, True) if value is old else (value, False)
        if isinstance(value, tuple) and len(value) == 2 and hasattr(value[0], "TypeId"):
            obj, subs = value
            if obj is not old:
                return value, False
            if isinstance(subs, str):
                return (new, mapped(subs)), True
            return (new, [mapped(s) for s in subs]), True
        if isinstance(value, (list, tuple)):
            out, changed = [], False
            for item in value:
                one, did = swapped(item)
                out.append(one)
                changed = changed or did
            return out, changed
        return value, False

    changed = []
    for user in users:
        for prop in user.PropertiesList:
            if prop in _CHAIN:
                continue
            try:
                kind = user.getTypeIdOfProperty(prop)
            except Exception:
                continue
            if not kind.startswith(("App::PropertyLink", "App::PropertyXLink")):
                continue
            try:
                value, did = swapped(getattr(user, prop))
                if not did:
                    continue
                setattr(user, prop, value)
            except Exception:
                continue  # that step then reports the lost link itself, like any other
            if user not in changed:
                changed.append(user)
    return changed


# -- picked elements of the part, found again when FreeCAD loses their names ------------------
# A sweep along an edge of the part, or a loft from a face of it, names that edge / face
# ("Edge3"). FreeCAD 1.1 loses such names after some edits of the step that made them (seen:
# the cylinder's Extrude edited after the design was reopened: the path became "?Edge3" and
# the sweep failed, "A curve picked from Extrude is gone"). Like Fusion, the sweep keeps
# following its edge: where each picked element was is remembered after every good compute,
# and a lost one is found again there (the same kind of curve or surface, facing the same
# way, nearest to where it was).
MEMORY = "SciForgeLinkMemory"
# A lost element found again may have turned a little (a taper added to the extrude under it
# tilts its side faces and edges): up to this much, nearest first.
SAME_WAY = math.cos(math.radians(30.0))
FAR = 0.25  # farther than this (a quarter of the part's size) is no longer the same element


def _record(element):
    kind = element.ShapeType
    rec = {"k": kind}
    try:
        if kind == "Vertex":
            rec["c"] = list(element.Point)
            return rec
        if kind == "Edge":
            curve = element.Curve
            rec["t"] = curve.TypeId
            rec["c"] = list(element.valueAt((element.FirstParameter + element.LastParameter) / 2))
            rec["s"] = element.Length
            if curve.TypeId in ("Part::GeomLine", "Part::GeomLineSegment"):
                d = element.Vertexes[-1].Point - element.Vertexes[0].Point
                if d.Length > TOL:
                    d.normalize()
                    rec["d"] = list(d)
            elif hasattr(curve, "Axis") and hasattr(curve, "Radius"):
                rec["d"] = list(curve.Axis)
                rec["r"] = curve.Radius
            return rec
        rec["t"] = element.Surface.TypeId
        if rec["t"] != "Part::GeomPlane" and _flat(element):
            rec["t"] = "Part::GeomPlane"  # a tapered extrude's flat sides are B-splines
        rec["c"] = list(element.CenterOfMass)
        rec["s"] = element.Area
        if rec["t"] == "Part::GeomPlane":
            u0, u1, v0, v1 = element.ParameterRange
            n = element.normalAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)
            if n.Length > TOL:
                n.normalize()
                rec["d"] = list(n)
    except Exception:
        pass
    return rec


def _flat(face):
    try:
        return face.findPlane() is not None
    except Exception:
        return False


def _same_way(a, b, kind, surface):
    dot = App.Vector(*a).dot(App.Vector(*b))
    if kind == "Face" and surface == "Part::GeomPlane":
        return dot > SAME_WAY  # a flat face keeps facing (about) the same way
    return abs(dot) > SAME_WAY


def _box(shape):
    b = shape.BoundBox
    return [b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax]


def _where(point, box):
    """`point` relative to the part's bounding box (0 .. 1 along each side it spans): the
    corner of a box made taller is still its top corner, where the old place is half way
    between the old top and bottom corners."""
    out = []
    for i, v in enumerate((point.x, point.y, point.z)):
        lo, hi = box[i], box[i + 3]
        out.append((v - lo) / (hi - lo) if hi - lo > TOL else 0.0)
    return App.Vector(*out)


class _Pool:
    """One shape's elements described once for any number of lost elements looked for on it
    (curves.refind, picks): the records of its edges / faces and its bounding box. A fillet
    of a hundred edges on a part of two thousand faces lost them all after an edit of the
    first step: looking for each one described every edge again (153 052 records and 253
    bounding boxes, 31 s); described once, the same search is the same answer in well under
    a second (SciForge speed with big designs, 2026-10-21)."""

    def __init__(self, shape):
        self.shape = shape
        self._box = None
        self._kinds = {}

    def box(self):
        if self._box is None:
            self._box = _box(self.shape)
        return self._box

    def elements(self, kind):
        """[(index, element or its record)] of `kind`: vertices as they are (their Point is
        all that is compared), edges and faces as their _record."""
        if kind not in self._kinds:
            pool = {"Edge": self.shape.Edges, "Face": self.shape.Faces, "Vertex": self.shape.Vertexes}
            out = []
            for i, other in enumerate(pool.get(kind) or [], start=1):
                if kind == "Vertex":
                    out.append((i, other))
                    continue
                try:
                    out.append((i, _record(other)))
                except Exception:
                    continue
            self._kinds[kind] = out
        return self._kinds[kind]


def _find_again(shape, rec, pool=None):
    """Name ("Edge3") of the element of `shape` that is most likely `rec`'s, or None. Nearest
    first: relative to the part's bounding box when the record has the box it was taken in
    (the part may have grown), else in place. `pool` (a _Pool of `shape`) shares the
    elements' descriptions between several searches on the same shape."""
    kind = rec.get("k")
    if kind not in ("Edge", "Face", "Vertex") or "c" not in rec:
        return None
    if pool is None:
        pool = _Pool(shape)
    candidates = pool.elements(kind)
    if not candidates:
        return None
    centre = App.Vector(*rec["c"])
    old_box = rec.get("b")
    new_box = pool.box() if old_box else None
    old_where = _where(centre, old_box) if old_box else None

    def gap(point):
        far = (point - centre).Length
        if not old_box:
            return far
        return (_where(point, new_box) - old_where).Length + 1e-6 * far

    best = None
    for i, there in candidates:
        try:
            if kind == "Vertex":
                distance = gap(there.Point)
            else:
                if there.get("t") != rec.get("t"):
                    continue
                if (
                    "d" in rec
                    and "d" in there
                    and not _same_way(rec["d"], there["d"], kind, rec["t"])
                ):
                    continue
                if (
                    "r" in rec
                    and "r" in there
                    and not 0.5 <= there["r"] / max(rec["r"], TOL) <= 2.0
                ):
                    continue
                size = rec.get("s", 0.0)
                if size > TOL and not 0.2 <= there.get("s", 0.0) / size <= 5.0:
                    continue
                distance = gap(App.Vector(*there["c"]))
        except Exception:
            continue
        if best is None or distance < best[0] - 1e-9:
            best = (distance, i)
    if best is not None and old_box and best[0] > FAR:
        return None  # nothing like it near where it was: rather red than another element
    return "%s%d" % (kind, best[1]) if best is not None else None


def _single(value):
    """True for the value of a one-object link (App::PropertyLinkSub): (object, [subs])."""
    return isinstance(value, tuple) and len(value) == 2 and hasattr(value[0], "Name")


def _items(value):
    """[(object, [sub names])] of a link (list) value."""
    if _single(value):
        value = [value]
    out = []
    for item in value or []:
        if isinstance(item, tuple) and len(item) == 2 and hasattr(item[0], "Name"):
            subs = item[1]
            subs = [subs] if isinstance(subs, str) else list(subs or [])
            out.append((item[0], subs))
    return out


def remember(feature, props, memory=MEMORY):
    """Store where the part elements linked by `props` are now (after a good compute), in the
    hidden property `memory` (saved with the file)."""
    import json

    data = {}
    shapes = {}  # linked object -> (shape, its box): one bounding box per part, not per pick
    for prop in props:
        rows = []
        for linked, subs in _items(getattr(feature, prop, None)):
            if linked is None or is_sketch(linked):
                continue
            for sub in subs:
                short = _element(sub)
                if not short or sub.startswith("?"):
                    continue
                try:
                    if linked.Name not in shapes:
                        shape = linked.Shape
                        shapes[linked.Name] = [shape, None]
                    entry = shapes[linked.Name]
                    rec = _record(entry[0].getElement(short))
                    if entry[1] is None:
                        entry[1] = _box(entry[0])
                    rec["b"] = list(entry[1])
                    rows.append([linked.Name, short, rec])
                except Exception:
                    continue
        if rows:
            data[prop] = rows
    text = json.dumps(data, sort_keys=True)
    if memory not in feature.PropertiesList:
        # hidden, output, no recompute: writing it from execute() changes nothing else
        feature.addProperty("App::PropertyString", memory, "SciForge", "Picked elements", 28)
    if getattr(feature, memory) != text:
        setattr(feature, memory, text)


def refind(feature, props, memory=MEMORY):
    """Point the links of `props` whose part element FreeCAD lost at the element found again
    where it was (remembered in the property `memory`). Returns {(object name, old name): new
    name} for the links changed."""
    import json

    try:
        memory = json.loads(getattr(feature, memory, "") or "{}")
    except Exception:
        return {}
    changed = {}
    pools = {}  # linked object -> _Pool: its elements described once for all lost picks
    for prop in props:
        rows = memory.get(prop) or []
        if not rows:
            continue
        entries = _items(getattr(feature, prop, None))
        touched = False
        renames = {}
        fixed = []
        for linked, subs in entries:
            new_subs = []
            for sub in subs:
                short = _element(sub)
                lost = bool(short) and (sub.startswith("?") or not _exists(linked, short))
                if lost and linked is not None and not is_sketch(linked):
                    rec = next((r for n, s, r in rows if n == linked.Name and s == short), None)
                    if rec is None:
                        # The step it was picked on was rebuilt as a new object (an extrude
                        # made thin): the link moved there with the old name.
                        doc = feature.Document
                        rec = next(
                            (r for n, s, r in rows if s == short and doc.getObject(n) is None),
                            None,
                        )
                    found = None
                    if rec:
                        if linked.Name not in pools:
                            pools[linked.Name] = _Pool(linked.Shape)
                        pool = pools[linked.Name]
                        found = _find_again(pool.shape, rec, pool)
                    if found is not None:
                        renames[(linked.Name, short)] = found
                        sub = found
                        touched = True
                new_subs.append(sub)
            fixed.append((linked, new_subs))
        if touched:
            try:
                if _single(getattr(feature, prop, None)):
                    setattr(feature, prop, fixed[0])
                else:
                    setattr(feature, prop, [(o, s) for o, s in fixed])
                changed.update(renames)
            except Exception:
                pass
    return changed


def _exists(obj, short):
    try:
        element = obj.Shape.getElement(short)
        return element is not None and not element.isNull()
    except Exception:
        return False


def computed(obj):
    """Recompute `obj` on its own (its base is up to date) without messages; True if it has a
    shape then."""
    from .preview import quiet

    try:
        with quiet():
            obj.recompute()
    except Exception:
        pass
    try:
        return not obj.Shape.isNull()
    except Exception:
        return False


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
