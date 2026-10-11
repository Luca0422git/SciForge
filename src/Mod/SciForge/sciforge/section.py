# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Section Analysis, the document side (no Qt): the analysis object and the cut maths.

A section analysis is an App::FeaturePython ("Section1"...) with SciForgeType
"SectionAnalysis", so the browser lists it in its Analysis folder (with an eye) and the
timeline leaves it out, as Fusion does. It keeps what the dialog set: the plane or flat face
it starts from (Plane), Distance, X Angle / Y Angle, Flip, Section Color (From Body /
Custom) and Show Hatch. Every recompute works out the cut (CutPlacement: origin on the cut,
local Z pointing at the side that is cut away), so the analysis follows the model.

Nothing about the bodies is changed: section_ui.py clips their display and draws the cut
faces (the "caps") from cap_faces(). Saved documents store "sciforge.section.SectionAnalysis":
keep the name stable.
"""
try:
    import FreeCAD as App

    V = App.Vector
except ImportError:
    App = V = None

from . import labels  # noqa: E402

KIND = "SectionAnalysis"
COLOR_MODES = ["From Body", "Custom"]


class SectionError(ValueError):
    pass


def is_section(obj):
    try:
        return getattr(obj, "SciForgeType", "") == KIND and obj.isAttachedToDocument()
    except Exception:
        return False


def sections(doc):
    return [o for o in doc.Objects if is_section(o)]


def base_frame(ref, pivot=(0.0, 0.0)):
    """The picked plane's frame, its origin moved within the plane to `pivot` (u, v): where
    the cut turns about and the handles sit (the middle of the part when it was picked)."""
    from . import construct

    try:
        base = construct.plane_frame(ref)
    except construct.ConstructError as exc:
        raise SectionError(str(exc))
    u, v = float(pivot[0]), float(pivot[1])
    return base.multiply(App.Placement(V(u, v, 0), App.Rotation()))


def pivot_for(ref, shapes):
    """(u, v) in the picked plane of the middle of `shapes` (global solids)."""
    from . import construct

    box = None
    for shape in shapes:
        if shape is None or shape.isNull():
            continue
        box = shape.BoundBox if box is None else box.united(shape.BoundBox)
    if box is None:
        return (0.0, 0.0)
    try:
        base = construct.plane_frame(ref)
    except construct.ConstructError:
        return (0.0, 0.0)
    local = base.inverse().multVec(box.Center)
    return (local.x, local.y)


def cut_frame(ref, distance=0.0, x_angle=0.0, y_angle=0.0, flip=False, pivot=(0.0, 0.0)):
    """Placement of the cut: from the plane or flat face `ref` (its outward normal is local
    Z, its origin at `pivot`), moved `distance` along it, turned about its X then Y axis, Z
    reversed when flipped. The side local Z points at is cut away."""
    base = base_frame(ref, pivot)
    place = base.multiply(App.Placement(V(0, 0, float(distance)), App.Rotation()))
    place = place.multiply(App.Placement(V(), App.Rotation(V(1, 0, 0), float(x_angle))))
    place = place.multiply(App.Placement(V(), App.Rotation(V(0, 1, 0), float(y_angle))))
    if flip:
        place = place.multiply(App.Placement(V(), App.Rotation(V(1, 0, 0), 180.0)))
    return place


def normal_of(place):
    n = place.Rotation.multVec(V(0, 0, 1))
    n.normalize()
    return n


def clipped_objects(doc):
    """What a section cuts: bodies and loose solids (not sketches or construction)."""
    found = []
    for obj in doc.Objects:
        try:
            if obj.TypeId == "PartDesign::Body":
                found.append(obj)
                continue
            if obj.getParentGeoFeatureGroup() is not None:
                continue
            if getattr(obj, "SciForgeType", ""):
                continue
            if not obj.isDerivedFrom("Part::Feature"):
                continue
            shape = obj.Shape
            if not shape.isNull() and shape.Solids:
                found.append(obj)
        except Exception:
            continue
    return found


def _big_face(place, box):
    """A square on the cut plane, larger than the box."""
    import Part

    n = normal_of(place)
    x = place.Rotation.multVec(V(1, 0, 0))
    size = 2.0 * box.DiagonalLength + (box.Center - place.Base).Length + 10.0
    corner = place.Base - x * size - n.cross(x) * size
    return Part.makePlane(2 * size, 2 * size, corner, n, x)


def cap_faces(shape, place):
    """The faces where the cut plane passes through `shape` (global), [] if it misses."""
    if shape is None or shape.isNull() or not shape.Solids:
        return []
    try:
        common = shape.common(_big_face(place, shape.BoundBox))
    except Exception:
        return []
    return [f for f in common.Faces if f.Area > 1e-9]


def hatch_lines(faces, place, spacing):
    """Diagonal hatch lines inside the cap faces: [(a, b)] segments."""
    import Part

    if not faces or spacing <= 0:
        return []
    x = place.Rotation.multVec(V(1, 0, 0))
    n = normal_of(place)
    y = n.cross(x)
    d = x + y
    d.normalize()
    across = n.cross(d)
    out = []
    for face in faces:
        box = face.BoundBox
        reach = box.DiagonalLength + 1.0
        centre = box.Center
        count = int(reach * 2 / spacing) + 1
        lines = []
        for i in range(count):
            offset = -reach + i * spacing
            mid = centre + across * offset
            lines.append(Part.LineSegment(mid - d * reach, mid + d * reach).toShape())
        if not lines:
            continue
        try:
            inside = face.common(Part.Compound(lines))
        except Exception:
            continue
        for edge in inside.Edges:
            out.append((edge.valueAt(edge.FirstParameter), edge.valueAt(edge.LastParameter)))
    return out


# -- the analysis object ------------------------------------------------------------------------
class SectionAnalysis:
    """Proxy of a section analysis (see the module text)."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        props = obj.PropertiesList
        add = [
            ("App::PropertyString", "SciForgeType", "SciForge", "Kind of SciForge object"),
            ("App::PropertyLinkSubGlobal", "Plane", "Section", "Plane or flat face"),
            ("App::PropertyDistance", "Distance", "Section", "Offset along the plane"),
            ("App::PropertyAngle", "XAngle", "Section", "Turn about the plane's X axis"),
            ("App::PropertyAngle", "YAngle", "Section", "Turn about the plane's Y axis"),
            ("App::PropertyBool", "Flip", "Section", "Cut away the other side"),
            ("App::PropertyEnumeration", "SectionColor", "Section", "Colour of the cut"),
            ("App::PropertyColor", "CustomColor", "Section", "Colour when Custom"),
            ("App::PropertyBool", "ShowHatch", "Section", "Diagonal lines on the cut"),
            ("App::PropertyFloat", "PivotU", "Section", "Where in the plane the cut turns (u)"),
            ("App::PropertyFloat", "PivotV", "Section", "Where in the plane the cut turns (v)"),
            ("App::PropertyPlacement", "CutPlacement", "Section", "The cut (worked out)"),
            ("App::PropertyString", "Problem", "Section", "Why the cut stays where it was"),
        ]
        for kind, name, group, doc in add:
            if name not in props:
                obj.addProperty(kind, name, group, doc)
                if name == "SectionColor":
                    obj.SectionColor = COLOR_MODES
                elif name == "ShowHatch":
                    obj.ShowHatch = True
                elif name == "CustomColor":
                    obj.CustomColor = (0.85, 0.35, 0.30)
        obj.SciForgeType = KIND
        try:
            obj.setEditorMode("CutPlacement", 1)
            obj.setEditorMode("SciForgeType", 2)
            obj.setPropertyStatus("Problem", ["Output", "Hidden"])
        except Exception:
            pass

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        """Work the cut out again. When the plane or face it was made on is gone (deleted,
        or changed by an edit) the cut stays where it was and Problem says why: it never
        fails (a failed analysis printed errors after every later change)."""
        try:
            place = cut_of(obj)
        except Exception as exc:
            text = str(exc) or GONE
            if obj.Problem != text:
                obj.Problem = text
            return
        if obj.Problem:
            obj.Problem = ""
        if not obj.CutPlacement.isSame(place, 1e-12):
            obj.CutPlacement = place

    def allowDuplicateLabel(self, obj):
        """Yes only while SciForge sets the label it worked out (see labels.py)."""
        return labels.allow_duplicate()

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


