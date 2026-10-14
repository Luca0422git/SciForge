# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's drawing annotations in SciForge: the Dimension dialog (double-click a
dimension: override, text before / after, symbols, precision, tolerances with ISO fits,
basic and reference), Ordinate, Baseline, Chain and Arc Length dimensions, Leader, Feature
Control Frame, Datum Identifier, Surface Texture and Edge Extension (the logic is in
drawing_annot.py, the shapes in drawing_annot_core.py)."""

import math

import FreeCADGui as Gui

from . import commands, drawing, drawing_annot, drawing_ui, taskui, warn
from . import drawing_annot_core as ac
from . import drawing_dims_core as dc
from . import drawing_fits as fits
from .compat import QtCore, QtWidgets
from .drawing_ui import DrawingPanel, _combo, _later, pick_at

LINEAR = ("DistanceX", "DistanceY", "Distance")
STACK_SPACING = 8.0  # mm between stacked baseline dimensions (on the paper)


# ------------------------------------------------------------------ what was double-clicked
def _label_point(dim):
    view = dim.References2D[0][0] if dim.References2D else None
    if view is None:
        return None
    x, y = drawing.view_position(view)
    return x + drawing._value(dim.X), y + drawing._value(dim.Y)


def dimension_at(page, point, tol=2.0):
    """The dimension whose text is under a page point."""
    best = None
    for dim in drawing.annotations(page):
        if dim.TypeId != drawing.DIMENSION or not dim.References2D:
            continue
        at = _label_point(dim)
        if at is None:
            continue
        text = drawing.dimension_text(dim) or "00"
        lines = text.split("\n")
        half = max(3.0, 0.6 * 3.5 * max(len(t) for t in lines) / 2.0) + tol
        d = math.hypot(point[0] - at[0], point[1] - at[1])
        if d <= half and (best is None or d < best[0]):
            best = (d, dim)
    return best[1] if best else None


def annotation_at(page, point, margin=1.0):
    """The annotation (leader, frame, symbol...) drawn under a page point."""
    best = None
    for obj in drawing_annot.annotations_of(page):
        try:
            x0, y0, x1, y1 = ac.bbox(drawing_annot.prims_of(obj))
        except Exception:
            continue
        if x0 - margin <= point[0] <= x1 + margin and y0 - margin <= point[1] <= y1 + margin:
            area = (x1 - x0) * (y1 - y0)
            if best is None or area < best[0]:
                best = (area, obj)
    return best[1] if best else None


def _selected_on(page):
    found = []
    try:
        for sel in Gui.Selection.getSelectionEx("", 0):
            obj = sel.Object
            owner = drawing.page_of(obj)
            if owner is not None and drawing.same(owner, page):
                found.append(obj)
    except Exception:
        pass
    return found


def edit_at(page, point):
    """A double-click with no command open: the Dimension dialog of the dimension, or the
    dialog of the annotation, under the mouse (TechDraw selected it with the first
    click). False when there is none."""
    target = None
    for obj in _selected_on(page):
        if obj.TypeId == drawing.DIMENSION and dimension_at(page, point, tol=6.0) is not None:
            target = obj
            break
        if drawing_annot.is_annotation(obj) and annotation_at(page, point, margin=3.0) is not None:
            target = obj
            break
    if target is None:
        target = dimension_at(page, point) or annotation_at(page, point)
    if target is None:
        return False
    _later(edit, target)
    return True


def edit(obj):
    """The dialog of a dimension or an annotation."""
    if not commands.finish_open_dialog():
        return None
    page = drawing.page_of(obj)
    if page is None:
        return None
    try:
        if obj.TypeId == drawing.DIMENSION:
            return DimensionEditPanel(page, obj).show()
        kind = drawing_annot.annotation_kind(obj)
        panel = PANELS.get(kind)
        if panel is not None:
            return panel(page, obj).show()
        if kind in ("ordinate", "arc"):
            commands.tell(
                "This dimension follows its points by itself: drag it to move its value, "
                "Delete to remove it."
            )
    except drawing.DrawingError as exc:
        commands.tell(str(exc))
    except Exception as exc:
        warn("edit %s: %s" % (getattr(obj, "Label", "?"), exc))
    return None


def _line(text=""):
    return QtWidgets.QLineEdit(text)


def _float(text, default=None):
    try:
        return float(str(text).strip().replace(",", ".").replace("±", ""))
    except (TypeError, ValueError):
        return default


def _num(value):
    return ("%.4f" % value).rstrip("0").rstrip(".") if value else "0"


class _FocusTracker(QtCore.QObject):
    """Tells which of several fields took the keyboard last."""

    def __init__(self, parent, on_focus):
        super().__init__(parent)
        self.on_focus = on_focus

    def eventFilter(self, obj, event):
        try:
            if event.type() == QtCore.QEvent.FocusIn:
                self.on_focus(obj)
        except Exception:
            pass
        return False


# ------------------------------------------------------------------ the Dimension dialog
class DimensionEditPanel(DrawingPanel):
    """Fusion's Dimension dialog (double-click a dimension): the value's override, text
    before and after it, symbols, precision, Tolerance (None, Symmetric, Deviation,
    Limits, Fit with ISO 286 classes), Basic and Reference. Changes show live; Cancel puts
    the dimension back."""

    title = "Dimension"
    icon = "dw_dimension"

    def __init__(self, page, dim):
        # TechDraw files a "Drag Dimension" step when a selected value is deselected after
        # it was laid out again (its text changed size): deselect it before this dialog's
        # step begins, so that one Undo takes back what the dialog did
        try:
            Gui.Selection.clearSelection()
            QtWidgets.QApplication.processEvents()
        except Exception:
            pass
        super().__init__(page, "Edit Dimension")
        self.dim = dim
        data = drawing_annot.dimension_settings(dim)
        self.kind = drawing_annot.dimension_kind(dim)
        value = drawing.dimension_value(dim)
        self.value = value
        units = drawing.units_of(page)
        measured = dc.texts(value, self.kind, units, {})["main"] if value is not None else "?"
        self.measured = QtWidgets.QLabel(measured)
        self.measured.setObjectName("SciForgeDimMeasured")
        self.layout.addRow("Measured", self.measured)
        self.override = _line(data["override"])
        self.override.setObjectName("SciForgeDimOverride")
        self.override.setPlaceholderText("(the measured value)")
        self.prefix = _line(data["prefix"])
        self.prefix.setObjectName("SciForgeDimPrefix")
        self.suffix = _line(data["suffix"])
        self.suffix.setObjectName("SciForgeDimSuffix")
        self.layout.addRow("Text before", self.prefix)
        self.layout.addRow("Override value", self.override)
        self.layout.addRow("Text after", self.suffix)
        self.target = self.prefix
        symbols = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(symbols)
        row.setContentsMargins(0, 0, 0, 0)
        for symbol, name in dc.SYMBOLS:
            button = QtWidgets.QToolButton()
            button.setText(symbol)
            button.setToolTip("Insert the %s sign" % name.lower())
            button.setObjectName("SciForgeDimSymbol_" + name.replace(" ", "").replace("/", ""))
            button.clicked.connect(lambda _c=False, t=symbol: self._insert(t))
            row.addWidget(button)
        row.addStretch(1)
        self.layout.addRow("Symbols", symbols)
        self._focus = _FocusTracker(self.prefix, self._focused)
        for field in (self.prefix, self.override, self.suffix):
            field.installEventFilter(self._focus)
        self.precision = _combo(dc.PRECISIONS, data["precision"])
        self.precision.setObjectName("SciForgeDimPrecision")
        self.layout.addRow("Precision", self.precision)
        self.tolerance = _combo(dc.TOLERANCES, data["tolerance"])
        self.tolerance.setObjectName("SciForgeDimTolerance")
        self.layout.addRow("Tolerance", self.tolerance)
        self.upper = _line(_num(data["upper"]))
        self.upper.setObjectName("SciForgeDimUpper")
        self.lower = _line(_num(data["lower"]))
        self.lower.setObjectName("SciForgeDimLower")
        self.layout.addRow("Upper", self.upper)
        self.layout.addRow("Lower", self.lower)
        self.basis = _combo(fits.BASES, data["fit_basis"])
        self.basis.setObjectName("SciForgeDimFitBasis")
        self.fit_type = _combo(fits.FIT_TYPES, self._type_of(data["fit"]))
        self.fit_type.setObjectName("SciForgeDimFitType")
        self.fit = QtWidgets.QComboBox()
        self.fit.setObjectName("SciForgeDimFit")
        self.hole = _line("")
        self.hole.setObjectName("SciForgeDimHoleClass")
        self.shaft = _line("")
        self.shaft.setObjectName("SciForgeDimShaftClass")
        self.member = _combo(dc.FIT_MEMBERS, data["fit_member"])
        self.member.setObjectName("SciForgeDimFitMember")
        self.display = _combo(dc.FIT_DISPLAYS, data["fit_display"])
        self.display.setObjectName("SciForgeDimFitDisplay")
        self.fit_info = QtWidgets.QLabel("")
        self.fit_info.setWordWrap(True)
        self.fit_info.setObjectName("SciForgeDimFitInfo")
        self.layout.addRow("Basis", self.basis)
        self.layout.addRow("Fit type", self.fit_type)
        self.layout.addRow("Fit", self.fit)
        self.layout.addRow("Hole class", self.hole)
        self.layout.addRow("Shaft class", self.shaft)
        self.layout.addRow("This dimension is the", self.member)
        self.layout.addRow("Display", self.display)
        self.layout.addRow(self.fit_info)
        self.tol_precision = _combo(dc.PRECISIONS, data["tol_precision"])
        self.tol_precision.setObjectName("SciForgeDimTolPrecision")
        self.layout.addRow("Tolerance precision", self.tol_precision)
        self.basic = QtWidgets.QCheckBox("Basic (in a box, no tolerance)")
        self.basic.setObjectName("SciForgeDimBasic")
        self.basic.setChecked(data["basic"])
        self.reference = QtWidgets.QCheckBox("Reference (in parentheses)")
        self.reference.setObjectName("SciForgeDimReference")
        self.reference.setChecked(data["reference"])
        self.layout.addRow(self.basic)
        self.layout.addRow(self.reference)
        self._filling = True
        self._fill_fits(data["fit"])
        self._filling = False
        for widget in (self.override, self.prefix, self.suffix, self.upper, self.lower):
            widget.textEdited.connect(self._changed)
        for widget in (
            self.precision,
            self.tolerance,
            self.member,
            self.display,
            self.tol_precision,
        ):
            widget.currentTextChanged.connect(self._changed)
        self.basis.currentTextChanged.connect(self._fit_filter)
        self.fit_type.currentTextChanged.connect(self._fit_filter)
        self.fit.currentTextChanged.connect(self._fit_chosen)
        self.hole.textEdited.connect(self._changed)
        self.shaft.textEdited.connect(self._changed)
        self.basic.toggled.connect(self._changed)
        self.reference.toggled.connect(self._changed)
        self._rows()
        self.finish_layout()
        self._info()
        self.say("Change the dimension's text and tolerance; it shows on the sheet. OK keeps it.")

    # -- fields ------------------------------------------------------------------------
    def _focused(self, field):
        """The symbol buttons type into the text field used last."""
        if field in (self.prefix, self.override, self.suffix):
            self.target = field

    def _insert(self, symbol):
        field = self.target or self.prefix
        try:
            field.insert(symbol)
            field.setFocus()
        except RuntimeError:
            return
        self._changed()

    @staticmethod
    def _type_of(name):
        for fit, _basis, kind, _use in fits.PREFERRED_FITS:
            if fit == name:
                return kind
        try:
            hole, shaft = fits.parse_fit(name)
            return fits.fit_type(hole, shaft, 20.0)
        except fits.FitError:
            return "Clearance"

    def _fill_fits(self, current=None):
        names = fits.preferred_fits(self.basis.currentText(), self.fit_type.currentText())
        self.fit.blockSignals(True)
        self.fit.clear()
        self.fit.addItems(names + ["Custom"])
        if current in names:
            self.fit.setCurrentText(current)
        elif current:
            self.fit.setCurrentText("Custom")
        self.fit.blockSignals(False)
        chosen = self.fit.currentText()
        if chosen != "Custom":
            hole, shaft = fits.parse_fit(chosen)
        else:
            try:
                hole, shaft = fits.parse_fit(current)
            except fits.FitError:
                hole, shaft = "H7", "g6"
        self.hole.setText(hole)
        self.shaft.setText(shaft)
        custom = chosen == "Custom"
        self.hole.setEnabled(custom)
        self.shaft.setEnabled(custom)

    def _fit_filter(self, *_args):
        if self._closed:
            return
        self._fill_fits(self.fit.currentText() if self.fit.currentText() != "Custom" else None)
        self._changed()

    def _fit_chosen(self, text):
        if self._closed or self._filling:
            return
        custom = text == "Custom"
        self.hole.setEnabled(custom)
        self.shaft.setEnabled(custom)
        if not custom:
            hole, shaft = fits.parse_fit(text)
            self.hole.setText(hole)
            self.shaft.setText(shaft)
        self._changed()

    def _rows(self):
        tol = self.tolerance.currentText()
        flags = {
            self.upper: tol in ("Symmetric", "Deviation", "Limits"),
            self.lower: tol in ("Deviation", "Limits"),
            self.basis: tol == "Fit",
            self.fit_type: tol == "Fit",
            self.fit: tol == "Fit",
            self.hole: tol == "Fit",
            self.shaft: tol == "Fit",
            self.member: tol == "Fit",
            self.display: tol == "Fit",
            self.fit_info: tol == "Fit",
            self.tol_precision: tol != "None",
        }
        for widget, on in flags.items():
            try:
                self.layout.setRowVisible(widget, on)
            except Exception:
                widget.setVisible(on)
        try:
            self.layout.labelForField(self.upper).setText(
                "Tolerance" if tol == "Symmetric" else "Upper"
            )
        except Exception:
            pass

    def gather(self):
        """The dialog's settings (drawing_dims_core.settings)."""
        upper = _float(self.upper.text(), 0.0)
        lower = _float(self.lower.text(), 0.0)
        return dc.settings(
            {
                "override": self.override.text(),
                "prefix": self.prefix.text(),
                "suffix": self.suffix.text(),
                "precision": self.precision.currentText(),
                "tolerance": self.tolerance.currentText(),
                "upper": upper,
                "lower": lower,
                "fit_basis": self.basis.currentText(),
                "fit": "%s/%s" % (self.hole.text().strip(), self.shaft.text().strip()),
                "fit_member": self.member.currentText(),
                "fit_display": self.display.currentText(),
                "tol_precision": self.tol_precision.currentText(),
                "basic": self.basic.isChecked(),
                "reference": self.reference.isChecked(),
            }
        )

    def _problem(self, data):
        for field, name in ((self.upper, "upper"), (self.lower, "lower")):
            if field.isVisibleTo(self.form) and _float(field.text()) is None:
                return "Type a number for the %s tolerance (like 0.1 or -0.05)." % name
        return dc.validate(data, self.value, self.kind)

    def _changed(self, *_args):
        if self._closed or self._filling:
            return
        self._rows()
        data = self.gather()
        problem = self._problem(data)
        self.message.setText(problem)
        self._info()
        if problem:
            return
        drawing_annot.set_dimension_settings(self.dim, data)
        self.schedule()

    def _info(self):
        if self.tolerance.currentText() != "Fit" or self.value is None:
            return
        try:
            hole, shaft = self.hole.text().strip(), self.shaft.text().strip()
            size = self.value
            hmax, hmin = fits.limits(hole, size)
            smax, smin = fits.limits(shaft, size)
            cmax, cmin = fits.clearance(hole, shaft, size)
            kind = fits.fit_type(hole, shaft, size)
            use = fits.fit_use("%s/%s" % (hole, shaft))
            self.fit_info.setText(
                "%s/%s at %s: hole %s to %s, shaft %s to %s; %s fit%s"
                % (
                    hole,
                    shaft,
                    dc.number(size),
                    _num(hmin),
                    _num(hmax),
                    _num(smin),
                    _num(smax),
                    kind.lower(),
                    (" (%s)" % use.lower()) if use else "",
                )
                + (
                    "; clearance %s to %s" % (_num(cmin), _num(cmax))
                    if kind != "Interference"
                    else ""
                )
            )
        except fits.FitError as exc:
            self.fit_info.setText(str(exc))

    def accept(self):
        data = self.gather()
        problem = self._problem(data)
        if problem:
            self.message.setText(problem)
            return False
        drawing_annot.set_dimension_settings(self.dim, data)
        return super().accept()


