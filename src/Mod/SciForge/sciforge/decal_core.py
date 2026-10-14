# SPDX-License-Identifier: LGPL-2.1-or-later
"""Decal maths without FreeCAD or Qt (unit tested in SciForgeTests/unit/test_decal_core.py).

A decal is a picture laid on a face. Its frame sits on the face: an origin, the face's outward
normal, an X direction along the face. Points of the face get picture coordinates (u, v) in
0..1 from where they are in that frame: straight onto the plane for a flat face, unrolled
around the axis for a cylinder (the picture wraps without stretching), straight onto the
frame's plane for other curved faces. The face's triangles are cut at the picture's edges so
only the part the picture covers is drawn.
"""

import math

MAX_TEXTURE = 1024  # the picture is drawn at most this many pixels wide (big photos stay quick)


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a):
    length = math.sqrt(_dot(a, a))
    if length < 1e-15:
        return (0.0, 0.0, 0.0)
    return (a[0] / length, a[1] / length, a[2] / length)


def frame_axes(normal, hint=(1.0, 0.0, 0.0)):
    """(x, y, z) of a frame whose z is `normal`: x is `hint` laid onto the plane (the design's
    X, else its Y when the plane faces X), y = z x x. A picture on a wall reads upright."""
    z = _norm(normal)
    x = _sub(hint, _mul(z, _dot(hint, z)))
    if math.sqrt(_dot(x, x)) < 1e-6:
        alt = (0.0, 1.0, 0.0) if abs(z[1]) < 0.9 else (0.0, 0.0, 1.0)
        x = _sub(alt, _mul(z, _dot(alt, z)))
    x = _norm(x)
    y = _cross(z, x)
    return x, y, z


def upright_hint(normal):
    """The X direction a picture gets on a face: for a wall (normal level), along the wall so
    that the picture's up is the design's up (Z); else the design's X."""
    z = _norm(normal)
    if abs(z[2]) < 0.7:  # a wall: x horizontal along it, y up
        return _norm(_cross((0.0, 0.0, 1.0), z))
    return (1.0, 0.0, 0.0)


def placed(u, v, options):
    """Picture coordinates from the frame coordinates (u, v in mm, before the decal's own
    move / turn / scale / flips): the decal's centre is (XDistance, YDistance), turned by
    ZAngle, its size BaseWidth x BaseHeight times ScaleX / ScaleY."""
    du = u - options.get("dx", 0.0)
    dv = v - options.get("dy", 0.0)
    angle = math.radians(options.get("angle", 0.0))
    c, s = math.cos(angle), math.sin(angle)
    lx = c * du + s * dv
    ly = -s * du + c * dv
    width = max(1e-9, options["width"] * options.get("scale_x", 1.0))
    height = max(1e-9, options["height"] * options.get("scale_y", 1.0))
    pu = 0.5 + lx / width
    pv = 0.5 + ly / height
    if options.get("flip_h"):
        pu = 1.0 - pu
    if options.get("flip_v"):
        pv = 1.0 - pv
    return pu, pv


def flat_coords(point, origin, x, y):
    """(u, v) mm of a point in a plane frame."""
    d = _sub(point, origin)
    return _dot(d, x), _dot(d, y)


def cylinder_coords(point, origin, axis_point, axis, radius):
    """(u, v) mm of a point of a cylinder unrolled about its axis: u = the arc from the
    frame's origin (positive turning right-handed about the axis), v = along the axis."""
    axis = _norm(axis)
    rel_o = _sub(origin, axis_point)
    rel_p = _sub(point, axis_point)
    radial_o = _norm(_sub(rel_o, _mul(axis, _dot(rel_o, axis))))
    radial_p = _norm(_sub(rel_p, _mul(axis, _dot(rel_p, axis))))
    tangent = _cross(axis, radial_o)
    angle = math.atan2(_dot(radial_p, tangent), _dot(radial_p, radial_o))
    return radius * angle, _dot(rel_p, axis) - _dot(rel_o, axis)


