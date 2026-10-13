# SPDX-License-Identifier: LGPL-2.1-or-later
"""The maths of SciForge's own sketch drawing tools (sketch_draw_tools.py does the mouse,
the preview and the sketch): the shapes Fusion's tools make from the clicked points.

No FreeCAD, no Qt here: plain (x, y) tuples in sketch millimetres, so it is unit tested
(SciForgeTests/unit/test_sketch_draw_core.py). Angles are radians unless a name says deg.

- Midpoint Line: the line symmetric about the first click.
- 2-Point Circle: the two clicks are the ends of a diameter.
- 2-Tangent Circle: the circle touching two lines in the quadrant the pointer is in.
- 3-Tangent Circle: the circles touching three lines (incircle and excircles), the one
  nearest the pointer.
- Edge Polygon: a regular polygon from one edge and the side it goes to.
- Slots: centre-to-centre, overall and centre-point linear slots, the three-point arc
  slot.
- Conic: Fusion's rho conic as a rational quadratic Bezier (start, apex, end; the apex
  weight is rho / (1 - rho)), its shoulder point and the rho a pointer asks for.
"""

import math

EPS = 1e-9


# -- 2D vectors ------------------------------------------------------------------------
def sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def add(a, b):
    return (a[0] + b[0], a[1] + b[1])


def mul(a, k):
    return (a[0] * k, a[1] * k)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def length(a):
    return math.hypot(a[0], a[1])


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def unit(a):
    n = length(a)
    return (a[0] / n, a[1] / n) if n > EPS else None


def left(a):
    """The direction a turned a quarter turn counterclockwise."""
    return (-a[1], a[0])


