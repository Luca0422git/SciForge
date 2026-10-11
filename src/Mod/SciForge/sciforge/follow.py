# SPDX-License-Identifier: LGPL-2.1-or-later
"""Later steps keep their faces when an earlier Shell / Scale / Draft is edited, like in
Fusion. No GUI code.

FreeCAD's later steps (a sketch on a face, a Press Pull, a fillet...) name the faces and
edges they use. When an earlier step is edited so that the faces it gives are made in a
different way (a Shell changed from Inside to Both: the outside walls are new faces), or
the step is replaced by another kind of feature (FreeCAD's Thickness <-> SciForge's
shell), FreeCAD loses those names: the later step fails ("?Face3", "subshape not
found") or quietly uses another face. Fusion keeps them.

snapshot() remembers, before the edit, where every face/edge/corner used by a later
step is; repair() then points every reference FreeCAD lost at the element found again
on the new shape: the one in the same place, else the same kind of element facing the
same way nearest to where it was (a wall that moved by its new thickness).
"""

TOL = 1e-6


def _kind(element):
    try:
        return element.ShapeType
    except Exception:
        return ""


def _elements(shape, kind):
    return {"Face": shape.Faces, "Edge": shape.Edges, "Vertex": shape.Vertexes}.get(kind, [])


def _prefix(kind):
    return kind  # "Face" -> "Face3"


def _center(element):
    kind = _kind(element)
    if kind == "Vertex":
        return element.Point
    if kind == "Edge":
        return element.valueAt((element.FirstParameter + element.LastParameter) / 2.0)
    return element.CenterOfMass


def _size(element):
    kind = _kind(element)
    if kind == "Face":
        return element.Area
    if kind == "Edge":
        return element.Length
    return 0.0


def _surface(element):
    try:
        if _kind(element) == "Face":
            name = element.Surface.__class__.__name__
            if name in ("BSplineSurface", "BezierSurface"):
                try:
                    if element.Surface.isPlanar():
                        return "Plane"  # a flat face of a part scaled non-uniformly
                except Exception:
                    pass
            return name
        if _kind(element) == "Edge":
            return element.Curve.__class__.__name__
    except Exception:
        pass
    return ""


def _direction(element):
    """Outward normal of a flat face, direction of a straight edge, else None."""
    try:
        kind = _kind(element)
        if kind == "Face" and _surface(element) == "Plane":
            u0, u1, v0, v1 = element.ParameterRange
            n = element.normalAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)
            return n.normalize() if n.Length > 0 else None
        if kind == "Face" and _surface(element) in ("Cylinder", "Cone"):
            a = element.Surface.Axis
            return a.normalize() if a.Length > 0 else None
        if kind == "Edge" and _surface(element) == "Line":
            d = element.Vertexes[-1].Point - element.Vertexes[0].Point
            return d.normalize() if d.Length > 0 else None
    except Exception:
        pass
    return None


def same(a, b, tol=TOL):
    """True if two elements are the same place and size (copies of one another)."""
    if _kind(a) != _kind(b):
        return False
    try:
        if a.isSame(b):
            return True
    except Exception:
        pass
    size = max(1.0, abs(_size(a)))
    if abs(_size(a) - _size(b)) > tol * size * 10:
        return False
    if _surface(a) != _surface(b):
        return False
    return (_center(a) - _center(b)).Length < tol * max(1.0, size**0.5) * 10


def find(shape, element, fuzzy=True):
    """Name ("Face3") of the element of `shape` that is `element`: the one in the same
    place, else (fuzzy) the same kind facing the same way nearest to it. None if none."""
    kind = _kind(element)
    candidates = _elements(shape, kind)
    for i, other in enumerate(candidates, start=1):
        if same(element, other):
            return "%s%d" % (_prefix(kind), i)
    if not fuzzy:
        return None
    surface = _surface(element)
    direction = _direction(element)
    size = _size(element)
    center = _center(element)
    best = None
    for i, other in enumerate(candidates, start=1):
        if _surface(other) != surface:
            continue
        if direction is not None:
            other_dir = _direction(other)
            if other_dir is None:
                continue
            dot = direction.dot(other_dir)
            if kind == "Face" and surface == "Plane":
                if dot < 1.0 - 1e-6:
                    continue  # a flat face keeps facing the same way
            elif abs(dot) < 1.0 - 1e-6:
                continue
        if size > 0:
            ratio = _size(other) / size
            if ratio < 0.2 or ratio > 5.0:
                continue
        distance = (_center(other) - center).Length
        if best is None or distance < best[0] - 1e-9:
            best = (distance, i)
    return "%s%d" % (_prefix(kind), best[1]) if best is not None else None


