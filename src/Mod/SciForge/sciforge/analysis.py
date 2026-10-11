# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Center of Mass and Interference, the document side (no Qt): the maths and the
analysis objects the browser lists in its Analysis folder (SciForgeType ...Analysis, left out
of the timeline). Both follow the model: every recompute measures the picked bodies again.

  CenterOfMassAnalysis  Bodies (picked; none = every visible body), Position (worked out),
                        Volume. Each body weighs with the density of its Physical Material
                        (material.effective: Steel while on FreeCAD's Default).
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

from . import labels  # noqa: E402

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
def density_of(obj):
    """kg/mm^3 a body weighs with in the Center of Mass: its Physical Material (Steel while it
    is still on FreeCAD's Default, as Fusion designs start in Steel), or None if unknown."""
    try:
        from . import material

        _label, rho = material.effective(obj)
        return float(rho) if rho is not None and rho > 0 else None
    except Exception:
        return None


def center_of_mass(shapes, densities=None):
    """(centre, volume) of solids: the centre of their mass, each solid weighing its volume
    times the density of its body (`densities`, one per shape). Without densities, or when
    one is unknown, every solid weighs its volume (one material: the volume centroid)."""
    shapes = list(shapes)
    if densities is None or len(densities) != len(shapes) or None in densities:
        densities = [1.0] * len(shapes)
    total = 0.0
    weight = 0.0
    moment = V(0, 0, 0)
    for shape, rho in zip(shapes, densities):
        for solid in shape.Solids:
            volume = solid.Volume
            if volume <= 0:
                continue
            total += volume
            weight += volume * rho
            moment = moment + solid.CenterOfMass * (volume * rho)
    if total <= 0 or weight <= 0:
        raise AnalysisError("There is no solid to find the centre of mass of.")
    return moment * (1.0 / weight), total


def all_bodies(obj):
    """True for a Center of Mass of every visible body (none picked)."""
    return bool(getattr(obj, "AllBodies", not [o for o in obj.Bodies if o is not None]))


def problem(obj):
    """Why an analysis shows its last result instead of a new one, or ''."""
    return getattr(obj, "Problem", "") or ""


def _set(obj, prop, value):
    if getattr(obj, prop) != value:
        setattr(obj, prop, value)


def _targets(obj):
    picked = [o for o in obj.Bodies if o is not None]
    if not all_bodies(obj):
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
            ("App::PropertyBool", "AllBodies", "Center of Mass", "Every visible body"),
            ("App::PropertyString", "Problem", "Center of Mass", "Why it shows nothing"),
        ]
        for kind, name, group, doc in add:
            if name not in props:
                obj.addProperty(kind, name, group, doc)
                if name == "AllBodies":  # documents from before: none picked meant all
                    obj.AllBodies = not [o for o in obj.Bodies if o is not None]
        obj.SciForgeType = COM_KIND
        for name in ("AllBodies", "Problem"):
            try:
                obj.setEditorMode(name, 2)
            except Exception:
                pass
        for name in ("Position", "Volume", "Problem"):
            try:
                obj.setEditorMode(name, 1)
                # worked-out values: writing them (follow) must not mark the analysis touched
                obj.setPropertyStatus(name, "Output")
            except Exception:
                pass

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        """Measure again. Nothing to measure (the picked bodies were deleted, every body is
        hidden) keeps the last values and says why in Problem (the marker is hidden): it
        never fails, a failed analysis printed errors after every later change."""
        try:
            centre, volume = measure_com(obj)
        except Exception as exc:
            _set(obj, "Problem", str(exc) or "There is nothing to measure.")
            return
        _set(obj, "Problem", "")
        obj.Position = centre
        obj.Volume = volume

    def allowDuplicateLabel(self, obj):
        """Yes only while SciForge sets the label it worked out (see labels.py)."""
        return labels.allow_duplicate()

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


GONE = "The bodies it measured are gone. Edit it and pick bodies."


def measure_com(obj):
    """(centre, volume) of what a Center of Mass analysis measures; raises AnalysisError."""
    targets = _targets(obj)
    if not targets and not all_bodies(obj):
        raise AnalysisError(GONE)
    return center_of_mass([solid_of(o) for o in targets], [density_of(o) for o in targets])


def follow(doc):
    """A Center of Mass of every visible body links to none, so a recompute never reaches
    it: work its values out again (called after a recompute, a body shown or hidden, undo /
    redo). Returns the analyses that moved."""
    moved = []
    for obj in of_kind(doc, COM_KIND):
        if not all_bodies(obj):
            continue
        try:
            centre, volume = measure_com(obj)
        except Exception as exc:
            text = str(exc) or "There is nothing to measure."
            if problem(obj) != text:
                obj.Problem = text
                moved.append(obj)
            continue  # nothing to measure: the analysis keeps its last values
        if problem(obj):
            obj.Problem = ""
            moved.append(obj)
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


TOO_FEW = "Pick at least two bodies to compare."


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
            ("App::PropertyString", "Problem", "Interference", "Why nothing was compared"),
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
        try:
            obj.setEditorMode("Problem", 2)
        except Exception:
            pass

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        """Compare the bodies again. Fewer than two left (one was deleted) or one without a
        solid: no result, Problem says why. It never fails: a failed analysis printed
        errors after every later change."""
        import Part

        picked = [o for o in obj.Bodies if o is not None]
        try:
            if len(picked) < 2:
                raise AnalysisError(TOO_FEW)
            named = [(o.Label, solid_of(o)) for o in picked]
            found = interference(named, obj.IncludeCoincident)
        except Exception as exc:
            _set(obj, "Problem", str(exc) or TOO_FEW)
            if obj.Results:
                obj.Results = []
            if not obj.Overlap.isNull():
                obj.Overlap = Part.Shape()
            return
        _set(obj, "Problem", "")
        obj.Results = ["%s|%s|%.9g" % (a, b, v) for a, b, v, _s in found]
        shapes = [s for _a, _b, _v, s in found]
        obj.Overlap = Part.Compound(shapes) if shapes else Part.Shape()

    def allowDuplicateLabel(self, obj):
        """Yes only while SciForge sets the label it worked out (see labels.py)."""
        return labels.allow_duplicate()

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
    labels.set_exact(obj, next_label(doc, "Center of Mass"))
    set_bodies(obj, picked)
    return obj


def make_interference(doc, picked=(), include_coincident=False):
    obj = doc.addObject("App::FeaturePython", "Interference")
    InterferenceAnalysis(obj)
    labels.set_exact(obj, next_label(doc, "Interference"))
    set_bodies(obj, picked)
    if bool(obj.IncludeCoincident) != bool(include_coincident):
        obj.IncludeCoincident = bool(include_coincident)
    return obj


def set_bodies(obj, picked):
    picked = [o for o in picked if o is not None]
    if [o.Name for o in obj.Bodies] != [o.Name for o in picked]:
        obj.Bodies = picked
    if "AllBodies" in obj.PropertiesList and bool(obj.AllBodies) != (not picked):
        obj.AllBodies = not picked
    obj.touch()