# ------------------------------------------------------------------ picking points of a view
def _pick(panel, point, curve=None, want_vertex=True):
    """(view, element name, local point) under the mouse, or (None, None, None)."""
    return pick_at(panel.page, point, panel.tolerance(), want_vertex=want_vertex, curve=curve)


def _point_anchor(view, name, local):
    if view is None:
        return None
    return drawing_annot.make_anchor(view, name, local)


# ------------------------------------------------------------------ Ordinate
class OrdinatePanel(DrawingPanel):
    """Fusion's Ordinate Dimension: click the origin (a corner, a circle's centre...), then
    a point to measure and where its value goes: up or down measures across (x),
    sideways measures up (y). The origin shows 0. More points follow; Esc ends."""

    title = "Ordinate Dimension"
    icon = "dw_dimension"

    def __init__(self, page):
        super().__init__(page, "Ordinate Dimension")
        self.view = None
        self.origin = None
        self.feature = None
        self.made = []
        self.lines = {}  # axis -> the text line's page coordinate of the first one
        self.finish_layout()
        self.say("Click the origin: a corner, an edge's end or a circle's centre of a view.")

    def _anchor(self, point):
        view, name, local = _pick(self, point)
        if view is None or name is None:
            return None, None
        if self.view is not None and not drawing.same(view, self.view):
            self.message.setText("Pick from the same view as the origin.")
            return None, None
        if drawing.is_isometric(view):
            self.message.setText(
                "An isometric view cannot be dimensioned: pick a front, top or side view."
            )
            return None, None
        return view, drawing_annot.make_anchor(view, name, local)

    def on_press(self, point, event):
        if self.origin is None:
            view, anchor = self._anchor(point)
            if anchor is None:
                if not self.message.text():
                    self.message.setText("Click a corner, an edge or a circle of a view.")
                return True
            self.view, self.origin = view, anchor
            self.message.setText("")
            self.say("Click a point to dimension from the origin.")
            return True
        if self.feature is None:
            view, anchor = self._anchor(point)
            if anchor is None:
                if not self.message.text():
                    self.message.setText("Click a corner, an edge or a circle of the same view.")
                return True
            self.feature = anchor
            self.message.setText("")
            self.say("Move up or down (x) or sideways (y) and click where the value goes.")
            return True
        self._place(point)
        return True

    def _feature_page(self):
        return drawing.local_to_page(self.view, drawing_annot.centre_point(self.feature))

    def _snapped(self, axis, point):
        """Values of one axis line up (the first one's line, when the mouse is near it)."""
        line = self.lines.get(axis)
        if line is None:
            return point
        if axis == "x" and abs(point[1] - line) < 6.0:
            return point[0], line
        if axis == "y" and abs(point[0] - line) < 6.0:
            return line, point[1]
        return point

    def _place(self, point):
        f = self._feature_page()
        axis = ac.ordinate_axis(f, point)
        point = self._snapped(axis, point)
        origin_page = drawing.local_to_page(self.view, drawing_annot.centre_point(self.origin))
        if not drawing_annot.has_zero(self.page, self.view, self.origin, axis):
            if axis == "x":
                zero_at = (origin_page[0], point[1])
            else:
                zero_at = (point[0], origin_page[1])
            drawing_annot.add_ordinate(self.view, self.origin, self.origin, axis, zero_at)
        obj = drawing_annot.add_ordinate(self.view, self.origin, self.feature, axis, point)
        self.lines.setdefault(axis, point[1] if axis == "x" else point[0])
        self.made.append(obj.Name)
        self.feature = None
        self.clear_overlay()
        self.doc.recompute()
        taskui._end_transaction(self.doc)
        self.doc.openTransaction("Ordinate Dimension")
        self.say("%s placed. Click the next point, or Enter / Esc." % obj.Label)

    def on_move(self, point, event):
        if self._closed or self.feature is None:
            return
        self.clear_overlay()
        f = self._feature_page()
        axis = ac.ordinate_axis(f, point)
        point = self._snapped(axis, point)
        end = (f[0], point[1]) if axis == "x" else (point[0], f[1])
        self.overlay_line(f, end, dashed=False)

    def escape(self):
        if self.feature is not None:
            self.feature = None
            self.clear_overlay()
            self.say("Click a point to dimension from the origin.")
            return
        taskui.press_dialog_button("accept")


