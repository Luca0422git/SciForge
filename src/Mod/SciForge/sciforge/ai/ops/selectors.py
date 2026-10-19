# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pick edges or faces of a shape by geometric rules instead of by name.

Golden models must not say "Edge7": names change between FreeCAD versions and
are exactly what reference-stability work is about. They describe *which*
geometry a user would click, e.g. "the 4 straight edges at the top":

    {"type": "line", "at": {"axis": "z", "value": "max"}, "count": 4}

Filters (all optional, combined with AND, applied in this order):
    type         line | circle | ellipse | bspline            (edges)
                 plane | cylinder | cone | sphere | torus | bspline (faces)
    normal       [x, y, z]  planar faces whose outward normal points this way
    parallel     [x, y, z]  straight edges parallel to this direction (either sense)
    radius       number     circles / cylinders / spheres with this radius
    on_faces     selector   edges that bound the faces this selector picks
    not_on_faces selector   edges that do NOT bound those faces
    at           {"axis": "x|y|z", "value": "max" | "min" | number}, or a list of them
                 keeps elements whose centre lies at the extreme (or given value)
                 along that axis, among the elements that survived the filters above
                 (a list applies each condition in turn)
    all          true       no filtering (combine with nothing else)
    count        integer    the selection must contain exactly this many, or the
                            model fails loudly (protects against silent drift)
    any_of       [selector, ...]   union of several selectors (each may have count)
"""

TOL = 1e-6

_EDGE_TYPES = {
    "Line": "line",
    "LineSegment": "line",
    "Circle": "circle",
    "Ellipse": "ellipse",
    "BSplineCurve": "bspline",
    "BezierCurve": "bspline",
}
_FACE_TYPES = {
    "Plane": "plane",
    "Cylinder": "cylinder",
    "Cone": "cone",
    "Sphere": "sphere",
    "Toroid": "torus",
    "BSplineSurface": "bspline",
    "BezierSurface": "bspline",
}
_AXIS = {"x": 0, "y": 1, "z": 2}


class SelectionError(ValueError):
    pass


def _xyz(v):
    return (v.x, v.y, v.z)


def _unit(vec):
    x, y, z = vec
    n = (x * x + y * y + z * z) ** 0.5
    if n < TOL:
        raise SelectionError("zero-length direction %r" % (vec,))
    return (x / n, y / n, z / n)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def edge_type(edge):
    return _EDGE_TYPES.get(type(edge.Curve).__name__, "other")


def face_type(face):
    return _FACE_TYPES.get(type(face.Surface).__name__, "other")


def face_normal(face):
    u0, u1, v0, v1 = face.ParameterRange
    return _xyz(face.normalAt((u0 + u1) / 2.0, (v0 + v1) / 2.0))


def _center(element):
    return _xyz(element.CenterOfMass)


def _radius(element, kind):
    if kind in ("circle", "cylinder", "sphere"):
        geom = element.Curve if hasattr(element, "Curve") else element.Surface
        return geom.Radius
    return None


def _same_edge(a, b):
    return a.isSame(b)


def select(shape, spec, element="edges"):
    """Return sorted element names (e.g. ["Edge3", "Edge9"]) matching spec."""
    if not isinstance(spec, dict):
        raise SelectionError("selector must be an object, got %r" % (spec,))
    if "any_of" in spec:
        names = set()
        for sub in spec["any_of"]:
            names.update(select(shape, sub, element))
        result = sorted(names, key=_natural)
        _check_count(spec, result, element)
        return result

    items = list(enumerate(shape.Edges if element == "edges" else shape.Faces, start=1))
    prefix = "Edge" if element == "edges" else "Face"
    classify = edge_type if element == "edges" else face_type

    if spec.get("all"):
        result = ["%s%d" % (prefix, i) for i, _ in items]
        _check_count(spec, result, element)
        return result

    if "type" in spec:
        items = [(i, e) for i, e in items if classify(e) == spec["type"]]
    if "normal" in spec:
        if element != "faces":
            raise SelectionError("'normal' only applies to faces")
        want = _unit(spec["normal"])
        items = [
            (i, f)
            for i, f in items
            if face_type(f) == "plane" and _dot(_unit(face_normal(f)), want) > 1 - 1e-6
        ]
    if "parallel" in spec:
        want = _unit(spec["parallel"])
        kept = []
        for i, e in items:
            if element == "edges":
                if edge_type(e) != "line":
                    continue
                d = _unit(_xyz(e.Vertexes[-1].Point - e.Vertexes[0].Point))
            else:
                if face_type(e) != "plane":
                    continue
                d = _unit(face_normal(e))
            if abs(_dot(d, want)) > 1 - 1e-6:
                kept.append((i, e))
        items = kept
    if "radius" in spec:
        items = [
            (i, e)
            for i, e in items
            if _radius(e, classify(e)) is not None
            and abs(_radius(e, classify(e)) - spec["radius"]) < 1e-6
        ]
    if "on_faces" in spec or "not_on_faces" in spec:
        if element != "edges":
            raise SelectionError("'on_faces' only applies to edges")
        key = "on_faces" if "on_faces" in spec else "not_on_faces"
        face_names = select(shape, spec[key], "faces")
        face_edges = [e for name in face_names for e in shape.getElement(name).Edges]
        inside = [(i, e) for i, e in items if any(_same_edge(e, fe) for fe in face_edges)]
        if key == "on_faces":
            items = inside
        else:
            inside_ids = {i for i, _ in inside}
            items = [(i, e) for i, e in items if i not in inside_ids]
    if "at" in spec:
        conditions = spec["at"] if isinstance(spec["at"], list) else [spec["at"]]
        for at in conditions:
            axis = _AXIS[at["axis"].lower()]
            coords = [_center(e)[axis] for _, e in items]
            if not coords:
                break
            if at["value"] == "max":
                target = max(coords)
            elif at["value"] == "min":
                target = min(coords)
            else:
                target = float(at["value"])
            items = [(i, e) for (i, e), c in zip(items, coords) if abs(c - target) < 1e-4]

    result = ["%s%d" % (prefix, i) for i, _ in items]
    _check_count(spec, result, element)
    return result


def _natural(name):
    digits = "".join(ch for ch in name if ch.isdigit())
    return (name.rstrip("0123456789"), int(digits) if digits else 0)


def _check_count(spec, result, element):
    if "count" in spec and len(result) != spec["count"]:
        raise SelectionError(
            "selector %r picked %d %s, expected %d: %s"
            % (
                {k: v for k, v in spec.items() if k != "count"},
                len(result),
                element,
                spec["count"],
                ", ".join(result) or "nothing",
            )
        )
