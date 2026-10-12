# SPDX-License-Identifier: LGPL-2.1-or-later
"""The rules of picking sketch areas (profiles) inside an open sketch; sketch_areas.py
does the mouse and the drawing.

Fusion, in an open sketch with no drawing tool running:
- a click inside a closed area (not on a curve, a point or a dimension) selects that
  area (profile); it shows in a stronger blue;
- Ctrl+click or Shift+click adds another area; clicking a selected area again (with or
  without Ctrl/Shift) drops it;
- a plain click on empty space, or on a curve, ends the area selection;
- E (Extrude) or Q (Press Pull) then works on exactly the selected areas.

An area is remembered by a point inside it (sketch millimetres), not by its number: the
areas are worked out again after every change of the sketch and their order can change.

No FreeCAD, no Qt here: plain (x, y) tuples, so it is unit tested.
"""


def in_triangle(x, y, a, b, c, eps=1e-12):
    """True if (x, y) lies in the triangle a, b, c (on its edge counts as inside)."""
    d1 = (x - b[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (y - b[1])
    d2 = (x - c[0]) * (b[1] - c[1]) - (b[0] - c[0]) * (y - c[1])
    d3 = (x - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (y - a[1])
    negative = d1 < -eps or d2 < -eps or d3 < -eps
    positive = d1 > eps or d2 > eps or d3 > eps
    return not (negative and positive)


class Region:
    """One closed area of the sketch, as the triangles it is shaded with.

    points: [(x, y), ...]; triangles: [(i, j, k), ...] indices into points."""

    __slots__ = ("points", "triangles", "box", "area")

    def __init__(self, points, triangles):
        self.points = [(float(p[0]), float(p[1])) for p in points]
        self.triangles = [tuple(t) for t in triangles]
        if self.points:
            xs = [p[0] for p in self.points]
            ys = [p[1] for p in self.points]
            self.box = (min(xs), min(ys), max(xs), max(ys))
        else:
            self.box = (0.0, 0.0, -1.0, -1.0)  # empty: contains nothing
        area = 0.0
        for i, j, k in self.triangles:
            a, b, c = self.points[i], self.points[j], self.points[k]
            area += abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])) / 2.0
        self.area = area

    def contains(self, x, y):
        x0, y0, x1, y1 = self.box
        if x < x0 or x > x1 or y < y0 or y > y1:
            return False
        pts = self.points
        for i, j, k in self.triangles:
            if in_triangle(x, y, pts[i], pts[j], pts[k]):
                return True
        return False


def region_at(regions, x, y):
    """Index of the area that contains (x, y), or None. The areas of a sketch do not
    overlap; on a shared edge the smaller one wins (a hole's disc inside a plate)."""
    best = None
    for index, region in enumerate(regions):
        if region.contains(x, y) and (best is None or region.area < regions[best].area):
            best = index
    return best


def picked_regions(picks, regions):
    """Indices of the areas the picked points lie in, in the order they were picked
    (each area once); points that are in no area any more are left out."""
    found = []
    for x, y in picks:
        index = region_at(regions, x, y)
        if index is not None and index not in found:
            found.append(index)
    return found


def keep_valid(picks, regions):
    """The picked points that still lie in an area (one per area): after the sketch
    changed, a point whose area is gone (or merged with another picked one) is dropped."""
    kept, seen = [], set()
    for point in picks:
        index = region_at(regions, point[0], point[1])
        if index is None or index in seen:
            continue
        seen.add(index)
        kept.append(point)
    return kept


def click(picks, regions, point, additive, anchor=None):
    """The picked points after a click at `point` (an area or empty space; the caller
    has already ruled out curves, points and dimensions under the pointer).

    additive: Ctrl or Shift held. anchor: the point remembered for a newly picked area
    (a point well inside it); the click point itself when not given."""
    hit = region_at(regions, point[0], point[1])
    if hit is None:
        return list(picks) if additive else []
    picks = keep_valid(picks, regions)
    same = [p for p in picks if region_at(regions, p[0], p[1]) == hit]
    if same:  # clicked again: dropped (Ctrl/Shift or not)
        return [p for p in picks if p not in same]
    new = tuple(anchor) if anchor is not None else (point[0], point[1])
    return picks + [new] if additive else [new]
