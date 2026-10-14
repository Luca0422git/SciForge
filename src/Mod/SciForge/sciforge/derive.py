# SPDX-License-Identifier: LGPL-2.1-or-later
"""Derive / Insert Derive, the document side (no Qt): read another saved design, bring its
bodies, sketches, construction geometry and user parameters into this one, keep them linked
(update when the source is saved again), break the link. derive_ui.py is the dialog; the
logic without FreeCAD is derive_core.py. Spec and sources: docs/sciforge/parity/misc.md.

What a Derive makes (all found again by their SciForgeType):
  Derive         an App::FeaturePython at document level: the timeline step (kind "derive").
                 SourceFile (absolute) + SourceRelative (from this design's folder),
                 SourceStamp, Items ("body:Body001", ...), Results ("key=ObjectName"),
                 PlaceAtOrigin, LinkBroken. No proxy: nothing to load but plain properties.
  DerivedSolid   a hidden Part::Feature holding a derived body's solid; the derived body's
                 BaseFeature (PartDesign shows it as the body's first step, hidden from the
                 timeline), so features added on the derived body follow an update.
  derived sketch a Sketcher::SketchObject with the source's curves, each fixed (Block)
  derived plane  a PartDesign::Plane / Line / Point at the source's placement
  parameter      a property of the "Parameters" VarSet in its group "Derived" (read-only in
                 Change Parameters, usable in every formula)
The source design itself is never opened: a copy of its saved file is read and thrown away,
so an open source with unsaved changes is left alone and only saved versions are derived,
as in Fusion.
"""

import os
import shutil
import uuid

import FreeCAD as App

from . import bodies, log, warn
from . import derive_core as core

TYPE = "Derive"
SOLID_TYPE = "DerivedSolid"
SOLID_TYPEID = "Part::Feature"
DERIVED_PROP = "SciForgeDerive"  # on every derived object: the name of its Derive
PARAM_GROUP = "Derived"
WARNING = "SciForgeWarning"  # the timeline shows it in yellow (timeline_ops.WARNING)
DATUM_TYPES = {
    "PartDesign::Plane": "PartDesign::Plane",
    "PartDesign::Line": "PartDesign::Line",
    "PartDesign::Point": "PartDesign::Point",
    "Part::DatumPlane": "PartDesign::Plane",
    "Part::DatumLine": "PartDesign::Line",
    "Part::DatumPoint": "PartDesign::Point",
}
PARAM_TYPES = {
    "App::PropertyLength": "mm",
    "App::PropertyDistance": "mm",
    "App::PropertyAngle": "deg",
    "App::PropertyFloat": "",
    "App::PropertyInteger": "",
    "App::PropertyQuantity": "",
}

DeriveError = core.DeriveError


# -- reading a source design ----------------------------------------------------------------------
def _container_place(obj):
    """The placement the component(s) around `obj` give it (identity at the root)."""
    try:
        parent = obj.getParentGeoFeatureGroup()
    except Exception:
        parent = None
    while parent is not None and parent.TypeId == "PartDesign::Body":
        try:
            parent = parent.getParentGeoFeatureGroup()
        except Exception:
            parent = None
    if parent is None:
        return App.Placement(), None
    try:
        return parent.getGlobalPlacement(), parent
    except Exception:
        return App.Placement(parent.Placement), parent


def _component_label(obj):
    _place, part = _container_place(obj)
    return part.Label if part is not None else None


def _placements(obj):
    """(where it is in the design, where it is in its own component)."""
    glob = obj.getGlobalPlacement()
    outer, _part = _container_place(obj)
    return glob, outer.inverse().multiply(glob)


def _used_up(doc):
    try:
        return set(bodies.consumed(doc))
    except Exception:
        return set()


def _value_text(value, unit):
    try:
        number = value.Value if hasattr(value, "Value") else float(value)
        text = ("%.4f" % number).rstrip("0").rstrip(".")
        return text + (" " + unit if unit else "")
    except Exception:
        return str(value)


