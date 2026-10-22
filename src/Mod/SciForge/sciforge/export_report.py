# SPDX-License-Identifier: LGPL-2.1-or-later
"""What an export leaves out and what an import skipped, counted from the real design
(needs FreeCAD; headless is enough). The sentences and the format rules are in
export_report_core.py (pure, unit tested); the message on screen is export_report_ui.py.

For the AI tools and scripts (one call, no window needed):

    from sciforge import export_report
    export_report.losses(doc, None, "STL (Binary)")   # whole design
    export_report.losses(doc, [body1, body2], "STEP")  # chosen bodies
    export_report.losses(doc, export.exportable_bodies(doc), "STEP", whole=True)
        # the bodies a whole-design export took (Export Everything, the AI tool's mesh
        # exports): the hidden ones are reported too
    export_report.losses(doc, component, "3MF")        # a component
    export_report.losses(doc, sketch, "DXF")           # a sketch (or (body, "Face3"))
    export_report.losses(doc, page, "drawing_dxf", which="current")   # a drawing
    -> [{"key": "timeline", "count": 6, "text": "the timeline (6 steps): ..."}, ...]

The counts follow exactly what each export path writes (exchange.py, export.py,
drawing.py): the same bodies, the same shown / hidden rules, the same structure.
"""

import os

from . import export_report_core as core
from . import log, warn

# Types of the steps that only hold a shape brought in from a file (no history to lose).
SHAPE_ONLY_STEPS = ("InsertSTEP", "InsertMesh")
DIMENSION_TYPES = ("Distance", "DistanceX", "DistanceY", "Radius", "Diameter", "Angle")
HELPER_CONSTRAINTS = ("InternalAlignment", "Block")
MAX_TOPOLOGY_FACETS = 2000000  # open-edge counting is plain Python: skipped beyond this
# The validity check of an imported part (OpenCASCADE's BRepCheck) costs about 5 ms a face:
# on a plate with 324 holes it took longer than reading the file. Only this many faces per
# import are checked (small parts, where it is cheap); bigger parts are not looked at, so
# the import report never makes Open / Insert STEP noticeably slower.
MAX_VALIDITY_FACES = 300


# ==================================================================== exports
def losses(doc, objects=None, fmt="STEP", purpose="file", **options):
    """What a file of type `fmt` will not keep of `objects` (None: the whole design as
    File > Export writes it; a list of bodies; a component; a sketch or (object, "FaceN")
    for DXF; a drawing page for "drawing_pdf" / "drawing_dxf"). options: unit, per_body,
    level / surface / normal (mesh refinement), which ("all" / "current" sheets).
    Returns [{"key", "count", "text"}], empty when nothing is lost."""
    return core.items(fmt, facts(doc, objects, fmt, **options), purpose)


def facts(doc, objects=None, fmt="STEP", **options):
    """The counts export_report_core.items reads (see losses)."""
    key = core.format_key(fmt)
    if key in core.FLAT_FORMATS:
        return flat_facts(objects)
    if key in core.DRAWING_FORMATS:
        return drawing_facts(objects, options.get("which", "all"))
    return design_facts(doc, objects, key, **options)


# -- what goes into a 3D file ----------------------------------------------------------------
def _scope_of(objects):
    from . import components

    if objects is None:
        return "design", None, None
    if not isinstance(objects, (list, tuple)):
        if components.is_component(objects):
            return "component", objects, None
        objects = [objects]
    return "bodies", None, [o for o in objects if o is not None]


def _consumed(doc):
    """Bodies a step uses up (a Combine's tools...): hidden, but not hidden by the user."""
    from . import bodies

    for name in ("combine", "mesh", "extrude_bodies"):
        try:
            __import__("sciforge." + name)
        except Exception:
            pass
    try:
        return bodies.consumed(doc)
    except Exception:
        return set()


def _rolled(obj):
    return bool(getattr(obj, "SciForgeRolledHidden", False))


def _in_instance(obj):
    """True when `obj` sits in a copy (instance) of a component: STEP writes the copy as a
    second occurrence of its source, not its own bodies."""
    from . import components, instances

    try:
        for parent in components.ancestors(obj):
            if instances.is_instance(parent):
                return True
    except Exception:
        pass
    return False


