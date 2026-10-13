# SPDX-License-Identifier: LGPL-2.1-or-later
"""The MESH tab's steps in the design (no Qt): Repair (and Make Closed Mesh), Remesh, Reduce,
Smooth, Plane Cut, Separate, Combine, Reverse Normal, Shell, Erase and Fill, Delete Faces,
Generate Face Groups and Tessellate, each one timeline step, plus Create Mesh Section Sketch.
Spec and sources: docs/sciforge/parity/mesh.md.

How a mesh body keeps its history (Fusion keeps one body and lists its features in the
timeline): every step is a Mesh::FeaturePython that reads the body as the step before left it
(its Source) and holds the body as it is after. The newest step is the body: it is the one
shown and listed in the browser's Bodies folder; the steps before it are used up
(bodies.CONSUMERS: hidden and out of the browser, like Combine's tool bodies). Every step of
a body carries the body's name as its Label (the browser, Export and the dialogs show
Labels); the timeline shows the step's own name (SciForgeStepLabel; empty: "Repair 2"). The
bodies a step makes beside its own (Separate's pieces, Split Body's halves) are MeshPiece
objects that read their part from that step; the step itself is then used up by them.

Everything runs on FreeCAD's Mesh module (C++) where it has the tool (holes, normals,
non-manifolds, decimation, smoothing, plane trimming, set operations, offsets) and on
mesh_core (pure Python) where it has not.
"""

import math

from . import log, warn
from . import mesh_core as core
from .mesh_core import MeshError


class _Lazy:
    def __init__(self, name):
        self._name = name

    def __getattr__(self, attr):
        import importlib

        module = importlib.import_module("." + self._name, __package__)
        return getattr(module, attr)


bodies = _Lazy("bodies")
insert = _Lazy("insert")

STEP_TYPE = "Mesh::FeaturePython"
MESH_TYPES = ("Mesh::Feature", "Mesh::FeaturePython")
PROXY = "sciforge.mesh.MeshStep"  # saved in files: keep the class name and module

# SciForgeType -> (object name, Fusion's name of the step)
KINDS = {
    "MeshRepair": ("Repair", "Repair"),
    "MeshRemesh": ("Remesh", "Remesh"),
    "MeshReduce": ("Reduce", "Reduce"),
    "MeshSmooth": ("Smooth", "Smooth"),
    "MeshPlaneCut": ("PlaneCut", "Plane Cut"),
    "MeshSeparate": ("Separate", "Separate"),
    "MeshCombine": ("MeshCombine", "Combine"),
    "MeshReverseNormal": ("ReverseNormal", "Reverse Normal"),
    "MeshShell": ("MeshShell", "Shell"),
    "MeshEraseFill": ("EraseFill", "Erase And Fill"),
    "MeshDeleteFaces": ("DeleteFaces", "Delete Faces"),
    "MeshFaceGroups": ("FaceGroups", "Generate Face Groups"),
    "Tessellate": ("Tessellate", "Tessellate"),
}
PIECE = "MeshPiece"  # a body made beside a step's own (not a timeline step)
STEP_LABEL = "SciForgeStepLabel"
WARNING = "SciForgeWarning"
HOLD = set()  # "doc/name" of steps whose dialog has Preview off: they pass their body through


def _key(obj):
    return "%s/%s" % (obj.Document.Name, obj.Name)


# ----------------------------------------------------------------------------- finding meshes
def is_mesh(obj):
    try:
        return obj is not None and obj.TypeId in MESH_TYPES
    except Exception:
        return False


def kind(obj):
    try:
        return getattr(obj, "SciForgeType", "") or ""
    except Exception:
        return ""


def is_step(obj):
    return kind(obj) in KINDS


def is_piece(obj):
    return kind(obj) == PIECE


def step_of(obj):
    """The step a body comes from: a piece's step, else the object itself."""
    if is_piece(obj):
        return getattr(obj, "Source", None)
    return obj


def mesh_bodies(doc, include_hidden=True):
    """The mesh bodies of the design as the browser lists them: every mesh object no later
    step uses up (shown or not)."""
    if doc is None:
        return []
    used = bodies.consumed(doc)
    found = []
    for obj in doc.Objects:
        if not is_mesh(obj) or obj.Name in used:
            continue
        if not include_hidden and not bodies.is_shown(obj):
            continue
        found.append(obj)
    return found


def global_mesh(obj):
    """A copy of a mesh body's triangles where they are in the design (its placement built
    in), with no placement of its own."""
    mesh = insert.kernel_copy(obj)
    placement = obj.Placement
    if not placement.isIdentity():
        mesh.transform(placement.toMatrix())
    return mesh


def size_of(mesh):
    box = mesh.BoundBox
    return max(box.XLength, box.YLength, box.ZLength)


def topology(mesh):
    """(points as tuples, facets as tuples) of a FreeCAD mesh."""
    points, facets = mesh.Topology
    return [(p.x, p.y, p.z) for p in points], [tuple(f) for f in facets]


def signed_volume(mesh):
    """The volume the faces enclose, negative when they point inward. (FreeCAD's
    Mesh.Volume is always positive: it cannot tell an inside-out body.)"""
    if mesh.CountFacets == 0:
        return 0.0
    return core.signed_volume(*topology(mesh))


def from_topology(points, facets):
    import FreeCAD as App
    import Mesh

    if not facets:
        return Mesh.Mesh()
    return Mesh.Mesh(([App.Vector(*p) for p in points], [tuple(f) for f in facets]))


# ----------------------------------------------------------------------------- analysis
def analyze(mesh, self_intersections=False):
    """What Repair's analysis counts: holes, flipped faces, edges with more than two faces,
    separate shells, doubled and empty faces, and whether the mesh is closed."""
    info = {"facets": mesh.CountFacets, "points": mesh.CountPoints}
    if mesh.CountFacets == 0:
        info.update(closed=False, holes=0, shells=0)
        return info
    points, facets = topology(mesh)
    info["holes"] = len(core.boundary_loops(facets))
    info["open_edges"] = len(core.boundary_edges(facets))
    info["non_manifold"] = len(core.non_manifold_edges(facets))
    try:
        info["flipped"] = int(mesh.countNonUniformOrientedFacets())
    except Exception:
        info["flipped"] = 0
    info["shells"] = int(mesh.countComponents())
    before = len(facets)
    info["duplicated"] = before - len(core.drop_degenerate([f for f in facets if len(set(f)) == 3]))
    info["degenerate"] = sum(1 for f in facets if core.facet_area(points, f) <= 1e-12)
    if self_intersections:
        try:
            info["self_intersections"] = len(mesh.getSelfIntersections())
        except Exception:
            info["self_intersections"] = 0
    info["closed"] = (
        info["holes"] == 0
        and info["open_edges"] == 0
        and info["non_manifold"] == 0
        and info["flipped"] == 0
    )
    info["volume"] = core.signed_volume(points, facets) if info["closed"] else None
    # closed but the faces point in: a slicer may print it as a hole
    info["inside_out"] = bool(info["closed"] and info["volume"] < 0)
    return info


def describe(mesh):
    """One line for a dialog: faces, size, closed or what is wrong."""
    info = analyze(mesh)
    box = mesh.BoundBox
    text = "%d faces, %.1f x %.1f x %.1f mm" % (
        info["facets"],
        box.XLength,
        box.YLength,
        box.ZLength,
    )
    problems = core.analysis_lines(info)
    if info["closed"] and not problems:
        return text + ", closed"
    if problems:
        return text + "; " + ", ".join(problems)
    return text + "; not closed"


_HEALTH = {}


def browser_note(obj):
    """("warning", text) for a mesh body the browser should flag (Fusion puts a warning
    beside a mesh body that is not closed: its tip lists the problems, Repair fixes them),
    or None. Cached per triangle count: the browser refreshes often."""
    if not is_mesh(obj):
        return None
    failed = problem(obj)
    if failed:
        return ("warning", failed)
    try:
        mesh = obj.Mesh
        if mesh.CountFacets == 0:
            return None
        key = (obj.Document.Name, obj.Name)
        stamp = (mesh.CountFacets, mesh.CountPoints, round(mesh.Area, 6))
        cached = _HEALTH.get(key)
        if cached is not None and cached[0] == stamp:
            return cached[1]
        note = None
        solid = mesh.isSolid()
        if not solid or mesh.hasNonManifolds() or mesh.countNonUniformOrientedFacets():
            import MeshPart

            parts = []
            holes = len(MeshPart.wireFromMesh(mesh))
            if holes:
                parts.append("%d hole%s" % (holes, "" if holes == 1 else "s"))
            flipped = mesh.countNonUniformOrientedFacets()
            if flipped:
                parts.append("%d flipped face%s" % (flipped, "" if flipped == 1 else "s"))
            if mesh.hasNonManifolds():
                parts.append("edges with more than two faces")
            note = (
                "warning",
                "Not closed (%s): right-click > Repair, or MESH > Repair."
                % (", ".join(parts) or "open edges"),
            )
        elif signed_volume(mesh) < 0:
            note = (
                "warning",
                "Inside out (all the faces point inward): MESH > Reverse Normal, or Repair.",
            )
        if len(_HEALTH) > 500:
            _HEALTH.clear()
        _HEALTH[key] = (stamp, note)
        return note
    except Exception:
        return None


