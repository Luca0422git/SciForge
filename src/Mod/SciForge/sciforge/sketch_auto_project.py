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


def auto_project(sketch, target):
    """A sketch on a flat face gets the face's edges as projected (purple) curves that make
    profiles, like Fusion's "Auto project geometry on active sketch plane". One external
    reference to the whole face (FreeCAD projects every edge of a face it is given).

    The face is the one the sketch hangs on (`target`: sketch_ui._earliest, the earliest
    step that has the face), so suppressing or deleting a later unrelated step (a hole
    drilled in the face) leaves the curves alone, as it leaves the sketch alone; a
    reference to the later step's face broke the sketch then (fixsketch_hole D). Edges a
    later step added to the face (that hole) are projected with P. Never raises: a face
    that cannot be projected (another body's) leaves the sketch without, with a note in
    the log. Returns the number of curves projected."""
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
