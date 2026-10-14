# SPDX-License-Identifier: LGPL-2.1-or-later
"""The maths of moving an assembly by hand (pure Python: no FreeCAD, no Qt; unit tested in
SciForgeTests/unit/test_motion_core.py). joints_drag.py, joints.py and joints_ui.py turn these
into placements. Spec: docs/sciforge/parity/joints.md ("Dragging components", "Motion Link",
"Contact Sets", "Motion Study").

Component Drag (Fusion: press on a component and drag it in the canvas): the mouse gives a
ray (from the eye through the pointer) and the drag holds the point of the component that
was pressed (the grab point). Each joint turns that ray into the joint's own motion:

- a revolute joint turns the component about its axis by the angle the pointer went round
  the axis, seen in the plane of the turn (a dial); when that plane is seen edge-on, the
  grab point goes to the place on its circle nearest the pointer's ray;
- a slider slides it to the point of its line nearest the pointer's ray;
- a cylindrical / pin-slot joint does both (slide first, then the turn);
- a planar joint slides it in its plane under the pointer;
- a ball joint turns it about the ball's centre so the grab point sits under the pointer;
- a free component (no joint) moves in the plane facing the viewer through the grab point.

Vectors are (x, y, z) tuples; rotations 3x3 tuples of rows (see joints_core).
"""

import math

from . import joints_core as core

EDGE_ON = 0.2  # |ray . axis| below this: the plane of a turn is seen nearly edge-on
SAMPLES = 720  # the circle is searched every half degree when seen edge-on


# -- small helpers -------------------------------------------------------------------------------
def unwrap(angle, previous):
    """`angle` (degrees) plus the whole turns that bring it nearest `previous`: a drag that
    goes on round the axis keeps counting (270, 360, 450...)."""
    if previous is None:
        return float(angle)
    turns = round((previous - angle) / 360.0)
    return float(angle + 360.0 * turns)


def ray_plane(ray_o, ray_d, point, normal):
    """Where the ray meets the plane through `point` with `normal`, or None (parallel)."""
    denom = core.dot(ray_d, normal)
    if abs(denom) < 1e-12:
        return None
    t = core.dot(core.vsub(point, ray_o), normal) / denom
    return core.vadd(ray_o, core.vscale(ray_d, t))


def distance_to_ray(p, ray_o, ray_d):
    """Distance from a point to the (infinite) line of the ray."""
    d = core.unit(ray_d)
    w = core.vsub(p, ray_o)
    return core.norm(core.cross(w, d))


def _basis(axis, radial):
    """Unit e1 along `radial` (already across `axis`) and e2 = axis x e1."""
    e1 = core.unit(radial)
    e2 = core.cross(core.unit(axis), e1)
    return e1, e2


# -- the drag of each joint type -------------------------------------------------------------------
def turn_from_ray(center, axis, grab, ray_o, ray_d, previous=0.0):
    """Degrees to turn the component about the line (center, axis) so the grab point follows
    the pointer's ray, counted from where the grab point was (0 = the press), unwrapped near
    `previous` (the angle of the last mouse move). None when the grab point lies on the axis
    (nothing to turn by)."""
    a = core.unit(axis)
    rel = core.vsub(grab, center)
    h = core.dot(rel, a)
    radial = core.vsub(rel, core.vscale(a, h))
    if core.norm(radial) < 1e-9:
        return None
    hub = core.vadd(center, core.vscale(a, h))  # the centre of the grab point's circle
    e1, e2 = _basis(a, radial)
    d = core.unit(ray_d)
    if abs(core.dot(d, a)) >= EDGE_ON:
        q = ray_plane(ray_o, d, hub, a)
        if q is None:
            return previous
        v = core.vsub(q, hub)
        if core.norm(v) < 1e-12:
            return previous
        angle = math.degrees(math.atan2(core.dot(v, e2), core.dot(v, e1)))
        return unwrap(angle, previous)
    # seen edge-on: the point of the circle nearest the ray (of the two that line up with
    # the pointer, the one nearer the last angle)
    radius = core.norm(radial)

    def point_at(deg):
        t = math.radians(deg)
        return core.vadd(
            hub, core.vadd(core.vscale(e1, radius * math.cos(t)), core.vscale(e2, radius * math.sin(t)))
        )

    best = []
    for i in range(SAMPLES):
        deg = -180.0 + 360.0 * i / SAMPLES
        best.append((distance_to_ray(point_at(deg), ray_o, d), deg))
    lowest = min(b[0] for b in best)
    slack = max(1e-6, 0.02 * radius)
    # the dips of the distance round the circle (each a place lining up with the pointer)
    count = len(best)
    near = [
        deg
        for i, (dist, deg) in enumerate(best)
        if dist <= lowest + slack
        and dist <= best[i - 1][0]
        and dist <= best[(i + 1) % count][0]
    ] or [min(best)[1]]
    prev = previous if previous is not None else 0.0
    chosen = min(near, key=lambda deg: abs(unwrap(deg, prev) - prev))
    # refine around the chosen sample (golden section on the distance)
    lo, hi = chosen - 0.5, chosen + 0.5
    for _ in range(40):
        m1 = lo + (hi - lo) * 0.382
        m2 = lo + (hi - lo) * 0.618
        if distance_to_ray(point_at(m1), ray_o, d) < distance_to_ray(point_at(m2), ray_o, d):
            hi = m2
        else:
            lo = m1
    return unwrap(0.5 * (lo + hi), prev)