# ----------------------------------------------------------------------------- the operations
def _orient_outward(mesh):
    try:
        mesh.harmonizeNormals()
    except Exception:
        pass
    try:
        if mesh.isSolid() and signed_volume(mesh) < 0:
            mesh.flipNormals()
    except Exception:
        pass


def _fill_holes(mesh, max_area=0.0):
    """Close every hole; returns how many were filled."""
    before = len(core.boundary_loops(topology(mesh)[1]))
    if not before:
        return 0
    try:
        mesh.fillupHoles(2**31 - 1, 0, float(max_area))
    except Exception as exc:
        log("hole filling stopped: %s" % exc)
    after = len(core.boundary_loops(topology(mesh)[1]))
    if after:
        # FreeCAD skips holes it cannot flatten (bent rims): close those one by one
        points, facets = topology(mesh)
        extra = []
        for loop in core.boundary_loops(facets):
            try:
                extra += core.fill_loop(points, loop)
            except MeshError:
                continue
        if extra:
            mesh.clear()
            rebuilt = from_topology(points, core.drop_degenerate(facets + extra))
            mesh.addMesh(rebuilt)
            mesh.removeDuplicatedPoints()
    return before - len(core.boundary_loops(topology(mesh)[1]))


def _remove_tiny_shells(mesh):
    """Stitch and Remove drops small loose pieces: shells under 0.1 % of the faces (at least
    3 faces' worth), which are left-overs, not parts of the model."""
    limit = max(3, int(mesh.CountFacets * 0.001))
    if mesh.countComponents() > 1:
        mesh.removeComponents(limit)


def _inside(container, point):
    """Is `point` inside the closed `container` mesh (rays along three axes vote)."""
    import FreeCAD as App

    votes = 0
    for direction in ((1, 0.0001, 0.0002), (0.0003, 1, 0.0001), (0.0002, 0.0001, 1)):
        hits = container.foraminate(App.Vector(*point), App.Vector(*direction))
        # foraminate reports hits both ways along the line: count the ones ahead
        ahead = 0
        for xyz in hits.values():
            d = core.sub(tuple(xyz), point)
            if core.dot(d, direction) > 0:
                ahead += 1
        votes += ahead % 2
    return votes >= 2


def _drop_inner_shells(mesh):
    """Wrap's 'inner structures': shells lying wholly inside another closed shell."""
    import Mesh

    parts = mesh.getSeparateComponents()
    if len(parts) < 2:
        return 0
    closed = [p for p in parts if p.isSolid()]
    keep = []
    dropped = 0
    for part in parts:
        probe = tuple(part.Topology[0][0]) if part.CountPoints else None
        inner = False
        if probe is not None:
            for other in closed:
                if other is part or other.Volume < part.Volume:
                    continue
                if _inside(other, probe):
                    inner = True
                    break
        if inner:
            dropped += 1
        else:
            keep.append(part)
    if dropped:
        merged = Mesh.Mesh()
        for part in keep:
            merged.addMesh(part)
        mesh.clear()
        mesh.addMesh(merged)
    return dropped


def repair_mesh(
    mesh,
    repair_type=core.DEFAULT_REPAIR,
    rebuild_type=core.DEFAULT_REBUILD,
    density=core.REBUILD_DENSITY[2],
    offset=0.0,
):
    """Repair. Returns (mesh, report dict). Close Holes turns flipped faces round and closes
    holes; Stitch and Remove also joins cracks, drops doubled, empty and non-manifold faces
    and tiny loose shells; Wrap also drops inner shells, faces inside the body and faces
    that cross each other; Rebuild makes a new closed surface from the inside (voxels)."""
    import Mesh

    if mesh.CountFacets == 0:
        raise MeshError("The body has no faces to repair.")
    if repair_type not in core.REPAIR_TYPES:
        raise MeshError("Unknown repair type: %s" % repair_type)
    before = analyze(mesh)
    work = mesh.copy()
    level = core.REPAIR_TYPES.index(repair_type)
    report = {"before": before}
    if repair_type == "Rebuild":
        _orient_outward(work)
        points, facets = topology(work)
        new_points, new_facets = core.rebuild(points, facets, density, rebuild_type)
        work = from_topology(new_points, new_facets)
        work.removeDuplicatedPoints()
        if rebuild_type == "Fast":
            work.smooth(Method="Taubin", Iteration=3)
        if rebuild_type == "Accurate" and abs(float(offset)) > 1e-12:
            work.offset(float(offset))
        _orient_outward(work)
    else:
        if level >= 1:  # Stitch and Remove
            work.removeDuplicatedPoints()
            work.removeDuplicatedFacets()
            points, facets = topology(work)
            welded, merged = core.weld_open_edges(points, facets, 1e-4 * max(size_of(work), 1.0))
            if merged:
                work = from_topology(*core.compact(points, welded))
            report["stitched"] = merged
            work.fixDegenerations(1e-6)
            work.removeNonManifolds()
            work.removeNonManifoldPoints()
            _remove_tiny_shells(work)
        if level >= 2:  # Wrap
            report["inner_shells"] = _drop_inner_shells(work)
            try:
                inner = list(work.getInternalFacets())
                if inner and len(inner) < work.CountFacets:
                    work.removeFacets(inner)
            except Exception:
                pass
            try:
                work.fixSelfIntersections()
            except Exception:
                pass
            work.removeNonManifolds()
        _orient_outward(work)
        report["filled"] = _fill_holes(work)
        _orient_outward(work)
    if work.CountFacets == 0:
        raise MeshError("Nothing is left after %s: this mesh cannot be repaired." % repair_type)
    after = analyze(work)
    report["after"] = after
    report["advice"] = core.repair_advice(after, repair_type)
    return Mesh.Mesh(work), report


def reduce_mesh(
    mesh,
    target="Tolerance",
    tolerance=core.DEFAULT_TOLERANCE,
    proportion=core.DEFAULT_PROPORTION,
    face_count=None,
    reduce_type="Adaptive",
):
    """Reduce: fewer faces, within a deviation (Tolerance) or to a number of faces."""
    count = mesh.CountFacets
    if count < 8:
        raise MeshError("The body has only %d faces: there is nothing to reduce." % count)
    work = mesh.copy()
    wanted = core.reduce_target_count(count, target, proportion, face_count)
    if wanted is None:
        work.decimate(core.quadric_tolerance(tolerance), 1.0)
    elif reduce_type == "Uniform" and mesh.isSolid():
        edge = math.sqrt(work.Area / (0.4330127018922193 * wanted))
        work = _uniform_surface(work, edge, sharp=True)
        if work.CountFacets > wanted:
            work.decimate(int(wanted))
    else:
        work.decimate(int(wanted))
    _orient_outward(work)
    return work


def _uniform_surface(mesh, edge, sharp=False):
    """A new closed surface of even triangles about `edge` long, on the old one."""
    points, facets = topology(mesh)
    size = size_of(mesh)
    density = core.clamp(size / max(edge, 1e-9), core.REBUILD_DENSITY[0], core.REBUILD_DENSITY[1])
    kind = "Preserve Sharp Edges" if sharp else "Accurate"
    new_points, new_facets = core.rebuild(points, facets, density, kind)
    work = from_topology(new_points, new_facets)
    work.removeDuplicatedPoints()
    return work