# ------------------------------------------------------------------ Baseline and Chain
def linear_dimension_at(page, point, tol=3.0):
    """A linear dimension whose line, extension lines or text are near a page point."""
    best = None
    for dim in drawing.annotations(page):
        if dim.TypeId != drawing.DIMENSION or dim.Type not in LINEAR or not dim.References2D:
            continue
        pts = drawing_annot.dimension_points(dim)
        if pts is None:
            continue
        (px, py), (qx, qy) = pts
        tx, ty = drawing_annot.dimension_line_offset(dim)
        if dim.Type == "DistanceX":
            segments = [((px, py), (px, ty)), ((qx, qy), (qx, ty)), ((px, ty), (qx, ty))]
        elif dim.Type == "DistanceY":
            segments = [((px, py), (tx, py)), ((qx, qy), (tx, qy)), ((tx, py), (tx, qy))]
        else:
            segments = [((px, py), (qx, qy))]
        d = min(
            [_seg_distance(point, a, b) for a, b in segments]
            + [math.hypot(point[0] - tx, point[1] - ty)]
        )
        if d <= tol and (best is None or d < best[0]):
            best = (d, dim)
    return best[1] if best else None


def _seg_distance(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    if length2 < 1e-12:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length2))
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))


class StackPanel(DrawingPanel):
    """Fusion's Baseline / Chain Dimension: click an existing linear dimension near the
    end to start from, then the next points; each one is a dimension of the same kind:
    from that start, stacked further out (Baseline), or from the point before, on one
    line (Chain). Esc or Enter ends."""

    title = "Baseline Dimension"
    icon = "dw_dimension"
    chain = False

    def __init__(self, page):
        super().__init__(page, self.title)
        self.base = None  # (dim, view, base vertex name, base page point)
        self.last = None  # (vertex name, page point) chain: the point before
        self.count = 0
        self.made = []
        self.finish_layout()
        self.say("Click an existing linear dimension, near the end to start from.")

    def on_press(self, point, event):
        if self.base is None:
            dim = linear_dimension_at(self.page, point)
            if dim is None:
                self.message.setText(
                    "Click a horizontal or vertical dimension (make one with Dimension first)."
                )
                return True
            name, end = drawing_annot.base_reference(dim, point)
            if name is None:
                self.message.setText(
                    "That dimension's end is not a point SciForge can measure from."
                )
                return True
            view = dim.References2D[0][0]
            self.base = (dim, view, name, end)
            if self.chain:
                points = drawing_annot.dimension_points(dim)
                other = max(points, key=lambda p: math.hypot(p[0] - end[0], p[1] - end[1]))
                other_name = drawing_annot.vertex_at(view, drawing.page_to_local(view, other))
                self.last = (other_name or name, other if other_name else end)
            self.message.setText("")
            self.say("Click the next point to dimension; Enter or Esc when done.")
            return True
        dim, view, base_name, base_page = self.base
        picked_view, name, local = _pick(self, point)
        if picked_view is None or name is None or not drawing.same(picked_view, view):
            self.message.setText("Click a corner, an edge's end or a circle of the same view.")
            return True
        vertex = self._vertex(view, name, local)
        if vertex is None:
            self.message.setText("Click a corner or a circle (its centre is used).")
            return True
        target = drawing.local_to_page(view, vertex[1])
        start_name, start_page = self.last if self.chain else (base_name, base_page)
        if start_name == vertex[0]:
            self.message.setText("Click a point other than the one the dimension starts from.")
            return True
        self.count += 1
        text_at = self._text_at(dim, start_page, target)
        new = drawing.add_dimension(view, [start_name, vertex[0]], dim.Type, text_at)
        self.made.append(new.Name)
        if self.chain:
            self.last = (vertex[0], target)
        self.message.setText("")
        self.doc.recompute()
        taskui._end_transaction(self.doc)
        self.doc.openTransaction(self.title)
        self.say("Placed. Click the next point; Enter or Esc when done.")
        return True

    def _vertex(self, view, name, local):
        """(vertex name, local point) of a pick: a vertex, a circle's centre, or the
        nearer end of a straight edge."""
        if name.startswith("Vertex"):
            p = view.getVertexBySelection(name).Point
            return name, (p.x, p.y)
        info = drawing.edge_info(view, name)
        if info is None:
            return None
        if info["kind"] in ("circle", "arc"):
            centre = drawing.center_vertex(view, info["center"])
            return (centre, info["center"]) if centre else None
        if info["kind"] == "line":
            end = min(
                (info["p1"], info["p2"]), key=lambda p: math.hypot(p[0] - local[0], p[1] - local[1])
            )
            vertex = drawing_annot.vertex_at(view, end)
            return (vertex, end) if vertex else None
        return None

    def _text_at(self, dim, start, target):
        base_text = drawing_annot.dimension_line_offset(dim)
        if self.chain:
            return _chain_text(dim.Type, base_text, start, target)
        return drawing_annot.stacked_position(
            dim.Type, base_text, start, target, STACK_SPACING, self.count
        )

    def escape(self):
        taskui.press_dialog_button("accept")


