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
     "target": {"plane": "XY", "offset": 20}}
        edge: straight edges of the current body through the given points
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


# --- sm-more ---
# Bend, Hem, Join by Bend, Corner Closure, Lofted Flange and the sheet metal Fillet / Chamfer
# (branch sf/sm-more). Picks are points: a face / an edge of the current body through the point
# (design coordinates), sketch lines through points given in sketch coordinates.
#
#    {"op": "sf_sm_bend", "id": "b1", "face": [10, 10, 1], "lines": "s2", "at": [[25, 0]],
#     "options": {"angle": 90, "position": "center", "flip": false}}
#    {"op": "sf_sm_hem", "id": "h1", "edges": [[50, 15, 1]], "options": {"type": "open", ...}}
#    {"op": "sf_sm_join_bend", "id": "j1", "first": [50, 15, 1], "other": "f2",
#     "second": [60, 15, 5], "options": {"use_rule_radius": true}}
#    {"op": "sf_sm_corner_closure", "id": "c1", "dominant": [x, y, z], "submissive": [x, y, z],
#     "options": {"alignment": "symmetric", "gap": 1}}
#    {"op": "sf_sm_lofted_flange", "id": "l1", "profile1": "s1", "profile2": "s2",
#     "rule": "Steel (mm)", "options": {"forming": "brake", "control": "chord_tolerance", ...}}
#    {"op": "sf_sm_fillet", "id": "r1", "sets": [{"edges": [[0, 0, 0.5]], "value": 5}]}
#    {"op": "sf_sm_chamfer", "id": "r2", "sets": [{"edges": [[0, 0, 0.5]], "value": 3}]}
#    {"op": "sf_sm_more_edit", "target": "h1", "set": {"type": "rolled"}}


def _smm_point(value):
    return App.Vector(*[float(c) for c in value])


def _smm_edge(shape, point, where):
    import Part

    vertex = Part.Vertex(_smm_point(point))
    for i, edge in enumerate(shape.Edges, 1):
        if edge.distToShape(vertex)[0] < 1e-4:
            return "Edge%d" % i
    raise BuildError("%s: no edge through %r" % (where, list(point)))


def _smm_face(shape, point, where):
    import Part

    vertex = Part.Vertex(_smm_point(point))
    for i, face in enumerate(shape.Faces, 1):
        if face.Surface.TypeId == "Part::GeomPlane" and face.distToShape(vertex)[0] < 1e-4:
            return "Face%d" % i
    raise BuildError("%s: no flat face through %r" % (where, list(point)))


def _smm_local(builder, point):
    """A design-coordinates point in the current body's own coordinates."""
    place = builder.body.getGlobalPlacement()
    return place.inverse().multVec(_smm_point(point))


def op_sf_sm_bend(self, step):
    from sciforge import sheetmetal_bend as sb

    where = "sf_sm_bend %r" % step["id"]
    tip = self._tip()
    local = _smm_local(self, step["face"])
    face = _smm_face(tip.Shape, local, where)
    sketch = _sketch(self, step["lines"], where)
    self.doc.recompute()
    spec = {"kind": "contour", "profile": step["lines"]}
    if "at" in step:
        spec["at"] = step["at"]
    subs = [sub for _s, sub in _profile_refs(self, spec, where)]
    try:
        feature = sb.make(
            self.body,
            tip,
            face,
            local,
            [(sketch, subs)],
            dict(step.get("options") or {}),
            name=step["id"],
        )
    except sb.SheetMetalError as exc:
        raise BuildError("%s: %s" % (where, exc))
    return _settle(self, step, feature, "sf_sm_bend")


def op_sf_sm_hem(self, step):
    from sciforge import sheetmetal_hem as sh

    where = "sf_sm_hem %r" % step["id"]
    tip = self._tip()
    names = [_smm_edge(tip.Shape, _smm_local(self, p), where) for p in step["edges"]]
    feature = sh.make(self.body, tip, names, dict(step.get("options") or {}), name=step["id"])
    return _settle(self, step, feature, "sf_sm_hem")


