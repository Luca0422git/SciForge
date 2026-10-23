# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Sketch > Project / Include > Isoparametric Curve (March 2026), no Qt: the U or V
curves of a face of the part, one at a distance from the face's edge or several spread
evenly across it, as 3D curves that follow the face when the design changes.

A U curve keeps the face's U parameter fixed (FreeCAD's Surface.uIso), a V curve its V. One
curve sits `Distance` from the face's first edge across the curves (measured along the
face, the middle of its other direction); Distributed puts `Count` curves at even steps of
the face's parameter. Each curve is cut to the face (a trimmed face keeps only the pieces
on it).

Fusion keeps them in the sketch as projected (associative) geometry. FreeCAD's sketches are
flat, so SciForge keeps them, like Project to Surface's curves, in a companion object of
the sketch (sketch_companions.py, the kind of Project to Surface's "Projected Curves": drawn,
hidden, listed and deleted with the sketch, shown in the projected purple).
"""

import FreeCAD as App

from . import log, warn
from . import surface_core as core

DIRECTIONS = ("U", "V")
MODES = ("Single", "Distributed")
SAMPLES = 256  # points along the face where a distance is measured


def _face_of(obj, sub):
    try:
        face = obj.Shape.getElement(sub)
    except Exception:
        face = None
    if face is None or face.isNull() or face.ShapeType != "Face":
        raise core.SurfaceError(
            "The face of these isoparametric curves is gone. Delete them and pick the face "
            "again."
        )
    return face


def ranges(face, direction):
    """(across, along): the parameter range the curves are spread over and the one each
    curve runs over. U curves (U fixed) are spread over U and run along V."""
    u0, u1, v0, v1 = face.ParameterRange
    return ((u0, u1), (v0, v1)) if direction == "U" else ((v0, v1), (u0, u1))


def _point(face, direction, across, along):
    surface = face.Surface
    return surface.value(across, along) if direction == "U" else surface.value(along, across)


def lengths(face, direction, samples=SAMPLES):
    """Cumulative lengths (mm) across the face, along its middle, at `samples` + 1 even
    steps of the parameter the curves are spread over."""
    (a, b), (c, d) = ranges(face, direction)
    middle = 0.5 * (c + d)
    out = [0.0]
    last = _point(face, direction, a, middle)
    for i in range(1, samples + 1):
        here = _point(face, direction, a + (b - a) * i / float(samples), middle)
        out.append(out[-1] + (here - last).Length)
        last = here
    return out


def fraction_of_point(face, direction, point):
    """Where a point on the face lies across it (0 .. 1 of the parameter range)."""
    u, v = face.Surface.parameter(App.Vector(point))
    (a, b), _along = ranges(face, direction)
    value = u if direction == "U" else v
    return core.clamp_fraction((value - a) / (b - a) if abs(b - a) > 1e-12 else 0.0)


def distance_of_point(face, direction, point):
    """The distance (mm, along the face) from its first edge to where `point` lies."""
    return core.length_at_fraction(
        lengths(face, direction), fraction_of_point(face, direction, point)
    )


def fractions(face, direction, mode, distance=0.0, count=1):
    if mode == "Single":
        return [core.fraction_at_length(lengths(face, direction), float(distance))]
    return core.iso_fractions(int(count))


def iso_edges(face, direction, values):
    """The curves of `face` at parameter fractions `values`, each cut to the face."""
    (a, b), (c, d) = ranges(face, direction)
    surface = face.Surface
    edges = []
    for f in values:
        param = a + (b - a) * float(f)
        try:
            curve = surface.uIso(param) if direction == "U" else surface.vIso(param)
            edge = curve.toShape(c, d)
        except Exception as exc:
            raise core.SurfaceError("This face has no %s curve there (%s)." % (direction, exc))
        pieces = []
        try:
            pieces = list(edge.common(face).Edges)
        except Exception:
            pieces = []
        if not pieces:  # a face that is its whole parameter rectangle: the curve as it is
            if face.isInside(
                edge.valueAt(0.5 * (edge.FirstParameter + edge.LastParameter)), 1e-6, True
            ):
                pieces = [edge]
        edges.extend(p for p in pieces if p.Length > 1e-7)
    if not edges:
        raise core.SurfaceError("No curve lands on the face there. Pick another place or face.")
    return edges


class IsoparametricCurves:
    """FeaturePython proxy (saved as "sciforge.surface_iso.IsoparametricCurves": keep it)."""

    def __init__(self, obj):
        obj.Proxy = self
        self.setup(obj)

    def setup(self, obj):
        def add(kind, name, doc):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, "Isoparametric Curve", doc)
                return True
            return False

        add("App::PropertyLinkSubGlobal", "Face", "The face whose curves these are")
        if add("App::PropertyEnumeration", "Direction", "U curves or V curves"):
            obj.Direction = list(DIRECTIONS)
        if add("App::PropertyEnumeration", "Mode", "One curve, or several spread evenly"):
            obj.Mode = list(MODES)
        add("App::PropertyLength", "Distance", "Single: from the face's first edge")
        if add("App::PropertyInteger", "Count", "Distributed: how many curves"):
            obj.Count = 3
        try:
            obj.setEditorMode("Placement", 2)
        except Exception:
            pass

    def onDocumentRestored(self, obj):
        self.setup(obj)

    def dumps(self):
        return None

    def loads(self, state):
        return None

    def execute(self, obj):
        import Part

        link = obj.Face
        if not link or link[0] is None or not link[1]:
            raise core.SurfaceError("Pick the face of the isoparametric curves.")
        face = _face_of(link[0], link[1][0])
        values = fractions(face, obj.Direction, obj.Mode, obj.Distance.Value, obj.Count)
        obj.Shape = Part.makeCompound(iso_edges(face, obj.Direction, values))


class ViewIsoparametricCurves:
    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        from . import ui_icon_path

        return ui_icon_path("isocurve")

    def dumps(self):
        return None

    def loads(self, state):
        return None


def make(sketch, face_ref, direction="U", mode="Single", distance=0.0, count=3):
    """An "Isoparametric Curves" companion of `sketch` on face_ref (object, "FaceN").
    Raises SurfaceError with the reason (nothing is left behind)."""
    from . import components, sketch_companions

    face = _face_of(*face_ref)
    iso_edges(face, direction, fractions(face, direction, mode, distance, count))  # checks
    doc = sketch.Document
    obj = doc.addObject("Part::FeaturePython", "IsoparametricCurves")
    IsoparametricCurves(obj)
    # Fusion keeps them as projected geometry of the sketch
    sketch_companions.adopt(obj, sketch, "ProjectedCurves")
    if App.GuiUp:
        try:
            ViewIsoparametricCurves(obj.ViewObject)
            obj.ViewObject.LineColor = (0.75, 0.52, 0.99)  # projected purple
            obj.ViewObject.LineWidth = 2.0
        except Exception as exc:
            warn("Isoparametric Curve: %s" % exc)
    obj.Label = "Isoparametric Curves"
    obj.Face = (face_ref[0], [face_ref[1]])
    obj.Direction = direction
    obj.Mode = mode
    obj.Distance = float(distance)
    obj.Count = int(count)
    try:
        component = components.container_of(sketch)
        if component is not None:
            component.addObject(obj)
    except Exception as exc:
        warn("Isoparametric Curve: %s" % exc)
    obj.recompute()
    if "Invalid" in obj.State or obj.Shape.isNull() or not obj.Shape.Edges:
        doc.removeObject(obj.Name)
        raise core.SurfaceError("No curve lands on the face there.")
    log(
        "Isoparametric Curve: %d %s curve(s) on %s"
        % (len(obj.Shape.Edges), direction, face_ref[0].Label)
    )
    return obj


def is_iso(obj):
    return isinstance(getattr(obj, "Proxy", None), IsoparametricCurves)