def _candidates(doc, scope, target, meshes):
    """Every body that could be exported in the scope (solid bodies, and mesh bodies when
    `meshes`), minus the ones a step used up or the history marker hides."""
    from . import bodies, components, export

    used = _consumed(doc)
    if scope == "component":
        found = components.bodies_in(doc, target, recursive=True)
    else:
        found = bodies.list_bodies(doc)
    out = [b for b in found if bodies.has_solid(b) and b.Name not in used and not _rolled(b)]
    if meshes:
        try:
            from . import mesh

            for obj in mesh.exportable(doc, shown_only=False):
                if obj.Name in used or _rolled(obj):
                    continue
                if scope == "component" and not components.is_inside(obj, target):
                    continue
                if export.can_export(obj):
                    out.append(obj)
        except Exception as exc:
            log("export report: mesh bodies not counted (%s)" % exc)
    return out


def _step_written(doc, scope, target):
    """(bodies STEP writes, components hidden with their bodies, [components written]) for
    the whole design or a component, exactly as exchange._mirror_document walks it."""
    from . import bodies, components, exchange, instances

    written, hidden_comps, comps = [], [], []

    def walk(comp, check_self=True):
        if check_self and not bodies.is_shown(comp):
            hidden_comps.append(comp)
            return
        comps.append(comp)
        if instances.is_instance(comp):
            return  # an occurrence of its source
        written.extend(exchange.solid_bodies_in(doc, comp, True))
        for child in components.components_in(doc, comp):
            walk(child)

    if scope == "component":
        walk(target, check_self=False)
    else:
        written.extend(exchange.solid_bodies_in(doc, None, True))
        for comp in components.components_in(doc, None):
            walk(comp)
    return written, hidden_comps, comps


def _written(doc, key, scope, target, chosen):
    """(bodies the export writes, components hidden with their bodies)."""
    from . import bodies, exchange, export

    if scope == "bodies":
        if key in core.EXACT_FORMATS:
            return [b for b in chosen if not export.is_mesh_body(b) and bodies.has_solid(b)], []
        return [b for b in chosen if export.can_export(b)], []
    if key == "step":
        written, hidden_comps, _comps = _step_written(doc, scope, target)
        return written, hidden_comps
    if key in ("iges", "brep"):
        return exchange._bodies_of_scope(doc, scope, target), []
    if scope == "component":
        return exchange.mesh_bodies_of(doc, target), []
    return export.exportable_bodies(doc), []


