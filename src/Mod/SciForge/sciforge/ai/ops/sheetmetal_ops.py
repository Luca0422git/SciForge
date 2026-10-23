# SPDX-License-Identifier: LGPL-2.1-or-later
"""Design steps for the SHEET METAL forming steps (rules, Flange, Hem, Bend), built with the same
SciForge code the dialogs use, registered on core.Builder when the package is imported. The step
format is checked by SciForgeTests/golden/sheetmetal_schema.py.

    {"op": "sf_sheet_rule", "name": "Thin", "from": "Steel (mm)", "set": {"thickness": "0.5"},
     "active": true}
        add (or change) a sheet metal rule In This Design; "from" starts it from a library or
        design rule; "active" makes it the design's active rule
    {"op": "sf_flange", "id": "f1", "kind": "base", "profile": "s1", "at": [[5, 5]],
     "rule": "Steel (mm)", "operation": "new_body", "options": {"orientation": "side1"}}
        base: closed sketch areas (all, or the ones holding the "at" points, sketch coordinates)
    {"op": "sf_flange", "id": "f2", "kind": "contour", "profile": "s2", "options": {...}}
        contour: every curve of the sketch (or the ones through the "at" points)
    {"op": "sf_flange", "id": "f3", "kind": "edge", "edges": [[50, 15, 1]], "options": {...},
     "target": {"plane": "XY", "offset": 20}, "offset_refs": [{"plane": "XZ", "offset": 5}, ...]}
        edge: straight edges of the current body through the given points; "target" is the
        To Object plane, "offset_refs" the two Two Offsets references (planes made for them)
    {"op": "sf_flange_edit", "target": "f3", "set": {"height": 20}}
"""

import FreeCAD as App

from .core import Builder, BuildError
from .primitive_ops import _settle


def _sketch(builder, name, where):
    sketch = builder.objects.get(name)
    if sketch is None or sketch.TypeId != "Sketcher::SketchObject":
        raise BuildError("%s: %r is not a sketch step" % (where, name))
    return sketch


def _profile_refs(builder, step, where):
    from sciforge import extrude

    sketch = _sketch(builder, step["profile"], where)
    builder.doc.recompute()
    place = sketch.getGlobalPlacement()
    if step["kind"] == "base":
        found = extrude.profile_regions(sketch)
        if "at" in step:
            picked = []
            for x, y in step["at"]:
                point = place.multVec(App.Vector(x, y, 0))
                hits = [sub for sub, face in found if face.isInside(point, 1e-6, True)]
                if len(hits) != 1:
                    raise BuildError("%s: no single profile at %r" % (where, [x, y]))
                picked.append((sketch, hits[0]))
            return picked
        if not found:
            raise BuildError("%s: the sketch has no closed profile" % where)
        return [(sketch, sub) for sub, _face in found]
    edges = list(sketch.Shape.Edges)
    if "at" in step:
        import Part

        picked = []
        for x, y in step["at"]:
            vertex = Part.Vertex(place.multVec(App.Vector(x, y, 0)))
            best = None
            for i, edge in enumerate(edges, 1):
                if edge.distToShape(vertex)[0] < 1e-4:
                    best = "Edge%d" % i
                    break
            if best is None:
                raise BuildError("%s: no sketch curve through %r" % (where, [x, y]))
            picked.append((sketch, best))
        return picked
    return [(sketch, "Edge%d" % i) for i in range(1, len(edges) + 1)]


def _edge_refs(builder, step, where):
    import Part

    tip = builder._tip()
    refs = []
    for point in step["edges"]:
        vertex = Part.Vertex(App.Vector(*[float(c) for c in point]))
        best = None
        for i, edge in enumerate(tip.Shape.Edges, 1):
            if edge.distToShape(vertex)[0] < 1e-4 and isinstance(
                edge.Curve, (Part.Line, Part.LineSegment)
            ):
                best = "Edge%d" % i
                break
        if best is None:
            raise BuildError("%s: no straight edge through %r" % (where, point))
        refs.append((tip, best))
    return refs


def _target(builder, spec, where):
    """A To Object pick: {"plane": "XY", "offset": d} (a datum plane made for it)."""
    if not spec:
        return None
    plane = builder.doc.addObject("Part::Plane", "FlangeTarget")
    plane.Length = plane.Width = 1.0
    rotations = {
        "XY": App.Rotation(),
        "XZ": App.Rotation(App.Vector(1, 0, 0), -90),
        "YZ": App.Rotation(App.Vector(0, 1, 0), 90),
    }
    if spec.get("plane") not in rotations:
        raise BuildError("%s: 'target' plane must be XY, XZ or YZ" % where)
    rot = rotations[spec["plane"]]
    plane.Placement = App.Placement(rot.multVec(App.Vector(0, 0, spec.get("offset", 0.0))), rot)
    builder.doc.recompute()
    try:
        from sciforge import bodies

        bodies.hide_from_timeline(plane)
    except Exception:
        pass
    return (plane, "Face1")


def op_sf_sheet_rule(self, step):
    from sciforge import sheetmetal
    from sciforge import sheetmetal_core as core

    where = "sf_sheet_rule %r" % step["name"]
    start = step.get("from")
    if start:
        rule = sheetmetal.find_rule(self.doc, start) or core.library_rule(start)
        if rule is None:
            raise BuildError("%s: no rule named %r" % (where, start))
    else:
        rule = sheetmetal.find_rule(self.doc, step["name"]) or core.make_rule(step["name"])
    rule = dict(rule, name=step["name"])
    for key, value in (step.get("set") or {}).items():
        rule[key] = value if isinstance(value, str) else repr(float(value))
    try:
        sheetmetal.save_rule(self.doc, rule)
    except ValueError as exc:
        raise BuildError("%s: %s" % (where, exc))
    if step.get("active"):
        sheetmetal.set_active_rule(self.doc, step["name"])
    self.doc.recompute()
    return None


def op_sf_flange(self, step):
    from sciforge import sheetmetal_flange as flange

    where = "sf_flange %r" % step["id"]
    kind = step["kind"]
    if kind == "edge":
        refs = _edge_refs(self, step, where)
    else:
        refs = _profile_refs(self, step, where)
    body = None
    if step.get("operation") == "join":
        body = self.body
    try:
        feature = flange.make(
            self.doc,
            kind,
            refs,
            dict(step.get("options") or {}),
            rule_name=step.get("rule"),
            operation=step.get("operation", "new_body"),
            body=body,
            name=step["id"],
            target=_target(self, step.get("target"), where),
            offset_refs=[_target(self, spec, where) for spec in step.get("offset_refs") or []],
        )
    except flange.FormError as exc:
        raise BuildError("%s: %s" % (where, exc))
    return _settle(self, step, feature, "sf_flange")


def op_sf_flange_edit(self, step):
    from sciforge import sheetmetal_flange as flange

    where = "sf_flange_edit %r" % step["target"]
    feature = self.objects.get(step["target"])
    if feature is None or not flange.is_flange(feature):
        raise BuildError("%s: not a flange step" % where)
    try:
        flange.update(feature, options=dict(step["set"]))
    except flange.FormError as exc:
        raise BuildError("%s: %s" % (where, exc))
    self._recompute(step, feature)
    return feature


Builder.op_sf_sheet_rule = op_sf_sheet_rule
Builder.op_sf_flange = op_sf_flange
Builder.op_sf_flange_edit = op_sf_flange_edit
