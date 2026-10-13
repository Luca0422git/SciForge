# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's ASSEMBLE joints: the dialogs and commands (the document side is joints.py, the
maths joints_core.py, the behaviour spec docs/sciforge/parity/joints.md).

Joint (J): two clicks. Hover a component and its snap points light up (a face's centre, its
corners, its edges' midpoints and round edges' centres; an edge's ends and middle; a corner),
the nearest one carrying a small triad that shows where the joint origin would be and how it
points. The first click picks component 1 (it moves), the second component 2: component 1
flies onto component 2 (faces mate) and the motion is previewed. The Position tab holds the
Mode, Offset X / Y / Z, Angle and Flip; the Motion tab the Type (Rigid, Revolute, Slider,
Cylindrical, Pin-Slot, Planar, Ball), its axes, Animate and the limits. OK keeps it (one undo
step), Cancel / Esc puts everything back.

Also here: As-Built Joint, Joint Origin, Rigid Group, Drive Joints, Ground / Unground
(browser right-click), Capture Position / Revert, the view providers of the joint objects
and a document watch that removes a deleted component's joints.
"""

import time

import FreeCAD as App
import FreeCADGui as Gui

from . import bodies_gui, commands, hole_common, joints, joints_core as core, log, preview, warn
from . import ui_icon_path
from .bodies_panel import BodyPanel, edit as _edit, start as _start
from .compat import QtCore, QtGui, QtWidgets
from .taskui import DistanceField

TYPES = [(core.TITLES[t], t) for t in core.JOINT_TYPES]
MODES = ["Simple", "Between Two Faces", "Two Edge Intersection"]
ICON_BY_TYPE = {
    "rigid": "joint",
    "revolute": "joint_revolute",
    "slider": "joint_slider",
    "cylindrical": "joint_cylindrical",
    "pinslot": "joint_pinslot",
    "planar": "joint_planar",
    "ball": "joint_ball",
}
SNAP = (0.55, 0.65, 0.78)  # a snap point that is not the nearest
SNAP_HOT = (0.30, 0.62, 0.95)  # Fusion's manipulator blue: the snap the click would take
AXIS_COLORS = ((0.93, 0.33, 0.31), (0.36, 0.78, 0.40), (0.31, 0.66, 0.95))  # X red, Y green, Z blue
PICK_PIXELS = 14.0
HOVER_MS = 30
ANIMATION_MS = 40
ANIMATION_SECONDS = 1.8
AXIS_KEYS = {"Rotate": "rotate", "Slide": "slide", "Normal": "rotate"}


class NeedsPick(joints.JointError):
    """A hint shown in blue while the dialog waits for a click."""


def _selection_entries(doc):
    """[(root object, full sub path, picked point or None)] of the selection, unresolved
    (the body or component at the top of the path, as FreeCAD's tree has it)."""
    found = []
    try:
        selected = Gui.Selection.getSelectionEx("", 0)
    except Exception:
        selected = Gui.Selection.getSelectionEx()
    for sel in selected:
        try:
            if sel.Object.Document.Name != doc.Name:
                continue
        except Exception:
            continue
        points = list(getattr(sel, "PickedPoints", []) or [])
        subs = list(sel.SubElementNames) or [""]
        for i, sub in enumerate(subs):
            point = App.Vector(points[i]) if i < len(points) else None
            found.append((sel.Object, sub, point))
    return found


def _label(pick, snap=None):
    text = pick.part.Label
    if pick.obj is not pick.part:
        text += " · " + pick.obj.Label
    if pick.element:
        text += " · " + pick.element
    if snap is not None and snap.get("kind") not in (None, "origin"):
        text += " (%s)" % {
            "centre": "centre",
            "vertex": "corner",
            "midpoint": "midpoint",
            "circle": "circle centre",
        }.get(snap["kind"], snap["kind"])
    return text


class _Gate:
    """Only what the open dialog can take lights up under the mouse and can be clicked."""

    def __init__(self, panel):
        self.panel = panel

    def allow(self, doc, obj, sub):
        try:
            panel = self.panel
            if panel is None or panel._closed:
                return True
            return bool(panel.allow_raw(obj, sub or ""))
        except Exception:
            return False


# -- the snap hover --------------------------------------------------------------------------------
class SnapHover:
    """Fusion's snap points on the element under the mouse, the nearest highlighted with a
    triad showing the joint origin it would make. Drawn in SciForge's own Coin nodes, never
    pickable (clicks go through to the element). `allow(pick)` says which components count."""

    def __init__(self, view, allow):
        from pivy import coin

        self.coin = coin
        self.view = view
        self.allow = allow
        self.enabled = True
        self.position = None
        self.key = None
        self.pick = None
        self.candidates = []
        self.hot = None
        self.root = coin.SoAnnotation()
        style = coin.SoPickStyle()
        style.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(style)
        self.switch = coin.SoSwitch()
        self.switch.whichChild = coin.SO_SWITCH_ALL
        self.root.addChild(self.switch)
        view.getSceneGraph().addChild(self.root)
        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.setInterval(HOVER_MS)
        self.timer.timeout.connect(self._update)
        self.callback = view.addEventCallback("SoLocation2Event", self._moved)

    # -- events ------------------------------------------------------------------------------------
    def _moved(self, info):
        try:
            self.position = tuple(info["Position"])
            if self.enabled and not self.timer.isActive():
                self.timer.start()
        except Exception:
            pass

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        if not enabled:
            self.clear()

    def _update(self):
        try:
            if not self.enabled or self.position is None:
                return
            info = self.view.getObjectInfo(self.position)
            pick = self._pick_from(info)
            if pick is None or not self.allow(pick):
                self.clear()
                return
            # the part may have moved since (the joint itself moves it): its place is part
            # of the key, else the snaps would be drawn where it stood
            plc = pick.part.Placement
            key = (pick.part.Name, pick.obj.Name, pick.element, tuple(plc.Base), plc.Rotation.Q)
            if key != self.key:
                self.key = key
                self.pick = pick
                self.candidates = joints.snap_candidates(pick)
            if not self.candidates:
                self.clear(keep_key=True)
                return
            pixels = []
            for snap in self.candidates:
                try:
                    pixels.append(self.view.getPointOnViewport(snap["point"]))
                except Exception:
                    pixels.append((-1e9, -1e9))
            index = core.nearest_on_screen(pixels, self.position, 1e9)
            hot = self.candidates[index] if index is not None else self.candidates[0]
            if hot is not self.hot or self.switch.getNumChildren() == 0:
                self.hot = hot
                self._draw()
        except Exception as exc:
            warn("joint snap hover: %s" % exc)

    def _pick_from(self, info):
        if not info or not info.get("Object"):
            return None
        doc = App.getDocument(info.get("Document")) if info.get("Document") else App.ActiveDocument
        if doc is None:
            return None
        root = info.get("ParentObject")
        sub = info.get("SubName") or ""
        if root is None:
            root = doc.getObject(info.get("Object"))
            sub = info.get("Component") or ""
        elif isinstance(root, str):
            root = doc.getObject(root)
        if root is None:
            return None
        point = App.Vector(info["x"], info["y"], info["z"])
        return joints.resolve_selection(root, sub, point)

    # -- results -----------------------------------------------------------------------------------
    def current(self):
        """(pick, hot snap) under the mouse now, or (None, None)."""
        if self.pick is None or self.hot is None:
            return None, None
        return self.pick, self.hot

    def snap_for(self, pick, point):
        """The snap a click on `pick` takes: the highlighted one when the mouse is on that
        element, else the one nearest the clicked point."""
        if (
            self.pick is not None
            and self.hot is not None
            and self.pick.part is pick.part
            and self.pick.obj is pick.obj
            and self.pick.element == pick.element
        ):
            return self.hot
        return joints.nearest_snap(joints.snap_candidates(pick), point)

    # -- drawing -----------------------------------------------------------------------------------
    def _size(self):
        try:
            from .taskui import handle_size_at

            return handle_size_at(self.view, self.hot["point"], pixels=28, lo=0.5)
        except Exception:
            return 3.0

    def _draw(self):
        coin = self.coin
        self.switch.removeAllChildren()
        size = self._size()
        for snap in self.candidates:
            hot = snap is self.hot
            sep = coin.SoSeparator()
            material = coin.SoMaterial()
            colour = SNAP_HOT if hot else SNAP
            material.diffuseColor.setValue(*colour)
            material.emissiveColor.setValue(*[c * 0.6 for c in colour])
            move = coin.SoTranslation()
            p = snap["point"]
            move.translation.setValue(p.x, p.y, p.z)
            ball = coin.SoSphere()
            ball.radius.setValue(size * (0.13 if hot else 0.08))
            sep.addChild(material)
            sep.addChild(move)
            sep.addChild(ball)
            self.switch.addChild(sep)
        if self.hot is not None:
            self.switch.addChild(self._triad(self.hot["frame"], size))

    def _triad(self, frame, size):
        coin = self.coin
        sep = coin.SoSeparator()
        style = coin.SoDrawStyle()
        style.lineWidth = 2.5
        sep.addChild(style)
        base = frame.Base
        for i, colour in enumerate(AXIS_COLORS):
            axis = frame.Rotation.multVec(App.Vector(*[1.0 if j == i else 0.0 for j in range(3)]))
            tip = base + axis * (size * (1.0 if i == 2 else 0.7))
            material = coin.SoMaterial()
            material.diffuseColor.setValue(*colour)
            material.emissiveColor.setValue(*colour)
            coords = coin.SoCoordinate3()
            coords.point.setValues(0, 2, [(base.x, base.y, base.z), (tip.x, tip.y, tip.z)])
            line = coin.SoLineSet()
            line.numVertices.setValue(2)
            sep.addChild(material)
            sep.addChild(coords)
            sep.addChild(line)
        return sep

    def clear(self, keep_key=False):
        if not keep_key:
            self.key = None
            self.pick = None
            self.candidates = []
        self.hot = None
        try:
            self.switch.removeAllChildren()
        except Exception:
            pass

    def remove(self):
        try:
            self.timer.stop()
        except Exception:
            pass
        if self.callback is not None:
            try:
                self.view.removeEventCallback("SoLocation2Event", self.callback)
            except Exception:
                pass
            self.callback = None
        try:
            self.view.getSceneGraph().removeChild(self.root)
        except Exception:
            pass


class Marker:
    """The triad of a joint origin already picked (stays while the dialog waits for the
    second click), drawn like the hover's."""

    def __init__(self, view, frame, size):
        from pivy import coin

        self.view = view
        self.root = coin.SoAnnotation()
        style = coin.SoPickStyle()
        style.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(style)
        hover = SnapHover.__new__(SnapHover)
        hover.coin = coin
        self.root.addChild(hover._triad(frame, size))
        view.getSceneGraph().addChild(self.root)

    def remove(self):
        try:
            self.view.getSceneGraph().removeChild(self.root)
        except Exception:
            pass


# -- animation -------------------------------------------------------------------------------------
class Animator:
    """Plays a joint through its freedom and back (Fusion's preview after the second pick,
    the Animate button, Animate Joint). Every frame starts from where the parts stood when
    the animation began, so nothing drifts; stop() puts them back exactly."""

    def __init__(self, joint, on_done=None, loop=False):
        self.joint = joint
        self.doc = joint.Document
        self.on_done = on_done
        self.loop = loop
        self.start_places = joints.placements(self.doc)
        self.angle0, self.slide0 = joints.value(joint)
        self.span = core.default_span(joints.part_size(joints.part1(joint)))
        self.started = time.perf_counter()
        self.timer = QtCore.QTimer()
        self.timer.setInterval(ANIMATION_MS)
        self.timer.timeout.connect(self._tick)
        self.running = False

    def start(self):
        if joints.fusion_type(self.joint) == "rigid":
            return False
        self.running = True
        self.started = time.perf_counter()
        self.timer.start()
        return True

    def _tick(self):
        try:
            if not self.running or self.joint.Document is None:
                self.stop()
                return
            elapsed = time.perf_counter() - self.started
            phase = (elapsed / ANIMATION_SECONDS) % 1.0
            if elapsed >= ANIMATION_SECONDS and not self.loop:
                self.stop()
                return
            joints.apply_placements(self.doc, self.start_places)
            kind = joints.fusion_type(self.joint)
            lim = joints.limits(self.joint)
            if kind in ("ball", "planar"):
                joints.wobble(self.joint, phase, self.span)
                joints.solve(self.doc)
            else:
                angle = slide = None
                if kind in core.HAS_ANGLE:
                    a = lim["angle"]
                    angle = core.sweep(phase, self.angle0, a["min"], a["max"], 90.0)
                if kind in core.HAS_DISTANCE:
                    s = lim["slide"]
                    slide = core.sweep(phase, self.slide0, s["min"], s["max"], self.span)
                joints.drive(self.joint, angle=angle, slide=slide)
        except Exception as exc:
            warn("joint animation: %s" % exc)
            self.stop()

    def stop(self):
        was = self.running
        self.running = False
        try:
            self.timer.stop()
        except Exception:
            pass
        if was:
            try:
                if self.joint.Document is not None:
                    joints.apply_placements(self.doc, self.start_places)
                    joints.solve(self.doc)
            except Exception as exc:
                warn("joint animation: %s" % exc)
            if self.on_done is not None:
                try:
                    self.on_done()
                except Exception:
                    pass


_STANDALONE = {"animator": None, "shortcut": None}


def animate(joint, loop=True):
    """Animate Joint (browser right-click): plays until Esc or another command."""
    stop_animation()
    if not commands.finish_open_dialog():  # a command in progress ends (and its Esc with it)
        return None
    if joint is None or joints.fusion_type(joint) == "rigid":
        commands.tell("A rigid joint has no motion to animate.")
        return None
    animator = Animator(joint, on_done=stop_animation, loop=loop)
    if not animator.start():
        return None
    _STANDALONE["animator"] = animator
    try:
        shortcut = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Escape), Gui.getMainWindow())
        shortcut.activated.connect(lambda: QtCore.QTimer.singleShot(0, stop_animation))
        _STANDALONE["shortcut"] = shortcut
    except Exception:
        pass
    log("animating %s (Esc stops it)" % joint.Label)
    return animator