def slide_from_ray(grab, axis, ray_o, ray_d):
    """How far (mm, along the unit axis) to slide so the grab point is the point of its line
    nearest the pointer's ray; None when the line is seen end-on (the ray runs along it)."""
    a = core.unit(axis)
    d = core.unit(ray_d)
    w0 = core.vsub(grab, ray_o)
    b = core.dot(a, d)
    denom = 1.0 - b * b
    if denom < 1e-6:
        return None
    return (b * core.dot(d, w0) - core.dot(a, w0)) / denom


def plane_move_from_ray(grab, normal, ray_o, ray_d):
    """The move (a vector in the plane through the grab point) that puts the grab point under
    the pointer; None when the plane is seen edge-on."""
    q = ray_plane(ray_o, core.unit(ray_d), grab, core.unit(normal))
    if q is None:
        return None
    move = core.vsub(q, grab)
    n = core.unit(normal)
    return core.vsub(move, core.vscale(n, core.dot(move, n)))  # exactly in the plane


def free_move_from_ray(grab, view_dir, ray_o, ray_d):
    """A component held by nothing moves in the plane facing the viewer (Fusion)."""
    return plane_move_from_ray(grab, view_dir, ray_o, ray_d)


def ball_turn_from_ray(center, grab, ray_o, ray_d):
    """The smallest rotation (3x3) about the ball's centre that takes the grab point to the
    point of its sphere nearest the pointer's ray; identity when the grab point is the
    centre."""
    r0 = core.vsub(grab, center)
    radius = core.norm(r0)
    if radius < 1e-9:
        return core.IDENTITY
    d = core.unit(ray_d)
    # nearest point of the ray to the centre, then onto the sphere (front hit when it cuts)
    w = core.vsub(center, ray_o)
    t = core.dot(w, d)
    closest = core.vadd(ray_o, core.vscale(d, t))
    off = core.vsub(closest, center)
    gap = core.norm(off)
    if gap < radius:
        back = math.sqrt(max(0.0, radius * radius - gap * gap))
        target = core.vadd(ray_o, core.vscale(d, t - back))
    elif gap > 1e-12:
        target = core.vadd(center, core.vscale(off, radius / gap))
    else:
        return core.IDENTITY
    return rotation_between(r0, core.vsub(target, center))


def rotation_between(a, b):
    """The smallest rotation taking direction a onto direction b."""
    ua, ub = core.unit(a), core.unit(b)
    c = max(-1.0, min(1.0, core.dot(ua, ub)))
    axis = core.cross(ua, ub)
    if core.norm(axis) < 1e-12:
        if c > 0:
            return core.IDENTITY
        pick = core.X if abs(ua[0]) < 0.9 else core.Y
        axis = core.cross(ua, pick)
        return core.rot_axis_angle(axis, 180.0)
    return core.rot_axis_angle(axis, math.degrees(math.acos(c)))