def _chain_text(dim_type, base_text, start, target):
    if dim_type == "DistanceX":
        return (start[0] + target[0]) / 2.0, base_text[1]
    if dim_type == "DistanceY":
        return base_text[0], (start[1] + target[1]) / 2.0
    return (start[0] + target[0]) / 2.0, (start[1] + target[1]) / 2.0


class BaselinePanel(StackPanel):
    title = "Baseline Dimension"
    chain = False


class ChainPanel(StackPanel):
    title = "Chain Dimension"
    chain = True


# ------------------------------------------------------------------ Arc length
class ArcLengthPanel(DrawingPanel):
    """An arc's length: click an arc, then where the dimension goes."""

    title = "Arc Length Dimension"
    icon = "dw_dimension"

    def __init__(self, page):
        super().__init__(page, "Arc Length Dimension")
        self.view = None
        self.anchor = None
        self.made = []
        self.finish_layout()
        self.say("Click an arc of a view.")

    def on_press(self, point, event):
        if self.anchor is None:
            view, name, local = _pick(self, point, curve="circle", want_vertex=False)
            info = drawing.edge_info(view, name) if view is not None and name else None
            if info is None or info["kind"] != "arc":
                self.message.setText(
                    "Click an arc (part of a circle): a whole circle takes a diameter."
                )
                return True
            if drawing.is_isometric(view):
                self.message.setText("An isometric view cannot be dimensioned.")
                return True
            self.view = view
            self.anchor = drawing_annot.make_anchor(view, name, local)
            self.message.setText("")
            self.say("Move out and click where the dimension goes.")
            return True
        base = drawing.view_position(self.view)
        data = {
            "kind": "arc",
            "anchor": self.anchor,
            "off": [point[0] - base[0], point[1] - base[1]],
        }
        obj = drawing_annot.add_annotation(self.page, data, self.view)
        self.made.append(obj.Name)
        self.anchor = None
        self.clear_overlay()
        self.doc.recompute()
        taskui._end_transaction(self.doc)
        self.doc.openTransaction("Arc Length Dimension")
        self.say("Placed. Click another arc, or Enter / Esc.")
        return True

    def on_move(self, point, event):
        if self._closed or self.anchor is None:
            return
        self.clear_overlay()
        sig = self.anchor["sig"]
        centre = drawing.local_to_page(self.view, (sig[0], sig[1]))
        r = math.hypot(point[0] - centre[0], point[1] - centre[1])
        self.overlay_circle(centre, r)

    def escape(self):
        if self.anchor is not None:
            self.anchor = None
            self.clear_overlay()
            self.say("Click an arc of a view.")
            return
        taskui.press_dialog_button("accept")