def op_sf_sm_join_bend(self, step):
    from sciforge import bodies
    from sciforge import sheetmetal_bend_join as sj

    where = "sf_sm_join_bend %r" % step["id"]
    other = self.objects.get(step["other"])
    other_body = bodies.body_of(other) if other is not None else None
    if other_body is None:
        raise BuildError("%s: 'other' must name an earlier step of another body" % where)
    other_tip = other_body.Tip
    tip = self._tip()
    first = _smm_edge(tip.Shape, _smm_local(self, step["first"]), where)
    other_local = other_body.getGlobalPlacement().inverse().multVec(_smm_point(step["second"]))
    second = _smm_edge(other_tip.Shape, other_local, where)
    feature = sj.make(
        self.body, tip, first, other_tip, second, dict(step.get("options") or {}), name=step["id"]
    )
    return _settle(self, step, feature, "sf_sm_join_bend")


def op_sf_sm_corner_closure(self, step):
    from sciforge import sheetmetal_corner as sc

    where = "sf_sm_corner_closure %r" % step["id"]
    tip = self._tip()
    dominant = _smm_edge(tip.Shape, _smm_local(self, step["dominant"]), where)
    submissive = _smm_edge(tip.Shape, _smm_local(self, step["submissive"]), where)
    feature = sc.make(
        self.body, tip, dominant, submissive, dict(step.get("options") or {}), name=step["id"]
    )
    return _settle(self, step, feature, "sf_sm_corner_closure")


def op_sf_sm_lofted_flange(self, step):
    from sciforge import sheetmetal_lofted as sl

    where = "sf_sm_lofted_flange %r" % step["id"]
    one = _sketch(self, step["profile1"], where)
    two = _sketch(self, step["profile2"], where)
    options = dict(step.get("options") or {})
    options["operation"] = step.get("operation", "new_body")
    self.doc.recompute()
    body = sl.target_body(self.doc, options["operation"], self.body, step.get("rule"))
    feature = sl.make(body, [(one, [])], [(two, [])], options, name=step["id"])
    return _settle(self, step, feature, "sf_sm_lofted_flange")


def _smm_round(self, step, kind):
    from sciforge import sheetmetal_corner_round as sr

    where = "sf_sm_%s %r" % (kind, step["id"])
    tip = self._tip()
    sets = []
    for entry in step["sets"]:
        names = [_smm_edge(tip.Shape, _smm_local(self, p), where) for p in entry["edges"]]
        sets.append({"edges": names, "value": float(entry["value"])})
    feature = sr.make(self.body, tip, kind, sets, name=step["id"])
    return _settle(self, step, feature, "sf_sm_" + kind)


def op_sf_sm_fillet(self, step):
    return _smm_round(self, step, "fillet")


def op_sf_sm_chamfer(self, step):
    return _smm_round(self, step, "chamfer")


def op_sf_sm_more_edit(self, step):
    """Change a Bend / Hem / Corner Closure / Lofted Flange step's options afterwards (what
    the dialog's edit does), then recompute."""
    from sciforge import bodies
    from sciforge import sheetmetal_bend as sb
    from sciforge import sheetmetal_corner as sc
    from sciforge import sheetmetal_hem as sh
    from sciforge import sheetmetal_lofted as sl

    where = "sf_sm_more_edit %r" % step["target"]
    feature = self.objects.get(step["target"])
    kind = bodies.kind(feature) if feature is not None else ""
    if kind == sb.KIND:
        base, face, point, lines, options = sb.read(feature)
        options.update(step["set"])
        sb.apply(feature, base, face, point, lines, options)
    elif kind == sh.KIND:
        base, names, options = sh.read(feature)
        options.update(step["set"])
        sh.apply(feature, base, names, options)
    elif kind == sc.KIND:
        base, dominant, submissive, options = sc.read(feature)
        options.update(step["set"])
        sc.apply(feature, base, dominant, submissive, options)
    elif kind == sl.KIND:
        one, two, options = sl.read(feature)
        options.update(step["set"])
        sl.apply(feature, one, two, options)
    else:
        raise BuildError("%s: not a Bend, Hem, Corner Closure or Lofted Flange step" % where)
    self._recompute(step, feature)
    return feature


Builder.op_sf_sm_bend = op_sf_sm_bend
Builder.op_sf_sm_hem = op_sf_sm_hem
Builder.op_sf_sm_join_bend = op_sf_sm_join_bend
Builder.op_sf_sm_corner_closure = op_sf_sm_corner_closure
Builder.op_sf_sm_lofted_flange = op_sf_sm_lofted_flange
Builder.op_sf_sm_fillet = op_sf_sm_fillet
Builder.op_sf_sm_chamfer = op_sf_sm_chamfer
Builder.op_sf_sm_more_edit = op_sf_sm_more_edit
