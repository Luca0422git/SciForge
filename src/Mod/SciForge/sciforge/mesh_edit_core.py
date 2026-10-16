# SPDX-License-Identifier: LGPL-2.1-or-later
"""Direct Edit of a mesh body and the face group tools (MESH tab), without FreeCAD or Qt
(unit tested). Spec and sources: docs/sciforge/parity/mesh.md, "Direct Edit".

Fusion's Direct Edit (MESH > MODIFY > Direct Edit) opens an environment where single faces
(triangles) of a mesh body are picked with the Mesh Selection Palette (Paint, Window or Free
Form selection, a brush size, Faces or Face Groups, Select Back Faces; Grow, Shrink, Invert,
Expand To Face Group, Expand To Connected) and changed: deleted, erased and filled, made a
face group, turned over, moved or smoothed. Finish Direct Edit keeps it all as one step in
the timeline (Fusion's mesh base feature).

SciForge keeps that step's edits as a list (one JSON text per edit) and plays them again on
the body as the step before leaves it, so the step stays one timeline step that can be
opened again; the picked faces of each edit are kept by their centres (as Erase and Fill
does), so they are found again after an earlier change where they still exist.

A mesh here is the plain lists of mesh_core: points [(x, y, z)], facets [(a, b, c)]
counter-clockwise seen from outside, and one face group number per facet."""

import json
import math

from . import mesh_core as core
from .mesh_core import MeshError

# ----------------------------------------------------------------------------- choices
# The Mesh Selection Palette: Fusion's selection types; Direct Edit opens it on Paint.
SELECTION_TYPES = ["Paint", "Window", "Free Form"]
DEFAULT_SELECTION = "Paint"
# What a pick takes: single faces or whole face groups (the palette's filter).
SELECT_FILTERS = ["Faces", "Face Groups"]
DEFAULT_FILTER = "Faces"
# Brush Size: the brush scales with the body (Fusion's slider); SciForge's slider runs from
# 0.5 % to 50 % of the body's size, 5 % at first (the Erase and Fill brush).
BRUSH_FRACTION = 0.05
BRUSH_RANGE = (0.005, 0.5)
# Move: along the picked faces' mean normal or a design axis (Fusion moves faces with its
# Move/Copy triad; SciForge's arrow drags along the chosen direction).
MOVE_DIRECTIONS = ["Normal", "X", "Y", "Z"]
DEFAULT_SMOOTHNESS = core.DEFAULT_SMOOTHNESS  # Fusion's Smooth: 0 .. 1, 0.02

OPS = ("delete", "erase_fill", "group", "reverse", "move", "smooth")
OP_NAMES = {
    "delete": "Delete",
    "erase_fill": "Erase and Fill",
    "group": "Create Face Group",
    "reverse": "Reverse Normal",
    "move": "Move",
    "smooth": "Smooth",
}
LAPLACE = (0.5,)  # one move half-way to the neighbours' middle per round (the rim is fixed)


# ----------------------------------------------------------------------------- the working mesh
class EditState:
    """The mesh a Direct Edit works on: points, facets and one face group per facet."""

    def __init__(self, points, facets, groups=None):
        self.points = [tuple(p) for p in points]
        self.facets = [tuple(f) for f in facets]
        groups = list(groups) if groups else []
        if len(groups) != len(self.facets):
            groups = [0] * len(self.facets)
        self.groups = groups
        self._quantum = None

    def copy(self):
        twin = EditState(self.points, self.facets, self.groups)
        twin._quantum = self._quantum
        return twin

    def size(self):
        return core.diagonal(self.points) if self.points else 0.0

    def quantum(self):
        """How close a kept face centre must be to count as the same face (worked out once,
        from the body the edits start on)."""
        if self._quantum is None:
            self._quantum = max(1e-6 * max(self.size(), 1.0), 1e-9)
        return self._quantum

    def result_groups(self):
        """The face groups to keep on the body: none when every face is in one group."""
        return list(self.groups) if core.group_count(self.groups) > 1 else []

    def centres(self, indices):
        return [core.centroid(self.points, self.facets[i]) for i in indices]

    def find(self, picks):
        """(facet indices, picks lost) of kept face centres."""
        if not picks or not self.facets:
            return [], len(picks or [])
        return core.find_facets(self.points, self.facets, [tuple(p) for p in picks], self.quantum())

    def compact(self):
        """Points no facet uses are left out (the facets keep their order)."""
        self.points, self.facets = core.compact(self.points, self.facets)


