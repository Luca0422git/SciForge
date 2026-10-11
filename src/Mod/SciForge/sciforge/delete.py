# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Delete (Del) on what is selected: the document side, no Qt. delete_ui.py runs
it from the Del key, the ribbon and the marking menu.

What a selection means (Fusion):
  a body (browser)                     the body and everything in it
  a step: feature, sketch, plane...    that step; the steps after it keep working where they
                                       can (the body's history is re-linked around it, the
                                       Tip moves back, a sketch that sat on a face of it stays
                                       where it was); the ones that cannot are shown red or
                                       yellow in the timeline with the reason, never as
                                       errors in the Report view
  faces of a body (3D view)            a "Delete Face" step: the faces are removed and the
                                       faces around them grow to close the gap (OpenCASCADE
                                       defeaturing); refused with the reason when they cannot
  curves of a sketch (3D view)         those curves are deleted from the sketch

Steps that made bodies take them along: deleting a Split Body deletes the bodies it split
off, deleting a copy (Move/Copy with Create Copy) deletes the copy. A body that others were
copied or split from can be deleted: its copies keep their shape.

Everything is one undo step.
"""
import FreeCAD as App

from . import bodies

TYPE = "PartDesign::FeaturePython"
SCIFORGE_TYPE = "DeleteFace"
WARNING = "SciForgeWarning"
STEP_TYPES_NOT_DELETABLE = ("App::Origin", "App::Line", "App::Plane", "App::Point", "App::VarSet")


class DeleteError(ValueError):
    """Nothing can be deleted as asked; the message says why."""


# -- what the selection means --------------------------------------------------------------------
def plan(entries):
    """{"bodies": [...], "steps": [...], "faces": {feature: [FaceN]}, "curves": {sketch: [i]},
    "refused": "why"} for selection entries [(object, short element name)]."""
    found = {"bodies": [], "steps": [], "faces": {}, "curves": {}, "refused": ""}
    for obj, short in entries:
        if obj is None:
            continue
        if obj.TypeId in STEP_TYPES_NOT_DELETABLE or getattr(obj, "Role", None):
            found["refused"] = "The origin and its planes and axes cannot be deleted."
            continue
        if bodies.is_body(obj) and not short:
            if obj not in found["bodies"]:
                found["bodies"].append(obj)
            continue
        if obj.TypeId == "Sketcher::SketchObject" and short.startswith("Edge"):
            index = int(short[4:]) - 1
            found["curves"].setdefault(obj, [])
            if index not in found["curves"][obj]:
                found["curves"][obj].append(index)
            continue
        if obj.TypeId == "Sketcher::SketchObject" and short:
            found["refused"] = "Points of a sketch are deleted with the sketch's curves."
            continue
        if short.startswith("Face") and bodies.body_of(obj) is not None:
            body = bodies.body_of(obj)
            feature = body.Tip
            name = short if obj in (body, feature) else _same_face(obj, short, feature)
            if feature is None or not name:
                found["refused"] = "That face is not on the body as it is now."
                continue
            found["faces"].setdefault(feature, [])
            if name not in found["faces"][feature]:
                found["faces"][feature].append(name)
            continue
        if short.startswith(("Edge", "Vertex")):
            found["refused"] = (
                "Edges and corners of a solid cannot be deleted. Select a face, a body, a "
                "sketch or a step."
            )
            continue
        if not short and obj not in found["steps"]:
            found["steps"].append(obj)
    inside = {b.Name for b in found["bodies"]}
    found["steps"] = [s for s in found["steps"] if not _in_bodies(s, inside)]
    found["faces"] = {f: n for f, n in found["faces"].items() if not _in_bodies(f, inside)}
    return found


def _same_face(obj, short, feature):
    """The name of face `short` of `obj` on `feature` (the body as it is now), or ''."""
    try:
        face = obj.Shape.getElement(short)
    except Exception:
        return ""
    point = face.CenterOfMass
    for i, other in enumerate(feature.Shape.Faces, start=1):
        if abs(other.Area - face.Area) > 1e-6 * max(1.0, face.Area):
            continue
        if other.distToShape(Part_vertex(point))[0] < 1e-6:
            return "Face%d" % i
    return ""


def Part_vertex(point):
    import Part

    return Part.Vertex(point)


def _in_bodies(obj, names):
    body = bodies.body_of(obj)
    return body is not None and body.Name in names


def is_empty(found):
    return not (found["bodies"] or found["steps"] or found["faces"] or found["curves"])


# -- the deleting ---------------------------------------------------------------------------------
def _objects_in(value):
    if value is None:
        return []
    if hasattr(value, "TypeId") and hasattr(value, "Name"):
        return [value]
    if isinstance(value, (list, tuple)):
        out = []
        for v in value:
            out += _objects_in(v)
        return out
    return []


def _warn_step(obj, text):
    bodies.add_prop(obj, "App::PropertyString", WARNING, "Base")
    setattr(obj, WARNING, text)


def _keep_attached(doc, gone):
    """Sketches and planes that sat on something deleted stay where they are (Fusion), with
    a warning in the timeline, instead of failing."""
    for obj in doc.Objects:
        if obj.Name in gone:
            continue
        support = getattr(obj, "AttachmentSupport", None)
        if not support or not any(o.Name in gone for o in _objects_in(support)):
            continue
        mode = getattr(obj, "MapMode", None)
        if mode and mode != "Deactivated":
            obj.MapMode = "Deactivated"  # keeps its current placement
        _warn_step(obj, "Lost the face or plane it was on (deleted); it stays where it was.")


def _profile_sketch(obj):
    for prop in ("Profile", "Sketch"):
        if prop not in obj.PropertiesList:
            continue
        for o in _objects_in(getattr(obj, prop)):
            if o.TypeId == "Sketcher::SketchObject":
                return o
    return None


def _show_profiles(doc, gone):
    """A sketch whose extrude is deleted shows again (Fusion)."""
    for name in gone:
        obj = doc.getObject(name)
        if obj is None:
            continue
        sketch = _profile_sketch(obj)
        if sketch is None or sketch.Name in gone:
            continue
        users = [
            o
            for o in sketch.InList
            if o.Name not in gone and _profile_sketch(o) is sketch and o is not obj
        ]
        if not users:
            bodies.set_shown(sketch, True)


def extra_steps(steps):
    """Steps that go with the ones deleted: the bodies a split or copy made."""
    from . import move, split

    more_bodies = []
    for step in steps:
        if split.is_split(step):
            more_bodies += split.piece_bodies(step)
        if move.is_copy(step):
            body = move.copy_body(step)
            if body is not None:
                more_bodies.append(body)
    return more_bodies


def _same_element(shape, element, kind):
    """Name of the element of `shape` that is geometrically `element` (same place), or ''."""
    import Part

    tol = 1e-6
    if kind == "Vertex":
        for i, v in enumerate(shape.Vertexes, start=1):
            if (v.Point - element.Point).Length < tol:
                return "Vertex%d" % i
        return ""
    if kind == "Edge":
        mid = element.valueAt((element.FirstParameter + element.LastParameter) / 2.0)
        for i, e in enumerate(shape.Edges, start=1):
            if abs(e.Length - element.Length) > tol * max(1.0, element.Length):
                continue
            if e.distToShape(Part.Vertex(mid))[0] < tol:
                return "Edge%d" % i
        return ""
    if kind == "Face":
        center = element.CenterOfMass
        for i, f in enumerate(shape.Faces, start=1):
            if abs(f.Area - element.Area) > tol * max(1.0, element.Area):
                continue
            if (f.CenterOfMass - center).Length < tol:
                return "Face%d" % i
        return ""
    return ""


def _relink_to_base(doc, step, gone):
    """Steps that use edges/faces of `step` (a fillet on its edges, a sketch on its face) are
    pointed at the same edges/faces of the step before it, where those exist unchanged: they
    then keep working after the delete (Fusion re-finds geometry the same way)."""
    base = getattr(step, "BaseFeature", None)
    if base is None or base.Shape.isNull():
        return
    for obj in list(step.InList):
        if obj.Name in gone or obj is step:
            continue
        for prop in obj.PropertiesList:
            try:
                kind = obj.getTypeIdOfProperty(prop)
            except Exception:
                continue
            if not kind.startswith("App::PropertyLinkSub") or prop in ("BaseFeature",):
                continue
            try:
                value = getattr(obj, prop)
            except Exception:
                continue
            entries = value if isinstance(value, list) else ([value] if value else [])
            changed, out = False, []
            for entry in entries:
                if not entry:
                    continue
                target, subs = entry[0], entry[1]
                subs = [subs] if isinstance(subs, str) else list(subs)
                if target is not step:
                    out.append((target, subs))
                    continue
                mapped = []
                for sub in subs:
                    elem_kind = sub.rstrip("0123456789")
                    try:
                        element = step.Shape.getElement(sub)
                    except Exception:
                        mapped = None
                        break
                    name = _same_element(base.Shape, element, elem_kind) if sub else ""
                    if sub and not name:
                        mapped = None
                        break
                    mapped.append(name)
                if mapped is None:
                    out.append((target, subs))
                    continue
                out.append((base, mapped))
                changed = True
            if not changed:
                continue
            try:
                if "List" in kind:
                    setattr(obj, prop, out)
                else:
                    setattr(obj, prop, out[0])
            except Exception:
                pass


def delete_steps(doc, steps):
    """Delete steps (no transaction of its own). Later steps of the body are re-linked
    around each one by PartDesign; the body's Tip moves back if it was deleted."""
    from . import move, split

    steps = [s for s in steps if bodies.alive(s)]
    gone = {s.Name for s in steps}
    extra = extra_steps(steps)
    for body in extra:
        gone.add(body.Name)
        gone.update(o.Name for o in body.Group)
    for step in sorted(steps, key=lambda o: -o.ID):
        _relink_to_base(doc, step, gone)
        _reroute_users(doc, step, gone)
    _freeze_users(doc, gone)
    _keep_attached(doc, gone)
    _show_profiles(doc, gone)
    for body in extra:
        bodies.remove_body(body)
    # Later steps first, so each removal re-links the history of what is left.
    for step in sorted(steps, key=lambda o: -o.ID):
        if not bodies.alive(step):
            continue
        if split.is_split(step):
            split.remove(step)
        elif move.is_copy(step):
            move.remove(step)
        else:
            bodies.remove_step(step)


