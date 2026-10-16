# SPDX-License-Identifier: LGPL-2.1-or-later
"""Export with structure, without Qt (Fusion's File > Export and Save As DXF): STEP that
keeps the components (each component a product, a copy of a component a second occurrence
of it), IGES, a sketch or a flat face as DXF (Fusion: right-click a sketch > Save As DXF),
DWG through a free converter when one is installed. Spec and sources:
docs/sciforge/parity/insert-export.md ("Part 2").

STEP and IGES are written from a hidden throw-away document that mirrors the design: a
component with bodies only is a part named after it (its bodies' solids, with their
colours); a component with components in it is an assembly holding them and a part of its
own name for its bodies; a copy (instance) of a component written too is an App::Link to
it, which FreeCAD writes as a second occurrence of the same product. step_import reads such
a file back into the same components.
"""

import os

import FreeCAD as App

from . import bodies, components, export, insert, instances, log, warn
from . import exchange_core as core

IGES_MODE = "write.iges.brep.mode"  # OpenCASCADE: 1 = solids (MSBO), 0 = faces only
IGES_PREFS = "User parameter:BaseApp/Preferences/Mod/Part/IGES"


# -- what is exported --------------------------------------------------------------------------
def solid_bodies_in(doc, component, shown_only=True):
    """The bodies directly in a component (None: the root) that have a solid (and are
    shown, as Fusion's export takes the visible bodies)."""
    found = []
    for body in components.bodies_in(doc, component):
        if not bodies.has_solid(body):
            continue
        if shown_only and not bodies.is_shown(body):
            continue
        found.append(body)
    return found


def _units(doc, parents, shown_only, check_self=True):
    out = []
    for comp in parents:
        if shown_only and check_self and not bodies.is_shown(comp):
            continue
        source = instances.source_of(comp) if instances.is_instance(comp) else None
        out.append(
            {
                "id": comp.Name,
                "name": comp.Label,
                "bodies": len(solid_bodies_in(doc, comp, shown_only)),
                "children": _units(doc, components.components_in(doc, comp), shown_only),
                "instance_of": source.Name if source is not None else None,
            }
        )
    return out


# -- the mirror document -----------------------------------------------------------------------
def _view_colours(obj):
    return insert._view_colours(obj)


def _body_faces(body, frame_inverse):
    """(solid in the frame, [colour per face]) of a body."""
    shape = bodies.global_shape(body)
    if frame_inverse is not None:
        shape.transformShape(frame_inverse.toMatrix(), True)
    colours = []
    tip = getattr(body, "Tip", None)
    if tip is not None:
        colours = _view_colours(tip) or _view_colours(body)
    count = len(shape.Faces)
    if len(colours) != count:
        colours = [colours[0]] * count if colours else []
    return shape, colours


def _part_feature(tmp, label, body_list, frame):
    """A Part::Feature named `label` holding the bodies' solids in `frame` (the component's
    placement in the design), with their colours."""
    import Part

    inverse = frame.inverse()
    shapes, colours = [], []
    for body in body_list:
        shape, faces = _body_faces(body, inverse)
        shapes.append(shape)
        colours += faces
    feature = tmp.addObject("Part::Feature", "Part")
    feature.Label = label
    solids = [s for shape in shapes for s in shape.Solids]
    feature.Shape = solids[0] if len(solids) == 1 else Part.makeCompound(solids)
    _paint(feature, colours)
    return feature


def _paint(feature, colours):
    if not colours or not App.GuiUp:
        return
    try:
        vobj = feature.ViewObject
        if vobj is None:
            return
        materials = []
        for colour in colours:
            material = App.Material()
            material.DiffuseColor = tuple(colour[:3]) + (1.0,)
            materials.append(material)
        if len(materials) == len(feature.Shape.Faces):
            vobj.ShapeAppearance = materials
        else:
            vobj.ShapeAppearance = materials[:1]
    except Exception as exc:
        warn("export: colours of %s not written (%s)" % (feature.Label, exc))


class _Mirror:
    def __init__(self, doc, tmp, shown_only):
        self.doc = doc
        self.tmp = tmp
        self.shown_only = shown_only
        self.made = {}  # component name -> mirror object
        self.links = []  # (component, mirror container or None)

    def unit(self, plan, container):
        comp = self.doc.getObject(plan["id"])
        if comp is None or plan["as"] == "skip":
            return None
        frame = comp.getGlobalPlacement()
        local = App.Placement(comp.Placement)
        if plan["as"] == "link":
            self.links.append((comp, container))
            return None
        body_list = solid_bodies_in(self.doc, comp, self.shown_only)
        if plan["as"] == "part":
            obj = _part_feature(self.tmp, comp.Label, body_list, frame)
            obj.Placement = local
        else:
            obj = self.tmp.addObject("App::Part", "Assembly")
            obj.Label = comp.Label
            obj.Placement = local
            if plan["bodies_part"] and body_list:
                obj.addObject(_part_feature(self.tmp, comp.Label, body_list, frame))
            for child in plan["children"]:
                self.unit(child, obj)
        if container is not None:
            container.addObject(obj)
        self.made[comp.Name] = obj
        return obj

    def finish_links(self):
        for comp, container in self.links:
            source = instances.source_of(comp)
            target = self.made.get(source.Name) if source is not None else None
            if target is None:
                continue
            link = self.tmp.addObject("App::Link", "Occurrence")
            link.LinkedObject = target
            link.Label = instances.core.split_instance_label(comp.Label)[0] or comp.Label
            link.Placement = App.Placement(comp.Placement)
            if container is not None:
                container.addObject(link)


