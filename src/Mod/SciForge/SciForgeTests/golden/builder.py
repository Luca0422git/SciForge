# SPDX-License-Identifier: LGPL-2.1-or-later
"""Builds a golden model's steps in a real FreeCAD document (needs FreeCAD).

Each step maps to the PartDesign feature a Fusion command corresponds to today.
As SciForge grows its own feature types (Press/Pull, Fusion-style Extrude ...)
this mapping is where the golden models switch over to them, so the same model
files keep measuring parity over time.

Conventions (documented for model authors in golden/README.md):
  * Sketch planes are the body's origin planes. In FreeCAD the sketch normal is
    +Z for XY, -Y for XZ and +X for YZ; sketch x/y map to (X,Y), (X,Z), (Y,Z).
  * Extrude "distance" goes along the sketch normal; "flip": true goes the
    other way. That holds for both join and cut.
  * Every feature gets Refine = True, because Fusion never leaves the extra
    seam faces FreeCAD keeps by default (face counts are compared exactly).
"""
import math

import FreeCAD as App
import Part
import Sketcher

from . import selectors


class BuildError(RuntimeError):
    """A step could not be built. The message names the step and the reason."""


_PLANE_ROLE = {"XY": "XY_Plane", "XZ": "XZ_Plane", "YZ": "YZ_Plane"}
_AXIS_ROLE = {"X": "X_Axis", "Y": "Y_Axis", "Z": "Z_Axis"}

# Step option name -> FreeCAD property name, per feature type, for "edit" steps.
_EDIT_PROPS = {
    "extrude": {"distance": "Length", "distance2": "Length2", "taper": "TaperAngle"},
    "revolve": {"angle": "Angle"},
    "fillet": {"radius": "Radius"},
    "chamfer": {"distance": "Size", "distance2": "Size2", "angle": "Angle"},
    "shell": {"thickness": "Value"},
    "hole": {"diameter": "Diameter", "depth": "Depth"},
    "press_pull": {"distance": "Distance"},
    "pattern_rect": {
        "count": "Occurrences",
        "spacing": "Offset",
        "count2": "Occurrences2",
        "spacing2": "Offset2",
    },
    "pattern_circ": {"count": "Occurrences", "angle": "Angle"},
}