def stop_animation():
    animator, _STANDALONE["animator"] = _STANDALONE["animator"], None
    shortcut, _STANDALONE["shortcut"] = _STANDALONE["shortcut"], None
    if shortcut is not None:
        try:
            shortcut.setEnabled(False)
            shortcut.setParent(None)
            shortcut.deleteLater()
        except Exception:
            pass
    if animator is not None:
        animator.on_done = None
        animator.stop()


# -- a shared base for the joint dialogs -----------------------------------------------------------
class _JointsPanel(BodyPanel):
    """BodyPanel with raw (unresolved) picks, a selection gate and the snap hover."""

    hover_boxes = ()  # names of the selection boxes that take a snap point

    def __init__(self, doc, transaction, editing=False):
        self.hover = None
        self.gate = None
        self.markers = []
        self.animator = None
        self.notice = ""  # a refusal to show until the next good pick
        self.transaction_name = transaction
        super().__init__(doc, transaction, editing)
        stop_animation()
        try:
            self.gate = _Gate(self)
            Gui.Selection.addSelectionGate(self.gate, Gui.Selection.ResolveMode.NoResolve)
        except Exception as exc:
            warn("%s: selection filter unavailable: %s" % (self.title, exc))
            self.gate = None
        try:
            self.hover = SnapHover(self.view, self.allow_hover)
        except Exception as exc:
            warn("%s: snap points unavailable: %s" % (self.title, exc))
            self.hover = None

    # -- picks -------------------------------------------------------------------------------------
    def allow_raw(self, root, sub):
        pick = joints.resolve_selection(root, sub)
        if pick is None:
            return self.allow_object(root)
        return self.allow_click(pick)

    def allow_object(self, obj):
        """A whole object clicked in the browser (no element)."""
        return False

    def allow_pick(self, pick):
        """What the dialog takes (and lights up on hover)."""
        return True

    def allow_click(self, pick):
        """What the selection filter lets through; a dialog may take more than allow_pick so
        it can say why a click is refused."""
        return self.allow_pick(pick)

    def allow_hover(self, pick):
        return self.active in self.hover_boxes and self.allow_pick(pick)

    def restart(self):
        """Take back everything the dialog changed so far (a joint being made, the component
        it moved, the ground it added) and keep waiting in a fresh undo step."""
        self.stop_animation()
        try:
            preview.end_transaction(self.doc, abort=True)
        except Exception as exc:
            warn("%s: %s" % (self.title, exc))
        self.doc.openTransaction(self.transaction_name)
        preview.recompute(self.doc)

    def refuse(self, text):
        """Show why a click was refused; it stays until the next good pick."""
        self.notice = text
        self.message.setText("⚠ " + text)

    def took(self):
        """A good pick: the refusal goes."""
        self.notice = ""
        self.message.setText("")

    def show_status(self):
        super().show_status()
        if self.notice and not self.error:
            self.message.setText("⚠ " + self.notice)

    def _selection_changed(self):
        if self._closed:
            return
        try:
            entries = _selection_entries(self.doc)
            if not entries:
                return
            self._syncing = True
            try:
                Gui.Selection.clearSelection()
            finally:
                self._syncing = False
            if time.time() < self._busy_until:
                return
            for root, sub, point in entries:
                self.picked_raw(root, sub, point)
        except Exception as exc:
            warn("%s pick: %s" % (self.title, exc))

    def start_from_selection(self):
        entries = _selection_entries(self.doc)
        self._syncing = True
        try:
            Gui.Selection.clearSelection()
        finally:
            self._syncing = False
        for root, sub, point in entries:
            try:
                self.picked_raw(root, sub, point)
            except Exception as exc:
                warn("%s pick: %s" % (self.title, exc))
        return bool(entries)

    def picked_raw(self, root, sub, point):
        """A click: a part's element (Pick) or a whole object (browser row)."""

    def snap_for(self, pick, point):
        if self.hover is not None:
            return self.hover.snap_for(pick, point)
        return joints.nearest_snap(joints.snap_candidates(pick), point)

    def activated(self, name):
        if self.hover is not None:
            self.hover.set_enabled(name in self.hover_boxes)

    # -- markers -----------------------------------------------------------------------------------
    def show_marker(self, frame):
        try:
            from .taskui import handle_size_at

            size = handle_size_at(self.view, frame.Base, pixels=28, lo=0.5)
            self.markers.append(Marker(self.view, frame, size))
        except Exception as exc:
            warn("%s marker: %s" % (self.title, exc))

    def clear_markers(self):
        for marker in self.markers:
            marker.remove()
        self.markers = []

    # -- animation ---------------------------------------------------------------------------------
    def stop_animation(self):
        animator, self.animator = self.animator, None
        if animator is not None:
            animator.on_done = None
            animator.stop()

    def changed(self):
        self.stop_animation()
        super().changed()

    def accept(self):
        self.stop_animation()
        return super().accept()

    def reject(self):
        self.stop_animation()
        return super().reject()

    # -- closing -----------------------------------------------------------------------------------
    def remove_handles(self):
        self.stop_animation()
        self.clear_markers()
        if self.hover is not None:
            self.hover.remove()
            self.hover = None
        if self.gate is not None:
            self.gate.panel = None
            try:
                Gui.Selection.removeSelectionGate()
            except Exception:
                pass
            self.gate = None

    def after_close(self, ok):
        super().after_close(ok)
        try:
            attach_views(self.doc)
        except Exception as exc:
            warn("%s: %s" % (self.title, exc))

    def solve_check(self, code):
        text = joints.solve_message(code)
        if text:
            raise joints.JointError(text)

    # -- form helpers ------------------------------------------------------------------------------
    def form_box(self, layout, name, label, empty="Select"):
        field = hole_common.SelectionField(self, name, empty)
        caption = QtWidgets.QLabel(label)
        layout.addRow(caption, field.widget)
        self.fields[name] = field
        self.captions[name] = caption
        return field

    def form_field(self, layout, label, value, unit, on_change):
        field = DistanceField(value, unit=unit, on_change=on_change)
        caption = QtWidgets.QLabel(label)
        layout.addRow(caption, field.widget)
        return field, caption

    def form_combo(self, layout, label, pairs, current, on_change):
        box = hole_common.combo(pairs, current)
        box.currentIndexChanged.connect(lambda *_: self._guarded(on_change))
        caption = QtWidgets.QLabel(label)
        layout.addRow(caption, box)
        return box, caption