# ------------------------------------------------------------------ annotations with a leader
class AnnotationPanel(DrawingPanel):
    """A symbol on an edge: click the edge (its arrow or foot goes there), then where the
    text, frame or symbol goes; the fields change it live. Double-click it later to edit."""

    kind = ""
    title = "Annotation"
    icon = "dw_symbol"
    free = False  # may be put on empty paper without an edge
    first_hint = "Click an edge of a view."
    place_hint = "Click where it goes."

    def __init__(self, page, obj=None):
        super().__init__(page, self.title if obj is None else "Edit %s" % self.title)
        self.obj = obj
        self.view = None
        self.anchor = None
        data = drawing_annot.annotation_data(obj) if obj is not None else {}
        self.build(data)
        self.finish_layout()
        if obj is not None:
            self.view = drawing_annot.annotation_view(obj, data)
            self.anchor = data.get("anchor")
            self.say("Change the fields, then OK. Drag it on the sheet to move it.")
        else:
            self.say(self.first_hint)

    # -- subclasses ------------------------------------------------------------------------
    def build(self, data):
        pass

    def fields(self):
        return {}

    def problem(self):
        return ""

    # -- the two clicks ----------------------------------------------------------------------
    def on_press(self, point, event):
        if self.obj is not None:
            return True
        if self.view is None and self.anchor is None:
            view, name, local = _pick(self, point, want_vertex=True)
            if view is None or name is None:
                if self.free and view is None:
                    return self._create(None, None, point)
                self.message.setText(
                    "Click on an edge of a view (the %s attaches to it)." % self.title.lower()
                )
                return True
            self.view = view
            self.anchor = drawing_annot.make_anchor(view, name, local)
            self.message.setText("")
            self.say(self.place_hint)
            return True
        return self._create(self.view, self.anchor, point)

    def _create(self, view, anchor, point):
        problem = self.problem()
        if problem:
            self.message.setText(problem)
            return True
        base = drawing.view_position(view) if view is not None else (0.0, 0.0)
        data = {
            "kind": self.kind,
            "anchor": anchor,
            "off": [point[0] - base[0], point[1] - base[1]],
        }
        data.update(self.fields())
        self.obj = drawing_annot.add_annotation(self.page, data, view)
        self.view = view
        self.clear_overlay()
        self.say("Change the fields, then OK.")
        self.schedule()
        return True

    def on_move(self, point, event):
        if self._closed or self.obj is not None or self.anchor is None:
            return
        self.clear_overlay()
        start = drawing_annot.page_point(self.view, self.anchor)
        if start is not None:
            self.overlay_line(start, point, dashed=False)

    def changed(self, *_args):
        if self._closed or self.obj is None:
            return
        problem = self.problem()
        self.message.setText(problem)
        if problem:
            return
        data = drawing_annot.annotation_data(self.obj)
        data.update(self.fields())
        drawing_annot.update_annotation(self.obj, data)
        self.schedule()

    def escape(self):
        if self.obj is None and self.anchor is not None:
            self.anchor = None
            self.view = None
            self.clear_overlay()
            self.say(self.first_hint)
            return
        super().escape()

    def accept(self):
        if self.obj is None:
            self.message.setText("Click an edge, then where it goes, first.")
            return False
        problem = self.problem()
        if problem:
            self.message.setText(problem)
            return False
        self.changed()
        return super().accept()


