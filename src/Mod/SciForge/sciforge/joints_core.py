# SPDX-License-Identifier: LGPL-2.1-or-later
"""The maths behind Fusion's joints: pure Python (no FreeCAD, no Qt), unit tested
(SciForgeTests/unit/test_joints_core.py). joints.py turns these into FreeCAD placements.

A *frame* is where a joint origin sits and how it points: ``(origin, rot)`` with ``origin``
an (x, y, z) tuple and ``rot`` a 3x3 rotation matrix as a tuple of rows; its columns are the
frame's X, Y and Z axes. Fusion's rules copied here (docs/sciforge/parity/joints.md):

- a joint origin on a face points its Z along the face's normal, on an edge along the edge,
  at a circle's centre along the circle's axis, at a corner like the component's own axes;
- component 1 moves onto component 2 so that the two joint origins coincide with their Z
  axes against each other (faces mate); Flip turns component 1 over (Z axes the same way);
- Offset X / Y / Z move component 1 along component 2's joint origin axes, Angle turns it
  about that Z;
- the joint's value is the turn about Z (Revolute, Cylindrical, Pin-Slot, Planar) and the
  slide along Z (Slider, Cylindrical) of joint origin 1 seen from joint origin 2, measured
  from the mated pose, so a fresh joint reads 0.
"""

import math

JOINT_TYPES = ["rigid", "revolute", "slider", "cylindrical", "pinslot", "planar", "ball"]
TITLES = {
    "rigid": "Rigid",
    "revolute": "Revolute",
    "slider": "Slider",
    "cylindrical": "Cylindrical",
    "pinslot": "Pin-Slot",
    "planar": "Planar",
    "ball": "Ball",
}
# FreeCAD's Assembly joint type that gives the motion (Planar / Pin-Slot ride on its Distance
# joint between two flat faces, see joints.py).
FREECAD_TYPE = {
    "rigid": "Fixed",
    "revolute": "Revolute",
    "slider": "Slider",
    "cylindrical": "Cylindrical",
    "pinslot": "Distance",
    "planar": "Distance",
    "ball": "Ball",
}
HAS_ANGLE = {"revolute", "cylindrical", "pinslot", "planar"}
HAS_DISTANCE = {"slider", "cylindrical", "pinslot"}
# Which limits FreeCAD's solver knows (joints.md, Known gaps)
ANGLE_LIMITS = {"revolute", "cylindrical"}
LENGTH_LIMITS = {"slider", "cylindrical"}
# Fusion's axis choices of the Motion tab, per type: (label, options)
AXIS_CHOICES = {
    "revolute": [("Rotate", ("z", "x", "y"))],
    "slider": [("Slide", ("z", "x", "y"))],
    "cylindrical": [("Rotate", ("z", "x", "y"))],
    "pinslot": [("Rotate", ("z",)), ("Slide", ("x", "y"))],
    "planar": [("Normal", ("z", "x", "y"))],
    "ball": [],
    "rigid": [],
}
AXIS_LABELS = {"x": "X Axis", "y": "Y Axis", "z": "Z Axis"}
SNAP_KINDS = ("centre", "vertex", "midpoint", "circle", "point", "origin", "asbuilt")
EPS = 1e-9


class JointError(ValueError):
    """Something Fusion's dialog would refuse; the text says what to do."""


# -- vectors ---------------------------------------------------------------------------------------
def vadd(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def vsub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def vscale(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def norm(a):
    return math.sqrt(dot(a, a))


def unit(a):
    n = norm(a)
    if n < EPS:
        raise JointError("A direction of zero length.")
    return vscale(a, 1.0 / n)


def distance(a, b):
    return norm(vsub(a, b))


# -- rotations (3x3, rows) -------------------------------------------------------------------------
IDENTITY = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
X, Y, Z = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)


def rot_axis_angle(axis, degrees):
    """Rotation of `degrees` about `axis` (right hand rule)."""
    x, y, z = unit(axis)
    a = math.radians(degrees)
    c, s, t = math.cos(a), math.sin(a), 1.0 - math.cos(a)
    return (
        (t * x * x + c, t * x * y - s * z, t * x * z + s * y),
        (t * x * y + s * z, t * y * y + c, t * y * z - s * x),
        (t * x * z - s * y, t * y * z + s * x, t * z * z + c),
    )


def rot_mul(a, b):
    return tuple(
        tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3)
    )


