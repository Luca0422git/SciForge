# SPDX-License-Identifier: LGPL-2.1-or-later
"""Components, the way Fusion has them, on FreeCAD's document (no Qt: the golden-model
builder, headless tests and the dialogs all use this).

The model (a contract other features rely on, see docs/sciforge/parity/components.md):

- A component is an ``App::Part`` container. Its name in the browser is its ``Label``.
  Bodies (``PartDesign::Body``) live inside it (``part.Group``), and sketches, features and
  construction geometry live inside their body as FreeCAD's PartDesign needs. A nested
  component is an ``App::Part`` inside an ``App::Part``.
- The root component is the document itself: a design with no component has no container
  at all, so every single-body workflow and file from before components keeps working.
- One component is **active** and gets every new sketch, body and feature. FreeCAD's own
  active-object slot "part" (``Gui.ActiveDocument.ActiveView.setActiveObject("part", obj)``)
  holds it; the active body (slot "pdbody") always lies inside it. ``active_component()``
  reads it: the active body's container when a body is active, else the "part" slot, else
  the root (None). A file opens with the root active (Fusion does the same).
- ``commands.find_body()`` / ``commands.ensure_body()`` give a body *inside* the active
  component (creating one there when it has none), so every command that puts work into
  "the body" puts it into the active component.

    list_components(doc)          every component, in the order they were made
    container_of(obj)             the component an object (body, sketch, component) is in
    component_of(obj)             the same, but a component is its own component
    is_inside(obj, component)     obj lies in component (or in one inside it); root: True
    bodies_in(doc, component)     the bodies directly in a component (None: the root)
    components_in(doc, component) the components directly in a component (None: the root)
    new_component(doc, label, parent)   an empty component (no undo step of its own)
    new_body_in(doc, container)         an empty body in a component ("Body1" per component)
    from_bodies(doc, bodies)            Create Components from Bodies: one per body
    place(obj, component)               move a body / component into another (None: root)
    remove(doc, component)              delete a component with everything inside it
    active_component(doc) / set_active(component) / activate_body(body)   (GUI)
"""

import FreeCAD as App

from . import components_core as core
from . import log, warn

PART = "App::Part"
BODY = "PartDesign::Body"
TYPE_PROP = "SciForgeType"
COMPONENT_TYPE = "Component"

# component name -> name of the body that was last active in it (per document)
_last_body = {}


# -- reading the tree ------------------------------------------------------------------------
def is_component(obj):
    try:
        return obj is not None and obj.TypeId == PART
    except Exception:
        return False


def is_body(obj):
    try:
        return obj is not None and obj.TypeId == BODY
    except Exception:
        return False


def alive(obj):
    if obj is None:
        return False
    try:
        if hasattr(obj, "isAttachedToDocument"):
            return bool(obj.isAttachedToDocument())
        return bool(obj.Name)
    except Exception:
        return False


def list_components(doc):
    if doc is None:
        return []
    return sorted([o for o in doc.Objects if o.TypeId == PART], key=lambda o: o.ID)


def _parent_group(obj):
    try:
        return obj.getParentGeoFeatureGroup()
    except Exception:
        return None


def container_of(obj):
    """The component ``obj`` is in (None: the root). A body's sketch is in the body's
    component; a component's own origin planes are in that component."""
    parent = _parent_group(obj)
    while parent is not None and parent.TypeId != PART:
        parent = _parent_group(parent)
    return parent


def component_of(obj):
    """Like container_of, but a component is its own component."""
    if is_component(obj):
        return obj
    return container_of(obj)


def ancestors(obj):
    """Containers of obj, nearest first."""
    found = []
    current = container_of(obj)
    while current is not None and current not in found:
        found.append(current)
        current = container_of(current)
    return found


def is_inside(obj, component):
    """obj lies in component, at any depth (the root holds everything)."""
    if component is None:
        return True
    if obj is None:
        return False
    if obj is component:
        return True
    return any(c is component for c in ancestors(obj))


def members(doc, component):
    """Objects directly in a component (None: the root level of the document)."""
    if component is not None:
        return list(component.Group)
    return [o for o in doc.Objects if o.TypeId in (PART, BODY) and _parent_group(o) is None]