def read_doc(doc):
    """Everything a Derive can take from an open design, as plain data (shapes copied):
    {"rows": [dialog rows], "items": {key: data}, "derives": [source files of its Derives]}.
    """
    rows, items = [], {}
    used_up = _used_up(doc)
    for body in bodies.list_bodies(doc):
        if body.Name in used_up or getattr(body, "SciForgeTimeline", True) is False:
            continue
        try:
            shape = body.Shape
            if shape.isNull() or not shape.Solids:
                continue
        except Exception:
            continue
        glob, local = _placements(body)
        key = core.item_key("body", body.Name)
        rows.append(
            {
                "kind": "body",
                "name": body.Name,
                "label": body.Label,
                "component": _component_label(body),
            }
        )
        solid = shape.copy()
        solid.Placement = App.Placement()  # the body's own frame; placed below
        items[key] = {
            "label": body.Label,
            "shape": solid,
            "global": glob,
            "local": local,
            "material": _material_of(body),
            "look": getattr(body, "SciForgeAppearance", ""),
            "user_material": getattr(body, "SciForgeUserMaterial", ""),
        }
    for obj in doc.Objects:
        if obj.TypeId == "Sketcher::SketchObject":
            if getattr(obj, "SciForgeTimeline", True) is False and not getattr(
                obj, DERIVED_PROP, ""
            ):
                continue  # a helper sketch of a step (a Single Hole's): not the user's
            glob, local = _placements(obj)
            key = core.item_key("sketch", obj.Name)
            rows.append(
                {
                    "kind": "sketch",
                    "name": obj.Name,
                    "label": obj.Label,
                    "component": _component_label(obj),
                }
            )
            geos = []
            for i, geo in enumerate(obj.Geometry):
                try:
                    geos.append((geo.copy(), bool(obj.getConstruction(i))))
                except Exception:
                    geos.append((geo.copy(), False))
            items[key] = {"label": obj.Label, "geometry": geos, "global": glob, "local": local}
        elif obj.TypeId in DATUM_TYPES:
            if getattr(obj, "SciForgeTimeline", True) is False and not getattr(
                obj, DERIVED_PROP, ""
            ):
                continue
            glob, local = _placements(obj)
            key = core.item_key("construction", obj.Name)
            rows.append(
                {
                    "kind": "construction",
                    "name": obj.Name,
                    "label": obj.Label,
                    "component": _component_label(obj),
                }
            )
            items[key] = {
                "label": obj.Label,
                "type": DATUM_TYPES[obj.TypeId],
                "global": glob,
                "local": local,
            }
    for row in _parameter_rows(doc):
        key = core.item_key("parameter", row["name"])
        rows.append(
            {
                "kind": "parameter",
                "name": row["name"],
                "label": row["name"],
                "component": None,
                "value_text": _value_text(row["value"], row["unit"]),
            }
        )
        items[key] = row
    derives = []
    for master in masters(doc):
        derives.append(master.SourceFile)
    return {"rows": rows, "items": items, "derives": derives}


def _parameter_rows(doc):
    """The design's own and derived parameters: [{name, type_id, unit, value, comment}]."""
    container = doc.getObject("Parameters")
    if container is None or container.TypeId != "App::VarSet":
        return []
    found = []
    for name in container.PropertiesList:
        group = container.getGroupOfProperty(name)
        if group not in ("Parameters", PARAM_GROUP):
            continue
        type_id = container.getTypeIdOfProperty(name)
        if type_id not in PARAM_TYPES:
            continue
        found.append(
            {
                "name": name,
                "type_id": type_id,
                "unit": PARAM_TYPES[type_id],
                "value": getattr(container, name),
                "comment": container.getDocumentationOfProperty(name),
            }
        )
    return found


def _material_of(body):
    try:
        return body.ShapeMaterial
    except Exception:
        return None