class _Limits:
    """Fusion's motion limits (Minimum / Maximum / Rest, each a check box and a value) for an
    angle or a slide."""

    def __init__(self, panel, layout, unit, on_change):
        self.panel = panel
        self.unit = unit
        self.on_change = on_change
        self.rows = {}
        self.caption = QtWidgets.QLabel("Angle limits" if unit == "deg" else "Slide limits")
        font = self.caption.font()
        font.setBold(True)
        self.caption.setFont(font)
        layout.addRow(self.caption)
        for key, label in (("min", "Minimum"), ("max", "Maximum"), ("rest", "Rest")):
            check = QtWidgets.QCheckBox(label)
            check.setObjectName("SciForgeJoint_%s_%s" % (unit, key))
            field = DistanceField(0.0, unit=unit, on_change=lambda v: on_change())
            field.widget.setEnabled(False)
            check.toggled.connect(lambda on, k=key: self._toggled(k, on))
            layout.addRow(check, field.widget)
            self.rows[key] = (check, field)

    def _toggled(self, key, on):
        """A limit switched on starts at the joint's value now, so switching it on moves
        nothing until a value is typed."""
        try:
            _check, field = self.rows[key]
            field.widget.setEnabled(on)
            joint = getattr(self.panel, "joint", None)
            if on and joint is not None and not self.panel._quiet:
                angle, slide = joints.value(joint)
                field.set_value(round(angle if self.unit == "deg" else slide, 6))
            self.on_change()
        except Exception as exc:
            warn("joint limits: %s" % exc)

    def set_visible(self, shown):
        self.caption.setVisible(shown)
        for check, field in self.rows.values():
            check.setVisible(shown)
            field.widget.setVisible(shown)

    def values(self):
        out = {}
        for key, (check, field) in self.rows.items():
            out[key] = field.value() if check.isChecked() else None
        return out

    def show(self, data):
        for key, (check, field) in self.rows.items():
            value = data.get(key)
            check.setChecked(value is not None)
            field.widget.setEnabled(value is not None)
            if value is not None:
                field.set_value(value)


