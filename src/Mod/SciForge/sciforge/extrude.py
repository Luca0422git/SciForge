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
The profile is a sketch, or a planar face of the body given as (feature, "FaceN"),
like picking a face in Fusion's Extrude.
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


def _profile_value(profile):
    """Value for the Pad/Pocket Profile property: a sketch, or (feature, ["FaceN"])."""
    if isinstance(profile, tuple):
        obj, sub = profile
        return (obj, [sub] if isinstance(sub, str) else list(sub))
    return profile


def profile_of(feature):
    """The profile of an existing Pad/Pocket, in the form make() takes."""
    value = feature.Profile
    if isinstance(value, tuple):
        obj, subs = value[0], list(value[1]) if len(value) > 1 else []
        subs = [s for s in subs if s]
        if subs and obj.TypeId != "Sketcher::SketchObject":
            return (obj, subs[0])
        return obj
    return value


def profile_frame(profile):
    """(center, outward normal) of a profile: sketch plane normal, or the face normal."""
    if isinstance(profile, tuple):
        obj, sub = profile
        face = obj.Shape.getElement(sub if isinstance(sub, str) else sub[0])
        u0, u1, v0, v1 = face.ParameterRange
        normal = face.normalAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)
        if face.Orientation == "Reversed":
            normal = normal * -1
        return face.CenterOfMass, normal
    placement = profile.getGlobalPlacement()
    return profile.Shape.BoundBox.Center, placement.Rotation.multVec(App.Vector(0, 0, 1))


def profile_label(profile):
    if isinstance(profile, tuple):
        return "%s face" % profile[0].Label
    return profile.Label


def make(body, sketch, options, name="Extrude"):
    """New Pad/Pocket in `body` with Fusion-style options. `sketch` is the profile:
    a sketch or (feature, "FaceN")."""
    operation = options.get("operation", "join")
    if operation not in OPERATIONS:
        raise ExtrudeError("unknown operation %r" % operation)
    if operation == "new_body" and body.Tip is not None and not body.Tip.Shape.isNull():
        raise ExtrudeError(
            "'New Body' after the first solid is not available yet; use Join or Cut."
        )
    if isinstance(sketch, tuple):
        face = sketch[0].Shape.getElement(sketch[1])
        if face.Surface.TypeId != "Part::GeomPlane":
            raise ExtrudeError("Only flat faces can be extruded; pick a planar face or a sketch.")
    feature = body.newObject(feature_type(operation), name)
    feature.Profile = _profile_value(sketch)
    apply(feature, options)
    body.Tip = feature
    if App.GuiUp and not isinstance(sketch, tuple):
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
    sketch = profile_of(feature)
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
        center, normal = profile_frame(sketch)
        step = 0.01 if distance >= 0 else -0.01
        probe = center + normal * step
        return base_shape.isInside(probe, 1e-7, True)
    except Exception:
        return False
