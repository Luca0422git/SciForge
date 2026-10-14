# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's motion tools of ASSEMBLE: Motion Link, Contact Sets (Disable Contact, Enable
Contact Sets, Enable All Contact, New Contact Set), Motion Study, and the SELECT menu's
Component Drag tick. The document side is joints.py, the maths motion_core.py, the spec
docs/sciforge/parity/joints.md.

- Motion Link: pick two joints (their browser rows, timeline steps or jointed components);
  each gets its value (an angle for a turning joint, a distance for a sliding one): joint 1
  moving by its value moves joint 2 by its value (a pinion turning 360 degrees moves its
  rack one circumference); Reverse turns joint 2 the other way; Animate plays it. A Motion
  Link step in the timeline and in the browser's Joints folder.
- Contact sets: while contact sets are on, the components of a set stop where they touch
  when dragged or driven; Enable All Contact makes every component stop at every other.
- Motion Study: joints, key points (a value at a step from 0 to 100), Play (once, loop,
  ping-pong) with a speed; kept in the browser's Motion Studies folder.
"""

import time

import FreeCAD as App

from . import commands, hole_common, joints, joints_drag, joints_ui, log, motion_core
from . import ui_icon_path, warn
from .bodies_panel import edit as _edit, start as _start
from .compat import QtCore, QtWidgets
from .joints_ui import NeedsPick, _JointsPanel, attach_views
from .taskui import DistanceField

PLAY_MS = 40


def _joint_from(root, sub, point, doc):
    """A click meaning a joint: its browser row / timeline step, or a jointed component
    (its first joint with a motion). (joint or None, refusal text)."""
    if joints.is_joint(root):
        return root, ""
    pick = joints.resolve_selection(root, sub, point)
    part = pick.part if pick is not None else joints.part_of(root)
    if part is None:
        return None, ""
    for j in joints.joints(doc):
        if part in (joints.part1(j), joints.part2(j)) and joints.fusion_type(j) != "rigid":
            return j, ""
    return None, "%s has no joint with a motion." % part.Label


def _unit(motion):
    return "deg" if motion == "angle" else "mm"


def _motion_label(motion):
    return "Angle" if motion == "angle" else "Distance"


# -- Motion Link -----------------------------------------------------------------------------------
class MotionLinkPanel(_JointsPanel):
    """Fusion's Motion Link dialog."""

    title = "Motion Link"
    icon = "motion_link"
    needs_pick = (NeedsPick,)
    hover_boxes = ()
    last = None

    def __init__(self, doc, feature=None):
        self.link = feature
        self.picked = []  # the joints, in order
        self.motions = ["", ""]
        super().__init__(
            doc, "Motion Link" if feature is None else "Edit Motion Link", feature is not None
        )
        MotionLinkPanel.last = self
        self.target = feature
        if feature is not None:
            self._read(feature)
        self.activate("joints")
        if feature is None:
            self.start_from_selection()
        self.dirty = True
        self._timer.stop()
        self._recompute()

    def build_form(self):
        self.form_box(self.layout, "joints", "Joints", "Select")
        self.rows = []
        for index in (0, 1):
            caption = QtWidgets.QLabel("")
            font = caption.font()
            font.setBold(True)
            caption.setFont(font)
            self.layout.addRow(caption)
            motion, motion_caption = self.form_combo(
                self.layout,
                "Motion",
                [("Rotate", "angle"), ("Slide", "slide")],
                "angle",
                lambda i=index: self._motion_changed(i),
            )
            field, field_caption = self.form_field(
                self.layout, "Angle", 360.0, "deg", lambda v: self.changed()
            )
            field.widget.setObjectName("SciForgeMotionLink_value%d" % (index + 1))
            self.rows.append(
                {
                    "caption": caption,
                    "motion": motion,
                    "motion_caption": motion_caption,
                    "field": field,
                    "field_caption": field_caption,
                }
            )
        self.reverse = QtWidgets.QCheckBox("Reverse")
        self.reverse.setObjectName("SciForgeMotionLink_reverse")
        self.reverse.setToolTip("Joint 2 moves the other way")
        self.reverse.toggled.connect(lambda *_: self._guarded(self.changed))
        self.layout.addRow(QtWidgets.QLabel(""), self.reverse)
        self.animate = QtWidgets.QPushButton("Animate")
        self.animate.setObjectName("SciForgeMotionLink_animate")
        self.animate.setCheckable(True)
        self.animate.toggled.connect(lambda on: self._guarded(lambda: self._animate(on)))
        self.layout.addRow(QtWidgets.QLabel(""), self.animate)
        self._show_rows()

    def _show_rows(self):
        for index, row in enumerate(self.rows):
            joint = self.picked[index] if index < len(self.picked) else None
            shown = joint is not None
            row["caption"].setVisible(shown)
            for key in ("field", "field_caption"):
                widget = row[key].widget if key == "field" else row[key]
                widget.setVisible(shown)
            motions = joints.motions_of(joint) if joint is not None else []
            both = len(motions) > 1
            row["motion"].setVisible(both)
            row["motion_caption"].setVisible(both)
            if joint is None:
                continue
            row["caption"].setText("%s %d: %s" % ("Joint", index + 1, joint.Label))
            motion = self.motions[index] or joints.default_motion(joint)
            self.motions[index] = motion
            self._quiet = True
            try:
                hole_common.set_combo(row["motion"], motion)
            finally:
                self._quiet = False
            row["field_caption"].setText(_motion_label(motion))
        two = len(self.picked) == 2
        self.reverse.setVisible(two)  # Fusion shows Reverse once the second joint is picked
        self.animate.setVisible(two)

    def _set_unit(self, index, motion, value=None):
        """The value box of joint `index` in the unit of its motion (degrees or mm), with
        `value` (else Fusion-like defaults: one turn, 10 mm)."""
        row = self.rows[index]
        old = row["field"]
        unit = _unit(motion)
        if value is None:
            value = 360.0 if motion == "angle" else 10.0
        if getattr(old, "unit", None) == unit:
            old.set_value(value)
            return
        # a new box of the right unit in the same place (a DistanceField keeps its unit)
        position = self.layout.getWidgetPosition(old.widget)
        field = DistanceField(value, unit=unit, on_change=lambda v: self.changed())
        field.widget.setObjectName(old.widget.objectName())
        old.widget.hide()
        self.layout.setWidget(position[0], QtWidgets.QFormLayout.FieldRole, field.widget)
        old.widget.setParent(None)
        row["field"] = field

    def _motion_changed(self, index):
        row = self.rows[index]
        motion = row["motion"].currentData()
        if motion == self.motions[index]:
            return
        self.motions[index] = motion
        self._set_unit(index, motion)
        row["field_caption"].setText(_motion_label(motion))
        self.changed()

    def _read(self, link):
        data = joints.link_data(link)
        self._quiet = True
        try:
            self.picked = [j for j in (link.Joint1, link.Joint2) if j is not None]
            self.motions = [data["motion1"], data["motion2"]]
            for index, key in ((0, "value1"), (1, "value2")):
                motion = self.motions[index] or (
                    joints.default_motion(self.picked[index]) if index < len(self.picked) else ""
                )
                self._set_unit(index, motion or "angle", value=data[key])
            self.reverse.setChecked(bool(data["reverse"]))
            self.fields["joints"].set_text(", ".join(j.Label for j in self.picked))
        finally:
            self._quiet = False
        self._show_rows()

    def allow_object(self, obj):
        return joints.is_joint(obj) or joints.part_of(obj) is not None

    def allow_pick(self, pick):
        return True

    def picked_raw(self, root, sub, point):
        joint, why = _joint_from(root, sub, point, self.doc)
        if joint is None:
            if why:
                self.refuse(why)
            return
        if joints.fusion_type(joint) == "rigid":
            self.refuse("%s is rigid: it has no motion to link." % joint.Label)
            return
        if joint in self.picked:
            index = self.picked.index(joint)
            self.picked.remove(joint)  # a click on a picked joint drops it
            self.motions.pop(index)
            self.motions.append("")
        elif len(self.picked) >= 2:
            self.refuse("A motion link ties two joints; clear one first.")
            return
        else:
            self.picked.append(joint)
            index = len(self.picked) - 1
            self.motions[index] = joints.default_motion(joint)
            self._set_unit(index, self.motions[index], value=None)
        self.fields["joints"].set_text(", ".join(j.Label for j in self.picked))
        self.took()
        self._show_rows()
        self.changed()

    def cleared(self, name):
        self.stop_animation()
        self.picked = []
        self.motions = ["", ""]
        self.fields["joints"].set_text("")
        self._show_rows()
        if self.link is not None and not self.editing:
            self.link = None
            self.target = None
            self.restart()

    def _animate(self, on):
        if not on:
            self.stop_animation()
            return
        if self.link is None or not self.picked:
            self.animate.setChecked(False)
            return
        self.stop_animation()
        self.animator = joints_ui.Animator(self.picked[0], on_done=self._done, loop=True)
        if not self.animator.start():
            self.animator = None
            self.animate.setChecked(False)

    def _done(self):
        self.animator = None
        try:
            self.animate.setChecked(False)
        except Exception:
            pass

    def stop_animation(self):
        super().stop_animation()
        try:
            if self.animate.isChecked():
                self.animate.blockSignals(True)
                self.animate.setChecked(False)
                self.animate.blockSignals(False)
        except Exception:
            pass

    def apply(self):
        if len(self.picked) < 2:
            raise NeedsPick(
                "Click two joints (their rows in the browser or timeline, or a jointed "
                "component): when the first moves, the second follows."
            )
        values = [row["field"].value() for row in self.rows]
        if abs(values[0]) < 1e-12:
            raise joints.JointError("The first joint's value cannot be 0: type how far it moves.")
        if self.link is None:
            self.link = joints.create_motion_link(
                self.doc,
                self.picked[0],
                self.picked[1],
                values[0],
                values[1],
                self.reverse.isChecked(),
                self.motions[0],
                self.motions[1],
            )
            self.target = self.link
        else:
            joints.set_motion_link(
                self.link,
                self.picked[0],
                self.picked[1],
                values[0],
                values[1],
                self.reverse.isChecked(),
                self.motions[0],
                self.motions[1],
            )
        attach_views(self.doc)

    def after_recompute(self):
        if self.link is None:
            self.note.setText("")
            return
        data = joints.link_data(self.link)
        ratio = motion_core.link_ratio(data["value1"], data["value2"], data["reverse"])
        units = [_unit(data["motion1"]), _unit(data["motion2"])]
        self.note.setText(
            "%s moves %.4g %s for each %s %s moves."
            % (self.picked[1].Label, ratio, units[1], units[0], self.picked[0].Label)
        )

    def preview_steps(self):
        return [self.link] if self.link is not None else []

    def can_finish(self):
        return "" if self.link is not None else "Pick two joints."

    def before_close(self, ok):
        self.stop_animation()


