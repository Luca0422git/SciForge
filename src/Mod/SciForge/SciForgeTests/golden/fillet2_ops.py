# SPDX-License-Identifier: LGPL-2.1-or-later
"""Golden-model steps for the Fillet / Chamfer options of SciForge's own fillet step
(sciforge/fillet_sets.py, the code the F and Chamfer dialogs use). Registered on
builder.Builder when builder.py is imported.

  {"op": "fillet_sets", "id": "f1", "kind": "fillet" | "chamfer", "tangent_chain": true,
   "sets": [{"edges": sel, "faces": sel, "features": [step ids],
             "radius": 1, "radius_type": "constant" | "chord" | "variable", "chord": 3,
             "start": 1, "end": 1.5, "points": [[0.5, 3]]}, ...]}
      Fusion's selection sets: one row each, one step. Chamfer rows take "chamfer_type"
      (equal / two / angle), "distance", "distance2", "angle", "flip".
  {"op": "rule_fillet", "id": "r1", "radius": 1, "rule": "all" | "between",
   "faces": sel, "features": [step ids], "faces2": sel, "features2": [step ids],
   "rounds": true, "fillets": true}
      Rule Fillet: the edges are found again from the faces / steps at every compute.
  {"op": "full_round", "id": "fr1", "faces": [sel, ...]}
      Full Round Fillet: each selector picks one centre face (the side faces are found).
  {"op": "blend_radius_expect", "at": [x, y, z], "radius": r, "tol": 0.01}
      The round on a 90 degree edge passes (sqrt(2) - 1) R from the old corner `at`: the
      radius measured there must be `radius` (a Variable fillet's radius points).
"""

import math

from . import selectors
from .builder import Builder, BuildError

ROW_KEYS = (
    "radius",
    "radius_type",
    "chord",
    "start",
    "end",
    "points",
    "chamfer_type",
    "distance",
    "distance2",
    "angle",
    "flip",
)


def _picks(builder, shape, info, item, edge_key="edges", face_key="faces", feature_key=None):
    from sciforge import blend

    refs = []
    if edge_key and edge_key in item:
        refs += selectors.select(shape, item[edge_key], "edges")
    if face_key in item:
        refs += selectors.select(shape, item[face_key], "faces")
    if feature_key and feature_key in item:
        for name in item[feature_key]:
            refs += [e for e in blend.feature_edges(builder.objects[name], info) if e not in refs]
    return refs


def _build(builder, step, spec, refs, refs2=(), features=(), features2=()):
    from sciforge import blend, fillet_sets

    base = builder._tip()
    try:
        fillet_sets.compute(base.Shape, spec, refs, refs2, features, features2)
        feature = fillet_sets.make(
            builder.body, base, spec, refs, refs2, features, features2, name=step["id"]
        )
    except blend.BlendError as exc:
        raise BuildError("%s %r: %s" % (step["op"], step["id"], exc))
    builder.objects[step["id"]] = feature
    builder.ops[step["id"]] = step["op"]
    builder._recompute(step, feature)
    return feature


def op_fillet_sets(self, step):
    from sciforge import blend, fillet_core as core

    kind = step.get("kind", "fillet")
    base = self._tip()
    info = blend.ShapeInfo(base.Shape)
    spec = core.default_spec(kind)
    spec["tangent_chain"] = bool(step.get("tangent_chain", True))
    spec["sets"] = []
    groups = []
    for item in step["sets"]:
        row = core.new_set(kind)
        for key in ROW_KEYS:
            if key in item and key in row:
                row[key] = item[key]
        refs = _picks(self, base.Shape, info, item, feature_key="features")
        if not refs:
            raise BuildError("fillet_sets %r: a set picked nothing" % step["id"])
        spec["sets"].append(row)
        groups.append(refs)
    flat, counts = core.join_refs(groups)
    for row, count in zip(spec["sets"], counts):
        row["count"] = count
    return _build(self, step, spec, flat)


def op_rule_fillet(self, step):
    from sciforge import fillet_core as core

    base = self._tip()
    spec = core.default_spec("fillet")
    spec.update(
        mode="rule",
        rule=step.get("rule", "all"),
        radius=float(step["radius"]),
        rounds=bool(step.get("rounds", True)),
        fillets=bool(step.get("fillets", True)),
    )
    spec["sets"] = [core.new_set("fillet", "rule")]
    faces = selectors.select(base.Shape, step["faces"], "faces") if "faces" in step else []
    faces2 = selectors.select(base.Shape, step["faces2"], "faces") if "faces2" in step else []
    features = [self.objects[n] for n in step.get("features", [])]
    features2 = [self.objects[n] for n in step.get("features2", [])]
    spec["sets"][0]["count"] = len(faces)
    return _build(self, step, spec, faces, faces2, features, features2)


def op_full_round(self, step):
    from sciforge import fillet_core as core, fillet_sets

    base = self._tip()
    spec = core.default_spec("fillet")
    spec["mode"] = "full_round"
    spec["sets"] = []
    flat = []
    for sel in step["faces"]:
        names = selectors.select(base.Shape, sel, "faces")
        if len(names) != 1:
            raise BuildError("full_round %r: each selector picks one centre face" % step["id"])
        try:
            side1, side2 = fillet_sets.side_faces(base.Shape, names[0])
        except core.SetError as exc:
            raise BuildError("full_round %r: %s" % (step["id"], exc))
        row = core.new_set("fillet", "full_round")
        row["count"] = 3
        spec["sets"].append(row)
        flat += [side1, names[0], side2]
    return _build(self, step, spec, flat)


def op_blend_radius_expect(self, step):
    import FreeCAD as App
    import Part

    shape = self.body.Shape
    point = App.Vector(*step["at"])
    measured = shape.distToShape(Part.Vertex(point))[0] / (math.sqrt(2.0) - 1.0)
    if abs(measured - float(step["radius"])) > float(step.get("tol", 0.01)):
        raise BuildError(
            "blend_radius_expect at %s: radius %.4f, expected %g"
            % (step["at"], measured, step["radius"])
        )
    return None


Builder.op_fillet_sets = op_fillet_sets
Builder.op_rule_fillet = op_rule_fillet
Builder.op_full_round = op_full_round
Builder.op_blend_radius_expect = op_blend_radius_expect
