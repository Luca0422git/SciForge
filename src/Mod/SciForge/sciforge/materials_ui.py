# SPDX-License-Identifier: LGPL-2.1-or-later
"""Manage Materials (MODIFY > Manage Materials): Fusion's Material Browser.

Two tabs, Physical and Appearance. Each lists In This Design (what the bodies are made of /
look like, with how many bodies), Favorites, the Library (by group) and the user's own (My
Materials / My Appearances), with a search box; the right side shows the selected entry
(density and the other physical values; the colour). Assign to Selection gives the selected
bodies the entry (one undo step); the star adds it to Favorites; New Material makes a material
of the user's own from the selected one with its own name and density (kept in FreeCAD's User
material library, so Physical Material lists it too); New Appearance makes a colour of the
user's own. Sources: docs/sciforge/parity/misc.md. The library and assignment are
material.py / appearance.py.
"""

import json

import FreeCAD as App
import FreeCADGui as Gui

from . import appearance, bodies, commands, log, material, ui_icon, ui_icon_path, warn
from .compat import QtCore, QtGui, QtWidgets

PREFS = "User parameter:BaseApp/Preferences/Mod/SciForge/Preferences"
LOOK_FAVORITES = "AppearanceFavorites"
MY_LOOKS = "MyAppearances"
PHYSICAL_VALUES = [
    ("Density", "Density", "g/cm^3"),
    ("YoungsModulus", "Young's Modulus", "GPa"),
    ("PoissonRatio", "Poisson's Ratio", ""),
    ("YieldStrength", "Yield Strength", "MPa"),
    ("UltimateTensileStrength", "Ultimate Tensile Strength", "MPa"),
    ("ThermalConductivity", "Thermal Conductivity", "W/m/K"),
    ("SpecificHeat", "Specific Heat", "J/kg/K"),
]
_state = {"dialog": None}


# -- the user's own appearances and favourites ----------------------------------------------------
def my_looks():
    try:
        data = json.loads(App.ParamGet(PREFS).GetString(MY_LOOKS, "") or "[]")
    except Exception:
        data = []
    return [d for d in data if isinstance(d, dict) and d.get("key")]


def add_look(name, color_hex):
    """New Appearance: a colour of the user's own, by name. Returns the look."""
    name = (name or "").strip()
    if not name:
        raise material.MaterialError("Give the new appearance a name.")
    taken = {l["label"].lower() for l in appearance.library() + my_looks()}
    if name.lower() in taken:
        raise material.MaterialError("There is already an appearance called %s." % name)
    color = QtGui.QColor(color_hex.strip() if color_hex else "")
    if not color.isValid():
        raise material.MaterialError("The colour is a hex code such as #3a7bd5.")
    look = appearance.custom((color.redF(), color.greenF(), color.blueF()))
    look["key"] = "my:" + name
    look["label"] = name
    look["group"] = "My Appearances"
    looks = my_looks() + [look]
    App.ParamGet(PREFS).SetString(MY_LOOKS, json.dumps(looks))
    log("appearance %s made (%s)" % (name, color.name()))
    return look


def delete_look(key):
    looks = [l for l in my_looks() if l["key"] != key]
    App.ParamGet(PREFS).SetString(MY_LOOKS, json.dumps(looks))


def look_favorites():
    text = App.ParamGet(PREFS).GetString(LOOK_FAVORITES, "")
    return [k for k in text.split(";") if k]


def set_look_favorite(key, on):
    keys = [k for k in look_favorites() if k != key]
    if on:
        keys.append(key)
    App.ParamGet(PREFS).SetString(LOOK_FAVORITES, ";".join(keys))


def find_look(key):
    for look in appearance.library() + my_looks():
        if look["key"] == key:
            return look
    return None


def selected_bodies():
    found = []
    for sel in Gui.Selection.getSelectionEx():
        body = bodies.body_of(sel.Object)
        if body is not None and body not in found:
            found.append(body)
    return found