GONE = "The plane or face of this section is gone. Edit it and pick one."


def cut_of(obj):
    """The cut placement of a section analysis from its stored plane and values."""
    from . import construct

    link = obj.Plane
    if not link:
        raise SectionError(GONE)
    target, subs = link if isinstance(link, tuple) else (link, [""])
    if not construct.alive(target):
        raise SectionError(GONE)
    sub = (subs[0] if isinstance(subs, (list, tuple)) and subs else subs) or ""
    ref = construct.normalize_pick(target, sub)
    return cut_frame(
        ref,
        obj.Distance.Value,
        obj.XAngle.Value,
        obj.YAngle.Value,
        obj.Flip,
        (obj.PivotU, obj.PivotV),
    )


def problem(obj):
    """Why a section analysis keeps its old cut, or ''."""
    return getattr(obj, "Problem", "") or ""


def next_label(doc, base="Section"):
    import re

    used = 0
    for obj in doc.Objects:
        match = re.match(r"^%s(\d+)$" % base, obj.Label or "")
        if match:
            used = max(used, int(match.group(1)))
    return "%s%d" % (base, used + 1)


def make(doc, ref, options=None):
    """A new section analysis on `ref` (plane object, "" or feature, "FaceN")."""
    obj = doc.addObject("App::FeaturePython", "Section")
    SectionAnalysis(obj)
    labels.set_exact(obj, next_label(doc))
    update(obj, ref, options)
    return obj


