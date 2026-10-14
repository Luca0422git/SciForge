# SPDX-License-Identifier: LGPL-2.1-or-later
"""INSPECT > Display Component Colors (Shift+N), Fusion-style: every component's bodies are
drawn in a colour of their own, so the parts of an assembly are told apart at a glance.
The same command (or Shift+N) again shows the bodies' own appearances. Only the display
changes: nothing is stored in the design or the undo history.

The colours are drawn like the analyses (surface_analysis_ui.colored_into): on the model's
own display triangles, whose faces are switched off meanwhile, with the edges on top. One Coin
node per design, put into each of its 3D views and drawn again after every change.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import components, log, warn
from . import surface_analysis as sa
from . import ui_icon_path
from .compat import QtCore

# One colour per component (the root component first), in turn.
PALETTE = [
    (0.36, 0.62, 0.92),
    (0.95, 0.62, 0.25),
    (0.42, 0.78, 0.45),
    (0.86, 0.38, 0.40),
    (0.67, 0.52, 0.88),
    (0.93, 0.83, 0.33),
    (0.35, 0.80, 0.80),
    (0.88, 0.50, 0.75),
    (0.62, 0.70, 0.35),
    (0.60, 0.45, 0.33),
]
NODE_NAME = "SciForgeComponentColors"
_STATE = {"on": set(), "nodes": {}, "observer": None, "pending": set(), "armed": False}


def is_on(doc=None):
    doc = doc or App.ActiveDocument
    return doc is not None and doc.Name in _STATE["on"]


def color_of(doc, owner):
    """The colour of the component `owner` (a body or loose solid) is in."""
    parts = components.list_components(doc)
    component = components.container_of(owner)
    index = 0 if component is None else 1 + parts.index(component)
    return PALETTE[index % len(PALETTE)]


def owners(doc):
    found = []
    for obj in doc.Objects:
        if sa.owner_of(obj) is not obj:
            continue
        try:
            if obj.ViewObject is None or not obj.ViewObject.Visibility:
                continue
            if obj.Shape.isNull() or not obj.Shape.Faces:
                continue
        except Exception:
            continue
        found.append(obj)
    return found


def _views(doc):
    try:
        gui = Gui.getDocument(doc.Name)
        return list(gui.mdiViewsOfType("Gui::View3DInventor")) if gui is not None else []
    except Exception:
        return []


def _detach(doc_name):
    node = _STATE["nodes"].pop(doc_name, None)
    if node is None:
        return
    try:
        doc = App.getDocument(doc_name)
    except Exception:
        doc = None
    if doc is not None:
        for view in _views(doc):
            try:
                root = view.getSceneGraph()
                index = root.findChild(node)
                if index >= 0:
                    root.removeChild(index)
            except Exception:
                continue
    node.unref()


def draw(doc):
    """Put the colours of `doc` in order (drawn again from its bodies now)."""
    from pivy import coin

    from . import surface_analysis_ui as ui

    _detach(doc.Name)
    if not is_on(doc):
        return
    node = coin.SoSeparator()
    node.setName(NODE_NAME)
    node.ref()
    pick = coin.SoPickStyle()
    pick.style = coin.SoPickStyle.UNPICKABLE
    node.addChild(pick)
    analysed = ui.analysed_owners(doc)  # an analysis shows on those
    for owner in owners(doc):
        if owner.Name in analysed:
            continue
        try:
            m = sa.mesh(owner, (), coarse=True)
            if not m.triangles:
                continue
            group = ui.group_for(coin, owner)
            color = color_of(doc, owner)
            ui.colored_into(coin, group, m, [color] * len(m.points), 0.0)
            node.addChild(group)
        except Exception as exc:
            warn("component colours of %s: %s" % (owner.Label, exc))
    _STATE["nodes"][doc.Name] = node
    for view in _views(doc):
        try:
            view.getSceneGraph().addChild(node)
        except Exception:
            continue
    _cover(doc)


def _cover(doc):
    """The model's own faces off under the colours (back on when they go)."""
    try:
        from . import surface_analysis_ui as ui

        ui.ensure_watch()
        ui.cover(doc)
        ui.redraw_views(doc)
    except Exception as exc:
        warn("component colours: %s" % exc)


def schedule(doc):
    try:
        _STATE["pending"].add(doc.Name)
    except Exception:
        return
    if not _STATE["armed"]:
        _STATE["armed"] = True
        QtCore.QTimer.singleShot(60, _run)


def _run():
    _STATE["armed"] = False
    names, _STATE["pending"] = _STATE["pending"], set()
    for name in names:
        try:
            doc = App.getDocument(name)
        except Exception:
            _STATE["on"].discard(name)
            _detach(name)
            continue
        try:
            if doc.Recomputing:
                schedule(doc)
                continue
            draw(doc)
        except Exception as exc:
            warn("component colours: %s" % exc)


class _Watch:
    def slotRecomputedDocument(self, doc):
        if is_on(doc):
            schedule(doc)

    def slotChangedObject(self, obj, prop):
        try:
            if prop in ("Visibility", "Placement", "Group") and is_on(obj.Document):
                schedule(obj.Document)
        except Exception:
            pass

    def slotDeletedObject(self, obj):
        try:
            if is_on(obj.Document):
                schedule(obj.Document)
        except Exception:
            pass

    def slotDeletedDocument(self, doc):
        try:
            _STATE["on"].discard(doc.Name)
            _STATE["nodes"].pop(doc.Name, None)
        except Exception:
            pass

    def slotUndoDocument(self, doc):
        if is_on(doc):
            schedule(doc)

    def slotRedoDocument(self, doc):
        if is_on(doc):
            schedule(doc)


def refresh_views(doc=None):
    """A new 3D view of a design (Viewports) shows its colours too."""
    doc = doc or App.ActiveDocument
    if doc is not None and is_on(doc):
        schedule(doc)


def toggle(doc=None):
    doc = doc or App.ActiveDocument
    if doc is None:
        from . import commands

        commands.tell("Open or start a design first.")
        return False
    if _STATE["observer"] is None:
        _STATE["observer"] = _Watch()
        App.addDocumentObserver(_STATE["observer"])
    if doc.Name in _STATE["on"]:
        _STATE["on"].discard(doc.Name)
        _detach(doc.Name)
        _cover(doc)
        log("component colours off")
    else:
        _STATE["on"].add(doc.Name)
        draw(doc)
        log("component colours on")
    return True


class ComponentColorsCommand:
    def GetResources(self):
        return {
            "MenuText": "Display Component Colors",
            "ToolTip": "Draw every component in a colour of its own (again: back to normal)",
            "Pixmap": ui_icon_path("component_colors"),
        }

    def IsActive(self):
        return True

    def Activated(self):
        try:
            toggle()
        except Exception as exc:
            warn("Display Component Colors: %s" % exc)


COMMANDS = {"SciForge_ComponentColors": ComponentColorsCommand}
