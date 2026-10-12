# SPDX-License-Identifier: LGPL-2.1-or-later
"""The red see-through volume a command dialog shows while its preview removes material
(Fusion shows a cut in red while you set it up).

CutPreview(view).show(shape) draws `shape` (global coordinates) in red over the part;
clear() takes it away. It is only a picture in the 3D view: one Coin node that the
dialog owns, never a colour on a real feature, so nothing red can stay behind after OK
or Cancel. Mouse clicks go through it (it cannot be picked).
"""
import FreeCADGui as Gui

NAME = "SciForgeCutPreview"
RED = (0.95, 0.20, 0.20)
GLOW = (0.45, 0.05, 0.05)
TRANSPARENCY = 0.45
EDGE = (0.85, 0.08, 0.08)


class CutPreview:
    def __init__(self, view=None):
        self.view = view if view is not None else Gui.ActiveDocument.ActiveView
        self.root = None
        self.shape = None  # the shape shown (tests read its BoundBox)

    @property
    def shown(self):
        return self.root is not None

    def show(self, shape):
        """Draw `shape` (a solid in global coordinates) in red, replacing what was shown."""
        from pivy import coin

        node = coin.SoSeparator()
        node.setName(NAME)
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE  # clicks reach the faces behind it
        node.addChild(pick)
        # Drawn just in front of the part's own faces where they lie on each other (the walls
        # of the hole), as FreeCAD's own tool preview does.
        offset = coin.SoPolygonOffset()
        offset.factor = -1.0
        offset.units = -1.0
        node.addChild(offset)
        hints = coin.SoShapeHints()
        hints.vertexOrdering = coin.SoShapeHints.UNKNOWN_ORDERING
        hints.shapeType = coin.SoShapeHints.UNKNOWN_SHAPE_TYPE  # lit from both sides
        node.addChild(hints)
        size = max(shape.BoundBox.DiagonalLength, 1e-3)
        points, triangles = shape.tessellate(max(0.002 * size, 0.005))
        material = coin.SoMaterial()
        material.diffuseColor.setValue(*RED)
        material.emissiveColor.setValue(*GLOW)
        material.transparency.setValue(TRANSPARENCY)
        node.addChild(material)
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, len(points), [(p.x, p.y, p.z) for p in points])
        node.addChild(coords)
        faces = coin.SoIndexedFaceSet()
        index = []
        for a, b, c in triangles:
            index += [a, b, c, -1]
        faces.coordIndex.setValues(0, len(index), index)
        node.addChild(faces)
        node.addChild(self._outline(coin, shape, size))
        self.clear()
        self.view.getSceneGraph().addChild(node)
        self.root = node
        self.shape = shape

    @staticmethod
    def _outline(coin, shape, size):
        """The tool's edges as red lines, so its outline reads also where it is inside."""
        sep = coin.SoSeparator()
        style = coin.SoDrawStyle()
        style.lineWidth = 2.0
        sep.addChild(style)
        material = coin.SoMaterial()
        material.diffuseColor.setValue(*EDGE)
        material.emissiveColor.setValue(*EDGE)
        sep.addChild(material)
        points, counts = [], []
        for edge in shape.Edges:
            try:
                line = edge.discretize(Deflection=max(0.002 * size, 0.005))
            except Exception:
                continue
            if len(line) < 2:
                continue
            points += [(p.x, p.y, p.z) for p in line]
            counts.append(len(line))
        if counts:
            coords = coin.SoCoordinate3()
            coords.point.setValues(0, len(points), points)
            sep.addChild(coords)
            lines = coin.SoLineSet()
            lines.numVertices.setValues(0, len(counts), counts)
            sep.addChild(lines)
        return sep

    def clear(self):
        node, self.root = self.root, None
        self.shape = None
        if node is None:
            return
        try:
            self.view.getSceneGraph().removeChild(node)
        except Exception:
            pass  # the view closed with its document: the node went with it


def find(view=None):
    """The cut preview nodes in the view's scene (tests: nothing may be left behind)."""
    from pivy import coin

    try:
        view = view if view is not None else Gui.ActiveDocument.ActiveView
        root = view.getSceneGraph()
    except Exception:
        return []
    return [
        root.getChild(i)
        for i in range(root.getNumChildren())
        if root.getChild(i).getName().getString() == NAME
    ]