# -- Joint (J) -------------------------------------------------------------------------------------
class JointPanel(_JointsPanel):
    """Fusion's Joint dialog. Component 1 moves onto component 2."""

    title = "Joint"
    icon = "joint"
    needs_pick = (NeedsPick,)
    hover_boxes = ("comp1", "comp2")
    last = None

    def __init__(self, doc, feature=None, show_motion=False):
        self.joint = feature
        self.picks = {"comp1": None, "comp2": None}
        self.snaps = {"comp1": None, "comp2": None}
        self.first = feature is None
        self._announce = ""
        self._pending_animation = False
        self._realign = False  # a Position / type / axis change: the component goes to it
        self._rejoin = False
        super().__init__(doc, "Joint" if feature is None else "Edit Joint", feature is not None)
        JointPanel.last = self
        self.target = feature
        if feature is not None:
            self._read(feature)
            self.activate("comp1")
            if show_motion:
                self.tabs.setCurrentIndex(1)
        else:
            self.activate("comp1")
            Gui.Selection.clearSelection()  # Fusion's Joint starts with its own picks
        self.dirty = True
        self._timer.stop()
        self._recompute()

    # -- form --------------------------------------------------------------------------------------
    def build_form(self):
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setObjectName("SciForgeJointTabs")
        position = QtWidgets.QWidget()
        motion = QtWidgets.QWidget()
        self.tabs.addTab(position, "Position")
        self.tabs.addTab(motion, "Motion")
        self.layout.addRow(self.tabs)
        pos = QtWidgets.QFormLayout(position)
        self.form_box(pos, "comp1", "Component 1", "Select snap")
        self.form_box(pos, "comp2", "Component 2", "Select snap")
        self.mode, _ = self.form_combo(pos, "Mode", [(m, m) for m in MODES], "Simple", lambda: None)
        model = self.mode.model()
        for i in (1, 2):  # not built yet: shown greyed, like an unavailable Fusion option
            item = model.item(i)
            if item is not None:
                item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEnabled)
        self.offset_fields = {}
        for key, label in (("x", "Offset X"), ("y", "Offset Y"), ("z", "Offset Z")):
            field, _ = self.form_field(pos, label, 0.0, "mm", lambda v, k=key: self._offset(k, v))
            self.offset_fields[key] = field
        self.angle, _ = self.form_field(
            pos, "Angle", 0.0, "deg", lambda v: self._offset("angle", v)
        )
        self.flip = QtWidgets.QPushButton("Flip")
        self.flip.setObjectName("SciForgeJoint_flip")
        self.flip.setCheckable(True)
        self.flip.setToolTip("Turn component 1 over the joint origin")
        self.flip.toggled.connect(lambda on: self._guarded(lambda: self._offset("flip", on)))
        pos.addRow(QtWidgets.QLabel(""), self.flip)
        mot = QtWidgets.QFormLayout(motion)
        self.type_box, _ = self.form_combo(mot, "Type", TYPES, "rigid", self._type_changed)
        self.axis_boxes = {}
        for label in ("Rotate", "Slide", "Normal"):
            pairs = [(core.AXIS_LABELS[a], a) for a in ("z", "x", "y")]
            box, caption = self.form_combo(mot, label, pairs, "z", self._axes_changed)
            self.axis_boxes[label] = (box, caption)
        self.animate = QtWidgets.QPushButton("Animate")
        self.animate.setObjectName("SciForgeJoint_animate")
        self.animate.setCheckable(True)
        self.animate.setToolTip("Play the joint's motion (press again or Esc to stop)")
        self.animate.toggled.connect(lambda on: self._guarded(lambda: self._animate_toggled(on)))
        mot.addRow(QtWidgets.QLabel(""), self.animate)
        self.angle_limits = _Limits(self, mot, "deg", self._limits_changed)
        self.slide_limits = _Limits(self, mot, "mm", self._limits_changed)
        self._show_type_rows("rigid")

    def _show_type_rows(self, kind):
        wanted = {label: options for label, options in core.AXIS_CHOICES.get(kind, [])}
        for label, (box, caption) in self.axis_boxes.items():
            shown = label in wanted
            box.setVisible(shown)
            caption.setVisible(shown)
            if shown:
                self._quiet = True
                try:
                    current = box.currentData()
                    hole_common.fill_combo(
                        box,
                        [(core.AXIS_LABELS[a], a) for a in wanted[label]],
                        current if current in wanted[label] else wanted[label][0],
                    )
                finally:
                    self._quiet = False
        self.animate.setVisible(kind != "rigid")
        self.angle_limits.set_visible(kind in core.ANGLE_LIMITS)
        self.slide_limits.set_visible(kind in core.LENGTH_LIMITS)

    def _read(self, joint):
        """Show an existing joint's settings."""
        self._quiet = True
        try:
            kind = joints.fusion_type(joint)
            hole_common.set_combo(self.type_box, kind)
            self._show_type_rows(kind)
            data = joints.offsets(joint)
            for key, field in self.offset_fields.items():
                field.set_value(data[key])
            self.angle.set_value(data["angle"])
            self.flip.setChecked(bool(data["flip"]))
            axes = joints._json(joint, joints.PROPS["axes"], joints.default_axes(kind))
            for label, (box, _c) in self.axis_boxes.items():
                hole_common.set_combo(box, axes.get(AXIS_KEYS[label], "z"))
            lim = joints.limits(joint)
            self.angle_limits.show(lim["angle"])
            self.slide_limits.show(lim["slide"])
            for name, index in (("comp1", 0), ("comp2", 1)):
                ref = joint.Reference1 if index == 0 else joint.Reference2
                if ref:
                    obj = joints.shape_owner(ref) or ref[0]
                    pick = joints.Pick(ref[0], obj, joints.element_name(ref[1][0]))
                    self.picks[name] = pick
                    record = joints._json(joint, joints.PROPS["snap1" if index == 0 else "snap2"])
                    self.snaps[name] = {"kind": record.get("kind"), "at": record.get("at", "")}
                    self.fields[name].set_text(_label(pick, self.snaps[name]))
        finally:
            self._quiet = False

    # -- picks -------------------------------------------------------------------------------------
    def allow_pick(self, pick):
        if self.active == "comp2" and self.picks["comp1"] is not None:
            return pick.part is not self.picks["comp1"].part
        if self.active == "comp1" and self.picks["comp2"] is not None:
            return pick.part is not self.picks["comp2"].part
        return True

    def allow_click(self, pick):
        return pick.part is not None  # the same component again is refused with a message

    def allow_object(self, obj):
        """A joint origin's row in the browser is a snap too (Fusion: pick it anywhere)."""
        return self.active in ("comp1", "comp2") and joints.is_joint_origin(obj)

    def picked_raw(self, root, sub, point):
        pick = joints.resolve_selection(root, sub, point)
        if pick is None:
            return
        if not pick.element and not pick.is_datum():
            self.info.setText("Click a face, edge or corner of the component (a snap point).")
            return
        name = self.active if self.active in ("comp1", "comp2") else "comp1"
        other = "comp2" if name == "comp1" else "comp1"
        if self.picks[other] is not None and self.picks[other].part is pick.part:
            self.refuse(
                "Both picks are on %s. Pick a point on another component." % pick.part.Label
            )
            return
        snap = self.snap_for(pick, point)
        if snap is None:
            self.info.setText("No snap point there; try a face, an edge or a corner.")
            return
        self.picks[name] = pick
        self.snaps[name] = snap
        self.fields[name].set_text(_label(pick, snap))
        self.took()
        if name == "comp1":
            self.clear_markers()
            self.show_marker(snap["frame"])
            if self.picks["comp2"] is None:
                self.activate("comp2")
        else:
            self.clear_markers()
        if self.joint is not None:
            self._rejoin = True
        self.changed()

    def cleared(self, name):
        self.picks[name] = None
        self.snaps[name] = None
        self.fields[name].set_text("")
        self.clear_markers()
        self.stop_animation()
        if self.joint is not None and self.first:
            # the joint being made goes with its picks; the component comes back, and the
            # ground the joint added goes
            self.joint = None
            self.target = None
            self._announce = ""
            self.restart()

    # -- fields ------------------------------------------------------------------------------------
    def _offset(self, key, value):
        if self._quiet or self._closed:
            return
        if self.joint is not None:
            try:
                joints.set_offset(self.joint, **{key: value})
            except Exception as exc:
                self.message.setText("⚠ %s" % exc)
                return
        self._realign = True
        self.changed()

    def _type_changed(self):
        kind = self.type_box.currentData()
        self._show_type_rows(kind)
        # Fusion plays the new motion once as soon as the type is picked
        self._pending_animation = self.joint is not None and kind != "rigid"
        self._realign = True
        self.changed()

    def _axes_changed(self):
        self._realign = True
        self.changed()

    def _limits_changed(self):
        self.changed()

    def _animate_toggled(self, on):
        if not on:
            self.stop_animation()
            return
        if self.joint is None:
            self.animate.setChecked(False)
            return
        self._start_animation(loop=True)

    def _start_animation(self, loop=False):
        # the playing one stops; the Animate button keeps the state the person gave it
        _JointsPanel.stop_animation(self)
        if self.joint is None or joints.fusion_type(self.joint) == "rigid":
            return
        self.animator = Animator(self.joint, on_done=self._animation_done, loop=loop)
        if not self.animator.start():
            self.animator = None

    def _animation_done(self):
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

    # -- the preview -------------------------------------------------------------------------------
    def apply(self):
        pick1, pick2 = self.picks["comp1"], self.picks["comp2"]
        kind = self.type_box.currentData()
        if pick1 is None:
            raise NeedsPick("Click a snap point on the first component (the one that will move).")
        if pick2 is None:
            raise NeedsPick("Click a snap point on the second component.")
        offset = {k: f.value() for k, f in self.offset_fields.items()}
        offset["angle"] = self.angle.value()
        offset["flip"] = self.flip.isChecked()
        axes = {}
        for label, (box, _c) in self.axis_boxes.items():
            if not box.isHidden():  # shown for this type (the Motion tab may be behind)
                axes[AXIS_KEYS[label]] = box.currentData()
        made = False
        if self.joint is None:
            self.joint = joints.create_joint(
                self.doc, kind, pick1, self.snaps["comp1"], pick2, self.snaps["comp2"], offset, axes
            )
            self.target = self.joint
            made = True
            grounded = joints.ensure_ground(self.joint)
            self._announce = (
                "%s is grounded so the joint has something to hold on to (Unground it in the "
                "browser if it must move)." % grounded.Label
                if grounded is not None
                else ""
            )
        else:
            if self._rejoin:
                self._rejoin = False
                joints._set_json(
                    self.joint,
                    joints.PROPS["snap1"],
                    joints.snap_record(pick1, self.snaps["comp1"]),
                )
                joints._set_json(
                    self.joint,
                    joints.PROPS["snap2"],
                    joints.snap_record(pick2, self.snaps["comp2"]),
                )
                joints.set_references(self.joint, pick1, pick2)
                made = True
            joints.set_type(self.joint, kind, pick1, pick2)
            joints.set_offset(self.joint, **offset)
            if axes:
                joints.set_axes(self.joint, **axes)
        self._apply_limits()
        attach_views(self.doc)
        realign, self._realign = made or self._realign, False
        if realign:
            # the component goes where the picks, Offsets, Angle, Flip and type put it
            code = joints.align(self.joint, first=made)
            if made:
                self._pending_animation = True
        else:
            code = joints.solve(self.doc)  # only the limits changed: nothing else moves
        if code == 0:
            joints.keep_in_limits(self.joint)
        self.solve_check(code)

    def _apply_limits(self):
        if self.joint is None:
            return
        kind = joints.fusion_type(self.joint)
        angle = self.angle_limits.values() if kind in core.ANGLE_LIMITS else None
        slide = self.slide_limits.values() if kind in core.LENGTH_LIMITS else None
        joints.set_limits(self.joint, angle=angle, slide=slide)

    def after_recompute(self):
        if self.joint is None:
            self.note.setText("")
            return
        angle, slide = joints.value(self.joint)
        kind = joints.fusion_type(self.joint)
        parts = []
        if kind in core.HAS_ANGLE:
            parts.append("angle %.1f°" % angle)
        if kind in core.HAS_DISTANCE:
            parts.append("slide %.2f mm" % slide)
        text = self._announce
        if parts:
            text = (text + " " if text else "") + "Now: " + ", ".join(parts) + "."
        self.note.setText(text)
        if self._pending_animation:
            self._pending_animation = False
            QtCore.QTimer.singleShot(0, lambda: self._start_animation(loop=False))

    def preview_steps(self):
        return [self.joint] if self.joint is not None else []

    def can_finish(self):
        if self.joint is None:
            return "Pick a snap point on each of two components."
        return ""

    def before_close(self, ok):
        self.stop_animation()
        if ok and self.joint is not None:
            try:
                joints.go_to_rest(self.joint)
                joints.save_baseline(self.doc)
            except Exception as exc:
                warn("Joint: %s" % exc)