# -- the references of later steps ------------------------------------------------------
def _link_props(obj):
    found = []
    for prop in obj.PropertiesList:
        try:
            kind = obj.getTypeIdOfProperty(prop)
        except Exception:
            continue
        if kind in ("App::PropertyLinkSub", "App::PropertyLinkSubList"):
            found.append((prop, kind))
        elif kind in ("App::PropertyLinkSubHidden", "App::PropertyLinkSubListHidden"):
            found.append((prop, kind))
    return found


def _entries(value):
    """[(object, [sub names])] of a LinkSub / LinkSubList value."""
    if value is None:
        return []
    if isinstance(value, tuple) and len(value) == 2 and hasattr(value[0], "Name"):
        return [(value[0], list(value[1] or []))]
    out = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, tuple) and len(item) == 2 and hasattr(item[0], "Name"):
                subs = item[1]
                subs = [subs] if isinstance(subs, str) else list(subs or [])
                out.append((item[0], subs))
    return out


def _element_name(sub):
    name = (sub or "").split(".")[-1].lstrip("?")
    return name if name.startswith(("Face", "Edge", "Vertex")) else ""


def snapshot(body, after):
    """{(object name, property): [(linked name, sub, element copy)]} for every step of
    `body` after `after` that uses faces/edges/corners (of any step of the body)."""
    records = {}
    if body is None:
        return records
    group = list(body.Group)
    try:
        start = group.index(after) + 1 if after is not None else 0
    except ValueError:
        start = 0
    for obj in group[start:]:
        for prop, _kind_name in _link_props(obj):
            try:
                value = getattr(obj, prop)
            except Exception:
                continue
            items = []
            for linked, subs in _entries(value):
                for sub in subs:
                    name = _element_name(sub)
                    if not name or (sub or "").startswith("?"):
                        continue
                    try:
                        element = linked.Shape.getElement(name).copy()
                    except Exception:
                        continue
                    items.append((linked.Name, name, element))
            if items:
                records[(obj.Name, prop)] = items
    return records


def _lost(obj):
    try:
        state = list(obj.State)
    except Exception:
        return False
    return "Invalid" in state or "Error" in state


def repair(doc, records):
    """Point references FreeCAD lost (or that now fail) at the element found again by
    geometry. True if something was changed (the caller recomputes)."""
    changed = False
    for (name, prop), items in records.items():
        obj = doc.getObject(name)
        if obj is None:
            continue
        try:
            value = getattr(obj, prop)
        except Exception:
            continue
        entries = _entries(value)
        if not entries:
            continue
        broken = _lost(obj)
        if not broken and not any(s.startswith("?") for _o, subs in entries for s in subs):
            continue
        remembered = {}
        for linked_name, sub, element in items:
            remembered.setdefault(linked_name, []).append((sub, element))
        new_entries = []
        touched = False
        for linked, subs in entries:
            known = list(remembered.get(linked.Name, []))
            new_subs = []
            for k, sub in enumerate(subs):
                plain = _element_name(sub)
                new = sub
                record = known[k] if k < len(known) and known[k][0] == plain else None
                if record is None:
                    record = next((r for r in known if r[0] == plain), None)
                if record is not None and (sub.startswith("?") or broken):
                    try:
                        shape = linked.Shape
                        current = None
                        if not sub.startswith("?"):
                            try:
                                current = shape.getElement(plain)
                            except Exception:
                                current = None
                        if current is None or not same(current, record[1]):
                            found = find(shape, record[1])
                            if found is not None:
                                new = found
                    except Exception:
                        pass
                if new != sub:
                    touched = True
                new_subs.append(new)
            new_entries.append((linked, new_subs))
        if not touched:
            continue
        try:
            if isinstance(value, tuple):
                setattr(obj, prop, (new_entries[0][0], new_entries[0][1]))
            else:
                setattr(obj, prop, [(o, tuple(s)) for o, s in new_entries])
            changed = True
        except Exception:
            continue
    return changed


def recompute(doc, records, compute=None, rounds=4):
    """Recompute, then give the later steps the faces/edges they lost back; a repaired
    step changes the steps after it, so look again (a few rounds). `compute` is the
    recompute to use (default doc.recompute)."""
    compute = compute or doc.recompute
    compute()
    for _round in range(rounds):
        if not records or not repair(doc, records):
            break
        compute()
