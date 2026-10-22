# SPDX-License-Identifier: LGPL-2.1-or-later
"""Draft with Fusion's dialog: Type Fixed Plane or Parting Line, Draft Sides One Side / Two
Side / Symmetric, faces of one or several bodies.

Pressing Draft with nothing selected opens the dialog, which waits for the Pull Direction:
click a flat face of the part, or one of the big origin squares shown while that box is blue
(or a plane in the browser). The pull direction is shown as a blue arrow; clicking the arrow
or the flip button next to the box turns it round.
  Fixed Plane    the faces turn about where they meet the plane picked as Pull Direction.
  Parting Line   the Parting Tool box takes the line the faces turn about: an origin square, a
                 plane, a flat face, edges of the part, a sketch (in the browser) or its
                 curves. Fix Parting Line keeps that line where it is (Move Parting Line is
                 not built: greyed with the reason).
The Faces box then takes the clicks: click the faces to tilt (click one again to drop it),
flat, round or free-form walls (the side of an extruded spline), also faces of other bodies
(one Draft step changes them all); Tangent Chain picks the faces
that continue a picked one smoothly. Draft Sides: One Side tilts the faces one way (Parting
Line: only the pull side of the line), Two Side splits them at the plane or line and tilts
each side away from it (Angle 1 toward the pull direction, Angle 2 the other way),
Symmetric the same with one angle. Drag the blue curved handle or type the angle; a positive
angle makes the part narrower toward the pull direction. Faces that cannot be tilted do not
light up. An angle dragged or typed past what the faces can take stops at the steepest one
that works and the dialog says so (Luca, 2026-10-21; Fusion refuses it: value_limits.py); a
draft that cannot be made otherwise (or an angle from a formula) is explained in the dialog
and OK waits.

Built on FreeCAD's PartDesign::Draft (Fixed Plane, One Side) or SciForge's DraftFeature
(drafting.py). Double-click the step in the timeline to edit it.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import (
    bodies,
    commands,
    drafting,
    hole_common,
    log,
    modify_bodies,
    pickpanel,
    preview,
    ui_icon_path,
    value_limits,
    warn,
)
from .compat import QtCore, QtWidgets
from .taskui import DistanceField, ValueBoxes

PLANE_HELP = (
    "Pull Direction: click a flat face or an origin plane. The faces turn about it; the "
    "arrow shows which way the part is pulled out (click it to flip)."
)
PULL_HELP = (
    "Pull Direction: click a flat face or an origin plane; the arrow shows which way the "
    "part is pulled out (click it to flip)."
)
PARTING_HELP = (
    "Parting Tool: click an origin plane, a flat face, edges of the part or sketch curves "
    "(a whole sketch in the browser). The faces turn about where they meet it."
)
FACES_HELP = "Click the faces to draft (click one again to drop it), also of other bodies."
NO_MOVE = (
    "Not available yet: moving the parting line needs a step face where the two sides meet, "
    "which OpenCASCADE's draft does not make. Use Fix Parting Line."
)


class ViewProviderDraft:
    """View provider of SciForge's own draft (Two Side, Symmetric, Parting Line)."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        return ui_icon_path("draft")

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return None
        edit_draft(vobj.Object)
        return True

    def unsetEdit(self, vobj, mode=0):
        return None

    def doubleClicked(self, vobj):
        edit_draft(vobj.Object)
        return True

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


class PullArrow(pickpanel.Arrow):
    """The blue arrow showing the pull direction, like Fusion's: clicking it flips the
    pull direction (as the flip button does). Grabbed by where it is on the screen
    (handles3d), so it takes the click also where it is drawn over the part."""

    def __init__(self, origin, direction, length, on_click):
        self.on_click = on_click
        super().__init__(origin, direction, 0.0, length, on_release=self._let_go)

    def _let_go(self, value):
        try:
            moved = self.value()
            self.set_value(0.0)  # it shows a direction: it never stays dragged away
            # a click (or a drag backwards) flips; a drag along it does nothing
            if abs(moved) < 0.25 * self.size or moved < 0:
                QtCore.QTimer.singleShot(0, self.on_click)
        except Exception as exc:
            warn("Draft pull arrow: %s" % exc)

    def tip(self):
        """A point on the arrow head (tests, hints)."""
        return self.tip_point() - self.direction * (0.15 * self.size)


TYPE_ITEMS = [
    ("Fixed Plane", "fixed", True, "The faces turn about the plane you pick"),
    ("Parting Line", "parting", True, "The faces turn about a parting line or plane"),
]
SIDE_ITEMS = [
    ("One Side", "one", True, "Every picked face turns the same way"),
    ("Two Side", "two", True, "The faces are split at the plane or line; each side has its angle"),
    ("Symmetric", "symmetric", True, "Both sides tilt away from the plane or line by one angle"),
]
MODE_ITEMS = [
    ("Fix Parting Line", "fix", True, "The parting line stays where it is"),
    ("Move Parting Line", "move", False, NO_MOVE),
]


