# SPDX-License-Identifier: LGPL-2.1-or-later
"""Selection like Fusion: the maths and the rules, without Qt or FreeCAD (unit tested).

What Fusion does (docs/sciforge/parity/selection.md has the sources):

* A drag from left to right draws a **window**: only what lies fully inside it is selected.
  A drag from right to left draws a **crossing** box: everything it touches is selected.
  Freeform (a lasso) follows the same direction rule; Paint selects what the pointer passes
  over, always "crossing". Keys 1 / 2 / 3 pick Window / Freeform / Paint.
* Ctrl toggles (adds what is not selected, removes what is); Shift only adds. A plain
  click or box replaces the selection; inside a command a plain box adds to its picks.
* Selection Filters say which kinds can be selected at all (hover and click); the
  Selection Priority entries (Body / Face / Edge) are presets that leave one kind on;
  clicking the active priority again puts every filter back on.
* Select Through (off by default): a window or freeform box also takes what is hidden
  behind other faces.
* Select Other: press and hold the left button for about a second without moving: a list
  of everything under the pointer, front to back; hovering a row shows it on the model.

Screen coordinates here are plain (x, y) pairs in one consistent space (the caller
converts; the tests use pixels with y up, as Coin does).
"""

KINDS = (
    "bodies",
    "faces",
    "edges",
    "vertices",
    "sketch_curves",
    "sketch_points",
    "work_geometry",
)
LABELS = {
    "bodies": "Bodies",
    "faces": "Body Faces",
    "edges": "Body Edges",
    "vertices": "Body Vertices",
    "sketch_curves": "Sketch Curves",
    "sketch_points": "Sketch Points",
    "work_geometry": "Work Geometry",
}
# Fusion's Selection Priority entries: one kind stays on, the others go off.
PRIORITIES = {"body": "bodies", "face": "faces", "edge": "edges"}
PRIORITY_LABELS = {
    "body": "Select Body Priority",
    "face": "Select Face Priority",
    "edge": "Select Edge Priority",
}

MODES = ("window", "freeform", "paint")
DEFAULT_MODE = "window"
MODE_LABELS = {
    "window": "Window Selection",
    "freeform": "Freeform Selection",
    "paint": "Paint Selection",
}
MODE_KEYS = {"1": "window", "2": "freeform", "3": "paint"}  # Fusion's hotkeys

DEFAULT_SELECT_THROUGH = False  # Fusion: hidden geometry needs Select Through turned on
# (forum answers tell people to turn it on; the default itself is not documented)
LONG_PRESS_S = 1.0  # Select Other: Fusion "about a second"; FreeCAD's LongPressTimeout too
CLICK_SLOP = 5  # pixels: moving further ends the long press and starts a box
LASSO_STEP = 3.0  # pixels: a freeform point closer than this to the last one is not kept
FACE_SAMPLES = 10  # points per curved edge when an element is projected to the screen

# Looks of the box (SciForge's own; Fusion's exact colours are not documented).
WINDOW_LINE = (0.25, 0.60, 0.95, 1.0)  # solid blue outline, light tint
WINDOW_FILL = (0.25, 0.60, 0.95, 0.16)
CROSSING_LINE = (0.42, 0.80, 0.42, 1.0)  # dashed green outline, light tint
CROSSING_FILL = (0.42, 0.80, 0.42, 0.14)
CROSSING_DASH = (6.0, 4.0)


# -- filters ----------------------------------------------------------------------------------


class Filters:
    """Which kinds can be selected, and whether a box selects through other faces."""

    def __init__(self, off=(), select_through=DEFAULT_SELECT_THROUGH):
        self.off = {k for k in off if k in KINDS}
        self.select_through = bool(select_through)

    def copy(self):
        return Filters(self.off, self.select_through)

    def allows(self, kind):
        """A kind that is not filtered at all (None, unknown) is always allowed."""
        return kind not in self.off

    def is_restrictive(self):
        return bool(self.off)

    def set(self, kind, on):
        if kind not in KINDS:
            raise ValueError("unknown selection kind %r" % (kind,))
        if on:
            self.off.discard(kind)
        else:
            self.off.add(kind)

    def toggle(self, kind):
        self.set(kind, not self.allows(kind))

    def all_on(self):
        self.off = set()

    def priority(self):
        """ "body", "face" or "edge" when exactly that kind is on, else None."""
        on = [k for k in KINDS if k not in self.off]
        for name, kind in PRIORITIES.items():
            if on == [kind]:
                return name
        return None

    def apply_priority(self, name):
        """Fusion: the priority's filter is checked and every other one unchecked; the
        active priority clicked again removes the filter (everything on again)."""
        if name not in PRIORITIES:
            raise ValueError("unknown selection priority %r" % (name,))
        if self.priority() == name:
            self.all_on()
        else:
            self.off = {k for k in KINDS if k != PRIORITIES[name]}

    def encode(self):
        """The filters that are off, for the preferences ("faces,edges")."""
        return ",".join(k for k in KINDS if k in self.off)

    @classmethod
    def decode(cls, text, select_through=DEFAULT_SELECT_THROUGH):
        parts = [p.strip() for p in (text or "").split(",")]
        return cls([p for p in parts if p in KINDS], select_through)

    def __eq__(self, other):
        return (
            isinstance(other, Filters)
            and self.off == other.off
            and self.select_through == other.select_through
        )

    def __repr__(self):
        return "Filters(off=%s, through=%s)" % (sorted(self.off), self.select_through)


