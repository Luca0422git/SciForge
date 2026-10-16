# SPDX-License-Identifier: LGPL-2.1-or-later
"""STEP and IGES files with their structure, without Qt (File > Open, Insert STEP): every
product of the file becomes a component, nested as in the file, named after it, with its
solids as bodies and its colours; a part used twice comes in once and the other occurrences
are linked copies of it (instances.py). The rules are in exchange_core.py, the spec in
docs/sciforge/parity/insert-export.md ("Part 2").

How the file is read: FreeCAD's own reader (Import.insert with link groups, the reader of
FreeCAD 1.x that keeps assemblies) runs in a hidden throw-away document; every node of what
it builds (App::LinkGroup = an assembly, Part::Feature = a part, App::Link = a repeated
occurrence) is turned into a plain node with its solids in the file's coordinates; then the
throw-away document is closed and SciForge's components and bodies are made from the nodes.
"""

import FreeCAD as App

from . import bodies, components, insert, instances, log, warn
from . import exchange_core as core

UNIT_TYPES = ("App::LinkGroup", "App::Part", "App::Link")
SKIP_TYPES = ("App::Origin", "App::Line", "App::Plane", "App::Point")
SOURCE = "SourceFile"


class Made:
    """What one import made: the file's component (Insert), every component, the copies
    (instances) and the bodies, in the order they were made."""

    def __init__(self):
        self.top = None
        self.components = []
        self.instances = []
        self.bodies = []
        self.built = {}  # file key -> component


# -- reading -----------------------------------------------------------------------------------
def read_tree(path):
    """The file's top nodes (exchange_core.node), with each part's solids in the file's
    coordinates as (shape, [colours], surface?) and each node's placement in the file."""
    import os

    import Import

    if not path or not os.path.isfile(path):
        raise core.ExchangeError("The file was not found: %s" % (path or "(no file)"))
    if core.file_kind(path) not in ("step", "iges"):
        raise core.ExchangeError("Choose a STEP (.step, .stp) or IGES (.iges, .igs) file.")
    doc, active = insert._temp_document()
    try:
        try:
            found = Import.insert(
                path, doc.Name, importHidden=False, merge=False, useLinkGroup=True, mode=0
            )
        except Exception as exc:
            raise core.ExchangeError("The file could not be read: %s" % exc)
        doc.recompute()
        colours = {}
        for feature, values in found or []:
            try:
                colours[feature.Name] = [tuple(float(c) for c in v[:3]) for v in values]
            except Exception:
                pass
        units = [o for o in doc.Objects if o.TypeId not in SKIP_TYPES]
        names = {o.Name for o in units}
        tops = [o for o in units if not any(p.Name in names for p in o.InList if p is not o)]
        nodes = [_walk(top, top, "", colours) for top in tops]
        nodes = [n for n in nodes if n is not None]
        if not nodes:
            raise core.ExchangeError("Nothing could be read from the file.")
        if not any(_has_pieces(n) for n in nodes):
            raise core.ExchangeError(
                "The file holds no solid or surface body (lines and points are not taken)."
            )
        return nodes
    finally:
        insert._close_temp(doc, active)


def _has_pieces(n):
    return bool(n["pieces"]) or any(_has_pieces(c) for c in n["children"])


def _place(top, sub):
    """The placement of the node at `sub` under `top`, in the file's coordinates."""
    if not sub:
        return App.Placement(top.Placement)
    try:
        found = top.getSubObject(sub, retType=2)
        return App.Placement(found[1])
    except Exception:
        return App.Placement()


def _children_of(obj):
    if obj.TypeId == "App::LinkGroup":
        return list(obj.ElementList)
    if obj.TypeId == "App::Part":
        return [c for c in obj.Group if c.TypeId not in SKIP_TYPES]
    return []


def _walk(top, obj, sub, colours):
    """A node for `obj`, reached from `top` by the sub-object path `sub`."""
    link = None
    target = obj
    if obj.TypeId == "App::Link":
        try:
            target = obj.getLinkedObject(True)
        except Exception:
            target = obj.LinkedObject
        if target is None or target is obj:
            return None
        link = target.Name
    place = _place(top, sub)
    kids = _children_of(target)
    if kids or target.TypeId in ("App::LinkGroup", "App::Part"):
        children = []
        for child in kids:
            n = _walk(top, child, sub + child.Name + ".", colours)
            if n is not None:
                children.append(n)
        return core.node(
            obj.Label, core.ASSEMBLY, key=target.Name, link=link, children=children, place=place
        )
    shape = _shape(top, sub)
    if shape is None:
        return None
    return core.node(
        obj.Label,
        core.PART,
        key=target.Name,
        link=link,
        pieces=_pieces(shape, colours.get(target.Name, [])),
        place=place,
    )


def _shape(top, sub):
    import Part

    try:
        shape = Part.getShape(top, sub) if sub else Part.getShape(top)
    except Exception:
        return None
    if shape is None or shape.isNull():
        return None
    return shape