def rot_transpose(a):
    return tuple(tuple(a[j][i] for j in range(3)) for i in range(3))


def rot_apply(r, v):
    return tuple(r[i][0] * v[0] + r[i][1] * v[1] + r[i][2] * v[2] for i in range(3))


def rot_from_axes(x, y, z):
    """The rotation whose columns are the axes x, y, z (each a unit vector)."""
    return ((x[0], y[0], z[0]), (x[1], y[1], z[1]), (x[2], y[2], z[2]))


def quaternion(r):
    """(w, x, y, z) of a rotation matrix."""
    trace = r[0][0] + r[1][1] + r[2][2]
    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0
        return (0.25 * s, (r[2][1] - r[1][2]) / s, (r[0][2] - r[2][0]) / s, (r[1][0] - r[0][1]) / s)
    if r[0][0] > r[1][1] and r[0][0] > r[2][2]:
        s = math.sqrt(1.0 + r[0][0] - r[1][1] - r[2][2]) * 2.0
        return ((r[2][1] - r[1][2]) / s, 0.25 * s, (r[0][1] + r[1][0]) / s, (r[0][2] + r[2][0]) / s)
    if r[1][1] > r[2][2]:
        s = math.sqrt(1.0 + r[1][1] - r[0][0] - r[2][2]) * 2.0
        return ((r[0][2] - r[2][0]) / s, (r[0][1] + r[1][0]) / s, 0.25 * s, (r[1][2] + r[2][1]) / s)
    s = math.sqrt(1.0 + r[2][2] - r[0][0] - r[1][1]) * 2.0
    return ((r[1][0] - r[0][1]) / s, (r[0][2] + r[2][0]) / s, (r[1][2] + r[2][1]) / s, 0.25 * s)


def twist_about(r, axis):
    """How much (degrees) the rotation `r` turns about `axis`: the twist of its swing-twist
    split. Taking it back out leaves the smallest rotation that still swings the axis."""
    w, x, y, z = quaternion(r)
    a = unit(axis)
    along = dot((x, y, z), a)
    return math.degrees(2.0 * math.atan2(along, w))


def turn_about_point(point, axis, degrees):
    """The frame that turns the world about a line through `point` along `axis`."""
    r = rot_axis_angle(axis, degrees)
    return (vsub(point, rot_apply(r, point)), r)


def axis_of(r, index):
    """Column `index` of the rotation: the frame's X (0), Y (1) or Z (2) axis."""
    return (r[0][index], r[1][index], r[2][index])


def rot_from_z(z, x_hint=None):
    """A rotation whose Z is `z`; X follows `x_hint` projected into the plane, else a stable
    perpendicular (the same for the same z, so joint origins do not jump between recomputes)."""
    z = unit(z)
    x = None
    if x_hint is not None:
        projected = vsub(x_hint, vscale(z, dot(x_hint, z)))
        if norm(projected) > 1e-6:
            x = unit(projected)
    if x is None:
        pick = X if abs(dot(z, X)) < 0.9 else Y
        x = unit(vsub(pick, vscale(z, dot(pick, z))))
    y = cross(z, x)
    return rot_from_axes(x, y, z)


# Turning a frame so that its named axis becomes the motion axis (Fusion's Rotate / Slide /
# Normal choice): Z stays, X -> Z, Y -> Z.
AXIS_TO_Z = {
    "z": IDENTITY,
    "x": rot_from_axes((0.0, 0.0, -1.0), Y, X),  # new Z = old X, new X = -old Z
    "y": rot_from_axes(X, (0.0, 0.0, -1.0), Y),  # new Z = old Y, new Y = -old Z
}


def to_motion_axis(frame, axis):
    """The frame turned so that its `axis` ("x", "y", "z") is the Z the solver moves about."""
    if axis not in AXIS_TO_Z:
        raise JointError("Unknown axis %r." % (axis,))
    return (frame[0], rot_mul(frame[1], AXIS_TO_Z[axis]))


# -- frames (placements) ---------------------------------------------------------------------------
def frame(origin=(0.0, 0.0, 0.0), rot=IDENTITY):
    return (tuple(float(c) for c in origin), rot)