# -- the window -----------------------------------------------------------------------------------
class _Tab(QtWidgets.QWidget):
    """One tab: search, the tree on the left, details and buttons on the right."""

    def __init__(self, browser, kind):
        super().__init__()
        self.browser = browser
        self.kind = kind  # "physical" or "appearance"
        outer = QtWidgets.QHBoxLayout(self)
        left = QtWidgets.QVBoxLayout()
        self.search = QtWidgets.QLineEdit()
        self.search.setObjectName("SciForgeMaterialSearch_" + kind)
        self.search.setPlaceholderText("Search")
        self.search.textChanged.connect(lambda *_: self.fill())
        left.addWidget(self.search)
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setObjectName("SciForgeMaterialTree_" + kind)
        self.tree.setHeaderHidden(True)
        self.tree.currentItemChanged.connect(lambda *_: self.show_selected())
        left.addWidget(self.tree, 1)
        outer.addLayout(left, 1)
        right = QtWidgets.QVBoxLayout()
        self.title = QtWidgets.QLabel("")
        self.title.setObjectName("SciForgeMaterialTitle_" + kind)
        right.addWidget(self.title)
        self.swatch = QtWidgets.QLabel("")
        self.swatch.setFixedSize(120, 60)
        right.addWidget(self.swatch)
        self.details = QtWidgets.QFormLayout()
        right.addLayout(self.details)
        self.detail_labels = {}
        if kind == "physical":
            for prop, label, _unit in PHYSICAL_VALUES:
                value = QtWidgets.QLabel("")
                value.setObjectName("SciForgeMaterialValue_" + prop)
                self.details.addRow(label, value)
                self.detail_labels[prop] = value
        right.addStretch(1)
        row = QtWidgets.QHBoxLayout()
        self.star = QtWidgets.QPushButton("Add to Favorites")
        self.star.setObjectName("SciForgeMaterialFavorite_" + kind)
        self.star.clicked.connect(lambda: self.browser.guarded(self.toggle_favorite))
        self.assign = QtWidgets.QPushButton("Assign to Selection")
        self.assign.setObjectName("SciForgeMaterialAssign_" + kind)
        self.assign.clicked.connect(lambda: self.browser.guarded(self.assign_selected))
        row.addWidget(self.star)
        row.addWidget(self.assign)
        right.addLayout(row)
        row2 = QtWidgets.QHBoxLayout()
        self.new_button = QtWidgets.QPushButton(
            "New Material" if kind == "physical" else "New Appearance"
        )
        self.new_button.setObjectName("SciForgeMaterialNew_" + kind)
        self.new_button.clicked.connect(lambda: self.browser.guarded(self.show_new))
        self.delete_button = QtWidgets.QPushButton("Delete")
        self.delete_button.setObjectName("SciForgeMaterialDelete_" + kind)
        self.delete_button.clicked.connect(lambda: self.browser.guarded(self.delete_selected))
        row2.addWidget(self.new_button)
        row2.addWidget(self.delete_button)
        right.addLayout(row2)
        self.new_box = QtWidgets.QGroupBox(
            "New Material" if kind == "physical" else "New Appearance"
        )
        self.new_box.setObjectName("SciForgeMaterialNewBox_" + kind)
        form = QtWidgets.QFormLayout(self.new_box)
        self.new_name = QtWidgets.QLineEdit()
        self.new_name.setObjectName("SciForgeMaterialNewName_" + kind)
        form.addRow("Name", self.new_name)
        self.new_value = QtWidgets.QLineEdit()
        self.new_value.setObjectName("SciForgeMaterialNewValue_" + kind)
        form.addRow("Density (g/cm³)" if kind == "physical" else "Colour (#RRGGBB)", self.new_value)
        self.based_on = QtWidgets.QLabel("")
        if kind == "physical":
            form.addRow("Based on", self.based_on)
        make = QtWidgets.QPushButton("Create")
        make.setObjectName("SciForgeMaterialCreate_" + kind)
        make.clicked.connect(lambda: self.browser.guarded(self.create))
        form.addRow(make)
        self.new_box.setVisible(False)
        right.addWidget(self.new_box)
        outer.addLayout(right, 1)

    # -- filling ----------------------------------------------------------------------------
    def _entries(self):
        if self.kind == "physical":
            return material.available()
        return appearance.library() + my_looks()

    def _favorites(self):
        return material.favorites() if self.kind == "physical" else look_favorites()

    def _in_design(self, doc):
        """[(key, label, count)] of what the design's bodies use."""
        if doc is None:
            return []
        found = {}
        if self.kind == "physical":
            for body in bodies.solid_bodies(doc):
                key = material.key_of(body) or material.default_key()
                label, _rho = material.effective(body)
                found.setdefault(key, [label, 0])[1] += 1
        else:
            for look, users in appearance.looks_in_design(doc):
                found.setdefault(look["key"], [look["label"], 0])[1] += len(users)
        return [(k, v[0], v[1]) for k, v in found.items()]

    def fill(self):
        current = self.selected_key()
        text = self.search.text().lower().split()

        def shown(label):
            return all(w in label.lower() for w in text)

        self.tree.blockSignals(True)
        try:
            self.tree.clear()
            entries = self._entries()
            by_key = {e["key"]: e for e in entries}
            doc = App.ActiveDocument
            design = QtWidgets.QTreeWidgetItem(self.tree, ["In This Design"])
            for key, label, count in self._in_design(doc):
                if shown(label):
                    self._leaf(design, key, "%s (%d)" % (label, count))
            favorites = QtWidgets.QTreeWidgetItem(self.tree, ["Favorites"])
            for key in self._favorites():
                if key in by_key and shown(by_key[key]["label"]):
                    self._leaf(favorites, key, by_key[key]["label"])
            library = QtWidgets.QTreeWidgetItem(self.tree, ["Library"])
            groups = {}
            own = QtWidgets.QTreeWidgetItem(
                self.tree, ["My Materials" if self.kind == "physical" else "My Appearances"]
            )
            for entry in entries:
                if not shown(entry["label"]):
                    continue
                if entry["group"] in ("My Materials", "My Appearances"):
                    self._leaf(own, entry["key"], entry["label"])
                    continue
                group = groups.get(entry["group"])
                if group is None:
                    group = QtWidgets.QTreeWidgetItem(library, [entry["group"]])
                    groups[entry["group"]] = group
                self._leaf(group, entry["key"], entry["label"])
            self.tree.expandAll()
            if current:
                self.select(current)
        finally:
            self.tree.blockSignals(False)
        self.show_selected()

    def _leaf(self, parent, key, label):
        item = QtWidgets.QTreeWidgetItem(parent, [label])
        item.setData(0, QtCore.Qt.UserRole, key)
        return item

    def items(self, key=None, under=None):
        found = []
        it = QtWidgets.QTreeWidgetItemIterator(self.tree)
        while it.value():
            item = it.value()
            if item.data(0, QtCore.Qt.UserRole) and (
                key is None or item.data(0, QtCore.Qt.UserRole) == key
            ):
                top = item
                while top.parent() is not None:
                    top = top.parent()
                if under is None or top.text(0) == under:
                    found.append(item)
            it += 1
        return found

    def select(self, key, under=None):
        found = self.items(key, under)
        if found:
            self.tree.setCurrentItem(found[0])
            return found[0]
        return None

    def selected_key(self):
        item = self.tree.currentItem()
        return item.data(0, QtCore.Qt.UserRole) if item is not None else None

    def show_selected(self):
        key = self.selected_key()
        is_own = bool(key) and str(key).startswith(("user:", "my:"))
        self.assign.setEnabled(bool(key))
        self.star.setEnabled(bool(key))
        self.delete_button.setEnabled(is_own)
        if not key:
            self.title.setText("")
            self.swatch.setStyleSheet("")
            for value in self.detail_labels.values():
                value.setText("")
            return
        self.star.setText(
            "Remove from Favorites" if key in self._favorites() else "Add to Favorites"
        )
        if self.kind == "physical":
            row = material.entry(key)
            self.title.setText("<b>%s</b>" % (row["label"] if row else key))
            mat = material.material_of(row)
            for prop, _label, unit in PHYSICAL_VALUES:
                self.detail_labels[prop].setText(_physical(mat, prop, unit))
            look = appearance.find(row["look"]) if row else None
            self.based_on.setText(row["label"] if row else "")
        else:
            look = find_look(key)
            self.title.setText("<b>%s</b>" % (look["label"] if look else key))
        if look:
            self.swatch.setStyleSheet(
                "background: %s; border: 1px solid #8a94a6;" % appearance.hex_color(look)
            )

    # -- actions ----------------------------------------------------------------------------
    def toggle_favorite(self):
        key = self.selected_key()
        if not key:
            return
        on = key not in self._favorites()
        if self.kind == "physical":
            material.set_favorite(key, on)
        else:
            set_look_favorite(key, on)
        self.fill()
        self.browser.say("Added to Favorites." if on else "Removed from Favorites.")

    def assign_selected(self):
        key = self.selected_key()
        if not key:
            raise material.MaterialError("Pick a material first.")
        doc = App.ActiveDocument
        targets = selected_bodies()
        if doc is None or not targets:
            raise material.MaterialError(
                "Select the bodies first (in the browser or the 3D view), then Assign."
            )
        doc.openTransaction("Physical Material" if self.kind == "physical" else "Appearance")
        try:
            for body in targets:
                if self.kind == "physical":
                    material.assign(body, key)
                else:
                    appearance.set_body(body, find_look(key))
            doc.recompute()
        except Exception:
            doc.abortTransaction()
            raise
        doc.commitTransaction()
        try:
            from . import bodies_gui

            bodies_gui.sync(doc)
        except Exception:
            pass
        if self.kind == "physical":
            label = material.entry(key)["label"]
        else:
            label = find_look(key)["label"]
        self.fill()
        self.browser.say("%s: %s." % (", ".join(b.Label for b in targets), label))

    def show_new(self):
        self.new_box.setVisible(True)
        self.new_name.setFocus()
        if self.kind == "physical":
            row = material.entry(self.selected_key()) if self.selected_key() else None
            if row is None:
                self.select(material.default_key())
                row = material.entry(material.default_key())
            rho = material.density_of(row["key"])
            self.based_on.setText(row["label"])
            if rho is not None and not self.new_value.text():
                self.new_value.setText("%.4g" % (rho * 1e6))

    def create(self):
        if self.kind == "physical":
            base = self.selected_key() or material.default_key()
            if str(base).startswith("user:") or material.entry(base) is None:
                base = material.default_key()
            key = material.create_user_material(self.new_name.text(), base, self.new_value.text())
            label = material.entry(key)["label"]
        else:
            look = add_look(self.new_name.text(), self.new_value.text())
            key, label = look["key"], look["label"]
        self.new_name.clear()
        self.new_value.clear()
        self.new_box.setVisible(False)
        self.fill()
        own = "My Materials" if self.kind == "physical" else "My Appearances"
        self.select(key, own)
        self.browser.say("%s made: it is in %s." % (label, own))

    def delete_selected(self):
        key = self.selected_key()
        if not key or not str(key).startswith(("user:", "my:")):
            raise material.MaterialError("Only your own materials and appearances are deleted.")
        if self.kind == "physical":
            label = material.entry(key)["label"]
            material.delete_user_material(key)
            material.set_favorite(key, False)
        else:
            label = find_look(key)["label"]
            delete_look(key)
            set_look_favorite(key, False)
        self.fill()
        self.browser.say("%s deleted (bodies keep what they were given)." % label)


