# SPDX-License-Identifier: LGPL-2.1-or-later
"""Align (Modify > Align) with Fusion's dialog: Objects (Bodies / Components), From, To,
Flip, Angle. Fusion gives Align no key (A is Appearance).

The From box takes the first click: a corner, an edge, a face of what moves (a solid without
history becomes a body built on it), or a construction plane / axis. Its body moves (with
Components: its component). Then the To box: the geometry it goes to (a face, an edge, a
corner of another body, one of the big origin squares, an axis). Two flat faces end up in
one plane facing each other; Flip turns the result over, Angle turns it 90 degrees about the
To geometry per click. Previewed live; OK / Enter keeps it (one undo step), Cancel / Esc
throws it away. Double-click the Align in the timeline to change it. Document side:
align.py, maths: align_core.py.
"""

import FreeCAD as App

from . import align, align_core, bodies, modify_common as mc, ui_icon_path, warn
from .bodies_panel import BodyPanel, edit as _edit, start as _start
from .compat import QtWidgets

OBJECTS = [("Bodies", "bodies"), ("Components", "components")]


def _unmove(frame, place):
    """A frame picked on the moved preview, as it was before the move."""
    if frame is None:
        return None
    back = place.inverse()
    point = back.multVec(App.Vector(*frame["point"]))
    axis = frame.get("axis")
    if axis is not None:
        axis = back.Rotation.multVec(App.Vector(*axis))
    return align_core.frame(point, axis, frame.get("oriented"))


class AlignPanel(BodyPanel):
    title = "Align"
    icon = "align"
    needs_pick = (align.NeedsPick,)

    def __init__(self, doc, feature=None):
        self.options = align.with_defaults({})
        self.labels = ("", "")
        self.steps = []
        self.moving = None
        if feature is not None:
            try:
                read = align.read(feature)
                self.labels = read.pop("labels", ("", ""))
                self.options.update(read)
                self.steps = align.steps_of(feature.AlignId, doc) or [feature]
                self.moving = align.moved_thing(feature)
            except Exception as exc:
                warn("could not read %s: %s" % (feature.Label, exc))
        self._adopted = []
        self.squares = None
        super().__init__(doc, "Align" if feature is None else "Edit Align", feature is not None)
        self.target = feature
        self.squares = mc.PlaneSquares(self, self._take_plane)
        self._show_picks()
        if feature is not None:
            self.activate("to")
        else:
            self.activate("from")
            self.start_from_selection()
            self.dirty = True
            self._timer.stop()
            self._recompute()

    # -- form ----------------------------------------------------------------------------------
    def build_form(self):
        self.objects, _ = self.combo("Objects", OBJECTS, self.options["objects"], self._typed)
        self.selection_box("from", "From")
        self.selection_box("to", "To")
        row = QtWidgets.QWidget()
        buttons = QtWidgets.QHBoxLayout(row)
        buttons.setContentsMargins(0, 0, 0, 0)
        self.flip_button = QtWidgets.QPushButton("Flip")
        self.flip_button.setObjectName("SciForgeAlignFlip")
        self.flip_button.setToolTip("Turn the result over (180 degrees)")
        self.flip_button.clicked.connect(lambda *_: self._guarded(self._flip))
        self.angle_button = QtWidgets.QPushButton("Angle")
        self.angle_button.setObjectName("SciForgeAlignAngle")
        self.angle_button.setToolTip("Turn the result 90 degrees about the To geometry")
        self.angle_button.clicked.connect(lambda *_: self._guarded(self._turn))
        buttons.addWidget(self.flip_button)
        buttons.addWidget(self.angle_button)
        self.layout.addRow(row)
        self.state = QtWidgets.QLabel("")
        self.state.setStyleSheet("color: #b8c7d9;")
        self.layout.addRow(self.state)

    def _typed(self):
        objects = self.objects.currentData()
        if objects != self.options["objects"]:
            self.options["objects"] = objects
            self.moving = (
                align.moving(self.options["from_pick"], objects)
                if self.options["from_pick"]
                else None
            )
        self.changed()

    def _flip(self):
        self.options["flip"] = not self.options["flip"]
        self._show_picks()
        self.changed()

    def _turn(self):
        self.options["turns"] = (int(self.options["turns"]) + 1) % 4
        self._show_picks()
        self.changed()

    def _show_picks(self):
        from_text = align.describe_pick(self.options["from_pick"]) or self.labels[0]
        to_text = align.describe_pick(self.options["to_pick"]) or self.labels[1]
        if not self.options["from_pick"] and not self.options.get("from_frame"):
            from_text = ""
        if not self.options["to_pick"] and not self.options.get("to_frame"):
            to_text = ""
        self.fields["from"].set_text(from_text)
        self.fields["to"].set_text(to_text)
        self.state.setText(align_core.describe(self.options["flip"], self.options["turns"]))

    def cleared(self, name):
        self.options[name + "_pick"] = None
        self.options[name + "_frame"] = None
        self.labels = ("", self.labels[1]) if name == "from" else (self.labels[0], "")
        if name == "from":
            self.moving = None
        self._show_picks()

    def activated(self, name):
        if self.squares is None:
            return
        if name == "to" and not self.options["to_pick"] and not self.options.get("to_frame"):
            self.squares.show(
                self.moving if bodies.is_body(self.moving) else bodies.find_body(self.doc)
            )
        else:
            self.squares.hide()

    # -- clicks --------------------------------------------------------------------------------
    def _movement(self):
        for step in self.steps:
            if bodies.alive(step):
                return step.Movement
        return None

    def picked(self, obj, short, point):
        if self.squares is not None and self.squares.took_click():
            return
        if self.active == "from":
            self._pick_from(obj, short, point)
        else:
            self._pick_to(obj, short, point)

    def _pick_from(self, obj, short, point):
        if short and bodies.body_of(obj) is None:
            adopted = mc.body_of_pick(self, obj)  # a solid without history becomes a body
            if adopted is not None:
                obj = adopted.Tip
        frame = align.frame_of(obj, short, point)
        if frame is None:
            self.message.setText("Pick a corner, an edge, a face or a plane of what moves.")
            return
        thing = align.moving((obj, short), self.options["objects"])
        if thing is None:
            self.message.setText(
                "That is not on a body%s."
                % (" in a component" if self.options["objects"] == "components" else "")
            )
            return
        movement = self._movement()
        if movement is not None and thing is self.moving:
            frame = _unmove(frame, movement)  # picked on the moved preview
        if self.moving is not None and thing is not self.moving and self.steps:
            self._drop_steps()
        self.moving = thing
        self.options["from_pick"] = (obj, short, point)
        self.options["from_frame"] = frame
        self.message.setText("")
        self._show_picks()
        self.activate("to")
        self.changed()

    def _pick_to(self, obj, short, point):
        thing = align.moving((obj, short), self.options["objects"])
        if thing is not None and thing is self.moving:
            self.message.setText("That is on what moves. Pick the geometry it goes to.")
            return
        frame = align.frame_of(obj, short, point)
        if frame is None:
            self.message.setText("Pick a corner, an edge, a face, a plane or an axis.")
            return
        self.options["to_pick"] = (obj, short, point)
        self.options["to_frame"] = frame
        self.message.setText("")
        self._show_picks()
        if self.squares is not None:
            self.squares.hide()
        self.changed()

    def _take_plane(self, ref):
        if self._closed:
            return
        obj = ref[0]
        if self.active == "from":
            self._pick_from(obj, "", None)
        else:
            self._pick_to(obj, "", None)

    def _drop_steps(self):
        for step in self.steps:
            if bodies.alive(step):
                align.remove(step)
        self.steps = []

    # -- preview -------------------------------------------------------------------------------
    def apply(self):
        try:
            align.check(self.options)
        except align.AlignError:
            if not self.editing:
                self._drop_steps()
            raise
        self.steps = align.build(
            self.options,
            self.steps,
            getattr(self.target, "AlignId", None) if self.target is not None else None,
            target=self.moving,
        )

    def after_recompute(self):
        for step in self.steps:
            if bodies.alive(step) and not align.is_component_step(step):
                bodies.show_tip(bodies.body_of(step))

    def preview_steps(self):
        return [s for s in self.steps if bodies.alive(s) and not align.is_component_step(s)]

    def can_finish(self):
        if not [s for s in self.steps if bodies.alive(s)]:
            try:
                align.check(self.options)
            except align.AlignError as exc:
                return str(exc)
            return self.error or "Pick the From and the To geometry."
        return ""

    def remove_handles(self):
        if self.squares is not None:
            self.squares.close()

    def before_close(self, ok):
        self._ok = ok

    def restore_view(self):
        mc.restore_adopted(self, getattr(self, "_ok", False))


