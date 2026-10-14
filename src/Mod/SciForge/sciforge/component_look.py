# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Active Component Visibility (Preferences > General > Design, on by default): while
a component is active, everything outside it is drawn dimmed, see-through, so the active
component stands out; activating the design's root draws everything normally again. The
dimmed objects can still be picked.

It is a look only: a Coin material node that overrides the transparency is put at the top of
each dimmed object's own scene node (a body or a whole component outside the active one), so
nothing in the design changes (not saved, no undo step, no clash with Appearance, which
writes the bodies' own colours). The browser calls update() as it follows the active
component. GUI only.
"""

import FreeCAD as App

from . import components, prefs_core, warn

SEE_THROUGH = 0.75  # transparency of what lies outside the active component
GHOSTED_TYPES = ("App::Part", "PartDesign::Body", "Mesh::Feature", "Mesh::FeaturePython")

_STATE = {}  # document name -> {object name: the override node in its scene}


def enabled():
    try:
        return App.ParamGet(prefs_core.PREFS).GetBool("ActiveComponentVisibility", True)
    except Exception:
        return True


def wanted(doc, active):
    """Names of what is drawn dimmed while `active` (a component; None: the root) is active:
    at each level from the active component up to the root, everything beside the way down
    to it (root bodies, the other components, the bodies of the parent components)."""
    if active is None or doc is None:
        return set()
    names = set()
    chain = [active] + components.ancestors(active)
    holders = chain[1:] + [None]
    for keep, holder in zip(chain, holders):
        for member in components.members(doc, holder):
            if member is keep:
                continue
            try:
                if member.TypeId in GHOSTED_TYPES:
                    names.add(member.Name)
            except Exception:
                continue
    if holders[-1] is None:  # meshes and other solids at the root of the design
        for obj in doc.Objects:
            try:
                if obj.TypeId.startswith("Mesh::") and obj.getParentGeoFeatureGroup() is None:
                    names.add(obj.Name)
            except Exception:
                continue
    return names


def ghosted(doc):
    """Names of the objects drawn dimmed now (tests, diagnostics)."""
    if doc is None:
        return set()
    return set(_STATE.get(doc.Name, {}))


def update(doc):
    """Dim what lies outside the active component (Fusion), undim the rest."""
    if doc is None or not App.GuiUp:
        return
    try:
        active = components.active_component(doc) if enabled() else None
        wanted_names = wanted(doc, active)
    except Exception as exc:
        warn("component look: %s" % exc)
        return
    have = _STATE.setdefault(doc.Name, {})
    for name in list(have):
        obj = doc.getObject(name)
        if name not in wanted_names or obj is None:
            _undim(obj, have.pop(name))
    for name in wanted_names:
        obj = doc.getObject(name)
        if obj is None:
            continue
        node = have.get(name)
        root = _root(obj)
        if root is None:
            continue
        if node is not None and root.findChild(node) >= 0:
            continue
        node = node or _override()
        try:
            root.insertChild(node, 0)
            have[name] = node
        except Exception as exc:
            warn("component look: %s" % exc)


def refresh_all():
    """The preference changed: every open design follows it."""
    for doc in App.listDocuments().values():
        update(doc)


def forget(doc_name):
    _STATE.pop(doc_name, None)


def _root(obj):
    try:
        vobj = obj.ViewObject
        return vobj.RootNode if vobj is not None else None
    except Exception:
        return None


def _override():
    from pivy import coin

    node = coin.SoMaterial()
    node.setName("SciForgeActiveComponentVisibility")
    node.transparency.setValue(SEE_THROUGH)
    for field in (
        node.ambientColor,
        node.diffuseColor,
        node.specularColor,
        node.emissiveColor,
        node.shininess,
    ):
        field.setIgnored(True)
    node.setOverride(True)
    node.ref()  # ours: kept alive while it is out of the scene
    return node


def _undim(obj, node):
    root = _root(obj) if obj is not None else None
    try:
        if root is not None:
            index = root.findChild(node)
            if index >= 0:
                root.removeChild(index)
    except Exception as exc:
        warn("component look: %s" % exc)
    try:
        node.unref()
    except Exception:
        pass