# ----------------------------------------------------------------------------- edits as text
def _rounded(values, digits=9):
    return [round(float(v), digits) for v in values]


def make_edit(op, picks, **params):
    """One edit as a dict: the operation, the picked faces' centres and its values."""
    if op not in OPS:
        raise MeshError("Unknown edit: %s" % op)
    edit = {"op": op, "picks": [_rounded(p) for p in picks]}
    if op == "move":
        edit["vector"] = _rounded(params.get("vector", (0.0, 0.0, 0.0)))
    elif op == "smooth":
        edit["smoothness"] = float(params.get("smoothness", DEFAULT_SMOOTHNESS))
    elif op == "erase_fill":
        edit["fill"] = params.get("fill", "Uniform")
        if edit["fill"] not in core.ERASE_FILL_TYPES:
            edit["fill"] = "Uniform"
        edit["density"] = float(params.get("density", core.ERASE_DENSITY))
    return edit


def encode(edit):
    return json.dumps(edit, sort_keys=True, separators=(",", ":"))


def decode(text):
    """The edit kept as text, or None when it cannot be read (a damaged file)."""
    try:
        edit = json.loads(text)
    except (TypeError, ValueError):
        return None
    if not isinstance(edit, dict) or edit.get("op") not in OPS:
        return None
    picks = edit.get("picks") or []
    try:
        edit["picks"] = [tuple(float(c) for c in p) for p in picks if len(p) == 3]
    except (TypeError, ValueError):
        return None
    return edit


def describe(edit):
    """'Move: 12 faces, 0, 0, 2 mm' for the dialog's list of edits."""
    count = len(edit.get("picks") or [])
    text = "%s: %d face%s" % (
        OP_NAMES.get(edit["op"], edit["op"]),
        count,
        "" if count == 1 else "s",
    )
    if edit["op"] == "move":
        x, y, z = edit.get("vector", (0.0, 0.0, 0.0))
        text += ", %s mm" % ", ".join(_short(v) for v in (x, y, z))
    elif edit["op"] == "smooth":
        text += ", smoothness %s" % _short(edit.get("smoothness", DEFAULT_SMOOTHNESS))
    elif edit["op"] == "erase_fill":
        text += ", %s" % edit.get("fill", "Uniform")
    return text


def _short(value):
    text = "%.3f" % float(value)
    text = text.rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


# ----------------------------------------------------------------------------- playing edits
def apply(state, edit):
    """Play one edit on `state` (changed in place). Returns how many of its picked faces were
    not found (the body changed before the step). Raises MeshError when the edit cannot be
    done on what was found (the dialog says why and leaves the edit out)."""
    which, lost = state.find(edit.get("picks") or [])
    if not which:
        return lost
    op = edit["op"]
    if op == "delete":
        delete_facets(state, which)
    elif op == "reverse":
        reverse_facets(state, which)
    elif op == "group":
        new_group(state, which)
    elif op == "move":
        move_facets(state, which, tuple(edit.get("vector") or (0.0, 0.0, 0.0)))
    elif op == "smooth":
        smooth_facets(state, which, float(edit.get("smoothness", DEFAULT_SMOOTHNESS)))
    elif op == "erase_fill":
        erase_and_fill(
            state,
            which,
            edit.get("fill", "Uniform"),
            float(edit.get("density", core.ERASE_DENSITY)),
        )
    return lost


def replay(state, edits):
    """Play the edits in order; an edit that cannot be done any more is skipped. Returns
    (picked faces lost, [indices of the edits skipped])."""
    lost = 0
    skipped = []
    for index, edit in enumerate(edits):
        try:
            lost += apply(state, edit)
        except MeshError:
            skipped.append(index)
    return lost, skipped


