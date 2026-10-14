# SPDX-License-Identifier: LGPL-2.1-or-later
"""Copy (Ctrl+C), Paste (Ctrl+V) and Paste New of components and bodies, Fusion's way.

  Copy       remembers the selected components / bodies (a browser row, or something of
             them clicked in the 3D view)
  Paste      a component: a linked instance ("Bracket:2", instances.py: editing the
             original changes it too), in the active component (or the component whose
             row was right-clicked); a body: Move/Copy opens with Create Copy on
  Paste New  a component: an independent copy ("Bracket (1)") with its own features
  then       Move/Copy opens on what was pasted (Fusion's manipulator), to put it in place;
             Cancel leaves it where it was pasted (right on the original)

In a sketch the keys copy and paste sketch curves (sketch_mode). Each paste is one undo
step; the move after it is its own.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, components, instances, log, ui_icon_path, warn
from .compat import QtCore

_CLIP = {"doc": None, "names": []}


def _in_sketch():
    try:
        edit = Gui.ActiveDocument.getInEdit() if Gui.ActiveDocument is not None else None
        obj = edit.Object if edit is not None else None
        return obj is not None and obj.TypeId == "Sketcher::SketchObject"
    except Exception:
        return False


def _selected(doc):
    """Components and bodies selected (a body clicked in a component copies the body;
    a component row the component)."""
    from . import bodies
    from .bodies_panel import preselection

    found = []
    for obj, short, _point in preselection():
        if obj.Document is not doc:
            continue
        if components.is_component(obj) and not short:
            target = obj
        else:
            target = bodies.body_of(obj)
        if target is not None and target not in found:
            found.append(target)
    return found


def copy(objects=None):
    """Remember components / bodies for Paste. Returns how many."""
    doc = App.ActiveDocument
    if doc is None:
        commands.tell("Open or start a design first.")
        return 0
    objects = [o for o in (objects if objects is not None else _selected(doc)) if o is not None]
    if not objects:
        commands.tell("Select a component or a body to copy (click it, or its browser row).")
        return 0
    _CLIP["doc"] = doc.Name
    _CLIP["names"] = [o.Name for o in objects]
    log("copied: %s" % ", ".join(o.Label for o in objects))
    return len(objects)


def clipboard(doc=None):
    """The copied objects that still exist (in `doc`, default the active design)."""
    doc = doc or App.ActiveDocument
    if doc is None or _CLIP["doc"] != doc.Name:
        return []
    found = [doc.getObject(n) for n in _CLIP["names"]]
    return [o for o in found if o is not None]


def has_components(doc=None):
    return any(components.is_component(o) for o in clipboard(doc))


def has_anything(doc=None):
    return bool(clipboard(doc))


def _target(doc, source, into):
    """Where a pasted component goes: the right-clicked component, else the active one;
    never into the copied component itself (its container then)."""
    target = into if into is not None else components.active_component(doc)
    if target is not None and components.is_inside(target, source):
        target = components.container_of(source)
    return target


def paste(into=None, new=False):
    """Paste (or Paste New) what was copied; then Move/Copy opens on it."""
    doc = App.ActiveDocument
    if doc is None:
        commands.tell("Open or start a design first.")
        return []
    found = clipboard(doc)
    if not found:
        commands.tell("Nothing to paste: select a component or a body and press Ctrl+C first.")
        return []
    if not commands.finish_open_dialog():
        return []
    parts = [o for o in found if components.is_component(o)]
    others = [o for o in found if not components.is_component(o)]
    made = []
    if parts:
        doc.openTransaction("Paste New" if new else "Paste")
        try:
            for part in parts:
                where = _target(doc, instances.definition(part) or part, into)
                if new:
                    made.append(instances.paste_new(part, where))
                else:
                    made.append(instances.make_instance(part, where))
            doc.recompute()
        except Exception as exc:
            doc.abortTransaction()
            doc.recompute()
            commands.tell("Could not paste: %s" % exc)
            warn("paste: %s" % exc)
            return []
        doc.commitTransaction()
        log("pasted %s" % ", ".join(p.Label for p in made))
        _refresh_browser()
        QtCore.QTimer.singleShot(0, lambda: _move_after(doc.Name, [p.Name for p in made]))
    elif others:
        bodies = [o for o in others if o.TypeId == "PartDesign::Body"]
        QtCore.QTimer.singleShot(0, lambda: _copy_bodies(doc.Name, [b.Name for b in bodies]))
    return made


def _move_after(doc_name, names):
    """Fusion opens the move manipulator on what was pasted."""
    try:
        if doc_name not in App.listDocuments():
            return
        doc = App.getDocument(doc_name)
        parts = [doc.getObject(n) for n in names]
        parts = [p for p in parts if p is not None]
        if not parts:
            return
        from . import component_move_ui

        component_move_ui.start(picks=parts)
    except Exception as exc:
        warn("paste: the move could not start: %s" % exc)


def _copy_bodies(doc_name, names):
    """A pasted body: Move/Copy with the body picked and Create Copy on."""
    try:
        if doc_name not in App.listDocuments() or not names:
            return
        doc = App.getDocument(doc_name)
        found = [doc.getObject(n) for n in names]
        found = [b for b in found if b is not None]
        from . import move_ui
        from .bodies_panel import start

        start(move_ui.MovePanel, carry={"copy": True}, picks=found)
    except Exception as exc:
        warn("paste: %s" % exc)


def _refresh_browser():
    try:
        from . import browser_ui

        tree = browser_ui.widget()
        if tree is not None:
            tree.refresh(force=True)
    except Exception:
        pass


# -- commands ---------------------------------------------------------------------------------
class CopyCommand:
    def GetResources(self):
        return {
            "MenuText": "Copy",
            "ToolTip": "Copy the selected component or body (Ctrl+C); paste it with Ctrl+V",
            "Pixmap": ui_icon_path("new_component"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            if _in_sketch():
                Gui.runCommand("Sketcher_CopyClipboard")
                return
            copy()
        except Exception as exc:
            warn("Copy failed: %s" % exc)


class PasteCommand:
    new = False
    text = "Paste"
    tip = (
        "Paste the copied component as a linked instance (editing one changes both), or a "
        "copy of the copied body (Ctrl+V)"
    )

    def GetResources(self):
        return {
            "MenuText": self.text,
            "ToolTip": self.tip,
            "Pixmap": ui_icon_path("new_component"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            if _in_sketch() and not self.new:
                from . import sketch_mode

                sketch_mode.paste()
                return
            paste(new=self.new)
        except Exception as exc:
            warn("%s failed: %s" % (self.text, exc))


class PasteNewCommand(PasteCommand):
    new = True
    text = "Paste New"
    tip = "Paste the copied component as an independent copy with its own features"


COMMANDS = {
    "SciForge_Copy": CopyCommand,
    "SciForge_Paste": PasteCommand,
    "SciForge_PasteNew": PasteNewCommand,
}

try:
    instances.install_watch()
except Exception as _exc:  # never let an import fail the commands
    warn("instances watch unavailable: %s" % _exc)
