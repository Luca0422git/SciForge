# SPDX-License-Identifier: LGPL-2.1-or-later
"""INSERT > Hardware...: put a real-size screw, nut, washer, heat-set insert or magnet into
the design, and make the hole it needs, in one step (hardware.py does the work).

1. Pick what: Type (Screw / Nut / Washer / Heat-set insert / Magnet), its standard, Size
   and, for a screw, Length (the standard lengths).
2. Place on: click a round edge of the part (the rim of a hole: the part goes on its axis
   and takes the hole's size by itself, like Fusion's Insert Fastener with Size Automatic)
   or click a flat face where it should go. A face or edge selected before the command is
   taken at once. The part appears at once (a live preview), as its own component.
3. "Make the hole too" (on by default, off when the rim clicked already is a hole) drills
   the matching hole as a normal Hole step: a clearance hole with the counterbore or
   countersink of the head ("Head sunk in"), an insert's hole, a magnet's pocket. Fit and
   Hole depth set the clearance hole; Clearance widens a magnet's pocket. Flip turns the
   part round.

OK keeps everything as one undo step, Cancel or Esc removes it, Enter is OK. Problems are
said in the dialog, which then stays open. Double-click the Hardware step in the timeline
to change it later (its hole follows).
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, hardware, hole, log, preview, ui_icon_path, warn
from . import hardware_core as core
from . import hole_common as common
from .compat import QtCore, QtWidgets
from .taskui import DistanceField, Panel


def _pairs(rows):
    """(label, value) pairs for a drop-down from hardware_core's (value, label) rows."""
    return [(label, value) for value, label in rows]


WAITING = "Click a hole's rim (a round edge) or a flat face of the part."


def _safe(method):
    """Never let an exception out of a Qt signal handler."""

    def wrapper(self, *args):
        try:
            return method(self, *args)
        except Exception as exc:
            warn("Hardware: %s" % exc)
            try:
                self.message.setText("⚠ %s" % exc)
            except Exception:
                pass
        return None

    wrapper.__name__ = method.__name__
    return wrapper