def _physical(mat, prop, unit):
    if mat is None:
        return "-"
    try:
        if not mat.hasPhysicalProperty(prop):
            return "-"
        value = mat.getPhysicalValue(prop)
    except Exception:
        return "-"
    try:
        if unit and hasattr(value, "getValueAs"):
            return "%.4g %s" % (float(value.getValueAs(unit)), unit.replace("^3", "³"))
        return "%.4g" % float(value) if not hasattr(value, "Value") else str(value)
    except Exception:
        return str(value)


class MaterialBrowser(QtWidgets.QDialog):
    last = None

    def __init__(self, parent=None):
        super().__init__(parent or Gui.getMainWindow())
        MaterialBrowser.last = self
        self.setObjectName("SciForgeMaterialBrowser")
        self.setWindowTitle("Material Browser")
        self.setWindowIcon(ui_icon("material"))
        self.resize(760, 520)
        layout = QtWidgets.QVBoxLayout(self)
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setObjectName("SciForgeMaterialTabs")
        self.physical = _Tab(self, "physical")
        self.appearance = _Tab(self, "appearance")
        self.tabs.addTab(self.physical, "Physical")
        self.tabs.addTab(self.appearance, "Appearance")
        layout.addWidget(self.tabs, 1)
        self.message = QtWidgets.QLabel("")
        self.message.setObjectName("SciForgeMaterialMessage")
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        row = QtWidgets.QHBoxLayout()
        row.addStretch(1)
        close = QtWidgets.QPushButton("Close")
        close.setObjectName("SciForgeMaterialClose")
        close.clicked.connect(self.reject)
        row.addWidget(close)
        layout.addLayout(row)
        self.physical.fill()
        self.appearance.fill()

    def say(self, text, ok=True):
        self.message.setStyleSheet("color: %s;" % ("#9fe0a0" if ok else "#ff8a80"))
        self.message.setText(text)

    def guarded(self, fn):
        try:
            fn()
        except material.MaterialError as exc:
            self.say(str(exc), False)
        except Exception as exc:
            warn("Manage Materials: %s" % exc)
            self.say(str(exc), False)


def show():
    dialog = _state.get("dialog")
    try:
        if dialog is not None and dialog.isVisible():
            dialog.physical.fill()
            dialog.appearance.fill()
            dialog.raise_()
            return dialog
    except RuntimeError:
        pass
    dialog = MaterialBrowser()
    _state["dialog"] = dialog

    def closed(*_):
        from . import preferences_ui

        QtCore.QTimer.singleShot(0, preferences_ui.refocus_main)

    dialog.finished.connect(closed)
    dialog.show()
    dialog.raise_()
    return dialog


class ManageMaterialsCommand:
    def GetResources(self):
        return {
            "MenuText": "Manage Materials",
            "ToolTip": "The physical materials and appearances: In This Design, Favorites, "
            "the library and your own",
            "Pixmap": ui_icon_path("material"),
        }

    def IsActive(self):
        return True

    def Activated(self):
        try:
            show()
        except Exception as exc:
            warn("Manage Materials: %s" % exc)
            commands.tell("Manage Materials could not open: %s" % exc)


COMMANDS = {"SciForge_ManageMaterials": ManageMaterialsCommand}
