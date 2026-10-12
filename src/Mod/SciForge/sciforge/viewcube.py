# SPDX-License-Identifier: LGPL-2.1-or-later
"""The ViewCube's shape and camera maths, without Qt or FreeCAD (so it can be unit tested).

The ViewCube (viewcube_ui.py draws it) is a cube with bevelled edges and corners. It has
26 parts you can click: 6 faces, 12 edge strips and 8 corner triangles. Each part has an
outward direction, for example (0, -1, 0) for the FRONT face or (1, -1, 1) for the
front-right-top corner. Clicking a part turns the camera so it looks straight at that part
(it looks along the opposite direction).

Directions follow FreeCAD's and Fusion's "Z up" designs: FRONT looks along +Y (from the -Y
side), TOP looks down along -Z, RIGHT looks along -X.

Rotations are quaternions written (x, y, z, w), like FreeCAD's ``Rotation.Q``. A camera
orientation ``q`` turns the camera's own axes into world directions:
``rotate(q, (1, 0, 0))`` is the camera's right, ``rotate(q, (0, 1, 0))`` its up, and the
camera looks along ``rotate(q, (0, 0, -1))``.
"""
import json
import math

# -- small vector and quaternion helpers -------------------------------------------------


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def scale(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def unit(a):
    length = math.sqrt(dot(a, a))
    if length < 1e-12:
        return (0.0, 0.0, 0.0)
    return scale(a, 1.0 / length)


def q_mul(a, b):
    """The rotation b followed by a (Hamilton product a*b)."""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )


def q_conj(q):
    return (-q[0], -q[1], -q[2], q[3])


def q_unit(q):
    length = math.sqrt(sum(c * c for c in q))
    if length < 1e-12:
        return (0.0, 0.0, 0.0, 1.0)
    return tuple(c / length for c in q)


def q_axis_angle(axis, angle):
    """Rotation by `angle` radians about `axis` (right-hand rule)."""
    axis = unit(axis)
    s = math.sin(angle / 2.0)
    return (axis[0] * s, axis[1] * s, axis[2] * s, math.cos(angle / 2.0))


def rotate(q, v):
    """The vector v turned by the rotation q."""
    p = q_mul(q_mul(q, (v[0], v[1], v[2], 0.0)), q_conj(q))
    return (p[0], p[1], p[2])


def q_from_axes(right, up, back):
    """The camera orientation whose right, up and back (towards the viewer) axes are these
    world directions (they must be at right angles to each other)."""
    # Rotation matrix with the three directions as columns.
    m00, m10, m20 = right
    m01, m11, m21 = up
    m02, m12, m22 = back
    trace = m00 + m11 + m22
    if trace > 0:
        s = 2.0 * math.sqrt(trace + 1.0)
        q = ((m21 - m12) / s, (m02 - m20) / s, (m10 - m01) / s, 0.25 * s)
    elif m00 > m11 and m00 > m22:
        s = 2.0 * math.sqrt(1.0 + m00 - m11 - m22)
        q = (0.25 * s, (m01 + m10) / s, (m02 + m20) / s, (m21 - m12) / s)
    elif m11 > m22:
        s = 2.0 * math.sqrt(1.0 + m11 - m00 - m22)
        q = ((m01 + m10) / s, 0.25 * s, (m12 + m21) / s, (m02 - m20) / s)
    else:
        s = 2.0 * math.sqrt(1.0 + m22 - m00 - m11)
        q = ((m02 + m20) / s, (m12 + m21) / s, 0.25 * s, (m10 - m01) / s)
    return q_unit(q)


def camera_axes(q):
    """(right, up, view direction) of the camera orientation q, as world directions."""
    return rotate(q, (1, 0, 0)), rotate(q, (0, 1, 0)), rotate(q, (0, 0, -1))


def same_orientation(a, b, tol=1e-4):
    """True when the rotations a and b are the same (q and -q are the same rotation)."""
    return abs(abs(sum(x * y for x, y in zip(q_unit(a), q_unit(b)))) - 1.0) < tol