class HardwarePanel(Panel):
    title = "Hardware"
    icon = "hardware"
    last = None
    remembered = {}  # the next insert of this session starts with the last one's choices

    def __init__(self, doc, feature=None, selection=None):
        super().__init__(doc, "Insert Hardware" if feature is None else "Edit Hardware")
        HardwarePanel.last = self
        self.escape = preview.EscapeCancels(self)
        self.undo_guard = preview.UndoCancels(self)
        self.enter = preview.EnterFinishes(self)
        self.target = feature
        self.editing = feature is not None
        self.pick = None
        self.error = ""
        self._quiet = False
        self.observer = None
        self.gate = None
        if feature is not None:
            try:
                Gui.Selection.clearSelection()
            except Exception:
                pass
            pick, self.options = hardware.read(feature)
            self.pick = pick
        else:
            self.options = core.with_defaults(dict(HardwarePanel.remembered))
        self._build_form()
        self._show_options()
        self._watch()
        if feature is None:
            self._start(selection)
        else:
            self._show_status_text()

    # -- form -----------------------------------------------------------------------------------
    def _build_form(self):
        form = self.layout
        self.kind = common.combo(_pairs(core.KINDS), self.options["kind"])
        self.kind.setObjectName("SciForgeHardware_type")
        form.addRow("Type", self.kind)
        self.standard = QtWidgets.QComboBox()
        self.standard.setObjectName("SciForgeHardware_standard")
        form.addRow("Standard", self.standard)
        self.size = QtWidgets.QComboBox()
        self.size.setObjectName("SciForgeHardware_size")
        form.addRow("Size", self.size)
        self.length = QtWidgets.QComboBox()
        self.length.setObjectName("SciForgeHardware_length")
        self.length_label = QtWidgets.QLabel("Length")
        form.addRow(self.length_label, self.length)
        self.place = common.SelectionField(self, "place", "Select a rim or a face")
        self.place.button.setToolTip(WAITING)
        form.addRow("Place on", self.place.widget)
        self.flip = QtWidgets.QCheckBox("Flip")
        self.flip.setObjectName("SciForgeHardware_flip")
        self.flip.setToolTip("Turn the part round on its axis")
        form.addRow("", self.flip)
        self.make_hole = QtWidgets.QCheckBox("Make the hole too")
        self.make_hole.setObjectName("SciForgeHardware_make_hole")
        self.make_hole.setToolTip(
            "Drill the hole this part needs as a Hole step in the part you clicked"
        )
        form.addRow("", self.make_hole)
        self.sink = QtWidgets.QCheckBox("Head sunk in")
        self.sink.setObjectName("SciForgeHardware_sink")
        self.sink.setToolTip(
            "The head goes into a counterbore (socket and button heads) or a countersink "
            "(countersunk heads)"
        )
        form.addRow("", self.sink)
        self.fit = common.combo(_pairs(core.FITS), self.options["fit"])
        self.fit.setObjectName("SciForgeHardware_fit")
        self.fit_label = QtWidgets.QLabel("Fit")
        form.addRow(self.fit_label, self.fit)
        self.hole_depth = common.combo(_pairs(core.HOLE_DEPTHS), self.options["hole_depth"])
        self.hole_depth.setObjectName("SciForgeHardware_hole_depth")
        self.hole_depth_label = QtWidgets.QLabel("Hole depth")
        form.addRow(self.hole_depth_label, self.hole_depth)
        self.clearance = DistanceField(self.options["clearance"], on_change=self._clearance_typed)
        self.clearance.widget.setObjectName("SciForgeHardware_clearance")
        self.clearance.widget.setToolTip("How much wider than the magnet its pocket is")
        self.clearance_label = QtWidgets.QLabel("Clearance")
        form.addRow(self.clearance_label, self.clearance.widget)
        self.hole_info = QtWidgets.QLabel("")
        self.hole_info.setObjectName("SciForgeHardware_hole_info")
        self.hole_info.setWordWrap(True)
        form.addRow("Hole", self.hole_info)
        self.name = QtWidgets.QLineEdit()
        self.name.setReadOnly(True)
        self.name.setObjectName("SciForgeHardware_name")
        form.addRow("Name", self.name)
        self.finish_layout()
        self.kind.currentIndexChanged.connect(self._kind_changed)
        self.standard.currentIndexChanged.connect(self._standard_changed)
        self.size.currentIndexChanged.connect(self._size_changed)
        self.length.currentIndexChanged.connect(self._changed)
        for box in (self.flip, self.make_hole, self.sink):
            box.toggled.connect(self._changed)
        self.fit.currentIndexChanged.connect(self._changed)
        self.hole_depth.currentIndexChanged.connect(self._changed)

    def _show_options(self):
        """Put self.options into the fields (no signals)."""
        o = self.options
        self._quiet = True
        try:
            common.set_combo(self.kind, o["kind"])
            common.fill_combo(self.standard, _pairs(core.standards(o["kind"])), o["standard"])
            common.fill_combo(
                self.size,
                [(core.size_label(o["standard"], s), s) for s in core.sizes(o["standard"])],
                o["size"],
            )
            lengths = core.lengths(o["standard"], o["size"])
            common.fill_combo(self.length, [("%g mm" % v, v) for v in lengths], o.get("length"))
            self.flip.setChecked(bool(o["flip"]))
            self.make_hole.setChecked(bool(o["make_hole"]))
            self.sink.setChecked(bool(o["sink_head"]))
            common.set_combo(self.fit, o["fit"])
            common.set_combo(self.hole_depth, o["hole_depth"])
            self.clearance.set_value(float(o["clearance"]))
        finally:
            self._quiet = False
        self._update_visibility()
        self._show_names()

    def _update_visibility(self):
        kind = self.options["kind"]
        screw = kind == "screw"
        hole_on = bool(self.options["make_hole"])
        shown = {
            (self.length, self.length_label): screw,
            (self.sink,): screw,
            (self.fit, self.fit_label): hole_on and kind in ("screw", "nut", "washer"),
            (self.hole_depth, self.hole_depth_label): hole_on and screw,
            (self.clearance.widget, self.clearance_label): hole_on and kind == "magnet",
        }
        for widgets, visible in shown.items():
            for widget in widgets:
                widget.setVisible(visible)

    def _show_names(self):
        try:
            self.name.setText(core.name(self.options))
        except Exception:
            self.name.setText("")
        self.hole_info.setText(self._hole_text())

    def _hole_text(self):
        try:
            want = core.hole_options(self.options)
        except core.HardwareError as exc:
            return str(exc)
        if want is None:
            return "None"
        if want["tap_type"] == "clearance":
            text = "Clearance %g mm" % core.clearance(self.options)
            if want["hole_type"] == "counterbore":
                text += ", counterbore %g x %g" % (want["cbore_diameter"], want["cbore_depth"])
            elif want["hole_type"] == "countersink":
                text += ", countersink %g x %g deg" % (want["csink_diameter"], want["csink_angle"])
            if want["extent"] == "all":
                return text + ", through all"
            return text + ", %g deep" % want["depth"]
        return "%g mm, %g deep, flat bottom" % (want["diameter"], want["depth"])

    def _collect(self):
        o = self.options
        o["kind"] = self.kind.currentData()
        o["standard"] = self.standard.currentData() or o["standard"]
        o["size"] = self.size.currentData() or o["size"]
        if core.has_length(o["standard"]) and self.length.currentData() is not None:
            o["length"] = float(self.length.currentData())
        o["flip"] = self.flip.isChecked()
        o["make_hole"] = self.make_hole.isChecked()
        o["sink_head"] = self.sink.isChecked()
        o["fit"] = self.fit.currentData()
        o["hole_depth"] = self.hole_depth.currentData()
        o["clearance"] = abs(float(self.clearance.value()))

    # -- choices --------------------------------------------------------------------------------
    @_safe
    def _kind_changed(self, *_):
        if self._quiet:
            return
        kind = self.kind.currentData()
        self.options = core.change_standard(self.options, core.standards(kind)[0][0])
        self._show_options()
        self._rebuild()

    @_safe
    def _standard_changed(self, *_):
        if self._quiet:
            return
        self.options = core.change_standard(self.options, self.standard.currentData())
        self._show_options()
        self._rebuild()

    @_safe
    def _size_changed(self, *_):
        if self._quiet:
            return
        o = self.options
        o["size"] = self.size.currentData()
        if core.has_length(o["standard"]):
            o["length"] = core.fit_length(o["standard"], o["size"], o.get("length"))
        self._show_options()
        self._rebuild()

    @_safe
    def _changed(self, *_):
        if self._quiet:
            return
        self._collect()
        self._update_visibility()
        self._rebuild()

    @_safe
    def _clearance_typed(self, _value):
        if self._quiet:
            return
        self._collect()
        self._rebuild()

    # -- placing --------------------------------------------------------------------------------
    def activate(self, name):
        self.place.set_active(True)

    def clear_field(self, name):
        """The x of Place on: the part goes away until a new place is clicked."""
        if self.editing:
            self.message.setText("Click a new place for it (a rim or a face).")
            return
        if self.target is not None:
            try:
                hardware.remove(self.target)
            except Exception as exc:
                warn("Hardware: %s" % exc)
            self.target = None
            self.schedule()
        self.pick = None
        self.place.set_text("")
        self.message.setText("")

    def allow(self, obj, name):
        """What lights up and can be clicked: faces and edges of the parts' solids, never the
        hardware itself."""
        if not name.startswith(("Face", "Edge")):
            return False
        body = hole.owner_body(obj) if obj.TypeId != "PartDesign::Body" else obj
        if body is None:
            return False
        try:
            if any(hardware.is_hardware(o) for o in body.Group):
                return False
        except Exception:
            return False
        return True

    def _watch(self):
        panel = self

        class Observer:
            def addSelection(self, doc, obj, sub, pnt):
                # Deferred: nothing is built inside FreeCAD's click handling.
                QtCore.QTimer.singleShot(30, panel._selection_changed)

        self.observer = Observer()
        Gui.Selection.addObserver(self.observer)
        self.gate = common.install_gate(self)

    def _unwatch(self):
        if self.observer is not None:
            try:
                Gui.Selection.removeObserver(self.observer)
            except Exception:
                pass
            self.observer = None
        common.remove_gate(self.gate)
        self.gate = None

    def _start(self, selection=None):
        self.activate("place")
        found = list(selection) if selection is not None else []
        try:
            Gui.Selection.clearSelection()
        except Exception:
            pass
        for obj, short, point in found:
            if short.startswith(("Face", "Edge")) and self.allow(obj, short):
                self._clicked(obj, short, point)
                break
        if self.target is not None:
            self._timer.stop()
            self._recompute()

    @_safe
    def _selection_changed(self):
        if self._closed:
            return
        found = common.picks(self.doc)
        if not found:
            return
        Gui.Selection.clearSelection()
        for obj, short, point in found:
            if short.startswith(("Face", "Edge")):
                self._clicked(obj, short, point)
                break

    def _own_hole(self):
        return hardware.hole_of(self.target) if self.target is not None else None

    def _clicked(self, obj, short, point):
        if not self.allow(obj, short):
            return
        own = self._own_hole()
        try:
            place = hardware.spot(obj, short, point)
        except core.HardwareError as exc:
            self.message.setText("⚠ %s" % exc)
            return
        if own is not None and obj is own:
            # A click on this part's own hole (the preview): the same face of the part
            # before that hole, at the place clicked (its rim: the hole's axis).
            base = own.BaseFeature
            body = place["body"]
            local = hole.to_local(body, place["face_point"])
            rotation = body.getGlobalPlacement().Rotation.inverted()
            name = hole.base_face_at(base, local, rotation.multVec(place["normal"]))
            if name is None:
                return
            obj, short, point = base, name, place["center"]
            place = dict(place, rim=False, is_hole=False)
        elif place["rim"] and place["is_hole"]:
            self._fit_existing_hole(place["diameter"])
        self.pick = (obj, short, App.Vector(point) if point is not None else None)
        if place["rim"]:
            self.pick = (obj, short, App.Vector(place["center"]))
        self.place.set_text("%s (%s)" % (short, place["body"].Label))
        self._rebuild()

    def _fit_existing_hole(self, diameter):
        """A rim of a hole that is already there: no second hole, and the part takes the
        hole's size (Fusion's Size: Automatic)."""
        o = self.options
        size = core.size_for_hole(o["standard"], diameter, current=o["size"])
        if size is not None and size != o["size"]:
            o["size"] = size
            if core.has_length(o["standard"]):
                o["length"] = core.fit_length(o["standard"], size, o.get("length"))
        o["make_hole"] = False
        if o["kind"] == "screw":
            o["sink_head"] = core.head_fits_rim(o["standard"], o["size"], diameter)
        self._show_options()

    # -- building -------------------------------------------------------------------------------
    def _rebuild(self):
        """Make or change the part (and its hole) for the options and place now."""
        self._show_names()
        if self.pick is None:
            return
        try:
            if self.target is None:
                self.target = hardware.make(self.doc, self.pick, self.options)
            else:
                hardware.update(self.target, pick=self.pick, options=self.options)
            self.error = ""
        except core.HardwareError as exc:
            self.error = str(exc)
        except Exception as exc:
            self.error = "The part cannot go there: %s" % exc
        self._show_status_text()
        self.schedule()

    def _show_status_text(self):
        if self.error:
            self.message.setText("⚠ " + self.error)
        else:
            self.message.setText("")
        if self.pick is not None:
            self.place.set_text("%s (%s)" % (self.pick[1], self.pick[0].Label))

    def _recompute(self):
        if self._closed:
            return
        try:
            preview.recompute(self.doc)
            text = self.problem()
            if text:
                self.message.setText("⚠ " + text)
            else:
                self._show_status_text()
        except Exception as exc:
            try:
                self.message.setText(str(exc))
            except RuntimeError:
                pass

    def problem(self):
        if self.error:
            return self.error
        for obj in (self.target, self._own_hole()):
            if obj is None:
                continue
            state = list(getattr(obj, "State", []))
            if "Invalid" in state or "Error" in state:
                return "%s: %s" % (obj.Label, obj.getStatusString())
        own = self._own_hole()
        if own is not None and hole.misses(own):
            return "The hole misses the part: click a face of the part."
        return ""

    def feature(self):
        return self.target

    # -- OK / Cancel ----------------------------------------------------------------------------
    def accept(self):
        if self._closed:
            return True
        if self.target is None:
            self.message.setText("⚠ " + WAITING)
            return False
        self._timer.stop()
        try:
            preview.recompute(self.doc)
        except Exception as exc:
            warn("Hardware: %s" % exc)
        text = self.problem()
        if text:
            self.message.setText("⚠ " + text)
            return False
        # The next insert starts with this part's choices; what a click decided by itself
        # (no second hole on a rim, the head's seat) and Flip start fresh.
        HardwarePanel.remembered = {
            k: v for k, v in self.options.items() if k not in ("flip", "make_hole", "sink_head")
        }
        self.cleanup()
        preview.end_transaction(self.doc)
        self._close()
        log("%s done" % self.title)
        return True

    def reject(self):
        if self._closed:
            return True
        self._timer.stop()
        body = self.pick[0] if self.pick is not None else None
        self.cleanup()
        preview.end_transaction(self.doc, abort=True)
        try:
            preview.recompute(self.doc)
            if body is not None:
                hole.show_tip(hole.owner_body(body))
        except Exception:
            pass
        self._close()
        return True

    def cleanup(self):
        self._unwatch()
        for guard in (self.escape, self.undo_guard, self.enter):
            try:
                guard.remove()
            except Exception:
                pass
        super().cleanup()


