# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Scale for a body, as a step in the body's timeline. No GUI code: the Scale
dialog (scale_ui.py) and the golden-model builder both use this module.

The body's solid, as it is at this point of the timeline, is scaled about a point:
  Uniform      one factor for every direction (2 = twice as big)
  Non Uniform  one factor per direction (X, Y, Z of the body)
The point is the body's origin (the default, like an empty Point box), a corner of the
part (a vertex), or a construction point of the body. A point on the part follows later
edits of earlier steps, like every other step.

It is a PartDesign::FeaturePython, so it behaves like any PartDesign feature: later
steps build on it, editing earlier steps recomputes it, it shows in the timeline (kind
"scale") and its dialog opens with a double-click there. Saved documents store the
class path "sciforge.scale.ScaleFeature": keep the name and the properties stable.

A uniform scale keeps the exact geometry (planes stay planes, circles circles). A non
uniform one turns every face into a NURBS surface: the shape is still exact, but FreeCAD
then measures the volume of curved NURBS faces only approximately (to about 1 %).
"""
import FreeCAD as App

TYPE = "PartDesign::FeaturePython"
KIND = "Scale"
MIN_FACTOR = 1e-3
MAX_FACTOR = 1e4


class ScaleError(ValueError):
    """The scale cannot be made; the message says why and what to try."""


def default_options():
    return {"uniform": True, "factor": 1.0, "factors": [1.0, 1.0, 1.0]}


def is_scale(obj):
    return (
        obj is not None
        and getattr(obj, "TypeId", "") == TYPE
        and getattr(obj, "SciForgeType", "") == KIND
    )


def factors_of(options):
    """(sx, sy, sz) the options ask for."""
    if options.get("uniform", True):
        f = float(options.get("factor", 1.0))
        return f, f, f
    values = list(options.get("factors", [1.0, 1.0, 1.0]))
    if len(values) != 3:
        raise ScaleError("A non uniform scale needs three factors (X, Y, Z).")
    return tuple(float(v) for v in values)


def check_factors(factors, uniform=True):
    names = ("Scale factor",) if uniform else ("X scale", "Y scale", "Z scale")
    values = factors[:1] if uniform else factors
    for name, value in zip(names, values):
        if value <= 0:
            raise ScaleError("%s must be more than 0." % name)
        if value < MIN_FACTOR or value > MAX_FACTOR:
            raise ScaleError(
                "%s %g is out of range: use a value between %g and %g."
                % (name, value, MIN_FACTOR, MAX_FACTOR)
            )


def matrix(point, factors):
    """The matrix that scales by `factors` about `point`."""
    sx, sy, sz = factors
    m = App.Matrix()
    m.move(-point)
    scale = App.Matrix()
    scale.scale(sx, sy, sz)
    m = scale.multiply(m)
    back = App.Matrix()
    back.move(point)
    return back.multiply(m)


def _keep_names(shape, result):
    """FreeCAD's non-uniform transform gives a shape without element names, and the
    uniform one names its faces differently: a sketch on a face of the scaled part (or
    any later step using its faces) lost its face as soon as the factors were edited
    ("?Face6"). Both keep every face, edge and corner in the same order, so the part's
    own names carry over one to one, whatever the factors."""
    try:
        if (
            len(result.Faces) == len(shape.Faces)
            and len(result.Edges) == len(shape.Edges)
            and len(result.Vertexes) == len(shape.Vertexes)
        ):
            names = shape.ElementMap
            if names:
                result.ElementMap = names
                result.Tag = shape.Tag  # FreeCAD tags the names with it (one way for both)
    except Exception:
        pass


def scaled(shape, point, factors):
    """A scaled copy of `shape` about `point` (body coordinates). Raises ScaleError."""
    sx, sy, sz = factors
    if shape is None or shape.isNull() or not shape.Solids:
        raise ScaleError("Make a solid first (Create Sketch, then Extrude).")
    try:
        if abs(sx - sy) < 1e-12 and abs(sx - sz) < 1e-12:
            result = shape.copy()
            result.scale(sx, point)  # exact: planes stay planes, circles stay circles
        else:
            result = shape.transformGeometry(matrix(point, factors))
        _keep_names(shape, result)
    except Exception as exc:
        raise ScaleError("The part could not be scaled: %s" % exc)
    if result.isNull() or not result.Solids or not result.isValid():
        raise ScaleError("Scaling made an invalid part. Try other factors.")
    return result


# -- the point --------------------------------------------------------------------------
def origin_point(body):
    """The body's origin point object (App::Point, role "Origin"), or None."""
    try:
        for feature in body.Origin.OriginFeatures:
            if getattr(feature, "Role", "") == "Origin" or feature.TypeId == "App::Point":
                return feature
    except Exception:
        pass
    return None