def design_facts(doc, objects=None, fmt="step", unit="Millimeter", per_body=False, **options):
    """Counts for a STEP / IGES / STL / 3MF / OBJ export of `objects` (see losses)."""
    from . import bodies, components, export

    key = core.format_key(fmt)
    scope, target, chosen = _scope_of(objects)
    meshes_allowed = key not in core.EXACT_FORMATS
    written, hidden_comps = _written(doc, key, scope, target, chosen)
    names = {b.Name for b in written}
    solids = [b for b in written if not export.is_mesh_body(b)]
    mesh_bodies = [b for b in written if export.is_mesh_body(b)]
    out = {
        "scope": scope,
        "solids": len(solids),
        "mesh_bodies": len(mesh_bodies),
        "unit": unit or "Millimeter",
        "per_body": bool(per_body),
        "colours_written": False,
        # body by body (Selected bodies, Export Everything): a STEP holds no components
        "flat": scope == "bodies",
    }
    # left out
    if scope == "bodies":
        out["meshes"] = len([b for b in chosen if export.is_mesh_body(b)])
        surface_list = [b for b in chosen if _is_surface(b)]
        if options.get("whole"):
            # the bodies are what a whole-design export took (Export Everything, the AI
            # tools: export.exportable_bodies): the shown ones; the others are left out
            given = {b.Name for b in chosen}
            out["hidden"] = len(
                [b for b in _candidates(doc, "design", None, True) if b.Name not in given]
            )
            surface_list = [
                b for b in bodies.list_bodies(doc) if _is_surface(b) and bodies.is_shown(b)
            ]
            out["scope"] = "design"
    else:
        hidden_inside = set()
        for comp in hidden_comps:
            for b in components.bodies_in(doc, comp, recursive=True):
                hidden_inside.add(b.Name)
        candidates = _candidates(doc, scope, target, meshes_allowed)
        if key == "step":
            candidates = [b for b in candidates if not _in_instance(b)]
        out["hidden"] = len(
            [b for b in candidates if b.Name not in names and b.Name not in hidden_inside]
        )
        out["hidden_components"] = len(hidden_comps)
        if not meshes_allowed:
            try:
                from . import mesh

                found = mesh.exportable(doc)
                if scope == "component":
                    found = [m for m in found if components.is_inside(m, target)]
                out["meshes"] = len(found)
            except Exception:
                out["meshes"] = 0
        if scope == "component":
            pool = components.bodies_in(doc, target, recursive=True)
        else:
            pool = bodies.list_bodies(doc)
        surface_list = [b for b in pool if _is_surface(b) and bodies.is_shown(b)]
    out["surfaces"] = len(surface_list)
    # how it was made
    history_scope = out["scope"]
    in_scope = _scope_bodies(doc, history_scope, target, chosen)
    steps = _steps(doc, history_scope, target, in_scope)
    out["timeline"] = len(steps)
    out["sketches"] = len([o for o in steps if o.TypeId == "Sketcher::SketchObject"])
    out["construction"] = len([o for o in steps if _is_datum(o)])
    out["parameters"] = _parameter_count(doc, None if history_scope == "design" else steps)
    out["joints"] = _joint_count(doc) if history_scope == "design" else 0
    # structure
    comps = set()
    for body in written:
        try:
            for parent in components.ancestors(body):
                comps.add(parent.Name)
        except Exception:
            pass
    out["components"] = len(comps)
    if key == "step":
        out["names_lost"] = step_names_lost(doc, scope, target)
    elif key == "iges":
        out["names_lost"] = iges_names_lost(solids)
    elif key == "brep":
        out["names_lost"] = len(solids)  # one compound of solids: no names at all
    if key == "step":
        try:
            import FreeCAD as App

            out["colours_written"] = bool(App.GuiUp)
        except Exception:
            pass
    # looks and the rest
    looks, see_through, materials = _looks(solids)
    out["looks"] = looks
    out["see_through"] = see_through
    out["materials"] = materials
    out["threads"] = _cosmetic_threads(doc, {b.Name for b in solids})
    out["pictures"] = _pictures(doc, history_scope, {b.Name for b in solids})
    if key in core.MESH_FORMATS:
        out["open_meshes"] = _open_meshes(mesh_bodies)
        out["curved"] = _curved_faces(solids)
        try:
            out["deviation"] = export.refinement_values(
                options.get("level", export.DEFAULT_REFINEMENT),
                options.get("surface"),
                options.get("normal"),
            )[0]
        except Exception:
            out["deviation"] = None
    return out


def _is_surface(body):
    try:
        from . import surface

        return surface.is_surface_body(body)
    except Exception:
        return False


def _scope_bodies(doc, scope, target, chosen):
    """{body names} whose steps the file leaves out (the design: every body)."""
    from . import bodies, components

    if scope == "design":
        return None
    if scope == "component":
        return {b.Name for b in components.bodies_in(doc, target, recursive=True)}
    return {b.Name for b in chosen if bodies.is_body(b)}


def _steps(doc, scope, target, in_scope):
    """The timeline steps whose history the file leaves out: real features (not the
    components themselves, not the shape a STEP / mesh file brought in)."""
    from . import bodies, components, timeline_ops

    out = []
    try:
        rows = timeline_ops.steps(doc)
    except Exception as exc:
        log("export report: timeline not read (%s)" % exc)
        return out
    bases = base_features(doc)
    for obj, body in rows:
        try:
            if components.is_component(obj) or bodies.kind(obj) in SHAPE_ONLY_STEPS:
                continue
            if obj.Name in bases:
                continue  # the shape a body starts from (an imported STEP part)
            if obj.TypeId in ("Mesh::Feature", "Mesh::FeaturePython") and not bodies.kind(obj):
                continue
            if in_scope is not None:
                owner = body if body is not None else bodies.body_of(obj)
                if owner is None or owner.Name not in in_scope:
                    if scope != "component" or not components.is_inside(obj, target):
                        continue
            out.append(obj)
        except Exception:
            continue
    return out


