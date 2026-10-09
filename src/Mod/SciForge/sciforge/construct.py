# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Construct menu on top of PartDesign datums. No GUI code.

Each Fusion entry becomes a datum plane/axis/point attached to the selection
with the attachment mode that does what the entry says (FreeCAD's attacher
names differ). Midplane has no attacher mode, so it is computed: a plane on
the first face, offset to halfway to the second.
"""
# How many picks each preset needs before the datum can be made.
NEEDS = {
    "Midplane": 2,
    "PlaneTwoEdges": 2,
    "PlaneThreePoints": 3,
    "AxisTwoPlanes": 2,
    "AxisTwoPoints": 2,
    "PointTwoEdges": 2,
    "PointThreePlanes": 3,
    "PointEdgePlane": 2,
}
# Presets whose result is adjusted with a distance (offset along the normal) or an angle.
DISTANCE = {"OffsetPlane", "Midplane", "TangentPlane", "PerpendicularPlane", "PlaneAlongPath"}
ANGLE = {"PlaneAtAngle"}

# key -> (menu label, datum type, preferred attacher modes in order)
PRESETS = {
    "OffsetPlane": ("Offset Plane", "PartDesign::Plane", ["FlatFace", "ObjectXY"]),
    "PlaneAtAngle": ("Plane at Angle", "PartDesign::Plane", ["FlatFace", "ObjectXY"]),
    "TangentPlane": ("Tangent Plane", "PartDesign::Plane", ["TangentPlane"]),
    "Midplane": ("Midplane", "PartDesign::Plane", []),
    "PerpendicularPlane": ("Perpendicular Plane", "PartDesign::Plane", ["NormalToEdge"]),
    "PlaneTwoEdges": ("Plane Through Two Edges", "PartDesign::Plane", ["ThreePointsPlane"]),
    "PlaneThreePoints": ("Plane Through Three Points", "PartDesign::Plane", ["ThreePointsPlane"]),
    "PlaneAlongPath": ("Plane Along Path", "PartDesign::Plane", ["NormalToEdge", "FrenetNB"]),
    "AxisCylinder": ("Axis Through Cylinder/Cone/Torus", "PartDesign::Line", ["AxisOfCurvature"]),
    "AxisNormal": ("Axis Perpendicular to Face", "PartDesign::Line", ["FaceNormal", "Normal"]),
    "AxisTwoPlanes": ("Axis Through Two Planes", "PartDesign::Line", ["IntersectionLine"]),
    "AxisTwoPoints": ("Axis Through Two Points", "PartDesign::Line", ["TwoPointLine"]),
    "AxisEdge": ("Axis Through Edge", "PartDesign::Line", ["TwoPointLine", "ObjectX"]),
    "PointVertex": ("Point at Vertex", "PartDesign::Point", ["Vertex"]),
    "PointTwoEdges": ("Point Through Two Edges", "PartDesign::Point", ["ProximityPoint1"]),
    "PointThreePlanes": ("Point Through Three Planes", "PartDesign::Point", []),
    "PointCenter": (
        "Point at Center of Circle/Sphere/Torus",
        "PartDesign::Point",
        ["CenterOfCurvature", "CenterOfMass"],
    ),
    "PointEdgePlane": ("Point at Edge and Plane", "PartDesign::Point", ["ProximityPoint1"]),
    "PointAlongPath": ("Point Along Path", "PartDesign::Point", ["OnEdge"]),
}

_ENGINES = {
    "PartDesign::Plane": "Attacher::AttachEnginePlane",
    "PartDesign::Line": "Attacher::AttachEngineLine",
    "PartDesign::Point": "Attacher::AttachEnginePoint",
}


SHORT_NAMES = {
    "PartDesign::Plane": "Plane",
    "PartDesign::Line": "Axis",
    "PartDesign::Point": "Point",
}


class ConstructError(ValueError):
    pass


def pick_mode(type_id, refs, preferred):
    """The first preferred attacher mode that fits `refs`, else FreeCAD's best guess."""
    import Part

    engine = Part.AttachEngine(_ENGINES[type_id])
    engine.References = refs
    suggestion = engine.suggestModes()
    applicable = suggestion.get("allApplicableModes", [])
    for mode in preferred:
        if mode in applicable:
            return mode
    best = suggestion.get("bestFitMode", "")
    if best:
        return best
    raise ConstructError("This selection does not fit here. %s" % suggestion.get("message", ""))


def make(body, key, refs, offset=0.0):
    """New datum in `body` for preset `key`, attached to refs [(obj, "Face3"), ...]."""
    label, type_id, preferred = PRESETS[key]
    if key == "Midplane":
        return _midplane(body, refs)
    if not refs:
        raise ConstructError("Select the geometry for %s first." % label)
    if key in ("AxisCylinder", "PointCenter"):
        refs = _round_face_to_edge(refs)
    mode = pick_mode(type_id, refs, preferred)
    datum = body.newObject(type_id, key)
    datum.AttachmentSupport = refs
    datum.MapMode = mode
    if offset:
        import FreeCAD as App

        datum.AttachmentOffset = App.Placement(App.Vector(0, 0, offset), App.Rotation())
    datum.Label = SHORT_NAMES[type_id]  # Fusion: Plane1, Axis1, Point1
    return datum


def _round_face_to_edge(refs):
    """FreeCAD's AxisOfCurvature/CenterOfCurvature want a round edge; Fusion lets you
    click the round face. Use the face's first circular edge instead (same axis)."""
    out = []
    for obj, sub in refs:
        if sub.startswith("Face"):
            face = obj.Shape.getElement(sub)
            if type(face.Surface).__name__ in ("Cylinder", "Cone", "Toroid", "Sphere"):
                for i, edge in enumerate(obj.Shape.Edges, start=1):
                    if type(edge.Curve).__name__ == "Circle" and any(
                        edge.isSame(e) for e in face.Edges
                    ):
                        sub = "Edge%d" % i
                        break
        out.append((obj, sub))
    return out


def _midplane(body, refs):
    faces = [(obj, sub) for obj, sub in refs if sub.startswith("Face")]
    if len(faces) != 2:
        raise ConstructError("Midplane needs two faces.")
    (obj1, sub1), (obj2, sub2) = faces
    f1 = obj1.Shape.getElement(sub1)
    f2 = obj2.Shape.getElement(sub2)
    if type(f1.Surface).__name__ != "Plane" or type(f2.Surface).__name__ != "Plane":
        raise ConstructError("Midplane needs two flat faces.")
    u0, u1, v0, v1 = f1.ParameterRange
    normal = f1.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
    distance = (f2.CenterOfMass - f1.CenterOfMass).dot(normal)
    import FreeCAD as App

    datum = body.newObject("PartDesign::Plane", "Midplane")
    datum.AttachmentSupport = [(obj1, sub1)]
    datum.MapMode = "FlatFace"
    datum.AttachmentOffset = App.Placement(App.Vector(0, 0, distance / 2.0), App.Rotation())
    datum.Label = "Midplane"
    return datum
