# SPDX-License-Identifier: LGPL-2.1-or-later
"""AI actions for designs and files: undo / redo, new / open / save / save as / close /
list / switch designs, export to every format SciForge writes and insert (import) files,
with the same code as File > Open, Export and the INSERT menu (exchange.py, export.py,
step_import.py, insert.py, design_insert.py)."""

import os

import FreeCAD as App

from .. import bridge_core, executor
from ..executor import UserError, json_result, summary
from . import action

MESH_LABELS = {"stl": "STL (Binary)", "stl_ascii": "STL (ASCII)", "3mf": "3MF", "obj": "OBJ"}
MESH_UNITS = {"mm": "Millimeter", "cm": "Centimeter", "m": "Meter", "in": "Inch", "ft": "Foot"}


def mark_modified(doc):
    if doc is not None:
        executor.MODIFIED.add(doc.Name)


def is_modified(ctx, doc):
    if ctx.host.gui:
        try:
            import FreeCADGui as Gui

            gdoc = Gui.getDocument(doc.Name)
            return bool(gdoc is not None and gdoc.Modified)
        except Exception:
            return False
    return doc.Name in executor.MODIFIED or not doc.FileName


def _check_overwrite(ctx, path, own=None):
    from ... import versions

    if os.path.exists(path) and not (own and versions.same_path(path, own)):
        if not ctx.host.confirm_overwrite(path):
            raise UserError(ctx.host.refuse_overwrite_text(path))


# -- undo / redo ------------------------------------------------------------------------------
def _undo_redo(ctx, which):
    doc = ctx.need_doc()
    names = doc.UndoNames if which == "undo" else doc.RedoNames
    if not names:
        raise UserError("There is nothing to %s." % which)
    getattr(doc, which)()
    doc.recompute()
    ctx.host.after_change(doc)
    mark_modified(doc)
    return bridge_core.result("%s: %s. %s" % (which.capitalize(), names[0], summary(doc)))


@action("undo")
def undo(ctx, args):
    return _undo_redo(ctx, "undo")


@action("redo")
def redo(ctx, args):
    return _undo_redo(ctx, "redo")


# -- saving -----------------------------------------------------------------------------------
@action("save")
def save(ctx, args):
    from ... import versions

    doc = ctx.need_doc()
    path = args.get("path")
    if not path:
        if not doc.FileName:
            raise UserError(
                "This design has never been saved: give a path ending in .FCStd, or the person "
                "saves it in SciForge."
            )
        written = ctx.host.save(doc, None)
        executor.MODIFIED.discard(doc.Name)
        return bridge_core.result("Saved %s." % written)
    path = os.path.abspath(path)
    if not versions.is_design(path):
        raise UserError("The path must end in .FCStd.")
    _check_overwrite(ctx, path, doc.FileName)
    ctx.host.save(doc, path)
    if not os.path.isfile(path):
        raise UserError("The design could not be saved to %s." % path)
    executor.MODIFIED.discard(doc.Name)
    return bridge_core.result("Saved as %s." % path)


@action("save_as")
def save_as(ctx, args):
    return save(ctx, {"path": args["path"]})


# -- designs ----------------------------------------------------------------------------------
def _designs():
    return [
        d
        for d in App.listDocuments().values()
        if not d.Name.startswith(("SciForgeExport", "SciForgeTemp")) and not _hidden(d)
    ]


def _hidden(doc):
    try:
        return bool(doc.Temporary) or bool(getattr(doc, "Hidden", False))
    except Exception:
        return False


def _find_design(name):
    for doc in _designs():
        if name in (doc.Name, doc.Label) or (
            doc.FileName and os.path.basename(doc.FileName) == name
        ):
            return doc
    raise UserError("No open design is called %r (list_designs lists them)." % name)


@action("new_design")
def new_design(ctx, args):
    name = args.get("name") or "Untitled"
    doc = ctx.host.new_document(name)
    ctx.host.ready(doc)
    body = ctx.host.ensure_body(doc)
    mark_modified(doc)
    return bridge_core.result(
        "New design %r (id %r) with an empty body %r; it is the active design."
        % (doc.Label, doc.Name, body.Name)
    )


@action("open_design")
def open_design(ctx, args):
    from ... import exchange_core, step_import

    path = os.path.abspath(args["path"])
    if not os.path.isfile(path):
        raise UserError("There is no file %s." % path)
    if path.lower().endswith(".fcstd"):
        doc = ctx.host.open_design(path)
    else:
        name = exchange_core.base_name(path)
        doc = ctx.host.new_document(name)
        try:
            made = step_import.import_file(doc, path, exchange_core.OPEN)
        except Exception:
            App.closeDocument(doc.Name)
            raise
        doc.recompute()
        step_import.apply_looks(made)
    ctx.host.ready(doc)
    body = ctx.host.find_body(doc)
    if body is not None:
        ctx.host.set_active_body(body)
    return bridge_core.result(
        "Opened %s as design %r (id %r). %s" % (path, doc.Label, doc.Name, summary(doc))
    )


