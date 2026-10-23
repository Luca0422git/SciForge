# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fillet (F) and Chamfer with Fusion's dialogs.

Picking works like inside a Fusion command:
  * click edges in the 3D view to add them, click a picked one again to drop it
    (no Ctrl needed; clicking empty space does not lose the picks);
  * click a face to round every sharp edge around it;
  * click a feature in the timeline to round the edges that feature made;
  * edges tangent to a picked edge are picked with it (Tangent Chain; it can be turned off);
  * press F with edges already selected and the fillet starts at once.
While picking, the part before the fillet is shown see-through with the picks
highlighted, and the result is previewed solid on top. A blue arrow on the first
edge drags the radius (chamfer: the distance; two arrows for two distances).
A size dragged or typed past what fits stops at the largest size that works (Luca,
2026-10-21; Fusion refuses it instead), and the dialog says so: "Largest that fits here: 3.47
mm" (value_limits.py). A size from a formula is not rewritten: it is reported in the dialog,
with that limit, and OK waits for a fix. Nothing is printed to the Report view.

Fusion's selection box has rows ("+" adds one): each row is a selection set with its own
size and type, one step in the timeline, one undo step. The Fillet dialog also has
Fusion's Type (Fillet / Rule Fillet / Full Round Fillet), Radius Type (Constant / Chord
Length / Variable with radius points) and Tangent Chain on/off; the Chamfer dialog has
chamfer sets. A plain fillet / chamfer (one row, one constant size, Tangent Chain on) is
FreeCAD's PartDesign::Fillet / Chamfer (refined), so Press Pull's fillet editing
(presspull_core.owning_fillet) keeps working on it; anything more is SciForge's own step
(fillet_sets.py): the dialog turns FreeCAD's step into SciForge's the moment it is needed.
"""

import contextlib
import copy
import math
import time

import FreeCAD as App
import FreeCADGui as Gui

from . import blend, commands, fillet_core as core, fillet_sets, log, shape_checks, ui_icon
from . import ui_icon_path, value_limits, warn
from .blend_field import SaveFinishes, ValueField
from .compat import QtCore, QtWidgets
from . import taskui
from .taskui import ArrowDragger, Panel, ValueBoxes, _end_transaction, handle_size_at

GHOST = 75  # transparency (%) of the part before the blend while the preview is shown
MIN_DRAG = 0.1  # mm: dragging an arrow back through its edge stops here (and it shows "mm")
# dialog value -> property of FreeCAD's feature that holds its formula
PROPS = {
    "radius": "Radius",
    "distance": "Size",
    "distance2": "Size2",
    "angle": "Angle",
}
NAMES = {
    "radius": "Radius",
    "chord": "Chord Length",
    "start": "Start Radius",
    "end": "End Radius",
    "distance": "Distance",
    "distance2": "Distance 2",
    "angle": "Angle",
}
GREEDY = 1  # FreeCAD selection style where a click toggles a pick, like in Fusion's commands
NORMAL = 0
PICK_HELP = (
    "Click edges or faces of the part (or a feature in the timeline).\n"
    "Click a pick again to drop it."
)
RULE_HELP = (
    "Click faces of the part or a feature in the timeline: every edge of them is rounded, "
    "also edges a later change adds (Rule)."
)
ROUND_HELP = (
    "Click the face to round: the top of a rib or a wall. Its two side faces are found by "
    "themselves."
)
VARIABLE_HELP = (
    "Click on the picked edge to add a radius point there (or Add Point). ✕ drops the edge."
)
CLICK_SECONDS = 2.0  # a press on a Variable edge counts as "add a point" for this long


@contextlib.contextmanager
def quiet_errors():
    """While previewing, a failing step is explained in the dialog (Fusion does that)
    instead of in the Report view, the notification pop-ups and the console."""
    muted = []
    try:
        for name in App.Console.GetObservers():
            for kind in ("Err", "Wrn"):
                try:
                    if App.Console.GetStatus(name, kind):
                        App.Console.SetStatus(name, kind, False)
                        muted.append((name, kind))
                except Exception:
                    pass
    except Exception:
        pass
    try:
        yield
    finally:
        for name, kind in muted:
            try:
                App.Console.SetStatus(name, kind, True)
            except Exception:
                pass


def solid_base(body):
    """The feature a new fillet builds on: the body's current end, if it is a solid."""
    if body is None:
        return None
    tip = body.Tip
    if tip is None or not hasattr(tip, "Shape") or tip.Shape.isNull() or not tip.Shape.Solids:
        return None
    return tip


def _resolve(sel):
    """[(object, short element name)] of a selection entry ("" for a whole object)."""
    found = []
    subs = [s for s in sel.SubElementNames if s] or [""]
    for name in subs:
        found.append((sel.Object, name.split(".")[-1] if name else ""))
    return found


def picks_from_selection(body, info, base):
    """What is selected now, as refs on `base` (Fusion: F with edges already selected).
    Edges/faces of another step are matched by their geometry. A whole feature that is
    selected is not a pick: the timeline selects the item it was right-clicked on (to roll
    the marker there, say), and F then rounded every edge that feature made. Inside the
    dialog a click on a timeline feature still adds its edges."""
    refs = []
    if base is None or info is None:
        return refs
    for sel in Gui.Selection.getSelectionEx():
        for obj, name in _resolve(sel):
            if obj is None or not name:
                continue
            if obj.Name != base.Name:
                name = _match(obj, name, info)
            if name and info.pickable(name) and name not in refs:
                refs.append(name)
    return refs


def _match(obj, name, info):
    """Name of the same edge/face in info's shape (picked on another feature's shape)."""
    try:
        item = obj.Shape.getElement(name)
    except Exception:
        return None
    if name.startswith("Edge"):
        key = blend._edge_key(item)
        for i, edge in enumerate(info.edges, start=1):
            if blend._edge_key(edge) == key:
                return "Edge%d" % i
    elif name.startswith("Face"):
        for i, face in enumerate(info.faces, start=1):
            if (
                abs(face.Area - item.Area) < 1e-6 * max(1.0, item.Area)
                and (face.CenterOfMass - item.CenterOfMass).Length < 1e-5
            ):
                return "Face%d" % i
    return None


def _combo(items, current=0):
    """Combo box; items are (label, value, enabled, tooltip). Disabled items are kinds
    Fusion has that SciForge cannot build yet: shown greyed with the reason."""
    box = QtWidgets.QComboBox()
    for label, value, enabled, tip in items:
        box.addItem(label, value)
        index = box.count() - 1
        if tip:
            box.setItemData(index, tip, QtCore.Qt.ToolTipRole)
        if not enabled:
            item = box.model().item(index)
            if item is not None:
                item.setEnabled(False)
    box.setCurrentIndex(current)
    return box


def _select(box, value):
    """Show `value` in a combo without running its change handler."""
    index = box.findData(value)
    if index >= 0 and index != box.currentIndex():
        box.blockSignals(True)
        box.setCurrentIndex(index)
        box.blockSignals(False)


class _Observer:
    """Selection events only queue work; the panel handles them a moment later, outside
    FreeCAD's click handling (feature guide rule 2)."""

    def __init__(self, panel):
        self.panel = panel

    def addSelection(self, doc, obj, sub, pnt):
        self.panel._selection_event(False)

    def removeSelection(self, doc, obj, sub):
        self.panel._selection_event(False)

    def setSelection(self, doc):
        self.panel._selection_event(False)

    def clearSelection(self, doc):
        self.panel._selection_event(True)


def _alive(obj):
    """False for None and for objects an undo (or a closed document) took away."""
    if obj is None:
        return False
    try:
        return (
            obj.isAttachedToDocument() if hasattr(obj, "isAttachedToDocument") else bool(obj.Name)
        )
    except Exception:
        return False


def _nodes(root, type_name):
    """Every Coin node of a type below `root` (pivy)."""
    from pivy import coin

    search = coin.SoSearchAction()
    search.setType(getattr(coin, type_name).getClassTypeId())
    search.setInterest(coin.SoSearchAction.ALL)
    search.setSearchingAll(True)
    search.apply(root)
    paths = search.getPaths()
    return [paths[i].getTail() for i in range(paths.getLength())]


class _Looks:
    """Field changes on Coin nodes, remembered so restore() puts every old value back."""

    def __init__(self):
        self.saved = []  # (node, field name, old value or values)
        self.tags = set()
        # The nodes belong to FreeCAD's view providers, which may delete them (e.g. when a
        # recompute rebuilds a part's display). A Coin reference keeps each one alive until
        # restore(): writing to a deleted node crashes FreeCAD.
        self.held = []

    def done(self, tag):
        """True if `tag` was applied already (and marks it applied)."""
        if tag in self.tags:
            return True
        self.tags.add(tag)
        return False

    def set(self, node, field, value):
        if not any(node is n for n in self.held):
            node.ref()
            self.held.append(node)
        fld = getattr(node, field)
        if hasattr(fld, "getNum"):  # a multi-value field (per-face colours)
            old = [fld[i] for i in range(fld.getNum())]
        else:
            old = fld.getValue()
        self.saved.append((node, field, old))
        fld.setValue(value)

    def restore(self):
        for node, field, old in reversed(self.saved):
            try:
                fld = getattr(node, field)
                if isinstance(old, list):
                    fld.setValues(0, len(old), old)
                    fld.setNum(len(old))
                else:
                    fld.setValue(old)
            except Exception:
                pass
        for node in self.held:
            try:
                node.unref()
            except Exception:
                pass
        self.held = []
        self.saved = []
        self.tags = set()


class _DocumentWatch:
    """Undo/redo or closing the document while the dialog is open: FreeCAD lets Ctrl+Z run
    and it takes the dialog's own unfinished step away. The dialog then ends (cancelled)
    instead of working on objects that no longer exist; Ctrl+Y brings the step back."""

    def __init__(self, panel):
        self.panel = panel

    def slotUndoDocument(self, doc):
        self.panel._document_event(doc, False)

    def slotRedoDocument(self, doc):
        self.panel._document_event(doc, False)

    def slotDeletedDocument(self, doc):
        self.panel._document_event(doc, True)


class _Gate:
    """Only edges/faces that can be rounded (and whole features of the body) can be picked;
    everything else does not even light up under the mouse. Rule Fillet and Full Round take
    faces only."""

    def __init__(self, panel):
        self.panel = panel

    def allow(self, doc, obj, sub):
        try:
            panel = self.panel
            if panel._closed or panel.base is None or obj is None:
                return True
            if obj.Document.Name != panel._doc_name:
                return False  # another design (its own "Extrude" is not this part's)
            name = (sub or "").split(".")[-1]
            if obj.Name == panel.base.Name:
                return panel._pickable(name) if name else True
            if name:
                return False
            return panel._is_body_feature(obj)  # a timeline click: round the edges it made
        except Exception:
            return False


class _PointPanel:
    """What a radius point's value box (blend_field.ValueField) talks to: the dialog, with
    the point's own key."""

    def __init__(self, panel):
        self.panel = panel

    @property
    def options(self):
        return {}

    @property
    def doc(self):
        return self.panel.doc

    @property
    def _closed(self):
        return self.panel._closed

    def _typed(self, key, value):
        self.panel._typed(key, value)

    def _formula_changed(self, key):
        self.panel.schedule()

    def _formula_failed(self, key, text):
        self.panel._formula_failed(key, text)