def compose(a, b):
    """a then b: the frame b expressed in a (a * b in FreeCAD's Placement sense)."""
    return (vadd(a[0], rot_apply(a[1], b[0])), rot_mul(a[1], b[1]))


def inverse(f):
    rt = rot_transpose(f[1])
    return (vscale(rot_apply(rt, f[0]), -1.0), rt)


def apply(f, p):
    return vadd(f[0], rot_apply(f[1], p))


def same_frame(a, b, tol=1e-6):
    if distance(a[0], b[0]) > tol:
        return False
    return all(abs(a[1][i][j] - b[1][i][j]) <= tol for i in range(3) for j in range(3))


# -- Fusion's alignment ----------------------------------------------------------------------------
FLIP = rot_axis_angle(X, 180.0)  # turning a joint origin over: Z against, X kept


def flip_frame(f):
    """The frame turned over about its X: faces mate when joint origin 1 is stored this way
    (the solver wants the two joint origins to coincide, Z the same way). Fusion's Flip
    button leaves it out."""
    return (f[0], rot_mul(f[1], FLIP))


def stored_offset(offset=(0.0, 0.0, 0.0), angle=0.0, mate=True):
    """What joint origin 1 is composed with before it is stored for the solver. The solver
    makes the two stored joint origins coincide; Fusion wants component 1's own joint origin
    at jcs2 * (offset along jcs2's axes) * (Angle about its Z) * (turned over when faces
    mate). So the stored one is that, undone: stored = own * stored_offset(...)."""
    f = frame(offset, rot_axis_angle(Z, angle))
    if mate:
        f = flip_frame(f)
    return inverse(f)


def own_frame(stored, offset=(0.0, 0.0, 0.0), angle=0.0, mate=True):
    """Component 1's own joint origin (the triad Fusion draws) from the stored one."""
    return compose(stored, inverse(stored_offset(offset, angle, mate)))


def mate_transform(jcs1, jcs2):
    """The transform T (a frame) to apply to component 1's placement so that its stored joint
    origin `jcs1` lands on `jcs2`: new placement = T * old placement."""
    return compose(jcs2, inverse(jcs1))


def keep_heading(transform, point, axis):
    """Fusion does not spin a component about the joint axis when it mates it: the same
    transform with its turn about `axis` (through `point`) taken out."""
    theta = twist_about(transform[1], axis)
    return compose(turn_about_point(point, axis, -theta), transform)


def relative(jcs1, jcs2):
    """Joint origin 1 seen from joint origin 2."""
    return compose(inverse(jcs2), jcs1)


SLIDE_INDEX = {"x": 0, "y": 1, "z": 2}


def joint_value(jcs1, jcs2, slide_axis="z"):
    """(angle in degrees about Z, slide along `slide_axis`) of joint origin 1 in joint origin
    2, measured from the mated pose: 0 for a fresh joint; the Angle / Offset typed in the
    dialog show up here; the turn is positive the right-hand way about joint origin 2's Z.
    A Pin-Slot slides along its slot (X or Y of the joint origin), everything else along Z."""
    rel = relative(jcs1, jcs2)
    x1 = axis_of(rel[1], 0)
    angle = math.degrees(math.atan2(x1[1], x1[0]))
    return angle, rel[0][SLIDE_INDEX[slide_axis]]


def driven_frame(jcs1, jcs2, angle=None, slide=None, slide_axis="z"):
    """Joint origin 1's new global frame when the joint is driven to `angle` degrees and / or
    `slide` mm (either may be None: unchanged). The turn is about joint origin 2's Z through
    its origin; the slide along joint origin 2's `slide_axis`."""
    rel = relative(jcs1, jcs2)
    now_angle, now_slide = joint_value(jcs1, jcs2, slide_axis)
    if angle is not None:
        # the turn is about joint origin 1's own Z (a pin turns where it stands in its slot)
        turn = rot_axis_angle(Z, angle - now_angle)
        rel = (rel[0], rot_mul(turn, rel[1]))
    if slide is not None:
        step = [0.0, 0.0, 0.0]
        step[SLIDE_INDEX[slide_axis]] = slide - now_slide
        rel = (vadd(rel[0], tuple(step)), rel[1])
    return compose(jcs2, rel)