# -- Contact Sets ----------------------------------------------------------------------------------
class ContactSetPanel(_JointsPanel):
    """Fusion's New Contact Set: two or more components that stop where they touch."""

    title = "New Contact Set"
    icon = "contact_set"
    needs_pick = (NeedsPick,)
    hover_boxes = ()
    last = None

    def __init__(self, doc, feature=None):
        self.group = feature
        self.members = []
        super().__init__(
            doc,
            "New Contact Set" if feature is None else "Edit Contact Set",
            feature is not None,
        )
        ContactSetPanel.last = self
        self.target = feature
        if feature is not None:
            self.members = [m for m in feature.Members if m is not None]
            self._show_members()
        self.activate("components")
        if feature is None:
            self.start_from_selection()
        self.dirty = True
        self._timer.stop()
        self._recompute()

    def build_form(self):
        self.form_box(self.layout, "components", "Components", "Select")

    def _show_members(self):
        self.fields["components"].set_text(", ".join(m.Label for m in self.members))

    def allow_object(self, obj):
        return joints.part_of(obj) is not None

    def allow_pick(self, pick):
        return True

    def picked_raw(self, root, sub, point):
        pick = joints.resolve_selection(root, sub, point)
        part = pick.part if pick is not None else joints.part_of(root)
        if part is None:
            return
        if part in self.members:
            self.members.remove(part)
        else:
            self.members.append(part)
        self._show_members()
        self.took()
        self.changed()

    def cleared(self, name):
        self.members = []
        self._show_members()
        self.changed()

    def apply(self):
        if len(self.members) < 2:
            if self.group is not None and not self.editing:
                self.group = None
                self.target = None
                self.restart()
            raise NeedsPick("Click two or more components (in the view or the browser).")
        if self.group is None:
            self.group = joints.create_contact_set(self.doc, self.members)
            self.target = self.group
        else:
            self.group.Members = self.members
        attach_views(self.doc)

    def after_recompute(self):
        mode = joints.contact_mode(self.doc)
        if mode == "off" and self.group is not None:
            self.note.setText(
                "Contact is off: turn on ASSEMBLE > Enable Contact Sets for the set to stop "
                "the motion."
            )
        else:
            self.note.setText("")

    def preview_steps(self):
        return [self.group] if self.group is not None else []

    def can_finish(self):
        return "" if self.group is not None else "Pick two or more components."