def angle_between(a, b):
    """Degrees the camera turns to go from orientation a to orientation b."""
    d = abs(sum(x * y for x, y in zip(q_unit(a), q_unit(b))))
    return math.degrees(2.0 * math.acos(min(1.0, d)))


def roll_of(q):
    """How far the camera is rolled: 0 when its sideways axis is level (no tilt of the
    picture), up to 1 when the sideways axis points straight up or down."""
    return abs(rotate(q, (1, 0, 0))[2])


# -- the 26 parts of the cube ---------------------------------------------------------------

FACE_NAMES = {
    (0, 0, 1): "top",
    (0, 0, -1): "bottom",
    (0, -1, 0): "front",
    (0, 1, 0): "back",
    (1, 0, 0): "right",
    (-1, 0, 0): "left",
}
FACE_LABELS = {
    "top": "TOP",
    "bottom": "BOTTOM",
    "front": "FRONT",
    "back": "BACK",
    "right": "RIGHT",
    "left": "LEFT",
}
# How far in from the cube's outline the flat face stops: the bevels (edge strips and
# corner triangles) take the rest. The cube is 2 wide (from -1 to 1).
BEVEL = 0.27
INNER = 1.0 - BEVEL


def _name(direction):
    """'top-front-right' style name: the faces the part touches, top/bottom first."""
    x, y, z = direction
    parts = []
    if z:
        parts.append("top" if z > 0 else "bottom")
    if y:
        parts.append("back" if y > 0 else "front")
    if x:
        parts.append("right" if x > 0 else "left")
    return "-".join(parts)


def _kind(direction):
    return {1: "face", 2: "edge", 3: "corner"}[sum(1 for c in direction if c)]


def _directions():
    found = []
    for x in (-1, 0, 1):
        for y in (-1, 0, 1):
            for z in (-1, 0, 1):
                if (x, y, z) != (0, 0, 0):
                    found.append((x, y, z))
    return found


def _polygon(direction):
    """Corners (3D) of the part's flat piece on the bevelled cube, in order around it."""
    axes = [i for i in range(3) if direction[i]]
    a = INNER
    points = []
    if len(axes) == 1:  # a face: a square at distance 1, a wide
        i = axes[0]
        j, k = [n for n in range(3) if n != i]
        for sj, sk in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
            p = [0.0, 0.0, 0.0]
            p[i], p[j], p[k] = direction[i], sj * a, sk * a
            points.append(tuple(p))
    elif len(axes) == 2:  # an edge strip between two faces
        i, j = axes
        k = [n for n in range(3) if n not in axes][0]
        for pi, pj, pk in ((1.0, a, -a), (1.0, a, a), (a, 1.0, a), (a, 1.0, -a)):
            p = [0.0, 0.0, 0.0]
            p[i], p[j], p[k] = direction[i] * pi, direction[j] * pj, pk
            points.append(tuple(p))
    else:  # a corner triangle
        for i in range(3):
            p = [direction[n] * a for n in range(3)]
            p[i] = float(direction[i])
            points.append(tuple(p))
    return points


REGIONS = [
    {"name": _name(d), "kind": _kind(d), "direction": d, "points": _polygon(d)}
    for d in _directions()
]
REGION_BY_NAME = {r["name"]: r for r in REGIONS}


def direction_of(name):
    return REGION_BY_NAME[name]["direction"]


# -- where the camera goes ----------------------------------------------------------------

DEFAULT_HOME = "top-front-right"  # Fusion's default Home: the isometric view, fitted


def target_orientation(name):
    """The camera orientation for a click on the part `name`: it looks straight at the part.
    Z stays up on screen, except for TOP (+Y up, front at the bottom) and BOTTOM (-Y up,
    front at the top), the usual orientations of those two views."""
    n = unit(direction_of(name))
    view = scale(n, -1.0)
    if abs(n[2]) > 0.999:
        up = (0.0, 1.0, 0.0) if n[2] > 0 else (0.0, -1.0, 0.0)
    else:
        up = unit(add((0.0, 0.0, 1.0), scale(view, -dot((0.0, 0.0, 1.0), view))))
    back = n
    right = cross(up, back)
    return q_from_axes(right, up, back)