def _pieces(shape, colours):
    """[(shape, colours, surface)] of a part: its solids; a file of faces only (IGES often
    is) is sewn: closed shells become solids, open ones surface bodies."""
    import Part

    found = list(shape.Solids)
    surface = False
    if not found and shape.Faces:
        sewn = Part.makeCompound([f.copy() for f in shape.Faces])
        try:
            sewn.sewShape()
        except Exception as exc:
            warn("import: faces not sewn (%s)" % exc)
        shells = list(sewn.Shells) or [Part.Shell(list(sewn.Faces))]
        for shell in shells:
            try:
                if shell.isClosed():
                    solid = Part.Solid(shell)
                    if solid.Volume < 0:
                        solid.reverse()
                    found.append(solid)
                    continue
            except Exception:
                pass
            found.append(shell)
            surface = True
    pieces = []
    total = sum(len(p.Faces) for p in found)
    start = 0
    for piece in found:
        count = len(piece.Faces)
        if colours and len(colours) == total:
            mine = colours[start : start + count]
        else:
            mine = colours[:1]
        start += count
        pieces.append((piece, mine, surface and not piece.Solids))
    return pieces


# -- building ----------------------------------------------------------------------------------
def import_file(doc, path, mode=core.OPEN, parent=None, label=None):
    """Bring a STEP / IGES file into `doc` with its structure. mode OPEN: the file's top
    product is the design (File > Open into a new design); INSERT: the whole file becomes
    one component (named `label`, else after the file) inside `parent` (None: the root).
    No undo step of its own (the caller's). Returns a Made."""
    tops = read_tree(path)
    name = label or core.base_name(path)
    level = core.plan(tops, mode, name)
    made = Made()
    container = parent
    if level["component"]:
        container = components.new_component(doc, _component_label(doc, name), parent)
        made.top = container
        made.components.append(container)
    origin = components._container_placement(container)
    top = level["top"]
    at_root = container is None
    part_name = level["part_name"] if at_root else (top and top["name"])
    _bodies(doc, container, level["pieces"], App.Placement(), at_root, part_name, made)
    for child in level["children"]:
        _component(doc, child, container, App.Placement(), origin, made)
    doc.recompute()
    _finish_bodies(made, path)
    log(
        "%s %s"
        % (
            "opened" if mode == core.OPEN else "inserted",
            core.describe(
                len(made.components) - (1 if made.top is not None else 0),
                len(made.instances),
                len(made.bodies),
                name,
            ),
        )
    )
    return made


def _component_label(doc, name):
    labels = {c.Label for c in components.list_components(doc)}
    label, n = name, 1
    while label in labels:
        n += 1
        label = "%s (%d)" % (name, n)
    return label


def _component(doc, n, container, parent_place, origin, made):
    """One node as a component in `container`; parent_place: the container's placement in
    the file; origin: the level's placement in the design (for copies)."""
    key = n.get("link")
    if key and key in made.built:
        source = made.built[key]
        wanted = origin.multiply(n["place"])
        try:
            made.instances.append(instances.make_instance(source, container, placement=wanted))
            return
        except Exception as exc:
            warn("import: %s made as its own component (%s)" % (n["name"], exc))
    comp = components.new_component(doc, n["name"] or "Component", container)
    comp.Placement = parent_place.inverse().multiply(n["place"])
    made.components.append(comp)
    for k in (n.get("key"), n.get("folded")):
        if k and k not in made.built:
            made.built[k] = comp
    _bodies(doc, comp, n["pieces"], n["place"], False, n["name"], made)
    for child in n["children"]:
        _component(doc, child, comp, n["place"], origin, made)


def _bodies(doc, container, pieces, frame, at_root, part_name, made):
    """A body per piece in `container`, its shape moved from the file's coordinates into
    the container's (`frame`: the container's placement in the file)."""
    labels = core.body_labels(len(pieces), at_root, part_name)
    taken = set()
    inverse = frame.inverse().toMatrix()
    for (shape, colours, surface), label in zip(pieces, labels):
        local = bodies.baked(shape)
        if not frame.isIdentity():
            local.transformShape(inverse, True)
        if at_root:
            label = insert._unique_label(doc, label, taken)
        body = components.new_body_in(doc, container, label)
        base = doc.addObject("Part::Feature", "ImportedShape")
        base.Label = body.Label + " (imported)"
        base.Shape = local
        if container is not None:
            container.addObject(base)  # FreeCAD's link scope: the base sits in the component
        body.BaseFeature = base
        made.bodies.append((body, colours, base))


def _finish_bodies(made, path):
    for body, colours, base in made.bodies:
        tip = body.Tip
        if tip is not None:
            bodies.mark(tip, insert.TYPE_STEP)
            bodies.add_prop(tip, "App::PropertyString", SOURCE, "Insert", "The file it came from")
            setattr(tip, SOURCE, path)
        insert._colour_body(body, colours)
        try:
            if base.ViewObject is not None:
                base.ViewObject.Visibility = False
        except Exception:
            pass
    made.bodies = [b for b, _c, _base in made.bodies]
    # The copies were made before their source bodies had their colours.
    try:
        from . import appearance

        for inst in made.instances:
            for feature, copy in instances.copy_features(inst):
                source = getattr(feature, "Source", None)
                if source is not None and copy is not None:
                    appearance.copy_body_appearance(source, copy)
    except Exception as exc:
        warn("import: the copies' colours were not copied (%s)" % exc)


def apply_looks(made):
    """The bodies' appearance on screen (GUI), copies included."""
    try:
        from . import appearance

        for body in made.bodies:
            appearance.apply(body)
        for inst in made.instances:
            for body in components.bodies_in(inst.Document, inst, recursive=True):
                appearance.apply(body)
    except Exception as exc:
        warn("import: looks not applied (%s)" % exc)