class AlignCommand:
    def GetResources(self):
        return {
            "MenuText": "Align",
            "ToolTip": "Move a body or component so that a face, edge or point of it goes onto "
            "another (Flip turns it over, Angle turns it 90 degrees)",
            "Pixmap": ui_icon_path("align"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            _start(AlignPanel)
        except Exception as exc:
            warn("Align could not start: %s" % exc)


def edit(feature):
    _edit(AlignPanel, feature)


COMMANDS = {"SciForge_Align": AlignCommand}
EDITORS = {"SciForge::Align": edit}


class _DeleteWatch:
    """The timeline's or the browser's Delete of a component's Align puts the component back
    where it was (the Align step itself only recorded the move). Not after an undo, a redo
    or while a file loads: those put the placement back themselves."""

    def slotDeletedObject(self, obj):
        try:
            if not align.is_component_step(obj):
                return
            doc = obj.Document
            if getattr(doc, "Transacting", False) or getattr(doc, "Restoring", False):
                return
            part = obj.Component
            if (
                part is not None
                and bodies.alive(part)
                and not part.Placement.isSame(obj.Before, 1e-12)
            ):
                part.Placement = obj.Before
        except Exception as exc:
            warn("Align: %s" % exc)


_WATCH = {"observer": None}


def install():
    if _WATCH["observer"] is None:
        _WATCH["observer"] = _DeleteWatch()
        App.addDocumentObserver(_WATCH["observer"])


try:
    install()
except Exception as _exc:  # never let an import fail the commands
    warn("align watch unavailable: %s" % _exc)