class LeaderPanel(AnnotationPanel):
    """Fusion's Leader: an arrow on an edge, a line to the text, the text typed in."""

    kind = "leader"
    title = "Leader"
    icon = "dw_text"
    place_hint = "Click where the text goes, then type it."

    def build(self, data):
        self.text = QtWidgets.QPlainTextEdit("\n".join(data.get("lines") or []))
        self.text.setObjectName("SciForgeLeaderText")
        self.text.setMaximumHeight(80)
        self.layout.addRow("Text", self.text)
        self.text.textChanged.connect(self.changed)

    def fields(self):
        lines = self.text.toPlainText().splitlines()
        return {"lines": lines or ["Text"]}

    def _create(self, view, anchor, point):
        result = super()._create(view, anchor, point)
        try:
            self.text.setFocus()
        except RuntimeError:
            pass
        return result

    def on_key(self, key, event):
        if key == QtCore.Qt.Key_Escape:
            _later(self.escape)
        return True

    def problem(self):
        if self.obj is not None and not self.text.toPlainText().strip():
            return "Type the leader's text (or Cancel)."
        return ""


class FeatureControlPanel(AnnotationPanel):
    """Fusion's Feature Control Frame (GD&T): characteristic, tolerance (diameter zone,
    material modifier), up to three datums with modifiers, and a second row for a
    composite frame. Click an edge for its leader (or empty paper for none)."""

    kind = "fcf"
    title = "Feature Control Frame"
    free = True
    first_hint = "Click an edge of a view for the leader (or empty paper for a frame alone)."
    place_hint = "Click where the frame goes."

    def build(self, data):
        fcf = data.get("fcf") or {}
        row1 = fcf.get("row1") or {}
        row2 = fcf.get("row2") or {}
        self.char = _combo([c[1] for c in ac.CHARACTERISTICS])
        self.char.setObjectName("SciForgeFcfCharacteristic")
        names = dict(ac.CHARACTERISTICS)
        self.char.setCurrentText(names.get(row1.get("char", "position"), "Position"))
        self.layout.addRow("Characteristic", self.char)
        self.rows = []
        for index, row in ((1, row1), (2, row2)):
            widgets = self._row(index, row)
            self.rows.append(widgets)
        self.composite = QtWidgets.QCheckBox("Composite (a second row)")
        self.composite.setObjectName("SciForgeFcfComposite")
        self.composite.setChecked(bool(fcf.get("composite")) and bool(row2))
        self.layout.addRow(self.composite)
        self._row_widgets(2, self.composite.isChecked())
        self.char.currentTextChanged.connect(self.changed)
        self.composite.toggled.connect(self._composite)

    def _row(self, index, row):
        dia = QtWidgets.QCheckBox("⌀ (a round zone)")
        dia.setObjectName("SciForgeFcfDiameter%d" % index)
        dia.setChecked(bool(row.get("dia", index == 1 and not row)))
        tol = QtWidgets.QLineEdit(str(row.get("tol", "0.1" if index == 1 else "0.05")))
        tol.setObjectName("SciForgeFcfTolerance%d" % index)
        mod = _combo([m[1] for m in ac.MODIFIERS])
        mod.setObjectName("SciForgeFcfModifier%d" % index)
        mod.setCurrentIndex(
            [m[0] for m in ac.MODIFIERS].index(row.get("mod", ""))
            if row.get("mod", "") in [m[0] for m in ac.MODIFIERS]
            else 0
        )
        datums = []
        given = list(row.get("datums") or [])
        for d in range(3):
            letter = QtWidgets.QLineEdit(given[d][0] if d < len(given) else "")
            letter.setObjectName("SciForgeFcfDatum%d_%d" % (index, d + 1))
            letter.setMaxLength(3)
            dmod = _combo([m[1] for m in ac.MODIFIERS])
            dmod.setObjectName("SciForgeFcfDatumModifier%d_%d" % (index, d + 1))
            if d < len(given) and len(given[d]) > 1 and given[d][1] in [m[0] for m in ac.MODIFIERS]:
                dmod.setCurrentIndex([m[0] for m in ac.MODIFIERS].index(given[d][1]))
            datums.append((letter, dmod))
        suffix = "" if index == 1 else " (row 2)"
        self.layout.addRow("Tolerance" + suffix, tol)
        self.layout.addRow(dia)
        self.layout.addRow("Material condition" + suffix, mod)
        for d, (letter, dmod) in enumerate(datums):
            line = QtWidgets.QWidget()
            box = QtWidgets.QHBoxLayout(line)
            box.setContentsMargins(0, 0, 0, 0)
            box.addWidget(letter, 1)
            box.addWidget(dmod, 2)
            self.layout.addRow(("Primary", "Secondary", "Tertiary")[d] + " datum" + suffix, line)
            letter.textEdited.connect(self.changed)
            dmod.currentTextChanged.connect(self.changed)
        dia.toggled.connect(self.changed)
        tol.textEdited.connect(self.changed)
        mod.currentTextChanged.connect(self.changed)
        return {"dia": dia, "tol": tol, "mod": mod, "datums": datums}

    def _row_widgets(self, index, on):
        widgets = self.rows[index - 1]
        items = [widgets["dia"], widgets["tol"], widgets["mod"]] + [
            w.parentWidget() for w, _m in widgets["datums"]
        ]
        for widget in items:
            try:
                self.layout.setRowVisible(widget, on)
            except Exception:
                widget.setVisible(on)

    def _composite(self, on):
        self._row_widgets(2, on)
        self.changed()

    def _row_data(self, index):
        widgets = self.rows[index - 1]
        mods = [m[0] for m in ac.MODIFIERS]
        datums = []
        for letter, dmod in widgets["datums"]:
            text = letter.text().strip().upper()
            if text:
                datums.append([text, mods[dmod.currentIndex()]])
        names = [c[0] for c in ac.CHARACTERISTICS]
        return {
            "char": names[self.char.currentIndex()],
            "dia": widgets["dia"].isChecked(),
            "tol": widgets["tol"].text().strip(),
            "mod": mods[widgets["mod"].currentIndex()],
            "datums": datums,
        }

    def fields(self):
        fcf = {"row1": self._row_data(1)}
        if self.composite.isChecked():
            fcf["row2"] = self._row_data(2)
            fcf["composite"] = True
        return {"fcf": fcf}

    def problem(self):
        rows = [1, 2] if self.composite.isChecked() else [1]
        for index in rows:
            text = self.rows[index - 1]["tol"].text().strip()
            if _float(text) is None:
                return "Type the tolerance as a number (like 0.1)%s." % (
                    "" if index == 1 else " in row 2"
                )
        return ""