def _mirror_document(doc, scope, target, chosen, shown_only=True, frame=None):
    """(throw-away document, [top objects]) holding what is exported, as described in the
    module's doc. scope: "design", "component" (target) or "bodies" (chosen, flat)."""
    active = App.ActiveDocument.Name if App.ActiveDocument is not None else None
    tmp = App.newDocument("SciForgeExportCAD", "export", True, True)
    try:
        tops = []
        mirror = None
        if scope == "bodies":
            for body in chosen or []:
                if export.is_mesh_body(body) or not bodies.has_solid(body):
                    continue
                tops.append(_part_feature(tmp, body.Label, [body], frame or App.Placement()))
        else:
            if scope == "component":
                if target is None or not components.is_component(target):
                    raise core.ExchangeError("Pick the component to export.")
                plans = core.mirror_plan(_units(doc, [target], shown_only, check_self=False))
                mirror = _Mirror(doc, tmp, shown_only)
                for plan in plans:
                    obj = mirror.unit(plan, None)
                    if obj is not None:
                        # the component's own frame is the file's origin (Fusion: "the selected
                        # component defines the coordinate system")
                        obj.Placement = App.Placement()
                        tops.append(obj)
            else:
                units = _units(doc, components.components_in(doc, None), shown_only)
                root_bodies = solid_bodies_in(doc, None, shown_only)
                plans = core.mirror_plan(units)
                mirror = _Mirror(doc, tmp, shown_only)
                if not any(p["as"] != "skip" for p in plans):
                    if root_bodies:
                        # one body: the part is named after it (opened again, the body keeps
                        # its name); several: after the design, as Fusion's root product
                        label = root_bodies[0].Label if len(root_bodies) == 1 else None
                        tops.append(
                            _part_feature(
                                tmp, label or _design_label(doc), root_bodies, App.Placement()
                            )
                        )
                else:
                    root = tmp.addObject("App::Part", "Design")
                    root.Label = _design_label(doc)
                    if root_bodies:
                        root.addObject(_part_feature(tmp, root.Label, root_bodies, App.Placement()))
                    for plan in plans:
                        mirror.unit(plan, root)
                    tops.append(root)
        if mirror is not None:
            mirror.finish_links()
        tmp.recompute()
        if not tops:
            found = chosen if chosen is not None else export.exportable_bodies(doc)
            if any(export.is_mesh_body(b) for b in found):
                raise core.ExchangeError(
                    "STEP holds solid bodies only (IGES too): convert the mesh bodies first "
                    "(MESH > Convert Mesh), or export them as STL, 3MF or OBJ."
                )
            raise core.ExchangeError(
                "There is no solid body to export (hidden bodies are left out)."
            )
        return tmp, tops, active
    except Exception:
        _close(tmp, active)
        raise


def _close(tmp, active):
    try:
        App.closeDocument(tmp.Name)
    except Exception:
        pass
    insert.restore_active_document(active)


def _design_label(doc):
    if doc.FileName:
        return os.path.splitext(os.path.basename(doc.FileName))[0]
    return doc.Label


def _writer():
    if App.GuiUp:
        try:
            import ImportGui

            return ImportGui
        except Exception:
            pass
    import Import

    return Import


# -- STEP / IGES -------------------------------------------------------------------------------
def export_cad(doc, kind, path, scope="design", target=None, chosen=None):
    """Write STEP (with the component structure) or IGES (the solids, flat: IGES keeps no
    assemblies). Returns the path written."""
    if kind not in core.CAD_KINDS:
        raise core.ExchangeError("Not a CAD type: %s" % kind)
    extension = ".step" if kind == "step" else ".igs"
    if not path.lower().endswith((".step", ".stp", ".igs", ".iges")):
        path += extension
    folder = os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder, exist_ok=True)
    frame = None
    if kind == "iges" and scope != "bodies":
        chosen = _bodies_of_scope(doc, scope, target)
        if scope == "component":  # in the component's own coordinates, as STEP is
            frame = component_frame(target)
        scope = "bodies"
    tmp, tops, active = _mirror_document(doc, scope, target, chosen, frame=frame)
    try:
        if kind == "iges":
            _write_iges(tops, path)
        else:
            _writer().export(tops, path)
    finally:
        _close(tmp, active)
    if not os.path.isfile(path):
        raise core.ExchangeError("The file could not be written: %s" % path)
    log("export: %s (%s)" % (path, kind.upper()))
    return path


