# SPDX-License-Identifier: LGPL-2.1-or-later
"""The 3D view side of ending an extrude on a clicked face (the rules are in
extrude_to_face_core.py, the dialog is extrude_ui.py): what a click or the mouse points at,
in design coordinates, and the see-through mark on the face or point a dragged arrow snaps
to (a picture only: clicks go through it). No Qt.
"""

import FreeCAD as App

from . import extrude, profile_pick, warn

SNAP_NAME = "SciForgeSnapTarget"
SNAP_COLOR = (0.247, 0.663, 0.961)  # SciForge's highlight blue (cut_preview.BLUE)
SNAP_GLOW = (0.12, 0.33, 0.55)
SNAP_TRANSPARENCY = 0.35
SNAP_EDGE = (0.20, 0.55, 0.90)
NEAR_PIXELS = 6  # hits this close (in depth, at the screen's scale) to the front-most one count


def vertex_point(obj, short):
    """The vertex `short` of `obj` in design coordinates, or None."""
    try:
        vertex = obj.Shape.getElement(short)
    except Exception:
        return None
    try:
        return App.Vector(extrude._to_global(vertex, obj).Point)
    except Exception:
        return None


def target(obj, short, point=None):
    """What the extrusion would end on, in design coordinates, or None (an edge, a whole
    body, a sketch): {"shape": "flat" | "curved" | "vertex" | "plane", "normal": the face's
    or plane's normal (None for a vertex or curved face), "point": a point of it (a flat
    face's centre, exact; the clicked point on a curved face), "shape_obj": the face or
    vertex (for the snap mark)}."""
    if obj is None:
        return None
    if obj.TypeId in extrude.PLANE_TYPES:
        plane = extrude._plane_of_ref((obj, ""))
        if plane is None:
            return None
        return {"shape": "plane", "normal": plane[1], "point": plane[0], "shape_obj": None}
    if short.startswith("Vertex"):
        p = vertex_point(obj, short)
        if p is None:
            return None
        return {"shape": "vertex", "normal": None, "point": p, "shape_obj": None}
    if not short.startswith("Face"):
        return None
    face = profile_pick.global_face(obj, short)
    if face is None:
        return None
    if face.Surface.TypeId == "Part::GeomPlane":
        return {
            "shape": "flat",
            "normal": extrude.face_normal(face),
            "point": face.CenterOfMass,
            "shape_obj": face,
        }
    where = None
    if point is not None:
        try:
            import Part

            # (the click lands on the drawn mesh, a little off the true surface)
            slack = max(0.1, face.BoundBox.DiagonalLength * 0.01)
            if face.distToShape(Part.Vertex(App.Vector(point)))[0] < slack:
                where = App.Vector(point)  # where it was clicked (it tells the side)
        except Exception:
            where = None
    if where is None:
        where = extrude.interior_point(face)
    return {"shape": "curved", "normal": None, "point": where, "shape_obj": face}


def _info_ref(info):
    """(object, element, picked point) of a getObjectsInfo entry, or None."""
    try:
        doc = App.getDocument(info["Document"])
        obj = doc.getObject(info["Object"])
    except Exception:
        return None
    if obj is None:
        return None
    short = str(info.get("Component", "") or "")
    return obj, short, App.Vector(info["x"], info["y"], info["z"])


def hits_at(view, pixel, scale):
    """[(object, element, point)] under the Coin pixel at the front-most spot: the first
    thing the line of sight meets and whatever lies within a few pixels of it there (a
    vertex at a face's corner). Sketches are left out (their lines are no target). `scale`:
    millimetres per pixel at that depth."""
    try:
        infos = list(view.getObjectsInfo((int(round(pixel[0])), int(round(pixel[1])))) or [])
    except Exception:
        return []
    found, first = [], None
    for info in infos:
        ref = _info_ref(info)
        if ref is None:
            continue
        obj = ref[0]
        if extrude.is_sketch(obj) or extrude.is_text(obj):
            continue
        if first is None:
            first = ref[2]
        elif (ref[2] - first).Length > NEAR_PIXELS * scale:
            break
        found.append(ref)
    return found


def base_face_at(base, point, tol=0.05):
    """(base, "FaceN"): the face of `base` (a feature, design coordinates through its body)
    that holds `point`, or None. A face of the extrude's own preview that merged with a face
    of the part (a Join ending flush with it) is found again this way, where it was."""
    if base is None or point is None:
        return None
    try:
        import Part

        shape = extrude._to_global(base.Shape, base)
        probe = Part.Vertex(App.Vector(point))
        for i, face in enumerate(shape.Faces, start=1):
            box = face.BoundBox
            box.enlarge(tol)
            if not box.isInside(App.Vector(point)):
                continue
            if face.distToShape(probe)[0] <= tol:
                return (base, "Face%d" % i)
    except Exception as exc:
        warn("face under the click: %s" % exc)
    return None


class SnapHighlight:
    """The face (or point) a dragged arrow snaps to, drawn see-through in SciForge's blue
    over the part while the arrow is held there. show(key, shape) replaces what is shown
    (nothing is rebuilt while the key stays the same); clear() takes it away."""

    def __init__(self, view):
        self.view = view
        self.node = None
        self.key = None

    @property
    def shown(self):
        return self.node is not None

    def show(self, key, shape):
        if key is not None and key == self.key and self.node is not None:
            return
        self.clear()
        if shape is None or shape.isNull():
            return
        try:
            from pivy import coin

            from . import cut_preview

            node = cut_preview._mesh_node(
                coin, shape, SNAP_NAME, SNAP_COLOR, SNAP_GLOW, SNAP_TRANSPARENCY, SNAP_EDGE
            )
            self.view.getSceneGraph().addChild(node)
            self.node, self.key = node, key
        except Exception as exc:
            warn("snap mark: %s" % exc)

    def clear(self):
        node, self.node, self.key = self.node, None, None
        if node is None:
            return
        try:
            self.view.getSceneGraph().removeChild(node)
        except Exception:
            pass  # the view closed with its document: the node went with it


def point_mark(point, scale):
    """A small ball at `point` (the snap mark of a vertex), about 5 pixels across."""
    import Part

    return Part.makeSphere(max(scale * 5.0, 1e-3), App.Vector(point))


def find(view):
    """The snap mark nodes in the view's scene (tests: none may be left behind)."""
    try:
        root = view.getSceneGraph()
    except Exception:
        return []
    return [
        root.getChild(i)
        for i in range(root.getNumChildren())
        if root.getChild(i).getName().getString() == SNAP_NAME
    ]