# -- As-Built Joint --------------------------------------------------------------------------------
class AsBuiltPanel(_JointsPanel):
    """Fusion's As-Built Joint: two components where they stand, a type, and for every type
    but Rigid a Position (snap point) for the motion's axis."""

    title = "As-Built Joint"
    icon = "joint_asbuilt"
    needs_pick = (NeedsPick,)
    hover_boxes = ("position",)
    last = None

    def __init__(self, doc, feature=None):
        self.joint = feature
        self.parts = []
        self.position_pick = None
        self.position_snap = None
        self._remake = False  # the components, the type or the position changed
        super().__init__(
            doc, "As-Built Joint" if feature is None else "Edit As-Built Joint", feature is not None
        )
        AsBuiltPanel.last = self
        self.target = feature
        if feature is not None:
            self._read(feature)
            self.activate("position" if joints.fusion_type(feature) != "rigid" else "components")
        else:
            self.activate("components")
            self.start_from_selection()
        self.dirty = True
        self._timer.stop()
        self._recompute()

    def build_form(self):
        self.form_box(self.layout, "components", "Components", "Select")
        self.type_box, _ = self.form_combo(self.layout, "Type", TYPES, "rigid", self._type_changed)
        self.form_box(self.layout, "position", "Position", "Select snap")
        self.angle_limits = _Limits(self, self.layout, "deg", self.changed)
        self.slide_limits = _Limits(self, self.layout, "mm", self.changed)
        self._show_rows("rigid")

    def _show_rows(self, kind):
        shown = kind != "rigid"
        self.fields["position"].widget.setVisible(shown)
        self.captions["position"].setVisible(shown)
        self.angle_limits.set_visible(kind in core.ANGLE_LIMITS)
        self.slide_limits.set_visible(kind in core.LENGTH_LIMITS)

    def _read(self, joint):
        self._quiet = True
        try:
            kind = joints.fusion_type(joint)
            hole_common.set_combo(self.type_box, kind)
            self._show_rows(kind)
            self.parts = [p for p in (joints.part1(joint), joints.part2(joint)) if p is not None]
            self.fields["components"].set_text(", ".join(p.Label for p in self.parts))
            lim = joints.limits(joint)
            self.angle_limits.show(lim["angle"])
            self.slide_limits.show(lim["slide"])
            for index in (0, 1):
                record = joints._json(joint, joints.PROPS["snap1" if index == 0 else "snap2"])
                if record.get("kind") not in ("asbuilt", None):
                    ref = joint.Reference1 if index == 0 else joint.Reference2
                    obj = joints.shape_owner(ref) or ref[0]
                    self.position_pick = joints.Pick(ref[0], obj, record.get("element", ""))
                    self.position_snap = {"kind": record.get("kind"), "at": record.get("at", "")}
                    self.fields["position"].set_text(_label(self.position_pick, self.position_snap))
        finally:
            self._quiet = False

    def allow_object(self, obj):
        return self.active == "components" and joints.part_of(obj) is not None

    def allow_pick(self, pick):
        if self.active == "position":
            return pick.part in self.parts if self.parts else True
        return True

    def allow_click(self, pick):
        return pick.part is not None

    def picked_raw(self, root, sub, point):
        pick = joints.resolve_selection(root, sub, point)
        part = pick.part if pick is not None else joints.part_of(root)
        if part is None:
            return
        if self.active == "position" and pick is not None and (pick.element or pick.is_datum()):
            if self.parts and part not in self.parts:
                self.refuse("Pick the position on one of the two components.")
                return
            snap = self.snap_for(pick, point)
            if snap is None:
                return
            self.position_pick, self.position_snap = pick, snap
            self.fields["position"].set_text(_label(pick, snap))
            self.clear_markers()
            self.show_marker(snap["frame"])
            self.took()
            self._remake = True
            self.changed()
            return
        if part in self.parts:
            self.parts.remove(part)  # a click on a picked component drops it
        elif len(self.parts) >= 2:
            self.refuse("An as-built joint takes two components; clear one first.")
            return
        else:
            self.parts.append(part)
        self.fields["components"].set_text(", ".join(p.Label for p in self.parts))
        self.took()
        self._remake = True
        if len(self.parts) == 2 and self.type_box.currentData() != "rigid":
            self.activate("position")
        self.changed()

    def cleared(self, name):
        if name == "components":
            self.parts = []
            self.fields["components"].set_text("")
        else:
            self.position_pick = self.position_snap = None
            self.fields["position"].set_text("")
            self.clear_markers()
        if self.joint is not None and not self.editing:
            self.joint = None
            self.target = None
            self.restart()  # the joint and the ground it added go

    def _type_changed(self):
        kind = self.type_box.currentData()
        self._show_rows(kind)
        self._remake = True
        if kind != "rigid" and len(self.parts) == 2 and self.position_pick is None:
            self.activate("position")
        self.changed()

    def apply(self):
        kind = self.type_box.currentData()
        if len(self.parts) < 2:
            raise NeedsPick("Click two components (in the view or the browser).")
        if kind != "rigid" and self.position_snap is None:
            raise NeedsPick("Click a snap point for the joint's position (its axis).")
        position = (self.position_pick, self.position_snap) if kind != "rigid" else (None, None)
        if self.joint is None:
            self.joint = joints.create_as_built_joint(
                self.doc, kind, self.parts[0], self.parts[1], *position
            )
            self.target = self.joint
        elif self._remake:
            # the same joint, redefined (Edit keeps it in its place in the timeline)
            joints.set_as_built(self.joint, kind, self.parts[0], self.parts[1], *position)
            joints.ensure_ground(self.joint)
        self._remake = False
        angle = self.angle_limits.values() if kind in core.ANGLE_LIMITS else None
        slide = self.slide_limits.values() if kind in core.LENGTH_LIMITS else None
        joints.set_limits(self.joint, angle=angle, slide=slide)
        attach_views(self.doc)
        code = joints.solve(self.doc)
        if code == 0:
            joints.keep_in_limits(self.joint)
        self.solve_check(code)

    def preview_steps(self):
        return [self.joint] if self.joint is not None else []

    def can_finish(self):
        return "" if self.joint is not None else "Pick two components."

    def before_close(self, ok):
        self.stop_animation()
        if ok and self.joint is not None:
            try:
                joints.go_to_rest(self.joint)
                joints.save_baseline(self.doc)
            except Exception as exc:
                warn("As-Built Joint: %s" % exc)