def delete_bodies(doc, targets):
    """Delete bodies with everything in them (no transaction of its own)."""
    targets = [b for b in targets if bodies.alive(b)]
    gone = set()
    for body in targets:
        gone.add(body.Name)
        gone.update(o.Name for o in body.Group)
    # Steps of these bodies that made other bodies take them along (a split's pieces).
    from . import split

    for body in targets:
        for step in body.Group:
            if split.is_split(step):
                for piece in split.pieces_of(step):
                    piece.Split = None  # the pieces keep their shape (the source is gone)
    _keep_attached(doc, gone)
    _freeze_users(doc, gone)
    from . import move

    for body in targets:
        base = body.BaseFeature
        bodies.remove_body(body)
        # The hidden first step of a copied or split-off body goes with it.
        if base is not None and bodies.alive(base) and (move.is_copy(base) or split.is_piece(base)):
            try:
                doc.removeObject(base.Name)
            except Exception:
                pass


def _reroute_users(doc, step, gone):
    """A Combine that used the deleted step as a tool, or a copy made from it, uses the
    step before it instead (the tool body as it was just before that step)."""
    from . import combine, move

    base = getattr(step, "BaseFeature", None)
    if base is None or base.Name in gone:
        return
    for obj in list(step.InList):
        if obj.Name in gone:
            continue
        try:
            if combine.is_combine(obj) and step in obj.Tools:
                obj.Tools = [base if t is step else t for t in obj.Tools]
            elif combine.is_combine(obj) and obj.NewBody and obj.Target is step:
                obj.Target = base
            elif move.is_copy(obj) and obj.Source is step:
                obj.Source = base
        except Exception:
            pass


