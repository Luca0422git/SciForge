# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shell with Fusion's dialog.

Pressing Shell with nothing selected opens the dialog, which waits for a pick:
  * click faces of the part to take them away (click a picked one again to drop it);
    Tangent Chain also takes the faces that continue a picked face smoothly;
  * pick the body itself (click it in the browser, or have it selected before pressing
    Shell) to make it hollow, a closed wall all round;
  * faces (or the body) selected before pressing Shell are taken at once.
Inside Thickness / Outside Thickness with Direction Inside, Outside or Both, Shell Type
Sharp or Rounded (how walls meet outside the part). The blue arrows on the opening's rim
drag the thicknesses. The result is previewed solid inside the see-through part. A wall
dragged or typed thicker than fits stops at the thickest one that works and the dialog says
so (Luca, 2026-10-21; Fusion refuses it: value_limits.py); a wall from a formula that does
not fit is explained (with the thickest one that does) and OK waits for a fix. Fields take
parameters and formulas ("wall", "wall * 2").

Built on FreeCAD's PartDesign::Thickness, or SciForge's ShellFeature for what that cannot
do (hollow body, Both): see shelling.py. Double-click the step in the timeline to edit.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import bodies, commands, hole_common, log, modify_bodies, pickpanel, preview, shelling
from . import ui_icon_path, value_limits, warn
from .compat import QtWidgets
from .taskui import DistanceField, ValueBoxes

PICK_HELP = (
    "Click faces to take away (click one again to drop it).\n"
    "Pick the body in the browser to make it hollow."
)
ARROW_LENGTH = 2.2  # the arrow's length in units of the handle size (ball, shaft, head)
DIRECTION_ITEMS = [("Inside", "inside"), ("Outside", "outside"), ("Both", "both")]
TYPE_ITEMS = [
    ("Sharp", "sharp", True, "Walls meet in sharp corners outside the part"),
    ("Rounded", "rounded", True, "Walls meet in rounded corners outside the part"),
]


