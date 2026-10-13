# SPDX-License-Identifier: LGPL-2.1-or-later
"""Silhouette Split (Modify > Silhouette Split) with Fusion's dialog: View Direction, Target
Body, Operation (Split Faces Only / Split Solid Body / Split Shelled Body).

The View Direction box takes the first click: an axis (origin or construction), a straight
edge, a flat face or one of the big origin squares (its normal). Then the Target Body box:
click the body (a solid without history becomes a body built on it). The split is
previewed live (new bodies show); OK / Enter keeps it (one undo step), Cancel / Esc throws it
away; the reason is said in the dialog when the outline cannot be used (Split Solid Body
needs an outline in one plane, Split Shelled Body a shelled body). Double-click the
Silhouette Split in the timeline to change it. Document side: silhouette.py.
"""

import FreeCAD as App

from . import bodies, modify_common as mc, silhouette, split, ui_icon_path, warn
from .bodies_panel import BodyPanel, edit as _edit, start as _start

OPERATIONS = [(silhouette.OPERATION_LABELS[k], k) for k in silhouette.OPERATIONS]


class SilhouettePanel(BodyPanel):
    title = "Silhouette Split"
    icon = "silhouette_split"
    needs_pick = (silhouette.NeedsPick,)

    def __init__(self, doc, feature=None):
        self.options = silhouette.with_defaults({})
        if feature is not None:
            try:
                self.options.update(silhouette.read(feature))
            except Exception as exc:
                warn("could not read %s: %s" % (feature.Label, exc))
        self._adopted = []
        self.squares = None
        super().__init__(
            doc,
            "Silhouette Split" if feature is None else "Edit Silhouette Split",
            feature is not None,
        )
        self.target = feature
        self.squares = mc.PlaneSquares(self, self._take_direction)
        self._show_picks()
        if feature is not None:
            self.activate("direction")
        else:
            self.activate("direction")
            self.start_from_selection()
            self.dirty = True
            self._timer.stop()
            self._recompute()

    def build_form(self):
        self.selection_box("direction", "View Direction")
        self.selection_box("body", "Target Body")
        self.operation, _ = self.combo(
            "Operation", OPERATIONS, self.options["operation"], self._typed
        )

    def _typed(self):
        self.options["operation"] = self.operation.currentData()
        self.changed()

    def _show_picks(self):
        self.fields["direction"].set_text(mc.ref_text(self.options["direction"]))
        body = self.options["body"]
        self.fields["body"].set_text(body.Label if body is not None else "")

    def cleared(self, name):
        self.options[name] = None
        self._show_picks()

    def activated(self, name):
        if self.squares is None:
            return
        if name == "direction" and self.options["direction"] is None:
            self.squares.show(self.options["body"] or bodies.find_body(self.doc))
        else:
            self.squares.hide()

    def picked(self, obj, short, point):
        if self.squares is not None and self.squares.took_click():
            return
        if self.active == "direction":
            ref = (obj, short)
            if silhouette.view_direction(ref) is None:
                self.message.setText(
                    "Pick an axis, a straight edge, a flat face or a plane as the view direction."
                )
                return
            self._take_direction(ref)
            return
        body = mc.body_of_pick(self, obj)
        if body is None or self._made_by_preview(body):
            return
        self.options["body"] = body
        self.message.setText("")
        self._show_picks()
        self.changed()

    def _take_direction(self, ref):
        if self._closed:
            return
        self.options["direction"] = ref
        self.message.setText("")
        self._show_picks()
        if self.squares is not None:
            self.squares.hide()
        if self.options["body"] is None:
            self.activate("body")
        self.changed()

    def _made_by_preview(self, body):
        feature = self.target
        if feature is None or not bodies.alive(feature) or body is None:
            return False
        return body in split.piece_bodies(feature)

    def apply(self):
        try:
            silhouette.check(self.options)
        except silhouette.SilhouetteError:
            if self.target is not None and not self.editing and bodies.alive(self.target):
                silhouette.remove(self.target)
                self.target = None
            raise
        try:
            self.target = silhouette.build(self.options, self.target)
        except silhouette.SilhouetteError:
            if self.target is not None and not self.editing and bodies.alive(self.target):
                silhouette.remove(self.target)
                self.target = None
            raise

    def after_recompute(self):
        feature = self.target
        if feature is None or not bodies.alive(feature):
            self.note.setText("")
            return
        bodies.show_tip(bodies.body_of(feature))
        made = split.piece_bodies(feature)
        for body in made:
            bodies.show_tip(body)
        if feature.Operation == "faces":
            base = feature.BaseFeature
            extra = len(feature.Shape.Faces) - len(base.Shape.Faces) if base is not None else 0
            self.note.setText(
                "%d more face%s" % (extra, "" if extra == 1 else "s")
                if extra > 0
                else "The outline runs along edges the body has already."
            )
        else:
            self.note.setText("%d bodies" % (len(made) + 1))

    def preview_steps(self):
        if self.target is None or not bodies.alive(self.target):
            return []
        return [self.target] + split.pieces_of(self.target)

    def can_finish(self):
        if not self.preview_steps():
            try:
                silhouette.check(self.options)
            except silhouette.SilhouetteError as exc:
                return str(exc)
            return self.error or "Pick the view direction and the body."
        return ""

    def remove_handles(self):
        if self.squares is not None:
            self.squares.hide()

    def before_close(self, ok):
        self._ok = ok

    def restore_view(self):
        mc.restore_adopted(self, getattr(self, "_ok", False))


class SilhouetteSplitCommand:
    def GetResources(self):
        return {
            "MenuText": "Silhouette Split",
            "ToolTip": "Split a body's faces (or the body) along its outline seen from a "
            "direction",
            "Pixmap": ui_icon_path("silhouette_split"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            _start(SilhouettePanel)
        except Exception as exc:
            warn("Silhouette Split could not start: %s" % exc)


def edit(feature):
    _edit(SilhouettePanel, feature)


COMMANDS = {"SciForge_SilhouetteSplit": SilhouetteSplitCommand}
EDITORS = {"SciForge::SilhouetteSplit": edit}