DRAG_KIND = {
    "revolute": "turn",
    "slider": "slide",
    "cylindrical": "turn+slide",
    "pinslot": "turn+slide",
    "planar": "plane",
    "ball": "ball",
    "rigid": None,
}


# -- motion links ----------------------------------------------------------------------------------
class LinkError(ValueError):
    """A motion link Fusion would refuse; the text says what to do."""


def link_ratio(value1, value2, reverse=False):
    """How much joint 2 moves per unit of joint 1 (Fusion: joint 1 moving `value1` moves
    joint 2 by `value2`; Reverse turns the second the other way)."""
    if abs(value1) < 1e-12:
        raise LinkError("The first joint's value cannot be 0: type how far it moves.")
    ratio = float(value2) / float(value1)
    return -ratio if reverse else ratio


def link_offset(ratio, now1, now2):
    """The offset that keeps both joints where they are when the link is made:
    value2 = ratio * value1 + offset."""
    return float(now2) - ratio * float(now1)


def linked_value(value1, ratio, offset):
    return ratio * float(value1) + offset


def unlinked_value(value2, ratio, offset):
    """Joint 1's value for joint 2 at `value2` (a link drives both ways)."""
    if abs(ratio) < 1e-12:
        return None
    return (float(value2) - offset) / ratio


# -- contact: stop where the parts touch -----------------------------------------------------------
def last_free(blocked, steps=14):
    """The largest fraction f in [0, 1] of a move for which blocked(f) is False, given that
    the move's start (0) is free: 1.0 when the whole move is free, else found by halving
    (blocked is a test of the parts' overlap at that fraction)."""
    if not blocked(1.0):
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(steps):
        mid = 0.5 * (lo + hi)
        if blocked(mid):
            hi = mid
        else:
            lo = mid
    return lo


def boxes_meet(a, b, tol=0.0):
    """Two boxes (xmin, ymin, zmin, xmax, ymax, zmax) overlap or touch (within tol)."""
    return all(a[i] <= b[i + 3] + tol and b[i] <= a[i + 3] + tol for i in range(3))


# -- motion study ----------------------------------------------------------------------------------
STUDY_STEPS = 100  # Fusion's motion study counts steps 0 to 100
STUDY_MODES = ("once", "loop", "pingpong")
STUDY_MODE_LABELS = {"once": "Play Once", "loop": "Loop", "pingpong": "Ping-Pong"}
STEPS_PER_SECOND = 25.0  # at speed 1


def study_value(keys, step):
    """A joint's value at `step` from its key points [(step, value)]: straight lines between
    the points, flat before the first and after the last; None without points."""
    points = sorted((float(s), float(v)) for s, v in keys or [])
    if not points:
        return None
    if step <= points[0][0]:
        return points[0][1]
    for (s0, v0), (s1, v1) in zip(points, points[1:]):
        if s0 <= step <= s1:
            if s1 - s0 < 1e-12:
                return v1
            return v0 + (v1 - v0) * (step - s0) / (s1 - s0)
    return points[-1][1]


def study_step(seconds, steps=STUDY_STEPS, speed=1.0, mode="once"):
    """(step, done) of a playing study after `seconds`: Play Once runs 0..steps and stops,
    Loop starts again at 0, Ping-Pong goes back and forth."""
    steps = max(1, int(steps))
    travelled = max(0.0, seconds) * STEPS_PER_SECOND * max(0.05, float(speed))
    if mode == "loop":
        return travelled % steps, False
    if mode == "pingpong":
        phase = travelled % (2 * steps)
        return (phase if phase <= steps else 2 * steps - phase), False
    if travelled >= steps:
        return float(steps), True
    return travelled, False


def set_key(keys, step, value):
    """Key points with the one at `step` set to `value` (added or replaced), sorted."""
    out = [(float(s), float(v)) for s, v in keys or [] if abs(float(s) - float(step)) > 1e-9]
    out.append((float(step), float(value)))
    return sorted(out)


def drop_key(keys, step):
    return [(float(s), float(v)) for s, v in keys or [] if abs(float(s) - float(step)) > 1e-9]