class DatumPanel(AnnotationPanel):
    """Fusion's Datum Identifier: a letter in a box, a triangle on the datum feature's
    edge."""

    kind = "datum"
    title = "Datum Identifier"
    place_hint = "Click where the datum's box goes."

    def build(self, data):
        letter = data.get("letter") or drawing_annot.next_datum_letter(self.page)
        self.letter = QtWidgets.QLineEdit(letter)
        self.letter.setObjectName("SciForgeDatumLetter")
        self.letter.setMaxLength(3)
        self.layout.addRow("Datum", self.letter)
        self.letter.textEdited.connect(self.changed)

    def fields(self):
        return {"letter": self.letter.text().strip().upper() or "A"}

    def problem(self):
        text = self.letter.text().strip()
        if not text:
            return "Type the datum's letter."
        if not text.isalpha():
            return "A datum is named with letters (A, B, C...)."
        return ""


class SurfaceTexturePanel(AnnotationPanel):
    """Fusion's Surface Texture: the symbol (basic, material removal required or
    prohibited), the roughness, the lay and All around; on an edge, or with a leader when
    placed away from it."""

    kind = "texture"
    title = "Surface Texture"
    place_hint = "Click where the symbol goes (on the edge, or away from it for a leader)."

    def build(self, data):
        texture = data.get("texture") or {}
        self.kind_box = _combo([k[1] for k in ac.SURFACE_KINDS])
        self.kind_box.setObjectName("SciForgeTextureKind")
        kinds = [k[0] for k in ac.SURFACE_KINDS]
        self.kind_box.setCurrentIndex(
            kinds.index(texture.get("kind", "removal"))
            if texture.get("kind", "removal") in kinds
            else 1
        )
        self.value = QtWidgets.QLineEdit(texture.get("value", "Ra 3.2"))
        self.value.setObjectName("SciForgeTextureValue")
        self.lay = _combo(list(ac.LAYS), texture.get("lay", ""))
        self.lay.setObjectName("SciForgeTextureLay")
        self.around = QtWidgets.QCheckBox("All around")
        self.around.setObjectName("SciForgeTextureAllAround")
        self.around.setChecked(bool(texture.get("all_around")))
        self.layout.addRow("Symbol", self.kind_box)
        self.layout.addRow("Roughness", self.value)
        self.layout.addRow("Lay", self.lay)
        self.layout.addRow(self.around)
        self.kind_box.currentTextChanged.connect(self.changed)
        self.value.textEdited.connect(self.changed)
        self.lay.currentTextChanged.connect(self.changed)
        self.around.toggled.connect(self.changed)

    def fields(self):
        kinds = [k[0] for k in ac.SURFACE_KINDS]
        return {
            "texture": {
                "kind": kinds[self.kind_box.currentIndex()],
                "value": self.value.text().strip(),
                "lay": self.lay.currentText(),
                "all_around": self.around.isChecked(),
            }
        }

    def _create(self, view, anchor, point):
        start = drawing_annot.page_point(view, anchor)
        if start is not None and math.hypot(point[0] - start[0], point[1] - start[1]) < 2.0:
            point = start  # the symbol stands on the edge
        return super()._create(view, anchor, point)