def clean(q):
    """Removes rounding noise: matrix entries within 1e-5 of 0 or +-1 become exact, so that
    four 90-degree steps give back exactly the view you started from."""
    axes = []
    for v in camera_axes(q)[:2]:
        axes.append(tuple(round(c) if abs(c - round(c)) < 1e-5 else c for c in v))
    right, up = unit(axes[0]), unit(axes[1])
    if abs(dot(right, up)) > 1e-6:
        return q_unit(q)
    return q_from_axes(right, up, cross(right, up))


def face_on(q, tolerance_deg=0.5):
    """The face seen straight on (camera looking along its axis), or None."""
    view = rotate(q, (0, 0, -1))
    limit = math.cos(math.radians(tolerance_deg))
    for direction, name in FACE_NAMES.items():
        if -dot(view, direction) > limit:
            return name
    return None


def turn(q, side):
    """The view after a click on the small triangle on `side` of a face-on cube ('up',
    'down', 'left' or 'right'): the face that was on that side turns to face you, a turn of
    90 degrees about the camera's sideways or up axis."""
    right, up, _ = camera_axes(q)
    axis, angle = {
        "up": (right, -90.0),
        "down": (right, 90.0),
        "left": (up, -90.0),
        "right": (up, 90.0),
    }[side]
    return clean(q_mul(q_axis_angle(axis, math.radians(angle)), q))


def roll(q, clockwise):
    """The view after a click on a curved arrow: the picture turns 90 degrees (clockwise or
    counter-clockwise) about the line of sight."""
    back = rotate(q, (0, 0, 1))
    angle = 90.0 if clockwise else -90.0
    return clean(q_mul(q_axis_angle(back, math.radians(angle)), q))


ORBIT_DEG_PER_PIXEL = 0.8


def orbit(q, dx, dy, deg_per_pixel=ORBIT_DEG_PER_PIXEL):
    """Turntable orbit for a mouse move of (dx, dy) pixels (Qt: y grows downwards), the
    same as Shift + middle-drag with Fusion's constrained orbit: the model turns with the
    mouse about the world's up axis (Z) for sideways moves and tilts about the camera's
    sideways axis for up/down moves. Neither turn can roll the camera."""
    right, up, _ = camera_axes(q)
    # Upside down (orbited over the top), sideways moves turn the other way, like FreeCAD.
    side = 1.0 if up[2] >= 0 else -1.0
    spin = q_axis_angle((0.0, 0.0, 1.0), math.radians(-dx * deg_per_pixel * side))
    tilt = q_axis_angle(right, math.radians(-dy * deg_per_pixel))
    return q_unit(q_mul(spin, q_mul(tilt, q)))


# -- drawing the cube (2D layout in widget pixels) ----------------------------------------

# Light from the upper left, towards the viewer (camera coordinates): faces turned to it
# are drawn brighter, so the cube reads as a solid.
LIGHT = unit((-0.45, 0.65, 1.0))


def project(q, point):
    """Camera coordinates of a world point: x to the right, y up, z towards the viewer."""
    return rotate(q_conj(q), point)


def to_pixels(local, cx, cy, size):
    return (cx + local[0] * size, cy - local[1] * size)


def layout(q, cx, cy, size):
    """The parts of the cube the camera sees, back to front, for drawing and picking.

    Returns a list of dicts: name, kind, points (widget pixels), depth (bigger = nearer)
    and shade (0..1, brightness from the light). `size` is half the cube's width in pixels.
    A part whose flat side faces away from the camera (or is seen exactly edge-on) is left
    out: the cube is convex, so the rest never overlap."""
    parts = []
    for region in REGIONS:
        normal = project(q, unit(region["direction"]))
        if normal[2] <= 1e-4:
            continue
        local = [project(q, p) for p in region["points"]]
        depth = sum(p[2] for p in local) / len(local)
        parts.append(
            {
                "name": region["name"],
                "kind": region["kind"],
                "points": [to_pixels(p, cx, cy, size) for p in local],
                "depth": depth,
                "shade": 0.62 + 0.38 * max(0.0, dot(normal, LIGHT)),
                "facing": normal[2],
            }
        )
    parts.sort(key=lambda part: part["depth"])
    return parts