def base_features(doc):
    """{names} of the shapes bodies start from (Body.BaseFeature: what Open / Insert
    STEP brought in): a shape, not a step of history."""
    from . import bodies

    found = set()
    for body in bodies.list_bodies(doc):
        base = getattr(body, "BaseFeature", None)
        if base is not None:
            found.add(base.Name)
    return found


def _is_datum(obj):
    try:
        from . import construct

        return obj.TypeId in construct.DATUM_TYPES or bool(getattr(obj, construct.PROP_KEY, ""))
    except Exception:
        return obj.TypeId in ("PartDesign::Plane", "PartDesign::Line", "PartDesign::Point")


def _parameter_count(doc, steps=None):
    """The user's parameters whose values the file has built in: all of them for the whole
    design; for some bodies or a component, the ones the steps in that scope use (through
    their formulas, and the parameters those formulas use in turn)."""
    try:
        import re

        from . import parameters

        own = parameters.own_names(doc)
        if steps is None or not own:
            return len(own)
        container = parameters.container(doc)
        holder = parameters.core.CONTAINER
        reference = re.compile(
            r"(?<![A-Za-z0-9_.])(?:<<%s>>|%s)\.([A-Za-z_][A-Za-z0-9_]*)"
            % (re.escape(holder), re.escape(holder))
        )
        used = set()
        for obj in steps:
            for _path, expr in getattr(obj, "ExpressionEngine", None) or []:
                used.update(reference.findall(expr))
        # a parameter's formula ("depth = width / 4") names the others without the holder
        formulas = dict(container.ExpressionEngine) if container is not None else {}
        todo = list(used)
        while todo:
            name = todo.pop()
            expr = formulas.get(name, "")
            for other in own:
                if other not in used and re.search(
                    r"(?<![A-Za-z0-9_.])%s(?![A-Za-z0-9_])" % re.escape(other), expr
                ):
                    used.add(other)
                    todo.append(other)
        return len([n for n in own if n in used])
    except Exception:
        return 0


def _joint_count(doc):
    try:
        from . import joints

        return len([o for o in doc.Objects if getattr(o, "SciForgeType", "") in joints.JOINT_TYPES])
    except Exception:
        return 0


def _looks(solids):
    """(bodies with a colour, bodies with a see-through look, bodies with a physical
    material of their own)."""
    from . import appearance

    looks = see = mats = 0
    for body in solids:
        try:
            data = appearance.get(body)
            entries = [data.get("body"), data.get("material")] + [
                f.get("look") for f in data.get("faces") or []
            ]
            entries = [e for e in entries if e]
            if entries:
                looks += 1
            if any(float(e.get("transparency", 0.0) or 0.0) > 0.0 for e in entries):
                see += 1
        except Exception:
            pass
        try:
            from . import material

            if material.key_of(body):
                mats += 1
        except Exception:
            pass
    return looks, see, mats


def _cosmetic_threads(doc, names):
    try:
        from . import bodies, thread

        count = 0
        for obj in doc.Objects:
            if not thread.is_thread(obj) or bool(getattr(obj, "Modeled", False)):
                continue
            body = bodies.body_of(obj)
            if body is not None and body.Name in names and bodies.is_active_step(obj):
                count += 1
        return count
    except Exception:
        return 0


def _pictures(doc, scope, names):
    from . import bodies

    count = 0
    try:
        from . import decal

        for obj in doc.Objects:
            if bodies.kind(obj) != decal.TYPE:
                continue
            body = bodies.body_of(obj)
            target = getattr(obj, "Body", None) or getattr(obj, "Target", None)
            owner = body or (target if bodies.is_body(target) else None)
            if (owner is not None and owner.Name in names) or (owner is None and scope == "design"):
                count += 1
    except Exception:
        pass
    if scope == "design":
        try:
            from . import insert

            count += len(insert.canvases(doc))
        except Exception:
            pass
    return count


