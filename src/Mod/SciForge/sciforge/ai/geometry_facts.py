# SPDX-License-Identifier: LGPL-2.1-or-later
"""Facts about the faces, edges and corners of a shape, and a stable reference to each one,
for the AI tools query_geometry, inspect_design and render (docs/sciforge/dev/
cadcraft-lessons.md idea 3: "query_faces by selector, so an agent confirms numbers before
trusting a picture").

A fact is what Fusion's Measure and Properties show for a pick: the kind of surface or
curve, its area or length, centre, normal (flat faces), axis and radius (round ones), start
and end (edges). A stable reference is a selector (sciforge/ai/ops/selectors.py, the
language every AI tool takes) that picks exactly that one element by its geometry, e.g.
{"type": "plane", "normal": [0, 0, 1], "at": {"axis": "z", "value": "max"}, "count": 1}:
it keeps working when FreeCAD renumbers "Face7", and the AI can hand it straight to fillet,
chamfer, measure or create_sketch. It is built from the cheapest filters that make the
pick unique (the type, then the normal / direction / radius, then the position along x, y
and z, "max" / "min" when the element is at the extreme, so "the top face" stays the top
face when the part grows), then checked with the selector code itself.

Needs FreeCAD (Part shapes); no Qt.
"""

import math

from .ops import selectors

TOL = 1e-4  # the selectors' "at" tolerance (selectors.select keeps |c - target| < 1e-4)


def _r(value, digits=6):
    try:
        out = round(float(value), digits)
        return 0.0 if out == 0 else out
    except Exception:
        return value


def _xyz(vector, digits=6):
    return [_r(vector.x, digits), _r(vector.y, digits), _r(vector.z, digits)]


def _bbox(box):
    return [_r(v) for v in (box.XMin, box.YMin, box.ZMin, box.XMax, box.YMax, box.ZMax)]


def elements(shape, element):
    """The shape's faces / edges / vertices as [(name, sub-shape)] (Face1, Face2...)."""
    if element == "faces":
        return [("Face%d" % i, f) for i, f in enumerate(shape.Faces, start=1)]
    if element == "edges":
        return [("Edge%d" % i, e) for i, e in enumerate(shape.Edges, start=1)]
    return [("Vertex%d" % i, v) for i, v in enumerate(shape.Vertexes, start=1)]


# -- facts --------------------------------------------------------------------------------------
def face_facts(face):
    kind = selectors.face_type(face)
    out = {"type": kind, "area_mm2": _r(face.Area), "center_mm": _xyz(face.CenterOfMass)}
    surface = face.Surface
    try:
        if kind == "plane":
            out["normal"] = [_r(c) for c in selectors.face_normal(face)]
        elif kind in ("cylinder", "cone"):
            out["axis"] = _xyz(surface.Axis)
            out["axis_point_mm"] = _xyz(surface.Center if kind == "cylinder" else surface.Apex)
            if kind == "cylinder":
                out["radius_mm"] = _r(surface.Radius)
                out["diameter_mm"] = _r(2 * surface.Radius)
            else:
                out["half_angle_deg"] = _r(math.degrees(surface.SemiAngle))
        elif kind == "sphere":
            out["radius_mm"] = _r(surface.Radius)
            out["sphere_center_mm"] = _xyz(surface.Center)
        elif kind == "torus":
            out["major_radius_mm"] = _r(surface.MajorRadius)
            out["minor_radius_mm"] = _r(surface.MinorRadius)
            out["axis"] = _xyz(surface.Axis)
    except Exception:
        pass
    out["bbox_mm"] = _bbox(face.BoundBox)
    out["edges"] = len(face.Edges)
    return out


def edge_facts(edge):
    kind = selectors.edge_type(edge)
    out = {"type": kind, "length_mm": _r(edge.Length), "center_mm": _xyz(edge.CenterOfMass)}
    try:
        verts = edge.Vertexes
        if verts:
            out["start_mm"] = _xyz(verts[0].Point)
            out["end_mm"] = _xyz(verts[-1].Point)
        out["closed"] = bool(edge.isClosed())
        curve = edge.Curve
        if kind == "line" and len(verts) >= 2:
            d = verts[-1].Point - verts[0].Point
            if d.Length > 1e-12:
                d.normalize()
                out["direction"] = _xyz(d)
        elif kind in ("circle", "ellipse"):
            out["curve_center_mm"] = _xyz(curve.Center)
            out["axis"] = _xyz(curve.Axis)
            if kind == "circle":
                out["radius_mm"] = _r(curve.Radius)
                out["diameter_mm"] = _r(2 * curve.Radius)
            else:
                out["major_radius_mm"] = _r(curve.MajorRadius)
                out["minor_radius_mm"] = _r(curve.MinorRadius)
    except Exception:
        pass
    return out


def vertex_facts(vertex):
    return {"type": "vertex", "point_mm": _xyz(vertex.Point)}


def facts(sub, element):
    if element == "faces":
        return face_facts(sub)
    if element == "edges":
        return edge_facts(sub)
    return vertex_facts(sub)