SKETCH_TYPE = "Sketcher::SketchObject"
WORK_TYPES = (
    "PartDesign::Plane",
    "PartDesign::Line",
    "PartDesign::Point",
    "PartDesign::CoordinateSystem",
    "App::Plane",
    "App::Line",
    "App::Origin",
    "Part::DatumFeature",
)
BODY_TYPE = "PartDesign::Body"


def element_kind(short):
    """The kind of a body element by its name ("Face6" -> "faces"); None when it is not a
    face, edge or vertex."""
    if short.startswith("Face"):
        return "faces"
    if short.startswith("Edge"):
        return "edges"
    if short.startswith("Vertex"):
        return "vertices"
    return None


def kind_of(type_id, short, in_body=False):
    """The selection filter kind of a pick: `type_id` of the picked object, `short` the
    element ("Face6", "Edge2", "" for the whole object), `in_body` when the object is a
    PartDesign body or one of its features. None: the pick is not filtered (an
    analysis, a text, a sketch area)."""
    type_id = type_id or ""
    if type_id == SKETCH_TYPE:
        if short.startswith("Edge"):
            return "sketch_curves"
        if short.startswith("Vertex"):
            return "sketch_points"
        return None
    if type_id in WORK_TYPES:
        return "work_geometry"
    kind = element_kind(short)
    if kind is not None:
        return kind if (in_body or type_id.startswith(("Part::", "PartDesign::"))) else None
    if not short and (type_id == BODY_TYPE or in_body):
        return "bodies"
    return None


def box_kinds(filters):
    """What a box or a paint stroke selects, of what the filters allow. Fusion's box takes
    faces and edges (not every vertex: Autodesk limited that for speed), whole bodies with
    the Body priority, and sketch curves. Vertices only when the user asked for them
    (faces and edges off)."""
    kinds = set()
    if filters.allows("bodies") and not any(
        filters.allows(k) for k in ("faces", "edges", "vertices")
    ):
        kinds.add("bodies")
    else:
        for kind in ("faces", "edges"):
            if filters.allows(kind):
                kinds.add(kind)
        if filters.allows("vertices") and not kinds:
            kinds.add("vertices")
    if filters.allows("sketch_curves"):
        kinds.add("sketch_curves")
    if filters.allows("work_geometry"):
        # the planes, axes and points that are shown (Guess: Fusion's Work Geometry filter
        # covers window selection like the other kinds; sketch-2)
        kinds.add("work_geometry")
    return kinds


def only_bodies(filters):
    """Clicks select whole bodies: the Body priority (or any filter set that leaves no
    face, edge or vertex)."""
    return "bodies" in box_kinds(filters)


# -- modifiers ---------------------------------------------------------------------------------


def plan(shift, ctrl, in_dialog):
    """What a box does with what it finds: "replace" the selection, "add" (Shift; or a
    plain box inside a command, which collects picks), "toggle" (Ctrl)."""
    if ctrl and not shift:
        return "toggle"
    if shift or in_dialog:
        return "add"
    return "replace"


def click_plan(shift, ctrl, in_dialog, already_selected):
    """What a click does on one element: "keep" (Shift on something selected: Fusion's
    Shift never removes), "add", "toggle" or "replace"; None when FreeCAD's own click
    does the right thing (plain click, Ctrl click)."""
    if shift and not ctrl:
        return "keep" if already_selected else "add"
    if ctrl:
        return "toggle"
    return "add" if in_dialog else "replace"


# -- the box ----------------------------------------------------------------------------------


def box_mode(x_start, x_end):
    """ "window" for a drag to the right (or straight up/down), "crossing" to the left."""
    return "crossing" if x_end < x_start else "window"


def rect_polygon(x0, y0, x1, y1):
    """The four corners of the rectangle between two drag points, counter-clockwise."""
    xa, xb = min(x0, x1), max(x0, x1)
    ya, yb = min(y0, y1), max(y0, y1)
    return [(xa, ya), (xb, ya), (xb, yb), (xa, yb)]


