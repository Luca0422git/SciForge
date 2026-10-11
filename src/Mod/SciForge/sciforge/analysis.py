# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Center of Mass and Interference, the document side (no Qt): the maths and the
analysis objects the browser lists in its Analysis folder (SciForgeType ...Analysis, left out
of the timeline). Both follow the model: every recompute measures the picked bodies again.

  CenterOfMassAnalysis  Bodies (picked; none = every visible body), Position (worked out),
                        Volume. The mass centre assumes one material for every body (the
                        volume centroid), see docs/sciforge/parity/inspect.md.
  InterferenceAnalysis  Bodies (two or more), IncludeCoincident (also report bodies that
                        only touch), Results ("label 1|label 2|volume" per pair) and Overlap
                        (the overlapping solids, drawn red by the view provider).

Saved documents store "sciforge.analysis.CenterOfMassAnalysis" / "...InterferenceAnalysis":
keep the names stable.
"""
try:
    import FreeCAD as App

    V = App.Vector
except ImportError:
    App = V = None

COM_KIND = "CenterOfMassAnalysis"
INTERFERENCE_KIND = "InterferenceAnalysis"
VOLUME_EPS = 1e-6  # mm^3: less than this does not count as an overlap


class AnalysisError(ValueError):
    pass


def is_kind(obj, kind):
    try:
        return getattr(obj, "SciForgeType", "") == kind and obj.isAttachedToDocument()
    except Exception:
        return False


def of_kind(doc, kind):
    return [o for o in doc.Objects if is_kind(o, kind)]


def bodies(doc):
    """What can be measured: bodies and loose solids (not analyses, sketches, datums)."""
    from . import section

    return section.clipped_objects(doc)


def solid_of(obj):
    """The solid shape of a body or loose solid in global coordinates."""
    try:
        shape = obj.Shape
    except Exception:
        shape = None
    if shape is None or shape.isNull() or not shape.Solids:
        raise AnalysisError("%s has no solid." % getattr(obj, "Label", "?"))
    return shape


def body_of(obj):
    """The body (or loose solid) a pick belongs to, or None."""
    if obj is None:
        return None
    if obj.TypeId == "PartDesign::Body":
        return obj
    try:
        parent = obj.getParentGeoFeatureGroup()
    except Exception:
        parent = None
    if parent is not None and parent.TypeId == "PartDesign::Body":
        return parent
    if parent is None:
        try:
            if obj.isDerivedFrom("Part::Feature") and obj.Shape.Solids:
                if not getattr(obj, "SciForgeType", ""):
                    return obj
        except Exception:
            return None
    return None


# -- Center of Mass ----------------------------------------------------------------------------
def center_of_mass(shapes):
    """(centre, volume) of solids of one material: the volume-weighted centroid."""
    total = 0.0
    moment = V(0, 0, 0)
    for shape in shapes:
        for solid in shape.Solids:
            volume = solid.Volume
            if volume <= 0:
                continue
            total += volume
            moment = moment + solid.CenterOfMass * volume
    if total <= 0:
        raise AnalysisError("There is no solid to find the centre of mass of.")
    return moment * (1.0 / total), total


def _targets(obj):
    picked = [o for o in obj.Bodies if o is not None]
    if picked:
        return picked
    found = []
    for o in bodies(obj.Document):
        try:
            if o.ViewObject is not None and not o.ViewObject.Visibility:
                continue
        except Exception:
            pass
        found.append(o)
    return found


class CenterOfMassAnalysis:
    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        props = obj.PropertiesList
        add = [
            ("App::PropertyString", "SciForgeType", "SciForge", "Kind of SciForge object"),
            ("App::PropertyLinkListGlobal", "Bodies", "Center of Mass", "Bodies (none: all)"),
            ("App::PropertyVector", "Position", "Center of Mass", "The centre (worked out)"),
            ("App::PropertyFloat", "Volume", "Center of Mass", "Volume measured (mm^3)"),
        ]
        for kind, name, group, doc in add:
            if name not in props:
                obj.addProperty(kind, name, group, doc)
        obj.SciForgeType = COM_KIND
        for name in ("Position", "Volume"):
            try:
                obj.setEditorMode(name, 1)
                # worked-out values: writing them (follow) must not mark the analysis touched
                obj.setPropertyStatus(name, "Output")
            except Exception:
                pass

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        targets = _targets(obj)
        shapes = [solid_of(o) for o in targets]
        centre, volume = center_of_mass(shapes)
        obj.Position = centre
        obj.Volume = volume

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def follow(doc):
    """A Center of Mass with no bodies picked counts every visible body, so it links to none
    and a recompute never reaches it: work its values out again (called after a recompute,
    a body shown or hidden, undo / redo). Returns the analyses that moved."""
    moved = []
    for obj in of_kind(doc, COM_KIND):
        try:
            if [o for o in obj.Bodies if o is not None]:
                continue
            centre, volume = center_of_mass([solid_of(o) for o in _targets(obj)])
        except Exception:
            continue  # nothing to measure: the analysis keeps its last values
        if (obj.Position - centre).Length > 1e-9 or abs(obj.Volume - volume) > 1e-9:
            obj.Position = centre
            obj.Volume = volume
            moved.append(obj)
    return moved


# -- Interference --------------------------------------------------------------------------------
def _touching(a, b):
    """Faces two solids share (they touch without overlapping), or None."""
    try:
        dist = a.distToShape(b)[0]
    except Exception:
        return None
    if dist > 1e-7:
        return None
    try:
        import Part

        shared = Part.Shell(a.Faces).common(Part.Shell(b.Faces))
    except Exception:
        return None
    faces = [f for f in shared.Faces if f.Area > 1e-9]
    return Part.Compound(faces) if faces else None


def interference(named_shapes, include_coincident=False):
    """[(label 1, label 2, volume, shape)] for every pair of the shapes that overlap (and,
    with include_coincident, that only touch: volume 0, shape = the shared faces)."""
    found = []
    for i in range(len(named_shapes)):
        for j in range(i + 1, len(named_shapes)):
            (la, a), (lb, b) = named_shapes[i], named_shapes[j]
            if not a.BoundBox.intersect(b.BoundBox):
                continue
            try:
                common = a.common(b)
            except Exception as exc:
                raise AnalysisError("Could not compare %s and %s: %s" % (la, lb, exc))
            volume = sum(s.Volume for s in common.Solids)
            if volume > VOLUME_EPS:
                found.append((la, lb, volume, common))
            elif include_coincident:
                shared = _touching(a, b)
                if shared is not None:
                    found.append((la, lb, 0.0, shared))
    return found


class InterferenceAnalysis:
    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        props = obj.PropertiesList
        add = [
            ("App::PropertyString", "SciForgeType", "SciForge", "Kind of SciForge object"),
            ("App::PropertyLinkListGlobal", "Bodies", "Interference", "Bodies to compare"),
            ("App::PropertyBool", "IncludeCoincident", "Interference", "Report touching too"),
            ("App::PropertyStringList", "Results", "Interference", "label|label|volume"),
            ("Part::PropertyPartShape", "Overlap", "Interference", "Where they overlap"),
        ]
        for kind, name, group, doc in add:
            if name not in props:
                obj.addProperty(kind, name, group, doc)
        obj.SciForgeType = INTERFERENCE_KIND
        for name in ("Results", "Overlap"):
            try:
                obj.setEditorMode(name, 1)
            except Exception:
                pass

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        import Part

        picked = [o for o in obj.Bodies if o is not None]
        if len(picked) < 2:
            raise AnalysisError("Pick at least two bodies to compare.")
        named = [(o.Label, solid_of(o)) for o in picked]
        found = interference(named, obj.IncludeCoincident)
        obj.Results = ["%s|%s|%.9g" % (a, b, v) for a, b, v, _s in found]
        shapes = [s for _a, _b, _v, s in found]
        obj.Overlap = Part.Compound(shapes) if shapes else Part.Shape()

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def results(obj):
    """[(label 1, label 2, volume)] stored on an interference analysis."""
    out = []
    for line in obj.Results:
        parts = line.split("|")
        if len(parts) == 3:
            try:
                out.append((parts[0], parts[1], float(parts[2])))
            except ValueError:
                continue
    return out


# -- making them -------------------------------------------------------------------------------
def next_label(doc, base):
    import re

    used = 0
    for obj in doc.Objects:
        match = re.match(r"^%s\s*(\d+)$" % re.escape(base), obj.Label or "")
        if match:
            used = max(used, int(match.group(1)))
    return "%s%d" % (base, used + 1)


def make_com(doc, picked=()):
    obj = doc.addObject("App::FeaturePython", "CenterOfMass")
    CenterOfMassAnalysis(obj)
    obj.Label = next_label(doc, "Center of Mass")
    set_bodies(obj, picked)
    return obj


def make_interference(doc, picked=(), include_coincident=False):
    obj = doc.addObject("App::FeaturePython", "Interference")
    InterferenceAnalysis(obj)
    obj.Label = next_label(doc, "Interference")
    set_bodies(obj, picked)
    if bool(obj.IncludeCoincident) != bool(include_coincident):
        obj.IncludeCoincident = bool(include_coincident)
    return obj


def set_bodies(obj, picked):
    picked = [o for o in picked if o is not None]
    if [o.Name for o in obj.Bodies] != [o.Name for o in picked]:
        obj.Bodies = picked
    obj.touch()