def _freeze_users(doc, gone):
    """Combines (outside what is deleted) that use a deleted body as a tool keep it as it
    was: they go on giving the same result."""
    from . import combine

    for obj in doc.Objects:
        if obj.Name in gone or not combine.is_combine(obj):
            continue
        try:
            combine.freeze_tools(obj, gone)
        except Exception:
            pass


def delete_curves(sketch, indices):
    """Delete curves from a sketch (with their constraints)."""
    indices = sorted(set(i for i in indices if 0 <= i < sketch.GeometryCount))
    if not indices:
        return
    sketch.delGeometries(indices)


def run(doc, found, title="Delete"):
    """Do what plan() found, as one undo step, then recompute without FreeCAD's error
    output (failures are shown in the timeline). Returns the Delete Face steps made."""
    from . import timeline_ops

    if is_empty(found):
        raise DeleteError(found.get("refused") or "Select what to delete.")
    if not doc.UndoMode:
        doc.UndoMode = 1
    doc.openTransaction(title)
    made = []
    try:
        for sketch, indices in found["curves"].items():
            delete_curves(sketch, indices)
        for feature, names in found["faces"].items():
            made.append(delete_faces(feature, names))
        if found["steps"]:
            delete_steps(doc, found["steps"])
        if found["bodies"]:
            delete_bodies(doc, found["bodies"])
        timeline_ops.recompute(doc)
        for step in made:
            if bodies.alive(step) and "Invalid" in list(step.State):
                raise DeleteError(_face_failure(step))
    except Exception:
        doc.abortTransaction()
        timeline_ops.recompute(doc)
        raise
    doc.commitTransaction()
    try:
        App.closeActiveTransaction()
    except Exception:
        pass
    return made


