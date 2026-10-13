# SPDX-License-Identifier: LGPL-2.1-or-later
"""The MESH tab without FreeCAD or Qt (unit tested): Fusion's choices and defaults, how a
dialog value becomes an algorithm's setting, and the mesh algorithms FreeCAD lacks: open
edges and holes, the region a plane cut leaves open (with islands and holes in it), face
groups by angle, splitting long edges without opening cracks, welding open edges (Repair's
stitch) and the voxel rebuild (Repair > Rebuild, Remesh Uniform).

A mesh here is two plain lists: points [(x, y, z)] and facets [(a, b, c)], each facet
counter-clockwise seen from outside (the STL / FreeCAD convention). Spec and sources:
docs/sciforge/parity/mesh.md."""

import math

# ----------------------------------------------------------------------------- choices
# Repair (PREPARE > Repair): least to most invasive, Fusion's order. Fusion's API starts at
# Stitch and Remove.
REPAIR_TYPES = ["Close Holes", "Stitch and Remove", "Wrap", "Rebuild"]
DEFAULT_REPAIR = "Stitch and Remove"
REBUILD_TYPES = ["Fast", "Preserve Sharp Edges", "Accurate", "Blocky"]
DEFAULT_REBUILD = "Fast"
REBUILD_DENSITY = (8, 256, 128)  # (lowest, highest, Fusion's default): cells along the longest side

# Remesh: Density 0..1 (0.25), Shape Preservation 0..1 (0.5, Adaptive only).
REMESH_TYPES = ["Adaptive", "Uniform"]
REMESH_DENSITY = 0.25
SHAPE_PRESERVATION = 0.5

# Reduce: the target, and how the faces are laid out (Proportion / Face Count only).
REDUCE_TARGETS = ["Tolerance", "Proportion", "Face Count"]
REDUCE_TYPES = ["Adaptive", "Uniform"]
DEFAULT_TOLERANCE = 0.05  # mm (Fusion's API starts at 0, which reduces nothing: a guess)
DEFAULT_PROPORTION = 50.0  # percent (a guess)

# Smooth: Smoothness 0..1 (Fusion's API default is 0.02).
DEFAULT_SMOOTHNESS = 0.02

# Plane Cut
CUT_TYPES = ["Trim", "Split Body", "Split Faces"]
FILL_TYPES = ["No Fill", "Uniform", "Minimal"]
DEFAULT_FILL = "Uniform"  # (a guess: Fusion's page does not say)

# Separate, Combine, Erase and Fill, Generate Face Groups, Shell
SEPARATE_TYPES = ["Mesh Shells", "All Face Groups", "Select Face Groups"]
COMBINE_OPERATIONS = ["Join", "Cut", "Intersect", "Merge"]
ERASE_FILL_TYPES = ["Uniform", "Minimal"]
ERASE_DENSITY = 0.5
FACE_GROUP_METHODS = ["Fast", "Accurate"]
ANGLE_THRESHOLD = math.degrees(0.436)  # Fusion's API default 0.436 rad = 25 degrees
MIN_GROUP_SIZE = 0.02  # fraction of the body's area
BOUNDARY_TOLERANCE = 0.001  # fraction of the body's largest size
DEFAULT_SHELL = 2.0  # mm (a guess)

# Tessellate: Fusion's refinement presets (the same as its Save As Mesh / 3D Print ones).
TESSELLATE_REFINEMENTS = ["Low", "Medium", "High", "Custom"]

BIG_MESH = 250000  # facets: above this the dialogs say a step can take a while


class MeshError(ValueError):
    """Something the mesh or the values do not allow; the text says why and what to try."""