def update(obj, ref, options=None):
    options = options or {}
    from . import construct

    target, sub = construct.normalize_pick(ref[0], ref[1])
    link = (target, [sub] if sub else [""])
    current = obj.Plane
    if not current or current[0] is not target or list(current[1] or [""]) != link[1]:
        obj.Plane = link
    for prop, key in (("Distance", "distance"), ("XAngle", "x_angle"), ("YAngle", "y_angle")):
        if key in options:
            value = float(options[key])
            if abs(getattr(obj, prop).Value - value) > 1e-12:
                setattr(obj, prop, value)
    if "flip" in options and bool(obj.Flip) != bool(options["flip"]):
        obj.Flip = bool(options["flip"])
    if "color_mode" in options and obj.SectionColor != options["color_mode"]:
        obj.SectionColor = options["color_mode"]
    if "color" in options:
        obj.CustomColor = tuple(options["color"])[:3]
    if "hatch" in options and bool(obj.ShowHatch) != bool(options["hatch"]):
        obj.ShowHatch = bool(options["hatch"])
    if "pivot" in options:
        u, v = (float(x) for x in options["pivot"])
        if abs(obj.PivotU - u) > 1e-12 or abs(obj.PivotV - v) > 1e-12:
            obj.PivotU, obj.PivotV = u, v
    obj.touch()
    return obj


def read(obj):
    """(ref, options) of a section analysis, for its dialog."""
    link = obj.Plane
    ref = None
    if link:
        target, subs = link
        sub = (subs[0] if isinstance(subs, (list, tuple)) and subs else subs) or ""
        ref = (target, sub)
    color = tuple(obj.CustomColor)[:3]
    options = {
        "distance": obj.Distance.Value,
        "x_angle": obj.XAngle.Value,
        "y_angle": obj.YAngle.Value,
        "flip": bool(obj.Flip),
        "color_mode": obj.SectionColor,
        "color": color,
        "hatch": bool(obj.ShowHatch),
        "pivot": (obj.PivotU, obj.PivotV),
    }
    return ref, options


def kept_volume(shape, place):
    """Volume of `shape` on the kept side of the cut (the side local Z points away from):
    what the section shows of the part (the scenarios check it)."""
    import Part

    box = shape.BoundBox
    size = 2.0 * box.DiagonalLength + (box.Center - place.Base).Length + 10.0
    half = Part.makeBox(2 * size, 2 * size, 2 * size)
    half.Placement = place.multiply(App.Placement(V(-size, -size, -2 * size), App.Rotation()))
    return shape.common(half).Volume