class _Copy:
    """A copy of a saved design opened hidden and read, then closed and removed again."""

    def __init__(self, path):
        self.path = path
        self.copy = None
        self.doc = None
        self.active = None
        self.folder = None  # a temporary folder made for the copy (removed with it)

    def __enter__(self):
        if not self.path or not os.path.isfile(self.path):
            raise DeriveError("The design %s was not found." % (self.path or "(none)"))
        self.active = App.ActiveDocument.Name if App.ActiveDocument else None
        token = uuid.uuid4().hex[:12]
        folder = os.path.dirname(os.path.abspath(self.path))
        self.copy = core.copy_name(folder, token)
        try:
            shutil.copyfile(self.path, self.copy)
        except OSError:
            import tempfile

            # A folder that cannot be written (a read-only share): a temporary folder.
            self.folder = tempfile.mkdtemp(prefix="sciforge-derive-")
            self.copy = core.copy_name(self.folder, token)
            shutil.copyfile(self.path, self.copy)
        try:
            self.doc = App.openDocument(self.copy, True)  # hidden: no tab of its own
        except Exception as exc:
            self._remove_file()
            raise DeriveError(
                "%s could not be read: %s" % (core.design_name(self.path), exc)
            ) from exc
        return self.doc

    def __exit__(self, *exc):
        try:
            if self.doc is not None and self.doc.Name in App.listDocuments():
                App.closeDocument(self.doc.Name)
        except Exception as error:
            warn("derive: closing the copy of %s: %s" % (core.design_name(self.path), error))
        self._remove_file()
        if self.active and self.active in App.listDocuments():
            try:
                App.setActiveDocument(self.active)
                if App.GuiUp:
                    import FreeCADGui as Gui

                    Gui.setActiveDocument(self.active)
            except Exception:
                pass
        return False

    def _remove_file(self):
        try:
            if self.copy and os.path.isfile(self.copy):
                os.remove(self.copy)
        except OSError:
            pass
        if self.folder:
            shutil.rmtree(self.folder, ignore_errors=True)


def read_source(path):
    """What a saved design offers to derive (see read_doc), read from a copy of its file,
    plus "stamp" (the file read) and "path"."""
    with _Copy(path) as doc:
        data = read_doc(doc)
    data["stamp"] = core.file_stamp(path)
    data["path"] = os.path.abspath(path)
    data["name"] = core.design_name(path)
    return data


# -- the Derive step ------------------------------------------------------------------------------
def is_derive(obj):
    return bodies.kind(obj) == TYPE


def masters(doc):
    return [o for o in doc.Objects if is_derive(o)] if doc is not None else []


def derived_from(obj):
    """The Derive that made `obj` (a derived body, sketch, plane or solid), or None."""
    try:
        name = getattr(obj, DERIVED_PROP, "")
    except Exception:
        return None
    if not name:
        return None
    master = obj.Document.getObject(name)
    return master if is_derive(master) else None


def _add(obj, kind, name, doc, hidden=True):
    bodies.add_prop(obj, kind, name, "Derive", doc, hidden)


def make_master(doc, source_path, label=None):
    master = doc.addObject("App::FeaturePython", "Derive")
    bodies.mark(master, TYPE)
    _add(master, "App::PropertyString", "SourceFile", "The source design (absolute path)", False)
    _add(master, "App::PropertyString", "SourceRelative", "The source from this design's folder")
    _add(master, "App::PropertyString", "SourceName", "The source design's name", False)
    _add(master, "App::PropertyString", "SourceStamp", "The source file as last read")
    _add(master, "App::PropertyStringList", "Items", "What is derived (kind:name)")
    _add(master, "App::PropertyStringList", "Results", "What each item became (key=Name)")
    _add(master, "App::PropertyStringList", "ItemLabels", "The items' names in the source")
    _add(master, "App::PropertyBool", "PlaceAtOrigin", "At their component's origin", False)
    _add(master, "App::PropertyBool", "LinkBroken", "No longer follows the source", False)
    master.SourceFile = os.path.abspath(source_path)
    master.SourceName = core.design_name(source_path)
    set_relative(master)
    if label:
        master.Label = label
    return master


def set_relative(master, design_file=None):
    """SourceRelative from the design's file (none yet for a design never saved)."""
    design_file = design_file if design_file is not None else master.Document.FileName
    if not design_file:
        return
    try:
        rel = os.path.relpath(
            os.path.abspath(master.SourceFile), os.path.dirname(os.path.abspath(design_file))
        ).replace(os.sep, "/")
    except ValueError:
        rel = ""  # another drive (Windows): only the absolute path
    if master.SourceRelative != rel:
        master.SourceRelative = rel