# ----------------------------------------------------------------------------- the operations
def delete_facets(state, which):
    """Delete: the faces go, the hole they leave stays open."""
    gone = set(which)
    if len(gone) >= len(state.facets):
        raise MeshError("That is every face of the body: delete the body instead.")
    state.facets = [f for i, f in enumerate(state.facets) if i not in gone]
    state.groups = [g for i, g in enumerate(state.groups) if i not in gone]
    state.compact()


def reverse_facets(state, which):
    """Reverse Normal of single faces: each picked face turned over."""
    state.facets = core.flip(state.facets, which)


def new_group(state, which):
    """Create Face Group: the picked faces (joined or not) become one new face group.
    Returns its number."""
    number = (max(state.groups) + 1) if state.groups else 0
    chosen = set(which)
    state.groups = [number if i in chosen else g for i, g in enumerate(state.groups)]
    return number


def points_of(facets, which):
    found = set()
    for i in which:
        found.update(facets[i])
    return found


def move_facets(state, which, vector):
    """Move: the corners of the picked faces move by `vector`; the faces around them
    stretch, so the body stays joined."""
    if core.length(vector) < 1e-12:
        return
    moved = points_of(state.facets, which)
    points = state.points
    for i in moved:
        points[i] = core.add(points[i], vector)


def boundary_points(facets, which):
    """Corners of the picked faces that a face outside the pick (or an open edge) also
    touches: they stay put when the region is smoothed, so it stays joined to the rest."""
    chosen = set(which)
    inside = points_of(facets, which)
    border = set()
    for i, facet in enumerate(facets):
        if i not in chosen:
            border.update(p for p in facet if p in inside)
    for u, v in core.boundary_edges([facets[i] for i in which]):
        # an edge of the pick on one picked face only: on the rim of the pick or of a hole
        border.add(u)
        border.add(v)
    return border


def smooth_facets(state, which, smoothness):
    """Smooth a region: the picked faces' inner corners move towards the middle of their
    neighbours (rounds of Laplace smoothing, as many as Smooth's Smoothness gives); the rim of
    the region stays where it is, so the body neither shrinks nor comes apart there (the
    whole-body Smooth uses Taubin's non-shrinking smoothing instead, which keeps bumps the
    size of a picked region). Returns how many corners moved."""
    rounds = core.smooth_iterations(smoothness)
    inner = sorted(points_of(state.facets, which) - boundary_points(state.facets, which))
    if not inner:
        raise MeshError(
            "The picked area has no inner corners to smooth: pick a bigger area (Grow)."
        )
    if rounds <= 0:
        return 0
    neighbours = {i: set() for i in inner}
    chosen = set(which)
    for index in chosen:
        a, b, c = state.facets[index]
        for p, q, r in ((a, b, c), (b, c, a), (c, a, b)):
            if p in neighbours:
                neighbours[p].add(q)
                neighbours[p].add(r)
    points = list(state.points)
    for _round in range(rounds):
        for factor in LAPLACE:
            new = {}
            for i in inner:
                ring = neighbours[i]
                if not ring:
                    continue
                sx = sy = sz = 0.0
                for j in ring:
                    pj = points[j]
                    sx += pj[0]
                    sy += pj[1]
                    sz += pj[2]
                n = float(len(ring))
                p = points[i]
                new[i] = (
                    p[0] + factor * (sx / n - p[0]),
                    p[1] + factor * (sy / n - p[1]),
                    p[2] + factor * (sz / n - p[2]),
                )
            for i, p in new.items():
                points[i] = p
    state.points = points
    return len(inner)


def _drop_degenerate_tagged(facets, tags):
    seen = set()
    out, out_tags = [], []
    for facet, tag in zip(facets, tags):
        a, b, c = facet
        if a == b or b == c or a == c:
            continue
        key = tuple(sorted(facet))
        if key in seen:
            continue
        seen.add(key)
        out.append(facet)
        out_tags.append(tag)
    return out, out_tags


