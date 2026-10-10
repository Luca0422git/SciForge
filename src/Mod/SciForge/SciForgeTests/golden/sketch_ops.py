# SPDX-License-Identifier: LGPL-2.1-or-later
"""Golden-model steps for Fusion's sketch tools, built with the same SciForge code the
SKETCH tab uses (registered on builder.Builder when builder.py is imported).

  {"op": "sketch_polygon", "sketch": "s1", "center": [x, y], "point": [x, y],
   "sides": 6, "circumscribed": true, "diameter": 5.5, "name": "nut"}
      Circumscribed / Inscribed Polygon (sciforge/sketch_polygon.py): `point` is the
      middle of an edge (circumscribed) or a corner (inscribed); "diameter" dimensions
      the polygon's circle (across flats for circumscribed, across corners otherwise),
      named "<name>.diameter" for a later `edit`.

  {"op": "sketch_trim", "sketch": "s1", "points": [[x, y], ...]}
      Trim (T) clicked at each point in turn: the curve nearest the point loses the
      piece between its neighbouring intersections. Sketches FreeCAD's trim leaves
      invalid are repaired the way the SKETCH tab does (sciforge/sketch_fix.py).
"""

import FreeCAD as App
import Part
import Sketcher

from .builder import Builder, BuildError


def _sketch(builder, step):
    name = step["sketch"]
    sketch = builder.objects.get(name)
    if sketch is None or builder.ops.get(name) != "sketch":
        raise BuildError(
            "%s: 'sketch' must name an earlier sketch step, got %r" % (step["op"], name)
        )
    return sketch


def op_sketch_polygon(self, step):
    from sciforge import sketch_polygon

    sketch = _sketch(self, step)
    circumscribed = bool(step.get("circumscribed", True))
    center = App.Vector(step["center"][0], step["center"][1], 0)
    point = App.Vector(step["point"][0], step["point"][1], 0)
    ids = sketch_polygon.add_polygon(sketch, step["sides"], center, point, circumscribed)
    if "diameter" in step:
        # circumscribed: lines, inner circle, helper line, outer circle; inscribed: lines, circle
        circle = ids[step["sides"]] if circumscribed else ids[-1]
        index = sketch.addConstraint(
            Sketcher.Constraint("Diameter", circle, float(step["diameter"]))
        )
        if step.get("name"):
            sketch.renameConstraint(index, step["name"] + ".diameter")
    self.doc.recompute()
    if "Invalid" in list(sketch.State):
        raise BuildError("sketch_polygon made %r invalid" % step["sketch"])
    return sketch


def _nearest_curve(sketch, point):
    vertex = Part.Vertex(point)
    best = None
    for index, geometry in enumerate(sketch.Geometry):
        if sketch.getConstruction(index) or geometry.TypeId == "Part::GeomPoint":
            continue
        distance = geometry.toShape().distToShape(vertex)[0]
        if best is None or distance < best[1]:
            best = (index, distance)
    if best is None or best[1] > 1e-3:
        raise BuildError("sketch_trim: no curve at %s" % point)
    return best[0]


def op_sketch_trim(self, step):
    from sciforge import sketch_fix

    sketch = _sketch(self, step)
    for x, y in step["points"]:
        point = App.Vector(x, y, 0)
        index = _nearest_curve(sketch, point)
        try:
            sketch.trim(index, point)  # raises when FreeCAD cannot trim there
        except Exception as exc:
            raise BuildError("sketch_trim: FreeCAD could not trim at %s: %s" % (point, exc))
        sketch_fix.repair(sketch)
        sketch.solve()
    self.doc.recompute()
    if "Invalid" in list(sketch.State) or sketch.MalformedConstraints:
        raise BuildError(
            "sketch_trim left %r invalid: %s" % (step["sketch"], sketch.MalformedConstraints)
        )
    return sketch


Builder.op_sketch_polygon = op_sketch_polygon
Builder.op_sketch_trim = op_sketch_trim