class DraftPanel(pickpanel.PickPanel, value_limits.LimitedValues):
    title = "Draft"
    icon = "draft"
    last = None  # the most recent panel (tests and diagnostics)

    def __init__(self, doc, feature=None, picks=None, body=None):
        super().__init__(doc, "Draft" if feature is None else "Edit Draft")
        DraftPanel.last = self
        self.target = feature
        self.editing = feature is not None
        self.plane_ref = None  # (object, element name or "")
        self.parting = []  # the parting tool: [(object, element name or "")]
        self.picked = []  # faces the user clicked, on self.base
        self.active = "plane"
        self.options = drafting.default_options()
        self.formula = ""
        self.formula2 = ""
        self.formula_error = ""
        self.handle = None
        self.arrow = None
        # Fusion shows the draft angle beside the angle disc; typed there it is taken like
        # the Angle field (a formula too).
        self.value_boxes = ValueBoxes(self, default="angle")
        self.planes = None  # the origin squares while a plane box takes the clicks
        self._chains = {}
        self.limit_init()  # an angle past what the faces take stops at the steepest that works
        if feature is not None:
            self.body = drafting.owner_body(feature)
            base, plane_ref, names, options, formula = drafting.read(feature)
            self.base = base
            self.plane_ref = plane_ref
            self.picked = list(names)
            self.options.update(options)
            self.parting = list(options.get("parting") or [])
            self.formula = formula or ""
            self.formula2 = options.get("formula2", "") or ""
            self.active = "faces" if plane_ref is not None else "plane"
            for follower in modify_bodies.followers_of(feature):  # the other bodies
                member = self.add_member(bodies.body_of(follower), follower.BaseFeature)
                link = follower.Faces
                member.picked = [s.lstrip("?") for s in (link[1] if link else []) if s]
                member.target = follower
        else:
            from . import shell_ui

            self.body, self.base = shell_ui.start_body(body)
        self._build()
        self.finish_layout()
        self.limit_label = value_limits.note_label()  # "Largest that fits here: ..."
        self.layout.addRow(self.limit_label)
        self._rows()
        try:
            self._start(picks or [])
        except Exception as exc:  # never leave a half-open dialog without a reason
            self.say("⚠ %s" % exc)
            warn("Draft could not start picking: %s" % exc)

    # -- layout -------------------------------------------------------------------------
    def _build(self):
        self.type = pickpanel.combo(TYPE_ITEMS, self.options.get("draft_type", "fixed"))
        self.type.currentIndexChanged.connect(self._type_changed)
        self.layout.addRow("Type", self.type)
        row = QtWidgets.QWidget()
        line = QtWidgets.QHBoxLayout(row)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(4)
        self.plane_box = hole_common.SelectionField(self, "plane", "Select")
        self.flip = QtWidgets.QToolButton()
        self.flip.setText("⇅")
        self.flip.setCheckable(True)
        self.flip.setChecked(bool(self.options.get("flip")))
        self.flip.setToolTip("Flip the pull direction")
        self.flip.toggled.connect(self._flipped)
        line.addWidget(self.plane_box.widget, 1)
        line.addWidget(self.flip)
        self.layout.addRow("Pull Direction", row)
        self.parting_box = hole_common.SelectionField(self, "parting", "Select")
        self.parting_label = QtWidgets.QLabel("Parting Tool")
        self.layout.addRow(self.parting_label, self.parting_box.widget)
        self.faces_box = hole_common.SelectionField(self, "faces", "Select")
        self.layout.addRow("Faces", self.faces_box.widget)
        self.help = QtWidgets.QLabel(PLANE_HELP)
        self.help.setWordWrap(True)
        self.help.setStyleSheet("color: #9aa4b1;")
        self.layout.addRow(self.help)
        self.tangent = QtWidgets.QCheckBox()
        self.tangent.setChecked(bool(self.options.get("tangent", True)))
        self.tangent.setToolTip("Also draft the faces that continue a picked face smoothly")
        self.tangent.toggled.connect(self._tangent_toggled)
        self.layout.addRow("Tangent Chain", self.tangent)
        self.mode = pickpanel.combo(MODE_ITEMS, "fix")
        self.mode_label = QtWidgets.QLabel("Parting Line Type")
        self.layout.addRow(self.mode_label, self.mode)
        self.sides = pickpanel.combo(SIDE_ITEMS, self.options.get("sides", "one"))
        self.sides.currentIndexChanged.connect(self._sides_changed)
        self.layout.addRow("Draft Sides", self.sides)
        self.angle = DistanceField(self.options["angle"], unit="deg", on_change=self._typed)
        self.angle.widget.setProperty("minimum", -89.9)
        self.angle.widget.setProperty("maximum", 89.9)
        self.angle_label = QtWidgets.QLabel("Angle")
        self.layout.addRow(self.angle_label, self.angle.widget)
        self.angle2 = DistanceField(
            self.options.get("angle2", self.options["angle"]), unit="deg", on_change=self._typed2
        )
        self.angle2.widget.setProperty("minimum", -89.9)
        self.angle2.widget.setProperty("maximum", 89.9)
        self.angle2_label = QtWidgets.QLabel("Angle 2")
        self.layout.addRow(self.angle2_label, self.angle2.widget)
        self.formula_label = QtWidgets.QLabel("")
        self.formula_label.setWordWrap(True)
        self.formula_label.setStyleSheet("color: #b8c7d9;")
        self.layout.addRow(self.formula_label)
        self._formula_inputs = [
            preview.FormulaInput(self, "angle", self.angle),
            preview.FormulaInput(self, "angle2", self.angle2),
        ]
        self._show_formula()

    def _rows(self):
        parting = self.type.currentData() == "parting"
        two = self.sides.currentData() == "two"
        for widget in (self.parting_label, self.parting_box.widget, self.mode_label, self.mode):
            widget.setVisible(parting)
        for widget in (self.angle2_label, self.angle2.widget):
            widget.setVisible(two)
        self.angle_label.setText("Angle 1" if two else "Angle")

    # -- starting -----------------------------------------------------------------------
    def _start(self, picks):
        if self.base is None:
            self.say("⚠ Make a solid first (Create Sketch, then Extrude).")
            return
        planes = [(o, s) for o, s in picks if not s and drafting.is_plane_object(o)]
        faces = [(o, s) for o, s in picks if s.startswith("Face")]
        for obj, short in planes[:1]:
            self._set_plane((obj, ""))
        for obj, short in faces:
            self._add_face(obj, short)
        self.remember_later(self.target if self.editing else self.base)
        self.start_picking()
        self._activate(self.active if self.plane_ref is not None else "plane", schedule=False)
        self._picks_updated(schedule=False)
        if self.target is not None:
            self.show_preview(True)
        if self.plane_ref is not None and self.picked:
            self.schedule()

    # -- boxes ----------------------------------------------------------------------------
    def activate(self, name):
        self._activate(name)

    def _activate(self, name, schedule=True):
        if name == "parting" and self.type.currentData() != "parting":
            name = "faces"
        self.active = name
        self.plane_box.set_active(name == "plane")
        self.parting_box.set_active(name == "parting")
        self.faces_box.set_active(name == "faces")
        parting = self.type.currentData() == "parting"
        texts = {
            "plane": PULL_HELP if parting else PLANE_HELP,
            "parting": PARTING_HELP,
            "faces": FACES_HELP,
        }
        self.help.setText(texts.get(name, FACES_HELP))
        if name in ("plane", "parting"):
            self._show_planes()
        else:
            self._hide_planes()

    def _next_box(self):
        if self.plane_ref is None:
            return "plane"
        if self.type.currentData() == "parting" and not self.parting:
            return "parting"
        return "faces"

    def clear_field(self, name):
        if name == "plane":
            if self.plane_ref is not None:
                self.plane_ref = None
                self._activate("plane")
        elif name == "parting":
            self.parting = []
            self._activate("parting")
        else:
            self.picked = []
            for member in list(self.members):
                self.drop_member(member.body)
        self._sync()
        self._picks_updated()

    def _show_planes(self):
        if self.planes is not None or self.body is None or self._closed:
            return
        try:
            from . import sketch_ui

            self.planes = sketch_ui.PlanePicker(
                Gui.ActiveDocument.ActiveView,
                self.body,
                lambda plane: QtCore.QTimer.singleShot(0, lambda: self._square_clicked(plane)),
            )
        except Exception as exc:
            self.planes = None
            warn("Draft: origin planes unavailable: %s" % exc)

    def _hide_planes(self):
        if self.planes is not None:
            self.planes.remove()
            self.planes = None

    def _square_clicked(self, plane):
        try:
            if self._closed:
                return
            if self.active == "plane":
                self._set_plane((plane, ""))
            elif self.active == "parting":
                self._set_parting_plane((plane, ""))
            else:
                return
            self._sync()
            self._picks_updated()
        except Exception as exc:
            warn("Draft plane: %s" % exc)

    # -- the picks (PickPanel calls these) ---------------------------------------------------
    def chain(self, name):
        if not self.tangent.isChecked() or self.base is None:
            return [name]
        if name not in self._chains:
            try:
                self._chains[name] = drafting.tangent_faces(self.base.Shape, [name])
            except Exception:
                self._chains[name] = [name]
        return self._chains[name]

    def names(self):
        """The faces drafted: the picks with their tangent chains (never the plane face)."""
        found = []
        plane_face = self.plane_ref[1] if self.plane_ref is not None else None
        for pick in self.picked:
            for name in self.chain(pick):
                if name not in found and name != plane_face:
                    found.append(name)
        return found

    def member_names(self, member):
        found = []
        for pick in member.picked:
            if self.tangent.isChecked():
                if pick not in member.chains:
                    try:
                        member.chains[pick] = drafting.tangent_faces(member.base.Shape, [pick])
                    except Exception:
                        member.chains[pick] = [pick]
                chain = member.chains[pick]
            else:
                chain = [pick]
            for name in chain:
                if name not in found:
                    found.append(name)
        return found

    def shown(self):
        entries = []
        if self.base is None:
            return entries
        names = list(self.names())
        if self.plane_ref is not None:
            obj, sub = self.plane_ref
            if sub and obj is self.base:
                names = [sub] + names
            elif not sub:
                entries.append((obj, []))
        for obj, sub in self.parting:
            if obj is self.base and sub:
                names.append(sub)
            elif not sub:
                entries.append((obj, []))
            else:
                entries.append((obj, [sub]))
        if names:
            entries.insert(0, (self.base, names))
        for member in self.members:
            member_names = self.member_names(member)
            if member_names:
                entries.append((member.base, member_names))
        return entries

    def _pull(self):
        if self.plane_ref is None:
            return None
        try:
            return drafting.pull_direction(self.plane_ref, self.flip.isChecked())
        except drafting.DraftError:
            return None

    def _in_body(self, obj):
        if obj is None or self.body is None:
            return False
        if obj.TypeId == "App::Plane":
            return any(o is obj for o in self.body.Origin.OriginFeatures)
        return drafting.owner_body(obj) is self.body

    def _flat(self, obj, short):
        try:
            return obj.Shape.getElement(short).Surface.__class__.__name__ == "Plane"
        except Exception:
            return False

    def _other_body(self, obj):
        """(body, base) when `obj` is the solid of another body and the dialog may still
        move there (nothing picked yet, not editing): Fusion drafts any body's faces."""
        if self.editing or self.plane_ref is not None or self.picked or self.members:
            return None
        body = drafting.owner_body(obj)
        if body is None or body is self.body:
            return None
        base = drafting.solid_base(body)
        if base is None or obj is not base:
            return None
        return body, base

    def _joinable(self, obj):
        """(body, base) of another body whose faces join this Draft step (the pull direction
        and some faces are picked already)."""
        if self.active != "faces" or self.plane_ref is None:
            return None
        body = drafting.owner_body(obj)
        if body is None or body is self.body:
            return None
        member = self.member(body)
        if member is not None:
            return (body, member.base) if obj is member.base else None
        base = modify_bodies.base_for(self.target, body)
        if base is None or obj is not base or base.Shape.isNull() or not base.Shape.Solids:
            return None
        return body, base

    def _follow(self, body, base):
        self._hide_planes()
        self.switch_body(body, base)
        self._chains = {}
        pickpanel.activate(body)
        if self.active in ("plane", "parting"):
            self._show_planes()

    def allow(self, obj, short):
        if self.base is None or obj is None:
            return False
        if self.active == "parting":
            return self._allow_parting(obj, short)
        if not short:
            return drafting.is_plane_object(obj) and self._in_body(obj)
        if not short.startswith("Face"):
            return False
        if self.plane_ref is not None and obj is self.plane_ref[0] and short == self.plane_ref[1]:
            return True  # the plane face stays shown (and a click on it drops it)
        member = self.member_of_object(obj)
        if member is not None:
            pull = self._member_pull(member)
            return pull is None or not drafting.why_not(member.base.Shape, short, pull)
        if obj.Name != self.base.Name:
            if self._joinable(obj) is not None:
                return True
            if self._other_body(obj) is None:
                return False
            return self.active != "plane" or self._flat(obj, short)
        if self.active == "plane":
            return self._flat(obj, short)
        pull = self._pull()
        if pull is None:
            return True
        return not drafting.why_not(self.base.Shape, short, pull, self.plane_ref)

    def _allow_parting(self, obj, short):
        if not short:
            if drafting.is_plane_object(obj):
                return self._in_body(obj)
            return obj.TypeId == "Sketcher::SketchObject"
        if obj.TypeId == "Sketcher::SketchObject":
            return short.startswith("Edge")
        if obj is not self.base:
            return False
        if short.startswith("Edge"):
            return True
        return short.startswith("Face") and self._flat(obj, short)

    def picks_changed(self, added, dropped):
        changed = False
        for obj, short, _point in dropped:
            if (
                self.plane_ref is not None
                and obj is self.plane_ref[0]
                and short == (self.plane_ref[1] or "")
            ):
                if short:  # a whole plane object stays (it is only shown selected)
                    self.plane_ref = None
                    self._activate("plane", schedule=False)
                    changed = True
            elif (obj, short) in self.parting or any(
                o is obj and s == short for o, s in self.parting
            ):
                if short:
                    self.parting = [
                        (o, s) for o, s in self.parting if not (o is obj and s == short)
                    ]
                    changed = True
            elif obj is self.base and short.startswith("Face"):
                changed = self._drop(short) or changed
            elif short.startswith("Face") and self.member_of_object(obj) is not None:
                changed = self._drop_member_face(self.member_of_object(obj), short) or changed
        for obj, short, _point in added:
            if self.active == "parting":
                changed = self._toggle_parting((obj, short)) or changed
                continue
            if short.startswith("Face") and obj is not self.base:
                follow = self._other_body(obj)
                if follow is not None:
                    self._follow(*follow)
            if not short:
                if drafting.is_plane_object(obj) and self._in_body(obj):
                    changed = self._set_plane((obj, "")) or changed
            elif short.startswith("Face") and obj is self.base:
                if self.active == "plane":
                    if self._flat(obj, short):
                        changed = self._set_plane((obj, short)) or changed
                else:
                    changed = self._add_face(obj, short) or changed
            elif short.startswith("Face") and self.active == "faces":
                changed = self._add_member_face(obj, short) or changed
        if changed:
            self._picks_updated(schedule=False)
        return changed

    def _set_plane(self, ref):
        obj, sub = ref
        if obj is not self.base and sub:
            return False
        if self.plane_ref is not None and self.plane_ref[0] is obj and self.plane_ref[1] == sub:
            return False
        self.plane_ref = ref
        self.picked = [p for p in self.picked if p != sub]
        if self.active == "plane":
            self._activate(self._next_box(), schedule=False)
        return True

    def _set_parting_plane(self, ref):
        self.parting = [ref]
        self._activate("faces", schedule=False)
        return True

    def _toggle_parting(self, ref):
        obj, sub = ref
        if not self._allow_parting(obj, sub):
            return False
        whole = not sub or sub.startswith("Face")
        for o, s in self.parting:
            if o is obj and s == sub:
                self.parting = [(a, b) for a, b in self.parting if not (a is obj and b == sub)]
                return True
        if whole or any(not s or s.startswith("Face") for _o, s in self.parting):
            self.parting = [ref]  # a plane, a face or a whole sketch is the whole tool
        else:
            self.parting.append(ref)
        if whole:
            self._activate("faces", schedule=False)
        return True

    def _add_face(self, obj, short):
        name = pickpanel.match_face(self.base, obj, short) if obj is not self.base else short
        if not name:
            return False
        pull = self._pull()
        if pull is not None:
            reason = drafting.why_not(self.base.Shape, name, pull, self.plane_ref)
            if reason:
                self.help.setText(reason)
                return False
        if name in self.picked or name in self.names():
            return False
        self.picked.append(name)
        return True

    def _member_pull(self, member):
        pull = self._pull()
        if pull is None:
            return None
        return modify_bodies.vector_between(pull, self.plane_ref[0], member.base)

    def _add_member_face(self, obj, short):
        join = self._joinable(obj)
        if join is None:
            return False
        member = self.add_member(*join)
        pull = self._member_pull(member)
        if pull is not None:
            reason = drafting.why_not(member.base.Shape, short, pull)
            if reason:
                self.help.setText(reason)
                return False
        if short in member.picked or short in self.member_names(member):
            return False
        member.picked.append(short)
        return True

    def _drop_member_face(self, member, name):
        before = len(member.picked)
        member.picked = [
            p
            for p in member.picked
            if name not in (member.chains.get(p, [p]) if self.tangent.isChecked() else [p])
        ]
        if not member.picked:
            self.drop_member(member.body)
        return len(member.picked) != before

    def _drop(self, name):
        before = len(self.picked)
        self.picked = [p for p in self.picked if name not in self.chain(p)]
        return len(self.picked) != before

    def _picks_updated(self, schedule=True):
        self.limits.note = ""  # a limit found for the old picks no longer applies
        if self.plane_ref is not None:
            self.plane_box.set_text(drafting.plane_label(self.plane_ref))
        else:
            self.plane_box.set_text("")
        self.parting_box.set_text(drafting.parting_label(self.parting))
        count = len(self.names()) + sum(len(self.member_names(m)) for m in self.members)
        text = "%d face%s" % (count, "" if count == 1 else "s") if count else ""
        if self.members:
            text += " (%d bodies)" % (len(self.members) + 1)
        self.faces_box.set_text(text)
        self._update_handles()
        if schedule:
            self.schedule()

    def _tangent_toggled(self, *_):
        self.options["tangent"] = self.tangent.isChecked()
        self._chains = {}
        for member in self.members:
            member.chains = {}
        self._sync()
        self._picks_updated()

    def _flipped(self, *_):
        self.options["flip"] = self.flip.isChecked()
        self._update_handles()
        self.schedule()

    def _arrow_clicked(self):
        """Fusion: clicking the pull direction arrow flips it."""
        try:
            if not self._closed and self.plane_ref is not None:
                self.flip.toggle()  # -> _flipped()
        except Exception as exc:
            warn("Draft flip: %s" % exc)

    def _type_changed(self, *_):
        try:
            self.options["draft_type"] = self.type.currentData()
            self._rows()
            if self.options["draft_type"] == "parting" and not self.parting:
                if self.plane_ref is not None:
                    self._activate("parting", schedule=False)
            elif self.active == "parting":
                self._activate("faces", schedule=False)
            self._picks_updated()
        except Exception as exc:
            warn("Draft Type: %s" % exc)

    def _sides_changed(self, *_):
        try:
            self.options["sides"] = self.sides.currentData()
            self._rows()
            self._update_handles()
            self.schedule()
        except Exception as exc:
            warn("Draft Sides: %s" % exc)

    # -- values -------------------------------------------------------------------------------
    def _typed(self, value):
        value = self._limit_typed("angle", self.angle, value, self.formula)
        self.options["angle"] = value
        if self.handle is not None:
            try:
                self.handle.set_angle(value)
            except Exception:
                pass
        self.schedule()

    def _typed2(self, value):
        value = self._limit_typed("angle2", self.angle2, value, self.formula2)
        self.options["angle2"] = value
        self.schedule()

    def _limit_typed(self, what, field, value, formula):
        """A typed angle held at the steepest one known to work (not a formula's)."""
        held = self.limit_edit(what, value, "formula" if formula else "typed")
        if held != value:  # the box shows it now, or once it is left
            value_limits.show_held(self.limit_shower, what, field, value, held)
        return held

    def _turned(self, degrees, released=False):
        value = round(max(-89.9, min(89.9, degrees)), 1)
        held = self.limit_edit("angle", value, "dragged")
        if held != value:
            value = held
            if self.handle is not None:
                self.handle.set_angle(value)  # the handle stops at the steepest angle
        elif released and abs(value - degrees) > 0.05 and self.handle is not None:
            self.handle.set_angle(value)  # turned past what a draft can be: back to the limit
        changed = abs(float(self.options.get("angle", 0.0)) - value) > 1e-12
        self.options["angle"] = value
        self.angle.set_value(value)
        if self.formula:
            self.formula = ""  # a drag gives a plain number
            self._show_formula()
            changed = True
        if changed:
            self.schedule()
        elif self.limits.note and not self.error:
            self.show_status()  # held at the limit: nothing to rebuild

    # -- angles past what fits (value_limits.LimitedValues) ------------------------------------
    def limit_unit(self, what):
        return "deg"

    def limit_key(self, what):
        options = self._spec_options()
        options.pop(what, None)
        plane = (self.plane_ref[0], self.plane_ref[1]) if self.plane_ref else None
        return value_limits.make_key(
            "draft",
            self.base.Shape if self.base is not None else None,
            plane,
            self.names(),
            [(m.body.Name, self.member_names(m)) for m in self.members],
            options,
            what,
        )

    def limit_works(self, what):
        options = self._spec_options()
        plane_ref, base, names = self.plane_ref, self.base, list(self.names())
        members = [(m.base, list(self.member_names(m))) for m in self.members]

        def works(value):
            trial = dict(options)
            trial[what] = value
            drafting.check(base.Shape, plane_ref, names, trial)
            drafting.draft_shape(base.Shape, names, drafting.build_spec(plane_ref, trial, base))
            for member_base, member_names in members:
                if member_names:
                    spec = drafting.build_spec(plane_ref, trial, member_base)
                    drafting.draft_shape(member_base.Shape, member_names, spec)
            return True

        return works

    def limit_value(self, what):
        return float(self.options.get(what, 0.0))

    def limit_set(self, what, value):
        self.options[what] = value
        field = self.angle if what == "angle" else self.angle2
        value_limits.show_held(self.limit_shower, what, field, field.value(), value)
        if what == "angle" and self.handle is not None:
            try:
                self.handle.set_angle(value)
            except Exception:
                pass

    def limit_keep(self):
        return self.base.Shape if self.base is not None else None

    def _collect(self):
        self.options["flip"] = self.flip.isChecked()
        self.options["tangent"] = self.tangent.isChecked()
        self.options["draft_type"] = self.type.currentData()
        self.options["sides"] = self.sides.currentData()
        self.options["parting_mode"] = self.mode.currentData() or "fix"
        self.options["parting"] = list(self.parting)
        if not self.formula:
            self.options["angle"] = self.limit_held("angle", self.angle.value())
        if not self.formula2:
            self.options["angle2"] = self.limit_held("angle2", self.angle2.value())

    def formula_typed(self, key, text, value):
        self.formula_error = ""
        if key == "angle2":
            self.formula2 = text
            self._show_formula()
            self._typed2(value)
            return
        self.formula = text
        self._show_formula()
        self._typed(value)

    def formula_cleared(self, key):
        self.formula_error = ""
        if key == "angle2":
            if self.formula2:
                self.formula2 = ""
                self._show_formula()
            self._typed2(self.angle2.value())
            return
        if self.formula:
            self.formula = ""
            self._show_formula()
        self._typed(self.angle.value())

    def formula_failed(self, key, text):
        self.formula_error = text
        self.show_status()

    def _show_formula(self):
        rows = []
        if self.formula:
            rows.append("Angle = %s" % self.formula)
        if self.formula2:
            rows.append("Angle 2 = %s" % self.formula2)
        self.formula_label.setText("\n".join(rows))

    # -- handles ----------------------------------------------------------------------------
    def _remove_handles(self):
        for item in (self.handle, self.arrow):
            if item is not None:
                try:
                    item.remove()
                except Exception:
                    pass
        self.handle = self.arrow = None

    @property
    def arrows(self):
        return [self.handle] if self.handle is not None else []

    def live_handles(self):
        return [x for x in (self.handle, self.arrow) if x is not None]

    def _hinge_point(self, shape):
        """A point of the line the first face turns about (Parting Line: on the parting
        tool), in the body's coordinates; None for the fixed plane's own point."""
        if self.type.currentData() != "parting" or not self.parting:
            return None
        try:
            spec = drafting.build_spec(self.plane_ref, self._spec_options(), self.base)
            if spec["plane"] is not None:
                return spec["plane"][0]
            import Part

            face = shape.getElement(self.names()[0])
            pairs = spec["curves"].distToShape(Part.Vertex(face.CenterOfMass))[1]
            return pairs[0][0]
        except Exception:
            return None

    def _spec_options(self):
        options = dict(self.options)
        options["parting"] = list(self.parting)
        return options

    def _update_handles(self):
        self._remove_handles()
        if self.base is None or self.plane_ref is None or self._closed:
            return
        try:
            self._collect()
            placement = self.body.getGlobalPlacement() if self.body else App.Placement()
            shape = self.base.Shape
            diag = shape.BoundBox.DiagonalLength
            pull = drafting.pull_direction(self.plane_ref, self.options["flip"])
            point, _axis, _out = drafting.plane_frame(self.plane_ref)
            if not self.plane_ref[1]:
                center = shape.BoundBox.Center
                point = center - pull * (center - point).dot(pull)
            point = self._arrow_foot(shape, point, pull, placement)
            self.arrow = PullArrow(
                placement.multVec(point),
                placement.Rotation.multVec(pull),
                max(4.0, min(diag * 0.25, 40.0)),
                self._arrow_clicked,
            )
            if not self.names():
                return
            frame = drafting.handle_frame(
                shape, self.plane_ref, self.names(), self.options, self._hinge_point(shape)
            )
            if frame is None:
                return
            pivot, axis, zero = frame
            from .extrude_ui import AngleDragger

            radius = max(3.0, min(diag * 0.18, 30.0))
            self.handle = AngleDragger(
                placement.multVec(pivot),
                placement.Rotation.multVec(axis),
                placement.Rotation.multVec(zero),
                float(self.options.get("angle", 0.0)),
                radius,
                radius * 0.12,
                on_drag=self._turned,
                on_release=lambda d: self._turned(d, True),
            )
            hole_common.on_top(self.handle.root)
            field = self.angle
            self.value_boxes.attach(
                self.handle,
                "angle",
                lambda: field.widget.text(),
                lambda text: self._box_typed("angle", text),
            )
        except Exception as exc:
            warn("Draft handles unavailable: %s" % exc)

    def _box_typed(self, key, text):
        if self._closed:
            return
        for formula in self._formula_inputs:
            if formula.key == key:
                formula.take(text)
                return

    def _arrow_foot(self, shape, point, pull, placement):
        """Where the pull arrow stands: on the plane, just beside the part (at the corner
        of its outline seen furthest left). Over the part it covered the faces to click,
        and it takes the clicks itself (they flip it)."""
        box = shape.BoundBox
        corners = [
            App.Vector(x, y, z)
            for x in (box.XMin, box.XMax)
            for y in (box.YMin, box.YMax)
            for z in (box.ZMin, box.ZMax)
        ]
        on_plane = [c - pull * (c - point).dot(pull) for c in corners]
        middle = box.Center - pull * (box.Center - point).dot(pull)
        try:
            view = Gui.ActiveDocument.ActiveView
            corner = min(on_plane, key=lambda c: view.getPointOnViewport(placement.multVec(c))[0])
        except Exception:
            corner = on_plane[0]
        out = corner - middle
        if out.Length < 1e-9:
            return point
        out.normalize()
        return corner + out * max(1.0, box.DiagonalLength * 0.06)

    # -- preview --------------------------------------------------------------------------
    def _ready(self):
        """What is still missing before a preview can be made ('' when nothing)."""
        if self.plane_ref is None:
            return "Pick the pull direction first: a flat face or an origin plane."
        if self.type.currentData() == "parting" and not self.parting:
            return "Pick the parting tool: a plane, a flat face, edges or sketch curves."
        if not self.names():
            return "Pick the faces to draft."
        return ""

    def _preview(self):
        if self._closed or self.base is None:
            return
        self._collect()
        if self.formula_error:
            self.show_status()
            return
        names = self.names()
        if self._ready():
            self.error = None
            if self.target is not None and not self.editing:
                target, self.target = self.target, None
                self._looks.restore()
                self._ghost = False
                drafting.remove(target)
                for member in self.members:
                    member.target = None
                self.quiet_recompute()
                self.prepare_display()
                self.show_members()
            self.show_preview(False)
            self.show_status()
            return
        try:
            drafting.check(self.base.Shape, self.plane_ref, names, self.options)
        except drafting.DraftError as exc:
            self.error = str(exc)
            self.show_status()
            return
        self.error = None
        if self.target is None:
            self.target = drafting.make(
                self.body,
                self.base,
                self.plane_ref,
                names,
                self.options,
                formula=self.formula,
                formula2=self.formula2,
            )
        else:
            new = drafting.update(
                self.target,
                self.base,
                self.plane_ref,
                names,
                self.options,
                self.formula,
                self.formula2,
            )
            if new is not self.target:
                self._looks.restore()
                self._ghost = False
                self.target = new
        self._sync_members()
        self.quiet_recompute()
        self.follow_later()
        if _failed(self.target):
            self.error = drafting.friendly(_status(self.target))
        elif drafting.is_draft(self.target) and not drafting.is_own(self.target):
            left = drafting.undrafted(self.base.Shape, self.target.Shape, names)
            if left:
                self.error = (
                    "%s could not be tilted with this plane and angle. Drop %s or try "
                    "another angle." % (", ".join(left), "it" if len(left) == 1 else "them")
                )
        if not self.error:
            for member in self.members:
                if member.target is not None and _failed(member.target):
                    self.error = "%s: %s" % (member.body.Label, _status(member.target))
                    break
        if self.error and self.limit_refused(self.error):
            self._preview()  # held at the steepest angle that works: preview that
            return
        if self.error:
            self.error = self.limit_hint(self.error)
        else:
            self.limit_good()
        self.show_preview(True)
        self.show_status()

    def _sync_members(self):
        try:
            followers = modify_bodies.sync(
                self.target,
                [(m.body, self.member_names(m)) for m in self.members],
                modify_bodies.DraftFollower,
                "Draft",
            )
        except modify_bodies.FollowerError as exc:
            self.error = str(exc)
            return
        for member, follower in zip(self.members, followers):
            member.target = follower

    def show_status(self):
        if self.formula_error:
            self.say("⚠ " + self.formula_error)
            return
        if self.base is None:
            self.say("⚠ Make a solid first (Create Sketch, then Extrude).")
            return
        if self.error:
            self.say("⚠ " + self.error)
            return
        if self.target is None or self._ready():
            self.say("")
            return
        broken = self.later_broken()
        if broken:
            self.say("⚠ Later steps no longer work: %s" % ", ".join(broken))
            return
        self.say("")

    def say(self, text):
        """The dialog's message. The note of a angle held at its limit shows under it while
        there is no error."""
        self.message.setText(text)
        limits = getattr(self, "limits", None)
        note = "" if text or limits is None else limits.note
        value_limits.show_note(getattr(self, "limit_label", None), note)

    # -- OK / Cancel ------------------------------------------------------------------------
    def accept(self):
        try:
            self._timer.stop()
            if self.base is None:
                self.say("⚠ Make a solid first (Create Sketch, then Extrude).")
                return False
            missing = self._ready()
            if missing:
                self.say("⚠ " + missing)
                return False
            self._preview()
            obj = self.target
            if self.formula_error or self.error or obj is None:
                self.show_status()
                return False
            state = list(obj.State)
            if "Invalid" in state or "Error" in state or not obj.Shape.isValid():
                self.show_status()
                return False
            if any(m.target is None or _failed(m.target) for m in self.members):
                self.show_status()
                return False
            return self.finish_ok()
        except Exception as exc:
            self.say("⚠ %s" % exc)
            return False

    def cleanup(self):
        self._remove_handles()
        self._hide_planes()
        self.value_boxes.discard()
        super().cleanup()