def erase_and_fill(state, which, fill="Uniform", density=core.ERASE_DENSITY):
    """Erase and Fill: the picked faces go and the gap is closed (Minimal: no new points;
    Uniform: even triangles, finer with a higher Density). Holes the body had stay. The patch
    joins the face group most of the erased faces were in."""
    gone = set(which)
    if len(gone) >= len(state.facets):
        raise MeshError("That is every face of the body: there is nothing left to fill from.")
    facets = state.facets
    before = {tuple(sorted(loop)) for loop in core.boundary_loops(facets)}
    kept = [f for i, f in enumerate(facets) if i not in gone]
    kept_groups = [g for i, g in enumerate(state.groups) if i not in gone]
    counts = {}
    for i in gone:
        counts[state.groups[i]] = counts.get(state.groups[i], 0) + 1
    patch_group = max(counts, key=lambda g: (counts[g], -g)) if counts else 0
    loops = [loop for loop in core.boundary_loops(kept) if tuple(sorted(loop)) not in before]
    patch = []
    for loop in loops:
        try:
            patch += core.fill_loop(state.points, loop)
        except MeshError:
            continue
    if not patch:
        raise MeshError("The erased area could not be filled: pick a smaller area.")
    start = len(kept)
    joined = kept + patch
    tags = kept_groups + [patch_group] * len(patch)
    points = state.points
    if fill == "Uniform":
        areas = [core.facet_area(points, f) for f in kept] or [1.0]
        mean = sum(areas) / len(areas)
        edge = math.sqrt(core.erase_fill_area(mean, density) / 0.4330127018922193)
        points, joined, _done, tags = core.split_long_edges(
            points, joined, edge, only=range(start, len(joined)), tags=tags
        )
    joined, tags = _drop_degenerate_tagged(joined, tags)
    state.points, state.facets, state.groups = list(points), joined, tags
    state.compact()


# ----------------------------------------------------------------------------- selection
def point_facets(facets, count=None):
    """[[facets using point i]]."""
    if count is None:
        count = 1 + max((max(f) for f in facets), default=-1)
    found = [[] for _ in range(count)]
    for index, facet in enumerate(facets):
        for p in facet:
            found[p].append(index)
    return found


def grow(facets, selected, by_point=None):
    """Grow: the faces touching the picked ones (by an edge or a corner) join them."""
    if by_point is None:
        by_point = point_facets(facets)
    out = set(selected)
    for p in points_of(facets, selected):
        out.update(by_point[p])
    return sorted(out)


def shrink(facets, selected, by_point=None):
    """Shrink: the picked faces on the rim of the pick (touching a face not picked) drop
    out."""
    if by_point is None:
        by_point = point_facets(facets)
    chosen = set(selected)
    rim = set()
    for p in points_of(facets, selected):
        if any(f not in chosen for f in by_point[p]):
            rim.update(f for f in by_point[p] if f in chosen)
    return sorted(chosen - rim)


def invert(count, selected):
    """Invert: every face that is not picked, and none that is."""
    chosen = set(selected)
    return [i for i in range(count) if i not in chosen]


def expand_to_groups(groups, selected):
    """Expand To Face Group: every face of the face groups the picked faces are in."""
    if not groups:
        return sorted(set(selected))
    wanted = {groups[i] for i in selected if 0 <= i < len(groups)}
    return [i for i, g in enumerate(groups) if g in wanted]


def expand_connected(facets, selected, neighbours=None):
    """Expand To Connected: every face joined to the picked ones through shared edges (the
    whole shell they lie on)."""
    if neighbours is None:
        neighbours = core.facet_neighbours(facets)
    found = set(selected)
    todo = list(found)
    while todo:
        f = todo.pop()
        for g in neighbours[f]:
            if g not in found:
                found.add(g)
                todo.append(g)
    return sorted(found)


def facing(points, facets, indices, look, eye=None):
    """The faces of `indices` turned towards the viewer (Select Back Faces off). `look`:
    the view direction (into the screen); `eye`: the camera's position for a perspective
    view (then each face is judged from the eye)."""
    out = []
    for i in indices:
        n = core.facet_normal(points, facets[i])
        if eye is not None:
            d = core.sub(core.centroid(points, facets[i]), eye)
        else:
            d = look
        if core.dot(n, d) < 0.0:
            out.append(i)
    return out