# -- orphans (a step deleted from the timeline or the browser) -----------------------------------------
def orphans(doc):
    """Bodies left behind by a deleted Split Body or copy step."""
    from . import move, split

    found = []
    for piece in split.orphan_pieces(doc):
        body = split.piece_body(piece)
        if body is not None:
            found.append((body, piece))
    for body in move.orphan_copies(doc):
        found.append((body, None))
    for step in doc.Objects:  # a copied body deleted from the browser: its copy step goes too
        if move.is_copy(step) and move.copy_body(step) is None:
            found.append((None, step))
    return found


def remove_orphans(doc):
    for body, piece in orphans(doc):
        if body is not None:
            bodies.remove_body(body)
        if piece is not None and bodies.alive(piece):
            try:
                doc.removeObject(piece.Name)
            except Exception:
                pass
    return True


# -- Delete Face ------------------------------------------------------------------------------------
class DeleteFaceFeature:
    """Removes faces and grows the faces around them to close the gap. Saved as
    "sciforge.delete.DeleteFaceFeature"."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        if "Faces" not in obj.PropertiesList:
            obj.addProperty("App::PropertyLinkSub", "Faces", "Delete Face", "The faces removed")
        if "Refine" not in obj.PropertiesList:
            obj.addProperty("App::PropertyBool", "Refine", "Delete Face", "Merge faces")
            obj.Refine = True
        bodies.mark(obj, SCIFORGE_TYPE)

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        try:
            self._build(obj)
        except Exception:
            bodies.pass_through(obj)  # the faces stay (as before this step), the step red
            raise

    def _build(self, obj):
        base = obj.BaseFeature
        if base is None or base.Shape.isNull() or not base.Shape.Solids:
            raise DeleteError("There is no solid before this step.")
        link = obj.Faces
        if not link or not link[1]:
            raise DeleteError("No faces to delete.")
        source, names = link[0], list(link[1])
        faces = []
        for name in names:
            try:
                faces.append(source.Shape.getElement(name))
            except Exception:
                raise DeleteError(
                    "The face %s no longer exists (an earlier step changed the model)." % name
                )
        obj.Shape = heal(base.Shape, faces, refine=bool(obj.Refine))

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def heal(shape, faces, refine=True):
    """The solid without `faces`, the faces around them grown to close it."""
    if len(faces) >= len(shape.Faces):
        raise DeleteError("Deleting every face would leave nothing.")
    try:
        healed = shape.defeaturing(faces)
    except Exception as exc:
        raise DeleteError(
            "These faces cannot be deleted: the faces around them cannot be extended to close "
            "the gap (%s)." % exc
        )
    if healed.isNull() or not healed.Solids or not healed.isValid():
        raise DeleteError(
            "These faces cannot be deleted: the faces around them cannot be extended to close "
            "the gap."
        )
    if len(healed.Faces) == len(shape.Faces) and abs(healed.Volume - shape.Volume) < 1e-9:
        raise DeleteError(
            "These faces cannot be deleted: the faces around them cannot be extended to close "
            "the gap."
        )
    if refine:
        try:
            healed = healed.removeSplitter()
        except Exception:
            pass
    return healed


def delete_faces(feature, names):
    """A Delete Face step at the end of the feature's body (no transaction of its own)."""
    body = bodies.body_of(feature)
    faces = [feature.Shape.getElement(n) for n in names]
    heal(feature.Shape, faces)  # refuse before anything is added
    obj = bodies.insert_after_tip(body, TYPE, "DeleteFace")
    DeleteFaceFeature(obj)
    obj.Faces = (feature, list(names))
    if App.GuiUp:
        try:
            from .bodies_gui import StepViewProvider

            StepViewProvider(obj.ViewObject)
        except Exception:
            pass
    return obj


def _face_failure(step):
    try:
        text = step.getStatusString()
    except Exception:
        text = ""
    return text or "These faces cannot be deleted."