def point_of(ref):
    """The point (body coordinates) of a point reference (object, element name), or the
    origin for None. Raises ScaleError."""
    if ref is None or ref[0] is None:
        return App.Vector(0, 0, 0)
    obj, sub = ref
    if sub:
        sub = plain_name(sub)
        try:
            vertex = obj.Shape.getElement(sub)
        except Exception:
            raise ScaleError(
                "The scale point %s no longer exists (an earlier step changed the part). "
                "Pick the point again." % sub
            )
        if not sub.startswith("Vertex"):
            raise ScaleError("The scale point must be a corner (vertex) or a point.")
        return App.Vector(vertex.Point)
    if obj.TypeId == "App::Point":
        return App.Vector(obj.Placement.Base)
    if obj.TypeId == "PartDesign::Point":
        try:
            return App.Vector(obj.Shape.Vertexes[0].Point)
        except Exception:
            return App.Vector(obj.Placement.Base)
    raise ScaleError("The scale point must be a corner (vertex) or a point.")


def plain_name(sub):
    """FreeCAD marks a reference it lost track of with "?" ("?Vertex6"): its naming loses
    the corners of a Pad when the Pad's length changes. The corner with the same number is
    then used (the same corner as long as the part's topology did not change)."""
    return sub.lstrip("?") if sub else sub


def point_label(ref):
    if ref is None or ref[0] is None:
        return "Origin"
    obj, sub = ref
    if sub:
        return plain_name(sub)
    if obj.TypeId == "App::Point":
        return "Origin"
    return obj.Label


def is_point_object(obj):
    return obj is not None and obj.TypeId in ("App::Point", "PartDesign::Point")


# -- the feature -------------------------------------------------------------------------
class ScaleFeature:
    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc, group="Scale"):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, group, doc)
                return True
            return False

        if add("App::PropertyEnumeration", "ScaleType", "One factor, or one per direction"):
            obj.ScaleType = ["Uniform", "NonUniform"]
        if add("App::PropertyFloat", "Factor", "Scale factor (Uniform)"):
            obj.Factor = 1.0
        for axis in "XYZ":
            if add("App::PropertyFloat", "Factor" + axis, "Scale factor along %s" % axis):
                setattr(obj, "Factor" + axis, 1.0)
        add(
            "App::PropertyLinkSub",
            "Point",
            "The point the part is scaled about (empty: the body's origin)",
        )
        if add("App::PropertyBool", "Refine", "Merge faces that end up in one plane, like Fusion"):
            obj.Refine = True
        if "SciForgeType" not in obj.PropertiesList:
            obj.addProperty("App::PropertyString", "SciForgeType", "Base", "", 4)  # hidden
            obj.SciForgeType = KIND
        ScaleFeature.show_used(obj)

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def onChanged(self, obj, prop):
        if prop == "ScaleType":
            ScaleFeature.show_used(obj)

    @staticmethod
    def show_used(obj):
        """Only the factors the scale type uses are shown (property editor, Change
        Parameters), like the dialog's fields."""
        try:
            uniform = str(obj.ScaleType) == "Uniform"
            obj.setEditorMode("Factor", 0 if uniform else 2)
            for axis in "XYZ":
                obj.setEditorMode("Factor" + axis, 2 if uniform else 0)
        except Exception:
            pass

    def execute(self, obj):
        base = obj.BaseFeature
        if base is None or base.Shape.isNull() or not base.Shape.Solids:
            raise ScaleError("Scale needs a solid before it in the timeline.")
        options = read_options(obj)
        factors = factors_of(options)
        check_factors(factors, options["uniform"])
        link = obj.Point
        ref = None
        if link and link[0] is not None:
            subs = [s for s in link[1] if s]
            ref = (link[0], subs[0] if subs else "")
            if ref[1] and ref[0] is not base:
                ref = (base, ref[1])  # the vertex of the step before (it may have moved)
        result = scaled(base.Shape, point_of(ref), factors)
        if obj.Refine:
            try:
                result = result.removeSplitter()
            except Exception:
                pass
        obj.Shape = result

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def read_options(obj):
    uniform = obj.ScaleType == "Uniform"
    return {
        "uniform": uniform,
        "factor": float(obj.Factor),
        "factors": [float(obj.FactorX), float(obj.FactorY), float(obj.FactorZ)],
    }


def _attach_view_provider(obj):
    try:
        if not App.GuiUp or obj.ViewObject is None:
            return
        from .scale_ui import ViewProviderScale

        ViewProviderScale(obj.ViewObject)
    except Exception:
        pass