class ViewProviderShell:
    """View provider of SciForge's shell feature (hollow body / Both)."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        return ui_icon_path("shell")

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return None
        edit_shell(vobj.Object)
        return True

    def unsetEdit(self, vobj, mode=0):
        return None

    def doubleClicked(self, vobj):
        edit_shell(vobj.Object)
        return True

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def start_body(preferred=None):
    """(body, base) a new shell works on: the preferred/active body if it has a solid,
    else the first body of the design that has one."""
    doc = App.ActiveDocument
    if doc is None:
        return None, None
    candidates = []
    for body in (preferred, commands.find_body()):
        if body is not None and body not in candidates:
            candidates.append(body)
    candidates += [b for b in doc.findObjects("PartDesign::Body") if b not in candidates]
    for body in candidates:
        base = shelling.solid_base(body)
        if base is not None:
            return body, base
    return (candidates[0] if candidates else None), None


class ShellPanel(pickpanel.PickPanel, value_limits.LimitedValues):
    title = "Shell"
    icon = "shell"
    last = None  # the most recent panel (tests and diagnostics)

    def __init__(self, doc, feature=None, picks=None, body=None):
        super().__init__(doc, "Shell" if feature is None else "Edit Shell")
        ShellPanel.last = self
        self.target = feature
        self.editing = feature is not None
        self.picked = []  # faces the user clicked, on self.base
        self.whole = False  # the body itself is picked: it becomes hollow
        self.options = shelling.default_options()
        self.formulas = {"inside": "", "outside": ""}
        self.formula_errors = {}
        self.arrows = []  # (pickpanel.Arrow, spot, origin, direction) in global coordinates
        self.value_boxes = ValueBoxes(self, default="inside#0")  # the box next to each arrow
        self._chains = {}
        self.limit_init()  # a wall past what fits stops at the thickest that works
        if feature is not None:
            self.body = shelling.owner_body(feature)
            base, names, options, formulas = shelling.read(feature)
            self.base = base
            self.picked = list(names)
            self.whole = not names
            self.options.update(options)
            self.formulas.update({k: v for k, v in formulas.items() if v})
            for follower in modify_bodies.followers_of(feature):  # the other bodies (Fusion)
                member = self.add_member(bodies.body_of(follower), follower.BaseFeature)
                link = follower.Faces
                member.picked = [s.lstrip("?") for s in (link[1] if link else []) if s]
                member.whole = not member.picked
                member.target = follower
        else:
            self.body, self.base = start_body(body)
        self._build()
        self.finish_layout()
        self.limit_label = value_limits.note_label()  # "Largest that fits here: ..."
        self.layout.addRow(self.limit_label)
        try:
            self._start(picks or [])
        except Exception as exc:  # never leave a half-open dialog without a reason
            self.say("⚠ %s" % exc)
            warn("Shell could not start picking: %s" % exc)

    # -- layout -------------------------------------------------------------------------
    def _build(self):
        self.selection = hole_common.SelectionField(self, "faces", "Select")
        self.selection.set_active(True)
        self.selection.button.setToolTip(PICK_HELP)
        self.layout.addRow("Faces/Body", self.selection.widget)
        self.help = QtWidgets.QLabel(PICK_HELP)
        self.help.setWordWrap(True)
        self.help.setStyleSheet("color: #9aa4b1;")
        self.layout.addRow(self.help)
        self.tangent = QtWidgets.QCheckBox()
        self.tangent.setChecked(bool(self.options.get("tangent", True)))
        self.tangent.setToolTip("Also take away the faces that continue a picked face smoothly")
        self.tangent.toggled.connect(self._tangent_toggled)
        self.layout.addRow("Tangent Chain", self.tangent)
        self.inside = DistanceField(self.options["inside"], on_change=self._inside_typed)
        self.inside.widget.setProperty("minimum", 0.0)
        self.inside_label = QtWidgets.QLabel("Inside Thickness")
        self.layout.addRow(self.inside_label, self.inside.widget)
        self.outside = DistanceField(self.options["outside"], on_change=self._outside_typed)
        self.outside.widget.setProperty("minimum", 0.0)
        self.outside_label = QtWidgets.QLabel("Outside Thickness")
        self.layout.addRow(self.outside_label, self.outside.widget)
        self.direction = pickpanel.combo(DIRECTION_ITEMS, self.options["direction"])
        self.direction.currentIndexChanged.connect(self._direction_changed)
        self.layout.addRow("Direction", self.direction)
        self.shell_type = pickpanel.combo(TYPE_ITEMS, self.options["shell_type"])
        self.shell_type.currentIndexChanged.connect(self._type_changed)
        self.layout.addRow("Shell Type", self.shell_type)
        self.formula_label = QtWidgets.QLabel("")
        self.formula_label.setWordWrap(True)
        self.formula_label.setStyleSheet("color: #b8c7d9;")
        self.layout.addRow(self.formula_label)
        # Fusion's fields take parameters and formulas; FreeCAD's number field does not.
        self._formula_inputs = [
            preview.FormulaInput(self, "inside", self.inside),
            preview.FormulaInput(self, "outside", self.outside),
        ]
        self._rows()
        self._show_formulas()

    def _rows(self):
        direction = self.direction.currentData()
        for widget in (self.inside.widget, self.inside_label):
            widget.setVisible(direction in ("inside", "both"))
        for widget in (self.outside.widget, self.outside_label):
            widget.setVisible(direction in ("outside", "both"))

    # -- starting -----------------------------------------------------------------------
    def _start(self, picks):
        if self.base is None:
            self.say("⚠ Make a solid first (Create Sketch, then Extrude).")
            return
        for obj, short in picks:
            if not short and obj.TypeId == "PartDesign::Body":
                self._pick_body(obj)
            elif short.startswith("Face"):
                self._add_face(obj, short)
        self.remember_later(self.target if self.editing else self.base)
        self.start_picking()
        self._picks_updated(schedule=False)
        if self.target is not None:
            self.show_preview(True)
        if self.has_picks():
            self.schedule()

    # -- the picks (PickPanel calls these) ---------------------------------------------------
    def has_picks(self):
        return self.whole or bool(self.picked)

    def chain(self, name):
        if not self.tangent.isChecked() or self.base is None:
            return [name]
        if name not in self._chains:
            try:
                self._chains[name] = shelling.tangent_faces(self.base.Shape, [name])
            except Exception:
                self._chains[name] = [name]
        return self._chains[name]

    def names(self):
        """The faces taken away: the picks with their tangent chains."""
        if self.whole:
            return []
        found = []
        for pick in self.picked:
            for name in self.chain(pick):
                if name not in found:
                    found.append(name)
        return found

    def shown(self):
        names = self.names()
        entries = [(self.base, names)] if names and self.base is not None else []
        for member in self.members:
            member_names = self.member_names(member)
            if member_names and member.base is not None:
                entries.append((member.base, member_names))
        return entries

    # -- other bodies (Fusion's Shell takes faces or bodies of several bodies) ----------------
    def member_chain(self, member, name):
        if not self.tangent.isChecked():
            return [name]
        if name not in member.chains:
            try:
                member.chains[name] = shelling.tangent_faces(member.base.Shape, [name])
            except Exception:
                member.chains[name] = [name]
        return member.chains[name]

    def member_names(self, member):
        if member.whole:
            return []
        found = []
        for pick in member.picked:
            for name in self.member_chain(member, pick):
                if name not in found:
                    found.append(name)
        return found

    def _joinable(self, obj):
        """(body, base) of another body `obj` (or a face's step) belongs to, when the dialog
        already has picks: it joins the same Shell step (Fusion)."""
        if not self.has_picks() and not self.members:
            return None
        body = obj if obj.TypeId == "PartDesign::Body" else shelling.owner_body(obj)
        if body is None or body is self.body:
            return None
        member = self.member(body)
        if member is not None:
            return body, member.base
        base = modify_bodies.base_for(self.target, body)
        if base is None or base.Shape.isNull() or not base.Shape.Solids:
            return None
        return body, base

    def _other_body_solid(self, obj):
        """(body, base) when `obj` belongs to another body with a solid, and the dialog may
        still move there (nothing picked yet, not editing)."""
        if self.editing or self.has_picks() or self.members:
            return None
        body = obj if obj.TypeId == "PartDesign::Body" else shelling.owner_body(obj)
        if body is None or body is self.body:
            return None
        base = shelling.solid_base(body)
        if base is None:
            return None
        return body, base

    def allow(self, obj, short):
        if self.base is None or obj is None:
            return False
        if not short:
            return obj.TypeId == "PartDesign::Body" and (
                obj is self.body
                or self._other_body_solid(obj) is not None
                or self._joinable(obj) is not None
            )
        if not short.startswith("Face"):
            return False
        if obj.Name == self.base.Name:
            return True
        if self.member_of_object(obj) is not None:
            return True
        if shelling.owner_body(obj) is self.body:
            return False  # an older step of this body (a click in the timeline roll-back)
        follow = self._other_body_solid(obj)
        if follow is not None:
            return obj is follow[1]
        join = self._joinable(obj)
        return join is not None and obj is join[1]

    def picks_changed(self, added, dropped):
        changed = False
        for obj, short, _point in dropped:
            if short.startswith("Face") and obj is self.base:
                changed = self._drop(short) or changed
            elif short.startswith("Face") and self.member_of_object(obj) is not None:
                changed = self._drop_member_face(self.member_of_object(obj), short) or changed
        for obj, short, _point in added:
            if not short:
                if obj.TypeId == "PartDesign::Body":
                    changed = self._pick_body(obj) or changed
            elif short.startswith("Face"):
                changed = self._add_face(obj, short) or changed
        if changed:
            self._picks_updated(schedule=False)
        return changed

    def _add_face(self, obj, short):
        if self.base is None:
            return False
        member = self.member_of_object(obj)
        if obj is not self.base and member is None:
            follow = self._other_body_solid(obj)
            join = self._joinable(obj) if follow is None else None
            if follow is not None:
                self.switch_body(*follow)
                pickpanel.activate(follow[0])
                self._chains = {}
            elif join is not None:
                member = self.add_member(*join)
                return self._add_member_face(member, obj, short)
            name = pickpanel.match_face(self.base, obj, short)
        elif member is not None:
            return self._add_member_face(member, obj, short)
        else:
            name = short
        if not name or not shelling.removable(self.base.Shape, name):
            self.help.setText("That face is not on %s; click a face of it." % self.body.Label)
            return False
        self.whole = False
        if name in self.picked or name in self.names():
            return False
        self.picked.append(name)
        return True

    def _add_member_face(self, member, obj, short):
        name = pickpanel.match_face(member.base, obj, short) if obj is not member.base else short
        if not name or not shelling.removable(member.base.Shape, name):
            return False
        member.whole = False
        if name in member.picked or name in self.member_names(member):
            return False
        member.picked.append(name)
        return True

    def _drop_member_face(self, member, name):
        before = len(member.picked)
        member.picked = [p for p in member.picked if name not in self.member_chain(member, p)]
        if not member.picked and not member.whole:
            self.drop_member(member.body)
        return len(member.picked) != before

    def _drop(self, name):
        before = len(self.picked)
        self.picked = [p for p in self.picked if name not in self.chain(p)]
        return len(self.picked) != before

    def _pick_body(self, obj):
        if obj is not self.body:
            member = self.member(obj)
            if member is not None:  # a picked body clicked again in the browser: dropped
                self.drop_member(obj)
                return True
            join = self._joinable(obj)
            if join is not None:
                member = self.add_member(*join)
                member.whole = True
                member.picked = []
                return True
            follow = self._other_body_solid(obj)
            if follow is None:
                self.help.setText("This shell belongs to %s." % self.body.Label)
                return False
            self.switch_body(*follow)
            pickpanel.activate(follow[0])
            self._chains = {}
        if self.whole:
            return False
        self.whole = True
        self.picked = []
        return True

    def activate(self, name):
        self.selection.set_active(True)

    def clear_field(self, name):
        if self.has_picks() or self.members:
            self.picked = []
            self.whole = False
            for member in list(self.members):
                self.drop_member(member.body)
            self._sync()
            self._picks_updated()

    def _picks_updated(self, schedule=True):
        self.limits.note = ""  # a limit found for the old picks no longer applies
        if self.whole:
            text = "Body"
        else:
            count = len(self.names())
            text = "%d face%s" % (count, "" if count == 1 else "s") if count else ""
        if self.members:
            text = "%s + %d other bod%s" % (
                text or "0 faces",
                len(self.members),
                "y" if len(self.members) == 1 else "ies",
            )
        self.selection.set_text(text)
        if self.whole:
            self.help.setText("The body becomes hollow. Click a face to take it away instead.")
        elif not self.picked:
            self.help.setText(PICK_HELP)
        else:
            self.help.setText(
                "Click more faces to take away (also of other bodies), or a picked one to "
                "drop it."
            )
        self._update_arrows()
        if schedule:
            self.schedule()

    def _tangent_toggled(self, *_):
        self.options["tangent"] = self.tangent.isChecked()
        self._chains = {}
        self._sync()
        self._picks_updated()

    # -- values -----------------------------------------------------------------------------
    def _inside_typed(self, value):
        self._typed("inside", value)

    def _outside_typed(self, value):
        self._typed("outside", value)

    def _typed(self, what, value):
        field = self.inside if what == "inside" else self.outside
        source = "formula" if self.formulas.get(what) else "typed"
        held = self.limit_edit(what, value, source)
        if held != value:
            value_limits.show_held(self.limit_shower, what, field, value, held)
            value = held
        self.options[what] = value
        found = False
        for dragger, spot, _origin, _direction in self.arrows:
            if spot["what"] == what:
                dragger.set_distance(max(value, 0.0))
                found = True
        if not found and self.has_picks():
            self._update_arrows()  # the arrow comes back with a value it can show
        self.schedule()

    def _dragged(self, what, distance, released=False):
        value = max(0.01, round(distance, 2))
        held = self.limit_edit(what, value, "dragged")
        if held != value:
            value = held
            self._arrow_to(what, value)  # the arrow stops at the thickest wall that fits
        elif released and abs(value - distance) > 1e-9:
            # dragged through the surface: the arrow goes back to the thinnest wall
            for dragger, spot, _origin, _direction in self.arrows:
                if spot["what"] == what:
                    dragger.set_distance(value)
        changed = abs(float(self.options.get(what, -1.0)) - value) > 1e-12
        self.options[what] = value
        field = self.inside if what == "inside" else self.outside
        field.set_value(value)
        if self.formulas.get(what):
            self.formulas[what] = ""  # a drag gives a plain number
            self._show_formulas()
            changed = True
        if changed:
            self.schedule()
        elif self.limits.note and not self.error:
            self.show_status()  # held at the limit: nothing to rebuild

    def _arrow_to(self, what, value):
        for dragger, spot, _origin, _direction in self.arrows:
            if spot["what"] == what:
                try:
                    dragger.set_distance(value)
                except Exception:
                    pass

    # -- walls past what fits (value_limits.LimitedValues) ---------------------------------------
    def limit_key(self, what):
        options = {k: v for k, v in self.options.items() if k != what}
        return value_limits.make_key(
            "shell",
            self.base.Shape if self.base is not None else None,
            self.names(),
            self.whole,
            [(m.body.Name, self.member_names(m)) for m in self.members],
            options,
            what,
        )

    def limit_works(self, what):
        options = dict(self.options)
        shape, names = self.base.Shape, list(self.names())
        members = [(m.base.Shape, list(self.member_names(m))) for m in self.members]

        def works(value):
            trial = dict(options)
            trial[what] = value
            shelling.trial(shape, names, trial)
            for member_shape, member_names in members:
                shelling.trial(member_shape, member_names, trial)
            return True

        return works

    def limit_value(self, what):
        return float(self.options.get(what, 0.0))

    def limit_set(self, what, value):
        self.options[what] = value
        field = self.inside if what == "inside" else self.outside
        value_limits.show_held(self.limit_shower, what, field, field.value(), value)
        self._arrow_to(what, value)

    def limit_keep(self):
        return self.base.Shape if self.base is not None else None

    def _direction_changed(self, *_):
        self.options["direction"] = self.direction.currentData()
        self._rows()
        self._update_arrows()
        self.schedule()

    def _type_changed(self, *_):
        self.options["shell_type"] = self.shell_type.currentData()
        self.schedule()

    def _collect(self):
        self.options["direction"] = self.direction.currentData()
        self.options["shell_type"] = self.shell_type.currentData()
        self.options["tangent"] = self.tangent.isChecked()
        if not self.formulas.get("inside"):
            self.options["inside"] = self.limit_held("inside", self.inside.value())
        if not self.formulas.get("outside"):
            self.options["outside"] = self.limit_held("outside", self.outside.value())

    # -- formulas (preview.FormulaInput calls these) -------------------------------------------
    def formula_typed(self, key, text, value):
        self.formula_errors.pop(key, None)
        self.formulas[key] = text
        self.options[key] = value
        self._show_formulas()
        self._typed(key, value)

    def formula_cleared(self, key):
        self.formula_errors.pop(key, None)
        if self.formulas.get(key):
            self.formulas[key] = ""
            self._show_formulas()
        field = self.inside if key == "inside" else self.outside
        self._typed(key, field.value())

    def formula_failed(self, key, text):
        self.formula_errors[key] = text
        self.show_status()

    def _show_formulas(self):
        lines = []
        for key, label in (("inside", "Inside Thickness"), ("outside", "Outside Thickness")):
            if self.formulas.get(key):
                lines.append("%s = %s" % (label, self.formulas[key]))
        self.formula_label.setText("\n".join(lines))

    # -- arrows ---------------------------------------------------------------------------
    def _remove_arrows(self):
        for dragger, _spot, _origin, _direction in self.arrows:
            dragger.remove()
        self.arrows = []

    def _update_arrows(self):
        self._remove_arrows()
        if self.base is None or self._closed or not self.has_picks():
            return
        try:
            self._collect()
            view = Gui.ActiveDocument.ActiveView
            toward = -view.getViewDirection()
            placement = self.body.getGlobalPlacement() if self.body else App.Placement()
            local_toward = placement.Rotation.inverted().multVec(toward)
            shape = self.base.Shape
            spots = shelling.arrow_spots(shape, self.names(), self.options, local_toward)
            size = max(2.0, min(shape.BoundBox.DiagonalLength * 0.06, 12.0))
            for spot in spots:
                # the ball sits where the wall ends (rim + thickness), the arrow beyond it
                local = spot["point"] + spot["lift"] * (0.25 * size)
                origin = placement.multVec(local)
                direction = placement.Rotation.multVec(spot["direction"])
                value = float(self.options.get(spot["what"], 1.0))
                dragger = pickpanel.Arrow(
                    origin,
                    direction,
                    value,
                    size * ARROW_LENGTH,
                    on_drag=lambda d, w=spot["what"]: self._dragged(w, d),
                    on_release=lambda d, w=spot["what"]: self._dragged(w, d, True),
                )
                self.arrows.append((dragger, spot, origin, direction))
                self._attach_box(dragger, spot["what"], len(self.arrows) - 1)
        except Exception as exc:
            warn("Shell arrow unavailable: %s" % exc)

    def _attach_box(self, dragger, what, index):
        """The value box next to an arrow: the thickness field's text (inside or outside),
        and a value or formula typed in it goes to that field."""
        field = self.inside if what == "inside" else self.outside
        return self.value_boxes.attach(
            dragger,
            "%s#%d" % (what, index),
            lambda: field.widget.text(),
            lambda text: self._box_typed(what, text),
        )

    def _box_typed(self, what, text):
        if self._closed:
            return
        for formula in self._formula_inputs:
            if formula.key == what:
                formula.take(text)
                return

    # -- preview --------------------------------------------------------------------------
    def _preview(self):
        if self.limit_waits():
            return  # the search of the thickest wall that fits previews when it ends
        if self._closed or self.base is None:
            return
        self._collect()
        if self.formula_errors:
            self.show_status()
            return
        names = self.names()
        if not names and not self.whole:
            self.error = None
            if self.target is not None and not self.editing:
                target, self.target = self.target, None
                self._looks.restore()
                self._ghost = False
                shelling.remove(target)
                self.quiet_recompute()  # the body's shape is the step before again
                self.prepare_display()
            self.show_preview(False)
            self.show_status()
            return
        try:
            shelling.trial(self.base.Shape, names, self.options)
            for member in self.members:
                try:
                    shelling.trial(member.base.Shape, self.member_names(member), self.options)
                except shelling.ShellError as exc:
                    raise shelling.ShellError("%s: %s" % (member.body.Label, exc))
        except shelling.ShellError as exc:
            held = self.limit_refuse(str(exc))
            if held == "again":
                self._preview()  # held at the thickest wall that fits: preview that
                return
            if held == "later":
                return  # looked for one trial per event-loop turn; previews when found
            self.error = str(exc)
            self.show_status()
            self._hint.start()
            return
        self.error = None
        self.limit_good()
        if self.target is None:
            self.target = shelling.make(
                self.body, self.base, names, self.options, formulas=self.formulas
            )
        else:
            new = shelling.update(self.target, self.base, names, self.options, self.formulas)
            if new is not self.target:
                self._looks.restore()  # the old preview's look; the new one gets its own
                self._ghost = False
                self.target = new
        self._sync_members()
        self.quiet_recompute()
        self.follow_later()
        self.show_preview(True)
        self.show_status()

    def _sync_members(self):
        """The other bodies' follower steps match the members (made, updated, removed)."""
        try:
            followers = modify_bodies.sync(
                self.target,
                [(m.body, self.member_names(m)) for m in self.members],
                modify_bodies.ShellFollower,
                "Shell",
            )
        except modify_bodies.FollowerError as exc:
            self.error = str(exc)
            return
        for member, follower in zip(self.members, followers):
            member.target = follower

    def _compute_hint(self):
        """A wall from a formula that does not fit (it is not held at the limit): the error
        also says the thickest wall that fits."""
        try:
            if self._closed or not self.error or self.base is None:
                return
            text = self.limit_hint(self.error)
            if text != self.error and self.error:
                self.say("⚠ " + text)
        except Exception as exc:
            warn("Shell thickness hint: %s" % exc)

    def show_status(self):
        if self.formula_errors:
            self.say("⚠ " + list(self.formula_errors.values())[0])
            return
        if self.base is None:
            self.say("⚠ Make a solid first (Create Sketch, then Extrude).")
            return
        if self.error:
            self.say("⚠ " + self.error)
            return
        obj = self.target
        if obj is None or not self.has_picks():
            self.say("")
            return
        text = preview.failure(obj)
        if text:
            self.say("⚠ " + shelling.friendly(text))
            return
        for member in self.members:
            text = preview.failure(member.target) if member.target is not None else ""
            if text:
                self.say("⚠ %s: %s" % (member.body.Label, shelling.friendly(text)))
                return
        broken = self.later_broken()
        if broken:
            self.say("⚠ Later steps no longer work: %s" % ", ".join(broken))
            return
        self.say("")

    def say(self, text):
        """The dialog's message. The note of a wall held at its limit shows under it while
        there is no error."""
        self.message.setText(text)
        limits = getattr(self, "limits", None)
        note = "" if text or limits is None else limits.note
        value_limits.show_note(getattr(self, "limit_label", None), note)

    def members_failed(self):
        for member in self.members:
            obj = member.target
            if obj is None:
                return True
            state = list(getattr(obj, "State", []))
            if "Invalid" in state or "Error" in state:
                return True
        return False

    # -- OK / Cancel ------------------------------------------------------------------------
    def accept(self):
        try:
            self._timer.stop()
            if self.base is None:
                self.say("⚠ Make a solid first (Create Sketch, then Extrude).")
                return False
            if not self.has_picks():
                self.say(
                    "⚠ Select the faces to take away, or pick the body in the browser "
                    "to make it hollow."
                )
                return False
            self.limit_accept()
            try:
                self._preview()
            finally:
                self.limit_accepted()
            obj = self.target
            if self.formula_errors or self.error or obj is None:
                self.show_status()
                return False
            state = list(obj.State)
            if "Invalid" in state or "Error" in state or not obj.Shape.isValid():
                self.show_status()
                return False
            if self.members_failed():
                self.show_status()
                return False
            return self.finish_ok()
        except Exception as exc:
            self.say("⚠ %s" % exc)
            return False

    def cleanup(self):
        self.limit_cancel()
        value_limits.busy(self, False)
        self._remove_arrows()
        self.value_boxes.discard()
        super().cleanup()


# -- command -----------------------------------------------------------------------------
class ShellCommand:
    def GetResources(self):
        return {
            "MenuText": "Shell",
            "ToolTip": "Hollow out the part: click the faces to take away (or pick the body), "
            "set the wall thickness inside, outside or both, with a live preview",
            "Pixmap": ui_icon_path("shell"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            start()
        except Exception as exc:
            warn("Shell could not start: %s" % exc)


def start():
    """Run Shell: faces or a body selected beforehand are taken at once; with nothing
    selected the dialog opens and waits for picks."""
    selection = pickpanel.capture_selection()
    picked_body = pickpanel.selected_body()
    if not commands.finish_open_dialog():
        return None
    doc = App.ActiveDocument
    if doc is None:
        return None
    body, base = start_body(picked_body)
    if base is None:
        commands.tell("Shell needs a solid: make one first (Create Sketch, then Extrude).")
        return None
    pickpanel.activate(body)
    pickpanel.reselect(selection)
    picks = [(obj, short) for obj, short, _p in pickpanel.selection_entries(doc)]
    panel = None
    try:
        panel = ShellPanel(doc, picks=picks, body=body)
        Gui.Control.showDialog(panel)
    except Exception:
        if panel is not None and not panel._closed:
            try:
                panel.reject()
            except Exception:
                pass
        raise
    log("shell started with %d pick(s)" % len(picks))
    return panel


def edit_shell(obj):
    """Timeline double-click: the Shell dialog on the existing shell."""
    try:
        if Gui.Control.activeDialog() and not commands.finish_open_dialog():
            return
        Gui.Control.showDialog(ShellPanel(obj.Document, feature=obj))
    except Exception as exc:
        warn("could not edit %s: %s" % (obj.Label, exc))


COMMANDS = {"SciForge_Shell": ShellCommand}
EDITORS = {shelling.NATIVE: edit_shell, "SciForge::" + shelling.KIND: edit_shell}
