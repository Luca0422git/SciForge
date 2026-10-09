# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion-style Extrude on top of PartDesign Pad (join) and Pocket (cut). No GUI code.

One set of options, like Fusion's dialog:
  direction  "one_side" | "two_sides" | "symmetric"
  extent     "distance" | "all"
  distance   mm along the sketch normal; negative goes the other way
  distance2  second side (two_sides)
  taper      degrees
  operation  "join" | "cut" | "new_body"
Switching join <-> cut swaps the underlying Pad/Pocket, keeping the options.
Used by the Extrude command and by the golden-model builder, so both behave the same.
"""
import FreeCAD as App

OPERATIONS = ("join", "cut", "new_body")
DIRECTIONS = ("one_side", "two_sides", "symmetric")
EXTENTS = ("distance", "all")


class ExtrudeError(ValueError):
    pass


def feature_type(operation):
    return "PartDesign::Pocket" if operation == "cut" else "PartDesign::Pad"


def apply(feature, options):
    """Write the options onto an existing Pad/Pocket."""
    cut = feature.TypeId == "PartDesign::Pocket"
    distance = float(options.get("distance", 10.0))
    extent = options.get("extent", "distance")
    if extent == "all":
        feature.Type = "ThroughAll" if cut else "UpToLast"
    else:
        feature.Type = "Length"
        feature.Length = max(abs(distance), 1e-4)
    direction = options.get("direction", "one_side")
    if direction == "symmetric":
        feature.SideType = "Symmetric"
    elif direction == "two_sides":
        feature.SideType = "Two sides"
        feature.Type2 = "Length"
        feature.Length2 = max(abs(float(options.get("distance2", distance))), 1e-4)
    else:
        feature.SideType = "One side"
    feature.TaperAngle = float(options.get("taper", 0.0))
    along_normal = distance >= 0
    # A Pocket cuts against the sketch normal unless Reversed.
    feature.Reversed = along_normal if cut else not along_normal
    if hasattr(feature, "Refine"):
        feature.Refine = True


def make(body, sketch, options, name="Extrude"):
    """New Pad/Pocket for `sketch` in `body` with Fusion-style options."""
    operation = options.get("operation", "join")
    if operation not in OPERATIONS:
        raise ExtrudeError("unknown operation %r" % operation)
    if operation == "new_body" and body.Tip is not None and not body.Tip.Shape.isNull():
        raise ExtrudeError(
            "'New Body' after the first solid is not available yet; use Join or Cut."
        )
    feature = body.newObject(feature_type(operation), name)
    feature.Profile = sketch
    apply(feature, options)
    body.Tip = feature
    if App.GuiUp:
        try:
            sketch.ViewObject.Visibility = False
        except Exception:
            pass
    return feature


def switch(body, feature, options):
    """Replace a Pad by a Pocket or back when the operation changes. Returns the new feature."""
    wanted = feature_type(options.get("operation", "join"))
    if feature.TypeId == wanted:
        apply(feature, options)
        return feature
    sketch = feature.Profile[0] if isinstance(feature.Profile, tuple) else feature.Profile
    label = feature.Label
    doc = feature.Document
    body.removeObject(feature)
    doc.removeObject(feature.Name)
    new = make(body, sketch, options, "Extrude")
    new.Label = label
    return new


def goes_into_material(base_shape, sketch, distance):
    """True if extruding the sketch by `distance` starts inside existing material,
    which is when Fusion switches the operation to Cut on its own."""
    if base_shape is None or base_shape.isNull() or not base_shape.Solids:
        return False
    try:
        placement = sketch.getGlobalPlacement()
        normal = placement.Rotation.multVec(App.Vector(0, 0, 1))
        center = sketch.Shape.BoundBox.Center
        step = 0.01 if distance >= 0 else -0.01
        probe = center + normal * step
        return base_shape.isInside(probe, 1e-7, True)
    except Exception:
        return False
