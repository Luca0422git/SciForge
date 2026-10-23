# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Sheet Metal Rules dialog (SHEET METAL > MODIFY > Sheet Metal Rules).

Two lists, In This Design and Library. Under each: New (a copy of the selected rule, so it
keeps that rule's units, as Fusion's New Rule does), Edit (or a double-click), Copy (library
-> design, design -> library), Delete (refused with the reason while a body follows the rule,
for the active rule and for SciForge's built-in library rules) and, for the design, Set
Active (the rule new sheet metal in the active component gets). Edit shows the rule's fields
on the same window: every length takes a number in the rule's units or an expression in
Thickness ("Thickness * 2"). Saving a design rule recomputes every body that follows it.
The whole visit is one undo step (library changes are kept in the user's preferences).
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import log, sheetmetal, ui_icon, ui_icon_path, warn
from . import sheetmetal_core as core
from . import sheetmetal_rules as rules
from .compat import QtCore, QtWidgets

LABELS = {
    "thickness": "Thickness",
    "miter_gap": "Miter/Rip/Seam Gap",
    "bend_radius": "Bend Radius",
    "k_factor": "K Factor",
    "bend_relief_shape": "Relief Shape",
    "bend_relief_width": "Relief Width",
    "bend_relief_depth": "Relief Depth",
    "bend_relief_remnant": "Relief Remnant",
    "corner_relief_2bend_shape": "Relief Shape",
    "corner_relief_2bend_placement": "Relief Placement",
    "corner_relief_2bend_size": "Relief Size",
    "corner_relief_3bend_shape": "Relief Shape",
    "corner_relief_3bend_radius": "Relief Radius",
}
GROUPS = [
    ("", ("thickness", "miter_gap")),
    ("Bend", ("bend_radius", "k_factor")),
    ("Bend Relief", ("bend_relief_shape", "bend_relief_width", "bend_relief_depth")),
    ("", ("bend_relief_remnant",)),
    (
        "Corner Relief (2 bends)",
        ("corner_relief_2bend_shape", "corner_relief_2bend_placement", "corner_relief_2bend_size"),
    ),
    ("Corner Relief (3 bends)", ("corner_relief_3bend_shape", "corner_relief_3bend_radius")),
]
CHOICE_TEXT = {
    "straight": "Straight",
    "tear": "Tear",
    "round": "Round",
    "square": "Square",
    "trim_to_bend": "Trim To Bend",
    "linear_weld": "Linear Weld",
    "arc_weld": "Arc Weld",
    "laser_weld": "Laser Weld",
    "intersection": "Intersection",
    "tangent": "Tangent",
    "no_replacement": "No Replacement",
    "full_round": "Full Round",
    "round_with_radius": "Round With Radius",
    "mm": "mm",
    "in": "in",
}


class RulesDialog(QtWidgets.QDialog):
    last = None

    def __init__(self, doc, parent=None):
        super().__init__(parent or Gui.getMainWindow())
        RulesDialog.last = self
        self.doc = doc
        self.setObjectName("SciForgeSheetMetalRules")
        self.setWindowTitle("Sheet Metal Rules")
        self.setWindowIcon(ui_icon("sm_rules"))
        self.resize(460, 560)
        doc.openTransaction("Sheet Metal Rules")
        self._changed = False
        self.editing = None  # ("design" | "library", old name or None)
        layout = QtWidgets.QVBoxLayout(self)
        self.pages = QtWidgets.QStackedWidget()
        layout.addWidget(self.pages, 1)
        self.pages.addWidget(self._lists_page())
        self.pages.addWidget(self._edit_page())
        self.message = QtWidgets.QLabel("")
        self.message.setObjectName("SciForgeSheetMetalRules_message")
        self.message.setWordWrap(True)
        self.message.setStyleSheet("color: #ff8a80;")
        layout.addWidget(self.message)
        self.close_button = QtWidgets.QPushButton("Close")
        self.close_button.setObjectName("SciForgeSheetMetalRules_close")
        self.close_button.clicked.connect(self.accept)
        row = QtWidgets.QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.close_button)
        layout.addLayout(row)
        self.reload()

    # -- the two lists ----------------------------------------------------------------------
    def _list(self, key, title, buttons):
        box = QtWidgets.QGroupBox(title)
        inner = QtWidgets.QVBoxLayout(box)
        widget = QtWidgets.QListWidget()
        widget.setObjectName("SciForgeSheetMetalRules_" + key)
        widget.itemDoubleClicked.connect(lambda *_a: self._safe(self.edit_rule, key))
        inner.addWidget(widget)
        row = QtWidgets.QHBoxLayout()
        for text, fn in buttons:
            button = QtWidgets.QPushButton(text)
            button.setObjectName("SciForgeSheetMetalRules_%s_%s" % (key, text.split()[0].lower()))
            button.clicked.connect(lambda _c=False, f=fn: self._safe(f, key))
            row.addWidget(button)
        inner.addLayout(row)
        return box, widget

    def _lists_page(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        box, self.design = self._list(
            "design",
            "In This Design",
            [
                ("New", self.new_rule),
                ("Edit", self.edit_rule),
                ("Copy to Library", self.copy_rule),
                ("Delete", self.delete_rule),
                ("Set Active", self.set_active),
            ],
        )
        layout.addWidget(box, 1)
        box, self.library = self._list(
            "library",
            "Library",
            [
                ("New", self.new_rule),
                ("Edit", self.edit_rule),
                ("Copy to Design", self.copy_rule),
                ("Delete", self.delete_rule),
            ],
        )
        layout.addWidget(box, 1)
        return page

    def reload(self):
        active = sheetmetal.active_rule_name(self.doc, self._component())
        self._fill(self.design, sheetmetal.design_rules(self.doc), active, "active")
        self._fill(self.library, rules.library_rules(), core.DEFAULT_RULE, "Default")

    def _fill(self, widget, items, marked, word):
        current = widget.currentItem().data(QtCore.Qt.UserRole) if widget.currentItem() else None
        widget.clear()
        for rule in items:
            name = rule["name"]
            text = "%s (%s)" % (name, word) if name == marked else name
            item = QtWidgets.QListWidgetItem(text)
            item.setData(QtCore.Qt.UserRole, name)
            item.setToolTip(
                "Thickness %s, bend radius %s, K %s"
                % (
                    core.display_value(rule, "thickness"),
                    core.display_value(rule, "bend_radius"),
                    rule.get("k_factor"),
                )
            )
            widget.addItem(item)
            if name == current:
                widget.setCurrentItem(item)

    def _component(self):
        try:
            from . import components

            component = components.active_component(self.doc)
            return component if getattr(component, sheetmetal.RULE_PROP, "") else None
        except Exception:
            return None

    def _picked(self, key):
        widget = self.design if key == "design" else self.library
        item = widget.currentItem()
        if item is None:
            raise ValueError("Click a rule in the list first.")
        return item.data(QtCore.Qt.UserRole)

    def _rule(self, key, name):
        if key == "design":
            return sheetmetal.find_rule(self.doc, name)
        return rules.find_library_rule(name)

    def _safe(self, fn, key):
        try:
            self.message.setText("")
            fn(key)
        except ValueError as exc:
            self.message.setText("⚠ %s" % exc)
        except Exception as exc:
            warn("Sheet Metal Rules: %s" % exc)
            self.message.setText("⚠ %s" % exc)

    # -- actions ----------------------------------------------------------------------------------
    def new_rule(self, key):
        widget = self.design if key == "design" else self.library
        item = widget.currentItem()
        base = self._rule(key, item.data(QtCore.Qt.UserRole)) if item else None
        if base is None:
            base = core.library_rule(core.DEFAULT_RULE)
        taken = [
            r["name"]
            for r in (
                sheetmetal.design_rules(self.doc) if key == "design" else rules.library_rules()
            )
        ]
        rule = rules.new_rule_from(base, taken)
        self._open_editor(key, None, rule, new=True)

    def edit_rule(self, key):
        name = self._picked(key)
        if key == "library" and rules.is_builtin(name):
            raise ValueError(
                "'%s' is one of SciForge's built-in rules: use New to make your own copy." % name
            )
        self._open_editor(key, name, self._rule(key, name), new=False)

    def copy_rule(self, key):
        name = self._picked(key)
        if key == "design":
            got = rules.copy_to_library(self.doc, name)
            self.message.setText("'%s' copied to the library as '%s'." % (name, got))
        else:
            got = rules.copy_to_design(self.doc, name)
            self._changed = True
            self.message.setText("'%s' copied into this design as '%s'." % (name, got))
        self.reload()

    def delete_rule(self, key):
        name = self._picked(key)
        if key == "design":
            rules.delete_design_rule(self.doc, name)
            self._changed = True
        else:
            rules.delete_library_rule(name)
        self.reload()
        log("sheet metal rule '%s' deleted" % name)

    def set_active(self, key):
        name = self._picked("design")
        sheetmetal.set_active_rule(self.doc, name, self._component())
        self._changed = True
        self.reload()

    # -- the editor --------------------------------------------------------------------------------
    def _edit_page(self):
        page = QtWidgets.QWidget()
        outer = QtWidgets.QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        holder = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(holder)
        self.fields = {}
        self.name_field = QtWidgets.QLineEdit()
        self.name_field.setObjectName("SciForgeSheetMetalRules_field_name")
        form.addRow("Name", self.name_field)
        self.units_field = QtWidgets.QComboBox()
        self.units_field.setObjectName("SciForgeSheetMetalRules_field_units")
        for unit in core.UNITS:
            self.units_field.addItem(unit, unit)
        self.units_field.setToolTip("A rule's units are fixed when it is made")
        form.addRow("Units", self.units_field)
        for title, keys in GROUPS:
            if title:
                label = QtWidgets.QLabel("<b>%s</b>" % title)
                form.addRow(label)
            for key in keys:
                kind = core.FIELDS[key][0]
                if kind == "choice":
                    widget = QtWidgets.QComboBox()
                    for value in core.CHOICES[key]:
                        widget.addItem(CHOICE_TEXT.get(value, value), value)
                    if key == "corner_relief_2bend_shape":
                        widget.currentIndexChanged.connect(self._placement_rule)
                else:
                    widget = QtWidgets.QLineEdit()
                    if kind == "length":
                        widget.setToolTip(
                            "A number in the rule's units, or an expression in Thickness "
                            "(Thickness * 2)"
                        )
                if key == "k_factor":
                    widget.setToolTip("K = where the neutral layer lies: its offset ÷ thickness")
                if key == "corner_relief_2bend_size":
                    widget.setToolTip(
                        "Measured on the flat pattern; for Round, the relief's diameter "
                        "(SciForge's choice)"
                    )
                widget.setObjectName("SciForgeSheetMetalRules_field_" + key)
                form.addRow(LABELS[key], widget)
                self.fields[key] = widget
        scroll.setWidget(holder)
        outer.addWidget(scroll, 1)
        row = QtWidgets.QHBoxLayout()
        row.addStretch(1)
        self.save_button = QtWidgets.QPushButton("Save")
        self.save_button.setObjectName("SciForgeSheetMetalRules_save")
        self.save_button.clicked.connect(lambda: self._safe(lambda _k: self.save_editor(), ""))
        self.back_button = QtWidgets.QPushButton("Cancel")
        self.back_button.setObjectName("SciForgeSheetMetalRules_back")
        self.back_button.clicked.connect(self.close_editor)
        row.addWidget(self.save_button)
        row.addWidget(self.back_button)
        outer.addLayout(row)
        return page

    def _placement_rule(self, *_):
        """Round takes Intersection or Tangent, Square Intersection only, the others none."""
        try:
            shape = self.fields["corner_relief_2bend_shape"].currentData()
            box = self.fields["corner_relief_2bend_placement"]
            box.setEnabled(shape in ("round", "square"))
            if shape == "square":
                box.setCurrentIndex(box.findData("intersection"))
        except Exception as exc:
            warn("Sheet Metal Rules: %s" % exc)

    def _open_editor(self, key, old, rule, new):
        self.editing = (key, old)
        self.name_field.setText(rule["name"])
        self.units_field.setCurrentIndex(self.units_field.findData(rule.get("units", "mm")))
        self.units_field.setEnabled(new)
        for field, widget in self.fields.items():
            value = rule.get(field, core.FIELDS[field][1])
            if isinstance(widget, QtWidgets.QComboBox):
                widget.setCurrentIndex(max(0, widget.findData(value)))
            elif core.FIELDS[field][0] == "length":
                widget.setText(core.display_value(rule, field))
            else:
                widget.setText(str(value))
        self._placement_rule()
        self.setWindowTitle("Sheet Metal Rules - %s" % ("New Rule" if new else rule["name"]))
        self.pages.setCurrentIndex(1)

    def close_editor(self, *_):
        self.editing = None
        self.setWindowTitle("Sheet Metal Rules")
        self.pages.setCurrentIndex(0)

    def editor_rule(self):
        """The rule as typed in the editor (raises ValueError with the reason)."""
        units = self.units_field.currentData()
        rule = {"name": self.name_field.text().strip(), "units": units, "unfold_rule": "k_factor"}
        for field, widget in self.fields.items():
            kind = core.FIELDS[field][0]
            if isinstance(widget, QtWidgets.QComboBox):
                rule[field] = widget.currentData()
            elif kind == "length":
                try:
                    rule[field] = core.parse_length(widget.text(), units)
                except ValueError as exc:
                    raise ValueError("%s: %s" % (LABELS[field], exc))
            else:
                rule[field] = widget.text().strip()
        problems = core.validate(rule)
        if problems:
            raise ValueError(problems[0])
        return rule

    def save_editor(self):
        if self.editing is None:
            return
        key, old = self.editing
        rule = self.editor_rule()
        if key == "design":
            rules.save_design_rule(self.doc, rule, old_name=old)
            self._changed = True
            self.doc.recompute()
        else:
            rules.save_library_rule(rule, old_name=old)
        self.close_editor()
        self.reload()
        log("sheet metal rule '%s' saved (%s)" % (rule["name"], key))

    # -- closing --------------------------------------------------------------------------------
    def accept(self):
        try:
            if self.pages.currentIndex() == 1:
                self.close_editor()
            self.doc.commitTransaction()
            if self._changed:
                self.doc.recompute()
        except Exception as exc:
            warn("Sheet Metal Rules: %s" % exc)
        super().accept()

    def reject(self):
        try:
            if self.pages.currentIndex() == 1:
                self.close_editor()
                return
            self.doc.commitTransaction()
        except Exception as exc:
            warn("Sheet Metal Rules: %s" % exc)
        super().reject()


class RulesCommand:
    def GetResources(self):
        return {
            "MenuText": "Sheet Metal Rules",
            "ToolTip": "The sheet metal rules of this design and of your library: thickness, "
            "bend radius, K factor, reliefs",
            "Pixmap": ui_icon_path("sm_rules"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            from . import commands

            if not commands.finish_open_dialog():
                return
            dialog = RulesDialog(App.ActiveDocument)
            dialog.show()
            log("Sheet Metal Rules opened")
        except Exception as exc:
            warn("Sheet Metal Rules failed to open: %s" % exc)


COMMANDS = {"SciForge_SheetMetalRules": RulesCommand}