def source_path(master):
    """The source file this Derive reads now (relative path first), or None."""
    return core.resolve_source(master.Document.FileName, master.SourceRelative, master.SourceFile)


def state(master, refresh=True):
    """derive_core's UP_TO_DATE / NEWER / MISSING / BROKEN for a Derive. A copied, unchanged
    source refreshes the stored stamp (refresh=True) and counts as up to date."""
    if getattr(master, "LinkBroken", False):
        return core.BROKEN
    path = source_path(master)
    if path is None:
        return core.MISSING
    try:
        st = os.stat(path)
    except OSError:
        return core.MISSING
    result, fresh = core.compare_stamp(
        master.SourceStamp, st.st_mtime, st.st_size, lambda: core.file_digest(path)
    )
    if fresh and refresh:
        try:
            master.SourceStamp = fresh
        except Exception:
            pass
    return result


def set_warning(obj, text):
    """The timeline's yellow note on the Derive (never saved: it is found again on open)."""
    if WARNING not in obj.PropertiesList:
        if not text:
            return
        obj.addProperty("App::PropertyString", WARNING, "Derive", "Why the timeline warns", 4 | 2)
        try:  # a note, not a change of the design: no "unsaved" star for it
            obj.setPropertyStatus(WARNING, ["NoModify"])
        except Exception:
            pass
    if getattr(obj, WARNING) != text:
        setattr(obj, WARNING, text)


# -- building what is derived --------------------------------------------------------------------
def _place_for(data, at_origin):
    return data["local"] if at_origin else data["global"]


def _mark_derived(obj, master):
    _add(obj, "App::PropertyString", DERIVED_PROP, "The Derive that made it")
    setattr(obj, DERIVED_PROP, master.Name)


def _new_body(doc, label, component):
    body = doc.addObject("PartDesign::Body", "Body")
    if component is not None:
        component.addObject(body)
    body.Label = label
    return body


def _solid_shape(data, at_origin):
    """The derived solid in design coordinates, its placement baked into the geometry
    (PartDesign's base feature drops a shape's own placement)."""
    shape = data["shape"].copy()
    place = _place_for(data, at_origin)
    if not place.isIdentity():
        shape.transformShape(place.toMatrix(), True)
    return shape


def _build_body(master, data, component):
    doc = master.Document
    holder = doc.addObject(SOLID_TYPEID, "DerivedSolid")
    bodies.mark(holder, SOLID_TYPE)
    bodies.hide_from_timeline(holder)
    _mark_derived(holder, master)
    holder.Shape = _solid_shape(data, master.PlaceAtOrigin)
    body = _new_body(doc, data["label"], component)
    _mark_derived(body, master)
    body.BaseFeature = holder
    for obj in body.Group:
        if obj.TypeId == "PartDesign::FeatureBase":
            bodies.hide_from_timeline(obj)
            _mark_derived(obj, master)
    _copy_look(body, data)
    if App.GuiUp:
        try:
            holder.ViewObject.Visibility = False
        except Exception:
            pass
    return body


def _copy_look(body, data):
    if data.get("material") is not None:
        try:
            body.ShapeMaterial = data["material"]
        except Exception:
            pass
    for prop, text in (
        ("SciForgeAppearance", data.get("look")),
        ("SciForgeUserMaterial", data.get("user_material")),  # material.USER_PROP
    ):
        if not text and prop not in body.PropertiesList:
            continue
        try:
            bodies.add_prop(body, "App::PropertyString", prop, "Base", "", True)
            if getattr(body, prop) != (text or ""):
                setattr(body, prop, text or "")
        except Exception:
            pass


def _fill_sketch(sketch, data):
    import Sketcher

    if sketch.GeometryCount:
        sketch.deleteAllGeometry()
    for geo, construction in data["geometry"]:
        index = sketch.addGeometry(geo.copy(), construction)
        if not construction:
            try:
                sketch.addConstraint(Sketcher.Constraint("Block", index))
            except Exception:
                pass