def bodies_in(doc, component, recursive=False):
    """Bodies in a component (None: at the root), in the order they were made."""
    if recursive and component is not None:
        found = [o for o in doc.Objects if o.TypeId == BODY and is_inside(o, component)]
    else:
        found = [o for o in members(doc, component) if o.TypeId == BODY]
    return sorted(found, key=lambda o: o.ID)


def components_in(doc, component):
    found = [o for o in members(doc, component) if o.TypeId == PART]
    return sorted(found, key=lambda o: o.ID)


def parents_map(doc):
    """{unit name: container name or None} for every body and component (components_core)."""
    found = {}
    for obj in doc.Objects:
        if obj.TypeId in (PART, BODY):
            container = container_of(obj)
            found[obj.Name] = container.Name if container is not None else None
    return found


def component_names(doc):
    return {o.Name for o in doc.Objects if o.TypeId == PART}


def label_of(component):
    """What the browser calls a component (the root is the design's name)."""
    if component is None:
        return None
    return component.Label


# -- making and changing -----------------------------------------------------------------------
def next_label(doc):
    return core.next_label([o.Label for o in list_components(doc)])


def mark(part):
    """Tag a component as SciForge's (the timeline shows it as a Component step either way)."""
    try:
        if TYPE_PROP not in part.PropertiesList:
            part.addProperty(
                "App::PropertyString", TYPE_PROP, "SciForge", "SciForge object kind", 0
            )
            part.setEditorMode(TYPE_PROP, 2)
        if getattr(part, TYPE_PROP) != COMPONENT_TYPE:
            setattr(part, TYPE_PROP, COMPONENT_TYPE)
    except Exception as exc:
        warn("could not tag component %s: %s" % (part.Label, exc))


def new_component(doc, label=None, parent=None):
    """A new, empty component (no undo step of its own: the caller's transaction holds it).
    ``parent``: the component it goes into (None: the root). Its origin is hidden, as a
    body's is."""
    label = label or next_label(doc)
    part = doc.addObject(PART, "Component")
    part.Label = label
    mark(part)
    if parent is not None and is_component(parent):
        parent.addObject(part)
    try:
        if part.Origin is not None and part.Origin.ViewObject is not None:
            part.Origin.ViewObject.Visibility = False
    except Exception:
        pass
    log("component %s created%s" % (label, " in %s" % parent.Label if parent is not None else ""))
    return part


def body_label_in(doc, container, exclude=None):
    """The next body label in a component. `exclude`: a body already placed there that is
    being named (it must not count itself)."""
    labels = [b.Label for b in bodies_in(doc, container) if b is not exclude]
    return core.body_label(labels)


def new_body_in(doc, container, label=None):
    """A new, empty body inside a component (None: the root). Bodies are numbered per
    component, like Fusion's (the first body of a new component is Body1)."""
    label = label or body_label_in(doc, container)
    body = doc.addObject(BODY, "Body")
    if container is not None:
        container.addObject(body)
    body.Label = label
    return body


def body_for_new(src_body, component=False):
    """The body a feature's New Body / New Component result goes into: a new body beside
    the source body, or a new body inside a new component. Fusion puts the new component
    under the active component (the source body's one when no GUI decides)."""
    doc = src_body.Document
    if not component:
        return new_body_in(doc, container_of(src_body))
    parent = active_component(doc) if App.GuiUp else container_of(src_body)
    part = new_component(doc, parent=parent)
    return new_body_in(doc, part)


def drop_if_empty(component):
    """Remove a component SciForge made when nothing is left in it (the body of a failed
    New Component preview was just removed). False when it stays."""
    if not is_component(component) or getattr(component, TYPE_PROP, "") != COMPONENT_TYPE:
        return False
    try:
        if list(component.Group):
            return False
        doc = component.Document
        doc.removeObject(component.Name)
        return True
    except Exception as exc:
        warn("could not remove the empty component: %s" % exc)
        return False


