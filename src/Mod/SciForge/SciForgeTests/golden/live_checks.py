# SPDX-License-Identifier: LGPL-2.1-or-later
"""The golden models' check of Fillet's and Chamfer's live picture (needs FreeCAD).

live_blend_expect {"target": step id, "tol": mm, "sizes": {...}}: the picture the dialog draws
while a size arrow is dragged (sciforge/fillet_live.py) for the step's picks and sizes, every
point of it compared with the exact result the step built: no point may be farther than `tol`
(default 0.005 mm) from the result's faces. `sizes` (optional) first changes the step's
sizes ({"radius": 3} on its first set, {"sets": [{"radius": 2}, ...]}) and rebuilds it, so
the check also runs at a size the step was not made with.
"""

import FreeCAD as App

from .builder import Builder, BuildError


def _resize(feature, sizes):
    """Change the step's sizes and rebuild it."""
    from sciforge import blend, fillet_sets

    if fillet_sets.is_sets(feature):
        base, spec, flat, refs2, features, features2 = fillet_sets.read(feature)
        rows = sizes.get("sets") or [sizes]
        for row, change in zip(spec["sets"], rows):
            row.update({k: v for k, v in change.items() if k != "sets"})
        fillet_sets.update(feature, base, spec, flat, refs2, features, features2)
    else:
        options = blend.read(feature)
        options.update(sizes)
        blend.apply(feature, options)
    feature.Document.recompute()


def op_live_blend_expect(self, step):
    import Part

    from sciforge import fillet_live

    feature = self.objects.get(step["target"])
    if feature is None:
        raise BuildError("live_blend_expect: unknown target %r" % step["target"])
    if step.get("sizes"):
        _resize(feature, step["sizes"])
    if "Invalid" in list(feature.State) or feature.Shape.isNull():
        raise BuildError("live_blend_expect: %s did not build" % feature.Label)
    picture, spec = fillet_live.picture_of(feature)
    points = picture.points(spec)
    if len(points) < int(step.get("min_points", 4)):
        raise BuildError("live_blend_expect: only %d points" % len(points))
    faces = Part.Compound(feature.Shape.Faces)
    tol = float(step.get("tol", 0.005))
    worst, where = 0.0, None
    for p in points:
        d = faces.distToShape(Part.Vertex(App.Vector(*p)))[0]
        if d > worst:
            worst, where = d, p
    if worst > tol:
        raise BuildError(
            "live_blend_expect: a point of the live picture is %.4f mm off the result (at %s), "
            "allowed %g" % (worst, ["%.3f" % c for c in where], tol)
        )
    return None


Builder.op_live_blend_expect = op_live_blend_expect
