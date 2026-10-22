# SPDX-License-Identifier: LGPL-2.1-or-later
"""AI actions for designs and files: undo / redo, new / open / save / save as / close /
list / switch designs, export to every format SciForge writes and insert (import) files,
with the same code as File > Open, Export and the INSERT menu (exchange.py, export.py,
step_import.py, insert.py, design_insert.py)."""

import os

import FreeCAD as App

from ... import warn
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


def _check_overwrite(ctx, paths, own=None):
    """Refuse (headless) or ask the person once (the window) when the file, or any of the
    files (a list: One File Per Body), already exists."""
    from ... import versions

    if isinstance(paths, str):
        paths = [paths]
    taken = [p for p in paths if os.path.exists(p) and not (own and versions.same_path(p, own))]
    if not taken:
        return
    what = taken[0] if len(taken) == 1 else taken
    if not ctx.host.confirm_overwrite(what):
        raise UserError(ctx.host.refuse_overwrite_text(what))


# -- undo / redo ------------------------------------------------------------------------------
def _undo_redo(ctx, which):
    doc = ctx.need_doc()
    names = doc.UndoNames if which == "undo" else doc.RedoNames
    if not names:
        raise UserError("There is nothing to %s." % which)
    getattr(doc, which)()
    _settle_after_undo(doc)
    ctx.host.after_change(doc)
    mark_modified(doc)
    return bridge_core.result("%s: %s. %s" % (which.capitalize(), names[0], summary(doc)))


def _settle_after_undo(doc):
    """What the timeline does after Ctrl+Z / Ctrl+Y (timeline_ui.after_undo): no rebuild
    when FreeCAD already put back every shape built from the values it restored (undo_fast,
    whose ledger the window keeps), else the design is rebuilt the Fusion way."""
    from ... import timeline_ops, undo_fast

    try:
        stale = any(
            "Touched" in o.State or "Invalid" in o.State or "Error" in o.State for o in doc.Objects
        )
        if not stale or undo_fast.settle_without_rebuild(doc):
            return
        timeline_ops.recompute(doc)
    except Exception as exc:
        warn("AI undo: %s" % exc)
        doc.recompute()


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
    path = ctx.full_path(path)
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


def _answers_to(doc, name):
    """True when name is the design's id, its name, its file's name or its file's path."""
    from ... import versions

    if name in (doc.Name, doc.Label):
        return True
    if not doc.FileName:
        return False
    return os.path.basename(doc.FileName) == name or (
        os.path.isabs(name) and versions.same_path(doc.FileName, name)
    )


def _handle(doc, designs):
    """The shortest text that names this design alone ("id:<id>" when nothing else does)."""
    names = [doc.Label, doc.Name]
    if doc.FileName:
        names[1:1] = [os.path.basename(doc.FileName), doc.FileName]
    for name in names:
        if [d for d in designs if _answers_to(d, name)] == [doc]:
            return name
    return "id:" + doc.Name