def mid(a, b):
    return ((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5)


def polar(angle, radius=1.0, centre=(0.0, 0.0)):
    return (centre[0] + radius * math.cos(angle), centre[1] + radius * math.sin(angle))


def angle_of(v):
    return math.atan2(v[1], v[0])


def rotate(p, centre, angle):
    c, s = math.cos(angle), math.sin(angle)
    x, y = p[0] - centre[0], p[1] - centre[1]
    return (centre[0] + c * x - s * y, centre[1] + s * x + c * y)


# -- lines -------------------------------------------------------------------------------
def direction_point(start, pointer, length_=None, angle=None):
    """The end of a line from `start` towards `pointer`; a typed `length_` (mm) or
    `angle` (radians from the sketch's X axis) wins over the pointer's own. None when the
    pointer is on the start and nothing is typed."""
    d = sub(pointer, start)
    if angle is not None:
        u = (math.cos(angle), math.sin(angle))
        if length_ is None:
            # the pointer's distance along the typed direction (never backwards)
            length_ = max(dot(d, u), 0.0)
    else:
        u = unit(d)
        if u is None:
            return None
        if length_ is None:
            length_ = length(d)
    if length_ <= EPS:
        return None
    return add(start, mul(u, length_))


def midpoint_line(middle, pointer, length_=None, angle=None):
    """(a, b): the Midpoint Line's ends. `pointer` is one end; a typed length is the whole
    line's length (Fusion's length box), the angle that of middle -> pointer."""
    half = None if length_ is None else length_ * 0.5
    b = direction_point(middle, pointer, half, angle)
    if b is None:
        return None
    a = sub(mul(middle, 2.0), b)
    return a, b


def line_line(p1, d1, p2, d2):
    """Where the endless lines (point, direction) meet, or None when parallel."""
    den = cross(d1, d2)
    if abs(den) < EPS * max(1.0, length(d1) * length(d2)):
        return None
    t = cross(sub(p2, p1), d2) / den
    return add(p1, mul(d1, t))


def point_line_distance(p, a, b):
    """Distance from p to the endless line through a and b."""
    u = unit(sub(b, a))
    if u is None:
        return dist(p, a)
    return abs(cross(u, sub(p, a)))


def foot(p, a, b):
    """The foot of the perpendicular from p on the endless line a-b."""
    ab = sub(b, a)
    n2 = dot(ab, ab)
    if n2 < EPS:
        return a
    return add(a, mul(ab, dot(sub(p, a), ab) / n2))


# -- circles ----------------------------------------------------------------------------
def circle_2point(a, b, diameter=None):
    """(centre, radius) of the circle whose diameter runs from a to b. A typed diameter
    keeps the direction a -> b and moves b."""
    if diameter is not None:
        u = unit(sub(b, a))
        if u is None or diameter <= EPS:
            return None
        b = add(a, mul(u, diameter))
    r = dist(a, b) * 0.5
    if r <= EPS:
        return None
    return mid(a, b), r


def circle_3point(p1, p2, p3):
    """(centre, radius) of the circle through three points, or None (in a line)."""
    ax, ay = p1
    bx, by = p2
    cx, cy = p3
    d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < EPS:
        return None
    a2, b2, c2 = ax * ax + ay * ay, bx * bx + by * by, cx * cx + cy * cy
    ux = (a2 * (by - cy) + b2 * (cy - ay) + c2 * (ay - by)) / d
    uy = (a2 * (cx - bx) + b2 * (ax - cx) + c2 * (bx - ax)) / d
    centre = (ux, uy)
    return centre, dist(centre, p1)


def _line(line):
    """(point, unit direction, unit left normal) of a line given as (a, b)."""
    a, b = line
    u = unit(sub(b, a))
    if u is None:
        raise ValueError("a line of no length")
    return a, u, left(u)


def tangent_circle_2lines(line1, line2, pointer, radius=None):
    """(centre, radius) of the circle touching both endless lines, in the quadrant the
    pointer is in (Fusion's 2-Tangent Circle: the click picks the side). Without a typed
    radius the centre follows the pointer along that quadrant's bisector. Parallel lines:
    the circle between them (its size is set by the gap; a typed radius cannot change
    it). None when the pointer gives no circle."""
    p1, u1, n1 = _line(line1)
    p2, u2, n2 = _line(line2)
    x = line_line(p1, u1, p2, u2)
    if x is None:
        # parallel: the centre on the middle line, opposite the pointer's projection
        gap = dot(sub(p2, p1), n1)
        if abs(gap) <= EPS:
            return None
        r = abs(gap) * 0.5
        middle = add(p1, mul(n1, gap * 0.5))
        centre = add(middle, mul(u1, dot(sub(pointer, middle), u1)))
        return centre, r
    s1 = 1.0 if dot(n1, sub(pointer, p1)) >= 0 else -1.0
    s2 = 1.0 if dot(n2, sub(pointer, p2)) >= 0 else -1.0
    b = unit(add(mul(n1, s1), mul(n2, s2)))
    if b is None:
        return None
    rate = s1 * dot(n1, b)  # how fast the distance to the lines grows along b
    if rate <= EPS:
        return None
    if radius is not None:
        if radius <= EPS:
            return None
        return add(x, mul(b, radius / rate)), radius
    t = dot(sub(pointer, x), b)
    if t <= EPS:
        return None
    return add(x, mul(b, t)), t * rate


def tangent_circles_3lines(line1, line2, line3):
    """Every circle touching the three endless lines: [(centre, radius)] (four for a
    triangle, two when two lines are parallel, none when all three are, or meet in one
    point)."""
    rows = []
    for line in (line1, line2, line3):
        p, _u, n = _line(line)
        rows.append((n, dot(n, p)))
    found = []
    for s2 in (1.0, -1.0):
        for s3 in (1.0, -1.0):
            signs = (1.0, s2, s3)
            # n_i . C - s_i r = c_i
            m = [(rows[i][0][0], rows[i][0][1], -signs[i]) for i in range(3)]
            c = [rows[i][1] for i in range(3)]
            sol = _solve3(m, c)
            if sol is None:
                continue
            cx, cy, r = sol
            if abs(r) <= 1e-7:
                continue
            centre, radius = (cx, cy), abs(r)
            if not any(dist(centre, f[0]) < 1e-6 and abs(radius - f[1]) < 1e-6 for f in found):
                found.append((centre, radius))
    return found


def _solve3(m, c):
    """Cramer's rule for a 3x3 system; None when singular."""

    def det(a):
        return (
            a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1])
            - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
            + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0])
        )

    d = det(m)
    if abs(d) < 1e-12:
        return None
    out = []
    for col in range(3):
        a = [list(row) for row in m]
        for i in range(3):
            a[i][col] = c[i]
        out.append(det(a) / d)
    return tuple(out)


def nearest_circle(circles, pointer):
    """The (centre, radius) whose centre is nearest the pointer, or None."""
    best = None
    for centre, radius in circles:
        d = dist(centre, pointer)
        if best is None or d < best[0]:
            best = (d, (centre, radius))
    return best[1] if best else None