def _failed(obj):
    try:
        state = list(obj.State)
    except Exception:
        return False
    return "Invalid" in state or "Error" in state


def _status(obj):
    """FreeCAD's error text of a failed step ('' when it gives none: Draft often does)."""
    try:
        return obj.getStatusString() or ""
    except Exception:
        return ""


# -- command -----------------------------------------------------------------------------
class DraftCommand:
    def GetResources(self):
        return {
            "MenuText": "Draft",
            "ToolTip": "Tilt faces so a mould can be pulled off: pick the pull direction (and a "
            "parting line), then the faces, drag or type the angle, with a live preview",
            "Pixmap": ui_icon_path("draft"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            start()
        except Exception as exc:
            warn("Draft could not start: %s" % exc)


def start():
    """Run Draft: a plane / faces selected beforehand are taken at once; with nothing
    selected the dialog opens and waits for the pull direction."""
    selection = pickpanel.capture_selection()
    picked_body = pickpanel.selected_body()
    if not commands.finish_open_dialog():
        return None
    doc = App.ActiveDocument
    if doc is None:
        return None
    from . import shell_ui

    body, base = shell_ui.start_body(picked_body)
    if base is None:
        commands.tell("Draft needs a solid: make one first (Create Sketch, then Extrude).")
        return None
    pickpanel.activate(body)
    pickpanel.reselect(selection)
    picks = [(obj, short) for obj, short, _p in pickpanel.selection_entries(doc)]
    panel = None
    try:
        panel = DraftPanel(doc, picks=picks, body=body)
        Gui.Control.showDialog(panel)
    except Exception:
        if panel is not None and not panel._closed:
            try:
                panel.reject()
            except Exception:
                pass
        raise
    log("draft started with %d pick(s)" % len(picks))
    return panel


def edit_draft(obj):
    """Timeline double-click: the Draft dialog on the existing draft."""
    try:
        if Gui.Control.activeDialog() and not commands.finish_open_dialog():
            return
        Gui.Control.showDialog(DraftPanel(obj.Document, feature=obj))
    except Exception as exc:
        warn("could not edit %s: %s" % (obj.Label, exc))


COMMANDS = {"SciForge_Draft": DraftCommand}
EDITORS = {drafting.NATIVE: edit_draft, "SciForge::" + drafting.KIND: edit_draft}