def _set(feature, prop, value):
    from . import shelling

    shelling._set(feature, prop, value)


def apply(feature, base, point_ref, options, formulas=None):
    """Write the dialog's point and options onto the feature. `formulas` {"factor",
    "x", "y", "z": text} are parameter formulas typed in the fields ("" = a number)."""
    from . import shelling

    formulas = dict(formulas or {})
    if feature.BaseFeature is not base:
        feature.BaseFeature = base
    uniform = bool(options.get("uniform", True))
    _set(feature, "ScaleType", "Uniform" if uniform else "NonUniform")
    shelling._set_formula(feature, "Factor", formulas.get("factor", ""))
    _set(feature, "Factor", float(options.get("factor", 1.0)))
    values = list(options.get("factors", [1.0, 1.0, 1.0]))
    for axis, value in zip("XYZ", values):
        shelling._set_formula(feature, "Factor" + axis, formulas.get(axis.lower(), ""))
        _set(feature, "Factor" + axis, float(value))
    if point_ref is None or point_ref[0] is None:
        if feature.Point is not None and feature.Point[0] is not None:
            feature.Point = None
    else:
        obj, sub = point_ref
        old = feature.Point
        if not (old and old[0] is obj and [s for s in old[1] if s] == ([sub] if sub else [])):
            feature.Point = (obj, [sub] if sub else [""])
    if not feature.Refine:
        feature.Refine = True


def make(body, base, point_ref, options, name="Scale", formulas=None):
    """A new Scale at the end of `body`, on `base` (normally body.Tip). Not recomputed."""
    if base is None or base.Shape.isNull() or not base.Shape.Solids:
        raise ScaleError("Make a solid first (Create Sketch, then Extrude).")
    obj = body.newObject(TYPE, name)
    ScaleFeature(obj)
    _attach_view_provider(obj)
    obj.BaseFeature = base
    body.Tip = obj  # newObject() does not always move the Tip for Python features
    apply(obj, base, point_ref, options, formulas)
    return obj


def read(feature):
    """(base, point_ref, options, formulas) of an existing Scale."""
    from . import shelling

    options = read_options(feature)
    link = feature.Point
    ref = None
    if link and link[0] is not None:
        subs = [s for s in link[1] if s]
        ref = (link[0], plain_name(subs[0]) if subs else "")
    formulas = {"factor": shelling.formula_of(feature, "Factor")}
    for axis in "XYZ":
        formulas[axis.lower()] = shelling.formula_of(feature, "Factor" + axis)
    return feature.BaseFeature, ref, options, formulas


def trial(shape, point_ref, options):
    """Build and check without touching the document. Returns the shape."""
    factors = factors_of(options)
    check_factors(factors, bool(options.get("uniform", True)))
    return scaled(shape, point_of(point_ref), factors)


def owner_body(obj):
    from . import shelling

    return shelling.owner_body(obj)


def remove(feature):
    from . import shelling

    shelling.remove(feature)


def handle_spots(shape, point, options):
    """Where the blue arrows go: [{"what", "origin", "direction", "length"}] in body
    coordinates. Each sits on the side of the part farthest from the scale point and
    moves with that side: dragging it by d changes the factor by d / length."""
    box = shape.BoundBox
    spots = []
    if options.get("uniform", True):
        corners = [
            App.Vector(x, y, z)
            for x in (box.XMin, box.XMax)
            for y in (box.YMin, box.YMax)
            for z in (box.ZMin, box.ZMax)
        ]
        far = max(corners, key=lambda c: (c - point).Length)
        reach = far - point
        if reach.Length < 1e-9:
            return spots
        spots.append(
            {
                "what": "factor",
                "origin": far,
                "direction": reach.normalize() * 1.0,
                "length": (far - point).Length,
            }
        )
        return spots
    center = box.Center
    for i, axis in enumerate("xyz"):
        lo = (box.XMin, box.YMin, box.ZMin)[i]
        hi = (box.XMax, box.YMax, box.ZMax)[i]
        p = (point.x, point.y, point.z)[i]
        side = hi if abs(hi - p) >= abs(lo - p) else lo
        length = side - p
        if abs(length) < 1e-9:
            continue
        unit = App.Vector(*[1.0 if j == i else 0.0 for j in range(3)])
        origin = App.Vector(center)
        if i == 0:
            origin.x = side
        elif i == 1:
            origin.y = side
        else:
            origin.z = side
        spots.append(
            {
                "what": axis,
                "origin": origin,
                "direction": unit * (1.0 if length > 0 else -1.0),
                "length": abs(length),
            }
        )
    return spots
