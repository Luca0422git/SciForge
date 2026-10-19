# SPDX-License-Identifier: LGPL-2.1-or-later
"""Design steps for the SURFACE tab, built with the same SciForge code the dialogs use
(sciforge/surface.py: surface.build), registered on core.Builder when the package is
imported.

  {"op": "sf_surface", "id": "w1", "kind": "extrude", "refs": [ref, ...], "refs2": [...],
   "options": {...}, "remove": [{"step": id, "at": [x, y, z]}], "cells": [[x, y, z]],
   "bodies": [step ids], "target": step id}
      kind: a SURFACE tool (surface_core.KINDS: extrude, revolve, sweep, loft, patch,
      ruled, offset, boundary_fill, thicken, trim, untrim, extend, stitch, unstitch,
      reverse_normal); refs / refs2 / refs3: what the dialog's boxes hold, in its order
      (surface_ui.py: profile / path / axis / tools ...):
        {"sketch": id, "at": [x, y]}     the sketch curve through that sketch point,
                                         chained like Chain Selection ("chain": false: just
                                         it; "tangent": true: through tangent joints only)
        {"sketch": id}                    every curve of the sketch
        {"plane": "XY"} / {"axis": "Z"}   an origin plane / axis
        {"step": id}                      that step's body, whole (Stitch, Trim, Fill tools)
        {"step": id, "faces": selector}   faces / edges of that step's body as it is now
        {"step": id, "edges": selector}
      remove: Trim's pieces (a point on each, in the body of `step`); cells: Boundary
      Fill's cells (a point inside each); bodies: Reverse Normal's bodies; target: the
      solid body a Thicken / Boundary Fill joins, cuts or intersects.
      The body the step is in becomes the one the model measures (Fusion: the body you
      work on).
  {"op": "sf_surface_edit", "target": "w1", "set": {options}}
      double-click the step in the timeline and change its fields
"""

import FreeCAD as App
import Part

from . import selectors
from .core import _AXIS_ROLE, _PLANE_ROLE, Builder, BuildError

REF_KEYS = ("refs", "refs2", "refs3")


def _body(builder, name, where):
    from sciforge import bodies

    obj = builder.objects.get(name)
    if obj is None:
        raise BuildError("%s: unknown step %r" % (where, name))
    body = obj if bodies.is_body(obj) else bodies.body_of(obj)
    if body is None:
        raise BuildError("%s: step %r is in no body" % (where, name))
    return body


def _sketch_curve(builder, spec, where):
    from sciforge import curves

    sketch = builder.objects.get(spec["sketch"])
    if sketch is None or builder.ops.get(spec["sketch"]) not in ("sketch", "sf_curves"):
        raise BuildError("%s: %r is not a sketch step" % (where, spec["sketch"]))
    if "at" not in spec:
        return [(sketch, "")]
    at = spec["at"]
    point = sketch.getGlobalPlacement().multVec(App.Vector(at[0], at[1], 0))
    probe = Part.Vertex(point)
    hit = None
    for i, edge in enumerate(sketch.Shape.Edges, start=1):
        if edge.distToShape(probe)[0] < 1e-6:
            hit = "Edge%d" % i
            break
    if hit is None:
        raise BuildError("%s: no curve of %s through %s" % (where, spec["sketch"], at))
    if not spec.get("chain", True):
        return [(sketch, hit)]
    return [(sketch, n) for n in curves.chain(sketch, hit, tangent=bool(spec.get("tangent")))]


def _refs(builder, specs, where):
    out = []
    for spec in specs or []:
        if "sketch" in spec:
            out += _sketch_curve(builder, spec, where)
        elif "plane" in spec:
            out.append((builder._origin(_PLANE_ROLE[spec["plane"]]), ""))
        elif "axis" in spec:
            out.append((builder._origin(_AXIS_ROLE[spec["axis"]]), ""))
        elif "faces" in spec or "edges" in spec:
            body = _body(builder, spec["step"], where)
            what = "faces" if "faces" in spec else "edges"
            names = selectors.select(body.Tip.Shape, spec[what], what)
            if not names:
                raise BuildError("%s: the %s selector picks nothing" % (where, what))
            out += [(body.Tip, n) for n in names]
        elif "step" in spec:
            out.append((_body(builder, spec["step"], where), ""))
        else:
            raise BuildError("%s: unknown reference %r" % (where, spec))
    return out


def _finish(builder, step, feature, where):
    from sciforge import bodies

    builder.doc.recompute()
    broken = [
        o.Label
        for o in builder.doc.Objects
        if "Invalid" in list(getattr(o, "State", [])) or "Error" in list(getattr(o, "State", []))
    ]
    if broken:
        raise BuildError("%s: these steps failed: %s" % (where, ", ".join(broken)))
    body = bodies.body_of(feature)
    if body is not None:
        builder.body = body  # Fusion: the body you work on
    return feature


def op_sf_surface(self, step):
    from sciforge import bodies, surface
    from sciforge import surface_core as core

    where = "sf_surface %r" % step["id"]
    kind = step["kind"]
    refs = {key: _refs(self, step.get(key), where) for key in REF_KEYS}
    options = dict(step.get("options") or {})
    if kind == "loft":
        groups = []
        for spec in step.get("refs") or []:
            groups.append(len(_refs(self, [spec], where)))
        options["groups"] = groups
    if "remove" in step:
        options["cells"] = [
            [_body(self, r["step"], where).Name, [float(c) for c in r["at"]]]
            for r in step["remove"]
        ]
    if "cells" in step:
        options["cells"] = [[float(c) for c in p] for p in step["cells"]]
    if "bodies" in step:
        options["bodies"] = [_body(self, name, where) for name in step["bodies"]]
    if "target" in step:
        options["target"] = _body(self, step["target"], where)
    if kind == "trim" and not refs["refs2"]:
        # the dialog lists the other surfaces the tool cuts (TrimPanel._candidates)
        refs["refs2"] = [
            (_body(self, r["step"], where), "")
            for r in step.get("remove") or []
            if _body(self, r["step"], where) not in [o for o, _s in refs["refs"]]
        ]
    try:
        feature = surface.build(kind, refs, options, name=step["id"])
    except core.SurfaceError as exc:
        raise BuildError("%s: %s" % (where, exc))
    self.objects[step["id"]] = feature
    self.ops[step["id"]] = "sf_surface"
    _finish(self, step, feature, where)
    if feature.Shape.isNull() or not bodies.alive(feature):
        raise BuildError("%s: no shape" % where)
    return feature


def op_sf_surface_edit(self, step):
    from sciforge import surface
    from sciforge import surface_core as core

    where = "sf_surface_edit %r" % step["target"]
    target = self.objects.get(step["target"])
    if target is None or self.ops.get(step["target"]) != "sf_surface":
        raise BuildError("%s: not a sf_surface step" % where)
    kind, refs, options = surface.read(target)
    options.update(step["set"])
    try:
        feature = surface.build(kind, refs, options, target)
    except core.SurfaceError as exc:
        raise BuildError("%s: %s" % (where, exc))
    self.objects[step["target"]] = feature
    return _finish(self, step, feature, where)


Builder.op_sf_surface = op_sf_surface
Builder.op_sf_surface_edit = op_sf_surface_edit