class BlendPanel(Panel):
    """Shared dialog of Fillet and Chamfer. Subclasses add their fields (_fields)."""

    kind = "fillet"
    title = "Fillet"
    icon = "fillet"
    last = None  # the most recent panel (tests and diagnostics)

    def __init__(self, doc, feature=None, refs=None):
        super().__init__(doc, self.title if feature is None else "Edit " + self.title)
        type(self).last = BlendPanel.last = self
        self.target = feature
        self.created = feature is None
        self.body = feature.getParentGeoFeatureGroup() if feature else commands.find_body()
        self.base = None
        self.info = None
        # The selection box: one row (selection set) per entry of spec["sets"], its picks in
        # groups[row]. Rule Fillet: groups[0] and refs2 are the two boxes' faces, features /
        # features2 the steps picked in them.
        self.spec = core.default_spec(self.kind)
        self.groups = [[]]
        self.active = 0
        self.refs2 = []
        self.features = []
        self.features2 = []
        self.rule_box = 0
        self.row_formulas = {}  # (row, or None for the rule radius; value name) -> formula
        self.error = None
        # A size past what fits stops at the largest that works (value_limits.py): the limits
        # found, the size edited last ((row, value name, "typed" / "dragged" / "formula")),
        # whether its preview is still to come, and the sizes whose preview worked.
        self.limits = value_limits.Limiter()
        self.limits.key_now = self._limit_key_now  # a note goes when its inputs change
        self._edit = None
        self._edit_pending = False
        self._limiting = False
        self._good_values = {}
        self.arrows = []  # (ArrowDragger, spot, origin, direction) in global coordinates
        self.value_boxes = ValueBoxes(self)  # the value box next to each arrow
        self.fields = {}  # option name -> ValueField
        self.point_rows = []  # (position box, radius ValueField, remove button) of Variable
        self.formula_error = ""
        self.keep = None  # blend.References of the later steps (kept on their edges)
        self._saving = None
        self.observer = None
        self.gate = False
        self._style = None
        self._shown = []  # names on base FreeCAD shows selected (the picks + chains)
        self._cleared = False
        self._syncing = False
        self._accepted = False
        self._looks = _Looks()  # Coin-level look of the preview, undone at the end
        self._ghost = False  # the preview is shown (before-shape see-through)
        self.view = None
        self._keys = None
        self._mouse = None
        self._click = None  # (time, edge name, point) of a press on a Variable row's edge
        self._watch = None
        self._held = []  # QShortcuts switched off while the dialog is open
        self._doc_name = doc.Name
        self._events = QtCore.QTimer()
        self._events.setSingleShot(True)
        self._events.setInterval(30)
        self._events.timeout.connect(self._process_selection)
        self._hint = QtCore.QTimer()
        self._hint.setSingleShot(True)
        self._hint.setInterval(450)
        self._hint.timeout.connect(self._compute_hint)

        if feature is not None:
            self._read(feature)
        else:
            self.base = solid_base(self.body)
        if self.base is not None and not self.base.Shape.isNull():
            self.info = blend.ShapeInfo(self.base.Shape)
        try:
            # what the later steps are attached to, before this dialog changes anything
            self.keep = blend.References(self.body, feature if feature is not None else self.base)
        except Exception as exc:
            warn("%s: later steps not tracked: %s" % (self.title, exc))

        self._build()
        self._load_row()
        self.finish_layout()
        self.limit_label = value_limits.note_label()  # "Largest that fits here: 3.47 mm"
        self.layout.addRow(self.limit_label)
        try:
            self._start(refs)
        except Exception as exc:  # never leave a half-open dialog without a reason
            self._say("⚠ %s" % exc)
            warn("%s could not start picking: %s" % (self.title, exc))

    def _read(self, feature):
        """An existing step's settings and picks (FreeCAD's or SciForge's)."""
        from . import preview

        if fillet_sets.is_sets(feature):
            base, spec, flat, refs2, features, features2 = fillet_sets.read(feature)
            self.base, self.spec = base, spec
            self.groups = core.split_refs(spec, flat) or [[]]
            while len(self.groups) < len(spec["sets"]):
                self.groups.append([])
            if not spec["sets"]:
                spec["sets"].append(core.new_set(self.kind, spec.get("mode", "fillet")))
            self.refs2, self.features, self.features2 = refs2, features, features2
            for prop in feature.PropertiesList:
                row, option = fillet_sets.prop_key(spec, prop)
                if option is not None:
                    formula = preview.formula_of(feature, prop)
                    if formula:
                        self.row_formulas[(row, option)] = formula
        else:
            self.base, flat = blend.refs_of(feature)
            self.spec["sets"][0].update(blend.read(feature))
            self.groups = [list(flat)]
            for key, prop in PROPS.items():
                formula = preview.formula_of(feature, prop)
                if formula:
                    self.row_formulas[(0, key)] = formula

    # -- the rows of the selection box ---------------------------------------------------------
    @property
    def mode(self):
        return self.spec.get("mode", "fillet")

    @property
    def refs(self):
        """The picks of the row (Rule Fillet: the box) that clicks go into now."""
        if self.mode == "rule":
            return self.refs2 if self.rule_box == 1 else self.groups[0]
        return self.groups[self.active]

    @refs.setter
    def refs(self, value):
        value = list(value)
        if self.mode == "rule" and self.rule_box == 1:
            self.refs2 = value
        elif self.mode == "rule":
            self.groups[0] = value
        else:
            self.groups[self.active] = value

    @property
    def options(self):
        """The values the dialog's boxes edit now: the active row (Rule Fillet: the step)."""
        if self.mode == "rule":
            return self.spec
        return self.spec["sets"][self.active]

    def _row_key(self):
        return None if self.mode == "rule" else self.active

    def _has_picks(self):
        if self.mode == "rule":
            return bool(self.groups[0] or self.features)
        return any(self.groups)

    def _needs_step(self):
        """SciForge's own step is needed (FreeCAD's holds one row of one constant size)."""
        return core.needs_step(self.spec, self.groups)

    def _native_row(self):
        """The row a FreeCAD Fillet / Chamfer holds (the only row with picks)."""
        for i, group in enumerate(self.groups):
            if group:
                return i
        return self.active

    def _flat(self):
        """Every row's picks as one list (the step's Picks), with each row's count."""
        flat, counts = core.join_refs(self.groups)
        for row, count in zip(self.spec["sets"], counts):
            row["count"] = count
        return flat

    # -- layout -------------------------------------------------------------------------
    def _build(self):
        self._type_row()
        rows = QtWidgets.QWidget()
        line = QtWidgets.QHBoxLayout(rows)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(4)
        self.rows = QtWidgets.QListWidget()
        self.rows.setObjectName("SciForgeBlendRows")
        self.rows.setToolTip("The selection sets of this step: each has its own size")
        self.rows.currentRowChanged.connect(self._row_clicked)
        buttons = QtWidgets.QVBoxLayout()
        buttons.setSpacing(2)
        self.add_row_button = QtWidgets.QToolButton()
        self.add_row_button.setText("+")
        self.add_row_button.setToolTip("Add a selection set with its own size")
        self.add_row_button.clicked.connect(self._add_row)
        self.remove_row_button = QtWidgets.QToolButton()
        self.remove_row_button.setText("−")
        self.remove_row_button.setToolTip("Remove the selected set")
        self.remove_row_button.clicked.connect(self._remove_row)
        buttons.addWidget(self.add_row_button)
        buttons.addWidget(self.remove_row_button)
        buttons.addStretch(1)
        line.addWidget(self.rows, 1)
        line.addLayout(buttons)
        self.rows_widget = rows
        self.layout.addRow("Sets", rows)
        self.rule_rows()
        self.select_button, self.clear_button, row = self._select_row(0)
        self.select_label = QtWidgets.QLabel("Edges/Faces/Features")
        self.layout.addRow(self.select_label, row)
        self.select2_button, self.clear2_button, row2 = self._select_row(1)
        self.select2_label = QtWidgets.QLabel("Faces/Features 2")
        self.layout.addRow(self.select2_label, row2)
        self.select2_row = row2
        self.help = QtWidgets.QLabel(PICK_HELP)
        self.help.setWordWrap(True)
        self.help.setStyleSheet("color: #9aa4b1;")
        self.layout.addRow(self.help)
        self.chain = QtWidgets.QCheckBox()
        self.chain.setChecked(True)
        self.chain.setToolTip(
            "On: edges tangent to a picked edge are rounded with it. Off: only the picked "
            "edges (the round stops where a tangent edge begins)."
        )
        self.chain.toggled.connect(self._chain_toggled)
        self.chain_label = QtWidgets.QLabel("Tangent Chain")
        self.layout.addRow(self.chain_label, self.chain)
        self._fields()
        self.formulas = QtWidgets.QLabel("")  # values that follow a parameter / formula
        self.formulas.setWordWrap(True)
        self.formulas.setStyleSheet("color: #b8c7d9;")
        self.formulas.setVisible(False)  # shown when a box follows a formula
        self.layout.addRow(self.formulas)
        self._update_visible()
        self._refresh_rows()

    def _type_row(self):
        """Fusion's Type drop-down (the Fillet dialog has one)."""

    def rule_rows(self):
        """Rule Fillet's Rule drop-down (the Fillet dialog has one)."""

    def _select_row(self, box):
        row = QtWidgets.QWidget()
        line = QtWidgets.QHBoxLayout(row)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(4)
        button = QtWidgets.QPushButton("Select")
        button.setIcon(ui_icon("select"))
        button.setCheckable(True)
        button.setChecked(box == 0)
        button.setToolTip(PICK_HELP)
        button.setStyleSheet(
            "QPushButton:checked { background: #2f7fd1; color: white; border-radius: 3px; }"
        )
        button.clicked.connect(lambda *_a, b=box: self._choose_box(b))
        clear = QtWidgets.QToolButton()
        clear.setText("✕")
        clear.setToolTip("Drop every pick of this set")
        clear.clicked.connect(lambda *_a, b=box: self._clear_picks(b))
        line.addWidget(button, 1)
        line.addWidget(clear)
        return button, clear, row

    def _fields(self):
        raise NotImplementedError

    def _size_field(self, label, what, unit="mm"):
        field = ValueField(self, what, self.options.get(what, 1.0), unit=unit, minimum=0.0)
        self.fields[what] = field
        caption = QtWidgets.QLabel(label)
        self.layout.addRow(caption, field.widget)
        return field, caption

    def _show_row(self, widget, visible, label=None):
        widget.setVisible(visible)
        label = label or self.layout.labelForField(widget)
        if label is not None:
            label.setVisible(visible)

    def _update_visible(self):
        """Which rows of the dialog show (subclasses)."""
        rule = self.mode == "rule"
        self._show_row(self.rows_widget, not rule)
        self._show_row(self.select2_row, rule and self.spec.get("rule") == "between")
        self.select_label.setText(
            "Faces/Features"
            if rule
            else "Center Face" if self.mode == "full_round" else ("Edges/Faces/Features")
        )
        self._show_row(self.chain, self.kind == "fillet" and self.mode == "fillet")

    def _row_text(self, i):
        row = self.spec["sets"][i]
        count = len(self.groups[i]) if i < len(self.groups) else 0
        if self.mode == "full_round":
            if count != 3:
                return "%d: click a face" % (i + 1)
            size = self._round_radius(i)
            return "%d: full round" % (i + 1) + (", r %.2f mm" % size if size else "")
        picks = "%d pick%s" % (count, "" if count == 1 else "s")
        if self.kind == "chamfer":
            ctype = row.get("chamfer_type", "equal")
            if ctype == "two":
                size = "%g / %g mm" % (row.get("distance", 1.0), row.get("distance2", 1.0))
            elif ctype == "angle":
                size = "%g mm, %g°" % (row.get("distance", 1.0), row.get("angle", 45.0))
            else:
                size = "%g mm" % row.get("distance", 1.0)
            return "%d: %s · %s" % (i + 1, picks, size)
        rtype = row.get("radius_type", "constant")
        if rtype == "chord":
            size = "chord %g mm" % row.get("chord", 1.0)
        elif rtype == "variable":
            size = "variable %g → %g mm" % (row.get("start", 1.0), row.get("end", 1.0))
        else:
            size = "%g mm" % row.get("radius", 1.0)
        return "%d: %s · %s" % (i + 1, picks, size)

    def _round_radius(self, i):
        try:
            return fillet_sets.full_round_size(self.info.shape, self.groups[i])
        except Exception:
            return None

    def _refresh_rows(self):
        if not hasattr(self, "rows"):
            return
        self.rows.blockSignals(True)
        try:
            while self.rows.count() > len(self.spec["sets"]):
                self.rows.takeItem(self.rows.count() - 1)
            for i in range(len(self.spec["sets"])):
                text = self._row_text(i)
                if i < self.rows.count():
                    if self.rows.item(i).text() != text:
                        self.rows.item(i).setText(text)
                else:
                    self.rows.addItem(text)
            self.rows.setCurrentRow(self.active)
        finally:
            self.rows.blockSignals(False)
        self.remove_row_button.setEnabled(len(self.spec["sets"]) > 1)
        # as tall as its rows (2 to 5), so no row hides half under the list's edge
        try:
            # (a row's size hint is not known before the list is shown: the font's height
            # with the theme's padding is the floor)
            line = max(self.rows.sizeHintForRow(0), self.rows.fontMetrics().height() + 6, 18)
            shown = min(max(self.rows.count(), 2), 5)
            self.rows.setFixedHeight(line * shown + 2 * self.rows.frameWidth() + 6)
            if self.rows.count() <= 5:
                self.rows.scrollToTop()
            else:
                self.rows.scrollToItem(self.rows.item(self.active))
        except Exception:
            pass

    def _row_clicked(self, index):
        try:
            if 0 <= index < len(self.spec["sets"]) and index != self.active:
                self._activate(index)
        except Exception as exc:
            warn("%s set: %s" % (self.title, exc))

    def _activate(self, index, rebuild=True):
        """Make row `index` the one clicks go into and the boxes edit."""
        self.active = index
        self._load_row()
        self._refresh_rows()
        if rebuild:
            self._refs_changed(recompute=False)

    def _add_row(self, *_):
        """Fusion's "+": a new, empty selection set with the sizes of the current one."""
        try:
            if self._closed:
                return
            like = self.spec["sets"][self.active]
            self.spec["sets"].append(core.new_set(self.kind, self.mode, like))
            self.groups.append([])
            for (row, key), formula in list(self.row_formulas.items()):
                if row == self.active:
                    self.row_formulas[(len(self.groups) - 1, key)] = formula
            self._activate(len(self.groups) - 1)
            self.help.setText("Set %d: click the edges for this size." % len(self.groups))
        except Exception as exc:
            warn("%s +: %s" % (self.title, exc))

    def _remove_row(self, *_):
        try:
            if self._closed or len(self.spec["sets"]) < 2:
                return
            gone = self.active
            del self.spec["sets"][gone]
            del self.groups[gone]
            moved = {}
            for (row, key), formula in self.row_formulas.items():
                if row is None or row < gone:
                    moved[(row, key)] = formula
                elif row > gone:
                    moved[(row - 1, key)] = formula
            self.row_formulas = moved
            self.active = max(0, gone - 1)
            self._load_row()
            self._refresh_rows()
            self._sync()
            self._refs_changed()
        except Exception as exc:
            warn("%s −: %s" % (self.title, exc))

    def _choose_box(self, box):
        """Rule Fillet's two selection boxes: clicks go into the one chosen."""
        self.rule_box = box if self.mode == "rule" else 0
        self.select_button.setChecked(self.rule_box == 0)
        self.select2_button.setChecked(self.rule_box == 1)

    def _load_row(self):
        """The boxes show the active row's values and formulas (subclasses add theirs)."""
        key = self._row_key()
        for what, field in self.fields.items():
            value = self.options.get(what)
            if value is not None:
                field.set_value(float(value))
            field.set_formula(self.row_formulas.get((key, what), ""))
        if hasattr(self, "formulas"):
            self.show_formulas()

    # -- starting -----------------------------------------------------------------------
    def _start(self, refs):
        if self.base is None or self.info is None:
            self._say("⚠ Make a solid first (Create Sketch, then Extrude).")
            return
        if self.target is not None:
            missing = 0
            for i, group in enumerate(self.groups):
                kept = [r for r in group if self._pickable(r)]
                if self.mode == "full_round" and len(kept) != len(group):
                    kept = []
                missing += len(group) - len(kept)
                self.groups[i] = kept
            kept2 = [r for r in self.refs2 if self._pickable(r)]
            missing += len(self.refs2) - len(kept2)
            self.refs2 = kept2
            if missing:
                self._say(
                    "⚠ %d picked edge(s) no longer exist after an earlier change. "
                    "Pick them again." % missing
                )
        elif refs:
            self.groups[0] = [r for r in refs if self.info.pickable(r)]
        self._prepare_display()
        Gui.Selection.clearSelection()
        self.observer = _Observer(self)
        Gui.Selection.addObserver(self.observer)
        self._watch = _DocumentWatch(self)
        App.addDocumentObserver(self._watch)
        try:
            Gui.Selection.addSelectionGate(_Gate(self))
            self.gate = True
        except Exception as exc:
            warn("selection filter unavailable: %s" % exc)
        try:
            self._style = NORMAL
            Gui.Selection.setSelectionStyle(GREEDY)
        except Exception:
            self._style = None
        try:
            self.view = Gui.ActiveDocument.ActiveView
            self._keys = self.view.addEventCallback("SoKeyboardEvent", self._key)
            self._mouse = self.view.addEventCallback("SoMouseButtonEvent", self._mouse_event)
        except Exception as exc:
            warn("%s: Esc key unavailable: %s" % (self.title, exc))
        self._hold_delete(True)
        try:
            self._saving = SaveFinishes(self)
        except Exception as exc:
            warn("%s: Ctrl+S guard unavailable: %s" % (self.title, exc))
        self._sync()
        self._refresh_rows()
        self._refs_changed()
        if self.target is not None:
            self._show_preview(self._has_picks())

    def _document_event(self, doc, closing):
        try:
            if self._closed or getattr(doc, "Name", None) != self._doc_name:
                return
            if closing:
                self._abandon()
            else:
                QtCore.QTimer.singleShot(0, self._undone)
        except Exception as exc:
            warn("%s: %s" % (self.title, exc))

    def _undone(self):
        """Ctrl+Z / Ctrl+Y ran while the dialog was open: end it, keeping what undo did."""
        if self._closed:
            return
        try:
            self._accepted = False
            self._timer.stop()
            self.cleanup()
            if self.doc.HasPendingTransaction:
                self.doc.abortTransaction()
            self._close()
            log("%s ended by undo" % self.title)
        except Exception as exc:
            warn("%s could not end after undo: %s" % (self.title, exc))

    def _abandon(self):
        """The document is closing: let go of everything without touching it."""
        self.base = self.target = self.body = None
        self._looks = _Looks()
        self.cleanup()
        try:
            from . import taskui

            if taskui.current() is self:
                taskui.set_current(None)
            QtCore.QTimer.singleShot(0, Gui.Control.closeDialog)
        except Exception:
            pass

    def _hold_delete(self, hold):
        """The picks are a real FreeCAD selection: the Delete key would try to delete the part
        they belong to (with a pop-up), and FreeCAD's delete step would also close this
        dialog's own undo step, so Cancel could no longer take the fillet away. While the
        dialog is open the key does nothing (typing in a field still works)."""
        try:
            if hold:
                from . import shortcuts

                for key in ("Del", "Backspace"):
                    entry = shortcuts._bound.get(shortcuts.normalise(key))
                    if entry is not None and entry[1].isEnabled():
                        entry[1].setEnabled(False)
                        self._held.append(entry[1])
            else:
                for shortcut in self._held:
                    shortcut.setEnabled(True)
                self._held = []
        except Exception as exc:
            warn("%s: Delete key: %s" % (self.title, exc))

    def _key(self, info):
        """Keys pressed over the 3D view, like in Fusion: Esc cancels, Enter is OK (FreeCAD
        only listens to them while the task panel has the keyboard focus)."""
        try:
            key = info.get("Key")
            if info.get("State") != "UP" or self._closed:
                return
            if QtWidgets.QApplication.mouseButtons() != QtCore.Qt.NoButton:
                return  # never while an arrow is being dragged
            if key == "ESCAPE":
                QtCore.QTimer.singleShot(0, self._escape)
            elif key in ("RETURN", "PAD_ENTER", "ENTER"):
                QtCore.QTimer.singleShot(0, self._enter)
        except Exception as exc:
            warn("%s key: %s" % (self.title, exc))

    def _mouse_event(self, info):
        """A press on the edge of a Variable row: remembered, so the click adds a radius point
        there instead of dropping the edge (nothing is built here: rule 2)."""
        try:
            if self._closed or info.get("State") != "DOWN" or info.get("Button") != "BUTTON1":
                return
            if self._variable_row() is None:
                return
            found = self.view.getObjectInfo(tuple(info.get("Position")))
            if not found or found.get("Object") != self.base.Name:
                return
            name = (found.get("Component") or "").split(".")[-1]
            if name not in self._variable_chain():
                return
            point = App.Vector(found["x"], found["y"], found["z"])
            placement = self.body.getGlobalPlacement() if self.body else App.Placement()
            self._click = (time.time(), name, placement.inverse().multVec(point))
        except Exception as exc:
            warn("%s click: %s" % (self.title, exc))

    def _escape(self):
        try:
            if not self._closed:
                self.reject()
        except Exception as exc:
            warn("%s could not cancel: %s" % (self.title, exc))

    def _enter(self):
        """OK; if the fillet cannot be made yet the dialog stays open and says why."""
        try:
            if not self._closed:
                self.accept()
        except Exception as exc:
            warn("%s could not finish: %s" % (self.title, exc))

    # -- the picks ----------------------------------------------------------------------
    def _pickable(self, name):
        if self.info is None or not name:
            return False
        if self.mode in ("rule", "full_round") and not name.startswith("Face"):
            return False
        return self.info.pickable(name)

    def _row_chained(self, row):
        """Tangent Chain of set `row` (a setting of each set; always on for a chamfer and
        Rule Fillet)."""
        if self.kind != "fillet" or self.mode != "fillet" or row is None:
            return True
        rows = self.spec["sets"]
        return bool(rows[row].get("tangent_chain", True)) if row < len(rows) else True

    def _display_of(self, ref, chained=True):
        if ref.startswith("Edge") and chained:
            return self.info.chain(ref)
        return [ref]

    def _display_set(self):
        names = []
        lists = [(i, g) for i, g in enumerate(self.groups)]
        if self.mode == "rule":
            lists.append((None, self.refs2))
        for row, refs in lists:
            for ref in refs:
                for name in self._display_of(ref, self._row_chained(row)):
                    if name not in names:
                        names.append(name)
        return names

    def _sync(self):
        """Make FreeCAD's selection show exactly the picks (and their tangent chains)."""
        if self.base is None:
            return
        want = self._display_set()
        shown = list(want)
        if self._events.isActive():
            # Clicks not handled yet (they came in while a preview was built): keep them as
            # they are for _process_selection, which compares the selection with _shown.
            # Wiping them lost a pick: seven edges clicked, six taken (CI's
            # inspect_analysis_curvature), a lid corner of the Pi 5 case.
            current = self._base_selection()
            want = [n for n in want if n in current or n not in self._shown]
            want += [n for n in current if n not in want and n not in self._shown]
        self._syncing = True
        try:
            Gui.Selection.clearSelection()
            if want:
                Gui.Selection.addSelection(self.base, want)
        finally:
            self._syncing = False
        self._shown = shown

    def _base_selection(self):
        """Element names of the part before the blend that FreeCAD has selected now."""
        names = []
        try:
            for sel in Gui.Selection.getSelectionEx(self._doc_name):
                for obj, name in _resolve(sel):
                    if obj is not None and name and obj.Name == self.base.Name:
                        names.append(name)
        except Exception as exc:
            warn("%s selection: %s" % (self.title, exc))
        return names

    def _selection_event(self, cleared):
        if self._syncing or self._closed:
            return
        self._cleared = self._cleared or cleared
        self._events.start()

    def _process_selection(self):
        try:
            if self._closed or self.base is None:
                return
            cleared, self._cleared = self._cleared, False
            self.help.setText(self._help_text())  # (a timeline click below says what it added)
            names, features = [], []
            for sel in Gui.Selection.getSelectionEx(self._doc_name):
                for obj, name in _resolve(sel):
                    if obj is None:
                        continue
                    if not name:
                        features.append(obj)
                    elif obj.Name == self.base.Name:
                        names.append(name)
            changed = False
            if not cleared:  # a pick that is no longer selected was clicked again: drop it
                for name in self._shown:
                    if name not in names:
                        if self._point_click(name):
                            changed = True
                            continue
                        changed = self._drop(name) or changed
            for name in names:
                if name not in self._shown:
                    changed = self._add(name) or changed
            for obj in features:
                changed = self._add_feature(obj) or changed
            self._sync()
            if changed:
                self._refresh_rows()
                self._refs_changed()
        except Exception as exc:
            warn("%s pick: %s" % (self.title, exc))

    def _help_text(self):
        if self.mode == "rule":
            return RULE_HELP
        if self.mode == "full_round":
            return ROUND_HELP
        if self._variable_row() is not None:
            return VARIABLE_HELP
        return PICK_HELP

    def _add(self, name):
        if not self._pickable(name):
            return False
        if self.mode == "full_round":
            try:
                side1, side2 = fillet_sets.side_faces(self.info.shape, name)
            except core.SetError as exc:
                self.help.setText(str(exc))
                return False
            for i, group in enumerate(self.groups):
                if i != self.active and name in group:
                    self.groups[i] = []
            self.groups[self.active] = [side1, name, side2]
            return True
        if name in self.refs:
            return False
        # an edge belongs to one set: picked into another set, it moves there
        for i, group in enumerate(self.groups):
            if group is not self.refs and name in group:
                group.remove(name)
        if self.mode == "rule":
            other = self.groups[0] if self.rule_box == 1 else self.refs2
            if name in other:
                other.remove(name)
        self.refs.append(name)
        return True

    def _drop(self, name):
        changed = False
        for i, group in enumerate(self.groups):
            if self.mode == "full_round":
                if name in group:
                    self.groups[i] = []
                    changed = True
                continue
            chained = self._row_chained(i)
            kept = [r for r in group if name not in self._display_of(r, chained)]
            if len(kept) != len(group):
                self.groups[i] = kept
                changed = True
        kept2 = [r for r in self.refs2 if name not in self._display_of(r)]
        if len(kept2) != len(self.refs2):
            self.refs2 = kept2
            changed = True
        return changed

    def _is_body_feature(self, obj):
        body = self.body
        return (
            body is not None
            and obj is not self.target
            and obj.isDerivedFrom("PartDesign::Feature")
            and any(o.Name == obj.Name for o in body.Group)
        )

    def _add_feature(self, obj):
        if not self._is_body_feature(obj):
            return False
        if self.mode == "full_round":
            self.help.setText(ROUND_HELP)
            return False
        if self.mode == "rule":
            box = self.features2 if self.rule_box == 1 else self.features
            if any(o.Name == obj.Name for o in box):
                return False
            box.append(obj)
            self.help.setText("%s added: the rule rounds its edges." % obj.Label)
            return True
        edges = blend.feature_edges(obj, self.info)
        added = [e for e in edges if e not in self.refs]
        if not added:
            self.help.setText("%s has no sharp edges left to round here." % obj.Label)
            return False
        for name in added:
            self._add(name)
        self.help.setText("%d edge(s) of %s added." % (len(added), obj.Label))
        return True

    def _clear_picks(self, box=0):
        self._choose_box(box)
        if self.mode == "rule":
            if box == 1:
                changed = bool(self.refs2 or self.features2)
                self.refs2, self.features2 = [], []
            else:
                changed = bool(self.groups[0] or self.features)
                self.groups[0], self.features = [], []
        else:
            changed = bool(self.refs)
            self.refs = []
        if changed:
            self._sync()
            self._refresh_rows()
            self._refs_changed()

    def _refs_changed(self, recompute=True):
        count = len(self.groups[0] if self.mode == "rule" else self.refs)
        if self.mode == "rule":
            count += len(self.features)
            count2 = len(self.refs2) + len(self.features2)
            self.select2_button.setText("%d selected" % count2 if count2 else "Select")
        self.select_button.setText("%d selected" % count if count else "Select")
        if hasattr(self, "_rebuild_points"):
            self._rebuild_points()
        self._limit_cancel()  # a search for the old picks
        self.limits.note = ""  # a limit found for the old picks no longer applies
        self._update_arrows()
        if recompute:
            self.schedule()

    # -- Variable radius points --------------------------------------------------------------
    def _variable_row(self):
        """The active row when it is a Variable row with its edge picked, else None."""
        if self.kind != "fillet" or self.mode != "fillet":
            return None
        row = self.spec["sets"][self.active]
        if row.get("radius_type") != "variable" or not self.refs:
            return None
        return row

    def _chained(self):
        return self._row_chained(self.active)

    def _variable_chain(self):
        try:
            found = fillet_sets.chain_points(self.info, self.refs, self._chained())
            return [n for n, _r, _a, _b in found]
        except Exception:
            return []

    def _point_click(self, name):
        """A click on the edge of a Variable row (it would drop the edge): a radius point is
        added there instead, like Fusion's green dot on the edge."""
        click, self._click = self._click, None
        row = self._variable_row()
        if row is None or click is None or click[1] != name:
            return False
        if time.time() - click[0] > CLICK_SECONDS:
            return False
        position = fillet_sets.position_of(self.info, self.refs, click[2], self._chained())
        if position is None:
            return False
        return self._add_point(round(position, 3))

    def _add_point(self, position=None):
        """A radius point at `position` (0..1; None: the middle of the widest gap) with the
        radius the law has there now."""
        row = self._variable_row()
        if row is None:
            self.help.setText("Pick the edge first, then add radius points on it.")
            return False
        points = [list(p) for p in row.get("points", [])]
        marks = sorted([0.0, 1.0] + [p[0] for p in points])
        if position is None:
            gaps = [(b - a, (a + b) / 2.0) for a, b in zip(marks, marks[1:])]
            position = round(max(gaps)[1], 3)
        if any(abs(position - m) < 0.02 for m in marks):
            self.help.setText("There is already a radius point there.")
            return False
        try:
            law = core.variable_points(row.get("start", 1.0), row.get("end", 1.0), points)
            radius = round(core.law(law, position), 2)
        except core.SetError:
            radius = float(row.get("start", 1.0))
        points.append([position, radius])
        points.sort()
        row["points"] = points
        self.help.setText("Radius point added at %g (radius %g mm)." % (position, radius))
        return True

    # -- values ---------------------------------------------------------------------------
    def _value(self, row, what):
        if row is None:
            return float(self.spec.get(what, 1.0))
        data = self.spec["sets"][row]
        if what.startswith("pt"):
            k = int(what[2:])
            points = data.get("points", [])
            return float(points[k][1]) if k < len(points) else 0.0
        return float(data.get(what, 1.0))

    def _set_value(self, row, what, value):
        if row is None:
            self.spec[what] = value
            return
        data = self.spec["sets"][row]
        if what.startswith("pt"):
            k = int(what[2:])
            if k < len(data.get("points", [])):
                data["points"][k][1] = value
            return
        data[what] = value

    def _field_for(self, what):
        if what.startswith("pt"):
            k = int(what[2:])
            return self.point_rows[k][1] if k < len(self.point_rows) else None
        return self.fields.get(what)

    def _typed(self, what, value):
        """A new value from a box (typed number, formula, the box's arrows). A plain number
        past the largest size that fits (found already for these picks) is held there."""
        self.formula_error = ""
        row = self._row_key()
        field = self._field_for(what)
        formula = field is not None and bool(field.formula)
        self._edit = (row, what, "formula" if formula else "typed")
        self._edit_pending = True
        self._limit_stale(row, what, -1.0 if formula else value)
        if formula:
            self.limits.note = ""  # a formula is never held at the limit
        else:
            value = self._hold(row, what, value, typed=True)
        self._set_value(row, what, value)
        self._place_arrows(row, what)
        self._refresh_rows()
        self.schedule()

    def _place_arrows(self, row, what):
        value = self._value(row, what)
        for dragger, spot, _origin, _direction in self.arrows:
            if spot["what"] == what and spot.get("row") == row:
                dragger.set_distance(max(value, 0.0) * spot["per_unit"])

    def _dragged(self, spot, distance, released=False):
        """An arrow moved: the size follows it. Dragged back through its edge the size stops
        at MIN_DRAG, dragged past the largest size that fits it stops there (the arrow too,
        like the end of a slider), and when the mouse is let go the arrow comes back to the
        size shown."""
        what, row = spot["what"], spot.get("row")
        if row is not None and row != self.active and row < len(self.groups):
            self._activate(row, rebuild=False)  # dragging a set's arrow makes it the current one
        value = max(MIN_DRAG, round(distance / spot["per_unit"], 2))
        self._edit = (row, what, "dragged")
        self._limit_stale(row, what, value)
        held = self._hold(row, what, value, typed=False)
        if held != value:
            value = held
            self._place_arrows_now(row, what, value)
        changed = abs(value - self._value(row, what)) > 1e-12
        if changed:
            self._edit_pending = True
        self._set_value(row, what, value)
        field = self._field_for(what)
        if field is not None:
            field.set_value(value)
            if field.formula:  # a dragged size is a plain number again (Fusion)
                field.formula = ""
                self._formula_changed(what)
        if released:
            self._place_arrows(row, what)
        if changed:
            self.formula_error = ""
            self._refresh_rows()
            self.schedule()
        elif self.limits.note and not self.error:
            self.show_status()

    # -- sizes past what fits (value_limits.py) -----------------------------------------------
    def _unit(self, what):
        return "deg" if what == "angle" else "mm"

    def _limit_key(self, row, what):
        """The inputs the largest size of (row, what) depends on: the part before the blend,
        every set's picks and every other value (not the one being changed)."""
        spec = copy.deepcopy(self.spec)
        self._put(spec, row, what, None)
        return value_limits.make_key(
            self.kind,
            self.info.shape if self.info is not None else None,
            self.groups,
            self.refs2,
            [getattr(f, "Name", "") for f in self.features],
            [getattr(f, "Name", "") for f in self.features2],
            spec,
            row,
            what,
            self._uses_step(),
        )

    @staticmethod
    def _put(spec, row, what, value):
        """Set (value None: drop) value `what` of row `row` in a copy of the settings."""
        data = spec if row is None else spec["sets"][row]
        if what.startswith("pt"):
            k = int(what[2:])
            points = data.get("points", [])
            if k < len(points):
                points[k][1] = value
            return
        if value is None:
            data.pop(what, None)
        else:
            data[what] = value

    def _limit_key_now(self):
        """The inputs now for the size edited last (None: none edited)."""
        if self._edit is None or self.info is None:
            return None
        row, what = self._edit[0], self._edit[1]
        if row is not None and row >= len(self.spec["sets"]):
            return None
        return self._limit_key(row, what)

    def _limit_works(self, row, what):
        """works(value): the blend builds with `what` set to value (nothing in the document)."""
        spec = copy.deepcopy(self.spec)
        uses_step = self._uses_step()
        flat = self._flat() if uses_step else None
        native = self._native_row()
        info, groups = self.info, [list(g) for g in self.groups]
        refs2, features, features2 = list(self.refs2), list(self.features), list(self.features2)

        def works(value):
            self._put(spec, row, what, value)
            if uses_step:
                fillet_sets.compute(info.shape, spec, flat, refs2, features, features2)
            else:
                blend.check_build(self.kind, info, groups[native], spec["sets"][native])
            return True

        return works

    def _hold(self, row, what, value, typed):
        """`value` held at the largest (or smallest) size known to fit for these picks; the
        note under the boxes says so. Nothing is built here: every drag step comes past."""
        if self.info is None:
            return value
        try:
            held = self.limits.clamp(self._limit_key(row, what), value, typed, self._unit(what))
        except Exception as exc:
            warn("%s size limit: %s" % (self.title, exc))
            return value
        if held != value:
            field = self._field_for(what)
            if field is not None and field.raw is None:  # not while a number is being typed
                field.set_value(held)
        return held

    def _place_arrows_now(self, row, what, value):
        """The dragged arrow stops at the limit (it is set back on every drag step)."""
        for dragger, spot, _origin, _direction in self.arrows:
            if spot["what"] == what and spot.get("row") == row:
                try:
                    dragger.set_distance(max(value, 0.0) * spot["per_unit"])
                except Exception:
                    pass

    def _good_size(self, row, what, key, value):
        """(good, known): the size whose preview worked last with these same inputs, when it
        is below `value`; else the smallest size (to be built first)."""
        found = self._good_values.get((row, what))
        if found is not None and found[0] == key and found[1] < value:
            return found[1], True
        return (MIN_DRAG if what != "angle" else 1.0), False

    def _limit_refused(self, reason):
        """The size just dragged or typed was refused as too big: find the largest that works
        (once for these picks), use it and preview again. True when that was done, or when the
        search runs in the background (one trial build per turn of the event loop, so a
        dragged arrow keeps moving; Luca, 2026-10-23): its end previews the held size. While
        OK runs, the search runs to its end at once (a wait cursor)."""
        if self._limiting or not self._edit_pending or self._edit is None or self.info is None:
            return False
        row, what, source = self._edit
        if source == "formula" or not value_limits.is_limit_error(reason):
            return False
        if row is not None and row >= len(self.spec["sets"]):
            return False
        value = self._value(row, what)
        self._limiting = True
        try:
            key = self._limit_key(row, what)
            good, good_known = self._good_size(row, what, key, value)
            if value <= good:
                return False
            works, unit, keep = self._limit_works(row, what), self._unit(what), self.info.shape
            if not getattr(self, "_accepting_limit", False):
                answered, limit = self.limits.cached(key, value, good)
                if not answered:
                    self._limit_start(row, what, source, key, works, value, good, good_known)
                    return True
            else:
                with value_limits._WaitCursor():
                    limit = self.limits.find(
                        key, works, value, good, good_known=good_known, unit=unit, keep=keep
                    )
            if limit is None:
                return False
            self._limit_hold(row, what, source, key, value, limit)
            self._preview()
            return True
        except Exception as exc:
            warn("%s size limit: %s" % (self.title, exc))
            return False
        finally:
            self._limiting = False

    def _limit_hold(self, row, what, source, key, value, limit):
        """`value` (refused) held at `limit`: the note, the size, its box, the arrows."""
        self._edit_pending = False
        self.limits.limited(key, value, limit, source == "typed", self._unit(what))
        self._set_value(row, what, limit)
        field = self._field_for(what)
        if field is not None and field.raw is None:
            field.set_value(limit)
        self._place_arrows(row, what)
        self._refresh_rows()

    def _limit_start(self, row, what, source, key, works, value, good, good_known):
        """Look for the largest size that fits in the background (value_limits.Background)."""
        self._limit_cancel()
        progress = {}
        unit, keep = self._unit(what), self.info.shape

        def steps(clock):
            return self.limits.find_steps(
                key,
                works,
                value,
                good,
                good_known=good_known,
                unit=unit,
                keep=keep,
                clock=clock,
                progress=progress,
            )

        def ended(limit):
            self._limit_job = None
            self._limit_ended(row, what, source, key, value, limit)

        job = value_limits.Background(steps, ended, key, self._limit_paused)
        job.row, job.what, job.value, job.progress = row, what, value, progress
        self._limit_job = job
        self.error = None
        self.limits.note = (
            value_limits.SEARCHING_ANGLE if unit == "deg" else value_limits.SEARCHING_VALUE
        )
        self.show_status()
        job.start()

    def _limit_searching(self):
        job = getattr(self, "_limit_job", None)
        return job is not None and not job.done

    def _limit_cancel(self):
        job, self._limit_job = getattr(self, "_limit_job", None), None
        if job is not None:
            job.cancel()

    def _limit_stale(self, row, what, value):
        """A size back below the nearest one the running search found not to fit (or another
        size edited): the search is not needed for it any more."""
        job = getattr(self, "_limit_job", None)
        if job is None or job.done:
            return
        try:
            fails = job.progress.get("fails", job.value)
            if (job.row, job.what) == (row, what) and value - fails >= -1e-12:
                return
        except Exception:
            pass
        self._limit_cancel()

    def _limit_paused(self):
        """True while an arrow is being dragged: the search builds nothing then."""
        try:
            if self._closed or not taskui.button_held():
                return False
            return time.perf_counter() - self.last_moved() < self.PAUSE_MS / 1000.0
        except Exception:
            return False

    def _limit_ended(self, row, what, source, key, value, limit):
        """The background search ended: the size is held at the limit if it is still past it
        for the same picks, then previewed (now, or once the mouse rests)."""
        try:
            if self._closed:
                return
            if self.limits.note in (value_limits.SEARCHING_VALUE, value_limits.SEARCHING_ANGLE):
                self.limits.note = ""
            if limit is not None and key == self._limit_key(row, what):
                now = self._value(row, what)
                if now - limit > 1e-12:
                    if self._edit is not None and self._edit[:2] == (row, what):
                        source = self._edit[2]  # typed meanwhile: the note says so
                    self._limit_hold(row, what, source, key, now, limit)
            value_limits.busy(self)  # until the preview it asks for has run
            quiet = time.perf_counter() - self.last_moved()
            if quiet < self._rest_needed():
                self.schedule(settle=True)
            else:
                self._timer.stop()
                self._timer.setInterval(0)
                self._timer.start()
        except Exception as exc:
            value_limits.busy(self, False)
            warn("%s size limit: %s" % (self.title, exc))

    def _collect(self):
        """Read the dialog's choices into the settings (subclasses). The value boxes report
        their values themselves (ValueField), they are not read back here: FreeCAD's box can
        hold a half-read value while a number is being typed."""

    # -- formulas ----------------------------------------------------------------------------
    def show_formulas(self):
        """Fusion shows a formula in its box; FreeCAD's box can only show the number, so the
        values that follow a parameter are listed under the boxes."""
        rows = [
            "%s = %s" % (NAMES.get(key, key), field.formula)
            for key, field in self.fields.items()
            if field.formula and field.widget.isVisibleTo(self.form)
        ]
        self.formulas.setText("\n".join(rows))
        self.formulas.setVisible(bool(rows))

    def _formula_changed(self, what):
        self.formula_error = ""
        field = self.fields.get(what)
        if field is not None:
            key = (self._row_key(), what)
            if field.formula:
                self.row_formulas[key] = field.formula
            else:
                self.row_formulas.pop(key, None)
        self.show_formulas()
        self.schedule()

    def _formula_failed(self, what, text):
        self.formula_error = text
        self._say("⚠ " + text)

    def _sync_formulas(self):
        """The formulas typed in the boxes go onto the step as expressions (and a box that
        holds a plain number again drops its expression)."""
        from . import preview

        target = self.target
        if not _alive(target):
            return
        if fillet_sets.is_sets(target):
            for prop in target.PropertiesList:
                row, option = fillet_sets.prop_key(self.spec, prop)
                if option is not None:
                    preview.set_formula(target, prop, self.row_formulas.get((row, option), ""))
            return
        row = self._native_row()
        for key in self.fields:
            prop = PROPS.get(key)
            if prop in target.PropertiesList:
                preview.set_formula(target, prop, self.row_formulas.get((row, key), ""))

    # -- arrows ---------------------------------------------------------------------------
    def _remove_arrows(self):
        for dragger, _spot, _origin, _direction in self.arrows:
            dragger.remove()
        self.arrows = []

    def _spots(self, toward):
        """[(row or None, spot)] of every arrow: one per row (Variable: one per radius point,
        Two Distances: one per distance); Rule Fillet: on its first edge."""
        info = self.info
        out = []
        if self.mode == "full_round":
            return out
        if self.mode == "rule":
            try:
                edges = fillet_sets.rule_edges(
                    info, self.spec, self.groups[0], self.features, self.refs2, self.features2
                )
            except Exception:
                edges = []
            if edges:
                spots = blend.arrow_spots("fillet", info, edges[:1], self.spec, toward)
                out += [(None, s) for s in spots]
            return out
        for i, (row, refs) in enumerate(zip(self.spec["sets"], self.groups)):
            if not refs:
                continue
            if self.kind == "chamfer":
                spots = blend.arrow_spots("chamfer", info, refs, row, toward)
            elif row.get("radius_type") == "variable":
                spots = fillet_sets.variable_spots(info, row, refs, toward, self._chained())
            else:
                spots = blend.arrow_spots("fillet", info, refs, row, toward)
                if row.get("radius_type") == "chord":
                    for spot in spots:
                        spot["what"] = "chord"
                        spot["per_unit"] = fillet_sets.chord_per_unit(info, refs)
            out += [(i, s) for s in spots]
        return out

    def _update_arrows(self):
        self._remove_arrows()
        if self.info is None or not self._has_picks():
            return
        try:
            view = Gui.ActiveDocument.ActiveView
            toward = -view.getViewDirection()
            placement = self.body.getGlobalPlacement() if self.body else App.Placement()
            local_toward = placement.Rotation.inverted().multVec(toward)
            for row, spot in self._spots(local_toward):
                spot["row"] = row
                refs = self.groups[row] if row is not None else self.groups[0]
                # The arrow looks the same size on the screen whatever the part is (about 75
                # px after Fit, like Extrude's), but never longer than about half the picked
                # edge (it would dwarf a short one) and never shorter than about 1 mm (a tiny
                # part): at 8 mm it was 16 px on a 400 mm part, and 1.5 mm put it off a 4 mm
                # part.
                longest = self.info.shape.BoundBox.DiagonalLength * 0.3
                if refs and refs[0].startswith("Edge"):
                    edge = blend.element(self.info.shape, refs[0])
                    if edge is not None and edge.Length > 1e-6:
                        longest = edge.Length
                size = handle_size_at(view, placement.multVec(spot["point"]), hi=longest / 6.0)
                # The arrow's inner tip sits on the line where the blend starts; it lies on the
                # face (lifted a little) and points away from the edge.
                local = (
                    spot["point"] + spot["lift"] * (0.25 * size) + spot["direction"] * (1.6 * size)
                )
                origin = placement.multVec(local)
                direction = placement.Rotation.multVec(spot["direction"])
                value = self._value(row, spot["what"])
                dragger = ArrowDragger(
                    origin,
                    direction,
                    value * spot["per_unit"],
                    size,
                    on_drag=lambda d, s=spot: self._dragged(s, d),
                    on_release=lambda d, s=spot: self._dragged(s, d, True),
                )
                self.arrows.append((dragger, spot, origin, direction))
                self._attach_box(dragger, spot, len(self.arrows) - 1)
        except Exception as exc:
            warn("%s arrow unavailable: %s" % (self.title, exc))

    def _attach_box(self, dragger, spot, index):
        """The value box next to an arrow: the size it sets (radius, a chamfer distance, a
        radius point...), and a value or formula typed in it goes to that size. Each arrow has
        a box of its own; typing into the box of another set's arrow makes that set the
        current one."""
        what, row = spot["what"], spot.get("row")

        def text():
            field = self._field_for(what)
            if field is not None and (row is None or row == self.active):
                return field.widget.text()
            unit = "°" if what == "angle" else " mm"
            return "%.2f%s" % (self._value(row, what), unit)

        return self.value_boxes.attach(
            dragger,
            "%s#%d" % (what, index),
            text,
            lambda typed: self._box_typed(row, what, typed),
        )

    def _box_typed(self, row, what, text):
        if self._closed:
            return
        if row is not None and row != self.active and row < len(self.groups):
            self._activate(row, rebuild=False)
        field = self._field_for(what)
        if field is not None:
            field.take_text(text)

    # -- display -------------------------------------------------------------------------
    # Nothing here changes a document or view property: FreeCAD records those in the undo
    # history (a Ctrl+Z / Ctrl+Y would replay a see-through or unclickable part). PartDesign
    # shows one feature of a body at a time; makeTemporaryVisible() shows or hides one
    # without touching its Visibility, and the see-through look is set on the Coin nodes.
    def _features(self):
        if self.body is None:
            return []
        return [
            o
            for o in self.body.Group
            if o.isDerivedFrom("PartDesign::Feature") and getattr(o, "ViewObject", None)
        ]

    def _prepare_display(self):
        """Show the part before the blend (the timeline rolled back to it while picking)."""
        for obj in self._features():
            if obj is not self.base:
                obj.ViewObject.makeTemporaryVisible(False)
        self.base.ViewObject.makeTemporaryVisible(True)

    def _show_preview(self, on):
        """on: the result solid (not clickable) with the part before the blend see-through
        around it, so its edges stay clickable and the picks stay highlighted.
        off: just the part before the blend."""
        if not _alive(self.target) or self.target.ViewObject is None:
            on = False
        try:
            if on:
                self.target.ViewObject.makeTemporaryVisible(True)
                self.base.ViewObject.makeTemporaryVisible(True)
                if not self._looks.done("preview"):
                    root = self.target.ViewObject.RootNode
                    for node in _nodes(root, "SoPickStyle"):
                        self._looks.set(node, "style", node.UNPICKABLE)
                    for node in _nodes(root, "SoPolygonOffset"):
                        # behind the see-through faces it shares: a picked face's highlight
                        # then shows cleanly instead of flickering stripes
                        self._looks.set(node, "factor", 3.0)
                        self._looks.set(node, "units", 8.0)
                    for node in _nodes(self.base.ViewObject.RootNode, "SoMaterial"):
                        if node.getName().getString() == "ShapeMaterial":
                            self._looks.set(node, "transparency", GHOST / 100.0)
            else:
                self._looks.restore()
                if _alive(self.target) and self.target.ViewObject is not None:
                    self.target.ViewObject.makeTemporaryVisible(False)
                self.base.ViewObject.makeTemporaryVisible(True)
            if on != self._ghost:
                self._ghost = on
                self._sync()  # the highlight follows the shape that is displayed now
        except Exception as exc:
            warn("%s preview display: %s" % (self.title, exc))

    def _restore_display(self):
        """Undo the look changes and show what the body's Visibility properties say."""
        self._looks.restore()
        for obj in self._features():
            try:
                obj.ViewObject.makeTemporaryVisible(bool(obj.ViewObject.Visibility))
            except Exception:
                pass

    # -- preview --------------------------------------------------------------------------
    def schedule(self):
        if not self._closed:
            super().schedule()

    def _recompute(self):
        try:
            self._preview()
        except Exception as exc:
            self.error = str(exc)
            self.show_status()

    def _uses_step(self):
        """SciForge's own step builds this (or already holds it)."""
        if self.target is not None and fillet_sets.is_sets(self.target):
            return True
        return self._needs_step()

    def _trial(self):
        """Build the blend without touching the document; BlendError says why it fails."""
        if self._uses_step():
            fillet_sets.compute(
                self.info.shape,
                self.spec,
                self._flat(),
                self.refs2,
                self.features,
                self.features2,
            )
        else:
            # check_build: a Distance and Angle chamfer is built in a throw-away document
            # (trial() cannot build it); FreeCAD's own step kept the last good shape when
            # it failed, and the dialog showed no reason
            row = self._native_row()
            blend.check_build(self.kind, self.info, self.groups[row], self.spec["sets"][row])

    def _preview(self):
        if self._limit_searching() and not self._closed:
            return  # the search of the largest size that fits previews when it ends
        value_limits.busy(self, False)  # the preview after a search: this one
        if self._closed:
            return
        self._collect()
        if not self._has_picks() or self.info is None:
            self.error = None
            self._show_preview(False)
            if self.created:
                self._discard_target()
            self.show_status()
            return
        # Speed: once a preview worked, FreeCAD's own Fillet/Chamfer is changed straight away
        # and checked afterwards (the round was built twice: a trial, then the feature); the
        # trial only runs first after a failure, and to explain one.
        optimistic = self._optimistic()
        if not optimistic:
            try:
                self._trial()
            except blend.BlendError as exc:
                self._failed(str(exc))
                return
        self.error = None
        with quiet_errors():
            if self._uses_step():
                flat = self._flat()
                if self.target is None:
                    self.target = fillet_sets.make(
                        self.body,
                        self.base,
                        self.spec,
                        flat,
                        self.refs2,
                        self.features,
                        self.features2,
                    )
                elif not fillet_sets.is_sets(self.target):
                    self._swap(flat)
                else:
                    fillet_sets.update(
                        self.target,
                        self.base,
                        self.spec,
                        flat,
                        self.refs2,
                        self.features,
                        self.features2,
                    )
                self._sync_formulas()
            else:
                row = self._native_row()
                refs, options = self.groups[row], self.spec["sets"][row]
                subs = blend.base_subs(self.info, refs)
                if self.target is None:
                    self.target = blend.make(self.body, self.base, refs, self.kind, options)
                    self._sync_formulas()
                else:
                    blend.set_refs(self.target, self.base, subs)
                    self._sync_formulas()
                    blend.apply(self.target, options)
            # later steps (marker rolled back, or an earlier fillet edited) stay on their edges
            blend.recompute_keeping(self.doc, self.keep)
            if optimistic and not self._target_ok():
                self._back_to_good()
                try:
                    self._trial()
                    reason = None
                except blend.BlendError as exc:
                    reason = str(exc)
                if reason is not None:
                    self._failed(reason)
                    return
            self._remember_good()
        if self._edit is not None:
            row, what, _source = self._edit
            try:
                key = self._limit_key(row, what)
                self._good_values[(row, what)] = (key, self._value(row, what))
            except Exception:
                pass
        self._edit_pending = False
        self._show_preview(True)
        self._refresh_rows()
        self.show_status()

    def _failed(self, reason):
        if self._limit_refused(reason):
            return  # held at the largest size that fits, and previewed with it
        self._good_last = False
        self.error = reason
        self.show_status()
        self._hint.start()

    def _optimistic(self):
        """The last preview worked and FreeCAD's own step holds it: change it directly."""
        good = getattr(self, "_good", None)
        if self.kind == "chamfer" and not self._uses_step():
            if self.spec["sets"][self._native_row()].get("chamfer_type") == "angle":
                # checked first (blend.check_build): FreeCAD's Distance and Angle builder
                # crashed (OpenCASCADE segfault) on some sizes that do not fit
                return False
        return (
            bool(getattr(self, "_good_last", False))
            and good is not None
            and good[0] is self.target
            and _alive(self.target)
            and not self._uses_step()
        )

    def _remember_good(self):
        target = self.target
        # the shape was checked already (by the trial, or by _target_ok): state only here
        if target is None or self._uses_step() or not self._target_ok(validate=False):
            self._good, self._good_last = None, False
            return
        props = {}
        for name in ("Radius", "ChamferType", "Size", "Size2", "Angle", "FlipDirection"):
            if hasattr(target, name):
                props[name] = getattr(target, name)
        base = (target.Base[0], list(target.Base[1])) if target.Base else None
        self._good = (target, base, props)
        self._good_last = True

    def _target_ok(self, validate=True):
        """FreeCAD's Fillet/Chamfer built a sound result (it keeps an invalid one)."""
        target = self.target
        try:
            state = list(target.State)
            if "Invalid" in state or "Error" in state or "Touched" in state:
                return False
            shape = target.Shape
            if shape.isNull() or not shape.Solids:
                return False
            if len(shape.Solids) > max(1, len(self.info.shape.Solids)):
                return False
            return shape_checks.is_valid(shape) if validate else True
        except Exception:
            return False

    def _back_to_good(self):
        """The direct change failed: the step goes back to the last preview that worked."""
        good = getattr(self, "_good", None)
        if good is None or good[0] is not self.target:
            return
        target, base, props = good
        try:
            if base is not None:
                target.Base = base
            for name, value in props.items():
                setattr(target, name, value)
            blend.recompute_keeping(self.doc, self.keep)
        except Exception as exc:
            warn("%s: %s" % (self.title, exc))

    def _swap(self, flat):
        """FreeCAD's Fillet / Chamfer becomes SciForge's step (a second set, another type):
        the new step takes its place in the timeline, the steps after it stay on it."""
        old = self.target
        label = old.Label
        self._looks.restore()
        self._ghost = False

        def build(body):
            return fillet_sets.make(
                body, self.base, self.spec, flat, self.refs2, self.features, self.features2
            )

        new, _expressions = fillet_sets.replace(old, build)
        try:
            new.Label = label
        except Exception:
            pass
        self.target = new
        log("%s is now SciForge's own step %s (more than FreeCAD's one size)" % (label, new.Name))

    def _discard_target(self):
        """Every pick dropped (x, or the last edge clicked again) while making a new blend:
        the preview step goes away, so the body, the timeline and a measurement are back to
        the part as it was (it stayed in the body, hidden, and the body still measured it)."""
        target, self.target = self.target, None
        if not _alive(target):
            return
        self._looks.restore()  # its Coin nodes were changed for the preview
        self._ghost = False
        body = self.body
        try:
            with quiet_errors():
                if body is not None and any(o.Name == target.Name for o in body.Group):
                    body.removeObject(target)
                self.doc.removeObject(target.Name)
                if body is not None and _alive(self.base) and body.Tip is not self.base:
                    body.Tip = self.base
                blend.recompute_keeping(self.doc, self.keep)
        except Exception as exc:
            warn("%s: could not drop the preview: %s" % (self.title, exc))
        try:
            # FreeCAD hid the step before when the preview was added: the body shows its Tip
            self.base.ViewObject.Visibility = True
            self.base.ViewObject.makeTemporaryVisible(True)
        except Exception:
            pass

    def _compute_hint(self):
        """A size that does not fit and is not held at the limit (a formula, or picks that
        changed under it): the error also says the largest size that fits."""
        try:
            if self._closed or not self.error or not self._has_picks() or self.info is None:
                return
            if not value_limits.is_limit_error(self.error) or self._limit_searching():
                return
            if self._edit is not None and self._edit[0] == self._row_key():
                row, what = self._edit[0], self._edit[1]
            else:
                row = self._row_key()
                what = "radius" if self.kind == "fillet" else "distance"
                if row is not None and self.mode == "fillet":
                    rtype = self.spec["sets"][row].get("radius_type", "constant")
                    what = "chord" if rtype == "chord" else what
            size = self._value(row, what)
            key = self._limit_key(row, what)
            good, good_known = self._good_size(row, what, key, size)
            if size <= good:
                return
            limit = self.limits.find(
                key,
                self._limit_works(row, what),
                size,
                good,
                good_known=good_known,
                unit=self._unit(what),
                keep=self.info.shape,
            )
            if limit is not None and self.error:
                self._say(
                    "⚠ %s\n%s" % (self.error, value_limits.hint(limit, "hi", self._unit(what)))
                )
        except Exception as exc:
            warn("%s size hint: %s" % (self.title, exc))

    def show_status(self):
        if self.formula_error:
            self._say("⚠ " + self.formula_error)
            return
        if self.error:
            self._say("⚠ " + self.error)
            return
        obj = self.target
        if obj is None or not self._has_picks():
            self._say("")
            return
        state = list(getattr(obj, "State", []))
        if "Invalid" in state or "Error" in state:
            self._say("⚠ " + blend.friendly(obj.getStatusString()))
            return
        if obj.Shape.isNull() or not shape_checks.is_valid(obj.Shape):
            self._say("⚠ The result is not a valid solid. Try a smaller size.")
            return
        broken = [
            o.Label
            for o in (self.body.Group if self.body else [])
            if o is not obj and "Invalid" in list(getattr(o, "State", []))
        ]
        if broken:
            self._say("⚠ Later steps no longer work: %s" % ", ".join(broken))
            return
        self._say("")

    def feature(self):
        return self.target

    def _say(self, text):
        """Show (or clear) the dialog's message, growing the panel so no line is cut off. The
        note of a size held at its limit shows under it while there is no error."""
        self.message.setText(text)
        limits = getattr(self, "limits", None)
        note = "" if text or limits is None else limits.note
        value_limits.show_note(getattr(self, "limit_label", None), note)
        width = max(self.message.width(), self.form.width() - 30, 260)
        self.message.setMinimumHeight(self.message.heightForWidth(width) if text else 0)

    # -- OK / Cancel ------------------------------------------------------------------------
    def accept(self):
        try:
            self._timer.stop()
            if not self._has_picks() or self.info is None:
                self._say(
                    "⚠ Select the edges or faces to %s first." % self.title.lower()
                    if self.info is not None
                    else "⚠ Make a solid first (Create Sketch, then Extrude)."
                )
                return False
            if self.formula_error:  # a box holds text that is no value: fix it first
                self._say("⚠ " + self.formula_error)
                return False
            self._accepting_limit = True  # a size past what fits is searched at once here
            try:
                if self._limit_searching():  # the search still running: its end now
                    with value_limits._WaitCursor():
                        self._limit_job.finish()
                    self._timer.stop()
                self._preview()
            finally:
                self._accepting_limit = False
            obj = self.target
            if self.error or obj is None:
                self.show_status()
                return False
            state = list(obj.State)
            if "Invalid" in state or "Error" in state or not shape_checks.is_valid(obj.Shape):
                self.show_status()
                return False
            self._accepted = True
            # Panel.accept() without its plain recompute: a later step this edit broke (and
            # the dialog named) would print its failure to the Report view once more.
            self.cleanup()
            # the steps after the marker waited (preview.hold): rebuilt now, and later blends
            # put back on their edges, in this undo step
            from . import edit_rollback, preview

            edit_rollback.restore(self.doc)
            if preview.catch_up(self.doc):
                blend.recompute_keeping(self.doc, self.keep)
            _end_transaction(self.doc)
            self._close()
            log("%s done" % self.title)
            return True
        except Exception as exc:
            self._accepted = False
            self._say("⚠ %s" % exc)
            return False

    def reject(self):
        self._accepted = False
        return super().reject()

    def cleanup(self):
        self._closed = True
        self._limit_cancel()
        value_limits.busy(self, False)
        for timer in (self._events, self._hint):
            try:
                timer.stop()
            except Exception:
                pass
        self._remove_arrows()
        self.value_boxes.discard()
        for callback, kind in (
            (self._keys, "SoKeyboardEvent"),
            (self._mouse, "SoMouseButtonEvent"),
        ):
            if callback is not None:
                try:
                    self.view.removeEventCallback(kind, callback)
                except Exception:
                    pass
        self._keys = self._mouse = None
        if self.observer is not None:
            try:
                Gui.Selection.removeObserver(self.observer)
            except Exception:
                pass
            self.observer = None
        self._hold_delete(False)
        if self._saving is not None:
            self._saving.remove()
            self._saving = None
        if self._watch is not None:
            try:
                App.removeDocumentObserver(self._watch)
            except Exception:
                pass
            self._watch = None
        if self.gate:
            try:
                Gui.Selection.removeSelectionGate()
            except Exception:
                pass
            self.gate = False
        if self._style is not None:
            try:
                Gui.Selection.setSelectionStyle(self._style)
            except Exception:
                pass
            self._style = None
        try:
            self._restore_display()
        except Exception as exc:
            warn("%s could not restore the view: %s" % (self.title, exc))
        super().cleanup()

    # -- shared handlers ------------------------------------------------------------------
    def _chain_toggled(self, on):
        try:
            if self.mode == "fillet":
                self.options["tangent_chain"] = bool(on)
            self._refresh_rows()
            self._sync()
            self._refs_changed()
        except Exception as exc:
            warn("%s tangent chain: %s" % (self.title, exc))