def place(obj, component, keep_position=True):
    """Move a body or component into ``component`` (None: the root). Returns True when it
    moved. Refused (False) when it would put a component inside itself. ``keep_position``:
    it stays where it is in the design (a moved existing body); False for a new, empty body,
    which starts at its new component's origin like any body made there."""
    if obj is None:
        return False
    if component is not None and (component is obj or is_inside(component, obj)):
        warn("%s cannot be moved into itself" % obj.Label)
        return False
    current = container_of(obj)
    if current is component:
        return False
    # The body stays where it is on the screen (Fusion): a component that a joint or Move
    # has moved carries a Placement of its own, so the moved object's own Placement is
    # changed by the difference between the old and the new container.
    before = _container_placement(current)
    after = _container_placement(component)
    if current is not None:
        current.removeObject(obj)
    if component is not None:
        component.addObject(obj)
    try:
        if keep_position and not before.isSame(after, 1e-12):
            obj.Placement = after.inverse().multiply(before).multiply(obj.Placement)
    except Exception as exc:
        warn("%s: could not keep its position: %s" % (obj.Label, exc))
    log("%s moved to %s" % (obj.Label, component.Label if component is not None else "the root"))
    return True


def _container_placement(component):
    """The placement a component gives what is inside it, in the design (its own placement
    times its parents'); identity for the root."""
    if component is None:
        return App.Placement()
    try:
        return component.getGlobalPlacement()
    except Exception:
        return App.Placement(component.Placement)


KEEP = object()  # from_bodies: each component goes where its body was


def from_bodies(doc, bodies, parent=KEEP, label=None):
    """Create Components from Bodies: one component per body, named after the body, with
    the body inside it; the body's sketches go with the body (they are inside it), as in
    Fusion where "the sketch is still resident at the top level" only for sketches outside
    the body. ``parent``: where the components go: KEEP (each body's own container, the
    right-click command), None (the root) or a component (the dialog's Parent)."""
    made = []
    for body in bodies:
        if not is_body(body):
            continue
        where = container_of(body) if parent is KEEP else parent
        name = label if (label and len(bodies) == 1) else body.Label
        part = new_component(doc, name, where)
        part.addObject(body)
        made.append(part)
    return made


def remove(doc, component, _top=True):
    """Delete a component with everything inside it, as one undo step (Fusion: Delete on a
    component takes its bodies and nested components with it)."""
    from . import timeline_ops as ops

    if not is_component(component):
        return False
    if _top:
        ops._transaction(doc, "Delete %s" % component.Label)
    try:
        for child in components_in(doc, component):
            remove(doc, child, _top=False)
        names = [b.Name for b in bodies_in(doc, component)]
        if names:
            ops.delete_bodies(doc, names, transaction=False)
        for left in list(component.Group):  # anything else that was put in (a datum...)
            if doc.getObject(left.Name) is not None:
                doc.removeObject(left.Name)
        name, label = component.Name, component.Label
        doc.removeObject(name)
        log("component %s deleted" % label)
    except Exception:
        if _top:
            doc.abortTransaction()
            ops.recompute(doc)
        raise
    if _top:
        ops.recompute(doc)
        doc.commitTransaction()
    return True


def rename(doc, component, text):
    from . import timeline_ops as ops

    return ops.rename(doc, component.Name, text)


def origin_owner(feature):
    """The body or component whose origin plane/axis ``feature`` is, or None."""
    try:
        for origin in feature.InList:
            if origin.TypeId == "App::Origin":
                for owner in origin.InList:
                    if owner.TypeId in (PART, BODY):
                        return owner
    except Exception:
        pass
    return None


def same_role_plane(body, plane):
    """A body's own origin plane with the role of ``plane`` (a component's origin plane
    clicked in the browser: the sketch goes on the body's matching plane, which lies at
    the same place)."""
    role = getattr(plane, "Role", "")
    try:
        for feature in body.Origin.OriginFeatures:
            if getattr(feature, "Role", "") == role:
                return feature
    except Exception:
        pass
    return plane