def remesh_mesh(
    mesh,
    remesh_type="Adaptive",
    density=core.REMESH_DENSITY,
    shape_preservation=core.SHAPE_PRESERVATION,
    sharp=False,
    boundaries=False,
):
    """Remesh: new faces of a size set by Density. Adaptive puts more, smaller faces where
    the shape bends; Uniform makes them all about the same size."""
    if mesh.CountFacets == 0:
        raise MeshError("The body has no faces to remesh.")
    box = mesh.BoundBox
    diag = box.DiagonalLength
    edge = core.remesh_edge_length(diag, density)
    wanted = max(8, core.remesh_face_count(mesh.Area, edge))
    if wanted > 4000000:
        raise MeshError("That Density would make %d faces: use a lower Density." % wanted)
    closed = mesh.isSolid()
    if remesh_type == "Uniform" and closed:
        work = _uniform_surface(mesh, edge, sharp=sharp)
    else:
        work = mesh.copy()
        if wanted > work.CountFacets:
            points, facets = topology(work)
            fine = edge if remesh_type == "Uniform" else edge * 0.5
            points, facets, _done = core.split_long_edges(
                points, facets, fine, max_facets=4 * wanted
            )
            work = from_topology(points, facets)
        if work.CountFacets > wanted:
            work.decimate(int(wanted))
        rounds = int(round((1.0 - core.clamp(float(shape_preservation), 0.0, 1.0)) * 6))
        if rounds and not sharp and not (boundaries and not closed):
            work.smooth(Method="Taubin", Iteration=rounds)
    _orient_outward(work)
    return work


def smooth_mesh(mesh, smoothness=core.DEFAULT_SMOOTHNESS):
    work = mesh.copy()
    rounds = core.smooth_iterations(smoothness)
    if rounds:
        work.smooth(Method="Taubin", Iteration=rounds)
    return work


def reverse_mesh(mesh, groups=None, selected=None):
    """Reverse Normal: every face turned over, or only the faces of the chosen face groups."""
    if not selected or not groups:
        work = mesh.copy()
        work.flipNormals()
        return work
    chosen = set(selected)
    which = [i for i, g in enumerate(groups) if g in chosen]
    points, facets = topology(mesh)
    return from_topology(points, core.flip(facets, which))


def shell_mesh(mesh, thickness):
    """Shell: the body hollowed with walls `thickness` thick (the inside wall faces in)."""
    thickness = float(thickness)
    if thickness <= 0:
        raise MeshError("The wall must be thicker than 0 mm.")
    if not mesh.isSolid():
        raise MeshError("Shell needs a closed body: Repair it first (PREPARE > Repair).")
    box = mesh.BoundBox
    smallest = min(box.XLength, box.YLength, box.ZLength)
    if thickness * 2.0 >= smallest:
        raise MeshError(
            "A %.2f mm wall does not fit: the body is %.2f mm across at its thinnest. "
            "Try under %.2f mm." % (thickness, smallest, smallest / 2.0)
        )
    work = mesh.copy()
    _orient_outward(work)
    points, facets = topology(work)
    inner_points = core.offset_points(points, facets, -thickness)
    inner = from_topology(inner_points, facets)
    if inner.hasSelfIntersections():
        raise MeshError(
            "A %.2f mm wall is too thick for this body: its inside wall would cross itself. "
            "Try a thinner wall." % thickness
        )
    inside = core.signed_volume(inner_points, facets)
    if inside <= 0 or inside >= core.signed_volume(points, facets):
        raise MeshError("A %.2f mm wall is too thick for this body." % thickness)
    inner.flipNormals()
    result = work.copy()
    result.addMesh(inner)
    return result


def _plane_side_counts(points, origin, normal):
    above = below = 0
    eps = 1e-9 * max(1.0, core.diagonal(points)) if points else 1e-9
    for p in points:
        d = core.dot(core.sub(p, origin), normal)
        if d > eps:
            above += 1
        elif d < -eps:
            below += 1
    return above, below


def plane_cut_mesh(mesh, origin, normal, cut_type="Trim", fill=core.DEFAULT_FILL, flip=False):
    """Plane Cut. `normal` points to the side Trim removes (Flip removes the other side).
    Returns (kept mesh, other half or None, face groups or None)."""
    import FreeCAD as App

    origin = tuple(origin)
    normal = core.unit(tuple(normal))
    if flip:
        normal = core.scale(normal, -1.0)
    points = [(p.x, p.y, p.z) for p in mesh.Topology[0]]
    above, below = _plane_side_counts(points, origin, normal)
    if not above or not below:
        raise MeshError(
            "The plane does not cut the body: it lies wholly on one side. Move the plane "
            "onto the body (drag the arrow or type a Distance)."
        )
    if cut_type not in core.CUT_TYPES:
        raise MeshError("Unknown cut type: %s" % cut_type)
    base, away = App.Vector(*origin), App.Vector(*normal)
    kept = mesh.copy()
    kept.trimByPlane(base, away)  # keeps the side the normal points away from
    kept.removeDuplicatedPoints()
    other = mesh.copy()
    other.trimByPlane(base, -away)
    other.removeDuplicatedPoints()
    if cut_type == "Split Faces":
        merged, groups = _join_halves(kept, other, size_of(mesh))
        return merged, None, groups
    if fill != "No Fill":
        _cap(kept, origin, normal, fill)
        if cut_type == "Split Body":
            _cap(other, origin, core.scale(normal, -1.0), fill)
    if kept.CountFacets == 0:
        raise MeshError("Nothing is left on this side: use Flip to keep the other side.")
    return kept, (other if cut_type == "Split Body" else None), None


def _join_halves(kept, other, size):
    """Split Faces: both halves as one mesh, the faces cut along the plane, each half a face
    group of its own."""
    p1, f1 = topology(kept)
    p2, f2 = topology(other)
    offset = len(p1)
    points = p1 + p2
    facets = f1 + [(a + offset, b + offset, c + offset) for a, b, c in f2]
    groups = [0] * len(f1) + [1] * len(f2)
    welded, _merged = core.weld_open_edges(points, facets, 1e-5 * max(size, 1.0))
    if len(welded) != len(facets):
        groups = None  # a face fell away while welding: the halves are not told apart
    points, welded = core.compact(points, welded)
    return from_topology(points, welded), groups


