# SPDX-License-Identifier: LGPL-2.1-or-later
"""Where the value box next to a drag arrow goes on the screen (pure geometry, no Qt).

Fusion shows a distance box beside the arrow you drag. The box must never cover the
arrow's heads: they are what you grab. An arrow can point any way on the screen (in the
Front view the arrow of a side face points sideways), so the box goes, in this order:

  1. beside the arrow's middle, on its right (above it when the arrow lies level),
     clear of the heads;
  2. beside it on the other side (when the edge of the view is in the way);
  3. past the arrow's tip, then past its tail;

and it always stays inside the view. Pixels: x to the right, y down (as in Qt).
taskui.ArrowValueBox uses spot(); the unit tests check it without FreeCAD.
"""

import math

# The arrow FreeCAD draws (Coin's SoTranslate1Dragger), in arrow sizes from its middle:
# a thin bar to 1.0 on both sides, then a cone head from 1.0 to 1.5, 0.25 wide (radius).
REACH = 1.5
HEAD = 0.25
GAP = 6.0  # pixels between the arrow (its heads included) and the box
EDGE = 2.0  # pixels kept free at the view's border


def _segment_point(a, b, p):
    """Distance from point p to the segment a-b."""
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    t = 0.0 if length2 < 1e-12 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _rect_point(rect, p):
    """Distance from point p to the rectangle (left, top, width, height); 0 inside."""
    left, top, width, height = rect
    dx = max(left - p[0], 0.0, p[0] - (left + width))
    dy = max(top - p[1], 0.0, p[1] - (top + height))
    return math.hypot(dx, dy)


def _cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _segments_cross(p1, p2, q1, q2):
    d1, d2 = _cross(q1, q2, p1), _cross(q1, q2, p2)
    d3, d4 = _cross(p1, p2, q1), _cross(p1, p2, q2)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def clearance(tail, tip, rect):
    """Distance between the segment tail-tip and the rectangle (left, top, width, height):
    0 when they touch or overlap."""
    if _rect_point(rect, tail) == 0.0 or _rect_point(rect, tip) == 0.0:
        return 0.0
    left, top, width, height = rect
    corners = [(left, top), (left + width, top), (left + width, top + height), (left, top + height)]
    for i in range(4):
        if _segments_cross(tail, tip, corners[i], corners[(i + 1) % 4]):
            return 0.0
    return min(
        [_rect_point(rect, tail), _rect_point(rect, tip)]
        + [_segment_point(tail, tip, c) for c in corners]
    )


def spot(anchor, tail, tip, radius, box, view, gap=GAP, other_side=False):
    """Top-left corner (x, y) of a box of size `box` (w, h) beside an arrow on the screen.

    anchor     the arrow's middle (where the extrusion ends), in view pixels
    tail, tip  the arrow's two ends (the tips of its heads)
    radius     how far the heads reach sideways from the arrow's line, in pixels
    view       the size (w, h) of the 3D view the box sits in
    other_side the box starts on the arrow's other side (left, or below a level arrow):
               for a second arrow that can sit on the first one (both at 0), so the two
               boxes do not cover each other
    The box keeps `gap` pixels plus `radius` away from the arrow's line, never covers a
    head, and stays inside the view (only when nothing fits does it go where it covers the
    arrow least)."""
    ax, ay = float(anchor[0]), float(anchor[1])
    tail = (float(tail[0]), float(tail[1]))
    tip = (float(tip[0]), float(tip[1]))
    width, height = float(box[0]), float(box[1])
    view_w, view_h = float(view[0]), float(view[1])
    dx, dy = tip[0] - tail[0], tip[1] - tail[1]
    length = math.hypot(dx, dy)
    if length < 1.0:
        dx, dy = 0.0, -1.0  # the arrow points at you (or away): as if it stood upright
    else:
        dx, dy = dx / length, dy / length
    # The two sides of the arrow: its right first, or above it when it lies level.
    sides = sorted([(-dy, dx), (dy, -dx)], key=lambda n: -(n[0] - 0.5 * n[1]))
    if other_side:
        sides.reverse()
    centres = []
    for nx, ny in sides:
        reach = radius + gap + (abs(nx) * width + abs(ny) * height) / 2.0
        centres.append((ax + nx * reach, ay + ny * reach))
    along = radius + gap + (abs(dx) * width + abs(dy) * height) / 2.0
    centres.append((tip[0] + dx * along, tip[1] + dy * along))
    centres.append((tail[0] - dx * along, tail[1] - dy * along))
    best = None
    for cx, cy in centres:
        left = max(EDGE, min(cx - width / 2.0, view_w - width - EDGE))
        top = max(EDGE, min(cy - height / 2.0, view_h - height - EDGE))
        clear = clearance(tail, tip, (left, top, width, height))
        if clear >= radius + 1.0:
            return int(round(left)), int(round(top))
        if best is None or clear > best[0]:
            best = (clear, left, top)
    return int(round(best[1])), int(round(best[2]))
