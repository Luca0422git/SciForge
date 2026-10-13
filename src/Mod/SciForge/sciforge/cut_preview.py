# SPDX-License-Identifier: LGPL-2.1-or-later
"""The red see-through volume a command dialog shows while its preview removes material
(Fusion shows a cut in red while you set it up), and the blue see-through copies of the
bodies the Extrude dialog's "Bodies to Cut" row lists while that row is active.

CutPreview(view).show(shape) draws `shape` (global coordinates) in red over the part;
clear() takes it away. BodyHighlight(view).show(shapes) draws each shape in SciForge's
highlight blue, one node per shape; clear() takes them away. Both are only pictures in
the 3D view: Coin nodes that the dialog owns, never a colour on a real feature, so
nothing can stay behind after OK or Cancel. Mouse clicks go through them (they cannot be
picked).
"""
import FreeCADGui as Gui

NAME = "SciForgeCutPreview"
RED = (0.95, 0.20, 0.20)
GLOW = (0.45, 0.05, 0.05)
TRANSPARENCY = 0.45
EDGE = (0.85, 0.08, 0.08)
HIGHLIGHT_NAME = "SciForgeBodyHighlight"
BLUE = (0.247, 0.663, 0.961)  # theme.ACCENT (#3fa9f5), SciForge's highlight blue
BLUE_GLOW = (0.10, 0.28, 0.45)
BLUE_TRANSPARENCY = 0.6
BLUE_EDGE = (0.20, 0.55, 0.90)


def _mesh_node(coin, shape, name, color, glow, transparency, edge):
    """A see-through copy of `shape` with its outline, clicks going through it."""
    node = coin.SoSeparator()
    node.setName(name)
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
    material.diffuseColor.setValue(*color)
    material.emissiveColor.setValue(*glow)
    material.transparency.setValue(transparency)
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
    node.addChild(_outline(coin, shape, size, edge))
    return node


def _outline(coin, shape, size, color):
    """The shape's edges as lines, so its outline reads also where it is inside."""
    sep = coin.SoSeparator()
    style = coin.SoDrawStyle()
    style.lineWidth = 2.0
    sep.addChild(style)
    material = coin.SoMaterial()
    material.diffuseColor.setValue(*color)
    material.emissiveColor.setValue(*color)
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

        node = _mesh_node(coin, shape, NAME, RED, GLOW, TRANSPARENCY, EDGE)
        self.clear()
        self.view.getSceneGraph().addChild(node)
        self.root = node
        self.shape = shape

    def clear(self):
        node, self.root = self.root, None
        self.shape = None
        if node is None:
            return
        try:
            self.view.getSceneGraph().removeChild(node)
        except Exception:
            pass  # the view closed with its document: the node went with it


class BodyHighlight:
    """The bodies listed in the Extrude dialog's "Bodies to Cut / Join / Intersect" row,
    drawn as see-through blue copies (with their outlines) while the row is active, so the
    person sees which bodies the extrude will change. show(shapes) replaces what is shown
    (one node per shape, in design coordinates); clear() takes them away."""

    def __init__(self, view=None):
        self.view = view if view is not None else Gui.ActiveDocument.ActiveView
        self.nodes = []

    @property
    def shown(self):
        return bool(self.nodes)

    def show(self, shapes):
        from pivy import coin

        self.clear()
        for shape in shapes:
            try:
                if shape is None or shape.isNull():
                    continue
                node = _mesh_node(
                    coin, shape, HIGHLIGHT_NAME, BLUE, BLUE_GLOW, BLUE_TRANSPARENCY, BLUE_EDGE
                )
            except Exception:
                continue
            self.view.getSceneGraph().addChild(node)
            self.nodes.append(node)

    def clear(self):
        nodes, self.nodes = self.nodes, []
        for node in nodes:
            try:
                self.view.getSceneGraph().removeChild(node)
            except Exception:
                pass  # the view closed with its document: the node went with it


def find(view=None, name=NAME):
    """The cut preview nodes (or, with name=HIGHLIGHT_NAME, the body highlight nodes) in
    the view's scene (tests: nothing may be left behind)."""
    try:
        view = view if view is not None else Gui.ActiveDocument.ActiveView
        root = view.getSceneGraph()
    except Exception:
        return []
    return [
        root.getChild(i)
        for i in range(root.getNumChildren())
        if root.getChild(i).getName().getString() == name
    ]


def find_highlights(view=None):
    return find(view, HIGHLIGHT_NAME)
