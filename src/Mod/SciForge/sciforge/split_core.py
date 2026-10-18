# SPDX-License-Identifier: LGPL-2.1-or-later
"""How big Split Body's red splitting-tool preview is drawn (Luca: "the splitting tool
should show an extension of the face it is using to split the body. in red. like fusion").
Pure logic, no FreeCAD: the shapes are made in split.py (tool_shape(..., fit=True)), the
picture in split_ui.py (cut_preview.CutPreview).

What Fusion does (parity/bodies.md, Split Body): with Extend Splitting Tool on, the tool is
extended so it crosses the whole body; the red see-through preview shows the extended
tool, a little bigger than the body. How much bigger is a **Guess**: SciForge adds
MARGIN of the body's size on every side.

The cut itself still uses an endless plane (split.tool_shape without fit): the preview is
the same plane or cylinder, only cut down to the body's size, so it shows where the cut
goes and is not a huge sheet across the screen.

Points are (x, y, z) tuples, or anything with x, y, z (FreeCAD vectors).
"""

MARGIN = 0.1  # of the body's diagonal, on every side (Guess)
MIN_MARGIN = 1.0  # mm: a tiny body still gets a visible rim


def corners(box):
    """The 8 corners of a box given as (xmin, ymin, zmin, xmax, ymax, zmax)."""
    x0, y0, z0, x1, y1, z1 = box
    return [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]


def diagonal(box):
    x0, y0, z0, x1, y1, z1 = box
    return ((x1 - x0) ** 2 + (y1 - y0) ** 2 + (z1 - z0) ** 2) ** 0.5


def margin(box):
    """How far the preview reaches past the body, on every side."""
    return max(MARGIN * diagonal(box), MIN_MARGIN)


def span(values, rim):
    """(low, high) of `values`, widened by `rim` at both ends."""
    values = list(values)
    if not values:
        return (-rim, rim)
    return (min(values) - rim, max(values) + rim)


def cover_uv(uvs, rim):
    """(u0, u1, v0, v1): the rectangle in a plane that covers the body (its corners projected
    into the plane as (u, v)) and `rim` more on every side."""
    uvs = list(uvs)
    u0, u1 = span([uv[0] for uv in uvs], rim)
    v0, v1 = span([uv[1] for uv in uvs], rim)
    return (u0, u1, v0, v1)


def _xyz(p):
    if hasattr(p, "x"):
        return (p.x, p.y, p.z)
    return tuple(p)


def along(points, origin, direction):
    """Where each point lies along a line (origin, unit direction): its signed distance."""
    o = _xyz(origin)
    d = _xyz(direction)
    out = []
    for p in points:
        p = _xyz(p)
        out.append((p[0] - o[0]) * d[0] + (p[1] - o[1]) * d[1] + (p[2] - o[2]) * d[2])
    return out


def cover_axis(box, origin, direction):
    """(low, high) along an axis (a cylinder's, or a sketch's normal) covering the body and
    its margin."""
    return span(along(corners(box), origin, direction), margin(box))