def _build_sketch(master, data, body):
    sketch = body.newObject("Sketcher::SketchObject", "Sketch")
    sketch.Label = data["label"]
    try:
        sketch.MapMode = "Deactivated"
    except Exception:
        pass
    sketch.Placement = _place_for(data, master.PlaceAtOrigin)
    _fill_sketch(sketch, data)
    _mark_derived(sketch, master)
    bodies.hide_from_timeline(sketch)
    return sketch


def _build_datum(master, data, body):
    datum = body.newObject(data["type"], data["type"].split("::")[1])
    datum.Label = data["label"]
    try:
        datum.MapMode = "Deactivated"
    except Exception:
        pass
    datum.Placement = _place_for(data, master.PlaceAtOrigin)
    _mark_derived(datum, master)
    bodies.hide_from_timeline(datum)
    return datum


def _params(doc, create=False):
    from . import parameters

    return parameters.container(doc, create=create)


def _build_parameter(master, data):
    doc = master.Document
    container = _params(doc, create=True)
    taken = set(container.PropertiesList)
    name = core.unique_name(data["name"], taken)
    note = "Derived from %s" % master.SourceName
    if data.get("comment"):
        note += ": " + data["comment"]
    container.addProperty(data["type_id"], name, PARAM_GROUP, note)
    setattr(container, name, data["value"])
    try:
        container.setPropertyStatus(name, ["ReadOnly"])
    except Exception:
        pass
    return name


def _target_body(doc, made_bodies, target_body, component):
    if target_body is not None and bodies.alive(target_body):
        return target_body
    if made_bodies:
        return made_bodies[0]
    body = _new_body(doc, "Body1", component)
    return body


def build(master, data, keys, target_body=None, component=None):
    """Make the derived objects of `keys` (item keys) from read_source() data. Returns the
    {key: object name} of what was made. `target_body`: the body that holds derived sketches
    and planes (the active one); `component`: where derived bodies go (None: the root)."""
    doc = master.Document
    made = {}
    labels = list(master.ItemLabels)
    made_bodies = []
    for key in keys:
        kind, _name = core.parse_item(key)
        if kind == "body" and key in data["items"]:
            body = _build_body(master, data["items"][key], component)
            made[key] = body.Name
            made_bodies.append(body)
    holder = None
    for key in keys:
        kind, _name = core.parse_item(key)
        item = data["items"].get(key)
        if item is None:
            continue
        if kind in ("sketch", "construction"):
            if holder is None:
                holder = _target_body(doc, made_bodies, target_body, component)
            obj = (_build_sketch if kind == "sketch" else _build_datum)(master, item, holder)
            made[key] = obj.Name
        elif kind == "parameter":
            made[key] = _build_parameter(master, item)
    for key in keys:
        item = data["items"].get(key)
        if item is not None:
            labels.append("%s=%s" % (key, item.get("label") or item.get("name") or ""))
    results = core.result_map(master.Results)
    results.update(made)
    master.Results = core.result_entries(results)
    current = list(master.Items)
    master.Items = current + [k for k in keys if k not in current]
    master.ItemLabels = sorted(set(labels))
    return made


def derive(doc, source, keys, place_at_origin=False, target_body=None, component=None):
    """A new Derive in `doc` from `source` (read_source() data) with these item keys. No
    transaction of its own. Returns the Derive."""
    keys = [k for k in keys if k in source["items"]]
    if not keys:
        raise DeriveError("Tick at least one body, sketch, construction object or parameter.")
    master = make_master(doc, source["path"])
    master.PlaceAtOrigin = bool(place_at_origin)
    master.SourceStamp = source["stamp"]
    build(master, source, keys, target_body, component)
    log("derived %s from %s into %s" % (core.summary(keys), source["name"], doc.Label or doc.Name))
    return master


# -- results ---------------------------------------------------------------------------------------
def results(master):
    """{item key: object or parameter name} of what still exists."""
    doc = master.Document
    found = {}
    container = _params(doc)
    for key, name in core.result_map(master.Results).items():
        kind, _n = core.parse_item(key)
        if kind == "parameter":
            if container is not None and name in container.PropertiesList:
                found[key] = name
        elif doc.getObject(name) is not None:
            found[key] = name
    return found


