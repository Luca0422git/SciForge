# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's "Auto project geometry on active sketch plane": a new sketch on a flat face of
the part starts with the face's edges projected into it, as purple curves that make
profiles with what is drawn against them (Luca: "When sketching on a face of a body, the
edges of the face should already be projected").

FreeCAD projects every edge of a face it is given as one external reference
(SketchObject::addExternal with a face); `defining` makes the curves profile-making.
No Qt here: Create Sketch (sketch_ui.create_sketch) and the golden-model builder use it.
"""

import FreeCAD as App

from . import log

PARAM = ("User parameter:BaseApp/Preferences/Mod/SciForge/SketchInference", "AutoProject")


def enabled():
    """Preferences > Design > "Auto project the face's edges when sketching on a face"
    (default on: Luca's wish; Fusion's own option exists and is off by default)."""
    try:
        return App.ParamGet(PARAM[0]).GetBool(PARAM[1], True)
    except Exception:
        return True


def auto_project(sketch, target, at=None):
    """A sketch on a flat face gets the face's edges as projected (purple) curves that make
    profiles, like Fusion's "Auto project geometry on active sketch plane". One external
    reference to the whole face (FreeCAD projects every edge of a face it is given).

    `target` is the face as it is now, on the earliest step that has it with this outline
    (sketch_ui.create_sketch): a hole drilled in the face later is left out (suppressing or
    deleting it leaves the curves alone, fixsketch_hole D; its edges are projected with P),
    while a face a later Draft or fillet reshaped is projected as it is after it (Luca,
    2026-10-23). `at`: a point of the face (body coordinates), kept so that follow() finds
    the face again when the steps before the sketch change. Never raises: a face that
    cannot be projected (another body's) leaves the sketch without, with a note in the
    log. Returns the number of curves projected."""
    if not target[1].startswith("Face"):
        return 0
    before = len(sketch.ExternalGeo)
    try:
        sketch.addExternal(target[0].Name, target[1], True, False)
        sketch.Document.recompute()
    except Exception as exc:
        log("sketch: the face's edges were not projected (%s: %s)" % (target[1], exc))
        return 0
    count = len(sketch.ExternalGeo) - before
    remember(sketch, list(sketch.ExternalGeo)[before:])
    if at is not None:
        remember_anchor(sketch, at)
    log(
        "sketch: %d edge(s) of %s.%s projected (Auto project)" % (count, target[0].Label, target[1])
    )
    return count


PROPERTY = "SciForgeAutoProjected"


def remember(sketch, geos):
    """Keep the ids of the curves Auto project made (a hidden property of the sketch, kept
    in the file): the area only they bound is the face itself (sketch_regions.face_areas),
    while curves the person projects with P make profiles as usual."""
    try:
        import Sketcher

        ids = [Sketcher.ExternalGeometryFacade(g).Id for g in geos]
        if PROPERTY not in sketch.PropertiesList:
            sketch.addProperty(
                "App::PropertyIntegerList",
                PROPERTY,
                "SciForge",
                "Ids of the projected curves Auto project made (the face's own edges)",
            )
            sketch.setEditorMode(PROPERTY, 2)
        setattr(sketch, PROPERTY, ids)
    except Exception as exc:
        log("sketch: Auto project ids not kept: %s" % exc)


ANCHOR = "SciForgeAutoProjectedAt"


def remember_anchor(sketch, point):
    """Keep the point of the face Create Sketch was clicked on (`point` in body coordinates;
    kept in the sketch's own, so it moves with the face: a hidden property kept in the
    file): follow() finds the face there again."""
    try:
        if ANCHOR not in sketch.PropertiesList:
            sketch.addProperty(
                "App::PropertyVector",
                ANCHOR,
                "SciForge",
                "A point of the face whose edges Auto project made (sketch coordinates)",
            )
            sketch.setEditorMode(ANCHOR, 2)
        setattr(sketch, ANCHOR, sketch.Placement.inverse().multVec(App.Vector(point)))
    except Exception as exc:
        log("sketch: Auto project point not kept: %s" % exc)


def auto_ids(sketch):
    """The ids of the curves Auto project made in this sketch (remember), or set()."""
    try:
        return set(getattr(sketch, PROPERTY, ()) or ())
    except Exception:
        return set()


def missing_edges(sketch, obj, sub):
    """(edges of the part's element `sub` of `obj` ("FaceN": its edges, "EdgeN": itself)
    that the sketch does not have yet, how many it has). An edge is in the sketch when it
    is referenced itself or lies on an edge of a projected face or edge (Auto project took
    the face from an earlier step, sketch_ui._earliest: the same edges under other names).
    ([], 0) for anything else."""
    try:
        shape = obj.Shape
        if sub.startswith("Face"):
            names = []
            element = shape.getElement(sub)
            for edge in element.Edges:
                for i, e in enumerate(shape.Edges, start=1):
                    if e.isSame(edge):
                        names.append("Edge%d" % i)
                        break
        elif sub.startswith("Edge"):
            names = [sub]
        else:
            return [], 0
        known = []  # edges the sketch has: (object, edge shape)
        for ref_obj, subs in sketch.ExternalGeometry:
            for ref in subs:
                if ref.startswith("Face"):
                    known += list(ref_obj.Shape.getElement(ref).Edges)
                elif ref.startswith("Edge"):
                    known.append(ref_obj.Shape.getElement(ref))
        missing = []
        for name in names:
            edge = shape.getElement(name)
            first, last = edge.ParameterRange
            points = [edge.valueAt(first + (last - first) * k) for k in (0.0, 0.5, 1.0)]
            if not all(_on(known, p) for p in points):
                missing.append(name)
        return missing, len(names) - len(missing)
    except Exception:
        return [], 0


def add_edges(sketch, obj, names):
    """Project the part's edges `names` of `obj` into the sketch (defining: they make
    profiles) in one undo step "Project". Returns how many curves came in."""
    doc = sketch.Document
    before = len(sketch.ExternalGeo)
    doc.openTransaction("Project")
    try:
        for name in names:
            sketch.addExternal(obj.Name, name, True, False)
        doc.recompute()
    except Exception:
        doc.abortTransaction()
        raise
    doc.commitTransaction()
    return len(sketch.ExternalGeo) - before


def _on(edges, point, tolerance=1e-6):
    import Part

    vertex = Part.Vertex(point)
    return any(e.distToShape(vertex)[0] <= tolerance for e in edges)


# -- the face as it is at the sketch's place ---------------------------------------------------
def source(sketch):
    """(object, plain sub or None) the curves Auto project made are projected from. The sub
    is None when the link is gone (FreeCAD keeps the curves as "missing reference" copies
    when the face goes: a step before the sketch suppressed or deleted)."""
    import Sketcher

    from . import sketch_external

    ids = auto_ids(sketch)
    if not ids:
        return None, None
    ref, missing = None, False
    for geo in list(sketch.ExternalGeo)[2:]:
        try:
            facade = Sketcher.ExternalGeometryFacade(geo)
            if facade.Id in ids:
                ref = facade.Ref
                break
        except Exception:
            continue
    if not ref:
        return None, None
    try:
        missing = facade.testFlag("Missing")
    except Exception:
        pass
    obj = sketch.Document.getObject(ref.split(".", 1)[0])
    if obj is None or missing:
        return obj, None
    sub = sketch_external._sub_of(ref, obj.Name)
    for linked, subs in sketch.ExternalGeometry or []:
        if linked is obj:
            for s in [subs] if isinstance(subs, str) else list(subs):
                if s == sub or sketch_external.plain_sub(obj, s) == sketch_external.plain_sub(obj, sub):
                    return obj, sketch_external.plain_sub(obj, s)
    return obj, None


def _followable(sketch):
    """The sketch, its body and the step it hangs on, when Auto project's face follows the
    design (a sketch Create Sketch made on a face of its own body), else None."""
    from . import hole

    if ANCHOR not in sketch.PropertiesList or not auto_ids(sketch):
        return None
    if sketch.MapMode != "FlatFace" or not sketch.AttachmentSupport:
        return None
    body = hole.owner_body(sketch)
    attached = sketch.AttachmentSupport[0][0]
    if body is None or hole.owner_body(attached) is not body:
        return None
    if App.GuiUp:
        import FreeCADGui as Gui

        try:
            gdoc = Gui.getDocument(sketch.Document.Name)
            vp = gdoc.getInEdit() if gdoc is not None else None
            if vp is not None and getattr(vp, "Object", None) is sketch:
                return None  # being edited: left alone until it is closed
        except Exception:
            pass
    return body


def _step_before(body, sketch):
    """The newest solid step before `sketch` in its body: the design at the sketch's place."""
    group = list(body.Group)
    if sketch not in group:
        return None
    for obj in reversed(group[: group.index(sketch)]):
        if "BaseFeature" in obj.PropertiesList:
            try:
                if not obj.Shape.isNull():
                    return obj
            except Exception:
                continue
    return None


def face_now(sketch, body=None, step=None):
    """(step, "FaceN"): the face the sketch's Auto-projected curves should show: where the
    point Create Sketch kept lies, as the design is at the sketch's place in the timeline,
    on the earliest step that has it with this outline (hole.earliest_face). None when it
    cannot tell (the face is gone there): the curves are then left as they are."""
    from . import hole, sketch_external

    body = body or _followable(sketch)
    if body is None:
        return None
    step = step or _step_before(body, sketch)
    if step is None:
        return None
    point = sketch.Placement.multVec(App.Vector(getattr(sketch, ANCHOR)))
    attached, subs = sketch.AttachmentSupport[0]
    try:
        sub = sketch_external.plain_sub(attached, list(subs)[0])
        normal = hole.face_normal_at(attached.Shape.getElement(sub), point)
    except Exception:
        return None
    name = hole.base_face_at(step, point, normal_hint=normal, loose=0.0)
    if name is None:
        return None
    face = step.Shape.getElement(name)
    if face.Surface.TypeId != "Part::GeomPlane":
        return None
    if hole.face_normal_at(face, point).dot(normal) < 1.0 - 1e-9:
        return None
    return hole.earliest_face(step, name, point, same_outline=True)


_CHECKED = {}  # (document, sketch) -> what follow() last found in order (_state)


def _state(sketch, step):
    try:
        links = [
            (o.Name, tuple([subs] if isinstance(subs, str) else subs))
            for o, subs in sketch.ExternalGeometry or []
        ]
        place = sketch.Placement
        return (step.Name, step.Shape.hashCode(), tuple(links), tuple(place.Base), tuple(place.Rotation.Q))
    except Exception:
        return None


def follow(sketch):
    """Auto project's curves show the face as it is at the sketch's place in the timeline,
    as Fusion's projected edges do: after a step before the sketch reshaped the face, was
    suppressed or deleted, the face found at the kept point (face_now) is projected again in
    their place, and the constraints on them move to the new curves on the same line or
    circle. The sketch keeps hanging on the step it was made on. True when the curves
    changed. Never raises."""
    try:
        body = _followable(sketch)
        if body is None:
            return False
        step = _step_before(body, sketch)
        if step is None:
            return False
        memo = (sketch.Document.Name, sketch.Name)
        state = _state(sketch, step)
        if state is not None and _CHECKED.get(memo) == state:
            return False  # nothing changed since it was last found in order
        changed = _follow(sketch, body, step)
        _CHECKED[memo] = None if changed else state
        return changed
    except Exception as exc:
        log("sketch: Auto project's edges of %s not followed: %s" % (sketch.Label, exc))
        return False


def _follow(sketch, body, step):
    from . import hole

    want = face_now(sketch, body, step)
    if want is None:
        return False
    obj, sub = source(sketch)
    if obj is want[0] and sub == want[1]:
        return False
    if obj is not None and sub is not None and not _suppressed(obj):
        # still linked: only a face of another outline is projected again
        try:
            now = want[0].Shape.getElement(want[1])
            if hole.same_outer_boundary(obj.Shape.getElement(sub), now):
                return False
        except Exception:
            pass
    return _reproject(sketch, want)


def _suppressed(obj):
    return bool(getattr(obj, "Suppressed", False))


def follow_all(doc):
    """follow() every sketch of `doc` that keeps Create Sketch's point; returns the sketches
    whose curves changed (timeline_ops.settle runs it after every recompute)."""
    changed = []
    for obj in list(doc.Objects):
        try:
            if not obj.TypeId.startswith("Sketcher::SketchObject"):
                continue
            if ANCHOR in obj.PropertiesList and follow(obj):
                changed.append(obj)
        except Exception:
            continue
    if changed:
        log(
            "sketch: the projected face of %s follows the design"
            % ", ".join(o.Label for o in changed)
        )
    return changed


def soft_links(doc):
    """{(sketch name, step name)}: a sketch's only link to a step being the face Auto project
    took from it, where the sketch hangs on another step and follows the design (follow):
    suppressing that step leaves the sketch on, with the face as it is without the step (as
    in Fusion, where a sketch stays when its projected edges change; fixsketch_fillet E)."""
    found = set()
    for sketch in list(doc.Objects):
        try:
            if not sketch.TypeId.startswith("Sketcher::SketchObject"):
                continue
            if ANCHOR not in sketch.PropertiesList or _followable(sketch) is None:
                continue
            obj, sub = source(sketch)
            if obj is None or sub is None or obj is sketch.AttachmentSupport[0][0]:
                continue
            links = [
                s
                for linked, subs in sketch.ExternalGeometry or []
                if linked is obj
                for s in ([subs] if isinstance(subs, str) else list(subs))
            ]
            if len(links) == 1:
                found.add((sketch.Name, obj.Name))
        except Exception:
            continue
    return found


def _reproject(sketch, target):
    """Project `target` (step, "FaceN") in place of the curves Auto project made. Each
    constraint on an old curve moves to the new curve that stands in its place (the same
    side of the face: on the same line or parallel to it, the same circle; a line the
    other way round swaps its ends), so what was drawn on the face's corners follows them;
    a constraint on a curve with no such new curve goes. True when done."""
    import Sketcher

    ids = auto_ids(sketch)
    geos = list(sketch.ExternalGeo)
    old, links = {}, {}  # geo id -> curve; reference -> geo ids
    for index, geo in enumerate(geos):
        if index < 2:
            continue
        try:
            facade = Sketcher.ExternalGeometryFacade(geo)
        except Exception:
            continue
        if facade.Id in ids:
            old[-(index + 1)] = geo
            links.setdefault(facade.Ref, []).append(-(index + 1))
    before = len(geos)
    sketch.addExternal(target[0].Name, target[1], True, False)
    sketch.recompute()
    made = list(sketch.ExternalGeo)[before:]
    if not made:
        return False
    new = {-(before + k + 1): geo for k, geo in enumerate(made)}
    remap = _pairs(old, new)
    kept, dropped = [], 0
    for constraint in sketch.Constraints:
        refs = [getattr(constraint, a) for a in ("First", "Second", "Third")]
        if any(r in old and r not in remap for r in refs):
            dropped += 1
            continue
        for attr, pos in (("First", "FirstPos"), ("Second", "SecondPos"), ("Third", "ThirdPos")):
            value = getattr(constraint, attr)
            if value in remap:
                geo_id, swap = remap[value]
                setattr(constraint, attr, geo_id)
                at = getattr(constraint, pos)
                if swap and at in (1, 2):
                    setattr(constraint, pos, 3 - at)
        kept.append(constraint)
    sketch.Constraints = kept
    new_ids = [Sketcher.ExternalGeometryFacade(g).Id for g in made]
    # FreeCAD deletes every curve of a link with one of them: once per old link, from the
    # link whose first curve comes last (a delete renumbers only the curves after it)
    for geo_id in sorted(max(group) for group in links.values()):
        sketch.delExternal(geo_id)
    setattr(sketch, PROPERTY, new_ids)
    sketch.recompute()
    log(
        "sketch: %s projects %s.%s again (%d curve(s), %d constraint(s) moved, %d dropped)"
        % (sketch.Label, target[0].Label, target[1], len(made), len(remap), dropped)
    )
    return True


def _pairs(old, new):
    """{old geo id: (new geo id, swap ends)}: each old curve paired with the new curve of
    its kind nearest to it (_likeness), the closest pairs first, each new curve used once,
    none further away than half the new outline's size."""
    import Part

    try:
        cap = 0.5 * Part.Compound([g.toShape() for g in new.values()]).BoundBox.DiagonalLength
    except Exception:
        cap = float("inf")
    candidates = []
    for old_id, curve in old.items():
        for new_id, other in new.items():
            if type(other) is not type(curve):
                continue
            score, swap = _likeness(curve, other)
            if score is not None and score <= cap:
                candidates.append((score, old_id, new_id, swap))
    candidates.sort(key=lambda c: c[0])
    remap, used = {}, set()
    for _score, old_id, new_id, swap in candidates:
        if old_id not in remap and new_id not in used:
            remap[old_id] = (new_id, swap)
            used.add(new_id)
    return remap


def _likeness(a, b):
    """(how far apart, swapped) for two curves of one kind: lines must be parallel (how far
    apart: the gap between their lines and between their middles), circles and arcs are
    compared by centre and radius; (None, False) for two lines that cross."""
    import Part

    if isinstance(a, Part.LineSegment):
        da, db = a.EndPoint - a.StartPoint, b.EndPoint - b.StartPoint
        if da.Length < 1e-9 or db.Length < 1e-9:
            return None, False
        da.normalize()
        db.normalize()
        if da.cross(db).Length > 1e-6:
            return None, False
        gap = (b.StartPoint - a.StartPoint).cross(da).Length
        middle = (a.StartPoint + a.EndPoint - b.StartPoint - b.EndPoint) * 0.5
        return gap + middle.Length, da.dot(db) < 0
    if isinstance(a, (Part.Circle, Part.ArcOfCircle)):
        score = (a.Center - b.Center).Length + abs(a.Radius - b.Radius)
        if isinstance(a, Part.ArcOfCircle):
            score += (_middle(a) - _middle(b)).Length
        return score, False
    if isinstance(a, Part.Point):
        return (App.Vector(a.X, a.Y, a.Z) - App.Vector(b.X, b.Y, b.Z)).Length, False
    try:
        return (_middle(a) - _middle(b)).Length, False
    except Exception:
        return None, False


def _middle(curve):
    return curve.value((curve.FirstParameter + curve.LastParameter) / 2.0)