class HardwareCommand:
    def GetResources(self):
        return {
            "MenuText": "Hardware...",
            "ToolTip": "Insert a real-size screw, nut, washer, heat-set insert or magnet as "
            "its own component, on a hole's rim or a face, and make the hole it needs",
            "Pixmap": ui_icon_path("hardware"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            found = common.picks(App.ActiveDocument)  # a rim or face picked first
            if not commands.finish_open_dialog():
                return
            Gui.Control.showDialog(HardwarePanel(App.ActiveDocument, selection=found))
            log("hardware started")
        except Exception as exc:
            warn("Hardware failed to start: %s" % exc)


def edit(feature):
    """Open the Hardware dialog on an existing part (timeline double-click)."""
    try:
        if Gui.Control.activeDialog() and not commands.finish_open_dialog():
            return
        _keep_part_active(feature)
        Gui.Control.showDialog(HardwarePanel(feature.Document, feature=feature))
    except Exception as exc:
        warn("could not edit %s: %s" % (feature.Label, exc))


def _keep_part_active(feature):
    """The timeline makes the component of a step being edited the active one; for a
    hardware part that would leave its component active afterwards (new sketches would go
    into the screw). The part it was put into stays the active one (Guess)."""
    try:
        from . import bodies, components

        pick = hardware.pick_of(feature)
        body = bodies.body_of(pick[0]) if pick is not None else None
        if body is not None:
            components.activate_body(body)
    except Exception as exc:
        warn("Hardware: %s" % exc)


COMMANDS = {"SciForge_Hardware": HardwareCommand}
EDITORS = {"SciForge::" + hardware.KIND: edit}
