# SPDX-License-Identifier: LGPL-2.1-or-later
"""Split Body (Modify > Split Body) with Fusion's dialog: Body to Split, Splitting Tool(s),
Extend Splitting Tool.

The Body to Split box takes the first click on a body; then the Splitting Tool box waits:
click one of the three big origin planes, a construction plane, a face of any body (flat or
round; Extend Splitting Tool takes its whole plane or cylinder), or a body in the browser
(split along its faces). A body or face selected before the command is taken at once. The
pieces are previewed live (each new body shows); OK / Enter keeps them (one undo step),
Cancel / Esc throws them away, the reason is said in the dialog when the tool does not cut
the body. Double-click the Split Body in the timeline to change it. Document side: split.py.
"""
import time

import FreeCAD as App

from . import bodies, split, ui_icon_path, warn
from .bodies_panel import BodyPanel, edit as _edit, start as _start

OVERLAY_CLICK_S = 0.8


class SplitPanel(BodyPanel):
    title = "Split Body"
    icon = "split_body"
    needs_pick = (split.NeedsPick,)

    def __init__(self, doc, feature=None):
        self.options = split.with_defaults({})
        if feature is not None:
            try:
                self.options.update(split.read(feature))
            except Exception as exc:
                warn("could not read %s: %s" % (feature.Label, exc))
        self.plane_picker = None
        self._planes_wanted = True
        self._overlay_time = 0.0
        super().__init__(
            doc, "Split Body" if feature is None else "Edit Split Body", feature is not None
        )
        self.target = feature
        self._show_picks()
        if feature is not None:
            self._go("tool")
        else:
            self._go("body")
            self.start_from_selection()
            self.dirty = True
            self._timer.stop()
            self._recompute()

    # -- form ----------------------------------------------------------------------------------------
    def build_form(self):
        self.selection_box("body", "Body to Split")
        self.selection_box("tool", "Splitting Tool")
        self.extend, _ = self.check_box(
            "Extend Splitting Tool",
            self.options["extend"],
            self._typed,
            "Take a face's whole plane (or cylinder), so it cuts right through the body",
        )

    def _typed(self):
        self.options["extend"] = self.extend.isChecked()
        self.changed()

    def _show_picks(self):
        body = self.options["body"]
        self.fields["body"].set_text(body.Label if body is not None else "")
        self.fields["tool"].set_text(_tool_text(self.options["tool"]))

    def cleared(self, name):
        self.options[name] = None
        self._show_picks()

    def activate(self, name):
        """A box clicked (or cleared) by the user: it takes the next click, the origin
        squares show for the tool box."""
        self._planes_wanted = True
        super().activate(name)

    def _go(self, name):
        """The dialog moves on to a box by itself: the squares show only while no tool is
        picked (they would cover the part)."""
        self._planes_wanted = self.options["tool"] is None
        BodyPanel.activate(self, name)

    def activated(self, name):
        self._update_planes()

    def _update_planes(self):
        """The three big origin squares while the Splitting Tool box waits for a tool
        (FreeCAD's own origin planes are small and hidden)."""
        wants = self.active == "tool" and self._planes_wanted and not self._closed
        body = self.options["body"] or bodies.find_body(self.doc)
        if wants and self.plane_picker is None and body is not None:
            try:
                from .pattern_ui import front_planes

                self.plane_picker = front_planes()(self.view, body, self._plane_clicked)
            except Exception as exc:
                warn("Split Body: origin planes unavailable: %s" % exc)
        elif not wants and self.plane_picker is not None:
            self.plane_picker.remove()
            self.plane_picker = None

    def _plane_clicked(self, plane):
        """An origin square was pressed (inside FreeCAD's mouse handling: work comes later)."""
        self._overlay_time = time.time()
        from .compat import QtCore

        QtCore.QTimer.singleShot(0, lambda: self._take_tool((plane, "")))

    # -- clicks ----------------------------------------------------------------------------------
    def picked(self, obj, short, point):
        if time.time() - self._overlay_time < OVERLAY_CLICK_S:
            return  # the origin square drawn over the part took this click
        if self.active == "body":
            body = bodies.body_of(obj)
            if body is None or self._made_by_preview(body):
                return
            self.options["body"] = body
            if self.options["tool"] is not None and self._tool_body() is body:
                self.options["tool"] = None
            self._show_picks()
            self._go("tool")
            self.changed()
            return
        if obj.TypeId in split.PLANE_TYPES:
            self._take_tool((obj, ""))
            return
        if obj.TypeId == "Sketcher::SketchObject" and short.startswith("Edge"):
            self._take_tool((obj, short))  # a sketch line or arc cuts straight through
            return
        if short.startswith("Face"):
            ref = self._face_ref(obj, short)
            if ref is not None:
                self._take_tool(ref)
            return
        body = bodies.body_of(obj)
        if body is not None and not short:
            if body is self.options["body"]:
                self.message.setText(
                    "A body cannot split itself. Pick a plane, a face or another body."
                )
                return
            self._take_tool((body, ""))
            return
        self.message.setText("Split with a plane, a face, a body or a sketch curve.")

    def _face_ref(self, obj, short):
        """A face clicked on the preview (the split's own result) is the same face of the
        step before the split."""
        feature = self.target
        if feature is None or not bodies.alive(feature):
            return (obj, short)
        body = bodies.body_of(obj)
        if body is not bodies.body_of(feature) and not self._made_by_preview(body):
            return (obj, short)
        base = feature.BaseFeature
        from . import profile_pick

        global_face = profile_pick.global_face(obj, short)
        if global_face is None or base is None:
            return None
        name = profile_pick.face_name_in(base, global_face)
        if not name:
            # A face the split itself made (the cut): take its plane from the tool instead.
            self.message.setText(
                "That face was made by this split. Pick the splitting tool itself."
            )
            return None
        return (base, name)

    def _take_tool(self, ref):
        if self._closed:
            return
        try:
            self.options["tool"] = ref
            self._show_picks()
            self.message.setText("")
            self._planes_wanted = False  # picked: the squares go (click the box to pick again)
            self._update_planes()
            self.changed()
        except Exception as exc:
            warn("Split Body pick: %s" % exc)

    def _tool_body(self):
        tool = self.options["tool"]
        return bodies.body_of(tool[0]) if tool else None

    def _made_by_preview(self, body):
        feature = self.target
        if feature is None or not bodies.alive(feature) or body is None:
            return False
        return body in split.piece_bodies(feature)

    # -- preview ------------------------------------------------------------------------------------
    def apply(self):
        if self.options["body"] is None or self.options["tool"] is None:
            if self.target is not None and not self.editing and bodies.alive(self.target):
                split.remove(self.target)
                self.target = None
            split.check(self.options)
        try:
            self.target = split.build(self.options, self.target)
        except split.SplitError:
            if self.target is not None and not self.editing and bodies.alive(self.target):
                split.remove(self.target)  # no half-made pieces stay behind
                self.target = None
            raise

    def after_recompute(self):
        feature = self.target
        if feature is not None and bodies.alive(feature):
            bodies.show_tip(bodies.body_of(feature))
            for body in split.piece_bodies(feature):
                bodies.show_tip(body)
        count = (
            len(split.piece_bodies(feature)) + 1
            if feature is not None and bodies.alive(feature)
            else 0
        )
        self.note.setText("%d bodies" % count if count else "")

    def preview_steps(self):
        if self.target is None or not bodies.alive(self.target):
            return []
        return [self.target] + split.pieces_of(self.target)

    def can_finish(self):
        if self.target is None or not bodies.alive(self.target):
            try:
                split.check(self.options)
            except split.SplitError as exc:
                return str(exc)
            return self.error or "Pick the body to split and the splitting tool."
        return ""

    def remove_handles(self):
        if self.plane_picker is not None:
            try:
                self.plane_picker.remove()
            except Exception:
                pass
            self.plane_picker = None


def _tool_text(tool):
    if not tool:
        return ""
    obj, sub = tool
    if obj.TypeId in split.PLANE_TYPES:
        return obj.Label
    if bodies.is_body(obj):
        return obj.Label
    body = bodies.body_of(obj)
    where = body.Label if body is not None else obj.Label
    if obj.TypeId == "Sketcher::SketchObject":
        return "Curve of %s" % obj.Label
    if sub:
        return "%s of %s" % (sub.rstrip("0123456789"), where)
    return where


class SplitBodyCommand:
    def GetResources(self):
        return {
            "MenuText": "Split Body",
            "ToolTip": "Split a body in two (or more) with a plane, a face or another body; "
            "every piece becomes a body",
            "Pixmap": ui_icon_path("split_body"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            _start(SplitPanel)
        except Exception as exc:
            warn("Split Body could not start: %s" % exc)


def edit(feature):
    _edit(SplitPanel, feature)


COMMANDS = {"SciForge_SplitBody": SplitBodyCommand}
EDITORS = {"SciForge::SplitBody": edit}