def result_bodies(master):
    doc = master.Document
    out = []
    for key, name in results(master).items():
        if core.parse_item(key)[0] == "body":
            body = doc.getObject(name)
            if body is not None:
                out.append(body)
    return out


def result_steps(master):
    """The derived sketches and planes (they live in bodies)."""
    doc = master.Document
    out = []
    for key, name in results(master).items():
        if core.parse_item(key)[0] in ("sketch", "construction"):
            obj = doc.getObject(name)
            if obj is not None:
                out.append(obj)
    return out


def result_parameters(master):
    return [n for k, n in results(master).items() if core.parse_item(k)[0] == "parameter"]


def orphan_solids(doc):
    """Hidden solids of derived bodies that are gone (deleted with their body)."""
    used = set()
    for body in bodies.list_bodies(doc):
        base = getattr(body, "BaseFeature", None)
        if base is not None:
            used.add(base.Name)
    return [o for o in doc.Objects if bodies.kind(o) == SOLID_TYPE and o.Name not in used]


def _solid_holder(body):
    base = getattr(body, "BaseFeature", None)
    return base if bodies.kind(base) == SOLID_TYPE else None


# -- update ----------------------------------------------------------------------------------------
def update(master, data=None):
    """Bring the source's saved changes in. Returns the item keys no longer in the source
    (they keep their last shape). No transaction of its own."""
    if master.LinkBroken:
        raise DeriveError("The link to %s was broken: it no longer updates." % master.SourceName)
    if data is None:
        path = source_path(master)
        if path is None:
            raise DeriveError(core.state_words(core.MISSING, master.SourceName))
        data = read_source(path)
    doc = master.Document
    made = results(master)
    gone = []
    container = _params(doc)
    for key in master.Items:
        kind, _name = core.parse_item(key)
        item = data["items"].get(key)
        if item is None:
            gone.append(key)
            continue
        name = made.get(key)
        if name is None:
            continue  # deleted in this design: not brought back
        if kind == "body":
            body = doc.getObject(name)
            holder = _solid_holder(body) if body is not None else None
            if holder is not None:
                holder.Shape = _solid_shape(item, master.PlaceAtOrigin)
                holder.touch()
                _copy_look(body, item)
        elif kind == "sketch":
            sketch = doc.getObject(name)
            if sketch is not None:
                sketch.Placement = _place_for(item, master.PlaceAtOrigin)
                _fill_sketch(sketch, item)
        elif kind == "construction":
            datum = doc.getObject(name)
            if datum is not None:
                datum.Placement = _place_for(item, master.PlaceAtOrigin)
        elif kind == "parameter" and container is not None:
            try:
                if getattr(container, name) != item["value"]:
                    setattr(container, name, item["value"])
            except Exception as exc:
                warn("derive: parameter %s: %s" % (name, exc))
    master.SourceStamp = data["stamp"]
    if data.get("path"):
        master.SourceFile = data["path"]
        set_relative(master)
    set_warning(master, _gone_words(master, gone))
    log("%s updated from %s" % (master.Label, master.SourceName))
    return gone


def _gone_words(master, gone):
    if not gone:
        return ""
    labels = core.result_map(master.ItemLabels)
    names = [labels.get(k) or core.parse_item(k)[1] for k in gone]
    return "%s no longer has %s: kept as %s last was." % (
        master.SourceName,
        ", ".join(names),
        "it" if len(names) == 1 else "they",
    )


def set_place_at_origin(master, on, data):
    """Place Objects At Origin changed in the edit dialog: everything placed again."""
    if bool(master.PlaceAtOrigin) == bool(on):
        return
    master.PlaceAtOrigin = bool(on)
    doc = master.Document
    for key, name in results(master).items():
        kind, _n = core.parse_item(key)
        item = data["items"].get(key)
        obj = doc.getObject(name) if kind != "parameter" else None
        if item is None or obj is None:
            continue
        if kind == "body":
            holder = _solid_holder(obj)
            if holder is not None:
                holder.Shape = _solid_shape(item, master.PlaceAtOrigin)
        else:
            obj.Placement = _place_for(item, master.PlaceAtOrigin)