# -- stable references -------------------------------------------------------------------------
class _Index:
    """What the selectors look at, computed once per element (type, normal, direction,
    radius, centre), so finding a unique selector for every element stays fast."""

    def __init__(self, shape, element):
        self.element = element
        self.items = elements(shape, element)
        self.kind = []
        self.normal = []
        self.direction = []
        self.radius = []
        self.center = []
        classify = selectors.face_type if element == "faces" else selectors.edge_type
        for _name, sub in self.items:
            kind = classify(sub)
            self.kind.append(kind)
            normal = direction = radius = None
            try:
                if element == "faces" and kind == "plane":
                    normal = selectors._unit(selectors.face_normal(sub))
                if element == "edges" and kind == "line":
                    a, b = sub.Vertexes[0].Point, sub.Vertexes[-1].Point
                    direction = selectors._unit((b.x - a.x, b.y - a.y, b.z - a.z))
                radius = selectors._radius(sub, kind)
            except Exception:
                pass
            self.normal.append(normal)
            self.direction.append(direction)
            self.radius.append(radius)
            c = sub.CenterOfMass
            self.center.append((c.x, c.y, c.z))

    def base(self, i):
        """The geometric filters of element i (no position yet), as a selector dict."""
        spec = {"type": self.kind[i]} if self.kind[i] != "other" else {}
        if self.normal[i] is not None:
            spec["normal"] = [_r(c, 9) for c in self.normal[i]]
        if self.direction[i] is not None:
            spec["parallel"] = [_r(c, 9) for c in self.direction[i]]
        if self.radius[i] is not None:
            spec["radius"] = _r(self.radius[i], 9)
        return spec

    def matches(self, j, spec):
        """Element j passes the selector's filters (selectors.select's rules)."""
        if "type" in spec and self.kind[j] != spec["type"]:
            return False
        if "normal" in spec:
            n = self.normal[j]
            if n is None or selectors._dot(n, selectors._unit(spec["normal"])) <= 1 - 1e-6:
                return False
        if "parallel" in spec:
            d = self.direction[j]
            if d is None or abs(selectors._dot(d, selectors._unit(spec["parallel"]))) <= 1 - 1e-6:
                return False
        if "radius" in spec:
            r = self.radius[j]
            if r is None or abs(r - spec["radius"]) >= 1e-6:
                return False
        return True


_AXES = ("x", "y", "z")


def _filter_at(index, candidates, axis, value):
    k = _AXES.index(axis)
    coords = [index.center[j][k] for j in candidates]
    if value == "max":
        target = max(coords)
    elif value == "min":
        target = min(coords)
    else:
        target = float(value)
    return [j for j, c in zip(candidates, coords) if abs(c - target) < TOL]


def _unique(index, i):
    """A selector that picks only element i, or None."""
    spec = index.base(i)
    if not spec:
        return None
    candidates = [j for j in range(len(index.items)) if index.matches(j, spec)]
    if i not in candidates:
        return None
    conditions = []
    used = set()
    while len(candidates) > 1 and len(used) < 3:
        best = None
        for k, axis in enumerate(_AXES):
            if axis in used:
                continue
            mine = index.center[i][k]
            coords = [index.center[j][k] for j in candidates]
            if abs(mine - max(coords)) < TOL:
                value = "max"
            elif abs(mine - min(coords)) < TOL:
                value = "min"
            else:
                value = _r(mine, 9)
            left = _filter_at(index, candidates, axis, value)
            if i not in left:
                continue
            rank = (len(left), 0 if value in ("max", "min") else 1, k)
            if best is None or rank < best[0]:
                best = (rank, axis, value, left)
        if best is None or len(best[3]) == len(candidates):
            break
        _rank, axis, value, candidates = best
        used.add(axis)
        conditions.append({"axis": axis, "value": value})
    if len(candidates) != 1:
        return None
    if conditions:
        spec["at"] = conditions[0] if len(conditions) == 1 else conditions
    spec["count"] = 1
    return spec


def stable_refs(shape, element, wanted=None, verify=True):
    """{name: selector or None} for the faces / edges (wanted: only these names). Vertices
    have no selector: a corner is picked by its point ({"vertex": [x, y, z]})."""
    if element == "vertices":
        return {name: None for name, _v in elements(shape, element)}
    index = _Index(shape, element)
    out = {}
    for i, (name, _sub) in enumerate(index.items):
        if wanted is not None and name not in wanted:
            continue
        spec = _unique(index, i)
        if spec is not None and verify:
            try:
                if selectors.select(shape, spec, element) != [name]:
                    spec = None
            except Exception:
                spec = None
        out[name] = spec
    return out


def pick_of(name, element, ref, sub=None):
    """The pick other tools take for this element ({"face": ref}, {"edge": ref},
    {"vertex": [x, y, z]})."""
    if element == "vertices" and sub is not None:
        return {"vertex": _xyz(sub.Point)}
    if ref is None:
        return None
    return {"face" if element == "faces" else "edge": ref}


def select_vertices(shape, spec):
    """Vertex names kept by a selector that only has "at" conditions (and count / all)."""
    items = elements(shape, "vertices")
    if spec.get("all") or not spec.get("at"):
        names = [n for n, _v in items]
    else:
        kept = list(range(len(items)))
        conditions = spec["at"] if isinstance(spec["at"], list) else [spec["at"]]
        for at in conditions:
            k = _AXES.index(str(at["axis"]).lower())
            coords = [getattr(items[j][1].Point, _AXES[k]) for j in kept]
            if not coords:
                break
            if at["value"] == "max":
                target = max(coords)
            elif at["value"] == "min":
                target = min(coords)
            else:
                target = float(at["value"])
            kept = [j for j, c in zip(kept, coords) if abs(c - target) < TOL]
        names = [items[j][0] for j in kept]
    if "count" in spec and len(names) != spec["count"]:
        raise selectors.SelectionError(
            "the selector picked %d vertices, expected %d" % (len(names), spec["count"])
        )
    return names