class FilletPanel(BlendPanel):
    kind = "fillet"
    title = "Fillet"
    icon = "fillet"

    def _type_row(self):
        self.type = _combo(
            [
                ("Fillet", "fillet", True, "Round the picked edges"),
                (
                    "Rule Fillet",
                    "rule",
                    True,
                    "Round every edge of the picked faces or features (also edges a later "
                    "change adds)",
                ),
                (
                    "Full Round Fillet",
                    "full_round",
                    True,
                    "Replace the top face of a rib or wall by a half round",
                ),
            ]
        )
        _select(self.type, self.mode)
        self.type.currentIndexChanged.connect(self._mode_changed)
        self.layout.addRow("Type", self.type)

    def rule_rows(self):
        self.rule = _combo(
            [
                ("All Edges", "all", True, "Every edge of the faces / features picked"),
                (
                    "Between Faces/Features",
                    "between",
                    True,
                    "Only the edges where the first faces / features meet the second ones",
                ),
            ]
        )
        _select(self.rule, self.spec.get("rule", "all"))
        self.rule.currentIndexChanged.connect(self._rule_changed)
        self.layout.addRow("Rule", self.rule)

    def _fields(self):
        self.radius_type = _combo(
            [
                ("Constant", "constant", True, "The same radius along the whole edge"),
                (
                    "Chord Length",
                    "chord",
                    True,
                    "The width of the round (from where it starts on one face to the other)",
                ),
                ("Variable", "variable", True, "Radius points along the edge"),
            ]
        )
        self.radius_type.currentIndexChanged.connect(self._radius_type_changed)
        self.layout.addRow("Radius Type", self.radius_type)
        self.radius, self.radius_label = self._size_field("Radius", "radius")
        self.chord_field, self.chord_label = self._size_field("Chord Length", "chord")
        self.start_field, self.start_label = self._size_field("Start Radius", "start")
        self.end_field, self.end_label = self._size_field("End Radius", "end")
        self.points_box = QtWidgets.QWidget()
        self.points_layout = QtWidgets.QVBoxLayout(self.points_box)
        self.points_layout.setContentsMargins(0, 0, 0, 0)
        self.points_layout.setSpacing(2)
        self.add_point_button = QtWidgets.QPushButton("Add Point")
        self.add_point_button.setToolTip("A radius point in the middle of the widest gap")
        self.add_point_button.clicked.connect(self._add_point_clicked)
        self.points_layout.addWidget(self.add_point_button)
        self.layout.addRow("Radius Points", self.points_box)
        self.rounds = QtWidgets.QCheckBox("Rounds (outside edges)")
        self.rounds.setChecked(bool(self.spec.get("rounds", True)))
        self.fillets = QtWidgets.QCheckBox("Fillets (inside edges)")
        self.fillets.setChecked(bool(self.spec.get("fillets", True)))
        self.rounds.toggled.connect(self._rule_toggled)
        self.fillets.toggled.connect(self._rule_toggled)
        both = QtWidgets.QWidget()
        line = QtWidgets.QVBoxLayout(both)
        line.setContentsMargins(0, 0, 0, 0)
        line.addWidget(self.rounds)
        line.addWidget(self.fillets)
        self.rule_kinds = both
        self.layout.addRow("Rounds/Fillets", both)
        self.round_info = QtWidgets.QLabel("")
        self.round_info.setWordWrap(True)
        self.layout.addRow("Radius", self.round_info)
        self.continuity = _combo(
            [
                ("Tangent (G1)", "g1", True, "The round meets the faces smoothly (tangent)"),
                (
                    "Curvature (G2)",
                    "g2",
                    False,
                    "Not available: OpenCASCADE builds circular (G1) rounds only",
                ),
            ]
        )
        self.layout.addRow("Continuity", self.continuity)
        self.corner = _combo(
            [
                ("Rolling Ball", "rolling_ball", True, "Corners where rounds meet are blended"),
                (
                    "Setback",
                    "setback",
                    False,
                    "Not available: OpenCASCADE's fillet builder has no setback corners",
                ),
            ]
        )
        self.layout.addRow("Corner Type", self.corner)

    def _update_visible(self):
        super()._update_visible()
        if not hasattr(self, "radius_type"):
            return
        mode = self.mode
        row = self.spec["sets"][min(self.active, len(self.spec["sets"]) - 1)]
        rtype = row.get("radius_type", "constant") if mode == "fillet" else "constant"
        self._show_row(self.radius_type, mode == "fillet")
        self._show_row(self.rule, mode == "rule")
        self._show_row(
            self.radius.widget, mode == "rule" or (mode == "fillet" and rtype == "constant")
        )
        self._show_row(self.chord_field.widget, mode == "fillet" and rtype == "chord")
        for field in (self.start_field, self.end_field):
            self._show_row(field.widget, mode == "fillet" and rtype == "variable")
        self._show_row(self.points_box, mode == "fillet" and rtype == "variable")
        self._show_row(self.rule_kinds, mode == "rule")
        self._show_row(self.round_info, mode == "full_round")
        self._show_row(self.continuity, mode != "full_round")
        self._show_row(self.corner, mode != "full_round")
        self.add_row_button.setToolTip(
            "Add another full round" if mode == "full_round" else "Add a selection set"
        )
        if hasattr(self, "formulas"):
            self.show_formulas()

    def _load_row(self):
        super()._load_row()
        if not hasattr(self, "radius_type"):
            return
        if self.mode == "fillet":
            _select(self.radius_type, self.options.get("radius_type", "constant"))
        _select(self.rule, self.spec.get("rule", "all"))
        _select(self.type, self.mode)
        for box, key in ((self.rounds, "rounds"), (self.fillets, "fillets")):
            box.blockSignals(True)
            box.setChecked(bool(self.spec.get(key, True)))
            box.blockSignals(False)
        self.chain.blockSignals(True)
        self.chain.setChecked(self._chained())
        self.chain.blockSignals(False)
        self._rebuild_points()
        self._update_visible()

    def _preview(self):
        super()._preview()
        if self.mode == "full_round" and hasattr(self, "round_info"):
            sizes = [self._round_radius(i) for i, g in enumerate(self.groups) if len(g) == 3]
            sizes = [s for s in sizes if s]
            self.round_info.setText(
                "Half the width between the side faces: %s"
                % ", ".join("%.2f mm" % s for s in sizes)
                if sizes
                else "Half the width between the side faces (pick a face)."
            )

    # -- Fusion's Type and Rule ------------------------------------------------------------------
    def _mode_changed(self, *_):
        """Fillet / Rule Fillet / Full Round Fillet: each picks something else, so the picks
        start over (as in Fusion)."""
        try:
            mode = self.type.currentData()
            if mode == self.mode:
                return
            self.spec["mode"] = mode
            self.spec["sets"] = [core.new_set(self.kind, mode)]
            self.groups = [[]]
            self.active = 0
            self.refs2, self.features, self.features2 = [], [], []
            self.row_formulas = {}
            self._choose_box(0)
            self.help.setText(self._help_text())
            self._load_row()
            self._refresh_rows()
            self._sync()
            self._refs_changed()
        except Exception as exc:
            warn("Fillet type: %s" % exc)

    def _rule_changed(self, *_):
        try:
            self.spec["rule"] = self.rule.currentData()
            if self.spec["rule"] != "between":
                self.refs2, self.features2 = [], []
                self._choose_box(0)
            self._update_visible()
            self._sync()
            self._refs_changed()
        except Exception as exc:
            warn("Fillet rule: %s" % exc)

    def _rule_toggled(self, *_):
        self.spec["rounds"] = self.rounds.isChecked()
        self.spec["fillets"] = self.fillets.isChecked()
        self._refs_changed()

    # -- Radius Type -----------------------------------------------------------------------------
    def _radius_type_changed(self, *_):
        try:
            rtype = self.radius_type.currentData()
            row = self.options
            if row.get("radius_type") == rtype:
                return
            if rtype == "variable" and not row.get("points"):
                row["start"] = row["end"] = float(row.get("radius", 1.0))
            if rtype == "chord" and row.get("radius_type") == "constant":
                row["chord"] = round(core.radius_chord(row.get("radius", 1.0), math.pi / 2), 2)
            row["radius_type"] = rtype
            self._load_row()
            self._refresh_rows()
            self.help.setText(self._help_text())
            self._refs_changed()
        except Exception as exc:
            warn("Fillet radius type: %s" % exc)

    def _rebuild_points(self):
        """The Variable row's radius points: a position (0 = start of the edge, 1 = its end)
        and a radius each, and a button that removes the point."""
        if not hasattr(self, "points_layout"):
            return
        row = self.options if self.mode == "fillet" else {}
        points = row.get("points", []) if row.get("radius_type") == "variable" else []
        if len(points) == len(self.point_rows):
            for (spin, field, _button), (position, radius) in zip(self.point_rows, points):
                spin.blockSignals(True)
                spin.setValue(float(position))
                spin.blockSignals(False)
                field.set_value(float(radius))
            return
        for spin, field, button in self.point_rows:
            for widget in (spin, field.widget, button):
                widget.hide()
                widget.deleteLater()
        for i in reversed(range(self.points_layout.count())):
            item = self.points_layout.itemAt(i)
            if item is not None and item.layout() is not None:
                self.points_layout.takeAt(i)
        self.point_rows = []
        for k, (position, radius) in enumerate(points):
            line = QtWidgets.QHBoxLayout()
            line.setSpacing(4)
            spin = QtWidgets.QDoubleSpinBox()
            spin.setObjectName("SciForgeRadiusPointPosition%d" % k)
            spin.setDecimals(3)
            spin.setRange(0.001, 0.999)
            spin.setSingleStep(0.05)
            spin.setValue(float(position))
            spin.setToolTip("Where the point is: 0 = start of the edge, 1 = its end")
            spin.valueChanged.connect(lambda value, k=k: self._point_moved(k, value))
            field = ValueField(_PointPanel(self), "pt%d" % k, float(radius), minimum=0.0)
            button = QtWidgets.QToolButton()
            button.setText("✕")
            button.setToolTip("Remove this radius point")
            button.clicked.connect(lambda *_a, k=k: self._remove_point(k))
            line.addWidget(spin)
            line.addWidget(field.widget, 1)
            line.addWidget(button)
            self.points_layout.insertLayout(self.points_layout.count() - 1, line)
            self.point_rows.append((spin, field, button))

    def _point_moved(self, k, value):
        try:
            points = self.options.get("points", [])
            if k < len(points):
                points[k][0] = float(value)
                self._update_arrows()
                self.schedule()
        except Exception as exc:
            warn("Fillet radius point: %s" % exc)

    def _remove_point(self, k):
        try:
            points = self.options.get("points", [])
            if k < len(points):
                del points[k]
                QtCore.QTimer.singleShot(0, self._points_changed)
        except Exception as exc:
            warn("Fillet radius point: %s" % exc)

    def _points_changed(self):
        try:
            if self._closed:
                return
            self._rebuild_points()
            self._refresh_rows()
            self._refs_changed()
        except Exception as exc:
            warn("Fillet radius points: %s" % exc)

    def _add_point_clicked(self, *_):
        try:
            if self._add_point():
                self._points_changed()
        except Exception as exc:
            warn("Fillet add point: %s" % exc)


