# SPDX-License-Identifier: LGPL-2.1-or-later
"""Remove (Modify > Remove, and Remove in a body's or component's right-click menu), like
Fusion: a Remove step in the timeline from which on the body is gone. Rolling the marker
before it, suppressing or deleting it brings the body back; Delete instead deletes the
features that made the body. (remove.py is the document side.)

Bodies or components selected first (browser, 3D view) are removed at once, one undo step.
With nothing selected a small dialog waits for clicks: Objects (bodies in the 3D view or the
browser, components in the browser; a click on a picked one drops it), OK removes them.
Double-clicking a Remove step in the timeline opens that dialog on it.

In a design without history there is no timeline to hold a Remove: the bodies are deleted
(what Fusion's Delete does there).
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import bodies, bodies_gui, commands, components, direct, log, remove, ui_icon_path, warn
from .bodies_panel import BodyPanel, edit as _edit, start as _start


def _picked_objects(doc, entries):
    found = []
    for obj, _short, _point in entries:
        if obj is None or obj.Document is not doc:
            continue
        target = obj if components.is_component(obj) else bodies.body_of(obj)
        if target is not None and target not in found:
            found.append(target)
    return found


def remove_now(objects):
    """Remove these bodies / components (one undo step). Returns the steps made."""
    objects = [o for o in objects if o is not None]
    if not objects:
        commands.tell("Select the bodies or components to remove.")
        return []
    doc = objects[0].Document
    if Gui.Control.activeDialog() and not commands.finish_open_dialog():
        return []
    if direct.is_direct(doc):
        return _delete_instead(doc, objects)
    found, parts = remove.targets_of(objects)
    if not doc.UndoMode:
        doc.UndoMode = 1
    doc.openTransaction("Remove %s" % ", ".join(o.Label for o in objects[:3]))
    try:
        steps = remove.make(found, parts)
        from . import timeline_ops

        timeline_ops.recompute(doc)
    except remove.RemoveError as exc:
        doc.abortTransaction()
        commands.tell(str(exc))
        return []
    except Exception:
        doc.abortTransaction()
        raise
    doc.commitTransaction()
    _after(doc, steps)
    log("removed: %s" % ", ".join(o.Label for o in objects))
    return steps


def _after(doc, steps):
    for step in steps:
        body = bodies.body_of(step)
        if body is not None:
            bodies.set_shown(body, False)
    remove.leave_removed_body(doc)
    try:
        bodies_gui.sync(doc)
    except Exception as exc:
        warn("Remove: %s" % exc)
    bodies_gui.clear_selection()


def _delete_instead(doc, objects):
    from . import delete

    found, parts = remove.targets_of(objects)
    entries = [(b, "") for b in found]
    plan = delete.plan(entries)
    try:
        delete.run(doc, plan, "Delete %s" % ", ".join(o.Label for o in objects[:3]))
    except delete.DeleteError as exc:
        commands.tell(str(exc))
        return []
    for part in parts:
        if bodies.alive(part) and not components.bodies_in(doc, part, recursive=True):
            try:
                components.remove(doc, part)
            except Exception:
                pass
    commands.tell("This design does not capture history: the bodies are deleted.")
    return []


class RemoveCommand:
    def GetResources(self):
        return {
            "MenuText": "Remove",
            "ToolTip": "Take bodies or components out of the design from this point of the "
            "timeline on (Delete takes away the steps that made them)",
            "Pixmap": ui_icon_path("remove"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            doc = App.ActiveDocument
            entries = [e for e in bodies_gui.selection_entries() if e[0].Document is doc]
            picked = _picked_objects(doc, entries)
            if picked:
                remove_now(picked)
                return
            _start(RemovePanel)
        except Exception as exc:
            warn("Remove failed: %s" % exc)


class RemovePanel(BodyPanel):
    """Objects to remove; a Remove step (or its steps) being edited."""

    title = "Remove"
    icon = "remove"
    needs_pick = (remove.RemoveError,)

    def __init__(self, doc, feature=None):
        self.feature_ = feature
        self.picked_objects = []
        self.steps = []
        self._hidden = []  # bodies the preview hid (shown again on Cancel)
        self._shown_back = []  # bodies the edited step removed, shown by the preview
        if feature is not None:
            self.steps = remove.steps_of(feature.RemoveId, doc) or [feature]
            self.picked_objects = [bodies.body_of(s) for s in self.steps]
        super().__init__(doc, "Remove" if feature is None else "Edit Remove", feature is not None)
        self.target = feature
        self.activate("objects")
        self._show()
        if feature is None:
            self.start_from_selection()
        self.dirty = True
        self._timer.stop()
        self._recompute()

    def build_form(self):
        self.selection_box("objects", "Objects")

    def _show(self):
        objs = [o for o in self.picked_objects if bodies.alive(o)]
        self.fields["objects"].set_text(bodies_gui.body_text(objs) if objs else "")

    def cleared(self, name):
        self.picked_objects = []
        self._show()

    def picked(self, obj, short, point):
        target = obj if components.is_component(obj) else bodies.body_of(obj)
        if target is None:
            return
        if target in self.picked_objects:
            self.picked_objects.remove(target)
        else:
            self.picked_objects.append(target)
        self._show()
        self.changed()

    def apply(self):
        before = [bodies.body_of(s) for s in self.steps if bodies.alive(s)]
        for step in self.steps:
            if bodies.alive(step):
                bodies.remove_step(step)
        self.steps = []
        found, parts = remove.targets_of([o for o in self.picked_objects if bodies.alive(o)])
        for body in list(self._hidden):  # dropped from the selection: shown again
            if body not in found and bodies.alive(body):
                bodies.set_shown(body, True)
                bodies.show_tip(body)
                self._hidden.remove(body)
        for body in before:  # removed by the step being edited, not any more: shown
            if body is not None and body not in found and bodies.alive(body):
                if not bodies.is_shown(body):
                    bodies.set_shown(body, True)
                    bodies.show_tip(body)
                    if body not in self._shown_back:
                        self._shown_back.append(body)
        if not found:
            raise remove.RemoveError("Click the bodies (or components in the browser) to remove.")
        remove_id = getattr(self.feature_, "RemoveId", None) if self.feature_ else None
        self.steps = remove.make(found, parts, remove_id)
        for body in found:
            if bodies.is_shown(body):
                bodies.set_shown(body, False)
                if body not in self._hidden:
                    self._hidden.append(body)

    def preview_steps(self):
        return [s for s in self.steps if bodies.alive(s)]

    def can_finish(self):
        return "" if self.preview_steps() else "Click the bodies to remove."

    def before_close(self, ok):
        self._ok = ok

    def restore_view(self):
        if getattr(self, "_ok", False):
            return
        for body in self._hidden:
            if bodies.alive(body):
                bodies.set_shown(body, True)
                bodies.show_tip(body)
        for body in self._shown_back:  # Cancel: the edited step removes them again
            if bodies.alive(body) and remove.removed(body) is not None:
                bodies.set_shown(body, False)

    def after_close(self, ok):
        super().after_close(ok)
        if ok:
            remove.leave_removed_body(self.doc)


def edit(feature):
    _edit(RemovePanel, feature)


COMMANDS = {"SciForge_Remove": RemoveCommand}
EDITORS = {"SciForge::Remove": edit}