@action("close_design")
def close_design(ctx, args):
    doc = _find_design(args["design"]) if args.get("design") else ctx.need_doc()
    if is_modified(ctx, doc):
        if not args.get("discard_changes"):
            raise UserError(
                "%s has unsaved changes: save it first, or give discard_changes true." % doc.Label
            )
        if ctx.host.gui and not ctx.host.ask(
            "AI control",
            "The AI app wants to close %s without saving its changes.\n\n" "Allow it?" % doc.Label,
        ):
            raise UserError("The person did not allow closing %s without saving." % doc.Label)
    label = doc.Label
    name = doc.Name
    if ctx.host.gui:
        try:
            import FreeCADGui as Gui

            Gui.getDocument(name).Modified = False
        except Exception:
            pass
    App.closeDocument(name)
    executor.forget(name)
    executor.MODIFIED.discard(name)
    left = App.ActiveDocument
    return bridge_core.result(
        "Closed %s.%s"
        % (
            label,
            (" The active design is now %s." % left.Label) if left else " No design is open now.",
        )
    )


@action("list_designs")
def list_designs(ctx, args):
    active = App.ActiveDocument
    rows = []
    for doc in _designs():
        rows.append(
            {
                "id": doc.Name,
                "name": doc.Label,
                "file": doc.FileName or None,
                "unsaved_changes": is_modified(ctx, doc),
                "active": active is not None and doc is active,
            }
        )
    return json_result({"designs": rows})


@action("switch_design")
def switch_design(ctx, args):
    doc = _find_design(args["design"])
    ctx.host.show_document(doc)
    return bridge_core.result("The active design is now %s. %s" % (doc.Label, summary(doc)))


# -- export -----------------------------------------------------------------------------------
def _bodies_for_export(ctx, doc, args):
    from ... import export

    if args.get("bodies"):
        return [ctx.body_of(ident) for ident in args["bodies"]]
    found = export.exportable_bodies(doc)
    if not found:
        raise UserError("There is nothing to export: the design has no visible body.")
    return found


@action("export")
def export_file(ctx, args):
    from ... import exchange, export

    doc = ctx.need_doc()
    fmt = args["format"]
    path = os.path.abspath(args["path"])
    if fmt == "dxf":
        if "sketch" in args:
            target = (ctx.resolve(args["sketch"], "sketch"), "")
            if target[0].TypeId != "Sketcher::SketchObject":
                raise UserError("%r is not a sketch." % args["sketch"])
        else:
            from ..ops import selectors

            tip = _tip(ctx, doc)
            names = selectors.select(tip.Shape, args["face"], "faces")
            if len(names) != 1:
                raise UserError(
                    "The face selector must pick exactly one face (it picked %d)." % len(names)
                )
            target = exchange.flat_target(tip, names[0])
            if target is None:
                raise UserError("That face is not flat: DXF takes a sketch or a flat face.")
        _check_overwrite(ctx, path)
        written = exchange.export_dxf(target, path)
        return bridge_core.result("Exported %s." % written)
    if fmt in MESH_LABELS:
        label = MESH_LABELS[fmt]
        path = export.with_extension(path, export.extension_of(label))
        _check_overwrite(ctx, path)
        body_list = _bodies_for_export(ctx, doc, args)
        written = export.export_mesh_files(
            doc,
            body_list,
            label,
            path,
            level=args.get("refinement", export.DEFAULT_REFINEMENT),
            unit=args.get("unit", "Millimeter"),
            per_body=bool(args.get("one_file_per_body")),
        )
        files = ", ".join("%s (%d triangles)" % (p, n) for p, n in written)
        return bridge_core.result("Exported %s." % files)
    if fmt in ("step", "iges"):
        _check_overwrite(ctx, path)
        if args.get("bodies"):
            chosen = _bodies_for_export(ctx, doc, args)
            if fmt == "step":
                written = export.export_step(chosen, path)
            else:
                written = exchange.export_cad(doc, fmt, path, scope="bodies", chosen=chosen)
        elif fmt == "step" and not ctx.host.gui:
            written = exchange.export_cad(doc, "step", path, scope="design")
        elif fmt == "step":
            written = export.export_step(export.exportable_bodies(doc), path)
        else:
            written = exchange.export_cad(doc, fmt, path, scope="design")
        return bridge_core.result("Exported %s." % written)
    if fmt == "brep":
        import Part

        _check_overwrite(ctx, path)
        solids = []
        for body in _bodies_for_export(ctx, doc, args):
            from ... import bodies

            solids += bodies.global_shape(body).Solids
        if not solids:
            raise UserError("There is no solid to write.")
        Part.makeCompound(solids).exportBrep(path)
        return bridge_core.result("Exported %s (%d solids)." % (path, len(solids)))
    raise UserError("SciForge cannot export %s." % fmt)


