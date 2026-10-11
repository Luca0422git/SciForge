# SPDX-License-Identifier: LGPL-2.1-or-later
"""Physical Material (Modify > Physical Material) with a Fusion-like dialog:

  In This Design  the materials the bodies are made of now
  Library         steels, aluminium, copper, titanium, plastics (ABS, PLA, PETG, nylon,
                  polycarbonate, acetal, acrylic...), wood, glass, with their density

Pick a material, then click bodies in the 3D view (or the browser): each click makes that
body of the material, and gives it the material's look unless it has an Appearance of its
own. Bodies selected before the command get the first material picked. The bodies' mass is
shown. OK keeps it (one undo step), Cancel / Esc puts the old materials back. The material
is FreeCAD's own (the body's ShapeMaterial, saved in the file); Inspect and Measure read the
mass through bodies.mass(). The document side is material.py.
"""
import FreeCAD as App

from . import bodies, bodies_gui, material, ui_icon_path, warn
from .bodies_panel import BodyPanel, start as _start
from .compat import QtCore, QtWidgets


class MaterialPanel(BodyPanel):
    title = "Physical Material"
    icon = "material"
    needs_pick = ()

    def __init__(self, doc):
        self.key = None
        self.pending = []
        self.touched = []
        super().__init__(doc, "Physical Material")
        self.pending = []
        for obj, _s, _p in bodies_gui.selection_entries():
            body = bodies.body_of(obj)
            if obj.Document is doc and body is not None and body not in self.pending:
                self.pending.append(body)
        bodies_gui.clear_selection()
        self._fill_design()
        self.info.setText(
            "Pick a material, then click bodies to make them of it."
            if not self.pending
            else "Pick a material for the selected bodies."
        )

    def build_form(self):
        self.layout.addRow(QtWidgets.QLabel("<b>In This Design</b>"))
        self.design = QtWidgets.QListWidget()
        self.design.setFixedHeight(90)
        self.design.itemClicked.connect(lambda item: self._guarded(lambda: self._clicked(item)))
        self.layout.addRow(self.design)
        self.layout.addRow(QtWidgets.QLabel("<b>Library</b>"))
        self.library = QtWidgets.QListWidget()
        self.library.setMinimumHeight(260)
        for row in material.available():
            rho = material.density_of(row["key"])
            text = row["label"]
            if rho is not None:
                text += "   %.3g g/cm³" % (rho * 1e6)
            item = QtWidgets.QListWidgetItem(text)
            item.setData(QtCore.Qt.UserRole, row["key"])
            item.setToolTip("%s: FreeCAD material %s" % (row["label"], row["freecad"]))
            self.library.addItem(item)
        self.library.itemClicked.connect(lambda item: self._guarded(lambda: self._clicked(item)))
        self.layout.addRow(self.library)
        self.chosen = QtWidgets.QLabel("")
        self.chosen.setStyleSheet("color: #b8c7d9;")
        self.layout.addRow("Material", self.chosen)
        self.masses = QtWidgets.QLabel("")
        self.masses.setWordWrap(True)
        self.masses.setStyleSheet("color: #b8c7d9;")
        self.layout.addRow("Mass", self.masses)

    def _fill_design(self):
        self.design.clear()
        used = {}
        for body in bodies.solid_bodies(self.doc):
            label, _rho = material.effective(body)
            used.setdefault((material.key_of(body), label), []).append(body)
        for (key, label), found in sorted(used.items(), key=lambda kv: kv[0][1]):
            item = QtWidgets.QListWidgetItem("%s  (%s)" % (label, bodies_gui.body_text(found)))
            item.setData(QtCore.Qt.UserRole, key or material.DEFAULT_KEY)
            self.design.addItem(item)
        self._show_masses()

    def _show_masses(self):
        rows = []
        for body in bodies.solid_bodies(self.doc, visible_only=True):
            kg = material.mass(body)
            label, _rho = material.effective(body)
            if kg is not None:
                rows.append("%s: %s (%s)" % (body.Label, _mass_text(kg), label))
        self.masses.setText("\n".join(rows))

    def item_for(self, label):
        for i in range(self.library.count()):
            item = self.library.item(i)
            if material.entry(item.data(QtCore.Qt.UserRole))["label"] == label:
                return item
        return None

    def _clicked(self, item):
        key = item.data(QtCore.Qt.UserRole)
        row = material.entry(key)
        if row is None:
            return
        self.key = key
        self.chosen.setText(row["label"])
        self.info.setText("Click bodies to make them of %s." % row["label"])
        if self.pending:
            pending, self.pending = self.pending, []
            for body in pending:
                self._give(body)

    def picked(self, obj, short, point):
        body = bodies.body_of(obj)
        if body is None:
            return
        if self.key is None:
            if body not in self.pending:
                self.pending.append(body)
            self.message.setText("Pick a material first, then click.")
            return
        self.message.setText("")
        self._give(body)

    def _give(self, body):
        try:
            material.assign(body, self.key)
        except material.MaterialError as exc:
            self.message.setText("⚠ %s" % exc)
            return
        if body not in self.touched:
            self.touched.append(body)
        try:
            from . import appearance

            appearance.apply(body)
        except Exception as exc:
            warn("appearance: %s" % exc)
        self._fill_design()
        self.note.setText("%s: %s" % (body.Label, material.entry(self.key)["label"]))


def _mass_text(kg):
    if kg >= 1.0:
        return "%.3f kg" % kg
    return "%.2f g" % (kg * 1000.0)


class MaterialCommand:
    def GetResources(self):
        return {
            "MenuText": "Physical Material",
            "ToolTip": "Say what bodies are made of (steel, aluminium, plastics...): their "
            "mass and look follow",
            "Pixmap": ui_icon_path("material"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            _start(MaterialPanel)
        except Exception as exc:
            warn("Physical Material could not start: %s" % exc)


COMMANDS = {"SciForge_PhysicalMaterial": MaterialCommand}
