# SPDX-License-Identifier: LGPL-2.1-or-later
"""How the origin planes and axes look wherever SciForge draws them: the squares of Create
Sketch (sketch_ui.PlanePicker, reused by Construct, Section, Draft, Insert, the patterns,
Align and the other Modify tools, the primitives and the surfaces), the Mesh plane cut's
squares and the axis lines of Revolve and the patterns.

Luca: "you can't tell which face is the x y or z. none of them are labeled. give it the red
green blue of all the rest of the axis and make it smaller. and label them." So:
- one colour per axis, as on the view cube and Move's triad: X red, Y green, Z blue;
- a plane takes the colour of the axis it faces (its normal): XY blue, XZ green, YZ red;
- see-through, brighter with a thicker outline under the mouse;
- a small screen label ("XY", "X") so you can tell which is which;
- the squares are about 0.6 x the part (they were 1.3 x and covered it).

Colours and sizes are plain data (unit-tested); the coin nodes are built only on demand.
"""

AXIS_RGB = {
    "X": (0.90, 0.28, 0.28),
    "Y": (0.35, 0.78, 0.35),
    "Z": (0.30, 0.52, 0.98),
}
PLANE_NORMAL_AXIS = {"XY": "Z", "XZ": "Y", "YZ": "X"}
IDLE_TRANSPARENCY = 0.80
HOVER_TRANSPARENCY = 0.55
IDLE_OUTLINE = 1.0
HOVER_OUTLINE = 3.0
SIZE_FACTOR = 0.6  # square side / largest side of the part
MIN_SIZE = 20.0  # mm: a tiny part still gets squares you can click
EMPTY_SIZE = 100.0  # mm: an empty design (the view is framed on them)
LABEL_POINTS = 16.0
LABEL_INSET = 0.86  # the label sits this far out towards a corner (fraction of the half size)


def plane_key(role):
    """ "XY", "XZ" or "YZ" for an origin plane's role or name ("XY_Plane", "XZ_Plane001"),
    or "" when it is none of them."""
    text = str(role or "")
    for key in PLANE_NORMAL_AXIS:
        if text.startswith(key):
            return key
    return ""


def axis_key(name):
    """ "X", "Y" or "Z" for an axis role or name ("X_Axis", "Y_Axis001", "Z"), or ""."""
    text = str(name or "")
    return text[0] if text[:1] in AXIS_RGB else ""


def plane_colour(role):
    """The colour of an origin plane: the colour of the axis it faces."""
    axis = PLANE_NORMAL_AXIS.get(plane_key(role))
    return AXIS_RGB.get(axis, (0.70, 0.70, 0.70))


def axis_colour(name, default=(0.95, 0.62, 0.22)):
    return AXIS_RGB.get(axis_key(name), default)


def plane_key_of_normal(normal):
    """The origin plane a (body-frame) normal belongs to, by its largest component."""
    x, y, z = (abs(float(c)) for c in normal)
    if z >= x and z >= y:
        return "XY"
    if y >= x:
        return "XZ"
    return "YZ"


def lighter(color, amount=0.35):
    """`color` moved `amount` of the way to white (the hover look)."""
    return tuple(c + (1.0 - c) * amount for c in color)


def square_size(extent, empty=False):
    """Side of the origin squares for a part whose largest side is `extent` mm."""
    if empty:
        return EMPTY_SIZE
    return max(MIN_SIZE, SIZE_FACTOR * float(extent))


def look(role, hovered):
    """(face colour, transparency, outline colour, outline width) of a square."""
    base = plane_colour(role)
    if hovered:
        return lighter(base, 0.35), HOVER_TRANSPARENCY, lighter(base, 0.55), HOVER_OUTLINE
    return base, IDLE_TRANSPARENCY, base, IDLE_OUTLINE


def axis_label_spot(start, end, fraction=0.7):
    """Where an axis line's label goes: on its + half, 40 % of the way out from the middle
    (the ends of the long lines are often off the screen)."""
    return tuple(float(a) + (float(b) - float(a)) * fraction for a, b in zip(start, end))


def label_corner(corners, away_from=None):
    """Index of the corner the label goes to: the one farthest from `away_from` (the part's
    centre: the label is not drawn over the part), else the third one (+u, +v)."""
    if away_from is None or not corners:
        return 2 if len(corners) > 2 else 0

    def far(i):
        p = corners[i]
        return sum((float(a) - float(b)) ** 2 for a, b in zip(p, away_from))

    return max(range(len(corners)), key=far)


# -- coin nodes -----------------------------------------------------------------------------
def label_node(coin, point, text, color, size=LABEL_POINTS):
    """A screen text at `point`, drawn over everything (an SoAnnotation), not pickable."""
    sep = coin.SoAnnotation()
    pick = coin.SoPickStyle()
    pick.style = coin.SoPickStyle.UNPICKABLE
    material = coin.SoMaterial()
    material.diffuseColor.setValue(*color)
    material.emissiveColor.setValue(*color)
    move = coin.SoTranslation()
    move.translation.setValue(float(point[0]), float(point[1]), float(point[2]))
    font = coin.SoFont()
    font.size.setValue(size)
    label = coin.SoText2()
    label.string.setValue(text)
    for node in (pick, material, move, font, label):
        sep.addChild(node)
    return sep


class SquareLook:
    """The nodes of one origin square (a see-through face, an outline and its label) under
    `parent`; paint(hovered) switches between the idle and the hover look."""

    def __init__(self, coin, parent, role, corners, label_at=None, text=None):
        self.role = role
        sep = coin.SoSeparator()
        self.material = coin.SoMaterial()
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, 4, [(p[0], p[1], p[2]) for p in corners])
        faces = coin.SoFaceSet()
        faces.numVertices.setValue(4)
        outline = coin.SoSeparator()
        self.line_material = coin.SoMaterial()
        self.line_style = coin.SoDrawStyle()
        line_coords = coin.SoCoordinate3()
        loop = list(corners) + [corners[0]]
        line_coords.point.setValues(0, 5, [(p[0], p[1], p[2]) for p in loop])
        lines = coin.SoLineSet()
        lines.numVertices.setValue(5)
        for node in (self.line_material, self.line_style, line_coords, lines):
            outline.addChild(node)
        for node in (self.material, coords, faces, outline):
            sep.addChild(node)
        text = plane_key(role) if text is None else text
        self.label = None
        if text and label_at is not None:
            self.label = label_node(coin, label_at, text, lighter(plane_colour(role), 0.45))
            sep.addChild(self.label)
        parent.addChild(sep)
        self.node = sep
        self.paint(False)

    def paint(self, hovered):
        face, transparency, line, width = look(self.role, hovered)
        self.material.diffuseColor.setValue(*face)
        self.material.emissiveColor.setValue(*[c * 0.5 for c in face])
        self.material.transparency.setValue(transparency)
        self.line_material.diffuseColor.setValue(*line)
        self.line_material.emissiveColor.setValue(*line)
        self.line_material.transparency.setValue(0.15 if hovered else 0.35)
        self.line_style.lineWidth.setValue(width)