def _open_meshes(mesh_bodies):
    """Mesh bodies written as they are whose triangles do not close (a solid is meshed
    closed; a mesh body keeps its holes)."""
    count = 0
    for obj in mesh_bodies:
        try:
            if not obj.Mesh.isSolid():
                count += 1
        except Exception:
            continue
    return count


def _curved_faces(solids):
    """Faces that are not flat. A face's kind does not depend on where the body sits, so the
    shape is read as it is (no copy moved into design coordinates: on a big design those
    copies cost more than the count)."""
    count = 0
    for body in solids:
        try:
            for face in body.Shape.Faces:
                if face.Surface.TypeId == "Part::GeomPlane":
                    continue
                try:
                    if face.findPlane() is not None:
                        continue
                except Exception:
                    pass
                count += 1
        except Exception:
            continue
    return count


# What FreeCAD's IGES writer names the one product of an IGES file: the throw-away document
# exchange.py writes it from (IGES has no assemblies; a single body comes back named so).
IGES_PRODUCT = "SciForgeExportCAD"


def iges_names_lost(solids):
    """How many bodies an IGES export does not give back under their own name: the file
    holds one unnamed product, read back as Body1, Body2 ... (one body: named after the
    product), in the order they were written."""
    from . import exchange_core as xcore

    labels = xcore.body_labels(len(solids), True, IGES_PRODUCT)
    return sum(1 for body, label in zip(solids, labels) if body.Label != label)


def step_names_lost(doc, scope, target):
    """How many bodies a STEP export does not give back under their own name (opened again
    in SciForge or Fusion they are Body1, Body2 ... in their component; a single body at
    the design's root keeps its name). Follows exchange._mirror_document and
    exchange_core.body_labels, the code that writes and reads the file."""
    from . import exchange
    from . import exchange_core as xcore

    if scope == "bodies":
        return 0  # each body is a part named after it
    lost = [0]

    def count(body_list, at_root, part_name):
        labels = xcore.body_labels(len(body_list), at_root, part_name)
        lost[0] += sum(1 for body, label in zip(body_list, labels) if body.Label != label)

    def unit(plan, at_root, as_top_part=False):
        comp = doc.getObject(plan["id"])
        if comp is None or plan["as"] in ("skip", "link"):
            return
        body_list = exchange.solid_bodies_in(doc, comp, True)
        if plan["as"] == "part":
            count(body_list, at_root and as_top_part, comp.Label if as_top_part else None)
        else:
            count(body_list, at_root, None)
            for child in plan["children"]:
                unit(child, False)

    if scope == "component":
        plans = xcore.mirror_plan(exchange._units(doc, [target], True, check_self=False))
        for plan in plans:
            unit(plan, True, as_top_part=True)
        return lost[0]
    from . import components

    units = exchange._units(doc, components.components_in(doc, None), True)
    plans = xcore.mirror_plan(units)
    root = exchange.solid_bodies_in(doc, None, True)
    if not any(p["as"] != "skip" for p in plans):
        if len(root) == 1:
            return 0
        count(root, True, None)
        return lost[0]
    count(root, True, None)
    for plan in plans:
        unit(plan, False)
    return lost[0]


# -- a sketch or a face as DXF ---------------------------------------------------------------
def flat_facts(target):
    """Counts for Save As DXF of a sketch ((sketch, "") or the sketch) or a flat face."""
    if isinstance(target, (list, tuple)):
        obj, sub = (target[0], target[1]) if len(target) > 1 else (target[0], "")
    else:
        obj, sub = target, ""
    if obj is None or sub or getattr(obj, "TypeId", "") != "Sketcher::SketchObject":
        return {}
    return sketch_facts(obj)