def remove_items(master, keys):
    """Take items out of a Derive (unticked in the edit dialog): their objects go, the steps
    built on them keep working where they can (delete.py). No transaction of its own."""
    from . import delete

    doc = master.Document
    made = results(master)
    body_objs, step_objs, params = [], [], []
    for key in keys:
        name = made.get(key)
        kind, _n = core.parse_item(key)
        if name is None:
            continue
        if kind == "parameter":
            params.append(name)
        elif kind == "body":
            body_objs.append(doc.getObject(name))
        else:
            step_objs.append(doc.getObject(name))
    if step_objs:
        delete.delete_steps(doc, [o for o in step_objs if o is not None])
    if body_objs:
        remove_bodies(doc, [b for b in body_objs if b is not None])
    _remove_parameters(doc, params)
    mapping = core.result_map(master.Results)
    for key in keys:
        mapping.pop(key, None)
    master.Results = core.result_entries(mapping)
    master.Items = [k for k in master.Items if k not in keys]


def remove_bodies(doc, targets):
    """Derived bodies with their hidden solid holders."""
    from . import delete

    holders = [_solid_holder(b) for b in targets]
    delete.delete_bodies(doc, targets)
    for holder in holders:
        if holder is not None and bodies.alive(holder):
            try:
                doc.removeObject(holder.Name)
            except Exception:
                pass


def _remove_parameters(doc, names):
    container = _params(doc)
    if container is None:
        return
    for name in names:
        if name in container.PropertiesList:
            try:
                container.setPropertyStatus(name, ["-ReadOnly"])
            except Exception:
                pass
            try:
                container.removeProperty(name)
            except Exception as exc:
                warn("derive: parameter %s stays: %s" % (name, exc))


def remove_master_parts(master):
    """What goes with a deleted Derive (delete.py): its parameters. Its bodies, sketches and
    planes are taken by delete.extra_steps / its step list."""
    _remove_parameters(master.Document, result_parameters(master))


def break_link(master):
    """Fusion's Break Link: the derived objects stay as they are and never update again;
    the derived parameters become ordinary user parameters. No transaction of its own."""
    if master.LinkBroken:
        return False
    container = _params(master.Document)
    for name in result_parameters(master):
        if container is None:
            break
        try:
            container.setPropertyStatus(name, ["-ReadOnly"])
        except Exception:
            pass
        try:
            container.setGroupOfProperty(name, "Parameters")
        except Exception as exc:
            warn("derive: parameter %s: %s" % (name, exc))
    master.LinkBroken = True
    set_warning(master, "")
    log("%s: link to %s broken" % (master.Label, master.SourceName))
    return True


def sources_of_file(path):
    """The source files a saved design's own Derives read (for the loop check), without
    opening it: read from the copy only when it has a Derive at all."""
    try:
        import zipfile

        with zipfile.ZipFile(path) as zf:
            xml = zf.read("Document.xml").decode("utf-8", "replace")
    except Exception:
        return []
    if "SourceFile" not in xml:
        return []
    import re

    from xml.sax.saxutils import unescape

    found = []
    for match in re.finditer(
        r'<Property name="SourceFile" type="App::PropertyString"[^>]*>\s*<String value="([^"]*)"',
        xml,
    ):
        found.append(unescape(match.group(1), {"&quot;": '"', "&apos;": "'"}))
    return found


def check(doc_file, source):
    """Refuse a derive that loops (DeriveError): the source, or a design it derives from
    (at any depth), derives from this design."""
    feeding, seen, todo = [], set(), [source]
    while todo and len(seen) < 200:
        path = todo.pop()
        norm = os.path.normcase(os.path.normpath(os.path.abspath(path)))
        if norm in seen:
            continue
        seen.add(norm)
        found = sources_of_file(path)
        feeding.extend(found)
        todo.extend(found)
    core.check_cycle(doc_file, source, feeding)