def label_frame(face):
    """(centre, right, up) of a face's label on the cube, as world vectors: the text sits
    on the face, upright for a person looking at that face (Z up; TOP and BOTTOM read with
    FRONT below them and above them)."""
    n = {name: d for d, name in FACE_NAMES.items()}[face]
    if n[2] > 0:
        up = (0.0, 1.0, 0.0)
    elif n[2] < 0:
        up = (0.0, -1.0, 0.0)
    else:
        up = (0.0, 0.0, 1.0)
    right = cross(up, n)
    return (float(n[0]), float(n[1]), float(n[2])), right, up


def label_transform(q, face, cx, cy, size):
    """The 2D map (m11, m12, m21, m22, dx, dy) of Qt's QTransform that puts text written in
    "cube units" (1 = half the cube; x right, y down) flat on the face as seen now."""
    centre, right, up = label_frame(face)
    c = to_pixels(project(q, centre), cx, cy, size)
    r = project(q, right)
    u = project(q, up)
    # Text x follows the face's right; text y (downwards) follows the face's down.
    return (r[0] * size, -r[1] * size, -u[0] * size, u[1] * size, c[0], c[1])


def point_in_polygon(x, y, points):
    """True when (x, y) is inside the polygon (any winding; edges count as inside)."""
    inside = False
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            cross_x = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x <= cross_x:
                inside = not inside
    if inside:
        return True
    # On the outline (a click exactly on a shared edge) counts too.
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        if _distance_to_segment(x, y, x1, y1, x2, y2) < 0.5:
            return True
    return False


def _distance_to_segment(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    length = dx * dx + dy * dy
    t = 0.0 if length == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length))
    return math.hypot(px - (ax + dx * t), py - (ay + dy * t))


def centroid(points):
    """The middle of a convex polygon (always inside it): where a test or a person aims."""
    x = sum(p[0] for p in points) / len(points)
    y = sum(p[1] for p in points) / len(points)
    return x, y


def pick(parts, x, y):
    """Name of the cube part under widget pixel (x, y), nearest first, or None."""
    for part in reversed(parts):
        if point_in_polygon(x, y, part["points"]):
            return part["name"]
    return None


# -- the buttons around the cube ----------------------------------------------------------


def controls(cx, cy, size, home_at):
    """The clickable buttons around the cube, in widget pixels.

    * 'home': the small house (always there), a square at `home_at` (x, y, side).
    * 'turn-up/down/left/right': triangles beside a face-on cube, pointing at the
      neighbouring face they turn to.
    * 'roll-ccw' / 'roll-cw': a curved arrow round the top-right corner of a face-on cube,
      in two halves, each with its own arrow head.

    The arrows only exist while a face is seen straight on (viewcube_ui decides). Their
    exact set and place in Fusion are unconfirmed (they follow Autodesk Inventor's cube:
    four triangles and two curved arrows)."""
    gap, depth, half = 5.0, 9.0, 7.0
    edge = size + gap
    found = [{"id": "home", "kind": "home", "rect": tuple(float(v) for v in home_at)}]
    triangles = {
        "turn-up": [(cx - half, cy - edge), (cx + half, cy - edge), (cx, cy - edge - depth)],
        "turn-down": [(cx - half, cy + edge), (cx + half, cy + edge), (cx, cy + edge + depth)],
        "turn-left": [(cx - edge, cy - half), (cx - edge, cy + half), (cx - edge - depth, cy)],
        "turn-right": [(cx + edge, cy - half), (cx + edge, cy + half), (cx + edge + depth, cy)],
    }
    for name, points in triangles.items():
        found.append({"id": name, "kind": "triangle", "points": points})
    radius = size * math.sqrt(2.0) + 6.0
    found.append(
        {
            "id": "roll-ccw",
            "kind": "arc",
            "centre": (cx, cy),
            "radius": radius,
            "start": 48.0,
            "end": 74.0,
            "head": "end",
        }
    )
    found.append(
        {
            "id": "roll-cw",
            "kind": "arc",
            "centre": (cx, cy),
            "radius": radius,
            "start": 16.0,
            "end": 42.0,
            "head": "start",
        }
    )
    return found