def sketch_facts(sketch):
    """What a sketch has that its DXF does not: dimensions, constraints, construction
    curves, points, projected curves, and its place in 3D."""
    out = {"dimensions": 0, "constraints": 0, "construction_curves": 0, "points": 0}
    helpers = set()
    try:
        for c in sketch.Constraints:
            if c.Type in HELPER_CONSTRAINTS:
                helpers.add(c.First)
                continue
            if c.Type in DIMENSION_TYPES:
                out["dimensions"] += 1
            else:
                out["constraints"] += 1
    except Exception:
        pass
    try:
        for i, geo in enumerate(sketch.Geometry):
            if i in helpers:
                continue
            point = geo.TypeId == "Part::GeomPoint"
            construction = bool(sketch.getConstruction(i))
            if construction and not point:
                out["construction_curves"] += 1
            elif point and not construction:
                out["points"] += 1
    except Exception:
        pass
    out["projected"] = _reference_curves(sketch)
    try:
        out["off_plane"] = not sketch.getGlobalPlacement().isIdentity()
    except Exception:
        out["off_plane"] = False
    return out


def _reference_curves(sketch):
    """Projected curves the DXF does not get: the ones that are only references. Curves
    projected as "defining" (SciForge's Project and Auto project) are part of the sketch's
    shape and are written. Counts curves, not the edges or faces they were projected from."""
    try:
        import Sketcher

        count = 0
        for geometry in list(sketch.ExternalGeo)[2:]:  # the first two are the sketch axes
            try:
                if geometry.TypeId == "Part::GeomPoint":
                    continue
                if Sketcher.ExternalGeometryFacade(geometry).testFlag("Defining"):
                    continue
                count += 1
            except Exception:
                continue
        return count
    except Exception:
        return 0


# -- a drawing -------------------------------------------------------------------------------
def drawing_facts(page, which="all"):
    """Counts for a drawing's Export PDF / DXF (all sheets, or the current one)."""
    from . import drawing

    out = {}
    if page is None:
        return out
    try:
        from . import drawing_sheets

        every = drawing_sheets.sheets(page)
    except Exception:
        every = [page]
    pages = every if which == "all" else [page]
    out["sheets_left"] = max(0, len(every) - len(pages))
    hidden = dims = symbols = tables = curves = hatched = texts = 0
    for sheet in pages:
        try:
            if bool(drawing._get(sheet, "SciForgeTitleBlock", True)):
                texts += 1
        except Exception:
            pass
        for view in drawing.all_views(sheet):
            try:
                if not drawing._get(view, "Visibility", True):
                    hidden += 1
                    continue
                curves += _view_curves(view)
                if _hatched(view):
                    hatched += 1
            except Exception:
                continue
        for obj in drawing.annotations(sheet):
            try:
                kind = drawing.kind(obj)
                if obj.TypeId == drawing.DIMENSION:
                    dims += 1
                elif obj.TypeId == drawing.BALLOON:
                    symbols += 1
                elif kind == "PartsList":
                    tables += 1
                elif kind == "DrawingAnnotation":
                    if _annotation_kind(obj) in ("ordinate", "baseline", "chain"):
                        dims += 1
                    else:
                        symbols += 1
                texts += 1
            except Exception:
                continue
    out.update(
        {
            "hidden_views": hidden,
            "drawing_dimensions": dims,
            "symbols": symbols,
            "tables": tables,
            "curves": curves,
            "hatching": hatched,
            "texts": texts,
        }
    )
    return out


def _annotation_kind(obj):
    try:
        from . import drawing_annot

        return drawing_annot.annotation_data(obj).get("kind")
    except Exception:
        return None


def _view_curves(view):
    """Edges the drawing DXF writes as short straight lines (drawing._dxf_edge: what is
    not a line, a circle or an arc)."""
    import Part

    from . import drawing

    edges = []
    try:
        edges += list(view.getVisibleEdges(True))
    except Exception:
        pass
    if drawing._get(view, "HardHidden", False):
        try:
            edges += list(view.getHiddenEdges(True))
        except Exception:
            pass
    count = 0
    for edge in edges:
        curve = edge.Curve
        if isinstance(curve, Part.Circle) or curve.__class__.__name__ in ("Line", "LineSegment"):
            continue
        count += 1
    return count


def _hatched(view):
    from . import drawing

    if drawing.is_section(view):
        return (
            view.TypeId == drawing.SECTION and drawing._get(view, "CutSurfaceDisplay", "") != "Hide"
        )
    try:
        return bool(drawing.has_breakout(view))
    except Exception:
        return False