def tangent_points(centre, lines):
    """Where a circle centred at `centre` touches each endless line (the feet)."""
    return [foot(centre, a, b) for a, b in lines]


# -- arcs ---------------------------------------------------------------------------------
def arc_through(p1, p2, p3):
    """(centre, radius, a1, a2): the counterclockwise arc from a1 to a2 through the three
    points with p1, p3 its ends and p2 on it (FreeCAD's arcs run counterclockwise, so
    the ends may come out swapped), or None (in a line)."""
    circle = circle_3point(p1, p2, p3)
    if circle is None:
        return None
    centre, r = circle
    a1 = angle_of(sub(p1, centre))
    a2 = angle_of(sub(p2, centre))
    a3 = angle_of(sub(p3, centre))

    def ccw(start, end):
        return (end - start) % (2.0 * math.pi)

    if ccw(a1, a2) <= ccw(a1, a3):
        start, end = a1, a3  # counterclockwise p1 -> p2 -> p3
    else:
        start, end = a3, a1  # clockwise: as a counterclockwise arc it runs p3 -> p1
    while end <= start:
        end += 2.0 * math.pi
    return centre, r, start, end


def arc_points(centre, radius, a1, a2, n=48):
    step = (a2 - a1) / n
    return [polar(a1 + i * step, radius, centre) for i in range(n + 1)]


def tangent_arc_radius(start, tangent, pointer, radius):
    """(centre, radius, a1, a2, joint_pos): the arc of the given radius that leaves
    `start` along the unit `tangent` and turns towards the pointer's side, ending at the
    pointer's angle about its centre (Fusion's Tangent Arc with a typed radius). As
    FreeCAD's counterclockwise arcs: joint_pos 1 when it turns left (the start is the
    arc's start), 2 when it turns right. None on the tangent line itself."""
    side = cross(tangent, sub(pointer, start))
    if abs(side) < EPS or radius <= EPS:
        return None
    sign = 1.0 if side > 0 else -1.0
    centre = add(start, mul(left(tangent), sign * radius))
    a_start = angle_of(sub(start, centre))
    a_end = angle_of(sub(pointer, centre))
    if sign > 0:
        a1, a2, joint = a_start, a_end, 1
    else:
        a1, a2, joint = a_end, a_start, 2
    while a2 <= a1:
        a2 += 2.0 * math.pi
    return centre, radius, a1, a2, joint


# -- polygons --------------------------------------------------------------------------
def edge_polygon(p1, p2, sides, side_point):
    """(corners, centre, radius) of the regular polygon with the edge p1 -> p2 on the side
    of `side_point` (Fusion's Edge Polygon): corners[0] = p1, corners[1] = p2. None for
    an edge of no length."""
    sides = int(sides)
    if sides < 3:
        raise ValueError("a polygon needs at least 3 sides")
    edge = sub(p2, p1)
    n_edge = length(edge)
    if n_edge <= EPS:
        return None
    u = mul(edge, 1.0 / n_edge)
    side = 1.0 if cross(u, sub(side_point, p1)) >= 0 else -1.0
    apothem = n_edge / (2.0 * math.tan(math.pi / sides))
    centre = add(mid(p1, p2), mul(left(u), side * apothem))
    radius = dist(centre, p1)
    # p1 -> p2 turns about the centre by side * 2pi/n (counterclockwise when the centre
    # is to the left of the edge)
    step = side * 2.0 * math.pi / sides
    corners = [rotate(p1, centre, step * i) for i in range(sides)]
    return corners, centre, radius


# -- slots ------------------------------------------------------------------------------
CENTER_TO_CENTER, OVERALL, CENTER_POINT = "center", "overall", "center_point"


def slot_centres(kind, first, second, width):
    """(c1, c2, r): the two end-arc centres and their radius of a linear slot of the
    given kind from the two clicked points and the width. None when the clicks give no
    slot (an overall slot shorter than its width)."""
    r = width * 0.5
    if r <= EPS or dist(first, second) <= EPS:
        return None
    if kind == CENTER_TO_CENTER:
        return first, second, r
    if kind == CENTER_POINT:
        return sub(mul(first, 2.0), second), second, r
    if kind == OVERALL:
        u = unit(sub(second, first))
        if dist(first, second) <= 2.0 * r + EPS:
            return None
        return add(first, mul(u, r)), sub(second, mul(u, r)), r
    raise ValueError("unknown slot kind %r" % kind)