def _tip(ctx, doc):
    body = ctx.host.find_body(doc)
    if body is None or body.Tip is None or body.Tip.Shape.isNull():
        raise UserError("There is no solid to pick a face from.")
    return body.Tip


# -- insert -----------------------------------------------------------------------------------
@action("import_file")
def import_file(ctx, args):
    path = os.path.abspath(args["path"])
    if not os.path.isfile(path):
        raise UserError("There is no file %s." % path)
    ext = os.path.splitext(path)[1].lower()
    doc = ctx.need_doc(create=True)
    label = args.get("label")

    def work():
        from ... import components, exchange_core, insert, step_import

        body = ctx.host.find_body(doc)
        parent = components.container_of(body) if body is not None else None
        if ext in (".step", ".stp", ".igs", ".iges"):
            made = step_import.import_file(doc, path, exchange_core.INSERT, parent, label)
            doc.recompute()
            step_import.apply_looks(made)
            return "Inserted %s: %s." % (
                os.path.basename(path),
                exchange_core.describe(
                    len(made.components),
                    len(made.instances),
                    len(made.bodies),
                    os.path.basename(path),
                ),
            ), (made.top.Name if made.top is not None else None)
        if ext in (".stl", ".obj", ".3mf"):
            mesh = insert.read_mesh(path)
            obj = insert.make_mesh_body(
                doc, mesh, path, MESH_UNITS[args.get("unit", "mm")], label=label
            )
            return (
                "Inserted %s as a mesh body (%d triangles)."
                % (os.path.basename(path), mesh.CountFacets),
                obj.Name,
            )
        if ext == ".dxf":
            layers = insert.read_curves(path)
            edges = [e for _layer, found in layers for e in found]
            if not edges:
                raise UserError("The DXF has no curves SciForge can read.")
            body = ctx.host.ensure_body(doc)
            sketch = _sketch_on_plane(ctx, body, args.get("sketch_plane", "XY"), label)
            factor = (
                insert.unit_scale(MESH_UNITS[args.get("unit", "mm")]) if args.get("unit") else 1.0
            )
            if abs(factor - 1.0) > 1e-12:
                import FreeCAD as App2

                matrix = App2.Matrix()
                matrix.scale(factor, factor, factor)
                edges = [e.transformGeometry(matrix) for e in edges]
            insert.add_curves(sketch, edges)
            doc.recompute()
            return (
                "Inserted %d curves of %s into the sketch %r."
                % (len(edges), os.path.basename(path), sketch.Name),
                sketch.Name,
            )
        if ext == ".fcstd":
            from ... import design_insert, versions

            if not doc.FileName:
                raise UserError(
                    "Save this design first (save_as): an inserted design is "
                    "linked to it by its file's place."
                )
            if versions.same_path(doc.FileName, path):
                raise UserError("A design cannot be inserted into itself.")
            other = None
            for name in App.listDocuments():
                if versions.same_path(App.getDocument(name).FileName, path):
                    other = App.getDocument(name)
            if other is None:
                other = App.openDocument(path, True)
                App.setActiveDocument(doc.Name)
            comp = design_insert.insert_linked(doc, other, parent, label)
            return (
                "Inserted %s as the linked component %r." % (os.path.basename(path), comp.Name),
                comp.Name,
            )
        raise UserError("SciForge cannot insert %s files." % ext)

    before = None
    text, made = ctx.change(work)
    mark_modified(doc)
    return ctx.done(text + ((" Its id is %r." % made) if made else ""), doc, before)


def _sketch_on_plane(ctx, body, plane, label):
    roles = {"XY": "XY_Plane", "XZ": "XZ_Plane", "YZ": "YZ_Plane"}
    feature = [f for f in body.Origin.OriginFeatures if f.Role == roles[plane]][0]
    sketch = body.newObject("Sketcher::SketchObject", "Sketch")
    sketch.AttachmentSupport = [(feature, "")]
    sketch.MapMode = "FlatFace"
    if label:
        sketch.Label = label
    body.Document.recompute()
    return sketch