def drive_transform(jcs1, jcs2, angle=None, slide=None, slide_axis="z"):
    """The transform to apply to the moving component's placement for `driven_frame`."""
    return compose(driven_frame(jcs1, jcs2, angle, slide, slide_axis), inverse(jcs1))


def wobble_frame(jcs1, jcs2, pitch=0.0, yaw=0.0):
    """A Ball joint turned by `pitch` about joint origin 2's X and `yaw` about its Y (for the
    animated preview); the origin stays put."""
    rel = relative(jcs1, jcs2)
    turn = rot_mul(rot_axis_angle(Y, yaw), rot_axis_angle(X, pitch))
    rel = (rot_apply(turn, rel[0]), rot_mul(turn, rel[1]))
    return compose(compose(jcs2, rel), inverse(jcs1))


def slide_frame(jcs1, jcs2, dx=0.0, dy=0.0):
    """A Planar joint slid by dx, dy in joint origin 2's plane (the animated preview)."""
    rel = relative(jcs1, jcs2)
    rel = (vadd(rel[0], (dx, dy, 0.0)), rel[1])
    return compose(compose(jcs2, rel), inverse(jcs1))


# -- limits ----------------------------------------------------------------------------------------
def clamp(value, low=None, high=None):
    """The value kept between the enabled limits (None = no limit that side). Swapped
    limits are taken in order, as FreeCAD does."""
    if low is not None and high is not None and low > high:
        low, high = high, low
    if low is not None and value < low:
        return float(low)
    if high is not None and value > high:
        return float(high)
    return float(value)


def normalize_limits(limits):
    """A limits dict ({"min": v or None, "max": v or None, "rest": v or None}) with values as
    floats and a refused rest outside the range."""
    out = {}
    for key in ("min", "max", "rest"):
        v = limits.get(key) if limits else None
        out[key] = None if v is None else float(v)
    if out["min"] is not None and out["max"] is not None and out["min"] > out["max"]:
        out["min"], out["max"] = out["max"], out["min"]
    if out["rest"] is not None and clamp(out["rest"], out["min"], out["max"]) != out["rest"]:
        raise JointError("The rest position must lie between the minimum and the maximum.")
    return out


def sweep(t, start, low=None, high=None, span=1.0):
    """The value of an animated joint at phase t (0..1): a smooth out-and-back trip. Inside
    both limits it travels the whole range; otherwise it swings `span` either side of
    `start`, never past an enabled limit. The trip starts and ends at `start`."""
    if low is not None and high is not None:
        low, high = min(low, high), max(low, high)
        up, down = high - start, start - low
    else:
        up = span if high is None else max(0.0, min(span, high - start))
        down = span if low is None else max(0.0, min(span, start - low))
    s = math.sin(2.0 * math.pi * t)
    return start + (up * s if s >= 0.0 else down * s)


# -- snap points -----------------------------------------------------------------------------------
def nearest(points, target):
    """Index of the point nearest to target, or None."""
    best = None
    for i, p in enumerate(points):
        d = distance(p, target)
        if best is None or d < best[0]:
            best = (d, i)
    return None if best is None else best[1]


def nearest_on_screen(pixels, pointer, radius):
    """Index of the screen point within `radius` pixels of the pointer, nearest first."""
    best = None
    for i, (x, y) in enumerate(pixels):
        d = math.hypot(x - pointer[0], y - pointer[1])
        if d <= radius and (best is None or d < best[0]):
            best = (d, i)
    return None if best is None else best[1]


def dedupe(snaps, tol=1e-6):
    """Snaps at one place keep the first (a corner that is also an edge's end)."""
    kept = []
    for snap in snaps:
        if all(distance(snap["point"], k["point"]) > tol for k in kept):
            kept.append(snap)
    return kept


def label_number(labels, base):
    """The next free number for "<base> N" among existing labels (Fusion counts up and never
    reuses a number still in use)."""
    used = set()
    for label in labels:
        text = (label or "").strip()
        if text.startswith(base + " "):
            tail = text[len(base) + 1 :].strip()
            if tail.isdigit():
                used.add(int(tail))
    n = 1
    while n in used:
        n += 1
    return n


def default_span(size):
    """How far the animated preview slides for a part of this size (mm)."""
    return max(1.0, 0.25 * float(size))