PANELS = {
    "leader": LeaderPanel,
    "fcf": FeatureControlPanel,
    "datum": DatumPanel,
    "texture": SurfaceTexturePanel,
}


# ------------------------------------------------------------------ Edge Extension
class EdgeExtensionPanel(DrawingPanel):
    """Fusion's Edge Extension: click two straight edges; thin lines extend them to where
    they meet (a rounded corner's sharp corner) and a point there takes dimensions."""

    title = "Edge Extension"
    icon = "dw_centerline"

    def __init__(self, page):
        super().__init__(page, "Edge Extension")
        self.first = None
        self.made = 0
        self.finish_layout()
        self.say("Click the first of two straight edges.")

    def on_press(self, point, event):
        view, name, _local = pick_at(
            self.page, point, self.tolerance(), want_vertex=False, curve="line"
        )
        info = drawing.edge_info(view, name) if view is not None and name else None
        if info is None or info["kind"] != "line":
            self.message.setText("Click a straight edge.")
            return True
        self.message.setText("")
        if self.first is None or not drawing.same(self.first[0], view):
            self.first = (view, name)
            self.say("Click the second edge.")
            return True
        try:
            drawing.add_edge_extension(view, self.first[1], name)
        except drawing.DrawingError as exc:
            self.message.setText(str(exc))
            return True
        self.first = None
        self.made += 1
        view.requestPaint()
        self.schedule()
        self.say("Edges extended. Click two more edges, or Enter / Esc.")
        return True

    def escape(self):
        taskui.press_dialog_button("accept")


# ------------------------------------------------------------------ commands
class _Command(drawing_ui._Base):
    panel = None

    def run(self):
        drawing_ui._start(self.panel)


class EditDimensionCommand(drawing_ui._Base):
    title = "Edit Dimension"
    tip = "The Dimension dialog of the selected dimension (or double-click it)"
    icon = "dw_dimension"

    def run(self):
        page = drawing_ui._need_page()
        if page is None:
            return
        dims = [o for o in _selected_on(page) if o.TypeId == drawing.DIMENSION]
        if len(dims) != 1:
            commands.tell("Select one dimension on the sheet (or double-click it).")
            return
        edit(dims[0])


class OrdinateCommand(_Command):
    title = "Ordinate Dimension"
    tip = "Distances from one origin, each value at the end of a leader"
    icon = "dw_dimension"
    panel = OrdinatePanel


class BaselineCommand(_Command):
    title = "Baseline Dimension"
    tip = "Dimensions from one end of an existing dimension, stacked"
    icon = "dw_dimension"
    panel = BaselinePanel


class ChainCommand(_Command):
    title = "Chain Dimension"
    tip = "Dimensions one after the other, on the line of an existing dimension"
    icon = "dw_dimension"
    panel = ChainPanel


class ArcLengthCommand(_Command):
    title = "Arc Length Dimension"
    tip = "The length along an arc"
    icon = "dw_dimension"
    panel = ArcLengthPanel


class LeaderCommand(_Command):
    title = "Leader"
    tip = "An arrow on an edge and a note"
    icon = "dw_text"
    panel = LeaderPanel


class FeatureControlCommand(_Command):
    title = "Feature Control Frame"
    tip = "A geometric tolerance (GD&T) with its datums"
    icon = "dw_symbol"
    panel = FeatureControlPanel


class DatumCommand(_Command):
    title = "Datum Identifier"
    tip = "A datum letter on a feature's edge"
    icon = "dw_symbol"
    panel = DatumPanel


class SurfaceTextureCommand(_Command):
    title = "Surface Texture"
    tip = "A surface finish symbol (roughness, lay)"
    icon = "dw_symbol"
    panel = SurfaceTexturePanel


class EdgeExtensionCommand(_Command):
    title = "Edge Extension"
    tip = "Extend two edges to where they meet (a rounded corner's sharp corner)"
    icon = "dw_centerline"
    panel = EdgeExtensionPanel


COMMANDS = {
    "SciForge_DrawingEditDimension": EditDimensionCommand,
    "SciForge_DrawingOrdinateDimension": OrdinateCommand,
    "SciForge_DrawingBaselineDimension": BaselineCommand,
    "SciForge_DrawingChainDimension": ChainCommand,
    "SciForge_DrawingArcLengthDimension": ArcLengthCommand,
    "SciForge_DrawingLeader": LeaderCommand,
    "SciForge_DrawingFeatureControlFrame": FeatureControlCommand,
    "SciForge_DrawingDatumIdentifier": DatumCommand,
    "SciForge_DrawingSurfaceTexture": SurfaceTextureCommand,
    "SciForge_DrawingEdgeExtension": EdgeExtensionCommand,
}
