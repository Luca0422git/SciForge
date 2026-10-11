# SPDX-License-Identifier: LGPL-2.1-or-later
"""Combine (Modify > Combine) with Fusion's dialog: Target Body, Tool Bodies, Operation
(Join / Cut / Intersect), New Body, Keep Tools.

Click a body (anywhere on it, or in the browser) to pick it: the Target Body box takes the
first click, then the Tool Bodies box takes every further one (a click on a picked tool
drops it). Bodies selected before the command are taken at once (the first is the target).
The result is previewed live; while the dialog is open the tool bodies stay visible, see-
through, so they can be clicked again. OK / Enter keeps it (one undo step), Cancel / Esc
throws it away. Double-click the Combine in the timeline to change it. The document side
is combine.py.
"""
import FreeCAD as App

from . import bodies, bodies_gui, combine, ui_icon_path, warn
from .bodies_panel import BodyPanel, edit as _edit, start as _start

OPERATIONS = [("Join", "join"), ("Cut", "cut"), ("Intersect", "intersect")]
SEE_THROUGH = 70  # transparency (%) of the tool bodies while the dialog is open


class CombinePanel(BodyPanel):
    title = "Combine"
    icon = "combine"
    needs_pick = (combine.NeedsPick,)

    def __init__(self, doc, feature=None):
        self.options = combine.with_defaults({})
        self.feature_ = feature
        if feature is not None:
            try:
                self.options.update(combine.read(feature))
            except Exception as exc:
                warn("could not read %s: %s" % (feature.Label, exc))
        self._looks = {}  # body name -> transparency before it was made see-through
        super().__init__(doc, "Combine" if feature is None else "Edit Combine", feature is not None)
        self.target = feature
        if feature is not None:
            self._show_picks()
            self.activate("tools")
            # The used-up tools show (see-through) while the Combine is edited, as in Fusion,
            # where editing rolls the design back to before the Combine: they can be clicked.
            self.after_recompute()
        else:
            self.activate("target")
            self.start_from_selection()
            self.dirty = True
            self._timer.stop()
            self._recompute()  # the preview (or the hint) is there when the dialog appears

    # -- form ----------------------------------------------------------------------------------
    def build_form(self):
        self.selection_box("target", "Target Body")
        self.selection_box("tools", "Tool Bodies")
        self.operation, _ = self.combo(
            "Operation", OPERATIONS, self.options["operation"], self._typed
        )
        self.new_body, _ = self.check_box(
            "New Body",
            self.options["new_body"],
            self._typed,
            "Put the result in a new body (the target body is used up like the tools)",
        )
        self.keep_tools, _ = self.check_box(
            "Keep Tools",
            self.options["keep_tools"],
            self._typed,
            "Keep the tool bodies in the design after combining",
        )

    def _typed(self):
        self.options["operation"] = self.operation.currentData()
        self.options["new_body"] = self.new_body.isChecked()
        self.options["keep_tools"] = self.keep_tools.isChecked()
        self.changed()

    def _show_picks(self):
        target = self.options["target"]
        if target is not None:
            text = target.Label
        elif self.options.get("frozen_target") and self.options["new_body"]:
            text = "Deleted body (kept as it was)"
        else:
            text = ""
        self.fields["target"].set_text(text)
        tools = self.options["tools"]
        text = bodies_gui.body_text(tools) if tools else ""
        kept = self.options.get("frozen") or 0
        if kept:
            # tool bodies deleted since: the Combine keeps them as they were
            more = "%d deleted body%s" % (kept, "" if kept == 1 else "s")
            text = "%s + %s" % (text, more) if text else more
        self.fields["tools"].set_text(text)

    def cleared(self, name):
        if name == "target":
            self.options["target"] = None
            self.options["frozen_target"] = False
        else:
            self.options["tools"] = []
            self.options["frozen"] = 0  # tool bodies deleted since go too
        self._show_picks()

    # -- clicks -----------------------------------------------------------------------------------
    def picked(self, obj, short, point):
        body = self._really_clicked(bodies.body_of(obj), point)
        if body is None or self._made_by_preview(body):
            return
        if self.active == "target":
            if body in self.options["tools"]:
                self.options["tools"].remove(body)
            self.options["target"] = body
            self._show_picks()
            self.activate("tools")
        else:
            if body is self.options["target"]:
                self.message.setText("That is the target body. Click another body as a tool.")
                return
            if body in self.options["tools"]:
                self.options["tools"].remove(body)
            else:
                self.options["tools"].append(body)
            self._show_picks()
        self.changed()

    def _made_by_preview(self, body):
        feature = self.target
        return (
            feature is not None and bodies.alive(feature) and combine.created_body(feature) is body
        )

    def _really_clicked(self, body, point):
        """The body a click means. The preview (the target's combined result, or the New
        Body) is drawn where the see-through tools are, so a click on a tool usually lands on
        the preview: the body really there under the pointer is the one meant (Fusion's
        preview cannot be clicked; its bodies can)."""
        feature = self.target
        if body is None or point is None or feature is None or not bodies.alive(feature):
            return body
        new_body = self._made_by_preview(body)
        on_target = body is self.options["target"] and not feature.NewBody
        if not new_body and not on_target:
            return body
        try:
            target = self.options["target"]
            before = feature.BaseFeature if on_target else target
            if target is not None and _touches(before, point):
                return target
            for tool in self.options["tools"]:
                if bodies.alive(tool) and _touches(tool, point):
                    return tool
        except Exception as exc:
            warn("Combine pick: %s" % exc)
        return None if new_body else body

    # -- preview ---------------------------------------------------------------------------------
    def apply(self):
        if self.options["target"] is None or not self.options["tools"]:
            # Nothing to preview yet: an earlier preview goes.
            if self.target is not None and not self.editing and bodies.alive(self.target):
                combine.remove(self.target)
                self.target = None
            combine.check(self.options)  # raises NeedsPick with the hint
        self.target = combine.build(self.options, self.target)

    def after_recompute(self):
        self._see_through()
        target = self.options["target"]
        if target is not None:
            bodies.show_tip(target)
        if self.target is not None and bodies.alive(self.target):
            bodies.show_tip(bodies.body_of(self.target))
            if self.options["new_body"] and target is not None:
                bodies.set_shown(target, False)
            elif target is not None:
                bodies.set_shown(target, True)
        for body in self.options["tools"]:
            bodies.set_shown(body, True)

    def preview_steps(self):
        return [self.target] if self.target is not None else []

    def can_finish(self):
        if self.target is None or not bodies.alive(self.target):
            try:
                combine.check(self.options)
            except combine.CombineError as exc:
                return str(exc)
            return "Pick the target body and the tool bodies."
        return ""

    # -- see-through tools -----------------------------------------------------------------------
    def _see_through(self):
        """Tools stay visible and see-through while the dialog is open (they are clicked to
        drop them); their own look comes back when it closes."""
        if not App.GuiUp:
            return
        wanted = {b.Name for b in self.options["tools"] if bodies.alive(b)}
        for name in list(self._looks):
            if name not in wanted:
                self._restore(name)
        for body in self.options["tools"]:
            if body.Name in self._looks or body.ViewObject is None:
                continue
            try:
                self._looks[body.Name] = int(body.ViewObject.Transparency)
                body.ViewObject.Transparency = SEE_THROUGH
            except Exception:
                pass

    def _restore(self, name):
        before = self._looks.pop(name, None)
        body = self.doc.getObject(name)
        if body is None or before is None or body.ViewObject is None:
            return
        try:
            body.ViewObject.Transparency = before
        except Exception:
            pass

    def restore_view(self):
        for name in list(self._looks):
            self._restore(name)
        try:
            from . import appearance

            for body in self.options["tools"]:
                if bodies.alive(body):
                    appearance.apply(body)
        except Exception:
            pass

    def after_close(self, ok):
        super().after_close(ok)
        try:
            used = bodies.consumed(self.doc)
            for body in self.options["tools"] + [self.options["target"]]:
                if body is not None and bodies.alive(body) and body.Name in used:
                    bodies.set_shown(body, False)  # shown while the dialog was open
        except Exception:
            pass
        feature = self.target
        if ok and feature is not None and bodies.alive(feature) and feature.NewBody:
            bodies.set_active_body(bodies.body_of(feature))


def _touches(obj, point, tol=1e-3):
    """True when `point` (design coordinates) is in or on the solid of `obj` (a body or a
    step)."""
    if obj is None or not bodies.alive(obj):
        return False
    shape = bodies.global_shape(obj)
    if shape.isNull() or not shape.Solids:
        return False
    return any(solid.isInside(point, tol, True) for solid in shape.Solids)


class CombineCommand:
    def GetResources(self):
        return {
            "MenuText": "Combine",
            "ToolTip": "Join, cut or intersect bodies: pick the target body, then the tool "
            "bodies (Keep Tools, New Body), with a live preview",
            "Pixmap": ui_icon_path("combine"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            _start(CombinePanel)
        except Exception as exc:
            warn("Combine could not start: %s" % exc)


def edit(feature):
    _edit(CombinePanel, feature)


COMMANDS = {"SciForge_Combine": CombineCommand}
EDITORS = {"SciForge::Combine": edit}

try:
    bodies_gui.install()
except Exception as _exc:  # never let an import fail the commands
    warn("body tools watch unavailable: %s" % _exc)