def _bodies_of_scope(doc, scope, target):
    if scope == "component":
        found = components.bodies_in(doc, target, recursive=True)
    else:
        found = bodies.list_bodies(doc)
    return [b for b in found if bodies.has_solid(b) and bodies.is_shown(b)]


def _write_iges(tops, path):
    """IGES with solids (MSBO entities) instead of loose faces, so another program (and
    SciForge) reads solid bodies back; the user's own setting is put back afterwards."""
    import Part

    try:
        Part.setStaticValue(IGES_MODE, 1)
    except Exception as exc:
        warn("IGES: solids mode not set (%s)" % exc)
    try:
        import Import

        Import.export(tops, path)
    finally:
        try:
            Part.setStaticValue(IGES_MODE, 1 if App.ParamGet(IGES_PREFS).GetBool("BrepMode") else 0)
        except Exception:
            pass


# -- DXF / DWG ---------------------------------------------------------------------------------
def flat_target(obj, sub=""):
    """(object, sub) if it can be written as DXF: a sketch, or a flat face; else None."""
    if obj is None:
        return None
    if obj.TypeId == "Sketcher::SketchObject":
        return (obj, "")
    if sub.startswith("Face"):
        try:
            face = obj.Shape.getElement(sub)
            if face.Surface.TypeId == "Part::GeomPlane" or face.findPlane() is not None:
                return (obj, sub)
        except Exception:
            return None
    return None


def flat_edges(target):
    """The edges of a sketch (its own 2D coordinates: the sketch's X and Y, as Fusion's Save
    As DXF writes them) or of a flat face (in the face's own frame, its origin at its
    middle), as a compound in the XY plane."""
    import Part

    obj, sub = target
    if not sub:
        shape = obj.Shape.copy()
        shape.Placement = App.Placement()  # a sketch's geometry is in its own frame
        edges = shape.Edges
        if not edges:
            raise core.ExchangeError(
                "%s has no curves to save (construction lines are left out)." % obj.Label
            )
        return Part.makeCompound([e.copy() for e in edges])
    face = bodies.global_shape(obj).getElement(sub)
    frame = face_frame(face)
    out = Part.makeCompound([e.copy() for e in face.Edges])
    out.transformShape(frame.inverse().toMatrix(), True)
    return out


def face_frame(face):
    """The frame of a flat face (design coordinates): its plane's axes, the normal out of
    the part, the origin at the face's middle."""
    rotation = face.Surface.Rotation
    u0, u1, v0, v1 = face.ParameterRange
    normal = face.normalAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)
    if rotation.multVec(App.Vector(0, 0, 1)).dot(normal) < 0:
        rotation = rotation.multiply(App.Rotation(App.Vector(1, 0, 0), 180))
    return App.Placement(face.CenterOfMass, rotation)


def export_dxf(target, path):
    """Save a sketch or a flat face as DXF (FreeCAD's DXF writer: lines, circles, arcs,
    splines). Returns the path."""
    if not path.lower().endswith(".dxf"):
        path += ".dxf"
    compound = flat_edges(target)
    folder = os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder, exist_ok=True)
    active = App.ActiveDocument.Name if App.ActiveDocument is not None else None
    tmp = App.newDocument("SciForgeExportDXF", "export", True, True)
    try:
        feature = tmp.addObject("Part::Feature", "Curves")
        feature.Label = target[0].Label
        feature.Shape = compound
        tmp.recompute()
        import importDXF

        importDXF.export([feature], path)
    finally:
        _close(tmp, active)
    if not os.path.isfile(path):
        raise core.ExchangeError("The DXF could not be written: %s" % path)
    log("export: %s (DXF of %s)" % (path, target[0].Label))
    return path


def dwg_converter():
    """The free DWG converter FreeCAD can use (LibreDWG, ODA, QCAD), or None."""
    try:
        import importDWG

        for find in (
            lambda: importDWG.get_libredwg_converter("dxf2dwg"),
            importDWG.get_oda_converter,
            importDWG.get_qcad_converter,
        ):
            try:
                found = find()
            except Exception:
                found = None
            if found:
                return found
    except Exception:
        pass
    return None


def export_dwg(target, path):
    """A DXF converted to DWG by the free converter, never a renamed DXF: without a
    converter the export is refused with what to install."""
    if not path.lower().endswith(".dwg"):
        path += ".dwg"
    if dwg_converter() is None:
        raise core.ExchangeError(core.DWG_NONE)
    import importDWG

    dxf = os.path.splitext(path)[0] + ".dxf"
    export_dxf(target, dxf)
    importDWG.convertToDwg(dxf, path)
    if not os.path.isfile(path):
        raise core.ExchangeError("The DWG converter did not write %s." % path)
    return path


# -- meshes of a component ---------------------------------------------------------------------
def component_frame(component):
    return component.getGlobalPlacement() if component is not None else App.Placement()


def mesh_bodies_of(doc, component):
    """The bodies a mesh export of a component takes (its bodies and its components',
    shown ones)."""
    found = components.bodies_in(doc, component, recursive=True)
    return [b for b in found if bodies.is_shown(b) and export.can_export(b)]
