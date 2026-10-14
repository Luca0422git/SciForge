# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Objects To Cut row for Revolve, Sweep and Loft (wave 4): the bodies a Join, Cut
or Intersect acts on, the way Extrude's "Bodies to Cut" row works (extrude_ui.py).

The row lists the bodies the feature's solid passes through (a Join: also those it only
touches face to face), as "2 bodies" and their names. Click the row, then click a body in
the 3D view to leave it out or take it back; while the row takes the clicks, the bodies it
lists show as see-through blue copies (a picture only). A Cut shows the solid it takes
away in see-through red while the dialog is open, as Extrude does (show_cut). The document side is
extrude_bodies.py (bodies_in_way, participants_of, the hidden follower steps); the wording
and the click rules are extrude_bodies_core.py. Never lets an exception out (warn()).
"""

from . import bodies, extrude_bodies, log, warn
from . import extrude_bodies_core as core
from .compat import QtWidgets


class BodiesRow:
    """One dialog's Objects To Cut row. `field` is the dialog's selection box named
    "bodies" (it calls panel.activate("bodies") / panel.clear_field("bodies")); `what`
    names the feature in messages ("revolve", "sweep", "loft")."""

    def __init__(self, panel, form, field, what):
        self.panel = panel
        self.field = field
        self.what = what
        self.label = QtWidgets.QLabel(core.row_label("cut"))
        field.button.setToolTip(
            "The bodies this %s changes. Click here, then click a body in the view to leave "
            "it out or take it back." % what
        )
        form.addRow(self.label, field.widget)
        self.names = QtWidgets.QLabel("")
        self.names.setWordWrap(True)
        form.addRow(self.names)
        self.excluded = set()  # names of bodies in the way that were clicked away
        self.stored = None  # editing: the names the step was saved with
        self.way = None  # (names it passes through, names it touches), or None
        self.problem = ""  # e.g. a cut that goes through no body (OK refused)
        self.highlight = None
        self.closed = False
        self.paused = False  # body hiding paused while a Join merges bodies (see built())
        self.tool = None  # the feature's solid at the last test (design coordinates)
        self.cut_view = None  # the red cut preview (cut_preview.CutPreview)

    # -- reading an existing step -------------------------------------------------------
    def read(self, stored, feature):
        """Editing: start from the step's saved list (`stored`: bodies or None for a step
        made before it could act on several bodies: its own body). A step saved as a New
        Body has no list: switched to Join or Cut, it acts on every body in its way."""
        if self.panel.options.get("operation") not in ("join", "cut", "intersect"):
            self.stored = None
        elif stored is not None:
            self.stored = [b.Name for b in stored]
        else:
            body = bodies.body_of(feature) if feature is not None else None
            self.stored = [body.Name] if body is not None else None

    # -- the bodies in the way ----------------------------------------------------------
    def update(self, tool_fn, lead):
        """Test which bodies the solid tool_fn() passes through (before `lead`, the step
        previewed or edited)."""
        self.tool = None
        try:
            tool = tool_fn()
            self.tool = tool
            found = extrude_bodies.bodies_in_way(self.panel.doc, tool, lead)
            self.way = tuple([b.Name for b in f] for f in found)
        except Exception as exc:
            self.way = None
            log("%s bodies: not told (%s)" % (self.what, exc))
            return
        if self.stored is not None:
            # Editing: bodies clicked away before stay away.
            touched = self.touched(self.panel.options.get("operation"))
            self.excluded = core.excluded_for_edit(touched, self.stored)
            self.stored = None

    def touched(self, operation):
        if self.way is None:
            return None
        return self.way[1] if operation == "join" else self.way[0]

    def for_build(self, operation):
        """options["bodies"] for the build: the bodies in the way minus those clicked away;
        None when it cannot be told or the operation acts on no body (the profile's body
        only, as before). Raises ValueError when every body was clicked away."""
        self.problem = ""
        if operation not in ("join", "cut", "intersect"):
            return None
        touched = self.touched(operation)
        if touched is None:
            return None
        if not touched and operation in ("cut", "intersect"):
            self.problem = extrude_bodies.nothing_touched({"operation": operation}, self.what)
            return None
        names = core.participants(touched, self.excluded)
        if touched and not names:
            raise ValueError(
                "%s is empty. Click it, then click a body to take it back."
                % core.row_label(operation)
            )
        found = [self.panel.doc.getObject(n) for n in names]
        return [b for b in found if b is not None]

    # -- what the row shows ----------------------------------------------------------------
    def show(self, operation, active, has_picks):
        try:
            self._show(operation, active, has_picks)
        except Exception as exc:
            warn("%s bodies row: %s" % (self.what, exc))

    def _show(self, operation, active, has_picks):
        label = core.row_label(operation)
        visible = bool(label) and has_picks
        for widget in (self.label, self.field.widget, self.names):
            widget.setVisible(visible)
        if not visible:
            self._highlight([])
            return
        self.label.setText(label)
        touched = self.touched(operation)
        if touched is None:
            body = self.panel.body
            names = [body.Name] if body is not None else []
        else:
            names = core.participants(touched, self.excluded)
        self._highlight(names if active else [])
        labels = []
        for name in names:
            obj = self.panel.doc.getObject(name)
            labels.append(obj.Label if obj is not None else name)
        self.field.set_text(core.count_text(len(labels)))
        text = core.names_text(labels)
        if not labels:
            text = (
                "Touches no body: a new body is made."
                if operation == "join"
                else "The %s goes through no body." % self.what
            )
        if active:
            text += "\nClick a body to leave it out or take it back."
        self.names.setText(text)

    def _highlight(self, names):
        if self.closed:
            return
        try:
            from . import cut_preview

            if not names:
                if self.highlight is not None:
                    self.highlight.clear()
                return
            shapes = []
            lead = getattr(self.panel, "target", None)
            for name in names:
                body = self.panel.doc.getObject(name)
                if body is None:
                    continue
                try:
                    shape = extrude_bodies.before_shape(body, lead)
                except Exception:
                    shape = None
                if shape is None or shape.isNull() or not shape.Solids:
                    shape = bodies.global_shape(body)
                shapes.append(shape)
            if self.highlight is None:
                import FreeCADGui as Gui

                self.highlight = cut_preview.BodyHighlight(Gui.ActiveDocument.ActiveView)
            self.highlight.show(shapes)
        except Exception as exc:
            warn("%s bodies highlight: %s" % (self.what, exc))

    def built(self, lead):
        """After a build: a Join that merges bodies, or a cut that takes all of one, keeps
        them shown while the dialog is open (the used-up body would vanish from under the
        next click), as Extrude does. Hiding resumes when the dialog closes."""
        try:
            on = False
            if lead is not None and extrude_bodies._alive(lead):
                followers = extrude_bodies.followers_of(lead)
                on = any(extrude_bodies.is_merge(f) for f in followers)
                on = on or bool(extrude_bodies.used_up_by(lead))
            self._pause(on)
        except Exception as exc:
            warn("%s bodies: %s" % (self.what, exc))

    def _pause(self, on):
        doc = self.panel.doc
        if on and not self.paused:
            bodies.pause(doc)
            self.paused = True
        elif not on and self.paused:
            bodies.resume(doc)
            self.paused = False

    def show_cut(self, operation, failed):
        """Fusion shows a cut in red while the dialog is open: the solid the feature takes
        away, drawn over the part (a picture only; the features keep their colours)."""
        if self.closed:
            return
        try:
            from . import cut_preview

            shape = self.tool if operation == "cut" and not failed else None
            if shape is None or shape.isNull() or not shape.Solids:
                if self.cut_view is not None:
                    self.cut_view.clear()
                return
            if self.cut_view is None:
                import FreeCADGui as Gui

                self.cut_view = cut_preview.CutPreview(Gui.ActiveDocument.ActiveView)
            self.cut_view.show(shape)
        except Exception as exc:
            warn("%s cut preview: %s" % (self.what, exc))

    # -- clicks -----------------------------------------------------------------------------
    def picked(self, obj, operation):
        """A click on a body with the row active: leave it out or take it back. Returns
        what to say in the dialog ("" when it worked)."""
        body = bodies.body_of(obj)
        solid = bodies.is_body(obj) or "BaseFeature" in obj.PropertiesList
        if body is None or not solid:  # a sketch or a plane is no body
            return "Click a body to leave it out or take it back."
        touched = self.touched(operation) or []
        excluded, what = core.toggle(touched, self.excluded, body.Name)
        if what == "not_in_way":
            return "%s is not in the %s's way, so it cannot change it." % (body.Label, self.what)
        self.excluded = excluded
        log(
            "%s: %s %s" % (self.what, body.Label, "left out" if what == "dropped" else "taken back")
        )
        return ""

    def clear_all(self, operation):
        """The row's x: every body left out (the dialog then asks for one)."""
        self.excluded = set(self.touched(operation) or [])

    def cleanup(self):
        self.closed = True
        try:
            self._pause(False)
        except Exception as exc:
            warn("%s bodies: %s" % (self.what, exc))
        for view in (self.highlight, self.cut_view):
            if view is not None:
                try:
                    view.clear()
                except Exception:
                    pass
        self.highlight = self.cut_view = None
