# SPDX-License-Identifier: LGPL-2.1-or-later
"""Thread geometry without FreeCAD: the groove a modeled thread cuts, the length it covers,
and the volume it removes. Pure Python (unit tested); sciforge/thread.py turns these numbers
into OpenCASCADE shapes.

The thread profile is ISO 68-1's basic profile (the same 60 degree profile serves the
Unified threads, ASME B1.1). With H = sqrt(3)/2 * P (P = pitch) and the major radius R:

  external thread (a bolt, a shaft): the groove between two ridges has a flat root P/4 wide
      at R - 5H/8 and opens at 60 degrees to P/8-wide crests at R. The groove is carried a
      little past R (to R + H/16, 15P/16 wide) so it cleanly breaks out of the surface.
  internal thread (a nut, a tapped hole): the groove cut into the hole wall has a flat root
      P/8 wide at R and opens towards the hole to 7P/8 at R - 3H/4, inside the drilled hole
      (a tap drill is R - P/2 or more, so R - 3H/4 = R - 0.65 P is in the empty hole).

A groove is a trapezoid in a plane through the thread's axis: (radius, axial position)
corners. Swept along a helix it makes a screw-shaped cutter; inside the thread's length every
cross section across the axis has the same area, so the material it removes is

    removed = length * (2 * pi / P) * integral over r of r * w(r) dr

where w(r) is the groove's width along the axis at radius r (only where there was material).
"""
import math

TAN30 = math.tan(math.radians(30.0))


def fundamental_height(pitch):
    """H: the height of the sharp 60 degree triangle of the thread form."""
    return math.sqrt(3.0) / 2.0 * pitch


def groove(major_radius, pitch, internal):
    """The groove trapezoid as [(radius, z), ...] (closed, counter-clockwise in r-z), centred
    on z = 0. See the module text for the shape."""
    h = fundamental_height(pitch)
    r = float(major_radius)
    p = float(pitch)
    if internal:
        inner, outer = r - 0.75 * h, r
        inner_half, outer_half = 7.0 * p / 16.0, p / 16.0
    else:
        inner, outer = r - 5.0 * h / 8.0, r + h / 16.0
        inner_half, outer_half = p / 8.0, 15.0 * p / 32.0
    return [
        (inner, -inner_half),
        (outer, -outer_half),
        (outer, outer_half),
        (inner, inner_half),
    ]


def groove_width(major_radius, pitch, internal, radius):
    """w(r): the groove's width along the axis at `radius` (0 outside the groove)."""
    corners = groove(major_radius, pitch, internal)
    inner, outer = corners[0][0], corners[1][0]
    if radius < inner - 1e-12 or radius > outer + 1e-12:
        return 0.0
    w_inner, w_outer = 2.0 * corners[0][1] * -1.0, 2.0 * corners[1][1] * -1.0
    t = (radius - inner) / (outer - inner)
    return w_inner + (w_outer - w_inner) * t


def _integral_rw(major_radius, pitch, internal, a, b):
    """Integral of r * w(r) dr from a to b (w linear between the groove's radii)."""
    corners = groove(major_radius, pitch, internal)
    inner, outer = corners[0][0], corners[1][0]
    a, b = max(a, inner), min(b, outer)
    if b <= a:
        return 0.0
    w_inner, w_outer = -2.0 * corners[0][1], -2.0 * corners[1][1]
    slope = (w_outer - w_inner) / (outer - inner)
    # w(r) = w_inner + slope * (r - inner) = c0 + slope * r
    c0 = w_inner - slope * inner

    def f(r):
        return c0 * r * r / 2.0 + slope * r**3 / 3.0

    return f(b) - f(a)


def removed_area(major_radius, pitch, internal, face_radius):
    """Area of one cross section (across the axis) of the material a modeled thread removes
    from a cylinder of radius `face_radius`: a shaft (external) or a hole (internal). A shaft
    wider than the thread is first turned down to the major diameter, a hole narrower than
    the thread's minor diameter is first bored up to it (that is what Fusion's modeled thread
    does: the thread has its standard size whatever the cylinder was)."""
    h = fundamental_height(pitch)
    r = float(major_radius)
    face = float(face_radius)
    two_pi_over_p = 2.0 * math.pi / pitch
    if internal:
        minor = r - 5.0 * h / 8.0
        bore = math.pi * (minor**2 - face**2) if face < minor else 0.0
        start = max(face, minor) if bore else face
        return bore + two_pi_over_p * _integral_rw(r, pitch, True, start, r)
    turn = math.pi * (face**2 - r**2) if face > r else 0.0
    end = min(face, r) if turn else face
    return turn + two_pi_over_p * _integral_rw(r, pitch, False, 0.0, end)


def removed_volume(major_radius, pitch, internal, face_radius, length):
    return removed_area(major_radius, pitch, internal, face_radius) * float(length)


def span(face_start, face_end, full_length=True, length=0.0, offset=0.0, from_end=False):
    """(z0, z1) the thread covers along a cylinder that runs from face_start to face_end
    (positions along its axis). Full length: all of it. Otherwise `length` long, starting
    `offset` in from the start (or from the end when from_end: the end nearer the click),
    and never past the face."""
    lo, hi = min(face_start, face_end), max(face_start, face_end)
    if full_length:
        return lo, hi
    length = max(0.0, float(length))
    offset = max(0.0, float(offset))
    if from_end:
        z1 = hi - offset
        z0 = z1 - length
    else:
        z0 = lo + offset
        z1 = z0 + length
    return max(lo, z0), min(hi, z1)


def helix_points(radius, pitch, z0, z1, per_turn=24, left_hand=False, phase=0.0):
    """Points (x, y, z) of a helix around the z axis from z0 to z1 (for drawing a cosmetic
    thread). Right-handed: it turns counter-clockwise going up."""
    if z1 <= z0 or pitch <= 0:
        return []
    turns = (z1 - z0) / pitch
    count = max(2, int(math.ceil(turns * per_turn)) + 1)
    sign = -1.0 if left_hand else 1.0
    points = []
    for i in range(count):
        t = i / float(count - 1)
        z = z0 + (z1 - z0) * t
        angle = phase + sign * 2.0 * math.pi * (z - z0) / pitch
        points.append((radius * math.cos(angle), radius * math.sin(angle), z))
    return points