# -- Joint Origin ----------------------------------------------------------------------------------
class JointOriginPanel(_JointsPanel):
    """Fusion's Joint Origin: one snap point plus offsets, angle and flip."""

    title = "Joint Origin"
    icon = "joint_origin"
    needs_pick = (NeedsPick,)
    hover_boxes = ("snap",)
    last = None

    def __init__(self, doc, feature=None):
        self.origin = feature
        self.pick = None
        self.snap = None
        super().__init__(
            doc, "Joint Origin" if feature is None else "Edit Joint Origin", feature is not None
        )
        JointOriginPanel.last = self
        self.target = feature
        if feature is not None:
            self._read(feature)
        self.activate("snap")
        self.dirty = True
        self._timer.stop()
        self._recompute()

    def build_form(self):
        self.form_box(self.layout, "snap", "Snap", "Select snap")
        self.offset_fields = {}
        for key, label in (("x", "Offset X"), ("y", "Offset Y"), ("z", "Offset Z")):
            field, _ = self.form_field(self.layout, label, 0.0, "mm", lambda v: self.changed())
            self.offset_fields[key] = field
        self.angle, _ = self.form_field(self.layout, "Angle", 0.0, "deg", lambda v: self.changed())
        self.flip = QtWidgets.QPushButton("Flip")
        self.flip.setCheckable(True)
        self.flip.toggled.connect(lambda on: self._guarded(self.changed))
        self.layout.addRow(QtWidgets.QLabel(""), self.flip)

    def _read(self, origin):
        self._quiet = True
        try:
            data = dict(joints.default_offset(), **joints._json(origin, joints.PROPS["offset"]))
            for key, field in self.offset_fields.items():
                field.set_value(data[key])
            self.angle.set_value(data["angle"])
            self.flip.setChecked(bool(data["flip"]))
            on = joints.joint_origin_owner(origin)
            if on is not None:
                part = joints.part_of(on) or on
                self.pick = joints.Pick(part, on, getattr(origin, "SciForgeElement", ""))
                record = joints._json(origin, joints.PROPS["snap1"])
                self.snap = {"kind": record.get("kind"), "at": record.get("at", "")}
                self.fields["snap"].set_text(_label(self.pick, self.snap))
        finally:
            self._quiet = False

    def allow_pick(self, pick):
        return not pick.is_datum()

    def picked_raw(self, root, sub, point):
        pick = joints.resolve_selection(root, sub, point)
        if pick is None or not pick.element:
            return
        snap = self.snap_for(pick, point)
        if snap is None:
            return
        self.pick, self.snap = pick, snap
        self.fields["snap"].set_text(_label(pick, snap))
        self.message.setText("")
        self.changed()

    def cleared(self, name):
        self.pick = self.snap = None
        self.fields["snap"].set_text("")
        if self.origin is not None and not self.editing:
            try:
                self.doc.removeObject(self.origin.Name)
            except Exception:
                pass
            self.origin = None
            self.target = None

    def apply(self):
        if self.pick is None:
            raise NeedsPick("Click a snap point on a component: the joint origin goes there.")
        offset = {k: f.value() for k, f in self.offset_fields.items()}
        offset["angle"] = self.angle.value()
        offset["flip"] = self.flip.isChecked()
        same = (
            self.origin is not None and getattr(self.origin, "SciForgeOn", "") == self.pick.obj.Name
        )
        if self.origin is not None and not same and not self.editing:
            self.doc.removeObject(self.origin.Name)
            self.origin = None
        if self.origin is None:
            self.origin = joints.create_joint_origin(self.doc, self.pick, self.snap, offset)
            self.target = self.origin
        else:
            joints._set_json(
                self.origin, joints.PROPS["snap1"], joints.snap_record(self.pick, self.snap)
            )
            self.origin.SciForgeOn = self.pick.obj.Name
            self.origin.SciForgeElement = self.pick.element
            joints._set_json(
                self.origin, joints.PROPS["offset"], dict(joints.default_offset(), **offset)
            )
            joints.place_joint_origin(self.origin)

    def preview_steps(self):
        return [self.origin] if self.origin is not None else []

    def can_finish(self):
        return "" if self.origin is not None else "Pick a snap point."


# -- Rigid Group -----------------------------------------------------------------------------------
class RigidGroupPanel(_JointsPanel):
    """Fusion's Rigid Group: two or more components locked together where they stand."""

    title = "Rigid Group"
    icon = "rigid_group"
    needs_pick = (NeedsPick,)
    hover_boxes = ()
    last = None

    def __init__(self, doc, feature=None):
        self.group = feature
        self.members = []
        super().__init__(
            doc, "Rigid Group" if feature is None else "Edit Rigid Group", feature is not None
        )
        RigidGroupPanel.last = self
        self.target = feature
        if feature is not None:
            self.members = [m for m in feature.Members if m is not None]
            self.include.setChecked(bool(feature.IncludeChildren))
            self._show_members()
        self.activate("components")
        if feature is None:
            self.start_from_selection()
        self.dirty = True
        self._timer.stop()
        self._recompute()

    def build_form(self):
        self.form_box(self.layout, "components", "Components", "Select")
        self.include, _ = self.check_box(
            "Include Child Components",
            True,
            self.changed,
            "Components inside the picked components are locked in too",
        )

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
        self.message.setText("")
        self.changed()

    def cleared(self, name):
        self.members = []
        self._show_members()
        self.changed()

    def apply(self):
        if len(self.members) < 2:
            if self.group is not None and not self.editing:
                self.doc.removeObject(self.group.Name)
                self.group = None
                self.target = None
            raise NeedsPick("Click two or more components (in the view or the browser).")
        if self.group is None:
            self.group = joints.create_rigid_group(self.doc, self.members, self.include.isChecked())
            self.target = self.group
        else:
            self.group.Members = self.members
            self.group.IncludeChildren = self.include.isChecked()
            joints.rebuild_rigid_group(self.group)
        attach_views(self.doc)
        self.solve_check(joints.solve(self.doc))

    def preview_steps(self):
        return [self.group] if self.group is not None else []

    def can_finish(self):
        return "" if self.group is not None else "Pick two or more components."

    def before_close(self, ok):
        if ok:
            try:
                joints.save_baseline(self.doc)
            except Exception as exc:
                warn("Rigid Group: %s" % exc)


