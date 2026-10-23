# SPDX-License-Identifier: LGPL-2.1-or-later
"""Opacity Control on bodies, mesh bodies and components (Fusion's browser right-click >
Opacity Control). The numbers and the rule are opacity_core.py; the menu and the Custom
Opacity dialog are opacity_ui.py.

Stored in the design: an `SciForgeOpacity` property (0..100 %) on the body, mesh body or
component, so it is saved with the file and one Ctrl+Z takes a change back. What shows is
FreeCAD's Transparency on the body's view and on each of its steps' views (FreeCAD shows a
body through its steps): apply() puts it there, and bodies_gui.sync() calls it after every
recompute, undo and redo, so a new step in a body (or a new body in a see-through
component) is see-through at once and an appearance put on later does not undo it.

The property is added before the undo step opens: undoing the first change then gives the
property its 100 % back (and the body its solid look) instead of taking the property away
while the body stays see-through.
"""

import FreeCAD as App

from . import bodies, components, log, warn
from . import opacity_core as core

PROP = "SciForgeOpacity"
# (document name, body name) left alone by apply(): a dialog showing that body its own way
# for a while (Combine shows its tool bodies see-through and puts their look back after).
HOLD = set()
_SHOWN = {}  # document name -> names of the bodies apply() made see-through last time


# -- reading -------------------------------------------------------------------------------------
def supports(obj):
    """Bodies, mesh bodies and components have an Opacity Control."""
    if obj is None:
        return False
    if bodies.is_body(obj) or components.is_component(obj):
        return True
    from . import mesh

    return mesh.is_mesh(obj)


def get(obj):
    """The opacity set on `obj` itself (100 when none was set)."""
    try:
        if obj is not None and PROP in obj.PropertiesList:
            return core.clamp(getattr(obj, PROP))
    except Exception:
        pass
    return core.DEFAULT


def _managed(chain):
    return any(PROP in getattr(o, "PropertiesList", ()) for o in chain)


def shown(obj):
    """The opacity `obj` shows: its own times its components' (a component: its own times
    the components it is in)."""
    return core.effective(get(obj), [get(c) for c in components.ancestors(obj)])


# -- changing ------------------------------------------------------------------------------------
def _ensure(obj):
    if PROP not in obj.PropertiesList:
        obj.addProperty(
            "App::PropertyInteger",
            PROP,
            "SciForge",
            "Opacity Control: 100 = solid, 0 = clear (times the components it is in)",
            4,  # hidden from FreeCAD's property editor
        )
        setattr(obj, PROP, core.DEFAULT)


def set_opacity(objects, value):
    """Give bodies / mesh bodies / components an opacity (0..100), one undo step. Returns
    the objects changed."""
    value = core.clamp(value)
    objects = [o for o in objects if supports(o) and bodies.alive(o)]
    if not objects:
        return []
    doc = objects[0].Document
    for obj in objects:
        _ensure(obj)
    changed = [o for o in objects if get(o) != value]
    if changed:
        doc.openTransaction("Opacity %s" % core.label(value))
        try:
            for obj in changed:
                setattr(obj, PROP, value)
        except Exception:
            doc.abortTransaction()
            raise
        doc.commitTransaction()
        log(
            "opacity %s: %s" % (core.label(value), ", ".join(o.Label for o in changed)),
        )
    apply(doc)
    return changed


# -- on screen -----------------------------------------------------------------------------------
def _base(body):
    """How see-through the body's own look is (an appearance like glass), in %."""
    try:
        from . import appearance

        look = appearance.effective(body)
        if look:
            return core.clamp(float(look.get("transparency", 0.0)) * 100.0)
    except Exception:
        pass
    return 0


def _views(obj):
    """The view objects whose Transparency makes `obj` look see-through: a body's own and
    its steps' (FreeCAD shows a body through them), a mesh body's."""
    views = []
    vobj = getattr(obj, "ViewObject", None)
    if vobj is not None and "Transparency" in vobj.PropertiesList:
        views.append(vobj)
    if bodies.is_body(obj):
        for step in obj.Group:
            try:
                if not step.isDerivedFrom("PartDesign::Feature"):
                    continue
                svobj = step.ViewObject
                if svobj is not None and "Transparency" in svobj.PropertiesList:
                    views.append(svobj)
            except Exception:
                continue
    return views


def _show(obj, transparency):
    for vobj in _views(obj):
        try:
            if int(vobj.Transparency) != transparency:
                vobj.Transparency = transparency
        except Exception:
            continue


def preview(objects, value):
    """Show `objects` at `value` % without changing the design (Custom Opacity's slider);
    apply() puts the design's own values back."""
    if not App.GuiUp:
        return
    for obj in objects:
        if not bodies.alive(obj):
            continue
        targets = [obj] if not components.is_component(obj) else _shapes_in(obj)
        for target in targets:
            others = [get(c) for c in components.ancestors(target) if c is not obj]
            own = value if target is obj else get(target)
            seen = core.effective(own, others + ([value] if target is not obj else []))
            _show(target, core.transparency(seen, _base(target)))


def _shapes_in(component):
    doc = component.Document
    found = components.bodies_in(doc, component, recursive=True)
    return found + [m for m in _meshes(doc) if components.is_inside(m, component)]


def _meshes(doc):
    from . import mesh

    return [o for o in doc.Objects if mesh.is_mesh(o)]


def apply(doc):
    """Every body and mesh body of the design shows its opacity (GUI only). Bodies nobody
    set an opacity on (nor on a component they are in) are left as they are."""
    if not App.GuiUp or doc is None:
        return
    try:
        shown_now = set()
        for obj in bodies.list_bodies(doc) + _meshes(doc):
            if (doc.Name, obj.Name) in HOLD:
                continue
            chain = [obj] + components.ancestors(obj)
            if not _managed(chain):
                if obj.Name in _SHOWN.get(doc.Name, ()):
                    _show(obj, _base(obj))  # its opacity was taken away (undo): solid again
                continue
            seen = core.effective(get(obj), [get(c) for c in chain[1:]])
            _show(obj, core.transparency(seen, _base(obj)))
            if seen < 100:
                shown_now.add(obj.Name)
        _SHOWN[doc.Name] = shown_now
    except Exception as exc:
        warn("opacity: %s" % exc)


def forget(doc_name):
    _SHOWN.pop(doc_name, None)
    for key in [k for k in HOLD if k[0] == doc_name]:
        HOLD.discard(key)