def contact_is(mode):
    doc = App.ActiveDocument
    return doc is not None and joints.contact_mode(doc) == mode


def contact_off():
    doc = App.ActiveDocument
    return doc is None or joints.contact_mode(doc) == "off"


def contact_sets_on():
    return contact_is("sets")


def contact_all_on():
    return contact_is("all")


def set_contact(mode):
    doc = App.ActiveDocument
    if doc is None:
        commands.tell("Open or start a design first.")
        return False
    if not commands.finish_open_dialog():
        return False
    labels = {"off": "Disable Contact", "sets": "Enable Contact Sets", "all": "Enable All Contact"}
    doc.openTransaction(labels[mode])
    try:
        joints.set_contact_mode(doc, mode)
    except Exception as exc:
        doc.abortTransaction()
        commands.tell(str(exc))
        return False
    doc.commitTransaction()
    log("contact: %s" % labels[mode])
    joints_ui._refresh_browser()
    return True


# -- Motion Study ----------------------------------------------------------------------------------
class MotionStudyPanel(_JointsPanel):
    """Fusion's Motion Study: the joints to move, a value for each at chosen steps (0 to
    100), the step slider to look, Play (once, loop or ping-pong) at a speed. The
    components go back where they were when the dialog closes."""

    title = "Motion Study"
    icon = "motion_study"
    needs_pick = (NeedsPick,)
    hover_boxes = ()
    last = None

    def __init__(self, doc, feature=None):
        self.study = feature
        self.data = joints.study_data(feature)
        self.playing = False
        self.play_started = 0.0
        super().__init__(
            doc, "Motion Study" if feature is None else "Edit Motion Study", feature is not None
        )
        MotionStudyPanel.last = self
        self.target = feature
        self.start_places = joints.placements(doc)
        self.timer = QtCore.QTimer()
        self.timer.setInterval(PLAY_MS)
        self.timer.timeout.connect(self._tick)
        self._fill()
        self.activate("joints")
        if feature is None:
            self.start_from_selection()
        self.dirty = True
        self._timer.stop()
        self._recompute()

    def build_form(self):
        self.form_box(self.layout, "joints", "Joints", "Select")
        self.joint_box, _ = self.form_combo(self.layout, "Joint", [], None, self._joint_changed)
        self.step = QtWidgets.QSpinBox()
        self.step.setObjectName("SciForgeStudy_step")
        self.step.setRange(0, motion_core.STUDY_STEPS)
        self.layout.addRow(QtWidgets.QLabel("Step"), self.step)
        self.value_field, self.value_caption = self.form_field(
            self.layout, "Value", 0.0, "deg", lambda v: None
        )
        buttons = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(buttons)
        row.setContentsMargins(0, 0, 0, 0)
        self.set_point = QtWidgets.QPushButton("Set Point")
        self.set_point.setObjectName("SciForgeStudy_set")
        self.set_point.setToolTip("The joint takes this value at this step")
        self.set_point.clicked.connect(lambda *_: self._guarded(self._set_point))
        self.delete_point = QtWidgets.QPushButton("Delete Point")
        self.delete_point.setObjectName("SciForgeStudy_delete")
        self.delete_point.clicked.connect(lambda *_: self._guarded(self._delete_point))
        row.addWidget(self.set_point)
        row.addWidget(self.delete_point)
        self.layout.addRow(QtWidgets.QLabel(""), buttons)
        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setObjectName("SciForgeStudy_points")
        self.table.setHorizontalHeaderLabels(["Step", "Joint", "Value"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setMinimumHeight(120)
        self.layout.addRow(self.table)
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setObjectName("SciForgeStudy_slider")
        self.slider.setRange(0, motion_core.STUDY_STEPS)
        self.slider.valueChanged.connect(lambda v: self._guarded(lambda: self._scrub(v)))
        self.layout.addRow(QtWidgets.QLabel("Playhead"), self.slider)
        self.mode_box, _ = self.form_combo(
            self.layout,
            "Mode",
            [(motion_core.STUDY_MODE_LABELS[m], m) for m in motion_core.STUDY_MODES],
            "once",
            self._mode_changed,
        )
        self.speed = QtWidgets.QDoubleSpinBox()
        self.speed.setObjectName("SciForgeStudy_speed")
        self.speed.setRange(0.25, 4.0)
        self.speed.setSingleStep(0.25)
        self.speed.setValue(1.0)
        self.speed.valueChanged.connect(lambda v: self._guarded(self._speed_changed))
        self.layout.addRow(QtWidgets.QLabel("Speed"), self.speed)
        self.play = QtWidgets.QPushButton("Play")
        self.play.setObjectName("SciForgeStudy_play")
        self.play.setCheckable(True)
        self.play.toggled.connect(lambda on: self._guarded(lambda: self._play(on)))
        self.layout.addRow(QtWidgets.QLabel(""), self.play)

    # -- the form ---------------------------------------------------------------------------
    def _joints(self):
        out = []
        for name in self.data["joints"]:
            obj = self.doc.getObject(name)
            if obj is not None and joints.is_joint(obj):
                out.append(obj)
        return out

    def _fill(self):
        self._quiet = True
        try:
            picked = self._joints()
            self.fields["joints"].set_text(", ".join(j.Label for j in picked))
            current = self.joint_box.currentData()
            hole_common.fill_combo(self.joint_box, [(j.Label, j.Name) for j in picked], current)
            self.table.setRowCount(0)
            for joint in picked:
                for step, value in sorted(self.data["keys"].get(joint.Name, [])):
                    r = self.table.rowCount()
                    self.table.insertRow(r)
                    unit = "°" if joints.default_motion(joint) == "angle" else " mm"
                    for c, text in enumerate(("%g" % step, joint.Label, "%g%s" % (value, unit))):
                        item = QtWidgets.QTableWidgetItem(text)
                        item.setData(QtCore.Qt.UserRole, (joint.Name, step))
                        self.table.setItem(r, c, item)
            hole_common.set_combo(self.mode_box, self.data.get("mode", "once"))
            self.speed.setValue(float(self.data.get("speed", 1.0)))
        finally:
            self._quiet = False
        self._joint_changed()

    def _joint_changed(self):
        name = self.joint_box.currentData()
        joint = self.doc.getObject(name) if name else None
        motion = joints.default_motion(joint) if joint is not None else "angle"
        unit = _unit(motion)
        if getattr(self.value_field, "unit", None) != unit:
            position = self.layout.getWidgetPosition(self.value_field.widget)
            field = DistanceField(0.0, unit=unit, on_change=lambda v: None)
            field.widget.setObjectName("SciForgeStudy_value")
            self.value_field.widget.hide()
            self.layout.setWidget(position[0], QtWidgets.QFormLayout.FieldRole, field.widget)
            self.value_field.widget.setParent(None)
            self.value_field = field
        self.value_field.widget.setObjectName("SciForgeStudy_value")
        self.value_caption.setText(_motion_label(motion))

    def _mode_changed(self):
        self.data["mode"] = self.mode_box.currentData()
        self.changed()

    def _speed_changed(self):
        self.data["speed"] = float(self.speed.value())
        self.changed()

    # -- picks -------------------------------------------------------------------------------
    def allow_object(self, obj):
        return joints.is_joint(obj) or joints.part_of(obj) is not None

    def allow_pick(self, pick):
        return True

    def picked_raw(self, root, sub, point):
        joint, why = _joint_from(root, sub, point, self.doc)
        if joint is None:
            if why:
                self.refuse(why)
            return
        if joints.fusion_type(joint) == "rigid":
            self.refuse("%s is rigid: it has no motion to study." % joint.Label)
            return
        names = self.data["joints"]
        if joint.Name in names:
            names.remove(joint.Name)  # a click on a picked joint drops it
            self.data["keys"].pop(joint.Name, None)
        else:
            names.append(joint.Name)
            now = joints.joint_motion_value(joint, joints.default_motion(joint))
            self.data["keys"][joint.Name] = [[0.0, round(now, 9)]]  # where it stands now
        self._fill()
        hole_common.set_combo(self.joint_box, joint.Name)
        self._joint_changed()
        self.took()
        self.changed()

    def cleared(self, name):
        self._play(False)
        self.data["joints"] = []
        self.data["keys"] = {}
        self._fill()
        self.changed()

    # -- key points --------------------------------------------------------------------------
    def _set_point(self):
        name = self.joint_box.currentData()
        if not name:
            self.refuse("Pick a joint first.")
            return
        keys = self.data["keys"].get(name, [])
        keys = motion_core.set_key(keys, self.step.value(), self.value_field.value())
        self.data["keys"][name] = [list(k) for k in keys]
        self._fill()
        hole_common.set_combo(self.joint_box, name)
        self.changed()

    def _delete_point(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        if not rows:
            self.refuse("Click a point in the list first.")
            return
        for r in rows:
            item = self.table.item(r, 0)
            name, step = item.data(QtCore.Qt.UserRole)
            self.data["keys"][name] = [
                list(k) for k in motion_core.drop_key(self.data["keys"].get(name, []), step)
            ]
        self._fill()
        self.changed()

    # -- playing -----------------------------------------------------------------------------
    def _pose(self, step):
        joints.apply_placements(self.doc, self.start_places)
        joints.study_pose(self.doc, self.data, step)

    def _scrub(self, value):
        if self._quiet or self.playing:
            return
        self._pose(float(value))

    def _play(self, on):
        if not on:
            self.playing = False
            self.timer.stop()
            if self.play.isChecked():
                self.play.blockSignals(True)
                self.play.setChecked(False)
                self.play.blockSignals(False)
            self.play.setText("Play")
            return
        if not self._joints():
            self.play.setChecked(False)
            self.refuse("Pick the joints to move first.")
            return
        self.playing = True
        self.play.setText("Stop")
        self.play_started = time.perf_counter()
        self.timer.start()

    def _tick(self):
        try:
            if not self.playing or self._closed:
                self.timer.stop()
                return
            seconds = time.perf_counter() - self.play_started
            step, done = motion_core.study_step(
                seconds, motion_core.STUDY_STEPS, self.data.get("speed", 1.0), self.data["mode"]
            )
            self._pose(step)
            self._quiet = True
            try:
                self.slider.setValue(int(round(step)))
            finally:
                self._quiet = False
            if done:
                self._play(False)
        except Exception as exc:
            warn("Motion Study: %s" % exc)
            self._play(False)

    # -- the step ----------------------------------------------------------------------------
    def apply(self):
        if not self._joints():
            raise NeedsPick(
                "Click the joints to move (their rows in the browser or timeline, or a "
                "jointed component), then set their values at the steps."
            )
        if self.study is None:
            self.study = joints.create_motion_study(self.doc, self.data)
            self.target = self.study
        else:
            joints.set_motion_study(self.study, self.data)
        attach_views(self.doc)

    def preview_steps(self):
        return [self.study] if self.study is not None else []

    def can_finish(self):
        return "" if self.study is not None else "Pick the joints to move."

    def before_close(self, ok):
        self._play(False)
        try:
            joints.apply_placements(self.doc, self.start_places)
            joints.solve(self.doc)
        except Exception as exc:
            warn("Motion Study: %s" % exc)

    def remove_handles(self):
        try:
            self.timer.stop()
        except Exception:
            pass
        super().remove_handles()


def play_study(study, mode=None):
    """Play a stored motion study (its browser menu)."""
    if study is None:
        return None
    return _edit(MotionStudyPanel, study)


# -- commands --------------------------------------------------------------------------------------
class _Command:
    text = ""
    tip = ""
    icon = "joint"

    def GetResources(self):
        return {"MenuText": self.text, "ToolTip": self.tip, "Pixmap": ui_icon_path(self.icon)}

    def IsActive(self):
        return App.ActiveDocument is not None

    def run(self):
        pass

    def Activated(self):
        try:
            self.run()
        except Exception as exc:
            warn("%s could not start: %s" % (self.text, exc))


def _moving_joints(doc):
    return [j for j in joints.joints(doc) if joints.fusion_type(j) != "rigid"]


class MotionLinkCommand(_Command):
    text = "Motion Link"
    tip = (
        "Tie two joints' motion: when one moves, the other follows by a ratio (a gear and a "
        "rack, two gears)."
    )
    icon = "motion_link"

    def IsActive(self):
        doc = App.ActiveDocument
        return doc is not None and len(_moving_joints(doc)) >= 2

    def run(self):
        doc = App.ActiveDocument
        if doc is None or len(_moving_joints(doc)) < 2:
            commands.tell("A motion link needs two joints with a motion (Revolute, Slider...).")
            return
        _start(MotionLinkPanel)


class NewContactSetCommand(_Command):
    text = "New Contact Set"
    tip = "Components that stop where they touch while contact sets are on."
    icon = "contact_set"

    def IsActive(self):
        doc = App.ActiveDocument
        return doc is not None and len(joints.parts(doc)) >= 2

    def run(self):
        doc = App.ActiveDocument
        if doc is None or len(joints.parts(doc)) < 2:
            commands.tell("A contact set needs two components or bodies in the design.")
            return
        _start(ContactSetPanel)


class EnableContactSetsCommand(_Command):
    text = "Enable Contact Sets"
    tip = "The components of each contact set stop where they touch when moved."
    icon = "contact_set"

    def run(self):
        set_contact("sets")


class EnableAllContactCommand(_Command):
    text = "Enable All Contact"
    tip = "Every component stops where it touches another when moved (slower)."
    icon = "contact_set"

    def run(self):
        set_contact("all")


class DisableContactCommand(_Command):
    text = "Disable Contact"
    tip = "Components move through each other (the default)."
    icon = "contact_set"

    def run(self):
        set_contact("off")


class MotionStudyCommand(_Command):
    text = "Motion Study"
    tip = "Set joint values at steps and play them back (once, in a loop or back and forth)."
    icon = "motion_study"

    def IsActive(self):
        doc = App.ActiveDocument
        return doc is not None and bool(_moving_joints(doc))

    def run(self):
        doc = App.ActiveDocument
        if doc is None or not _moving_joints(doc):
            commands.tell("Make a joint with a motion (Revolute, Slider...) first.")
            return
        _start(MotionStudyPanel)


class ComponentDragCommand(_Command):
    text = "Component Drag"
    tip = (
        "When ticked, dragging a component with the mouse moves it along its joints; "
        "untick it to draw a selection box from a component instead."
    )
    icon = "component_drag"

    def IsActive(self):
        return True

    def run(self):
        joints_drag.toggle()


def edit_motion_link(feature):
    _edit(MotionLinkPanel, feature)


def edit_contact_set(feature):
    _edit(ContactSetPanel, feature)


def edit_motion_study(feature):
    _edit(MotionStudyPanel, feature)


COMMANDS = {
    "SciForge_MotionLink": MotionLinkCommand,
    "SciForge_NewContactSet": NewContactSetCommand,
    "SciForge_EnableContactSets": EnableContactSetsCommand,
    "SciForge_EnableAllContact": EnableAllContactCommand,
    "SciForge_DisableContact": DisableContactCommand,
    "SciForge_MotionStudy": MotionStudyCommand,
    "SciForge_ComponentDrag": ComponentDragCommand,
}
EDITORS = {
    "SciForge::MotionLink": edit_motion_link,
    "SciForge::ContactSet": edit_contact_set,
    "SciForge::MotionStudy": edit_motion_study,
}