def in_polygon(screen, facets, polygon, crossing=False, indices=None):
    """The faces inside a screen polygon (a Window box or a Free Form lasso). `screen`: the
    screen position of each point (None: behind the camera). Window takes faces wholly
    inside, crossing (a box drawn right to left) faces with a corner inside."""
    if len(polygon) < 3:
        return []
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    lo_x, hi_x, lo_y, hi_y = min(xs), max(xs), min(ys), max(ys)
    inside_cache = {}

    def inside(p):
        hit = inside_cache.get(p)
        if hit is None:
            s = screen[p]
            hit = (
                s is not None
                and lo_x <= s[0] <= hi_x
                and lo_y <= s[1] <= hi_y
                and core.point_in_polygon_2d(s, polygon)
            )
            inside_cache[p] = hit
        return hit

    out = []
    for i in range(len(facets)) if indices is None else indices:
        corners = [inside(p) for p in facets[i]]
        if any(corners) if crossing else all(corners):
            out.append(i)
    return out


def mean_normal(points, facets, which):
    """The area-weighted normal of the picked faces (unit), or None."""
    total = (0.0, 0.0, 0.0)
    for i in which:
        total = core.add(total, core.facet_normal(points, facets[i]))
    if core.length(total) < 1e-12:
        return None
    return core.unit(total)


def centre_of(points, facets, which):
    """The area-weighted centre of the picked faces, or None."""
    area_sum = 0.0
    acc = (0.0, 0.0, 0.0)
    for i in which:
        area = core.facet_area(points, facets[i])
        acc = core.add(acc, core.scale(core.centroid(points, facets[i]), area))
        area_sum += area
    if area_sum <= 0:
        return None
    return core.scale(acc, 1.0 / area_sum)


def move_vector(direction, distance, normal=None):
    """The move of a Distance along Normal (the picked faces' mean normal), X, Y or Z."""
    distance = float(distance)
    if direction == "X":
        return (distance, 0.0, 0.0)
    if direction == "Y":
        return (0.0, distance, 0.0)
    if direction == "Z":
        return (0.0, 0.0, distance)
    if normal is None:
        raise MeshError("The picked faces have no common direction: move them along X, Y or Z.")
    return core.scale(core.unit(normal), distance)


# ----------------------------------------------------------------------------- face groups
def group_adjacency(facets, groups):
    """{group: {groups sharing an edge with it}}."""
    near = {g: set() for g in set(groups)}
    for owners in core.edge_facets(facets).values():
        gs = {groups[f] for f in owners}
        if len(gs) > 1:
            for g in gs:
                near[g].update(gs - {g})
    return near


def combine_groups(facets, groups, chosen):
    """Combine Face Groups: the chosen groups (two or more, each sharing an edge with
    another one of them, all joined) become one, numbered as the first of them."""
    chosen = list(dict.fromkeys(chosen))
    if len(chosen) < 2:
        raise MeshError("Pick two or more face groups that touch (click them on the body).")
    present = set(groups)
    missing = [g for g in chosen if g not in present]
    if missing:
        raise MeshError("Some picked face groups are no longer on the body: pick them again.")
    near = group_adjacency(facets, groups)
    reached = {chosen[0]}
    todo = [chosen[0]]
    wanted = set(chosen)
    while todo:
        g = todo.pop()
        for h in near.get(g, ()):
            if h in wanted and h not in reached:
                reached.add(h)
                todo.append(h)
    if reached != wanted:
        raise MeshError(
            "These face groups do not touch: Combine Face Groups joins face groups that "
            "share an edge. Pick groups next to each other."
        )
    into = chosen[0]
    return [into if g in wanted else g for g in groups]


def renumber(groups):
    """Face group numbers 0, 1, 2 ... in the order they first appear (keeps the look stable
    after groups were joined)."""
    number = {}
    out = []
    for g in groups:
        if g not in number:
            number[g] = len(number)
        out.append(number[g])
    return out