def clip(polygon, lo=0.0, hi=1.0):
    """Sutherland-Hodgman: the part of a convex polygon inside lo <= u, v <= hi. A vertex is
    a tuple whose first two entries are (u, v); every entry is interpolated."""

    def cut(poly, inside, cross):
        out = []
        for i, current in enumerate(poly):
            previous = poly[i - 1]
            if inside(current):
                if not inside(previous):
                    out.append(cross(previous, current))
                out.append(current)
            elif inside(previous):
                out.append(cross(previous, current))
        return out

    def crossing(index, limit):
        def at(a, b):
            t = (limit - a[index]) / (b[index] - a[index])
            return tuple(p + (q - p) * t for p, q in zip(a, b))

        return at

    poly = list(polygon)
    for index, limit, keep in ((0, lo, 1), (0, hi, -1), (1, lo, 1), (1, hi, -1)):
        if not poly:
            break
        poly = cut(
            poly,
            (lambda k, i, lim: (lambda p: (p[i] - lim) * k >= -1e-12))(keep, index, limit),
            crossing(index, limit),
        )
    return poly


def fan(polygon):
    """Triangles [(a, b, c)] of a convex polygon (indices into it)."""
    return [(0, i, i + 1) for i in range(1, len(polygon) - 1)]


def cover(points, triangles, uv_of, normal_of=None):
    """The decal's mesh: (vertices [(x, y, z)], uv [(u, v)], normals [(x, y, z)], triangles
    [(a, b, c)]) of the face triangles cut to the picture. uv_of(point) -> (u, v);
    normal_of(point) -> outward normal (None: the triangle's own)."""
    out_points, out_uv, out_normals, out_tris = [], [], [], []
    for tri in triangles:
        corners = [points[i] for i in tri]
        uvs = [uv_of(p) for p in corners]
        if all(u < 0 for u, v in uvs) or all(u > 1 for u, v in uvs):
            continue
        if all(v < 0 for u, v in uvs) or all(v > 1 for u, v in uvs):
            continue
        if normal_of is not None:
            normals = [normal_of(p) for p in corners]
        else:
            n = _norm(_cross(_sub(corners[1], corners[0]), _sub(corners[2], corners[0])))
            normals = [n, n, n]
        poly = [uv + p + n for uv, p, n in zip(uvs, corners, normals)]
        cut = clip(poly)
        if len(cut) < 3:
            continue
        base = len(out_points)
        for vertex in cut:
            out_uv.append((vertex[0], vertex[1]))
            out_points.append((vertex[2], vertex[3], vertex[4]))
            out_normals.append(_norm((vertex[5], vertex[6], vertex[7])))
        for a, b, c in fan(cut):
            out_tris.append((base + a, base + b, base + c))
    return out_points, out_uv, out_normals, out_tris


def lifted(points, normals, distance):
    """The points moved `distance` along their normals (the picture just above the face)."""
    return [_add(p, _mul(n, distance)) for p, n in zip(points, normals)]


def default_size(pixels, face_size):
    """(width, height) mm at scale 1 for a picture of (w, h) pixels on a face whose smaller
    side is `face_size` mm: the longer side of the picture is 80 % of it (it fits on the
    face), the picture keeps its proportions; 50 mm when the face size is unknown."""
    w, h = pixels
    if w <= 0 or h <= 0:
        raise ValueError("The image has no size.")
    longest = 0.8 * face_size if face_size and face_size > 0 else 50.0
    if w >= h:
        return longest, longest * h / float(w)
    return longest * w / float(h), longest


def texture_size(pixels, limit=MAX_TEXTURE):
    """The size the picture is drawn at: at most `limit` pixels on its longer side."""
    w, h = pixels
    longest = max(w, h)
    if longest <= limit:
        return w, h
    k = limit / float(longest)
    return max(1, int(round(w * k))), max(1, int(round(h * k)))


def area(points, triangles):
    """Total area of triangles (mm^2)."""
    total = 0.0
    for a, b, c in triangles:
        cr = _cross(_sub(points[b], points[a]), _sub(points[c], points[a]))
        total += 0.5 * math.sqrt(_dot(cr, cr))
    return total
