# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Silhouette Split (Modify > Silhouette Split): the document side, no Qt.
silhouette_ui.py is the dialog; the golden-model builder calls build() too.

Options (dict, see DEFAULTS):
  direction   (object, sub) the view direction: an origin axis or construction axis, a
              straight edge, a flat face or a plane (its normal)
  body        the body to split (Target Body)
  operation   "faces"  Split Faces Only: the faces are divided along the body's outline seen
                       from that direction; it stays one body
              "body"   Split Solid Body: the body is split in two at the outline, which must
                       lie in one plane (Fusion's rule)
              "shelled" Split Shelled Body: a shelled (hollow) body split in two along the
                       outline (a flat outline: its plane; else the outline swept along the
                       view direction)

The outline is OpenCASCADE's silhouette ("outline" reflect lines, kept on the body's own
surface). What is built: a "Silhouette Split" step (SciForgeType "SilhouetteSplit",
SilhouetteSplitFeature) at the history marker; the split operations keep one piece in the
body (the biggest) and give each other piece a new body, exactly like Split Body (split.py
pieces, which follow the step when earlier steps change).
"""

import FreeCAD as App

from . import bodies, split

TYPE = "PartDesign::FeaturePython"
SCIFORGE_TYPE = "SilhouetteSplit"
OPERATIONS = ("faces", "body", "shelled")
OPERATION_LABELS = {
    "faces": "Split Faces Only",
    "body": "Split Solid Body",
    "shelled": "Split Shelled Body",
}
PLANE_TYPES = ("App::Plane", "PartDesign::Plane", "Part::DatumPlane")
LINE_TYPES = ("App::Line", "PartDesign::Line", "Part::DatumLine")
DEFAULTS = {"direction": None, "body": None, "operation": "faces"}
META = "SciForgeSplit"
TOL = 1e-6


class SilhouetteError(ValueError):
    """The split cannot be made as asked; the message says why and what to do."""


class NeedsPick(SilhouetteError):
    """A selection box still waits for its click."""


def with_defaults(options):
    merged = dict(DEFAULTS)
    merged.update(options or {})
    return merged


def is_silhouette(obj):
    return bodies.kind(obj) == SCIFORGE_TYPE


# -- geometry ----------------------------------------------------------------------------------
def view_direction(ref):
    """The view direction (design coordinates) of an axis, a straight edge, a flat face or a
    plane, or None."""
    from . import split_face

    return split_face.direction_of(ref)


def outline(shape, direction):
    """The body's outline seen along ``direction``: edges lying on the body."""
    direction = App.Vector(direction).normalize()
    up = (
        App.Vector(0, 1, 0)
        if abs(direction.dot(App.Vector(0, 1, 0))) < 0.9
        else App.Vector(1, 0, 0)
    )
    try:
        lines = shape.reflectLines(direction, shape.BoundBox.Center, up, "OutLine", True, True)
    except Exception as exc:
        raise SilhouetteError("The outline of the body cannot be found: %s" % exc)
    edges = [e for e in lines.Edges if e.Length > 1e-6]
    if not edges:
        raise SilhouetteError(
            "The body has no outline from that direction to split along (flat faces seen "
            "edge-on only). Pick another direction, or use Split Face."
        )
    return edges


def _plane_of(edges):
    import Part

    try:
        plane = Part.makeCompound(edges).findPlane()
    except Exception:
        plane = None
    return plane


def _faces_split(shape, edges):
    import Part

    try:
        result, _map = shape.generalFuse([Part.makeCompound(edges)])
    except Exception as exc:
        raise SilhouetteError("The faces cannot be split along the outline: %s" % exc)
    solids = [s for s in result.Solids if s.Volume > TOL]
    if len(solids) != len(shape.Solids) or not solids:
        raise SilhouetteError("Splitting the faces broke the solid.")
    out = solids[0] if len(solids) == 1 else Part.makeCompound(solids)
    if not out.isValid():
        raise SilhouetteError("Splitting the faces gave an invalid solid.")
    return out


def _big_plane(plane, around):
    size = max(around.BoundBox.DiagonalLength, 1.0) * 4.0 + 50.0
    u, v = plane.parameter(around.BoundBox.Center)
    return plane.toShape(u - size, u + size, v - size, v + size)


def _parting_surface(edges, direction, around):
    import Part

    size = max(around.BoundBox.DiagonalLength, 1.0) * 4.0 + 50.0
    swept = []
    for edge in edges:
        moved = edge.copy()
        moved.translate(direction * -size)
        try:
            swept.append(moved.extrude(direction * (2 * size)))
        except Exception:
            continue
    if not swept:
        raise SilhouetteError("No parting surface can be made from the outline.")
    return Part.makeCompound(swept)


def is_shelled(shape):
    """A hollow body: a solid with more than one shell (Shell's inside wall)."""
    try:
        return any(len(s.Shells) > 1 for s in shape.Solids)
    except Exception:
        return False