# -- Drive Joints ----------------------------------------------------------------------------------
class DrivePanel(_JointsPanel):
    """Fusion's Drive Joints: pick a joint, type or slide its value, Animate."""

    title = "Drive Joints"
    icon = "drive_joints"
    needs_pick = (NeedsPick,)
    hover_boxes = ()
    last = None

    def __init__(self, doc, joint=None):
        self.joint = None
        self._start = {}
        self._in_slider = False
        super().__init__(doc, "Drive Joints", False)
        DrivePanel.last = self
        self.activate("joint")
        if joint is not None:
            self._take_joint(joint)
        else:
            self.start_from_selection()
        self.dirty = True
        self._timer.stop()
        self._recompute()

    def build_form(self):
        self.form_box(self.layout, "joint", "Joint", "Select")
        self.angle, self.angle_caption = self.form_field(
            self.layout, "Rotation", 0.0, "deg", lambda v: self._typed()
        )
        self.angle_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.angle_slider.setObjectName("SciForgeDrive_angle")
        self.angle_slider.setRange(-1800, 1800)
        self.angle_slider.valueChanged.connect(
            lambda v: self._guarded(lambda: self._slid("angle", v))
        )
        self.layout.addRow(QtWidgets.QLabel(""), self.angle_slider)
        self.slide, self.slide_caption = self.form_field(
            self.layout, "Distance", 0.0, "mm", lambda v: self._typed()
        )
        self.slide_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slide_slider.setObjectName("SciForgeDrive_slide")
        self.slide_slider.setRange(-1000, 1000)
        self.slide_slider.valueChanged.connect(
            lambda v: self._guarded(lambda: self._slid("slide", v))
        )
        self.layout.addRow(QtWidgets.QLabel(""), self.slide_slider)
        self.animate = QtWidgets.QPushButton("Animate")
        self.animate.setObjectName("SciForgeDrive_animate")
        self.animate.setCheckable(True)
        self.animate.toggled.connect(lambda on: self._guarded(lambda: self._animate_toggled(on)))
        self.layout.addRow(QtWidgets.QLabel(""), self.animate)
        self._show_rows(None)

    def _show_rows(self, joint):
        kind = joints.fusion_type(joint) if joint is not None else None
        has_angle = kind in core.HAS_ANGLE
        has_slide = kind in core.HAS_DISTANCE
        for widget in (self.angle.widget, self.angle_caption, self.angle_slider):
            widget.setVisible(has_angle)
        for widget in (self.slide.widget, self.slide_caption, self.slide_slider):
            widget.setVisible(has_slide)
        self.animate.setVisible(joint is not None and kind != "rigid")

    def allow_object(self, obj):
        return joints.is_joint(obj) or joints.part_of(obj) is not None

    def allow_pick(self, pick):
        return True

    def picked_raw(self, root, sub, point):
        joint = None
        if joints.is_joint(root):
            joint = root
        else:
            pick = joints.resolve_selection(root, sub, point)
            part = pick.part if pick is not None else joints.part_of(root)
            if part is not None:
                for j in joints.joints(self.doc):
                    if (
                        part in (joints.part1(j), joints.part2(j))
                        and joints.fusion_type(j) != "rigid"
                    ):
                        joint = j
                        break
                if joint is None:
                    self.refuse("%s has no joint with a motion to drive." % part.Label)
                    return
        if joint is not None:
            self._take_joint(joint)

    def _take_joint(self, joint):
        self.stop_animation()
        if joints.fusion_type(joint) == "rigid":
            self.refuse("%s is rigid: it has no motion to drive." % joint.Label)
            return
        self.joint = joint
        self.fields["joint"].set_text(joint.Label)
        self._start = joints.placements(self.doc)
        angle, slide = joints.value(joint)
        lim = joints.limits(joint)
        self._quiet = True
        try:
            self.angle.set_value(angle)
            self.slide.set_value(slide)
            a_lo = lim["angle"]["min"] if lim["angle"]["min"] is not None else -180.0
            a_hi = lim["angle"]["max"] if lim["angle"]["max"] is not None else 180.0
            self.angle_slider.setRange(int(round(a_lo * 10)), int(round(a_hi * 10)))
            self.angle_slider.setValue(int(round(angle * 10)))
            span = core.default_span(joints.part_size(joints.part1(joint))) * 2.0
            s_lo = lim["slide"]["min"] if lim["slide"]["min"] is not None else slide - span
            s_hi = lim["slide"]["max"] if lim["slide"]["max"] is not None else slide + span
            self.slide_slider.setRange(int(round(s_lo * 100)), int(round(s_hi * 100)))
            self.slide_slider.setValue(int(round(slide * 100)))
        finally:
            self._quiet = False
        self._show_rows(joint)
        self.took()
        self.changed()

    def cleared(self, name):
        self.stop_animation()
        if self.joint is not None:
            joints.apply_placements(self.doc, self._start)
            joints.solve(self.doc)
        self.joint = None
        self.fields["joint"].set_text("")
        self._show_rows(None)
        self.changed()

    def _typed(self):
        if self._quiet or self._closed:
            return
        self._quiet = True
        try:
            self.angle_slider.setValue(int(round(self.angle.value() * 10)))
            self.slide_slider.setValue(int(round(self.slide.value() * 100)))
        finally:
            self._quiet = False
        self.changed()

    def _slid(self, key, raw):
        if self._quiet or self._closed:
            return
        self._quiet = True
        try:
            if key == "angle":
                self.angle.set_value(raw / 10.0)
            else:
                self.slide.set_value(raw / 100.0)
        finally:
            self._quiet = False
        self.changed()

    def _animate_toggled(self, on):
        if not on:
            self.stop_animation()
            return
        if self.joint is None:
            self.animate.setChecked(False)
            return
        self.stop_animation()
        self.animator = Animator(self.joint, on_done=self._animation_done, loop=True)
        if not self.animator.start():
            self.animator = None
            self.animate.setChecked(False)

    def _animation_done(self):
        self.animator = None
        try:
            self.animate.setChecked(False)
        except Exception:
            pass

    def apply(self):
        if self.joint is None:
            raise NeedsPick(
                "Click a joint (in the browser or the timeline), or a jointed component."
            )
        kind = joints.fusion_type(self.joint)
        angle = self.angle.value() if kind in core.HAS_ANGLE else None
        slide = self.slide.value() if kind in core.HAS_DISTANCE else None
        got_angle, got_slide = joints.drive(self.joint, angle=angle, slide=slide)
        self._quiet = True
        try:
            if angle is not None and abs(got_angle - angle) > 1e-6:
                self.angle.set_value(got_angle)  # clamped to a limit
                self.angle_slider.setValue(int(round(got_angle * 10)))
            if slide is not None and abs(got_slide - slide) > 1e-6:
                self.slide.set_value(got_slide)
                self.slide_slider.setValue(int(round(got_slide * 100)))
        finally:
            self._quiet = False

    def can_finish(self):
        return "" if self.joint is not None else "Pick a joint to drive."

    def before_close(self, ok):
        self.stop_animation()


# -- Ground, Capture Position, Revert --------------------------------------------------------------
def toggle_ground(obj):
    """Ground / Unground a component (browser right-click, the Ground command)."""
    part = joints.part_of(obj) if obj is not None else None
    if part is None:
        commands.tell("Pick a body or component to ground.")
        return False
    if not commands.finish_open_dialog():
        return False
    doc = part.Document
    grounded = joints.is_grounded(part)
    doc.openTransaction("Unground %s" % part.Label if grounded else "Ground %s" % part.Label)
    try:
        if grounded:
            joints.unground(part)
        else:
            joints.ground(part)
            attach_views(doc)
        joints.solve(doc)
        preview.recompute(doc)
    except Exception as exc:
        doc.abortTransaction()
        warn("Ground: %s" % exc)
        commands.tell(str(exc))
        return False
    doc.commitTransaction()
    _refresh_browser()
    return True


def capture_position(doc):
    if doc is None:
        commands.tell("Open or start a design first.")
        return None
    if not commands.finish_open_dialog():
        return None
    doc.openTransaction("Capture Position")
    try:
        obj = joints.capture_position(doc)
        attach_views(doc)
        preview.recompute(doc)
    except Exception as exc:
        doc.abortTransaction()
        commands.tell(str(exc))
        return None
    doc.commitTransaction()
    log("position captured as %s" % obj.Label)
    return obj


def revert_position(doc):
    if doc is None:
        commands.tell("Open or start a design first.")
        return False
    if not commands.finish_open_dialog():
        return False
    doc.openTransaction("Revert Position")
    try:
        joints.revert_position(doc)
        preview.recompute(doc)
    except Exception as exc:
        doc.abortTransaction()
        commands.tell(str(exc))
        return False
    doc.commitTransaction()
    return True


def _refresh_browser():
    try:
        from . import browser_ui

        tree = browser_ui.widget()
        if tree is not None:
            tree.refresh(force=True)
    except Exception:
        pass


# -- view providers --------------------------------------------------------------------------------
_VIEW_BASE = object
try:
    import JointObject as _JointObject

    _VIEW_BASE = _JointObject.ViewProviderJoint
except Exception as _exc:  # pragma: no cover
    warn("FreeCAD's joint view provider is not available: %s" % _exc)


class JointView(_VIEW_BASE):
    """FreeCAD's joint view provider (it draws the two joint origins) with SciForge's icons
    and dialog. Saved as "sciforge.joints_ui.JointView": keep the name."""

    def getIcon(self):
        try:
            return ui_icon_path(ICON_BY_TYPE.get(joints.fusion_type(self.app_obj), "joint"))
        except Exception:
            return ui_icon_path("joint")

    def getOverlayIcons(self):
        return {}

    def doubleClicked(self, vobj):
        bodies_gui._edit_later(vobj.Object)
        return True

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return None
        bodies_gui._edit_later(vobj.Object)
        return True

    def unsetEdit(self, vobj, mode=0):
        return None

    def canDelete(self, _obj):
        return True


