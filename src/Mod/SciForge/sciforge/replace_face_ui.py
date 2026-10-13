# SPDX-License-Identifier: LGPL-2.1-or-later
"""Replace Face (Modify > Replace Face) with Fusion's dialog: Source Faces, Tangent Chain,
Target Faces.

The Source Faces box takes clicks on faces of one body (a click on a picked face drops it;
the first face decides the body, also a solid without history: it becomes a body built on
it). Then the Target Faces box waits: click a face of any body, or one of the big origin
squares or a construction plane. The source faces move onto the target (the faces around
them extended or trimmed), previewed live; OK / Enter keeps it (one undo step), Cancel /
Esc throws it away; the reason is said in the dialog when the target cannot be used.
Double-click the Replace Face in the timeline to change it. Document side: replace_face.py.
"""

import FreeCAD as App

from . import bodies, modify_common as mc, replace_face, ui_icon_path, warn
from .bodies_panel import BodyPanel, edit as _edit, start as _start


class ReplaceFacePanel(BodyPanel):
    title = "Replace Face"
    icon = "replace_face"
    needs_pick = (replace_face.NeedsPick,)

    def __init__(self, doc, feature=None):
        self.options = replace_face.with_defaults({})
        if feature is not None:
            try:
                self.options.update(replace_face.read(feature))
            except Exception as exc:
                warn("could not read %s: %s" % (feature.Label, exc))
        self._adopted = []
        self.squares = None
        super().__init__(
            doc, "Replace Face" if feature is None else "Edit Replace Face", feature is not None
        )
        self.target = feature
        self.squares = mc.PlaneSquares(self, self._take_target)
        self._show_picks()
        if feature is not None:
            self.activate("target")
        else:
            self.activate("faces")
            self.start_from_selection()
            self.dirty = True
            self._timer.stop()
            self._recompute()

    # -- form ----------------------------------------------------------------------------------
    def build_form(self):
        self.selection_box("faces", "Source Faces")
        self.tangent, _ = self.check_box(
            "Tangent Chain",
            self.options["tangent_chain"],
            self._typed,
            "Also replace the faces that continue the picked ones smoothly",
        )
        self.selection_box("target", "Target Faces")

    def _typed(self):
        self.options["tangent_chain"] = self.tangent.isChecked()
        self.changed()

    def _show_picks(self):
        faces = self.options["faces"]
        self.fields["faces"].set_text(mc.faces_text(faces[1]) if faces else "")
        self.fields["target"].set_text(mc.ref_text(self.options["target"]))

    def cleared(self, name):
        self.options[name] = None
        self._show_picks()

    def activated(self, name):
        if self.squares is None:
            return
        if name == "target" and self.options["target"] is None:
            body = self._body() or bodies.find_body(self.doc)
            self.squares.show(body)
        else:
            self.squares.hide()

    def _body(self):
        faces = self.options["faces"]
        return bodies.body_of(faces[0]) if faces else None

    # -- clicks --------------------------------------------------------------------------------
    def picked(self, obj, short, point):
        if self.squares is not None and self.squares.took_click():
            return
        if self.active == "faces":
            self._pick_face(obj, short)
            return
        from . import split

        if obj.TypeId in split.PLANE_TYPES and not short:
            self._take_target((obj, ""))
            return
        if short.startswith("Face"):
            ref = mc.face_on_base(obj, short, self.target)
            if ref is None:
                self.message.setText("That face was made by this Replace Face. Pick another.")
                return
            self._take_target(ref)
            return
        self.message.setText("Pick a face of a body, or a plane, as the target.")

    def _pick_face(self, obj, short):
        if not short.startswith("Face"):
            self.message.setText("Click faces of a body.")
            return
        body = mc.body_of_pick(self, obj)
        if body is None:
            return
        if bodies.body_of(obj) is None:
            obj = body.Tip  # a plain solid made a body: its base feature has the same faces
        ref = mc.face_on_base(obj, short, self.target)
        if ref is None:
            self.message.setText("That face was made by this Replace Face. Pick a face it moves.")
            return
        source, name = ref
        faces = self.options["faces"]
        if faces and bodies.body_of(faces[0]) is not body:
            self.message.setText("The source faces must all be on one body.")
            return
        names = list(faces[1]) if faces else []
        if faces and faces[0] is not source:
            names = []  # picked on another step of the body: start again there
        if name in names:
            names.remove(name)
        else:
            names.append(name)
        self.options["faces"] = (source, names) if names else None
        self.message.setText("")
        self._show_picks()
        self.changed()

    def _take_target(self, ref):
        if self._closed:
            return
        self.options["target"] = ref
        self._show_picks()
        self.message.setText("")
        if self.squares is not None:
            self.squares.hide()
        self.changed()

    # -- preview -------------------------------------------------------------------------------
    def apply(self):
        if self.options["faces"] is None or self.options["target"] is None:
            if self.target is not None and not self.editing and bodies.alive(self.target):
                bodies.remove_step(self.target)
                self.target = None
            replace_face.check(self.options)
        self.target = replace_face.build(self.options, self.target)

    def after_recompute(self):
        if self.target is not None and bodies.alive(self.target):
            bodies.show_tip(bodies.body_of(self.target))
        note = getattr(getattr(self.target, "Proxy", None), "note", "") if self.target else ""
        self.note.setText(note)

    def preview_steps(self):
        return [self.target] if self.target is not None and bodies.alive(self.target) else []

    def can_finish(self):
        if not self.preview_steps():
            try:
                replace_face.check(self.options)
            except replace_face.ReplaceFaceError as exc:
                return str(exc)
            return self.error or "Pick the faces to replace and the target."
        return ""

    def remove_handles(self):
        if self.squares is not None:
            self.squares.hide()

    def before_close(self, ok):
        self._ok = ok

    def restore_view(self):
        mc.restore_adopted(self, getattr(self, "_ok", False))


class ReplaceFaceCommand:
    def GetResources(self):
        return {
            "MenuText": "Replace Face",
            "ToolTip": "Replace faces of a body by another face or a plane: the faces around "
            "them are extended or trimmed to it",
            "Pixmap": ui_icon_path("replace_face"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            _start(ReplaceFacePanel)
        except Exception as exc:
            warn("Replace Face could not start: %s" % exc)


def edit(feature):
    _edit(ReplaceFacePanel, feature)


COMMANDS = {"SciForge_ReplaceFace": ReplaceFaceCommand}
EDITORS = {"SciForge::ReplaceFace": edit}