def bounds(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def simplify_lasso(points, step=LASSO_STEP):
    """Drop lasso points closer than `step` to the one kept before them."""
    kept = []
    for p in points:
        if not kept or (p[0] - kept[-1][0]) ** 2 + (p[1] - kept[-1][1]) ** 2 >= step * step:
            kept.append(p)
    return kept


def point_in_polygon(x, y, poly):
    """Ray casting; a point on the boundary counts as inside."""
    n = len(poly)
    if n < 3:
        return False
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if _on_segment((x, y), (xi, yi), (xj, yj)):
            return True
        if (yi > y) != (yj > y):
            x_cross = xi + (y - yi) * (xj - xi) / (yj - yi)
            if x < x_cross:
                inside = not inside
        j = i
    return inside


def _cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _on_segment(p, a, b, eps=1e-9):
    if abs(_cross(a, b, p)) > eps * max(1.0, abs(b[0] - a[0]) + abs(b[1] - a[1])):
        return False
    return (
        min(a[0], b[0]) - eps <= p[0] <= max(a[0], b[0]) + eps
        and min(a[1], b[1]) - eps <= p[1] <= max(a[1], b[1]) + eps
    )


def segments_cross(a, b, c, d):
    """Segments ab and cd meet (crossing or touching)."""
    d1 = _cross(c, d, a)
    d2 = _cross(c, d, b)
    d3 = _cross(a, b, c)
    d4 = _cross(a, b, d)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)) and d1 != 0 and d2 != 0:
        return True
    return (
        _on_segment(a, c, d) or _on_segment(b, c, d) or _on_segment(c, a, b) or _on_segment(d, a, b)
    )


def polygon_crosses_segment(poly, a, b):
    n = len(poly)
    for i in range(n):
        if segments_cross(poly[i], poly[(i + 1) % n], a, b):
            return True
    return False


def element_selected(points, segments, poly, mode, outline=None):
    """Whether one element is taken by the box `poly` (a list of (x, y) screen points).

    points:   every screen point of the element (its vertices, the points along its curved
              edges); segments: [(a, b)] its boundary pieces; outline: the element's own
              outer boundary as a polygon (faces and bodies), for a box lying inside it.
    window:   every point inside (and at least one point).
    crossing: any point inside, any boundary piece touched, or the box inside the outline.
    """
    if not points:
        return False
    if mode == "window":
        return all(point_in_polygon(x, y, poly) for x, y in points)
    if any(point_in_polygon(x, y, poly) for x, y in points):
        return True
    for a, b in segments:
        if polygon_crosses_segment(poly, a, b):
            return True
    if outline and len(outline) >= 3:
        return any(point_in_polygon(x, y, outline) for x, y in poly)
    return False


def quick_reject(points, poly):
    """True when the element's screen box and the selection's screen box do not even
    overlap (saves the exact test on big parts)."""
    if not points:
        return True
    ax0, ay0, ax1, ay1 = bounds(points)
    bx0, by0, bx1, by1 = bounds(poly)
    return ax1 < bx0 or bx1 < ax0 or ay1 < by0 or by1 < ay0


# -- Select Other -----------------------------------------------------------------------------


def dedupe(items):
    """Keep the first of equal (object, element) entries; items are (key, payload)."""
    seen = set()
    kept = []
    for key, payload in items:
        if key in seen:
            continue
        seen.add(key)
        kept.append((key, payload))
    return kept


def depth_key(point, camera, direction):
    """How far along the view direction a picked point is: smaller = nearer the eye."""
    return sum((point[i] - camera[i]) * direction[i] for i in range(3))


def order_front_to_back(items, camera, direction):
    """items: (payload, point) -> payloads sorted nearest first (Fusion's list order)."""
    return [p for p, _ in sorted(items, key=lambda it: depth_key(it[1], camera, direction))]


def pretty_element(short):
    """ "Face6" -> "Face 6", "" -> "Body"."""
    if not short:
        return "Body"
    for i, ch in enumerate(short):
        if ch.isdigit():
            return short[:i] + " " + short[i:]
    return short


def row_label(short, owner):
    """One row of the Select Other list: the element and the body it belongs to."""
    name = pretty_element(short)
    return "%s  ·  %s" % (name, owner) if owner and short else (owner or name)


def depth_tolerance(diagonal):
    """How far (model units) a picked point may be from an element's own point and still
    be that element (a visibility test with the view's pick): 0.2 % of the part's size."""
    return max(1e-4, 0.002 * float(diagonal))


def filter_message(kind):
    """Why a click selected nothing: the filter for that kind is off."""
    label = LABELS.get(kind, kind)
    return "%s are filtered out (SELECT ▾ > Selection Filters)." % label
