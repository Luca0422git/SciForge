# SPDX-License-Identifier: LGPL-2.1-or-later
"""Split Face (Modify > Split Face) with Fusion's dialog: Faces to Split, Splitting Tool,
Extend Splitting Tool, Split Type (Split with Surface / Along Vector / Closest Point) and,
for Along Vector, the direction.

The Faces to Split box takes clicks on faces of one body (a click on a picked face drops
it; a solid without history becomes a body built on it). Then the Splitting Tool box
waits: a sketch (in the browser, or one of its curves in the view), one of the big origin
squares or a construction plane, a face of any body, or another body in the browser. The
new edges are previewed live; OK / Enter keeps them (one undo step), Cancel / Esc throws
them away; the reason is said in the dialog when the tool does not cross the faces.
Double-click the Split Face in the timeline to change it. Document side: split_face.py.
"""

import FreeCAD as App

from . import bodies, modify_common as mc, split_face, ui_icon_path, warn
from .bodies_panel import BodyPanel, edit as _edit, start as _start

TYPES = [(split_face.SPLIT_TYPE_LABELS[k], k) for k in split_face.SPLIT_TYPES]


class SplitFacePanel(BodyPanel):
    title = "Split Face"
    icon = "split_face"
    needs_pick = (split_face.NeedsPick,)

    def __init__(self, doc, feature=None):
        self.options = split_face.with_defaults({})
        if feature is not None:
            try:
                self.options.update(split_face.read(feature))
            except Exception as exc:
                warn("could not read %s: %s" % (feature.Label, exc))
        self._adopted = []
        self.squares = None
        super().__init__(
            doc, "Split Face" if feature is None else "Edit Split Face", feature is not None
        )
        self.target = feature
        self.squares = mc.PlaneSquares(self, self._take_plane)
        self._show_picks()
        self._show_rows()
        if feature is not None:
            self.activate("tool")
        else:
            self.activate("faces")
            self.start_from_selection()
            self.dirty = True
            self._timer.stop()
            self._recompute()

    # -- form ----------------------------------------------------------------------------------
    def build_form(self):
        self.selection_box("faces", "Faces to Split")
        self.selection_box("tool", "Splitting Tool")
        self.split_type, _ = self.combo(
            "Split Type", TYPES, self.options["split_type"], self._typed
        )
        self.extend, self.extend_caption = self.check_box(
            "Extend Splitting Tool",
            self.options["extend"],
            self._typed,
            "Extend the tool so it crosses the whole face (a flat face as its plane, a round "
            "face as its cylinder)",
        )
        self.selection_box("direction", "Direction")

    def _typed(self):
        self.options["split_type"] = self.split_type.currentData()
        self.options["extend"] = self.extend.isChecked()
        self._show_rows()
        self.changed()

    def _show_rows(self):
        kind = self.options["split_type"]
        self.show_row(self.extend, self.extend_caption, kind == "surface")
        field = self.fields.get("direction")
        if field is not None:
            self.show_row(field.widget, self.captions["direction"], kind == "vector")

    def _show_picks(self):
        faces = self.options["faces"]
        self.fields["faces"].set_text(mc.faces_text(faces[1]) if faces else "")
        self.fields["tool"].set_text(mc.ref_text(self.options["tool"]))
        self.fields["direction"].set_text(mc.ref_text(self.options["direction"]))

    def cleared(self, name):
        self.options[name] = None
        self._show_picks()

    def activated(self, name):
        if self.squares is None:
            return
        wants = (name == "tool" and self.options["tool"] is None) or (
            name == "direction" and self.options["direction"] is None
        )
        if wants:
            faces = self.options["faces"]
            body = bodies.body_of(faces[0]) if faces else bodies.find_body(self.doc)
            self.squares.show(body)
        else:
            self.squares.hide()

    # -- clicks --------------------------------------------------------------------------------
    def picked(self, obj, short, point):
        if self.squares is not None and self.squares.took_click():
            return
        if self.active == "faces":
            self._pick_face(obj, short)
        elif self.active == "tool":
            self._pick_tool(obj, short)
        elif self.active == "direction":
            ref = (obj, short)
            if split_face.direction_of(ref) is None:
                self.message.setText("Pick a straight edge, a flat face, a plane or an axis.")
                return
            self.options["direction"] = ref
            self._after_pick()

    def _pick_face(self, obj, short):
        if not short.startswith("Face"):
            self.message.setText("Click faces of a body.")
            return
        body = mc.body_of_pick(self, obj)
        if body is None:
            return
        if bodies.body_of(obj) is None:
            obj = body.Tip
        ref = mc.face_on_base(obj, short, self.target)
        if ref is None:
            self.message.setText(
                "That face was made by this split. Pick one of the faces it splits."
            )
            return
        source, name = ref
        faces = self.options["faces"]
        if faces and bodies.body_of(faces[0]) is not body:
            self.message.setText("The faces to split must all be on one body.")
            return
        names = list(faces[1]) if faces and faces[0] is source else []
        if name in names:
            names.remove(name)
        else:
            names.append(name)
        self.options["faces"] = (source, names) if names else None
        self.message.setText("")
        self._show_picks()
        self.changed()

    def _pick_tool(self, obj, short):
        if obj.TypeId == "Sketcher::SketchObject":
            self.options["tool"] = (obj, short if short.startswith("Edge") else "")
        elif obj.TypeId in split_face.PLANE_TYPES and not short:
            self.options["tool"] = (obj, "")
        elif short.startswith("Face"):
            ref = mc.face_on_base(obj, short, self.target)
            if ref is None:
                self.message.setText("Pick the splitting tool itself, not a face this split made.")
                return
            self.options["tool"] = ref
        elif short.startswith("Edge") and self.options["split_type"] != "surface":
            self.options["tool"] = (obj, short)
        elif bodies.is_body(obj) and not short:
            faces = self.options["faces"]
            if faces and bodies.body_of(faces[0]) is obj:
                self.message.setText("A body cannot split its own faces with itself.")
                return
            self.options["tool"] = (obj, "")
        else:
            self.message.setText("Split with a sketch, a plane, a face or another body.")
            return
        self._after_pick()

    def _take_plane(self, ref):
        if self._closed:
            return
        if self.active == "direction":
            self.options["direction"] = ref
        else:
            self.options["tool"] = ref
        self._after_pick()

    def _after_pick(self):
        self.message.setText("")
        self._show_picks()
        if self.squares is not None:
            self.squares.hide()
        if self.options["split_type"] == "vector" and self.options["direction"] is None:
            self.activate("direction")
        self.changed()

    # -- preview -------------------------------------------------------------------------------
    def apply(self):
        try:
            split_face.check(self.options)
        except split_face.SplitFaceError:
            if self.target is not None and not self.editing and bodies.alive(self.target):
                bodies.remove_step(self.target)
                self.target = None
            raise
        self.target = split_face.build(self.options, self.target)

    def after_recompute(self):
        if self.target is not None and bodies.alive(self.target):
            bodies.show_tip(bodies.body_of(self.target))
            base = self.target.BaseFeature
            if base is not None and not self.target.Shape.isNull():
                extra = len(self.target.Shape.Faces) - len(base.Shape.Faces)
                self.note.setText(
                    "%d more face%s" % (extra, "" if extra == 1 else "s") if extra > 0 else ""
                )

    def preview_steps(self):
        return [self.target] if self.target is not None and bodies.alive(self.target) else []

    def can_finish(self):
        if not self.preview_steps():
            try:
                split_face.check(self.options)
            except split_face.SplitFaceError as exc:
                return str(exc)
            return self.error or "Pick the faces to split and the splitting tool."
        return ""

    def remove_handles(self):
        if self.squares is not None:
            self.squares.hide()

    def before_close(self, ok):
        self._ok = ok

    def restore_view(self):
        mc.restore_adopted(self, getattr(self, "_ok", False))


class SplitFaceCommand:
    def GetResources(self):
        return {
            "MenuText": "Split Face",
            "ToolTip": "Divide faces of a body along a sketch, a plane, a face or a body (the "
            "body stays one body)",
            "Pixmap": ui_icon_path("split_face"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            _start(SplitFacePanel)
        except Exception as exc:
            warn("Split Face could not start: %s" % exc)


def edit(feature):
    _edit(SplitFacePanel, feature)


COMMANDS = {"SciForge_SplitFace": SplitFaceCommand}
EDITORS = {"SciForge::SplitFace": edit}