ARC_HALF_WIDTH = 7.0


def arc_point(control, angle_deg, offset=0.0):
    """Widget pixel on a curved arrow at `angle_deg` (0 = right, 90 = up), `offset` pixels
    outside its middle line."""
    cx, cy = control["centre"]
    r = control["radius"] + offset
    a = math.radians(angle_deg)
    return cx + r * math.cos(a), cy - r * math.sin(a)


def arc_head(control):
    """The triangle of a curved arrow's head (widget pixels)."""
    if control["head"] == "end":
        angle, sign = control["end"], 1.0
    else:
        angle, sign = control["start"], -1.0
    a = math.radians(angle)
    tip = arc_point(control, angle)
    # Direction along the arc (increasing angle, screen y down), and outwards.
    along = (-math.sin(a) * sign, -math.cos(a) * sign)
    out = (math.cos(a), -math.sin(a))
    base = (tip[0] - along[0] * 2.0, tip[1] - along[1] * 2.0)
    return [
        (tip[0] + along[0] * 6.0, tip[1] + along[1] * 6.0),
        (base[0] + out[0] * 5.0, base[1] + out[1] * 5.0),
        (base[0] - out[0] * 5.0, base[1] - out[1] * 5.0),
    ]


def hit_control(control, x, y):
    kind = control["kind"]
    if kind == "home":
        left, top, side = control["rect"]
        return left <= x <= left + side and top <= y <= top + side
    if kind == "triangle":
        # A little more room than the drawn triangle: it is small.
        cx = sum(p[0] for p in control["points"]) / 3.0
        cy = sum(p[1] for p in control["points"]) / 3.0
        grown = [(cx + (px - cx) * 1.4, cy + (py - cy) * 1.4) for px, py in control["points"]]
        return point_in_polygon(x, y, grown)
    if kind == "arc":
        cx, cy = control["centre"]
        distance = math.hypot(x - cx, y - cy)
        if abs(distance - control["radius"]) > ARC_HALF_WIDTH:
            return False
        angle = math.degrees(math.atan2(cy - y, x - cx))
        return control["start"] - 4.0 <= angle <= control["end"] + 4.0
    return False


def control_centre(control):
    """Where a person (or a test) clicks a button: its middle."""
    kind = control["kind"]
    if kind == "home":
        left, top, side = control["rect"]
        return left + side / 2.0, top + side / 2.0
    if kind == "triangle":
        return centroid(control["points"])
    middle = (control["start"] + control["end"]) / 2.0
    return arc_point(control, middle)


# -- Home, stored in the design ---------------------------------------------------------------

HOME_VERSION = 1


def encode_home(rotation, fit, camera=None):
    """The text stored in the document for its Home view. `rotation` is the camera
    orientation (x, y, z, w); `fit` True means "Fit to View" (Home fits the model), False
    "Fixed Distance" (Home also restores this zoom and position: `camera` is FreeCAD's
    camera description, view.getCamera())."""
    data = {"v": HOME_VERSION, "rotation": [float(c) for c in rotation], "fit": bool(fit)}
    if not fit and camera:
        data["camera"] = str(camera)
    return json.dumps(data, separators=(",", ":"))


def decode_home(text):
    """The Home stored in a document ({'rotation', 'fit', 'camera'}), or None when there is
    none or it cannot be read (then the default Home is used)."""
    if not text:
        return None
    try:
        data = json.loads(text)
        rotation = [float(c) for c in data["rotation"]]
        if len(rotation) != 4 or not all(math.isfinite(c) for c in rotation):
            return None
        if sum(c * c for c in rotation) < 1e-12:
            return None
        fit = bool(data.get("fit", True))
        camera = data.get("camera") if not fit else None
        return {"rotation": q_unit(tuple(rotation)), "fit": fit or not camera, "camera": camera}
    except (ValueError, KeyError, TypeError):
        return None


def default_home():
    return {"rotation": target_orientation(DEFAULT_HOME), "fit": True, "camera": None}
