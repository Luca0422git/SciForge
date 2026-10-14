# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Shell, without GUI code: the Shell dialog (shell_ui.py) and the golden-model
builder both use this module, so a model built by the test suite is built exactly like
one made with the mouse.

What the user picks (Fusion's "Faces/Body" box) on the body's last solid:
  faces    those faces are taken away and the rest of the part becomes a wall
  nothing  (the body itself) the part becomes hollow: a closed wall with a void inside

Options, like Fusion's dialog:
  {"inside": mm, "outside": mm, "direction": "inside" | "outside" | "both",
   "shell_type": "sharp" | "rounded", "tangent": bool}
"inside" is the wall inside the part's surface (used by Inside and Both), "outside" the
wall outside it (Outside and Both). Sharp gives sharp corners where walls meet outside
the part, Rounded rounds them (FreeCAD's Join "Arc"). Tangent Chain is a picking aid:
faces that continue a picked face smoothly are picked with it.

The feature that is made:
  faces taken away, Inside or Outside  -> PartDesign::Thickness (FreeCAD's own shell)
  a hollow body, or Both               -> ShellFeature, a PartDesign::FeaturePython:
                                          FreeCAD's Thickness cannot hollow a closed body
                                          or make a wall on both sides of the surface.
update() swaps one for the other when the options change; the step keeps its place and
name in the timeline and later steps are moved over to the new one.

Too-thick walls: OpenCASCADE either refuses ("BRep_API: command not done") or quietly
returns a wrong part (a solid box, or a broken solid sticking out of the part).
build() checks every result and raises ShellError with a plain-language reason, so the
dialog can say why and keep the last good preview.
"""
import json
import math
import time

NATIVE = "PartDesign::Thickness"
FP_TYPE = "PartDesign::FeaturePython"
KIND = "Shell"
META = "SciForgeShell"  # hidden JSON on the feature: what FreeCAD's Thickness cannot hold
TOL = 1e-7
# Wall tags (see _tagged): far from FreeCAD's object ids, and small enough for a C "long"
# on Windows (32 bits there: 1 << 40 failed every Shell Both with "Python int too large
# to convert to C long" in the Windows build, 2026-10-12).
TAG_BASE = 1 << 30
TAG_MAX = (1 << 31) - 1
RIM_SPOTS = (0.5, 0.375, 0.625, 0.25, 0.75, 0.125, 0.875, 0.0)  # where an arrow may sit
SMOOTH = math.radians(1.0)
DIRECTIONS = ("inside", "outside", "both")
SHELL_TYPES = ("sharp", "rounded")


class ShellError(ValueError):
    """The shell cannot be made; the message says why and what to try."""


def default_options():
    return {
        "inside": 1.0,
        "outside": 1.0,
        "direction": "inside",
        "shell_type": "sharp",
        "tangent": True,
    }


def with_defaults(options):
    opts = default_options()
    opts.update({k: v for k, v in (options or {}).items() if v is not None})
    if opts["direction"] not in DIRECTIONS:
        raise ShellError("Direction must be Inside, Outside or Both.")
    if opts["shell_type"] not in SHELL_TYPES:
        raise ShellError("Shell Type must be Sharp or Rounded.")
    return opts


def is_own(obj):
    return (
        obj is not None
        and getattr(obj, "TypeId", "") == FP_TYPE
        and getattr(obj, "SciForgeType", "") == KIND
    )


def is_shell(obj):
    return obj is not None and (getattr(obj, "TypeId", "") == NATIVE or is_own(obj))


def needs_own_feature(names, options):
    """True when FreeCAD's Thickness cannot make this shell (hollow body, or Both)."""
    return not names or options.get("direction") == "both"


def thicknesses(options):
    """(inside, outside) wall thickness in mm that the direction uses (0 = no wall)."""
    direction = options.get("direction", "inside")
    inside = float(options.get("inside", 0.0)) if direction in ("inside", "both") else 0.0
    outside = float(options.get("outside", 0.0)) if direction in ("outside", "both") else 0.0
    return inside, outside


# -- picking ----------------------------------------------------------------------
def _normal_at(face, point):
    u, v = face.Surface.parameter(point)
    normal = face.normalAt(u, v)  # already points out of the solid
    if normal.Length > 0:
        normal.normalize()
    return normal


def smooth_edge(face, other, edge):
    """True if the two faces meet smoothly (tangent) along `edge`."""
    try:
        mid = edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2.0)
        return _normal_at(face, mid).getAngle(_normal_at(other, mid)) < SMOOTH
    except Exception:
        return False


def tangent_faces(shape, names):
    """`names` plus every face of `shape` reached from them across smooth edges (Fusion's
    Tangent Chain: picking one face of a filleted run picks the whole run)."""
    by_name = {"Face%d" % i: face for i, face in enumerate(shape.Faces, start=1)}
    around = {}  # edge hash -> [(face name, face, edge)]
    for name, face in by_name.items():
        for edge in face.Edges:
            around.setdefault(edge.hashCode(), []).append((name, face, edge))
    found = [n for n in names if n in by_name]
    queue = list(found)
    while queue:
        name = queue.pop()
        face = by_name[name]
        for edge in face.Edges:
            for other_name, other, other_edge in around.get(edge.hashCode(), []):
                if other_name in found or not other_edge.isSame(edge):
                    continue
                if smooth_edge(face, other, edge):
                    found.append(other_name)
                    queue.append(other_name)
    return found


def removable(shape, name):
    """True if face `name` of `shape` exists (any face of a solid can be taken away)."""
    if not name.startswith("Face"):
        return False
    try:
        shape.getElement(name)
        return True
    except Exception:
        return False


# -- the geometry -------------------------------------------------------------------
def _join(options):
    return 2 if options.get("shell_type", "sharp") == "sharp" else 0  # Intersection / Arc


def too_thick(what, value):
    return (
        "A %g mm %s wall is too thick for this part: the walls run into each other. "
        "Try a thinner wall." % (value, what)
    )


def _thick(solid, faces, offset, join, what):
    try:
        return solid.makeThickness(faces, offset, TOL, False, False, 0, join)
    except Exception:
        raise ShellError(
            "The shell cannot be made with a %g mm %s wall here. Try a thinner wall or "
            "take away other faces." % (abs(offset), what)
        )


def _offset(solid, offset, join, what):
    try:
        result = solid.makeOffsetShape(offset, TOL, False, False, 0, join, False)
    except Exception:
        raise ShellError(too_thick(what, abs(offset)))
    if result is None or result.isNull() or not result.Solids or not result.isValid():
        raise ShellError(too_thick(what, abs(offset)))
    if result.Volume <= TOL:
        raise ShellError(too_thick(what, abs(offset)))
    return result.Solids[0]


def _box(shape):
    """The exact bounding box. shape.BoundBox comes from the display triangles once the
    part has been drawn: a round part's box is then a little too small (a cylinder of
    radius 10 measured 9.997), and a 1 mm cup wall looked like "sticking out of the part"
    (it was refused as too thick)."""
    try:
        return shape.optimalBoundingBox(False, False)
    except Exception:
        return shape.BoundBox


def _inside_box(inner, outer, margin):
    tol = margin + 1e-6 * max(1.0, outer.DiagonalLength)
    return (
        inner.XMin >= outer.XMin - tol
        and inner.YMin >= outer.YMin - tol
        and inner.ZMin >= outer.ZMin - tol
        and inner.XMax <= outer.XMax + tol
        and inner.YMax <= outer.YMax + tol
        and inner.ZMax <= outer.ZMax + tol
    )


def solid_of(shape):
    """The one solid a shell is made from, or raises ShellError."""
    if shape is None or shape.isNull() or not shape.Solids:
        raise ShellError("Make a solid first (Create Sketch, then Extrude).")
    if len(shape.Solids) > 1:
        raise ShellError(
            "Shell works on a body made of one solid; this one has %d." % len(shape.Solids)
        )
    return shape if shape.ShapeType == "Solid" else shape.Solids[0]


def _tagged(shapes, tags):
    """Give the two walls that are joined their own tags. Both come from the same solid
    with the same history, so without it FreeCAD's naming had to tell their faces apart
    by an index that changed with every thickness: a later step (a Press Pull on the
    outside wall, a sketch on it) lost its face whenever the shell was edited."""
    if not tags:
        return
    for shape, tag in zip(shapes, tags):
        if not 0 < int(tag) <= TAG_MAX:
            continue  # FreeCAD would fail the whole step on a tag it cannot hold
        try:
            shape.Tag = int(tag)
        except Exception:
            pass


def wall_tags(feature):
    """The tags build() gives the walls of `feature` (stable: saved with the design)."""
    try:
        ident = int(feature.ID)
    except Exception:
        return None
    tags = (TAG_BASE + 2 * ident, TAG_BASE + 2 * ident + 1)
    return tags if tags[1] <= TAG_MAX else None


def build(shape, names, options, tags=None):
    """The shelled shape of `shape` (not refined), with faces `names` taken away (none:
    hollow). Checked: raises ShellError with a plain-language reason. `tags`: see
    _tagged() (the feature passes its own; trials do not need them)."""
    opts = with_defaults(options)
    inside, outside = thicknesses(opts)
    if opts["direction"] in ("inside", "both") and inside <= 0:
        raise ShellError("The inside thickness must be more than 0 mm.")
    if opts["direction"] in ("outside", "both") and outside <= 0:
        raise ShellError("The outside thickness must be more than 0 mm.")
    solid = solid_of(shape)
    join = _join(opts)
    faces = []
    for name in names:
        try:
            # "?Face3": a reference FreeCAD lost track of; the face with the same number
            faces.append(shape.getElement(name.lstrip("?")))
        except Exception:
            raise ShellError(
                "The face %s no longer exists (an earlier step changed the part). "
                "Pick the faces again." % name
            )
    if faces:
        walls = []
        if inside > 0:
            walls.append(_thick(solid, faces, -inside, join, "inside"))
        if outside > 0:
            walls.append(_thick(solid, faces, outside, join, "outside"))
        result = walls[0]
        if len(walls) == 2:
            _tagged(walls, tags)
            try:
                result = walls[0].fuse(walls[1])
            except Exception:
                raise ShellError("The inside and outside walls could not be joined here.")
    else:
        inner = _offset(solid, -inside, join, "inside") if inside > 0 else solid
        outer = _offset(solid, outside, join, "outside") if outside > 0 else solid
        if inside > 0 and not _inside_box(_box(inner), _box(solid), 0.0):
            raise ShellError(too_thick("inside", inside))
        if inside > 0 and outside > 0:
            _tagged((outer, inner), tags)
        try:
            result = outer.cut(inner)
        except Exception:
            raise ShellError("The hollow part could not be made with these walls.")
    try:
        _check(solid, result, inside, outside, bool(faces))
    except ShellError:
        if join == 2 and faces and _rounded_works(shape, names, opts):
            # OpenCASCADE's sharp (intersection) walls give up on some parts where rounded
            # ones work (a narrow slot open at the side): say so instead of "too thick".
            raise ShellError(
                "Sharp corners cannot be made with these walls here (FreeCAD's geometry kernel "
                "gives up). Choose Shell Type Rounded, or try another thickness."
            )
        raise
    return result


def _rounded_works(shape, names, opts):
    try:
        build(shape, names, dict(opts, shell_type="rounded"))
        return True
    except Exception:
        return False


def _check(solid, result, inside, outside, opened):
    biggest = inside if inside >= outside else outside
    what = "inside" if inside >= outside else "outside"
    if result is None or result.isNull() or not result.Solids:
        raise ShellError(too_thick(what, biggest))
    if len(result.Solids) > 1:
        raise ShellError(
            "These walls would split the part into %d pieces. Try a thinner wall."
            % len(result.Solids)
        )
    if not result.isValid():
        raise ShellError(too_thick(what, biggest))
    if not _inside_box(_box(result), _box(solid), outside):
        raise ShellError(too_thick(what, biggest))
    volume = result.Volume
    if volume <= TOL:
        raise ShellError(too_thick(what, biggest))
    if outside <= 0 and volume >= solid.Volume * (1.0 - 1e-9):
        # OpenCASCADE gave the solid part back: the walls filled the whole inside.
        raise ShellError(too_thick("inside", inside))


def trial(shape, names, options):
    """Build and check without touching the document (the dialog calls this before it
    changes the feature). Returns the shape or raises ShellError."""
    return build(shape, names, options)


def max_thickness(shape, names, options, which, upper, budget=0.6):
    """Largest `which` ("inside"/"outside") thickness that still works (bisection), or
    None. Stops after `budget` seconds: it is a hint for the message, not an exact limit."""
    lo, hi = 0.0, float(upper)
    start = time.time()
    trials = dict(options)
    for _ in range(14):
        if time.time() - start > budget:
            break
        mid = (lo + hi) / 2.0
        trials[which] = mid
        try:
            build(shape, names, trials)
            lo = mid
        except ShellError:
            hi = mid
    return lo if lo > 0 else None


# -- drag arrows -----------------------------------------------------------------------
def arrow_spots(shape, names, options, toward=None):
    """Where the blue thickness arrows go: [{"what", "point", "direction", "lift"}] in the
    shape's coordinates. With faces taken away the arrows sit on the rim of the first
    opening, pointing into the wall (inside) or out of it (outside); a hollow body gets
    them on the face turned most toward the viewer, pointing out of the part (dragging
    away from the surface makes the wall thicker)."""
    direction = options.get("direction", "inside")
    # An arrow for every wall the direction has, also while its value is 0 or wrong: the
    # arrow is how the wall is dragged back to a good value.
    inside = direction in ("inside", "both")
    outside = direction in ("outside", "both")
    spots = []
    try:
        solid = solid_of(shape)
    except ShellError:
        return spots
    if names:
        try:
            opening = shape.getElement(names[0])
        except Exception:
            return spots
        best = None  # (score, point, wall normal, opening normal): the rim spot facing you
        for edge in opening.Edges:
            for i, face in enumerate(solid.Faces, start=1):
                if "Face%d" % i in names or not any(e.isSame(edge) for e in face.Edges):
                    continue
                # several spots along the edge: a round rim (a cup) is one edge whose middle
                # is not the side turned toward you; the middle wins a tie (a straight edge)
                for fraction in RIM_SPOTS:
                    t = edge.FirstParameter + (edge.LastParameter - edge.FirstParameter) * fraction
                    mid = edge.valueAt(t)
                    try:
                        wall = _normal_at(face, mid)
                        up = _normal_at(opening, mid)
                    except Exception:
                        continue
                    if wall.Length < 0.5 or up.Length < 0.5:
                        continue
                    score = wall.dot(toward) if toward is not None else 0.0
                    if best is None or score > best[0] + 1e-9:
                        best = (score, mid, wall, up)
        if best is not None:
            _score, mid, wall, up = best
            if inside:
                spots.append({"what": "inside", "point": mid, "direction": -wall, "lift": up})
            if outside:
                spots.append({"what": "outside", "point": mid, "direction": wall, "lift": up})
        return spots
    faces = list(solid.Faces)
    if toward is not None:
        faces.sort(key=lambda f: -_face_normal(f).dot(toward))
    else:
        faces.sort(key=lambda f: -f.Area)
    for what, used in (("inside", inside), ("outside", outside)):
        if not used or not faces:
            continue
        face = faces.pop(0)
        point, normal = _face_middle(face)
        spots.append({"what": what, "point": point, "direction": normal, "lift": normal * 0.0})
    return spots


def _face_middle(face):
    u0, u1, v0, v1 = face.ParameterRange
    u, v = (u0 + u1) / 2.0, (v0 + v1) / 2.0
    point = face.valueAt(u, v)
    try:
        if face.Surface.__class__.__name__ == "Plane":
            point = face.CenterOfMass
            u, v = face.Surface.parameter(point)
    except Exception:
        pass
    normal = face.normalAt(u, v)
    if normal.Length > 0:
        normal.normalize()
    return point, normal


def _face_normal(face):
    return _face_middle(face)[1]


# -- the features ----------------------------------------------------------------------
def load_meta(feature):
    try:
        return json.loads(getattr(feature, META, "") or "{}")
    except Exception:
        return {}


def _save_meta(feature, meta):
    if META not in feature.PropertiesList:
        feature.addProperty("App::PropertyString", META, "Base", "", 4)  # hidden
    text = json.dumps(meta, sort_keys=True)
    if getattr(feature, META) != text:
        setattr(feature, META, text)


def _has_expression(feature, prop):
    try:
        return any(path in (prop, "." + prop) for path, _ in feature.ExpressionEngine)
    except Exception:
        return False


def _set(feature, prop, value):
    """Set a property only when it changes (an untouched feature is not recomputed) and
    never over an expression the user typed (=wall*2): that one wins."""
    if _has_expression(feature, prop):
        return
    current = getattr(feature, prop)
    current = getattr(current, "Value", current)
    if isinstance(value, float) and isinstance(current, float):
        if abs(current - value) < 1e-12:
            return
    elif current == value:
        return
    setattr(feature, prop, value)


def _set_formula(feature, prop, formula):
    """Put the dialog's formula (bare parameter names) on feature.prop, or take it away."""
    try:
        from . import preview

        preview.set_formula(feature, prop, formula or "")
    except Exception:
        if formula:
            raise


def formula_of(feature, prop):
    try:
        from . import preview

        return preview.formula_of(feature, prop)
    except Exception:
        return ""


class ShellFeature:
    """A hollow body, or a shell with walls on both sides of the surface. Saved documents
    store "sciforge.shelling.ShellFeature": keep the name and the properties stable."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc, group="Shell"):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, group, doc)
                return True
            return False

        add(
            "App::PropertyLinkSub",
            "Faces",
            "The faces taken away (none: the body becomes hollow)",
        )
        if add("App::PropertyLength", "InsideThickness", "Wall thickness inside the surface"):
            obj.InsideThickness = 1.0
        if add("App::PropertyLength", "OutsideThickness", "Wall thickness outside the surface"):
            obj.OutsideThickness = 1.0
        if add("App::PropertyEnumeration", "Direction", "Which side of the surface the wall is"):
            obj.Direction = ["Inside", "Outside", "Both"]
        if add("App::PropertyEnumeration", "ShellType", "Sharp or rounded outside corners"):
            obj.ShellType = ["Sharp", "Rounded"]
        if add("App::PropertyBool", "Refine", "Merge faces that end up in one plane, like Fusion"):
            obj.Refine = True
        if "SciForgeType" not in obj.PropertiesList:
            obj.addProperty("App::PropertyString", "SciForgeType", "Base", "", 4)  # hidden
            obj.SciForgeType = KIND
        ShellFeature.show_used(obj)

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def onChanged(self, obj, prop):
        if prop == "Direction":
            ShellFeature.show_used(obj)

    @staticmethod
    def show_used(obj):
        """Only the thickness the direction uses is shown (property editor, Change
        Parameters), like the dialog's fields."""
        try:
            direction = str(obj.Direction)
            obj.setEditorMode("InsideThickness", 0 if direction in ("Inside", "Both") else 2)
            obj.setEditorMode("OutsideThickness", 0 if direction in ("Outside", "Both") else 2)
        except Exception:
            pass

    def execute(self, obj):
        base = obj.BaseFeature
        if base is None or base.Shape.isNull() or not base.Shape.Solids:
            raise ShellError("Shell needs a solid before it in the timeline.")
        link = obj.Faces
        names = [s.lstrip("?") for s in (link[1] if link else []) if s]
        result = build(base.Shape, names, _fp_options(obj), tags=wall_tags(obj))
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


def _fp_options(obj):
    return {
        "inside": obj.InsideThickness.Value,
        "outside": obj.OutsideThickness.Value,
        "direction": str(obj.Direction).lower(),
        "shell_type": str(obj.ShellType).lower(),
    }


def _attach_view_provider(obj):
    try:
        import FreeCAD as App

        if not App.GuiUp or obj.ViewObject is None:
            return
        from .shell_ui import ViewProviderShell

        ViewProviderShell(obj.ViewObject)
    except Exception:
        pass


def owner_body(obj):
    try:
        parent = obj.getParentGeoFeatureGroup()
    except Exception:
        return None
    if parent is not None and parent.TypeId == "PartDesign::Body":
        return parent
    return None


def solid_base(body):
    """The step a new shell builds on: the body's current end, if it is a solid."""
    tip = body.Tip if body is not None else None
    if tip is None or not hasattr(tip, "Shape") or tip.Shape.isNull() or not tip.Shape.Solids:
        return None
    return tip


def _new(body, type_id, name, before=None):
    if before is not None:
        obj = body.Document.addObject(type_id, name)
        body.insertObject(obj, before, False)
        return obj
    return body.newObject(type_id, name)


def make(body, base, names, options, name="Shell", before=None, formulas=None):
    """A new shell at the end of `body` (or just before `before`), on `base` (normally
    body.Tip). Not recomputed. Returns the feature."""
    if base is None or base.Shape.isNull() or not base.Shape.Solids:
        raise ShellError("Make a solid first (Create Sketch, then Extrude).")
    opts = with_defaults(options)
    names = list(names or [])
    if needs_own_feature(names, opts):
        feature = _new(body, FP_TYPE, name, before)
        ShellFeature(feature)
        _attach_view_provider(feature)
    else:
        feature = _new(body, NATIVE, name, before)
    if before is None:
        body.Tip = feature  # newObject() does not always move the Tip (feature guide #5)
    apply(feature, base, names, opts, formulas)
    return feature


def apply(feature, base, names, options, formulas=None):
    """Write the dialog's picks and options onto the feature (native or SciForge's).
    `formulas` {"inside": text, "outside": text} are parameter formulas typed in the
    fields ("" = a plain number)."""
    opts = with_defaults(options)
    formulas = dict(formulas or {})
    names = list(names or [])
    direction = opts["direction"]
    if feature.TypeId == NATIVE:
        if needs_own_feature(names, opts):
            raise ShellError("FreeCAD's shell cannot do this; use update() to switch.")
        old = feature.Base
        if not (old and old[0] is base and list(old[1]) == names):
            feature.Base = (base, names)
        key = "inside" if direction == "inside" else "outside"
        _set_formula(feature, "Value", formulas.get(key, ""))
        _set(feature, "Value", float(opts[key]))
        _set(feature, "Reversed", direction == "inside")
        _set(feature, "Join", "Intersection" if opts["shell_type"] == "sharp" else "Arc")
        # Mode and Intersection keep FreeCAD's defaults (Skin, off): Fusion has no such
        # choices, and a shell made in FreeCAD with other values keeps them when edited.
    else:
        old = feature.Faces
        if not (old and old[0] is base and [s for s in old[1] if s] == names):
            feature.Faces = (base, names)
        if feature.BaseFeature is not base:
            feature.BaseFeature = base
        _set_formula(feature, "InsideThickness", formulas.get("inside", ""))
        _set_formula(feature, "OutsideThickness", formulas.get("outside", ""))
        _set(feature, "InsideThickness", float(opts["inside"]))
        _set(feature, "OutsideThickness", float(opts["outside"]))
        _set(feature, "Direction", direction.capitalize())
        _set(feature, "ShellType", opts["shell_type"].capitalize())
    if not feature.Refine:
        feature.Refine = True  # Fusion never leaves seam faces
    _save_meta(
        feature,
        {
            "v": 1,
            "inside": float(opts["inside"]),
            "outside": float(opts["outside"]),
            "inside_formula": formulas.get("inside", ""),
            "outside_formula": formulas.get("outside", ""),
            "tangent": bool(opts.get("tangent", True)),
        },
    )


def read(feature):
    """(base, names, options, formulas) of an existing shell, in the form make() takes."""
    meta = load_meta(feature)
    opts = default_options()
    formulas = {
        "inside": meta.get("inside_formula", ""),
        "outside": meta.get("outside_formula", ""),
    }
    if feature.TypeId == NATIVE:
        link = feature.Base
        base = feature.BaseFeature or (link[0] if link else None)
        names = [s.lstrip("?") for s in (link[1] if link else []) if s]
        key = "inside" if feature.Reversed else "outside"
        other = "outside" if key == "inside" else "inside"
        value = feature.Value.Value
        opts.update(
            {
                "direction": key,
                key: value,
                other: float(meta.get(other, value)),
                "shell_type": "sharp" if feature.Join == "Intersection" else "rounded",
            }
        )
        formulas[key] = formula_of(feature, "Value")
    else:
        link = feature.Faces
        base = feature.BaseFeature or (link[0] if link else None)
        names = [s.lstrip("?") for s in (link[1] if link else []) if s]
        opts.update(_fp_options(feature))
        formulas["inside"] = formula_of(feature, "InsideThickness")
        formulas["outside"] = formula_of(feature, "OutsideThickness")
    opts["tangent"] = bool(meta.get("tangent", True))
    return base, names, opts, formulas


def update(feature, base, names, options, formulas=None):
    """Change a shell. Returns the feature: a new object when the change needs the other
    kind (FreeCAD's Thickness <-> SciForge's ShellFeature); it takes the old one's place
    and label, and later steps are moved over to it."""
    opts = with_defaults(options)
    own = needs_own_feature(list(names or []), opts)
    if own == is_own(feature):
        apply(feature, base, names, opts, formulas)
        return feature
    return _replace(feature, base, names, opts, formulas)


def _replace(old, base, names, options, formulas):
    body = owner_body(old)
    if body is None:
        raise ShellError("The shell is not in a body.")
    doc = old.Document
    was_tip = body.Tip is old
    label = old.Label
    new = make(body, base, names, options, before=old, formulas=formulas)
    _compute(new)  # its faces must exist to point the later steps at them
    _repoint(old, new)
    from . import modify_bodies

    modify_bodies.move_followers(old, new)  # its steps in other bodies (modify-2)
    try:
        body.removeObject(old)
    except Exception:
        pass
    doc.removeObject(old.Name)
    try:
        new.Label = label
    except Exception:
        pass
    if was_tip:
        body.Tip = new
    show_tip(body)
    return new


def _compute(feature):
    """Compute one new feature now (quietly: the dialog already tried its values)."""
    try:
        from . import preview

        with preview.quiet():
            feature.recompute()
    except Exception:
        pass


def _is_subs(value):
    return isinstance(value, (list, tuple)) and all(isinstance(s, str) for s in value)


def _swap(value, old, new, rename=None):
    if value is old:
        return new, True
    if (
        isinstance(value, tuple)
        and len(value) == 2
        and value[0] is old
        and _is_subs(value[1])
        and rename is not None
    ):
        subs = [rename(s) for s in value[1]]
        return (new, type(value[1])(subs)), True
    if isinstance(value, tuple):
        items = [_swap(v, old, new, rename) for v in value]
        return tuple(v for v, _c in items), any(c for _v, c in items)
    if isinstance(value, list):
        items = [_swap(v, old, new, rename) for v in value]
        return [v for v, _c in items], any(c for _v, c in items)
    return value, False


def _renamer(old, new):
    """Old element name -> the same face/edge/corner on the new feature (found by where
    it is: the two kinds of feature number their faces differently)."""
    from . import follow

    def rename(sub):
        name = (sub or "").split(".")[-1].lstrip("?")
        if not name.startswith(("Face", "Edge", "Vertex")):
            return sub
        try:
            element = old.Shape.getElement(name)
            found = follow.find(new.Shape, element)
        except Exception:
            found = None
        return found or name

    return rename


def _repoint(old, new):
    """Steps that used `old` (a sketch on one of its faces, a later fillet...) use `new`,
    and the same faces of it."""
    rename = _renamer(old, new)
    for dep in list(old.InList):
        if dep is new or dep.TypeId == "PartDesign::Body":
            continue
        for prop in dep.PropertiesList:
            try:
                kind = dep.getTypeIdOfProperty(prop)
            except Exception:
                continue
            if not kind.startswith(("App::PropertyLink", "App::PropertyXLink")):
                continue
            try:
                value, changed = _swap(getattr(dep, prop), old, new, rename)
                if changed:
                    setattr(dep, prop, value)
            except Exception:
                pass


def show_tip(body):
    """FreeCAD draws a body through its Tip, and a new feature hides the one before it; a
    feature removed by code left the new Tip hidden (the part vanished from the view)."""
    tip = body.Tip if body is not None else None
    if tip is None:
        return
    try:
        import FreeCAD as App

        if App.GuiUp and tip.ViewObject is not None:
            tip.ViewObject.Visibility = True
        else:
            tip.Visibility = True
    except Exception:
        pass


def remove(feature):
    """Delete a shell made by the dialog (its preview), showing the step before it."""
    from . import modify_bodies

    modify_bodies.remove_all(feature)  # its steps in other bodies (modify-2)
    body = owner_body(feature)
    doc = feature.Document
    base = feature.BaseFeature
    was_tip = body is not None and body.Tip is feature
    try:
        if body is not None:
            body.removeObject(feature)
    except Exception:
        pass
    try:
        doc.removeObject(feature.Name)
    except Exception:
        pass
    if body is not None and was_tip:
        if body.Tip is None and base is not None:
            body.Tip = base
        show_tip(body)


def friendly(text):
    """FreeCAD's error text for a failed Thickness, in plain words."""
    low = (text or "").lower()
    if "thick solid" in low or "command not done" in low or "failed" in low:
        return "The shell cannot be made with these faces and this thickness. Try a thinner wall."
    if "invalid face reference" in low:
        return "A picked face no longer exists (an earlier step changed the part). Pick it again."
    return text
