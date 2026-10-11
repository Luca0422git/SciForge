# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion lights up what a timeline step made while the mouse is over its icon: the faces
an extrude, hole or fillet made, the curves of a sketch, a construction plane.

``made_by(obj)`` works the faces out without Qt (a face of the step's result is the
step's own when no face of its base lies on the same surface); ``HoverLook`` draws them
on top of the 3D view in its own Coin nodes (never FreeCAD's, which FreeCAD may delete).
"""
from . import warn

COLOR = (0.30, 0.62, 0.95)  # Fusion's hover blue
TOL = 1e-6


def _same_surface(a, b):
    """True if two faces lie on the same plane / cylinder / cone / sphere (a face trimmed
    by a step is still the old face; one the step made has a surface of its own)."""
    try:
        sa, sb = a.Surface, b.Surface
    except Exception:
        return False
    if sa.TypeId != sb.TypeId:
        return False
    kind = sa.TypeId
    try:
        if kind == "Part::GeomPlane":
            na, nb = a.normalAt(0, 0), b.normalAt(0, 0)
            if abs(abs(na.dot(nb)) - 1.0) > 1e-7:
                return False
            return abs((a.Vertexes[0].Point - b.Vertexes[0].Point).dot(na)) < 1e-6
        if kind in ("Part::GeomCylinder", "Part::GeomCone", "Part::GeomSphere"):
            if abs(getattr(sa, "Radius", 0) - getattr(sb, "Radius", 0)) > TOL:
                return False
            if (sa.Center - sb.Center).Length > 1e-6 and kind == "Part::GeomSphere":
                return False
            if kind != "Part::GeomSphere":
                axis = sa.Axis
                if abs(abs(axis.dot(sb.Axis)) - 1.0) > 1e-7:
                    return False
                off = sb.Center - sa.Center
                return (off - axis * off.dot(axis)).Length < 1e-6
            return True
    except Exception:
        return False
    # Other surfaces: the same face, by place and size.
    ba, bb = a.BoundBox, b.BoundBox
    return (
        abs(ba.XMin - bb.XMin) < 1e-6
        and abs(ba.XMax - bb.XMax) < 1e-6
        and abs(ba.YMin - bb.YMin) < 1e-6
        and abs(ba.YMax - bb.YMax) < 1e-6
        and abs(ba.ZMin - bb.ZMin) < 1e-6
        and abs(ba.ZMax - bb.ZMax) < 1e-6
        and abs(a.Area - b.Area) < 1e-4
    )


def made_by(obj):
    """The faces a solid step made (on its own result), or [] if none can be told."""
    try:
        shape = obj.Shape
        if shape.isNull():
            return []
        base = getattr(obj, "BaseFeature", None)
        base_faces = [] if base is None or base.Shape.isNull() else base.Shape.Faces
    except Exception:
        return []
    found = []
    for face in shape.Faces:
        if not any(_same_surface(face, old) for old in base_faces):
            found.append(face)
    return found


def lines_of(obj):
    """Edges to light up for a sketch (its curves) or a construction line/plane outline."""
    try:
        shape = obj.Shape
        return [] if shape.isNull() else list(shape.Edges)
    except Exception:
        return []


class HoverLook:
    """The highlight drawn while the mouse is over a timeline step."""

    def __init__(self):
        self.root = None
        self.view = None
        self.name = None

    def show(self, obj):
        """Light up what ``obj`` made; the previous highlight goes."""
        if obj is not None and obj.Name == self.name and self.root is not None:
            return
        self.clear()
        if obj is None:
            return
        try:
            import FreeCADGui as Gui

            gdoc = Gui.getDocument(obj.Document.Name)
            view = gdoc.ActiveView if gdoc is not None else None
            if view is None or not hasattr(view, "getSceneGraph"):
                return
            root = self._build(obj)
            if root is None:
                return
            view.getSceneGraph().addChild(root)
            self.root, self.view, self.name = root, view, obj.Name
        except Exception as exc:
            warn("timeline hover: %s" % exc)

    def clear(self):
        root, view = self.root, self.view
        self.root = self.view = self.name = None
        if root is None:
            return
        try:
            view.getSceneGraph().removeChild(root)
        except Exception:
            pass  # the view is gone (design closed): our nodes went with it

    def _build(self, obj):
        from pivy import coin

        faces, edges = [], []
        if "BaseFeature" in obj.PropertiesList:
            faces = made_by(obj)
        elif obj.TypeId in ("PartDesign::Plane", "Part::DatumPlane"):
            faces = list(obj.Shape.Faces) if not obj.Shape.isNull() else []
        else:
            edges = lines_of(obj)
        if not faces and not edges:
            return None
        root = coin.SoSeparator()
        root.setName("SciForgeTimelineHover")
        annotation = coin.SoAnnotation()  # on top of the part, like Fusion's highlight
        root.addChild(annotation)
        # Shapes are in their body's coordinates; the body may have been moved.
        try:
            extra = obj.getGlobalPlacement().multiply(obj.Placement.inverse())
            move = coin.SoTransform()
            move.translation.setValue(extra.Base.x, extra.Base.y, extra.Base.z)
            move.rotation.setValue(*extra.Rotation.Q)
            annotation.addChild(move)
        except Exception:
            pass
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        annotation.addChild(pick)
        material = coin.SoMaterial()
        material.diffuseColor.setValue(*COLOR)
        material.emissiveColor.setValue(*[c * 0.6 for c in COLOR])
        material.transparency.setValue(0.55 if faces else 0.0)
        annotation.addChild(material)
        if faces:
            self._faces(coin, annotation, faces)
        if edges:
            self._edges(coin, annotation, edges)
        return root

    @staticmethod
    def _faces(coin, parent, faces):
        points, index = [], []
        for face in faces:
            try:
                verts, tris = face.tessellate(0.1)
            except Exception:
                continue
            start = len(points)
            points += [(v.x, v.y, v.z) for v in verts]
            for a, b, c in tris:
                index += [start + a, start + b, start + c, -1]
        if not index:
            return
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, len(points), points)
        mesh = coin.SoIndexedFaceSet()
        mesh.coordIndex.setValues(0, len(index), index)
        hints = coin.SoShapeHints()
        hints.vertexOrdering = coin.SoShapeHints.UNKNOWN_ORDERING
        parent.addChild(hints)
        parent.addChild(coords)
        parent.addChild(mesh)

    @staticmethod
    def _edges(coin, parent, edges):
        style = coin.SoDrawStyle()
        style.lineWidth = 3
        parent.addChild(style)
        for edge in edges:
            try:
                pts = edge.discretize(Deflection=0.05)
            except Exception:
                continue
            if len(pts) < 2:
                continue
            coords = coin.SoCoordinate3()
            coords.point.setValues(0, len(pts), [(p.x, p.y, p.z) for p in pts])
            line = coin.SoLineSet()
            line.numVertices.setValue(len(pts))
            parent.addChild(coords)
            parent.addChild(line)
