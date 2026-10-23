# SPDX-License-Identifier: LGPL-2.1-or-later
"""The arithmetic of Fillet's and Chamfer's live picture (fillet_live.py), without FreeCAD:
unit tested in SciForgeTests/unit/test_fillet_live_core.py.

While the radius or distance arrow is dragged, the dialog shows the round (or the bevel)
moving with the mouse and builds the exact solid only when the mouse rests, as Draft does
(draft_live.py). The picture is worked out at sample points along each picked edge, in the
plane square to the edge there:

  Fillet (a rolling ball): the ball of radius r touches both faces. With the faces' outward
  normals n0, n1 at the edge point P (c = n0 . n1), its centre is
      C = P + s r (n0 + n1) / (1 + c)        s = -1 on an outside (convex) edge: the ball
                                             is in the material; +1 on an inside edge
  (at distance r from both faces' tangent planes), and the round is the arc of the ball's
  circle from the point where it touches face 0, C - s r n0, to the one where it touches
  face 1, C - s r n1. Every point of it is P + r * V with V depending only on the normals:
  V = s (n0 + n1) / (1 + c) + slerp(-s n0, -s n1, t). So a new radius moves each point by
  one multiply-add (ball_dirs()). This is exact where the faces' cross-sections are straight
  lines in that plane: two flat faces, a flat face and a cylinder or cone at a circle edge, a
  flat top on an extruded (spline) wall; elsewhere it is off by about r^2 times the
  curvature, and the exact solid replaces it as soon as the mouse rests.

  Chamfer: the flat band from the point a along face 0 to the point b along face 1, each
  measured square to the edge across its face (into0, into1: the directions from the edge
  across each face). Equal distance a = b = d; Two Distances: d1 on the reference face, d2
  on the other; Distance and Angle: b from the law of sines, fillet_core.angle_distance2.

  Where two picked edges meet at a corner the bands would run through each other: each is
  cut at the plane that halves the corner (mitre()), the points past it slid back onto it
  along the edge (clamp()). Two equal rounds meet exactly on that plane.
"""

import math

EPS = 1e-12


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def scale(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def norm(a):
    return math.sqrt(dot(a, a))


def unit(a):
    n = norm(a)
    if n < EPS:
        raise ValueError("zero vector")
    return scale(a, 1.0 / n)


def slerp(a, b, t):
    """The unit vector a fraction t of the way from unit a to unit b (the short way)."""
    c = max(-1.0, min(1.0, dot(a, b)))
    angle = math.acos(c)
    if angle < 1e-9:
        return a
    s = math.sin(angle)
    wa = math.sin((1.0 - t) * angle) / s
    wb = math.sin(t * angle) / s
    return add(scale(a, wa), scale(b, wb))


def side(convex):
    """s of the formulas above: -1 on an outside edge (the ball in the material), +1 inside."""
    return -1.0 if convex else 1.0


def turn(n0, n1):
    """The angle (radians) the normals turn by across the edge (90 degrees on a box edge); the
    corner's angle gamma is pi minus it."""
    return math.acos(max(-1.0, min(1.0, dot(n0, n1))))


def ball_dirs(n0, n1, convex, steps):
    """[V_0 .. V_steps]: the round's points at radius r are P + r V_j, from face 0 (j = 0) to
    face 1 (j = steps). Raises ValueError for faces that are tangent or fold back (c ~ -1)."""
    c = dot(n0, n1)
    if 1.0 + c < 1e-9:
        raise ValueError("the faces fold back on each other")
    if turn(n0, n1) < 1e-6:
        raise ValueError("the faces are tangent")
    s = side(convex)
    w = scale(add(n0, n1), s / (1.0 + c))
    u0, u1 = scale(n0, -s), scale(n1, -s)
    return [add(w, slerp(u0, u1, j / float(steps))) for j in range(steps + 1)]


def ball_centre(p, n0, n1, convex, r):
    """The rolling ball's centre at edge point p (tests)."""
    c = dot(n0, n1)
    return add(p, scale(add(n0, n1), side(convex) * r / (1.0 + c)))


def chord_radius(chord, n0, n1):
    """The radius whose round has chord `chord` here (fillet_core.chord_radius)."""
    half = math.sin(turn(n0, n1) / 2.0)
    if half < 1e-6:
        raise ValueError("the faces are tangent")
    return float(chord) / (2.0 * half)


def angle_second(distance, angle, n0, n1):
    """The second distance of a Distance and Angle chamfer here (fillet_core.angle_distance2:
    the corner's angle gamma = pi - turn); None when the bevel never reaches the other face."""
    a = math.radians(float(angle))
    gamma = math.pi - turn(n0, n1)
    far = math.sin(gamma + a)
    if not 0.0 < a < math.pi or a + gamma >= math.pi - 1e-9 or far <= 1e-9:
        return None
    return float(distance) * math.sin(a) / far


def interp(positions, radii, x):
    """The radius at position x (0..1), straight between the points (fillet_core.law)."""
    x = min(1.0, max(0.0, float(x)))
    for (p0, r0), (p1, r1) in zip(zip(positions, radii), zip(positions[1:], radii[1:])):
        if x <= p1 + 1e-12:
            if p1 - p0 < 1e-12:
                return r1
            return r0 + (r1 - r0) * (x - p0) / (p1 - p0)
    return radii[-1]


def mitre(vertex, away, other_away):
    """(point, normal) of the plane that halves the corner at `vertex` between an edge that
    leaves it along unit `away` and another that leaves it along unit `other_away`: the edge's
    band keeps the points with (p - point) . normal >= 0. None for edges that double back on
    each other (nothing sensible to cut)."""
    m = sub(away, other_away)
    if norm(m) < 1e-9:
        return None
    return vertex, unit(m)


def clamp(p, tangent, plane):
    """p slid along `tangent` back onto the plane (point, normal) when it lies past it."""
    point, normal = plane
    d = dot(sub(p, point), normal)
    if d >= 0.0:
        return p
    along = dot(tangent, normal)
    if abs(along) < 1e-9:
        return p
    return sub(p, scale(tangent, d / along))