def _cap(mesh, origin, normal, fill):
    """Close the open edges a cut left on the plane (origin, normal: pointing out of `mesh`):
    Minimal uses only the cut's own points, Uniform adds even triangles inside. Islands and
    holes in the cut (a hollow part) are kept apart."""
    points, facets = topology(mesh)
    loops = core.boundary_loops(facets)
    if not loops:
        return
    size = max(core.diagonal(points), 1e-9)
    tol = 1e-5 * size
    on_plane = [
        loop
        for loop in loops
        if all(abs(core.dot(core.sub(points[i], origin), normal)) <= tol * 10 for i in loop)
    ]
    if not on_plane:
        return
    u, v = core.plane_basis(normal)
    flat = [[core.to_2d(points[i], origin, u, v) for i in loop] for loop in on_plane]
    regions = core.nest_loops_2d(flat)
    corners = []  # (2D point, mesh point index) of the cut's corners
    for loop, poly in zip(on_plane, flat):
        corners += list(zip(poly, loop))
    corner_points = [p for p, _i in corners]
    edge_len = []
    for loop in on_plane:
        for a, b in zip(loop, loop[1:] + loop[:1]):
            edge_len.append(core.length(core.sub(points[a], points[b])))
    edge_len.sort()
    spacing = edge_len[len(edge_len) // 2] if edge_len else size / 20.0
    new_facets = []
    for outer, holes in regions:
        try:
            tri_points, tris = _triangulate_region(
                [flat[outer]] + [flat[h] for h in holes], fill, spacing
            )
        except Exception as exc:
            log("cut fill fell back to one hole at a time: %s" % exc)
            for index in [outer] + holes:
                try:
                    new_facets += _orient(core.fill_loop(points, on_plane[index]), points, normal)
                except MeshError:
                    pass
            continue
        index_of = {}
        extra = []  # (2D point, new point index) not on the cut's corners
        matched = core.match_points_2d(corner_points, tri_points, tol)
        for n, (x, y) in enumerate(tri_points):
            if n in matched:
                index_of[n] = corners[matched[n]][1]
                continue
            found = len(points)
            points.append(core.add(origin, core.add(core.scale(u, x), core.scale(v, y))))
            extra.append(((x, y), found))
            index_of[n] = found
        cap = [(index_of[a], index_of[b], index_of[c]) for a, b, c in tris]
        if extra:
            facets = _split_open_edges(points, facets, on_plane, extra, origin, u, v, tol)
        new_facets += _orient(cap, points, normal)
    mesh.clear()
    mesh.addMesh(from_topology(*core.compact(points, core.drop_degenerate(facets + new_facets))))
    mesh.removeDuplicatedPoints()


def _orient(cap, points, normal):
    """Cap faces turned to face `normal`. The mesher winds all of one region's triangles the
    same way, so the region turns as a whole (a sliver's own normal could point anywhere)."""
    total = (0.0, 0.0, 0.0)
    for facet in cap:
        total = core.add(total, core.facet_normal(points, facet))
    if core.dot(total, normal) >= 0:
        return list(cap)
    return [(a, c, b) for a, b, c in cap]


def _split_open_edges(points, facets, loops, extra, origin, u, v, tol):
    """Uniform fill puts points along the cut's edges: the faces on those edges are split
    at them too, so no crack opens."""
    segments = []
    edges = []
    for loop in loops:
        for a, b in zip(loop, loop[1:] + loop[:1]):
            segments.append(
                (core.to_2d(points[a], origin, u, v), core.to_2d(points[b], origin, u, v))
            )
            edges.append((a, b))
    hits = core.segment_hits([p for p, _i in extra], segments, tol)
    if not hits:
        return facets
    by_edge = {}
    for seg, entries in hits.items():
        a, b = edges[seg]
        by_edge[(a, b)] = [extra[i][1] for _t, i in entries]
    out = []
    for facet in facets:
        a, b, c = facet
        done = False
        for u_, v_ in ((a, b), (b, c), (c, a)):
            if (u_, v_) in by_edge:
                out += core.fan_split(facet, (u_, v_), by_edge[(u_, v_)])
                done = True
                break
        if not done:
            out.append(facet)
    return out


def _triangulate_region(polys, fill, spacing):
    """Triangles over one region of the cut (outer loop + its holes, in 2D): FreeCAD's face
    mesher on a flat face made from the loops. Returns (2D points, triangles)."""
    import FreeCAD as App
    import MeshPart
    import Part

    wires = []
    for poly in polys:
        pts = [App.Vector(x, y, 0.0) for x, y in poly]
        wires.append(Part.makePolygon(pts + [pts[0]]))
    face = Part.makeFace(wires, "Part::FaceMakerBullseye")
    if face.isNull() or not face.Faces:
        raise MeshError("The cut could not be made into a face.")
    if fill == "Uniform":
        cap = MeshPart.meshFromShape(Shape=face, MaxLength=float(spacing))
        pts, tris = cap.Topology
        return [(p.x, p.y) for p in pts], [tuple(t) for t in tris]
    pts, tris = face.tessellate(1e9)
    return [(p.x, p.y) for p in pts], [tuple(t) for t in tris]


def separate_mesh(mesh, separate_type="Mesh Shells", groups=None, selected=None):
    """Separate: one mesh per shell, per face group, or one per chosen group plus the rest."""
    if separate_type == "Mesh Shells":
        parts = list(mesh.getSeparateComponents())
        parts.sort(
            key=lambda m: (
                -m.CountFacets,
                round(m.BoundBox.XMin, 6),
                round(m.BoundBox.YMin, 6),
                round(m.BoundBox.ZMin, 6),
            )
        )
        if len(parts) < 2:
            raise MeshError(
                "The body is one shell: there is nothing to separate. (Separate by face groups "
                "after Generate Face Groups, or use Plane Cut > Split Body.)"
            )
        return parts
    if not groups or core.group_count(groups) < 2:
        raise MeshError(
            "The body has one face group: use PREPARE > Generate Face Groups first, or "
            "separate by Mesh Shells."
        )
    points, facets = topology(mesh)
    if len(groups) != len(facets):
        raise MeshError("The face groups do not fit the body any more: generate them again.")
    if separate_type == "All Face Groups":
        buckets = {}
        for i, g in enumerate(groups):
            buckets.setdefault(g, []).append(facets[i])
        keys = sorted(buckets, key=lambda g: (-len(buckets[g]), g))
    else:
        chosen = set(selected or [])
        if not chosen:
            raise MeshError("Pick the face groups to separate (click them on the body).")
        buckets = {}
        for i, g in enumerate(groups):
            buckets.setdefault(g if g in chosen else -1, []).append(facets[i])
        keys = sorted(buckets, key=lambda g: (g == -1, -len(buckets[g]), g))
    parts = []
    for g in keys:
        parts.append(from_topology(*core.compact(points, buckets[g])))
    if len(parts) < 2:
        raise MeshError("All the faces are in the chosen groups: pick fewer to separate.")
    return parts


def combine_meshes(target, tools, operation="Join"):
    """Combine: Join (one body, the overlap's inside walls gone), Cut, Intersect, or Merge
    (both kept as they are in one body)."""
    if operation not in core.COMBINE_OPERATIONS:
        raise MeshError("Unknown operation: %s" % operation)
    if not tools:
        raise MeshError("Pick the tool bodies to combine with.")
    result = target.copy()
    for tool in tools:
        if operation == "Merge":
            result.addMesh(tool)
            continue
        if not result.isSolid() or not tool.isSolid():
            raise MeshError(
                "%s needs closed bodies: Repair them first (or use Merge, which keeps them as "
                "they are)." % operation
            )
        try:
            if operation == "Join":
                result = result.unite(tool)
            elif operation == "Cut":
                result = result.difference(tool)
            else:
                result = result.intersect(tool)
        except Exception as exc:
            raise MeshError("The bodies could not be combined (%s)." % exc)
        if result.CountFacets == 0:
            if operation == "Intersect":
                raise MeshError("The bodies do not overlap: Intersect leaves nothing.")
            if operation == "Cut":
                raise MeshError("The tool covers the whole target: Cut leaves nothing.")
            raise MeshError("Join gave nothing: check that both bodies are closed.")
    _orient_outward(result)
    return result


def _picked_indices(mesh, picks):
    points, facets = topology(mesh)
    quantum = max(1e-6 * size_of(mesh), 1e-9)
    found, lost = core.find_facets(points, facets, [tuple(p) for p in picks], quantum)
    return points, facets, found, lost


def _without_picked(mesh, picks):
    """(points, facets left, the original facets, how many picks were lost)."""
    if not picks:
        raise MeshError("Pick the faces first (click them on the body).")
    points, facets, found, lost = _picked_indices(mesh, picks)
    if not found:
        raise MeshError("The picked faces are no longer on the body: pick them again.")
    if len(found) >= len(facets):
        raise MeshError("That is every face of the body: use Delete on the body instead.")
    gone = set(found)
    return points, [f for i, f in enumerate(facets) if i not in gone], facets, lost


def delete_faces_mesh(mesh, picks):
    """Delete (Direct Edit): the picked faces removed, the hole they leave left open."""
    points, kept, _facets, lost = _without_picked(mesh, picks)
    return from_topology(*core.compact(points, kept)), lost


def erase_fill_mesh(mesh, picks, fill="Uniform", density=core.ERASE_DENSITY):
    """Erase and Fill: the picked faces removed and the gap they leave closed (Minimal: no
    new points; Uniform: even triangles, finer with a higher Density). Holes the body had
    before stay as they were."""
    points, kept, facets, lost = _without_picked(mesh, picks)
    before = {tuple(sorted(loop)) for loop in core.boundary_loops(facets)}
    loops = [loop for loop in core.boundary_loops(kept) if tuple(sorted(loop)) not in before]
    patch = []
    for loop in loops:
        try:
            patch += core.fill_loop(points, loop)
        except MeshError:
            continue
    if not patch:
        raise MeshError("The erased area could not be filled: pick a smaller area.")
    start = len(kept)
    joined = kept + patch
    if fill == "Uniform":
        areas = [core.facet_area(points, f) for f in kept] or [1.0]
        mean = sum(areas) / len(areas)
        edge = math.sqrt(core.erase_fill_area(mean, density) / 0.4330127018922193)
        points, joined, _done = core.split_long_edges(
            points, joined, edge, only=range(start, len(joined))
        )
    result = from_topology(*core.compact(points, core.drop_degenerate(joined)))
    _orient_outward(result)
    return result, lost


def face_groups_of(
    mesh,
    method="Fast",
    angle=core.ANGLE_THRESHOLD,
    min_size=core.MIN_GROUP_SIZE,
    tolerance=core.BOUNDARY_TOLERANCE,
):
    """Generate Face Groups: one group number per face. Fast: faces whose normals turn less
    than `angle` share a group; Accurate: faces fitting one plane, cylinder or sphere (within
    `tolerance` of the body's size) share a group, the rest by angle."""
    points, facets = topology(mesh)
    if method == "Accurate":
        groups = [-1] * len(facets)
        deviation = max(float(tolerance), 1e-6) * size_of(mesh)
        number = 0
        for surface in ("Plane", "Cylinder", "Sphere"):
            try:
                segments = mesh.getSegmentsOfType(surface, deviation, 3)
            except Exception:
                segments = []
            for segment in segments:
                free = [i for i in segment if groups[i] < 0]
                if len(free) < 3:
                    continue
                for i in free:
                    groups[i] = number
                number += 1
        rest = [i for i, g in enumerate(groups) if g < 0]
        if rest:
            sub = core.face_groups(points, [facets[i] for i in rest], angle, 0.0)
            for i, g in zip(rest, sub):
                groups[i] = number + g
        return _renumber(groups, points, facets)
    return core.face_groups(points, facets, angle, min_size)


def _renumber(groups, points, facets):
    area = {}
    for i, g in enumerate(groups):
        area[g] = area.get(g, 0.0) + core.facet_area(points, facets[i])
    order = sorted(area, key=lambda g: (-area[g], g))
    number = {g: n for n, g in enumerate(order)}
    return [number[g] for g in groups]


def tessellate_shape(shape, surface, normal_degrees, max_edge=0.0):
    """Tessellate: the triangles of a solid's faces (FreeCAD's mesher), one face group per
    face of the solid; with a Maximum Edge Length, longer edges are split (cracks never
    open: both faces on an edge split together)."""
    import MeshPart

    if shape is None or shape.isNull() or not shape.Faces:
        raise MeshError("The body has no faces to tessellate.")
    if surface <= 0 or normal_degrees <= 0:
        raise MeshError("Surface and Normal Deviation must be more than 0.")
    mesh = MeshPart.meshFromShape(
        Shape=shape,
        LinearDeflection=float(surface),
        AngularDeflection=math.radians(float(normal_degrees)),
        Relative=False,
        Segments=True,
    )
    groups = [0] * mesh.CountFacets
    for n in range(mesh.countSegments()):
        for i in mesh.getSegment(n):
            groups[i] = n
    if max_edge and max_edge > 0:
        points, facets = topology(mesh)
        points, facets, _done, groups = core.split_long_edges(
            points, facets, float(max_edge), tags=groups
        )
        mesh = from_topology(points, facets)
    return mesh, groups


# ----------------------------------------------------------------------------- the step object
def _add(obj, kind_, name, group, doc, value=None, hidden=False):
    if name in obj.PropertiesList:
        return False
    obj.addProperty(kind_, name, group, doc, 4 if hidden else 0)
    if value is not None:
        setattr(obj, name, value)
    return True


def _enum(obj, name, group, doc, values, default):
    if _add(obj, "App::PropertyEnumeration", name, group, doc):
        setattr(obj, name, list(values))
        setattr(obj, name, default)


def ensure_properties(obj, step_kind):
    """The properties of a step of this kind (added once; files from older SciForge get the
    missing ones when opened)."""
    group = KINDS.get(step_kind, ("", "Mesh"))[1] if step_kind in KINDS else "Mesh"
    if step_kind == PIECE:
        group = "Mesh"
    bodies.mark(obj, step_kind)
    _add(
        obj,
        "App::PropertyString",
        STEP_LABEL,
        "Base",
        "The step's own name in the timeline",
        hidden=True,
    )
    if step_kind == "Tessellate":
        _add(obj, "App::PropertyLink", "Source", group, "The solid body it is made from")
    else:
        _add(obj, "App::PropertyLink", "Source", group, "The mesh body as the step before left it")
    _add(obj, "App::PropertyString", "StepInfo", group, "What the step did", hidden=True)
    _add(
        obj,
        "App::PropertyIntegerList",
        "FaceGroups",
        "Mesh",
        "Face group of each face",
        hidden=True,
    )
    _add(
        obj,
        "App::PropertyColorList",
        "FaceColors",
        "Mesh",
        "Colour of each face (face groups)",
        hidden=True,
    )
    if step_kind == "MeshRepair":
        _enum(
            obj,
            "RepairType",
            group,
            "Close Holes .. Rebuild",
            core.REPAIR_TYPES,
            core.DEFAULT_REPAIR,
        )
        _enum(
            obj,
            "RebuildType",
            group,
            "How Rebuild builds the surface",
            core.REBUILD_TYPES,
            core.DEFAULT_REBUILD,
        )
        _add(
            obj,
            "App::PropertyInteger",
            "Density",
            group,
            "Rebuild cells along the longest side",
            core.REBUILD_DENSITY[2],
        )
        _add(obj, "App::PropertyDistance", "Offset", group, "Rebuild Accurate: offset", 0.0)
    elif step_kind == "MeshRemesh":
        _enum(obj, "RemeshType", group, "Adaptive or Uniform", core.REMESH_TYPES, "Adaptive")
        _add(obj, "App::PropertyFloat", "Density", group, "0 coarse .. 1 fine", core.REMESH_DENSITY)
        _add(
            obj,
            "App::PropertyFloat",
            "ShapePreservation",
            group,
            "0 .. 1 (Adaptive)",
            core.SHAPE_PRESERVATION,
        )
        _add(obj, "App::PropertyBool", "PreserveSharpEdges", group, "Keep sharp edges", False)
        _add(obj, "App::PropertyBool", "PreserveBoundaries", group, "Keep open edges", False)
    elif step_kind == "MeshReduce":
        _enum(obj, "Target", group, "What the reduction aims for", core.REDUCE_TARGETS, "Tolerance")
        _add(
            obj,
            "App::PropertyLength",
            "Tolerance",
            group,
            "Largest deviation allowed",
            core.DEFAULT_TOLERANCE,
        )
        _add(
            obj,
            "App::PropertyFloat",
            "Proportion",
            group,
            "Percent of the faces kept",
            core.DEFAULT_PROPORTION,
        )
        _add(obj, "App::PropertyInteger", "FaceCount", group, "Faces kept", 0)
        _enum(obj, "ReduceType", group, "Adaptive or Uniform", core.REDUCE_TYPES, "Adaptive")
    elif step_kind == "MeshSmooth":
        _add(obj, "App::PropertyFloat", "Smoothness", group, "0 .. 1", core.DEFAULT_SMOOTHNESS)
    elif step_kind == "MeshPlaneCut":
        _enum(obj, "CutType", group, "Trim, Split Body or Split Faces", core.CUT_TYPES, "Trim")
        _enum(obj, "FillType", group, "How the cut is closed", core.FILL_TYPES, core.DEFAULT_FILL)
        _add(obj, "App::PropertyBool", "Flip", group, "Remove the other side", False)
        _add(obj, "App::PropertyLinkSubGlobal", "Plane", group, "The plane or flat face it cuts at")
        _add(
            obj,
            "App::PropertyPlacement",
            "PlaneFrame",
            group,
            "The plane picked (kept when the plane is gone)",
            hidden=True,
        )
        _add(obj, "App::PropertyDistance", "Distance", group, "Offset from the picked plane", 0.0)
        _add(obj, "App::PropertyAngle", "AngleX", group, "Tilt about the plane's first axis", 0.0)
        _add(obj, "App::PropertyAngle", "AngleY", group, "Tilt about the plane's second axis", 0.0)
    elif step_kind == "MeshSeparate":
        _enum(
            obj,
            "SeparateType",
            group,
            "By shells or face groups",
            core.SEPARATE_TYPES,
            "Mesh Shells",
        )
        _add(obj, "App::PropertyIntegerList", "Groups", group, "Chosen face groups")
        _add(obj, "App::PropertyBool", "KeepBody", group, "Keep the original body too", False)
    elif step_kind == "MeshCombine":
        _add(obj, "App::PropertyLinkList", "Tools", group, "The tool bodies")
        _enum(
            obj,
            "Operation",
            group,
            "Join, Cut, Intersect or Merge",
            core.COMBINE_OPERATIONS,
            "Join",
        )
        _add(obj, "App::PropertyBool", "KeepTools", group, "Keep the tool bodies", False)
    elif step_kind == "MeshReverseNormal":
        _add(obj, "App::PropertyIntegerList", "Groups", group, "Face groups (none: every face)")
    elif step_kind == "MeshShell":
        _add(obj, "App::PropertyLength", "Thickness", group, "Wall thickness", core.DEFAULT_SHELL)
    elif step_kind in ("MeshEraseFill", "MeshDeleteFaces"):
        _add(obj, "App::PropertyVectorList", "Picks", group, "Centres of the picked faces")
        if step_kind == "MeshEraseFill":
            _enum(obj, "FillType", group, "Uniform or Minimal", core.ERASE_FILL_TYPES, "Uniform")
            _add(
                obj,
                "App::PropertyFloat",
                "Density",
                group,
                "0 coarse .. 1 fine",
                core.ERASE_DENSITY,
            )
    elif step_kind == "MeshFaceGroups":
        _enum(obj, "Method", group, "Fast or Accurate", core.FACE_GROUP_METHODS, "Fast")
        _add(
            obj,
            "App::PropertyAngle",
            "AngleThreshold",
            group,
            "Fast: angle between groups",
            core.ANGLE_THRESHOLD,
        )
        _add(
            obj,
            "App::PropertyFloat",
            "MinimumGroupSize",
            group,
            "Fast: fraction of the area",
            core.MIN_GROUP_SIZE,
        )
        _add(
            obj,
            "App::PropertyFloat",
            "BoundaryTolerance",
            group,
            "Accurate: fraction of the size",
            core.BOUNDARY_TOLERANCE,
        )
    elif step_kind == "Tessellate":
        _enum(
            obj,
            "Refinement",
            group,
            "Low, Medium, High or Custom",
            core.TESSELLATE_REFINEMENTS,
            "Medium",
        )
        _add(
            obj,
            "App::PropertyLength",
            "SurfaceDeviation",
            group,
            "Largest gap to the surface",
            0.0508,
        )
        _add(
            obj, "App::PropertyAngle", "NormalDeviation", group, "Largest angle between faces", 15.0
        )
        _add(obj, "App::PropertyLength", "MaximumEdgeLength", group, "0: no limit", 0.0)
    elif step_kind == PIECE:
        _add(obj, "App::PropertyInteger", "Index", group, "Which piece of its step", 0)


class MeshStep:
    """Saved in files as "sciforge.mesh.MeshStep": keep the class name and its properties."""

    def __init__(self, obj, step_kind):
        obj.Proxy = self
        ensure_properties(obj, step_kind)

    def onDocumentRestored(self, obj):
        try:
            ensure_properties(obj, kind(obj))
        except Exception as exc:
            warn("mesh step %s: %s" % (obj.Label, exc))

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads

    def execute(self, obj):
        step_kind = kind(obj)
        try:
            result, groups, info = compute(obj, step_kind)
            _set_result(obj, result)
            _set_groups(obj, groups)
            _note(obj, "")
            if obj.StepInfo != (info or ""):
                obj.StepInfo = info or ""
        except MeshError as exc:
            _pass_through(obj)
            _note(obj, str(exc))
        except Exception as exc:  # an unexpected failure: say it, never break the recompute
            warn("%s: %s" % (obj.Label, exc))
            _pass_through(obj)
            _note(obj, "This step could not be computed (%s)." % exc)


def _note(obj, text):
    if not text and WARNING not in obj.PropertiesList:
        return
    _add(
        obj, "App::PropertyString", WARNING, "Base", "Why the timeline shows a warning", hidden=True
    )
    if getattr(obj, WARNING) != text:
        setattr(obj, WARNING, text)


def problem(obj):
    """Why the step could not be done ('' when it could)."""
    return getattr(obj, WARNING, "") if obj is not None else ""


def _set_result(obj, mesh):
    import FreeCAD as App

    placement = App.Placement(obj.Placement)
    obj.Mesh = mesh
    if not placement.isIdentity():
        obj.Placement = placement  # setting the triangles resets the placement


def _set_groups(obj, groups):
    groups = list(groups) if groups and core.group_count(groups) > 1 else []
    if list(obj.FaceGroups) == groups and len(obj.FaceColors) == len(groups):
        return
    obj.FaceGroups = groups
    obj.FaceColors = [tuple(c) for c in core.group_colors(groups)] if groups else []


def _pass_through(obj):
    """A step that cannot be done shows the body as it was before it (Fusion skips a failed
    feature); a piece shows nothing."""
    import Mesh

    try:
        source = getattr(obj, "Source", None)
        if is_piece(obj) or source is None or not is_mesh(source):
            if is_piece(obj) and source is not None and obj.Mesh.CountFacets:
                return  # keep what it had: its step is only changing
            _set_result(obj, Mesh.Mesh())
            return
        _set_result(obj, global_mesh(source))
        _set_groups(obj, list(getattr(source, "FaceGroups", []) or []))
    except Exception:
        pass


def source_mesh(obj):
    source = getattr(obj, "Source", None)
    if source is None or not bodies.alive(source):
        raise MeshError("Its mesh body is gone (deleted?): edit the step and pick a body.")
    if not is_mesh(source):
        raise MeshError("%s is not a mesh body." % source.Label)
    return global_mesh(source)


def _source_groups(obj):
    source = getattr(obj, "Source", None)
    return list(getattr(source, "FaceGroups", []) or []) if source is not None else []


def held(obj):
    try:
        return _key(obj) in HOLD
    except Exception:
        return False


def hold(obj, on):
    """A dialog with Preview off: the step shows its body unchanged until OK."""
    key = _key(obj)
    if on:
        HOLD.add(key)
    else:
        HOLD.discard(key)


def compute(obj, step_kind):
    """(result mesh, face groups or None, info text) of a step."""
    if step_kind == PIECE:
        return _piece(obj)
    if step_kind == "Tessellate":
        return _tessellate(obj)
    source = source_mesh(obj)
    if bodies.is_suppressed(obj) or held(obj):
        return source, _source_groups(obj), ""
    before = source.CountFacets
    if step_kind == "MeshRepair":
        result, report = repair_mesh(
            source, obj.RepairType, obj.RebuildType, obj.Density, float(obj.Offset)
        )
        info = "%d -> %d faces. %s" % (before, result.CountFacets, report["advice"])
        return result, None, info
    if step_kind == "MeshRemesh":
        result = remesh_mesh(
            source,
            obj.RemeshType,
            obj.Density,
            obj.ShapePreservation,
            obj.PreserveSharpEdges,
            obj.PreserveBoundaries,
        )
        return result, None, "%d -> %d faces" % (before, result.CountFacets)
    if step_kind == "MeshReduce":
        result = reduce_mesh(
            source,
            obj.Target,
            float(obj.Tolerance),
            obj.Proportion,
            obj.FaceCount or None,
            obj.ReduceType,
        )
        return result, None, "%d -> %d faces" % (before, result.CountFacets)
    if step_kind == "MeshSmooth":
        return smooth_mesh(source, obj.Smoothness), _source_groups(obj), "%d faces" % before
    if step_kind == "MeshPlaneCut":
        origin, normal = cut_plane(obj)
        kept, other, groups = plane_cut_mesh(
            source, origin, normal, obj.CutType, obj.FillType, obj.Flip
        )
        cache = _cache(obj)
        cache["pieces"] = [kept, other] if other is not None else []
        return kept, groups, "%d -> %d faces" % (before, kept.CountFacets)
    if step_kind == "MeshSeparate":
        parts = separate_mesh(source, obj.SeparateType, _source_groups(obj), list(obj.Groups))
        _cache(obj)["pieces"] = parts
        return parts[0], None, "%d bodies" % len(parts)
    if step_kind == "MeshCombine":
        tools = [global_mesh(t) for t in obj.Tools if is_mesh(t)]
        result = combine_meshes(source, tools, obj.Operation)
        return result, None, "%d faces" % result.CountFacets
    if step_kind == "MeshReverseNormal":
        groups = _source_groups(obj)
        return reverse_mesh(source, groups, list(obj.Groups)), groups, "%d faces" % before
    if step_kind == "MeshShell":
        result = shell_mesh(source, float(obj.Thickness))
        return result, None, "%d faces" % result.CountFacets
    if step_kind == "MeshDeleteFaces":
        result, lost = delete_faces_mesh(source, list(obj.Picks))
        return result, None, _lost_note(before - result.CountFacets, lost)
    if step_kind == "MeshEraseFill":
        result, lost = erase_fill_mesh(source, list(obj.Picks), obj.FillType, obj.Density)
        return result, None, _lost_note(len(obj.Picks) - lost, lost)
    if step_kind == "MeshFaceGroups":
        groups = face_groups_of(
            source,
            obj.Method,
            float(obj.AngleThreshold),
            obj.MinimumGroupSize,
            obj.BoundaryTolerance,
        )
        return source, groups, "%d face groups" % core.group_count(groups)
    raise MeshError("Unknown mesh step: %s" % step_kind)


def _lost_note(done, lost):
    text = "%d faces" % done
    if lost:
        text += "; %d picked faces are gone (the body changed before this step)" % lost
    return text


def _cache(obj):
    proxy = obj.Proxy
    if not hasattr(proxy, "_cache"):
        proxy._cache = {}
    return proxy._cache


def _piece(obj):
    """A body made beside a step's own: piece `Index` of that step."""
    step = getattr(obj, "Source", None)
    if step is None or not bodies.alive(step):
        raise MeshError("The step that made this body is gone.")
    if bodies.is_suppressed(step) or bodies.is_suppressed(obj) or held(step):
        import Mesh

        return Mesh.Mesh(), None, ""
    pieces = _cache(step).get("pieces")
    if pieces is None:
        try:
            compute(step, kind(step))
        except MeshError:
            pieces = []
        pieces = _cache(step).get("pieces") or []
    index = int(obj.Index)
    if index >= len(pieces) or pieces[index] is None:
        raise MeshError("Its step makes no such piece any more.")
    return pieces[index].copy(), None, "%d faces" % pieces[index].CountFacets


def _tessellate(obj):
    source = getattr(obj, "Source", None)
    if source is None or not bodies.alive(source):
        raise MeshError("Its solid body is gone (deleted?).")
    shape = bodies.global_shape(source)
    if shape.isNull() or not shape.Faces:
        raise MeshError("%s has no faces to tessellate." % source.Label)
    surface, normal = tessellate_values(
        obj.Refinement, float(obj.SurfaceDeviation), float(obj.NormalDeviation)
    )
    mesh, groups = tessellate_shape(shape, surface, normal, float(obj.MaximumEdgeLength))
    return mesh, groups, "%d faces, %d face groups" % (mesh.CountFacets, core.group_count(groups))


def tessellate_values(refinement, surface, normal):
    """(surface deviation mm, normal deviation degrees) of a refinement preset."""
    from . import export

    if refinement in export.REFINEMENT:
        return export.REFINEMENT[refinement]
    return surface, normal


# ----------------------------------------------------------------------------- the cut plane
def plane_frame_of(reference):
    """(origin, normal, x axis or None) of a picked plane in the design: an origin plane, a
    construction plane, or a flat face (at the face's centre). None when it is none of those
    (or gone)."""
    import FreeCAD as App
    import Part

    if not reference:
        return None
    obj, subs = reference
    if obj is None:
        return None
    sub = subs[0] if isinstance(subs, (list, tuple)) and subs else (subs or "")
    if sub and sub.split(".")[-1].startswith("Face"):
        try:
            face = Part.getShape(obj, sub, needSubElement=True)
            if face.isNull() or face.ShapeType != "Face":
                return None
            if face.Surface.TypeId != "Part::GeomPlane":
                return None
            u0, u1, v0, v1 = face.ParameterRange
            normal = face.normalAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)
            return (tuple(face.CenterOfMass), tuple(normal), None)
        except Exception:
            return None
    try:
        placement = obj.getGlobalPlacement()
    except Exception:
        placement = obj.Placement
    rot = placement.Rotation
    normal = rot.multVec(App.Vector(0, 0, 1))
    u = rot.multVec(App.Vector(1, 0, 0))
    return (tuple(placement.Base), tuple(normal), tuple(u))