class GroundView:
    """A grounded component: nothing in the 3D view (Fusion shows an anchor in the browser
    only). Saved as "sciforge.joints_ui.GroundView": keep the name."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        from pivy import coin

        self.Object = vobj.Object
        vobj.addDisplayMode(coin.SoSeparator(), "Default")

    def getDisplayModes(self, vobj):
        return ["Default"]

    def getDefaultDisplayMode(self):
        return "Default"

    def getIcon(self):
        return ui_icon_path("ground")

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def attach_views(doc):
    """Give every joint object without a view provider its SciForge one."""
    if doc is None or not App.GuiUp:
        return
    for obj in doc.Objects:
        try:
            vobj = obj.ViewObject
            if vobj is None or getattr(vobj, "Proxy", None) is not None:
                continue
            if joints.is_joint(obj) or joints.is_helper(obj):
                JointView(vobj)
                if joints.is_helper(obj):
                    vobj.Visibility = False
            elif "ObjectToGround" in obj.PropertiesList:
                GroundView(vobj)
                vobj.Visibility = False
            elif joints.is_rigid_group(obj) or getattr(obj, joints.TYPE_PROP, "") == "Position":
                bodies_gui.StepViewProvider(vobj)
        except Exception as exc:
            warn("joint view: %s" % exc)


# -- the document watch ----------------------------------------------------------------------------
class Watch:
    """Removes a deleted component's joints (Fusion deletes them with it) and keeps joint
    origins on their geometry, a moment after FreeCAD's own callbacks."""

    def __init__(self):
        self._pending = set()
        self._tidy = set()

    def _later(self, doc, tidy=False):
        try:
            name = doc.Name
        except Exception:
            return
        if tidy:
            self._tidy.add(name)
        if name in self._pending:
            return
        self._pending.add(name)
        QtCore.QTimer.singleShot(0, lambda: self._run(name))

    def slotDeletedObject(self, obj):
        try:
            doc = obj.Document
            if getattr(doc, "Transacting", False):
                return  # an undo / redo brings its joints back or takes them itself
            if joints.is_part(obj) or obj.TypeId in ("PartDesign::Body", "App::Part"):
                self._later(doc, tidy=True)
        except Exception:
            pass

    def slotRecomputedDocument(self, doc):
        self._later(doc)

    def slotUndoDocument(self, doc):
        self._later(doc)

    def slotRedoDocument(self, doc):
        self._later(doc)

    def slotDeletedDocument(self, doc):
        try:
            self._pending.discard(doc.Name)
            self._tidy.discard(doc.Name)
        except Exception:
            pass

    def _run(self, name):
        self._pending.discard(name)
        tidy = name in self._tidy
        self._tidy.discard(name)
        try:
            if name not in App.listDocuments():
                return
            doc = App.getDocument(name)
            if joints.assembly(doc) is None and not joints.joint_origins(doc):
                return
            if getattr(doc, "Recomputing", False):
                self._later(doc, tidy)
                return
            attach_views(doc)
            # Never inside a dialog's undo step (opening a step would close the dialog's:
            # what a dialog deletes is its own business) nor while one is pending.
            if tidy and (
                getattr(doc, "HasPendingTransaction", False) or Gui.Control.activeDialog()
            ):
                tidy = False
            if tidy:
                doc.openTransaction("Remove joints of deleted components")
                removed = joints.tidy(doc)
                if removed:
                    doc.commitTransaction()
                    preview.recompute(doc)
                else:
                    doc.abortTransaction()
                    try:
                        App.closeActiveTransaction(True)
                    except Exception:
                        pass
            for origin in joints.joint_origins(doc):
                if joints.joint_origin_owner(origin) is None:
                    continue
                joints.place_joint_origin(origin)
        except Exception as exc:
            warn("joints watch: %s" % exc)


_WATCH = {"observer": None}


def install():
    if _WATCH["observer"] is None:
        _WATCH["observer"] = Watch()
        App.addDocumentObserver(_WATCH["observer"])


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


class JointCommand(_Command):
    text = "Joint"
    tip = (
        "Joint two components: click a snap point on each (J). Rigid, Revolute, Slider, "
        "Cylindrical, Pin-Slot, Planar or Ball, with offsets, limits and an animated preview."
    )
    icon = "joint"

    def IsActive(self):
        return App.ActiveDocument is not None and len(joints.parts(App.ActiveDocument)) >= 2

    def run(self):
        if App.ActiveDocument is not None and len(joints.parts(App.ActiveDocument)) < 2:
            commands.tell("A joint needs two bodies or components in the design.")
            return
        _start(JointPanel)


class AsBuiltJointCommand(JointCommand):
    text = "As-built Joint"
    tip = (
        "Joint two components where they stand (nothing moves): pick them, the type and, "
        "for a moving joint, the position of its axis."
    )
    icon = "joint_asbuilt"

    def run(self):
        if App.ActiveDocument is not None and len(joints.parts(App.ActiveDocument)) < 2:
            commands.tell("An as-built joint needs two bodies or components in the design.")
            return
        _start(AsBuiltPanel)


class JointOriginCommand(_Command):
    text = "Joint Origin"
    tip = (
        "Put a joint origin on a component at a snap point, with offsets, angle and flip; "
        "joints can snap to it."
    )
    icon = "joint_origin"

    def IsActive(self):
        return App.ActiveDocument is not None and bool(joints.parts(App.ActiveDocument))

    def run(self):
        _start(JointOriginPanel)


class RigidGroupCommand(JointCommand):
    text = "Rigid Group"
    tip = "Lock two or more components together where they stand."
    icon = "rigid_group"

    def run(self):
        if App.ActiveDocument is not None and len(joints.parts(App.ActiveDocument)) < 2:
            commands.tell("A rigid group needs two bodies or components in the design.")
            return
        _start(RigidGroupPanel)


class DriveJointsCommand(_Command):
    text = "Drive Joints"
    tip = "Move a joint to an angle or a distance, with a slider and Animate."
    icon = "drive_joints"

    def IsActive(self):
        doc = App.ActiveDocument
        return doc is not None and any(joints.fusion_type(j) != "rigid" for j in joints.joints(doc))

    def run(self):
        doc = App.ActiveDocument
        if doc is None or not any(joints.fusion_type(j) != "rigid" for j in joints.joints(doc)):
            commands.tell("Make a joint with a motion (Revolute, Slider...) first.")
            return
        _start(DrivePanel)


class GroundCommand(_Command):
    text = "Ground / Unground"
    tip = "Hold the selected body or component in place (or free it again)."
    icon = "ground"

    def run(self):
        doc = App.ActiveDocument
        if doc is None:
            commands.tell("Open or start a design first.")
            return
        entries = _selection_entries(doc)
        if not entries:
            commands.tell("Select a body or component first (click it, or its browser row).")
            return
        toggle_ground(entries[0][0])


class CapturePositionCommand(_Command):
    text = "Capture Position"
    tip = "Record where the components stand now as a step in the timeline."
    icon = "position"

    def IsActive(self):
        doc = App.ActiveDocument
        return doc is not None and joints.assembly(doc) is not None and joints.positions_dirty(doc)

    def run(self):
        doc = App.ActiveDocument
        if doc is None or joints.assembly(doc) is None:
            commands.tell("Nothing to capture: there are no joints yet.")
            return
        if not joints.positions_dirty(doc):
            commands.tell("Nothing moved since the last position: nothing to capture.")
            return
        capture_position(doc)


class RevertPositionCommand(CapturePositionCommand):
    text = "Revert Position"
    tip = "Put the components back where the last captured position (or the joints) left them."
    icon = "position"

    def run(self):
        doc = App.ActiveDocument
        if doc is None or joints.assembly(doc) is None:
            commands.tell("Nothing to revert: there are no joints yet.")
            return
        if not joints.positions_dirty(doc):
            commands.tell("Nothing moved since the last position: nothing to revert.")
            return
        revert_position(doc)


def edit_joint(feature):
    _edit(JointPanel, feature)


def edit_joint_limits(feature):
    """Edit Joint Limits (browser right-click): the joint's dialog on its limits."""
    if getattr(feature, joints.TYPE_PROP, "") == "AsBuiltJoint":
        _edit(AsBuiltPanel, feature)  # its limits are in its one page
    else:
        _edit(JointPanel, feature, show_motion=True)


def edit_as_built(feature):
    _edit(AsBuiltPanel, feature)


def edit_joint_origin(feature):
    _edit(JointOriginPanel, feature)


def edit_rigid_group(feature):
    _edit(RigidGroupPanel, feature)


def edit_position(feature):
    """Double-click a captured position: the components go back to it."""
    doc = feature.Document
    if not commands.finish_open_dialog():
        return
    doc.openTransaction("Go to %s" % feature.Label)
    try:
        joints.apply_placements(doc, joints._json(feature, joints.PROPS["placements"]))
        joints.solve(doc)
        preview.recompute(doc)
    except Exception as exc:
        doc.abortTransaction()
        warn("Position: %s" % exc)
        return
    doc.commitTransaction()


def drive(joint):
    """Drive Joints on one joint (browser right-click)."""
    if not commands.finish_open_dialog():
        return None
    try:
        from .bodies_panel import _open

        return _open(DrivePanel, joint.Document, joint=joint)
    except Exception as exc:
        warn("Drive Joints: %s" % exc)
        return None


COMMANDS = {
    "SciForge_Joint": JointCommand,
    "SciForge_AsBuiltJoint": AsBuiltJointCommand,
    "SciForge_JointOrigin": JointOriginCommand,
    "SciForge_RigidGroup": RigidGroupCommand,
    "SciForge_DriveJoints": DriveJointsCommand,
    "SciForge_Ground": GroundCommand,
    "SciForge_CapturePosition": CapturePositionCommand,
    "SciForge_RevertPosition": RevertPositionCommand,
}
EDITORS = {
    "SciForge::Joint": edit_joint,
    "SciForge::AsBuiltJoint": edit_as_built,
    "SciForge::JointOrigin": edit_joint_origin,
    "SciForge::RigidGroup": edit_rigid_group,
    "SciForge::Position": edit_position,
}

try:
    install()
except Exception as _exc:  # never let an import fail the commands
    warn("joints watch unavailable: %s" % _exc)