def compute(shape, direction, operation):
    """(the body's own solid, [other pieces]) for the operation, design coordinates."""
    edges = outline(shape, direction)
    if operation == "faces":
        return _faces_split(shape, edges), []
    if operation == "shelled" and not is_shelled(shape):
        raise SilhouetteError(
            "Split Shelled Body needs a shelled (hollow) body: use Shell first, or Split "
            "Solid Body."
        )
    plane = _plane_of(edges)
    if plane is not None:
        tool = _big_plane(plane, shape)
    elif operation == "body":
        raise SilhouetteError(
            "The outline does not lie in one plane, so the body cannot be split along it "
            "(Fusion's rule). Use Split Faces Only, or Split Body with a plane."
        )
    else:
        tool = _parting_surface(edges, App.Vector(direction).normalize(), shape)
    pieces = split.split_shape(shape, tool)
    if len(pieces) < 2:
        raise SilhouetteError("The outline does not divide the body in two.")
    pieces = split.order(pieces)
    return pieces[0], pieces[1:]


# -- the step ----------------------------------------------------------------------------------
class SilhouetteSplitFeature:
    """Saved as "sciforge.silhouette.SilhouetteSplitFeature": keep the name and properties."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, "Silhouette Split", doc)
                return True
            return False

        add("App::PropertyLinkSubGlobal", "Direction", "The view direction")
        if add("App::PropertyEnumeration", "Operation", "What is split"):
            obj.Operation = list(OPERATIONS)
            obj.Operation = "faces"
        if "OtherPieces" not in obj.PropertiesList:
            # The pieces that went to new bodies (design coordinates), read by split.SplitPiece.
            obj.addProperty(
                "Part::PropertyPartShape", "OtherPieces", "Silhouette Split", "", 4 | 16
            )
        bodies.mark(obj, SCIFORGE_TYPE)

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        import Part

        try:
            body = bodies.body_of(obj)
            base = obj.BaseFeature
            if base is None or base.Shape.isNull() or not base.Shape.Solids:
                raise SilhouetteError("There is no solid before this step to split.")
            link = obj.Direction
            if not link or link[0] is None:
                raise SilhouetteError(
                    "Its view direction is gone (deleted?). Edit the Silhouette Split and pick "
                    "a direction."
                )
            direction = view_direction((link[0], (list(link[1]) or [""])[0]))
            if direction is None:
                raise SilhouetteError(
                    "The view direction must be an axis, a straight edge, a flat face or a "
                    "plane."
                )
            shape = bodies.global_shape(base)
            kept, others = compute(shape, direction, obj.Operation)
            meta = bodies.load_meta(obj, META)
            if others and meta.get("centers"):
                ordered = split.order([kept] + others, meta.get("centers"))
                kept, others = ordered[0], ordered[1:]
            obj.Shape = bodies.to_local(kept, body)
            obj.OtherPieces = Part.makeCompound(others) if others else Part.Shape()
        except Exception:
            bodies.pass_through(obj)
            raise

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def check(options):
    if options["direction"] is None:
        raise NeedsPick(
            "Select the view direction: an axis, a straight edge, a flat face or a plane."
        )
    if options["body"] is None:
        raise NeedsPick("Select the body to split.")
    if options["operation"] not in OPERATIONS:
        raise SilhouetteError("Pick what to split.")
    if not bodies.has_solid(options["body"]):
        raise SilhouetteError("%s has no solid to split." % options["body"].Label)


def preview_pieces(options, feature=None):
    body = options["body"]
    base = feature.BaseFeature if feature is not None else body.Tip
    direction = view_direction(options["direction"])
    if direction is None:
        raise SilhouetteError(
            "The view direction must be an axis, a straight edge, a flat face or a plane."
        )
    kept, others = compute(bodies.global_shape(base), direction, options["operation"])
    return [kept] + others


def build(options, feature=None, name="SilhouetteSplit"):
    """Create the step (or update ``feature``); the split operations add a body per extra
    piece (split.py's pieces). Returns the step."""
    options = with_defaults(options)
    check(options)
    body = options["body"]
    if feature is not None and bodies.alive(feature) and bodies.body_of(feature) is not body:
        remove(feature)
        feature = None
    pieces = preview_pieces(options, feature if bodies.alive(feature) else None)
    if feature is None or not bodies.alive(feature):
        feature = bodies.insert_after_tip(body, TYPE, name)
        SilhouetteSplitFeature(feature)
        _attach_view_provider(feature)
    obj, sub = options["direction"]
    current = feature.Direction
    if not current or current[0] is not obj or (list(current[1]) or [""])[0] != sub:
        feature.Direction = (obj, [sub])
    if feature.Operation != options["operation"]:
        feature.Operation = options["operation"]
    centers = [list(p.CenterOfMass) for p in pieces] if len(pieces) > 1 else []
    bodies.save_meta(feature, META, {"v": 1, "centers": centers})
    split._sync_bodies(feature, len(pieces) - 1)
    return feature


def remove(feature):
    split.remove(feature)


def read(feature):
    link = feature.Direction
    return with_defaults(
        {
            "direction": (link[0], (list(link[1]) or [""])[0]) if link else None,
            "body": bodies.body_of(feature),
            "operation": feature.Operation,
        }
    )


def _attach_view_provider(obj):
    if not App.GuiUp:
        return
    try:
        from .bodies_gui import StepViewProvider

        StepViewProvider(obj.ViewObject)
    except Exception:
        pass