# ==================================================================== imports
def mesh_import_facts(path, mesh, unit=None):
    """What is wrong with or left out of a mesh file brought in by Insert Mesh."""
    out = {}
    try:
        if mesh.CountFacets <= MAX_TOPOLOGY_FACETS:
            single, many = core.open_edges(mesh.Topology[1])
            out["open_edges"], out["non_manifold"] = single, many
    except Exception as exc:
        log("import report: edges not checked (%s)" % exc)
    try:
        out["flipped"] = int(mesh.countNonUniformOrientedFacets())
    except Exception:
        pass
    try:
        out["pieces"] = int(mesh.countComponents())
    except Exception:
        pass
    ext = os.path.splitext(path or "")[1].lower()
    try:
        if ext == ".3mf":
            import zipfile

            with zipfile.ZipFile(path) as archive:
                for name in archive.namelist():
                    if name.lower().endswith(".model"):
                        found = core.three_mf_facts(archive.read(name).decode("utf-8", "replace"))
                        out["objects"] = out.get("objects", 0) + found["objects"]
                        out["colours"] = out.get("colours", False) or found["colours"]
                        out["file_unit"] = found["file_unit"]
        elif ext == ".obj":
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                out["colours"] = core.obj_has_colours(handle.read())
    except Exception as exc:
        log("import report: %s not looked into (%s)" % (os.path.basename(path), exc))
    if unit:
        out["unit"] = unit
    return out


def mesh_import_items(path, mesh, unit=None):
    return core.mesh_items(mesh_import_facts(path, mesh, unit))


def shape_notes(shape, notes):
    """Add to `notes` what step_import leaves out of a part's shape: faces that are not
    part of its solids (when it has solids, only those come in) and loose curves and
    points (only solids and faces come in)."""
    if notes is None or shape is None:
        return
    try:
        import Part

        faces = shape.Faces
        solids = shape.Solids
        if solids:
            in_solids = sum(len(s.Faces) for s in solids)
            notes["loose_faces"] = notes.get("loose_faces", 0) + max(0, len(faces) - in_solids)
        face_edges = len(Part.makeCompound(faces).Edges) if faces else 0
        loose_edges = max(0, len(shape.Edges) - face_edges)
        loose_points = 0
        if not shape.Edges and shape.Vertexes:
            loose_points = len(shape.Vertexes)
        notes["loose_curves"] = notes.get("loose_curves", 0) + loose_edges + loose_points
    except Exception as exc:
        log("import report: a part was not looked into (%s)" % exc)


def piece_notes(pieces, notes):
    """Add the sewn surface bodies and the shapes with errors of a part's pieces. The
    validity check stops after MAX_VALIDITY_FACES faces per import (notes["_faces_checked"]
    keeps the count): it is the slow part of reading a big file."""
    if notes is None:
        return
    for shape, _colours, surface in pieces:
        try:
            if surface:
                notes["sewn"] = notes.get("sewn", 0) + 1
            faces = len(shape.Faces)
            checked = notes.get("_faces_checked", 0)
            if checked + faces > MAX_VALIDITY_FACES:
                continue
            notes["_faces_checked"] = checked + faces
            if not shape.isValid():
                notes["invalid"] = notes.get("invalid", 0) + 1
        except Exception:
            continue


def cad_import_items(notes):
    return core.cad_items(notes or {})


def curve_import_items(path, notes):
    kind = "svg" if (path or "").lower().endswith(".svg") else "dxf"
    return core.curve_items(notes or {}, kind)


# ==================================================================== the message
def describe(file_name, entries, verb="Not in"):
    """The one line of a report (log, AI tools)."""
    return core.summary(file_name, entries, verb)


def log_report(file_name, entries, verb="Not in"):
    line = core.summary(file_name, entries, verb)
    if line:
        log(line)
    return line


def safe_losses(*args, **kwargs):
    """losses() that never raises (export paths call it after the file is written: a
    report that cannot be made must not turn a good export into a failure)."""
    try:
        return losses(*args, **kwargs)
    except Exception as exc:
        warn("export report: not made (%s)" % exc)
        return []