def cut_frame(obj):
    """The placement of a Plane Cut's plane: the picked plane (or the one remembered when it
    is gone), moved Distance along its normal, turned AngleX about its X axis and then AngleY
    about its Y axis (the frames the dialog's arrow and turning balls use)."""
    frame = None
    try:
        frame = plane_frame_of(obj.Plane)
    except Exception:
        frame = None
    if frame is not None:
        origin, normal, u = frame
        placement = frame_placement(origin, normal, u)
        if not placement.isSame(obj.PlaneFrame, 1e-12):
            obj.PlaneFrame = placement
    else:
        placement = obj.PlaneFrame
    return tilted_frame(placement, float(obj.Distance), float(obj.AngleX), float(obj.AngleY))


def cut_plane(obj):
    """(origin, normal) of a Plane Cut; the normal points to the side Trim removes."""
    import FreeCAD as App

    frame = cut_frame(obj)
    return tuple(frame.Base), core.unit(tuple(frame.Rotation.multVec(App.Vector(0, 0, 1))))


def frame_placement(origin, normal, u=None):
    import FreeCAD as App

    n = core.unit(normal)
    if u is None or abs(core.dot(core.unit(u), n)) > 1e-6:
        u, v = core.plane_basis(n)
    else:
        u = core.unit(u)
        v = core.cross(n, u)
    rot = App.Rotation(App.Vector(*u), App.Vector(*v), App.Vector(*n), "ZXY")
    return App.Placement(App.Vector(*origin), rot)