def _find_design(name):
    """The open design name names: its id, its name, its file's name or path, or "id:<id>"
    (the id alone). A text that names several designs (one design's id is another's name: a
    new "Part" beside a saved design whose id is "Part") is refused with each one's id, so
    a close or a switch never acts on another design than the one meant."""
    designs = _designs()
    if name.startswith("id:"):
        found = [d for d in designs if d.Name == name[3:]]
    else:
        found = [d for d in designs if _answers_to(d, name)]
    if len(found) == 1:
        return found[0]
    if not found:
        raise UserError("No open design is called %r (list_designs lists them)." % name)
    raise UserError(
        "%r could mean %d open designs: %s. Nothing was done: give the one you mean exactly."
        % (
            name,
            len(found),
            "; ".join(
                "%s (id %r, %s): give %r"
                % (
                    d.Label,
                    d.Name,
                    ("file %s" % os.path.basename(d.FileName)) if d.FileName else "never saved",
                    _handle(d, designs),
                )
                for d in found
            ),
        )
    )


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

    path = ctx.full_path(args["path"])
    if not os.path.isfile(path):
        raise UserError("There is no file %s." % path)
    notes = ""
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
        notes = _cad_notes(made, path, "Opened")
    ctx.host.ready(doc)
    body = ctx.host.find_body(doc)
    if body is not None:
        ctx.host.set_active_body(body)
    return bridge_core.result(
        "Opened %s as design %r (id %r). %s%s" % (path, doc.Label, doc.Name, summary(doc), notes)
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
    executor.forget(name, closed=True)
    executor.MODIFIED.discard(name)
    left = App.ActiveDocument
    others = _designs()
    if (left is None or left not in others) and others:
        # The window makes another tab active; command-line FreeCAD leaves none active,
        # and every later tool would answer that no design is open.
        left = others[-1]
        ctx.host.show_document(left)
    return bridge_core.result(
        "Closed %s.%s"
        % (
            label,
            (" The active design is now %s (id %r)." % (left.Label, left.Name))
            if left
            else " No design is open now.",
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


# -- what a file leaves out (export_report: the same facts as the window's message) ----------
def report_lines(lead, entries):
    """The extra lines of an answer: the lead and one line per item ("" when none)."""
    if not entries:
        return ""
    return "\n%s\n%s" % (lead, "\n".join("- %s" % e["text"] for e in entries))


def export_losses(doc, objects, fmt, file_name, **options):
    """What the file does not keep (export_report.losses, the facts File > Export's message
    shows), as lines to add to the answer; the window also shows its message and every run
    logs the one-line report. Never raises: a report that cannot be made never turns a
    written file into a failure."""
    try:
        from ... import export_report, export_report_ui

        entries = export_report.safe_losses(doc, objects, fmt, **options)
        several = str(file_name).endswith(" files")
        lead = "Not kept in these files:" if several else "Not kept in this file:"
        export_report_ui.report_export(file_name, entries, lead=lead)
        return report_lines(lead, entries)
    except Exception as exc:
        warn("AI export report: %s" % exc)
        return ""


def import_notes(file_name, entries, verb="Inserted"):
    """What a file had that did not come in (or came in changed), as lines to add to the
    answer, the same facts as the window's message after Open / Insert. Never raises."""
    try:
        from ... import export_report_ui

        export_report_ui.report_import(file_name, entries, verb)
        return report_lines("Not brought in, or changed:", entries)
    except Exception as exc:
        warn("AI import report: %s" % exc)
        return ""


def _cad_notes(made, path, verb):
    try:
        from ... import export_report

        entries = export_report.cad_import_items(getattr(made, "notes", None))
    except Exception as exc:
        warn("AI import report: %s" % exc)
        return ""
    return import_notes(os.path.basename(path), entries, verb)


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
    path = ctx.full_path(args["path"])
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
        lost = export_losses(doc, target, "DXF", os.path.basename(written))
        return bridge_core.result("Exported %s.%s" % (written, lost))
    if fmt in MESH_LABELS:
        label = MESH_LABELS[fmt]
        path = export.with_extension(path, export.extension_of(label))
        body_list = _bodies_for_export(ctx, doc, args)
        level = args.get("refinement", export.DEFAULT_REFINEMENT)
        unit = args.get("unit", "Millimeter")
        per_body = bool(args.get("one_file_per_body"))
        _check_overwrite(ctx, _mesh_files(export, body_list, path, label, per_body))
        written = export.export_mesh_files(
            doc, body_list, label, path, level=level, unit=unit, per_body=per_body
        )
        files = ", ".join("%s (%d triangles)" % (p, n) for p, n in written)
        lost = export_losses(
            doc,
            body_list,
            label,
            _files_label([p for p, _n in written]),
            unit=unit,
            per_body=per_body,
            level=level,
            whole=not args.get("bodies"),
        )
        return bridge_core.result("Exported %s.%s" % (files, lost))
    if fmt in ("step", "iges"):
        _check_overwrite(ctx, path)
        options = {}
        if args.get("bodies"):
            chosen = _bodies_for_export(ctx, doc, args)
            if fmt == "step":
                written = export.export_step(chosen, path)
            else:
                written = exchange.export_cad(doc, fmt, path, scope="bodies", chosen=chosen)
        elif fmt == "step" and not ctx.host.gui:
            chosen = None  # the whole design, its components kept (File > Export)
            written = exchange.export_cad(doc, "step", path, scope="design")
        elif fmt == "step":
            chosen = export.exportable_bodies(doc)
            options["whole"] = True
            written = export.export_step(chosen, path)
        else:
            chosen = None
            written = exchange.export_cad(doc, fmt, path, scope="design")
        lost = export_losses(doc, chosen, fmt, os.path.basename(str(written)), **options)
        return bridge_core.result("Exported %s.%s" % (written, lost))
    if fmt == "brep":
        import Part

        _check_overwrite(ctx, path)
        solids = []
        body_list = _bodies_for_export(ctx, doc, args)
        for body in body_list:
            from ... import bodies

            solids += bodies.global_shape(body).Solids
        if not solids:
            raise UserError("There is no solid to write.")
        Part.makeCompound(solids).exportBrep(path)
        lost = export_losses(
            doc, body_list, "brep", os.path.basename(path), whole=not args.get("bodies")
        )
        return bridge_core.result("Exported %s (%d solids).%s" % (path, len(solids), lost))
    raise UserError("SciForge cannot export %s." % fmt)


def _mesh_files(export, body_list, path, label, per_body):
    """The files a mesh export writes (export_mesh_files: one per body with One File Per
    Body and several bodies, else the one path)."""
    if per_body and len(body_list) > 1:
        base = os.path.splitext(os.path.basename(path))[0]
        return export.body_file_names(
            [b.Label for b in body_list], os.path.dirname(path), base, export.extension_of(label)
        )
    return [path]


def _files_label(paths):
    """A file's name, or "N files" (One File Per Body), as the window's message says."""
    if len(paths) == 1:
        return os.path.basename(str(paths[0]))
    return "%d files" % len(paths)


def _tip(ctx, doc):
    body = ctx.host.find_body(doc)
    if body is None or body.Tip is None or body.Tip.Shape.isNull():
        raise UserError("There is no solid to pick a face from.")
    return body.Tip


# -- insert -----------------------------------------------------------------------------------
@action("import_file")
def import_file(ctx, args):
    path = ctx.full_path(args["path"])
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
            reports.append(lambda: _cad_notes(made, path, "Inserted"))
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
            unit = MESH_UNITS[args.get("unit", "mm")]
            obj = insert.make_mesh_body(doc, mesh, path, unit, label=label)
            reports.append(lambda: _mesh_notes(path, mesh, unit))
            return (
                "Inserted %s as a mesh body (%d triangles)."
                % (os.path.basename(path), mesh.CountFacets),
                obj.Name,
            )
        if ext == ".dxf":
            notes = {}
            layers = insert.read_curves(path, notes)
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
            geos = insert.curves_to_geometry(edges)
            notes["skipped"] = max(0, len(edges) - len(geos))
            insert.add_geometry(sketch, geos)
            doc.recompute()
            reports.append(lambda: _curve_notes(path, notes))
            return (
                "Inserted %d curves of %s into the sketch %r."
                % (len(geos), os.path.basename(path), sketch.Name),
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
    reports = []  # what did not come in: told once the insert is done (not undone)
    text, made = ctx.change(work)
    mark_modified(doc)
    answer = ctx.done(text + ((" Its id is %r." % made) if made else ""), doc, before)
    notes = "".join(report() for report in reports)
    if notes:
        answer["text"] += notes
    return answer


def _mesh_notes(path, mesh, unit):
    try:
        from ... import export_report

        entries = export_report.mesh_import_items(path, mesh, unit)
    except Exception as exc:
        warn("AI import report: %s" % exc)
        return ""
    return import_notes(os.path.basename(path), entries)


def _curve_notes(path, notes):
    try:
        from ... import export_report

        entries = export_report.curve_import_items(path, notes)
    except Exception as exc:
        warn("AI import report: %s" % exc)
        return ""
    return import_notes(os.path.basename(path), entries)


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