class Builder:
    def __init__(self, doc):
        self.doc = doc
        self.body = doc.addObject("PartDesign::Body", "Body")
        self.objects = {}  # step id -> FreeCAD object
        self.ops = {}  # step id -> op name

    # -- helpers --------------------------------------------------------
    def _origin(self, role):
        for feature in self.body.Origin.OriginFeatures:
            if feature.Role == role:
                return feature
        raise BuildError("origin feature %s not found" % role)

    def _tip(self):
        tip = self.body.Tip
        if tip is None or tip.Shape.isNull():
            raise BuildError("there is no solid yet to pick edges or faces from")
        return tip

    def _recompute(self, step, obj):
        self.doc.recompute()
        state = list(getattr(obj, "State", []))
        if "Invalid" in state or "Error" in state or obj.Shape.isNull():
            raise BuildError(
                "step %r (%s) failed to compute: %s" % (step.get("id"), step["op"], state)
            )

    def _add(self, step, type_id, name=None):
        obj = self.body.newObject(type_id, name or step.get("id", step["op"]))
        if hasattr(obj, "Refine"):
            obj.Refine = True
        # body.newObject() does not move the Tip for pattern/mirror features
        # (FreeCAD's GUI commands do it separately). In Fusion a new feature
        # always becomes the end of the timeline, so make that explicit.
        self.body.Tip = obj
        self.objects[step["id"]] = obj
        self.ops[step["id"]] = step["op"]
        return obj

    def _features(self, step):
        return [self.objects[name] for name in step["features"]]

    # -- steps ----------------------------------------------------------
    def run(self, step):
        handler = getattr(self, "op_" + step["op"], None)
        if handler is None:
            raise BuildError("op %r is not implemented by the builder yet" % step["op"])
        return handler(step)

    def op_sketch(self, step):
        sketch = self.body.newObject("Sketcher::SketchObject", step["id"])
        sketch.AttachmentSupport = (self._origin(_PLANE_ROLE[step["plane"]]), [""])
        sketch.MapMode = "FlatFace"
        if step.get("offset"):
            sketch.AttachmentOffset = App.Placement(
                App.Vector(0, 0, step["offset"]), App.Rotation()
            )
        for i, item in enumerate(step["geometry"]):
            name = item.get("name", "g%d" % i)
            if "rect" in item:
                x0, y0, x1, y1 = item["rect"]
                _rect(sketch, name, min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
            elif "center_rect" in item:
                cx, cy, w, h = item["center_rect"]
                _center_rect(sketch, name, cx, cy, w, h)
            elif "circle" in item:
                _circle(sketch, name, *item["circle"])
            elif "polyline" in item:
                _polyline(sketch, item["polyline"])
            elif "polygon" in item:
                spec = item["polygon"]
                cx, cy = spec["center"]
                r, n = spec["radius"], spec["sides"]
                start = math.radians(spec.get("rotation", 0))
                pts = [
                    [
                        cx + r * math.cos(start + 2 * math.pi * k / n),
                        cy + r * math.sin(start + 2 * math.pi * k / n),
                    ]
                    for k in range(n)
                ]
                _polyline(sketch, pts)
            elif "slot" in item:
                _slot(sketch, *item["slot"])
        self.objects[step["id"]] = sketch
        self.ops[step["id"]] = "sketch"
        self.doc.recompute()
        if "Invalid" in list(sketch.State):
            raise BuildError("sketch %r is invalid (over-constrained or conflicting)" % step["id"])
        return sketch

    def op_extrude(self, step):
        """SciForge's Fusion-style Extrude (sciforge/extrude.py), as the E command builds it."""
        from sciforge import extrude

        if step.get("extent") == "through_all" and step.get("operation", "join") != "cut":
            raise BuildError("'through_all' is only supported for cut extrudes")
        distance = step.get("distance", 1.0)
        options = {
            "operation": step.get("operation", "join"),
            "direction": step.get("direction", "one_side"),
            "extent": "all" if step.get("extent") == "through_all" else "distance",
            "distance": -distance if step.get("flip") else distance,
            "distance2": step.get("distance2", distance),
            "taper": step.get("taper", 0.0),
        }
        try:
            feature = extrude.make(self.body, self.objects[step["profile"]], options, step["id"])
        except extrude.ExtrudeError as exc:
            raise BuildError("extrude %r: %s" % (step["id"], exc))
        self.objects[step["id"]] = feature
        self.ops[step["id"]] = "extrude"
        self._recompute(step, feature)
        return feature

    def op_revolve(self, step):
        operation = step.get("operation", "join")
        feature = self._add(
            step, "PartDesign::Groove" if operation == "cut" else "PartDesign::Revolution"
        )
        sketch = self.objects[step["profile"]]
        feature.Profile = sketch
        axis = step["axis"]
        if axis == "sketch_h":
            feature.ReferenceAxis = (sketch, ["H_Axis"])
        elif axis == "sketch_v":
            feature.ReferenceAxis = (sketch, ["V_Axis"])
        else:
            feature.ReferenceAxis = (self._origin(_AXIS_ROLE[axis]), [""])
        feature.Angle = step.get("angle", 360)
        self._recompute(step, feature)
        return feature

    def op_fillet(self, step):
        base = self._tip()
        edges = selectors.select(base.Shape, step["edges"], "edges")
        if not edges:
            raise BuildError("fillet %r: the edge selector picked nothing" % step["id"])
        feature = self._add(step, "PartDesign::Fillet")
        feature.Base = (base, edges)
        feature.Radius = step["radius"]
        self._recompute(step, feature)
        return feature

    def op_chamfer(self, step):
        base = self._tip()
        edges = selectors.select(base.Shape, step["edges"], "edges")
        if not edges:
            raise BuildError("chamfer %r: the edge selector picked nothing" % step["id"])
        feature = self._add(step, "PartDesign::Chamfer")
        feature.Base = (base, edges)
        if "angle" in step:
            feature.ChamferType = "Distance and Angle"
            feature.Angle = step["angle"]
        elif "distance2" in step:
            feature.ChamferType = "Two distances"
            feature.Size2 = step["distance2"]
        else:
            feature.ChamferType = "Equal distance"
        feature.Size = step["distance"]
        self._recompute(step, feature)
        return feature

    def op_shell(self, step):
        base = self._tip()
        faces = selectors.select(base.Shape, step["faces"], "faces")
        feature = self._add(step, "PartDesign::Thickness")
        feature.Base = (base, faces)
        feature.Value = step["thickness"]
        feature.Mode = "Skin"
        feature.Join = "Intersection"  # sharp inner corners, like Fusion's shell
        direction = step.get("direction", "inside")
        if direction not in ("inside", "outside"):
            raise BuildError("shell direction must be inside or outside")
        feature.Reversed = direction == "inside"
        self._recompute(step, feature)
        return feature

    def op_press_pull(self, step):
        """SciForge's Press/Pull, exactly as the Q command builds it."""
        from sciforge import presspull, presspull_core

        base = self._tip()
        if "faces" in step:
            names = selectors.select(base.Shape, step["faces"], "faces")
            obj = presspull.make(self.body, base, names, step["distance"], step["id"])
            self.objects[step["id"]] = obj
            self.ops[step["id"]] = "press_pull"
            self._recompute(step, obj)
            return obj
        if "edges" in step:  # Press Pull on edges = fillet with that radius
            fillet = self._add(dict(step, op="fillet"), "PartDesign::Fillet")
            self.ops[step["id"]] = "fillet"
            fillet.Base = (base, selectors.select(base.Shape, step["edges"], "edges"))
            fillet.Radius = step["distance"]
            self._recompute(step, fillet)
            return fillet
        # Press Pull on a fillet face = edit that fillet's radius
        names = selectors.select(base.Shape, step["fillet_face"], "faces")
        face = base.Shape.getElement(names[0])
        fillet = presspull_core.owning_fillet(self.body, face)
        if fillet is None:
            raise BuildError("press_pull %r: the face is not made by a fillet" % step["id"])
        fillet.Radius = step["distance"]
        self.objects[step["id"]] = fillet
        self.ops[step["id"]] = "fillet"
        self.doc.recompute()
        if "Invalid" in list(fillet.State):
            raise BuildError(
                "press_pull %r: fillet radius %g failed" % (step["id"], step["distance"])
            )
        return fillet

    def op_hole(self, step):
        feature = self._add(step, "PartDesign::Hole")
        feature.Profile = self.objects[step["sketch"]]
        feature.Diameter = step["diameter"]
        if step.get("through_all"):
            feature.DepthType = "ThroughAll"
        else:
            feature.DepthType = "Dimension"
            feature.Depth = step["depth"]
        feature.DrillPoint = "Flat"
        if "counterbore" in step:
            feature.HoleCutType = "Counterbore"
            feature.HoleCutCustomValues = True
            feature.HoleCutDiameter = step["counterbore"]["diameter"]
            feature.HoleCutDepth = step["counterbore"]["depth"]
        elif "countersink" in step:
            feature.HoleCutType = "Countersink"
            feature.HoleCutCustomValues = True
            feature.HoleCutDiameter = step["countersink"]["diameter"]
            feature.HoleCutCountersinkAngle = step["countersink"].get("angle", 90)
        self._recompute(step, feature)
        return feature

    def op_pattern_rect(self, step):
        feature = self._add(step, "PartDesign::LinearPattern")
        feature.Originals = self._features(step)
        feature.Direction = (self._origin(_AXIS_ROLE[step["direction"]]), [""])
        feature.Mode = "Spacing"
        feature.Offset = step["spacing"]
        feature.Occurrences = step["count"]
        if "direction2" in step:
            feature.Direction2 = (self._origin(_AXIS_ROLE[step["direction2"]]), [""])
            feature.Mode2 = "Spacing"
            feature.Offset2 = step["spacing2"]
            feature.Occurrences2 = step["count2"]
        self._recompute(step, feature)
        return feature

    def op_pattern_circ(self, step):
        feature = self._add(step, "PartDesign::PolarPattern")
        feature.Originals = self._features(step)
        feature.Axis = (self._origin(_AXIS_ROLE[step["axis"]]), [""])
        feature.Angle = step.get("angle", 360)
        feature.Occurrences = step["count"]
        self._recompute(step, feature)
        return feature

    def op_mirror(self, step):
        feature = self._add(step, "PartDesign::Mirrored")
        feature.Originals = self._features(step)
        feature.MirrorPlane = (self._origin(_PLANE_ROLE[step["plane"]]), [""])
        self._recompute(step, feature)
        return feature

    def op_edit(self, step):
        """Change an earlier step, like double-clicking it in Fusion's timeline."""
        target = self.objects[step["target"]]
        op = self.ops[step["target"]]
        if "constraint" in step:
            if op != "sketch":
                raise BuildError("edit %r: 'constraint' needs a sketch target" % step["target"])
            try:
                target.setDatum(step["constraint"], App.Units.Quantity("%r mm" % step["value"]))
            except Exception as exc:
                raise BuildError(
                    "edit %r: cannot set %s = %r: %s"
                    % (step["target"], step["constraint"], step["value"], exc)
                )
        for key, value in step.get("set", {}).items():
            prop = _EDIT_PROPS.get(op, {}).get(key)
            if prop is None:
                raise BuildError("edit %r: cannot set %r on a %s step" % (step["target"], key, op))
            setattr(target, prop, value)
        self.doc.recompute()
        broken = [o.Label for o in self.body.Group if "Invalid" in list(getattr(o, "State", []))]
        if broken:
            raise BuildError(
                "after editing %r these features broke: %s" % (step["target"], ", ".join(broken))
            )
        return target

    def shape(self):
        return self.body.Shape


# -- sketch geometry with Fusion-like dimensions --------------------------
def _v(x, y):
    return App.Vector(x, y, 0)


def _lines_closed(sketch, pts):
    first = sketch.GeometryCount
    n = len(pts)
    for i in range(n):
        sketch.addGeometry(Part.LineSegment(_v(*pts[i]), _v(*pts[(i + 1) % n])))
    sketch.addConstraint(
        [Sketcher.Constraint("Coincident", first + i, 2, first + (i + 1) % n, 1) for i in range(n)]
    )
    return first


def _named(sketch, constraint, name):
    index = sketch.addConstraint(constraint)
    sketch.renameConstraint(index, name)
    return index


def _rect(sketch, name, x0, y0, x1, y1):
    """Rectangle dimensioned like Fusion: <name>.width, <name>.height, and its
    corner located from the origin by <name>.x / <name>.y."""
    g = _lines_closed(sketch, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    sketch.addConstraint(
        [
            Sketcher.Constraint("Horizontal", g),
            Sketcher.Constraint("Horizontal", g + 2),
            Sketcher.Constraint("Vertical", g + 1),
            Sketcher.Constraint("Vertical", g + 3),
        ]
    )
    _named(sketch, Sketcher.Constraint("DistanceX", g, 1, g, 2, x1 - x0), name + ".width")
    _named(sketch, Sketcher.Constraint("DistanceY", g + 1, 1, g + 1, 2, y1 - y0), name + ".height")
    _named(sketch, Sketcher.Constraint("DistanceX", -1, 1, g, 1, x0), name + ".x")
    _named(sketch, Sketcher.Constraint("DistanceY", -1, 1, g, 1, y0), name + ".y")


def _center_rect(sketch, name, cx, cy, w, h):
    """Center rectangle: editing width/height keeps the centre fixed, as in Fusion."""
    x0, y0, x1, y1 = cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0
    g = _lines_closed(sketch, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    sketch.addConstraint(
        [
            Sketcher.Constraint("Horizontal", g),
            Sketcher.Constraint("Horizontal", g + 2),
            Sketcher.Constraint("Vertical", g + 1),
            Sketcher.Constraint("Vertical", g + 3),
        ]
    )
    center = sketch.addGeometry(Part.Point(_v(cx, cy)), True)
    sketch.addConstraint(Sketcher.Constraint("Symmetric", g, 1, g + 1, 2, center, 1))
    _named(sketch, Sketcher.Constraint("DistanceX", g, 1, g, 2, w), name + ".width")
    _named(sketch, Sketcher.Constraint("DistanceY", g + 1, 1, g + 1, 2, h), name + ".height")
    _named(sketch, Sketcher.Constraint("DistanceX", -1, 1, center, 1, cx), name + ".x")
    _named(sketch, Sketcher.Constraint("DistanceY", -1, 1, center, 1, cy), name + ".y")


def _circle(sketch, name, cx, cy, r):
    g = sketch.addGeometry(Part.Circle(_v(cx, cy), App.Vector(0, 0, 1), r))
    _named(sketch, Sketcher.Constraint("Diameter", g, 2.0 * r), name + ".diameter")
    _named(sketch, Sketcher.Constraint("DistanceX", -1, 1, g, 3, cx), name + ".x")
    _named(sketch, Sketcher.Constraint("DistanceY", -1, 1, g, 3, cy), name + ".y")


def _polyline(sketch, pts):
    _lines_closed(sketch, [tuple(p) for p in pts])


def _slot(sketch, x1, y1, x2, y2, width):
    """Straight slot between two centre points, as Fusion's centre-to-centre slot."""
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length < 1e-9:
        raise BuildError("slot needs two different centre points")
    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux
    r = width / 2.0
    theta = math.atan2(uy, ux)
    z = App.Vector(0, 0, 1)
    sketch.addGeometry(Part.LineSegment(_v(x1 + nx * r, y1 + ny * r), _v(x2 + nx * r, y2 + ny * r)))
    sketch.addGeometry(
        Part.ArcOfCircle(Part.Circle(_v(x2, y2), z, r), theta - math.pi / 2, theta + math.pi / 2)
    )
    sketch.addGeometry(Part.LineSegment(_v(x2 - nx * r, y2 - ny * r), _v(x1 - nx * r, y1 - ny * r)))
    sketch.addGeometry(
        Part.ArcOfCircle(
            Part.Circle(_v(x1, y1), z, r), theta + math.pi / 2, theta + 3 * math.pi / 2
        )
    )