def tilted_frame(placement, distance, angle_x, angle_y):
    import FreeCAD as App

    moved = placement.multiply(App.Placement(App.Vector(0, 0, distance), App.Rotation()))
    turned = moved.multiply(App.Placement(App.Vector(), App.Rotation(App.Vector(1, 0, 0), angle_x)))
    return turned.multiply(App.Placement(App.Vector(), App.Rotation(App.Vector(0, 1, 0), angle_y)))


# ----------------------------------------------------------------------------- the look
ICONS = {
    "MeshRepair": "mesh_repair",
    "MeshRemesh": "mesh_remesh",
    "MeshReduce": "mesh_reduce",
    "MeshSmooth": "mesh_smooth",
    "MeshPlaneCut": "mesh_plane_cut",
    "MeshSeparate": "mesh_separate",
    "MeshCombine": "mesh_combine",
    "MeshReverseNormal": "mesh_reverse_normal",
    "MeshShell": "mesh_shell",
    "MeshEraseFill": "mesh_erase_fill",
    "MeshDeleteFaces": "mesh_delete_faces",
    "MeshFaceGroups": "mesh_face_groups",
    "Tessellate": "mesh_tessellate",
    PIECE: "insert_mesh",
}


class MeshStepView:
    """How a mesh step is drawn: like an inserted mesh. FreeCAD gives a Python mesh feature
    no display mode of its own (nothing was drawn), so this one names "Shaded". Saved in
    files as "sciforge.mesh.MeshStepView": keep the name."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getDefaultDisplayMode(self):
        return "Shaded"

    def getIcon(self):
        try:
            from . import ui_icon_path

            return ui_icon_path(ICONS.get(kind(self.Object), "insert_mesh"))
        except Exception:
            return ""

    def doubleClicked(self, vobj):
        try:
            from . import taskui

            taskui.edit_object(vobj.Object)
        except Exception as exc:
            warn("could not edit %s: %s" % (vobj.Object.Label, exc))
        return True

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def attach_view(obj):
    """Give a new step its look (GUI only)."""
    try:
        import FreeCAD as App

        if App.GuiUp and obj.ViewObject is not None:
            MeshStepView(obj.ViewObject)
            if obj.ViewObject.DisplayMode != "Shaded":
                obj.ViewObject.DisplayMode = "Shaded"
    except Exception as exc:
        warn("mesh step look: %s" % exc)


# ----------------------------------------------------------------------------- making steps
def _container_of(obj):
    try:
        from . import components

        return components.container_of(obj)
    except Exception:
        return None


def new_step(doc, step_kind, source, label=None):
    """A new step on the body `source` (a mesh body; for Tessellate a solid body), named after
    the body. Not yet computed."""
    import FreeCAD as App

    name = KINDS[step_kind][0] if step_kind in KINDS else "MeshPiece"
    obj = doc.addObject(STEP_TYPE, name)
    MeshStep(obj, step_kind)
    obj.Source = source
    obj.Label = label or (source.Label if source is not None else name)
    attach_view(obj)
    container = _container_of(source) if source is not None else None
    if container is not None and hasattr(container, "addObject"):
        try:
            container.addObject(obj)
        except Exception:
            pass
    _copy_look(source, obj)
    if App.GuiUp:
        log("%s step added to %s" % (KINDS.get(step_kind, (name, name))[1], obj.Label))
    return obj


def new_piece(doc, step, index, label):
    obj = doc.addObject(STEP_TYPE, "MeshPiece")
    MeshStep(obj, PIECE)
    obj.Source = step
    obj.Index = int(index)
    obj.Label = label
    bodies.add_prop(obj, "App::PropertyString", "SciForgeRole", "Base")
    obj.SciForgeRole = PIECE  # a helper: the timeline lists its step, not it
    attach_view(obj)
    container = _container_of(step)
    if container is not None and hasattr(container, "addObject"):
        try:
            container.addObject(obj)
        except Exception:
            pass
    _copy_look(step, obj)
    return obj


def pieces_of(step):
    """The pieces a step made, in order."""
    if step is None:
        return []
    found = [o for o in step.InList if is_piece(o) and getattr(o, "Source", None) is step]
    return sorted(found, key=lambda o: int(o.Index))


def piece_label(body_name, index):
    return body_name if index == 0 else "%s (%d)" % (body_name, index + 1)


def set_piece_count(step, count, body_name):
    """Make the step have `count` pieces (made or removed as needed). Returns the pieces."""
    doc = step.Document
    pieces = pieces_of(step)
    for extra in pieces[count:]:
        try:
            doc.removeObject(extra.Name)
        except Exception:
            pass
    pieces = pieces[:count]
    for index in range(len(pieces), count):
        pieces.append(new_piece(doc, step, index, piece_label(body_name, index)))
    return pieces


def _copy_look(source, obj):
    """A new step looks like the body it changes."""
    try:
        import FreeCAD as App

        if not App.GuiUp or source is None or source.ViewObject is None:
            return
        src, dst = source.ViewObject, obj.ViewObject
        if dst is None:
            return
        for prop in ("ShapeAppearance", "DisplayMode", "Transparency"):
            if prop in src.PropertiesList and prop in dst.PropertiesList:
                try:
                    setattr(dst, prop, getattr(src, prop))
                except Exception:
                    pass
    except Exception:
        pass


def apply_colours(obj):
    """Show the face groups in colour (GUI): one colour per group, plain when there is one."""
    try:
        import FreeCAD as App

        if (
            not App.GuiUp
            or obj.ViewObject is None
            or "Coloring" not in obj.ViewObject.PropertiesList
        ):
            return
        want = bool(list(getattr(obj, "FaceColors", []) or []))
        if want and len(obj.FaceColors) != obj.Mesh.CountFacets:
            want = False
        if bool(obj.ViewObject.Coloring) != want:
            obj.ViewObject.Coloring = want
        elif want:
            obj.ViewObject.Coloring = True  # new colours of the same size: draw them again
    except Exception:
        pass


# ----------------------------------------------------------------------------- bodies used up
def _used_up(step):
    k = kind(step)
    source = getattr(step, "Source", None)
    if k == PIECE:
        return [source] if source is not None else []
    if k == "MeshSeparate" and getattr(step, "KeepBody", False):
        return []
    found = [source] if source is not None else []
    if k == "MeshCombine" and not getattr(step, "KeepTools", False):
        found += [t for t in step.Tools if t is not None]
    return found


def register_consumers():
    for k in list(KINDS) + [PIECE]:
        bodies.CONSUMERS[k] = _used_up


# ----------------------------------------------------------------------------- body history
def history(obj):
    """The objects that make up a mesh body and nothing else (its steps back to its first),
    newest first: what deleting the body takes away."""
    if obj is None:
        return []
    doc = obj.Document
    chosen = [obj]
    names = {obj.Name}
    changed = True
    while changed:
        changed = False
        for item in list(chosen):
            for link in _links(item):
                if link is None or link.Name in names or not is_mesh(link):
                    continue
                users = [
                    u
                    for u in link.InList
                    if u.TypeId not in ("App::Part", "App::DocumentObjectGroup")
                ]
                if all(u.Name in names for u in users):
                    chosen.append(link)
                    names.add(link.Name)
                    changed = True
    _ = doc
    return chosen


def _links(obj):
    found = []
    source = getattr(obj, "Source", None)
    if source is not None:
        found.append(source)
    if kind(obj) == "MeshCombine":
        found += [t for t in getattr(obj, "Tools", []) if t is not None]
    return found


def delete_body(obj):
    """Delete a mesh body with the steps that made only it (the caller's undo step). Other
    bodies of the same Separate stay: their step is not the deleted body's alone."""
    doc = obj.Document
    for item in history(obj):
        if doc.getObject(item.Name) is not None:
            doc.removeObject(item.Name)


def rename_body(obj, text):
    """Rename a mesh body: every step of its history carries its name."""
    text = (text or "").strip()
    if not text:
        return False
    for item in history(obj):
        if item.Label != text:
            item.Label = text
    return True


class _ChainWatch:
    """A step deleted from the middle of a body's history: the step after it reads the body
    from the step before it (Fusion recomputes the later features on what is left). Done in
    the delete's own undo step, before FreeCAD drops the links."""

    def slotDeletedObject(self, obj):
        try:
            doc = obj.Document
            if (
                doc is None
                or getattr(doc, "Transacting", False)
                or getattr(doc, "Restoring", False)
            ):
                return
            if not is_mesh(obj) and not is_step(obj):
                return
            before = getattr(obj, "Source", None) if is_step(obj) else None
            for user in list(obj.InList):
                if not is_step(user) or getattr(user, "Source", None) is not obj:
                    continue
                if before is not None and is_mesh(before):
                    user.Source = before
            for user in list(obj.InList):
                if kind(user) == "MeshCombine" and obj in user.Tools:
                    user.Tools = [t for t in user.Tools if t is not obj]
        except Exception as exc:
            warn("mesh history: %s" % exc)


_WATCH = {"observer": None}


def install_watch():
    import FreeCAD as App

    if _WATCH["observer"] is None:
        _WATCH["observer"] = _ChainWatch()
        App.addDocumentObserver(_WATCH["observer"])


# ----------------------------------------------------------------------------- the section sketch
def section_polylines(mesh, origin, normal, tolerance):
    """Where the plane cuts the mesh, as simplified polylines ([[points]], closed ones end
    where they start)."""
    import FreeCAD as App

    sections = mesh.crossSections([(App.Vector(*origin), App.Vector(*normal))], 1e-4, True)
    lines = []
    for polyline in sections[0] if sections else []:
        pts = [(p.x, p.y, p.z) for p in polyline]
        if len(pts) < 2:
            continue
        closed = core.length(core.sub(pts[0], pts[-1])) <= tolerance
        if closed:
            body = pts[:-1]
            simple = core.simplify_polyline(body, tolerance, closed=True)
            if len(simple) >= 3:
                lines.append(simple + [simple[0]])
        else:
            simple = core.simplify_polyline(pts, tolerance)
            if len(simple) >= 2:
                lines.append(simple)
    return lines


def section_into_sketch(sketch, mesh, fixed=True):
    """Put the section of `mesh` by the sketch's plane into the sketch as lines (fixed, like
    an inserted drawing). Returns the number of lines."""
    import FreeCAD as App
    import Part
    import Sketcher

    placement = (
        sketch.getGlobalPlacement() if hasattr(sketch, "getGlobalPlacement") else sketch.Placement
    )
    origin = tuple(placement.Base)
    normal = tuple(placement.Rotation.multVec(App.Vector(0, 0, 1)))
    tolerance = max(size_of(mesh) * 2e-4, 1e-4)
    lines = section_polylines(mesh, origin, normal, tolerance)
    if not lines:
        raise MeshError("The plane does not cut the body: move it onto the body.")
    inverse = placement.inverse()
    geometry = []
    for polyline in lines:
        local = [inverse.multVec(App.Vector(*p)) for p in polyline]
        for a, b in zip(local, local[1:]):
            a2, b2 = App.Vector(a.x, a.y, 0), App.Vector(b.x, b.y, 0)
            if (a2 - b2).Length > 1e-7:
                geometry.append(Part.LineSegment(a2, b2))
    first = sketch.GeometryCount
    sketch.addGeometry(geometry, False)
    if fixed:
        sketch.addConstraint(
            [Sketcher.Constraint("Block", first + i) for i in range(len(geometry))]
        )
    return len(geometry)


# ----------------------------------------------------------------------------- export
def exportable(doc, names=None, shown_only=True):
    """Mesh bodies for Export / 3D Print: the shown ones, or those named."""
    found = []
    for obj in mesh_bodies(doc):
        if names is not None and obj.Name not in names:
            continue
        if names is None and shown_only and not bodies.is_shown(obj):
            continue
        if obj.Mesh.CountFacets:
            found.append(obj)
    return found


try:
    register_consumers()
except Exception:  # pragma: no cover - bodies needs FreeCAD
    pass