def slot_outline(c1, c2, r):
    """The slot's four curves as SciForge builds them (and FreeCAD's slot tool does):
    [("arc", centre, r, a1, a2) x 2, ("line", a, b) x 2]; arc 1 around c1 faces away from
    c2, line 1 joins arc 1's start to arc 2's end, line 2 arc 1's end to arc 2's start."""
    angle = angle_of(sub(c2, c1))
    arc1 = ("arc", c1, r, angle + math.pi / 2.0, angle + 1.5 * math.pi)
    arc2 = ("arc", c2, r, angle + 1.5 * math.pi, angle + 2.5 * math.pi)
    a1s, a1e = polar(arc1[3], r, c1), polar(arc1[4], r, c1)
    a2s, a2e = polar(arc2[3], r, c2), polar(arc2[4], r, c2)
    return [arc1, arc2, ("line", a1s, a2e), ("line", a1e, a2s)]


def slot_width_from_pointer(c1, c2, pointer):
    """Twice the pointer's distance to the slot's centre segment (the width a click
    there gives: FreeCAD's slot tool works it out the same way)."""
    ab = sub(c2, c1)
    n2 = dot(ab, ab)
    t = 0.0 if n2 < EPS else max(0.0, min(1.0, dot(sub(pointer, c1), ab) / n2))
    return 2.0 * dist(pointer, add(c1, mul(ab, t)))


def arc_slot(c1, c2, through, width):
    """The three-point arc slot: the centre arc runs from c1 through `through` to c2.
    Returns {"centre", "radius", "a1", "a2", "r", "reversed"} (a1 < a2, counterclockwise;
    "reversed" when c1 is at a2), or None (points in a line, or too wide for the arc)."""
    arc = arc_through(c1, through, c2)
    if arc is None:
        return None
    centre, radius, a1, a2 = arc
    r = width * 0.5
    if r <= EPS or r >= radius - EPS:
        return None
    reversed_ = dist(polar(a1, radius, centre), c1) > dist(polar(a2, radius, centre), c1)
    return {"centre": centre, "radius": radius, "a1": a1, "a2": a2, "r": r, "reversed": reversed_}


def arc_slot_width_from_pointer(slot, pointer):
    """Twice the pointer's distance to the centre arc (clamped below the arc's radius)."""
    d = abs(dist(pointer, slot["centre"]) - slot["radius"])
    return min(2.0 * d, 2.0 * slot["radius"] * 0.98)


# -- the conic --------------------------------------------------------------------------
RHO_MIN, RHO_MAX = 0.01, 0.99


def conic_weight(rho):
    """The apex weight of the rational quadratic Bezier for Fusion's rho."""
    if not 0.0 < rho < 1.0:
        raise ValueError("rho must be between 0 and 1")
    return rho / (1.0 - rho)


def conic_rho(weight):
    return weight / (1.0 + weight)


def conic_point(start, apex, end, rho, t):
    """The conic's point at parameter t (0..1)."""
    w = conic_weight(rho)
    b0, b1, b2 = (1.0 - t) ** 2, 2.0 * t * (1.0 - t) * w, t * t
    den = b0 + b1 + b2
    return (
        (b0 * start[0] + b1 * apex[0] + b2 * end[0]) / den,
        (b0 * start[1] + b1 * apex[1] + b2 * end[1]) / den,
    )


def conic_points(start, apex, end, rho, n=48):
    return [conic_point(start, apex, end, rho, i / float(n)) for i in range(n + 1)]


def conic_shoulder(start, apex, end, rho):
    """The conic's shoulder: the point at rho of the way from the chord's middle to the
    apex (where the curve crosses that line; the rho handle sits there)."""
    m = mid(start, end)
    return add(m, mul(sub(apex, m), rho))


def rho_from_pointer(start, apex, end, pointer):
    """The rho the pointer asks for: its position along the chord-middle -> apex line,
    kept strictly between 0 and 1."""
    m = mid(start, end)
    axis = sub(apex, m)
    n2 = dot(axis, axis)
    if n2 < EPS:
        return 0.5
    rho = dot(sub(pointer, m), axis) / n2
    return max(RHO_MIN, min(RHO_MAX, rho))