class ChamferPanel(BlendPanel):
    kind = "chamfer"
    title = "Chamfer"
    icon = "chamfer"

    def _fields(self):
        types = [(label, value, True, "") for value, _freecad, label in blend.CHAMFER_TYPES]
        current = [v for v, _f, _l in blend.CHAMFER_TYPES].index(
            self.options.get("chamfer_type", "equal")
        )
        self.ctype = _combo(types, current)
        self.layout.addRow("Chamfer Type", self.ctype)
        self.distance, self.distance_label = self._size_field("Distance", "distance")
        self.distance2, self.distance2_label = self._size_field("Distance 2", "distance2")
        self.angle, self.angle_label = self._size_field("Angle", "angle", unit="deg")
        self.flip = QtWidgets.QToolButton()
        self.flip.setText("⇄ Flip")
        self.flip.setCheckable(True)
        self.flip.setChecked(bool(self.options.get("flip")))
        self.flip.setToolTip("Swap the faces the two sizes are measured on")
        self.flip_label = QtWidgets.QLabel("Flip")
        self.layout.addRow(self.flip_label, self.flip)
        self.corner = _combo(
            [
                ("Chamfer", "chamfer", True, "Corners where chamfers meet get a flat face"),
                (
                    "Miter",
                    "miter",
                    False,
                    "Not available: OpenCASCADE's chamfer builder makes flat corners only",
                ),
                (
                    "Blend",
                    "blend",
                    False,
                    "Not available: OpenCASCADE's chamfer builder makes flat corners only",
                ),
            ]
        )
        self.layout.addRow("Corner Type", self.corner)
        self.ctype.currentIndexChanged.connect(self._type_changed)
        self.flip.toggled.connect(self._flip_toggled)
        self._update_rows()

    def _update_rows(self):
        ctype = self.ctype.currentData()
        two, angle = ctype == "two", ctype == "angle"
        self.distance_label.setText("Distance 1" if two else "Distance")
        for widget in (self.distance2.widget, self.distance2_label):
            widget.setVisible(two)
        for widget in (self.angle.widget, self.angle_label):
            widget.setVisible(angle)
        for widget in (self.flip, self.flip_label):
            widget.setVisible(two or angle)
        if hasattr(self, "formulas"):
            self.show_formulas()

    def _load_row(self):
        super()._load_row()
        if not hasattr(self, "ctype"):
            return
        _select(self.ctype, self.options.get("chamfer_type", "equal"))
        self.flip.blockSignals(True)
        self.flip.setChecked(bool(self.options.get("flip")))
        self.flip.blockSignals(False)
        self._update_rows()

    def _type_changed(self, *_):
        self.limits.note = ""
        self._update_rows()
        self._collect()
        self._refresh_rows()
        self._update_arrows()
        self.schedule()

    def _flip_toggled(self, *_):
        self._collect()
        self._update_arrows()
        self.schedule()

    def _collect(self):
        self.options["chamfer_type"] = self.ctype.currentData()
        self.options["flip"] = self.flip.isChecked()