# -- the active component (GUI) -------------------------------------------------------------
def _view(doc=None):
    if not App.GuiUp:
        return None
    try:
        import FreeCADGui as Gui

        gdoc = Gui.ActiveDocument if doc is None else Gui.getDocument(doc.Name)
        if gdoc is None:
            return None
        return gdoc.ActiveView
    except Exception:
        return None


def _in_doc(obj, doc):
    try:
        return alive(obj) and (doc is None or obj.Document is doc)
    except Exception:
        return False


def active_body(doc=None):
    view = _view(doc)
    if view is None:
        return None
    try:
        body = view.getActiveObject("pdbody")
    except Exception:
        return None
    return body if _in_doc(body, doc) and is_body(body) else None


def active_component(doc=None):
    """The active component (None: the root). The active body's container decides when
    a body is active (FreeCAD only sets the "part" slot from its own tree), else the "part"
    slot."""
    if doc is None:
        doc = App.ActiveDocument
    if doc is None:
        return None
    body = active_body(doc)
    if body is not None:
        return container_of(body)
    view = _view(doc)
    if view is None:
        return None
    try:
        part = view.getActiveObject("part")
    except Exception:
        return None
    return part if _in_doc(part, doc) and is_component(part) else None


def _set_slot(doc, slot, obj):
    view = _view(doc)
    if view is None:
        return
    try:
        view.setActiveObject(slot, obj)
    except Exception as exc:
        warn("could not set the active %s: %s" % (slot, exc))


def remember(body):
    """Keep the body that was active in its component, so activating the component again
    gives new work to the same body."""
    if not is_body(body):
        return
    container = container_of(body)
    key = (body.Document.Name, container.Name if container is not None else None)
    _last_body[key] = body.Name


def preferred_body(doc, component):
    """The body new work goes to in a component: the one that was active there last, else
    the oldest body directly in it (a reopened file has none active), else None."""
    key = (doc.Name, component.Name if component is not None else None)
    name = _last_body.get(key)
    if name:
        body = doc.getObject(name)
        if is_body(body) and container_of(body) is component:
            return body
    found = bodies_in(doc, component)
    return found[0] if found else None


def activate_body(body):
    """Make a body the active one; its component becomes the active component with it
    (the active body always lies in the active component)."""
    if not is_body(body):
        return
    doc = body.Document
    _set_slot(doc, "pdbody", body)
    _set_slot(doc, "part", container_of(body))
    remember(body)


def sync_part_slot(body):
    """Align FreeCAD's "part" slot with the active body's container (FreeCAD only sets it
    on a double-click in its own tree)."""
    if not is_body(body):
        return
    view = _view(body.Document)
    if view is None:
        return
    try:
        current = view.getActiveObject("part")
    except Exception:
        current = None
    wanted = container_of(body)
    if current is not wanted:
        _set_slot(body.Document, "part", wanted)
    remember(body)


def set_active(component, doc=None):
    """Activate a component (None: the root). Its preferred body becomes the active body;
    with no body in it, no body is active until one is made (ensure_body puts it here)."""
    if doc is None:
        doc = component.Document if component is not None else App.ActiveDocument
    if doc is None:
        return
    if component is not None and not is_component(component):
        return
    body = preferred_body(doc, component)
    _set_slot(doc, "part", component)
    _set_slot(doc, "pdbody", body)
    if body is not None:
        remember(body)
    log("component %s activated" % (component.Label if component is not None else "root"))


def forget(doc_name):
    for key in [k for k in _last_body if k[0] == doc_name]:
        _last_body.pop(key, None)


# -- isolate -----------------------------------------------------------------------------------
def isolate_hidden(doc, target):
    """The bodies and components Isolate hides for ``target`` (names)."""
    return core.isolate_hidden(parents_map(doc), target.Name)


def move_targets(doc, moving):
    """[(label, component or None)] the objects ``moving`` may be moved into."""
    names = core.move_targets(
        parents_map(doc), [o.Name for o in list_components(doc)], [o.Name for o in moving]
    )
    found = []
    for name in names:
        if name is None:
            found.append((doc.Label + " (root)", None))
        else:
            obj = doc.getObject(name)
            if obj is not None:
                found.append((obj.Label, obj))
    return found
