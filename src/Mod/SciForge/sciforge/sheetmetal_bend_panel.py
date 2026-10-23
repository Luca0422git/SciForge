# SPDX-License-Identifier: LGPL-2.1-or-later
"""The dialog base of the sm-more SHEET METAL tools (Bend, Hem, Join by Bend, Corner Closure,
Lofted Flange, sheet metal Fillet / Chamfer): Fusion's selection boxes, the value rows, a live
preview of the step on the see-through part, OK / Cancel / Esc, editing a step again.

A subclass names its boxes (BOXES: name, label, empty text, several picks or one), builds its
value rows with add_combo / add_length / add_angle / add_check / add_number, and implements:
    accept_pick(box, obj, short)   may this click go into the box?
    ready()                        enough picked to build?
    make_feature(options)          the step, built the first time the preview can be made
    apply_feature(options)         the step's values changed
    read_feature(feature)          (options) of a step being edited, filling self.picks
    hint()                         what to do next (shown under the boxes)
Picking works like inside a Fusion command: a click on what the blue box takes adds it, a click
on a picked one drops it; a box that takes one pick hands the clicks to the next box once
filled. Problems are shown in the dialog (OK waits for a fix), never in the Report view.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import bodies, commands, hole_common, log, pickpanel, preview, sheetmetal, warn
from . import sheetmetal_bend as sb
from .compat import QtCore, QtWidgets
from .taskui import DistanceField, ValueBoxes

HELP_STYLE = "color: #9aa4b1;"


def sheet_metal_body(preferred=None):
    """The sheet metal body a tool works on: the preferred or active one when it is sheet
    metal, else the first sheet metal body of the design (None: there is none)."""
    doc = App.ActiveDocument
    if doc is None:
        return None
    found = []
    for body in (preferred, commands.active_body()):
        if body is not None and sheetmetal.is_sheet_metal_body(body) and body not in found:
            found.append(body)
    try:
        used = bodies.consumed(doc)
    except Exception:
        used = set()
    found += [
        b for b in sheetmetal.sheet_metal_bodies(doc) if b not in found and b.Name not in used
    ]
    for body in found:
        tip = body.Tip
        if tip is not None and not tip.Shape.isNull() and tip.Shape.Solids:
            return body
    return None


def solid_tip(body):
    tip = body.Tip if body is not None else None
    if tip is None or tip.Shape.isNull() or not tip.Shape.Solids:
        return None
    return tip


def rooted(obj, short):
    """(top object, "Body.Feature.Edge3") for an element of a body inside a component: FreeCAD
    keeps a selection made with the component's path apart from one made on the feature
    alone, and a click in the 3D view always carries the path (the picks then looked
    dropped). Outside components: (obj, short) as they are."""
    try:
        chain = [obj]
        parent = obj.getParentGeoFeatureGroup()
        while parent is not None and len(chain) < 16:
            chain.insert(0, parent)
            parent = parent.getParentGeoFeatureGroup()
    except Exception:
        return obj, short
    if len(chain) <= 2:
        return obj, short
    return chain[0], ".".join(o.Name for o in chain[1:]) + "." + short


class SmPanel(pickpanel.PickPanel):
    title = "Sheet Metal"
    icon = None
    BOXES = []  # (name, label, empty text, multi)
    NEEDS_BASE = True
    last = None

    def __init__(self, doc, feature=None, body=None):
        super().__init__(doc, self.title if feature is None else "Edit " + self.title)
        type(self).last = self
        SmPanel.last = self
        self.target = feature
        self.editing = feature is not None
        self.picks = {b[0]: [] for b in self.BOXES}
        self.boxes = {}
        self.fields = {}
        self.number_fields = {}
        self.rows = {}
        self.error = None
        self.active = self.BOXES[0][0] if self.BOXES else None
        self.value_boxes = ValueBoxes(self)
        self.handles = {}
        if feature is not None:
            self.body = bodies.body_of(feature)
            self.base = getattr(feature, "BaseFeature", None)
            self.options = self.read_feature(feature)
        else:
            self.body = body
            self.base = solid_tip(body)
            self.options = self.default_options()
        self._build()
        self.finish_layout()
        try:
            self._start()
        except Exception as exc:  # never leave a half-open dialog without a reason
            self.say("⚠ %s" % exc)
            warn("%s could not start picking: %s" % (self.title, exc))

    # -- what subclasses give ---------------------------------------------------------------
    def default_options(self):
        return {}

    def build_fields(self):
        pass

    def accept_pick(self, box, obj, short):
        return False

    def ready(self):
        return all(self.picks[b[0]] for b in self.BOXES)

    def make_feature(self, options):
        raise NotImplementedError

    def apply_feature(self, options):
        raise NotImplementedError

    def read_feature(self, feature):
        return {}

    def hint(self):
        return ""

    def check(self, options):
        """Raise sb.SheetMetalError for values that cannot work (before building)."""

    def fields_changed(self, key):
        """A value row changed (show / hide rows here)."""

    # -- layout -----------------------------------------------------------------------------
    def _build(self):
        for name, label, empty, _multi in self.BOXES:
            field = hole_common.SelectionField(self, name, empty)
            self.boxes[name] = field
            self.layout.addRow(label, field.widget)
        self.help = QtWidgets.QLabel("")
        self.help.setWordWrap(True)
        self.help.setStyleSheet(HELP_STYLE)
        self.layout.addRow(self.help)
        self.build_fields()
        self._refresh_boxes()

    def _row(self, key, label, widget):
        text = QtWidgets.QLabel(label)
        self.layout.addRow(text, widget)
        self.rows[key] = (widget, text)
        return widget

    def add_combo(self, key, label, items, tip=""):
        box = pickpanel.combo(items, self.options.get(key))
        box.setToolTip(tip)
        box.currentIndexChanged.connect(lambda *_a, k=key: self._changed(k))
        self.fields[key] = box
        return self._row(key, label, box)

    def add_length(self, key, label, tip="", minimum=0.0):
        field = DistanceField(
            float(self.options.get(key) or 0.0), "mm", on_change=lambda _v, k=key: self._changed(k)
        )
        field.widget.setProperty("minimum", minimum)
        field.widget.setToolTip(tip)
        self.fields[key] = field
        self.number_fields[key] = field
        self._row(key, label, field.widget)
        return field

    def add_angle(self, key, label, tip=""):
        field = DistanceField(
            float(self.options.get(key) or 0.0), "deg", on_change=lambda _v, k=key: self._changed(k)
        )
        field.widget.setToolTip(tip)
        self.fields[key] = field
        self.number_fields[key] = field
        self._row(key, label, field.widget)
        return field

    def add_number(self, key, label, tip="", lo=0.0, hi=1e6, decimals=3):
        box = QtWidgets.QDoubleSpinBox()
        box.setDecimals(decimals)
        box.setRange(lo, hi)
        box.setValue(float(self.options.get(key) or 0.0))
        box.setToolTip(tip)
        box.valueChanged.connect(lambda *_a, k=key: self._changed(k))
        self.fields[key] = box
        self.number_fields[key] = box
        self._row(key, label, box)
        return box

    def add_check(self, key, label, tip=""):
        box = QtWidgets.QCheckBox()
        box.setChecked(bool(self.options.get(key)))
        box.setToolTip(tip)
        box.toggled.connect(lambda *_a, k=key: self._changed(k))
        self.fields[key] = box
        return self._row(key, label, box)

    def show_row(self, key, shown):
        widget, text = self.rows[key]
        widget.setVisible(shown)
        text.setVisible(shown)

    def value(self, key):
        widget = self.fields[key]
        if isinstance(widget, DistanceField):
            return widget.value()
        if isinstance(widget, QtWidgets.QComboBox):
            return widget.currentData()
        if isinstance(widget, QtWidgets.QCheckBox):
            return widget.isChecked()
        if isinstance(widget, QtWidgets.QDoubleSpinBox):
            return widget.value()
        return None

    def set_value(self, key, value):
        widget = self.fields[key]
        if isinstance(widget, DistanceField):
            widget.set_value(value)
        elif isinstance(widget, QtWidgets.QComboBox):
            hole_common.set_combo(widget, value)
        elif isinstance(widget, QtWidgets.QCheckBox):
            widget.setChecked(bool(value))
        elif isinstance(widget, QtWidgets.QDoubleSpinBox):
            widget.setValue(float(value))

    def collect(self):
        opts = dict(self.options)
        for key in self.fields:
            opts[key] = self.value(key)
        return opts

    def _changed(self, key):
        if self._closed:
            return
        try:
            self.fields_changed(key)
        except Exception as exc:
            warn("%s: %s" % (self.title, exc))
        self.schedule()

    # -- starting -----------------------------------------------------------------------------
    def _start(self):
        if self.NEEDS_BASE and self.base is None:
            self.say(
                "⚠ %s needs a sheet metal body: make one with Flange first (SHEET METAL tab)."
                % self.title
            )
            return
        self.start_picking()
        self._picks_updated(schedule=False)
        if self.target is not None:
            self.show_preview(True)
        if self.ready():
            self.schedule()

    # -- picks (PickPanel calls these) ------------------------------------------------------
    def _box_spec(self, name):
        for spec in self.BOXES:
            if spec[0] == name:
                return spec
        return None

    def allow(self, obj, short):
        if obj is None or self.active is None:
            return False
        for box in self.picks:  # a picked element can always be clicked to drop it
            if any(o is obj and s == short for o, s, _p in self.picks[box]):
                return True
        try:
            return bool(self.accept_pick(self.active, obj, short))
        except Exception:
            return False

    def picks_changed(self, added, dropped):
        changed = False
        if added and dropped:
            # one click either adds a pick or drops one; both at once is FreeCAD replacing
            # the selection (a click inside a component after a pick made on its feature):
            # the old picks stay
            dropped = []
        for obj, short, _point in dropped:
            for box in self.picks:
                before = len(self.picks[box])
                self.picks[box] = [
                    p for p in self.picks[box] if not (p[0] is obj and p[1] == short)
                ]
                if len(self.picks[box]) != before:
                    changed = True
                    self.active = box
        for obj, short, point in added:
            box = self.active
            if box is None or not self.accept_pick(box, obj, short):
                continue
            spec = self._box_spec(box)
            entry = (obj, short, App.Vector(point) if point is not None else None)
            if spec[3]:
                self.picks[box].append(entry)
            else:
                self.picks[box] = [entry]
                self._next_box()
            changed = True
        if changed:
            self._picks_updated(schedule=False)
        return changed

    def _next_box(self):
        names = [b[0] for b in self.BOXES]
        index = names.index(self.active)
        for name in names[index + 1 :] + names[:index]:
            if not self.picks[name]:
                self.active = name
                break

    def shown(self):
        grouped = []
        for box in self.picks:
            for obj, short, _p in self.picks[box]:
                obj, short = rooted(obj, short)
                for entry in grouped:
                    if entry[0] is obj:
                        if short not in entry[1]:
                            entry[1].append(short)
                        break
                else:
                    grouped.append((obj, [short]))
        return grouped

    def activate(self, name):
        self.active = name
        self._refresh_boxes()

    def clear_field(self, name):
        self.picks[name] = []
        self.active = name
        self._sync()
        self._picks_updated()

    def _refresh_boxes(self):
        for name, field in self.boxes.items():
            field.set_active(name == self.active)
            count = len(self.picks.get(name, []))
            spec = self._box_spec(name)
            if count == 0:
                field.set_text("")
            elif spec[3]:
                field.set_text("%d selected" % count)
            else:
                field.set_text("1 selected")

    def _picks_updated(self, schedule=True):
        self._refresh_boxes()
        try:
            self.help.setText(self.hint())
        except Exception:
            pass
        if schedule:
            self.schedule()

    # -- preview ----------------------------------------------------------------------------
    def _preview(self):
        if self._closed:
            return
        if self.NEEDS_BASE and self.base is None:
            return
        opts = self.collect()
        if not self.ready():
            self.error = None
            if self.target is not None and not self.editing:
                target, self.target = self.target, None
                self._looks.restore()
                self._ghost = False
                self.drop_preview(target)
                self.quiet_recompute()
                self.prepare_display()
            self.show_preview(False)
            self.show_status()
            return
        try:
            self.check(opts)
        except (sb.SheetMetalError, ValueError) as exc:
            self.error = str(exc)
            self.show_status()
            return
        self.error = None
        if self.target is None:
            self.target = self.make_feature(opts)
        else:
            self.apply_feature(opts)
        self.quiet_recompute()
        self.show_preview(True)
        self.after_preview()
        self.show_status()

    def drop_preview(self, target):
        bodies.remove_step(target)

    def after_preview(self):
        """The preview was rebuilt (handles can follow it here)."""

    def show_status(self):
        if self.NEEDS_BASE and self.base is None:
            return
        if self.error:
            self.say("⚠ " + self.error)
            return
        text = preview.failure(self.target) if self.target is not None else ""
        if text:
            self.say("⚠ " + text)
            return
        self.say("")

    # -- OK / Cancel ------------------------------------------------------------------------
    def accept(self):
        try:
            self._timer.stop()
            if self.NEEDS_BASE and self.base is None:
                return False
            if not self.ready():
                self.say("⚠ " + (self.hint() or "Pick what the boxes ask for first."))
                return False
            self._preview()
            obj = self.target
            if self.error or obj is None:
                self.show_status()
                return False
            state = list(obj.State)
            if "Invalid" in state or "Error" in state or obj.Shape.isNull():
                self.show_status()
                return False
            self.finished(obj)
            return self.finish_ok()
        except Exception as exc:
            self.say("⚠ %s" % exc)
            return False

    def finished(self, obj):
        """The step is good and the dialog closes with OK."""

    def cleanup(self):
        for handle in list(self.handles.values()):
            try:
                handle.remove()
            except Exception:
                pass
        self.handles = {}
        try:
            self.value_boxes.discard()
        except Exception:
            pass
        super().cleanup()


# -- starting a command ------------------------------------------------------------------------
def start(panel_class, needs_sheet=True, label=""):
    """Open panel_class on the sheet metal body (the selected or active one)."""
    try:
        preferred = pickpanel.selected_body()
        if not commands.finish_open_dialog():
            return None
        doc = App.ActiveDocument
        if doc is None:
            return None
        body = sheet_metal_body(preferred)
        if needs_sheet and body is None:
            commands.tell(
                "%s needs a sheet metal body: make one with Flange first (SHEET METAL tab)."
                % (label or panel_class.title)
            )
            return None
        if body is not None:
            pickpanel.activate(body)
        panel = panel_class(doc, body=body)
        Gui.Control.showDialog(panel)
        log("%s started" % panel_class.title)
        return panel
    except Exception as exc:
        warn("%s could not start: %s" % (panel_class.title, exc))
        return None


def edit(panel_class, obj):
    """Timeline double-click: the dialog on the existing step."""
    try:
        if Gui.Control.activeDialog() and not commands.finish_open_dialog():
            return
        Gui.Control.showDialog(panel_class(obj.Document, feature=obj))
    except Exception as exc:
        warn("could not edit %s: %s" % (obj.Label, exc))


class StepViewProvider:
    """View provider of the sm-more steps (each module subclasses it with its icon and
    editor; saved in files as "sciforge.<module>.<class>": never rename)."""

    ICON = "sm_bend"

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        from . import ui_icon_path

        return ui_icon_path(self.ICON)

    def edit(self, obj):
        pass

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return None
        QtCore.QTimer.singleShot(0, lambda o=vobj.Object: self.edit(o))
        return True

    def unsetEdit(self, vobj, mode=0):
        return None

    def doubleClicked(self, vobj):
        self.edit(vobj.Object)
        return True

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def register_kinds(kinds, params=None):
    """Timeline titles and icons of the steps ({SciForgeType: (title, icon)}) and their
    Change Parameters rows, added at import of the *_ui.py modules."""
    try:
        import re

        from . import timeline_core

        for sciforge_type, (title, icon) in kinds.items():
            key = re.sub(r"(?<!^)(?=[A-Z])", "_", sciforge_type).lower()
            timeline_core.KINDS[key] = (title, icon)
            timeline_core.KIND_BY_SCIFORGE_TYPE[sciforge_type] = key
    except Exception as exc:
        warn("sheet metal timeline kinds: %s" % exc)
    if params:
        try:
            from . import parameters

            parameters.SCIFORGE_PROPS.update(params)
        except Exception as exc:
            warn("sheet metal parameters: %s" % exc)