# -- commands ------------------------------------------------------------------------------
class _BlendCommand:
    panel = FilletPanel
    menu = "Fillet"
    tip = ""

    def GetResources(self):
        return {
            "MenuText": self.menu,
            "ToolTip": self.tip,
            "Pixmap": ui_icon_path(self.panel.icon),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            start(self.panel)
        except Exception as exc:
            warn("%s could not start: %s" % (self.menu, exc))


def _selected_body():
    """The body the selected edges/faces belong to (it may not be the active one)."""
    for sel in Gui.Selection.getSelectionEx():
        parent = sel.Object.getParentGeoFeatureGroup()
        if parent is not None and parent.TypeId == "PartDesign::Body":
            return parent
    return None


def start(panel_class):
    """Run Fillet/Chamfer: with edges/faces already selected it starts with them."""
    selection, picked_body = [], None
    if not Gui.Control.activeDialog():
        # (with a dialog open, the selection is that dialog's picks, not the user's: F
        # pressed inside a Fillet finishes it and starts a new one with nothing picked)
        selection = [(s.Object, list(s.SubElementNames)) for s in Gui.Selection.getSelectionEx()]
        picked_body = _selected_body()
    if not commands.finish_open_dialog():
        return None
    doc = App.ActiveDocument
    if picked_body is not None and picked_body is not commands.active_body():
        try:  # Fusion rounds the edges you picked, whichever body they are on
            Gui.ActiveDocument.ActiveView.setActiveObject("pdbody", picked_body)
        except Exception as exc:
            warn("could not activate %s: %s" % (picked_body.Label, exc))
    body = commands.find_body()
    base = solid_base(body)
    if base is None:
        commands.tell(
            "%s needs a solid to round: make one first (Create Sketch, then Extrude)."
            % panel_class.title
        )
        return None
    info = blend.ShapeInfo(base.Shape)
    _reselect(selection)
    refs = picks_from_selection(body, info, base)
    panel = None
    try:
        panel = panel_class(doc, refs=refs)
        Gui.Control.showDialog(panel)
    except Exception:
        if panel is not None and not panel._closed:
            try:
                panel.reject()
            except Exception:
                pass
        raise
    log("%s started with %d pick(s)" % (panel_class.title.lower(), len(refs)))
    return panel


def _reselect(selection):
    """finish_open_dialog() clears the selection; put back what the user had picked."""
    if Gui.Selection.getSelectionEx() or not selection:
        return
    for obj, subs in selection:
        try:
            if subs:
                Gui.Selection.addSelection(obj, subs)
            else:
                Gui.Selection.addSelection(obj)
        except Exception:
            pass


class FilletCommand(_BlendCommand):
    panel = FilletPanel
    menu = "Fillet"
    tip = (
        "Round edges: click edges or faces, drag the arrow or type a radius, "
        "with a live preview (F)"
    )


class ChamferCommand(_BlendCommand):
    panel = ChamferPanel
    menu = "Chamfer"
    tip = "Bevel edges: equal distance, two distances or distance and angle, " "with a live preview"


def edit_fillet(obj):
    """Timeline double-click: the Fillet dialog with the feature's edges picked."""
    Gui.Control.showDialog(FilletPanel(obj.Document, feature=obj))


def edit_chamfer(obj):
    Gui.Control.showDialog(ChamferPanel(obj.Document, feature=obj))


COMMANDS = {"SciForge_Fillet": FilletCommand, "SciForge_Chamfer": ChamferCommand}
EDITORS = {
    blend.FILLET: edit_fillet,
    blend.CHAMFER: edit_chamfer,
    "SciForge::" + fillet_sets.SCIFORGE_TYPES["fillet"]: edit_fillet,
    "SciForge::" + fillet_sets.SCIFORGE_TYPES["chamfer"]: edit_chamfer,
}