# ----------------------------------------------------------------------------- vectors
def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def scale(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def length(a):
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


def unit(a):
    n = length(a)
    if n < 1e-300:
        raise MeshError("A direction of zero length.")
    return (a[0] / n, a[1] / n, a[2] / n)


def facet_normal(points, facet):
    """Not normalised: its length is twice the facet's area."""
    a, b, c = (points[i] for i in facet)
    return cross(sub(b, a), sub(c, a))


def facet_area(points, facet):
    return 0.5 * length(facet_normal(points, facet))


def centroid(points, facet):
    a, b, c = (points[i] for i in facet)
    return ((a[0] + b[0] + c[0]) / 3.0, (a[1] + b[1] + c[1]) / 3.0, (a[2] + b[2] + c[2]) / 3.0)


def bounds(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    zs = [p[2] for p in points]
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def diagonal(points):
    lo, hi = bounds(points)
    return length(sub(hi, lo))


def rotate(vector, axis, degrees):
    """Rodrigues' rotation of `vector` about the unit `axis`."""
    t = math.radians(degrees)
    c, s = math.cos(t), math.sin(t)
    k = unit(axis)
    kv = cross(k, vector)
    kd = dot(k, vector) * (1.0 - c)
    return (
        vector[0] * c + kv[0] * s + k[0] * kd,
        vector[1] * c + kv[1] * s + k[1] * kd,
        vector[2] * c + kv[2] * s + k[2] * kd,
    )


# ----------------------------------------------------------------------------- dialog values
def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def reduce_target_count(current, target, proportion=DEFAULT_PROPORTION, face_count=None):
    """The number of faces Reduce aims for (None for Tolerance, which stops at a deviation).
    Fusion's Proportion is the percentage of faces kept."""
    if target == "Tolerance":
        return None
    if target == "Proportion":
        wanted = int(round(current * clamp(float(proportion), 0.0, 100.0) / 100.0))
    elif target == "Face Count":
        wanted = int(face_count if face_count is not None else current // 2)
    else:
        raise MeshError("Unknown Reduce target: %s" % target)
    if wanted < 4:
        raise MeshError("A closed mesh needs at least 4 faces: ask for more than %d." % wanted)
    if wanted >= current:
        raise MeshError(
            "The body has %d faces already: ask for fewer to reduce it (Remesh makes more)."
            % current
        )
    return wanted


def quadric_tolerance(deviation):
    """FreeCAD's decimation stops on a quadric error (about a squared distance): Fusion's
    Tolerance is a distance in mm."""
    deviation = float(deviation)
    if deviation <= 0:
        raise MeshError("The tolerance must be more than 0 mm.")
    return deviation * deviation


def remesh_edge_length(diag, density):
    """Target edge length of Remesh. Density 0 is very coarse (a tenth of the body's
    diagonal), 1 very fine (a thousandth); Fusion's default 0.25 gives about 3 %."""
    density = clamp(float(density), 0.0, 1.0)
    return diag * 10.0 ** (-1.0 - 2.0 * density)


def remesh_face_count(area, edge):
    """About how many faces of side `edge` cover `area` (equilateral triangles)."""
    if edge <= 0:
        return 0
    return int(round(area / (0.4330127018922193 * edge * edge)))


def smooth_iterations(smoothness):
    """Smoothness 0..1 to rounds of Taubin smoothing (which keeps the volume, unlike plain
    Laplace): 0.02 (Fusion's default) gives a light 2, 1.0 a heavy 60."""
    smoothness = clamp(float(smoothness), 0.0, 1.0)
    if smoothness <= 0:
        return 0
    return max(1, int(round(1 + 59 * smoothness)))


def rebuild_cell(size, density):
    """Edge of a voxel cell: the body's longest side split into `density` cells (8..256)."""
    lo, hi, _default = REBUILD_DENSITY
    density = int(clamp(int(round(density)), lo, hi))
    if size <= 0:
        raise MeshError("The body has no size.")
    return size / float(density)


def erase_fill_area(mean_area, density):
    """Largest triangle of an Erase and Fill (Uniform): Density 0..1 from 4 times the body's
    mean triangle (coarse) down to a sixteenth of it (fine)."""
    density = clamp(float(density), 0.0, 1.0)
    return mean_area * 4.0 * 64.0 ** (-density)


# ----------------------------------------------------------------------------- topology
def edge_facets(facets):
    """{(a, b) with a < b: [indices of the facets on it]}."""
    found = {}
    get = found.get
    for index, (a, b, c) in enumerate(facets):
        for u, v in ((a, b), (b, c), (c, a)):
            key = (u, v) if u < v else (v, u)
            entry = get(key)
            if entry is None:
                found[key] = [index]
            else:
                entry.append(index)
    return found


def boundary_edges(facets):
    """The open edges (on one facet only) as (u, v) in that facet's winding."""
    count = {}
    directed = {}
    for a, b, c in facets:
        for u, v in ((a, b), (b, c), (c, a)):
            key = (u, v) if u < v else (v, u)
            count[key] = count.get(key, 0) + 1
            directed[key] = (u, v)
    return [directed[k] for k, n in count.items() if n == 1]


def boundary_loops(facets):
    """The holes: closed loops of open edges (point indices, in the facets' winding). Where
    two loops touch at one point (a bow tie) each loop still closes on itself; a chain that
    does not close is left out."""
    outgoing = {}
    for u, v in boundary_edges(facets):
        outgoing.setdefault(u, []).append(v)
    loops = []
    while outgoing:
        start = next(iter(outgoing))
        path = [start]
        where = {start: 0}
        current = start
        while True:
            nexts = outgoing.get(current)
            if not nexts:
                break  # a chain that does not close
            nxt = nexts.pop()
            if not nexts:
                del outgoing[current]
            if nxt in where:
                i = where[nxt]
                loop = path[i:]
                if len(loop) >= 3:
                    loops.append(loop)
                for p in loop[1:]:
                    del where[p]
                del path[i + 1 :]
                current = nxt
                if i == 0 and not outgoing.get(start):
                    break
                continue
            where[nxt] = len(path)
            path.append(nxt)
            current = nxt
    return loops


def non_manifold_edges(facets):
    """Edges with more than two facets on them."""
    return [k for k, owners in edge_facets(facets).items() if len(owners) > 2]


def orientation_conflicts(facets):
    """Edges two facets run the same way (one of them is flipped)."""
    seen = {}
    bad = 0
    for a, b, c in facets:
        for u, v in ((a, b), (b, c), (c, a)):
            if (u, v) in seen:
                bad += 1
            seen[(u, v)] = True
    return bad


class _UnionFind:
    def __init__(self, n):
        self.parent = list(range(n))

    def find(self, i):
        parent = self.parent
        root = i
        while parent[root] != root:
            root = parent[root]
        while parent[i] != root:
            parent[i], i = root, parent[i]
        return root

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            if ra < rb:
                self.parent[rb] = ra
            else:
                self.parent[ra] = rb


def components(facets):
    """Facet index lists of the pieces (facets joined by an edge), biggest first."""
    uf = _UnionFind(len(facets))
    for owners in edge_facets(facets).values():
        first = owners[0]
        for other in owners[1:]:
            uf.union(first, other)
    groups = {}
    for i in range(len(facets)):
        groups.setdefault(uf.find(i), []).append(i)
    return sorted(groups.values(), key=lambda g: (-len(g), g[0]))


def compact(points, facets):
    """(points, facets) with the points no facet uses left out."""
    used = {}
    new_points = []
    new_facets = []
    for facet in facets:
        mapped = []
        for i in facet:
            j = used.get(i)
            if j is None:
                j = used[i] = len(new_points)
                new_points.append(points[i])
            mapped.append(j)
        new_facets.append(tuple(mapped))
    return new_points, new_facets


def drop_degenerate(facets):
    """Facets that use a point twice, and second copies of a facet, left out."""
    seen = set()
    out = []
    for a, b, c in facets:
        if a == b or b == c or a == c:
            continue
        key = tuple(sorted((a, b, c)))
        if key in seen:
            continue
        seen.add(key)
        out.append((a, b, c))
    return out


def flip(facets, which=None):
    """Facets turned over (all, or the indices in `which`)."""
    if which is None:
        return [(a, c, b) for a, b, c in facets]
    which = set(which)
    return [(a, c, b) if i in which else (a, b, c) for i, (a, b, c) in enumerate(facets)]


def signed_volume(points, facets):
    """Volume enclosed (negative when the facets face inwards)."""
    total = 0.0
    for a, b, c in facets:
        pa, pb, pc = points[a], points[b], points[c]
        total += dot(pa, cross(pb, pc))
    return total / 6.0


# ----------------------------------------------------------------------------- analysis
def analysis_lines(info):
    """What Repair's analysis says, one line per problem found (empty: nothing found).
    `info`: {"holes", "open_edges", "flipped", "non_manifold", "self_intersections",
    "shells", "degenerate", "duplicated", "inside_out"}."""
    lines = []

    def say(key, one, many):
        n = int(info.get(key) or 0)
        if n:
            lines.append((one if n == 1 else many) % n)

    say("holes", "%d hole", "%d holes")
    say("flipped", "%d flipped face", "%d flipped faces")
    say("non_manifold", "%d edge with more than two faces", "%d edges with more than two faces")
    say(
        "self_intersections",
        "%d place where the mesh crosses itself",
        "%d places where the mesh crosses itself",
    )
    say("degenerate", "%d face of no area", "%d faces of no area")
    say("duplicated", "%d doubled face", "%d doubled faces")
    shells = int(info.get("shells") or 0)
    if shells > 1:
        lines.append("%d separate shells" % shells)
    if info.get("inside_out"):
        lines.append("inside out (the faces point inward)")
    return lines


def repair_advice(info, repair_type):
    """The plain sentence a Repair result ends with: closed, or what to try next."""
    if info.get("closed"):
        return "The mesh is closed (watertight): it can be printed or converted to a solid."
    steps = REPAIR_TYPES.index(repair_type) if repair_type in REPAIR_TYPES else 0
    holes = int(info.get("holes") or 0)
    left = "%d hole%s left" % (holes, "" if holes == 1 else "s") if holes else "still open"
    if steps < REPAIR_TYPES.index("Wrap"):
        return "Not closed yet (%s): try Wrap or Rebuild." % left
    if steps < REPAIR_TYPES.index("Rebuild"):
        return "Not closed yet (%s): try Rebuild." % left
    return (
        "This mesh cannot be repaired into a closed body (%s): it may be a surface with no "
        "inside. Try a higher Density, or Plane Cut away the broken part." % left
    )


# ----------------------------------------------------------------------------- planes, 2D
def plane_basis(normal):
    """Two unit axes in the plane (u, v) with u x v = normal: always the same for a normal."""
    n = unit(normal)
    ax = (abs(n[0]), abs(n[1]), abs(n[2]))
    if ax[0] <= ax[1] and ax[0] <= ax[2]:
        helper = (1.0, 0.0, 0.0)
    elif ax[1] <= ax[2]:
        helper = (0.0, 1.0, 0.0)
    else:
        helper = (0.0, 0.0, 1.0)
    u = unit(cross(helper, n))
    v = cross(n, u)
    return u, v


def to_2d(point, origin, u, v):
    d = sub(point, origin)
    return (dot(d, u), dot(d, v))


def signed_area_2d(poly):
    total = 0.0
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        total += x0 * y1 - x1 * y0
    return 0.5 * total


def point_in_polygon_2d(point, poly):
    x, y = point
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y):
            cross_x = xi + (y - yi) * (xj - xi) / (yj - yi)
            if x < cross_x:
                inside = not inside
        j = i
    return inside


def _inner_point(poly):
    """A point just inside a polygon (beside its first edge, on its inner side)."""
    area = signed_area_2d(poly)
    (x0, y0), (x1, y1) = poly[0], poly[1]
    mx, my = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    dx, dy = x1 - x0, y1 - y0
    n = math.hypot(dx, dy) or 1.0
    # left normal points inside a counter-clockwise polygon
    nx, ny = -dy / n, dx / n
    if area < 0:
        nx, ny = -nx, -ny
    eps = n * 1e-3
    return (mx + nx * eps, my + ny * eps)


def nest_loops_2d(polys):
    """Regions of loops lying in one plane: [(outer index, [hole indices])]. A loop inside an
    odd number of others is a hole of the nearest one around it; one inside an even number
    (an island in a hole) starts a region of its own."""
    count = len(polys)
    probes = [_inner_point(p) if len(p) >= 3 else p[0] for p in polys]
    areas = [abs(signed_area_2d(p)) for p in polys]
    containers = []
    for i in range(count):
        around = [
            j
            for j in range(count)
            if j != i and areas[j] > areas[i] and point_in_polygon_2d(probes[i], polys[j])
        ]
        containers.append(around)
    depth = [len(c) for c in containers]
    regions = {}
    order = []
    for i in range(count):
        if depth[i] % 2 == 0:
            regions[i] = []
            order.append(i)
    for i in range(count):
        if depth[i] % 2 == 1:
            parents = [j for j in containers[i] if depth[j] == depth[i] - 1]
            if parents:
                parent = min(parents, key=lambda j: areas[j])
                regions.setdefault(parent, []).append(i)
    return [(i, regions[i]) for i in order]


def match_points_2d(targets, queries, tolerance):
    """{query index: target index} for each query point within `tolerance` of a target
    point (the nearest one): a mesher's output points found again among the cut's corners,
    whatever its rounding."""
    cell = max(float(tolerance), 1e-300)
    grid = {}
    for index, (x, y) in enumerate(targets):
        grid.setdefault((int(math.floor(x / cell)), int(math.floor(y / cell))), []).append(index)
    found = {}
    t2 = cell * cell
    for qi, (x, y) in enumerate(queries):
        gx, gy = int(math.floor(x / cell)), int(math.floor(y / cell))
        best, best_d = None, None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for ti in grid.get((gx + dx, gy + dy), ()):
                    tx, ty = targets[ti]
                    d = (tx - x) * (tx - x) + (ty - y) * (ty - y)
                    if d <= t2 and (best_d is None or d < best_d):
                        best, best_d = ti, d
        if best is not None:
            found[qi] = best
    return found


def segment_hits(points2d, segments, tolerance):
    """For each point lying on one of the segments (within `tolerance`, not at its ends):
    {segment index: [(t along it, point index)]} sorted by t. Used to split the facets of
    an open edge where a fill put extra points on it."""
    found = {}
    if not segments:
        return found
    cell = max(tolerance * 50.0, 1e-9)
    lengths = []
    for (ax, ay), (bx, by) in segments:
        lengths.append(math.hypot(bx - ax, by - ay))
    cell = max(cell, (sum(lengths) / len(lengths)) if lengths else cell)
    grid = {}
    for index, ((ax, ay), (bx, by)) in enumerate(segments):
        x0, x1 = sorted((ax, bx))
        y0, y1 = sorted((ay, by))
        for gx in range(
            int(math.floor((x0 - tolerance) / cell)), int(math.floor((x1 + tolerance) / cell)) + 1
        ):
            for gy in range(
                int(math.floor((y0 - tolerance) / cell)),
                int(math.floor((y1 + tolerance) / cell)) + 1,
            ):
                grid.setdefault((gx, gy), []).append(index)
    for pindex, (px, py) in enumerate(points2d):
        key = (int(math.floor(px / cell)), int(math.floor(py / cell)))
        for index in grid.get(key, ()):
            (ax, ay), (bx, by) = segments[index]
            dx, dy = bx - ax, by - ay
            l2 = dx * dx + dy * dy
            if l2 <= 0:
                continue
            t = ((px - ax) * dx + (py - ay) * dy) / l2
            if t <= 1e-9 or t >= 1.0 - 1e-9:
                continue
            qx, qy = ax + t * dx, ay + t * dy
            if math.hypot(px - qx, py - qy) <= tolerance:
                found.setdefault(index, []).append((t, pindex))
                break
    for entry in found.values():
        entry.sort()
    return found


def fan_split(facet, edge, extra):
    """Facets replacing `facet` once the points `extra` (in order from edge[0] to edge[1])
    are put on its edge: a fan from the corner across from that edge."""
    a, b, c = facet
    u, v = edge
    # rotate the facet so that its edge u -> v comes first
    for _ in range(3):
        if (a, b) == (u, v):
            break
        a, b, c = b, c, a
    else:
        if (a, b) != (u, v):
            raise MeshError("The edge is not on that face.")
    chain = [a] + list(extra) + [b]
    return [(chain[i], chain[i + 1], c) for i in range(len(chain) - 1)]


# ----------------------------------------------------------------------------- offset
def offset_points(points, facets, distance):
    """Every point moved so that each face around it ends `distance` further out (negative:
    in), as a solid's offset does: on a flat face along its normal, at a box corner along
    the corner's diagonal by the right amount (moving along the averaged normal would make
    the walls of a hollowed box thinner than asked)."""
    around = [[] for _ in points]
    for facet in facets:
        n = facet_normal(points, facet)
        size = length(n)
        if size <= 1e-300:
            continue
        unit_n = (n[0] / size, n[1] / size, n[2] / size)
        for i in facet:
            around[i].append((unit_n, size))
    moved = []
    limit = 4.0 * abs(distance)
    for p, normals in zip(points, around):
        if not normals:
            moved.append(p)
            continue
        total = sum(w for _n, w in normals)
        avg = (
            sum(n[0] * w for n, w in normals),
            sum(n[1] * w for n, w in normals),
            sum(n[2] * w for n, w in normals),
        )
        try:
            avg = unit(avg)
        except MeshError:
            moved.append(p)
            continue
        reg = 1e-6 * total
        m = [[reg, 0.0, 0.0], [0.0, reg, 0.0], [0.0, 0.0, reg]]
        b = [reg * distance * avg[0], reg * distance * avg[1], reg * distance * avg[2]]
        # each direction once: many faces of one flat area must not outvote a corner's few
        seen = []
        for n, w in normals:
            if any(dot(n, s) > 0.9999 for s in seen):
                continue
            seen.append(n)
            for r in range(3):
                for c in range(3):
                    m[r][c] += total * n[r] * n[c]
                b[r] += total * n[r] * distance
        d = _solve3(m, b) or scale(avg, distance)
        size = length(d)
        if size > limit > 0:
            d = scale(d, limit / size)
        moved.append(add(p, d))
    return moved


# ----------------------------------------------------------------------------- filling a hole
def newell_normal(loop_points):
    """The best-fit normal of a closed 3D polygon (Newell's method): its length is twice the
    polygon's area, its direction follows the polygon's winding."""
    nx = ny = nz = 0.0
    count = len(loop_points)
    for i in range(count):
        x0, y0, z0 = loop_points[i]
        x1, y1, z1 = loop_points[(i + 1) % count]
        nx += (y0 - y1) * (z0 + z1)
        ny += (z0 - z1) * (x0 + x1)
        nz += (x0 - x1) * (y0 + y1)
    return (nx, ny, nz)


def triangulate_polygon_2d(poly):
    """Ear clipping of a simple polygon (no holes): index triples into `poly`, wound like the
    polygon. Points that make no turn are cut off too, so a polygon with straight runs works."""
    count = len(poly)
    if count < 3:
        return []
    order = list(range(count))
    if signed_area_2d(poly) < 0:
        order.reverse()  # work counter-clockwise; the triangles are turned back at the end
        flipped = True
    else:
        flipped = False

    def is_convex(a, b, c):
        (ax, ay), (bx, by), (cx, cy) = poly[a], poly[b], poly[c]
        return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax) > 1e-15

    def inside(p, a, b, c):
        px, py = poly[p]
        (ax, ay), (bx, by), (cx, cy) = poly[a], poly[b], poly[c]
        d1 = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
        d2 = (cx - bx) * (py - by) - (cy - by) * (px - bx)
        d3 = (ax - cx) * (py - cy) - (ay - cy) * (px - cx)
        return d1 >= 0 and d2 >= 0 and d3 >= 0

    triangles = []
    guard = 0
    while len(order) > 3 and guard < 4 * count * count + 10:
        guard += 1
        clipped = False
        n = len(order)
        for k in range(n):
            a, b, c = order[(k - 1) % n], order[k], order[(k + 1) % n]
            if not is_convex(a, b, c):
                continue
            if any(inside(p, a, b, c) for p in order if p not in (a, b, c)):
                continue
            triangles.append((a, b, c))
            del order[k]
            clipped = True
            break
        if not clipped:
            # no ear (a self-crossing or degenerate polygon): cut the flattest corner
            best = min(
                range(n),
                key=lambda k: abs(_turn(poly, order[(k - 1) % n], order[k], order[(k + 1) % n])),
            )
            a, b, c = order[(best - 1) % n], order[best], order[(best + 1) % n]
            if _turn(poly, a, b, c) > 1e-15:
                triangles.append((a, b, c))
            del order[best]
    if len(order) == 3 and _turn(poly, *order) > 1e-15:
        triangles.append(tuple(order))
    if flipped:
        triangles = [(a, c, b) for a, b, c in triangles]
    return triangles


def _turn(poly, a, b, c):
    (ax, ay), (bx, by), (cx, cy) = poly[a], poly[b], poly[c]
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def fill_loop(points, loop):
    """Facets closing one hole (Minimal: no new points). `loop` runs the way the facets
    around it do (boundary_loops), so the patch runs it the other way and faces the same
    side as its neighbours."""
    if len(loop) < 3:
        return []
    loop_points = [points[i] for i in loop]
    normal = newell_normal(loop_points)
    if length(normal) < 1e-300:
        raise MeshError("The hole has no area to fill.")
    u, v = plane_basis(normal)
    origin = loop_points[0]
    poly = [to_2d(p, origin, u, v) for p in loop_points]
    triangles = triangulate_polygon_2d(poly)
    # the loop runs with its neighbours' winding: the patch must run it backwards
    return [(loop[a], loop[c], loop[b]) for a, b, c in triangles]


def plane_section_segments(points, facets, origin, normal, eps):
    """Where the plane cuts the facets, as segments [(p, q)]. Points within `eps` of the plane
    count as on it. An edge lying in the plane comes once, and only where the surface really
    crosses or ends there: between faces on both sides, or at the rim of faces lying in the
    plane (a ring of corners on the plane is not doubled; a flat bottom gives its outline,
    not its triangles' diagonals; where the surface only touches the plane, nothing)."""
    n = unit(normal)
    dist = []
    for p in points:
        x = dot(sub(p, origin), n)
        dist.append(0.0 if abs(x) <= eps else x)
    segments = []
    in_plane = {}  # edge on the plane -> the side of each face it belongs to (0: in the plane)
    for a, b, c in facets:
        da, db, dc = dist[a], dist[b], dist[c]
        if (da > 0 and db > 0 and dc > 0) or (da < 0 and db < 0 and dc < 0):
            continue
        on = [v for v, dv in ((a, da), (b, db), (c, dc)) if dv == 0.0]
        if len(on) == 3:
            for u, v in ((a, b), (b, c), (c, a)):
                in_plane.setdefault((min(u, v), max(u, v)), []).append(0)
            continue
        if len(on) == 2:
            third = [v for v in (a, b, c) if v not in on][0]
            edge = (min(on), max(on))
            in_plane.setdefault(edge, []).append(1 if dist[third] > 0 else -1)
            continue
        cut = [points[v] for v in on]
        for u, v in ((a, b), (b, c), (c, a)):
            if u > v:
                u, v = v, u  # the same numbers for the face on the other side of the edge
            du, dv = dist[u], dist[v]
            if du * dv < 0:
                t = du / (du - dv)
                cut.append(add(points[u], scale(sub(points[v], points[u]), t)))
        if len(cut) == 2 and length(sub(cut[0], cut[1])) > eps:
            segments.append((cut[0], cut[1]))
    for (u, v), sides in in_plane.items():
        if len(set(sides)) > 1 or (len(sides) == 1 and sides[0] != 0):
            segments.append((points[u], points[v]))
    return segments


def chain_segments(segments, quantum):
    """Join segments sharing ends (within `quantum`) into polylines; a segment met twice
    counts once. Open lines first, then closed ones (which end where they start)."""

    def key(p):
        return (round(p[0] / quantum), round(p[1] / quantum), round(p[2] / quantum))

    where = {}
    edges = {}
    for p, q in segments:
        kp, kq = key(p), key(q)
        if kp == kq:
            continue
        where.setdefault(kp, p)
        where.setdefault(kq, q)
        edges.setdefault((min(kp, kq), max(kp, kq)), True)
    links = {}
    for kp, kq in edges:
        links.setdefault(kp, []).append(kq)
        links.setdefault(kq, []).append(kp)
    used = set()

    def walk(start):
        line = [start]
        here = start
        while True:
            step = None
            for other in links.get(here, []):
                edge = (min(here, other), max(here, other))
                if edge not in used:
                    step = other
                    used.add(edge)
                    break
            if step is None:
                return line
            line.append(step)
            here = step
            if here == start:
                return line

    lines = []
    starts = [k for k in links if len(links[k]) % 2 == 1] + list(links)
    for start in starts:
        while any((min(start, o), max(start, o)) not in used for o in links[start]):
            keys = walk(start)
            if len(keys) >= 2:
                lines.append([where[k] for k in keys])
    return lines


def simplify_polyline(points, tolerance, closed=False):
    """Douglas-Peucker: the fewest points keeping the line within `tolerance` of the original
    (a section of a dense mesh would otherwise put thousands of lines in a sketch)."""
    if len(points) < 3 or tolerance <= 0:
        return list(points)
    if closed:
        # split at the point farthest from the first one, simplify both halves
        far = max(range(len(points)), key=lambda i: length(sub(points[i], points[0])))
        first = simplify_polyline(points[: far + 1], tolerance)
        second = simplify_polyline(points[far:] + [points[0]], tolerance)
        return first[:-1] + second[:-1]
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        start, end = stack.pop()
        a, b = points[start], points[end]
        ab = sub(b, a)
        ab2 = dot(ab, ab)
        worst, where = -1.0, None
        for i in range(start + 1, end):
            ap = sub(points[i], a)
            if ab2 > 0:
                t = clamp(dot(ap, ab) / ab2, 0.0, 1.0)
                d = length(sub(ap, scale(ab, t)))
            else:
                d = length(ap)
            if d > worst:
                worst, where = d, i
        if where is not None and worst > tolerance:
            keep[where] = True
            stack.append((start, where))
            stack.append((where, end))
    return [p for p, k in zip(points, keep) if k]


# ----------------------------------------------------------------------------- picked faces
def centroid_key(point, quantum):
    return (
        int(round(point[0] / quantum)),
        int(round(point[1] / quantum)),
        int(round(point[2] / quantum)),
    )


def find_facets(points, facets, picks, quantum):
    """The facets whose centres are the picked ones (each pick is a facet's centre, kept so
    the pick survives a change elsewhere in the mesh). Returns (indices, how many were lost)."""
    table = {}
    for index, facet in enumerate(facets):
        table.setdefault(centroid_key(centroid(points, facet), quantum), index)
    found = []
    lost = 0
    for pick in picks:
        key = centroid_key(pick, quantum)
        index = table.get(key)
        if index is None:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        index = table.get((key[0] + dx, key[1] + dy, key[2] + dz))
                        if index is not None:
                            break
                    if index is not None:
                        break
                if index is not None:
                    break
        if index is None:
            lost += 1
        else:
            found.append(index)
    return sorted(set(found)), lost


def facets_near(points, facets, seed, radius, neighbours=None):
    """The facets joined to `seed` (through shared edges) whose centres lie within `radius`
    of the seed's centre: Fusion's paint brush on a mesh."""
    if neighbours is None:
        neighbours = facet_neighbours(facets)
    centre = centroid(points, facets[seed])
    r2 = radius * radius
    found = {seed}
    todo = [seed]
    while todo:
        f = todo.pop()
        for g in neighbours[f]:
            if g in found:
                continue
            c = centroid(points, facets[g])
            d = sub(c, centre)
            if dot(d, d) <= r2:
                found.add(g)
                todo.append(g)
    return sorted(found)


def facet_neighbours(facets):
    """[[facets sharing an edge with facet i]]."""
    found = [[] for _ in facets]
    for owners in edge_facets(facets).values():
        for f in owners:
            for g in owners:
                if f != g:
                    found[f].append(g)
    return found


# ----------------------------------------------------------------------------- refinement
def split_long_edges(
    points, facets, max_length, max_facets=4000000, passes=24, tags=None, only=None
):
    """Split every edge longer than `max_length` at its middle until none is left (or the
    mesh reaches `max_facets`). Both facets on an edge are split at the same new point, so a
    closed mesh stays closed. `tags`: one value per facet (a face group) that the halves
    keep; `only`: facet indices whose edges may be split (an Erase and Fill patch; a split
    edge still splits the facet on its other side). Returns (points, facets, done), plus the
    new tags when `tags` is given."""
    points = list(points)
    facets = [tuple(f) for f in facets]
    tags = list(tags) if tags is not None else None
    marks = None
    if only is not None:
        chosen = set(only)
        marks = [i in chosen for i in range(len(facets))]
    limit2 = float(max_length) ** 2
    if limit2 <= 0:
        raise MeshError("The edge length must be more than 0.")
    done = False
    for _round in range(passes):
        owners = edge_facets(facets)
        long_edges = []
        for (u, v), on in owners.items():
            if marks is not None and not any(marks[f] for f in on):
                continue
            pu, pv = points[u], points[v]
            dx, dy, dz = pu[0] - pv[0], pu[1] - pv[1], pu[2] - pv[2]
            l2 = dx * dx + dy * dy + dz * dz
            if l2 > limit2:
                long_edges.append((l2, (u, v)))
        if not long_edges:
            done = True
            break
        if len(facets) >= max_facets:
            break
        long_edges.sort(reverse=True)
        busy = {}
        for _l2, key in long_edges:
            on = owners[key]
            if any(f in busy for f in on):
                continue
            u, v = key
            pu, pv = points[u], points[v]
            mid = len(points)
            points.append(((pu[0] + pv[0]) / 2.0, (pu[1] + pv[1]) / 2.0, (pu[2] + pv[2]) / 2.0))
            for f in on:
                busy[f] = (key, mid)
        out = []
        out_tags = [] if tags is not None else None
        out_marks = [] if marks is not None else None
        for index, facet in enumerate(facets):
            entry = busy.get(index)
            if entry is None:
                out.append(facet)
                count = 1
            else:
                (u, v), mid = entry
                a, b, c = facet
                for _ in range(3):
                    if {a, b} == {u, v}:
                        break
                    a, b, c = b, c, a
                out.append((a, mid, c))
                out.append((mid, b, c))
                count = 2
            if out_tags is not None:
                out_tags.extend([tags[index]] * count)
            if out_marks is not None:
                out_marks.extend([marks[index]] * count)
        facets = out
        tags = out_tags
        marks = out_marks
    if tags is not None:
        return points, facets, done, tags
    return points, facets, done


# ----------------------------------------------------------------------------- welding
def weld_open_edges(points, facets, tolerance):
    """Repair's stitch: points on open edges closer than `tolerance` become one, so cracks
    between pieces that should touch close. Facets that collapse and doubled facets go.
    Returns (facets, merged point count)."""
    on_edge = set()
    for u, v in boundary_edges(facets):
        on_edge.add(u)
        on_edge.add(v)
    if not on_edge or tolerance <= 0:
        return list(facets), 0
    cell = float(tolerance)
    grid = {}
    for i in on_edge:
        p = points[i]
        grid.setdefault(
            (
                int(math.floor(p[0] / cell)),
                int(math.floor(p[1] / cell)),
                int(math.floor(p[2] / cell)),
            ),
            [],
        ).append(i)
    uf = _UnionFind(len(points))
    t2 = cell * cell
    for (gx, gy, gz), members in grid.items():
        near = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    near.extend(grid.get((gx + dx, gy + dy, gz + dz), ()))
        for i in members:
            pi = points[i]
            for j in near:
                if j <= i:
                    continue
                pj = points[j]
                ddx, ddy, ddz = pi[0] - pj[0], pi[1] - pj[1], pi[2] - pj[2]
                if ddx * ddx + ddy * ddy + ddz * ddz <= t2:
                    uf.union(i, j)
    merged = sum(1 for i in on_edge if uf.find(i) != i)
    if not merged:
        return list(facets), 0
    remapped = [(uf.find(a), uf.find(b), uf.find(c)) for a, b, c in facets]
    return drop_degenerate(remapped), merged


# ----------------------------------------------------------------------------- face groups
def facet_normals_areas(points, facets):
    normals = []
    areas = []
    for facet in facets:
        n = facet_normal(points, facet)
        size = length(n)
        areas.append(0.5 * size)
        normals.append(
            (n[0] / size, n[1] / size, n[2] / size) if size > 1e-300 else (0.0, 0.0, 0.0)
        )
    return normals, areas


def face_groups(points, facets, angle=ANGLE_THRESHOLD, min_size=MIN_GROUP_SIZE):
    """Generate Face Groups (Fast): neighbouring faces whose normals differ by less than
    `angle` degrees share a group; groups smaller than `min_size` of the body's area join
    the neighbour they share the longest edge with. One group number per facet, the biggest
    group 0."""
    count = len(facets)
    if count == 0:
        return []
    normals, areas = facet_normals_areas(points, facets)
    limit = math.cos(math.radians(clamp(float(angle), 0.0, 90.0)))
    owners = edge_facets(facets)
    uf = _UnionFind(count)
    shared = []
    for (u, v), on in owners.items():
        if len(on) != 2:
            continue
        f, g = on
        nf, ng = normals[f], normals[g]
        if nf[0] * ng[0] + nf[1] * ng[1] + nf[2] * ng[2] >= limit:
            uf.union(f, g)
        else:
            pu, pv = points[u], points[v]
            shared.append((f, g, length(sub(pu, pv))))
    groups = [uf.find(i) for i in range(count)]
    total = sum(areas) or 1.0
    floor_area = clamp(float(min_size), 0.0, 1.0) * total
    for _round in range(64):
        size = {}
        for i, g in enumerate(groups):
            size[g] = size.get(g, 0.0) + areas[i]
        small = {g for g, a in size.items() if a < floor_area}
        if not small or len(size) == 1:
            break
        border = {}
        for f, g, edge_len in shared:
            gf, gg = groups[f], groups[g]
            if gf == gg:
                continue
            for a, b in ((gf, gg), (gg, gf)):
                if a in small:
                    border.setdefault(a, {})
                    border[a][b] = border[a].get(b, 0.0) + edge_len
        if not border:
            break
        # the smallest group first, into its longest-shared neighbour
        target = {}
        for g in sorted(border, key=lambda k: size[k]):
            if g in target or g in target.values():
                continue
            best = max(border[g].items(), key=lambda kv: (kv[1], size[kv[0]]))[0]
            target[g] = best
        if not target:
            break
        groups = [target.get(g, g) for g in groups]
    # renumber: biggest area first
    size = {}
    for i, g in enumerate(groups):
        size[g] = size.get(g, 0.0) + areas[i]
    order = sorted(size, key=lambda g: (-size[g], g))
    number = {g: n for n, g in enumerate(order)}
    return [number[g] for g in groups]


def group_count(groups):
    return len(set(groups)) if groups else 0


def group_colors(groups):
    """One colour per facet (r, g, b in 0..1): each face group its own, evenly spread hues,
    soft enough for the dark theme."""
    colours = {}
    for g in set(groups):
        hue = (g * 0.618033988749895) % 1.0
        colours[g] = _hsv(hue, 0.45, 0.92)
    return [colours[g] for g in groups]


def _hsv(h, s, v):
    i = int(h * 6.0) % 6
    f = h * 6.0 - int(h * 6.0)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    return [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][i]


# ----------------------------------------------------------------------------- the voxel rebuild
class Grid:
    """Cells of edge `cell` covering a box with an empty cell all round. Cell (i, j, k) has
    its centre at origin + (i + 0.5, j + 0.5, k + 0.5) * cell; flat index i + nx * (j + ny * k).
    The box's low corner is a cell corner, so the centres of a body whose sizes are whole
    cells never lie on its faces."""

    def __init__(self, lo, hi, cell):
        self.cell = float(cell)
        self.origin = tuple(lo[a] - self.cell for a in range(3))
        self.n = tuple(int(math.ceil((hi[a] - lo[a]) / self.cell - 1e-9)) + 2 for a in range(3))
        self.size = self.n[0] * self.n[1] * self.n[2]

    def index(self, i, j, k):
        return i + self.n[0] * (j + self.n[1] * k)

    def centre(self, axis, i):
        return self.origin[axis] + (i + 0.5) * self.cell


MAX_CELLS = 24000000
# Rays run a hair off the cell centres (fractions of a cell, irrational) so a ray never goes
# exactly through a mesh edge or corner, which would count that crossing twice or not at all.
RAY_SHIFT = (0.000173205, 0.000223607)


def _rays(points, facets, grid, axis):
    """Every facet a ray parallel to `axis` crosses, for the rays through the cell centres:
    {(i, j): [(position along the ray, +1 going in / -1 going out, facet index)]}. The way a
    facet faces tells in from out, so overlapping shells count as one."""
    a1, a2 = [a for a in range(3) if a != axis]
    n1, n2 = grid.n[a1], grid.n[a2]
    h = grid.cell
    o1 = grid.origin[a1] + RAY_SHIFT[0] * h
    o2 = grid.origin[a2] + RAY_SHIFT[1] * h
    flip_sense = axis == 1  # (x, z) is a left-handed pair seen along y
    columns = {}
    setdefault = columns.setdefault
    ceil, floor = math.ceil, math.floor
    for index, facet in enumerate(facets):
        p, q, r = points[facet[0]], points[facet[1]], points[facet[2]]
        x0, y0, x1, y1, x2, y2 = p[a1], p[a2], q[a1], q[a2], r[a1], r[a2]
        det = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        if abs(det) < 1e-300:
            continue  # seen edge-on along this axis: no ray crosses it
        facing_up = (det > 0) != flip_sense
        step = -1 if facing_up else 1  # a facet facing +axis is where a ray leaves
        i_lo = max(0, int(ceil((min(x0, x1, x2) - o1) / h - 0.5)))
        i_hi = min(n1 - 1, int(floor((max(x0, x1, x2) - o1) / h - 0.5)))
        if i_lo > i_hi:
            continue
        j_lo = max(0, int(ceil((min(y0, y1, y2) - o2) / h - 0.5)))
        j_hi = min(n2 - 1, int(floor((max(y0, y1, y2) - o2) / h - 0.5)))
        if j_lo > j_hi:
            continue
        inv = 1.0 / det
        pa, qa, ra = p[axis], q[axis], r[axis]
        for i in range(i_lo, i_hi + 1):
            cx = o1 + (i + 0.5) * h
            for j in range(j_lo, j_hi + 1):
                cy = o2 + (j + 0.5) * h
                w1 = ((cx - x0) * (y2 - y0) - (x2 - x0) * (cy - y0)) * inv
                if w1 < 0:
                    continue
                w2 = ((x1 - x0) * (cy - y0) - (cx - x0) * (y1 - y0)) * inv
                if w2 < 0 or w1 + w2 > 1.0:
                    continue
                t = (1.0 - w1 - w2) * pa + w1 * qa + w2 * ra
                setdefault((i, j), []).append((t, step, index))
    return columns


def _fill(columns, grid, axis):
    """A bytearray of the cells these rays find inside (1 inside): a cell is inside where
    more shells were gone into than left (winding number not 0), so overlapping shells count
    as one and a mesh facing inwards everywhere still has its inside. A ray whose count does
    not come back to 0 (a flipped or doubled face on it) is read by parity instead: every
    crossing switches in and out."""
    inside = bytearray(grid.size)
    a1, a2 = [a for a in range(3) if a != axis]
    n = grid.n
    stride = (1, n[0], n[0] * n[1])
    step_along = stride[axis]
    h = grid.cell
    origin = grid.origin[axis]
    count = n[axis]
    ceil = math.ceil

    def cell(t):
        k = int(ceil((t - origin) / h - 0.5))  # first cell centre at or after t
        return 0 if k < 0 else (count if k > count else k)

    def run(base, start, end):
        if end > start:
            first = base + start * step_along
            last = base + (end - 1) * step_along
            inside[first : last + 1 : step_along] = b"\x01" * (end - start)

    for (i, j), hits in columns.items():
        hits.sort()
        base = i * stride[a1] + j * stride[a2]
        if sum(step for _t, step, _f in hits) != 0:
            for n_hit in range(0, len(hits) - 1, 2):  # parity
                run(base, cell(hits[n_hit][0]), cell(hits[n_hit + 1][0]))
            continue
        winding = 0
        start = None
        for t, step, _facet in hits:
            before = winding
            winding += step
            if before == 0 and winding != 0:
                start = cell(t)
            elif before != 0 and winding == 0 and start is not None:
                run(base, start, cell(t))
                start = None
    return inside


def solid_cells(points, facets, grid, keep_rays=False):
    """Cells inside the mesh: rays along x, y and z vote (two of three win), so a ray that
    slips through a small hole or a crack does not leave a streak. With `keep_rays`, the
    rays' crossings come back too (exact_crossings uses them)."""
    if grid.size > MAX_CELLS:
        raise MeshError(
            "That Density makes %d million cells: use a lower Density." % (grid.size // 1000000)
        )
    votes = []
    rays = []
    for axis in (0, 1, 2):
        columns = _rays(points, facets, grid, axis)
        votes.append(_fill(columns, grid, axis))
        rays.append(columns if keep_rays else None)
    total = (
        int.from_bytes(votes[0], "little")
        + int.from_bytes(votes[1], "little")
        + int.from_bytes(votes[2], "little")
    ).to_bytes(grid.size, "little")
    table = bytes([0, 0, 1, 1] + [0] * 252)
    inside = bytearray(total.translate(table))
    return (inside, rays) if keep_rays else inside


def _xor(a, b):
    return (int.from_bytes(a, "little") ^ int.from_bytes(b, "little")).to_bytes(len(a), "little")


def _changes(inside, grid, axis):
    """Flat indices c of cells whose neighbour c + stride along `axis` is on the other side."""
    n = grid.n
    stride = (1, n[0], n[0] * n[1])[axis]
    diff = _xor(bytes(inside[:-stride]), bytes(inside[stride:]))
    found = []
    pos = diff.find(1)
    while pos >= 0:
        found.append(pos)
        pos = diff.find(1, pos + 1)
    if axis == 0:
        found = [c for c in found if c % n[0] != n[0] - 1]
    elif axis == 1:
        found = [c for c in found if (c // n[0]) % n[1] != n[1] - 1]
    return found


def _coords(c, n):
    i = c % n[0]
    j = (c // n[0]) % n[1]
    k = c // (n[0] * n[1])
    return i, j, k


def blocky_surface(inside, grid):
    """The cells' outer squares (two triangles each), facing out. Points are cell corners."""
    n = grid.n
    h = grid.cell
    ox, oy, oz = grid.origin
    corner_index = {}
    points = []

    def corner(i, j, k):
        key = (i, j, k)
        found = corner_index.get(key)
        if found is None:
            found = corner_index[key] = len(points)
            points.append((ox + i * h, oy + j * h, oz + k * h))
        return found

    facets = []
    for axis in (0, 1, 2):
        for c in _changes(inside, grid, axis):
            i, j, k = _coords(c, n)
            filled = inside[c] == 1  # the lower cell is the inside one: the square faces +axis
            if axis == 0:
                quad = [
                    corner(i + 1, j, k),
                    corner(i + 1, j + 1, k),
                    corner(i + 1, j + 1, k + 1),
                    corner(i + 1, j, k + 1),
                ]
            elif axis == 1:
                quad = [
                    corner(i, j + 1, k),
                    corner(i, j + 1, k + 1),
                    corner(i + 1, j + 1, k + 1),
                    corner(i + 1, j + 1, k),
                ]
            else:
                quad = [
                    corner(i, j, k + 1),
                    corner(i + 1, j, k + 1),
                    corner(i + 1, j + 1, k + 1),
                    corner(i, j + 1, k + 1),
                ]
            if not filled:
                quad.reverse()
            facets.append((quad[0], quad[1], quad[2]))
            facets.append((quad[0], quad[2], quad[3]))
    return points, facets


def dual_surface(inside, grid, crossings=None, normals=None, sharp=False):
    """A smooth surface between inside and outside cells (surface nets): one point per block
    of 2 x 2 x 2 cell centres that is partly inside, placed at the mean of where its edges
    cross the surface (the edge middle when the exact place is not known), or, with
    `sharp`, where the crossing faces' planes meet (dual contouring: corners stay corners).
    Every edge between an inside and an outside cell centre gives a square of four such
    points. `crossings`: {(cell, axis): position on that edge}; `normals`: {(cell, axis):
    the crossed facet's unit normal}."""
    n = grid.n
    h = grid.cell
    ox, oy, oz = grid.origin
    nx, nxy = n[0], n[0] * n[1]
    strides = (1, nx, nxy)
    crossings = crossings or {}
    normals = normals or {}
    vertex_of = {}
    points = []

    def edge_point(c, axis):
        exact = crossings.get((c, axis))
        i, j, k = _coords(c, n)
        base = [ox + (i + 0.5) * h, oy + (j + 0.5) * h, oz + (k + 0.5) * h]
        if exact is not None:
            base[axis] = exact
        else:
            base[axis] += 0.5 * h
        return tuple(base)

    def block_point(bi, bj, bk):
        key = (bi, bj, bk)
        found = vertex_of.get(key)
        if found is not None:
            return found
        # the block's 8 cell centres: (bi..bi+1, bj..bj+1, bk..bk+1)
        hits = []
        planes = []
        for axis in (0, 1, 2):
            others = [a for a in range(3) if a != axis]
            for d1 in (0, 1):
                for d2 in (0, 1):
                    idx = [bi, bj, bk]
                    idx[others[0]] += d1
                    idx[others[1]] += d2
                    c = idx[0] + nx * idx[1] + nxy * idx[2]
                    if inside[c] != inside[c + strides[axis]]:
                        p = edge_point(c, axis)
                        hits.append(p)
                        nrm = normals.get((c, axis))
                        if nrm is not None:
                            planes.append((p, nrm))
        if not hits:
            mass = (ox + (bi + 1.0) * h, oy + (bj + 1.0) * h, oz + (bk + 1.0) * h)
        else:
            mass = (
                sum(p[0] for p in hits) / len(hits),
                sum(p[1] for p in hits) / len(hits),
                sum(p[2] for p in hits) / len(hits),
            )
        point = mass
        if sharp and len(planes) >= 2:
            point = _qef_point(planes, mass, h)
            lo = (ox + (bi + 0.5) * h, oy + (bj + 0.5) * h, oz + (bk + 0.5) * h)
            if not all(lo[a] - 1e-9 <= point[a] <= lo[a] + h + 1e-9 for a in range(3)):
                point = mass
        found = vertex_of[key] = len(points)
        points.append(point)
        return found

    facets = []
    for axis in (0, 1, 2):
        a1, a2 = [a for a in range(3) if a != axis]
        for c in _changes(inside, grid, axis):
            idx = list(_coords(c, n))
            # the four blocks around the edge from cell c along `axis`
            quad = []
            for d1, d2 in ((0, 0), (1, 0), (1, 1), (0, 1)):
                b = list(idx)
                b[a1] -= 1 - d1
                b[a2] -= 1 - d2
                if min(b) < 0 or b[0] >= n[0] - 1 or b[1] >= n[1] - 1 or b[2] >= n[2] - 1:
                    quad = None
                    break
                quad.append(block_point(b[0], b[1], b[2]))
            if quad is None:
                continue
            lower_inside = inside[c] == 1
            # (a1, a2, axis) is right-handed for axis x and z, left-handed for y
            facing_up = lower_inside != (axis == 1)
            if not facing_up:
                quad.reverse()
            facets.append((quad[0], quad[1], quad[2]))
            facets.append((quad[0], quad[2], quad[3]))
    return points, facets


def _qef_point(planes, mass, h):
    """The point closest (least squares) to all the planes (p, n), pulled a little toward
    `mass` so flat spots stay put: dual contouring's vertex."""
    reg = 0.05
    ata = [[reg, 0.0, 0.0], [0.0, reg, 0.0], [0.0, 0.0, reg]]
    atb = [reg * mass[0], reg * mass[1], reg * mass[2]]
    for p, nrm in planes:
        d = dot(nrm, p)
        for r in range(3):
            for c in range(3):
                ata[r][c] += nrm[r] * nrm[c]
            atb[r] += nrm[r] * d
    solved = _solve3(ata, atb)
    return solved if solved is not None else mass


def _solve3(m, b):
    (a, bb, c), (d, e, f), (g, hh, i) = m
    det = a * (e * i - f * hh) - bb * (d * i - f * g) + c * (d * hh - e * g)
    if abs(det) < 1e-18:
        return None
    x = (b[0] * (e * i - f * hh) - bb * (b[1] * i - f * b[2]) + c * (b[1] * hh - e * b[2])) / det
    y = (a * (b[1] * i - f * b[2]) - b[0] * (d * i - f * g) + c * (d * b[2] - b[1] * g)) / det
    z = (a * (e * b[2] - b[1] * hh) - bb * (d * b[2] - b[1] * g) + b[0] * (d * hh - e * g)) / det
    return (x, y, z)


def exact_crossings(points, facets, grid, inside, rays):
    """Where the mesh crosses each edge between two cell centres that changed side
    ({(cell, axis): position}) and the crossed facet's unit normal: the rays of solid_cells
    run through the cell centres, so an edge along a ray is crossed exactly where a facet
    cuts that ray."""
    n = grid.n
    strides = (1, n[0], n[0] * n[1])
    h = grid.cell
    found = {}
    normals = {}
    for axis in (0, 1, 2):
        a1, a2 = [a for a in range(3) if a != axis]
        changed = set(_changes(inside, grid, axis))
        if not changed or not rays[axis]:
            continue
        origin = grid.origin[axis]
        for (i, j), hits in rays[axis].items():
            base = i * strides[a1] + j * strides[a2]
            for t, _step, facet in hits:
                k = int(math.floor((t - origin) / h - 0.5))
                if k < 0 or k >= n[axis] - 1:
                    continue
                c = base + k * strides[axis]
                if c in changed and (c, axis) not in found:
                    found[(c, axis)] = t
                    try:
                        normals[(c, axis)] = unit(facet_normal(points, facets[facet]))
                    except MeshError:
                        pass
    return found, normals


def rebuild(points, facets, density, kind="Fast"):
    """Repair > Rebuild (and Remesh Uniform of a closed body): a new closed surface made from
    the cells inside the mesh. Fast: the surface between the cells (smoothed afterwards by
    the caller); Accurate: its points put where the old surface crosses; Preserve Sharp
    Edges: where the crossed faces' planes meet; Blocky: the cells' own squares. Returns
    (points, facets); raises MeshError when nothing is inside."""
    facets = drop_degenerate(facets)  # a doubled face would be crossed twice
    if not facets:
        raise MeshError("The body has no faces to rebuild from.")
    lo, hi = bounds(points)
    size = max(hi[a] - lo[a] for a in range(3))
    grid = Grid(lo, hi, rebuild_cell(size, density))
    inside, rays = solid_cells(points, facets, grid, keep_rays=True)
    if inside.count(1) == 0:
        raise MeshError(
            "No inside could be found: the mesh is a surface with no volume (or far too thin "
            "for this Density). Try a higher Density."
        )
    if kind == "Blocky":
        return blocky_surface(inside, grid)
    crossings, normals = ({}, {})
    if kind in ("Accurate", "Preserve Sharp Edges"):
        crossings, normals = exact_crossings(points, facets, grid, inside, rays)
    return dual_surface(inside, grid, crossings, normals, sharp=(kind == "Preserve Sharp Edges"))
