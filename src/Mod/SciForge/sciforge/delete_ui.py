# SPDX-License-Identifier: LGPL-2.1-or-later
"""Delete (Del, Modify > Delete, the marking menu) on what is selected, like Fusion:

  a body (picked in the browser)        deleted with everything in it
  a sketch, feature or plane            deleted; what came after it keeps working where it can
                                        (fillets and sketches move onto the same edges and
                                        faces of the step before it, the body's history is
                                        re-linked, the end of the timeline moves back); what
                                        cannot is shown red or yellow in the timeline
  faces of a body (clicked in the view) a "Delete Face" step: the faces go and the faces
                                        around them grow to close the gap; if they cannot,
                                        the reason is shown next to the pointer and nothing
                                        changes
  curves of a sketch (clicked)          deleted from the sketch

Nothing selected: says so next to the pointer. In an open sketch Del deletes sketch curves
(sketch_mode handles the key there); the browser and the timeline take Del themselves
when they have the keyboard. One undo step. The document side is delete.py.

Double-clicking a Delete Face step in the timeline opens a small dialog to change its faces.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import bodies, bodies_gui, commands, delete, log, ui_icon_path, warn
from .bodies_panel import BodyPanel, edit as _edit


class DeleteCommand:
    def GetResources(self):
        return {
            "MenuText": "Delete",
            "ToolTip": "Delete the selected bodies, steps, sketches or faces; later steps keep "
            "working where they can (Del)",
            "Pixmap": ui_icon_path("delete"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            run()
        except Exception as exc:
            warn("Delete failed: %s" % exc)


def run():
    if _in_sketch():
        Gui.runCommand("Std_Delete")  # sketch curves, with FreeCAD's sketch delete
        return
    doc = App.ActiveDocument
    if doc is None:
        return
    entries = [(o, short) for o, short, _p in bodies_gui.selection_entries() if o.Document is doc]
    if Gui.Control.activeDialog():
        commands.tell("Finish the open command first (OK or Cancel), then delete.")
        return
    if not entries:
        commands.tell(
            "Select what to delete: a body or sketch in the browser, a step in the "
            "timeline, or faces of a body."
        )
        return
    found = delete.plan(entries)
    if delete.is_empty(found):
        commands.tell(found["refused"] or "That cannot be deleted.")
        return
    bodies_gui.clear_selection()
    try:
        made = delete.run(doc, found, _title(found), heal=_heals())
    except delete.DeleteError as exc:
        commands.tell(str(exc))
        return
    bodies_gui.sync(doc)
    for body in {bodies.body_of(step) for step in made if bodies.alive(step)}:
        bodies.show_tip(body)
    log("deleted: %s" % _title(found))
    if found["refused"]:
        commands.tell(found["refused"])


def _heals():
    """Fusion decides by the tab Delete runs from: SOLID heals a solid's faces, SURFACE
    removes them (surfmod_core.delete_heals; surface-4)."""
    try:
        from . import shell

        ribbon = shell.ribbon()
        tab = ribbon.current_tab() if ribbon is not None else "solid"
    except Exception:
        tab = "solid"
    return tab != "surface"


def _title(found):
    parts = [b.Label for b in found["bodies"]]
    parts += [s.Label for s in found["steps"]]
    if found["faces"]:
        count = sum(len(v) for v in found["faces"].values())
        parts.append("%d face%s" % (count, "" if count == 1 else "s"))
    if found["curves"]:
        count = sum(len(v) for v in found["curves"].values())
        parts.append("%d sketch curve%s" % (count, "" if count == 1 else "s"))
    return "Delete " + ", ".join(parts[:3]) + ("..." if len(parts) > 3 else "")


def _in_sketch():
    try:
        edit = Gui.ActiveDocument.getInEdit() if Gui.ActiveDocument is not None else None
        obj = edit.Object if edit is not None else None
        return obj is not None and obj.TypeId == "Sketcher::SketchObject"
    except Exception:
        return False


# -- editing a Delete Face step ---------------------------------------------------------------------------
class DeleteFacePanel(BodyPanel):
    """Change the faces a Delete Face step removes: click a face to add it, a picked one to
    drop it (the faces are those of the body before this step)."""

    title = "Delete Face"
    icon = "delete"
    needs_pick = ()

    def __init__(self, doc, feature=None):
        self.feature_step = feature
        link = feature.Faces
        self.base = link[0] if link else feature.BaseFeature
        self.names = list(link[1]) if link else []
        super().__init__(doc, "Edit Delete Face", True)
        self.target = feature
        self.activate("faces")
        self._show()

    def build_form(self):
        self.selection_box("faces", "Faces")

    def _show(self):
        count = len(self.names)
        self.fields["faces"].set_text(
            "%d face%s" % (count, "" if count == 1 else "s") if count else ""
        )

    def cleared(self, name):
        self.names = []
        self._show()

    def picked(self, obj, short, point):
        if not short.startswith("Face") or self.base is None:
            return
        from . import profile_pick

        face = profile_pick.global_face(obj, short)
        name = profile_pick.face_name_in(self.base, face) if face is not None else None
        if not name:
            self.message.setText("Pick a face the body had before this step.")
            return
        if name in self.names:
            self.names.remove(name)
        else:
            self.names.append(name)
        self._show()
        self.changed()

    def apply(self):
        if not self.names:
            raise delete.DeleteError("Pick the faces to delete.")
        faces = [self.base.Shape.getElement(n) for n in self.names]
        delete.heal(self.base.Shape, faces)  # the reason, before anything changes
        self.feature_step.Faces = (self.base, list(self.names))

    def preview_steps(self):
        return [self.feature_step] if bodies.alive(self.feature_step) else []


def edit(feature):
    _edit(DeleteFacePanel, feature)


COMMANDS = {"SciForge_Delete": DeleteCommand}
EDITORS = {"SciForge::DeleteFace": edit}
